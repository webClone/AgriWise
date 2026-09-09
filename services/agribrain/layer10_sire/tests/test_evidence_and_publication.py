"""
Layer 10 Evidence and Publication Test Suite.
Verifies ASMAE spatial publication, composite scouting grounding,
fallback guidance, degradation codes, and publication reconciliation.
"""
from types import SimpleNamespace

from services.agribrain.layer10_sire import runner as layer10_runner
from services.agribrain.layer10_sire.runner import (
    apply_composite_scouting_grounding,
    reconcile_durable_asmae_job_before_publication,
    separate_asmae_evidence_and_publication,
)
from services.agribrain.layer9_interface.fallback_actions import (
    build_fallback_guidance_map,
    get_fallback_guidance,
)
from services.agribrain.layer10_sire.adapters.l1_adapter import L1SpatialData
from services.agribrain.layer10_sire.schema import Layer10Input, SurfaceType
from services.agribrain.layer10_sire.surfaces.asmae import generate_asmae_surfaces
from services.agribrain.common.plot_namespace import PlotNamespace


TEST_NAMESPACE = PlotNamespace("tenant-a", "farm-a", "plot-a")


def test_variable_composite_scouting_is_model_assisted_not_uniform():
    surface = SimpleNamespace(
        provenance={"support_class": "composite_scouting"},
        observed_ratio=1.0,
        grounding_class="UNIFORM",
    )
    assert apply_composite_scouting_grounding(surface, unique_count=270) is True
    assert surface.grounding_class == "MODEL_ASSISTED_RASTER"
    assert surface.observed_ratio == 0.0
    assert surface.provenance["direct_observation"] is False
    assert surface.provenance["management_zone_eligible"] is False
    assert surface.provenance["zone_statistics_eligible"] is False
    assert surface.provenance["scope"] == "model_assisted_spatial_scouting"


def test_asmae_state_guidance_names_committed_surface_and_stays_scouting_only():
    guidance = build_fallback_guidance_map({}, has_plot_data=True)
    water = guidance["WATER_ASMAE_CANOPY_WATER"]
    nutrient = guidance["NUTRIENT_ASMAE_CHLOROPHYLL_PROXY"]
    assert water["action_mode"] == "scouting_only"
    assert water["guidance_surface_type"] == "WATER_ASMAE_CANOPY_WATER"
    assert "valid model-assisted scouting surface" in water["why"]
    assert "invalid" not in water["why"].lower()
    assert nutrient["action_mode"] == "scouting_only"
    assert "do not infer fertilizer adequacy" in nutrient["recommended_next_step"]


def test_fallback_language_never_claims_unqualified_trust_or_fertilizer_adequacy():
    uncertainty = get_fallback_guidance("UNCERTAINTY_SIGMA", "none", True)
    nutrient = get_fallback_guidance("NUTRIENT_STRESS_PROB", "none", True)
    assert "trusted at face value" not in uncertainty["recommended_next_step"].lower()
    assert "maintain current fertilization" not in nutrient["recommended_next_step"].lower()


def test_composite_publication_cannot_overwrite_real_core_asmae_evidence():
    original = {
        "state": "diagnostic_spatial_posterior",
        "real_asmae_evidence": True,
        "visual_fusion_allowed": True,
        "source_reality": "real_raster",
        "authority": "diagnostic_spatial",
    }

    core, publication, demotion = separate_asmae_evidence_and_publication(
        original, has_composite_surface=True
    )

    assert original["state"] == "diagnostic_spatial_posterior"
    assert core == original
    assert publication["state"] == "composite_assimilated_asmae"
    assert publication["source_reality"] == "raster_composite_proxy"
    assert publication["core_authority_unchanged"] is True
    assert demotion["applied"] is False
    assert demotion["core_state"] == "diagnostic_spatial_posterior"


def test_rollout_failure_is_core_authoritative_without_plot_state():
    core, publication, _ = separate_asmae_evidence_and_publication(
        {"state": "diagnostic_spatial_posterior", "real_asmae_evidence": True},
        has_composite_surface=True,
        rollout_block_reason="worker_failed",
        has_plot_state_artifact=False,
    )

    assert core["state"] == "asmae_unavailable"
    assert core["authority"] == "none"
    assert core["reason"] == "worker_failed"
    assert publication["authority"] == "experimental_asmae_advisory"


def test_plot_state_survives_spatial_rollout_failure_as_non_surface_evidence():
    input_state = {
        "state": "context_prior_conditioned",
        "real_asmae_evidence": False,
        "authority": "diagnostic_plot_state",
    }
    core, _, _ = separate_asmae_evidence_and_publication(
        input_state,
        has_composite_surface=False,
        rollout_block_reason="spatial_worker_failed",
        has_plot_state_artifact=True,
    )

    assert core == input_state


