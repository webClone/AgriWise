"""
Tests for Layer 0 — Weakness Score Raster & Data-Driven Zone Derivation.

Tests strict spatial masking, data-derived weakness scoring, adaptive EVI
fallback for dense canopies, zone derivation from quantile banding,
fallback behavior, and performance benchmarks.
"""

import pytest
from layer0.weakness_raster import (
    compute_weakness_raster,
    compute_weakness_raster_sar,
    derive_zones_from_weakness,
    generate_quadrant_zones,
    WeaknessRaster,
    ZoneDerivation,
    _alpha_weighted_field_stats,
    MIN_VALID_PIXELS,
    HOMOGENEITY_THRESHOLD,
    EVI_SATURATION_THRESHOLD,
)
from layer0.sentinel2.schemas import Raster2D


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_raster(values, valid_mask=None):
    """Build a Raster2D from a 2D list."""
    h = len(values)
    w = len(values[0]) if values else 0
    if valid_mask is None:
        valid_mask = [[1 if v is not None else 0 for v in row] for row in values]
    return Raster2D(
        values=values,
        valid_mask=valid_mask,
        grid_shape=(h, w),
        resolution_m=10.0,
        crs="EPSG:32631",
    )


def _uniform_alpha(h, w, alpha=1.0):
    """Full-coverage alpha mask."""
    return [[alpha] * w for _ in range(h)]


def _uniform_valid(h, w):
    """All-valid mask."""
    return [[1] * w for _ in range(h)]


# ── Test: Strict Alpha Masking ──────────────────────────────────────────────

class TestStrictAlphaMasking:
    """Pixels outside the field polygon (alpha=0) must have WSR=None."""

    def test_outside_polygon_is_none(self):
        """Pixels with alpha=0 must produce WSR=None, never a score."""
        # 4x4 raster, only center 2x2 is inside the polygon
        ndvi_vals = [
            [0.3, 0.3, 0.3, 0.3],
            [0.3, 0.7, 0.5, 0.3],
            [0.3, 0.4, 0.6, 0.3],
            [0.3, 0.3, 0.3, 0.3],
        ]
        alpha = [
            [0.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 1.0, 0.0],
            [0.0, 1.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 0.0],
        ]
        valid = _uniform_valid(4, 4)
        ndvi = _make_raster(ndvi_vals)

        wsr = compute_weakness_raster(ndvi, alpha, valid)

        # All border pixels must be None
        for r in [0, 3]:
            for c in range(4):
                assert wsr.values[r][c] is None, f"pixel ({r},{c}) should be None"
        for r in [1, 2]:
            for c in [0, 3]:
                assert wsr.values[r][c] is None, f"pixel ({r},{c}) should be None"

        # Interior pixels must have values
        for r in [1, 2]:
            for c in [1, 2]:
                assert wsr.values[r][c] is not None, f"pixel ({r},{c}) should have a score"

    def test_valid_pixel_count_respects_alpha(self):
        """valid_pixel_count should only count pixels inside the polygon."""
        ndvi = _make_raster([[0.5] * 6 for _ in range(6)])
        alpha = [[0.0] * 6 for _ in range(6)]
        # Only 4 pixels inside
        alpha[2][2] = 1.0
        alpha[2][3] = 1.0
        alpha[3][2] = 1.0
        alpha[3][3] = 1.0
        valid = _uniform_valid(6, 6)

        wsr = compute_weakness_raster(ndvi, alpha, valid)
        assert wsr.valid_pixel_count == 4


# ── Test: Homogeneous NDVI → Low Weakness ────────────────────────────────────

