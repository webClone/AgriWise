"""
Derived Weather Features.

Computes GDD, ET₀, water balance, heat/frost flags from consensus weather.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from layer0.environment.schemas import ProcessForcing
from layer0.environment.weather.et0 import select_et0
from layer0.environment.weather.schemas import VariableConsensus, WeatherConsensusDaily


# Default crop base temperature for GDD
DEFAULT_T_BASE = 5.0


def compute_gdd(
    temp_min: Optional[float],
    temp_max: Optional[float],
    t_base: float = DEFAULT_T_BASE,
) -> float:
    """Compute Growing Degree Days for a single day."""
    if temp_min is None or temp_max is None:
        return 0.0
    t_mean = (temp_min + temp_max) / 2.0
    return max(0.0, round(t_mean - t_base, 2))


def compute_water_balance(
    precipitation_mm: float,
    et0_mm: float,
) -> float:
    """Water balance = precipitation - ET₀."""
    return round(precipitation_mm - et0_mm, 2)


def compute_daily_forcing(
    consensus: WeatherConsensusDaily,
    latitude_deg: float = 0.0,
    day_of_year: int = 1,
    t_base: float = DEFAULT_T_BASE,
) -> ProcessForcing:
    """Compute ProcessForcing from a daily consensus.

    Extracts consensus values, computes GDD, ET₀, water balance, flags.
    """
    # Extract consensus values
    temp_min = _get_consensus_value(consensus, "temp_min")
    temp_max = _get_consensus_value(consensus, "temp_max")
    temp_mean = _get_consensus_value(consensus, "temp_mean")
    precip = _get_consensus_value(consensus, "precipitation_sum") or 0.0
    vpd = _get_consensus_value(consensus, "vpd_mean")
    radiation = _get_consensus_value(consensus, "shortwave_radiation_sum")
    provider_et0 = _get_consensus_value(consensus, "et0_mm")

    # GDD
    gdd = compute_gdd(temp_min, temp_max, t_base)

    # ET₀ — full PM cascade (provider → PM → Hargreaves)
    rh_mean = _get_consensus_value(consensus, "relative_humidity_mean")
    wind_max = _get_consensus_value(consensus, "wind_speed_max")
    # Convert wind from 10m (station) to 2m if available
    wind_2m = None
    if wind_max is not None:
        from layer0.environment.weather.et0 import wind_speed_at_2m
        wind_2m = wind_speed_at_2m(wind_max, measurement_height=10.0)

    et0, et0_source = select_et0(
        provider_et0, temp_min, temp_max, latitude_deg, day_of_year,
        temp_mean=temp_mean,
        relative_humidity_mean=rh_mean,
        wind_speed_2m=wind_2m,
        shortwave_radiation_mj=radiation,
    )

    # Water balance
    water_balance = compute_water_balance(precip, et0)

    # Stress flags
    frost_flag = temp_min is not None and temp_min < 0
    thermal_stress_flag = temp_max is not None and temp_max > 35

    # Rainfall confidence from consensus
    rain_consensus = consensus.variable_consensus.get("precipitation_sum")
    rainfall_confidence = rain_consensus.confidence if rain_consensus else 0.5

    # Overall weather confidence
    weather_confidence = consensus.overall_confidence

    return ProcessForcing(
        date=consensus.date,
        gdd=gdd,
        precipitation_mm=precip,
        effective_precipitation_mm=precip * rainfall_confidence,
        et0_mm=et0,
        vpd_kpa=vpd,
        radiation_mj_m2=radiation,
        temp_min=temp_min,
        temp_max=temp_max,
        temp_mean=temp_mean,
        thermal_stress_flag=thermal_stress_flag,
        frost_flag=frost_flag,
        water_balance_mm=water_balance,
        rainfall_confidence=rainfall_confidence,
        weather_confidence=weather_confidence,
        et0_source=et0_source,
    )


def compute_multi_day_features(
    forcing_list: List[ProcessForcing],
) -> Dict[str, Any]:
    """Compute multi-day aggregated features from a forcing time series."""
    if not forcing_list:
        return {}

    # Consecutive dry/wet days
    consecutive_dry = 0
    consecutive_wet = 0
    max_dry = 0
    max_wet = 0

    cumulative_gdd = 0.0
    cumulative_precip = 0.0
    cumulative_et0 = 0.0
    frost_days = 0
    heat_days = 0

    for f in forcing_list:
        cumulative_gdd += f.gdd
        cumulative_precip += f.precipitation_mm
        cumulative_et0 += f.et0_mm

        if f.frost_flag:
            frost_days += 1
        if f.thermal_stress_flag:
            heat_days += 1

        if f.precipitation_mm < 0.5:
            consecutive_dry += 1
            consecutive_wet = 0
        else:
            consecutive_wet += 1
            consecutive_dry = 0

        max_dry = max(max_dry, consecutive_dry)
        max_wet = max(max_wet, consecutive_wet)

    return {
        "cumulative_gdd": round(cumulative_gdd, 2),
        "cumulative_precipitation_mm": round(cumulative_precip, 2),
        "cumulative_et0_mm": round(cumulative_et0, 2),
        "cumulative_water_balance_mm": round(cumulative_precip - cumulative_et0, 2),
        "consecutive_dry_days": max_dry,
        "consecutive_wet_days": max_wet,
        "frost_days": frost_days,
        "heat_stress_days": heat_days,
    }


def _get_consensus_value(
    consensus: WeatherConsensusDaily,
    variable: str,
) -> Optional[float]:
    """Extract selected value from consensus for a variable."""
    vc = consensus.variable_consensus.get(variable)
    if vc is None:
        return None
    return vc.selected_value
