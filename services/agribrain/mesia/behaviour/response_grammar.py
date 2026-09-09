"""MESIA Agricultural Response Grammar & Causality Engine — R6 §9.5 / P7.5.

Validates temporal state sequences (wetting, drying, diurnal transpiration,
rainfall pulses) against agronomic physical causality and rate-of-change limits.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class AgriculturalRegime(str, Enum):
    STEADY_STATE = "STEADY_STATE"
    IRRIGATION_PULSE = "IRRIGATION_PULSE"
    POST_IRRIGATION_DRYING = "POST_IRRIGATION_DRYING"
    DIURNAL_TRANSPIRATION = "DIURNAL_TRANSPIRATION"
    CANOPY_DEW_EVENT = "CANOPY_DEW_EVENT"
    RAINFALL_INFILTRATION = "RAINFALL_INFILTRATION"
    PHYSICAL_ANOMALY = "PHYSICAL_ANOMALY"


@dataclass(frozen=True)
class GrammarValidationResult:
    """Outcome of validating a temporal signal trajectory against the response grammar."""

    current_regime: AgriculturalRegime
    is_physically_plausible: bool
    rate_of_change_db_per_hour: float
    violations: List[str]


class ResponseGrammarEngine:
    """Enforces physical causality rules across time-series radio responses."""

    # Maximum plausible agronomic drying rate (~2% VWC per hour in Mediterranean heat)
    MAX_DRYING_RATE_DB_PER_HOUR = 3.0
    # Maximum instantaneous pulse rate
    MAX_IRRIGATION_PULSE_RATE_DB_PER_HOUR = 25.0

    @classmethod
    def validate_trajectory_step(
        cls,
        previous_signal_db: float,
        current_signal_db: float,
        delta_time_hours: float,
        is_irrigation_active: bool = False,
        is_raining: bool = False,
    ) -> GrammarValidationResult:
        """Validate whether the signal change matches a valid agricultural response pattern."""
        violations: List[str] = []
        if delta_time_hours <= 0:
            return GrammarValidationResult(
                current_regime=AgriculturalRegime.STEADY_STATE,
                is_physically_plausible=True,
                rate_of_change_db_per_hour=0.0,
                violations=[],
            )

        rate = (current_signal_db - previous_signal_db) / delta_time_hours
        abs_rate = abs(rate)

        regime = AgriculturalRegime.STEADY_STATE

        if is_raining:
            regime = AgriculturalRegime.RAINFALL_INFILTRATION
        elif is_irrigation_active:
            regime = AgriculturalRegime.IRRIGATION_PULSE
        elif rate < 0:
            regime = AgriculturalRegime.POST_IRRIGATION_DRYING
            if abs_rate > cls.MAX_DRYING_RATE_DB_PER_HOUR:
                violations.append(
                    f"Drying rate {abs_rate:.2f} dB/h exceeds max physical drying rate {cls.MAX_DRYING_RATE_DB_PER_HOUR} dB/h."
                )
                regime = AgriculturalRegime.PHYSICAL_ANOMALY
        elif rate > 0 and not is_irrigation_active and not is_raining:
            # Spontaneous wetting without water application is physically impossible
            violations.append("Spontaneous attenuation increase without rain or irrigation application.")
            regime = AgriculturalRegime.PHYSICAL_ANOMALY

        plausible = len(violations) == 0

        return GrammarValidationResult(
            current_regime=regime,
            is_physically_plausible=plausible,
            rate_of_change_db_per_hour=rate,
            violations=violations,
        )
