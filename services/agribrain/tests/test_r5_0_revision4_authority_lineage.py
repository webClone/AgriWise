import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from services.agribrain.layer05_asmae import background_jobs
from services.agribrain.layer05_asmae.feature_export import export_asmae_feature_pack
from services.agribrain.layer10_sire.adapters.asmae_feature_bus import (
    build_asmae_feature_bus,
)
from services.agribrain.common.plot_namespace import PlotNamespace


def _grid(value):
    return [[value, value + 0.1], [value + 0.2, value + 0.3]]


def _prior_ledger():
    states = (
        "vigor", "lai", "chlorophyll", "canopy_water", "root_zone_water",
        "surface_wetness_event", "structure", "bare_soil_fraction",
        "salinity_stress", "thermal_stress", "biotic_confounder_risk",
        "phenology_progress", "stress_memory",
    )
    return {
        state: {
            "state": state,
            "support_status": "prior_constrained",
            "observation_relationship": "none",
            "accepted_update_count": 0,
            "direct_observation_count": 0,
            "indirect_observation_count": 0,
            "proxy_observation_count": 0,
        }
        for state in states
    }


def test_feature_pack_does_not_promote_prior_or_unexecuted_stages():
    output = SimpleNamespace(
        raster_maps={"vigor": _grid(0.2)},
        uncertainty_maps={},
        confidence_maps={"archive_support": _grid(0.0)},
        retrovalidation_maps={"retro_score": _grid(0.0)},
        bma_maps={
            "bma_disagreement": _grid(0.0),
            "ml_support": _grid(0.0),
        },
        diagnostics={
            "state_support_ledger": _prior_ledger(),
            "used_archive": False,
            "used_ml": False,
            "used_bma": False,
            "used_retrovalidation": False,
            "ml_state": "unavailable",
            "bma_status": "no_holdout_available",
        },
        grid_spec={"height": 2, "width": 2},
        asmae_evidence_state={"real_asmae_evidence": True},
    )
    pack = export_asmae_feature_pack(output)
    assert pack["feature_status"]["vigor"]["status"] == "prior_constrained"
    for feature in (
        "archive_support", "ml_support", "bma_disagreement",
        "retrovalidation_score",
    ):
        assert pack["feature_status"][feature]["status"] == "unavailable"
        assert pack["feature_status"][feature]["weight"] == 0.0


def test_feature_bus_respects_prior_upper_bound_over_layer1_raster():
    ndvi = np.array([[0.1, 0.3, 0.6], [0.2, 0.5, 0.8], [0.4, 0.7, 0.9]])
    prior = {
        "status": "prior_constrained",
        "source": "layer05_process_model",
        "weight": 0.0,
        "confidence": 0.0,
        "usable_for_advisory": False,
    }
    l1 = SimpleNamespace(
        real_asmae_evidence=True,
        raster_maps={"NDVI": ndvi, "ASMAE_VIGOR": ndvi},
        asmae_feature_pack={
            "state": {"vigor": ndvi.tolist()},
            "diagnostics": {},
            "resolution": {},
            "feature_status": {"vigor": prior},
        },
    )
    bus = build_asmae_feature_bus(3, 3, [], None, l1)
    assert bus.available is True
    assert bus.vigor is None
    assert bus.feature_status["vigor"]["status"] == "prior_constrained"
    assert bus.feature_status["vigor"]["authority_upper_bound"] == "prior_constrained"


