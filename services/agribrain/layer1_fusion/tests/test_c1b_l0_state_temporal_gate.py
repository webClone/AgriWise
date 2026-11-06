"""C1B Layer 0 -> Layer 1 observational trust and temporal boundary tests.

These are deterministic contract/engine tests. Not a real-source field
calibration, tenant authentication, or signed irrigation qualification.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.agribrain.layer0.source_package import Layer0StatePackage
from services.agribrain.layer1_fusion.engine import Layer1FusionEngine
from services.agribrain.layer1_fusion.layer0_state_admission import (
    Layer1StateAdmissionError,
)
from services.agribrain.layer1_fusion.schemas import (
    EvidenceItem, Layer1InputBundle, SourceEnvelope,
)

RUN = datetime(2026, 11, 6, 15, 30, tzinfo=timezone.utc)


def bundle(*, state=None, sensor=None):
    return Layer1InputBundle(
        plot_id="plot-c1b",
        run_id="fusion-c1b-attempt",
        run_timestamp=RUN,
        window_start=RUN - timedelta(days=2),
        window_end=RUN,
        layer0_state_package=state,
        sensor_context_package=sensor,
    )


def canonical_state():
    return Layer0StatePackage(
        plot_id="plot-c1b",
        geometry_hash="geom-hash-v1",
        geometry_version=1,
        run_id="layer0-c1b-attempt",
        daily_state={"plot": [{"day": "2026-11-06", "sm_0_10": 0.32}]},
        state_uncertainty={"plot": [{"day": "2026-11-06", "sm_0_10": 0.08}]},
        health_report={
            "scientific_state_admissible": True,
            "audit": {"structural_audit": {
                "status": "PASS", "checks_run": 5, "checks_failed": 0,
            }},
        },
        provenance={
            "run_id": "layer0-c1b-attempt",
            "scientific_state_integrity": "PASSED_RUNTIME_BOUNDARY",
        },
        scientific_publication_authorized=False,
        actuator_control_authorized=False,
    )


def test_missing_layer0_state_is_a_gap_not_fabricated_observation():
    result = Layer1FusionEngine().fuse(bundle())
    assert not [x for x in result.evidence_items if x.source_family == "l0_state"]


def test_valid_c1_state_remains_derived_diagnostic_not_provider_observation():
    result = Layer1FusionEngine().fuse(bundle(state=canonical_state()))
    items = [x for x in result.evidence_items if x.source_family == "l0_state"]
    assert items, "accepted state should be visible as diagnostic evidence"
    assert all(x.data_status == "assimilated" for x in items)
    assert all(x.truth_class == "assimilated_state" for x in items)
    assert all(x.source_reality == "model_estimate" for x in items)
    assert all(x.diagnostic_only is True for x in items)
    assert all(x.real_provider_product is False for x in items)
    assert all(x.state_update_allowed is False for x in items)


@pytest.mark.parametrize("kind,reason", [
    ("legacy_dictionary", "layer0_state_not_canonical_object"),
    ("marker_missing", "layer0_state_integrity_not_qualified"),
    ("marker_false", "layer0_state_integrity_not_qualified"),
    ("plot_mismatch", "layer0_state_plot_scope_mismatch"),
    ("run_mismatch", "layer0_state_integrity_not_qualified"),
    ("geometry_missing", "layer0_state_invalid_scientific_identity"),
    ("content_tampering", "layer0_state_content_hash_mismatch"),
    ("audit_not_passed", "layer0_state_structural_audit_not_passed"),
    ("unexpected_actuation_authority", "layer0_state_unexpected_execution_authority"),
])
def test_unqualified_or_tampered_l0_state_is_terminal_before_fusion(kind, reason):
    pkg = canonical_state()
    if kind == "legacy_dictionary":
        pkg = {"state_vectors": {"sm_0_10": 0.32}}
    elif kind == "marker_missing":
        del pkg.health_report["scientific_state_admissible"]
    elif kind == "marker_false":
        pkg.health_report["scientific_state_admissible"] = False
    elif kind == "plot_mismatch":
        pkg.plot_id = "other-tenant-plot"
    elif kind == "run_mismatch":
        pkg.provenance["run_id"] = "unbound-run"
    elif kind == "geometry_missing":
        pkg.geometry_hash = ""
    elif kind == "content_tampering":
        pkg.daily_state["plot"][0]["sm_0_10"] = 0.83
    elif kind == "audit_not_passed":
        pkg.health_report["audit"]["structural_audit"]["status"] = "DEGRADED"
    elif kind == "unexpected_actuation_authority":
        pkg.actuator_control_authorized = True

    with pytest.raises(Layer1StateAdmissionError, match=reason):
        Layer1FusionEngine().fuse(bundle(state=pkg))


class StubSensor:
    source_family = "sensor"

    def can_read(self, pkg):
        return pkg is not None

    def source_health(self, pkg):
        return SourceEnvelope(
            source_id="c1b-sensor",
            source_family="sensor",
            source_name="C1B sensor fixture",
            package_id="c1b-packet",
            package_version="test-v1",
            source_status="ok",
            trust_score=0.9,
        )

    def extract_evidence(self, pkg, context):
        return [EvidenceItem(
            evidence_id="c1b-future-sensor",
            plot_id=context.plot_id,
            variable="soil_moisture_vwc",
            value=0.32,
            unit="fraction",
            source_family="sensor",
            source_id="c1b-sensor",
            observation_type="measurement",
            spatial_scope="point",
            observed_at=pkg,
            confidence=0.85,
            reliability=0.85,
            provenance_ref="c1b-sensor-source-evidence",
            diagnostic_only=False,
            state_update_allowed=True,
            data_status="observed",
        )]


@pytest.mark.parametrize("minutes", [6, 59, 120])
def test_future_sensor_evidence_is_quarantined_before_freshness(minutes):
    engine = Layer1FusionEngine()
    engine._registry.register(StubSensor())
    result = engine.fuse(bundle(sensor=RUN + timedelta(minutes=minutes)))
    assert not any(x.evidence_id == "c1b-future-sensor" for x in result.evidence_items)
    assert any(
        q.evidence_id == "c1b-future-sensor"
        and "FUTURE_EVIDENCE_BEYOND_SKEW" in q.reason_codes
        for q in result.diagnostics.quarantined_evidence
    )


def test_small_valid_clock_skew_is_bounded_positive_control():
    engine = Layer1FusionEngine()
    engine._registry.register(StubSensor())
    result = engine.fuse(bundle(sensor=RUN + timedelta(minutes=4)))
    assert any(x.evidence_id == "c1b-future-sensor" for x in result.evidence_items)


def test_future_sensor_timestamp_without_timezone_is_quarantined():
    engine = Layer1FusionEngine()
    engine._registry.register(StubSensor())
    naive = datetime(2026, 11, 6, 15, 39)
    result = engine.fuse(bundle(sensor=naive))
    assert any(
        q.evidence_id == "c1b-future-sensor"
        and "INVALID_TEMPORAL_REFERENCE" in q.reason_codes
        for q in result.diagnostics.quarantined_evidence
    )


def test_legacy_runner_cannot_swallow_failed_l0_admission(monkeypatch):
    """Modern trust denial must remain terminal even when ENV is development."""
    from types import SimpleNamespace
    from services.agribrain.layer1_fusion import runner as runner_module

    monkeypatch.setattr(runner_module, "is_production", lambda: False)

    def refuse(*_args, **_kwargs):
        raise runner_module.Layer1StateAdmissionError("layer0_state_integrity_not_qualified")

    def forbidden_fallback(*_args, **_kwargs):
        pytest.fail("legacy fallback must never run after a C1B admission denial")

    monkeypatch.setattr(runner_module, "run_layer1_fusion_v1", refuse)
    monkeypatch.setattr(runner_module, "run_layer1_fusion_legacy", forbidden_fallback)
    input_obj = SimpleNamespace(operational_context={})
    unqualified_l0_output = SimpleNamespace(
        layer0_state_package={"unverified": True},
        layer0_source_packages={},
    )
    with pytest.raises(
        runner_module.Layer1StateAdmissionError,
        match="layer0_state_integrity_not_qualified",
    ):
        runner_module.run_layer1_fusion(
            input_obj, layer0_output=unqualified_l0_output,
        )
