"""
Delta Histograms — Date-to-date change histograms
==================================================

Computes distribution of per-pixel changes between two time snapshots.
"""
from typing import List, Dict, Any, Optional


def compute_delta_histograms(
    current_values: List[List[Optional[float]]],
    previous_values: List[List[Optional[float]]],
    H: int, W: int,
    surface_name: str = "unknown",
    bins: int = 20,
) -> Dict[str, Any]:
    """Compute histogram of value changes between two snapshots."""
    deltas = []
    for r in range(min(H, len(current_values), len(previous_values))):
        for c in range(min(W, len(current_values[r]), len(previous_values[r]))):
            curr = current_values[r][c]
            prev = previous_values[r][c]
            if curr is not None and prev is not None:
                deltas.append(curr - prev)

    if not deltas:
        return {"surface": surface_name, "bins": [], "counts": [], "stats": {}}

    mn, mx = min(deltas), max(deltas)
    if mn == mx:
        return {
            "surface": surface_name,
            "bins": [mn],
            "counts": [len(deltas)],
            "stats": {"mean": mn, "std": 0.0, "positive_pct": 100.0 if mn > 0 else 0.0},
        }

    bin_width = (mx - mn) / bins
    bin_edges = [mn + i * bin_width for i in range(bins + 1)]
    counts = [0] * bins

    import math
    for d in deltas:
        if math.isnan(d): continue
        idx = min(int((d - mn) / bin_width), bins - 1)
        counts[idx] += 1

    mean_delta = sum(deltas) / len(deltas)
    std_delta = (sum((d - mean_delta) ** 2 for d in deltas) / len(deltas)) ** 0.5
    positive_pct = sum(1 for d in deltas if d > 0) / len(deltas) * 100

    return {
        "surface": surface_name,
        "bins": [round(e, 4) for e in bin_edges],
        "counts": counts,
        "stats": {
            "mean": round(mean_delta, 4),
            "std": round(std_delta, 4),
            "min": round(mn, 4),
            "max": round(mx, 4),
            "n_pixels": len(deltas),
            "positive_pct": round(positive_pct, 1),
            "negative_pct": round(100 - positive_pct, 1),
        },
    }
