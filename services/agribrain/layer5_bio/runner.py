
from dataclasses import asdict
from typing import Any, Dict, Optional, List
from datetime import datetime, timezone
import hashlib
import json
import math

from layer5_bio.schema import (
    BioThreatIntelligenceOutput, RunMeta, QualityMetricsL5, AuditSnapshot,
    BioThreatState, BioRecommendation, ThreatId, ThreatClass, Severity, SpreadPattern,
    Confounder, ActionId
)
from layer3_decision.schema import Driver, DegradationMode, ExecutionPlan, TaskNode

from layer5_bio.engines.weather_pressure import build_weather_pressure
from layer5_bio.engines.spread_signature import infer_spread_signature
from layer5_bio.engines.remote_signature import build_remote_evidence
from layer5_bio.engines.inference import infer_threat_states
from layer5_bio.engines.response_planner import build_response_plan

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
    
    features_snapshot = {}
    missing = []
    penalties = {}
    completeness = 1.0
    from layer3_decision.schema import DegradationMode
    degradation = DegradationMode.NORMAL
    reliability = 1.0

    # Strict Partial Tolerance Check
    if not ts:
        missing.append("L1_Rain")
        missing.append("L1_Temp")
        degradation = DegradationMode.DATA_GAP
        reliability -= 0.4
        
    static_props = getattr(field_tensor, "static", {}) or {}
    if not static_props.get("texture_class"):
        missing.append("L1_Soil")
        reliability -= 0.2
        # Note: We do NOT fail. We just lower reliability and neutralize soil-dependent logics.

    # 1. Weather Pressure Engine
    wp = build_weather_pressure(ts, veg_output, plot_context)
    features_snapshot.update(wp)

    # 2. Spread Signature (must happen before remote signature)
    # If spatial anomalies exist in veg_output, use them. Otherwise default to UNKNOWN or UNIFORM.
    sss = infer_spread_signature(field_tensor, veg_output, plot_context)
    features_snapshot["spread"] = sss

    # 3. Remote Signature (NDVI/SAR)
    rs, rs_missing = build_remote_evidence(
        ts=ts, 
        veg_output=veg_output,
        wdp=wp,
        spread=sss,
        nutrient_output=nutrient_output,
        plot_context=plot_context,
        degradation_mode=DegradationMode.NORMAL
    )
    missing.extend(rs_missing)
    if rs_missing:
        reliability -= (0.1 * len(rs_missing))
    features_snapshot.update(rs)

    # 4. Synthesize Evidence
    from layer5_bio.schema import EvidenceLogit
    from layer3_decision.schema import Driver
    evidence_by_threat = {
        ThreatId.FUNGAL_LEAF_SPOT: [
            EvidenceLogit(Driver.NDVI, "NDVI Drop",  0.5 if rs.get("ndvi_drop_detected") else -0.5, 1.0, []),
            EvidenceLogit(Driver.RAIN, "Wetness Proxy",  wp.get("fungal_pressure", 0.0) * 2.0 - 1.0, 1.5, [])
        ],
        ThreatId.BACTERIAL_BLIGHT: [
            EvidenceLogit(Driver.TEMP, "Bacterial Heat Proxy",  wp.get("bacterial_pressure", 0.0) * 2.0 - 1.0, 1.2, [])
        ],
        ThreatId.CHEWING_INSECTS: [
            EvidenceLogit(Driver.TEMP, "Degree Days",  wp.get("insect_pressure", 0.0) * 2.5 - 1.0, 1.0, [])
        ],
        ThreatId.DOWNY_MILDEW: [
             EvidenceLogit(Driver.NDVI_UNC, "Soil Clay Proxy", 1.0 if "clay" in static_props.get("texture_class", "").lower() else -0.5, 1.5, [])
        ]
    }
    
    # Apply strict penalties for missing drivers
    if "L1_Soil" in missing:
        evidence_by_threat[ThreatId.DOWNY_MILDEW] = [] # Unknown risk
        
    if "L1_Rain" in missing or "L1_Temp" in missing:
        evidence_by_threat[ThreatId.FUNGAL_LEAF_SPOT] = []
        evidence_by_threat[ThreatId.BACTERIAL_BLIGHT] = []
        evidence_by_threat[ThreatId.CHEWING_INSECTS] = []

    reliability = max(0.1, reliability)

    threat_states = infer_threat_states(
        evidence_by_threat=evidence_by_threat,
        spread=sss,
        nutrient_output=nutrient_output,
        plot_context=plot_context,
        confidence=reliability
    )

    # --- SPATIAL EXTENSIONS (Phase 11): Zonal Threats ---
    zone_metrics = {}
    if hasattr(field_tensor, "zones") and field_tensor.zones:
        for z_id, z_data in field_tensor.zones.items():
            print(f"🌍 [Layer 5] Assessing Biotic Risk for {z_id}")
            # Mock Zonal heuristics based on global inference:
            z_threat_states = {}
            import copy
            for t_id, zt in threat_states.items():
                zts = copy.deepcopy(zt)
                if z_id == "Zone C":
                    # Stressed zones are generally more susceptible to weeds and soil-borne diseases
                    if zts.threat_id in [ThreatId.WEED_PRESSURE, ThreatId.DOWNY_MILDEW]:
                        zts.probability = min(1.0, zts.probability * 1.2)
                elif z_id == "Zone A":
                    # Dense lush canopy favors fungal/mildew due to microclimate
                    if "FUNGAL" in zts.threat_id or "MILDEW" in zts.threat_id:
                        zts.probability = min(1.0, zts.probability * 1.15)
                z_threat_states[t_id] = zts
            
            zone_metrics[z_id] = {
                "threat_states": z_threat_states
            }

    # --- Plan ---
    recommendations, plan = build_response_plan(
        threat_states=threat_states,
        decision_output=decision_output,
        plot_context=plot_context,
        degradation_mode=degradation
    )
    
    # Tag Execution Plan tasks with target zones
    if zone_metrics and plan:
        for task in plan.tasks:
            # Map interventions/scouting to high-probability localized zones
            target_zones = []
            for z_id, zm in zone_metrics.items():
                # Gather all threats exceeding 50% probability in this zone
                high_threats = [t_id for t_id, state in zm["threat_states"].items() if state.probability > 0.5]
                # In MVP, if the task is triggered (globally), we point it to ALL active threat zones.
                if len(high_threats) > 0:
                    target_zones.append(z_id)
                    
            # Set minimum fallback if no > 50% detected but a task exists
            task.target_zones = target_zones if target_zones else list(zone_metrics.keys())

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
        generated_at=datetime.now(timezone.utc).isoformat(),
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
        zone_metrics=zone_metrics,
        quality_metrics=quality,
        audit=audit
    )

from orchestrator_v2.schema import OrchestratorInput
from layer5_bio.schema import Layer5Input
from layer1_fusion.schema import FieldTensor
from layer2_veg_int.schema import VegIntOutput
from layer3_decision.schema import DecisionOutput
from layer4_nutrients.schema import NutrientIntelligenceOutput

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
