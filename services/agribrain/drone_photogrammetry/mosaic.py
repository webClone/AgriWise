"""
Stage H — Mosaic Generation.

Blends orthorectified tiles into a single unified orthomosaic.

V1: Weighted average blending based on QA weight, with contribution tracking.
V2: Multi-band blending, exposure normalization, advanced seam selection.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import logging

from .schemas import OrthoTile
from .orthorectify import OrthoTileStack

logger = logging.getLogger(__name__)


@dataclass
class MosaicResult:
    """Raw blended orthomosaic before seam optimization and georef."""
    # Pixel data (for benchmark / in-memory pipeline)
    pixels: Optional[Dict[str, List[List[int]]]] = None
    # Dimensions
    width_px: int = 0
    height_px: int = 0
    
    # Map extent
    min_lat: float = 0.0
    max_lat: float = 0.0
    min_lon: float = 0.0
    max_lon: float = 0.0
    
    # Contribution tracking
    contribution_map: List[List[int]] = field(default_factory=list)
    # Grid[y][x] = number of tiles contributing to this cell
    
    # Hole tracking
    hole_map: List[List[bool]] = field(default_factory=list)
    # Grid[y][x] = True if no tile covers this cell
    holes_fraction: float = 0.0
    
    # Quality
    mean_contribution_count: float = 0.0
    contribution_uniformity: float = 1.0
    
    # Which frames contributed where
    frame_contribution_index: Dict[str, int] = field(default_factory=dict)
    # {frame_id: number_of_cells_contributed}


class MosaicGenerator:
    """Blends orthorectified tiles into a unified orthomosaic.
    
    V2: Resolution-aware grid sizing from camera native GSD.
    Weighted average blending. Prefers high-QA, sharp frames.
    Tracks contribution uniformity and hole coverage.
    """
    
    # Maximum grid dimension (caps memory for benchmark performance)
    MAX_GRID_DIM = 500
    # Minimum grid dimension
    MIN_GRID_DIM = 50
    
    def generate(self, tile_stack: OrthoTileStack) -> MosaicResult:
        """Blend tiles into a mosaic.
        
        Args:
            tile_stack: Orthorectified tiles with bounds and QA weights.
            
        Returns:
            MosaicResult with blended pixel data and contribution maps.
        """
        result = MosaicResult(
            min_lat=tile_stack.min_lat,
            max_lat=tile_stack.max_lat,
            min_lon=tile_stack.min_lon,
            max_lon=tile_stack.max_lon,
        )
        
        if not tile_stack.tiles:
            return result
        
        # --- 1. Define output grid (resolution-aware) ---
        lat_range = max(tile_stack.max_lat - tile_stack.min_lat, 1e-7)
        lon_range = max(tile_stack.max_lon - tile_stack.min_lon, 1e-7)
        
        # Compute native GSD from tile pixel density
        h, w = self._compute_grid_dimensions(
            tile_stack, lat_range, lon_range
        )
        
        result.width_px = w
        result.height_px = h
        
        # --- 2. Accumulate weighted pixel values ---
        red_acc = [[0.0] * w for _ in range(h)]
        green_acc = [[0.0] * w for _ in range(h)]
        blue_acc = [[0.0] * w for _ in range(h)]
        weight_acc = [[0.0] * w for _ in range(h)]
        contrib_count = [[0] * w for _ in range(h)]
        
        for tile in tile_stack.tiles:
            self._accumulate_tile(
                tile, result,
                red_acc, green_acc, blue_acc, weight_acc, contrib_count,
                lat_range, lon_range, h, w,
            )
        
        # --- 3. Normalize to get final pixel values ---
        red_out = [[0] * w for _ in range(h)]
        green_out = [[0] * w for _ in range(h)]
        blue_out = [[0] * w for _ in range(h)]
        holes = [[False] * w for _ in range(h)]
        hole_count = 0
        
        for y in range(h):
            for x in range(w):
                if weight_acc[y][x] > 0:
                    red_out[y][x] = min(255, int(red_acc[y][x] / weight_acc[y][x]))
                    green_out[y][x] = min(255, int(green_acc[y][x] / weight_acc[y][x]))
                    blue_out[y][x] = min(255, int(blue_acc[y][x] / weight_acc[y][x]))
                else:
                    holes[y][x] = True
                    hole_count += 1
        
        result.pixels = {"red": red_out, "green": green_out, "blue": blue_out}
        result.contribution_map = contrib_count
        result.hole_map = holes
        result.holes_fraction = hole_count / max(h * w, 1)
        
        # --- 4. Contribution statistics ---
        flat_contrib = [contrib_count[y][x] for y in range(h) for x in range(w)]
        non_hole = [c for c in flat_contrib if c > 0]
        if non_hole:
            result.mean_contribution_count = sum(non_hole) / len(non_hole)
            mean_c = result.mean_contribution_count
            if mean_c > 0:
                variance = sum((c - mean_c) ** 2 for c in non_hole) / len(non_hole)
                cv = (variance ** 0.5) / mean_c
                result.contribution_uniformity = max(0.0, 1.0 - cv)
        
        logger.info(
            f"[Mosaic] {w}x{h} grid, "
            f"holes={result.holes_fraction:.1%}, "
            f"mean_contrib={result.mean_contribution_count:.1f}, "
            f"uniformity={result.contribution_uniformity:.2f}"
        )
        
        return result
    
    def _accumulate_tile(
        self,
        tile: OrthoTile,
        result: MosaicResult,
        red_acc, green_acc, blue_acc, weight_acc, contrib_count,
        lat_range, lon_range, h, w,
    ) -> None:
        """Accumulate a single tile's contribution to the mosaic grid."""
        # Map tile bounds to grid coordinates
        y_start = int((tile.min_lat - result.min_lat) / lat_range * h)
        y_end = int((tile.max_lat - result.min_lat) / lat_range * h)
        x_start = int((tile.min_lon - result.min_lon) / lon_range * w)
        x_end = int((tile.max_lon - result.min_lon) / lon_range * w)
        
        y_start = max(0, min(h - 1, y_start))
        y_end = max(0, min(h, y_end))
        x_start = max(0, min(w - 1, x_start))
        x_end = max(0, min(w, x_end))
        
        weight = tile.qa_weight * tile.usable_fraction
        cells_contributed = 0
        
        if tile.synthetic_pixels:
            # Use actual pixel data from synthetic frames
            src_red = tile.synthetic_pixels.get("red", [])
            src_green = tile.synthetic_pixels.get("green", [])
            src_blue = tile.synthetic_pixels.get("blue", [])
            
            src_h = len(src_green) if src_green else 0
            src_w = len(src_green[0]) if src_h > 0 else 0
            
            tile_h = max(1, y_end - y_start)
            tile_w = max(1, x_end - x_start)
            
            for dy in range(tile_h):
                y = y_start + dy
                if y >= h:
                    break
                src_y = int(dy / tile_h * src_h) if src_h > 0 else 0
                src_y = min(src_y, src_h - 1)
                
                for dx in range(tile_w):
                    x = x_start + dx
                    if x >= w:
                        break
                    src_x = int(dx / tile_w * src_w) if src_w > 0 else 0
                    src_x = min(src_x, src_w - 1)
                    
                    if src_h > 0 and src_w > 0:
                        r = src_red[src_y][src_x] if src_red else 0
                        g = src_green[src_y][src_x]
                        b = src_blue[src_y][src_x] if src_blue else 0
                    else:
                        r, g, b = 128, 128, 128
                    
                    red_acc[y][x] += r * weight
                    green_acc[y][x] += g * weight
                    blue_acc[y][x] += b * weight
                    weight_acc[y][x] += weight
                    contrib_count[y][x] += 1
                    cells_contributed += 1
        else:
            # No pixel data — fill with a neutral value
            for y in range(y_start, min(y_end, h)):
                for x in range(x_start, min(x_end, w)):
                    red_acc[y][x] += 128 * weight
                    green_acc[y][x] += 128 * weight
                    blue_acc[y][x] += 128 * weight
                    weight_acc[y][x] += weight
                    contrib_count[y][x] += 1
                    cells_contributed += 1
        
        result.frame_contribution_index[tile.frame_id] = cells_contributed
    
    def _compute_grid_dimensions(
        self,
        tile_stack: OrthoTileStack,
        lat_range: float,
        lon_range: float,
    ) -> tuple:
        """Compute output grid dimensions from tile pixel density.
        
        Strategy: estimate the native GSD from the source frame pixel
        dimensions and their geographic footprints, then size the output
        grid to approximately match the native resolution (capped for
        benchmark performance).
        """
        import math
        
        # Collect per-tile pixel densities (pixels per degree)
        densities_lat = []
        densities_lon = []
        
        for tile in tile_stack.tiles:
            tile_lat_span = max(tile.max_lat - tile.min_lat, 1e-9)
            tile_lon_span = max(tile.max_lon - tile.min_lon, 1e-9)
            
            # Estimate source frame pixel dimensions
            src_h = 30  # Default synthetic frame height
            src_w = 40  # Default synthetic frame width
            if tile.synthetic_pixels:
                green = tile.synthetic_pixels.get("green", [])
                if green:
                    src_h = len(green)
                    src_w = len(green[0]) if green else 40
            
            densities_lat.append(src_h / tile_lat_span)
            densities_lon.append(src_w / tile_lon_span)
        
        if densities_lat:
            # Use median density to avoid outlier skew
            densities_lat.sort()
            densities_lon.sort()
            mid = len(densities_lat) // 2
            median_density_lat = densities_lat[mid]
            median_density_lon = densities_lon[mid]
            
            # Target output dimensions
            h = max(self.MIN_GRID_DIM, int(lat_range * median_density_lat))
            w = max(self.MIN_GRID_DIM, int(lon_range * median_density_lon))
        else:
            # Fallback: aspect-ratio-based
            base = self.MIN_GRID_DIM * 2
            if lat_range >= lon_range:
                h = base
                w = max(1, int(base * lon_range / lat_range))
            else:
                w = base
                h = max(1, int(base * lat_range / lon_range))
        
        # Cap at MAX_GRID_DIM to keep benchmark fast
        if h > self.MAX_GRID_DIM or w > self.MAX_GRID_DIM:
            scale = min(self.MAX_GRID_DIM / h, self.MAX_GRID_DIM / w)
            h = max(self.MIN_GRID_DIM, int(h * scale))
            w = max(self.MIN_GRID_DIM, int(w * scale))
        
        return h, w
