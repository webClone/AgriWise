"""L0-02A: numerical admission regression tests for the existing Joseph EKF."""

from copy import deepcopy
import math

from services.agribrain.layer0.kalman_engine import KalmanObservation, ZoneKalmanFilter
from services.agribrain.layer0.state_vector import N_STATES


def _filter(provider):
    filt = ZoneKalmanFilter("plot", observation_model_provider=provider)
    filt.initialize("2026-11-01")
    return filt


def _unchanged_after(filt, obs):
    initial_state = filt.state.values.copy()
    initial_covariance = deepcopy(filt.covariance.P)
    assert filt.update([obs]) == {}
    assert filt.state.values == initial_state
    assert filt.covariance.P == initial_covariance
    assert filt.last_update_admitted_count == 0


def test_nonfinite_model_prediction_is_rejected():
    def provider(_):
        return lambda values: (math.nan, [1.0] + [0.0] * (N_STATES - 1), 0.01)
    _unchanged_after(_filter(provider), KalmanObservation("ndvi", 0.6, 0.02))


def test_nonfinite_and_wrong_length_jacobians_are_rejected():
    for jacobian in ([math.inf] + [0.0] * (N_STATES - 1), [1.0]):
        def provider(_):
            return lambda values: (0.2, jacobian, 0.01)
        _unchanged_after(_filter(provider), KalmanObservation("ndvi", 0.6, 0.02))


def test_overflowing_innovation_cannot_half_update_state():
    def provider(_):
        return lambda values: (-1e308, [1.0] + [0.0] * (N_STATES - 1), 0.01)
    _unchanged_after(_filter(provider), KalmanObservation("ndvi", 1e308, 0.02))


def test_valid_scalar_joseph_update_stays_symmetric_and_counted():
    def provider(_):
        return lambda values: (values[0], [1.0] + [0.0] * (N_STATES - 1), 0.01)
    filt = _filter(provider)
    before = filt.state.values[0]
    weights = filt.update([KalmanObservation("ndvi", 0.6, 0.02, source="test")])
    assert filt.state.values[0] > before
    assert filt.last_update_admitted_count == 1
    assert weights == {"test": 1.0}
    for i in range(N_STATES):
        assert math.isfinite(filt.covariance.P[i][i])
        assert filt.covariance.P[i][i] >= 0
        for j in range(N_STATES):
            assert math.isclose(filt.covariance.P[i][j], filt.covariance.P[j][i], abs_tol=1e-10)
