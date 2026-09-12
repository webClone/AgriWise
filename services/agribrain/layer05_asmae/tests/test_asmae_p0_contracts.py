from __future__ import annotations

import tempfile
import unittest
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from services.agribrain.common.plot_namespace import PlotNamespace

import services.agribrain.layer05_asmae.assimilation.filter as enkf_filter
from services.agribrain.layer05_asmae.assimilation.filter import (
    _batch_scalar_etkf_target_update,
    _etkf_target_update,
    _forecast_elapsed_interval,
    _predict_observation_array,
    _scene_has_pixel_obs,
    has_observation_in_stack,
    run_enkf,
)
from services.agribrain.layer05_asmae.cache import stable_value_hash
from services.agribrain.layer05_asmae.chain_integrity import (
    ASMAEChainIntegrityError,
    assert_scene_operator_binding,
    compute_h_matrix_digest,
)
from services.agribrain.layer05_asmae.constraints.radiometric import (
    enforce_radiometric_consistency,
)
from services.agribrain.layer05_asmae.evidence_capability import prepare_capability_execution_context
from services.agribrain.layer05_asmae.geometry.layer0_package_adapter import adapt_layer0_package_to_scene_candidate
from services.agribrain.layer05_asmae.geometry.support_contract import build_scene_valid_support
from services.agribrain.world_model.canonical_worldline import CanonicalWorldlineService
from services.agribrain.layer05_asmae.history.resolution_evidence_builder import build_resolution_evidence
from services.agribrain.layer05_asmae.history.historical_scene_adapter import HistoricalSceneAdapter
from services.agribrain.layer05_asmae.graph.microzone_graph import (
    MicrozoneEdge,
    MicrozoneGraph,
    MicrozoneNode,
)
from services.agribrain.layer05_asmae.graph.spatial_regularization import (
    apply_ensemble_graph_regularization,
)
from services.agribrain.layer05_asmae.observation.pixel_extraction import extract_pixel_observations
from services.agribrain.layer05_asmae.observation.s2_forward_model import predict_observation
from services.agribrain.layer05_asmae.observation.s1_sar_model import predict_sar_observation
from services.agribrain.layer05_asmae.resolution.resource_planner import plan_resolution
from services.agribrain.layer05_asmae.resolution.evaluator import (
    _compute_shift_diversity,
    _gramian_proxy,
    _score_prior_confidence,
)
from services.agribrain.layer05_asmae.resilient_posterior import (
    estimate_resilient_plot_posterior,
)
from services.agribrain.layer05_asmae.retrovalidation.future_projection import predict_held_out_scene
from services.agribrain.layer0.asmae_scene_products.scene_product_schema import SceneProduct
from services.agribrain.layer0.archive.scene_manifest import HistoricalSceneRecord
from services.agribrain.layer0.archive.archive_fetcher import ArchiveFetcher


def _scene(scene_id: str = "s2-a") -> SimpleNamespace:
    return SimpleNamespace(
        scene_id=scene_id,
        sensor="S2",
        acquisition_time="2026-07-01T00:00:00+00:00",
        crs="EPSG:32631",
        transform=(500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0),
        width=2,
        height=2,
        source_reality="real_raster",
        band_arrays={"B04": np.ones((2, 2)), "B08": np.full((2, 2), 2.0)},
        bands={
            "B04": np.ones((2, 2)),
            "B05": np.ones((2, 2)),
            "B06": np.full((2, 2), 2.0),
            "B08": np.full((2, 2), 4.0),
        },
        masks={"SCL": np.full((2, 2), 9), "DATAMASK": np.zeros((2, 2))},
        valid_support=None,
        valid_support_hash="",
    )


