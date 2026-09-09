"""MESIA Ontology — enums, state machines, and taxonomies."""

from .identity_states import (
    IdentityState,
    IdentityStateMachine,
    VALID_IDENTITY_TRANSITIONS,
    InvalidIdentityTransition,
)
from .coverage_outcomes import CoverageOutcome
from .confirmation_levels import ConfirmationLevel
from .evidence_roles import EvidenceRole
from .capability_lifecycle import (
    CapabilityState,
    CapabilityLifecycle,
    VALID_CAPABILITY_TRANSITIONS,
    InvalidCapabilityTransition,
)
from .evidence_taxonomy import (
    SourceClass,
    ProcessingLevel,
    AuthorityState,
    PresentationState,
    TruthEnvelope,
)
from .front_ends import FrontEndClass

__all__ = [
    "IdentityState",
    "IdentityStateMachine",
    "VALID_IDENTITY_TRANSITIONS",
    "InvalidIdentityTransition",
    "CoverageOutcome",
    "ConfirmationLevel",
    "EvidenceRole",
    "CapabilityState",
    "CapabilityLifecycle",
    "VALID_CAPABILITY_TRANSITIONS",
    "InvalidCapabilityTransition",
    "FrontEndClass",
    "SourceClass",
    "ProcessingLevel",
    "AuthorityState",
    "PresentationState",
    "TruthEnvelope",
]
