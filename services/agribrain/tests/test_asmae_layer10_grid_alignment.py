from dataclasses import replace
from types import SimpleNamespace

import pytest

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.layer10_sire.adapters.l1_adapter import L1SpatialData, adapt_l1
from services.agribrain.layer10_sire import runner as layer10_runner
from services.agribrain.layer10_sire.l10_frontend_bridge import serialize_output
from services.agribrain.layer10_sire.schema import (
    ASMAE_DIAGNOSTIC_SURFACES,
    ASMAE_STATE_SURFACES,
    Layer10Input,
    SurfaceType,
)
from services.agribrain.layer10_sire.surfaces.asmae import (
    _align_asmae_grid_to_target,
    generate_asmae_aliases,
    generate_asmae_surfaces,
)
from services.agribrain.layer1_fusion.raster_ingest import ingest_asmae_raster_refs


NAMESPACE = PlotNamespace("tenant-grid", "farm-grid", "plot-grid")


def _north_up_spec(height: int, width: int) -> dict:
    return {
        "crs": "EPSG:32631",
        "bounds": [0.0, 0.0, 180.0, 190.0],
        "transform": [
            0.0,
            180.0 / width,
            0.0,
            190.0,
            0.0,
            -(190.0 / height),
        ],
        "width": width,
        "height": height,
        "resolution_m": 10.0,
        "nodata": -9999.0,
    }


def test_asmae_grid_shape_change_uses_proven_geography_without_transpose(monkeypatch):
    monkeypatch.setattr(
        "rollout.rollout_policy.should_render_l10_asmae", lambda _plot_id: True
    )
    source_spec = _north_up_spec(19, 18)
    target_spec = _north_up_spec(18, 19)
    source_grid = [[float(row * 100 + col) for col in range(18)] for row in range(19)]
    l1 = L1SpatialData(
        height=18,
        width=19,
        grid_spec=target_spec,
        raster_maps={"asmae_vigor": source_grid},
        raster_metadata={
            "asmae_vigor": {
                "resolution_m": 10.0,
                "diagnostic_only": True,
                "state_update_allowed": False,
            }
        },
        asmae_feature_pack={"grid_spec": source_spec},
        asmae_evidence_state={
            "real_asmae_evidence": True,
            "source_reality": "real_raster",
        },
        real_asmae_evidence=True,
    )

    surfaces = generate_asmae_surfaces(
        Layer10Input(plot_namespace=NAMESPACE), 18, 19, l1_data=l1
    )
    vigor = next(surface for surface in surfaces if surface.semantic_type == SurfaceType.ASMAE_VIGOR)

    assert len(vigor.values) == 18
    assert all(len(row) == 19 for row in vigor.values)
    assert vigor.values[0][0] < vigor.values[0][-1]
    assert vigor.values[0][0] < vigor.values[-1][0]
    assert vigor.provenance["display_resampled"] is True
    assert vigor.provenance["resampling_method"] == "bilinear"
    assert vigor.provenance["source_grid_shape"] == [19, 18]
    assert vigor.provenance["display_grid_shape"] == [18, 19]
    assert vigor.source_grid_spec["transform_convention"] == "gdal"
    assert vigor.display_grid_spec["transform_convention"] == "gdal"

    aliases = generate_asmae_aliases(18, 19, surfaces, Layer10Input(plot_namespace=NAMESPACE), target_spec)
    canopy = next(alias for alias in aliases if alias.semantic_type == SurfaceType.CANOPY_ASMAE_VIGOR)
    assert len(canopy.values) == 18
    assert all(len(row) == 19 for row in canopy.values)


def test_asmae_shape_change_without_affine_proof_fails_closed():
    with pytest.raises(ValueError, match="ASMAE_GRID_ALIGNMENT_UNPROVEN"):
        _align_asmae_grid_to_target(
            [[1.0, 2.0], [3.0, 4.0]],
            source_grid_spec=None,
            target_grid_spec=_north_up_spec(1, 4),
            target_height=1,
            target_width=4,
            method="bilinear",
        )