class AtomicEvidenceTests(unittest.TestCase):
    def test_vectorized_graph_regularization_matches_scalar_equations(self):
        graph = MicrozoneGraph(10, "geometry", n_rows=1, n_cols=4)
        node_ids = [f"mz_000_{column:03d}" for column in range(4)]
        for column, node_id in enumerate(node_ids):
            graph.add_node(MicrozoneNode(node_id, 0, column, 10))
        for column in range(3):
            graph.add_edge(MicrozoneEdge(
                node_ids[column], node_ids[column + 1],
                distance_weight=0.7 + 0.1 * column,
            ))

        generator = np.random.default_rng(9182)
        values = generator.uniform(0.2, 0.8, size=(4, 5, len(enkf_filter.STATE_NAMES)))
        ensemble = {
            node_id: values[position].tolist()
            for position, node_id in enumerate(node_ids)
        }
        expected = {
            node: [list(member) for member in members]
            for node, members in ensemble.items()
        }
        strengths = {"vigor": 0.04, "canopy_water": 0.06}
        for member_index in range(5):
            current = {node: ensemble[node][member_index] for node in node_ids}
            proposed = {node: list(current[node]) for node in node_ids}
            for state_name in ("vigor", "canopy_water"):
                state_index = enkf_filter.STATE_NAMES.index(state_name)
                original_mean = np.mean([current[node][state_index] for node in node_ids])
                for node in node_ids:
                    neighbours = []
                    for edge in graph.neighbors(node):
                        neighbour = edge.target if edge.source == node else edge.source
                        neighbours.append((edge.combined_weight, current[neighbour][state_index]))
                    weight_total = sum(weight for weight, _ in neighbours)
                    if weight_total:
                        neighbour_mean = sum(weight * value for weight, value in neighbours) / weight_total
                        alpha = strengths[state_name]
                        proposed[node][state_index] = (
                            (1.0 - alpha) * current[node][state_index]
                            + alpha * neighbour_mean
                        )
                correction = original_mean - np.mean([
                    proposed[node][state_index] for node in node_ids
                ])
                low, high = enkf_filter.STATE_BOUNDS[state_name]
                for node in node_ids:
                    proposed[node][state_index] = min(
                        high, max(low, proposed[node][state_index] + correction),
                    )
            for node in node_ids:
                expected[node][member_index] = proposed[node]

        actual, report = apply_ensemble_graph_regularization(
            ensemble, graph, ["vigor", "canopy_water"],
        )
        self.assertTrue(report["applied"])
        for node_id in node_ids:
            np.testing.assert_allclose(actual[node_id], expected[node_id], atol=1e-12)

    def test_vectorized_forward_models_match_scalar_contracts(self):
        generator = np.random.default_rng(20260826)
        states = np.empty((7, 5, len(enkf_filter.STATE_NAMES)), dtype=float)
        for index, state_name in enumerate(enkf_filter.STATE_NAMES):
            low, high = enkf_filter.STATE_BOUNDS[state_name]
            states[..., index] = generator.uniform(low, high, size=states.shape[:2])

        for observation_name in ("ndvi", "evi", "ndre", "ndmi", "ndwi", "bsi"):
            actual = _predict_observation_array(observation_name, states, "S2")
            expected = np.asarray([
                [predict_observation(observation_name, member) for member in zone]
                for zone in states
            ])
            np.testing.assert_allclose(actual, expected, rtol=0.0, atol=1e-12)

        for observation_name in ("sar_vv", "sar_vh", "sar_ratio", "delta_sar"):
            actual = _predict_observation_array(observation_name, states, "S1")
            expected = np.asarray([
                [predict_sar_observation(observation_name, member) for member in zone]
                for zone in states
            ])
            np.testing.assert_allclose(actual, expected, rtol=0.0, atol=1e-12)

        self.assertIsNone(_predict_observation_array("unsupported", states, "S2"))

    def test_wrapper_is_flattened_into_scene_and_direct_packet(self):
        scene = _scene()
        scene.packets = [{
            "timestamp": "2026-07-01T00:00:00+00:00",
            "data_status": "observed",
            "ndvi_mean": 0.42,
            "observation_id": "obs-1",
        }]
        prepared, plan = prepare_capability_execution_context({
            "layer0_source_packages": {"asmae_sentinel2_real": [scene]},
            "raster_composites": {},
            "plot_timeseries": [],
        })
        self.assertEqual(1, len(plan.spatial_scenes))
        self.assertEqual(1, sum(node.direct_observation for node in plan.temporal_observations))
        self.assertEqual(1, len(prepared["layer0_source_packages"]["asmae_sentinel2_real"]))
        self.assertEqual(1, len(prepared["plot_timeseries"]))
        self.assertTrue(prepared["capability_plan_hash"])

    def test_list_scene_content_changes_hash(self):
        first = [SimpleNamespace(scene_id="a", bands={"B04": np.array([[1.0]])})]
        second = [SimpleNamespace(scene_id="b", bands={"B04": np.array([[2.0]])})]
        self.assertNotEqual(stable_value_hash(first), stable_value_hash(second))

    def test_scene_dict_is_executable_not_only_classifiable(self):
        raw = {
            "scene_id": "scene-dict",
            "sensor": "S2",
            "acquisition_datetime": "2026-07-01T00:00:00+00:00",
            "crs": "EPSG:32631",
            "transform": [500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0],
            "width": 2,
            "height": 2,
            "band_arrays": {"B04": np.ones((2, 2)), "B08": np.full((2, 2), 2.0)},
            "mask_refs": {},
            "source_reality": "real_raster",
            "production_usable": False,
            "diagnostic_only": True,
        }
        candidate = adapt_layer0_package_to_scene_candidate(raw, "sentinel2", {})
        self.assertEqual("scene-dict", candidate.provenance.get("legacy_ordinal_scene_id"))
        self.assertTrue(candidate.scene_id.startswith("sentinel2_"))
        self.assertFalse(candidate.production_usable)
        self.assertTrue(candidate.diagnostic_only)

    def test_empty_scalar_packet_is_not_mean_evidence(self):
        package = SimpleNamespace(
            metadata=SimpleNamespace(
                scene_id="empty-means",
                acquisition_datetime=datetime(2026, 7, 1, tzinfo=timezone.utc),
                crs="EPSG:32631",
                transform=None,
                width=None,
                height=None,
            ),
            packets=[{"ndvi_mean": None, "evi_mean": float("nan")}],
        )
        candidate = adapt_layer0_package_to_scene_candidate(package, "sentinel2", {})
        self.assertEqual("unavailable", candidate.reality)
        self.assertEqual({}, candidate.scalar_observations)

    def test_hash_only_historical_manifest_never_invents_spatial_evidence(self):
        record = HistoricalSceneRecord(
            scene_id="archive-no-affine",
            plot_id="plot-a",
            geometry_hash="geometry-hash",
            source="sentinel2",
            mission="S2A",
            product_level="L2A",
            collection="sentinel-2-l2a",
            acquisition_time="2026-07-01T00:00:00Z",
            orbit_number=None,
            relative_orbit=None,
            tile_id="T31SUD",
            native_resolution_m=10.0,
            crs="EPSG:32631",
            transform_hash="transform-hash-only",
            footprint_hash="footprint-hash",
            cloud_score=0.0,
            valid_pixel_fraction=1.0,
            quality_status="accepted",
            source_content_hash="content-hash",
            bands_available=["B04", "B08"],
            local_cache_refs={},
        )
        package = HistoricalSceneAdapter().adapt(record)
        self.assertIsNone(package.metadata.transform)
        self.assertIsNone(package.metadata.width)
        self.assertFalse(package.qa.usable)
        self.assertNotIn("ndvi_mean", package.packets[0])
        self.assertFalse(package.production_usable)
        candidate = adapt_layer0_package_to_scene_candidate(package, "sentinel2", {})
        self.assertEqual("unavailable", candidate.reality)

    def test_offline_archive_fixtures_require_explicit_test_override(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(
            os.environ,
            {"AGRIWISE_ARCHIVE_OFFLINE": "true", "ASMAE_TEST_OVERRIDE": "false"},
        ):
            fetcher = ArchiveFetcher(cache_dir=root)
            with self.assertRaisesRegex(RuntimeError, "explicit_test_override"):
                fetcher.orchestrate_fetch(
                    plot_id="plot-a",
                    geometry_wkt="POLYGON ((2 36, 2.1 36, 2.1 36.1, 2 36.1, 2 36))",
                    start_date="2026-01-01",
                    end_date="2026-02-01",
                    sources=["sentinel2"],
                )


class PixelSupportTests(unittest.TestCase):
    def test_cloud_datamask_and_nonfinite_values_are_rejected(self):
        scene = _scene()
        support = build_scene_valid_support(scene)
        self.assertEqual(0, support["valid_pixel_count"])
        observations = extract_pixel_observations(scene)
        self.assertEqual(0, observations["ndre"].n_valid)
        self.assertTrue(all(not value for value in observations["ndre"].valid_mask))

    def test_ndre_uses_b06_over_b05(self):
        scene = _scene()
        scene.masks = {"SCL": np.full((2, 2), 4), "DATAMASK": np.ones((2, 2))}
        build_scene_valid_support(scene)
        ndre = extract_pixel_observations(scene)["ndre"]
        self.assertTrue(all(abs(value - (1.0 / 3.0)) < 1e-9 for value in ndre.values))

    def test_precomputed_nan_is_not_valid(self):
        scene = _scene()
        scene.bands = {"NDVI": np.array([[np.nan, 0.5], [0.4, 0.3]])}
        scene.masks = {"DATAMASK": np.ones((2, 2))}
        build_scene_valid_support(scene)
        ndvi = extract_pixel_observations(scene)["ndvi"]
        self.assertFalse(ndvi.valid_mask[0])
        self.assertTrue(np.isfinite(ndvi.mean))

    def test_thin_cirrus_is_not_marginal_assimilation_support(self):
        scene = _scene()
        scene.masks = {"SCL": np.full((2, 2), 10), "DATAMASK": np.ones((2, 2))}
        support = build_scene_valid_support(scene)
        self.assertEqual(0, support["valid_pixel_count"])

    def test_sensor_name_or_invalid_pixels_do_not_claim_state_observation(self):
        scene = _scene()
        build_scene_valid_support(scene)
        self.assertFalse(has_observation_in_stack([scene], "vigor"))
        self.assertFalse(_scene_has_pixel_obs(scene))


class InferenceCoreTests(unittest.TestCase):
    def test_missing_prior_has_zero_resolution_credit(self):
        self.assertEqual(0.0, _score_prior_confidence(1, None, []))
        self.assertEqual(0.0, _score_prior_confidence(1, {"mean_confidence": float("nan")}, []))

    def test_only_accepted_image_registration_counts_as_shift_diversity(self):
        results = [
            SimpleNamespace(
                accepted=True,
                method="geospatial_grid_only",
                confidence=0.25,
                shift_x_m=2.0,
                shift_y_m=3.0,
            ),
            SimpleNamespace(
                accepted=False,
                method="phase_gradient:NDVI",
                confidence=0.9,
                shift_x_m=4.0,
                shift_y_m=5.0,
            ),
        ]
        self.assertEqual(0.0, _compute_shift_diversity(results, 10))

    def test_deterministic_etkf_is_member_order_equivariant(self):
        members = [[0.2], [0.4], [0.7], [0.9]]
        predicted = np.asarray([[0.2, 0.4, 0.7, 0.9]])
        forward = {"mz": [list(member) for member in members]}
        reverse = {"mz": [list(member) for member in reversed(members)]}
        _etkf_target_update(forward, ["mz"], [0], predicted, np.array([0.6]), 0.04)
        _etkf_target_update(reverse, ["mz"], [0], predicted[:, ::-1], np.array([0.6]), 0.04)
        self.assertTrue(np.allclose(
            sorted(member[0] for member in forward["mz"]),
            sorted(member[0] for member in reverse["mz"]),
        ))

    def test_batched_scalar_etkf_matches_independent_zone_updates(self):
        node_ids = ["mz-0", "mz-1", "mz-2"]
        members = {
            node_id: [
                [0.1 + zone * 0.05 + member * 0.08, 0.7 - member * 0.04]
                for member in range(5)
            ]
            for zone, node_id in enumerate(node_ids)
        }
        predicted = np.asarray([
            [0.2, 0.3, 0.5, 0.6, 0.8],
            [0.1, 0.4, 0.45, 0.7, 0.9],
            [0.3, 0.35, 0.55, 0.72, 0.81],
        ])
        observed = np.asarray([0.52, 0.61, 0.47])
        expected = {
            node: [list(member) for member in node_members]
            for node, node_members in members.items()
        }
        actual = {
            node: [list(member) for member in node_members]
            for node, node_members in members.items()
        }
        for position, node_id in enumerate(node_ids):
            _etkf_target_update(
                expected,
                [node_id],
                [0, 1],
                predicted[position : position + 1, :],
                observed[position : position + 1],
                0.04,
            )
        _batch_scalar_etkf_target_update(
            actual,
            node_ids,
            [0, 1],
            predicted,
            observed,
            0.04,
            np.arange(len(node_ids)),
        )
        for node_id in node_ids:
            self.assertTrue(np.allclose(expected[node_id], actual[node_id]))

    def test_scene_operator_binding_is_exact(self):
        scenes = [
            SimpleNamespace(scene_id="s1", valid_support_hash="h", crs="EPSG:32631", width=1, height=1),
            SimpleNamespace(scene_id="s2", valid_support_hash="h", crs="EPSG:32631", width=1, height=1),
        ]
        operators = [
            SimpleNamespace(scene_id="s1", valid_support_hash="h", source_crs="EPSG:32631", H_matrix=np.ones((1, 1))),
            SimpleNamespace(scene_id="s3", valid_support_hash="h", source_crs="EPSG:32631", H_matrix=np.ones((1, 1))),
        ]
        with self.assertRaises(ASMAEChainIntegrityError):
            assert_scene_operator_binding(scenes, operators, "test")

    def test_phantom_holdout_prediction_is_unavailable(self):
        result = predict_held_out_scene({}, _scene(), operator=None)
        self.assertNotEqual("predicted", result["status"])
        self.assertIsNone(result["mean_error"])
        self.assertEqual({}, result["errors"])

    def test_forward_model_rejects_unsupported_state_instead_of_crashing(self):
        state = [None] * 13
        self.assertIsNone(predict_observation("bsi", state))

    def test_radiometry_rejects_pixel_count_mismatch_without_resampling(self):
        from scipy import sparse

        scene = SimpleNamespace(
            scene_id="misaligned",
            sensor="S2",
            acquisition_time=datetime(2026, 7, 1, tzinfo=timezone.utc),
            crs="EPSG:32631",
            transform=(500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0),
            width=2,
            height=2,
            bands={"NDVI": np.asarray([[0.2, 0.3, 0.4]])},
            masks={},
            valid_support=np.ones((2, 2), dtype=bool),
            valid_support_hash="support-a",
        )
        operator = SimpleNamespace(
            scene_id=scene.scene_id,
            source_crs=scene.crs,
            valid_support_hash=scene.valid_support_hash,
            H_matrix=sparse.csr_matrix(np.ones((4, 1), dtype=float)),
        )
        result = enforce_radiometric_consistency(
            {"mz": [0.5] * 13},
            {},
            {},
            operators=[operator],
            scenes=[scene],
        )
        record = result["per_index"]["ndvi"]
        self.assertEqual("reject", record["status"])
        self.assertEqual("ht_support_mismatch", record["predicted_method"])
        self.assertIsNone(record["rmse"])
        self.assertFalse(result["full_radiometric_credit_allowed"])
        self.assertTrue(result["has_alignment_rejection"])

    def test_large_operator_digest_covers_unsampled_middle_values(self):
        from scipy import sparse

        size = 60_010
        indices = np.arange(size, dtype=np.int32)
        indptr = np.asarray([0, size], dtype=np.int32)
        first_data = np.ones(size, dtype=np.float64)
        second_data = first_data.copy()
        first_data[20_000], first_data[20_001] = 2.0, 3.0
        second_data[20_000], second_data[20_001] = 3.0, 2.0
        first = sparse.csr_matrix(
            (first_data, indices, indptr), shape=(1, size),
        )
        second = sparse.csr_matrix(
            (second_data, indices, indptr), shape=(1, size),
        )
        self.assertNotEqual(
            compute_h_matrix_digest(first),
            compute_h_matrix_digest(second),
        )

    def test_gramian_proxy_evaluates_columns_beyond_first_fifty(self):
        from scipy import sparse

        rows = []
        columns = []
        values = []
        for index in range(50):
            rows.append(index)
            columns.append(index)
            values.append(1.0)
        for index in range(50, 110):
            rows.append(50)
            columns.append(index)
            values.append(1.0)
        matrix = sparse.csr_matrix(
            (values, (rows, columns)), shape=(51, 110),
        )
        score = _gramian_proxy([SimpleNamespace(H_matrix=matrix)])
        self.assertIsNotNone(score)
        self.assertGreater(score, 0.60)
        self.assertLess(score, 0.80)

    def test_resilient_initialization_excludes_later_window_evidence(self):
        common = {
            "archive_posterior": {},
            "geometry_hash": "geometry-a",
            "crop_context": {},
            "weather_daily_series": {},
            "coarse_layer_outputs": {},
            "soil_context": {},
            "end_date": date(2026, 7, 3),
        }
        early = {
            "timestamp": "2026-07-01T12:00:00Z",
            "ndvi": 0.20,
            "ndvi_uncertainty": 0.01,
            "quality": 1.0,
        }
        later = {
            "timestamp": "2026-07-02T12:00:00Z",
            "ndvi": 0.90,
            "ndvi_uncertainty": 0.01,
            "quality": 1.0,
        }
        cutoff = datetime(2026, 7, 1, 23, 59, tzinfo=timezone.utc)
        early_only = estimate_resilient_plot_posterior(
            SimpleNamespace(**common, plot_timeseries=[early]),
            as_of=cutoff,
        )
        future_present = estimate_resilient_plot_posterior(
            SimpleNamespace(**common, plot_timeseries=[early, later]),
            as_of=cutoff,
        )
        unbounded = estimate_resilient_plot_posterior(
            SimpleNamespace(**common, plot_timeseries=[early, later]),
        )
        self.assertEqual(
            early_only["plot_level_posterior"]["vigor"]["mean"],
            future_present["plot_level_posterior"]["vigor"]["mean"],
        )
        self.assertNotEqual(
            early_only["plot_level_posterior"]["vigor"]["mean"],
            unbounded["plot_level_posterior"]["vigor"]["mean"],
        )

    def test_elapsed_forecast_splits_days_and_applies_event_once(self):
        calls = []

        def fake_forecast(ensemble, *args, **kwargs):
            calls.append({
                "delta_days": kwargs["delta_days"],
                "events": list(kwargs["management_events"]),
                "day": kwargs["process_day"],
            })
            return ensemble

        start = datetime(2026, 7, 1, 12, tzinfo=timezone.utc)
        end = datetime(2026, 7, 3, 12, tzinfo=timezone.utc)
        event = {
            "timestamp": "2026-07-02T06:00:00Z",
            "type": "irrigation",
            "amount_mm": 12,
        }
        with patch.object(enkf_filter, "forecast_step", side_effect=fake_forecast):
            _, segments = _forecast_elapsed_interval(
                {"mz": [[0.0] * 13]},
                start,
                end,
                {},
                {},
                __import__("random").Random(1),
                [],
                {},
                {},
                [event],
            )
        self.assertAlmostEqual(2.0, sum(item["delta_days"] for item in segments))
        self.assertEqual(3, len(calls))
        self.assertEqual(1, sum(len(item["events"]) for item in calls))

    def test_learning_memory_is_applied_only_during_initialization(self):
        from scipy import sparse

        scenes = []
        operators = []
        for index, stamp in enumerate((
            datetime(2026, 7, 1, tzinfo=timezone.utc),
            datetime(2026, 7, 2, tzinfo=timezone.utc),
            datetime(2026, 7, 3, tzinfo=timezone.utc),
        )):
            scene_id = f"blank-{index}"
            support_hash = f"support-{index}"
            scenes.append(SimpleNamespace(
                scene_id=scene_id,
                sensor="S2",
                acquisition_time=stamp,
                crs="EPSG:32631",
                transform=(500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0),
                width=1,
                height=1,
                bands={},
                masks={},
                valid_support=np.ones((1, 1), dtype=bool),
                valid_support_hash=support_hash,
            ))
            operators.append(SimpleNamespace(
                scene_id=scene_id,
                source_crs="EPSG:32631",
                valid_support_hash=support_hash,
                H_matrix=sparse.csr_matrix([[1.0]]),
            ))
        priors = {
            "learning_memory": {
                "usable_as_prior": True,
                "status": "available",
                "memory_data": {
                    "memory_status": "candidate",
                    "variables": {
                        "recurring_stress_zone": {
                            "value": 0.8,
                            "trust": 1.0,
                            "confidence": 1.0,
                            "evidence_count": 5,
                        },
                    },
                },
            },
        }
        with patch.object(
            enkf_filter,
            "blend_learning_memory",
            wraps=enkf_filter.blend_learning_memory,
        ) as blend:
            result = run_enkf(
                scenes,
                operators,
                {"n_rows": 1, "n_cols": 1, "node_count": 1},
                priors,
                resolution_m=10,
                mode="shadow",
            )
        self.assertEqual(1, blend.call_count)
        self.assertEqual(0.1, result["memory_blend_weight"])


class AuthorityAndResourceTests(unittest.TestCase):
    def test_scene_authority_defaults_fail_closed(self):
        product = SceneProduct(
            scene_id="unproven",
            sensor="S2",
            acquisition_datetime=datetime.now(timezone.utc),
            crs="EPSG:32631",
            transform=(500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0),
            width=1,
            height=1,
        )
        self.assertFalse(product.production_usable)
        self.assertFalse(product.real_provider_product)
        self.assertTrue(product.diagnostic_only)
        self.assertFalse(product.usable_for_1m_approval)

    def test_one_metre_plan_rejects_unsafe_allocation(self):
        scene = SimpleNamespace(
            crs="EPSG:32631",
            transform=[500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0],
            width=93,
            height=89,
        )
        plan = plan_resolution(
            scene, 1, "standard",
            SimpleNamespace(resource_memory_limit_mb=768),
        )
        self.assertGreaterEqual(plan["n_microzones"], 827_000)
        self.assertFalse(plan["feasible"])

    def test_broadcast_resolution_maps_do_not_prove_local_support(self):
        evidence = build_resolution_evidence(
            inp=SimpleNamespace(weather_archive_status="available"),
            scene_stack=None,
            local_retro_support={1: {"zone": 0.9}},
            local_archive_map=np.ones((2, 2)),
            local_uncertainty_map=np.ones((2, 2)),
            local_weather_map=np.ones((2, 2)),
            local_scene_depth_map=np.full((2, 2), 3.0),
            local_gap_risk_map=np.zeros((2, 2)),
            evidence_lineage={
                "independent_historical_product": True,
                "excludes_current_run": True,
                "source_hash": "history-a",
            },
        )
        self.assertEqual("unavailable", evidence.evidence_status)
        self.assertIn(
            "local_provider_scene_depth_is_broadcast_or_empty",
            evidence.missing_reasons,
        )
        self.assertIn(
            "local_gap_risk_is_constant_or_empty", evidence.missing_reasons
        )


class WorldlineTests(unittest.TestCase):
    def test_repeated_commit_repairs_missing_head(self):
        with tempfile.TemporaryDirectory() as root:
            service = CanonicalWorldlineService(Path(root))
            event = service.commit_event(
                plot_id="plot-a", event_type="TEST", payload={"value": 1},
                geometry_hash="geometry-a",
                authority="DIAGNOSTIC",
                effective_at="2026-07-28T00:00:00Z",
                observation_or_valid_time="2026-07-28T00:00:00Z",
            )
            service._head_path("plot-a").unlink()
            repeated = service.commit_event(
                plot_id="plot-a", event_type="TEST", payload={"value": 1},
                geometry_hash="geometry-a",
                authority="DIAGNOSTIC",
                effective_at="2026-07-28T00:00:00Z",
                observation_or_valid_time="2026-07-28T00:00:00Z",
            )
            self.assertEqual(event["event_id"], repeated["event_id"])
            self.assertEqual(event["event_id"], service.load_head("plot-a")["latest_event_id"])


class WorkerIdentityTests(unittest.TestCase):
    def test_concurrent_identical_enqueue_spawns_once(self):
        import services.agribrain.layer05_asmae.background_jobs as jobs

        with tempfile.TemporaryDirectory() as root:
            context = {
                "geometry_hash": "geometry-a",
                "capability_plan_hash": "plan-a",
                "execution_plan_hash": "execution-a",
                "quarantine_ledger_hash": "quarantine-a",
                "evidence_capability_contract_version": jobs.EVIDENCE_CAPABILITY_CONTRACT_VERSION,
                "crop_posterior_lineage": "crop-a",
                "layer0_source_packages": {},
            }
            with patch.object(jobs, "JOBS_DIR", Path(root)), patch.object(jobs, "spawn_worker") as spawn:
                with ThreadPoolExecutor(max_workers=12) as pool:
                    results = list(pool.map(
                        lambda index: jobs.enqueue_standard_job(
                            PlotNamespace("tenant-a", "farm-a", "plot-a"),
                            f"run-{index}", context, {}
                        ),
                        range(24),
                    ))
                self.assertEqual(1, spawn.call_count)
                self.assertEqual(1, len({item["job_id"] for item in results}))


if __name__ == "__main__":
    unittest.main()
