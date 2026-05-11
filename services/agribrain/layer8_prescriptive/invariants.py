"""
Layer 8 Runtime Invariants — Production Gate v8.1.0
===================================================

Non-negotiable safety checks enforced before emitting Layer8Output.
13 invariant checks with auto-clamp where possible:

  1.  rate_non_negative        — Rates >= 0
  2.  rate_max_safe             — Rates <= max safe limits
  3.  zone_allocation_sum       — Zone allocations sum <= 1.0 per action
  4.  schedule_date_format      — ISO date format validation
  5.  blocked_not_confirmed     — Blocked actions -> no CONFIRMED schedule
  6.  evidence_required         — Every ActionCard has >= 1 evidence (or heuristic=True)
  7.  score_bounds              — Breakdown scores in [0, 1]
  8.  priority_non_negative     — Priority scores >= 0
  9.  run_id_present            — Output has non-empty run_id
  10. timestamp_present         — Output has non-empty timestamp
  11. schedule_action_alignment — Schedule count == action count
  12. quality_reliability_bound — Decision reliability in [0, 1]
  13. outcome_forecast_sane     — Outcome forecast values are realistic

Auto-clamp where possible, log violations via structured logger.
"""

import logging
from typing import List
from dataclasses import dataclass
from datetime import datetime

