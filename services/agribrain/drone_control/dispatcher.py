"""
Drone Control — Dispatcher.

The main orchestration entrypoint. One method can dispatch any supported
mission — Mapping and Command both work through the same dispatcher.

Flow:
  1. Select driver
  2. Run preflight
  3. Compile mission
  4. Connect → upload → arm → start
  5. Stream telemetry
  6. Track state via state machine
  7. Return DispatchResult
"""

from __future__ import annotations
from typing import Dict, List, Optional, Type
import logging
import uuid

from .schemas import (
    CommandStatus,
    DispatchRequest,
    DispatchResult,
    LiveMissionState,
    TelemetryPacket,
)
from .driver_base import DroneDriverBase
from .drivers.mock_driver import MockDriver
from .drivers.dji_wayline_driver import DJIWaylineDriver
from .drivers.mavsdk_driver import MAVSDKDriver
from .mission_compiler import MissionCompiler
from .mission_state_machine import MissionStateMachine
from .preflight import PreflightGate
from .telemetry_ingest import TelemetryIngestor
from .health_monitor import HealthMonitor
from .failsafe_controller import FailsafeController

logger = logging.getLogger(__name__)


# Driver registry
_DRIVER_REGISTRY: Dict[str, Type[DroneDriverBase]] = {
    "mock": MockDriver,
    "dji_wayline": DJIWaylineDriver,
    "mavsdk": MAVSDKDriver,
}


def register_driver(name: str, driver_class: Type[DroneDriverBase]):
    """Register a new driver type."""
    _DRIVER_REGISTRY[name] = driver_class


class Dispatcher:
    """Main mission dispatch orchestrator.
    
    Provides a single dispatch() method that handles the full lifecycle:
    preflight → compile → connect → upload → arm → start → telemetry → complete.
    """
    
    def __init__(self):
        self._compiler = MissionCompiler()
        self._preflight = PreflightGate()
        self._active_missions: Dict[str, MissionStateMachine] = {}
    
    def dispatch(self, request: DispatchRequest) -> DispatchResult:
        """Dispatch a mission to a drone.
        
        This is the single entrypoint for all mission types.
        
        Args:
            request: DispatchRequest with flight plan, vehicle, and safety policy
            
        Returns:
            DispatchResult with success/failure status and execution details
        """
        execution_id = request.execution_id or f"exec_{uuid.uuid4().hex[:8]}"
        mission_id = request.mission_id
        
        sm = MissionStateMachine(execution_id=execution_id)
        self._active_missions[execution_id] = sm
        
        # 1. Select driver
        driver = self._get_driver(request.driver_type)
        if driver is None:
            return self._fail(execution_id, mission_id, sm, "preflight",
                              f"Unknown driver type: {request.driver_type}")
        
        # 2. Connect
        connect_ack = driver.connect(request.vehicle_id)
        if connect_ack.status != CommandStatus.ACCEPTED:
            return self._fail(execution_id, mission_id, sm, "connect",
                              f"Connect failed: {connect_ack.message}")
        
        try:
            # 3. Preflight
            vehicle_state = driver.validate_vehicle_ready()
            preflight = self._preflight.evaluate(request, vehicle_state)
            
            if not preflight.passed:
                return self._fail(execution_id, mission_id, sm, "preflight",
                                  preflight.summary)
            
            # 4. Compile mission
            if request.flight_plan is None:
                return self._fail(execution_id, mission_id, sm, "compile",
                                  "No flight plan provided")
            
            compiled = self._compiler.compile(
                flight_plan=request.flight_plan,
                intent=request.intent,
                mission_id=mission_id,
                execution_id=execution_id,
            )
            
            if not compiled.waypoints:
                return self._fail(execution_id, mission_id, sm, "compile",
                                  "Compilation produced no waypoints")
            
            # 5. Upload
            sm.transition(LiveMissionState.UPLOADED, "Mission compiled and uploading")
            upload_ack = driver.upload_mission(compiled)
            
            if upload_ack.status != CommandStatus.ACCEPTED:
                return self._fail(execution_id, mission_id, sm, "upload",
                                  f"Upload failed: {upload_ack.message}")
            
            # 6. Ready
            sm.transition(LiveMissionState.READY, "Mission uploaded")
            
            # 7. Arm
            sm.transition(LiveMissionState.ARMING, "Arming vehicle")
            arm_ack = driver.arm()
            
            if arm_ack.status != CommandStatus.ACCEPTED:
                return self._fail(execution_id, mission_id, sm, "arm",
                                  f"Arm failed: {arm_ack.message}")
            
            # 8. Start
            sm.transition(LiveMissionState.IN_FLIGHT, "Mission started")
            start_ack = driver.start_mission()
            
            if start_ack.status != CommandStatus.ACCEPTED:
                return self._fail(execution_id, mission_id, sm, "start",
                                  f"Start failed: {start_ack.message}")
            
            # 9. Telemetry stream
            ingestor = TelemetryIngestor(execution_id=execution_id)
            monitor = HealthMonitor(policy=request.failsafe_policy)
            failsafe = FailsafeController(
                driver=driver,
                state_machine=sm,
                policy=request.failsafe_policy,
            )
            
            for packet in driver.stream_telemetry():
                ingestor.ingest(packet)
                
                # Health check
                warnings = monitor.evaluate(packet, compiled)
                
                # Failsafe action
                for warning in warnings:
                    action = failsafe.handle(warning)
                    if action and sm.is_terminal:
                        break
                
                if sm.is_terminal:
                    break
            
            # 10. Mission complete
            if not sm.is_terminal:
                sm.transition(LiveMissionState.RETURNING, "Mission waypoints complete")
                sm.transition(LiveMissionState.COMPLETED, "Mission completed successfully")
            
            final_state = driver.get_vehicle_state()
            
            return DispatchResult(
                execution_id=execution_id,
                mission_id=mission_id,
                success=sm.state == LiveMissionState.COMPLETED,
                state=sm.state,
                compiled_mission=compiled,
                vehicle_state=final_state,
            )
        
        finally:
            driver.disconnect()
    
    def get_mission_state(self, execution_id: str) -> Optional[LiveMissionState]:
        """Get current state of an active mission."""
        sm = self._active_missions.get(execution_id)
        return sm.state if sm else None
    
    def _get_driver(self, driver_type: str) -> Optional[DroneDriverBase]:
        """Instantiate a driver by type."""
        cls = _DRIVER_REGISTRY.get(driver_type)
        if cls is None:
            return None
        return cls()
    
    def _fail(
        self,
        execution_id: str,
        mission_id: str,
        sm: MissionStateMachine,
        stage: str,
        reason: str,
    ) -> DispatchResult:
        """Record a failure and return a failed DispatchResult."""
        logger.error(f"[Dispatcher] FAILED at {stage}: {reason}")
        
        if sm.is_operational:
            sm.transition(LiveMissionState.FAILED, f"Failed at {stage}: {reason}")
        
        return DispatchResult(
            execution_id=execution_id,
            mission_id=mission_id,
            success=False,
            state=sm.state,
            failure_reason=reason,
            failure_stage=stage,
        )
