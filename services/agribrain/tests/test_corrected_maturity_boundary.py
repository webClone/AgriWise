from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from layer3_water.contracts import (
    HydrologyMode,
    IrrigationConstraints,
    IrrigationMethod,
    SoilObservationVector,
)
from layer3_water.et import DualKcEngine
from layer3_water.runner import WaterIntelligenceEngine
from layer3_water.soil import SoilProfileDatabase
from layer4_nutrients.optimization.engine import OptimizationEngine
from layer4_nutrients.photosynthesis_nue.engine import PhotosynthesisNUEEngine
from layer4_nutrients.salinity.engine import SalinityEngine
from layer4_nutrients.schema import Nutrient
from layer5_bio.visual_detection import VisualDetectionEngine
from layer3_decision.features.builder import build_decision_features
from layer3_decision.schema import PlotContext
from services.agribrain.scientific_contracts import (
    AUTHORITY_DIAGNOSTIC_NO_STATE_UPDATE,
    AUTHORITY_MACHINE_EXECUTION_APPROVED,
    ContractViolation,
    MechanismExpertContributionV3,
    ScientificStateEnvelopeV1,
    AuthorizedActionV1,
    PrescriptionAuthorizationEnvelopeV1,
)
from services.agribrain.diagnostic_integration import post_execution_audit
from services.agribrain.orchestrator_v2.run_schema import (
    _serialize_plan,
    artifact_to_run,
)
from services.agribrain.orchestrator_v2.chat_context_builder import (
    build_rich_chat_context,
)
from services.agribrain.scientific_contracts.prescription_authorization import (
    canonical_hash,
)
from services.agribrain.orchestrator_v2.schema import (
    GlobalQuality,
    LayerResult,
    LayerStatus,
    OrchestratorInput,
    RunArtifact,
    RunMeta,
)
from services.agribrain.common.plot_namespace import PlotNamespace


WEATHER = {
    "t_max_c": 35.0,
    "t_min_c": 20.0,
    "precipitation_mm": 0.0,
    "wind_speed_2m_m_s": 2.5,
    "rh_min_pct": 30.0,
    "rh_max_pct": 75.0,
    "net_radiation_mj_m2": 22.0,
}


def test_empty_water_inputs_fail_closed() -> None:
    with pytest.raises(ContractViolation, match="explicit weather observations"):
        WaterIntelligenceEngine.execute_pipeline(
            plot_id="plot-1",
            timestamp=datetime(2026, 8, 25, tzinfo=timezone.utc),
        )


def test_legacy_l3_does_not_reconstruct_rain_or_soil_moisture_from_stress() -> None:
    features = build_decision_features(
        SimpleNamespace(
            operational_signals={
                "water_deficit_severity": 0.9,
                "rain_available": False,
                "temp_available": False,
            },
            stress_summary={"WATER": 0.9},
            stress_detail={},
            phenology_stage="unknown",
            stage_specific_allowed=False,
            zone_status={},
            vegetation_status={},
        ),
        PlotContext(),
    )
    assert features.rain_available is False
    assert features.rain_sum_7d == 0.0
    assert features.rain_sum_14d == 0.0
    assert features.days_since_rain == 0
    assert features.soil_moisture_proxy == 0.5


def test_richards_request_never_mislabels_bucket_execution() -> None:
    state, _ = WaterIntelligenceEngine.execute_pipeline(
        plot_id="plot-1",
        timestamp=datetime(2026, 8, 25, tzinfo=timezone.utc),
        weather_observations=WEATHER,
        requested_hydrology_mode=HydrologyMode.RICHARDS_1D,
    )
    assert state.hydrology_mode == HydrologyMode.FAO56_LAYERED_BUCKET
    assert state.solver_fidelity.value == "EMPIRICAL_BUCKET"


def test_zero_allocation_forces_hold() -> None:
    dry_soil = SoilProfileDatabase.get_canonical_soil_profile(
        soil_type="loam", initial_saturation_fraction=0.2,
    )
    state, _ = WaterIntelligenceEngine.execute_pipeline(
        plot_id="plot-1",
        timestamp=datetime(2026, 8, 25, tzinfo=timezone.utc),
        weather_observations=WEATHER,
        soil_profile_state=dry_soil,
        irrigation_method=IrrigationMethod.DRIP,
        irrigation_constraints=IrrigationConstraints(allocation_remaining_mm=0.0),
    )
    assert state.active_decision.action.value == "HOLD"
    assert state.active_decision.recommended_gross_mm == 0.0


