# -*- coding: utf-8 -*-
"""
Tests for Biophysical Microzones, Resolution Ladder Promotion, Kalman Assimilation,
BMA Expert Conditioning, Uncertainty Calibration, and Learning Weak Labels.
"""

from __future__ import annotations

import numpy as np
import pytest

from services.agribrain.layer05_asmae.graph.biophysical_microzones import (
    BIO_CLUSTER_CHRONIC_SALINE,
    BIO_CLUSTER_MODERATE_LOAM,
    BIO_CLUSTER_RAPID_DRAINAGE_SAND,
    BIO_CLUSTER_RETENTIVE_FERTILE,
    MicrozoneBiophysicalProfile,
    delineate_biophysical_microzones,
)
from services.agribrain.layer05_asmae.graph.microzone_graph import (
    MicrozoneGraph,
    MicrozoneNode,
    build_microzone_graph,
)
from services.agribrain.layer05_asmae.graph.spatial_regularization import (
    apply_ensemble_graph_regularization,
)
from services.agribrain.layer05_asmae.bma.archive_expert_scoring import ArchiveExpertScoring
from services.agribrain.layer05_asmae.retrovalidation.calibration_score import (
    compute_biophysical_calibration_report,
    compute_calibration_score,
)
from services.agribrain.layer05_asmae.training.exporter import export_weak_labels
from services.agribrain.layer05_asmae.history.event_detector import SeasonalEventRecord
from datetime import datetime, timezone


def test_delineate_biophysical_microzones_profiles():
    """Verify that intra-seasonal events and raster responses produce distinct biophysical clusters."""
    events = [
        SeasonalEventRecord(
            event_id="irr_01",
            event_type="irrigation",
            start_date=datetime(2024, 5, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 5, 3, tzinfo=timezone.utc),
            peak_date=datetime(2024, 5, 2, tzinfo=timezone.utc),
            severity=0.8,
            confidence=0.9,
            sensor_evidence={"sar_delta_db": 2.5},
        ),
        SeasonalEventRecord(
            event_id="drt_01",
            event_type="drought",
            start_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            peak_date=datetime(2024, 6, 14, tzinfo=timezone.utc),
            severity=0.85,
            confidence=0.88,
            sensor_evidence={"cumulative_deficit_mm": 45.0},
        ),
        SeasonalEventRecord(
            event_id="fert_01",
            event_type="fertilization",
            start_date=datetime(2024, 5, 10, tzinfo=timezone.utc),
            end_date=datetime(2024, 5, 22, tzinfo=timezone.utc),
            peak_date=datetime(2024, 5, 20, tzinfo=timezone.utc),
            severity=0.75,
            confidence=0.85,
            sensor_evidence={"ndvi_acceleration": 0.18},
        ),
    ]

    # Mock vigor and water rasters (10x10)
    vigor = np.full((10, 10), 0.60)
    vigor[0:3, 0:3] = 0.20  # saline / stunted corner
    vigor[4:7, 4:7] = 0.75  # fertile center

    water = np.full((10, 10), 0.50)
    water[0:3, 0:3] = 0.48  # saline wet crust
    water[7:10, 7:10] = 0.25 # dry sandy edge

    soil_clusters, irr_groups, profiles = delineate_biophysical_microzones(
        n_rows=10,
        n_cols=10,
        target_origin_x=0.0,
        target_origin_y=100.0,
        resolution_m=10,
        events=events,
        base_raster_vigor=vigor,
        base_raster_water=water,
    )

    assert len(soil_clusters) == 100
    assert len(irr_groups) == 100
    assert len(profiles) == 100

    # Verify saline detection in the stunted corner
    saline_profile = profiles["mz_001_001"]
    assert saline_profile.biophysical_cluster_id == BIO_CLUSTER_CHRONIC_SALINE
    assert saline_profile.salinity_persistence_index >= 0.50

    # Verify retentive / fertile in center
    fertile_profile = profiles["mz_005_005"]
    assert fertile_profile.biophysical_cluster_id == BIO_CLUSTER_RETENTIVE_FERTILE
    assert fertile_profile.nutrient_response_index >= 0.50

    # Verify rapid drainage on the dry sandy perimeter
    sandy_profile = profiles["mz_009_009"]
    assert sandy_profile.water_retention_index <= 0.45


