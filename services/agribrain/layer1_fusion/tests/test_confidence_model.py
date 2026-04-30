"""
Layer 1 — Confidence Model Unit Tests.

Tests role ceilings, observation type ceilings, conflict penalty stacking,
min() composition, and edge cases (zero reliability, multiple conflicts).
"""

import pytest
from datetime import datetime, timezone

from layer1_fusion.confidence_model import (
    compute_confidence,
    compute_confidence_batch,
    ROLE_CEILINGS,
)
from layer1_fusion.schemas import EvidenceConflict, EvidenceItem


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_evidence(source_family="sensor", confidence=0.90, reliability=0.90,
                   freshness_score=0.90, observation_type="measurement"):
    return EvidenceItem(
        evidence_id="ev_conf",
        plot_id="plot_1",
        variable="moisture",
        value=0.5,
        unit="fraction",
        source_family=source_family,
        source_id=f"{source_family}_1",
        observation_type=observation_type,
        spatial_scope="plot",
        confidence=confidence,
        reliability=reliability,
        freshness_score=freshness_score,
        provenance_ref="prov_1",
    )


def _make_conflict(evidence_id, severity="minor"):
    return EvidenceConflict(
        conflict_id="cf_test",
        conflict_type="SENSOR_VS_SAR_MOISTURE_CONFLICT",
        variable_group="water",
        spatial_scope="plot",
        source_a=evidence_id,
        source_b="other_ev",
        severity=severity,
    )


# ── Test: Role Ceilings ────────────────────────────────────────────────────

class TestRoleCeilings:
    """Each source family has a confidence ceiling."""

    def test_sensor_ceiling_095(self):
        e = _make_evidence("sensor", confidence=0.99)
        score = compute_confidence(e, [])
        assert score <= 0.95

    def test_s2_ceiling_085(self):
        e = _make_evidence("sentinel2", confidence=0.99)
        score = compute_confidence(e, [])
        assert score <= 0.85

    def test_s1_ceiling_065(self):
        e = _make_evidence("sentinel1", confidence=0.99)
        score = compute_confidence(e, [])
        assert score <= 0.65

    def test_forecast_ceiling_060(self):
        e = _make_evidence("weather_forecast", confidence=0.99,
                           observation_type="forecast")
        score = compute_confidence(e, [])
        assert score <= 0.60

    def test_history_ceiling_035(self):
        e = _make_evidence("history", confidence=0.99)
        score = compute_confidence(e, [])
        assert score <= 0.35

    def test_all_families_have_ceiling(self):
        """Every source family in the registry must have a role ceiling."""
        from layer1_fusion.schemas import SOURCE_FAMILIES
        for family in SOURCE_FAMILIES:
            assert family in ROLE_CEILINGS, f"Missing ceiling for {family}"


# ── Test: Observation Type Ceilings ─────────────────────────────────────────

class TestObservationTypeCeilings:
    def test_forecast_type_caps_at_060(self):
        e = _make_evidence("sensor", observation_type="forecast", confidence=0.99)
        score = compute_confidence(e, [])
        assert score <= 0.60

    def test_model_estimate_caps_at_050(self):
        e = _make_evidence("sensor", observation_type="model_estimate", confidence=0.99)
        score = compute_confidence(e, [])
        assert score <= 0.50

    def test_static_prior_caps_at_075(self):
        e = _make_evidence("geo_context", observation_type="static_prior", confidence=0.99)
        score = compute_confidence(e, [])
        assert score <= 0.75

    def test_measurement_no_cap(self):
        e = _make_evidence("sensor", observation_type="measurement", confidence=0.90)
        score = compute_confidence(e, [])
        # Only limited by role ceiling (0.95) and other factors
        assert score == 0.90


# ── Test: Conflict Penalties ────────────────────────────────────────────────

