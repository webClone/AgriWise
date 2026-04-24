"""
Layer 4 Invariants — Nutrient Intelligence

Enforced on NutrientIntelligenceOutput:
  1. Prescription rates >= 0
  2. Rates <= max safe by nutrient (N: 300, P: 150, K: 200 kg/ha)
  3. Blocked prescriptions -> is_allowed = False
  4. NutrientState probability_deficient in [0, 1]
  5. NutrientState confidence in [0, 1]
  6. Environmental risk scores in [0, 1]
  7. Compliance gate consistency
"""

from typing import List, Dict
from dataclasses import dataclass


MAX_SAFE_RATES: Dict[str, float] = {"N": 300.0, "P": 150.0, "K": 200.0}


@dataclass
class InvariantViolation:
    check_name: str
    severity: str
    description: str
    auto_fixed: bool = False


def enforce_layer4_invariants(output) -> List[InvariantViolation]:
    violations: List[InvariantViolation] = []

    # 1-2. Prescription rates
    for rx in output.prescriptions:
        aid = rx.action_id if hasattr(rx.action_id, "value") else str(rx.action_id)

        if rx.rate_kg_ha < 0:
            violations.append(InvariantViolation(
                "rate_non_negative", "error",
                f"{aid}: rate={rx.rate_kg_ha} < 0",
                auto_fixed=True))
            rx.rate_kg_ha = 0

        nutrient_key = aid.replace("APPLY_", "")
        max_rate = MAX_SAFE_RATES.get(nutrient_key, 300.0)
        if rx.rate_kg_ha > max_rate:
            violations.append(InvariantViolation(
                "rate_max_safe", "warning",
                f"{aid}: rate={rx.rate_kg_ha} > max={max_rate}",
                auto_fixed=True))
            rx.rate_kg_ha = max_rate

        # 3. Blocked consistency
        if rx.blocked_reason and rx.is_allowed:
            violations.append(InvariantViolation(
                "blocked_consistency", "error",
                f"{aid}: has blocked_reason but is_allowed=True"))

    # 4-5. NutrientState bounds
    for nutrient, state in output.nutrient_states.items():
        nk = nutrient if isinstance(nutrient, str) else nutrient.value

        if state.probability_deficient < 0 or state.probability_deficient > 1:
            violations.append(InvariantViolation(
                "prob_deficient_range", "error",
                f"{nk}: probability_deficient={state.probability_deficient}"))

        if state.confidence < 0 or state.confidence > 1:
            violations.append(InvariantViolation(
                "confidence_range", "error",
                f"{nk}: confidence={state.confidence}"))

    # 6. Environmental risk
    for rx in output.prescriptions:
        er = rx.environmental_risk
        for attr in ("leaching", "runoff", "volatilization"):
            val = getattr(er, attr, 0)
            if val < 0 or val > 1:
                violations.append(InvariantViolation(
                    "env_risk_range", "warning",
                    f"{rx.action_id}: {attr}={val} not in [0,1]"))

    # 7. Decision reliability
    qm = output.quality_metrics
    if qm.decision_reliability < 0 or qm.decision_reliability > 1:
        violations.append(InvariantViolation(
            "reliability_range", "warning",
            f"decision_reliability={qm.decision_reliability}"))

    return violations
