from datetime import datetime, timedelta
import pytest

from layer8_prescriptive.schema import (
    Layer8Input, ActionType, ScheduleStatus, PrescriptiveDegradation, ConfidenceLevel,
)
from layer8_prescriptive.action_ranker import ActionRankingEngine
from layer8_prescriptive.scheduler import ConstraintScheduler
from layer8_prescriptive.zone_prioritizer import ZonePrioritizer


def _build_l8_input(audit_grade: str = "B", diagnoses=None, conflicts=None):
    if diagnoses is None:
        diagnoses = [
            {"problem_id": "WATER_STRESS", "probability": 0.85, "severity": 0.70, "confidence": 0.80},
            {"problem_id": "N_DEFICIENCY", "probability": 0.75, "severity": 0.60, "confidence": 0.85},
            {"problem_id": "FUNGAL_RUST", "probability": 0.65, "severity": 0.80, "confidence": 0.70},
        ]
    return Layer8Input(
        diagnoses=diagnoses,
        nutrient_states={"N": {"probability_deficient": 0.75, "severity": "HIGH"}},
        bio_threats={"FUNGAL_RUST": {"probability": 0.65, "risk_level": "HIGH"}},
        weather_forecast=[
            {"date": (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d"),
             "rain_mm": 0.0, "wind_kmh": 10.0, "temp_max": 25.0, "temp_min": 14.0}
            for i in range(7)
        ],
        zone_ids=["zone_1", "zone_2"],
        audit_grade=audit_grade,
        conflicts=conflicts or [],
        crop="wheat",
        phenology_stage="VEGETATIVE",
        species_specific_allowed=True,
        stage_specific_allowed=True,
        crop_posterior_hash="a" * 64,
        phenology_posterior_hash="b" * 64,
    )


def test_action_ranking_multi_objective():
    """Verify action card generation, priority scoring, and sorting descending."""
    l8_input = _build_l8_input(audit_grade="A")
    ranker = ActionRankingEngine()
    cards = ranker.rank_actions(l8_input)

    assert len(cards) >= 3
    # Sorted strictly descending by priority_score
    for i in range(len(cards) - 1):
        assert cards[i].priority_score >= cards[i + 1].priority_score

    # Check mapped action types
    action_types = {c.action_type for c in cards}
    assert ActionType.IRRIGATE in action_types
    assert ActionType.FERTILIZE in action_types
    assert ActionType.SPRAY in action_types

    # Every card has non-empty evidence or is a heuristic monitor card
    for card in cards:
        assert len(card.evidence) >= 1 or card.heuristic is True
        assert card.priority_score > 0.0


def test_action_ranking_trust_degradation():
    """Verify grade C requires confirmation and grade D/F restricts irreversible actions."""
    ranker = ActionRankingEngine()

    # Grade C: Low trust -> irreversible actions marked requires_confirmation
    input_c = _build_l8_input(audit_grade="C")
    cards_c = ranker.rank_actions(input_c)
    for card in cards_c:
        if card.action_type in (ActionType.SPRAY, ActionType.FERTILIZE):
            assert card.requires_confirmation is True

    # Grade D: Very low trust -> irreversible actions (SPRAY, FERTILIZE) downgraded to SCOUT/WAIT/MONITOR
    input_d = _build_l8_input(audit_grade="D")
    cards_d = ranker.rank_actions(input_d)
    for card in cards_d:
        assert card.action_type not in (ActionType.SPRAY, ActionType.FERTILIZE)
    assert any(c.action_type in (ActionType.SCOUT, ActionType.WAIT, ActionType.MONITOR) for c in cards_d)


def test_constraint_scheduler_benign_weather():
    """Under favorable conditions, actions are placed on the calendar as CONFIRMED."""
    l8_input = _build_l8_input(audit_grade="B")
    cards = ActionRankingEngine().rank_actions(l8_input)

    forecast = [
        {"date": (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d"),
         "precipitation": 0.0, "wind_speed": 8.0, "temp_max": 24.0, "temp_min": 12.0}
        for i in range(7)
    ]
    scheduler = ConstraintScheduler()
    schedule = scheduler.schedule_actions(cards, forecast, datetime.now())

    assert len(schedule) == len(cards)
    for item in schedule:
        assert item.status in (ScheduleStatus.CONFIRMED, ScheduleStatus.TENTATIVE)
        assert item.scheduled_date is not None


def test_constraint_scheduler_weather_blocks():
    """High winds and heavy rains block spray and irrigation actions."""
    l8_input = _build_l8_input(audit_grade="B")
    cards = ActionRankingEngine().rank_actions(l8_input)

    # Extreme storm throughout the 7 days: 50mm rain, 45 km/h winds
    storm_forecast = [
        {"date": (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d"),
         "precipitation": 50.0, "wind_speed": 45.0, "temp_max": 18.0, "temp_min": 10.0}
        for i in range(7)
    ]
    scheduler = ConstraintScheduler()
    schedule = scheduler.schedule_actions(cards, storm_forecast, datetime.now())

    # SPRAY must be BLOCKED due to high wind (> 15 km/h) and heavy rain (> 0.5 mm)
    spray_items = [s for s in schedule if s.action_type == ActionType.SPRAY]
    for s in spray_items:
        assert s.status == ScheduleStatus.BLOCKED
        assert any("weather" in b.lower() or "rain" in b.lower() or "wind" in b.lower() for b in s.blocking_constraints)


def test_zone_prioritizer_allocation():
    """Verify zone-aware action prioritization and allocation generation."""
    l8_input = _build_l8_input(audit_grade="A")
    cards = ActionRankingEngine().rank_actions(l8_input)
    prioritizer = ZonePrioritizer()
    zone_plans = prioritizer.prioritize_zones(cards, {"zone_1": 0.8, "zone_2": 0.8}, l8_input.zone_ids)

    assert "zone_1" in zone_plans
    assert "zone_2" in zone_plans
    for z_id, plan in zone_plans.items():
        assert plan.zone_id == z_id
        assert len(plan.actions) > 0
