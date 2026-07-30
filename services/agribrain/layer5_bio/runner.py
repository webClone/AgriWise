"""
Layer 5 Runner — BioThreat Intelligence Pipeline Orchestration (v6.0)

Wires the modernized engine chain:
  WDP (LWD) → SSS (Spread + Spore Dispersal) → RAS (Remote Evidence)
  → PIE (BioThreatInferenceEngine) → RAP (Response Planner)

Key v6.0 changes:
  - Dynamic priors replace static THREAT_PRIORS
  - BioThreatInferenceEngine replaces flat infer_threat_states()
  - L3 decision_output is threaded through for confounder gating
  - WDP dict passed to inference engine for LWD-aware confidence
  - Phenology stage extracted from L2 and passed to dynamic priors + engine
  - Legacy evidence synthesis block removed (now handled entirely by RAS + PIE)
"""

from dataclasses import asdict
from typing import Any, Dict, Optional, List
from datetime import datetime, timezone
import hashlib
import json
import copy

from layer5_bio.schema import (
    BioThreatIntelligenceOutput, RunMeta, QualityMetricsL5, AuditSnapshot,
    BioThreatState, BioRecommendation, ThreatId, ThreatClass, Severity, SpreadPattern,
    Confounder, ActionId
)
from layer3_decision.schema import Driver, DegradationMode, ExecutionPlan, TaskNode

from layer5_bio.engines.weather_pressure import build_weather_pressure
from layer5_bio.engines.spread_signature import infer_spread_signature
from layer5_bio.engines.remote_signature import build_remote_evidence
from layer5_bio.engines.inference import BioThreatInferenceEngine
from layer5_bio.engines.response_planner import build_response_plan
from layer5_bio.knowledge.dynamic_priors import compute_dynamic_priors
from layer5_bio.invariants import enforce_layer5_invariants
from layer5_bio.engines.genetical_engine import run_genetical_engine
from layer5_bio.engines.chemical_engine import run_chemical_engine
from layer5_bio.engines.biophysical_engine import run_biophysical_engine

import logging
logger = logging.getLogger(__name__)

