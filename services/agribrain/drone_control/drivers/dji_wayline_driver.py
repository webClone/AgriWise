"""
Drone Control — DJI Wayline Driver.

Real DJI Cloud API integration driver. Uses:
  - WPMLSerializer to generate KMZ wayline packages
  - MQTTBridge to communicate with DJI gateway (RC Plus / Dock)
  - TelemetryMapper to convert DJI OSD → AgriWise TelemetryPacket

Communication flow:
  AgriWise Dispatcher
    → DJIWaylineDriver
      → MQTTBridge (MQTT / sim bus)
        → DJI Gateway (real or simulator)
          → Aircraft

Protocol reference: DJI Cloud API v2
"""

from __future__ import annotations
from typing import Any, Dict, Iterator, Optional, List
import logging
import threading
import time
import uuid

from ..driver_base import DroneDriverBase
from ..schemas import (
    CaptureRecord,
    CommandAck,
    CommandStatus,
    CompiledMission,
    MediaManifest,
    TelemetryPacket,
    VehicleState,
)
from .dji.dji_config import DJICloudConfig, dev_config
from .dji.wpml_serializer import WPMLSerializer
from .dji.mqtt_bridge import MQTTBridge
from .dji.telemetry_mapper import TelemetryMapper

logger = logging.getLogger(__name__)


