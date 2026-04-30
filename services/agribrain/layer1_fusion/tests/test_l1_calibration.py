"""
Layer 1 — Real-World Scenario Calibration & Performance Benchmarks.

Tests the full 18-step fusion pipeline against 6 realistic multi-source
scenarios with typed fixture objects, timing budgets, determinism
verification, and a calibration report table.

Scenarios:
  1. Full-stack irrigated field (S2 + sensor, ~20 evidence items)
  2. Sensor-only smallholder (no satellite, degraded health)
  3. Satellite-only remote field (no ground sensors)
  4. Multi-scene S2 + sensor with raster refs
  5. Stale S2 + sensor (both > 10 days old)
  6. Minimal empty plot (no sources at all)
"""

import time
import pytest
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from layer1_fusion.engine import Layer1FusionEngine
from layer1_fusion.schemas import Layer1InputBundle, Layer1ContextPackage


# ── Typed Fixture Objects (matching adapter expectations) ───────────────────

_TS = datetime(2026, 4, 15, 12, 0, 0, tzinfo=timezone.utc)


@dataclass
class S2Meta:
    scene_id: str = "S2A_20260415"
    acquisition_datetime: datetime = field(default_factory=lambda: _TS - timedelta(days=2))
    qa_version: str = "s2qa_v1"
    grid_alignment_hash: str = "h1"

@dataclass
class S2QA:
    usable: bool = True
    reliability_weight: float = 0.85
    cloud_fraction: float = 0.05

@dataclass
class S2PlotSummary:
    ndvi_mean: float = 0.65
    ndmi_mean: float = 0.30
    ndre_mean: float = 0.20
    evi_mean: float = 0.40
    bsi_mean: float = 0.08
    vegetation_fraction_scl: float = 0.80
    bare_soil_fraction_scl: float = 0.05

@dataclass
class S2ZoneSummary:
    zone_id: str = "zone_1"
    ndvi_mean: float = 0.60
    ndmi_mean: float = 0.25
    ndre_mean: float = 0.18
    reliability: float = 0.80
    cloud_fraction: float = 0.05

@dataclass
class S2Package:
    plot_id: str = "test_plot"
    metadata: S2Meta = field(default_factory=S2Meta)
    qa: S2QA = field(default_factory=S2QA)
    plot_summary: S2PlotSummary = field(default_factory=S2PlotSummary)
    zone_summaries: List = field(default_factory=list)
    indices: Dict = field(default_factory=dict)

@dataclass
class MockRaster:
    content_hash: str = "raster_hash_001"

@dataclass
class SensorReading:
    device_id: str = "dragino_001"
    variable: str = "soil_moisture_vwc"
    value: float = 0.32
    unit: str = "fraction"
    timestamp: datetime = field(default_factory=lambda: _TS - timedelta(hours=2))

@dataclass
class SensorQA:
    usable: bool = True
    reading_reliability: float = 0.88
    update_allowed: bool = True

@dataclass
class SensorPackage:
    plot_id: str = "test_plot"
    readings: List = field(default_factory=lambda: [
        SensorReading(variable="soil_moisture_vwc", value=0.32, unit="fraction"),
    ])
    qa_results: List = field(default_factory=lambda: [SensorQA()])
    aggregates: List = field(default_factory=list)
    process_forcing_events: List = field(default_factory=list)
    window_start: datetime = field(default_factory=lambda: _TS - timedelta(hours=6))
    window_end: datetime = field(default_factory=lambda: _TS)

@dataclass
class ForecastDay:
    date: str
    precipitation_mm: float = 0.0
    et0_mm: float = 4.0
    temp_max: float = 28.0
    temp_min: float = 15.0

@dataclass
class ForecastPackage:
    plot_id: str = "test_plot"
    forecast_process_forcing: List[ForecastDay] = field(default_factory=list)


