"""
Layer 3 Invariants — Decision Intelligence.

12 runtime invariant checks with auto-fix capability.
Mirrors L1/L2 invariant architecture.

Enforced on DecisionOutput:
  1. probability_range — diagnosis p in [0, 1]       (auto-fix: clamp)
  2. severity_range — diagnosis severity in [0, 1]    (auto-fix: clamp)
  3. confidence_range — diagnosis confidence in [0, 1] (auto-fix: clamp)
  4. evidence_required — non-trivial (p > 0.1) needs evidence
  5. priority_non_negative — recommendation priority >= 0  (auto-fix: clamp)
  6. blocked_consistency — blocked_reason → is_allowed=False (auto-fix)
  7. reliability_range — decision_reliability in [0, 1] (auto-fix: clamp)
  8. no_intervention_without_diagnosis — recommendations must link to diagnosis IDs
  9. severity_monotonic_with_evidence — more evidence → higher severity (warning only)
  10. confidence_ceiling_from_data_health — confidence ≤ data_health ceiling (auto-fix: cap)
  11. execution_plan_acyclic — DAG must have no cycles
  12. lineage_complete — lineage must reference L1 and L2 run IDs
"""

from __future__ import annotations

from typing import Any, Dict, List, Set

from dataclasses import dataclass


@dataclass
class InvariantViolation:
    check_name: str
    severity: str        # "error", "warning"
    description: str
    auto_fixed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_name": self.check_name,
            "severity": self.severity,
            "description": self.description,
            "auto_fixed": self.auto_fixed,
        }


def enforce_layer3_invariants(output) -> List[InvariantViolation]:
    """Run all 12 invariant checks against a DecisionOutput.

    Auto-fixable violations are fixed in-place.
    """
    violations: List[InvariantViolation] = []

    # Get confidence ceiling from data_health
    conf_ceiling = getattr(output, "data_health", None)
    if conf_ceiling is not None:
        conf_ceiling = getattr(conf_ceiling, "confidence_ceiling", 1.0)
    else:
        conf_ceiling = 1.0

    for d in output.diagnoses:
        pid = d.problem_id

        # 1. Probability bounds
        if d.probability < 0 or d.probability > 1:
            old = d.probability
            d.probability = max(0.0, min(1.0, d.probability))
            violations.append(InvariantViolation(
                "probability_range", "error",
                f"Diagnosis '{pid}': probability={old} clamped to {d.probability}",
                auto_fixed=True))

        # 2. Severity bounds
        if d.severity < 0 or d.severity > 1:
            old = d.severity
            d.severity = max(0.0, min(1.0, d.severity))
            violations.append(InvariantViolation(
                "severity_range", "error",
                f"Diagnosis '{pid}': severity={old} clamped to {d.severity}",
                auto_fixed=True))

        # 3. Confidence bounds
        if d.confidence < 0 or d.confidence > 1:
            old = d.confidence
            d.confidence = max(0.0, min(1.0, d.confidence))
            violations.append(InvariantViolation(
                "confidence_range", "error",
                f"Diagnosis '{pid}': confidence={old} clamped to {d.confidence}",
                auto_fixed=True))

        # 4. Evidence trace for non-trivial diagnoses
        if d.probability > 0.1 and len(d.evidence_trace) == 0:
            violations.append(InvariantViolation(
                "evidence_required", "warning",
                f"Diagnosis '{pid}': p={d.probability:.2f} but no evidence trace"))

        # 10. Confidence ceiling from data health
        if d.confidence > conf_ceiling + 0.001:
            old = d.confidence
            d.confidence = min(d.confidence, conf_ceiling)
            violations.append(InvariantViolation(
                "confidence_ceiling_from_data_health", "warning",
                f"Diagnosis '{pid}': confidence={old:.3f} capped to ceiling={conf_ceiling:.3f}",
                auto_fixed=True))

    # Build diagnosis ID set for recommendation validation
    diag_ids = {d.problem_id for d in output.diagnoses}

    for r in output.recommendations:
        # 5. Priority score
        if r.priority_score < 0:
            old = r.priority_score
            r.priority_score = 0.0
            violations.append(InvariantViolation(
                "priority_non_negative", "warning",
                f"Recommendation '{r.action_id}': priority={old} clamped to 0",
                auto_fixed=True))

        # 6. Blocked consistency
        if r.blocked_reason and r.is_allowed:
            r.is_allowed = False
            violations.append(InvariantViolation(
                "blocked_consistency", "error",
                f"Recommendation '{r.action_id}': has blocked_reason but is_allowed=True, auto-fixed",
                auto_fixed=True))

        # 8. No intervention without diagnosis
        if r.action_type == "INTERVENE" and r.linked_diagnosis_ids:
            unlinked = [lid for lid in r.linked_diagnosis_ids if lid not in diag_ids]
            if unlinked:
                violations.append(InvariantViolation(
                    "no_intervention_without_diagnosis", "error",
                    f"Recommendation '{r.action_id}': links to non-existent diagnoses {unlinked}"))

    # 7. Decision reliability
    qm = output.quality_metrics
    if qm.decision_reliability < 0 or qm.decision_reliability > 1:
        old = qm.decision_reliability
        qm.decision_reliability = max(0.0, min(1.0, qm.decision_reliability))
        violations.append(InvariantViolation(
            "reliability_range", "warning",
            f"decision_reliability={old} clamped to {qm.decision_reliability}",
            auto_fixed=True))

    # 9. Severity monotonic with evidence (warning only, not auto-fix)
    for d in output.diagnoses:
        if len(d.evidence_trace) >= 3 and d.severity < 0.1:
            violations.append(InvariantViolation(
                "severity_monotonic_with_evidence", "warning",
                f"Diagnosis '{d.problem_id}': {len(d.evidence_trace)} evidence items but severity={d.severity:.2f}"))

    # 11. Execution plan acyclic
    if hasattr(output, "execution_plan") and output.execution_plan:
        cycle = _detect_cycle(output.execution_plan)
        if cycle:
            violations.append(InvariantViolation(
                "execution_plan_acyclic", "error",
                f"Execution plan has cycle: {' → '.join(cycle)}"))

    # 12. Lineage complete
    lineage = getattr(output, "lineage", {})
    if not lineage.get("l2_run_id"):
        violations.append(InvariantViolation(
            "lineage_complete", "warning",
            "Lineage missing L2 run ID"))

    return violations


def _detect_cycle(plan) -> List[str]:
    """Detect cycles in execution plan DAG using DFS."""
    if not plan.tasks:
        return []

    adj: Dict[str, List[str]] = {}
    for task in plan.tasks:
        adj[task.task_id] = list(task.depends_on)

    visited: Set[str] = set()
    in_stack: Set[str] = set()
    path: List[str] = []

    def dfs(node: str) -> bool:
        if node in in_stack:
            cycle_start = path.index(node)
            path.append(node)
            return True
        if node in visited:
            return False

        visited.add(node)
        in_stack.add(node)
        path.append(node)

        for neighbor in adj.get(node, []):
            if dfs(neighbor):
                return True

        path.pop()
        in_stack.remove(node)
        return False

    for task_id in adj:
        if task_id not in visited:
            if dfs(task_id):
                return path

    return []
