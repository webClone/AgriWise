"""
Uncertainty & Source Dominance Histograms
=========================================

Distribution of uncertainty and source contribution across the field.
"""
from typing import List, Dict, Any
from layer10_sire.schema import SurfaceArtifact, SurfaceType


def compute_uncertainty_histograms(
    surfaces: List[SurfaceArtifact],
    bins: int = 20,
) -> List[Dict[str, Any]]:
    """Compute histograms for uncertainty-family surfaces."""
    results = []

    unc_types = {
        SurfaceType.UNCERTAINTY_SIGMA,
        SurfaceType.DATA_RELIABILITY,
        SurfaceType.SOURCE_DOMINANCE,
    }

    for s in surfaces:
        if s.semantic_type not in unc_types:
            continue

        vals = []
        for row in s.values:
            for v in row:
                if v is not None:
                    vals.append(v)

        if not vals:
            continue

        mn, mx = min(vals), max(vals)
        mean = sum(vals) / len(vals)
        std = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5

        # Build histogram
        if mn == mx:
            hist = {"bins": [mn], "counts": [len(vals)]}
        else:
            bw = (mx - mn) / bins
            edges = [mn + i * bw for i in range(bins + 1)]
            counts = [0] * bins
            import math
            for v in vals:
                if math.isnan(v): continue
                idx = min(int((v - mn) / bw), bins - 1)
                counts[idx] += 1
            hist = {"bins": [round(e, 4) for e in edges], "counts": counts}

        results.append({
            "surface_type": s.semantic_type.value,
            "histogram": hist,
            "stats": {
                "mean": round(mean, 4),
                "std": round(std, 4),
                "min": round(mn, 4),
                "max": round(mx, 4),
                "n_pixels": len(vals),
                "high_uncertainty_pct": round(
                    sum(1 for v in vals if v > mean + std) / len(vals) * 100, 1
                ),
            },
        })

    return results


def compute_dominance_breakdown(
    dominance_surface: SurfaceArtifact,
) -> Dict[str, float]:
    """Compute field-average source contribution breakdown."""
    if not hasattr(dominance_surface, 'source_weights') or not dominance_surface.source_weights:
        return {}

    # Aggregate source weights across all pixels
    all_weights = {}
    count = 0

    for row in dominance_surface.source_weights:
        for cell_weights in row:
            if cell_weights and isinstance(cell_weights, dict):
                for src, w in cell_weights.items():
                    all_weights[src] = all_weights.get(src, 0.0) + w
                count += 1

    if count == 0:
        return {}

    return {src: round(w / count, 3) for src, w in all_weights.items()}
