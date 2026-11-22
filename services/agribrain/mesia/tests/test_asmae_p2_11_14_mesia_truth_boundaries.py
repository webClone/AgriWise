"""P2-11..14: MESIA physical evidence, P-08, unit and claim safety.

Source-level plus small runtime regression controls. No end-to-end calibration
or physical radio capture qualifications are claimed.
"""
import hashlib
import inspect
import json
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone

import pytest

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.mesia.ingestion.sigmf_ingest import ingest_sigmf_capture, verify_capture_integrity
from services.agribrain.mesia.integration import (
    MesiaAgriBrainBridge,
    verify_native_capture_for_plot,
    resolve_mesia_evidence_role,
)
from services.agribrain.mesia.contracts.observation import RadioObservationPacket
from services.agribrain.mesia.behaviour.likelihood_engine import BehaviourLikelihoodEngine
from services.agribrain.mesia.behaviour.feature_extraction import NativeFeatureExtractor
from services.agribrain.mesia.assimilation.layer0_spine import EvidenceAdmissionStatus
from services.agribrain.mesia.governance import claim_scanner


def _packet(uri="", digest="", *, profile="WIFI_CSI/v2", scope="evidence_proposal",
            role=""):
    return RadioObservationPacket(
        packet_id="p2-mesia-packet-1",
        source_profile=profile,
        receiver_id="rx-probe",
        native_data_uri=uri,
        native_data_hash=digest,
        utc_time=datetime(2026, 11, 21, tzinfo=timezone.utc),
        authority_scope=scope,
        evidence_role=role,
    )


@pytest.mark.parametrize("uri", [
    "file://mesia/evidence/plot-1/not-real.sigmf-data",
    "https://example.org/capture.sigmf-data",
    "sigmf://capture/abc.sigmf-data",
    "file:///definitely-nonexistent-capture-99244.nmea",
    "file://../plot-1/sample.nmea",
    "",
])
def test_p2_11_missing_nonlocal_and_spoofed_native_capture_never_qualifies(tmp_path, uri):
    ns = PlotNamespace(tenant_id="tenant-1", farm_id="farm-1", plot_id="plot-1")
    assert not verify_native_capture_for_plot(
        _packet(uri, "a" * 64), ns, storage_root=tmp_path,
    )


def test_p2_11_actual_sha256_match_requires_plot_and_tenant_scoped_file(tmp_path):
    ns = PlotNamespace(tenant_id="tenant-1", farm_id="farm-1", plot_id="plot-1")
    directory = tmp_path / "tenant-1" / "plot-1"
    directory.mkdir(parents=True)
    raw = b"$GPRMC,20261121,24.5,SNR,37.4\r\n"
    real_file = directory / "capture.nmea"
    real_file.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    good = _packet(real_file.as_uri(), digest)
    assert verify_native_capture_for_plot(good, ns, storage_root=tmp_path)
    assert not verify_native_capture_for_plot(
        good, PlotNamespace(tenant_id="tenant-1", farm_id="farm-1", plot_id="foreign-plot"), storage_root=tmp_path
    )
    assert not verify_native_capture_for_plot(
        good, PlotNamespace(tenant_id="foreign-tenant", farm_id="farm-1", plot_id="plot-1"), storage_root=tmp_path
    )
    # Missing / plot-only namespace fails closed
    assert not verify_native_capture_for_plot(good, "plot-1", storage_root=tmp_path)
    assert not verify_native_capture_for_plot(good, None, storage_root=tmp_path)
    assert not verify_native_capture_for_plot(
        _packet(real_file.as_uri(), "0" * 64), ns, storage_root=tmp_path
    )
    real_file.write_bytes(b"tampered")
    assert not verify_native_capture_for_plot(good, ns, storage_root=tmp_path)


@pytest.mark.parametrize("role", ["", "SENSING"])
def test_p2_11_unknown_radio_cannot_default_to_sensing(role):
    norm, allowed = resolve_mesia_evidence_role(
        _packet(profile="NEW_UNKNOWN_SIGNAL/v99", role=role)
    )
    assert allowed is False
    if not role:
        assert norm == "UNKNOWN"


def test_p2_11_registered_radio_requires_its_actual_role():
    role, allowed = resolve_mesia_evidence_role(_packet())
    assert role == "SENSING" and allowed is True


def test_p2_11_mesia_bridge_rejects_p08_state_claim_before_admission():
    ns = PlotNamespace(tenant_id="tenant-1", farm_id="farm-1", plot_id="plot-1")
    bridge = MesiaAgriBrainBridge(plot_namespace=ns)
    with pytest.raises(ValueError, match="Principle P-08"):
        bridge.process_and_admit_observation(
            _packet("file:///nonexistent.raw", "a"*64, scope="STATE_UPDATE"),
            is_calibration_valid=True, is_epoch_active=True,
        )


def test_p2_11_nonexistent_hash_address_never_admitted_with_valid_flags():
    ns = PlotNamespace(tenant_id="tenant-1", farm_id="farm-1", plot_id="plot-1")
    bridge = MesiaAgriBrainBridge(plot_namespace=ns)
    record, event = bridge.process_and_admit_observation(
        _packet("file://mesia/evidence/plot-1/fake.raw", "a" * 64),
        is_calibration_valid=True, is_epoch_active=True,
    )
    assert record.status == EvidenceAdmissionStatus.INVALIDATED
    assert record.is_usable_for_assimilation is False
    assert event is None


