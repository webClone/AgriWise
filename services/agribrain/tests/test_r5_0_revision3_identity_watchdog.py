import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.agribrain.layer05_asmae import background_jobs
from services.agribrain.layer05_asmae.evidence_capability import (
    _stable_node_hash,
    build_capability_plan,
    prepare_capability_execution_context,
)
from services.agribrain.layer05_asmae.scene_admission import scene_quality_identity
from services.agribrain.layer0.observation_packet import DataStatus
from services.agribrain.layer0.source_package import Layer0SourcePackage
from services.agribrain.layer05_asmae.job_manifest import (
    build_job_identity,
    load_job_manifest,
    scientific_job_id,
    write_job_manifest,
)
from services.agribrain.layer05_asmae.cache import compute_source_hash
from services.agribrain.layer10_sire.surfaces.derivation_lineage import (
    attach_derived_surface_lineage,
)
from services.agribrain.common.plot_namespace import PlotNamespace


def _scene(root: Path, *, valid_fraction: float = 0.9):
    root.mkdir(parents=True, exist_ok=True)
    red = root / "B04.bin"
    nir = root / "B08.bin"
    mask = root / "SCL.bin"
    red.write_bytes(b"red-pixels-v1")
    nir.write_bytes(b"nir-pixels-v1")
    mask.write_bytes(b"support-mask-v1")
    return {
        "scene_id": "portable-scene",
        "sensor": "S2",
        "source_reality": "real_raster",
        "acquisition_time": "2026-07-27T10:25:59Z",
        "crs": "EPSG:32631",
        "transform": [10.0, 0.0, 500000.0, 0.0, -10.0, 4050000.0],
        "width": 2,
        "height": 2,
        "band_refs": {"B04": str(red), "B08": str(nir)},
        "mask_refs": {"SCL": str(mask)},
        "valid_fraction": valid_fraction,
        "valid_pixel_count": int(valid_fraction * 1000),
        "total_pixel_count": 1000,
        "cloud_fraction": 1.0 - valid_fraction,
        "quality_score": valid_fraction,
        "quality_class": "good" if valid_fraction > 0.75 else "fair",
        "usable": True,
        "data_status": "observed",
    }


def _plan(scene):
    return build_capability_plan({"asmae_sentinel2_real": [scene]}, {}, [])


def test_unavailable_enum_status_survives_manifest_scalar_normalization():
    """Layer 0 enums and their JSON scalar form are one scientific fact.

    This reproduces the live worker failure where the frozen quarantine ledger
    saw ``DataStatus.UNAVAILABLE`` but the manifest-rehydrated worker saw the
    string ``"unavailable"``.
    """
    package = Layer0SourcePackage.unavailable(
        "sentinel1",
        plot_id="plot-status-roundtrip",
        reason="PROVIDER_UNAVAILABLE",
    )
    manifest_record = dict(package.__dict__)
    manifest_record["data_status"] = "unavailable"

    assert scene_quality_identity(package) == scene_quality_identity(manifest_record)
    assert scene_quality_identity(package)["data_status"] == "unavailable"
    assert _stable_node_hash(
        package,
        "sentinel1",
        ("layer0_source_packages", "sentinel1", "0"),
        None,
    ) == _stable_node_hash(
        manifest_record,
        "sentinel1",
        ("layer0_source_packages", "sentinel1", "0"),
        None,
    )


