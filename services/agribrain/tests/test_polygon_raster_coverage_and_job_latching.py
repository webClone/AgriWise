"""Regression tests for polygon raster coverage, coordinate extraction, and background job freshness/manifest locking."""
import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
import numpy as np

from services.agribrain.eo.sentinel import (
    _extract_ring_coordinates,
    _build_process_bounds,
    _compute_raster_dimensions,
)
from services.agribrain.layer10_sire.runner import _rasterize_polygon_mask
import services.agribrain.layer05_asmae.background_jobs as jobs


PLOT_COORDS_LIST = [
    [2.65551, 36.509522],
    [2.655457, 36.507444],
    [2.663261, 36.507194],
    [2.663331, 36.510609],
    [2.65551, 36.509522],
]

PLOT_COORDS_TUPLES = [(float(pt[0]), float(pt[1])) for pt in PLOT_COORDS_LIST]

PLOT_COORDS_SERIALIZED = [{"items": [float(pt[0]), float(pt[1])]} for pt in PLOT_COORDS_LIST]

PLOT_GEOJSON_FEATURE = {
    "type": "Feature",
    "properties": {},
    "geometry": {
        "type": "Polygon",
        "coordinates": [PLOT_COORDS_LIST],
    },
}


def test_extract_ring_coordinates_formats():
    """Verify robust extraction across GeoJSON, list of tuples, and serialized structures."""
    c1 = _extract_ring_coordinates(PLOT_GEOJSON_FEATURE)
    assert c1 is not None and len(c1) == 5
    assert abs(c1[1][0] - 2.655457) < 1e-6

    c2 = _extract_ring_coordinates(PLOT_COORDS_TUPLES)
    assert c2 is not None and len(c2) == 5
    assert abs(c2[1][0] - 2.655457) < 1e-6

    c3 = _extract_ring_coordinates(PLOT_COORDS_SERIALIZED)
    assert c3 is not None and len(c3) == 5
    assert abs(c3[1][0] - 2.655457) < 1e-6

    c4 = _extract_ring_coordinates(PLOT_COORDS_LIST)
    assert c4 is not None and len(c4) == 5


def test_build_process_bounds_encloses_plot():
    """Verify that process bounds completely envelope plot 6a09d9e91dd0c7ed6fce7d50."""
    lat = 36.5089015
    lng = 2.659394
    bounds_dict = _build_process_bounds(PLOT_COORDS_TUPLES, lat, lng)
    bbox = bounds_dict["bbox"]
    min_x, min_y, max_x, max_y = bbox

    # Plot min_lng is 2.655457, max_lng is 2.663331
    # Plot min_lat is 36.507194, max_lat is 36.510609
    assert min_x <= 2.655457, f"min_x {min_x} must be <= 2.655457 to cover west plot border"
    assert max_x >= 2.663331, f"max_x {max_x} must be >= 2.663331 to cover east plot border"
    assert min_y <= 36.507194, f"min_y {min_y} must be <= 36.507194 to cover south plot border"
    assert max_y >= 36.510609, f"max_y {max_y} must be >= 36.510609 to cover north plot border"

    # Verify geometry in bounds is valid closed polygon
    geom = bounds_dict["geometry"]
    assert geom["type"] == "Polygon"
    ring = geom["coordinates"][0]
    assert ring[0] == ring[-1], "Polygon outer ring must be closed"


def test_compute_raster_dimensions_spans_plot():
    """Verify raster width and height reflect true polygon bounds rather than fixed 600m fallback."""
    lat = 36.5089015
    lng = 2.659394
    w, h = _compute_raster_dimensions(PLOT_COORDS_TUPLES, lat, lng, target_resolution_m=10.0)

    # In the old bug, w was 53 (from 0.006 deg fallback)
    # The actual plot span is ~706m east-west, which at 10m requires ~71-72 pixels
    assert w >= 70, f"Raster width {w} should be >= 70 pixels to cover ~706m plot span"
    assert h >= 38, f"Raster height {h} should be >= 38 pixels"


def test_rasterize_polygon_mask_preserves_border_cells():
    """Verify that cells touching or intersecting the polygon retain valid/True values in the mask."""
    # Create a 10x10 grid on [0, 0, 10, 10]
    # Polygon is a triangle [0, 0] -> [10, 0] -> [0, 10] -> [0, 0]
    tri_poly = [(0.0, 0.0), (10.0, 0.0), (0.0, 10.0), (0.0, 0.0)]
    bounds = [0.0, 0.0, 10.0, 10.0]
    mask = _rasterize_polygon_mask(10, 10, bounds, tri_poly)

    # Cells along the diagonal hypotenuse should have border preservation
    assert np.any(mask), "Mask must contain true values"
    assert mask[9, 0] == True or mask[0, 0] == True
    assert np.sum(mask) >= 50, f"Mask area {np.sum(mask)} should cover triangle and intersecting cells"


