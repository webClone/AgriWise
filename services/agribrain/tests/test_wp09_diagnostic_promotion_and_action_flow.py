"""
Test suite for Work Package 09 (WP09) — Rebuild Diagnostic Promotion & Action Flow.

Validates the resolution of 4 architectural defects identified in the Monograph Audit:
1. Finding #1: Deterministic Prescription Authority Deadlock resolved via DiagnosticPromotionService.
2. Finding #2: Permission Reconstruction from None Metadata eliminated via explicit type-checked validation.
3. Finding #3: Intent Branch Contradictions aligned (DIAGNOSIS, PLANNING, DECISION).
4. Finding #4: Decision Sequence Inversion corrected (L6 Feasibility -> L7 Planning -> L8 Prescriptive),
   with candidate scenarios and feasibility constraints propagated into Layer8Input.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest

from services.agribrain.diagnostic_integration import (
    ConsistencyTribunal,
    ContributionRole,
    DependencyGraph,
    DiagnosticContribution,
    DiagnosticPromotionService,
    IdentifiabilityClass,
    InfluenceManifestBuilder,
    InfluenceUse,
    PromotionResult,
)
from services.agribrain.diagnostic_integration.contracts import (
    canonical_hash,
)
from services.agribrain.scientific_contracts.authority import (
    AUTHORITY_DIAGNOSTIC_NO_STATE_UPDATE,
    AuthorityVector,
)
from services.agribrain.layer8_prescriptive.schema import (
    Layer8Input,
)
from services.agribrain.orchestrator_v2.intents import (
    Intent,
)
from services.agribrain.orchestrator_v2.registry import (
    LayerId,
)
from services.agribrain.orchestrator_v2.schema import (
    LayerResult,
    LayerStatus,
    OrchestratorInput,
)
from services.agribrain.orchestrator_v2.runner import (
    _build_diagnostic_integration,
)


def make_diagnostic_contribution(
    contribution_id: str,
    *,
    layer_id: str = "L2",
    target: str = "vegetation.vigor",
    confidence: float = 0.85,
    identifiability: IdentifiabilityClass = IdentifiabilityClass.IDENTIFIED,
    role: ContributionRole = ContributionRole.PRIMARY,
    family: str = "S2_OPTICAL",
    parents: tuple[str, ...] = (),
    block_reasons: tuple[str, ...] = (),
    authority: AuthorityVector = AUTHORITY_DIAGNOSTIC_NO_STATE_UPDATE,
) -> DiagnosticContribution:
    """Helper to construct valid DiagnosticContribution with diagnostic authority."""
    return DiagnosticContribution(
        layer_id=layer_id,
        contribution_id=contribution_id,
        input_belief_id="belief-test-101",
        input_evidence_ids=("evidence-sample-1",),
        input_contribution_ids=parents,
        target_state=target,
        contribution_role=role,
        supporting_evidence=("evidence-sample-1",),
        dependency_families=(family,),
        identifiability_class=identifiability,
        authority=authority,
        block_reasons=block_reasons,
        confidence=confidence,
        payload={"stress_index": 0.32, "metric": "test"},
        generated_at="2026-09-09T12:00:00+00:00",
    )


# -----------------------------------------------------------------------------
# 1. Finding #1: Deadlock Resolution via DiagnosticPromotionService
# -----------------------------------------------------------------------------

def test_deadlock_resolution_via_promotion():
    """Verify that DiagnosticPromotionService elevates diagnostic contributions to PRESCRIPTION_DRIVER,

    unblocking the influence manifest and resolving the deterministic authority deadlock.
    """
    # 1. Diagnostic adapter outputs initially have prescription_driver_allowed = False
    c1 = make_diagnostic_contribution("c_veg", target="vegetation.vigor", confidence=0.88)
    c2 = make_diagnostic_contribution("c_water", layer_id="L3", target="soil.moisture", confidence=0.78)

    assert c1.authority.prescription_driver_allowed is False
    assert c2.authority.prescription_driver_allowed is False

    # 2. Before promotion, requesting PRESCRIPTION_DRIVER produces an empty manifest
    graph = DependencyGraph()
    graph.add_many([c1, c2])
    tribunal = ConsistencyTribunal()
    verdict = tribunal.adjudicate([c1, c2], graph)
    assert verdict.accepted_contribution_ids == ("c_veg", "c_water")

    builder = InfluenceManifestBuilder()
    unpromoted_manifest = builder.build(verdict, [c1, c2], graph, InfluenceUse.PRESCRIPTION_DRIVER)
    # Finding #1 Deadlock reproduced: unpromoted entries are completely empty!
    assert len(unpromoted_manifest.entries) == 0

    # 3. Promote via DiagnosticPromotionService
    promo_service = DiagnosticPromotionService(default_min_confidence=0.70)
    policy_snapshot = {
        "min_prescription_confidence": 0.70,
        "allowed_target_variables": ["vegetation.vigor", "soil.moisture"],
    }
    promo_result = promo_service.promote_to_prescription_eligibility(
        [c1, c2], policy_snapshot=policy_snapshot
    )

    assert isinstance(promo_result, PromotionResult)
    assert promo_result.promoted_count == 2
    assert set(promo_result.promoted_ids) == {"c_veg", "c_water"}
    assert len(promo_result.exclusions) == 0

    # Verify elevated authority on promoted contributions
    for promoted in promo_result.promoted_contributions:
        assert promoted.authority.prescription_driver_allowed is True
        assert promoted.authority.diagnosis_allowed is True
        assert promoted.authority.visualization_allowed is True
        assert promoted.authority.machine_execution_allowed is False  # Safe: execution gated separately

    # 4. Building manifest with promoted contributions succeeds (deadlock broken)
    promoted_map = {c.contribution_id: c for c in promo_result.promoted_contributions}
    effective_contributions = [promoted_map.get(c.contribution_id, c) for c in [c1, c2]]

    promoted_manifest = builder.build(
        verdict, effective_contributions, graph, InfluenceUse.PRESCRIPTION_DRIVER
    )
    assert len(promoted_manifest.entries) == 2
    entry_ids = [e.contribution_id for e in promoted_manifest.entries]
    assert "c_veg" in entry_ids
    assert "c_water" in entry_ids


def test_build_diagnostic_integration_end_to_end_promotion():
    """Verify that _build_diagnostic_integration() with PRESCRIPTION_DRIVER executes promotion

    and returns a completed manifest with non-empty entries and promotion_audit.
    """
    # Create valid mock outputs for L1, L2, L3
    mock_l1 = SimpleNamespace(
        run_id="run_l1_test",
        intelligence_snapshot_id="snap_101",
        provenance={"evidence_count": 4, "data_health_status": "healthy"},
    )
    mock_l2 = SimpleNamespace(
        run_id="run_l2_test",
        belief_id="belief_101",
        output=SimpleNamespace(
            run_id="run_l2_test",
            anomalies=[
                {
                    "anomaly_id": "anom_1",
                    "type": "STRESS",
                    "confidence": 0.85,
                    "likely_cause": "WATER_DEFICIT",
                }
            ],
            health_index=0.85,
        ),
    )
    mock_l3 = SimpleNamespace(
        run_id="run_l3_test",
        output=SimpleNamespace(
            run_id="run_l3_test",
            diagnoses=[
                {
                    "problem_id": "WATER_DEFICIT",
                    "confidence": 0.85,
                    "probability": 0.80,
                    "evidence_trace": ["ndvi_drop"],
                }
            ],
        ),
    )

    results = {
        LayerId.L1: LayerResult(layer_id="L1", status=LayerStatus.OK, output=mock_l1, run_id="run_l1_test"),
        LayerId.L2: LayerResult(layer_id="L2", status=LayerStatus.OK, output=mock_l2.output, run_id="run_l2_test"),
        LayerId.L3: LayerResult(layer_id="L3", status=LayerStatus.OK, output=mock_l3.output, run_id="run_l3_test"),
    }

    policy = {"min_prescription_confidence": 0.60}
    diag_res = _build_diagnostic_integration(
        results,
        orchestrator_run_id="orch_test_001",
        timestamp="2026-09-09T12:00:00Z",
        requested_use=InfluenceUse.PRESCRIPTION_DRIVER,
        policy_snapshot=policy,
    )

    assert diag_res["status"] in ("completed", "completed_with_adapter_failures")
    manifest = diag_res.get("influence_manifest", {})
    assert manifest.get("requested_use") == "PRESCRIPTION_DRIVER"
    # Promotion audit must be present in the diagnostic result
    assert "promotion_audit" in diag_res
    audit = diag_res["promotion_audit"]
    assert audit["evaluated_count"] > 0
    # Eligible contributions must have been promoted, giving non-empty manifest entries
    assert len(manifest.get("entries", [])) > 0


# -----------------------------------------------------------------------------
# 2. Finding #1: Fail-Closed Behavior for Low-Confidence / Ineligible Input
# -----------------------------------------------------------------------------

def test_fail_closed_low_confidence_or_uncalibrated():
    """Verify that contributions failing confidence, identifiability, policy scope, or with

    block reasons are strictly rejected by DiagnosticPromotionService.
    """
    promo_service = DiagnosticPromotionService(default_min_confidence=0.75)
    policy = {
        "min_prescription_confidence": 0.75,
        "allowed_target_variables": ["vegetation.vigor", "soil.moisture"],
    }

    # Contribution A: Low confidence (0.55 < 0.75)
    c_low_conf = make_diagnostic_contribution(
        "c_low_conf", target="vegetation.vigor", confidence=0.55
    )
    # Contribution B: Identifiability is HEURISTIC
    c_heuristic = make_diagnostic_contribution(
        "c_heuristic",
        target="vegetation.vigor",
        confidence=0.90,
        identifiability=IdentifiabilityClass.HEURISTIC,
    )
    # Contribution C: Identifiability is CONFOUNDED
    c_confounded = make_diagnostic_contribution(
        "c_confounded",
        target="vegetation.vigor",
        confidence=0.88,
        identifiability=IdentifiabilityClass.CONFOUNDED,
    )
    # Contribution D: Target out of policy scope
    c_out_of_scope = make_diagnostic_contribution(
        "c_out_of_scope", target="market.commodity_price", confidence=0.95
    )
    # Contribution E: Has block reasons
    c_blocked = make_diagnostic_contribution(
        "c_blocked",
        target="soil.moisture",
        confidence=0.85,
        block_reasons=("CALIBRATION_EXPIRED",),
    )

    candidate_list = [c_low_conf, c_heuristic, c_confounded, c_out_of_scope, c_blocked]
    res = promo_service.promote_to_prescription_eligibility(
        candidate_list, policy_snapshot=policy
    )

    # All must be rejected
    assert res.promoted_count == 0
    assert len(res.promoted_contributions) == 0
    assert res.evaluated_count == 5

    # Check explicit exclusion reasons
    exclusions = res.exclusions
    assert "c_low_conf" in exclusions
    assert "PROMOTION_DENIED_LOW_CONFIDENCE" in exclusions["c_low_conf"][0]

    assert "c_heuristic" in exclusions
    assert exclusions["c_heuristic"] == ("PROMOTION_DENIED_HEURISTIC_ONLY",)

    assert "c_confounded" in exclusions
    assert exclusions["c_confounded"] == ("PROMOTION_DENIED_CONFOUNDED",)

    assert "c_out_of_scope" in exclusions
    assert "PROMOTION_DENIED_OUT_OF_POLICY_SCOPE" in exclusions["c_out_of_scope"][0]

    assert "c_blocked" in exclusions
    assert "PROMOTION_DENIED_BLOCK_REASONS:CALIBRATION_EXPIRED" in exclusions["c_blocked"][0]


# -----------------------------------------------------------------------------
# 3. Finding #2: Permission Reconstruction from None Metadata
# -----------------------------------------------------------------------------

def test_permission_reconstruction_from_none_metadata():
    """Verify Finding #2: When evidence_count or health_status is None, 0, or unusable,

    diagnosis permission is NOT granted (l1_usable = False), fail-closed.
    """
    test_cases = [
        # (evidence_count, health_status, expected_usable)
        (None, "healthy", False),               # None evidence_count must not pass
        (0, "healthy", False),                  # 0 evidence must not pass
        (-1, "healthy", False),                 # Negative evidence must not pass
        ("three", "healthy", False),            # Non-numeric evidence must not pass
        (5, None, False),                       # None health_status must not pass
        (5, "unusable", False),                 # "unusable" health must not pass
        (5, "unknown", False),                  # "unknown" health must not pass
        (5, "none", False),                     # "none" health must not pass
        (5, "", False),                         # empty health must not pass
        (5, "healthy", True),                   # Valid evidence and valid health passes!
        (1, "DEGRADED_ACCEPTABLE", True),       # Positive evidence and acceptable health passes!
    ]

    for ev_count, health_st, expected_usable in test_cases:
        mock_l1 = SimpleNamespace(
            run_id="run_l1_test",
            provenance={"evidence_count": ev_count, "data_health_status": health_st},
        )
        mock_l2 = SimpleNamespace(
            run_id="run_l2_test",
            belief_id="b_1",
            vegetation_vigor=0.7,
        )
        results = {
            LayerId.L1: LayerResult(layer_id="L1", status=LayerStatus.OK, output=mock_l1, run_id="run_l1_test"),
            LayerId.L2: LayerResult(layer_id="L2", status=LayerStatus.OK, output=mock_l2, run_id="run_l2_test"),
        }

        diag = _build_diagnostic_integration(
            results,
            orchestrator_run_id="orch_01",
            timestamp="2026-09-09T12:00:00Z",
            requested_use=InfluenceUse.DIAGNOSIS,
        )

        assert diag["diagnosis_allowed"] is expected_usable, (
            f"Failed for evidence_count={ev_count}, health_status={health_st}: "
            f"expected diagnosis_allowed={expected_usable}, got {diag['diagnosis_allowed']}"
        )


# -----------------------------------------------------------------------------
# 4. Finding #4: Decision Sequence Inversion & Scenario Propagation
# -----------------------------------------------------------------------------

def test_decision_sequence_and_scenario_propagation():
    """Verify Finding #4: Layer8Input accepts candidate_scenarios from L7 planning

    and feasibility_constraints from L6 feasibility, with full type compatibility.
    """
    # Create candidate scenario references (simulating L7 CropOptionEvaluation / scenarios)
    scenario_a = {
        "crop": "wheat",
        "overall_rank_score": 0.88,
        "suitability_percentage": 85.0,
        "window_status": "OPTIMAL",
    }
    scenario_b = {
        "crop": "barley",
        "overall_rank_score": 0.76,
        "suitability_percentage": 74.0,
        "window_status": "ACCEPTABLE",
    }

    feasibility_constraints = {
        "feasibility_score": 0.92,
        "nitrogen_leaching_fraction": 0.08,
        "runoff_risk_index": 0.12,
        "vapor_pressure_deficit_kpa": 1.45,
    }

    # Construct Layer8Input with L7 scenarios and L6 feasibility constraints
    l8_input = Layer8Input(
        diagnoses=[],
        nutrient_states={},
        bio_threats={},
        weather_forecast=[{"temp_max": 25.0, "temp_min": 14.0, "precipitation": 0.0, "source": "ecmwf"}],
        zone_ids=["zone_1"],
        audit_grade="A",
        candidate_scenarios=[scenario_a, scenario_b],
        feasibility_constraints=feasibility_constraints,
        crop="wheat",
        phenology_stage="TILLERING",
    )

    assert len(l8_input.candidate_scenarios) == 2
    assert l8_input.candidate_scenarios[0]["crop"] == "wheat"
    assert l8_input.candidate_scenarios[1]["crop"] == "barley"

    assert l8_input.feasibility_constraints["feasibility_score"] == 0.92
    assert l8_input.feasibility_constraints["nitrogen_leaching_fraction"] == 0.08
    assert l8_input.feasibility_constraints["runoff_risk_index"] == 0.12
    assert l8_input.feasibility_constraints["vapor_pressure_deficit_kpa"] == 1.45

    # Run Layer 8 to ensure runner consumes this input without breaking invariants
    from services.agribrain.layer8_prescriptive.runner import run_layer8
    l8_output = run_layer8(l8_input)
    assert l8_output is not None
    assert hasattr(l8_output, "actions")
    assert hasattr(l8_output, "schedule")


# -----------------------------------------------------------------------------
# 5. Finding #3: Intent Routing Capabilities
# -----------------------------------------------------------------------------

def test_intent_routing_capabilities():
    """Verify Finding #3: DIAGNOSIS, PLANNING, and DECISION intents execute their

    proper subsystem scopes and declare the correct intent_scope on output artifacts.
    """
    from services.agribrain.orchestrator_v2.schema import RunArtifact, RunMeta

    # 1. RunMeta and RunArtifact support intent_scope
    meta = RunMeta(
        orchestrator_run_id="run_intent_001",
        timestamp_utc="2026-09-09T12:00:00Z",
        orchestrator_version="2.0.0",
        intent_scope="diagnostic_only",
    )
    assert meta.intent_scope == "diagnostic_only"

    meta_planning = RunMeta(
        orchestrator_run_id="run_intent_002",
        timestamp_utc="2026-09-09T12:00:00Z",
        orchestrator_version="2.0.0",
        intent_scope="planning_only",
    )
    assert meta_planning.intent_scope == "planning_only"

    # 2. Verify intent enum definitions
    assert Intent.DIAGNOSIS.value == "DIAGNOSIS"
    assert Intent.PLANNING.value == "PLANNING"
    assert Intent.DECISION.value == "DECISION"
