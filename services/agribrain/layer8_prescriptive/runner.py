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
    ConfidenceLevel, CognitiveLoadProfile, ActionType, PrescriptiveEvidence,
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
from layer8_prescriptive.engines.adoption_model import adoption_engine
from layer8_prescriptive.engines.framing_engine import FramingEngine
from layer8_prescriptive.engines.salinity_leaching import salinity_leaching_engine
from layer8_prescriptive.engines.crop_cooling import crop_cooling_engine
from layer8_prescriptive.engines.spray_drift_gate import spray_drift_gate_engine
from layer8_prescriptive.engines.tillage_compaction import tillage_compaction_engine
from layer8_prescriptive.engines.lodging_pgr import lodging_pgr_engine
from layer8_prescriptive.engines.volatilization_inhibitor import volatilization_inhibitor_engine
from layer8_prescriptive.engines.frost_sprinkling import frost_sprinkling_engine

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


def _valid_receipt_hash(value: Any) -> bool:
    token = str(value or "").lower()
    return len(token) == 64 and all(char in "0123456789abcdef" for char in token)


def _semantic_authority(l8_input: Layer8Input):
    crop_hash_ok = _valid_receipt_hash(l8_input.crop_posterior_hash)
    phenology_hash_ok = _valid_receipt_hash(l8_input.phenology_posterior_hash)
    species_allowed = bool(l8_input.species_specific_allowed and crop_hash_ok)
    stage_allowed = bool(
        l8_input.stage_specific_allowed
        and phenology_hash_ok
        and str(l8_input.phenology_authority or "").upper() == "CALIBRATED"
    )
    reasons = list(l8_input.semantic_demotion_reasons)
    if not crop_hash_ok:
        reasons.append("crop_posterior_hash_missing_or_invalid")
    if not phenology_hash_ok:
        reasons.append("phenology_posterior_hash_missing_or_invalid")
    if not species_allowed:
        reasons.append("species_specific_authority_unavailable")
    if not stage_allowed:
        reasons.append(
            "calibrated_stage_authority_required_for_prescription"
            if l8_input.stage_specific_allowed
            else "stage_specific_authority_unavailable"
        )
    return species_allowed, stage_allowed, list(dict.fromkeys(reasons))


def _apply_semantic_prescription_gate(action_cards, l8_input, species_allowed, stage_allowed, reasons):
    safe_observation_types = {ActionType.SCOUT, ActionType.MONITOR, ActionType.WAIT}
    contract = l8_input.group_recommendation_contract or {}
    contract_valid = bool(
        l8_input.crop_resolution == "group_only"
        and _valid_receipt_hash(contract.get("content_hash"))
        and _valid_receipt_hash(l8_input.crop_posterior_hash)
    )
    group_safe = {
        str(value).upper() for value in (contract.get("safe_action_types") or [])
    } if contract_valid else set()

    for card in action_cards:
        original_type = card.action_type
        prescriptive = original_type not in safe_observation_types
        exact_authorized = species_allowed and stage_allowed
        group_authorized = (
            stage_allowed and original_type.value.upper() in group_safe
        )
        if prescriptive and not (exact_authorized or group_authorized):
            card.action_type = ActionType.SCOUT
            card.rate = None
            card.requires_confirmation = True
            card.confidence = ConfidenceLevel.LOW
            card.priority_breakdown.confidence_score = min(
                card.priority_breakdown.confidence_score, 0.30
            )
            card.blocked_reason.extend(
                reason for reason in reasons if reason not in card.blocked_reason
            )
            card.explain = (
                f"Scout/confirm before {original_type.value.lower()}: canonical "
                "crop and phenology authority is insufficient."
            )
        card.evidence.append(PrescriptiveEvidence(
            source_layer="L2",
            evidence_type="crop_phenology_receipt",
            reference_id=(
                f"crop:{l8_input.crop_posterior_hash or 'missing'}|"
                f"phenology:{l8_input.phenology_posterior_hash or 'missing'}"
            ),
            contribution=0.0,
            description=(
                f"crop={l8_input.crop_evidence_class}; "
                f"phenology={l8_input.phenology_evidence_class}; "
                f"original_action={original_type.value}"
            ),
            source_type="canonical_receipt",
        ))
    return action_cards


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
        "crop_posterior_hash": l8_input.crop_posterior_hash,
        "phenology_posterior_hash": l8_input.phenology_posterior_hash,
        "crop_evidence_class": l8_input.crop_evidence_class,
        "phenology_evidence_class": l8_input.phenology_evidence_class,
        "group_contract_hash": l8_input.group_recommendation_contract.get("content_hash", ""),
        "input_belief_id": l8_input.input_belief_id,
        "tribunal_content_hash": l8_input.tribunal_content_hash,
        "prescription_manifest_hash": l8_input.prescription_manifest_hash,
        "prescription_manifest_entry_ids": sorted(l8_input.prescription_manifest_entry_ids),
        "policy_snapshot_hash": l8_input.policy_snapshot_hash,
        "engine_version": ENGINE_VERSION,
    }
    digest = hashlib.sha256(
        _canonical_json(content).encode("utf-8")
    ).hexdigest()[:12]
    return "L8-{}".format(digest)


