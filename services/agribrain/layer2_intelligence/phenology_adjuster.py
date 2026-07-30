"""
Layer 2 Intelligence — Phenology Adjuster.

Uses CropCycleContext + GDD to contextualize stress severity.
Phenology-sensitive adjustments:
  - Flowering/reproductive stage → water stress sensitivity ×1.3
  - Senescence → NDVI decline expected, stress severity ×0.6
  - Emergence → thermal stress sensitivity ×1.2

Also computes phenology-adjusted vegetation indices:
  - gdd_adjusted_vigor: NDVI normalized by expected value at current GDD
  - deviation_from_expected: how far current NDVI is from stage expectation
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .schemas import (
    PhenologyFeature,
    StressEvidence,
    CropCycleContext,
)


# Expected NDVI by crop stage (generic crop model)
_STAGE_EXPECTED_NDVI = {
    "bare_soil": 0.12,
    "emergence": 0.25,
    "vegetative": 0.55,
    "reproductive": 0.65,
    "senescence": 0.35,
    "harvested": 0.15,
    "unknown": 0.40,
}

# Stage → stress sensitivity multipliers
_WATER_SENSITIVITY = {
    "bare_soil": 0.5,
    "emergence": 1.0,
    "vegetative": 1.0,
    "reproductive": 1.3,   # flowering most sensitive
    "senescence": 0.6,
    "harvested": 0.3,
    "unknown": 1.0,
}

_THERMAL_SENSITIVITY = {
    "bare_soil": 0.4,
    "emergence": 1.2,
    "vegetative": 1.0,
    "reproductive": 1.1,
    "senescence": 0.7,
    "harvested": 0.3,
    "unknown": 1.0,
}

# v3.2: Stage-aware sensitivity multipliers for all stress types
# Based on Hsiao (2009) "Plant responses to water deficit", and
# Farooq et al. (2009) "Plant drought stress: effects, mechanisms"
_NUTRIENT_SENSITIVITY = {
    "bare_soil": 0.3,
    "emergence": 0.8,
    "vegetative": 1.2,        # High N demand during rapid growth
    "reproductive": 1.0,
    "senescence": 0.4,
    "harvested": 0.2,
    "unknown": 1.0,
}

_SALINITY_SENSITIVITY = {
    "bare_soil": 0.3,
    "emergence": 1.3,         # Seedlings most salt-sensitive (Maas & Hoffman 1977)
    "vegetative": 1.0,
    "reproductive": 1.1,
    "senescence": 0.6,
    "harvested": 0.2,
    "unknown": 1.0,
}

_BIOTIC_SENSITIVITY = {
    "bare_soil": 0.2,
    "emergence": 0.7,
    "vegetative": 1.1,        # Dense canopy facilitates disease spread
    "reproductive": 1.3,      # Grain fill most vulnerable to pest damage
    "senescence": 0.5,
    "harvested": 0.2,
    "unknown": 1.0,
}

# v3.2: Stage-dependent thermal thresholds (°C above/below optimal)
# Used by attributor to determine if temperature is stressful FOR THIS STAGE
_STAGE_THERMAL_THRESHOLDS = {
    "bare_soil":    {"heat_trigger": 45.0, "cold_trigger": 0.0},
    "emergence":    {"heat_trigger": 30.0, "cold_trigger": 5.0},    # Most sensitive
    "vegetative":   {"heat_trigger": 33.0, "cold_trigger": 3.0},
    "reproductive": {"heat_trigger": 32.0, "cold_trigger": 4.0},    # Pollen sterility
    "senescence":   {"heat_trigger": 38.0, "cold_trigger": 0.0},
    "harvested":    {"heat_trigger": 50.0, "cold_trigger": -10.0},
    "unknown":      {"heat_trigger": 35.0, "cold_trigger": 2.0},
}

# v3.2: Stage-dependent water stress thresholds (NDMI below which = stress)
_STAGE_WATER_THRESHOLDS = {
    "bare_soil":    {"ndmi_stress": 0.05, "soil_moisture_stress": 0.08},
    "emergence":    {"ndmi_stress": 0.18, "soil_moisture_stress": 0.20},
    "vegetative":   {"ndmi_stress": 0.15, "soil_moisture_stress": 0.18},
    "reproductive": {"ndmi_stress": 0.20, "soil_moisture_stress": 0.22},  # Most sensitive
    "senescence":   {"ndmi_stress": 0.10, "soil_moisture_stress": 0.12},
    "harvested":    {"ndmi_stress": 0.05, "soil_moisture_stress": 0.08},
    "unknown":      {"ndmi_stress": 0.15, "soil_moisture_stress": 0.18},
}


def get_stage_threshold(stress_type: str, stage: str, metric: str = "") -> Optional[float]:
    """Look up a stage-dependent threshold for a given stress type.

    Args:
        stress_type: WATER, THERMAL, NUTRIENT, SALINITY, BIOTIC
        stage: Current crop stage (lowercase)
        metric: Specific metric key (e.g. "heat_trigger", "ndmi_stress")

    Returns:
        The threshold value, or None if not applicable.
    """
    stage = stage.lower() if stage else "unknown"

    if stress_type == "THERMAL" and metric:
        return _STAGE_THERMAL_THRESHOLDS.get(stage, {}).get(metric)
    if stress_type == "WATER" and metric:
        return _STAGE_WATER_THRESHOLDS.get(stage, {}).get(metric)

    # Return sensitivity multiplier for other types
    lookup = {
        "WATER": _WATER_SENSITIVITY,
        "THERMAL": _THERMAL_SENSITIVITY,
        "NUTRIENT": _NUTRIENT_SENSITIVITY,
        "SALINITY": _SALINITY_SENSITIVITY,
        "BIOTIC": _BIOTIC_SENSITIVITY,
    }
    table = lookup.get(stress_type)
    if table:
        return table.get(stage, 1.0)
    return None


# Map stress_type → sensitivity lookup table
_SENSITIVITY_TABLES = {
    "WATER": _WATER_SENSITIVITY,
    "THERMAL": _THERMAL_SENSITIVITY,
    "NUTRIENT": _NUTRIENT_SENSITIVITY,
    "SALINITY": _SALINITY_SENSITIVITY,
    "BIOTIC": _BIOTIC_SENSITIVITY,
}


def adjust_stress_for_phenology(
    stress_items: List[StressEvidence],
    crop_cycle: Optional[CropCycleContext],
) -> List[StressEvidence]:
    """Adjust stress severity based on crop phenological stage.

    v3.2: Now handles all 7 stress types with stage-specific sensitivity
    multipliers derived from Hsiao (2009), Maas & Hoffman (1977), and
    Farooq et al. (2009).

    Modifies stress items in-place and returns them.
    """
    stage = _get_current_stage(crop_cycle)

    for s in stress_items:
        sensitivity_table = _SENSITIVITY_TABLES.get(s.stress_type)
        if sensitivity_table is None:
            continue

        multiplier = sensitivity_table.get(stage, 1.0)
        if multiplier != 1.0:
            old = s.severity
            s.severity = round(min(1.0, s.severity * multiplier), 3)
            if abs(old - s.severity) > 0.01:
                s.explanation_basis.append(
                    f"Severity adjusted ×{multiplier:.1f} for {stage} stage "
                    f"{s.stress_type.lower()} sensitivity"
                )

    return stress_items


def compute_phenology_features(
    vegetation_features: Dict[str, Any],
    crop_cycle: Optional[CropCycleContext],
) -> List[PhenologyFeature]:
    """Compute phenology-adjusted vegetation indices."""
    stage = _get_current_stage(crop_cycle)
    gdd = _get_gdd(crop_cycle)
    expected_ndvi = _STAGE_EXPECTED_NDVI.get(stage, 0.40)

    features: List[PhenologyFeature] = []

    # Get current NDVI
    ndvi_val = _extract_value(vegetation_features, "ndvi_mean", "ndvi")
    if ndvi_val is not None:
        # GDD-adjusted vigor: ratio of actual to expected
        vigor = round(ndvi_val / max(0.05, expected_ndvi), 3) if expected_ndvi > 0 else 1.0
        features.append(PhenologyFeature(
            name="gdd_adjusted_vigor",
            value=vigor,
            unit="ratio",
            crop_stage=stage,
            gdd_accumulated=gdd,
            confidence=0.6 if stage != "unknown" else 0.3,
            explanation_basis=[
                f"NDVI={ndvi_val:.2f} / expected {expected_ndvi:.2f} at {stage} stage",
                f"GDD accumulated={gdd:.0f}",
            ],
        ))

        # Deviation from expected
        deviation = round(ndvi_val - expected_ndvi, 3)
        features.append(PhenologyFeature(
            name="deviation_from_expected",
            value=deviation,
            unit="index",
            crop_stage=stage,
            gdd_accumulated=gdd,
            confidence=0.6 if stage != "unknown" else 0.3,
            explanation_basis=[
                f"NDVI deviation = {deviation:+.3f} from stage expectation",
            ],
        ))

        # Stage expected NDVI (for downstream reference)
        features.append(PhenologyFeature(
            name="stage_expected_ndvi",
            value=expected_ndvi,
            unit="index",
            crop_stage=stage,
            gdd_accumulated=gdd,
            confidence=0.8,
            explanation_basis=[
                f"Expected NDVI at {stage} stage = {expected_ndvi:.2f}",
            ],
        ))

    return features


def _get_current_stage(crop_cycle: Optional[CropCycleContext]) -> str:
    """Extract current crop stage from CropCycleContext."""
    if crop_cycle is None:
        return "unknown"

    stage = getattr(crop_cycle, "current_stage", None)
    if stage:
        return stage.lower()

    return "unknown"


def _get_gdd(crop_cycle: Optional[CropCycleContext]) -> float:
    """Extract GDD from CropCycleContext."""
    if crop_cycle is None:
        return 0.0

    return float(getattr(crop_cycle, "gdd_accumulated", 0.0) or 0.0)


def _extract_value(features: Dict[str, Any], *keys: str) -> Optional[float]:
    import math
    for k in keys:
        entry = features.get(k)
        if entry is not None:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val is not None and not (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
                return val
    return None
