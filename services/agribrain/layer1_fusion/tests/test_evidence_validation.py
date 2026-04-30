"""
Layer 1 — Evidence Validation Unit Tests.

Tests each validation rule, quarantine severity, boundary values,
and provenance enforcement.
"""

import pytest
from layer1_fusion.evidence_validation import validate_evidence, quarantine_evidence
from layer1_fusion.schemas import EvidenceItem, CANONICAL_UNITS, SOURCE_FAMILIES, SPATIAL_SCOPES


# ── Helpers ──────────────────────────────────────────────────────────────────

def _valid_evidence(**overrides):
    """Build a valid evidence item with optional overrides."""
    base = dict(
        evidence_id="ev_1",
        plot_id="plot_1",
        variable="moisture",
        value=0.5,
        unit="fraction",
        source_family="sensor",
        source_id="sensor_1",
        observation_type="measurement",
        spatial_scope="plot",
        confidence=0.8,
        reliability=0.9,
        provenance_ref="prov_ref_1",
    )
    base.update(overrides)
    return EvidenceItem(**base)


# ── Test: Valid Evidence Passes ──────────────────────────────────────────────

class TestValidEvidence:
    def test_valid_evidence_no_violations(self):
        e = _valid_evidence()
        violations = validate_evidence(e)
        assert violations == []

    def test_unit_none_is_valid(self):
        e = _valid_evidence(unit=None)
        violations = validate_evidence(e)
        assert violations == []

    def test_all_canonical_units_accepted(self):
        for unit in CANONICAL_UNITS:
            e = _valid_evidence(unit=unit)
            violations = validate_evidence(e)
            assert violations == [], f"Unit {unit} should be valid"


# ── Test: ID Validation ─────────────────────────────────────────────────────

class TestIDValidation:
    def test_empty_evidence_id(self):
        e = _valid_evidence(evidence_id="")
        violations = validate_evidence(e)
        assert "EMPTY_EVIDENCE_ID" in violations

    def test_empty_plot_id(self):
        e = _valid_evidence(plot_id="")
        violations = validate_evidence(e)
        assert "EMPTY_PLOT_ID" in violations

    def test_empty_variable(self):
        e = _valid_evidence(variable="")
        violations = validate_evidence(e)
        assert "EMPTY_VARIABLE" in violations


# ── Test: Source Family Validation ───────────────────────────────────────────

class TestSourceFamilyValidation:
    def test_invalid_source_family(self):
        e = _valid_evidence(source_family="unknown_source")
        violations = validate_evidence(e)
        assert any("INVALID_SOURCE_FAMILY" in v for v in violations)

    def test_all_valid_families_accepted(self):
        for family in SOURCE_FAMILIES:
            e = _valid_evidence(source_family=family)
            violations = validate_evidence(e)
            family_violations = [v for v in violations if "INVALID_SOURCE_FAMILY" in v]
            assert family_violations == [], f"Family {family} should be valid"


# ── Test: Observation Type Validation ───────────────────────────────────────

class TestObservationTypeValidation:
    def test_invalid_observation_type(self):
        e = _valid_evidence(observation_type="raw_data")
        violations = validate_evidence(e)
        assert any("INVALID_OBSERVATION_TYPE" in v for v in violations)

    def test_forecast_from_non_forecast_source(self):
        e = _valid_evidence(observation_type="forecast", source_family="sensor")
        violations = validate_evidence(e)
        assert "FORECAST_FROM_NON_FORECAST_SOURCE" in violations

    def test_forecast_from_weather_forecast_ok(self):
        e = _valid_evidence(observation_type="forecast",
                            source_family="weather_forecast")
        violations = validate_evidence(e)
        assert "FORECAST_FROM_NON_FORECAST_SOURCE" not in violations


# ── Test: Spatial Scope Validation ──────────────────────────────────────────

