"""
Safety and Feasibility Policy for Drone Missions.

Enforces the hard constraints:
1. Leaf-level GSD is impossible for full-plot mapping.
2. Battery limits vs polygon area.
3. Altitude restrictions.
"""

from typing import Tuple, Dict, Any, List
import math

from .schemas import MissionIntent, FlightPlan, FlightMode, MissionType
from .capability_profiles import DroneCapabilityProfile


def _calculate_polygon_area(polygon_geojson: Dict[str, Any]) -> float:
    """Calculate approximate area in square meters from GeoJSON polygon."""
    # Simplified calculation for small plots. A robust version would use pyproj.
    coords = polygon_geojson.get("coordinates", [[[]]])[0]
    if len(coords) < 3:
        return 0.0
        
    area = 0.0
    for i in range(len(coords) - 1):
        p1 = coords[i]
        p2 = coords[i+1]
        # Approx meters per degree at 40 deg latitude
        x1, y1 = p1[0] * 85000, p1[1] * 111000
        x2, y2 = p2[0] * 85000, p2[1] * 111000
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def check_feasibility(
    intent: MissionIntent, 
    plan: FlightPlan, 
    profile: DroneCapabilityProfile
) -> Tuple[bool, str]:
    """
    Check if a flight plan is physically feasible and safe.
    Returns (is_feasible, reason).
    """
    # 1. Mode vs GSD Constraint (The Leaf-Level Rule)
    if intent.flight_mode == FlightMode.MAPPING_MODE:
        if intent.target_gsd_cm < 1.0:
            return False, "MAPPING_MODE rejects GSD < 1.0cm. Leaf-level mapping over entire plots is unrealistic. Use COMMAND_REVISIT_MODE."
            
        area_sqm = _calculate_polygon_area(intent.polygon_geojson)
        # If plot is large (> 5 hectares) and GSD is very tight (< 1.5cm), reject
        if area_sqm > 50000 and intent.target_gsd_cm < 1.5:
            return False, f"Cannot map {area_sqm/10000:.1f}ha plot at {intent.target_gsd_cm}cm GSD. Required battery/image count too high."

    # 2. Altitude Constraints
    if plan.flight_altitude_m < profile.min_safe_altitude_m:
        return False, f"Flight altitude {plan.flight_altitude_m:.1f}m is below safe minimum {profile.min_safe_altitude_m}m."
    if plan.flight_altitude_m > profile.max_safe_altitude_m:
        return False, f"Flight altitude {plan.flight_altitude_m:.1f}m exceeds legal/safe maximum {profile.max_safe_altitude_m}m."

    # 3. Battery / Time Constraints
    safe_flight_time = profile.max_flight_time_min * (1.0 - (profile.return_home_reserve_pct / 100.0))
    if plan.estimated_flight_time_min > safe_flight_time:
        return False, f"Estimated flight time {plan.estimated_flight_time_min:.1f}m exceeds safe battery limit {safe_flight_time:.1f}m."

    # 4. Storage / Image Count Constraints
    # Assuming standard 128GB card limits ~10,000 images per mission safely
    if plan.estimated_image_count > 10000:
        return False, f"Image count {plan.estimated_image_count} exceeds safe single-mission storage capacity."

    return True, "Feasible"
