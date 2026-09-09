"""Unit tests for Layer 1 Freshness Scoring."""

from datetime import datetime, timezone, timedelta
import pytest

from services.agribrain.layer1_fusion.schemas import EvidenceItem
from services.agribrain.layer1_fusion.freshness import (
    compute_freshness,
    compute_freshness_batch,
)


def test_sensor_freshness_decay():
    """Verify sensor freshness decays appropriately across time windows."""
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)

    # 3 hours old (sensor < 6h -> 0.95)
    item_fresh = EvidenceItem(
        evidence_id="ev_s1",
        plot_id="plot_test",
        variable="soil_moisture_vwc",
        value=0.25,
        source_family="sensor",
        source_id="probe_01",
        observation_type="measurement",
        spatial_scope="point",
        observed_at=now - timedelta(hours=3),
    )
    assert compute_freshness(item_fresh, now) == 0.95

    # 18 hours old (sensor < 24h -> 0.80)
    item_day = EvidenceItem(
        evidence_id="ev_s2",
        plot_id="plot_test",
        variable="soil_moisture_vwc",
        value=0.24,
        source_family="sensor",
        source_id="probe_01",
        observation_type="measurement",
        spatial_scope="point",
        observed_at=now - timedelta(hours=18),
    )
    assert compute_freshness(item_day, now) == 0.80

    # 10 days old (sensor > 168h -> 0.10)
    item_old = EvidenceItem(
        evidence_id="ev_s3",
        plot_id="plot_test",
        variable="soil_moisture_vwc",
        value=0.20,
        source_family="sensor",
        source_id="probe_01",
        observation_type="measurement",
        spatial_scope="point",
        observed_at=now - timedelta(days=10),
    )
    assert compute_freshness(item_old, now) <= 0.10


def test_sentinel2_freshness():
    """Verify Sentinel-2 freshness allows multi-day satellite revisit tolerance."""
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)

    # 3 days old (S2 < 5d / 120h -> 0.85)
    item_recent = EvidenceItem(
        evidence_id="ev_s2_1",
        plot_id="plot_test",
        variable="ndvi",
        value=0.68,
        source_family="sentinel2",
        source_id="s2_l2a_20260707",
        observation_type="derived_feature",
        spatial_scope="plot",
        observed_at=now - timedelta(days=3),
    )
    assert compute_freshness(item_recent, now) == 0.85

    # 8 days old (S2 < 10d / 240h -> 0.65)
    item_revisit = EvidenceItem(
        evidence_id="ev_s2_2",
        plot_id="plot_test",
        variable="ndvi",
        value=0.66,
        source_family="sentinel2",
        source_id="s2_l2a_20260702",
        observation_type="derived_feature",
        spatial_scope="plot",
        observed_at=now - timedelta(days=8),
    )
    assert compute_freshness(item_revisit, now) == 0.65


def test_static_prior_no_decay():
    """Verify static priors (like SoilGrids / DEM) never decay."""
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    item_static = EvidenceItem(
        evidence_id="ev_geo",
        plot_id="plot_test",
        variable="elevation_m",
        value=350.0,
        source_family="geo_context",
        source_id="dem_copernicus_30m",
        observation_type="static_prior",
        spatial_scope="plot",
        observed_at=now - timedelta(days=365),
    )
    assert compute_freshness(item_static, now) == 1.0


def test_stale_flag_forces_low_freshness():
    """Verify explicitly flagged STALE items receive immediate low freshness score."""
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    item_stale = EvidenceItem(
        evidence_id="ev_stale",
        plot_id="plot_test",
        variable="soil_moisture_vwc",
        value=0.30,
        source_family="sensor",
        source_id="probe_01",
        observation_type="measurement",
        spatial_scope="point",
        observed_at=now - timedelta(hours=1),
        flags=["STALE"],
    )
    assert compute_freshness(item_stale, now) == 0.10


def test_compute_freshness_batch():
    """Verify compute_freshness_batch updates freshness_score in-place on all items."""
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    items = [
        EvidenceItem(
            evidence_id=f"ev_{i}",
            plot_id="p",
            variable="ndvi",
            value=0.5,
            source_family="sentinel2",
            source_id=f"s2_scene_{i}",
            observation_type="derived_feature",
            spatial_scope="plot",
            observed_at=now - timedelta(days=i),
        )
        for i in range(1, 5)
    ]
    updated = compute_freshness_batch(items, now)
    assert len(updated) == 4
    for item in updated:
        assert item.freshness_score is not None
        assert 0.0 < item.freshness_score <= 1.0
