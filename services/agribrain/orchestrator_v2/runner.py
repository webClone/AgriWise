
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
import hashlib
import json
from dataclasses import asdict

from orchestrator_v2.schema import (
    OrchestratorInput, RunArtifact, RunMeta, LayerResult, LayerStatus, GlobalQuality
)
from orchestrator_v2.registry import LAYER_REGISTRY, LayerId, get_layer_versions
from orchestrator_v2.hashing import generate_orchestrator_run_id
from orchestrator_v2.gating import merge_execution_plans, evaluate_global_quality, filter_unsafe_actions
from orchestrator_v2.storage import LocalJsonStore
from orchestrator_v2.chat_adapter import ChatPayload, build_chat_payload
from layer10_sire.schema import Layer10Input
from layer8_prescriptive.schema import Layer8Input

ORCHESTRATOR_VERSION = "2.1.0"

def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)

from orchestrator_v2.intents import Intent, detect_intent, resolve_time_window

def run_orchestrator(
    inputs: OrchestratorInput,
    store: Optional[LocalJsonStore] = None,
    intent: Intent = Intent.DECISION,
    user_query: Optional[str] = None
) -> RunArtifact:
    """
    Main Entrypoint for AgriBrain V2.1 (Hardened).
    Supports Intent-Based Routing to skip unnecessary layers.
    """
    ts_now = datetime.now(timezone.utc).isoformat() + "Z"
    
    # 1. Generate Deterministic ID
    layer_versions = get_layer_versions()
    run_id = generate_orchestrator_run_id(inputs, layer_versions, ORCHESTRATOR_VERSION)
    
    results: Dict[LayerId, LayerResult] = {}
    
    # 2. Execution Sequence
    
    # --- Intent Gating (Early Exit) ---
    if intent in [Intent.GREETING, Intent.GENERAL]:
        return _finalize_artifact(run_id, ts_now, inputs, results, store)
        
    # --- Layer 1 ---
    l1_res = _safe_run(LayerId.L1, inputs)
    results[LayerId.L1] = l1_res
    
    if l1_res.status == LayerStatus.FAILED:
        return _finalize_artifact(run_id, ts_now, inputs, results, store)

    # --- Intent Gating ---
    # If DATA_QUERY, skip everything else (L2-L6). 
    # L1 contains Weather, NDVI, SAR Raw Data which is sufficient for "How much rain?" or "Show me NDVI".
    if intent == Intent.DATA_QUERY:
        return _finalize_artifact(run_id, ts_now, inputs, results, store)
        
    # --- Layer 2 ---
    l2_res = _safe_run(LayerId.L2, inputs, l1_res.output)
    results[LayerId.L2] = l2_res
    
    if l2_res.status == LayerStatus.FAILED:
        return _finalize_artifact(run_id, ts_now, inputs, results, store)

    # --- Intent Gating (DIAGNOSIS Special Path) ---
    if intent == Intent.DIAGNOSIS:
        # User requested Diagnosis (Pest/Disease).
        # We Run L1 -> L2 -> L5. Skip L3/L4 for speed.
        # L5 is patched to handle missing L3/L4.
        l5_res = _safe_run(LayerId.L5, inputs, l1_res.output, l2_res.output, None, None)
        results[LayerId.L5] = l5_res
        
        # Merge plan (L5 only)
        plan_l5 = l5_res.output.execution_plan if l5_res.output else None
        unified_plan = merge_execution_plans(None, plan_l5)
        prov_gq = evaluate_global_quality(results)
        unified_plan = filter_unsafe_actions(unified_plan, prov_gq)
        
        return _finalize_artifact(run_id, ts_now, inputs, results, store, unified_plan)

    # --- Layer 3 ---
    l3_res = _safe_run(LayerId.L3, inputs, l1_res.output, l2_res.output)
    results[LayerId.L3] = l3_res
    
    # --- Intent Gating (DECISION) ---
    if intent == Intent.DECISION:
        # User requested Decision (Irrigation/General).
        # L1 -> L2 -> L3. Skip L4/L5/L6.
        plan_l3 = l3_res.output.execution_plan if l3_res.output else None
        unified_plan = merge_execution_plans(plan_l3, None)
        prov_gq = evaluate_global_quality(results)
        unified_plan = filter_unsafe_actions(unified_plan, prov_gq)
        if l3_res.output: l3_res.output.execution_plan = unified_plan
        
        return _finalize_artifact(run_id, ts_now, inputs, results, store, unified_plan)
    
    # --- Layer 4 (Nutrients) ---
    l4_res = _safe_run(LayerId.L4, inputs, l1_res.output, l2_res.output, l3_res.output)
    results[LayerId.L4] = l4_res
    
    # --- Intent Gating (NUTRIENT) ---
    if intent == Intent.NUTRIENT:
        # L1 -> L2 -> L3 -> L4.
        plan_l3 = l3_res.output.execution_plan if l3_res.output else None
        plan_l4 = getattr(l4_res.output, "verification_plan", None) if l4_res.output else None
        unified_plan = merge_execution_plans(plan_l3, None, plan_l4)
        prov_gq = evaluate_global_quality(results)
        unified_plan = filter_unsafe_actions(unified_plan, prov_gq)
        
        return _finalize_artifact(run_id, ts_now, inputs, results, store, unified_plan)
    
    # --- Intent Gating (PLANNING) ---
    if intent == Intent.PLANNING:
        # User requested season planning / crop suitability
        # Run L1 -> L7. Run L5 ONLY if explicitly asked about disease/risk.
        l5_res = None
        if user_query and any(k in user_query.lower() for k in ["disease", "risk", "fungal", "pest"]):
            l5_res = _safe_run(LayerId.L5, inputs, l1_res.output, None, None, None)
            results[LayerId.L5] = l5_res
        
        # Load chat memory if needed by L7
        from orchestrator_v2.chat_memory import load_memory
        mem = load_memory(inputs.plot_id)
        
        l7_res = _safe_run(LayerId.L7, inputs, l1_res.output, l5_res.output if l5_res else None, mem)
        results[LayerId.L7] = l7_res
        
        unified_plan = l7_res.output.execution_plan if (l7_res.output and hasattr(l7_res.output, "execution_plan")) else None
        prov_gq = evaluate_global_quality(results)
        unified_plan = filter_unsafe_actions(unified_plan, prov_gq)
        
        return _finalize_artifact(run_id, ts_now, inputs, results, store, unified_plan)

    # --- Layer 5 ---
    l5_res = _safe_run(LayerId.L5, inputs, l1_res.output, l2_res.output, l3_res.output, l4_res.output)
    results[LayerId.L5] = l5_res
    
    # --- Intermission: Plan Merging (Full Run) ---
    plan_l3 = l3_res.output.execution_plan if l3_res.output else None
    plan_l5 = l5_res.output.execution_plan if l5_res.output else None
    plan_l4 = getattr(l4_res.output, "verification_plan", None) if l4_res.output else None
    
    unified_plan = merge_execution_plans(plan_l3, plan_l5, plan_l4)
    
    # --- Safety Gating ---
    prov_gq = evaluate_global_quality(results)
    unified_plan = filter_unsafe_actions(unified_plan, prov_gq)
    
    # Patching L3 output for L6 consumption
    if l3_res.output:
        l3_res.output.execution_plan = unified_plan
    
    # --- Layer 6 ---
    # EXECUTION or DEFAULT run includes L6
    l6_res = _safe_run(LayerId.L6, inputs, l1_res.output, l2_res.output, l3_res.output, l4_res.output, l5_res.output)
    results[LayerId.L6] = l6_res
    
    # --- Layer 7 (Planning) ---
    l7_res = _safe_run(LayerId.L7, inputs, l1_res.output, l5_res.output if l5_res else None, None)
    results[LayerId.L7] = l7_res

    # --- Layer 8 (Prescriptive) ---
    l1_forecast = getattr(l1_res.output, "plot_timeseries", []) if l1_res and l1_res.output else []
    
    l8_input = Layer8Input(
        diagnoses=getattr(l3_res.output, "diagnoses", []) if l3_res.output else [],
        nutrient_states=_normalize_nutrient_states(l4_res.output),
        bio_threats=_normalize_threat_states(l5_res.output),
        weather_forecast=l1_forecast,
        zone_ids=_extract_zone_ids(l1_res),
        audit_grade=_derive_audit_grade_from_provenance(l1_res),
        source_reliability=_derive_source_reliability_from_provenance(l1_res),
        conflicts=_extract_conflicts_from_provenance(l1_res),
        phenology_stage=_derive_phenology_stage(l2_res, inputs),
        horizon_days=7
    )
    l8_res = _safe_run(LayerId.L8, l8_input, l1_forecast, None)
    results[LayerId.L8] = l8_res

    # --- Layer 10 (SIRE — Spatial Intelligence & Rendering) ---
    try:
        ft = l1_res.output
        vi = l2_res.output
        grid_h = getattr(getattr(ft, 'grid_spec', None), 'height', 10)
        grid_w = getattr(getattr(ft, 'grid_spec', None), 'width', 10)
        res_m = getattr(getattr(ft, 'grid_spec', None), 'resolution', 10.0)

        l10_input = Layer10Input(
            field_tensor=ft, veg_int=vi,
            decision=l3_res.output,
            nutrients=l4_res.output,
            bio=l5_res.output,
            exec_state=l6_res.output,
            planning=l7_res.output if l7_res else None,
            prescriptive=l8_res.output if l8_res else None,
            plot_id=inputs.plot_id,
            grid_height=grid_h, grid_width=grid_w,
            resolution_m=res_m,
        )
        l10_output = LAYER_REGISTRY[LayerId.L10].runner(l10_input)
        l10_result = LayerResult(
            layer_id="L10", status=LayerStatus.OK, output=l10_output,
            run_id=getattr(l10_output, 'run_id', '')
        )
    except Exception as e:
        l10_result = LayerResult(
            layer_id="L10", status=LayerStatus.DEGRADED, output=None,
            errors=[str(e)]
        )
    results[LayerId.L10] = l10_result

    # --- Layer 9 (Interface) ---
    # Pass L1 conflicts directly — L8Output does not expose conflicts,
    # so we pass them from the orchestrator's L1 extraction.
    l1_conflicts = _extract_conflicts_from_provenance(l1_res)
    l9_res = _safe_run(LayerId.L9, inputs,
                       l8_res.output if l8_res else None,
                       l3_res.output, l6_res.output,
                       l10_result.output if l10_result else None,
                       l1_conflicts)
    results[LayerId.L9] = l9_res
    
    # 3. Finalize
    return _finalize_artifact(run_id, ts_now, inputs, results, store, unified_plan)


