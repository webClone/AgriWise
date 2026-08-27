from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from services.agribrain.diagnostic_integration import (
    AdapterContext,
    ConsistencyTribunal,
    ContributionLedger,
    ContributionRole,
    DependencyGraph,
    DiagnosticContribution,
    IdentifiabilityClass,
    InfluenceManifestBuilder,
    InfluenceUse,
    build_default_registry,
    build_default_runtime,
    validate_dependency_map,
)
from services.agribrain.scientific_contracts.authority import (
    AUTHORITY_DIAGNOSTIC_NO_STATE_UPDATE,
    AUTHORITY_MACHINE_EXECUTION_APPROVED,
    AUTHORITY_VISUAL_ONLY_NO_DIAGNOSIS,
)
from services.agribrain.scientific_contracts.exceptions import ContractViolation


def contribution(
    contribution_id: str,
    *,
    role: ContributionRole = ContributionRole.PRIMARY,
    target: str = "vegetation.vigor",
    confidence: float = 0.8,
    family: str = "S2_OPTICAL",
    parents: tuple[str, ...] = (),
    authority=AUTHORITY_DIAGNOSTIC_NO_STATE_UPDATE,
    block_reasons: tuple[str, ...] = (),
    generated_at: str = "2026-07-28T10:00:00+00:00",
) -> DiagnosticContribution:
    return DiagnosticContribution(
        layer_id="L2",
        contribution_id=contribution_id,
        input_belief_id="belief-1",
        input_evidence_ids=("evidence-1",),
        input_contribution_ids=parents,
        target_state=target,
        contribution_role=role,
        supporting_evidence=("evidence-1",) if role is not ContributionRole.CONTRADICTING else (),
        contradicting_evidence=("evidence-1",) if role is ContributionRole.CONTRADICTING else (),
        dependency_families=(family,),
        identifiability_class=IdentifiabilityClass.PARTIALLY_IDENTIFIED,
        authority=authority,
        block_reasons=block_reasons,
        confidence=confidence,
        payload={"value": 0.5, "nested": {"source": "fixture"}},
        generated_at=generated_at,
    )


def test_contribution_is_lineage_complete_content_addressed_and_deeply_immutable():
    first = contribution("c1", generated_at="2026-01-01T00:00:00Z")
    second = contribution("c1", generated_at="2026-12-31T00:00:00Z")
    assert first.content_hash == second.content_hash
    assert first.authority.state_update_allowed is False
    assert first.authority.prescription_driver_allowed is False
    with pytest.raises(TypeError):
        first.payload["value"] = 0.7
    with pytest.raises(TypeError):
        first.payload["nested"]["source"] = "changed"
    with pytest.raises((FrozenInstanceError, AttributeError)):
        first.confidence = 0.1

    with pytest.raises(ContractViolation, match="input evidence or input contribution ancestry"):
        DiagnosticContribution(
            layer_id="L2",
            contribution_id="missing-lineage",
            input_belief_id="belief-1",
            input_evidence_ids=(),
            input_contribution_ids=(),
            target_state="vegetation.vigor",
            contribution_role=ContributionRole.PRIMARY,
            dependency_families=("S2_OPTICAL",),
            identifiability_class=IdentifiabilityClass.PARTIALLY_IDENTIFIED,
            authority=AUTHORITY_DIAGNOSTIC_NO_STATE_UPDATE,
        )


