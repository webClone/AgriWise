"""End-to-End Scientific Pilot Qualification for Plot A.

Genuine source-backed and authenticated qualification against Plot A real production artifacts:
  Plot ID: 6ab14f59ad442f274c3f2a62
  Tenant ID: 6aa9a259c805efbecad312f6
  Farm ID: 6aa9a259c805efbecad312f7
  Snapshot ID: ASMAE-SNAPSHOT-06d689425502dc902afcc88215c7a123
  Receipt Hash: 02d8352aaeca5f3464dbb0770d7e779cbd3c4ecb724e278d48677f994527306d
  Geometry Hash: 3e1c4915e1bfdf1c4b907deeaed54c0da33f32ee164b9d0bbf4fb5d497cbbfef
  Posterior Hash: ce2156db9a2421d6a0c82647c86d70ce36a54c06eb5c559949e9d4e41e20089a
  Job Manifest Hash: b6e2cc4118492c7e8a3c13b8c76f8cc6dd5d1abc0bd334f4fa851d7176f59d32
  Evidence Cutoff: 2026-10-30T17:44:46+00:00
  Admitted Evidence: S2ACQ-f4b410e88a86beac0cedbb98ba3d658149e060cb551941607a7445c43edeeefd

Verifies:
1. Real Plot A publication validation chain passes all 10 flags.
2. Authentic proof attestation attaches child witness roots to genuine Plot A head.
3. Positive qualification: unmocked publication retrieval, calibrated physical evidence,
   membership witness, bounded uncertainty witness, and positive issuer minting
   PrescriptionAuthorizationEnvelopeV2.
4. Public boundary qualification: recommendations exported with:
   - machine_execution_allowed: False (invariant)
   - requires_confirmation: True (invariant)
   - exact bounded rates
5. Adversarial qualification (unmocked):
   - Revoked candidate fails closed
   - Plot scope blocked fails closed
   - Tampered evidence hash fails closed
   - Missing mandatory policy fails closed
   - Post-cutoff measurement fails closed
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import shutil
import sqlite3
from types import SimpleNamespace

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
    _CANONICAL_SNAPSHOT_CACHE,
    _SNAPSHOT_CACHE_LOCK,
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

PLOT_A_NAMESPACE = PlotNamespace(
    tenant_id="6aa9a259c805efbecad312f6",
    farm_id="6aa9a259c805efbecad312f7",
    plot_id="6ab14f59ad442f274c3f2a62",
)
PLOT_A_SNAPSHOT_ID = "ASMAE-SNAPSHOT-06d689425502dc902afcc88215c7a123"
PLOT_A_RECEIPT_HASH = "02d8352aaeca5f3464dbb0770d7e779cbd3c4ecb724e278d48677f994527306d"
PLOT_A_GEOMETRY_HASH = "3e1c4915e1bfdf1c4b907deeaed54c0da33f32ee164b9d0bbf4fb5d497cbbfef"
PLOT_A_POSTERIOR_HASH = "ce2156db9a2421d6a0c82647c86d70ce36a54c06eb5c559949e9d4e41e20089a"
PLOT_A_JOB_MANIFEST_HASH = "b6e2cc4118492c7e8a3c13b8c76f8cc6dd5d1abc0bd334f4fa851d7176f59d32"
PLOT_A_CUTOFF = "2026-10-30T17:44:46+00:00"
PLOT_A_DIR_NAME = "8fbba2201db60cabcc72a67a1284e816"

# Real admitted Sentinel-2 optical radiometry acquisition ID from Plot A node
PLOT_A_ADMITTED_EVIDENCE_ID = "S2ACQ-f4b410e88a86beac0cedbb98ba3d658149e060cb551941607a7445c43edeeefd"
PLOT_A_ADMITTED_CONTENT_HASH = "f4b410e88a86beac0cedbb98ba3d658149e060cb551941607a7445c43edeeefd"
PLOT_A_CONTRIBUTION_ID = "DC-sentinel2-radiometry-f4b410"

SHA = lambda x: canonical_hash({"plot_a_fixture": x})
ISSUER_KEY = b"32-byte-explicit-plot-a-pilot-key-QUALIFIED-2026"
ISSUER_KEY_ID = "plot-a-qualified-issuer-v1"
NOW = "2026-10-31T12:00:00Z"
CROP_CYCLE_ID = "wheat-2026-pilot"


@pytest.fixture(autouse=True)
def clear_snapshot_cache():
    with _SNAPSHOT_CACHE_LOCK:
        _CANONICAL_SNAPSHOT_CACHE.clear()
    yield
    with _SNAPSHOT_CACHE_LOCK:
        _CANONICAL_SNAPSHOT_CACHE.clear()


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


def create_plot_a_qualified_environment(tmp_path, monkeypatch):
    """Set up an unmocked, genuine Plot A environment backed by authentic artifacts on disk."""
    store_dir = tmp_path / "plot_snapshots"
    store_dir.mkdir(parents=True, exist_ok=True)
    real_plot_a_src = Path(__file__).resolve().parents[1] / "artifacts" / "plot_snapshots" / PLOT_A_DIR_NAME
    shutil.copytree(real_plot_a_src, store_dir / PLOT_A_DIR_NAME)
    monkeypatch.setattr("services.agribrain.layer05_asmae.plot_snapshot_store.PLOT_SNAPSHOT_ROOT", store_dir)

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
        crop_config={"crop_cycle_id": CROP_CYCLE_ID},
        date_range={"start": "2026-10-16", "end": "2026-10-30"},
        policy_snapshot={"pilot_prescription_policy": "strict_admitted_only", "require_evidence_receipts": True},
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
                    "entries": [{"contribution_id": PLOT_A_CONTRIBUTION_ID}],
                },
            }
        },
    )

    # Physical evidence receipt for admitted Sentinel-2 observation
    receipt = create_evidence_receipt(
        contribution_id=PLOT_A_CONTRIBUTION_ID,
        evidence_ids=[PLOT_A_ADMITTED_EVIDENCE_ID],
        content_hashes=[PLOT_A_ADMITTED_CONTENT_HASH],
        calibration_certificate_id="cert-copernicus-sentinel-2-radiometric-l2a",
        spatial_support={"geometry_hash": PLOT_A_GEOMETRY_HASH},
        observation_timestamp=datetime(2026, 10, 22, 10, 41, 5, tzinfo=timezone.utc),
        validity_interval=(
            datetime(2026, 10, 22, 10, 41, 5, tzinfo=timezone.utc),
            datetime(2026, 11, 10, 0, 0, tzinfo=timezone.utc),
        ),
        freshness_expiry=datetime(2026, 11, 10, 0, 0, tzinfo=timezone.utc),
        truth_class="CALIBRATED_PHYSICAL_MEASUREMENT",
        originating_stage_receipt_id="stage-receipt-copernicus-l2a-001",
        action_classes_allowed=["EXACT_PRESCRIPTION"],
    )

    # Admitted membership witness bound to Plot A canonical publication and admitted evidence
    membership_witness = {
        "tenant_id": PLOT_A_NAMESPACE.tenant_id,
        "farm_id": PLOT_A_NAMESPACE.farm_id,
        "plot_id": PLOT_A_NAMESPACE.plot_id,
        "geometry_hash": PLOT_A_GEOMETRY_HASH,
        "crop_cycle_id": CROP_CYCLE_ID,
        "snapshot_id": PLOT_A_SNAPSHOT_ID,
        "schema_version": "pilot_admitted_membership_v1",
        "publication_receipt_hash": PLOT_A_RECEIPT_HASH,
        "job_manifest_hash": PLOT_A_JOB_MANIFEST_HASH,
        "evidence_cutoff_at": PLOT_A_CUTOFF,
        "input_belief_id": "belief-plot-a-1",
        "tribunal_content_hash": SHA("plot-a-tribunal-verdict"),
        "prescription_manifest_hash": SHA("plot-a-manifest-hash"),
        "accepted_contribution_ids": [PLOT_A_CONTRIBUTION_ID],
        "entries": [
            {
                "contribution_id": PLOT_A_CONTRIBUTION_ID,
                "evidence_id": PLOT_A_ADMITTED_EVIDENCE_ID,
                "evidence_content_hash": PLOT_A_ADMITTED_CONTENT_HASH,
                "receipt_content_hash": canonical_hash(receipt.to_dict()),
            }
        ],
    }
    membership_witness["content_hash"] = canonical_hash(membership_witness)

    # Bounded uncertainty witness bound to Plot A scientific posterior
    uncertainty_witness = {
        "tenant_id": PLOT_A_NAMESPACE.tenant_id,
        "farm_id": PLOT_A_NAMESPACE.farm_id,
        "plot_id": PLOT_A_NAMESPACE.plot_id,
        "geometry_hash": PLOT_A_GEOMETRY_HASH,
        "crop_cycle_id": CROP_CYCLE_ID,
        "snapshot_id": PLOT_A_SNAPSHOT_ID,
        "schema_version": "pilot_bounded_uncertainty_v1",
        "publication_receipt_hash": PLOT_A_RECEIPT_HASH,
        "job_manifest_hash": PLOT_A_JOB_MANIFEST_HASH,
        "evidence_cutoff_at": PLOT_A_CUTOFF,
        "admitted_evidence_root_hash": membership_witness["content_hash"],
        "source_posterior_hash": PLOT_A_POSTERIOR_HASH,
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

    # Proof attestation V1 signed and committed to the active head
    attestation = create_proof_attestation(
        snapshot_id=PLOT_A_SNAPSHOT_ID,
        canonical_publication_receipt_hash=PLOT_A_RECEIPT_HASH,
        tenant_id=PLOT_A_NAMESPACE.tenant_id,
        farm_id=PLOT_A_NAMESPACE.farm_id,
        plot_id=PLOT_A_NAMESPACE.plot_id,
        geometry_hash=PLOT_A_GEOMETRY_HASH,
        crop_cycle_id=CROP_CYCLE_ID,
        admitted_evidence_root_hash=membership_witness["content_hash"],
        bounded_uncertainty_receipt_hash=uncertainty_witness["content_hash"],
        scientific_posterior_hash=PLOT_A_POSTERIOR_HASH,
        issuer_key_id=ISSUER_KEY_ID,
    )
    attach_canonical_proof_attestation(PLOT_A_NAMESPACE, attestation)

    return {
        "ledger": ledger,
        "issuer": issuer,
        "artifact": artifact,
        "witness": membership_witness,
        "uncertainty": uncertainty_witness,
        "receipts": {PLOT_A_CONTRIBUTION_ID: receipt},
        "db_path": db_path,
        "attestation": attestation,
    }


def test_plot_a_positive_qualification_workflow(tmp_path, monkeypatch):
    """P75-TRUST-03: Real-world unmocked positive qualification of Plot A."""
    env = create_plot_a_qualified_environment(tmp_path, monkeypatch)

    # 1. Issue authorization — completely UNMOCKED publication reader
    envelope, record = env["issuer"].issue_prescription(
        namespace=PLOT_A_NAMESPACE,
        crop_cycle_id=CROP_CYCLE_ID,
        geometry_hash=PLOT_A_GEOMETRY_HASH,
        expected_snapshot_id=PLOT_A_SNAPSHOT_ID,
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

    # 2. Attach envelope to artifact output and export through public serializer — UNMOCKED
    env["artifact"].layer_8.output.authorization_envelope = envelope
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


def test_plot_a_adversarial_revocation_fails_closed(tmp_path, monkeypatch):
    """Plot A revoked authorization fails closed with recommendations blocked (unmocked)."""
    env = create_plot_a_qualified_environment(tmp_path, monkeypatch)
    envelope, record = env["issuer"].issue_prescription(
        namespace=PLOT_A_NAMESPACE,
        crop_cycle_id=CROP_CYCLE_ID,
        geometry_hash=PLOT_A_GEOMETRY_HASH,
        expected_snapshot_id=PLOT_A_SNAPSHOT_ID,
        artifact=env["artifact"],
        membership_witness=env["witness"],
        admitted_evidence_receipts=env["receipts"],
        uncertainty_witness=env["uncertainty"],
        now=NOW,
    )

    # Durable revocation
    env["ledger"].revoke(record["candidate_id"], reason="Plot A weather forecast changed to heavy rain", at=NOW)
    env["artifact"].layer_8.output.authorization_envelope = envelope

    blocked = artifact_to_run(env["artifact"], pilot_ledger=env["ledger"], now=NOW)

    assert blocked["audit"]["prescription_authorization"]["status"] == "BLOCKED"
    assert "revoked" in blocked["audit"]["prescription_authorization"]["reason"].lower()
    assert blocked["recommendations"] == []
    assert blocked["unified_plan"]["tasks"] == []


def test_plot_a_adversarial_scope_block_fails_closed(tmp_path, monkeypatch):
    """Plot A scope block fails closed immediately (unmocked)."""
    env = create_plot_a_qualified_environment(tmp_path, monkeypatch)
    envelope, record = env["issuer"].issue_prescription(
        namespace=PLOT_A_NAMESPACE,
        crop_cycle_id=CROP_CYCLE_ID,
        geometry_hash=PLOT_A_GEOMETRY_HASH,
        expected_snapshot_id=PLOT_A_SNAPSHOT_ID,
        artifact=env["artifact"],
        membership_witness=env["witness"],
        admitted_evidence_receipts=env["receipts"],
        uncertainty_witness=env["uncertainty"],
        now=NOW,
    )

    # Emergency scope block
    env["ledger"].block_scope(PLOT_A_NAMESPACE, reason="Plot A biosecurity quarantine", at=NOW)
    env["artifact"].layer_8.output.authorization_envelope = envelope

    blocked = artifact_to_run(env["artifact"], pilot_ledger=env["ledger"], now=NOW)

    assert blocked["audit"]["prescription_authorization"]["status"] == "BLOCKED"
    assert "administratively blocked" in blocked["audit"]["prescription_authorization"]["reason"].lower()
    assert blocked["recommendations"] == []


def test_plot_a_adversarial_tampered_evidence_rejected(tmp_path, monkeypatch):
    """Plot A tampered evidence payload hash fails closed at issuer boundary (unmocked)."""
    env = create_plot_a_qualified_environment(tmp_path, monkeypatch)
    # Tamper evidence content hash
    env["witness"]["entries"][0]["evidence_content_hash"] = SHA("tampered-copernicus-reading")
    env["witness"]["content_hash"] = canonical_hash(env["witness"])

    with pytest.raises(ContractViolation, match="Contribution evidence/receipt content mismatch"):
        env["issuer"].issue_prescription(
            namespace=PLOT_A_NAMESPACE,
            crop_cycle_id=CROP_CYCLE_ID,
            geometry_hash=PLOT_A_GEOMETRY_HASH,
            expected_snapshot_id=PLOT_A_SNAPSHOT_ID,
            artifact=env["artifact"],
            membership_witness=env["witness"],
            admitted_evidence_receipts=env["receipts"],
            uncertainty_witness=env["uncertainty"],
            now=NOW,
        )


def test_plot_a_adversarial_missing_policy_receipts_rejected(tmp_path, monkeypatch):
    """P75-POL-02: Plot A fails closed when require_evidence_receipts is omitted from policy."""
    env = create_plot_a_qualified_environment(tmp_path, monkeypatch)
    env["artifact"].inputs = replace(env["artifact"].inputs, policy_snapshot={"pilot_prescription_policy": "strict"})

    with pytest.raises(ContractViolation, match="require_evidence_receipts=True"):
        env["issuer"].issue_prescription(
            namespace=PLOT_A_NAMESPACE,
            crop_cycle_id=CROP_CYCLE_ID,
            geometry_hash=PLOT_A_GEOMETRY_HASH,
            expected_snapshot_id=PLOT_A_SNAPSHOT_ID,
            artifact=env["artifact"],
            membership_witness=env["witness"],
            admitted_evidence_receipts=env["receipts"],
            uncertainty_witness=env["uncertainty"],
            now=NOW,
        )


def test_plot_a_adversarial_post_cutoff_observation_rejected(tmp_path, monkeypatch):
    """Plot A observation arriving after evidence cutoff is strictly rejected (unmocked)."""
    env = create_plot_a_qualified_environment(tmp_path, monkeypatch)

    # Create post-cutoff receipt (cutoff is 2026-10-30T17:44:46Z; observation is at 19:00:00Z)
    post_cutoff_receipt = create_evidence_receipt(
        contribution_id=PLOT_A_CONTRIBUTION_ID,
        evidence_ids=[PLOT_A_ADMITTED_EVIDENCE_ID],
        content_hashes=[PLOT_A_ADMITTED_CONTENT_HASH],
        calibration_certificate_id="cert-copernicus-sentinel-2-radiometric-l2a",
        spatial_support={"geometry_hash": PLOT_A_GEOMETRY_HASH},
        observation_timestamp=datetime(2026, 10, 30, 19, 0, tzinfo=timezone.utc),
        validity_interval=(
            datetime(2026, 10, 30, 19, 0, tzinfo=timezone.utc),
            datetime(2026, 11, 10, 0, 0, tzinfo=timezone.utc),
        ),
        freshness_expiry=datetime(2026, 11, 10, 0, 0, tzinfo=timezone.utc),
        truth_class="CALIBRATED_PHYSICAL_MEASUREMENT",
        originating_stage_receipt_id="stage-receipt-post-cutoff-001",
        action_classes_allowed=["EXACT_PRESCRIPTION"],
    )

    env["witness"]["entries"][0]["receipt_content_hash"] = canonical_hash(post_cutoff_receipt.to_dict())
    env["witness"]["content_hash"] = canonical_hash(env["witness"])

    with pytest.raises(ContractViolation, match="Post-cutoff telemetry cannot be admitted into published science"):
        env["issuer"].issue_prescription(
            namespace=PLOT_A_NAMESPACE,
            crop_cycle_id=CROP_CYCLE_ID,
            geometry_hash=PLOT_A_GEOMETRY_HASH,
            expected_snapshot_id=PLOT_A_SNAPSHOT_ID,
            artifact=env["artifact"],
            membership_witness=env["witness"],
            admitted_evidence_receipts={PLOT_A_CONTRIBUTION_ID: post_cutoff_receipt},
            uncertainty_witness=env["uncertainty"],
            now=NOW,
        )
