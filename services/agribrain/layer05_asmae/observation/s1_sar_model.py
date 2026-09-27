"""
V72: Sentinel-1 SAR forward model.

Maps agronomic state vector → predicted SAR backscatter features.
SAR forward model: h_SAR(x_t) → VV, VH, VV/VH predictions.

Hard rules:
  - SAR must NOT directly update chlorophyll, vigor, LAI, or phenology
  - SAR VV → surface_wetness, root_zone_water (roughness-dominated)
  - SAR VH → structure (volume scattering)
  - SAR VV/VH ratio → structure + moisture coupling
"""

from __future__ import annotations

import math
from typing import List, Optional

from ..config import (
    IDX_BARE_SOIL,
    IDX_ROOT_ZONE_WATER,
    IDX_STRUCTURE,
    IDX_SURFACE_WETNESS,
    N_STATES,
)


def db_to_linear(db_val: float) -> float:
    """Convert dB backscatter to linear power ratio (BC.10.17 P1.3)."""
    return 10.0 ** (db_val / 10.0)


def linear_to_db(linear_val: float) -> float:
    """Convert linear power ratio to dB backscatter (BC.10.17 P1.3)."""
    if linear_val <= 1e-10:
        return -99.0
    return 10.0 * math.log10(linear_val)


def forward_model_sar_vv(state: List[float]) -> float:
    """Predict SAR VV backscatter from state vector.

    VV is influenced by surface roughness, soil moisture, and in woody /
    orchard canopies by structural double-bounce scattering.
    σ°_VV ≈ f(structure, surface_wetness, root_zone_water, bare_soil)

    Returns normalized backscatter in [0, 1] range.
    """
    sw = state[IDX_SURFACE_WETNESS]
    rzw = state[IDX_ROOT_ZONE_WATER]
    bare = state[IDX_BARE_SOIL]
    struct = state[IDX_STRUCTURE]

    if sw is None and rzw is None and struct is None:
        raise ValueError("SAR VV requires moisture or structure")
    struct_val = struct if (struct is not None and math.isfinite(struct)) else 0.4
    sw_val = sw if (sw is not None and math.isfinite(sw)) else 0.1
    rzw_val = rzw if (rzw is not None and math.isfinite(rzw)) else 0.2
    bare_val = bare if (bare is not None and math.isfinite(bare)) else 0.3

    # VV increases with structure (double-bounce), moisture, and bare soil exposure
    vv = 0.35 * struct_val + 0.25 * sw_val + 0.2 * rzw_val + 0.1 * bare_val + 0.05
    return max(0.0, min(1.0, vv))


def forward_model_sar_vh(state: List[float]) -> float:
    """Predict SAR VH backscatter from state vector.

    VH is dominated by volume scattering (vegetation structure).
    σ°_VH ≈ f(structure, surface_wetness)
    """
    struct = state[IDX_STRUCTURE]
    sw = state[IDX_SURFACE_WETNESS]

    vh = 0.6 * struct + 0.2 * sw + 0.1
    return max(0.0, min(1.0, vh))


def forward_model_sar_ratio(state: List[float]) -> float:
    """Predict the bounded cross-polarization fraction from state.

    The observation contract is VH / (VV + VH), a bounded monotonic form of
    the VH/VV ratio.  It is driven primarily by vegetation structure, with a
    smaller surface-wetness contribution.
    """
    struct = state[IDX_STRUCTURE]
    sw = state[IDX_SURFACE_WETNESS]

    ratio = 0.65 * struct + 0.10 * sw + 0.05
    return max(0.0, min(1.0, ratio))


def forward_model_delta_sar(state: List[float]) -> float:
    """Predict ΔSAR (change) from state vector.

    Large changes indicate harvest, tillage, flooding.
    """
    sw = state[IDX_SURFACE_WETNESS]
    bare = state[IDX_BARE_SOIL]

    delta = 0.5 * sw + 0.3 * bare
    return max(0.0, min(1.0, delta))


# ── Forward Model Dispatch ──────────────────────────────────────────────────

SAR_FORWARD_MODELS = {
    "sar_vv": forward_model_sar_vv,
    "sar_vh": forward_model_sar_vh,
    "sar_ratio": forward_model_sar_ratio,
    "delta_sar": forward_model_delta_sar,
}

