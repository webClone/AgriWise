
from dataclasses import asdict
from typing import Any, Dict, Optional, List
from datetime import datetime
import hashlib
import json
import math

from services.agribrain.layer5_bio.schema import (
    BioThreatIntelligenceOutput, RunMeta, QualityMetricsL5, AuditSnapshot,
    BioThreatState, BioRecommendation, ThreatId, ThreatClass, Severity, SpreadPattern,
    Confounder, ActionId
)
from services.agribrain.layer3_decision.schema import Driver, DegradationMode, ExecutionPlan, TaskNode

from services.agribrain.layer5_bio.engines.weather_pressure import build_weather_pressure
from services.agribrain.layer5_bio.engines.spread_signature import infer_spread_signature
from services.agribrain.layer5_bio.engines.remote_signature import build_remote_evidence
from services.agribrain.layer5_bio.engines.inference import infer_threat_states
from services.agribrain.layer5_bio.engines.response_planner import build_response_plan

CODE_VERSION = "5.0.0"
MODEL_VERSIONS = {
    "wdp": "1.0.0",
    "sss": "1.0.0",
    "ras": "1.0.0",
    "pie": "5.0.0",
    "rap": "1.0.0",
}

def _stable_hash(obj: Dict[str, Any]) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]

def run_layer5(
    field_tensor,           # L1 FieldTensor
    veg_output,             # L2 VegIntOutput
    decision_output,        # L3 DecisionOutput
    nutrient_output,        # L4 NutrientIntelligenceOutput
    plot_context: Dict[str, Any],
    user_images: Optional[List[Dict[str, Any]]] = None,  # optional visual inputs later
) -> BioThreatIntelligenceOutput:

    parent_ids = {
        "L1": getattr(field_tensor, "run_id", ""),
        "L2": getattr(getattr(veg_output, "run_meta", None), "run_id", getattr(veg_output, "run_id", "")),
    }
    
    # Safe Parent ID extraction
    if decision_output:
        l3_id = getattr(getattr(decision_output, "run_meta", None), "run_id", getattr(decision_output, "run_id_l3", ""))
        parent_ids["L3"] = l3_id
    else:
        parent_ids["L3"] = "SKIPPED"
        
    if nutrient_output:
        l4_id = getattr(getattr(nutrient_output, "run_meta", None), "run_id", "")
        parent_ids["L4"] = l4_id
    else:
        parent_ids["L4"] = "SKIPPED"

    # --- Feature sourcing (strict) ---
    ts = getattr(field_tensor, "plot_timeseries", []) or []
    # (we keep channels for gating; main truth is plot_timeseries)
    
    # ... inputs checking ...

    # --- Confounders from Layer 4 (strict) ---
    confounders: List[str] = []
    if nutrient_output:
        try:
            ns_map = getattr(nutrient_output, "nutrient_states", {}) or {}
            for k, state in ns_map.items():
                for c in (getattr(state, "confounders", []) or []):
                    confounders.append(str(c))
        except Exception:
            pass

    # ... inference ...

    # --- Plan ---
    recommendations, plan = build_response_plan(
        threat_states=threat_states,
        decision_output=decision_output,
        plot_context=plot_context,
        degradation_mode=degradation
    )

    # --- Deterministic run id ---
    l3_policy = {}
    if decision_output:
        l3_policy = getattr(getattr(decision_output, "audit", None), "policy_snapshot", {}) or {}
        
    policy_snapshot = {
        "degradation_mode": degradation.value,
        "plot_context_key": plot_context.get("crop", "UNKNOWN"),
        "policy_from_L3": l3_policy,
    }

    run_hash = _stable_hash({
        "parents": parent_ids,
        "policy": policy_snapshot,
        "code": CODE_VERSION,
        "models": MODEL_VERSIONS,
        "features_digest": _stable_hash(features_snapshot),
    })
    run_id = f"L5-{run_hash}"

    run_meta = RunMeta(
        run_id=run_id,
        parent_run_ids=parent_ids,
        generated_at=datetime.utcnow().isoformat(),
        degradation_mode=degradation
    )

    quality = QualityMetricsL5(
        decision_reliability=reliability,
        missing_drivers=missing,
        data_completeness=completeness,
        penalties_applied=penalties
    )

    audit = AuditSnapshot(
        features_snapshot=features_snapshot,
        policy_snapshot=policy_snapshot,
        model_versions=MODEL_VERSIONS
    )

    return BioThreatIntelligenceOutput(
        run_meta=run_meta,
        threat_states={k: v for k, v in threat_states.items()},
        recommendations=recommendations,
        execution_plan=plan,
        quality_metrics=quality,
        audit=audit
    )

from services.agribrain.orchestrator_v2.schema import OrchestratorInput
from services.agribrain.layer5_bio.schema import Layer5Input

def run_layer5_bio(
    inputs: OrchestratorInput,
    tensor: FieldTensor,
    veg_int: VegIntOutput,
    decision_l3: DecisionOutput,
    nutrient_l4: NutrientIntelligenceOutput
) -> BioThreatIntelligenceOutput:
    """Wrapper for Strict Input Contract"""
    
    # Map Context (L4 context creation logic repeated or handled inside run_layer5)
    cc = inputs.crop_config if inputs else {}
    oc = inputs.operational_context if inputs else {}
    plot_context = {
        "crop_type": cc.get("crop", "unknown"),
        "variety": cc.get("variety"),
        "planting_date": cc.get("planting_date", ""),
        "irrigation_type": oc.get("irrigation_type", "rainfed"),
        "management_goal": oc.get("management_goal", "yield_max"),
        "constraints": oc.get("constraints", {})
    }

    return run_layer5(
        field_tensor=tensor,
        veg_output=veg_int,
        decision_output=decision_l3,
        nutrient_output=nutrient_l4, # run_layer5 handles None internally? Need to check
        plot_context=plot_context
    )
    # Note: run_layer5 implementation has try/except for nutrient_output getattr, so it handles None partially.
    # But getattr(None, ...) crashes. I need to fix run_layer5 too.
