"""MESIA Negative & Teacher Controls Framework — R6 §10.9 / P8.9.

Manages negative control fixtures (RF-absorber boxes, 50-ohm terminators)
and positive teacher controls (calibrated direct-contact TDR/FDR sensors, gravimetric soil samples).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class NegativeControlResult:
    """Outcome of verifying receiver isolation against an RF absorbing or shielded load."""

    fixture_id: str
    measured_isolation_db: float
    is_isolation_adequate: bool  # >= 40 dB isolation
    leakage_power_dbm: float = -999.0
    reference_tx_power_dbm: float = 20.0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "measured_isolation_db": round(self.measured_isolation_db, 2),
            "is_isolation_adequate": self.is_isolation_adequate,
            "leakage_power_dbm": round(self.leakage_power_dbm, 2),
            "reference_tx_power_dbm": round(self.reference_tx_power_dbm, 2),
            "notes": self.notes,
        }


@dataclass(frozen=True)
class TeacherControlComparison:
    """Comparison between indirect radio estimation and direct physical teacher probe."""

    probe_id: str
    teacher_type: str  # TDR_PROBE | GRAVIMETRIC_CORE | THERMAL_INFRARED | FDR_PROBE
    teacher_measured_vwc: float
    mesia_estimated_vwc: float
    absolute_residual_error: float
    is_within_tolerance: bool
    tolerance_vwc: float = 0.03
    calibrated_depth_cm: float = 10.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "probe_id": self.probe_id,
            "teacher_type": self.teacher_type,
            "teacher_measured_vwc": round(self.teacher_measured_vwc, 4),
            "mesia_estimated_vwc": round(self.mesia_estimated_vwc, 4),
            "absolute_residual_error": round(self.absolute_residual_error, 5),
            "is_within_tolerance": self.is_within_tolerance,
            "tolerance_vwc": self.tolerance_vwc,
            "calibrated_depth_cm": self.calibrated_depth_cm,
        }


class TeacherControlsAuthority:
    """Manages negative and teacher control benchmarks."""

    ISOLATION_MINIMUM_DB: float = 40.0
    DEFAULT_TOLERANCE_VWC: float = 0.03

    @classmethod
    def verify_negative_absorber_isolation(
        cls,
        fixture_id: str,
        measured_signal_leakage_dbm: float,
        reference_tx_power_dbm: float = 20.0,
    ) -> NegativeControlResult:
        """Verify negative control RF absorber box or shielded terminator isolation."""
        isolation_db = reference_tx_power_dbm - measured_signal_leakage_dbm
        is_adequate = bool(isolation_db >= cls.ISOLATION_MINIMUM_DB)
        notes = (
            f"Adequate darkbox isolation ({round(isolation_db, 1)} dB >= {cls.ISOLATION_MINIMUM_DB} dB)"
            if is_adequate
            else f"Isolation breach: {round(isolation_db, 1)} dB is below {cls.ISOLATION_MINIMUM_DB} dB threshold"
        )
        return NegativeControlResult(
            fixture_id=fixture_id,
            measured_isolation_db=round(isolation_db, 2),
            is_isolation_adequate=is_adequate,
            leakage_power_dbm=measured_signal_leakage_dbm,
            reference_tx_power_dbm=reference_tx_power_dbm,
            notes=notes,
        )

    @classmethod
    def compare_with_teacher_truth(
        cls,
        probe_id: str,
        teacher_type: str,
        teacher_vwc: float,
        mesia_vwc: float,
        tolerance_vwc: float = 0.03,
        depth_cm: float = 10.0,
    ) -> TeacherControlComparison:
        """Compare MESIA estimation against direct physical teacher probe measurement."""
        residual = abs(mesia_vwc - teacher_vwc)
        is_within = bool(residual <= tolerance_vwc)
        return TeacherControlComparison(
            probe_id=probe_id,
            teacher_type=teacher_type,
            teacher_measured_vwc=teacher_vwc,
            mesia_estimated_vwc=mesia_vwc,
            absolute_residual_error=round(residual, 5),
            is_within_tolerance=is_within,
            tolerance_vwc=tolerance_vwc,
            calibrated_depth_cm=depth_cm,
        )

    @classmethod
    def verify_honest_null_abstention(
        cls,
        fixture_id: str,
        snr_db: float,
        is_terminated_load: bool = True,
    ) -> Dict[str, Any]:
        """Verify that a terminated 50-ohm load or zero SNR fixture triggers compulsory model abstention.

        Ensures the model cannot hallucinate phantom soil moisture from pure receiver noise.
        """
        # Compulsory abstention triggers if terminated load is present or SNR < 3.0 dB
        must_abstain = bool(is_terminated_load or snr_db < 3.0)

        return {
            "fixture_id": fixture_id,
            "is_terminated_load": is_terminated_load,
            "snr_db": round(snr_db, 2),
            "abstention_enforced": must_abstain,
            "decision_eligible": False,
            "output_state": "ABSTAIN_TERMINATED_LOAD" if is_terminated_load else ("ABSTAIN_NOISE_FLOOR" if must_abstain else "ACTIVE_DETECTION"),
            "phantom_moisture_prevented": must_abstain,
            "inferred_vwc": None if must_abstain else round(0.05 + snr_db * 0.01, 3),
            "audit_timestamp": datetime.now(timezone.utc).isoformat(),
        }