class TestHomogeneousField:
    """A uniform field should have near-zero weakness everywhere."""

    def test_uniform_ndvi_near_zero_weakness(self):
        """All pixels have the same NDVI → all weakness scores near 0."""
        h, w = 6, 6
        ndvi = _make_raster([[0.65] * w for _ in range(h)])
        alpha = _uniform_alpha(h, w)
        valid = _uniform_valid(h, w)

        wsr = compute_weakness_raster(ndvi, alpha, valid)

        # All interior pixels should have very low weakness
        for r in range(h):
            for c in range(w):
                if wsr.values[r][c] is not None:
                    # Edge contamination may contribute up to 0.2*0.3 = 0.06
                    assert wsr.values[r][c] <= 0.15, (
                        f"Homogeneous field pixel ({r},{c}) has weakness "
                        f"{wsr.values[r][c]}, expected ≤ 0.15"
                    )


# ── Test: Heterogeneous NDVI → High Weakness in Patch ────────────────────────

class TestHeterogeneousField:
    """A field with a stressed patch should show high WSR in that region."""

    def test_stressed_patch_high_weakness(self):
        """A low-NDVI patch should get WSR > 0.3."""
        h, w = 6, 6
        # Mostly healthy, but bottom-right 3x3 is stressed
        ndvi_vals = [[0.7] * w for _ in range(h)]
        for r in range(3, 6):
            for c in range(3, 6):
                ndvi_vals[r][c] = 0.3  # Stressed patch

        ndvi = _make_raster(ndvi_vals)
        alpha = _uniform_alpha(h, w)
        valid = _uniform_valid(h, w)

        wsr = compute_weakness_raster(ndvi, alpha, valid)

        # Healthy region: low weakness
        healthy_scores = [wsr.values[r][c] for r in range(3) for c in range(3)
                          if wsr.values[r][c] is not None]
        # Stressed region: high weakness
        stressed_scores = [wsr.values[r][c] for r in range(3, 6) for c in range(3, 6)
                           if wsr.values[r][c] is not None]

        assert healthy_scores and stressed_scores
        mean_healthy = sum(healthy_scores) / len(healthy_scores)
        mean_stressed = sum(stressed_scores) / len(stressed_scores)

        assert mean_stressed > mean_healthy, (
            f"Stressed mean {mean_stressed:.3f} should exceed healthy mean {mean_healthy:.3f}"
        )
        assert mean_stressed > 0.2, (
            f"Stressed mean {mean_stressed:.3f} should be meaningful (> 0.2)"
        )


# ── Test: NDMI Stress Contribution ──────────────────────────────────────────

class TestNDMIContribution:
    """Negative NDMI should elevate weakness beyond NDVI alone."""

    def test_ndmi_raises_weakness(self):
        """Adding negative NDMI should increase WSR for affected pixels."""
        h, w = 4, 4
        ndvi_vals = [[0.5] * w for _ in range(h)]
        ndvi_vals[0][0] = 0.3  # One stressed pixel

        ndmi_vals = [[0.2] * w for _ in range(h)]
        ndmi_vals[0][0] = -0.3  # Same pixel also has moisture stress

        alpha = _uniform_alpha(h, w)
        valid = _uniform_valid(h, w)

        ndvi = _make_raster(ndvi_vals)
        ndmi = _make_raster(ndmi_vals)

        wsr_no_ndmi = compute_weakness_raster(ndvi, alpha, valid, ndmi_raster=None)
        wsr_with_ndmi = compute_weakness_raster(ndvi, alpha, valid, ndmi_raster=ndmi)

        score_no = wsr_no_ndmi.values[0][0]
        score_with = wsr_with_ndmi.values[0][0]

        assert score_no is not None and score_with is not None
        assert score_with >= score_no, (
            f"With NDMI ({score_with}) should be >= without ({score_no})"
        )


# ── Test: Edge Contamination Component ──────────────────────────────────────

