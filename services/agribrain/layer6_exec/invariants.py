"""
Layer 6 Invariants — Production Enforcement Suite (v7.0)

Enforced on Layer6Output after every run:
  1.  DAG integrity: no duplicate task IDs in state
  2.  Outcome metrics bounded: confidence in [0, 1]
  3.  Evidence ID format: non-empty, starts with "EV-"
  4.  Calibration proposals: no no-ops (current != proposed)
  5.  Task completion rate in [0, 1]
  6.  Decision reliability in [0, 1]
  7.  Intervention portfolio: utility scores non-negative
  8.  Feasibility grade consistency: F-grade cannot have action_type INTERVENE without blocked_reasons
  9.  Conflict log: all conflict_ids unique
  10. Upstream digest: min_upstream_confidence in [0, 1]
  11. Content hash: output must produce non-empty hash
  12. Portfolio ordering: utility scores must be descending
  13. IPM compliance: L5-sourced INTERVENE actions must depend on a VERIFY/scout task
"""

from typing import List
from dataclasses import dataclass

from layer6_exec.schema import Layer6Output, FeasibilityGrade


@dataclass
class InvariantViolation:
    check_name: str
    severity: str       # "error", "warning", "info"
    description: str
    auto_fixed: bool = False


def enforce_layer6_invariants(output: Layer6Output) -> List[InvariantViolation]:
    """Run all invariant checks on L6 output. Returns violations list."""
    violations: List[InvariantViolation] = []

    # 1. DAG integrity — no duplicate task IDs
    task_ids = list(output.updated_state.tasks.keys())
    if len(task_ids) != len(set(task_ids)):
        violations.append(InvariantViolation(
            "dag_no_duplicates", "error",
            f"Duplicate task IDs: {len(task_ids)} keys, {len(set(task_ids))} unique"))

    # 2. Outcome metric confidence in [0, 1]
    for om in output.outcome_report:
        if om.confidence < 0 or om.confidence > 1:
            violations.append(InvariantViolation(
                "outcome_confidence_range", "warning",
                f"Outcome '{om.metric_id}': confidence={om.confidence}"))

    # 3. Evidence IDs non-empty and well-formed
    for ev in output.evidence_registry:
        if not ev.evidence_id:
            violations.append(InvariantViolation(
                "evidence_id_present", "error",
                "Evidence record has empty evidence_id"))
        elif not ev.evidence_id.startswith("EV-"):
            violations.append(InvariantViolation(
                "evidence_id_format", "warning",
                f"Evidence ID '{ev.evidence_id}' doesn't follow EV-{{hash}} format"))

    # 4. Calibration no-ops
    for cal in output.calibration_proposals:
        if cal.current_value == cal.proposed_value:
            violations.append(InvariantViolation(
                "calibration_no_op", "warning",
                f"Calibration '{cal.parameter_key}': current==proposed ({cal.current_value})"))

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

    # 7. Utility scores non-negative
    for c in output.intervention_portfolio:
        if c.utility_score < 0:
            violations.append(InvariantViolation(
                "utility_non_negative", "error",
                f"Intervention '{c.intervention_id}': utility={c.utility_score}"))

    # 8. Feasibility grade consistency
    for c in output.intervention_portfolio:
        if c.feasibility_grade == FeasibilityGrade.F and c.action_type == "INTERVENE":
            if not c.blocked_reasons:
                violations.append(InvariantViolation(
                    "feasibility_blocked_reasons", "warning",
                    f"Intervention '{c.intervention_id}' is F-grade INTERVENE but has no blocked_reasons"))

    # 9. Unique conflict IDs
    conflict_ids = [c.conflict_id for c in output.conflict_log]
    if len(conflict_ids) != len(set(conflict_ids)):
        violations.append(InvariantViolation(
            "conflict_id_unique", "error",
            f"Duplicate conflict IDs: {len(conflict_ids)} total, {len(set(conflict_ids))} unique"))

    # 10. Upstream digest confidence
    if output.upstream_digest:
        conf = output.upstream_digest.min_upstream_confidence
        if conf < 0 or conf > 1:
            violations.append(InvariantViolation(
                "upstream_confidence_range", "warning",
                f"min_upstream_confidence={conf}"))

    # 11. Content hash
    try:
        h = output.content_hash()
        if not h or len(h) < 16:
            violations.append(InvariantViolation(
                "content_hash_valid", "error",
                f"content_hash() produced invalid hash: '{h}'"))
    except Exception as e:
        violations.append(InvariantViolation(
            "content_hash_valid", "error",
            f"content_hash() raised: {e}"))

    # 12. Portfolio ordering (utility descending)
    scores = [c.utility_score for c in output.intervention_portfolio]
    for i in range(1, len(scores)):
        if scores[i] > scores[i - 1] + 0.0001:  # tolerance for float
            violations.append(InvariantViolation(
                "portfolio_ordering", "info",
                f"Portfolio not sorted by utility: [{i-1}]={scores[i-1]:.4f} < [{i}]={scores[i]:.4f}"))
            break

    # 13. IPM compliance: L5-sourced INTERVENE tasks must depend on a VERIFY/scout task
    portfolio_ids = {c.intervention_id for c in output.intervention_portfolio}
    verify_ids = {c.intervention_id for c in output.intervention_portfolio
                  if c.action_type == "VERIFY"}
    for c in output.intervention_portfolio:
        if c.source_layer == "L5" and c.action_type == "INTERVENE":
            deps = set(c.depends_on or [])
            if not deps.intersection(verify_ids) and not deps.intersection(portfolio_ids):
                violations.append(InvariantViolation(
                    "ipm_scout_before_intervene", "error",
                    f"L5 INTERVENE '{c.intervention_id}' has no depends_on to a VERIFY/scout task"))
            elif deps and not deps.intersection(verify_ids):
                # Has deps but none are VERIFY — warning level (could be chained)
                violations.append(InvariantViolation(
                    "ipm_scout_before_intervene", "warning",
                    f"L5 INTERVENE '{c.intervention_id}' depends_on {list(deps)} "
                    f"but none are VERIFY tasks"))

    return violations
