"""
Coverage Patterns.

Algorithms for generating flight paths within polygons.
"""

from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import math
from .schemas import Waypoint

def _get_bounding_box(coords: List[List[float]]) -> Tuple[float, float, float, float]:
    min_lon = min(p[0] for p in coords)
    max_lon = max(p[0] for p in coords)
    min_lat = min(p[1] for p in coords)
    max_lat = max(p[1] for p in coords)
    return min_lon, min_lat, max_lon, max_lat

def _scan_line_intersections(coords: List[List[float]], lat: float) -> List[float]:
    """Find all longitudes where a horizontal scan line at `lat` intersects polygon edges."""
    intersections = []
    n = len(coords)
    for i in range(n):
        j = (i + 1) % n
        y1, y2 = coords[i][1], coords[j][1]
        x1, x2 = coords[i][0], coords[j][0]
        
        if y1 == y2:
            continue  # Horizontal edge, skip
        if not (min(y1, y2) <= lat < max(y1, y2)):
            continue  # Scan line doesn't cross this edge
            
        # Linear interpolation to find x at this y
        t = (lat - y1) / (y2 - y1)
        x_int = x1 + t * (x2 - x1)
        intersections.append(x_int)
    
    intersections.sort()
    return intersections


def plan_boustrophedon(
    polygon_geojson: Dict[str, Any], 
    altitude_m: float, 
    spacing_m: float
) -> List[Waypoint]:
    """Generate a polygon-clipped lawnmower pattern.
    
    Each horizontal pass is clipped to the polygon boundary rather than
    spanning the full bounding box, reducing outside-polygon waste.
    """
    coords = polygon_geojson.get("coordinates", [[[]]])[0]
    if len(coords) < 3:
        return []
        
    min_lon, min_lat, max_lon, max_lat = _get_bounding_box(coords)
    
    # Approx degrees per meter (very rough, at 40 deg lat)
    deg_lat_per_m = 1.0 / 111000.0
    
    spacing_lat = spacing_m * deg_lat_per_m
    
    waypoints = []
    current_lat = min_lat
    direction = 1 # 1 for East, -1 for West
    
    while current_lat <= max_lat:
        # Find polygon intersections at this latitude
        xs = _scan_line_intersections(coords, current_lat)
        
        # Process intersection pairs (entry/exit)
        if len(xs) >= 2:
            # Take the outermost pair for a convex-enough polygon
            x_start = xs[0]
            x_end = xs[-1]
            
            if direction == 1:
                waypoints.append(Waypoint(lat=current_lat, lon=x_start, alt_m=altitude_m))
                waypoints.append(Waypoint(lat=current_lat, lon=x_end, alt_m=altitude_m))
            else:
                waypoints.append(Waypoint(lat=current_lat, lon=x_end, alt_m=altitude_m))
                waypoints.append(Waypoint(lat=current_lat, lon=x_start, alt_m=altitude_m))
            
        current_lat += spacing_lat
        direction *= -1
        
    return waypoints

def plan_contour(
    polygon_geojson: Dict[str, Any], 
    altitude_m: float, 
    spacing_m: float
) -> List[Waypoint]:
    """Generate contour-following passes by adjusting altitude to a mock terrain gradient."""
    # First, generate base 2D paths
    waypoints = plan_boustrophedon(polygon_geojson, altitude_m, spacing_m)
    if not waypoints:
        return []
        
    # Simulate a terrain gradient: ground elevation rises towards the North
    # Ground elevation = (lat - min_lat) * 111000 * slope
    coords = polygon_geojson.get("coordinates", [[[]]])[0]
    _, min_lat, _, _ = _get_bounding_box(coords)
    
    slope = 0.05 # 5% incline
    
    for wp in waypoints:
        dist_north_m = (wp.lat - min_lat) * 111000.0
        ground_elev = dist_north_m * slope
        # Maintain constant altitude AGL
        wp.alt_m = altitude_m + ground_elev
        
    return waypoints

