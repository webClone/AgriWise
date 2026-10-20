from __future__ import annotations
import hashlib
import json
from typing import Any, Dict, List, Optional
try:
    from scientific_contracts.numeric import finite_real
except ImportError:
    from services.agribrain.scientific_contracts.numeric import finite_real
from asmae_learn.schemas import ValidationEvent
from asmae_learn.disagreement import check_disagreement

REQUIRED_LINEAGE_FIELDS = [
    "plot_id",
    "run_id",
    "geometry_hash",
    "layer0_output_hash",
    "asmae_content_hash",
    "asmae_artifact_instance_hash",
]

def hash_dict(d: dict) -> str:
    serialized = json.dumps(d, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()

def build_learning_candidate(run_record: Dict[str, Any]) -> Dict[str, Any]:
    # 1. Enforce validation of lineage fields
    for field in REQUIRED_LINEAGE_FIELDS:
        val = run_record.get(field)
        if not val or not isinstance(val, str) or val.strip() == "":
            raise ValueError(f"Lineage field '{field}' is missing or empty.")

    validation_events_data = run_record.get("validation_events", [])
    if not validation_events_data:
        raise ValueError("Cannot create candidate without validation events.")

    # Convert validation_events_data dict list to list[ValidationEvent]
    events = []
    for ed in validation_events_data:
        if isinstance(ed, ValidationEvent):
            events.append(ed)
        else:
            from dataclasses import fields
            valid_keys = {f.name for f in fields(ValidationEvent)}
            init_args = {k: v for k, v in ed.items() if k in valid_keys}
            events.append(ValidationEvent(**init_args))

    # Run disagreement check
    disagreement_report = check_disagreement(run_record, events)
    diag_hash = hash_dict(disagreement_report)

    validation_event_ids = [e.event_id for e in events]
    
    # Base candidate object
    candidate = {
        "candidate_id": f"cand_{run_record['run_id']}",
        "plot_id": run_record["plot_id"],
        "run_id": run_record["run_id"],
        "candidate_type": "validated_state_candidate",
        "target_variable": events[0].target_variable,
        "zone_id": events[0].zone_id,
        "geometry_hash": run_record["geometry_hash"],
        "layer0_output_hash": run_record["layer0_output_hash"],
        "asmae_content_hash": run_record["asmae_content_hash"],
        "asmae_artifact_instance_hash": run_record["asmae_artifact_instance_hash"],
        "validation_event_ids": validation_event_ids,
        "disagreement_report_hash": diag_hash,
        "evidence_count": len(events),
        "validation_trust_score": max([e.trust_weight for e in events]) if events else 0.0,
        "agreement_score": disagreement_report["agreement_score"],
        "retro_score": None,
        "bma_status": None,
        "retro_status": None,
        "uncertainty": None,
        "eligible": True,
        "blocked_reasons": []
    }

    # Zero-eligibility checks
    diagnostics = run_record.get("diagnostics", {})
    raw_res = diagnostics.get("resolution_selected_m") or run_record.get("resolution_m", 10.0)
    res_m = finite_real(raw_res)
    if res_m is None or res_m <= 0.0:
        candidate["eligible"] = False
        candidate["blocked_reasons"].append("invalid_resolution")
    elif res_m <= 1.0 or (candidate["target_variable"] == "vigor" and res_m <= 1.0):
        candidate["candidate_type"] = "1m_certification_candidate"
        candidate["learning_candidate_status"] = "pending_1m_candidate"
        candidate["eligible"] = False
        candidate["blocked_reasons"].append("no_v86_certified_1m_status")

    if run_record.get("visual_only") or diagnostics.get("visual_only"):
        candidate["eligible"] = False
        candidate["blocked_reasons"].append("visual_only_asmae")
    if run_record.get("diagnostic_only") or diagnostics.get("diagnostic_only"):
        candidate["eligible"] = False
        candidate["blocked_reasons"].append("diagnostic_only_asmae")

    # BMA status
    bma_status = diagnostics.get("bma_status") if "bma_status" in diagnostics else run_record.get("bma_status")
    if bma_status is None:
        candidate["eligible"] = False
        candidate["blocked_reasons"].append("missing_bma_status")
    elif bma_status != "success":
        candidate["eligible"] = False
        candidate["blocked_reasons"].append("bma_status_not_success")
    candidate["bma_status"] = bma_status

    # Retro status
    retro_status = diagnostics.get("retro_status") if "retro_status" in diagnostics else run_record.get("retro_status")
    if retro_status is None:
        candidate["eligible"] = False
        candidate["blocked_reasons"].append("missing_retro_status")
    elif retro_status != "success_with_holdouts":
        candidate["eligible"] = False
        candidate["blocked_reasons"].append("retro_status_not_success_with_holdouts")
    candidate["retro_status"] = retro_status

    # Uncertainty
    raw_uncertainty = diagnostics.get("uncertainty") if "uncertainty" in diagnostics else run_record.get("uncertainty")
    if raw_uncertainty is None:
        candidate["eligible"] = False
        candidate["blocked_reasons"].append("missing_uncertainty")
        candidate["uncertainty"] = None
    else:
        uncertainty = finite_real(raw_uncertainty)
        if uncertainty is None or uncertainty < 0.0 or uncertainty > 0.4:
            candidate["eligible"] = False
            if uncertainty is not None and uncertainty > 0.4:
                candidate["blocked_reasons"].append("uncertainty_above_threshold")
            else:
                candidate["blocked_reasons"].append("invalid_or_unqualified_uncertainty")
        candidate["uncertainty"] = uncertainty

    # Retro score
    raw_retro = None
    if "retro_mean_score" in diagnostics:
        raw_retro = diagnostics["retro_mean_score"]
    elif "retrovalidation_score" in run_record:
        raw_retro = run_record["retrovalidation_score"]

    if raw_retro is None:
        candidate["eligible"] = False
        candidate["blocked_reasons"].append("missing_retro_score")
        candidate["retro_score"] = None
    else:
        retro_score = finite_real(raw_retro)
        if retro_score is None or retro_score < 0.7 or retro_score > 1.0:
            candidate["eligible"] = False
            if retro_score is not None and retro_score < 0.7:
                candidate["blocked_reasons"].append("retro_score_below_threshold")
            else:
                candidate["blocked_reasons"].append("invalid_or_unqualified_retro_score")
        candidate["retro_score"] = retro_score

    if candidate["validation_trust_score"] < 0.5:
        candidate["eligible"] = False
        candidate["blocked_reasons"].append("validation_trust_too_low")

    if events[0].spatial_scope == "zone":
        candidate["candidate_type"] = "zone_memory_candidate"
        if not candidate["zone_id"]:
            candidate["eligible"] = False
            candidate["blocked_reasons"].append("scope_mismatch")
    elif events[0].spatial_scope == "plot":
        candidate["candidate_type"] = "validated_state_candidate"

    if disagreement_report["candidate_status"] == "rejected":
        candidate["eligible"] = False
        candidate["blocked_reasons"].append("contradiction_detected")

    if "certified_1m" in candidate.get("learning_candidate_status", ""):
        candidate["learning_candidate_status"] = "pending_1m_candidate"
        candidate["eligible"] = False
        candidate["blocked_reasons"].append("no_v86_certified_1m_status")

    # V88 Guard: ML evidence cannot create/promote/certify 1m or bypass V90 required blockers
    from layer05_asmae.config import ASMAE_ML_EXPERTS_ENABLED
    if ASMAE_ML_EXPERTS_ENABLED or diagnostics.get("shadow_ml", {}).get("enabled"):
        if candidate.get("candidate_type") == "1m_certification_candidate" or candidate.get("learning_candidate_status") == "pending_1m_candidate":
            candidate["eligible"] = False
            candidate["blocked_reasons"].append("ml_cannot_influence_1m_certification")
        # ML cannot bypass V90 required blocker
        run_record_blockers = run_record.get("blocked_reasons", [])
        if "v90_blocker_bypass" in run_record_blockers or "v90_blocker_bypass" in candidate.get("blocked_reasons", []):
            candidate["eligible"] = False
            if "v90_blocker_bypass" not in candidate.get("blocked_reasons", []):
                candidate["blocked_reasons"].append("v90_blocker_bypass")

    return candidate