def test_microzone_graph_boundary_preservation():
    """Verify that edges crossing biophysical clusters get suppressed weight (0.3)."""
    soil_clusters = {
        "mz_000_000": BIO_CLUSTER_RETENTIVE_FERTILE,
        "mz_000_001": BIO_CLUSTER_RETENTIVE_FERTILE,
        "mz_000_002": BIO_CLUSTER_CHRONIC_SALINE,  # Boundary between col 1 and 2
    }
    irr_groups = {
        "mz_000_000": "irr_sector_0",
        "mz_000_001": "irr_sector_0",
        "mz_000_002": "irr_sector_0",
    }

    graph = build_microzone_graph(
        resolution_m=10,
        n_pixel_rows=1,
        n_pixel_cols=3,
        pixel_size_m=10.0,
        target_origin_x=0.0,
        target_origin_y=10.0,
        soil_clusters=soil_clusters,
        irrigation_groups=irr_groups,
    )

    # Edge between same cluster (mz_000_000 <-> mz_000_001)
    edges_from_0 = [e for e in graph.neighbors("mz_000_000") if e.target == "mz_000_001"]
    assert len(edges_from_0) == 1
    assert edges_from_0[0].soil_similarity_weight == 1.0

    # Edge crossing biophysical cluster boundary (mz_000_001 <-> mz_000_002)
    edges_boundary = [e for e in graph.neighbors("mz_000_001") if e.target == "mz_000_002"]
    assert len(edges_boundary) == 1
    # Different soil cluster weight is 0.3
    assert abs(edges_boundary[0].soil_similarity_weight - 0.3) < 1e-5
    assert edges_boundary[0].combined_weight < edges_from_0[0].combined_weight


def test_kalman_ensemble_graph_regularization_with_biophysical_clusters():
    """Verify Kalman assimilation spatial regularization respects biophysical boundaries."""
    soil_clusters = {
        "mz_000_000": BIO_CLUSTER_RETENTIVE_FERTILE,
        "mz_000_001": BIO_CLUSTER_CHRONIC_SALINE,
    }
    graph = build_microzone_graph(
        resolution_m=10,
        n_pixel_rows=1,
        n_pixel_cols=2,
        pixel_size_m=10.0,
        target_origin_x=0.0,
        target_origin_y=10.0,
        soil_clusters=soil_clusters,
    )

    # 13 states per ensemble member, 5 members
    from services.agribrain.layer05_asmae.config import N_STATES
    ensemble = {
        "mz_000_000": [[0.80] + [0.5]*(N_STATES-1) for _ in range(5)],
        "mz_000_001": [[0.20] + [0.5]*(N_STATES-1) for _ in range(5)],
    }

    regularized, report = apply_ensemble_graph_regularization(
        ensemble=ensemble,
        graph=graph,
        state_names=["vigor"],
    )

    assert report["applied"] is True
    # Due to boundary suppression (weight=0.3), values remain well separated
    v0 = np.mean([m[0] for m in regularized["mz_000_000"]])
    v1 = np.mean([m[0] for m in regularized["mz_000_001"]])
    assert v0 > 0.75
    assert v1 < 0.25


def test_bma_biophysical_cluster_expert_weights():
    """Verify BMA adapts physics expert weights based on biophysical cluster."""
    scoring = ArchiveExpertScoring()
    base_rmses = {
        "hydro_drainage_model": 0.08,
        "prosail_canopy_model": 0.08,
        "salinity_osmotic_model": 0.08,
    }

    # Sandy cluster should favor drainage model
    sand_bma = scoring.compute_biophysical_cluster_bma_weights(
        base_rmses, cluster_id=BIO_CLUSTER_RAPID_DRAINAGE_SAND,
    )
    weights_sand = sand_bma["weights"]
    assert weights_sand["hydro_drainage_model"] > weights_sand["prosail_canopy_model"]

    # Saline cluster should favor osmotic stress model
    saline_bma = scoring.compute_biophysical_cluster_bma_weights(
        base_rmses, cluster_id=BIO_CLUSTER_CHRONIC_SALINE,
    )
    weights_saline = saline_bma["weights"]
    assert weights_saline["salinity_osmotic_model"] > weights_saline["prosail_canopy_model"]


def test_biophysical_uncertainty_calibration_report():
    """Verify uncertainty calibration report per biophysical cluster and event."""
    holdout_errors = [
        {"vigor": 0.02, "canopy_water": -0.01},
        {"vigor": 0.03, "canopy_water": 0.02},
        {"vigor": -0.02, "canopy_water": 0.01},
    ]
    sigmas = {
        "mz_000_000": [0.03] * 13,
        "mz_000_001": [0.03] * 13,
    }
    clusters = {
        "mz_000_000": BIO_CLUSTER_RETENTIVE_FERTILE,
        "mz_000_001": BIO_CLUSTER_RAPID_DRAINAGE_SAND,
    }

    report = compute_biophysical_calibration_report(
        holdout_errors=holdout_errors,
        sigmas=sigmas,
        soil_clusters=clusters,
    )

    assert "global_calibration_score" in report
    assert report["is_calibrated"] is True
    assert BIO_CLUSTER_RETENTIVE_FERTILE in report["cluster_calibration_scores"]
    assert BIO_CLUSTER_RAPID_DRAINAGE_SAND in report["cluster_calibration_scores"]


