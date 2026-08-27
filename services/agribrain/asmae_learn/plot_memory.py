from __future__ import annotations
import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

AGRIBRAIN_ROOT = Path(__file__).resolve().parents[1]
PLOT_MEMORY_ROOT = AGRIBRAIN_ROOT / "artifacts" / "plot_memory"

APPROVED_TARGET_VARIABLES = {
    "row_direction_deg",
    "irrigation_response_delay_days",
    "salinity_persistence",
    "root_zone_water_tendency",
    "canopy_water_response",
    "phenology_timing_offset",
    "recurring_stress_zone",
    "microzone_stability",
}

BLOCKED_TARGET_VARIABLES = {
    "direct crop diagnosis truth",
    "yield ground truth",
    "1m certification",
    "biotic outbreak confirmation",
    "irreversible action success",
    "layer8_action_success",
    "yield_truth_without_harvest_validation"
}

class PlotLearningMemory:
    def __init__(
        self,
        plot_id: str,
        geometry_hash: str,
        crop_season_id: str,
        memory_status: Literal["candidate", "provisional", "validated", "certified_plot_memory", "revoked"] = "candidate",
        revocation_reason: Optional[str] = None,
        evidence_count: int = 0,
        distinct_validation_events: Optional[List[str]] = None,
        first_evidence_time: Optional[str] = None,
        last_evidence_time: Optional[str] = None,
        variables: Optional[Dict[str, Dict[str, Any]]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        memory_content_hash: str = "",
        memory_instance_hash: str = "",
    ):
        self.plot_id = plot_id
        self.geometry_hash = geometry_hash
        self.crop_season_id = crop_season_id
        self.memory_status = memory_status
        self.revocation_reason = revocation_reason
        self.evidence_count = evidence_count
        self.distinct_validation_events = distinct_validation_events or []
        self.first_evidence_time = first_evidence_time
        self.last_evidence_time = last_evidence_time
        self.variables = variables or {}
        self.history = history or []
        self.memory_content_hash = memory_content_hash
        self.memory_instance_hash = memory_instance_hash

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plot_id": self.plot_id,
            "geometry_hash": self.geometry_hash,
            "crop_season_id": self.crop_season_id,
            "memory_status": self.memory_status,
            "revocation_reason": self.revocation_reason,
            "evidence_count": self.evidence_count,
            "distinct_validation_events": sorted(self.distinct_validation_events),
            "first_evidence_time": self.first_evidence_time,
            "last_evidence_time": self.last_evidence_time,
            "variables": self.variables,
            "history": self.history,
            "memory_content_hash": self.memory_content_hash,
            "memory_instance_hash": self.memory_instance_hash,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> PlotLearningMemory:
        return cls(
            plot_id=d["plot_id"],
            geometry_hash=d["geometry_hash"],
            crop_season_id=d["crop_season_id"],
            memory_status=d.get("memory_status", "candidate"),
            revocation_reason=d.get("revocation_reason"),
            evidence_count=d.get("evidence_count", 0),
            distinct_validation_events=d.get("distinct_validation_events"),
            first_evidence_time=d.get("first_evidence_time"),
            last_evidence_time=d.get("last_evidence_time"),
            variables=d.get("variables"),
            history=d.get("history"),
            memory_content_hash=d.get("memory_content_hash", ""),
            memory_instance_hash=d.get("memory_instance_hash", ""),
        )

    def update_hashes(self, timestamp: str) -> None:
        self.memory_content_hash = self.compute_content_hash()
        self.memory_instance_hash = self.compute_instance_hash(timestamp)

    def compute_content_hash(self) -> str:
        d = self.to_dict()
        d.pop("memory_instance_hash", None)
        d.pop("memory_content_hash", None)
        d.pop("history", None)  # exclude history and status change timestamps from content hash to keep it value-focused
        serialized = json.dumps(d, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()

    def compute_instance_hash(self, timestamp: str) -> str:
        payload = {
            "content_hash": self.memory_content_hash,
            "timestamp": timestamp
        }
        serialized = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()

def validate_safe_path_segment(value: Any, name: str) -> None:
    if not value or not isinstance(value, str) or value.strip() == "":
        raise ValueError(f"empty value for path segment: {name}")
    import os
    if ".." in value or "/" in value or "\\" in value or ":" in value:
        raise ValueError(f"unsafe path segment detected in {name}: {value}")


def _geometry_storage_segment(geometry_hash: str) -> str:
    """Map a canonical geometry identifier to one collision-safe path segment.

    Geometry identity is now transported as ``sha256:<digest>``.  The colon is
    part of the scientific identifier but is not a valid Windows path
    character.  Preserve the identifier inside the memory payload while using
    an explicit, reversible-on-format storage representation.  Unknown colon
    forms remain rejected rather than being broadly sanitized.
    """
    import re

    value = str(geometry_hash or "").strip()
    match = re.fullmatch(r"sha256:([0-9a-fA-F]{64})", value)
    if match:
        return f"sha256-{match.group(1).lower()}"
    validate_safe_path_segment(value, "geometry_hash")
    return value

def get_memory_file_path(plot_id: str, geometry_hash: str, crop_season_id: str) -> Path:
    validate_safe_path_segment(plot_id, "plot_id")
    validate_safe_path_segment(crop_season_id, "crop_season_id")
    geometry_segment = _geometry_storage_segment(geometry_hash)
    return PLOT_MEMORY_ROOT / plot_id / geometry_segment / crop_season_id / "memory.json"

def load_plot_memory(plot_id: str, geometry_hash: str, crop_season_id: str) -> Optional[PlotLearningMemory]:
    path = get_memory_file_path(plot_id, geometry_hash, crop_season_id)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return PlotLearningMemory.from_dict(data)
    except Exception:
        return None

def save_plot_memory(memory: PlotLearningMemory) -> None:
    path = get_memory_file_path(memory.plot_id, memory.geometry_hash, memory.crop_season_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).isoformat()
    memory.update_hashes(timestamp)
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(memory.to_dict(), f, indent=2, default=str)

def append_ledger_record(record: dict, ledger_path: Optional[Path] = None) -> None:
    from rollout.rollout_config import VALIDATION_LEDGER_PATH
    path = Path(ledger_path) if ledger_path else VALIDATION_LEDGER_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

def append_update_ledger_record(
    memory: PlotLearningMemory,
    candidate: Dict[str, Any],
    variable: str,
    old_value: Any,
    new_value: Any,
    old_status: str,
    new_status: str,
    ledger_path: Optional[Path] = None
) -> None:
    from datetime import datetime, timezone
    record = {
        "record_type": "memory_update",
        "plot_id": memory.plot_id,
        "geometry_hash": memory.geometry_hash,
        "crop_season_id": memory.crop_season_id,
        "variable": variable,
        "old_value": old_value,
        "new_value": new_value,
        "old_status": old_status,
        "new_status": new_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "memory": {
            "memory_content_hash": memory.memory_content_hash,
            "memory_instance_hash": memory.memory_instance_hash,
            "memory_status": memory.memory_status
        },
        "candidate": {
            "candidate_id": candidate.get("candidate_id"),
            "run_id": candidate.get("run_id"),
            "candidate_type": candidate.get("candidate_type"),
            "validation_event_ids": candidate.get("validation_event_ids", []),
            "disagreement_report_hash": candidate.get("disagreement_report_hash"),
            "validation_trust_score": candidate.get("validation_trust_score", 0.0),
            "agreement_score": candidate.get("agreement_score", 0.0),
            "evidence_count": candidate.get("evidence_count", 0),
        }
    }
    append_ledger_record(record, ledger_path)

def append_demotion_ledger_record(
    plot_id: str,
    geometry_hash: str,
    crop_season_id: str,
    variable: str,
    reason: str,
    trust_penalty: float,
    old_trust: float,
    new_trust: float,
    old_status: str,
    new_status: str,
    ledger_path: Optional[Path] = None
) -> None:
    from datetime import datetime, timezone
    record = {
        "record_type": "memory_demotion",
        "plot_id": plot_id,
        "geometry_hash": geometry_hash,
        "crop_season_id": crop_season_id,
        "variable": variable,
        "reason": reason,
        "trust_penalty": trust_penalty,
        "old_trust": old_trust,
        "new_trust": new_trust,
        "old_status": old_status,
        "new_status": new_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    append_ledger_record(record, ledger_path)

def append_revocation_ledger_record(
    plot_id: str,
    old_geometry_hash: str,
    new_geometry_hash: str,
    old_crop_season_id: str,
    new_crop_season_id: str,
    reason: str,
    ledger_path: Optional[Path] = None
) -> None:
    from datetime import datetime, timezone
    record = {
        "record_type": "memory_revocation",
        "plot_id": plot_id,
        "old_geometry_hash": old_geometry_hash,
        "new_geometry_hash": new_geometry_hash,
        "old_crop_season_id": old_crop_season_id,
        "new_crop_season_id": new_crop_season_id,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    append_ledger_record(record, ledger_path)

def revoke_obsolete_memories(
    plot_id: str,
    new_geometry_hash: str,
    new_crop_season_id: str,
    ledger_path: Optional[Path] = None
) -> None:
    validate_safe_path_segment(plot_id, "plot_id")
    validate_safe_path_segment(new_geometry_hash, "new_geometry_hash")
    validate_safe_path_segment(new_crop_season_id, "new_crop_season_id")
    plot_dir = PLOT_MEMORY_ROOT / plot_id
    if not plot_dir.exists():
        return
        
    from datetime import datetime, timezone
    now_str = datetime.now(timezone.utc).isoformat()
    
    for path in plot_dir.glob("**/memory.json"):
        try:
            rel = path.relative_to(PLOT_MEMORY_ROOT)
            if len(rel.parts) == 4:
                _, geom, season, _ = rel.parts
                if geom != new_geometry_hash or season != new_crop_season_id:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    if data.get("memory_status") != "revoked":
                        reason = ""
                        if geom != new_geometry_hash:
                            reason = "geometry_hash_changed"
                        else:
                            reason = "crop_season_changed"
                            
                        data["memory_status"] = "revoked"
                        data["revocation_reason"] = reason
                        
                        mem = PlotLearningMemory.from_dict(data)
                        mem.update_hashes(now_str)
                        with open(path, "w", encoding="utf-8") as f:
                            json.dump(mem.to_dict(), f, indent=2, default=str)
                            
                        append_revocation_ledger_record(
                            plot_id=plot_id,
                            old_geometry_hash=geom,
                            new_geometry_hash=new_geometry_hash,
                            old_crop_season_id=season,
                            new_crop_season_id=new_crop_season_id,
                            reason=reason,
                            ledger_path=ledger_path
                        )
        except Exception as e:
            print(f"Error revoking obsolete memory at {path}: {e}")
