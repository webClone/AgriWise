"""L0-JAC-01: native shutdown-boundary numerical regression.

The original process model jumped at shutdown_pressure > 0.1.
These controls test the full process prediction and EKF transition,
not scientific calibration or absolute accuracy of photosynthesis.
"""
import math

import pytest

from services.agribrain.layer0.kalman_engine import ZoneKalmanFilter
from services.agribrain.layer0.state_vector import (
    StateVector, StateCovariance, ProcessModel, N_STATES,
    IDX_STRESS_THERMAL, IDX_PHOTO_EFF, IDX_CANOPY_STRESS
)


WEATHER = {
    "temp_max": 25.0, "temp_min": 15.0,
    "precipitation": 0.0, "et0": 3.0
}

PRIOR = [1.0, 0.3, 0.5, 0.5, 0.0, 300.0, 1.1666666666667, 0.4625, 0.8]


def _prior(thermal=0.4625, water_stress=0.0, photo=0.8):
    values = PRIOR[:]
    values[IDX_STRESS_THERMAL] = thermal
    values[IDX_CANOPY_STRESS] = water_stress
    values[IDX_PHOTO_EFF] = photo
    return StateVector(values=values, day="2026-05-01", variance=[0.1]*N_STATES)


def _filter(prior):
    f = ZoneKalmanFilter("review-zone")
    f.initialize("2026-05-01")
    f.state = prior
    f.covariance = StateCovariance.from_diagonal([0.1]*N_STATES)
    return f


@pytest.mark.parametrize("photo", [0.25, 0.8, 0.95])
def test_photo_response_is_continuous_at_original_thermal_boundary(photo):
    model = ProcessModel()
    left = model.predict(_prior(thermal=0.4625-1e-6, photo=photo), WEATHER)[0]
    right = model.predict(_prior(thermal=0.4625+1e-6, photo=photo), WEATHER)[0]
    assert abs(left.photosynthetic_efficiency - right.photosynthetic_efficiency) < 1e-4


@pytest.mark.parametrize("photo", [0.25, 0.8, 0.95])
def test_photo_response_jacobian_converges_with_step_size(photo):
    model = ProcessModel()
    state = _prior(photo=photo)
    estimates = []
    for h in (1e-3, 1e-4, 1e-5, 1e-6):
        plus = _prior(thermal=0.4625 + h, photo=photo)
        minus = _prior(thermal=0.4625 - h, photo=photo)
        y_plus = model.predict(plus, WEATHER)[0].photosynthetic_efficiency
        y_minus = model.predict(minus, WEATHER)[0].photosynthetic_efficiency
        estimates.append((y_plus - y_minus)/(2*h))
    assert all(math.isfinite(d) for d in estimates)
    assert max(abs(d) for d in estimates) < 100.0
    assert abs(estimates[-1] - estimates[-2]) < 0.02


def test_full_ekf_no_artificial_sigma_spike_at_boundary():
    filt = _filter(_prior())
    predicted, Q = filt.process_model.predict(filt.state, WEATHER)
    F = filt.process_model.transition_jacobian(
        filt.state, WEATHER, predicted_state=predicted
    )
    assert abs(F[IDX_PHOTO_EFF][IDX_STRESS_THERMAL]) < 20.0

    output = filt.step("2026-05-02", WEATHER, observations=None)
    assert output["n_obs"] == 0
    sigma = filt.state.uncertainty_dict()["photosynthetic_efficiency"]
    assert math.isfinite(sigma)
    assert 0.0 < sigma < 5.0
    assert filt.covariance.P[IDX_PHOTO_EFF][IDX_PHOTO_EFF] >= 0


@pytest.mark.parametrize("water_stress", [0.0, 0.12, 0.25, 0.45])
def test_thermal_and_water_pressure_response_is_finite(water_stress):
    model = ProcessModel()
    prior = _prior(thermal=0.4625, water_stress=water_stress)
    state, Q = model.predict(prior, WEATHER)
    F = model.transition_jacobian(prior, WEATHER, predicted_state=state)
    assert 0.0 <= state.photosynthetic_efficiency <= 1.0
    assert all(math.isfinite(x) for row in F for x in row)


@pytest.mark.parametrize("params", [
    {"photo_shutdown_blend_start": 0.2, "photo_shutdown_blend_end": 0.1},
    {"photo_shutdown_blend_start": -0.2},
    {"photo_shutdown_blend_start": float("nan")},
    {"photo_shutdown_blend_end": True},
])
def test_invalid_provisional_regime_interval_rejected(params):
    with pytest.raises(ValueError, match="photosynthesis"):
        ProcessModel(params)