def test_terminal_layer10_path_does_not_shadow_default_proof_builder(monkeypatch):
    monkeypatch.setattr(layer10_runner, "load_layer10_from_cache", lambda _key: None)
    monkeypatch.setattr(layer10_runner, "save_layer10_to_cache", lambda *_args: 0)

    output = layer10_runner.run_layer10_sire(
        Layer10Input(
            plot_namespace=PlotNamespace(
                "tenant-a", "farm-a", "terminal-publication-regression"
            ),
            grid_height=2,
            grid_width=2,
            requested_modes=["quick_visual"],
            user_mode="quick_visual",
        )
    )

    assert output.asmae_proof["enkf_proof"]["update_mode"] == "unavailable"
    assert output.publication_status == "VALID_DEGRADED"


def test_ndvi_without_pixel_support_publishes_fail_closed_dependency_masks(monkeypatch):
    """A finite plot-level NDVI must never become valid spatial support."""
    monkeypatch.setenv("ASMAE_ENABLED", "false")
    monkeypatch.setenv("L10_ASMAE_SURFACES_ENABLED", "false")
    monkeypatch.setattr(layer10_runner, "load_layer10_from_cache", lambda _key: None)
    monkeypatch.setattr(layer10_runner, "save_layer10_to_cache", lambda *_args: 0)

    grid_spec = {
        "crs": "EPSG:4326",
        "transform": [1.0, 0.01, 0.0, 2.0, 0.0, -0.01],
        "width": 2,
        "height": 2,
        "bounds": [1.0, 1.98, 1.02, 2.0],
        "resolution": 10.0,
    }
    field_geometry = {
        "type": "Polygon",
        "coordinates": [[
            [1.0, 1.98], [1.02, 1.98], [1.02, 2.0],
            [1.0, 2.0], [1.0, 1.98],
        ]],
    }
    field_tensor = SimpleNamespace(
        run_id="mask-contract-probe",
        maps={},
        map_metadata={},
        data=[],
        channels=[],
        plot_timeseries=[{"date": "2026-08-10", "ndvi": 0.42}],
        daily_state={},
        zone_stats={},
        zones={},
        provenance={},
        static={},
        grid_spec=grid_spec,
    )

    output = layer10_runner.run_layer10_sire(Layer10Input(
        plot_namespace=PlotNamespace("tenant-a", "farm-a", "mask-contract-probe"),
        field_tensor=field_tensor,
        field_geometry=field_geometry,
        grid_height=2,
        grid_width=2,
        requested_modes=["standard", "scientific_refresh"],
    ))
    assert "DIAGNOSTIC_AUTHORITY_ONLY" in output.quality_report.degradation_codes
    assert "PRODUCTION_USE_NOT_AUTHORIZED" in output.quality_report.degradation_codes
    by_type = {
        getattr(surface.semantic_type, "value", str(surface.semantic_type)): surface
        for surface in output.surface_pack
    }

    for surface_type in (
        "OBSERVED_DATA_MASK_NDVI",
        "GAP_FILL_MASK_NDVI",
        "VALID_DATA_MASK_NDVI",
    ):
        surface = by_type[surface_type]
        assert surface.values == [[0.0, 0.0], [0.0, 0.0]]
        assert surface.provenance["source_support_available"] is False
        assert surface.provenance["authority_block_reason"] == (
            "provider_observation_support_unavailable"
        )


def test_asmae_alignment_rejection_is_published_as_typed_degradation(monkeypatch):
    monkeypatch.setattr(layer10_runner, "load_layer10_from_cache", lambda _key: None)
    monkeypatch.setattr(layer10_runner, "save_layer10_to_cache", lambda *_args: 0)

    def reject_one_surface(_inp, _height, _width, *, l1_data):
        l1_data.asmae_alignment_failures = [{
            "component": "ASMAE_SURFACE_ALIGNMENT",
            "code": "ASMAE_GRID_ALIGNMENT_FAILED",
            "surface_type": "ASMAE_VIGOR",
            "variable": "asmae_vigor",
            "reason": "ASMAE_GRID_ALIGNMENT_UNPROVEN:source_grid_spec_missing",
        }]
        return []

    monkeypatch.setattr(layer10_runner, "generate_asmae_surfaces", reject_one_surface)

    grid_spec = {
        "crs": "EPSG:4326",
        "transform": [1.0, 0.01, 0.0, 2.0, 0.0, -0.01],
        "width": 2,
        "height": 2,
        "bounds": [1.0, 1.98, 1.02, 2.0],
        "resolution": 10.0,
    }
    field_geometry = {
        "type": "Polygon",
        "coordinates": [[
            [1.0, 1.98], [1.02, 1.98], [1.02, 2.0],
            [1.0, 2.0], [1.0, 1.98],
        ]],
    }
    field_tensor = SimpleNamespace(
        run_id="alignment-quality-probe",
        maps={"ndvi": [[0.3, 0.4], [0.5, 0.6]]},
        map_metadata={},
        data=[],
        channels=[],
        plot_timeseries=[],
        daily_state={},
        zone_stats={},
        zones={},
        provenance={},
        static={},
        grid_spec=grid_spec,
    )

    output = layer10_runner.run_layer10_sire(Layer10Input(
        plot_namespace=PlotNamespace(
            "tenant-a", "farm-a", "alignment-quality-probe"
        ),
        field_tensor=field_tensor,
        field_geometry=field_geometry,
        grid_height=2,
        grid_width=2,
        requested_modes=["standard", "scientific_refresh"],
    ))

    assert output.quality_report.degradation_mode.value == "DEGRADED"
    assert "ASMAE_GRID_ALIGNMENT_FAILED" in output.quality_report.degradation_codes
    failure = next(
        item for item in output.quality_report.component_failures
        if item.code == "ASMAE_GRID_ALIGNMENT_FAILED"
    )
    assert failure.stage == "alignment"
    assert failure.affected_surface_types == ["ASMAE_VIGOR"]
    assert "source_grid_spec_missing" in failure.message
    assert output.publication_status == "VALID_DEGRADED"


