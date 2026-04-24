"""
Layer 3 Invariants — Decision Intelligence

Enforced on DecisionOutput:
  1. Diagnosis probability in [0, 1]
  2. Diagnosis severity in [0, 1]
  3. Diagnosis confidence in [0, 1]
  4. Evidence trace non-empty for non-trivial diagnoses (probability > 0.1)
  5. Recommendation priority scores >= 0
  6. Blocked actions -> is_allowed = False
  7. Decision reliability in [0, 1]
"""

from typing import List
from dataclasses import dataclass


@dataclass
class InvariantViolation:
    check_name: str
    severity: str
    description: str
    auto_fixed: bool = False


def enforce_layer3_invariants(output) -> List[InvariantViolation]:
    violations: List[InvariantViolation] = []

    for d in output.diagnoses:
        pid = d.problem_id

        # 1. Probability bounds
        if d.probability < 0 or d.probability > 1:
            violations.append(InvariantViolation(
                "probability_range", "error",
                f"Diagnosis '{pid}': probability={d.probability} not in [0,1]"))

        # 2. Severity bounds
        if d.severity < 0 or d.severity > 1:
            violations.append(InvariantViolation(
                "severity_range", "error",
                f"Diagnosis '{pid}': severity={d.severity} not in [0,1]"))

        # 3. Confidence bounds
        if d.confidence < 0 or d.confidence > 1:
            violations.append(InvariantViolation(
                "confidence_range", "error",
                f"Diagnosis '{pid}': confidence={d.confidence} not in [0,1]"))

        # 4. Evidence trace for non-trivial diagnoses
        if d.probability > 0.1 and len(d.evidence_trace) == 0:
            violations.append(InvariantViolation(
                "evidence_required", "warning",
                f"Diagnosis '{pid}': p={d.probability:.2f} but no evidence trace"))

    for r in output.recommendations:
        # 5. Priority score
        if r.priority_score < 0:
            violations.append(InvariantViolation(
                "priority_non_negative", "warning",
                f"Recommendation '{r.action_id}': priority={r.priority_score} < 0"))

        # 6. Blocked consistency
        if r.blocked_reason and r.is_allowed:
            violations.append(InvariantViolation(
                "blocked_consistency", "error",
                f"Recommendation '{r.action_id}': has blocked_reason but is_allowed=True"))

    # 7. Decision reliability
    qm = output.quality_metrics
    if qm.decision_reliability < 0 or qm.decision_reliability > 1:
        violations.append(InvariantViolation(
            "reliability_range", "warning",
            f"decision_reliability={qm.decision_reliability} not in [0,1]"))

    return violations