def _bundle(**kw):
    defaults = dict(
        plot_id="test_plot", run_id="test_run", run_timestamp=_TS,
        window_start=_TS - timedelta(days=30), window_end=_TS,
    )
    defaults.update(kw)
    return Layer1InputBundle(**defaults)


# ── Scenario 1: Full-Stack ──────────────────────────────────────────────────

class TestScenarioFullStack:
    """Full-stack field: S2 + sensor → rich evidence, all prohibitions pass."""

    def _build(self):
        s2 = S2Package(
            metadata=S2Meta(scene_id="S2A_20260413",
                           acquisition_datetime=_TS - timedelta(days=2)),
            plot_summary=S2PlotSummary(ndvi_mean=0.68, ndmi_mean=0.25,
                                       evi_mean=0.42),
            zone_summaries=[
                S2ZoneSummary(zone_id="z1", ndvi_mean=0.72),
                S2ZoneSummary(zone_id="z2", ndvi_mean=0.55),
            ],
            indices={"ndvi": MockRaster()},
        )
        sensor = SensorPackage(
            readings=[
                SensorReading(variable="soil_moisture_vwc", value=0.32),
            ],
        )
        return _bundle(
            plot_id="fullstack",
            run_id="run_fullstack",
            sentinel2_packages=[s2],
            sensor_context_package=sensor,
        )

    def test_evidence_count(self):
        engine = Layer1FusionEngine()
        pkg = engine.fuse(self._build())
        assert len(pkg.evidence_items) >= 5

    def test_vegetation_context_populated(self):
        engine = Layer1FusionEngine()
        pkg = engine.fuse(self._build())
        assert len(pkg.fused_features.vegetation_context) > 0

    def test_all_13_prohibitions_pass(self):
        engine = Layer1FusionEngine()
        pkg = engine.fuse(self._build())
        for name, passed in pkg.diagnostics.hard_prohibition_results.items():
            assert passed, f"Prohibition {name} failed"

    def test_downstream_payloads_built(self):
        engine = Layer1FusionEngine()
        pkg = engine.fuse(self._build())
        assert pkg.layer2_input is not None
        assert isinstance(pkg.layer10_payload, dict)
        assert "zone_overlays" in pkg.layer10_payload

    def test_spatial_index_has_zones(self):
        engine = Layer1FusionEngine()
        pkg = engine.fuse(self._build())
        assert len(pkg.spatial_index.zones) >= 2

    def test_raster_refs_preserved(self):
        engine = Layer1FusionEngine()
        pkg = engine.fuse(self._build())
        assert len(pkg.spatial_index.raster_refs) >= 1

    def test_determinism(self):
        engine = Layer1FusionEngine()
        h1 = engine.fuse(self._build()).content_hash()
        h2 = engine.fuse(self._build()).content_hash()
        assert h1 == h2

    def test_performance(self):
        engine = Layer1FusionEngine()
        t0 = time.perf_counter()
        engine.fuse(self._build())
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.5, f"Full-stack: {elapsed:.3f}s"


# ── Scenario 2: Sensor-Only ─────────────────────────────────────────────────

class TestScenarioSensorOnly:
    """Sensor-only: no satellite, degraded health, many gaps."""

    def _build(self):
        return _bundle(
            plot_id="sensor_only",
            run_id="run_sensor",
            sensor_context_package=SensorPackage(),
        )

    def test_gaps_detected(self):
        engine = Layer1FusionEngine()
        pkg = engine.fuse(self._build())
        gap_types = {g.gap_type for g in pkg.gaps}
        assert "NO_RECENT_SENTINEL2" in gap_types
        assert "NO_RECENT_SENTINEL1" in gap_types

    def test_no_fake_ndvi(self):
        engine = Layer1FusionEngine()
        pkg = engine.fuse(self._build())
        ndvi_features = [f for f in pkg.fused_features.vegetation_context if f.name == "ndvi"]
        assert len(ndvi_features) == 0, "NDVI should not exist without S2"

    def test_health_degraded(self):
        engine = Layer1FusionEngine()
        pkg = engine.fuse(self._build())
        assert pkg.diagnostics.data_health.source_completeness < 0.5

    def test_performance(self):
        engine = Layer1FusionEngine()
        t0 = time.perf_counter()
        engine.fuse(self._build())
        assert time.perf_counter() - t0 < 0.3


