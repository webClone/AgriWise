"""
Open-Meteo Provider Adapter.

Normalizes Open-Meteo API responses to common WeatherDailyRecord.
V1: accepts pre-fetched/mocked JSON. No live API calls.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from layer0.environment.weather.schemas import WeatherDailyRecord, WeatherTimeSeries


# Open-Meteo field name mapping to common schema
OPEN_METEO_DAILY_MAP = {
    "temperature_2m_min": "temp_min",
    "temperature_2m_max": "temp_max",
    "temperature_2m_mean": "temp_mean",
    "precipitation_sum": "precipitation_sum",
    "rain_sum": "rain_sum",
    "precipitation_hours": "precipitation_hours",
    "et0_fao_evapotranspiration": "et0_mm",
    "vapour_pressure_deficit_max": "vpd_mean",
    "shortwave_radiation_sum": "shortwave_radiation_sum",
    "sunshine_duration": "sunshine_duration_hours",
    "windspeed_10m_max": "wind_speed_max",
    "windgusts_10m_max": "wind_gusts_max",
    "relative_humidity_2m_mean": "relative_humidity_mean",
    "dewpoint_2m_mean": "dew_point_mean",
    "surface_pressure_mean": "surface_pressure_mean",
    "cloudcover_mean": "cloud_cover_mean",
    "soil_temperature_0_to_7cm_mean": "soil_temperature_0_7cm",
    "soil_temperature_7_to_28cm_mean": "soil_temperature_7_28cm",
    "soil_moisture_0_to_1cm_mean": "soil_moisture_0_1cm",
    "soil_moisture_1_to_3cm_mean": "soil_moisture_1_3cm",
    "soil_moisture_3_to_9cm_mean": "soil_moisture_3_9cm",
    "soil_moisture_9_to_27cm_mean": "soil_moisture_9_27cm",
    "soil_moisture_27_to_81cm_mean": "soil_moisture_27_81cm",
}


def normalize_open_meteo_daily(
    raw_response: Dict[str, Any],
    data_kind: str = "historical_reanalysis",
    retrieval_time: Optional[str] = None,
) -> List[WeatherDailyRecord]:
    """Convert Open-Meteo daily response to list of WeatherDailyRecord.

    Expected format:
    {
        "daily": {
            "time": ["2026-04-20", "2026-04-21", ...],
            "temperature_2m_min": [8.5, 9.1, ...],
            "temperature_2m_max": [22.3, 23.1, ...],
            ...
        },
        "timezone": "UTC"
    }
    """
    daily = raw_response.get("daily", {})
    dates = daily.get("time", [])
    records: List[WeatherDailyRecord] = []

    for i, date in enumerate(dates):
        rec = WeatherDailyRecord(
            date=date,
            provider="open_meteo",
            data_kind=data_kind,
            retrieval_time=retrieval_time,
        )

        for om_key, common_key in OPEN_METEO_DAILY_MAP.items():
            values = daily.get(om_key, [])
            if i < len(values) and values[i] is not None:
                setattr(rec, common_key, values[i])

        # Convert sunshine_duration from seconds to hours if needed
        if rec.sunshine_duration_hours is not None and rec.sunshine_duration_hours > 24:
            rec.sunshine_duration_hours = rec.sunshine_duration_hours / 3600.0

        records.append(rec)

    return records


# ---------------------------------------------------------------------------
# V1.1 Forecast Normalization
# ---------------------------------------------------------------------------

# Open-Meteo hourly forecast field mapping
OPEN_METEO_HOURLY_MAP = {
    "temperature_2m": "temperature_2m_c",
    "relative_humidity_2m": "relative_humidity_2m_pct",
    "dew_point_2m": "dew_point_2m_c",
    "precipitation": "precipitation_mm",
    "rain": "rain_mm",
    "precipitation_probability": "precipitation_probability_pct",
    "cloud_cover": "cloud_cover_pct",
    "shortwave_radiation": "shortwave_radiation_w_m2",
    "et0_fao_evapotranspiration": "reference_et0_mm",
    "vapour_pressure_deficit": "vapour_pressure_deficit_kpa",
    "wind_speed_10m": "wind_speed_10m_ms",
    "wind_direction_10m": "wind_direction_10m_deg",
    "wind_gusts_10m": "wind_gusts_10m_ms",
    "surface_pressure": "surface_pressure_hpa",
    "soil_temperature_0cm": "soil_temperature_0cm_c",
    "soil_temperature_6cm": "soil_temperature_6cm_c",
    "soil_temperature_18cm": "soil_temperature_18cm_c",
    "soil_temperature_54cm": "soil_temperature_54cm_c",
    "soil_moisture_0_to_1cm": "soil_moisture_0_1cm",
    "soil_moisture_1_to_3cm": "soil_moisture_1_3cm",
    "soil_moisture_3_to_9cm": "soil_moisture_3_9cm",
    "soil_moisture_9_to_27cm": "soil_moisture_9_27cm",
    "soil_moisture_27_to_81cm": "soil_moisture_27_81cm",
    "weather_code": "weather_code",
}


def normalize_open_meteo_forecast_hourly(
    raw_response: Dict[str, Any],
    timezone: str = "UTC",
    model_run_time: Optional[str] = None,
    retrieval_time: Optional[str] = None,
) -> List:
    """Convert Open-Meteo hourly forecast response to ForecastHourlyRecord list.

    Expected format:
    {
        "hourly": {
            "time": ["2026-04-26T00:00", "2026-04-26T01:00", ...],
            "temperature_2m": [12.5, 11.8, ...],
            ...
        }
    }
    """
    from layer0.environment.weather.forecast_schemas import ForecastHourlyRecord

    hourly = raw_response.get("hourly", {})
    times = hourly.get("time", [])
    records = []

    for i, ts in enumerate(times):
        # Derive date and lead_hour from position
        lead_hour = i
        lead_day = i // 24

        date_part = ts[:10] if len(ts) >= 10 else ""

        rec = ForecastHourlyRecord(
            provider="open_meteo",
            data_kind="forecast",
            timestamp=ts,
            local_timestamp=ts,
            date=date_part,
            lead_hour=lead_hour,
            lead_day=lead_day,
            timezone=timezone,
            model_run_time=model_run_time,
            retrieval_time=retrieval_time,
        )

        for om_key, attr in OPEN_METEO_HOURLY_MAP.items():
            values = hourly.get(om_key, [])
            if i < len(values) and values[i] is not None:
                setattr(rec, attr, values[i])

        records.append(rec)

    return records


def normalize_open_meteo_forecast_daily(
    raw_response: Dict[str, Any],
    timezone: str = "UTC",
    model_run_time: Optional[str] = None,
    retrieval_time: Optional[str] = None,
) -> List:
    """Convert Open-Meteo daily forecast response to ForecastDailyRecord list.

    Reuses the daily format from V1, but emits ForecastDailyRecord with lead_day.
    """
    from layer0.environment.weather.forecast_schemas import ForecastDailyRecord

    daily = raw_response.get("daily", {})
    dates = daily.get("time", [])
    records = []

    for i, date in enumerate(dates):
        rec = ForecastDailyRecord(
            provider="open_meteo",
            date=date,
            local_date=date,
            lead_day=i,
            data_kind="forecast",
            timezone=timezone,
            model_run_time=model_run_time,
            retrieval_time=retrieval_time,
            tmin_c=_safe_idx(daily.get("temperature_2m_min", []), i),
            tmax_c=_safe_idx(daily.get("temperature_2m_max", []), i),
            tmean_c=_safe_idx(daily.get("temperature_2m_mean", []), i),
            precipitation_sum_mm=_safe_idx(daily.get("precipitation_sum", []), i),
            rain_sum_mm=_safe_idx(daily.get("rain_sum", []), i),
            et0_sum_mm=_safe_idx(daily.get("et0_fao_evapotranspiration", []), i),
            vpd_max_kpa=_safe_idx(daily.get("vapour_pressure_deficit_max", []), i),
            shortwave_radiation_sum_mj_m2=_safe_idx(
                daily.get("shortwave_radiation_sum", []), i
            ),
            wind_speed_max_10m_ms=_safe_idx(daily.get("windspeed_10m_max", []), i),
            wind_gusts_max_10m_ms=_safe_idx(daily.get("windgusts_10m_max", []), i),
            cloud_cover_mean_pct=_safe_idx(daily.get("cloudcover_mean", []), i),
        )
        records.append(rec)

    return records


def _safe_idx(lst: list, idx: int):
    """Safely index a list, returning None if out of bounds or None."""
    if idx < len(lst):
        return lst[idx]
    return None

