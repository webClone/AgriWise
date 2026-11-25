"""Regression suite for ASMAE Gap A (full-engine publication + terminal guard) & Gap B (historical bootstrap + continuity)."""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pytest

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.geometry_contract import compute_geometry_hash
from services.agribrain.layer0.asmae_scene_products.scene_product_schema import SceneProduct
from services.agribrain.layer05_asmae import plot_snapshot_store, snapshot_store
from services.agribrain.layer05_asmae.history.archive_bootstrap_service import ArchiveBootstrapService
from services.agribrain.layer10_sire.surface_contract import (
    RENDER_AUTHORIZATION_VERSION,
    SURFACES_SCHEMA_VERSION,
)
from services.agribrain.layer1_fusion.truth_bridge import compute_asmae_vector_numerical_hash
from services.agribrain.scripts import run_afroun_diagnostic_publication as pub_script
from services.agribrain.scripts import run_archive_pilot as pilot_script
from services.agribrain.world_model.canonical_worldline import CanonicalWorldlineService


@pytest.fixture
def isolated_stores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(plot_snapshot_store, "PLOT_SNAPSHOT_ROOT", tmp_path / "plot_snapshots")
    monkeypatch.setattr(snapshot_store, "SNAPSHOT_DIR", tmp_path / "asmae_snapshots")
    monkeypatch.setattr(snapshot_store, "SNAPSHOT_NODE_DIR", tmp_path / "asmae_snapshots" / "nodes")
    with plot_snapshot_store._SNAPSHOT_CACHE_LOCK:
        plot_snapshot_store._CANONICAL_SNAPSHOT_CACHE.clear()
    yield tmp_path
    with plot_snapshot_store._SNAPSHOT_CACHE_LOCK:
        plot_snapshot_store._CANONICAL_SNAPSHOT_CACHE.clear()


def _make_diagnostic_fe_payload(snapshot_id: str, plot_id: str, cutoff: str | None) -> Dict[str, Any]:
    return {
        "version": SURFACES_SCHEMA_VERSION,
        "surface_schema_version": SURFACES_SCHEMA_VERSION,
        "intelligence_snapshot_id": snapshot_id,
        "plot_id": plot_id,
        "publication_id": f"pub-{snapshot_id}",
        "publication_run_id": f"run-{snapshot_id}",
        "run_id": f"run-{snapshot_id}",
        "pipeline_state": "terminal_layer10_published",
        "publication_status": "VALID_NORMAL",
        "render_authorization_version": RENDER_AUTHORIZATION_VERSION,
        "render_authorizations": {"canopy": {"authorized": True}},
        "claims_numerical_authority": False,
        "publication_authority": "DIAGNOSTIC_ONLY",
        "asmae_proof": {
            "proof_id": f"proof-{snapshot_id}",
            "status": "valid",
            "publication_authority": "DIAGNOSTIC_ONLY",
        },
        "scientific_evidence_lineage": {
            "crop_posterior_lineage": "crop-lineage-1",
            "crop_worldline_event_id": "crop-evt-1",
            "phenology_worldline_event_id": "pheno-evt-1",
        },
        "mode_display_state": {"canopy": {"canRenderPixels": True}},
        "source_policy_display_state": {"requested_policy": "satellite"},
        "core_asmae_evidence_state": {"state": "nominal", "content_hash": "dummy_content_hash"},
        "publication_surface_state": {"state": "provider_surface"},
        "evidence_cutoff_at": cutoff,
        "observation_window": {"start": "2026-08-30", "end": "2026-09-08"},
        "published_at": "2026-09-08T12:00:00+00:00",
        "crop_cycle_id": "cycle-a",
        "surfaces": [
            {
                "surface_id": f"surf_ndvi_{snapshot_id}",
                "surface_type": "NDVI_CLEAN",
                "type": "NDVI_CLEAN",
                "semantic_type": "NDVI_CLEAN",
                "values": [[0.62, 0.64], [0.61, 0.65]],
                "grounding_class": "RASTER_GROUNDED",
                "grid_spec": {"height": 2, "width": 2, "crs": "EPSG:4326"},
                "resolution_m": 10.0,
                "content_hash": "dummy_hash_diag",
                "provenance": {"has_spatial_grid": True},
            }
        ],
        "surface_inventory": {
            "NDVI_CLEAN": {"status": "available", "available": True, "spatial": True}
        },
        "raster_availability": {"can_render_pixels": True, "supported_layers": ["NDVI_CLEAN"]},
    }


