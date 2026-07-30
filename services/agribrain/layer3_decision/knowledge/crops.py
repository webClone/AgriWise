"""
Layer 3 Crop Profile Interface.

Thin adapter that delegates to the centralized crop_database.
Maintains backward compatibility — get_crop_profile() still returns
a CropProfile dataclass, built from CropSpec.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from crop_database import get_crop as _get_crop, CropSpec


@dataclass
class CropProfile:
    """L3-compatible crop profile (backward compatible)."""
    name: str
    gdd_base_temp: float
    water_stress_sensitivity: Dict[str, float]
    max_root_depth_cm: float
    kc_init: float
    kc_mid: float
    kc_end: float


def _spec_to_profile(spec: CropSpec) -> CropProfile:
    """Convert a CropSpec to a CropProfile."""
    return CropProfile(
        name=spec.name,
        gdd_base_temp=spec.gdd_base_temp,
        water_stress_sensitivity=dict(spec.water_stress_sensitivity),
        max_root_depth_cm=spec.max_root_depth_cm,
        kc_init=spec.kc_init,
        kc_mid=spec.kc_mid,
        kc_end=spec.kc_end,
    )


def get_crop_profile(crop_name: str) -> CropProfile:
    """Look up a crop profile by name, with alias resolution and substring fallback.

    Delegates to the centralized crop_database (209+ species).
    Never returns None — falls back to wheat if unrecognized.
    """
    spec = _get_crop(crop_name)
    return _spec_to_profile(spec)
