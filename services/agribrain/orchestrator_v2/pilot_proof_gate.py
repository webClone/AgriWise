"""Strict *structural* scientific pilot proof gates. NOT an authorization issuer.

The currently published ASMAE head lacks admitted_evidence_root_hash and
bounded_uncertainty_receipt_hash. Consequently these checks fail closed against
real heads until immutable publication producers actually commit/validate those
roots. Call only with a head already fetched from authenticated server storage;
untrusted client JSON is never sufficient authority.

A content hash binds a claimed witness to a publication root; it does NOT
independently establish instrument calibration, source truth, or policy approval.
No public action/export/signing path calls this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
import re
from typing import Any, Mapping, Sequence

from services.agribrain.scientific_contracts.exceptions import ContractViolation
from services.agribrain.scientific_contracts.prescription_authorization import (
    CANONICAL_PUBLICATION_VALIDATION_FLAGS,
    PrescriptionAuthorizationEnvelopeV2,
    canonical_hash,
    _required_hash,
    _required_text,
    _utc_instant,
)


@dataclass(frozen=True)
class PilotProofCheck:
    kind: str
    status: str  # STRUCTURAL_MATCH_ONLY, never AUTHORIZED
    claimed_root: str
    checked_entries: int


def _same_instant(left: Any, right: Any, name: str) -> bool:
    l = datetime.fromisoformat(_utc_instant(left, name).replace("Z", "+00:00"))
    r = datetime.fromisoformat(_utc_instant(right, name).replace("Z", "+00:00"))
    return l == r


def _time(value: Any, name: str) -> datetime:
    return datetime.fromisoformat(_utc_instant(value, name).replace("Z", "+00:00"))


def _strict_hash(value: Any, name: str) -> str:
    return _required_hash(value, name)


def _verified_head(head: Mapping[str, Any], envelope: PrescriptionAuthorizationEnvelopeV2) -> None:
    if not isinstance(head, Mapping) or head.get("available") is not True:
        raise ContractViolation("Scientific proof requires current authenticated publication")
    if head.get("snapshot_kind") != "asmae":
        raise ContractViolation("Scientific proof requires current ASMAE publication")
    flags = head.get("validation")
    if not isinstance(flags, Mapping) or not all(
        flags.get(k) is True for k in CANONICAL_PUBLICATION_VALIDATION_FLAGS
    ):
        raise ContractViolation("Scientific proof requires all current publication validation flags")
    for field in ("tenant_id", "farm_id", "plot_id", "geometry_hash", "crop_cycle_id", "snapshot_id"):
        if head.get(field) != getattr(envelope, field):
            raise ContractViolation(f"Scientific proof {field} mismatch")
    for field, env_field in (
        ("publication_receipt_hash", "canonical_publication_receipt_hash"),
        ("manifest_hash", "evidence_manifest_hash"),
    ):
        if head.get(field) != getattr(envelope, env_field):
            raise ContractViolation(f"Scientific proof {field} mismatch")
    if not _same_instant(head.get("evidence_cutoff_at"), envelope.evidence_cutoff_at, "evidence cutoff"):
        raise ContractViolation("Scientific proof cutoff mismatch")


def _witness_claims(witness: Mapping[str, Any], envelope: PrescriptionAuthorizationEnvelopeV2) -> None:
    if not isinstance(witness, Mapping):
        raise ContractViolation("Scientific witness is missing")
    for field in ("tenant_id", "farm_id", "plot_id", "geometry_hash", "crop_cycle_id", "snapshot_id"):
        if witness.get(field) != getattr(envelope, field):
            raise ContractViolation(f"Scientific witness {field} mismatch")
    for claim, attribute in (
        ("publication_receipt_hash", "canonical_publication_receipt_hash"),
        ("job_manifest_hash", "evidence_manifest_hash"),
    ):
        if witness.get(claim) != getattr(envelope, attribute):
            raise ContractViolation(f"Scientific witness {claim} mismatch")
    if not _same_instant(witness.get("evidence_cutoff_at"), envelope.evidence_cutoff_at, "evidence cutoff"):
        raise ContractViolation("Scientific witness evidence cutoff mismatch")


def _hash_witness(witness: Mapping[str, Any], *, published_hash: Any, field_name: str) -> str:
    """Require an immutable publication hash, never derive trust from the witness."""
    expected = _strict_hash(published_hash, field_name)
    claimed = _strict_hash(witness.get("content_hash"), "witness content_hash")
    unsigned = {key: value for key, value in witness.items() if key != "content_hash"}
    if claimed != canonical_hash(unsigned) or claimed != expected:
        raise ContractViolation(f"{field_name} does not match a published immutable proof")
    return claimed


def verify_published_evidence_membership(
    *,
    head: Mapping[str, Any],
    envelope: PrescriptionAuthorizationEnvelopeV2,
    membership_witness: Mapping[str, Any],
    admitted_evidence_receipts: Mapping[str, Any],
    reference_time: str,
    permitted_truth_classes: Sequence[str],
    action_class: str,
) -> PilotProofCheck:
    """Verify a publication-anchored membership *claim*, not source acquisition.

    A future trusted publisher must commit the witness root into the immutable
    ASMAE node and its validated head. The currently deployed head has no such
    field; no caller-supplied witness can substitute for it.
    """
    if not isinstance(envelope, PrescriptionAuthorizationEnvelopeV2):
        raise ContractViolation("Published membership requires V2")
    _verified_head(head, envelope)
    _witness_claims(membership_witness, envelope)
    if membership_witness.get("schema_version") != "pilot_admitted_membership_v1":
        raise ContractViolation("Unsupported admitted evidence membership schema")
    for field, expected in (
        ("input_belief_id", envelope.input_belief_id),
        ("tribunal_content_hash", envelope.tribunal_content_hash),
        ("prescription_manifest_hash", envelope.prescription_manifest_hash),
    ):
        if membership_witness.get(field) != expected:
            raise ContractViolation(f"Membership {field} mismatch")
    permitted = set(permitted_truth_classes)
    if not permitted or any(not isinstance(x, str) or not x.strip() for x in permitted):
        raise ContractViolation("Membership requires a trusted nonempty truth-class policy")
    accepted = membership_witness.get("accepted_contribution_ids")
    if not isinstance(accepted, list) or not accepted or len(set(accepted)) != len(accepted):
        raise ContractViolation("Membership must list distinct tribunal-accepted contributions")
    selected = tuple(envelope.prescription_manifest_entry_ids)
    if not selected or not set(selected).issubset(set(accepted)):
        raise ContractViolation("Selected L8 contribution lacks tribunal acceptance")
    entries = membership_witness.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ContractViolation("Publication membership has no evidence entries")
    if not isinstance(admitted_evidence_receipts, Mapping):
        raise ContractViolation("Physical evidence receipts are missing")
    cutoff = _time(envelope.evidence_cutoff_at, "evidence cutoff")
    at = _time(reference_time, "membership reference time")
    covered: set[str] = set()
    distinct: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ContractViolation("Invalid membership entry")
        contribution = _required_text(entry.get("contribution_id"), "contribution ID")
        evidence_id = _required_text(entry.get("evidence_id"), "evidence ID")
        content = _strict_hash(entry.get("evidence_content_hash"), "admitted evidence hash")
        if contribution not in accepted or (contribution, evidence_id) in distinct:
            raise ContractViolation("Duplicate or nonaccepted contribution/evidence")
        distinct.add((contribution, evidence_id))
        receipt = admitted_evidence_receipts.get(contribution)
        # Require a real typed EvidenceReceipt, not a dict with booleans coerced
        # through its permissive legacy from_dict() parser.
        from services.agribrain.scientific_contracts.evidence_receipt import EvidenceReceipt
        if not isinstance(receipt, EvidenceReceipt) or receipt.contribution_id != contribution:
            raise ContractViolation("Missing typed physical evidence receipt for contribution")
        if (len(receipt.evidence_ids) != len(receipt.content_hashes)
                or (evidence_id, content) not in zip(receipt.evidence_ids, receipt.content_hashes)):
            raise ContractViolation("Contribution evidence/receipt content mismatch")
        if not all(type(getattr(receipt, key)) is bool and getattr(receipt, key)
                   for key in ("is_calibrated", "calibration_valid", "spatial_support_valid")):
            raise ContractViolation("Evidence calibration or spatial support is not verified")
        if not receipt.calibration_certificate_id or not receipt.originating_stage_receipt_id:
            raise ContractViolation("Evidence lacks a calibration or stage receipt reference")
        if receipt.truth_class not in permitted:
            raise ContractViolation("Unadmitted truth class; operational telemetry is not certified")
        if receipt.spatial_support.get("geometry_hash") != envelope.geometry_hash:
            raise ContractViolation("Evidence spatial support does not match publication geometry")
        if _time(receipt.observation_timestamp.isoformat(), "observation time") > cutoff:
            raise ContractViolation("Post-cutoff telemetry cannot be admitted into published science")
        valid, _ = receipt.is_valid_for_action(action_class, reference_time=at)
        if not valid:
            raise ContractViolation("Evidence expired, uncalibrated or not eligible for action")
        covered.add(contribution)
    if not set(selected).issubset(covered):
        raise ContractViolation("Not every selected L8 contribution has admitted evidence")
    root = _hash_witness(
        membership_witness,
        published_hash=head.get("admitted_evidence_root_hash"),
        field_name="admitted_evidence_root_hash",
    )
    return PilotProofCheck(
        kind="ADMITTED_MEMBERSHIP", status="STRUCTURAL_MATCH_ONLY",
        claimed_root=root, checked_entries=len(entries),
    )


def verify_published_uncertainty_bounds(
    *,
    head: Mapping[str, Any],
    envelope: PrescriptionAuthorizationEnvelopeV2,
    uncertainty_witness: Mapping[str, Any],
    membership: PilotProofCheck,
) -> PilotProofCheck:
    """Require published, action-specific posterior uncertainty proof.

    This is structural consistency only. Source covariance/posterior verification
    must happen in an authenticated scientific publication producer.
    """
    if not isinstance(envelope, PrescriptionAuthorizationEnvelopeV2):
        raise ContractViolation("Published uncertainty requires V2")
    _verified_head(head, envelope)
    _witness_claims(uncertainty_witness, envelope)
    if not isinstance(membership, PilotProofCheck) or membership.kind != "ADMITTED_MEMBERSHIP" or membership.status != "STRUCTURAL_MATCH_ONLY":
        raise ContractViolation("Published membership proof is missing")
    if membership.claimed_root != _strict_hash(
        head.get("admitted_evidence_root_hash"), "admitted_evidence_root_hash"
    ):
        raise ContractViolation("Uncertainty membership proof is not anchored to publication")
    if uncertainty_witness.get("schema_version") != "pilot_bounded_uncertainty_v1":
        raise ContractViolation("Unsupported published uncertainty witness schema")
    if uncertainty_witness.get("admitted_evidence_root_hash") != membership.claimed_root:
        raise ContractViolation("Uncertainty receipt is detached from admitted evidence")
    source_posterior = _strict_hash(
        uncertainty_witness.get("source_posterior_hash"), "source_posterior_hash"
    )
    if source_posterior != _strict_hash(head.get("scientific_posterior_hash"), "scientific_posterior_hash"):
        raise ContractViolation("Uncertainty posterior is detached from ASMAE state")
    actions = uncertainty_witness.get("actions")
    if not isinstance(actions, list) or not actions:
        raise ContractViolation("Published uncertainty must cover selected actions")
    by_id = {}
    for item in actions:
        if not isinstance(item, Mapping) or not isinstance(item.get("action_id"), str):
            raise ContractViolation("Invalid action uncertainty entry")
        action_id = item["action_id"]
        if not action_id or action_id in by_id:
            raise ContractViolation("Duplicate action uncertainty entry")
        by_id[action_id] = item
    if set(by_id) != {a.action_id for a in envelope.actions}:
        raise ContractViolation("Uncertainty action coverage mismatch")
    for action in envelope.actions:
        item = by_id[action.action_id]
        if not item.get("zone_targets") or set(item["zone_targets"]) != set(action.zone_targets):
            raise ContractViolation("Action uncertainty zone mismatch")
        if not isinstance(item.get("timing"), Mapping) or dict(item["timing"]) != dict(action.timing):
            raise ContractViolation("Action uncertainty timing mismatch")
        if action.rate:
            if item.get("unit") != action.rate.get("unit"):
                raise ContractViolation("Action uncertainty rate unit mismatch")
            lower, upper = item.get("min_safe"), item.get("max_safe")
            if any(type(x) not in (int, float) or not math.isfinite(x) for x in (lower, upper)):
                raise ContractViolation("Action uncertainty has invalid bounds")
            if (lower < 0 or lower > upper
                    or lower > action.rate["min_safe"]
                    or upper < action.rate["max_safe"]):
                raise ContractViolation("Action rate exceeds published scientific uncertainty bounds")
        elif any(item.get(k) is not None for k in ("min_safe", "max_safe", "unit")):
            raise ContractViolation("Monitoring cannot inherit physical dose uncertainty")
    root = _hash_witness(
        uncertainty_witness,
        published_hash=head.get("bounded_uncertainty_receipt_hash"),
        field_name="bounded_uncertainty_receipt_hash",
    )
    if envelope.uncertainty_receipt_hash != root:
        raise ContractViolation("V2 uncertainty receipt is not the published receipt")
    return PilotProofCheck(
        kind="BOUNDED_UNCERTAINTY", status="STRUCTURAL_MATCH_ONLY",
        claimed_root=root, checked_entries=len(actions),
    )