def test_cross_geometry_terminal_snapshot_guard_preserves_admitted_asmae(isolated_stores: Path):
    """Degraded L10 terminal runs lacking evidence_cutoff_at never overwrite admitted ASMAE snapshots."""
    plot_id = pub_script.PLOT_ID
    ns = PlotNamespace(tenant_id=pub_script.TENANT_ID, farm_id=pub_script.FARM_ID, plot_id=plot_id)
    asmae_res = {
        "plot_id": plot_id,
        "content_hash": "hash-admitted-1",
        "crop_posterior_lineage": "crop-lineage-1",
        "crop_worldline_event_id": "crop-evt-1",
        "phenology_worldline_event_id": "pheno-evt-1",
        "crop_influence_manifest_hash": "manifest-1",
        "crop_evidence_ledger_hash": "ledger-1",
        "plot_state_artifact": {"as_of": "2026-09-06T17:44:33+00:00", "authority_level": "DIAGNOSTIC_NO_STATE_UPDATE"},
        "claims_numerical_authority": False,
        "publication_authority": "DIAGNOSTIC_ONLY",
        "evidence_cutoff_at": "2026-09-06T17:44:33+00:00",
        "raster_maps": {},
    }
    ref = snapshot_store.publish_latest_snapshot(asmae_res, context_hash="ctx-1", geometry_hash=pub_script.GEOMETRY_HASH)
    asmae_res["snapshot_ref"] = ref
    snap_id = asmae_res["snapshot_id"]

    fe_admitted = _make_diagnostic_fe_payload(snap_id, plot_id, cutoff="2026-09-06T17:44:33+00:00")
    head = plot_snapshot_store.publish_canonical_plot_snapshot(
        namespace=ns,
        geometry_hash=pub_script.GEOMETRY_HASH,
        snapshot_id=snap_id,
        asmae_result=asmae_res,
        frontend_payload=fe_admitted,
        job_id="job-admitted-1",
        manifest_hash="manifest-1",
        execution_identity={"crop_cycle_id": "cycle-a"},
        snapshot_kind="asmae",
        publication_authority="DIAGNOSTIC_ONLY",
    )
    assert head["snapshot_id"] == snap_id

    # Now attempt a degraded terminal L10 snapshot with no evidence_cutoff_at
    fe_terminal = _make_diagnostic_fe_payload("L10-SNAP-DEGRADED-1", plot_id, cutoff=None)
    states, sigmas = {}, {}
    num_hash = compute_asmae_vector_numerical_hash(states, sigmas)
    fe_terminal["asmae_posterior_numerical_record"] = {
        "states": states,
        "sigmas": sigmas,
        "numerical_vector_hash": num_hash,
    }
    res_term = plot_snapshot_store.publish_canonical_layer10_snapshot(
        namespace=ns,
        geometry_hash=pub_script.GEOMETRY_HASH,
        frontend_payload=fe_terminal,
        request_run_id="req-term-1",
        crop_cycle_id="cycle-a",
    )
    latest = plot_snapshot_store.load_latest_plot_snapshot(ns, force_verify=True)
    assert latest is not None
    assert latest["snapshot_id"] == snap_id
    assert latest["evidence_cutoff_at"] == "2026-09-06T17:44:33+00:00"
    assert res_term["snapshot_id"] == snap_id


