"""
WaPOR Indicators.

Computes derived water-productivity indicators from WaPOR context.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from layer0.geo_context.wapor.schemas import WaPORContext


def compute_wapor_indicators(
    wapor: WaPORContext,
) -> Dict[str, Any]:
    """Compute derived indicators from WaPOR context.

    Returns dict with:
        et_ratio, water_productivity_class, irrigation_assessment,
        biomass_status, validation_context
    """
    indicators: Dict[str, Any] = {}

    if not wapor.wapor_available:
        return {"available": False}

    # ET ratio classification
    if wapor.et_ratio is not None:
        if wapor.et_ratio >= 0.9:
            indicators["et_status"] = "well_watered"
        elif wapor.et_ratio >= 0.7:
            indicators["et_status"] = "moderate_stress"
        elif wapor.et_ratio >= 0.5:
            indicators["et_status"] = "significant_stress"
        else:
            indicators["et_status"] = "severe_stress"
        indicators["et_ratio"] = wapor.et_ratio

    # Water productivity classification
    if wapor.water_productivity_score is not None:
        wp = wapor.water_productivity_score
        if wp >= 1.5:
            indicators["water_productivity_class"] = "high"
        elif wp >= 0.8:
            indicators["water_productivity_class"] = "moderate"
        else:
            indicators["water_productivity_class"] = "low"
        indicators["water_productivity_score"] = wp

    # Irrigation performance assessment
    if wapor.irrigation_performance_proxy is not None:
        ip = wapor.irrigation_performance_proxy
        if ip >= 0.85:
            indicators["irrigation_assessment"] = "good"
        elif ip >= 0.6:
            indicators["irrigation_assessment"] = "moderate"
        else:
            indicators["irrigation_assessment"] = "poor"
        indicators["irrigation_performance_proxy"] = ip

    # Biomass trend
    if wapor.biomass_trend is not None:
        indicators["biomass_trend"] = wapor.biomass_trend
        if wapor.biomass_trend > 0:
            indicators["biomass_status"] = "increasing"
        elif wapor.biomass_trend < 0:
            indicators["biomass_status"] = "decreasing"
        else:
            indicators["biomass_status"] = "stable"

    # Validation context for cross-checking
    indicators["validation_context"] = {
        "level": wapor.wapor_level,
        "resolution_m": wapor.wapor_resolution_m,
        "confidence": wapor.wapor_confidence,
        "resolution_adequate": wapor.resolution_adequate_for_plot,
    }

    return indicators
