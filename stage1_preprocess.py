"""
Execution Script: Stage 1 - Hyperspectral Data Exploration & Preprocessing
===========================================================================
Simulates satellite onboard hyperspectral calibration and feature generation.
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from src.preprocessing import HyperspectralPreprocessor, SALINAS_CLASSES


def main():
    print("=" * 70)
    print("  STAGE 1: HYPERSPECTRAL PREPROCESSING & VEGETATION INDICES EXTRACTION")
    print("=" * 70)

    # File paths
    data_path = os.path.join("archive", "Salinas_corrected.mat")
    gt_path = os.path.join("archive", "Salinas_gt.mat")
    output_dir = "outputs"
    cache_dir = os.path.join("data", "processed")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(cache_dir, exist_ok=True)

    # 1. Initialize preprocessor and load dataset
    preprocessor = HyperspectralPreprocessor(data_path=data_path, gt_path=gt_path)
    raw_cube, ground_truth = preprocessor.load_mat_dataset()

    print("\n[STEP 1] Exploring Cube Dimensions & Structure:")
    print(f"  • Spatial Dimensions : {raw_cube.shape[0]} rows x {raw_cube.shape[1]} columns")
    print(f"  • Spectral Channels  : {raw_cube.shape[2]} contiguous bands")
    print(f"  • Total Pixels       : {raw_cube.shape[0] * raw_cube.shape[1]:,} pixels")
    print(f"  • Raw Value Range    : Min={raw_cube.min():.2f}, Max={raw_cube.max():.2f}")

    # 2. Clean and Normalize
    print("\n[STEP 2] Cleaning & Normalization (Simulating Satellite Edge Preprocessing):")
    clean_cube = preprocessor.clean_and_normalize(clip_negative=True, method="minmax")
    print(f"  • Normalized Range   : [{clean_cube.min():.4f}, {clean_cube.max():.4f}]")

    # 3. Compute Vegetation Indices
    print("\n[STEP 3] Generating Agricultural Biophysical Indices:")
    indices = preprocessor.compute_vegetation_indices()
    for name, arr in indices.items():
        print(f"  • {name:<6} -> Min: {arr.min():.3f}, Max: {arr.max():.3f}, Mean: {arr.mean():.3f}")

    # 4. Generate Visualizations
    print("\n[STEP 4] Generating Remote Sensing Visualizations...")

    # Visualization A: True Color vs Color-Infrared (CIR)
    rgb = preprocessor.generate_rgb_composite()
    cir = preprocessor.generate_cir_composite()

    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    axes[0].imshow(rgb)
    axes[0].set_title("Natural RGB Composite\n(Bands: Red=29, Green=18, Blue=9)", fontsize=11)
    axes[0].axis("off")

    axes[1].imshow(cir)
    axes[1].set_title("Color-Infrared (CIR / False Color)\n(Bands: NIR=49, Red=29, Green=18)", fontsize=11)
    axes[1].axis("off")
    plt.tight_layout()
    fig_path_rgb_cir = os.path.join(output_dir, "composite_rgb_and_cir.png")
    plt.savefig(fig_path_rgb_cir, dpi=200)
    plt.close()
    print(f"  ✓ Saved: {fig_path_rgb_cir}")

    # Visualization B: Vegetation Indices Grid
    fig, axes = plt.subplots(1, 4, figsize=(18, 5))
    cmaps = ["YlGn", "summer", "RdYlGn", "Blues"]
    names = ["NDVI", "GNDVI", "NDRE", "NDWI"]

    for ax, name, cmap in zip(axes, names, cmaps):
        im = ax.imshow(indices[name], cmap=cmap, vmin=-0.2, vmax=1.0 if name != "NDWI" else 0.8)
        ax.set_title(f"{name} Index Map", fontsize=12, fontweight="bold")
        ax.axis("off")
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    plt.tight_layout()
    fig_path_indices = os.path.join(output_dir, "vegetation_indices_grid.png")
    plt.savefig(fig_path_indices, dpi=200)
    plt.close()
    print(f"  ✓ Saved: {fig_path_indices}")

    # Visualization C: Ground Truth Classification Map
    plt.figure(figsize=(8, 8))
    cmap_gt = plt.colormaps["tab20"].resampled(17)
    im = plt.imshow(ground_truth, cmap=cmap_gt)
    plt.title("Salinas Ground Truth Field Classes", fontsize=14, fontweight="bold")
    plt.axis("off")
    cbar = plt.colorbar(im, ticks=range(17), fraction=0.046, pad=0.04)
    cbar.ax.set_yticklabels([f"{k}: {v[:14]}" for k, v in SALINAS_CLASSES.items()], fontsize=8)
    fig_path_gt = os.path.join(output_dir, "ground_truth_map.png")
    plt.savefig(fig_path_gt, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  ✓ Saved: {fig_path_gt}")

    # Visualization D: Spectral Signatures (Crop & Disease Profiles)
    signatures = preprocessor.compute_spectral_signatures()
    plt.figure(figsize=(14, 6))
    
    # Plot key representative crops and fallow fields
    selected_classes = [1, 3, 7, 8, 10, 11, 15]  # Broccoli, Fallow, Celery, Grapes, Corn, Lettuce, Vinyard
    colors = plt.cm.tab10(np.linspace(0, 1, len(selected_classes)))

    bands_x = np.arange(clean_cube.shape[2])
    for cls_id, col in zip(selected_classes, colors):
        sig = signatures[cls_id]
        plt.plot(bands_x, sig["mean"], label=f"{sig['name']} (n={sig['count']})", color=col, linewidth=2)
        plt.fill_between(bands_x, sig["mean"] - sig["std"], sig["mean"] + sig["std"], color=col, alpha=0.15)

    plt.title("Hyperspectral Signatures Across 204 Spectral Bands\n(Mean Reflectance ± 1 Std)", fontsize=13, fontweight="bold")
    plt.xlabel("Spectral Band Index (AVIRIS ~400 nm - 2500 nm)", fontsize=11)
    plt.ylabel("Normalized Reflectance", fontsize=11)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(loc="upper right", fontsize=9, framealpha=0.9)
    plt.tight_layout()
    fig_path_signatures = os.path.join(output_dir, "spectral_signatures.png")
    plt.savefig(fig_path_signatures, dpi=200)
    plt.close()
    print(f"  ✓ Saved: {fig_path_signatures}")

    # 5. Save Preprocessed Artifacts for Stage 2
    cache_file = os.path.join(cache_dir, "salinas_preprocessed.npz")
    preprocessor.save_preprocessed_cache(cache_file)

    print("\n" + "=" * 70)
    print("  STAGE 1 COMPLETED SUCCESSFULLY!")
    print(f"  • Preprocessed cache stored at: {cache_file}")
    print(f"  • Visualizations saved in: {output_dir}/")
    print("=" * 70)


if __name__ == "__main__":
    main()
