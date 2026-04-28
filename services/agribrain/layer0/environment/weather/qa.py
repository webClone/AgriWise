"""
Weather QA.

Provider availability, temporal completeness, data-kind validation.
"""

from __future__ import annotations

from typing import Dict, List

from layer0.environment.weather.schemas import WeatherDailyRecord, WeatherTimeSeries


def evaluate_weather_qa(
    timeseries: WeatherTimeSeries,
) -> Dict[str, any]:
    """Evaluate weather data quality."""
    flags: List[str] = []

    if not timeseries.daily_records:
        return {
            "provider_count": 0,
            "temporal_completeness": 0.0,
            "has_et0": False,
            "has_soil_moisture": False,
            "flags": ["NO_WEATHER_DATA"],
            "quality": "unusable",
        }

    # Provider availability
    providers = set(r.provider for r in timeseries.daily_records)

    # Temporal completeness
    dates = sorted(set(r.date for r in timeseries.daily_records if r.date))
    temporal_completeness = len(dates) / max(
        timeseries.historical_days + timeseries.forecast_days, 1
    )

    # Check for ET₀
    has_et0 = any(
        r.et0_mm is not None for r in timeseries.daily_records
    )

    # Check for soil moisture
    has_soil_moisture = any(
        r.soil_moisture_0_1cm is not None for r in timeseries.daily_records
    )

    # Data-kind validation: ensure forecast not mixed with historical
    data_kinds = set(r.data_kind for r in timeseries.daily_records)
    if "forecast" in data_kinds and "historical_reanalysis" in data_kinds:
        flags.append("MIXED_DATA_KINDS")

    # Model/reanalysis flag
    if any(r.data_kind in ("historical_reanalysis", "historical_forecast")
           for r in timeseries.daily_records):
        flags.append("REANALYSIS_OR_MODEL_DATA")

    quality = "good"
    if temporal_completeness < 0.5:
        quality = "degraded"
        flags.append("LOW_TEMPORAL_COMPLETENESS")
    if len(providers) == 0:
        quality = "unusable"

    return {
        "provider_count": len(providers),
        "providers": sorted(providers),
        "temporal_completeness": round(temporal_completeness, 4),
        "has_et0": has_et0,
        "has_soil_moisture": has_soil_moisture,
        "data_kinds": sorted(data_kinds),
        "flags": flags,
        "quality": quality,
    }
