"""End-to-End Production Capture Pipeline Qualification Tests.

Validates Lane 1 MESIA Production Capture Remediation:
1. Real HTTP-to-storage-to-scan execution using actual mounted FastAPI endpoints.
2. Verified multi-farm tenant isolation: root / tenant / farm / plot / capture triplet.
3. Single canonical receipt referenced across upload, cold scanner, and Layer 0 bridge.
4. Accurate UTC acquisition time propagation and verification.
5. Fail-closed negative controls: foreign tenant, foreign farm, altered metadata,
   missing companion files, spoofed client payload, unobserved plot baseline.
6. Zero LIVE or persistence-authority claims without verified capture proof.
7. Zero unauthorized biological state mutations.
"""

import base64
import copy
import json
import math
import uuid
import numpy as np
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from services.agribrain.app.main import app, require_internal_service_request
from services.agribrain.app.internal_service_auth import compute_request_signature
from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.mesia.contracts.capture_manifest import SigMFCaptureManifest, QuarantinedCaptureException
from services.agribrain.mesia.ingestion import sigmf_ingest
from services.agribrain.mesia.ingestion.sigmf_ingest import (
    DEFAULT_STORAGE_ROOT,
    verify_capture_integrity,
    ingest_sigmf_capture,
)
import services.agribrain.mesia.integration as mesia_integration
from services.agribrain.mesia.lanes.wifi.csi_extractor import NativeWifiCsiExtractor
from services.agribrain.mesia.ontology.evidence_taxonomy import SourceClass, PresentationState
from services.agribrain.mesia.service import MesiaProductionService


@pytest.fixture
def test_storage(tmp_path, monkeypatch):
    """Provide an isolated storage root for capture artifacts across modules."""
    storage = tmp_path / "mesia_captures"
    storage.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sigmf_ingest, "DEFAULT_STORAGE_ROOT", storage)
    return storage


def _generate_synthetic_wifi_sigmf(dt: datetime, n_subcarriers: int = 64):
    """Generate authentic cf32_le SigMF CSI bytes and metadata."""
    amps = [0.08 + 0.02 * math.cos(i * 0.1) for i in range(n_subcarriers)]
    phases = [math.sin(i * 0.15) for i in range(n_subcarriers)]
    data_bytes = NativeWifiCsiExtractor.pack_sigmf_cf32_le(amps, phases)
    meta = {
        "global": {
            "core:datatype": "cf32_le",
            "core:sample_rate": 20.0e6,
            "core:hw": "esp32_s3_csi_iot_anchor",
            "core:version": "1.0.0",
        },
        "captures": [{
            "core:sample_start": 0,
            "core:datetime": dt.isoformat(),
            "core:frequency": 2.437e9,
        }],
        "annotations": [{
            "core:sample_start": 0,
            "core:sample_count": n_subcarriers,
        }],
    }
    return data_bytes, meta


def _make_geojson_polygon(coords):
    """Converts [(lat, lon), ...] to valid GeoJSON polygon dict."""
    ring = [[lon, lat] for lat, lon in coords]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return {
        "type": "Polygon",
        "coordinates": [ring],
    }