def test_assimilation_recomputes_fluxes_from_posterior_ks() -> None:
    prior = SoilProfileDatabase.get_canonical_soil_profile(
        soil_type="loam", initial_saturation_fraction=0.8,
    )
    observations = SoilObservationVector(
        timestamp=datetime(2026, 8, 25, tzinfo=timezone.utc),
        soil_probe_moisture_profile=[0.09, 0.10, 0.11, 0.12, 0.13],
        observation_uncertainties={"soil_probe": 0.005},
    )
    state, _ = WaterIntelligenceEngine.execute_pipeline(
        plot_id="plot-1",
        timestamp=datetime(2026, 8, 25, tzinfo=timezone.utc),
        weather_observations=WEATHER,
        soil_profile_state=prior,
        soil_observations=observations,
    )
    # Under F03: realized fluxes over the completed interval are preserved from the transition receipt
    # rather than retroactively rewritten by assimilation; posterior root-zone reflects the new post-assimilation state
    assert state.root_zone.stress_factor_ks == 0.0
    assert state.fluxes.actual.ks == 0.956
    assert state.fluxes.actual.ks != state.root_zone.stress_factor_ks
    assert state.transition_receipt is not None


def test_fao56_ke_uses_upper_bound_minimum() -> None:
    ke, _ = DualKcEngine.calculate_soil_evaporation_ke(
        kcb=0.8,
        kc_max=1.2,
        fvc=0.5,
        surface_storage_mm=12.0,
    )
    assert ke == pytest.approx(0.4)


def test_n_concentration_and_requirement_units() -> None:
    result = PhotosynthesisNUEEngine().analyze(
        crop_type="wheat",
        lai_current=2.0,
        fpar_current=0.5,
        npp_g_c_m2_day=0.0,
        n_applied_kg_ha=0.0,
        soil_n_supply_kg_ha=30.0,
    )
    expected_pct = (30.0 * 0.60) / (result.estimated_biomass_t_ha * 10.0)
    assert result.actual_n_pct == pytest.approx(expected_pct, abs=0.01)
    assert result.actual_n_pct < 10.0
    assert result.optimal_n_rate_kg_ha < 300.0


def test_sustainable_optimization_receives_water_balance() -> None:
    rate, _, _ = OptimizationEngine()._compute_optimal_rate(
        Nutrient.N,
        "corn",
        "sustainable",
        {},
        SimpleNamespace(leaching_risk_index=0.8),
    )
    assert rate >= 0.0


def test_asmae_pressure_is_not_promoted_to_ece_and_sar_uses_mmol_units() -> None:
    pressure_only = SalinityEngine().assess_salinity_impact(
        ec_ds_m=0.0,
        inferred_salinity_pressure=0.8,
    )
    assert pressure_only.ec_ds_m == 0.0
    assert pressure_only.salinity_source == "unavailable"
    assert pressure_only.severity_class == "UNKNOWN"
    assert pressure_only.sodicity_risk == "UNKNOWN"
    assert "not assessed" in pressure_only.notes.lower()
    ions = SalinityEngine().assess_salinity_impact(
        ec_ds_m=2.0,
        na_mmol=10.0,
        ca_mmol=4.0,
        mg_mmol=5.0,
    )
    assert ions.sar == pytest.approx(10.0 / 3.0, abs=0.01)


def test_unvalidated_vision_abstains() -> None:
    result = VisualDetectionEngine().analyze_image(None, {})
    assert result["status"] == "unavailable"
    assert result["authority"] == "VISUALIZATION_ONLY_NO_DIAGNOSIS"


def test_post_execution_audit_uses_runtime_ingest_and_finalize() -> None:
    result = post_execution_audit({
        "run_id": "run-1",
        "L2": SimpleNamespace(
            run_id="l2-run",
            anomalies=[],
            health_index=SimpleNamespace(
                overall_score=0.7,
                ndvi_health=0.8,
                water_stress_index=0.2,
                vigor_trend="STABLE",
                confidence=0.75,
            ),
        ),
    })
    assert result.input_belief_id == "run-1"
    assert result.influence_manifest.entries


