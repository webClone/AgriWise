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


def adjust_stress_for_phenology(
    stress_items: List[StressEvidence],
    crop_cycle: Optional[CropCycleContext],
) -> List[StressEvidence]:
    """Adjust stress severity based on crop phenological stage.

    Modifies stress items in-place and returns them.
    """
    stage = _get_current_stage(crop_cycle)

    for s in stress_items:
        if s.stress_type == "WATER":
            multiplier = _WATER_SENSITIVITY.get(stage, 1.0)
            if multiplier != 1.0:
                old = s.severity
                s.severity = round(min(1.0, s.severity * multiplier), 3)
                if abs(old - s.severity) > 0.01:
                    s.explanation_basis.append(
                        f"Severity adjusted ×{multiplier:.1f} for {stage} stage water sensitivity"
                    )

        elif s.stress_type == "THERMAL":
            multiplier = _THERMAL_SENSITIVITY.get(stage, 1.0)
            if multiplier != 1.0:
                old = s.severity
                s.severity = round(min(1.0, s.severity * multiplier), 3)
                if abs(old - s.severity) > 0.01:
                    s.explanation_basis.append(
                        f"Severity adjusted ×{multiplier:.1f} for {stage} stage thermal sensitivity"
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