# ── Scenario 3: Satellite-Only ──────────────────────────────────────────────

class TestScenarioSatelliteOnly:
    """Satellite-only: S2 data, no ground sensors."""

    def _build(self):
        return _bundle(
            plot_id="sat_only",
            run_id="run_sat",
            sentinel2_packages=[S2Package()],
        )

    def test_sensor_gap_detected(self):
        engine = Layer1FusionEngine()
        pkg = engine.fuse(self._build())
        gap_types = {g.gap_type for g in pkg.gaps}
        assert "NO_SENSOR_FOR_ROOT_ZONE" in gap_types

    def test_vegetation_from_s2(self):
        engine = Layer1FusionEngine()
        pkg = engine.fuse(self._build())
        assert len(pkg.fused_features.vegetation_context) > 0

    def test_prohibitions_pass(self):
        engine = Layer1FusionEngine()
        pkg = engine.fuse(self._build())
        for name, passed in pkg.diagnostics.hard_prohibition_results.items():
            assert passed, f"Prohibition {name} failed"

    def test_performance(self):
        engine = Layer1FusionEngine()
        t0 = time.perf_counter()
        engine.fuse(self._build())
        assert time.perf_counter() - t0 < 0.3


# ── Scenario 4: Multi-Scene S2 ──────────────────────────────────────────────

class TestScenarioMultiScene:
    """Multiple S2 scenes + sensor: fusion with temporal depth."""

    def _build(self):
        s2_recent = S2Package(
            metadata=S2Meta(scene_id="S2A_recent",
                           acquisition_datetime=_TS - timedelta(days=2)),
            plot_summary=S2PlotSummary(ndvi_mean=0.70),
        )
        s2_old = S2Package(
            metadata=S2Meta(scene_id="S2A_old",
                           acquisition_datetime=_TS - timedelta(days=8)),
            plot_summary=S2PlotSummary(ndvi_mean=0.55),
        )
        return _bundle(
            plot_id="multi_scene",
            run_id="run_multi",
            sentinel2_packages=[s2_recent, s2_old],
            sensor_context_package=SensorPackage(),
        )

    def test_evidence_from_both_scenes(self):
        engine = Layer1FusionEngine()
        pkg = engine.fuse(self._build())
        # Should have evidence from both S2 packages
        s2_ids = [e.source_id for e in pkg.evidence_items if e.source_family == "sentinel2"]
        assert len(set(s2_ids)) >= 2

    def test_determinism(self):
        engine = Layer1FusionEngine()
        h1 = engine.fuse(self._build()).content_hash()
        h2 = engine.fuse(self._build()).content_hash()
        assert h1 == h2


# ── Scenario 5: Stale Data ──────────────────────────────────────────────────

class TestScenarioStaleData:
    """All data > 10 days old: low freshness, degraded health."""

    def _build(self):
        stale_dt = _TS - timedelta(days=14)
        s2 = S2Package(
            metadata=S2Meta(scene_id="S2A_stale",
                           acquisition_datetime=stale_dt),
        )
        sensor = SensorPackage(
            readings=[SensorReading(timestamp=stale_dt)],
            window_start=stale_dt - timedelta(hours=6),
            window_end=stale_dt,
        )
        return _bundle(
            plot_id="stale_field",
            run_id="run_stale",
            sentinel2_packages=[s2],
            sensor_context_package=sensor,
        )

    def test_low_freshness(self):
        engine = Layer1FusionEngine()
        pkg = engine.fuse(self._build())
        assert pkg.diagnostics.data_health.freshness < 0.7

    def test_health_degraded_or_worse(self):
        engine = Layer1FusionEngine()
        pkg = engine.fuse(self._build())
        assert pkg.diagnostics.data_health.status in ("degraded", "unusable")

    def test_performance(self):
        engine = Layer1FusionEngine()
        t0 = time.perf_counter()
        engine.fuse(self._build())
        assert time.perf_counter() - t0 < 0.3