def test_transition_contracts_are_immutable_and_diagnostic_only() -> None:
    envelope = ScientificStateEnvelopeV1(
        belief_id="belief-1",
        worldline_head="event-10",
        X_refs=("asmae-state-1", "l3-water-state-1"),
        Z_ref=None,
        H_distribution={"WATER_LIMITATION": 0.6, "UNRESOLVED": 0.4},
        M_refs=("plot-worldline-1",),
        U={
            "uncertainty": {"water": 0.2},
            "missingness": ["soil_probe"],
            "ood_status": "IN_DOMAIN",
            "limitations": ["diagnostic_only"],
        },
        geometry_version="geom-v3",
        evidence_cutoff="2026-08-25T00:00:00+00:00",
        authority_vector=AUTHORITY_DIAGNOSTIC_NO_STATE_UPDATE,
    )
    assert envelope.Z_ref is None
    assert envelope.to_dict()["H_distribution"]["UNRESOLVED"] == 0.4
    with pytest.raises(TypeError):
        envelope.U["ood_status"] = "OOD"

    contribution = MechanismExpertContributionV3(
        expert_id="water-balance",
        expert_version="1.0.0",
        input_belief_id="belief-1",
        target_state="root_zone.water_availability",
        support=0.7,
        contradiction=0.1,
        unknown=0.2,
        evidence_ids=("weather-1", "soil-1"),
        dependency_families=("WEATHER", "SOIL"),
        confounders=("salinity",),
        alternative_hypotheses=("ROOT_DAMAGE",),
        applicability_domain={"soil_types": ["loam"]},
        ood_status="IN_DOMAIN",
        predicted_observables={"probe_vwc_change": "decrease"},
        next_discriminating_measurements=("root_zone_probe",),
        uncertainty={"epistemic": 0.2},
        authority=AUTHORITY_DIAGNOSTIC_NO_STATE_UPDATE,
    )
    assert contribution.to_dict()["unknown"] == 0.2
    with pytest.raises(ContractViolation, match="diagnostic-only"):
        MechanismExpertContributionV3(
            **{
                **{
                    key: getattr(contribution, key)
                    for key in contribution.__dataclass_fields__
                    if key not in {"authority", "content_hash"}
                },
                "authority": AUTHORITY_MACHINE_EXECUTION_APPROVED,
            }
        )


def _artifact_with_shadow_l4_rate() -> RunArtifact:
    namespace = PlotNamespace(tenant_id="tenant-1", farm_id="farm-1", plot_id="plot-1")
    inputs = OrchestratorInput(
        plot_namespace=namespace,
        geometry_hash="geometry-1",
        date_range={"start": "2026-08-18", "end": "2026-08-25"},
        policy_snapshot={"policy": "reviewed-v1"},
    )
    l4_output = SimpleNamespace(prescriptions=[SimpleNamespace(
        action_id="APPLY_N",
        rate_kg_ha=130.5,
        timing_window=SimpleNamespace(start_date="2026-08-26", end_date="2026-08-27"),
        is_allowed=True,
    )])
    return RunArtifact(
        meta=RunMeta(orchestrator_run_id="run-1"),
        inputs=inputs,
        global_quality=GlobalQuality(
            modes=[], reliability_score=0.8, missing_drivers=[], critical_errors=[]
        ),
        layer_4=LayerResult(
            layer_id="L4", status=LayerStatus.OK, output=l4_output, run_id="l4-1"
        ),
        final_execution_plan=SimpleNamespace(tasks=[], edges=[]),
    )


def test_farmer_serializer_never_reconstructs_shadow_l4_rate() -> None:
    artifact = _artifact_with_shadow_l4_rate()
    layer10_detail = {
        "timestamp": "2026-08-25T00:00:00+00:00",
        "zones": [{
            "zone_id": "zone-1",
            "severity": 0.7,
            "linked_actions": [{"action": "APPLY_N", "rate_kg_ha": 130.5}],
        }],
        "scenario_pack": [{"recommendation": "APPLY_N 130.5 kg/ha"}],
        "history_pack": [{"scheduled_action": "APPLY_N 130.5 kg/ha"}],
        "explainability_pack": {
            "diagnostic_summary": "Possible nutrient stress",
            "recommended_rate_kg_ha": 130.5,
        },
    }
    surfaces = [{
        "type": "NDVI",
        "values": [[0.3]],
        "linked_actions": [{"action": "APPLY_N", "rate_kg_ha": 130.5}],
    }]
    serialized = artifact_to_run(
        artifact, surfaces=surfaces, layer10_detail=layer10_detail
    )
    assert serialized["recommendations"] == []
    assert serialized["unified_plan"]["tasks"] == []
    assert serialized["audit"]["prescription_authorization"]["status"] == "BLOCKED"
    assert serialized["scenario_pack"] == []
    assert serialized["history_pack"] == []
    assert "linked_actions" not in serialized["zones"][0]
    assert "linked_actions" not in serialized["surfaces"][0]
    assert serialized["explainability_pack"]["diagnostic_summary"] == "Possible nutrient stress"
    assert "130.5" not in str(serialized)

    prompt_context = build_rich_chat_context(
        artifact, user_mode="farmer", user_query="What fertilizer action should I take?"
    )
    assert "130.5" not in prompt_context
    assert "BLOCKED: no exact action" in prompt_context


