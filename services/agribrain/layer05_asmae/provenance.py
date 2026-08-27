"""
ASMAE Provenance Tracking.

Every ASMAE run produces a full provenance record that includes:
  - Input fingerprint (geometry hash, source package hashes)
  - Run metadata (run_id, mode, timestamps)
  - Scene inventory (which scenes used, quality scores)
  - Resolution decision provenance
  - Invariant violation log
  - Operator manifests used
  - Content hash for deterministic verification
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


def _clean_summary_item(item: Any) -> Any:
    if isinstance(item, dict):
        cleaned = {}
        for k, v in item.items():
            s_val = str(v)
            if s_val.startswith("[[") or s_val.startswith("array("):
                cleaned[k] = "<array_data_omitted>"
            else:
                cleaned[k] = _clean_summary_item(v)
        return cleaned
    if isinstance(item, list):
        return [_clean_summary_item(x) for x in item]
    return item


@dataclass
class ASMAEProvenance:
    """Full provenance record for an ASMAE run."""

    # Identity
    run_id: str = ""
    plot_id: str = ""
    schema_version: str = "asmae_v1"
    mode: str = "shadow"

    # Timestamps
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Input fingerprints
    geometry_hash: str = ""
    layer0_hash: str = ""
    layer1_hash: str = ""
    coarse_priors_hash: str = ""

    # Scene inventory
    scenes_available: int = 0
    scenes_used: int = 0
    scenes_rejected: int = 0
    scene_summary: List[Dict[str, Any]] = field(default_factory=list)

    # Resolution decision
    resolution_tested: List[int] = field(default_factory=list)
    resolution_selected_m: int = 10
    resolution_reason_codes: List[str] = field(default_factory=list)

    # Operator manifests
    operator_manifest_refs: List[str] = field(default_factory=list)

    # Invariant violations
    invariant_violations: List[Dict[str, Any]] = field(default_factory=list)

    # Certification
    certification_level: str = "provisional"
    retro_score: Optional[float] = None

    # Audit trail
    audit_log: List[Dict[str, Any]] = field(default_factory=list)

    # V922: Selected operator bundle identity
    selected_operator_bundle_hash: str = ""
    selected_operators_rebuilt: bool = False
    selected_operator_count: int = 0

    # Deterministic hash
    content_hash: str = ""

    def compute_content_hash(self) -> str:
        """Compute deterministic hash from provenance state."""
        payload = {
            "run_id": self.run_id,
            "plot_id": self.plot_id,
            "mode": self.mode,
            "geometry_hash": self.geometry_hash,
            "layer0_hash": self.layer0_hash,
            "scenes_used": self.scenes_used,
            "resolution_selected_m": self.resolution_selected_m,
            "certification_level": self.certification_level,
        }
        raw = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.content_hash = hashlib.sha256(raw).hexdigest()
        return self.content_hash

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for storage."""
        cleaned_scenes = [_clean_summary_item(s) for s in self.scene_summary]
        return {
            "run_id": self.run_id,
            "plot_id": self.plot_id,
            "schema_version": self.schema_version,
            "mode": self.mode,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "geometry_hash": self.geometry_hash,
            "scenes_available": self.scenes_available,
            "scenes_used": self.scenes_used,
            "scenes_rejected": self.scenes_rejected,
            "scene_summary": cleaned_scenes,
            "resolution_tested": self.resolution_tested,
            "resolution_selected_m": self.resolution_selected_m,
            "resolution_reason_codes": self.resolution_reason_codes,
            "operator_manifest_refs": self.operator_manifest_refs,
            "invariant_violations": self.invariant_violations,
            "certification_level": self.certification_level,
            "retro_score": self.retro_score,
            "audit_log": self.audit_log,
            "selected_operator_bundle_hash": self.selected_operator_bundle_hash,
            "selected_operators_rebuilt": self.selected_operators_rebuilt,
            "selected_operator_count": self.selected_operator_count,
            "content_hash": self.content_hash,
        }


@dataclass
class ASMAEAuditStep:
    """Single step in the ASMAE audit trail."""
    step: str
    timestamp: Optional[datetime] = None
    duration_ms: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "duration_ms": self.duration_ms,
            **self.details,
        }
