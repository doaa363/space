"""
Hyperspectral Data Preprocessing Module for Agricultural Disease Detection
===========================================================================
Simulating Satellite / Airborne Edge Preprocessing Pipeline.
Author: Edge AI & Hyperspectral Engineering Specialist
"""

import os
from typing import Dict, Tuple, List, Optional
import numpy as np
import scipy.io as sio
import matplotlib.pyplot as plt


# Standard Salinas AVIRIS Class Names mapping (0 is background/unclassified)
SALINAS_CLASSES: Dict[int, str] = {
    0: "Background",
    1: "Brocoli_green_weeds_1",
    2: "Brocoli_green_weeds_2",
    3: "Fallow",
    4: "Fallow_rough_plow",
    5: "Fallow_smooth",
    6: "Stubble",
    7: "Celery",
    8: "Grapes_untrained",
    9: "Soil_vinyard_develop",
    10: "Corn_senesced_green_weeds",
    11: "Lettuce_romaine_4wk",
    12: "Lettuce_romaine_5wk",
    13: "Lettuce_romaine_6wk",
    14: "Lettuce_romaine_7wk",
    15: "Vinyard_untrained",
    16: "Vinyard_vertical_trellis"
}

# Approximate AVIRIS Key Spectral Bands in 204-band corrected Salinas cube
# Salinas corrected has 204 bands covering ~400 nm to ~2500 nm (water bands removed)
BAND_INDICES = {
    "BLUE": 9,        # ~485 nm (Chlorophyll absorption / carotenoid)
    "GREEN": 18,      # ~560 nm (Chlorophyll reflectance peak)
    "RED": 29,        # ~660 nm (Maximum chlorophyll 'a' absorption)
    "RED_EDGE": 36,   # ~715 nm (Transition zone, prime early disease indicator)
    "NIR": 49,        # ~830 nm (Near-infrared plateau, leaf cellular structure)
    "SWIR1": 125,     # ~1600 nm (Short-wave infrared, canopy moisture)
}


