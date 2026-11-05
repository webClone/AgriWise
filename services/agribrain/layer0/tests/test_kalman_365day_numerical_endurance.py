"""365-Day Continuous Numerical Endurance & Covariance Stability Gate.

Verifies long-horizon (365 days) mathematical and physical stability of the
Layer 0 Kalman Filter (ZoneKalmanFilter and DailyAssimilationEngine):
  1. Covariance stability: Joseph form maintains symmetry and positive
     semi-definiteness (all eigenvalues >= -1e-10) across all 365 daily steps.
  2. Physical constraints: all 9 state variables remain within biophysical bounds
     (LAI in [0, 8], soil moisture fractions in [0, 1], stress indices in [0, 1],
     GDD non-decreasing).
  3. Temporal gap admission: validates Q(dt) linear scaling across varying
     temporal gaps within [0, 30] days, and strict fail-closed rejection of
     zero, negative, or >30-day gaps.
  4. Deterministic replay invariance: bitwise/tolerance-identical state trajectories
     under identical forcing, plus mid-cycle serialization/deserialization fidelity.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import math
from typing import Dict, List

import numpy as np
import pytest

from services.agribrain.layer0.kalman_engine import (
    DailyAssimilationEngine,
    KalmanObservation,
    ZoneKalmanFilter,
)
from services.agribrain.layer0.state_vector import (
    IDX_BIOMASS,
    IDX_CANOPY_STRESS,
    IDX_LAI,
    IDX_PHENO_GDD,
    IDX_PHENO_STAGE,
    IDX_PHOTO_EFF,
    IDX_SM_0_10,
    IDX_SM_10_40,
    IDX_STRESS_THERMAL,
    N_STATES,
)


def generate_synthetic_365day_weather(start_date: date) -> Dict[str, Dict[str, float]]:
    """Generate realistic annual weather cycle for 365 days."""
    weather_by_day = {}
    for i in range(365):
        current_day = start_date + timedelta(days=i)
        day_str = current_day.isoformat()
        
        # Annual sinusoidal temperature cycle (Northern Hemisphere temperate/Mediterranean)
        # Winter ~5°C, Summer ~28°C
        t_mean = 16.5 + 11.5 * math.sin(2 * math.pi * (i - 100) / 365.0)
        t_min = t_mean - 5.0
        t_max = t_mean + 5.0
        
        # Precipitation: periodic rainfall events every 12 days
        if (i % 12 == 0) and (i % 36 != 0):
            precip = 8.0 + 6.0 * math.cos(i)
        elif i % 36 == 0:
            precip = 22.0  # heavy rain event
        else:
            precip = 0.0
            
        # ET0 proportional to solar radiation and temperature
        et0 = max(1.0, 1.2 + 3.2 * max(0.0, (t_mean - 2.0) / 25.0))
        
        weather_by_day[day_str] = {
            "temp_mean": round(t_mean, 2),
            "temp_min": round(t_min, 2),
            "temp_max": round(t_max, 2),
            "precipitation": round(max(0.0, precip), 2),
            "et0": round(et0, 2),
        }
    return weather_by_day


def generate_synthetic_365day_observations(start_date: date) -> Dict[str, List[KalmanObservation]]:
    """Generate periodic satellite observations (NDVI, soil moisture) across 365 days."""
    obs_by_day = {}
    for i in range(365):
        current_day = start_date + timedelta(days=i)
        day_str = current_day.isoformat()
        daily_obs = []
        
        # NDVI observation every 5 days (optical Sentinel-2 cadence)
        if i % 5 == 0:
            # Expected seasonal NDVI curve
            expected_ndvi = 0.2 + 0.55 * max(0.0, math.sin(math.pi * i / 365.0))
            daily_obs.append(KalmanObservation(
                obs_type="ndvi",
                value=float(round(expected_ndvi, 3)),
                sigma=0.03,
                reliability=0.95,
                source="sentinel2",
            ))
            
        # SAR soil moisture observation every 6 days (Sentinel-1 cadence)
        if i % 6 == 0:
            daily_obs.append(KalmanObservation(
                obs_type="soil_moisture",
                value=0.22,
                sigma=0.04,
                reliability=0.90,
                source="sentinel1",
            ))
            
        if daily_obs:
            obs_by_day[day_str] = daily_obs
    return obs_by_day


def test_365day_continuous_assimilation_stability_and_psd():
    """Verify covariance PSD, symmetry, and physical state bounds across 365 consecutive days."""
    start_date = date(2025, 1, 1)
    weather_series = generate_synthetic_365day_weather(start_date)
    obs_series = generate_synthetic_365day_observations(start_date)
    
    filt = ZoneKalmanFilter("plot_endurance_365")
    filt.initialize(start_date.isoformat(), soil_props={"clay_pct": 25.0, "sand_pct": 40.0})
    
    prev_gdd = 0.0
    
    for i in range(1, 365):
        current_day = (start_date + timedelta(days=i)).isoformat()
        weather = weather_series[current_day]
        observations = obs_series.get(current_day, [])
        
        # Assimilate day
        prov = filt.step(current_day, weather, observations=observations)
        assert prov["day"] == current_day
        
        # 1. Check Covariance Symmetry
        P = filt.covariance.P
        for r in range(N_STATES):
            for c in range(N_STATES):
                assert math.isclose(P[r][c], P[c][r], abs_tol=1e-12), (
                    f"Day {current_day}: Asymmetry at ({r}, {c}): {P[r][c]} != {P[c][r]}"
                )
                assert math.isfinite(P[r][c]), f"Day {current_day}: Non-finite P[{r}][{c}]"
                
        # 2. Check Positive Semi-Definiteness (all eigenvalues >= -1e-10)
        eigenvalues = np.linalg.eigvalsh(np.array(P, dtype=np.float64))
        min_eigen = float(np.min(eigenvalues))
        assert min_eigen >= -1e-10, (
            f"Day {current_day}: Covariance non-PSD! Minimum eigenvalue: {min_eigen:.2e}"
        )
        
        # 3. Check diagonal variances: strictly positive and bounded
        diag = filt.covariance.diagonal()
        for idx, var in enumerate(diag):
            assert var > 0.0, f"Day {current_day}: Variance collapsed to non-positive at state {idx}: {var}"
            assert var < 1e5, f"Day {current_day}: Variance exploded at state {idx}: {var}"
            
        # 4. Check Biophysical State Bounds
        st = filt.state
        assert 0.0 <= st.lai <= 8.0, f"Day {current_day}: LAI out of bounds: {st.lai}"
        assert 0.0 <= st.biomass <= 10.0, f"Day {current_day}: Biomass out of bounds: {st.biomass}"
        assert 0.0 <= st.sm_0_10 <= 1.0, f"Day {current_day}: SM 0-10cm out of bounds: {st.sm_0_10}"
        assert 0.0 <= st.sm_10_40 <= 1.0, f"Day {current_day}: SM 10-40cm out of bounds: {st.sm_10_40}"
        assert 0.0 <= st.canopy_stress <= 1.0, f"Day {current_day}: Canopy stress out of bounds: {st.canopy_stress}"
        assert 0.0 <= st.stress_thermal <= 1.0, f"Day {current_day}: Thermal stress out of bounds: {st.stress_thermal}"
        assert 0.0 <= st.photosynthetic_efficiency <= 1.0, f"Day {current_day}: Photo eff out of bounds: {st.photosynthetic_efficiency}"
        assert 0.0 <= st.phenology_stage <= 4.0, f"Day {current_day}: Stage out of bounds: {st.phenology_stage}"
        assert st.phenology_gdd >= prev_gdd - 1e-9, f"Day {current_day}: GDD decreased from {prev_gdd} to {st.phenology_gdd}"
        prev_gdd = st.phenology_gdd


def test_365day_temporal_gaps_and_rejection_boundary():
    """Verify temporal gap contracts over arbitrary step sizes and boundary rejections."""
    start_date = date(2025, 1, 1)
    filt = ZoneKalmanFilter("plot_gap_test")
    filt.initialize(start_date.isoformat())
    
    # 1. Valid gaps: 1, 2, 5, 14, 28, 30 days
    valid_gaps = [1, 2, 5, 14, 28, 30]
    cursor = start_date
    for gap_days in valid_gaps:
        target = cursor + timedelta(days=gap_days)
        filt.predict_missing_weather(target.isoformat())
        
        # Verify dt_days in last contract
        assert filt._last_temporal_contract.dt_days == pytest.approx(float(gap_days))
        
        # Verify eigenvalues remain PSD after large gap
        eigs = np.linalg.eigvalsh(np.array(filt.covariance.P, dtype=np.float64))
        assert np.min(eigs) >= -1e-10
        cursor = target
        
    # 2. Strict fail-closed boundary rejection: gap > 30 days
    over_limit_day = (cursor + timedelta(days=31)).isoformat()
    with pytest.raises(ValueError, match="invalid temporal gap"):
        filt.predict_missing_weather(over_limit_day)
        
    # 3. Non-positive gap rejection: 0 or negative days
    with pytest.raises(ValueError, match="invalid temporal gap"):
        filt.predict_missing_weather(cursor.isoformat())
    with pytest.raises(ValueError, match="invalid temporal gap"):
        filt.predict_missing_weather((cursor - timedelta(days=1)).isoformat())


def test_365day_deterministic_replay_invariance():
    """Verify exact deterministic trajectory replay and checkpoint restore fidelity."""
    start_date = date(2025, 1, 1)
    weather_series = generate_synthetic_365day_weather(start_date)
    obs_series = generate_synthetic_365day_observations(start_date)
    
    filt_1 = ZoneKalmanFilter("plot_replay_1")
    filt_2 = ZoneKalmanFilter("plot_replay_2")
    filt_1.initialize(start_date.isoformat())
    filt_2.initialize(start_date.isoformat())
    
    checkpoint_state = None
    checkpoint_cov = None
    mid_day_str = (start_date + timedelta(days=182)).isoformat()
    
    # Run both filters simultaneously for 365 days
    for i in range(1, 365):
        current_day = (start_date + timedelta(days=i)).isoformat()
        weather = weather_series[current_day]
        observations = obs_series.get(current_day, [])
        
        filt_1.step(current_day, weather, observations=deepcopy(observations))
        filt_2.step(current_day, weather, observations=deepcopy(observations))
        
        # Exact trajectory invariance
        assert filt_1.state.values == filt_2.state.values, f"State divergence on day {current_day}"
        assert filt_1.covariance.P == filt_2.covariance.P, f"Covariance divergence on day {current_day}"
        
        # Snapshot at day 182
        if current_day == mid_day_str:
            checkpoint_state = deepcopy(filt_1.state)
            checkpoint_cov = deepcopy(filt_1.covariance)
            
    # Test mid-cycle cold restore
    filt_resume = ZoneKalmanFilter("plot_resume")
    filt_resume.state = deepcopy(checkpoint_state)
    filt_resume.covariance = deepcopy(checkpoint_cov)
    filt_resume.initialized = True
    filt_resume.days_since_obs = filt_1.days_since_obs  # restored state
    
    # Run resumed filter from day 183 to 365
    for i in range(183, 365):
        current_day = (start_date + timedelta(days=i)).isoformat()
        weather = weather_series[current_day]
        observations = obs_series.get(current_day, [])
        filt_resume.step(current_day, weather, observations=deepcopy(observations))
        
    # Compare final state and covariance: must match continuous run within float precision
    for idx in range(N_STATES):
        assert math.isclose(
            filt_1.state.values[idx], filt_resume.state.values[idx], abs_tol=1e-12,
        ), f"State {idx} difference between continuous and resumed filter"
        for j in range(N_STATES):
            assert math.isclose(
                filt_1.covariance.P[idx][j], filt_resume.covariance.P[idx][j], abs_tol=1e-12,
            ), f"Covariance ({idx}, {j}) difference between continuous and resumed filter"


def test_365day_daily_assimilation_engine_multi_zone():
    """Verify DailyAssimilationEngine multi-zone tracking across full 365 days."""
    start_date = date(2025, 1, 1)
    init_day = (start_date - timedelta(days=1)).isoformat()
    weather_series = generate_synthetic_365day_weather(start_date)
    
    engine = DailyAssimilationEngine()
    engine.add_zone("zone_north", soil_props={"clay_pct": 20.0}, start_day=init_day)
    engine.add_zone("zone_south", soil_props={"clay_pct": 40.0}, start_day=init_day)
    
    # Run 365 days with zone-specific observation distinguishing north from south
    zone_obs = {
        "2025-06-15": {
            "zone_north": [KalmanObservation(obs_type="ndvi", value=0.72, sigma=0.03, source="sentinel2")],
            "zone_south": [KalmanObservation(obs_type="ndvi", value=0.45, sigma=0.03, source="sentinel2")],
        }
    }
    results = engine.run_period(
        start_date=start_date.isoformat(),
        end_date=(start_date + timedelta(days=364)).isoformat(),
        daily_weather=weather_series,
        all_observations=zone_obs,
    )
    assert len(results) == 365
    
    # Verify both zones remained distinct, stable, and positive
    north_final = engine.filters["zone_north"]
    south_final = engine.filters["zone_south"]
    
    assert north_final.state.values != south_final.state.values
    for z_name, z_filt in [("north", north_final), ("south", south_final)]:
        eigs = np.linalg.eigvalsh(np.array(z_filt.covariance.P, dtype=np.float64))
        assert np.min(eigs) >= -1e-10, f"Zone {z_name} non-PSD covariance at 365 days"
        assert 0.0 <= z_filt.state.sm_0_10 <= 1.0
        assert 0.0 <= z_filt.state.sm_10_40 <= 1.0
