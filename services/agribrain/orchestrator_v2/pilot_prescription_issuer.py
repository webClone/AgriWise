"""Phase 1E-B: Trusted server-owned positive prescription authorization issuer.

Binds qualified L8 actions, verified evidence membership, and bounded uncertainty
to the exact published ASMAE snapshot, attestation, and canonical receipt.
Registers the issued authorization in the durable PilotCandidateLedger.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import math
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.scientific_contracts.exceptions import ContractViolation
from services.agribrain.scientific_contracts.prescription_authorization import (
    AuthorizedActionV1,
    PrescriptionAuthorizationEnvelopeV2,
    PRESCRIPTION_AUTHORIZATION_ENVELOPE_V2,
    CANONICAL_PUBLICATION_VALIDATION_FLAGS,
    canonical_hash,
    _required_hash,
    _required_text,
    _utc_instant,
    selected_entries_exist,
    validate_published_pilot_envelope,
)
from services.agribrain.orchestrator_v2.pilot_proof_gate import (
    PilotProofCheck,
    verify_published_evidence_membership,
    verify_published_uncertainty_bounds,
)
from services.agribrain.orchestrator_v2.pilot_publication_gate import (
    read_trusted_current_asmae_publication,
)
from services.agribrain.orchestrator_v2.pilot_authorization_ledger import (
    PilotCandidateLedger,
    AUTHORIZED_SCHEMA_VERSION,
)
from services.agribrain.orchestrator_v2.schema import LayerStatus
from services.agribrain.orchestrator_v2.run_schema import _serialize_plan


def _iso_to_utc(val: str, label: str) -> str:
    """Normalize date or instant to ISO UTC string."""
    s = _required_text(val, label)
    if "T" not in s:
        s = f"{s}T00:00:00Z"
    return _utc_instant(s, label)


class PilotPrescriptionIssuer:
    """Qualified server-owned issuer for scientific pilot prescriptions.

    Verifies the complete audit lineage:
    1. Real calibrated physical measurements and typed evidence receipts.
    2. ASMAE assimilation membership anchored to the published root.
    3. Diagnostic-to-prescriptive promotion via completed prescription gate.
    4. Bounded posterior uncertainty receipt covering all selected L8 actions.
    5. Exact current canonical publication and authentic proof attestation.
    6. Safety invariants: machine execution disallowed, confirmation required.
    7. Durable registration in PilotCandidateLedger with domain-separated signature.
    """

    def __init__(self, ledger: PilotCandidateLedger):
        if not isinstance(ledger, PilotCandidateLedger):
            raise ContractViolation("PilotPrescriptionIssuer requires a PilotCandidateLedger instance")
        self.ledger = ledger

    def issue_prescription(
        self,
        *,
        namespace: PlotNamespace,
        crop_cycle_id: str,
        geometry_hash: str,
        artifact: Any,
        membership_witness: Mapping[str, Any],
        admitted_evidence_receipts: Mapping[str, Any],
        uncertainty_witness: Mapping[str, Any],
        now: str,
        expires_at: Optional[str] = None,
        permitted_truth_classes: Sequence[str] = ("CALIBRATED_PHYSICAL_MEASUREMENT",),
    ) -> tuple[PrescriptionAuthorizationEnvelopeV2, dict[str, Any]]:
        """Mint a verified positive PrescriptionAuthorizationEnvelopeV2 and register it."""
        if not isinstance(namespace, PlotNamespace) or not namespace.is_valid():
            raise ContractViolation("Prescription issuer requires a valid PlotNamespace")
        geometry_hash = _required_hash(geometry_hash, "geometry_hash")
        crop_cycle_id = _required_text(crop_cycle_id, "crop_cycle_id")
        issued_instant = _utc_instant(now, "issuance time")

        # 1. Validate artifact structure and L8 result
        if not artifact or not getattr(artifact, "layer_8", None):
            raise ContractViolation("Artifact Layer 8 is missing")
        l8_res = artifact.layer_8
        if l8_res.status != LayerStatus.OK or l8_res.output is None:
            raise ContractViolation("Artifact Layer 8 output is unavailable or degraded")
        l8_output = l8_res.output
        raw_actions = getattr(l8_output, "actions", []) or []
        if not raw_actions:
            raise ContractViolation("L8 produced no actions to authorize")

        # 2. Extract and validate actions
        authorized_actions: list[AuthorizedActionV1] = []
        for a in raw_actions:
            if getattr(a, "machine_execution_allowed", False):
                raise ContractViolation("Machine execution is never allowed for pilot actions")
            if getattr(a, "requires_confirmation", True) is not True:
                raise ContractViolation("Farmer confirmation is strictly required for pilot actions")
            action = a if isinstance(a, AuthorizedActionV1) else AuthorizedActionV1.from_l8_action(a)
            if action.machine_execution_allowed:
                raise ContractViolation("Machine execution is never allowed for pilot actions")
            if not action.requires_confirmation:
                raise ContractViolation("Farmer confirmation is strictly required for pilot actions")
            authorized_actions.append(action)

        # 3. Validate diagnostic-to-prescriptive promotion and tribunal
        gate = (getattr(artifact, "diagnostic_integration", None) or {}).get("prescription_gate") or {}
        if gate.get("status") != "completed":
            raise ContractViolation("Prescription gate did not complete cleanly")
        manifest = gate.get("influence_manifest") or {}
        if manifest.get("requested_use") != "PRESCRIPTION_DRIVER":
            raise ContractViolation("Prescription manifest has the wrong requested use")
        tribunal = gate.get("tribunal_verdict") or {}
        input_belief_id = _required_text(str(gate.get("input_belief_id") or ""), "input_belief_id")
        tribunal_hash = _required_hash(str(tribunal.get("content_hash") or ""), "tribunal_content_hash")
        manifest_hash = _required_hash(str(manifest.get("content_hash") or ""), "prescription_manifest_hash")

        # Entries coverage check
        manifest_entries = manifest.get("entries") or []
        selected_ids = tuple(str(e.get("contribution_id") or "") for e in manifest_entries if isinstance(e, Mapping))
        if not selected_ids:
            raise ContractViolation("Prescription manifest contains no contribution entries")

        # Inputs policy and plan hashes
        inputs = getattr(artifact, "inputs", None)
        if inputs is None:
            raise ContractViolation("Run artifact inputs are missing")
        policy_hash = canonical_hash(getattr(inputs, "policy_snapshot", {}))
        l8_run_id = _required_text(str(getattr(l8_output, "run_id", "") or ""), "l8_run_id")

        l8_content_hash = ""
        audit = getattr(l8_output, "audit", None)
        for check in getattr(audit, "policy_checks", []) if audit else []:
            if isinstance(check, dict) and check.get("check") == "content_hash":
                l8_content_hash = str(check.get("value") or "")
        _required_hash(l8_content_hash, "l8_content_hash")

        plan = getattr(artifact, "final_execution_plan", None)
        if plan is None:
            raise ContractViolation("Final execution plan is missing")
        plan_hash = canonical_hash(_serialize_plan(plan))

        # 4. Fetch and verify current canonical publication
        head = read_trusted_current_asmae_publication(
            namespace,
            expected_geometry_hash=geometry_hash,
            expected_crop_cycle_id=crop_cycle_id,
            require_proof_attestation=True,
        )
        if head.get("available") is not True or head.get("snapshot_kind") != "asmae":
            raise ContractViolation("Current publication must be an available ASMAE snapshot")
        if head.get("proof_attestation_valid") is not True:
            raise ContractViolation("Current publication lacks an authenticated proof attestation")
        attestation = head.get("proof_attestation")
        if not isinstance(attestation, Mapping):
            raise ContractViolation("Current publication attestation is invalid")

        # 5. Determine temporal bounds
        if expires_at is None:
            expiry_dt = datetime.fromisoformat(issued_instant.replace("Z", "+00:00")) + timedelta(hours=72)
            expiry_instant = expiry_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        else:
            expiry_instant = _utc_instant(expires_at, "expires_at")

        window = head.get("observation_window") or {}
        obs_start = _iso_to_utc(window.get("start", ""), "observation_window.start")
        obs_end = _iso_to_utc(window.get("end", ""), "observation_window.end")

        # 6. Construct positive candidate PrescriptionAuthorizationEnvelopeV2
        envelope = PrescriptionAuthorizationEnvelopeV2(
            tenant_id=namespace.tenant_id,
            farm_id=namespace.farm_id,
            plot_id=namespace.plot_id,
            geometry_hash=geometry_hash,
            crop_cycle_id=crop_cycle_id,
            snapshot_id=head["snapshot_id"],
            canonical_publication_receipt_hash=head["publication_receipt_hash"],
            evidence_manifest_hash=head["manifest_hash"],
            evidence_cutoff_at=_utc_instant(head["evidence_cutoff_at"], "evidence_cutoff_at"),
            observation_window_start=obs_start,
            observation_window_end=obs_end,
            published_at=_utc_instant(head["published_at"], "published_at"),
            issued_at=issued_instant,
            expires_at=expiry_instant,
            uncertainty_receipt_hash=head["bounded_uncertainty_receipt_hash"],
            input_belief_id=input_belief_id,
            tribunal_content_hash=tribunal_hash,
            prescription_manifest_hash=manifest_hash,
            prescription_manifest_entry_ids=selected_ids,
            policy_snapshot_hash=policy_hash,
            l8_run_id=l8_run_id,
            l8_content_hash=l8_content_hash,
            final_execution_plan_hash=plan_hash,
            actions=tuple(authorized_actions),
        )

        # 7. Check selected entries existence
        if not selected_entries_exist(envelope, manifest_entries):
            raise ContractViolation("Authorization references unavailable manifest entries")

        # 8. Verify published evidence membership
        membership_check = verify_published_evidence_membership(
            head=head,
            envelope=envelope,
            membership_witness=membership_witness,
            admitted_evidence_receipts=admitted_evidence_receipts,
            reference_time=issued_instant,
            permitted_truth_classes=permitted_truth_classes,
            action_class="EXACT_PRESCRIPTION",
        )

        # 9. Verify published uncertainty bounds
        verify_published_uncertainty_bounds(
            head=head,
            envelope=envelope,
            uncertainty_witness=uncertainty_witness,
            membership=membership_check,
        )

        # 10. Verify publication binding contract
        validate_published_pilot_envelope(
            envelope,
            canonical_head=head,
            tenant_id=namespace.tenant_id,
            farm_id=namespace.farm_id,
            plot_id=namespace.plot_id,
            geometry_hash=geometry_hash,
            crop_cycle_id=crop_cycle_id,
            now=issued_instant,
            verified_uncertainty_receipt_hash=head["bounded_uncertainty_receipt_hash"],
        )

        # 11. Register in durable ledger as AUTHORIZED
        record = self.ledger.register_authorized_prescription(
            namespace=namespace,
            geometry_hash=geometry_hash,
            crop_cycle_id=crop_cycle_id,
            envelope=envelope,
            now=issued_instant,
        )

        return envelope, record
