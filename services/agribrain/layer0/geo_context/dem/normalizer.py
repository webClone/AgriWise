"""
DEM Normalizer.

Validates raster alignment, computes valid mask statistics,
and prepares DEM data for terrain feature extraction.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np

from layer0.geo_context.schemas import RasterInput


def normalize_dem_raster(
    raw_data: Dict[str, Any],
) -> RasterInput:
    """Normalize pre-fetched DEM raster into a validated RasterInput.

    Expected raw_data keys:
        elevation_m: 2D list or ndarray
        valid_mask: 2D list or ndarray (bool)
        resolution_m: float
        crs: str (optional, default EPSG:4326)
        alpha_mask: 2D list or ndarray (optional)
        raster_ref: str (optional)
        content_hash: str (optional)

    Raises ValueError on contract violations (shape mismatch, etc).
    """
    elevation = np.asarray(raw_data["elevation_m"], dtype=np.float64)
    valid = np.asarray(raw_data["valid_mask"], dtype=bool)
    resolution = float(raw_data["resolution_m"])
    crs = raw_data.get("crs", "EPSG:4326")

    alpha = None
    if "alpha_mask" in raw_data and raw_data["alpha_mask"] is not None:
        alpha = np.asarray(raw_data["alpha_mask"], dtype=np.float64)

    # Replace NaN/inf in elevation with masked values
    nan_mask = ~np.isfinite(elevation)
    if nan_mask.any():
        valid = valid & ~nan_mask
        elevation = np.where(nan_mask, 0.0, elevation)

    return RasterInput(
        data=elevation,
        valid_mask=valid,
        resolution_m=resolution,
        crs=crs,
        aligned_to_plot_grid=True,
        alpha_mask=alpha,
        raster_ref=raw_data.get("raster_ref"),
        content_hash=raw_data.get("content_hash"),
    )
