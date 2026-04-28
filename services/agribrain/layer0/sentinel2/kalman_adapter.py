"""
Sentinel-2 Kalman Adapter — Maps indices to KalmanObservations.

V1 mapping strategy:
  NDVI/EVI → LAI (strong)
  NDMI → canopy_stress (moderate)
  NDRE → canopy_stress (weak, supporting evidence only)
  BSI → inverse LAI (weak, supporting evidence only)

UNUSABLE scenes → zero observations.
DEGRADED scenes → reliability ≤ 0.5, sigma_multiplier ≥ 2.0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from layer0.sentinel2.schemas import (
    SceneQualityClass,
    Sentinel2ScenePackage,
)


@dataclass
class Sentinel2KalmanObservation:
    """A single observation ready for the Kalman filter."""
    obs_type: str = ""          # Key for observation_model dispatcher
    value: float = 0.0
    sigma: float = 0.1          # Measurement noise std dev
    reliability: float = 0.5    # 0–1 reliability weight
    scene_id: str = ""
    source: str = "SENTINEL2"


# V1 mapping definitions
_KALMAN_MAPPINGS = {
    "NDVI": {
        "obs_type": "ndvi",
        "attr": "ndvi_mean",
        "base_sigma": 0.02,
        "reliability_range": (0.85, 0.95),
        "strength": "strong",
    },
    "EVI": {
        "obs_type": "evi",
        "attr": "evi_mean",
        "base_sigma": 0.03,
        "reliability_range": (0.80, 0.90),
        "strength": "strong",
    },
    "NDMI": {
        "obs_type": "ndmi",
        "attr": "ndmi_mean",
        "base_sigma": 0.04,
        "reliability_range": (0.75, 0.90),
        "strength": "moderate",
    },
    "NDRE": {
        "obs_type": "ndre",
        "attr": "ndre_mean",
        "base_sigma": 0.06,
        "reliability_range": (0.50, 0.70),
        "strength": "weak",
    },
    "BSI": {
        "obs_type": "bare_soil_index",
        "attr": "bsi_mean",
        "base_sigma": 0.08,
        "reliability_range": (0.40, 0.65),
        "strength": "weak",
    },
}


def create_kalman_observations(
    pkg: Sentinel2ScenePackage,
) -> List[Sentinel2KalmanObservation]:
    """
    Create Kalman observations from a Sentinel2ScenePackage.

    Rules:
      - UNUSABLE scenes → empty list
      - DEGRADED scenes → reliability ≤ 0.5, sigma × 2.0
      - EXCELLENT scenes → full reliability range
      - Weak indices (NDRE, BSI) always have low reliability ceiling
    """
    if not pkg.qa.usable:
        return []

    observations = []
    summary = pkg.plot_summary
    qa = pkg.qa

    # Quality-based scaling
    if qa.quality_class == SceneQualityClass.EXCELLENT:
        quality_factor = 1.0
    elif qa.quality_class == SceneQualityClass.GOOD:
        quality_factor = 0.85
    else:  # DEGRADED
        quality_factor = 0.5

    for idx_name, mapping in _KALMAN_MAPPINGS.items():
        value = getattr(summary, mapping["attr"], None)
        if value is None:
            continue

        base_sigma = mapping["base_sigma"]
        rel_lo, rel_hi = mapping["reliability_range"]

        # Compute effective sigma
        sigma = base_sigma * qa.sigma_multiplier

        # Compute reliability within allowed range
        reliability = rel_lo + (rel_hi - rel_lo) * quality_factor

        # Enforce DEGRADED ceiling
        if qa.quality_class == SceneQualityClass.DEGRADED:
            reliability = min(reliability, 0.5)
            sigma = max(sigma, base_sigma * 2.0)

        # Weak indices cannot exceed their ceiling regardless of quality
        if mapping["strength"] == "weak":
            reliability = min(reliability, rel_hi)

        observations.append(Sentinel2KalmanObservation(
            obs_type=mapping["obs_type"],
            value=value,
            sigma=round(sigma, 4),
            reliability=round(max(0.0, min(1.0, reliability)), 4),
            scene_id=pkg.metadata.scene_id,
        ))

    return observations