def test_weak_label_learning_export_biophysical_enrichment():
    """Verify weak-label exports include biophysical cluster and continuous response indices."""
    state_result = {
        "raster_maps": {"mz_000_000": [0.70] * 13},
        "uncertainty_maps": {"mz_000_000": [0.05] * 13},
    }
    retro_result = {
        "status": "success_with_holdouts",
        "aggregate": {"mean_retro_score": 0.85},
        "per_microzone": {"mz_000_000": {"retro_score": 0.85}},
    }
    bma_result = {
        "status": "success",
        "per_microzone_disagreement": {"mz_000_000": 0.02},
    }
    consistency_result = {"overall_pass": True}

    profile = MicrozoneBiophysicalProfile(
        microzone_id="mz_000_000",
        water_retention_index=0.72,
        nutrient_response_index=0.80,
        biophysical_cluster_id=BIO_CLUSTER_RETENTIVE_FERTILE,
    )

    labels = export_weak_labels(
        state_result=state_result,
        retro_result=retro_result,
        bma_result=bma_result,
        consistency_result=consistency_result,
        scene_stack_mode="real_raster",
        resolution_m=2,
        plot_id="plot_test",
        run_id="run_001",
        production_usable=True,
        n_scenes_processed=8,
        certification_level="certified",
        biophysical_profiles={"mz_000_000": profile},
    )

    assert len(labels) > 0
    first = labels[0]
    assert first["training_weight"] > 0.0
    assert first["retro_score"] == 0.85
    assert first["biophysical_cluster"] == BIO_CLUSTER_RETENTIVE_FERTILE
    assert first["water_retention_index"] == 0.72
    assert first["nutrient_response_index"] == 0.80


def test_resolution_ladder_promotion_with_archive_retrovalidation():
    """Verify archive depth and retrovalidation residual R2 >= 0.75 promote resolution beyond 10m."""
    from services.agribrain.layer05_asmae.schema import ASMAEInput, ASMAESceneRuntime
    from services.agribrain.layer05_asmae.resolution.candidates import generate_candidates
    from services.agribrain.layer05_asmae.resolution.policy import apply_policies
    from services.agribrain.layer05_asmae.resolution.evaluator import EvaluationResult

    from datetime import date
    inp = ASMAEInput(
        plot_id="test_plot",
        run_id="test_run",
        polygon_geojson={"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]},
        geometry_hash="test_geom",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 10),
        layer0_source_packages={},
        historical_scene_refs=[f"scene_{i}" for i in range(12)],
        archive_metrics={"scene_count": 12, "optical_good_scene_count": 8, "r2": 0.85},
        retrovalidation_residuals={"1": 0.85, "2": 0.88, "5": 0.92, "10": 1.0},
    )
    s1 = ASMAESceneRuntime(
        scene_id="s1",
        sensor="S2",
        acquisition_time=datetime(2026, 9, 1, tzinfo=timezone.utc),
        crs="EPSG:32631",
        transform=[10.0, 0.0, 500000.0, 0.0, -10.0, 4000000.0],
        width=10,
        height=10,
        bands={"ndvi": np.full((10, 10), 0.5)},
        masks={"clear": np.ones((10, 10), dtype=bool)},
    )
    s2 = ASMAESceneRuntime(
        scene_id="s2",
        sensor="S2",
        acquisition_time=datetime(2026, 9, 6, tzinfo=timezone.utc),
        crs="EPSG:32631",
        transform=[10.0, 0.0, 500000.0, 0.0, -10.0, 4000000.0],
        width=10,
        height=10,
        bands={"ndvi": np.full((10, 10), 0.55)},
        masks={"clear": np.ones((10, 10), dtype=bool)},
    )
    scenes = [s1, s2]

    candidate_set = generate_candidates(inp=inp, scenes=scenes, operators=[])
    eligible_res = candidate_set.eligible_resolutions()
    assert 2 in eligible_res
    assert 1 in eligible_res

    eval_results = {
        10: EvaluationResult(resolution_m=10, composite_score=0.80, operator_quality=0.85),
        2: EvaluationResult(resolution_m=2, composite_score=0.82, operator_quality=0.85),
        1: EvaluationResult(resolution_m=1, composite_score=0.84, operator_quality=0.85),
    }
    policy_res = apply_policies(
        evaluation_results=eval_results,
        scenes=scenes,
        retro_scores={1: 0.85, 2: 0.88, 5: 0.92, 10: 1.0},
    )
    assert policy_res.safe_for_1m_claim is True
    assert policy_res.effective_resolution_m < 10

