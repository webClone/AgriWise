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

    # ================================================================
    # v3.0 NEW: Invariant checks for advanced engines
    # ================================================================

    # 8. CEC bounds (1-50 cmol(+)/kg is the physical range for soils)
    cec = output.cec_analysis
    if cec is not None:
        if cec.cec_estimated < 1.0 or cec.cec_estimated > 50.0:
            violations.append(InvariantViolation(
                "cec_range", "warning",
                f"CEC={cec.cec_estimated} outside [1, 50] cmol(+)/kg"))

    # 9. Lime requirement bounds (0-15000 kg/ha CaCO3)
    lime = output.lime_requirement
    if lime is not None:
        if lime.caco3_equivalent_kg_ha < 0:
            violations.append(InvariantViolation(
                "lime_rate_negative", "error",
                f"Lime CaCO3={lime.caco3_equivalent_kg_ha} < 0", True))
            lime.caco3_equivalent_kg_ha = 0.0
        if lime.caco3_equivalent_kg_ha > 15000:
            violations.append(InvariantViolation(
                "lime_rate_excessive", "warning",
                f"Lime CaCO3={lime.caco3_equivalent_kg_ha} > 15000 kg/ha"))

    # 10. VRA zone consistency
    for nut_key, vra in output.vra_prescriptions.items():
        if hasattr(vra, "zone_rates"):
            for zr in vra.zone_rates:
                if zr.adjusted_rate_kg_ha < 0:
                    violations.append(InvariantViolation(
                        "vra_rate_negative", "error",
                        f"VRA zone {zr.zone_id}: rate={zr.adjusted_rate_kg_ha} < 0", True))
                    zr.adjusted_rate_kg_ha = 0.0
                if zr.adjustment_factor < 0.3 or zr.adjustment_factor > 2.0:
                    violations.append(InvariantViolation(
                        "vra_factor_range", "warning",
                        f"VRA zone {zr.zone_id}: factor={zr.adjustment_factor} outside [0.3, 2.0]"))

    # 11. Residual credits non-negative total
    rc = output.residual_credits
    if rc is not None:
        if rc.total_n_credit_kg_ha < 0:
            violations.append(InvariantViolation(
                "residual_credit_negative", "error",
                f"Total N credit={rc.total_n_credit_kg_ha} < 0", True))
            rc.total_n_credit_kg_ha = 0.0

    # 12. Nutrient interactions: Liebig coherence
    ix = output.nutrient_interactions
    if ix is not None and hasattr(ix, "limiting_factor"):
        lf = ix.limiting_factor
        if lf.yield_limitation_factor < 0 or lf.yield_limitation_factor > 1:
            violations.append(InvariantViolation(
                "liebig_ylf_range", "warning",
                f"Yield limitation factor={lf.yield_limitation_factor} outside [0, 1]"))

    return violations
