"""
Sentinel-2 Index Computation Engine.

Pure-math functions — no API calls, no side effects.
Handles reflectance scale normalization and numerical guards.

V1 indices: NDVI, EVI, NDMI, NDRE, BSI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Tuple

from layer0.sentinel2.schemas import Raster2D

# Minimum denominator to avoid division-by-zero
EPS = 1e-10


class ScaleError(Exception):
    """Raised when byte_0_255 data is not explicitly marked as reflectance-scaled."""
    pass

# Index metadata registry
SUPPORTED_INDICES = {
    "NDVI": {
        "formula": "(B08 - B04) / (B08 + B04)",
        "required_bands": ["B04", "B08"],
        "valid_range": (-1.0, 1.0),
        "description": "Normalized Difference Vegetation Index",
    },
    "EVI": {
        "formula": "2.5 * (B08 - B04) / (B08 + 6*B04 - 7.5*B02 + 1)",
        "required_bands": ["B02", "B04", "B08"],
        "valid_range": (-1.0, 1.5),
        "description": "Enhanced Vegetation Index",
    },
    "NDMI": {
        "formula": "(B08 - B11) / (B08 + B11)",
        "required_bands": ["B08", "B11"],
        "valid_range": (-1.0, 1.0),
        "description": "Normalized Difference Moisture Index",
    },
    "NDRE": {
        "formula": "(B8A - B05) / (B8A + B05)",
        "required_bands": ["B05", "B8A"],
        "valid_range": (-1.0, 1.0),
        "description": "Normalized Difference Red Edge",
    },
    "BSI": {
        "formula": "((B11 + B04) - (B08 + B02)) / ((B11 + B04) + (B08 + B02))",
        "required_bands": ["B02", "B04", "B08", "B11"],
        "valid_range": (-1.0, 1.0),
        "description": "Bare Soil Index",
    },
}


def normalize_reflectance(
    value: float,
    scale: Literal["reflectance_0_1", "scaled_0_10000", "byte_0_255"],
) -> float:
    """Convert any reflectance scale to 0–1 float."""
    if scale == "reflectance_0_1":
        return value
    elif scale == "scaled_0_10000":
        return value / 10000.0
    elif scale == "byte_0_255":
        return value / 255.0
    return value


def _get_band_value(
    bands: Dict[str, float],
    band_name: str,
    scale: str,
) -> Optional[float]:
    """Get normalized reflectance value for a band, or None."""
    val = bands.get(band_name)
    if val is None:
        return None
    return normalize_reflectance(val, scale)


def compute_index(
    name: str,
    bands: Dict[str, float],
    scale: str = "reflectance_0_1",
) -> Optional[float]:
    """
    Compute a single-pixel index value from band values.

    Returns None if:
    - Required bands are missing
    - Denominator is near zero
    - Result is out of valid range

    This function is PURE — no side effects, no diagnostics collection.
    """
    meta = SUPPORTED_INDICES.get(name.upper())
    if meta is None:
        return None

    # Check required bands
    for b in meta["required_bands"]:
        if b not in bands or bands[b] is None:
            return None

    vmin, vmax = meta["valid_range"]

    if name.upper() == "NDVI":
        nir = _get_band_value(bands, "B08", scale)
        red = _get_band_value(bands, "B04", scale)
        if nir is None or red is None:
            return None
        denom = nir + red
        if abs(denom) < EPS:
            return None
        result = (nir - red) / denom

    elif name.upper() == "EVI":
        nir = _get_band_value(bands, "B08", scale)
        red = _get_band_value(bands, "B04", scale)
        blue = _get_band_value(bands, "B02", scale)
        if nir is None or red is None or blue is None:
            return None
        denom = nir + 6.0 * red - 7.5 * blue + 1.0
        if abs(denom) < EPS:
            return None
        result = 2.5 * (nir - red) / denom

    elif name.upper() == "NDMI":
        nir = _get_band_value(bands, "B08", scale)
        swir1 = _get_band_value(bands, "B11", scale)
        if nir is None or swir1 is None:
            return None
        denom = nir + swir1
        if abs(denom) < EPS:
            return None
        result = (nir - swir1) / denom

    elif name.upper() == "NDRE":
        nir_narrow = _get_band_value(bands, "B8A", scale)
        rededge1 = _get_band_value(bands, "B05", scale)
        if nir_narrow is None or rededge1 is None:
            return None
        denom = nir_narrow + rededge1
        if abs(denom) < EPS:
            return None
        result = (nir_narrow - rededge1) / denom

    elif name.upper() == "BSI":
        swir1 = _get_band_value(bands, "B11", scale)
        red = _get_band_value(bands, "B04", scale)
        nir = _get_band_value(bands, "B08", scale)
        blue = _get_band_value(bands, "B02", scale)
        if any(v is None for v in [swir1, red, nir, blue]):
            return None
        num = (swir1 + red) - (nir + blue)
        denom = (swir1 + red) + (nir + blue)
        if abs(denom) < EPS:
            return None
        result = num / denom

    else:
        return None

    # Range guard
    if result < vmin or result > vmax:
        return None

    return result


@dataclass
class RasterComputationDiagnostics:
    """Diagnostics collected during raster-level index computation."""
    total_pixels: int = 0
    valid_input_pixels: int = 0
    valid_output_pixels: int = 0
    invalid_index_counts: Dict[str, int] = field(default_factory=dict)
    out_of_range_counts: Dict[str, int] = field(default_factory=dict)


def compute_index_raster(
    name: str,
    band_rasters: Dict[str, Raster2D],
    valid_mask: Optional[List[List[int]]] = None,
    scale: str = "reflectance_0_1",
) -> Tuple[Raster2D, RasterComputationDiagnostics]:
    """
    Compute an index raster from aligned band rasters.

    Returns (index_raster, diagnostics).
    Diagnostics track invalid/out-of-range pixel counts.

    Raises ScaleError if byte_0_255 bands are not marked as reflectance-scaled.
    """
    meta = SUPPORTED_INDICES.get(name.upper())
    if meta is None:
        raise ValueError(f"Unknown index: {name}")

    # Enforce byte_0_255 restriction: must be explicitly reflectance-scaled
    if scale == "byte_0_255":
        for b in meta["required_bands"]:
            raster = band_rasters.get(b)
            if raster and not getattr(raster, 'is_reflectance_scaled', False):
                raise ScaleError(
                    f"Band '{b}' uses byte_0_255 scale but is not marked as "
                    f"reflectance-scaled (is_reflectance_scaled=False). "
                    f"Scientific indices cannot be computed from visual RGB-rendered bytes."
                )

    # Determine grid shape from first available band
    ref_band = None
    for b in meta["required_bands"]:
        if b in band_rasters:
            ref_band = band_rasters[b]
            break
    if ref_band is None:
        raise ValueError(f"No required bands found for {name}")

    h, w = ref_band.grid_shape
    diag = RasterComputationDiagnostics(total_pixels=h * w)

    out_values: List[List[Optional[float]]] = [[None] * w for _ in range(h)]
    out_valid: List[List[int]] = [[0] * w for _ in range(h)]

    for r in range(h):
        for c in range(w):
            # Skip if external valid_mask says invalid
            if valid_mask and not valid_mask[r][c]:
                continue

            # Gather band values for this pixel
            pixel_bands: Dict[str, float] = {}
            pixel_ok = True
            for b in meta["required_bands"]:
                raster = band_rasters.get(b)
                if raster is None:
                    pixel_ok = False
                    break
                val = raster.values[r][c] if r < len(raster.values) and c < len(raster.values[r]) else None
                if val is None:
                    pixel_ok = False
                    break
                pixel_bands[b] = val

            if not pixel_ok:
                continue

            diag.valid_input_pixels += 1

            result = compute_index(name, pixel_bands, scale)
            if result is not None:
                out_values[r][c] = round(result, 6)
                out_valid[r][c] = 1
                diag.valid_output_pixels += 1
            else:
                diag.out_of_range_counts[name] = diag.out_of_range_counts.get(name, 0) + 1

    result_raster = Raster2D(
        values=out_values,
        valid_mask=out_valid,
        resolution_m=ref_band.resolution_m,
        resampled_from_resolution_m=ref_band.resampled_from_resolution_m,
        resampling_method=ref_band.resampling_method,
        aligned_to_plot_grid=ref_band.aligned_to_plot_grid,
        grid_shape=(h, w),
        crs=ref_band.crs,
        value_scale="reflectance_0_1",  # Indices are always in natural units
    )

    return result_raster, diag
