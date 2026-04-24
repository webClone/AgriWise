"""
Drone Control — Mission Compiler.

Translates FlightPlan from drone_mission/ into CompiledMission.
This is where planner-generated coverage patterns become executable
drone missions with camera trigger actions, heading rules, and
gimbal policies.
"""

from __future__ import annotations
from typing import List, Optional, Tuple
import datetime
import logging
import math
import uuid

from .schemas import CompiledMission, CompiledWaypoint

logger = logging.getLogger(__name__)


# Flight mode → heading/gimbal defaults
_MODE_DEFAULTS = {
    "mapping_mode": {
        "heading_policy": "course",
        "gimbal_pitch_deg": -90.0,
        "capture_cadence_s": 2.0,
    },
    "command_revisit": {
        "heading_policy": "poi",
        "gimbal_pitch_deg": -45.0,
        "capture_cadence_s": 1.0,
    },
}

# Mission type → segment semantics
_MISSION_CAPTURE = {
    "full_plot_map": True,
    "rapid_scout": True,
    "row_audit": True,
    "weed_map": True,
    "orchard_audit": True,
    "concern_zone_command": True,
    "refly_weak_zones": True,
}


class MissionCompiler:
    """Compiles FlightPlan into vendor-neutral CompiledMission.
    
    Responsibilities:
    - Convert planner waypoints into executable waypoint commands
    - Expand pass endpoints into capture actions
    - Insert camera trigger cadence
    - Enforce heading/gimbal rules per mission type
    - Preserve mission intent for downstream routing
    - Validate waypoint sequence
    """
    
    VERSION = "v1"
    
    def compile(
        self,
        flight_plan,          # FlightPlan from drone_mission
        intent=None,          # MissionIntent (optional)
        mission_id: str = "",
        execution_id: str = "",
    ) -> CompiledMission:
        """Compile a FlightPlan into an executable CompiledMission.
        
        Args:
            flight_plan: FlightPlan from drone_mission/planner
            intent: Optional MissionIntent for semantic context
            mission_id: Mission identifier
            execution_id: Execution attempt identifier
            
        Returns:
            CompiledMission ready for upload to a driver
        """
        if not execution_id:
            execution_id = f"exec_{uuid.uuid4().hex[:8]}"
        if not mission_id:
            mission_id = getattr(flight_plan, 'intent_id', '') or f"mission_{uuid.uuid4().hex[:8]}"
        
        # Determine flight mode and mission type
        flight_mode = "mapping_mode"
        mission_type = "full_plot_map"
        plot_id = ""
        intent_id = ""
        
        if intent:
            flight_mode = getattr(intent, 'flight_mode', 'mapping_mode')
            if hasattr(flight_mode, 'value'):
                flight_mode = flight_mode.value
            mission_type = getattr(intent, 'mission_type', 'full_plot_map')
            if hasattr(mission_type, 'value'):
                mission_type = mission_type.value
            plot_id = getattr(intent, 'plot_id', '')
            intent_id = getattr(intent, 'intent_id', '')
        
        # Mode defaults
        defaults = _MODE_DEFAULTS.get(flight_mode, _MODE_DEFAULTS["mapping_mode"])
        
        # Get planner metadata
        altitude = getattr(flight_plan, 'flight_altitude_m', 50.0)
        gsd = getattr(flight_plan, 'achieved_gsd_cm', 2.0)
        pattern = getattr(flight_plan, 'pattern', 'boustrophedon')
        if hasattr(pattern, 'value'):
            pattern = pattern.value
        plan_id = getattr(flight_plan, 'plan_id', '')
        drone_profile = getattr(flight_plan, 'drone_profile', '')
        
        # Optional planner extensions
        capture_cadence = getattr(flight_plan, 'capture_cadence_s', defaults["capture_cadence_s"])
        heading_policy = getattr(flight_plan, 'heading_policy', defaults["heading_policy"])
        gimbal_pitch = getattr(flight_plan, 'gimbal_pitch_deg', defaults["gimbal_pitch_deg"])
        overlap = getattr(flight_plan, 'required_overlap_pct', 75.0)
        if hasattr(flight_plan, 'intent_id'):
            # Try to get from intent if not set on flight_plan
            if not intent_id:
                intent_id = flight_plan.intent_id
        
        # Compile waypoints
        planner_wps = getattr(flight_plan, 'waypoints', [])
        compiled_wps = self._compile_waypoints(
            planner_wps, altitude, heading_policy, gimbal_pitch,
            capture_cadence, pattern, flight_mode,
        )
        
        # Validate
        self._validate_waypoints(compiled_wps)
        
        # Compute metrics
        total_dist = self._compute_total_distance(compiled_wps)
        cruise_speed = self._determine_cruise_speed(compiled_wps)
        est_duration = total_dist / max(cruise_speed, 0.5)
        capture_count = sum(1 for wp in compiled_wps if wp.capture)
        total_passes = max(set(wp.pass_index for wp in compiled_wps), default=0) + 1
        
        mission = CompiledMission(
            mission_id=mission_id,
            execution_id=execution_id,
            waypoints=compiled_wps,
            flight_altitude_m=altitude,
            cruise_speed_m_s=cruise_speed,
            capture_cadence_s=capture_cadence,
            target_overlap_pct=overlap,
            target_gsd_cm=gsd,
            heading_policy=heading_policy,
            gimbal_pitch_deg=gimbal_pitch,
            pattern=pattern,
            total_passes=total_passes,
            estimated_captures=capture_count,
            estimated_distance_m=total_dist,
            estimated_duration_s=est_duration,
            flight_mode=flight_mode,
            mission_type=mission_type,
            plot_id=plot_id,
            intent_id=intent_id,
            source_plan_id=plan_id,
            drone_profile=drone_profile,
            compiler_version=self.VERSION,
        )
        
        logger.info(
            f"[Compiler] Compiled {len(compiled_wps)} waypoints, "
            f"{capture_count} captures, {total_dist:.0f}m, "
            f"mode={flight_mode}, pattern={pattern}"
        )
        
        return mission
    
    def _compile_waypoints(
        self,
        planner_wps,
        default_alt: float,
        heading_policy: str,
        gimbal_pitch: float,
        capture_cadence: float,
        pattern: str,
        flight_mode: str,
    ) -> List[CompiledWaypoint]:
        """Convert planner Waypoints into CompiledWaypoints with capture actions."""
        compiled = []
        pass_idx = 0
        prev_action = None
        
        for i, wp in enumerate(planner_wps):
            lat = getattr(wp, 'lat', 0.0)
            lon = getattr(wp, 'lon', 0.0)
            alt = getattr(wp, 'alt_m', default_alt)
            action = getattr(wp, 'action', 'capture')
            speed = getattr(wp, 'speed_m_s', None) or 5.0
            
            # Determine capture behavior
            should_capture = False
            segment_type = "pass"
            
            if action == "capture":
                should_capture = True
            elif action == "start_capture":
                should_capture = True
                segment_type = "pass"
            elif action == "stop_capture":
                should_capture = True
                segment_type = "pass"
            elif action == "hover":
                should_capture = True
                segment_type = "orbit"
            else:
                segment_type = "transit"
            
            # Track passes: new pass when we see a direction reversal
            # (simplified: assume sequential waypoints in same pass)
            if i > 0 and action == "capture" and prev_action in ("stop_capture", "hover"):
                pass_idx += 1
            
            # Compute heading
            heading = 0.0
            if heading_policy == "course" and i < len(planner_wps) - 1:
                next_wp = planner_wps[i + 1]
                dlat = getattr(next_wp, 'lat', 0.0) - lat
                dlon = getattr(next_wp, 'lon', 0.0) - lon
                heading = math.degrees(math.atan2(dlon, dlat)) % 360.0
            
            cwp = CompiledWaypoint(
                index=i,
                latitude=lat,
                longitude=lon,
                altitude_m=alt,
                speed_m_s=speed,
                action="stop_and_capture" if should_capture and action == "hover" else (
                    "flythrough" if not should_capture else "stop_and_capture"
                ),
                capture=should_capture,
                heading_deg=heading,
                heading_mode=heading_policy,
                gimbal_pitch_deg=gimbal_pitch,
                segment_type=segment_type,
                pass_index=pass_idx,
            )
            compiled.append(cwp)
            prev_action = action
        
        # For mapping mode: if no captures were set, add captures at all pass waypoints
        if flight_mode == "mapping_mode" and not any(wp.capture for wp in compiled):
            for wp in compiled:
                if wp.segment_type == "pass":
                    wp.capture = True
        
        return compiled
    
    def _validate_waypoints(self, waypoints: List[CompiledWaypoint]):
        """Validate compiled waypoint sequence."""
        if not waypoints:
            logger.warning("[Compiler] Empty waypoint sequence")
            return
        
        for i in range(len(waypoints) - 1):
            wp1, wp2 = waypoints[i], waypoints[i + 1]
            
            # Check for duplicate positions
            if (abs(wp1.latitude - wp2.latitude) < 1e-10 and
                abs(wp1.longitude - wp2.longitude) < 1e-10):
                logger.warning(f"[Compiler] Duplicate waypoint at index {i}")
            
            # Check altitude transitions (max 50m step)
            alt_diff = abs(wp1.altitude_m - wp2.altitude_m)
            if alt_diff > 50.0:
                logger.warning(
                    f"[Compiler] Large altitude step {alt_diff:.0f}m "
                    f"at index {i}→{i+1}"
                )
    
    def _compute_total_distance(self, waypoints: List[CompiledWaypoint]) -> float:
        """Compute total path distance in meters."""
        total = 0.0
        for i in range(len(waypoints) - 1):
            wp1, wp2 = waypoints[i], waypoints[i + 1]
            dx = (wp2.longitude - wp1.longitude) * 85000.0
            dy = (wp2.latitude - wp1.latitude) * 111000.0
            total += math.sqrt(dx * dx + dy * dy)
        return total
    
    def _determine_cruise_speed(self, waypoints: List[CompiledWaypoint]) -> float:
        """Determine cruise speed from waypoints."""
        speeds = [wp.speed_m_s for wp in waypoints if wp.speed_m_s > 0]
        if speeds:
            return sum(speeds) / len(speeds)
        return 5.0
