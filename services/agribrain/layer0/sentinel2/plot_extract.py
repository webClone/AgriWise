"""
Sentinel-2 PlotGrid Extraction & Zone Aggregation.

Bridges index rasters to PlotGrid with:
  - Alpha-weighted means, std, p10/p90
  - Boundary contamination from interior/edge/neighbor masks
  - Per-zone extraction with separate reliability
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from layer0.sentinel2.schemas import (
    Raster2D,
    Sentinel2PlotSummary,
    Sentinel2QAResult,
    Sentinel2ZoneSummary,
)
from layer0.sentinel2.masks import Sentinel2MaskSet


def _alpha_weighted_stats(
    values: List[List[Optional[float]]],
    alpha: List[List[float]],
    valid_mask: Optional[List[List[int]]] = None,
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    Compute alpha-weighted mean, std, p10, p90.
    Returns (mean, std, p10, p90) or (None, None, None, None) if no valid data.
    """
    weighted_vals = []
    weights = []

    h = len(alpha)
    w = len(alpha[0]) if alpha else 0

    for r in range(h):
        for c in range(w):
            a = alpha[r][c] if r < len(alpha) and c < len(alpha[r]) else 0.0
            if a <= 0:
                continue
            if valid_mask and (r >= len(valid_mask) or c >= len(valid_mask[r]) or not valid_mask[r][c]):
                continue
            v = values[r][c] if r < len(values) and c < len(values[r]) else None
            if v is None:
                continue
            weighted_vals.append((v, a))
            weights.append(a)

    if not weighted_vals:
        return None, None, None, None

    total_w = sum(weights)
    mean = sum(v * w for v, w in weighted_vals) / total_w

    # Weighted std
    if len(weighted_vals) > 1:
        var = sum(w * (v - mean) ** 2 for v, w in weighted_vals) / total_w
        std = math.sqrt(max(0.0, var))
    else:
        std = 0.0

    # Approximate alpha-weighted percentiles via sorted values
    sorted_vals = sorted(weighted_vals, key=lambda x: x[0])
    cum_weight = 0.0
    p10 = sorted_vals[0][0]
    p90 = sorted_vals[-1][0]
    for v, w in sorted_vals:
        cum_weight += w
        if cum_weight / total_w >= 0.10 and p10 == sorted_vals[0][0]:
            p10 = v
        if cum_weight / total_w >= 0.90:
            p90 = v
            break

    return (round(mean, 6), round(std, 6), round(p10, 6), round(p90, 6))


def _compute_boundary_contamination(
    index_raster: List[List[Optional[float]]],
    alpha: List[List[float]],
    valid_mask: Optional[List[List[int]]] = None,
    buffer_pixels: int = 2,
) -> Tuple[float, float, float, float]:
    """
    Compute boundary contamination score.

    interior_mask: alpha == 1.0 AND distance_to_boundary > buffer_pixels
    edge_mask: 0 < alpha < 1.0 OR alpha=1 near boundary
    neighbor_buffer: alpha == 0 AND distance_to_plot <= buffer_pixels

    Returns (contamination_score, edge_valid_frac, interior_valid_frac, neighbor_green_pressure)
    """
    h = len(alpha)
    w = len(alpha[0]) if alpha else 0

    if h == 0 or w == 0:
        return 0.0, 0.0, 0.0, 0.0

    # Build distance-to-boundary mask
    # Interior: alpha == 1.0 and all neighbors within buffer also alpha >= 0.5
    interior_vals = []
    interior_weights = []
    edge_vals = []
    edge_weights = []
    neighbor_vals = []

    for r in range(h):
        for c in range(w):
            a = alpha[r][c] if r < len(alpha) and c < len(alpha[r]) else 0.0
            v = index_raster[r][c] if r < len(index_raster) and c < len(index_raster[r]) else None
            vm = valid_mask[r][c] if valid_mask and r < len(valid_mask) and c < len(valid_mask[r]) else 1

            if a >= 1.0:
                # Check if near boundary
                near_boundary = False
                for dr in range(-buffer_pixels, buffer_pixels + 1):
                    for dc in range(-buffer_pixels, buffer_pixels + 1):
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < h and 0 <= nc < w:
                            na = alpha[nr][nc] if nr < len(alpha) and nc < len(alpha[nr]) else 0.0
                            if na < 0.5:
                                near_boundary = True
                                break
                    if near_boundary:
                        break

                if near_boundary:
                    if v is not None and vm:
                        edge_vals.append(v)
                        edge_weights.append(a)
                else:
                    if v is not None and vm:
                        interior_vals.append(v)
                        interior_weights.append(a)

            elif a > 0:
                # Fractional boundary pixel
                if v is not None and vm:
                    edge_vals.append(v)
                    edge_weights.append(a)

            else:
                # Outside plot — check if within neighbor buffer
                near_plot = False
                for dr in range(-buffer_pixels, buffer_pixels + 1):
                    for dc in range(-buffer_pixels, buffer_pixels + 1):
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < h and 0 <= nc < w:
                            na = alpha[nr][nc] if nr < len(alpha) and nc < len(alpha[nr]) else 0.0
                            if na > 0:
                                near_plot = True
                                break
                    if near_plot:
                        break
                if near_plot and v is not None:
                    neighbor_vals.append(v)

    # Compute means
    interior_mean = sum(interior_vals) / len(interior_vals) if interior_vals else 0.0
    edge_mean = sum(v * w for v, w in zip(edge_vals, edge_weights)) / sum(edge_weights) if edge_weights else 0.0
    neighbor_mean = sum(neighbor_vals) / len(neighbor_vals) if neighbor_vals else 0.0

    total_plot_pixels = len(interior_vals) + len(edge_vals)
    edge_area_frac = len(edge_vals) / max(1, total_plot_pixels)
    neighbor_valid_frac = min(1.0, len(neighbor_vals) / max(1, total_plot_pixels))

    # Boundary contamination score
    green_pressure = max(0.0, neighbor_mean - interior_mean) if interior_vals else 0.0
    contamination = green_pressure * edge_area_frac * neighbor_valid_frac

    interior_valid_frac = len(interior_vals) / max(1, total_plot_pixels)
    edge_valid_frac = len(edge_vals) / max(1, total_plot_pixels)

    return (
        round(min(1.0, contamination), 4),
        round(edge_valid_frac, 4),
        round(interior_valid_frac, 4),
        round(green_pressure, 4),
    )


