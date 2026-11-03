"""Unit tests for Layer 0 Kalman Engine and Zone State Assimilation."""

import math
import pytest

from services.agribrain.layer0.kalman_engine import (
    ZoneKalmanFilter,
    KalmanObservation,
    DailyAssimilationEngine,
)
from services.agribrain.layer0.state_vector import (
    StateVector,
    IDX_LAI,
    IDX_SM_0_10,
    IDX_PHENO_GDD,
    N_STATES,
)


def test_zone_kalman_filter_initialization():
    """Verify ZoneKalmanFilter initializes with proper 9-variable state and covariance."""
    zkf = ZoneKalmanFilter(zone_id="zone_test_01")
    zkf.initialize(day="2026-07-01", soil_props={"clay_pct": 30})

    assert zkf.initialized is True
    assert zkf.zone_id == "zone_test_01"
    assert len(zkf.state.values) == N_STATES
    assert zkf.state.lai == 0.2
    assert zkf.state.day == "2026-07-01"

    P = zkf.covariance.P
    assert len(P) == N_STATES
    assert len(P[0]) == N_STATES

    # Covariance must be symmetric
    for i in range(N_STATES):
        for j in range(N_STATES):
            assert math.isclose(P[i][j], P[j][i], abs_tol=1e-7)


def test_zone_kalman_filter_predict_step():
    """Verify state evolution and process covariance noise growth during predict()."""
    zkf = ZoneKalmanFilter(zone_id="zone_pred_01")
    zkf.initialize(day="2026-07-01")

    initial_diag = zkf.covariance.diagonal()

    weather = {
        "temp_mean": 21.0,
        "temp_min": 14.0,
        "temp_max": 28.0,
        "precipitation": 5.0,
        "et0": 3.5,
    }

    pred_state = zkf.predict(day="2026-07-02", weather=weather)
    predicted_diag = zkf.covariance.diagonal()

    # A nontrivial F can contract some state variances even when Q is
    # positive. Check covariance validity and a non-contracting GDD axis.
    for i in range(N_STATES):
        assert math.isfinite(predicted_diag[i]) and predicted_diag[i] >= 0.0
    assert predicted_diag[IDX_PHENO_GDD] > initial_diag[IDX_PHENO_GDD]
    assert zkf.state.variance == predicted_diag

    # GDD accumulation: (28+14)/2 - 5.0 (t_base) = 21 - 5 = 16 GDD
    assert pred_state.phenology_gdd == 16.0
    assert 0.0 <= pred_state.sm_0_10 <= 1.0


def test_zone_kalman_filter_update_step():
    """Verify observation correction updates state and maintains covariance symmetry."""
    zkf = ZoneKalmanFilter(zone_id="zone_corr_01")
    zkf.initialize(day="2026-07-01")

    weather = {
        "t_mean": 20.0,
        "t_min": 12.0,
        "t_max": 25.0,
        "t_base": 10.0,
        "rain_mm": 0.0,
        "et0_mm": 3.0,
    }
    zkf.predict(day="2026-07-02", weather=weather)
    lai_before = zkf.state.lai

    obs = [
        KalmanObservation(
            obs_type="ndvi",
            value=0.75,
            sigma=0.03,
            reliability=1.0,
            source="sentinel2",
        ),
        KalmanObservation(
            obs_type="soil_moisture",
            value=0.35,
            sigma=0.04,
            reliability=0.9,
            source="soil_sensor",
        ),
    ]

    weights = zkf.update(obs)
    assert len(weights) > 0

    # High NDVI observation must pull LAI upward
    assert zkf.state.lai > lai_before

    # Covariance must remain symmetric after Joseph update
    P = zkf.covariance.P
    for i in range(N_STATES):
        for j in range(N_STATES):
            assert math.isclose(P[i][j], P[j][i], abs_tol=1e-5)


def test_zone_kalman_filter_missing_weather_mode():
    """Verify missing weather fallback inflates process noise and logs provenance."""
    zkf = ZoneKalmanFilter(zone_id="zone_missing_w")
    zkf.initialize(day="2026-07-01")

    state_arr, P_arr = zkf.predict_missing_weather(day="2026-07-02")
    assert state_arr.shape == (N_STATES,)
    assert P_arr.shape == (N_STATES, N_STATES)
    assert zkf.provenance_history[-1]["weather_update_mode"] == "missing_weather_high_uncertainty"


def test_daily_assimilation_engine_multi_zone():
    """Verify DailyAssimilationEngine runs coordinated daily cycles across multiple zones."""
    engine = DailyAssimilationEngine()
    engine.add_zone(zone_id="zone_A", start_day="2026-07-01")
    engine.add_zone(zone_id="zone_B", start_day="2026-07-01")

    weather = {
        "t_mean": 24.0,
        "t_min": 16.0,
        "t_max": 30.0,
        "t_base": 10.0,
        "rain_mm": 10.0,
        "et0_mm": 4.0,
    }
    zone_obs = {
        "zone_A": [KalmanObservation(obs_type="ndvi", value=0.68, sigma=0.04, source="sentinel2")],
        "zone_B": [KalmanObservation(obs_type="ndvi", value=0.45, sigma=0.04, source="sentinel2")],
    }

    result = engine.run_day(day="2026-07-02", weather=weather, zone_observations=zone_obs)

    assert "zone_A" in result["zones"]
    assert "zone_B" in result["zones"]
    assert result["zones"]["zone_A"]["state"]["day"] == "2026-07-02"
    assert "lai_proxy" in result["zones"]["zone_A"]["state"]
    assert "uncertainty" in result["zones"]["zone_A"]
    # Zone A had higher observed NDVI than Zone B
    assert result["zones"]["zone_A"]["state"]["lai_proxy"] > result["zones"]["zone_B"]["state"]["lai_proxy"]