# ── Scenario 6: Empty Plot ──────────────────────────────────────────────────

class TestScenarioEmptyPlot:
    """No sources at all: maximum gaps, minimal health."""

    def _build(self):
        return _bundle(
            plot_id="empty_plot",
            run_id="run_empty",
        )

    def test_runs_without_crash(self):
        engine = Layer1FusionEngine()
        pkg = engine.fuse(self._build())
        assert pkg.plot_id == "empty_plot"

    def test_many_gaps(self):
        engine = Layer1FusionEngine()
        pkg = engine.fuse(self._build())
        assert len(pkg.gaps) >= 5

    def test_no_fake_features(self):
        engine = Layer1FusionEngine()
        pkg = engine.fuse(self._build())
        assert len(pkg.fused_features.water_context) == 0
        assert len(pkg.fused_features.vegetation_context) == 0

    def test_performance(self):
        engine = Layer1FusionEngine()
        t0 = time.perf_counter()
        engine.fuse(self._build())
        assert time.perf_counter() - t0 < 0.2


# ── Scenario 7: Zone-Aware Field ────────────────────────────────────────────

class TestScenarioZoneAware:
    """S2 with multiple zones, point sensors. Tests zone spatial index."""

    def _build(self):
        s2 = S2Package(
            zone_summaries=[
                S2ZoneSummary(zone_id="z_north", ndvi_mean=0.8),
                S2ZoneSummary(zone_id="z_south", ndvi_mean=0.4),
            ]
        )
        sensor = SensorPackage(
            readings=[SensorReading(variable="soil_moisture_vwc", value=0.25)]
        )
        return _bundle(
            plot_id="zone_aware",
            run_id="run_zone",
            sentinel2_packages=[s2],
            sensor_context_package=sensor,
        )

    def test_spatial_index_zones_and_points(self):
        engine = Layer1FusionEngine()
        pkg = engine.fuse(self._build())
        zone_ids = {z.zone_id for z in pkg.spatial_index.zones}
        assert "z_north" in zone_ids
        assert "z_south" in zone_ids
        assert len(pkg.spatial_index.points) >= 1

    def test_zone_features_fused_separately(self):
        engine = Layer1FusionEngine()
        pkg = engine.fuse(self._build())
        veg = pkg.fused_features.vegetation_context
        # Should have plot level + 2 zones
        ndvi_features = [f for f in veg if f.name == "ndvi"]
        assert len(ndvi_features) == 3


# ── Scenario 8: Edge-Contaminated Field ─────────────────────────────────────

class TestScenarioEdgeContaminated:
    """Field with edge contamination evidence. Tests edge spatial index."""

    def _build(self):
        return _bundle(
            plot_id="edge_field",
            run_id="run_edge",
            layer0_state_package={
                "edge_contamination": [
                    {"edge_id": "edge_east", "contamination_score": 0.85},
                    {"edge_id": "edge_west", "contamination_score": 0.12},
                ]
            }
        )

    def test_edge_regions_indexed(self):
        engine = Layer1FusionEngine()
        pkg = engine.fuse(self._build())
        edge_ids = {e.edge_id for e in pkg.spatial_index.edge_regions}
        assert "edge_east" in edge_ids
        assert "edge_west" in edge_ids

    def test_contamination_scores_propagated(self):
        engine = Layer1FusionEngine()
        pkg = engine.fuse(self._build())
        east = [e for e in pkg.spatial_index.edge_regions if e.edge_id == "edge_east"][0]
        assert east.contamination_score == 0.85