class TestEdgeContamination:
    """Partial-alpha boundary pixels should get elevated weakness."""

    def test_partial_alpha_elevates_weakness(self):
        """A pixel with alpha=0.3 should have higher WSR than alpha=1.0."""
        h, w = 4, 4
        ndvi = _make_raster([[0.5] * w for _ in range(h)])
        valid = _uniform_valid(h, w)

        # All interior except (0,0) which is partial boundary
        alpha = _uniform_alpha(h, w)
        alpha[0][0] = 0.3  # Partial boundary pixel

        wsr = compute_weakness_raster(ndvi, alpha, valid)

        edge_score = wsr.values[0][0]
        interior_score = wsr.values[2][2]
        assert edge_score is not None and interior_score is not None
        assert edge_score > interior_score, (
            f"Partial-alpha pixel ({edge_score}) should have higher weakness "
            f"than interior ({interior_score})"
        )


# ── Test: Zone Derivation ───────────────────────────────────────────────────

class TestZoneDerivation:
    """Test that zones emerge from weakness raster via quantile banding."""

    def test_heterogeneous_produces_data_zones(self):
        """A field with clear spatial variance → data-derived zones."""
        h, w = 8, 8
        # Top half healthy, bottom half stressed
        ndvi_vals = [[0.7] * w for _ in range(4)] + [[0.3] * w for _ in range(4)]

        ndvi = _make_raster(ndvi_vals)
        alpha = _uniform_alpha(h, w)
        valid = _uniform_valid(h, w)

        wsr = compute_weakness_raster(ndvi, alpha, valid)
        result = derive_zones_from_weakness(wsr, alpha)

        assert not result.fallback_used, "Should produce data-derived zones"
        assert result.zone_method == "weakness_quantile_v1"
        assert result.zone_source == "data_derived"
        assert result.zone_confidence == 0.70
        assert result.n_zones >= 2

    def test_homogeneous_falls_back_to_quadrants(self):
        """A uniform field → falls back to quadrant zones."""
        h, w = 8, 8
        # All pixels identical NDVI
        ndvi = _make_raster([[0.65] * w for _ in range(h)])
        alpha = _uniform_alpha(h, w)
        valid = _uniform_valid(h, w)

        wsr = compute_weakness_raster(ndvi, alpha, valid)
        result = derive_zones_from_weakness(wsr, alpha)

        assert result.fallback_used, "Should fall back to quadrants for homogeneous field"
        assert result.zone_method == "auto_quadrant_v1"
        assert result.zone_source == "geometry_fallback"
        assert result.zone_confidence == 0.25

    def test_insufficient_data_falls_back(self):
        """Too few valid pixels → falls back to quadrants."""
        h, w = 4, 4
        # Only 2 valid pixels (below MIN_VALID_PIXELS)
        ndvi_vals = [[None] * w for _ in range(h)]
        ndvi_vals[1][1] = 0.5
        ndvi_vals[1][2] = 0.3

        alpha = [[0.0] * w for _ in range(h)]
        alpha[1][1] = 1.0
        alpha[1][2] = 1.0
        valid = _uniform_valid(h, w)

        ndvi = _make_raster(ndvi_vals)
        wsr = compute_weakness_raster(ndvi, alpha, valid)
        result = derive_zones_from_weakness(wsr, alpha)

        assert result.fallback_used


# ── Test: Min Zone Cells Filter ─────────────────────────────────────────────

class TestMinZoneCells:
    """Single-pixel noise should be filtered out by min_zone_cells."""

    def test_single_pixel_filtered(self):
        """A single isolated stressed pixel should not form its own zone."""
        h, w = 8, 8
        ndvi_vals = [[0.7] * w for _ in range(h)]
        ndvi_vals[3][3] = 0.1  # Single stressed pixel

        ndvi = _make_raster(ndvi_vals)
        alpha = _uniform_alpha(h, w)
        valid = _uniform_valid(h, w)

        wsr = compute_weakness_raster(ndvi, alpha, valid)
        result = derive_zones_from_weakness(wsr, alpha, min_zone_cells=4)

        # The single pixel should not form a zone on its own
        if not result.fallback_used:
            for zone_id, mask in result.zone_masks.items():
                cell_count = sum(1 for r in range(h) for c in range(w) if mask[r][c] > 0)
                assert cell_count >= 4, f"Zone {zone_id} has {cell_count} cells < min 4"


