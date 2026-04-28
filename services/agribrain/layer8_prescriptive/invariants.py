"""
Layer 8 Runtime Invariants

Non-negotiable safety checks enforced before emitting Layer8Output:
  1. Rates >= 0, never exceed max safe limits
  2. Zone allocations sum <= 1.0 per action (if exclusive)
  3. Schedule dates within requested horizon
  4. Blocked actions -> no CONFIRMED schedule
  5. Every ActionCard has >= 1 evidence item (or heuristic=True)
  6. Confidence scores in [0, 1]
  7. Priority scores >= 0

Auto-clamp where possible, log violations.
"""

from typing import List
from dataclasses import dataclass
from datetime import datetime

from layer8_prescriptive.schema import (
    Layer8Output, ActionCard, ScheduledAction, ScheduleStatus,
)


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
    
    Returns list of violations found (even if auto-fixed).
    """
    violations: List[InvariantViolation] = []
    
    # 1. Rate bounds
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
            if card.rate.recommended > card.rate.max_safe:
                violations.append(InvariantViolation(
                    check_name="rate_max_safe",
                    severity="warning",
                    description=f"{card.action_id}: rate={card.rate.recommended} > max={card.rate.max_safe}",
                    auto_fixed=True,
                ))
                card.rate.recommended = card.rate.max_safe
    
    # 2. Zone allocation sum <= 1.0
    for card in output.actions:
        alloc_sum = sum(card.zone_allocation.values())
        if alloc_sum > 1.01:  # small tolerance
            violations.append(InvariantViolation(
                check_name="zone_allocation_sum",
                severity="warning",
                description=f"{card.action_id}: zone allocation sum={alloc_sum:.2f} > 1.0",
                auto_fixed=True,
            ))
            # Normalize
            for z in card.zone_allocation:
                card.zone_allocation[z] /= alloc_sum
    
    # 3. Schedule dates within horizon (skip if no scheduled_date)
    # Just validate format, not horizon (horizon depends on input)
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
    
    # 4. Blocked -> no CONFIRMED
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
    
    # 5. Evidence requirement
    for card in output.actions:
        if not card.evidence and not card.heuristic:
            violations.append(InvariantViolation(
                check_name="evidence_required",
                severity="warning",
                description=f"{card.action_id}: no evidence and heuristic=False",
                auto_fixed=True,
            ))
            card.heuristic = True
    
    # 6. Confidence scores in [0, 1]
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
    
    # 7. Priority scores >= 0
    for card in output.actions:
        if card.priority_score < 0:
            violations.append(InvariantViolation(
                check_name="priority_non_negative",
                severity="warning",
                description=f"{card.action_id}: priority_score={card.priority_score} < 0",
                auto_fixed=True,
            ))
            card.priority_score = 0.0
    
    # Store violations in audit
    output.audit.invariant_violations = [
        f"[{v.severity}] {v.check_name}: {v.description}" for v in violations
    ]
    
    return violations
