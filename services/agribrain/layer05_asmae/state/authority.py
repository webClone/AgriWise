"""Re-export shim for authority contracts.

Redirects to central scientific_contracts package.
"""

from __future__ import annotations

from services.agribrain.scientific_contracts.authority import (
    AUTHORITY_BLOCKED,
    AUTHORITY_ASSIMILATION_INPUT_APPROVED,
    AUTHORITY_DIAGNOSTIC,
    AUTHORITY_DIAGNOSTIC_NO_STATE_UPDATE,
    AUTHORITY_MACHINE_EXECUTION_APPROVED,
    AUTHORITY_PRESCRIPTION_DRIVER_APPROVED,
    AUTHORITY_TRAINING_APPROVED,
    AUTHORITY_VISUAL_ONLY_NO_DIAGNOSIS,
    AUTHORITY_VISUALIZATION_ONLY,
    AuthorityVector,
    EpistemicReality,
    OperationalStatus,
    ProductClass,
    ProductRole,
    ScientificProductEnvelope,
    SpatialSupport,
)

__all__ = [
    "ProductClass",
    "EpistemicReality",
    "SpatialSupport",
    "ProductRole",
    "OperationalStatus",
    "AuthorityVector",
    "ScientificProductEnvelope",
    "AUTHORITY_BLOCKED",
    "AUTHORITY_VISUAL_ONLY_NO_DIAGNOSIS",
    "AUTHORITY_DIAGNOSTIC_NO_STATE_UPDATE",
    "AUTHORITY_ASSIMILATION_INPUT_APPROVED",
    "AUTHORITY_TRAINING_APPROVED",
    "AUTHORITY_PRESCRIPTION_DRIVER_APPROVED",
    "AUTHORITY_MACHINE_EXECUTION_APPROVED",
    "AUTHORITY_VISUALIZATION_ONLY",
    "AUTHORITY_DIAGNOSTIC",
]
