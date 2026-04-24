"""
Layer 7 Invariants — Pre-Season Planning

Enforced on Layer7Output:
  1. Yield distribution: all values non-negative, p10 <= p50 <= p90
  2. Economics: profit values finite, break_even_yield >= 0
  3. Suitability probability_ok in [0, 1]
  4. Suitability confidence in [0, 1]
  5. Overall rank score >= 0
  6. Chosen plan is_allowed consistency
"""

from typing import List
from dataclasses import dataclass
import math


@dataclass
class InvariantViolation:
    check_name: str
    severity: str
    description: str
    auto_fixed: bool = False


def enforce_layer7_invariants(output) -> List[InvariantViolation]:
    violations: List[InvariantViolation] = []

    for opt in output.options:
        crop = opt.crop

        # 1. Yield distribution
        yd = opt.yield_dist
        if yd.mean < 0:
            violations.append(InvariantViolation(
                "yield_non_negative", "warning",
                f"'{crop}': yield mean={yd.mean} < 0"))
        if yd.p10 > yd.p50 or yd.p50 > yd.p90:
            violations.append(InvariantViolation(
                "yield_percentile_order", "error",
                f"'{crop}': p10={yd.p10} p50={yd.p50} p90={yd.p90} not ordered"))

        # 2. Economics
        ec = opt.econ
        if math.isinf(ec.expected_profit) or math.isnan(ec.expected_profit):
            violations.append(InvariantViolation(
                "profit_finite", "error",
                f"'{crop}': expected_profit not finite"))
        if ec.break_even_yield < 0:
            violations.append(InvariantViolation(
                "break_even_non_negative", "warning",
                f"'{crop}': break_even_yield={ec.break_even_yield} < 0"))

        # 3-4. Suitability states
        for state_name in ("window", "soil", "water", "biotic"):
            state = getattr(opt, state_name, None)
            if state:
                if state.probability_ok < 0 or state.probability_ok > 1:
                    violations.append(InvariantViolation(
                        "suitability_prob_range", "error",
                        f"'{crop}'.{state_name}: probability_ok={state.probability_ok}"))
                if state.confidence < 0 or state.confidence > 1:
                    violations.append(InvariantViolation(
                        "suitability_conf_range", "error",
                        f"'{crop}'.{state_name}: confidence={state.confidence}"))

        # 5. Rank score
        if opt.overall_rank_score < 0:
            violations.append(InvariantViolation(
                "rank_non_negative", "warning",
                f"'{crop}': overall_rank_score={opt.overall_rank_score} < 0"))

    # 6. Chosen plan consistency
    cp = output.chosen_plan
    if cp.blocked_reason and cp.is_allowed:
        violations.append(InvariantViolation(
            "chosen_plan_consistency", "error",
            f"Chosen plan '{cp.crop}' has blocked_reason but is_allowed=True"))

    return violations
