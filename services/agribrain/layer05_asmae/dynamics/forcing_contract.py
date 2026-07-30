"""R5.0: Forcing series contract.

Design rules:
  1. Weather and management enter the transition model as exogenous forcing,
     NOT as observations in the measurement vector.
  2. ForcingSeriesRef identifies the complete forcing path for an interval.
  3. Missing intervals widen uncertainty — they do NOT create hidden
     default observations.
  4. This contract is frozen in R5.0. R5.1 connects it to the temporal engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Tuple


@dataclass(frozen=True)
class TimeInterval:
    """A contiguous time interval [start, end)."""
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError(
                f"TimeInterval end ({self.end}) must be after start ({self.start})"
            )

    @property
    def duration(self) -> timedelta:
        return self.end - self.start


@dataclass(frozen=True)
class ForcingSeriesRef:
    """Immutable reference to the forcing series consumed by a forecast.

    Identifies the complete weather and management path for an integration
    interval. Every forcing series used in a forecast or assimilation run
    must be identifiable and reproducible.

    The R5.1 temporal engine will integrate over every timestep in this
    series rather than using endpoint weather × delta_days.
    """
    start_time: datetime
    end_time: datetime
    timestep: timedelta

    # Content identity
    weather_series_hash: str
    management_event_ids: Tuple[str, ...] = ()

    # Coverage assessment
    missing_intervals: Tuple[TimeInterval, ...] = ()
    prior_intervals: Tuple[TimeInterval, ...] = ()

    # Source provenance
    weather_source: str = ""
    weather_source_resolution: str = ""

    def has_gaps(self) -> bool:
        """Whether the forcing series has missing data."""
        return len(self.missing_intervals) > 0

    @property
    def n_timesteps(self) -> int:
        """Number of integration timesteps."""
        if self.timestep.total_seconds() <= 0:
            return 0
        total = (self.end_time - self.start_time).total_seconds()
        return max(0, int(total / self.timestep.total_seconds()))

    def validate(self) -> None:
        """Check forcing series invariants."""
        if self.end_time <= self.start_time:
            raise ValueError(
                f"end_time ({self.end_time}) must be after "
                f"start_time ({self.start_time})"
            )
        if self.timestep.total_seconds() <= 0:
            raise ValueError(
                f"timestep must be positive: {self.timestep}"
            )
        if not self.weather_series_hash:
            raise ValueError("weather_series_hash is required")
