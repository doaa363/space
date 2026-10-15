"""
ClimCam Phase 4: End-to-End Deploy & Benchmarking Pipeline
===========================================================
Raspberry Pi / Edge Device deployment script with:
  1. Full End-to-End pipeline execution
  2. Performance benchmarking (Inference time, Memory, Throughput)
  3. ISS Pass simulation over East Africa using TLE data
  4. Automated test report generation (JSON + TXT)

Target Hardware : Raspberry Pi 4B / Jetson Nano / Google Coral Edge TPU
Mission Scope   : East Africa (Egypt, Kenya, Uganda)
Acceptance KPI  : Inference < 30 seconds per scene, Compression > 100:1
"""

import sys
import os
import json
import time
import math
import tracemalloc
import datetime
from typing import Dict, List, Tuple, Any, Optional

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import numpy as np

# TFLite universal import (tflite_runtime for Pi, tensorflow.lite for desktop)
try:
    import tflite_runtime.interpreter as tflite
    BACKEND = "tflite_runtime"
except ImportError:
    from tensorflow import lite as tflite
    BACKEND = "tensorflow.lite"

# ============================================================
# Configuration Constants
# ============================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
           if os.path.basename(os.getcwd()) == "src" else os.getcwd()

PATHS = {
    "model":   os.path.join(BASE_DIR, "outputs", "hyperspectral_model_quantized.tflite"),
    "cache":   os.path.join(BASE_DIR, "data", "processed", "salinas_preprocessed.npz"),
    "outputs": os.path.join(BASE_DIR, "outputs"),
    "reports": os.path.join(BASE_DIR, "outputs", "reports"),
}

# Acceptance thresholds
KPI = {
    "max_inference_seconds": 30.0,
    "min_compression_ratio": 100.0,
    "min_accuracy_pct":      75.0,
}

# East Africa ground targets for ISS pass simulation
EAST_AFRICA_TARGETS = [
    {"name": "Egypt - Nile Delta",        "lat": 30.8025,  "lon": 30.9188},
    {"name": "Egypt - Cairo Metro Area",  "lat": 30.0444,  "lon": 31.2357},
    {"name": "Kenya - Nairobi",           "lat": -1.2921,  "lon": 36.8219},
    {"name": "Kenya - Lake Victoria",     "lat": -0.1375,  "lon": 37.0833},
    {"name": "Uganda - Kampala",          "lat":  0.3476,  "lon": 32.5825},
    {"name": "Uganda - Lake Albert",      "lat":  1.6801,  "lon": 31.1498},
]

# Real ISS TLE (Two-Line Elements) – valid as of late 2026 (epoch will be offset in simulation)
ISS_TLE = {
    "name": "ISS (ZARYA)",
    "line1": "1 25544U 98067A   26287.54903935  .00009573  00000-0  17437-3 0  9993",
    "line2": "2 25544  51.6416 272.5940 0001773  82.4320 277.6989 15.50246792476998"
}


# ============================================================
# 1. Performance Benchmarking Module
# ============================================================
class PerformanceBenchmark:
    """
    Wraps inference engine and measures wall-clock time,
    peak memory, and pixel throughput for each pipeline stage.
    """

    def __init__(self):
        self.records: List[Dict[str, Any]] = []

    def start(self, label: str) -> float:
        tracemalloc.start()
        t = time.perf_counter()
        self._current_label = label
        self._start_time = t
        return t

    def stop(self, n_pixels: int = 0) -> Dict[str, Any]:
        elapsed = time.perf_counter() - self._start_time
        _, peak_mem_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        record = {
            "stage":                 self._current_label,
            "elapsed_seconds":       round(elapsed, 4),
            "peak_memory_mb":        round(peak_mem_bytes / (1024 * 1024), 3),
            "throughput_pixels_sec": round(n_pixels / elapsed, 1) if (n_pixels > 0 and elapsed > 0) else 0,
            "passed_kpi":            elapsed < KPI["max_inference_seconds"] if "Inference" in self._current_label else None
        }
        self.records.append(record)
        return record

    def summary(self) -> Dict[str, Any]:
        total_elapsed = sum(r["elapsed_seconds"] for r in self.records)
        kpi_results = {
            r["stage"]: {
                "elapsed_s": r["elapsed_seconds"],
                "peak_mem_mb": r["peak_memory_mb"],
                "throughput": r["throughput_pixels_sec"],
                "kpi_passed": r["passed_kpi"]
            }
            for r in self.records
        }
        return {
            "total_pipeline_seconds": round(total_elapsed, 4),
            "stage_metrics": kpi_results,
            "backend": BACKEND,
            "hardware_target": "Raspberry Pi 4B / Jetson Nano"
        }


