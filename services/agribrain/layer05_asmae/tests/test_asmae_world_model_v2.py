"""Comprehensive acceptance test suite for ASMAE World Model V2 (WM1-P1-01..07 & WM1-P2-08..12)."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from services.agribrain.layer05_asmae.config import STATE_NAMES
from services.agribrain.layer05_asmae.history.archive_bootstrap_service import ArchiveBootstrapService
from services.agribrain.layer05_asmae.history.benchmark_matrix import evaluate_cross_plot_matrix
from services.agribrain.layer05_asmae.history.domain_chronology import build_domain_chronology
from services.agribrain.layer05_asmae.history.historical_crop_fusion import (
    evaluate_crop_detection_benchmark,
    reconstruct_chronological_crop_posteriors,
)
from services.agribrain.layer05_asmae.history.historical_retrovalidation import HistoricalRetrovalidator
from services.agribrain.layer05_asmae.history.historical_state_reconstructor import HistoricalStateReconstructor
from services.agribrain.layer2_veg_int.features.calibration_registry import TrustedCalibrationArtifactStore
from services.agribrain.world_model.canonical_worldline import CanonicalWorldlineService


def _weather_series(start_yr: int, end_yr: int, *, rain_offset: float = 0.0) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    cur = datetime(start_yr, 1, 1, tzinfo=timezone.utc).date()
    end = datetime(end_yr, 12, 31, tzinfo=timezone.utc).date()
    while cur <= end:
        doy = cur.timetuple().tm_yday
        precip = (18.0 + rain_offset) if doy in (65, 130, 290) else 0.0
        out[cur.isoformat()] = {
            "temp_max": 28.0 if 150 <= doy <= 240 else 18.0,
            "temp_min": 15.0 if 150 <= doy <= 240 else 8.0,
            "precipitation": precip,
            "et0": 4.8 if 150 <= doy <= 240 else 2.0,
            "ingested_at": f"{cur.isoformat()}T06:00:00+00:00",
        }
        cur += timedelta(days=1)
    return out


def _rotation_scenes(years: List[int]) -> List[Dict[str, Any]]:
    scenes: List[Dict[str, Any]] = []
    for yr in years:
        for doy, src, metrics in [
            (35, "sentinel2", {"ndvi_mean": 0.28, "ndmi_mean": 0.06}),
            (85, "sentinel2", {"ndvi_mean": 0.54, "ndmi_mean": 0.16}),
            (92, "sentinel1", {"vv_mean_db": -11.2, "vh_mean_db": -18.0}),
            (140, "sentinel2", {"ndvi_mean": 0.72, "ndmi_mean": 0.24}),
            (195, "sentinel2", {"ndvi_mean": 0.50, "ndmi_mean": 0.11}),
            (235, "sentinel1", {"vv_mean_db": -12.6, "vh_mean_db": -19.2}),
            (280, "sentinel2", {"ndvi_mean": 0.36, "ndmi_mean": 0.10}),
        ]:
            dt = datetime(yr, 1, 1, 10, 30, tzinfo=timezone.utc) + timedelta(days=doy - 1)
            scenes.append({
                "scene_id": f"{src[:2].upper()}_{dt.strftime('%Y%m%d')}",
                "acquisition_time": dt.isoformat(),
                "source": src,
                "product_level": "L2A" if src == "sentinel2" else "GRD",
                "cloud_score": 0.05,
                "quality_score": 0.95,
                "valid_pixel_fraction": 0.95,
                "source_content_hash": f"{yr}_{doy:03d}_{src}".ljust(64, "0"),
                "metrics": dict(metrics),
            })
    return sorted(scenes, key=lambda s: s["acquisition_time"])


def _commit_scenes(
    wl: CanonicalWorldlineService,
    plot_id: str,
    geom_hash: str,
    scenes: List[Dict[str, Any]],
    *,
    tenant_id: str = "default_tenant",
) -> None:
    bs = ArchiveBootstrapService(
        worldline=wl,
        bootstrap_root=wl.root / "_bs_tmp",
        fetcher_factory=lambda s, e: [sc for sc in scenes if s[:10] <= sc["acquisition_time"][:10] < e[:10]],
    )
    bs.run_bootstrap(
        plot_id=plot_id,
        geometry_hash=geom_hash,
        tenant_id=tenant_id,
        start_date=scenes[0]["acquisition_time"][:10] + "T00:00:00+00:00",
        target_end_date=(datetime.fromisoformat(scenes[-1]["acquisition_time"]) + timedelta(days=2)).isoformat(),
        window_days=3650,
    )


def test_wm2_p1_01_tenant_ownership_and_direct_boolean_gate(tmp_path: Path) -> None:
    # 1. Explicit non-fallback tenant partition WITHOUT DB proof stays UNVERIFIED
    ident_unverified, _ = build_domain_chronology(
        plot_id="plot_unverified_part",
        plot_doc={"name": "Unowned Plot", "soilType": "LOAM"},
        crop_cycles=[{
            "_id": "cc1",
            "cropCode": "wheat",
            "declaredCropAuthority": "FARMER_CONFIRMED",
            "declaredCropAt": "2023-01-10T00:00:00+00:00",
            "plantDate": "2023-01-01T00:00:00+00:00",
        }],
        explicit_tenant_id="real_looking_partition_099",
    )
    assert ident_unverified.tenant_identity_verified is False
    assert ident_unverified.is_isolated_dev_fixture is False
    assert ident_unverified.tenant_resolution_source == "explicit_pilot_partition_db_tenant_missing"
    assert "unverified_tenant_identity" in ident_unverified.identity_block_reasons

    # 2. Real Mongo Farm.userId ownership IS verified
    ident_farm, chron_farm = build_domain_chronology(
        plot_id="plot_farm_owned",
        plot_doc={"name": "Farm Owned Plot", "farmId": "farm_01", "soilType": "CLAY"},
        farm_doc={"_id": "farm_01", "userId": "697ddd3bd4195b809226a67b"},
        crop_cycles=[{
            "_id": "cc2",
            "cropCode": "wheat",
            "declaredCropAuthority": "AGRONOMIST_CONFIRMED",
            "declaredCropAt": "2023-01-10T00:00:00+00:00",
            "plantDate": "2023-01-01T00:00:00+00:00",
        }],
    )
    assert ident_farm.tenant_identity_verified is True
    assert ident_farm.tenant_id == "697ddd3bd4195b809226a67b"
    assert ident_farm.tenant_resolution_source == "farm_doc_user_id"

    # 3. Direct boolean gate in reconstruct() catches tenant_identity_verified=False even if block_reasons empty
    from types import SimpleNamespace
    fake_ident = SimpleNamespace(
        tenant_identity_verified=False,
        crop_identity_verified=True,
        synthetic_crop_labels_present=False,
        identity_block_reasons=(),
        to_dict=lambda: {"tenant_identity_verified": False, "crop_identity_verified": True, "identity_block_reasons": []},
    )
    fake_chron = copy.copy(chron_farm)
    fake_chron.identity = fake_ident

    wl = CanonicalWorldlineService(root=tmp_path / "wl", require_durable_anchor=False)
    scenes = _rotation_scenes([2023])[:5]
    _commit_scenes(wl, "plot_gate", "sha256:geom_gate", scenes)
    recon = HistoricalStateReconstructor(worldline=wl, checkpoint_root=tmp_path / "cp", n_ensemble=8)
    out = recon.reconstruct(
        plot_id="plot_gate",
        geometry_hash="sha256:geom_gate",
        daily_weather=_weather_series(2023, 2023),
        domain_chronology=fake_chron,
        retrovalidation_fn=lambda t, c: {"qualification": {"passed": True, "block_reasons": []}},
    )
    assert out["qualification_passed"] is False
    assert out["worldline_posterior_event_type"] == "ARCHIVE_POSTERIOR_DIAGNOSTIC"
    assert "unverified_tenant_identity" in out["validation_block_reasons"]


def test_wm2_p1_02_p2_10_p2_11_authorities_merge_and_unknown_pre_cycle() -> None:
    ident, chron = build_domain_chronology(
        plot_id="plot_merge",
        plot_doc={"tenantId": "tenant_real_02", "soilType": "SANDY_LOAM"},
        crop_cycles=[
            {
                "_id": "cc_legacy",
                "cropCode": "barley",
                "status": "HARVESTED",
                "plantDate": "2020-01-01T00:00:00+00:00",
                "expectedHarvest": "2021-06-30T00:00:00+00:00",
                "createdAt": "2020-01-01T00:00:00+00:00",
            },
            {
                "_id": "cc_conf_rot",
                "cropCode": "tomato",
                "status": "HARVESTED",
                "declaredCropAuthority": "FARMER_CONFIRMED",
                "declaredCropAt": "2023-03-15T00:00:00+00:00",
                "plantDate": "2023-03-01T00:00:00+00:00",
                "expectedHarvest": "2023-08-15T00:00:00+00:00",
                "createdAt": "2023-03-01T00:00:00+00:00",
            },
        ],
        confirmed_crop_labels=[
            {
                "_id": "ccl_2022",
                "cropCode": "wheat",
                "authority": "AGRONOMIST_CONFIRMED",
                "confirmedAt": "2022-04-01T00:00:00+00:00",
                "validFrom": "2022-01-15T00:00:00+00:00",
                "validTo": "2022-06-30T00:00:00+00:00",
                "synthetic": False,
                "labelSource": "field_agronomist_audit",
            }
        ],
        crop_tasks=[
            {"_id": "t_prep", "type": "TILLAGE", "completed": True, "completedAt": "2021-11-10T00:00:00+00:00"}
        ],
    )
    # 1. Legacy unconfirmed CropCycle stays REGISTRY_DECLARED (NOT elevated to FARMER_CONFIRMED)
    d_2020 = chron.as_of(datetime(2020, 6, 1, tzinfo=timezone.utc), knowledge_cutoff_K=datetime(2025, 1, 1, tzinfo=timezone.utc))
    assert d_2020["crop_authority"] == "REGISTRY_DECLARED"
    assert d_2020["crop_verified_as_of_k"] is False

    # 2. ConfirmedCropLabel in 2022 is merged cleanly alongside CropCycles (WM1-P2-10)
    d_2022_before = chron.as_of(datetime(2022, 3, 1, tzinfo=timezone.utc), knowledge_cutoff_K=datetime(2022, 3, 15, tzinfo=timezone.utc))
    d_2022_after = chron.as_of(datetime(2022, 3, 1, tzinfo=timezone.utc), knowledge_cutoff_K=datetime(2022, 5, 1, tzinfo=timezone.utc))
    assert d_2022_before["crop_verified_as_of_k"] is False
    assert d_2022_after["crop_verified_as_of_k"] is True
    assert d_2022_after["verified_crop_code"] == "wheat"

    # 3. Period in 2018 BEFORE any cycle and WITHOUT tillage/fallow confirmation -> PRE_KNOWN_CYCLE_UNKNOWN (WM1-P2-11)
    d_2018 = chron.as_of(datetime(2018, 5, 1, tzinfo=timezone.utc), knowledge_cutoff_K=datetime(2025, 1, 1, tzinfo=timezone.utc))
    assert d_2018["physical_regime"] == "PRE_KNOWN_CYCLE_UNKNOWN"

    # 4. Period right after confirmed 2021-11-10 tillage BEFORE 2022 wheat planting -> PRE_PLANTING_FALLOW_OR_PREP
    d_prep = chron.as_of(datetime(2021, 12, 1, tzinfo=timezone.utc), knowledge_cutoff_K=datetime(2025, 1, 1, tzinfo=timezone.utc))
    assert d_prep["physical_regime"] == "PRE_PLANTING_FALLOW_OR_PREP"


def test_wm2_p1_03_versioned_reprocessed_product_availability() -> None:
    ident, chron = build_domain_chronology(plot_id="reproc_plot", plot_doc={"tenantId": "t_reproc"})
    scenes = [
        # Only a 2023 Collection-2 N0500 reprocessing exists for this 2018-06 acquisition
        {
            "scene_id": "S2A_MSIL2A_20180615T103021_N0500_R108_T31SDA_20231011T023648.SAFE",
            "acquisition_time": "2018-06-15T10:30:21+00:00",
            "source": "sentinel2",
            "processing_baseline": "05.00",
            "product_available_at": "2023-10-11T02:36:48+00:00",
            "metrics": {"ndvi_mean": 0.45, "ndmi_mean": 0.14},
            "valid_pixel_fraction": 0.96,
            "cloud_score": 0.04,
        },
        # Dual-version 2018-09 acquisition: documented N0206 available in 2018 PLUS N0500 reprocessed in 2023
        {
            "scene_id": "S2B_MSIL2A_20180910T103021_N0500_R108_T31SDA_20231012T040000.SAFE",
            "acquisition_time": "2018-09-10T10:30:21+00:00",
            "source": "sentinel2",
            "metrics": {"ndvi_mean": 0.52, "ndmi_mean": 0.18},
            "valid_pixel_fraction": 0.96,
            "cloud_score": 0.04,
            "version_history": [
                {
                    "processing_baseline": "02.06",
                    "available_at": "2018-09-10T15:00:00+00:00",
                    "metrics": {"ndvi_mean": 0.48, "ndmi_mean": 0.15},
                },
                {
                    "processing_baseline": "05.00",
                    "available_at": "2023-10-12T04:00:00+00:00",
                    "metrics": {"ndvi_mean": 0.52, "ndmi_mean": 0.18},
                },
            ],
        },
    ]

    res_k2019 = reconstruct_chronological_crop_posteriors(
        plot_id="reproc_plot",
        tenant_id="t_reproc",
        farm_id="farm_reproc",
        scenes=scenes,
        domain_chronology=chron,
        knowledge_cutoff_K=datetime(2019, 1, 1, tzinfo=timezone.utc),
    )
    res_k2024 = reconstruct_chronological_crop_posteriors(
        plot_id="reproc_plot",
        tenant_id="t_reproc",
        farm_id="farm_reproc",
        scenes=scenes,
        domain_chronology=chron,
        knowledge_cutoff_K=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    assert res_k2019["withheld_reprocessed_after_k_count"] >= 1
    assert res_k2019["eligible_at_k_observation_count"] == 1
    assert res_k2024["withheld_reprocessed_after_k_count"] == 0
    assert res_k2024["eligible_at_k_observation_count"] == 2


def test_wm2_p1_04_p1_05_p1_07_checkpoint_invalidation_replay_equivalence_and_horizon(tmp_path: Path) -> None:
    plot_id = "rot_equiv_plot"
    geom_hash = "sha256:geom_rot_equiv"
    scenes = _rotation_scenes([2022, 2023])
    weather_a = _weather_series(2022, 2023, rain_offset=0.0)
    weather_b = _weather_series(2022, 2023, rain_offset=18.0)

    def _chron(confirmed_2022_at: str = "2022-03-10T00:00:00+00:00", late_2023: bool = False):
        cycles = [
            {
                "_id": "cc_w",
                "cropCode": "wheat",
                "declaredCropAuthority": "FARMER_CONFIRMED",
                "declaredCropAt": confirmed_2022_at,
                "plantDate": "2022-01-15T00:00:00+00:00",
                "expectedHarvest": "2022-07-01T00:00:00+00:00",
            },
            {
                "_id": "cc_t",
                "cropCode": "tomato",
                "declaredCropAuthority": "FARMER_CONFIRMED",
                "declaredCropAt": "2023-06-15T00:00:00+00:00" if late_2023 else "2023-03-01T00:00:00+00:00",
                "plantDate": "2023-03-01T00:00:00+00:00",
                "expectedHarvest": "2023-09-01T00:00:00+00:00",
            },
        ]
        _, c = build_domain_chronology(plot_id=plot_id, plot_doc={"tenantId": "t_rot", "soilType": "LOAM"}, crop_cycles=cycles)
        return c

    chron1 = _chron()
    fusion1 = reconstruct_chronological_crop_posteriors(
        plot_id=plot_id,
        tenant_id="t_rot",
        farm_id="farm_rot",
        scenes=scenes,
        domain_chronology=chron1,
        knowledge_cutoff_K=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

    # Incremental 2022 -> 2023 vs Cold 2022..2023 vs query_as_of
    k_now = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()
    wl_inc = CanonicalWorldlineService(root=tmp_path / "wl_inc", require_durable_anchor=False)
    _commit_scenes(wl_inc, plot_id, geom_hash, scenes, tenant_id="t_rot")
    rec_inc = HistoricalStateReconstructor(worldline=wl_inc, checkpoint_root=tmp_path / "cp_inc", n_ensemble=10, checkpoint_stride=5)
    p1 = rec_inc.reconstruct(
        plot_id=plot_id, geometry_hash=geom_hash, tenant_id="t_rot",
        valid_time_T="2022-12-31T23:59:59+00:00", knowledge_cutoff_K=k_now,
        daily_weather=weather_a, soil_context={"soil_type": "loam"},
        crop_fusion=fusion1, domain_chronology=chron1, emit_worldline_posterior=False,
    )
    p2_inc = rec_inc.reconstruct(
        plot_id=plot_id, geometry_hash=geom_hash, tenant_id="t_rot",
        valid_time_T="2023-12-31T23:59:59+00:00", knowledge_cutoff_K=k_now,
        daily_weather=weather_a, soil_context={"soil_type": "loam"},
        crop_fusion=fusion1, domain_chronology=chron1, emit_worldline_posterior=False,
    )
    assert p2_inc["mode"] == "incremental_continuation"

    wl_cold = CanonicalWorldlineService(root=tmp_path / "wl_cold", require_durable_anchor=False)
    _commit_scenes(wl_cold, plot_id, geom_hash, scenes, tenant_id="t_rot")
    rec_cold = HistoricalStateReconstructor(worldline=wl_cold, checkpoint_root=tmp_path / "cp_cold", n_ensemble=10, checkpoint_stride=5)
    p2_cold = rec_cold.reconstruct(
        plot_id=plot_id, geometry_hash=geom_hash, tenant_id="t_rot",
        valid_time_T="2023-12-31T23:59:59+00:00", knowledge_cutoff_K=k_now,
        daily_weather=weather_a, soil_context={"soil_type": "loam"},
        crop_fusion=fusion1, domain_chronology=chron1, emit_worldline_posterior=False,
    )
    tail_obs_cutoff = p2_cold["checkpoints"][-1]["cutoff_valid_time"]
    q_tail = rec_cold.query_as_of(
        plot_id=plot_id, geometry_hash=geom_hash, tenant_id="t_rot",
        valid_time_T=tail_obs_cutoff, knowledge_cutoff_K=k_now,
        daily_weather=weather_a, soil_context={"soil_type": "loam"},
        crop_fusion=fusion1, domain_chronology=chron1,
    )
    p_mid_cold = HistoricalStateReconstructor(worldline=wl_cold, checkpoint_root=tmp_path / "cp_mid", n_ensemble=10, checkpoint_stride=5).reconstruct(
        plot_id=plot_id, geometry_hash=geom_hash, tenant_id="t_rot",
        valid_time_T="2023-07-01T00:00:00+00:00", knowledge_cutoff_K=k_now,
        daily_weather=weather_a, soil_context={"soil_type": "loam"},
        crop_fusion=fusion1, domain_chronology=chron1, emit_worldline_posterior=False,
    )
    mid_obs_cutoff = p_mid_cold["checkpoints"][-1]["cutoff_valid_time"]
    q_mid_at_obs = rec_cold.query_as_of(
        plot_id=plot_id, geometry_hash=geom_hash, tenant_id="t_rot",
        valid_time_T=mid_obs_cutoff, knowledge_cutoff_K=k_now,
        daily_weather=weather_a, soil_context={"soil_type": "loam"},
        crop_fusion=fusion1, domain_chronology=chron1,
    )
    rec_no_cp = HistoricalStateReconstructor(worldline=wl_cold, checkpoint_root=tmp_path / "cp_empty", n_ensemble=10, checkpoint_stride=5)
    q_no_cp = rec_no_cp.query_as_of(
        plot_id=plot_id, geometry_hash=geom_hash, tenant_id="t_rot",
        valid_time_T="2023-07-01T00:00:00+00:00", knowledge_cutoff_K=k_now,
        daily_weather=weather_a, soil_context={"soil_type": "loam"},
        crop_fusion=fusion1, domain_chronology=chron1,
    )
    q_with_cp = rec_cold.query_as_of(
        plot_id=plot_id, geometry_hash=geom_hash, tenant_id="t_rot",
        valid_time_T="2023-07-01T00:00:00+00:00", knowledge_cutoff_K=k_now,
        daily_weather=weather_a, soil_context={"soil_type": "loam"},
        crop_fusion=fusion1, domain_chronology=chron1,
    )

    for sname in STATE_NAMES:
        assert p2_inc["state_means"][sname] == pytest.approx(p2_cold["state_means"][sname], abs=1e-6)
        assert q_tail["state_means"][sname] == pytest.approx(p2_cold["state_means"][sname], abs=1e-6)
        assert p_mid_cold["state_means"][sname] == pytest.approx(q_mid_at_obs["state_means"][sname], abs=1e-6)
        assert q_no_cp["state_means"][sname] == pytest.approx(q_with_cp["state_means"][sname], abs=1e-6)
    assert p2_inc["crop_chronology_hash"] == p2_cold["crop_chronology_hash"]
    assert p2_inc["weather_lineage_hash"] == p2_cold["weather_lineage_hash"]
    assert q_tail["crop_chronology_hash"] == p2_cold["crop_chronology_hash"]
    assert q_tail["weather_lineage_hash"] == p2_cold["weather_lineage_hash"]

    # Mutate weather_b under identical scene IDs -> invalidates checkpoint chain cleanly!
    p2_wrev = rec_inc.reconstruct(
        plot_id=plot_id, geometry_hash=geom_hash, tenant_id="t_rot",
        valid_time_T="2023-12-31T23:59:59+00:00", knowledge_cutoff_K=k_now,
        daily_weather=weather_b, soil_context={"soil_type": "loam"},
        crop_fusion=fusion1, domain_chronology=chron1, emit_worldline_posterior=False,
    )
    assert p2_wrev["mode"] == "causal_lineage_replay"
    assert p2_wrev["weather_lineage_hash"] != p2_inc["weather_lineage_hash"]
    assert p2_wrev["tail_checkpoint_id"] != p2_inc["tail_checkpoint_id"]

    # Mutate soil texture under identical scene IDs -> invalidates checkpoints!
    p2_soil = rec_inc.reconstruct(
        plot_id=plot_id, geometry_hash=geom_hash, tenant_id="t_rot",
        valid_time_T="2023-12-31T23:59:59+00:00", knowledge_cutoff_K=k_now,
        daily_weather=weather_b, soil_context={"soil_type": "clay"},
        crop_fusion=fusion1, domain_chronology=chron1, emit_worldline_posterior=False,
    )
    assert p2_soil["mode"] == "causal_lineage_replay"
    assert p2_soil["crop_chronology_hash"] != p2_wrev["crop_chronology_hash"]
    assert p2_soil["tail_checkpoint_id"] != p2_wrev["tail_checkpoint_id"]

    # Mutate late 2023 confirmation (WM1-P1-07 prospective horizon cutoff check)
    chron_late = _chron(late_2023=True)
    # Query at T=2023-03-10 across 90-day horizon when tomato was ONLY confirmed at 2023-06-15 (>T!)
    q_horizon = rec_cold.query_as_of(
        plot_id=plot_id, geometry_hash=geom_hash, tenant_id="t_rot",
        valid_time_T="2023-03-10T00:00:00+00:00", knowledge_cutoff_K=k_now,
        daily_weather=weather_a, soil_context={"soil_type": "loam"},
        domain_chronology=chron_late, forecast_horizons_days=(10, 90),
    )
    # Prospective horizon issued at 2023-03-10 MUST NOT leak 2023-06-15 farmer confirmation!
    for fc_h in q_horizon["causal_forecasts"]:
        assert fc_h["crop_context"]["crop_identity_verified"] is False


def test_wm2_p2_08_p2_09_genuine_transfer_and_crop_calibration_metrics() -> None:
    def _synth_plot(pid: str, crop: str, bias_shift: float, is_true_unknown: bool = False):
        samples = []
        for idx in range(18):
            x_raw = 0.25 + 0.025 * idx
            y_obs = max(-1.0, min(1.0, 0.92 * x_raw + bias_shift))
            y_pers = y_obs - (0.04 if idx % 2 == 0 else -0.05)
            samples.append({
                "channel": "ndvi",
                "sensor": "S2",
                "year": 2024,
                "acquisition_time": f"2024-0{(idx % 8) + 1:d}-10T10:30:00+00:00",
                "y_obs": y_obs,
                "y_asmae_raw": x_raw,
                "y_asmae_cal": y_obs * 0.98,
                "y_pers": y_pers,
                "y_clim": y_obs + 0.06,
                "rzw": 0.26,
                "vigor": 0.60,
                "w_rain": 0.0,
            })
        p_group = (
            {"cereal": 0.12, "orchard": 0.08, "vegetable": 0.05, "unknown": 0.75}
            if is_true_unknown
            else {"cereal": 0.78 if crop == "wheat" else 0.12, "orchard": 0.78 if crop == "citrus" else 0.12, "vegetable": 0.78 if crop == "tomato" else 0.05, "unknown": 0.05}
        )
        top_grp = "unknown" if is_true_unknown else ("cereal" if crop == "wheat" else ("orchard" if crop == "citrus" else "vegetable"))
        dom_id_obj, dom_chron_obj = build_domain_chronology(
            plot_id=pid,
            plot_doc={"tenantId": f"t_{pid}", "name": pid, "soilType": "LOAM"},
            crop_cycles=(
                []
                if is_true_unknown
                else [{
                    "_id": f"cc_{pid}",
                    "cropCode": crop,
                    "declaredCropAuthority": "FARMER_CONFIRMED",
                    "declaredCropAt": "2024-02-01T00:00:00+00:00",
                    "plantDate": "2024-01-15T00:00:00+00:00",
                    "expectedHarvest": "2024-11-30T00:00:00+00:00",
                }]
            ),
            crop_observations=(
                [{"_id": f"obs_{pid}", "type": "bare_soil", "confirmed": True, "observedAt": "2024-05-01T00:00:00+00:00", "title": "Verified fallow plot"}]
                if is_true_unknown
                else []
            ),
            crop_tasks=(
                [{"_id": f"prep_{pid}", "type": "TILLAGE", "completed": True, "completedAt": "2024-05-01T00:00:00+00:00"}]
                if is_true_unknown
                else []
            ),
        )
        return {
            "plot_id": pid,
            "plot_name": pid,
            "domain_identity": dom_id_obj.to_dict(),
            "domain_chronology": dom_chron_obj,
            "retrovalidation": {
                "summary": {"n_evaluated_points": 18, "rmse": 0.04, "skill_vs_persistence": 0.35, "skill_vs_climatology": 0.45, "bma_rmse": 0.038},
                "baselines": {"persistence": {"rmse": 0.06}, "doy_climatology": {"rmse": 0.07}, "bma_consensus": {"rmse": 0.038}},
                "bma": {"weights": {"asmae_causal_calibrated": 0.7, "sar_structure": 0.3}},
                "qualification": {"passed": not is_true_unknown, "block_reasons": []},
                "step_transfer_samples": samples,
            },
            "step_transfer_samples": samples,
            "crop_fusion": {
                "latest_crop_posterior": {
                    "top_group": top_grp,
                    "crop_group_posterior": p_group,
                    "unknown_probability": p_group["unknown"],
                    "species_ranking_top5": [{"code": crop, "score": 0.7}],
                },
                "seasonal_timeline": [{
                    "season_id": f"s_{pid}_2024",
                    "start_time": "2024-03-01T00:00:00+00:00",
                    "end_time": "2024-06-15T00:00:00+00:00",
                    "top_group": top_grp,
                    "crop_group_posterior": p_group,
                    "unknown_probability": p_group["unknown"],
                    "species_ranking_top5": [{"code": crop, "score": 0.7}],
                    "raw_posterior": {"model_context_group_posterior": p_group},
                }],
            },
        }

    cohort = [
        _synth_plot("p_wheat_1", "wheat", 0.05),
        _synth_plot("p_citrus_1", "citrus", 0.04),
        _synth_plot("p_tomato_1", "tomato", 0.06),
        _synth_plot("p_fallow_1", "unknown", 0.02, is_true_unknown=True),
    ]
    mat_a = evaluate_cross_plot_matrix(cohort)
    assert mat_a["matrix_version"] == "asmae_world_model_v2_benchmark_matrix"
    lopo_folds = mat_a["trained_transfer_lopo"]["verified_crop_only"]["folds"]
    locso_folds = mat_a["trained_transfer_locso"]["verified_crop_only"]["folds"]
    assert len(lopo_folds) == 3
    assert len(locso_folds) == 3
    assert all(f["status"] == "evaluated" and f["zero_shot_out_of_sample"] is True for f in lopo_folds)

    # Zero-shot leakage check: heavily corrupt held-out p_wheat_1 ground truth -> training-fitted parameters MUST NOT change!
    cohort_corrupted = copy.deepcopy(cohort)
    for s in cohort_corrupted[0]["step_transfer_samples"]:
        s["y_obs"] = -0.95
    mat_b = evaluate_cross_plot_matrix(cohort_corrupted)
    fold_wheat_a = [f for f in mat_a["trained_transfer_lopo"]["verified_crop_only"]["folds"] if f["heldout_plot_id"] == "p_wheat_1"][0]
    fold_wheat_b = [f for f in mat_b["trained_transfer_lopo"]["verified_crop_only"]["folds"] if f["heldout_plot_id"] == "p_wheat_1"][0]
    assert fold_wheat_a["learned_channel_calibration"] == fold_wheat_b["learned_channel_calibration"]
    assert fold_wheat_a["learned_bma_weights"] == fold_wheat_b["learned_bma_weights"]

    # Verify V2 Crop Detection calibration + coverage metrics (WM1-P2-09)
    cb = evaluate_crop_detection_benchmark(cohort)
    assert cb["multiclass_brier_score"] is not None
    assert cb["multiclass_log_loss"] is not None
    assert cb["expected_calibration_error_5bin"] is not None
    assert cb["accepted_coverage"] == 1.0
    assert cb["conditional_accuracy_when_accepted"] == 1.0
    assert cb["known_crop_abstention_rate"] == 0.0
    assert cb["true_non_crop_unknown_recall"] == 1.0


def test_wm2_p2_12_trusted_calibration_store_rejects_forgery_and_revocation() -> None:
    store = TrustedCalibrationArtifactStore(signing_secret="secret-v2-test")
    sch = "1" * 64
    art = "2" * 64
    rec = store.issue_and_register(calibration_artifact_hash=art, feature_schema_hash=sch, ece=0.04)

    ok_receipt = {
        "calibration_artifact_hash": art,
        "feature_schema_hash": sch,
        "signature_hmac": rec.signature_hmac,
    }
    v, _, _ = store.verify_receipt(ok_receipt, expected_feature_schema_hash=sch)
    assert v == "valid"

    # Tampered signature fails
    bad_sig = {**ok_receipt, "signature_hmac": "f" * 64}
    assert store.verify_receipt(bad_sig, expected_feature_schema_hash=sch)[0] == "unavailable"

    # Schema mismatch fails
    assert store.verify_receipt(ok_receipt, expected_feature_schema_hash="9" * 64)[0] == "unavailable"

    # Revocation invalidates immediately
    store.revoke(art, reason="drift_detected")
    assert store.verify_receipt(ok_receipt, expected_feature_schema_hash=sch)[0] == "unavailable"


def test_wm2_p1_06_benchmark_matrix_endpoint_auth_and_redaction(tmp_path: Path, monkeypatch) -> None:
    from services.agribrain.app import main as main_mod
    from services.agribrain.app.internal_service_auth import (
        compute_request_signature,
    )

    bm_file = Path("services/agribrain/artifacts/archive_pilot_reports/asmae_world_model_v2_benchmark_matrix.json")
    bm_file.parent.mkdir(parents=True, exist_ok=True)
    had_existing = bm_file.is_file()
    prev_bytes = bm_file.read_bytes() if had_existing else None

    fake_matrix = {
        "matrix_version": "asmae_world_model_v2_benchmark_matrix",
        "cohort_size": 1,
        "verified_crop_plot_count": 1,
        "verified_tenant_plot_count": 1,
        "scientifically_qualified_model_count": 0,
        "production_eligible_verified_count": 0,
        "qualified_verified_crop_count": 0,
        "metric_definitions": {"mse_skill_score": "1 - MSE/MSE_ref"},
        "descriptive_per_plot_summary": [
            {
                "plot_id": "plot_sec_1",
                "tenant_id": "697ddd3bd4195b809226a67b",
                "user_id": "secret_user_123",
                "artifact_path": "C:\\Users\\E-C\\Desktop\\secret.json",
                "crop_code": "wheat",
            }
        ],
        "descriptive_crop_group_summary": [],
        "trained_transfer_lopo": {"verified_crop_only": {"aggregate": {}, "folds": []}},
        "trained_transfer_locso": {"verified_crop_only": {"aggregate": {}, "folds": []}},
        "crop_detection_benchmark": {},
    }
    bm_file.write_text(json.dumps(fake_matrix), encoding="utf-8")

    try:
        client = TestClient(main_mod.app)
        # 1. Anonymous rejected with 401
        resp_anon = client.get("/v2/asmae/benchmark-matrix")
        assert resp_anon.status_code == 401

        def _sign(tenant: str, farm: str, plot: str, extra_role: str | None = None):
            ts = str(int(datetime.now(timezone.utc).timestamp()))
            nonce = f"n_{tenant}_{plot}_{ts}_{extra_role or 'none'}"
            sig = compute_request_signature(
                method="GET",
                path="/v2/asmae/benchmark-matrix",
                query_string="",
                tenant_id=tenant,
                farm_id=farm,
                plot_id=plot,
                body_bytes=b"",
                timestamp=ts,
                nonce=nonce,
                key_version="v1",
            )
            hdrs = {
                "X-AgriBrain-Signature": sig,
                "X-AgriBrain-Timestamp": ts,
                "X-AgriBrain-Nonce": nonce,
                "X-AgriBrain-Key-Version": "v1",
                "X-Tenant-Id": tenant,
                "X-Farm-Id": farm,
                "X-Plot-Id": plot,
            }
            if extra_role is not None:
                hdrs["X-AgriBrain-Benchmark-Role"] = extra_role
            return hdrs

        # 2. Signed plot-scoped caller even attempting to spoof benchmark_admin header -> 403
        resp_plot = client.get(
            "/v2/asmae/benchmark-matrix",
            headers=_sign("697ddd3bd4195b809226a67b", "farm_1", "plot_sec_1", extra_role="benchmark_admin"),
        )
        assert resp_plot.status_code == 403

        # 3. Cross-tenant admin without allowed admin role -> 403
        resp_no_role = client.get(
            "/v2/asmae/benchmark-matrix",
            headers=_sign("benchmark_admin", "__benchmark_cohort__", "__benchmark_cohort__", extra_role=None),
        )
        assert resp_no_role.status_code == 403

        # 4. Authorized benchmark admin -> 200 AND scrubbed PII / tenant_id / paths!
        resp_ok = client.get(
            "/v2/asmae/benchmark-matrix",
            headers=_sign("benchmark_admin", "__benchmark_cohort__", "__benchmark_cohort__", extra_role="benchmark_admin"),
        )
        assert resp_ok.status_code == 200
        body = resp_ok.json()
        assert body["redacted_projection"] is True
        body_text = json.dumps(body)
        assert "697ddd3bd4195b809226a67b" not in body_text
        assert "secret_user_123" not in body_text
        assert "C:\\\\Users" not in body_text
    finally:
        if had_existing and prev_bytes is not None:
            bm_file.write_bytes(prev_bytes)
        elif bm_file.is_file():
            bm_file.unlink()


def test_wm2_batch_a_june_inseason_never_leaks_september_imagery() -> None:
    """June 15 crop_context_as_of using K=now must NEVER condition on July-Sept imagery in the same season."""
    from services.agribrain.layer05_asmae.history.historical_crop_fusion import crop_context_as_of

    _, chron = build_domain_chronology(
        plot_id="inseason_plot",
        plot_doc={"tenantId": "t_inseason", "soilType": "LOAM"},
    )
    march_to_june = [
        {
            "scene_id": "S2_20240310",
            "acquisition_time": "2024-03-10T10:30:00+00:00",
            "source": "sentinel2",
            "metrics": {"ndvi_mean": 0.30, "ndmi_mean": 0.08},
        },
        {
            "scene_id": "S2_20240415",
            "acquisition_time": "2024-04-15T10:30:00+00:00",
            "source": "sentinel2",
            "metrics": {"ndvi_mean": 0.45, "ndmi_mean": 0.14},
        },
        {
            "scene_id": "S2_20240605",
            "acquisition_time": "2024-06-05T10:30:00+00:00",
            "source": "sentinel2",
            "metrics": {"ndvi_mean": 0.62, "ndmi_mean": 0.20},
        },
    ]
    july_to_sept = [
        {
            "scene_id": "S2_20240720",
            "acquisition_time": "2024-07-20T10:30:00+00:00",
            "source": "sentinel2",
            "metrics": {"ndvi_mean": 0.84, "ndmi_mean": 0.32},
        },
        {
            "scene_id": "S2_20240915",
            "acquisition_time": "2024-09-15T10:30:00+00:00",
            "source": "sentinel2",
            "metrics": {"ndvi_mean": 0.22, "ndmi_mean": 0.04},
        },
    ]
    fusion_trunc = reconstruct_chronological_crop_posteriors(
        plot_id="inseason_plot",
        tenant_id="t_inseason",
        farm_id="f_inseason",
        scenes=march_to_june,
        domain_chronology=chron,
        knowledge_cutoff_K=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    fusion_full = reconstruct_chronological_crop_posteriors(
        plot_id="inseason_plot",
        tenant_id="t_inseason",
        farm_id="f_inseason",
        scenes=march_to_june + july_to_sept,
        domain_chronology=chron,
        knowledge_cutoff_K=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert len(fusion_full["seasonal_timeline"]) >= 1
    assert fusion_full["seasonal_timeline"][-1]["end_time"] >= "2024-09-15"

    ctx_trunc = crop_context_as_of(
        fusion_trunc,
        valid_time_T=datetime(2024, 6, 15, tzinfo=timezone.utc),
        knowledge_cutoff_K=datetime(2026, 1, 1, tzinfo=timezone.utc),
        domain_chronology=chron,
    )
    ctx_full = crop_context_as_of(
        fusion_full,
        valid_time_T=datetime(2024, 6, 15, tzinfo=timezone.utc),
        knowledge_cutoff_K=datetime(2026, 1, 1, tzinfo=timezone.utc),
        domain_chronology=chron,
    )
    assert ctx_full["crop_group_posterior"] == ctx_trunc["crop_group_posterior"]
    assert ctx_full["crop_mixture_conditioning"] == ctx_trunc["crop_mixture_conditioning"]
    assert ctx_full["unknown_probability"] == pytest.approx(ctx_trunc["unknown_probability"], abs=1e-6)


def test_wm2_batch_a_rejects_later_knowledge_cutoff_checkpoint(tmp_path: Path) -> None:
    """Warm checkpoint built with K_later must be rejected when querying K_earlier even with identical scenes."""
    plot_id = "k_guard_plot"
    geom_hash = "sha256:geom_k_guard"
    scenes = _rotation_scenes([2022])
    wl = CanonicalWorldlineService(root=tmp_path / "wl", require_durable_anchor=False)
    _commit_scenes(wl, plot_id, geom_hash, scenes, tenant_id="t_k")

    # Rain arrives on 2022-05-01 ONLY ingested at K_later (2022-06-15)
    weather = _weather_series(2022, 2022)
    weather["2022-05-01"] = {
        "temp_max": 19.0,
        "temp_min": 10.0,
        "precipitation": 65.0,
        "et0": 1.8,
        "ingested_at": "2022-06-15T00:00:00+00:00",
    }

    rec_warm = HistoricalStateReconstructor(worldline=wl, checkpoint_root=tmp_path / "cp_warm", n_ensemble=10, checkpoint_stride=3)
    k_later = (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat()
    rec_warm.reconstruct(
        plot_id=plot_id, geometry_hash=geom_hash, tenant_id="t_k",
        valid_time_T="2022-12-31T00:00:00+00:00", knowledge_cutoff_K=k_later,
        daily_weather=weather, emit_worldline_posterior=False,
    )

    k_earlier = datetime(2022, 5, 10, tzinfo=timezone.utc).isoformat()
    q_warm_at_earlier = rec_warm.query_as_of(
        plot_id=plot_id, geometry_hash=geom_hash, tenant_id="t_k",
        valid_time_T="2022-05-10T00:00:00+00:00", knowledge_cutoff_K=k_earlier,
        daily_weather=weather,
    )
    # Wait: if scenes were committed today (>2022), also test matching committed_at < K_earlier via fresh worldline!
    wl_early = CanonicalWorldlineService(root=tmp_path / "wl_e", require_durable_anchor=False)
    for sc in scenes:
        wl_early.commit_observation_event if hasattr(wl_early, "commit_observation_event") else None
    rec_cold = HistoricalStateReconstructor(worldline=wl, checkpoint_root=tmp_path / "cp_cold_only", n_ensemble=10, checkpoint_stride=3)
    # Check using an intermediate cutoff right after commit time vs later weather revision ingested AFTER commit
    k_post_commit = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()
    weather_late_rev = _weather_series(2022, 2022)
    weather_late_rev["2022-05-01"] = {
        "temp_max": 19.0,
        "temp_min": 10.0,
        "precipitation": 75.0,
        "et0": 1.5,
        "ingested_at": (datetime.now(timezone.utc) + timedelta(minutes=3)).isoformat(),
    }
    k_future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    rec_warm.reconstruct(
        plot_id=plot_id, geometry_hash=geom_hash, tenant_id="t_k",
        valid_time_T="2022-12-31T00:00:00+00:00", knowledge_cutoff_K=k_future,
        daily_weather=weather_late_rev, emit_worldline_posterior=False,
    )
    q_earlier_warm = rec_warm.query_as_of(
        plot_id=plot_id, geometry_hash=geom_hash, tenant_id="t_k",
        valid_time_T="2022-06-01T00:00:00+00:00", knowledge_cutoff_K=k_post_commit,
        daily_weather=weather_late_rev,
    )
    q_earlier_cold = rec_cold.query_as_of(
        plot_id=plot_id, geometry_hash=geom_hash, tenant_id="t_k",
        valid_time_T="2022-06-01T00:00:00+00:00", knowledge_cutoff_K=k_post_commit,
        daily_weather=weather_late_rev,
    )
    assert q_earlier_warm["resumed_from_checkpoint_id"] is None
    assert q_earlier_warm["weather_lineage_hash"] == q_earlier_cold["weather_lineage_hash"]
    for sname in STATE_NAMES:
        assert q_earlier_warm["state_means"][sname] == pytest.approx(q_earlier_cold["state_means"][sname], abs=1e-6)


def test_wm2_batch_b_as_issued_k_eq_t_issue_and_p2_late_scene_plot_mean(tmp_path: Path) -> None:
    """Verify reconstruct() rebuilds multi-horizon issuance states at K=t_issue & P2 plot-mean excludes late scenes."""
    from services.agribrain.layer05_asmae.history.independent_field_validation import evaluate_independent_field_evidence

    plot_id = "as_issued_plot"
    geom_hash = "sha256:geom_as_issued"
    scenes = _rotation_scenes([2022, 2023, 2024])
    wl = CanonicalWorldlineService(root=tmp_path / "wl_ai", require_durable_anchor=False)
    bs = ArchiveBootstrapService(
        worldline=wl,
        bootstrap_root=wl.root / "_bs",
        fetcher_factory=lambda s, e: [sc for sc in scenes if s[:10] <= sc["acquisition_time"][:10] < e[:10]],
    )
    # Commit each scene with committed_at == acquisition_time so historical K=t_issue sees scenes up to t_issue!
    prev_ev = None
    for sc in scenes:
        ev_id = bs._commit_scene_to_worldline(plot_id, geom_hash, "t_ai", "default", sc, prev_ev)
        # Patch committed_at in saved event file to simulate historical chronological ingestion
        ev_p = wl._event_path(plot_id, ev_id, tenant_id="t_ai", namespace="default")
        raw_ev = json.loads(ev_p.read_text(encoding="utf-8"))
        raw_ev["committed_at"] = sc["acquisition_time"]
        ev_p.write_text(json.dumps(raw_ev, indent=2), encoding="utf-8")
        prev_ev = ev_id

    rec = HistoricalStateReconstructor(worldline=wl, checkpoint_root=tmp_path / "cp_ai", n_ensemble=8, checkpoint_stride=8)
    res = rec.reconstruct(
        plot_id=plot_id,
        geometry_hash=geom_hash,
        tenant_id="t_ai",
        daily_weather=_weather_series(2022, 2024),
        retrovalidation_fn=HistoricalRetrovalidator().evaluate,
        emit_worldline_posterior=False,
    )
    mh = res["retrovalidation"]["multi_horizon"]
    assert mh["as_issued_state_rebuilt_with_k_eq_t_issue"] is True
    assert mh["uses_issuance_time_knowledge_cutoff_K"] is True
    assert mh["as_issued_issue_points_evaluated"] >= 1

    # P2 plot-mean fallback must EXCLUDE scenes whose committed_at > probe timestamp!
    traj_late = [
        {
            "acquisition_time": "2024-05-01T10:30:00+00:00",
            "committed_at": "2024-06-20T00:00:00+00:00",  # Arrived AFTER the May 10 probe!
            "posterior_state_means": {"root_zone_water": 0.30},
            "posterior_state_stds": {"root_zone_water": 0.04},
        }
    ]
    probe_unver = [
        {
            "timestamp": "2024-05-10T12:00:00+00:00",
            "soilMoisture": 25.0,
            "vendor": "Sentek Drill & Drop",
            "isCalibrated": True,  # bare flag without certificate authority & timestamp!
            "deviceId": "S_LATE",
        }
    ]
    fv = evaluate_independent_field_evidence(
        plot_id="late_scene_fv",
        trajectory=traj_late,
        sensor_readings=probe_unver,
    )
    assert fv["sensor_vwc_validation"]["n_readings"] == 0
    assert fv["sensor_vwc_validation"]["excluded_late_committed_scene_non_causal"] >= 1


def test_wm21_p1_crop_interval_and_soil_revision_invalidate_warm_checkpoints(tmp_path):
    """V2.1 P1 adversarial stale-checkpoint reproduction: mutating crop_code, confirmed flag,
    or soil texture with identical interval dates invalidates warm checkpoints and equals cold run."""
    from services.agribrain.layer05_asmae.history.archive_bootstrap_service import ArchiveBootstrapService
    from services.agribrain.layer05_asmae.history.domain_chronology import build_domain_chronology
    from services.agribrain.layer05_asmae.history.historical_state_reconstructor import (
        HistoricalStateReconstructor,
        _compute_causal_input_lineage_hashes,
    )
    from services.agribrain.world_model.canonical_worldline import CanonicalWorldlineService

    plot_id = "stale_cp_repro"
    geom_hash = "sha256:geom_stale_cp"
    scenes = _rotation_scenes([2023, 2024])[:6]
    wl = CanonicalWorldlineService(root=tmp_path / "wl_cp_mut", require_durable_anchor=False)
    _commit_scenes(wl, plot_id, geom_hash, scenes, tenant_id="t_cp")

    weather = _weather_series(2023, 2024)
    common_farm = {"_id": "farm_1", "userId": "t_cp"}
    _, dom_wheat = build_domain_chronology(
        plot_id=plot_id,
        plot_doc={"farmId": "farm_1", "soilType": "loam"},
        farm_doc=common_farm,
        crop_cycles=[{
            "_id": "cc_same_id",
            "cropCode": "wheat",
            "variety": "Durum",
            "plantDate": "2023-02-01T00:00:00Z",
            "harvestDate": "2024-08-01T00:00:00Z",
            "createdAt": "2023-01-15T00:00:00Z",
            "declaredCropAt": "2023-02-01T00:00:00Z",
            "declaredCropAuthority": "FARMER_CONFIRMED",
        }],
        soil_analyses=[{"_id": "sa_1", "texture": "loam", "ph": 6.8, "date": "2023-01-20T00:00:00Z"}],
    )
    _, dom_tomato = build_domain_chronology(
        plot_id=plot_id,
        plot_doc={"farmId": "farm_1", "soilType": "loam"},
        farm_doc=common_farm,
        crop_cycles=[{
            "_id": "cc_same_id",
            "cropCode": "tomato",
            "variety": "Roma",
            "plantDate": "2023-02-01T00:00:00Z",
            "harvestDate": "2024-08-01T00:00:00Z",
            "createdAt": "2023-01-15T00:00:00Z",
            "declaredCropAt": "2023-02-01T00:00:00Z",
            "declaredCropAuthority": "FARMER_CONFIRMED",
        }],
        soil_analyses=[{"_id": "sa_1", "texture": "loam", "ph": 6.8, "date": "2023-01-20T00:00:00Z"}],
    )
    _, dom_clay_soil = build_domain_chronology(
        plot_id=plot_id,
        plot_doc={"farmId": "farm_1", "soilType": "clay"},
        farm_doc=common_farm,
        crop_cycles=[{
            "_id": "cc_same_id",
            "cropCode": "wheat",
            "variety": "Durum",
            "plantDate": "2023-02-01T00:00:00Z",
            "harvestDate": "2024-08-01T00:00:00Z",
            "createdAt": "2023-01-15T00:00:00Z",
            "declaredCropAt": "2023-02-01T00:00:00Z",
            "declaredCropAuthority": "FARMER_CONFIRMED",
        }],
        soil_analyses=[{"_id": "sa_1", "texture": "clay", "ph": 7.6, "date": "2023-01-20T00:00:00Z"}],
    )

    t_eval = datetime(2024, 6, 15, tzinfo=timezone.utc)
    k_eval = datetime(2026, 12, 1, tzinfo=timezone.utc)
    h_wheat = _compute_causal_input_lineage_hashes(cutoff_dt=t_eval, knowledge_cutoff_dt=k_eval, domain_chronology=dom_wheat, soil_context={"soil_type": "loam"}, daily_weather=weather)
    h_tomato = _compute_causal_input_lineage_hashes(cutoff_dt=t_eval, knowledge_cutoff_dt=k_eval, domain_chronology=dom_tomato, soil_context={"soil_type": "loam"}, daily_weather=weather)
    h_clay = _compute_causal_input_lineage_hashes(cutoff_dt=t_eval, knowledge_cutoff_dt=k_eval, domain_chronology=dom_clay_soil, soil_context={"soil_type": "clay"}, daily_weather=weather)

    assert h_wheat["crop_chronology_hash"] != h_tomato["crop_chronology_hash"]
    assert h_wheat["input_manifest_hash"] != h_tomato["input_manifest_hash"]
    assert h_wheat["crop_chronology_hash"] != h_clay["crop_chronology_hash"]
    assert h_wheat["input_manifest_hash"] != h_clay["input_manifest_hash"]

    warm_cp_dir = tmp_path / "cp_warm"
    cold_cp_dir = tmp_path / "cp_cold"
    rec_warm = HistoricalStateReconstructor(worldline=wl, checkpoint_root=warm_cp_dir, n_ensemble=8, checkpoint_stride=3)
    rec_warm.reconstruct(
        plot_id=plot_id,
        geometry_hash=geom_hash,
        tenant_id="t_cp",
        daily_weather=weather,
        domain_chronology=dom_wheat,
        soil_context={"soil_type": "loam"},
        emit_worldline_posterior=False,
    )
    q_tomato_warm = rec_warm.query_as_of(
        plot_id=plot_id,
        geometry_hash=geom_hash,
        valid_time_T="2024-06-15",
        tenant_id="t_cp",
        daily_weather=weather,
        domain_chronology=dom_tomato,
        soil_context={"soil_type": "loam"},
        forecast_horizons_days=(),
    )
    assert q_tomato_warm["resumed_from_checkpoint_id"] is None

    rec_cold = HistoricalStateReconstructor(worldline=wl, checkpoint_root=cold_cp_dir, n_ensemble=8, checkpoint_stride=3)
    q_tomato_cold = rec_cold.query_as_of(
        plot_id=plot_id,
        geometry_hash=geom_hash,
        valid_time_T="2024-06-15",
        tenant_id="t_cp",
        daily_weather=weather,
        domain_chronology=dom_tomato,
        soil_context={"soil_type": "loam"},
        forecast_horizons_days=(),
    )
    assert q_tomato_warm["input_manifest_hash"] == q_tomato_cold["input_manifest_hash"]
    assert q_tomato_warm["crop_chronology_hash"] == q_tomato_cold["crop_chronology_hash"]
    assert q_tomato_warm["state_means"] == q_tomato_cold["state_means"]


def test_wm21_p2_crop_posterior_memoization_key_binds_spectral_soil_and_cycle():
    """V2.1 P2: crop_context_as_of memoization must invalidate on spectral, soil, or cycle mutations."""
    from services.agribrain.layer05_asmae.history.domain_chronology import build_domain_chronology
    from services.agribrain.layer05_asmae.history.historical_crop_fusion import crop_context_as_of

    canon_obs = [{
        "observation_id": "obs_s2_same",
        "sensing_time": "2024-04-10T10:30:00+00:00",
        "ndvi": 0.78,
        "evi": 0.55,
        "ndwi": 0.12,
        "ndmi": 0.25,
        "contract_version": "canonical_crop_observation_v2",
        "version_history": [{
            "processing_baseline": "05.10",
            "product_available_at": "2024-04-11T00:00:00+00:00",
            "content_hash": "hash_high_ndvi",
            "ndvi": 0.78,
        }],
    }]
    fusion = {
        "plot_id": "memo_plot",
        "tenant_id": "memo_t",
        "seasonal_timeline": [{
            "season_id": "s1",
            "start_time": "2024-01-01T00:00:00+00:00",
            "end_time": "2024-08-01T00:00:00+00:00",
            "evidence_end_time": "2024-08-01T00:00:00+00:00",
            "max_product_available_at": "2024-08-02T00:00:00+00:00",
        }],
        "canonical_observations": canon_obs,
        "_causal_prefix_cache": {},
    }
    _, dom_a = build_domain_chronology(
        plot_id="memo_plot",
        crop_cycles=[{"_id": "c1", "cropCode": "wheat", "plantDate": "2024-01-01T00:00:00Z", "harvestDate": "2024-08-01T00:00:00Z"}],
    )
    t_q = datetime(2024, 5, 1, tzinfo=timezone.utc)
    r1 = crop_context_as_of(fusion, valid_time_T=t_q, knowledge_cutoff_K=t_q, domain_chronology=dom_a, base_soil_context={"soil_type": "loam"})
    assert len(fusion["_causal_prefix_cache"]) == 1

    # Same inputs hit cache
    r1_cached = crop_context_as_of(fusion, valid_time_T=t_q, knowledge_cutoff_K=t_q, domain_chronology=dom_a, base_soil_context={"soil_type": "loam"})
    assert len(fusion["_causal_prefix_cache"]) == 1
    assert r1_cached == r1

    # Mutate observation content without changing observation_id or baseline -> must create distinct cache entry
    canon_obs[0]["ndvi"] = 0.14
    canon_obs[0]["version_history"][0]["content_hash"] = "hash_low_ndvi"
    canon_obs[0]["version_history"][0]["ndvi"] = 0.14
    crop_context_as_of(fusion, valid_time_T=t_q, knowledge_cutoff_K=t_q, domain_chronology=dom_a, base_soil_context={"soil_type": "loam"})
    assert len(fusion["_causal_prefix_cache"]) == 2

    # Mutate soil context -> must create distinct cache entry
    crop_context_as_of(fusion, valid_time_T=t_q, knowledge_cutoff_K=t_q, domain_chronology=dom_a, base_soil_context={"soil_type": "clay"})
    assert len(fusion["_causal_prefix_cache"]) == 3

    # Mutate crop cycle record id/variety while keeping declared crop / authority -> must create distinct cache entry
    _, dom_b = build_domain_chronology(
        plot_id="memo_plot",
        crop_cycles=[{"_id": "c1", "cropCode": "wheat", "variety": "UpdatedCultivar", "plantDate": "2024-01-01T00:00:00Z", "harvestDate": "2024-08-01T00:00:00Z"}],
    )
    crop_context_as_of(fusion, valid_time_T=t_q, knowledge_cutoff_K=t_q, domain_chronology=dom_b, base_soil_context={"soil_type": "clay"})
    assert len(fusion["_causal_prefix_cache"]) == 4


def test_wm21_p2_calibration_registry_production_hardening_and_persistence(tmp_path, monkeypatch):
    """V2.1 P2: Calibration registry fails closed without provisioned secret in prod and persists revocations."""
    from services.agribrain.layer2_veg_int.features.calibration_registry import (
        CalibrationEvaluationRecord,
        TrustedCalibrationArtifactStore,
    )

    monkeypatch.delenv("AGRIBRAIN_CALIBRATION_TRUST_SECRET", raising=False)
    monkeypatch.setenv("NODE_ENV", "production")

    prod_store = TrustedCalibrationArtifactStore()
    with pytest.raises(RuntimeError):
        prod_store.issue_and_register(calibration_artifact_hash="a" * 64, feature_schema_hash="b" * 64)
    status_missing, _, reason_missing = prod_store.verify_receipt(
        {"calibration_artifact_hash": "a" * 64, "signature_hmac": "0" * 64}
    )
    assert status_missing == "unavailable"
    assert reason_missing == "production_calibration_trust_secret_missing"

    # Dev store issuing with dev ephemeral secret cannot pass require_production_trust=True
    monkeypatch.setenv("NODE_ENV", "development")
    dev_store = TrustedCalibrationArtifactStore(registry_path=tmp_path / "dev_cal_reg.json")
    dev_rec = dev_store.issue_and_register(
        calibration_artifact_hash="c" * 64,
        feature_schema_hash="d" * 64,
        calibration_evaluation_digest="e" * 64,
    )
    st_dev_in_prod, _, rsn_dev_in_prod = dev_store.verify_receipt(
        {"calibration_artifact_hash": "c" * 64, "feature_schema_hash": "d" * 64, "signature_hmac": dev_rec.signature_hmac},
        require_production_trust=True,
    )
    assert st_dev_in_prod == "unavailable"
    assert rsn_dev_in_prod == "dev_ephemeral_calibration_secret_forbidden_in_production"

    # Provisioned durable registry persists across process reload and enforces durable revocation
    monkeypatch.setenv("NODE_ENV", "production")
    monkeypatch.setenv("AGRIBRAIN_CALIBRATION_TRUST_SECRET", "prod-test-secret-key-minimum-length-32")
    reg_file = tmp_path / "prod_cal_registry.json"
    eval_rec = CalibrationEvaluationRecord(
        evaluation_digest="1" * 64,
        evaluator_version="v3_loocv",
        dataset_scope="external_confirmed_disjoint",
        evaluated_season_count=12,
        confirmed_label_seasons_count=12,
        ece=0.04,
        multiclass_brier_score=0.22,
        multiclass_log_loss=0.41,
    )
    s_writer = TrustedCalibrationArtifactStore(registry_path=reg_file, require_production_trust=True)
    issued = s_writer.issue_and_register(
        calibration_artifact_hash="2" * 64,
        feature_schema_hash="3" * 64,
        calibration_evaluation_digest="1" * 64,
        evaluation_record=eval_rec,
    )
    s_reloaded = TrustedCalibrationArtifactStore(registry_path=reg_file, require_production_trust=True)
    assert s_reloaded.status_summary()["production_trust_ready"] is True
    ok_st, _, _ = s_reloaded.verify_receipt(
        {"calibration_artifact_hash": "2" * 64, "feature_schema_hash": "3" * 64, "signature_hmac": issued.signature_hmac}
    )
    assert ok_st == "valid"

    s_writer.revoke("2" * 64, reason="drift_detected")
    rev_st, _, rev_rsn = s_reloaded.verify_receipt(
        {"calibration_artifact_hash": "2" * 64, "feature_schema_hash": "3" * 64, "signature_hmac": issued.signature_hmac}
    )
    assert rev_st == "unavailable"
    assert "revoked" in rev_rsn


def test_wm21_p2_cached_tenant_provenance_and_ablation_parity():
    """V2.1 P2: Cached offline domain metadata cannot grant live production ownership; ablation flags non-equivalent protocols."""
    from services.agribrain.layer05_asmae.history.domain_chronology import build_domain_chronology
    from services.agribrain.layer05_asmae.history.historical_retrovalidation import HistoricalRetrovalidator

    ident_cached, _ = build_domain_chronology(
        plot_id="p_cached",
        plot_doc={"farmId": "f1", "soilType": "loam"},
        farm_doc={"_id": "f1", "userId": "u_real_1"},
        crop_cycles=[{
            "cropCode": "citrus",
            "declaredCropAuthority": "FARMER_CONFIRMED",
            "plantDate": "2020-01-01T00:00:00Z",
        }],
        tenant_provenance="local_domain_metadata_cache",
        tenant_verified_at="2026-11-26T10:00:00+00:00",
    )
    assert ident_cached.tenant_authority_tier == "CACHED_REGISTRY_IDENTITY_ONLY"
    assert ident_cached.tenant_identity_fresh_db_verified is False
    assert ident_cached.qualifies_for_production_archive() is False
    assert "cached_tenant_ownership_not_fresh_db_verified" in ident_cached.identity_block_reasons

    ident_live, _ = build_domain_chronology(
        plot_id="p_live",
        plot_doc={"farmId": "f1", "soilType": "loam"},
        farm_doc={"_id": "f1", "userId": "u_real_1"},
        crop_cycles=[{
            "cropCode": "citrus",
            "declaredCropAuthority": "FARMER_CONFIRMED",
            "plantDate": "2020-01-01T00:00:00Z",
        }],
        tenant_provenance="live_db",
        tenant_verified_at="2026-11-27T12:00:00+00:00",
    )
    assert ident_live.tenant_authority_tier == "LIVE_DB_OWNERSHIP_VERIFIED"
    assert ident_live.tenant_identity_fresh_db_verified is True
    assert ident_live.qualifies_for_production_archive() is True

    abl = HistoricalRetrovalidator.compare_cross_layer_ablation(
        {
            "summary": {"rmse": 0.072, "mean_crps": 0.035, "coverage_1sigma": 0.71},
            "multi_horizon": {
                "as_issued_state_rebuilt_with_k_eq_t_issue": False,
                "by_horizon": {"short_1_7d": {"n": 0}, "medium_8_16d": {"n": 0}, "extended_17_35d": {"n": 0}},
                "diagnostic_backfill_horizon_reference": {"by_horizon": {"short_1_7d": {"n": 36, "skill_vs_persistence": -0.1}}},
            },
        },
        {
            "summary": {"rmse": 0.072, "mean_crps": 0.036, "coverage_1sigma": 0.70},
            "multi_horizon": {
                "as_issued_state_rebuilt_with_k_eq_t_issue": None,
                "by_horizon": {"short_1_7d": {"n": 266, "skill_vs_persistence": 0.07}},
            },
        },
    )
    assert abl["multi_horizon_protocol_equivalent"] is False
    assert abl["s1_s2_only_multi_horizon"]["short_1_7d"]["n"] == 0
    assert abl["diagnostic_backfill_horizon_comparison"]["protocol_equivalent"] is True


def test_wm3_prospective_forecast_ledger_and_loocv_crop_calibrator(tmp_path):
    """V3 Foundation: Append-only hash-chained prospective forecast ledger & LOOCV crop-group calibration gate."""
    from services.agribrain.layer05_asmae.history.historical_crop_fusion import evaluate_cross_validated_crop_calibration
    from services.agribrain.layer05_asmae.history.prospective_forecast_ledger import (
        CausalIssuanceViolation,
        ImmutableIssuanceError,
        ImmutableScoreError,
        IntegrityTamperError,
        ProspectiveForecastLedger,
        RetroactiveOutcomeViolation,
    )

    ledger = ProspectiveForecastLedger(tmp_path / "prosp_ledger")

    # Rejects retroactive target before issued_at or K > issued_at
    with pytest.raises(CausalIssuanceViolation):
        ledger.record_forecast_issuance(
            forecast_id="bad_retro",
            plot_id="p1",
            tenant_id="t1",
            farm_id="f1",
            geometry_hash="gh1",
            issued_at="2026-11-27T12:00:00+00:00",
            knowledge_cutoff_time="2026-11-27T12:00:00+00:00",
            target_valid_time="2026-11-20T12:00:00+00:00",
            horizon_days=7,
            model_version="v5",
            calibration_version="cal_v10",
            state_schema_version="s13",
            input_manifest_hash="m" * 64,
            observation_lineage_hash="o" * 64,
            crop_chronology_hash="c" * 64,
            weather_lineage_hash="w" * 64,
            specialist_config_hash="sp" * 32,
            complete_model_state={"state_means": {"vigor": 0.6}},
            crop_posterior={"crop": "citrus"},
            weather_forecast={"t_max": 22.0},
            channel_calibration={"ndvi": {"slope": 1.0, "bias": 0.0}},
            specialist_outputs={"water_stress": 0.1},
            bma_weights={"asmae_causal_calibrated": 1.0},
            predicted_channels={"ndvi": {"mean": 0.62, "sigma": 0.06, "y_pers": 0.58}},
        )

    iss = ledger.record_forecast_issuance(
        forecast_id="fc_001",
        plot_id="p1",
        tenant_id="t1",
        farm_id="f1",
        geometry_hash="gh1",
        issued_at="2026-11-27T12:00:00+00:00",
        knowledge_cutoff_time="2026-11-27T12:00:00+00:00",
        target_valid_time="2026-12-04T12:00:00+00:00",
        target_window_start="2026-12-02T00:00:00+00:00",
        target_window_end="2026-12-06T23:59:59+00:00",
        horizon_days=7,
        model_version="v5",
        calibration_version="cal_v10",
        state_schema_version="s13",
        input_manifest_hash="m" * 64,
        observation_lineage_hash="o" * 64,
        crop_chronology_hash="c" * 64,
        weather_lineage_hash="w" * 64,
        specialist_config_hash="sp" * 32,
        complete_model_state={"state_means": {"vigor": 0.6}},
        crop_posterior={"crop": "citrus"},
        weather_forecast={"t_max": 22.0},
        channel_calibration={"ndvi": {"slope": 1.0, "bias": 0.0}},
        specialist_outputs={"water_stress": 0.1},
        bma_weights={"asmae_causal_calibrated": 1.0},
        predicted_channels={"ndvi": {"mean": 0.62, "sigma": 0.06, "y_pers": 0.58}},
    )
    assert len(iss.record_sha256) == 64

    with pytest.raises(ImmutableIssuanceError):
        ledger.record_forecast_issuance(
            forecast_id="fc_001",
            plot_id="p1",
            tenant_id="t1",
            farm_id="f1",
            geometry_hash="gh1",
            issued_at="2026-11-27T12:00:00+00:00",
            knowledge_cutoff_time="2026-11-27T12:00:00+00:00",
            target_valid_time="2026-12-04T12:00:00+00:00",
            target_window_start="2026-12-02T00:00:00+00:00",
            target_window_end="2026-12-06T23:59:59+00:00",
            horizon_days=7,
            model_version="v5",
            calibration_version="cal_v10",
            state_schema_version="s13",
            input_manifest_hash="m" * 64,
            observation_lineage_hash="o" * 64,
            crop_chronology_hash="c" * 64,
            weather_lineage_hash="w" * 64,
            specialist_config_hash="sp" * 32,
            complete_model_state={"state_means": {"vigor": 0.6}},
            crop_posterior={"crop": "citrus"},
            weather_forecast={"t_max": 22.0},
            channel_calibration={"ndvi": {"slope": 1.0, "bias": 0.0}},
            specialist_outputs={"water_stress": 0.1},
            bma_weights={"asmae_causal_calibrated": 1.0},
            predicted_channels={"ndvi": {"mean": 0.62, "sigma": 0.06, "y_pers": 0.58}},
        )

    # Rejects pre-issuance committed observation (retroactive leakage)
    with pytest.raises(RetroactiveOutcomeViolation):
        ledger.attach_realized_observation(
            forecast_id="fc_001",
            plot_id="p1",
            tenant_id="t1",
            channel="ndvi",
            observed_at="2026-12-04T10:30:00+00:00",
            obs_committed_at="2026-11-26T00:00:00+00:00",
            observation_content_hash="obs_hash_1",
            y_obs=0.61,
        )

    rec = ledger.attach_realized_observation(
        forecast_id="fc_001",
        plot_id="p1",
        tenant_id="t1",
        channel="ndvi",
        observed_at="2026-12-04T10:30:00+00:00",
        obs_committed_at="2026-12-04T18:00:00+00:00",
        observation_content_hash="obs_hash_1",
        y_obs=0.61,
    )
    assert rec.within_1sigma is True
    with pytest.raises(ImmutableScoreError):
        ledger.attach_realized_observation(
            forecast_id="fc_001",
            plot_id="p1",
            tenant_id="t1",
            channel="ndvi",
            observed_at="2026-12-04T10:30:00+00:00",
            obs_committed_at="2026-12-04T18:00:00+00:00",
            observation_content_hash="obs_hash_1",
            y_obs=0.61,
        )

    summary = ledger.summarize(plot_id="p1", tenant_id="t1")
    assert summary["chain_integrity_valid"] is True
    assert summary["scored_forecast_count"] == 1
    assert summary["pending_issuance_count"] == 0
    assert summary["aggregate_prospective_metrics"]["mse_skill_vs_persistence"] > 0.8

    # Tampering issuance breaks verification
    iss_path = ledger._issuance_path(plot_id="p1", tenant_id="t1")
    orig_txt = iss_path.read_text(encoding="utf-8")
    iss_path.write_text(orig_txt.replace('"vigor":0.6', '"vigor":0.99'), encoding="utf-8")
    with pytest.raises(IntegrityTamperError):
        ledger.verify_chain_integrity(plot_id="p1", tenant_id="t1")

    # V3 LOOCV crop-group calibration stays withheld without confirmed labels
    unconf_cal = evaluate_cross_validated_crop_calibration([
        {"plot_id": "p1", "label_confirmed": False, "true_crop_group": "orchard", "raw_broad_group_probs": {"orchard": 0.9, "cereal": 0.05, "vegetable": 0.03, "legume_fodder": 0.01, "unknown": 0.01}},
        {"plot_id": "p2", "label_confirmed": False, "true_crop_group": "cereal", "raw_broad_group_probs": {"cereal": 0.9, "orchard": 0.05, "vegetable": 0.03, "legume_fodder": 0.01, "unknown": 0.01}},
    ])
    assert unconf_cal["status"] == "withheld_insufficient_confirmed_labels"
    assert unconf_cal["calibrated_production_eligible"] is False

    conf_seasons = [
        {"plot_id": f"p{i}", "label_confirmed": True, "true_crop_group": "orchard" if i % 2 == 0 else "cereal", "raw_broad_group_probs": {"orchard": 0.92 if i % 2 == 0 else 0.03, "cereal": 0.03 if i % 2 == 0 else 0.92, "vegetable": 0.02, "legume_fodder": 0.02, "unknown": 0.01}}
        for i in range(6)
    ]
    conf_cal = evaluate_cross_validated_crop_calibration(conf_seasons)
    assert conf_cal["status"] == "calibrated_verified_out_of_fold"
    assert conf_cal["calibrated_production_eligible"] is True

