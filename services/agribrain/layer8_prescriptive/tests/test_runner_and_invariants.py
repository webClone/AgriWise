from datetime import datetime, timedelta
import pytest

from layer8_prescriptive.schema import (
    Layer8Input, Layer8Output, ActionType, ScheduleStatus, PrescriptiveDegradation, RateRange,
)
from layer8_prescriptive.runner import run_layer8
from layer8_prescriptive.invariants import enforce_layer8_invariants


def _build_full_l8_input(audit_grade="A", conflicts=None, species_allowed=True, stage_allowed=True):
    return Layer8Input(
        diagnoses=[
            {"problem_id": "WATER_STRESS", "probability": 0.85, "severity": 0.70, "confidence": 0.85},
            {"problem_id": "N_DEFICIENCY", "probability": 0.75, "severity": 0.65, "confidence": 0.80},
            {"problem_id": "FUNGAL_RUST", "probability": 0.60, "severity": 0.75, "confidence": 0.70},
        ],
        nutrient_states={"N": {"probability_deficient": 0.75, "severity": "HIGH"}},
        bio_threats={"FUNGAL_RUST": {"probability": 0.60, "risk_level": "HIGH"}},
        weather_forecast=[
            {"date": (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d"),
             "rain_mm": 0.0, "precipitation": 0.0, "wind_kmh": 10.0, "wind_speed": 10.0,
             "temp_max": 25.0, "temp_min": 14.0}
            for i in range(7)
        ],
        zone_ids=["zone_north", "zone_south"],
        audit_grade=audit_grade,
        conflicts=conflicts or [],
        crop="wheat",
        crop_authority="CALIBRATED",
        phenology_stage="VEGETATIVE",
        phenology_authority="CALIBRATED",
        species_specific_allowed=species_allowed,
        stage_specific_allowed=stage_allowed,
        crop_posterior_hash="c" * 64,
        phenology_posterior_hash="d" * 64,
    )


def test_layer8_runner_end_to_end():
    """Verify full 12-step execution of Layer 8 prescriptive pipeline."""
    l8_input = _build_full_l8_input(audit_grade="A")
    output = run_layer8(l8_input)

    assert isinstance(output, Layer8Output)
    assert output.run_id is not None and output.run_id.startswith("L8-") and len(output.run_id) == 15
    assert output.timestamp is not None

    # Actions ranked and populated
    assert len(output.actions) >= 3
    # Sorted by priority
    for i in range(len(output.actions) - 1):
        assert output.actions[i].priority_score >= output.actions[i + 1].priority_score

    # Schedule placed
    assert len(output.schedule) == len(output.actions)
    for s in output.schedule:
        assert s.scheduled_date is not None

    # Zone plan
    assert "zone_north" in output.zone_plan
    assert "zone_south" in output.zone_plan

    # Outcome forecast
    assert output.outcome_forecast is not None
    assert output.outcome_forecast.yield_delta_pct >= 0.0
    assert output.outcome_forecast.roi_pct >= 0.0

    # Governance & quality
    assert 0.0 <= output.quality.decision_reliability <= 1.0
    assert output.quality.degradation_mode == PrescriptiveDegradation.NORMAL


def test_layer8_invariants_enforcement_and_autofix():
    """Verify invariant enforcement detects violations and auto-fixes rates and allocations."""
    l8_input = _build_full_l8_input(audit_grade="B")
    output = run_layer8(l8_input)

    # 1. Clean output has 0 error violations
    violations = enforce_layer8_invariants(output)
    errors = [v for v in violations if v.severity == "error"]
    assert len(errors) == 0

    # 2. Corrupt negative rate -> auto-fixed to 0
    card = next(c for c in output.actions if c.rate is not None)
    card.rate.recommended = -25.0
    v_neg = enforce_layer8_invariants(output)
    assert any(v.check_name == "rate_non_negative" for v in v_neg)
    assert card.rate.recommended == 0.0  # auto-fixed

    # 3. Corrupt rate exceeding max safe limit -> clamped to max_safe
    card.rate.recommended = card.rate.max_safe + 50.0
    v_max = enforce_layer8_invariants(output)
    assert any(v.check_name == "rate_max_safe" for v in v_max)
    assert card.rate.recommended == card.rate.max_safe

    # 4. Corrupt zone allocations summing to > 1.0 -> normalized
    card.zone_allocation = {"zone_north": 0.8, "zone_south": 0.8}  # sum = 1.6
    v_zone = enforce_layer8_invariants(output)
    assert any(v.check_name == "zone_allocation_sum" for v in v_zone)
    assert sum(card.zone_allocation.values()) <= 1.01

    # 5. Blocked action cannot be marked CONFIRMED
    sched = output.schedule[0]
    sched.status = ScheduleStatus.CONFIRMED
    sched.blocked_reasons = ["severe_wind_block"]
    v_blocked = enforce_layer8_invariants(output)
    assert any(v.check_name == "blocked_not_confirmed" for v in v_blocked)
    assert sched.status == ScheduleStatus.BLOCKED


def test_layer8_degradation_modes():
    """Verify graceful degradation across audit grades, conflicts, and missing lineage."""
    # 1. Grade C -> LOW_TRUST
    input_c = _build_full_l8_input(audit_grade="C")
    output_c = run_layer8(input_c)
    assert output_c.quality.degradation_mode == PrescriptiveDegradation.LOW_TRUST

    # 2. Grade D -> VERY_LOW_TRUST
    input_d = _build_full_l8_input(audit_grade="D")
    output_d = run_layer8(input_d)
    assert output_d.quality.degradation_mode == PrescriptiveDegradation.VERY_LOW_TRUST

    # 3. Upstream conflict -> CONFLICT_FLAG
    input_conf = _build_full_l8_input(audit_grade="A", conflicts=[{"source": "L0_conflict"}])
    output_conf = run_layer8(input_conf)
    assert output_conf.quality.degradation_mode == PrescriptiveDegradation.CONFLICT_FLAG

    # 4. Missing species/stage authority -> DATA_GAP
    input_gap = _build_full_l8_input(audit_grade="A", species_allowed=False, stage_allowed=False)
    output_gap = run_layer8(input_gap)
    assert output_gap.quality.degradation_mode == PrescriptiveDegradation.DATA_GAP
