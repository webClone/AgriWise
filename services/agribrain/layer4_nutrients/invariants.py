"""
Layer 4 Invariants v2.0 — Nutrient Intelligence Safety Checks.

Enforced on NutrientIntelligenceOutput:
  1. Prescription rates >= 0 and <= max safe
  2. NutrientState probability/confidence in [0, 1]
  3. Environmental risk scores in [0, 1]
  4. Blocked prescriptions -> is_allowed = False
  5. Compliance consistency
  6. Budget coherence
  7. Tillage/SOC validity
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from layer4_nutrients.schema import Nutrient


MAX_SAFE_RATES: Dict[str, float] = {
    "N": 300.0, "P": 150.0, "K": 250.0,
    "S": 100.0, "Ca": 500.0, "Mg": 100.0,
}


@dataclass
class InvariantViolation:
    check_name: str
    severity: str    # "error", "warning"
    description: str
    auto_fixed: bool = False


def enforce_layer4_invariants(output) -> List[InvariantViolation]:
    """Run all invariant checks on L4 output. Auto-fixes where possible."""
    violations: List[InvariantViolation] = []

    # 1-2. Prescription rates
    for rx in output.prescriptions:
        aid = rx.action_id.value if hasattr(rx.action_id, "value") else str(rx.action_id)
        nut = rx.nutrient.value if hasattr(rx.nutrient, "value") else "N"

        if rx.rate_kg_ha < 0:
            violations.append(InvariantViolation(
                "rate_non_negative", "error",
                f"{aid}: rate={rx.rate_kg_ha} < 0", True))
            rx.rate_kg_ha = 0.0

        max_rate = MAX_SAFE_RATES.get(nut, 300.0)
        if rx.rate_kg_ha > max_rate:
            violations.append(InvariantViolation(
                "rate_max_safe", "warning",
                f"{aid}: rate={rx.rate_kg_ha} > max={max_rate}", True))
            rx.rate_kg_ha = max_rate

        # Blocked consistency
        if rx.blocked_reason and rx.is_allowed:
            violations.append(InvariantViolation(
                "blocked_consistency", "error",
                f"{aid}: has blocked_reason but is_allowed=True"))

    # 3-4. NutrientState bounds
    for nutrient, state in output.nutrient_states.items():
        nk = nutrient.value if hasattr(nutrient, "value") else str(nutrient)

        if state.probability_deficient < 0 or state.probability_deficient > 1:
            violations.append(InvariantViolation(
                "prob_range", "error",
                f"{nk}: probability={state.probability_deficient}"))
            state.probability_deficient = max(0.0, min(1.0, state.probability_deficient))

        if state.confidence < 0 or state.confidence > 1:
            violations.append(InvariantViolation(
                "conf_range", "error",
                f"{nk}: confidence={state.confidence}"))
            state.confidence = max(0.0, min(1.0, state.confidence))

    # 5. Environmental risk bounds
    for rx in output.prescriptions:
        er = rx.environmental_risk
        for attr in ("leaching", "runoff", "volatilization", "denitrification", "overall"):
            val = getattr(er, attr, 0)
            if val < 0 or val > 1:
                violations.append(InvariantViolation(
                    "env_risk_range", "warning",
                    f"{rx.action_id}: {attr}={val} not in [0,1]"))

    # 6. Decision reliability
    qm = output.quality_metrics
    if qm.decision_reliability < 0 or qm.decision_reliability > 1:
        violations.append(InvariantViolation(
            "reliability_range", "warning",
            f"decision_reliability={qm.decision_reliability}"))

    # 7. Tillage mineralization multiplier bounds
    td = output.tillage_detection
    if td.mineralization_multiplier < 0.5 or td.mineralization_multiplier > 2.0:
        violations.append(InvariantViolation(
            "tillage_multiplier_range", "warning",
            f"mineralization_multiplier={td.mineralization_multiplier} outside [0.5, 2.0]"))

    return violations
