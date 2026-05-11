"""
Layer 8 Pipeline Runner -- Prescriptive Intelligence Engine v8.2.0
==================================================================

Orchestrates the full 12-step prescriptive pipeline:

  1. Rank actions (multi-objective scoring)
  2. Phenology dosing (BBCH rate scaling)
  3. Nutrient interactions (Liebig's law + antagonisms)
  4. IPM cascade (economic threshold escalation)
  5. Environmental risk (leaching/runoff scoring)
  6. Re-score (recalculate priorities after adjustments)
  7. Schedule (weather-constrained calendar placement)
  8. Zone allocation (reliability-aware zone assignment)
  9. Cognitive load management (decision fatigue pruning)
  10. Adoption modeling (farmer adoption probability)
  11. Framing (prospect-theory message generation)
  12. Invariant enforcement (mandatory safety gate)

Production-grade with:
  - Deterministic run_id from upstream content hash
  - Structured logging (no print statements)
  - Full invariant gating before emission
"""

import logging
import hashlib
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from layer8_prescriptive.schema import (
    Layer8Input, Layer8Output, OutcomeForecast, Tradeoff,
    PrescriptiveQuality, PrescriptiveAudit, PrescriptiveDegradation,
    ConfidenceLevel, CognitiveLoadProfile,
)
from layer8_prescriptive.action_ranker import ActionRankingEngine
from layer8_prescriptive.scheduler import ConstraintScheduler
from layer8_prescriptive.zone_prioritizer import ZonePrioritizer
from layer8_prescriptive.invariants import enforce_layer8_invariants

# Intelligence engines
from layer8_prescriptive.engines.phenology_dosing import PhenologyDosingEngine
from layer8_prescriptive.engines.nutrient_interaction import NutrientInteractionEngine
from layer8_prescriptive.engines.ipm_cascade import IPMCascadeEngine
from layer8_prescriptive.engines.environmental_risk import EnvironmentalRiskEngine
from layer8_prescriptive.engines.cognitive_load import CognitiveLoadEngine
from layer8_prescriptive.engines.adoption_model import AdoptionModelEngine
from layer8_prescriptive.engines.framing_engine import FramingEngine

logger = logging.getLogger(__name__)

ENGINE_VERSION = "8.2.0"

# Grade -> confidence level mapping
_GRADE_TO_CONFIDENCE = {
    "A": ConfidenceLevel.HIGH,
    "B": ConfidenceLevel.HIGH,
    "C": ConfidenceLevel.MODERATE,
    "D": ConfidenceLevel.LOW,
    "F": ConfidenceLevel.LOW,
}

# Grade -> decision reliability mapping
_GRADE_TO_RELIABILITY = {
    "A": 0.95, "B": 0.85, "C": 0.65, "D": 0.35, "F": 0.15,
}

# Grade -> degradation mode mapping
_GRADE_TO_DEGRADATION = {
    "D": PrescriptiveDegradation.VERY_LOW_TRUST,
    "F": PrescriptiveDegradation.VERY_LOW_TRUST,
    "C": PrescriptiveDegradation.LOW_TRUST,
}