def test_scene_identity_is_path_invariant_and_byte_sensitive(tmp_path):
    first = _scene(tmp_path / "host-a")
    second_root = tmp_path / "host-b"
    shutil.copytree(tmp_path / "host-a", second_root)
    second = dict(first)
    second["band_refs"] = {
        "B04": str(second_root / "B04.bin"),
        "B08": str(second_root / "B08.bin"),
    }
    second["mask_refs"] = {"SCL": str(second_root / "SCL.bin")}
    assert _plan(first).plan_hash() == _plan(second).plan_hash()

    @dataclass
    class CacheInput:
        layer0_source_packages: dict
        raster_composites: dict
        run_id: str

    first_context = {
        "geometry_hash": "geometry-v1",
        "capability_plan_hash": _plan(first).plan_hash(),
        "layer0_source_packages": {"asmae_sentinel2_real": [first]},
    }
    second_context = {
        **first_context,
        "layer0_source_packages": {"asmae_sentinel2_real": [second]},
    }
    assert build_job_identity("plot", first_context, {}) == build_job_identity(
        "plot", second_context, {}
    )
    assert compute_source_hash(CacheInput(
        first_context["layer0_source_packages"], {}, "run-a"
    )) == compute_source_hash(CacheInput(
        second_context["layer0_source_packages"], {}, "run-b"
    ))

    (second_root / "B08.bin").write_bytes(b"nir-pixels-CHANGED")
    assert _plan(first).plan_hash() != _plan(second).plan_hash()
    assert compute_source_hash(CacheInput(
        first_context["layer0_source_packages"], {}, "run-a"
    )) != compute_source_hash(CacheInput(
        second_context["layer0_source_packages"], {}, "run-b"
    ))


def test_quality_facts_change_plan_identity(tmp_path):
    high = _scene(tmp_path / "quality", valid_fraction=0.9)
    lower = dict(high)
    lower.update({
        "valid_fraction": 0.5,
        "valid_pixel_count": 500,
        "cloud_fraction": 0.5,
        "quality_score": 0.5,
        "quality_class": "fair",
    })
    assert _plan(high).plan_hash() != _plan(lower).plan_hash()


def test_manifest_copies_referenced_rasters_into_artifact_table(tmp_path):
    namespace = PlotNamespace("tenant", "farm", "plot-portable")
    scene = _scene(tmp_path / "source")
    plan = _plan(scene)
    context = {
        "plot_namespace": {
            "tenant_id": namespace.tenant_id,
            "farm_id": namespace.farm_id,
            "plot_id": namespace.plot_id,
        },
        "tenant_id": namespace.tenant_id,
        "farm_id": namespace.farm_id,
        "plot_id": namespace.plot_id,
        "geometry_hash": "geometry-v1",
        "capability_plan_hash": plan.plan_hash(),
        "execution_plan_hash": plan.execution_plan_hash(),
        "quarantine_ledger_hash": plan.quarantine_ledger_hash(),
        "evidence_capability_contract_version": plan.contract_version,
        "layer0_source_packages": plan.execution_layer0_packages(),
    }
    identity = build_job_identity(namespace, context, {})
    job_id = scientific_job_id(identity)
    manifest_path = tmp_path / f"{job_id}.manifest.json"
    manifest = write_job_manifest(
        manifest_path,
        job_id=job_id,
        plot_id="plot-portable",
        namespace=namespace,
        run_id="portable-run",
        context=context,
        config={},
        identity=identity,
    )
    external = [a for a in manifest["artifacts"] if a["kind"] == "external_file_v1"]
    assert len(external) == 3
    manifest_text = manifest_path.read_text(encoding="utf-8")
    assert str(tmp_path / "source") not in manifest_text
    loaded = load_job_manifest(manifest_path)
    decoded_scene = loaded["context"]["layer0_source_packages"]["asmae_sentinel2_real"][0]
    assert Path(decoded_scene["band_refs"]["B04"]).read_bytes() == b"red-pixels-v1"
    assert Path(decoded_scene["mask_refs"]["SCL"]).read_bytes() == b"support-mask-v1"


