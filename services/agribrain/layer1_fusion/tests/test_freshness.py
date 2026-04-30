"""
Layer 1 — Freshness Module Unit Tests.

Tests source-specific decay curves, edge cases, static prior bypass,
HISTORICAL/STALE flag handling, and batch processing.
"""

import pytest
from datetime import datetime, timedelta, timezone

from layer1_fusion.freshness import (
    compute_freshness,
    compute_freshness_batch,
    _FRESHNESS_CURVES,
)
from layer1_fusion.schemas import EvidenceItem


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_evidence(source_family="sensor", variable="moisture",
                   observed_at=None, observation_type="measurement",
                   flags=None):
    """Build a minimal EvidenceItem for freshness testing."""
    return EvidenceItem(
        evidence_id="ev_test",
        plot_id="plot_1",
        variable=variable,
        value=0.5,
        unit="fraction",
        source_family=source_family,
        source_id=f"{source_family}_1",
        observation_type=observation_type,
        spatial_scope="plot",
        observed_at=observed_at,
        provenance_ref=f"{source_family}_prov",
        flags=flags or [],
    )


RUN_TS = datetime(2026, 4, 15, 12, 0, 0, tzinfo=timezone.utc)


# ── Test: Sensor Decay Curve ────────────────────────────────────────────────

class TestSensorFreshness:
    """Sensor freshness: <6h=0.95, <24h=0.80, <72h=0.60, <168h=0.30."""

    def test_fresh_sensor_1h(self):
        e = _make_evidence("sensor", observed_at=RUN_TS - timedelta(hours=1))
        assert compute_freshness(e, RUN_TS) == 0.95

    def test_sensor_12h(self):
        e = _make_evidence("sensor", observed_at=RUN_TS - timedelta(hours=12))
        assert compute_freshness(e, RUN_TS) == 0.80

    def test_sensor_48h(self):
        e = _make_evidence("sensor", observed_at=RUN_TS - timedelta(hours=48))
        assert compute_freshness(e, RUN_TS) == 0.60

    def test_sensor_5d(self):
        e = _make_evidence("sensor", observed_at=RUN_TS - timedelta(days=5))
        assert compute_freshness(e, RUN_TS) == 0.30

    def test_sensor_30d_very_stale(self):
        e = _make_evidence("sensor", observed_at=RUN_TS - timedelta(days=30))
        score = compute_freshness(e, RUN_TS)
        assert score <= 0.10
        assert score >= 0.05


# ── Test: Sentinel-2 Decay Curve ────────────────────────────────────────────

class TestSentinel2Freshness:
    """S2: <5d=0.85, <10d=0.65, <20d=0.40."""

    def test_s2_3d(self):
        e = _make_evidence("sentinel2", observed_at=RUN_TS - timedelta(days=3))
        assert compute_freshness(e, RUN_TS) == 0.85

    def test_s2_7d(self):
        e = _make_evidence("sentinel2", observed_at=RUN_TS - timedelta(days=7))
        assert compute_freshness(e, RUN_TS) == 0.65

    def test_s2_15d(self):
        e = _make_evidence("sentinel2", observed_at=RUN_TS - timedelta(days=15))
        assert compute_freshness(e, RUN_TS) == 0.40

    def test_s2_25d(self):
        e = _make_evidence("sentinel2", observed_at=RUN_TS - timedelta(days=25))
        assert compute_freshness(e, RUN_TS) == 0.20

    def test_s2_60d_very_stale(self):
        e = _make_evidence("sentinel2", observed_at=RUN_TS - timedelta(days=60))
        score = compute_freshness(e, RUN_TS)
        assert score <= 0.20
        assert score >= 0.05


# ── Test: Sentinel-1 Decay ──────────────────────────────────────────────────

class TestSentinel1Freshness:
    def test_s1_4d(self):
        e = _make_evidence("sentinel1", observed_at=RUN_TS - timedelta(days=4))
        assert compute_freshness(e, RUN_TS) == 0.80

    def test_s1_10d(self):
        e = _make_evidence("sentinel1", observed_at=RUN_TS - timedelta(days=10))
        assert compute_freshness(e, RUN_TS) == 0.60


