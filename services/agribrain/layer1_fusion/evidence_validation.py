"""
Layer 1 Evidence Validation.

Validates evidence items before admission to the ledger.
Quarantines invalid evidence with structured reasons.
"""

from __future__ import annotations

from typing import List

from .schemas import (
    CANONICAL_UNITS,
    EvidenceItem,
    QuarantinedEvidence,
    SOURCE_FAMILIES,
    SPATIAL_SCOPES,
    OBSERVATION_TYPES,
)


def validate_evidence(item: EvidenceItem) -> List[str]:
    """Validate a single evidence item. Returns list of violation messages."""
    violations: List[str] = []

    if not item.evidence_id:
        violations.append("EMPTY_EVIDENCE_ID")
    if not item.plot_id:
        violations.append("EMPTY_PLOT_ID")
    if not item.variable:
        violations.append("EMPTY_VARIABLE")
    if item.source_family not in SOURCE_FAMILIES:
        violations.append(f"INVALID_SOURCE_FAMILY:{item.source_family}")
    if item.observation_type not in OBSERVATION_TYPES:
        violations.append(f"INVALID_OBSERVATION_TYPE:{item.observation_type}")
    if item.spatial_scope not in SPATIAL_SCOPES:
        violations.append(f"INVALID_SPATIAL_SCOPE:{item.spatial_scope}")

    # Unit validation: if provided, must be canonical
    if item.unit is not None and item.unit not in CANONICAL_UNITS:
        violations.append(f"NON_CANONICAL_UNIT:{item.unit}")

    # Confidence bounds
    if not (0.0 <= item.confidence <= 1.0):
        violations.append(f"CONFIDENCE_OUT_OF_BOUNDS:{item.confidence}")
    if not (0.0 <= item.reliability <= 1.0):
        violations.append(f"RELIABILITY_OUT_OF_BOUNDS:{item.reliability}")

    # Forecast must not claim to be observation
    if item.observation_type == "forecast" and item.source_family not in ("weather_forecast", "history"):
        violations.append("FORECAST_FROM_NON_FORECAST_SOURCE")

    # Provenance ref should be present
    if not item.provenance_ref:
        violations.append("MISSING_PROVENANCE_REF")

    return violations


def quarantine_evidence(
    item: EvidenceItem, violations: List[str]
) -> QuarantinedEvidence:
    """Create a quarantine record for invalid evidence."""
    severity = "blocking" if len(violations) >= 3 else (
        "error" if len(violations) >= 1 else "warning"
    )
    return QuarantinedEvidence(
        evidence_id=item.evidence_id,
        reason_codes=violations,
        original_source_family=item.source_family,
        variable=item.variable,
        severity=severity,
        can_override=False,
        original_value=item.value,
        original_unit=item.unit,
    )