CODE_VERSION = "6.0.0"
MODEL_VERSIONS = {
    "wdp": "2.0.0",    # LWD-based weather pressure
    "sss": "2.0.0",    # Spread signature + spore dispersal
    "ras": "2.0.0",    # Extended remote evidence (all 9 threats + LWD + L3 confounders)
    "pie": "6.0.0",    # Bayesian inference engine (class-based, per-threat methods)
    "rap": "1.0.0",    # Response planner (unchanged)
    "dp":  "1.0.0",    # Dynamic priors (new)
    "genetical": "1.0.0",
    "chemical": "1.0.0",
    "biophysical": "1.0.0",
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

    # ── Parent ID extraction (resilient) ────────────────────────────────
    parent_ids = {
        "L1": getattr(field_tensor, "run_id", ""),
        "L2": getattr(getattr(veg_output, "run_meta", None), "run_id", getattr(veg_output, "run_id", "")),
    }
    
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

    # ── Feature sourcing (strict) ───────────────────────────────────────
    ts = getattr(field_tensor, "plot_timeseries", []) or []
    
    features_snapshot = {}
    missing = []
    penalties = []
    data_completeness = {"timeseries": 1.0, "soil": 1.0, "spatial": 1.0}
    degradation = DegradationMode.NORMAL
    reliability = 1.0

    # Strict Partial Tolerance Check
    if not ts:
        missing.append("L1_Rain")
        missing.append("L1_Temp")
        degradation = DegradationMode.DATA_GAP
        reliability -= 0.4
        data_completeness["timeseries"] = 0.0
        penalties.append({"driver": "L1_Rain", "penalty": 0.2, "reason": "No timeseries data"})
        penalties.append({"driver": "L1_Temp", "penalty": 0.2, "reason": "No timeseries data"})
        
    static_props = getattr(field_tensor, "static", {}) or {}
    if not static_props.get("texture_class"):
        missing.append("L1_Soil")
        reliability -= 0.2
        data_completeness["soil"] = 0.0
        penalties.append({"driver": "L1_Soil", "penalty": 0.2, "reason": "No soil texture data"})

    # ── Extract phenology stage from L2 ─────────────────────────────────
    phenology_stage = ""
    try:
        phenology = getattr(veg_output, "phenology", None)
        if phenology:
            phenology_stage = getattr(phenology, "stage", "") or getattr(phenology, "growth_stage", "") or ""
        if not phenology_stage:
            phenology_stage = plot_context.get("phenology_stage", "")
    except Exception:
        phenology_stage = plot_context.get("phenology_stage", "")

    # ── Extract crop type + coordinates ─────────────────────────────────
    crop_type = plot_context.get("crop_type", plot_context.get("crop", ""))
    lat = float(plot_context.get("lat", plot_context.get("latitude", 0.0)) or 0.0)

    # ══════════════════════════════════════════════════════════════════════
    # ENGINE CHAIN: WDP → SSS → RAS → PIE → RAP
    # ══════════════════════════════════════════════════════════════════════

    # 1. Weather-Disease Pressure (WDP) — Now with LWD
    wp = build_weather_pressure(ts, veg_output, plot_context)
    features_snapshot.update(wp)

    # 2. Spread Signature (SSS) — Spatial pattern inference
    sss = infer_spread_signature(field_tensor, veg_output, plot_context)
    features_snapshot["spread"] = sss

    # 3. Remote / Anomaly Signature (RAS) — Evidence generation for ALL threats
    #    Now receives l3_decision for structural confounder gating
    remote_evidence, remote_feats = build_remote_evidence(
        ts=ts,
        veg_output=veg_output,
        wdp=wp,
        spread=sss,
        nutrient_output=nutrient_output,
        plot_context=plot_context,
        degradation_mode=degradation,
        l3_decision=decision_output,  # NEW: L3 confounder integration
    )
    features_snapshot.update(remote_feats)

    # 4. Dynamic Priors — Context-adjusted base rates
    climate_indicators = {
        "tmean_7d": wp.get("tmean_7d", 20.0),
        "rain_sum_7d": wp.get("rain_sum_7d", 10.0),
    }
    priors = compute_dynamic_priors(
        crop_type=crop_type,
        phenology_stage=phenology_stage,
        climate_indicators=climate_indicators,
        lat=lat,
    )
    features_snapshot["dynamic_priors"] = {tid.value: round(p, 4) for tid, p in priors.items()}
    features_snapshot["phenology_stage"] = phenology_stage

    # 5. Soil-dependent evidence (clay proxy for downy mildew)
    #    Inject directly into the evidence dict from RAS
    from layer5_bio.schema import EvidenceLogit
    has_clay = (
        (static_props.get("soil_clay", 0) or 0) > 20.0
        or "clay" in str(static_props.get("texture_class", "")).lower()
    )
    if has_clay:
        remote_evidence.setdefault(ThreatId.DOWNY_MILDEW, []).append(
            EvidenceLogit(Driver.NDVI_UNC, "Soil Clay Proxy", 1.0, 1.5, {"soil_clay": True})
        )
    elif ThreatId.DOWNY_MILDEW in remote_evidence:
        remote_evidence[ThreatId.DOWNY_MILDEW].append(
            EvidenceLogit(Driver.NDVI_UNC, "No Soil Clay", -0.5, 1.0, {"soil_clay": False})
        )

    # 5b. Scientific & Agricultural Engine Extensions
    # A. Genetical Engine (R-gene matching & susceptibility)
    # References:
    #   - Jones, J. D., & Dangl, J. L. (2006). The plant immune system. Nature, 444(7117), 323-329.
    genetical_results = {}
    variety = plot_context.get("variety")
    for tid in list(remote_evidence.keys()):
        gen_res = run_genetical_engine(crop_type, variety, tid, plot_context)
        genetical_results[tid.value] = {
            "susceptibility_score": gen_res["susceptibility_score"],
            "matching_r_genes": gen_res["matching_r_genes"],
            "match_found": gen_res["match_found"]
        }
        remote_evidence.setdefault(tid, []).append(gen_res["evidence_logit"])
        
    features_snapshot["genetical"] = genetical_results

    # B. Biophysical Engine (canopy microclimate & wind spore release)
    # References:
    #   - Monteith, J. L. (1965). Evaporation and environment. Symp. Soc. Exp. Biol., 19, 205-234.
    # Runs before Chemical Engine to compute transpiration rates driving systemic translocation.
    biophys_res = run_biophysical_engine(ts, veg_output, decision_output, plot_context)
    features_snapshot["biophysical"] = {
        "canopy_microclimate": biophys_res["canopy_microclimate"],
        "spore_release_probability": biophys_res["spore_release_probability"]
    }
    for tid, ev_logit in biophys_res["biophysical_logits"].items():
        remote_evidence.setdefault(tid, []).append(ev_logit)

    # C. Chemical Engine (degradation kinetics, wash-off, & spray drift)
    # References:
    #   - Bromilow, R. H., & Chamberlain, K. (1995). Principles governing uptake and translocation of xenobiotics.
    # Consumes biophys_res to extract transpiration rate for systemic translocation modeling.
    chem_res = run_chemical_engine(ts, veg_output, plot_context, biophys_res)
    features_snapshot["chemical"] = {
        "chemical_protection_factors": chem_res["chemical_protection_factors"],
        "applied_status": chem_res["applied_status"],
        "spray_drift_risk": chem_res["spray_drift_risk"]
    }
    from layer5_bio.knowledge.threats import THREAT_CLASS
    for tid, tclass in THREAT_CLASS.items():
        if tclass in chem_res["evidence_logits"]:
            remote_evidence.setdefault(tid, []).append(chem_res["evidence_logits"][tclass])

    # 6. Apply strict penalties for missing drivers
    #    (Wiping removed: we now rely on the Inference Engine's confidence scores
    #     to pass the low-confidence status up to the LLM, rather than hiding the threat.)
    # if "L1_Soil" in missing:
    #     remote_evidence[ThreatId.DOWNY_MILDEW] = []
    #
    # if "L1_Rain" in missing or "L1_Temp" in missing:
    #     for tid in [ThreatId.FUNGAL_LEAF_SPOT, ThreatId.BACTERIAL_BLIGHT,
    #                 ThreatId.CHEWING_INSECTS, ThreatId.FUNGAL_RUST]:
    #         remote_evidence[tid] = []

    reliability = max(0.10, reliability)

    # 7. Probabilistic Inference Engine (PIE) — Bayesian log-odds
    engine = BioThreatInferenceEngine()
    threat_states = engine.infer_states(
        evidence_by_threat=remote_evidence,
        spread=sss,
        priors=priors,
        l3_decision=decision_output,
        wdp=wp,
        phenology_stage=phenology_stage,
        missing_drivers=missing,
    )

    # ── Multimodal Leaf Photo Diagnostic Loop ─────────────────────────────
    image_b64 = plot_context.get("image")
    if image_b64:
        try:
            import base64
            import numpy as np
            import cv2
            
            # Clean base64 string
            if "," in image_b64:
                image_b64 = image_b64.split(",")[1]
            img_bytes = base64.b64decode(image_b64)
            img_arr = np.frombuffer(img_bytes, dtype=np.uint8)
            img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
            
            if img is not None:
                from layer5_bio.visual_detection import visual_engine
                # Run the NumPy CNN / VLM visual detection
                vis_res = visual_engine.analyze_image(img, {
                    "water_stress_prob": float(decision_output.water_stress_index) if decision_output and hasattr(decision_output, "water_stress_index") else 0.0,
                    "n_deficiency_prob": float(nutrient_output.n_deficit_kg_ha) if nutrient_output and hasattr(nutrient_output, "n_deficit_kg_ha") and isinstance(nutrient_output.n_deficit_kg_ha, (int, float)) else 0.0
                })
                
                # If analyzed, fuse this visual evidence into the threat states!
                if vis_res.get("status") == "analyzed":
                    top_diag = vis_res.get("top_diagnosis")
                    confidence = float(vis_res.get("confidence", 0.8))
                    description = vis_res.get("description", "")
                    
                    logger.info(f"[Layer 5] Ground Truth Visual diagnosis matching: {top_diag} with confidence {confidence:.2f}")
                    
                    # Update features_snapshot and audit
                    features_snapshot["visual_diagnosis"] = {
                        "top_class": top_diag,
                        "confidence": confidence,
                        "description": description,
                        "engine": vis_res.get("engine", "numpy_cnn")
                    }
                    
                    # Map the top class to ThreatId enum
                    threat_map = {
                        "early_blight": ThreatId.BACTERIAL_BLIGHT,
                        "late_blight": ThreatId.BACTERIAL_BLIGHT,
                        "septoria": ThreatId.FUNGAL_LEAF_SPOT
                    }
                    target_tid = threat_map.get(top_diag)
                    if target_tid in threat_states:
                        threat_states[target_tid].probability = confidence
                        threat_states[target_tid].confidence = 0.90  # high confidence due to image ground-truth
                        
        except Exception as e:
            logger.warning(f"[Layer 5] Failed to run visual diagnosis on uploaded image: {e}")

    # ── SPATIAL EXTENSIONS (Phase 11): Zonal Threats ────────────────────
    zone_metrics = {}
    if hasattr(field_tensor, "zones") and field_tensor.zones:
        for z_id, z_data in field_tensor.zones.items():
            logger.debug(f"[Layer 5] Assessing Biotic Risk for {z_id}")
            z_threat_states = {}
            for t_id, zt in threat_states.items():
                zts = copy.deepcopy(zt)
                if z_id == "Zone C":
                    # Stressed zones → more susceptible to weeds and soil-borne diseases
                    if zts.threat_id in [ThreatId.WEED_PRESSURE, ThreatId.DOWNY_MILDEW]:
                        zts.probability = min(1.0, zts.probability * 1.2)
                elif z_id == "Zone A":
                    # Dense lush canopy → favors fungal/mildew due to microclimate
                    if hasattr(zts.threat_id, 'value'):
                        tid_val = zts.threat_id.value
                    else:
                        tid_val = str(zts.threat_id)
                    if "FUNGAL" in tid_val or "MILDEW" in tid_val:
                        zts.probability = min(1.0, zts.probability * 1.15)
                z_threat_states[t_id] = zts
            
            zone_metrics[z_id] = {
                "threat_states": z_threat_states
            }

    # 8. Response Action Planner (RAP)
    recommendations, plan = build_response_plan(
        threat_states=threat_states,
        decision_output=decision_output,
        plot_context=plot_context,
        degradation_mode=degradation
    )
    
    # Tag Execution Plan tasks with target zones
    if zone_metrics and plan:
        for task in plan.tasks:
            target_zones = []
            for z_id, zm in zone_metrics.items():
                high_threats = [t_id for t_id, state in zm["threat_states"].items() if state.probability > 0.5]
                if len(high_threats) > 0:
                    target_zones.append(z_id)
            task.target_zones = target_zones if target_zones else list(zone_metrics.keys())

    # ── Deterministic run id ────────────────────────────────────────────
    l3_policy = {}
    if decision_output:
        l3_policy = getattr(getattr(decision_output, "audit", None), "policy_snapshot", {}) or {}
        
    policy_snapshot = {
        "degradation_mode": degradation.value,
        "plot_context_key": plot_context.get("crop", plot_context.get("crop_type", "UNKNOWN")),
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
        data_completeness=data_completeness,
        penalties_applied=penalties
    )

    audit = AuditSnapshot(
        features_snapshot=features_snapshot,
        policy_snapshot=policy_snapshot,
        model_versions=MODEL_VERSIONS
    )

    output = BioThreatIntelligenceOutput(
        run_meta=run_meta,
        threat_states={k: v for k, v in threat_states.items()},
        recommendations=recommendations,
        execution_plan=plan,
        zone_metrics=zone_metrics,
        quality_metrics=quality,
        audit=audit,
        leaf_wetness_hours=wp.get("lwd_mean_hours", 0.0),
    )

    # Invariant Enforcement (Mandatory Gate)
    violations = enforce_layer5_invariants(output)
    errors = [v for v in violations if v.severity == "error"]
    warnings = [v for v in violations if v.severity == "warning"]
    if errors:
        for v in errors:
            logger.error(f"[Layer 5] INVARIANT ERROR: {v.check_name} — {v.description}")
    if warnings:
        for v in warnings:
            logger.warning(f"[Layer 5] INVARIANT WARN: {v.check_name} — {v.description}")

    return output


# ══════════════════════════════════════════════════════════════════════════
# Orchestrator Entry Point (Strict Input Contract)
# ══════════════════════════════════════════════════════════════════════════

from orchestrator_v2.schema import OrchestratorInput
from layer5_bio.schema import Layer5Input
from layer1_fusion.schema import FieldTensor
from layer2_veg_int.schema import VegIntOutput
from layer3_decision.schema import DecisionOutput
from layer4_nutrients.schema import NutrientIntelligenceOutput

def run_layer5_bio(
    inputs: Any,
    tensor: Optional[FieldTensor] = None,
    veg_int: Optional[Any] = None,
    decision_l3: Optional[DecisionOutput] = None,
    nutrient_l4: Optional[NutrientIntelligenceOutput] = None
) -> BioThreatIntelligenceOutput:
    """Wrapper for Strict Input Contract — Orchestrator V2 compatible."""

    if hasattr(inputs, "tensor"):
        # It's a Layer5Input!
        tensor = inputs.tensor
        veg_int = inputs.veg_int
        decision_l3 = inputs.decision_l3
        nutrient_l4 = inputs.nutrient_l4
        ctx = getattr(inputs, "context", None)
        applied_chemicals = None
        if ctx:
            # Try to extract applied_chemicals from the strict contract context object
            applied_chemicals = getattr(ctx, "applied_chemicals", None)
            if not applied_chemicals and hasattr(ctx, "constraints"):
                constraints = getattr(ctx, "constraints") or {}
                if isinstance(constraints, dict):
                    applied_chemicals = constraints.get("applied_chemicals")
            if not applied_chemicals and isinstance(ctx, dict):
                applied_chemicals = ctx.get("applied_chemicals")

            image_val = (
                getattr(ctx, "image", None)
                or getattr(ctx, "image_data_b64", None)
                or (ctx.get("image") if isinstance(ctx, dict) else None)
                or (ctx.get("image_data_b64") if isinstance(ctx, dict) else None)
                or getattr(inputs, "image", None)
                or getattr(inputs, "image_data_b64", None)
            )
            plot_context = {
                "crop_type": getattr(ctx, "crop_type", "unknown"),
                "variety": getattr(ctx, "variety", None),
                "planting_date": getattr(ctx, "planting_date", ""),
                "irrigation_type": getattr(ctx, "irrigation_type", "rainfed"),
                "management_goal": getattr(ctx, "management_goal", "yield_max"),
                "constraints": getattr(ctx, "constraints", {}) or {},
                "lat": getattr(ctx, "lat", 0.0),
                "lon": getattr(ctx, "lon", 0.0),
                "phenology_stage": getattr(ctx, "phenology_stage", ""),
                "applied_chemicals": applied_chemicals or [],
                "image": image_val
            }
        else:
            plot_context = {"applied_chemicals": []}
    else:
        cc = inputs.crop_config if inputs else {}
        oc = inputs.operational_context if inputs else {}

        # GAP 8: Resolve phenology stage with layered precedence:
        # 1. Real L2 phenology.stage_by_day (most accurate)
        # 2. crop_config["phenology_stage"] (user-provided)
        # 3. operational_context["phenology_stage"]
        # 4. "" (fallback — dynamic priors degrade to uniform)
        phenology_stage = cc.get("phenology_stage", oc.get("phenology_stage", ""))
        if not phenology_stage and veg_int is not None:
            try:
                pheno = getattr(veg_int, "phenology", None)
                if pheno:
                    stages = getattr(pheno, "stage_by_day", [])
                    for s in reversed(stages):
                        val = s.value if hasattr(s, "value") else str(s)
                        if val.upper() not in ("UNKNOWN", "NONE", ""):
                            phenology_stage = val
                            break
            except Exception:
                pass

        # Try to extract applied_chemicals from the lax contract dictionary
        applied_chemicals = oc.get("applied_chemicals") or cc.get("applied_chemicals")
        if not applied_chemicals and isinstance(oc, dict) and "constraints" in oc:
            applied_chemicals = oc.get("constraints", {}).get("applied_chemicals")
        if not applied_chemicals and isinstance(inputs, dict):
            applied_chemicals = inputs.get("applied_chemicals")

        plot_context = {
            "crop_type": cc.get("crop", "unknown"),
            "variety": cc.get("variety"),
            "planting_date": cc.get("planting_date", ""),
            "irrigation_type": oc.get("irrigation_type", "rainfed"),
            "management_goal": oc.get("management_goal", "yield_max"),
            "constraints": oc.get("constraints", {}),
            "lat": cc.get("lat", oc.get("lat", 0.0)),
            "lon": cc.get("lon", oc.get("lon", 0.0)),
            "phenology_stage": phenology_stage,
            "applied_chemicals": applied_chemicals or [],
            "image": oc.get("image") or oc.get("image_data_b64") or cc.get("image") or cc.get("image_data_b64")
        }

    return run_layer5(
        field_tensor=tensor,
        veg_output=veg_int,
        decision_output=decision_l3,
        nutrient_output=nutrient_l4,
        plot_context=plot_context
    )
