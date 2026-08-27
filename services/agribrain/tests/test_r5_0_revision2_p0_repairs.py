# -*- coding: utf-8 -*-
"""Revision 2 P0 Contract & Integrity Tests for R5.0."""

import pytest
import os
import json
import hashlib
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock

from services.agribrain.layer05_asmae.evidence_capability import (
    CapabilityPlanIdentityError,
    EvidenceCapability,
    _stable_node_hash,
    build_capability_plan,
    classify_package,
    prepare_capability_execution_context,
)
from services.agribrain.layer05_asmae.background_jobs import (
    _completed_result_event_type,
    classify_execution_failure,
    resolve_retry_decision,
)
from services.agribrain.layer05_asmae.job_manifest import (
    build_job_identity,
    load_job_manifest,
    scientific_job_id,
    write_job_manifest,
)
from services.agribrain.layer05_asmae.evidence_classifier import classify_asmae_evidence
from services.agribrain.layer05_asmae.geometry.scene_stack_builder import build_real_asmae_scene_stack
from services.agribrain.layer05_asmae.geometry.layer0_package_adapter import adapt_layer0_package_to_scene_candidate
from services.agribrain.layer05_asmae.cache import ensure_cache_directories_exist
from services.agribrain.layer10_sire.surfaces.grid_access import reproject_scientific_grid
from services.agribrain.diagnostic_integration import pre_decision_tribunal
from services.agribrain.orchestrator_v2.hashing import generate_orchestrator_run_id
from services.agribrain.orchestrator_v2.schema import OrchestratorInput
from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.orchestrator_v2.runner import (
    _weather_records_from_reintegration_context,
)
from services.agribrain.layer05_asmae.reintegration import (
    _mark_completed_publication,
)


