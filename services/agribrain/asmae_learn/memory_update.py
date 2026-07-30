from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from asmae_learn.plot_memory import (
    APPROVED_TARGET_VARIABLES,
    BLOCKED_TARGET_VARIABLES,
    PlotLearningMemory,
    load_plot_memory,
    save_plot_memory,
    revoke_obsolete_memories,
    append_update_ledger_record,
    append_demotion_ledger_record,
    append_revocation_ledger_record,
)

def check_candidate_eligibility(candidate: Dict[str, Any]) -> None:
    # check if eligible is true
    if not candidate.get("eligible"):
        raise ValueError("candidate_not_eligible")
    
    # check candidate_type in allowed
    allowed_candidate_types = {"validated_state_candidate", "zone_memory_candidate"}
    if candidate.get("candidate_type") not in allowed_candidate_types:
        raise ValueError("candidate_not_eligible")
        
    # check validation_event_ids
    if not candidate.get("validation_event_ids"):
        raise ValueError("missing_validation_event_ids")
        
    # check disagreement_report_hash
    if not candidate.get("disagreement_report_hash"):
        raise ValueError("missing_disagreement_report_hash")
        
    # check lineage hashes (hardened global lineage checks)
    required_lineage = [
        "plot_id",
        "run_id",
        "geometry_hash",
        "layer0_output_hash",
        "asmae_content_hash",
        "asmae_artifact_instance_hash",
    ]
    for key in required_lineage:
        val = candidate.get(key)
        if not val or not isinstance(val, str) or val.strip() == "":
            raise ValueError("missing_lineage_hash")
        
    # check blocked_reasons
    if candidate.get("blocked_reasons"):
        raise ValueError("candidate_has_blocked_reasons")

