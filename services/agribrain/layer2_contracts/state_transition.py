"""
Layer 2 Vegetation State Transition Dynamics Engine.

Implements the dynamic temporal state transition model:
    P(X_t^L2 | X_{t-1}^L2, Weather_t, Crop_Context)

Scientific Basis (Sinclair & Seligman 1996, Hsiao 1973, Tardieu 2013):
1. Biological Development Persistence:
   D_t = D_{t-1} + Delta_GDD_t * f_stress(S_{t-1})
2. Physical Stress Inertia (Hydraulic & Tissue Recovery Lag):
   S_{k, t} = alpha_k * S_{k, t-1} + (1 - alpha_k) * S_{k, obs, t}
   where alpha_k in [0.50, 0.85] prevents unphysical instantaneous drops (e.g. 0.8 -> 0.0).
3. Diagnostic Hypothesis Markov Prior P(H_t | H_{t-1}):
   T_{j, k} captures persistence of agricultural stress states across consecutive timesteps.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .state_contracts import (
    CropKnowledgeAuthority,
    InferenceMode,
    PhysicalSourceType,
    StressMagnitudeState,
    StressHypothesisState,
    StressImpactEstimate,
    UncertaintyBudget,
    InferenceProvenance,
    VegetationState,
    CANONICAL_HYPOTHESES,
)


# Default physical persistence factors alpha_k per stress type
DEFAULT_STRESS_PERSISTENCE = {
    "WATER": 0.65,       # Soil-plant hydraulic capacitance recovery lag
    "THERMAL": 0.40,     # Faster cooling relaxation once heatwave breaks
    "NUTRIENT": 0.85,    # High inertia, soil mineralization / uptake is slow
    "SALINITY": 0.90,    # Very high inertia without leaching
    "BIOTIC": 0.75,      # Pest/pathogen population persistence
    "UNRESOLVED": 0.50,  # Unexplained residual persistence
}

# Canonical Markov transition matrix T[from_hyp, to_hyp]
DEFAULT_TRANSITION_MATRIX: Dict[str, Dict[str, float]] = {
    "WATER": {
        "WATER": 0.70, "THERMAL": 0.10, "NUTRIENT": 0.05,
        "SALINITY": 0.05, "BIOTIC": 0.03, "UNRESOLVED": 0.07,
    },
    "THERMAL": {
        "WATER": 0.20, "THERMAL": 0.60, "NUTRIENT": 0.03,
        "SALINITY": 0.02, "BIOTIC": 0.05, "UNRESOLVED": 0.10,
    },
    "NUTRIENT": {
        "WATER": 0.05, "THERMAL": 0.02, "NUTRIENT": 0.80,
        "SALINITY": 0.03, "BIOTIC": 0.03, "UNRESOLVED": 0.07,
    },
    "SALINITY": {
        "WATER": 0.08, "THERMAL": 0.02, "NUTRIENT": 0.05,
        "SALINITY": 0.80, "BIOTIC": 0.01, "UNRESOLVED": 0.04,
    },
    "BIOTIC": {
        "WATER": 0.05, "THERMAL": 0.03, "NUTRIENT": 0.04,
        "SALINITY": 0.01, "BIOTIC": 0.75, "UNRESOLVED": 0.12,
    },
    "UNRESOLVED": {
        "WATER": 0.20, "THERMAL": 0.15, "NUTRIENT": 0.15,
        "SALINITY": 0.10, "BIOTIC": 0.15, "UNRESOLVED": 0.25,
    },
}


class VegetationStateTransitionModel:
    """State transition operator F(X_{t-1}, Weather_t, dt) for Bayesian state estimation."""

    @staticmethod
    def transition_stress_magnitude(
        prev_magnitude: float,
        obs_magnitude: float,
        stress_type: str,
        dt_days: float = 1.0,
        irrigation_or_rain_mm: float = 0.0,
    ) -> Tuple[float, float]:
        """Apply hydraulic inertia to compute S_k(t) from S_k(t-1) and S_k,obs(t).
        
        Returns:
            (predicted_magnitude, inertia_applied_fraction)
        """
        alpha_base = DEFAULT_STRESS_PERSISTENCE.get(stress_type.upper(), 0.60)
        
        # Exponential decay of persistence over longer time gaps
        alpha = alpha_base ** max(0.5, dt_days)
        
        # Substantial rain/irrigation breaks water stress inertia faster
        if stress_type.upper() == "WATER" and irrigation_or_rain_mm > 15.0:
            alpha = max(0.15, alpha * 0.40)

        s_trans = alpha * prev_magnitude + (1.0 - alpha) * obs_magnitude
        return round(min(1.0, max(0.0, s_trans)), 3), round(alpha, 3)

    @staticmethod
    def transition_hypothesis_prior(
        prev_hypothesis_state: StressHypothesisState,
        dt_days: float = 1.0,
    ) -> StressHypothesisState:
        """Compute prior hypothesis simplex P(H_t | H_{t-1}) using transition Markov matrix."""
        prev_p = prev_hypothesis_state.posteriors
        new_p: Dict[str, float] = {h: 0.0 for h in CANONICAL_HYPOTHESES}

        for from_h, p_from in prev_p.items():
            t_row = DEFAULT_TRANSITION_MATRIX.get(from_h, DEFAULT_TRANSITION_MATRIX["UNRESOLVED"])
            for to_h in CANONICAL_HYPOTHESES:
                prob_trans = t_row.get(to_h, 1.0 / len(CANONICAL_HYPOTHESES))
                # Diffuse transitions if time gap is long
                if dt_days > 3.0:
                    prob_trans = 0.5 * prob_trans + 0.5 * (1.0 / len(CANONICAL_HYPOTHESES))
                new_p[to_h] += p_from * prob_trans

        # Normalize to strict simplex
        tot = sum(new_p.values())
        if tot > 0:
            new_p = {k: round(v / tot, 4) for k, v in new_p.items()}

        return StressHypothesisState(posteriors=new_p)

    @classmethod
    def step_state(
        cls,
        prev_state: VegetationState,
        current_observations: Dict[str, Any],
        delta_gdd: float,
        dt_days: float = 1.0,
        weather_context: Optional[Dict[str, float]] = None,
    ) -> VegetationState:
        """Propagate state vector X_{t-1} -> X_t incorporating dynamic transitions and current observations."""
        weather_context = weather_context or {}
        precip = weather_context.get("precip_mm", 0.0) or 0.0

        # 1. Propagate development coordinate D_t
        new_dev_time = prev_state.development_time + max(0.0, delta_gdd)
        new_stage_frac = min(1.0, prev_state.stage_progress_fraction + (delta_gdd / 1200.0 if delta_gdd > 0 else 0.0))

        # 2. Propagate physical canopy metrics with relaxation
        obs_lai = current_observations.get("lai", prev_state.lai)
        obs_fvc = current_observations.get("fvc", prev_state.fvc)
        obs_fpar = current_observations.get("fpar", prev_state.fpar)
        
        # Smooth canopy state with temporal inertia
        smooth_lai = round(0.70 * prev_state.lai + 0.30 * obs_lai, 2)
        smooth_fvc = round(0.70 * prev_state.fvc + 0.30 * obs_fvc, 2)
        smooth_fpar = round(0.70 * prev_state.fpar + 0.30 * obs_fpar, 2)
        smooth_biomass = round(prev_state.biomass_proxy + max(0.0, smooth_fpar * delta_gdd * 0.8), 1)

        # 3. Propagate physical stress states with hydraulic inertia
        obs_stresses = current_observations.get("physical_stress_states", {})
        new_physical_stresses: Dict[str, StressMagnitudeState] = {}

        all_stress_types = set(prev_state.physical_stress_states.keys()) | set(obs_stresses.keys())
        for stype in all_stress_types:
            prev_s = prev_state.physical_stress_states.get(stype)
            obs_s = obs_stresses.get(stype)
            
            prev_val = prev_s.value if prev_s else 0.0
            obs_val = obs_s.value if obs_s else 0.0
            
            s_val, alpha = cls.transition_stress_magnitude(
                prev_val, obs_val, stype, dt_days=dt_days, irrigation_or_rain_mm=precip,
            )
            
            # Kalman-style uncertainty propagation through transition:
            # sigma_t^2 = alpha^2 * sigma_{t-1}^2 + (1-alpha)^2 * sigma_{obs}^2 + Q_process
            prev_u = prev_s.uncertainty if prev_s else UncertaintyBudget(0.02, 0.03, 0.0, 0.02)
            obs_u = obs_s.uncertainty if obs_s else UncertaintyBudget(0.02, 0.03, 0.0, 0.02)
            
            q_proc = 0.015 * min(3.0, dt_days)  # Process model noise accumulation
            trans_sensor_sigma = round(math.sqrt((alpha * prev_u.sensor_sigma)**2 + ((1.0 - alpha) * obs_u.sensor_sigma)**2), 4)
            trans_retrieval_sigma = round(math.sqrt((alpha * prev_u.retrieval_sigma)**2 + ((1.0 - alpha) * obs_u.retrieval_sigma)**2), 4)
            trans_conflict_sigma = round(max(prev_u.conflict_sigma * alpha, obs_u.conflict_sigma), 4)
            trans_model_sigma = round(math.sqrt((alpha * prev_u.model_sigma)**2 + ((1.0 - alpha) * obs_u.model_sigma)**2 + q_proc**2), 4)

            unc = UncertaintyBudget(
                sensor_sigma=trans_sensor_sigma,
                retrieval_sigma=trans_retrieval_sigma,
                conflict_sigma=trans_conflict_sigma,
                model_sigma=trans_model_sigma,
            )
            ev = obs_s.primary_sensor_evidence if obs_s else (prev_s.primary_sensor_evidence if prev_s else ["temporal_prior"])
            
            new_physical_stresses[stype] = StressMagnitudeState(
                stress_type=stype,
                value=s_val,
                uncertainty=unc,
                source=PhysicalSourceType.DERIVED,
                primary_sensor_evidence=ev,
            )

        # 4. Propagate diagnostic hypothesis simplex via Bayesian Evidence-Ratio Fusion:
        # P(H_t | E_t, H_{t-1}) ∝ P(H_t | H_{t-1}) * [P(H_t | E_t) / P_0(H_t)]
        prior_hyp = cls.transition_hypothesis_prior(prev_state.diagnostic_hypothesis_state, dt_days=dt_days)

        obs_hyp = current_observations.get("diagnostic_hypothesis_state")
        if obs_hyp and isinstance(obs_hyp, StressHypothesisState):
            bayes_unnorm = {}
            for h in CANONICAL_HYPOTHESES:
                prior_h = max(1e-5, prior_hyp.posteriors.get(h, 0.15))
                obs_h = max(1e-5, obs_hyp.posteriors.get(h, 0.15))
                # Likelihood ratio relative to uninformative prior
                likelihood_weight = obs_h / 0.1667
                bayes_unnorm[h] = prior_h * likelihood_weight
            tot = sum(bayes_unnorm.values())
            fused_posteriors = {k: round(v / tot, 4) for k, v in bayes_unnorm.items()}
            final_hyp = StressHypothesisState(posteriors=fused_posteriors)
        else:
            final_hyp = prior_hyp

        # 5. Biological impact memory dynamics:
        # I_t = max(I_obs, gamma_stage * I_{t-1}) — tissue necrosis / floret abortion has memory
        current_stage = current_observations.get("phenology_stage", prev_state.phenology_stage)
        gamma_stage = 0.80 if current_stage.upper() in ("REPRODUCTIVE", "FLOWERING", "GRAIN_FILL") else 0.40
        
        obs_impacts = current_observations.get("biological_impact_states", {})
        new_impacts: Dict[str, StressImpactEstimate] = {}
        
        all_impact_keys = set(prev_state.biological_impact_states.keys()) | set(obs_impacts.keys())
        for stype in all_impact_keys:
            prev_imp = prev_state.biological_impact_states.get(stype)
            obs_imp = obs_impacts.get(stype)
            
            if obs_imp:
                prev_raw = prev_imp.raw_impact if prev_imp else 0.0
                effective_raw = max(obs_imp.raw_impact, round(prev_raw * gamma_stage, 3))
                effective_norm = min(1.0, effective_raw)
                effective_prob = round(1.0 / (1.0 + math.exp(-3.0 * (effective_raw - 0.7))), 3)
                
                new_impacts[stype] = StressImpactEstimate(
                    stress_type=stype,
                    raw_impact=effective_raw,
                    normalized_impact=effective_norm,
                    damage_probability=effective_prob,
                    impact_uncertainty=obs_imp.impact_uncertainty,
                    compound_synergy_factor=obs_imp.compound_synergy_factor,
                    compound_partner=obs_imp.compound_partner,
                    stage_sensitivity_multiplier=obs_imp.stage_sensitivity_multiplier,
                    crop_authority=obs_imp.crop_authority,
                    impact_authority=obs_imp.impact_authority,
                    explanation_basis=obs_imp.explanation_basis,
                )
            elif prev_imp:
                # Retain residual damage memory
                rem_raw = round(prev_imp.raw_impact * gamma_stage, 3)
                if rem_raw >= 0.10:
                    new_impacts[stype] = StressImpactEstimate(
                        stress_type=stype,
                        raw_impact=rem_raw,
                        normalized_impact=min(1.0, rem_raw),
                        damage_probability=round(1.0 / (1.0 + math.exp(-3.0 * (rem_raw - 0.7))), 3),
                        impact_uncertainty=round(prev_imp.impact_uncertainty * 1.1, 4),
                        crop_authority=prev_imp.crop_authority,
                        impact_authority=prev_imp.impact_authority,
                        explanation_basis=[f"Residual biological damage memory from previous {stype.lower()} stress"],
                    )

        now = current_observations.get("timestamp") or (prev_state.timestamp + timedelta(days=dt_days))

        return VegetationState(
            plot_id=prev_state.plot_id,
            timestamp=now,
            development_time=round(new_dev_time, 2),
            phenology_stage=current_stage,
            stage_progress_fraction=round(new_stage_frac, 3),
            crop_authority=prev_state.crop_authority,
            lai=smooth_lai,
            fvc=smooth_fvc,
            fpar=smooth_fpar,
            biomass_proxy=smooth_biomass,
            canopy_water_index=current_observations.get("canopy_water_index", prev_state.canopy_water_index),
            root_depth_proxy_m=current_observations.get("root_depth_proxy_m", prev_state.root_depth_proxy_m),
            root_zone_accessibility=current_observations.get("root_zone_accessibility", prev_state.root_zone_accessibility),
            physical_stress_states=new_physical_stresses,
            diagnostic_hypothesis_state=final_hyp,
            biological_impact_states=new_impacts,
            data_health_score=current_observations.get("data_health_score", prev_state.data_health_score),
            provenance=InferenceProvenance(
                model_version="4.2.0",
                crop_profile_version="4.0.0",
                data_sources=prev_state.provenance.data_sources,
                observation_count=prev_state.provenance.observation_count + 1,
                authority_level=prev_state.crop_authority,
                inference_mode=InferenceMode.ONLINE,
                execution_timestamp=now,
            ),
        )
