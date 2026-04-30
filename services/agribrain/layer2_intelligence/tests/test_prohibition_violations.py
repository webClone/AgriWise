"""
Layer 2 Intelligence — Prohibition Violation Tests.

Intentionally breaks each of the 10 hard prohibitions and verifies
the engine detects the violation.  Mirrors L1's test_prohibition_violations.py.
"""

import pytest
from datetime import datetime, timezone

from layer1_fusion.schemas import (
    DataHealthScore, Layer2InputContext, SpatialIndex, ZoneRef,
)
from layer2_intelligence.engine import Layer2IntelligenceEngine
from layer2_intelligence.schemas import (
    Layer2Output, StressEvidence, FORBIDDEN_L2_VOCABULARY,
)
from layer2_intelligence.context_invariants import enforce_layer2_invariants


_TS = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
_HEALTH = DataHealthScore(
    overall=0.8, confidence_ceiling=0.9, status="ok",
    source_completeness=0.9, provenance_completeness=1.0,
    freshness=0.9, spatial_fidelity=0.7,
)


def _ctx(water=None, veg=None, stress=None, **kw):
    return Layer2InputContext(
        plot_id="prohib_plot",
        water_context=water or {},
        vegetation_context=veg or {},
        stress_evidence_context=stress or {},
        operational_context={}, soil_site_context={},
        conflicts=[], gaps=[],
        provenance_ref="l1_prohib",
        spatial_index_ref=kw.get("spatial_index"),
        data_health=kw.get("data_health", _HEALTH),
    )


def _stress_ctx():
    """Context that produces a WATER stress item."""
    return _ctx(
        water={
            "ndmi_mean": {"value": 0.10, "confidence": 0.7, "source_weights": {"s2": 0.8}},
            "soil_moisture_vwc": {"value": 0.12, "confidence": 0.6, "source_weights": {}},
        },
        veg={"ndvi_mean": {"value": 0.40, "confidence": 0.7, "source_weights": {}}},
    )


# ══════════════════════════════════════════════════════════════════════════
# 1. Forbidden vocabulary injection
# ══════════════════════════════════════════════════════════════════════════

class TestForbiddenVocabulary:
    """Injecting forbidden terms into explanation_basis must be caught."""

    def test_each_forbidden_term_detected(self):
        """Each of the 13 forbidden terms must be caught by invariants."""
        engine = Layer2IntelligenceEngine()
        pkg = engine.analyze(_stress_ctx(), run_id="vocab_test", run_timestamp=_TS)
        assert len(pkg.stress_context) > 0

        for term in FORBIDDEN_L2_VOCABULARY:
            # Inject forbidden term
            pkg.stress_context[0].explanation_basis.append(
                f"You should {term} immediately"
            )
            violations = enforce_layer2_invariants(pkg)
            vocab_violations = [v for v in violations if v.check_name == "no_prescription_vocabulary"]
            assert len(vocab_violations) > 0, f"Forbidden term '{term}' was not caught"
            # Clean up for next iteration
            pkg.stress_context[0].explanation_basis.pop()

    def test_clean_output_has_no_vocab_violations(self):
        engine = Layer2IntelligenceEngine()
        pkg = engine.analyze(_stress_ctx(), run_id="vocab_clean", run_timestamp=_TS)
        violations = enforce_layer2_invariants(pkg)
        vocab_violations = [v for v in violations if v.check_name == "no_prescription_vocabulary"]
        assert len(vocab_violations) == 0


# ══════════════════════════════════════════════════════════════════════════
# 2. Severity > confidence injection
# ══════════════════════════════════════════════════════════════════════════

