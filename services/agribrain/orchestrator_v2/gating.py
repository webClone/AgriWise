
from typing import List, Dict, Any, Optional, Set
import hashlib
import json

from services.agribrain.layer3_decision.schema import ExecutionPlan, TaskNode
from services.agribrain.orchestrator_v2.schema import GlobalQuality, GlobalDegradation, LayerResult, LayerStatus
from services.agribrain.orchestrator_v2.registry import LayerId

def _compute_task_uid(task: TaskNode) -> str:
    """
    Generates deterministic UID for deduplication.
    Hash(type + instructions + required_inputs + target_zones)
    
    target_zones is included so that spatially distinct tasks
    (e.g. SCOUT ZoneA vs SCOUT ZoneB) are NOT collapsed.
    target_points is excluded from UID (too volatile for stable dedup).
    """
    zones_str = json.dumps(sorted(task.target_zones), sort_keys=True) if task.target_zones else "[]"
    raw = f"{task.type}|{task.instructions}|{json.dumps(task.required_inputs, sort_keys=True)}|{zones_str}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"TASK-{h}"

def merge_execution_plans(
    plan_l3: Optional[ExecutionPlan],
    plan_l5: Optional[ExecutionPlan],
    plan_l4: Optional[ExecutionPlan] = None,
) -> ExecutionPlan:
    """
    Unify operational plans from Decision (L3), Nutrients (L4), and Bio (L5).
    Strategy: Deduplicate by Deterministic Content Hash (UID), not just ID.
    Edge remapping: All old task IDs are rewritten to stable UIDs.
    
    NOTE: L7 (strategic planning) is intentionally excluded.
    L7's execution_plan is used only in the PLANNING intent branch.
    """
    all_plans = [p for p in [plan_l3, plan_l5, plan_l4] if p]
    if not all_plans:
        return ExecutionPlan(tasks=[], edges=[], recommended_start_date="", review_date="")
        
    merged_tasks: Dict[str, TaskNode] = {}
    master_edges: List[Any] = []
    id_remap: Dict[str, str] = {}  # old_id -> new_uid
    
    def add_tasks(tasks: List[TaskNode], source_layer: str):
        for t in tasks:
            uid = _compute_task_uid(t)
            id_remap[t.task_id] = uid
            
            if uid not in merged_tasks:
                new_t = TaskNode(
                    task_id=uid,
                    type=t.type,
                    instructions=t.instructions,
                    required_inputs=t.required_inputs,
                    completion_signal=t.completion_signal,
                    depends_on=t.depends_on,  # Will be remapped below
                    target_zones=list(t.target_zones) if t.target_zones else [],
                    target_points=list(t.target_points) if t.target_points else [],
                )
                merged_tasks[uid] = new_t

    if plan_l3:
        add_tasks(plan_l3.tasks, "L3")
        master_edges.extend(plan_l3.edges)
    
    if plan_l4:
        add_tasks(plan_l4.tasks, "L4")
        master_edges.extend(plan_l4.edges)
        
    if plan_l5:
        add_tasks(plan_l5.tasks, "L5")
        master_edges.extend(plan_l5.edges)
    
    # Remap depends_on references in all tasks
    for task in merged_tasks.values():
        if task.depends_on:
            task.depends_on = [id_remap.get(dep, dep) for dep in task.depends_on]
    
    # Remap edges — handles both list/tuple and dict formats.
    # Preserves extra metadata keys in dict edges (e.g. "condition").
    remapped_edges = []
    for edge in master_edges:
        if isinstance(edge, dict) and "from" in edge and "to" in edge:
            # Dict edge: remap from/to while preserving all other keys
            remapped = dict(edge)
            remapped["from"] = id_remap.get(edge["from"], edge["from"])
            remapped["to"] = id_remap.get(edge["to"], edge["to"])
            if remapped not in remapped_edges:
                remapped_edges.append(remapped)
        elif isinstance(edge, (list, tuple)) and len(edge) >= 2:
            remapped = [id_remap.get(edge[0], edge[0]), id_remap.get(edge[1], edge[1])]
            if remapped not in remapped_edges:
                remapped_edges.append(remapped)
        else:
            remapped_edges.append(edge)
    
    # Deliberate date precedence: L3 -> L4 -> L5
    def _first_date(*plans, attr: str) -> str:
        for p in plans:
            if p:
                val = getattr(p, attr, "")
                if val:
                    return val
        return ""
    
    return ExecutionPlan(
        tasks=list(merged_tasks.values()),
        edges=remapped_edges,
        recommended_start_date=_first_date(plan_l3, plan_l4, plan_l5, attr="recommended_start_date"),
        review_date=_first_date(plan_l3, plan_l4, plan_l5, attr="review_date"),
    )

