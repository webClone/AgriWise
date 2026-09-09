"""MESIA Constitutional Principles — R6 §1.2.

Runtime-enforceable validation rules implementing principles P-01 through P-10.
Every principle raises ConstitutionalViolation on breach.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from ..ontology.identity_states import IdentityState
from ..ontology.evidence_roles import EvidenceRole
from ..ontology.coverage_outcomes import CoverageOutcome


class ConstitutionalViolation(ValueError):
    """Raised when an operation violates one of MESIA's 10 constitutional principles."""

    def __init__(self, principle_id: str, message: str) -> None:
        self.principle_id = principle_id
        super().__init__(f"[{principle_id}] Constitutional Violation: {message}")


def check_p01_no_universal_receiver(coverage_manifest_ref: Optional[str]) -> None:
    """P-01: No universal-receiver fiction.

    A valid coverage manifest or tuple reference must exist before
    scheduling or scanning.
    """
    if not coverage_manifest_ref or not coverage_manifest_ref.strip():
        raise ConstitutionalViolation(
            "P-01",
            "Cannot scan or observe without an explicit CoverageManifest or CoverageTuple reference.",
        )


def check_p02_discover_before_identify(has_detection_event: bool, identity_state: str) -> None:
    """P-02: Discover before identify.

    Protocol confirmation or candidate classification requires a prior
    calibrated wave detection event.
    """
    classified_states = {
        IdentityState.WAVEFORM_CLASSIFIED.value,
        IdentityState.RAT_CANDIDATE.value,
        IdentityState.PROTOCOL_CONFIRMED.value,
        IdentityState.CONTROLLED_SOURCE.value,
    }
    if identity_state in classified_states and not has_detection_event:
        raise ConstitutionalViolation(
            "P-02",
            f"Cannot assign identity state {identity_state} without a valid WaveCandidate detection event.",
        )


def check_p03_identify_before_sense(
    evidence_role: str,
    identity_state: str,
    has_receipt: bool,
) -> None:
    """P-03: Identify before sense.

    Environmental sensing role requires confirmed protocol identity or
    controlled source, backed by direct evidence.
    """
    if evidence_role == EvidenceRole.SENSING.value:
        valid_states = {
            IdentityState.PROTOCOL_CONFIRMED.value,
            IdentityState.CONTROLLED_SOURCE.value,
        }
        if identity_state not in valid_states:
            raise ConstitutionalViolation(
                "P-03",
                f"Sensing evidence role requires PROTOCOL_CONFIRMED or CONTROLLED_SOURCE, got {identity_state}.",
            )
        if identity_state == IdentityState.PROTOCOL_CONFIRMED.value and not has_receipt:
            raise ConstitutionalViolation(
                "P-03",
                "PROTOCOL_CONFIRMED sensing evidence requires a valid ProtocolConfirmationReceipt.",
            )


def check_p04_native_evidence_survives(native_uri: Optional[str], native_hash: Optional[str]) -> None:
    """P-04: Native evidence survives.

    IQ, CSI, range profiles, radar cubes, tag responses, or telephony metadata
    must have immutable native artefact references and content hashes.
    """
    if not native_uri or not native_uri.strip():
        raise ConstitutionalViolation(
            "P-04",
            "Native evidence URI cannot be empty. Derived features do not replace raw native data.",
        )
    if not native_hash or not native_hash.strip():
        raise ConstitutionalViolation(
            "P-04",
            "Native evidence content hash cannot be empty.",
        )
    if native_hash == "f" * 64 or native_hash == "d" * 64:
        raise ConstitutionalViolation(
            "P-04",
            "Native evidence content hash cannot be a placeholder.",
        )


def check_p05_no_raw_phase_stitching(fusion_mechanism: str) -> None:
    """P-05: No raw-phase stitching across independent RATs.

    Fusion occurs at calibrated likelihood, event, state constraint or closure level.
    """
    forbidden_mechanisms = {
        "RAW_PHASE_STITCHING",
        "COHERENT_CHANNEL_CONCATENATION",
        "UNVETTED_EMBEDDING_INJECTION",
    }
    if fusion_mechanism.upper() in forbidden_mechanisms:
        raise ConstitutionalViolation(
            "P-05",
            f"Forbidden cross-RAT fusion mechanism: {fusion_mechanism}. Fusion must occur at likelihood/event/closure level.",
        )


