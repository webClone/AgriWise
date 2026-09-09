"""Tests for Layer 4 Runner Standalone Execution."""

from layer4_nutrients.runner import run_layer4_standalone
from layer4_nutrients.schema import NutrientIntelligenceOutput


def _dummy_weather(n_days: int = 30):
    return [
        {
            "t_max": 25.0,
            "t_min": 14.0,
            "rain_mm": 0.0,
            "et0": 4.5,
            "vpd_kpa": 1.5,
        }
        for _ in range(n_days)
    ]


def test_layer4_standalone_wheat_baseline():
    output = run_layer4_standalone(
        plot_id="plot-l4-test-1",
        crop_type="wheat",
        management_goal="yield_max",
        irrigation_type="rainfed",
        planting_date="2025-11-15",
        daily_weather=_dummy_weather(30),
        soil_props={
            "soil_texture": "clay_loam",
            "ph": 6.8,
            "som_pct": 2.2,
            "soil_n_ppm": 18.0,
            "soil_p_ppm": 22.0,
            "soil_k_ppm": 180.0,
        },
        ndvi=0.65,
        ndre=0.35,
        stages=["initial"] * 10 + ["vegetative"] * 10 + ["reproductive"] * 5 + ["maturity"] * 5,
    )
    assert isinstance(output, NutrientIntelligenceOutput)
    assert output.run_meta.layer == "L4"
    assert output.run_meta.run_id.startswith("L4-")

    # Verify budgets and plan
    assert output.nutrient_budgets is not None
    assert output.prescriptions is not None
    assert isinstance(output.prescriptions, list)
    assert output.quality_metrics.decision_reliability > 0.0


def test_layer4_standalone_deterministic_run_id():
    out1 = run_layer4_standalone(
        plot_id="plot-det",
        crop_type="corn",
        l3_run_id="L3-DET",
        management_goal="yield_max",
        daily_weather=_dummy_weather(20),
    )
    out2 = run_layer4_standalone(
        plot_id="plot-det",
        crop_type="corn",
        l3_run_id="L3-DET",
        management_goal="yield_max",
        daily_weather=_dummy_weather(20),
    )
    assert out1.run_meta.run_id == out2.run_meta.run_id
