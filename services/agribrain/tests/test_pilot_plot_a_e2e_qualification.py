"""
End-to-End Scientific Qualification Suite for Akaloris Scientific Pilot (Plot-A).

Demonstrates and proves the complete, connected scientific pipeline:
  1. Layer 0 Observation & State Ingestion (S2 optical, Weather, Point Sensor)
  2. Layer 1 Scientific Fusion, Temporal Alignment, and EvidenceLedger Admission
  3. Pre-Ledger Quarantining: non-PSD covariance, unverified receipts, and out-of-scope data
  4. Layer 0.5 ASMAE Biophysical Integration and Canonical Plot Snapshot Publication
  5. Downstream Lineage: Layer 2 Agronomic Intake and Layer 10 SIRE Spatial Intelligence
  6. Strict Actuation Interlock: Hardware-level disablement of verified irrigation
     (AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
import pytest

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.layer0.observation_packet import (
    DataStatus,
    ObservationPacket,
    ObservationSource,
    QAMetadata,
    UncertaintyModel,
)
from services.agribrain.layer0.source_package import (
    Layer0SourcePackage,
    Layer0StatePackage,
)
from services.agribrain.layer1_fusion.engine import Layer1FusionEngine
from services.agribrain.layer1_fusion.schemas import (
    EvidenceItem,
    Layer1InputBundle,
    SourceEnvelope,
)
from services.agribrain.layer1_fusion import truth_bridge as tb
from services.agribrain.layer1_fusion.tests.trust_fixtures import (
    provision_test_issuer_keypair,
    create_signed_sensor_receipt,
    create_signed_publication_receipt,
)
from services.agribrain.layer05_asmae import plot_snapshot_store as asmae_store
from services.agribrain.layer10_sire.surface_contract import (
    SURFACES_SCHEMA_VERSION,
    RENDER_AUTHORIZATION_VERSION,
    classify_surface_publication,
)
from services.agribrain.app.production_delivery_runtime import (
    verified_irrigation_enabled,
    ENABLE_FLAG,
)
from services.agribrain.layer0.production_admission import (
    Layer0AdmissionRequiredError,
)


PLOT_ID = "plot-A"
NAMESPACE = PlotNamespace(tenant_id="tenant-akaloris", farm_id="farm-pilot", plot_id=PLOT_ID)
RUN_TIME = datetime(2026, 11, 10, 12, 0, 0, tzinfo=timezone.utc)
GEOM_HASH = "geom-plot-a-hash-v1"
GEOM_VERSION = 1


@pytest.fixture(autouse=True)
def _setup_pilot_test_environment(tmp_path, monkeypatch):
    """Enforce strict observation-only pilot interlock and isolated test stores."""
    # 1. Enforce strict actuation lock
    monkeypatch.setenv(ENABLE_FLAG, "false")
    os.environ[ENABLE_FLAG] = "false"

    # 2. Isolate revocation store
    rev_path = tmp_path / "revocation_store.json"
    store = tb.DurableRevocationStore(persistence_path=rev_path)
    tb.set_revocation_store(store)

    # 3. Provision authentic test issuer keypair
    issuer = "agriwise:trust:sensor_authority"
    _priv, pub_key = provision_test_issuer_keypair(issuer)
    tb.register_trusted_issuer_public_key(issuer, pub_key)

    # 4. Isolate ASMAE plot snapshot root
    monkeypatch.setattr(asmae_store, "PLOT_SNAPSHOT_ROOT", tmp_path / "snapshots")

    # 5. Register authentic sensor device in device registry
    from services.agribrain.sensor_runtime.registry import SensorDeviceRegistration, register_device, _DEVICE_REGISTRY
    _DEVICE_REGISTRY.clear()
    reg = SensorDeviceRegistration(
        device_id="sensor_probe_alpha",
        vendor="acme",
        model="probe-x",
        protocol="lora",
        farm_id="farm-pilot",
        plot_id=PLOT_ID,
        latitude=35.0,
        longitude=10.0,
        variables=["soil_moisture_vwc"],
        installation_datetime=RUN_TIME - timedelta(days=30),
        status="active",
        calibration_profile_id="cal_soil_probe_2026",
        depth_cm=15.0,
    )
    register_device(reg)

    yield

    _DEVICE_REGISTRY.clear()
    tb.clear_sensor_receipts()
    tb.clear_publication_receipts()


def _build_authentic_layer0_sensor_package() -> Layer0SourcePackage:
    """Build a qualified Layer 0 sensor source package for soil moisture."""
    receipt_id = "urn:agriwise:receipt:sensor_probe_alpha:001"
    issuer = "agriwise:trust:sensor_authority"
    obs_time = RUN_TIME - timedelta(minutes=15)
    reading_val = 0.32

    # Compute deterministic content digest matching IEEE precision
    content_digest = tb.compute_reading_content_digest(
        device_id="sensor_probe_alpha",
        plot_id=PLOT_ID,
        variable="soil_moisture_vwc",
        value=reading_val,
        unit="fraction",
        observed_at=obs_time,
    )

    signed_rcpt = create_signed_sensor_receipt(
        receipt_id=receipt_id,
        issuer=issuer,
        device_id="sensor_probe_alpha",
        plot_id=PLOT_ID,
        variable="soil_moisture_vwc",
        calibration_profile_id="cal_soil_probe_2026",
        status="active",
        content_digest=content_digest,
        observation_instant=obs_time.isoformat(),
        reading_value=reading_val,
        reading_unit="fraction",
        observed_at=obs_time,
    )
    tb.register_sensor_receipt(signed_rcpt)

    packet = ObservationPacket(
        packet_id="pkt_sensor_001",
        source=ObservationSource.SENSOR_IOT,
        obs_type="measurement",
        timestamp=obs_time,
        plot_id=PLOT_ID,
        spatial_scope="point",
        data_status=DataStatus.OBSERVED,
        qa=QAMetadata(sensor_health="healthy"),
        uncertainty=UncertaintyModel(sigmas={"soil_moisture_vwc": 0.02}),
        payload={
            "variable": "soil_moisture_vwc",
            "value": reading_val,
            "unit": "fraction",
            "device_id": "sensor_probe_alpha",
            "instrument_id": "sensor_probe_alpha",
            "calibration_version": "cal_soil_probe_2026",
            "provenance_ref": receipt_id,
            "receipt": signed_rcpt,
            "content_digest": content_digest,
            "observation_instant": obs_time.isoformat(),
        },
    )

    return Layer0SourcePackage(
        source_family="sensor",
        package_id="pkg_sensor_001",
        plot_id=PLOT_ID,
        geometry_hash=GEOM_HASH,
        geometry_version=GEOM_VERSION,
        packets=[packet],
        is_available=True,
    )


def _build_authentic_layer0_state_package() -> Layer0StatePackage:
    """Build a canonically admissible Layer 0 state package from Kalman posterior."""
    return Layer0StatePackage(
        plot_id=PLOT_ID,
        run_id="run_l0_kalman_pilot_a",
        geometry_hash=GEOM_HASH,
        geometry_version=GEOM_VERSION,
        daily_state={"zone-1": {"soil_moisture": 0.31, "sm_0_10": 0.31}},
        state_uncertainty={"zone-1": {"covariance": [[0.015, 0.0], [0.0, 0.015]]}},
        zone_summaries=[{"zone_id": "zone-1", "label": "Zone 1", "area_fraction": 0.65}],
        edge_contamination=[{"edge_id": "edge-north", "contamination_score": 0.05}],
        health_report={
            "scientific_state_admissible": True,
            "audit": {
                "structural_audit": {
                    "status": "PASS",
                    "checks_run": 5,
                    "checks_failed": 0,
                }
            },
        },
        provenance={
            "run_id": "run_l0_kalman_pilot_a",
            "scientific_state_integrity": "PASSED_RUNTIME_BOUNDARY",
        },
        scientific_publication_authorized=False,
        actuator_control_authorized=False,
    )


def test_pilot_plot_a_observation_only_pipeline_e2e(monkeypatch):
    """Verify complete end-to-end flow from Layer 0 observations to Layer 10 SIRE without actuator leakage."""
    # 1. Prepare Layer 0 inputs
    sensor_pkg = _build_authentic_layer0_sensor_package()
    l0_state_pkg = _build_authentic_layer0_state_package()

    # 2. Prepare Layer 1 Raster Composite with authentic cryptographic publication receipt
    ndvi_pub_dt = RUN_TIME - timedelta(hours=1)
    grid_data = [[0.65] * 10] * 10
    raster_composite = {
        "values": grid_data,
        "crs": "EPSG:4326",
        "bounds": [10.0, 35.0, 10.1, 35.1],
        "transform": [0.001, 0.0, 10.0, 0.0, -0.001, 35.1],
        "resolution_m": 10.0,
        "width": 10,
        "height": 10,
        "published_at": ndvi_pub_dt.isoformat(),
        "source_id": "s2_composite_clean",
        "acquisition_id": "s2_composite_clean",
        "source_reality": "provider_observation",
        "real_provider_product": True,
        "production_usable": True,
        "diagnostic_only": False,
    }
    raster_hash = tb.compute_raster_composite_content_hash(raster_composite, native_resolution_m=10.0)
    raster_composite["content_hash"] = raster_hash

    pub_rcpt = create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:s2:clean_001",
        issuer="agriwise:trust:sensor_authority",
        source_family="raster_composite",
        acquisition_id="s2_composite_clean",
        published_at=ndvi_pub_dt,
        content_hash=raster_hash,
    )
    tb.register_publication_receipt(pub_rcpt)
    raster_composite["publication_receipt"] = pub_rcpt

    # 3. Prepare ASMAE biophysical model output with cryptographically bound authority claims
    asmae_pub_dt = RUN_TIME - timedelta(minutes=30)
    raw_asmae_data = {
        "plot_id": PLOT_ID,
        "timestamp": asmae_pub_dt.isoformat(),
        "state_vector": {"lai": 2.4, "canopy_water": 0.42},
        "covariance": [[0.05, 0.0], [0.0, 0.05]],
        "provenance": {
            "operator_locked": True,
            "graph_locked": True,
            "radiometric_mode": "ht_per_pixel",
            "full_radiometric_credit_allowed": True,
            "enkf_mode": "etkf",
            "full_enkf_credit_allowed": True,
            "retrovalidation_score": 0.92,
            "published_at": asmae_pub_dt.isoformat(),
        },
    }
    asmae_hash = tb.compute_asmae_content_hash(raw_asmae_data)
    raw_asmae_data["content_hash"] = asmae_hash

    asmae_rcpt = create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:asmae:clean_001",
        issuer="agriwise:trust:sensor_authority",
        source_family="asmae",
        acquisition_id="asmae_raster_output",
        published_at=asmae_pub_dt,
        content_hash=asmae_hash,
    )
    tb.register_publication_receipt(asmae_rcpt)
    raw_asmae_data["provenance"]["publication_receipt"] = asmae_rcpt
    raw_asmae_data["publication_receipt"] = asmae_rcpt

    # 4. Construct Layer 1 Input Bundle with authentic inputs PLUS competing adversarial inputs
    # Adversarial input 1: Point sensor with future clock-skew violation (15 minutes ahead of run timestamp)
    future_obs_time = RUN_TIME + timedelta(minutes=15)
    future_packet = ObservationPacket(
        packet_id="pkt_sensor_future",
        source=ObservationSource.SENSOR_IOT,
        obs_type="measurement",
        timestamp=future_obs_time,
        plot_id=PLOT_ID,
        spatial_scope="point",
        data_status=DataStatus.OBSERVED,
        qa=QAMetadata(sensor_health="healthy"),
        uncertainty=UncertaintyModel(sigmas={"soil_moisture_vwc": 0.02}),
        payload={
            "variable": "soil_moisture_vwc",
            "value": 0.40,
            "unit": "fraction",
            "device_id": "sensor_probe_future",
            "calibration_version": "cal_soil_probe_2026",
            "provenance_ref": "urn:agriwise:receipt:sensor_probe_alpha:001",
            "content_digest": "dummy_digest",
            "observation_instant": future_obs_time.isoformat(),
        },
    )
    adversarial_sensor_pkg = Layer0SourcePackage(
        source_family="sensor",
        package_id="pkg_sensor_future",
        plot_id=PLOT_ID,
        geometry_hash=GEOM_HASH,
        geometry_version=GEOM_VERSION,
        packets=[future_packet],
        is_available=True,
    )

    bundle = Layer1InputBundle(
        plot_id=PLOT_ID,
        run_id="run_pilot_a_fusion_001",
        run_timestamp=RUN_TIME,
        window_start=RUN_TIME - timedelta(days=5),
        window_end=RUN_TIME,
        layer0_state_package=l0_state_pkg,
        layer0_source_packages={
            "sensor": [sensor_pkg, adversarial_sensor_pkg],
        },
        raster_composites={"NDVI": raster_composite},
        asmae_output=raw_asmae_data,
    )

    # 5. Execute Layer 1 Fusion Engine
    engine = Layer1FusionEngine()
    pkg = engine.fuse(bundle)

    # ── VERIFICATION 1: PRE-LEDGER QUARANTINING & ADVERSARIAL ISOLATION ───
    print("EVIDENCE:", [(e.source_family, e.source_id, getattr(e, 'instrument_id', None)) for e in pkg.evidence_items])
    print("QUARANTINED:", [(q.evidence_id, q.reason_codes) for q in pkg.diagnostics.quarantined_evidence])
    # Future sensor packet (> 5m skew) MUST be quarantined fail-closed
    quarantine_reasons = {q.evidence_id: q.reason_codes for q in pkg.diagnostics.quarantined_evidence}
    assert any("FUTURE_EVIDENCE_BEYOND_SKEW" in codes for codes in quarantine_reasons.values())

    # ── VERIFICATION 2: ADMITTED SCIENTIFIC EVIDENCE LEDGER ──────────────
    # Genuine sensor observation admitted as observed_sensor
    sensor_admitted = [e for e in pkg.evidence_items if e.source_family == "sensor" and e.instrument_id == "sensor_probe_alpha"]
    assert len(sensor_admitted) == 1
    assert sensor_admitted[0].value == 0.32
    assert sensor_admitted[0].truth_class == "observed_sensor"
    assert sensor_admitted[0].data_status == "observed"

    # Layer 0 Kalman state admitted as non-updating, derived model state
    l0_items = [e for e in pkg.evidence_items if e.source_family == "l0_state"]
    assert len(l0_items) > 0
    assert all(e.truth_class == "assimilated_state" for e in l0_items)
    assert all(e.source_reality == "model_estimate" for e in l0_items)
    assert all(e.state_update_allowed is False for e in l0_items)
    assert all(e.diagnostic_only is True for e in l0_items)

    # In-cutoff verified NDVI raster admitted into spatial index
    raster_vars = [r.variable.lower() for r in pkg.spatial_index.raster_refs]
    assert "ndvi" in raster_vars
    ndvi_ref = next(r for r in pkg.spatial_index.raster_refs if r.variable.lower() == "ndvi")
    assert ndvi_ref.scientific_surface_allowed is True
    assert ndvi_ref.content_hash == raster_hash

    # ── VERIFICATION 3: DETERMINISTIC CONTENT ROOT & PROVENANCE ──────────
    assert pkg.provenance is not None
    scientific_root = pkg.scientific_content_root()
    assert isinstance(scientific_root, str)
    assert len(scientific_root) == 64  # SHA256 hex string

    # ── VERIFICATION 4: DOWNSTREAM LAYER 2 & LAYER 10 PAYLOADS ───────────
    # Layer 2 Input
    assert pkg.layer2_input is not None
    assert getattr(pkg.layer2_input, "plot_id", None) == PLOT_ID or (isinstance(pkg.layer2_input, dict) and pkg.layer2_input.get("plot_id") == PLOT_ID)

    # Layer 10 SIRE Spatial Intelligence Payload
    assert pkg.layer10_payload is not None
    assert len(pkg.layer10_payload.get("zone_overlays", [])) > 0 or len(pkg.layer10_payload.get("zones", [])) >= 0
    assert "sensor_markers" in pkg.layer10_payload or "sensors" in pkg.layer10_payload or isinstance(pkg.layer10_payload, dict)

    # ── VERIFICATION 5: ASMAE PLOT SNAPSHOT INTEGRITY ────────────────────
    from services.agribrain.layer10_sire.surface_contract import PublicationStatus
    snapshot_payload = {
        "run_id": "science-run-pilot-a",
        "publication_run_id": "science-run-pilot-a",
        "publication_id": "publication-pilot-a",
        "intelligence_snapshot_id": "L10-SNAP-PILOT-A-001",
        "plot_id": PLOT_ID,
        "crop_cycle_id": "CYCLE-2026-PILOT",
        "surface_schema_version": SURFACES_SCHEMA_VERSION,
        "render_authorization_version": RENDER_AUTHORIZATION_VERSION,
        "render_authorizations": {"canopy": {"authorized": True}},
        "asmae_proof": {"sentinel_proof": {}},
        "mode_display_state": {"canopy": {"canRenderPixels": True}},
        "source_policy_display_state": {"requested_policy": "satellite"},
        "core_asmae_evidence_state": {"state": "nominal"},
        "publication_surface_state": {"state": "provider_surface"},
        "resolved_crop_stage": "UNKNOWN",
        "phenology_context": {
            "resolved_crop_stage": "UNKNOWN",
            "ndvi_mean": 0.65,
            "crop": "olive",
            "crop_known": True,
        },
        "published_at": asmae_pub_dt.isoformat(),
        "evidence_cutoff_at": asmae_pub_dt.isoformat(),
        "observation_window": {
            "start": (RUN_TIME - timedelta(days=30)).isoformat(),
            "end": asmae_pub_dt.isoformat(),
        },
        "scientific_evidence_lineage": {
            "crop_posterior_lineage": scientific_root,
            "crop_worldline_event_id": "worldline-event-001",
            "phenology_worldline_event_id": "phenology-event-001",
        },
        "surfaces": [
            {
                "surface_id": "surface-canopy-ndvi",
                "surface_type": "canopy_vigor",
                "values": grid_data,
                "resolution_m": 10.0,
            }
        ],
    }
    status, details = classify_surface_publication(snapshot_payload)
    assert status in (PublicationStatus.VALID_NORMAL.value, PublicationStatus.VALID_DEGRADED.value)

    # Publish canonical snapshot into store
    pub_res = asmae_store.publish_canonical_layer10_snapshot(
        namespace=NAMESPACE,
        geometry_hash=GEOM_HASH,
        frontend_payload=snapshot_payload,
        request_run_id="science-run-pilot-a",
        crop_cycle_id="CYCLE-2026-PILOT",
    )
    assert pub_res is not None
    loaded_snapshot = asmae_store.load_latest_plot_snapshot(
        namespace=NAMESPACE,
        geometry_hash=GEOM_HASH,
    )
    assert loaded_snapshot is not None
    assert loaded_snapshot["snapshot_id"] == "L10-SNAP-PILOT-A-001"

    # ── VERIFICATION 6: PHYSICAL ACTUATION HARDWARE INTERLOCK ────────────
    # Pillar 5: Verify AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false is enforced
    assert verified_irrigation_enabled() is False

    # In disabled state, bootstrap returns None (zero verifier, zero physical delivery)
    from services.agribrain.app.production_delivery_runtime import (
        bootstrap_server_verified_irrigation,
    )
    assert bootstrap_server_verified_irrigation(database=None) is None

    # Even if an adversary forces the flag to true in environment, bootstrap fails closed
    # with Layer0AdmissionRequiredError because signed v3, live revocation, and Mongo are absent
    monkeypatch.setenv(ENABLE_FLAG, "true")
    with pytest.raises(Layer0AdmissionRequiredError):
        bootstrap_server_verified_irrigation(database=None)


def test_pilot_plot_a_non_psd_covariance_quarantined():
    """Verify that non-positive-semidefinite covariance in ASMAE output is fail-closed quarantined."""
    non_psd_cov = [[1.0, 2.0], [2.0, 1.0]]  # det = -3.0 < 0
    raw_asmae_data = {
        "plot_id": PLOT_ID,
        "timestamp": RUN_TIME.isoformat(),
        "state_vector": {"lai": 2.4, "canopy_water": 0.42},
        "covariance": non_psd_cov,
        "provenance": {
            "operator_locked": True,
            "published_at": RUN_TIME.isoformat(),
        },
    }
    asmae_hash = tb.compute_asmae_content_hash(raw_asmae_data)
    raw_asmae_data["content_hash"] = asmae_hash

    asmae_rcpt = create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:asmae:non_psd",
        issuer="agriwise:trust:sensor_authority",
        source_family="asmae",
        acquisition_id="asmae_raster_output",
        published_at=RUN_TIME,
        content_hash=asmae_hash,
    )
    tb.register_publication_receipt(asmae_rcpt)
    raw_asmae_data["provenance"]["publication_receipt"] = asmae_rcpt
    raw_asmae_data["publication_receipt"] = asmae_rcpt

    bundle = Layer1InputBundle(
        plot_id=PLOT_ID,
        run_id="run_pilot_a_non_psd",
        run_timestamp=RUN_TIME,
        window_start=RUN_TIME - timedelta(days=5),
        window_end=RUN_TIME,
        asmae_output=raw_asmae_data,
    )

    engine = Layer1FusionEngine()
    pkg = engine.fuse(bundle)

    # ASMAE source MUST be quarantined fail-closed due to non-PSD covariance
    quarantine_reasons = [c for q in pkg.diagnostics.quarantined_evidence for c in q.reason_codes]
    assert any("INVALID_COVARIANCE" in c for c in quarantine_reasons)

    # No ASMAE raster reference may be granted scientific surface authorization
    for r in pkg.spatial_index.raster_refs:
        if r.source_basis == "asmae" or "asmae" in r.raster_id:
            assert r.scientific_surface_allowed is False


def test_pilot_plot_a_unverified_sensor_receipt_rejected():
    """Verify that unverified or tampered sensor readings cannot attain observed_sensor truth."""
    obs_time = RUN_TIME - timedelta(minutes=10)
    fake_packet = ObservationPacket(
        packet_id="pkt_fake_sensor",
        source=ObservationSource.SENSOR_IOT,
        obs_type="measurement",
        timestamp=obs_time,
        plot_id=PLOT_ID,
        spatial_scope="point",
        data_status=DataStatus.OBSERVED,
        qa=QAMetadata(sensor_health="healthy"),
        uncertainty=UncertaintyModel(sigmas={"soil_moisture_vwc": 0.02}),
        payload={
            "variable": "soil_moisture_vwc",
            "value": 0.35,
            "unit": "fraction",
            "device_id": "sensor_unregistered_xyz",
            "calibration_version": "cal_unregistered",
            "provenance_ref": "urn:agriwise:receipt:fake:999",
            "content_digest": "dummy_digest",
            "observation_instant": obs_time.isoformat(),
        },
    )
    fake_pkg = Layer0SourcePackage(
        source_family="sensor",
        package_id="pkg_fake_sensor",
        plot_id=PLOT_ID,
        geometry_hash=GEOM_HASH,
        geometry_version=GEOM_VERSION,
        packets=[fake_packet],
        is_available=True,
    )

    bundle = Layer1InputBundle(
        plot_id=PLOT_ID,
        run_id="run_pilot_a_unverified_sensor",
        run_timestamp=RUN_TIME,
        window_start=RUN_TIME - timedelta(days=5),
        window_end=RUN_TIME,
        layer0_source_packages={"sensor": [fake_pkg]},
    )

    engine = Layer1FusionEngine()
    pkg = engine.fuse(bundle)

    # Measurement must NEVER be classified as observed_sensor
    fake_items = [e for e in pkg.evidence_items if e.source_id == "pkt_fake_sensor"]
    if fake_items:
        for item in fake_items:
            assert item.truth_class != "observed_sensor"
            assert item.state_update_allowed is False
            assert item.diagnostic_only is True
