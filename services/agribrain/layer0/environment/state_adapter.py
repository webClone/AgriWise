"""
Environmental State Adapter.

Named state_adapter (not kalman_adapter) because most environmental data
affects the process prediction step, not the Kalman update step.

Produces:
  - ProcessParameters (from soil priors → process model params)
  - ProcessForcing (from weather → process model prediction)
  - WeakKalmanObservations (from Open-Meteo modelled soil moisture only)

NOT allowed:
  - Weather provider → direct canopy_stress Kalman update
  - SoilGrids/FAO → daily Kalman observations
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from layer0.environment.schemas import WeakKalmanObservation
from layer0.environment.weather.schemas import WeatherConsensusDaily, WeatherDailyRecord


# Weak observation mapping from CONTRACT.md
WEAK_SM_MAP = {
    "soil_moisture_0_1cm": {
        "obs_type": "open_meteo_sm_0_1",
        "state_maps_to": "sm_0_10",
        "base_sigma": 0.15,
        "reliability_ceiling": 0.35,
    },
    "soil_moisture_1_3cm": {
        "obs_type": "open_meteo_sm_1_3",
        "state_maps_to": "sm_0_10",
        "base_sigma": 0.15,
        "reliability_ceiling": 0.35,
    },
    "soil_moisture_3_9cm": {
        "obs_type": "open_meteo_sm_3_9",
        "state_maps_to": "sm_10_40",
        "base_sigma": 0.18,
        "reliability_ceiling": 0.30,
    },
    "soil_moisture_9_27cm": {
        "obs_type": "open_meteo_sm_9_27",
        "state_maps_to": "sm_10_40",
        "base_sigma": 0.18,
        "reliability_ceiling": 0.30,
    },
}

# 27-81cm: deep context only, NOT mapped to Kalman in V1
DEEP_LAYER_CONTEXT_ONLY = ["soil_moisture_27_81cm"]

# Data kinds allowed for weak Kalman observations
ALLOWED_DATA_KINDS = {"current", "historical_reanalysis"}


def create_weak_kalman_observations(
    open_meteo_records: List[WeatherDailyRecord],
    weather_provider_failed: bool = False,
) -> List[WeakKalmanObservation]:
    """Create weak Kalman observations from Open-Meteo modelled soil moisture.

    Conditions for emission (from CONTRACT.md):
    - data_kind must be current/historical_reanalysis (NOT forecast)
    - weather consensus does not flag provider-wide failure
    - labeled as modelled_soil_moisture, never soil_moisture_observation
    - reliability ≤ 0.35 always
    """
    if weather_provider_failed:
        return []

    observations: List[WeakKalmanObservation] = []

    for rec in open_meteo_records:
        if rec.provider != "open_meteo":
            continue
        if rec.data_kind not in ALLOWED_DATA_KINDS:
            continue

        for sm_attr, config in WEAK_SM_MAP.items():
            value = getattr(rec, sm_attr, None)
            if value is None:
                continue

            observations.append(WeakKalmanObservation(
                obs_type=config["obs_type"],
                value=value,
                sigma=config["base_sigma"],
                reliability=config["reliability_ceiling"],
                state_maps_to=config["state_maps_to"],
                source="open_meteo",
                data_kind="modelled",
                label="modelled_soil_moisture",
                timestamp=rec.date,
            ))

    return observations


# ---------------------------------------------------------------------------
# V1.1: Forecast Process Forcing
# ---------------------------------------------------------------------------

def create_forecast_process_forcing(
    forecast_consensus: List,
) -> List:
    """Create future process forcing from forecast consensus.

    HARD RULE: This creates ForecastProcessForcing only.
    It must NEVER create a WeakKalmanObservation.
    Forecast does NOT correct current crop state.
    """
    from layer0.environment.weather.forecast_schemas import ForecastProcessForcing
    from layer0.environment.weather.derived import compute_gdd, compute_water_balance
    from layer0.environment.weather.et0 import select_et0

    forcing_list = []

    for day_consensus in forecast_consensus:
        # SAFETY CHECK: assert this is forecast data
        assert day_consensus.lead_day >= 0, "Forecast forcing must have non-negative lead_day"

        # Extract consensus values
        tmin = _get_forecast_value(day_consensus, "tmin")
        tmax = _get_forecast_value(day_consensus, "tmax")
        tmean = _get_forecast_value(day_consensus, "tmean")
        precip = _get_forecast_value(day_consensus, "precipitation") or 0.0
        et0_val = _get_forecast_value(day_consensus, "et0")
        vpd = _get_forecast_value(day_consensus, "vpd_max")
        wind = _get_forecast_value(day_consensus, "wind_speed")
        gust = _get_forecast_value(day_consensus, "wind_gusts")

        # ET₀ fallback
        et0 = et0_val if et0_val is not None else 0.0

        # GDD
        gdd = compute_gdd(tmin, tmax) if tmin is not None and tmax is not None else 0.0

        # Water balance
        water_balance = compute_water_balance(precip, et0)

        # Rainfall confidence for effective precipitation
        rain_conf = 0.5
        rain_vc = day_consensus.variable_consensus.get("precipitation")
        if rain_vc:
            rain_conf = rain_vc.variable_confidence

        forcing_list.append(ForecastProcessForcing(
            date=day_consensus.date,
            lead_day=day_consensus.lead_day,
            temperature_min_c=tmin,
            temperature_max_c=tmax,
            temperature_mean_c=tmean,
            precipitation_mm=precip,
            effective_precipitation_mm=round(precip * rain_conf, 2),
            et0_mm=et0,
            vpd_kpa=vpd,
            wind_speed_mean_ms=wind,
            wind_gust_max_ms=gust,
            water_balance_mm=water_balance,
            gdd=gdd,
            forcing_confidence=day_consensus.overall_forecast_confidence,
            data_kind="forecast",
        ))

    return forcing_list


def _get_forecast_value(day_consensus, var: str):
    """Extract selected value from forecast consensus."""
    vc = day_consensus.variable_consensus.get(var)
    if vc is None:
        return None
    return vc.selected_value

