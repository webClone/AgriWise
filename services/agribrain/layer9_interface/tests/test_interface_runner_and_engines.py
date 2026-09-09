"""
End-to-end and integration tests for Layer 9 Interface Runner and Specialized Engines.
"""
from types import SimpleNamespace
import pytest

from layer9_interface.schema import (
    InterfaceOutput, PhrasingMode, BadgeColor, UserIntent,
)
from layer9_interface.runner import run_layer9


def _build_mock_l8_output(audit_grade="A"):
    quality = SimpleNamespace(
        audit_grade=audit_grade,
        upstream_confidence={"L0": 0.9, "L1": 0.85, "L3": 0.8},
        degradation_mode="NORMAL",
    )
    action = SimpleNamespace(
        action_id="ACT-901",
        action_type=SimpleNamespace(value="IRRIGATE"),
        priority_score=0.88,
        is_allowed=True,
        confidence=SimpleNamespace(value="HIGH"),
        rate=SimpleNamespace(recommended=25.0, unit="mm"),
        zone_targets=["zone_north"],
        zone_allocation={"zone_north": 1.0},
    )
    schedule_item = SimpleNamespace(
        action_id="ACT-901",
        action_type=SimpleNamespace(value="IRRIGATE"),
        scheduled_date="2026-09-12",
        status=SimpleNamespace(value="CONFIRMED"),
        blocking_constraints=[],
        priority_score=0.88,
        weather_ok=True,
        phenology_ok=True,
    )
    zone_plan = {
        "zone_north": [action]
    }
    return SimpleNamespace(
        quality=quality,
        actions=[action],
        schedule=[schedule_item],
        zone_plan=zone_plan,
        outcome_forecast={"yield_delta_pct": 8.5, "roi_pct": 24.0},
    )


def _build_mock_l3_output():
    diag = SimpleNamespace(
        problem_id="WATER_STRESS",
        probability=0.82,
        severity=0.70,
        confidence=0.85,
        affected_area_pct=35.0,
    )
    return SimpleNamespace(diagnoses=[diag])


def test_layer9_runner_end_to_end_confident():
    """Verify full execution of the 15-engine pipeline under Audit Grade A."""
    orch_inputs = {
        "plot_id": "plot_algeria_mitidja",
        "user_query": "Give me an overview of the field status and next recommended actions",
    }
    l8_output = _build_mock_l8_output(audit_grade="A")
    l3_output = _build_mock_l3_output()

    output = run_layer9(orch_inputs, l8_output=l8_output, l3_output=l3_output)

    assert isinstance(output, InterfaceOutput)
    assert output.phrasing_mode == PhrasingMode.CONFIDENT
    assert output.render_hints.badge_color == BadgeColor.GREEN
    assert len(output.summary) > 0
    assert len(output.zone_cards) >= 1
    assert output.zone_cards[0].zone_id == "zone_north"

    # Tasks synchronized from L8 actions
    assert output.task_board is not None
    assert len(output.task_board.tasks) >= 1
    assert any(t.action_type == "IRRIGATE" for t in output.task_board.tasks)

    # Engine trace validation
    trace = getattr(output, "_engine_trace", [])
    assert "context_assembly" in trace
    assert "conversation_memory" in trace
    assert "intent_router" in trace
    assert "policy_enforcer" in trace
    assert "advisory" in trace
    assert "telemetry" in trace


def test_layer9_runner_degradation_modes():
    """Verify phrasing mode and disclaimers under lower audit grades."""
    orch_inputs = {"plot_id": "plot_degraded", "user_query": "How is the crop looking?"}
    l3_output = _build_mock_l3_output()

    # 1. Grade C -> HEDGED phrasing + YELLOW badge + disclaimers
    l8_c = _build_mock_l8_output(audit_grade="C")
    output_c = run_layer9(orch_inputs, l8_output=l8_c, l3_output=l3_output)
    assert output_c.phrasing_mode == PhrasingMode.HEDGED
    assert output_c.render_hints.badge_color == BadgeColor.YELLOW
    assert len(output_c.disclaimers) > 0

    # 2. Grade D -> RESTRICTED phrasing + RED badge + disclaimers
    l8_d = _build_mock_l8_output(audit_grade="D")
    output_d = run_layer9(orch_inputs, l8_output=l8_d, l3_output=l3_output)
    assert output_d.phrasing_mode == PhrasingMode.RESTRICTED
    assert output_d.render_hints.badge_color == BadgeColor.RED
    assert len(output_d.disclaimers) > 0


def test_layer9_runner_specialized_intents():
    """Verify dispatch to specialized engines (Report and Spatial Narrator)."""
    l8_output = _build_mock_l8_output(audit_grade="B")
    l3_output = _build_mock_l3_output()

    # 1. Report intent
    orch_report = {
        "plot_id": "plot_report_test",
        "user_query": "Please generate a seasonal agronomic report for this plot",
    }
    output_report = run_layer9(orch_report, l8_output=l8_output, l3_output=l3_output)
    trace_report = getattr(output_report, "_engine_trace", [])
    assert "report" in trace_report

    # 2. Spatial intent
    orch_spatial = {
        "plot_id": "plot_spatial_test",
        "user_query": "Show me the spatial zone plan and variability across management zones",
    }
    output_spatial = run_layer9(orch_spatial, l8_output=l8_output, l3_output=l3_output)
    trace_spatial = getattr(output_spatial, "_engine_trace", [])
    assert "spatial_narrator" in trace_spatial
