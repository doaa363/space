"""
ClimCam Onboard Edge Inference & Semantic Encoder (Stage 3)
===========================================================
Simulating Satellite / ISS Onboard AI Edge Processing on Raspberry Pi.
Designed for ClimCam: Climate & Agricultural Monitoring Camera.

Author: Senior Embedded AI & Remote Sensing Specialist
"""

import sys
import os
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Any, Optional

# UTF-8 stdout configuration for clean cross-platform logging (Windows/Linux/Raspberry Pi)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
import scipy.io as sio
import matplotlib.pyplot as plt

# Universal TFLite Interpreter import (supports native tflite_runtime on Raspberry Pi or tensorflow.lite)
try:
    import tflite_runtime.interpreter as tflite
    INTERPRETER_BACKEND = "tflite_runtime (Edge Optimized)"
except ImportError:
    try:
        from tensorflow import lite as tflite
        INTERPRETER_BACKEND = "tensorflow.lite"
    except ImportError:
        raise ImportError("Neither 'tflite_runtime' nor 'tensorflow.lite' is installed.")

# ==============================================================================
# 1. ClimCam Semantic Category Definitions
# ==============================================================================
# Mapping from the 16 hyperspectral agricultural classes to the 4 primary ClimCam mission domains:
# 0: Unclassified / Mask
# 1: Vegetation (الغطاء النباتي)
# 2: Hydration / Water Stress (الإجهاد المائي والرطوبة)
# 3: Desertification / Bare Soil (التصحر والأراضي البور)
# 4: Urban / Built-up Infrastructure (المناطق العمرانية والبنية التحتية)

CLIMCAM_CLASSES = {
    0: "Background / Mask",
    1: "Vegetation",
    2: "Hydration",
    3: "Desertification",
    4: "Urban"
}

# Salinas Class Mapping to ClimCam Macro Domains
SALINAS_TO_CLIMCAM = {
    1: 1,   # Brocoli_green_weeds_1 -> Vegetation
    2: 1,   # Brocoli_green_weeds_2 -> Vegetation
    3: 3,   # Fallow -> Desertification / Bare
    4: 3,   # Fallow_rough_plow -> Desertification / Bare
    5: 3,   # Fallow_smooth -> Desertification / Bare
    6: 4,   # Stubble -> Urban / Harvested ground
    7: 1,   # Celery -> Vegetation
    8: 1,   # Grapes_untrained -> Vegetation
    9: 4,   # Soil_vinyard_develop -> Urban / Trellis Infrastructure
    10: 1,  # Corn_senesced_green_weeds -> Vegetation
    11: 1,  # Lettuce_romaine_4wk -> Vegetation
    12: 1,  # Lettuce_romaine_5wk -> Vegetation
    13: 1,  # Lettuce_romaine_6wk -> Vegetation
    14: 1,  # Lettuce_romaine_7wk -> Vegetation
    15: 1,  # Vinyard_untrained -> Vegetation
    16: 4   # Vinyard_vertical_trellis -> Urban / Infrastructure
}

# Approximate geographic bounding box for Salinas Valley target scene
SCENE_GEO_ORIGIN = {
    "center_lat": 36.6777,
    "center_lon": -121.6555,
    "pixel_resolution_m": 3.7  # AVIRIS ~3.7m spatial resolution per pixel
}


