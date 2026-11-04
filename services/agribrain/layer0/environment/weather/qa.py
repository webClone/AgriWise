"""
Weather QA.

Provider availability, temporal completeness, data-kind validation.
"""

from __future__ import annotations

from typing import Dict, List

from services.agribrain.layer0.environment.weather.schemas import WeatherDailyRecord, WeatherTimeSeries
from services.agribrain.layer0.environment.weather.source_roles import (
    HISTORICAL_CONTEXT_ROLES, FORECAST_ROLES,
    role_for_data_kind, record_role_is_consistent,
)


def evaluate_weather_qa(
    timeseries: WeatherTimeSeries,
) -> Dict[str, any]:
    """Evaluate weather data quality."""
    flags: List[str] = []

    if not timeseries.daily_records:
        return {
            "provider_count": 0,
            "temporal_completeness": 0.0,
            "historical_completeness": 0.0,
            "has_et0": False,
            "has_soil_moisture": False,
            "flags": ["NO_WEATHER_DATA"],
            "quality": "unusable",
        }

    # Provider availability
    providers = set(r.provider for r in timeseries.daily_records)

    # Temporal and historical completeness
    eligible_historical_dates = sorted(set(
        r.date for r in timeseries.daily_records
        if r.date
        and role_for_data_kind(getattr(r, "data_kind", None)) in HISTORICAL_CONTEXT_ROLES
        and record_role_is_consistent(r)
    ))
    eligible_forecast_dates = sorted(set(
        r.date for r in timeseries.daily_records
        if r.date
        and role_for_data_kind(getattr(r, "data_kind", None)) in FORECAST_ROLES
        and record_role_is_consistent(r)
    ))

    expected_historical = timeseries.historical_days
    expected_forecast = timeseries.forecast_days
    expected_total = expected_historical + expected_forecast

    if expected_historical > 0:
        historical_completeness = min(1.0, len(eligible_historical_dates) / expected_historical)
    elif eligible_historical_dates:
        historical_completeness = 1.0
    else:
        historical_completeness = 0.0

    eligible_dates = set(eligible_historical_dates) | set(eligible_forecast_dates)
    if expected_total > 0:
        temporal_completeness = min(1.0, len(eligible_dates) / expected_total)
    elif eligible_dates:
        temporal_completeness = min(1.0, len(eligible_dates) / max(len(eligible_dates), 1))
    else:
        temporal_completeness = 0.0

    # Check for ET₀
    has_et0 = any(
        r.et0_mm is not None for r in timeseries.daily_records
    )

    # Check for soil moisture
    has_soil_moisture = any(
        r.soil_moisture_0_1cm is not None for r in timeseries.daily_records
    )

    # Explicit dataset-role diagnostics. A response labelled 'current'
    # does not prove an independently measured weather station.
    data_kinds = {
        r.data_kind if isinstance(r.data_kind, str) else "<invalid>"
        for r in timeseries.daily_records
    }
    roles = {role_for_data_kind(r.data_kind) for r in timeseries.daily_records}
    historical_roles_present = bool(roles & HISTORICAL_CONTEXT_ROLES)
    forecast_roles_present = bool(roles & FORECAST_ROLES)
    if historical_roles_present and forecast_roles_present:
        flags.append("MIXED_DATA_KINDS")
    if forecast_roles_present:
        flags.append("FORECAST_MODEL_DATA")
    if any(role.value in ("REANALYSIS_MODEL","CLIMATOLOGY_MODEL") for role in roles):
        flags.append("REANALYSIS_OR_MODEL_DATA")
    if any(not record_role_is_consistent(r) for r in timeseries.daily_records):
        flags.append("INVALID_WEATHER_SOURCE_ROLE")
    if not historical_roles_present:
        flags.append("NO_HISTORICAL_WEATHER_CONTEXT")

    quality = "good"
    if "INVALID_WEATHER_SOURCE_ROLE" in flags or "NO_HISTORICAL_WEATHER_CONTEXT" in flags:
        quality = "unusable"
    elif "MIXED_DATA_KINDS" in flags:
        quality = "degraded"
    if historical_completeness < 0.5 or temporal_completeness < 0.5:
        if quality != "unusable":
            quality = "degraded"
        flags.append("LOW_TEMPORAL_COMPLETENESS")
    if len(providers) == 0:
        quality = "unusable"

    return {
        "provider_count": len(providers),
        "providers": sorted(providers),
        "temporal_completeness": round(temporal_completeness, 4),
        "historical_completeness": round(historical_completeness, 4),
        "has_et0": has_et0,
        "has_soil_moisture": has_soil_moisture,
        "data_kinds": sorted(data_kinds),
        "flags": flags,
        "quality": quality,
    }
