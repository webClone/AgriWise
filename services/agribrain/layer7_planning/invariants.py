"""
Layer 7 Invariants — Pre-Season Planning (v7.1)

Production-grade invariant suite enforced on Layer7Output.
13 checks covering agronomic realism, economics, and governance.

  1. yield_non_negative         — All yield values >= 0
  2. yield_percentile_order     — p10 <= p50 <= p90
  3. profit_finite              — No NaN/Inf in economics
  4. break_even_non_negative    — Break-even yield >= 0
  5. suitability_prob_range     — probability_ok ∈ [0, 1]
  6. suitability_conf_range     — confidence ∈ [0, 1]
  7. chosen_plan_consistency    — blocked_reason XOR is_allowed
  8. content_hash_valid         — Non-empty hash >= 16 chars
  9. suitability_pct_range      — suitability_percentage ∈ [0, 100]
 10. evidence_trace_non_empty   — Each SuitabilityState has >= 1 logit
 11. economics_profit_order     — profit_p10 <= profit_p50 <= profit_p90
 12. option_ranking_consistency — Options sorted descending by rank_score
 13. agronomic_yield_realism    — yield mean <= 3× base profile yield
"""

from typing import List
from dataclasses import dataclass
import math


@dataclass
class InvariantViolation:
    check_name: str
    severity: str       # "error", "warning", "info"
    description: str
    auto_fixed: bool = False


def enforce_layer7_invariants(output, crop_profiles=None) -> List[InvariantViolation]:
    """Enforce all 13 production invariants on a Layer7Output instance.

    Args:
        output: Layer7Output instance
        crop_profiles: Optional dict of crop_id -> CropProfile for agronomic checks

    Returns:
        List of violations found.  Empty list == clean.
    """
    violations: List[InvariantViolation] = []

    for opt in output.options:
        crop = opt.crop

        # 1. Yield distribution — non-negative
        yd = opt.yield_dist
        if yd.mean < 0:
            violations.append(InvariantViolation(
                "yield_non_negative", "warning",
                f"'{crop}': yield mean={yd.mean} < 0"))

        # 2. Yield percentile ordering
        if yd.p10 > yd.p50 or yd.p50 > yd.p90:
            violations.append(InvariantViolation(
                "yield_percentile_order", "error",
                f"'{crop}': p10={yd.p10} p50={yd.p50} p90={yd.p90} not ordered"))

        # 3. Economics — finite profit
        ec = opt.econ
        if math.isinf(ec.expected_profit) or math.isnan(ec.expected_profit):
            violations.append(InvariantViolation(
                "profit_finite", "error",
                f"'{crop}': expected_profit not finite"))

        # 4. Break-even yield non-negative
        if ec.break_even_yield < 0:
            violations.append(InvariantViolation(
                "break_even_non_negative", "warning",
                f"'{crop}': break_even_yield={ec.break_even_yield} < 0"))

        # 5-6. Suitability states — probability and confidence ranges
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

                # 10. Evidence trace non-empty
                if not state.evidence_trace:
                    violations.append(InvariantViolation(
                        "evidence_trace_non_empty", "warning",
                        f"'{crop}'.{state_name}: no evidence logits attached"))

        # 9. Suitability percentage range
        if opt.suitability_percentage < 0 or opt.suitability_percentage > 100:
            violations.append(InvariantViolation(
                "suitability_pct_range", "error",
                f"'{crop}': suitability_percentage={opt.suitability_percentage} outside [0,100]"))

        # 11. Economics profit ordering
        if ec.profit_p10 > ec.profit_p50 or ec.profit_p50 > ec.profit_p90:
            violations.append(InvariantViolation(
                "economics_profit_order", "warning",
                f"'{crop}': profit_p10={ec.profit_p10} p50={ec.profit_p50} p90={ec.profit_p90} not ordered"))

        # 13. Agronomic yield realism (guard against runaway calculations)
        if crop_profiles:
            # Try to find the profile by matching display name or id
            matched_profile = None
            for pid, prof in crop_profiles.items():
                if prof.display_name == crop or pid == crop.lower():
                    matched_profile = prof
                    break
            if matched_profile and matched_profile.varieties:
                max_base = max(v.base_yield_t_ha for v in matched_profile.varieties)
                if max_base > 0 and yd.mean > max_base * 3.0:
                    violations.append(InvariantViolation(
                        "agronomic_yield_realism", "warning",
                        f"'{crop}': yield mean={yd.mean:.1f} exceeds 3× base ({max_base:.1f})"))

    # 7. Chosen plan consistency
    cp = output.chosen_plan
    if cp:
        if cp.blocked_reason and cp.is_allowed:
            violations.append(InvariantViolation(
                "chosen_plan_consistency", "error",
                f"Chosen plan '{cp.crop}' has blocked_reason but is_allowed=True"))

    # 8. Content hash valid
    try:
        h = output.content_hash()
        if not h or len(h) < 16:
            violations.append(InvariantViolation(
                "content_hash_valid", "error",
                f"content_hash() returned invalid hash: '{h}'"))
    except Exception as e:
        violations.append(InvariantViolation(
            "content_hash_valid", "error",
            f"content_hash() raised: {e}"))

    # 12. Option ranking consistency (should be sorted descending by rank_score)
    if len(output.options) > 1:
        scores = [o.overall_rank_score for o in output.options]
        for i in range(len(scores) - 1):
            if scores[i] < scores[i + 1]:
                violations.append(InvariantViolation(
                    "option_ranking_consistency", "info",
                    f"Options not sorted: [{i}]={scores[i]:.2f} < [{i+1}]={scores[i+1]:.2f}"))
                break  # One violation is enough

    return violations
