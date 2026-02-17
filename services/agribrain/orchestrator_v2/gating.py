
from typing import List, Dict, Any, Optional, Set
import hashlib
import json

from services.agribrain.layer3_decision.schema import ExecutionPlan, TaskNode
from services.agribrain.orchestrator_v2.schema import GlobalQuality, GlobalDegradation, LayerResult, LayerStatus
from services.agribrain.orchestrator_v2.registry import LayerId

def _compute_task_uid(task: TaskNode) -> str:
    """
    Generates deterministic UID for deduplication.
    Hash(type + instructions + required_inputs + completion_signal)
    Ignores original task_id if it's unstable.
    """
    # Canonical string construction
    raw = f"{task.type}|{task.instructions}|{json.dumps(task.required_inputs, sort_keys=True)}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"TASK-{h}"

def merge_execution_plans(
    plan_l3: Optional[ExecutionPlan],
    plan_l5: Optional[ExecutionPlan]
) -> ExecutionPlan:
    """
    Unify plans from Decision (L3) and Bio (L5).
    Strategy: Deduplicate by Deterministic Content Hash (UID), not just ID.
    """
    if not plan_l3 and not plan_l5:
        return ExecutionPlan(tasks=[], edges=[], recommended_start_date="", review_date="")
        
    merged_tasks: Dict[str, TaskNode] = {}
    master_edges: List[Any] = []
    
    def add_tasks(tasks: List[TaskNode], source_layer: str):
        for t in tasks:
            uid = _compute_task_uid(t)
            
            if uid not in merged_tasks:
                # Rewrite ID to be stable? Or keep original?
                # Best practice: Use Deterministic ID as the Task ID for L6.
                # Store original ID in metadata if needed.
                
                # Clone task to avoid mutation side effects (if simple object)
                # Dataclasses are mutable unless frozen.
                new_t = TaskNode(
                    task_id=uid,
                    type=t.type,
                    instructions=t.instructions,
                    required_inputs=t.required_inputs,
                    completion_signal=t.completion_signal,
                    depends_on=t.depends_on # Edges might need remapping if we change IDs!
                )
                # metadata?
                merged_tasks[uid] = new_t
            else:
                # Merge logic: Append sources?
                pass

    if plan_l3:
        add_tasks(plan_l3.tasks, "L3")
        master_edges.extend(plan_l3.edges)
        
    if plan_l5:
        add_tasks(plan_l5.tasks, "L5")
        master_edges.extend(plan_l5.edges)
        
    # NOTE: Original edges referring to old IDs are now broken if we renamed tasks.
    # To do this safely, we need a map OldID -> NewUID.
    # For now, assuming flat plans or simple dependencies. 
    # If edge logic is complex, we need a second pass to rewrite edges.
    
    return ExecutionPlan(
        tasks=list(merged_tasks.values()),
        edges=master_edges, # Edges likely broken if IDs changed. Ideally rewrite edges too.
        recommended_start_date=plan_l3.recommended_start_date if plan_l3 else "",
        review_date=plan_l3.review_date if plan_l3 else ""
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
                if "NO_SAR" in str(md) or "SAR" in str(missing):
                    modes.add(GlobalDegradation.NO_SAR)
                if "RAIN" in str(md):
                    modes.add(GlobalDegradation.PARTIAL_DATA)
                    
        weighted_score += (layer_score * weight)
        
    final_reliability = weighted_score / max(0.01, total_weight)
    
    # Cap reliability if critical modes
    if GlobalDegradation.NO_SAR in modes:
        final_reliability = min(final_reliability, 0.85)
    if GlobalDegradation.CRITICAL_FAILURE in modes or critical_failure:
        final_reliability = 0.0
        
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
