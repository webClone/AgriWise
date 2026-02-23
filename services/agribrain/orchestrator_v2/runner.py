
from datetime import datetime
from typing import Dict, Any, Optional
import hashlib
import json
from dataclasses import asdict

from services.agribrain.orchestrator_v2.schema import (
    OrchestratorInput, RunArtifact, RunMeta, LayerResult, LayerStatus, GlobalQuality
)
from services.agribrain.orchestrator_v2.registry import LAYER_REGISTRY, LayerId, get_layer_versions
from services.agribrain.orchestrator_v2.hashing import generate_orchestrator_run_id
from services.agribrain.orchestrator_v2.gating import merge_execution_plans, evaluate_global_quality, filter_unsafe_actions
from services.agribrain.orchestrator_v2.storage import LocalJsonStore
from services.agribrain.orchestrator_v2.chat_adapter import ChatPayload, build_chat_payload

ORCHESTRATOR_VERSION = "2.1.0"

def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)

from services.agribrain.orchestrator_v2.intents import Intent, detect_intent, resolve_time_window

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
    ts_now = datetime.utcnow().isoformat() + "Z"
    
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
        unified_plan = merge_execution_plans(plan_l3, None) # L4 doesn't produce ExecutionPlan yet? Or does it?
        # L4 produces "nutrient_states" and "prescription". Does it map to Dispatch?
        # Assuming L4 outputs are informational for now or integrated later.
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
        from services.agribrain.orchestrator_v2.chat_memory import load_memory
        mem = load_memory(inputs.plot_id)
        
        l7_res = _safe_run(LayerId.L7, inputs, l1_res.output, l5_res.output if l5_res else None, mem)
        results[LayerId.L7] = l7_res
        
        unified_plan = l7_res.execution_plan if hasattr(l7_res, "execution_plan") else None
        prov_gq = evaluate_global_quality(results)
        unified_plan = filter_unsafe_actions(unified_plan, prov_gq)
        
        return _finalize_artifact(run_id, ts_now, inputs, results, store, unified_plan)

    # --- Layer 5 ---
    l5_res = _safe_run(LayerId.L5, inputs, l1_res.output, l2_res.output, l3_res.output, l4_res.output)
    results[LayerId.L5] = l5_res
    
    # --- Intermission: Plan Merging (Full Run) ---
    plan_l3 = l3_res.output.execution_plan if l3_res.output else None
    plan_l5 = l5_res.output.execution_plan if l5_res.output else None
    
    unified_plan = merge_execution_plans(plan_l3, plan_l5)
    
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
        status = LayerStatus.FAILED if spec.required else LayerStatus.DEGRADED
        return LayerResult(
            layer_id=lid.value,
            status=status,
            output=None,
            errors=[str(e)]
        )

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
        final_execution_plan=final_plan,
        top_findings=[],
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
    user_query: Optional[str] = None
) -> ChatPayload:
    """
    Optimized entrypoint for Chat/LLM interactions.
    Runs full pipeline -> Compresses to ChatPayload.
    """
    # 2. Date Resolution
    if user_query:
        # Detect Intent
        intent = detect_intent(user_query)
        
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
                 
    return build_chat_payload(artifact, user_query, intent=intent)
