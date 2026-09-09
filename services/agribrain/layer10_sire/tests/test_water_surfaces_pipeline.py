"""Tests for Layer 10 Water Surfaces Pipeline (WP01)."""

from types import SimpleNamespace
import pytest

from services.agribrain.layer10_sire.schema import Layer10Input, SurfaceType
from services.agribrain.layer10_sire.adapters.l1_adapter import L1SpatialData
from services.agribrain.layer10_sire.adapters.l3_adapter import L3DiagnosticData
from services.agribrain.layer10_sire.surfaces.water import (
    generate_water_surfaces,
    _compute_water_stress_prob,
    _compute_drainage_deficit,
)


def _make_dummy_input():
    return Layer10Input(
        tenant_id="default_tenant",
        farm_id="farm_01",
        plot_id="test_plot_wp01",
        field_tensor=None,
        veg_int=None,
        decision=SimpleNamespace(
            primary_hypothesis="WATER_DEFICIT",
            water_stress_probability=0.65,
            confidence=0.82,
            affected_area_pct=25.0,
            stress_hotspots=["Z1"],
            deficit_mm=35.0,
            diagnoses=[],
        ),
        nutrients=None,
        bio=None,
    )


def _make_dummy_l1(H=4, W=4):
    return L1SpatialData(
        height=H,
        width=W,
        resolution_m=10.0,
        raster_maps={
            "soil_moisture": [[0.38 if (r + c) % 2 == 0 else 0.22 for c in range(W)] for r in range(H)],
            "ndmi": [[0.35 if r == 0 else 0.15 for c in range(W)] for r in range(H)],
        },
        zone_masks={"Z1": [(0, 0), (0, 1)]},
    )


def _make_dummy_l3():
    return L3DiagnosticData(
        diagnoses=[{
            "problem_id": "WATER_STRESS",
            "probability": 0.65,
            "confidence": 0.85,
            "affected_area_pct": 25.0,
            "hotspot_zones": ["Z1"],
            "deficit_mm": 35.0,
        }],
        target_zones=["Z1"],
    )


def test_generate_water_surfaces_runner_signature():
    """Verify generate_water_surfaces works with runner's calling signature (H, W positional, l1/l3 kw)."""
    inp = _make_dummy_input()
    l1 = _make_dummy_l1(4, 4)
    l3 = _make_dummy_l3()

    # Call exactly as in runner.py line 2256
    surfaces = generate_water_surfaces(inp, 4, 4, l1_data=l1, l3_data=l3)

    assert isinstance(surfaces, list)
    assert len(surfaces) >= 1
    types = {s.semantic_type for s in surfaces}
    assert SurfaceType.WATER_STRESS_PROB in types


def test_generate_water_surfaces_legacy_signature():
    """Verify generate_water_surfaces also works with legacy signature (l1, l3 positional, H, W)."""
    inp = _make_dummy_input()
    l1 = _make_dummy_l1(4, 4)
    l3 = _make_dummy_l3()

    # Call with legacy positional ordering
    surfaces = generate_water_surfaces(inp, l1, l3, 4, 4)

    assert isinstance(surfaces, list)
    assert len(surfaces) >= 1
    types = {s.semantic_type for s in surfaces}
    assert SurfaceType.WATER_STRESS_PROB in types


def test_compute_drainage_deficit_helper():
    """Verify _compute_drainage_deficit correctly calculates excess water above field capacity."""
    l1 = _make_dummy_l1(4, 4)
    grid = _compute_drainage_deficit(l1, 4, 4)

    assert grid is not None
    assert len(grid) == 4
    assert len(grid[0]) == 4
    # Cells with moisture 0.38 should show (0.38 - 0.35) * 300 = 9.0 mm
    assert grid[0][0] == 9.0
    # Cells with moisture 0.22 should show 0.0 mm
    assert grid[0][1] == 0.0
