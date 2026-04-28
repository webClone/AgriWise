"""
DEM Quality Assessment.

Evaluates DEM raster quality: coverage, resolution suitability,
pixel count thresholds (Revision 4).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from layer0.geo_context.schemas import RasterInput
from layer0.geo_context.dem.schemas import DEMQAResult, DEMQualityClass, MIN_PIXELS_GOOD, MIN_PIXELS_TERRAIN_DERIVATIVES


def evaluate_dem_qa(
    dem: RasterInput,
    plot_width_m: Optional[float] = None,
) -> DEMQAResult:
    """Evaluate DEM quality for terrain analysis.

    Args:
        dem: Validated DEM raster input.
        plot_width_m: Approximate plot width in meters (for resolution checks).
    """
    total = int(dem.valid_mask.size)
    valid_count = int(dem.valid_mask.sum())
    valid_frac = valid_count / total if total > 0 else 0.0
    nan_frac = 1.0 - valid_frac

    flags: List[str] = []
    quality = DEMQualityClass.GOOD
    terrain_reliable = True
    placement_confidence = 1.0

    # Pixel count thresholds (Revision 4)
    if valid_count < MIN_PIXELS_TERRAIN_DERIVATIVES:
        quality = DEMQualityClass.UNUSABLE
        terrain_reliable = False
        placement_confidence = 0.2
        flags.append("SLOPE_UNCERTAIN_SMALL_PLOT")
        flags.append("LOW_TERRAIN_PIXEL_COUNT")
    elif valid_count < MIN_PIXELS_GOOD:
        quality = DEMQualityClass.DEGRADED
        placement_confidence = 0.5
        flags.append("DEM_TOO_COARSE_FOR_FINE_PLACEMENT")
        flags.append("LOW_TERRAIN_PIXEL_COUNT")

    # Resolution vs plot size (Revision 4)
    if plot_width_m is not None and dem.resolution_m > plot_width_m / 4:
        placement_confidence = min(placement_confidence, 0.4)
        flags.append("DEM_TOO_COARSE_FOR_FINE_PLACEMENT")

    # Coverage
    if valid_frac < 0.5:
        quality = DEMQualityClass.UNUSABLE
        flags.append("DEM_LOW_COVERAGE")
    elif valid_frac < 0.8:
        if quality == DEMQualityClass.GOOD:
            quality = DEMQualityClass.DEGRADED
        flags.append("DEM_PARTIAL_COVERAGE")

    # NaN presence
    if nan_frac > 0:
        flags.append("DEM_HAS_NAN_PIXELS")

    # Flat field detection
    valid_elev = dem.data[dem.valid_mask]
    if valid_elev.size > 0:
        elev_range = float(valid_elev.max() - valid_elev.min())
        if elev_range < 0.5:
            flags.append("DEM_FLAT_FIELD")

    # TWI proxy flag (Revision 3)
    flags.append("TWI_PROXY_NOT_HYDROLOGICAL_MODEL")

    return DEMQAResult(
        quality_class=quality,
        valid_pixel_count=valid_count,
        total_pixel_count=total,
        valid_fraction=round(valid_frac, 4),
        nan_fraction=round(nan_frac, 4),
        resolution_m=dem.resolution_m,
        terrain_derivatives_reliable=terrain_reliable,
        placement_confidence_factor=round(placement_confidence, 4),
        flags=flags,
    )
