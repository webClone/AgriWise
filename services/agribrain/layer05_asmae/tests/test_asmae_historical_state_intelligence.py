"""Comprehensive verification suite for Historical State Intelligence & Safeguard B.

Tests:
  1. Safeguard B: ArchiveBootstrapService emits OBSERVATION_QUALIFIED only;
     ARCHIVE_POSTERIOR_VALIDATED is issued only after chronological ASMAE assimilation.
  2. Incremental 13-state posterior continuity vs cold full-history reconstruction
     (13 state means, stds, 13x13 covariance, model versions, ordering, causal forecasts).
  3. Non-destructive late-arrival replay: a 2020 observation arriving in 2026 triggers
     checkpoint replay from before 2020 without mutating previously published 2026 records,
     preserving bitemporal K1/K2 history and matching cold combined reconstruction.
  4. Event memory epistemic separation (observed_event vs model_hypothesis) & outcome scoring.
  5. Retrovalidation causal BMA vs Persistence / DOY Climatology / Trend, PIT/CRPS calibration,
     and seasonal skill scorecard with production-promotion quarantine.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pytest

from services.agribrain.layer0.archive.raster_store import RasterStore
from services.agribrain.layer0.asmae_scene_products.scene_product_store import SceneProductStore
from services.agribrain.layer05_asmae.config import N_STATES, STATE_NAMES, STATE_SCHEMA_VERSION
from services.agribrain.layer05_asmae.history.archive_bootstrap_service import ArchiveBootstrapService
from services.agribrain.layer05_asmae.history.historical_event_memory import HistoricalEventMemory
from services.agribrain.layer05_asmae.history.historical_retrovalidation import HistoricalRetrovalidator
from services.agribrain.layer05_asmae.history.historical_state_intelligence import (
    HistoricalStateIntelligenceService,
)
from services.agribrain.layer05_asmae.history.historical_state_reconstructor import (
    CALIBRATION_VERSION,
    HistoricalStateReconstructor,
    RECONSTRUCTOR_MODEL_VERSION,
)
from services.agribrain.world_model.canonical_worldline import CanonicalWorldlineService


def _build_synthetic_weather(start_year: int, end_year: int) -> Dict[str, Dict[str, Any]]:
    """Build multi-year deterministic weather dict with seasonal rain & dry summer intervals."""
    weather: Dict[str, Dict[str, Any]] = {}
    cur = datetime(start_year, 1, 1, tzinfo=timezone.utc).date()
    end = datetime(end_year, 12, 31, tzinfo=timezone.utc).date()
    while cur <= end:
        doy = cur.timetuple().tm_yday
        # Wet pulse around DOY 60 and 300; dry deficit June-August (DOY 160-220)
        precip = 22.0 if doy in (60, 120, 300) else (4.0 if doy % 25 == 0 and not (160 <= doy <= 220) else 0.0)
        et0 = 5.4 if 150 <= doy <= 240 else 2.2
        t_max = 33.0 if 170 <= doy <= 230 else 19.0
        t_min = 19.0 if 170 <= doy <= 230 else 9.0
        # Leave explicit gap days cleanly (DOY 350..355 in alternating years)
        if not (cur.year % 2 == 1 and 350 <= doy <= 355):
            weather[cur.isoformat()] = {
                "temp_max": t_max,
                "temp_min": t_min,
                "precipitation": precip,
                "et0": et0,
            }
        cur += timedelta(days=1)
    return weather


def _commit_obs_sequence(
    wl: CanonicalWorldlineService,
    plot_id: str,
    geom_hash: str,
    scenes: List[Dict[str, Any]],
) -> List[str]:
    """Commit mock OBSERVATION_QUALIFIED events through ArchiveBootstrapService."""
    bs = ArchiveBootstrapService(
        worldline=wl,
        bootstrap_root=wl.root.parent / "bs_tmp",
        fetcher_factory=lambda s, e: [
            sc for sc in scenes
            if s[:10] <= sc["acquisition_time"][:10] < e[:10]
        ],
    )
    bs.run_bootstrap(
        plot_id=plot_id,
        geometry_hash=geom_hash,
        start_date=scenes[0]["acquisition_time"][:10] + "T00:00:00+00:00",
        target_end_date=(datetime.fromisoformat(scenes[-1]["acquisition_time"].replace("Z", "+00:00")) + timedelta(days=2)).isoformat(),
        window_days=3650,
    )
    return [ev["event_id"] for ev in wl.load_all_events(plot_id)]


def _make_seasonal_scenes(years: List[int]) -> List[Dict[str, Any]]:
    """Create multi-year S2 + S1 observation dicts with realistic phenological cycles."""
    scenes: List[Dict[str, Any]] = []
    for yr in years:
        # DOY offsets: winter bare, spring green-up, summer stress, autumn recovery
        points = [
            (25, "sentinel2", {"ndvi_mean": 0.24, "ndmi_mean": 0.05}),
            (65, "sentinel2", {"ndvi_mean": 0.42, "ndmi_mean": 0.14}),
            (72, "sentinel1", {"vv_mean_db": -11.5, "vh_mean_db": -18.5}),
            (110, "sentinel2", {"ndvi_mean": 0.68, "ndmi_mean": 0.24}),
            (150, "sentinel2", {"ndvi_mean": 0.72, "ndmi_mean": 0.22}),
            (185, "sentinel1", {"vv_mean_db": -14.2, "vh_mean_db": -20.8}),
            (195, "sentinel2", {"ndvi_mean": 0.56, "ndmi_mean": 0.10}),
            (202, "sentinel1", {"vv_mean_db": -11.2, "vh_mean_db": -17.9}),  # dry-period SAR spike
            (225, "sentinel2", {"ndvi_mean": 0.62, "ndmi_mean": 0.17}),
            (295, "sentinel2", {"ndvi_mean": 0.48, "ndmi_mean": 0.15}),
        ]
        for doy, src, metrics in points:
            dt = datetime(yr, 1, 1, 10, 30, tzinfo=timezone.utc) + timedelta(days=doy - 1)
            scenes.append({
                "scene_id": f"{src[:2].upper()}_{dt.strftime('%Y%m%d')}",
                "acquisition_time": dt.isoformat(),
                "source": src,
                "product_level": "L2A" if src == "sentinel2" else "GRD",
                "cloud_score": 0.05,
                "quality_score": 0.95,
                "valid_pixel_fraction": 0.96,
                "source_content_hash": f"{yr}_{doy:03d}_{src}".ljust(64, "0"),
                "metrics": dict(metrics),
            })
    return sorted(scenes, key=lambda s: s["acquisition_time"])


def test_safeguard_b_observation_qualified_never_claims_validated_posterior(tmp_path: Path):
    """Bootstrap writes OBSERVATION_QUALIFIED only; ARCHIVE_POSTERIOR_VALIDATED follows real assimilation."""
    wl = CanonicalWorldlineService(root=tmp_path / "wl", require_durable_anchor=False)
    plot_id = "afroun_test"
    geom_hash = "sha256:testgeom1234567890"
    scenes = _make_seasonal_scenes([2023, 2024])
    _commit_obs_sequence(wl, plot_id, geom_hash, scenes)

    events_before = wl.load_all_events(plot_id)
    assert len(events_before) == len(scenes)
    assert all(ev["event_type"] == "OBSERVATION_QUALIFIED" for ev in events_before)
    assert not any(
        ev["event_type"] in ("ARCHIVE_POSTERIOR_VALIDATED", "ARCHIVE_POSTERIOR_DIAGNOSTIC")
        for ev in events_before
    )
    assert events_before[0]["payload"]["observation_qualified"]["assimilated"] is False

    weather = _build_synthetic_weather(2023, 2024)
    svc = HistoricalStateIntelligenceService(
        worldline=wl,
        bootstrap_root=tmp_path / "bs",
        checkpoint_root=tmp_path / "cp",
        n_ensemble=12,
        checkpoint_stride=5,
    )
    res = svc.run_full_intelligence(
        plot_id=plot_id,
        geometry_hash=geom_hash,
        daily_weather=weather,
        skip_bootstrap=True,
        compare_ablation=False,
    )
    recon = res["reconstruction"]
    assert recon["status"] == "COMPLETED"
    assert recon["observation_count"] == len(scenes)
    assert len(recon["state_means"]) == N_STATES
    assert len(recon["state_covariance"]) == N_STATES
    assert len(recon["state_covariance"][0]) == N_STATES

    # Verify unsupported states remain withheld / non-assimilated
    ledger = recon["state_support_ledger"]
    for withheld_state in ("thermal_stress", "salinity_stress", "biotic_confounder_risk"):
        assert ledger[withheld_state]["accepted_update_count"] == 0
        assert ledger[withheld_state]["support_status"] == "unsupported"
        assert ledger[withheld_state]["spatial_support"] == "unavailable"
        assert ledger[withheld_state]["field_approval_eligible"] is False

    # Verify authority gating: VALIDATED only if qualification passes, else DIAGNOSTIC with block reasons
    expected_ev_type = "ARCHIVE_POSTERIOR_VALIDATED" if recon["qualification_passed"] else "ARCHIVE_POSTERIOR_DIAGNOSTIC"
    assert recon["worldline_posterior_event_type"] == expected_ev_type
    post_events = [ev for ev in wl.load_all_events(plot_id) if ev["event_type"] == expected_ev_type]
    assert len(post_events) == 1
    if not recon["qualification_passed"]:
        assert not [ev for ev in wl.load_all_events(plot_id) if ev["event_type"] == "ARCHIVE_POSTERIOR_VALIDATED"]
        assert len(recon["validation_block_reasons"]) > 0
    ap = post_events[0]["payload"]["archive_posterior"]
    assert ap["model_version"] == RECONSTRUCTOR_MODEL_VERSION
    assert ap["state_schema_version"] == STATE_SCHEMA_VERSION
    assert ap["calibration_version"] == CALIBRATION_VERSION
    assert ap["publication_authority"] == "DIAGNOSTIC_ONLY"
    assert ap["claims_numerical_authority"] is False
    assert ap["observation_count"] == len(scenes)
    assert set(ap["state_means"].keys()) == set(STATE_NAMES)


def test_incremental_13_state_equivalence_vs_cold_full_history(tmp_path: Path):
    """Incremental resume across checkpoints matches cold full-history 13-state posterior distribution."""
    plot_id = "afroun_eq"
    geom_hash = "sha256:eq_geom_0011223344"
    scenes = _make_seasonal_scenes([2022, 2023, 2024])
    weather = _build_synthetic_weather(2022, 2024)

    # 1. Incremental worldline: first commit 2022-2023, reconstruct, then add 2024 and resume
    wl_inc = CanonicalWorldlineService(root=tmp_path / "wl_inc", require_durable_anchor=False)
    bs_inc = ArchiveBootstrapService(
        worldline=wl_inc,
        bootstrap_root=tmp_path / "bs_inc",
        fetcher_factory=lambda s, e: [
            sc for sc in scenes
            if s[:10] <= sc["acquisition_time"][:10] < e[:10]
        ],
    )
    bs_inc.run_bootstrap(
        plot_id=plot_id, geometry_hash=geom_hash,
        start_date="2022-01-01T00:00:00+00:00", target_end_date="2024-01-01T00:00:00+00:00", window_days=365,
    )

    svc_inc = HistoricalStateIntelligenceService(
        worldline=wl_inc, bootstrap_root=tmp_path / "bs_inc", checkpoint_root=tmp_path / "cp_inc",
        n_ensemble=14, checkpoint_stride=8,
    )
    res_part1 = svc_inc.run_full_intelligence(
        plot_id=plot_id, geometry_hash=geom_hash,
        valid_time_T="2024-01-01T00:00:00+00:00", daily_weather=weather, skip_bootstrap=True,
    )
    assert res_part1["reconstruction"]["mode"] == "cold_full_reconstruction"
    assert res_part1["reconstruction"]["observation_count"] == 20

    # Extend observations through end of 2024 and resume from stored checkpoint
    bs_inc.run_bootstrap(
        plot_id=plot_id, geometry_hash=geom_hash,
        start_date="2022-01-01T00:00:00+00:00", target_end_date="2024-12-31T00:00:00+00:00", window_days=365,
    )
    res_inc = svc_inc.run_full_intelligence(
        plot_id=plot_id, geometry_hash=geom_hash,
        valid_time_T="2024-12-31T00:00:00+00:00", daily_weather=weather, skip_bootstrap=True,
    )
    r_inc = res_inc["reconstruction"]
    assert r_inc["mode"] == "incremental_continuation"
    assert r_inc["resumed_from_checkpoint_id"] == res_part1["reconstruction"]["tail_checkpoint_id"]
    assert r_inc["newly_assimilated_count"] == 10
    assert r_inc["observation_count"] == 30

    # 2. Cold full-history run across all 2022-2024 observations
    wl_cold = CanonicalWorldlineService(root=tmp_path / "wl_cold", require_durable_anchor=False)
    _commit_obs_sequence(wl_cold, plot_id, geom_hash, scenes)
    svc_cold = HistoricalStateIntelligenceService(
        worldline=wl_cold, bootstrap_root=tmp_path / "bs_cold", checkpoint_root=tmp_path / "cp_cold",
        n_ensemble=14, checkpoint_stride=8,
    )
    r_cold = svc_cold.run_full_intelligence(
        plot_id=plot_id, geometry_hash=geom_hash,
        valid_time_T="2024-12-31T00:00:00+00:00", daily_weather=weather, skip_bootstrap=True,
    )["reconstruction"]

    # Exact equivalence across 13-state means, stds, 13x13 covariance, versions, event order, and forecasts!
    assert r_inc["model_version"] == r_cold["model_version"]
    assert r_inc["state_schema_version"] == r_cold["state_schema_version"]
    assert r_inc["calibration_version"] == r_cold["calibration_version"]

    for name in STATE_NAMES:
        assert r_inc["state_means"][name] == pytest.approx(r_cold["state_means"][name], abs=1e-6)
        assert r_inc["state_stds"][name] == pytest.approx(r_cold["state_stds"][name], abs=1e-6)

    np.testing.assert_allclose(
        np.asarray(r_inc["state_covariance"]),
        np.asarray(r_cold["state_covariance"]),
        atol=1e-6,
    )

    assert [s["scene_id"] for s in r_inc["trajectory"]] == [s["scene_id"] for s in r_cold["trajectory"]]
    for s_i, s_c in zip(r_inc["trajectory"], r_cold["trajectory"]):
        assert s_i["prior_predictions"] == s_c["prior_predictions"]

    assert r_inc["retrovalidation"]["summary"] == r_cold["retrovalidation"]["summary"]
    assert r_inc["retrovalidation"]["bma"]["weights"] == r_cold["retrovalidation"]["bma"]["weights"]


def test_late_arrival_2020_after_2026_publication_non_destructive_replay(tmp_path: Path):
    """Late-arriving 2020 observation after 2026 posterior triggers anchor replay without rewriting 2026 publication."""
    plot_id = "afroun_late"
    geom_hash = "sha256:late_geom_998877"
    scenes_all = _make_seasonal_scenes([2019, 2020, 2021, 2026])
    weather = _build_synthetic_weather(2019, 2026)

    # Identify one mid-2020 observation to withhold initially and inject late
    late_scene = copy.deepcopy([s for s in scenes_all if s["acquisition_time"].startswith("2020-07")][0])
    # Slightly perturb late observation so 2020 posterior measurably reflects its inclusion
    late_scene["metrics"] = {"vv_mean_db": -8.2, "vh_mean_db": -16.1}
    initial_scenes = [s for s in scenes_all if s["scene_id"] != late_scene["scene_id"]]

    wl = CanonicalWorldlineService(root=tmp_path / "wl", require_durable_anchor=False)
    for sc in initial_scenes:
        _commit_obs_sequence_single = wl.load_all_events(plot_id)
        prev = _commit_obs_sequence_single[-1]["event_id"] if _commit_obs_sequence_single else None
        bs = ArchiveBootstrapService(worldline=wl, bootstrap_root=tmp_path / "bs")
        bs._commit_scene_to_worldline(plot_id, geom_hash, "default_tenant", "default", sc, prev)

    recon_svc = HistoricalStateReconstructor(
        worldline=wl, checkpoint_root=tmp_path / "cp", n_ensemble=12, checkpoint_stride=10
    )
    k1 = datetime.now(timezone.utc).isoformat()
    res_v1 = recon_svc.reconstruct(
        plot_id=plot_id, geometry_hash=geom_hash,
        valid_time_T="2026-12-31T00:00:00+00:00", knowledge_cutoff_K=k1, daily_weather=weather,
    )
    v1_event_id = res_v1["worldline_posterior_event_id"]
    v1_event_path = wl._event_path(plot_id, v1_event_id)
    v1_raw_bytes_before = v1_event_path.read_bytes()
    v1_tail_cp = res_v1["tail_checkpoint_id"]

    # Now in 2026 (committed_at K2 > K1), the missing 2020 acquisition finally arrives!
    prev_tail = wl.load_all_events(plot_id)[-1]["event_id"]
    bs_late = ArchiveBootstrapService(worldline=wl, bootstrap_root=tmp_path / "bs")
    late_ev_id = bs_late._commit_scene_to_worldline(
        plot_id, geom_hash, "default_tenant", "default", late_scene, prev_tail
    )
    assert late_ev_id is not None

    k2 = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
    res_v2 = recon_svc.reconstruct(
        plot_id=plot_id, geometry_hash=geom_hash,
        valid_time_T="2026-12-31T00:00:00+00:00", knowledge_cutoff_K=k2, daily_weather=weather,
    )
    assert res_v2["mode"] == "late_arrival_replay"
    assert late_ev_id in res_v2["late_arrival_event_ids"]
    # Must anchor before the 2020 late observation rather than blindly appending at 2026 tail
    assert res_v2["resumed_from_checkpoint_id"] is not None
    assert res_v2["resumed_from_checkpoint_id"] != v1_tail_cp
    assert v1_tail_cp in res_v2["superseded_checkpoint_ids"]

    # Prior 2026 published worldline event & checkpoint remain byte-for-byte unmutated
    assert v1_event_path.read_bytes() == v1_raw_bytes_before
    assert recon_svc.load_checkpoint(plot_id, v1_tail_cp) is not None

    # New superseding ARCHIVE_POSTERIOR_VALIDATED committed with explicit lineage
    v2_event_id = res_v2["worldline_posterior_event_id"]
    assert v2_event_id != v1_event_id
    v2_rec = wl.load_event(plot_id, v2_event_id)
    assert v2_rec["payload"]["archive_posterior"]["supersedes_event_id"] == v1_event_id
    assert v2_rec["payload"]["archive_posterior"]["prior_publication_preserved"] is True

    # Re-querying as-of K1 before late arrival still omits late_ev_id cleanly
    obs_at_k1 = recon_svc.load_qualified_observations(
        plot_id=plot_id, valid_time_T="2026-12-31T00:00:00+00:00", knowledge_cutoff_K=k1,
    )
    assert late_ev_id not in [e["event_id"] for e in obs_at_k1]

    # Compare K2 late-arrival replay against cold reconstruction over all scenes (including late_scene)
    wl_cold = CanonicalWorldlineService(root=tmp_path / "wl_cold", require_durable_anchor=False)
    combined_sorted = sorted(initial_scenes + [late_scene], key=lambda s: s["acquisition_time"])
    _commit_obs_sequence(wl_cold, plot_id, geom_hash, combined_sorted)
    recon_cold = HistoricalStateReconstructor(
        worldline=wl_cold, checkpoint_root=tmp_path / "cp_cold", n_ensemble=12, checkpoint_stride=10
    )
    res_cold = recon_cold.reconstruct(
        plot_id=plot_id, geometry_hash=geom_hash,
        valid_time_T="2026-12-31T00:00:00+00:00", daily_weather=weather,
    )
    for name in STATE_NAMES:
        assert res_v2["state_means"][name] == pytest.approx(res_cold["state_means"][name], abs=1e-6)


def test_event_memory_separates_observed_from_hypotheses_and_measures_outcomes():
    """Verify event reconstruction separates observed triggers from hypotheses and scores outcomes."""
    base = datetime(2024, 3, 1, 10, 30, tzinfo=timezone.utc)
    weather: Dict[str, Dict[str, Any]] = {}
    for d in range(95):
        day = (base + timedelta(days=d)).strftime("%Y-%m-%d")
        precip = 24.0 if d == 10 else 0.0
        et0 = 5.0 if 30 <= d <= 55 else 2.5
        weather[day] = {"temp_max": 28.0, "temp_min": 14.0, "precipitation": precip, "et0": et0}

    def _step(d: int, src: str, vigor: float, cw: float, rzw: float, bs: float, sm: float, **metrics) -> Dict[str, Any]:
        return {
            "step_index": d,
            "acquisition_time": (base + timedelta(days=d)).isoformat(),
            "source": src,
            "obs_channels": {"ndvi": vigor} if src == "sentinel2" else {"sar_vv": 0.45},
            "raw_metrics": metrics,
            "posterior_state_means": {
                "vigor": vigor, "lai": vigor * 4.0, "canopy_water": cw, "root_zone_water": rzw,
                "surface_wetness_event": 0.55 if metrics.get("vv_mean_db", -14.0) > -11.5 else 0.15,
                "bare_soil_fraction": bs, "stress_memory": sm,
            },
        }

    trajectory = [
        _step(2, "sentinel2", 0.25, 0.22, 0.24, 0.55, 0.05, ndvi_mean=0.25),
        _step(8, "sentinel2", 0.41, 0.30, 0.26, 0.35, 0.04, ndvi_mean=0.41),      # emergence + canopy flush hypothesis -> positive followup
        _step(14, "sentinel2", 0.50, 0.36, 0.31, 0.28, 0.03, ndvi_mean=0.50),
        _step(25, "sentinel1", 0.48, 0.31, 0.22, 0.30, 0.10, vv_mean_db=-14.5),
        _step(35, "sentinel2", 0.42, 0.24, 0.18, 0.34, 0.48, ndvi_mean=0.42),      # stress regime
        _step(42, "sentinel1", 0.43, 0.26, 0.25, 0.33, 0.38, vv_mean_db=-11.0),   # candidate irrigation hypothesis (dry weather!) -> rebound
        _step(52, "sentinel2", 0.52, 0.33, 0.27, 0.25, 0.15, ndvi_mean=0.52),      # recovery + positive outcome
        _step(65, "sentinel2", 0.55, 0.34, 0.28, 0.22, 0.10, ndvi_mean=0.55),
    ]
    mgmt = [{"event_type": "planting", "status": "applied", "date": (base + timedelta(days=1)).strftime("%Y-%m-%d")}]

    mem = HistoricalEventMemory().reconstruct_memory(
        trajectory, {"daily_weather": weather, "management_events": mgmt}
    )
    evs = mem["events"]
    cats = {e["event_category"] for e in evs}
    assert {"rainfall_forcing", "planting_emergence", "candidate_irrigation", "canopy_change", "stress_onset", "recovery"} <= cats

    rain_evs = [e for e in evs if e["event_category"] == "rainfall_forcing"]
    plant_evs = [e for e in evs if e["event_category"] == "planting_emergence"]
    cand_irrig = [e for e in evs if e["event_category"] == "candidate_irrigation"]
    assert all(e["epistemic_class"] == "meteorological_forcing_reanalysis" for e in rain_evs)
    assert any(
        e["epistemic_class"] == "agronomic_event_confirmed"
        and e.get("trigger_evidence", {}).get("source") == "management_log"
        for e in plant_evs
    )
    assert all(e["epistemic_class"] == "model_hypothesis" for e in cand_irrig)
    assert cand_irrig[0]["hypothesis_status"] == "consistent_with_followup"
    assert abs(sum(cand_irrig[0]["competing_explanations"].values()) - 1.0) < 0.02
    om = cand_irrig[0]["outcome_measurement"]
    assert om["outcome_epistemic_class"] == "subsequent_outcome"
    assert om["consistency_is_not_proof"] is True
    assert "independent_observation_outcome" in om
    assert "model_state_inferred_outcome" in om
    assert om["independent_observation_outcome"]["delta_obs_ndvi"] > 0


def test_retrovalidation_bma_baselines_calibration_and_seasonal_scorecard(tmp_path: Path):
    """Retrovalidator scores BMA vs baselines, DOY climatology strict causality, PIT/CRPS, and yearly skills."""
    wl = CanonicalWorldlineService(root=tmp_path / "wl", require_durable_anchor=False)
    plot_id = "afroun_retro"
    geom_hash = "sha256:retro_geom"
    scenes = _make_seasonal_scenes([2019, 2020, 2021, 2022])
    weather = _build_synthetic_weather(2019, 2022)
    _commit_obs_sequence(wl, plot_id, geom_hash, scenes)

    svc = HistoricalStateIntelligenceService(
        worldline=wl, bootstrap_root=tmp_path / "bs", checkpoint_root=tmp_path / "cp", n_ensemble=15
    )
    recon = svc.run_full_intelligence(
        plot_id=plot_id, geometry_hash=geom_hash, daily_weather=weather, skip_bootstrap=True
    )["reconstruction"]
    retro = recon["retrovalidation"]
    assert retro["status"] == "evaluated"

    # DOY climatology must be absent in first year (2019) to prove zero future leakage
    scorecard = {row["season_year"]: row for row in retro["seasonal_scorecard"]}
    assert set(scorecard.keys()) == {2019, 2020, 2021, 2022}
    assert scorecard[2019]["climatology_rmse"] is None
    assert scorecard[2020]["climatology_rmse"] is not None

    # Uncertainty calibration & forecast skill fields present & finite
    summary = retro["summary"]
    assert 0.0 <= summary["coverage_1sigma"] <= 1.0
    assert 0.0 <= summary["coverage_2sigma"] <= 1.0
    assert 0.0 <= summary["mean_pit"] <= 1.0
    assert summary["mean_crps"] >= 0.0
    assert summary["skill_vs_persistence"] is not None

    # BMA weights remain quarantined diagnostic-only
    bma = retro["bma"]
    assert bma["archive_bma_status"] == "diagnostic"
    assert bma["can_promote_to_production"] is False
    assert abs(sum(bma["weights"].values()) - 1.0) < 1e-4
    assert {"persistence", "doy_climatology", "damped_linear_trend", "asmae_enkf", "bma_consensus"} <= set(retro["baselines"].keys())
    assert "multi_horizon" in retro and "qualification" in retro


def test_authority_gating_never_validates_without_retrovalidation_or_skill(tmp_path: Path):
    """Safeguard B: without retrovalidation or when skill/calibration fails, NEVER emit ARCHIVE_POSTERIOR_VALIDATED."""
    wl = CanonicalWorldlineService(root=tmp_path / "wl_gate", require_durable_anchor=False)
    plot_id = "afroun_gate"
    geom_hash = "sha256:gate_geom"
    scenes = _make_seasonal_scenes([2022])
    _commit_obs_sequence(wl, plot_id, geom_hash, scenes)

    recon_svc = HistoricalStateReconstructor(
        worldline=wl, checkpoint_root=tmp_path / "cp_gate", n_ensemble=10, checkpoint_stride=5
    )
    res_no_retro = recon_svc.reconstruct(
        plot_id=plot_id,
        geometry_hash=geom_hash,
        daily_weather=_build_synthetic_weather(2022, 2022),
        retrovalidation_fn=None,
        emit_worldline_posterior=True,
    )
    assert res_no_retro["qualification_passed"] is False
    assert res_no_retro["worldline_posterior_event_type"] == "ARCHIVE_POSTERIOR_DIAGNOSTIC"
    assert "retrovalidation_not_executed" in res_no_retro["validation_block_reasons"]
    events = wl.load_all_events(plot_id)
    assert not any(ev["event_type"] == "ARCHIVE_POSTERIOR_VALIDATED" for ev in events)
    diag = [ev for ev in events if ev["event_type"] == "ARCHIVE_POSTERIOR_DIAGNOSTIC"]
    assert len(diag) == 1
    assert diag[0]["payload"]["archive_posterior"]["qualification_passed"] is False


def test_cross_layer_bridge_l2_l8_coupling_and_non_circularity(tmp_path: Path):
    """Cross-layer intelligence executes L2-L8 engines, preserves non-assimilable guard, and scores L2-8 vs S1/S2 ablation."""
    wl = CanonicalWorldlineService(root=tmp_path / "wl_cl", require_durable_anchor=False)
    plot_id = "afroun_cl"
    geom_hash = "sha256:cl_geom"
    scenes = _make_seasonal_scenes([2022, 2023])
    _commit_obs_sequence(wl, plot_id, geom_hash, scenes)

    svc = HistoricalStateIntelligenceService(
        worldline=wl, bootstrap_root=tmp_path / "bs_cl", checkpoint_root=tmp_path / "cp_cl", n_ensemble=10
    )
    res = svc.run_full_intelligence(
        plot_id=plot_id,
        geometry_hash=geom_hash,
        daily_weather=_build_synthetic_weather(2022, 2023),
        skip_bootstrap=True,
        use_cross_layer_priors=True,
        compare_ablation=True,
    )
    cl = res["cross_layer_intelligence"]
    assert cl["observation_role"] == "refined_specialist_output_non_assimilable"
    assert cl["eligible_for_asmae_assimilation"] is False
    assert len(cl["engines_executed"]) >= 25
    assert cl["layers_refined"]["layer8_constraints"]["is_constraint_only"] is True
    assert cl["layers_refined"]["layer8_constraints"]["never_physical_ground_truth"] is True
    assert cl["layers_refined"]["layer8_constraints"]["contains_recommendations"] is False
    assert "observation_type" in cl["next_best_observation"]

    abl = res["cross_layer_ablation"]
    assert abl["cross_layer_rmse"] is not None
    assert abl["s1_s2_only_rmse"] is not None
    assert abl["delta_rmse_cross_minus_s1s2"] is not None


def test_spatial_canonical_grid_reprojection_and_causal_time_travel(tmp_path: Path):
    """Multi-resolution SAFE rasters reproject onto one canonical parcel grid & query_as_of stays strictly causal."""
    plot_id = "afroun_spatial"
    geom_hash = "sha256:spatial_geom"
    poly = {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[2.6555, 36.5072], [2.6625, 36.5072], [2.6625, 36.5105], [2.6555, 36.5105], [2.6555, 36.5072]]],
        },
    }
    scenes_dir = tmp_path / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    store = SceneProductStore.__new__(SceneProductStore)
    store.plot_id = plot_id
    store.run_id = None
    store.provider_product_id = None
    store.base_dir = str(scenes_dir)
    store.raster_store = RasterStore()

    # Create 3 synthetic real-format .SAFE dirs with distinct raster dimensions (18x22 vs 24x28 vs 20x24)
    for idx, (day_iso, shape, ndvi_val, ndmi_val) in enumerate([
        ("2023-03-10T10:30:00+00:00", (18, 22), 0.45, 0.14),
        ("2023-06-15T10:30:00+00:00", (24, 28), 0.72, 0.25),
        ("2024-04-20T10:30:00+00:00", (20, 24), 0.64, 0.18),
    ]):
        sid = f"S2A_MSIL2A_{day_iso[:10].replace('-', '')}"
        sdir = scenes_dir / sid
        sdir.mkdir(parents=True, exist_ok=True)
        h, w = shape
        dx = (2.6625 - 2.6555) / w
        dy = (36.5105 - 36.5072) / h
        # Ramp across east-west columns so spatial pattern is non-flat
        col_ramp = np.linspace(-0.08, 0.08, w, dtype=np.float32)[None, :].repeat(h, axis=0)
        b04 = np.full((h, w), 0.08, dtype=np.float32)
        b08 = np.clip(b04 * (1.0 + ndvi_val + col_ramp) / np.maximum(0.1, 1.0 - (ndvi_val + col_ramp)), 0.05, 0.9).astype(np.float32)
        b11 = np.clip(b08 * (1.0 - ndmi_val) / np.maximum(0.1, 1.0 + ndmi_val), 0.05, 0.9).astype(np.float32)
        scl = np.full((h, w), 4, dtype=np.int16)
        store.raster_store.save_band(str(sdir / "B04.npz"), b04)
        store.raster_store.save_band(str(sdir / "B08.npz"), b08)
        store.raster_store.save_band(str(sdir / "B11.npz"), b11)
        store.raster_store.save_band(str(sdir / "SCL.npz"), scl)
        meta = {
            "scene_id": sid,
            "sensor": "sentinel2",
            "acquisition_datetime": day_iso,
            "crs": "EPSG:4326",
            "transform": [2.6555, dx, 0.0, 36.5105, 0.0, -dy],
            "width": w,
            "height": h,
        }
        (sdir / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")

    # Add 3 Sentinel-1 SAR .SAFE scenes (1 before 2023-07-01 cutoff, 2 in 2024 after cutoff)
    for s1_day, bias_db in [
        ("2023-06-20T17:30:00+00:00", 0.0),
        ("2024-05-10T17:30:00+00:00", -0.6),
        ("2024-06-15T17:30:00+00:00", -0.9),
    ]:
        s1_id = f"S1A_IW_GRDH_{s1_day[:10].replace('-', '')}"
        s1_dir = scenes_dir / s1_id
        s1_dir.mkdir(parents=True, exist_ok=True)
        h1, w1 = 22, 26
        dx1 = (2.6625 - 2.6555) / w1
        dy1 = (36.5105 - 36.5072) / h1
        row_ramp = np.linspace(-1.5, 1.5, h1, dtype=np.float32)[:, None].repeat(w1, axis=1)
        vv_db = (-12.5 + bias_db + row_ramp).astype(np.float32)
        vh_db = (-19.2 + bias_db + row_ramp * 0.7).astype(np.float32)
        store.raster_store.save_band(str(s1_dir / "VV.npz"), vv_db)
        store.raster_store.save_band(str(s1_dir / "VH.npz"), vh_db)
        (s1_dir / "metadata.json").write_text(json.dumps({
            "scene_id": s1_id,
            "sensor": "sentinel1",
            "acquisition_datetime": s1_day,
            "crs": "EPSG:4326",
            "transform": [2.6555, dx1, 0.0, 36.5105, 0.0, -dy1],
            "width": w1,
            "height": h1,
            "band_units": {"VV": "db", "VH": "db"},
        }), encoding="utf-8")

    wl = CanonicalWorldlineService(root=tmp_path / "wl_sp", require_durable_anchor=False)
    scene_records = []
    for sd in sorted(scenes_dir.iterdir()):
        meta = json.loads((sd / "metadata.json").read_text(encoding="utf-8"))
        if meta["sensor"] == "sentinel2":
            b04 = store.raster_store.load_band(str(sd / "B04.npz"))
            b08 = store.raster_store.load_band(str(sd / "B08.npz"))
            b11 = store.raster_store.load_band(str(sd / "B11.npz"))
            ndvi = (b08 - b04) / np.maximum(1e-6, b08 + b04)
            ndmi = (b08 - b11) / np.maximum(1e-6, b08 + b11)
            scene_records.append({
                "scene_id": meta["scene_id"],
                "acquisition_time": meta["acquisition_datetime"],
                "source": "sentinel2",
                "product_level": "L2A",
                "cloud_score": 0.02,
                "quality_score": 0.96,
                "valid_pixel_fraction": 0.98,
                "source_content_hash": f"sp_{meta['scene_id']}".ljust(64, "0"),
                "metrics": {"ndvi_mean": float(np.mean(ndvi)), "ndmi_mean": float(np.mean(ndmi))},
            })
        else:
            vv = store.raster_store.load_band(str(sd / "VV.npz"))
            vh = store.raster_store.load_band(str(sd / "VH.npz"))
            scene_records.append({
                "scene_id": meta["scene_id"],
                "acquisition_time": meta["acquisition_datetime"],
                "source": "sentinel1",
                "product_level": "GRD",
                "cloud_score": 0.0,
                "quality_score": 0.95,
                "valid_pixel_fraction": 0.98,
                "source_content_hash": f"sp_{meta['scene_id']}".ljust(64, "0"),
                "metrics": {"vv_mean_db": float(np.mean(vv)), "vh_mean_db": float(np.mean(vh))},
            })
    scene_records.sort(key=lambda r: r["acquisition_time"])
    _commit_obs_sequence(wl, plot_id, geom_hash, scene_records)

    recon = HistoricalStateReconstructor(
        worldline=wl, checkpoint_root=tmp_path / "cp_sp", scene_store=store, n_ensemble=10, checkpoint_stride=1
    )
    weather = _build_synthetic_weather(2023, 2024)
    res = recon.reconstruct(
        plot_id=plot_id, geometry_hash=geom_hash, daily_weather=weather, polygon_geojson=poly,
        retrovalidation_fn=None, emit_worldline_posterior=False,
    )
    assert res["has_spatial_observations"] is True
    assert res["spatial_surfaces_count"] >= 6

    # Time-travel query as of 2023-07-01 must NOT include 2024-04-20 observation (only 3 observations before cutoff)
    q = recon.query_as_of(
        plot_id=plot_id,
        geometry_hash=geom_hash,
        valid_time_T="2023-07-01T00:00:00+00:00",
        daily_weather=weather,
        polygon_geojson=poly,
    )
    assert q["available"] is True
    assert q["assimilated_observation_count"] == 3
    assert len(q["causal_forecasts"]) == 3
    # Explicit pre-ingest knowledge_cutoff_K must enforce strict bitemporal recorded_at gating
    q_early_k = recon.query_as_of(
        plot_id=plot_id,
        geometry_hash=geom_hash,
        valid_time_T="2023-07-01T00:00:00+00:00",
        knowledge_cutoff_K="2020-01-01T00:00:00+00:00",
        daily_weather=weather,
        polygon_geojson=poly,
    )
    assert q_early_k["available"] is False
    surf_types = {s["surface_type"] for s in q["spatial_surfaces"]}
    assert "ASMAE_VIGOR" in surf_types
    assert "ASMAE_THERMAL_STRESS" not in surf_types
    assert "ASMAE_SALINITY_STRESS" not in surf_types
    assert "ASMAE_BIOTIC_CONFOUNDER_RISK" not in surf_types
    # Every spatial surface grid matches one canonical grid shape and preserves uncertainty grid
    shapes = {(len(s["values"]), len(s["values"][0])) for s in q["spatial_surfaces"]}
    assert len(shapes) == 1
    assert all(len(s["uncertainty"]) == len(s["values"]) for s in q["spatial_surfaces"])
    assert q["cross_layer_intelligence"]["observation_role"] == "refined_specialist_output_non_assimilable"


def test_fastapi_historical_intelligence_endpoint_auth_and_tenant_isolation():
    """Verify /v2/plots/{plot_id}/historical-intelligence enforces plot/tenant scope and serves signed requests."""
    import uuid
    import time
    from fastapi.testclient import TestClient
    from services.agribrain.app.main import app
    from services.agribrain.app.internal_service_auth import compute_request_signature

    client = TestClient(app)

    def _signed_headers(plot_id: str, tenant_id: str, farm_id: str, header_plot: str = "", query_pairs=None):
        ts = str(int(time.time()))
        nonce = uuid.uuid4().hex
        p_hdr = header_plot or plot_id
        path = f"/v2/plots/{plot_id}/historical-intelligence"
        sig = compute_request_signature("GET", path, query_pairs or [], tenant_id, farm_id, p_hdr, b"", ts, nonce, "v1")
        return {
            "X-AgriBrain-Signature": sig,
            "X-AgriBrain-Timestamp": ts,
            "X-AgriBrain-Nonce": nonce,
            "X-AgriBrain-Key-Version": "v1",
            "X-Tenant-Id": tenant_id,
            "X-Farm-Id": farm_id,
            "X-Plot-Id": p_hdr,
        }

    # 1. Unknown uninitialized plot returns 404
    r404 = client.get(
        "/v2/plots/plot_uninitialized_xyz/historical-intelligence",
        headers=_signed_headers("plot_uninitialized_xyz", "t_demo", "f_demo"),
    )
    assert r404.status_code == 404

    # 2. Foreign tenant querying afroun must never see tenant 697ddd3bd4195b809226a67b observations
    r_foreign = client.get(
        "/v2/plots/6a09d9e91dd0c7ed6fce7d50/historical-intelligence?as_of=2026-09-01",
        headers=_signed_headers(
            "6a09d9e91dd0c7ed6fce7d50", "foreign_tenant_isolated", "69ad7b6f7e6843e8234afcf6",
            query_pairs=[("as_of", "2026-09-01")],
        ),
    )
    if r_foreign.status_code == 200:
        body = r_foreign.json()
        assert body["available"] is False
        assert body["assimilated_observation_count"] == 0
    else:
        assert r_foreign.status_code == 404

    # 3. Mismatched X-Plot-Id must return 403
    r403 = client.get(
        "/v2/plots/6a09d9e91dd0c7ed6fce7d50/historical-intelligence",
        headers=_signed_headers(
            "6a09d9e91dd0c7ed6fce7d50", "697ddd3bd4195b809226a67b", "69ad7b6f7e6843e8234afcf6",
            header_plot="other_plot_id",
        ),
    )
    assert r403.status_code == 403

    # 4. If afroun archive exists locally, verify 200 OK causal sub-slice scoping, spatial honesty & cache version key
    from pathlib import Path as _P
    afroun_rpt = (
        _P("services/agribrain/artifacts/archive_pilot_reports")
        / "697ddd3bd4195b809226a67b" / "69ad7b6f7e6843e8234afcf6" / "6a09d9e91dd0c7ed6fce7d50"
        / "historical_state_intelligence_summary.json"
    )
    if afroun_rpt.is_file():
        r2018 = client.get(
            "/v2/plots/6a09d9e91dd0c7ed6fce7d50/historical-intelligence?as_of=2018-07-15",
            headers=_signed_headers(
                "6a09d9e91dd0c7ed6fce7d50", "697ddd3bd4195b809226a67b", "69ad7b6f7e6843e8234afcf6",
                query_pairs=[("as_of", "2018-07-15")],
            ),
        )
        assert r2018.status_code == 200
        d18 = r2018.json()
        assert d18["available"] is True
        assert d18["assimilated_observation_count"] == 40
        assert d18["spatial_estimation_mode"] == "inferred_state_anomaly_field"
        import re as _re
        assert _re.match(
            r"^wl=\d+:[^|]+\|cp=[^|]+\|rpt=\d+(?:\|dom=\d+\|ldgr=[^|]+)?\|gh=",
            d18["archive_state_version"],
        )
        assert d18["temporal_query_scope"]["is_full_tail_epoch"] is False
        assert d18["cross_layer_ablation"] == {}
        assert d18["retrovalidation_summary"]["summary"]["n_evaluated_points"] < 90
        assert d18["worldline_authority"] == "ARCHIVE_POSTERIOR_DIAGNOSTIC"


def test_prospective_multi_horizon_zero_future_weather_or_sigma_leakage(tmp_path: Path):
    """Prospective multi-horizon scoring MUST NOT leak future ERA5 weather or target scene obs_sigma."""
    wl = CanonicalWorldlineService(root=tmp_path / "wl_prosp", require_durable_anchor=False)
    plot_id = "prosp_plot"
    geom_hash = "sha256:prosp_geom"
    scenes = _make_seasonal_scenes([2022, 2023, 2024, 2025])
    # Ensure a late-2025 pair lands inside (0.5d, 35d] right after 2025-10-22 (DOY 295)
    dt_nov = datetime(2025, 11, 12, 10, 30, tzinfo=timezone.utc)
    scenes.append({
        "scene_id": f"S2_{dt_nov.strftime('%Y%m%d')}",
        "acquisition_time": dt_nov.isoformat(),
        "source": "sentinel2",
        "product_level": "L2A",
        "cloud_score": 0.05,
        "quality_score": 0.95,
        "valid_pixel_fraction": 0.96,
        "source_content_hash": "2025_316_sentinel2".ljust(64, "0"),
        "metrics": {"ndvi_mean": 0.44, "ndmi_mean": 0.13},
    })
    scenes.sort(key=lambda s: s["acquisition_time"])
    weather_base = _build_synthetic_weather(2022, 2025)
    _commit_obs_sequence(wl, plot_id, geom_hash, scenes)

    recon = HistoricalStateReconstructor(
        worldline=wl, checkpoint_root=tmp_path / "cp_prosp", n_ensemble=10, checkpoint_stride=8
    )
    res_base = recon.reconstruct(
        plot_id=plot_id, geometry_hash=geom_hash, daily_weather=weather_base,
        retrovalidation_fn=None, emit_worldline_posterior=False,
    )
    traj_orig = copy.deepcopy(res_base["trajectory"])
    ctx_orig = {
        "plot_id": plot_id,
        "geometry_hash": geom_hash,
        "daily_weather": copy.deepcopy(weather_base),
        "crop_context": {"crop_type": "citrus", "crop_coefficient": 0.75},
        "soil_context": {},
    }
    eval_base = HistoricalRetrovalidator().evaluate(traj_orig, ctx_orig)
    mh_base = eval_base["multi_horizon"]
    assert mh_base["uses_realized_future_weather"] is False
    assert mh_base["uses_target_scene_obs_sigma"] is False

    # Mutate ONLY weather >= 2025-10-22 (same issuance day 10:30 UTC afternoon + future!) & mutate target scene obs_sigma
    weather_post = copy.deepcopy(weather_base)
    for d_key in list(weather_post.keys()):
        if d_key >= "2025-10-22":
            weather_post[d_key] = {"temp_max": 45.0, "temp_min": 30.0, "precipitation": 80.0, "et0": 12.0}
    traj_mut = copy.deepcopy(traj_orig)
    for step in traj_mut:
        if str(step.get("acquisition_time", "")).startswith("2025-"):
            for p_rec in (step.get("prior_predictions") or {}).values():
                p_rec["obs_sigma"] = 0.45

    eval_sigma_only = HistoricalRetrovalidator().evaluate(traj_mut, ctx_orig)
    assert eval_sigma_only["multi_horizon"]["by_horizon"] == mh_base["by_horizon"]
    assert eval_sigma_only["multi_horizon"]["by_heldout_year"] == mh_base["by_heldout_year"]

    eval_post = HistoricalRetrovalidator().evaluate(traj_orig, {**ctx_orig, "daily_weather": weather_post})
    assert eval_post["multi_horizon"]["by_horizon"] == mh_base["by_horizon"]
    assert eval_post["multi_horizon"]["hindcast_realized_weather_reference"]["by_horizon"] != mh_base["hindcast_realized_weather_reference"]["by_horizon"]


def test_strict_validation_gate_and_multi_crop_confirmed_events(tmp_path: Path):
    """P1-B gate rejects negative overall persistence skill; CrossLayer & EventMemory support olive/wheat + confirmed events."""
    from services.agribrain.layer05_asmae.cross_layer_intelligence import CrossLayerSpecialistBridge

    wl = CanonicalWorldlineService(root=tmp_path / "wl_strict", require_durable_anchor=False)
    plot_id = "olive_strict_plot"
    geom_hash = "sha256:olive_geom"
    scenes = _make_seasonal_scenes([2022, 2023])
    weather = _build_synthetic_weather(2022, 2023)
    _commit_obs_sequence(wl, plot_id, geom_hash, scenes)

    svc = HistoricalStateIntelligenceService(
        worldline=wl, bootstrap_root=tmp_path / "bs_s", checkpoint_root=tmp_path / "cp_s", n_ensemble=10
    )
    res = svc.run_full_intelligence(
        plot_id=plot_id,
        geometry_hash=geom_hash,
        daily_weather=weather,
        crop_context={"crop_type": "olive", "crop_coefficient": 0.65},
        management_events=[
            {"event_type": "irrigation", "status": "applied", "date": "2023-07-20", "amount_mm": 28.0},
            {"event_type": "harvest", "status": "applied", "date": "2023-10-15"},
        ],
        skip_bootstrap=True,
        compare_ablation=False,
    )
    recon = res["reconstruction"]
    qual = recon["retrovalidation"]["qualification"]
    if not qual["passed"]:
        assert recon["worldline_posterior_event_type"] == "ARCHIVE_POSTERIOR_DIAGNOSTIC"
        assert qual["qualification_tier"] == "DIAGNOSTIC_HISTORICAL_RECONSTRUCTION"
    assert recon["event_memory"]["summary"]["agronomic_event_confirmed_count"] >= 2
    confirmed_evs = [
        e for e in recon["event_memory"]["events"]
        if e["epistemic_class"] == "agronomic_event_confirmed"
    ]
    assert any(e["event_category"] == "irrigation" for e in confirmed_evs)
    assert any(e["event_category"] == "canopy_change" for e in confirmed_evs)

    # Verify annual crop (wheat) L2-8 cross-layer bridge executes cleanly without errors
    bridge = CrossLayerSpecialistBridge()
    st = bridge.initialize_chrono_state(crop_context={"crop_type": "wheat"})
    bridge.advance_chrono_state(
        st,
        start_time=datetime(2023, 3, 1, tzinfo=timezone.utc),
        end_time=datetime(2023, 4, 15, tzinfo=timezone.utc),
        weather_daily_series=weather,
        crop_context={"crop_type": "wheat"},
    )
    pre_w = bridge.evaluate_step_priors(
        state=st,
        timestamp=datetime(2023, 4, 15, 10, tzinfo=timezone.utc),
        knowledge_cutoff=datetime(2023, 4, 15, 10, tzinfo=timezone.utc),
        crop_context={"crop_type": "wheat"},
    )
    assert pre_w["priors"]["layer2"]["phenology_stage"]
    assert pre_w["priors"]["layer3"]["et0"] >= 0.0


def test_issuance_day_complete_daily_weather_strict_d_minus_1_cutoff():
    """build_prospective_weather_series excludes full daily summary on issuance date unless >=23:59 or timestamped <= issue_dt."""
    from services.agribrain.layer05_asmae.history.historical_state_reconstructor import build_prospective_weather_series

    dw = {
        "2025-05-08": {"temp_max": 24.0, "temp_min": 13.0, "precipitation": 0.0, "et0": 3.5},
        "2025-05-09": {"temp_max": 25.0, "temp_min": 14.0, "precipitation": 0.0, "et0": 3.8},
        "2025-05-10": {"temp_max": 49.0, "temp_min": 28.0, "precipitation": 88.0, "et0": 14.0},
        "2025-05-11": {"temp_max": 48.0, "temp_min": 27.0, "precipitation": 50.0, "et0": 12.0},
    }
    issue_dt = datetime(2025, 5, 10, 10, 30, tzinfo=timezone.utc)
    end_dt = datetime(2025, 5, 14, 10, 30, tzinfo=timezone.utc)

    pw = build_prospective_weather_series(dw, issue_dt, end_dt)
    assert pw["2025-05-09"]["temp_max"] == 25.0
    # Same-day un-timestamped ERA5 aggregate (afternoon peak/storm) MUST be replaced by causal climatology
    assert pw["2025-05-10"]["temp_max"] < 30.0
    assert pw["2025-05-10"]["precipitation"] == 0.0
    assert pw["2025-05-10"].get("source_role") == "causal_doy_climatology_projection"
    assert pw["2025-05-11"]["temp_max"] < 30.0

    # Explicit observed_before <= issue_dt intraday reading IS permitted
    dw_ts = dict(dw)
    dw_ts["2025-05-10"] = {
        "temp_max": 21.5,
        "temp_min": 13.0,
        "precipitation": 1.2,
        "et0": 1.8,
        "observed_before": "2025-05-10T10:00:00+00:00",
    }
    pw_ts = build_prospective_weather_series(dw_ts, issue_dt, end_dt)
    assert pw_ts["2025-05-10"]["temp_max"] == 21.5


def test_strict_bitemporal_knowledge_cutoff_k_and_cache_invalidation_after_replay(tmp_path: Path):
    """P1-C + Bitemporal P1-D: K separates 2018-as-known-in-2018 vs 2018-with-today's-knowledge & invalidates cache after replay."""
    import uuid
    import time
    from fastapi.testclient import TestClient
    from services.agribrain.app.main import app
    from services.agribrain.app.internal_service_auth import compute_request_signature
    from services.agribrain.world_model.canonical_worldline import WorldlineEventProposal

    # Use isolated plot IDs and commit explicit historical committed_at timestamps
    from unittest.mock import patch

    def _commit_with_k(wl_svc: CanonicalWorldlineService, pid: str, ghash: str, recs: List[Dict[str, Any]], committed_at: str, tenant_id: str = "default_tenant") -> None:
        with patch("services.agribrain.world_model.canonical_worldline._now", lambda: committed_at):
            for sc in recs:
                p = WorldlineEventProposal(
                    event_type="OBSERVATION_QUALIFIED",
                    geometry_version=ghash[:16],
                    evidence_set_hash=str(sc["source_content_hash"])[:64].ljust(64, "0"),
                    payload={"observation_qualified": sc},
                    model_version="asmae_hist_obs_v1",
                    calibration_version="uncalibrated",
                    authority_contract_version="auth_v1",
                    authority_ref="test:k",
                    state_schema_version="asmae_state_v1_13",
                    observation_or_valid_time=sc["acquisition_time"],
                )
                wl_svc.commit_proposal(
                    plot_id=pid,
                    proposal=p,
                    tenant_id=tenant_id,
                    effective_at=sc["acquisition_time"],
                )

    wl = CanonicalWorldlineService(root=tmp_path / "wl_bi", require_durable_anchor=False)
    plot_id = "bitemp_test_plot"
    geom_hash = "sha256:bitemp_geom"
    weather = _build_synthetic_weather(2018, 2020)

    # Batch 1: 4 initial scenes committed in July 2018
    early_scenes = [
        {"scene_id": "S2_180401", "acquisition_time": "2018-04-01T10:30:00+00:00", "source": "sentinel2", "product_level": "L2A", "cloud_score": 0.05, "quality_score": 0.95, "valid_pixel_fraction": 0.98, "source_content_hash": "b1a".ljust(64, "0"), "metrics": {"ndvi_mean": 0.32, "ndmi_mean": 0.02}},
        {"scene_id": "S2_180501", "acquisition_time": "2018-05-01T10:30:00+00:00", "source": "sentinel2", "product_level": "L2A", "cloud_score": 0.05, "quality_score": 0.95, "valid_pixel_fraction": 0.98, "source_content_hash": "b1b".ljust(64, "0"), "metrics": {"ndvi_mean": 0.56, "ndmi_mean": 0.14}},
        {"scene_id": "S1_180601", "acquisition_time": "2018-06-01T17:44:00+00:00", "source": "sentinel1", "product_level": "GRD", "cloud_score": 0.0, "quality_score": 0.95, "valid_pixel_fraction": 0.99, "source_content_hash": "b1c".ljust(64, "0"), "metrics": {"vv_mean_db": -10.5, "vh_mean_db": -16.8}},
        {"scene_id": "S2_180710", "acquisition_time": "2018-07-10T10:30:00+00:00", "source": "sentinel2", "product_level": "L2A", "cloud_score": 0.05, "quality_score": 0.95, "valid_pixel_fraction": 0.98, "source_content_hash": "b1d".ljust(64, "0"), "metrics": {"ndvi_mean": 0.61, "ndmi_mean": 0.18}},
    ]
    _commit_with_k(wl, plot_id, geom_hash, early_scenes, committed_at="2018-07-12T00:00:00+00:00")

    # Batch 2: late-arriving 2018-06-20 scene committed in 2025 + future 2019-06-01 scene committed in 2019
    late_prop = WorldlineEventProposal(
        event_type="OBSERVATION_QUALIFIED",
        geometry_version=geom_hash[:16],
        evidence_set_hash="b2_late".ljust(64, "0"),
        payload={"observation_qualified": {"scene_id": "S2_180620_LATE", "acquisition_time": "2018-06-20T10:30:00+00:00", "source": "sentinel2", "product_level": "L2A", "cloud_score": 0.05, "quality_score": 0.95, "valid_pixel_fraction": 0.98, "source_content_hash": "b2late".ljust(64, "0"), "metrics": {"ndvi_mean": 0.19, "ndmi_mean": -0.15}}},
        model_version="asmae_hist_obs_v1",
        calibration_version="uncalibrated",
        authority_contract_version="auth_v1",
        authority_ref="test:late",
        state_schema_version="asmae_state_v1_13",
        observation_or_valid_time="2018-06-20T10:30:00+00:00",
    )
    with patch("services.agribrain.world_model.canonical_worldline._now", lambda: "2025-02-01T00:00:00+00:00"):
        wl.commit_proposal(plot_id=plot_id, proposal=late_prop, effective_at="2018-06-20T10:30:00+00:00")

    fut_prop = WorldlineEventProposal(
        event_type="OBSERVATION_QUALIFIED",
        geometry_version=geom_hash[:16],
        evidence_set_hash="b2_fut".ljust(64, "0"),
        payload={"observation_qualified": {"scene_id": "S2_190601_FUT", "acquisition_time": "2019-06-01T10:30:00+00:00", "source": "sentinel2", "product_level": "L2A", "cloud_score": 0.05, "quality_score": 0.95, "valid_pixel_fraction": 0.98, "source_content_hash": "b2fut".ljust(64, "0"), "metrics": {"ndvi_mean": 0.72, "ndmi_mean": 0.22}}},
        model_version="asmae_hist_obs_v1",
        calibration_version="uncalibrated",
        authority_contract_version="auth_v1",
        authority_ref="test:fut",
        state_schema_version="asmae_state_v1_13",
        observation_or_valid_time="2019-06-01T10:30:00+00:00",
    )
    with patch("services.agribrain.world_model.canonical_worldline._now", lambda: "2019-06-02T00:00:00+00:00"):
        wl.commit_proposal(plot_id=plot_id, proposal=fut_prop, effective_at="2019-06-01T10:30:00+00:00")

    recon = HistoricalStateReconstructor(worldline=wl, checkpoint_root=tmp_path / "cp_bi", n_ensemble=8, checkpoint_stride=4)
    q_k2018 = recon.query_as_of(
        plot_id=plot_id, geometry_hash=geom_hash,
        valid_time_T="2018-07-15T23:59:59+00:00", knowledge_cutoff_K="2018-07-15T23:59:59+00:00",
        daily_weather=weather,
    )
    q_know = recon.query_as_of(
        plot_id=plot_id, geometry_hash=geom_hash,
        valid_time_T="2018-07-15T23:59:59+00:00", knowledge_cutoff_K="2026-01-01T00:00:00+00:00",
        daily_weather=weather,
    )
    assert q_k2018["assimilated_observation_count"] == 4
    assert q_know["assimilated_observation_count"] == 5
    # available_dates must NOT leak 2019-06-01 or 2025 late arrival when K=2018-07-15
    assert "2019-06-01" not in q_k2018["available_dates"]
    assert "2018-06-20" not in q_k2018["available_dates"]
    assert "2018-06-20" in q_know["available_dates"]

    # Clean direct test on CanonicalWorldlineService + _HIST_INTEL_RESPONSE_CACHE key mutation after late arrival
    # Ensure report summary written for K=now does NOT leak late arrival into K=2018-07-15 API response!
    import services.agribrain.app.main as main_mod
    from unittest.mock import patch
    from services.agribrain.geometry_contract import compute_geometry_hash
    artifacts_mock = tmp_path / "app_art"
    client = TestClient(app)

    def _hdr(qp=None):
        ts = str(int(time.time())); nonce = uuid.uuid4().hex
        p = f"/v2/plots/{plot_id}/historical-intelligence"
        sig = compute_request_signature("GET", p, qp or [], "t_api", "f_api", plot_id, b"", ts, nonce, "v1")
        return {"X-AgriBrain-Signature": sig, "X-AgriBrain-Timestamp": ts, "X-AgriBrain-Nonce": nonce, "X-AgriBrain-Key-Version": "v1", "X-Tenant-Id": "t_api", "X-Farm-Id": "f_api", "X-Plot-Id": plot_id}

    poly_wkt = "POLYGON ((2.65 36.50, 2.66 36.50, 2.66 36.51, 2.65 36.51, 2.65 36.50))"
    from services.agribrain.scripts.run_archive_pilot import _wkt_to_geojson_and_centroid
    gj_test, _, _ = _wkt_to_geojson_and_centroid(poly_wkt)
    gh_test = compute_geometry_hash(gj_test)
    wl_api2 = CanonicalWorldlineService(root=artifacts_mock / "wl2", require_durable_anchor=False)
    _commit_with_k(wl_api2, plot_id, gh_test, early_scenes, committed_at="2018-07-12T00:00:00+00:00", tenant_id="t_api")
    late_prop_api = WorldlineEventProposal(
        event_type="OBSERVATION_QUALIFIED",
        geometry_version=gh_test[:16],
        evidence_set_hash="b2_late".ljust(64, "0"),
        payload=late_prop.payload,
        model_version="asmae_hist_obs_v1",
        calibration_version="uncalibrated",
        authority_contract_version="auth_v1",
        authority_ref="test:late",
        state_schema_version="asmae_state_v1_13",
        observation_or_valid_time="2018-06-20T10:30:00+00:00",
    )
    with patch("services.agribrain.world_model.canonical_worldline._now", lambda: "2025-02-01T00:00:00+00:00"):
        wl_api2.commit_proposal(plot_id=plot_id, proposal=late_prop_api, tenant_id="t_api", effective_at="2018-06-20T10:30:00+00:00")
    svc2 = HistoricalStateIntelligenceService(worldline=wl_api2, bootstrap_root=artifacts_mock / "bs2", checkpoint_root=artifacts_mock / "cp2", n_ensemble=8)
    full_rep = svc2.run_full_intelligence(plot_id=plot_id, geometry_hash=gh_test, tenant_id="t_api", daily_weather=weather, skip_bootstrap=True, compare_ablation=False)
    assert full_rep["reconstruction"]["observation_count"] == 5

    # Compare response scoping with K=2018 vs K=2026 on same T=2018-07-15
    orig_wl_init = CanonicalWorldlineService.__init__
    orig_recon_init = HistoricalStateReconstructor.__init__
    rpt_dir = Path("services/agribrain/artifacts/archive_pilot_reports/t_api/f_api") / plot_id
    # Use clean temp worldline root via env/patch of Path for historical_intelligence_worldlines
    main_mod._HIST_INTEL_RESPONSE_CACHE.clear()
    with patch.dict(main_mod.COHORT_GEOMETRIES if hasattr(main_mod, "COHORT_GEOMETRIES") else {}, {}, clear=False), \
         patch("services.agribrain.scripts.run_archive_pilot.COHORT_GEOMETRIES", {plot_id: poly_wkt}):
        rpt_dir.mkdir(parents=True, exist_ok=True)
        try:
            (rpt_dir / "historical_state_intelligence_summary.json").write_text(json.dumps({**full_rep, "plot_id": plot_id, "tenant_id": "t_api", "farm_id": "f_api", "geometry_hash": gh_test}, default=str), encoding="utf-8")
            (rpt_dir / "historical_weather_cache.json").write_text(json.dumps({"daily_weather": weather}), encoding="utf-8")
            with patch("services.agribrain.world_model.canonical_worldline.CanonicalWorldlineService.__init__", lambda self, root=None, require_durable_anchor=False, **kw: orig_wl_init(self, root=artifacts_mock / "wl2", require_durable_anchor=False)), \
                 patch("services.agribrain.layer05_asmae.history.historical_state_reconstructor.HistoricalStateReconstructor.__init__", lambda self, worldline=None, checkpoint_root=None, **kw: orig_recon_init(self, worldline=worldline, checkpoint_root=artifacts_mock / "cp2", **{k: v for k, v in kw.items() if k not in ("worldline", "checkpoint_root")})):
                rk18 = client.get(
                    f"/v2/plots/{plot_id}/historical-intelligence?as_of=2018-07-15&knowledge_cutoff=2018-07-15",
                    headers=_hdr([("as_of", "2018-07-15"), ("knowledge_cutoff", "2018-07-15")]),
                )
                rknow = client.get(
                    f"/v2/plots/{plot_id}/historical-intelligence?as_of=2018-07-15",
                    headers=_hdr([("as_of", "2018-07-15")]),
                )
                assert rk18.status_code == 200 and rknow.status_code == 200
                dk18 = rk18.json(); dknow = rknow.json()
                assert dk18["assimilated_observation_count"] == 4
                assert dknow["assimilated_observation_count"] == 5
                assert dk18["temporal_query_scope"]["has_explicit_knowledge_cutoff"] is True
                assert dk18["retrovalidation_summary"]["summary"]["n_evaluated_points"] < dknow["retrovalidation_summary"]["summary"]["n_evaluated_points"]
                assert dk18["manifest_reconciliation"]["admitted_unique_count"] == 4

                # Cache invalidation test after replay: commit one more event & inspect version + count change
                replay_prop = WorldlineEventProposal(
                    event_type="OBSERVATION_QUALIFIED",
                    geometry_version=gh_test[:16],
                    evidence_set_hash="b3_replay".ljust(64, "0"),
                    payload={"observation_qualified": {"scene_id": "S2_180714_RPL", "acquisition_time": "2018-07-14T10:30:00+00:00", "source": "sentinel2", "product_level": "L2A", "cloud_score": 0.05, "quality_score": 0.95, "valid_pixel_fraction": 0.98, "source_content_hash": "b3rpl".ljust(64, "0"), "metrics": {"ndvi_mean": 0.65, "ndmi_mean": 0.19}}},
                    model_version="asmae_hist_obs_v1",
                    calibration_version="uncalibrated",
                    authority_contract_version="auth_v1",
                    authority_ref="test:replay",
                    state_schema_version="asmae_state_v1_13",
                    observation_or_valid_time="2018-07-14T10:30:00+00:00",
                )
                with patch("services.agribrain.world_model.canonical_worldline._now", lambda: "2025-03-01T00:00:00+00:00"):
                    wl_api2.commit_proposal(plot_id=plot_id, proposal=replay_prop, tenant_id="t_api", effective_at="2018-07-14T10:30:00+00:00")
                r_after = client.get(
                    f"/v2/plots/{plot_id}/historical-intelligence?as_of=2018-07-15",
                    headers=_hdr([("as_of", "2018-07-15")]),
                )
                assert r_after.status_code == 200
                dafter = r_after.json()
                assert dafter["archive_state_version"] != dknow["archive_state_version"]
                assert dafter["assimilated_observation_count"] == 6
        finally:
            import shutil
            shutil.rmtree(rpt_dir, ignore_errors=True)
            shutil.rmtree(Path("services/agribrain/artifacts/archive_pilot_reports/t_api"), ignore_errors=True)
            main_mod._HIST_INTEL_RESPONSE_CACHE.clear()