SAR_FORWARD_MODEL_STATE_REQUIREMENTS = {
    "sar_vv": (IDX_SURFACE_WETNESS,),
    "sar_vh": (IDX_STRUCTURE,),
    "sar_ratio": (IDX_STRUCTURE,),
    "delta_sar": (IDX_SURFACE_WETNESS,),
}


def predict_sar_observation(
    index_name: str, state: List[float], nuisance_state: Optional[List[float]] = None,
) -> Optional[float]:
    """Predict SAR observation-equivalent from state vector."""
    model = SAR_FORWARD_MODELS.get(index_name)
    if model is None:
        return None
    if nuisance_state:
        state = [
            state[i] if (i < len(state) and state[i] is not None)
            else (nuisance_state[i] if i < len(nuisance_state) else None)
            for i in range(max(len(state), len(nuisance_state)))
        ]
    requirements = SAR_FORWARD_MODEL_STATE_REQUIREMENTS.get(index_name, ())
    try:
        if any(
            index >= len(state) or state[index] is None or not math.isfinite(float(state[index]))
            for index in requirements
        ):
            # Special case for SAR VV: root_zone_water or structure can fulfill primary requirement
            if index_name == "sar_vv" and len(state) > IDX_ROOT_ZONE_WATER and state[IDX_ROOT_ZONE_WATER] is not None and math.isfinite(float(state[IDX_ROOT_ZONE_WATER])):
                pass
            else:
                return None
    except (TypeError, ValueError):
        return None
    return model(state)


# ── SAR Jacobians ───────────────────────────────────────────────────────────

def compute_jacobian_sar_vv(state: List[float]) -> List[float]:
    jac = [0.0] * N_STATES
    jac[IDX_STRUCTURE] = 0.35
    jac[IDX_SURFACE_WETNESS] = 0.25
    jac[IDX_ROOT_ZONE_WATER] = 0.2
    jac[IDX_BARE_SOIL] = 0.1
    return jac


def compute_jacobian_sar_vh(state: List[float]) -> List[float]:
    jac = [0.0] * N_STATES
    jac[IDX_STRUCTURE] = 0.6
    jac[IDX_SURFACE_WETNESS] = 0.2
    return jac


def compute_jacobian_sar_ratio(state: List[float]) -> List[float]:
    jac = [0.0] * N_STATES
    jac[IDX_STRUCTURE] = 0.65
    jac[IDX_SURFACE_WETNESS] = 0.10
    return jac


def compute_jacobian_delta_sar(state: List[float]) -> List[float]:
    jac = [0.0] * N_STATES
    jac[IDX_SURFACE_WETNESS] = 0.5
    jac[IDX_BARE_SOIL] = 0.3
    return jac


SAR_JACOBIANS = {
    "sar_vv": compute_jacobian_sar_vv,
    "sar_vh": compute_jacobian_sar_vh,
    "sar_ratio": compute_jacobian_sar_ratio,
    "delta_sar": compute_jacobian_delta_sar,
}


def compute_sar_jacobian(
    index_name: str, state: List[float],
) -> Optional[List[float]]:
    """Compute Jacobian row for a SAR observation."""
    fn = SAR_JACOBIANS.get(index_name)
    if fn is None:
        return None
    return fn(state)


# ── Incidence Angle Normalization ───────────────────────────────────────────


def normalize_incidence_angle(
    backscatter: float,
    incidence_deg: float,
    reference_deg: float = 38.0,
) -> float:
    """Normalize SAR backscatter to a reference incidence angle.

    Uses the cosine correction:
        σ°_norm = σ° * (cos(θ_ref) / cos(θ))^n

    where n ≈ 2.0 for typical agricultural scenes.

    Args:
        backscatter: Observed backscatter value.
        incidence_deg: Observed incidence angle (degrees).
        reference_deg: Reference incidence angle (degrees).

    Returns:
        Normalized backscatter.
    """
    n = 2.0
    cos_ref = math.cos(math.radians(reference_deg))
    cos_obs = math.cos(math.radians(incidence_deg))

    if cos_obs < 1e-6:
        return backscatter

    correction = (cos_ref / cos_obs) ** n
    return backscatter * correction
