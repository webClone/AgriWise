"""
Compare Toolchain — Zone vs Zone, Surface vs Surface comparisons
================================================================

Enables side-by-side histograms for two zones or two surfaces.
"""
from typing import List, Dict, Any, Optional, Tuple
from services.agribrain.layer10_sire.schema import (
    SurfaceArtifact, ZoneArtifact,
)


def compare_zones(
    surface: SurfaceArtifact,
    zone_a: ZoneArtifact,
    zone_b: ZoneArtifact,
    bins: int = 15,
) -> Dict[str, Any]:
    """Compare distribution of a surface within two zones."""
    vals_a = _extract_zone_values(surface, zone_a)
    vals_b = _extract_zone_values(surface, zone_b)

    if not vals_a or not vals_b:
        return {"error": "Insufficient data for comparison"}

    hist_a = _build_hist(vals_a, bins)
    hist_b = _build_hist(vals_b, bins)
    stats_a = _compute_stats(vals_a)
    stats_b = _compute_stats(vals_b)

    # Statistical comparison
    mean_diff = stats_a["mean"] - stats_b["mean"]
    pooled_std = ((stats_a["std"] ** 2 + stats_b["std"] ** 2) / 2) ** 0.5

    return {
        "surface": surface.semantic_type.value,
        "zone_a": {"id": zone_a.zone_id, "histogram": hist_a, "stats": stats_a},
        "zone_b": {"id": zone_b.zone_id, "histogram": hist_b, "stats": stats_b},
        "comparison": {
            "mean_difference": round(mean_diff, 4),
            "effect_size": round(mean_diff / pooled_std, 3) if pooled_std > 0 else 0.0,
            "overlap_pct": _compute_overlap(vals_a, vals_b),
        },
    }


def compare_surfaces(
    surface_a: SurfaceArtifact,
    surface_b: SurfaceArtifact,
    H: int, W: int,
    bins: int = 15,
) -> Dict[str, Any]:
    """Compare two surfaces pixel-by-pixel (e.g., NDVI vs yield)."""
    pairs = []
    for r in range(min(H, len(surface_a.values), len(surface_b.values))):
        for c in range(min(W, len(surface_a.values[r]), len(surface_b.values[r]))):
            va = surface_a.values[r][c]
            vb = surface_b.values[r][c]
            if va is not None and vb is not None:
                pairs.append((va, vb))

    if not pairs:
        return {"error": "No overlapping pixels"}

    vals_a = [p[0] for p in pairs]
    vals_b = [p[1] for p in pairs]

    # Simple correlation
    mean_a = sum(vals_a) / len(vals_a)
    mean_b = sum(vals_b) / len(vals_b)
    cov = sum((a - mean_a) * (b - mean_b) for a, b in pairs) / len(pairs)
    std_a = (sum((a - mean_a) ** 2 for a in vals_a) / len(vals_a)) ** 0.5
    std_b = (sum((b - mean_b) ** 2 for b in vals_b) / len(vals_b)) ** 0.5
    corr = cov / (std_a * std_b) if std_a > 0 and std_b > 0 else 0.0

    return {
        "surface_a": surface_a.semantic_type.value,
        "surface_b": surface_b.semantic_type.value,
        "correlation": round(corr, 3),
        "n_pixels": len(pairs),
        "stats_a": _compute_stats(vals_a),
        "stats_b": _compute_stats(vals_b),
    }


def _extract_zone_values(surface, zone):
    vals = []
    for r, c in zone.cell_indices:
        if 0 <= r < len(surface.values) and 0 <= c < len(surface.values[r]):
            v = surface.values[r][c]
            if v is not None:
                vals.append(v)
    return vals


def _build_hist(vals, bins):
    mn, mx = min(vals), max(vals)
    if mn == mx:
        return {"bins": [mn], "counts": [len(vals)]}
    bw = (mx - mn) / bins
    edges = [mn + i * bw for i in range(bins + 1)]
    counts = [0] * bins
    import math
    for v in vals:
        if math.isnan(v): continue
        idx = min(int((v - mn) / bw), bins - 1)
        counts[idx] += 1
    return {"bins": [round(e, 4) for e in edges], "counts": counts}


def _compute_stats(vals):
    mean = sum(vals) / len(vals)
    std = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
    return {
        "mean": round(mean, 4),
        "std": round(std, 4),
        "min": round(min(vals), 4),
        "max": round(max(vals), 4),
        "n": len(vals),
    }


def _compute_overlap(vals_a, vals_b):
    """Approximate overlap percentage of two distributions."""
    mn = min(min(vals_a), min(vals_b))
    mx = max(max(vals_a), max(vals_b))
    if mn == mx:
        return 100.0

    bins = 20
    bw = (mx - mn) / bins
    hist_a = [0] * bins
    hist_b = [0] * bins

    import math
    for v in vals_a:
        if math.isnan(v): continue
        idx = min(int((v - mn) / bw), bins - 1)
        hist_a[idx] += 1
    for v in vals_b:
        if math.isnan(v): continue
        idx = min(int((v - mn) / bw), bins - 1)
        hist_b[idx] += 1

    # Normalize
    tot_a = sum(hist_a) or 1
    tot_b = sum(hist_b) or 1
    norm_a = [c / tot_a for c in hist_a]
    norm_b = [c / tot_b for c in hist_b]

    overlap = sum(min(a, b) for a, b in zip(norm_a, norm_b))
    return round(overlap * 100, 1)
