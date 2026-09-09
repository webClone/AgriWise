"""Automated Test Suite for MESIA Truth Governance, Evidence Taxonomy, Metrology, and Security Hardening.

Verifies:
1. TruthEnvelope immutability, field structure, and decision eligibility rejection.
2. SourceConfirmationReceipt hierarchy and metadata integrity.
3. NmeaCycleAssembler XOR checksum validation, multipart cycle assembly, compound keying, and time anchoring.
4. SigMF complex float (cf32_le) real/imag interleaving.
5. Strict parcel isolation (no cross-plot NMEA fallback).
6. Non-evaluated dual closure when no physical observation is withheld.
7. Principle P-08 advisory proposals (decision_eligible: False, RESEARCH_ONLY).
8. FastAPI route security rejecting client-supplied tenant_id / farm_id.
"""

import pytest
import numpy as np
import math
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

from services.agribrain.mesia.ontology.evidence_taxonomy import (
    SourceClass,
    ProcessingLevel,
    AuthorityState,
    PresentationState,
    TruthEnvelope,
)
from services.agribrain.mesia.ontology.identity_states import IdentityState
from services.agribrain.mesia.contracts.scientific import (
    ClosureStatus,
    ClosureCertificate,
)
from services.agribrain.mesia.contracts.receipts import (
    SourceConfirmationReceipt,
    ProtocolConfirmationReceipt,
    SatelliteObservationReceipt,
    RemoteProductReceipt,
    ModelContextReceipt,
)
from services.agribrain.mesia.lanes.gnss.nmea_assembler import NmeaCycleAssembler
from services.agribrain.mesia.lanes.wifi.csi_extractor import NativeWifiCsiExtractor
from services.agribrain.mesia.service import MesiaProductionService
from services.agribrain.common.plot_namespace import PlotNamespace


def test_truth_envelope_structure_and_immutability():
    """Verify TruthEnvelope is frozen, serializable, and enforces scientific governance."""
    env = TruthEnvelope(
        value=21.5,
        unit="% VWC",
        source_class=SourceClass.SIMULATOR,
        processing_level=ProcessingLevel.DERIVED,
        identity_state=IdentityState.UNKNOWN,
        authority_state=AuthorityState.RESEARCH_ONLY,
        presentation_state=PresentationState.SIMULATION,
        software_epoch_ref="mesia-r6.1",
        observed_at=datetime.now(timezone.utc),
        valid_for_seconds=3600.0,
        uncertainty=0.05,
        decision_eligible=False,
        explanation="Theoretical forward-modeled simulation.",
        parent_envelope_refs=("PARENT_ENV_001",),
    )
    d = env.to_dict()
    assert d["source_class"] == "SIMULATOR"
    assert d["processing_level"] == "DERIVED"
    assert d["authority_state"] == "RESEARCH_ONLY"
    assert d["decision_eligible"] is False

    # Immutability check (frozen dataclass cannot be mutated)
    with pytest.raises(Exception):
        env.decision_eligible = True  # type: ignore


def test_receipt_schemas_and_hashing():
    """Verify source receipts generate valid content hashes and metadata."""
    now_dt = datetime.now(timezone.utc)
    rec = ProtocolConfirmationReceipt(
        receipt_id="REC_WIFI_001",
        source_type="PHYSICAL_RECEIVER",
        hardware_id="ESP32_S3_PERIMETER_01",
        timestamp_utc=now_dt,
        content_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        protocol_name="802.11bf-CSI",
        frame_type="NDP_ANNOUNCEMENT",
        station_or_cell_id="AP_FARMSTEAD_HQ",
        crc_passed=True,
        channel_freq_hz=2437.0e6,
        snr_db=38.5,
    )
    d = rec.to_dict()
    assert d["protocol_name"] == "802.11bf-CSI"
    assert d["station_or_cell_id"] == "AP_FARMSTEAD_HQ"
    assert d["crc_passed"] is True
    assert len(d["content_hash"]) == 64


def test_nmea_cycle_assembler_checksum_validation():
    """Verify NmeaCycleAssembler validates XOR checksums and rejects corrupted sentences."""
    valid_sentence = "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"
    assert NmeaCycleAssembler.verify_xor_checksum(valid_sentence) is True

    corrupted_sentence = "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*99"
    assert NmeaCycleAssembler.verify_xor_checksum(corrupted_sentence) is False

    # Verify stream parser rejects corrupt sentences when enforce_checksum is True
    raw_stream = f"{corrupted_sentence}\r\n"
    obs, meta = NmeaCycleAssembler.assemble_nmea_stream(raw_stream, enforce_checksum=True)
    assert len(obs) == 0
    assert meta["corrupted_sentence_count"] == 1