def test_prepared_plan_identity_survives_enum_like_manifest_round_trip(tmp_path):
    namespace = PlotNamespace("tenant", "farm", "plot-roundtrip")
    scene = _scene(tmp_path / "source")
    scene.update({
        "quality_class": SimpleNamespace(value="unknown"),
        "diagnostic_only": True,
        "production_usable": False,
        "data_status": "fallback",
    })
    prepared, original_plan = prepare_capability_execution_context({
        "plot_namespace": {
            "tenant_id": namespace.tenant_id,
            "farm_id": namespace.farm_id,
            "plot_id": namespace.plot_id,
        },
        "tenant_id": namespace.tenant_id,
        "farm_id": namespace.farm_id,
        "plot_id": namespace.plot_id,
        "geometry_hash": "geometry-v1",
        "layer0_source_packages": {"experimental_s2_proxy": [scene]},
    })
    assert original_plan.spatial_scene_count == 0
    assert original_plan.rejected_nodes
    identity = build_job_identity(namespace, prepared, {})
    job_id = scientific_job_id(identity)
    manifest_path = tmp_path / f"{job_id}.manifest.json"
    write_job_manifest(
        manifest_path,
        job_id=job_id,
        plot_id="plot-roundtrip",
        namespace=namespace,
        run_id="roundtrip-run",
        context=prepared,
        config={},
        identity=identity,
    )

    loaded = load_job_manifest(manifest_path)["context"]
    reparsed, reparsed_plan = prepare_capability_execution_context(loaded)
    assert reparsed_plan.plan_hash() == original_plan.plan_hash()
    assert reparsed_plan.execution_plan_hash() == original_plan.execution_plan_hash()
    assert reparsed_plan.quarantine_ledger_hash() == original_plan.quarantine_ledger_hash()
    assert reparsed["capability_plan_hash"] == prepared["capability_plan_hash"]


def test_execution_and_quarantine_identities_are_independent(tmp_path):
    accepted = _scene(tmp_path / "accepted")
    rejected = _scene(tmp_path / "rejected", valid_fraction=0.0)
    rejected.update({
        "diagnostic_only": True,
        "production_usable": False,
        "quality_class": SimpleNamespace(value="unknown"),
    })
    changed_rejected = dict(rejected)
    changed_rejected["quality_class"] = SimpleNamespace(value="poor")
    first = build_capability_plan({
        "asmae_sentinel2_real": [accepted],
        "experimental_s2_proxy": [rejected],
    })
    second = build_capability_plan({
        "asmae_sentinel2_real": [accepted],
        "experimental_s2_proxy": [changed_rejected],
    })
    assert first.execution_plan_hash() == second.execution_plan_hash()
    assert first.quarantine_ledger_hash() != second.quarantine_ledger_hash()
    assert first.plan_hash() != second.plan_hash()


def test_zero_spatial_scene_preflight_creates_no_job(monkeypatch, tmp_path):
    prepared, plan = prepare_capability_execution_context({
        "geometry_hash": "geometry-v1",
        "plot_timeseries": [{
            "timestamp": "2026-07-27T00:00:00Z",
            "ndvi": 0.42,
            "data_status": "observed",
        }],
    })
    monkeypatch.setattr(background_jobs, "JOBS_DIR", tmp_path / "jobs")
    result = background_jobs.enqueue_standard_job(
        PlotNamespace("tenant", "farm", "plot-no-scene"),
        "run-no-scene", prepared, {}
    )
    assert plan.spatial_scene_count == 0
    assert result["status"] == "not_eligible"
    assert result["reason"] == "NOT_ELIGIBLE_NO_EXECUTABLE_SPATIAL_SCENE"
    assert result["temporal_diagnostic_available"] is True
    assert not (tmp_path / "jobs").exists()


@pytest.mark.parametrize("status", ["partial", "unavailable", "error", "failed_spatial_timeout"])
def test_failure_lineage_is_secondary_and_never_raises(monkeypatch, status):
    from services.agribrain.layer05_asmae.history.worldline_service import PlotWorldlineService

    def fail_commit(*args, **kwargs):
        raise OSError("lineage store unavailable")

    monkeypatch.setattr(PlotWorldlineService, "commit_event", fail_commit)
    outcome, event_id = background_jobs._commit_job_failure_event(
        {"status": status, "reason": "PRIMARY_SCIENTIFIC_FAILURE"},
        {"job_id": "a" * 24, "plot_id": "plot-a", "run_id": "run-a"},
        {"context": {}},
    )
    assert outcome == "lineage_commit_failed"
    assert event_id is None