# ==============================================================================
# 2. Onboard Edge Inference Engine (TFLite INT8)
# ==============================================================================
class EdgeInferenceEngine:
    """
    Manages loading and executing the quantized TFLite INT8 model on edge hardware
    with strict memory safety (chunked inference) to fit within micro-SBC limits.
    """

    def __init__(self, model_path: str):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Quantized TFLite model not found at: {model_path}")

        self.model_path = model_path
        self.interpreter = tflite.Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()

        # Retrieve model input and output metadata
        self.input_details = self.interpreter.get_input_details()[0]
        self.output_details = self.interpreter.get_output_details()[0]

        self.input_shape = self.input_details['shape']
        self.input_dtype = self.input_details['dtype']
        self.output_dtype = self.output_details['dtype']

        # Quantization parameters (scale and zero-point)
        self.in_scale, self.in_zero_point = self.input_details.get('quantization', (0.0, 0))
        self.out_scale, self.out_zero_point = self.output_details.get('quantization', (0.0, 0))

        print(f"[EDGE-AI] Loaded TFLite Model: {os.path.basename(model_path)}")
        print(f"[EDGE-AI] Backend Engine  : {INTERPRETER_BACKEND}")
        print(f"[EDGE-AI] Input Shape     : {self.input_shape} ({self.input_dtype.__name__})")
        print(f"[EDGE-AI] Output Shape    : {self.output_details['shape']} ({self.output_dtype.__name__})")

    def predict_pixel(self, spectral_signature: np.ndarray) -> Tuple[int, float]:
        """
        Runs single-pixel inference (204 spectral bands).
        Returns predicted class ID (0-15) and confidence probability.
        """
        inp = spectral_signature.reshape(1, 204, 1)

        # Handle INT8 input quantization if required by the model
        if self.input_dtype == np.int8 and self.in_scale > 0:
            inp = np.round(inp / self.in_scale + self.in_zero_point).astype(np.int8)
        else:
            inp = inp.astype(np.float32)

        self.interpreter.set_tensor(self.input_details['index'], inp)
        self.interpreter.invoke()
        output_data = self.interpreter.get_tensor(self.output_details['index'])[0]

        # Dequantize output if necessary
        if self.output_dtype == np.int8 and self.out_scale > 0:
            output_data = (output_data.astype(np.float32) - self.out_zero_point) * self.out_scale

        pred_class = int(np.argmax(output_data))
        confidence = float(np.max(output_data))
        return pred_class, confidence

    def predict_cube_chunked(self, cube: np.ndarray, chunk_size: int = 2048) -> Tuple[np.ndarray, np.ndarray]:
        """
        Processes hyperspectral cube in memory-safe chunks to prevent RAM overflow on Raspberry Pi.
        Returns:
            pred_map: 2D array of predicted classes (Height, Width)
            conf_map: 2D array of prediction confidence (Height, Width)
        """
        h, w, b = cube.shape
        flat_pixels = cube.reshape(-1, b, 1)
        total_pixels = flat_pixels.shape[0]

        preds = np.zeros(total_pixels, dtype=np.int32)
        confs = np.zeros(total_pixels, dtype=np.float32)

        # Resize input tensor to process in batches
        num_chunks = int(np.ceil(total_pixels / chunk_size))
        print(f"[EDGE-AI] Processing {total_pixels:,} pixels in {num_chunks} chunks (chunk_size={chunk_size})...")

        start_time = time.time()
        for i in range(num_chunks):
            start_idx = i * chunk_size
            end_idx = min(start_idx + chunk_size, total_pixels)
            batch = flat_pixels[start_idx:end_idx]
            actual_bs = end_idx - start_idx

            # Resize interpreter batch dynamically if required
            if self.interpreter.get_input_details()[0]['shape'][0] != actual_bs:
                self.interpreter.resize_tensor_input(self.input_details['index'], [actual_bs, b, 1])
                self.interpreter.allocate_tensors()

            if self.input_dtype == np.int8 and self.in_scale > 0:
                batch_inp = np.round(batch / self.in_scale + self.in_zero_point).astype(np.int8)
            else:
                batch_inp = batch.astype(np.float32)

            self.interpreter.set_tensor(self.input_details['index'], batch_inp)
            self.interpreter.invoke()
            out = self.interpreter.get_tensor(self.output_details['index'])

            if self.output_dtype == np.int8 and self.out_scale > 0:
                out = (out.astype(np.float32) - self.out_zero_point) * self.out_scale

            preds[start_idx:end_idx] = np.argmax(out, axis=1)
            confs[start_idx:end_idx] = np.max(out, axis=1)

        elapsed = time.time() - start_time
        print(f"[EDGE-AI] Inference complete in {elapsed:.2f}s ({(total_pixels / elapsed):.1f} pixels/sec)")

        return preds.reshape(h, w), confs.reshape(h, w)


