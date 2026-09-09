from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from unittest.mock import patch

import numpy as np

from services.agribrain.layer05_asmae import cache
from services.agribrain.layer05_asmae.cache import (
    compute_source_hash,
    deserialize_cached_asmae,
    get_asmae_cache_key,
    serialize_and_cache_asmae,
    stable_value_hash,
)
from services.agribrain.layer05_asmae.schema import ASMAEInput


def _input(scene: dict | None = None) -> ASMAEInput:
    scene = scene or {
        "scene_id": "scene-a",
        "sensor": "S2",
        "acquisition_time": "2026-07-01T00:00:00+00:00",
        "crs": "EPSG:32631",
        "transform": [500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0],
        "width": 2,
        "height": 2,
        "bands": {"B04": np.ones((2, 2), dtype=np.float64)},
        "masks": {"DATAMASK": np.ones((2, 2), dtype=np.uint8)},
        "source_reality": "real_raster",
        "production_usable": False,
        "diagnostic_only": True,
        "admission_status": "diagnostic",
        "validation_status": "passed_diagnostic",
        "provenance_ref": "provider:item-a",
    }
    return ASMAEInput(
        plot_id="plot-a",
        run_id="run-a",
        polygon_geojson={
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
        },
        geometry_hash="geometry-a",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 2),
        layer0_source_packages={"sentinel2": scene},
        mode="standard",
        source_policy="asmae",
        execution_permissions={"production_allowed": False},
        permission_contract_version="authority-v1",
        authority_phase="diagnostic",
        rollout_state="active",
    )


def _output() -> dict:
    return {
        "status": "completed",
        "plot_id": "plot-a",
        "run_id": "run-a",
        "raster_maps": {"vigor": [[0.1, 0.2], [0.3, 0.4]]},
        "uncertainty_maps": {"vigor": [[0.01, None], [0.03, 0.04]]},
        "confidence_maps": {},
        "retrovalidation_maps": {},
        "bma_maps": {},
    }


@contextmanager
def _isolated_cache():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        cache_dir = root / "asmae_cache"
        raster_dir = root / "asmae_rasters"
        operator_dir = root / "asmae_operators"
        cache_dir.mkdir()
        raster_dir.mkdir()
        operator_dir.mkdir()
        with (
            patch.object(cache, "ARTIFACTS_DIR", str(root)),
            patch.object(cache, "CACHE_DIR", str(cache_dir)),
            patch.object(cache, "RASTERS_DIR", str(raster_dir)),
            patch.object(cache, "OPERATORS_DIR", str(operator_dir)),
        ):
            yield root, cache_dir


def _cache_json_path(inp: ASMAEInput, cache_dir: Path) -> Path:
    key = get_asmae_cache_key(inp)
    return cache_dir / f"{key}_{inp.source_policy or 'satellite'}.json"


class CacheIdentityTests(unittest.TestCase):
    def test_canonical_phenology_content_and_lineage_each_invalidate_cache(self):
        original = _input()
        original.phenology_posterior = {
            "current_stage": "UNKNOWN", "stage_authority": "unavailable",
        }
        original.phenology_posterior_hash = "phenology-hash-a"
        original.phenology_worldline_event_id = "phenology-event-a"
        original_key = get_asmae_cache_key(original)
        for field, value in (
            ("phenology_posterior", {
                "current_stage": "REPRODUCTIVE", "stage_authority": "diagnostic",
                "season_progress": {"mean": 0.58},
            }),
            ("phenology_posterior_hash", "phenology-hash-b"),
            ("phenology_worldline_event_id", "phenology-event-b"),
        ):
            with self.subTest(field=field):
                changed = copy.deepcopy(original)
                setattr(changed, field, value)
                self.assertNotEqual(original_key, get_asmae_cache_key(changed))
        self.assertEqual(original_key, get_asmae_cache_key(copy.deepcopy(original)))

    def test_scene_authority_change_changes_source_hash_and_full_key(self):
        diagnostic = _input()
        production_scene = copy.deepcopy(diagnostic.layer0_source_packages["sentinel2"])
        production_scene.update({
            "production_usable": True,
            "diagnostic_only": False,
            "admission_status": "production",
            "validation_status": "passed_production",
        })
        production = _input(production_scene)

        self.assertNotEqual(compute_source_hash(diagnostic), compute_source_hash(production))
        self.assertNotEqual(get_asmae_cache_key(diagnostic), get_asmae_cache_key(production))

    def test_large_array_hidden_middle_cell_changes_hash(self):
        first = np.arange(100_000, dtype=np.float64)
        second = first.copy()
        second[50_000] += 0.125
        self.assertNotEqual(stable_value_hash(first), stable_value_hash(second))

    def test_float64_values_equal_after_float32_quantization_do_not_collide(self):
        first = np.array([1.00000001], dtype=np.float64)
        second = np.nextafter(first, np.inf)
        self.assertEqual(first.astype(np.float32).tobytes(), second.astype(np.float32).tobytes())
        self.assertNotEqual(stable_value_hash(first), stable_value_hash(second))

    def test_array_source_and_key_hashes_are_stable_under_both_import_styles(self):
        workspace = Path(__file__).resolve().parents[4]
        backend = workspace / "services" / "agribrain"
        script = (
            "import importlib,json,numpy as np,sys;from datetime import date,datetime,timezone;"
            "m=importlib.import_module(sys.argv[1]);"
            "s=importlib.import_module(sys.argv[1].rsplit('.',1)[0]+'.schema');"
            "a=np.arange(100000,dtype=np.float64);a[50000]=123.456789012345;"
            "scene=s.ASMAESceneRuntime(scene_id='s',sensor='S2',"
            "acquisition_time=datetime(2026,7,1,tzinfo=timezone.utc),crs='EPSG:32631',"
            "transform=[500000,10,0,4000000,0,-10],width=100000,height=1,"
            "bands={'B04':a},masks={'DATAMASK':np.ones_like(a,dtype=np.uint8)},"
            "source_reality='real_raster',production_usable=False,diagnostic_only=True,"
            "provenance_ref='provider:item');"
            "i=s.ASMAEInput(plot_id='p',run_id='r',polygon_geojson={'type':'Polygon'},"
            "geometry_hash='g',start_date=date(2026,7,1),end_date=date(2026,7,2),"
            "layer0_source_packages={'s2':scene},mode='standard',source_policy='asmae');"
            "print(json.dumps([m.stable_value_hash(a),m.compute_source_hash(i),"
            "m.get_asmae_cache_key(i)]))"
        )

        def run(module: str, pythonpath: Path) -> str:
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(pythonpath)
            return subprocess.check_output(
                [sys.executable, "-c", script, module],
                cwd=workspace,
                env=environment,
                text=True,
            ).strip()

        short_style = run("layer05_asmae.cache", backend)
        qualified_style = run("services.agribrain.layer05_asmae.cache", workspace)
        self.assertEqual(short_style, qualified_style)


