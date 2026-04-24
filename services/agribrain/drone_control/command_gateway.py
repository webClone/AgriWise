"""
Drone Control — Command Gateway.

Thin API facade for UI/orchestrator use. This is what the app
and orchestrator should call — never the dispatcher directly.
"""

from __future__ import annotations
from typing import Dict, Optional
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
    
    def get_live_state(self, execution_id: str) -> Optional[LiveMissionState]:
        """Get current state of a mission execution."""
        return self._dispatcher.get_mission_state(execution_id)
    
    def get_execution_result(self, execution_id: str) -> Optional[DispatchResult]:
        """Get the result of a completed execution."""
        return self._executions.get(execution_id)
    
    def list_executions(self) -> Dict[str, DispatchResult]:
        """List all execution results."""
        return dict(self._executions)
