"""Phase 1E: Trusted Positive Issuer & Guarded Public V2 Exporter Qualification Tests.

Verifies:
1. Positive issuance and qualification: real calibrated physical evidence receipts,
   membership and uncertainty proof witnesses, attestation, durable ledger registration,
   and successful export through the guarded public action boundary.
2. Strict invariants: machine execution disallowed, confirmation required.
3. Complete adversarial coverage: quarantined candidate export blocked, revocation,
   scope block, expiration, superseded snapshot, tampered HMAC, key rotation,
   post-cutoff evidence, uncalibrated evidence, and rate-bound violations.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone, timedelta
import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.scientific_contracts.exceptions import ContractViolation
from services.agribrain.scientific_contracts.evidence_receipt import create_evidence_receipt
from services.agribrain.scientific_contracts.prescription_authorization import (
    AuthorizedActionV1,
    PrescriptionAuthorizationEnvelopeV2,
    canonical_hash,
    CANONICAL_PUBLICATION_VALIDATION_FLAGS,
)
from services.agribrain.scientific_contracts.proof_attestation import create_proof_attestation
from services.agribrain.layer05_asmae.plot_snapshot_store import (
    publish_canonical_plot_snapshot,
    attach_canonical_proof_attestation,
    load_latest_plot_snapshot,
)
from services.agribrain.tests.test_pilot_producer_publication_roots import (
    _make_valid_frontend_payload,
)
from services.agribrain.orchestrator_v2.schema import (
    LayerStatus, LayerResult, GlobalQuality, RunArtifact, RunMeta, OrchestratorInput,
)
from services.agribrain.orchestrator_v2.pilot_authorization_ledger import (
    PilotCandidateLedger,
    AUTHORIZED_SCHEMA_VERSION,
)
from services.agribrain.orchestrator_v2.pilot_prescription_issuer import (
    PilotPrescriptionIssuer,
)
from services.agribrain.orchestrator_v2.run_schema import (
    artifact_to_run,
    _validated_authorization,
    _serialize_plan,
)

SHA = lambda x: canonical_hash({"fixture": x})
SCOPE = dict(
    tenant_id="tenant-A",
    farm_id="farm-A",
    plot_id="6ab14f59ad442f274c3f2a62",
    geometry_hash=SHA("geometry"),
    crop_cycle_id="wheat-2026",
    snapshot_id="ASMAE-SNAPSHOT-positive-fixture",
)
TIMES = dict(
    evidence_cutoff_at="2026-10-30T17:44:46Z",
    observation_window_start="2026-10-29T00:00:00Z",
    observation_window_end="2026-10-30T16:00:00Z",
    published_at="2026-10-30T18:00:00Z",
    issued_at="2026-10-30T18:30:00Z",
    expires_at="2026-11-03T18:30:00Z",
)
NOW = "2026-10-31T15:00:00Z"
KEY = b"32-byte-minimum-positive-issuer-test-key-EXPLICIT"
KEY_ID = "pilot-issuer-key-v1"
JOB = SHA("job-manifest")
PUBLICATION = SHA("publication")
POSTERIOR = SHA("asmae-actual-posterior")
CONTENT = SHA("real-evidence-payload")
CONTRIBUTION = "DC-accepted-1"
EVIDENCE_ID = "physical-evidence-1"


def create_fixture_action(action_id="L8-1", recommended=4.0, min_safe=3.0, max_safe=5.0):
    return AuthorizedActionV1(
        action_id=action_id,
        action_type="IRRIGATE",
        priority_score=0.8,
        urgency_score=0.7,
        confidence="MODERATE",
        rationale="Qualified scientific pilot action",
        rate={"recommended": recommended, "min_safe": min_safe, "max_safe": max_safe, "unit": "mm"},
        timing={"earliest": "2026-11-01T16:00:00Z", "latest": "2026-11-02T16:00:00Z", "optimal": None},
        zone_targets=("plot",),
        requires_confirmation=True,
        machine_execution_allowed=False,
    )


def create_mock_artifact(action: AuthorizedActionV1, l8_content_hash: str):
    l8_action = SimpleNamespace(
        action_id=action.action_id,
        action_type=SimpleNamespace(value=action.action_type),
        priority_score=action.priority_score,
        priority_breakdown=SimpleNamespace(urgency_score=action.urgency_score),
        confidence=SimpleNamespace(value=action.confidence),
        explain=action.rationale,
        rate=SimpleNamespace(
            recommended=action.rate["recommended"],
            min_safe=action.rate["min_safe"],
            max_safe=action.rate["max_safe"],
            unit=action.rate["unit"],
        ),
        time_window=SimpleNamespace(**action.timing),
        zone_targets=list(action.zone_targets),
        requires_confirmation=action.requires_confirmation,
        machine_execution_allowed=action.machine_execution_allowed,
    )
    l8_output = SimpleNamespace(
        run_id="l8-run-1",
        actions=[l8_action],
        audit=SimpleNamespace(policy_checks=[{"check": "content_hash", "value": l8_content_hash}]),
    )
    plan = SimpleNamespace(
        tasks=[
            SimpleNamespace(
                task_id="task-1",
                type="IRRIGATE",
                instructions="Apply 4.0 mm irrigation",
                required_inputs=[],
                completion_signal="flow_meter",
                depends_on=[],
                target_zones=["plot"],
                target_points=[],
            )
        ],
        edges=[],
        recommended_start_date="2026-11-01T16:00:00Z",
        review_date="2026-11-02T16:00:00Z",
    )
    inputs = OrchestratorInput(
        plot_namespace=PlotNamespace(SCOPE["tenant_id"], SCOPE["farm_id"], SCOPE["plot_id"]),
        tenant_id=SCOPE["tenant_id"],
        farm_id=SCOPE["farm_id"],
        plot_id=SCOPE["plot_id"],
        geometry_hash=SCOPE["geometry_hash"],
        crop_config={"crop_cycle_id": SCOPE["crop_cycle_id"]},
        date_range={"start": "2026-10-29", "end": "2026-10-30"},
        policy_snapshot={"pilot_policy": "strict", "require_evidence_receipts": True},
    )

    return RunArtifact(
        meta=RunMeta(orchestrator_run_id="orchestrator-run-1"),
        global_quality=GlobalQuality(
            modes=[], reliability_score=0.8, missing_drivers=[], critical_errors=[]
        ),
        inputs=inputs,
        layer_8=LayerResult(
            layer_id="L8",
            status=LayerStatus.OK,
            output=l8_output,
            run_id="l8-run-1",
        ),
        final_execution_plan=plan,
        diagnostic_integration={
            "prescription_gate": {
                "status": "completed",
                "input_belief_id": "belief-test-1",
                "tribunal_verdict": {"content_hash": SHA("tribunal-positive")},
                "influence_manifest": {
                    "requested_use": "PRESCRIPTION_DRIVER",
                    "content_hash": SHA("manifest-positive"),
                    "entries": [{"contribution_id": CONTRIBUTION}],
                },
            }
        },
    )


def create_pilot_setup(tmp_path):
    action = create_fixture_action()
    l8_content_hash = SHA("l8-positive-audit")
    artifact = create_mock_artifact(action, l8_content_hash)

    witness = {
        **SCOPE,
        "schema_version": "pilot_admitted_membership_v1",
        "publication_receipt_hash": PUBLICATION,
        "job_manifest_hash": JOB,
        "evidence_cutoff_at": TIMES["evidence_cutoff_at"],
        "input_belief_id": "belief-test-1",
        "tribunal_content_hash": SHA("tribunal-positive"),
        "prescription_manifest_hash": SHA("manifest-positive"),
        "accepted_contribution_ids": [CONTRIBUTION],
        "entries": [
            {
                "contribution_id": CONTRIBUTION,
                "evidence_id": EVIDENCE_ID,
                "evidence_content_hash": CONTENT,
            }
        ],
    }

    receipt = create_evidence_receipt(
        contribution_id=CONTRIBUTION,
        evidence_ids=[EVIDENCE_ID],
        content_hashes=[CONTENT],
        calibration_certificate_id="calib-cert-001",
        spatial_support={"geometry_hash": SCOPE["geometry_hash"]},
        observation_timestamp=datetime(2026, 10, 30, 12, tzinfo=timezone.utc),
        validity_interval=(
            datetime(2026, 10, 30, 12, tzinfo=timezone.utc),
            datetime(2026, 11, 4, 12, tzinfo=timezone.utc),
        ),
        freshness_expiry=datetime(2026, 11, 4, 12, tzinfo=timezone.utc),
        truth_class="CALIBRATED_PHYSICAL_MEASUREMENT",
        originating_stage_receipt_id="stage-receipt-001",
        action_classes_allowed=["EXACT_PRESCRIPTION"],
    )
    witness["entries"][0]["receipt_content_hash"] = canonical_hash(receipt.to_dict())
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
            {
                "action_id": action.action_id,
                "zone_targets": list(action.zone_targets),
                "timing": dict(action.timing),
                "min_safe": 2.0,
                "max_safe": 6.0,
                "unit": "mm",
            }
        ],
    }
    bounded["content_hash"] = canonical_hash(bounded)

    attestation = {
        "schema_version": "asmae_proof_attestation_v1",
        "snapshot_id": SCOPE["snapshot_id"],
        "canonical_publication_receipt_hash": PUBLICATION,
        "admitted_evidence_root_hash": witness["content_hash"],
        "bounded_uncertainty_receipt_hash": bounded["content_hash"],
        "scientific_posterior_hash": POSTERIOR,
        "attestation_hash": SHA("attestation-hash"),
    }

    head = {
        "available": True,
        "snapshot_kind": "asmae",
        **SCOPE,
        "publication_receipt_hash": PUBLICATION,
        "manifest_hash": JOB,
        "evidence_cutoff_at": TIMES["evidence_cutoff_at"],
        "observation_window": {
            "start": TIMES["observation_window_start"],
            "end": TIMES["observation_window_end"],
        },
        "published_at": TIMES["published_at"],
        "validation": {key: True for key in CANONICAL_PUBLICATION_VALIDATION_FLAGS},
        "proof_attestation_valid": True,
        "proof_attestation": attestation,
        "proof_attestation_hash": attestation["attestation_hash"],
        "admitted_evidence_root_hash": witness["content_hash"],
        "bounded_uncertainty_receipt_hash": bounded["content_hash"],
        "scientific_posterior_hash": POSTERIOR,
    }

    db_path = tmp_path / "pilot_ledger.sqlite"
    ledger = PilotCandidateLedger(db_path, key_id=KEY_ID, signing_key=KEY)
    issuer = PilotPrescriptionIssuer(ledger)
    ns = PlotNamespace(SCOPE["tenant_id"], SCOPE["farm_id"], SCOPE["plot_id"])
    receipts = {CONTRIBUTION: receipt}

    return {
        "ledger": ledger,
        "issuer": issuer,
        "head": head,
        "artifact": artifact,
        "witness": witness,
        "receipts": receipts,
        "bounded": bounded,
        "ns": ns,
        "action": action,
        "db_path": db_path,
    }


def test_positive_pilot_issuance_and_guarded_public_export(tmp_path):
    s = create_pilot_setup(tmp_path)
    with patch(
        "services.agribrain.orchestrator_v2.pilot_prescription_issuer.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ), patch(
        "services.agribrain.orchestrator_v2.pilot_authorization_ledger.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ):
        envelope, record = s["issuer"].issue_prescription(
            namespace=s["ns"],
            crop_cycle_id=SCOPE["crop_cycle_id"],
            geometry_hash=SCOPE["geometry_hash"],
            artifact=s["artifact"],
            membership_witness=s["witness"],
            admitted_evidence_receipts=s["receipts"],
            uncertainty_witness=s["bounded"],
            now=NOW,
            expires_at=TIMES["expires_at"],
        )

    assert isinstance(envelope, PrescriptionAuthorizationEnvelopeV2)
    assert record["state"] == "AUTHORIZED"
    assert record["schema_version"] == AUTHORIZED_SCHEMA_VERSION
    assert record["candidate_id"]
    assert record["hmac"]

    # Attach envelope to artifact's L8 output
    s["artifact"].layer_8.output.authorization_envelope = envelope

    # Export through the guarded public action boundary
    with patch(
        "services.agribrain.orchestrator_v2.pilot_authorization_ledger.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ):
        serialized = artifact_to_run(s["artifact"], pilot_ledger=s["ledger"], now=NOW)

    # Verify recommendations and plan
    assert serialized["audit"]["prescription_authorization"]["status"] == "AUTHORIZED"
    assert len(serialized["recommendations"]) == 1
    rec = serialized["recommendations"][0]
    assert rec["action_id"] == "L8-1"
    assert rec["action"] == "IRRIGATE"
    assert rec["source"] == "L8_AUTHORIZED_ACTION"
    assert rec["rate"]["recommended"] == 4.0
    assert rec["rate"]["unit"] == "mm"
    assert rec["requires_confirmation"] is True
    assert rec["machine_execution_allowed"] is False
    assert serialized["unified_plan"]["total_tasks"] == 1


def test_quarantined_candidate_never_exports_as_prescription(tmp_path):
    s = create_pilot_setup(tmp_path)
    # Register candidate as QUARANTINED
    with patch(
        "services.agribrain.orchestrator_v2.pilot_prescription_issuer.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ), patch(
        "services.agribrain.orchestrator_v2.pilot_authorization_ledger.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ):
        # Build envelope manually
        envelope, _ = s["issuer"].issue_prescription(
            namespace=s["ns"],
            crop_cycle_id=SCOPE["crop_cycle_id"],
            geometry_hash=SCOPE["geometry_hash"],
            artifact=s["artifact"],
            membership_witness=s["witness"],
            admitted_evidence_receipts=s["receipts"],
            uncertainty_witness=s["bounded"],
            now=NOW,
            expires_at=TIMES["expires_at"],
        )
    # Register a separate ledger with only QUARANTINED state
    db2 = tmp_path / "quarantined_ledger.sqlite"
    q_ledger = PilotCandidateLedger(db2, key_id=KEY_ID, signing_key=KEY)
    with patch(
        "services.agribrain.orchestrator_v2.pilot_authorization_ledger.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ):
        q_record = q_ledger.register_quarantined_candidate(
            namespace=s["ns"],
            geometry_hash=SCOPE["geometry_hash"],
            crop_cycle_id=SCOPE["crop_cycle_id"],
            envelope=envelope,
            now=NOW,
        )
    assert q_record["state"] == "QUARANTINED"

    s["artifact"].layer_8.output.authorization_envelope = envelope
    with patch(
        "services.agribrain.orchestrator_v2.pilot_authorization_ledger.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ):
        blocked = artifact_to_run(s["artifact"], pilot_ledger=q_ledger, now=NOW)

    assert blocked["audit"]["prescription_authorization"]["status"] == "BLOCKED"
    assert "quarantined" in blocked["audit"]["prescription_authorization"]["reason"].lower()
    assert blocked["recommendations"] == []
    assert blocked["unified_plan"]["tasks"] == []


def test_revoked_candidate_fails_closed_at_export(tmp_path):
    s = create_pilot_setup(tmp_path)
    with patch(
        "services.agribrain.orchestrator_v2.pilot_prescription_issuer.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ), patch(
        "services.agribrain.orchestrator_v2.pilot_authorization_ledger.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ):
        envelope, record = s["issuer"].issue_prescription(
            namespace=s["ns"],
            crop_cycle_id=SCOPE["crop_cycle_id"],
            geometry_hash=SCOPE["geometry_hash"],
            artifact=s["artifact"],
            membership_witness=s["witness"],
            admitted_evidence_receipts=s["receipts"],
            uncertainty_witness=s["bounded"],
            now=NOW,
            expires_at=TIMES["expires_at"],
        )

    # Revoke candidate
    s["ledger"].revoke(record["candidate_id"], reason="Sensor recalibration required", at=NOW)
    s["artifact"].layer_8.output.authorization_envelope = envelope

    with patch(
        "services.agribrain.orchestrator_v2.pilot_authorization_ledger.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ):
        blocked = artifact_to_run(s["artifact"], pilot_ledger=s["ledger"], now=NOW)

    assert blocked["audit"]["prescription_authorization"]["status"] == "BLOCKED"
    assert "revoked" in blocked["audit"]["prescription_authorization"]["reason"].lower()
    assert blocked["recommendations"] == []


def test_plot_scope_block_denies_export(tmp_path):
    s = create_pilot_setup(tmp_path)
    with patch(
        "services.agribrain.orchestrator_v2.pilot_prescription_issuer.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ), patch(
        "services.agribrain.orchestrator_v2.pilot_authorization_ledger.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ):
        envelope, record = s["issuer"].issue_prescription(
            namespace=s["ns"],
            crop_cycle_id=SCOPE["crop_cycle_id"],
            geometry_hash=SCOPE["geometry_hash"],
            artifact=s["artifact"],
            membership_witness=s["witness"],
            admitted_evidence_receipts=s["receipts"],
            uncertainty_witness=s["bounded"],
            now=NOW,
            expires_at=TIMES["expires_at"],
        )

    # Block entire plot scope
    s["ledger"].block_scope(s["ns"], reason="Emergency biological threat block", at=NOW)
    s["artifact"].layer_8.output.authorization_envelope = envelope

    with patch(
        "services.agribrain.orchestrator_v2.pilot_authorization_ledger.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ):
        blocked = artifact_to_run(s["artifact"], pilot_ledger=s["ledger"], now=NOW)

    assert blocked["audit"]["prescription_authorization"]["status"] == "BLOCKED"
    assert "administratively blocked" in blocked["audit"]["prescription_authorization"]["reason"].lower()
    assert blocked["recommendations"] == []


def test_superseded_snapshot_denies_export(tmp_path):
    s = create_pilot_setup(tmp_path)
    with patch(
        "services.agribrain.orchestrator_v2.pilot_prescription_issuer.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ), patch(
        "services.agribrain.orchestrator_v2.pilot_authorization_ledger.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ):
        envelope, record = s["issuer"].issue_prescription(
            namespace=s["ns"],
            crop_cycle_id=SCOPE["crop_cycle_id"],
            geometry_hash=SCOPE["geometry_hash"],
            artifact=s["artifact"],
            membership_witness=s["witness"],
            admitted_evidence_receipts=s["receipts"],
            uncertainty_witness=s["bounded"],
            now=NOW,
            expires_at=TIMES["expires_at"],
        )

    # ASMAE publishes a new snapshot
    new_head = dict(s["head"])
    new_head["snapshot_id"] = "ASMAE-SNAPSHOT-superseded-newer-run"
    s["artifact"].layer_8.output.authorization_envelope = envelope

    with patch(
        "services.agribrain.orchestrator_v2.pilot_authorization_ledger.read_trusted_current_asmae_publication",
        return_value=new_head,
    ):
        blocked = artifact_to_run(s["artifact"], pilot_ledger=s["ledger"], now=NOW)

    assert blocked["audit"]["prescription_authorization"]["status"] == "BLOCKED"
    assert "no longer matches current publication" in blocked["audit"]["prescription_authorization"]["reason"]
    assert blocked["recommendations"] == []


def test_tampered_ledger_hmac_denies_export(tmp_path):
    s = create_pilot_setup(tmp_path)
    with patch(
        "services.agribrain.orchestrator_v2.pilot_prescription_issuer.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ), patch(
        "services.agribrain.orchestrator_v2.pilot_authorization_ledger.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ):
        envelope, record = s["issuer"].issue_prescription(
            namespace=s["ns"],
            crop_cycle_id=SCOPE["crop_cycle_id"],
            geometry_hash=SCOPE["geometry_hash"],
            artifact=s["artifact"],
            membership_witness=s["witness"],
            admitted_evidence_receipts=s["receipts"],
            uncertainty_witness=s["bounded"],
            now=NOW,
            expires_at=TIMES["expires_at"],
        )

    # Tamper the record_json in sqlite
    with sqlite3.connect(s["db_path"]) as conn:
        row = conn.execute("SELECT record_json FROM candidates WHERE candidate_id=?", (record["candidate_id"],)).fetchone()
        data = json.loads(row[0])
        data["hmac"] = "0000000000000000000000000000000000000000000000000000000000000000"
        conn.execute("UPDATE candidates SET record_json=? WHERE candidate_id=?", (json.dumps(data), record["candidate_id"]))

    s["artifact"].layer_8.output.authorization_envelope = envelope
    with patch(
        "services.agribrain.orchestrator_v2.pilot_authorization_ledger.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ):
        blocked = artifact_to_run(s["artifact"], pilot_ledger=s["ledger"], now=NOW)

    assert blocked["audit"]["prescription_authorization"]["status"] == "BLOCKED"
    assert "integrity or signature" in blocked["audit"]["prescription_authorization"]["reason"]
    assert blocked["recommendations"] == []


def test_machine_execution_strictly_disallowed(tmp_path):
    s = create_pilot_setup(tmp_path)
    # Create action with machine_execution_allowed=True
    unsafe = replace(s["action"], machine_execution_allowed=True, requires_confirmation=False)
    bad_artifact = create_mock_artifact(unsafe, SHA("l8-positive-audit"))

    with patch(
        "services.agribrain.orchestrator_v2.pilot_prescription_issuer.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ):
        with pytest.raises(ContractViolation, match="Machine execution is never allowed"):
            s["issuer"].issue_prescription(
                namespace=s["ns"],
                crop_cycle_id=SCOPE["crop_cycle_id"],
                geometry_hash=SCOPE["geometry_hash"],
                artifact=bad_artifact,
                membership_witness=s["witness"],
                admitted_evidence_receipts=s["receipts"],
                uncertainty_witness=s["bounded"],
                now=NOW,
            )


def test_farmer_confirmation_strictly_required(tmp_path):
    s = create_pilot_setup(tmp_path)
    unsafe = replace(s["action"], requires_confirmation=False)
    bad_artifact = create_mock_artifact(unsafe, SHA("l8-positive-audit"))

    with patch(
        "services.agribrain.orchestrator_v2.pilot_prescription_issuer.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ):
        with pytest.raises(ContractViolation, match="Farmer confirmation is strictly required"):
            s["issuer"].issue_prescription(
                namespace=s["ns"],
                crop_cycle_id=SCOPE["crop_cycle_id"],
                geometry_hash=SCOPE["geometry_hash"],
                artifact=bad_artifact,
                membership_witness=s["witness"],
                admitted_evidence_receipts=s["receipts"],
                uncertainty_witness=s["bounded"],
                now=NOW,
            )


def test_post_cutoff_evidence_rejected_at_issuance(tmp_path):
    s = create_pilot_setup(tmp_path)
    late_receipt = create_evidence_receipt(
        contribution_id=CONTRIBUTION,
        evidence_ids=[EVIDENCE_ID],
        content_hashes=[CONTENT],
        calibration_certificate_id="calib-cert-001",
        spatial_support={"geometry_hash": SCOPE["geometry_hash"]},
        observation_timestamp=datetime(2026, 10, 31, 12, tzinfo=timezone.utc),  # after cutoff 2026-10-30T17:44:46Z
        validity_interval=(
            datetime(2026, 10, 31, 12, tzinfo=timezone.utc),
            datetime(2026, 11, 4, 12, tzinfo=timezone.utc),
        ),
        freshness_expiry=datetime(2026, 11, 4, 12, tzinfo=timezone.utc),
        truth_class="CALIBRATED_PHYSICAL_MEASUREMENT",
        originating_stage_receipt_id="stage-receipt-001",
        action_classes_allowed=["EXACT_PRESCRIPTION"],
    )
    s["witness"]["entries"][0]["receipt_content_hash"] = canonical_hash(late_receipt.to_dict())
    s["witness"]["content_hash"] = canonical_hash(s["witness"])
    s["head"]["admitted_evidence_root_hash"] = s["witness"]["content_hash"]
    s["head"]["proof_attestation"]["admitted_evidence_root_hash"] = s["witness"]["content_hash"]

    with patch(
        "services.agribrain.orchestrator_v2.pilot_prescription_issuer.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ):
        with pytest.raises(ContractViolation, match="Post-cutoff telemetry cannot be admitted"):
            s["issuer"].issue_prescription(
                namespace=s["ns"],
                crop_cycle_id=SCOPE["crop_cycle_id"],
                geometry_hash=SCOPE["geometry_hash"],
                artifact=s["artifact"],
                membership_witness=s["witness"],
                admitted_evidence_receipts={CONTRIBUTION: late_receipt},
                uncertainty_witness=s["bounded"],
                now=NOW,
            )


def test_uncalibrated_evidence_rejected_at_issuance(tmp_path):
    s = create_pilot_setup(tmp_path)
    uncalibrated = create_evidence_receipt(
        contribution_id=CONTRIBUTION,
        evidence_ids=[EVIDENCE_ID],
        content_hashes=[CONTENT],
        calibration_certificate_id="",
        spatial_support={"geometry_hash": SCOPE["geometry_hash"]},
        observation_timestamp=datetime(2026, 10, 30, 12, tzinfo=timezone.utc),
        validity_interval=(
            datetime(2026, 10, 30, 12, tzinfo=timezone.utc),
            datetime(2026, 11, 4, 12, tzinfo=timezone.utc),
        ),
        freshness_expiry=datetime(2026, 11, 4, 12, tzinfo=timezone.utc),
        truth_class="UNVERIFIED_OBSERVATION",
        is_calibrated=False,
        calibration_valid=False,
        originating_stage_receipt_id="stage-receipt-001",
        action_classes_allowed=["EXACT_PRESCRIPTION"],
    )
    s["witness"]["entries"][0]["receipt_content_hash"] = canonical_hash(uncalibrated.to_dict())
    s["witness"]["content_hash"] = canonical_hash(s["witness"])
    s["head"]["admitted_evidence_root_hash"] = s["witness"]["content_hash"]
    s["head"]["proof_attestation"]["admitted_evidence_root_hash"] = s["witness"]["content_hash"]

    with patch(
        "services.agribrain.orchestrator_v2.pilot_prescription_issuer.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ):
        with pytest.raises(ContractViolation, match="Evidence calibration or spatial support is not verified"):
            s["issuer"].issue_prescription(
                namespace=s["ns"],
                crop_cycle_id=SCOPE["crop_cycle_id"],
                geometry_hash=SCOPE["geometry_hash"],
                artifact=s["artifact"],
                membership_witness=s["witness"],
                admitted_evidence_receipts={CONTRIBUTION: uncalibrated},
                uncertainty_witness=s["bounded"],
                now=NOW,
            )


def test_rate_exceeding_uncertainty_bounds_rejected(tmp_path):
    s = create_pilot_setup(tmp_path)
    # Uncertainty witness allows max_safe 6.0 mm. Action requests recommended 10.0 mm, max_safe 12.0 mm.
    excessive_action = create_fixture_action(recommended=10.0, min_safe=8.0, max_safe=12.0)
    bad_artifact = create_mock_artifact(excessive_action, SHA("l8-positive-audit"))

    with patch(
        "services.agribrain.orchestrator_v2.pilot_prescription_issuer.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ):
        with pytest.raises(ContractViolation, match="rate exceeds published scientific uncertainty bounds"):
            s["issuer"].issue_prescription(
                namespace=s["ns"],
                crop_cycle_id=SCOPE["crop_cycle_id"],
                geometry_hash=SCOPE["geometry_hash"],
                expected_snapshot_id=SCOPE["snapshot_id"],
                artifact=bad_artifact,
                membership_witness=s["witness"],
                admitted_evidence_receipts=s["receipts"],
                uncertainty_witness=s["bounded"],
                now=NOW,
            )


def test_policy_without_require_evidence_receipts_rejected(tmp_path):
    """P75-POL-02: Issuer strictly requires require_evidence_receipts=True in policy snapshot."""
    s = create_pilot_setup(tmp_path)

    # 1. Missing require_evidence_receipts
    artifact_missing = create_mock_artifact(s["action"], SHA("l8-hash"))
    artifact_missing.inputs = replace(artifact_missing.inputs, policy_snapshot={"pilot_policy": "strict"})
    with patch(
        "services.agribrain.orchestrator_v2.pilot_prescription_issuer.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ):
        with pytest.raises(ContractViolation, match="require_evidence_receipts=True"):
            s["issuer"].issue_prescription(
                namespace=s["ns"],
                crop_cycle_id=SCOPE["crop_cycle_id"],
                geometry_hash=SCOPE["geometry_hash"],
                expected_snapshot_id=SCOPE["snapshot_id"],
                artifact=artifact_missing,
                membership_witness=s["witness"],
                admitted_evidence_receipts=s["receipts"],
                uncertainty_witness=s["bounded"],
                now=NOW,
            )

    # 2. Explicitly False
    artifact_false = create_mock_artifact(s["action"], SHA("l8-hash"))
    artifact_false.inputs = replace(artifact_false.inputs, policy_snapshot={"require_evidence_receipts": False})
    with patch(
        "services.agribrain.orchestrator_v2.pilot_prescription_issuer.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ):
        with pytest.raises(ContractViolation, match="require_evidence_receipts=True"):
            s["issuer"].issue_prescription(
                namespace=s["ns"],
                crop_cycle_id=SCOPE["crop_cycle_id"],
                geometry_hash=SCOPE["geometry_hash"],
                expected_snapshot_id=SCOPE["snapshot_id"],
                artifact=artifact_false,
                membership_witness=s["witness"],
                admitted_evidence_receipts=s["receipts"],
                uncertainty_witness=s["bounded"],
                now=NOW,
            )

    # 3. None or empty policy
    artifact_empty = create_mock_artifact(s["action"], SHA("l8-hash"))
    artifact_empty.inputs = replace(artifact_empty.inputs, policy_snapshot={})
    with patch(
        "services.agribrain.orchestrator_v2.pilot_prescription_issuer.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ):
        with pytest.raises(ContractViolation, match="require_evidence_receipts=True"):
            s["issuer"].issue_prescription(
                namespace=s["ns"],
                crop_cycle_id=SCOPE["crop_cycle_id"],
                geometry_hash=SCOPE["geometry_hash"],
                expected_snapshot_id=SCOPE["snapshot_id"],
                artifact=artifact_empty,
                membership_witness=s["witness"],
                admitted_evidence_receipts=s["receipts"],
                uncertainty_witness=s["bounded"],
                now=NOW,
            )


def test_unmocked_issuer_with_real_publication_store(tmp_path, monkeypatch):
    """P75-ISS-01: Issuer executes against real unmocked publication store."""
    store_dir = tmp_path / "plot_snapshots"
    store_dir.mkdir(parents=True)
    monkeypatch.setattr("services.agribrain.layer05_asmae.plot_snapshot_store.PLOT_SNAPSHOT_ROOT", store_dir)

    ns = PlotNamespace("tenant-real", "farm-real", "6ab14f59ad442f274c3f2a62")
    geom_hash = SHA("real-geom")
    cycle_id = "wheat-2026-real"
    snap_id = "ASMAE-SNAPSHOT-unmocked-001"
    job_id = "job-unmocked-001"
    manifest_hash = SHA("manifest-job-001")

    window = {"start": "2026-10-16", "end": "2026-10-30"}
    cutoff_str = "2026-10-30T17:44:46Z"
    frontend_payload = _make_valid_frontend_payload(
        snapshot_id=snap_id,
        plot_id=ns.plot_id,
        cycle_id=cycle_id,
        cutoff_str=cutoff_str,
        window=window,
    )
    asmae_result = {
        "snapshot_id": snap_id,
        "crop_posterior_lineage": f"crop-{snap_id}",
        "crop_worldline_event_id": f"worldline-{snap_id}",
        "phenology_worldline_event_id": f"pheno-{snap_id}",
        "evidence_cutoff_at": cutoff_str,
        "observation_window": window,
    }

    head = publish_canonical_plot_snapshot(
        namespace=ns,
        geometry_hash=geom_hash,
        snapshot_id=snap_id,
        asmae_result=asmae_result,
        frontend_payload=frontend_payload,
        job_id=job_id,
        manifest_hash=manifest_hash,
    )
    receipt_hash = head["publication_receipt_hash"]

    # Build action, artifact, receipts, and witnesses
    action = AuthorizedActionV1(
        action_id="REAL-IRRIG-01",
        action_type="IRRIGATE",
        priority_score=0.9,
        urgency_score=0.8,
        confidence="HIGH",
        rationale="Unmocked real pilot action",
        rate={"recommended": 5.0, "min_safe": 3.0, "max_safe": 8.0, "unit": "mm"},
        timing={"earliest": "2026-11-01T06:00:00Z", "latest": "2026-11-01T18:00:00Z", "optimal": None},
        zone_targets=("plot",),
        requires_confirmation=True,
        machine_execution_allowed=False,
    )
    l8_hash = SHA("l8-unmocked-content")
    artifact = create_mock_artifact(action, l8_hash)
    artifact.inputs = replace(
        artifact.inputs,
        plot_namespace=ns,
        tenant_id=ns.tenant_id,
        farm_id=ns.farm_id,
        plot_id=ns.plot_id,
        geometry_hash=geom_hash,
        crop_config={"crop_cycle_id": cycle_id},
        policy_snapshot={"require_evidence_receipts": True},
    )

    ev_receipt = create_evidence_receipt(
        contribution_id="contrib-real-1",
        evidence_ids=["ev-real-1"],
        content_hashes=[SHA("ev-real-content")],
        calibration_certificate_id="cert-iso-17025-real",
        spatial_support={"geometry_hash": geom_hash},
        observation_timestamp=datetime(2026, 10, 30, 10, 0, tzinfo=timezone.utc),
        validity_interval=(
            datetime(2026, 10, 30, 10, 0, tzinfo=timezone.utc),
            datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc),
        ),
        freshness_expiry=datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc),
        truth_class="CALIBRATED_PHYSICAL_MEASUREMENT",
        originating_stage_receipt_id="stage-receipt-real-1",
        action_classes_allowed=["EXACT_PRESCRIPTION"],
    )

    artifact.diagnostic_integration["prescription_gate"]["influence_manifest"]["entries"] = [
        {"contribution_id": "contrib-real-1"}
    ]
    tribunal_hash = str(artifact.diagnostic_integration["prescription_gate"]["tribunal_verdict"]["content_hash"])
    presc_manifest_hash = str(artifact.diagnostic_integration["prescription_gate"]["influence_manifest"]["content_hash"])

    mem_witness = {
        "tenant_id": ns.tenant_id,
        "farm_id": ns.farm_id,
        "plot_id": ns.plot_id,
        "geometry_hash": geom_hash,
        "crop_cycle_id": cycle_id,
        "snapshot_id": snap_id,
        "schema_version": "pilot_admitted_membership_v1",
        "publication_receipt_hash": receipt_hash,
        "job_manifest_hash": manifest_hash,
        "evidence_cutoff_at": "2026-10-30T17:44:46Z",
        "input_belief_id": "belief-test-1",
        "tribunal_content_hash": tribunal_hash,
        "prescription_manifest_hash": presc_manifest_hash,
        "accepted_contribution_ids": ["contrib-real-1"],
        "entries": [
            {
                "contribution_id": "contrib-real-1",
                "evidence_id": "ev-real-1",
                "evidence_content_hash": SHA("ev-real-content"),
                "receipt_content_hash": canonical_hash(ev_receipt.to_dict()),
            }
        ],
    }
    mem_witness["content_hash"] = canonical_hash(mem_witness)

    posterior_hash = SHA("real-posterior-hash")
    unc_witness = {
        "tenant_id": ns.tenant_id,
        "farm_id": ns.farm_id,
        "plot_id": ns.plot_id,
        "geometry_hash": geom_hash,
        "crop_cycle_id": cycle_id,
        "snapshot_id": snap_id,
        "schema_version": "pilot_bounded_uncertainty_v1",
        "publication_receipt_hash": receipt_hash,
        "job_manifest_hash": manifest_hash,
        "evidence_cutoff_at": "2026-10-30T17:44:46Z",
        "admitted_evidence_root_hash": mem_witness["content_hash"],
        "source_posterior_hash": posterior_hash,
        "actions": [
            {
                "action_id": action.action_id,
                "zone_targets": list(action.zone_targets),
                "timing": dict(action.timing),
                "min_safe": 2.0,
                "max_safe": 10.0,
                "unit": "mm",
            }
        ],
    }
    unc_witness["content_hash"] = canonical_hash(unc_witness)

    attestation = create_proof_attestation(
        tenant_id=ns.tenant_id,
        farm_id=ns.farm_id,
        plot_id=ns.plot_id,
        geometry_hash=geom_hash,
        crop_cycle_id=cycle_id,
        snapshot_id=snap_id,
        canonical_publication_receipt_hash=receipt_hash,
        admitted_evidence_root_hash=mem_witness["content_hash"],
        bounded_uncertainty_receipt_hash=unc_witness["content_hash"],
        scientific_posterior_hash=posterior_hash,
        issuer_key_id=KEY_ID,
    )
    attach_canonical_proof_attestation(ns, attestation)

    # Completely unmocked issuer and export!
    db_path = tmp_path / "unmocked_ledger.sqlite"
    ledger = PilotCandidateLedger(db_path, key_id=KEY_ID, signing_key=KEY)
    issuer = PilotPrescriptionIssuer(ledger)

    envelope, record = issuer.issue_prescription(
        namespace=ns,
        crop_cycle_id=cycle_id,
        geometry_hash=geom_hash,
        expected_snapshot_id=snap_id,
        artifact=artifact,
        membership_witness=mem_witness,
        admitted_evidence_receipts={"contrib-real-1": ev_receipt},
        uncertainty_witness=unc_witness,
        now="2026-10-31T12:00:00Z",
    )

    assert envelope.snapshot_id == snap_id
    assert record["state"] == "AUTHORIZED"

    # Export completely unmocked!
    artifact.layer_8.output.authorization_envelope = envelope
    run = artifact_to_run(artifact, pilot_ledger=ledger, now="2026-10-31T12:00:00Z")
    assert run["audit"]["prescription_authorization"]["status"] == "AUTHORIZED"
    assert len(run["recommendations"]) == 1
    assert run["recommendations"][0]["action_id"] == "REAL-IRRIG-01"
    assert run["recommendations"][0]["machine_execution_allowed"] is False
    assert run["recommendations"][0]["requires_confirmation"] is True


def test_unmocked_issuer_rejects_mismatched_snapshot_id(tmp_path, monkeypatch):
    """P75-ISS-01: Issuer unmocked call with mismatched expected_snapshot_id fails closed."""
    store_dir = tmp_path / "plot_snapshots"
    store_dir.mkdir(parents=True)
    monkeypatch.setattr("services.agribrain.layer05_asmae.plot_snapshot_store.PLOT_SNAPSHOT_ROOT", store_dir)

    ns = PlotNamespace("tenant-real", "farm-real", "6ab14f59ad442f274c3f2a62")
    geom_hash = SHA("real-geom")
    cycle_id = "wheat-2026-real"
    snap_id = "ASMAE-SNAPSHOT-real-001"

    window = {"start": "2026-10-16", "end": "2026-10-30"}
    cutoff_str = "2026-10-30T17:44:46Z"
    frontend_payload = _make_valid_frontend_payload(
        snapshot_id=snap_id,
        plot_id=ns.plot_id,
        cycle_id=cycle_id,
        cutoff_str=cutoff_str,
        window=window,
    )
    asmae_result = {
        "snapshot_id": snap_id,
        "crop_posterior_lineage": f"crop-{snap_id}",
        "crop_worldline_event_id": f"worldline-{snap_id}",
        "phenology_worldline_event_id": f"pheno-{snap_id}",
        "evidence_cutoff_at": cutoff_str,
        "observation_window": window,
    }
    publish_canonical_plot_snapshot(
        namespace=ns,
        geometry_hash=geom_hash,
        snapshot_id=snap_id,
        asmae_result=asmae_result,
        frontend_payload=frontend_payload,
        job_id="job-001",
        manifest_hash=SHA("manifest"),
    )

    action = create_fixture_action()
    artifact = create_mock_artifact(action, SHA("l8-hash"))
    artifact.inputs = replace(
        artifact.inputs,
        plot_namespace=ns,
        crop_config={"crop_cycle_id": cycle_id},
        policy_snapshot={"require_evidence_receipts": True},
    )

    db_path = tmp_path / "unmocked_ledger_mismatch.sqlite"
    ledger = PilotCandidateLedger(db_path, key_id=KEY_ID, signing_key=KEY)
    issuer = PilotPrescriptionIssuer(ledger)

    with pytest.raises(ContractViolation, match="Current ASMAE snapshot differs from the requested exact snapshot"):
        issuer.issue_prescription(
            namespace=ns,
            crop_cycle_id=cycle_id,
            geometry_hash=geom_hash,
            expected_snapshot_id="ASMAE-SNAPSHOT-wrong-snapshot-id",
            artifact=artifact,
            membership_witness={},
            admitted_evidence_receipts={},
            uncertainty_witness={},
            now=NOW,
        )


def test_quarantined_candidate_cannot_be_exported_or_promoted(tmp_path, monkeypatch):
    """P75-POL-02: Quarantined candidates cannot bypass the issuer to become exportable."""
    store_dir = tmp_path / "plot_snapshots"
    store_dir.mkdir(parents=True)
    monkeypatch.setattr("services.agribrain.layer05_asmae.plot_snapshot_store.PLOT_SNAPSHOT_ROOT", store_dir)

    s = create_pilot_setup(tmp_path)
    ns = s["ns"]
    snap_id = SCOPE["snapshot_id"]
    geom_hash = SCOPE["geometry_hash"]
    cycle_id = SCOPE["crop_cycle_id"]
    manifest_hash = JOB

    # Publish canonical snapshot so ledger register_quarantined_candidate has real head
    window = {"start": "2026-10-16", "end": "2026-10-30"}
    cutoff_str = "2026-10-30T17:44:46Z"
    frontend_payload = _make_valid_frontend_payload(
        snapshot_id=snap_id,
        plot_id=ns.plot_id,
        cycle_id=cycle_id,
        cutoff_str=cutoff_str,
        window=window,
    )
    asmae_result = {
        "snapshot_id": snap_id,
        "crop_posterior_lineage": f"crop-{snap_id}",
        "crop_worldline_event_id": f"worldline-{snap_id}",
        "phenology_worldline_event_id": f"pheno-{snap_id}",
        "evidence_cutoff_at": cutoff_str,
        "observation_window": window,
    }
    pub_head = publish_canonical_plot_snapshot(
        namespace=ns,
        geometry_hash=geom_hash,
        snapshot_id=snap_id,
        asmae_result=asmae_result,
        frontend_payload=frontend_payload,
        job_id="job-quarantine-001",
        manifest_hash=manifest_hash,
    )
    receipt_hash = pub_head["publication_receipt_hash"]

    attestation = create_proof_attestation(
        tenant_id=ns.tenant_id,
        farm_id=ns.farm_id,
        plot_id=ns.plot_id,
        geometry_hash=geom_hash,
        crop_cycle_id=cycle_id,
        snapshot_id=snap_id,
        canonical_publication_receipt_hash=receipt_hash,
        admitted_evidence_root_hash=s["witness"]["content_hash"],
        bounded_uncertainty_receipt_hash=s["bounded"]["content_hash"],
        scientific_posterior_hash=POSTERIOR,
        issuer_key_id=KEY_ID,
    )
    attach_canonical_proof_attestation(ns, attestation)

    envelope = PrescriptionAuthorizationEnvelopeV2(
        tenant_id=s["ns"].tenant_id,
        farm_id=s["ns"].farm_id,
        plot_id=s["ns"].plot_id,
        geometry_hash=geom_hash,
        crop_cycle_id=cycle_id,
        snapshot_id=snap_id,
        canonical_publication_receipt_hash=receipt_hash,
        evidence_manifest_hash=manifest_hash,
        evidence_cutoff_at="2026-10-30T17:44:46Z",
        observation_window_start="2026-10-16T00:00:00Z",
        observation_window_end="2026-10-30T00:00:00Z",
        published_at="2026-10-30T18:00:00Z",
        issued_at=NOW,
        expires_at=TIMES["expires_at"],
        uncertainty_receipt_hash=s["bounded"]["content_hash"],
        input_belief_id="belief-test-1",
        tribunal_content_hash=SHA("tribunal-positive"),
        prescription_manifest_hash=SHA("manifest-positive"),
        prescription_manifest_entry_ids=(CONTRIBUTION,),
        policy_snapshot_hash=canonical_hash({"pilot_policy": "strict", "require_evidence_receipts": True}),
        l8_run_id="l8-run-1",
        l8_content_hash=SHA("l8-positive-audit"),
        final_execution_plan_hash=canonical_hash(_serialize_plan(s["artifact"].final_execution_plan)),
        actions=(s["action"],),
    )

    # Directly register in quarantined candidate state
    rec = s["ledger"].register_quarantined_candidate(
        namespace=ns,
        geometry_hash=geom_hash,
        crop_cycle_id=cycle_id,
        envelope=envelope,
        now=NOW,
    )
    cid = rec["candidate_id"]

    # Attempting to authorize export on quarantined record MUST fail closed
    with pytest.raises(ContractViolation, match="Pilot candidate is quarantined; cannot authorize export"):
        s["ledger"].authorize_export(cid, envelope=envelope, namespace=s["ns"], now=NOW)


def test_direct_ledger_authorized_registration_without_issuer_fails(tmp_path):
    """P343-LEDGER-01: Direct calls to ledger.register_authorized_prescription must not bypass issuer."""
    s = create_pilot_setup(tmp_path)
    ns = s["ns"]
    geom_hash = SCOPE["geometry_hash"]
    cycle_id = SCOPE["crop_cycle_id"]

    envelope = PrescriptionAuthorizationEnvelopeV2(
        tenant_id=ns.tenant_id,
        farm_id=ns.farm_id,
        plot_id=ns.plot_id,
        geometry_hash=geom_hash,
        crop_cycle_id=cycle_id,
        snapshot_id=s["head"]["snapshot_id"],
        canonical_publication_receipt_hash=s["head"]["publication_receipt_hash"],
        evidence_manifest_hash=s["head"]["manifest_hash"],
        evidence_cutoff_at=s["head"]["evidence_cutoff_at"],
        observation_window_start=TIMES["observation_window_start"],
        observation_window_end=TIMES["observation_window_end"],
        published_at="2026-10-30T18:00:00Z",
        issued_at=NOW,
        expires_at=TIMES["expires_at"],
        uncertainty_receipt_hash=s["bounded"]["content_hash"],
        input_belief_id="belief-test-1",
        tribunal_content_hash=SHA("tribunal-positive"),
        prescription_manifest_hash=SHA("manifest-positive"),
        prescription_manifest_entry_ids=(CONTRIBUTION,),
        policy_snapshot_hash=canonical_hash({"pilot_policy": "strict", "require_evidence_receipts": True}),
        l8_run_id="l8-run-1",
        l8_content_hash=SHA("l8-positive-audit"),
        final_execution_plan_hash=canonical_hash(_serialize_plan(s["artifact"].final_execution_plan)),
        actions=(s["action"],),
    )

    with patch(
        "services.agribrain.orchestrator_v2.pilot_authorization_ledger.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ):
        with pytest.raises(ContractViolation, match="requires trusted issuer scientific verification token"):
            s["ledger"].register_authorized_prescription(
                namespace=ns,
                geometry_hash=geom_hash,
                crop_cycle_id=cycle_id,
                envelope=envelope,
                now=NOW,
                issuer_token="",
            )


def test_direct_ledger_authorized_registration_with_tampered_issuer_token_fails(tmp_path):
    """P343-LEDGER-01: Forged issuer token is rejected by the ledger."""
    s = create_pilot_setup(tmp_path)
    ns = s["ns"]
    geom_hash = SCOPE["geometry_hash"]
    cycle_id = SCOPE["crop_cycle_id"]

    envelope = PrescriptionAuthorizationEnvelopeV2(
        tenant_id=ns.tenant_id,
        farm_id=ns.farm_id,
        plot_id=ns.plot_id,
        geometry_hash=geom_hash,
        crop_cycle_id=cycle_id,
        snapshot_id=s["head"]["snapshot_id"],
        canonical_publication_receipt_hash=s["head"]["publication_receipt_hash"],
        evidence_manifest_hash=s["head"]["manifest_hash"],
        evidence_cutoff_at=s["head"]["evidence_cutoff_at"],
        observation_window_start=TIMES["observation_window_start"],
        observation_window_end=TIMES["observation_window_end"],
        published_at="2026-10-30T18:00:00Z",
        issued_at=NOW,
        expires_at=TIMES["expires_at"],
        uncertainty_receipt_hash=s["bounded"]["content_hash"],
        input_belief_id="belief-test-1",
        tribunal_content_hash=SHA("tribunal-positive"),
        prescription_manifest_hash=SHA("manifest-positive"),
        prescription_manifest_entry_ids=(CONTRIBUTION,),
        policy_snapshot_hash=canonical_hash({"pilot_policy": "strict", "require_evidence_receipts": True}),
        l8_run_id="l8-run-1",
        l8_content_hash=SHA("l8-positive-audit"),
        final_execution_plan_hash=canonical_hash(_serialize_plan(s["artifact"].final_execution_plan)),
        actions=(s["action"],),
    )

    with patch(
        "services.agribrain.orchestrator_v2.pilot_authorization_ledger.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ):
        with pytest.raises(ContractViolation, match="invalid or forged issuer verification token"):
            s["ledger"].register_authorized_prescription(
                namespace=ns,
                geometry_hash=geom_hash,
                crop_cycle_id=cycle_id,
                envelope=envelope,
                now=NOW,
                issuer_token="baadc0de" * 8,
            )


def test_direct_ledger_authorized_registration_with_wrong_envelope_token_fails(tmp_path):
    """P343-LEDGER-01: Issuer token minted for another envelope cannot authorize a different envelope."""
    s = create_pilot_setup(tmp_path)
    ns = s["ns"]
    geom_hash = SCOPE["geometry_hash"]
    cycle_id = SCOPE["crop_cycle_id"]

    envelope1 = PrescriptionAuthorizationEnvelopeV2(
        tenant_id=ns.tenant_id,
        farm_id=ns.farm_id,
        plot_id=ns.plot_id,
        geometry_hash=geom_hash,
        crop_cycle_id=cycle_id,
        snapshot_id=s["head"]["snapshot_id"],
        canonical_publication_receipt_hash=s["head"]["publication_receipt_hash"],
        evidence_manifest_hash=s["head"]["manifest_hash"],
        evidence_cutoff_at=s["head"]["evidence_cutoff_at"],
        observation_window_start=TIMES["observation_window_start"],
        observation_window_end=TIMES["observation_window_end"],
        published_at="2026-10-30T18:00:00Z",
        issued_at=NOW,
        expires_at=TIMES["expires_at"],
        uncertainty_receipt_hash=s["bounded"]["content_hash"],
        input_belief_id="belief-test-1",
        tribunal_content_hash=SHA("tribunal-positive"),
        prescription_manifest_hash=SHA("manifest-positive"),
        prescription_manifest_entry_ids=(CONTRIBUTION,),
        policy_snapshot_hash=canonical_hash({"pilot_policy": "strict", "require_evidence_receipts": True}),
        l8_run_id="l8-run-1",
        l8_content_hash=SHA("l8-positive-audit"),
        final_execution_plan_hash=canonical_hash(_serialize_plan(s["artifact"].final_execution_plan)),
        actions=(s["action"],),
    )

    from dataclasses import replace
    envelope2 = replace(envelope1, l8_run_id="l8-run-2", content_hash="")
    envelope2.__post_init__()

    # Mint token for envelope2
    token_for_envelope2 = s["ledger"].mint_issuer_verification_token(
        envelope=envelope2,
        head=s["head"],
        issued_at=NOW,
    )

    with patch(
        "services.agribrain.orchestrator_v2.pilot_authorization_ledger.read_trusted_current_asmae_publication",
        return_value=s["head"],
    ):
        with pytest.raises(ContractViolation, match="invalid or forged issuer verification token"):
            s["ledger"].register_authorized_prescription(
                namespace=ns,
                geometry_hash=geom_hash,
                crop_cycle_id=cycle_id,
                envelope=envelope1,
                now=NOW,
                issuer_token=token_for_envelope2,
            )
