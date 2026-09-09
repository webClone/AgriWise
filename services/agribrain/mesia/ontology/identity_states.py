"""MESIA Identity State Machine — R6 §5.1.

Eleven-state open-set identification hierarchy.  UNKNOWN and AMBIGUOUS
remain valid at every observable level.

State semantics:
  NO_COVERAGE    — No receiver/antenna path can observe the required band.
  UNAVAILABLE    — Expected interface is offline, permission-blocked, etc.
  NO_SIGNAL      — Coverage exists; calibrated scan found no event.
  DETECTED       — A calibrated time-frequency/pulse/chirp event exists.
  WAVEFORM_CLASSIFIED — Evidence supports a morphology (OFDM, CSS, etc.).
  RAT_CANDIDATE  — Band/BW/numerology/signatures support ≥1 radio family.
  PROTOCOL_CONFIRMED — Direct correlator/decoder/CRC/reference evidence.
  CONTROLLED_SOURCE — Known Tx, action, geometry, time, config, policy.
  AMBIGUOUS      — ≥2 hypotheses remain materially plausible.
  UNKNOWN        — Observable event doesn't match supported profiles.
  UNTRUSTED      — Spoofing/contamination/corruption/provenance failure.

Hard integrity rules:
  - NO_COVERAGE must never transition to NO_SIGNAL.
  - PROTOCOL_CONFIRMED requires a ProtocolConfirmationReceipt.
  - UNKNOWN retains native data for future registry versions.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, FrozenSet, Optional


class IdentityState(str, Enum):
    """Open-set signal identity states — R6 §5.1."""

    NO_COVERAGE = "NO_COVERAGE"
    UNAVAILABLE = "UNAVAILABLE"
    NO_SIGNAL = "NO_SIGNAL"
    DETECTED = "DETECTED"
    WAVEFORM_CLASSIFIED = "WAVEFORM_CLASSIFIED"
    RAT_CANDIDATE = "RAT_CANDIDATE"
    PROTOCOL_CONFIRMED = "PROTOCOL_CONFIRMED"
    CONTROLLED_SOURCE = "CONTROLLED_SOURCE"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"
    UNTRUSTED = "UNTRUSTED"


# ── Evidence ladder (normal progression) ────────────────────────────────
#
#  NO_COVERAGE ──────────────────────────────────────────────────(terminal)
#  UNAVAILABLE ──────────────────────────────────────────────────(terminal)
#  NO_SIGNAL ────────────────────────────────────────────────────(terminal)
#
#  DETECTED ──→ WAVEFORM_CLASSIFIED ──→ RAT_CANDIDATE ──→ PROTOCOL_CONFIRMED
#       │              │                      │                    │
#       └──→ AMBIGUOUS ←──────────────────────┘                    │
#       └──→ UNKNOWN                                               │
#       └──→ UNTRUSTED ←───── (any state) ─────────────────────────┘
#                                                                  │
#                                          PROTOCOL_CONFIRMED ──→ CONTROLLED_SOURCE
#
# AMBIGUOUS may resolve to any later state.
# Any state may transition to UNTRUSTED if provenance fails.

VALID_IDENTITY_TRANSITIONS: Dict[IdentityState, FrozenSet[IdentityState]] = {
    # Terminal observation states — no further transitions
    IdentityState.NO_COVERAGE: frozenset(),
    IdentityState.UNAVAILABLE: frozenset(),
    IdentityState.NO_SIGNAL: frozenset(),

    # Detection — branches to classification, ambiguity, or unknown
    IdentityState.DETECTED: frozenset({
        IdentityState.WAVEFORM_CLASSIFIED,
        IdentityState.AMBIGUOUS,
        IdentityState.UNKNOWN,
        IdentityState.UNTRUSTED,
    }),

    # Waveform classification — narrows to RAT candidate or stays ambiguous
    IdentityState.WAVEFORM_CLASSIFIED: frozenset({
        IdentityState.RAT_CANDIDATE,
        IdentityState.AMBIGUOUS,
        IdentityState.UNKNOWN,
        IdentityState.UNTRUSTED,
    }),

    # RAT candidate — may confirm protocol or remain ambiguous
    IdentityState.RAT_CANDIDATE: frozenset({
        IdentityState.PROTOCOL_CONFIRMED,
        IdentityState.AMBIGUOUS,
        IdentityState.UNTRUSTED,
    }),

    # Protocol confirmed — may escalate to controlled source
    IdentityState.PROTOCOL_CONFIRMED: frozenset({
        IdentityState.CONTROLLED_SOURCE,
        IdentityState.UNTRUSTED,
    }),

    # Controlled source — terminal success; only untrusted if provenance fails
    IdentityState.CONTROLLED_SOURCE: frozenset({
        IdentityState.UNTRUSTED,
    }),

    # Ambiguous — may resolve forward to any classification/confirmation state
    IdentityState.AMBIGUOUS: frozenset({
        IdentityState.WAVEFORM_CLASSIFIED,
        IdentityState.RAT_CANDIDATE,
        IdentityState.PROTOCOL_CONFIRMED,
        IdentityState.UNKNOWN,
        IdentityState.UNTRUSTED,
    }),

    # Unknown — may reclassify with future registry versions
    IdentityState.UNKNOWN: frozenset({
        IdentityState.WAVEFORM_CLASSIFIED,
        IdentityState.AMBIGUOUS,
        IdentityState.UNTRUSTED,
    }),

    # Untrusted — quarantine; no transitions out (requires new observation)
    IdentityState.UNTRUSTED: frozenset(),
}

# Hard integrity: NO_COVERAGE → NO_SIGNAL is explicitly impossible.
assert IdentityState.NO_SIGNAL not in VALID_IDENTITY_TRANSITIONS[IdentityState.NO_COVERAGE]


class InvalidIdentityTransition(Exception):
    """Raised when an illegal identity state transition is attempted."""

    def __init__(self, from_state: IdentityState, to_state: IdentityState) -> None:
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"Invalid identity transition: {from_state.value} → {to_state.value}"
        )


class IdentityStateMachine:
    """Enforces the open-set identification state machine.

    Usage::

        sm = IdentityStateMachine(IdentityState.DETECTED)
        sm.transition(IdentityState.WAVEFORM_CLASSIFIED)
        sm.transition(IdentityState.RAT_CANDIDATE)
        sm.transition(IdentityState.PROTOCOL_CONFIRMED, receipt=receipt)
    """

    def __init__(self, initial_state: IdentityState) -> None:
        self._state = initial_state
        self._history: list[IdentityState] = [initial_state]

    @property
    def state(self) -> IdentityState:
        return self._state

    @property
    def history(self) -> list[IdentityState]:
        return list(self._history)

    def can_transition(self, target: IdentityState) -> bool:
        """Check whether a transition is legal without performing it."""
        return target in VALID_IDENTITY_TRANSITIONS.get(self._state, frozenset())

    def transition(
        self,
        target: IdentityState,
        *,
        receipt: Optional[object] = None,
    ) -> None:
        """Perform a state transition.

        Args:
            target: The target identity state.
            receipt: Required when transitioning to PROTOCOL_CONFIRMED.
                     Must be a ProtocolConfirmationReceipt (checked by name
                     to avoid circular imports at the contract level).

        Raises:
            InvalidIdentityTransition: If the transition is not valid.
            ValueError: If PROTOCOL_CONFIRMED is requested without a receipt.
        """
        if not self.can_transition(target):
            raise InvalidIdentityTransition(self._state, target)

        # P-02 / P-03: PROTOCOL_CONFIRMED requires direct evidence
        if target == IdentityState.PROTOCOL_CONFIRMED and receipt is None:
            raise ValueError(
                "Transition to PROTOCOL_CONFIRMED requires a "
                "ProtocolConfirmationReceipt (principle P-03)."
            )

        self._state = target
        self._history.append(target)

    def __repr__(self) -> str:
        return f"IdentityStateMachine(state={self._state.value})"
