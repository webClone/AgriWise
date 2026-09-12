"""
ASMAE Dynamics: Soil Hydraulic Drying & Water Balance Model.

Computes soil moisture depletion, evapotranspiration loss,
percolation, and surface wetness decay from FAO-56 dual crop coefficient principles.

References:
  - FAO Irrigation and Drainage Paper No. 56 (Allen et al., 1998)
  - Campbell and Van Genuchten soil water retention formulations
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class SoilHydraulicParameters:
    """Soil physical texture and water retention thresholds."""
    theta_sat: float = 0.45    # Saturation volumetric water content (m3/m3)
    theta_fc: float = 0.32     # Field capacity (m3/m3)
    theta_wp: float = 0.14     # Permanent wilting point (m3/m3)
    rooting_depth_m: float = 0.8  # Effective root zone depth (m)
    p_depletion: float = 0.5   # Fraction of TAW easily available without stress (p factor)
    drainage_coeff: float = 0.4  # Daily excess gravity drainage coefficient


def compute_transpiration_reduction_ks(
    theta: float,
    theta_fc: float = 0.32,
    theta_wp: float = 0.14,
    p: float = 0.5,
) -> float:
    """Calculate FAO-56 moisture stress reduction coefficient Ks [0.0, 1.0].

    Ks = (TAW - Dr) / ((1 - p) * TAW)
    When theta > theta_threshold, Ks = 1.0 (no water stress).
    When theta <= theta_wp, Ks = 0.0 (maximum stress / complete stomatal closure).
    """
    theta_val = max(theta_wp, min(theta_fc, float(theta)))
    theta_threshold = theta_fc - p * (theta_fc - theta_wp)
    if theta_val >= theta_threshold:
        return 1.0
    denom = max(1e-4, theta_threshold - theta_wp)
    return max(0.0, min(1.0, (theta_val - theta_wp) / denom))


def step_soil_drying(
    current_root_zone_water: float,
    current_surface_wetness: float,
    weather_day: Dict[str, Any],
    soil_params: Optional[SoilHydraulicParameters] = None,
    kc: float = 1.0,
    irrigation_mm: float = 0.0,
    delta_days: float = 1.0,
) -> Tuple[float, float, float]:
    """Execute dynamic transition step for soil moisture and surface wetness.

    Returns:
        (updated_root_zone_water, updated_surface_wetness, ks_stress_factor)
    """
    params = soil_params or SoilHydraulicParameters()
    rain_mm = float(weather_day.get("precipitation_mm") or weather_day.get("rainfall_mm") or 0.0)
    et0_mm = float(weather_day.get("et0_mm") or weather_day.get("et0") or 3.5)

    root_depth_mm = max(100.0, params.rooting_depth_m * 1000.0)

    # 1. Surface wetness event dynamics (evaporates and drains quickly)
    water_input_mm = (rain_mm * delta_days) + float(irrigation_mm)
    rain_pulse = min(1.0, max(0.0, water_input_mm / 25.0)) if water_input_mm > 0.0 else 0.0
    surface_decay = 0.60 ** delta_days
    updated_surface_wetness = min(1.0, max(0.0, current_surface_wetness * surface_decay + rain_pulse))

    # 2. Moisture stress factor Ks
    ks = compute_transpiration_reduction_ks(
        current_root_zone_water, params.theta_fc, params.theta_wp, params.p_depletion
    )

    # 3. Evapotranspiration extraction
    actual_et_mm = ks * kc * et0_mm * delta_days
    delta_theta_et = actual_et_mm / root_depth_mm
    delta_theta_inflow = water_input_mm / root_depth_mm

    # 4. Drainage above field capacity
    excess = max(0.0, current_root_zone_water - params.theta_fc)
    drainage = excess * params.drainage_coeff * delta_days

    updated_root_zone_water = (
        current_root_zone_water + delta_theta_inflow - delta_theta_et - drainage
    )
    # Physical clamp to [0.5 * theta_wp, theta_sat]
    updated_root_zone_water = min(params.theta_sat, max(params.theta_wp * 0.5, updated_root_zone_water))

    return (
        round(float(updated_root_zone_water), 4),
        round(float(updated_surface_wetness), 4),
        round(float(ks), 4),
    )
