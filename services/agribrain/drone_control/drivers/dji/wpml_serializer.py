"""
DJI Cloud API — WPML/KMZ Serializer.

Converts CompiledMission into a DJI-compatible KMZ wayline package:
  - template.kml  → mission config, drone/payload info, safety actions
  - waylines.wpml → executable waypoint sequence with actions

The KMZ is a ZIP archive containing both files.

Reference: DJI Cloud API WPML specification
  xmlns:wpml="http://www.dji.com/wpmz/1.0.2"
"""

from __future__ import annotations
from io import BytesIO
from typing import List, Optional, Tuple
from xml.etree.ElementTree import Element, SubElement, tostring
import datetime
import logging
import uuid
import zipfile

from ...schemas import CompiledMission, CompiledWaypoint
from .dji_config import DJICloudConfig, DJIDroneModel, DJIPayloadModel

logger = logging.getLogger(__name__)

# XML namespaces
KML_NS = "http://www.opengis.net/kml/2.2"
WPML_NS = "http://www.dji.com/wpmz/1.0.2"

# Heading mode mapping: AgriWise → DJI WPML
_HEADING_MAP = {
    "course": "followWayline",
    "fixed": "fixed",
    "poi": "towardPOI",
}

# Action type mapping
_ACTION_MAP = {
    "stop_and_capture": "takePhoto",
    "flythrough": None,                   # No action on flythrough
    "start_capture": "startRecord",
    "stop_capture": "stopRecord",
    "hover": "hover",
}


