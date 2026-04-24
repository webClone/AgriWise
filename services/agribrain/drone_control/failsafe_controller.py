"""
Drone Control — Failsafe Controller.

Policy-driven action layer for runtime safety. Every failsafe action
is deterministic, traceable, and logged in the execution audit.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
import logging

from .schemas import (
    FailsafeAction,
    FailsafePolicy,
    HealthSeverity,
    HealthWarning,
    LiveMissionState,
)
from .driver_base import DroneDriverBase
from .mission_state_machine import MissionStateMachine

logger = logging.getLogger(__name__)


@dataclass
class FailsafeRecord:
    """Record of a failsafe action taken."""
    warning: HealthWarning
    action_taken: FailsafeAction
    result: str = ""                       # "executed", "skipped", "failed"


class FailsafeController:
    """Deterministic, policy-driven failsafe action layer.
    
    Takes HealthWarning inputs from the monitor and executes the
    appropriate action through the driver. All actions are traceable
    in the execution log.
    """
    
    def __init__(
        self,
        driver: DroneDriverBase,
        state_machine: MissionStateMachine,
        policy: Optional[FailsafePolicy] = None,
    ):
        self._driver = driver
        self._sm = state_machine
        self._policy = policy or FailsafePolicy()
        self._records: List[FailsafeRecord] = []
        self._paused = False
    
    @property
    def records(self) -> List[FailsafeRecord]:
        return list(self._records)
    
    @property
    def actions_taken(self) -> List[str]:
        """List of action names taken."""
        return [r.action_taken.value for r in self._records]
    
    def handle(self, warning: HealthWarning) -> Optional[FailsafeAction]:
        """Handle a health warning by executing the recommended action.
        
        Returns the action taken, or None if no action needed.
        """
        if self._sm.is_terminal:
            return None
        
        action = warning.recommended_action
        
        # Execute the action
        record = FailsafeRecord(warning=warning, action_taken=action)
        
        try:
            if action == FailsafeAction.CONTINUE:
                record.result = "executed"
            
            elif action == FailsafeAction.PAUSE:
                if (self._sm.state == LiveMissionState.IN_FLIGHT and
                        self._sm.can_transition_to(LiveMissionState.PAUSED)):
                    self._driver.pause_mission()
                    self._sm.transition(LiveMissionState.PAUSED, f"Failsafe: {warning.message}")
                    self._paused = True
                    record.result = "executed"
                    logger.info(f"[Failsafe] PAUSED: {warning.message}")
                else:
                    record.result = "skipped"
            
            elif action == FailsafeAction.RESUME:
                if (self._sm.state == LiveMissionState.PAUSED and
                        self._sm.can_transition_to(LiveMissionState.IN_FLIGHT)):
                    self._driver.resume_mission()
                    self._sm.transition(LiveMissionState.IN_FLIGHT, "Failsafe: condition cleared")
                    self._paused = False
                    record.result = "executed"
                    logger.info("[Failsafe] RESUMED")
                else:
                    record.result = "skipped"
            
            elif action == FailsafeAction.SKIP_SEGMENT:
                # Cannot skip segments without mission modification — log and continue
                record.result = "executed"
                logger.warning(f"[Failsafe] SKIP_SEGMENT requested: {warning.message}")
            
            elif action == FailsafeAction.RTL:
                if self._sm.can_transition_to(LiveMissionState.RETURNING):
                    self._driver.rtl()
                    self._sm.transition(LiveMissionState.RETURNING, f"Failsafe RTL: {warning.message}")
                    record.result = "executed"
                    logger.warning(f"[Failsafe] RTL: {warning.message}")
                elif self._sm.can_transition_to(LiveMissionState.ABORTED):
                    self._sm.transition(LiveMissionState.ABORTED, f"Failsafe RTL (from {self._sm.state.value}): {warning.message}")
                    record.result = "executed"
                else:
                    record.result = "skipped"
            
            elif action == FailsafeAction.LAND_NOW:
                self._driver.land_now()
                if self._sm.can_transition_to(LiveMissionState.RETURNING):
                    self._sm.transition(LiveMissionState.RETURNING, f"Failsafe LAND_NOW: {warning.message}")
                elif self._sm.can_transition_to(LiveMissionState.ABORTED):
                    self._sm.transition(LiveMissionState.ABORTED, f"Failsafe LAND_NOW: {warning.message}")
                record.result = "executed"
                logger.warning(f"[Failsafe] LAND_NOW: {warning.message}")
            
            elif action == FailsafeAction.ABORT:
                self._driver.abort_mission()
                if self._sm.can_transition_to(LiveMissionState.ABORTED):
                    self._sm.transition(LiveMissionState.ABORTED, f"Failsafe ABORT: {warning.message}")
                elif self._sm.can_transition_to(LiveMissionState.FAILED):
                    self._sm.transition(LiveMissionState.FAILED, f"Failsafe ABORT: {warning.message}")
                record.result = "executed"
                logger.error(f"[Failsafe] ABORT: {warning.message}")
        
        except Exception as e:
            record.result = f"failed: {e}"
            logger.error(f"[Failsafe] Action {action.value} failed: {e}")
        
        self._records.append(record)
        return action