def test_nmea_cycle_assembler_multipart_gsv_and_compound_keys():
    """Verify NmeaCycleAssembler handles multi-sentence GSV cycles with compound keys."""
    # Compute authentic checksums for a 2-part GSV cycle
    s1_body = "GPGSV,2,1,08,01,40,083,42,02,17,308,38,03,12,045,35,04,65,120,46"
    s2_body = "GPGSV,2,2,08,05,52,210,44,06,20,180,39,07,08,095,,08,35,270,41"
    
    def format_nmea(body):
        c = 0
        for ch in body:
            c ^= ord(ch)
        return f"${body}*{c:02X}"

    s1 = format_nmea(s1_body)
    s2 = format_nmea(s2_body)
    stream = f"{s1}\r\n{s2}\r\n"

    obs, meta = NmeaCycleAssembler.assemble_nmea_stream(stream, enforce_checksum=True)
    assert meta["corrupted_sentence_count"] == 0
    assert meta["valid_checksum_count"] == 2
    assert len(obs) == 8

    # PRN 07 had an empty SNR in sentence 2 -> must be None, NOT 0.0 or fabricated
    prn7 = next(o for o in obs if o.satellite_prn == 7)
    assert prn7.snr_db_hz is None
    assert prn7.constellation == "GPS"

    # PRN 01 has valid SNR 42.0
    prn1 = next(o for o in obs if o.satellite_prn == 1)
    assert prn1.snr_db_hz == 42.0


def test_wifi_sigmf_complex_float_packing():
    """Verify SigMF cf32_le packing stores real and imaginary interleaved floats."""
    amplitudes = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    phases = np.array([0.0, math.pi / 2.0, math.pi], dtype=np.float32)

    raw_bytes = NativeWifiCsiExtractor.pack_sigmf_cf32_le(amplitudes, phases)
    # 3 subcarriers * 2 floats (real, imag) * 4 bytes per float = 24 bytes
    assert len(raw_bytes) == 24

    floats = np.frombuffer(raw_bytes, dtype=np.float32)
    assert len(floats) == 6

    # Subcarrier 0: amp=1.0, phase=0 -> real=1.0, imag=0.0
    assert abs(floats[0] - 1.0) < 1e-5
    assert abs(floats[1] - 0.0) < 1e-5

    # Subcarrier 1: amp=2.0, phase=pi/2 -> real=0.0, imag=2.0
    assert abs(floats[2] - 0.0) < 1e-5
    assert abs(floats[3] - 2.0) < 1e-5

    # Subcarrier 2: amp=3.0, phase=pi -> real=-3.0, imag=0.0
    assert abs(floats[4] - (-3.0)) < 1e-5
    assert abs(floats[5] - 0.0) < 1e-5


def test_strict_parcel_isolation():
    """Verify a plot without in-situ NMEA returns AWAITING_FIELD_RECEIVER_STREAM, with no cross-plot fallback."""
    res = MesiaProductionService._process_real_in_situ_gnss("non_existent_plot_xyz_999")
    assert res["status"] == "AWAITING_FIELD_RECEIVER_STREAM"
    assert res["physical_waves_measured"] is False


def test_dual_closure_not_evaluated_without_physical_holdout():
    """Verify dual closure cannot be claimed without an authentic withheld physical observation."""
    val = MesiaProductionService._evaluate_validation_loop(
        real_grid=None,
        unc_grid=None,
        mean_cwi=0.10,
        vwc_surface=0.18,
        vwc_rootzone=0.22,
        vwc_deeproot=0.25,
        cygnss_refl_db=-14.2,
    )
    # Must be marked NOT_EVALUATED and dual_closure_verified False
    assert val["independent_dual_closure"] == "NOT_EVALUATED"
    assert val["dual_closure_verified"] is False
    assert "MODEL_SELF_CONSISTENCY_ONLY" in val["rf_holdout_validation"]["status"]
    assert isinstance(val["model_self_consistency_passed"], bool)