def test_adaptive_state_dependent_spatial_resolution_and_sub_hectare_suppression():
    """Uniform 10m claim is replaced by state-dependent resolutions & coarse suppression on sub-hectare plots."""
    from services.agribrain.layer05_asmae.history.historical_state_reconstructor import build_canonical_parcel_grid
    import numpy as np

    # Large ~20ha polygon
    big_poly = {"type": "Polygon", "coordinates": [[[2.655, 36.507], [2.660, 36.507], [2.660, 36.511], [2.655, 36.511], [2.655, 36.507]]]}
    big_grid = build_canonical_parcel_grid(big_poly)
    H, W = int(big_grid["height"]), int(big_grid["width"])
    acc = {"vigor": 50, "canopy_water": 50, "structure": 40, "root_zone_water": 80, "lai": 50}
    rng = np.random.default_rng(7)
    sdelta = rng.normal(0.0, 0.05, size=(10, H, W)).astype(np.float32)
    svar = np.full((10, H, W), 0.01, dtype=np.float32)

    surfaces_big = HistoricalStateReconstructor.build_spatial_surfaces_payload(
        canonical_grid=big_grid,
        state_means={k: 0.5 for k in acc},
        state_stds={k: 0.05 for k in acc},
        accepted_counts=acc,
        spatial_delta=sdelta,
        spatial_var=svar,
        has_spatial_observations=True,
    )
    by_type = {s["surface_type"]: s for s in surfaces_big}
    assert by_type["ASMAE_VIGOR"]["effective_resolution_m"] == 10.0
    assert by_type["ASMAE_CANOPY_WATER"]["effective_resolution_m"] == 20.0
    assert by_type["ASMAE_STRUCTURE"]["effective_resolution_m"] == 30.0
    assert by_type["ASMAE_ROOT_ZONE_WATER"]["effective_resolution_m"] == 40.0
    assert all(not s["certified_1m"] for s in surfaces_big)
    assert len({s["effective_resolution_m"] for s in surfaces_big}) >= 4

    # Sub-hectare ~0.3ha plot (~30 10m cells) -> 40m root_zone_water (<3 indep cells) MUST be suppressed
    tiny_poly = {"type": "Polygon", "coordinates": [[[5.7160, 34.8294], [5.7166, 34.8294], [5.7166, 34.8299], [5.7160, 34.8299], [5.7160, 34.8294]]]}
    tiny_grid = build_canonical_parcel_grid(tiny_poly)
    Ht, Wt = int(tiny_grid["height"]), int(tiny_grid["width"])
    surfaces_tiny = HistoricalStateReconstructor.build_spatial_surfaces_payload(
        canonical_grid=tiny_grid,
        state_means={k: 0.5 for k in acc},
        state_stds={k: 0.05 for k in acc},
        accepted_counts=acc,
        spatial_delta=np.zeros((10, Ht, Wt), dtype=np.float32),
        spatial_var=np.full((10, Ht, Wt), 0.01, dtype=np.float32),
        has_spatial_observations=True,
    )
    tiny_types = {s["surface_type"] for s in surfaces_tiny}
    assert "ASMAE_VIGOR" in tiny_types
    assert "ASMAE_ROOT_ZONE_WATER" not in tiny_types


