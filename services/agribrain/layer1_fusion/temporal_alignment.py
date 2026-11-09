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


from common.time_utils import ensure_utc


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

    rt_utc = ensure_utc(run_timestamp)
    obs_utc = ensure_utc(item.observed_at)
    age = rt_utc - obs_utc
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
    rt_utc = ensure_utc(run_timestamp)
    for item in items:
        if item.observed_at is None:
            continue
        obs_utc = ensure_utc(item.observed_at)
        age = rt_utc - obs_utc
        if age > timedelta(days=7) and "STALE" not in item.flags:
            item.flags.append("STALE")
        if age > timedelta(days=30) and "VERY_STALE" not in item.flags:
            item.flags.append("VERY_STALE")
    return items


def is_available_at_cutoff(
    item: EvidenceItem,
    as_of_cutoff: datetime,
) -> Tuple[bool, str]:
    """Check if evidence item was available to the decision system at as_of_cutoff (SPEC-B/T23-T25)."""
    cutoff_utc = ensure_utc(as_of_cutoff)

    # 1. Check publication/recorded/ingested time
    pub_time = getattr(item, "published_at", None) or getattr(item, "recorded_at", None)
    if pub_time is not None:
        if ensure_utc(pub_time) > cutoff_utc:
            return False, f"PUBLISHED_AFTER_CUTOFF: published {pub_time} > cutoff {cutoff_utc}"

    for f in item.flags:
        if f.startswith("PUBLISHED_AT:"):
            try:
                p_dt = datetime.fromisoformat(f.split(":", 1)[1])
                if ensure_utc(p_dt) > cutoff_utc:
                    return False, f"PUBLISHED_AFTER_CUTOFF: {p_dt} > {cutoff_utc}"
            except Exception:
                pass
        elif f.startswith("RECORDED_AT:"):
            try:
                r_dt = datetime.fromisoformat(f.split(":", 1)[1])
                if ensure_utc(r_dt) > cutoff_utc:
                    return False, f"RECORDED_AFTER_CUTOFF: {r_dt} > {cutoff_utc}"
            except Exception:
                pass
        elif f.startswith("ISSUED_AT:"):
            try:
                i_dt = datetime.fromisoformat(f.split(":", 1)[1])
                if ensure_utc(i_dt) > cutoff_utc:
                    return False, f"FORECAST_ISSUED_AFTER_CUTOFF: {i_dt} > {cutoff_utc}"
            except Exception:
                pass

    # 2. Check future observation time relative to cutoff
    if item.observed_at is not None:
        obs_utc = ensure_utc(item.observed_at)
        if obs_utc > cutoff_utc + timedelta(minutes=5):
            return False, f"OBSERVED_AFTER_CUTOFF: observed {obs_utc} > cutoff {cutoff_utc}"

    return True, "available"
