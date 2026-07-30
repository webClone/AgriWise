from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from asmae_learn.schemas import ValidationEvent
from asmae_learn.disagreement import check_disagreement
from asmae_learn.candidate_builder import build_learning_candidate
from rollout.validation_ledger import get_run_validation_view, VALIDATION_LEDGER_PATH

def add_validation_event_to_ledger(
    run_id: str, 
    event_data: Dict[str, Any], 
    ledger_path: Optional[Path] = None
) -> bool:
    """Ties a validation event to a specific run in the ledger and triggers eligibility checks."""
    path = Path(ledger_path) if ledger_path else VALIDATION_LEDGER_PATH
    
    view = get_run_validation_view(run_id, ledger_path=path)
    if not view:
        return False
        
    event_data.setdefault("plot_id", view.get("plot_id"))
    event_data.setdefault("geometry_hash", view.get("geometry_hash"))
    event_data.setdefault("run_id", run_id)
    event_data.setdefault("event_time", datetime.now(timezone.utc).isoformat())
    event_data.setdefault("created_at", datetime.now(timezone.utc).isoformat())

    event = ValidationEvent(**event_data)
    
    event_dict = {
        "record_type": "validation_event",
        "ledger_version": "v86_validation_ledger_v2",
        "run_id": run_id,
        "plot_id": event.plot_id,
        "event_id": event.event_id,
        "zone_id": event.zone_id,
        "geometry_hash": event.geometry_hash,
        "event_time": event.event_time,
        "source_type": event.source_type,
        "target_variable": event.target_variable,
        "observed_value": event.observed_value,
        "observed_unit": event.observed_unit,
        "spatial_scope": event.spatial_scope,
        "temporal_scope": event.temporal_scope,
        "confidence": event.confidence,
        "validator_role": event.validator_role,
        "trust_weight": event.trust_weight,
        "evidence_hash": event.evidence_hash,
        "attachment_refs": event.attachment_refs,
        "notes": event.notes,
        "created_at": event.created_at,
        "event_hash": event.event_hash,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event_dict) + "\n")
        
    updated_view = get_run_validation_view(run_id, ledger_path=path)
    
    events = []
    for ev_dict in updated_view.get("validation_events", []):
        from dataclasses import fields
        valid_keys = {f.name for f in fields(ValidationEvent)}
        init_args = {k: v for k, v in ev_dict.items() if k in valid_keys}
        events.append(ValidationEvent(**init_args))
        
    disagreement_report = check_disagreement(updated_view, events)
    
    disagreement_record = {
        "record_type": "disagreement_report",
        "ledger_version": "v86_validation_ledger_v2",
        "run_id": run_id,
        "plot_id": updated_view["plot_id"],
        "agreement_score": disagreement_report["agreement_score"],
        "contradictions": disagreement_report["contradictions"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(disagreement_record) + "\n")
        
    final_view = get_run_validation_view(run_id, ledger_path=path)
    
    candidate = build_learning_candidate(final_view)
    
    status_val = "approved" if candidate["eligible"] else candidate.get("learning_candidate_status", "pending")
    reasons_val = ["validation_event_verified"] if candidate["eligible"] else candidate["blocked_reasons"]
    
    candidate_record = {
        "record_type": "candidate_update",
        "ledger_version": "v86_validation_ledger_v2",
        "run_id": run_id,
        "plot_id": final_view["plot_id"],
        "learning_candidate_status": status_val,
        "learning_candidate_reasons": reasons_val,
        "eligible_for_asmae_learn": candidate["eligible"],
        "candidate": {
            "candidate_id": candidate.get("candidate_id"),
            "candidate_type": candidate.get("candidate_type"),
            "eligible": candidate.get("eligible", False),
            "blocked_reasons": candidate.get("blocked_reasons", []),
            "validation_event_ids": candidate.get("validation_event_ids", []),
            "disagreement_report_hash": candidate.get("disagreement_report_hash", ""),
            "evidence_count": candidate.get("evidence_count", 0),
            "validation_trust_score": candidate.get("validation_trust_score", 0.0),
            "agreement_score": candidate.get("agreement_score", 0.0),
            "bma_status": candidate.get("bma_status"),
            "retro_status": candidate.get("retro_status"),
            "retro_score": candidate.get("retro_score"),
            "uncertainty": candidate.get("uncertainty")
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(candidate_record) + "\n")
        
    return True