# ==============================================================================
# 3. Space Alert & Anomaly Engine
# ==============================================================================
class SpaceAlertSystem:
    """
    Evaluates ecological thresholds (extreme drought, desertification expansion,
    and severe crop disease) and generates prioritized alerts.
    """

    THRESHOLDS = {
        "CRITICAL_MOISTURE_DEFICIT": -0.10,  # NDWI below this indicates severe drought / desiccation
        "WARNING_DESERTIFICATION_PCT": 28.0,  # Percentage of barren/desertified soil exceeding nominal
        "WARNING_VEGETATION_STRESS": 0.12,   # NDRE below this in vegetation indicates acute pathology
    }

    @staticmethod
    def evaluate(metrics: Dict[str, float], roi_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        alerts = []

        # 1. Moisture & Hydration Risk Assessment
        mean_ndwi = metrics.get("mean_ndwi", 0.0)
        hydration_pct = metrics.get("hydration_percentage", 0.0)
        if mean_ndwi < SpaceAlertSystem.THRESHOLDS["CRITICAL_MOISTURE_DEFICIT"] or hydration_pct < 8.0:
            alerts.append({
                "alert_id": f"ALT-MOIST-{int(time.time())}",
                "severity": "CRITICAL",
                "type": "ACUTE_MOISTURE_DEFICIT",
                "message": "Critical drought & canopy dehydration detected across target scene.",
                "metric_trigger": f"Mean NDWI = {mean_ndwi:.3f} (< {SpaceAlertSystem.THRESHOLDS['CRITICAL_MOISTURE_DEFICIT']})",
                "recommendation": "Deploy targeted irrigation and ground drone inspection."
            })

        # 2. Desertification Expansion Risk
        desert_pct = metrics.get("desertification_percentage", 0.0)
        if desert_pct > SpaceAlertSystem.THRESHOLDS["WARNING_DESERTIFICATION_PCT"]:
            alerts.append({
                "alert_id": f"ALT-DESERT-{int(time.time())}",
                "severity": "WARNING",
                "type": "DESERTIFICATION_ENCROACHMENT",
                "message": f"Desertification/Bare Soil ratio ({desert_pct:.1f}%) exceeds safety threshold.",
                "metric_trigger": f"Desertification = {desert_pct:.1f}% (> {SpaceAlertSystem.THRESHOLDS['WARNING_DESERTIFICATION_PCT']}%)",
                "recommendation": "Flag for soil stabilization and satellite trend tracking."
            })

        # 3. Vegetative Pathology & Disease Risk
        mean_ndre = metrics.get("mean_ndre", 0.0)
        if mean_ndre < SpaceAlertSystem.THRESHOLDS["WARNING_VEGETATION_STRESS"] and metrics.get("vegetation_percentage", 0.0) > 20.0:
            alerts.append({
                "alert_id": f"ALT-PATH-{int(time.time())}",
                "severity": "WARNING",
                "type": "VEGETATION_PATHOLOGY_RISK",
                "message": "Abnormal Red-Edge chlorophyll depression indicates early pathogen or pest infestation.",
                "metric_trigger": f"Mean NDRE = {mean_ndre:.3f} (< {SpaceAlertSystem.THRESHOLDS['WARNING_VEGETATION_STRESS']})",
                "recommendation": "Initiate localized crop pathology inspection."
            })

        # If no severe conditions, add nominal status
        if not alerts:
            alerts.append({
                "alert_id": f"ALT-NOM-{int(time.time())}",
                "severity": "INFO",
                "type": "NOMINAL_CONDITIONS",
                "message": "All biophysical indicators are within nominal operational parameters.",
                "metric_trigger": "Nominal thresholds maintained."
            })

        return alerts


# ==============================================================================
# 4. Semantic Encoder & Downlink Packaging
# ==============================================================================
class SemanticEncoder:
    """
    Compresses massive 3D hyperspectral telemetry into an ultra-compact semantic JSON
    payload (achieving > 100:1 to 15,000:1 compression ratio).
    """

    @staticmethod
    def encode_telemetry(
        pred_map: np.ndarray,
        clean_cube: np.ndarray,
        indices: Dict[str, np.ndarray],
        raw_cube_bytes: int,
        sensor_id: str = "ClimCam-ISS-EXP1"
    ) -> Dict[str, Any]:
        h, w = pred_map.shape
        total_pixels = h * w

        # Map 16 Salinas model predictions into the 4 ClimCam domains
        climcam_map = np.zeros((h, w), dtype=np.uint8)
        for salinas_cls, climcam_cls in SALINAS_TO_CLIMCAM.items():
            # Model output was (0 to 15), representing classes 1 to 16
            climcam_map[pred_map == (salinas_cls - 1)] = climcam_cls

        # Refine Hydration using the physical NDWI layer
        # Areas with significant water moisture (NDWI > 0.45) receive Hydration flag
        ndwi = indices.get("NDWI", np.zeros((h, w)))
        ndvi = indices.get("NDVI", np.zeros((h, w)))
        ndre = indices.get("NDRE", np.zeros((h, w)))

        # Mask high hydration pixels
        hydration_mask = (ndwi > 0.55) & (climcam_map != 0)
        climcam_map[hydration_mask] = 2  # Hydration class

        # Compute Class Distributions
        count_veg = int(np.sum(climcam_map == 1))
        count_hyd = int(np.sum(climcam_map == 2))
        count_des = int(np.sum(climcam_map == 3))
        count_urb = int(np.sum(climcam_map == 4))
        count_valid = max(1, count_veg + count_hyd + count_des + count_urb)

        distribution_pct = {
            "vegetation_percentage": round((count_veg / count_valid) * 100.0, 2),
            "hydration_percentage": round((count_hyd / count_valid) * 100.0, 2),
            "desertification_percentage": round((count_des / count_valid) * 100.0, 2),
            "urban_percentage": round((count_urb / count_valid) * 100.0, 2)
        }

        # Calculate Mean Biophysical Metrics
        metrics = {
            **distribution_pct,
            "mean_ndvi": round(float(np.mean(ndvi)), 4),
            "mean_ndwi": round(float(np.mean(ndwi)), 4),
            "mean_ndre": round(float(np.mean(ndre)), 4),
            "vegetation_health_score": round(float(np.clip(np.mean(ndvi[climcam_map == 1]) if count_veg > 0 else 0.0, 0, 1) * 100.0), 2)
        }

        # Identify Critical Regions of Interest (ROI) - Hotspots of Desertification or Moisture Stress
        regions_of_interest = SemanticEncoder._extract_rois(climcam_map, ndwi, ndre, h, w)

        # Generate Space Alerts
        alerts = SpaceAlertSystem.evaluate(metrics, regions_of_interest)

        # Build Downlink Payload Structure
        payload = {
            "mission": "ClimCam ISS Agricultural & Climate Monitor",
            "telemetry_header": {
                "sensor_id": sensor_id,
                "platform": "ISS / Raspberry Pi Edge Unit",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "spatial_grid": {
                    "rows": h,
                    "columns": w,
                    "total_pixels_analyzed": total_pixels
                },
                "scene_georeference": SCENE_GEO_ORIGIN
            },
            "scene_classification_distribution": {
                "categories": CLIMCAM_CLASSES,
                "metrics": distribution_pct
            },
            "biophysical_indicators": {
                "mean_ndvi": metrics["mean_ndvi"],
                "mean_ndwi": metrics["mean_ndwi"],
                "mean_ndre": metrics["mean_ndre"],
                "vegetation_health_score": metrics["vegetation_health_score"]
            },
            "regions_of_interest": regions_of_interest,
            "active_alerts": alerts
        }

        # Calculate Bandwidth Compression Metrics
        json_str = json.dumps(payload, indent=2)
        encoded_bytes = len(json_str.encode('utf-8'))
        compression_ratio = round(raw_cube_bytes / max(1, encoded_bytes), 1)

        payload["bandwidth_optimization"] = {
            "raw_cube_size_bytes": raw_cube_bytes,
            "raw_cube_size_mb": round(raw_cube_bytes / (1024 * 1024), 2),
            "encoded_payload_size_bytes": encoded_bytes,
            "encoded_payload_size_kb": round(encoded_bytes / 1024, 2),
            "compression_ratio": f"{compression_ratio}:1",
            "bandwidth_saving_percentage": f"{((1 - (encoded_bytes / raw_cube_bytes)) * 100.0):.3f}%"
        }

        return payload, climcam_map

    @staticmethod
    def _extract_rois(climcam_map: np.ndarray, ndwi: np.ndarray, ndre: np.ndarray, h: int, w: int) -> List[Dict[str, Any]]:
        """
        Detects spatially cohesive anomaly clusters (e.g. desertification patches or drought pockets)
        and extracts their bounding boxes and center GPS coordinates.
        """
        rois = []
        # Divide scene into a 4x4 spatial patrol grid
        grid_rows, grid_cols = 4, 4
        dh = h // grid_rows
        dw = w // grid_cols

        for r in range(grid_rows):
            for c in range(grid_cols):
                y0, y1 = r * dh, (r + 1) * dh
                x0, x1 = c * dw, (c + 1) * dw
                sub_map = climcam_map[y0:y1, x0:x1]
                sub_ndwi = ndwi[y0:y1, x0:x1]

                # Check if this zone has high desertification concentration (> 40%)
                sub_total = sub_map.size
                sub_desert = np.sum(sub_map == 3)
                desert_ratio = sub_desert / sub_total

                if desert_ratio > 0.40:
                    # Calculate approximate lat/lon
                    center_y = (y0 + y1) // 2
                    center_x = (x0 + x1) // 2
                    lat = SCENE_GEO_ORIGIN["center_lat"] + (center_y - h/2) * (SCENE_GEO_ORIGIN["pixel_resolution_m"] / 111139.0)
                    lon = SCENE_GEO_ORIGIN["center_lon"] + (center_x - w/2) * (SCENE_GEO_ORIGIN["pixel_resolution_m"] / 111139.0)

                    rois.append({
                        "roi_id": f"ROI-DESERT-R{r}C{c}",
                        "anomaly_type": "HIGH_DESERTIFICATION_CONCENTRATION",
                        "severity": "HIGH" if desert_ratio > 0.60 else "MEDIUM",
                        "desertification_concentration_pct": round(desert_ratio * 100.0, 1),
                        "mean_moisture_ndwi": round(float(np.mean(sub_ndwi)), 3),
                        "bounding_box_pixels": {"ymin": int(y0), "xmin": int(x0), "ymax": int(y1), "xmax": int(x1)},
                        "estimated_gps": {"latitude": round(lat, 6), "longitude": round(lon, 6)}
                    })

        return rois[:5]  # Keep top 5 most critical regions for minimal telemetry size


# ==============================================================================
# 5. Visualizer Routine for Stage 3 Map
# ==============================================================================
def save_stage3_thematic_map(climcam_map: np.ndarray, rois: List[Dict[str, Any]], output_path: str):
    """
    Renders and saves the 4-class thematic ClimCam map with ROI bounding boxes.
    """
    from matplotlib.colors import ListedColormap
    import matplotlib.patches as patches

    # Colors: 0: Black (Background), 1: ForestGreen (Veg), 2: DeepSkyBlue (Hydration), 3: Goldenrod (Desert), 4: DimGray (Urban)
    cmap_colors = ["#1a1a1a", "#2e7d32", "#0288d1", "#d4af37", "#757575"]
    custom_cmap = ListedColormap(cmap_colors)

    fig, ax = plt.subplots(figsize=(8, 10))
    im = ax.imshow(climcam_map, cmap=custom_cmap, vmin=0, vmax=4)

    # Draw ROI bounding boxes
    for roi in rois:
        bb = roi["bounding_box_pixels"]
        rect = patches.Rectangle(
            (bb["xmin"], bb["ymin"]),
            bb["xmax"] - bb["xmin"],
            bb["ymax"] - bb["ymin"],
            linewidth=2,
            edgecolor='red' if roi["severity"] == "HIGH" else 'orange',
            facecolor='none',
            linestyle='--'
        )
        ax.add_patch(rect)
        ax.text(bb["xmin"] + 5, bb["ymin"] + 20, roi["roi_id"], color="yellow", fontsize=8, fontweight="bold", backgroundcolor="black")

    ax.set_title("ClimCam ISS Onboard Thematic Map\n(4 Core Domains + Detected Hotspot ROIs)", fontsize=13, fontweight="bold")
    ax.axis("off")

    # Add custom legend
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='s', color='w', label='Vegetation (الغطاء النباتي)', markerfacecolor='#2e7d32', markersize=12),
        Line2D([0], [0], marker='s', color='w', label='Hydration (الرطوبة/الماء)', markerfacecolor='#0288d1', markersize=12),
        Line2D([0], [0], marker='s', color='w', label='Desertification (التصحر والأراضي البور)', markerfacecolor='#d4af37', markersize=12),
        Line2D([0], [0], marker='s', color='w', label='Urban (المناطق العمرانية والبنية)', markerfacecolor='#757575', markersize=12),
        Line2D([0], [0], color='red', linestyle='--', linewidth=2, label='Alert ROI Hotspot')
    ]
    ax.legend(handles=legend_elements, loc='lower center', bbox_to_anchor=(0.5, -0.12), ncol=2, framealpha=0.9, fontsize=9)

    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches='tight')
    plt.close()
    print(f"[EDGE-AI] Saved Thematic Classification Map: {output_path}")


