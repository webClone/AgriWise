from datetime import datetime, timedelta
from types import SimpleNamespace
import pytest

from layer7_risk.scenario_simulator import ScenarioSimulator, scenario_engine
from layer7_risk.trust_monitor import TrustMonitor, trust_monitor


def test_scenario_simulator_interventions():
    """Verify causal what-if interventions (irrigate, fertilize, fungicide)."""
    sim = ScenarioSimulator()

    baseline = {
        "water_loss_factor": 0.40,
        "nutrient_loss_factor": 0.30,
        "disease_loss_factor": 0.20,
    }
    yield_pot = 10.0  # 10 t/ha
    price = 300.0     # $300/ton

    # 1. Irrigation intervention
    res_irr = sim.simulate_intervention(baseline, "irrigate", yield_pot, price)
    assert res_irr["scenario"] == "irrigate"
    assert res_irr["new_yield_t_ha"] > 0
    assert res_irr["yield_delta"] > 0
    assert res_irr["profit_delta_usd"] > 0
    assert res_irr["roi_pct"] > 0

    # 2. Fertilization intervention
    res_fert = sim.simulate_intervention(baseline, "fertilize", yield_pot, price)
    assert res_fert["scenario"] == "fertilize"
    assert res_fert["yield_delta"] > 0

    # 3. Fungicide intervention
    res_fung = sim.simulate_intervention(baseline, "fungicide", yield_pot, price)
    assert res_fung["scenario"] == "fungicide"
    assert res_fung["yield_delta"] > 0


def test_trust_monitor_freshness_and_telemetry_health():
    """Verify trust score computation based on data latency and sensor health."""
    mon = TrustMonitor()
    now = datetime.now()

    # 1. Optimal conditions: recent satellite (2 days ago), active sensors, forecast present
    res_opt = mon.evaluate_trust(
        last_satellite_date=now - timedelta(days=2),
        sensor_active=True,
        forecast_available=True,
    )
    assert res_opt["trust_score"] == 100
    assert res_opt["trust_level"] == "High"
    assert len(res_opt["issues"]) == 0

    # 2. Moderate latency: 7 days since satellite image (-10)
    res_mod = mon.evaluate_trust(
        last_satellite_date=now - timedelta(days=7),
        sensor_active=True,
        forecast_available=True,
    )
    assert res_mod["trust_score"] == 90
    assert res_mod["trust_level"] == "High"

    # 3. Severe gap: 14 days since satellite (-30), no sensor (-20), no forecast (-20)
    res_bad = mon.evaluate_trust(
        last_satellite_date=now - timedelta(days=14),
        sensor_active=False,
        forecast_available=False,
    )
    # 100 - 30 - 20 - 20 = 30
    assert res_bad["trust_score"] == 30
    assert res_bad["trust_level"] == "Low"
    assert len(res_bad["issues"]) >= 3


def test_trust_monitor_cross_layer_conflict():
    """Verify detection of cross-layer contradictions between ASMAE and physical sensors."""
    mon = TrustMonitor()

    # 1. No ASMAE features -> no conflict
    res_empty = mon.evaluate_cross_layer_conflict({}, {})
    assert res_empty["conflict_score"] == 0.0
    assert res_empty["agreement"] is True

    # 2. Water contradiction: high soil moisture with high ASMAE canopy water stress
    asmae_water = {"ASMAE_CANOPY_WATER": SimpleNamespace(value=0.85)}
    sensor_moisture = {"soil_moisture_vwc": 0.35}
    res_water = mon.evaluate_cross_layer_conflict(asmae_water, sensor_moisture)
    assert res_water["conflict_score"] >= 0.4
    assert any("water_conflict" in r for r in res_water["reasons"])

    # 3. Salinity contradiction: low EC with high ASMAE salinity
    asmae_sal = {"ASMAE_SALINITY_STRESS": SimpleNamespace(value=0.80)}
    sensor_ec = {"ec_ds_m": 0.5}
    res_sal = mon.evaluate_cross_layer_conflict(asmae_sal, sensor_ec)
    assert res_sal["conflict_score"] >= 0.5
    assert res_sal["agreement"] is False
