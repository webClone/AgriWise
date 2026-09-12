"""
ASMAE Dynamics: Thermal-Time Plant Growth Model.

Computes degree-day driven LAI expansion, biomass accumulation,
and phenological development from meteorological forcing and crop priors.

References:
  - FAO Irrigation and Drainage Paper No. 56 (Allen et al., 1998)
  - Growing Degree Day (GDD) thermal time accumulation
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class CropGrowthParameters:
    """Species-specific thermal and developmental growth parameters."""
    t_base: float = 10.0      # Base temperature below which development ceases (°C)
    t_opt: float = 25.0       # Optimal growth temperature (°C)
    t_max: float = 40.0       # Upper biological threshold temperature (°C)
    gdd_maturity: float = 1800.0  # Total accumulated degree days from planting to harvest
    max_lai: float = 5.0      # Maximum potential Leaf Area Index
    growth_rate_k: float = 0.005  # Sigmoidal growth rate coefficient


def calculate_daily_gdd(
    t_max: float,
    t_min: float,
    t_base: float = 10.0,
    t_upper: float = 35.0,
) -> float:
    """Calculate daily Growing Degree Days using the standard cutoff method.

    T_mean = (min(T_max, T_upper) + max(T_min, T_base)) / 2
    GDD = max(0.0, T_mean - T_base)
    """
    t_max_adj = min(float(t_max), float(t_upper))
    t_min_adj = max(float(t_min), float(t_base))
    t_mean = (t_max_adj + t_min_adj) / 2.0
    return max(0.0, t_mean - float(t_base))


def temperature_inhibition_factor(
    temp: float,
    t_opt: float = 25.0,
    t_max: float = 40.0,
    t_base: float = 10.0,
) -> float:
    """Thermal stress modifier on photosynthetic vigor [0.0, 1.0]."""
    if temp <= t_base or temp >= t_max:
        return 0.0
    if temp <= t_opt:
        return max(0.0, min(1.0, (temp - t_base) / (t_opt - t_base)))
    return max(0.0, min(1.0, (t_max - temp) / (t_max - t_opt)))


def step_plant_growth(
    current_lai: float,
    current_vigor: float,
    current_phenology: float,
    weather_day: Dict[str, Any],
    crop_params: Optional[CropGrowthParameters] = None,
    water_stress_ks: float = 1.0,
    delta_days: float = 1.0,
) -> Tuple[float, float, float]:
    """Execute dynamic transition step for LAI, vigor, and phenological progress.

    Returns:
        (updated_lai, updated_vigor, updated_phenology)
    """
    params = crop_params or CropGrowthParameters()
    t_max = weather_day.get("temp_max_c") or weather_day.get("temp_max") or 25.0
    t_min = weather_day.get("temp_min_c") or weather_day.get("temp_min") or 15.0
    t_mean = (float(t_max) + float(t_min)) / 2.0

    # 1. Thermal time advancement
    daily_gdd = calculate_daily_gdd(float(t_max), float(t_min), params.t_base, params.t_max)
    delta_phenology = (daily_gdd * delta_days) / max(100.0, params.gdd_maturity)
    updated_phenology = min(1.0, max(0.0, current_phenology + delta_phenology))

    # 2. Temperature effect on photosynthetic capacity
    t_factor = temperature_inhibition_factor(t_mean, params.t_opt, params.t_max, params.t_base)

    # 3. Vigor transition
    target_vigor = t_factor * max(0.0, min(1.0, water_stress_ks))
    vigor_decay = 0.95 ** delta_days
    updated_vigor = vigor_decay * current_vigor + (1.0 - vigor_decay) * target_vigor

    # 4. LAI dynamics (expansion during vegetative stages, stability during maturity)
    if updated_phenology < 0.75:
        # Vegetative expansion limited by water stress
        lai_growth = params.growth_rate_k * (params.max_lai - current_lai) * daily_gdd * water_stress_ks
        updated_lai = min(params.max_lai, max(0.0, current_lai + lai_growth * delta_days))
    else:
        # Senescence phase
        updated_lai = max(0.1, current_lai * (0.98 ** delta_days))

    return (
        round(float(updated_lai), 4),
        round(float(updated_vigor), 4),
        round(float(updated_phenology), 4),
    )