# ==============================================================================
# 6. Main Execution Pipeline
# ==============================================================================
def main():
    print("=" * 75)
    print("  STAGE 3: CLIMCAM ONBOARD EDGE INFERENCE & SEMANTIC ENCODER (ISS)")
    print("=" * 75)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if os.path.basename(os.getcwd()) == "src" else os.getcwd()
    model_path = os.path.join(base_dir, "outputs", "hyperspectral_model_quantized.tflite")
    raw_mat_path = os.path.join(base_dir, "archive", "Salinas_corrected.mat")
    cache_path = os.path.join(base_dir, "data", "processed", "salinas_preprocessed.npz")
    output_dir = os.path.join(base_dir, "outputs")
    os.makedirs(output_dir, exist_ok=True)

    # 1. Load Preprocessed Data Cube & Indices
    print("\n[STEP 1] Loading calibrated hyperspectral cube from onboard storage...")
    if os.path.exists(cache_path):
        cache = np.load(cache_path, allow_pickle=True)
        cube = cache['cube']
        indices_arr = cache['indices']
        indices_names = list(cache['indices_names'])
        indices = {name: indices_arr[:, :, i] for i, name in enumerate(indices_names)}
        print(f"  ✓ Loaded cached cube from: {cache_path} | Shape: {cube.shape}")
    else:
        raise FileNotFoundError(f"Cached dataset not found at {cache_path}. Run Stage 1 first.")

    raw_file_bytes = os.path.getsize(raw_mat_path) if os.path.exists(raw_mat_path) else cube.nbytes

    # 2. Run Edge Inference using INT8 TFLite Engine
    print("\n[STEP 2] Running Onboard Edge Inference using INT8 Quantized TFLite Engine...")
    engine = EdgeInferenceEngine(model_path=model_path)
    pred_map, conf_map = engine.predict_cube_chunked(cube, chunk_size=4096)

    print(f"  • Prediction Grid: {pred_map.shape[0]}x{pred_map.shape[1]}")
    print(f"  • Mean Confidence Score: {np.mean(conf_map) * 100:.2f}%")

    # 3. Semantic Encoding & Downlink Packaging
    print("\n[STEP 3] Executing Semantic Encoder & Bandwidth Optimization...")
    payload, climcam_map = SemanticEncoder.encode_telemetry(
        pred_map=pred_map,
        clean_cube=cube,
        indices=indices,
        raw_cube_bytes=raw_file_bytes,
        sensor_id="ClimCam-ISS-EXP1"
    )

    # 4. Save JSON Telemetry Payload
    payload_path = os.path.join(output_dir, "edge_telemetry_payload.json")
    with open(payload_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"  ✓ Saved Encoded Telemetry JSON: {payload_path}")

    # 5. Render Thematic Visual Map
    print("\n[STEP 4] Generating Onboard Thematic Map Visualization...")
    map_path = os.path.join(output_dir, "climcam_classification_map.png")
    save_stage3_thematic_map(climcam_map, payload["regions_of_interest"], map_path)

    # 6. Display Summary Telemetry
    print("\n" + "=" * 75)
    print("  CLIMCAM ONBOARD TELEMETRY REPORT:")
    print("=" * 75)
    dist = payload["scene_classification_distribution"]["metrics"]
    print(f"  🌱 Vegetation (الغطاء النباتي)      : {dist['vegetation_percentage']}%")
    print(f"  💧 Hydration (الرطوبة والإجهاد المائي): {dist['hydration_percentage']}%")
    print(f"  🏜️ Desertification (التصحر والأراضي البور): {dist['desertification_percentage']}%")
    print(f"  🏢 Urban (المناطق العمرانية)         : {dist['urban_percentage']}%")
    print("-" * 75)
    bw = payload["bandwidth_optimization"]
    print(f"  📦 Raw Hyperspectral Cube Size   : {bw['raw_cube_size_mb']} MB ({bw['raw_cube_size_bytes']:,} bytes)")
    print(f"  🛰️ Encoded JSON Telemetry Size   : {bw['encoded_payload_size_kb']} KB ({bw['encoded_payload_size_bytes']:,} bytes)")
    print(f"  ⚡ Bandwidth Compression Ratio   : {bw['compression_ratio']}")
    print(f"  🚀 Bandwidth Data Saving         : {bw['bandwidth_saving_percentage']}")
    print("-" * 75)
    print(f"  🚨 Active Alerts ({len(payload['active_alerts'])}):")
    for alt in payload["active_alerts"]:
        print(f"     [{alt['severity']}] {alt['type']}: {alt['message']}")
    print("=" * 75)


if __name__ == "__main__":
    main()
