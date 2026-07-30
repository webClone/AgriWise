import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Literal, Optional

@dataclass
class V90CertificationRecord:
    # ID/Metadata
    certification_id: str
    certification_schema_version: str = "v90"
    certification_policy_version: str = "1.0.0"

    # Subject details
    plot_id: str = ""
    geometry_hash: str = ""
    crop_season_id: str = ""
    variable: str = ""
    surface_id: str = ""
    time_window_start: str = ""
    time_window_end: str = ""

    # Resolution details
    inference_resolution_m: float = 1.0
    native_observation_basis_m: float = 10.0
    certified_basis: str = ""

    # Status parameters
    status: Literal["candidate", "eligible_pending_review", "certified", "revoked", "expired", "rejected"] = "candidate"
    certified_at: Optional[str] = None
    expires_at: Optional[str] = None  # Mandatory for status == "certified"

    # Summary dictionaries
    spatial_holdout_summary: Dict[str, Any] = field(default_factory=dict)
    temporal_holdout_summary: Dict[str, Any] = field(default_factory=dict)
    radiometric_summary: Dict[str, Any] = field(default_factory=dict)
    bma_summary: Dict[str, Any] = field(default_factory=dict)
    contradiction_summary: Dict[str, Any] = field(default_factory=dict)

    # Lineage hashes
    layer0_output_hash: str = ""
    asmae_content_hash: str = ""
    asmae_artifact_instance_hash: str = ""
    memory_content_hash: str = ""
    report_verified_evidence_hash: str = ""

    # Production approval metadata
    approved_by: Optional[str] = None
    approved_role: Optional[str] = None
    approved_at: Optional[str] = None
    approval_reason: Optional[str] = None
    approval_hash: Optional[str] = None
    approval_mode: Optional[Literal["automatic_test_only", "manual_admin"]] = None

    # Cryptographic auditing
    certification_hash: str = ""
    certification_instance_hash: str = ""

    # Administrative details
    limitations: Optional[str] = None
    revocation_reason: Optional[str] = None
    revoked_at: Optional[str] = None
    revocation_event_hash: Optional[str] = None

    def calculate_certification_hash(self) -> str:
        """
        Calculates a deterministic content hash.
        Excludes certified_at, revoked_at, certification_instance_hash, revocation_reason,
        revocation_event_hash, approved_by, approved_role, approved_at, approval_reason, approval_hash, approval_mode, and status.
        """
        data = asdict(self)
        # Exclude mutable/instance fields
        exclude_fields = [
            "certified_at",
            "revoked_at",
            "revocation_reason",
            "revocation_event_hash",
            "certification_instance_hash",
            "approved_by",
            "approved_role",
            "approved_at",
            "approval_reason",
            "approval_hash",
            "approval_mode",
            "status",
            "certification_hash"  # must exclude itself
        ]
        filtered_data = {k: v for k, v in data.items() if k not in exclude_fields}
        # Serialize deterministically
        serialized = json.dumps(filtered_data, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def calculate_certification_instance_hash(self) -> str:
        """
        Calculates the instance hash, which covers certification_hash plus mutable fields/metadata:
        certified_at, approved_by, approved_at, approval_mode, status, revocation_reason, revoked_at.
        """
        # Ensure we have the base hash calculated
        base_hash = self.certification_hash or self.calculate_certification_hash()
        
        instance_data = {
            "certification_hash": base_hash,
            "status": self.status,
            "certified_at": self.certified_at,
            "revoked_at": self.revoked_at,
            "revocation_reason": self.revocation_reason,
            "revocation_event_hash": self.revocation_event_hash,
            "approved_by": self.approved_by,
            "approved_role": self.approved_role,
            "approved_at": self.approved_at,
            "approval_reason": self.approval_reason,
            "approval_hash": self.approval_hash,
            "approval_mode": self.approval_mode,
        }
        serialized = json.dumps(instance_data, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def validate_for_status(self) -> None:
        if self.status == "certified":
            required_fields = [
                "geometry_hash",
                "crop_season_id",
                "variable",
                "time_window_start",
                "time_window_end",
                "expires_at",
                "layer0_output_hash",
                "asmae_content_hash",
                "asmae_artifact_instance_hash",
                "report_verified_evidence_hash"
            ]
            for field_name in required_fields:
                val = getattr(self, field_name)
                if val is None or val == "":
                    raise ValueError(f"Field '{field_name}' is required when status is 'certified'.")

    def __post_init__(self) -> None:
        self.validate_for_status()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "V90CertificationRecord":
        return cls(**data)


@dataclass
class V90ResolutionResult:
    approved: bool
    reason_codes: List[str]
    record: Optional[V90CertificationRecord] = None
    certification_id: Optional[str] = None
    certification_status: Optional[str] = None
