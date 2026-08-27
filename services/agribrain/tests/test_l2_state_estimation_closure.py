"""
Layer 2 State Estimation Closure & Contracts Verification Suite.

Validates:
1. Canonical contracts (StressMagnitudeState, StressHypothesisState, StressImpactEstimate, VegetationState, UncertaintyBudget, InferenceProvenance).
2. Strict continuous probability simplex sum_{H} P(H | E) = 1.0.
3. Quadratic quadrature uncertainty budget sigma_total = sqrt(sigma_s^2 + sigma_r^2 + sigma_c^2 + sigma_m^2).
4. Jacobian retrieval models (NDMI, Temperature, Salinity).
5. Bounded environmentally-modulated compound synergy beta in [1.0, 1.95].
6. Smooth sigmoid damage probability and raw impact preservation.
7. Unknown vegetation strict authority gating (impact_authority = UNAVAILABLE).
"""

from __future__ import annotations

import math
from datetime import datetime
import pytest

from layer2_contracts.state_contracts import (
    CropKnowledgeAuthority,
    InferenceMode,
    PhysicalSourceType,
    UncertaintyBudget,
    StressMagnitudeState,
    StressHypothesisState,
    StressImpactEstimate,
    InferenceProvenance,
    VegetationState,
    CANONICAL_HYPOTHESES,
)
from layer2_uncertainty.retrieval_models import (
    NDMIWaterStressModel,
    TemperatureThermalStressModel,
    SalinityECModel,
    UncertaintyPropagator,
)
from layer2_intelligence.schemas import StressEvidence, CropCycleContext, DataHealthScore
from layer2_intelligence.stress_attributor import attribute_stress
from layer2_intelligence.phenology_adjuster import adjust_stress_for_phenology
from layer2_veg_int.crop_response_profile import CropParameterResolver
from layer2_veg_int.schema import PhenologyStage


def test_canonical_uncertainty_budget_quadratic_quadrature():
    """Invariant: UncertaintyBudget computes sigma_total = sqrt(sum sigma_i^2) exactly."""
    budget = UncertaintyBudget(
        sensor_sigma=0.03,
        retrieval_sigma=0.04,
        conflict_sigma=0.00,
        model_sigma=0.00,
    )
    # sqrt(0.03^2 + 0.04^2) = 0.05
    assert budget.total_sigma == 0.05

    budget4 = UncertaintyBudget(
        sensor_sigma=0.02,
        retrieval_sigma=0.04,
        conflict_sigma=0.03,
        model_sigma=0.05,
    )
    # sqrt(0.0004 + 0.0016 + 0.0009 + 0.0025) = sqrt(0.0054) = 0.0735
    expected = round(math.sqrt(0.02**2 + 0.04**2 + 0.03**2 + 0.05**2), 4)
    assert budget4.total_sigma == expected


def test_jacobian_retrieval_models():
    """Invariant: Analytical Jacobians correctly scale retrieval uncertainty."""
    # NDMI model: S_W = 0.3 + (0.2 - (-0.1)) * 2.0 = 0.90, Jacobian = 2.0
    val_w, sigma_w = NDMIWaterStressModel.evaluate(ndmi=-0.10, sigma_ndmi=0.03)
    assert val_w == 0.90
    assert sigma_w == round(2.0 * 0.03, 4)

    # Thermal model: T=40.0, VPD=3.5
    val_t, sigma_t = TemperatureThermalStressModel.evaluate(temp_max=40.0, vpd=3.5, sigma_temp=0.4, sigma_vpd=0.1)
    assert val_t > 0.0
    assert sigma_t > 0.0

    # Salinity model: EC=6.0
    val_s, sigma_s = SalinityECModel.evaluate(soil_ec=6.0, sigma_ec=0.2)
    assert val_s > 0.0
    assert sigma_s > 0.0


def test_continuous_probability_simplex_sum_to_one():
    """Invariant: StressHypothesisState strictly satisfies sum P(H | E) = 1.0."""
    hyp_state = StressHypothesisState(
        posteriors={
            "WATER": 0.40,
            "THERMAL": 0.20,
            "NUTRIENT": 0.10,
            "SALINITY": 0.05,
            "BIOTIC": 0.05,
            "UNRESOLVED": 0.20,
        }
    )
    assert round(sum(hyp_state.posteriors.values()), 3) == 1.0
    assert hyp_state.dominant_hypothesis == "WATER"
    assert hyp_state.dominant_probability == 0.40
    assert hyp_state.epistemic_entropy > 0.0


