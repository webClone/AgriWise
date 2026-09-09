"""MESIA Continuous Drift Sentinel & Demotion Policy Authority — R6 §6.7 / P6.7.

Monitors continuous reference sentinels (cable loopbacks, noise diodes, 50-ohm loads)
and triggers automatic calibration invalidation and capability demotion on tolerance breach.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..contracts.epochs import CalibrationState
from ..ontology.capability_lifecycle import CapabilityLifecycle, CapabilityState
from ..truth.reference_sentinel import SentinelVerificationResult


@dataclass(frozen=True)
class DriftEvaluationResult:
    """Outcome of evaluating continuous drift against calibration tolerances."""

    receiver_id: str
    is_healthy: bool
    requires_demotion: bool
    observed_gain_drift_db: float
    observed_phase_drift_deg: float
    new_calibration_state: CalibrationState
    demotion_reason: str = ""


class DriftSentinelMonitor:
    """Monitors instrument drift and enforces Principle P-10 (fail-closed demotion)."""

    def __init__(
        self,
        max_allowed_gain_drift_db: float = 1.5,
        max_allowed_phase_drift_deg: float = 5.0,
    ) -> None:
        self.max_gain_drift_db = max_allowed_gain_drift_db
        self.max_phase_drift_deg = max_allowed_phase_drift_deg

    def evaluate_sentinel_health(
        self,
        receiver_id: str,
        current_calibration: CalibrationState,
        sentinel_result: SentinelVerificationResult,
    ) -> DriftEvaluationResult:
        """Evaluate sentinel result and update CalibrationState status."""
        drift = sentinel_result.deviation
        is_drift_excessive = (drift > self.max_gain_drift_db) or not sentinel_result.is_healthy

        now = datetime.now(timezone.utc)

        if is_drift_excessive:
            new_cal = CalibrationState(
                epoch_id=current_calibration.epoch_id,
                triggered_at=now,
                trigger_reason=f"Sentinel drift breach: {drift:.2f} {sentinel_result.unit}",
                previous_epoch_id=current_calibration.previous_epoch_id,
                valid_from=current_calibration.valid_from,
                valid_to=now,
                uncertainty_db=current_calibration.uncertainty_db,
                reference_artefact_ref=current_calibration.reference_artefact_ref,
                drift_sentinel_ref=current_calibration.drift_sentinel_ref,
                status="FAILED",
                demotion_reason=f"Drift breach: drift={drift:.2f}{sentinel_result.unit} (tolerance {sentinel_result.tolerance}{sentinel_result.unit})",
            )
            reason = f"Drift sentinel triggered invalidation: drift {drift:.2f} {sentinel_result.unit} exceeds tolerance."
            return DriftEvaluationResult(
                receiver_id=receiver_id,
                is_healthy=False,
                requires_demotion=True,
                observed_gain_drift_db=drift,
                observed_phase_drift_deg=0.0,
                new_calibration_state=new_cal,
                demotion_reason=reason,
            )

        # Still valid
        return DriftEvaluationResult(
            receiver_id=receiver_id,
            is_healthy=True,
            requires_demotion=False,
            observed_gain_drift_db=drift,
            observed_phase_drift_deg=0.0,
            new_calibration_state=current_calibration,
            demotion_reason="",
        )
