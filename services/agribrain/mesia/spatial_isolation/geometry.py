"""MESIA Cadastral Geometry, Local ENU Projection, & Polygon Erosion.

Provides geodesy transformations and inward boundary erosion to separate
P_plot into protected core P_core and perimeter buffer margin P_buffer.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple


def geodetic_to_local_enu(
    lat: float, lon: float, origin_lat: float, origin_lon: float
) -> Tuple[float, float]:
    """Convert geodetic (lat, lon) in degrees to local ENU (east_m, north_m)."""
    r_earth = 6378137.0  # WGS-84 equatorial radius in metres
    lat_rad = math.radians(origin_lat)
    d_lat = math.radians(lat - origin_lat)
    d_lon = math.radians(lon - origin_lon)

    north_m = d_lat * r_earth
    east_m = d_lon * r_earth * math.cos(lat_rad)
    return east_m, north_m


def local_enu_to_geodetic(
    east_m: float, north_m: float, origin_lat: float, origin_lon: float
) -> Tuple[float, float]:
    """Convert local ENU (east_m, north_m) to geodetic (lat, lon) in degrees."""
    r_earth = 6378137.0
    lat_rad = math.radians(origin_lat)
    d_lat = north_m / r_earth
    d_lon = east_m / (r_earth * math.cos(lat_rad))

    lat = origin_lat + math.degrees(d_lat)
    lon = origin_lon + math.degrees(d_lon)
    return lat, lon


def polygon_area(polygon_enu: List[Tuple[float, float]]) -> float:
    """Compute polygon area in square metres using standard shoelace formula."""
    n = len(polygon_enu)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += polygon_enu[i][0] * polygon_enu[j][1]
        area -= polygon_enu[j][0] * polygon_enu[i][1]
    return abs(area) * 0.5


def point_in_polygon(x: float, y: float, polygon_enu: List[Tuple[float, float]]) -> bool:
    """Ray casting algorithm to determine whether point (x, y) is inside polygon_enu."""
    n = len(polygon_enu)
    if n < 3:
        return False
    inside = False
    p1x, p1y = polygon_enu[0]
    for i in range(n + 1):
        p2x, p2y = polygon_enu[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def distance_point_to_segment(
    px: float, py: float, x1: float, y1: float, x2: float, y2: float
) -> float:
    """Minimum Euclidean distance from point (px, py) to line segment (x1, y1)-(x2, y2)."""
    dx = x2 - x1
    dy = y2 - y1
    l2 = dx * dx + dy * dy
    if l2 == 0.0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def distance_point_to_polygon_boundary(
    x: float, y: float, polygon_enu: List[Tuple[float, float]]
) -> float:
    """Minimum Euclidean distance from point (x, y) to the nearest polygon boundary edge."""
    n = len(polygon_enu)
    if n < 2:
        return 0.0
    min_dist = float("inf")
    for i in range(n):
        j = (i + 1) % n
        d = distance_point_to_segment(
            x, y, polygon_enu[i][0], polygon_enu[i][1], polygon_enu[j][0], polygon_enu[j][1]
        )
        if d < min_dist:
            min_dist = d
    return min_dist


def compute_dynamic_buffer_width(
    footprint_minor_axis_m: float,
    sigma_cadastre_m: float = 0.5,
    sigma_receiver_m: float = 0.2,
    min_guard_m: float = 3.0,
    platform_scale: float = 1.0,
) -> float:
    """Compute physics-informed dynamic perimeter buffer margin width w_buffer.

    Equation:
    w_buffer = max(min_guard, sqrt(sigma_cad^2 + sigma_rx^2 + (0.5 * footprint_minor)^2) * platform_scale)
    """
    variance_terms = (sigma_cadastre_m ** 2) + (sigma_receiver_m ** 2) + ((0.5 * footprint_minor_axis_m) ** 2)
    computed_width = math.sqrt(variance_terms) * platform_scale
    return float(max(min_guard_m, computed_width))


def erode_polygon_inward(
    polygon_enu: List[Tuple[float, float]], buffer_width_m: float
) -> List[Tuple[float, float]]:
    """Erodes a 2D planar polygon inward by buffer_width_m to form P_core.

    Uses inward edge normal shifting and line intersection. If buffer width
    exceeds polygon radius, falls back to an appropriately scaled centroid polygon.
    """
    n = len(polygon_enu)
    if n < 3 or buffer_width_m <= 0.0:
        return list(polygon_enu)

    # Compute centroid
    cx = sum(p[0] for p in polygon_enu) / n
    cy = sum(p[1] for p in polygon_enu) / n

    # Check minimum distance from centroid to edges
    centroid_dist = distance_point_to_polygon_boundary(cx, cy, polygon_enu)
    if buffer_width_m >= centroid_dist * 0.95:
        # Scale towards centroid to maintain a non-degenerate core
        scale = max(0.05, 1.0 - (buffer_width_m / max(1.0, centroid_dist)))
        return [(cx + scale * (p[0] - cx), cy + scale * (p[1] - cy)) for p in polygon_enu]

    # Calculate inward unit normals for each edge
    eroded_vertices: List[Tuple[float, float]] = []
    # Ensure polygon orientation is counter-clockwise
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += polygon_enu[i][0] * polygon_enu[j][1] - polygon_enu[j][0] * polygon_enu[i][1]
    is_ccw = area > 0

    edge_normals = []
    for i in range(n):
        j = (i + 1) % n
        dx = polygon_enu[j][0] - polygon_enu[i][0]
        dy = polygon_enu[j][1] - polygon_enu[i][1]
        length = math.hypot(dx, dy)
        if length < 1e-6:
            edge_normals.append((0.0, 0.0))
            continue
        if is_ccw:
            # Inward normal for CCW polygon is (-dy, dx)
            nx = -dy / length
            ny = dx / length
        else:
            nx = dy / length
            ny = -dx / length
        edge_normals.append((nx, ny))

    # Compute offset vertices by averaging adjacent normals and scaling
    for i in range(n):
        prev_i = (i - 1 + n) % n
        n1 = edge_normals[prev_i]
        n2 = edge_normals[i]
        bisector_x = n1[0] + n2[0]
        bisector_y = n1[1] + n2[1]
        b_len = math.hypot(bisector_x, bisector_y)
        if b_len < 1e-6:
            vx = polygon_enu[i][0] + n1[0] * buffer_width_m
            vy = polygon_enu[i][1] + n1[1] * buffer_width_m
        else:
            cos_half = (n1[0] * bisector_x + n1[1] * bisector_y) / b_len
            d = buffer_width_m / max(0.2, cos_half)
            vx = polygon_enu[i][0] + (bisector_x / b_len) * d
            vy = polygon_enu[i][1] + (bisector_y / b_len) * d
        eroded_vertices.append((vx, vy))

    # Verify eroded polygon area is smaller and positive
    core_area = polygon_area(eroded_vertices)
    orig_area = polygon_area(polygon_enu)
    if 0.0 < core_area < orig_area:
        return eroded_vertices
    else:
        # Fallback to radial centroid shrinkage
        scale = max(0.1, 1.0 - (buffer_width_m / max(5.0, centroid_dist)))
        return [(cx + scale * (p[0] - cx), cy + scale * (p[1] - cy)) for p in polygon_enu]


def classify_point_region(
    x: float, y: float, polygon_plot: List[Tuple[float, float]], polygon_core: List[Tuple[float, float]]
) -> str:
    """Classifies (x, y) into 'CORE', 'PERIMETER_BUFFER', or 'OUT_OF_PLOT'."""
    if point_in_polygon(x, y, polygon_core):
        return "CORE"
    elif point_in_polygon(x, y, polygon_plot):
        return "PERIMETER_BUFFER"
    else:
        return "OUT_OF_PLOT"
