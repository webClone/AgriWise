"""Frozen schema contracts for ASMAE World Model V1 (Workstreams W1-W8 + P1-1..P1-4)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


WORLD_MODEL_CONTRACT_VERSION = "asmae_world_model_v1"

CONFIRMED_SCOUTING_STATUSES = frozenset({
    "CONFIRMED",
    "VERIFIED",
    "APPROVED",
    "VALIDATION_CONFIRMED",
})

FALLBACK_TENANT_TOKENS = frozenset({
    "",
    "default_tenant",
    "unknown",
    "none",
    "null",
    "unassigned",
    "dev",
    "isolated_dev",
    "sandbox",
})

ALLOWED_CALIBRATION_AUTHORITIES = frozenset({
    "calibrated",
    "verified",
    "factory_certified",
    "field_calibrated",
})

CALIBRATION_STATUS_VENDOR_UNVERIFIED = "vendor_known_unverified_calibration"

FAILURE_CAUSE_CODES = frozenset({
    "unverified_domain_identity",
    "insufficient_observations",
    "regime_transition_mismatch",
    "wrong_physical_prior",
    "systematic_bias",
    "poor_uncertainty_calibration",
    "missing_field_validation",
    "model_skill_below_baseline",
})


def _to_json_safe(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_to_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_to_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    return value


@dataclass(frozen=True)
class DomainIdentityContract:
    """Strict provenance and identity verification status for a plot."""

    plot_id: str
    tenant_id: Optional[str]
    farm_id: Optional[str]
    tenant_identity_verified: bool
    is_isolated_dev_fixture: bool
    tenant_resolution_source: str
    crop_identity_verified: bool
    synthetic_label_rejected: bool
    crop_resolution_source: str
    resolved_crop_code: str
    crop_variety: Optional[str] = None
    crop_architecture_class: Optional[str] = None
    soil_identity_verified: bool = False
    soil_texture: str = "loam"
    soil_resolution_source: str = "fallback_unverified"
    identity_block_reasons: Tuple[str, ...] = ()
    diagnostic_fallback_crop: Optional[str] = None
    plot_name: Optional[str] = None

    def qualifies_for_crop_identity(self) -> bool:
        return bool(self.crop_identity_verified)

    def to_dict(self) -> Dict[str, Any]:
        return _to_json_safe(asdict(self))


@dataclass(frozen=True)
class CropIntervalRecord:
    """Bitemporal crop planting/harvest interval record."""

    record_id: str
    crop_code: str
    variety: Optional[str]
    status: str
    valid_from: Optional[str]
    valid_to: Optional[str]
    known_from: Optional[str]
    source: str
    verified: bool
    synthetic_rejected: bool = False
    architecture_class: Optional[str] = None
    estimated_yield: Optional[float] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return _to_json_safe(asdict(self))


@dataclass(frozen=True)
class SoilRevisionRecord:
    """Bitemporal soil analysis or baseline texture record."""

    record_id: str
    texture: Optional[str]
    ph: Optional[float]
    ec: Optional[float]
    organic_matter: Optional[float]
    nitrogen: Optional[float]
    phosphorus: Optional[float]
    potassium: Optional[float]
    depth_from_cm: Optional[float]
    depth_to_cm: Optional[float]
    valid_from: Optional[str]
    known_from: Optional[str]
    source: str
    verified: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return _to_json_safe(asdict(self))


@dataclass(frozen=True)
class ManagementLogRecord:
    """Bitemporal agronomic task or completed management execution record."""

    record_id: str
    task_type: str
    title: str
    completed: bool
    is_confirmed_execution: bool
    valid_from: Optional[str]
    known_from: Optional[str]
    source: str
    crop_cycle_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return _to_json_safe(asdict(self))


@dataclass(frozen=True)
class ScoutingRecord:
    """Bitemporal crop observation separating unconfirmed scouting vs verified confirmation (P1-3)."""

    record_id: str
    obs_type: str
    title: str
    severity: Optional[str]
    observed_at: Optional[str]
    created_at: Optional[str]
    is_confirmed: bool
    confirmation_status: str
    confirmation_evidence: Dict[str, Any] = field(default_factory=dict)
    description: Optional[str] = None
    crop_cycle_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return _to_json_safe(asdict(self))


@dataclass(frozen=True)
class ScientificFailureDiagnosis:
    """Structured root-cause scientific diagnosis for non-qualifying plots or horizons (W7)."""

    plot_id: str
    primary_cause: Optional[str]
    causes: Tuple[str, ...] = ()
    details: Dict[str, Any] = field(default_factory=dict)
    recommended_evidence_to_unblock: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return _to_json_safe(asdict(self))


__all__ = [
    "ALLOWED_CALIBRATION_AUTHORITIES",
    "CALIBRATION_STATUS_VENDOR_UNVERIFIED",
    "CONFIRMED_SCOUTING_STATUSES",
    "CropIntervalRecord",
    "DomainIdentityContract",
    "FAILURE_CAUSE_CODES",
    "FALLBACK_TENANT_TOKENS",
    "ManagementLogRecord",
    "ScoutingRecord",
    "ScientificFailureDiagnosis",
    "SoilRevisionRecord",
    "WORLD_MODEL_CONTRACT_VERSION",
]
