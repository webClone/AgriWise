"""
Layer 1 Temporal Alignment.

Maps evidence items to canonical temporal windows and injects stale flags.

Rules:
- Observations and forecasts are NEVER mixed in the same window
- Forecast evidence is always in forecast_day_N scope
- Historical carry-forward evidence always gets stale flag
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .schemas import EvidenceItem


TEMPORAL_WINDOWS = (
    "instant", "hourly", "daily",
    "7d_trailing", "14d_trailing", "30d_trailing",
    "season_to_date",
    "forecast_day_0", "forecast_day_1", "forecast_day_2",
    "forecast_day_3", "forecast_day_4", "forecast_day_5", "forecast_day_6",
    "crop_stage",
    "static",
)


def assign_temporal_window(
    item: EvidenceItem, run_timestamp: datetime
) -> str:
    """Assign a canonical temporal window to an evidence item."""
    # Forecasts have their own scope
    if item.observation_type == "forecast":
        for flag in item.flags:
            if flag.startswith("FORECAST_DAY_"):
                return f"forecast_{flag.lower().replace('forecast_', '')}"
        return "forecast_day_0"

    # Static priors
    if item.observation_type == "static_prior":
        return "static"

    # Historical carry-forward
    if "HISTORICAL" in item.flags or "STALE" in item.flags:
        return "7d_trailing"  # assigned to trailing window

    # Time-based classification
    if item.observed_at is None:
        return "daily"

    age = run_timestamp - item.observed_at
    if age < timedelta(hours=1):
        return "instant"
    elif age < timedelta(hours=6):
        return "hourly"
    elif age < timedelta(days=1):
        return "daily"
    elif age < timedelta(days=7):
        return "7d_trailing"
    elif age < timedelta(days=14):
        return "14d_trailing"
    elif age < timedelta(days=30):
        return "30d_trailing"
    else:
        return "season_to_date"


def compute_stale_flags(
    items: List[EvidenceItem], run_timestamp: datetime
) -> List[EvidenceItem]:
    """Inject stale flags based on age."""
    for item in items:
        if item.observed_at is None:
            continue
        age = run_timestamp - item.observed_at
        if age > timedelta(days=7) and "STALE" not in item.flags:
            item.flags.append("STALE")
        if age > timedelta(days=30) and "VERY_STALE" not in item.flags:
            item.flags.append("VERY_STALE")
    return items
