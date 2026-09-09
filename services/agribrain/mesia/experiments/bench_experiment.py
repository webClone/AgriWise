"""MESIA E0 Instrument Bench Experiment Harness — R6 §10.1 / P8.1.

Executes controlled laboratory bench tests: stepped attenuators, gain sweeps,
temperature chambers, and receiver saturation limits.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class BenchExperimentResult:
    """Outcome of an E0 instrument bench sweep."""

    experiment_id: str
    receiver_id: str
    frequency_hz: float
    attenuation_steps_db: List[float]
    measured_rssi_dbm: List[float]
    measured_noise_figure_db: float
    p1db_compression_point_dbm: float
    is_linear: bool
    executed_at: datetime

    def content_hash(self) -> str:
        d = {
            "experiment_id": self.experiment_id,
            "receiver_id": self.receiver_id,
            "frequency_hz": self.frequency_hz,
            "attenuation_steps_db": self.attenuation_steps_db,
            "measured_rssi_dbm": self.measured_rssi_dbm,
            "measured_noise_figure_db": self.measured_noise_figure_db,
            "p1db_compression_point_dbm": self.p1db_compression_point_dbm,
            "is_linear": self.is_linear,
            "executed_at": self.executed_at.isoformat(),
        }
        raw = json.dumps(d, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class BenchExperimentHarness:
    """Executes E0 instrument laboratory calibration sweeps."""

    @staticmethod
    def run_stepped_attenuation_test(
        receiver_id: str,
        frequency_hz: float,
        input_power_dbm: float = -30.0,
        attenuation_range_db: Tuple[float, float, float] = (0.0, 40.0, 5.0),
    ) -> BenchExperimentResult:
        """Step programmable attenuator and measure linearity."""
        raise NotImplementedError("Physical bench instruments (programmable attenuator) missing.")