def test_authenticated_http_upload_to_storage_to_scan_pipeline(test_storage):
    """Exit Gate 1: Full pipeline from mounted HTTP upload -> disk triplet -> scan -> Layer 0."""
    client = TestClient(app)
    tenant_id = "tenant_algeria_01"
    farm_id = "farm_biskra_palm"
    plot_id = "parcel_date_palm_42"

    auth_ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)
    app.dependency_overrides[require_internal_service_request] = lambda: auth_ns

    capture_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    raw_bytes, meta_dict = _generate_synthetic_wifi_sigmf(capture_time)
    data_b64 = base64.b64encode(raw_bytes).decode("ascii")

    try:
        # Step 1: Upload via mounted FastAPI endpoint
        upload_resp = client.post(
            "/v2/mesia/ingest-sigmf-csi",
            json={"data_b64": data_b64, "meta_json": meta_dict},
        )
        assert upload_resp.status_code == 200, f"Upload failed: {upload_resp.text}"
        upload_data = upload_resp.json()

        assert upload_data["status"] == "MEASURED_IN_SITU_RADIO_WAVES"
        assert upload_data["physical_waves_measured"] is True
        assert upload_data["presentation_state"] == "REPLAY"
        assert upload_data["identity_state"] == "PROTOCOL_CONFIRMED"

        receipt_id = upload_data.get("receipt_id")
        capture_id = upload_data.get("capture_id")
        canonical_rcpt = upload_data.get("canonical_receipt")
        assert receipt_id and receipt_id.startswith("rcpt-sigmf-")
        assert capture_id and len(capture_id) == 64
        assert canonical_rcpt is not None
        assert canonical_rcpt["receipt_id"] == receipt_id
        assert canonical_rcpt["tenant_id"] == tenant_id
        assert canonical_rcpt["farm_id"] == farm_id
        assert canonical_rcpt["plot_id"] == plot_id

        # Step 2: Verify on-disk triplet under farm-isolated directory hierarchy
        dest_dir = test_storage / tenant_id / farm_id / plot_id
        assert dest_dir.is_dir()
        data_file = dest_dir / f"{capture_id}.sigmf-data"
        meta_file = dest_dir / f"{capture_id}.sigmf-meta"
        manifest_file = dest_dir / f"{capture_id}.manifest.json"

        assert data_file.is_file()
        assert meta_file.is_file()
        assert manifest_file.is_file()

        manifest = SigMFCaptureManifest.from_dict(json.loads(manifest_file.read_text(encoding="utf-8")))
        assert manifest.farm_id == farm_id
        assert manifest.tenant_id == tenant_id
        assert manifest.plot_id == plot_id
        assert verify_capture_integrity(manifest_file, expected_namespace=auth_ns, storage_root=test_storage)

        # Step 3: Run cold spectrum scan via mounted endpoint
        coords = [
            (34.8510, 5.7280),
            (34.8510, 5.7310),
            (34.8530, 5.7310),
            (34.8530, 5.7280),
        ]
        scan_resp = client.post(
            f"/v2/mesia/{plot_id}",
            json={"geo_json": _make_geojson_polygon(coords), "soil_type": "SAND"},
        )
        assert scan_resp.status_code == 200, f"Scan failed: {scan_resp.text}"
        scan_data = scan_resp.json()

        # Step 4: Verify single canonical receipt and Layer 0 admission in evidence proposals
        proposals = scan_data.get("evidence_proposals", [])
        wifi_prop = next((p for p in proposals if p["feature"] == "mesia_wifi_csi_canopy_foliar"), None)
        assert wifi_prop is not None, "mesia_wifi_csi_canopy_foliar proposal missing from scan"

        assert wifi_prop["receipt_id"] == receipt_id
        assert wifi_prop["capture_id"] == capture_id
        assert wifi_prop["canonical_receipt"] == canonical_rcpt
        assert wifi_prop["native_capture_present"] is True
        assert wifi_prop["physical_waves_measured"] is True
        assert wifi_prop["presentation_state"] == "REPLAY"

        # Verify exact URI referencing verified on-disk capture
        assert wifi_prop["native_artifact_ref"] == data_file.as_uri()

        # Verify Layer 0 admission: uncalibrated demonstrator fails closed
        assert wifi_prop["is_usable_for_assimilation"] is False
        assert wifi_prop["admission_status"] in ("ABSENT", "INVALIDATED", "CALIBRATION_INVALID")

        # Verify TruthEnvelope binds canonical receipt and native artifact
        env = wifi_prop["truth_envelope"]
        assert env["source_class"] == SourceClass.PHYSICAL_RECEIVER.value
        assert env["presentation_state"] == PresentationState.REPLAY.value
        assert env["calibration_state_ref"] == "CALIB-UNVERIFIED-DEMONSTRATOR"
        assert env["source_receipt_ref"] == receipt_id
        assert env["native_artifact_ref"] == data_file.as_uri()

        # Verify Signals of Opportunity ambient_wifi_csi projection
        soo_wifi = scan_data["signals_of_opportunity"]["ambient_wifi_csi"]
        assert soo_wifi["status"] == "RECORDED_CAPTURE_AVAILABLE"
        assert soo_wifi["presentation_state"] == "REPLAY"
        assert soo_wifi["canonical_receipt_id"] == receipt_id
        assert soo_wifi["recorded_capture_available"] is True
        assert soo_wifi["is_fresh"] is True

    finally:
        app.dependency_overrides.clear()


