"""B2B-07A UTC time, Q(dt), covariance PSD and physical-forcing isolation.

Numerical software contract only: rates are provisional and uncalibrated.
"""
from copy import deepcopy
import math

import numpy as np
import pytest

from services.agribrain.layer0.temporal_process_noise import (
    TemporalGapContract, NOMINAL_VARIANCE_RATE_PER_DAY,
    UNFORCED_DRIFT_VARIANCE_RATE_PER_DAY, Q_RATE_UNITS,
    scale_diagonal_variance_rates,
)
from services.agribrain.layer0.state_vector import (
    StateVector, StateCovariance, ProcessModel, N_STATES,
    IDX_LAI, IDX_SM_0_10, IDX_PHENO_GDD,
)
from services.agribrain.layer0.kalman_engine import (
    ZoneKalmanFilter, DailyAssimilationEngine,
)

WEATHER = {"temp_min": 10.0, "temp_max": 20.0, "precipitation": 0.0, "et0": 3.0}


def make_filter():
    filt = ZoneKalmanFilter("plot")
    filt.initialize("2026-11-01")
    return filt


@pytest.mark.parametrize("before,after,expected", [
    ("2026-11-01","2026-11-02",1.0),
    ("2026-11-01","2026-11-03",2.0),
    ("2026-11-01T00:00:00Z","2026-11-01T12:00:00Z",0.5),
    ("2026-11-01T00:00:00+01:00","2026-11-01T12:00:00+01:00",0.5),
    ("2026-11-01","2026-12-01",30.0),
])
def test_exact_utc_elapsed_days(before, after, expected):
    gap = TemporalGapContract.between(before, after)
    assert gap.dt_days == pytest.approx(expected)
    assert gap.previous_utc.utcoffset().total_seconds() == 0


@pytest.mark.parametrize("before,after", [
    ("2026-11-01","2026-11-01"),
    ("2026-11-02","2026-11-01"),
    ("2026-11-01","2026-12-02"),
    ("2026-11-01T12:00:00","2026-11-02T12:00:00"),
    ("garbage","2026-11-02"),
])
def test_invalid_gaps_denied(before, after):
    with pytest.raises(ValueError):
        TemporalGapContract.between(before, after)


@pytest.mark.parametrize("dt", [0, -1, 31, math.nan, math.inf, -math.inf, True])
def test_model_f_and_q_both_reject_invalid_dt(dt):
    model = ProcessModel()
    prior = StateVector.initial("2026-11-01")
    original = prior.values[:]
    with pytest.raises(ValueError, match="invalid temporal gap"):
        model.predict(prior, WEATHER, dt_days=dt)
    with pytest.raises(ValueError, match="invalid temporal gap"):
        model.transition_jacobian(prior, WEATHER, dt_days=dt)
    assert prior.values == original


def test_nominal_noise_rate_scales_as_variance_not_sigma():
    assert len(Q_RATE_UNITS) == N_STATES
    q1 = scale_diagonal_variance_rates(NOMINAL_VARIANCE_RATE_PER_DAY, 1)
    q2 = scale_diagonal_variance_rates(NOMINAL_VARIANCE_RATE_PER_DAY, 2)
    assert q1[IDX_SM_0_10] == pytest.approx(0.03)
    assert q2 == pytest.approx([2 * q for q in q1])


def test_process_q_scales_and_gdd_physics_is_not_dt_squared():
    model = ProcessModel()
    prior = StateVector.initial("2026-11-01")
    x1, q1 = model.predict(prior, WEATHER, dt_days=1)
    x2, q2 = model.predict(prior, WEATHER, dt_days=2)
    assert q2 == pytest.approx([2 * q for q in q1])
    assert x2.values[IDX_PHENO_GDD] == pytest.approx(2 * x1.values[IDX_PHENO_GDD])
    delta1 = x1.values[IDX_LAI] - prior.values[IDX_LAI]
    delta2 = x2.values[IDX_LAI] - prior.values[IDX_LAI]
    assert delta1 > 0
    assert 1.5 < delta2 / delta1 < 3.0


def test_normal_two_day_filter_prediction_uses_one_gap_for_f_and_q():
    f = make_filter()
    f.predict("2026-11-03", WEATHER)
    assert f._last_temporal_contract.dt_days == pytest.approx(2)
    assert f._last_process_q == pytest.approx(
        [2 * rate for rate in NOMINAL_VARIANCE_RATE_PER_DAY],
    )
    assert f.days_since_obs == pytest.approx(2)
    assert np.linalg.eigvalsh(f.covariance.P)[0] >= -1e-10


def test_degraded_two_day_no_synthetic_weather_and_no_global_5x():
    f = make_filter()
    before = f.state.values[:]
    f.predict_missing_weather("2026-11-03")
    assert f.state.values == before
    assert f._last_process_q == pytest.approx(
        [2 * rate for rate in UNFORCED_DRIFT_VARIANCE_RATE_PER_DAY],
    )
    assert f._last_q_regime == "UNFORCED_DRIFT_VARIANCE_RATE"
    assert f.provenance_history[-1]["q_temporal_contract"]["calibrated"] is False


