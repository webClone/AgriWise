"""
OpenWeather Provider Adapter.

Normalizes OpenWeather API responses to common WeatherDailyRecord.
V1: accepts pre-fetched/mocked JSON. No live API calls.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from layer0.environment.weather.schemas import WeatherDailyRecord


def normalize_openweather_daily(
    raw_response: Dict[str, Any],
    data_kind: str = "current",
    retrieval_time: Optional[str] = None,
) -> List[WeatherDailyRecord]:
    """Convert OpenWeather response to list of WeatherDailyRecord.

    Handles both current weather and daily forecast formats.

    Expected format (daily):
    {
        "daily": [
            {
                "dt": 1714089600,
                "temp": {"min": 8.5, "max": 22.3, "day": 15.4},
                "humidity": 65,
                "pressure": 1013,
                "wind_speed": 5.2,
                "wind_gust": 8.1,
                "clouds": 40,
                "rain": 0.5,
                "weather": [{"id": 500, "main": "Rain"}]
            },
            ...
        ]
    }
    """
    daily_list = raw_response.get("daily", [])

    # Handle single current weather as a list of one
    if not daily_list and "main" in raw_response:
        daily_list = [_current_to_daily(raw_response)]

    records: List[WeatherDailyRecord] = []

    for day_data in daily_list:
        date = day_data.get("date", "")
        temp = day_data.get("temp", {})

        # Temperature: OpenWeather sometimes uses Kelvin
        temp_min = temp.get("min") if isinstance(temp, dict) else None
        temp_max = temp.get("max") if isinstance(temp, dict) else None
        temp_mean = temp.get("day") if isinstance(temp, dict) else None

        # Convert from Kelvin if values look like Kelvin
        if temp_min is not None and temp_min > 100:
            temp_min -= 273.15
        if temp_max is not None and temp_max > 100:
            temp_max -= 273.15
        if temp_mean is not None and temp_mean > 100:
            temp_mean -= 273.15

        rec = WeatherDailyRecord(
            date=date,
            provider="openweather",
            data_kind=data_kind,
            retrieval_time=retrieval_time,
            temp_min=round(temp_min, 2) if temp_min is not None else None,
            temp_max=round(temp_max, 2) if temp_max is not None else None,
            temp_mean=round(temp_mean, 2) if temp_mean is not None else None,
            precipitation_sum=day_data.get("rain", day_data.get("precipitation", None)),
            relative_humidity_mean=day_data.get("humidity"),
            surface_pressure_mean=day_data.get("pressure"),
            wind_speed_max=day_data.get("wind_speed"),
            wind_gusts_max=day_data.get("wind_gust"),
            cloud_cover_mean=day_data.get("clouds"),
        )
        records.append(rec)

    return records


def _current_to_daily(current: Dict[str, Any]) -> Dict[str, Any]:
    """Convert OpenWeather current-weather response to daily-like dict."""
    main = current.get("main", {})
    wind = current.get("wind", {})
    clouds = current.get("clouds", {})
    rain = current.get("rain", {})

    return {
        "date": current.get("date", ""),
        "temp": {
            "min": main.get("temp_min"),
            "max": main.get("temp_max"),
            "day": main.get("temp"),
        },
        "humidity": main.get("humidity"),
        "pressure": main.get("pressure"),
        "wind_speed": wind.get("speed"),
        "wind_gust": wind.get("gust"),
        "clouds": clouds.get("all"),
        "rain": rain.get("1h", rain.get("3h", 0)),
    }


# ---------------------------------------------------------------------------
# V1.1 Forecast Normalization
# ---------------------------------------------------------------------------

# OpenWeather hourly: only 0-48h (Revision 2)
OPENWEATHER_MAX_HOURLY_HOURS = 48


def normalize_openweather_forecast_daily(
    raw_response: Dict[str, Any],
    max_days: int = 7,
    timezone: str = "UTC",
    model_run_time: Optional[str] = None,
    retrieval_time: Optional[str] = None,
) -> List:
    """Convert OpenWeather One Call 3.0 daily forecast to ForecastDailyRecord list.

    OpenWeather provides up to 8 daily forecasts; we trim to max_days (default 7).
    """
    from layer0.environment.weather.forecast_schemas import ForecastDailyRecord

    daily_list = raw_response.get("daily", [])
    records = []

    for i, day_data in enumerate(daily_list[:max_days]):
        date = day_data.get("date", "")
        temp = day_data.get("temp", {})

        tmin = temp.get("min") if isinstance(temp, dict) else None
        tmax = temp.get("max") if isinstance(temp, dict) else None
        tmean = temp.get("day") if isinstance(temp, dict) else None

        # Kelvin→Celsius
        if tmin is not None and tmin > 100:
            tmin -= 273.15
        if tmax is not None and tmax > 100:
            tmax -= 273.15
        if tmean is not None and tmean > 100:
            tmean -= 273.15

        rec = ForecastDailyRecord(
            provider="openweather",
            date=date,
            local_date=date,
            lead_day=i,
            data_kind="forecast",
            timezone=timezone,
            model_run_time=model_run_time,
            retrieval_time=retrieval_time,
            tmin_c=round(tmin, 2) if tmin is not None else None,
            tmax_c=round(tmax, 2) if tmax is not None else None,
            tmean_c=round(tmean, 2) if tmean is not None else None,
            precipitation_sum_mm=day_data.get("rain", day_data.get("precipitation")),
            precipitation_probability_max_pct=day_data.get("pop"),
            wind_speed_max_10m_ms=day_data.get("wind_speed"),
            wind_gusts_max_10m_ms=day_data.get("wind_gust"),
            dominant_wind_direction_deg=day_data.get("wind_deg"),
            cloud_cover_mean_pct=day_data.get("clouds"),
        )
        records.append(rec)

    return records


def normalize_openweather_forecast_hourly(
    raw_response: Dict[str, Any],
    timezone: str = "UTC",
    model_run_time: Optional[str] = None,
    retrieval_time: Optional[str] = None,
) -> List:
    """Convert OpenWeather One Call 3.0 hourly forecast to ForecastHourlyRecord list.

    OpenWeather provides only 48 hourly records.
    Missing hourly after 48h must NOT count as provider failure (Revision 2).
    """
    from layer0.environment.weather.forecast_schemas import ForecastHourlyRecord

    hourly_list = raw_response.get("hourly", [])
    records = []

    for i, hour_data in enumerate(hourly_list[:OPENWEATHER_MAX_HOURLY_HOURS]):
        ts = hour_data.get("timestamp", hour_data.get("dt", ""))
        date = hour_data.get("date", str(ts)[:10] if ts else "")

        main = hour_data.get("main", {})
        wind = hour_data.get("wind", {})
        clouds = hour_data.get("clouds", {})
        rain = hour_data.get("rain", {})

        temp = main.get("temp")
        if temp is not None and temp > 100:
            temp -= 273.15

        rec = ForecastHourlyRecord(
            provider="openweather",
            data_kind="forecast",
            timestamp=str(ts),
            local_timestamp=str(ts),
            date=date,
            lead_hour=i,
            lead_day=i // 24,
            timezone=timezone,
            model_run_time=model_run_time,
            retrieval_time=retrieval_time,
            temperature_2m_c=round(temp, 2) if temp is not None else None,
            relative_humidity_2m_pct=main.get("humidity"),
            precipitation_mm=rain.get("1h", 0),
            precipitation_probability_pct=hour_data.get("pop"),
            cloud_cover_pct=clouds.get("all") if isinstance(clouds, dict) else clouds,
            wind_speed_10m_ms=wind.get("speed"),
            wind_direction_10m_deg=wind.get("deg"),
            wind_gusts_10m_ms=wind.get("gust"),
            surface_pressure_hpa=main.get("pressure"),
        )
        records.append(rec)

    return records