# ── Scenario 9: Forecast-Heavy Field ────────────────────────────────────────

class TestScenarioForecastHeavy:
    """5-day forecast, minimal current observations."""

    def _build(self):
        fc = ForecastPackage(
            forecast_process_forcing=[
                ForecastDay(date=f"day_{i}", precipitation_mm=2.0 * i)
                for i in range(5)
            ]
        )
        return _bundle(
            plot_id="forecast_field",
            run_id="run_forecast",
            weather_forecast_package=fc,
        )

    def test_forecast_features_have_forecast_scope(self):
        engine = Layer1FusionEngine()
        pkg = engine.fuse(self._build())
        fc_features = [f for f in pkg.fused_features.water_context if f.name == "forecast_precip"]
        assert len(fc_features) == 5
        for f in fc_features:
            assert f.temporal_scope.startswith("forecast_day_")


# ── Scenario 10: WSR-Enriched Field ─────────────────────────────────────────

class TestScenarioWSREnriched:
    """Layer 0 state package with zone weakness scores."""

    def _build(self):
        s2 = S2Package(
            zone_summaries=[
                S2ZoneSummary(zone_id="z1", ndvi_mean=0.6),
                S2ZoneSummary(zone_id="z2", ndvi_mean=0.4),
            ]
        )
        return _bundle(
            plot_id="wsr_field",
            run_id="run_wsr",
            sentinel2_packages=[s2],
            layer0_state_package={
                "zone_summaries": [
                    {"zone_id": "z1", "label": "healthy", "area_fraction": 0.7},
                    {"zone_id": "z2", "label": "weak", "area_fraction": 0.3},
                ]
            }
        )

    def test_wsr_metadata_propagated(self):
        engine = Layer1FusionEngine()
        pkg = engine.fuse(self._build())
        z1 = [z for z in pkg.spatial_index.zones if z.zone_id == "z1"][0]
        z2 = [z for z in pkg.spatial_index.zones if z.zone_id == "z2"][0]
        assert z1.label == "healthy"
        assert z1.area_fraction == 0.7
        assert z2.label == "weak"

    def test_layer10_zone_confidence(self):
        engine = Layer1FusionEngine()
        pkg = engine.fuse(self._build())
        # L10 payload should have per_zone confidence
        per_zone = pkg.layer10_payload.get("confidence_data", {}).get("per_zone", {})
        assert "z1" in per_zone
        assert "z2" in per_zone
        assert per_zone["z1"] > 0.0


# ── Cross-Scenario Invariants ───────────────────────────────────────────────

class TestCrossScenarioInvariants:
    """Invariants that must hold across ALL scenarios."""

    @pytest.fixture(params=[
        "fullstack", "sensor_only", "sat_only", "multi_scene",
        "stale_field", "empty_plot", "zone_aware", "edge_contam",
        "forecast_heavy", "wsr_enriched"
    ])
    def scenario_pkg(self, request):
        builders = {
            "fullstack": TestScenarioFullStack()._build,
            "sensor_only": TestScenarioSensorOnly()._build,
            "sat_only": TestScenarioSatelliteOnly()._build,
            "multi_scene": TestScenarioMultiScene()._build,
            "stale_field": TestScenarioStaleData()._build,
            "empty_plot": TestScenarioEmptyPlot()._build,
            "zone_aware": TestScenarioZoneAware()._build,
            "edge_contam": TestScenarioEdgeContaminated()._build,
            "forecast_heavy": TestScenarioForecastHeavy()._build,
            "wsr_enriched": TestScenarioWSREnriched()._build,
        }
        engine = Layer1FusionEngine()
        return request.param, engine.fuse(builders[request.param]())

    def test_no_forbidden_terms(self, scenario_pkg):
        name, pkg = scenario_pkg
        all_text = " ".join(
            f"{f.name} {str(f.value)}"
            for group in [
                pkg.fused_features.water_context,
                pkg.fused_features.vegetation_context,
                pkg.fused_features.stress_evidence_context,
                pkg.fused_features.operational_context,
            ]
            for f in group
        ).lower()
        from layer1_fusion.schemas import FORBIDDEN_DIAGNOSIS_TERMS
        for term in FORBIDDEN_DIAGNOSIS_TERMS:
            assert term not in all_text, f"{name}: forbidden term '{term}' found"

    def test_provenance_complete(self, scenario_pkg):
        name, pkg = scenario_pkg
        assert pkg.provenance.run_id, f"{name}: missing run_id"
        assert pkg.provenance.engine_version, f"{name}: missing engine_version"

    def test_data_health_bounded(self, scenario_pkg):
        name, pkg = scenario_pkg
        dh = pkg.diagnostics.data_health
        assert 0.0 <= dh.overall <= 1.0, f"{name}: health {dh.overall} out of bounds"
        assert dh.status in ("ok", "degraded", "unusable")


