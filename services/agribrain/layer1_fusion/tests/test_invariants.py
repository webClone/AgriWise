"""
Layer 1 — Invariants Module Unit Tests.

Tests all 6 invariant checks on FieldTensor-like objects:
date alignment, NaN/Inf, source coverage, value ranges, grid spec, run_id.
"""

import math
import pytest
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

from layer1_fusion.invariants import enforce_layer1_invariants, InvariantViolation


# ── Mock FieldTensor ─────────────────────────────────────────────────────────

@dataclass
class MockGridSpec:
    width: int = 10
    height: int = 10

@dataclass
class MockTensor:
    daily_state: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)
    grid_spec: Optional[MockGridSpec] = field(default_factory=MockGridSpec)
    run_id: str = "run_001"


# ── Test: Date Alignment ────────────────────────────────────────────────────

class TestDateAlignment:
    def test_aligned_lengths_no_violation(self):
        t = MockTensor(daily_state={
            "ndvi": [0.5, 0.6, 0.7],
            "precipitation": [1.0, 2.0, 3.0],
            "temp_max": [25.0, 26.0, 27.0],
        })
        violations = enforce_layer1_invariants(t)
        assert not any(v.check_name == "date_alignment" for v in violations)

    def test_misaligned_lengths_violation(self):
        t = MockTensor(daily_state={
            "ndvi": [0.5, 0.6, 0.7],
            "precipitation": [1.0, 2.0],  # different length!
        })
        violations = enforce_layer1_invariants(t)
        assert any(v.check_name == "date_alignment" for v in violations)

    def test_single_channel_no_alignment_issue(self):
        t = MockTensor(daily_state={"ndvi": [0.5, 0.6]})
        violations = enforce_layer1_invariants(t)
        assert not any(v.check_name == "date_alignment" for v in violations)

    def test_empty_daily_state_no_violation(self):
        t = MockTensor(daily_state={})
        violations = enforce_layer1_invariants(t)
        assert not any(v.check_name == "date_alignment" for v in violations)


# ── Test: NaN/Inf Detection ─────────────────────────────────────────────────

class TestNaNInfDetection:
    def test_clean_values_no_violation(self):
        t = MockTensor(daily_state={"ndvi": [0.5, 0.6, 0.7]})
        violations = enforce_layer1_invariants(t)
        assert not any(v.check_name == "nan_inf_check" for v in violations)

    def test_nan_detected(self):
        t = MockTensor(daily_state={"ndvi": [0.5, float("nan"), 0.7]})
        violations = enforce_layer1_invariants(t)
        assert any(v.check_name == "nan_inf_check" for v in violations)

    def test_inf_detected(self):
        t = MockTensor(daily_state={"precipitation": [1.0, float("inf"), 3.0]})
        violations = enforce_layer1_invariants(t)
        assert any(v.check_name == "nan_inf_check" for v in violations)

    def test_negative_inf_detected(self):
        t = MockTensor(daily_state={"temp_max": [25.0, float("-inf")]})
        violations = enforce_layer1_invariants(t)
        assert any(v.check_name == "nan_inf_check" for v in violations)

    def test_non_key_channel_not_checked(self):
        """Channels not in key_channels are not checked for NaN."""
        t = MockTensor(daily_state={"custom_var": [float("nan")]})
        violations = enforce_layer1_invariants(t)
        assert not any(v.check_name == "nan_inf_check" for v in violations)


# ── Test: Source Coverage ────────────────────────────────────────────────────

class TestSourceCoverage:
    def test_sources_present_no_violation(self):
        t = MockTensor(provenance={"sources": {"s2": {}, "sensor": {}}})
        violations = enforce_layer1_invariants(t)
        assert not any(v.check_name == "source_coverage" for v in violations)

    def test_no_sources_violation(self):
        t = MockTensor(provenance={"sources": {}})
        violations = enforce_layer1_invariants(t)
        assert any(v.check_name == "source_coverage" for v in violations)

    def test_missing_provenance_dict_no_crash(self):
        t = MockTensor(provenance={})
        violations = enforce_layer1_invariants(t)
        # Should not crash, may or may not flag depending on structure


