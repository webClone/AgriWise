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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pytest

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
    assert not any(ev["event_type"] == "ARCHIVE_POSTERIOR_VALIDATED" for ev in events_before)
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

    # Verify ARCHIVE_POSTERIOR_VALIDATED is now committed once after assimilation
    post_events = [ev for ev in wl.load_all_events(plot_id) if ev["event_type"] == "ARCHIVE_POSTERIOR_VALIDATED"]
    assert len(post_events) == 1
    ap = post_events[0]["payload"]["archive_posterior"]
    assert ap["model_version"] == RECONSTRUCTOR_MODEL_VERSION
    assert ap["state_schema_version"] == STATE_SCHEMA_VERSION
    assert ap["calibration_version"] == CALIBRATION_VERSION
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
    assert {"rainfall_response", "planting_emergence", "candidate_irrigation", "canopy_change", "stress_onset", "recovery"} <= cats

    rain_evs = [e for e in evs if e["event_category"] == "rainfall_response"]
    cand_irrig = [e for e in evs if e["event_category"] == "candidate_irrigation"]
    assert all(e["epistemic_class"] == "observed_event" for e in rain_evs)
    assert all(e["epistemic_class"] == "model_hypothesis" for e in cand_irrig)
    assert cand_irrig[0]["hypothesis_status"] == "supported"
    assert cand_irrig[0]["outcome_measurement"]["delta_obs_ndvi"] > 0


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