def test_independent_field_validation_excludes_mocks_and_unconfirmed_tasks():
    """Independent validation compares withheld sensors/scouting/MESIA & rejects unconfirmed planned tasks."""
    from services.agribrain.layer05_asmae.history.independent_field_validation import evaluate_independent_field_evidence

    traj = [
        {
            "acquisition_time": "2026-05-10T10:30:00+00:00",
            "posterior_state_means": {"root_zone_water": 0.28, "vigor": 0.62, "stress_memory": 0.12},
            "posterior_state_stds": {"root_zone_water": 0.04},
            "cross_layer_refined": {"layers_refined": {"layer5_biotic": {"top_threat_hypothesis": "moderate_fungal_risk"}}},
        }
    ]
    res = evaluate_independent_field_evidence(
        plot_id="val_plot",
        trajectory=traj,
        sensor_readings=[
            {
                "timestamp": "2026-05-10T12:00:00+00:00",
                "soilMoisture": 26.5,
                "vendor": "Sentek Drill & Drop",
                "isCalibrated": True,
                "calibrationCertificateId": "SENTEK-TEST-01",
                "calibrationAuthority": "sentek_lab_cert_authority",
                "calibrationVerifiedAt": "2026-05-01T00:00:00+00:00",
                "deviceId": "S1",
            },
            {"timestamp": "2026-05-10T12:05:00+00:00", "soilMoisture": 99.0, "vendor": "Mock Vendor", "deviceId": "M1"},
        ],
        crop_observations=[{"createdAt": "2026-05-11T09:00:00+00:00", "type": "disease", "title": "Foliar Rust"}],
        crop_tasks=[
            {"type": "IRRIGATION", "title": "Planned Cycle", "dueDate": "2026-05-12", "completed": False},
            {"type": "IRRIGATION", "title": "Applied Cycle", "dueDate": "2026-05-09", "completed": True},
        ],
        mesia_packets=[{"timestamp": "2026-05-10T11:00:00+00:00", "likelihood_value": 0.65, "calibrated_vwc": 0.265}],
    )
    assert res["zero_circularity_enforced"] is True
    assert res["sensor_vwc_validation"]["n_readings"] == 1
    assert res["sensor_vwc_validation"]["skipped_mock_or_simulator"] == 1
    assert res["sensor_vwc_validation"]["coverage_2sigma"] == 1.0
    assert res["mesia_hydrological_validation"]["evaluations"][0]["comparison_mode"] == "CALIBRATED_PHYSICAL_OBSERVATION"
    assert res["mesia_hydrological_validation"]["evaluations"][0]["is_hydrologically_consistent"] is True
    assert res["crop_tasks_summary"]["applied_or_completed_count"] == 1
    assert res["crop_tasks_summary"]["unconfirmed_planned_ignored_count"] == 1
    assert res["scouting_records_audited"] == 1


