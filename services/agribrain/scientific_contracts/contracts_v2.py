"""Scientific Contracts V2 — Frozen Canonical Contracts.

R5.0 Architecture: 7 Canonical Scientific Contracts establishing strict semantic
validation, immutable lineage, and fail-closed security across all system boundaries:
  1. EvidenceRef: Immutable observational evidence receipt.
  2. StateRef: Authoritative system belief state snapshot.
  3. DiagnosticResult: Standardized diagnostic assertion.
  4. CapabilityReceipt: Authenticated permission and capability token.
  5. ForcingEvent: Physical management and environmental forcing event.
  6. ScenarioRef: Candidate action plan and simulated trajectory.
  7. ActionAuthorization: Binding prescriptive decision envelope.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union
from uuid import UUID

from .authority import AuthorityVector, SpatialSupport
from .exceptions import ContractViolation
from .stage_receipt import ExecutionStatus, ScientificUsability, StageReceipt


# ============================================================================
# CANONICAL ENUMS
# ============================================================================

class EvidenceRole(str, Enum):
    OBSERVATION_NATIVE = "OBSERVATION_NATIVE"
    DERIVED_PROXY = "DERIVED_PROXY"
    CALIBRATION = "CALIBRATION"


class InfluenceUse(str, Enum):
    DIAGNOSIS = "DIAGNOSIS"
    STATE_UPDATE = "STATE_UPDATE"
    TRAINING = "TRAINING"
    PRESCRIPTION_DRIVER = "PRESCRIPTION_DRIVER"
    MACHINE_EXECUTION = "MACHINE_EXECUTION"


class ForcingExecutionStatus(str, Enum):
    PLANNED = "PLANNED"
    SCENARIO_SIMULATED = "SCENARIO_SIMULATED"
    OBSERVED_CONFIRMED = "OBSERVED_CONFIRMED"


class InterventionLifecycleState(str, Enum):
    """4-phase lifecycle for farm interventions distinguishing plans from physical exposures (P06.1)."""
    PROPOSED = "PROPOSED"
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    EXPOSED = "EXPOSED"


# ============================================================================
# SERIALIZATION & HASHING HELPERS
# ============================================================================

def canonical_data(value: Any) -> Any:
    """Recursively converts structures to deterministic, JSON-safe primitives."""
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return canonical_data(value.to_dict())
    if is_dataclass(value):
        return canonical_data({f.name: getattr(value, f.name) for f in dataclasses.fields(value)})
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (Decimal, UUID, Path)):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
        return {"type": "bytes", "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ContractViolation("Scientific contract payload contains non-finite float")
        return value
    if isinstance(value, Mapping):
        return {str(k): canonical_data(v) for k, v in sorted(value.items(), key=lambda p: str(p[0]))}
    if isinstance(value, (list, tuple)):
        return [canonical_data(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted([canonical_data(v) for v in value], key=lambda x: json.dumps(x, sort_keys=True, default=str))
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if hasattr(value, "__dict__"):
        return canonical_data(vars(value))
    raise ContractViolation(f"Unsupported contract value type: {type(value).__name__}")


def canonical_hash(value: Any) -> str:
    """Produces a deterministic SHA-256 hex digest from canonical data."""
    payload = json.dumps(canonical_data(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ============================================================================
# SUPPORTING DOMAIN DATACLASSES
# ============================================================================

@dataclass(frozen=True)
class OwnershipContext:
    tenant_id: str
    farm_id: str
    plot_id: str

    def __post_init__(self) -> None:
        if not str(self.tenant_id or "").strip():
            raise ContractViolation("OwnershipContext requires non-blank tenant_id")
        if not str(self.farm_id or "").strip():
            raise ContractViolation("OwnershipContext requires non-blank farm_id")
        if not str(self.plot_id or "").strip():
            raise ContractViolation("OwnershipContext requires non-blank plot_id")

    def to_dict(self) -> Dict[str, str]:
        return {
            "tenant_id": self.tenant_id,
            "farm_id": self.farm_id,
            "plot_id": self.plot_id,
        }


@dataclass(frozen=True)
class ValidityDomain:
    bounding_box: Optional[Tuple[float, float, float, float]] = None
    crop_species: Optional[str] = None
    phenology_stage: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bounding_box": list(self.bounding_box) if self.bounding_box is not None else None,
            "crop_species": self.crop_species,
            "phenology_stage": self.phenology_stage,
        }


@dataclass(frozen=True)
class YieldDistribution:
    p10: float
    p50: float
    p90: float
    units: str = "t/ha"

    def __post_init__(self) -> None:
        for val, name in ((self.p10, "p10"), (self.p50, "p50"), (self.p90, "p90")):
            if not isinstance(val, (int, float)) or not math.isfinite(val) or val < 0.0:
                raise ContractViolation(f"YieldDistribution {name} must be finite and non-negative")
        if not (self.p10 <= self.p50 <= self.p90):
            raise ContractViolation(
                f"YieldDistribution must satisfy p10 <= p50 <= p90, got {self.p10}, {self.p50}, {self.p90}"
            )
        if not str(self.units or "").strip():
            raise ContractViolation("YieldDistribution requires units")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "p10": self.p10,
            "p50": self.p50,
            "p90": self.p90,
            "units": self.units,
        }


@dataclass(frozen=True)
class FeasibilityReceipt:
    is_feasible: bool
    constraint_checks: Mapping[str, bool] = field(default_factory=dict)
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_feasible": self.is_feasible,
            "constraint_checks": dict(self.constraint_checks),
            "evaluated_at": self.evaluated_at.isoformat(),
        }


# ============================================================================
# THE 7 CANONICAL SCIENTIFIC CONTRACTS
# ============================================================================

# ── 1. EvidenceRef ──────────────────────────────────────────────────────────
@dataclass(frozen=True)
class EvidenceRef:
    """Canonical Observational Evidence.
    
    Represents an immutable receipt of an observed physical quantity or
    remote sensing acquisition with verified spatial support and dimensional units.
    """
    evidence_id: str
    ownership: OwnershipContext
    variable_name: str
    units: str
    observed_at: datetime
    knowledge_available_at: datetime
    spatial_support: SpatialSupport
    transformation_lineage: Tuple[str, ...] = ()
    admissible_roles: Tuple[EvidenceRole, ...] = (EvidenceRole.OBSERVATION_NATIVE,)
    quality_grade: str = "A"
    raw_payload_uri: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.evidence_id or "").strip():
            raise ContractViolation("EvidenceRef requires non-blank evidence_id")
        if not isinstance(self.ownership, OwnershipContext):
            raise ContractViolation("EvidenceRef requires typed OwnershipContext")
        if not str(self.variable_name or "").strip():
            raise ContractViolation("EvidenceRef requires non-blank variable_name")
        if not str(self.units or "").strip():
            raise ContractViolation("EvidenceRef requires non-blank units")
        if not isinstance(self.observed_at, datetime):
            raise ContractViolation("EvidenceRef requires observed_at datetime")
        if not isinstance(self.knowledge_available_at, datetime):
            raise ContractViolation("EvidenceRef requires knowledge_available_at datetime")
        if self.observed_at > self.knowledge_available_at:
            raise ContractViolation("EvidenceRef observed_at cannot be later than knowledge_available_at")
        if not isinstance(self.spatial_support, SpatialSupport):
            raise ContractViolation("EvidenceRef requires typed SpatialSupport")
        if self.quality_grade not in ("A", "B", "C", "REJECTED"):
            raise ContractViolation(f"EvidenceRef quality_grade must be A, B, C, or REJECTED, got {self.quality_grade}")

    def compute_hash(self) -> str:
        return canonical_hash(self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "ownership": self.ownership.to_dict(),
            "variable_name": self.variable_name,
            "units": self.units,
            "observed_at": self.observed_at.isoformat(),
            "knowledge_available_at": self.knowledge_available_at.isoformat(),
            "spatial_support": self.spatial_support.value,
            "transformation_lineage": list(self.transformation_lineage),
            "admissible_roles": [r.value for r in self.admissible_roles],
            "quality_grade": self.quality_grade,
            "raw_payload_uri": self.raw_payload_uri,
            "metadata": dict(self.metadata),
        }


# ── 2. StateRef ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class StateRef:
    """Canonical System Belief State.
    
    Defines the complete state of a field or microzone at a specific point in time
    with explicit covariance matrix and evidence availability cutoff.
    """
    state_id: str
    schema_version: str
    snapshot_timestamp: datetime
    knowledge_cutoff: datetime
    lattice_reference: str
    state_vector: Tuple[float, ...]
    state_covariance: Tuple[Tuple[float, ...], ...]
    identifiability_classes: Mapping[str, str]
    worldline_head_hash: str

    def __post_init__(self) -> None:
        if not str(self.state_id or "").strip():
            raise ContractViolation("StateRef requires non-blank state_id")
        if not str(self.schema_version or "").strip():
            raise ContractViolation("StateRef requires non-blank schema_version")
        if not isinstance(self.snapshot_timestamp, datetime):
            raise ContractViolation("StateRef requires snapshot_timestamp datetime")
        if not isinstance(self.knowledge_cutoff, datetime):
            raise ContractViolation("StateRef requires knowledge_cutoff datetime")
        if not str(self.lattice_reference or "").strip():
            raise ContractViolation("StateRef requires non-blank lattice_reference")
        if not self.state_vector:
            raise ContractViolation("StateRef requires non-empty state_vector")
        N = len(self.state_vector)
        if len(self.state_covariance) != N or any(len(row) != N for row in self.state_covariance):
            raise ContractViolation(
                f"StateRef state_covariance must be {N}x{N} matching state_vector dimension {N}"
            )
        if not str(self.worldline_head_hash or "").strip():
            raise ContractViolation("StateRef requires non-blank worldline_head_hash")

    def compute_hash(self) -> str:
        return canonical_hash(self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state_id": self.state_id,
            "schema_version": self.schema_version,
            "snapshot_timestamp": self.snapshot_timestamp.isoformat(),
            "knowledge_cutoff": self.knowledge_cutoff.isoformat(),
            "lattice_reference": self.lattice_reference,
            "state_vector": list(self.state_vector),
            "state_covariance": [list(row) for row in self.state_covariance],
            "identifiability_classes": dict(self.identifiability_classes),
            "worldline_head_hash": self.worldline_head_hash,
        }


# ── 3. DiagnosticResult ─────────────────────────────────────────────────────
@dataclass(frozen=True)
class DiagnosticResult:
    """Standardized Diagnostic Assertion.
    
    Encapsulates an agronomic diagnosis emitted by Layers 2, 3, 4, or 5 with strictly
    segregated severity, probability, confidence, and confounder evaluation.
    """
    diagnosis_id: str
    layer_id: str
    target_hypothesis: str
    severity: float
    probability: float
    confidence: float
    evidence_strength_log_odds: float = 0.0
    confounders_evaluated: Tuple[str, ...] = ()
    unresolved_status: bool = False
    input_evidence_ids: Tuple[str, ...] = ()
    computational_dependencies: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not str(self.diagnosis_id or "").strip():
            raise ContractViolation("DiagnosticResult requires non-blank diagnosis_id")
        if not str(self.layer_id or "").strip():
            raise ContractViolation("DiagnosticResult requires non-blank layer_id")
        if not str(self.target_hypothesis or "").strip():
            raise ContractViolation("DiagnosticResult requires non-blank target_hypothesis")
        for val, name in ((self.severity, "severity"), (self.probability, "probability"), (self.confidence, "confidence")):
            if not isinstance(val, (int, float)) or not math.isfinite(val) or not (0.0 <= float(val) <= 1.0):
                raise ContractViolation(f"DiagnosticResult {name} must be finite in [0.0, 1.0], got {val}")
        if not isinstance(self.evidence_strength_log_odds, (int, float)) or not math.isfinite(self.evidence_strength_log_odds):
            raise ContractViolation("DiagnosticResult evidence_strength_log_odds must be finite")

    def compute_hash(self) -> str:
        return canonical_hash(self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "diagnosis_id": self.diagnosis_id,
            "layer_id": self.layer_id,
            "target_hypothesis": self.target_hypothesis,
            "severity": self.severity,
            "probability": self.probability,
            "confidence": self.confidence,
            "evidence_strength_log_odds": self.evidence_strength_log_odds,
            "confounders_evaluated": list(self.confounders_evaluated),
            "unresolved_status": self.unresolved_status,
            "input_evidence_ids": list(self.input_evidence_ids),
            "computational_dependencies": list(self.computational_dependencies),
        }


# ── 4. CapabilityReceipt ────────────────────────────────────────────────────
@dataclass(frozen=True)
class CapabilityReceipt:
    """Authenticated Permission Token.
    
    Represents an authorized capability grant permitting a specific operational
    use of an output across diagnostic, state, prescription, or execution paths.
    """
    receipt_id: str
    target_variable: str
    permitted_use: InfluenceUse
    validity_domain: ValidityDomain
    evidence_support_hash: str
    qualification_certificate_id: str
    issued_at: datetime
    expires_at: datetime
    revoked: bool = False
    signature: str = ""

    def __post_init__(self) -> None:
        if not str(self.receipt_id or "").strip():
            raise ContractViolation("CapabilityReceipt requires non-blank receipt_id")
        if not str(self.target_variable or "").strip():
            raise ContractViolation("CapabilityReceipt requires non-blank target_variable")
        if not isinstance(self.permitted_use, InfluenceUse):
            raise ContractViolation("CapabilityReceipt requires typed InfluenceUse")
        if not isinstance(self.validity_domain, ValidityDomain):
            raise ContractViolation("CapabilityReceipt requires typed ValidityDomain")
        if not isinstance(self.issued_at, datetime):
            raise ContractViolation("CapabilityReceipt requires issued_at datetime")
        if not isinstance(self.expires_at, datetime):
            raise ContractViolation("CapabilityReceipt requires expires_at datetime")
        if self.issued_at >= self.expires_at:
            raise ContractViolation("CapabilityReceipt issued_at must be strictly before expires_at")

    def is_valid_at(self, check_time: Optional[datetime] = None) -> bool:
        if self.revoked:
            return False
        t = check_time or datetime.now(timezone.utc)
        return self.issued_at <= t <= self.expires_at

    def compute_hash(self) -> str:
        return canonical_hash(self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "target_variable": self.target_variable,
            "permitted_use": self.permitted_use.value,
            "validity_domain": self.validity_domain.to_dict(),
            "evidence_support_hash": self.evidence_support_hash,
            "qualification_certificate_id": self.qualification_certificate_id,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "revoked": self.revoked,
            "signature": self.signature,
        }


# ── 5. ForcingEvent ─────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ForcingEvent:
    """Physical Management & Environmental Forcing.
    
    Represents interventions or weather inputs driving state transitions, distinguishing
    planned scenarios from confirmed observed applications.
    """
    event_id: str
    forcing_type: str
    execution_status: Union[ForcingExecutionStatus, ExecutionStatus, InterventionLifecycleState]
    quantity: float
    units: str
    effective_start: datetime
    effective_end: datetime
    spatial_extent: SpatialSupport
    efficiency_factor: float = 1.0
    provenance_hash: str = ""

    def __post_init__(self) -> None:
        if not str(self.event_id or "").strip():
            raise ContractViolation("ForcingEvent requires non-blank event_id")
        if not str(self.forcing_type or "").strip():
            raise ContractViolation("ForcingEvent requires non-blank forcing_type")
        if not isinstance(self.quantity, (int, float)) or not math.isfinite(self.quantity) or self.quantity < 0.0:
            raise ContractViolation(f"ForcingEvent quantity must be finite and non-negative, got {self.quantity}")
        if not str(self.units or "").strip():
            raise ContractViolation("ForcingEvent requires non-blank units")
        if not isinstance(self.effective_start, datetime) or not isinstance(self.effective_end, datetime):
            raise ContractViolation("ForcingEvent requires effective_start and effective_end datetimes")
        if self.effective_start > self.effective_end:
            raise ContractViolation("ForcingEvent effective_start cannot be after effective_end")
        if not isinstance(self.spatial_extent, SpatialSupport):
            raise ContractViolation("ForcingEvent requires typed SpatialSupport")
        if not (0.0 <= self.efficiency_factor <= 1.0):
            raise ContractViolation(f"ForcingEvent efficiency_factor must be in [0.0, 1.0], got {self.efficiency_factor}")

    def compute_hash(self) -> str:
        return canonical_hash(self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "forcing_type": self.forcing_type,
            "execution_status": self.execution_status.value if hasattr(self.execution_status, "value") else str(self.execution_status),
            "quantity": self.quantity,
            "units": self.units,
            "effective_start": self.effective_start.isoformat(),
            "effective_end": self.effective_end.isoformat(),
            "spatial_extent": self.spatial_extent.value,
            "efficiency_factor": self.efficiency_factor,
            "provenance_hash": self.provenance_hash,
        }


# ── 6. ScenarioRef ──────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ScenarioRef:
    """Candidate Action Plan.
    
    Produced by Layer 7 planning to express conditional future trajectories with
    verified feasibility and calibrated yield distributions.
    """
    scenario_id: str
    action_type: str
    proposed_timing: datetime
    target_zones: Tuple[str, ...]
    parameters: Mapping[str, Any]
    feasibility_receipt: FeasibilityReceipt
    conditional_trajectory_id: str
    expected_yield_impact: YieldDistribution
    assumptions: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not str(self.scenario_id or "").strip():
            raise ContractViolation("ScenarioRef requires non-blank scenario_id")
        if not str(self.action_type or "").strip():
            raise ContractViolation("ScenarioRef requires non-blank action_type")
        if not isinstance(self.proposed_timing, datetime):
            raise ContractViolation("ScenarioRef requires proposed_timing datetime")
        if not isinstance(self.feasibility_receipt, FeasibilityReceipt):
            raise ContractViolation("ScenarioRef requires typed FeasibilityReceipt")
        if not isinstance(self.expected_yield_impact, YieldDistribution):
            raise ContractViolation("ScenarioRef requires typed YieldDistribution")

    def compute_hash(self) -> str:
        return canonical_hash(self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "action_type": self.action_type,
            "proposed_timing": self.proposed_timing.isoformat(),
            "target_zones": list(self.target_zones),
            "parameters": dict(self.parameters),
            "feasibility_receipt": self.feasibility_receipt.to_dict(),
            "conditional_trajectory_id": self.conditional_trajectory_id,
            "expected_yield_impact": self.expected_yield_impact.to_dict(),
            "assumptions": list(self.assumptions),
        }


# ── 7. ActionAuthorization ──────────────────────────────────────────────────
@dataclass(frozen=True)
class ActionAuthorization:
    """Binding Prescriptive Decision.
    
    The final authorized output emitted by Layer 8 and verified prior to execution,
    cryptographically linking tribunal receipts, prescription manifests, and policy snapshots.
    """
    authorization_id: str
    selected_scenario_id: str
    belief_state_id: str
    tribunal_receipt_hash: str
    prescription_manifest_hash: str
    policy_snapshot_hash: str
    authorized_by: str
    authorized_at: datetime
    exact_action_payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        for name in (
            "authorization_id", "selected_scenario_id", "belief_state_id",
            "tribunal_receipt_hash", "prescription_manifest_hash",
            "policy_snapshot_hash", "authorized_by",
        ):
            val = getattr(self, name)
            if not isinstance(val, str) or not val.strip():
                raise ContractViolation(f"ActionAuthorization requires non-blank {name}")
        if not isinstance(self.authorized_at, datetime):
            raise ContractViolation("ActionAuthorization requires authorized_at datetime")
        if not isinstance(self.exact_action_payload, (Mapping, dict)) or not self.exact_action_payload:
            raise ContractViolation("ActionAuthorization requires non-empty exact_action_payload")

    def compute_hash(self) -> str:
        return canonical_hash(self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "authorization_id": self.authorization_id,
            "selected_scenario_id": self.selected_scenario_id,
            "belief_state_id": self.belief_state_id,
            "tribunal_receipt_hash": self.tribunal_receipt_hash,
            "prescription_manifest_hash": self.prescription_manifest_hash,
            "policy_snapshot_hash": self.policy_snapshot_hash,
            "authorized_by": self.authorized_by,
            "authorized_at": self.authorized_at.isoformat(),
            "exact_action_payload": dict(self.exact_action_payload),
        }