def test_p2_12_radiometric_db_residual_never_appears_as_vwc_innovation(monkeypatch):
    monkeypatch.setattr(
        NativeFeatureExtractor, "extract_features",
        lambda packet: SimpleNamespace(features={
            "snr_db": 42.0,
            "expected_baseline_snr_db": 35.0,
            "calibration_uncertainty_db": 1.5,
        }),
    )
    nuisance = SimpleNamespace(
        is_safe_for_soil_assimilation=True,
        p_instrument_nuisance=0.1,
        p_geometry_nuisance=0.1,
        p_network_nuisance=0.1,
        p_coexistence_nuisance=0.1,
        p_weather_motion_nuisance=0.1,
        p_unknown_nuisance=0.5,
    )
    likelihood = BehaviourLikelihoodEngine.generate_likelihood(
        _packet(profile="GNSS_REFLECTOMETRY/v1"), nuisance_report=nuisance,
    )
    assert likelihood.radio_residual_db == pytest.approx(7.0)
    assert likelihood.radio_residual_variance_db2 is not None
    assert likelihood.radio_residual_variance_db2 > 0
    assert likelihood.innovation is None
    assert likelihood.covariance is None
    assert likelihood.support == 0.0
    assert likelihood.target_variable == "UNSPECIFIED_PENDING_CALIBRATED_OPERATOR"
    assert likelihood.target_unit == "UNQUALIFIED"
    assert likelihood.authority_scope == "evidence_proposal"


def test_p2_13_biological_inversion_contract_preserves_parent_receipt():
    from services.agribrain.mesia.service import MesiaProductionService
    source = inspect.getsource(MesiaProductionService.scan_plot_spectrum)
    assert '"evidence_class": "DERIVED_MODEL_INFERRED"' in source
    assert '"truth_classification": "DERIVED_MODEL_INFERRED"' in source
    assert '"authority_scope": "evidence_proposal"' in source
    assert "processing_level=ProcessingLevel.DERIVED" in source
    assert "parent_envelope_refs=(l0_rec.record_id,)" in source
    assert '"native_capture_present"] = verify_native_capture_for_plot(packet, plot_namespace)' in source


def test_p2_14_production_ui_is_not_whole_file_exempt():
    path = "src/components/farm/intelligence/EngineExpertView.tsx"
    assert not claim_scanner.is_file_exempt(path, [
        {"file_pattern": path, "reason": "previous unsafe blanket exemption"},
    ])


def test_p2_14_exact_reviewed_ground_truth_line_does_not_exempt_synthetic_claim(tmp_path, monkeypatch):
    monkeypatch.setattr(claim_scanner, "WORKSPACE_ROOT", tmp_path)
    path = "src/components/farm/intelligence/EngineExpertView.tsx"
    src = tmp_path / path
    src.parent.mkdir(parents=True)
    src.write_text(
        "// Ground Truth registry field label\n// Zero synthetic data.\n",
        encoding="utf-8",
    )
    config = tmp_path / "claim_exemptions.json"
    config.write_text(json.dumps({
        "exemptions": [{"file_pattern": path, "reason": "unsafe blanket"}],
        "line_exemptions": [{
            "file": path, "rule": "GROUND_TRUTH",
            "line_text": "// Ground Truth registry field label",
            "reason": "Precisely reviewed registry label",
        }],
    }), encoding="utf-8")
    bad = claim_scanner.scan_repository_for_forbidden_claims(
        target_dirs=[tmp_path / "src/components/farm/intelligence"],
        exemptions_file=config,
    )
    assert [(x["rule"], x["line_number"]) for x in bad] == [("ZERO_SYNTHETIC", 2)]


# =============================================================================
# BATCH A ADVERSARIAL COVERAGE — D01 (Tenant Binding) & D02 (SigMF Integrity)
# =============================================================================

