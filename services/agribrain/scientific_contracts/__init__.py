"""Scientific Contracts — Central Package.

Isolated scientific contract definitions for AgriBrain.
Must not import from world_model, layer05_asmae, or any layer package.
"""

from __future__ import annotations

from .authority import (
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
from .exceptions import ContractViolation, Layer10PublicationConstructionError
from .identity import (
    WORLDLINE_CONTRACT_VERSION,
    WORLDLINE_IDENTITY_V1,
    WORLDLINE_IDENTITY_V2,
    EventIdentityInput,
    ExternalParentRef,
    ParentRef,
    compute_payload_hash,
    compute_v2_identity,
)
from .ledger_adapter import (
    canonicalize_state_support_record,
    index_state_support_ledger,
    validate_ledger_dict,
)
from .state_support import ObservationRelationship, StateSupportRecord
from .resolution import (
    CURRENT_EXPERIMENTAL_RESOLUTION,
    DEFAULT_10M_RESOLUTION,
    ResolutionAuthority,
    ResolutionContract,
    ResolutionValidationProof,
    SupportBasis,
    TransformationClass,
)
from .state_schema_ref import (
    LAYER10_PUBLICATION_SCHEMA_VERSION,
    SCIENTIFIC_CONTRACTS_VERSION,
    STATE_ORDER,
    STATE_SCHEMA_VERSION,
    STATE_STATUS_CONTRACT_VERSION,
    STATE_SUPPORT_LEDGER_SCHEMA_VERSION,
)
from .state_status import StateSupportStatus, normalize_status

__all__ = [
    "ContractViolation",
    "Layer10PublicationConstructionError",
    "AuthorityVector",
    "ProductClass",
    "EpistemicReality",
    "SpatialSupport",
    "ProductRole",
    "OperationalStatus",
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
    "ResolutionContract",
    "ResolutionValidationProof",
    "TransformationClass",
    "SupportBasis",
    "ResolutionAuthority",
    "DEFAULT_10M_RESOLUTION",
    "CURRENT_EXPERIMENTAL_RESOLUTION",
    "WORLDLINE_IDENTITY_V1",
    "WORLDLINE_IDENTITY_V2",
    "WORLDLINE_CONTRACT_VERSION",
    "ParentRef",
    "ExternalParentRef",
    "EventIdentityInput",
    "compute_payload_hash",
    "compute_v2_identity",
    "StateSupportStatus",
    "normalize_status",
    "STATE_SCHEMA_VERSION",
    "STATE_SUPPORT_LEDGER_SCHEMA_VERSION",
    "STATE_STATUS_CONTRACT_VERSION",
    "SCIENTIFIC_CONTRACTS_VERSION",
    "LAYER10_PUBLICATION_SCHEMA_VERSION",
    "STATE_ORDER",
    "index_state_support_ledger",
    "validate_ledger_dict",
    "canonicalize_state_support_record",
    "ObservationRelationship",
    "StateSupportRecord",
]