class CacheTransactionTests(unittest.TestCase):
    def test_commit_contains_checksum_size_key_shape_and_dtype_manifest(self):
        inp = _input()
        output = _output()
        original = copy.deepcopy(output)
        with _isolated_cache() as (root, cache_dir):
            self.assertTrue(serialize_and_cache_asmae(inp, output))
            self.assertEqual(original, output, "cache serialization mutated caller output")
            document = json.loads(_cache_json_path(inp, cache_dir).read_text(encoding="utf-8"))
            commit = document["_asmae_cache_commit"]
            artifact = commit["raster_artifact"]
            self.assertTrue(commit["committed"])
            self.assertEqual(get_asmae_cache_key(inp), commit["cache_key"])
            self.assertGreater(artifact["size_bytes"], 0)
            self.assertEqual(64, len(artifact["sha256"]))
            self.assertEqual([2, 2], artifact["arrays"]["raster_maps__vigor"]["shape"])
            self.assertEqual("float64", artifact["arrays"]["raster_maps__vigor"]["dtype"])
            self.assertTrue((root / artifact["ref"]).is_file())

            restored = deserialize_cached_asmae(inp)
            self.assertIsNotNone(restored)
            self.assertEqual(original["raster_maps"], restored["raster_maps"])
            self.assertEqual(original["uncertainty_maps"], restored["uncertainty_maps"])

    def test_npz_failure_does_not_publish_json_commit(self):
        inp = _input()
        with _isolated_cache() as (_, cache_dir):
            with patch.object(cache.np, "savez_compressed", side_effect=OSError("disk failure")):
                self.assertFalse(serialize_and_cache_asmae(inp, _output()))
            self.assertFalse(_cache_json_path(inp, cache_dir).exists())
            self.assertIsNone(deserialize_cached_asmae(inp))

    def test_missing_npz_is_a_clean_miss(self):
        inp = _input()
        with _isolated_cache() as (root, cache_dir):
            self.assertTrue(serialize_and_cache_asmae(inp, _output()))
            document = json.loads(_cache_json_path(inp, cache_dir).read_text(encoding="utf-8"))
            (root / document["rasters_artifact_ref"]).unlink()
            self.assertIsNone(deserialize_cached_asmae(inp))

    def test_corrupt_npz_is_a_clean_miss(self):
        inp = _input()
        with _isolated_cache() as (root, cache_dir):
            self.assertTrue(serialize_and_cache_asmae(inp, _output()))
            document = json.loads(_cache_json_path(inp, cache_dir).read_text(encoding="utf-8"))
            artifact_path = root / document["rasters_artifact_ref"]
            corrupted = bytearray(artifact_path.read_bytes())
            corrupted[len(corrupted) // 2] ^= 0x01  # preserve size; checksum must catch it
            artifact_path.write_bytes(corrupted)
            self.assertIsNone(deserialize_cached_asmae(inp))

    def test_legacy_completed_json_with_empty_rasters_is_rejected(self):
        inp = _input()
        with _isolated_cache() as (_, cache_dir):
            path = _cache_json_path(inp, cache_dir)
            path.write_text(
                json.dumps({
                    "status": "completed",
                    "raster_maps": {},
                    "rasters_artifact_ref": "",
                }),
                encoding="utf-8",
            )
            self.assertIsNone(deserialize_cached_asmae(inp))


if __name__ == "__main__":
    unittest.main()
