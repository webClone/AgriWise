"""
Field Histogram Engine — Compute per-surface histograms for entire field
"""
import math
from typing import List
from layer10_sire.schema import (
    SurfaceArtifact, HistogramArtifact,
)


def compute_field_histograms(
    surfaces: List[SurfaceArtifact], n_bins: int = 20,
    field_valid_cells: int | None = None,
) -> List[HistogramArtifact]:
    """Compute field-level histogram for each surface.

    Parameters
    ----------
    field_valid_cells : If provided, used as total_pixels denominator so
                       coverage ratio reflects true field footprint, not bbox.
    """
    histograms = []

    for s in surfaces:
        vals = []
        for row in s.values:
            for v in row:
                if v is not None:
                    vals.append(v)

        if not vals:
            continue

        # WS8: field footprint denominator when available
        total_pixels = field_valid_cells if (field_valid_cells is not None and field_valid_cells > 0) else sum(len(row) for row in s.values)
        valid_pixels = len(vals)

        # Compute bin edges
        lo = min(vals)
        hi = max(vals)
        if lo == hi:
            hi = lo + 1.0  # Avoid zero-width bins

        bin_width = (hi - lo) / n_bins
        bin_edges = [lo + i * bin_width for i in range(n_bins + 1)]
        bin_counts = [0] * n_bins

        for v in vals:
            if math.isnan(v): continue
            idx = min(int((v - lo) / bin_width), n_bins - 1)
            bin_counts[idx] += 1

        # Stats
        mean_val = sum(vals) / len(vals)
        sorted_vals = sorted(vals)
        median_val = sorted_vals[len(sorted_vals) // 2]
        variance = sum((v - mean_val) ** 2 for v in vals) / len(vals)
        std_val = math.sqrt(variance)

        p10_idx = max(0, int(len(sorted_vals) * 0.1) - 1)
        p90_idx = min(len(sorted_vals) - 1, int(len(sorted_vals) * 0.9))
        p10 = sorted_vals[p10_idx]
        p90 = sorted_vals[p90_idx]

        # Skewness (Fisher's)
        skewness = 0.0
        if std_val > 0 and len(vals) > 2:
            skewness = sum(((v - mean_val) / std_val) ** 3 for v in vals) / len(vals)

        # Bimodality detection (simple: two peaks in histogram)
        is_bimodal = _detect_bimodality(bin_counts)

        histograms.append(HistogramArtifact(
            surface_type=s.semantic_type,
            region_id="field",
            bin_edges=bin_edges,
            bin_counts=bin_counts,
            total_pixels=total_pixels,
            valid_pixels=valid_pixels,
            mean=round(mean_val, 4),
            median=round(median_val, 4),
            std=round(std_val, 4),
            p10=round(p10, 4),
            p90=round(p90, 4),
            skewness=round(skewness, 4),
            is_bimodal=is_bimodal,
        ))

    return histograms


def _detect_bimodality(counts: List[int], min_valley_ratio: float = 0.5) -> bool:
    """Simple bimodality detection: look for a valley between two peaks."""
    if len(counts) < 5:
        return False

    # Find peaks (local maxima)
    peaks = []
    for i in range(1, len(counts) - 1):
        if counts[i] > counts[i-1] and counts[i] > counts[i+1]:
            peaks.append((i, counts[i]))

    if len(peaks) < 2:
        return False

    # Check if there's a valley between the two highest peaks
    peaks.sort(key=lambda x: -x[1])
    p1, p2 = peaks[0], peaks[1]
    left, right = min(p1[0], p2[0]), max(p1[0], p2[0])
    valley = min(counts[left:right+1])
    peak_min = min(p1[1], p2[1])

    return valley < peak_min * min_valley_ratio
