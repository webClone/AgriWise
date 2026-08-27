"""
Zone Histogram Engine — Compute per-zone histograms for cross-zone comparison
"""
import math
import numpy as np
from typing import List
from services.agribrain.layer10_sire.schema import (
    SurfaceArtifact, ZoneArtifact, HistogramArtifact,
)


def compute_zone_histograms(
    surfaces: List[SurfaceArtifact],
    zones: List[ZoneArtifact],
    n_bins: int = 10,
) -> List[HistogramArtifact]:
    """Compute histograms for each surface within each zone."""
    histograms = []
    prepared_surfaces = []
    for surface in surfaces:
        prov = getattr(surface, "provenance", {}) or {}
        if prov.get("zone_statistics_eligible") is False or getattr(surface, "zone_statistics_eligible", True) is False:
            continue
        surface_type = (
            surface.semantic_type.value
            if hasattr(surface.semantic_type, "value")
            else str(surface.semantic_type)
        )
        if surface_type in {
            "OBSERVED_DATA_MASK_NDVI", "GAP_FILL_MASK_NDVI", "VALID_DATA_MASK_NDVI"
        }:
            continue
        prepared_surfaces.append((surface, np.asarray(surface.values, dtype=float)))

    for zone in zones:
        if not zone.cell_indices:
            continue
        rows = np.fromiter((r for r, _ in zone.cell_indices), dtype=int)
        cols = np.fromiter((c for _, c in zone.cell_indices), dtype=int)

        for surface, surface_arr in prepared_surfaces:
            # Gather values within zone cells
            in_bounds = (rows < surface_arr.shape[0]) & (cols < surface_arr.shape[1])
            vals = surface_arr[rows[in_bounds], cols[in_bounds]]
            vals = vals[np.isfinite(vals)]

            if vals.size == 0:
                continue

            lo = float(np.min(vals))
            hi = float(np.max(vals))
            if lo == hi:
                hi = lo + 1.0

            bin_width = (hi - lo) / n_bins
            bin_edges = [lo + i * bin_width for i in range(n_bins + 1)]
            indices = np.minimum(((vals - lo) / bin_width).astype(int), n_bins - 1)
            bin_counts = np.bincount(indices, minlength=n_bins).astype(int).tolist()

            mean_val = float(np.mean(vals))
            sorted_vals = np.sort(vals)
            n = int(vals.size)
            median_val = float(sorted_vals[n // 2])
            std_val = float(np.std(vals))

            # Real p10/p90 from sorted values (no fake 0.0)
            p10_val = float(sorted_vals[max(0, int(n * 0.10))])
            p90_val = float(sorted_vals[min(n - 1, int(n * 0.90))])

            histograms.append(HistogramArtifact(
                surface_type=surface.semantic_type,
                region_id=zone.zone_id,
                bin_edges=bin_edges,
                bin_counts=bin_counts,
                total_pixels=len(zone.cell_indices),
                valid_pixels=n,
                mean=round(mean_val, 4),
                median=round(median_val, 4),
                std=round(std_val, 4),
                p10=round(p10_val, 4),
                p90=round(p90_val, 4),
            ))

    return histograms