def update_plot_memory(
    candidate: Dict[str, Any],
    crop_context: Optional[Dict[str, Any]] = None,
    candidate_value: Optional[float] = None,
    candidate_confidence: Optional[float] = None,
    contradictions: Optional[List[Dict[str, Any]]] = None,
    ledger_path: Optional[Path] = None,
) -> PlotLearningMemory:
    # 1. Eligibility Check
    check_candidate_eligibility(candidate)
    
    # 2. Variable Allowed check
    target_var = candidate.get("target_variable")
    if target_var in BLOCKED_TARGET_VARIABLES:
        raise ValueError(f"unapproved_target_variable: {target_var} is blocked")
    if target_var not in APPROVED_TARGET_VARIABLES:
        raise ValueError(f"unapproved_target_variable: {target_var}")
        
    plot_id = candidate["plot_id"]
    geom_hash = candidate["geometry_hash"]
    crop_season_id = (crop_context or {}).get("crop_season_id") or candidate.get("crop_season_id") or "default_season"
    
    # 3. Load or initialize memory
    memory = load_plot_memory(plot_id, geom_hash, crop_season_id)
    if not memory:
        # Revoke other memories for same plot first
        revoke_obsolete_memories(plot_id, geom_hash, crop_season_id, ledger_path)
        memory = PlotLearningMemory(
            plot_id=plot_id,
            geometry_hash=geom_hash,
            crop_season_id=crop_season_id,
            memory_status="candidate"
        )
        
    # Check if memory is revoked
    if memory.memory_status == "revoked":
        # Do not update revoked memory
        return memory

    # 4. Handle Contradictions (High/Critical)
    for c in (contradictions or []):
        severity = c.get("severity")
        if severity == "critical":
            # Revoke memory
            memory.memory_status = "revoked"
            memory.revocation_reason = "critical_contradiction"
            memory.variables = {}
            save_plot_memory(memory)
            append_revocation_ledger_record(
                plot_id=plot_id,
                old_geometry_hash=geom_hash,
                new_geometry_hash=geom_hash,
                old_crop_season_id=crop_season_id,
                new_crop_season_id=crop_season_id,
                reason="critical_contradiction",
                ledger_path=ledger_path
            )
            return memory
        elif severity == "high":
            # Demote memory
            old_status = memory.memory_status
            status_order = ["candidate", "provisional", "validated", "certified_plot_memory"]
            try:
                idx = status_order.index(memory.memory_status)
                new_status = status_order[max(0, idx - 1)]
            except ValueError:
                new_status = "candidate"
            memory.memory_status = new_status
            
            # Apply trust penalty of 0.3 to target variable
            var = c.get("variable") or target_var
            var_data = memory.variables.get(var)
            if var_data:
                old_trust = var_data.get("trust", 0.0)
                new_trust = max(0.0, old_trust - 0.3)
                var_data["trust"] = new_trust
                
                append_demotion_ledger_record(
                    plot_id=plot_id,
                    geometry_hash=geom_hash,
                    crop_season_id=crop_season_id,
                    variable=var,
                    reason="high_contradiction",
                    trust_penalty=0.3,
                    old_trust=old_trust,
                    new_trust=new_trust,
                    old_status=old_status,
                    new_status=new_status,
                    ledger_path=ledger_path
                )
            save_plot_memory(memory)
            return memory

    # 5. Extract Candidate trust & value & confidence (Require explicit value/confidence)
    candidate_trust = candidate.get("validation_trust_score", 0.5)
    events = candidate.get("validation_events") or []
    
    resolved_val = candidate_value
    resolved_conf = candidate_confidence
    
    event = None
    if events:
        event = events[0]
        
    if resolved_val is None:
        if event is not None:
            resolved_val = event.get("observed_value") if isinstance(event, dict) else getattr(event, "observed_value", None)
            if resolved_val is None:
                candidate.setdefault("blocked_reasons", []).append("missing_candidate_value")
                raise ValueError("missing_candidate_value")
        else:
            candidate.setdefault("blocked_reasons", []).append("missing_validation_event_payload")
            raise ValueError("missing_validation_event_payload")
            
    if resolved_conf is None:
        if event is not None:
            resolved_conf = event.get("confidence") if isinstance(event, dict) else getattr(event, "confidence", None)
            if resolved_conf is None:
                candidate.setdefault("blocked_reasons", []).append("missing_candidate_confidence")
                raise ValueError("missing_candidate_confidence")
        else:
            candidate.setdefault("blocked_reasons", []).append("missing_validation_event_payload")
            raise ValueError("missing_validation_event_payload")
            
    candidate_value = resolved_val
    candidate_confidence = resolved_conf

    # 6. EMA Update
    alpha = 0.2
    var_data = memory.variables.setdefault(target_var, {
        "value": 0.5,
        "trust": 0.0,
        "confidence": 0.0,
        "evidence_count": 0
    })
    
    old_value = var_data["value"]
    old_trust = var_data["trust"]
    old_confidence = var_data["confidence"]
    old_ev_count = var_data["evidence_count"]
    
    if old_ev_count == 0:
        new_value = candidate_value
        new_trust = min(0.95, candidate_trust)
        new_confidence = candidate_confidence
    else:
        new_value = alpha * candidate_value + (1 - alpha) * old_value
        new_trust = min(0.95, alpha * candidate_trust + (1 - alpha) * old_trust)
        new_confidence = alpha * candidate_confidence + (1 - alpha) * old_confidence
        
    var_data["value"] = round(new_value, 4)
    var_data["trust"] = round(new_trust, 4)
    var_data["confidence"] = round(new_confidence, 4)
    var_data["evidence_count"] = old_ev_count + 1

    # 7. Update memory-level metadata
    memory.evidence_count += 1
    new_event_ids = candidate.get("validation_event_ids", [])
    for ev_id in new_event_ids:
        if ev_id not in memory.distinct_validation_events:
            memory.distinct_validation_events.append(ev_id)
            
    # Event time tracking
    event_time_str = candidate.get("timestamp") or candidate.get("event_time")
    if not event_time_str and events:
        event_time_str = events[0].get("event_time") if isinstance(events[0], dict) else getattr(events[0], "event_time", None)
    if not event_time_str:
        from datetime import datetime, timezone
        event_time_str = datetime.now(timezone.utc).isoformat()
        
    if not memory.first_evidence_time:
        memory.first_evidence_time = event_time_str
    memory.last_evidence_time = event_time_str
    
    # Calculate time span
    from datetime import datetime
    time_span_days = 0.0
    if memory.first_evidence_time and memory.last_evidence_time:
        try:
            t1 = datetime.fromisoformat(memory.first_evidence_time.replace("Z", "+00:00"))
            t2 = datetime.fromisoformat(memory.last_evidence_time.replace("Z", "+00:00"))
            time_span_days = (t2 - t1).total_seconds() / 86400.0
        except Exception:
            pass

    # 8. Status Promotion
    old_status = memory.memory_status
    meets_cert = (
        memory.evidence_count >= 5 and
        len(memory.distinct_validation_events) >= 3 and
        new_trust >= 0.70 and
        time_span_days >= 14.0
    )
    
    if meets_cert:
        memory.memory_status = "certified_plot_memory"
    elif memory.evidence_count >= 3:
        memory.memory_status = "validated"
    elif memory.evidence_count >= 1:
        memory.memory_status = "provisional"
    else:
        memory.memory_status = "candidate"
        
    # Save & Ledger log
    save_plot_memory(memory)
    
    append_update_ledger_record(
        memory=memory,
        candidate=candidate,
        variable=target_var,
        old_value=old_value if old_ev_count > 0 else None,
        new_value=var_data["value"],
        old_status=old_status,
        new_status=memory.memory_status,
        ledger_path=ledger_path
    )
    
    return memory
