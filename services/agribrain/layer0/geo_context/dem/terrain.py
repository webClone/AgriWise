"""
DEM Terrain Feature Extraction.

Computes 17+ terrain features from a validated DEM raster using NumPy.
All proxy features are explicitly labeled (Revision 3).
DEM coarseness is accounted for (Revision 4).
All summaries are alpha-weighted (Revision 2).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from layer0.geo_context.schemas import RasterInput, alpha_weighted_mean, alpha_weighted_std
from layer0.geo_context.dem.schemas import DEMContext, DEMQAResult, DEMQualityClass


# Aspect sector labels (8 cardinal + intercardinal)
ASPECT_SECTORS = {
    "N": (337.5, 22.5), "NE": (22.5, 67.5), "E": (67.5, 112.5),
    "SE": (112.5, 157.5), "S": (157.5, 202.5), "SW": (202.5, 247.5),
    "W": (247.5, 292.5), "NW": (292.5, 337.5),
}


def compute_terrain_features(
    dem: RasterInput,
    source: str = "copernicus_dem",
) -> DEMContext:
    """Compute all terrain features from a validated DEM raster.

    Returns DEMContext with all fields populated, including QA.
    """
    elev = dem.data
    valid = dem.valid_mask
    alpha = dem.alpha_mask
    res = dem.resolution_m

    # --- Elevation statistics (alpha-weighted, Revision 2) ---
    elev_mean = alpha_weighted_mean(elev, valid, alpha)
    elev_std = alpha_weighted_std(elev, valid, alpha)

    valid_elev = elev[valid]
    elev_min = float(valid_elev.min()) if valid_elev.size > 0 else None
    elev_max = float(valid_elev.max()) if valid_elev.size > 0 else None

    # --- Slope & Aspect via numpy gradients ---
    slope_deg, aspect_deg = _compute_slope_aspect(elev, valid, res)

    slope_mean = alpha_weighted_mean(slope_deg, valid, alpha)
    valid_slope = slope_deg[valid]
    slope_p90 = float(np.percentile(valid_slope, 90)) if valid_slope.size > 0 else None
    slope_max = float(valid_slope.max()) if valid_slope.size > 0 else None

    # --- Aspect distribution ---
    aspect_dom, aspect_dist = _compute_aspect_distribution(aspect_deg, valid, alpha)

    # --- Curvature proxy (Revision 3 label) ---
    curvature = _compute_curvature_proxy(elev, valid, res)
    curvature_mean = alpha_weighted_mean(curvature, valid, alpha)

    # --- TWI proxy (Revision 3 label) ---
    twi = _compute_twi_proxy(slope_deg, valid, res)
    twi_mean = alpha_weighted_mean(twi, valid, alpha)

    # --- Low-spot / ridge fraction ---
    low_frac = _compute_low_spot_fraction(elev, valid, alpha)
    ridge_frac = _compute_ridge_fraction(elev, valid, alpha)

    # --- Risk scores ---
    runoff = _compute_runoff_risk(slope_mean, slope_p90, elev_std)
    erosion = _compute_erosion_risk(slope_mean, slope_max)
    cold_air = _compute_cold_air_pooling_risk(low_frac, elev_std)
    irrig_unif = _compute_irrigation_uniformity_risk(slope_mean, elev_std, slope_p90)

    # --- QA (Revision 4) ---
    qa = _compute_dem_qa(dem)

    return DEMContext(
        elevation_mean=elev_mean,
        elevation_min=elev_min,
        elevation_max=elev_max,
        elevation_std=elev_std,
        slope_mean=slope_mean,
        slope_p90=slope_p90,
        slope_max=slope_max,
        aspect_dominant=aspect_dom,
        aspect_distribution=aspect_dist,
        curvature_proxy=curvature_mean,
        flow_accumulation_proxy=None,  # requires full routing — omit in V1
        topographic_wetness_proxy=twi_mean,
        low_spot_fraction=low_frac,
        ridge_fraction=ridge_frac,
        runoff_risk_score=runoff,
        erosion_risk_score=erosion,
        cold_air_pooling_risk=cold_air,
        irrigation_uniformity_risk=irrig_unif,
        qa=qa,
        source=source,
        resolution_m=dem.resolution_m,
    )


# ---------------------------------------------------------------------------
# Internal computation functions
# ---------------------------------------------------------------------------

def _compute_slope_aspect(
    elev: np.ndarray, valid: np.ndarray, res: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute slope (degrees) and aspect (degrees, 0=N clockwise) via gradients."""
    dy, dx = np.gradient(elev, res)

    slope_rad = np.arctan(np.sqrt(dx**2 + dy**2))
    slope_deg = np.degrees(slope_rad)

    # Aspect: atan2(-dy, dx) gives math convention; convert to geographic (0=N CW)
    aspect_math = np.degrees(np.arctan2(-dy, dx))
    aspect_geo = (90.0 - aspect_math) % 360.0

    # Mask invalid regions
    slope_deg = np.where(valid, slope_deg, 0.0)
    aspect_geo = np.where(valid, aspect_geo, 0.0)

    return slope_deg, aspect_geo