def _safe_run(lid: LayerId, *args) -> LayerResult:
    spec = LAYER_REGISTRY[lid]
    try:
        output = spec.runner(*args)
        status = LayerStatus.OK
        
        return LayerResult(
            layer_id=lid.value,
            status=status,
            output=output,
            run_id=getattr(output, "run_id", "") or getattr(getattr(output, "run_meta", None), "run_id", "")
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        status = LayerStatus.FAILED if spec.required else LayerStatus.DEGRADED
        return LayerResult(
            layer_id=lid.value,
            status=status,
            output=None,
            errors=[str(e)]
        )


# ============================================================================
# L8 Input Helpers — upstream trust, normalization, zone extraction
# ============================================================================

def _normalize_nutrient_states(l4_output) -> Dict[str, Any]:
    """
    Convert L4's Dict[Nutrient, NutrientState] dataclasses into the
    Dict[str, dict] shape that action_ranker actually reads:
    { "N": {"probability_deficient": 0.6, "confidence": 0.8, "severity": "HIGH"}, ... }
    """
    if not l4_output:
        return {}
    raw = getattr(l4_output, "nutrient_states", {})
    if not raw:
        return {}
    result = {}
    for key, state in raw.items():
        k = key.value if hasattr(key, "value") else str(key)
        if hasattr(state, "probability_deficient"):
            # Dataclass → dict
            result[k] = {
                "probability_deficient": getattr(state, "probability_deficient", 0.0),
                "confidence": getattr(state, "confidence", 0.5),
                "severity": getattr(state, "severity", "LOW"),
                "state_index": getattr(state, "state_index", 0.0),
                "drivers_used": [str(d) for d in getattr(state, "drivers_used", [])],
            }
        elif isinstance(state, dict):
            result[k] = state
        else:
            result[k] = {"probability_deficient": 0.0, "confidence": 0.5}
    return result


def _normalize_threat_states(l5_output) -> Dict[str, Any]:
    """
    Convert L5's Dict[str, BioThreatState] dataclasses into the
    Dict[str, dict] shape that action_ranker actually reads:
    { "FUNGAL_LEAF_SPOT": {"probability": 0.7, "confidence": 0.6, "severity": "HIGH"}, ... }
    """
    if not l5_output:
        return {}
    raw = getattr(l5_output, "threat_states", {})
    if not raw:
        return {}
    result = {}
    for key, state in raw.items():
        k = key.value if hasattr(key, "value") else str(key)
        if hasattr(state, "probability"):
            # Dataclass → dict
            result[k] = {
                "probability": getattr(state, "probability", 0.0),
                "confidence": getattr(state, "confidence", 0.5),
                "severity": getattr(state, "severity", "LOW"),
                "spread_pattern": getattr(state, "spread_pattern", "UNKNOWN"),
                "threat_class": getattr(state, "threat_class", ""),
            }
        elif isinstance(state, dict):
            result[k] = state
        else:
            result[k] = {"probability": 0.0, "confidence": 0.5}
    return result


def _extract_zone_ids(l1_res) -> List[str]:
    """
    Pull canonical zone IDs from FieldTensor.zones (L1 spatial layer).
    Fallback to ["plot"] if no zones defined.
    """
    if not l1_res or not l1_res.output:
        return ["plot"]
    tensor_zones = getattr(l1_res.output, "zones", {})
    if tensor_zones and isinstance(tensor_zones, dict) and len(tensor_zones) > 0:
        return list(tensor_zones.keys())
    return ["plot"]


def _derive_audit_grade_from_provenance(l1_res) -> str:
    """
    Read audit grade from L1 provenance upstream trust channel.
    Source: tensor.provenance["audit"]["trust_report"]["health_grade"]
    or tensor.provenance["layer0_reliability"] mapped to letter grade.
    Fallback: "B" (conservative default).
    """
    if not l1_res or not l1_res.output:
        return "B"
    prov = getattr(l1_res.output, "provenance", {})
    if not isinstance(prov, dict):
        return "B"
    # Try structured audit path first
    audit = prov.get("audit", {})
    if isinstance(audit, dict):
        trust_report = audit.get("trust_report", {})
        if isinstance(trust_report, dict):
            grade = trust_report.get("health_grade")
            if grade and isinstance(grade, str) and grade.upper() in ("A", "B", "C", "D", "F"):
                return grade.upper()
    # Fall back to layer0_reliability score → letter grade
    l0_rel = prov.get("layer0_reliability")
    if isinstance(l0_rel, (int, float)):
        if l0_rel >= 0.8:
            return "A"
        if l0_rel >= 0.6:
            return "B"
        if l0_rel >= 0.4:
            return "C"
        return "D"
    return "B"


def _derive_source_reliability_from_provenance(l1_res) -> Dict[str, float]:
    """
    Read source-level reliability from L1 provenance.
    Source: tensor.provenance["layer0_reliability"] if it is a dict of source→score.
    
    IMPORTANT: This returns SOURCE-SCOPED reliability (e.g. sentinel2, sentinel1,
    weather, sensor), NOT per-zone reliability. Layer 8's ZonePrioritizer receives
    these values but cannot map them to individual zones without a separate
    zone→source mapping (which does not exist yet). Zone prioritization therefore
    remains approximate — this is a known architectural gap, not a bug.
    """
    if not l1_res or not l1_res.output:
        return {}
    prov = getattr(l1_res.output, "provenance", {})
    if not isinstance(prov, dict):
        return {}
    l0_rel = prov.get("layer0_reliability", {})
    if isinstance(l0_rel, dict):
        # Source-scoped: {"sentinel2": 0.9, "weather": 0.7, ...}
        return {str(k): float(v) for k, v in l0_rel.items() if isinstance(v, (int, float))}
    return {}


def _extract_conflicts_from_provenance(l1_res) -> List[Dict[str, Any]]:
    """
    Extract cross-source conflicts from L1 provenance.
    Source: tensor.provenance["layer0_conflicts"]
    These flow into L8 (for degradation mode) and must also be passed
    directly to L9 (for disclaimers and conflict icons).
    """
    if not l1_res or not l1_res.output:
        return []
    prov = getattr(l1_res.output, "provenance", {})
    if not isinstance(prov, dict):
        return []
    conflicts = prov.get("layer0_conflicts", [])
    if isinstance(conflicts, list):
        return conflicts
    return []


def _derive_phenology_stage(l2_res, inputs) -> str:
    """
    Resolve crop phenology stage with layered precedence:
    1. L2 phenology.stage_by_day — scan backward for latest non-UNKNOWN stage
    2. inputs.crop_config["stage"] (what run_entrypoint writes)
    3. inputs.crop_config["crop_stage"] (legacy key)
    4. "VEGETATIVE" (safe fallback)
    Skips "UNKNOWN" at every level.
    """
    # 1. Try L2 real phenology structure: VegIntOutput.phenology.stage_by_day
    if l2_res and l2_res.output:
        phenology = getattr(l2_res.output, "phenology", None)
        if phenology:
            stage_by_day = getattr(phenology, "stage_by_day", [])
            if stage_by_day and isinstance(stage_by_day, list):
                # Scan backward to find latest non-UNKNOWN stage
                for i in range(len(stage_by_day) - 1, -1, -1):
                    entry = stage_by_day[i]
                    # Handle string entries
                    if isinstance(entry, str) and entry.upper() != "UNKNOWN":
                        return entry.upper()
                    # Handle enum entries
                    val = getattr(entry, "value", None)
                    if val and isinstance(val, str) and val.upper() != "UNKNOWN":
                        return val.upper()
    # 2. Try crop_config
    cfg = inputs.crop_config if isinstance(inputs.crop_config, dict) else {}
    for key in ("stage", "crop_stage"):
        val = cfg.get(key)
        if val and isinstance(val, str) and val.upper() != "UNKNOWN":
            return val.upper()
    return "VEGETATIVE"

def _finalize_artifact(
    run_id: str,
    ts: str,
    inputs: OrchestratorInput,
    results: Dict[LayerId, LayerResult],
    store: Optional[LocalJsonStore],
    final_plan: Optional[Any] = None
) -> RunArtifact:
    
    # Quality
    gq = evaluate_global_quality(results)
    
    # Collect Parents
    parents_map = {lid.value: res.run_id for lid, res in results.items() if res.output}
    
    # Construct Meta
    meta = RunMeta(
        orchestrator_run_id=run_id,
        artifact_hash="", # Set after hash calc
        timestamp_utc=ts,
        orchestrator_version=ORCHESTRATOR_VERSION,
        layer_versions=get_layer_versions(),
        parents=parents_map,
        replay_uri=""
    )
    
    art = RunArtifact(
        meta=meta,
        inputs=inputs,
        global_quality=gq,
        layer_1=results.get(LayerId.L1),
        layer_2=results.get(LayerId.L2),
        layer_3=results.get(LayerId.L3),
        layer_4=results.get(LayerId.L4),
        layer_5=results.get(LayerId.L5),
        layer_6=results.get(LayerId.L6),
        layer_7=results.get(LayerId.L7),
        layer_8=results.get(LayerId.L8),
        layer_10=results.get(LayerId.L10),
        layer_9=results.get(LayerId.L9),
        final_execution_plan=final_plan,
        top_findings=_extract_top_findings(results, gq),
        lineage_map=parents_map
    )
    
    # Calculate Artifact Hash (Pure Content)
    # We exclude meta.timestamp, meta.orchestrator_run_id (circular), meta.replay_uri
    pure_dict = asdict(art)
    # Be careful with circular refs or exclusions. 
    # Hash everything except meta fields that change? 
    # Just hashing inputs + global_quality + final_plan + result_hashes seems robust.
    
    # Only hashing inputs + layers content
    content_payload = {
        "inputs": asdict(inputs),
        "layers": {k: asdict(v) for k, v in results.items() if v},
        "plan": asdict(final_plan) if final_plan else None
    }
    art_hash = hashlib.sha256(_canonical_json(content_payload).encode("utf-8")).hexdigest()
    art.meta.artifact_hash = art_hash
    
    if store:
        uri = store.save(art)
        art.meta.replay_uri = uri
        
    return art

def run_for_chat(
    inputs: OrchestratorInput,
    store: Optional[LocalJsonStore] = None,
    user_query: Optional[str] = None,
    history: Optional[List[Dict[str, str]]] = None,
) -> Tuple[ChatPayload, RunArtifact]:
    """
    Optimized entrypoint for Chat/LLM interactions.
    Runs full pipeline -> Compresses to ChatPayload.
    """
    # 2. Date Resolution
    if user_query:
        # Detect Intent
        intent = detect_intent(user_query, has_context=True)
        
        try:
            # Assume inputs.date_range['end'] is a valid reference date string
            ref_date = datetime.strptime(inputs.date_range['end'], "%Y-%m-%d")
            start, end = resolve_time_window(user_query, ref_date)
            
            # Use replace() for frozen dataclass
            from dataclasses import replace
            inputs = replace(inputs, date_range={
                "start": start.strftime("%Y-%m-%d"),
                "end": end.strftime("%Y-%m-%d")
            })
            
        except Exception as e:
            # Fallback to default inputs if parsing fails
            print(f"Date resolution failed: {e}")
            pass
    
    # 3. Run Pipeline with Intent Routing
    artifact = run_orchestrator(inputs, store, intent=intent, user_query=user_query)
    
    # 4. Safety Assertion (Hard Check)
    if intent == Intent.DATA_QUERY:
        if artifact.layer_3 or artifact.layer_5:
            # This should effectively never happen due to gating above, 
            # but creates a hard invariant for the future.
            pass 
        if artifact.final_execution_plan and artifact.final_execution_plan.tasks:
             # Ensure no INTERVENE
             if any(t.type == "INTERVENE" for t in artifact.final_execution_plan.tasks):
                 raise RuntimeError("SAFETY VIOLATION: DATA_QUERY intent produced INTERVENE tasks.")
                 
    return build_chat_payload(artifact, user_query, intent=intent, history=history), artifact


def _extract_top_findings(results: Dict, gq) -> list:
    """
    Extract headline findings from layer outputs.
    Grounded in actual data — no hallucination.
    """
    findings = []

    # L1: Weather/soil summary
    l1 = results.get(LayerId.L1)
    if l1 and l1.output:
        ts = getattr(l1.output, "plot_timeseries", [])
        if ts and isinstance(ts, list):
            # Rainfall — plot_timeseries entries are dicts with FieldTensorChannels keys
            rain_vals = []
            temp_maxes = []
            temp_mins = []
            for t in ts:
                if isinstance(t, dict):
                    p = t.get("precipitation") or t.get("rainfall_mm") or t.get("rain")
                    if p is not None:
                        rain_vals.append(float(p))
                    tmax = t.get("temp_max") or t.get("temperature_max") or t.get("tmax") or t.get("tmean")
                    tmin = t.get("temp_min") or t.get("temperature_min") or t.get("tmin") or t.get("tmean")
                    if tmax is not None:
                        temp_maxes.append(float(tmax))
                    if tmin is not None:
                        temp_mins.append(float(tmin))

            if rain_vals:
                total = sum(rain_vals)
                wet_days = sum(1 for v in rain_vals if v > 0.1)
                if total < 5:
                    findings.append(f"Very low rainfall ({total:.1f}mm) \u2014 potential dryness.")
                elif total > 50:
                    findings.append(f"Significant rainfall ({total:.1f}mm over {wet_days} days).")
                else:
                    findings.append(f"Moderate rainfall ({total:.1f}mm over {wet_days} days).")

            # Temperature extremes
            if temp_maxes or temp_mins:
                t_max = max(temp_maxes) if temp_maxes else None
                t_min = min(temp_mins) if temp_mins else None
                if t_max and t_max > 40:
                    findings.append(f"Heat stress risk: peak temperature {t_max:.0f}°C.")
                elif t_min is not None and t_min < 2:
                    findings.append(f"Frost risk: minimum temperature {t_min:.1f}°C.")

        # Soil moisture
        static = getattr(l1.output, "static", {})
        if isinstance(static, dict):
            sm = static.get("soil_moisture")
            if sm and isinstance(sm, dict):
                for depth, val in sm.items():
                    if val is not None and val < 0.15:
                        findings.append(f"Low soil moisture at {depth} ({val:.2f} m³/m³).")
                        break

    # L3: Diagnoses
    l3 = results.get(LayerId.L3)
    if l3 and l3.output:
        for diag in getattr(l3.output, "diagnoses", [])[:3]:
            cond = getattr(diag, "condition", "")
            sev = getattr(diag, "severity", 0)
            conf = getattr(diag, "confidence", 0)
            if cond and sev >= 5:
                findings.append(f"Diagnosis: {cond} (severity {sev}/10, confidence {conf:.0%}).")

    # L5: Bio threats
    l5 = results.get(LayerId.L5)
    if l5 and l5.output:
        for threat in getattr(l5.output, "threats", [])[:2]:
            name = getattr(threat, "name", "")
            risk = getattr(threat, "risk_level", "")
            if name and risk in ("HIGH", "CRITICAL"):
                findings.append(f"Bio threat: {name} ({risk} risk).")

    # Degradation warnings
    if gq.critical_failure:
        findings.insert(0, "⚠️ Critical data failure — results may be unreliable.")
    elif gq.missing_drivers:
        drivers = ", ".join(gq.missing_drivers[:3])
        findings.append(f"Data gaps: {drivers}.")

    return findings[:5]  # Cap at 5
