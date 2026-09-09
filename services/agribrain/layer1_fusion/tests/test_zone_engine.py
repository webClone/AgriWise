"""Unit tests for Layer 1 Management Zone Engine."""

import numpy as np
import pytest

from services.agribrain.layer1_fusion.zone_engine import (
    generate_management_zones,
    _fallback_single_zone,
)


def test_generate_management_zones_quantiles():
    """Verify zone clustering divides multi-pixel field into distinct vigor zones."""
    grid_spec = {
        "width": 10,
        "height": 10,
        "resolution_m": 10.0,
        "bounds": [0.0, 0.0, 100.0, 100.0],
        "crs": "EPSG:32631",
    }
    # Create 3-day time series with distinct vigor gradient
    # Top left low vigor (~0.2), bottom right high vigor (~0.8)
    time_series = []
    for _ in range(3):
        frame = []
        for r in range(10):
            row = []
            for c in range(10):
                val = 0.2 + 0.6 * ((r + c) / 18.0)
                row.append(val)
            frame.append(row)
        time_series.append(frame)

    sar_series = [[[-12.0 for _ in range(10)] for _ in range(10)] for _ in range(3)]

    zones = generate_management_zones(
        plot_id="plot_zone_test",
        ndvi_stack=time_series,
        sar_vv_stack=sar_series,
        grid_spec=grid_spec,
    )

    assert len(zones) >= 2
    for zone_id, zone_data in zones.items():
        assert "label" in zone_data
        assert "area_pct" in zone_data
        assert "mask" in zone_data
        assert len(zone_data["mask"]) == 10
        assert len(zone_data["mask"][0]) == 10
        assert "signature" in zone_data


def test_fallback_on_all_clouds():
    """Verify zone engine gracefully falls back to single-zone when entirely obscured."""
    grid_spec = {
        "width": 5,
        "height": 5,
        "resolution_m": 10.0,
        "bounds": [0.0, 0.0, 50.0, 50.0],
        "crs": "EPSG:32631",
    }
    # All NaN stack (clouds)
    cloud_stack = [[[float("nan") for _ in range(5)] for _ in range(5)] for _ in range(3)]
    zones = generate_management_zones(
        plot_id="plot_cloud_test",
        ndvi_stack=cloud_stack,
        sar_vv_stack=[],
        grid_spec=grid_spec,
    )

    assert len(zones) == 3
    assert "Zone A" in zones
    assert "Zone B" in zones
    assert "Zone C" in zones
    total_area = sum(z["area_pct"] for z in zones.values())
    assert abs(total_area - 100.0) < 1.0


def test_fallback_on_empty_stack():
    """Verify zone engine defaults to geometric zones when no imagery is provided."""
    grid_spec = {
        "width": 4,
        "height": 4,
        "resolution_m": 10.0,
        "bounds": [0.0, 0.0, 40.0, 40.0],
        "crs": "EPSG:32631",
    }
    zones = generate_management_zones(
        plot_id="plot_empty_test",
        ndvi_stack=[],
        sar_vv_stack=[],
        grid_spec=grid_spec,
    )
    assert len(zones) == 3
    total_area = sum(z["area_pct"] for z in zones.values())
    assert abs(total_area - 100.0) < 1.0