def extract_plot_summary(
    index_rasters: Dict[str, Raster2D],
    qa: Sentinel2QAResult,
    mask_set: Sentinel2MaskSet,
    alpha_mask: List[List[float]],
    buffer_pixels: int = 2,
) -> Sentinel2PlotSummary:
    """
    Compute alpha-weighted plot-level summary for all indices.
    """
    summary = Sentinel2PlotSummary(
        valid_fraction=qa.valid_fraction,
        cloud_fraction=qa.cloud_fraction,
        shadow_fraction=qa.shadow_fraction,
        snow_fraction=qa.snow_fraction,
        water_fraction=qa.water_fraction,
    )

    valid_mask = mask_set.valid_for_index if mask_set.valid_for_index else None

    # NDVI
    if "NDVI" in index_rasters:
        m, s, p10, p90 = _alpha_weighted_stats(
            index_rasters["NDVI"].values, alpha_mask, valid_mask
        )
        summary.ndvi_mean = m
        summary.ndvi_std = s
        summary.ndvi_p10 = p10
        summary.ndvi_p90 = p90

    # EVI
    if "EVI" in index_rasters:
        m, s, _, _ = _alpha_weighted_stats(
            index_rasters["EVI"].values, alpha_mask, valid_mask
        )
        summary.evi_mean = m
        summary.evi_std = s

    # NDMI
    if "NDMI" in index_rasters:
        m, s, _, _ = _alpha_weighted_stats(
            index_rasters["NDMI"].values, alpha_mask, valid_mask
        )
        summary.ndmi_mean = m
        summary.ndmi_std = s

    # NDRE
    if "NDRE" in index_rasters:
        m, s, _, _ = _alpha_weighted_stats(
            index_rasters["NDRE"].values, alpha_mask, valid_mask
        )
        summary.ndre_mean = m
        summary.ndre_std = s

    # BSI
    if "BSI" in index_rasters:
        m, s, _, _ = _alpha_weighted_stats(
            index_rasters["BSI"].values, alpha_mask, valid_mask
        )
        summary.bsi_mean = m
        summary.bsi_std = s

    # Heterogeneity from NDVI spatial variance
    if summary.ndvi_std is not None:
        summary.heterogeneity_score = round(min(1.0, summary.ndvi_std / 0.15), 4)

    # Boundary contamination (use NDVI as primary indicator)
    if "NDVI" in index_rasters:
        cont, edge_vf, int_vf, ngp = _compute_boundary_contamination(
            index_rasters["NDVI"].values, alpha_mask, valid_mask, buffer_pixels
        )
        summary.boundary_contamination_score = cont
        summary.edge_valid_fraction = edge_vf
        summary.interior_valid_fraction = int_vf
        summary.neighbor_green_pressure = ngp

    return summary


def generate_quadrant_zones(
    alpha_mask: List[List[float]],
) -> Dict[str, List[List[float]]]:
    """
    Generate default 2×2 quadrant zone masks from alpha mask.
    Each zone gets the alpha values for its quadrant.
    """
    h = len(alpha_mask)
    w = len(alpha_mask[0]) if alpha_mask else 0
    mid_r = h // 2
    mid_c = w // 2

    zones = {}
    quadrants = [
        ("zone_NW", 0, mid_r, 0, mid_c),
        ("zone_NE", 0, mid_r, mid_c, w),
        ("zone_SW", mid_r, h, 0, mid_c),
        ("zone_SE", mid_r, h, mid_c, w),
    ]

    for name, r0, r1, c0, c1 in quadrants:
        zone_alpha = [[0.0] * w for _ in range(h)]
        for r in range(r0, r1):
            for c in range(c0, c1):
                zone_alpha[r][c] = alpha_mask[r][c] if r < len(alpha_mask) and c < len(alpha_mask[r]) else 0.0
        zones[name] = zone_alpha

    return zones


