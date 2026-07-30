"""
Drone Control — Media Handoff.

Routes captured media to the correct downstream engine:
  - MAPPING_MODE → drone_photogrammetry/
  - COMMAND_REVISIT → Farmer Photo path

Preserves full execution provenance through the handoff.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import logging

from .schemas import (
    CompiledMission,
    ExecutionReport,
    MediaManifest,
)

logger = logging.getLogger(__name__)


@dataclass
class HandoffResult:
    """Result of a media handoff."""
    target: str                            # "photogrammetry" or "farmer_photo"
    success: bool = True
    message: str = ""
    
    # What was handed off
    capture_count: int = 0
    execution_id: str = ""
    mission_id: str = ""
    
    # Downstream input object (ready to pass to the target engine)
    downstream_input: Optional[Any] = None
    
    # Provenance attached
    provenance: Dict[str, Any] = field(default_factory=dict)


class MediaHandoff:
    """Post-mission media router.
    
    Classifies execution by flight mode and packages captures for
    the correct downstream engine with full provenance.
    """
    
    def route(
        self,
        manifest: MediaManifest,
        compiled_mission: CompiledMission,
        execution_report: Optional[ExecutionReport] = None,
    ) -> HandoffResult:
        """Route media to the correct downstream engine.
        
        Args:
            manifest: Media captured during the flight
            compiled_mission: The mission that was flown
            execution_report: Optional execution audit (attached as provenance)
            
        Returns:
            HandoffResult with downstream input ready for the target engine
        """
        flight_mode = compiled_mission.flight_mode
        
        # Build common provenance
        provenance = {
            "execution_id": compiled_mission.execution_id,
            "mission_id": compiled_mission.mission_id,
            "plot_id": compiled_mission.plot_id,
            "flight_mode": flight_mode,
            "mission_type": compiled_mission.mission_type,
            "driver_type": compiled_mission.driver_type,         # runtime driver
            "vehicle_profile": compiled_mission.drone_profile,   # vehicle capability
            "compiler_version": compiled_mission.compiler_version,
            "flight_altitude_m": compiled_mission.flight_altitude_m,
            "target_gsd_cm": compiled_mission.target_gsd_cm,
            "target_overlap_pct": compiled_mission.target_overlap_pct,
            "capture_count": manifest.total_captures,
            "pattern": compiled_mission.pattern,
        }
        
        if execution_report:
            provenance["battery_used_pct"] = execution_report.battery_used_pct
            provenance["flown_distance_m"] = execution_report.flown_distance_m
            provenance["coverage_estimate_pct"] = execution_report.coverage_estimate_pct
            provenance["overlap_estimate_pct"] = execution_report.overlap_estimate_pct
        
        if flight_mode == "mapping_mode":
            return self._route_to_photogrammetry(manifest, compiled_mission, provenance)
        elif flight_mode == "command_revisit":
            return self._route_to_farmer_photo(manifest, compiled_mission, provenance)
        else:
            logger.warning(f"[MediaHandoff] Unknown flight mode: {flight_mode}")
            return HandoffResult(
                target="unknown",
                success=False,
                message=f"Unknown flight mode: {flight_mode}",
                capture_count=manifest.total_captures,
                execution_id=compiled_mission.execution_id,
                mission_id=compiled_mission.mission_id,
                provenance=provenance,
            )
    
    def _route_to_photogrammetry(
        self,
        manifest: MediaManifest,
        mission: CompiledMission,
        provenance: Dict[str, Any],
    ) -> HandoffResult:
        """Package mapping captures for drone_photogrammetry.
        
        Builds a DroneFrameSetInput-compatible dict with:
        - frame_refs from capture records
        - GPS from capture records
        - camera model from mission metadata
        - execution provenance
        """
        frame_refs = [c.file_ref for c in manifest.captures]
        frame_gps = [
            {
                "latitude": c.latitude,
                "longitude": c.longitude,
                "altitude_m": c.altitude_m,
                "heading_deg": c.heading_deg,
            }
            for c in manifest.captures
        ]
        
        # Build downstream input dict (compatible with DroneFrameSetInput)
        downstream = {
            "mission_id": mission.mission_id,
            "plot_id": mission.plot_id,
            "flight_mode": "mapping_mode",
            "frame_refs": frame_refs,
            "frame_count": len(frame_refs),
            "frame_gps": frame_gps,
            "target_gsd_cm": mission.target_gsd_cm,
            "target_overlap_pct": mission.target_overlap_pct,
            "flight_altitude_m": mission.flight_altitude_m,
            "source_execution_id": mission.execution_id,
            "vehicle_profile_id": mission.drone_profile,
            "capture_mode": "waypoint",
        }
        
        logger.info(
            f"[MediaHandoff] MAPPING → photogrammetry: "
            f"{len(frame_refs)} frames, mission={mission.mission_id}"
        )
        
        return HandoffResult(
            target="photogrammetry",
            success=True,
            message=f"Routed {len(frame_refs)} mapping captures to photogrammetry",
            capture_count=len(frame_refs),
            execution_id=mission.execution_id,
            mission_id=mission.mission_id,
            downstream_input=downstream,
            provenance=provenance,
        )
    
    def _route_to_farmer_photo(
        self,
        manifest: MediaManifest,
        mission: CompiledMission,
        provenance: Dict[str, Any],
    ) -> HandoffResult:
        """Package command/revisit captures for Farmer Photo.
        
        Each capture becomes a separate FarmerPhotoEngineInput-compatible dict.
        """
        frames = []
        for c in manifest.captures:
            frame = {
                "plot_id": mission.plot_id,
                "image_ref": c.file_ref,
                "user_label": "drone_close_up",
                "capture_source": "drone",
                "mission_id": mission.mission_id,
                "execution_id": mission.execution_id,
                "capture_timestamp": c.timestamp.isoformat() if c.timestamp else "",
                "capture_altitude_m": c.altitude_m,
                "capture_latitude": c.latitude,
                "capture_longitude": c.longitude,
            }
            frames.append(frame)
        
        logger.info(
            f"[MediaHandoff] COMMAND → Farmer Photo: "
            f"{len(frames)} frames, mission={mission.mission_id}"
        )
        
        return HandoffResult(
            target="farmer_photo",
            success=True,
            message=f"Routed {len(frames)} command captures to Farmer Photo",
            capture_count=len(frames),
            execution_id=mission.execution_id,
            mission_id=mission.mission_id,
            downstream_input=frames,
            provenance=provenance,
        )