def test_latest_job_for_plot_prefers_newer_jobs_over_stale_snapshot():
    """Verify latest_job_for_plot does not latch onto an old snapshot job when a newer candidate exists."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        old_id = "a" * 24
        new_id = "b" * 24
        old_job = {
            "job_id": old_id,
            "plot_id": "plot-freshness-test",
            "status": "completed",
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            "completed_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        }
        new_job = {
            "job_id": new_id,
            "plot_id": "plot-freshness-test",
            "status": "completed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        (root / f"{old_id}.job.json").write_text(json.dumps(old_job), encoding="utf-8")
        (root / f"{new_id}.job.json").write_text(json.dumps(new_job), encoding="utf-8")

        mock_head = {"publication_job_id": old_id}

        with patch.object(jobs, "JOBS_DIR", root), \
             patch("services.agribrain.layer05_asmae.plot_snapshot_store.load_latest_plot_snapshot", return_value=mock_head):
            res = jobs.latest_job_for_plot("plot-freshness-test")
            assert res is not None
            assert res.get("job_id") == new_id, f"Expected {new_id} but got {res.get('job_id')}"


def test_reservation_state_blocks_premature_worker_launch():
    """Verify that jobs in 'reserving' status or missing manifest_hash cannot be launched or recovered."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        res_id = "c" * 24
        res_job = {
            "job_id": res_id,
            "plot_id": "plot-res-test",
            "status": "reserving",
            "manifest_ref": f"{res_id}.manifest.json",
        }
        p_res = root / f"{res_id}.job.json"
        p_res.write_text(json.dumps(res_job), encoding="utf-8")

        # _reserve_launch must reject reserving jobs
        assert jobs._reserve_launch(p_res) is None

        # Missing manifest_hash must also be rejected
        no_hash_id = "d" * 24
        no_hash_job = {
            "job_id": no_hash_id,
            "plot_id": "plot-res-test",
            "status": "queued",
            "manifest_ref": f"{no_hash_id}.manifest.json",
        }
        p_no_hash = root / f"{no_hash_id}.job.json"
        p_no_hash.write_text(json.dumps(no_hash_job), encoding="utf-8")
        assert jobs._reserve_launch(p_no_hash) is None

        # recover_pending_jobs must skip both
        with patch.object(jobs, "JOBS_DIR", root):
            assert jobs.recover_pending_jobs(plot_id="plot-res-test") == 0


def test_asmae_raster_matches_ndvi_clean_coverage():
    """Verify that ASMAE diagnostic rasters for plot 6a09d9e91dd0c7ed6fce7d50 completely cover the polygon and match NDVI_CLEAN mask."""
    from services.agribrain.layer05_asmae.plot_snapshot_store import load_latest_plot_snapshot, PlotNamespace
    ns = PlotNamespace(tenant_id="697ddd3bd4195b809226a67b", farm_id="69ad7b6f7e6843e8234afcf6", plot_id="6a09d9e91dd0c7ed6fce7d50")
    snapshot = load_latest_plot_snapshot(ns)
    assert snapshot is not None, "Canonical snapshot for plot must exist"

    surfaces = snapshot.get("frontend_payload", {}).get("surfaces", [])
    surface_map = {s.get("type"): s for s in surfaces if isinstance(s, dict)}

    assert "NDVI_CLEAN" in surface_map, "NDVI_CLEAN must be in publication surfaces"
    assert "CANOPY_ASMAE_VIGOR" in surface_map, "CANOPY_ASMAE_VIGOR must be in publication surfaces"
    assert "ASMAE_VIGOR" in surface_map, "ASMAE_VIGOR must be in publication surfaces"

    ndvi_vals = np.array(surface_map["NDVI_CLEAN"]["values"], dtype=float)
    ndvi_valid = ~np.isnan(ndvi_vals)

    for stype in ["CANOPY_ASMAE_VIGOR", "ASMAE_VIGOR"]:
        asmae_vals = np.array(surface_map[stype]["values"], dtype=float)
        assert asmae_vals.shape == ndvi_vals.shape, f"{stype} shape {asmae_vals.shape} != NDVI shape {ndvi_vals.shape}"
        asmae_valid = ~np.isnan(asmae_vals)

        # Mismatch between valid masks must be zero
        mismatches = np.sum(asmae_valid != ndvi_valid)
        assert mismatches == 0, f"{stype} has {mismatches} pixel mask mismatches with NDVI_CLEAN"

        # Verify border columns (0-8 and 64-71) are fully populated
        for col in list(range(9)) + list(range(64, ndvi_vals.shape[1])):
            col_valid_count = np.sum(asmae_valid[:, col])
            assert col_valid_count > 0, f"Column {col} in {stype} is unexpectedly empty"