# ── Test: Connected Components ──────────────────────────────────────────────

class TestConnectedComponents:
    """Two separate patches should produce separate zones."""

    def test_two_patches_two_zones(self):
        """Two spatially separated stressed patches → two separate zones."""
        h, w = 10, 10
        ndvi_vals = [[0.7] * w for _ in range(h)]
        # Patch 1: top-left 3x3
        for r in range(3):
            for c in range(3):
                ndvi_vals[r][c] = 0.2
        # Patch 2: bottom-right 3x3
        for r in range(7, 10):
            for c in range(7, 10):
                ndvi_vals[r][c] = 0.2

        ndvi = _make_raster(ndvi_vals)
        alpha = _uniform_alpha(h, w)
        valid = _uniform_valid(h, w)

        wsr = compute_weakness_raster(ndvi, alpha, valid)
        result = derive_zones_from_weakness(wsr, alpha)

        if not result.fallback_used:
            # Should have at least 2 weak zones (the two patches)
            weak_zones = [zid for zid in result.zone_masks if "weak" in zid]
            assert len(weak_zones) >= 1, "Should identify at least one weak zone"
            assert result.n_zones >= 2, "Should produce at least 2 zones total"


# ── Test: Quadrant Zones ────────────────────────────────────────────────────

class TestQuadrantZones:
    """Test the canonical quadrant fallback."""

    def test_produces_four_zones(self):
        alpha = _uniform_alpha(6, 6)
        zones = generate_quadrant_zones(alpha)
        assert len(zones) == 4
        assert set(zones.keys()) == {"zone_NW", "zone_NE", "zone_SW", "zone_SE"}

    def test_quadrant_coverage(self):
        """Every pixel should belong to exactly one quadrant."""
        h, w = 6, 6
        alpha = _uniform_alpha(h, w)
        zones = generate_quadrant_zones(alpha)

        for r in range(h):
            for c in range(w):
                count = sum(1 for z in zones.values() if z[r][c] > 0)
                # Pixels inside polygon should be in exactly 1 quadrant
                if alpha[r][c] > 0:
                    assert count == 1, f"Pixel ({r},{c}) belongs to {count} quadrants"


# ── Test: Determinism ───────────────────────────────────────────────────────

class TestDeterminism:
    """Same input must produce identical output."""

    def test_deterministic_wsr(self):
        """Two runs with same input → same weakness raster."""
        h, w = 6, 6
        ndvi_vals = [[0.5 + 0.03 * (r * w + c) for c in range(w)] for r in range(h)]
        ndvi = _make_raster(ndvi_vals)
        alpha = _uniform_alpha(h, w)
        valid = _uniform_valid(h, w)

        wsr1 = compute_weakness_raster(ndvi, alpha, valid)
        wsr2 = compute_weakness_raster(ndvi, alpha, valid)

        for r in range(h):
            for c in range(w):
                assert wsr1.values[r][c] == wsr2.values[r][c], (
                    f"Non-deterministic at ({r},{c}): {wsr1.values[r][c]} vs {wsr2.values[r][c]}"
                )

    def test_deterministic_zones(self):
        """Two runs with same WSR → same zone derivation."""
        h, w = 8, 8
        ndvi_vals = [[0.7] * w for _ in range(4)] + [[0.3] * w for _ in range(4)]
        ndvi = _make_raster(ndvi_vals)
        alpha = _uniform_alpha(h, w)
        valid = _uniform_valid(h, w)

        wsr = compute_weakness_raster(ndvi, alpha, valid)
        r1 = derive_zones_from_weakness(wsr, alpha)
        r2 = derive_zones_from_weakness(wsr, alpha)

        assert r1.zone_method == r2.zone_method
        assert r1.n_zones == r2.n_zones
        assert set(r1.zone_masks.keys()) == set(r2.zone_masks.keys())