# ── Calibration Report ──────────────────────────────────────────────────────

class TestCalibrationReport:
    """Print a calibration summary table for all scenarios."""

    def test_calibration_summary(self, capsys):
        builders = [
            ("Full-stack", TestScenarioFullStack()._build),
            ("Sensor-only", TestScenarioSensorOnly()._build),
            ("Satellite-only", TestScenarioSatelliteOnly()._build),
            ("Multi-scene", TestScenarioMultiScene()._build),
            ("Stale data", TestScenarioStaleData()._build),
            ("Empty plot", TestScenarioEmptyPlot()._build),
            ("Zone-aware", TestScenarioZoneAware()._build),
            ("Edge-contaminated", TestScenarioEdgeContaminated()._build),
            ("Forecast-heavy", TestScenarioForecastHeavy()._build),
            ("WSR-enriched", TestScenarioWSREnriched()._build),
        ]

        engine = Layer1FusionEngine()
        results = []

        for name, build in builders:
            t0 = time.perf_counter()
            pkg = engine.fuse(build())
            elapsed = time.perf_counter() - t0

            n_pass = sum(1 for v in pkg.diagnostics.hard_prohibition_results.values() if v)
            n_total = len(pkg.diagnostics.hard_prohibition_results)

            results.append({
                "name": name,
                "evidence": len(pkg.evidence_items),
                "fused": sum(len(g) for g in [
                    pkg.fused_features.water_context,
                    pkg.fused_features.vegetation_context,
                    pkg.fused_features.phenology_context,
                    pkg.fused_features.stress_evidence_context,
                    pkg.fused_features.soil_site_context,
                    pkg.fused_features.operational_context,
                    pkg.fused_features.data_quality_context,
                ]),
                "conflicts": len(pkg.conflicts),
                "gaps": len(pkg.gaps),
                "health": pkg.diagnostics.data_health.overall,
                "status": pkg.diagnostics.data_health.status,
                "prohib": f"{n_pass}/{n_total}",
                "hash": pkg.content_hash()[:12],
                "ms": round(elapsed * 1000, 1),
            })

        print("\n" + "=" * 115)
        print("LAYER 1 FUSION CALIBRATION REPORT")
        print("=" * 115)
        print(f"{'Scenario':<18} {'Evid':>5} {'Fused':>5} {'Conf':>5} "
              f"{'Gaps':>5} {'Health':>6} {'Status':<10} "
              f"{'Prohib':<7} {'Hash':<14} {'ms':>6}")
        print("-" * 115)
        for r in results:
            print(f"{r['name']:<18} {r['evidence']:>5} {r['fused']:>5} "
                  f"{r['conflicts']:>5} {r['gaps']:>5} {r['health']:>6.3f} "
                  f"{r['status']:<10} {r['prohib']:<7} {r['hash']:<14} "
                  f"{r['ms']:>6.1f}")
        print("=" * 115)

        for r in results:
            assert r["ms"] < 1000, f"{r['name']} took {r['ms']}ms"