def check_p06_configuration_is_measurement(
    instrument_epoch_id: Optional[str],
    calibration_state_id: Optional[str],
) -> None:
    """P-06: Configuration is part of the measurement.

    Instrument and calibration epochs are mandatory scientific inputs.
    """
    if not instrument_epoch_id or not instrument_epoch_id.strip():
        raise ConstitutionalViolation(
            "P-06",
            "InstrumentEpoch reference is mandatory for every scientific observation.",
        )
    if not calibration_state_id or not calibration_state_id.strip():
        raise ConstitutionalViolation(
            "P-06",
            "CalibrationState reference is mandatory for every scientific observation.",
        )


def check_p07_unknown_is_valid(
    identity_state: str,
    abstention_score: Optional[float] = None,
    threshold: float = 0.5,
) -> None:
    """P-07: Unknown is a valid result.

    If abstention or ambiguity is indicated, it must not be forced to a known class.
    """
    if abstention_score is not None and abstention_score > threshold:
        if identity_state in {IdentityState.PROTOCOL_CONFIRMED.value, IdentityState.CONTROLLED_SOURCE.value}:
            raise ConstitutionalViolation(
                "P-07",
                f"Abstention score {abstention_score} exceeds threshold {threshold}; cannot force to {identity_state}.",
            )


def check_p08_asmae_owns_posterior(authority_scope: str) -> None:
    """P-08: ASMAE owns the posterior.

    MESIA emits evidence proposals or likelihoods only; it never directly
    updates agricultural state.
    """
    forbidden_scopes = {
        "AGRICULTURAL_POSTERIOR",
        "STATE_UPDATE",
        "DIRECT_PRESCRIPTION",
    }
    if authority_scope.upper() in forbidden_scopes or authority_scope != "evidence_proposal":
        raise ConstitutionalViolation(
            "P-08",
            f"MESIA outputs must carry authority_scope='evidence_proposal', got {authority_scope}.",
        )


def check_p09_capabilities_qualify_separately(target_variable: Optional[str], domain_scoped: bool) -> None:
    """P-09: Capabilities qualify separately.

    A cluster is never globally certified; qualification is specific to a target and domain.
    """
    if not target_variable or not target_variable.strip():
        raise ConstitutionalViolation(
            "P-09",
            "CapabilityAuthorityRecord must specify an explicit target_variable (no global certification).",
        )
    if not domain_scoped:
        raise ConstitutionalViolation(
            "P-09",
            "CapabilityAuthorityRecord must define an explicit operational domain.",
        )


def check_p10_fail_closed_and_revoke(calibration_valid: bool, closure_valid: bool, current_state: str) -> None:
    """P-10: Fail closed and revoke.

    Failed calibration or closure must demote or revoke capability authority.
    """
    if (not calibration_valid or not closure_valid) and current_state == "QUALIFIED":
        raise ConstitutionalViolation(
            "P-10",
            "Failed calibration or closure cannot retain QUALIFIED capability state. Must demote/revoke.",
        )


def validate_observation_packet(packet: Any) -> None:
    """Run all applicable constitutional checks on a RadioObservationPacket."""
    check_p04_native_evidence_survives(packet.native_data_uri, packet.native_data_hash)
    check_p06_configuration_is_measurement(packet.instrument_epoch_id, packet.calibration_state_id)
    check_p08_asmae_owns_posterior(packet.authority_scope)

    if packet.evidence_role == EvidenceRole.SENSING.value:
        has_receipt = bool(getattr(packet, "receipt_id", None) or getattr(packet, "task_receipt_ref", None))
        check_p03_identify_before_sense(packet.evidence_role, packet.identity_state, has_receipt=has_receipt)