def test_cross_tenant_isolation_in_pipeline(test_storage):
    """Negative Control: Captures uploaded by Tenant A cannot be seen or claimed by Tenant B."""
    client = TestClient(app)
    shared_plot = "shared_field_99"
    tenant_a = "tenant_alpha"
    tenant_b = "tenant_beta"
    farm_id = "farm_shared"

    ns_a = PlotNamespace(tenant_id=tenant_a, farm_id=farm_id, plot_id=shared_plot)
    ns_b = PlotNamespace(tenant_id=tenant_b, farm_id=farm_id, plot_id=shared_plot)

    coords = [(34.85, 5.72), (34.85, 5.73), (34.86, 5.73), (34.86, 5.72)]

    # Ingest capture under Tenant A
    app.dependency_overrides[require_internal_service_request] = lambda: ns_a
    try:
        raw_bytes, meta_dict = _generate_synthetic_wifi_sigmf(datetime.now(timezone.utc))
        b64 = base64.b64encode(raw_bytes).decode("ascii")
        up = client.post("/v2/mesia/ingest-sigmf-csi", json={"data_b64": b64, "meta_json": meta_dict})
        assert up.status_code == 200
        assert up.json()["physical_waves_measured"] is True
    finally:
        app.dependency_overrides.clear()

    # Now scan as Tenant B
    app.dependency_overrides[require_internal_service_request] = lambda: ns_b
    try:
        scan_resp = client.post(
            f"/v2/mesia/{shared_plot}",
            json={"geo_json": _make_geojson_polygon(coords), "soil_type": "SAND"},
        )
        assert scan_resp.status_code == 200
        scan_data = scan_resp.json()

        # Tenant B must NOT see Tenant A's Wi-Fi capture as verified or LIVE
        proposals = scan_data.get("evidence_proposals", [])
        wifi_prop = next((p for p in proposals if p["feature"] == "mesia_wifi_csi_canopy_foliar"), None)
        assert wifi_prop is None or wifi_prop.get("physical_waves_measured") is False
    finally:
        app.dependency_overrides.clear()


def test_cross_farm_isolation_in_pipeline(test_storage):
    """Negative Control: Captures uploaded for Farm 1 cannot be seen on Farm 2 within same tenant."""
    client = TestClient(app)
    tenant_id = "tenant_agri_corp"
    shared_plot = "parcel_greenhouse"
    farm_1 = "farm_north_oasis"
    farm_2 = "farm_south_valley"

    ns_farm1 = PlotNamespace(tenant_id=tenant_id, farm_id=farm_1, plot_id=shared_plot)
    ns_farm2 = PlotNamespace(tenant_id=tenant_id, farm_id=farm_2, plot_id=shared_plot)

    coords = [(34.85, 5.72), (34.85, 5.73), (34.86, 5.73), (34.86, 5.72)]

    # Ingest capture under Farm 1
    app.dependency_overrides[require_internal_service_request] = lambda: ns_farm1
    try:
        raw_bytes, meta_dict = _generate_synthetic_wifi_sigmf(datetime.now(timezone.utc))
        b64 = base64.b64encode(raw_bytes).decode("ascii")
        up = client.post("/v2/mesia/ingest-sigmf-csi", json={"data_b64": b64, "meta_json": meta_dict})
        assert up.status_code == 200
        assert up.json()["physical_waves_measured"] is True
    finally:
        app.dependency_overrides.clear()

    # Scan as Farm 2
    app.dependency_overrides[require_internal_service_request] = lambda: ns_farm2
    try:
        scan_resp = client.post(
            f"/v2/mesia/{shared_plot}",
            json={"geo_json": _make_geojson_polygon(coords), "soil_type": "SAND"},
        )
        assert scan_resp.status_code == 200
        scan_data = scan_resp.json()

        proposals = scan_data.get("evidence_proposals", [])
        wifi_prop = next((p for p in proposals if p["feature"] == "mesia_wifi_csi_canopy_foliar"), None)
        assert wifi_prop is None or wifi_prop.get("physical_waves_measured") is False
    finally:
        app.dependency_overrides.clear()