def test_asmae_equal_shape_without_affine_proof_fails_closed():
    with pytest.raises(
        ValueError,
        match="ASMAE_GRID_ALIGNMENT_UNPROVEN:source_grid_spec_missing",
    ):
        _align_asmae_grid_to_target(
            [[1.0, 2.0], [3.0, 4.0]],
            source_grid_spec=None,
            target_grid_spec=None,
            target_height=2,
            target_width=2,
            method="bilinear",
        )


def test_production_adapter_preserves_native_grid_then_reprojects_crs(monkeypatch):
    """Exercise ingest refs -> adapt_l1 -> generate, not a hand-built L1 value."""
    from rasterio.warp import transform_bounds

    monkeypatch.setattr(
        "rollout.rollout_policy.should_render_l10_asmae", lambda _plot_id: True
    )
    source_h, source_w = 19, 18
    source_bounds = [491000.0, 4039000.0, 491180.0, 4039190.0]
    source_spec = {
        "crs": "EPSG:32631",
        "bounds": source_bounds,
        "transform": [491000.0, 10.0, 0.0, 4039190.0, 0.0, -10.0],
        "width": source_w,
        "height": source_h,
        "resolution_m": 10.0,
        "nodata": -9999.0,
    }
    target_h, target_w = 18, 19
    target_bounds = list(
        transform_bounds(
            source_spec["crs"], "EPSG:4326", *source_bounds, densify_pts=21
        )
    )
    min_x, min_y, max_x, max_y = target_bounds
    target_spec = {
        "crs": "EPSG:4326",
        "bounds": target_bounds,
        "transform": [
            min_x,
            (max_x - min_x) / target_w,
            0.0,
            max_y,
            0.0,
            -((max_y - min_y) / target_h),
        ],
        "width": target_w,
        "height": target_h,
        "resolution_m": 10.0,
    }
    source_grid = [
        [float(row * 100 + col) for col in range(source_w)]
        for row in range(source_h)
    ]
    output = {
        "status": "success",
        "plot_id": NAMESPACE.plot_id,
        "schema_version": "asmae-test-v1",
        "generated_at": "2026-08-21T00:00:00+00:00",
        "grid_spec": source_spec,
        "resolution_decision": {"selected_effective_resolution_m": 10.0},
        "raster_maps": {"ASMAE_VIGOR": source_grid},
        "uncertainty_maps": {},
        "confidence_maps": {},
        "retrovalidation_maps": {},
        "bma_maps": {},
        "asmae_feature_pack": {"grid_spec": source_spec},
        "diagnostics": {"scene_stack_mode": "real_scene_stack"},
        "provenance": {},
        "diagnostic_only": True,
        "state_update_allowed": False,
    }
    refs = ingest_asmae_raster_refs(output, NAMESPACE.plot_id)
    assert refs
    assert (refs[0].height, refs[0].width) == (source_h, source_w)

    evidence_state = {
        "real_asmae_evidence": True,
        "source_reality": "real_raster",
    }
    context_package = SimpleNamespace(
        spatial_index=SimpleNamespace(raster_refs=refs),
        asmae_output=output,
        asmae_evidence_state=evidence_state,
    )
    tensor = SimpleNamespace(
        run_id="l1-production-adapter",
        grid_spec=target_spec,
        maps={},
        map_metadata={},
        data=[],
        channels=[],
        time_index=[],
        raster_composites={},
        zones={},
        zone_stats={},
        daily_state={},
        plot_timeseries=[],
        provenance={},
        provenance_log=[],
        spatial_reliability={},
        _context_package=context_package,
        asmae_output=output,
        asmae_evidence_state=evidence_state,
    )

    l1 = adapt_l1(tensor, target_h, target_w, skip_idw=False)
    native = l1.raster_maps["ASMAE_VIGOR"]
    assert len(native) == source_h
    assert all(len(row) == source_w for row in native)
    assert native[-1][-1] == source_grid[-1][-1]
    assert len(l1.observed_masks["ASMAE_VIGOR"]) == source_h

    surfaces = generate_asmae_surfaces(
        Layer10Input(plot_namespace=NAMESPACE, field_tensor=tensor),
        target_h,
        target_w,
        l1_data=l1,
    )
    vigor = next(
        surface
        for surface in surfaces
        if surface.semantic_type == SurfaceType.ASMAE_VIGOR
    )
    assert len(vigor.values) == target_h
    assert all(len(row) == target_w for row in vigor.values)
    assert vigor.provenance["reprojection_applied"] is True
    assert vigor.provenance["source_crs"] == "EPSG:32631"
    assert vigor.provenance["display_crs"] == "EPSG:4326"
    assert vigor.provenance["grid_inheritance_allowed"] is False
    assert vigor.source_grid_spec["width"] == source_w
    assert vigor.display_grid_spec["width"] == target_w
    assert l1.asmae_alignment_failures == []


