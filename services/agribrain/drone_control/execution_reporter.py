"""
Drone Control — Execution Reporter.

Builds an ExecutionReport for EVERY mission, including failed ones.
Reports feed mission history, temporal comparison, refly planning,
and operator audit.
"""

from __future__ import annotations
from typing import List, Optional
import logging

from .schemas import (
    CompiledMission,
    ExecutionReport,
    HealthWarning,
    LiveMissionState,
    MediaManifest,
)
from .mission_state_machine import MissionStateMachine
from .telemetry_ingest import TelemetryIngestor, TelemetrySummary
from .failsafe_controller import FailsafeController
from .media_handoff import HandoffResult

logger = logging.getLogger(__name__)


class ExecutionReporter:
    """Builds post-mission execution reports.
    
    Every mission produces a report, even failed ones. The report
    provides:
    - Planned vs flown comparison
    - Coverage and overlap estimates
    - Battery usage
    - Safety events and failsafe actions
    - Media handoff status
    - Complete provenance chain
    """
    
    def build_report(
        self,
        state_machine: MissionStateMachine,
        compiled_mission: Optional[CompiledMission] = None,
        telemetry: Optional[TelemetryIngestor] = None,
        failsafe: Optional[FailsafeController] = None,
        handoff: Optional[HandoffResult] = None,
        manifest: Optional[MediaManifest] = None,
    ) -> ExecutionReport:
        """Build a complete execution report.
        
        Args:
            state_machine: The mission state machine
            compiled_mission: The compiled mission (if compilation succeeded)
            telemetry: The telemetry ingestor (if flight occurred)
            failsafe: The failsafe controller (if runtime was active)
            handoff: The media handoff result (if handoff occurred)
            manifest: The media manifest (if media was captured)
        """
        report = ExecutionReport(
            execution_id=state_machine.execution_id,
            final_state=state_machine.state,
            success=state_machine.state == LiveMissionState.COMPLETED,
        )
        
        # Timing from state machine history
        history = state_machine.history
        if history:
            report.started_at = history[0].timestamp
            report.completed_at = history[-1].timestamp
            report.duration_s = state_machine.get_duration_s()
        
        # Mission metadata
        if compiled_mission:
            report.mission_id = compiled_mission.mission_id
            report.plot_id = compiled_mission.plot_id
            report.flight_mode = compiled_mission.flight_mode
            report.mission_type = compiled_mission.mission_type
            report.driver_type = compiled_mission.driver_type        # runtime driver
            report.vehicle_profile = compiled_mission.drone_profile  # vehicle capability
            report.compiler_version = compiled_mission.compiler_version
            
            # Planned metrics
            report.planned_distance_m = compiled_mission.estimated_distance_m
            report.planned_waypoints = len(compiled_mission.waypoints)
            report.expected_captures = compiled_mission.estimated_captures
        
        # Telemetry-derived metrics
        if telemetry and telemetry.packet_count > 0:
            summary = telemetry.summarize()
            
            report.flown_distance_m = summary.flown_distance_m
            report.mean_off_track_m = summary.mean_off_track_m
            report.max_off_track_m = summary.max_off_track_m
            report.completed_waypoints = summary.max_waypoint_reached + 1
            
            # Battery
            report.battery_start_pct = summary.battery_start_pct
            report.battery_end_pct = summary.battery_end_pct
            report.battery_used_pct = summary.battery_used_pct
            
            # Captures
            report.actual_captures = summary.total_captures
            report.capture_completeness_pct = summary.capture_completeness_pct
            
            # Coverage estimate (from progress)
            report.coverage_estimate_pct = summary.final_progress_pct
            
            # Overlap estimate (based on capture completeness and planned overlap)
            if compiled_mission and compiled_mission.target_overlap_pct > 0:
                completeness_factor = summary.capture_completeness_pct / 100.0
                report.overlap_estimate_pct = (
                    compiled_mission.target_overlap_pct * completeness_factor
                )
        
        # Failsafe events
        if failsafe:
            report.warnings_triggered = list(failsafe.records)
            report.failsafe_actions_taken = failsafe.actions_taken
            report.segment_failures = sum(
                1 for r in failsafe.records
                if r.action_taken.value in ("abort", "rtl", "land_now")
            )
        
        # Media handoff
        if handoff:
            report.media_handoff_status = "completed" if handoff.success else "failed"
            report.media_handoff_target = handoff.target
        elif manifest:
            report.media_handoff_status = "pending"
        else:
            report.media_handoff_status = "no_media"
        
        if manifest:
            report.media_manifest = manifest
        
        logger.info(
            f"[ExecutionReporter] Report built: "
            f"state={report.final_state.value}, "
            f"success={report.success}, "
            f"captures={report.actual_captures}/{report.expected_captures}, "
            f"distance={report.flown_distance_m:.0f}m"
        )
        
        return report
