"""MESIA Timing & Clock Characterization — R6 §1.2 & §7.1.

Implements Allan Deviation (ADEV), fractional frequency error, clock drift rate,
phase noise modeling, trigger latency analysis, and time uncertainty bounds.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ClockStabilityReport:
    """Characterization of an oscillator/clock source over multiple integration times tau."""

    clock_id: str
    clock_type: str
    """e.g., 'GPSDO', 'OCXO', 'TCXO', 'RUBIDIUM', 'INTERNAL_RC'."""

    nominal_frequency_hz: float
    evaluated_at: Optional[datetime] = None

    # Allan Deviation points: List of (tau_seconds, adev_value)
    adev_points: List[Tuple[float, float]] = field(default_factory=list)

    frequency_drift_rate_ppm_per_day: Optional[float] = None
    initial_offset_ppm: Optional[float] = None
    time_uncertainty_1s_ns: Optional[float] = None
    time_uncertainty_1hr_ns: Optional[float] = None

    # Quality & Lock Status
    is_disciplined: bool = False
    gnss_lock_valid: bool = False
    max_phase_error_ns: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        for f in self.__dataclass_fields__:
            val = getattr(self, f)
            if isinstance(val, datetime):
                val = val.isoformat()
            elif isinstance(val, (list, tuple)):
                val = [list(x) if isinstance(x, tuple) else x for x in val]
            d[f] = val
        return d

    def content_hash(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def calculate_allan_deviation(
    fractional_freq_series: List[float],
    tau_s: float = 1.0,
) -> float:
    """Calculate the Allan Deviation (ADEV) sigma_y(tau) for an equidistant series
    of fractional frequency errors y_k.

    Formula: sigma_y^2(tau) = 1 / (2 * (N - 1)) * sum( (y_{k+1} - y_k)^2 )
    """
    n = len(fractional_freq_series)
    if n < 2:
        raise ValueError("Allan deviation calculation requires at least 2 fractional frequency samples.")

    diff_sq_sum = sum(
        (fractional_freq_series[k + 1] - fractional_freq_series[k]) ** 2
        for k in range(n - 1)
    )
    allan_var = diff_sq_sum / (2.0 * (n - 1))
    return math.sqrt(allan_var)


def estimate_time_uncertainty_growth(
    initial_sync_uncertainty_ns: float,
    adev_1s: float,
    drift_rate_ppm_per_day: float,
    elapsed_time_s: float,
) -> float:
    """Estimate upper bound on accumulated time uncertainty (in ns) after elapsed_time_s
    without external sync.

    sigma_t(t) = sqrt( sigma_0^2 + (adev * t * 1e9)^2 + (0.5 * drift * (t/86400) * t * 1e9)^2 )
    """
    sigma_0 = initial_sync_uncertainty_ns
    stochastic_growth = adev_1s * elapsed_time_s * 1e9

    days = elapsed_time_s / 86400.0
    drift_fraction = (drift_rate_ppm_per_day * 1e-6)
    deterministic_drift_ns = 0.5 * drift_fraction * days * elapsed_time_s * 1e9

    total_variance = (sigma_0 ** 2) + (stochastic_growth ** 2) + (deterministic_drift_ns ** 2)
    return math.sqrt(total_variance)


@dataclass(frozen=True)
class TriggerLatencyCharacterization:
    """Trigger latency and jitter assessment between trigger signal and first sample."""

    device_id: str
    trigger_type: str
    """e.g., 'HARDWARE_PULSE', 'SOFTWARE_COMMAND', 'PTP_EVENT'."""

    mean_latency_s: float
    jitter_std_s: float
    min_latency_s: float
    max_latency_s: float
    sample_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "trigger_type": self.trigger_type,
            "mean_latency_s": self.mean_latency_s,
            "jitter_std_s": self.jitter_std_s,
            "min_latency_s": self.min_latency_s,
            "max_latency_s": self.max_latency_s,
            "sample_count": self.sample_count,
        }