# ── Test: Weather Forecast Decay ────────────────────────────────────────────

class TestForecastFreshness:
    def test_forecast_day0(self):
        e = _make_evidence("weather_forecast", observation_type="forecast",
                           observed_at=RUN_TS - timedelta(hours=12))
        assert compute_freshness(e, RUN_TS) == 0.80

    def test_forecast_day2(self):
        e = _make_evidence("weather_forecast", observation_type="forecast",
                           observed_at=RUN_TS - timedelta(hours=60))
        assert compute_freshness(e, RUN_TS) == 0.50

    def test_forecast_day5(self):
        e = _make_evidence("weather_forecast", observation_type="forecast",
                           observed_at=RUN_TS - timedelta(hours=110))
        assert compute_freshness(e, RUN_TS) == 0.25


# ── Test: Edge Cases ────────────────────────────────────────────────────────

class TestFreshnessEdgeCases:
    def test_age_zero(self):
        """Observation at exactly run_timestamp."""
        e = _make_evidence("sensor", observed_at=RUN_TS)
        assert compute_freshness(e, RUN_TS) == 0.95

    def test_future_observation(self):
        """Observation in the future (age < 0) → treated as age=0."""
        e = _make_evidence("sensor", observed_at=RUN_TS + timedelta(hours=1))
        assert compute_freshness(e, RUN_TS) == 0.95

    def test_missing_observed_at(self):
        """No observed_at → moderate default."""
        e = _make_evidence("sensor", observed_at=None)
        assert compute_freshness(e, RUN_TS) == 0.50

    def test_static_prior_never_decays(self):
        """Static priors (geo_context) always return 1.0."""
        e = _make_evidence("geo_context", observation_type="static_prior",
                           observed_at=RUN_TS - timedelta(days=365))
        assert compute_freshness(e, RUN_TS) == 1.0

    def test_historical_flag_always_stale(self):
        """HISTORICAL flag forces freshness to 0.10."""
        e = _make_evidence("sensor", observed_at=RUN_TS - timedelta(hours=1),
                           flags=["HISTORICAL"])
        assert compute_freshness(e, RUN_TS) == 0.10

    def test_stale_flag_always_stale(self):
        """STALE flag forces freshness to 0.10."""
        e = _make_evidence("sentinel2", observed_at=RUN_TS - timedelta(hours=1),
                           flags=["STALE"])
        assert compute_freshness(e, RUN_TS) == 0.10

    def test_geo_context_no_curve_returns_1(self):
        """geo_context has empty curve → always 1.0."""
        e = _make_evidence("geo_context", observation_type="measurement",
                           observed_at=RUN_TS - timedelta(days=100))
        assert compute_freshness(e, RUN_TS) == 1.0

    def test_history_always_low(self):
        """History source → always 0.30 (from curve)."""
        e = _make_evidence("history", observed_at=RUN_TS)
        assert compute_freshness(e, RUN_TS) == 0.30


# ── Test: Batch Processing ──────────────────────────────────────────────────

class TestFreshnessBatch:
    def test_batch_updates_all_items(self):
        items = [
            _make_evidence("sensor", observed_at=RUN_TS - timedelta(hours=1)),
            _make_evidence("sentinel2", observed_at=RUN_TS - timedelta(days=3)),
            _make_evidence("geo_context", observation_type="static_prior"),
        ]
        result = compute_freshness_batch(items, RUN_TS)
        assert result[0].freshness_score == 0.95  # sensor 1h
        assert result[1].freshness_score == 0.85  # S2 3d
        assert result[2].freshness_score == 1.0   # static prior

    def test_batch_empty_list(self):
        result = compute_freshness_batch([], RUN_TS)
        assert result == []

    def test_batch_mutates_in_place(self):
        items = [_make_evidence("sensor", observed_at=RUN_TS)]
        original = items[0]
        compute_freshness_batch(items, RUN_TS)
        assert original.freshness_score == 0.95
        assert items[0] is original  # same object, mutated