class HyperspectralPreprocessor:
    """
    Handles loading, atmospheric/noise calibration, spectral index generation,
    and preparation of hyperspectral data cubes for lightweight edge AI models.
    """

    def __init__(self, data_path: str, gt_path: str):
        """
        Initialize the preprocessor with paths to .mat dataset files.
        
        Args:
            data_path: Path to Salinas_corrected.mat
            gt_path: Path to Salinas_gt.mat
        """
        self.data_path = data_path
        self.gt_path = gt_path
        self.raw_cube: Optional[np.ndarray] = None
        self.ground_truth: Optional[np.ndarray] = None
        self.clean_cube: Optional[np.ndarray] = None
        self.indices: Dict[str, np.ndarray] = {}
        self.metadata: Dict[str, any] = {}

    def load_mat_dataset(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Loads the .mat files using scipy.io, auto-detects array keys, and extracts cubes.
        
        Returns:
            Tuple of (raw_cube, ground_truth) as numpy arrays.
        """
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"Data file not found: {self.data_path}")
        if not os.path.exists(self.gt_path):
            raise FileNotFoundError(f"Ground truth file not found: {self.gt_path}")

        # Load MATLAB .mat structures
        mat_data = sio.loadmat(self.data_path)
        mat_gt = sio.loadmat(self.gt_path)

        # Extract primary data array keys (ignoring '__header__', '__version__', '__globals__')
        data_keys = [k for k in mat_data.keys() if not k.startswith("__")]
        gt_keys = [k for k in mat_gt.keys() if not k.startswith("__")]

        if not data_keys or not gt_keys:
            raise KeyError("Failed to locate valid array keys in the .mat files.")

        cube_key = data_keys[0]
        gt_key = gt_keys[0]

        # Convert to float32 for high-precision vectorization and ML compatibility
        self.raw_cube = mat_data[cube_key].astype(np.float32)
        self.ground_truth = mat_gt[gt_key].astype(np.int32)

        # Store metadata
        h, w, b = self.raw_cube.shape
        self.metadata = {
            "cube_key": cube_key,
            "gt_key": gt_key,
            "height": h,
            "width": w,
            "bands_count": b,
            "data_dtype": str(self.raw_cube.dtype),
            "raw_min": float(self.raw_cube.min()),
            "raw_max": float(self.raw_cube.max()),
            "classes_count": len(np.unique(self.ground_truth)) - 1,  # excluding 0 (background)
        }

        print(f"[INFO] Loaded '{cube_key}' -> Shape: {self.raw_cube.shape} | Bands: {b}")
        print(f"[INFO] Loaded '{gt_key}' -> Shape: {self.ground_truth.shape} | Classes: {self.metadata['classes_count']}")
        return self.raw_cube, self.ground_truth

    def clean_and_normalize(self, clip_negative: bool = True, method: str = "minmax") -> np.ndarray:
        """
        Cleans sensor artifacts (negative values, atmospheric dead bands)
        and normalizes the spectral cube for stable neural network training and INT8 quantization.
        
        Args:
            clip_negative: Whether to clip values below 0 caused by calibration noise.
            method: 'minmax' (scales to [0, 1]) or 'standard' (zero-mean unit-variance).
        
        Returns:
            Normalized spectral cube of shape (Height, Width, Bands).
        """
        if self.raw_cube is None:
            raise ValueError("Data not loaded. Call load_mat_dataset() first.")

        cleaned = np.copy(self.raw_cube)

        # 1. Filter negative calibration noise common in AVIRIS radiance retrieval
        if clip_negative:
            cleaned = np.clip(cleaned, a_min=0.0, a_max=None)

        # 2. Normalization strategy
        if method == "minmax":
            c_min = cleaned.min()
            c_max = cleaned.max()
            eps = 1e-8
            self.clean_cube = (cleaned - c_min) / (c_max - c_min + eps)
            self.metadata["norm_method"] = "minmax"
            self.metadata["norm_scale_min"] = float(c_min)
            self.metadata["norm_scale_max"] = float(c_max)
        elif method == "standard":
            mean = np.mean(cleaned, axis=(0, 1), keepdims=True)
            std = np.std(cleaned, axis=(0, 1), keepdims=True) + 1e-8
            self.clean_cube = (cleaned - mean) / std
            self.metadata["norm_method"] = "standard"
        else:
            raise ValueError(f"Unknown normalization method: {method}")

        print(f"[INFO] Cleaned and normalized cube via '{method}': Min={self.clean_cube.min():.4f}, Max={self.clean_cube.max():.4f}")
        return self.clean_cube

    def compute_vegetation_indices(self) -> Dict[str, np.ndarray]:
        """
        Generates standard and advanced biophysical vegetation indices:
        - NDVI: Normalized Difference Vegetation Index (General vigor & biomass)
        - GNDVI: Green NDVI (Canopy chlorophyll concentration)
        - NDRE: Normalized Difference Red Edge (Sensitive early disease/chlorosis detection)
        - NDWI: Normalized Difference Water Index (Canopy water content / drought stress)
        - SAVI: Soil Adjusted Vegetation Index (Corrects for exposed soil background)
        
        Returns:
            Dictionary containing 2D spatial maps of each index.
        """
        if self.clean_cube is None:
            raise ValueError("Data must be cleaned before computing indices.")

        # Extract key bands
        b_blue = self.clean_cube[:, :, BAND_INDICES["BLUE"]]
        b_green = self.clean_cube[:, :, BAND_INDICES["GREEN"]]
        b_red = self.clean_cube[:, :, BAND_INDICES["RED"]]
        b_red_edge = self.clean_cube[:, :, BAND_INDICES["RED_EDGE"]]
        b_nir = self.clean_cube[:, :, BAND_INDICES["NIR"]]
        b_swir = self.clean_cube[:, :, BAND_INDICES["SWIR1"]]

        eps = 1e-8

        # 1. NDVI = (NIR - Red) / (NIR + Red)
        ndvi = (b_nir - b_red) / (b_nir + b_red + eps)
        ndvi = np.clip(ndvi, -1.0, 1.0)

        # 2. GNDVI = (NIR - Green) / (NIR + Green)
        gndvi = (b_nir - b_green) / (b_nir + b_green + eps)
        gndvi = np.clip(gndvi, -1.0, 1.0)

        # 3. NDRE = (NIR - Red Edge) / (NIR + Red Edge)
        # Critical for early plant pathology (detects disease before leaf necrosis)
        ndre = (b_nir - b_red_edge) / (b_nir + b_red_edge + eps)
        ndre = np.clip(ndre, -1.0, 1.0)

        # 4. NDWI = (NIR - SWIR) / (NIR + SWIR)
        # Reflects plant water stress caused by root or vascular diseases
        ndwi = (b_nir - b_swir) / (b_nir + b_swir + eps)
        ndwi = np.clip(ndwi, -1.0, 1.0)

        # 5. SAVI = ((NIR - Red) / (NIR + Red + L)) * (1 + L) with L=0.5
        L = 0.5
        savi = ((b_nir - b_red) / (b_nir + b_red + L)) * (1.0 + L)
        savi = np.clip(savi, -1.0, 1.5)

        self.indices = {
            "NDVI": ndvi,
            "GNDVI": gndvi,
            "NDRE": ndre,
            "NDWI": ndwi,
            "SAVI": savi,
        }

        print("[INFO] Computed 5 key Agricultural Vegetation Indices: NDVI, GNDVI, NDRE, NDWI, SAVI")
        return self.indices

    def generate_rgb_composite(self) -> np.ndarray:
        """
        Generates a natural-color True RGB composite image from hyperspectral bands.
        """
        if self.clean_cube is None:
            raise ValueError("Cube not loaded or normalized.")

        r = self.clean_cube[:, :, BAND_INDICES["RED"]]
        g = self.clean_cube[:, :, BAND_INDICES["GREEN"]]
        b = self.clean_cube[:, :, BAND_INDICES["BLUE"]]

        rgb = np.stack([r, g, b], axis=-1)
        # Stretch contrast for visualization
        p2, p98 = np.percentile(rgb, (2, 98))
        rgb_stretched = np.clip((rgb - p2) / (p98 - p2 + 1e-8), 0.0, 1.0)
        return rgb_stretched

    def generate_cir_composite(self) -> np.ndarray:
        """
        Generates Color Infrared (CIR / False Color: NIR, Red, Green) composite.
        Standard in remote sensing: healthy vegetation appears bright red.
        """
        if self.clean_cube is None:
            raise ValueError("Cube not loaded or normalized.")

        nir = self.clean_cube[:, :, BAND_INDICES["NIR"]]
        r = self.clean_cube[:, :, BAND_INDICES["RED"]]
        g = self.clean_cube[:, :, BAND_INDICES["GREEN"]]

        cir = np.stack([nir, r, g], axis=-1)
        p2, p98 = np.percentile(cir, (2, 98))
        cir_stretched = np.clip((cir - p2) / (p98 - p2 + 1e-8), 0.0, 1.0)
        return cir_stretched

    def compute_spectral_signatures(self) -> Dict[int, Dict[str, np.ndarray]]:
        """
        Computes mean and standard deviation spectral signatures for each class in the dataset.
        Essential for understanding spectral separability between healthy crops and infected/fallow fields.
        """
        if self.clean_cube is None or self.ground_truth is None:
            raise ValueError("Clean cube and ground truth must be available.")

        signatures = {}
        h, w, bands = self.clean_cube.shape

        for class_id in range(1, 17):
            mask = (self.ground_truth == class_id)
            pixel_count = np.sum(mask)
            if pixel_count == 0:
                continue

            pixels = self.clean_cube[mask]  # Shape: (N, bands)
            signatures[class_id] = {
                "name": SALINAS_CLASSES.get(class_id, f"Class {class_id}"),
                "mean": np.mean(pixels, axis=0),
                "std": np.std(pixels, axis=0),
                "count": int(pixel_count)
            }

        return signatures

    def save_preprocessed_cache(self, output_path: str) -> None:
        """
        Saves preprocessed cube, ground truth, and indices into a compressed .npz archive
        to ensure rapid loading during model training and edge deployment.
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        # Stack indices into an array (Height, Width, num_indices)
        indices_stack = np.stack(list(self.indices.values()), axis=-1)
        indices_names = list(self.indices.keys())

        np.savez_compressed(
            output_path,
            cube=self.clean_cube.astype(np.float32),
            ground_truth=self.ground_truth,
            indices=indices_stack.astype(np.float32),
            indices_names=indices_names,
            classes=list(SALINAS_CLASSES.values())
        )
        print(f"[INFO] Successfully cached preprocessed dataset to: {output_path}")
