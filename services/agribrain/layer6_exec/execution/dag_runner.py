
from typing import Dict, List, Any, Tuple
from datetime import datetime

from services.agribrain.layer6_exec.schema import (
    ExecutionState, TaskStatus, OperationalContext
)
from services.agribrain.layer3_decision.schema import ExecutionPlan, TaskNode

def _is_expired(node: TaskNode, current_date: str) -> bool:
    # Check if beyond valid window (stub logic: assuming tasks usually valid for 7 days if not specified)
    return False 

def update_execution_state(
    plan: ExecutionPlan,
    current_state: ExecutionState,
    op_context: OperationalContext,
    normalized_evidence: List[Any], # List[NormalizedEvidence]
    current_time: str
) -> ExecutionState:
    """
    Core DAG Update Logic.
    Transition PENDING -> READY | BLOCKED | EXPIRED
    Transition RUNNING -> COMPLETED (if evidence exists)
    """
    
    # 1. Initialize missing tasks
    new_status_map = current_state.tasks.copy()
    
    node_map = {n.task_id: n for n in plan.tasks}
    
    # Sort for deterministic processing
    sorted_nodes = sorted(plan.tasks, key=lambda x: x.task_id)
    
    changes = []

    for node in sorted_nodes:
        tid = node.task_id
        current_status = new_status_map.get(tid, TaskStatus.PENDING)
        
        # --- State Transitions ---
        
        if current_status == TaskStatus.PENDING:
            # Check dependencies
            all_deps_met = True
            for dep_id in node.depends_on:
                dep_status = new_status_map.get(dep_id, TaskStatus.PENDING)
                if dep_status != TaskStatus.COMPLETED:
                    all_deps_met = False
                    break
            
            if not all_deps_met:
                # Keep Pending, or Block if parent failed?
                # Simple DAG: Keep Pending
                pass
            else:
                # Deps met. Check Preconditions (Op Context)
                # Stub: Assume all checks pass for now unless explicitly blocked
                new_status_map[tid] = TaskStatus.READY
                changes.append(f"Task {tid} -> READY")

        elif current_status == TaskStatus.READY:
            # External agent picks this up. We don't auto-run unless it's a computation.
            # But we can check if Evidence auto-completes it.
            # Stub: If this were a 'System' task, we might set RUNNING.
            pass
            
        elif current_status == TaskStatus.RUNNING:
            # Check for completion evidence
            # Look for evidence referencing this task_id
            found_evidence = False
            for ev in normalized_evidence:
                if str(tid) in ev.source_refs.get("task_id", ""):
                    found_evidence = True
                    break
            
            if found_evidence:
                new_status_map[tid] = TaskStatus.COMPLETED
                changes.append(f"Task {tid} -> COMPLETED (Evidence Found)")
    
    return ExecutionState(
        tasks=new_status_map,
        last_updated=current_time,
        logs=current_state.logs + [{"ts": current_time, "msg": c} for c in changes]
    )
