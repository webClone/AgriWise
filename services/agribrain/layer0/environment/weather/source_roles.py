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

    # Resolve *all* declared carriers, including the original envelope.
    # A permissive preferred alias must never conceal a restrictive sibling.
    nodes = [record]
    if isinstance(record, Mapping):
        payload = record.get("payload")
        if isinstance(payload, Mapping):
            nodes.append(payload)

    def values(*keys: str) -> list[Any]:
        found = []
        for node in nodes:
            if isinstance(node, Mapping):
                found.extend(node[key] for key in keys if key in node and node[key] is not None)
            else:
                found.extend(getattr(node, key) for key in keys
                             if getattr(node, key, None) is not None)
        return found

    kinds = [str(x).lower() for x in values("data_kind")]
    if not kinds:
        return "unverified"
    if len(set(kinds)) != 1:
        return "rejected"
    data_kind = kinds[0]
    expected_role = KIND_TO_ROLE.get(data_kind)
    if expected_role is None or expected_role == WeatherSourceRole.UNVERIFIED:
        return "unverified"

    date_values = [str(x)[:10] for x in values("date", "timestamp", "valid_time")]
    if not date_values or len(set(date_values)) != 1:
        return "rejected"
    try:
        if date.fromisoformat(date_values[0]).isoformat() != date_values[0]:
            return "rejected"
    except (TypeError, ValueError):
        return "rejected"

    if any(x is not False for x in values("source_qualified")):
        # This component is never an issuer; even literal True on a nested
        # carrier is an unauthorized source-grant claim.
        return "rejected"

    roles = [str(x).upper() for x in values("source_role", "role", "data_role", "status_role")]
    statuses = [str(x).lower() for x in values("data_status", "status")]
    restricted = {"REJECTED", "EXCLUDED", "UNAVAILABLE", "DENIED"}
    if any(role in restricted for role in roles):
        return "rejected"
    if any(s in ("unavailable", "rejected", "excluded", "denied") for s in statuses):
        return "rejected"
    if data_kind in ("mixed", "unqualified", "rejected"):
        return "rejected"

    observational = {"OBSERVED_STATION", "STATION_OBSERVATION", "HISTORICAL_OBSERVATION", "OBSERVED"}
    if any(r in observational for r in roles) or any(s == "observed" for s in statuses):
        return "unverified"
    if any(r in ("UNVERIFIED", "CURRENT_PROVIDER_CONTEXT") for r in roles):
        return "unverified"
    if any(s in ("unverified", "simulated", "synthetic", "fallback", "proxy", "reconstruction") for s in statuses):
        return "unverified"
    if not roles:
        return "unverified"
    if any(r != expected_role.value for r in roles):
        return "rejected"

    if expected_role in FORECAST_ROLES:
        return "forecast"
    if expected_role in HISTORICAL_CONTEXT_ROLES:
        return "reanalysis_archive"
    return "unverified"
