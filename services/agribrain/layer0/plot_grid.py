"""
Layer 0.0: PlotGrid — Canonical Spatial Grid for a Plot

Defines the master 10m grid (Sentinel-2 aligned) that ALL sources
are reprojected/resampled into. This is the spatial foundation.

Key concepts:
  - Fractional alpha mask: alpha[y,x] ∈ [0,1] (not boolean clip)
  - UTM CRS aligned to Sentinel-2 tile grid
  - Per-pixel identity preserved across time
  - All raster sources resampled to this grid
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import math


@dataclass
class PlotGrid:
    """
    The canonical spatial grid for one plot.
    
    Everything in Layer 0 references this grid:
    - Sentinel-2 indices are stored at native resolution (10m)
    - Sentinel-1 SAR is resampled to this grid
    - SoilGrids/FAO priors are resampled to this grid
    - Weather is broadcast as a shared driver (no fake 10m weather)
    - Daily states X[t,y,x,k] live on this grid
    
    The grid is defined by:
    - A UTM CRS (derived from the plot centroid)
    - An origin (top-left corner in UTM)
    - pixel_size = 10m (Sentinel-2 native)
    - width × height in pixels
    - A fractional alpha mask alpha[y,x] ∈ [0,1]
    """
    
    # Grid definition
    crs: str = "EPSG:32631"     # UTM zone (computed from plot centroid)
    origin_x: float = 0.0       # Top-left X in UTM meters
    origin_y: float = 0.0       # Top-left Y in UTM meters
    pixel_size: float = 10.0    # meters (S2 native)
    width: int = 0              # pixels
    height: int = 0             # pixels
    
    # Plot boundary
    polygon_coords_wgs84: List[List[float]] = field(default_factory=list)
    # [[lng, lat], [lng, lat], ...] — original user-drawn boundary
    
    polygon_coords_utm: List[List[float]] = field(default_factory=list)
    # [[x, y], [x, y], ...] — projected into UTM
    
    # Fractional coverage mask: alpha[y][x] ∈ [0.0, 1.0]
    # 0.0 = pixel entirely outside plot
    # 1.0 = pixel entirely inside plot
    # 0.0 < alpha < 1.0 = partial boundary pixel
    alpha: List[List[float]] = field(default_factory=list)
    
    # Boundary quality
    boundary_confidence: float = 0.8  # 0–1 (how much we trust the polygon)
    boundary_source: str = "user_drawn"  # "user_drawn", "cadastral", "auto_detected"
    
    # Buffer zone (pixels outside polygon but within buffer)
    buffer_pixels: int = 2  # extra pixels around polygon for edge effects
    
    @classmethod
    def from_polygon_wgs84(cls, coords: List[List[float]], 
                           pixel_size: float = 10.0,
                           buffer_m: float = 20.0) -> "PlotGrid":
        """
        Build a PlotGrid from a WGS84 polygon.
        
        Args:
            coords: [[lng, lat], ...] polygon ring
            pixel_size: grid cell size in meters (default 10m for S2)
            buffer_m: buffer distance in meters around polygon
            
        Returns:
            PlotGrid with alpha mask computed
        """
        if not coords or len(coords) < 3:
            raise ValueError("Polygon must have at least 3 coordinates")
        
        # 1. Compute centroid
        centroid_lng = sum(c[0] for c in coords) / len(coords)
        centroid_lat = sum(c[1] for c in coords) / len(coords)
        
        # 2. Determine UTM zone
        utm_zone = int((centroid_lng + 180) / 6) + 1
        hemisphere = "north" if centroid_lat >= 0 else "south"
        epsg = 32600 + utm_zone if hemisphere == "north" else 32700 + utm_zone
        crs = f"EPSG:{epsg}"
        
        # 3. Project polygon to UTM (simplified Mercator approximation)
        # In production, use pyproj. This is a pure-Python fallback.
        utm_coords = [cls._wgs84_to_utm_approx(c[0], c[1], utm_zone, hemisphere == "north") 
                      for c in coords]
        
        # 4. Compute bounding box in UTM + buffer
        xs = [c[0] for c in utm_coords]
        ys = [c[1] for c in utm_coords]
        min_x = min(xs) - buffer_m
        max_x = max(xs) + buffer_m
        min_y = min(ys) - buffer_m
        max_y = max(ys) + buffer_m
        
        # 5. Align origin to pixel grid (snap to pixel_size multiples)
        origin_x = math.floor(min_x / pixel_size) * pixel_size
        origin_y = math.ceil(max_y / pixel_size) * pixel_size  # top-left Y
        
        # 6. Compute grid dimensions
        w = int(math.ceil((max_x - origin_x) / pixel_size))
        h = int(math.ceil((origin_y - min_y) / pixel_size))
        
        # Cap at reasonable size (prevent accidental huge grids)
        MAX_DIM = 500  # 500 × 10m = 5km
        w = min(w, MAX_DIM)
        h = min(h, MAX_DIM)
        
        buffer_pixels = max(1, int(buffer_m / pixel_size))
        
        # 7. Build fractional alpha mask
        alpha = cls._compute_alpha_mask(
            utm_coords, origin_x, origin_y, w, h, pixel_size
        )
        
        return cls(
            crs=crs,
            origin_x=origin_x,
            origin_y=origin_y,
            pixel_size=pixel_size,
            width=w,
            height=h,
            polygon_coords_wgs84=coords,
            polygon_coords_utm=utm_coords,
            alpha=alpha,
            buffer_pixels=buffer_pixels,
        )
    
    @staticmethod
    def _wgs84_to_utm_approx(lng: float, lat: float, 
                               zone: int, northern: bool) -> List[float]:
        """
        Approximate WGS84 -> UTM conversion (pure Python).
        Accurate to ~1m for small areas. In production, use pyproj.
        """
        import math as m
        
        # WGS84 ellipsoid
        a = 6378137.0
        f = 1 / 298.257223563
        e2 = 2 * f - f * f
        e_prime2 = e2 / (1 - e2)
        
        lat_rad = m.radians(lat)
        lng_rad = m.radians(lng)
        lng0 = m.radians((zone - 1) * 6 - 180 + 3)  # central meridian
        
        N = a / m.sqrt(1 - e2 * m.sin(lat_rad) ** 2)
        T = m.tan(lat_rad) ** 2
        C = e_prime2 * m.cos(lat_rad) ** 2
        A = m.cos(lat_rad) * (lng_rad - lng0)
        
        # Meridional arc
        M = a * (
            (1 - e2 / 4 - 3 * e2**2 / 64) * lat_rad
            - (3 * e2 / 8 + 3 * e2**2 / 32) * m.sin(2 * lat_rad)
            + (15 * e2**2 / 256) * m.sin(4 * lat_rad)
        )
        
        k0 = 0.9996
        
        easting = k0 * N * (
            A + (1 - T + C) * A**3 / 6
            + (5 - 18 * T + T**2) * A**5 / 120
        ) + 500000.0
        
        northing = k0 * (
            M + N * m.tan(lat_rad) * (
                A**2 / 2 + (5 - T + 9 * C + 4 * C**2) * A**4 / 24
                + (61 - 58 * T + T**2) * A**6 / 720
            )
        )
        
        if not northern:
            northing += 10000000.0
        
        return [easting, northing]
    
    @staticmethod
    def _utm_to_wgs84_approx(easting: float, northing: float,
                               zone: int, northern: bool) -> List[float]:
        """Approximate UTM -> WGS84 (inverse of above)."""
        import math as m
        
        a = 6378137.0
        f = 1 / 298.257223563
        e2 = 2 * f - f * f
        e1 = (1 - m.sqrt(1 - e2)) / (1 + m.sqrt(1 - e2))
        k0 = 0.9996
        
        x = easting - 500000.0
        y = northing
        if not northern:
            y -= 10000000.0
        
        M = y / k0
        mu = M / (a * (1 - e2 / 4 - 3 * e2**2 / 64))
        
        phi1 = mu + (3 * e1 / 2 - 27 * e1**3 / 32) * m.sin(2 * mu)
        phi1 += (21 * e1**2 / 16 - 55 * e1**4 / 32) * m.sin(4 * mu)
        
        N1 = a / m.sqrt(1 - e2 * m.sin(phi1)**2)
        T1 = m.tan(phi1)**2
        C1 = (e2 / (1 - e2)) * m.cos(phi1)**2
        R1 = a * (1 - e2) / (1 - e2 * m.sin(phi1)**2)**1.5
        D = x / (N1 * k0)
        
        lat = phi1 - (N1 * m.tan(phi1) / R1) * (
            D**2 / 2 - (5 + 3 * T1) * D**4 / 24
        )
        lng = (D - (1 + 2 * T1 + C1) * D**3 / 6) / m.cos(phi1)
        
        lng0 = m.radians((zone - 1) * 6 - 180 + 3)
        
        return [m.degrees(lng + lng0), m.degrees(lat)]
    
    @staticmethod
    def _compute_alpha_mask(polygon_utm: List[List[float]],
                             origin_x: float, origin_y: float,
                             width: int, height: int,
                             pixel_size: float) -> List[List[float]]:
        """
        Compute fractional coverage mask using sub-pixel sampling.
        
        For each pixel, samples a 4×4 sub-grid and counts how many
        sub-pixels fall inside the polygon. This gives alpha ∈ {0, 1/16, ..., 1}.
        """
        SUB = 4  # 4×4 sub-pixel sampling
        sub_step = pixel_size / SUB
        
        alpha = []
        for row in range(height):
            row_alpha = []
            for col in range(width):
                # Pixel center in UTM
                px = origin_x + (col + 0.5) * pixel_size
                py = origin_y - (row + 0.5) * pixel_size
                
                # Sub-pixel sampling
                inside_count = 0
                for si in range(SUB):
                    for sj in range(SUB):
                        sx = origin_x + col * pixel_size + (sj + 0.5) * sub_step
                        sy = origin_y - row * pixel_size - (si + 0.5) * sub_step
                        if _point_in_polygon(sx, sy, polygon_utm):
                            inside_count += 1
                
                row_alpha.append(inside_count / (SUB * SUB))
            alpha.append(row_alpha)
        
        return alpha
    
    def pixel_to_utm(self, row: int, col: int) -> Tuple[float, float]:
        """Convert pixel (row, col) to UTM center coordinate."""
        x = self.origin_x + (col + 0.5) * self.pixel_size
        y = self.origin_y - (row + 0.5) * self.pixel_size
        return (x, y)
    
    def utm_to_pixel(self, x: float, y: float) -> Tuple[int, int]:
        """Convert UTM coordinate to nearest pixel (row, col)."""
        col = int((x - self.origin_x) / self.pixel_size)
        row = int((self.origin_y - y) / self.pixel_size)
        return (max(0, min(row, self.height - 1)),
                max(0, min(col, self.width - 1)))
    
    def pixel_to_wgs84(self, row: int, col: int) -> Tuple[float, float]:
        """Convert pixel to WGS84 (lat, lng)."""
        x, y = self.pixel_to_utm(row, col)
        epsg = int(self.crs.split(":")[1])
        zone = epsg % 100 if epsg < 32700 else (epsg - 32700)
        northern = epsg < 32700
        lng, lat = self._utm_to_wgs84_approx(x, y, zone, northern)
        return (lat, lng)
    
    def inside_mask(self, threshold: float = 0.5) -> List[List[bool]]:
        """Boolean mask: True if alpha >= threshold."""
        return [[self.alpha[r][c] >= threshold 
                 for c in range(self.width)] 
                for r in range(self.height)]
    
    def n_valid_pixels(self, threshold: float = 0.5) -> int:
        """Count pixels with alpha >= threshold."""
        return sum(1 for r in range(self.height) 
                   for c in range(self.width) 
                   if self.alpha[r][c] >= threshold)
    
    def weighted_mean(self, values: List[List[float]]) -> float:
        """Compute alpha-weighted mean of a 2D raster."""
        total_w = 0.0
        total_v = 0.0
        for r in range(min(self.height, len(values))):
            for c in range(min(self.width, len(values[r]))):
                a = self.alpha[r][c]
                if a > 0:
                    total_w += a
                    total_v += a * values[r][c]
        return total_v / total_w if total_w > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "crs": self.crs,
            "origin": [self.origin_x, self.origin_y],
            "pixel_size": self.pixel_size,
            "width": self.width,
            "height": self.height,
            "n_valid_pixels": self.n_valid_pixels(),
            "boundary_confidence": self.boundary_confidence,
            "boundary_source": self.boundary_source,
        }
    
    def __repr__(self) -> str:
        n = self.n_valid_pixels()
        return (f"PlotGrid({self.width}×{self.height} @ {self.pixel_size}m, "
                f"{n} valid px, {self.crs})")


# ============================================================================
# Geometry utilities (pure Python, no dependencies)
# ============================================================================

def _point_in_polygon(x: float, y: float, polygon: List[List[float]]) -> bool:
    """Ray-casting point-in-polygon test."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside
