"""Unit tests for Layer 0 PlotGrid spatial georeferencing and UTM projection."""

import pytest
from services.agribrain.layer0.plot_grid import PlotGrid


def test_plot_grid_from_polygon_wgs84():
    """Verify PlotGrid projects coordinates to UTM and computes positive width/height."""
    # Simple rectangular polygon in northern hemisphere (approx 100m x 100m)
    coords = [
        [2.350, 48.850],
        [2.352, 48.850],
        [2.352, 48.852],
        [2.350, 48.852],
        [2.350, 48.850],
    ]
    grid = PlotGrid.from_polygon_wgs84(coords, pixel_size=10.0, buffer_m=20.0)

    assert grid.width > 0
    assert grid.height > 0
    assert grid.pixel_size == 10.0
    assert grid.crs.startswith("EPSG:326")  # Northern hemisphere UTM zone 31
    assert len(grid.polygon_coords_utm) == len(coords)
    assert len(grid.alpha) == grid.height
    assert len(grid.alpha[0]) == grid.width


def test_plot_grid_alpha_mask_values():
    """Verify fractional alpha mask values are within [0.0, 1.0]."""
    coords = [
        [3.00, 36.00],
        [3.01, 36.00],
        [3.01, 36.01],
        [3.00, 36.01],
        [3.00, 36.00],
    ]
    grid = PlotGrid.from_polygon_wgs84(coords, pixel_size=10.0)

    for row in grid.alpha:
        for val in row:
            assert 0.0 <= val <= 1.0


def test_plot_grid_insufficient_coordinates():
    """Verify PlotGrid rejects invalid polygons with fewer than 3 points."""
    with pytest.raises(ValueError):
        PlotGrid.from_polygon_wgs84([[1.0, 1.0], [2.0, 2.0]])