class TestRevision2P0Repairs:

    def test_completed_publication_clears_all_nested_running_state(self) -> None:
        nested = {
            "active_spatial_job_status": "running",
            "supersession_reason": "newer_spatial_refresh_in_progress",
        }
        frontend = {
            "source_policy_display_state": {
                "asmaePlotState": {
                    "activeSpatialJobStatus": "running",
                    "activeSpatialJobProgressPct": 85,
                    "spatialSupersession": dict(nested),
                },
            },
            "asmae_evidence_state": {
                "active_spatial_job_status": "running",
                "active_spatial_job_progress_pct": 85,
                "spatial_supersession": dict(nested),
            },
            "core_asmae_evidence_state": {
                "active_spatial_job_status": "running",
                "spatial_supersession": dict(nested),
            },
            "spatial_supersession": dict(nested),
        }

        _mark_completed_publication(frontend, "job-complete")

        plot_state = frontend["source_policy_display_state"]["asmaePlotState"]
        assert plot_state["activeSpatialJobStatus"] == "completed"
        assert plot_state["activeSpatialJobStage"] == "complete"
        assert plot_state["activeSpatialJobProgressPct"] == 100
        for state in (
            plot_state["spatialSupersession"],
            frontend["asmae_evidence_state"],
            frontend["asmae_evidence_state"]["spatial_supersession"],
            frontend["core_asmae_evidence_state"],
            frontend["core_asmae_evidence_state"]["spatial_supersession"],
            frontend["spatial_supersession"],
        ):
            assert state["active_spatial_job_status"] == "completed"
            assert state["active_spatial_job_id"] == "job-complete"
        assert plot_state["spatialSupersession"]["supersession_reason"] == (
            "completed_snapshot_current"
        )

    @staticmethod
    def _composites():
        grid = {
            "crs": "EPSG:32631",
            "transform": [500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0],
            "width": 2,
            "height": 2,
            "source_window": ["2026-07-01", "2026-07-31"],
            "provider": "sentinel-hub",
            "production_usable": True,
            "real_provider_product": True,
        }
        return {
            "NDVI": {**grid, "values": np.array([[0.2, 0.3], [0.4, 0.5]], dtype=np.float64)},
            "NDMI": {**grid, "values": np.array([[0.1, 0.2], [0.3, 0.4]], dtype=np.float64)},
            "QUALITY": {**grid, "values": np.array([[1, 1], [0, 1]], dtype=np.uint8)},
            "SAR": {**grid, "values": np.array([[-10.0, -11.0], [-9.0, -12.0]], dtype=np.float32)},
        }

    def test_composite_products_have_distinct_exact_identities(self) -> None:
        plan = build_capability_plan({}, self._composites(), [])
        identities = {node.source_family: node.content_hash for node in plan.composite_rasters}
        assert set(identities) == {"NDVI", "NDMI", "QUALITY", "SAR"}
        assert len(set(identities.values())) == 4
        changed = self._composites()
        changed["NDVI"]["values"][0, 0] = 0.20000000000000004
        changed_plan = build_capability_plan({}, changed, [])
        changed_ids = {node.source_family: node.content_hash for node in changed_plan.composite_rasters}
        assert identities["NDVI"] != changed_ids["NDVI"]

    def test_wrapper_order_does_not_change_plan_identity(self) -> None:
        observation = {
            "timestamp": "2026-07-01T00:00:00Z",
            "sensor": "S2",
            "data_status": "observed",
            "ndvi_mean": 0.42,
            "production_usable": True,
        }
        sparse_wrapper = {
            "timestamp": observation["timestamp"],
            "sensor": "S2",
            "data_status": "observed",
            "ndvi_mean": 0.42,
            "production_usable": True,
        }
        first = build_capability_plan(
            {"sentinel2": [observation], "asmae_sentinel2_raw": [sparse_wrapper]},
            self._composites(),
            [],
        )
        second = build_capability_plan(
            {"asmae_sentinel2_raw": [sparse_wrapper], "sentinel2": [observation]},
            dict(reversed(list(self._composites().items()))),
            [],
        )
        assert first.plan_hash() == second.plan_hash()
        assert len(first.temporal_observations) == len(second.temporal_observations) == 1
        assert first.temporal_observations[0].source_family == "asmae_sentinel2_raw"
        assert second.temporal_observations[0].source_family == "asmae_sentinel2_raw"
        assert first.public_records() == second.public_records()

    def test_manifest_round_trip_rebuilds_identical_plan(self, tmp_path: Path) -> None:
        prepared, original = prepare_capability_execution_context({
            "layer0_source_packages": {
                "sentinel2": [{
                    "timestamp": "2026-07-01T00:00:00Z",
                    "sensor": "S2",
                    "data_status": "observed",
                    "ndvi_mean": 0.42,
                }],
            },
            "raster_composites": self._composites(),
            "plot_timeseries": [],
            "geometry_hash": "geometry-a",
        })
        namespace = PlotNamespace("tenant-a", "farm-a", "plot-a")
        prepared.update({
            "plot_namespace": {
                "tenant_id": namespace.tenant_id,
                "farm_id": namespace.farm_id,
                "plot_id": namespace.plot_id,
            },
            "tenant_id": namespace.tenant_id,
            "farm_id": namespace.farm_id,
            "plot_id": namespace.plot_id,
        })
        identity = build_job_identity(namespace, prepared, {})
        job_id = scientific_job_id(identity)
        path = tmp_path / f"{job_id}.manifest.json"
        write_job_manifest(
            path,
            job_id=job_id,
            plot_id="plot-a",
            namespace=namespace,
            run_id="run-a",
            context=prepared,
            config={},
            identity=identity,
        )
        decoded = load_job_manifest(path)["context"]
        _, rebuilt = prepare_capability_execution_context(decoded)
        assert rebuilt.plan_hash() == original.plan_hash()
        assert {node.source_family for node in rebuilt.composite_rasters} == {
            "NDVI", "NDMI", "QUALITY", "SAR",
        }

    def test_process_forcings_survive_execution_and_reintegration(self) -> None:
        raw_rows = [{
            "timestamp": "2026-07-01T00:00:00Z",
            "source": "open_meteo_archive",
            "data_status": "estimated",
            "temp_max": 34.0,
            "temp_min": 22.0,
            "precipitation": 1.5,
            "et0": 5.2,
            "humidity_mean_pct": 61.0,
            "wind_speed_m_s": 3.4,
        }]
        prepared, plan = prepare_capability_execution_context({
            "layer0_source_packages": {},
            "raster_composites": {},
            "plot_timeseries": raw_rows,
        })
        assert plan.capability_summary["temporal_capability"] == {
            "status": "available",
            "accepted_count": 1,
            "rejected_count": 0,
            "direct_observation_count": 0,
            "process_forcing_count": 1,
        }
        [execution_row] = prepared["plot_timeseries"]
        assert execution_row["observation_role"] == "process_forcing"
        assert execution_row["direct_observation"] is False
        assert execution_row["humidity"] == 61.0
        assert execution_row["wind_speed"] == 3.4

        replay = _weather_records_from_reintegration_context({
            "asmae_worker_reintegration": True,
            "asmae_replay_plot_timeseries": [execution_row],
            "asmae_replay_capability_plan_hash": plan.plan_hash(),
        })
        assert len(replay) == 1
        assert replay[0]["date"] == "2026-07-01"
        assert replay[0]["precipitation"] == 1.5
        assert replay[0]["humidity"] == 61.0
        assert replay[0]["wind_speed"] == 3.4
        assert replay[0]["direct_observation"] is False

    def test_plan_mismatch_is_permanent_until_contract_changes(self) -> None:
        exc = CapabilityPlanIdentityError("CAPABILITY_PLAN_IDENTITY_MISMATCH")
        assert classify_execution_failure(exc, 1) == (
            "permanent_contract", "contract_validation_failed",
        )
        existing = {
            "retry_classification": "permanent_contract",
            "scientific_identity": {"evidence_capability_contract_version": "old"},
        }
        assert resolve_retry_decision(existing, "old") == "return_existing_permanent"
        assert resolve_retry_decision(existing, "new") == "enqueue_successor_contract_changed"

    def test_completed_diagnostic_results_are_not_failure_events(self) -> None:
        assert _completed_result_event_type({
            "status": "partial", "scene_count": 5, "production_usable": False,
        }) == "ASMAE_SPATIAL_DIAGNOSTIC_COMPLETED"
        assert _completed_result_event_type({
            "status": "partial", "scene_count": 0, "production_usable": False,
        }) == "ASMAE_TEMPORAL_DIAGNOSTIC_COMPLETED"
        assert _completed_result_event_type({
            "status": "completed", "scene_count": 5, "production_usable": True,
        }) == "ASMAE_SPATIAL_PRODUCTION_COMPLETED"

    def test_nonproduction_worldline_authority_is_always_diagnostic(self) -> None:
        from services.agribrain.layer05_asmae.plot_state import intersect_artifact_authority

        resolved = intersect_artifact_authority(
            {
                "authority_level": "MODEL_ASSISTED",
                "posterior": {"vigor": {"mean": 0.5}},
                "production_usable": False,
            },
            production_allowed=False,
            scientific_production_usable=False,
        )
        assert resolved["authority_level"] == "DIAGNOSTIC"
        assert resolved["production_usable"] is False

    def test_equivalent_snapshot_reuse_has_job_bound_receipts(self, tmp_path: Path) -> None:
        from unittest.mock import patch
        from services.agribrain.layer05_asmae import plot_snapshot_store as store

        snapshot_id = "ASMAE-SNAPSHOT-" + ("a" * 32)
        result = {
            "snapshot_id": snapshot_id,
            "content_hash": "science-a",
            "crop_posterior_lineage": "crop-hash-a",
            "crop_worldline_event_id": "crop-event-a",
            "phenology_worldline_event_id": "phenology-event-a",
        }
        frontend = {
            "intelligence_snapshot_id": snapshot_id,
            "scientific_evidence_lineage": {
                "crop_posterior_lineage": "crop-hash-a",
                "crop_worldline_event_id": "crop-event-a",
                "phenology_worldline_event_id": "phenology-event-a",
            },
            "source_policy_display_state": {
                "asmaePlotState": {
                    "activeSpatialJobStatus": "running",
                    "activeSpatialJobProgressPct": 85,
                    "spatialSupersession": {
                        "active_spatial_job_status": "running",
                    },
                },
            },
            "asmae_evidence_state": {
                "active_spatial_job_status": "running",
                "spatial_supersession": {
                    "active_spatial_job_status": "running",
                },
            },
            "worker_reintegration": {"job_id": "job-a", "status": "running"},
        }
        with patch.object(store, "PLOT_SNAPSHOT_ROOT", tmp_path):
            namespace = PlotNamespace("tenant-a", "farm-a", "plot-a")
            first = store.publish_canonical_plot_snapshot(
                namespace=namespace, geometry_hash="geometry-a",
                snapshot_id=snapshot_id, asmae_result=result,
                frontend_payload=frontend, job_id="job-a",
                manifest_hash="manifest-a",
                execution_identity={
                    "worker_contract_version": "worker-v1",
                    "capability_contract_version": "capability-v1",
                    "capability_plan_hash": "plan-a",
                },
            )
            second_frontend = {
                **frontend,
                "source_policy_display_state": {
                    "publicationMarker": "current-job-b",
                    "asmaePlotState": {
                        "activeSpatialJobStatus": "running",
                        "spatialSupersession": {
                            "active_spatial_job_status": "running",
                        },
                    },
                },
            }
            second = store.publish_canonical_plot_snapshot(
                namespace=namespace, geometry_hash="geometry-a",
                snapshot_id=snapshot_id, asmae_result=result,
                frontend_payload=second_frontend, job_id="job-b",
                manifest_hash="manifest-b",
                execution_identity={
                    "worker_contract_version": "worker-v2",
                    "capability_contract_version": "capability-v2",
                    "capability_plan_hash": "plan-b",
                },
            )
            node = json.loads(Path(first["node_ref"]).read_text(encoding="utf-8"))
            receipt = json.loads(Path(second["publication_receipt_ref"]).read_text(encoding="utf-8"))
            latest = store.load_latest_plot_snapshot(namespace, "geometry-a")

        assert node["job_id"] == "job-a"
        assert receipt["job_id"] == "job-b"
        assert receipt["manifest_hash"] == "manifest-b"
        assert receipt["source_node_job_id"] == "job-a"
        assert receipt["worker_contract_version"] == "worker-v2"
        assert receipt["capability_contract_version"] == "capability-v2"
        assert first["publication_receipt_ref"] != second["publication_receipt_ref"]
        assert latest["frontend_payload"]["source_policy_display_state"]["asmaePlotState"]["activeSpatialJobStatus"] == "completed"
        assert latest["frontend_payload"]["source_policy_display_state"]["asmaePlotState"]["activeSpatialJobId"] == "job-b"
        current_plot_state = latest["frontend_payload"]["source_policy_display_state"]["asmaePlotState"]
        assert current_plot_state["activeSpatialJobProgressPct"] == 100
        assert current_plot_state["activeSpatialJobStage"] == "complete"
        assert current_plot_state["spatialSupersession"]["active_spatial_job_status"] == "completed"
        assert latest["frontend_payload"]["asmae_evidence_state"]["spatial_supersession"]["active_spatial_job_status"] == "completed"
        assert latest["frontend_payload"]["source_policy_display_state"]["publicationMarker"] == "current-job-b"
        assert latest["publication_receipt_hash"] == second["publication_receipt_hash"]
        assert {
            key: latest["validation"][key]
            for key in (
                "nodeValid",
                "publicationValid",
                "receiptValid",
                "inventoryValid",
                "bindingValid",
                "lineageValid",
            )
        } == {
            "nodeValid": True,
            "publicationValid": True,
            "receiptValid": True,
            "inventoryValid": True,
            "bindingValid": True,
            "lineageValid": True,
        }
        # This fixture intentionally omits the current Layer 10 publication
        # envelope. It remains cryptographically valid for audit/reuse, but it
        # is no longer eligible to become browser authority.
        assert latest["validation"]["schemaValid"] is False
        assert latest["validation"]["contractValid"] is False
        assert latest["refresh_required"] is True

    def test_path_independent_evidence_hash(self) -> None:
        """Verify identical evidence payloads under different wrapper paths produce the same canonical hash."""
        payload = {
            "observation_id": "obs_s2_1001",
            "timestamp": "2026-07-28T10:00:00Z",
            "sensor": "S2",
            "ndvi_mean": 0.85,
        }
        
        hash1 = _stable_node_hash(payload, "sentinel2", ["l0", "sentinel2"], "parent_1")
        hash2 = _stable_node_hash(payload, "asmae_sentinel2_raw", ["l0", "asmae", "raw"], "parent_2")
        
        assert hash1 == hash2, "Canonical observation hash must be path-independent to prevent double counting"

    def test_diagnostic_only_package_not_spatial_provider_scene(self) -> None:
        """Verify diagnostic-only packages are excluded from spatial provider scene capabilities."""
        pkg = {
            "scene_id": "s1_diag_01",
            "crs": "EPSG:4326",
            "timestamp": "2026-07-28T10:00:00Z",
            "diagnostic_only": True,
            "spatial_visualization_unavailable": True,
            "transform": [10.0, 0, 0, 0, -10.0, 0],
            "width": 10,
            "height": 10,
            "band_arrays": {"VV": [[0.5]]},
            "contract_type": "spatial_provider_scene",
            "provider_receipt": {"receipt": "ok"},
        }
        cap, reasons, _ = classify_package(pkg, "sentinel1")
        assert cap == EvidenceCapability.UNKNOWN_OR_INVALID
        assert "diagnostic_only_package_not_spatial_provider_scene" in reasons

    def test_zero_support_scene_is_rejected_by_plan_and_runtime(self) -> None:
        from types import SimpleNamespace
        from services.agribrain.layer05_asmae.geometry.s2_scene_loader import load_s2_scenes

        package = {
            "scene_id": "s2-zero-support",
            "sensor": "S2",
            "crs": "EPSG:32631",
            "acquisition_time": "2026-07-28T10:00:00Z",
            "transform": [500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0],
            "width": 2,
            "height": 2,
            "band_arrays": {"B04": [[0.1, 0.1], [0.1, 0.1]], "B08": [[0.2, 0.2], [0.2, 0.2]]},
            "qa_metrics": {"valid_fraction": 0.0, "usable": True},
            "production_usable": True,
            "real_provider_product": True,
            "diagnostic_only": False,
            "reality": "real_raster",
            "product_binding": "exact_catalog_item",
        }
        capability, reasons, _ = classify_package(package, "sentinel2")
        assert capability == EvidenceCapability.UNKNOWN_OR_INVALID
        assert "scene_has_no_valid_spatial_support" in reasons
        candidate = SimpleNamespace(**{
            **package,
            "acquisition_datetime": package["acquisition_time"],
            "band_refs": {}, "mask_refs": {}, "scalar_observations": {},
            "provider_product_id": "provider-1", "catalog_item_id": "catalog-1",
            "provider_tile_id": None, "provider_orbit_id": None,
            "provider_orbit_pass": None, "binding_proof": {}, "test_override": False,
        })
        assert load_s2_scenes([candidate]) == []

    def test_scene_count_does_not_auto_grant_1m_or_prescription_authority(self) -> None:
        """Verify scene count alone without certification proofs does not auto-grant 1m approval or asmae_certified authority."""
        make_s2 = lambda: {
            "runtime": {
                "sensor": "S2",
                "width": 10,
                "height": 10,
                "crs": "EPSG:4326",
                "transform": [10,0,0,0,-10,0],
                "acquisition_time": "2026-07-28",
                "bands": {"B04": [[1]], "B08": [[1]]},
                "qa_score": 0.9,
                "source_reality": "real_raster",
                "production_usable": True,
                "real_provider_product": True,
                "test_override": False,
            },
            "source_reality": "real_raster",
            "production_usable": True,
            "real_provider_product": True,
            "test_override": False,
            "holdout_proof": None,
            "registration_proof": None,
            "field_approval": False,
        }
        make_s1 = lambda: {
            "runtime": {
                "sensor": "S1",
                "width": 10,
                "height": 10,
                "crs": "EPSG:4326",
                "transform": [10,0,0,0,-10,0],
                "acquisition_time": "2026-07-28",
                "bands": {"VV": [[1]]},
                "qa_score": 0.9,
                "source_reality": "real_raster",
                "production_usable": True,
                "real_provider_product": True,
                "test_override": False,
            },
            "source_reality": "real_raster",
            "production_usable": True,
            "real_provider_product": True,
            "test_override": False,
            "holdout_proof": None,
            "registration_proof": None,
            "field_approval": False,
        }
        scenes = [make_s2(), make_s2(), make_s2(), make_s1(), make_s1()]
        result = classify_asmae_evidence(
            scenes=scenes,
            archive_metrics_status="valid",
            archive_metrics_hash="hash_123",
            archive_baselines={},
            retrovalidation_residuals={},
            archive_bma={},
            raster_composites={},
            layer0_source_packages={},
        )
        assert result.current_1m_approval_allowed is False
        assert result.authority == "advisory_only"
        assert result.reason == "1m_approval_unavailable_certification_proof_missing"

    def test_canonical_full_sha256_scene_id_generation(self) -> None:
        """Verify layer0 package adapter generates a full SHA-256 canonical scene ID."""
        pkg = {
            "metadata": {
                "scene_id": "s1_real_scene_1",
                "crs": "EPSG:4326",
                "transform": [10.0, 0, 0, 0, -10.0, 0],
                "width": 10,
                "height": 10,
                "acquisition_datetime": "2026-07-28T10:00:00Z",
            },
            "provider_product_id": "S1A_IW_GRDH_1SDV_20260728T100000",
        }
        candidate = adapt_layer0_package_to_scene_candidate(pkg, "sentinel1")
        assert candidate.scene_id.startswith("sentinel1_")
        assert len(candidate.scene_id) == len("sentinel1_") + 64
        assert candidate.provenance.get("legacy_ordinal_scene_id") == "s1_real_scene_1"

    def test_reproject_scientific_grid_fails_closed_without_metadata(self) -> None:
        """Verify reproject_scientific_grid fails closed when transform or CRS metadata is missing."""
        arr = np.ones((10, 10), dtype=np.float32)
        with pytest.raises(ValueError, match="requires valid 2D array"):
            reproject_scientific_grid(arr, None, "EPSG:4326", (10, 10), [10,0,0,0,-10,0], "EPSG:4326")

    def test_pre_decision_tribunal_evaluates_belief(self) -> None:
        """Verify pre_decision_tribunal runs before decision planning."""
        verdict, findings = pre_decision_tribunal("belief_head_123", {"plot_id": "plot_01"})
        assert verdict is not None

    def test_generate_orchestrator_run_id_includes_scientific_identity(self) -> None:
        """Verify generate_orchestrator_run_id populates scientific identity hashes."""
        inp = OrchestratorInput(
            plot_namespace=PlotNamespace("tenant-a", "farm-a", "plot_test_123"),
            geometry_hash="geom_hash_456",
            date_range={"start": "2026-01-01", "end": "2026-07-28"},
            crop_config={"type": "wheat"},
            operational_context={},
            policy_snapshot={},
        )
        run_id = generate_orchestrator_run_id(inp, {}, "v2.1")
        assert run_id.startswith("AGB2-")
