"""
Unit tests for Layer 10 Surface Contracts, Invariants, and 1-Meter Policy.
"""
from types import SimpleNamespace
import pytest

from services.agribrain.layer10_sire.surface_contract import (
    serialize_surface_artifact,
    PublicationStatus,
    VALID_PUBLICATION_STATUSES,
)
from services.agribrain.layer10_sire.schema import (
    Layer10Output, SurfaceArtifact, SurfaceType, QualityReport, SIREDegradation,
    GroundingClass,
)
from services.agribrain.layer10_sire.invariants import enforce_layer10_invariants
from services.agribrain.layer10_sire.one_meter_policy import (
    build_one_meter_policy_summary,
    enforce_one_meter_policy,
)


def test_surface_artifact_serialization():
    """Verify surface serialization contract enforces mandatory immutable identity."""
    # 1. Valid surface artifact
    valid_surface = SimpleNamespace(
        surface_id="surf_ndvi_001",
        semantic_type="NDVI_CLEAN",
        values=[[0.5, 0.6], [0.7, 0.8]],
        provenance={"resolution_m": 10.0, "source": "sentinel-2"},
        native_resolution_m=10.0,
    )
    serialized = serialize_surface_artifact(valid_surface)
    assert serialized["surface_id"] == "surf_ndvi_001"
    assert serialized["semantic_type"] == "NDVI_CLEAN"
    assert serialized["provenance"]["resolution_m"] == 10.0

    # 2. Missing surface_id -> ValueError
    invalid_no_id = SimpleNamespace(
        surface_id="",
        semantic_type="NDVI_CLEAN",
        provenance={},
    )
    with pytest.raises(ValueError, match="missing mandatory surface_id"):
        serialize_surface_artifact(invalid_no_id)

    # 3. Missing semantic_type -> ValueError
    invalid_no_type = SimpleNamespace(
        surface_id="surf_002",
        semantic_type="",
        provenance={},
    )
    with pytest.raises(ValueError, match="missing semantic_type"):
        serialize_surface_artifact(invalid_no_type)

    # 4. Provenance not mapping -> ValueError
    invalid_prov = SimpleNamespace(
        surface_id="surf_003",
        semantic_type="NDVI_CLEAN",
        provenance="not-a-dict",
    )
    with pytest.raises(ValueError, match="provenance is not a mapping"):
        serialize_surface_artifact(invalid_prov)


