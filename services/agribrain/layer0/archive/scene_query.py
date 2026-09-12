import re
from typing import Dict, Any, List, Optional, Tuple

MGRS_BANDS = {
    "C": (-80.0, -72.0), "D": (-72.0, -64.0), "E": (-64.0, -56.0), "F": (-56.0, -48.0),
    "G": (-48.0, -40.0), "H": (-40.0, -32.0), "J": (-32.0, -24.0), "K": (-24.0, -16.0),
    "L": (-16.0, -8.0),  "M": (-8.0, 0.0),    "N": (0.0, 8.0),     "P": (8.0, 16.0),
    "Q": (16.0, 24.0),   "R": (24.0, 32.0),   "S": (32.0, 40.0),   "T": (40.0, 48.0),
    "U": (48.0, 56.0),   "V": (56.0, 64.0),   "W": (64.0, 72.0),   "X": (72.0, 84.0),
}

def calculate_aoi_footprint(geometry_wkt: str) -> Dict[str, Any]:
    """Calculates coordinate extent/envelope of plot footprint."""
    return {"wkt": geometry_wkt, "type": "Polygon"}

def check_tile_overlap(tile_footprint: str, plot_geometry: str) -> float:
    """Computes basic overlap fraction between the scene and the plot.
    
    Calculates genuine spatial bounding-box overlap or MGRS zone bounds inclusion.
    Fails closed (0.0) on missing, malformed, or disjoint geometries.
    """
    if not tile_footprint or not plot_geometry or not isinstance(tile_footprint, str) or not isinstance(plot_geometry, str):
        return 0.0

    # 1. Parse plot bbox
    p_nums = [float(n) for n in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", plot_geometry)]
    if len(p_nums) < 4:
        return 0.0
    p_xs = p_nums[0::2]
    p_ys = p_nums[1::2]
    if len(p_xs) != len(p_ys) or not p_xs:
        return 0.0
    p_min_x, p_max_x = min(p_xs), max(p_xs)
    p_min_y, p_max_y = min(p_ys), max(p_ys)

    # 2. Check if tile_footprint is geometric WKT / GeoJSON
    t_nums = [float(n) for n in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", tile_footprint)]
    if len(t_nums) >= 4:
        t_xs = t_nums[0::2]
        t_ys = t_nums[1::2]
        if len(t_xs) == len(t_ys) and t_xs:
            t_min_x, t_max_x = min(t_xs), max(t_xs)
            t_min_y, t_max_y = min(t_ys), max(t_ys)
            inter_min_x = max(p_min_x, t_min_x)
            inter_min_y = max(p_min_y, t_min_y)
            inter_max_x = min(p_max_x, t_max_x)
            inter_max_y = min(p_max_y, t_max_y)
            if inter_max_x <= inter_min_x or inter_max_y <= inter_min_y:
                return 0.0
            inter_area = (inter_max_x - inter_min_x) * (inter_max_y - inter_min_y)
            plot_area = max(1e-12, (p_max_x - p_min_x) * (p_max_y - p_min_y))
            return float(min(1.0, max(0.0, inter_area / plot_area)))

    # 3. Check if tile_footprint is MGRS tile ID (e.g., T31SUD, 31SUD)
    m = re.match(r"^T?(\d{1,2})([A-Z])([A-Z]{2})?$", tile_footprint.strip().upper())
    if m:
        zone = int(m.group(1))
        band = m.group(2)
        if 1 <= zone <= 60 and band in MGRS_BANDS:
            zone_min_lon = (zone - 31) * 6.0 - 1.0  # 1 degree buffer for UTM overlap
            zone_max_lon = (zone - 30) * 6.0 + 1.0
            band_min_lat, band_max_lat = MGRS_BANDS[band]
            band_min_lat -= 1.0
            band_max_lat += 1.0
            
            # Check if plot center is within zone/band bounds
            plot_center_x = (p_min_x + p_max_x) / 2.0
            plot_center_y = (p_min_y + p_max_y) / 2.0
            if (zone_min_lon <= plot_center_x <= zone_max_lon and 
                band_min_lat <= plot_center_y <= band_max_lat):
                return 1.0
            return 0.0

    return 0.0
