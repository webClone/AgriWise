"""
Sentinel-5P Kalman Adapter — Maps SIF to KalmanObservations.

V1 mapping strategy:
  SIF → photosynthetic_efficiency + LAI (the ONLY direct photo_eff signal)

UNUSABLE scenes → zero observations.
DEGRADED scenes → reliability ≤ 0.20, sigma_multiplier ≥ 2.5.
CEILING: reliability never exceeds 0.45 (spatial resolution penalty).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from layer0.sentinel5p.schemas import (
    SIFQualityClass,
    Sentinel5PScenePackage,
)


@dataclass
class Sentinel5PKalmanObservation:
    """A single SIF observation ready for the Kalman filter."""
    obs_type: str = ""          # Key for observation_model dispatcher
    value: float = 0.0
    sigma: float = 0.15         # Measurement noise std dev (coarse)
    reliability: float = 0.35   # 0–0.45 range (ceiling)
    scene_id: str = ""
    source: str = "SENTINEL5P"


# Reliability ranges per quality class (always within 0–0.45 ceiling)
_QUALITY_PARAMS = {
    SIFQualityClass.EXCELLENT: {
        "quality_factor": 1.0,
        "reliability_range": (0.35, 0.45),
    },
    SIFQualityClass.GOOD: {
        "quality_factor": 0.80,
        "reliability_range": (0.28, 0.38),
    },
    SIFQualityClass.DEGRADED: {
        "quality_factor": 0.50,
        "reliability_range": (0.15, 0.25),
    },
}


def create_kalman_observations(
    pkg: Sentinel5PScenePackage,
) -> List[Sentinel5PKalmanObservation]:
    """
    Create Kalman observations from a Sentinel5PScenePackage.

    Rules:
      - UNUSABLE scenes → empty list
      - Only produces 'sif' obs_type (maps to ObservationModel.sentinel5p_sif)
      - Reliability NEVER exceeds 0.45 (hard ceiling)
      - Sigma is always high (≥ 0.15) due to coarse spatial resolution
    """
    if not pkg.qa.usable:
        return []

    sif_value = pkg.sif_data.sif_daily_mean
    if sif_value is None:
        return []

    qa = pkg.qa
    params = _QUALITY_PARAMS.get(
        qa.quality_class,
        _QUALITY_PARAMS[SIFQualityClass.DEGRADED],
    )

    quality_factor = params["quality_factor"]
    rel_lo, rel_hi = params["reliability_range"]

    # Compute effective sigma (base 0.15 × QA sigma_multiplier)
    base_sigma = 0.15
    sigma = base_sigma * qa.sigma_multiplier

    # Compute reliability within allowed range
    reliability = rel_lo + (rel_hi - rel_lo) * quality_factor

    # Enforce DEGRADED ceiling
    if qa.quality_class == SIFQualityClass.DEGRADED:
        reliability = min(reliability, 0.25)
        sigma = max(sigma, base_sigma * 2.5)

    # HARD CEILING — spatial resolution penalty
    reliability = min(reliability, 0.45)

    return [Sentinel5PKalmanObservation(
        obs_type="sif",
        value=sif_value,
        sigma=round(sigma, 4),
        reliability=round(max(0.0, min(0.45, reliability)), 4),
        scene_id=pkg.metadata.scene_id,
    )]
