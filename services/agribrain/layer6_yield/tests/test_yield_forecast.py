import pytest
from layer6_yield.yield_forecast import YieldForecastEngine


def test_yield_forecast_potential_and_stress_reduction():
    """Verify hybrid yield prediction: potential yield and stress penalties."""
    engine = YieldForecastEngine()
    
    # 1. Zero stress: full potential yield
    res_ideal = engine.predict_yield(
        crop_type="wheat",
        final_biomass_kg_ha=10000.0,
        cumulative_stress={
            "water_loss_factor": 0.0,
            "nutrient_loss_factor": 0.0,
            "disease_loss_factor": 0.0,
        },
    )
    
    assert "yield_mean_t_ha" in res_ideal
    assert res_ideal["yield_mean_t_ha"] > 0.0
    assert "yield_p10" in res_ideal
    assert "yield_p90" in res_ideal
    # p10 <= mean <= p90
    assert res_ideal["yield_p10"] <= res_ideal["yield_mean_t_ha"] <= res_ideal["yield_p90"]

    # 2. Moderate water stress (30% loss)
    res_stressed = engine.predict_yield(
        crop_type="wheat",
        final_biomass_kg_ha=10000.0,
        cumulative_stress={
            "water_loss_factor": 0.30,
            "nutrient_loss_factor": 0.0,
            "disease_loss_factor": 0.0,
        },
    )
    assert res_stressed["yield_mean_t_ha"] < res_ideal["yield_mean_t_ha"]
    assert res_stressed["attribution"]["water"] > 0.0


def test_yield_forecast_loss_capping():
    """Verify that cumulative stress losses are capped at 70% to prevent absurd drops."""
    engine = YieldForecastEngine()
    
    # Catastrophic individual losses (90% water, 90% nutrient, 90% disease)
    res_capped = engine.predict_yield(
        crop_type="wheat",
        final_biomass_kg_ha=10000.0,
        cumulative_stress={
            "water_loss_factor": 0.90,
            "nutrient_loss_factor": 0.90,
            "disease_loss_factor": 0.90,
        },
    )
    
    # Yield reduction factor should not drop below 0.30 (70% max loss)
    assert res_capped["reduction_factor"] == 0.30
