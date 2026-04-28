"""
Sentinel-1 SAR Plot & Zone Extraction.

Alpha-weighted statistics for all SAR features at plot and zone level.
Zone-specific QA is computed independently — never copied from global.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from layer0.sentinel1.schemas import (
    SARRaster2D,
    Sentinel1PlotSummary,
    Sentinel1QAResult,
    Sentinel1ZoneSummary,
)
from layer0.sentinel1.masks import Sentinel1MaskSet


# ============================================================================
# Alpha-weighted statistics
# ============================================================================

def _alpha_weighted_stats(
    values: List[List[Optional[float]]],
    alpha: List[List[float]],
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    Compute alpha-weighted mean, std, p10, p90.

    Returns (mean, std, p10, p90) or (None, None, None, None) if no valid pixels.
    """
    weighted_vals = []
    h = len(values)
    for r in range(h):
        w = len(values[r])
        for c in range(w):
            a = alpha[r][c] if r < len(alpha) and c < len(alpha[r]) else 0.0
            if a <= 0:
                continue
            v = values[r][c]
            if v is None:
                continue
            weighted_vals.append((v, a))

    if not weighted_vals:
        return None, None, None, None

    total_weight = sum(w for _, w in weighted_vals)
    if total_weight < 1e-12:
        return None, None, None, None

    # Weighted mean
    mean = sum(v * w for v, w in weighted_vals) / total_weight

    # Weighted std
    var = sum(w * (v - mean) ** 2 for v, w in weighted_vals) / total_weight
    std = math.sqrt(var)

    # Weighted percentiles (approximate)
    sorted_vals = sorted(weighted_vals, key=lambda x: x[0])
    cum = 0.0
    p10 = sorted_vals[0][0]
    p90 = sorted_vals[-1][0]
    for v, w in sorted_vals:
        cum += w
        if cum / total_weight >= 0.10 and p10 == sorted_vals[0][0]:
            p10 = v
        if cum / total_weight >= 0.90:
            p90 = v
            break

    return (
        round(mean, 4),
        round(std, 4),
        round(p10, 4),
        round(p90, 4),
    )


def _alpha_weighted_fraction(
    mask: List[List[int]],
    alpha: List[List[float]],
) -> float:
    """Compute alpha-weighted fraction."""
    num = 0.0
    den = 0.0
    for r in range(len(mask)):
        for c in range(len(mask[r])):
            a = alpha[r][c] if r < len(alpha) and c < len(alpha[r]) else 0.0
            den += a
            if mask[r][c]:
                num += a
    if den < 1e-12:
        return 0.0
    return num / den


def _feature_mean(
    feature: Optional[SARRaster2D],
    alpha: List[List[float]],
) -> Optional[float]:
    """Get alpha-weighted mean of a feature raster."""
    if feature is None:
        return None
    m, _, _, _ = _alpha_weighted_stats(feature.values, alpha)
    return m


# ============================================================================
# Plot summary
# ============================================================================

def extract_sar_plot_summary(
    features: Dict[str, SARRaster2D],
    qa: Sentinel1QAResult,
    mask_set: Sentinel1MaskSet,
    alpha_mask: List[List[float]],
) -> Sentinel1PlotSummary:
    """
    Compute plot-level SAR summary from feature rasters.

    All stats are alpha-weighted.
    """
    valid_fraction = _alpha_weighted_fraction(mask_set.valid_for_backscatter, alpha_mask)
    border_noise_fraction = _alpha_weighted_fraction(mask_set.border_noise_like, alpha_mask)
    low_signal_fraction = _alpha_weighted_fraction(mask_set.low_signal, alpha_mask)

    # VV dB stats
    vv_db_mean, vv_db_std, vv_db_p10, vv_db_p90 = (None, None, None, None)
    if "VV_DB" in features:
        vv_db_mean, vv_db_std, vv_db_p10, vv_db_p90 = _alpha_weighted_stats(
            features["VV_DB"].values, alpha_mask
        )

    # VH dB stats
    vh_db_mean, vh_db_std, vh_db_p10, vh_db_p90 = (None, None, None, None)
    if "VH_DB" in features:
        vh_db_mean, vh_db_std, vh_db_p10, vh_db_p90 = _alpha_weighted_stats(
            features["VH_DB"].values, alpha_mask
        )

    # Heterogeneity from VV dB std
    heterogeneity = 0.0
    if vv_db_std is not None:
        heterogeneity = min(1.0, vv_db_std / 5.0)

    return Sentinel1PlotSummary(
        valid_fraction=round(valid_fraction, 4),
        vv_db_mean=vv_db_mean,
        vv_db_std=vv_db_std,
        vv_db_p10=vv_db_p10,
        vv_db_p90=vv_db_p90,
        vh_db_mean=vh_db_mean,
        vh_db_std=vh_db_std,
        vh_db_p10=vh_db_p10,
        vh_db_p90=vh_db_p90,
        vv_vh_ratio_mean=_feature_mean(features.get("VV_VH_RATIO"), alpha_mask),
        vv_minus_vh_db_mean=_feature_mean(features.get("VV_MINUS_VH_DB"), alpha_mask),
        rvi_mean=_feature_mean(features.get("RVI"), alpha_mask),
        cross_pol_fraction_mean=_feature_mean(features.get("CROSS_POL_FRACTION"), alpha_mask),
        span_mean=_feature_mean(features.get("SPAN"), alpha_mask),
        surface_wetness_proxy_mean=_feature_mean(features.get("SURFACE_WETNESS_PROXY"), alpha_mask),
        structure_proxy_mean=_feature_mean(features.get("STRUCTURE_PROXY"), alpha_mask),
        flood_score=_feature_mean(features.get("FLOOD_SCORE"), alpha_mask),
        roughness_proxy=_feature_mean(features.get("ROUGHNESS_PROXY"), alpha_mask),
        heterogeneity_score=round(heterogeneity, 4),
        anomaly_fraction=0.0,
        border_noise_fraction=round(border_noise_fraction, 4),
        low_signal_fraction=round(low_signal_fraction, 4),
    )


