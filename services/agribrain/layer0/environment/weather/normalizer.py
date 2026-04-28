"""
Weather Normalizer.

Common normalization for all weather providers: timezone alignment,
unit validation, temporal completeness checking.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from layer0.environment.weather.schemas import WeatherDailyRecord, WeatherTimeSeries


def build_weather_timeseries(
    records: List[WeatherDailyRecord],
    timezone: str = "UTC",
) -> WeatherTimeSeries:
    """Build a WeatherTimeSeries from normalized daily records.

    Groups by provider, computes window metadata.
    """
    if not records:
        return WeatherTimeSeries(timezone=timezone)

    dates = sorted(set(r.date for r in records if r.date))
    providers = sorted(set(r.provider for r in records if r.provider))

    # Count historical vs forecast
    historical_dates = {
        r.date for r in records
        if r.data_kind in ("current", "historical_reanalysis", "historical_forecast")
    }
    forecast_dates = {
        r.date for r in records
        if r.data_kind == "forecast"
    }

    historical = len(historical_dates)
    forecast = len(forecast_dates)

    return WeatherTimeSeries(
        daily_records=records,
        window_start=dates[0] if dates else "",
        window_end=dates[-1] if dates else "",
        historical_days=historical,
        forecast_days=forecast,
        timezone=timezone,
        providers=providers,
    )


def check_temporal_completeness(
    records: List[WeatherDailyRecord],
    expected_dates: List[str],
) -> float:
    """Check what fraction of expected dates have records."""
    if not expected_dates:
        return 0.0
    present = set(r.date for r in records)
    covered = sum(1 for d in expected_dates if d in present)
    return covered / len(expected_dates)


def validate_weather_record(record: WeatherDailyRecord) -> List[str]:
    """Validate a single weather record. Returns list of issues."""
    issues = []

    if not record.date:
        issues.append("missing_date")
    if not record.provider:
        issues.append("missing_provider")

    # Temperature sanity
    if record.temp_min is not None and record.temp_max is not None:
        if record.temp_min > record.temp_max:
            issues.append("temp_min_exceeds_temp_max")

    if record.temp_max is not None and record.temp_max > 60:
        issues.append("temp_max_implausible")
    if record.temp_min is not None and record.temp_min < -80:
        issues.append("temp_min_implausible")

    # Precipitation sanity
    if record.precipitation_sum is not None and record.precipitation_sum < 0:
        issues.append("negative_precipitation")

    # ET₀ sanity
    if record.et0_mm is not None and record.et0_mm < 0:
        issues.append("negative_et0")

    return issues
