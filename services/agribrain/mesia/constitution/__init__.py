"""MESIA Constitution — Invariants, Scope, and Boundaries."""

from .principles import (
    ConstitutionalViolation,
    check_p01_no_universal_receiver,
    check_p02_discover_before_identify,
    check_p03_identify_before_sense,
    check_p04_native_evidence_survives,
    check_p05_no_raw_phase_stitching,
    check_p06_configuration_is_measurement,
    check_p07_unknown_is_valid,
    check_p08_asmae_owns_posterior,
    check_p09_capabilities_qualify_separately,
    check_p10_fail_closed_and_revoke,
    validate_observation_packet,
)
from .scope import (
    SupportedFamily,
    ExcludedClaim,
    TargetState,
    EXCLUDED_CLAIMS,
)

__all__ = [
    "ConstitutionalViolation",
    "check_p01_no_universal_receiver",
    "check_p02_discover_before_identify",
    "check_p03_identify_before_sense",
    "check_p04_native_evidence_survives",
    "check_p05_no_raw_phase_stitching",
    "check_p06_configuration_is_measurement",
    "check_p07_unknown_is_valid",
    "check_p08_asmae_owns_posterior",
    "check_p09_capabilities_qualify_separately",
    "check_p10_fail_closed_and_revoke",
    "validate_observation_packet",
    "SupportedFamily",
    "ExcludedClaim",
    "TargetState",
    "EXCLUDED_CLAIMS",
]
