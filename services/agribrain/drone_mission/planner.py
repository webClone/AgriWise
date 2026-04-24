"""
Drone Mission Planner.

Translates MissionIntent into a feasible FlightPlan.
"""

from typing import Dict, Any, Tuple
import uuid

from .schemas import MissionIntent, FlightPlan, FlightMode, MissionType, CoveragePattern, DroneCapabilityProfile
from .capability_profiles import get_profile
from .safety_rules import check_feasibility
from . import coverage_patterns

class DroneMissionPlanner:
    
    def __init__(self, default_profile: str = "standard_prosumer"):
        self.default_profile = default_profile
        
    def _calculate_altitude_for_gsd(self, profile: DroneCapabilityProfile, target_gsd_cm: float) -> float:
        """Calculate required altitude to achieve target GSD."""
        # Derived from: GSD(mm) = (alt(m) * 1000 * sensor_w) / (focal_l * img_w)
        target_gsd_mm = target_gsd_cm * 10.0
        alt_m = (target_gsd_mm * profile.focal_length_mm * profile.image_width_px) / (1000.0 * profile.sensor_width_mm)
        return alt_m

    def _determine_pattern(self, intent: MissionIntent) -> CoveragePattern:
        """Select best pattern based on mission type."""
        if intent.mission_type == MissionType.CONCERN_ZONE_COMMAND:
            return CoveragePattern.SPIRAL
        elif intent.mission_type == MissionType.ROW_AUDIT:
            return CoveragePattern.ROW_ALIGNED
        else:
            return CoveragePattern.BOUSTROPHEDON

    def plan_mission(self, intent: MissionIntent, profile_override: str = None) -> FlightPlan:
        """Generate a flight plan from an intent."""
        profile = get_profile(profile_override or self.default_profile)
        
        # 1. Calculate flight altitude based on requested GSD
        alt_m = self._calculate_altitude_for_gsd(profile, intent.target_gsd_cm)
        
        # 2. Determine path overlap spacing
        footprint_w, footprint_h = profile.calculate_footprint(alt_m)
        spacing_m = footprint_h * (1.0 - (intent.required_overlap_pct / 100.0))
        
        # 3. Generate waypoints based on pattern
        pattern = self._determine_pattern(intent)
        waypoints = []
        if pattern == CoveragePattern.SPIRAL:
            radius = footprint_w / 2.0
            waypoints = coverage_patterns.plan_spiral(intent.polygon_geojson, alt_m, radius)
        elif pattern == CoveragePattern.ROW_ALIGNED:
            # Requires crop row azimuth, assume 0 for now
            waypoints = coverage_patterns.plan_row_aligned(intent.polygon_geojson, alt_m, spacing_m, 0.0)
        elif intent.mission_type == MissionType.FULL_PLOT_MAP:
            # V1.5: Use pass direction optimization for full-plot maps
            waypoints, _ = coverage_patterns.optimize_pass_direction(
                intent.polygon_geojson, alt_m, spacing_m,
            )
        else:
            # V1.5: Use adaptive boustrophedon (skips narrow passes)
            waypoints = coverage_patterns.plan_adaptive_boustrophedon(
                intent.polygon_geojson, alt_m, spacing_m,
            )
            
        # 4. Estimate metrics
        dist_m = 0.0
        # Simple euclidian estimate for flight distance
        for i in range(len(waypoints)-1):
            w1, w2 = waypoints[i], waypoints[i+1]
            dx = (w2.lon - w1.lon) * 85000.0
            dy = (w2.lat - w1.lat) * 111000.0
            dist_m += (dx*dx + dy*dy)**0.5
            
        est_time_min = (dist_m / profile.max_speed_m_s) / 60.0
        est_images = int((dist_m / profile.max_speed_m_s) / 2.0) # Assume 1 image per 2 seconds
        
        plan = FlightPlan(
            plan_id=f"plan_{uuid.uuid4().hex[:8]}",
            intent_id=intent.intent_id,
            drone_profile=profile.name,
            pattern=pattern,
            waypoints=waypoints,
            estimated_flight_time_min=est_time_min,
            estimated_image_count=max(1, est_images),
            achieved_gsd_cm=intent.target_gsd_cm, # In real life, camera constraints might modify this
            flight_altitude_m=alt_m
        )
        
        # 5. Feasibility check
        is_feasible, reason = check_feasibility(intent, plan, profile)
        plan.is_feasible = is_feasible
        plan.infeasibility_reason = reason if not is_feasible else None
        
        return plan