def evaluate_global_quality(
    results: Dict[LayerId, LayerResult]
) -> GlobalQuality:
    """
    Determine system-wide health using Weighted Aggregation.
    """
    modes: Set[GlobalDegradation] = set()
    missing: List[str] = []
    errors: List[str] = []
    
    kw = {
        LayerId.L1: 0.40,
        LayerId.L2: 0.15,
        LayerId.L3: 0.20,
        LayerId.L4: 0.10,
        LayerId.L5: 0.10,
        LayerId.L6: 0.05
    }
    
    weighted_score = 0.0
    total_weight = 0.0
    
    critical_failure = False
    
    for lid, weight in kw.items():
        if lid not in results:
            continue
            
        res = results[lid]
        total_weight += weight
        
        # Base score for this layer
        layer_score = 1.0
        
        if res.status == LayerStatus.FAILED:
            layer_score = 0.0
            errors.extend([f"{lid}: {e}" for e in res.errors])
            if lid == LayerId.L1:
                critical_failure = True
                modes.add(GlobalDegradation.CRITICAL_FAILURE)
        
        elif res.status == LayerStatus.DEGRADED:
            layer_score = 0.7 # Penalty
            modes.add(GlobalDegradation.PARTIAL_DATA) # Generic fallback
            
        # Refine with internal metrics if available
        if res.output:
            qm = getattr(res.output, "quality_metrics", None)
            if qm:
                rel = getattr(qm, "decision_reliability", 1.0)
                layer_score = min(layer_score, rel)
                
                md = getattr(qm, "missing_drivers", [])
                missing.extend([f"{lid}.{d}" for d in md])
                
                # Check specifics
                degradation_str = str(getattr(qm, "degradation_mode", ""))
                if "NO_SAR" in str(md) or ("SAR" in str(missing) and "LOW_SAR_CADENCE" not in degradation_str):
                    modes.add(GlobalDegradation.NO_SAR)
                if "LOW_SAR_CADENCE" in degradation_str:
                    modes.add(GlobalDegradation.LOW_SAR_CADENCE)
                if "RAIN" in str(md):
                    modes.add(GlobalDegradation.PARTIAL_DATA)
                    
        weighted_score += (layer_score * weight)
        
    final_reliability = weighted_score / max(0.01, total_weight)
    
    # Cap reliability if critical modes
    if GlobalDegradation.NO_SAR in modes:
        final_reliability = min(final_reliability, 0.85)
    if GlobalDegradation.LOW_SAR_CADENCE in modes:
        final_reliability = min(final_reliability, 0.95)
        
    # Only hardcode 0.0 if literally 0 weight was accumulated
    if total_weight < 0.01:
        final_reliability = 0.0
    elif critical_failure:
        # Instead of 0.0, we just apply a massive penalty but keep base scores
        final_reliability = max(0.1, final_reliability * 0.3)
        
    if not modes:
        modes.add(GlobalDegradation.NORMAL)
        
    return GlobalQuality(
        modes=list(modes),
        reliability_score=round(final_reliability, 3),
        missing_drivers=list(set(missing)),
        critical_errors=errors,
        critical_failure=critical_failure
    )

def filter_unsafe_actions(plan: ExecutionPlan, quality: GlobalQuality) -> ExecutionPlan:
    """
    Safety Gate: Remove 'INTERVENE' tasks if confidence is low or Critical Data Gaps exist.
    """
    if not plan or not plan.tasks:
        return plan
        
    unsafe_modes = {GlobalDegradation.NO_SAR, GlobalDegradation.CRITICAL_FAILURE}
    has_unsafe_mode = any(m in unsafe_modes for m in quality.modes)
    
    # If partial data, check reliability score
    is_unreliable = quality.reliability_score < 0.7
    
    # If DATA_GAP is the primary issue, we should not intervene blindly.
    # (In V2, this is handled by L3 logic, but global safety net is needed)
    
    if has_unsafe_mode or is_unreliable:
        safe_tasks = []
        for t in plan.tasks:
            # Allow MONITOR and VERIFY, Block INTERVENE
            if t.type in ["MONITOR", "VERIFY"]:
                safe_tasks.append(t)
            elif t.type == "INTERVENE":
                # Log or just drop
                pass
                
        # Return filtered plan
        return ExecutionPlan(
            tasks=safe_tasks,
            edges=plan.edges, # Edges might be broken, but safer than running unsafe key tasks
            recommended_start_date=plan.recommended_start_date,
            review_date=plan.review_date
        )
        
    return plan