def test_environmentally_modulated_compound_synergy_bounds():
    """Invariant: Compound synergy beta(c, z, pair, env) is strictly bounded in [1.0, 1.95]."""
    maize_prof = CropParameterResolver.resolve("maize")
    
    # Normal environment
    beta_norm = maize_prof.get_compound_synergy(
        PhenologyStage.REPRODUCTIVE, "WATER", "THERMAL",
        env_context={"temp_max": 32.0, "vpd": 2.0},
    )
    # Extreme environment: T=42C, VPD=4.5kPa
    beta_ext = maize_prof.get_compound_synergy(
        PhenologyStage.REPRODUCTIVE, "WATER", "THERMAL",
        env_context={"temp_max": 42.0, "vpd": 4.5},
    )
    
    assert beta_ext >= beta_norm
    assert 1.0 <= beta_norm <= 1.95
    assert 1.0 <= beta_ext <= 1.95


def test_smooth_damage_probability_and_raw_impact_preservation():
    """Invariant: Extreme compound stress records raw_biological_impact > 1.0 and smooth sigmoid damage probability."""
    item = StressEvidence(
        stress_id="w_ext",
        stress_type="WATER",
        severity=0.85,
        stress_magnitude=0.85,
        magnitude_uncertainty=0.06,
        compound_partner="THERMAL",
        compound_synergy_factor=1.50,
        confidence=0.85,
    )
    cycle = CropCycleContext(crop_type="maize", current_stage="REPRODUCTIVE")
    
    res = adjust_stress_for_phenology([item], cycle)[0]
    
    # Invariant: Raw biological impact is preserved without saturation loss
    assert res.raw_biological_impact > 1.0
    assert res.normalized_impact == 1.0  # Clipped index
    assert res.biological_impact == 1.0  # Backwards compatibility alias
    assert 0.0 < res.damage_probability <= 1.0
    assert res.impact_uncertainty is not None
    assert res.impact_uncertainty > 0.0
    assert res.impact_authority in ("TRANSFERRED", "CALIBRATED")


def test_unknown_vegetation_strict_authority_gating():
    """Invariant: UNKNOWN_VEGETATION has impact_authority = UNAVAILABLE and damage_probability = 0.0."""
    item = StressEvidence(
        stress_id="w_unk",
        stress_type="WATER",
        severity=0.70,
        stress_magnitude=0.70,
        magnitude_uncertainty=0.08,
    )
    profile_unk = CropParameterResolver.resolve("UNKNOWN_VEGETATION")
    cycle_unk = CropCycleContext(crop_type="UNKNOWN_VEGETATION", current_stage="REPRODUCTIVE")
    cycle_unk.crop_response_profile = profile_unk

    res = adjust_stress_for_phenology([item], cycle_unk)[0]
    
    assert res.impact_authority == "UNAVAILABLE"
    assert res.damage_probability == 0.0
    assert res.impact_uncertainty is None
    assert res.diagnostic_only is True
    assert "UNKNOWN_VEGETATION_UNCONDITIONED" in res.flags


def test_unified_vegetation_state_instantiation():
    """Invariant: VegetationState encapsulates full X_t^L2 state with provenance."""
    unc = UncertaintyPropagator.build_budget(sensor_sigma=0.02, retrieval_sigma=0.03, conflict_penalty=0.0, model_sigma=0.02)
    mag_state = StressMagnitudeState(
        stress_type="WATER",
        value=0.55,
        uncertainty=unc,
        source=PhysicalSourceType.DERIVED,
        primary_sensor_evidence=["S2_NDMI", "ERA5_VPD"],
    )
    hyp_state = StressHypothesisState(
        posteriors={"WATER": 0.50, "THERMAL": 0.20, "NUTRIENT": 0.10, "SALINITY": 0.05, "BIOTIC": 0.05, "UNRESOLVED": 0.10}
    )
    imp_state = StressImpactEstimate(
        stress_type="WATER",
        raw_impact=0.75,
        normalized_impact=0.75,
        damage_probability=0.54,
        impact_uncertainty=0.05,
        crop_authority=CropKnowledgeAuthority.TRANSFERRED,
    )
    prov = InferenceProvenance(
        model_version="4.2.0",
        crop_profile_version="4.0.0",
        data_sources=["Sentinel-2", "ERA5-Land"],
        observation_count=6,
        authority_level=CropKnowledgeAuthority.TRANSFERRED,
        inference_mode=InferenceMode.ONLINE,
        execution_timestamp=datetime.now(),
    )
    veg_state = VegetationState(
        plot_id="plot_state_001",
        timestamp=datetime.now(),
        development_time=450.0,
        phenology_stage="REPRODUCTIVE",
        stage_progress_fraction=0.62,
        crop_authority=CropKnowledgeAuthority.TRANSFERRED,
        lai=3.4,
        fvc=0.78,
        fpar=0.72,
        biomass_proxy=520.0,
        physical_stress_states={"WATER": mag_state},
        diagnostic_hypothesis_state=hyp_state,
        biological_impact_states={"WATER": imp_state},
        data_health_score=0.92,
        provenance=prov,
    )

    assert veg_state.plot_id == "plot_state_001"
    assert veg_state.lai == 3.4
    assert veg_state.crop_authority == CropKnowledgeAuthority.TRANSFERRED
    assert veg_state.physical_stress_states["WATER"].value == 0.55
    assert veg_state.diagnostic_hypothesis_state.dominant_hypothesis == "WATER"
    assert veg_state.biological_impact_states["WATER"].damage_probability == 0.54
    assert veg_state.biological_impact_states["WATER"].biological_impact == 0.75
    assert veg_state.provenance.inference_mode == InferenceMode.ONLINE


