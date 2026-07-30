"""R5.0: Canonical event identity computation.

Re-exports and wraps central scientific_contracts.identity to maintain single source of truth.
"""

from __future__ import annotations

from services.agribrain.scientific_contracts.identity import (
    WORLDLINE_CONTRACT_VERSION,
    WORLDLINE_IDENTITY_V1,
    WORLDLINE_IDENTITY_V2,
    EventIdentityInput,
    EventIdentityRecord,
    ExternalParentRef,
    ParentRef,
    compute_payload_hash,
    compute_v1_identity,
    compute_v2_identity,
)

__all__ = [
    "WORLDLINE_IDENTITY_V1",
    "WORLDLINE_IDENTITY_V2",
    "WORLDLINE_CONTRACT_VERSION",
    "ParentRef",
    "ExternalParentRef",
    "EventIdentityInput",
    "EventIdentityRecord",
    "compute_payload_hash",
    "compute_v1_identity",
    "compute_v2_identity",
]
