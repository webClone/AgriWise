"""Tests for Layer 8 InterventionScenarioCandidate and typed counterfactual contracts."""

from types import SimpleNamespace
import pytest

from services.agribrain.layer8_prescriptive.scenario_contract import (
    InterventionScenarioCandidate,
    ScenarioType,
)


def test_intervention_scenario_candidate_creation():
    candidate = InterventionScenarioCandidate(
        scenario_id="SCN-IRR-001",
        scenario_type=ScenarioType.IRRIGATION_INTERVENTION,
        action_type="IRRIGATE_VARIABLE_RATE",
        assumed_state={"root_zone_vwc": 0.18, "depletion_mm": 25.0},
        weather_scenario={"forecast_rain_mm": 0.0, "et0_mm_day": 4.5},
        management_params={"volume_mm": 25.0, "application_method": "DRIP"},
        expected_outcomes={"stress_reduction_pct": 85.0, "yield_protection_pct": 12.0},
        constraints={"flow_rate_limit_l_hr": 1200.0},
        uncertainty={"outcome_sigma": 0.05},
        is_reversible=False,
        required_evidence=("soil_moisture_sensor", "weather_forecast"),
        validity_domain={"soil_type": "loam", "crop_stage": "vegetative"},
    )

    assert candidate.scenario_id == "SCN-IRR-001"
    assert candidate.scenario_type == ScenarioType.IRRIGATION_INTERVENTION
    assert candidate.action_type == "IRRIGATE_VARIABLE_RATE"
    assert candidate.is_reversible is False

    d = candidate.to_dict()
    assert d["scenario_id"] == "SCN-IRR-001"
    assert d["scenario_type"] == "IRRIGATION_INTERVENTION"
    assert d["management_params"]["volume_mm"] == 25.0


def test_from_crop_planning_option_conversion():
    l7_option = SimpleNamespace(
        option_id="WHEAT_SPRING_2026",
        crop_type="Spring Wheat",
        expected_yield=4.8,
    )

    candidate = InterventionScenarioCandidate.from_crop_planning_option(l7_option, index=1)
    assert candidate.scenario_id == "SCN-CROP-WHEAT_SPRING_2026"
    assert candidate.scenario_type == ScenarioType.CROP_SELECTION
    assert candidate.action_type == "SELECT_CROP_ROTATION"
    assert candidate.assumed_state["target_crop"] == "Spring Wheat"
    assert candidate.expected_outcomes["expected_yield_relative"] == 4.8
    assert "crop_history" in candidate.required_evidence
