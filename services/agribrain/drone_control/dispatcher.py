"""
Drone Control — Dispatcher.

The main orchestration entrypoint. Maintains persistent live mission
sessions that support pause/resume/abort/RTL after dispatch.

Flow:
  1. Select driver
  2. Run preflight
  3. Compile mission
  4. Connect → upload → arm → start
  5. Stream telemetry (in session)
  6. Track state via state machine
  7. Expose pause/resume/abort/RTL on active session
  8. Return DispatchResult on completion or failure
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Type
import logging
import threading
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


# ============================================================================
# Live Mission Session
# ============================================================================

@dataclass
class LiveMissionSession:
    """Persistent session for a dispatched mission.
    
    Holds the driver handle, state machine, telemetry ingestor,
    health monitor, and failsafe controller. Lives until the
    mission reaches a terminal state and the driver is disconnected.
    """
    execution_id: str
    mission_id: str
    driver: DroneDriverBase
    state_machine: MissionStateMachine
    ingestor: TelemetryIngestor
    monitor: HealthMonitor
    failsafe: FailsafeController
    compiled_mission: Optional[object] = None     # CompiledMission
    request: Optional[DispatchRequest] = None
    dispatch_result: Optional[DispatchResult] = None  # Set by async dispatch
    
    @property
    def state(self) -> LiveMissionState:
        return self.state_machine.state
    
    @property
    def is_terminal(self) -> bool:
        return self.state_machine.is_terminal


class Dispatcher:
    """Main mission dispatch orchestrator.
    
    Maintains persistent live sessions — dispatch returns after the
    telemetry loop completes but the session is retained for audit.
    Exposes pause/resume/abort/RTL on active sessions.
    """
    
    def __init__(self):
        self._compiler = MissionCompiler()
        self._preflight = PreflightGate()
        self._sessions: Dict[str, LiveMissionSession] = {}
    
    def dispatch(self, request: DispatchRequest) -> DispatchResult:
        """Dispatch a mission to a drone.
        
        This is the single entrypoint for all mission types.
        Creates a persistent session that supports live control.
        
        Args:
            request: DispatchRequest with flight plan, vehicle, and safety policy
            
        Returns:
            DispatchResult with success/failure status and execution details
        """
        execution_id = request.execution_id or f"exec_{uuid.uuid4().hex[:8]}"
        mission_id = request.mission_id
        
        sm = MissionStateMachine(execution_id=execution_id)
        
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
                driver_type=request.driver_type,
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
            
            # 9. Create persistent session
            ingestor = TelemetryIngestor(execution_id=execution_id)
            monitor = HealthMonitor(policy=request.failsafe_policy)
            failsafe = FailsafeController(
                driver=driver,
                state_machine=sm,
                policy=request.failsafe_policy,
            )
            
            session = LiveMissionSession(
                execution_id=execution_id,
                mission_id=mission_id,
                driver=driver,
                state_machine=sm,
                ingestor=ingestor,
                monitor=monitor,
                failsafe=failsafe,
                compiled_mission=compiled,
                request=request,
            )
            self._sessions[execution_id] = session
            
            # 10. Telemetry stream
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
            
            # 11. Mission complete
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
        
        except Exception as e:
            logger.error(f"[Dispatcher] Exception during dispatch: {e}")
            if sm.is_operational:
                sm.transition(LiveMissionState.FAILED, f"Exception: {e}")
            return DispatchResult(
                execution_id=execution_id,
                mission_id=mission_id,
                success=False,
                state=sm.state,
                failure_reason=str(e),
                failure_stage="runtime",
            )
        finally:
            # Disconnect only if terminal — session still holds reference
            if sm.is_terminal:
                driver.disconnect()
    
    # ========================================================================
    # Async dispatch (for live control testing)
    # ========================================================================
    
    def dispatch_async(
        self,
        request: DispatchRequest,
    ) -> str:
        """Dispatch a mission in a background thread.
        
        Returns execution_id immediately. The mission runs in a daemon
        thread — use pause/resume/abort/rtl/get_mission_state to interact.
        
        The DispatchResult is stored on the session when complete.
        """
        execution_id = request.execution_id or f"exec_{uuid.uuid4().hex[:8]}"
        request.execution_id = execution_id
        
        t = threading.Thread(
            target=self._dispatch_background,
            args=(request,),
            daemon=True,
            name=f"dispatch_{execution_id}",
        )
        t.start()
        
        return execution_id
    
    def dispatch_async_with_driver(
        self,
        request: DispatchRequest,
        driver: DroneDriverBase,
    ) -> str:
        """Dispatch with a pre-built driver (for testing with stepped MockDriver).
        
        Like dispatch_async but injects a driver instead of creating one
        from the registry. Essential for stepped-mode live control tests.
        """
        execution_id = request.execution_id or f"exec_{uuid.uuid4().hex[:8]}"
        request.execution_id = execution_id
        
        t = threading.Thread(
            target=self._dispatch_with_driver_background,
            args=(request, driver),
            daemon=True,
            name=f"dispatch_{execution_id}",
        )
        t.start()
        
        return execution_id
    
    def _dispatch_background(self, request: DispatchRequest):
        """Background dispatch — stores result on session."""
        result = self.dispatch(request)
        session = self._sessions.get(result.execution_id)
        if session:
            session.dispatch_result = result
    
    def _dispatch_with_driver_background(
        self,
        request: DispatchRequest,
        driver: DroneDriverBase,
    ):
        """Background dispatch with injected driver."""
        # Save original _get_driver and monkey-patch for this call
        execution_id = request.execution_id or f"exec_{uuid.uuid4().hex[:8]}"
        request.execution_id = execution_id
        
        mission_id = request.mission_id
        sm = MissionStateMachine(execution_id=execution_id)
        
        # Connect
        connect_ack = driver.connect(request.vehicle_id)
        if connect_ack.status != CommandStatus.ACCEPTED:
            return
        
        try:
            # Preflight
            vehicle_state = driver.validate_vehicle_ready()
            preflight = self._preflight.evaluate(request, vehicle_state)
            if not preflight.passed:
                return
            
            # Compile
            if request.flight_plan is None:
                return
            
            compiled = self._compiler.compile(
                flight_plan=request.flight_plan,
                intent=request.intent,
                mission_id=mission_id,
                execution_id=execution_id,
                driver_type=request.driver_type,
            )
            
            if not compiled.waypoints:
                return
            
            # Upload → arm → start
            sm.transition(LiveMissionState.UPLOADED, "Compiled")
            driver.upload_mission(compiled)
            sm.transition(LiveMissionState.READY, "Uploaded")
            sm.transition(LiveMissionState.ARMING, "Arming")
            driver.arm()
            sm.transition(LiveMissionState.IN_FLIGHT, "Started")
            driver.start_mission()
            
            # Create session
            ingestor = TelemetryIngestor(execution_id=execution_id)
            monitor = HealthMonitor(policy=request.failsafe_policy)
            failsafe = FailsafeController(
                driver=driver,
                state_machine=sm,
                policy=request.failsafe_policy,
            )
            
            session = LiveMissionSession(
                execution_id=execution_id,
                mission_id=mission_id,
                driver=driver,
                state_machine=sm,
                ingestor=ingestor,
                monitor=monitor,
                failsafe=failsafe,
                compiled_mission=compiled,
                request=request,
            )
            self._sessions[execution_id] = session
            
            # Telemetry loop
            for packet in driver.stream_telemetry():
                ingestor.ingest(packet)
                warnings = monitor.evaluate(packet, compiled)
                for warning in warnings:
                    action = failsafe.handle(warning)
                    if action and sm.is_terminal:
                        break
                if sm.is_terminal:
                    break
            
            # Complete
            if not sm.is_terminal:
                sm.transition(LiveMissionState.RETURNING, "Waypoints complete")
                sm.transition(LiveMissionState.COMPLETED, "Completed")
        
        except Exception as e:
            if sm.is_operational:
                sm.transition(LiveMissionState.FAILED, str(e))
        finally:
            if sm.is_terminal:
                driver.disconnect()
    
    # ========================================================================
    # Live control methods
    # ========================================================================
    
    def pause(self, execution_id: str, reason: str = "Operator requested") -> bool:
        """Pause an active mission."""
        session = self._sessions.get(execution_id)
        if session is None or session.is_terminal:
            return False
        if not session.state_machine.can_transition_to(LiveMissionState.PAUSED):
            return False
        
        ack = session.driver.pause_mission()
        if ack.status == CommandStatus.ACCEPTED:
            session.state_machine.transition(LiveMissionState.PAUSED, reason)
            logger.info(f"[Dispatcher] Paused {execution_id}: {reason}")
            return True
        return False
    
    def resume(self, execution_id: str) -> bool:
        """Resume a paused mission."""
        session = self._sessions.get(execution_id)
        if session is None or session.is_terminal:
            return False
        if not session.state_machine.can_transition_to(LiveMissionState.IN_FLIGHT):
            return False
        
        ack = session.driver.resume_mission()
        if ack.status == CommandStatus.ACCEPTED:
            session.state_machine.transition(LiveMissionState.IN_FLIGHT, "Operator resumed")
            logger.info(f"[Dispatcher] Resumed {execution_id}")
            return True
        return False
    
    def abort(self, execution_id: str, reason: str = "Operator abort") -> bool:
        """Abort an active mission."""
        session = self._sessions.get(execution_id)
        if session is None or session.is_terminal:
            return False
        
        ack = session.driver.abort_mission()
        if ack.status == CommandStatus.ACCEPTED:
            if session.state_machine.can_transition_to(LiveMissionState.ABORTED):
                session.state_machine.transition(LiveMissionState.ABORTED, reason)
            elif session.state_machine.can_transition_to(LiveMissionState.FAILED):
                session.state_machine.transition(LiveMissionState.FAILED, reason)
            session.driver.disconnect()
            logger.warning(f"[Dispatcher] Aborted {execution_id}: {reason}")
            return True
        return False
    
    def rtl(self, execution_id: str, reason: str = "Operator RTL") -> bool:
        """Return-to-launch an active mission."""
        session = self._sessions.get(execution_id)
        if session is None or session.is_terminal:
            return False
        
        ack = session.driver.rtl()
        if ack.status == CommandStatus.ACCEPTED:
            if session.state_machine.can_transition_to(LiveMissionState.RETURNING):
                session.state_machine.transition(LiveMissionState.RETURNING, reason)
            logger.warning(f"[Dispatcher] RTL {execution_id}: {reason}")
            return True
        return False
    
    # ========================================================================
    # Session queries
    # ========================================================================
    
    def get_mission_state(self, execution_id: str) -> Optional[LiveMissionState]:
        """Get current state of an active or completed mission."""
        session = self._sessions.get(execution_id)
        return session.state if session else None
    
    def get_session(self, execution_id: str) -> Optional[LiveMissionSession]:
        """Get the full session for an execution."""
        return self._sessions.get(execution_id)
    
    def list_active_sessions(self) -> List[str]:
        """List execution_ids of non-terminal sessions."""
        return [eid for eid, s in self._sessions.items() if not s.is_terminal]
    
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
