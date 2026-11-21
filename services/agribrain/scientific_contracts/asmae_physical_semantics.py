"""Fail-closed physical semantics for ASMAE states consumed outside Layer 05.

A value without explicit source unit is NOT a physical observation.
An authentic physical quantity is NOT automatically a crop stress diagnosis.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class TaggedStateQuantity:
    value: float
    unit: str
    state: str


_STATE_UNITS = {
    "chlorophyll": ("ug/cm2", 0.0, 80.0),
    "canopy_water": ("fraction_content", 0.0, 1.0),
}


def _field(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def require_tagged_state_quantity(value: Any, state: str) -> TaggedStateQuantity:
    """Explicit source unit required, never inferred from a float or its range."""
    if state not in _STATE_UNITS:
        raise ValueError(f"unsupported_asmae_physical_state:{state}")
    expected, lower, upper = _STATE_UNITS[state]
    unit = _field(value, "unit")
    if unit is None:
        unit = _field(value, "units")
    if not isinstance(unit, str) or unit != expected:
        raise ValueError(f"asmae_{state}_unit_missing_or_mismatched")
    raw = _field(value, "value")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(f"asmae_{state}_value_not_finite")
    physical = float(raw)
    if not math.isfinite(physical) or not lower <= physical <= upper:
        raise ValueError(f"asmae_{state}_value_outside_physical_domain")
    return TaggedStateQuantity(value=physical, unit=unit, state=state)


def calibrated_chlorophyll_deficit(
    feature: Any,
    *,
    crop_type: str,
    calibration: Optional[Mapping[str, Any]],
) -> Optional[float]:
    """Return an exploratory 0..1 deficiency score, never prescription authority.

    No generic <0.45/>0.65 or guessed <30/>50 thresholds. A *separately*
    qualified crop/phenology calibration must be supplied by an authorized
    source. Missing calibration means missing signal, not zero chlorophyll.
    """
    quantity = require_tagged_state_quantity(feature, "chlorophyll")
    if (not isinstance(calibration, Mapping)
            or calibration.get("status") != "qualified"
            or calibration.get("unit") != "ug/cm2"
            or calibration.get("crop_type") != crop_type
            or not isinstance(calibration.get("calibration_ref"), str)
            or not calibration.get("calibration_ref")):
        return None
    if (_field(feature, "state_update_allowed") is not True
            or _field(feature, "diagnostic_only", True) is not False):
        return None
    low = calibration.get("low_chlorophyll")
    normal = calibration.get("adequate_chlorophyll")
    if (type(low) not in (float, int) or type(normal) not in (float, int)
            or not math.isfinite(float(low)) or not math.isfinite(float(normal))
            or not 0 <= float(low) < float(normal) <= 80.0):
        return None
    return max(0.0, min(1.0,
        (float(normal) - quantity.value) / (float(normal) - float(low))
    ))


def validate_canopy_water_content(feature: Any) -> TaggedStateQuantity:
    """Water *content*, not inverted water stress or irrigation demand."""
    return require_tagged_state_quantity(feature, "canopy_water")