def test_asmae_proposals_advisory_only():
    """Verify all ASMAE proposals generated by MESIA are tagged decision_eligible: False and RESEARCH_ONLY."""
    res = MesiaProductionService.scan_plot_spectrum(
        plot_id="test_plot_governance",
        polygon_wgs84=[(36.5, 3.0), (36.5, 3.01), (36.49, 3.01), (36.49, 3.0)],
        soil_type="CLAY",
    )
    proposals = res.get("asmae_p08_proposals", [])
    assert len(proposals) > 0
    for p in proposals:
        assert p["authority_scope"] in ("RESEARCH_ONLY", "unqualified_research_proposal")
        assert p["decision_eligible"] is False
        assert p["truth_envelope"]["authority_state"] == "RESEARCH_ONLY"
        assert p["truth_envelope"]["decision_eligible"] is False


def test_truth_envelopes_injected_in_observatory_scan():
    """Verify primary observables in scan_plot_spectrum carry machine-enforced TruthEnvelopes."""
    res = MesiaProductionService.scan_plot_spectrum(
        plot_id="test_plot_governance",
        polygon_wgs84=[(36.5, 3.0), (36.5, 3.01), (36.49, 3.01), (36.49, 3.0)],
        soil_type="CLAY",
    )
    assert "truth_envelopes" in res
    envs = res["truth_envelopes"]
    assert "topsoil_moisture" in envs
    assert envs["topsoil_moisture"]["source_class"] == "NWP_MODEL"
    assert envs["topsoil_moisture"]["decision_eligible"] is False

    assert "rootzone_moisture" in envs
    assert envs["rootzone_moisture"]["source_class"] == "NWP_MODEL"

    assert "deep_subsoil_moisture" in envs
    assert envs["deep_subsoil_moisture"]["source_class"] == "SIMULATOR"

    assert "dual_closure_validation" in envs
    assert envs["dual_closure_validation"]["value"] == "NOT_EVALUATED"


