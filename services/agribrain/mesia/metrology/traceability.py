"""MESIA Calibration Traceability & Out-of-Tolerance Handler — R6 §1.6 & §10.5.

Manages national/SI traceability chains, calibration certificates, automated
out-of-tolerance (OOT) anomaly detection, and typed invalidation generation
(ensuring NO silent correction).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..contracts.epochs import CalibrationState
from ..contracts.authority import RevocationEvent


@dataclass(frozen=True)
class TraceabilityNode:
    """A node in the metrology traceability chain from SI standard down to device."""

    standard_name: str
    standard_authority: str
    """e.g., 'BIPM', 'NIST', 'PTB', 'LNE', 'ONML_ALGERIA'."""

    certificate_number: str
    calibration_date: datetime
    valid_until: datetime
    expanded_uncertainty_k2: float
    unit: str = "dB"


@dataclass(frozen=True)
class CalibrationCertificate:
    """Complete traceable calibration record for an instrument or antenna."""

    certificate_id: str
    device_id: str
    calibrated_at: datetime
    valid_until: datetime
    calibrated_by: str
    traceability_chain: List[TraceabilityNode] = field(default_factory=list)
    uncertainty_budget_ref: str = ""
    is_valid: bool = True
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "certificate_id": self.certificate_id,
            "device_id": self.device_id,
            "calibrated_at": self.calibrated_at.isoformat(),
            "valid_until": self.valid_until.isoformat(),
            "calibrated_by": self.calibrated_by,
            "traceability_chain": [
                {
                    "standard_name": t.standard_name,
                    "standard_authority": t.standard_authority,
                    "certificate_number": t.certificate_number,
                    "calibration_date": t.calibration_date.isoformat(),
                    "valid_until": t.valid_until.isoformat(),
                    "expanded_uncertainty_k2": t.expanded_uncertainty_k2,
                    "unit": t.unit,
                }
                for t in self.traceability_chain
            ],
            "uncertainty_budget_ref": self.uncertainty_budget_ref,
            "is_valid": self.is_valid,
            "notes": self.notes,
        }

    def content_hash(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class OutOfToleranceDetector:
    """Detects when an instrument measurement exceeds its declared tolerance/uncertainty,
    and generates typed invalidation epoch updates rather than silent imputation."""

    def __init__(self, tolerance_limit: float, unit: str = "dB") -> None:
        self.tolerance_limit = tolerance_limit
        self.unit = unit

    def evaluate_deviation(
        self,
        measured_value: float,
        reference_value: float,
        current_calibration_epoch: CalibrationState,
        device_id: str,
    ) -> Optional[CalibrationState]:
        """Check if deviation |measured - reference| exceeds tolerance.

        Returns:
            A new mutated/chained CalibrationState with status='FAILED' if OOT,
            or None if within tolerance.
        """
        deviation = abs(measured_value - reference_value)
        if deviation > self.tolerance_limit:
            # Generate typed invalidation
            now = datetime.now(timezone.utc)
            return CalibrationState(
                epoch_id=f"cal-oot-{now.strftime('%Y%m%d%H%M%S')}",
                triggered_at=now,
                trigger_reason=(
                    f"Out-of-tolerance detected on {device_id}: "
                    f"deviation={deviation:.4f}{self.unit} > limit={self.tolerance_limit:.4f}{self.unit}"
                ),
                previous_epoch_id=current_calibration_epoch.epoch_id,
                uncertainty_db=current_calibration_epoch.uncertainty_db,
                reference_artefact_ref=current_calibration_epoch.reference_artefact_ref,
                drift_sentinel_ref=current_calibration_epoch.drift_sentinel_ref,
                status="FAILED",
                demotion_reason="MEASUREMENT_OUT_OF_TOLERANCE",
            )
        return None