def test_batch_a_d01_cross_tenant_same_plot_rejection(tmp_path):
    """D01: Two tenants sharing the same plot identifier are strictly isolated.
    A valid capture for Tenant B must be rejected under Tenant A's authenticated namespace.
    """
    tenant_a = "tenant-alpha"
    tenant_b = "tenant-beta"
    shared_plot = "parcel-shared-42"

    raw_data = b"synthetic_mesia_radio_csi_bytes_tenant_b"
    meta = {
        "global": {"core:sample_rate": 20.0e6, "core:hw": "wifi_csi_rx_fixture"},
        "captures": [{
            "core:datetime": datetime(2026, 11, 22, 12, 0, 0, tzinfo=timezone.utc).isoformat(),
            "core:frequency": 2.437e9,
        }],
        "annotations": [{"core:sample_count": 8}],
    }
    manifest_b = ingest_sigmf_capture(
        tenant_id=tenant_b,
        plot_id=shared_plot,
        raw_data_bytes=raw_data,
        metadata_dict=meta,
        storage_root=tmp_path,
    )
    capture_file_b = Path(manifest_b.data_path)
    assert capture_file_b.is_file()

    packet_b = _packet(uri=capture_file_b.as_uri(), digest=manifest_b.data_sha256)

    ns_a = PlotNamespace(tenant_id=tenant_a, farm_id="farm-a", plot_id=shared_plot)
    ns_b = PlotNamespace(tenant_id=tenant_b, farm_id="farm-b", plot_id=shared_plot)

    # 1. Tenant A's namespace must REJECT Tenant B's capture (even though plot_id matches!)
    assert not verify_native_capture_for_plot(packet_b, ns_a, storage_root=tmp_path)

    # 2. Tenant B's namespace must ACCEPT Tenant B's capture
    assert verify_native_capture_for_plot(packet_b, ns_b, storage_root=tmp_path)

    # 3. MesiaAgriBrainBridge under Tenant A must evaluate admission as INVALIDATED
    bridge_a = MesiaAgriBrainBridge(plot_namespace=ns_a, storage_root=tmp_path)
    rec_a, ev_a = bridge_a.process_and_admit_observation(
        packet_b, is_calibration_valid=True, is_epoch_active=True,
    )
    assert rec_a.status == EvidenceAdmissionStatus.INVALIDATED
    assert rec_a.is_usable_for_assimilation is False
    assert ev_a is None

    # 4. MesiaAgriBrainBridge under Tenant B must evaluate admission as ABSENT (evidence valid, innovation withheld)
    bridge_b = MesiaAgriBrainBridge(plot_namespace=ns_b, storage_root=tmp_path)
    rec_b, ev_b = bridge_b.process_and_admit_observation(
        packet_b, is_calibration_valid=True, is_epoch_active=True,
    )
    assert rec_b.status == EvidenceAdmissionStatus.ABSENT
    assert rec_b.is_usable_for_assimilation is False


def test_batch_a_d01_cross_tenant_uri_substitution_attack(tmp_path):
    """D01: Malicious caller attempting to substitute cross-tenant capture URI fails closed."""
    tenant_legit = "tenant-legit"
    tenant_attacker = "tenant-attacker"
    plot_id = "plot-target"

    raw = b"legitimate_iq_stream_bytes"
    meta = {
        "global": {"core:sample_rate": 10.0e6, "core:hw": "usrp_b210"},
        "captures": [{
            "core:datetime": datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc).isoformat(),
            "core:frequency": 5.18e9,
        }],
        "annotations": [{"core:sample_count": 4}],
    }
    manifest = ingest_sigmf_capture(
        tenant_id=tenant_legit,
        plot_id=plot_id,
        raw_data_bytes=raw,
        metadata_dict=meta,
        storage_root=tmp_path,
    )

    attack_packet = _packet(uri=Path(manifest.data_path).as_uri(), digest=manifest.data_sha256)

    attacker_ns = PlotNamespace(tenant_id=tenant_attacker, farm_id="farm-att", plot_id=plot_id)
    assert not verify_native_capture_for_plot(attack_packet, attacker_ns, storage_root=tmp_path)

    attacker_bridge = MesiaAgriBrainBridge(plot_namespace=attacker_ns, storage_root=tmp_path)
    rec, ev = attacker_bridge.process_and_admit_observation(
        attack_packet, is_calibration_valid=True, is_epoch_active=True,
    )
    assert rec.status == EvidenceAdmissionStatus.INVALIDATED


def test_batch_a_d01_path_escape_and_symlink_rejection(tmp_path):
    """D01: Path traversal or symlink escapes fail closed."""
    ns = PlotNamespace(tenant_id="tenant-escape", farm_id="farm-1", plot_id="plot-1")
    legit_dir = tmp_path / "tenant-escape" / "plot-1"
    legit_dir.mkdir(parents=True)

    target_outside = tmp_path / "outside.raw"
    target_outside.write_bytes(b"outside_bytes_12345678")
    outside_sha = hashlib.sha256(b"outside_bytes_12345678").hexdigest()

    # Traversal URI
    traversal_path = legit_dir / ".." / ".." / "outside.raw"
    pkt_trav = _packet(uri=traversal_path.as_uri(), digest=outside_sha)
    assert not verify_native_capture_for_plot(pkt_trav, ns, storage_root=tmp_path)

    # Symlink escape
    symlink_file = legit_dir / "symlink_escape.raw"
    try:
        symlink_file.symlink_to(target_outside)
        pkt_sym = _packet(uri=symlink_file.as_uri(), digest=outside_sha)
        assert not verify_native_capture_for_plot(pkt_sym, ns, storage_root=tmp_path)
    except (OSError, NotImplementedError):
        pass


