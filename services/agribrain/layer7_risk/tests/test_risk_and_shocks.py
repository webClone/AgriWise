import pytest
from types import SimpleNamespace

from layer7_risk.climate_shock import ClimateShockEngine, climate_engine
from layer7_risk.risk_composite import RiskCompositeEngine


def test_climate_shock_detection():
    """Verify detection of heatwaves, frost, heavy rain, and wind gusts."""
    engine = ClimateShockEngine()

    # 1. Benign weather: no shocks
    benign_forecast = [
        {"temp_max": 25, "temp_min": 15, "precip_mm": 5, "wind_speed": 15}
        for _ in range(7)
    ]
    res_benign = engine.detect_shocks(benign_forecast)
    assert res_benign["shock_prob"] == 0.0
    assert len(res_benign["events"]) == 0
    assert res_benign["is_severe"] is False

    # 2. Extreme heatwave on Day 2 (> 35C)
    heatwave_forecast = [
        {"temp_max": 25, "temp_min": 15, "precip_mm": 0, "wind_speed": 10},
        {"temp_max": 38, "temp_min": 22, "precip_mm": 0, "wind_speed": 15},
    ]
    res_heat = engine.detect_shocks(heatwave_forecast)
    assert res_heat["shock_prob"] >= 80.0
    assert res_heat["is_severe"] is True
    assert any("Heatwave" in e for e in res_heat["events"])

    # 3. Frost event on Day 1 (< 2C)
    frost_forecast = [
        {"temp_max": 10, "temp_min": -1, "precip_mm": 0, "wind_speed": 5},
    ]
    res_frost = engine.detect_shocks(frost_forecast)
    assert res_frost["shock_prob"] >= 90.0
    assert res_frost["is_severe"] is True
    assert any("Frost Risk" in e for e in res_frost["events"])

    # 4. Flood event (> 50mm) and high winds (> 40km/h)
    storm_forecast = [
        {"temp_max": 20, "temp_min": 15, "precip_mm": 65, "wind_speed": 50},
    ]
    res_storm = engine.detect_shocks(storm_forecast)
    assert res_storm["shock_prob"] >= 70.0
    assert any("Heavy Rain" in e for e in res_storm["events"])
    assert any("High Wind" in e for e in res_storm["events"])


def test_risk_composite_default_weights():
    """Verify composite risk calculation under default weights."""
    engine = RiskCompositeEngine()

    res = engine.calculate_composite_risk(
        water_stress_prob=40.0,
        nutrient_stress_prob=30.0,
        disease_risk_prob=20.0,
        climate_shock_prob=10.0,
    )

    # score = 40*0.3 + 30*0.2 + 20*0.3 + 10*0.2 = 12 + 6 + 6 + 2 = 26.0
    assert res["risk_score"] == 26.0
    assert res["risk_level"] == "Low"
    assert "water" in res["components"]
    assert len(res["top_drivers"]) > 0


def test_risk_composite_stage_adaptive_weights():
    """Verify adaptive weight shifting across vegetative vs flowering stages."""
    engine = RiskCompositeEngine()

    # 1. Flowering stage boosts disease risk weight to 0.4 and lowers nutrient to 0.1
    flowering_context = SimpleNamespace(
        stage_specific_allowed=True,
        phenology_posterior_hash="hash_flw_123",
        stage_posterior={"flowering": 0.9, "vegetative": 0.1},
        phenology_stage="flowering",
    )
    res_flw = engine.calculate_composite_risk(
        water_stress_prob=20.0,
        nutrient_stress_prob=20.0,
        disease_risk_prob=80.0,
        climate_shock_prob=10.0,
        semantic_context=flowering_context,
    )
    assert res_flw["weights"]["disease"] > 0.35
    assert res_flw["weights"]["nutrient"] < 0.15
    assert res_flw["risk_score"] > 35.0

    # 2. Vegetative stage boosts water (0.4) and nutrient (0.3)
    veg_context = SimpleNamespace(
        stage_specific_allowed=True,
        phenology_posterior_hash="hash_veg_123",
        stage_posterior={"vegetative": 1.0},
        phenology_stage="vegetative",
    )
    res_veg = engine.calculate_composite_risk(
        water_stress_prob=70.0,
        nutrient_stress_prob=60.0,
        disease_risk_prob=10.0,
        climate_shock_prob=10.0,
        semantic_context=veg_context,
    )
    assert res_veg["weights"]["water"] == 0.4
    assert res_veg["weights"]["nutrient"] == 0.3
    assert res_veg["risk_score"] >= 45.0
    assert res_veg["risk_level"] in ("Moderate", "High")
