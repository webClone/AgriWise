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
    is_historical_replay: bool = False,
) -> Tuple[bool, str]:
    """Check if evidence item was available to the decision system at as_of_cutoff (SPEC-B/T23-T25)."""
    cutoff_utc = ensure_utc(as_of_cutoff)

    # 1. Check publication/recorded/ingested time and first_available_at (RC2)
    pub_times: List[datetime] = []
    
    # Direct attributes
    for attr in ("published_at", "recorded_at", "ingested_at", "first_available_at"):
        val = getattr(item, attr, None)
        if val is not None:
            if isinstance(val, str):
                try:
                    dt = ensure_utc(datetime.fromisoformat(val))
                    pub_times.append(dt)
                    if dt > cutoff_utc and attr == "first_available_at":
                        return False, f"FIRST_AVAILABLE_AFTER_CUTOFF: {attr} {dt} > cutoff {cutoff_utc}"
                except Exception:
                    return False, f"MALFORMED_PUBLICATION_TIMESTAMP: malformed {attr} '{val}'"
            elif isinstance(val, datetime):
                dt = ensure_utc(val)
                pub_times.append(dt)
                if dt > cutoff_utc and attr == "first_available_at":
                    return False, f"FIRST_AVAILABLE_AFTER_CUTOFF: {attr} {dt} > cutoff {cutoff_utc}"

    # Also check signed receipt first_available_at (RC2: exact revision & publication binding)
    rcpt = getattr(item, "receipt", None)
    if rcpt is not None:
        rcpt_fa = getattr(rcpt, "first_available_at", None)
        if rcpt_fa:
            try:
                fa_dt = ensure_utc(datetime.fromisoformat(str(rcpt_fa)))
                pub_times.append(fa_dt)
                if fa_dt > cutoff_utc:
                    return False, f"FIRST_AVAILABLE_AFTER_CUTOFF: signed receipt first_available_at {fa_dt} > cutoff {cutoff_utc}"
            except Exception:
                return False, f"MALFORMED_FIRST_AVAILABLE_AT: malformed receipt first_available_at '{rcpt_fa}'"

        # Check content digest binding on sensor receipt
        rcpt_digest = getattr(rcpt, "content_digest", None)
        item_digest = getattr(item, "content_hash", None)
        if rcpt_digest and item_digest and str(rcpt_digest).strip() != str(item_digest).strip():
            return False, f"MISMATCHED_SENSOR_RECEIPT_DIGEST: receipt digest {rcpt_digest} != measurement digest {item_digest}"

    # Also check publication receipt content hash binding
    pub_rcpt = getattr(item, "publication_receipt", None)
    if pub_rcpt is None and rcpt is not None and hasattr(rcpt, "source_family") and getattr(rcpt, "source_family", "") != "sensor":
        pub_rcpt = rcpt
    if pub_rcpt is not None:
        pub_hash = getattr(pub_rcpt, "content_hash", None)
        item_digest = getattr(item, "content_hash", None)
        if pub_hash and item_digest and str(pub_hash).strip() != str(item_digest).strip():
            return False, f"MISMATCHED_PUBLICATION_RECEIPT_DIGEST: publication receipt hash {pub_hash} != measurement digest {item_digest}"

    # Parse flags with strict validation (L1-R7-04 / R7-G04, R9-03, RC2)
    v_pub = getattr(item, "verified_published_at", None)
    if v_pub is not None:
        v_dt = ensure_utc(v_pub)
        pub_times.append(v_dt)

    has_pub_flag = len(pub_times) > 0
    for f in item.flags:
        if f.startswith("PUBLISHED_AT:"):
            raw_str = f.split(":", 1)[1].strip()
            try:
                p_dt = ensure_utc(datetime.fromisoformat(raw_str))
                pub_times.append(p_dt)
                has_pub_flag = True
            except Exception:
                return False, f"MALFORMED_PUBLICATION_TIMESTAMP: malformed published_at in flag '{f}'"
        elif f.startswith("FIRST_AVAILABLE_AT:"):
            raw_str = f.split(":", 1)[1].strip()
            try:
                fa_dt = ensure_utc(datetime.fromisoformat(raw_str))
                pub_times.append(fa_dt)
                has_pub_flag = True
                if fa_dt > cutoff_utc:
                    return False, f"FIRST_AVAILABLE_AFTER_CUTOFF: first available {fa_dt} > cutoff {cutoff_utc}"
            except Exception:
                return False, f"MALFORMED_PUBLICATION_TIMESTAMP: malformed first_available_at in flag '{f}'"
        elif f.startswith("RECORDED_AT:"):
            raw_str = f.split(":", 1)[1].strip()
            try:
                r_dt = ensure_utc(datetime.fromisoformat(raw_str))
                pub_times.append(r_dt)
                has_pub_flag = True
            except Exception:
                return False, f"MALFORMED_PUBLICATION_TIMESTAMP: malformed recorded_at in flag '{f}'"
        elif f.startswith("ISSUED_AT:"):
            raw_str = f.split(":", 1)[1].strip()
            try:
                i_dt = ensure_utc(datetime.fromisoformat(raw_str))
                if i_dt > cutoff_utc:
                    return False, f"FORECAST_ISSUED_AFTER_CUTOFF: {i_dt} > {cutoff_utc}"
                pub_times.append(i_dt)
                has_pub_flag = True
            except Exception:
                return False, f"MALFORMED_PUBLICATION_TIMESTAMP: malformed issued_at in flag '{f}'"

    # If any verified publication/recorded time is after cutoff, exclude! (L1-R7-03 / R7-G06)
    for p_dt in pub_times:
        if p_dt > cutoff_utc:
            return False, f"PUBLISHED_AFTER_CUTOFF: published {p_dt} > cutoff {cutoff_utc}"

    # Check future observation time relative to cutoff (physical causality)
    # R8-06 / R8-G08: Enforce zero clock-skew tolerance on historical replay; live streaming retains 5-minute tolerance
    is_replay = (
        is_historical_replay
        or "REQUIRES_PUBLICATION_VERIFICATION" in item.flags
        or "HISTORICAL_REPLAY" in item.flags
        or ("HISTORICAL" in item.flags and item.source_family in ("sentinel2", "sentinel1", "sentinel5p", "weather_reanalysis", "asmae"))
    )
    if item.observed_at is not None:
        obs_utc = ensure_utc(item.observed_at)
        skew_tolerance = timedelta(0) if is_replay else timedelta(minutes=5)
        if obs_utc > cutoff_utc + skew_tolerance:
            return False, f"OBSERVED_AFTER_CUTOFF: observed {obs_utc} > cutoff {cutoff_utc}"

    # SPEC-B / L1-R7-05 / R7-G05 / R8-02 / R9-03: Historical replay mode verification
    # Static priors are exempt from publication verification; dynamic observations are subject to it
    is_static_prior = item.source_family in ("geo_context", "static_soil")
    
    if is_replay and not is_static_prior:
        is_pub_verified = getattr(item, "publication_receipt_verified", False)
        is_sensor_verified = bool(
            (item.source_family == "sensor" or getattr(item, "truth_class", None) in ("observed_sensor", "unverified_sensor"))
            and getattr(item, "receipt", None) is not None
            and getattr(item, "truth_class", None) == "observed_sensor"
        )
        
        if is_sensor_verified:
            # P1 Historical Replay: Authenticated availability required for historical state authority
            # Measurement authenticity (signed by authority) != Historical availability (available before cutoff).
            has_auth_availability = False
            
            # Check 1: Sensor receipt with first_available_at <= cutoff
            if rcpt is not None and getattr(rcpt, "first_available_at", None):
                try:
                    fa_dt = ensure_utc(datetime.fromisoformat(str(rcpt.first_available_at)))
                    if fa_dt <= cutoff_utc:
                        has_auth_availability = True
                    else:
                        return False, f"FIRST_AVAILABLE_AFTER_CUTOFF: signed receipt first_available_at {fa_dt} > cutoff {cutoff_utc}"
                except Exception:
                    return False, f"MALFORMED_FIRST_AVAILABLE_AT: malformed receipt first_available_at '{rcpt.first_available_at}'"
            
            # Check 2: Exact-content publication receipt with published_at <= cutoff
            # S01: Prohibit unhashed sensor receipts from asserting historical availability evidence.
            # Exact matching content digest required between publication receipt and measurement.
            item_digest = getattr(item, "content_hash", None) or (getattr(rcpt, "content_digest", None) if rcpt is not None else None)
            pub_hash = getattr(pub_rcpt, "content_hash", None) if pub_rcpt is not None else None

            has_matching_content_hash = bool(
                pub_hash and str(pub_hash).strip()
                and item_digest and str(item_digest).strip()
                and str(pub_hash).strip() == str(item_digest).strip()
            )

            if has_matching_content_hash and getattr(item, "publication_receipt_verified", False):
                v_published = getattr(item, "verified_published_at", None)
                if v_published is None and pub_rcpt is not None:
                    v_published = getattr(pub_rcpt, "published_at", None)
                if v_published is not None:
                    try:
                        p_dt = ensure_utc(v_published if isinstance(v_published, datetime) else datetime.fromisoformat(str(v_published)))
                        if p_dt <= cutoff_utc:
                            has_auth_availability = True
                        else:
                            return False, f"PUBLISHED_AFTER_CUTOFF: publication receipt published_at {p_dt} > cutoff {cutoff_utc}"
                    except Exception:
                        return False, f"MALFORMED_PUBLICATION_TIMESTAMP: malformed publication timestamp '{v_published}'"

            if not has_auth_availability:
                # Signed sensor without authenticated first-availability timestamp <= cutoff.
                # Must be diagnostic-only on historical replay: deny historical state update and Layer 2 influence.
                item.state_update_allowed = False
                item.diagnostic_only = True
                if "NO_AUTHENTICATED_AVAILABILITY_ON_HISTORICAL_REPLAY" not in item.flags:
                    item.flags.append("NO_AUTHENTICATED_AVAILABILITY_ON_HISTORICAL_REPLAY")
                return True, "admitted_diagnostic_only_no_availability_proof"

            return True, "available_authenticated_sensor"

        # Non-sensor dynamic observations or unverified sensors require verified publication timestamp
        if "CALLER_CLAIMED_PUBLICATION_TIME" in item.flags and not is_pub_verified:
            return False, "CALLER_CLAIMED_PUBLICATION_TIME_REJECTED: caller asserted publication availability without verified receipt proof on historical replay"
        if not is_pub_verified or not has_pub_flag:
            return False, "UNVERIFIED_PUBLICATION_TIME_ON_HISTORICAL_REPLAY: missing verified publication or recording timestamp"

    return True, "available"