def _rotate_point(x: float, y: float, cx: float, cy: float, angle_rad: float) -> Tuple[float, float]:
    """Rotate a point (x,y) around center (cx,cy) by angle_rad."""
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    nx = cos_a * (x - cx) - sin_a * (y - cy) + cx
    ny = sin_a * (x - cx) + cos_a * (y - cy) + cy
    return nx, ny

def plan_row_aligned(
    polygon_geojson: Dict[str, Any], 
    altitude_m: float, 
    spacing_m: float,
    row_azimuth_deg: float
) -> List[Waypoint]:
    """Generate lawnmower passes strictly parallel to row direction."""
    coords = polygon_geojson.get("coordinates", [[[]]])[0]
    if len(coords) < 3:
        return []
        
    # 1. Find centroid
    cx = sum(p[0] for p in coords) / len(coords)
    cy = sum(p[1] for p in coords) / len(coords)
    
    angle_rad = math.radians(row_azimuth_deg)
    
    # Approx degrees per meter scaling (so rotation is somewhat isometric)
    lon_scale = math.cos(math.radians(cy)) if cy else 1.0
    
    # 2. Rotate polygon coordinates by -angle_rad to align rows horizontally
    rot_coords = []
    for p in coords:
        # Scale lon to match lat distances
        sx = p[0] * lon_scale
        sy = p[1]
        scx = cx * lon_scale
        scy = cy
        rx, ry = _rotate_point(sx, sy, scx, scy, -angle_rad)
        rot_coords.append([rx / lon_scale, ry])
        
    # 3. Create dummy GeoJSON with rotated coords
    dummy_geojson = {"coordinates": [rot_coords]}
    
    # 4. Generate standard boustrophedon in this rotated space
    base_waypoints = plan_boustrophedon(dummy_geojson, altitude_m, spacing_m)
    
    # 5. Rotate waypoints back by +angle_rad
    final_waypoints = []
    for wp in base_waypoints:
        sx = wp.lon * lon_scale
        sy = wp.lat
        scx = cx * lon_scale
        scy = cy
        rx, ry = _rotate_point(sx, sy, scx, scy, angle_rad)
        final_waypoints.append(Waypoint(lat=ry, lon=rx / lon_scale, alt_m=wp.alt_m))
        
    return final_waypoints

def plan_spiral(
    target_zone_geojson: Dict[str, Any], 
    altitude_m: float, 
    radius_m: float
) -> List[Waypoint]:
    """Generate an orbit/spiral around a point of interest for close inspection."""
    coords = target_zone_geojson.get("coordinates", [[[]]])[0]
    if not coords:
        return []
        
    # Center of target zone
    center_lon = sum(p[0] for p in coords) / len(coords)
    center_lat = sum(p[1] for p in coords) / len(coords)
    
    deg_lat_per_m = 1.0 / 111000.0
    deg_lon_per_m = 1.0 / 85000.0
    
    waypoints = []
    num_points = 12
    for i in range(num_points):
        angle = (2 * math.pi * i) / num_points
        d_lat = radius_m * math.cos(angle) * deg_lat_per_m
        d_lon = radius_m * math.sin(angle) * deg_lon_per_m
        waypoints.append(Waypoint(
            lat=center_lat + d_lat, 
            lon=center_lon + d_lon, 
            alt_m=altitude_m
        ))
        
    return waypoints


# ============================================================================
# Geometric Execution Quality Scoring
# ============================================================================

