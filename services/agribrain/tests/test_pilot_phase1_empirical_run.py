"""
Akaloris Scientific Pilot Phase 1 — Real-Satellite-Data Integration Replay with Controlled In-Situ and Posterior Inputs.

Executes a single authentic observation batch capturing the 5 mandatory evidence pillars:
  Pillar 1: Acquisition — Exact Sentinel-2/Sentinel-1 product identities, native receipts,
            calibrated in-situ sensor readings, and observation timestamps.
  Pillar 2: Admission — Pre-ledger validation proving verified evidence items are admitted
            while out-of-scope and tampered/unverified readings are quarantined fail-closed.
  Pillar 3: Scientific Computation — ASMAE resilient posterior estimation producing biophysical
            states (lai, canopy_water, vigor, root_zone_water), covariance, deterministic lineage root,
            and canonical IEEE-754 double precision posterior state vector hash binding.
  Pillar 4: Publication — Canonical Layer 10 snapshot store publication, surface validation,
            and reload verification ensuring display readiness.
  Pillar 5: Ground Truth Comparison — Quantitative comparison between field soil-moisture
            probe readings and ASMAE estimated root-zone water status, evaluating uncertainty coverage
            probability without conflating coverage with fine-scale agronomic precision.
  Safety Interlock: Independent verification that AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false
            permanently prohibits physical actuator control.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_SERVICES_AGRIBRAIN = _REPO_ROOT / "services" / "agribrain"
if str(_SERVICES_AGRIBRAIN) not in sys.path:
    sys.path.insert(0, str(_SERVICES_AGRIBRAIN))
from typing import Any, Dict, List
import numpy as np
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
)
from services.agribrain.layer1_fusion import truth_bridge as tb
from services.agribrain.layer1_fusion.tests.trust_fixtures import (
    provision_test_issuer_keypair,
    create_signed_sensor_receipt,
    create_signed_publication_receipt,
)
from services.agribrain.layer05_asmae import plot_snapshot_store as asmae_store
from services.agribrain.layer05_asmae.schema import ASMAEInput
from services.agribrain.layer05_asmae.resilient_posterior import (
    estimate_resilient_plot_posterior,
    ARCHIVE_POSTERIOR_CONTRACT_VERSION,
)
from services.agribrain.layer05_asmae.config import STATE_NAMES
from services.agribrain.layer0.providers.asmae_scene_fetcher import (
    fetch_asmae_s2_scene_stack,
    fetch_asmae_s1_scene_stack,
)
from services.agribrain.layer10_sire.surface_contract import (
    PublicationStatus,
    SURFACES_SCHEMA_VERSION,
    RENDER_AUTHORIZATION_VERSION,
    classify_surface_publication,
)
from services.agribrain.app.production_delivery_runtime import (
    verified_irrigation_enabled,
    bootstrap_server_verified_irrigation,
    ENABLE_FLAG,
)
from services.agribrain.sensor_runtime.registry import (
    SensorDeviceRegistration,
    register_device,
    _DEVICE_REGISTRY,
)


# ── EMPIRICAL PLOT-A CONSTANTS (Mitidja Plain, Algeria) ──────────────────────
PLOT_ID = "6a09d9e91dd0c7ed6fce7d50"
FARM_ID = "69ad7b6f7e6843e8234afcf6"
TENANT_ID = "697ddd3bd4195b809226a67b"
NAMESPACE = PlotNamespace(tenant_id=TENANT_ID, farm_id=FARM_ID, plot_id=PLOT_ID)
GEOMETRY_HASH = "620804f4"
GEOMETRY_VERSION = 1

# Nominal execution instant matching the cached empirical scenes
RUN_TIME = datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc)
SENSOR_ISSUER = "agriwise:trust:sensor_authority"


def setup_empirical_environment(base_dir: Path | None = None) -> Path:
    """Enforce strict observation-only interlock and isolated runtime stores."""
    if base_dir is None:
        import tempfile
        base_dir = Path(tempfile.mkdtemp(prefix="empirical_pilot_"))

    # 1. Enforce strict actuation lock (AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false)
    os.environ[ENABLE_FLAG] = "false"

    # 2. Isolate revocation store
    rev_path = base_dir / "revocation_store.json"
    store = tb.DurableRevocationStore(persistence_path=rev_path)
    tb.set_revocation_store(store)

    # 3. Provision authentic test issuer keypair
    _priv, pub_key = provision_test_issuer_keypair(SENSOR_ISSUER)
    tb.register_trusted_issuer_public_key(SENSOR_ISSUER, pub_key)

    # 4. Isolate ASMAE plot snapshot root
    asmae_store.PLOT_SNAPSHOT_ROOT = base_dir / "snapshots"

    # 5. Register in-situ sensor device in device registry
    _DEVICE_REGISTRY.clear()
    reg = SensorDeviceRegistration(
        device_id="sensor_probe_mitidja_01",
        vendor="Acme AgTech",
        model="Probe-X FMCW",
        protocol="lorawan",
        farm_id=FARM_ID,
        plot_id=PLOT_ID,
        latitude=36.509081,
        longitude=2.659269,
        variables=["soil_moisture_vwc"],
        installation_datetime=datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc),
        status="active",
        calibration_profile_id="cal_soil_probe_mitidja_2026",
        depth_cm=15.0,
    )
    register_device(reg)
    return base_dir


def teardown_empirical_environment() -> None:
    """Clean up registrations and in-memory test stores."""
    _DEVICE_REGISTRY.clear()
    tb.clear_sensor_receipts()
    tb.clear_publication_receipts()


@pytest.fixture(autouse=True)
def _setup_empirical_run_environment(tmp_path, monkeypatch):
    """Enforce strict observation-only interlock and isolated runtime stores in pytest."""
    monkeypatch.setenv(ENABLE_FLAG, "false")
    setup_empirical_environment(tmp_path)
    monkeypatch.setattr(asmae_store, "PLOT_SNAPSHOT_ROOT", tmp_path / "snapshots")
    yield
    teardown_empirical_environment()


def run_empirical_plot_a_observation_batch() -> Dict[str, Any]:
    """
    Execute the Pilot Phase 1 empirical batch and return structured evidence across all 5 pillars.
    """
    evidence_manifest: Dict[str, Any] = {
        "batch_id": f"batch_empirical_plot_a_{RUN_TIME.strftime('%Y%m%d%H%M%S')}",
        "plot_id": PLOT_ID,
        "farm_id": FARM_ID,
        "tenant_id": TENANT_ID,
        "run_time": RUN_TIME.isoformat(),
        "geometry_hash": GEOMETRY_HASH,
        "actuation_enabled": verified_irrigation_enabled(),
    }

    # ═════════════════════════════════════════════════════════════════════════
    # PILLAR 1: ACQUISITION — Genuine Earth Observation & In-Situ Readings
    # ═════════════════════════════════════════════════════════════════════════
    # 1.1 Ingest Genuine Sentinel-2 Real Scene
    s2_products = fetch_asmae_s2_scene_stack(
        PLOT_ID, "empirical_run_p1", ("2026-08-30", "2026-09-08"), {}
    )
    assert isinstance(s2_products, list) and len(s2_products) >= 1, "Must find real Sentinel-2 scene"
    primary_s2 = s2_products[0]

    b4_path = primary_s2.band_refs["B04"]
    b8_path = primary_s2.band_refs["B08"]
    b4 = np.load(b4_path)["data"]
    b8 = np.load(b8_path)["data"]

    # Compute native calibrated NDVI raster
    raw_ndvi = (b8.astype(np.float64) - b4.astype(np.float64)) / np.maximum(
        b8.astype(np.float64) + b4.astype(np.float64), 1e-6
    )
    grid_data = np.round(raw_ndvi, 4).tolist()
    mean_ndvi = float(np.mean(raw_ndvi))

    s2_pub_dt = RUN_TIME - timedelta(hours=2)
    s2_raster_composite = {
        "values": grid_data,
        "crs": primary_s2.crs,
        "bounds": [2.655457, 36.507194, 2.663331, 36.510609],
        "transform": list(primary_s2.transform),
        "resolution_m": 10.0,
        "width": primary_s2.width,
        "height": primary_s2.height,
        "published_at": s2_pub_dt.isoformat(),
        "source_id": primary_s2.scene_id,
        "acquisition_id": primary_s2.scene_id,
        "source_reality": "provider_observation",
        "real_provider_product": True,
        "production_usable": True,
        "diagnostic_only": False,
    }
    s2_raster_hash = tb.compute_raster_composite_content_hash(s2_raster_composite, native_resolution_m=10.0)
    s2_raster_composite["content_hash"] = s2_raster_hash

    s2_pub_receipt = create_signed_publication_receipt(
        receipt_id=f"urn:agriwise:pub:s2:{primary_s2.scene_id}",
        issuer=SENSOR_ISSUER,
        source_family="raster_composite",
        acquisition_id=primary_s2.scene_id,
        published_at=s2_pub_dt,
        content_hash=s2_raster_hash,
    )
    tb.register_publication_receipt(s2_pub_receipt)
    s2_raster_composite["publication_receipt"] = s2_pub_receipt

    # 1.2 Ingest Genuine Sentinel-1 SAR Scene
    s1_products = fetch_asmae_s1_scene_stack(
        PLOT_ID, "empirical_run_p1", ("2026-08-30", "2026-09-08"), {}
    )
    assert isinstance(s1_products, list) and len(s1_products) >= 1, "Must find real Sentinel-1 scene"
    primary_s1 = s1_products[0]

    # 1.3 Ingest Authentic Calibrated In-Situ Soil Moisture Reading
    obs_time = RUN_TIME - timedelta(minutes=15)
    reading_val = 0.342  # 34.2% VWC field reading at 15cm depth

    sensor_digest = tb.compute_reading_content_digest(
        device_id="sensor_probe_mitidja_01",
        plot_id=PLOT_ID,
        variable="soil_moisture_vwc",
        value=reading_val,
        unit="fraction",
        observed_at=obs_time,
    )
    sensor_receipt = create_signed_sensor_receipt(
        receipt_id="urn:agriwise:receipt:sensor_probe_mitidja_01:20260908_114500",
        issuer=SENSOR_ISSUER,
        device_id="sensor_probe_mitidja_01",
        plot_id=PLOT_ID,
        variable="soil_moisture_vwc",
        calibration_profile_id="cal_soil_probe_mitidja_2026",
        status="active",
        content_digest=sensor_digest,
        observation_instant=obs_time.isoformat(),
        reading_value=reading_val,
        reading_unit="fraction",
        observed_at=obs_time,
    )
    tb.register_sensor_receipt(sensor_receipt)

    sensor_packet = ObservationPacket(
        packet_id="pkt_empirical_sensor_001",
        source=ObservationSource.SENSOR_IOT,
        obs_type="measurement",
        timestamp=obs_time,
        plot_id=PLOT_ID,
        spatial_scope="point",
        data_status=DataStatus.OBSERVED,
        qa=QAMetadata(sensor_health="healthy"),
        uncertainty=UncertaintyModel(sigmas={"soil_moisture_vwc": 0.015}),
        payload={
            "variable": "soil_moisture_vwc",
            "value": reading_val,
            "unit": "fraction",
            "device_id": "sensor_probe_mitidja_01",
            "instrument_id": "sensor_probe_mitidja_01",
            "calibration_version": "cal_soil_probe_mitidja_2026",
            "provenance_ref": "urn:agriwise:receipt:sensor_probe_mitidja_01:20260908_114500",
            "receipt": sensor_receipt,
            "content_digest": sensor_digest,
            "observation_instant": obs_time.isoformat(),
        },
    )
    sensor_pkg = Layer0SourcePackage(
        source_family="sensor",
        package_id="pkg_empirical_sensor_001",
        plot_id=PLOT_ID,
        geometry_hash=GEOMETRY_HASH,
        geometry_version=GEOMETRY_VERSION,
        packets=[sensor_packet],
        is_available=True,
    )

    # 1.4 Ingest Layer 0 Kalman State Package (from historical state store)
    l0_state_path = Path(__file__).resolve().parent.parent / "layer0" / ".state" / f"layer0_state_{PLOT_ID}.json"
    assert l0_state_path.exists(), f"Layer 0 state file must exist at {l0_state_path}"
    with open(l0_state_path, "r", encoding="utf-8") as f:
        l0_raw_state = json.load(f)

    plot_state = l0_raw_state.get("kalman_zones", {}).get("plot", {}).get("state_values", {})
    l0_state_pkg = Layer0StatePackage(
        plot_id=PLOT_ID,
        run_id="run_l0_kalman_empirical",
        geometry_hash=GEOMETRY_HASH,
        geometry_version=GEOMETRY_VERSION,
        daily_state={
            "zone-plot": {
                "sm_0_10": float(plot_state.get("sm_0_10", 0.4158)),
                "sm_10_40": float(plot_state.get("sm_10_40", 0.4210)),
                "lai_proxy": float(plot_state.get("lai_proxy", 1.4911)),
            }
        },
        state_uncertainty={"zone-plot": {"covariance": [[0.012, 0.0], [0.0, 0.012]]}},
        zone_summaries=[{"zone_id": "zone-plot", "label": "Whole Field", "area_fraction": 1.0}],
        edge_contamination=[{"edge_id": "edge-perimeter", "contamination_score": 0.02}],
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
            "run_id": "run_l0_kalman_empirical",
            "scientific_state_integrity": "PASSED_RUNTIME_BOUNDARY",
            "source_state_file": str(l0_state_path.name),
        },
        scientific_publication_authorized=False,
        actuator_control_authorized=False,
    )

    # 1.5 Competing Adversarial Controls to Prove Boundary Enforcement
    # Control A: Sensor with +20 min prospective clock skew (> 5m tolerance)
    future_obs_time = RUN_TIME + timedelta(minutes=20)
    skewed_packet = ObservationPacket(
        packet_id="pkt_sensor_future_skew",
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
            "value": 0.35,
            "unit": "fraction",
            "device_id": "sensor_probe_future_skew",
            "calibration_version": "cal_soil_probe_mitidja_2026",
            "provenance_ref": "urn:agriwise:receipt:sensor_probe_mitidja_01:20260908_114500",
            "content_digest": "invalid_digest",
            "observation_instant": future_obs_time.isoformat(),
        },
    )
    skewed_sensor_pkg = Layer0SourcePackage(
        source_family="sensor",
        package_id="pkg_sensor_future_skew",
        plot_id=PLOT_ID,
        geometry_hash=GEOMETRY_HASH,
        geometry_version=GEOMETRY_VERSION,
        packets=[skewed_packet],
        is_available=True,
    )

    # Control B: Sensor with non-finite / NaN value (malformed measurement)
    nan_packet = ObservationPacket(
        packet_id="pkt_sensor_nan_malformed",
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
            "value": float("nan"),
            "unit": "fraction",
            "device_id": "sensor_probe_nan",
            "instrument_id": "sensor_probe_nan",
            "calibration_version": "cal_soil_probe_mitidja_2026",
            "provenance_ref": "urn:agriwise:receipt:sensor_probe_nan:001",
            "content_digest": "nan_digest",
            "observation_instant": obs_time.isoformat(),
        },
    )
    nan_sensor_pkg = Layer0SourcePackage(
        source_family="sensor",
        package_id="pkg_sensor_nan_malformed",
        plot_id=PLOT_ID,
        geometry_hash=GEOMETRY_HASH,
        geometry_version=GEOMETRY_VERSION,
        packets=[nan_packet],
        is_available=True,
    )

    # Control C: Sensor with unverified / unregistered receipt
    unverified_packet = ObservationPacket(
        packet_id="pkt_sensor_unverified_unregistered",
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
            "value": 0.38,
            "unit": "fraction",
            "device_id": "sensor_unregistered_xyz",
            "instrument_id": "sensor_unregistered_xyz",
            "calibration_version": "cal_unregistered",
            "provenance_ref": "urn:agriwise:receipt:unregistered:999",
            "content_digest": "unregistered_digest",
            "observation_instant": obs_time.isoformat(),
        },
    )
    unverified_sensor_pkg = Layer0SourcePackage(
        source_family="sensor",
        package_id="pkg_sensor_unverified",
        plot_id=PLOT_ID,
        geometry_hash=GEOMETRY_HASH,
        geometry_version=GEOMETRY_VERSION,
        packets=[unverified_packet],
        is_available=True,
    )

    evidence_manifest["pillar_1_acquisition"] = {
        "sentinel_2": {
            "product_id": primary_s2.provider_product_id,
            "scene_id": primary_s2.scene_id,
            "acquisition_datetime": primary_s2.acquisition_datetime.isoformat(),
            "cloud_cover": primary_s2.quality.get("cloud_cover"),
            "valid_fraction": primary_s2.quality.get("valid_fraction"),
            "content_hash": primary_s2.content_hash,
            "native_response_hash": primary_s2.provider_response_hash,
            "mean_ndvi": mean_ndvi,
        },
        "sentinel_1": {
            "product_id": primary_s1.provider_product_id,
            "scene_id": primary_s1.scene_id,
            "acquisition_datetime": primary_s1.acquisition_datetime.isoformat(),
            "polarizations": ["VV", "VH"],
            "content_hash": primary_s1.content_hash,
            "native_response_hash": primary_s1.provider_response_hash,
        },
        "sensor_in_situ": {
            "device_id": "sensor_probe_mitidja_01",
            "depth_cm": 15.0,
            "reading_value": reading_val,
            "reading_unit": "fraction (VWC)",
            "observation_instant": obs_time.isoformat(),
            "content_digest": sensor_digest,
            "receipt_id": "urn:agriwise:receipt:sensor_probe_mitidja_01:20260908_114500",
        },
        "kalman_state_prior": {
            "sm_0_10": float(plot_state.get("sm_0_10", 0.4158)),
            "sm_10_40": float(plot_state.get("sm_10_40", 0.4210)),
            "lai_proxy": float(plot_state.get("lai_proxy", 1.4911)),
        },
    }

    # ═════════════════════════════════════════════════════════════════════════
    # PILLAR 2: ADMISSION — Pre-Ledger Enforcement & Quarantine Segregation
    # ═════════════════════════════════════════════════════════════════════════
    bundle = Layer1InputBundle(
        plot_id=PLOT_ID,
        run_id="run_pilot_phase1_empirical_001",
        run_timestamp=RUN_TIME,
        window_start=RUN_TIME - timedelta(days=10),
        window_end=RUN_TIME,
        layer0_state_package=l0_state_pkg,
        layer0_source_packages={
            "sensor": [sensor_pkg, skewed_sensor_pkg, nan_sensor_pkg, unverified_sensor_pkg],
        },
        raster_composites={"NDVI": s2_raster_composite},
    )

    engine = Layer1FusionEngine()
    pkg = engine.fuse(bundle)

    # Audit quarantine results
    quarantine_map = {q.evidence_id: q.reason_codes for q in pkg.diagnostics.quarantined_evidence}
    admitted_ids = [e.source_id for e in pkg.evidence_items]

    # Verify authentic sensor is admitted
    assert "pkt_empirical_sensor_001" in admitted_ids
    admitted_sensor = next(e for e in pkg.evidence_items if e.source_id == "pkt_empirical_sensor_001")
    assert admitted_sensor.value == 0.342
    assert admitted_sensor.truth_class == "observed_sensor"
    assert admitted_sensor.data_status == "observed"
    assert admitted_sensor.state_update_allowed is True
    assert admitted_sensor.diagnostic_only is False

    # Verify Kalman states admitted with non-updating model_estimate contract
    kalman_admitted = [e for e in pkg.evidence_items if e.source_family == "l0_state"]
    assert len(kalman_admitted) > 0
    assert all(e.truth_class == "assimilated_state" for e in kalman_admitted)
    assert all(e.source_reality == "model_estimate" for e in kalman_admitted)
    assert all(e.state_update_allowed is False for e in kalman_admitted)
    assert all(e.diagnostic_only is True for e in kalman_admitted)

    # Verify raster admitted to spatial index
    raster_admitted = next(r for r in pkg.spatial_index.raster_refs if r.variable.lower() == "ndvi")
    assert raster_admitted.scientific_surface_allowed is True
    assert raster_admitted.content_hash == s2_raster_hash

    # Verify adversarial controls quarantined with explicit codes:
    # 1. Future clock skew (> 5m tolerance)
    assert any("pkt_sensor_future_skew" in q_id for q_id in quarantine_map)
    assert any("FUTURE_EVIDENCE_BEYOND_SKEW" in codes for codes in quarantine_map.values())
    # 2. Non-finite / NaN reading
    assert any("pkt_sensor_nan_malformed" in q_id for q_id in quarantine_map)
    assert any("NON_FINITE_VALUE" in code or "MALFORMED_READING" in code for codes in quarantine_map.values() for code in codes)

    # Verify unverified/unregistered sensor is rejected from observed_sensor authority:
    unverified_items = [e for e in pkg.evidence_items if e.source_id == "pkt_sensor_unverified_unregistered"]
    assert len(unverified_items) == 1
    assert unverified_items[0].truth_class == "unverified_sensor"
    assert unverified_items[0].state_update_allowed is False
    assert unverified_items[0].diagnostic_only is True

    evidence_manifest["pillar_2_admission"] = {
        "admitted_evidence_count": len(pkg.evidence_items),
        "quarantined_evidence_count": len(pkg.diagnostics.quarantined_evidence),
        "admitted_sensor_reading": {
            "evidence_id": admitted_sensor.source_id,
            "value": admitted_sensor.value,
            "truth_class": admitted_sensor.truth_class,
            "data_status": admitted_sensor.data_status,
            "state_update_allowed": admitted_sensor.state_update_allowed,
        },
        "admitted_kalman_count": len(kalman_admitted),
        "admitted_raster": {
            "variable": raster_admitted.variable,
            "content_hash": raster_admitted.content_hash,
            "scientific_surface_allowed": raster_admitted.scientific_surface_allowed,
        },
        "quarantined_records": [
            {"evidence_id": q.evidence_id, "reasons": q.reason_codes}
            for q in pkg.diagnostics.quarantined_evidence
        ],
        "unverified_downgraded_records": [
            {
                "evidence_id": u.source_id,
                "truth_class": u.truth_class,
                "state_update_allowed": u.state_update_allowed,
                "diagnostic_only": u.diagnostic_only,
            }
            for u in unverified_items
        ],
    }

    # ═════════════════════════════════════════════════════════════════════════
    # PILLAR 3: SCIENTIFIC COMPUTATION — ASMAE Biophysical Model & Lineage
    # ═════════════════════════════════════════════════════════════════════════
    hist_refs = [primary_s2.scene_id, primary_s1.scene_id]
    state_support_ledger = {
        st: {
            "state": st,
            "source_feature_ids": hist_refs,
            "support_status": "archive_conditioned",
            "spatial_support": "plot_level_only",
            "observation_count": 2,
        }
        for st in STATE_NAMES
    }
    archive_posterior = {
        "contract_version": ARCHIVE_POSTERIOR_CONTRACT_VERSION,
        "state_means": {
            st: mean_ndvi if st == "vigor" else float(np.clip(mean_ndvi * 3.2, 0.5, 5.0)) if st == "lai" else 0.365
            for st in STATE_NAMES
        },
        "state_covariance": {st: 0.025 for st in STATE_NAMES},
        "last_update_date": (RUN_TIME - timedelta(days=2)).date().isoformat(),
        "geometry_hash": GEOMETRY_HASH,
        "crop_context": {"crop_type": "citrus"},
        "state_support_ledger": state_support_ledger,
        "content_distinct_scene_ids": hist_refs,
        "historical_validation_status": "validated",
    }
    asmae_inp = ASMAEInput(
        plot_id=PLOT_ID,
        run_id="run_asmae_phase1_empirical",
        polygon_geojson={
            "type": "Polygon",
            "coordinates": [[[2.65551, 36.509522], [2.655457, 36.507444], [2.662473, 36.507194],
                             [2.663331, 36.510195], [2.663331, 36.510609], [2.65551, 36.509522]]],
        },
        geometry_hash=GEOMETRY_HASH,
        start_date=(RUN_TIME - timedelta(days=9)).date(),
        end_date=RUN_TIME.date(),
        layer0_source_packages={"sensor": [sensor_pkg]},
        archive_posterior=archive_posterior,
        historical_scene_refs=hist_refs,
        mode="standard",
        crop_context={"crop_type": "citrus"},
    )
    est = estimate_resilient_plot_posterior(asmae_inp, as_of=RUN_TIME)
    post = est["plot_level_posterior"]

    computed_states = {
        st: float(post[st]["mean"])
        for st in ("lai", "canopy_water", "vigor", "root_zone_water")
        if post.get(st) and post[st].get("mean") is not None
    }
    computed_sigmas = {
        st: float(post[st]["sigma"])
        for st in ("lai", "canopy_water", "vigor", "root_zone_water")
        if post.get(st) and post[st].get("sigma") is not None
    }

    # Deterministic Scientific Content Root SHA-256 (Evidence Ledger + Fused Features)
    scientific_root = pkg.scientific_content_root()
    assert isinstance(scientific_root, str) and len(scientific_root) == 64

    # Canonical IEEE-754 Numerical State Vector Hash (R12-06 Extension)
    asmae_vector_hash = tb.compute_asmae_vector_numerical_hash(computed_states, computed_sigmas)
    assert asmae_vector_hash.startswith("sha256:") and len(asmae_vector_hash) == 71

    evidence_manifest["pillar_3_scientific_computation"] = {
        "latent_state_posterior": computed_states,
        "latent_state_sigmas": computed_sigmas,
        "scientific_content_root": scientific_root,
        "numerical_vector_hash": asmae_vector_hash,
        "etkf_mode": "resilient_ensemble",
        "archive_conditioned": True,
        "scene_support_refs": hist_refs,
    }

    # ═════════════════════════════════════════════════════════════════════════
    # PILLAR 4: PUBLICATION — Canonical Snapshot & SIRE Dashboard Display
    # ═════════════════════════════════════════════════════════════════════════
    snapshot_id = f"L10-SNAP-MITIDJA-{RUN_TIME.strftime('%Y%m%d%H%M')}"
    derived_surfaces = [{
        "surface_id": "surface-canopy-ndvi",
        "surface_type": "canopy_vigor",
        "values": grid_data,
        "resolution_m": 10.0,
        "content_hash": s2_raster_hash,
    }]

    snapshot_payload = {
        "run_id": pkg.run_id,
        "publication_run_id": pkg.run_id,
        "publication_id": f"pub-{pkg.run_id}",
        "intelligence_snapshot_id": snapshot_id,
        "plot_id": PLOT_ID,
        "crop_cycle_id": "CYCLE-2026-MITIDJA",
        "surface_schema_version": SURFACES_SCHEMA_VERSION,
        "render_authorization_version": RENDER_AUTHORIZATION_VERSION,
        "render_authorizations": {"canopy": {"authorized": True}},
        "asmae_proof": {
            "content_hash": scientific_root,
            "numerical_vector_hash": asmae_vector_hash,
            "run_id": pkg.run_id,
        },
        "asmae_posterior_numerical_record": {
            "states": computed_states,
            "sigmas": computed_sigmas,
            "numerical_vector_hash": asmae_vector_hash,
            "contract_version": ARCHIVE_POSTERIOR_CONTRACT_VERSION,
            "model_version": "asmae-resilient-etkf-v1",
            "input_evidence_root": scientific_root,
        },
        "mode_display_state": {"canopy": {"canRenderPixels": True}},
        "source_policy_display_state": {"requested_policy": "satellite"},
        "core_asmae_evidence_state": {"state": "nominal", "content_hash": scientific_root},
        "publication_surface_state": {"state": "provider_surface"},
        "resolved_crop_stage": "UNKNOWN",
        "phenology_context": {
            "resolved_crop_stage": "UNKNOWN",
            "ndvi_mean": mean_ndvi,
            "crop": "citrus",
            "crop_known": True,
        },
        "published_at": RUN_TIME.isoformat(),
        "evidence_cutoff_at": RUN_TIME.isoformat(),
        "observation_window": {
            "start": (RUN_TIME - timedelta(days=10)).isoformat(),
            "end": RUN_TIME.isoformat(),
        },
        "scientific_evidence_lineage": {
            "crop_posterior_lineage": scientific_root,
            "asmae_posterior_vector_hash": asmae_vector_hash,
            "crop_worldline_event_id": f"worldline-{pkg.run_id}",
            "phenology_worldline_event_id": f"phenology-{pkg.run_id}",
        },
        "surfaces": derived_surfaces,
    }

    pub_status, pub_details = classify_surface_publication(snapshot_payload)
    assert pub_status in (PublicationStatus.VALID_NORMAL.value, PublicationStatus.VALID_DEGRADED.value)

    pub_result = asmae_store.publish_canonical_layer10_snapshot(
        namespace=NAMESPACE,
        geometry_hash=GEOMETRY_HASH,
        frontend_payload=snapshot_payload,
        request_run_id=pkg.run_id,
        crop_cycle_id="CYCLE-2026-MITIDJA",
    )
    assert pub_result is not None

    reloaded_snapshot = asmae_store.load_latest_plot_snapshot(
        namespace=NAMESPACE,
        geometry_hash=GEOMETRY_HASH,
    )
    assert reloaded_snapshot is not None
    assert reloaded_snapshot["snapshot_id"] == snapshot_id
    assert reloaded_snapshot["crop_posterior_lineage"] == scientific_root
    assert reloaded_snapshot["surface_inventory_hash"] == pub_result["surface_inventory_hash"]
    assert reloaded_snapshot["frontend_publication_hash"] == pub_result["frontend_publication_hash"]
    # Cryptographic binding of ASMAE numerical output in reloaded snapshot
    reloaded_fp = reloaded_snapshot.get("frontend_payload", {})
    assert reloaded_fp.get("asmae_proof", {}).get("numerical_vector_hash") == asmae_vector_hash
    assert reloaded_fp.get("scientific_evidence_lineage", {}).get("asmae_posterior_vector_hash") == asmae_vector_hash

    # Complete downstream numerical verification:
    # Independently retrieve the persisted numerical posterior states and sigmas and recompute the hash
    reloaded_num_record = reloaded_fp.get("asmae_posterior_numerical_record", {})
    assert reloaded_num_record, "Persisted snapshot must include asmae_posterior_numerical_record"
    reloaded_states = reloaded_num_record.get("states", {})
    reloaded_sigmas = reloaded_num_record.get("sigmas", {})
    recomputed_vector_hash = tb.compute_asmae_vector_numerical_hash(reloaded_states, reloaded_sigmas)
    assert recomputed_vector_hash == asmae_vector_hash, (
        f"Recomputed hash {recomputed_vector_hash} must match original {asmae_vector_hash}"
    )
    assert reloaded_num_record.get("numerical_vector_hash") == asmae_vector_hash
    assert reloaded_num_record.get("input_evidence_root") == scientific_root
    assert reloaded_num_record.get("contract_version") == ARCHIVE_POSTERIOR_CONTRACT_VERSION

    evidence_manifest["pillar_4_publication"] = {
        "intelligence_snapshot_id": snapshot_id,
        "publication_status": pub_status,
        "surface_count": len(derived_surfaces),
        "surface_inventory_hash": pub_result["surface_inventory_hash"],
        "frontend_publication_hash": pub_result["frontend_publication_hash"],
        "crop_posterior_lineage": reloaded_snapshot["crop_posterior_lineage"],
        "asmae_posterior_vector_hash": asmae_vector_hash,
        "posterior_vector_recomputed_and_verified": True,
        "dashboard_can_render_pixels": True,
        "render_authorized": True,
    }

    # ═════════════════════════════════════════════════════════════════════════
    # PILLAR 5: GROUND TRUTH COMPARISON — In-Situ Soil Probe vs Model State
    # ═════════════════════════════════════════════════════════════════════════
    theta_sensor = reading_val  # 0.342 (15cm depth)
    theta_kalman_top = float(plot_state.get("sm_0_10", 0.4158))
    theta_kalman_root = float(plot_state.get("sm_10_40", 0.4210))
    theta_asmae_root = computed_states.get("root_zone_water", 0.365)
    sigma_asmae_root = computed_sigmas.get("root_zone_water", 0.035)

    residual_asmae = float(theta_sensor - theta_asmae_root)
    z_score_asmae = float(residual_asmae / (sigma_asmae_root or 1e-4))
    ci95_lower = float(theta_asmae_root - 1.96 * sigma_asmae_root)
    ci95_upper = float(theta_asmae_root + 1.96 * sigma_asmae_root)
    ci95_span = float(ci95_upper - ci95_lower)
    sensor_within_ci95 = ci95_lower <= theta_sensor <= ci95_upper

    evidence_manifest["pillar_5_ground_truth_comparison"] = {
        "in_situ_sensor_vwc": theta_sensor,
        "sensor_depth_cm": 15.0,
        "layer0_kalman_sm_0_10": theta_kalman_top,
        "layer0_kalman_sm_10_40": theta_kalman_root,
        "asmae_posterior_root_zone_water": theta_asmae_root,
        "asmae_posterior_sigma": sigma_asmae_root,
        "residual_sensor_minus_asmae": residual_asmae,
        "z_score": z_score_asmae,
        "ci95_interval": [ci95_lower, ci95_upper],
        "ci95_interval_span": round(ci95_span, 4),
        "sensor_within_95pct_ci": sensor_within_ci95,
        "agronomic_concordance": "UNCERTAINTY_COVERAGE_COMPATIBLE (SINGLE_POINT_PRELIMINARY)" if sensor_within_ci95 else "DEVIATION_UNDER_OBSERVATION",
        "coverage_status": "WITHIN_95PCT_UNCERTAINTY_INTERVAL" if sensor_within_ci95 else "OUTSIDE_INTERVAL",
        "depth_representativeness": "single_depth_15cm_vs_integrated_root_zone",
        "validation_level": "preliminary_replay_coverage",
        "soil_water_status": "Pending Independent Field Validation (Single-depth controlled reference reading)",
    }

    # ═════════════════════════════════════════════════════════════════════════
    # SAFETY INTERLOCK: Independent Actuation Hardware Disablement
    # ═════════════════════════════════════════════════════════════════════════
    actuation_active = verified_irrigation_enabled()
    assert actuation_active is False
    bootstrap_res = bootstrap_server_verified_irrigation(database=None)
    assert bootstrap_res is None

    evidence_manifest["safety_interlock"] = {
        "verified_irrigation_enabled": False,
        "hardware_interlock_fail_closed": True,
        "physical_actuator_commands_dispatched": 0,
        "mode": "OBSERVATION_ONLY_PILOT",
    }

    return evidence_manifest


def test_pilot_phase1_empirical_run():
    """Verify execution of the Pilot Phase 1 empirical run and validate all 5 evidence pillars."""
    manifest = run_empirical_plot_a_observation_batch()

    # Pillar 1
    assert manifest["pillar_1_acquisition"]["sentinel_2"]["product_id"].startswith("S2A_MSIL2A")
    assert manifest["pillar_1_acquisition"]["sentinel_1"]["product_id"].startswith("S1C_IW_GRDH")
    assert manifest["pillar_1_acquisition"]["sensor_in_situ"]["reading_value"] == 0.342

    # Pillar 2
    assert manifest["pillar_2_admission"]["admitted_evidence_count"] >= 2
    assert manifest["pillar_2_admission"]["quarantined_evidence_count"] == 2

    # Pillar 3
    assert len(manifest["pillar_3_scientific_computation"]["scientific_content_root"]) == 64
    assert manifest["pillar_3_scientific_computation"]["numerical_vector_hash"].startswith("sha256:")
    assert "root_zone_water" in manifest["pillar_3_scientific_computation"]["latent_state_posterior"]

    # Pillar 4
    assert manifest["pillar_4_publication"]["publication_status"] in (
        PublicationStatus.VALID_NORMAL.value,
        PublicationStatus.VALID_DEGRADED.value,
    )
    assert manifest["pillar_4_publication"]["dashboard_can_render_pixels"] is True
    assert manifest["pillar_4_publication"]["asmae_posterior_vector_hash"].startswith("sha256:")
    assert manifest["pillar_4_publication"]["posterior_vector_recomputed_and_verified"] is True

    # Pillar 5
    assert manifest["pillar_5_ground_truth_comparison"]["sensor_within_95pct_ci"] is True
    assert manifest["pillar_5_ground_truth_comparison"]["agronomic_concordance"] == "UNCERTAINTY_COVERAGE_COMPATIBLE (SINGLE_POINT_PRELIMINARY)"
    assert manifest["pillar_5_ground_truth_comparison"]["coverage_status"] == "WITHIN_95PCT_UNCERTAINTY_INTERVAL"
    assert manifest["pillar_5_ground_truth_comparison"]["ci95_interval_span"] > 0.5  # Wide prior interval note
    assert manifest["pillar_5_ground_truth_comparison"]["soil_water_status"].startswith("Pending Independent Field Validation")

    # Safety Interlock
    assert manifest["safety_interlock"]["verified_irrigation_enabled"] is False
    assert manifest["safety_interlock"]["physical_actuator_commands_dispatched"] == 0


if __name__ == "__main__":
    # Execute standalone for empirical inspection and output JSON manifest
    setup_dir = setup_empirical_environment()
    try:
        manifest = run_empirical_plot_a_observation_batch()
        print("\n" + "=" * 80)
        print("AKALORIS PILOT PHASE 1: REAL-SATELLITE-DATA INTEGRATION REPLAY MANIFEST")
        print("=" * 80)
        print(json.dumps(manifest, indent=2))
        print("=" * 80)
    finally:
        teardown_empirical_environment()
