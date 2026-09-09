import pytest
from unittest.mock import patch
from types import SimpleNamespace
from layer5_bio.runner import run_layer5
from layer5_bio.invariants import InvariantViolation
from layer3_decision.schema import DegradationMode


def test_layer5_invariant_error_triggers_degraded_mode():
    """Verify that when invariant errors occur, run_meta.degradation_mode is set to DATA_GAP and penalties applied."""
    tensor = SimpleNamespace(
        run_id="L1-TEST",
        plot_timeseries=[{"date": "2026-04-01", "tmean": 20.0, "rain": 0.0}],
        static={"texture_class": "loam"},
        zones={},
    )
    veg = SimpleNamespace(run_id="L2-TEST", lai=2.0, ndvi_mean=0.6, fvc=0.7)
    decision = SimpleNamespace(run_meta=SimpleNamespace(run_id="L3-TEST"), diagnoses=[])
    nutrient = SimpleNamespace(run_meta=SimpleNamespace(run_id="L4-TEST"))
    context = {"crop": "wheat", "lat": 36.0, "lon": 3.0}

    mock_violations = [
        InvariantViolation("mock_check", "error", "Simulated invariant failure"),
    ]

    with patch("layer5_bio.runner.enforce_layer5_invariants", return_value=mock_violations):
        output = run_layer5(tensor, veg, decision, nutrient, context)

    assert output.run_meta.degradation_mode == DegradationMode.DATA_GAP
    assert any(p.get("driver") == "INVARIANT_VIOLATION" for p in output.quality_metrics.penalties_applied)
