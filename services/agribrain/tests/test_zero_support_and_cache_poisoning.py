# -*- coding: utf-8 -*-
"""Regression tests for zero-support scene exclusion, cache poisoning prevention,
idempotent plan preparation, and exact snapshot resolution."""

import unittest
from datetime import datetime, timezone

from services.agribrain.layer05_asmae.geometry.scene_quality import (
    SceneQualityResult,
)
from services.agribrain.layer05_asmae.cache import (
    serialize_and_cache_asmae,
    deserialize_cached_asmae,
)
from services.agribrain.layer05_asmae.schema import ASMAEInput
from services.agribrain.layer05_asmae.evidence_capability import (
    prepare_capability_execution_context,
)


class TestZeroSupportAndCachePoisoning(unittest.TestCase):
    def test_zero_support_scene_hard_exclusion(self):
        """Zero valid support scenes must be excluded regardless of metadata scores."""
        q = SceneQualityResult(scene_id="S2B_July27_ZeroSupport", sensor="S2")
        q.clear_pixel_fraction = 0.0
        q.valid_polygon_coverage = 0.0
        q.radiometric_quality = 1.0
        q.temporal_spacing_score = 1.0
        q.metadata_completeness = 1.0
        q.sensor_specific_quality = 1.0
        score = q.compute()
        self.assertFalse(q.included)
        self.assertIn("Zero valid scientific support", q.exclusion_reason)

    def test_cache_poisoning_prevention(self):
        """Failed or fallback spatial results must be refused from canonical cache commit."""
        inp = ASMAEInput(
            run_id="run_01",
            plot_id="plot_cache_test_01",
            polygon_geojson={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
            geometry_hash="hash_01",
            start_date="2026-07-01",
            end_date="2026-07-31",
            layer0_source_packages={},
            source_policy="satellite",
        )
        output_failed = {
            "result_status": "failed_spatial_fallback",
            "reason": "chain_integrity_error",
            "diagnostics": {"chain_integrity_error": True},
        }
        res = serialize_and_cache_asmae(inp, output_failed)
        self.assertFalse(res)
        hit = deserialize_cached_asmae(inp)
        self.assertIsNone(hit)

    def test_prepare_capability_execution_context_idempotence(self):
        """Re-preparing an already-prepared capability context must be idempotent and hash-stable."""
        raw_ctx = {
            "layer0_source_packages": {
                "pkg1": {"scene_id": "scene_01", "acquisition_datetime": "2026-07-17T10:00:00Z"}
            },
            "plot_timeseries": [{"date": "2026-07-17", "ndvi_mean": 0.45}],
        }
        prep1, plan1 = prepare_capability_execution_context(raw_ctx)
        hash1 = prep1["capability_plan_hash"]

        prep2, plan2 = prepare_capability_execution_context(prep1)
        hash2 = prep2["capability_plan_hash"]

        self.assertEqual(hash1, hash2)
        self.assertEqual(plan1.plan_hash(), plan2.plan_hash())


if __name__ == "__main__":
    unittest.main()
