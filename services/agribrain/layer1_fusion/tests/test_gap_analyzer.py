"""
Layer 1 — Gap Analyzer Unit Tests.

Tests all 11 gap detection rules, variable-specific gaps,
source-present-but-variable-missing cases, and empty evidence.
"""

import pytest
from layer1_fusion.gap_analyzer import detect_gaps, _GAP_RULES
from layer1_fusion.schemas import EvidenceItem, GAP_TYPES


# ── Helpers ──────────────────────────────────────────────────────────────────

def _ev(source_family, variable="generic", **kw):
    defaults = dict(
        evidence_id=f"ev_{source_family}_{variable}",
        plot_id="plot_1",
        variable=variable,
        value=0.5,
        unit="fraction",
        source_family=source_family,
        source_id=f"{source_family}_1",
        observation_type="measurement",
        spatial_scope="plot",
        provenance_ref="prov",
    )
    defaults.update(kw)
    return EvidenceItem(**defaults)


# ── Test: Empty Evidence ────────────────────────────────────────────────────

class TestEmptyEvidence:
    def test_all_gaps_detected_on_empty(self):
        """No evidence at all → all 11 gap rules should fire."""
        gaps = detect_gaps([])
        assert len(gaps) == len(_GAP_RULES)

    def test_gap_types_are_canonical(self):
        gaps = detect_gaps([])
        for g in gaps:
            assert g.gap_type in GAP_TYPES or g.gap_type.startswith("NO_"), (
                f"Unknown gap type: {g.gap_type}"
            )


# ── Test: Source-Level Gaps ─────────────────────────────────────────────────

class TestSourceLevelGaps:
    def test_no_s2_gap_when_s2_missing(self):
        evidence = [_ev("sensor", "moisture")]
        gaps = detect_gaps(evidence)
        types = {g.gap_type for g in gaps}
        assert "NO_RECENT_SENTINEL2" in types

    def test_no_s2_gap_when_s2_present(self):
        evidence = [_ev("sentinel2", "ndvi")]
        gaps = detect_gaps(evidence)
        types = {g.gap_type for g in gaps}
        assert "NO_RECENT_SENTINEL2" not in types

    def test_no_s1_gap_when_s1_present(self):
        evidence = [_ev("sentinel1", "sar_wetness")]
        gaps = detect_gaps(evidence)
        types = {g.gap_type for g in gaps}
        assert "NO_RECENT_SENTINEL1" not in types

    def test_no_forecast_gap_when_forecast_present(self):
        evidence = [_ev("weather_forecast", "forecast_precip",
                        observation_type="forecast")]
        gaps = detect_gaps(evidence)
        types = {g.gap_type for g in gaps}
        assert "NO_VALID_WEATHER_FORECAST" not in types

    def test_no_geo_gap_when_geo_present(self):
        evidence = [_ev("geo_context", "elevation",
                        observation_type="static_prior", diagnostic_only=True)]
        gaps = detect_gaps(evidence)
        types = {g.gap_type for g in gaps}
        assert "NO_GEO_CONTEXT" not in types


# ── Test: Variable-Specific Gaps ────────────────────────────────────────────