def test_intraday_1030_forecast_byte_identical_under_afternoon_weather_and_future_obs_mutation(tmp_path: Path):
    """Acceptance test: 10:30 AM forecast is byte-identical when that day's afternoon weather & later days change."""
    (tmp_path / "run_a").mkdir(parents=True, exist_ok=True)
    (tmp_path / "run_b").mkdir(parents=True, exist_ok=True)
    wl1 = CanonicalWorldlineService(root=tmp_path / "run_a" / "wl", require_durable_anchor=False)
    wl2 = CanonicalWorldlineService(root=tmp_path / "run_b" / "wl", require_durable_anchor=False)
    plot_id = "intraday_1030_plot"
    geom_hash = "sha256:intraday_1030"

    base_scenes = _make_seasonal_scenes([2023, 2024])
    issuance_scene = {
        "scene_id": "S2_20250510_1030",
        "acquisition_time": "2025-05-10T10:30:00+00:00",
        "source": "sentinel2",
        "product_level": "L2A",
        "cloud_score": 0.04,
        "quality_score": 0.96,
        "valid_pixel_fraction": 0.98,
        "source_content_hash": "intraday1030".ljust(64, "0"),
        "metrics": {"ndvi_mean": 0.64, "ndmi_mean": 0.21},
    }
    later_scene_1 = {
        "scene_id": "S2_20250517_1030",
        "acquisition_time": "2025-05-17T10:30:00+00:00",
        "source": "sentinel2",
        "product_level": "L2A",
        "cloud_score": 0.04,
        "quality_score": 0.96,
        "valid_pixel_fraction": 0.98,
        "source_content_hash": "later1".ljust(64, "0"),
        "metrics": {"ndvi_mean": 0.59, "ndmi_mean": 0.16},
    }
    later_scene_2 = {
        "scene_id": "S2_20250517_ALT",
        "acquisition_time": "2025-05-17T10:30:00+00:00",
        "source": "sentinel2",
        "product_level": "L2A",
        "cloud_score": 0.04,
        "quality_score": 0.96,
        "valid_pixel_fraction": 0.98,
        "source_content_hash": "later2".ljust(64, "0"),
        "metrics": {"ndvi_mean": 0.22, "ndmi_mean": -0.14},
    }
    _commit_obs_sequence(wl1, plot_id, geom_hash, base_scenes + [issuance_scene, later_scene_1])
    _commit_obs_sequence(wl2, plot_id, geom_hash, base_scenes + [issuance_scene, later_scene_2])

    weather_a = _build_synthetic_weather(2023, 2025)
    weather_b = copy.deepcopy(weather_a)
    # Mutate same-day afternoon realized weather on 2025-05-10 and following days
    weather_b["2025-05-10"] = {"temp_max": 47.0, "temp_min": 28.0, "precipitation": 98.0, "et0": 11.5}
    for d in ("2025-05-11", "2025-05-12", "2025-05-13", "2025-05-14", "2025-05-15", "2025-05-16"):
        weather_b[d] = {"temp_max": 46.0, "temp_min": 29.0, "precipitation": 85.0, "et0": 12.0}

    r1 = HistoricalStateReconstructor(worldline=wl1, checkpoint_root=tmp_path / "cp_a", n_ensemble=10, checkpoint_stride=8)
    r2 = HistoricalStateReconstructor(worldline=wl2, checkpoint_root=tmp_path / "cp_b", n_ensemble=10, checkpoint_stride=8)

    issue_iso = "2025-05-10T10:30:00+00:00"
    fixed_k = "2027-01-01T00:00:00+00:00"
    q_a = r1.query_as_of(plot_id=plot_id, geometry_hash=geom_hash, valid_time_T=issue_iso, knowledge_cutoff_K=fixed_k, daily_weather=weather_a)
    q_b = r2.query_as_of(plot_id=plot_id, geometry_hash=geom_hash, valid_time_T=issue_iso, knowledge_cutoff_K=fixed_k, daily_weather=weather_b)

    assert q_a["available"] is True
    assert q_a["state_means"] == q_b["state_means"]
    assert q_a["causal_forecasts"] == q_b["causal_forecasts"]
    assert q_a["cross_layer_intelligence"] == q_b["cross_layer_intelligence"]

    # Also verify full reconstruction hindsight reference DOES change while prospective multi-horizon up to May 10 doesn't
    res_a = r1.reconstruct(plot_id=plot_id, geometry_hash=geom_hash, daily_weather=weather_a, retrovalidation_fn=None, emit_worldline_posterior=False)
    res_b = r2.reconstruct(plot_id=plot_id, geometry_hash=geom_hash, daily_weather=weather_b, retrovalidation_fn=None, emit_worldline_posterior=False)
    ev_a = HistoricalRetrovalidator().evaluate(res_a["trajectory"], {"daily_weather": weather_a, "crop_context": {"crop_type": "citrus", "crop_coefficient": 0.75}, "soil_context": {}})
    ev_b = HistoricalRetrovalidator().evaluate(res_b["trajectory"], {"daily_weather": weather_b, "crop_context": {"crop_type": "citrus", "crop_coefficient": 0.75}, "soil_context": {}})
    assert ev_a["multi_horizon"]["uses_issuance_day_complete_daily_weather"] is False
    assert ev_a["multi_horizon"]["hindcast_realized_weather_reference"] != ev_b["multi_horizon"]["hindcast_realized_weather_reference"]