def test_altered_metadata_fails_closed_in_scanner(test_storage):
    """Negative Control: Tampering with metadata file on disk invalidates capture in scanner."""
    client = TestClient(app)
    auth_ns = PlotNamespace(tenant_id="tenant_tamper", farm_id="farm_tamper", plot_id="parcel_tamper")
    app.dependency_overrides[require_internal_service_request] = lambda: auth_ns

    coords = [(34.85, 5.72), (34.85, 5.73), (34.86, 5.73), (34.86, 5.72)]

    try:
        raw_bytes, meta_dict = _generate_synthetic_wifi_sigmf(datetime.now(timezone.utc))
        b64 = base64.b64encode(raw_bytes).decode("ascii")
        up = client.post("/v2/mesia/ingest-sigmf-csi", json={"data_b64": b64, "meta_json": meta_dict})
        assert up.status_code == 200
        capture_id = up.json()["capture_id"]

        # Tamper with the metadata on disk (change sample rate)
        meta_file = test_storage / "tenant_tamper" / "farm_tamper" / "parcel_tamper" / f"{capture_id}.sigmf-meta"
        meta_content = json.loads(meta_file.read_text(encoding="utf-8"))
        meta_content["global"]["core:sample_rate"] = 99999999.0
        meta_file.write_text(json.dumps(meta_content), encoding="utf-8")

        # Now scan: scanner should reject the tampered capture fail-closed
        scan_resp = client.post(
            "/v2/mesia/parcel_tamper",
            json={"geo_json": _make_geojson_polygon(coords), "soil_type": "SAND"},
        )
        assert scan_resp.status_code == 200
        scan_data = scan_resp.json()

        proposals = scan_data.get("evidence_proposals", [])
        wifi_prop = next((p for p in proposals if p["feature"] == "mesia_wifi_csi_canopy_foliar"), None)
        assert wifi_prop is None or wifi_prop.get("physical_waves_measured") is False
    finally:
        app.dependency_overrides.clear()


def test_missing_companion_manifest_fails_closed(test_storage):
    """Negative Control: Deleting .manifest.json causes capture rejection."""
    client = TestClient(app)
    auth_ns = PlotNamespace(tenant_id="tenant_comp", farm_id="farm_comp", plot_id="parcel_comp")
    app.dependency_overrides[require_internal_service_request] = lambda: auth_ns

    coords = [(34.85, 5.72), (34.85, 5.73), (34.86, 5.72), (34.86, 5.73)]

    try:
        raw_bytes, meta_dict = _generate_synthetic_wifi_sigmf(datetime.now(timezone.utc))
        b64 = base64.b64encode(raw_bytes).decode("ascii")
        up = client.post("/v2/mesia/ingest-sigmf-csi", json={"data_b64": b64, "meta_json": meta_dict})
        assert up.status_code == 200
        capture_id = up.json()["capture_id"]

        # Delete the manifest
        manifest_file = test_storage / "tenant_comp" / "farm_comp" / "parcel_comp" / f"{capture_id}.manifest.json"
        manifest_file.unlink()

        # Scan should fail closed
        scan_resp = client.post(
            "/v2/mesia/parcel_comp",
            json={"geo_json": _make_geojson_polygon(coords), "soil_type": "SAND"},
        )
        assert scan_resp.status_code == 200
        scan_data = scan_resp.json()

        proposals = scan_data.get("evidence_proposals", [])
        wifi_prop = next((p for p in proposals if p["feature"] == "mesia_wifi_csi_canopy_foliar"), None)
        assert wifi_prop is None or wifi_prop.get("physical_waves_measured") is False
    finally:
        app.dependency_overrides.clear()


def test_client_payload_spoofed_tenant_or_farm_rejected():
    """Negative Control: Client cannot inject tenant_id, tenantId, farm_id, or farmId in payload."""
    client = TestClient(app)
    auth_ns = PlotNamespace(tenant_id="authed_tenant", farm_id="authed_farm", plot_id="parcel_spoof")
    app.dependency_overrides[require_internal_service_request] = lambda: auth_ns

    try:
        # Spoofed tenant_id
        resp1 = client.post(
            "/v2/mesia/ingest-sigmf-csi",
            json={"tenant_id": "attacker_tenant", "data_b64": "AAAA"},
        )
        assert resp1.status_code == 400
        assert "Authority is derived exclusively from authenticated tokens" in resp1.json()["detail"]

        # Spoofed farmId
        resp2 = client.post(
            "/v2/mesia/ingest-sigmf-csi",
            json={"farmId": "attacker_farm", "data_b64": "AAAA"},
        )
        assert resp2.status_code == 400
        assert "Authority is derived exclusively from authenticated tokens" in resp2.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_unobserved_plot_baseline():
    """Negative Control: Unobserved parcel baseline has physical_waves_measured=False, zero LIVE claims."""
    client = TestClient(app)
    auth_ns = PlotNamespace(tenant_id="tenant_virgin", farm_id="farm_virgin", plot_id="parcel_virgin_001")
    app.dependency_overrides[require_internal_service_request] = lambda: auth_ns

    coords = [(34.85, 5.72), (34.85, 5.73), (34.86, 5.73), (34.86, 5.72)]

    try:
        scan_resp = client.post(
            "/v2/mesia/parcel_virgin_001",
            json={"geo_json": _make_geojson_polygon(coords), "soil_type": "SAND"},
        )
        assert scan_resp.status_code == 200
        scan_data = scan_resp.json()

        proposals = scan_data.get("evidence_proposals", [])
        # No Wi-Fi proposal should exist when zero captures are present
        wifi_prop = next((p for p in proposals if p["feature"] == "mesia_wifi_csi_canopy_foliar"), None)
        assert wifi_prop is None

        # GNSS in-situ without physical log is SIMULATION or research proposal
        for p in proposals:
            assert p.get("decision_eligible") is False
            if p.get("physical_waves_measured") is not True:
                assert p.get("presentation_state") != "LIVE"
    finally:
        app.dependency_overrides.clear()


