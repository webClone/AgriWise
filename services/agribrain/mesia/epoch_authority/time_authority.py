"""MESIA Time Hierarchy, Clock Drift & Uncertainty Authority — R6 §6.1 / P6.1.

Tracks UTC time sources, trigger latencies, Allan-deviation drift models,
and cumulative time uncertainty growth for multi-static and coherent sensing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class TimeSourceType(str, Enum):
    GPSDO_DISCIPLINED = "GPSDO_DISCIPLINED"       # Sub-10 ns uncertainty
    PTP_IEEE1588 = "PTP_IEEE1588"                 # Sub-1 us uncertainty
    NTP_NETWORK = "NTP_NETWORK"                   # ~1-10 ms uncertainty
    FREE_RUNNING_OSCILLATOR = "FREE_RUNNING"      # Drift grows with time


@dataclass(frozen=True)
class TimeQualityReport:
    """Report detailing instantaneous time uncertainty and synchronization status."""

    time_source: TimeSourceType
    utc_timestamp: datetime
    initial_offset_uncertainty_s: float
    time_since_sync_s: float
    allan_deviation: float
    current_time_uncertainty_s: float
    is_synchronized_for_tdoa: bool
    is_synchronized_for_csi: bool


class TimeAuthority:
    """Authority managing time hierarchies and drift propagation."""

    @staticmethod
    def calculate_current_uncertainty(
        time_source: TimeSourceType,
        initial_offset_s: float,
        time_since_sync_s: float,
        allan_deviation: float = 1e-10,
    ) -> float:
        """Propagate cumulative time uncertainty: sigma_t = sigma_0 + Delta_t * sigma_y."""
        if time_source == TimeSourceType.GPSDO_DISCIPLINED:
            # GPSDO continuously disciplines the clock (constant bounded uncertainty)
            return max(initial_offset_s, 10e-9)

        # For free running or intermittent clocks, uncertainty grows linearly with drift rate
        return initial_offset_s + time_since_sync_s * allan_deviation

    @classmethod
    def evaluate_time_quality(
        cls,
        time_source: TimeSourceType,
        utc_timestamp: datetime,
        initial_offset_s: float,
        time_since_sync_s: float,
        allan_deviation: float = 1e-10,
    ) -> TimeQualityReport:
        """Evaluate time synchronization quality against strict sensing thresholds."""
        sigma_t = cls.calculate_current_uncertainty(
            time_source=time_source,
            initial_offset_s=initial_offset_s,
            time_since_sync_s=time_since_sync_s,
            allan_deviation=allan_deviation,
        )

        # TDoA requires sub-microsecond timing (< 1 us)
        is_tdoa_ok = sigma_t <= 1e-6
        # CSI sensing requires stable frame intervals (< 1 ms)
        is_csi_ok = sigma_t <= 1e-3

        return TimeQualityReport(
            time_source=time_source,
            utc_timestamp=utc_timestamp,
            initial_offset_uncertainty_s=initial_offset_s,
            time_since_sync_s=time_since_sync_s,
            allan_deviation=allan_deviation,
            current_time_uncertainty_s=sigma_t,
            is_synchronized_for_tdoa=is_tdoa_ok,
            is_synchronized_for_csi=is_csi_ok,
        )
