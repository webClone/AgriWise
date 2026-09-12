"""Canonical Evidence Receipt Contract.

Provides immutable proof of physical evidence, calibration, spatial support,
and allowed action scope for diagnostic contributions seeking prescription eligibility.
Separated from StageReceipt (which certifies stage execution integrity).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


def _ensure_utc(dt: Union[datetime, str]) -> datetime:
    if isinstance(dt, str):
        return datetime.fromisoformat(dt.replace("Z", "+00:00")).astimezone(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class EvidenceReceipt:
    """Canonical proof that physical observation evidence supports a diagnostic contribution."""

    receipt_id: str
    contribution_id: str
    evidence_ids: Tuple[str, ...] = ()
    content_hashes: Tuple[str, ...] = ()
    capture_manifest_id: Optional[str] = None
    calibration_certificate_id: Optional[str] = None
    spatial_support: Dict[str, Any] = field(default_factory=dict)
    observation_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    validity_interval: Tuple[datetime, datetime] = field(
        default_factory=lambda: (datetime.now(timezone.utc), datetime.now(timezone.utc))
    )
    freshness_expiry: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    truth_class: str = "DERIVED_MODEL_INFERRED"
    measurement_units: str = "dimensionless"
    originating_stage_receipt_id: str = ""
    action_classes_allowed: Tuple[str, ...] = ()
    is_calibrated: bool = True
    calibration_valid: bool = True
    spatial_support_valid: bool = True
    audit_metadata: Dict[str, Any] = field(default_factory=dict)

    def is_valid_for_action(
        self,
        action_class: str,
        reference_time: Optional[datetime] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Verify if this evidence receipt qualifies for a specific prescriptive action class."""
        ref_time = _ensure_utc(reference_time) if reference_time else datetime.now(timezone.utc)

        # 1. Calibration validity
        if not self.is_calibrated or not self.calibration_valid:
            return False, "UNCALIBRATED_EVIDENCE"

        # 2. Expiration / freshness
        expiry = _ensure_utc(self.freshness_expiry)
        if ref_time > expiry:
            return False, f"EVIDENCE_EXPIRED:{ref_time.isoformat()}>{expiry.isoformat()}"

        # 3. Validity window check
        if self.validity_interval and len(self.validity_interval) == 2:
            start_v = _ensure_utc(self.validity_interval[0])
            end_v = _ensure_utc(self.validity_interval[1])
            if ref_time < start_v or ref_time > end_v:
                return False, f"OUTSIDE_VALIDITY_INTERVAL:[{start_v.isoformat()},{end_v.isoformat()}]"

        # 4. Spatial support check
        if not self.spatial_support_valid or not self.spatial_support:
            return False, "INVALID_SPATIAL_SUPPORT"

        # 5. Action class authorization
        if self.action_classes_allowed:
            # If explicit action classes are defined, target must be in allowed list or allow wildcard
            if "*" not in self.action_classes_allowed and action_class not in self.action_classes_allowed:
                return False, f"ACTION_CLASS_NOT_ALLOWED:{action_class}"

        return True, None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "contribution_id": self.contribution_id,
            "evidence_ids": list(self.evidence_ids),
            "content_hashes": list(self.content_hashes),
            "capture_manifest_id": self.capture_manifest_id,
            "calibration_certificate_id": self.calibration_certificate_id,
            "spatial_support": dict(self.spatial_support),
            "observation_timestamp": _ensure_utc(self.observation_timestamp).isoformat(),
            "validity_interval": [
                _ensure_utc(self.validity_interval[0]).isoformat(),
                _ensure_utc(self.validity_interval[1]).isoformat(),
            ] if len(self.validity_interval) == 2 else [],
            "freshness_expiry": _ensure_utc(self.freshness_expiry).isoformat(),
            "truth_class": self.truth_class,
            "measurement_units": self.measurement_units,
            "originating_stage_receipt_id": self.originating_stage_receipt_id,
            "action_classes_allowed": list(self.action_classes_allowed),
            "is_calibrated": self.is_calibrated,
            "calibration_valid": self.calibration_valid,
            "spatial_support_valid": self.spatial_support_valid,
            "audit_metadata": dict(self.audit_metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EvidenceReceipt:
        raw_val = data.get("validity_interval") or []
        if isinstance(raw_val, (list, tuple)) and len(raw_val) == 2:
            val_interval = (_ensure_utc(raw_val[0]), _ensure_utc(raw_val[1]))
        else:
            now = datetime.now(timezone.utc)
            val_interval = (now, now)

        return cls(
            receipt_id=str(data.get("receipt_id", "")),
            contribution_id=str(data.get("contribution_id", "")),
            evidence_ids=tuple(str(x) for x in data.get("evidence_ids", ())),
            content_hashes=tuple(str(x) for x in data.get("content_hashes", ())),
            capture_manifest_id=data.get("capture_manifest_id"),
            calibration_certificate_id=data.get("calibration_certificate_id"),
            spatial_support=dict(data.get("spatial_support") or {}),
            observation_timestamp=_ensure_utc(data.get("observation_timestamp") or datetime.now(timezone.utc)),
            validity_interval=val_interval,
            freshness_expiry=_ensure_utc(data.get("freshness_expiry") or datetime.now(timezone.utc)),
            truth_class=str(data.get("truth_class", "DERIVED_MODEL_INFERRED")),
            measurement_units=str(data.get("measurement_units", "dimensionless")),
            originating_stage_receipt_id=str(data.get("originating_stage_receipt_id", "")),
            action_classes_allowed=tuple(str(x) for x in data.get("action_classes_allowed", ())),
            is_calibrated=bool(data.get("is_calibrated", True)),
            calibration_valid=bool(data.get("calibration_valid", True)),
            spatial_support_valid=bool(data.get("spatial_support_valid", True)),
            audit_metadata=dict(data.get("audit_metadata") or {}),
        )


def create_evidence_receipt(
    *,
    contribution_id: str,
    evidence_ids: Sequence[str] = (),
    content_hashes: Sequence[str] = (),
    capture_manifest_id: Optional[str] = None,
    calibration_certificate_id: Optional[str] = None,
    spatial_support: Optional[Dict[str, Any]] = None,
    observation_timestamp: Optional[datetime] = None,
    validity_interval: Optional[Tuple[datetime, datetime]] = None,
    freshness_expiry: Optional[datetime] = None,
    truth_class: str = "DERIVED_MODEL_INFERRED",
    measurement_units: str = "dimensionless",
    originating_stage_receipt_id: str = "",
    action_classes_allowed: Sequence[str] = (),
    is_calibrated: bool = True,
    calibration_valid: bool = True,
    spatial_support_valid: bool = True,
    audit_metadata: Optional[Dict[str, Any]] = None,
) -> EvidenceReceipt:
    """Convenience factory creating a content-addressed EvidenceReceipt."""
    obs_time = _ensure_utc(observation_timestamp or datetime.now(timezone.utc))
    expiry = _ensure_utc(freshness_expiry or obs_time)
    val_int = validity_interval or (obs_time, expiry)

    hash_basis = {
        "contribution_id": contribution_id,
        "evidence_ids": list(evidence_ids),
        "content_hashes": list(content_hashes),
        "capture_manifest_id": capture_manifest_id,
        "calibration_certificate_id": calibration_certificate_id,
        "spatial_support": spatial_support or {},
        "observation_timestamp": obs_time.isoformat(),
        "truth_class": truth_class,
        "measurement_units": measurement_units,
        "originating_stage_receipt_id": originating_stage_receipt_id,
        "action_classes_allowed": list(action_classes_allowed),
    }
    receipt_bytes = json.dumps(hash_basis, sort_keys=True, separators=(",", ":")).encode("utf-8")
    receipt_id = f"evrec-{hashlib.sha256(receipt_bytes).hexdigest()[:24]}"

    return EvidenceReceipt(
        receipt_id=receipt_id,
        contribution_id=contribution_id,
        evidence_ids=tuple(evidence_ids),
        content_hashes=tuple(content_hashes),
        capture_manifest_id=capture_manifest_id,
        calibration_certificate_id=calibration_certificate_id,
        spatial_support=dict(spatial_support or {}),
        observation_timestamp=obs_time,
        validity_interval=val_int,
        freshness_expiry=expiry,
        truth_class=truth_class,
        measurement_units=measurement_units,
        originating_stage_receipt_id=originating_stage_receipt_id,
        action_classes_allowed=tuple(action_classes_allowed),
        is_calibrated=is_calibrated,
        calibration_valid=calibration_valid,
        spatial_support_valid=spatial_support_valid,
        audit_metadata=dict(audit_metadata or {}),
    )
