"""
Layer 1 Source Registry.

Manages adapter registration, source envelope validation,
and quarantine for sources that cannot provide required metadata.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from .schemas import (
    EvidenceItem,
    Layer1InputBundle,
    QuarantinedEvidence,
    SOURCE_FAMILIES,
    SourceEnvelope,
)


# ============================================================================
# Adapter protocol
# ============================================================================

@runtime_checkable
class Layer1SourceAdapter(Protocol):
    """Protocol that every source adapter must implement."""

    source_family: str

    def can_read(self, package: Any) -> bool:
        """Return True if this adapter can process the given package."""
        ...

    def extract_evidence(
        self, package: Any, context: Layer1InputBundle
    ) -> List[EvidenceItem]:
        """Extract evidence items from a Layer 0 package."""
        ...

    def source_health(self, package: Any) -> SourceEnvelope:
        """Build a SourceEnvelope describing this source's health."""
        ...


# ============================================================================
# Source registry
# ============================================================================

class SourceRegistry:
    """Central registry of Layer 1 source adapters.

    Validates source envelopes and quarantines sources with
    missing or invalid metadata.
    """

    def __init__(self) -> None:
        self._adapters: Dict[str, Layer1SourceAdapter] = {}

    def register(self, adapter: Layer1SourceAdapter) -> None:
        """Register an adapter for a source family."""
        family = adapter.source_family
        if family not in SOURCE_FAMILIES:
            raise ValueError(
                f"Unknown source family: {family}. "
                f"Must be one of {SOURCE_FAMILIES}"
            )
        self._adapters[family] = adapter

    def get_adapter(self, family: str) -> Optional[Layer1SourceAdapter]:
        """Get the registered adapter for a source family."""
        return self._adapters.get(family)

    @property
    def registered_families(self) -> List[str]:
        """List of registered source families."""
        return list(self._adapters.keys())

    def validate_envelope(
        self, envelope: SourceEnvelope
    ) -> List[str]:
        """Validate a SourceEnvelope. Returns list of violation messages."""
        violations: List[str] = []

        if not envelope.source_id:
            violations.append("source_id is empty")
        if envelope.source_family not in SOURCE_FAMILIES:
            violations.append(
                f"source_family '{envelope.source_family}' not in {SOURCE_FAMILIES}"
            )
        if not envelope.package_id:
            violations.append("package_id is empty (required for provenance)")
        if not envelope.package_version:
            violations.append("package_version is empty")
        if not (0.0 <= envelope.trust_score <= 1.0):
            violations.append(
                f"trust_score {envelope.trust_score} out of [0, 1] range"
            )

        return violations

    def quarantine_envelope(
        self, envelope: SourceEnvelope, violations: List[str]
    ) -> QuarantinedEvidence:
        """Create a quarantine record for a bad source envelope."""
        return QuarantinedEvidence(
            evidence_id=f"quarantine_envelope_{envelope.source_id}",
            reason_codes=violations,
            original_source_family=envelope.source_family,
            variable=None,
            severity="error" if len(violations) > 2 else "warning",
            can_override=False,
        )
