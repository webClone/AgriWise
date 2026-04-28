"""
WaPOR Normalizer.

Parses pre-fetched WaPOR rasters/summaries.
No live API. Alpha-weighted summaries (Revision 2).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np

from layer0.geo_context.schemas import RasterInput, alpha_weighted_mean
from layer0.geo_context.wapor.schemas import WaPORContext


def normalize_wapor_data(
    raw_data: Dict[str, Any],
    plot_size_m: Optional[float] = None,
) -> WaPORContext:
    """Normalize pre-fetched WaPOR data into WaPORContext.

    Expected raw_data keys:
        available: bool
        level: int (1, 2, or 3)
        resolution_m: float
        actual_et: float or RasterInput (mm/10d)
        reference_et: float or RasterInput (mm/10d)
        biomass: float (optional)
        water_productivity: float (optional)
        land_productivity: float (optional)
        precipitation: float (optional)
        land_cover: str (optional)
        crop_calendar: dict (optional)
    """
    if not raw_data.get("available", False):
        reason = raw_data.get("reason", "WAPOR_NOT_AVAILABLE_FOR_REGION")
        return WaPORContext(
            wapor_available=False,
            flags=[reason],
        )

    level = int(raw_data.get("level", 1))
    resolution = float(raw_data.get("resolution_m", 250.0))

    # ET values — support both scalar and raster
    actual_et = _extract_scalar_or_raster_mean(raw_data.get("actual_et"))
    reference_et = _extract_scalar_or_raster_mean(raw_data.get("reference_et"))

    # Filter out nodata sentinel values (-999)
    if actual_et is not None and actual_et < -900:
        actual_et = None
    if reference_et is not None and reference_et < -900:
        reference_et = None

    # ET ratio
    et_ratio = None
    if actual_et is not None and reference_et is not None and reference_et > 0:
        et_ratio = round(actual_et / reference_et, 4)

    # Productivity scores
    biomass = raw_data.get("biomass")
    water_prod = raw_data.get("water_productivity")
    land_prod = raw_data.get("land_productivity")

    # Resolution adequacy (Revision 8)
    adequate = True
    flags = []
    if plot_size_m is not None and resolution > plot_size_m:
        adequate = False
        flags.append("WAPOR_RESOLUTION_COARSER_THAN_PLOT")

    # Confidence by level (Revision 8)
    confidence = _compute_wapor_confidence(level, resolution, plot_size_m, adequate)

    if level == 1:
        flags.append("WAPOR_LEVEL1_REGIONAL_CONTEXT_ONLY")

    return WaPORContext(
        wapor_available=True,
        wapor_level=level,
        wapor_resolution_m=resolution,
        actual_et_10d=round(actual_et, 4) if actual_et is not None else None,
        reference_et_10d=round(reference_et, 4) if reference_et is not None else None,
        et_ratio=et_ratio,
        biomass_trend=biomass,
        water_productivity_score=water_prod,
        land_productivity_score=land_prod,
        irrigation_performance_proxy=_compute_irrigation_proxy(et_ratio),
        wapor_confidence=round(confidence, 4),
        resolution_adequate_for_plot=adequate,
        flags=flags,
    )


def _extract_scalar_or_raster_mean(value: Any) -> Optional[float]:
    """Extract a scalar value or compute alpha-weighted mean from a RasterInput."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, RasterInput):
        return alpha_weighted_mean(value.data, value.valid_mask, value.alpha_mask)
    if isinstance(value, dict):
        return float(value.get("value", 0))
    return None


def _compute_wapor_confidence(
    level: int, resolution: float,
    plot_size_m: Optional[float], adequate: bool,
) -> float:
    """Compute WaPOR confidence based on level and resolution adequacy.

    Revision 8:
        Level 3 = strongest (up to 0.9)
        Level 2 = moderate  (up to 0.7)
        Level 1 = regional  (up to 0.4)
    """
    base = {1: 0.4, 2: 0.7, 3: 0.9}.get(level, 0.3)
    if not adequate:
        base *= 0.5
    return min(base, 1.0)


def _compute_irrigation_proxy(et_ratio: Optional[float]) -> Optional[float]:
    """Irrigation performance proxy from ET ratio.

    ET ratio near 1.0 = good irrigation performance.
    ET ratio << 1.0 = possible under-irrigation.
    ET ratio >> 1.0 = possible data issue or extreme conditions.
    """
    if et_ratio is None:
        return None
    if et_ratio > 1.2:
        return 0.5  # suspicious
    return round(min(et_ratio, 1.0), 4)