def extract_zone_summaries(
    index_rasters: Dict[str, Raster2D],
    qa: Sentinel2QAResult,
    mask_set: Sentinel2MaskSet,
    zone_masks: Dict[str, List[List[float]]],
    plot_alpha_mask: List[List[float]],
    zone_source: str = "auto_quadrant_v1",
    zone_method: str = "grid_subdivision_2x2",
    zone_confidence: float = 0.4,
) -> List[Sentinel2ZoneSummary]:
    """
    Extract per-zone summaries with zone-specific QA fractions.

    area_fraction is relative to the full plot alpha total (not the zone itself).
    valid/cloud/shadow fractions are computed per-zone from mask_set.
    """
    summaries = []
    valid_mask = mask_set.valid_for_index if mask_set.valid_for_index else None

    # Compute plot-level total alpha for area_fraction denominator
    plot_total_alpha = sum(
        plot_alpha_mask[r][c]
        for r in range(len(plot_alpha_mask))
        for c in range(len(plot_alpha_mask[r]))
        if plot_alpha_mask[r][c] > 0
    )
    if plot_total_alpha < 1e-10:
        plot_total_alpha = 1.0

    for zone_id, zone_alpha in zone_masks.items():
        h = len(zone_alpha)
        w = len(zone_alpha[0]) if zone_alpha else 0

        # Zone area fraction relative to full plot
        zone_total_alpha = sum(
            zone_alpha[r][c]
            for r in range(h) for c in range(w)
            if zone_alpha[r][c] > 0
        )
        area_fraction = zone_total_alpha / plot_total_alpha

        # Per-zone QA fractions (alpha-weighted within zone)
        zone_valid_sum = 0.0
        zone_cloud_sum = 0.0
        zone_shadow_sum = 0.0
        zone_alpha_sum = 0.0

        for r in range(h):
            for c in range(w):
                a = zone_alpha[r][c] if r < len(zone_alpha) and c < len(zone_alpha[r]) else 0.0
                if a <= 0:
                    continue
                zone_alpha_sum += a

                if mask_set.valid_for_index and r < len(mask_set.valid_for_index) and c < len(mask_set.valid_for_index[r]):
                    zone_valid_sum += a * mask_set.valid_for_index[r][c]
                if mask_set.cloud_like and r < len(mask_set.cloud_like) and c < len(mask_set.cloud_like[r]):
                    zone_cloud_sum += a * mask_set.cloud_like[r][c]
                if mask_set.shadow_like and r < len(mask_set.shadow_like) and c < len(mask_set.shadow_like[r]):
                    zone_shadow_sum += a * mask_set.shadow_like[r][c]

        if zone_alpha_sum > 1e-10:
            zone_valid_frac = zone_valid_sum / zone_alpha_sum
            zone_cloud_frac = zone_cloud_sum / zone_alpha_sum
            zone_shadow_frac = zone_shadow_sum / zone_alpha_sum
        else:
            zone_valid_frac = 0.0
            zone_cloud_frac = 0.0
            zone_shadow_frac = 0.0

        # Zone-specific reliability: scale from plot QA by zone quality
        zone_reliability = qa.reliability_weight
        zone_sigma_mult = qa.sigma_multiplier
        if zone_cloud_frac > 0.30:
            zone_reliability = min(zone_reliability, 0.4)
            zone_sigma_mult = max(zone_sigma_mult, 2.0)
        if zone_valid_frac < 0.50:
            zone_reliability = min(zone_reliability, 0.3)
            zone_sigma_mult = max(zone_sigma_mult, 2.5)

        zs = Sentinel2ZoneSummary(
            zone_id=zone_id,
            area_fraction=round(area_fraction, 4),
            valid_fraction=round(zone_valid_frac, 4),
            cloud_fraction=round(zone_cloud_frac, 4),
            shadow_fraction=round(zone_shadow_frac, 4),
            reliability=round(zone_reliability, 4),
            sigma_multiplier=round(zone_sigma_mult, 4),
            zone_source=zone_source,
            zone_method=zone_method,
            zone_confidence=zone_confidence,
        )

        # Per-zone NDVI
        if "NDVI" in index_rasters:
            m, s, _, _ = _alpha_weighted_stats(
                index_rasters["NDVI"].values, zone_alpha, valid_mask
            )
            zs.ndvi_mean = m
            zs.ndvi_std = s

        # Per-zone NDMI
        if "NDMI" in index_rasters:
            m, _, _, _ = _alpha_weighted_stats(
                index_rasters["NDMI"].values, zone_alpha, valid_mask
            )
            zs.ndmi_mean = m

        # Per-zone NDRE
        if "NDRE" in index_rasters:
            m, _, _, _ = _alpha_weighted_stats(
                index_rasters["NDRE"].values, zone_alpha, valid_mask
            )
            zs.ndre_mean = m

        # Per-zone BSI
        if "BSI" in index_rasters:
            m, _, _, _ = _alpha_weighted_stats(
                index_rasters["BSI"].values, zone_alpha, valid_mask
            )
            zs.bsi_mean = m

        summaries.append(zs)

    return summaries

