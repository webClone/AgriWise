"""Unit tests for Layer 1 Spatial Alignment."""

import pytest

from services.agribrain.layer1_fusion.schemas import EvidenceItem, RasterRef
from services.agribrain.layer1_fusion.spatial_alignment import (
    build_spatial_index,
    raster_ref_has_geographic_authority,
)


def test_build_spatial_index_preserves_distinct_scopes():
    """Verify build_spatial_index indexes zones, points, edges without scope collapse."""
    items = [
        EvidenceItem(
            evidence_id="ev_zone1",
            plot_id="plot_spatial",
            variable="ndvi",
            value=0.72,
            source_family="sentinel2",
            source_id="s2",
            observation_type="derived_feature",
            spatial_scope="zone",
            scope_id="zone_north",
        ),
        EvidenceItem(
            evidence_id="ev_zone2",
            plot_id="plot_spatial",
            variable="ndvi",
            value=0.55,
            source_family="sentinel2",
            source_id="s2",
            observation_type="derived_feature",
            spatial_scope="zone",
            scope_id="zone_south",
        ),
        EvidenceItem(
            evidence_id="ev_pt1",
            plot_id="plot_spatial",
            variable="soil_moisture_vwc",
            value=0.28,
            source_family="sensor",
            source_id="probe_sensor_42",
            observation_type="measurement",
            spatial_scope="point",
            scope_id="point_center",
        ),
        EvidenceItem(
            evidence_id="ev_edge",
            plot_id="plot_spatial",
            variable="ndvi",
            value=0.35,
            source_family="sentinel2",
            source_id="s2",
            observation_type="derived_feature",
            spatial_scope="edge",
            scope_id="edge_roadway",
        ),
        EvidenceItem(
            evidence_id="ev_block",
            plot_id="plot_spatial",
            variable="irrigation_depth_mm",
            value=25.0,
            source_family="user_event",
            source_id="farm_log",
            observation_type="event",
            spatial_scope="irrigation_block",
            scope_id="block_b",
        ),
    ]

    index = build_spatial_index(items, plot_id="plot_spatial")

    assert index.plot_id == "plot_spatial"
    assert len(index.zones) == 2
    zone_ids = {z.zone_id for z in index.zones}
    assert zone_ids == {"zone_north", "zone_south"}

    assert len(index.points) == 1
    assert index.points[0].point_id == "point_center"
    assert index.points[0].device_id == "probe_sensor_42"

    assert len(index.edge_regions) == 1
    assert index.edge_regions[0].edge_id == "edge_roadway"

    assert len(index.irrigation_blocks) == 1
    assert index.irrigation_blocks[0].block_id == "block_b"


def test_raster_ref_geographic_authority():
    """Verify raster_ref_has_geographic_authority enforces CRS, transform and bounds."""
    # Valid authoritative raster ref
    auth_ref = RasterRef(
        raster_id="raster_ndvi",
        variable="ndvi",
        crs="EPSG:32631",
        bounds=(500000.0, 4000000.0, 500100.0, 4000100.0),
        transform=(500000.0, 10.0, 0.0, 4000100.0, 0.0, -10.0),
        width=10,
        height=10,
        resolution_m=10.0,
        real_provider_product=True,
    )
    assert raster_ref_has_geographic_authority(auth_ref) is True

    # Invalid: missing transform
    missing_tf = RasterRef(
        raster_id="raster_bad",
        variable="ndvi",
        crs="EPSG:32631",
        bounds=(0.0, 0.0, 100.0, 100.0),
        transform=None,
    )
    assert raster_ref_has_geographic_authority(missing_tf) is False
