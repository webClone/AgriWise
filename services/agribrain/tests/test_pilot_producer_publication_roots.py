"""End-to-end qualification of ASMAE publication producer evidence and uncertainty roots.

Tests:
1. Full cycle: ASMAE simulation publication -> canonical receipt -> proof attestation V1
   binding witnesses & server signature -> atomic head locator -> proof gate verification.
2. Essential Negative Regression: Tampering ONLY head.admitted_evidence_root_hash
   without modifying the immutable proof attestation.
   The verifier MUST reject it, even when all 10 existing canonical publication flags remain TRUE.
3. Attestation signature forgery and content tampering detection.
4. Clean backward compatibility and fail-closed security for legacy snapshots.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import pytest

from services.agribrain.scientific_contracts.exceptions import ContractViolation
from services.agribrain.scientific_contracts.evidence_receipt import create_evidence_receipt
from services.agribrain.scientific_contracts.prescription_authorization import (
    AuthorizedActionV1,
    PrescriptionAuthorizationEnvelopeV2,
    canonical_hash,
    CANONICAL_PUBLICATION_VALIDATION_FLAGS,
)
from services.agribrain.scientific_contracts.proof_attestation import (
    create_proof_attestation,
    verify_proof_attestation,
    AsmaeProofAttestationV1,
)
from services.agribrain.layer10_sire.surface_contract import (
    SURFACES_SCHEMA_VERSION,
    RENDER_AUTHORIZATION_VERSION,
    classify_surface_publication,
)
from services.agribrain.layer05_asmae.plot_snapshot_store import (
    publish_canonical_plot_snapshot,
    attach_canonical_proof_attestation,
    attach_canonical_proof_roots,
    load_latest_plot_snapshot,
    _head_path,
    _CANONICAL_SNAPSHOT_CACHE,
    _SNAPSHOT_CACHE_LOCK,
)
from services.agribrain.orchestrator_v2.pilot_publication_gate import (
    read_trusted_current_asmae_publication,
    PlotNamespace,
)
from services.agribrain.orchestrator_v2.pilot_proof_gate import (
    verify_published_evidence_membership,
    verify_published_uncertainty_bounds,
    build_admitted_membership_witness,
    build_bounded_uncertainty_witness,
    PilotProofCheck,
)


SHA = lambda x: canonical_hash({"test": x})


@pytest.fixture(autouse=True)
def clear_cache():
    with _SNAPSHOT_CACHE_LOCK:
        _CANONICAL_SNAPSHOT_CACHE.clear()
    yield
    with _SNAPSHOT_CACHE_LOCK:
        _CANONICAL_SNAPSHOT_CACHE.clear()


@pytest.fixture
def tmp_store(tmp_path, monkeypatch):
    """Isolate snapshot store into a temporary directory."""
    root = tmp_path / "plot_snapshots"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "services.agribrain.layer05_asmae.plot_snapshot_store.PLOT_SNAPSHOT_ROOT",
        root,
    )
    return root


def _make_valid_frontend_payload(
    snapshot_id: str,
    plot_id: str,
    cycle_id: str,
    cutoff_str: str,
    window: dict,
    crop_worldline_event_id: Optional[str] = None,
    phenology_worldline_event_id: Optional[str] = None,
) -> dict:
    if crop_worldline_event_id is None:
        crop_worldline_event_id = (
            "event-" + snapshot_id
            if "P347" in snapshot_id
            else f"worldline-{snapshot_id}"
        )
    if phenology_worldline_event_id is None:
        phenology_worldline_event_id = (
            "phenology-" + snapshot_id
            if "P347" in snapshot_id
            else f"pheno-{snapshot_id}"
        )
    value = {
        "intelligence_snapshot_id": snapshot_id,
        "plot_id": plot_id,
        "crop_cycle_id": cycle_id,
        "evidence_cutoff_at": cutoff_str,
        "published_at": "2026-10-30T18:00:00Z",
        "observation_window": window,
        "surfaces": [],
        "status": "degraded",
        "placeholder_only": True,
        "render_authorization_version": RENDER_AUTHORIZATION_VERSION,
        "render_authorizations": {"canopy": {"authorized": False}},
        "asmae_proof": {"status": "unavailable"},
        "mode_display_state": {"canopy": {"status": "unavailable"}},
        "source_policy_display_state": {"status": "unavailable"},
        "core_asmae_evidence_state": {"status": "unavailable"},
        "publication_surface_state": {"status": "unavailable"},
        "publication_id": "PUB-" + snapshot_id,
        "publication_run_id": "RUN-" + snapshot_id,
        "run_id": "RUN-" + snapshot_id,
        "surface_schema_version": SURFACES_SCHEMA_VERSION,
        "scientific_evidence_lineage": {
            "crop_posterior_lineage": f"crop-{snapshot_id}",
            "crop_worldline_event_id": crop_worldline_event_id,
            "phenology_worldline_event_id": phenology_worldline_event_id,
        },
    }
    value["publication_status"] = classify_surface_publication(value)[0]
    return value


def test_producer_publishes_and_validates_canonical_proof_roots(tmp_store):
    """Test full cycle: publication -> receipt -> proof attestation V1 -> verified gates."""
    tenant_id = "tenant-prod-1"
    farm_id = "farm-prod-1"
    plot_id = "6ab14f59ad442f274c3f2a62"
    geom_hash = SHA("plot-geometry")
    cycle_id = "cycle-wheat-2026"
    snapshot_id = "ASMAE-SNAPSHOT-prod-test-001"
    job_manifest_hash = SHA("job-manifest-001")
    cutoff_str = "2026-10-30T17:44:46Z"
    window = {"start": "2026-10-29T00:00:00Z", "end": "2026-10-30T16:00:00Z"}

    action = AuthorizedActionV1(
        action_id="L8-action-1",
        action_type="IRRIGATE",
        priority_score=0.85,
        urgency_score=0.75,
        confidence="HIGH",
        rationale="Root validation test",
        rate={"recommended": 5.0, "min_safe": 4.0, "max_safe": 6.0, "unit": "mm"},
        timing={"earliest": "2026-11-01T10:00:00Z"},
        zone_targets=("plot",),
        requires_confirmation=True,
        machine_execution_allowed=False,
    )

    contribution_id = "DC-irrigation-001"
    evidence_id = "sensor-moisture-001"
    evidence_content = SHA("real-soil-sensor-data")

    # 1. Create typed physical evidence receipt
    receipt = create_evidence_receipt(
        contribution_id=contribution_id,
        evidence_ids=[evidence_id],
        content_hashes=[evidence_content],
        calibration_certificate_id="cert-soil-001",
        spatial_support={"geometry_hash": geom_hash},
        observation_timestamp=datetime(2026, 10, 30, 12, tzinfo=timezone.utc),
        validity_interval=(
            datetime(2026, 10, 30, 12, tzinfo=timezone.utc),
            datetime(2026, 11, 2, 12, tzinfo=timezone.utc),
        ),
        freshness_expiry=datetime(2026, 11, 2, 12, tzinfo=timezone.utc),
        truth_class="CALIBRATED_PHYSICAL_MEASUREMENT",
        originating_stage_receipt_id="stage-receipt-001",
        action_classes_allowed=["EXACT_PRESCRIPTION"],
    )

    # 2. Publish base ASMAE snapshot establishing immutable publication receipt
    ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)
    scientific_result = {
        "status": "OK",
        "plot_id": plot_id,
        "snapshot_id": snapshot_id,
        "crop_posterior_lineage": f"crop-{snapshot_id}",
        "crop_worldline_event_id": f"worldline-{snapshot_id}",
        "phenology_worldline_event_id": f"pheno-{snapshot_id}",
        "evidence_cutoff_at": cutoff_str,
        "observation_window": window,
    }
    frontend_payload = _make_valid_frontend_payload(
        snapshot_id=snapshot_id,
        plot_id=plot_id,
        cycle_id=cycle_id,
        cutoff_str=cutoff_str,
        window=window,
    )

    published_head = publish_canonical_plot_snapshot(
        namespace=ns,
        geometry_hash=geom_hash,
        snapshot_id=snapshot_id,
        asmae_result=scientific_result,
        frontend_payload=frontend_payload,
        job_id="job-prod-001",
        manifest_hash=job_manifest_hash,
    )

    actual_receipt_hash = published_head["publication_receipt_hash"]
    assert actual_receipt_hash is not None

    # 3. Build canonical membership witness binding to exact publication receipt hash
    membership_witness = build_admitted_membership_witness(
        tenant_id=tenant_id,
        farm_id=farm_id,
        plot_id=plot_id,
        geometry_hash=geom_hash,
        crop_cycle_id=cycle_id,
        snapshot_id=snapshot_id,
        publication_receipt_hash=actual_receipt_hash,
        job_manifest_hash=job_manifest_hash,
        evidence_cutoff_at=cutoff_str,
        input_belief_id="belief-001",
        tribunal_content_hash=SHA("tribunal-001"),
        prescription_manifest_hash=SHA("manifest-001"),
        accepted_contribution_ids=[contribution_id],
        entries=[
            {
                "contribution_id": contribution_id,
                "evidence_id": evidence_id,
                "evidence_content_hash": evidence_content,
                "receipt_content_hash": canonical_hash(receipt.to_dict()),
            }
        ],
    )
    admitted_root = membership_witness["content_hash"]
    posterior_hash = SHA("asmae-state-posterior-001")

    # 4. Build canonical uncertainty witness binding to exact publication receipt hash and admitted root
    uncertainty_witness = build_bounded_uncertainty_witness(
        tenant_id=tenant_id,
        farm_id=farm_id,
        plot_id=plot_id,
        geometry_hash=geom_hash,
        crop_cycle_id=cycle_id,
        snapshot_id=snapshot_id,
        publication_receipt_hash=actual_receipt_hash,
        job_manifest_hash=job_manifest_hash,
        evidence_cutoff_at=cutoff_str,
        admitted_evidence_root_hash=admitted_root,
        source_posterior_hash=posterior_hash,
        actions=[
            {
                "action_id": action.action_id,
                "zone_targets": ["plot"],
                "timing": dict(action.timing),
                "min_safe": 3.0,
                "max_safe": 7.0,
                "unit": "mm",
            }
        ],
    )
    uncertainty_root = uncertainty_witness["content_hash"]

    # 5. Create immutable signed proof attestation V1 referencing the canonical publication receipt
    proof_attestation = create_proof_attestation(
        tenant_id=tenant_id,
        farm_id=farm_id,
        plot_id=plot_id,
        geometry_hash=geom_hash,
        crop_cycle_id=cycle_id,
        snapshot_id=snapshot_id,
        canonical_publication_receipt_hash=actual_receipt_hash,
        admitted_evidence_root_hash=admitted_root,
        bounded_uncertainty_receipt_hash=uncertainty_root,
        scientific_posterior_hash=posterior_hash,
        issuer_key_id="test-issuer-key-01",
    )

    # 6. Commit proof attestation to the active head publication
    attached = attach_canonical_proof_attestation(ns, proof_attestation)
    assert attached["attestation_hash"] == proof_attestation.attestation_hash

    # 7. Verify load_latest_plot_snapshot authenticates attestation and validates all 10 flags
    loaded = load_latest_plot_snapshot(ns)
    assert loaded is not None
    assert loaded["admitted_evidence_root_hash"] == admitted_root
    assert loaded["bounded_uncertainty_receipt_hash"] == uncertainty_root
    assert loaded["scientific_posterior_hash"] == posterior_hash
    assert loaded["proof_attestation_valid"] is True
    assert loaded["proof_attestation"] is not None

    validation = loaded.get("validation", {})
    for flag in CANONICAL_PUBLICATION_VALIDATION_FLAGS:
        assert validation.get(flag) is True, f"Validation flag failed: {flag}"
    assert validation.get("proofAttestationValid") is True

    # 8. Verify read_trusted_current_asmae_publication exposes verified roots and attestation
    trusted_head = read_trusted_current_asmae_publication(
        ns,
        expected_snapshot_id=snapshot_id,
        expected_geometry_hash=geom_hash,
        expected_crop_cycle_id=cycle_id,
        require_proof_attestation=True,
    )
    assert trusted_head["admitted_evidence_root_hash"] == admitted_root
    assert trusted_head["bounded_uncertainty_receipt_hash"] == uncertainty_root
    assert trusted_head["scientific_posterior_hash"] == posterior_hash
    assert trusted_head["proof_attestation_valid"] is True

    # 9. Construct candidate V2 envelope
    envelope = PrescriptionAuthorizationEnvelopeV2(
        tenant_id=tenant_id,
        farm_id=farm_id,
        plot_id=plot_id,
        geometry_hash=geom_hash,
        crop_cycle_id=cycle_id,
        snapshot_id=snapshot_id,
        canonical_publication_receipt_hash=actual_receipt_hash,
        evidence_manifest_hash=job_manifest_hash,
        evidence_cutoff_at=cutoff_str,
        observation_window_start="2026-10-29T00:00:00Z",
        observation_window_end="2026-10-30T16:00:00Z",
        published_at="2026-10-30T18:00:00Z",
        issued_at="2026-10-30T18:30:00Z",
        expires_at="2026-11-02T18:30:00Z",
        uncertainty_receipt_hash=uncertainty_root,
        input_belief_id="belief-001",
        tribunal_content_hash=SHA("tribunal-001"),
        prescription_manifest_hash=SHA("manifest-001"),
        prescription_manifest_entry_ids=(contribution_id,),
        policy_snapshot_hash=SHA("policy-001"),
        l8_run_id="l8-001",
        l8_content_hash=SHA("l8-hash-001"),
        final_execution_plan_hash=SHA("plan-001"),
        actions=(action,),
    )

    # 10. Verify proof gates pass against authenticated head
    mem_check = verify_published_evidence_membership(
        head=trusted_head,
        envelope=envelope,
        membership_witness=membership_witness,
        admitted_evidence_receipts={contribution_id: receipt},
        reference_time="2026-10-31T12:00:00Z",
        permitted_truth_classes=["CALIBRATED_PHYSICAL_MEASUREMENT"],
        action_class="EXACT_PRESCRIPTION",
    )
    assert isinstance(mem_check, PilotProofCheck)
    assert mem_check.status == "STRUCTURAL_MATCH_ONLY"
    assert mem_check.claimed_root == admitted_root

    unc_check = verify_published_uncertainty_bounds(
        head=trusted_head,
        envelope=envelope,
        uncertainty_witness=uncertainty_witness,
        membership=mem_check,
    )
    assert isinstance(unc_check, PilotProofCheck)
    assert unc_check.status == "STRUCTURAL_MATCH_ONLY"
    assert unc_check.claimed_root == uncertainty_root


def test_essential_negative_regression_tampered_head_roots_rejected_while_10_flags_remain_true(tmp_store):
    """Essential Negative Regression (Phase 1D Review Gate):

    Change ONLY head.admitted_evidence_root_hash in head.json, without changing
    the immutable proof attestation.
    The verifier MUST reject it, even when all ten existing canonical publication
    validation flags remain true.
    """
    tenant_id = "tenant-tamper-1"
    farm_id = "farm-tamper-1"
    plot_id = "plot-tamper-1"
    geom_hash = SHA("geom-tamper")
    cycle_id = "cycle-tamper"
    snapshot_id = "ASMAE-SNAPSHOT-tamper-001"
    job_manifest_hash = SHA("job-manifest-tamper")
    cutoff_str = "2026-10-30T17:44:46Z"
    window = {"start": "2026-10-29T00:00:00Z", "end": "2026-10-30T16:00:00Z"}

    ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)
    scientific_result = {
        "status": "OK",
        "plot_id": plot_id,
        "snapshot_id": snapshot_id,
        "crop_posterior_lineage": f"crop-{snapshot_id}",
        "crop_worldline_event_id": f"worldline-{snapshot_id}",
        "phenology_worldline_event_id": f"pheno-{snapshot_id}",
        "evidence_cutoff_at": cutoff_str,
        "observation_window": window,
    }
    frontend_payload = _make_valid_frontend_payload(
        snapshot_id=snapshot_id,
        plot_id=plot_id,
        cycle_id=cycle_id,
        cutoff_str=cutoff_str,
        window=window,
    )

    published_head = publish_canonical_plot_snapshot(
        namespace=ns,
        geometry_hash=geom_hash,
        snapshot_id=snapshot_id,
        asmae_result=scientific_result,
        frontend_payload=frontend_payload,
        job_id="job-tamper-001",
        manifest_hash=job_manifest_hash,
    )

    receipt_hash = published_head["publication_receipt_hash"]
    genuine_admitted_root = SHA("genuine-admitted-root")
    genuine_uncertainty_root = SHA("genuine-uncertainty-root")
    genuine_posterior_hash = SHA("genuine-posterior-hash")

    # Create and attach genuine immutable proof attestation
    attestation = create_proof_attestation(
        tenant_id=tenant_id,
        farm_id=farm_id,
        plot_id=plot_id,
        geometry_hash=geom_hash,
        crop_cycle_id=cycle_id,
        snapshot_id=snapshot_id,
        canonical_publication_receipt_hash=receipt_hash,
        admitted_evidence_root_hash=genuine_admitted_root,
        bounded_uncertainty_receipt_hash=genuine_uncertainty_root,
        scientific_posterior_hash=genuine_posterior_hash,
        issuer_key_id="issuer-tamper-test",
    )
    attach_canonical_proof_attestation(ns, attestation)

    # 1. Baseline verification: valid 10/10 flags and valid attestation
    clean_loaded = load_latest_plot_snapshot(ns)
    assert clean_loaded["proof_attestation_valid"] is True
    assert clean_loaded["admitted_evidence_root_hash"] == genuine_admitted_root
    for flag in CANONICAL_PUBLICATION_VALIDATION_FLAGS:
        assert clean_loaded["validation"][flag] is True

    # 2. DELIBERATELY TAMPER ONLY head.json's admitted_evidence_root_hash
    # The immutable attestation on disk is NOT touched.
    with _SNAPSHOT_CACHE_LOCK:
        _CANONICAL_SNAPSHOT_CACHE.clear()

    head_path = _head_path(ns)
    head_content = json.loads(head_path.read_text(encoding="utf-8"))
    forged_root = SHA("forged-admitted-root-by-attacker")
    head_content["admitted_evidence_root_hash"] = forged_root
    head_path.write_text(json.dumps(head_content), encoding="utf-8")

    # 3. Reload snapshot
    tampered_loaded = load_latest_plot_snapshot(ns)
    assert tampered_loaded is not None

    # CRITICAL CHECK A: The ten canonical publication validation flags MUST ALL REMAIN TRUE
    # because the base publication chain (node, publication, receipt) was not corrupted.
    for flag in CANONICAL_PUBLICATION_VALIDATION_FLAGS:
        assert tampered_loaded["validation"][flag] is True, (
            f"Canonical flag {flag} should remain True on tampered head root"
        )

    # CRITICAL CHECK B: proofAttestationValid MUST BE FALSE
    assert tampered_loaded["validation"]["proofAttestationValid"] is False
    assert tampered_loaded["proof_attestation_valid"] is False
    assert tampered_loaded["proof_attestation_reason"] == "head_roots_tampered_relative_to_attestation"

    # CRITICAL CHECK C: Admitted roots must FAIL CLOSED (set to None, never exposing forged root)
    assert tampered_loaded["admitted_evidence_root_hash"] is None
    assert tampered_loaded["bounded_uncertainty_receipt_hash"] is None
    assert tampered_loaded["scientific_posterior_hash"] is None

    # CRITICAL CHECK D: read_trusted_current_asmae_publication with require_proof_attestation MUST REJECT
    with pytest.raises(ContractViolation, match="lacks an authenticated proof attestation"):
        read_trusted_current_asmae_publication(
            ns,
            expected_snapshot_id=snapshot_id,
            expected_geometry_hash=geom_hash,
            expected_crop_cycle_id=cycle_id,
            require_proof_attestation=True,
        )

    # CRITICAL CHECK E: Gate verifier MUST REJECT the tampered head
    trusted_tampered = read_trusted_current_asmae_publication(
        ns,
        expected_snapshot_id=snapshot_id,
        expected_geometry_hash=geom_hash,
        expected_crop_cycle_id=cycle_id,
        require_proof_attestation=False,
    )

    action = AuthorizedActionV1(
        action_id="A1",
        action_type="SCOUT",
        priority_score=0.5,
        urgency_score=0.5,
        confidence="LOW",
        rationale="Tamper test",
    )
    envelope = PrescriptionAuthorizationEnvelopeV2(
        tenant_id=tenant_id,
        farm_id=farm_id,
        plot_id=plot_id,
        geometry_hash=geom_hash,
        crop_cycle_id=cycle_id,
        snapshot_id=snapshot_id,
        canonical_publication_receipt_hash=receipt_hash,
        evidence_manifest_hash=job_manifest_hash,
        evidence_cutoff_at=cutoff_str,
        observation_window_start="2026-10-29T00:00:00Z",
        observation_window_end="2026-10-30T16:00:00Z",
        published_at="2026-10-30T18:00:00Z",
        issued_at="2026-10-30T18:30:00Z",
        expires_at="2026-11-02T18:30:00Z",
        uncertainty_receipt_hash=genuine_uncertainty_root,
        input_belief_id="belief",
        tribunal_content_hash=SHA("trib"),
        prescription_manifest_hash=SHA("man"),
        prescription_manifest_entry_ids=("contrib",),
        policy_snapshot_hash=SHA("pol"),
        l8_run_id="l8",
        l8_content_hash=SHA("l8h"),
        final_execution_plan_hash=SHA("plan"),
        actions=(action,),
    )

    witness = build_admitted_membership_witness(
        tenant_id=tenant_id,
        farm_id=farm_id,
        plot_id=plot_id,
        geometry_hash=geom_hash,
        crop_cycle_id=cycle_id,
        snapshot_id=snapshot_id,
        publication_receipt_hash=receipt_hash,
        job_manifest_hash=job_manifest_hash,
        evidence_cutoff_at=cutoff_str,
        input_belief_id="belief",
        tribunal_content_hash=SHA("trib"),
        prescription_manifest_hash=SHA("man"),
        accepted_contribution_ids=["contrib"],
        entries=[
            {
                "contribution_id": "contrib",
                "evidence_id": "ev1",
                "evidence_content_hash": SHA("evc"),
                "receipt_content_hash": SHA("rc"),
            }
        ],
    )

    with pytest.raises(ContractViolation, match="Scientific proof requires an authentic, verified proof attestation"):
        verify_published_evidence_membership(
            head=trusted_tampered,
            envelope=envelope,
            membership_witness=witness,
            admitted_evidence_receipts={},
            reference_time="2026-10-31T12:00:00Z",
            permitted_truth_classes=["CALIBRATED_PHYSICAL_MEASUREMENT"],
            action_class="EXACT_PRESCRIPTION",
        )


def test_tampered_attestation_signature_fails_closed(tmp_store):
    """Test forged digital signature or modified hash is detected and rejected."""
    tenant_id = "tenant-forge-1"
    farm_id = "farm-forge-1"
    plot_id = "plot-forge-1"
    geom_hash = SHA("geom-forge")
    cycle_id = "cycle-forge"
    snapshot_id = "ASMAE-SNAPSHOT-forge-001"
    receipt_hash = SHA("receipt-forge")

    attestation = create_proof_attestation(
        tenant_id=tenant_id,
        farm_id=farm_id,
        plot_id=plot_id,
        geometry_hash=geom_hash,
        crop_cycle_id=cycle_id,
        snapshot_id=snapshot_id,
        canonical_publication_receipt_hash=receipt_hash,
        admitted_evidence_root_hash=SHA("admitted-forge"),
        bounded_uncertainty_receipt_hash=SHA("uncertainty-forge"),
        scientific_posterior_hash=SHA("posterior-forge"),
    )
    # Untampered verifies
    verify_proof_attestation(attestation)

    # Forged signature raises ContractViolation
    forged_dict = attestation.to_dict()
    forged_dict["signature"] = "0" * 64
    with pytest.raises(ContractViolation, match="digital signature is invalid or forged"):
        verify_proof_attestation(forged_dict)

    # Tampered root with old signature raises ContractViolation
    tampered_dict = attestation.to_dict()
    tampered_dict["admitted_evidence_root_hash"] = "f" * 64
    with pytest.raises(ContractViolation, match="content hash is invalid or tampered"):
        verify_proof_attestation(tampered_dict)


def test_legacy_snapshot_without_roots_retains_validation_and_fails_closed(tmp_store):
    """Test legacy snapshot without roots: validates 10/10, but fails closed on proof gates."""
    tenant_id = "tenant-leg-1"
    farm_id = "farm-leg-1"
    plot_id = "plot-leg-1"
    geom_hash = SHA("geom-leg")
    cycle_id = "cycle-leg"
    snapshot_id = "ASMAE-SNAPSHOT-legacy-001"
    job_manifest_hash = SHA("job-manifest-leg")
    cutoff_str = "2026-10-30T17:44:46Z"
    window = {"start": "2026-10-29T00:00:00Z", "end": "2026-10-30T16:00:00Z"}

    ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)
    scientific_result = {
        "status": "OK",
        "plot_id": plot_id,
        "snapshot_id": snapshot_id,
        "crop_posterior_lineage": f"crop-{snapshot_id}",
        "crop_worldline_event_id": f"worldline-{snapshot_id}",
        "phenology_worldline_event_id": f"pheno-{snapshot_id}",
        "evidence_cutoff_at": cutoff_str,
        "observation_window": window,
    }
    frontend_payload = _make_valid_frontend_payload(
        snapshot_id=snapshot_id,
        plot_id=plot_id,
        cycle_id=cycle_id,
        cutoff_str=cutoff_str,
        window=window,
    )

    published_head = publish_canonical_plot_snapshot(
        namespace=ns,
        geometry_hash=geom_hash,
        snapshot_id=snapshot_id,
        asmae_result=scientific_result,
        frontend_payload=frontend_payload,
        job_id="job-leg-001",
        manifest_hash=job_manifest_hash,
    )

    loaded = load_latest_plot_snapshot(ns)
    assert loaded is not None
    assert loaded.get("admitted_evidence_root_hash") is None
    assert loaded.get("bounded_uncertainty_receipt_hash") is None
    assert loaded.get("scientific_posterior_hash") is None
    assert loaded.get("proof_attestation") is None
    validation = loaded.get("validation", {})
    for flag in CANONICAL_PUBLICATION_VALIDATION_FLAGS:
        assert validation.get(flag) is True, f"Legacy flag failed: {flag}"

    trusted = read_trusted_current_asmae_publication(
        ns,
        expected_snapshot_id=snapshot_id,
        expected_geometry_hash=geom_hash,
        expected_crop_cycle_id=cycle_id,
    )
    assert trusted.get("admitted_evidence_root_hash") is None
    assert trusted.get("proof_attestation") is None

    # Dummy envelope and matching typed receipt to verify fail-closed rejection
    envelope = PrescriptionAuthorizationEnvelopeV2(
        tenant_id=tenant_id,
        farm_id=farm_id,
        plot_id=plot_id,
        geometry_hash=geom_hash,
        crop_cycle_id=cycle_id,
        snapshot_id=snapshot_id,
        canonical_publication_receipt_hash=published_head["publication_receipt_hash"],
        evidence_manifest_hash=job_manifest_hash,
        evidence_cutoff_at=cutoff_str,
        observation_window_start="2026-10-29T00:00:00Z",
        observation_window_end="2026-10-30T16:00:00Z",
        published_at="2026-10-30T18:00:00Z",
        issued_at="2026-10-30T18:30:00Z",
        expires_at="2026-11-02T18:30:00Z",
        uncertainty_receipt_hash=SHA("unc"),
        input_belief_id="belief",
        tribunal_content_hash=SHA("trib"),
        prescription_manifest_hash=SHA("man"),
        prescription_manifest_entry_ids=("contrib",),
        policy_snapshot_hash=SHA("pol"),
        l8_run_id="l8",
        l8_content_hash=SHA("l8h"),
        final_execution_plan_hash=SHA("plan"),
        actions=(
            AuthorizedActionV1(
                action_id="A1",
                action_type="SCOUT",
                priority_score=0.5,
                urgency_score=0.5,
                confidence="LOW",
                rationale="Scout",
            ),
        ),
    )

    leg_receipt = create_evidence_receipt(
        contribution_id="contrib",
        evidence_ids=["ev1"],
        content_hashes=[SHA("evc")],
        calibration_certificate_id="cert-leg-001",
        spatial_support={"geometry_hash": geom_hash},
        observation_timestamp=datetime(2026, 10, 30, 12, tzinfo=timezone.utc),
        validity_interval=(
            datetime(2026, 10, 30, 12, tzinfo=timezone.utc),
            datetime(2026, 11, 2, 12, tzinfo=timezone.utc),
        ),
        freshness_expiry=datetime(2026, 11, 2, 12, tzinfo=timezone.utc),
        truth_class="CALIBRATED_PHYSICAL_MEASUREMENT",
        originating_stage_receipt_id="stage-leg-001",
        action_classes_allowed=["EXACT_PRESCRIPTION"],
    )

    witness = build_admitted_membership_witness(
        tenant_id=tenant_id,
        farm_id=farm_id,
        plot_id=plot_id,
        geometry_hash=geom_hash,
        crop_cycle_id=cycle_id,
        snapshot_id=snapshot_id,
        publication_receipt_hash=published_head["publication_receipt_hash"],
        job_manifest_hash=job_manifest_hash,
        evidence_cutoff_at=cutoff_str,
        input_belief_id="belief",
        tribunal_content_hash=SHA("trib"),
        prescription_manifest_hash=SHA("man"),
        accepted_contribution_ids=["contrib"],
        entries=[
            {
                "contribution_id": "contrib",
                "evidence_id": "ev1",
                "evidence_content_hash": SHA("evc"),
                "receipt_content_hash": canonical_hash(leg_receipt.to_dict()),
            }
        ],
    )

    # Gate must raise ContractViolation because head has no admitted_evidence_root_hash
    with pytest.raises(ContractViolation, match="admitted_evidence_root_hash"):
        verify_published_evidence_membership(
            head=trusted,
            envelope=envelope,
            membership_witness=witness,
            admitted_evidence_receipts={"contrib": leg_receipt},
            reference_time="2026-10-31T12:00:00Z",
            permitted_truth_classes=["CALIBRATED_PHYSICAL_MEASUREMENT"],
            action_class="EXACT_PRESCRIPTION",
        )