def test_batch_a_d02_tampered_sigmf_metadata_rejection(tmp_path):
    """D02: Tampered companion metadata must fail closed across verifier and bridge."""
    tenant = "tenant-d02"
    plot = "plot-d02"
    ns = PlotNamespace(tenant_id=tenant, farm_id="farm-1", plot_id=plot)

    raw = b"sigmf_iq_data_for_tamper_test"
    meta = {
        "global": {"core:sample_rate": 20.0e6, "core:hw": "wifi_csi_probe"},
        "captures": [{
            "core:datetime": datetime(2026, 11, 22, 14, 0, 0, tzinfo=timezone.utc).isoformat(),
            "core:frequency": 2.45e9,
        }],
        "annotations": [{"core:sample_count": 10}],
    }
    manifest = ingest_sigmf_capture(tenant, plot, raw, meta, storage_root=tmp_path)

    # Corrupt .sigmf-meta by changing frequency (meta hash mismatch with manifest)
    meta_path = Path(manifest.meta_path)
    corrupted_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    corrupted_meta["captures"][0]["core:frequency"] = 5.8e9
    meta_path.write_text(json.dumps(corrupted_meta), encoding="utf-8")

    data_file = Path(manifest.data_path)
    pkt = _packet(uri=data_file.as_uri(), digest=manifest.data_sha256)

    # Verifier must reject tampered companion metadata
    assert not verify_capture_integrity(data_file, expected_namespace=ns, storage_root=tmp_path)
    assert not verify_native_capture_for_plot(pkt, ns, storage_root=tmp_path)

    # Bridge admission must yield INVALIDATED
    bridge = MesiaAgriBrainBridge(plot_namespace=ns, storage_root=tmp_path)
    rec, ev = bridge.process_and_admit_observation(pkt, is_calibration_valid=True, is_epoch_active=True)
    assert rec.status == EvidenceAdmissionStatus.INVALIDATED


def test_batch_a_d02_stale_data_hash_in_metadata_rejection(tmp_path):
    """D02: Metadata with mismatched core:sha256 must fail closed."""
    tenant = "tenant-d02-stale"
    plot = "plot-d02-stale"
    ns = PlotNamespace(tenant_id=tenant, farm_id="farm-1", plot_id=plot)

    raw = b"sigmf_iq_data_for_stale_test"
    meta = {
        "global": {"core:sample_rate": 20.0e6, "core:hw": "wifi_csi_probe"},
        "captures": [{
            "core:datetime": datetime(2026, 11, 22, 14, 0, 0, tzinfo=timezone.utc).isoformat(),
            "core:frequency": 2.45e9,
        }],
        "annotations": [{"core:sample_count": 10}],
    }
    manifest = ingest_sigmf_capture(tenant, plot, raw, meta, storage_root=tmp_path)

    # Tamper data file
    data_path = Path(manifest.data_path)
    new_data = b"modified_data_bytes_stale_metadata"
    data_path.write_bytes(new_data)
    new_data_sha = hashlib.sha256(new_data).hexdigest()

    # Packet presents new data hash, but metadata has stale core:sha256
    pkt = _packet(uri=data_path.as_uri(), digest=new_data_sha)
    assert not verify_capture_integrity(data_path, expected_namespace=ns, storage_root=tmp_path)
    assert not verify_native_capture_for_plot(pkt, ns, storage_root=tmp_path)


def test_batch_a_d02_missing_or_corrupted_manifest_rejection(tmp_path):
    """D02: Missing or malformed manifest fails closed."""
    tenant = "tenant-d02-man"
    plot = "plot-d02-man"
    ns = PlotNamespace(tenant_id=tenant, farm_id="farm-1", plot_id=plot)

    raw = b"sigmf_iq_data_manifest_test"
    meta = {
        "global": {"core:sample_rate": 20.0e6, "core:hw": "wifi_csi_probe"},
        "captures": [{
            "core:datetime": datetime(2026, 11, 22, 14, 0, 0, tzinfo=timezone.utc).isoformat(),
            "core:frequency": 2.45e9,
        }],
        "annotations": [{"core:sample_count": 10}],
    }
    manifest = ingest_sigmf_capture(tenant, plot, raw, meta, storage_root=tmp_path)
    manifest_file = Path(str(manifest.storage_prefix) + ".manifest.json")
    assert manifest_file.is_file()

    data_file = Path(manifest.data_path)
    pkt = _packet(uri=data_file.as_uri(), digest=manifest.data_sha256)

    # 1. Corrupt manifest JSON
    manifest_file.write_text("NOT_VALID_JSON{{{", encoding="utf-8")
    assert not verify_capture_integrity(data_file, expected_namespace=ns, storage_root=tmp_path)
    assert not verify_native_capture_for_plot(pkt, ns, storage_root=tmp_path)

    # 2. Missing manifest file
    manifest_file.unlink()
    assert not verify_capture_integrity(data_file, expected_namespace=ns, storage_root=tmp_path)
    assert not verify_native_capture_for_plot(pkt, ns, storage_root=tmp_path)


def test_batch_a_d02_inconsistent_capture_id_rejection(tmp_path):
    """D02: Manifest with forged capture_id fails closed."""
    tenant = "tenant-d02-cid"
    plot = "plot-d02-cid"
    ns = PlotNamespace(tenant_id=tenant, farm_id="farm-1", plot_id=plot)

    raw = b"sigmf_iq_data_cid_test"
    meta = {
        "global": {"core:sample_rate": 20.0e6, "core:hw": "wifi_csi_probe"},
        "captures": [{
            "core:datetime": datetime(2026, 11, 22, 14, 0, 0, tzinfo=timezone.utc).isoformat(),
            "core:frequency": 2.45e9,
        }],
        "annotations": [{"core:sample_count": 10}],
    }
    manifest = ingest_sigmf_capture(tenant, plot, raw, meta, storage_root=tmp_path)
    manifest_file = Path(str(manifest.storage_prefix) + ".manifest.json")

    # Forged capture_id in manifest
    man_data = json.loads(manifest_file.read_text(encoding="utf-8"))
    man_data["capture_id"] = "f" * 64
    manifest_file.write_text(json.dumps(man_data), encoding="utf-8")

    data_file = Path(manifest.data_path)
    pkt = _packet(uri=data_file.as_uri(), digest=manifest.data_sha256)
    assert not verify_capture_integrity(data_file, expected_namespace=ns, storage_root=tmp_path)
    assert not verify_native_capture_for_plot(pkt, ns, storage_root=tmp_path)