def test_fastapi_endpoints_reject_client_spoofed_identity():
    """Verify FastAPI routes reject client payload attempts to pass farm_id or tenant_id."""
    from fastapi.testclient import TestClient
    from services.agribrain.app.main import app, require_internal_service_request

    client = TestClient(app)

    # Dependency override simulating authenticated internal service request
    fake_namespace = PlotNamespace(tenant_id="tenant_authed", farm_id="farm_authed", plot_id="plot_authed")
    app.dependency_overrides[require_internal_service_request] = lambda: fake_namespace

    try:
        # 1. Reject spoofed tenant_id in post_mesia_spectrum_observatory
        bad_payload = {"tenant_id": "malicious_tenant", "soil_type": "CLAY"}
        resp = client.post("/v2/mesia/plot_authed", json=bad_payload)
        assert resp.status_code == 400
        assert "Authority is derived exclusively from authenticated tokens" in resp.json()["detail"]

        # 2. Reject spoofed farm_id in simulate_mesia_wifi_csi
        bad_wifi = {"farm_id": "malicious_farm", "ap_distance_m": 30.0}
        resp2 = client.post("/v2/mesia/simulate-wifi-csi", json=bad_wifi)
        assert resp2.status_code == 400
        assert "Authority is derived exclusively from authenticated tokens" in resp2.json()["detail"]

        # 3. Reject spoofed tenant_id in ingest_nmea
        bad_nmea = {"tenant_id": "malicious_tenant", "nmea_text": "$GPGGA*47"}
        resp3 = client.post("/v2/mesia/ingest-nmea", json=bad_nmea)
        assert resp3.status_code == 400
        assert "Authority is derived exclusively from authenticated tokens" in resp3.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_truth_envelope_impossible_combinations():
    """Verify machine-enforced TruthEnvelope invariants reject impossible taxonomy combinations."""
    now_dt = datetime.now(timezone.utc)

    # 1. Reject SIMULATOR claiming LIVE presentation state
    with pytest.raises(ValueError, match="SIMULATOR cannot have LIVE presentation state"):
        TruthEnvelope(
            value=20.0,
            unit="%",
            source_class=SourceClass.SIMULATOR,
            processing_level=ProcessingLevel.NATIVE,
            identity_state=IdentityState.UNKNOWN,
            authority_state=AuthorityState.RESEARCH_ONLY,
            presentation_state=PresentationState.LIVE,
            software_epoch_ref="test-v1",
            observed_at=now_dt,
            valid_for_seconds=60.0,
            uncertainty=0.1,
            decision_eligible=False,
            explanation="Invalid envelope",
        )

    # 2. Reject NWP_MODEL claiming LIVE presentation state
    with pytest.raises(ValueError, match="NWP_MODEL cannot have LIVE presentation state"):
        TruthEnvelope(
            value=20.0,
            unit="%",
            source_class=SourceClass.NWP_MODEL,
            processing_level=ProcessingLevel.NATIVE,
            identity_state=IdentityState.UNKNOWN,
            authority_state=AuthorityState.RESEARCH_ONLY,
            presentation_state=PresentationState.LIVE,
            software_epoch_ref="test-v1",
            observed_at=now_dt,
            valid_for_seconds=60.0,
            uncertainty=0.1,
            decision_eligible=False,
            explanation="Invalid envelope",
        )

    # 3. Reject DERIVED without parent_envelope_refs
    with pytest.raises(ValueError, match="DERIVED and FUSED evidence require at least one parent_envelope_ref"):
        TruthEnvelope(
            value=20.0,
            unit="%",
            source_class=SourceClass.SIMULATOR,
            processing_level=ProcessingLevel.DERIVED,
            identity_state=IdentityState.UNKNOWN,
            authority_state=AuthorityState.RESEARCH_ONLY,
            presentation_state=PresentationState.SIMULATION,
            software_epoch_ref="test-v1",
            observed_at=now_dt,
            valid_for_seconds=60.0,
            uncertainty=0.1,
            decision_eligible=False,
            explanation="Invalid envelope",
            parent_envelope_refs=(),
        )

    # 4. Reject FUSED without parent_envelope_refs
    with pytest.raises(ValueError, match="DERIVED and FUSED evidence require at least one parent_envelope_ref"):
        TruthEnvelope(
            value=20.0,
            unit="%",
            source_class=SourceClass.REMOTE_PRODUCT,
            processing_level=ProcessingLevel.FUSED,
            identity_state=IdentityState.UNKNOWN,
            authority_state=AuthorityState.RESEARCH_ONLY,
            presentation_state=PresentationState.LIVE,
            software_epoch_ref="test-v1",
            observed_at=now_dt,
            valid_for_seconds=60.0,
            uncertainty=0.1,
            decision_eligible=False,
            explanation="Invalid envelope",
            parent_envelope_refs=(),
        )

    # 5. Reject uncertainty <= 0.0
    with pytest.raises(ValueError, match="uncertainty must be a strictly positive finite float"):
        TruthEnvelope(
            value=20.0,
            unit="%",
            source_class=SourceClass.SIMULATOR,
            processing_level=ProcessingLevel.NATIVE,
            identity_state=IdentityState.UNKNOWN,
            authority_state=AuthorityState.RESEARCH_ONLY,
            presentation_state=PresentationState.SIMULATION,
            software_epoch_ref="test-v1",
            observed_at=now_dt,
            valid_for_seconds=60.0,
            uncertainty=0.0,
            decision_eligible=False,
            explanation="Invalid zero uncertainty",
        )

    # 6. Valid derived envelope succeeds, produces canonical json and content hash
    valid_env = TruthEnvelope(
        value=20.0,
        unit="%",
        source_class=SourceClass.SIMULATOR,
        processing_level=ProcessingLevel.DERIVED,
        identity_state=IdentityState.UNKNOWN,
        authority_state=AuthorityState.RESEARCH_ONLY,
        presentation_state=PresentationState.SIMULATION,
        software_epoch_ref="test-v1",
        observed_at=now_dt,
        valid_for_seconds=60.0,
        uncertainty=0.05,
        decision_eligible=False,
        explanation="Valid derived simulation envelope",
        parent_envelope_refs=("PARENT_ENV_001",),
    )
    assert valid_env.schema_version == "1.0.0"
    assert len(valid_env.content_hash()) == 64
    canon_dict = valid_env.to_canonical_dict()
    assert canon_dict["schema_version"] == "1.0.0"
    assert canon_dict["parent_envelope_refs"] == ["PARENT_ENV_001"]


