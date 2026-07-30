"""
V72: Observation noise model.

Per-index observation noise R_t with crop-stage modulation
and weather-adjusted noise inflation.

Each observation has:
  - base_noise_sigma: Default noise σ
  - noise_floor: Minimum noise (prevents over-confident updates)
  - crop_stage_modifier: Extra noise during specific phenology stages
  - weather_modifier: Noise inflation for hazy/humid conditions
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

from .index_state_mapping import INDEX_STATE_REGISTRY, IndexStateMapping


def compute_observation_noise(
    index_name: str,
    crop_stage: str = "",
    cloud_fraction: float = 0.0,
    humidity_factor: float = 1.0,
    valid_support_fraction: float = 1.0,
    registration_uncertainty_m: float = 0.0,
    temporal_aggregation_days: float = 1.0,
) -> float:
    """Compute observation noise σ for a given index.

    noise = max(noise_floor, base_sigma * crop_modifier * weather_modifier)

    Args:
        index_name: Observation index name.
        crop_stage: Current crop phenology stage.
        cloud_fraction: Cloud fraction [0, 1] for weather modifier.
        humidity_factor: Humidity-based noise inflation (1.0 = normal).

    Returns:
        Observation noise standard deviation σ.
    """
    mapping = INDEX_STATE_REGISTRY.get(index_name)
    if mapping is None:
        return 0.1  # Conservative default

    sigma = mapping.base_noise_sigma

    # Crop-stage modifier
    if crop_stage and mapping.crop_stage_noise_multiplier:
        stage_mult = mapping.crop_stage_noise_multiplier.get(crop_stage, 1.0)
        sigma *= stage_mult

    # Weather modifier: inflate noise near cloud edges and in humid conditions
    if cloud_fraction > 0.3:
        # Near cloud edges: increase noise proportionally
        weather_mult = 1.0 + 0.5 * (cloud_fraction - 0.3) / 0.7
        sigma *= weather_mult

    sigma *= humidity_factor

    # Missing support, co-registration error and temporal compositing are
    # independent error families. Propagate them into R instead of allowing
    # a context-free static index default.
    support = max(0.0, min(1.0, float(valid_support_fraction)))
    support_sigma = (1.0 - support) * 0.10
    registration_sigma = min(0.20, max(0.0, float(registration_uncertainty_m)) / 100.0)
    temporal_sigma = min(0.15, math.log1p(max(0.0, float(temporal_aggregation_days) - 1.0)) * 0.02)
    sigma = math.sqrt(
        sigma * sigma
        + support_sigma * support_sigma
        + registration_sigma * registration_sigma
        + temporal_sigma * temporal_sigma
    )

    # Enforce noise floor
    return max(mapping.noise_floor, sigma)


def build_observation_noise_vector(
    index_names: List[str],
    crop_stage: str = "",
    cloud_fraction: float = 0.0,
    humidity_factor: float = 1.0,
) -> List[float]:
    """Build observation noise vector R_t = diag(σ²) for multiple indices.

    Returns list of noise VARIANCES (σ²), one per index.
    """
    variances = []
    for name in index_names:
        sigma = compute_observation_noise(
            name, crop_stage, cloud_fraction, humidity_factor,
        )
        variances.append(sigma * sigma)
    return variances


def get_noise_covariance_diagonal(
    index_names: List[str],
    crop_stage: str = "",
    cloud_fraction: float = 0.0,
) -> Dict[str, float]:
    """Get noise variances keyed by index name.

    Returns {index_name: σ²}.
    """
    result = {}
    for name in index_names:
        sigma = compute_observation_noise(name, crop_stage, cloud_fraction)
        result[name] = sigma * sigma
    return result
