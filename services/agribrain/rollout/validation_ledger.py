"""
Validation Ledger for ASMAE-Learn.
Records ASMAE execution metadata and agronomist/manual validation feedback
to an append-only JSONL file using event sourcing.
"""

from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from rollout.rollout_config import VALIDATION_LEDGER_PATH

REQUIRED_HASHES = [
    "geometry_hash",
    "layer0_output_hash",
    "asmae_content_hash",
    "asmae_artifact_instance_hash",
]

def _resolve_ledger_path(ledger_path: Optional[Path] = None) -> Path:
    if os.environ.get("AGRIWISE_ARCHIVE_PILOT_MODE") == "true":
        return Path("services/agribrain/artifacts/archive_metrics/asmae_validation_ledger_archive.jsonl")
    return Path(ledger_path) if ledger_path else VALIDATION_LEDGER_PATH

def record_asmae_run(record: Dict[str, Any], ledger_path: Optional[Path] = None) -> Dict[str, Any]:
    """Record an ASMAE run to the validation ledger JSONL file."""
    path = _resolve_ledger_path(ledger_path)
    
    record.setdefault("ledger_version", "v86_validation_ledger_v2")
    record.setdefault("record_type", "asmae_run")
    record.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    
    status = record.get("execution_status", "executed")
    failure_stage = record.get("failure_stage")
    
    is_failed_before = (
        status == "failed_before_execution" or 
        (status == "failed" and failure_stage == "before_execution")
    )
    is_failed_partial = (
        status == "failed_after_partial_execution" or 
        (status == "failed" and failure_stage in ["after_layer0", "after_asmae", "after_cache_write"])
    )
    
    no_hash_required = status in ["rollout_skipped", "backend_disabled"] or is_failed_before
    
    if not no_hash_required:
        if is_failed_partial:
            # Validate only those hashes that are present
            for h_key in REQUIRED_HASHES:
                val = record.get(h_key)
                if val is not None:
                    if not isinstance(val, str) or val.strip() == "":
                        raise ValueError(f"Hash field '{h_key}' is invalid.")
        else:
            # executed, cache_hit, visual_disabled, and others require all hashes
            for h_key in REQUIRED_HASHES:
                val = record.get(h_key)
                if not val or not isinstance(val, str) or val.strip() == "":
                    raise ValueError(f"Required hash field '{h_key}' is missing or empty.")
            
    if record.get("weak_labels_as_ground_truth") or record.get("validation", {}).get("use_weak_labels_as_ground_truth"):
        raise ValueError("Weak labels must never be recorded as ground truth.")
        
    record.setdefault("validation", {
        "manual_validation_status": "pending",
        "farmer_feedback": None,
        "agronomist_feedback": None,
        "field_observation": None
    })
    
    validation_status = record["validation"].get("manual_validation_status", "pending")
    if status in ["rollout_skipped", "backend_disabled"] or is_failed_before or is_failed_partial or status == "failed":
        record["training_use"] = {
            "eligible_for_asmae_learn": False,
            "reason": f"execution_status_{status}"
        }
        record["eligible_for_asmae_learn"] = False
    elif validation_status == "approved":
        record["training_use"] = {
            "eligible_for_asmae_learn": True,
            "reason": "manually_validated_by_agronomist"
        }
        record["eligible_for_asmae_learn"] = True
    else:
        record["training_use"] = {
            "eligible_for_asmae_learn": False,
            "reason": "manual_validation_pending"
        }
        record["eligible_for_asmae_learn"] = False
        
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
        
    return record

def get_run_validation_view(run_id: str, ledger_path: Optional[Path] = None) -> Dict[str, Any]:
    """Reconstruct the latest run validation view by replaying ledger events."""
    path = _resolve_ledger_path(ledger_path)
    if not path.exists():
        return {}

    view: Dict[str, Any] = {}
    validation_events = []
    
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("run_id") != run_id:
                continue
            
            record_type = rec.get("record_type", "asmae_run")
            
            if record_type == "asmae_run":
                view.update(rec)
                view.setdefault("validation_events", [])
            elif record_type == "validation_event":
                validation_events.append(rec)
            elif record_type == "disagreement_report":
                view["agreement_score"] = rec.get("agreement_score")
                view["contradictions"] = rec.get("contradictions")
            elif record_type == "candidate_update":
                status_val = rec.get("learning_candidate_status")
                view["learning_candidate_status"] = status_val
                view["learning_candidate_reasons"] = rec.get("learning_candidate_reasons")
                view["eligible_for_asmae_learn"] = rec.get("eligible_for_asmae_learn")
                if "validation" not in view:
                    view["validation"] = {}
                view["validation"]["manual_validation_status"] = status_val
                if "training_use" in view:
                    view["training_use"]["eligible_for_asmae_learn"] = rec.get("eligible_for_asmae_learn")
                    view["training_use"]["reason"] = ", ".join(rec.get("learning_candidate_reasons", []))
                    
    if not view:
        return {}
        
    view["validation_events"] = validation_events
    return view

def promote_ledger_run_validation(
    run_id: str, 
    validation_status: str, 
    feedback: Optional[Dict[str, Any]] = None,
    ledger_path: Optional[Path] = None
) -> bool:
    """Promotes a run by appending a candidate_update record to the ledger."""
    path = _resolve_ledger_path(ledger_path)
    view = get_run_validation_view(run_id, ledger_path=path)
    if not view:
        return False
        
    candidate_dict = {}
    try:
        from asmae_learn.candidate_builder import build_learning_candidate
        built_cand = build_learning_candidate(view)
        candidate_dict = {
            "candidate_id": built_cand.get("candidate_id"),
            "candidate_type": built_cand.get("candidate_type"),
            "eligible": built_cand.get("eligible", False),
            "blocked_reasons": built_cand.get("blocked_reasons", []),
            "validation_event_ids": built_cand.get("validation_event_ids", []),
            "disagreement_report_hash": built_cand.get("disagreement_report_hash", ""),
            "evidence_count": built_cand.get("evidence_count", 0),
            "validation_trust_score": built_cand.get("validation_trust_score", 0.0),
            "agreement_score": built_cand.get("agreement_score", 0.0),
            "bma_status": built_cand.get("bma_status"),
            "retro_status": built_cand.get("retro_status"),
            "retro_score": built_cand.get("retro_score"),
            "uncertainty": built_cand.get("uncertainty")
        }
    except Exception:
        candidate_dict = {
            "candidate_id": f"cand_{run_id}",
            "candidate_type": "validated_state_candidate",
            "eligible": validation_status == "approved",
            "blocked_reasons": [] if validation_status == "approved" else [f"validation_{validation_status}"],
            "validation_event_ids": [],
            "disagreement_report_hash": "",
            "evidence_count": 0,
            "validation_trust_score": 1.0 if validation_status == "approved" else 0.0,
            "agreement_score": 1.0 if validation_status == "approved" else 0.0,
            "bma_status": view.get("bma_status"),
            "retro_status": view.get("retro_status"),
            "retro_score": view.get("retro_mean_score"),
            "uncertainty": view.get("uncertainty")
        }
        
    record = {
        "record_type": "candidate_update",
        "ledger_version": "v86_validation_ledger_v2",
        "run_id": run_id,
        "plot_id": view.get("plot_id"),
        "learning_candidate_status": "approved" if validation_status == "approved" else "rejected",
        "learning_candidate_reasons": ["manually_validated_by_agronomist"] if validation_status == "approved" else [f"validation_{validation_status}"],
        "eligible_for_asmae_learn": validation_status == "approved",
        "candidate": candidate_dict,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
        
    return True