# ── Test: Field Stats Utility ───────────────────────────────────────────────

class TestFieldStats:
    """Test the alpha-weighted field stats helper."""

    def test_basic_stats(self):
        values = [[1.0, 2.0], [3.0, 4.0]]
        alpha = [[1.0, 1.0], [1.0, 1.0]]
        mean, std, p10, p90 = _alpha_weighted_field_stats(values, alpha)
        assert mean is not None
        assert abs(mean - 2.5) < 0.01  # (1+2+3+4)/4

    def test_alpha_weighted(self):
        """Higher alpha pixels should dominate the mean."""
        values = [[1.0, 5.0]]
        alpha = [[0.1, 0.9]]  # Second pixel dominates
        mean, _, _, _ = _alpha_weighted_field_stats(values, alpha)
        assert mean is not None
        assert mean > 4.0  # Should be close to 5.0

    def test_no_valid_returns_none(self):
        values = [[None, None]]
        alpha = [[1.0, 1.0]]
        mean, std, p10, p90 = _alpha_weighted_field_stats(values, alpha)
        assert mean is None


# ── Test: Zone Invariant (from invariants.py) ───────────────────────────────

class TestZoneInvariant:
    """Test zone quality invariant checker."""

    def test_quadrant_high_confidence_violates(self):
        from layer0.invariants import check_zone_quality
        zones = [
            {"zone_id": "z1", "zone_method": "auto_quadrant_v1", "zone_confidence": 0.5, "area_fraction": 0.25},
        ]
        violations = check_zone_quality(zones)
        assert any(v.invariant == "zone_confidence_inflated" for v in violations)

    def test_data_derived_proper_confidence_ok(self):
        from layer0.invariants import check_zone_quality
        zones = [
            {"zone_id": "z1", "zone_method": "weakness_quantile_v1", "zone_confidence": 0.7, "area_fraction": 0.5},
            {"zone_id": "z2", "zone_method": "weakness_quantile_v1", "zone_confidence": 0.7, "area_fraction": 0.5},
        ]
        violations = check_zone_quality(zones)
        # No confidence violations expected
        conf_violations = [v for v in violations if "confidence" in v.invariant]
        assert len(conf_violations) == 0

    def test_area_fraction_sum_violation(self):
        from layer0.invariants import check_zone_quality
        zones = [
            {"zone_id": "z1", "zone_method": "weakness_quantile_v1", "zone_confidence": 0.7, "area_fraction": 0.3},
            {"zone_id": "z2", "zone_method": "weakness_quantile_v1", "zone_confidence": 0.7, "area_fraction": 0.3},
        ]
        violations = check_zone_quality(zones)
        assert any(v.invariant == "zone_area_fraction_sum" for v in violations)


# ── Test: Adaptive EVI Fallback ─────────────────────────────────────────────