def _canonical_json(obj):
    """Deterministic JSON for hashing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _generate_run_id(l8_input):
    """Deterministic run_id from upstream content hash."""
    content = {
        "diagnoses_count": len(l8_input.diagnoses),
        "nutrient_keys": sorted(l8_input.nutrient_states.keys()),
        "threat_keys": sorted(l8_input.bio_threats.keys()),
        "zone_ids": sorted(l8_input.zone_ids),
        "audit_grade": l8_input.audit_grade,
        "phenology_stage": l8_input.phenology_stage,
        "horizon_days": l8_input.horizon_days,
        "crop": l8_input.crop,
        "engine_version": ENGINE_VERSION,
    }
    digest = hashlib.sha256(
        _canonical_json(content).encode("utf-8")
    ).hexdigest()[:12]
    return "L8-{}".format(digest)


def _generate_content_hash(output):
    """Content hash of the output for reproducibility audit."""
    content = {
        "actions": [
            {"id": c.action_id, "type": c.action_type.value,
             "score": round(c.priority_score, 6), "allowed": c.is_allowed}
            for c in output.actions
        ],
        "schedule": [
            {"id": s.action_id, "status": s.status.value, "date": s.scheduled_date}
            for s in output.schedule
        ],
        "zones": {k: v.priority for k, v in output.zone_plan.items()},
        "quality": {
            "reliability": output.quality.decision_reliability,
            "degradation": output.quality.degradation_mode.value,
        },
        "engine_version": ENGINE_VERSION,
    }
    return hashlib.sha256(_canonical_json(content).encode("utf-8")).hexdigest()


def run_layer8(l8_input, forecast=None, start_date=None):
    """
    Run the full Layer 8 prescriptive intelligence pipeline.

    12-step pipeline:
      rank -> phenology -> nutrients -> IPM -> env_risk -> rescore ->
      schedule -> zones -> cognitive_load -> adoption -> framing -> invariants

    Args:
        l8_input: Layer8Input with upstream layer outputs + audit info
        forecast: Weather forecast for scheduling (default: empty)
        start_date: Planning start date (default: today)

    Returns:
        Layer8Output with ranked actions, schedule, zone plan, audit
    """
    if forecast is None:
        forecast = []
    if start_date is None:
        start_date = datetime.now()

    run_id = _generate_run_id(l8_input)
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    grade = l8_input.audit_grade.upper()
    crop = l8_input.crop.lower()
    degradation = _GRADE_TO_DEGRADATION.get(grade, PrescriptiveDegradation.NORMAL)
    if degradation == PrescriptiveDegradation.NORMAL and l8_input.conflicts:
        degradation = PrescriptiveDegradation.CONFLICT_FLAG

    logger.debug("L8 v%s run_id=%s grade=%s crop=%s zones=%d diagnoses=%d threats=%d",
                 ENGINE_VERSION, run_id, grade, crop,
                 len(l8_input.zone_ids), len(l8_input.diagnoses),
                 len(l8_input.bio_threats))

    # ---------------------------------------------------------------
    # Step 1: Rank actions (multi-objective scoring)
    # ---------------------------------------------------------------
    ranker = ActionRankingEngine()
    action_cards = ranker.rank_actions(l8_input)
    logger.debug("Step 1/12 RANK: %d action cards", len(action_cards))

    # ---------------------------------------------------------------
    # Step 2: Phenology-aware dosing (BBCH rate scaling)
    # ---------------------------------------------------------------
    pheno = PhenologyDosingEngine()
    action_cards = pheno.adjust_rates(action_cards, crop, l8_input.phenology_stage)
    logger.debug("Step 2/12 PHENOLOGY: BBCH rates adjusted for %s/%s",
                 crop, l8_input.phenology_stage)

    # ---------------------------------------------------------------
    # Step 3: Nutrient interaction check (Liebig + antagonisms)
    # ---------------------------------------------------------------
    nut_engine = NutrientInteractionEngine()
    nut_result = nut_engine.analyze(action_cards, l8_input.nutrient_states)
    action_cards = nut_engine.apply_adjustments(action_cards, nut_result)
    logger.debug("Step 3/12 NUTRIENTS: limiting=%s antagonisms=%d synergies=%d",
                 nut_result.limiting_nutrient,
                 len(nut_result.antagonisms_detected),
                 len(nut_result.synergies_detected))

    # ---------------------------------------------------------------
    # Step 4: IPM cascade (economic threshold escalation)
    # ---------------------------------------------------------------
    ipm = IPMCascadeEngine()
    action_cards = ipm.apply_ipm_decisions(
        action_cards, l8_input.bio_threats, degradation)
    logger.debug("Step 4/12 IPM: cascade applied (degradation=%s)", degradation.value)

    # ---------------------------------------------------------------
    # Step 5: Environmental risk scoring
    # ---------------------------------------------------------------
    env = EnvironmentalRiskEngine()
    action_cards = env.apply_risk_scores(
        action_cards, l8_input.soil_static, forecast)
    logger.debug("Step 5/12 ENV_RISK: leaching/runoff scored")

    # ---------------------------------------------------------------
    # Step 6: Re-score priorities (after all adjustments)
    # ---------------------------------------------------------------
    for card in action_cards:
        bd = card.priority_breakdown
        w = ranker.weights
        card.priority_score = round(
            bd.impact_score * w["impact"] +
            bd.urgency_score * w["urgency"] +
            bd.risk_score * w["risk"] +
            bd.cost_score * w["cost"] +
            bd.confidence_score * w["confidence"],
            4
        )
    action_cards.sort(key=lambda c: c.priority_score, reverse=True)
    logger.debug("Step 6/12 RESCORE: priorities recalculated post-adjustment")

    # ---------------------------------------------------------------
    # Step 7: Schedule (weather-constrained calendar placement)
    # ---------------------------------------------------------------
    sched = ConstraintScheduler()
    scheduled = sched.schedule_actions(
        action_cards, forecast, start_date,
        horizon_days=l8_input.horizon_days,
        phenology_stage=l8_input.phenology_stage,
    )
    logger.debug("Step 7/12 SCHEDULE: %d actions scheduled", len(scheduled))

    # ---------------------------------------------------------------
    # Step 8: Zone allocation (reliability-aware)
    # ---------------------------------------------------------------
    zone_eng = ZonePrioritizer()
    zone_plan = zone_eng.prioritize_zones(
        action_cards,
        zone_reliability=l8_input.source_reliability,
        zone_ids=l8_input.zone_ids if l8_input.zone_ids else ["plot"],
    )
    logger.debug("Step 8/12 ZONES: %d zones allocated", len(zone_plan))

    # ---------------------------------------------------------------
    # Step 9: Cognitive load management (decision fatigue pruning)
    # ---------------------------------------------------------------
    cog = CognitiveLoadEngine()
    action_cards, cog_profile = cog.manage_load(action_cards)
    # Re-align schedule with pruned action list
    kept_ids = {c.action_id for c in action_cards}
    scheduled = [s for s in scheduled if s.action_id in kept_ids]
    logger.debug("Step 9/12 COGNITIVE: %d presented, %d suppressed",
                 cog_profile.actions_presented, cog_profile.actions_suppressed)

    # ---------------------------------------------------------------
    # Step 10: Adoption probability (TAM-based scoring)
    # ---------------------------------------------------------------
    adopt = AdoptionModelEngine()
    action_cards = adopt.score_adoption(action_cards)
    logger.debug("Step 10/12 ADOPTION: scored %d actions", len(action_cards))

    # ---------------------------------------------------------------
    # Step 11: Prospect-theory framing (loss/gain messaging)
    # ---------------------------------------------------------------
    framer = FramingEngine()
    action_cards = framer.frame_actions(action_cards, crop)
    logger.debug("Step 11/12 FRAMING: messages generated")

    # ---------------------------------------------------------------
    # Compute outcome forecast
    # ---------------------------------------------------------------
    allowed_cards = [c for c in action_cards if c.is_allowed]
    total_impact = (sum(c.priority_breakdown.impact_score for c in allowed_cards)
                    / max(1, len(action_cards)))
    total_cost = sum(c.rate.recommended * 2 if c.rate else 0
                     for c in allowed_cards)
    conf = _GRADE_TO_CONFIDENCE.get(grade, ConfidenceLevel.MODERATE)

    outcome = OutcomeForecast(
        yield_delta_pct=round(total_impact * 15, 1),
        risk_reduction_pct=round(total_impact * 20, 1),
        cost_total=round(total_cost, 2),
        roi_pct=round((total_impact * 15 / max(1, total_cost)) * 100, 1) if total_cost > 0 else 0,
        confidence=conf,
    )

    # ---------------------------------------------------------------
    # Generate tradeoffs
    # ---------------------------------------------------------------
    tradeoffs = []
    allowed_evidence = [c for c in allowed_cards if not c.heuristic]
    if len(allowed_evidence) >= 2:
        a0 = allowed_evidence[0]
        a1 = allowed_evidence[1]
        tradeoffs.append(Tradeoff(
            chosen_action_id=a0.action_id,
            rejected_action_id=a1.action_id,
            reason="{} ranks higher: impact={:.2f} vs {:.2f}".format(
                a0.action_type.value,
                a0.priority_breakdown.impact_score,
                a1.priority_breakdown.impact_score),
            score_delta=round(a0.priority_score - a1.priority_score, 4),
        ))

    # ---------------------------------------------------------------
    # Quality metrics
    # ---------------------------------------------------------------
    quality = PrescriptiveQuality(
        decision_reliability=max(0.0, min(1.0, _GRADE_TO_RELIABILITY.get(grade, 0.5))),
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
            "adoption_prob": c.adoption.adoption_probability if c.adoption else None,
            "frame_type": c.framed_message.frame_type.value if c.framed_message else None,
        } for c in action_cards],
    )

    # ---------------------------------------------------------------
    # Build output
    # ---------------------------------------------------------------
    output = Layer8Output(
        run_id=run_id,
        timestamp=timestamp,
        actions=action_cards,
        schedule=scheduled,
        zone_plan=zone_plan,
        outcome_forecast=outcome,
        tradeoffs=tradeoffs,
        cognitive_load=cog_profile,
        quality=quality,
        audit=audit,
    )

    # Content hash for audit trail
    output.audit.policy_checks.append({
        "check": "content_hash",
        "value": _generate_content_hash(output),
        "engine_version": ENGINE_VERSION,
    })

    # ---------------------------------------------------------------
    # Step 12: Enforce invariants (mandatory safety gate)
    # ---------------------------------------------------------------
    violations = enforce_layer8_invariants(output)
    if violations:
        logger.debug("Step 12/12 INVARIANTS: %d auto-fixed", len(violations))
    else:
        logger.debug("Step 12/12 INVARIANTS: clean pass")

    logger.debug("L8 COMPLETE: %d actions, %d scheduled, degradation=%s, "
                 "reliability=%.2f, cognitive_load=%d/%d",
                 len(output.actions), len(output.schedule),
                 output.quality.degradation_mode.value,
                 output.quality.decision_reliability,
                 cog_profile.actions_presented,
                 cog_profile.actions_presented + cog_profile.actions_suppressed)

    return output
