"""
DJI Cloud Gateway Simulator.

Simulates a DJI RC Plus / Pilot 2 gateway connected to your MQTT broker.
This is the most important fake environment for DJI integration testing.

It:
  - Subscribes to the services topic (commands from AgriWise)
  - Processes flighttask_prepare, flighttask_execute, pause, resume, RTL, abort
  - Emits telemetry OSD packets during flight
  - Emits mission events (state transitions)
  - Produces media manifests after flight

Architecture:
  AgriWise (MQTTBridge) ←→ SimMessageBus ←→ GatewaySimulator
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import logging
import threading
import time

from .device_state import DeviceStateMachine, DeviceMissionState, FailureInjection
from .service_router import SimMessageBus
from .media_sim import generate_media_manifest

logger = logging.getLogger(__name__)


class GatewaySimulator:
    """Simulates a DJI Cloud API gateway (RC Plus + Pilot 2).
    
    Connects to the SimMessageBus as a "gateway" client and responds
    to service commands the same way a real gateway would.
    """
    
    def __init__(
        self,
        bus: SimMessageBus,
        gateway_sn: str = "SIM_GATEWAY_001",
        device_sn: str = "SIM_DRONE_001",
        failure: Optional[FailureInjection] = None,
    ):
        self._bus = bus
        self._gateway_sn = gateway_sn
        self._device_sn = device_sn
        self._device = DeviceStateMachine(failure=failure)
        self._running = False
        self._media_manifest: Optional[Dict] = None
        
        # Topics
        self._services_topic = f"thing/product/{gateway_sn}/services"
        self._services_reply_topic = f"thing/product/{gateway_sn}/services_reply"
        self._events_topic = f"thing/product/{gateway_sn}/events"
        self._osd_topic = f"thing/product/{device_sn}/osd"
        
        # Register with bus
        self._bus.register_client(f"gateway_{gateway_sn}", self._on_message)
        self._bus.subscribe(f"gateway_{gateway_sn}", self._services_topic)
    
    @property
    def device(self) -> DeviceStateMachine:
        return self._device
    
    @property
    def media_manifest(self) -> Optional[Dict]:
        return self._media_manifest
    
    # ====================================================================
    # Message handling
    # ====================================================================
    
    def _on_message(self, topic: str, payload: Dict[str, Any]):
        """Handle incoming service commands."""
        if topic != self._services_topic:
            return
        
        method = payload.get("method", "")
        tid = payload.get("tid", "")
        data = payload.get("data", {})
        
        # Route to handler
        handler = {
            "flighttask_prepare": self._handle_prepare,
            "flighttask_execute": self._handle_execute,
            "flight_task_pause": self._handle_pause,
            "flight_task_resume": self._handle_resume,
            "return_home": self._handle_rtl,
            "emergency_stop": self._handle_abort,
            "get_media_manifest": self._handle_media_manifest,
        }.get(method)
        
        if handler is None:
            self._reply(tid, method, {"result": -1, "output": {"status": "unknown_method"}})
            return
        
        result = handler(data)
        if result is not None:
            self._reply(tid, method, result)
    
    def _reply(self, tid: str, method: str, result: Dict[str, Any]):
        """Send a service reply."""
        payload = {
            "tid": tid,
            "method": method,
            **result,
        }
        self._bus.publish_to_all(self._services_reply_topic, payload)
    
    # ====================================================================
    # Service handlers
    # ====================================================================
    
    def _handle_prepare(self, data: Dict) -> Optional[Dict]:
        result = self._device.prepare_mission(data)
        if result is None:
            return None  # Simulate timeout
        
        # Emit state event
        self._emit_event("mission_state", {"state": self._device.state.value})
        return result
    
    def _handle_execute(self, data: Dict) -> Dict:
        result = self._device.execute_mission()
        
        if result.get("result") == 0:
            self._emit_event("mission_state", {"state": "executing"})
            # Start telemetry stream in a thread
            self._running = True
            t = threading.Thread(target=self._telemetry_loop, daemon=True)
            t.start()
        
        return result
    
    def _handle_pause(self, data: Dict) -> Dict:
        result = self._device.pause_mission()
        if result.get("result") == 0:
            self._emit_event("mission_state", {"state": "paused"})
        return result
    
    def _handle_resume(self, data: Dict) -> Dict:
        result = self._device.resume_mission()
        if result.get("result") == 0:
            self._emit_event("mission_state", {"state": "executing"})
        return result
    
    def _handle_rtl(self, data: Dict) -> Dict:
        result = self._device.return_home()
        if result.get("result") == 0:
            self._emit_event("mission_state", {"state": "returning"})
        return result
    
    def _handle_abort(self, data: Dict) -> Dict:
        result = self._device.abort_mission()
        self._emit_event("mission_state", {"state": "failed"})
        return result
    
    def _handle_media_manifest(self, data: Dict) -> Dict:
        manifest = generate_media_manifest(self._device, flight_id=data.get("flight_id", ""))
        self._media_manifest = manifest
        return {"result": 0, "output": manifest}
    
    # ====================================================================
    # Telemetry loop
    # ====================================================================
    
    def _telemetry_loop(self):
        """Emit OSD telemetry at ~1Hz while mission is active."""
        while self._running:
            if self._device.state == DeviceMissionState.EXECUTING:
                # Advance waypoint
                still_flying = self._device.advance_waypoint()
                
                # Emit OSD
                osd = self._device.get_osd_payload()
                self._bus.publish_to_all(self._osd_topic, osd)
                
                if not still_flying:
                    # Mission ended (complete or failed)
                    if self._device.state == DeviceMissionState.RETURNING:
                        self._device.complete_return()
                        self._emit_event("mission_state", {"state": "completed"})
                    elif self._device.state == DeviceMissionState.FAILED:
                        self._emit_event("mission_state", {"state": "failed"})
                    
                    # Generate media
                    self._media_manifest = generate_media_manifest(
                        self._device, flight_id="sim_flight"
                    )
                    self._running = False
                    break
            
            elif self._device.state == DeviceMissionState.PAUSED:
                # Still emit OSD while paused (no waypoint advance)
                osd = self._device.get_osd_payload()
                self._bus.publish_to_all(self._osd_topic, osd)
            
            elif self._device.state in (
                DeviceMissionState.COMPLETED,
                DeviceMissionState.FAILED,
                DeviceMissionState.IDLE,
            ):
                self._running = False
                break
            
            # Small sleep to avoid busy-loop in tests
            time.sleep(0.001)
    
    def _emit_event(self, event_type: str, data: Dict[str, Any]):
        """Emit a device event."""
        payload = {
            "method": event_type,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        self._bus.publish_to_all(self._events_topic, payload)
    
    # ====================================================================
    # Direct control (for testing)
    # ====================================================================
    
    def run_full_mission(self) -> Dict:
        """Run the full mission lifecycle synchronously for testing.
        
        Simulates prepare → execute → fly → complete without MQTT.
        Returns the final device state.
        """
        self._device.prepare_mission({"flight_id": "direct_test", "waypoint_count": 10})
        self._device.execute_mission()
        
        while self._device.state == DeviceMissionState.EXECUTING:
            self._device.advance_waypoint()
        
        if self._device.state == DeviceMissionState.RETURNING:
            self._device.complete_return()
        
        self._media_manifest = generate_media_manifest(self._device, "direct_test")
        
        return {
            "state": self._device.state.value,
            "captures": self._device.vehicle.capture_count,
            "battery": self._device.vehicle.battery_pct,
        }
    
    def stop(self):
        """Stop the gateway simulator."""
        self._running = False
        self._bus.unregister_client(f"gateway_{self._gateway_sn}")
