"""
Layer 0 — Data-Driven Weakness Score Raster & Zone Derivation.

Computes a per-pixel weakness score from real spectral data (NDVI/EVI, NDMI),
strictly alpha-masked to the field polygon. Zones emerge from where
the data shows weakness — not from arbitrary geometry.

Adaptive VI selection:
  When field-mean NDVI > 0.80 (saturation zone), the engine automatically
  switches to EVI as the primary vegetation index. EVI does not saturate
  in dense, high-biomass canopies (e.g. late-stage corn, tropical crops),
  preserving spatial variance that NDVI would lose.

WSR ∈ [0, 1]:
  0.0 = pixel at or above field mean (healthy)
  1.0 = maximum weakness (far below mean, stressed, contaminated)

Components:
  - VI deviation  (weight 0.50): below-mean pixels get positive score
  - NDMI stress   (weight 0.30): negative NDMI = water stress
  - Edge contamination (weight 0.20): partial-alpha boundary pixels
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from layer0.sentinel2.schemas import Raster2D


# ── Configuration ─────────────────────────────────────────────────────────────

W_NDVI_DEVIATION = 0.50      # Weight for primary VI (NDVI or EVI) deviation
W_NDMI_STRESS = 0.30
W_EDGE_CONTAMINATION = 0.20

MIN_ZONE_CELLS = 4
MAX_ZONES = 5
MIN_VALID_PIXELS = 8       # Need at least this many valid pixels to attempt
HOMOGENEITY_THRESHOLD = 0.02  # If VI std < this, field is homogeneous

# When field-mean NDVI exceeds this, switch to EVI to avoid saturation
EVI_SATURATION_THRESHOLD = 0.80


# ── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class WeaknessRaster:
    """Per-pixel weakness score, strictly alpha-masked."""
    values: List[List[Optional[float]]] = field(default_factory=list)
    height: int = 0
    width: int = 0
    valid_pixel_count: int = 0

    # Field-level baselines used for normalization
    field_mean_ndvi: Optional[float] = None
    field_std_ndvi: Optional[float] = None
    field_range_ndvi: Optional[float] = None  # p90 - p10

    # Summary stats of the WSR itself
    weakness_mean: float = 0.0
    weakness_p90: float = 0.0
    weakness_max: float = 0.0

    # Provenance: which vegetation index was actually used
    primary_vi_used: str = "NDVI"       # "NDVI" or "EVI"
    evi_fallback_triggered: bool = False  # True if NDVI saturation caused EVI switch
    ndvi_mean_pre_switch: Optional[float] = None  # Original NDVI mean (when EVI used)


@dataclass
class ZoneDerivation:
    """Result of zone derivation from a weakness raster."""
    zone_masks: Dict[str, List[List[float]]] = field(default_factory=dict)
    zone_method: str = "auto_quadrant_v1"
    zone_source: str = "geometry_fallback"
    zone_confidence: float = 0.25

    # Retained for downstream consumers
    weakness_raster: Optional[WeaknessRaster] = None
    n_zones: int = 0
    fallback_used: bool = True


# ── Core: Weakness Raster Computation ─────────────────────────────────────────

def _alpha_weighted_field_stats(
    raster_values: List[List[Optional[float]]],
    alpha_mask: List[List[float]],
    valid_mask: Optional[List[List[int]]] = None,
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """Compute alpha-weighted mean, std, p10, p90 across the field."""
    weighted = []
    h = len(alpha_mask)
    w = len(alpha_mask[0]) if alpha_mask else 0

    for r in range(h):
        for c in range(w):
            a = alpha_mask[r][c] if r < len(alpha_mask) and c < len(alpha_mask[r]) else 0.0
            if a <= 0:
                continue
            if valid_mask and (r >= len(valid_mask) or c >= len(valid_mask[r]) or not valid_mask[r][c]):
                continue
            v = raster_values[r][c] if r < len(raster_values) and c < len(raster_values[r]) else None
            if v is None:
                continue
            weighted.append((v, a))

    if not weighted:
        return None, None, None, None

    total_w = sum(w for _, w in weighted)
    mean = sum(v * w for v, w in weighted) / total_w

    var = sum(w * (v - mean) ** 2 for v, w in weighted) / total_w
    std = math.sqrt(max(0.0, var))

    sorted_wv = sorted(weighted, key=lambda x: x[0])
    cum = 0.0
    p10 = sorted_wv[0][0]
    p90 = sorted_wv[-1][0]
    for v, w in sorted_wv:
        cum += w
        if cum / total_w >= 0.10 and p10 == sorted_wv[0][0]:
            p10 = v
        if cum / total_w >= 0.90:
            p90 = v
            break

    return mean, std, p10, p90


def compute_weakness_raster(
    ndvi_raster: Raster2D,
    alpha_mask: List[List[float]],
    valid_mask: List[List[int]],
    ndmi_raster: Optional[Raster2D] = None,
    evi_raster: Optional[Raster2D] = None,
    buffer_pixels: int = 2,
) -> WeaknessRaster:
    """
    Compute per-pixel weakness score, strictly alpha-masked to the field polygon.

    Adaptive VI selection:
      - Uses NDVI as primary vegetation index by default.
      - When field-mean NDVI > 0.80 AND EVI is available, automatically
        switches to EVI to avoid saturation in dense canopies.

    Args:
        ndvi_raster: NDVI index raster (from S2 engine)
        alpha_mask: PlotGrid fractional coverage mask
        valid_mask: SCL-derived valid-for-index mask
        ndmi_raster: Optional NDMI raster (adds water stress component)
        evi_raster: Optional EVI raster (used when NDVI saturates)
        buffer_pixels: Edge contamination buffer distance

    Returns:
        WeaknessRaster with per-pixel scores and field-level baselines
    """
    h = len(alpha_mask)
    w = len(alpha_mask[0]) if alpha_mask else 0

    wsr = WeaknessRaster(
        values=[[None] * w for _ in range(h)],
        height=h,
        width=w,
    )

    # 1. Compute field-level NDVI baselines (always needed for saturation check)
    ndvi_mean, ndvi_std, ndvi_p10, ndvi_p90 = _alpha_weighted_field_stats(
        ndvi_raster.values, alpha_mask, valid_mask,
    )
    if ndvi_mean is None:
        return wsr  # No valid data

    # 2. Adaptive VI selection: switch to EVI when NDVI saturates
    use_evi = False
    vi_raster = ndvi_raster
    vi_mean = ndvi_mean
    vi_std = ndvi_std
    vi_range = (ndvi_p90 - ndvi_p10) if (ndvi_p90 is not None and ndvi_p10 is not None) else 0.01

    if ndvi_mean >= EVI_SATURATION_THRESHOLD and evi_raster is not None:
        evi_mean, evi_std, evi_p10, evi_p90 = _alpha_weighted_field_stats(
            evi_raster.values, alpha_mask, valid_mask,
        )
        if evi_mean is not None and evi_std is not None:
            # EVI has more spatial variance than NDVI in this saturated regime
            # → better zone discrimination
            use_evi = True
            vi_raster = evi_raster
            vi_mean = evi_mean
            vi_std = evi_std
            vi_range = (evi_p90 - evi_p10) if (evi_p90 is not None and evi_p10 is not None) else 0.01

    vi_range = max(vi_range, 0.01)  # Prevent division by zero

    wsr.field_mean_ndvi = round(vi_mean, 6)
    wsr.field_std_ndvi = round(vi_std, 6)
    wsr.field_range_ndvi = round(vi_range, 6)
    wsr.primary_vi_used = "EVI" if use_evi else "NDVI"
    wsr.evi_fallback_triggered = use_evi
    wsr.ndvi_mean_pre_switch = round(ndvi_mean, 6) if use_evi else None

    # 3. Optional: NDMI baselines
    ndmi_mean = None
    ndmi_range = 1.0
    if ndmi_raster is not None:
        nm, ns, np10, np90 = _alpha_weighted_field_stats(
            ndmi_raster.values, alpha_mask, valid_mask,
        )
        if nm is not None:
            ndmi_mean = nm
            ndmi_range = max(0.01, (np90 - np10) if np90 is not None and np10 is not None else 1.0)

    # 4. Per-pixel weakness computation
    valid_count = 0
    weakness_vals = []

    for r in range(h):
        for c in range(w):
            a = alpha_mask[r][c] if r < len(alpha_mask) and c < len(alpha_mask[r]) else 0.0
            if a <= 0:
                continue  # Strict masking: outside polygon = None
            if valid_mask and (r >= len(valid_mask) or c >= len(valid_mask[r]) or not valid_mask[r][c]):
                continue

            vi_val = vi_raster.values[r][c] if r < len(vi_raster.values) and c < len(vi_raster.values[r]) else None
            if vi_val is None:
                continue

            # Component 1: VI deviation (below mean = positive weakness)
            vi_dev = max(0.0, (vi_mean - vi_val) / vi_range)
            vi_component = min(1.0, vi_dev)

            # Component 2: NDMI stress (negative NDMI = water stress)
            ndmi_component = 0.0
            if ndmi_raster is not None and ndmi_mean is not None:
                ndmi_val = ndmi_raster.values[r][c] if r < len(ndmi_raster.values) and c < len(ndmi_raster.values[r]) else None
                if ndmi_val is not None:
                    # More negative than field mean = more stressed
                    ndmi_dev = max(0.0, (ndmi_mean - ndmi_val) / ndmi_range)
                    ndmi_component = min(1.0, ndmi_dev)

            # Component 3: Edge contamination (partial alpha + near boundary)
            edge_component = 0.0
            if a < 1.0:
                # Partial boundary pixel: higher weakness for lower alpha
                edge_component = 1.0 - a
            elif buffer_pixels > 0:
                # Full pixel but near boundary: check neighbor alphas
                near_boundary = False
                for dr in range(-buffer_pixels, buffer_pixels + 1):
                    for dc in range(-buffer_pixels, buffer_pixels + 1):
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < h and 0 <= nc < w:
                            na = alpha_mask[nr][nc] if nr < len(alpha_mask) and nc < len(alpha_mask[nr]) else 0.0
                            if na < 0.5:
                                near_boundary = True
                                break
                    if near_boundary:
                        break
                if near_boundary:
                    edge_component = 0.3  # Near-boundary penalty

            # Weighted combination
            if ndmi_raster is not None and ndmi_mean is not None:
                score = (
                    W_NDVI_DEVIATION * vi_component
                    + W_NDMI_STRESS * ndmi_component
                    + W_EDGE_CONTAMINATION * edge_component
                )
            else:
                # No NDMI: redistribute weight to VI
                score = (
                    (W_NDVI_DEVIATION + W_NDMI_STRESS) * vi_component
                    + W_EDGE_CONTAMINATION * edge_component
                )

            score = round(max(0.0, min(1.0, score)), 4)
            wsr.values[r][c] = score
            valid_count += 1
            weakness_vals.append(score)

    wsr.valid_pixel_count = valid_count

    if weakness_vals:
        wsr.weakness_mean = round(sum(weakness_vals) / len(weakness_vals), 4)
        wsr.weakness_max = round(max(weakness_vals), 4)
        sorted_wv = sorted(weakness_vals)
        p90_idx = min(len(sorted_wv) - 1, int(len(sorted_wv) * 0.90))
        wsr.weakness_p90 = round(sorted_wv[p90_idx], 4)

    return wsr


# ── Core: Zone Derivation from Weakness Raster ───────────────────────────────

def _connected_components(
    label_grid: List[List[int]],
    h: int, w: int,
    target_label: int,
) -> List[List[Tuple[int, int]]]:
    """Extract connected components for a label via BFS (4-connectivity)."""
    visited = [[False] * w for _ in range(h)]
    components = []

    for r in range(h):
        for c in range(w):
            if label_grid[r][c] == target_label and not visited[r][c]:
                queue = [(r, c)]
                visited[r][c] = True
                component = []
                while queue:
                    cr, cc = queue.pop(0)
                    component.append((cr, cc))
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = cr + dr, cc + dc
                        if 0 <= nr < h and 0 <= nc < w and not visited[nr][nc] and label_grid[nr][nc] == target_label:
                            visited[nr][nc] = True
                            queue.append((nr, nc))
                components.append(component)

    return components


def generate_quadrant_zones(
    alpha_mask: List[List[float]],
) -> Dict[str, List[List[float]]]:
    """
    Fallback: 2×2 quadrant zone masks from alpha mask.
    Canonical implementation — S2 and S1 both delegate here.
    """
    h = len(alpha_mask)
    w = len(alpha_mask[0]) if alpha_mask else 0
    mid_r = h // 2
    mid_c = w // 2

    zones = {}
    for name, r0, r1, c0, c1 in [
        ("zone_NW", 0, mid_r, 0, mid_c),
        ("zone_NE", 0, mid_r, mid_c, w),
        ("zone_SW", mid_r, h, 0, mid_c),
        ("zone_SE", mid_r, h, mid_c, w),
    ]:
        zone_alpha = [[0.0] * w for _ in range(h)]
        for r in range(r0, r1):
            for c in range(c0, c1):
                zone_alpha[r][c] = alpha_mask[r][c] if r < len(alpha_mask) and c < len(alpha_mask[r]) else 0.0
        zones[name] = zone_alpha

    return zones


def derive_zones_from_weakness(
    weakness: WeaknessRaster,
    alpha_mask: List[List[float]],
    min_zone_cells: int = MIN_ZONE_CELLS,
    max_zones: int = MAX_ZONES,
) -> ZoneDerivation:
    """
    Derive spatial zones from the weakness raster via quantile banding
    + connected component extraction.

    Falls back to quadrant zones if the field is too homogeneous or
    has insufficient valid data.
    """
    h = weakness.height
    w = weakness.width

    # Guard: insufficient data → fallback
    if weakness.valid_pixel_count < MIN_VALID_PIXELS:
        return ZoneDerivation(
            zone_masks=generate_quadrant_zones(alpha_mask),
            zone_method="auto_quadrant_v1",
            zone_source="geometry_fallback",
            zone_confidence=0.25,
            weakness_raster=weakness,
            n_zones=4,
            fallback_used=True,
        )

    # Guard: homogeneous field (low NDVI std) → fallback
    if weakness.field_std_ndvi is not None and weakness.field_std_ndvi < HOMOGENEITY_THRESHOLD:
        return ZoneDerivation(
            zone_masks=generate_quadrant_zones(alpha_mask),
            zone_method="auto_quadrant_v1",
            zone_source="geometry_fallback",
            zone_confidence=0.25,
            weakness_raster=weakness,
            n_zones=4,
            fallback_used=True,
        )

    # Collect valid WSR values for quantile computation
    valid_vals = []
    for r in range(h):
        for c in range(w):
            v = weakness.values[r][c]
            if v is not None:
                valid_vals.append(v)

    if len(valid_vals) < MIN_VALID_PIXELS:
        return ZoneDerivation(
            zone_masks=generate_quadrant_zones(alpha_mask),
            zone_method="auto_quadrant_v1",
            zone_source="geometry_fallback",
            zone_confidence=0.25,
            weakness_raster=weakness,
            n_zones=4,
            fallback_used=True,
        )

    # Quantile banding: split into 3 bands
    sorted_vals = sorted(valid_vals)
    n = len(sorted_vals)
    p33 = sorted_vals[n // 3]
    p67 = sorted_vals[min(n - 1, 2 * n // 3)]

    # Prevent degenerate bands (all same value)
    if p33 == p67:
        return ZoneDerivation(
            zone_masks=generate_quadrant_zones(alpha_mask),
            zone_method="auto_quadrant_v1",
            zone_source="geometry_fallback",
            zone_confidence=0.25,
            weakness_raster=weakness,
            n_zones=4,
            fallback_used=True,
        )

    # Label grid: 0=healthy, 1=moderate, 2=weak, -1=nodata
    label_grid = [[-1] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            v = weakness.values[r][c]
            if v is None:
                continue
            if v < p33:
                label_grid[r][c] = 0  # Healthy
            elif v < p67:
                label_grid[r][c] = 1  # Moderate
            else:
                label_grid[r][c] = 2  # Weak

    # Extract connected components per band
    all_components = []
    band_names = ["healthy", "moderate", "weak"]
    for band_label in range(3):
        components = _connected_components(label_grid, h, w, band_label)
        for comp in components:
            if len(comp) >= min_zone_cells:
                all_components.append((band_names[band_label], comp))

    # Sort by size descending, cap at max_zones
    all_components.sort(key=lambda x: len(x[1]), reverse=True)
    all_components = all_components[:max_zones]

    # Need at least 2 zones for meaningful spatial differentiation
    if len(all_components) < 2:
        return ZoneDerivation(
            zone_masks=generate_quadrant_zones(alpha_mask),
            zone_method="auto_quadrant_v1",
            zone_source="geometry_fallback",
            zone_confidence=0.25,
            weakness_raster=weakness,
            n_zones=4,
            fallback_used=True,
        )

    # Build zone masks (alpha-weighted)
    zone_masks = {}
    for i, (band_name, cells) in enumerate(all_components):
        zone_id = f"zone_{band_name}_{i}"
        mask = [[0.0] * w for _ in range(h)]
        for r, c in cells:
            mask[r][c] = alpha_mask[r][c] if r < len(alpha_mask) and c < len(alpha_mask[r]) else 0.0
        zone_masks[zone_id] = mask

    return ZoneDerivation(
        zone_masks=zone_masks,
        zone_method="weakness_quantile_v1",
        zone_source="data_derived",
        zone_confidence=0.70,
        weakness_raster=weakness,
        n_zones=len(zone_masks),
        fallback_used=False,
    )


# ── SAR Weakness (simplified for S1) ─────────────────────────────────────────

def compute_weakness_raster_sar(
    vv_db_raster: "SARRaster2D",
    alpha_mask: List[List[float]],
    buffer_pixels: int = 2,
) -> WeaknessRaster:
    """
    Simplified weakness raster from SAR VV_DB.

    Lower VV_dB relative to field mean = wetter → higher weakness.
    (In most agricultural contexts, anomalously wet patches indicate
    drainage issues, waterlogging, or flooding.)
    """
    h = len(alpha_mask)
    w = len(alpha_mask[0]) if alpha_mask else 0

    wsr = WeaknessRaster(
        values=[[None] * w for _ in range(h)],
        height=h,
        width=w,
    )

    # Valid mask from the raster itself
    vv_valid = vv_db_raster.valid_mask if vv_db_raster.valid_mask else None

    # Field-level stats
    mean_vv, std_vv, p10_vv, p90_vv = _alpha_weighted_field_stats(
        vv_db_raster.values, alpha_mask, vv_valid,
    )
    if mean_vv is None:
        return wsr

    vv_range = max(0.01, (p90_vv - p10_vv) if p90_vv is not None and p10_vv is not None else 1.0)

    wsr.field_mean_ndvi = round(mean_vv, 6)  # Reusing field for SAR
    wsr.field_std_ndvi = round(std_vv, 6)
    wsr.field_range_ndvi = round(vv_range, 6)

    valid_count = 0
    weakness_vals = []

    for r in range(h):
        for c in range(w):
            a = alpha_mask[r][c] if r < len(alpha_mask) and c < len(alpha_mask[r]) else 0.0
            if a <= 0:
                continue
            if vv_valid and (r >= len(vv_valid) or c >= len(vv_valid[r]) or not vv_valid[r][c]):
                continue

            vv_val = vv_db_raster.values[r][c] if r < len(vv_db_raster.values) and c < len(vv_db_raster.values[r]) else None
            if vv_val is None:
                continue

            # Anomalous = deviates from field mean (either direction)
            deviation = abs(vv_val - mean_vv) / vv_range
            score = min(1.0, deviation)

            # Edge penalty
            edge = 0.0
            if a < 1.0:
                edge = (1.0 - a) * 0.3

            score = round(max(0.0, min(1.0, 0.80 * score + 0.20 * edge)), 4)
            wsr.values[r][c] = score
            valid_count += 1
            weakness_vals.append(score)

    wsr.valid_pixel_count = valid_count

    if weakness_vals:
        wsr.weakness_mean = round(sum(weakness_vals) / len(weakness_vals), 4)
        wsr.weakness_max = round(max(weakness_vals), 4)
        sorted_wv = sorted(weakness_vals)
        p90_idx = min(len(sorted_wv) - 1, int(len(sorted_wv) * 0.90))
        wsr.weakness_p90 = round(sorted_wv[p90_idx], 4)

    return wsr

