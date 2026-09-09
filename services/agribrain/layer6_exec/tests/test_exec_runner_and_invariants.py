import pytest
from types import SimpleNamespace
from layer6_exec.schema import (
    Layer6Input,
    OperationalContext,
    ExecutionState,
    TaskStatus,
)
from layer6_exec.runner import run_layer6, run_layer6_exec
from layer6_exec.invariants import enforce_layer6_invariants


@pytest.fixture
def baseline_l6_inputs():
    timeseries = [
        {
            "date": f"2026-04-{i:02d}",
            "temp": 21.0,
            "humidity": 65.0,
            "wind_speed": 2.5,
            "wind_dir": 180.0,
            "precip": 1.0 if i == 4 else 0.0,
            "soil_temp": 18.0,
            "soil_moisture": 0.45,
        }
        for i in range(1, 8)
    ]
    tensor = SimpleNamespace(
        plot_id="PLOT-L6-TEST",
        plot_timeseries=timeseries,
        forecast_7d=[{"precip": 0.0} for _ in range(7)],
    )
    veg = SimpleNamespace(
        ndvi_current=0.70,
        canopy_cover_pct=70.0,
        growth_velocity=0.015,
        phenology_stage="VEGETATIVE",
    )
    decision = SimpleNamespace(
        run_meta=SimpleNamespace(run_id="L3-TEST-001"),
        diagnoses=[],
        execution_plan=SimpleNamespace(tasks=[]),
    )
    nutrient = SimpleNamespace(
        run_meta=SimpleNamespace(run_id="L4-TEST-001"),
        verification_plan=SimpleNamespace(tasks=[]),
    )
    bio = SimpleNamespace(
        run_meta=SimpleNamespace(run_id="L5-TEST-001"),
        execution_plan=SimpleNamespace(tasks=[]),
    )
    op = OperationalContext(
        equipment_ids=["TRACTOR_1", "PIVOT_A"],
        workforce_available=True,
        labor_hours_available=60.0,
        water_quota_remaining=1200.0,
        budget_remaining=5000.0,
        plot_area_ha=12.5,
    )
    return Layer6Input(
        tensor=tensor,
        veg_int=veg,
        decision_l3=decision,
        nutrient_l4=nutrient,
        bio_l5=bio,
        op_context=op,
        evidence_batch=[],
        current_state=ExecutionState(tasks={}, logs=[], last_updated=""),
    )


def test_layer6_end_to_end_execution(baseline_l6_inputs):
    """Verify end-to-end execution of Layer 6, checking run_id and zero invariant errors."""
    output = run_layer6(baseline_l6_inputs)

    # 1. Metadata and Hash
    assert output.run_meta.layer == "L6"
    assert output.run_meta.run_id.startswith("L6-")
    assert output.content_hash() != ""

    # 2. Biophysical & Environmental Solvers
    assert 0.0 <= output.nitrogen_leaching_fraction <= 1.0
    assert output.vapor_pressure_deficit_kpa > 0.0
    assert isinstance(output.net_carbon_balance_t_co2eq, float)
    assert isinstance(output.carbon_valuation_impact_eur, float)

    # 3. Execution State & Portfolio
    assert isinstance(output.updated_state.tasks, dict)
    for c in output.intervention_portfolio:
        assert c.utility_score >= 0.0

    # 4. Invariant Enforcement
    violations = enforce_layer6_invariants(output)
    errors = [v for v in violations if v.severity == "error"]
    assert len(errors) == 0, f"Layer 6 invariant errors found: {errors}"


def test_layer6_deterministic_run_id(baseline_l6_inputs):
    """Verify that identical inputs generate bit-for-bit identical run_ids."""
    out1 = run_layer6(baseline_l6_inputs)
    out2 = run_layer6(baseline_l6_inputs)
    assert out1.run_meta.run_id == out2.run_meta.run_id