def test_layer10_invariants_enforcement():
    """Verify runtime enforcement of INV-1 through INV-7 invariants."""
    clean_surface = SurfaceArtifact(
        surface_id="s_clean",
        semantic_type=SurfaceType.NDVI_CLEAN,
        grid_ref="grid_2x2",
        values=[[0.4, 0.5], [0.6, 0.7]],
        units="index",
        confidence=[[0.9, 0.9], [0.9, 0.9]],
        native_resolution_m=10.0,
        grounding_class=GroundingClass.RASTER_GROUNDED,
        provenance={"source": "sentinel_2", "observed_ratio": 1.0},
    )

    output = Layer10Output(
        surface_pack=[clean_surface],
        zone_pack=[],
    )

    # 1. Clean output passes all invariants
    violations = enforce_layer10_invariants(output, grid_h=2, grid_w=2)
    assert len(violations) == 0
    assert output.quality_report.grid_alignment_ok is True

    # 2. INV-1: Grid height mismatch (3 rows instead of 2)
    corrupted_grid = SurfaceArtifact(
        surface_id="s_bad_grid",
        semantic_type=SurfaceType.NDVI_CLEAN,
        grid_ref="grid_2x2",
        values=[[0.4, 0.5], [0.6, 0.7], [0.8, 0.9]],
        units="index",
        confidence=[[0.9, 0.9], [0.9, 0.9], [0.9, 0.9]],
        native_resolution_m=10.0,
        grounding_class=GroundingClass.RASTER_GROUNDED,
        provenance={"source": "sentinel_2"},
    )
    output_bad_grid = Layer10Output(
        surface_pack=[corrupted_grid],
        zone_pack=[],
    )
    v_inv1 = enforce_layer10_invariants(output_bad_grid, grid_h=2, grid_w=2)
    assert any("INV-1" in v for v in v_inv1)
    assert output_bad_grid.quality_report.grid_alignment_ok is False

    # 3. INV-2: Range sanity violation (NDVI > 1.0)
    corrupted_range = SurfaceArtifact(
        surface_id="s_bad_range",
        semantic_type=SurfaceType.NDVI_CLEAN,
        grid_ref="grid_2x2",
        values=[[0.4, 1.5], [0.6, 0.7]],  # 1.5 > 1.0
        units="index",
        confidence=[[0.9, 0.9], [0.9, 0.9]],
        native_resolution_m=10.0,
        grounding_class=GroundingClass.RASTER_GROUNDED,
        provenance={"source": "sentinel_2"},
    )
    output_bad_range = Layer10Output(
        surface_pack=[corrupted_range],
        zone_pack=[],
    )
    v_inv2 = enforce_layer10_invariants(output_bad_range, grid_h=2, grid_w=2)
    assert any("INV-2" in v for v in v_inv2)

    # 4. INV-3: Source dominance weights sum violation (!= 1.0)
    corrupted_weights = SurfaceArtifact(
        surface_id="s_bad_weights",
        semantic_type=SurfaceType.NDVI_CLEAN,
        grid_ref="grid_2x2",
        values=[[0.4, 0.5], [0.6, 0.7]],
        units="index",
        confidence=[[0.9, 0.9], [0.9, 0.9]],
        source_weights=[[{"s2": 0.40}, {"s2": 1.0}], [{"s2": 1.0}, {"s2": 1.0}]],
        native_resolution_m=10.0,
        grounding_class=GroundingClass.RASTER_GROUNDED,
        provenance={"source": "sentinel_2"},
    )
    output_bad_weights = Layer10Output(
        surface_pack=[corrupted_weights],
        zone_pack=[],
    )
    v_inv3 = enforce_layer10_invariants(output_bad_weights, grid_h=2, grid_w=2)
    assert any("INV-3" in v for v in v_inv3)

    # 5. INV-7: Histogram consistency violation (bin_counts sum != valid_pixels)
    from services.agribrain.layer10_sire.schema import HistogramBundle, HistogramArtifact
    h_bad = HistogramArtifact(
        surface_type=SurfaceType.NDVI_CLEAN,
        region_id="field",
        bin_edges=[0.0, 0.5, 1.0],
        bin_counts=[1, 1],  # sum = 2
        total_pixels=4,
        valid_pixels=4,     # 2 != 4
    )
    output_bad_hist = Layer10Output(
        surface_pack=[clean_surface],
        zone_pack=[],
        histogram_bundle=HistogramBundle(field_histograms=[h_bad]),
    )
    v_inv7 = enforce_layer10_invariants(output_bad_hist, grid_h=2, grid_w=2)
    assert any("INV-7" in v for v in v_inv7)


def test_one_meter_policy():
    """Verify 1-meter high-resolution surfaces are visual-only and fail closed against state updates."""
    # 1. Legitimate visual-only 1m surface
    safe_1m = SimpleNamespace(
        native_resolution_m=0.5,
        provenance={
            "resolution_m": 0.5,
            "display_certified": True,
            "visual_only": True,
            "state_update_allowed": False,
            "training_label_allowed": False,
            "prescription_driver_allowed": False,
        },
    )
    summary = build_one_meter_policy_summary([safe_1m])
    assert summary["total_1m_surfaces"] == 1
    assert summary["visual_only"] == 1
    assert summary["state_update_allowed"] == 0
    enforce_one_meter_policy(summary)  # Does not raise

    # 2. Illicit state update on 1m surface raises RuntimeError
    unsafe_1m = SimpleNamespace(
        native_resolution_m=0.5,
        provenance={
            "resolution_m": 0.5,
            "display_certified": True,
            "visual_only": False,
            "state_update_allowed": True,  # Policy violation!
        },
    )
    unsafe_summary = build_one_meter_policy_summary([unsafe_1m])
    assert unsafe_summary["state_update_allowed"] == 1
    with pytest.raises(RuntimeError, match="one_meter_state_update_policy_violation"):
        enforce_one_meter_policy(unsafe_summary)