def test_genuine_signed_internal_service_authentication_pipeline(test_storage):
    """Exit Gate 8: Genuine signed HMAC authentication without dependency overrides."""
    client = TestClient(app)
    app.dependency_overrides.clear()  # Ensure strictly zero overrides

    tenant_id = "tenant_genuine_hmac"
    farm_id = "farm_genuine_hmac"
    plot_id = "parcel_genuine_hmac_99"

    capture_time = datetime(2026, 11, 22, 16, 0, 0, tzinfo=timezone.utc)
    raw_bytes, meta_dict = _generate_synthetic_wifi_sigmf(capture_time)
    data_b64 = base64.b64encode(raw_bytes).decode("ascii")

    payload_dict = {"data_b64": data_b64, "meta_json": meta_dict}
    body_bytes = json.dumps(payload_dict).encode("utf-8")

    import time
    timestamp = str(time.time())
    nonce = uuid.uuid4().hex
    path = "/v2/mesia/ingest-sigmf-csi"

    # Compute genuine RFC 3986 canonical HMAC-SHA256 signature
    sig = compute_request_signature(
        method="POST",
        path=path,
        query_string="",
        tenant_id=tenant_id,
        farm_id=farm_id,
        plot_id=plot_id,
        body_bytes=body_bytes,
        timestamp=timestamp,
        nonce=nonce,
        key_version="v1",
    )

    headers = {
        "X-AgriBrain-Signature": sig,
        "X-AgriBrain-Timestamp": timestamp,
        "X-AgriBrain-Nonce": nonce,
        "X-AgriBrain-Key-Version": "v1",
        "X-Tenant-Id": tenant_id,
        "X-Farm-Id": farm_id,
        "X-Plot-Id": plot_id,
        "Content-Type": "application/json",
    }

    # 1. Genuine signed request succeeds through real require_internal_service_request
    resp = client.post(path, content=body_bytes, headers=headers)
    assert resp.status_code == 200, f"Signed upload failed: {resp.text}"
    resp_data = resp.json()
    assert resp_data["status"] == "MEASURED_IN_SITU_RADIO_WAVES"
    assert resp_data["physical_waves_measured"] is True
    capture_id = resp_data["capture_id"]

    # Verify storage partition matches authenticated namespace exactly
    dest_dir = test_storage / tenant_id / farm_id / plot_id
    assert dest_dir.is_dir()
    assert (dest_dir / f"{capture_id}.sigmf-meta").is_file()
    assert (dest_dir / f"{capture_id}.sigmf-data").is_file()
    assert (dest_dir / f"{capture_id}.manifest.json").is_file()

    # 2. Tampered body fails closed (401 Unauthorized)
    tampered_body = json.dumps({"data_b64": data_b64, "meta_json": {**meta_dict, "tampered": True}}).encode("utf-8")
    resp_tampered = client.post(path, content=tampered_body, headers=headers)
    assert resp_tampered.status_code == 401

    # 3. Tampered signature fails closed (401 Unauthorized)
    headers_bad_sig = {**headers, "X-AgriBrain-Signature": "deadbeef" * 8, "X-AgriBrain-Nonce": uuid.uuid4().hex}
    resp_bad_sig = client.post(path, content=body_bytes, headers=headers_bad_sig)
    assert resp_bad_sig.status_code == 401

    # 4. Missing headers fails closed (401 Unauthorized)
    resp_no_headers = client.post(path, content=body_bytes)
    assert resp_no_headers.status_code == 401

    # 5. Replay attack with same nonce fails closed (401 Unauthorized)
    resp_replay = client.post(path, content=body_bytes, headers=headers)
    assert resp_replay.status_code == 401