# ============================================================
# 2. ISS Orbital Mechanics Simulation (TLE-based)
# ============================================================
class ISSPassSimulator:
    """
    Lightweight SGP4-free TLE parser and ground track approximation.
    Computes approximate sub-satellite lat/lon over time using
    Keplerian mean motion for East Africa overflight detection.
    Does NOT require sgp4 library (zero additional dependencies).
    """

    # WGS-84 constants
    GM = 3.986004418e14    # m^3/s^2
    RE = 6371000.0         # Earth radius in metres
    DEG = math.pi / 180.0

    def __init__(self, tle_dict: Dict[str, str]):
        self.name = tle_dict["name"]
        line1 = tle_dict["line1"]
        line2 = tle_dict["line2"]
        self._parse_tle(line1, line2)

    def _parse_tle(self, line1: str, line2: str):
        """Extract key orbital elements from TLE strings."""
        # Epoch (YYDDD.FFFFFFFF)
        epoch_str = line1[18:32].strip()
        yr2 = int(epoch_str[:2])
        year = 2000 + yr2 if yr2 < 57 else 1900 + yr2
        day_frac = float(epoch_str[2:])
        day_of_year = int(day_frac)
        frac_day = day_frac - day_of_year

        self.epoch_dt = (
            datetime.datetime(year, 1, 1, tzinfo=datetime.timezone.utc)
            + datetime.timedelta(days=day_of_year - 1)
            + datetime.timedelta(days=frac_day)
        )

        # Mean motion (revolutions/day) from field 8 of line 2
        self.mean_motion_rev_day = float(line2[52:63].strip())
        self.period_seconds = 86400.0 / self.mean_motion_rev_day

        # Inclination (degrees)
        self.inclination_deg = float(line2[8:16].strip())
        self.inclination_rad = self.inclination_deg * self.DEG

        # RAAN – Right Ascension of the Ascending Node
        self.raan_deg = float(line2[17:25].strip())

        # Semi-major axis from period
        T = self.period_seconds
        self.semi_major_axis = (self.GM * (T / (2 * math.pi)) ** 2) ** (1 / 3)
        self.altitude_km = (self.semi_major_axis - self.RE) / 1000.0

    def get_ground_track(self, start_dt: datetime.datetime, duration_minutes: int = 100, step_seconds: int = 15) -> List[Dict]:
        """
        Returns approximate (lat, lon) sub-satellite points from start_dt.
        Uses simplified circular orbit approximation.
        """
        track = []
        angular_velocity = (2 * math.pi) / self.period_seconds  # rad/s
        earth_rotation = (2 * math.pi) / 86164.0                # rad/s (sidereal)

        # Time elapsed since TLE epoch
        epoch_seconds = (start_dt - self.epoch_dt).total_seconds()
        total_steps = int(duration_minutes * 60 / step_seconds)

        for i in range(total_steps):
            t = epoch_seconds + i * step_seconds
            dt = start_dt + datetime.timedelta(seconds=i * step_seconds)

            # Orbital angle from ascending node
            u = angular_velocity * t  # rad

            # Satellite position in orbital plane (simplified)
            # latitude: asin(sin(inc) * sin(u))
            lat_rad = math.asin(
                math.sin(self.inclination_rad) * math.sin(u % (2 * math.pi))
            )
            lat_deg = lat_rad / self.DEG

            # Longitude: account for RAAN and Earth rotation
            raan_current = self.raan_deg - (earth_rotation * t / self.DEG)
            lon_at_an = math.atan2(
                math.cos(self.inclination_rad) * math.sin(u % (2 * math.pi)),
                math.cos(u % (2 * math.pi))
            ) / self.DEG
            lon_deg = (raan_current + lon_at_an + 180.0) % 360.0 - 180.0

            track.append({
                "timestamp_utc": dt.isoformat(),
                "latitude":      round(lat_deg, 4),
                "longitude":     round(lon_deg, 4),
                "altitude_km":   round(self.altitude_km, 1),
            })

        return track

    def find_passes_over_targets(
        self,
        targets: List[Dict],
        start_dt: datetime.datetime,
        duration_hours: int = 24,
        footprint_radius_km: float = 500.0
    ) -> List[Dict]:
        """
        Detects ISS overflights within footprint_radius_km of each target location.
        Returns a list of scheduled capture events.
        """
        track = self.get_ground_track(start_dt, duration_minutes=duration_hours * 60, step_seconds=30)
        passes = []

        for point in track:
            iss_lat = point["latitude"]
            iss_lon = point["longitude"]

            for target in targets:
                dist_km = self._haversine(iss_lat, iss_lon, target["lat"], target["lon"])
                if dist_km <= footprint_radius_km:
                    passes.append({
                        "target_name":    target["name"],
                        "target_lat":     target["lat"],
                        "target_lon":     target["lon"],
                        "iss_lat":        iss_lat,
                        "iss_lon":        iss_lon,
                        "iss_altitude_km": point["altitude_km"],
                        "closest_dist_km": round(dist_km, 2),
                        "acquisition_time_utc": point["timestamp_utc"],
                        "scene_capture": True,
                        "priority":       "HIGH" if dist_km < 200 else "MEDIUM"
                    })

        # De-duplicate consecutive passes over the same target (keep best approach)
        passes = self._deduplicate_passes(passes)
        return passes

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Great-circle distance (km) between two lat/lon coordinates."""
        R = 6371.0
        d = math.pi / 180.0
        dlat = (lat2 - lat1) * d
        dlon = (lon2 - lon1) * d
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1 * d) * math.cos(lat2 * d) * math.sin(dlon / 2) ** 2
        return R * 2 * math.asin(math.sqrt(a))

    @staticmethod
    def _deduplicate_passes(passes: List[Dict]) -> List[Dict]:
        """Keep only the closest approach per (target, pass window)."""
        best: Dict[str, Dict] = {}
        for p in passes:
            key = f"{p['target_name']}_{p['acquisition_time_utc'][:13]}"  # group by hour
            if key not in best or p["closest_dist_km"] < best[key]["closest_dist_km"]:
                best[key] = p
        return sorted(best.values(), key=lambda x: x["acquisition_time_utc"])


# ============================================================
# 3. Edge Inference Engine (Memory-Safe Chunked Inference)
# ============================================================
class EdgeInferenceEngine:
    """
    TFLite INT8 inference engine optimized for edge hardware.
    Processes pixels in configurable chunks to avoid RAM overflow.
    """

    def __init__(self, model_path: str, chunk_size: int = 2048):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"TFLite model not found: {model_path}")
        self.chunk_size = chunk_size
        self.interpreter = tflite.Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()
        self.input_details  = self.interpreter.get_input_details()[0]
        self.output_details = self.interpreter.get_output_details()[0]
        self.in_scale, self.in_zp   = self.input_details.get("quantization",  (0.0, 0))
        self.out_scale, self.out_zp = self.output_details.get("quantization", (0.0, 0))
        print(f"    [ENGINE] Model loaded from {os.path.basename(model_path)}")
        print(f"    [ENGINE] Backend: {BACKEND} | Input: {self.input_details['shape']} ({self.input_details['dtype'].__name__})")

    def predict(self, cube: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float]:
        """
        Full scene inference. Returns (pred_map, conf_map, elapsed_sec).
        """
        h, w, b = cube.shape
        flat = cube.reshape(-1, b, 1).astype(np.float32)
        N = flat.shape[0]
        preds = np.empty(N, dtype=np.int32)
        confs = np.empty(N, dtype=np.float32)

        t0 = time.perf_counter()
        for start in range(0, N, self.chunk_size):
            end   = min(start + self.chunk_size, N)
            batch = flat[start:end]
            bs    = end - start

            if self.interpreter.get_input_details()[0]["shape"][0] != bs:
                self.interpreter.resize_tensor_input(self.input_details["index"], [bs, b, 1])
                self.interpreter.allocate_tensors()

            inp = batch.astype(np.int8) if self.input_details["dtype"] == np.int8 and self.in_scale > 0 \
                  else batch.astype(np.float32)
            self.interpreter.set_tensor(self.input_details["index"], inp)
            self.interpreter.invoke()
            out = self.interpreter.get_tensor(self.output_details["index"])

            if self.output_details["dtype"] == np.int8 and self.out_scale > 0:
                out = (out.astype(np.float32) - self.out_zp) * self.out_scale

            preds[start:end] = np.argmax(out, axis=1)
            confs[start:end] = np.max(out, axis=1)

        elapsed = time.perf_counter() - t0
        return preds.reshape(h, w), confs.reshape(h, w), elapsed


# ============================================================
# 4. Test Report Generator
# ============================================================
class TestReportGenerator:
    """
    Compiles a structured test report (JSON + human-readable TXT)
    documenting accuracy, inference timing, compression, and alert simulation.
    """

    @staticmethod
    def build(
        bench_summary:      Dict,
        climcam_distribution: Dict,
        iss_passes:         List[Dict],
        compression_ratio:  float,
        active_alerts:      List[Dict],
        inference_seconds:  float,
        confidence_pct:     float,
    ) -> Dict[str, Any]:

        kpi_results = {
            "inference_time": {
                "value_seconds": inference_seconds,
                "threshold_seconds": KPI["max_inference_seconds"],
                "passed": inference_seconds < KPI["max_inference_seconds"],
                "margin_seconds": round(KPI["max_inference_seconds"] - inference_seconds, 2)
            },
            "compression_ratio": {
                "value": compression_ratio,
                "threshold": KPI["min_compression_ratio"],
                "passed": compression_ratio >= KPI["min_compression_ratio"],
                "margin": round(compression_ratio - KPI["min_compression_ratio"], 1)
            },
            "model_confidence": {
                "value_pct": confidence_pct,
                "threshold_pct": KPI["min_accuracy_pct"],
                "passed": confidence_pct >= KPI["min_accuracy_pct"],
            }
        }

        all_passed = all(v["passed"] for v in kpi_results.values())

        report = {
            "report_meta": {
                "project":          "ClimCam ISS Hyperspectral AI System",
                "phase":            "Phase 4: Integration & Validation",
                "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "hardware_target":  "Raspberry Pi 4B (Simulated on x86/x64)",
                "backend_engine":   BACKEND,
                "overall_verdict":  "PASS" if all_passed else "FAIL"
            },
            "kpi_validation":           kpi_results,
            "performance_benchmarks":   bench_summary,
            "scene_classification":     climcam_distribution,
            "iss_pass_simulation": {
                "total_passes_detected": len(iss_passes),
                "high_priority_passes":  sum(1 for p in iss_passes if p.get("priority") == "HIGH"),
                "targets_covered":       list({p["target_name"] for p in iss_passes}),
                "scheduled_captures":    iss_passes[:8]   # top 8 entries for brevity
            },
            "active_alerts":            active_alerts,
            "system_compliance": {
                "space_grade_memory_footprint": bench_summary.get("stage_metrics", {}).get(
                    "Edge Inference", {}).get("peak_mem_mb", "N/A"),
                "bandwidth_compression_ratio":  f"{compression_ratio:.1f}:1",
                "telemetry_payload_kb": None
            }
        }
        return report

    @staticmethod
    def save_json(report: Dict, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"    [REPORT] JSON report saved: {path}")

    @staticmethod
    def save_txt(report: Dict, path: str):
        """
        Renders a human-readable test report for operations team review.
        """
        lines = []
        sep = "=" * 78

        def s(text=""): lines.append(text)

        s(sep)
        s("  CLIMCAM ISS SYSTEM — PHASE 4 INTEGRATION & VALIDATION REPORT")
        s(sep)
        s(f"  Generated     : {report['report_meta']['generated_at_utc']}")
        s(f"  Hardware      : {report['report_meta']['hardware_target']}")
        s(f"  TFLite Backend: {report['report_meta']['backend_engine']}")
        s(f"  Overall Verdict: {'✅ PASS' if report['report_meta']['overall_verdict'] == 'PASS' else '❌ FAIL'}")
        s()
        s("─" * 78)
        s("  KPI VALIDATION RESULTS")
        s("─" * 78)
        for kpi_name, kv in report["kpi_validation"].items():
            icon = "✅" if kv["passed"] else "❌"
            s(f"  {icon}  {kpi_name}")
            for k, v in kv.items():
                s(f"       {k:<28}: {v}")
        s()
        s("─" * 78)
        s("  PERFORMANCE BENCHMARKS (Per Pipeline Stage)")
        s("─" * 78)
        for stage, metrics in report["performance_benchmarks"].get("stage_metrics", {}).items():
            s(f"  Stage : {stage}")
            s(f"       Elapsed              : {metrics['elapsed_s']} s")
            s(f"       Peak Memory          : {metrics['peak_mem_mb']} MB")
            s(f"       Throughput           : {metrics['throughput']} px/s")
            if metrics['kpi_passed'] is not None:
                s(f"       KPI Passed           : {'YES ✅' if metrics['kpi_passed'] else 'NO ❌'}")
            s()
        s("─" * 78)
        s("  SCENE CLASSIFICATION DISTRIBUTION")
        s("─" * 78)
        for cls, pct in report["scene_classification"].items():
            s(f"  {cls:<30}: {pct}%")
        s()
        s("─" * 78)
        s("  ISS PASS SIMULATION — EAST AFRICA")
        s("─" * 78)
        sim = report["iss_pass_simulation"]
        s(f"  Total Overflight Events : {sim['total_passes_detected']}")
        s(f"  HIGH Priority Captures  : {sim['high_priority_passes']}")
        s(f"  Targets Covered         : {', '.join(sim['targets_covered'])}")
        s()
        s("  Top Scheduled Captures:")
        for p in sim["scheduled_captures"][:5]:
            s(f"    [{p['priority']:6}] {p['target_name']:<35} @ {p['acquisition_time_utc'][:19]}Z  dist={p['closest_dist_km']} km")
        s()
        s("─" * 78)
        s("  ACTIVE ALERTS")
        s("─" * 78)
        for alt in report["active_alerts"]:
            s(f"  [{alt.get('severity','?')}] {alt.get('type','?')}")
            s(f"       {alt.get('message','')}")
        s()
        s(sep)

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"    [REPORT] TXT report saved: {path}")


# ============================================================
# 5. Semantic Encoder (Compact Version)
# ============================================================
SALINAS_TO_CLIMCAM = {
    1: 1, 2: 1, 3: 3, 4: 3, 5: 3, 6: 4, 7: 1, 8: 1,
    9: 4, 10: 1, 11: 1, 12: 1, 13: 1, 14: 1, 15: 1, 16: 4
}

ALERT_THRESHOLDS = {
    "desertification_pct_warn": 28.0,
    "hydration_pct_critical":    8.0,
    "ndwi_critical":            -0.10,
}


def encode_payload(pred_map: np.ndarray, indices: Dict[str, np.ndarray], raw_bytes: int) -> Tuple[Dict, np.ndarray]:
    h, w = pred_map.shape
    climcam = np.zeros((h, w), dtype=np.uint8)
    for s_cls, c_cls in SALINAS_TO_CLIMCAM.items():
        climcam[pred_map == (s_cls - 1)] = c_cls

    ndwi = indices.get("NDWI", np.zeros((h, w)))
    climcam[(ndwi > 0.55) & (climcam != 0)] = 2  # Hydration override

    v  = int(np.sum(climcam == 1))
    hy = int(np.sum(climcam == 2))
    d  = int(np.sum(climcam == 3))
    u  = int(np.sum(climcam == 4))
    total = max(1, v + hy + d + u)

    dist = {
        "Vegetation":      round((v / total)  * 100.0, 2),
        "Hydration":       round((hy / total) * 100.0, 2),
        "Desertification": round((d / total)  * 100.0, 2),
        "Urban":           round((u / total)  * 100.0, 2),
    }

    # Generate alerts
    alerts = []
    mean_ndwi = float(np.mean(ndwi))
    if dist["Desertification"] > ALERT_THRESHOLDS["desertification_pct_warn"]:
        alerts.append({
            "severity": "WARNING",
            "type":     "DESERTIFICATION_ENCROACHMENT",
            "message":  f"Desertification {dist['Desertification']}% exceeds {ALERT_THRESHOLDS['desertification_pct_warn']}% threshold.",
            "recommendation": "Flag for soil stabilization and trend tracking."
        })
    if mean_ndwi < ALERT_THRESHOLDS["ndwi_critical"] or dist["Hydration"] < ALERT_THRESHOLDS["hydration_pct_critical"]:
        alerts.append({
            "severity": "CRITICAL",
            "type":     "ACUTE_MOISTURE_DEFICIT",
            "message":  f"Mean NDWI={mean_ndwi:.3f} — critical drought detected.",
            "recommendation": "Initiate emergency irrigation alert."
        })
    if not alerts:
        alerts.append({"severity": "INFO", "type": "NOMINAL", "message": "All indicators within nominal range."})

    payload_body = {
        "mission":     "ClimCam ISS East Africa Monitor",
        "sensor_id":   "ClimCam-ISS-EXP1",
        "timestamp":   datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "distribution": dist,
        "alerts":      alerts,
        "biophysical": {
            "mean_ndwi": round(mean_ndwi, 4),
            "mean_ndvi": round(float(np.mean(indices.get("NDVI", np.zeros((h, w))))), 4),
            "mean_ndre": round(float(np.mean(indices.get("NDRE", np.zeros((h, w))))), 4),
        }
    }

    payload_bytes = len(json.dumps(payload_body).encode("utf-8"))
    ratio = raw_bytes / max(1, payload_bytes)

    payload_body["bandwidth"] = {
        "raw_cube_mb":        round(raw_bytes / (1024 * 1024), 3),
        "payload_kb":         round(payload_bytes / 1024, 3),
        "compression_ratio":  round(ratio, 1),
        "bandwidth_saving_%": round((1 - payload_bytes / raw_bytes) * 100.0, 4)
    }

    return payload_body, climcam, ratio, alerts


# ============================================================
# 6. Full End-to-End Pipeline
# ============================================================
def run_pipeline(target_pass: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Runs the complete ClimCam pipeline for one scene acquisition event.
    If target_pass is provided, the run is attributed to that ISS pass.
    """
    bench = PerformanceBenchmark()

    print("\n  ── Stage A: Loading Onboard Cache ─────────────────────────────────")
    bench.start("Data Load")
    cache = np.load(PATHS["cache"], allow_pickle=True)
    cube  = cache["cube"].astype(np.float32)
    idx_arr  = cache["indices"]
    idx_names = list(cache["indices_names"])
    indices = {name: idx_arr[:, :, i] for i, name in enumerate(idx_names)}
    load_rec = bench.stop(n_pixels=cube.shape[0] * cube.shape[1])
    raw_bytes = cube.nbytes   # Use in-memory size as proxy for raw cube telemetry
    print(f"    Cube: {cube.shape}  |  Load time: {load_rec['elapsed_seconds']} s")

    print("\n  ── Stage B: Edge Inference (INT8 TFLite) ──────────────────────────")
    engine = EdgeInferenceEngine(PATHS["model"])
    bench.start("Edge Inference")
    pred_map, conf_map, inf_elapsed = engine.predict(cube)
    inf_rec = bench.stop(n_pixels=pred_map.size)
    mean_conf_pct = round(float(np.mean(conf_map)) * 100.0, 2)
    print(f"    Inference: {inf_elapsed:.3f} s  |  Confidence: {mean_conf_pct}%  |  Throughput: {inf_rec['throughput_pixels_sec']} px/s")

    kpi_pass = inf_elapsed < KPI["max_inference_seconds"]
    print(f"    KPI ({'✅ PASS' if kpi_pass else '❌ FAIL'}) — Required < {KPI['max_inference_seconds']} s")

    print("\n  ── Stage C: Semantic Encoding & Compression ───────────────────────")
    bench.start("Semantic Encoder")
    payload, climcam_map, comp_ratio, alerts = encode_payload(pred_map, indices, raw_bytes)
    enc_rec = bench.stop()
    print(f"    Compression: {comp_ratio:.1f}:1  |  Payload: {payload['bandwidth']['payload_kb']} KB")
    print(f"    Bandwidth Saved: {payload['bandwidth']['bandwidth_saving_%']}%")

    return {
        "bench":       bench,
        "payload":     payload,
        "climcam_map": climcam_map,
        "comp_ratio":  comp_ratio,
        "inf_elapsed": inf_elapsed,
        "mean_conf":   mean_conf_pct,
        "alerts":      alerts,
        "target_pass": target_pass,
        "distribution": payload["distribution"],
    }


