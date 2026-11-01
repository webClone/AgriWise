"""Trusted current-ASMAE-publication reader and issuance preflight.

Phase 1B only. NO authorization issuer, signer or public action export.
This module deliberately has no API that mints a V2 authorization envelope.

Never accept a canonical head from HTTP/request JSON. Re-fetch the current head
using the namespace derived from authenticated server context.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.scientific_contracts.exceptions import ContractViolation
from services.agribrain.scientific_contracts.prescription_authorization import (
    CANONICAL_PUBLICATION_VALIDATION_FLAGS,
    _required_hash,
    _required_text,
    _utc_instant,
)


@dataclass(frozen=True)
class PublicationToPrescriptionPreflight:
    status: str
    reason: str
    plot_id: str
    snapshot_id: Optional[str]
    publication_receipt_hash: Optional[str]
    # Deliberately no "authorization", "signature" or "authorized_actions".


def read_trusted_current_asmae_publication(
    namespace: PlotNamespace,
    *,
    expected_snapshot_id: str,
    expected_geometry_hash: str,
    expected_crop_cycle_id: str,
    require_proof_attestation: bool = False,
) -> dict:
    """Fetch exactly the current locally revalidated head for one authenticated plot.

    The caller MUST supply an already-authorized PlotNamespace and the currently
    resolved geometry/crop cycle from trusted server state. This read does not
    update a head, publish a snapshot, invoke an orchestrator or sign an action.

    The raw storage return lacks "available": add it only after every verification
    has completed, yielding the strict shape consumed by the V2 binding validator.
    """
    if not isinstance(namespace, PlotNamespace) or not namespace.is_valid():
        raise ContractViolation("Trusted publication read requires an authenticated PlotNamespace")
    expected_snapshot = _required_text(expected_snapshot_id, "expected snapshot_id")
    expected_geometry = _required_hash(expected_geometry_hash, "expected geometry_hash")
    expected_cycle = _required_text(expected_crop_cycle_id, "expected crop_cycle_id")

    # Import only inside the function to preserve scientific_contracts layer
    # isolation and guarantee this is the real store, not HTTP request data.
    from services.agribrain.layer05_asmae.plot_snapshot_store import load_latest_plot_snapshot
    raw = load_latest_plot_snapshot(namespace)
    if not isinstance(raw, dict):
        raise ContractViolation("Current canonical plot head is unavailable")
    if raw.get("snapshot_kind") != "asmae" or not str(raw.get("snapshot_id") or "").startswith("ASMAE-SNAPSHOT-"):
        raise ContractViolation("Current canonical head is not an ASMAE publication")
    if raw.get("snapshot_id") != expected_snapshot:
        raise ContractViolation("Current ASMAE snapshot differs from the requested exact snapshot")
    for field, expected in (
        ("tenant_id", namespace.tenant_id),
        ("farm_id", namespace.farm_id),
        ("plot_id", namespace.plot_id),
        ("geometry_hash", expected_geometry),
        ("crop_cycle_id", expected_cycle),
    ):
        if raw.get(field) != expected:
            raise ContractViolation(f"Current ASMAE publication {field} mismatch")
    validation = raw.get("validation")
    if not isinstance(validation, Mapping) or not all(
        validation.get(flag) is True for flag in CANONICAL_PUBLICATION_VALIDATION_FLAGS
    ):
        raise ContractViolation("Current ASMAE publication is not fully integrity-validated")

    receipt = _required_hash(raw.get("publication_receipt_hash"), "publication_receipt_hash")
    # Caution: manifest_hash identifies the ASMAE JOB manifest. It is NOT a
    # per-evidence-membership proof for L8 tribunal-accepted contributors.
    manifest = _required_hash(raw.get("manifest_hash"), "job manifest_hash")
    window = raw.get("observation_window")
    if not isinstance(window, Mapping):
        raise ContractViolation("Current ASMAE observation window is missing")
    start = _utc_instant(window.get("start"), "observation_window.start")
    end = _utc_instant(window.get("end"), "observation_window.end")
    cutoff = _utc_instant(raw.get("evidence_cutoff_at"), "evidence_cutoff_at")
    published = _utc_instant(raw.get("published_at"), "published_at")
    # Use chronological comparisons, including sub-second precision.
    from datetime import datetime
    instants = [datetime.fromisoformat(t.replace("Z", "+00:00")) for t in (start, end, cutoff, published)]
    if not all(left <= right for left, right in zip(instants, instants[1:])):
        raise ContractViolation("Current ASMAE publication has invalid temporal order")

    if require_proof_attestation and raw.get("proof_attestation_valid") is not True:
        raise ContractViolation(f"Current ASMAE publication lacks an authenticated proof attestation: {raw.get('proof_attestation_reason')}")

    # Deliberately return a limited copy with no mutable scientific internals.
    return {
        "available": True,
        "snapshot_kind": "asmae",
        "tenant_id": namespace.tenant_id,
        "farm_id": namespace.farm_id,
        "plot_id": namespace.plot_id,
        "geometry_hash": expected_geometry,
        "crop_cycle_id": expected_cycle,
        "snapshot_id": expected_snapshot,
        "publication_receipt_hash": receipt,
        "manifest_hash": manifest,
        "evidence_cutoff_at": cutoff,
        "published_at": published,
        "observation_window": {"start": start, "end": end},
        "validation": {flag: True for flag in CANONICAL_PUBLICATION_VALIDATION_FLAGS},
        "admitted_evidence_root_hash": raw.get("admitted_evidence_root_hash"),
        "bounded_uncertainty_receipt_hash": raw.get("bounded_uncertainty_receipt_hash"),
        "scientific_posterior_hash": raw.get("scientific_posterior_hash"),
        "proof_attestation": raw.get("proof_attestation"),
        "proof_attestation_hash": raw.get("proof_attestation_hash"),
        "proof_attestation_valid": raw.get("proof_attestation_valid"),
        "proof_attestation_reason": raw.get("proof_attestation_reason"),
    }


def preflight_pilot_issuer(
    namespace: PlotNamespace,
    *,
    expected_snapshot_id: str,
    expected_geometry_hash: str,
    expected_crop_cycle_id: str,
    artifact: Any,
) -> PublicationToPrescriptionPreflight:
    """Read-only assessment of existing authority; NEVER issues a prescription.

    In particular, an L8 internal belief/manifest hash cannot be promoted into
    canonical ASMAE evidence merely because both look like SHA-256 strings.
    Until the physically admitted evidence-membership receipt, uncertainty
    validation and trusted issuance/revocation service are connected, status
    stays BLOCKED for ALL candidates, including otherwise healthy snapshots.
    """
    publication = read_trusted_current_asmae_publication(
        namespace, expected_snapshot_id=expected_snapshot_id,
        expected_geometry_hash=expected_geometry_hash,
        expected_crop_cycle_id=expected_crop_cycle_id,
    )
    if artifact is None:
        reason = "NO_RECORDED_PLOT_RUN"
    else:
        inputs = getattr(artifact, "inputs", None)
        if not inputs or getattr(inputs, "plot_namespace", None) != namespace:
            reason = "ORCHESTRATOR_NAMESPACE_MISMATCH"
        elif (not isinstance(getattr(inputs, "policy_snapshot", None), Mapping)
              or getattr(inputs, "policy_snapshot", {}).get("require_evidence_receipts") is not True):
            reason = "MANDATORY_EVIDENCE_RECEIPT_POLICY_ABSENT"
        else:
            gate = (getattr(artifact, "diagnostic_integration", None) or {}).get("prescription_gate") or {}
            manifest = gate.get("influence_manifest") or {}
            if gate.get("status") != "completed" or manifest.get("requested_use") != "PRESCRIPTION_DRIVER":
                reason = "DIAGNOSTIC_PROMOTION_GATE_UNAVAILABLE"
            else:
                reason = "ASSIMILATION_TO_L8_MEMBERSHIP_AND_UNCERTAINTY_UNVERIFIED"
    return PublicationToPrescriptionPreflight(
        status="BLOCKED",
        reason=reason,
        plot_id=namespace.plot_id,
        snapshot_id=publication["snapshot_id"],
        publication_receipt_hash=publication["publication_receipt_hash"],
    )