def test_batch_a_d01_invalid_namespace_identifiers_fail_closed_without_exception(tmp_path):
    """D01: Malformed/adversarial namespace identifiers return False without raising."""
    raw = b"sigmf_iq_data_safe"
    meta = {
        "global": {"core:sample_rate": 20.0e6, "core:hw": "wifi_csi_probe"},
        "captures": [{
            "core:datetime": datetime(2026, 11, 22, 14, 0, 0, tzinfo=timezone.utc).isoformat(),
            "core:frequency": 2.45e9,
        }],
        "annotations": [{"core:sample_count": 10}],
    }
    manifest = ingest_sigmf_capture("tenant-valid", "plot-valid", raw, meta, storage_root=tmp_path)
    data_file = Path(manifest.data_path)
    pkt = _packet(uri=data_file.as_uri(), digest=manifest.data_sha256)

    # Various malformed/adversarial namespace inputs that previously could trigger ValueError in _sanitize_id
    malformed_namespaces = [
        "",
        "   ",
        "../../etc",
        "tenant/../../escape",
        {"tenant_id": "../traversal", "farm_id": "f", "plot_id": "p"},
        {"tenant_id": "t", "farm_id": "f", "plot_id": "p/../escape"},
        PlotNamespace(tenant_id="../../bad_tenant", farm_id="farm", plot_id="plot"),
        PlotNamespace(tenant_id="tenant", farm_id="farm", plot_id="bad\x00plot"),
        None,
        12345,
    ]

    for bad_ns in malformed_namespaces:
        result = verify_native_capture_for_plot(pkt, bad_ns, storage_root=tmp_path)
        assert result is False, f"Expected False for {bad_ns!r}, got {result}"


def test_batch_a_d02_manifest_storage_prefix_mismatch_rejection(tmp_path):
    """D02: Manifest with mismatched storage_prefix fails closed."""
    tenant = "tenant-d02-prefix"
    plot = "plot-d02-prefix"
    ns = PlotNamespace(tenant_id=tenant, farm_id="farm-1", plot_id=plot)

    raw = b"sigmf_iq_data_prefix_test"
    meta = {
        "global": {"core:sample_rate": 20.0e6, "core:hw": "wifi_csi_probe"},
        "captures": [{
            "core:datetime": datetime(2026, 11, 22, 14, 0, 0, tzinfo=timezone.utc).isoformat(),
            "core:frequency": 2.45e9,
        }],
        "annotations": [{"core:sample_count": 10}],
    }
    manifest = ingest_sigmf_capture(tenant, plot, raw, meta, storage_root=tmp_path)
    manifest_file = Path(str(manifest.storage_prefix) + ".manifest.json")

    # Tamper storage_prefix in manifest to point elsewhere
    man_data = json.loads(manifest_file.read_text(encoding="utf-8"))
    man_data["storage_prefix"] = str(tmp_path / "other_tenant" / "other_plot" / manifest.capture_id)
    manifest_file.write_text(json.dumps(man_data), encoding="utf-8")

    data_file = Path(manifest.data_path)
    pkt = _packet(uri=data_file.as_uri(), digest=manifest.data_sha256)
    assert not verify_capture_integrity(data_file, expected_namespace=ns, storage_root=tmp_path)
    assert not verify_native_capture_for_plot(pkt, ns, storage_root=tmp_path)


def test_batch_a_d02_manifest_timestamp_mismatch_rejection(tmp_path):
    """D02: Desynchronized capture_timestamp_utc between manifest and SigMF meta fails closed."""
    tenant = "tenant-d02-time"
    plot = "plot-d02-time"
    ns = PlotNamespace(tenant_id=tenant, farm_id="farm-1", plot_id=plot)

    raw = b"sigmf_iq_data_time_test"
    meta = {
        "global": {"core:sample_rate": 20.0e6, "core:hw": "wifi_csi_probe"},
        "captures": [{
            "core:datetime": datetime(2026, 11, 22, 14, 0, 0, tzinfo=timezone.utc).isoformat(),
            "core:frequency": 2.45e9,
        }],
        "annotations": [{"core:sample_count": 10}],
    }
    manifest = ingest_sigmf_capture(tenant, plot, raw, meta, storage_root=tmp_path)
    manifest_file = Path(str(manifest.storage_prefix) + ".manifest.json")

    # Alter timestamp in manifest while leaving meta unchanged
    man_data = json.loads(manifest_file.read_text(encoding="utf-8"))
    man_data["capture_timestamp_utc"] = datetime(2026, 11, 22, 18, 0, 0, tzinfo=timezone.utc).isoformat()
    manifest_file.write_text(json.dumps(man_data), encoding="utf-8")

    data_file = Path(manifest.data_path)
    pkt = _packet(uri=data_file.as_uri(), digest=manifest.data_sha256)
    assert not verify_capture_integrity(data_file, expected_namespace=ns, storage_root=tmp_path)
    assert not verify_native_capture_for_plot(pkt, ns, storage_root=tmp_path)


