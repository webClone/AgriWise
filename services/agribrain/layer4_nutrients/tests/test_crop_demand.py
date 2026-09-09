"""Tests for CropDemandUptakeEngine in Layer 4 Nutrients."""

from layer4_nutrients.crop_demand.engine import CropDemandUptakeEngine
from layer4_nutrients.schema import CropDemandOutput


def test_crop_demand_wheat():
    engine = CropDemandUptakeEngine()
    stages = ["initial"] * 15 + ["vegetative"] * 40 + ["reproductive"] * 30 + ["maturity"] * 25
    output = engine.compute_demand(
        crop_type="wheat",
        management_goal="yield_max",
        stages=stages,
    )
    assert isinstance(output, CropDemandOutput)
    assert output.crop_type == "wheat"
    assert output.yield_target_t_ha > 0.0
    assert output.total_demand["N"] > 0.0
    assert output.total_demand["P"] > 0.0
    assert output.total_demand["K"] > 0.0
    assert output.total_demand["N"] >= 80.0

    cum_n = output.cumulative_uptake["N"]
    assert len(cum_n) == len(stages)
    for i in range(1, len(cum_n)):
        assert cum_n[i] >= cum_n[i - 1]


def test_crop_demand_management_goals_scaling():
    engine = CropDemandUptakeEngine()
    stages = ["vegetative"] * 30 + ["reproductive"] * 30
    out_max = engine.compute_demand(crop_type="corn", management_goal="yield_max", stages=stages)
    out_min = engine.compute_demand(crop_type="corn", management_goal="cost_min", stages=stages)
    out_sust = engine.compute_demand(crop_type="corn", management_goal="sustainable", stages=stages)

    assert out_max.yield_target_t_ha > out_min.yield_target_t_ha
    assert out_min.yield_target_t_ha >= out_sust.yield_target_t_ha
    assert out_max.total_demand["N"] > out_min.total_demand["N"]
