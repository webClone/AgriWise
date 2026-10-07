"""
Layer 3.0 Soil Water State Data Assimilation Engine
Optimal Interpolation (OI) with vertical spatial correlation for in-situ sensors, satellite soil moisture, and thermal observations.
NOTE: Despite early design documents referencing EnKF, the current implementation is OI — not ensemble-based.
"""

from typing import List, Optional, Tuple, Dict, Any
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
    def assimilate_observations(
        cls,
        prior_soil: SoilWaterState,
        observations: Optional[SoilObservationVector] = None,
        background_uncertainty_sigma: float = 0.035,
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

        def add_observation(idx: int, raw_value: Any, raw_sigma: Any, source: str) -> bool:
            value = finite_real(raw_value)
            sigma = finite_real(raw_sigma)
            reason = None
            if value is None:
                reason = "missing_or_non_finite_value"
            elif (
                sigma is None or sigma <= 0.0
                or not math.isfinite(sigma * sigma) or sigma * sigma == 0.0
            ):
                reason = "invalid_observation_uncertainty"
            elif not 0.0 <= value <= prior_soil.saturation_profile[idx]:
                reason = "outside_soil_moisture_range"
            if reason:
                rejected.append({
                    "source": source, "layer_index": idx, "reason": reason,
                    "value_repr": repr(raw_value), "sigma_repr": repr(raw_sigma),
                })
                return False
            obs_indices.append(idx)
            obs_values.append(value)
            obs_sigmas.append(sigma)
            if source not in sources:
                sources.append(source)
            return True

        # 1. In-situ probe profile observations
        if observations.soil_probe_moisture_profile:
            probe_vals = observations.soil_probe_moisture_profile
            probe_sigma = observations.observation_uncertainties.get("soil_probe", 0.015)
            for idx in range(min(n_layers, len(probe_vals))):
                add_observation(idx, probe_vals[idx], probe_sigma, "IN_SITU_PROBE_TDR")

        # 2. Satellite surface soil moisture (Top layer)
        if observations.satellite_surface_moisture_m3_m3 is not None and 0 not in obs_indices:
            sat_val = observations.satellite_surface_moisture_m3_m3
            sat_sigma = observations.observation_uncertainties.get("satellite_smap", 0.040)
            add_observation(0, sat_val, sat_sigma, "SATELLITE_SMAP_SENTINEL1")

        # 3. Thermal cooling differential proxy (Upper root zone constraint)
        if observations.canopy_cooling_differential_c is not None and not obs_indices:
            # If Tc - Ta is severely positive (+4C), soil is dry; if negative (-2C), soil is well-watered
            dt = finite_real(observations.canopy_cooling_differential_c)
            # Linear surrogate constraint on root-zone layer 1 & 2
            target_idx = 1 if n_layers > 1 else 0
            fc = prior_soil.field_capacity_profile[target_idx]
            wp = prior_soil.wilting_point_profile[target_idx]
            if dt is None:
                rejected.append({
                    "source": "THERMAL_CANOPY_COOLING_SURROGATE",
                    "layer_index": target_idx, "reason": "missing_or_non_finite_value",
                    "value_repr": repr(observations.canopy_cooling_differential_c),
                })
            elif dt > 2.0:
                est_th = wp + 0.20 * (fc - wp)
                add_observation(target_idx, est_th, 0.050, "THERMAL_CANOPY_COOLING_SURROGATE")

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