# =============================================================================
# BATCH B ADVERSARIAL COVERAGE — D03 (Cryptographic Capability Governance)
# =============================================================================

from dataclasses import replace
from datetime import timedelta
from cryptography.hazmat.primitives.asymmetric import ed25519
from services.agribrain.mesia.contracts.authority import CapabilityAuthorityRecord
from services.agribrain.mesia.assimilation.capability_governance import (
    CapabilityGovernanceAuthority,
    DEFAULT_CAPABILITY_ISSUER,
    provision_test_capability_issuer_keypair,
    get_test_capability_private_key,
    register_trusted_capability_issuer,
    verify_capability_authority,
    sign_capability_record,
    clear_capability_revocations_for_tests,
)


def _valid_d03_capability(**kwargs) -> CapabilityAuthorityRecord:
    """Helper creating a fully qualified, cryptographically signed CapabilityAuthorityRecord."""
    params = dict(
        capability_id="CAP_TEST_SOIL_V1",
        capability_name="WiFi Soil Moisture",
        target_variable="root_zone_water",
        supported_radios=["WIFI_CSI"],
        supported_soils=["LOAM"],
        supported_crops=["CITRUS"],
        gate_repeatability_passed=True,
        gate_sensitivity_passed=True,
        gate_specificity_passed=True,
        gate_observability_passed=True,
        gate_transfer_passed=True,
        gate_closure_passed=True,
        gate_incremental_value_passed=True,
        gate_governance_passed=True,
        validation_signature="SIG_AUDIT_APPROVED_2026",
    )
    params.update(kwargs)
    return CapabilityGovernanceAuthority.issue_qualification_record(**params)


def test_batch_b_d03_valid_capability_authorizes_and_registers():
    """D03: Properly qualified, signed, unexpired capability registers successfully."""
    clear_capability_revocations_for_tests()
    cap = _valid_d03_capability(capability_id="CAP_VALID_01")
    assert cap.state == "QUALIFIED"
    assert cap.signature is not None
    assert cap.signature.startswith("ed25519:")
    assert cap.all_gates_passed is True

    is_valid, msg = verify_capability_authority(cap)
    assert is_valid is True, msg

    bridge = MesiaAgriBrainBridge(plot_id="PLOT_D03_VALID")
    bridge.register_capability(cap)
    active = bridge.list_active_capabilities()
    assert len(active) == 1
    assert active[0].capability_id == "CAP_VALID_01"


def test_batch_b_d03_unsigned_capability_rejected_at_registration():
    """D03: Unsigned capability authority record fails closed on registration."""
    clear_capability_revocations_for_tests()
    cap = _valid_d03_capability(capability_id="CAP_UNSIGNED_01")
    # Strip signature
    cap_unsigned = replace(cap, signature=None)

    is_valid, reason = verify_capability_authority(cap_unsigned)
    assert is_valid is False
    assert "Missing or invalid Ed25519 signature prefix" in reason

    bridge = MesiaAgriBrainBridge(plot_id="PLOT_D03_UNSIGNED")
    with pytest.raises(ValueError, match="Capability registration rejected \\(D03\\)"):
        bridge.register_capability(cap_unsigned)


def test_batch_b_d03_forged_or_tampered_signature_rejected():
    """D03: Tampered Ed25519 signature bytes fail closed."""
    clear_capability_revocations_for_tests()
    cap = _valid_d03_capability(capability_id="CAP_FORGED_SIG_01")
    orig_sig = cap.signature
    assert orig_sig is not None

    # Tamper with the signature hex by flipping a character
    tampered_sig = orig_sig[:-2] + ("00" if orig_sig[-2:] != "00" else "ff")
    cap_forged = replace(cap, signature=tampered_sig)

    is_valid, reason = verify_capability_authority(cap_forged)
    assert is_valid is False
    assert "signature verification failed" in reason.lower()

    bridge = MesiaAgriBrainBridge(plot_id="PLOT_D03_FORGED")
    with pytest.raises(ValueError, match="Capability registration rejected \\(D03\\)"):
        bridge.register_capability(cap_forged)


def test_batch_b_d03_tampered_canonical_payload_rejected():
    """D03: Valid signature over altered canonical content fails closed."""
    clear_capability_revocations_for_tests()
    cap = _valid_d03_capability(capability_id="CAP_TAMPERED_BODY_01")

    # Tamper with target variable after signature was generated
    cap_tampered = replace(cap, target_variable="salinity_stress")

    is_valid, reason = verify_capability_authority(cap_tampered)
    assert is_valid is False
    assert "signature verification failed" in reason.lower()

    bridge = MesiaAgriBrainBridge(plot_id="PLOT_D03_TAMPERED")
    with pytest.raises(ValueError, match="Capability registration rejected \\(D03\\)"):
        bridge.register_capability(cap_tampered)