def _point_in_polygon(px: float, py: float, polygon: List[List[float]]) -> bool:
    """Ray-casting point-in-polygon test. Polygon is a list of [lon, lat] pairs."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i][0], polygon[i][1]
        xj, yj = polygon[j][0], polygon[j][1]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _point_in_rotated_rect(
    px: float, py: float,
    cx: float, cy: float,
    half_w: float, half_h: float,
    cos_a: float, sin_a: float
) -> bool:
    """Check if point (px, py) falls inside a rotated rectangle centered at (cx, cy)."""
    # Transform point into rectangle's local coordinate frame
    dx = px - cx
    dy = py - cy
    local_x = dx * cos_a + dy * sin_a
    local_y = -dx * sin_a + dy * cos_a
    return abs(local_x) <= half_w and abs(local_y) <= half_h


@dataclass
class ExecutionQuality:
    """Result of geometric execution quality analysis."""
    coverage_completeness: float = 0.0   # Fraction of polygon covered by footprints
    outside_polygon_waste: float = 0.0   # Fraction of total footprint area outside polygon
    overlap_compliance: float = 0.0      # Fraction of adjacent pairs meeting overlap requirement


def compute_execution_quality(
    polygon_coords: List[List[float]],
    waypoints: List[Waypoint],
    footprint_w_m: float,
    footprint_h_m: float,
    required_overlap_pct: float = 70.0,
    sample_density: int = 50,
) -> ExecutionQuality:
    """
    Compute geometric execution quality metrics via rasterized point sampling.

    This is benchmark-grade geometric scoring, not survey-grade flight certification.
    Coverage/waste/overlap metrics are meaningful for mapping missions (boustrophedon,
    row-aligned). They are not directly comparable for command/orbit revisit missions,
    which deliberately cover only a small target zone.

    Args:
        polygon_coords: GeoJSON-style [[lon, lat], ...] ring (closed)
        waypoints: Planned flight waypoints
        footprint_w_m: Camera footprint width in meters
        footprint_h_m: Camera footprint height in meters
        required_overlap_pct: Minimum overlap between adjacent images (%)
        sample_density: Grid resolution per axis for rasterized sampling
    """
    result = ExecutionQuality()
    if len(polygon_coords) < 3 or len(waypoints) < 1:
        return result

    # --- Constants for degree-to-meter conversion ---
    deg_lat_per_m = 1.0 / 111000.0
    deg_lon_per_m = 1.0 / 85000.0

    # Convert footprint to degrees
    fp_half_w_deg = (footprint_w_m / 2.0) * deg_lon_per_m
    fp_half_h_deg = (footprint_h_m / 2.0) * deg_lat_per_m

    # --- Build bounding box of polygon for sampling grid ---
    min_lon = min(p[0] for p in polygon_coords)
    max_lon = max(p[0] for p in polygon_coords)
    min_lat = min(p[1] for p in polygon_coords)
    max_lat = max(p[1] for p in polygon_coords)

    # --- Pre-compute per-pass swept coverage rectangles ---
    # In continuous capture mode, the drone flies the entire pass line while
    # capturing images. Coverage is the swept area: from (min_lon, pass_lat - h/2)
    # to (max_lon, pass_lat + h/2) across the full pass extent.
    # Waypoints come in pairs: (pass_start, pass_end).
    pass_bboxes = []
    for i in range(0, len(waypoints) - 1, 2):
        w1, w2 = waypoints[i], waypoints[i + 1]
        sweep_min_lon = min(w1.lon, w2.lon) - fp_half_w_deg
        sweep_max_lon = max(w1.lon, w2.lon) + fp_half_w_deg
        sweep_min_lat = w1.lat - fp_half_h_deg  # w1.lat == w2.lat for boustrophedon
        sweep_max_lat = w1.lat + fp_half_h_deg
        pass_bboxes.append((sweep_min_lon, sweep_min_lat, sweep_max_lon, sweep_max_lat))

    # --- Pass 1: Coverage completeness ---
    # Sample ONLY within the polygon bounding box. For each polygon-interior
    # sample, check if any footprint covers it.
    poly_step_lon = (max_lon - min_lon) / sample_density if max_lon > min_lon else 1e-6
    poly_step_lat = (max_lat - min_lat) / sample_density if max_lat > min_lat else 1e-6

    polygon_sample_count = 0
    polygon_covered_count = 0

    for iy in range(sample_density):
        sy = min_lat + (iy + 0.5) * poly_step_lat
        for ix in range(sample_density):
            sx = min_lon + (ix + 0.5) * poly_step_lon
            if not _point_in_polygon(sx, sy, polygon_coords):
                continue
            polygon_sample_count += 1
            for (bx0, by0, bx1, by1) in pass_bboxes:
                if bx0 <= sx <= bx1 and by0 <= sy <= by1:
                    polygon_covered_count += 1
                    break

    # --- Pass 2: Outside-polygon waste ---
    # Sample over the full footprint extent (expanded bounding box).
    # Count footprint samples that fall outside the polygon.
    margin_lon = fp_half_w_deg
    margin_lat = fp_half_h_deg
    exp_min_lon = min_lon - margin_lon
    exp_max_lon = max_lon + margin_lon
    exp_min_lat = min_lat - margin_lat
    exp_max_lat = max_lat + margin_lat
    exp_step_lon = (exp_max_lon - exp_min_lon) / sample_density
    exp_step_lat = (exp_max_lat - exp_min_lat) / sample_density

    footprint_sample_count = 0
    footprint_inside_polygon_count = 0

    for iy in range(sample_density):
        sy = exp_min_lat + (iy + 0.5) * exp_step_lat
        for ix in range(sample_density):
            sx = exp_min_lon + (ix + 0.5) * exp_step_lon
            in_any_footprint = False
            for (bx0, by0, bx1, by1) in pass_bboxes:
                if bx0 <= sx <= bx1 and by0 <= sy <= by1:
                    in_any_footprint = True
                    break
            if in_any_footprint:
                footprint_sample_count += 1
                if _point_in_polygon(sx, sy, polygon_coords):
                    footprint_inside_polygon_count += 1

    # --- Coverage completeness ---
    if polygon_sample_count > 0:
        result.coverage_completeness = polygon_covered_count / polygon_sample_count

    # --- Outside-polygon waste ---
    if footprint_sample_count > 0:
        result.outside_polygon_waste = 1.0 - (footprint_inside_polygon_count / footprint_sample_count)

    # --- Overlap compliance ---
    # For adjacent pass-to-pass transitions (cross-track), check if footprints overlap
    # by at least the required percentage. Skip in-line segments (within the same pass).
    if len(waypoints) >= 2:
        compliant_pairs = 0
        total_pairs = 0
        required_overlap_frac = required_overlap_pct / 100.0

        for i in range(len(waypoints) - 1):
            w1, w2 = waypoints[i], waypoints[i + 1]

            # Distance between waypoints in meters
            dlat_m = (w2.lat - w1.lat) * 111000.0
            dlon_m = (w2.lon - w1.lon) * 85000.0
            dist_m = math.sqrt(dlat_m ** 2 + dlon_m ** 2)

            # Determine if this is a cross-track transition or an in-line pass.
            # Cross-track: primarily latitude change (N-S move between passes).
            # In-line: primarily longitude change (E-W move along a pass).
            if dist_m < 0.1:
                continue  # Near-zero move, skip
            lat_fraction = abs(dlat_m) / dist_m
            if lat_fraction < 0.5:
                continue  # Primarily horizontal = in-line pass, skip

            # This is a cross-track transition — check overlap
            overlap_m = footprint_h_m - dist_m
            if footprint_h_m > 0:
                overlap_frac = max(0.0, overlap_m / footprint_h_m)
            else:
                overlap_frac = 0.0

            total_pairs += 1
            if overlap_frac >= required_overlap_frac:
                compliant_pairs += 1

        if total_pairs > 0:
            result.overlap_compliance = compliant_pairs / total_pairs

    return result


# ============================================================================
# V1.5 Adaptive Planning
# ============================================================================

def plan_adaptive_boustrophedon(
    polygon_geojson: Dict[str, Any],
    altitude_m: float,
    spacing_m: float,
    min_pass_width_m: float = 10.0,
) -> List[Waypoint]:
    """Polygon-clipped lawnmower with adaptive filtering.
    
    Improvements over basic boustrophedon:
      1. Skips scan lines where polygon intersection width < min_pass_width_m
      2. Estimates turn cost for flight time budgeting
      
    Returns waypoints (same format as plan_boustrophedon).
    """
    coords = polygon_geojson.get("coordinates", [[[]]])[0]
    if len(coords) < 3:
        return []

    min_lon, min_lat, max_lon, max_lat = _get_bounding_box(coords)

    deg_lat_per_m = 1.0 / 111000.0
    deg_lon_per_m = 1.0 / 85000.0
    spacing_lat = spacing_m * deg_lat_per_m
    min_pass_width_deg = min_pass_width_m * deg_lon_per_m

    waypoints = []
    direction = 1
    current_lat = min_lat

    while current_lat <= max_lat:
        xs = _scan_line_intersections(coords, current_lat)

        if len(xs) >= 2:
            x_start = xs[0]
            x_end = xs[-1]
            pass_width = x_end - x_start

            # Skip passes that are too narrow to be useful
            if pass_width >= min_pass_width_deg:
                if direction == 1:
                    waypoints.append(Waypoint(lat=current_lat, lon=x_start, alt_m=altitude_m))
                    waypoints.append(Waypoint(lat=current_lat, lon=x_end, alt_m=altitude_m))
                else:
                    waypoints.append(Waypoint(lat=current_lat, lon=x_end, alt_m=altitude_m))
                    waypoints.append(Waypoint(lat=current_lat, lon=x_start, alt_m=altitude_m))

        current_lat += spacing_lat
        direction *= -1

    return waypoints


def _total_path_distance(waypoints: List[Waypoint]) -> float:
    """Compute total Euclidean path distance in meters."""
    dist = 0.0
    for i in range(len(waypoints) - 1):
        dx = (waypoints[i + 1].lon - waypoints[i].lon) * 85000.0
        dy = (waypoints[i + 1].lat - waypoints[i].lat) * 111000.0
        dist += math.sqrt(dx * dx + dy * dy)
    return dist


def optimize_pass_direction(
    polygon_geojson: Dict[str, Any],
    altitude_m: float,
    spacing_m: float,
    row_azimuth_hint_deg: float = None,
) -> Tuple[List[Waypoint], float]:
    """Try multiple pass directions and pick the one with lowest total distance.
    
    Candidates: 0° (N-S), 90° (E-W), row_azimuth_hint_deg (if provided).
    
    Returns:
        (best_waypoints, best_direction_deg)
    """
    candidates = [0.0, 90.0]
    if row_azimuth_hint_deg is not None:
        candidates.append(row_azimuth_hint_deg)

    best_wps = []
    best_dist = float("inf")
    best_dir = 0.0

    for angle in candidates:
        if abs(angle) < 1e-3 or abs(angle - 180) < 1e-3:
            # N-S: use standard boustrophedon
            wps = plan_adaptive_boustrophedon(polygon_geojson, altitude_m, spacing_m)
        elif abs(angle - 90) < 1e-3:
            # E-W: rotate polygon 90°, plan, rotate back
            wps = _plan_rotated(polygon_geojson, altitude_m, spacing_m, 90.0)
        else:
            wps = plan_row_aligned(polygon_geojson, altitude_m, spacing_m, angle)

        dist = _total_path_distance(wps)
        if dist < best_dist and len(wps) >= 2:
            best_dist = dist
            best_wps = wps
            best_dir = angle

    return best_wps, best_dir


def _plan_rotated(
    polygon_geojson: Dict[str, Any],
    altitude_m: float,
    spacing_m: float,
    angle_deg: float,
) -> List[Waypoint]:
    """Plan boustrophedon in a rotated coordinate frame."""
    # Re-use plan_row_aligned which already handles rotation
    return plan_row_aligned(polygon_geojson, altitude_m, spacing_m, angle_deg)

