"""MESIA Active/Passive Sensing Task Contracts — R6 §9.3, Appendix A.

SensingTaskReceipt — Requested versus executed passive/active action,
spectrum/privacy/safety approval and completion evidence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class SensingTaskReceipt:
    """Requested vs executed action verification record — R6 Appendix A.

    An active probe is a controlled measurement action, not an arbitrary
    transmission (§9.3).  The task must specify objective, expected
    information gain, spectrum permission, and execution verification.
    """

    task_id: str
    objective: str = ""
    """e.g., 'CALIBRATION_PROBE', 'SOIL_DISCRIMINATION', 'SCHEDULED_SWEEP'."""

    action_type: str = "PASSIVE"
    """'PASSIVE' or 'ACTIVE'."""

    # Requested Parameters
    requested_at: Optional[datetime] = None
    target_receiver_ids: List[str] = field(default_factory=list)
    target_transmitter_ids: List[str] = field(default_factory=list)
    requested_frequency_range_hz: Optional[Tuple[float, float]] = None
    requested_tx_power_dbm: Optional[float] = None
    requested_duty_cycle_pct: Optional[float] = None
    requested_duration_s: Optional[float] = None

    # Safety & Regulatory Approvals
    spectrum_licence_ref: str = ""
    rf_exposure_compliance_verified: bool = False
    privacy_consent_verified: bool = False
    site_safety_signoff_by: str = ""

    # Executed Parameters
    executed_at: Optional[datetime] = None
    actual_duration_s: Optional[float] = None
    actual_tx_power_dbm: Optional[float] = None
    actual_frequency_range_hz: Optional[Tuple[float, float]] = None
    execution_status: str = "COMPLETED"
    """'COMPLETED', 'ABORTED', 'FAILED', 'PARAM_MISMATCH'."""

    # Execution Verification & Lineage
    verified_by_independent_receiver: bool = False
    independent_verifier_id: str = ""
    resulting_observation_packet_refs: List[str] = field(default_factory=list)
    execution_anomalies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        for f in self.__dataclass_fields__:
            val = getattr(self, f)
            if isinstance(val, datetime):
                val = val.isoformat()
            elif isinstance(val, (list, tuple)):
                val = list(val)
            d[f] = val
        return d

    def content_hash(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