def _generate_content_hash(output):
    """Content hash of the output for reproducibility audit."""
    content = {
        "actions": [{
            "id": c.action_id,
            "type": c.action_type.value,
            "score": round(c.priority_score, 6),
            "allowed": c.is_allowed,
            "confidence": c.confidence.value,
            "requires_confirmation": c.requires_confirmation,
            "zones": list(c.zone_targets),
            "rate": ({
                "recommended": c.rate.recommended,
                "min_safe": c.rate.min_safe,
                "max_safe": c.rate.max_safe,
                "unit": c.rate.unit,
            } if c.rate else None),
            "timing": ({
                "earliest": c.time_window.earliest,
                "latest": c.time_window.latest,
                "optimal": c.time_window.optimal,
            } if c.time_window else None),
            "explain": c.explain,
        } for c in output.actions],
        "schedule": [
            {"id": s.action_id, "status": s.status.value, "date": s.scheduled_date}
            for s in output.schedule
        ],
        "zones": {k: v.priority for k, v in output.zone_plan.items()},
        "quality": {
            "reliability": output.quality.decision_reliability,
            "degradation": output.quality.degradation_mode.value,
        },
        "semantic_receipt": next((
            check for check in output.audit.policy_checks
            if check.get("check") == "crop_phenology_prescription_authority"
        ), {}),
        "promotion_lineage": next((
            check for check in output.audit.policy_checks
            if check.get("check") == "prescription_promotion_lineage"
        ), {}),
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
    species_allowed, stage_allowed, semantic_reasons = _semantic_authority(l8_input)
    crop = l8_input.crop.lower() if species_allowed else "unknown"
    canonical_stage = l8_input.phenology_stage if stage_allowed else "UNKNOWN"
    degradation = _GRADE_TO_DEGRADATION.get(grade, PrescriptiveDegradation.NORMAL)
    if degradation == PrescriptiveDegradation.NORMAL and l8_input.conflicts:
        degradation = PrescriptiveDegradation.CONFLICT_FLAG
    if not (species_allowed and stage_allowed):
        degradation = PrescriptiveDegradation.DATA_GAP

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
    if species_allowed and stage_allowed:
        pheno = PhenologyDosingEngine()
        action_cards = pheno.adjust_rates(action_cards, crop, canonical_stage)

        # Crop Canopy Cooling evaluation
        action_cards = crop_cooling_engine.evaluate_cooling_need(
            action_cards, crop, canonical_stage, forecast
        )
    
    # Frost protection sprinkling check
    action_cards = frost_sprinkling_engine.evaluate_frost_risk(action_cards, forecast)
    
    # Soil Salinity Leaching requirement
    soil_salinity = l8_input.soil_static.get("soil_salinity_ece", 0.0)
    if not soil_salinity and "salinity" in l8_input.nutrient_states:
        soil_salinity = l8_input.nutrient_states["salinity"]
    if species_allowed:
        action_cards = salinity_leaching_engine.adjust_irrigation_for_salinity(
            action_cards, crop, soil_salinity
        )
    
    # Soil Compaction tillage check
    soil_bd = l8_input.soil_static.get("soil_bulk_density", 1.40)
    soil_txt = l8_input.soil_static.get("soil_texture", "loam")
    if stage_allowed:
        action_cards = tillage_compaction_engine.evaluate_compaction(
            action_cards, soil_bd, soil_txt, canonical_stage
        )
    
    logger.debug("Step 2/12 PHENOLOGY: BBCH rates, crop cooling, leaching, frost protection, and tillage adjusted for %s/%s",
                 crop, canonical_stage)

    # ---------------------------------------------------------------
    # Step 3: Nutrient interaction check (Liebig + antagonisms)
    # ---------------------------------------------------------------
    nut_engine = NutrientInteractionEngine()
    nut_result = nut_engine.analyze(action_cards, l8_input.nutrient_states)
    action_cards = nut_engine.apply_adjustments(action_cards, nut_result)
    
    # Nitrogen Volatilization inhibitor NBPT check
    soil_ph = l8_input.soil_static.get("soil_ph", 6.5)
    air_temp = sum(day.get("temp_max") if day.get("temp_max") is not None else 25.0 for day in forecast) / max(1, len(forecast))
    soil_moisture_pct = l8_input.soil_static.get("soil_moisture_pct", 40.0)
    action_cards = volatilization_inhibitor_engine.evaluate_volatilization(
        action_cards, soil_ph, air_temp, soil_moisture_pct
    )
    
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
        
    # Crop Lodging & growth regulator check
    canopy_height = l8_input.soil_static.get("canopy_height_m", 0.5)
    growth_velocity = l8_input.soil_static.get("growth_velocity_daily", 0.02)
    n_surplus = l8_input.soil_static.get("nitrogen_surplus_kg_ha", 0.0)
    if species_allowed:
        action_cards = lodging_pgr_engine.evaluate_lodging_risk(
            action_cards, crop, canopy_height, growth_velocity, n_surplus, forecast
        )
    
    logger.debug("Step 4/12 IPM: cascade and lodging PGR check applied (degradation=%s)", degradation.value)

    # ---------------------------------------------------------------
    # Step 5: Environmental risk scoring
    # ---------------------------------------------------------------
    env = EnvironmentalRiskEngine()
    action_cards = env.apply_risk_scores(
        action_cards, l8_input.soil_static, forecast)
        
    # Enforce US EPA pesticide spray drift limits and buffer zones
    action_cards = spray_drift_gate_engine.enforce_drift_limits(action_cards, forecast)
    
    logger.debug("Step 5/12 ENV_RISK: leaching/runoff and spray drift safety scored")

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

    # Hard production boundary: every action now carries the canonical receipt.
    # Unsafe rates/timing are converted into evidence-gathering actions.
    action_cards = _apply_semantic_prescription_gate(
        action_cards, l8_input, species_allowed, stage_allowed, semantic_reasons,
    )

    # ---------------------------------------------------------------
    # Step 7: Schedule (weather-constrained calendar placement)
    # ---------------------------------------------------------------
    sched = ConstraintScheduler()
    scheduled = sched.schedule_actions(
        action_cards, forecast, start_date,
        horizon_days=l8_input.horizon_days,
        phenology_stage=canonical_stage,
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
    action_cards = adoption_engine.score_adoption(action_cards)
    logger.debug("Step 10/12 ADOPTION: scored %d actions", len(action_cards))

    # ---------------------------------------------------------------
    # Step 11: Prospect-theory framing (loss/gain messaging)
    # ---------------------------------------------------------------
    framer = FramingEngine()
    action_cards = framer.frame_actions(
        action_cards, crop if species_allowed else "field"
    )
    logger.debug("Step 11/12 FRAMING: messages generated")

    # ---------------------------------------------------------------
    # Compute outcome forecast
    # ---------------------------------------------------------------
    allowed_cards = [c for c in action_cards if c.is_allowed]
    outcome_cards = [
        c for c in allowed_cards
        if c.action_type not in {ActionType.SCOUT, ActionType.MONITOR, ActionType.WAIT}
    ]
    total_impact = (sum(c.priority_breakdown.impact_score for c in outcome_cards)
                    / max(1, len(action_cards)))
    total_cost = sum(c.rate.recommended * 2 if c.rate else 0
                     for c in outcome_cards)
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
        decision_reliability=max(0.0, min(
            _GRADE_TO_RELIABILITY.get(grade, 0.5),
            1.0 if species_allowed and stage_allowed else 0.30,
        )),
        degradation_mode=degradation,
        audit_grade=grade,
        upstream_confidence=l8_input.source_reliability,
        missing_inputs=semantic_reasons,
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
        policy_checks=[{
            "check": "crop_phenology_prescription_authority",
            "crop_posterior_hash": l8_input.crop_posterior_hash,
            "phenology_posterior_hash": l8_input.phenology_posterior_hash,
            "crop_resolution": l8_input.crop_resolution,
            "crop_authority": l8_input.crop_authority,
            "phenology_authority": l8_input.phenology_authority,
            "crop_evidence_class": l8_input.crop_evidence_class,
            "phenology_evidence_class": l8_input.phenology_evidence_class,
            "species_specific_allowed": species_allowed,
            "stage_specific_allowed": stage_allowed,
            "crop_mixture": l8_input.crop_mixture,
            "stage_posterior": l8_input.stage_posterior,
            "group_recommendation_contract_hash": (
                l8_input.group_recommendation_contract.get("content_hash", "")
            ),
            "demotion_reasons": semantic_reasons,
        }, {
            "check": "prescription_promotion_lineage",
            "input_belief_id": l8_input.input_belief_id,
            "tribunal_content_hash": l8_input.tribunal_content_hash,
            "prescription_manifest_hash": l8_input.prescription_manifest_hash,
            "prescription_manifest_entry_ids": sorted(
                l8_input.prescription_manifest_entry_ids
            ),
            "policy_snapshot_hash": l8_input.policy_snapshot_hash,
            "publication_status": "SHADOW_ONLY_PENDING_AUTHORIZATION_ENVELOPE",
        }],
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

    # ---------------------------------------------------------------
    # Step 12: Enforce invariants (mandatory safety gate)
    # ---------------------------------------------------------------
    violations = enforce_layer8_invariants(output)
    if violations:
        logger.debug("Step 12/12 INVARIANTS: %d auto-fixed", len(violations))
    else:
        logger.debug("Step 12/12 INVARIANTS: clean pass")

    # Hash the final, invariant-enforced output.  This value is later bound by
    # the authorization envelope, so it must cover any auto-fixes.
    output.audit.policy_checks.append({
        "check": "content_hash",
        "value": _generate_content_hash(output),
        "engine_version": ENGINE_VERSION,
    })

    logger.debug("L8 COMPLETE: %d actions, %d scheduled, degradation=%s, "
                 "reliability=%.2f, cognitive_load=%d/%d",
                 len(output.actions), len(output.schedule),
                 output.quality.degradation_mode.value,
                 output.quality.decision_reliability,
                 cog_profile.actions_presented,
                 cog_profile.actions_presented + cog_profile.actions_suppressed)

    return output