class TestVariableSpecificGaps:
    def test_sensor_present_but_no_moisture(self):
        """Sensor is present but no moisture variable → NO_SENSOR_FOR_ROOT_ZONE."""
        evidence = [_ev("sensor", "temperature")]
        gaps = detect_gaps(evidence)
        types = {g.gap_type for g in gaps}
        assert "NO_SENSOR_FOR_ROOT_ZONE" in types

    def test_sensor_with_moisture_no_gap(self):
        evidence = [_ev("sensor", "soil_moisture_vwc")]
        gaps = detect_gaps(evidence)
        types = {g.gap_type for g in gaps}
        assert "NO_SENSOR_FOR_ROOT_ZONE" not in types

    def test_sensor_present_but_no_rain(self):
        evidence = [_ev("sensor", "moisture")]
        gaps = detect_gaps(evidence)
        types = {g.gap_type for g in gaps}
        assert "NO_RAIN_GAUGE" in types

    def test_sensor_with_rain_no_gap(self):
        evidence = [_ev("sensor", "rain_mm")]
        gaps = detect_gaps(evidence)
        types = {g.gap_type for g in gaps}
        assert "NO_RAIN_GAUGE" not in types

    def test_no_planting_declared(self):
        evidence = [_ev("user_event", "irrigation_event")]
        gaps = detect_gaps(evidence)
        types = {g.gap_type for g in gaps}
        assert "NO_CROP_STAGE_DECLARED" in types

    def test_planting_declared_no_gap(self):
        evidence = [_ev("user_event", "planting_date")]
        gaps = detect_gaps(evidence)
        types = {g.gap_type for g in gaps}
        assert "NO_CROP_STAGE_DECLARED" not in types

    def test_geo_present_but_no_landcover(self):
        evidence = [_ev("geo_context", "elevation",
                        observation_type="static_prior", diagnostic_only=True)]
        gaps = detect_gaps(evidence)
        types = {g.gap_type for g in gaps}
        assert "NO_LANDCOVER_VALIDITY" in types

    def test_geo_with_landcover_no_gap(self):
        evidence = [_ev("geo_context", "landcover_class",
                        observation_type="static_prior", diagnostic_only=True)]
        gaps = detect_gaps(evidence)
        types = {g.gap_type for g in gaps}
        assert "NO_LANDCOVER_VALIDITY" not in types

    def test_no_wapor_gap(self):
        evidence = [_ev("geo_context", "elevation",
                        observation_type="static_prior", diagnostic_only=True)]
        gaps = detect_gaps(evidence)
        types = {g.gap_type for g in gaps}
        assert "NO_WAPOR_CONTEXT" in types

    def test_wapor_present_no_gap(self):
        evidence = [_ev("geo_context", "wapor_et",
                        observation_type="static_prior", diagnostic_only=True)]
        gaps = detect_gaps(evidence)
        types = {g.gap_type for g in gaps}
        assert "NO_WAPOR_CONTEXT" not in types


# ── Test: Gap Metadata ──────────────────────────────────────────────────────

class TestGapMetadata:
    def test_gaps_have_ids(self):
        gaps = detect_gaps([])
        for g in gaps:
            assert g.gap_id.startswith("gap_")

    def test_gaps_have_severity(self):
        gaps = detect_gaps([])
        for g in gaps:
            assert g.severity in ("info", "warning", "blocking")

    def test_gaps_have_affected_features(self):
        gaps = detect_gaps([])
        for g in gaps:
            assert len(g.affected_features) > 0

    def test_gaps_have_suggested_action(self):
        gaps = detect_gaps([])
        for g in gaps:
            assert len(g.suggested_action) > 0


# ── Test: Full Coverage ─────────────────────────────────────────────────────

class TestFullCoverageNoGaps:
    def test_all_sources_and_variables_present(self):
        """Full evidence set should produce minimal gaps."""
        evidence = [
            _ev("sentinel2", "ndvi"),
            _ev("sentinel1", "sar_wetness"),
            _ev("sensor", "soil_moisture_vwc"),
            _ev("sensor", "rain_mm"),
            _ev("sensor", "irrigation_flow"),
            _ev("environment", "precipitation"),
            _ev("weather_forecast", "forecast_precip", observation_type="forecast"),
            _ev("geo_context", "landcover_class",
                observation_type="static_prior", diagnostic_only=True),
            _ev("geo_context", "wapor_et",
                observation_type="static_prior", diagnostic_only=True),
            _ev("user_event", "planting_date"),
            _ev("user_event", "irrigation_event"),
            _ev("perception", "photo_greenness"),
            _ev("history", "historical_ndvi", observation_type="forecast"),
        ]
        gaps = detect_gaps(evidence)
        assert len(gaps) == 0, f"Expected 0 gaps, got: {[g.gap_type for g in gaps]}"
