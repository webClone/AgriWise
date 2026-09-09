import pytest
from types import SimpleNamespace
from layer5_bio.runner import run_layer5
from layer5_bio.invariants import enforce_layer5_invariants
from layer5_bio.schema import ThreatId, ActionId, Severity


@pytest.fixture
def baseline_l5_inputs():
    timeseries = [
        {
            "date": f"2026-04-{i:02d}",
            "tmean": 21.0,
            "tmax": 26.0,
            "tmin": 16.0,
            "humidity": 78.0,
            "rain": 1.5 if i == 5 else 0.0,
            "wind_speed": 2.5,
        }
        for i in range(1, 8)
    ]
    tensor = SimpleNamespace(
        run_id="L1-TEST-001",
        plot_timeseries=timeseries,
        static={"texture_class": "clay_loam", "soil_clay": 28.0},
        zones={"Zone A": {"area_pct": 0.5}, "Zone B": {"area_pct": 0.5}},
    )
    veg = SimpleNamespace(
        run_id="L2-TEST-001",
        lai=2.8,
        ndvi_mean=0.72,
        fvc=0.80,
    )
    decision = SimpleNamespace(
        run_meta=SimpleNamespace(run_id="L3-TEST-001"),
        diagnoses=[],
    )
    nutrient = SimpleNamespace(
        run_meta=SimpleNamespace(run_id="L4-TEST-001"),
    )
    context = {
        "crop": "wheat",
        "crop_type": "wheat",
        "declared_crop_type": "wheat",
        "variety": "giza 168",
        "lat": 36.75,
        "lon": 3.05,
        "phenology_stage": "VEGETATIVE",
        "applied_chemicals": [
            {"chemical_id": "azoxystrobin", "days_ago": 5}
        ],
    }
    return tensor, veg, decision, nutrient, context


def test_layer5_end_to_end_execution(baseline_l5_inputs):
    """Verify end-to-end execution of run_layer5, checking output structure and invariants."""
    tensor, veg, decision, nutrient, context = baseline_l5_inputs
    output = run_layer5(
        field_tensor=tensor,
        veg_output=veg,
        decision_output=decision,
        nutrient_output=nutrient,
        plot_context=context,
    )

    # 1. Run Metadata
    assert output.run_meta.layer == "L5"
    assert output.run_meta.run_id.startswith("L5-")
    assert output.run_meta.parent_run_ids["L1"] == "L1-TEST-001"
    assert output.run_meta.parent_run_ids["L2"] == "L2-TEST-001"

    # 2. Threat States
    assert len(output.threat_states) >= 9
    for tid_str, state in output.threat_states.items():
        assert 0.0 <= state.probability <= 1.0
        assert 0.0 <= state.confidence <= 1.0
        assert isinstance(state.severity, Severity)

    # 3. Recommendations & Execution Plan
    assert isinstance(output.recommendations, list)
    if output.execution_plan:
        for task in output.execution_plan.tasks:
            assert task.task_id != ""

    # 4. Quality Metrics & Invariants
    assert 0.0 <= output.quality_metrics.decision_reliability <= 1.0
    violations = enforce_layer5_invariants(output)
    errors = [v for v in violations if v.severity == "error"]
    assert len(errors) == 0, f"Invariant errors found: {errors}"


def test_layer5_deterministic_run_id(baseline_l5_inputs):
    """Verify that identical inputs produce bit-for-bit identical run_ids."""
    tensor, veg, decision, nutrient, context = baseline_l5_inputs
    out1 = run_layer5(tensor, veg, decision, nutrient, context)
    out2 = run_layer5(tensor, veg, decision, nutrient, context)
    assert out1.run_meta.run_id == out2.run_meta.run_id
