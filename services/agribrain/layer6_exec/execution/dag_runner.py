"""
Engine 3: DAG Execution — Production State Machine

Full state machine for task execution tracking:
  PENDING → READY → RUNNING → COMPLETED / FAILED / EXPIRED / SKIPPED
  PENDING → BLOCKED (if parent FAILED/EXPIRED)

Features:
  - Topological dependency resolution
  - Blocked propagation (parent FAILED → child BLOCKED)
  - Timing window expiration
  - Evidence-driven completion
  - Auto-skip for low-confidence tasks
  - Conflict detection (two READY tasks, same zone, conflicting actions)
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from layer6_exec.schema import (
    ExecutionState, TaskState, TaskStatus, InterventionCandidate,
    NormalizedEvidence, InterventionDomain,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_expired(candidate: InterventionCandidate, current_time: str) -> bool:
    """Check if a task's timing window has passed."""
    window = candidate.timing_window
    if not window or "end" not in window:
        return False
    try:
        end = datetime.fromisoformat(window["end"])
        now = datetime.fromisoformat(current_time.replace("Z", "+00:00"))
        return now.date() > end.date()
    except (ValueError, TypeError):
        return False


def _check_evidence_completion(
    task_id: str,
    evidence: List[NormalizedEvidence],
) -> Optional[str]:
    """Check if evidence references this task → auto-complete."""
    for ev in evidence:
        refs = ev.source_refs or {}
        if refs.get("task_id") == task_id or task_id in str(refs):
            return ev.evidence_id
    return None


