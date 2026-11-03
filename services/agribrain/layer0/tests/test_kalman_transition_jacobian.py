"""L0-02B: dynamic transition Jacobian and covariance propagation contracts.

These tests verify software consistency with the current piecewise ProcessModel.
They do not validate the biological realism or calibration of that process model.
"""
import math

import pytest

from services.agribrain.layer0.kalman_engine import ZoneKalmanFilter
from services.agribrain.layer0.state_vector import (
    N_STATES, StateCovariance, StateVector, ProcessModel,
    IDX_LAI, IDX_BIOMASS, IDX_CANOPY_STRESS,
    IDX_PHENO_GDD, IDX_PHENO_STAGE, IDX_SM_0_10,
)


WEATHER = {
    "temp_max": 25.0, "temp_min": 15.0,
    "precipitation": 0.0, "et0": 3.0,
}


def test_full_covariance_propagation_matches_small_matrix_reference():
    cov = StateCovariance.from_diagonal([1.0] * N_STATES)
    F = [[float(i == j) for j in range(N_STATES)] for i in range(N_STATES)]
    F[IDX_BIOMASS][IDX_LAI] = 0.3
    cov.propagate(F, [0.01] * N_STATES)

    assert cov.P[IDX_BIOMASS][IDX_BIOMASS] == pytest.approx(1.10)
    assert cov.P[IDX_LAI][IDX_BIOMASS] == pytest.approx(0.3)
    assert cov.P[IDX_BIOMASS][IDX_LAI] == pytest.approx(0.3)
    assert cov.P[IDX_LAI][IDX_LAI] == pytest.approx(1.01)


def test_local_jacobian_captures_lai_biomass_stress_and_gdd_dependencies():
    process = ProcessModel()
    prior = StateVector.initial("2026-11-01")
    nominal, _ = process.predict(prior, WEATHER)
    F = process.transition_jacobian(prior, WEATHER, predicted_state=nominal)

    assert len(F) == N_STATES
    assert all(len(row) == N_STATES for row in F)
    assert F[IDX_BIOMASS][IDX_LAI] > 0.2
    assert F[IDX_BIOMASS][IDX_BIOMASS] == pytest.approx(0.7, abs=1e-6)
    assert F[IDX_LAI][IDX_CANOPY_STRESS] < 0.0
    assert F[IDX_PHENO_GDD][IDX_PHENO_GDD] == pytest.approx(1.0, abs=1e-6)


def test_predict_creates_cross_state_covariance_and_syncs_state_variance():
    filt = ZoneKalmanFilter("plot")
    filt.initialize("2026-11-01")
    initial = [row[:] for row in filt.covariance.P]
    assert initial[IDX_BIOMASS][IDX_LAI] == 0.0

    predicted = filt.predict("2026-11-02", WEATHER)
    P = filt.covariance.P

    assert abs(P[IDX_BIOMASS][IDX_LAI]) > 1e-4
    assert P[IDX_BIOMASS][IDX_LAI] == pytest.approx(P[IDX_LAI][IDX_BIOMASS])
    assert predicted.variance == pytest.approx(filt.covariance.diagonal())
    assert all(math.isfinite(P[i][i]) and P[i][i] >= 0 for i in range(N_STATES))

    # FPFt + Q is PSD whenever the prior P and Q are PSD. Check several
    # quadratic forms, not merely the diagonal or matrix symmetry.
    for sign in (-1.0, 1.0):
        for i in range(N_STATES):
            for j in range(i + 1, N_STATES):
                v = [0.0] * N_STATES
                v[i], v[j] = 1.0, sign
                quadratic = sum(v[k] * P[k][m] * v[m]
                                for k in range(N_STATES) for m in range(N_STATES))
                assert quadratic >= -1e-10


def test_irrigation_regime_affects_moisture_jacobian():
    process = ProcessModel()
    prior = StateVector.initial("2026-11-01")
    prior.values[IDX_SM_0_10] = 0.1

    dry = process.transition_jacobian(prior, WEATHER)
    irrigated = process.transition_jacobian(
        prior, WEATHER, [{"event_type": "irrigation", "amount_mm": 30.0}]
    )
    assert dry[IDX_SM_0_10][IDX_SM_0_10] > 0.9
    assert irrigated[IDX_SM_0_10][IDX_SM_0_10] == pytest.approx(0.0, abs=1e-6)


def test_bad_process_noise_is_rejected_without_mutating_covariance():
    cov = StateCovariance.from_diagonal([0.1] * N_STATES)
    before = [row[:] for row in cov.P]
    I = [[float(i == j) for j in range(N_STATES)] for i in range(N_STATES)]
    with pytest.raises(ValueError, match="process noise"):
        cov.propagate(I, [0.01] * (N_STATES - 1) + [math.nan])
    assert cov.P == before


def test_failed_covariance_prediction_is_atomic():
    filt = ZoneKalmanFilter("plot")
    filt.initialize("2026-11-01")
    filt.covariance.P[0][0] = -1.0  # Corrupt prior uncertainty
    before_state = filt.state.values[:]
    before_cov = [row[:] for row in filt.covariance.P]
    with pytest.raises(ValueError, match="negative prior variance"):
        filt.predict("2026-11-02", WEATHER)
    assert filt.state.values == before_state
    assert filt.covariance.P == before_cov
    assert filt.days_since_obs == 0
    assert filt.state.day == "2026-11-01"


def test_vegetative_threshold_advances_without_exploding_covariance():
    filt = ZoneKalmanFilter("plot")
    filt.initialize("2026-11-01")
    filt.state.values[IDX_PHENO_GDD] = 185.0  # 15 GDD => stage 1 at 200
    predicted = filt.predict("2026-11-02", WEATHER)

    assert predicted.phenology_gdd == pytest.approx(200.0)
    assert predicted.phenology_stage == pytest.approx(1.0)
    assert filt.days_since_obs == 1
    assert filt.state.day == "2026-11-02"
    assert all(math.isfinite(x) for row in filt.covariance.P for x in row)
    assert all(filt.covariance.P[i][i] >= 0.0 for i in range(N_STATES))
    assert filt.covariance.P[IDX_PHENO_STAGE][IDX_PHENO_STAGE] < 100.0
