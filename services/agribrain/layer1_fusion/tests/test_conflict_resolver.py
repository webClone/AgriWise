"""Unit tests for Layer 1 Conflict Resolver."""

from datetime import datetime, timezone
import pytest

from services.agribrain.layer1_fusion.schemas import EvidenceItem, EvidenceConflict
from services.agribrain.layer1_fusion.conflict_resolver import (
    detect_conflicts,
    detect_conflicts_with_diagnostics,
    _credibility,
    _bayesian_impact,
    _phenology_threshold_factor,
)


def test_sensor_vs_sar_moisture_conflict():
    """Verify SENSOR_VS_SAR_MOISTURE_CONFLICT is detected when sensor and SAR wetness disagree."""
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    # Sensor reports dry soil (0.10), SAR reports saturated surface wetness (0.65)
    e_sensor = EvidenceItem(
        evidence_id="ev_sens",
        plot_id="plot_01",
        variable="soil_moisture_vwc",
        value=0.10,
        source_family="sensor",
        source_id="probe_1",
        observation_type="measurement",
        spatial_scope="plot",
        observed_at=now,
        confidence=0.85,
        reliability=0.90,
        freshness_score=0.95,
    )
    e_sar = EvidenceItem(
        evidence_id="ev_sar",
        plot_id="plot_01",
        variable="surface_wetness_index",
        value=0.65,
        source_family="sentinel1",
        source_id="s1_grd_1",
        observation_type="derived_feature",
        spatial_scope="plot",
        observed_at=now,
        confidence=0.80,
        reliability=0.85,
        freshness_score=0.90,
    )

    conflicts, diags = detect_conflicts_with_diagnostics([e_sensor, e_sar])
    assert len(conflicts) > 0
    c_types = [c.conflict_type for c in conflicts]
    assert "SENSOR_VS_SAR_MOISTURE_CONFLICT" in c_types

    # Zero conflict suppression invariant
    assert diags.suppressed_conflicts == 0
    assert diags.candidate_conflicts == diags.emitted_conflicts


def test_s1_wetness_without_rain_or_irrigation():
    """Verify SAR wetness spike without accompanying rain or irrigation flags conflict."""
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    e_sar_wet = EvidenceItem(
        evidence_id="ev_sar_wet",
        plot_id="plot_01",
        variable="surface_wetness_index",
        value=0.80,
        source_family="sentinel1",
        source_id="s1_grd_2",
        observation_type="derived_feature",
        spatial_scope="plot",
        observed_at=now,
    )
    conflicts = detect_conflicts([e_sar_wet])
    assert any(c.conflict_type == "S1_WETNESS_WITHOUT_RAIN_OR_IRRIGATION" for c in conflicts)


def test_phenology_aware_threshold_widening():
    """Verify rapid vegetative growth stage widens vegetation index thresholds."""
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    # GDD between 200 and 800 indicates rapid vegetative growth
    e_gdd = EvidenceItem(
        evidence_id="ev_gdd",
        plot_id="plot_01",
        variable="gdd",
        value=450.0,
        source_family="environment",
        source_id="open_meteo",
        observation_type="derived_feature",
        spatial_scope="plot",
        observed_at=now,
    )
    factor = _phenology_threshold_factor([e_gdd])
    assert factor == 1.5

    # Dormancy stage string
    e_dormant = EvidenceItem(
        evidence_id="ev_dorm",
        plot_id="plot_01",
        variable="growth_stage",
        value="dormant",
        source_family="environment",
        source_id="stage_model",
        observation_type="derived_feature",
        spatial_scope="plot",
        observed_at=now,
    )
    assert _phenology_threshold_factor([e_dormant]) == 1.0


def test_bayesian_credibility_and_impact():
    """Verify Bayesian credibility product and conflict impact calculations."""
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    e = EvidenceItem(
        evidence_id="ev_cred",
        plot_id="plot_01",
        variable="ndvi",
        value=0.7,
        source_family="sentinel2",
        source_id="s2",
        observation_type="derived_feature",
        spatial_scope="plot",
        observed_at=now,
        freshness_score=0.8,
        reliability=0.9,
    )
    # credibility = freshness * reliability = 0.8 * 0.9 = 0.72
    assert abs(_credibility(e) - 0.72) < 1e-5

    # Both sources high confidence (0.9 and 0.9)
    impact_high = _bayesian_impact(0.9, 0.9)
    # One confident, one very uncertain (0.9 and 0.2)
    impact_uncertain = _bayesian_impact(0.9, 0.2)
    # Impact when one is uncertain is higher because uncertainty spreads
    assert impact_uncertain > impact_high