def test_timeout_primary_truth_is_durable_before_lineage(monkeypatch, tmp_path):
    job_path = tmp_path / ("b" * 24 + ".job.json")
    job_path.write_text(json.dumps({
        "job_id": "b" * 24,
        "plot_id": "plot-timeout",
        "run_id": "run-timeout",
        "status": "running",
        "stage": "scientific_execution",
        "launch_token": "launch-token",
        "revision": 1,
        "manifest_ref": str(tmp_path / "missing.manifest.json"),
    }), encoding="utf-8")

    def broken_secondary(*args, **kwargs):
        raise RuntimeError("secondary lineage failure")

    monkeypatch.setattr(background_jobs, "_commit_job_failure_event", broken_secondary)
    with pytest.raises(RuntimeError, match="secondary lineage failure"):
        background_jobs._finalize_supervised_timeout(job_path, "launch-token", 306.0)
    durable = json.loads(job_path.read_text(encoding="utf-8"))
    assert durable["status"] == "failed"
    assert durable["stage"] == "process_hard_timeout"
    assert durable["reason"] == "PROCESS_HARD_TIMEOUT"
    assert durable["error_type"] == "ProcessHardTimeout"
    assert durable["result_status"] == "failed_spatial_timeout"


def test_supervisor_terminates_then_kills_noncooperative_child(monkeypatch, tmp_path):
    calls = []

    class FakeChild:
        pid = 4242
        waits = 0

        def wait(self, timeout=None):
            self.waits += 1
            calls.append(("wait", timeout))
            if self.waits <= 2:
                raise subprocess.TimeoutExpired("worker", timeout)
            return -9

        def terminate(self):
            calls.append(("terminate", None))

        def kill(self):
            calls.append(("kill", None))

    monkeypatch.setattr(background_jobs.subprocess, "Popen", lambda *a, **k: FakeChild())
    monkeypatch.setattr(background_jobs, "_update_job", lambda *a, **k: {})
    monkeypatch.setattr(background_jobs, "_read_json", lambda *a, **k: {})
    monkeypatch.setattr(
        background_jobs, "_finalize_supervised_timeout",
        lambda *a, **k: calls.append(("finalize", None)),
    )
    background_jobs.supervise_job(tmp_path / "job.job.json", "launch")
    assert ("terminate", None) in calls
    assert ("kill", None) in calls
    assert calls[-1] == ("finalize", None)


@pytest.mark.parametrize(
    "semantic,operator",
    [
        ("NUTRIENT_STRESS_PROB", "nutrient_stress_v5"),
        ("SALINITY_STRESS", "salinity_stress_v2"),
        ("COMPOSITE_RISK", "composite_risk_v4"),
    ],
)
def test_diagnostic_surfaces_receive_typed_authority_lineage(semantic, operator):
    surface = SimpleNamespace(
        semantic_type=semantic,
        raster_basis=["ndvi"],
        observed_ratio=0.8,
        provenance={},
        grid_spec={"crs": "EPSG:32631", "transform": [10, 0, 0, 0, -10, 0]},
    )
    l1 = SimpleNamespace(
        grid_spec=surface.grid_spec,
        raster_metadata={
            "ndvi": {
                "raster_id": "provider-ndvi",
                "content_hash": "f" * 64,
                "source_reality": "provider_temporal_composite_raster",
                "real_provider_product": True,
                "production_usable": True,
                "crs": "EPSG:32631",
                "transform": [10, 0, 0, 0, -10, 0],
            }
        },
    )
    assert attach_derived_surface_lineage(surface, l1) is True
    assert surface.provenance["operator_model_version"] == operator
    assert surface.provenance["derived_from_surface_ids"] == ["provider-ndvi"]
    assert surface.provenance["derived_from_content_hashes"] == ["f" * 64]
    assert surface.provenance["observed_support_ratio"] == 0.8
    assert surface.provenance["uncertainty_propagation"]
    assert surface.provenance["state_update_authority"] == "none"
    assert surface.provenance["prescription_authority"] == "blocked_diagnostic_only"