# ── Test: Value Ranges ───────────────────────────────────────────────────────

class TestValueRanges:
    def test_ndvi_in_range_no_violation(self):
        t = MockTensor(daily_state={"ndvi": [-0.1, 0.0, 0.5, 0.9, 1.0]})
        violations = enforce_layer1_invariants(t)
        assert not any(v.check_name == "ndvi_range" for v in violations)

    def test_ndvi_above_1_violation(self):
        t = MockTensor(daily_state={"ndvi": [0.5, 1.5]})
        violations = enforce_layer1_invariants(t)
        assert any(v.check_name == "ndvi_range" for v in violations)

    def test_ndvi_below_minus1_violation(self):
        t = MockTensor(daily_state={"ndvi": [-1.5, 0.5]})
        violations = enforce_layer1_invariants(t)
        assert any(v.check_name == "ndvi_range" for v in violations)

    def test_ndvi_at_boundaries_ok(self):
        t = MockTensor(daily_state={"ndvi": [-1.0, 1.0]})
        violations = enforce_layer1_invariants(t)
        assert not any(v.check_name == "ndvi_range" for v in violations)

    def test_negative_precipitation_violation(self):
        t = MockTensor(daily_state={"precipitation": [5.0, -1.0, 3.0]})
        violations = enforce_layer1_invariants(t)
        precip_v = [v for v in violations if v.check_name == "precip_non_negative"]
        assert len(precip_v) == 1
        assert precip_v[0].auto_fixed is True

    def test_zero_precipitation_ok(self):
        t = MockTensor(daily_state={"precipitation": [0.0, 5.0, 0.0]})
        violations = enforce_layer1_invariants(t)
        assert not any(v.check_name == "precip_non_negative" for v in violations)


# ── Test: Grid Spec ──────────────────────────────────────────────────────────

class TestGridSpec:
    def test_valid_grid_no_violation(self):
        t = MockTensor(grid_spec=MockGridSpec(10, 10))
        violations = enforce_layer1_invariants(t)
        assert not any(v.check_name == "grid_spec_non_zero" for v in violations)

    def test_zero_width_violation(self):
        t = MockTensor(grid_spec=MockGridSpec(0, 10))
        violations = enforce_layer1_invariants(t)
        assert any(v.check_name == "grid_spec_non_zero" for v in violations)

    def test_zero_height_violation(self):
        t = MockTensor(grid_spec=MockGridSpec(10, 0))
        violations = enforce_layer1_invariants(t)
        assert any(v.check_name == "grid_spec_non_zero" for v in violations)

    def test_no_grid_spec_no_crash(self):
        t = MockTensor(grid_spec=None)
        violations = enforce_layer1_invariants(t)
        assert not any(v.check_name == "grid_spec_non_zero" for v in violations)


# ── Test: Run ID ─────────────────────────────────────────────────────────────

class TestRunID:
    def test_run_id_present_no_violation(self):
        t = MockTensor(run_id="run_001")
        violations = enforce_layer1_invariants(t)
        assert not any(v.check_name == "run_id_present" for v in violations)

    def test_missing_run_id_violation(self):
        t = MockTensor(run_id="")
        violations = enforce_layer1_invariants(t)
        assert any(v.check_name == "run_id_present" for v in violations)


# ── Test: Clean Tensor ───────────────────────────────────────────────────────

class TestCleanTensor:
    def test_clean_tensor_zero_violations(self):
        t = MockTensor(
            daily_state={
                "ndvi": [0.5, 0.6, 0.7],
                "precipitation": [1.0, 2.0, 3.0],
                "temp_max": [25.0, 26.0, 27.0],
                "temp_min": [15.0, 16.0, 17.0],
            },
            provenance={"sources": {"s2": {}, "sensor": {}}},
            grid_spec=MockGridSpec(50, 50),
            run_id="run_prod_001",
        )
        violations = enforce_layer1_invariants(t)
        assert len(violations) == 0