def test_full_layer10_publication_preserves_native_source_grid_for_core_asmae_surfaces(
    monkeypatch,
):
    """Protect native lineage through runner normalization and wire serialization."""
    from rasterio.warp import transform_bounds

    monkeypatch.setattr(
        "rollout.rollout_policy.should_render_l10_asmae", lambda _plot_id: True
    )
    monkeypatch.setattr(layer10_runner, "load_layer10_from_cache", lambda _key: None)
    monkeypatch.setattr(layer10_runner, "save_layer10_to_cache", lambda *_args: 0)

    source_h, source_w = 4, 3
    source_bounds = [491000.0, 4039000.0, 491030.0, 4039040.0]
    source_spec = {
        "crs": "EPSG:32631",
        "bounds": source_bounds,
        "transform": [491000.0, 10.0, 0.0, 4039040.0, 0.0, -10.0],
        "width": source_w,
        "height": source_h,
        "resolution_m": 10.0,
        "nodata": -9999.0,
    }
    target_h, target_w = 3, 4
    target_bounds = list(
        transform_bounds(
            source_spec["crs"], "EPSG:4326", *source_bounds, densify_pts=21
        )
    )
    min_x, min_y, max_x, max_y = target_bounds
    target_spec = {
        "crs": "EPSG:4326",
        "bounds": target_bounds,
        "transform": [
            min_x,
            (max_x - min_x) / target_w,
            0.0,
            max_y,
            0.0,
            -((max_y - min_y) / target_h),
        ],
        "width": target_w,
        "height": target_h,
        "resolution_m": 10.0,
    }
    source_grid = [
        [0.2 + (row * source_w + col) / 100.0 for col in range(source_w)]
        for row in range(source_h)
    ]
    core_types = sorted(
        (
            surface_type
            for surface_type in ASMAE_STATE_SURFACES | ASMAE_DIAGNOSTIC_SURFACES
            if surface_type.value.startswith("ASMAE_")
        ),
        key=lambda surface_type: surface_type.value,
    )
    asmae_output = {
        "status": "partial",
        "plot_id": NAMESPACE.plot_id,
        "schema_version": "asmae-publication-grid-regression-v1",
        "generated_at": "2026-08-26T00:00:00+00:00",
        "grid_spec": source_spec,
        "resolution_decision": {"selected_effective_resolution_m": 10.0},
        "raster_maps": {
            surface_type.value: source_grid for surface_type in core_types
        },
        "uncertainty_maps": {},
        "confidence_maps": {},
        "retrovalidation_maps": {},
        "bma_maps": {},
        "asmae_feature_pack": {"grid_spec": source_spec},
        "diagnostics": {"scene_stack_mode": "real_scene_stack"},
        "provenance": {},
        "diagnostic_only": True,
        "state_update_allowed": False,
    }
    refs = ingest_asmae_raster_refs(asmae_output, NAMESPACE.plot_id)
    context_package = SimpleNamespace(
        spatial_index=SimpleNamespace(raster_refs=refs),
        asmae_output=asmae_output,
        asmae_evidence_state={
            "real_asmae_evidence": True,
            "source_reality": "real_raster",
        },
    )
    field_tensor = SimpleNamespace(
        run_id="full-layer10-grid-regression",
        grid_spec=target_spec,
        maps={},
        map_metadata={},
        data=[],
        channels=[],
        time_index=[],
        raster_composites={},
        zones={},
        zone_stats={},
        daily_state={},
        plot_timeseries=[],
        provenance={},
        provenance_log=[],
        spatial_reliability={},
        static={},
        _context_package=context_package,
        asmae_output=asmae_output,
        asmae_evidence_state=context_package.asmae_evidence_state,
    )
    field_geometry = {
        "type": "Polygon",
        "coordinates": [[
            [min_x, min_y],
            [max_x, min_y],
            [max_x, max_y],
            [min_x, max_y],
            [min_x, min_y],
        ]],
    }

    result = layer10_runner.run_layer10_sire(
        Layer10Input(
            plot_namespace=NAMESPACE,
            field_tensor=field_tensor,
            field_geometry=field_geometry,
            grid_height=target_h,
            grid_width=target_w,
            requested_modes=["standard", "scientific_refresh"],
        )
    )
    serialized = serialize_output(result)
    serialized_core = [
        surface
        for surface in serialized["surfaces"]
        if surface["type"].startswith("ASMAE_")
    ]

    serialized_core_types = {surface["type"] for surface in serialized_core}
    assert {surface_type.value for surface_type in core_types} <= serialized_core_types
    assert "ASMAE_CHLOROPHYLL" in serialized_core_types
    assert serialized_core
    for surface in serialized_core:
        assert surface["source_grid_spec"]["crs"] == "EPSG:32631"
        assert surface["source_grid_spec"]["width"] == source_w
        assert surface["source_grid_spec"]["height"] == source_h
        assert surface["display_grid_spec"]["crs"] == "EPSG:4326"
        assert surface["display_grid_spec"]["width"] == target_w
        assert surface["display_grid_spec"]["height"] == target_h