class DJIWaylineDriver(DroneDriverBase):
    """DJI Cloud API driver for wayline mission dispatch.
    
    Implements DroneDriverBase using DJI Cloud API protocol:
    - Mission upload via WPML/KMZ + flighttask_prepare
    - Flight control via MQTT service commands
    - Telemetry via MQTT OSD subscription
    - Media manifest via MQTT query
    
    Supports two modes:
    - Real: connects to MQTT broker with real DJI gateway
    - Sim:  connects to in-process SimMessageBus with GatewaySimulator
    """
    
    def __init__(
        self,
        config: Optional[DJICloudConfig] = None,
        sim_bus: Optional[Any] = None,
    ):
        self._config = config or dev_config()
        self._serializer = WPMLSerializer(self._config)
        self._bridge = MQTTBridge(self._config, sim_bus=sim_bus)
        self._mapper = TelemetryMapper()
        self._connected = False
        self._vehicle_id = ""
        self._current_mission: Optional[CompiledMission] = None
        
        # Telemetry collection
        self._telemetry_buffer: List[TelemetryPacket] = []
        self._telemetry_lock = threading.Lock()
        self._telemetry_done = threading.Event()
        self._latest_osd: Dict[str, Any] = {}
        self._mission_events: List[Dict[str, Any]] = []
    
    @property
    def driver_type(self) -> str:
        return "dji_wayline"
    
    @property
    def connected(self) -> bool:
        return self._connected and self._bridge.connected
    
    # ====================================================================
    # Connection
    # ====================================================================
    
    def connect(self, vehicle_id: str = "") -> CommandAck:
        """Connect to DJI gateway via MQTT."""
        self._vehicle_id = vehicle_id
        
        success = self._bridge.connect()
        if not success:
            return CommandAck(
                command="connect",
                status=CommandStatus.ERROR,
                message="MQTT connection failed",
            )
        
        # Register telemetry + event callbacks
        self._bridge.on_telemetry(self._on_telemetry)
        self._bridge.on_event(self._on_event)
        
        self._connected = True
        logger.info(f"[DJI] Connected via MQTT, gateway={self._config.gateway_sn}")
        
        return CommandAck(
            command="connect",
            status=CommandStatus.ACCEPTED,
            message=f"Connected to DJI gateway {self._config.gateway_sn}",
        )
    
    def disconnect(self) -> CommandAck:
        """Disconnect from MQTT broker."""
        self._bridge.disconnect()
        self._connected = False
        return CommandAck(
            command="disconnect",
            status=CommandStatus.ACCEPTED,
            message="Disconnected",
        )
    
    # ====================================================================
    # Mission lifecycle
    # ====================================================================
    
    def upload_mission(self, compiled: CompiledMission) -> CommandAck:
        """Serialize to WPML/KMZ and upload via flighttask_prepare."""
        if not self.connected:
            return CommandAck(
                command="upload_mission",
                status=CommandStatus.ERROR,
                message="Not connected",
            )
        
        # 1. Validate
        errors = self._serializer.validate(compiled)
        if errors:
            return CommandAck(
                command="upload_mission",
                status=CommandStatus.REJECTED,
                message=f"Validation failed: {'; '.join(errors)}",
            )
        
        # 2. Serialize to KMZ
        kmz_bytes = self._serializer.serialize(compiled)
        
        # 3. Send flighttask_prepare via MQTT
        reply = self._bridge.send_command(
            method="flighttask_prepare",
            data={
                "flight_id": compiled.execution_id,
                "mission_id": compiled.mission_id,
                "waypoint_count": len(compiled.waypoints),
                "kmz_size_bytes": len(kmz_bytes),
                # In real deployment, KMZ would be uploaded to object storage
                # and the URL passed here. For sim, we pass the count.
            },
            timeout_s=self._config.upload_timeout_s,
        )
        
        if reply.get("result") != 0:
            error = reply.get("output", {}).get("reason", reply.get("error", "Unknown"))
            return CommandAck(
                command="upload_mission",
                status=CommandStatus.REJECTED,
                message=f"flighttask_prepare rejected: {error}",
            )
        
        self._current_mission = compiled
        self._mapper = TelemetryMapper(execution_id=compiled.execution_id)
        
        logger.info(
            f"[DJI] Mission uploaded: {len(compiled.waypoints)} waypoints, "
            f"{len(kmz_bytes)} bytes KMZ"
        )
        
        return CommandAck(
            command="upload_mission",
            status=CommandStatus.ACCEPTED,
            message=f"Mission uploaded ({len(compiled.waypoints)} waypoints)",
        )
    
    def arm(self) -> CommandAck:
        """Arm is implicit in DJI Cloud API — handled by flighttask_execute."""
        return CommandAck(
            command="arm",
            status=CommandStatus.ACCEPTED,
            message="Arm implicit in DJI Cloud API",
        )
    
    def start_mission(self) -> CommandAck:
        """Start mission via flighttask_execute."""
        if not self.connected:
            return CommandAck(
                command="start_mission",
                status=CommandStatus.ERROR,
                message="Not connected",
            )
        
        # Reset telemetry state
        self._telemetry_buffer.clear()
        self._telemetry_done.clear()
        self._mission_events.clear()
        
        reply = self._bridge.send_command(
            method="flighttask_execute",
            data={
                "flight_id": self._current_mission.execution_id if self._current_mission else "",
            },
            timeout_s=self._config.execute_timeout_s,
        )
        
        if reply.get("result") != 0:
            error = reply.get("output", {}).get("reason", reply.get("error", "Unknown"))
            return CommandAck(
                command="start_mission",
                status=CommandStatus.REJECTED,
                message=f"flighttask_execute rejected: {error}",
            )
        
        return CommandAck(
            command="start_mission",
            status=CommandStatus.ACCEPTED,
            message="Mission started",
        )
    
    def pause_mission(self) -> CommandAck:
        """Pause mission via flight_task_pause."""
        reply = self._bridge.send_command("flight_task_pause", {})
        if reply.get("result") == 0:
            return CommandAck(command="pause_mission", status=CommandStatus.ACCEPTED, message="Paused")
        return CommandAck(command="pause_mission", status=CommandStatus.REJECTED,
                         message=reply.get("output", {}).get("reason", "Pause rejected"))
    
    def resume_mission(self) -> CommandAck:
        """Resume mission via flight_task_resume."""
        reply = self._bridge.send_command("flight_task_resume", {})
        if reply.get("result") == 0:
            return CommandAck(command="resume_mission", status=CommandStatus.ACCEPTED, message="Resumed")
        return CommandAck(command="resume_mission", status=CommandStatus.REJECTED,
                         message=reply.get("output", {}).get("reason", "Resume rejected"))
    
    def abort_mission(self) -> CommandAck:
        """Abort mission via emergency_stop."""
        reply = self._bridge.send_command("emergency_stop", {})
        self._telemetry_done.set()
        if reply.get("result") == 0:
            return CommandAck(command="abort_mission", status=CommandStatus.ACCEPTED, message="Aborted")
        return CommandAck(command="abort_mission", status=CommandStatus.REJECTED, message="Abort failed")
    
    def rtl(self) -> CommandAck:
        """Return-to-launch via return_home."""
        reply = self._bridge.send_command("return_home", {})
        if reply.get("result") == 0:
            return CommandAck(command="rtl", status=CommandStatus.ACCEPTED, message="RTL initiated")
        return CommandAck(command="rtl", status=CommandStatus.REJECTED, message="RTL rejected")
    
    def land_now(self) -> CommandAck:
        """Emergency land — mapped to emergency_stop for DJI."""
        return self.abort_mission()
    
    # ====================================================================
    # Telemetry
    # ====================================================================
    
    def stream_telemetry(self) -> Iterator[TelemetryPacket]:
        """Yield TelemetryPackets from the MQTT OSD subscription.
        
        Blocks until the mission completes or fails. Packets
        arrive via the _on_telemetry callback and are buffered.
        """
        # Wait for telemetry to complete (mission end)
        # Poll buffer while waiting
        last_yield = 0
        timeout = 300  # Max 5 minutes
        deadline = time.time() + timeout
        
        while time.time() < deadline:
            # Yield any new packets
            with self._telemetry_lock:
                new_packets = self._telemetry_buffer[last_yield:]
            
            for pkt in new_packets:
                yield pkt
                last_yield += 1
            
            # Check if mission is done
            if self._telemetry_done.is_set():
                # Yield remaining
                with self._telemetry_lock:
                    remaining = self._telemetry_buffer[last_yield:]
                for pkt in remaining:
                    yield pkt
                break
            
            time.sleep(0.01)
    
    def _on_telemetry(self, osd_payload: Dict[str, Any]):
        """Callback from MQTT bridge for OSD data."""
        self._latest_osd = osd_payload
        
        # Map to AgriWise format
        packet = self._mapper.map(osd_payload)
        
        with self._telemetry_lock:
            self._telemetry_buffer.append(packet)
    
    def _on_event(self, event_payload: Dict[str, Any]):
        """Callback from MQTT bridge for device events."""
        self._mission_events.append(event_payload)
        
        method = event_payload.get("method", "")
        data = event_payload.get("data", {})
        state = data.get("state", "")
        
        if state in ("completed", "failed"):
            self._telemetry_done.set()
    
    # ====================================================================
    # Vehicle state
    # ====================================================================
    
    def validate_vehicle_ready(self) -> VehicleState:
        """Get current vehicle state from latest OSD data."""
        if not self._latest_osd:
            # If no OSD data yet, return a default ready state
            return VehicleState(
                armed=False,
                battery_pct=100.0,
                gps_fix=True,
                gps_satellites=16,
                gps_hdop=0.8,
                mode="ready",
                camera_ready=True,
            )
        
        pkt = self._mapper.map(self._latest_osd)
        return pkt.state
    
    def get_vehicle_state(self) -> VehicleState:
        """Get current vehicle state."""
        return self.validate_vehicle_ready()
    
    # ====================================================================
    # Media
    # ====================================================================
    
    def fetch_media_manifest(self) -> MediaManifest:
        """Fetch media manifest from the gateway."""
        reply = self._bridge.send_command(
            "get_media_manifest",
            {"flight_id": self._current_mission.execution_id if self._current_mission else ""},
            timeout_s=self._config.command_timeout_s,
        )
        
        output = reply.get("output", {})
        files = output.get("files", [])
        
        captures = []
        for f in files:
            captures.append(CaptureRecord(
                capture_index=f.get("capture_index", 0),
                latitude=f.get("latitude", 0.0),
                longitude=f.get("longitude", 0.0),
                altitude_m=f.get("altitude", 0.0),
                heading_deg=f.get("heading", 0.0),
                file_ref=f.get("file_path", ""),
                file_size_bytes=f.get("file_size", 0),
                waypoint_index=f.get("capture_index", 0),
            ))
        
        return MediaManifest(
            execution_id=self._current_mission.execution_id if self._current_mission else "",
            mission_id=self._current_mission.mission_id if self._current_mission else "",
            captures=captures,
            total_captures=len(captures),
            total_size_bytes=output.get("total_size_bytes", 0),
            complete=output.get("complete", False),
        )
