"""Regression suite for ASMAE multi-crop canonical CLI, strict field validation, local spatial resolution, weather provenance & L2-8 stress ranking."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from services.agribrain.layer05_asmae.cross_layer_intelligence import CrossLayerSpecialistBridge
from services.agribrain.layer05_asmae.history.historical_event_memory import HistoricalEventMemory
from services.agribrain.layer05_asmae.history.historical_state_reconstructor import (
    HistoricalStateReconstructor,
    _SPATIALLY_SUPPORTED_STATES,
    apply_causal_channel_calibration,
    filter_causal_daily_weather_at_cutoff,
    update_channel_cal_entry,
)
from services.agribrain.layer05_asmae.history.independent_field_validation import (
    evaluate_independent_field_evidence,
)
from services.agribrain.layer05_asmae.history.weather_archive_adapter import (
    normalize_weather_archive,
)
from services.agribrain.scripts.run_archive_pilot import run_historical_intelligence_for_plot


def test_weather_archive_publication_lag_provenance_and_k_filtering():
    """ERA5 reanalysis carries source_role, lag metadata, and strict K availability filtering."""
    from services.agribrain.layer0.environment.weather.source_roles import role_for_data_kind

    role_val = role_for_data_kind("historical_reanalysis").value
    recs = [
        {
            "date": "2026-11-01",
            "temp_max": 24.0,
            "temp_min": 14.0,
            "precipitation": 2.0,
            "et0": 3.5,
            "provider": "era5-open-meteo",
            "source_role": role_val,
            "data_kind": "historical_reanalysis",
        },
        {
            "date": "2026-11-09",
            "temp_max": 22.0,
            "temp_min": 13.0,
            "precipitation": 0.0,
            "et0": 3.2,
            "provider": "era5-open-meteo",
            "source_role": role_val,
            "data_kind": "historical_reanalysis",
        },
    ]
    norm = normalize_weather_archive({"records": recs})
    ds = norm["weather_daily_series"]
    assert ds["2026-11-01"]["source_role"] == role_val
    assert ds["2026-11-01"]["reanalysis_lag_days"] == 5
    assert ds["2026-11-01"]["is_reanalysis_backfill"] is True
    assert ds["2026-11-01"]["available_at"].startswith("2026-11-06")
    assert ds["2026-11-09"]["available_at"].startswith("2026-11-14")
    assert norm["weather_provenance_summary"]["reanalysis_days"] == 2

    # At T=2026-11-12T12:00, K=2026-11-12T12:00 with lag enforced: Nov 9 (avail Nov 14) is withheld!
    cutoff = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
    stats: dict = {}
    filtered = filter_causal_daily_weather_at_cutoff(
        ds,
        cutoff,
        knowledge_cutoff_dt=cutoff,
        enforce_publication_lag=True,
        stats_out=stats,
    )
    assert "2026-11-01" in filtered
    assert "2026-11-09" not in filtered
    assert stats["excluded_reanalysis_lag_count"] == 1


def test_spread_calibration_arid_convergence_without_hard_floor():
    """Causal spread calibration scales smoothly down below 0.20 on low-variance streams without hindsight."""
    st = None
    dt0 = datetime(2025, 1, 1, 10, 30, tzinfo=timezone.utc)
    for i in range(18):
        cal = apply_causal_channel_calibration(
            st,
            obs_name="ndvi",
            raw_pred_mean=0.22,
            raw_pred_var=0.0001,
            obs_sigma=0.08,
            elapsed_days=5.0,
            now_dt=dt0 + timedelta(days=5 * i),
        )
        # Actual residuals tightly clustered around +/-0.012 while nominal obs_sigma=0.08
        obs_y = 0.22 + (0.012 if i % 2 == 0 else -0.012)
        st = update_channel_cal_entry(
            st,
            obs_val=obs_y,
            raw_pred=0.22,
            cal_pred=cal["cal_pred_mean"],
            unscaled_sig=cal["unscaled_sigma"],
            obs_name="ndvi",
            obs_dt=dt0 + timedelta(days=5 * i),
            post_raw_pred=0.22,
            var_scale_used=cal["var_scale_prior"],
        )
    cal_final = apply_causal_channel_calibration(
        st,
        obs_name="ndvi",
        raw_pred_mean=0.22,
        raw_pred_var=0.0001,
        obs_sigma=0.08,
        elapsed_days=5.0,
        now_dt=dt0 + timedelta(days=95),
    )
    assert 0.008 <= cal_final["var_scale_prior"] < 0.15
    assert cal_final["cal_sigma"] < 0.045  # Down sharply from nominal obs_sigma=0.08


def test_space_varying_local_resolution_and_variance_coarsening():
    """build_spatial_surfaces_payload emits genuine per-pixel varying resolution >=10m (1m held)."""
    H, W = 8, 8
    inside = np.ones((H, W), dtype=bool)
    inside[0, :] = False
    inside[-1, :] = False
    canonical_grid = {
        "crs": "EPSG:4326",
        "height": H,
        "width": W,
        "resolution_m": 10.0,
        "bounds": [2.65, 36.50, 2.66, 36.51],
        "inside_mask": inside,
    }
    n_s = len(_SPATIALLY_SUPPORTED_STATES)
    spatial_delta = np.zeros((n_s, H, W), dtype=np.float32)
    spatial_var = np.full((n_s, H, W), 0.0025, dtype=np.float32)
    # Elevate variance in east side to emulate spatial innovation dispersion
    spatial_var[:, :, 5:] = 0.0144
    spatial_obs_count = np.full((H, W), 12, dtype=np.int32)
    spatial_obs_count[:, 6:] = 3  # lower local obs density

    surfaces = HistoricalStateReconstructor.build_spatial_surfaces_payload(
        canonical_grid=canonical_grid,
        state_means={"vigor": 0.62, "root_zone_water": 0.24},
        state_stds={"vigor": 0.05, "root_zone_water": 0.04},
        accepted_counts={"vigor": 25, "root_zone_water": 25},
        spatial_delta=spatial_delta,
        spatial_var=spatial_var,
        has_spatial_observations=True,
        spatial_obs_count=spatial_obs_count,
    )
    vig = next(s for s in surfaces if s["surface_type"] == "ASMAE_VIGOR")
    loc_map = vig["local_resolution_map_m"]
    res_sum = vig["resolution_summary"]
    assert res_sum["is_spatially_varying"] is True
    assert res_sum["min_m"] >= 10.0
    assert res_sum["max_m"] > res_sum["min_m"]
    assert vig["certified_1m"] is False
    # Interior clear pixel (r=3, c=3) finer than corner low-obs high-disp pixel (r=1, c=7)
    assert loc_map[3][3] == 10.0
    assert loc_map[1][7] >= 30.0


def test_strict_independent_field_validation_causal_depth_spatial_cal_dedup():
    """Independent validation enforces causality, probe depth, polygon containment, calibration & daily device dedup."""
    poly = {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[2.650, 36.500], [2.660, 36.500], [2.660, 36.510], [2.650, 36.510], [2.650, 36.500]]],
        },
    }
    traj = [
        {
            "acquisition_time": "2026-05-05T10:30:00+00:00",
            "posterior_state_means": {"root_zone_water": 0.26, "vigor": 0.60, "stress_memory": 0.12},
            "posterior_state_stds": {"root_zone_water": 0.04},
        },
        {
            "acquisition_time": "2026-05-15T10:30:00+00:00",
            "posterior_state_means": {"root_zone_water": 0.30, "vigor": 0.64, "stress_memory": 0.10},
            "posterior_state_stds": {"root_zone_water": 0.04},
        },
    ]
    surfs = [
        {
            "surface_type": "ASMAE_ROOT_ZONE_WATER",
            "bounds": [2.650, 36.500, 2.660, 36.510],
            "effective_resolution_m": 40.0,
            "values": [[0.255, 0.255], [0.255, 0.255]],
            "uncertainty": [[0.035, 0.035], [0.035, 0.035]],
            "local_resolution_map_m": [[40.0, 50.0], [50.0, 40.0]],
        }
    ]
    readings = []
    # 50 rapid same-day bursts from calibrated 20cm probe inside polygon after 2026-05-05 scene
    for k in range(50):
        readings.append({
            "timestamp": f"2026-05-08T12:{k // 4:02d}:{(k % 4) * 15:02d}+00:00",
            "deviceId": "SENTEK-01",
            "vendor": "Sentek Drill & Drop",
            "isCalibrated": True,
            "calibrationCertificateId": "SENTEK-CERT-2026",
            "calibrationAuthority": "sentek_metrology_lab",
            "calibrationVerifiedAt": "2026-05-01T00:00:00+00:00",
            "soilMoisture": 0.25,
            "depth_cm": 20.0,
            "lat": 36.505,
            "lng": 2.655,
        })
    # Surface 0-5cm reading -> incompatible with root_zone_water
    readings.append({
        "timestamp": "2026-05-08T14:00:00+00:00",
        "deviceId": "SURF-01",
        "vendor": "Sentek Drill & Drop",
        "soilMoisture": 0.18,
        "depth_cm": 4.0,
    })
    # Outside polygon reading -> excluded
    readings.append({
        "timestamp": "2026-05-08T14:15:00+00:00",
        "deviceId": "OUTSIDE-01",
        "vendor": "Sentek Drill & Drop",
        "soilMoisture": 0.30,
        "depth_cm": 20.0,
        "lat": 36.600,
        "lng": 2.750,
    })
    # Pre-first-scene reading (May 2, when earliest scene is May 5) -> post-reading non-causal!
    readings.append({
        "timestamp": "2026-05-02T10:00:00+00:00",
        "deviceId": "SENTEK-01",
        "vendor": "Sentek Drill & Drop",
        "soilMoisture": 0.27,
        "depth_cm": 20.0,
    })
    # Uncalibrated supersaturated unspecified vendor reading on same window
    readings.append({
        "timestamp": "2026-05-09T10:00:00+00:00",
        "deviceId": "VS-UNSPEC",
        "vendor": "unspecified",
        "soilMoisture": 0.62,
        "depth_cm": 20.0,
    })

    res = evaluate_independent_field_evidence(
        plot_id="strict_val_plot",
        trajectory=traj,
        sensor_readings=readings,
        polygon_geojson=poly,
        spatial_surfaces=surfs,
        soil_context={"theta_sat": 0.44},
    )
    v = res["sensor_vwc_validation"]
    assert v["raw_readings_matched"] == 51
    assert v["n_independent_device_days"] == 2
    assert v["n_independent_devices"] == 2
    assert v["n_independent_days"] == 2
    assert v["excluded_surface_depth_count"] == 1
    assert v["excluded_out_of_plot_count"] == 1
    assert v["excluded_post_reading_non_causal"] == 1
    assert v["spatial_pixel_matched_count"] == 50
    assert v["calibrated_only_validation"]["n_independent_device_days"] == 1
    assert v["uncalibrated_reported_validation"]["n_independent_device_days"] == 1
    assert v["calibrated_only_validation"]["rmse_vwc"] == 0.005  # pixel 0.255 vs 0.250
    assert res["mesia_hydrological_validation"]["native_sigmf_captures_present"] is False


def test_cross_layer_ranked_mechanisms_and_confirmed_scouting_separation():
    """L2-8 competing attribution separates measured EC & verified scouting from satellite hypotheses."""
    bridge = CrossLayerSpecialistBridge()
    chrono = bridge.initialize_chrono_state(
        crop_context={"crop_type": "tomato"},
        soil_context={"soil_type": "clay", "ec_ds_m": 4.2},
    )
    t_now = datetime(2026, 6, 15, 10, 30, tzinfo=timezone.utc)
    weather = {
        (t_now - timedelta(days=d)).strftime("%Y-%m-%d"): {
            "temp_max": 36.0, "temp_min": 21.0, "precipitation": 0.0, "et0": 6.5, "humidity_mean_pct": 42.0,
        }
        for d in range(1, 5)
    }
    bridge.advance_chrono_state(chrono, start_time=t_now - timedelta(days=3), end_time=t_now, weather_daily_series=weather, crop_context={"crop_type": "tomato"}, soil_context={"soil_type": "clay", "ec_ds_m": 4.2})
    pre = bridge.evaluate_step_priors(state=chrono, timestamp=t_now, knowledge_cutoff=t_now, crop_context={"crop_type": "tomato"}, soil_context={"soil_type": "clay", "ec_ds_m": 4.2})
    ref = bridge.refine_after_asmae(
        pre_bundle=pre,
        posterior_means={"vigor": 0.36, "lai": 1.6, "canopy_water": 0.28, "root_zone_water": 0.14, "stress_memory": 0.45},
        posterior_stds={"vigor": 0.04, "root_zone_water": 0.03},
        crop_context={"crop_type": "tomato"},
    )
    ranked = ref["ranked_stress_mechanisms"]
    names = {r["mechanism"]: r for r in ranked}
    assert {"water_deficit", "heat_vpd", "nitrogen_limitation", "salinity_osmotic_ec", "phenological_stage_transition", "biotic_or_unobserved_management"} == set(names.keys())
    assert names["salinity_osmotic_ec"]["verification_status"] == "measured_soil_ec"
    assert names["salinity_osmotic_ec"]["confirmed_ground_truth"] is True
    assert names["water_deficit"]["confirmed_ground_truth"] is False

    # Verify verified scouting enters HistoricalEventMemory as agronomic_event_confirmed
    mem = HistoricalEventMemory().reconstruct_memory(
        trajectory=[
            {"acquisition_time": "2026-06-10T10:30:00+00:00", "posterior_state_means": {"vigor": 0.55, "lai": 2.4, "canopy_water": 0.35, "root_zone_water": 0.24, "stress_memory": 0.1}, "obs_channels": {"ndvi": 0.55}, "raw_metrics": {"ndvi_mean": 0.55}},
            {"acquisition_time": "2026-06-18T10:30:00+00:00", "posterior_state_means": {"vigor": 0.52, "lai": 2.3, "canopy_water": 0.33, "root_zone_water": 0.23, "stress_memory": 0.15}, "obs_channels": {"ndvi": 0.52}, "raw_metrics": {"ndvi_mean": 0.52}},
        ],
        context_summary={
            "daily_weather": weather,
            "management_events": [
                {"type": "scouting_pest", "date": "2026-06-14", "status": "OBSERVED_CONFIRMED", "title": "Aphid observation"}
            ],
        },
    )
    sc_ev = [e for e in mem["events"] if e["event_category"] == "field_scouting_confirmed"]
    assert len(sc_ev) == 1
    assert sc_ev[0]["epistemic_class"] == "agronomic_event_confirmed"


def test_canonical_cli_resolves_distinct_crop_and_soil_contexts_dynamically(tmp_path: Path):
    """Canonical run_archive_pilot CLI uses real domain SoilAnalysis/CropCycle rather than hardcoded citrus."""
    from services.agribrain.layer0.archive.raster_store import RasterStore

    plot_id = "69de624047f8c01c4979ffff"
    art_dir = tmp_path / "services" / "agribrain" / "artifacts"
    meta_dir = art_dir / "multiplot_meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    domain_doc = {
        "plot_doc": {
            "_id": plot_id,
            "tenantId": "tenant_clay_001",
            "farmId": "farm_mitidja_99",
            "name": "Clay Tomato Test",
            "geoJson": {
                "type": "Feature",
                "properties": {},
                "geometry": {"type": "Polygon", "coordinates": [[[2.65, 36.50], [2.66, 36.50], [2.66, 36.51], [2.65, 36.51], [2.65, 36.50]]]},
            },
        },
        "soil_analyses": [{"texture": "Clay", "ec": 2.1, "ph": 7.4}],
        "crop_cycles": [{"cropType": "Tomato", "variety": "Roma", "declaredCropAuthority": "FARMER_CONFIRMED", "declaredCropAt": "2025-04-20T00:00:00+00:00"}],
        "sensor_readings": [],
        "crop_observations": [],
        "crop_tasks": [
            {"type": "IRRIGATION", "dueDate": "2025-05-05", "completed": False, "title": "Planned only"},
            {"type": "IRRIGATION", "dueDate": "2025-05-02", "completed": True, "title": "Applied drip"},
        ],
    }
    (meta_dir / f"{plot_id}_domain.json").write_text(json.dumps(domain_doc), encoding="utf-8")

    # Save minimal offline weather cache + 2 real-format .SAFE scenes
    weather_cache = {
        "weather_meta": {"status": "available", "source_reality": "reanalysis_archive"},
        "daily_weather": {
            (datetime(2025, 4, 15, tzinfo=timezone.utc).date() + timedelta(days=k)).isoformat(): {
                "temp_max": 24.0, "temp_min": 13.0, "precipitation": 0.0, "et0": 4.1,
            }
            for k in range(30)
        },
    }
    (meta_dir / f"{plot_id}_weather.json").write_text(json.dumps(weather_cache), encoding="utf-8")

    rs = RasterStore()
    scene_root = Path("services/agribrain/artifacts/real_scenes") / plot_id
    try:
        scene_root.mkdir(parents=True, exist_ok=True)
        for day_s, ndvi_v in [("2025-05-01T10:30:00+00:00", 0.42), ("2025-05-10T10:30:00+00:00", 0.56)]:
            sd = scene_root / f"S2A_{day_s[:10].replace('-', '')}"
            sd.mkdir(parents=True, exist_ok=True)
            b04 = np.full((6, 6), 0.08, dtype=np.float32)
            b08 = np.full((6, 6), 0.08 * (1.0 + ndvi_v) / (1.0 - ndvi_v), dtype=np.float32)
            b11 = np.full((6, 6), 0.14, dtype=np.float32)
            scl = np.full((6, 6), 4, dtype=np.int16)
            rs.save_band(str(sd / "B04.npz"), b04)
            rs.save_band(str(sd / "B08.npz"), b08)
            rs.save_band(str(sd / "B11.npz"), b11)
            rs.save_band(str(sd / "SCL.npz"), scl)
            (sd / "metadata.json").write_text(json.dumps({
                "scene_id": sd.name,
                "sensor": "sentinel2",
                "acquisition_datetime": day_s,
                "crs": "EPSG:4326",
                "transform": [2.65, 0.01 / 6, 0.0, 36.51, 0.0, -0.01 / 6],
                "width": 6,
                "height": 6,
            }), encoding="utf-8")

        res = run_historical_intelligence_for_plot(
            plot_id,
            workspace_root=str(tmp_path),
            offline=True,
            skip_bootstrap=False,
            local_scene_cache=True,
        )
        assert res["tenant_id"] == "tenant_clay_001"
        assert res["farm_id"] == "farm_mitidja_99"
        assert res["crop_context"]["crop_type"] == "tomato"
        assert res["soil_context"]["texture"] == "CLAY"
        assert res["domain_metadata_source"] == "local_domain_metadata_cache"
        summary_file = (
            art_dir / "archive_pilot_reports" / "tenant_clay_001" / "farm_mitidja_99" / plot_id
            / "historical_state_intelligence_summary.json"
        )
        assert summary_file.is_file()
        assert res["independent_field_validation"]["crop_tasks_summary"]["applied_or_completed_count"] == 1
        assert res["independent_field_validation"]["crop_tasks_summary"]["unconfirmed_planned_ignored_count"] == 1
    finally:
        import shutil
        shutil.rmtree(scene_root, ignore_errors=True)
