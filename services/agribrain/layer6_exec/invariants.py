"""
Layer 6 Invariants — Execution & Governance

Enforced on Layer6Output:
  1. DAG integrity: no duplicate task IDs in state
  2. Outcome metrics bounded: confidence in [0, 1]
  3. Evidence ID format (non-empty)
  4. Calibration proposals: current_value != proposed_value (no no-ops)
  5. Task completion rate in [0, 1]
  6. Decision reliability in [0, 1]
"""

from typing import List
from dataclasses import dataclass


@dataclass
class InvariantViolation:
    check_name: str
    severity: str
    description: str
    auto_fixed: bool = False


def enforce_layer6_invariants(output) -> List[InvariantViolation]:
    violations: List[InvariantViolation] = []

    # 1. DAG integrity — no duplicate task IDs
    task_ids = list(output.updated_state.tasks.keys())
    if len(task_ids) != len(set(task_ids)):
        violations.append(InvariantViolation(
            "dag_no_duplicates", "error",
            f"Duplicate task IDs in state: {len(task_ids)} keys, {len(set(task_ids))} unique"))

    # 2. Outcome metric confidence
    for om in output.outcome_report:
        if om.confidence < 0 or om.confidence > 1:
            violations.append(InvariantViolation(
                "outcome_confidence_range", "warning",
                f"Outcome '{om.metric_id}': confidence={om.confidence}"))

    # 3. Evidence IDs
    for ev in output.evidence_registry:
        if not ev.evidence_id:
            violations.append(InvariantViolation(
                "evidence_id_present", "error",
                "Evidence record has empty evidence_id"))

    # 4. Calibration no-ops
    for cal in output.calibration_proposals:
        if cal.current_value == cal.proposed_value:
            violations.append(InvariantViolation(
                "calibration_no_op", "warning",
                f"Calibration for '{cal.parameter_key}': current==proposed ({cal.current_value})"))

    # 5. Task completion rate
    qm = output.quality_metrics
    if qm.task_completion_rate < 0 or qm.task_completion_rate > 1:
        violations.append(InvariantViolation(
            "completion_rate_range", "warning",
            f"task_completion_rate={qm.task_completion_rate}"))

    # 6. Decision reliability
    if qm.decision_reliability < 0 or qm.decision_reliability > 1:
        violations.append(InvariantViolation(
            "reliability_range", "warning",
            f"decision_reliability={qm.decision_reliability}"))

    return violations
