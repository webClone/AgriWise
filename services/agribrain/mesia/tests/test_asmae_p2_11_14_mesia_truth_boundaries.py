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
    assert not verify_native_capture_for_plot(
        _packet(uri, "a" * 64), "plot-1", storage_root=tmp_path,
    )


def test_p2_11_actual_sha256_match_requires_plot_and_tenant_scoped_file(tmp_path):
    directory = tmp_path / "tenant-1" / "plot-1"
    directory.mkdir(parents=True)
    raw = b"$GPRMC,20261121,24.5,SNR,37.4\r\n"
    real_file = directory / "capture.nmea"
    real_file.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    good = _packet(real_file.as_uri(), digest)
    assert verify_native_capture_for_plot(good, "plot-1", storage_root=tmp_path)
    assert not verify_native_capture_for_plot(good, "foreign-plot", storage_root=tmp_path)
    assert not verify_native_capture_for_plot(
        _packet(real_file.as_uri(), "0" * 64), "plot-1", storage_root=tmp_path
    )
    real_file.write_bytes(b"tampered")
    assert not verify_native_capture_for_plot(good, "plot-1", storage_root=tmp_path)


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
    bridge = MesiaAgriBrainBridge(plot_id="plot-1")
    with pytest.raises(ValueError, match="Principle P-08"):
        bridge.process_and_admit_observation(
            _packet("file:///nonexistent.raw", "a"*64, scope="STATE_UPDATE"),
            is_calibration_valid=True, is_epoch_active=True,
        )


def test_p2_11_nonexistent_hash_address_never_admitted_with_valid_flags():
    bridge = MesiaAgriBrainBridge(plot_id="plot-1")
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
    assert '"native_capture_present"] = verify_native_capture_for_plot(packet, plot_id)' in source


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