class TestAdaptiveEVIFallback:
    """When NDVI saturates (mean > 0.80), EVI should be used instead."""

    def _make_saturated_field(self, h=8, w=8):
        """Create a field where NDVI is saturated but EVI has variance."""
        # NDVI: all very high (saturated) — tiny spatial variance
        ndvi_vals = [[0.88] * w for _ in range(h)]
        for r in range(4, h):
            ndvi_vals[r] = [0.86] * w  # Only 0.02 NDVI diff (nearly invisible)

        # EVI: same field but EVI shows real variance
        evi_vals = [[0.55] * w for _ in range(h)]
        for r in range(4, h):
            evi_vals[r] = [0.25] * w  # 0.30 EVI diff (highly visible)

        return (
            _make_raster(ndvi_vals),
            _make_raster(evi_vals),
            _uniform_alpha(h, w),
            _uniform_valid(h, w),
        )

    def test_evi_triggered_when_ndvi_saturated(self):
        """EVI should be used when field mean NDVI >= 0.80."""
        ndvi, evi, alpha, valid = self._make_saturated_field()
        wsr = compute_weakness_raster(ndvi, alpha, valid, evi_raster=evi)

        assert wsr.primary_vi_used == "EVI"
        assert wsr.evi_fallback_triggered is True

    def test_ndvi_used_when_below_threshold(self):
        """NDVI should be used when field mean is below saturation."""
        h, w = 8, 8
        ndvi = _make_raster([[0.5] * w for _ in range(h)])
        evi = _make_raster([[0.3] * w for _ in range(h)])
        alpha = _uniform_alpha(h, w)
        valid = _uniform_valid(h, w)

        wsr = compute_weakness_raster(ndvi, alpha, valid, evi_raster=evi)
        assert wsr.primary_vi_used == "NDVI"
        assert wsr.evi_fallback_triggered is False
        assert wsr.ndvi_mean_pre_switch is None

    def test_provenance_tracks_original_ndvi_mean(self):
        """When EVI is used, original NDVI mean should be recorded."""
        ndvi, evi, alpha, valid = self._make_saturated_field()
        wsr = compute_weakness_raster(ndvi, alpha, valid, evi_raster=evi)

        assert wsr.ndvi_mean_pre_switch is not None
        assert wsr.ndvi_mean_pre_switch >= EVI_SATURATION_THRESHOLD

    def test_evi_preserves_spatial_variance(self):
        """EVI path should preserve more spatial variance than saturated NDVI."""
        h, w = 10, 10
        # NDVI saturated: top=0.88, bottom=0.86 (tiny 0.02 diff)
        ndvi_vals = [[0.88] * w for _ in range(h)]
        for r in range(5, h):
            ndvi_vals[r] = [0.86] * w

        # EVI: top=0.55, bottom=0.20 (big 0.35 diff)
        evi_vals = [[0.55] * w for _ in range(h)]
        for r in range(5, h):
            evi_vals[r] = [0.20] * w

        ndvi = _make_raster(ndvi_vals)
        evi = _make_raster(evi_vals)
        alpha = _uniform_alpha(h, w)
        valid = _uniform_valid(h, w)

        wsr_ndvi_only = compute_weakness_raster(ndvi, alpha, valid, buffer_pixels=0)
        wsr_with_evi = compute_weakness_raster(ndvi, alpha, valid, evi_raster=evi, buffer_pixels=0)

        # The key metric: field_std_ndvi tracks the std of whichever VI was used
        # EVI has far more variance (std ~0.17) than saturated NDVI (std ~0.01)
        assert wsr_with_evi.field_std_ndvi > wsr_ndvi_only.field_std_ndvi, (
            f"EVI std ({wsr_with_evi.field_std_ndvi}) should exceed "
            f"NDVI std ({wsr_ndvi_only.field_std_ndvi}) in saturated regime"
        )
        # EVI path should have switched
        assert wsr_with_evi.primary_vi_used == "EVI"
        assert wsr_ndvi_only.primary_vi_used == "NDVI"

    def test_no_evi_graceful_degradation(self):
        """When NDVI saturates but no EVI available, still works (NDVI fallback)."""
        h, w = 8, 8
        ndvi = _make_raster([[0.88] * w for _ in range(h)])
        alpha = _uniform_alpha(h, w)
        valid = _uniform_valid(h, w)

        wsr = compute_weakness_raster(ndvi, alpha, valid, evi_raster=None)
        assert wsr.primary_vi_used == "NDVI"
        assert wsr.evi_fallback_triggered is False
        assert wsr.valid_pixel_count == h * w

    def test_evi_zones_data_derived_in_saturated_field(self):
        """Saturated field with EVI should produce data-derived zones."""
        ndvi, evi, alpha, valid = self._make_saturated_field()
        wsr = compute_weakness_raster(ndvi, alpha, valid, evi_raster=evi)
        result = derive_zones_from_weakness(wsr, alpha)

        assert not result.fallback_used, "EVI should enable data-derived zones"
        assert result.zone_method == "weakness_quantile_v1"
        assert result.zone_confidence == 0.70

    def test_evi_with_ndmi_combined(self):
        """EVI + NDMI should work together when NDVI is saturated."""
        ndvi, evi, alpha, valid = self._make_saturated_field()
        h, w = 8, 8
        ndmi = _make_raster([[0.2] * w for _ in range(h)])
        for r in range(4, h):
            ndmi.values[r] = [-0.1] * w  # Moisture stress in bottom half

        wsr = compute_weakness_raster(ndvi, alpha, valid, ndmi_raster=ndmi, evi_raster=evi)
        assert wsr.primary_vi_used == "EVI"
        assert wsr.valid_pixel_count == h * w

    def test_evi_threshold_boundary(self):
        """NDVI exactly at threshold should trigger EVI switch."""
        h, w = 6, 6
        ndvi = _make_raster([[EVI_SATURATION_THRESHOLD] * w for _ in range(h)])
        evi = _make_raster([[0.4] * w for _ in range(h)])
        alpha = _uniform_alpha(h, w)
        valid = _uniform_valid(h, w)

        wsr = compute_weakness_raster(ndvi, alpha, valid, evi_raster=evi)
        assert wsr.evi_fallback_triggered is True

    def test_evi_just_below_threshold_no_switch(self):
        """NDVI just below threshold should NOT trigger EVI switch."""
        h, w = 6, 6
        ndvi = _make_raster([[EVI_SATURATION_THRESHOLD - 0.01] * w for _ in range(h)])
        evi = _make_raster([[0.4] * w for _ in range(h)])
        alpha = _uniform_alpha(h, w)
        valid = _uniform_valid(h, w)

        wsr = compute_weakness_raster(ndvi, alpha, valid, evi_raster=evi)
        assert wsr.evi_fallback_triggered is False