def test_scientific_execution_id_is_unique_and_keeps_request_lineage(monkeypatch, tmp_path):
    monkeypatch.setattr(background_jobs, "JOBS_DIR", tmp_path / "jobs")
    monkeypatch.setattr(background_jobs, "spawn_worker", lambda _path: False)
    context = {
        "geometry_hash": "geometry-v1",
        "capability_plan_hash": "plan-v1",
        "execution_plan_hash": "execution-v1",
        "quarantine_ledger_hash": "quarantine-v1",
        "capability_plan_summary": {
            "spatial_scene_capability": {"accepted_count": 1}
        },
    }
    first = background_jobs.enqueue_standard_job(
        PlotNamespace("tenant", "farm", "plot-a"),
        "request-lineage", context, {"variant": 1}
    )
    second = background_jobs.enqueue_standard_job(
        PlotNamespace("tenant", "farm", "plot-a"),
        "request-lineage", context, {"variant": 2}
    )
    assert first["run_id"].startswith("ASMAE-RUN-")
    assert first["run_id"] != second["run_id"]
    assert first["request_lineage_id"] == second["request_lineage_id"] == "request-lineage"
    persisted = json.loads(Path(first["job_ref"]).read_text(encoding="utf-8"))
    assert persisted["plot_namespace"] == {
        "tenant_id": "tenant",
        "farm_id": "farm",
        "plot_id": "plot-a",
    }
    assert persisted["tenant_id"] == "tenant"
    assert persisted["farm_id"] == "farm"


def test_each_worker_launch_appends_an_immutable_build_receipt(monkeypatch, tmp_path):
    monkeypatch.setattr(background_jobs, "scientific_source_digest", lambda: "b" * 64)
    job_path = tmp_path / ("a" * 24 + ".job.json")
    payload = {
        "job_id": "a" * 24,
        "plot_id": "plot-a",
        "run_id": "ASMAE-RUN-" + "a" * 24,
        "status": "queued",
        "stage": "manifest_persisted",
        "manifest_hash": "manifest-v1",
        "scientific_identity": {
            "scientific_source_digest": "b" * 64,
            "config_hash": "config-v1",
        },
        "revision": 1,
    }
    job_path.write_text(json.dumps(payload), encoding="utf-8")
    assert background_jobs._reserve_launch(job_path)
    first = json.loads(job_path.read_text(encoding="utf-8"))
    assert len(first["operational_attempts"]) == 1
    assert first["operational_attempts"][0]["launch_generation"] == 1
    first.update(status="stalled", launch_reserved_at="2000-01-01T00:00:00+00:00")
    job_path.write_text(json.dumps(first), encoding="utf-8")
    assert background_jobs._reserve_launch(job_path)
    second = json.loads(job_path.read_text(encoding="utf-8"))
    assert [r["launch_generation"] for r in second["operational_attempts"]] == [1, 2]
    assert second["active_operational_attempt_id"] == second["operational_attempts"][-1]["operational_attempt_id"]


def test_scientific_launch_fails_closed_when_source_changed(monkeypatch, tmp_path):
    monkeypatch.setattr(background_jobs, "scientific_source_digest", lambda: "c" * 64)
    job_path = tmp_path / ("d" * 24 + ".job.json")
    job_path.write_text(json.dumps({
        "job_id": "d" * 24,
        "plot_id": "plot-source-change",
        "run_id": "ASMAE-RUN-" + "d" * 24,
        "status": "queued",
        "manifest_hash": "manifest-v1",
        "scientific_identity": {
            "scientific_source_digest": "b" * 64,
            "config_hash": "config-v1",
        },
        "revision": 1,
    }), encoding="utf-8")
    assert background_jobs._reserve_launch(job_path) is None
    blocked = json.loads(job_path.read_text(encoding="utf-8"))
    assert blocked["status"] == "superseded"
    assert blocked["compatibility_reason"] == "scientific_source_digest_mismatch"
    assert blocked["operational_attempts"][0]["launch_permitted"] is False


def test_chlorophyll_invariant_uses_physical_units_range():
    root = Path(__file__).resolve().parents[3]
    invariant_source = (root / "services/agribrain/layer10_sire/invariants.py").read_text(encoding="utf-8")
    surface_source = (root / "services/agribrain/layer10_sire/surfaces/asmae.py").read_text(encoding="utf-8")
    assert "SurfaceType.ASMAE_CHLOROPHYLL: (0.0, 80.0)" in invariant_source
    assert 'SurfaceType.ASMAE_CHLOROPHYLL: "ug/cm2"' in surface_source