def test_registry_is_fail_closed_and_all_adapters_strip_dangerous_authority():
    registry = build_default_registry()
    assert [item.layer_id for item in registry.registrations()] == [
        "L2", "L3", "L4", "L5", "L6", "L7", "L8"
    ]
    with pytest.raises(ContractViolation, match="unsupported diagnostic layer"):
        registry.resolve("L9")
    with pytest.raises(ContractViolation, match="unregistered diagnostic engine"):
        registry.resolve("L2", "missing")

    context = AdapterContext(
        input_belief_id="belief-1",
        input_evidence_ids=("weather-obs-17",),
        authority=AUTHORITY_MACHINE_EXECUTION_APPROVED,
    )
    fixtures = {
        "L2": SimpleNamespace(
            run_id="l2-run",
            anomalies=[],
            health_index=SimpleNamespace(
                overall_score=0.7, ndvi_health=0.8, water_stress_index=0.2,
                vigor_trend="STABLE", confidence=0.75,
            ),
        ),
        "L3": SimpleNamespace(
            run_id_l3="l3-run",
            diagnoses=[SimpleNamespace(
                problem_id="WATER_STRESS", probability=0.7, severity=0.5,
                confidence=0.8, drivers_used=["NDWI"], drivers_missing=[],
                evidence_trace=[{"feature_name": "ndwi"}], contra_trace=[],
            )],
        ),
        "L4": SimpleNamespace(
            run_meta=SimpleNamespace(run_id="l4-run"),
            nutrient_states={"N": SimpleNamespace(
                nutrient="N", probability_deficient=0.65, state_index=-0.3,
                severity="MODERATE", confidence=0.7, drivers_used=["NDRE"],
                evidence_trace=[], confounders=[],
            )},
        ),
        "L5": SimpleNamespace(
            run_meta=SimpleNamespace(run_id="l5-run"),
            threat_states={"rust": SimpleNamespace(
                threat_id="FUNGAL_RUST", threat_class="DISEASE", probability=0.4,
                severity="MODERATE", confidence=0.65, drivers_used=["LWD"],
                evidence_trace=[], spread_pattern="PATCHY", confounders=[],
            )},
        ),
        "L6": SimpleNamespace(
            run_meta=SimpleNamespace(run_id="l6-run"), conflict_log=[],
            outcome_report=[SimpleNamespace(
                metric_id="NDVI_RESPONSE", delta_value=0.03, confidence=0.6,
                method="BEFORE_AFTER", baseline_window={}, eval_window={},
                confounders_present=[],
            )],
        ),
        "L7": SimpleNamespace(
            run_meta=SimpleNamespace(run_id="l7-run"),
            quality_metrics=SimpleNamespace(decision_reliability=0.7),
            options=[SimpleNamespace(
                crop="wheat", overall_rank_score=0.72, suitability_percentage=72.0,
                yield_dist=None, econ=None,
                window=SimpleNamespace(confidence=0.7), soil=SimpleNamespace(confidence=0.8),
                water=SimpleNamespace(confidence=0.6), biotic=SimpleNamespace(confidence=0.75),
                rotation=None, microclimate=None, resilience=None,
            )],
        ),
        "L8": SimpleNamespace(
            run_id="l8-run",
            actions=[SimpleNamespace(
                action_id="scout-1", action_type="SCOUT", priority_score=0.8,
                is_allowed=True, blocked_reason=[], requires_confirmation=True,
                heuristic=False, evidence=[{"reference_id": "rust"}],
                primary_driver="FUNGAL_RUST", driver_source_family="L5",
                driver_confidence=0.7, confidence="HIGH",
            )],
        ),
    }
    for layer_id, fixture in fixtures.items():
        values = registry.adapt(layer_id, fixture, context)
        assert values
        assert all(value.layer_id == layer_id for value in values)
        assert all(value.input_evidence_ids == ("weather-obs-17",) for value in values)
        assert all(value.authority.state_update_allowed is False for value in values)
        assert all(value.authority.prescription_driver_allowed is False for value in values)
        assert all(value.authority.machine_execution_allowed is False for value in values)


def test_ledger_rejects_duplicates_forward_ancestry_and_cross_belief():
    ledger = ContributionLedger()
    root = contribution("root")
    child = contribution("child", parents=("root",))
    entries = ledger.append_many((root, child))
    assert [entry.sequence for entry in entries] == [1, 2]
    ledger.verify()
    assert ledger.head_hash == entries[-1].entry_hash
    with pytest.raises(ContractViolation, match="duplicate"):
        ledger.append(root)
    with pytest.raises(ContractViolation, match="absent or future"):
        ContributionLedger().append(contribution("orphan", parents=("future",)))


def test_dependency_graph_detects_cycles_and_reports_transitive_shared_families():
    with pytest.raises(ContractViolation, match="cycle"):
        validate_dependency_map({"a": ("b",), "b": ("a",)})

    graph = DependencyGraph()
    root = contribution("root", family="weather")
    child = contribution("child", family="water_model", parents=("root",))
    peer = contribution("peer", family="weather")
    graph.add_many((root, child, peer))
    assert graph.ancestry("child") == ("root",)
    assert graph.shared_families("child", "peer") == ("weather",)