def test_canonical_receipt_and_provenance_propagates_across_all_projections(test_storage):
    """P1-B: Canonical capture receipt, native URI, and provenance propagate consistently across all 3 projections."""
    client = TestClient(app)
    tenant_id = "tenant_prop_test"
    farm_id = "farm_prop_test"
    plot_id = "parcel_prop_test_01"
    ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)
    app.dependency_overrides[require_internal_service_request] = lambda: ns

    coords = [(34.85, 5.72), (34.85, 5.73), (34.86, 5.73), (34.86, 5.72)]
    acq_time = datetime.now(timezone.utc) - timedelta(minutes=15)

    try:
        raw_bytes, meta_dict = _generate_synthetic_wifi_sigmf(acq_time)
        b64 = base64.b64encode(raw_bytes).decode("ascii")
        up = client.post("/v2/mesia/ingest-sigmf-csi", json={"data_b64": b64, "meta_json": meta_dict})
        assert up.status_code == 200
        up_data = up.json()
        capture_id = up_data["capture_id"]
        canonical_receipt_id = up_data["receipt_id"]
        assert canonical_receipt_id == f"rcpt-sigmf-{capture_id[:16]}"
        assert not canonical_receipt_id.startswith("rcpt-sigmf-csi-")

        # Scan the plot
        scan_resp = client.post(
            f"/v2/mesia/{plot_id}",
            json={"geo_json": _make_geojson_polygon(coords), "soil_type": "SAND"},
        )
        assert scan_resp.status_code == 200
        scan_data = scan_resp.json()

        # 1. Wi-Fi evidence proposal projection
        proposals = scan_data.get("evidence_proposals", [])
        wifi_prop = next((p for p in proposals if p["feature"] == "mesia_wifi_csi_canopy_foliar"), None)
        assert wifi_prop is not None
        assert wifi_prop["receipt_id"] == canonical_receipt_id
        assert not wifi_prop["receipt_id"].startswith("rcpt-sigmf-csi-")
        assert wifi_prop["native_data_uri"].startswith("file:///")
        assert not wifi_prop["native_data_uri"].startswith("file://mesia/evidence/")
        assert wifi_prop["presentation_state"] == "REPLAY"

        # 2. ambient_wifi_csi TruthEnvelope projection
        truth_envelopes = scan_data.get("truth_envelopes", {})
        assert "ambient_wifi_csi" in truth_envelopes
        wifi_envelope = truth_envelopes["ambient_wifi_csi"]
        assert wifi_envelope["source_receipt_ref"] == canonical_receipt_id
        assert not wifi_envelope["source_receipt_ref"].startswith("rcpt-sigmf-csi-")
        assert wifi_envelope["native_artifact_ref"].startswith("file:///")
        assert not wifi_envelope["native_artifact_ref"].startswith("file://mesia/evidence/")
        assert wifi_envelope["calibration_state_ref"] == "CALIB-UNVERIFIED-DEMONSTRATOR"
        assert wifi_envelope["presentation_state"] == "REPLAY"

        # 3. Signals of opportunity projection
        soo = scan_data.get("signals_of_opportunity", {})
        assert "ambient_wifi_csi" in soo
        soo_wifi = soo["ambient_wifi_csi"]
        assert soo_wifi["canonical_receipt_id"] == canonical_receipt_id
        assert not soo_wifi["canonical_receipt_id"].startswith("rcpt-sigmf-csi-")
        assert soo_wifi["native_data_uri"].startswith("file:///")
        assert not soo_wifi["native_data_uri"].startswith("file://mesia/evidence/")
        assert soo_wifi["recorded_capture_available"] is True
        assert soo_wifi["presentation_state"] == "REPLAY"
        assert soo_wifi["status"] == "RECORDED_CAPTURE_AVAILABLE"
        assert soo_wifi["is_fresh"] is True
        assert soo_wifi["freshness"] == "FRESH"
    finally:
        app.dependency_overrides.clear()