class TestConflictPenalties:
    def test_minor_conflict_caps_at_085(self):
        e = _make_evidence("sensor", confidence=0.95)
        conflict = _make_conflict(e.evidence_id, "minor")
        score = compute_confidence(e, [conflict])
        assert score <= 0.85

    def test_major_conflict_caps_at_050(self):
        e = _make_evidence("sensor", confidence=0.95)
        conflict = _make_conflict(e.evidence_id, "major")
        score = compute_confidence(e, [conflict])
        assert score <= 0.50

    def test_moderate_conflict_caps_at_070(self):
        e = _make_evidence("sensor", confidence=0.95)
        conflict = _make_conflict(e.evidence_id, "moderate")
        score = compute_confidence(e, [conflict])
        assert score <= 0.70

    def test_unrelated_conflict_no_impact(self):
        e = _make_evidence("sensor", confidence=0.90)
        conflict = _make_conflict("other_evidence", "major")
        score = compute_confidence(e, [conflict])
        assert score == 0.90  # Not involved in the conflict

    def test_multiple_conflicts_worst_wins(self):
        e = _make_evidence("sensor", confidence=0.95)
        c1 = _make_conflict(e.evidence_id, "minor")
        c2 = EvidenceConflict(
            conflict_id="cf_2", conflict_type="S2_STRESS_WITH_ADEQUATE_WATER",
            variable_group="vegetation", spatial_scope="plot",
            source_a=e.evidence_id, source_b="other", severity="major",
        )
        score = compute_confidence(e, [c1, c2])
        assert score <= 0.50  # Major wins


# ── Test: Min() Composition ─────────────────────────────────────────────────

class TestMinComposition:
    def test_lowest_factor_wins(self):
        """Confidence is min() of all factors — lowest one dominates."""
        e = _make_evidence("sensor", confidence=0.95, reliability=0.20,
                           freshness_score=0.90)
        score = compute_confidence(e, [])
        assert score == 0.20  # reliability is the bottleneck

    def test_freshness_bottleneck(self):
        e = _make_evidence("sensor", confidence=0.95, reliability=0.95,
                           freshness_score=0.10)
        score = compute_confidence(e, [])
        assert score == 0.10  # freshness is the bottleneck

    def test_all_high_still_capped_by_role(self):
        e = _make_evidence("sentinel1", confidence=0.99, reliability=0.99,
                           freshness_score=0.99)
        score = compute_confidence(e, [])
        assert score == 0.65  # S1 role ceiling


# ── Test: Edge Cases ────────────────────────────────────────────────────────

class TestConfidenceEdgeCases:
    def test_zero_reliability(self):
        e = _make_evidence("sensor", confidence=0.90, reliability=0.0)
        score = compute_confidence(e, [])
        assert score == 0.0

    def test_zero_confidence(self):
        e = _make_evidence("sensor", confidence=0.0, reliability=0.90)
        score = compute_confidence(e, [])
        assert score == 0.0

    def test_zero_freshness(self):
        e = _make_evidence("sensor", confidence=0.90, freshness_score=0.0)
        score = compute_confidence(e, [])
        assert score == 0.0

    def test_result_never_negative(self):
        e = _make_evidence("sensor", confidence=0.01, reliability=0.01,
                           freshness_score=0.01)
        score = compute_confidence(e, [])
        assert score >= 0.0

    def test_result_never_above_1(self):
        e = _make_evidence("sensor", confidence=1.0, reliability=1.0,
                           freshness_score=1.0)
        score = compute_confidence(e, [])
        assert score <= 1.0


# ── Test: Batch Processing ──────────────────────────────────────────────────

class TestConfidenceBatch:
    def test_batch_updates_all(self):
        items = [
            _make_evidence("sensor", confidence=0.90),
            _make_evidence("sentinel2", confidence=0.90),
            _make_evidence("history", confidence=0.90),
        ]
        compute_confidence_batch(items, [])
        assert items[0].confidence <= 0.95  # sensor ceiling
        assert items[1].confidence <= 0.85  # S2 ceiling
        assert items[2].confidence <= 0.35  # history ceiling

    def test_batch_with_conflicts(self):
        items = [
            _make_evidence("sensor", confidence=0.90),
        ]
        items[0].evidence_id = "ev_target"
        conflict = _make_conflict("ev_target", "major")
        compute_confidence_batch(items, [conflict])
        assert items[0].confidence <= 0.50

    def test_batch_empty(self):
        result = compute_confidence_batch([], [])
        assert result == []
