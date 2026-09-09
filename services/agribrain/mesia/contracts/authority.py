"""MESIA Authority and Revocation Contracts — R6 §12, Appendix A.

CapabilityAuthorityRecord — Named capability, passed gates, allowed uses,
  domain, expiry, reviewers and rollback.
RevocationEvent — Why, when and how evidence/capability authority was
  demoted or withdrawn.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class CapabilityAuthorityRecord:
    """Named capability authority dossier — R6 Appendix A & Appendix D.

    Principle P-09: A cluster is never globally certified; each target,
    domain, use and evidence tier has its own authority record.
    """

    capability_id: str
    capability_name: str
    version: str = "1.0.0"

    target_variable: str = ""
    """e.g., 'root_zone_water', 'irrigation_detection', 'salinity_stress'."""

    # 8-Gate Qualification Status
    gate_repeatability_passed: bool = False
    gate_sensitivity_passed: bool = False
    gate_specificity_passed: bool = False
    gate_observability_passed: bool = False
    gate_transfer_passed: bool = False
    gate_closure_passed: bool = False
    gate_incremental_value_passed: bool = False
    gate_governance_passed: bool = False

    # Domain Boundaries
    supported_radio_families: List[str] = field(default_factory=list)
    supported_soil_textures: List[str] = field(default_factory=list)
    supported_crop_types: List[str] = field(default_factory=list)
    supported_moisture_range: List[float] = field(default_factory=list)
    geographic_domain: str = ""
    climate_zones: List[str] = field(default_factory=list)

    # Allowed & Prohibited Uses
    allowed_uses: List[str] = field(default_factory=list)
    """e.g., ['RESEARCH_ONLY', 'CONTEXT', 'DIAGNOSTIC_SUPPORT', 'STATE_PROPOSAL']."""

    prohibited_uses: List[str] = field(default_factory=list)

    # Lifecycle & Expiry
    state: str = "UNQUALIFIED_PENDING_EVIDENCE"
    """CapabilityState value. Defaults to UNQUALIFIED_PENDING_EVIDENCE (Audit Finding #6: fail-closed)."""

    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    renewal_cadence_days: int = 90

    # Reviewers & Sign-off
    review_board: str = "ScienceGateBoard"
    approved_by: List[str] = field(default_factory=list)
    preregistration_ref: str = ""
    closure_certificate_ref: str = ""
    observability_certificate_ref: str = ""

    # Rollback Strategy
    fallback_capability_ref: str = ""

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

    @property
    def all_gates_passed(self) -> bool:
        return (
            self.gate_repeatability_passed
            and self.gate_sensitivity_passed
            and self.gate_specificity_passed
            and self.gate_observability_passed
            and self.gate_transfer_passed
            and self.gate_closure_passed
            and self.gate_incremental_value_passed
            and self.gate_governance_passed
        )


@dataclass(frozen=True)
class RevocationEvent:
    """Authority demotion or withdrawal audit record — R6 Appendix A.

    Principle P-10: Failed calibration, closure, observability, transfer,
    security or governance demotes affected evidence/use automatically.
    """

    event_id: str
    capability_authority_ref: str
    revoked_at: datetime
    trigger_reason: str
    """e.g., 'CALIBRATION_EXPIRED', 'CLOSURE_RESIDUAL_DRIFT', 'DOMAIN_VIOLATION'."""

    # Scope of revocation
    previous_state: str = "QUALIFIED"
    new_state: str = "DEGRADED"  # DEGRADED | REVOKED
    affected_uses: List[str] = field(default_factory=list)
    affected_deployments: List[str] = field(default_factory=list)

    # Remediation & Recommissioning
    remediation_required: str = ""
    recommissioning_checklist_ref: str = ""
    notified_stakeholders: List[str] = field(default_factory=list)

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