def _compute_aspect_distribution(
    aspect_deg: np.ndarray, valid: np.ndarray,
    alpha: Optional[np.ndarray],
) -> Tuple[Optional[float], Dict[str, float]]:
    """Compute dominant aspect and 8-sector distribution."""
    valid_aspects = aspect_deg[valid]
    if valid_aspects.size == 0:
        return None, {}

    # Weighted histogram over 8 sectors
    dist: Dict[str, float] = {}
    weights = alpha[valid] if alpha is not None else np.ones_like(valid_aspects)
    total_weight = weights.sum()
    if total_weight == 0:
        return None, {}

    for sector, (lo, hi) in ASPECT_SECTORS.items():
        if sector == "N":
            mask = (valid_aspects >= lo) | (valid_aspects < hi)
        else:
            mask = (valid_aspects >= lo) & (valid_aspects < hi)
        dist[sector] = float(weights[mask].sum() / total_weight)

    # Dominant = sector with highest fraction
    dominant_sector = max(dist, key=dist.get)
    # Convert sector to representative angle
    sector_angles = {"N": 0, "NE": 45, "E": 90, "SE": 135,
                     "S": 180, "SW": 225, "W": 270, "NW": 315}
    dominant_angle = float(sector_angles[dominant_sector])

    return dominant_angle, dist


def _compute_curvature_proxy(
    elev: np.ndarray, valid: np.ndarray, res: float,
) -> np.ndarray:
    """Curvature proxy via second derivatives (Laplacian)."""
    dy, dx = np.gradient(elev, res)
    dyy, _ = np.gradient(dy, res)
    _, dxx = np.gradient(dx, res)
    curvature = dxx + dyy
    return np.where(valid, curvature, 0.0)


def _compute_twi_proxy(
    slope_deg: np.ndarray, valid: np.ndarray, res: float,
) -> np.ndarray:
    """Topographic Wetness Index proxy: ln(a / tan(slope)).

    Uses pixel area as proxy for contributing area (true TWI requires
    full flow routing). This is explicitly a PROXY, not a hydrological model.
    Diagnostic flag: TWI_PROXY_NOT_HYDROLOGICAL_MODEL
    """
    pixel_area = res * res
    slope_rad = np.radians(np.maximum(slope_deg, 0.1))  # avoid log(0)
    tan_slope = np.tan(slope_rad)
    tan_slope = np.maximum(tan_slope, 1e-6)
    twi = np.log(pixel_area / tan_slope)
    return np.where(valid, twi, 0.0)


def _compute_low_spot_fraction(
    elev: np.ndarray, valid: np.ndarray,
    alpha: Optional[np.ndarray],
) -> float:
    """Fraction of pixels that are local minima (3x3 neighborhood)."""
    if valid.sum() < 4:
        return 0.0

    h, w = elev.shape
    is_low = np.zeros_like(elev, dtype=bool)

    # Pad for boundary handling
    padded = np.pad(elev, 1, mode="edge")
    padded_valid = np.pad(valid, 1, mode="constant", constant_values=False)

    for di in range(-1, 2):
        for dj in range(-1, 2):
            if di == 0 and dj == 0:
                continue
            neighbor = padded[1 + di:h + 1 + di, 1 + dj:w + 1 + dj]
            neighbor_valid = padded_valid[1 + di:h + 1 + di, 1 + dj:w + 1 + dj]
            # A pixel is NOT a local min if any valid neighbor is lower
            is_low = is_low | (neighbor_valid & (neighbor < elev))

    # Local min = valid AND no valid neighbor is lower
    local_min = valid & ~is_low

    weights = alpha if alpha is not None else np.ones_like(elev, dtype=float)
    denom = (weights * valid.astype(float)).sum()
    if denom == 0:
        return 0.0
    return float((weights * local_min.astype(float)).sum() / denom)