def test_stress_factories_canonical_construction():
    """Invariant: StressEvidenceFactory and StressStateFactory construct fully normalized state contracts."""
    from layer2_contracts import StressStateFactory
    from layer2_intelligence.schemas import StressEvidenceFactory
    
    # 1. StressEvidenceFactory
    ev = StressEvidenceFactory.create(
        stress_id="test_ev_001",
        stress_type="water",
        severity=0.65,
        confidence=0.80,
        uncertainty=0.08,
        raw_biological_impact=1.25,
        damage_probability=0.84,
    )
    assert ev.stress_type == "WATER"
    assert ev.raw_biological_impact == 1.25
    assert ev.normalized_impact == 1.0  # Clipped index
    assert ev.biological_impact == 1.0  # Backwards compatibility alias
    assert ev.damage_probability == 0.84

    # 2. StressStateFactory
    budget = UncertaintyBudget(0.02, 0.03, 0.0, 0.02)
    mag = StressStateFactory.create_magnitude_state("water", 0.72, budget)
    assert mag.stress_type == "WATER"
    assert mag.value == 0.72

    imp = StressStateFactory.create_impact_estimate("water", raw_impact=1.40, damage_probability=0.88, impact_uncertainty=0.06)
    assert imp.raw_impact == 1.40
    assert imp.normalized_impact == 1.0
    assert imp.damage_probability == 0.88


def test_vegetation_state_transition_model_hydraulic_inertia():
    """Invariant: VegetationStateTransitionModel enforces temporal stress inertia and Markov hypothesis update."""
    from layer2_contracts.state_transition import VegetationStateTransitionModel
    
    # Yesterday: severe water stress S=0.80
    prev_budget = UncertaintyBudget(0.02, 0.03, 0.0, 0.02)
    prev_mag = StressMagnitudeState("WATER", 0.80, prev_budget, PhysicalSourceType.DERIVED)
    prev_hyp = StressHypothesisState(posteriors={"WATER": 0.75, "THERMAL": 0.05, "NUTRIENT": 0.05, "SALINITY": 0.05, "BIOTIC": 0.02, "UNRESOLVED": 0.08})
    prev_imp = StressImpactEstimate("WATER", raw_impact=0.90, normalized_impact=0.90, damage_probability=0.65, impact_uncertainty=0.05)
    
    prev_state = VegetationState(
        plot_id="plot_trans_01",
        timestamp=datetime(2026, 6, 10, 10, 0),
        development_time=300.0,
        lai=2.5,
        fvc=0.60,
        fpar=0.55,
        biomass_proxy=400.0,
        physical_stress_states={"WATER": prev_mag},
        diagnostic_hypothesis_state=prev_hyp,
        biological_impact_states={"WATER": imp_state if 'imp_state' in locals() else prev_imp},
    )

    # Today: NDMI temporarily returns 0.0 (e.g. sensor artifact or light cloud) without rain
    current_obs_mag = StressMagnitudeState("WATER", 0.0, prev_budget, PhysicalSourceType.DERIVED)
    current_obs = {
        "physical_stress_states": {"WATER": current_obs_mag},
        "lai": 2.5,
        "fvc": 0.60,
        "fpar": 0.55,
    }

    next_state = VegetationStateTransitionModel.step_state(
        prev_state=prev_state,
        current_observations=current_obs,
        delta_gdd=15.0,
        dt_days=1.0,
        weather_context={"precip_mm": 0.0},
    )

    # Invariant: Physical water stress S does NOT instantly jump to 0.0 without rain
    assert next_state.physical_stress_states["WATER"].value > 0.40  # Preserves ~0.52 via inertia
    assert next_state.development_time == 315.0
    assert next_state.diagnostic_hypothesis_state.dominant_hypothesis == "WATER"
    assert round(sum(next_state.diagnostic_hypothesis_state.posteriors.values()), 3) == 1.0
