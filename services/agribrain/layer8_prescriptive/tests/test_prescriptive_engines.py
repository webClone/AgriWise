import pytest

from layer8_prescriptive.schema import (
    ActionCard, ActionType, RateRange, PriorityBreakdown, PrescriptiveEvidence,
    ConfidenceLevel, BBCHStageInfo, IPMLevel, FrameType, PrescriptiveDegradation,
)
from layer8_prescriptive.engines.phenology_dosing import PhenologyDosingEngine
from layer8_prescriptive.engines.nutrient_interaction import NutrientInteractionEngine
from layer8_prescriptive.engines.ipm_cascade import IPMCascadeEngine
from layer8_prescriptive.engines.environmental_risk import EnvironmentalRiskEngine
from layer8_prescriptive.engines.framing_engine import FramingEngine
from layer8_prescriptive.engines.cognitive_load import CognitiveLoadEngine


def _make_action(action_type: ActionType, action_id: str, priority: float = 0.5, ref_id: str = "REF") -> ActionCard:
    return ActionCard(
        action_id=action_id,
        action_type=action_type,
        priority_score=priority,
        priority_breakdown=PriorityBreakdown(
            impact_score=0.6, urgency_score=0.5, risk_score=0.4, cost_score=0.5, confidence_score=0.8
        ),
        zone_targets=["zone_1"],
        zone_allocation={"zone_1": 1.0},
        rate=RateRange(recommended=50.0, min_safe=20.0, max_safe=100.0, unit="kg/ha"),
        evidence=[
            PrescriptiveEvidence(
                source_layer="L4", evidence_type="nutrient_state",
                reference_id=ref_id, contribution=0.8, description="Test evidence"
            )
        ],
        confidence=ConfidenceLevel.HIGH,
        explain="Test card",
    )


def test_phenology_dosing_lookup_and_scaling():
    """Verify BBCH stage lookup and rate scaling across phenological stages."""
    engine = PhenologyDosingEngine()

    # 1. Lookup wheat vegetative (tillering) vs reproductive (anthesis)
    stage_veg = engine.lookup_stage("wheat", "VEGETATIVE")
    assert stage_veg.bbch_code == 25
    assert stage_veg.critical_period is False

    stage_rep = engine.lookup_stage("wheat", "REPRODUCTIVE")
    assert stage_rep.bbch_code == 61
    assert stage_rep.critical_period is True

    # 2. Rate adjustments
    fert_card = _make_action(ActionType.FERTILIZE, "fert_n", ref_id="N_DEFICIENCY")
    irr_card = _make_action(ActionType.IRRIGATE, "irr_1", ref_id="WATER_STRESS")
    cards = [fert_card, irr_card]

    # Adjust rates for reproductive stage (high water demand 1.6x, high N absorption 0.65)
    adjusted = engine.adjust_rates(cards, "wheat", "REPRODUCTIVE")
    assert adjusted[0].rate.recommended > 50.0
    assert adjusted[1].rate.recommended > 50.0
    # Critical period boosts urgency
    assert adjusted[0].priority_breakdown.urgency_score > 0.5


def test_nutrient_interaction_liebig_and_antagonisms():
    """Verify Liebig's law of minimum and K-Mg / P-Zn interaction detection."""
    engine = NutrientInteractionEngine()

    card_n = _make_action(ActionType.FERTILIZE, "fert_n", priority=0.6, ref_id="N_DEFICIENCY")
    card_k = _make_action(ActionType.FERTILIZE, "fert_k", priority=0.5, ref_id="K_DEFICIENCY")
    cards = [card_n, card_k]

    nutrient_states = {
        "N": {"probability_deficient": 0.85, "severity": "HIGH"},
        "K": {"probability_deficient": 0.40, "severity": "MODERATE"},
        "Mg": {"probability_deficient": 0.30, "severity": "LOW"},
    }

    result = engine.analyze(cards, nutrient_states)
    assert result.limiting_nutrient == "N"
    # K-Mg antagonism flagged
    assert any(a[0] == "K" and a[1] == "MG" for a in result.antagonisms_detected)

    # Adjust actions applies interaction adjustments
    adjusted_cards = engine.apply_adjustments(cards, result)
    assert len(adjusted_cards) == len(cards)


def test_ipm_cascade_escalation_ladder():
    """Verify pest pressure below threshold triggers SCOUT/MONITOR, above triggers SPRAY."""
    engine = IPMCascadeEngine()

    # 1. Low pest pressure (0.15) below economic injury level (0.30)
    dec_low = engine.evaluate_threat(
        threat_id="FUNGAL_RUST", probability=0.15, severity=0.5, degradation=PrescriptiveDegradation.NORMAL
    )
    # Escalation level is preventative/scouting
    assert dec_low.escalation_level in (IPMLevel.MONITOR, IPMLevel.SCOUT, IPMLevel.BIOLOGICAL)

    # 2. Severe pest pressure (0.90) above economic injury level
    dec_high = engine.evaluate_threat(
        threat_id="FUNGAL_RUST", probability=0.90, severity=0.90, degradation=PrescriptiveDegradation.NORMAL
    )
    assert dec_high.escalation_level in (IPMLevel.CHEMICAL_TARGETED, IPMLevel.CHEMICAL_BROAD)
    assert dec_high.above_threshold is True


def test_environmental_risk_and_framing():
    """Verify leaching/runoff environmental gating and prospect theory framing."""
    # 1. Environmental risk
    env_engine = EnvironmentalRiskEngine()
    card_fert = _make_action(ActionType.FERTILIZE, "fert_n", ref_id="N_DEFICIENCY")
    risk_res = env_engine.score_risk(card_fert, soil_clay_pct=5.0, soil_org_carbon=0.5, forecast_rain_48h=45.0)
    assert risk_res.leaching_index > 0.3

    # 2. Behavioral framing
    framing_engine = FramingEngine()
    card_irr = _make_action(ActionType.IRRIGATE, "irr_1", ref_id="WATER_STRESS")
    cards = framing_engine.frame_actions([card_irr], crop="wheat")
    assert cards[0].framed_message is not None
    assert len(cards[0].framed_message.primary_message) > 0


def test_cognitive_load_pruning():
    """Verify cognitive load engine groups and limits excessive simultaneous actions."""
    engine = CognitiveLoadEngine(max_actions=4)

    many_cards = [
        _make_action(ActionType.IRRIGATE, f"irr_{i}", priority=0.8 - i * 0.05)
        for i in range(10)
    ]
    retained_cards, profile = engine.manage_load(many_cards)
    assert profile.actions_presented <= 5
    assert profile.actions_presented + profile.actions_suppressed == 10
    assert len(retained_cards) <= 5
