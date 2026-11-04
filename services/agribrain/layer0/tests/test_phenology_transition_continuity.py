"""L0-02B: numeric continuity and covariance regression gates.

Software-level tests only. The provisional emergence threshold and growth
modulation must be calibrated against independent crop/field evidence.
"""
import math

import pytest

from services.agribrain.layer0.kalman_engine import ZoneKalmanFilter
from services.agribrain.layer0.state_vector import (
    ProcessModel, StateVector, N_STATES, IDX_PHENO_GDD, IDX_PHENO_STAGE,
    IDX_LAI, IDX_PHOTO_EFF,
)

WEATHER = {"temp_max": 25.0, "temp_min": 15.0,
           "precipitation": 0.0, "et0": 3.0}
GDD_FORCING = 15.0


def _evolve_to(target_gdd, params=None):
    model = ProcessModel(params)
    previous = StateVector.initial("2026-11-01")
    previous.values[IDX_PHENO_GDD] = target_gdd - GDD_FORCING
    return model.predict(previous, WEATHER)[0]


@pytest.mark.parametrize("boundary", [100.0, 200.0, 800.0, 1200.0, 1600.0])
def test_full_state_transition_is_continuous_at_gdd_thresholds(boundary):
    epsilon = 1e-5
    left = _evolve_to(boundary - epsilon)
    exact = _evolve_to(boundary)
    right = _evolve_to(boundary + epsilon)

    # Not only the discrete stage indicator: LAI, biomass, photosynthetic
    # efficiency and other state variables must not jump at a threshold.
    for i in range(N_STATES):
        assert math.isfinite(left.values[i]) and math.isfinite(right.values[i])
        assert abs(right.values[i] - left.values[i]) < 1e-3, i
        assert min(left.values[i], right.values[i]) - 1e-3 <= exact.values[i]
        assert exact.values[i] <= max(left.values[i], right.values[i]) + 1e-3


def test_emergence_curve_is_bounded_and_locally_smooth():
    assert _evolve_to(90.0).values[IDX_PHENO_STAGE] == pytest.approx(0.0)
    assert 0.0 < _evolve_to(150.0).values[IDX_PHENO_STAGE] < 1.0
    assert _evolve_to(200.0).values[IDX_PHENO_STAGE] == pytest.approx(1.0)

    model = ProcessModel()
    prior = StateVector.initial("2026-11-01")
    prior.values[IDX_PHENO_GDD] = 185.0
    F = model.transition_jacobian(prior, WEATHER)
    assert math.isfinite(F[IDX_PHENO_STAGE][IDX_PHENO_GDD])
    assert F[IDX_PHENO_STAGE][IDX_PHENO_GDD] == pytest.approx(1 / 600, abs=5e-4)


def test_crop_override_preserves_relative_emergence_window_when_not_configured():
    params = {
        "gdd_vegetative": 120.0,
        "gdd_flowering": 600.0,
        "gdd_ripening": 1000.0,
        "gdd_senescence": 1300.0,
    }
    model = ProcessModel(params)
    assert model.params["gdd_emergence"] == pytest.approx(60.0)
    model = ProcessModel({**params, "gdd_emergence": 40.0})
    assert model.params["gdd_emergence"] == pytest.approx(40.0)


@pytest.mark.parametrize("params", [
    {"gdd_emergence": 200.0},
    {"gdd_emergence": math.nan},
    {"gdd_emergence": True},
    {"gdd_vegetative": 850.0},
    {"gdd_vegetative": -1.0},
])
def test_invalid_phenology_thresholds_fail_closed(params):
    with pytest.raises(ValueError):
        ProcessModel(params)


def test_one_year_covariance_remains_psd_numerically():
    np = pytest.importorskip("numpy")
    filt = ZoneKalmanFilter("plot")
    filt.initialize("2026-11-01")

    for day in range(1, 366):
        from datetime import date, timedelta
        target = (date(2026, 11, 1) + timedelta(days=day)).isoformat()
        filt.predict(target, WEATHER)
        P = np.asarray(filt.covariance.P, dtype=float)
        assert np.isfinite(P).all()
        assert np.allclose(P, P.T, rtol=1e-10, atol=1e-10)
        eigenvalues = np.linalg.eigvalsh(P)
        assert float(eigenvalues.min()) >= -1e-9 * max(
            1.0, float(abs(eigenvalues).max())
        )
        assert filt.state.variance == pytest.approx(P.diagonal().tolist())


def test_stage_boundary_does_not_create_anomalous_lai_or_efficiency_jump():
    before = _evolve_to(1600.0 - 1e-5)
    after = _evolve_to(1600.0 + 1e-5)
    assert abs(before.values[IDX_LAI] - after.values[IDX_LAI]) < 1e-4
    assert abs(before.values[IDX_PHOTO_EFF] - after.values[IDX_PHOTO_EFF]) < 1e-4
