"""MESIA Open-Set Identity & Profile Registry Framework."""

from .deterministic_rules import (
    RuleMatchResult,
    DeterministicProtocolRules,
)
from .correlators import (
    CorrelatorEngine,
)
from .open_set_classifier import (
    OpenSetClassificationResult,
    OpenSetWaveformClassifier,
)
from .evidence_fusion import (
    EvidenceFusionEngine,
)
from .ambiguity_manager import (
    AmbiguityManager,
)
from .profile_registry import (
    SignalIdentityProfile,
    SignalIdentityProfileRegistry,
)

__all__ = [
    # Rules
    "RuleMatchResult",
    "DeterministicProtocolRules",
    # Correlators
    "CorrelatorEngine",
    # Open-Set Classifier
    "OpenSetClassificationResult",
    "OpenSetWaveformClassifier",
    # Evidence Fusion
    "EvidenceFusionEngine",
    # Ambiguity
    "AmbiguityManager",
    # Profile Registry
    "SignalIdentityProfile",
    "SignalIdentityProfileRegistry",
]