def test_closure_certificate_fail_closed_and_validation():
    """Verify ClosureCertificate fails closed to NOT_EVALUATED and enforces physical holdout preconditions."""
    cert = ClosureCertificate(
        certificate_id="CERT_TEST_001",
        target_capability="root_zone_water",
    )
    # Fails closed defaults
    assert cert.status == ClosureStatus.NOT_EVALUATED
    assert cert.closure_passed is False
    assert cert.passed_shortcut_checks is False
    assert cert.incremental_value_demonstrated is False
    assert cert.withheld_evidence_refs == ()

    # Attempting EVALUATED_PASSED without withheld physical receiver evidence refs -> ValueError
    with pytest.raises(ValueError, match="authentic withheld physical receiver evidence refs"):
        ClosureCertificate(
            certificate_id="CERT_BAD",
            target_capability="root_zone_water",
            status=ClosureStatus.EVALUATED_PASSED,
        )

    # Attempting EVALUATED_PASSED with withheld evidence but no preregistration_ref -> ValueError
    with pytest.raises(ValueError, match="preregistration_ref"):
        ClosureCertificate(
            certificate_id="CERT_BAD",
            target_capability="root_zone_water",
            status=ClosureStatus.EVALUATED_PASSED,
            withheld_evidence_refs=("PHYS_REC_001",),
        )

    # Full qualification satisfying all criteria
    now_dt = datetime.now(timezone.utc)
    passed_cert = ClosureCertificate(
        certificate_id="CERT_PASSED_001",
        target_capability="root_zone_water",
        status=ClosureStatus.EVALUATED_PASSED,
        evaluated_at=now_dt,
        withheld_evidence_refs=("PHYS_REC_001", "PHYS_REC_002"),
        preregistration_ref="PREREG_HYPOTHESIS_2026_09",
        split_manifest_hash="a" * 64,
        receiver_epoch_ref="rx-epoch-1",
        geometry_epoch_ref="geo-epoch-1",
        calibration_epoch_ref="cal-epoch-1",
        software_epoch_ref="sw-epoch-1",
        passed_shortcut_checks=True,
        shortcut_challenge_receipt_ref="REC_SHORTCUT_CHALLENGE_001",
        incremental_value_demonstrated=True,
        closure_passed=True,
    )
    assert passed_cert.status == ClosureStatus.EVALUATED_PASSED
    assert passed_cert.closure_passed is True
    assert len(passed_cert.content_hash()) == 64


def test_nmea_411_signal_id_and_date_rollover():
    """Verify NMEA 4.11 Signal ID parsing, compound keying, and date rollover across midnight."""
    # Build ZDA sentence at 23:59:58 on Sept 4, 2026
    zda_body = "GPZDA,235958.00,04,09,2026,00,00"
    # GGA sentence at 23:59:59 (fix quality 4 = FIXED)
    gga1_body = "GPGGA,235959.00,36.5000,N,003.0000,E,4,12,0.8,50.0,M,0.0,M,1.0,0001"
    # GGA sentence at 00:00:01 (date rolls over to Sept 5, 2026)
    gga2_body = "GPGGA,000001.00,36.5000,N,003.0000,E,4,12,0.8,50.0,M,0.0,M,1.0,0001"
    # GSV with NMEA 4.11 Signal ID: GPGSV with Signal ID '7' (L5)
    # 1 sat: prn=10, el=55, az=180, snr=45, signal_id_code=7
    gsv_l5_body = "GPGSV,1,1,01,10,55,180,45,7"
    # GSV with missing SNR (empty string in SNR field)
    gsv_l1_nosnr_body = "GPGSV,1,1,01,12,30,090,,1"

    def format_nmea(body):
        c = 0
        for ch in body:
            c ^= ord(ch)
        return f"${body}*{c:02X}"

    stream = (
        f"{format_nmea(zda_body)}\r\n"
        f"{format_nmea(gga1_body)}\r\n"
        f"{format_nmea(gga2_body)}\r\n"
        f"{format_nmea(gsv_l5_body)}\r\n"
        f"{format_nmea(gsv_l1_nosnr_body)}\r\n"
    )

    obs, meta = NmeaCycleAssembler.assemble_nmea_stream(stream, enforce_checksum=True)
    assert meta["corrupted_sentence_count"] == 0
    assert len(obs) == 2

    # Verify L5 signal resolution
    obs_l5 = next(o for o in obs if o.satellite_prn == 10)
    assert obs_l5.signal_id == "L5"
    assert obs_l5.carrier_frequency_hz == 1176.45e6
    assert obs_l5.snr_db_hz == 45.0
    # Verified anchored to Sept 5 (after midnight rollover)
    assert obs_l5.timestamp_utc.day == 5

    # Verify missing SNR is strictly None, NOT 0.0
    obs_nosnr = next(o for o in obs if o.satellite_prn == 12)
    assert obs_nosnr.signal_id == "L1C/A"
    assert obs_nosnr.snr_db_hz is None


