"""
Field Histogram Engine — Compute per-surface histograms for entire field
"""
import math
import numpy as np
from typing import List
from services.agribrain.layer10_sire.schema import (
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
    by_type = {
        (s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type)): s
        for s in surfaces
    }
    base_surface = by_type.get("NDVI_CLEAN")
    base_cell_count = (
        sum(len(row) for row in base_surface.values)
        if base_surface is not None and base_surface.values
        else None
    )

    for s in surfaces:
        surface_type = s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type)
        if surface_type in {
            "OBSERVED_DATA_MASK_NDVI", "GAP_FILL_MASK_NDVI", "VALID_DATA_MASK_NDVI"
        }:
            # Dependency masks shape rendering alpha; they are not scientific
            # surfaces and must not appear in farmer/inspector histograms.
            continue
        observed_mask = by_type.get("OBSERVED_DATA_MASK_NDVI") if surface_type == "NDVI_CLEAN" else None
        gap_mask = by_type.get("GAP_FILL_MASK_NDVI") if surface_type == "NDVI_CLEAN" else None

        values_arr = np.asarray(s.values, dtype=float)
        finite = np.isfinite(values_arr)
        combined_vals = values_arr[finite]

        def collect(mask=None):
            if mask is None:
                return combined_vals
            mask_arr = np.asarray(mask.values, dtype=float)
            if mask_arr.shape != values_arr.shape:
                return np.empty(0, dtype=float)
            return values_arr[finite & np.isfinite(mask_arr) & (mask_arr != 0)]

        vals = collect(observed_mask) if observed_mask is not None else combined_vals

        if vals.size == 0:
            continue

        # WS8: field footprint denominator when available.  A high-resolution
        # surface needs a denominator on its own grid, never the base HxW count.
        surface_cell_count = sum(len(row) for row in s.values)
        if field_valid_cells is not None and field_valid_cells > 0:
            if base_cell_count and surface_cell_count != base_cell_count:
                footprint_fraction = min(1.0, field_valid_cells / base_cell_count)
                total_pixels = int(round(surface_cell_count * footprint_fraction))
            else:
                total_pixels = int(field_valid_cells)
        else:
            total_pixels = surface_cell_count
        valid_pixels = int(vals.size)
        # Geometry masks and nearest scaling can differ by a boundary pixel;
        # the coverage denominator must nevertheless remain mathematically valid.
        total_pixels = max(total_pixels, valid_pixels)

        # Compute bin edges
        lo = float(np.min(vals))
        hi = float(np.max(vals))
        if lo == hi:
            hi = lo + 1.0  # Avoid zero-width bins

        bin_width = (hi - lo) / n_bins
        bin_edges = [lo + i * bin_width for i in range(n_bins + 1)]
        indices = np.minimum(((vals - lo) / bin_width).astype(int), n_bins - 1)
        bin_counts = np.bincount(indices, minlength=n_bins).astype(int).tolist()

        # Stats
        mean_val = float(np.mean(vals))
        sorted_vals = np.sort(vals)
        median_val = float(sorted_vals[valid_pixels // 2])
        std_val = float(np.std(vals))

        p10_idx = max(0, int(valid_pixels * 0.1) - 1)
        p90_idx = min(valid_pixels - 1, int(valid_pixels * 0.9))
        p10 = float(sorted_vals[p10_idx])
        p90 = float(sorted_vals[p90_idx])

        # Skewness (Fisher's)
        skewness = 0.0
        if std_val > 0 and valid_pixels > 2:
            skewness = float(np.mean(((vals - mean_val) / std_val) ** 3))

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

        if surface_type == "NDVI_CLEAN" and observed_mask is not None:
            if gap_mask is not None:
                gap_vals = collect(gap_mask)
                if gap_vals.size:
                    histograms.append(_build_histogram(s, gap_vals, n_bins, total_pixels, "field_gap_filled"))
            if combined_vals.size:
                histograms.append(_build_histogram(s, combined_vals, n_bins, total_pixels, "field_combined_display"))

    return histograms


def _build_histogram(s, vals, n_bins, total_pixels, region_id):
    vals = np.asarray(vals, dtype=float)
    lo, hi = float(np.min(vals)), float(np.max(vals))
    if lo == hi:
        hi = lo + 1.0
    width = (hi - lo) / n_bins
    edges = [lo + i * width for i in range(n_bins + 1)]
    indices = np.minimum(((vals - lo) / width).astype(int), n_bins - 1)
    counts = np.bincount(indices, minlength=n_bins).astype(int).tolist()
    ordered = np.sort(vals)
    n_values = int(vals.size)
    mean = float(np.mean(vals))
    std = float(np.std(vals))
    return HistogramArtifact(
        surface_type=s.semantic_type, region_id=region_id,
        bin_edges=edges, bin_counts=counts, total_pixels=total_pixels,
        valid_pixels=n_values, mean=round(mean, 4),
        median=round(float(ordered[n_values // 2]), 4), std=round(std, 4),
        p10=round(float(ordered[max(0, int(n_values * .1) - 1)]), 4),
        p90=round(float(ordered[min(n_values - 1, int(n_values * .9))]), 4),
        skewness=0.0, is_bimodal=_detect_bimodality(counts),
    )


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
