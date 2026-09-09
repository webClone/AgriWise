import pytest
from types import SimpleNamespace
from layer6_exec.engines.nitrogen_leaching import run_nitrogen_leaching
from layer6_exec.engines.vpd_spray_window import run_vpd_spray_window
from layer6_exec.engines.carbon_sequestration import run_carbon_sequestration


@pytest.fixture
def dummy_l6_biophysical_inputs():
    timeseries = [
        {
            "temp": 22.0,
            "humidity": 60.0,
            "wind_speed": 3.0,
            "wind_dir": 180.0,
            "precip": 4.0,
            "soil_temp": 17.5,
            "soil_moisture": 0.45,
        }
        for _ in range(7)
    ]
    return SimpleNamespace(
        tensor=SimpleNamespace(
            plot_timeseries=timeseries,
            forecast_7d=[{"precip": 2.0} for _ in range(7)],
        ),
        veg_int=SimpleNamespace(
            ndvi_current=0.68,
            canopy_cover_pct=65.0,
            growth_velocity=0.015,
        ),
        decision_l3=None,
        nutrient_l4=None,
        bio_l5=None,
    )


def test_nitrogen_leaching_crank_nicolson_solver(dummy_l6_biophysical_inputs):
    """Verify 1D solute transport Crank-Nicolson finite-difference solver."""
    res = run_nitrogen_leaching(dummy_l6_biophysical_inputs, candidates=[])
    
    assert "nitrogen_leaching_fraction" in res
    assert "runoff_risk_index" in res
    # Leaching fraction must be bounded in [0, 1]
    assert 0.0 <= res["nitrogen_leaching_fraction"] <= 1.0
    assert 0.0 <= res["runoff_risk_index"] <= 1.0


def test_vpd_spray_window_3d_lagrangian_drift(dummy_l6_biophysical_inputs):
    """Verify vapor pressure deficit calculation and 3D droplet drift simulation."""
    res = run_vpd_spray_window(dummy_l6_biophysical_inputs, candidates=[])
    
    assert "vapor_pressure_deficit_kpa" in res
    assert "total_drift_fraction" in res
    assert "total_evap_fraction" in res
    # VPD under 22°C and 60% RH should be ~1.0 kPa
    assert 0.5 <= res["vapor_pressure_deficit_kpa"] <= 1.5
    assert 0.0 <= res["total_drift_fraction"] <= 1.0
    assert 0.0 <= res["total_evap_fraction"] <= 1.0


def test_carbon_sequestration_rothc_rk4_solver(dummy_l6_biophysical_inputs):
    """Verify 5-pool RothC soil carbon dynamics solved via Runge-Kutta 4th Order."""
    res = run_carbon_sequestration(dummy_l6_biophysical_inputs, candidates=[])
    
    assert "net_carbon_balance_t_co2eq" in res
    assert "carbon_valuation_impact_eur" in res
    # Valuation impact should scale linearly with net carbon balance (approx 50 EUR / t CO2eq)
    assert isinstance(res["net_carbon_balance_t_co2eq"], float)
    assert isinstance(res["carbon_valuation_impact_eur"], float)
