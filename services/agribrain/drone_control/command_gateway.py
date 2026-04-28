"""
Drone Control — Command Gateway.

Public API facade for UI/orchestrator use. This is what the app
and orchestrator should call — never the dispatcher directly.

Exposes the full control surface:
  - dispatch_mission
  - pause / resume / abort / rtl
  - get_live_state
  - get_execution_result
  - list_executions / list_active
"""

from __future__ import annotations
from typing import Dict, List, Optional
import logging
import uuid

from .schemas import (
    DispatchRequest,
    DispatchResult,
    LiveMissionState,
)
from .dispatcher import Dispatcher

logger = logging.getLogger(__name__)


class CommandGateway:
    """Public API for drone control operations.
    
    Provides clean, named methods that the UI and orchestrator call.
    Internally delegates to the Dispatcher.
    """
    
    def __init__(self):
        self._dispatcher = Dispatcher()
        self._executions: Dict[str, DispatchResult] = {}
    
    # ====================================================================
    # Dispatch
    # ====================================================================
    
    def dispatch_mission(
        self,
        mission_id: str,
        vehicle_id: str,
        request: DispatchRequest,
    ) -> DispatchResult:
        """Dispatch a planned mission to a vehicle.
        
        Args:
            mission_id: Mission identifier
            vehicle_id: Target vehicle identifier
            request: Full dispatch request
            
        Returns:
            DispatchResult with execution status
        """
        request.mission_id = mission_id
        request.vehicle_id = vehicle_id
        if not request.execution_id:
            request.execution_id = f"exec_{uuid.uuid4().hex[:8]}"
        
        result = self._dispatcher.dispatch(request)
        self._executions[result.execution_id] = result
        
        return result
    
    # ====================================================================
    # Live control
    # ====================================================================
    
    def pause(self, execution_id: str, reason: str = "Operator requested") -> bool:
        """Pause an active mission.
        
        Args:
            execution_id: The execution to pause
            reason: Human-readable reason
            
        Returns:
            True if successfully paused
        """
        success = self._dispatcher.pause(execution_id, reason)
        if success:
            logger.info(f"[Gateway] Paused {execution_id}: {reason}")
        return success
    
    def resume(self, execution_id: str) -> bool:
        """Resume a paused mission.
        
        Args:
            execution_id: The execution to resume
            
        Returns:
            True if successfully resumed
        """
        success = self._dispatcher.resume(execution_id)
        if success:
            logger.info(f"[Gateway] Resumed {execution_id}")
        return success
    
    def abort(self, execution_id: str, reason: str = "Operator abort") -> bool:
        """Abort an active mission. Vehicle will stop in place.
        
        Args:
            execution_id: The execution to abort
            reason: Human-readable reason
            
        Returns:
            True if successfully aborted
        """
        success = self._dispatcher.abort(execution_id, reason)
        if success:
            logger.warning(f"[Gateway] Aborted {execution_id}: {reason}")
        return success
    
    def rtl(self, execution_id: str, reason: str = "Operator RTL") -> bool:
        """Return-to-launch an active mission. Vehicle returns to home.
        
        Args:
            execution_id: The execution to RTL
            reason: Human-readable reason
            
        Returns:
            True if RTL was accepted
        """
        success = self._dispatcher.rtl(execution_id, reason)
        if success:
            logger.warning(f"[Gateway] RTL {execution_id}: {reason}")
        return success
    
    # ====================================================================
    # Queries
    # ====================================================================
    
    def get_live_state(self, execution_id: str) -> Optional[LiveMissionState]:
        """Get current state of a mission execution."""
        return self._dispatcher.get_mission_state(execution_id)
    
    def get_execution_result(self, execution_id: str) -> Optional[DispatchResult]:
        """Get the result of a completed execution."""
        return self._executions.get(execution_id)
    
    def list_executions(self) -> Dict[str, DispatchResult]:
        """List all execution results."""
        return dict(self._executions)
    
    def list_active(self) -> List[str]:
        """List execution_ids of currently active (non-terminal) missions."""
        return self._dispatcher.list_active_sessions()