class TestSpatialScopeValidation:
    def test_invalid_spatial_scope(self):
        e = _valid_evidence(spatial_scope="global")
        violations = validate_evidence(e)
        assert any("INVALID_SPATIAL_SCOPE" in v for v in violations)

    def test_all_valid_scopes_accepted(self):
        for scope in SPATIAL_SCOPES:
            e = _valid_evidence(spatial_scope=scope)
            violations = validate_evidence(e)
            scope_violations = [v for v in violations if "INVALID_SPATIAL_SCOPE" in v]
            assert scope_violations == [], f"Scope {scope} should be valid"


# ── Test: Unit Validation ───────────────────────────────────────────────────

class TestUnitValidation:
    def test_non_canonical_unit(self):
        e = _valid_evidence(unit="fahrenheit")
        violations = validate_evidence(e)
        assert any("NON_CANONICAL_UNIT" in v for v in violations)


# ── Test: Confidence/Reliability Bounds ─────────────────────────────────────

class TestBoundsValidation:
    def test_confidence_too_high(self):
        e = _valid_evidence(confidence=1.5)
        violations = validate_evidence(e)
        assert any("CONFIDENCE_OUT_OF_BOUNDS" in v for v in violations)

    def test_confidence_negative(self):
        e = _valid_evidence(confidence=-0.1)
        violations = validate_evidence(e)
        assert any("CONFIDENCE_OUT_OF_BOUNDS" in v for v in violations)

    def test_confidence_boundary_0(self):
        e = _valid_evidence(confidence=0.0)
        violations = validate_evidence(e)
        assert not any("CONFIDENCE_OUT_OF_BOUNDS" in v for v in violations)

    def test_confidence_boundary_1(self):
        e = _valid_evidence(confidence=1.0)
        violations = validate_evidence(e)
        assert not any("CONFIDENCE_OUT_OF_BOUNDS" in v for v in violations)

    def test_reliability_too_high(self):
        e = _valid_evidence(reliability=1.5)
        violations = validate_evidence(e)
        assert any("RELIABILITY_OUT_OF_BOUNDS" in v for v in violations)

    def test_reliability_negative(self):
        e = _valid_evidence(reliability=-0.1)
        violations = validate_evidence(e)
        assert any("RELIABILITY_OUT_OF_BOUNDS" in v for v in violations)


# ── Test: Provenance Validation ─────────────────────────────────────────────

class TestProvenanceValidation:
    def test_missing_provenance_ref(self):
        e = _valid_evidence(provenance_ref="")
        violations = validate_evidence(e)
        assert "MISSING_PROVENANCE_REF" in violations


# ── Test: Multiple Violations ───────────────────────────────────────────────

class TestMultipleViolations:
    def test_multiple_violations_all_caught(self):
        e = _valid_evidence(evidence_id="", plot_id="", variable="",
                            provenance_ref="")
        violations = validate_evidence(e)
        assert len(violations) >= 4


# ── Test: Quarantine ────────────────────────────────────────────────────────

class TestQuarantine:
    def test_quarantine_preserves_fields(self):
        e = _valid_evidence()
        q = quarantine_evidence(e, ["TEST_VIOLATION"])
        assert q.evidence_id == "ev_1"
        assert q.original_source_family == "sensor"
        assert q.variable == "moisture"
        assert q.original_value == 0.5
        assert q.original_unit == "fraction"

    def test_quarantine_severity_escalation(self):
        e = _valid_evidence()
        # 1 violation → error
        q1 = quarantine_evidence(e, ["V1"])
        assert q1.severity == "error"
        # 3+ violations → blocking
        q3 = quarantine_evidence(e, ["V1", "V2", "V3"])
        assert q3.severity == "blocking"

    def test_quarantine_reason_codes(self):
        e = _valid_evidence()
        q = quarantine_evidence(e, ["MISSING_PROVENANCE_REF", "EMPTY_VARIABLE"])
        assert "MISSING_PROVENANCE_REF" in q.reason_codes
        assert "EMPTY_VARIABLE" in q.reason_codes
