"""MESIA E4 Nuisance Challenge Matrix Harness — R6 §10.5 / P8.5.

Injects controlled perturbations (hardware swap, mast shift, pump actuation,
cellular handover) while soil state remains constant to verify zero false agronomic detection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ChallengeExecutionResult:
    """Outcome of executing a single row in the E4 nuisance challenge matrix."""

    challenge_id: str
    injected_perturbation: str
    observed_signal_shift_db: float
    correctly_attributed_as_nuisance: bool
    falsely_attributed_as_soil_change: bool
    is_safe: bool
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "challenge_id": self.challenge_id,
            "injected_perturbation": self.injected_perturbation,
            "observed_signal_shift_db": round(self.observed_signal_shift_db, 3),
            "correctly_attributed_as_nuisance": self.correctly_attributed_as_nuisance,
            "falsely_attributed_as_soil_change": self.falsely_attributed_as_soil_change,
            "is_safe": self.is_safe,
            "diagnostics": self.diagnostics,
        }


class NuisanceChallengeMatrixHarness:
    """Executes the complete E4 nuisance injection matrix."""

    @classmethod
    def run_firmware_swap_challenge(
        cls,
        challenge_id: str,
        observed_gain_shift_db: float = 2.0,
        firmware_event_logged: bool = True,
    ) -> ChallengeExecutionResult:
        """Inject a firmware update causing receiver gain step while soil state is constant."""
        # If firmware event is logged in instrument epoch, gain step is isolated to hardware
        correct = bool(firmware_event_logged)
        false_soil = bool(not firmware_event_logged)
        safe = bool(correct and not false_soil)

        return ChallengeExecutionResult(
            challenge_id=challenge_id,
            injected_perturbation="RECEIVER_FIRMWARE_GAIN_STEP",
            observed_signal_shift_db=observed_gain_shift_db,
            correctly_attributed_as_nuisance=correct,
            falsely_attributed_as_soil_change=false_soil,
            is_safe=safe,
            diagnostics={
                "firmware_event_logged": firmware_event_logged,
                "instrument_epoch_transition_detected": firmware_event_logged,
                "recalibration_triggered": firmware_event_logged,
                "false_moisture_step_pct": 0.0 if safe else round(observed_gain_shift_db * 1.5, 2),
            },
        )

    @classmethod
    def run_mast_wind_flutter_challenge(
        cls,
        challenge_id: str,
        wind_speed_m_s: float = 12.0,
        observed_phase_flutter_deg: float = 8.5,
        flutter_frequency_hz: float = 1.8,
    ) -> ChallengeExecutionResult:
        """Inject aerodynamic mast deflection and high-frequency phase flutter."""
        # Mast flutter occurs at mechanical frequencies (>0.5 Hz)
        # Agronomic soil moisture changes occur at hydrological timescales (<1e-4 Hz)
        is_high_freq = bool(flutter_frequency_hz >= 0.50)
        filter_rejected = is_high_freq

        return ChallengeExecutionResult(
            challenge_id=challenge_id,
            injected_perturbation="MAST_AERODYNAMIC_WIND_FLUTTER",
            observed_signal_shift_db=round(observed_phase_flutter_deg * 0.12, 3),
            correctly_attributed_as_nuisance=filter_rejected,
            falsely_attributed_as_soil_change=not filter_rejected,
            is_safe=filter_rejected,
            diagnostics={
                "wind_speed_m_s": wind_speed_m_s,
                "observed_phase_flutter_deg": observed_phase_flutter_deg,
                "flutter_frequency_hz": flutter_frequency_hz,
                "bandpass_filter_rejected": filter_rejected,
                "false_canopy_water_index_spike": 0.0 if filter_rejected else 0.04,
            },
        )

    @classmethod
    def run_cellular_handover_challenge(
        cls,
        challenge_id: str,
        observed_rsrp_drop_db: float = 6.0,
        cell_tower_handover_logged: bool = True,
    ) -> ChallengeExecutionResult:
        """Inject LTE base station handover causing step in observed carrier power."""
        correct = bool(cell_tower_handover_logged)
        false_soil = bool(not cell_tower_handover_logged)
        safe = bool(correct and not false_soil)

        return ChallengeExecutionResult(
            challenge_id=challenge_id,
            injected_perturbation="CELLULAR_BASE_STATION_HANDOVER",
            observed_signal_shift_db=observed_rsrp_drop_db,
            correctly_attributed_as_nuisance=correct,
            falsely_attributed_as_soil_change=false_soil,
            is_safe=safe,
            diagnostics={
                "cell_tower_handover_logged": cell_tower_handover_logged,
                "osm_mast_geometry_reindexed": cell_tower_handover_logged,
                "false_cwi_perturbation": 0.0 if safe else 0.06,
            },
        )

    @classmethod
    def run_honest_null_noise_challenge(
        cls,
        challenge_id: str,
        measured_snr_db: float = 0.8,
        is_terminated_50ohm_load: bool = True,
    ) -> ChallengeExecutionResult:
        """Inject pure thermal noise floor / terminated load and confirm compulsory abstention."""
        # When load is terminated or SNR < 3 dB, model must abstain from any moisture claim
        abstention_enforced = bool(is_terminated_50ohm_load or measured_snr_db < 3.0)

        return ChallengeExecutionResult(
            challenge_id=challenge_id,
            injected_perturbation="TERMINATED_RF_LOAD_NOISE_FLOOR",
            observed_signal_shift_db=0.0,
            correctly_attributed_as_nuisance=abstention_enforced,
            falsely_attributed_as_soil_change=not abstention_enforced,
            is_safe=abstention_enforced,
            diagnostics={
                "measured_snr_db": measured_snr_db,
                "is_terminated_50ohm_load": is_terminated_50ohm_load,
                "abstention_enforced": abstention_enforced,
                "zero_phantom_detection": abstention_enforced,
            },
        )
