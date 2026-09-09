"""MESIA Capability Lifecycle — R6 §10.5.

Nine-state qualification lifecycle for named capabilities.

A capability is per-target, per-domain, per-use — not a global cluster
certificate (principle P-09).  Transition to QUALIFIED requires passing
all eight gates: repeatability, sensitivity, specificity, observability,
transfer, closure, incremental value, and governance.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, FrozenSet


class CapabilityState(str, Enum):
    """Qualification lifecycle states — R6 §10.5."""

    DISCOVERY = "DISCOVERY"
    """Collect and learn radio/instrument representation; geometry
    optional; no agricultural state use."""

    EXPERIMENTAL = "EXPERIMENTAL"
    """Mutable topology and research models; training/benchmark only."""

    CONFIGURED = "CONFIGURED"
    """Declared identity, topology, bands and planned geometry;
    experimental kernels."""

    COMMISSIONED = "COMMISSIONED"
    """As-built pose, verified links, baseline, reference/sentinel and
    frozen configuration version."""

    CALIBRATING = "CALIBRATING"
    """Site adaptation, growing local history, drift and transfer
    limits."""

    ACTIVE = "ACTIVE"
    """Normal evidence generation inside validated capabilities and
    current health."""

    QUALIFIED = "QUALIFIED"
    """Specific capability/use/domain passed all required gates; not a
    global cluster certificate."""

    DEGRADED = "DEGRADED"
    """Calibration, health, observability, closure, transfer, governance
    or security failed.  Evidence may still be collected but authority
    is reduced."""

    REVOKED = "REVOKED"
    """Authority fully withdrawn.  Requires re-commissioning and
    re-qualification to restore."""


# ── Valid transitions ────────────────────────────────────────────────

VALID_CAPABILITY_TRANSITIONS: Dict[CapabilityState, FrozenSet[CapabilityState]] = {
    CapabilityState.DISCOVERY: frozenset({
        CapabilityState.EXPERIMENTAL,
    }),
    CapabilityState.EXPERIMENTAL: frozenset({
        CapabilityState.CONFIGURED,
        CapabilityState.DISCOVERY,    # fallback if experiment invalidates
    }),
    CapabilityState.CONFIGURED: frozenset({
        CapabilityState.COMMISSIONED,
        CapabilityState.EXPERIMENTAL,  # fallback on failed commissioning
    }),
    CapabilityState.COMMISSIONED: frozenset({
        CapabilityState.CALIBRATING,
        CapabilityState.DEGRADED,
    }),
    CapabilityState.CALIBRATING: frozenset({
        CapabilityState.ACTIVE,
        CapabilityState.DEGRADED,
    }),
    CapabilityState.ACTIVE: frozenset({
        CapabilityState.QUALIFIED,
        CapabilityState.DEGRADED,
        CapabilityState.CALIBRATING,  # re-calibration needed
    }),
    CapabilityState.QUALIFIED: frozenset({
        CapabilityState.ACTIVE,       # renewal / continued operation
        CapabilityState.DEGRADED,
        CapabilityState.REVOKED,
    }),
    CapabilityState.DEGRADED: frozenset({
        CapabilityState.CALIBRATING,  # repair path
        CapabilityState.COMMISSIONED, # re-commissioning
        CapabilityState.REVOKED,
    }),
    CapabilityState.REVOKED: frozenset({
        CapabilityState.COMMISSIONED, # full re-commissioning required
    }),
}


class InvalidCapabilityTransition(Exception):
    """Raised when an illegal capability state transition is attempted."""

    def __init__(
        self,
        from_state: CapabilityState,
        to_state: CapabilityState,
    ) -> None:
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"Invalid capability transition: "
            f"{from_state.value} → {to_state.value}"
        )


class CapabilityLifecycle:
    """Enforces the qualification lifecycle state machine.

    Usage::

        lc = CapabilityLifecycle()
        lc.transition(CapabilityState.EXPERIMENTAL)
        lc.transition(CapabilityState.CONFIGURED)
        ...
        lc.transition(CapabilityState.QUALIFIED)
    """

    def __init__(
        self,
        initial_state: CapabilityState = CapabilityState.DISCOVERY,
    ) -> None:
        self._state = initial_state
        self._history: list[CapabilityState] = [initial_state]

    @property
    def state(self) -> CapabilityState:
        return self._state

    @property
    def history(self) -> list[CapabilityState]:
        return list(self._history)

    @property
    def is_operational(self) -> bool:
        """Whether the capability may generate evidence with authority."""
        return self._state in {
            CapabilityState.ACTIVE,
            CapabilityState.QUALIFIED,
        }

    @property
    def is_research_only(self) -> bool:
        """Whether the capability is in a research/pre-qualification state."""
        return self._state in {
            CapabilityState.DISCOVERY,
            CapabilityState.EXPERIMENTAL,
            CapabilityState.CONFIGURED,
        }

    def can_transition(self, target: CapabilityState) -> bool:
        return target in VALID_CAPABILITY_TRANSITIONS.get(
            self._state, frozenset()
        )

    def transition(self, target: CapabilityState) -> None:
        """Perform a state transition.

        Raises:
            InvalidCapabilityTransition: If the transition is not valid.
        """
        if not self.can_transition(target):
            raise InvalidCapabilityTransition(self._state, target)
        self._state = target
        self._history.append(target)

    def degrade(self) -> None:
        """Convenience: transition to DEGRADED from any state that allows it."""
        self.transition(CapabilityState.DEGRADED)

    def revoke(self) -> None:
        """Convenience: transition to REVOKED (only from QUALIFIED or DEGRADED)."""
        self.transition(CapabilityState.REVOKED)

    def __repr__(self) -> str:
        return f"CapabilityLifecycle(state={self._state.value})"
