"""
Layer 3.0 Soil Water State Data Assimilation Engine
Optimal Interpolation (OI) with vertical spatial correlation for in-situ sensors, satellite soil moisture, and thermal observations.
NOTE: Despite early design documents referencing EnKF, the current implementation is OI — not ensemble-based.
"""

from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
import math
import numpy as np

from layer3_water.contracts.water_state import (
    SoilWaterState,
    AssimilationDiagnostic,
)
from layer3_water.contracts.assimilation_state import SoilObservationVector
from layer3_water.contracts.state_factory import WaterStateFactory
try:
    from scientific_contracts.numeric import finite_real
except ImportError:
    from services.agribrain.scientific_contracts.numeric import finite_real


class WaterStateAssimilator:
    """1D Optimal Interpolation / Kalman Filter for multi-layer soil moisture assimilation."""

    @classmethod
    def _build_vertical_background_covariance(
        cls,
        layer_depths_cm: List[float],
        base_sigma: float = 0.035,
        correlation_length_cm: float = 35.0,
    ) -> np.ndarray:
        """Construct vertical background error covariance matrix P^- with spatial correlation."""
        n = len(layer_depths_cm)
        P = np.zeros((n, n))
        centers = []
        prev_d = 0.0
        for d in layer_depths_cm:
            centers.append((d + prev_d) / 2.0)
            prev_d = d

        for i in range(n):
            for j in range(n):
                dist = abs(centers[i] - centers[j])
                corr = math.exp(-dist / correlation_length_cm)
                P[i, j] = (base_sigma ** 2) * corr
        return P

    @classmethod
    def _resolve_role(cls, global_role: str, comp_role: Optional[str]) -> str:
        g_upper = str(global_role).upper()
        c_upper = str(comp_role).upper() if comp_role else ""
        if g_upper in ("REJECTED", "EXCLUDED", "UNUSABLE") or c_upper in ("REJECTED", "EXCLUDED", "UNUSABLE"):
            return "EXCLUDED"
        if g_upper in ("SIMULATED", "SYNTHETIC", "SCENARIO", "PRIOR", "MODELLED", "FORECAST", "ESTIMATED"):
            return "SIMULATED"
        if c_upper in ("SIMULATED", "SYNTHETIC", "SCENARIO", "PRIOR", "MODELLED", "FORECAST", "ESTIMATED"):
            return "SIMULATED"
        return "OBSERVED"

    @classmethod
    def assimilate_observations(
        cls,
        prior_soil: SoilWaterState,
        observations: Optional[SoilObservationVector] = None,
        background_uncertainty_sigma: float = 0.035,
        cutoff: Optional[datetime] = None,
    ) -> Tuple[SoilWaterState, AssimilationDiagnostic]:
        """Perform optimal state update: X^+ = X^- + K(y - H X^-).
        
        Returns:
            (posterior_soil_state, assimilation_diagnostic)
        """
        background_uncertainty_sigma = finite_real(background_uncertainty_sigma)
        if (
            background_uncertainty_sigma is None or background_uncertainty_sigma <= 0.0
            or not math.isfinite(background_uncertainty_sigma * background_uncertainty_sigma)
            or background_uncertainty_sigma * background_uncertainty_sigma == 0.0
            or not math.isfinite(
                background_uncertainty_sigma * background_uncertainty_sigma * len(prior_soil.layer_depths_cm)
            )
        ):
            raise ValueError("background_uncertainty_sigma must be finite and strictly positive")
        if observations is None:
            diag = AssimilationDiagnostic(
                assimilation_method="NONE",
                observations_assimilated_count=0,
                innovation_vector_norm=0.0,
                kalman_gain_norm=0.0,
                prior_profile_variance=round(background_uncertainty_sigma ** 2 * len(prior_soil.layer_depths_cm), 5),
                posterior_profile_variance=round(background_uncertainty_sigma ** 2 * len(prior_soil.layer_depths_cm), 5),
                variance_reduction_fraction=0.0,
                assimilated_sensor_sources=[],
            )
            return prior_soil, diag

        n_layers = len(prior_soil.layer_depths_cm)
        x_prior = np.array(prior_soil.theta_profile, dtype=float)
        P_prior = cls._build_vertical_background_covariance(
            prior_soil.layer_depths_cm,
            base_sigma=background_uncertainty_sigma,
        )

        obs_indices = []
        obs_values = []
        obs_sigmas = []
        sources = []
        rejected = []

        temporal_reject_reason = None
        obs_time = getattr(observations, "timestamp", None)
        avail_time = getattr(observations, "available_at", None)
        if obs_time and avail_time and avail_time < obs_time:
            temporal_reject_reason = "causality_violation_availability_precedes_observation"
        elif cutoff is not None:
            if obs_time and obs_time > cutoff:
                temporal_reject_reason = "observation_time_postdates_cutoff"
            elif avail_time and avail_time > cutoff:
                temporal_reject_reason = "availability_time_postdates_cutoff"

        def _resolve_quality(component_val: Any, reading_val: Any, weight_val: Any) -> Optional[float]:
            candidates = [component_val, reading_val, weight_val]
            specified = [c for c in candidates if c is not None]
            if not specified:
                return 1.0
            valid_floats = []
            for c in specified:
                fin = finite_real(c)
                if fin is None:
                    return None
                if fin <= 0.0:
                    return 0.0
                valid_floats.append(fin)
            return min(valid_floats)

        def _resolve_role(global_role: str, comp_role: Optional[str]) -> str:
            g_upper = str(global_role).upper()
            c_upper = str(comp_role).upper() if comp_role else ""
            if g_upper in ("REJECTED", "EXCLUDED", "UNUSABLE") or c_upper in ("REJECTED", "EXCLUDED", "UNUSABLE"):
                return "EXCLUDED"
            if g_upper in ("SIMULATED", "SYNTHETIC", "SCENARIO", "PRIOR", "MODELLED", "FORECAST", "ESTIMATED"):
                return "SIMULATED"
            if c_upper in ("SIMULATED", "SYNTHETIC", "SCENARIO", "PRIOR", "MODELLED", "FORECAST", "ESTIMATED"):
                return "SIMULATED"
            return "OBSERVED"

        def add_observation(idx: int, raw_value: Any, raw_sigma: Any, source: str, role: str = "OBSERVED", reliability: Any = 1.0) -> bool:
            value = finite_real(raw_value)
            sigma = finite_real(raw_sigma)
            reason = None
            if temporal_reject_reason:
                reason = temporal_reject_reason
            elif value is None:
                reason = "missing_or_non_finite_value"
            elif (
                sigma is None or sigma <= 0.0
                or not math.isfinite(sigma * sigma) or sigma * sigma == 0.0
            ):
                reason = "invalid_observation_uncertainty"
            elif not 0.0 <= value <= prior_soil.saturation_profile[idx]:
                reason = "outside_soil_moisture_range"
            elif str(role).upper() in ("REJECTED", "EXCLUDED", "UNUSABLE"):
                reason = "explicitly_excluded_role"
            else:
                if reliability is None:
                    reason = "invalid_observation_reliability"
                else:
                    rel = finite_real(reliability)
                    if rel is None:
                        reason = "invalid_observation_reliability"
                    elif rel <= 0.0:
                        reason = "zero_reliability"
            if reason:
                rejected.append({
                    "source": source, "layer_index": idx, "reason": reason,
                    "value_repr": repr(raw_value), "sigma_repr": repr(raw_sigma),
                    "role": role,
                })
                return False
            obs_indices.append(idx)
            obs_values.append(value)
            obs_sigmas.append(sigma)
            if source not in sources:
                sources.append(source)
            return True

        vec_role = getattr(observations, "role", "OBSERVED")
        comp_roles = getattr(observations, "component_roles", {}) or {}
        comp_rels = getattr(observations, "component_reliabilities", {}) or {}
        reading_rel = getattr(observations, "reading_reliability", None)
        weight_rel = getattr(observations, "reliability_weight", None)

        # Domain definitions for provenance scoping
        NON_PROBE_DOMAINS = ("SATELLITE", "SMAP", "SENTINEL1", "THERMAL", "CANOPY_COOLING", "RADIOMETER", "FLUX")
        NON_SAT_DOMAINS = ("PROBE", "TDR", "IN_SITU", "CAPACITANCE", "SENSOR", "THERMAL", "CANOPY_COOLING", "RADIOMETER", "FLUX")
        NON_THERMAL_DOMAINS = ("PROBE", "TDR", "IN_SITU", "CAPACITANCE", "SENSOR", "SATELLITE", "SMAP", "SENTINEL1", "FLUX")

        # 1. In-situ probe profile observations
        if observations.soil_probe_moisture_profile:
            probe_vals = observations.soil_probe_moisture_profile
            probe_sigma = observations.observation_uncertainties.get("soil_probe", 0.015)
            probe_sources = [
                s for s in getattr(observations, "provenance_sources", [])
                if any(k in s.upper() for k in ("PROBE", "TDR", "IN_SITU", "CAPACITANCE", "SENSOR"))
            ]
            if not probe_sources:
                probe_sources = [
                    s for s in getattr(observations, "provenance_sources", [])
                    if not any(k in s.upper() for k in NON_PROBE_DOMAINS)
                ]
            probe_source = probe_sources[0] if probe_sources else (observations.provenance_sources[0] if observations.provenance_sources else "IN_SITU_PROBE_TDR")
            
            # Scoped probe restrictions: probe-specific or generic vector-wide restrictions (not scoped to other domains)
            probe_restriction_sources = [
                s for s in getattr(observations, "provenance_sources", [])
                if any(k in s.upper() for k in ("PROBE", "TDR", "IN_SITU", "CAPACITANCE", "SENSOR"))
                or not any(k in s.upper() for k in NON_PROBE_DOMAINS)
            ]
            probe_role_comp = comp_roles.get("soil_probe") or comp_roles.get("probe")
            probe_role = _resolve_role(vec_role, probe_role_comp)
            if any(term in s.upper() for s in probe_restriction_sources for term in ("REJECTED", "EXCLUDED", "UNUSABLE")) or any(term in probe_source.upper() for term in ("REJECTED", "EXCLUDED", "UNUSABLE")):
                probe_role = "EXCLUDED"
            elif any(term in s.upper() for s in probe_restriction_sources for term in ("SIMULATED", "SYNTHETIC", "SCENARIO", "PRIOR", "MODELLED", "FORECAST", "ESTIMATED")) or any(term in probe_source.upper() for term in ("SIMULATED", "SYNTHETIC", "SCENARIO", "PRIOR", "MODELLED", "FORECAST", "ESTIMATED")):
                if probe_role != "EXCLUDED":
                    probe_role = "SIMULATED"

            probe_rel = _resolve_quality(
                comp_rels.get("soil_probe", comp_rels.get("probe")),
                reading_rel,
                weight_rel,
            )
            for idx in range(min(n_layers, len(probe_vals))):
                add_observation(idx, probe_vals[idx], probe_sigma, probe_source, role=probe_role, reliability=probe_rel)

        # 2. Satellite surface soil moisture (Top layer)
        if observations.satellite_surface_moisture_m3_m3 is not None and 0 not in obs_indices:
            sat_val = observations.satellite_surface_moisture_m3_m3
            sat_sigma = observations.observation_uncertainties.get("satellite_smap", 0.040)
            sat_source = "SATELLITE_SMAP_SENTINEL1"
            sat_sources = [s for s in getattr(observations, "provenance_sources", []) if any(k in s.upper() for k in ("SATELLITE", "SMAP", "SENTINEL1"))]
            if sat_sources:
                sat_source = sat_sources[0]

            sat_restriction_sources = [
                s for s in getattr(observations, "provenance_sources", [])
                if any(k in s.upper() for k in ("SATELLITE", "SMAP", "SENTINEL1"))
                or not any(k in s.upper() for k in NON_SAT_DOMAINS)
            ]
            sat_role_comp = comp_roles.get("satellite")
            sat_role = _resolve_role(vec_role, sat_role_comp)
            if any(term in s.upper() for s in sat_restriction_sources for term in ("REJECTED", "EXCLUDED", "UNUSABLE")) or any(term in sat_source.upper() for term in ("REJECTED", "EXCLUDED", "UNUSABLE")):
                sat_role = "EXCLUDED"
            elif any(term in s.upper() for s in sat_restriction_sources for term in ("SIMULATED", "SYNTHETIC", "SCENARIO", "PRIOR", "MODELLED", "FORECAST", "ESTIMATED")) or any(term in sat_source.upper() for term in ("SIMULATED", "SYNTHETIC", "SCENARIO", "PRIOR", "MODELLED", "FORECAST", "ESTIMATED")):
                if sat_role != "EXCLUDED":
                    sat_role = "SIMULATED"

            sat_rel = _resolve_quality(
                comp_rels.get("satellite"),
                reading_rel,
                weight_rel,
            )
            add_observation(0, sat_val, sat_sigma, sat_source, role=sat_role, reliability=sat_rel)

        # 3. Thermal cooling differential proxy (Upper root zone constraint)
        if observations.canopy_cooling_differential_c is not None and not obs_indices:
            dt = finite_real(observations.canopy_cooling_differential_c)
            target_idx = 1 if n_layers > 1 else 0
            fc = prior_soil.field_capacity_profile[target_idx]
            wp = prior_soil.wilting_point_profile[target_idx]
            thermal_source = "THERMAL_CANOPY_COOLING_SURROGATE"
            thermal_sources = [s for s in getattr(observations, "provenance_sources", []) if any(k in s.upper() for k in ("THERMAL", "CANOPY_COOLING", "RADIOMETER"))]
            if thermal_sources:
                thermal_source = thermal_sources[0]

            thermal_restriction_sources = [
                s for s in getattr(observations, "provenance_sources", [])
                if any(k in s.upper() for k in ("THERMAL", "CANOPY_COOLING", "RADIOMETER"))
                or not any(k in s.upper() for k in NON_THERMAL_DOMAINS)
            ]
            thermal_role_comp = comp_roles.get("thermal")
            thermal_role = _resolve_role(vec_role, thermal_role_comp)
            if any(term in s.upper() for s in thermal_restriction_sources for term in ("REJECTED", "EXCLUDED", "UNUSABLE")) or any(term in thermal_source.upper() for term in ("REJECTED", "EXCLUDED", "UNUSABLE")):
                thermal_role = "EXCLUDED"
            elif any(term in s.upper() for s in thermal_restriction_sources for term in ("SIMULATED", "SYNTHETIC", "SCENARIO", "PRIOR", "MODELLED", "FORECAST", "ESTIMATED")) or any(term in thermal_source.upper() for term in ("SIMULATED", "SYNTHETIC", "SCENARIO", "PRIOR", "MODELLED", "FORECAST", "ESTIMATED")):
                if thermal_role != "EXCLUDED":
                    thermal_role = "SIMULATED"

            thermal_rel = _resolve_quality(
                comp_rels.get("thermal"),
                reading_rel,
                weight_rel,
            )

            if dt is None:
                rejected.append({
                    "source": thermal_source,
                    "layer_index": target_idx, "reason": "missing_or_non_finite_value",
                    "value_repr": repr(observations.canopy_cooling_differential_c),
                    "role": thermal_role,
                })
            elif dt > 2.0:
                est_th = wp + 0.20 * (fc - wp)
                add_observation(target_idx, est_th, 0.050, thermal_source, role=thermal_role, reliability=thermal_rel)

        if not obs_indices:
            diag = AssimilationDiagnostic(
                assimilation_method="NONE",
                observations_assimilated_count=0,
                prior_profile_variance=round(float(np.trace(P_prior)), 5),
                posterior_profile_variance=round(float(np.trace(P_prior)), 5),
                variance_reduction_fraction=0.0,
                assimilated_sensor_sources=[],
                rejected_observations=rejected,
            )
            return prior_soil, diag

        # Form Observation Operator H and Observation Covariance R
        m = len(obs_indices)
        H = np.zeros((m, n_layers))
        y = np.array(obs_values, dtype=float)
        R = np.zeros((m, m))

        for row, (idx, sig) in enumerate(zip(obs_indices, obs_sigmas)):
            H[row, idx] = 1.0
            R[row, row] = sig ** 2

        # Innovation: d = y - H x_prior
        d = y - H.dot(x_prior)

        # Innovation covariance: S = H P H^T + R
        S = H.dot(P_prior).dot(H.T) + R

        # Kalman Gain: K = P H^T S^-1
        K = P_prior.dot(H.T).dot(np.linalg.inv(S))

        # Posterior state: x_post = x_prior + K d
        x_post = x_prior + K.dot(d)

        # Posterior covariance: P_post = (I - K H) P_prior
        I_mat = np.eye(n_layers)
        P_post = (I_mat - K.dot(H)).dot(P_prior)

        # Enforce physical constraints: theta_r <= theta_post <= theta_s
        clamped_theta = []
        bound_corrections = 0
        for i in range(n_layers):
            th_r = prior_soil.residual_profile[i]
            th_s = prior_soil.saturation_profile[i]
            raw_v = float(x_post[i])
            if raw_v < th_r + 1e-4 or raw_v > th_s - 1e-4:
                bound_corrections += 1
            clamped_theta.append(float(np.clip(raw_v, th_r + 1e-4, th_s - 1e-4)))

        trace_prior = float(np.trace(P_prior))
        trace_post = float(np.trace(P_post))
        var_reduct = max(0.0, min(1.0, 1.0 - (trace_post / max(1e-6, trace_prior))))

        diag = AssimilationDiagnostic(
            assimilation_method="OPTIMAL_INTERPOLATION_1D",
            observations_assimilated_count=m,
            innovation_vector_norm=round(float(np.linalg.norm(d)), 4),
            kalman_gain_norm=round(float(np.linalg.norm(K)), 4),
            prior_profile_variance=round(trace_prior, 5),
            posterior_profile_variance=round(trace_post, 5),
            variance_reduction_fraction=round(var_reduct, 3),
            bound_corrections_applied=bound_corrections,
            assimilated_sensor_sources=sources,
            rejected_observations=rejected,
        )

        posterior_soil = WaterStateFactory.create_soil_water_state(
            layer_depths_cm=prior_soil.layer_depths_cm,
            theta_profile=clamped_theta,
            field_capacity_profile=prior_soil.field_capacity_profile,
            wilting_point_profile=prior_soil.wilting_point_profile,
            saturation_profile=prior_soil.saturation_profile,
            residual_profile=prior_soil.residual_profile,
            hydraulic_conductivity_profile=prior_soil.hydraulic_conductivity_profile,
            van_genuchten_alpha=prior_soil.van_genuchten_alpha,
            van_genuchten_n=prior_soil.van_genuchten_n,
            infiltration=prior_soil.infiltration,
            evaporation_state=prior_soil.evaporation_state,
            parameter_provenance=getattr(prior_soil, "parameter_provenance", "TEXTURE_PRIOR"),
        )

        return posterior_soil, diag

    # Alias for assimilate_observations
    assimilate = assimilate_observations