def test_archived_capture_cannot_claim_live_and_stale_capture_marked_stale(test_storage):
    """P1-B: Stored capture cannot claim LIVE, and capture >3600s is marked ARCHIVED_CAPTURE_STALE."""
    client = TestClient(app)
    tenant_id = "tenant_stale_test"
    farm_id = "farm_stale_test"
    plot_id = "parcel_stale_test_01"
    ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)
    app.dependency_overrides[require_internal_service_request] = lambda: ns

    coords = [(34.85, 5.72), (34.85, 5.73), (34.86, 5.73), (34.86, 5.72)]
    # Ingest capture from 3 hours ago (> 3600s)
    stale_time = datetime.now(timezone.utc) - timedelta(hours=3)

    try:
        raw_bytes, meta_dict = _generate_synthetic_wifi_sigmf(stale_time)
        b64 = base64.b64encode(raw_bytes).decode("ascii")
        up = client.post("/v2/mesia/ingest-sigmf-csi", json={"data_b64": b64, "meta_json": meta_dict})
        assert up.status_code == 200

        # Scan the plot
        scan_resp = client.post(
            f"/v2/mesia/{plot_id}",
            json={"geo_json": _make_geojson_polygon(coords), "soil_type": "SAND"},
        )
        assert scan_resp.status_code == 200
        scan_data = scan_resp.json()

        # Proposal must NOT claim LIVE
        proposals = scan_data.get("evidence_proposals", [])
        wifi_prop = next((p for p in proposals if p["feature"] == "mesia_wifi_csi_canopy_foliar"), None)
        assert wifi_prop is not None
        assert wifi_prop["presentation_state"] == "REPLAY"
        assert wifi_prop["presentation_state"] != "LIVE"

        # TruthEnvelope must NOT claim LIVE
        truth_envelopes = scan_data.get("truth_envelopes", {})
        wifi_envelope = truth_envelopes["ambient_wifi_csi"]
        assert wifi_envelope["presentation_state"] == "REPLAY"
        assert wifi_envelope["presentation_state"] != "LIVE"

        # Signals of Opportunity must be marked ARCHIVED_CAPTURE_STALE and STALE
        soo = scan_data.get("signals_of_opportunity", {})
        soo_wifi = soo["ambient_wifi_csi"]
        assert soo_wifi["status"] == "ARCHIVED_CAPTURE_STALE"
        assert soo_wifi["freshness"] == "STALE"
        assert soo_wifi["is_fresh"] is False
        assert soo_wifi["recorded_capture_available"] is True
        assert soo_wifi["presentation_state"] == "REPLAY"
    finally:
        app.dependency_overrides.clear()


