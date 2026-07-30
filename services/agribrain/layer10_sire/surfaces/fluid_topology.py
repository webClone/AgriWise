"""
Layer 10: Fluid Topology Generator

This module creates dynamic management zones (fluid heatmaps) that migrate
and morph depending on the incoming climate regime (wet, dry, heatwave).
Instead of static management zones, this returns conditional spatial states
using TRUE spatial raster data.
"""

import numpy as np
import math
from typing import Dict, List, Any
import logging

logger = logging.getLogger("agribrain.fluid_topology")

class FluidTopologyEngine:
    """
    Generates conditional management zones based on the plot's
    actual spatial memory (NDVI raster) and the predicted weather regime.
    """
    
    def __init__(self, plot_id: str, lat: float, lng: float, polygon_coords: List = None):
        self.plot_id = plot_id
        self.lat = lat
        self.lng = lng
        self.polygon_coords = polygon_coords
        self.raster_data = None
        self.width = 0
        self.height = 0
        
    def _fetch_baseline_topology(self) -> np.ndarray:
        """
        Fetches the recent 180-day NDVI median composite from Sentinel Hub.
        This provides the true physical footprint and spatial variance of the plot.
        """
        if self.raster_data is not None:
            return self.raster_data
            
        from layer0.data_gateway import broker
        import datetime
        end_date = datetime.datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.datetime.now() - datetime.timedelta(days=180)).strftime("%Y-%m-%d")
        
        logger.info(f"Fetching TRUE Raster Topology for Plot {self.plot_id}...")
        raster_dict = broker.get(
            "raster_composite_ndvi",
            plot_id=self.plot_id,
            lat=self.lat,
            lng=self.lng,
            start_date=start_date,
            end_date=end_date,
            polygon_coords=self.polygon_coords,
            target_resolution_m=10.0
        )
        
        if not raster_dict or "values" not in raster_dict:
            raise ValueError(f"Failed to fetch real NDVI raster for plot {self.plot_id}.")
            
        # The values array is nested list: [[float,...], ...]
        # None values represent masked areas (outside polygon)
        # We replace None with 0 for matrix math, but keep track of the mask.
        self.width = raster_dict["width"]
        self.height = raster_dict["height"]
        
        raw_vals = raster_dict["values"]
        grid = np.zeros((self.height, self.width), dtype=float)
        
        for y in range(self.height):
            for x in range(self.width):
                val = raw_vals[y][x]
                if val is not None:
                    grid[y, x] = max(0.01, float(val)) # Small positive floor for math
                else:
                    grid[y, x] = -1.0 # Mask value
                    
        self.raster_data = grid
        return grid
        
    def generate_regime_map(self, regime: str) -> np.ndarray:
        """
        Generates the predicted fluid management zone map for a given regime.
        Stress patterns are derived from the ACTUAL raster rather than fixed
        spatial gradients, ensuring each plot's unique topology drives the result.
        """
        base = self._fetch_baseline_topology()
        
        valid_mask = base > -0.5
        map_data = np.copy(base)
        
        if not np.any(valid_mask) or regime == 'optimal':
            return map_data
        
        # ---- Data-derived spatial vulnerability ----
        # Compute per-pixel deviation from the field's own spatial mean.
        # Negative deviation = weaker zone = more vulnerable to stress.
        valid_mean = base[valid_mask].mean()
        deviation = np.zeros_like(base)
        deviation[valid_mask] = base[valid_mask] - valid_mean  # positive = strong, negative = weak
        
        # Normalized weakness map: 0 (strongest zone) to 1 (weakest zone)
        dev_min = deviation[valid_mask].min()
        dev_max = deviation[valid_mask].max()
        weakness = np.zeros_like(base)
        if dev_max > dev_min:
            weakness[valid_mask] = 1.0 - (deviation[valid_mask] - dev_min) / (dev_max - dev_min)
        
        # Edge proximity map (for heatwave — field borders lose moisture faster)
        y_indices, x_indices = np.mgrid[0:self.height, 0:self.width]
        x_norm = x_indices / max(1, self.width)
        y_norm = y_indices / max(1, self.height)
        edge_proximity = np.maximum(0, 0.4 - np.minimum(
            np.minimum(x_norm, 1.0 - x_norm),
            np.minimum(y_norm, 1.0 - y_norm)
        ))
        
        if regime == 'drought':
            # Drought hits weakest zones hardest — areas already low on vegetation
            # suffer most from water deficit (lower NDVI = lower root density = less water access)
            map_data[valid_mask] = base[valid_mask] - 0.5 * weakness[valid_mask]
        elif regime == 'flood':
            # Flood favors high-vigor zones (deeper roots survive waterlogging)
            # but drowns weak zones (low NDVI = compacted soil = poor drainage)
            map_data[valid_mask] = base[valid_mask] + 0.2 * (1.0 - weakness[valid_mask]) - 0.4 * weakness[valid_mask]
        elif regime == 'heatwave':
            # Heatwave: field edges + weak interior zones are most stressed
            map_data[valid_mask] = base[valid_mask] - edge_proximity[valid_mask] * 1.2 - 0.3 * weakness[valid_mask]
            
        # Normalize between 0 and 1 ONLY for valid pixels
        if np.any(valid_mask):
            valid_pixels = map_data[valid_mask]
            map_min = valid_pixels.min()
            map_max = valid_pixels.max()
            if map_max > map_min:
                map_data[valid_mask] = (valid_pixels - map_min) / (map_max - map_min)
                
            map_data[valid_mask] = np.clip(map_data[valid_mask], 0, 1)
            
        return map_data

    def to_rgb_heatmap(self, data: np.ndarray) -> List[List[str]]:
        """
        Converts the float array into a hex color matrix for frontend rendering.
        Low = Red, High = Green. Masked = Transparent/None.
        """
        def float_to_hex(v: float) -> str:
            if v < 0: return "transparent" # Outside polygon
            
            if v < 0.5:
                r = 239
                g = int(68 + (163 * (v * 2)))
                b = int(68 - (58 * (v * 2)))
            else:
                v_adj = (v - 0.5) * 2
                r = int(234 - (200 * v_adj))
                g = int(179 + (18 * v_adj))
                b = int(8 + (86 * v_adj))
            return f"#{r:02x}{g:02x}{b:02x}"
            
        h, w = data.shape
        grid = []
        for y in range(h):
            row = []
            for x in range(w):
                row.append(float_to_hex(data[y, x]))
            grid.append(row)
            
        return grid

def generate_fluid_payload(plot_id: str, lat: float, lng: float, polygon_coords: List = None) -> Dict[str, Any]:
    """Generates the fluid zones using TRUE spatial data."""
    engine = FluidTopologyEngine(plot_id, lat, lng, polygon_coords)
    
    # Pre-fetch the topology so that engine.width and engine.height are populated
    engine._fetch_baseline_topology()
    
    return {
        "plot_id": plot_id,
        "width": engine.width,
        "height": engine.height,
        "regimes": {
            "drought": engine.to_rgb_heatmap(engine.generate_regime_map('drought')),
            "flood": engine.to_rgb_heatmap(engine.generate_regime_map('flood')),
            "heatwave": engine.to_rgb_heatmap(engine.generate_regime_map('heatwave')),
            "optimal": engine.to_rgb_heatmap(engine.generate_regime_map('optimal'))
        }
    }
