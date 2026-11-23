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
    directory = tmp_path / "tenant-1" / "farm-1" / "plot-1"
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

    raw_data = b"01234567" * 8
    meta = {
        "global": {"core:datatype": "cf32_le", "core:sample_rate": 20.0e6, "core:hw": "wifi_csi_rx_fixture"},
        "captures": [{
            "core:datetime": datetime(2026, 11, 22, 12, 0, 0, tzinfo=timezone.utc).isoformat(),
            "core:frequency": 2.437e9,
        }],
        "annotations": [{"core:sample_count": 8}],
    }
    manifest_b = ingest_sigmf_capture(
        tenant_id=tenant_b,
        farm_id="farm-b",
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

    raw = b"01234567" * 4
    meta = {
        "global": {"core:datatype": "cf32_le", "core:sample_rate": 10.0e6, "core:hw": "usrp_b210"},
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

    raw = b"01234567" * 10
    meta = {
        "global": {"core:datatype": "cf32_le", "core:sample_rate": 20.0e6, "core:hw": "wifi_csi_probe"},
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

    raw = b"01234567" * 10
    meta = {
        "global": {"core:datatype": "cf32_le", "core:sample_rate": 20.0e6, "core:hw": "wifi_csi_probe"},
        "captures": [{
            "core:datetime": datetime(2026, 11, 22, 14, 0, 0, tzinfo=timezone.utc).isoformat(),
            "core:frequency": 2.45e9,
        }],
        "annotations": [{"core:sample_count": 10}],
    }
    manifest = ingest_sigmf_capture(tenant, plot, raw, meta, storage_root=tmp_path)

    # Tamper data file
    data_path = Path(manifest.data_path)
    new_data = b"ABCDEFGH" * 10
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

    raw = b"01234567" * 10
    meta = {
        "global": {"core:datatype": "cf32_le", "core:sample_rate": 20.0e6, "core:hw": "wifi_csi_probe"},
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

    raw = b"01234567" * 10
    meta = {
        "global": {"core:datatype": "cf32_le", "core:sample_rate": 20.0e6, "core:hw": "wifi_csi_probe"},
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
    raw = b"01234567" * 10
    meta = {
        "global": {"core:datatype": "cf32_le", "core:sample_rate": 20.0e6, "core:hw": "wifi_csi_probe"},
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

    raw = b"01234567" * 10
    meta = {
        "global": {"core:datatype": "cf32_le", "core:sample_rate": 20.0e6, "core:hw": "wifi_csi_probe"},
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

    raw = b"01234567" * 10
    meta = {
        "global": {"core:datatype": "cf32_le", "core:sample_rate": 20.0e6, "core:hw": "wifi_csi_probe"},
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


def test_legacy_capture_rejected_for_non_default_farm(tmp_path):
    """P1 Regression: Legacy captures (default_farm / 2-level) cannot cross boundaries to non-default farms."""
    from services.agribrain.mesia.service import MesiaProductionService

    tenant = "tenant-legacy-cross"
    plot = "plot-legacy-cross"
    # Legacy ingestion without farm_id (defaults to default_farm, writes to tenant/plot/)
    raw = b"01234567" * 10
    meta = {
        "global": {"core:datatype": "cf32_le", "core:sample_rate": 20.0e6, "core:hw": "wifi_csi_probe"},
        "captures": [{
            "core:datetime": datetime(2026, 11, 22, 14, 0, 0, tzinfo=timezone.utc).isoformat(),
            "core:frequency": 2.45e9,
        }],
        "annotations": [{"core:sample_count": 10}],
    }
    manifest = ingest_sigmf_capture(tenant, plot, raw, meta, storage_root=tmp_path)
    data_file = Path(manifest.data_path)

    # 1. Non-default farm namespace: farm-east
    ns_non_default = PlotNamespace(tenant_id=tenant, farm_id="farm-east", plot_id=plot)
    pkt = _packet(uri=data_file.as_uri(), digest=manifest.data_sha256)

    # Verifier must reject legacy capture for non-default farm
    assert not verify_capture_integrity(data_file, expected_namespace=ns_non_default, storage_root=tmp_path)
    assert not verify_native_capture_for_plot(pkt, ns_non_default, storage_root=tmp_path)

    # Bridge admission must yield INVALIDATED for non-default farm
    bridge_non_default = MesiaAgriBrainBridge(plot_namespace=ns_non_default, storage_root=tmp_path)
    rec, ev = bridge_non_default.process_and_admit_observation(pkt, is_calibration_valid=True, is_epoch_active=True)
    assert rec.status == EvidenceAdmissionStatus.INVALIDATED

    # In-situ scanner must not find or use legacy capture for non-default farm
    scan_res = MesiaProductionService._process_real_in_situ_wifi_csi(plot_namespace=ns_non_default, storage_root=tmp_path)
    assert scan_res["status"] == "AWAITING_FIELD_RECEIVER_STREAM"

    # 2. Positive control: Authenticated default_farm request accepts the legacy capture
    ns_default = PlotNamespace(tenant_id=tenant, farm_id="default_farm", plot_id=plot)
    assert verify_capture_integrity(data_file, expected_namespace=ns_default, storage_root=tmp_path)
    assert verify_native_capture_for_plot(pkt, ns_default, storage_root=tmp_path)
