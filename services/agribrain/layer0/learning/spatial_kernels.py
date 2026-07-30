"""
Pattern ⑨ — Multi-Resolution Fusion Kernels.

Implements learned spatial weighting kernels to combine multi-resolution data
streams: 10m Sentinel pixels, 25km ERA5 weather grids, and point IoT sensors,
producing unified spatial estimates at any coordinate.
"""

from __future__ import annotations

import math
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger("agribrain.learning.spatial_kernels")


class SpatialFusionKernel:
    """Fuses multi-resolution spatial datasets using distance-decay kernels."""

    def __init__(self):
        # Default kernel length-scales (sigma) in meters
        self.kernel_scales = {
            "sensor": 200.0,      # Point sensor: decays rapidly beyond 200m
            "sentinel": 1000.0,   # Satellite: decays beyond 1km
            "era5": 25000.0,      # Regional grid: constant baseline up to 25km
        }

    def _haversine_distance_m(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate geographical distance between two coordinates in meters."""
        R = 6371000.0  # Earth radius
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lambda = math.radians(lng2 - lng1)

        a = math.sin(d_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0)**2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return R * c

    def fuse_data(
        self,
        target_lat: float,
        target_lng: float,
        inputs: List[Dict[str, Any]]
    ) -> float:
        """Fuse multiple inputs at target coordinates.
        
        Each input dict should contain:
          - value: float
          - lat, lng: float
          - source_type: "sensor" | "sentinel" | "era5"
          - confidence: float [0.0 - 1.0] (optional)
        """
        if not inputs:
            return 0.0

        total_weight = 0.0
        weighted_sum = 0.0

        for item in inputs:
            val = float(item["value"])
            lat = float(item["lat"])
            lng = float(item["lng"])
            s_type = item.get("source_type", "sentinel")
            conf = float(item.get("confidence", 1.0))

            # Re-scale kernel parameters based on type
            scale = self.kernel_scales.get(s_type, 1000.0)

            # Compute distance
            dist = self._haversine_distance_m(target_lat, target_lng, lat, lng)

            # Gaussian kernel weight
            # w = conf * exp(-d^2 / (2 * sigma^2))
            weight = conf * math.exp(-(dist ** 2) / (2.0 * (scale ** 2)))
            
            # Avoid numerical issues with extremely small weights
            if weight < 1e-8:
                weight = 1e-8

            weighted_sum += val * weight
            total_weight += weight

        if total_weight <= 0:
            return sum(x["value"] for x in inputs) / len(inputs)

        return weighted_sum / total_weight