class WPMLSerializer:
    """Serializes CompiledMission into DJI WPML/KMZ format.
    
    Output: bytes of a .kmz ZIP archive containing:
      - wpmz/template.kml
      - wpmz/waylines.wpml
      - wpmz/res/ (empty resource directory)
    """
    
    def __init__(self, config: DJICloudConfig):
        self._config = config
    
    def serialize(self, mission: CompiledMission) -> bytes:
        """Serialize a CompiledMission to KMZ bytes.
        
        Args:
            mission: The compiled mission to serialize
            
        Returns:
            bytes of a ZIP archive (.kmz)
        """
        template_kml = self._build_template_kml(mission)
        waylines_wpml = self._build_waylines_wpml(mission)
        
        return self._package_kmz(template_kml, waylines_wpml)
    
    def validate(self, mission: CompiledMission) -> List[str]:
        """Validate a CompiledMission for DJI compatibility.
        
        Returns list of validation errors. Empty = valid.
        """
        errors = []
        
        if not mission.waypoints:
            errors.append("Mission has no waypoints")
        
        if len(mission.waypoints) > 65535:
            errors.append(f"Too many waypoints: {len(mission.waypoints)} (max 65535)")
        
        for i, wp in enumerate(mission.waypoints):
            if not (-90 <= wp.latitude <= 90):
                errors.append(f"Waypoint {i}: latitude {wp.latitude} out of range")
            if not (-180 <= wp.longitude <= 180):
                errors.append(f"Waypoint {i}: longitude {wp.longitude} out of range")
            if not (0 <= wp.altitude_m <= 1500):
                errors.append(f"Waypoint {i}: altitude {wp.altitude_m}m out of range (0-1500)")
            if not (0.1 <= wp.speed_m_s <= 15.0):
                errors.append(f"Waypoint {i}: speed {wp.speed_m_s}m/s out of range (0.1-15)")
        
        if mission.flight_altitude_m < 2.0:
            errors.append(f"Flight altitude {mission.flight_altitude_m}m too low (min 2m)")
        
        return errors
    
    # ====================================================================
    # template.kml
    # ====================================================================
    
    def _build_template_kml(self, mission: CompiledMission) -> bytes:
        """Build the template.kml content."""
        kml = Element("kml", xmlns=KML_NS)
        kml.set("xmlns:wpml", WPML_NS)
        
        document = SubElement(kml, "Document")
        
        # Mission config
        mission_config = SubElement(document, f"{{{WPML_NS}}}missionConfig")
        
        # Drone info
        SubElement(mission_config, f"{{{WPML_NS}}}flyToWaylineMode").text = "safely"
        SubElement(mission_config, f"{{{WPML_NS}}}finishAction").text = self._config.finish_action
        SubElement(mission_config, f"{{{WPML_NS}}}exitOnRCLost").text = self._config.exit_on_rc_lost
        SubElement(mission_config, f"{{{WPML_NS}}}takeOffSecurityHeight").text = str(
            self._config.takeoff_security_height_m
        )
        SubElement(mission_config, f"{{{WPML_NS}}}globalTransitionalSpeed").text = str(
            mission.cruise_speed_m_s
        )
        
        # Drone model
        drone_info = SubElement(mission_config, f"{{{WPML_NS}}}droneInfo")
        SubElement(drone_info, f"{{{WPML_NS}}}droneEnumValue").text = self._config.drone_model.value
        SubElement(drone_info, f"{{{WPML_NS}}}droneSubEnumValue").text = "0"
        
        # Payload info
        payload_info = SubElement(mission_config, f"{{{WPML_NS}}}payloadInfo")
        SubElement(payload_info, f"{{{WPML_NS}}}payloadEnumValue").text = self._config.payload_model.value
        SubElement(payload_info, f"{{{WPML_NS}}}payloadPositionIndex").text = str(
            self._config.payload_position
        )
        SubElement(payload_info, f"{{{WPML_NS}}}payloadSubEnumValue").text = "0"
        
        # Template folder (waypoint template)
        folder = SubElement(document, "Folder")
        SubElement(folder, f"{{{WPML_NS}}}templateType").text = "waypoint"
        SubElement(folder, f"{{{WPML_NS}}}templateId").text = "0"
        SubElement(folder, f"{{{WPML_NS}}}autoFlightSpeed").text = str(mission.cruise_speed_m_s)
        
        # Waypoint headings in template (simplified)
        for i, wp in enumerate(mission.waypoints):
            placemark = SubElement(folder, "Placemark")
            
            point = SubElement(placemark, "Point")
            SubElement(point, "coordinates").text = f"{wp.longitude},{wp.latitude}"
            
            SubElement(placemark, f"{{{WPML_NS}}}index").text = str(i)
            SubElement(placemark, f"{{{WPML_NS}}}executeHeight").text = str(wp.altitude_m)
            SubElement(placemark, f"{{{WPML_NS}}}waypointSpeed").text = str(wp.speed_m_s)
        
        return tostring(kml, encoding="unicode", xml_declaration=True).encode("utf-8")
    
    # ====================================================================
    # waylines.wpml
    # ====================================================================
    
    def _build_waylines_wpml(self, mission: CompiledMission) -> bytes:
        """Build the waylines.wpml content."""
        kml = Element("kml", xmlns=KML_NS)
        kml.set("xmlns:wpml", WPML_NS)
        
        document = SubElement(kml, "Document")
        
        # Mission config (repeated in wpml for execution)
        mission_config = SubElement(document, f"{{{WPML_NS}}}missionConfig")
        SubElement(mission_config, f"{{{WPML_NS}}}flyToWaylineMode").text = "safely"
        SubElement(mission_config, f"{{{WPML_NS}}}finishAction").text = self._config.finish_action
        SubElement(mission_config, f"{{{WPML_NS}}}exitOnRCLost").text = self._config.exit_on_rc_lost
        SubElement(mission_config, f"{{{WPML_NS}}}takeOffSecurityHeight").text = str(
            self._config.takeoff_security_height_m
        )
        SubElement(mission_config, f"{{{WPML_NS}}}globalTransitionalSpeed").text = str(
            mission.cruise_speed_m_s
        )
        
        # Drone + payload (same as template)
        drone_info = SubElement(mission_config, f"{{{WPML_NS}}}droneInfo")
        SubElement(drone_info, f"{{{WPML_NS}}}droneEnumValue").text = self._config.drone_model.value
        SubElement(drone_info, f"{{{WPML_NS}}}droneSubEnumValue").text = "0"
        
        payload_info = SubElement(mission_config, f"{{{WPML_NS}}}payloadInfo")
        SubElement(payload_info, f"{{{WPML_NS}}}payloadEnumValue").text = self._config.payload_model.value
        SubElement(payload_info, f"{{{WPML_NS}}}payloadPositionIndex").text = str(
            self._config.payload_position
        )
        
        # Executable folder
        folder = SubElement(document, "Folder")
        SubElement(folder, f"{{{WPML_NS}}}templateId").text = "0"
        SubElement(folder, f"{{{WPML_NS}}}executeHeightMode").text = "relativeToStartPoint"
        SubElement(folder, f"{{{WPML_NS}}}waylineId").text = "0"
        SubElement(folder, f"{{{WPML_NS}}}autoFlightSpeed").text = str(mission.cruise_speed_m_s)
        
        # Waypoints with actions
        heading_mode = _HEADING_MAP.get(mission.heading_policy, "followWayline")
        
        for i, wp in enumerate(mission.waypoints):
            placemark = SubElement(folder, "Placemark")
            
            # Position
            point = SubElement(placemark, "Point")
            SubElement(point, "coordinates").text = f"{wp.longitude},{wp.latitude}"
            
            # Waypoint metadata
            SubElement(placemark, f"{{{WPML_NS}}}index").text = str(i)
            SubElement(placemark, f"{{{WPML_NS}}}executeHeight").text = str(wp.altitude_m)
            SubElement(placemark, f"{{{WPML_NS}}}waypointSpeed").text = str(wp.speed_m_s)
            
            # Heading
            heading_param = SubElement(placemark, f"{{{WPML_NS}}}waypointHeadingParam")
            SubElement(heading_param, f"{{{WPML_NS}}}waypointHeadingMode").text = heading_mode
            if heading_mode == "fixed":
                SubElement(heading_param, f"{{{WPML_NS}}}waypointHeadingAngle").text = str(wp.heading_deg)
            SubElement(heading_param, f"{{{WPML_NS}}}waypointHeadingPathMode").text = "followBadArc"
            
            # Turn mode
            SubElement(placemark, f"{{{WPML_NS}}}waypointTurnParam")
            
            # Action group (gimbal + capture)
            action_group = SubElement(placemark, f"{{{WPML_NS}}}actionGroup")
            SubElement(action_group, f"{{{WPML_NS}}}actionGroupId").text = str(i)
            SubElement(action_group, f"{{{WPML_NS}}}actionGroupStartIndex").text = str(i)
            SubElement(action_group, f"{{{WPML_NS}}}actionGroupEndIndex").text = str(i)
            SubElement(action_group, f"{{{WPML_NS}}}actionGroupMode").text = "sequence"
            SubElement(action_group, f"{{{WPML_NS}}}actionTrigger").text = "reachPoint"
            
            action_idx = 0
            
            # Gimbal rotate action
            gimbal_action = SubElement(action_group, f"{{{WPML_NS}}}action")
            SubElement(gimbal_action, f"{{{WPML_NS}}}actionId").text = str(action_idx)
            SubElement(gimbal_action, f"{{{WPML_NS}}}actionActuatorFunc").text = "gimbalRotate"
            gimbal_params = SubElement(gimbal_action, f"{{{WPML_NS}}}actionActuatorFuncParam")
            SubElement(gimbal_params, f"{{{WPML_NS}}}gimbalPitchRotateAngle").text = str(wp.gimbal_pitch_deg)
            SubElement(gimbal_params, f"{{{WPML_NS}}}gimbalRollRotateAngle").text = "0"
            SubElement(gimbal_params, f"{{{WPML_NS}}}gimbalYawRotateAngle").text = "0"
            SubElement(gimbal_params, f"{{{WPML_NS}}}gimbalRotateMode").text = "absoluteAngle"
            SubElement(gimbal_params, f"{{{WPML_NS}}}payloadPositionIndex").text = str(
                self._config.payload_position
            )
            action_idx += 1
            
            # Camera capture action (if this waypoint triggers capture)
            if wp.capture:
                capture_action = SubElement(action_group, f"{{{WPML_NS}}}action")
                SubElement(capture_action, f"{{{WPML_NS}}}actionId").text = str(action_idx)
                SubElement(capture_action, f"{{{WPML_NS}}}actionActuatorFunc").text = "takePhoto"
                capture_params = SubElement(capture_action, f"{{{WPML_NS}}}actionActuatorFuncParam")
                SubElement(capture_params, f"{{{WPML_NS}}}payloadPositionIndex").text = str(
                    self._config.payload_position
                )
                SubElement(capture_params, f"{{{WPML_NS}}}fileSuffix").text = "photo"
                action_idx += 1
        
        return tostring(kml, encoding="unicode", xml_declaration=True).encode("utf-8")
    
    # ====================================================================
    # KMZ packaging
    # ====================================================================
    
    def _package_kmz(self, template_kml: bytes, waylines_wpml: bytes) -> bytes:
        """Package template.kml + waylines.wpml into a KMZ ZIP archive."""
        buffer = BytesIO()
        
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("wpmz/template.kml", template_kml)
            zf.writestr("wpmz/waylines.wpml", waylines_wpml)
            # Empty res directory (required by spec)
            zf.writestr("wpmz/res/.keep", "")
        
        kmz_bytes = buffer.getvalue()
        logger.info(f"[WPML] Packaged KMZ: {len(kmz_bytes)} bytes")
        return kmz_bytes