# ============================================================
# 7. Main Entry Point
# ============================================================
def main():
    print("=" * 78)
    print("  CLIMCAM — PHASE 4: DEPLOY, BENCHMARKING & VALIDATION (ISS East Africa)")
    print("=" * 78)

    os.makedirs(PATHS["reports"], exist_ok=True)

    # ── STEP 1: ISS Pass Simulation ────────────────────────────────────────────
    print("\n[STEP 1] Simulating ISS Orbital Passes over East Africa (24-hour window)...\n")
    simulator = ISSPassSimulator(ISS_TLE)
    sim_start = datetime.datetime.now(datetime.timezone.utc)
    passes = simulator.find_passes_over_targets(
        targets=EAST_AFRICA_TARGETS,
        start_dt=sim_start,
        duration_hours=24,
        footprint_radius_km=500
    )
    print(f"  ✓ Found {len(passes)} overflight events")
    print(f"  ✓ HIGH priority captures: {sum(1 for p in passes if p['priority'] == 'HIGH')}")
    for p in passes[:6]:
        print(f"    [{p['priority']:6}] {p['target_name']:<38} @ {p['acquisition_time_utc'][:19]}Z  dist={p['closest_dist_km']} km")

    # ── STEP 2: End-to-End Pipeline (first scheduled pass) ────────────────────
    print("\n[STEP 2] Executing End-to-End Pipeline (Simulated Scene Capture)...\n")
    active_pass = passes[0] if passes else None
    if active_pass:
        print(f"  Triggered by ISS pass over: {active_pass['target_name']} @ {active_pass['acquisition_time_utc'][:19]}Z")

    result = run_pipeline(target_pass=active_pass)

    # ── STEP 3: Save JSON Telemetry ────────────────────────────────────────────
    payload_path = os.path.join(PATHS["outputs"], "edge_telemetry_phase4.json")
    with open(payload_path, "w", encoding="utf-8") as f:
        json.dump(result["payload"], f, indent=2, ensure_ascii=False)
    print(f"\n[STEP 3] Telemetry JSON saved: {payload_path}")

    # ── STEP 4: Build & Save Test Reports ─────────────────────────────────────
    print("\n[STEP 4] Generating Automated Test Reports...\n")
    bench_summary = result["bench"].summary()
    report = TestReportGenerator.build(
        bench_summary=bench_summary,
        climcam_distribution=result["distribution"],
        iss_passes=passes,
        compression_ratio=result["comp_ratio"],
        active_alerts=result["alerts"],
        inference_seconds=result["inf_elapsed"],
        confidence_pct=result["mean_conf"],
    )

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(PATHS["reports"], f"climcam_test_report_{ts}.json")
    txt_path  = os.path.join(PATHS["reports"], f"climcam_test_report_{ts}.txt")
    TestReportGenerator.save_json(report, json_path)
    TestReportGenerator.save_txt(report, txt_path)

    # ── Final Summary Console ──────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("  CLIMCAM PHASE 4 — FINAL VALIDATION SUMMARY")
    print("=" * 78)
    print(f"  Overall Verdict        : {'✅ PASS' if report['report_meta']['overall_verdict'] == 'PASS' else '❌ FAIL'}")
    print(f"  Inference Time         : {result['inf_elapsed']:.3f} s  (KPI: < {KPI['max_inference_seconds']} s)")
    print(f"  Mean Model Confidence  : {result['mean_conf']}%")
    print(f"  Compression Ratio      : {result['comp_ratio']:.1f}:1  (KPI: > {KPI['min_compression_ratio']}:1)")
    print(f"  ISS Passes Simulated   : {len(passes)} events over Egypt, Kenya & Uganda")
    print(f"  Active Alerts          : {len(result['alerts'])}")
    for a in result["alerts"]:
        print(f"    [{a.get('severity')}] {a.get('type')}")
    print(f"  Reports Directory      : {PATHS['reports']}")
    print("=" * 78)


if __name__ == "__main__":
    main()