# ============================================================================
# Zone extraction
# ============================================================================

def generate_quadrant_zones(
    alpha_mask: List[List[float]],
) -> Dict[str, List[List[float]]]:
    """Generate 4 auto-quadrant zone masks from the plot alpha mask."""
    h = len(alpha_mask)
    w = len(alpha_mask[0]) if alpha_mask else 0
    mid_r = h // 2
    mid_c = w // 2

    zones = {}
    for zone_id, row_range, col_range in [
        ("zone_NW", range(0, mid_r), range(0, mid_c)),
        ("zone_NE", range(0, mid_r), range(mid_c, w)),
        ("zone_SW", range(mid_r, h), range(0, mid_c)),
        ("zone_SE", range(mid_r, h), range(mid_c, w)),
    ]:
        mask = [[0.0] * w for _ in range(h)]
        for r in row_range:
            for c in col_range:
                mask[r][c] = alpha_mask[r][c] if r < h and c < w else 0.0
        zones[zone_id] = mask

    return zones


def extract_sar_zone_summaries(
    features: Dict[str, SARRaster2D],
    qa: Sentinel1QAResult,
    mask_set: Sentinel1MaskSet,
    zone_masks: Dict[str, List[List[float]]],
    plot_alpha_mask: List[List[float]],
    zone_source: str = "auto_quadrant_v1",
    zone_method: str = "grid_subdivision_2x2",
    zone_confidence: float = 0.4,
) -> List[Sentinel1ZoneSummary]:
    """
    Compute per-zone SAR summaries.

    IMPORTANT: area_fraction is relative to total plot alpha (not zone total).
    IMPORTANT: valid/border_noise/low_signal fractions are zone-specific.
    """
    summaries = []

    # Total plot alpha for area_fraction denominator
    total_plot_alpha = sum(
        plot_alpha_mask[r][c]
        for r in range(len(plot_alpha_mask))
        for c in range(len(plot_alpha_mask[r]))
    )
    if total_plot_alpha < 1e-12:
        total_plot_alpha = 1.0

    for zone_id, zone_alpha in zone_masks.items():
        # Zone area fraction relative to entire plot
        zone_alpha_sum = sum(
            zone_alpha[r][c]
            for r in range(len(zone_alpha))
            for c in range(len(zone_alpha[r]))
        )
        area_fraction = zone_alpha_sum / total_plot_alpha

        # Zone-specific QA fractions (computed from zone alpha, NOT global)
        zone_valid = _alpha_weighted_fraction(mask_set.valid_for_backscatter, zone_alpha)
        zone_border = _alpha_weighted_fraction(mask_set.border_noise_like, zone_alpha)
        zone_low_sig = _alpha_weighted_fraction(mask_set.low_signal, zone_alpha)

        # Zone-specific reliability/sigma
        if zone_valid < 0.45 or zone_border > 0.30 or zone_low_sig > 0.50:
            zone_rel = 0.0
            zone_sigma = 999.0
        elif zone_valid >= 0.90 and zone_low_sig <= 0.05 and zone_border <= 0.05:
            zone_rel = 0.90
            zone_sigma = 1.0
        elif zone_valid >= 0.75 and zone_low_sig <= 0.15:
            zone_rel = 0.80
            zone_sigma = 1.2
        else:
            zone_rel = 0.55
            zone_sigma = 1.8

        summary = Sentinel1ZoneSummary(
            zone_id=zone_id,
            zone_source=zone_source,
            zone_method=zone_method,
            zone_confidence=zone_confidence,
            area_fraction=round(area_fraction, 4),
            valid_fraction=round(zone_valid, 4),
            border_noise_fraction=round(zone_border, 4),
            low_signal_fraction=round(zone_low_sig, 4),
            reliability=round(zone_rel, 3),
            sigma_multiplier=round(zone_sigma, 3),
            vv_db_mean=_feature_mean(features.get("VV_DB"), zone_alpha),
            vh_db_mean=_feature_mean(features.get("VH_DB"), zone_alpha),
            vv_vh_ratio_mean=_feature_mean(features.get("VV_VH_RATIO"), zone_alpha),
            rvi_mean=_feature_mean(features.get("RVI"), zone_alpha),
            surface_wetness_proxy_mean=_feature_mean(features.get("SURFACE_WETNESS_PROXY"), zone_alpha),
            structure_proxy_mean=_feature_mean(features.get("STRUCTURE_PROXY"), zone_alpha),
            flood_score=_feature_mean(features.get("FLOOD_SCORE"), zone_alpha),
            anomaly_score=0.0,
        )
        summaries.append(summary)

    return summaries
