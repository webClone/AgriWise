"""B2B-07A: exact UTC duration, process-noise rates and degraded weather.

These are UNCALIBRATED structural process-variance priors, not empirical
uncertainty measurements or observation-noise R. Q is variance per day,
NOT standard deviation. No irrigation delivery authority is carried here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
import math
from typing import Any

MAX_TEMPORAL_GAP_DAYS = 30.0
Q_ASSUMPTION_ID = "uncalibrated_structural_prior_v1"

# State order matches state_vector.STATE_NAMES, 9 coordinates.
# Physical meaning: LAI²/day; biomass_proxy²/day; volumetric SM fraction²/day;
# canopy_stress²/day; GDD²/day; stage²/day; thermal_stress²/day;
# photosynthetic_efficiency²/day. All values provisional.
NOMINAL_VARIANCE_RATE_PER_DAY = (
    0.04, 0.02, 0.03, 0.02, 0.03, 1.0, 0.02, 0.02, 0.03,
)
# With missing weather, *do not evolve moisture, temperature, or GDD* using
# invented data. This is an explicit diagonal unforced drift uncertainty
# contract, not the former global "multiply by 5" magic factor.
UNFORCED_DRIFT_VARIANCE_RATE_PER_DAY = (
    0.04, 0.02, 0.06, 0.04, 0.06, 1.0, 0.02, 0.03, 0.045,
)
Q_RATE_UNITS = (
    "LAI^2/day", "biomass_proxy^2/day",
    "soil_moisture_fraction^2/day", "soil_moisture_fraction^2/day",
    "canopy_stress_index^2/day", "GDD^2/day",
    "phenology_stage^2/day", "thermal_stress_index^2/day",
    "photosynthetic_efficiency^2/day",
)


def validate_dt_days(dt_days: float) -> float:
    """Reject zero, negative, NaN, infinity, booleans, or >30-day steps."""
    if (
        isinstance(dt_days, bool) or not isinstance(dt_days, (float, int))
        or not math.isfinite(dt_days)
        or not (0.0 < dt_days <= MAX_TEMPORAL_GAP_DAYS)
    ):
        raise ValueError("invalid temporal gap: require 0 < dt_days <= 30")
    return float(dt_days)


def _timestamp_utc(stamp: Any) -> datetime:
    """ISO day implies 00:00 UTC; ISO time requires explicit timezone."""
    if isinstance(stamp, datetime):
        value = stamp
    elif isinstance(stamp, date):
        value = datetime.combine(stamp, time.min, tzinfo=timezone.utc)
    elif isinstance(stamp, str):
        if len(stamp) == 10:
            try:
                value = datetime.combine(
                    date.fromisoformat(stamp), time.min, tzinfo=timezone.utc,
                )
            except ValueError:
                raise ValueError("invalid ISO temporal stamp") from None
        else:
            try:
                value = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except ValueError:
                raise ValueError("invalid ISO temporal stamp") from None
    else:
        raise ValueError("invalid ISO temporal stamp")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone required for timestamp precision")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class TemporalGapContract:
    previous_utc: datetime
    target_utc: datetime
    dt_days: float

    @classmethod
    def between(cls, previous: Any, target: Any) -> "TemporalGapContract":
        p, t = _timestamp_utc(previous), _timestamp_utc(target)
        duration = validate_dt_days((t - p).total_seconds() / 86400.0)
        return cls(p, t, duration)

    def provenance(self, regime: str, q_variances: list[float]) -> dict[str, Any]:
        return {
            "assumption": Q_ASSUMPTION_ID,
            "time_basis": "utc_elapsed_seconds",
            "previous_utc": self.previous_utc.isoformat(),
            "target_utc": self.target_utc.isoformat(),
            "dt_days": self.dt_days,
            "q_regime": regime,
            "q_units": list(Q_RATE_UNITS),
            "q_variance": list(q_variances),
            "calibrated": False,
        }


def scale_diagonal_variance_rates(
    rates: tuple[float, ...] | list[float], dt_days: float,
) -> list[float]:
    """Constant diffusion-rate discretization, Q_i(dt) = q_rate_i * dt."""
    dt = validate_dt_days(dt_days)
    if len(rates) != len(Q_RATE_UNITS) or any(
        isinstance(r, bool) or not isinstance(r, (int, float))
        or not math.isfinite(r) or r < 0 for r in rates
    ):
        raise ValueError("invalid process variance rate vector")
    values = [r * dt for r in rates]
    if any(not math.isfinite(q) for q in values):
        raise ValueError("nonfinite discretized process covariance")
    return values
