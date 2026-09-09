"""Unit tests for Layer 0 Observation Models and State Vectors."""

import math
import pytest

from services.agribrain.layer0.observation_model import ObservationModel, get_observation_model
from services.agribrain.layer0.state_vector import (
    StateVector,
    ProcessModel,
    N_STATES,
    IDX_LAI,
    IDX_SM_0_10,
    IDX_CANOPY_STRESS,
    IDX_BIOMASS,
    IDX_PHENO_GDD,
    IDX_PHOTO_EFF,
    DEFAULT_CROP_PARAMS,
)


def test_observation_model_sentinel2_ndvi():
    """Verify forward NDVI prediction and non-zero Jacobian entry for LAI."""
    state = [0.0] * N_STATES
    state[IDX_LAI] = 2.5

    predicted, H, R = ObservationModel.sentinel2_ndvi(state)

    # Bare soil (0.15) < predicted < max canopy (0.90)
    assert 0.15 < predicted < 0.90
    assert len(H) == N_STATES
    assert H[IDX_LAI] > 0.0  # Positive sensitivity to LAI
    # All other states should be 0 in Jacobian row
    for i in range(N_STATES):
        if i != IDX_LAI:
            assert H[i] == 0.0
    assert R > 0.0


def test_observation_model_sentinel1_vv():
    """Verify SAR VV backscatter response to soil moisture and LAI attenuation."""
    state = [0.0] * N_STATES
    state[IDX_SM_0_10] = 0.30
    state[IDX_LAI] = 1.0

    predicted, H, R = ObservationModel.sentinel1_vv(state)

    # Typical agricultural VV is between -25 dB and -5 dB
    assert -25.0 <= predicted <= -5.0
    assert H[IDX_SM_0_10] == 10.0  # Positive sensitivity to soil moisture
    assert H[IDX_LAI] < 0.0        # Negative attenuation by vegetation


def test_observation_model_ndmi_canopy_stress():
    """Verify NDMI forward model decreases as canopy water stress increases."""
    state_no_stress = [0.0] * N_STATES
    state_no_stress[IDX_LAI] = 2.0
    state_no_stress[IDX_CANOPY_STRESS] = 0.0

    state_stressed = [0.0] * N_STATES
    state_stressed[IDX_LAI] = 2.0
    state_stressed[IDX_CANOPY_STRESS] = 0.8

    ndmi_normal, _, _ = ObservationModel.sentinel2_ndmi(state_no_stress)
    ndmi_stressed, H, _ = ObservationModel.sentinel2_ndmi(state_stressed)

    assert ndmi_normal > ndmi_stressed
    assert H[IDX_CANOPY_STRESS] < 0.0


def test_state_vector_initial_and_properties():
    """Verify StateVector.initial creates valid baseline state and properties work."""
    sv = StateVector.initial(day="2026-07-01", soil_props={"clay_pct": 30})
    assert sv.day == "2026-07-01"
    assert sv.lai == 0.2
    assert 0.0 <= sv.sm_0_10 <= 1.0
    assert sv.phenology_gdd == 0.0
    assert sv.photosynthetic_efficiency == 0.8

    d = sv.to_dict()
    assert d["day"] == "2026-07-01"
    assert "lai_proxy" in d
    assert "sm_0_10" in d

    u = sv.uncertainty_dict()
    assert "lai_proxy" in u
    assert u["lai_proxy"] > 0.0


def test_process_model_bounds_and_clamping():
    """Verify ProcessModel enforces physiological boundaries on state variables."""
    pm = ProcessModel()
    initial = StateVector.initial(day="2026-07-01")
    initial.values[IDX_LAI] = 15.0
    initial.values[IDX_SM_0_10] = -5.0

    weather = {
        "t_mean": 45.0,
        "t_min": 35.0,
        "t_max": 50.0,
        "rain_mm": 200.0,
        "et0_mm": 10.0,
    }
    next_state, Q = pm.predict(initial, weather, dt_days=1.0)

    # Values must be clamped within physiological boundaries
    assert 0.0 <= next_state.lai <= 8.0
    assert 0.0 <= next_state.sm_0_10 <= 1.0
    assert 0.0 <= next_state.sm_10_40 <= 1.0
    assert 0.0 <= next_state.canopy_stress <= 1.0
    assert 0.0 <= next_state.stress_thermal <= 1.0
    assert 0.0 <= next_state.photosynthetic_efficiency <= 1.0
    assert len(Q) == N_STATES
