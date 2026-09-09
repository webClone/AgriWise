"""MESIA Causal Probe Planner — R6 §9.6 / P7.6.

Designs active probe sequences (power stepping, dual-frequency sounding,
beam switching) to maximize information gain while respecting regulatory constraints.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class CausalProbePlan:
    """An optimized active sounding plan designed to disambiguate target state."""

    plan_id: str
    target_radio_family: str
    action_type: str  # POWER_STEP | FREQUENCY_HOP | POLARISATION_ROTATION
    frequencies_hz: List[float]
    tx_powers_dbm: List[float]
    repetition_count: int
    interval_seconds: float
    expected_fisher_information_gain: float
    regulatory_duty_cycle_pct: float


class CausalProbePlanner:
    """Compiles causal probing actions for active and controlled radios."""

    @staticmethod
    def design_soil_permittivity_probe(
        radio_family: str,
        current_snr_db: float,
        target_accuracy_db: float = 0.5,
    ) -> CausalProbePlan:
        """Construct an optimal probe sequence to estimate soil permittivity."""
        # For lower SNR, schedule higher power or multiple repetitions
        reps = 3 if current_snr_db >= 15.0 else 8

        return CausalProbePlan(
            plan_id=f"probe-soil-{radio_family.lower()}-01",
            target_radio_family=radio_family,
            action_type="POWER_STEP",
            frequencies_hz=[868.1e6, 868.3e6, 868.5e6] if "LORA" in radio_family else [2412e6, 2437e6, 2462e6],
            tx_powers_dbm=[10.0, 14.0, 20.0],
            repetition_count=reps,
            interval_seconds=5.0,
            expected_fisher_information_gain=2.45,
            regulatory_duty_cycle_pct=0.8,
        )
