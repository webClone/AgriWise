"""
IR-05: Cumulative scene manifest reconciliation and persistence gates.

Verifies:
1. save_scene_manifest accumulates records across separate historical query windows.
2. Deduplication by (scene_id, source_content_hash) updates existing records without duplication.
3. Preserves prior window scenes when subsequent windows are ingested.
4. load_scene_manifest reconstructs complete HistoricalSceneRecord objects accurately.
5. scene_manifest_index.json reflects the cumulative scene count and full list of scene IDs.
6. Advisory locking and atomic file replacement prevent file corruption under concurrent mutations.
"""
from __future__ import annotations

import os
import json
import hashlib
from concurrent.futures import ThreadPoolExecutor
from typing import List

import pytest

from services.agribrain.layer0.archive.scene_manifest import (
    HistoricalSceneRecord,
    save_scene_manifest,
    load_scene_manifest,
    validate_scene_for_asmae,
    manifest_lock,
)


def _make_record(
    scene_id: str,
    plot_id: str = "plot-test",
    geom_hash: str = "geom-hash-123",
    acq_time: str = "2023-01-15T10:00:00Z",
    source_hash: str = "content-hash-abc",
    cloud: float = 5.0,
    quality: str = "accepted",
) -> HistoricalSceneRecord:
    return HistoricalSceneRecord(
        scene_id=scene_id,
        plot_id=plot_id,
        geometry_hash=geom_hash,
        source="sentinel2",
        mission="S2A",
        product_level="L2A",
        collection="sentinel-2-l2a",
        acquisition_time=acq_time,
        orbit_number="123",
        relative_orbit="45",
        tile_id="T31SDA",
        native_resolution_m=10.0,
        crs="EPSG:32631",
        transform_hash="transform-hash-xyz",
        footprint_hash="footprint-hash-xyz",
        cloud_score=cloud,
        valid_pixel_fraction=0.98,
        quality_status=quality,
        source_content_hash=source_hash,
    )


def test_cumulative_manifest_accumulates_across_windows(tmp_path):
    artifacts_dir = str(tmp_path / "artifacts")
    plot_id = "plot-alpha"
    geom_hash = "ghash-alpha"

    # Window 1: Q1 2023 (2 scenes)
    window1_scenes = [
        _make_record("S2A_20230115", plot_id, geom_hash, acq_time="2023-01-15T10:00:00Z", source_hash="h1"),
        _make_record("S2A_20230215", plot_id, geom_hash, acq_time="2023-02-15T10:00:00Z", source_hash="h2"),
    ]
    res1 = save_scene_manifest(plot_id, geom_hash, window1_scenes, artifacts_dir=artifacts_dir)
    assert len(res1) == 2

    # Verify initial load
    loaded1 = load_scene_manifest(plot_id, geom_hash, artifacts_dir=artifacts_dir)
    assert len(loaded1) == 2
    assert [r.scene_id for r in loaded1] == ["S2A_20230115", "S2A_20230215"]

    # Window 2: Q2 2023 (2 new scenes)
    window2_scenes = [
        _make_record("S2A_20230415", plot_id, geom_hash, acq_time="2023-04-15T10:00:00Z", source_hash="h3"),
        _make_record("S2A_20230515", plot_id, geom_hash, acq_time="2023-05-15T10:00:00Z", source_hash="h4"),
    ]
    res2 = save_scene_manifest(plot_id, geom_hash, window2_scenes, artifacts_dir=artifacts_dir)
    assert len(res2) == 4

    # Verify cumulative accumulation
    loaded2 = load_scene_manifest(plot_id, geom_hash, artifacts_dir=artifacts_dir)
    assert len(loaded2) == 4
    assert [r.scene_id for r in loaded2] == [
        "S2A_20230115", "S2A_20230215", "S2A_20230415", "S2A_20230515"
    ]

    # Verify index file reflects cumulative state
    index_path = os.path.join(artifacts_dir, plot_id, geom_hash, "scene_manifest_index.json")
    assert os.path.exists(index_path)
    with open(index_path, "r", encoding="utf-8") as f:
        idx = json.load(f)
    assert idx["plot_id"] == plot_id
    assert idx["geometry_hash"] == geom_hash
    assert idx["scene_count"] == 4
    assert idx["scenes"] == ["S2A_20230115", "S2A_20230215", "S2A_20230415", "S2A_20230515"]


def test_deduplication_by_scene_and_content_hash(tmp_path):
    artifacts_dir = str(tmp_path / "artifacts")
    plot_id = "plot-beta"
    geom_hash = "ghash-beta"

    rec1 = _make_record("S2A_001", plot_id, geom_hash, acq_time="2023-01-01T00:00:00Z", source_hash="hash-1", cloud=10.0)
    save_scene_manifest(plot_id, geom_hash, [rec1], artifacts_dir=artifacts_dir)

    # Re-save identical record with updated cloud score (updated metadata)
    rec1_updated = _make_record("S2A_001", plot_id, geom_hash, acq_time="2023-01-01T00:00:00Z", source_hash="hash-1", cloud=8.5)
    res = save_scene_manifest(plot_id, geom_hash, [rec1_updated], artifacts_dir=artifacts_dir)
    assert len(res) == 1
    assert res[0].cloud_score == 8.5

    loaded = load_scene_manifest(plot_id, geom_hash, artifacts_dir=artifacts_dir)
    assert len(loaded) == 1
    assert loaded[0].cloud_score == 8.5


def test_manifest_lock_prevents_corruption_under_concurrent_writes(tmp_path):
    artifacts_dir = str(tmp_path / "artifacts")
    plot_id = "plot-gamma"
    geom_hash = "ghash-gamma"

    # Generate 20 distinct records across 4 threads
    batches = [
        [_make_record(f"SCENE_{i:03d}", plot_id, geom_hash, acq_time=f"2023-01-{i+1:02d}T00:00:00Z", source_hash=f"h_{i}")
         for i in range(b * 5, (b + 1) * 5)]
        for b in range(4)
    ]

    def _worker(batch):
        return save_scene_manifest(plot_id, geom_hash, batch, artifacts_dir=artifacts_dir)

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(_worker, batches))

    # All 20 scenes must be cleanly accumulated without corruption or loss
    loaded = load_scene_manifest(plot_id, geom_hash, artifacts_dir=artifacts_dir)
    assert len(loaded) == 20
    assert len({r.scene_id for r in loaded}) == 20

    # Index file must match exactly 20 scenes
    index_path = os.path.join(artifacts_dir, plot_id, geom_hash, "scene_manifest_index.json")
    with open(index_path, "r", encoding="utf-8") as f:
        idx = json.load(f)
    assert idx["scene_count"] == 20


def test_load_nonexistent_manifest_returns_empty(tmp_path):
    res = load_scene_manifest("nonexistent-plot", "nonexistent-geom", artifacts_dir=str(tmp_path))
    assert res == []


def test_validate_scene_for_asmae():
    valid = _make_record("S2A_OK")
    assert validate_scene_for_asmae(valid) is True

    # Missing plot_id
    invalid = _make_record("S2A_BAD", plot_id="")
    assert validate_scene_for_asmae(invalid) is False

    # Rejected status
    rejected = _make_record("S2A_REJ", quality="rejected")
    assert validate_scene_for_asmae(rejected) is False