def test_publication_reconciliation_uses_durable_terminal_job(monkeypatch):
    from services.agribrain.layer05_asmae import background_jobs

    monkeypatch.setattr(
        background_jobs,
        "get_job_status",
        lambda job_id: {
            "job_id": job_id,
            "plot_namespace": {
                "tenant_id": TEST_NAMESPACE.tenant_id,
                "farm_id": TEST_NAMESPACE.farm_id,
                "plot_id": TEST_NAMESPACE.plot_id,
            },
            "status": "completed",
            "stage": "complete",
            "progress_pct": 100,
        },
    )
    output = SimpleNamespace(
        source_policy_display_state={
            "asmaePlotState": {
                "activeSpatialJobId": "job-completed",
                "activeSpatialJobStatus": "running",
            }
        },
        asmae_evidence_state={"active_spatial_job_status": "running"},
        core_asmae_evidence_state={"active_spatial_job_status": "running"},
    )

    reconcile_durable_asmae_job_before_publication(output, TEST_NAMESPACE)

    state = output.source_policy_display_state["asmaePlotState"]
    assert state["activeSpatialJobStatus"] == "completed"
    assert state["activeSpatialJobProgressPct"] == 100
    assert output.asmae_evidence_state["active_spatial_job_status"] == "completed"
    assert output.core_asmae_evidence_state["active_spatial_job_status"] == "completed"


def test_asmae_surface_stage_claims_and_support_scores_are_evidence_bound(monkeypatch):
    monkeypatch.setattr(
        "rollout.rollout_policy.should_render_l10_asmae", lambda _plot_id: True
    )
    grid_spec = {
        "crs": "EPSG:32631",
        "bounds": [0.0, 0.0, 20.0, 20.0],
        "transform": [0.0, 10.0, 0.0, 20.0, 0.0, -10.0],
        "width": 2,
        "height": 2,
        "resolution_m": 10.0,
    }
    l1 = L1SpatialData(
        height=2,
        width=2,
        grid_spec=grid_spec,
        raster_maps={
            "asmae_vigor": [[0.4, 0.5], [0.6, 0.7]],
        },
        raster_metadata={
            "asmae_vigor": {
                "resolution_m": 10.0,
                "confidence": 0.82,
                "uncertainty": 0.18,
                "posterior_confidence_available": True,
                "posterior_uncertainty_available": True,
                "used_bma": False,
                "used_archive": False,
                "used_retrovalidation": False,
                "bma_status": "insufficient_experts",
                "diagnostic_only": True,
                "state_update_allowed": False,
            },
        },
        asmae_evidence_state={
            "real_asmae_evidence": True,
            "source_reality": "real_raster",
            "used_bma": False,
            "used_archive": False,
            "used_retrovalidation": False,
        },
        asmae_feature_pack={"grid_spec": grid_spec},
        real_asmae_evidence=True,
    )
    surfaces = generate_asmae_surfaces(
        Layer10Input(plot_namespace=TEST_NAMESPACE), 2, 2, l1_data=l1
    )
    vigor = next(s for s in surfaces if s.semantic_type == SurfaceType.ASMAE_VIGOR)
    assert vigor.provenance["used_bma"] is False
    assert vigor.provenance["used_archive"] is False
    assert vigor.provenance["used_retrovalidation"] is False
    assert vigor.provenance["confidence"] == 0.82
    assert vigor.provenance["uncertainty"] == 0.18
    assert vigor.provenance["posterior_confidence_available"] is True