def test_publication_coincidence_withheld_and_authorizations():
    """Verify spatial coincidence validation, withheld state stripping, NaN cleanup, and render_authorizations."""
    base_transform = (2.655457, 0.0001, 0.0, 36.510609, 0.0, -0.0001)
    s2 = SceneProduct(
        scene_id="s2_a", sensor="S2", acquisition_datetime=datetime(2026, 9, 5, tzinfo=timezone.utc),
        crs="EPSG:4326", transform=base_transform, width=10, height=8,
        band_refs={}, mask_refs={}, band_units={}, quality={}, source_reality="real_raster",
    )
    s1 = SceneProduct(
        scene_id="s1_a", sensor="S1", acquisition_datetime=datetime(2026, 9, 6, tzinfo=timezone.utc),
        crs="EPSG:4326", transform=base_transform, width=10, height=8,
        band_refs={}, mask_refs={}, band_units={}, quality={}, source_reality="real_raster",
    )
    proof = pub_script.verify_scene_grid_coincidence([s2], [s1])
    assert proof["coincident"] is True
    assert proof["height"] == 8 and proof["width"] == 10

    s1_bad = SceneProduct(
        scene_id="s1_bad", sensor="S1", acquisition_datetime=datetime(2026, 9, 6, tzinfo=timezone.utc),
        crs="EPSG:4326", transform=base_transform, width=11, height=8,
        band_refs={}, mask_refs={}, band_units={}, quality={}, source_reality="real_raster",
    )
    with pytest.raises(ValueError, match="shape mismatch"):
        pub_script.verify_scene_grid_coincidence([s2], [s1_bad])

    fake_asmae = {
        "plot_id": pub_script.PLOT_ID,
        "status": "success",
        "uncertainty_maps": {"vigor": [[0.1, 0.1]], "thermal_stress": [[0.2, 0.2]]},
        "raster_maps": {
            "vigor": [[0.7, 0.72]],
            "thermal_stress": [[0.5, 0.52]],
            "stress_memory": [[0.4, 0.41]],
            "salinity_stress": [[0.1, 0.12]],
            "biotic_confounder_risk": [[0.2, 0.22]],
        },
        "asmae_evidence_state": {
            "supported_states": ["vigor", "thermal_stress"],
            "allowed_outputs": ["vigor"],
        },
        "diagnostics": {
            "state_support_ledger": {
                "vigor": {"accepted_update_count": 8, "support_status": "temporally_conditioned"},
                "thermal_stress": {"accepted_update_count": 4, "support_status": "temporally_conditioned"},
                "stress_memory": {"accepted_update_count": 0, "support_status": "prior_constrained"},
                "salinity_stress": {"accepted_update_count": 0, "support_status": "unsupported"},
                "biotic_confounder_risk": {"accepted_update_count": 0, "support_status": "unsupported"},
            },
        },
    }
    filtered, withheld = pub_script.build_l10_filtered_asmae_payload(fake_asmae)
    assert "vigor" in filtered["raster_maps"]
    ledger_out = filtered["diagnostics"]["state_support_ledger"]
    for dropped in ("thermal_stress", "stress_memory", "salinity_stress", "biotic_confounder_risk"):
        assert dropped not in filtered["raster_maps"]
        assert ledger_out[dropped]["spatial_support"] == "unavailable"
        assert ledger_out[dropped]["field_approval_eligible"] is False
    assert {w["surface_type"] for w in withheld} >= {
        "ASMAE_THERMAL_STRESS",
        "ASMAE_STRESS_MEMORY",
        "ASMAE_SALINITY_STRESS",
        "ASMAE_BIOTIC_CONFOUNDER_RISK",
    }

    existing_entry = {
        "surfaceType": "CANOPY_ASMAE_VIGOR",
        "authorized": True,
        "renderKind": "full_raster",
        "reason": "asmae_proof_valid_authorized",
    }
    auth = {"asmae_diagnostic": {"canopy": {"base": {"CANOPY_ASMAE_VIGOR": dict(existing_entry)}}}}
    pub_script._authorize_surface_in_matrix(
        auth, "CANOPY_ASMAE_VIGOR", ["canopy"], allowed=True, preserve_existing=True
    )
    assert auth["asmae_diagnostic"]["canopy"]["base"]["CANOPY_ASMAE_VIGOR"] == existing_entry
    pub_script._authorize_surface_in_matrix(
        auth, "WATER_STRESS_PROB", ["water"], allowed=True, reason="sar_proxy", preserve_existing=False
    )
    assert auth["asmae_diagnostic"]["water"]["base"]["WATER_STRESS_PROB"]["authorized"] is True
    assert auth["asmae_diagnostic"]["water"]["base"]["WATER_STRESS_PROB"]["renderKind"] == "full_raster"
    assert pub_script._to_masked_grid_list(
        np.array([[0.5, float("nan"), float("inf"), 0.8]]),
        np.array([[True, True, True, False]]),
    ) == [[0.5, None, None, None]]