def test_batch_b_d03_untrusted_issuer_rejected():
    """D03: Capability signed by an unprovisioned or untrusted issuer fails closed."""
    clear_capability_revocations_for_tests()
    rogue_priv = ed25519.Ed25519PrivateKey.generate()
    cap_base = _valid_d03_capability(capability_id="CAP_ROGUE_01")

    # Sign with rogue key under untrusted issuer name
    cap_rogue = sign_capability_record(
        cap_base, rogue_priv, issuer_id="agriwise:trust:unauthorized_rogue_entity"
    )

    is_valid, reason = verify_capability_authority(cap_rogue)
    assert is_valid is False
    assert "Untrusted or unprovisioned capability issuer" in reason

    bridge = MesiaAgriBrainBridge(plot_id="PLOT_D03_ROGUE")
    with pytest.raises(ValueError, match="Untrusted or unprovisioned capability issuer"):
        bridge.register_capability(cap_rogue)


def test_batch_b_d03_expired_capability_rejected_and_excluded_from_active():
    """D03: Expired capability authority is rejected and drops from active enumeration."""
    clear_capability_revocations_for_tests()
    now = datetime.now(timezone.utc)
    expired_time = now - timedelta(days=1)
    priv = get_test_capability_private_key(DEFAULT_CAPABILITY_ISSUER)
    assert priv is not None

    cap_base = _valid_d03_capability(capability_id="CAP_EXPIRED_01")
    cap_expired = sign_capability_record(cap_base, priv, expires_at=expired_time)

    # 1. Registration fails closed for already-expired capability
    is_valid, reason = verify_capability_authority(cap_expired)
    assert is_valid is False
    assert "expired" in reason.lower()

    bridge = MesiaAgriBrainBridge(plot_id="PLOT_D03_EXP")
    with pytest.raises(ValueError, match="Capability registration rejected \\(D03\\)"):
        bridge.register_capability(cap_expired)

    # 2. Dynamic runtime expiration exclusion
    cap_valid = _valid_d03_capability(capability_id="CAP_VALID_EXP_01")
    bridge.register_capability(cap_valid)
    assert len(bridge.list_active_capabilities()) == 1

    # Simulate future time past expiration
    future_time = now + timedelta(days=365)
    is_still_valid, future_reason = verify_capability_authority(cap_valid, current_time=future_time)
    assert is_still_valid is False
    assert "expired" in future_reason.lower()


def test_batch_b_d03_future_issuance_rejected():
    """D03: Capability with post-dated issued_at fails closed."""
    clear_capability_revocations_for_tests()
    future_issued = datetime.now(timezone.utc) + timedelta(days=7)
    priv = get_test_capability_private_key(DEFAULT_CAPABILITY_ISSUER)
    assert priv is not None

    cap_base = _valid_d03_capability(capability_id="CAP_FUTURE_01")
    cap_future_unsigned = replace(cap_base, issued_at=future_issued)
    cap_future = sign_capability_record(cap_future_unsigned, priv)

    is_valid, reason = verify_capability_authority(cap_future)
    assert is_valid is False
    assert "in the future" in reason.lower()

    bridge = MesiaAgriBrainBridge(plot_id="PLOT_D03_FUT")
    with pytest.raises(ValueError, match="Capability registration rejected \\(D03\\)"):
        bridge.register_capability(cap_future)


def test_batch_b_d03_incomplete_gates_rejected_even_if_signed():
    """D03: Missing even one of the 8 qualification gates fails closed."""
    clear_capability_revocations_for_tests()
    priv = get_test_capability_private_key(DEFAULT_CAPABILITY_ISSUER)
    assert priv is not None

    # gate_closure_passed=False
    cap_incomplete = CapabilityGovernanceAuthority.issue_qualification_record(
        capability_id="CAP_INCOMPLETE_GATES_01",
        capability_name="Incomplete Gates Cap",
        target_variable="root_zone_water",
        supported_radios=["WIFI_CSI"],
        supported_soils=["LOAM"],
        supported_crops=["CITRUS"],
        gate_repeatability_passed=True,
        gate_sensitivity_passed=True,
        gate_specificity_passed=True,
        gate_observability_passed=True,
        gate_transfer_passed=True,
        gate_closure_passed=False,  # Failed gate!
        gate_incremental_value_passed=True,
        gate_governance_passed=True,
        validation_signature="SIG_AUDIT_APPROVED_2026",
    )
    assert cap_incomplete.state == "UNQUALIFIED_PENDING_EVIDENCE"
    assert cap_incomplete.signature is None

    # Even if an adversary forces state='QUALIFIED' and signs with valid key:
    cap_forced = replace(cap_incomplete, state="QUALIFIED")
    cap_forced_signed = sign_capability_record(cap_forced, priv)

    is_valid, reason = verify_capability_authority(cap_forced_signed)
    assert is_valid is False
    assert "Not all 8 qualification gates passed" in reason

    bridge = MesiaAgriBrainBridge(plot_id="PLOT_D03_GATES")
    with pytest.raises(ValueError, match="Not all 8 qualification gates passed"):
        bridge.register_capability(cap_forced_signed)


