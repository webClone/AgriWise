"""B2B-04A: conservative *declared* weather time/source roles.

A role describes the dataset's operational category. It does not attest
who fetched it, cryptographically authenticate a weather provider, validate
a physical station, or issue observation authority. In particular, a
"current" weather-API reading is NOT an independent station measurement.
"""
from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from datetime import date
from typing import Any


class WeatherSourceRole(str, Enum):
    FORECAST_MODEL = "FORECAST_MODEL"
    HISTORICAL_FORECAST_MODEL = "HISTORICAL_FORECAST_MODEL"
    REANALYSIS_MODEL = "REANALYSIS_MODEL"
    CURRENT_PROVIDER_CONTEXT = "CURRENT_PROVIDER_CONTEXT"
    CLIMATOLOGY_MODEL = "CLIMATOLOGY_MODEL"
    UNVERIFIED = "UNVERIFIED"


KIND_TO_ROLE = {
    "forecast": WeatherSourceRole.FORECAST_MODEL,
    "historical_forecast": WeatherSourceRole.HISTORICAL_FORECAST_MODEL,
    "historical_reanalysis": WeatherSourceRole.REANALYSIS_MODEL,
    "current": WeatherSourceRole.CURRENT_PROVIDER_CONTEXT,
    "statistical_climatology": WeatherSourceRole.CLIMATOLOGY_MODEL,
}

HISTORICAL_CONTEXT_ROLES = frozenset({
    WeatherSourceRole.REANALYSIS_MODEL,
})
FORECAST_ROLES = frozenset({
    WeatherSourceRole.FORECAST_MODEL,
    WeatherSourceRole.HISTORICAL_FORECAST_MODEL,
})


def role_for_data_kind(data_kind: Any) -> WeatherSourceRole:
    if not isinstance(data_kind, str):
        return WeatherSourceRole.UNVERIFIED
    return KIND_TO_ROLE.get(data_kind, WeatherSourceRole.UNVERIFIED)


def record_role_is_consistent(record: Any) -> bool:
    """Reject self-asserted source roles that disagree with data_kind.

    Legacy untyped records remain tagged only as *declared* provenance and
    cannot gain sensor-measured or source-authenticated privileges.
    """
    role = role_for_data_kind(getattr(record, "data_kind", None))
    claimed = getattr(record, "source_role", "UNVERIFIED")
    valid_day = getattr(record, "date", None)
    if not isinstance(valid_day, str):
        return False
    try:
        if date.fromisoformat(valid_day).isoformat() != valid_day:
            return False
    except ValueError:
        return False
    return (
        role != WeatherSourceRole.UNVERIFIED
        and isinstance(claimed, str)
        and claimed in ("UNVERIFIED", role.value)
        and getattr(record, "source_qualified", False) is False
    )


def classify_weather_record_admission(record: Any) -> str:
    """Centralized weather admission classifier for Layer 0 wrapper and ASMAE.

    Returns one of:
      - 'reanalysis_archive': valid historical reanalysis model context.
      - 'forecast': valid model forecast.
      - 'unverified': unverified, incomplete, or unauthenticated record.
      - 'rejected': rejected, conflicted, or prohibited record.

    In B2B-04A, 'observed_archive' is strictly prohibited because no independent
    WMO station identity, sensor calibration, or authenticated provider credentials
    exist in Layer 0. String-only claims fail closed to 'unverified'.
    """
    if record is None:
        return "rejected"

    def _get(obj: Any, *keys: str) -> Any:
        if isinstance(obj, Mapping):
            for k in keys:
                if k in obj and obj[k] is not None:
                    return obj[k]
            if "payload" in obj and isinstance(obj["payload"], Mapping):
                for k in keys:
                    if k in obj["payload"] and obj["payload"][k] is not None:
                        return obj["payload"][k]
        else:
            for k in keys:
                if hasattr(obj, k):
                    val = getattr(obj, k)
                    if val is not None:
                        return val
        return None

    data_kind = str(_get(record, "data_kind", "source_reality") or "").lower()
    source_role = str(_get(record, "source_role", "role", "data_role") or "").upper()
    data_status = str(_get(record, "data_status", "status") or "").lower()
    source_qualified = bool(_get(record, "source_qualified") or False)
    date_str = str(_get(record, "date", "timestamp", "valid_time") or "")[:10]

    # 1. Invalid or missing valid date
    if not date_str or len(date_str) != 10:
        return "rejected"

    # 2. Hard fail-closed / rejection / conflict checks
    if (
        source_role in ("REJECTED",)
        or data_kind in ("mixed", "unqualified", "rejected")
        or data_status in ("unavailable", "rejected")
    ):
        return "rejected"

    # 3. Source qualification: B2B-04A does not grant provider qualification credentials.
    # Self-asserted source_qualified=True is an unauthorized authority escalation.
    if source_qualified:
        return "rejected"

    # 4. Observation claims: B2B-04A strictly prohibits string-only or self-asserted
    # station promotion. No authenticated station credentials or WMO calibration exist.
    if (
        data_status == "observed"
        or source_role in ("OBSERVED_STATION", "STATION_OBSERVATION", "HISTORICAL_OBSERVATION")
        or "observed" in data_kind
    ):
        return "unverified"

    # 5. Current provider context is not a daily aggregate or reanalysis archive
    if (
        source_role in ("CURRENT_PROVIDER_CONTEXT", "UNVERIFIED")
        or data_kind in ("current", "unknown", "")
        or data_status in ("unverified",)
    ):
        return "unverified"

    # 6. Explicit role and kind must be present and mutually consistent
    expected_role = KIND_TO_ROLE.get(data_kind)
    if expected_role is None or expected_role == WeatherSourceRole.UNVERIFIED:
        return "unverified"

    if not source_role:
        # A record lacking an explicit source_role cannot be admitted as an archive
        return "unverified"

    if source_role != expected_role.value:
        # Contradictory role and kind (e.g. historical_reanalysis with FORECAST_MODEL)
        # must fail closed and be rejected from ALL archives (historical AND forecast)
        return "rejected"

    # 7. Check for Forecast Model Context
    if expected_role in FORECAST_ROLES:
        if data_status in ("unverified", "unavailable", "rejected"):
            return "unverified"
        return "forecast"

    # 8. Check for Historical Reanalysis Context
    if expected_role in HISTORICAL_CONTEXT_ROLES:
        if data_status in ("unverified", "unavailable", "rejected"):
            return "unverified"
        return "reanalysis_archive"

    return "unverified"