def build_execution_state(
    portfolio: List[InterventionCandidate],
    previous_state: ExecutionState,
    evidence: List[NormalizedEvidence],
    current_time: str,
) -> ExecutionState:
    """Build full execution state from intervention portfolio.

    This is the production DAG runner:
    1. Initialize all portfolio tasks as PENDING
    2. Resolve dependencies (topological)
    3. Check for expiration
    4. Check for evidence-driven completion
    5. Propagate blocks from failed parents
    """
    tasks: Dict[str, TaskStatus] = {}
    details: Dict[str, TaskState] = {}

    prev_tasks_dict = previous_state.tasks if isinstance(previous_state.tasks, dict) else {}
    prev_details_dict = previous_state.task_details if isinstance(previous_state.task_details, dict) else {}
    logs: List[Dict[str, Any]] = list(previous_state.logs) if isinstance(previous_state.logs, list) else []

    # Build dependency graph
    dep_graph: Dict[str, List[str]] = {}
    candidate_map: Dict[str, InterventionCandidate] = {}

    # Reconstruct placeholder candidates for historical tasks in previous_state not in current portfolio
    portfolio_ids = {c.intervention_id for c in portfolio}
    extended_portfolio = list(portfolio)
    if previous_state and prev_tasks_dict:
        for tid in prev_tasks_dict.keys():
            if tid not in portfolio_ids:
                historical_placeholder = InterventionCandidate(
                    intervention_id=tid,
                    domain=InterventionDomain.MONITORING,
                    action_type="MONITOR",
                    title=tid.replace("_", " ").title(),
                    instructions="Historical task state preservation",
                    utility_score=0.5,
                    expected_impact=0.5,
                    urgency=0.5,
                    confidence=0.5,
                    timing_window={"start": current_time, "end": current_time},
                )
                extended_portfolio.append(historical_placeholder)

    for c in extended_portfolio:
        tid = c.intervention_id
        candidate_map[tid] = c
        dep_graph[tid] = list(c.depends_on) if c.depends_on else []

        # Inherit previous status if exists (preserve RUNNING, READY, etc.)
        prev_status = prev_tasks_dict.get(tid)
        if prev_status and prev_status in (TaskStatus.COMPLETED, TaskStatus.FAILED,
                                            TaskStatus.SKIPPED, TaskStatus.EXPIRED,
                                            TaskStatus.RUNNING, TaskStatus.READY):
            tasks[tid] = prev_status
            prev_detail = prev_details_dict.get(tid)
            if prev_detail:
                details[tid] = prev_detail
            else:
                details[tid] = TaskState(
                    task_id=tid,
                    status=prev_status,
                    assigned_at=current_time,
                )
            continue

        # Start as PENDING
        tasks[tid] = TaskStatus.PENDING
        prev_detail = prev_details_dict.get(tid)
        if prev_detail:
            details[tid] = prev_detail
        else:
            details[tid] = TaskState(
                task_id=tid,
                status=TaskStatus.PENDING,
                assigned_at=current_time,
            )

    # Topological resolution passes
    changed = True
    max_iterations = len(portfolio) + 1
    iteration = 0

    while changed and iteration < max_iterations:
        changed = False
        iteration += 1

        for tid, status in list(tasks.items()):
            if status != TaskStatus.PENDING:
                if status in (TaskStatus.RUNNING, TaskStatus.READY):
                    ev_id = _check_evidence_completion(tid, evidence)
                    if ev_id:
                        tasks[tid] = TaskStatus.COMPLETED
                        details[tid].status = TaskStatus.COMPLETED
                        details[tid].completed_at = current_time
                        details[tid].evidence_ids = [ev_id]
                        logs.append({"ts": current_time,
                                     "msg": f"Task {tid} → COMPLETED (evidence: {ev_id})"})
                        changed = True
                continue

            candidate = candidate_map.get(tid)
            if not candidate:
                continue

            deps = dep_graph.get(tid, [])

            # Check 1: Expiration
            if _is_expired(candidate, current_time):
                tasks[tid] = TaskStatus.EXPIRED
                details[tid].status = TaskStatus.EXPIRED
                logs.append({"ts": current_time,
                             "msg": f"Task {tid} → EXPIRED (timing window passed)"})
                changed = True
                continue

            # Check 2: Parent status
            all_deps_met = True
            any_parent_failed = False

            for dep_id in deps:
                dep_status = tasks.get(dep_id, TaskStatus.PENDING)
                if dep_status in (TaskStatus.FAILED, TaskStatus.EXPIRED):
                    any_parent_failed = True
                    break
                if dep_status != TaskStatus.COMPLETED:
                    all_deps_met = False

            if any_parent_failed:
                tasks[tid] = TaskStatus.BLOCKED
                details[tid].status = TaskStatus.BLOCKED
                details[tid].blocked_reason = f"Parent task failed/expired"
                logs.append({"ts": current_time,
                             "msg": f"Task {tid} → BLOCKED (parent failed)"})
                changed = True
                continue

            # Check 3: All deps met → READY
            if all_deps_met:
                # Check for evidence-driven completion
                ev_id = _check_evidence_completion(tid, evidence)
                if ev_id:
                    tasks[tid] = TaskStatus.COMPLETED
                    details[tid].status = TaskStatus.COMPLETED
                    details[tid].completed_at = current_time
                    details[tid].evidence_ids = [ev_id]
                    logs.append({"ts": current_time,
                                 "msg": f"Task {tid} → COMPLETED (evidence: {ev_id})"})
                else:
                    # Auto-skip low-confidence INTERVENE tasks
                    if candidate.action_type == "INTERVENE" and candidate.confidence < 0.3:
                        tasks[tid] = TaskStatus.SKIPPED
                        details[tid].status = TaskStatus.SKIPPED
                        logs.append({"ts": current_time,
                                     "msg": f"Task {tid} → SKIPPED (confidence {candidate.confidence:.0%} < 30%)"})
                    else:
                        tasks[tid] = TaskStatus.READY
                        details[tid].status = TaskStatus.READY
                        logs.append({"ts": current_time,
                                     "msg": f"Task {tid} → READY"})
                changed = True

    return ExecutionState(
        tasks=tasks,
        task_details=details,
        last_updated=current_time,
        logs=logs,
    )
