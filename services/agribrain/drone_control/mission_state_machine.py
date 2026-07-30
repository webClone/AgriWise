"""
Drone Control — Mission State Machine.

Formal state transitions for mission execution. All transitions are
explicit and validated — impossible transitions raise InvalidTransitionError.

States:
  planned → uploaded → ready → arming → in_flight
  in_flight → paused → in_flight (resumed)
  in_flight → returning → completed
  any operational → aborted / failed
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Set
import datetime

from .schemas import LiveMissionState


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    def __init__(self, current: LiveMissionState, target: LiveMissionState):
        self.current = current
        self.target = target
        super().__init__(f"Invalid transition: {current.value} → {target.value}")


@dataclass
class StateTransition:
    """Record of a state transition."""
    from_state: LiveMissionState
    to_state: LiveMissionState
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    reason: str = ""


# ============================================================================
# Valid transition table
# ============================================================================

# Each key maps to the set of states it can transition TO
_VALID_TRANSITIONS: dict[LiveMissionState, Set[LiveMissionState]] = {
    LiveMissionState.PLANNED: {
        LiveMissionState.UPLOADED,
        LiveMissionState.ABORTED,
        LiveMissionState.FAILED,
    },
    LiveMissionState.UPLOADED: {
        LiveMissionState.READY,
        LiveMissionState.ABORTED,
        LiveMissionState.FAILED,
    },
    LiveMissionState.READY: {
        LiveMissionState.ARMING,
        LiveMissionState.ABORTED,
        LiveMissionState.FAILED,
    },
    LiveMissionState.ARMING: {
        LiveMissionState.IN_FLIGHT,
        LiveMissionState.ABORTED,
        LiveMissionState.FAILED,
    },
    LiveMissionState.IN_FLIGHT: {
        LiveMissionState.PAUSED,
        LiveMissionState.RETURNING,
        LiveMissionState.ABORTED,
        LiveMissionState.FAILED,
    },
    LiveMissionState.PAUSED: {
        LiveMissionState.IN_FLIGHT,   # resume
        LiveMissionState.RETURNING,
        LiveMissionState.ABORTED,
        LiveMissionState.FAILED,
    },
    LiveMissionState.RETURNING: {
        LiveMissionState.COMPLETED,
        LiveMissionState.ABORTED,
        LiveMissionState.FAILED,
    },
    # Terminal states — no outgoing transitions
    LiveMissionState.COMPLETED: set(),
    LiveMissionState.ABORTED: set(),
    LiveMissionState.FAILED: set(),
}

# Terminal states (cannot transition out of)
_TERMINAL_STATES = {
    LiveMissionState.COMPLETED,
    LiveMissionState.ABORTED,
    LiveMissionState.FAILED,
}


class MissionStateMachine:
    """Formal state machine for mission execution.
    
    All transitions are validated against the transition table.
    State history is tracked for audit.
    """
    
    def __init__(self, execution_id: str = ""):
        self._state = LiveMissionState.PLANNED
        self._execution_id = execution_id
        self._history: List[StateTransition] = []
        self._created_at = datetime.datetime.now()
    
    @property
    def state(self) -> LiveMissionState:
        """Current mission state."""
        return self._state
    
    @property
    def execution_id(self) -> str:
        return self._execution_id
    
    @property
    def history(self) -> List[StateTransition]:
        """Full state transition history."""
        return list(self._history)
    
    @property
    def is_terminal(self) -> bool:
        """Whether the mission is in a terminal state."""
        return self._state in _TERMINAL_STATES
    
    @property
    def is_operational(self) -> bool:
        """Whether the mission is in an operational (non-terminal) state."""
        return not self.is_terminal
    
    def can_transition_to(self, target: LiveMissionState) -> bool:
        """Check if a transition to target is valid from current state."""
        return target in _VALID_TRANSITIONS.get(self._state, set())
    
    def transition(self, target: LiveMissionState, reason: str = "") -> StateTransition:
        """Attempt a state transition.
        
        Args:
            target: The target state
            reason: Human-readable reason for the transition
            
        Returns:
            StateTransition record
            
        Raises:
            InvalidTransitionError: If the transition is not valid
        """
        if not self.can_transition_to(target):
            raise InvalidTransitionError(self._state, target)
        
        transition = StateTransition(
            from_state=self._state,
            to_state=target,
            reason=reason,
        )
        
        self._history.append(transition)
        self._state = target
        
        return transition
    
    def force_state(self, target: LiveMissionState, reason: str = ""):
        """Force a state change without validation.
        
        Only for error recovery. Still records the transition.
        """
        transition = StateTransition(
            from_state=self._state,
            to_state=target,
            reason=f"FORCED: {reason}",
        )
        self._history.append(transition)
        self._state = target
    
    def get_duration_s(self) -> float:
        """Total duration from creation to now or terminal state."""
        if self._history and self.is_terminal:
            end = self._history[-1].timestamp
        else:
            end = datetime.datetime.now()
        return (end - self._created_at).total_seconds()