def test_tribunal_blocks_denied_explicit_and_unresolved_contradictory_inputs():
    positive = contribution("positive", role=ContributionRole.PRIMARY, confidence=0.9)
    negative = contribution("negative", role=ContributionRole.CONTRADICTING, confidence=0.85)
    denied = contribution(
        "denied", target="vegetation.water", authority=AUTHORITY_VISUAL_ONLY_NO_DIAGNOSIS
    )
    explicit = contribution(
        "explicit", target="vegetation.nutrient", block_reasons=("UPSTREAM_INVALID",)
    )
    values = (positive, negative, denied, explicit)
    graph = DependencyGraph()
    graph.add_many(values)
    verdict = ConsistencyTribunal().adjudicate(values, graph)
    assert set(verdict.blocked_contribution_ids) == {
        "positive", "negative", "denied", "explicit"
    }
    codes = {finding.code for finding in verdict.findings}
    assert "UNRESOLVED_HIGH_CONFIDENCE_CONTRADICTION" in codes
    assert "DIAGNOSIS_AUTHORITY_DENIED" in codes
    assert "CONTRIBUTION_EXPLICITLY_BLOCKED" in codes


def test_manifest_bounds_shared_family_and_never_grants_state_update_by_default():
    first = contribution("first", confidence=0.9)
    # The child renames its immediate model family, but still inherits the
    # parent's optical family through contribution ancestry.
    second = contribution("second", confidence=0.8, family="WATER_MODEL", parents=("first",))
    values = (first, second)
    graph = DependencyGraph()
    graph.add_many(values)
    verdict = ConsistencyTribunal().adjudicate(values, graph)
    builder = InfluenceManifestBuilder(family_influence_limit=0.35)
    diagnostic = builder.build(verdict, values, graph)
    assert sum(abs(entry.signed_weight) for entry in diagnostic.entries) <= 0.35 + 1e-12
    assert diagnostic.requested_use is InfluenceUse.DIAGNOSIS

    state_update = builder.build(verdict, values, graph, InfluenceUse.STATE_UPDATE)
    assert state_update.entries == ()
    assert set(state_update.excluded_contribution_ids) == {"first", "second"}


def test_runtime_ingests_sequential_layers_against_one_immutable_belief():
    runtime = build_default_runtime()
    l2 = runtime.ingest_layer(
        "L2",
        SimpleNamespace(
            run_id="l2-run", anomalies=[],
            health_index=SimpleNamespace(
                overall_score=0.6, ndvi_health=0.65, water_stress_index=0.3,
                vigor_trend="STABLE", confidence=0.7,
            ),
        ),
        AdapterContext(
            input_belief_id="belief-1",
            input_evidence_ids=("s2-scene-1", "weather-obs-1"),
            authority=AUTHORITY_DIAGNOSTIC_NO_STATE_UPDATE,
        ),
    )
    l3 = runtime.ingest_layer(
        "L3",
        SimpleNamespace(
            run_id_l3="l3-run",
            diagnoses=[SimpleNamespace(
                problem_id="WATER_STRESS", probability=0.6, severity=0.4,
                confidence=0.7, drivers_used=["NDWI"], drivers_missing=[],
                evidence_trace=[{"feature_name": "ndwi"}], contra_trace=[],
            )],
        ),
        AdapterContext(
            input_belief_id="belief-1",
            input_evidence_ids=("weather-obs-1",),
            input_contribution_ids=tuple(item.contribution_id for item in l2),
            dependency_families=("WEATHER_OBSERVATION",),
            authority=AUTHORITY_DIAGNOSTIC_NO_STATE_UPDATE,
        ),
    )
    result = runtime.finalize("belief-1")
    assert len(runtime.ledger.entries()) == len(l2) + len(l3)
    assert result.ledger_head_hash == runtime.ledger.head_hash
    assert result.influence_manifest.input_belief_id == "belief-1"
    assert all(
        entry.input_belief_id == "belief-1" for entry in runtime.ledger.contributions()
    )
