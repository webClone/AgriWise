"""
V72: Sentinel-2 optical forward model.

Maps agronomic state vector x_t → predicted observation-equivalent features.
This is h(x_t) in the corrected equation: H_t · h(x̂_t) ≈ y_t.

Provides:
  - Forward model h(x) for each optical index
  - Jacobian ∂h/∂x for linearized EnKF update
  - Band-specific noise models

Note: These are linearized approximations. Full PROSAIL / non-linear
inversion is deferred to a later phase as approved.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from ..config import (
    IDX_BARE_SOIL,
    IDX_BIOTIC,
    IDX_CANOPY_WATER,
    IDX_CHLOROPHYLL,
    IDX_LAI,
    IDX_PHENOLOGY,
    IDX_ROOT_ZONE_WATER,
    IDX_SALINITY,
    IDX_STRESS_MEMORY,
    IDX_STRUCTURE,
    IDX_SURFACE_WETNESS,
    IDX_THERMAL,
    IDX_VIGOR,
    N_STATES,
    STATE_NAMES,
)


def forward_model_ndvi(state: List[float]) -> float:
    """Predict NDVI from state vector.

    NDVI ≈ vigor * (1 - bare_soil) * f(LAI)
    Linearized: NDVI ≈ 0.7 * vigor + 0.2 * LAI_norm - 0.3 * bare_soil + 0.1
    """
    vigor = state[IDX_VIGOR]
    lai = state[IDX_LAI]
    bare = state[IDX_BARE_SOIL]

    lai_norm = min(lai / 5.0, 1.0)  # Normalize LAI to [0, 1] range
    ndvi = 0.7 * vigor + 0.2 * lai_norm - 0.3 * bare + 0.1
    return max(-1.0, min(1.0, ndvi))


def forward_model_evi(state: List[float]) -> float:
    """Predict EVI from state vector.

    EVI ≈ vigor * f(LAI), better in dense canopy.
    """
    vigor = state[IDX_VIGOR]
    lai = state[IDX_LAI]
    bare = state[IDX_BARE_SOIL]

    lai_norm = min(lai / 6.0, 1.0)
    evi = 0.6 * vigor + 0.3 * lai_norm - 0.2 * bare + 0.05
    return max(-1.0, min(1.0, evi))


def forward_model_ndre(state: List[float]) -> float:
    """Predict NDRE from state vector.

    NDRE is sensitive to chlorophyll content.
    NDRE ≈ f(chlorophyll, LAI)
    """
    chl = state[IDX_CHLOROPHYLL]
    lai = state[IDX_LAI]

    chl_norm = min(chl / 60.0, 1.0)
    lai_norm = min(lai / 5.0, 1.0)
    ndre = 0.5 * chl_norm + 0.3 * lai_norm + 0.05
    return max(-1.0, min(1.0, ndre))


def forward_model_ndmi(state: List[float]) -> float:
    """Predict NDMI from state vector.

    NDMI responds to canopy water content.
    """
    cw = state[IDX_CANOPY_WATER]
    lai = state[IDX_LAI]

    lai_norm = min(lai / 5.0, 1.0)
    ndmi = 0.6 * cw + 0.2 * lai_norm + 0.05
    return max(-1.0, min(1.0, ndmi))


def forward_model_ndwi(state: List[float]) -> float:
    """Predict McFeeters NDWI from state vector.

    McFeeters NDWI = (Green - NIR) / (Green + NIR).
    Green vegetation canopy has high NIR reflectance and low Green reflectance,
    driving NDWI to negative values (-0.6 to -0.8) proportional to vigor.
    Bare soil has lower NIR contrast (~ -0.2 to -0.3).
    Standing surface wetness increases Green relative to NIR.
    """
    sw = state[IDX_SURFACE_WETNESS]
    vigor = state[IDX_VIGOR]
    bare = state[IDX_BARE_SOIL]

    ndwi = -0.65 * vigor - 0.20 * bare + 0.6 * sw - 0.05
    return max(-1.0, min(1.0, ndwi))


def forward_model_bsi(state: List[float]) -> float:
    """Predict BSI from state vector.

    BSI responds to bare soil fraction.
    """
    bare = state[IDX_BARE_SOIL]
    vigor = state[IDX_VIGOR]

    bsi = 0.6 * bare - 0.3 * vigor + 0.2
    return max(-1.0, min(1.0, bsi))


def forward_model_ndsi(state: List[float]) -> float:
    """Predict NDSI from state vector."""
    salinity = state[IDX_SALINITY]
    bare = state[IDX_BARE_SOIL]
    vigor = state[IDX_VIGOR]
    ndsi = 0.55 * salinity + 0.35 * bare - 0.20 * vigor
    return max(-1.0, min(1.0, ndsi))


def forward_model_cwsi(state: List[float]) -> float:
    """Predict CWSI thermal stress proxy from state vector."""
    thermal = state[IDX_THERMAL]
    cw = state[IDX_CANOPY_WATER]
    cwsi = 0.70 * thermal - 0.30 * cw
    return max(0.0, min(1.0, cwsi))


def forward_model_phenology(state: List[float]) -> float:
    """Predict phenology index from state vector."""
    pheno = state[IDX_PHENOLOGY]
    vigor = state[IDX_VIGOR]
    lai = state[IDX_LAI]
    p_idx = 0.60 * pheno + 0.30 * vigor + 0.10 * min(lai / 4.0, 1.0)
    return max(0.0, min(1.0, p_idx))


def forward_model_stress_memory(state: List[float]) -> float:
    """Predict stress memory from state vector."""
    mem = state[IDX_STRESS_MEMORY]
    sal = state[IDX_SALINITY]
    res = 0.65 * mem + 0.35 * sal
    return max(0.0, min(1.0, res))


def forward_model_biotic_anomaly(state: List[float]) -> float:
    """Predict biotic risk anomaly from state vector."""
    bio = state[IDX_BIOTIC]
    vigor = state[IDX_VIGOR]
    anomaly = 0.75 * bio - 0.25 * vigor
    return max(0.0, min(1.0, anomaly))


# ── Forward Model Dispatch ──────────────────────────────────────────────────

FORWARD_MODELS = {
    "ndvi": forward_model_ndvi,
    "evi": forward_model_evi,
    "ndre": forward_model_ndre,
    "ndmi": forward_model_ndmi,
    "ndwi": forward_model_ndwi,
    "bsi": forward_model_bsi,
    "ndsi": forward_model_ndsi,
    "cwsi": forward_model_cwsi,
    "phenology_index": forward_model_phenology,
    "stress_memory_index": forward_model_stress_memory,
    "biotic_anomaly": forward_model_biotic_anomaly,
}

FORWARD_MODEL_STATE_REQUIREMENTS = {
    "ndvi": (IDX_VIGOR, IDX_LAI, IDX_BARE_SOIL),
    "evi": (IDX_VIGOR, IDX_LAI, IDX_BARE_SOIL),
    "ndre": (IDX_CHLOROPHYLL, IDX_LAI),
    "ndmi": (IDX_CANOPY_WATER, IDX_LAI),
    "ndwi": (IDX_SURFACE_WETNESS, IDX_VIGOR, IDX_BARE_SOIL),
    "bsi": (IDX_BARE_SOIL, IDX_VIGOR),
}


def predict_observation(
    index_name: str, state: List[float],
) -> Optional[float]:
    """Predict observation-equivalent value from state vector.

    This is h(x_t) for a given index.
    """
    model = FORWARD_MODELS.get(index_name)
    if model is None:
        return None
    requirements = FORWARD_MODEL_STATE_REQUIREMENTS.get(index_name, ())
    try:
        if any(
            index >= len(state) or not math.isfinite(float(state[index]))
            for index in requirements
        ):
            return None
    except (TypeError, ValueError):
        return None
    return model(state)


# ── Jacobian ────────────────────────────────────────────────────────────────


def compute_jacobian_ndvi(state: List[float]) -> List[float]:
    """Compute ∂NDVI/∂x (linearized Jacobian row).

    Returns a list of N_STATES partial derivatives.
    """
    jac = [0.0] * N_STATES
    jac[IDX_VIGOR] = 0.7
    jac[IDX_LAI] = 0.2 / 5.0  # d/d(LAI) of LAI/5.0
    jac[IDX_BARE_SOIL] = -0.3
    return jac


def compute_jacobian_evi(state: List[float]) -> List[float]:
    jac = [0.0] * N_STATES
    jac[IDX_VIGOR] = 0.6
    jac[IDX_LAI] = 0.3 / 6.0
    jac[IDX_BARE_SOIL] = -0.2
    return jac


def compute_jacobian_ndre(state: List[float]) -> List[float]:
    jac = [0.0] * N_STATES
    jac[IDX_CHLOROPHYLL] = 0.5 / 60.0
    jac[IDX_LAI] = 0.3 / 5.0
    return jac


def compute_jacobian_ndmi(state: List[float]) -> List[float]:
    jac = [0.0] * N_STATES
    jac[IDX_CANOPY_WATER] = 0.6
    jac[IDX_LAI] = 0.2 / 5.0
    return jac


def compute_jacobian_ndwi(state: List[float]) -> List[float]:
    jac = [0.0] * N_STATES
    jac[IDX_VIGOR] = -0.65
    jac[IDX_BARE_SOIL] = -0.20
    jac[IDX_SURFACE_WETNESS] = 0.6
    return jac


def compute_jacobian_bsi(state: List[float]) -> List[float]:
    jac = [0.0] * N_STATES
    jac[IDX_BARE_SOIL] = 0.6
    jac[IDX_VIGOR] = -0.3
    return jac


def compute_jacobian_ndsi(state: List[float]) -> List[float]:
    jac = [0.0] * N_STATES
    jac[IDX_SALINITY] = 0.55
    jac[IDX_BARE_SOIL] = 0.35
    jac[IDX_VIGOR] = -0.20
    return jac


def compute_jacobian_cwsi(state: List[float]) -> List[float]:
    jac = [0.0] * N_STATES
    jac[IDX_THERMAL] = 0.70
    jac[IDX_CANOPY_WATER] = -0.30
    return jac


def compute_jacobian_phenology(state: List[float]) -> List[float]:
    jac = [0.0] * N_STATES
    jac[IDX_PHENOLOGY] = 0.60
    jac[IDX_VIGOR] = 0.30
    jac[IDX_LAI] = 0.10 / 4.0
    return jac


def compute_jacobian_stress_memory(state: List[float]) -> List[float]:
    jac = [0.0] * N_STATES
    jac[IDX_STRESS_MEMORY] = 0.65
    jac[IDX_SALINITY] = 0.35
    return jac


def compute_jacobian_biotic(state: List[float]) -> List[float]:
    jac = [0.0] * N_STATES
    jac[IDX_BIOTIC] = 0.75
    jac[IDX_VIGOR] = -0.25
    return jac


JACOBIANS = {
    "ndvi": compute_jacobian_ndvi,
    "evi": compute_jacobian_evi,
    "ndre": compute_jacobian_ndre,
    "ndmi": compute_jacobian_ndmi,
    "ndwi": compute_jacobian_ndwi,
    "bsi": compute_jacobian_bsi,
    "ndsi": compute_jacobian_ndsi,
    "cwsi": compute_jacobian_cwsi,
    "phenology_index": compute_jacobian_phenology,
    "stress_memory_index": compute_jacobian_stress_memory,
    "biotic_anomaly": compute_jacobian_biotic,
}


def compute_jacobian(
    index_name: str, state: List[float],
) -> Optional[List[float]]:
    """Compute Jacobian row ∂h/∂x for a given index."""
    fn = JACOBIANS.get(index_name)
    if fn is None:
        return None
    return fn(state)