def test_multi_day_single_daily_weather_is_unqualified():
    f = make_filter()
    before = f.state.values[:]
    provenance = f.step("2026-11-03", WEATHER)
    assert provenance["interval_forcing_coverage_verified"] is False
    assert provenance["weather_update_mode"] == "missing_weather_high_uncertainty"
    assert f.state.values == before
    assert provenance["q_temporal_contract"]["dt_days"] == pytest.approx(2)


def test_untrusted_interval_coverage_flag_does_not_promote_multi_day_weather():
    f = make_filter()
    before = f.state.values[:]
    weather = dict(WEATHER, interval_coverage_days=2.0)
    provenance = f.step("2026-11-03", weather)
    assert provenance["interval_forcing_coverage_verified"] is False
    assert provenance["weather_update_mode"] == "missing_weather_high_uncertainty"
    assert provenance["q_temporal_contract"]["q_regime"] == "UNFORCED_DRIFT_VARIANCE_RATE"
    assert f.state.values == before



def test_psd_eigen_gate_rejects_indefinite_positive_diagonal():
    cov = StateCovariance.from_diagonal([1.0] * N_STATES)
    cov.P[0][1] = cov.P[1][0] = 2.0
    before = deepcopy(cov.P)
    identity = [[float(i == j) for j in range(N_STATES)] for i in range(N_STATES)]
    with pytest.raises(ValueError, match="non-PSD prior covariance"):
        cov.propagate(identity, [0.01] * N_STATES)
    assert cov.P == before


def test_covariance_overflow_is_atomic():
    cov = StateCovariance.from_diagonal([1] * N_STATES)
    before = deepcopy(cov.P)
    jac = [[float(i == j) * 1e308 for j in range(N_STATES)] for i in range(N_STATES)]
    with pytest.raises((ValueError, OverflowError)):
        cov.propagate(jac, [0.01] * N_STATES)
    assert cov.P == before


def test_invalid_predict_gaps_do_not_mutate_state_covariance_or_age():
    f = make_filter()
    before = (deepcopy(f.state.values), f.state.day, deepcopy(f.covariance.P), f.days_since_obs)
    for stamp in ["2026-11-01", "2026-10-31", "2026-12-02"]:
        with pytest.raises(ValueError, match="temporal gap"):
            f.predict(stamp, WEATHER)
        assert (f.state.values, f.state.day, f.covariance.P, f.days_since_obs) == before
        assert f._last_temporal_contract is None


def test_missing_weather_rejects_zero_dt_without_provenance_mutation():
    f = make_filter()
    before = (deepcopy(f.state.values), deepcopy(f.covariance.P), len(f.provenance_history))
    with pytest.raises(ValueError, match="temporal gap"):
        f.predict_missing_weather("2026-11-01")
    assert (f.state.values, f.covariance.P, len(f.provenance_history)) == before


def test_missing_weather_psd_failure_is_atomic():
    f = make_filter()
    f.covariance.P[0][1] = f.covariance.P[1][0] = 10
    prior = deepcopy(f.covariance.P)
    with pytest.raises(ValueError, match="non-PSD prior covariance"):
        f.predict_missing_weather("2026-11-02")
    assert f.covariance.P == prior and f.state.day == "2026-11-01"


def test_daily_aggregation_emits_auditable_q_rate_provenance():
    engine = DailyAssimilationEngine()
    engine.add_zone("plot", start_day="2026-11-01")
    day = engine.run_day("2026-11-02", WEATHER)
    q = day["zones"]["plot"]["provenance"]["q_temporal_contract"]
    assert q["dt_days"] == pytest.approx(1)
    assert q["calibrated"] is False
    assert len(q["q_variance"]) == N_STATES


def test_unverified_raw_irrigation_is_still_forbidden():
    f = make_filter()
    before = deepcopy(f.covariance.P)
    with pytest.raises(ValueError, match="trusted L3 admission"):
        f.predict("2026-11-02", WEATHER, [{"event_type": "irrigation", "amount_mm": 20}])
    assert f.covariance.P == before
    assert f.state.day == "2026-11-01"



def test_subday_biomass_relaxation_composes_into_a_day():
    """Two independent half-day relaxation steps equal a daily step for a
    constant target, rather than applying a full daily EMA twice.
    """
    model = ProcessModel()
    prior = StateVector.initial("2026-11-01")
    weather = {"temp_min": 5.0, "temp_max": 5.0,
               "precipitation": 0.0, "et0": 0.0}
    half, _ = model.predict(prior, weather, dt_days=0.5)
    second, _ = model.predict(half, weather, dt_days=0.5)
    full, _ = model.predict(prior, weather, dt_days=1.0)
    assert second.biomass == pytest.approx(full.biomass, abs=1e-10)


def test_two_day_retention_matches_elapsed_time_not_twice_daily_mixing():
    model = ProcessModel()
    prior = StateVector.initial("2026-11-01")
    weather = {"temp_min": 5.0, "temp_max": 5.0,
               "precipitation": 0.0, "et0": 0.0}
    one, _ = model.predict(prior, weather, dt_days=1)
    two, _ = model.predict(prior, weather, dt_days=2)
    twice, _ = model.predict(one, weather, dt_days=1)
    assert two.biomass == pytest.approx(twice.biomass, abs=1e-10)
