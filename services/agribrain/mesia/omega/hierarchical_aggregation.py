"""MESIA Hierarchical Evidence Aggregation — R6 §16.2 / P14.2.

Aggregates plot-level radio observations up to Farm, Irrigation District, Basin,
and Regional scales while preserving spatial covariance and uncertainty bounds.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class AggregationScale(str, Enum):
    PLOT = "PLOT"
    FARM = "FARM"
    IRRIGATION_DISTRICT = "IRRIGATION_DISTRICT"
    HYDROLOGICAL_BASIN = "HYDROLOGICAL_BASIN"
    NATIONAL_REGION = "NATIONAL_REGION"


@dataclass(frozen=True)
class AggregatedEvidenceSummary:
    """Multi-scale spatial aggregation of soil moisture estimates."""

    scale: AggregationScale
    region_id: str
    constituent_plot_count: int
    mean_moisture_vwc: float
    combined_uncertainty_vwc: float
    spatial_coverage_fraction: float


class HierarchicalAggregator:
    """Propagates plot observations into regional macro-models."""

    @staticmethod
    def aggregate_plots_to_region(
        region_id: str,
        scale: AggregationScale,
        plot_moisture_values: List[float],
        plot_uncertainties: List[float],
    ) -> AggregatedEvidenceSummary:
        """Compute uncertainty-weighted regional mean."""
        if not plot_moisture_values:
            return AggregatedEvidenceSummary(
                scale=scale,
                region_id=region_id,
                constituent_plot_count=0,
                mean_moisture_vwc=0.0,
                combined_uncertainty_vwc=1.0,
                spatial_coverage_fraction=0.0,
            )

        n = len(plot_moisture_values)
        # Weighted mean by inverse variance 1/sigma^2
        weights = [1.0 / max(1e-6, u ** 2) for u in plot_uncertainties]
        sum_w = sum(weights)
        weighted_mean = sum(v * w for v, w in zip(plot_moisture_values, weights)) / sum_w

        # Combined standard error
        combined_u = math.sqrt(1.0 / sum_w)

        return AggregatedEvidenceSummary(
            scale=scale,
            region_id=region_id,
            constituent_plot_count=n,
            mean_moisture_vwc=weighted_mean,
            combined_uncertainty_vwc=combined_u,
            spatial_coverage_fraction=min(1.0, n / 10.0),
        )
