"""L0-C1 bounded fail-closed scientific-export + grid-coverage tests.

These tests use an isolated deterministic engine fixture; they are NOT a
field-calibration, real-provider or end-to-end Layer 1 acceptance gate.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from services.agribrain.layer0.invariants import enforce_all_invariants
from services.agribrain.layer0.plot_grid import PlotGrid
from services.agribrain.layer0.scientific_integrity_gate import (
    Layer0ScientificIntegrityError,
    assert_layer0_scientific_integrity,
    assert_structural_audit_passed,
)
from services.agribrain.layer0.state_engine import Layer0StateEngine


def fixture_state():
    states = {"plot": [
        {"day": "2026-11-01", "lai_proxy": 0.2, "sm_0_10": 0.3},
        {"day": "2026-11-02", "lai_proxy": 0.3, "sm_0_10": 0.35},
    ]}
    uncertainty = {"plot": [
        {"day": "2026-11-01", "lai_proxy": 0.15, "sm_0_10": 0.1},
        {"day": "2026-11-02", "lai_proxy": 0.18, "sm_0_10": 0.12},
    ]}
    provenance = [{"day": "2026-11-02", "zones": {
        "plot": {"state": states["plot"][1], "provenance": {"n_obs": 0}}
    }}]
    return states, uncertainty, provenance


def verify(states=None, uncertainty=None, provenance=None, checker=None):
    source_state, source_uncertainty, source_provenance = fixture_state()
    return assert_layer0_scientific_integrity(
        daily_state=states if states is not None else source_state,
        state_uncertainty=uncertainty if uncertainty is not None else source_uncertainty,
        provenance_log=provenance if provenance is not None else source_provenance,
        source_reliability={},
        enforce_invariants=checker if checker is not None else enforce_all_invariants,
    )


def test_real_native_invariant_enforcer_runs_without_silent_autofix():
    states, _, _ = fixture_state()
    assert verify() == []
    states["plot"][1]["lai_proxy"] = 12.0
    with pytest.raises(Layer0ScientificIntegrityError, match="layer0_scientific_invariant_violation"):
        verify(states=states)
    assert states["plot"][1]["lai_proxy"] == 12.0, "must NOT auto-clamp invalid scientific evidence"


@pytest.mark.parametrize("field", ["state", "uncertainty"])
def test_nonfinite_export_blocks_handoff(field):
    s, u, _ = fixture_state()
    target = s if field == "state" else u
    target["plot"][1]["sm_0_10"] = float("nan")
    with pytest.raises(Layer0ScientificIntegrityError, match="layer0_nonfinite_" + field):
        verify(states=s, uncertainty=u)


def test_negative_sigma_fails_closed_even_when_native_enforcer_would_not():
    s, u, _ = fixture_state()
    u["plot"][1]["sm_0_10"] = -0.2
    with pytest.raises(Layer0ScientificIntegrityError, match="layer0_negative_uncertainty"):
        verify(states=s, uncertainty=u)


def test_wrong_uncertainty_day_denies_trusted_state():
    s, u, _ = fixture_state()
    u["plot"][1]["day"] = "2026-11-03"
    with pytest.raises(Layer0ScientificIntegrityError, match="layer0_uncertainty_day_mismatch"):
        verify(states=s, uncertainty=u)


def test_invariant_checker_exception_is_fatal():
    def throws(*_args, **_kwargs):
        raise OSError("fake checker unavailable")
    with pytest.raises(Layer0ScientificIntegrityError, match="layer0_invariant_checker_failed"):
        verify(checker=throws)


def test_audit_result_must_explicitly_pass():
    assert_structural_audit_passed({"structural_audit": {
        "status": "PASS", "checks_run": 5, "checks_failed": 0,
    }})
    for data in (None, {}, {"structural_audit": {}}, {
        "structural_audit": {"status": "DEGRADED", "checks_run": 5, "checks_failed": 1},
    }):
        with pytest.raises(Layer0ScientificIntegrityError):
            assert_structural_audit_passed(data)


def make_engine(monkeypatch):
    e = Layer0StateEngine()
    assert e._has_kalman, "fixture requires the actual Layer 0 engine installed"
    states, uncertainty, provenance = fixture_state()

    class IsolatedAssimilator:
        def __init__(self):
            self.filters = {}

        def add_zone(self, zone, soil_props=None, start_day=""):
            self.filters[zone] = type("MockFilter", (), {})()

        def run_period(self, *_args):
            pass

        def to_field_tensor_outputs(self):
            return deepcopy(states), deepcopy(uncertainty), deepcopy(provenance)

    class Validation:
        source_reliability = {}
        def validate_day(self, *_args):
            return None
        def get_conflict_summary(self, **_kwargs):
            return []

    monkeypatch.setattr(e, "_DailyAssimilationEngine", IsolatedAssimilator)
    monkeypatch.setattr(e, "_ValidationGraph", Validation)
    monkeypatch.setattr(e, "_layer0_audit", lambda **_kwargs: {
        "structural_audit": {"status": "PASS", "checks_run": 4, "checks_failed": 0},
        "trust_report": {"health_grade": "A"},
    })
    return e


def execute(engine):
    return engine.run(
        plot_id="plot-c1", start_date="2026-11-02", end_date="2026-11-02",
        daily_weather={"2026-11-02": {
            "temp_max": 23.0, "temp_min": 11.0,
            "precipitation": 0.0, "et0": 2.0,
        }},
        observations_by_day={}, events_by_day={},
        geometry_hash="isolated-geometry", geometry_version=1,
        run_timestamp=datetime(2026, 11, 3, tzinfo=timezone.utc),
    )


def test_engine_marks_success_as_scientifically_admissible_only_after_both_gates(monkeypatch):
    result = execute(make_engine(monkeypatch))
    assert result.health_report["scientific_state_admissible"] is True
    assert result.health_report["invariant_decisions"] == []
    assert result.provenance["scientific_state_integrity"] == "PASSED_RUNTIME_BOUNDARY"
    assert result.scientific_publication_authorized is False
    assert result.actuator_control_authorized is False


def test_validation_exception_prevents_layer1_state_packet(monkeypatch):
    engine = make_engine(monkeypatch)
    class BrokenValidation:
        def validate_day(self, *_args):
            raise RuntimeError("qualification graph unavailable")
    monkeypatch.setattr(engine, "_ValidationGraph", BrokenValidation)
    with pytest.raises(Layer0ScientificIntegrityError, match="layer0_cross_source_validation_failed"):
        execute(engine)


def test_self_audit_exception_prevents_layer1_state_packet(monkeypatch):
    engine = make_engine(monkeypatch)
    def fails(**_kwargs):
        raise RuntimeError("audit unavailable")
    monkeypatch.setattr(engine, "_layer0_audit", fails)
    with pytest.raises(Layer0ScientificIntegrityError, match="layer0_structural_audit_execution_failed"):
        execute(engine)


def test_structural_audit_failure_prevents_layer1_state_packet(monkeypatch):
    engine = make_engine(monkeypatch)
    monkeypatch.setattr(engine, "_layer0_audit", lambda **_kwargs: {
        "structural_audit": {"status": "DEGRADED", "checks_run": 4, "checks_failed": 1},
    })
    with pytest.raises(Layer0ScientificIntegrityError, match="layer0_structural_audit_failed"):
        execute(engine)


def test_oversized_plot_rejected_before_any_partial_grid_is_built(monkeypatch):
    # > 5 km east-west near Blida, Algeria: old implementation silently
    # clipped to 500 pixels and falsely returned a normal grid.
    coords = [[2.7, 36.4], [2.77, 36.4], [2.77, 36.405], [2.7, 36.405]]
    monkeypatch.setattr(
        PlotGrid, "_compute_alpha_mask",
        classmethod(lambda *_a, **_k: pytest.fail("must reject before rasterization")),
    )
    with pytest.raises(ValueError, match="plot_grid_full_coverage_exceeds_single_grid_limit"):
        PlotGrid.from_polygon_wgs84(coords)


def test_small_plot_can_still_generate_full_grid():
    coords = [[2.7, 36.4], [2.7004, 36.4], [2.7004, 36.4004], [2.7, 36.4004]]
    grid = PlotGrid.from_polygon_wgs84(coords)
    assert 0 < grid.width <= 500
    assert 0 < grid.height <= 500
    assert len(grid.alpha) == grid.height
    assert all(len(row) == grid.width for row in grid.alpha)