class TestSeverityAboveConfidence:
    """Engine must cap severity ≤ confidence + 0.1."""

    def test_engine_caps_severity(self):
        engine = Layer2IntelligenceEngine()
        pkg = engine.analyze(_stress_ctx(), run_id="sev_cap", run_timestamp=_TS)
        for s in pkg.stress_context:
            assert s.severity <= s.confidence + 0.1 + 0.001, \
                f"severity={s.severity} exceeds confidence={s.confidence}+0.1"

    def test_prohibition_check_catches_violation(self):
        engine = Layer2IntelligenceEngine()
        pkg = engine.analyze(_stress_ctx(), run_id="sev_prohib", run_timestamp=_TS)
        # Manually break the invariant
        if pkg.stress_context:
            pkg.stress_context[0].severity = 0.95
            pkg.stress_context[0].confidence = 0.3
            result = engine._check_hard_prohibitions(pkg)
            assert result["no_severity_above_confidence"] is False


# ══════════════════════════════════════════════════════════════════════════
# 3. Zone stress without zone ref
# ══════════════════════════════════════════════════════════════════════════

class TestZoneStressWithoutZoneRef:
    """Zone-scoped stress must reference a real zone in spatial_index."""

    def test_phantom_zone_caught(self):
        engine = Layer2IntelligenceEngine()
        pkg = engine.analyze(_stress_ctx(), run_id="zone_phantom", run_timestamp=_TS)
        # Inject a zone-scoped stress for a nonexistent zone
        pkg.stress_context.append(StressEvidence(
            stress_id="fake_zone_stress",
            stress_type="WATER",
            severity=0.5,
            confidence=0.6,
            uncertainty=0.1,
            spatial_scope="zone",
            scope_id="nonexistent_zone",
            explanation_basis=["Fabricated zone stress"],
        ))
        result = engine._check_hard_prohibitions(pkg)
        assert result["no_zone_stress_without_zone_ref"] is False

    def test_valid_zone_passes(self):
        ctx = _ctx(
            water={
                "ndmi_mean": {"value": 0.10, "confidence": 0.7, "source_weights": {}},
                "ndmi_z1": {"value": 0.08, "confidence": 0.7, "scope_id": "z1", "source_weights": {}},
            },
            veg={
                "ndvi_mean": {"value": 0.40, "confidence": 0.7, "source_weights": {}},
                "ndvi_z1": {"value": 0.30, "confidence": 0.7, "scope_id": "z1", "source_weights": {}},
            },
            spatial_index=SpatialIndex(
                plot_id="prohib_plot",
                zones=[ZoneRef(zone_id="z1")],
            ),
        )
        engine = Layer2IntelligenceEngine()
        pkg = engine.analyze(ctx, run_id="zone_valid", run_timestamp=_TS)
        result = engine._check_hard_prohibitions(pkg)
        assert result["no_zone_stress_without_zone_ref"] is True


# ══════════════════════════════════════════════════════════════════════════
# 4. Diagnostic severity cap
# ══════════════════════════════════════════════════════════════════════════

class TestDiagnosticSeverityCap:
    """diagnostic_only stress must not exceed severity 0.5."""

    def test_invariant_caps_diagnostic_severity(self):
        engine = Layer2IntelligenceEngine()
        pkg = engine.analyze(_stress_ctx(), run_id="diag_cap", run_timestamp=_TS)
        if pkg.stress_context:
            pkg.stress_context[0].diagnostic_only = True
            pkg.stress_context[0].severity = 0.9
            violations = enforce_layer2_invariants(pkg)
            cap_violations = [v for v in violations if v.check_name == "diagnostic_only_severity_cap"]
            assert len(cap_violations) > 0
            # Should be auto-fixed
            assert pkg.stress_context[0].severity <= 0.5

    def test_non_diagnostic_not_capped(self):
        engine = Layer2IntelligenceEngine()
        pkg = engine.analyze(_stress_ctx(), run_id="diag_nocap", run_timestamp=_TS)
        for s in pkg.stress_context:
            assert not s.diagnostic_only or s.severity <= 0.5


# ══════════════════════════════════════════════════════════════════════════
# 5. Stress without evidence chain
# ══════════════════════════════════════════════════════════════════════════

