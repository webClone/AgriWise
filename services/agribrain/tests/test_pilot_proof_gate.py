"""Proof-root gates: trusted-head fixture controls, no issuance or public export.

A green fixture demonstrates only structural comparison. Real ASMAE heads
currently lack the two immutable proof roots and fail closed by design.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json

import pytest

from services.agribrain.scientific_contracts.exceptions import ContractViolation
from services.agribrain.scientific_contracts.evidence_receipt import create_evidence_receipt
from services.agribrain.scientific_contracts.prescription_authorization import (
    AuthorizedActionV1, PrescriptionAuthorizationEnvelopeV2, canonical_hash,
    CANONICAL_PUBLICATION_VALIDATION_FLAGS,
)
from services.agribrain.orchestrator_v2.pilot_proof_gate import (
    PilotProofCheck, verify_published_evidence_membership,
    verify_published_uncertainty_bounds,
)

SHA = lambda x: canonical_hash({"fixture": x})
SCOPE = dict(
    tenant_id="tenant-A", farm_id="farm-A", plot_id="6ab14f59ad442f274c3f2a62",
    geometry_hash=SHA("geometry"), crop_cycle_id="wheat-2026",
    snapshot_id="ASMAE-SNAPSHOT-structural-fixture",
)
TIMES = dict(
    evidence_cutoff_at="2026-10-30T17:44:46Z",
    observation_window_start="2026-10-29T00:00:00Z",
    observation_window_end="2026-10-30T16:00:00Z",
    published_at="2026-10-30T18:00:00Z",
    issued_at="2026-10-30T18:30:00Z",
    expires_at="2026-11-02T18:30:00Z",
)
NOW = "2026-10-31T15:00:00Z"
JOB = SHA("job-manifest")
PUBLICATION = SHA("publication")
POSTERIOR = SHA("asmae-actual-posterior")
CONTENT = SHA("real-evidence-payload")
CONTRIBUTION = "DC-accepted-1"
EVIDENCE_ID = "physical-evidence-1"


def fixture():
    action = AuthorizedActionV1(
        action_id="L8-1", action_type="IRRIGATE",
        priority_score=0.8, urgency_score=0.7, confidence="MODERATE",
        rationale="structural fixture only", rate={
            "recommended": 4.0, "min_safe": 3.0, "max_safe": 5.0, "unit": "mm",
        },
        timing={"earliest": "2026-11-01T16:00:00Z"},
        zone_targets=("plot",), requires_confirmation=True,
        machine_execution_allowed=False,
    )
    witness = {
        **SCOPE,
        "schema_version": "pilot_admitted_membership_v1",
        "publication_receipt_hash": PUBLICATION,
        "job_manifest_hash": JOB,
        "evidence_cutoff_at": TIMES["evidence_cutoff_at"],
        "input_belief_id": "belief-a",
        "tribunal_content_hash": SHA("tribunal"),
        "prescription_manifest_hash": SHA("L8-selected-contributions"),
        "accepted_contribution_ids": [CONTRIBUTION],
        "entries": [
            {"contribution_id": CONTRIBUTION, "evidence_id": EVIDENCE_ID,
             "evidence_content_hash": CONTENT}
        ],
    }
    witness["content_hash"] = canonical_hash(witness)
    bounded = {
        **SCOPE,
        "schema_version": "pilot_bounded_uncertainty_v1",
        "publication_receipt_hash": PUBLICATION,
        "job_manifest_hash": JOB,
        "evidence_cutoff_at": TIMES["evidence_cutoff_at"],
        "admitted_evidence_root_hash": witness["content_hash"],
        "source_posterior_hash": POSTERIOR,
        "actions": [
            {"action_id": action.action_id, "zone_targets": ["plot"],
             "timing": dict(action.timing), "min_safe": 2.0, "max_safe": 6.0,
             "unit": "mm"}
        ],
    }
    bounded["content_hash"] = canonical_hash(bounded)
    envelope = PrescriptionAuthorizationEnvelopeV2(
        input_belief_id="belief-a",
        tribunal_content_hash=SHA("tribunal"),
        prescription_manifest_hash=SHA("L8-selected-contributions"),
        prescription_manifest_entry_ids=(CONTRIBUTION,),
        policy_snapshot_hash=SHA("policy"),
        l8_run_id="l8-1",
        l8_content_hash=SHA("l8-result"),
        final_execution_plan_hash=SHA("plan"),
        actions=(action,),
        **SCOPE, **TIMES,
        canonical_publication_receipt_hash=PUBLICATION,
        evidence_manifest_hash=JOB,
        uncertainty_receipt_hash=bounded["content_hash"],
    )
    head = {
        "available": True, "snapshot_kind": "asmae", **SCOPE,
        "publication_receipt_hash": PUBLICATION,
        "manifest_hash": JOB, "evidence_cutoff_at": TIMES["evidence_cutoff_at"],
        "validation": {key: True for key in CANONICAL_PUBLICATION_VALIDATION_FLAGS},
        "admitted_evidence_root_hash": witness["content_hash"],
        "bounded_uncertainty_receipt_hash": bounded["content_hash"],
        "scientific_posterior_hash": POSTERIOR,
    }
    receipt = create_evidence_receipt(
        contribution_id=CONTRIBUTION,
        evidence_ids=[EVIDENCE_ID],
        content_hashes=[CONTENT],
        calibration_certificate_id="calibration-1",
        spatial_support={"geometry_hash": SCOPE["geometry_hash"]},
        observation_timestamp=datetime(2026, 10, 30, 12, tzinfo=timezone.utc),
        validity_interval=(
            datetime(2026, 10, 30, 12, tzinfo=timezone.utc),
            datetime(2026, 11, 2, 12, tzinfo=timezone.utc),
        ),
        freshness_expiry=datetime(2026, 11, 2, 12, tzinfo=timezone.utc),
        truth_class="CALIBRATED_PHYSICAL_MEASUREMENT",
        originating_stage_receipt_id="stage-certified-1",
        action_classes_allowed=["EXACT_PRESCRIPTION"],
    )
    receipts = {CONTRIBUTION: receipt}
    return head, envelope, witness, receipts, bounded


def membership(head, envelope, witness, receipts):
    return verify_published_evidence_membership(
        head=head, envelope=envelope, membership_witness=witness,
        admitted_evidence_receipts=receipts, reference_time=NOW,
        permitted_truth_classes=("CALIBRATED_PHYSICAL_MEASUREMENT",),
        action_class="EXACT_PRESCRIPTION",
    )


def test_synthetic_published_roots_match_structurally_not_authorize():
    h, e, w, receipts, u = fixture()
    m = membership(h, e, w, receipts)
    assert m.status == "STRUCTURAL_MATCH_ONLY" and m.checked_entries == 1
    result = verify_published_uncertainty_bounds(
        head=h, envelope=e, uncertainty_witness=u, membership=m,
    )
    assert result.status == "STRUCTURAL_MATCH_ONLY"
    assert not hasattr(result, "authorized_actions")
    assert not hasattr(result, "signature")


@pytest.mark.parametrize("root", ["admitted_evidence_root_hash", "bounded_uncertainty_receipt_hash", "scientific_posterior_hash"])
def test_actual_head_without_new_authenticated_roots_fails_closed(root):
    h, e, w, receipts, u = fixture()
    h.pop(root)
    if root == "admitted_evidence_root_hash":
        with pytest.raises(ContractViolation):
            membership(h, e, w, receipts)
    else:
        m = membership(h, e, w, receipts)
        with pytest.raises(ContractViolation):
            verify_published_uncertainty_bounds(head=h, envelope=e, uncertainty_witness=u, membership=m)


@pytest.mark.parametrize("changed", [
    "foreign_plot", "foreign_geometry", "wrong_snapshot", "mismatched_receipt",
    "unpublished_root", "wrong_tribunal", "foreign_evidence_id",
    "changed_digest", "late_evidence", "uncalibrated", "wrong_truth_class",
    "missing_calibration", "missing_stage_receipt", "stale",
    "missing_selected_evidence", "missing_policy", "json_receipt",
])
def test_membership_adversarial_cases_fail_closed(changed):
    h, e, w, receipts, u = fixture()
    if changed == "foreign_plot":
        h["plot_id"] = "foreign"
    elif changed == "foreign_geometry":
        w["geometry_hash"] = SHA("other")
    elif changed == "wrong_snapshot":
        w["snapshot_id"] = "ASMAE-SNAPSHOT-wrong"
    elif changed == "mismatched_receipt":
        h["publication_receipt_hash"] = SHA("swapped-publication")
    elif changed == "unpublished_root":
        h["admitted_evidence_root_hash"] = SHA("unpublished")
    elif changed == "wrong_tribunal":
        w["tribunal_content_hash"] = SHA("wrong")
    elif changed == "foreign_evidence_id":
        w["entries"][0]["evidence_id"] = "neighbor-reading"
    elif changed == "changed_digest":
        w["entries"][0]["evidence_content_hash"] = SHA("changed-reading")
    elif changed == "late_evidence":
        receipts[CONTRIBUTION] = replace(
            receipts[CONTRIBUTION],
            observation_timestamp=datetime(2026, 10, 30, 22, tzinfo=timezone.utc),
        )
    elif changed == "uncalibrated":
        receipts[CONTRIBUTION] = replace(receipts[CONTRIBUTION], calibration_valid=False)
    elif changed == "wrong_truth_class":
        receipts[CONTRIBUTION] = replace(receipts[CONTRIBUTION], truth_class="LIVE_UNCERTIFIED")
    elif changed == "missing_calibration":
        receipts[CONTRIBUTION] = replace(receipts[CONTRIBUTION], calibration_certificate_id=None)
    elif changed == "missing_stage_receipt":
        receipts[CONTRIBUTION] = replace(receipts[CONTRIBUTION], originating_stage_receipt_id="")
    elif changed == "stale":
        receipts[CONTRIBUTION] = replace(
            receipts[CONTRIBUTION],
            freshness_expiry=datetime(2026, 10, 31, 14, tzinfo=timezone.utc),
        )
    elif changed == "missing_selected_evidence":
        receipts.clear()
    elif changed == "missing_policy":
        with pytest.raises(ContractViolation):
            verify_published_evidence_membership(
                head=h, envelope=e, membership_witness=w,
                admitted_evidence_receipts=receipts, reference_time=NOW,
                permitted_truth_classes=(), action_class="EXACT_PRESCRIPTION",
            )
        return
    elif changed == "json_receipt":
        receipts[CONTRIBUTION] = receipts[CONTRIBUTION].to_dict()
    with pytest.raises(ContractViolation):
        membership(h, e, w, receipts)


@pytest.mark.parametrize("changed", [
    "altered_action", "altered_zone", "altered_timing", "wrong_unit",
    "narrow_bounds", "nonfinite_bounds", "wrong_posterior", "wrong_membership",
    "wrong_uncertainty_root", "missing_action", "foreign_plot",
])
def test_uncertainty_adversarial_cases_fail_closed(changed):
    h, e, w, receipts, u = fixture()
    m = membership(h, e, w, receipts)
    if changed == "altered_action":
        u["actions"][0]["action_id"] = "different"
    elif changed == "altered_zone":
        u["actions"][0]["zone_targets"] = ["neighbor"]
    elif changed == "altered_timing":
        u["actions"][0]["timing"]["earliest"] = "2026-11-02T00:00:00Z"
    elif changed == "wrong_unit":
        u["actions"][0]["unit"] = "kg/ha"
    elif changed == "narrow_bounds":
        u["actions"][0]["max_safe"] = 4.0
    elif changed == "nonfinite_bounds":
        u["actions"][0]["max_safe"] = float("nan")
    elif changed == "wrong_posterior":
        u["source_posterior_hash"] = SHA("not-ASMAE")
    elif changed == "wrong_membership":
        u["admitted_evidence_root_hash"] = SHA("unrelated-membership")
    elif changed == "wrong_uncertainty_root":
        h["bounded_uncertainty_receipt_hash"] = SHA("old-uncertainty")
    elif changed == "missing_action":
        u["actions"] = []
    elif changed == "foreign_plot":
        u["plot_id"] = "foreign"
    with pytest.raises(ContractViolation):
        verify_published_uncertainty_bounds(
            head=h, envelope=e, uncertainty_witness=u, membership=m,
        )


def test_fake_membership_result_cannot_substitute_for_current_publication_root():
    h, e, w, receipts, u = fixture()
    forged = PilotProofCheck(
        kind="ADMITTED_MEMBERSHIP", status="STRUCTURAL_MATCH_ONLY",
        claimed_root=SHA("fake"), checked_entries=999,
    )
    with pytest.raises(ContractViolation, match="anchored"):
        verify_published_uncertainty_bounds(
            head=h, envelope=e, uncertainty_witness=u, membership=forged,
        )
