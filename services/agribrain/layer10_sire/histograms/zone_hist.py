"""
Zone Histogram Engine — Compute per-zone histograms for cross-zone comparison
"""
import math
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

    for zone in zones:
        cell_set = set((r, c) for r, c in zone.cell_indices)

        for surface in surfaces:
            # Gather values within zone cells
            vals = []
            for r, c in zone.cell_indices:
                if r < len(surface.values) and c < len(surface.values[r]):
                    v = surface.values[r][c]
                    if v is not None:
                        vals.append(v)

            if not vals:
                continue

            lo = min(vals)
            hi = max(vals)
            if lo == hi:
                hi = lo + 1.0

            bin_width = (hi - lo) / n_bins
            bin_edges = [lo + i * bin_width for i in range(n_bins + 1)]
            bin_counts = [0] * n_bins

            for v in vals:
                if math.isnan(v): continue
                idx = min(int((v - lo) / bin_width), n_bins - 1)
                bin_counts[idx] += 1

            mean_val = sum(vals) / len(vals)
            sorted_vals = sorted(vals)
            median_val = sorted_vals[len(sorted_vals) // 2]
            variance = sum((v - mean_val) ** 2 for v in vals) / len(vals)
            std_val = math.sqrt(variance)

            # Real p10/p90 from sorted values (no fake 0.0)
            n = len(sorted_vals)
            p10_val = sorted_vals[max(0, int(n * 0.10))]
            p90_val = sorted_vals[min(n - 1, int(n * 0.90))]

            histograms.append(HistogramArtifact(
                surface_type=surface.semantic_type,
                region_id=zone.zone_id,
                bin_edges=bin_edges,
                bin_counts=bin_counts,
                total_pixels=len(zone.cell_indices),
                valid_pixels=len(vals),
                mean=round(mean_val, 4),
                median=round(median_val, 4),
                std=round(std_val, 4),
                p10=round(p10_val, 4),
                p90=round(p90_val, 4),
            ))

    return histograms
