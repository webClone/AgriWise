"""
Sentinel-1 SAR Feature Computation Engine.

Pure-math functions — no API calls, no side effects.
All functions have explicit unit annotations, epsilon guards, and range checks.

IMPORTANT: VV/VH inputs must be linear power, NOT dB.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from layer0.sentinel1.schemas import SARRaster2D

# Guard constants
EPS = 1e-10

# dB plausibility ranges from CONTRACT.md
VV_DB_HARD_MIN, VV_DB_HARD_MAX = -35.0, 5.0
VH_DB_HARD_MIN, VH_DB_HARD_MAX = -45.0, 0.0
VV_DB_SOFT_MIN, VV_DB_SOFT_MAX = -30.0, 0.0
VH_DB_SOFT_MIN, VH_DB_SOFT_MAX = -35.0, -5.0
RVI_HARD_MAX = 4.0
RVI_SOFT_MAX = 1.5

# Feature names
SUPPORTED_FEATURES = [
    "VV_DB", "VH_DB", "VV_VH_RATIO", "VV_MINUS_VH_DB",
    "SPAN", "RVI", "CROSS_POL_FRACTION",
    "SURFACE_WETNESS_PROXY", "STRUCTURE_PROXY", "FLOOD_SCORE",
    "ROUGHNESS_PROXY",
]


@dataclass
class SARFeatureDiagnostics:
    """Diagnostics collected during feature raster computation."""
    total_pixels: int = 0
    valid_input_pixels: int = 0
    valid_output_pixels: int = 0
    out_of_hard_range: int = 0
    out_of_soft_range: int = 0
    flags: List[str] = field(default_factory=list)


# ============================================================================
# Scalar feature functions (single pixel)
# ============================================================================

def to_db(linear_power: float) -> Optional[float]:
    """Convert linear power to dB. Returns None if ≤ 0."""
    if linear_power <= 0:
        return None
    return 10.0 * math.log10(linear_power)


def from_db(db_value: float) -> float:
    """Convert dB to linear power."""
    return 10.0 ** (db_value / 10.0)


def ratio_linear(vv: float, vh: float) -> Optional[float]:
    """VV/VH linear ratio. Returns None if VH ≤ epsilon."""
    if vh <= EPS:
        return None
    return vv / vh


def vv_minus_vh_db(vv_db: float, vh_db: float) -> Optional[float]:
    """dB difference. Returns None if outside hard range [-5, 25]."""
    diff = vv_db - vh_db
    if diff < -5.0 or diff > 25.0:
        return None
    return diff


def span(vv: float, vh: float) -> Optional[float]:
    """Total backscatter energy (linear). Returns None if any ≤ 0."""
    if vv <= 0 or vh <= 0:
        return None
    return vv + vh


def rvi_dual_pol(vv: float, vh: float) -> Optional[float]:
    """
    Radar Vegetation Index (dual-pol approximation).
    RVI = 4 * VH / (VV + VH)

    Returns None if denominator ≤ epsilon or result outside [0, 4].
    """
    denom = vv + vh
    if denom <= EPS:
        return None
    result = 4.0 * vh / denom
    if result < 0 or result > RVI_HARD_MAX:
        return None
    return result


def cross_pol_fraction(vv: float, vh: float) -> Optional[float]:
    """VH / (VV + VH) — volume scattering fraction. Returns None if denom ≤ eps."""
    denom = vv + vh
    if denom <= EPS:
        return None
    result = vh / denom
    if result < 0 or result > 1.0:
        return None
    return result


def surface_wetness_proxy(
    vv_db_val: float,
    ratio_val: Optional[float] = None,
    incidence_angle: Optional[float] = None,
) -> Optional[float]:
    """
    SAR-derived surface wetness proxy [0, 1].

    NOT calibrated volumetric soil moisture.
    Weak indicator until calibrated with sensors or ground truth.

    Higher VV_dB (wetter) + lower ratio (wetter) → higher proxy.
    """
    if vv_db_val < VV_DB_HARD_MIN or vv_db_val > VV_DB_HARD_MAX:
        return None

    # Normalize VV_dB to [0, 1]: -30 dB = dry (0), -5 dB = wet (1)
    wetness = (vv_db_val - (-30.0)) / ((-5.0) - (-30.0))
    wetness = max(0.0, min(1.0, wetness))

    # Adjust with ratio if available (lower ratio = wetter)
    if ratio_val is not None and ratio_val > 0:
        ratio_factor = max(0.0, min(1.0, 1.0 - (ratio_val - 2.0) / 10.0))
        wetness = 0.6 * wetness + 0.4 * ratio_factor

    # Incidence angle correction (larger angle → weaker signal → adjust)
    if incidence_angle is not None:
        if 30.0 <= incidence_angle <= 45.0:
            pass  # Normal range, no correction
        elif incidence_angle < 30.0:
            wetness *= 0.9  # Steeper → some overestimation
        elif incidence_angle > 45.0:
            wetness *= 0.85  # Shallow → signal weaker

    return round(max(0.0, min(1.0, wetness)), 4)


def structure_proxy(
    vh_db_val: float,
    rvi_val: Optional[float] = None,
) -> Optional[float]:
    """
    SAR-derived vegetation structure proxy [0, 1].

    Higher VH (more biomass) + higher RVI (more randomness) → higher structure.
    """
    if vh_db_val < VH_DB_HARD_MIN or vh_db_val > VH_DB_HARD_MAX:
        return None

    # Normalize VH_dB: -30 dB = bare (0), -10 dB = dense canopy (1)
    struct = (vh_db_val - (-30.0)) / ((-10.0) - (-30.0))
    struct = max(0.0, min(1.0, struct))

    # Adjust with RVI if available
    if rvi_val is not None:
        rvi_norm = max(0.0, min(1.0, rvi_val / 1.5))
        struct = 0.6 * struct + 0.4 * rvi_norm

    return round(max(0.0, min(1.0, struct)), 4)


def flood_score(
    vv_db_val: float,
    vh_db_val: float,
    span_val: Optional[float] = None,
) -> Optional[float]:
    """
    SAR-derived flood/water score [0, 1].

    Low VV + low VH + low span → high flood score.
    This is a packet-only feature — NOT for direct Kalman update.
    """
    if vv_db_val < VV_DB_HARD_MIN or vh_db_val < VH_DB_HARD_MIN:
        return None

    # Strong water signal: very low VV and very low VH
    vv_water = max(0.0, min(1.0, (-15.0 - vv_db_val) / 10.0))
    vh_water = max(0.0, min(1.0, (-20.0 - vh_db_val) / 10.0))

    score = 0.5 * vv_water + 0.5 * vh_water

    # Span can reinforce
    if span_val is not None and span_val > 0:
        span_db = 10.0 * math.log10(span_val) if span_val > 0 else -50.0
        if span_db < -15.0:
            score = min(1.0, score * 1.2)

    return round(max(0.0, min(1.0, score)), 4)


def roughness_proxy(
    vv_db_val: float,
    vh_db_val: float,
) -> Optional[float]:
    """
    SAR-derived surface roughness proxy.

    High VV + low VH under bare context → rough surface.
    Packet-only in V1 — very context dependent.
    """
    if vv_db_val < VV_DB_HARD_MIN or vh_db_val < VH_DB_HARD_MIN:
        return None

    # Rough surface: higher VV relative to VH
    diff = vv_db_val - vh_db_val
    rough = max(0.0, min(1.0, (diff - 5.0) / 15.0))
    return round(rough, 4)


# ============================================================================
# Raster-level feature computation
# ============================================================================

def compute_feature_raster(
    feature_name: str,
    vv_raster: SARRaster2D,
    vh_raster: SARRaster2D,
    valid_mask: Optional[List[List[int]]] = None,
    incidence_raster: Optional[List[List[Optional[float]]]] = None,
) -> Tuple[SARRaster2D, SARFeatureDiagnostics]:
    """
    Compute a feature raster from VV/VH linear power rasters.

    Returns (feature_raster, diagnostics).
    """
    h, w = vv_raster.grid_shape
    diag = SARFeatureDiagnostics(total_pixels=h * w)

    out_values: List[List[Optional[float]]] = [[None] * w for _ in range(h)]
    out_valid: List[List[int]] = [[0] * w for _ in range(h)]

    # Determine output unit
    unit_map = {
        "VV_DB": "db", "VH_DB": "db", "VV_VH_RATIO": "ratio",
        "VV_MINUS_VH_DB": "db", "SPAN": "linear_power", "RVI": "ratio",
        "CROSS_POL_FRACTION": "ratio", "SURFACE_WETNESS_PROXY": "score",
        "STRUCTURE_PROXY": "score", "FLOOD_SCORE": "score",
        "ROUGHNESS_PROXY": "score",
    }
    output_unit = unit_map.get(feature_name, "score")

    for r in range(h):
        for c in range(w):
            if valid_mask and not valid_mask[r][c]:
                continue

            vv = vv_raster.values[r][c] if r < len(vv_raster.values) and c < len(vv_raster.values[r]) else None
            vh = vh_raster.values[r][c] if r < len(vh_raster.values) and c < len(vh_raster.values[r]) else None

            if vv is None or vh is None or vv <= 0 or vh <= 0:
                continue

            diag.valid_input_pixels += 1

            vv_db_val = to_db(vv)
            vh_db_val = to_db(vh)
            if vv_db_val is None or vh_db_val is None:
                continue

            result = None

            if feature_name == "VV_DB":
                if VV_DB_HARD_MIN <= vv_db_val <= VV_DB_HARD_MAX:
                    result = round(vv_db_val, 4)
                    if not (VV_DB_SOFT_MIN <= vv_db_val <= VV_DB_SOFT_MAX):
                        diag.out_of_soft_range += 1
                else:
                    diag.out_of_hard_range += 1

            elif feature_name == "VH_DB":
                if VH_DB_HARD_MIN <= vh_db_val <= VH_DB_HARD_MAX:
                    result = round(vh_db_val, 4)
                    if not (VH_DB_SOFT_MIN <= vh_db_val <= VH_DB_SOFT_MAX):
                        diag.out_of_soft_range += 1
                else:
                    diag.out_of_hard_range += 1

            elif feature_name == "VV_VH_RATIO":
                result = ratio_linear(vv, vh)

            elif feature_name == "VV_MINUS_VH_DB":
                result = vv_minus_vh_db(vv_db_val, vh_db_val)

            elif feature_name == "SPAN":
                result = span(vv, vh)

            elif feature_name == "RVI":
                result = rvi_dual_pol(vv, vh)
                if result is not None and result > RVI_SOFT_MAX:
                    diag.out_of_soft_range += 1
                    if "RVI_HIGH_UNCERTAINTY" not in diag.flags:
                        diag.flags.append("RVI_HIGH_UNCERTAINTY")

            elif feature_name == "CROSS_POL_FRACTION":
                result = cross_pol_fraction(vv, vh)

            elif feature_name == "SURFACE_WETNESS_PROXY":
                ratio_val = ratio_linear(vv, vh)
                inc = None
                if incidence_raster and r < len(incidence_raster) and c < len(incidence_raster[r]):
                    inc = incidence_raster[r][c]
                result = surface_wetness_proxy(vv_db_val, ratio_val, inc)

            elif feature_name == "STRUCTURE_PROXY":
                rvi_val = rvi_dual_pol(vv, vh)
                result = structure_proxy(vh_db_val, rvi_val)

            elif feature_name == "FLOOD_SCORE":
                span_val = span(vv, vh)
                result = flood_score(vv_db_val, vh_db_val, span_val)

            elif feature_name == "ROUGHNESS_PROXY":
                result = roughness_proxy(vv_db_val, vh_db_val)

            if result is not None:
                out_values[r][c] = result
                out_valid[r][c] = 1
                diag.valid_output_pixels += 1

    result_raster = SARRaster2D(
        values=out_values,
        valid_mask=out_valid,
        unit=output_unit,
        resolution_m=vv_raster.resolution_m,
        aligned_to_plot_grid=vv_raster.aligned_to_plot_grid,
        grid_shape=(h, w),
        crs=vv_raster.crs,
    )

    return result_raster, diag