def test_surface_alignment_failure_is_typed_and_observable(monkeypatch):
    monkeypatch.setattr(
        "rollout.rollout_policy.should_render_l10_asmae", lambda _plot_id: True
    )
    target_spec = _north_up_spec(2, 2)
    l1 = L1SpatialData(
        height=2,
        width=2,
        grid_spec=target_spec,
        raster_maps={"asmae_vigor": [[0.1, 0.2], [0.3, 0.4]]},
        raster_metadata={"asmae_vigor": {"resolution_m": 10.0}},
        asmae_feature_pack={},
    )

    surfaces = generate_asmae_surfaces(
        Layer10Input(plot_namespace=NAMESPACE), 2, 2, l1_data=l1
    )

    assert not any(
        surface.semantic_type == SurfaceType.ASMAE_VIGOR for surface in surfaces
    )
    assert l1.asmae_alignment_failures == [
        {
            "component": "ASMAE_SURFACE_ALIGNMENT",
            "code": "ASMAE_GRID_ALIGNMENT_FAILED",
            "surface_type": "ASMAE_VIGOR",
            "variable": "asmae_vigor",
            "reason": "ASMAE_GRID_ALIGNMENT_UNPROVEN:source_grid_spec_missing",
        }
    ]
    assert (
        l1.asmae_feature_pack["surface_alignment_failures"]
        == l1.asmae_alignment_failures
    )


def test_malformed_alias_candidate_cannot_discard_valid_candidate(monkeypatch):
    monkeypatch.setattr(
        "rollout.rollout_policy.should_render_l10_asmae", lambda _plot_id: True
    )
    spec = _north_up_spec(2, 2)
    l1 = L1SpatialData(
        height=2,
        width=2,
        grid_spec=spec,
        raster_maps={"asmae_vigor": [[0.1, 0.2], [0.3, 0.4]]},
        raster_metadata={"asmae_vigor": {"resolution_m": 10.0}},
        asmae_feature_pack={"grid_spec": spec},
        asmae_evidence_state={
            "real_asmae_evidence": True,
            "source_reality": "real_raster",
        },
        real_asmae_evidence=True,
    )
    inp = Layer10Input(plot_namespace=NAMESPACE)
    surfaces = generate_asmae_surfaces(inp, 2, 2, l1_data=l1)
    valid = next(surface for surface in surfaces if surface.semantic_type == SurfaceType.ASMAE_VIGOR)
    malformed = replace(valid, surface_id="malformed", values=[[0.9], [0.8]])

    aliases = generate_asmae_aliases(2, 2, [malformed, valid], inp, spec)

    canopy = next(alias for alias in aliases if alias.semantic_type == SurfaceType.CANOPY_ASMAE_VIGOR)
    assert canopy.values == valid.values