def test_sliding_window_nonce_cache():
    """Verify sliding-window TTL cache rejects replayed nonces and evicts expired entries."""
    from services.agribrain.app.internal_service_auth import verify_and_store_nonce, _in_memory_nonces
    import time

    # Use unique test key_version
    kv = f"test_kv_{int(time.time() * 1000)}"
    nonce_1 = "nonce_alpha_1"
    nonce_2 = "nonce_beta_2"

    # First insert succeeds
    assert verify_and_store_nonce(kv, nonce_1, max_age_seconds=1) is True
    # Immediate replay is rejected
    assert verify_and_store_nonce(kv, nonce_1, max_age_seconds=1) is False

    # Second unique nonce succeeds
    assert verify_and_store_nonce(kv, nonce_2, max_age_seconds=1) is True

    # Sleep 1.1s for expiration
    time.sleep(1.1)

    # After expiration, inserting a new nonce triggers sliding window eviction of nonce_1 and nonce_2
    nonce_3 = "nonce_gamma_3"
    assert verify_and_store_nonce(kv, nonce_3, max_age_seconds=10) is True

    # Check that expired keys were evicted
    assert f"{kv}::{nonce_1}" not in _in_memory_nonces
    assert f"{kv}::{nonce_2}" not in _in_memory_nonces
    assert f"{kv}::{nonce_3}" in _in_memory_nonces


def test_client_spoofed_identity_camel_case_rejected():
    """Verify FastAPI routes reject client attempts to pass camelCase tenantId or farmId in body."""
    from fastapi.testclient import TestClient
    from services.agribrain.app.main import app, require_internal_service_request

    client = TestClient(app)
    fake_namespace = PlotNamespace(tenant_id="authed_t", farm_id="authed_f", plot_id="authed_p")
    app.dependency_overrides[require_internal_service_request] = lambda: fake_namespace

    try:
        # 1. Reject camelCase tenantId in post_mesia_spectrum_observatory
        bad_payload = {"tenantId": "spoof_tenant", "soil_type": "CLAY"}
        resp = client.post("/v2/mesia/authed_p", json=bad_payload)
        assert resp.status_code == 400
        assert "Authority is derived exclusively from authenticated tokens" in resp.json()["detail"]

        # 2. Reject camelCase farmId in simulate_wifi_csi
        bad_wifi = {"farmId": "spoof_farm", "ap_distance_m": 25.0}
        resp2 = client.post("/v2/mesia/simulate-wifi-csi", json=bad_wifi)
        assert resp2.status_code == 400
        assert "Authority is derived exclusively from authenticated tokens" in resp2.json()["detail"]

        # 3. Reject camelCase tenantId in ingest_nmea
        bad_nmea = {"tenantId": "spoof_tenant", "nmea_text": "$GPGGA*47"}
        resp3 = client.post("/v2/mesia/ingest-nmea", json=bad_nmea)
        assert resp3.status_code == 400
        assert "Authority is derived exclusively from authenticated tokens" in resp3.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_content_addressed_evidence_storage(tmp_path):
    """Verify MesiaProductionService.save_raw_evidence performs atomic content-addressed storage and quarantine."""
    p_ns = PlotNamespace(tenant_id="tenant_audit", farm_id="farm_audit", plot_id="plot_audit")
    raw_payload = b"$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47\r\n"
    expected_sha = hashlib.sha256(raw_payload).hexdigest()

    # Save standard evidence
    res = MesiaProductionService.save_raw_evidence(p_ns, raw_payload, extension="nmea", is_quarantined=False)
    assert res["sha256"] == expected_sha
    assert res["bytes_written"] == len(raw_payload)
    assert res["quarantined"] is False
    target_path = Path(res["path"])
    assert target_path.exists()
    assert target_path.read_bytes() == raw_payload
    assert "quarantine" not in target_path.parts

    # Save quarantined evidence
    q_res = MesiaProductionService.save_raw_evidence(p_ns, raw_payload, extension="nmea", is_quarantined=True)
    assert q_res["sha256"] == expected_sha
    assert q_res["quarantined"] is True
    q_path = Path(q_res["path"])
    assert q_path.exists()
    assert "quarantine" in q_path.parts

    # Clean up test files
    try:
        target_path.unlink(missing_ok=True)
        q_path.unlink(missing_ok=True)
    except Exception:
        pass


def test_claim_scanner_zero_violations():
    """Verify repository-wide scientific claim scanner detects 0 forbidden claim violations."""
    from services.agribrain.mesia.governance.claim_scanner import scan_repository_for_forbidden_claims

    violations = scan_repository_for_forbidden_claims()
    assert len(violations) == 0, f"Detected forbidden claim violations: {violations}"

