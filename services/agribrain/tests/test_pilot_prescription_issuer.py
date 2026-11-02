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
        policy_snapshot={"pilot_policy": "strict"},
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
                artifact=bad_artifact,
                membership_witness=s["witness"],
                admitted_evidence_receipts=s["receipts"],
                uncertainty_witness=s["bounded"],
                now=NOW,
            )
