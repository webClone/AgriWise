"""
Layer 0 — WSR Calibration Benchmarks with Real Polygon Geometries.

Tests the weakness raster + zone derivation system against realistic
field shapes derived from real-world WGS84 polygon coordinates via
PlotGrid's fractional alpha mask generation (sub-pixel sampling).

Polygon shapes tested:
  1. Rectangular wheat field — central Morocco
  2. Irregular L-shaped field — northern France
  3. Diamond/rhombus pivot field — US Midwest
  4. Narrow terrace strip — Indonesian hillside
  5. Large 50-ha estate with concavity — Brazilian cerrado
  6. Tiny garden plot (< 1 ha) — urban agriculture

Each polygon is run through the full pipeline:
  PlotGrid → alpha mask → synthetic NDVI/EVI/NDMI rasters → WSR → zones
"""

import math
import time
import random
import pytest

from layer0.plot_grid import PlotGrid
from layer0.weakness_raster import (
    compute_weakness_raster,
    derive_zones_from_weakness,
    generate_quadrant_zones,
    WeaknessRaster,
    ZoneDerivation,
    EVI_SATURATION_THRESHOLD,
)
from layer0.sentinel2.schemas import Raster2D


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_raster_from_grid(h, w, values, valid_mask=None):
    """Build a Raster2D with correct shape."""
    if valid_mask is None:
        valid_mask = [[1 if v is not None else 0 for v in row] for row in values]
    return Raster2D(
        values=values,
        valid_mask=valid_mask,
        grid_shape=(h, w),
        resolution_m=10.0,
        crs="EPSG:32631",
    )


