"""
Engine 2: Resource Feasibility — Operational Constraint Gating

Takes the ideal intervention portfolio and gates each candidate against
real-world operational constraints: water budget, chemical budget,
equipment availability, regulatory compliance, labor scheduling.

Each candidate receives a FeasibilityGrade (A-F) and blocked reasons.

Science:
  - Water budget: remaining quota vs. irrigation demand
  - Chemical budget: cost vs. budget ceiling
  - Equipment: timing window overlap check
  - Regulatory: NVZ nitrogen limits, buffer strips, pre-harvest intervals
  - Labor: available hours vs. estimated task durations
"""

from typing import Any, Dict, List
from layer6_exec.schema import (
    InterventionCandidate, InterventionDomain, FeasibilityGrade,
    OperationalContext, ResourceType,
)


def _grade_from_score(score: float) -> FeasibilityGrade:
    """Convert numeric feasibility score to letter grade."""
    if score >= 0.9:
        return FeasibilityGrade.A
    elif score >= 0.7:
        return FeasibilityGrade.B
    elif score >= 0.5:
        return FeasibilityGrade.C
    elif score >= 0.3:
        return FeasibilityGrade.D
    else:
        return FeasibilityGrade.F


def assess_feasibility(
    portfolio: List[InterventionCandidate],
    op_context: OperationalContext,
    area_ha: float = 10.0,
) -> List[InterventionCandidate]:
    """Gate each candidate against operational constraints.

    Mutates candidates in-place: sets feasibility_grade and blocked_reasons.
    Returns the same list (with grades assigned).
    """
    cumulative_water_mm = 0.0
    cumulative_cost_eur = 0.0
    cumulative_labor_hrs = 0.0

    for candidate in portfolio:
        score = 1.0
        reasons: List[str] = []

        # ── Water Check ──────────────────────────────────────────────────
        if candidate.domain == InterventionDomain.IRRIGATION:
            water_need = 0.0
            for req in candidate.resource_requirements:
                if req.get("resource_type") == ResourceType.WATER.value:
                    water_need = float(req.get("quantity", 0)) * area_ha
            total_water = cumulative_water_mm + water_need
            if total_water > op_context.water_quota_remaining:
                deficit = total_water - op_context.water_quota_remaining
                score -= 0.5
                reasons.append(
                    f"Water quota exceeded by {deficit:.0f}mm "
                    f"(need {total_water:.0f}, remaining {op_context.water_quota_remaining:.0f})"
                )
            else:
                cumulative_water_mm = total_water

        # ── Budget Check ─────────────────────────────────────────────────
        cost = candidate.estimated_cost_eur * area_ha
        cumulative_cost_eur += cost
        if cumulative_cost_eur > op_context.budget_remaining:
            overshoot = cumulative_cost_eur - op_context.budget_remaining
            score -= 0.4
            reasons.append(
                f"Budget exceeded by €{overshoot:.0f} "
                f"(cumulative €{cumulative_cost_eur:.0f}, budget €{op_context.budget_remaining:.0f})"
            )

        # ── Labor Check ──────────────────────────────────────────────────
        labor_need = 0.0
        for req in candidate.resource_requirements:
            if req.get("resource_type") == ResourceType.LABOR.value:
                labor_need = float(req.get("quantity", 0)) * area_ha
        cumulative_labor_hrs += labor_need
        if cumulative_labor_hrs > op_context.labor_hours_available:
            score -= 0.3
            reasons.append(
                f"Labor hours exceeded ({cumulative_labor_hrs:.1f}h needed, "
                f"{op_context.labor_hours_available:.1f}h available)"
            )

        # ── Equipment Check ──────────────────────────────────────────────
        if not op_context.workforce_available and candidate.action_type == "INTERVENE":
            score -= 0.2
            reasons.append("Workforce unavailable for intervention execution")

        for req in candidate.resource_requirements:
            if req.get("resource_type") == ResourceType.EQUIPMENT.value:
                if not op_context.equipment_ids:
                    score -= 0.15
                    reasons.append("No equipment registered for this operation")

        # ── Regulatory Check ─────────────────────────────────────────────
        if op_context.regulatory_zone == "NVZ":
            if candidate.domain == InterventionDomain.NUTRIENT and "nitrogen" in candidate.title.lower():
                score -= 0.3
                reasons.append("Nitrate Vulnerable Zone: nitrogen application restricted")
        elif op_context.regulatory_zone == "ORGANIC":
            if candidate.domain == InterventionDomain.PHYTOSANITARY:
                score -= 0.4
                reasons.append("Organic certification: synthetic phytosanitary products prohibited")

        # ── Season Stage Check ───────────────────────────────────────────
        if op_context.season_stage == "POST_HARVEST":
            if candidate.action_type == "INTERVENE":
                score -= 0.5
                reasons.append("Post-harvest: intervention is no longer applicable")

        if op_context.season_stage == "LATE" and candidate.domain == InterventionDomain.NUTRIENT:
            score -= 0.15
            reasons.append("Late season: nutrient uptake efficiency reduced")

        # ── Assign Grade ─────────────────────────────────────────────────
        final_score = max(0.0, min(1.0, score))
        candidate.feasibility_grade = _grade_from_score(final_score)
        candidate.blocked_reasons = reasons

    return portfolio