def test_archive_bootstrap_forwards_geometry_and_classifies_unavailable_statuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """ArchiveBootstrapService forwards real geometry and distinguishes NO_DATA, REJECTED, and ACQUISITION_ERROR."""
    wl = CanonicalWorldlineService(root=tmp_path / "wl", durable_anchor_root=tmp_path / "anc", require_durable_anchor=False)
    svc = ArchiveBootstrapService(worldline=wl, bootstrap_root=tmp_path / "cp")
    seen_calls: List[Dict[str, Any]] = []

    def _s2_no_data(plot_id, run_id, date_range, rc, lat=None, lng=None, polygon_coords=None):
        seen_calls.append({"sensor": "s2", "run_id": run_id, "lat": lat, "lng": lng, "coords": polygon_coords})
        return {"status": "unavailable", "stage": "catalog_query", "reason": "no_scene_found", "date_range": date_range}

    def _s1_no_data(plot_id, run_id, date_range, rc, lat=None, lng=None, polygon_coords=None):
        seen_calls.append({"sensor": "s1", "run_id": run_id, "lat": lat, "lng": lng, "coords": polygon_coords})
        return {"status": "unavailable", "stage": "catalog_query", "reason": "no_scene_found", "date_range": date_range}

    monkeypatch.setattr("services.agribrain.layer0.providers.asmae_scene_fetcher.fetch_asmae_s2_scene_stack", _s2_no_data)
    monkeypatch.setattr("services.agribrain.layer0.providers.asmae_scene_fetcher.fetch_asmae_s1_scene_stack", _s1_no_data)

    res_gap = svc.run_bootstrap(
        plot_id=pub_script.PLOT_ID,
        geometry_hash=pub_script.GEOMETRY_HASH,
        tenant_id=pub_script.TENANT_ID,
        namespace=pub_script.FARM_ID,
        start_date="2015-07-01T00:00:00+00:00",
        target_end_date="2015-08-01T00:00:00+00:00",
        window_days=60,
        polygon_geojson=pub_script.PLOT_GEOJSON,
    )
    assert res_gap["status"] == "COMPLETED"
    assert res_gap["checkpoint"]["completed_windows"][0]["window_status"] == "NO_DATA"
    assert len(seen_calls) == 2
    for c in seen_calls:
        assert c["coords"] == pub_script.PLOT_COORDINATES
        assert c["lat"] == pytest.approx(36.508951, abs=1e-3)
        assert c["lng"] == pytest.approx(2.659858, abs=1e-3)
        assert "2015-07-01_2015-08-01" in c["run_id"]

    # Cloud rejection -> REJECTED gap
    monkeypatch.setattr(
        "services.agribrain.layer0.providers.asmae_scene_fetcher.fetch_asmae_s2_scene_stack",
        lambda *a, **kw: {"status": "unavailable", "stage": "scene_validation", "reason": "cloud_filter_rejected"},
    )
    res_rej = ArchiveBootstrapService(worldline=wl, bootstrap_root=tmp_path / "cp_rej").run_bootstrap(
        plot_id=pub_script.PLOT_ID,
        geometry_hash=pub_script.GEOMETRY_HASH,
        start_date="2020-01-01T00:00:00+00:00",
        target_end_date="2020-02-01T00:00:00+00:00",
        polygon_geojson=pub_script.PLOT_GEOJSON,
    )
    assert res_rej["checkpoint"]["completed_windows"][0]["window_status"] == "REJECTED"

    # Auth / network / rate limit failure -> raises ACQUISITION_ERROR and sets checkpoint FAILED (no false gap)
    err_cp_root = tmp_path / "cp_err"
    monkeypatch.setattr(
        "services.agribrain.layer0.providers.asmae_scene_fetcher.fetch_asmae_s2_scene_stack",
        lambda *a, **kw: {"status": "unavailable", "stage": "authentication", "reason": "credentials_missing"},
    )
    err_svc = ArchiveBootstrapService(worldline=wl, bootstrap_root=err_cp_root)
    with pytest.raises(RuntimeError, match="ACQUISITION_ERROR:sentinel2:credentials_missing"):
        err_svc.run_bootstrap(
            plot_id=pub_script.PLOT_ID,
            geometry_hash=pub_script.GEOMETRY_HASH,
            start_date="2026-01-01T00:00:00+00:00",
            target_end_date="2026-02-01T00:00:00+00:00",
            polygon_geojson=pub_script.PLOT_GEOJSON,
        )
    cp_err = err_svc.load_checkpoint(pub_script.PLOT_ID)
    assert cp_err is not None
    assert cp_err.status == "FAILED"
    assert cp_err.total_gaps_recorded == 0