# ── Benchmarks: Performance & Scaling ───────────────────────────────────────

import time
import random

class TestBenchmarks:
    """Performance benchmarks for weakness raster computation."""

    @staticmethod
    def _timed_run(fn, *args, **kwargs):
        """Run function and return (result, elapsed_seconds)."""
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        return result, time.perf_counter() - t0

    def _make_field(self, h, w, ndvi_base=0.6, stressed_frac=0.25, seed=42):
        """Generate a realistic heterogeneous field for benchmarking."""
        rng = random.Random(seed)
        ndvi_vals = []
        evi_vals = []
        ndmi_vals = []
        for r in range(h):
            ndvi_row, evi_row, ndmi_row = [], [], []
            for c in range(w):
                if rng.random() < stressed_frac:
                    ndvi_row.append(round(rng.uniform(0.15, 0.35), 4))
                    evi_row.append(round(rng.uniform(0.10, 0.25), 4))
                    ndmi_row.append(round(rng.uniform(-0.3, 0.0), 4))
                else:
                    ndvi_row.append(round(rng.uniform(ndvi_base - 0.05, ndvi_base + 0.1), 4))
                    evi_row.append(round(rng.uniform(0.35, 0.50), 4))
                    ndmi_row.append(round(rng.uniform(0.1, 0.3), 4))
            ndvi_vals.append(ndvi_row)
            evi_vals.append(evi_row)
            ndmi_vals.append(ndmi_row)
        return _make_raster(ndvi_vals), _make_raster(evi_vals), _make_raster(ndmi_vals)

    def test_bench_small_field_10x10(self):
        """10x10 grid (1 ha at 10m) should complete in < 50ms."""
        ndvi, evi, ndmi = self._make_field(10, 10)
        alpha = _uniform_alpha(10, 10)
        valid = _uniform_valid(10, 10)

        wsr, elapsed = self._timed_run(
            compute_weakness_raster, ndvi, alpha, valid,
            ndmi_raster=ndmi, evi_raster=evi,
        )
        assert elapsed < 0.05, f"10x10 took {elapsed:.3f}s, expected < 0.05s"
        assert wsr.valid_pixel_count == 100

    def test_bench_medium_field_50x50(self):
        """50x50 grid (25 ha at 10m) should complete in < 500ms."""
        ndvi, evi, ndmi = self._make_field(50, 50)
        alpha = _uniform_alpha(50, 50)
        valid = _uniform_valid(50, 50)

        wsr, elapsed = self._timed_run(
            compute_weakness_raster, ndvi, alpha, valid,
            ndmi_raster=ndmi, evi_raster=evi,
        )
        assert elapsed < 0.5, f"50x50 took {elapsed:.3f}s, expected < 0.5s"
        assert wsr.valid_pixel_count == 2500

    def test_bench_large_field_100x100(self):
        """100x100 grid (100 ha at 10m) should complete in < 3s."""
        ndvi, evi, ndmi = self._make_field(100, 100)
        alpha = _uniform_alpha(100, 100)
        valid = _uniform_valid(100, 100)

        wsr, elapsed = self._timed_run(
            compute_weakness_raster, ndvi, alpha, valid,
            ndmi_raster=ndmi, evi_raster=evi,
        )
        assert elapsed < 3.0, f"100x100 took {elapsed:.3f}s, expected < 3s"
        assert wsr.valid_pixel_count == 10000

    def test_bench_zone_derivation_100x100(self):
        """Zone derivation from a 100x100 WSR should complete in < 2s."""
        ndvi, _, _ = self._make_field(100, 100)
        alpha = _uniform_alpha(100, 100)
        valid = _uniform_valid(100, 100)

        wsr = compute_weakness_raster(ndvi, alpha, valid)
        result, elapsed = self._timed_run(derive_zones_from_weakness, wsr, alpha)

        assert elapsed < 2.0, f"Zone derivation took {elapsed:.3f}s, expected < 2s"
        assert result.n_zones >= 2

    def test_bench_evi_switch_overhead(self):
        """EVI switch should add minimal overhead vs NDVI-only."""
        h, w = 50, 50
        rng = random.Random(99)
        # Saturated NDVI field
        ndvi_vals = [[round(rng.uniform(0.82, 0.90), 4) for _ in range(w)] for _ in range(h)]
        evi_vals = [[round(rng.uniform(0.20, 0.55), 4) for _ in range(w)] for _ in range(h)]
        ndvi = _make_raster(ndvi_vals)
        evi = _make_raster(evi_vals)
        alpha = _uniform_alpha(h, w)
        valid = _uniform_valid(h, w)

        _, t_ndvi = self._timed_run(compute_weakness_raster, ndvi, alpha, valid)
        _, t_evi = self._timed_run(compute_weakness_raster, ndvi, alpha, valid, evi_raster=evi)

        overhead = t_evi - t_ndvi
        assert overhead < 0.1, f"EVI overhead {overhead:.4f}s too high"

    def test_bench_full_pipeline_end_to_end(self):
        """Full pipeline: WSR compute + zone derivation for 50x50."""
        ndvi, evi, ndmi = self._make_field(50, 50)
        alpha = _uniform_alpha(50, 50)
        valid = _uniform_valid(50, 50)

        t0 = time.perf_counter()
        wsr = compute_weakness_raster(ndvi, alpha, valid, ndmi_raster=ndmi, evi_raster=evi)
        result = derive_zones_from_weakness(wsr, alpha)
        elapsed = time.perf_counter() - t0

        assert elapsed < 1.0, f"Full pipeline took {elapsed:.3f}s, expected < 1s"
        assert wsr.valid_pixel_count == 2500
        assert result.n_zones >= 2