def test_farmer_serializer_accepts_only_exact_lineage_bound_l8_envelope() -> None:
    artifact = _artifact_with_shadow_l4_rate()
    plan = SimpleNamespace(
        tasks=[SimpleNamespace(
            task_id="task-1",
            type="FERTILIZE",
            instructions="Apply the authorized dose",
            required_inputs=[],
            completion_signal="confirmed",
            depends_on=[],
            target_zones=["plot"],
            target_points=[],
        )],
        edges=[],
        recommended_start_date="2026-08-26",
        review_date="2026-08-27",
    )
    artifact.final_execution_plan = plan
    digest = lambda value: canonical_hash({"value": value})
    tribunal_hash = digest("tribunal")
    manifest_hash = digest("manifest")
    l8_hash = digest("l8-output")
    action = AuthorizedActionV1(
        action_id="l8-action-1",
        action_type="FERTILIZE",
        priority_score=0.82,
        urgency_score=0.80,
        confidence="MODERATE",
        rationale="L8 selected this dose from promoted evidence",
        rate={"recommended": 42.0, "min_safe": 35.0, "max_safe": 48.0, "unit": "kg_N/ha"},
        timing={
            "earliest": "2026-08-26", "latest": "2026-08-27", "optimal": None
        },
        zone_targets=("plot",),
    )
    envelope = PrescriptionAuthorizationEnvelopeV1(
        input_belief_id="belief-1",
        tribunal_content_hash=tribunal_hash,
        prescription_manifest_hash=manifest_hash,
        prescription_manifest_entry_ids=("DC-L4-1",),
        policy_snapshot_hash=canonical_hash(artifact.inputs.policy_snapshot),
        l8_run_id="l8-1",
        l8_content_hash=l8_hash,
        final_execution_plan_hash=canonical_hash(_serialize_plan(plan)),
        actions=(action,),
    )
    l8_action = SimpleNamespace(
        action_id="l8-action-1",
        action_type=SimpleNamespace(value="FERTILIZE"),
        priority_score=0.82,
        priority_breakdown=SimpleNamespace(urgency_score=0.80),
        confidence=SimpleNamespace(value="MODERATE"),
        explain="L8 selected this dose from promoted evidence",
        rate=SimpleNamespace(
            recommended=42.0, min_safe=35.0, max_safe=48.0, unit="kg_N/ha"
        ),
        time_window=SimpleNamespace(
            earliest="2026-08-26", latest="2026-08-27", optimal=None
        ),
        zone_targets=["plot"],
        requires_confirmation=True,
    )
    l8_output = SimpleNamespace(
        run_id="l8-1",
        actions=[l8_action],
        authorization_envelope=envelope.to_dict(),
        audit=SimpleNamespace(policy_checks=[{"check": "content_hash", "value": l8_hash}]),
    )
    artifact.layer_8 = LayerResult(
        layer_id="L8", status=LayerStatus.OK, output=l8_output, run_id="l8-1"
    )
    artifact.diagnostic_integration = {
        "prescription_gate": {
            "status": "completed",
            "input_belief_id": "belief-1",
            "tribunal_verdict": {"content_hash": tribunal_hash},
            "influence_manifest": {
                "requested_use": "PRESCRIPTION_DRIVER",
                "content_hash": manifest_hash,
                "entries": [{"contribution_id": "DC-L4-1"}],
            },
        }
    }

    serialized = artifact_to_run(artifact)
    assert [item["action_id"] for item in serialized["recommendations"]] == ["l8-action-1"]
    assert serialized["recommendations"][0]["rate"]["recommended"] == 42.0
    assert serialized["unified_plan"]["total_tasks"] == 1
    assert serialized["audit"]["prescription_authorization"]["status"] == "AUTHORIZED"

    artifact.diagnostic_integration["prescription_gate"]["influence_manifest"]["content_hash"] = digest("tampered")
    blocked = artifact_to_run(artifact)
    assert blocked["recommendations"] == []
    assert blocked["unified_plan"]["tasks"] == []