from layer8_prescriptive.schema import (
    Layer8Output, ActionCard, ScheduledAction, ScheduleStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class InvariantViolation:
    """Record of a single invariant violation."""
    check_name: str
    severity: str  # "warning", "error"
    description: str
    auto_fixed: bool = False


def enforce_layer8_invariants(output: Layer8Output) -> List[InvariantViolation]:
    """
    Enforce all Layer 8 invariants. Auto-clamp where possible.

    This is a mandatory production gate — called before every emission
    of Layer8Output. Returns list of violations found (even if auto-fixed).
    """
    violations: List[InvariantViolation] = []

    # 1. Rate non-negative
    for card in output.actions:
        if card.rate is not None:
            if card.rate.recommended < 0:
                violations.append(InvariantViolation(
                    check_name="rate_non_negative",
                    severity="error",
                    description=f"{card.action_id}: rate={card.rate.recommended} < 0",
                    auto_fixed=True,
                ))
                card.rate.recommended = 0

    # 2. Rate max safe
    for card in output.actions:
        if card.rate is not None:
            if card.rate.recommended > card.rate.max_safe:
                violations.append(InvariantViolation(
                    check_name="rate_max_safe",
                    severity="warning",
                    description=f"{card.action_id}: rate={card.rate.recommended} > max={card.rate.max_safe}",
                    auto_fixed=True,
                ))
                card.rate.recommended = card.rate.max_safe

    # 3. Zone allocation sum <= 1.0
    for card in output.actions:
        alloc_sum = sum(card.zone_allocation.values())
        if alloc_sum > 1.01:  # small tolerance
            violations.append(InvariantViolation(
                check_name="zone_allocation_sum",
                severity="warning",
                description=f"{card.action_id}: zone allocation sum={alloc_sum:.2f} > 1.0",
                auto_fixed=True,
            ))
            for z in card.zone_allocation:
                card.zone_allocation[z] /= alloc_sum

    # 4. Schedule date format (ISO YYYY-MM-DD)
    for sched in output.schedule:
        if sched.scheduled_date:
            try:
                datetime.strptime(sched.scheduled_date, "%Y-%m-%d")
            except ValueError:
                violations.append(InvariantViolation(
                    check_name="schedule_date_format",
                    severity="error",
                    description=f"{sched.action_id}: invalid date '{sched.scheduled_date}'",
                ))

    # 5. Blocked -> no CONFIRMED
    blocked_ids = {card.action_id for card in output.actions if not card.is_allowed}
    for sched in output.schedule:
        if sched.action_id in blocked_ids and sched.status == ScheduleStatus.CONFIRMED:
            violations.append(InvariantViolation(
                check_name="blocked_not_confirmed",
                severity="error",
                description=f"{sched.action_id}: blocked action has CONFIRMED schedule",
                auto_fixed=True,
            ))
            sched.status = ScheduleStatus.BLOCKED
            sched.blocking_constraints.append("action_blocked_by_policy")

    # 6. Evidence requirement
    for card in output.actions:
        if not card.evidence and not card.heuristic:
            violations.append(InvariantViolation(
                check_name="evidence_required",
                severity="warning",
                description=f"{card.action_id}: no evidence and heuristic=False",
                auto_fixed=True,
            ))
            card.heuristic = True

    # 7. Breakdown score bounds [0, 1]
    for card in output.actions:
        bd = card.priority_breakdown
        for attr_name in ("impact_score", "urgency_score", "risk_score",
                          "cost_score", "confidence_score"):
            val = getattr(bd, attr_name)
            if val < 0:
                setattr(bd, attr_name, 0.0)
                violations.append(InvariantViolation(
                    check_name="score_bounds",
                    severity="warning",
                    description=f"{card.action_id}: {attr_name}={val} < 0",
                    auto_fixed=True,
                ))
            elif val > 1.0:
                setattr(bd, attr_name, 1.0)
                violations.append(InvariantViolation(
                    check_name="score_bounds",
                    severity="warning",
                    description=f"{card.action_id}: {attr_name}={val} > 1.0",
                    auto_fixed=True,
                ))

    # 8. Priority scores >= 0
    for card in output.actions:
        if card.priority_score < 0:
            violations.append(InvariantViolation(
                check_name="priority_non_negative",
                severity="warning",
                description=f"{card.action_id}: priority_score={card.priority_score} < 0",
                auto_fixed=True,
            ))
            card.priority_score = 0.0

    # 9. Run ID present
    if not output.run_id or not output.run_id.startswith("L8-"):
        violations.append(InvariantViolation(
            check_name="run_id_present",
            severity="error",
            description=f"run_id missing or malformed: '{output.run_id}'",
        ))

    # 10. Timestamp present
    if not output.timestamp:
        violations.append(InvariantViolation(
            check_name="timestamp_present",
            severity="error",
            description="timestamp is empty",
        ))

    # 11. Schedule-action alignment
    action_ids = {c.action_id for c in output.actions}
    schedule_ids = {s.action_id for s in output.schedule}
    if action_ids != schedule_ids:
        missing_from_schedule = action_ids - schedule_ids
        orphan_schedules = schedule_ids - action_ids
        desc_parts = []
        if missing_from_schedule:
            desc_parts.append(f"unscheduled actions: {missing_from_schedule}")
        if orphan_schedules:
            desc_parts.append(f"orphan schedules: {orphan_schedules}")
        violations.append(InvariantViolation(
            check_name="schedule_action_alignment",
            severity="warning",
            description="; ".join(desc_parts),
        ))

    # 12. Quality reliability bound [0, 1]
    rel = output.quality.decision_reliability
    if rel < 0.0:
        output.quality.decision_reliability = 0.0
        violations.append(InvariantViolation(
            check_name="quality_reliability_bound",
            severity="warning",
            description=f"decision_reliability={rel} < 0",
            auto_fixed=True,
        ))
    elif rel > 1.0:
        output.quality.decision_reliability = 1.0
        violations.append(InvariantViolation(
            check_name="quality_reliability_bound",
            severity="warning",
            description=f"decision_reliability={rel} > 1.0",
            auto_fixed=True,
        ))

    # 13. Outcome forecast sanity
    of = output.outcome_forecast
    if of.yield_delta_pct < -100:
        violations.append(InvariantViolation(
            check_name="outcome_forecast_sane",
            severity="warning",
            description=f"yield_delta_pct={of.yield_delta_pct} < -100%",
        ))
    if of.risk_reduction_pct < -100 or of.risk_reduction_pct > 100:
        violations.append(InvariantViolation(
            check_name="outcome_forecast_sane",
            severity="warning",
            description=f"risk_reduction_pct={of.risk_reduction_pct} out of bounds",
        ))
    if of.cost_total < 0:
        violations.append(InvariantViolation(
            check_name="outcome_forecast_sane",
            severity="warning",
            description=f"cost_total={of.cost_total} < 0",
            auto_fixed=True,
        ))
        of.cost_total = 0.0

    # Store violations in audit trail
    output.audit.invariant_violations = [
        f"[{v.severity}] {v.check_name}: {v.description}" for v in violations
    ]

    # Log summary
    if violations:
        auto_fixed = sum(1 for v in violations if v.auto_fixed)
        logger.debug("L8 invariants: %d violations (%d auto-fixed)", len(violations), auto_fixed)
    else:
        logger.debug("L8 invariants: clean pass (13/13)")

    return violations
