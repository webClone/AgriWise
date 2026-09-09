"""
Integration and runner tests for Layer 10 (SIRE - Spatial Intelligence & Raster Engine).
"""
from types import SimpleNamespace
import pytest

from services.agribrain.layer10_sire import runner as layer10_runner
from services.agribrain.layer10_sire.schema import (
    Layer10Input, Layer10Output, SurfaceType,
)
from services.agribrain.layer10_sire.surface_contract import (
    PublicationStatus,
    VALID_PUBLICATION_STATUSES,
)
from services.agribrain.common.plot_namespace import PlotNamespace


TEST_NAMESPACE = PlotNamespace("tenant-test", "farm-test", "plot-sire-test")


@pytest.fixture(autouse=True)
def mock_sire_cache(monkeypatch):
    """Disable disk caching for deterministic, clean test execution."""
    monkeypatch.setattr(layer10_runner, "load_layer10_from_cache", lambda _key: None)
    monkeypatch.setattr(layer10_runner, "save_layer10_to_cache", lambda *_args: 0)


def test_layer10_sire_quick_visual_mode():
    """Verify that quick_visual mode runs end-to-end and produces valid degraded/normal publication."""
    l10_input = Layer10Input(
        plot_namespace=TEST_NAMESPACE,
        grid_height=3,
        grid_width=3,
        requested_modes=["quick_visual"],
        user_mode="quick_visual",
    )
    output = layer10_runner.run_layer10_sire(l10_input)

    assert isinstance(output, Layer10Output)
    assert output.publication_status in VALID_PUBLICATION_STATUSES
    assert output.render_manifest is not None
    assert output.quality_report is not None


def test_layer10_sire_standard_mode_with_field_tensor():
    """Verify standard execution with 2D tensor raster maps and geometry."""
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
        run_id="tensor-test-run",
        maps={"ndvi": [[0.4, 0.5], [0.6, 0.7]]},
        map_metadata={"ndvi": {"resolution": 10.0, "source": "sentinel-2"}},
        data=[],
        channels=["ndvi"],
        plot_timeseries=[{"date": "2026-09-01", "ndvi": 0.55}],
        daily_state={},
        zone_stats={},
        zones={},
        provenance={"sensor": "S2A"},
        static={"soil_clay": 25.0},
        grid_spec=grid_spec,
    )

    l10_input = Layer10Input(
        plot_namespace=TEST_NAMESPACE,
        field_tensor=field_tensor,
        field_geometry=field_geometry,
        grid_height=2,
        grid_width=2,
        requested_modes=["standard"],
        user_mode="farmer",
    )
    output = layer10_runner.run_layer10_sire(l10_input)

    assert isinstance(output, Layer10Output)
    assert output.publication_status in VALID_PUBLICATION_STATUSES
    assert output.quality_report.grid_alignment_ok is True
    # Verify surfaces were generated and indexed
    semantic_types = [s.semantic_type for s in output.surface_pack]
    assert len(semantic_types) > 0


def test_layer10_sire_explainability_surfaces():
    """Verify explainability pack contains reasoning records for rendered modes."""
    l10_input = Layer10Input(
        plot_namespace=TEST_NAMESPACE,
        grid_height=2,
        grid_width=2,
        requested_modes=["canopy", "water"],
        user_mode="agronomist",
    )
    output = layer10_runner.run_layer10_sire(l10_input)

    assert isinstance(output, Layer10Output)
    assert output.explainability_pack is not None