def test_batch_b_d03_empty_or_wildcard_target_variable_rejected():
    """D03: Principle P-09: Clusters are never globally certified; empty or wildcard target variable fails closed."""
    clear_capability_revocations_for_tests()
    priv = get_test_capability_private_key(DEFAULT_CAPABILITY_ISSUER)
    assert priv is not None

    for invalid_target in ["", "   ", "*", "ALL", "GLOBAL", "UNSPECIFIED_PENDING_CALIBRATED_OPERATOR"]:
        cap = _valid_d03_capability(capability_id=f"CAP_INV_TARGET_{hash(invalid_target)}")
        cap_inv = replace(cap, target_variable=invalid_target)
        cap_inv_signed = sign_capability_record(cap_inv, priv)

        is_valid, reason = verify_capability_authority(cap_inv_signed)
        assert is_valid is False, f"Expected invalid for target {invalid_target!r}"
        assert "explicit target variable required" in reason

        bridge = MesiaAgriBrainBridge(plot_id="PLOT_D03_TARGET")
        with pytest.raises(ValueError, match="explicit target variable required"):
            bridge.register_capability(cap_inv_signed)


def test_batch_b_d03_prohibited_actuation_use_rejected():
    """D03: Prohibit autonomous actuation and authoritative state mutation in allowed_uses."""
    clear_capability_revocations_for_tests()
    priv = get_test_capability_private_key(DEFAULT_CAPABILITY_ISSUER)
    assert priv is not None

    for forbidden_use in ["AUTONOMOUS_ACTUATION", "AUTHORITATIVE_STATE_MUTATION", "AUTONOMOUS_IRRIGATION"]:
        cap = _valid_d03_capability(capability_id=f"CAP_FORBIDDEN_{hash(forbidden_use)}")
        cap_bad = replace(cap, allowed_uses=["RESEARCH_ONLY", forbidden_use])
        cap_bad_signed = sign_capability_record(cap_bad, priv)

        is_valid, reason = verify_capability_authority(cap_bad_signed)
        assert is_valid is False, f"Expected invalid for use {forbidden_use!r}"
        assert "Forbidden use" in reason

        bridge = MesiaAgriBrainBridge(plot_id="PLOT_D03_USE")
        with pytest.raises(ValueError, match="Forbidden use"):
            bridge.register_capability(cap_bad_signed)


def test_batch_b_d03_revoked_capability_immediately_withdrawn():
    """D03 / P-10: Revoking a capability transitions state and excludes it from active enumeration."""
    clear_capability_revocations_for_tests()
    cap = _valid_d03_capability(capability_id="CAP_TO_BE_REVOKED_01")
    bridge = MesiaAgriBrainBridge(plot_id="PLOT_D03_REV")
    bridge.register_capability(cap)
    assert len(bridge.list_active_capabilities()) == 1

    rev_event = bridge.revoke_capability("CAP_TO_BE_REVOKED_01", trigger_reason="Closure error threshold exceeded")
    assert rev_event is not None
    assert rev_event.new_state == "REVOKED"
    assert rev_event.capability_authority_ref == "CAP_TO_BE_REVOKED_01"

    # Active capabilities list must immediately be empty
    assert len(bridge.list_active_capabilities()) == 0

    # Verification must fail closed
    is_valid, reason = verify_capability_authority(cap)
    assert is_valid is False
    assert "revoked" in reason.lower()


def test_batch_b_d03_mesia_bridge_withholds_agricultural_state_mutation(tmp_path):
    """D03: Verified SigMF capture under active capability strictly withholds agricultural state mutation."""
    clear_capability_revocations_for_tests()
    tenant = "tenant-d03-assim"
    plot = "plot-d03-assim"
    ns = PlotNamespace(tenant_id=tenant, farm_id="farm-d03", plot_id=plot)

    raw = b"physical_radio_csi_iq_bytes_batch_b"
    meta = {
        "global": {"core:sample_rate": 20.0e6, "core:hw": "wifi_csi_probe_v2"},
        "captures": [{
            "core:datetime": datetime(2026, 11, 22, 16, 0, 0, tzinfo=timezone.utc).isoformat(),
            "core:frequency": 2.437e9,
        }],
        "annotations": [{"core:sample_count": 16}],
    }
    manifest = ingest_sigmf_capture(tenant, plot, raw, meta, storage_root=tmp_path)
    data_file = Path(manifest.data_path)
    pkt = _packet(uri=data_file.as_uri(), digest=manifest.data_sha256, profile="WIFI_CSI/v2", role="SENSING")

    bridge = MesiaAgriBrainBridge(plot_namespace=ns, storage_root=tmp_path)

    # Register qualified capability for WIFI_CSI root_zone_water
    cap = _valid_d03_capability(capability_id="CAP_ASSIM_HOLD_01")
    bridge.register_capability(cap)
    assert len(bridge.list_active_capabilities()) == 1

    # Ingest packet with valid calibration and epoch
    l0_rec, asmae_event = bridge.process_and_admit_observation(
        pkt, is_calibration_valid=True, is_epoch_active=True,
    )

    # Invariants:
    # 1. Native capture is physically verified
    assert verify_native_capture_for_plot(pkt, ns, storage_root=tmp_path) is True
    # 2. Observation innovation is ABSENT (uncalibrated physical inversion withheld)
    assert l0_rec.status == EvidenceAdmissionStatus.ABSENT
    assert l0_rec.is_usable_for_assimilation is False
    # 3. No agricultural state update authority is granted
    assert asmae_event is None

