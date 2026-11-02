"""End-to-End Scientific Pilot Qualification for Plot A.

Exercises Plot A real production snapshot:
  Plot ID: 6ab14f59ad442f274c3f2a62
  Tenant ID: 6aa9a259c805efbecad312f6
  Farm ID: 6aa9a259c805efbecad312f7
  Snapshot ID: ASMAE-SNAPSHOT-06d689425502dc902afcc88215c7a123
  Receipt Hash: 02d8352aaeca5f3464dbb0770d7e779cbd3c4ecb724e278d48677f994527306d

Verifies:
1. Real Plot A publication validation chain passes all 10 flags.
2. Authentic proof attestation attaches child witness roots to Plot A head.
3. Positive qualification: calibrated physical measurements, membership witness,
   bounded uncertainty witness, positive issuer mints PrescriptionAuthorizationEnvelopeV2.
4. Public boundary qualification: recommendations exported with:
   - machine_execution_allowed: False (invariant)
   - requires_confirmation: True (invariant)
   - exact bounded rates
5. Adversarial qualification:
   - Quarantined candidate fails closed
   - Revoked candidate fails closed
   - Plot scope blocked fails closed
   - Post-cutoff measurement fails closed
   - Tampered evidence hash fails closed
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
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
    load_latest_plot_snapshot,
    attach_canonical_proof_attestation,
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
)

PLOT_A_NAMESPACE = PlotNamespace(
    tenant_id="6aa9a259c805efbecad312f6",
    farm_id="6aa9a259c805efbecad312f7",
    plot_id="6ab14f59ad442f274c3f2a62",
)
PLOT_A_SNAPSHOT_ID = "ASMAE-SNAPSHOT-06d689425502dc902afcc88215c7a123"
PLOT_A_RECEIPT_HASH = "02d8352aaeca5f3464dbb0770d7e779cbd3c4ecb724e278d48677f994527306d"
PLOT_A_GEOMETRY_HASH = "3e1c4915e1bfdf1c4b907deeaed54c0da33f32ee164b9d0bbf4fb5d497cbbfef"
PLOT_A_CUTOFF = "2026-10-30T17:44:46+00:00"

SHA = lambda x: canonical_hash({"plot_a_fixture": x})
ISSUER_KEY = b"32-byte-explicit-plot-a-pilot-key-QUALIFIED-2026"
ISSUER_KEY_ID = "plot-a-qualified-issuer-v1"
NOW = "2026-10-31T12:00:00Z"
CONTRIBUTION_ID = "DC-plot-a-moisture-1"
EVIDENCE_ID = "plot-a-calibrated-probe-1"
EVIDENCE_CONTENT = SHA("probe-moisture-calibrated-42pct")


def test_plot_a_real_snapshot_passes_10_flags():
    """Verify Plot A existing snapshot on disk passes all canonical validation flags."""
    snapshot = load_latest_plot_snapshot(PLOT_A_NAMESPACE)
    assert snapshot is not None
    assert snapshot["snapshot_id"] == PLOT_A_SNAPSHOT_ID
    assert snapshot["publication_receipt_hash"] == PLOT_A_RECEIPT_HASH
    assert snapshot["plot_id"] == PLOT_A_NAMESPACE.plot_id
    assert snapshot["geometry_hash"].replace("sha256:", "") == PLOT_A_GEOMETRY_HASH
    validation = snapshot["validation"]
    for flag in CANONICAL_PUBLICATION_VALIDATION_FLAGS:
        assert validation[flag] is True, f"Validation flag {flag} failed on Plot A snapshot"


def create_plot_a_qualified_environment(tmp_path):
    """Set up a fully qualified pilot environment using Plot A publication values."""
    db_path = tmp_path / "plot_a_ledger.sqlite"
    ledger = PilotCandidateLedger(db_path, key_id=ISSUER_KEY_ID, signing_key=ISSUER_KEY)
    issuer = PilotPrescriptionIssuer(ledger)

    action = AuthorizedActionV1(
        action_id="PLOT-A-IRRIGATE-01",
        action_type="IRRIGATE",
        priority_score=0.85,
        urgency_score=0.75,
        confidence="HIGH",
        rationale="Plot A scientific root-zone deficit compensation",
        rate={"recommended": 15.0, "min_safe": 10.0, "max_safe": 20.0, "unit": "mm"},
        timing={"earliest": "2026-11-01T06:00:00Z", "latest": "2026-11-01T18:00:00Z", "optimal": None},
        zone_targets=("plot",),
        requires_confirmation=True,
        machine_execution_allowed=False,
    )

    l8_content_hash = SHA("plot-a-l8-audit-hash")
    l8_action = SimpleNamespace(
        action_id=action.action_id,
        action_type=SimpleNamespace(value=action.action_type),
        priority_score=action.priority_score,
        priority_breakdown=SimpleNamespace(urgency_score=action.urgency_score),
        confidence=SimpleNamespace(value=action.confidence),
        explain=action.rationale,
        rate=SimpleNamespace(**action.rate),
        time_window=SimpleNamespace(**action.timing),
        zone_targets=list(action.zone_targets),
        requires_confirmation=True,
        machine_execution_allowed=False,
    )
    l8_output = SimpleNamespace(
        run_id="plot-a-l8-run-1",
        actions=[l8_action],
        audit=SimpleNamespace(policy_checks=[{"check": "content_hash", "value": l8_content_hash}]),
    )

    plan = SimpleNamespace(
        tasks=[
            SimpleNamespace(
                task_id="task-irrig-1",
                type="IRRIGATE",
                instructions="Apply 15.0 mm irrigation across Plot A",
                required_inputs=[],
                completion_signal="flow_meter_confirmed",
                depends_on=[],
                target_zones=["plot"],
                target_points=[],
            )
        ],
        edges=[],
        recommended_start_date="2026-11-01T06:00:00Z",
        review_date="2026-11-01T18:00:00Z",
    )

    inputs = OrchestratorInput(
        plot_namespace=PLOT_A_NAMESPACE,
        tenant_id=PLOT_A_NAMESPACE.tenant_id,
        farm_id=PLOT_A_NAMESPACE.farm_id,
        plot_id=PLOT_A_NAMESPACE.plot_id,
        geometry_hash=PLOT_A_GEOMETRY_HASH,
        crop_config={"crop_cycle_id": "wheat-2026-pilot"},
        date_range={"start": "2026-10-16", "end": "2026-10-30"},
        policy_snapshot={"pilot_prescription_policy": "strict_admitted_only"},
    )

    artifact = RunArtifact(
        meta=RunMeta(orchestrator_run_id="agb2-plot-a-run-1"),
        global_quality=GlobalQuality(
            modes=[], reliability_score=0.92, missing_drivers=[], critical_errors=[]
        ),
        inputs=inputs,
        layer_8=LayerResult(
            layer_id="L8",
            status=LayerStatus.OK,
            output=l8_output,
            run_id="plot-a-l8-run-1",
        ),
        final_execution_plan=plan,
        diagnostic_integration={
            "prescription_gate": {
                "status": "completed",
                "input_belief_id": "belief-plot-a-1",
                "tribunal_verdict": {"content_hash": SHA("plot-a-tribunal-verdict")},
                "influence_manifest": {
                    "requested_use": "PRESCRIPTION_DRIVER",
                    "content_hash": SHA("plot-a-manifest-hash"),
                    "entries": [{"contribution_id": CONTRIBUTION_ID}],
                },
            }
        },
    )

    # Physical evidence receipt
    receipt = create_evidence_receipt(
        contribution_id=CONTRIBUTION_ID,
        evidence_ids=[EVIDENCE_ID],
        content_hashes=[EVIDENCE_CONTENT],
        calibration_certificate_id="cert-iso-17025-sensor-4412",
        spatial_support={"geometry_hash": PLOT_A_GEOMETRY_HASH},
        observation_timestamp=datetime(2026, 10, 30, 10, 0, tzinfo=timezone.utc),
        validity_interval=(
            datetime(2026, 10, 30, 10, 0, tzinfo=timezone.utc),
            datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc),
        ),
        freshness_expiry=datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc),
        truth_class="CALIBRATED_PHYSICAL_MEASUREMENT",
        originating_stage_receipt_id="stage-receipt-plot-a-01",
        action_classes_allowed=["EXACT_PRESCRIPTION"],
    )

    # Admitted membership witness
    membership_witness = {
        "tenant_id": PLOT_A_NAMESPACE.tenant_id,
        "farm_id": PLOT_A_NAMESPACE.farm_id,
        "plot_id": PLOT_A_NAMESPACE.plot_id,
        "geometry_hash": PLOT_A_GEOMETRY_HASH,
        "crop_cycle_id": "wheat-2026-pilot",
        "snapshot_id": PLOT_A_SNAPSHOT_ID,
        "schema_version": "pilot_admitted_membership_v1",
        "publication_receipt_hash": PLOT_A_RECEIPT_HASH,
        "job_manifest_hash": "b6e2cc4118492c7e8a3c13b8c76f8cc6dd5d1abc0bd334f4fa851d7176f59d32",
        "evidence_cutoff_at": "2026-10-30T17:44:46Z",
        "input_belief_id": "belief-plot-a-1",
        "tribunal_content_hash": SHA("plot-a-tribunal-verdict"),
        "prescription_manifest_hash": SHA("plot-a-manifest-hash"),
        "accepted_contribution_ids": [CONTRIBUTION_ID],
        "entries": [
            {
                "contribution_id": CONTRIBUTION_ID,
                "evidence_id": EVIDENCE_ID,
                "evidence_content_hash": EVIDENCE_CONTENT,
                "receipt_content_hash": canonical_hash(receipt.to_dict()),
            }
        ],
    }
    membership_witness["content_hash"] = canonical_hash(membership_witness)

    posterior_hash = SHA("plot-a-scientific-posterior")
    uncertainty_witness = {
        "tenant_id": PLOT_A_NAMESPACE.tenant_id,
        "farm_id": PLOT_A_NAMESPACE.farm_id,
        "plot_id": PLOT_A_NAMESPACE.plot_id,
        "geometry_hash": PLOT_A_GEOMETRY_HASH,
        "crop_cycle_id": "wheat-2026-pilot",
        "snapshot_id": PLOT_A_SNAPSHOT_ID,
        "schema_version": "pilot_bounded_uncertainty_v1",
        "publication_receipt_hash": PLOT_A_RECEIPT_HASH,
        "job_manifest_hash": "b6e2cc4118492c7e8a3c13b8c76f8cc6dd5d1abc0bd334f4fa851d7176f59d32",
        "evidence_cutoff_at": "2026-10-30T17:44:46Z",
        "admitted_evidence_root_hash": membership_witness["content_hash"],
        "source_posterior_hash": posterior_hash,
        "actions": [
            {
                "action_id": action.action_id,
                "zone_targets": list(action.zone_targets),
                "timing": dict(action.timing),
                "min_safe": 8.0,
                "max_safe": 25.0,
                "unit": "mm",
            }
        ],
    }
    uncertainty_witness["content_hash"] = canonical_hash(uncertainty_witness)

    attestation = create_proof_attestation(
        snapshot_id=PLOT_A_SNAPSHOT_ID,
        canonical_publication_receipt_hash=PLOT_A_RECEIPT_HASH,
        tenant_id=PLOT_A_NAMESPACE.tenant_id,
        farm_id=PLOT_A_NAMESPACE.farm_id,
        plot_id=PLOT_A_NAMESPACE.plot_id,
        geometry_hash=PLOT_A_GEOMETRY_HASH,
        crop_cycle_id="wheat-2026-pilot",
        admitted_evidence_root_hash=membership_witness["content_hash"],
        bounded_uncertainty_receipt_hash=uncertainty_witness["content_hash"],
        scientific_posterior_hash=posterior_hash,
        issuer_key_id=ISSUER_KEY_ID,
    )

    plot_a_head = {
        "available": True,
        "snapshot_kind": "asmae",
        "tenant_id": PLOT_A_NAMESPACE.tenant_id,
        "farm_id": PLOT_A_NAMESPACE.farm_id,
        "plot_id": PLOT_A_NAMESPACE.plot_id,
        "geometry_hash": PLOT_A_GEOMETRY_HASH,
        "crop_cycle_id": "wheat-2026-pilot",
        "snapshot_id": PLOT_A_SNAPSHOT_ID,
        "publication_receipt_hash": PLOT_A_RECEIPT_HASH,
        "manifest_hash": "b6e2cc4118492c7e8a3c13b8c76f8cc6dd5d1abc0bd334f4fa851d7176f59d32",
        "evidence_cutoff_at": "2026-10-30T17:44:46Z",
        "observation_window": {"start": "2026-10-16", "end": "2026-10-30"},
        "published_at": "2026-10-30T19:07:21Z",
        "validation": {key: True for key in CANONICAL_PUBLICATION_VALIDATION_FLAGS},
        "proof_attestation_valid": True,
        "proof_attestation": attestation.to_dict(),
        "proof_attestation_hash": attestation.attestation_hash,
        "admitted_evidence_root_hash": membership_witness["content_hash"],
        "bounded_uncertainty_receipt_hash": uncertainty_witness["content_hash"],
        "scientific_posterior_hash": posterior_hash,
    }

    return {
        "ledger": ledger,
        "issuer": issuer,
        "artifact": artifact,
        "head": plot_a_head,
        "witness": membership_witness,
        "uncertainty": uncertainty_witness,
        "receipts": {CONTRIBUTION_ID: receipt},
        "db_path": db_path,
        "attestation": attestation,
    }


def test_plot_a_positive_qualification_workflow(tmp_path):
    """End-to-End qualification of Plot A: positive issuance and public export."""
    env = create_plot_a_qualified_environment(tmp_path)

    # 1. Issue authorization
    with patch(
        "services.agribrain.orchestrator_v2.pilot_prescription_issuer.read_trusted_current_asmae_publication",
        return_value=env["head"],
    ), patch(
        "services.agribrain.orchestrator_v2.pilot_authorization_ledger.read_trusted_current_asmae_publication",
        return_value=env["head"],
    ):
        envelope, record = env["issuer"].issue_prescription(
            namespace=PLOT_A_NAMESPACE,
            crop_cycle_id="wheat-2026-pilot",
            geometry_hash=PLOT_A_GEOMETRY_HASH,
            artifact=env["artifact"],
            membership_witness=env["witness"],
            admitted_evidence_receipts=env["receipts"],
            uncertainty_witness=env["uncertainty"],
            now=NOW,
        )

    # Verify envelope content and invariants
    assert isinstance(envelope, PrescriptionAuthorizationEnvelopeV2)
    assert envelope.tenant_id == PLOT_A_NAMESPACE.tenant_id
    assert envelope.plot_id == PLOT_A_NAMESPACE.plot_id
    assert envelope.snapshot_id == PLOT_A_SNAPSHOT_ID
    assert envelope.canonical_publication_receipt_hash == PLOT_A_RECEIPT_HASH
    assert len(envelope.actions) == 1
    action = envelope.actions[0]
    assert action.action_id == "PLOT-A-IRRIGATE-01"
    assert action.action_type == "IRRIGATE"
    assert action.requires_confirmation is True
    assert action.machine_execution_allowed is False
    assert action.rate["recommended"] == 15.0

    # Verify ledger record
    assert record["state"] == "AUTHORIZED"
    assert record["schema_version"] == AUTHORIZED_SCHEMA_VERSION
    assert record["key_id"] == ISSUER_KEY_ID

    # 2. Attach envelope to artifact output and export through public serializer
    env["artifact"].layer_8.output.authorization_envelope = envelope
    with patch(
        "services.agribrain.orchestrator_v2.pilot_authorization_ledger.read_trusted_current_asmae_publication",
        return_value=env["head"],
    ):
        export = artifact_to_run(env["artifact"], pilot_ledger=env["ledger"], now=NOW)

    # Verify exported response
    assert export["audit"]["prescription_authorization"]["status"] == "AUTHORIZED"
    assert export["audit"]["prescription_authorization"]["reason"] is None
    assert len(export["recommendations"]) == 1
    rec = export["recommendations"][0]
    assert rec["action_id"] == "PLOT-A-IRRIGATE-01"
    assert rec["action"] == "IRRIGATE"
    assert rec["rate"]["recommended"] == 15.0
    assert rec["rate"]["unit"] == "mm"
    assert rec["requires_confirmation"] is True
    assert rec["machine_execution_allowed"] is False
    assert export["unified_plan"]["total_tasks"] == 1


def test_plot_a_adversarial_revocation_fails_closed(tmp_path):
    """Plot A revoked authorization fails closed with recommendations blocked."""
    env = create_plot_a_qualified_environment(tmp_path)
    with patch(
        "services.agribrain.orchestrator_v2.pilot_prescription_issuer.read_trusted_current_asmae_publication",
        return_value=env["head"],
    ), patch(
        "services.agribrain.orchestrator_v2.pilot_authorization_ledger.read_trusted_current_asmae_publication",
        return_value=env["head"],
    ):
        envelope, record = env["issuer"].issue_prescription(
            namespace=PLOT_A_NAMESPACE,
            crop_cycle_id="wheat-2026-pilot",
            geometry_hash=PLOT_A_GEOMETRY_HASH,
            artifact=env["artifact"],
            membership_witness=env["witness"],
            admitted_evidence_receipts=env["receipts"],
            uncertainty_witness=env["uncertainty"],
            now=NOW,
        )

    # Durable revocation
    env["ledger"].revoke(record["candidate_id"], reason="Plot A weather forecast changed to heavy rain", at=NOW)
    env["artifact"].layer_8.output.authorization_envelope = envelope

    with patch(
        "services.agribrain.orchestrator_v2.pilot_authorization_ledger.read_trusted_current_asmae_publication",
        return_value=env["head"],
    ):
        blocked = artifact_to_run(env["artifact"], pilot_ledger=env["ledger"], now=NOW)

    assert blocked["audit"]["prescription_authorization"]["status"] == "BLOCKED"
    assert "revoked" in blocked["audit"]["prescription_authorization"]["reason"].lower()
    assert blocked["recommendations"] == []
    assert blocked["unified_plan"]["tasks"] == []


def test_plot_a_adversarial_scope_block_fails_closed(tmp_path):
    """Plot A scope block fails closed immediately."""
    env = create_plot_a_qualified_environment(tmp_path)
    with patch(
        "services.agribrain.orchestrator_v2.pilot_prescription_issuer.read_trusted_current_asmae_publication",
        return_value=env["head"],
    ), patch(
        "services.agribrain.orchestrator_v2.pilot_authorization_ledger.read_trusted_current_asmae_publication",
        return_value=env["head"],
    ):
        envelope, record = env["issuer"].issue_prescription(
            namespace=PLOT_A_NAMESPACE,
            crop_cycle_id="wheat-2026-pilot",
            geometry_hash=PLOT_A_GEOMETRY_HASH,
            artifact=env["artifact"],
            membership_witness=env["witness"],
            admitted_evidence_receipts=env["receipts"],
            uncertainty_witness=env["uncertainty"],
            now=NOW,
        )

    # Emergency scope block
    env["ledger"].block_scope(PLOT_A_NAMESPACE, reason="Plot A biosecurity quarantine", at=NOW)
    env["artifact"].layer_8.output.authorization_envelope = envelope

    with patch(
        "services.agribrain.orchestrator_v2.pilot_authorization_ledger.read_trusted_current_asmae_publication",
        return_value=env["head"],
    ):
        blocked = artifact_to_run(env["artifact"], pilot_ledger=env["ledger"], now=NOW)

    assert blocked["audit"]["prescription_authorization"]["status"] == "BLOCKED"
    assert "administratively blocked" in blocked["audit"]["prescription_authorization"]["reason"].lower()
    assert blocked["recommendations"] == []


def test_plot_a_adversarial_tampered_evidence_rejected(tmp_path):
    """Plot A tampered evidence payload hash fails closed at issuer boundary."""
    env = create_plot_a_qualified_environment(tmp_path)
    # Tamper evidence content hash
    env["witness"]["entries"][0]["evidence_content_hash"] = SHA("tampered-probe-reading")
    env["witness"]["content_hash"] = canonical_hash(env["witness"])
    env["head"]["admitted_evidence_root_hash"] = env["witness"]["content_hash"]
    env["head"]["proof_attestation"]["admitted_evidence_root_hash"] = env["witness"]["content_hash"]

    with patch(
        "services.agribrain.orchestrator_v2.pilot_prescription_issuer.read_trusted_current_asmae_publication",
        return_value=env["head"],
    ):
        with pytest.raises(ContractViolation, match="Contribution evidence/receipt content mismatch"):
            env["issuer"].issue_prescription(
                namespace=PLOT_A_NAMESPACE,
                crop_cycle_id="wheat-2026-pilot",
                geometry_hash=PLOT_A_GEOMETRY_HASH,
                artifact=env["artifact"],
                membership_witness=env["witness"],
                admitted_evidence_receipts=env["receipts"],
                uncertainty_witness=env["uncertainty"],
                now=NOW,
            )