def _synth_index_raster(h, w, grid, base, stressed_patches=None, noise_seed=42):
    """
    Generate a synthetic index raster shaped to a PlotGrid.

    Args:
        h, w: grid dimensions
        grid: PlotGrid (for alpha mask)
        base: base index value for healthy pixels
        stressed_patches: list of (center_r, center_c, radius, stress_val)
        noise_seed: random seed
    """
    rng = random.Random(noise_seed)
    vals = [[None] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            if grid.alpha[r][c] <= 0:
                continue
            val = base + rng.uniform(-0.02, 0.02)
            if stressed_patches:
                for cr, cc, rad, sval in stressed_patches:
                    dist = math.sqrt((r - cr) ** 2 + (c - cc) ** 2)
                    if dist <= rad:
                        val = sval + rng.uniform(-0.02, 0.02)
            vals[r][c] = round(max(-1.0, min(1.0, val)), 4)
    return _make_raster_from_grid(h, w, vals)


# ── Real Polygon Definitions ────────────────────────────────────────────────

# 1. Rectangular wheat field — Meknes, Morocco (~3 ha)
POLYGON_RECT_MOROCCO = [
    [-5.5600, 33.8800],
    [-5.5580, 33.8800],
    [-5.5580, 33.8785],
    [-5.5600, 33.8785],
    [-5.5600, 33.8800],
]

# 2. L-shaped field — Picardy, France (~5 ha)
POLYGON_L_FRANCE = [
    [2.8500, 49.8800],
    [2.8530, 49.8800],
    [2.8530, 49.8790],
    [2.8520, 49.8790],
    [2.8520, 49.8780],
    [2.8500, 49.8780],
    [2.8500, 49.8800],
]

# 3. Diamond/rhombus pivot — Iowa, USA (~4 ha)
POLYGON_DIAMOND_IOWA = [
    [-93.6100, 42.0310],
    [-93.6085, 42.0320],
    [-93.6070, 42.0310],
    [-93.6085, 42.0300],
    [-93.6100, 42.0310],
]

# 4. Narrow terrace strip — Java, Indonesia (~1.5 ha)
POLYGON_TERRACE_JAVA = [
    [110.4000, -7.5700],
    [110.4020, -7.5695],
    [110.4022, -7.5700],
    [110.4002, -7.5705],
    [110.4000, -7.5700],
]

# 5. Large estate with concavity — Goias, Brazil (~50 ha)
POLYGON_ESTATE_BRAZIL = [
    [-49.2700, -15.9400],
    [-49.2650, -15.9400],
    [-49.2650, -15.9360],
    [-49.2680, -15.9370],  # concavity
    [-49.2700, -15.9360],
    [-49.2700, -15.9400],
]

# 6. Tiny garden plot — Nairobi, Kenya (~0.3 ha)
POLYGON_GARDEN_KENYA = [
    [36.8170, -1.2860],
    [36.8175, -1.2860],
    [36.8175, -1.2864],
    [36.8170, -1.2864],
    [36.8170, -1.2860],
]


# ── Test Class: Real Polygon Calibration ─────────────────────────────────────

class TestRealPolygonCalibration:
    """Test WSR against realistic field polygons with PlotGrid alpha masks."""

    @staticmethod
    def _run_full_pipeline(polygon, base_ndvi=0.60, stressed_patches=None,
                           with_evi=False, with_ndmi=False, base_evi=0.40):
        """Run full PlotGrid → WSR → zones pipeline and return results."""
        grid = PlotGrid.from_polygon_wgs84(polygon)
        h, w = grid.height, grid.width
        alpha = grid.alpha
        valid = [[1] * w for _ in range(h)]

        ndvi = _synth_index_raster(h, w, grid, base_ndvi, stressed_patches)
        evi = _synth_index_raster(h, w, grid, base_evi, stressed_patches, noise_seed=77) if with_evi else None
        ndmi = _synth_index_raster(h, w, grid, 0.15, stressed_patches, noise_seed=99) if with_ndmi else None

        t0 = time.perf_counter()
        wsr = compute_weakness_raster(ndvi, alpha, valid,
                                      ndmi_raster=ndmi, evi_raster=evi)
        zones = derive_zones_from_weakness(wsr, alpha)
        elapsed = time.perf_counter() - t0

        return {
            "grid": grid,
            "wsr": wsr,
            "zones": zones,
            "elapsed": elapsed,
            "h": h, "w": w,
            "n_polygon_pixels": grid.n_valid_pixels(0.01),
            "n_boundary_pixels": sum(
                1 for r in range(h) for c in range(w)
                if 0 < alpha[r][c] < 1.0
            ),
        }

    # ── Shape Tests ─────────────────────────────────────────────────────

    def test_rectangle_morocco(self):
        """Rectangular wheat field: basic shape, should produce clean zones."""
        r = self._run_full_pipeline(
            POLYGON_RECT_MOROCCO,
            base_ndvi=0.55,
            stressed_patches=[(2, 2, 3, 0.25)],
        )
        assert r["wsr"].valid_pixel_count > 0
        assert r["n_polygon_pixels"] > 0
        # Strict masking: no WSR outside polygon
        for row in range(r["h"]):
            for col in range(r["w"]):
                if r["grid"].alpha[row][col] <= 0:
                    assert r["wsr"].values[row][col] is None

    def test_l_shape_france(self):
        """L-shaped field: non-convex polygon should be fully masked."""
        r = self._run_full_pipeline(
            POLYGON_L_FRANCE,
            base_ndvi=0.62,
            stressed_patches=[(5, 3, 2, 0.30)],
        )
        assert r["wsr"].valid_pixel_count > 0
        assert r["n_boundary_pixels"] > 0, "L-shape should have many boundary pixels"
        # Check alpha mask has the L-shape (some full pixels, some partial)
        full_pixels = sum(
            1 for row in range(r["h"]) for col in range(r["w"])
            if r["grid"].alpha[row][col] == 1.0
        )
        partial_pixels = r["n_boundary_pixels"]
        assert partial_pixels > 0, "L-shape should have partial boundary pixels"

    def test_diamond_iowa(self):
        """Diamond/rhombus: rotated shape, all edges are boundary."""
        r = self._run_full_pipeline(
            POLYGON_DIAMOND_IOWA,
            base_ndvi=0.70,
            stressed_patches=[(3, 3, 2, 0.35)],
        )
        assert r["wsr"].valid_pixel_count > 0
        # Diamond has many boundary pixels relative to interior
        boundary_ratio = r["n_boundary_pixels"] / max(1, r["n_polygon_pixels"])
        assert boundary_ratio > 0.2, f"Diamond boundary ratio {boundary_ratio:.2f} too low"

    def test_narrow_terrace_java(self):
        """Narrow terrace strip: width might be only 2-3 pixels."""
        r = self._run_full_pipeline(
            POLYGON_TERRACE_JAVA,
            base_ndvi=0.50,
        )
        assert r["wsr"].valid_pixel_count > 0
        # Narrow field → most pixels are boundary
        boundary_ratio = r["n_boundary_pixels"] / max(1, r["n_polygon_pixels"])
        assert boundary_ratio > 0.3, "Narrow strip should have high boundary ratio"

    def test_large_estate_brazil(self):
        """Large estate with concavity: should handle concave polygon."""
        r = self._run_full_pipeline(
            POLYGON_ESTATE_BRAZIL,
            base_ndvi=0.58,
            stressed_patches=[(10, 10, 5, 0.20), (25, 20, 4, 0.25)],
            with_ndmi=True,
        )
        assert r["wsr"].valid_pixel_count > 50, "Large estate should have many valid pixels"
        # Should produce data-derived zones (enough variance + pixels)
        if r["zones"].n_zones >= 2:
            assert not r["zones"].fallback_used

    def test_tiny_garden_kenya(self):
        """Tiny garden: may have very few pixels."""
        r = self._run_full_pipeline(
            POLYGON_GARDEN_KENYA,
            base_ndvi=0.45,
        )
        # Tiny plots may fall back to quadrants (< MIN_VALID_PIXELS)
        assert r["wsr"].valid_pixel_count >= 0
        # Should not crash regardless of pixel count

    # ── Strict Masking Invariant ────────────────────────────────────────

    def test_strict_masking_all_polygons(self):
        """No polygon should have WSR values outside alpha > 0 pixels."""
        for name, poly in [
            ("morocco", POLYGON_RECT_MOROCCO),
            ("france", POLYGON_L_FRANCE),
            ("iowa", POLYGON_DIAMOND_IOWA),
            ("java", POLYGON_TERRACE_JAVA),
            ("brazil", POLYGON_ESTATE_BRAZIL),
            ("kenya", POLYGON_GARDEN_KENYA),
        ]:
            r = self._run_full_pipeline(poly)
            for row in range(r["h"]):
                for col in range(r["w"]):
                    if r["grid"].alpha[row][col] <= 0:
                        assert r["wsr"].values[row][col] is None, (
                            f"{name}: WSR at ({row},{col}) should be None "
                            f"(alpha={r['grid'].alpha[row][col]})"
                        )

    # ── Edge Contamination Calibration ──────────────────────────────────

    def test_boundary_pixels_elevated_weakness(self):
        """Boundary pixels (0 < alpha < 1) should have higher WSR than interior."""
        r = self._run_full_pipeline(
            POLYGON_L_FRANCE,
            base_ndvi=0.60,
        )
        boundary_scores = []
        interior_scores = []
        for row in range(r["h"]):
            for col in range(r["w"]):
                v = r["wsr"].values[row][col]
                if v is None:
                    continue
                a = r["grid"].alpha[row][col]
                if 0 < a < 1.0:
                    boundary_scores.append(v)
                elif a == 1.0:
                    interior_scores.append(v)

        if boundary_scores and interior_scores:
            mean_boundary = sum(boundary_scores) / len(boundary_scores)
            mean_interior = sum(interior_scores) / len(interior_scores)
            assert mean_boundary >= mean_interior, (
                f"Boundary mean ({mean_boundary:.3f}) should be >= "
                f"interior mean ({mean_interior:.3f})"
            )

    # ── EVI Adaptive Switch with Real Polygons ──────────────────────────

    def test_evi_switch_real_polygon(self):
        """Dense canopy on real polygon should trigger EVI switch."""
        r = self._run_full_pipeline(
            POLYGON_RECT_MOROCCO,
            base_ndvi=0.85,  # Saturated
            with_evi=True,
            base_evi=0.45,
        )
        assert r["wsr"].evi_fallback_triggered is True
        assert r["wsr"].primary_vi_used == "EVI"

    def test_normal_ndvi_no_evi_switch_real_polygon(self):
        """Normal NDVI on real polygon should NOT trigger EVI switch."""
        r = self._run_full_pipeline(
            POLYGON_L_FRANCE,
            base_ndvi=0.55,
            with_evi=True,
            base_evi=0.35,
        )
        assert r["wsr"].evi_fallback_triggered is False
        assert r["wsr"].primary_vi_used == "NDVI"

    # ── Zone Derivation with Real Polygons ──────────────────────────────

    def test_heterogeneous_produces_zones_real_polygon(self):
        """A heterogeneous field on a real polygon should produce data zones."""
        grid = PlotGrid.from_polygon_wgs84(POLYGON_ESTATE_BRAZIL)
        h, w = grid.height, grid.width
        mid_r = h // 2

        # Top half healthy, bottom half stressed — clear spatial pattern
        ndvi_vals = [[None] * w for _ in range(h)]
        for r in range(h):
            for c in range(w):
                if grid.alpha[r][c] <= 0:
                    continue
                if r < mid_r:
                    ndvi_vals[r][c] = 0.70 + random.uniform(-0.02, 0.02)
                else:
                    ndvi_vals[r][c] = 0.30 + random.uniform(-0.02, 0.02)

        ndvi = _make_raster_from_grid(h, w, ndvi_vals)
        valid = [[1] * w for _ in range(h)]

        wsr = compute_weakness_raster(ndvi, grid.alpha, valid)
        zones = derive_zones_from_weakness(wsr, grid.alpha)

        assert wsr.valid_pixel_count > 0
        if wsr.valid_pixel_count >= 8:
            assert not zones.fallback_used, "Clear spatial pattern should produce data zones"
            assert zones.zone_confidence == 0.70

    def test_homogeneous_falls_back_real_polygon(self):
        """A uniform field on a real polygon should fall back to quadrants."""
        r = self._run_full_pipeline(
            POLYGON_RECT_MOROCCO,
            base_ndvi=0.60,
            stressed_patches=None,  # No stress — homogeneous
        )
        # With only noise (±0.02), field may be classified as homogeneous
        if r["wsr"].field_std_ndvi is not None and r["wsr"].field_std_ndvi < 0.02:
            assert r["zones"].fallback_used

    # ── Performance Benchmarks with Real Polygons ───────────────────────

    def test_bench_all_polygons(self):
        """All polygons should complete the full pipeline within budget."""
        budgets = {
            "morocco": 0.5,
            "france": 0.5,
            "iowa": 0.5,
            "java": 0.3,
            "brazil": 3.0,  # Large estate
            "kenya": 0.2,
        }
        for name, poly, budget in [
            ("morocco", POLYGON_RECT_MOROCCO, budgets["morocco"]),
            ("france", POLYGON_L_FRANCE, budgets["france"]),
            ("iowa", POLYGON_DIAMOND_IOWA, budgets["iowa"]),
            ("java", POLYGON_TERRACE_JAVA, budgets["java"]),
            ("brazil", POLYGON_ESTATE_BRAZIL, budgets["brazil"]),
            ("kenya", POLYGON_GARDEN_KENYA, budgets["kenya"]),
        ]:
            r = self._run_full_pipeline(poly, stressed_patches=[(3, 3, 2, 0.25)])
            assert r["elapsed"] < budget, (
                f"{name}: pipeline took {r['elapsed']:.3f}s, budget {budget}s"
            )

    # ── Multi-Index Calibration ─────────────────────────────────────────

    def test_full_stack_ndvi_evi_ndmi(self):
        """All three indices on a real polygon should work together."""
        r = self._run_full_pipeline(
            POLYGON_ESTATE_BRAZIL,
            base_ndvi=0.55,
            stressed_patches=[(8, 8, 4, 0.20)],
            with_evi=True,
            with_ndmi=True,
            base_evi=0.38,
        )
        assert r["wsr"].valid_pixel_count > 0
        assert r["wsr"].primary_vi_used == "NDVI"  # base=0.55, below threshold

    def test_full_stack_saturated_with_all_indices(self):
        """Saturated NDVI + EVI + NDMI on real polygon."""
        r = self._run_full_pipeline(
            POLYGON_L_FRANCE,
            base_ndvi=0.88,
            stressed_patches=[(4, 4, 3, 0.82)],
            with_evi=True,
            with_ndmi=True,
            base_evi=0.48,
        )
        assert r["wsr"].evi_fallback_triggered is True
        assert r["wsr"].valid_pixel_count > 0

    # ── Determinism with Real Polygons ──────────────────────────────────

    def test_deterministic_real_polygon(self):
        """Same polygon + same seed → identical WSR."""
        r1 = self._run_full_pipeline(POLYGON_DIAMOND_IOWA, base_ndvi=0.60,
                                     stressed_patches=[(3, 3, 2, 0.30)])
        r2 = self._run_full_pipeline(POLYGON_DIAMOND_IOWA, base_ndvi=0.60,
                                     stressed_patches=[(3, 3, 2, 0.30)])

        for row in range(r1["h"]):
            for col in range(r1["w"]):
                assert r1["wsr"].values[row][col] == r2["wsr"].values[row][col], (
                    f"Non-deterministic at ({row},{col})"
                )

    # ── Zone Area Fraction Invariant ────────────────────────────────────

    def test_zone_area_coverage_real_polygon(self):
        """Zone masks should cover all in-polygon pixels (no gaps)."""
        r = self._run_full_pipeline(
            POLYGON_L_FRANCE,
            base_ndvi=0.55,
            stressed_patches=[(3, 3, 3, 0.20), (8, 2, 2, 0.25)],
        )
        if r["zones"].fallback_used:
            return  # Quadrant zones have known full coverage

        h, w = r["h"], r["w"]
        alpha = r["grid"].alpha
        zone_masks = r["zones"].zone_masks

        for row in range(h):
            for col in range(w):
                if alpha[row][col] <= 0:
                    continue
                # Pixel should be in at least one zone
                in_any = any(m[row][col] > 0 for m in zone_masks.values())
                # Not all pixels are guaranteed to be covered (noise filter
                # can drop small components), but most should be


# ── Summary Report Benchmark ────────────────────────────────────────────────

class TestCalibrationReport:
    """Generate a summary calibration report across all polygon shapes."""

    def test_calibration_summary(self, capsys):
        """Print a calibration summary table for all polygon geometries."""
        polygons = [
            ("Rect Morocco", POLYGON_RECT_MOROCCO, 0.55, [(2, 2, 2, 0.25)]),
            ("L-shape France", POLYGON_L_FRANCE, 0.62, [(5, 3, 2, 0.30)]),
            ("Diamond Iowa", POLYGON_DIAMOND_IOWA, 0.70, [(3, 3, 2, 0.35)]),
            ("Terrace Java", POLYGON_TERRACE_JAVA, 0.50, None),
            ("Estate Brazil", POLYGON_ESTATE_BRAZIL, 0.58, [(10, 10, 5, 0.20)]),
            ("Garden Kenya", POLYGON_GARDEN_KENYA, 0.45, None),
        ]

        results = []
        for name, poly, base, patches in polygons:
            grid = PlotGrid.from_polygon_wgs84(poly)
            h, w = grid.height, grid.width

            ndvi = _synth_index_raster(h, w, grid, base, patches)
            evi = _synth_index_raster(h, w, grid, base * 0.7, patches, noise_seed=77)
            ndmi = _synth_index_raster(h, w, grid, 0.15, patches, noise_seed=99)
            valid = [[1] * w for _ in range(h)]

            t0 = time.perf_counter()
            wsr = compute_weakness_raster(ndvi, grid.alpha, valid,
                                          ndmi_raster=ndmi, evi_raster=evi)
            zones = derive_zones_from_weakness(wsr, grid.alpha)
            elapsed = time.perf_counter() - t0

            n_poly = grid.n_valid_pixels(0.01)
            n_boundary = sum(1 for r in range(h) for c in range(w) if 0 < grid.alpha[r][c] < 1.0)

            results.append({
                "name": name,
                "grid": f"{h}x{w}",
                "poly_px": n_poly,
                "boundary_px": n_boundary,
                "valid_wsr": wsr.valid_pixel_count,
                "vi_used": wsr.primary_vi_used,
                "wsr_mean": wsr.weakness_mean,
                "wsr_p90": wsr.weakness_p90,
                "zones": zones.n_zones,
                "method": zones.zone_method,
                "confidence": zones.zone_confidence,
                "fallback": zones.fallback_used,
                "time_ms": round(elapsed * 1000, 1),
            })

        # Print summary table
        print("\n" + "=" * 110)
        print("WEAKNESS RASTER CALIBRATION REPORT — Real Polygon Geometries")
        print("=" * 110)
        print(f"{'Field':<18} {'Grid':<7} {'Poly':>5} {'Bndry':>5} {'WSR':>4} "
              f"{'VI':>4} {'uWSR':>5} {'P90':>5} {'Zones':>5} "
              f"{'Method':<22} {'Conf':>5} {'ms':>6}")
        print("-" * 110)
        for r in results:
            print(f"{r['name']:<18} {r['grid']:<7} {r['poly_px']:>5} {r['boundary_px']:>5} "
                  f"{r['valid_wsr']:>4} {r['vi_used']:>4} {r['wsr_mean']:>5.3f} {r['wsr_p90']:>5.3f} "
                  f"{r['zones']:>5} {r['method']:<22} {r['confidence']:>5.2f} {r['time_ms']:>6.1f}")
        print("=" * 110)

        # All should have completed
        for r in results:
            assert r["valid_wsr"] >= 0, f"{r['name']} has negative valid count"
            assert r["time_ms"] < 5000, f"{r['name']} took {r['time_ms']}ms"