def test_csi_decoding_contract_rejects_unsupported_datatype_and_length(tmp_path):
    """P1-B: CSI decoding contract strictly enforces cf32_le, length divisible by 8, and sample count agreement."""
    # 1. Test ingest_sigmf_capture datatype rejection
    valid_payload = b"01234567" * 8  # 64 bytes = 8 samples
    valid_meta = {
        "global": {"core:datatype": "cf64_le", "core:sample_rate": 20.0e6, "core:hw": "iwlwifi"},
        "captures": [{"core:datetime": "2026-11-23T12:00:00+00:00", "core:frequency": 2.437e9}],
        "annotations": [{"core:sample_count": 8, "core:sample_start": 0}],
    }
    with pytest.raises(QuarantinedCaptureException, match="Unsupported SigMF core:datatype"):
        ingest_sigmf_capture("t1", "p1", valid_payload, copy.deepcopy(valid_meta), storage_root=tmp_path)

    # Missing mandatory core:datatype in metadata global segment
    missing_dt_meta = copy.deepcopy(valid_meta)
    missing_dt_meta["global"].pop("core:datatype", None)
    with pytest.raises(QuarantinedCaptureException, match="Missing mandatory SigMF core:datatype"):
        ingest_sigmf_capture("t1", "p1", valid_payload, missing_dt_meta, storage_root=tmp_path)

    # 2. Test ingest_sigmf_capture length not divisible by 8
    bad_length_payload = b"012345678"  # 9 bytes
    valid_meta_cf32 = copy.deepcopy(valid_meta)
    valid_meta_cf32["global"]["core:datatype"] = "cf32_le"
    with pytest.raises(QuarantinedCaptureException, match="not divisible by 8"):
        ingest_sigmf_capture("t1", "p1", bad_length_payload, valid_meta_cf32, storage_root=tmp_path)

    # 3. Test ingest_sigmf_capture sample count mismatch
    mismatch_meta = copy.deepcopy(valid_meta_cf32)
    mismatch_meta["annotations"][0]["core:sample_count"] = 100  # 100 != 8 samples
    with pytest.raises(QuarantinedCaptureException, match="Declared core:sample_count 100 does not reconcile"):
        ingest_sigmf_capture("t1", "p1", valid_payload, mismatch_meta, storage_root=tmp_path)

    # 4. Test NativeWifiCsiExtractor.read_sigmf / extract_csi_subcarriers rejection
    data_file = tmp_path / "test_csi.sigmf-data"
    meta_file = tmp_path / "test_csi.sigmf-meta"

    # Unsupported datatype
    bad_datatype_meta = copy.deepcopy(valid_meta)
    bad_datatype_meta["global"]["core:datatype"] = "ri16_le"
    data_file.write_bytes(valid_payload)
    meta_file.write_text(json.dumps(bad_datatype_meta), encoding="utf-8")
    with pytest.raises(QuarantinedCaptureException, match="Unsupported SigMF core:datatype"):
        NativeWifiCsiExtractor.read_sigmf(str(data_file))

    # Missing datatype in read_sigmf
    meta_file.write_text(json.dumps(missing_dt_meta), encoding="utf-8")
    with pytest.raises(QuarantinedCaptureException, match="Missing mandatory SigMF core:datatype"):
        NativeWifiCsiExtractor.read_sigmf(str(data_file))

    # Indivisible length
    meta_file.write_text(json.dumps(valid_meta_cf32), encoding="utf-8")
    data_file.write_bytes(bad_length_payload)
    with pytest.raises(QuarantinedCaptureException, match="divisible by 8"):
        NativeWifiCsiExtractor.extract_csi_subcarriers(str(data_file))

    # Sample count mismatch
    data_file.write_bytes(valid_payload)
    meta_file.write_text(json.dumps(mismatch_meta), encoding="utf-8")
    with pytest.raises(QuarantinedCaptureException, match="contradicts interpreted sample count"):
        NativeWifiCsiExtractor.read_sigmf(str(data_file))

    # 5. Test verify_capture_integrity returns False for invalid capture
    assert verify_capture_integrity(data_file, meta_file) is False


def test_wifi_capture_missing_datetime_fails_closed_as_unknown_freshness(monkeypatch):
    """P2 Follow-up: An alternate/incomplete Wi-Fi result with missing acquisition timestamp fails closed as freshness UNKNOWN."""
    mock_wifi = {
        "physical_waves_measured": True,
        "canopy_water_index": 0.42,
        "native_data_uri": "file://mesia/test.sigmf-data",
        "receipt_id": "rcpt-test-123",
        "acquisition_time": None,  # Missing acquisition timestamp!
        "is_active_stream": False,
        "presentation_state": "REPLAY",
        "num_subcarriers": 64,
        "target_classification": "BACKGROUND",
        "sha256": "a" * 64,
    }
    monkeypatch.setattr(MesiaProductionService, "_process_real_in_situ_wifi_csi", lambda *args, **kwargs: mock_wifi)
    monkeypatch.setattr(
        MesiaProductionService,
        "_fetch_real_copernicus_soil",
        lambda lat, lon: {
            "soil_moisture_0_to_1cm": 0.20,
            "soil_moisture_1_to_3cm": 0.22,
            "soil_moisture_3_to_9cm": 0.25,
            "soil_moisture_9_to_27cm": 0.28,
            "relative_humidity_2m": 65.0,
            "surface_pressure": 1013.25,
            "temperature_2m": 22.0,
            "wind_speed_10m": 3.5,
        },
    )
    monkeypatch.setattr(
        MesiaProductionService,
        "_fetch_real_osm_masts",
        lambda lat, lon, radius_m=8000.0: [],
    )

    coords = [(34.85, 5.72), (34.85, 5.73), (34.86, 5.73), (34.86, 5.72)]
    res = MesiaProductionService.scan_plot_spectrum("plot-nodt", polygon_wgs84=coords, soil_type="SAND")
    soo_wifi = res["signals_of_opportunity"]["ambient_wifi_csi"]

    assert soo_wifi["recorded_capture_available"] is True
    assert soo_wifi["presentation_state"] == "REPLAY"
    # Must fail closed as UNKNOWN freshness, NOT fresh!
    assert soo_wifi["freshness"] == "UNKNOWN"
    assert soo_wifi["is_fresh"] is False



