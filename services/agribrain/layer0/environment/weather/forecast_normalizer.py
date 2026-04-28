"""
Forecast Normalizer.

Combines hourly/daily forecast records from multiple providers,
validates the 7-day horizon cap, and computes staleness.

Convention:
  - Forecast horizon = 7 calendar dates (lead_day 0..6)
  - >7 days rejected or trimmed in V1.1
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from layer0.environment.weather.forecast_schemas import (
    ForecastDailyRecord,
    ForecastHourlyRecord,
    ForecastTimeSeries,
    MAX_FORECAST_HORIZON_V11,
    MAX_FORECAST_HOURS_V11,
    STALENESS_WARNING_HOURS,
    STALENESS_DEGRADE_HOURS,
    STALENESS_UNUSABLE_HOURS,
)


def build_forecast_timeseries(
    hourly_records: Optional[List[ForecastHourlyRecord]] = None,
    daily_records: Optional[List[ForecastDailyRecord]] = None,
    timezone_str: str = "UTC",
    model_run_time: Optional[str] = None,
    retrieval_time: Optional[str] = None,
) -> ForecastTimeSeries:
    """Build a ForecastTimeSeries from normalized provider records.

    Trims to 7-day horizon. Computes staleness.
    """
    hourly = trim_hourly_to_horizon(hourly_records or [])
    daily = trim_daily_to_horizon(daily_records or [])

    # Compute date range from daily (or hourly dates)
    all_dates = sorted(set(
        [r.date for r in daily if r.date] +
        [r.date for r in hourly if r.date]
    ))

    providers = sorted(set(
        [r.provider for r in hourly if r.provider] +
        [r.provider for r in daily if r.provider]
    ))

    horizon = len(all_dates)
    lead_day_min = 0
    lead_day_max = max(
        [r.lead_day for r in daily] + [r.lead_day for r in hourly] + [0]
    )

    # Staleness (Revision 5)
    age_hours = None
    stale = False
    if retrieval_time:
        age_hours = _compute_age_hours(retrieval_time)
        stale = age_hours is not None and age_hours > STALENESS_WARNING_HOURS

    return ForecastTimeSeries(
        hourly_records=hourly,
        daily_records=daily,
        horizon_calendar_days=horizon,
        lead_day_range=[lead_day_min, min(lead_day_max, MAX_FORECAST_HORIZON_V11 - 1)],
        date_range_start=all_dates[0] if all_dates else "",
        date_range_end=all_dates[-1] if all_dates else "",
        hourly_count=len(hourly),
        daily_count=len(daily),
        providers=providers,
        timezone=timezone_str,
        model_run_time=model_run_time,
        retrieval_time=retrieval_time,
        forecast_age_hours=age_hours,
        stale_forecast_flag=stale,
    )


def validate_forecast_horizon(
    daily_records: List[ForecastDailyRecord],
) -> Tuple[bool, List[str]]:
    """Validate forecast horizon. Returns (valid, warnings).

    >7 days: rejected in V1.1.
    0 days: warning.
    """
    warnings: List[str] = []

    if not daily_records:
        return True, ["NO_FORECAST_DATA"]

    max_lead = max(r.lead_day for r in daily_records)
    unique_dates = len(set(r.date for r in daily_records if r.date))

    if max_lead >= MAX_FORECAST_HORIZON_V11:
        return False, [f"FORECAST_EXCEEDS_V11_HORIZON: lead_day={max_lead} > {MAX_FORECAST_HORIZON_V11 - 1}"]

    if unique_dates > MAX_FORECAST_HORIZON_V11:
        return False, [f"FORECAST_TOO_MANY_DATES: {unique_dates} > {MAX_FORECAST_HORIZON_V11}"]

    return True, warnings


def validate_forecast_hourly_horizon(
    hourly_records: List[ForecastHourlyRecord],
) -> Tuple[bool, List[str]]:
    """Validate hourly forecast horizon. Returns (valid, warnings).

    >168 hours (lead_hour >= 168): rejected in V1.1.
    >7 unique local dates: rejected in V1.1.
    0 records: warning only (not invalid — hourly data is optional).
    """
    warnings: List[str] = []

    if not hourly_records:
        return True, ["NO_HOURLY_FORECAST_DATA"]

    max_lead = max(r.lead_hour for r in hourly_records)
    unique_dates = len(set(r.date for r in hourly_records if r.date))

    if max_lead >= MAX_FORECAST_HOURS_V11:
        return False, [
            f"HOURLY_FORECAST_EXCEEDS_V11_HORIZON: lead_hour={max_lead} >= {MAX_FORECAST_HOURS_V11}"
        ]

    if unique_dates > MAX_FORECAST_HORIZON_V11:
        return False, [
            f"HOURLY_FORECAST_TOO_MANY_DATES: {unique_dates} > {MAX_FORECAST_HORIZON_V11}"
        ]

    return True, warnings


def trim_daily_to_horizon(
    records: List[ForecastDailyRecord],
    max_days: int = MAX_FORECAST_HORIZON_V11,
) -> List[ForecastDailyRecord]:
    """Trim daily records to max horizon days."""
    return [r for r in records if r.lead_day < max_days]


def trim_hourly_to_horizon(
    records: List[ForecastHourlyRecord],
    max_hours: int = MAX_FORECAST_HOURS_V11,
) -> List[ForecastHourlyRecord]:
    """Trim hourly records to max horizon hours."""
    return [r for r in records if r.lead_hour < max_hours]


def _compute_age_hours(retrieval_time_iso: str) -> Optional[float]:
    """Compute forecast age in hours from retrieval time."""
    try:
        rt = datetime.fromisoformat(retrieval_time_iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = (now - rt).total_seconds() / 3600.0
        return round(delta, 2)
    except (ValueError, TypeError):
        return None
