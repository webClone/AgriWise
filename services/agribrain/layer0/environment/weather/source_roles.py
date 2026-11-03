"""B2B-04A: conservative *declared* weather time/source roles.

A role describes the dataset's operational category. It does not attest
who fetched it, cryptographically authenticate a weather provider, validate
a physical station, or issue observation authority. In particular, a
"current" weather-API reading is NOT an independent station measurement.
"""
from __future__ import annotations

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

# A retrospective model forecast, future model forecast and climatological
# baseline must not be represented as past/reanalysis weather forcing.
HISTORICAL_CONTEXT_ROLES = frozenset({
    WeatherSourceRole.REANALYSIS_MODEL,
    WeatherSourceRole.CURRENT_PROVIDER_CONTEXT,
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
