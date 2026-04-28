"""
Sentinel-1 SAR Kalman Adapter.

Creates KalmanObservation entries from SAR scene packages.
Uses existing vv/vh models from observation_model.py.
Adds weak sar_rvi and sar_moisture_proxy.

IMPORTANT: flood_score and emergence are packet-only — NO Kalman.
IMPORTANT: roughness_proxy is packet-only — NO Kalman.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from layer0.sentinel1.schemas import (
    SARQualityClass,
    Sentinel1PlotSummary,
    Sentinel1QAResult,
    Sentinel1SceneMetadata,
)


@dataclass
class SARKalmanObservation:
    """A single SAR-derived observation for the Kalman filter."""
    obs_type: str           # "vv", "vh", "sar_rvi", "sar_moisture_proxy"
    value: float
    sigma: float
    reliability: float
    source: str = "sentinel1_sar_v1"
    scene_id: str = ""
    acquisition_datetime: Optional[str] = None


# V1 Kalman mapping table from CONTRACT.md
SAR_KALMAN_MAP = {
    "vv": {
        "feature_key": "vv_db_mean",
        "base_sigma": 1.5,
        "reliability_ceiling": 0.85,
        "strength": "strong_moderate",
    },
    "vh": {
        "feature_key": "vh_db_mean",
        "base_sigma": 2.0,
        "reliability_ceiling": 0.75,
        "strength": "moderate",
    },
    "sar_rvi": {
        "feature_key": "rvi_mean",
        "base_sigma": 0.10,
        "reliability_ceiling": 0.55,
        "strength": "weak",
    },
    "sar_moisture_proxy": {
        "feature_key": "surface_wetness_proxy_mean",
        "base_sigma": 0.12,
        "reliability_ceiling": 0.50,
        "strength": "weak",
    },
}

# EXPLICITLY EXCLUDED from Kalman
PACKET_ONLY_FEATURES = [
    "flood_score",
    "roughness_proxy",
    "emergence_signal",
]


def create_sar_kalman_observations(
    plot_summary: Sentinel1PlotSummary,
    qa: Sentinel1QAResult,
    metadata: Sentinel1SceneMetadata,
    context: Optional[Dict[str, Any]] = None,
) -> List[SARKalmanObservation]:
    """
    Create Kalman observations from SAR plot summary.

    Returns empty list if scene is UNUSABLE.
    DEGRADED: all reliability ≤ 0.5, all sigma ≥ base × 2.0.

    Context can adjust reliability:
    - latest_sentinel2_lai > 3 → downweight VV moisture
    """
    if not qa.usable:
        return []

    observations = []
    is_degraded = qa.quality_class == SARQualityClass.DEGRADED

    # Context adjustments
    lai_high = False
    if context and context.get("latest_sentinel2_lai", 0) > 3.0:
        lai_high = True

    acq_str = (
        metadata.acquisition_datetime.isoformat()
        if metadata.acquisition_datetime else None
    )

    for obs_type, config in SAR_KALMAN_MAP.items():
        value = getattr(plot_summary, config["feature_key"], None)
        if value is None:
            continue

        sigma = config["base_sigma"] * qa.sigma_multiplier
        reliability = min(config["reliability_ceiling"], qa.reliability_weight)

        # DEGRADED caps
        if is_degraded:
            reliability = min(reliability, 0.50)
            sigma = max(sigma, config["base_sigma"] * 2.0)

        # Context: LAI high → downweight VV moisture
        if obs_type == "vv" and lai_high:
            reliability *= 0.6
            sigma *= 1.5

        if obs_type == "sar_moisture_proxy" and lai_high:
            reliability *= 0.5
            sigma *= 1.8

        observations.append(SARKalmanObservation(
            obs_type=obs_type,
            value=value,
            sigma=round(sigma, 4),
            reliability=round(reliability, 4),
            scene_id=metadata.scene_id,
            acquisition_datetime=acq_str,
        ))

    return observations