def _compute_ridge_fraction(
    elev: np.ndarray, valid: np.ndarray,
    alpha: Optional[np.ndarray],
) -> float:
    """Fraction of pixels that are local maxima (3x3 neighborhood)."""
    if valid.sum() < 4:
        return 0.0

    h, w = elev.shape
    is_high = np.zeros_like(elev, dtype=bool)

    padded = np.pad(elev, 1, mode="edge")
    padded_valid = np.pad(valid, 1, mode="constant", constant_values=False)

    for di in range(-1, 2):
        for dj in range(-1, 2):
            if di == 0 and dj == 0:
                continue
            neighbor = padded[1 + di:h + 1 + di, 1 + dj:w + 1 + dj]
            neighbor_valid = padded_valid[1 + di:h + 1 + di, 1 + dj:w + 1 + dj]
            is_high = is_high | (neighbor_valid & (neighbor > elev))

    local_max = valid & ~is_high

    weights = alpha if alpha is not None else np.ones_like(elev, dtype=float)
    denom = (weights * valid.astype(float)).sum()
    if denom == 0:
        return 0.0
    return float((weights * local_max.astype(float)).sum() / denom)


# ---------------------------------------------------------------------------
# Risk scores
# ---------------------------------------------------------------------------

def _compute_runoff_risk(
    slope_mean: Optional[float], slope_p90: Optional[float],
    elev_std: Optional[float],
) -> float:
    """Runoff risk from slope steepness and elevation variability."""
    if slope_mean is None:
        return 0.0
    # Heuristic: steep + variable = high runoff
    slope_factor = min((slope_mean or 0) / 15.0, 1.0)
    variability = min((elev_std or 0) / 10.0, 1.0)
    return round(min(0.6 * slope_factor + 0.4 * variability, 1.0), 4)


def _compute_erosion_risk(
    slope_mean: Optional[float], slope_max: Optional[float],
) -> float:
    """Erosion risk from slope severity."""
    if slope_mean is None:
        return 0.0
    mean_factor = min((slope_mean or 0) / 20.0, 1.0)
    max_factor = min((slope_max or 0) / 30.0, 1.0)
    return round(min(0.5 * mean_factor + 0.5 * max_factor, 1.0), 4)


def _compute_cold_air_pooling_risk(
    low_spot_frac: float, elev_std: Optional[float],
) -> float:
    """Cold-air pooling risk from low spots and elevation variability."""
    if elev_std is None or elev_std < 1.0:
        return 0.0
    return round(min(low_spot_frac * min(elev_std / 5.0, 1.0), 1.0), 4)


def _compute_irrigation_uniformity_risk(
    slope_mean: Optional[float], elev_std: Optional[float],
    slope_p90: Optional[float],
) -> float:
    """Irrigation uniformity risk from terrain variability."""
    if slope_mean is None:
        return 0.0
    slope_factor = min((slope_mean or 0) / 8.0, 1.0)
    p90_factor = min((slope_p90 or 0) / 12.0, 1.0)
    std_factor = min((elev_std or 0) / 5.0, 1.0)
    return round(min(0.4 * slope_factor + 0.3 * p90_factor + 0.3 * std_factor, 1.0), 4)


# ---------------------------------------------------------------------------
# QA (Revision 4)
# ---------------------------------------------------------------------------

def _compute_dem_qa(dem: RasterInput) -> DEMQAResult:
    """Compute DEM QA with pixel-count confidence thresholds."""
    from layer0.geo_context.dem.schemas import MIN_PIXELS_GOOD, MIN_PIXELS_TERRAIN_DERIVATIVES

    total = int(dem.valid_mask.size)
    valid_count = int(dem.valid_mask.sum())
    nan_count = total - valid_count
    valid_frac = valid_count / total if total > 0 else 0.0

    flags: List[str] = []
    quality = DEMQualityClass.GOOD
    terrain_reliable = True
    placement_confidence = 1.0

    if valid_count < MIN_PIXELS_TERRAIN_DERIVATIVES:
        quality = DEMQualityClass.UNUSABLE
        terrain_reliable = False
        placement_confidence = 0.2
        flags.append("SLOPE_UNCERTAIN_SMALL_PLOT")
        flags.append("LOW_TERRAIN_PIXEL_COUNT")
    elif valid_count < MIN_PIXELS_GOOD:
        quality = DEMQualityClass.DEGRADED
        placement_confidence = 0.5
        flags.append("DEM_TOO_COARSE_FOR_FINE_PLACEMENT")
        flags.append("LOW_TERRAIN_PIXEL_COUNT")

    if nan_count > 0:
        flags.append("DEM_HAS_NAN_PIXELS")

    # TWI proxy labeling (Revision 3)
    flags.append("TWI_PROXY_NOT_HYDROLOGICAL_MODEL")

    return DEMQAResult(
        quality_class=quality,
        valid_pixel_count=valid_count,
        total_pixel_count=total,
        valid_fraction=round(valid_frac, 4),
        nan_fraction=round(nan_count / total if total > 0 else 0.0, 4),
        resolution_m=dem.resolution_m,
        terrain_derivatives_reliable=terrain_reliable,
        placement_confidence_factor=placement_confidence,
        flags=flags,
    )