def test_archive_bootstrap_real_band_metrics_and_incremental_continuity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Real band NDVI/VV extraction with GDAL polygon masking + incremental checkpoint resume without rebuild."""
    # Grid covering PLOT_GEOJSON bbox [2.655457..2.663331, 36.507194..36.510609]
    H, W = 12, 16
    minx, maxy = 2.6550, 36.5110
    dx, dy = (2.6640 - minx) / W, -(maxy - 36.5065) / H
    transform = (minx, dx, 0.0, maxy, 0.0, dy)

    b04 = np.full((H, W), 0.10, dtype=np.float32)
    b08 = np.full((H, W), 0.50, dtype=np.float32)  # (0.5 - 0.1) / (0.5 + 0.1) = 0.666667
    scl = np.full((H, W), 4.0, dtype=np.float32)    # vegetation
    scl[0, :] = 9.0  # cloud strip outside/edge

    vv_lin = np.full((H, W), 0.12, dtype=np.float32)  # 10*log10(0.12) ~= -9.208188 dB
    vh_lin = np.full((H, W), 0.02, dtype=np.float32)  # 10*log10(0.02) ~= -16.9897 dB

    bands_dir = tmp_path / "bands"
    bands_dir.mkdir(parents=True)
    np.savez_compressed(bands_dir / "b04.npz", b04)
    np.savez_compressed(bands_dir / "b08.npz", b08)
    np.savez_compressed(bands_dir / "scl.npz", scl)
    np.savez_compressed(bands_dir / "vv.npz", vv_lin)
    np.savez_compressed(bands_dir / "vh.npz", vh_lin)

    window_queries: List[tuple[str, str, tuple]] = []

    def _s2_for_window(plot_id, run_id, date_range, rc, **kw):
        window_queries.append(("s2", run_id, date_range))
        day = date_range[0]
        return [
            SceneProduct(
                scene_id=f"s2_{day}", sensor="S2",
                acquisition_datetime=datetime.fromisoformat(f"{day}T10:30:00+00:00"),
                crs="EPSG:4326", transform=transform, width=W, height=H,
                band_refs={"B04": str(bands_dir / "b04.npz"), "B08": str(bands_dir / "b08.npz"), "SCL": str(bands_dir / "scl.npz")},
                mask_refs={}, band_units={}, quality={"cloud_fraction": 0.1}, source_reality="real_raster",
            )
        ]

    def _s1_for_window(plot_id, run_id, date_range, rc, **kw):
        window_queries.append(("s1", run_id, date_range))
        day = date_range[0]
        return [
            SceneProduct(
                scene_id=f"s1_{day}", sensor="S1",
                acquisition_datetime=datetime.fromisoformat(f"{day}T17:45:00+00:00"),
                crs="EPSG:4326", transform=transform, width=W, height=H,
                band_refs={"VV": str(bands_dir / "vv.npz"), "VH": str(bands_dir / "vh.npz")},
                mask_refs={}, band_units={"VV": "linear_power", "VH": "linear_power"}, quality={}, source_reality="real_raster",
            )
        ]

    monkeypatch.setattr("services.agribrain.layer0.providers.asmae_scene_fetcher.fetch_asmae_s2_scene_stack", _s2_for_window)
    monkeypatch.setattr("services.agribrain.layer0.providers.asmae_scene_fetcher.fetch_asmae_s1_scene_stack", _s1_for_window)

    wl_inc = CanonicalWorldlineService(root=tmp_path / "wl_inc", durable_anchor_root=tmp_path / "anc_inc", require_durable_anchor=False)
    svc_inc = ArchiveBootstrapService(worldline=wl_inc, bootstrap_root=tmp_path / "cp_inc")

    r1 = svc_inc.run_bootstrap(
        plot_id=pub_script.PLOT_ID, geometry_hash=pub_script.GEOMETRY_HASH,
        start_date="2026-05-05T00:00:00+00:00", target_end_date="2026-09-02T00:00:00+00:00",
        window_days=120, polygon_geojson=pub_script.PLOT_GEOJSON,
    )
    assert r1["total_events_committed"] == 2
    assert len(window_queries) == 2

    # Re-compress .npz files to change ZIP timestamps while keeping identical pixel arrays
    np.savez_compressed(bands_dir / "vv.npz", vv_lin)
    window_queries.clear()

    r2 = svc_inc.run_bootstrap(
        plot_id=pub_script.PLOT_ID, geometry_hash=pub_script.GEOMETRY_HASH,
        start_date="2026-05-05T00:00:00+00:00", target_end_date="2026-11-25T00:00:00+00:00",
        window_days=120, polygon_geojson=pub_script.PLOT_GEOJSON,
    )
    assert r2["resumed"] is True
    assert r2["completed_windows_count"] == 2
    # Must query ONLY the new extension window [2026-09-02, 2026-11-25], never re-running [2026-05-05, 2026-09-02]
    assert {q[2] for q in window_queries} == {("2026-09-02", "2026-11-25")}

    events_inc = wl_inc.load_all_events(pub_script.PLOT_ID)
    assert len(events_inc) == 4
    assert all(ev["event_type"] == "OBSERVATION_QUALIFIED" for ev in events_inc)
    s2_ap = events_inc[0]["payload"]["observation_qualified"]
    s1_ap = events_inc[1]["payload"]["observation_qualified"]
    assert s2_ap["assimilated"] is False
    assert s2_ap["metrics"]["ndvi_mean"] == pytest.approx(0.666667, abs=1e-4)
    assert not str(s2_ap["source_content_hash"]).startswith("hash_")
    assert len(s2_ap["source_content_hash"]) == 64
    assert s1_ap["metrics"]["vv_mean_db"] == pytest.approx(-9.208188, abs=1e-3)
    assert s1_ap["metrics"]["vh_mean_db"] == pytest.approx(-16.9897, abs=1e-3)
    assert s1_ap["calibration_status"] == "uncalibrated_proxy"

    # Compare incremental result against fresh cold multi-window run
    wl_cold = CanonicalWorldlineService(root=tmp_path / "wl_cold", durable_anchor_root=tmp_path / "anc_cold", require_durable_anchor=False)
    svc_cold = ArchiveBootstrapService(worldline=wl_cold, bootstrap_root=tmp_path / "cp_cold")
    svc_cold.run_bootstrap(
        plot_id=pub_script.PLOT_ID, geometry_hash=pub_script.GEOMETRY_HASH,
        start_date="2026-05-05T00:00:00+00:00", target_end_date="2026-11-25T00:00:00+00:00",
        window_days=120, polygon_geojson=pub_script.PLOT_GEOJSON,
    )
    events_cold = wl_cold.load_all_events(pub_script.PLOT_ID)
    assert [
        (e["payload"]["observation_qualified"]["scene_id"], e["payload"]["observation_qualified"]["source_content_hash"], e["payload"]["observation_qualified"]["metrics"])
        for e in events_inc
    ] == [
        (e["payload"]["observation_qualified"]["scene_id"], e["payload"]["observation_qualified"]["source_content_hash"], e["payload"]["observation_qualified"]["metrics"])
        for e in events_cold
    ]


def test_run_archive_pilot_canonical_geometry_and_real_weather(monkeypatch: pytest.MonkeyPatch):
    """Archive pilot uses canonical 6-vertex afroun GeoJSON hash and real weather adapter (no hardcoded 25C/15C)."""
    geom_wkt = pilot_script.COHORT_GEOMETRIES[pub_script.PLOT_ID]
    geojson, lat, lng = pilot_script._wkt_to_geojson_and_centroid(geom_wkt)
    assert compute_geometry_hash(geojson) == pub_script.GEOMETRY_HASH
    assert len(geojson["geometry"]["coordinates"][0]) == 6

    empty_w, meta_off = pilot_script._fetch_real_daily_weather(
        lat, lng, datetime(2026, 8, 30, tzinfo=timezone.utc), datetime(2026, 9, 2, tzinfo=timezone.utc), offline=True
    )
    assert empty_w == {} and meta_off["status"] == "unavailable"

    monkeypatch.setattr(
        pilot_script,
        "fetch_historical_weather",
        lambda *_a, **_kw: {
            "source": "era5-open-meteo",
            "records": [
                {"date": "2026-08-30", "temp_min": 21.0, "temp_max": 33.5, "temp_mean": 27.2, "precipitation": 0.0, "et0": 4.9, "wind_max": 12.0},
            ],
        },
    )
    daily_w, meta_on = pilot_script._fetch_real_daily_weather(
        lat, lng, datetime(2026, 8, 30, tzinfo=timezone.utc), datetime(2026, 8, 30, tzinfo=timezone.utc), offline=False
    )
    assert meta_on["status"] == "available"
    assert daily_w["2026-08-30"]["temp_max"] == 33.5
    assert daily_w["2026-08-30"]["et0"] == 4.9