class TestStressWithoutEvidence:
    """Every stress item must have at least explanation_basis or evidence IDs."""

    def test_empty_evidence_caught(self):
        engine = Layer2IntelligenceEngine()
        pkg = engine.analyze(_stress_ctx(), run_id="no_ev", run_timestamp=_TS)
        if pkg.stress_context:
            pkg.stress_context[0].contributing_evidence_ids = []
            pkg.stress_context[0].explanation_basis = []
            result = engine._check_hard_prohibitions(pkg)
            assert result["no_stress_without_evidence"] is False

    def test_normal_output_has_evidence(self):
        engine = Layer2IntelligenceEngine()
        pkg = engine.analyze(_stress_ctx(), run_id="has_ev", run_timestamp=_TS)
        result = engine._check_hard_prohibitions(pkg)
        assert result["no_stress_without_evidence"] is True


# ══════════════════════════════════════════════════════════════════════════
# 6. Uncertainty propagation
# ══════════════════════════════════════════════════════════════════════════

class TestUncertaintyPropagation:
    """All stress items must have uncertainty > 0."""

    def test_zero_uncertainty_caught(self):
        engine = Layer2IntelligenceEngine()
        pkg = engine.analyze(_stress_ctx(), run_id="unc_zero", run_timestamp=_TS)
        if pkg.stress_context:
            pkg.stress_context[0].uncertainty = 0.0
            result = engine._check_hard_prohibitions(pkg)
            assert result["uncertainty_propagated"] is False

    def test_normal_output_has_uncertainty(self):
        engine = Layer2IntelligenceEngine()
        pkg = engine.analyze(_stress_ctx(), run_id="unc_ok", run_timestamp=_TS)
        for s in pkg.stress_context:
            assert s.uncertainty > 0


# ══════════════════════════════════════════════════════════════════════════
# 7. Data health inheritance
# ══════════════════════════════════════════════════════════════════════════

class TestDataHealthInheritance:
    """L2 data_health must reflect L1 data_health."""

    def test_health_propagated(self):
        engine = Layer2IntelligenceEngine()
        pkg = engine.analyze(_stress_ctx(), run_id="health_prop", run_timestamp=_TS)
        assert pkg.data_health.overall == _HEALTH.overall

    def test_degraded_health_propagated(self):
        degraded = DataHealthScore(overall=0.15, confidence_ceiling=0.4, status="degraded")
        ctx = _ctx(
            water={"ndmi_mean": {"value": 0.10, "confidence": 0.3, "source_weights": {}}},
            veg={"ndvi_mean": {"value": 0.35, "confidence": 0.3, "source_weights": {}}},
            data_health=degraded,
        )
        engine = Layer2IntelligenceEngine()
        pkg = engine.analyze(ctx, run_id="health_deg", run_timestamp=_TS)
        assert pkg.data_health.overall == 0.15
        assert pkg.diagnostics.status == "degraded"


# ══════════════════════════════════════════════════════════════════════════
# 8. Invariant auto-fix verification
# ══════════════════════════════════════════════════════════════════════════

class TestInvariantAutoFix:
    """Auto-fixable violations must be fixed in-place."""

    def test_confidence_floor_auto_fixed(self):
        engine = Layer2IntelligenceEngine()
        pkg = engine.analyze(_stress_ctx(), run_id="autofix_conf", run_timestamp=_TS)
        if pkg.stress_context:
            pkg.stress_context[0].confidence = 0.001
            violations = enforce_layer2_invariants(pkg)
            floor_fixes = [v for v in violations if v.check_name == "stress_confidence_floor"]
            assert len(floor_fixes) > 0
            assert floor_fixes[0].auto_fixed is True
            assert pkg.stress_context[0].confidence == 0.05

    def test_severity_bounds_auto_fixed(self):
        engine = Layer2IntelligenceEngine()
        pkg = engine.analyze(_stress_ctx(), run_id="autofix_sev", run_timestamp=_TS)
        if pkg.stress_context:
            pkg.stress_context[0].severity = 1.5
            violations = enforce_layer2_invariants(pkg)
            bound_fixes = [v for v in violations if v.check_name == "stress_severity_bounds"]
            assert len(bound_fixes) > 0
            assert pkg.stress_context[0].severity == 1.0
