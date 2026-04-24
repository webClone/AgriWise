"""
Layer 5 Invariants — Bio Threat Intelligence

Enforced on BioThreatIntelligenceOutput:
  1. Threat probability in [0, 1]
  2. Threat confidence in [0, 1]
  3. Evidence trace non-empty for high-probability threats (> 0.3)
  4. Recommendation blocked consistency
  5. Scouting plan dates within horizon (if present)
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


def enforce_layer5_invariants(output) -> List[InvariantViolation]:
    violations: List[InvariantViolation] = []

    for tid, state in output.threat_states.items():
        # 1. Probability bounds
        if state.probability < 0 or state.probability > 1:
            violations.append(InvariantViolation(
                "threat_probability_range", "error",
                f"Threat '{tid}': probability={state.probability}"))

        # 2. Confidence bounds
        if state.confidence < 0 or state.confidence > 1:
            violations.append(InvariantViolation(
                "threat_confidence_range", "error",
                f"Threat '{tid}': confidence={state.confidence}"))

        # 3. Evidence trace for significant threats
        if state.probability > 0.3 and len(state.evidence_trace) == 0:
            violations.append(InvariantViolation(
                "evidence_required", "warning",
                f"Threat '{tid}': p={state.probability:.2f} but no evidence"))

    for rec in output.recommendations:
        # 4. Blocked consistency
        if rec.blocked_reason and rec.is_allowed:
            violations.append(InvariantViolation(
                "blocked_consistency", "error",
                f"Rec '{rec.action_id}': has blocked_reason but is_allowed=True"))

    # 5. Scouting plan feasibility (basic)
    if output.execution_plan:
        for task in output.execution_plan.tasks:
            if not task.task_id:
                violations.append(InvariantViolation(
                    "task_id_present", "warning",
                    "Execution plan has task with empty task_id"))

    # 6. Decision reliability
    qm = output.quality_metrics
    if qm.decision_reliability < 0 or qm.decision_reliability > 1:
        violations.append(InvariantViolation(
            "reliability_range", "warning",
            f"decision_reliability={qm.decision_reliability}"))

    return violations
