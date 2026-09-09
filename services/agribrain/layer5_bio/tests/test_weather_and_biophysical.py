import pytest
import pandas as pd
from layer5_bio.engines.weather_pressure import (
    _estimate_dew_point_depression,
    _estimate_lwd_hours,
    build_weather_pressure,
)
from layer5_bio.engines.biophysical_engine import (
    BiophysicalCanopyEnergyBalanceSolver,
    run_biophysical_engine,
)
from layer5_bio.weather_risk import weather_risk_engine
from layer5_bio.schema import ThreatId


def test_dew_point_depression_and_lwd_estimation():
    """Verify dew point depression and Leaf Wetness Duration models."""
    # Near saturation (RH = 98%): DPD should be very low (< 0.5°C)
    dpd_wet = _estimate_dew_point_depression(t_air=20.0, rh=98.0)
    assert dpd_wet < 0.5
    lwd_wet = _estimate_lwd_hours(t_air=20.0, rh=98.0, rain_mm=2.0)
    # LWD should be substantial under near saturation + rain
    assert lwd_wet >= 11.0

    # Dry conditions (RH = 40%): DPD should be high (12°C), LWD negligible
    dpd_dry = _estimate_dew_point_depression(t_air=25.0, rh=40.0)
    assert dpd_dry >= 10.0
    lwd_dry = _estimate_lwd_hours(t_air=25.0, rh=40.0, rain_mm=0.0)
    assert lwd_dry <= 1.0


def test_canopy_energy_balance_solver():
    """Verify iterative leaf-level energy balance solving for fluxes and transpiration."""
    solver = BiophysicalCanopyEnergyBalanceSolver()
    
    # Well-watered crop under sunlight
    result = solver.solve(
        t_ambient=22.0,
        rh_ambient=65.0,
        wind_speed=2.0,
        lai=2.5,
        solar_rad=600.0,
        water_stress_prob=0.0,
    )
    
    assert "t_leaf" in result
    assert "rh_leaf" in result
    assert "transpiration_rate_mm_hr" in result
    assert result["transpiration_rate_mm_hr"] > 0.0
    assert result["latent_heat_flux"] > 0.0
    # Inside the canopy, RH should be elevated relative to ambient
    assert result["rh_leaf"] >= 65.0

    # Under severe water stress (stomata closed), transpiration drops
    result_stressed = solver.solve(
        t_ambient=22.0,
        rh_ambient=65.0,
        wind_speed=2.0,
        lai=2.5,
        solar_rad=600.0,
        water_stress_prob=0.9,
    )
    assert result_stressed["transpiration_rate_mm_hr"] < result["transpiration_rate_mm_hr"]
    # Leaf temperature increases due to reduced evaporative cooling
    assert result_stressed["t_leaf"] > result["t_leaf"]


def test_biophysical_spore_dispersal_and_logits():
    """Verify aerodynamic spore release and Cauchy kernel dispersal."""
    ts = [
        {"tmean": 21.0, "tmax": 26.0, "tmin": 16.0, "humidity": 88.0, "rain": 0.0, "wind_speed": 4.5}
        for _ in range(7)
    ]
    res = run_biophysical_engine(
        ts=ts,
        veg_output=None,
        decision_output=None,
        plot_context={"crop": "wheat"},
    )
    
    assert "canopy_microclimate" in res
    assert "spore_release_probability" in res
    assert 0.0 <= res["spore_release_probability"] <= 1.0
    
    logits = res["biophysical_logits"]
    assert ThreatId.FUNGAL_RUST in logits
    assert ThreatId.POWDERY_MILDEW in logits
    assert ThreatId.DOWNY_MILDEW in logits


def test_weather_risk_engine_epidemiology():
    """Verify rule-based disease scoring and spray window feasibility."""
    df_favorable_late_blight = pd.DataFrame([
        {"temp_mean": 18.0, "humidity_max": 95.0, "precip": 10.0, "wind_speed": 5.0}
    ])
    risk = weather_risk_engine.assess_risk(
        weather_history=df_favorable_late_blight,
        gdd_cum=550.0,
        crop_type="tomato",
    )
    
    assert risk["risks"]["late_blight"]["prob"] > 50.0
    assert risk["risks"]["gdd_pest_risk"]["prob"] == 60.0
    # Rain was high (>5mm), so spray window should not be recommended
    assert risk["spray_window"]["recommended"] is False
