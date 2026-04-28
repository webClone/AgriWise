"""
Layer 8 Pipeline Runner

Orchestrates: rank → schedule → zone allocate → enforce invariants → Layer8Output

Usage:
    from layer8_prescriptive.runner import run_layer8
    output = run_layer8(l8_input, forecast, start_date)
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib

from layer8_prescriptive.schema import (
    Layer8Input, Layer8Output, OutcomeForecast, Tradeoff,
    PrescriptiveQuality, PrescriptiveAudit, PrescriptiveDegradation,
    ConfidenceLevel,
)
from layer8_prescriptive.action_ranker import ActionRankingEngine
from layer8_prescriptive.scheduler import ConstraintScheduler
from layer8_prescriptive.zone_prioritizer import ZonePrioritizer
from layer8_prescriptive.invariants import enforce_layer8_invariants


def run_layer8(l8_input: Layer8Input,
               forecast: Optional[List[Dict[str, Any]]] = None,
               start_date: Optional[datetime] = None) -> Layer8Output:
    """
    Run the full Layer 8 prescriptive pipeline.
    
    Args:
        l8_input: Upstream layer outputs + audit info
        forecast: Weather forecast for scheduling (default: empty)
        start_date: Planning start date (default: today)
    
    Returns:
        Layer8Output with ranked actions, schedule, zone plan, audit
    """
    if forecast is None:
        forecast = []
    if start_date is None:
        start_date = datetime.now()
    
    run_id = f"L8-{hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]}"
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    
    # --- Step 1: Rank actions ---
    ranker = ActionRankingEngine()
    action_cards = ranker.rank_actions(l8_input)
    
    # --- Step 2: Schedule ---
    sched = ConstraintScheduler()
    scheduled = sched.schedule_actions(
        action_cards, forecast, start_date,
        horizon_days=l8_input.horizon_days,
        phenology_stage=l8_input.phenology_stage,
    )
    
    # --- Step 3: Zone allocation ---
    zone_engine = ZonePrioritizer()
    zone_plan = zone_engine.prioritize_zones(
        action_cards,
        zone_reliability=l8_input.source_reliability,
        zone_ids=l8_input.zone_ids if l8_input.zone_ids else ["plot"],
    )
    
    # --- Step 4: Compute outcome forecast ---
    total_impact = sum(c.priority_breakdown.impact_score for c in action_cards
                       if c.is_allowed) / max(1, len(action_cards))
    total_cost = sum(c.rate.recommended * 2 if c.rate else 0
                     for c in action_cards if c.is_allowed)  # rough cost estimate
    
    grade = l8_input.audit_grade.upper()
    conf = ConfidenceLevel.HIGH if grade in ("A", "B") else (
        ConfidenceLevel.MODERATE if grade == "C" else ConfidenceLevel.LOW
    )
    
    outcome = OutcomeForecast(
        yield_delta_pct=round(total_impact * 15, 1),  # rough mapping
        risk_reduction_pct=round(total_impact * 20, 1),
        cost_total=round(total_cost, 2),
        roi_pct=round((total_impact * 15 / max(1, total_cost)) * 100, 1) if total_cost > 0 else 0,
        confidence=conf,
    )
    
    # --- Step 5: Generate tradeoffs (top 2 vs rest) ---
    tradeoffs: List[Tradeoff] = []
    allowed = [c for c in action_cards if c.is_allowed and not c.heuristic]
    if len(allowed) >= 2:
        tradeoffs.append(Tradeoff(
            chosen_action_id=allowed[0].action_id,
            rejected_action_id=allowed[1].action_id,
            reason=f"{allowed[0].action_type.value} ranks higher: "
                   f"impact={allowed[0].priority_breakdown.impact_score:.2f} vs "
                   f"{allowed[1].priority_breakdown.impact_score:.2f}",
            score_delta=round(allowed[0].priority_score - allowed[1].priority_score, 4),
        ))
    
    # --- Step 6: Quality metrics ---
    degradation = PrescriptiveDegradation.NORMAL
    if grade in ("D", "F"):
        degradation = PrescriptiveDegradation.VERY_LOW_TRUST
    elif grade == "C":
        degradation = PrescriptiveDegradation.LOW_TRUST
    elif l8_input.conflicts:
        degradation = PrescriptiveDegradation.CONFLICT_FLAG
    
    quality = PrescriptiveQuality(
        decision_reliability=max(0.0, min(1.0, {
            "A": 0.95, "B": 0.85, "C": 0.65, "D": 0.35, "F": 0.15
        }.get(grade, 0.5))),
        degradation_mode=degradation,
        audit_grade=grade,
        upstream_confidence=l8_input.source_reliability,
    )
    
    audit = PrescriptiveAudit(
        upstream_run_ids={},
        evidence_snapshot=[{
            "action_id": c.action_id,
            "evidence_count": len(c.evidence),
            "heuristic": c.heuristic,
        } for c in action_cards],
    )
    
    # --- Build output ---
    output = Layer8Output(
        run_id=run_id,
        timestamp=timestamp,
        actions=action_cards,
        schedule=scheduled,
        zone_plan=zone_plan,
        outcome_forecast=outcome,
        tradeoffs=tradeoffs,
        quality=quality,
        audit=audit,
    )
    
    # --- Step 7: Enforce invariants ---
    enforce_layer8_invariants(output)
    
    return output
