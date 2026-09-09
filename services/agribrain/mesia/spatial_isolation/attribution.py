"""MESIA Multi-Hypothesis External Cause Attribution & Boundary Isolation.

Disentangles ambiguous and external observations into specific physical hypotheses:
- Internal crop dynamics (H_internal)
- Adjacent plot irrigation (H_adjacent_irrigation)
- Adjacent asphalt road or metallic shed (H_road_metal)
- Bordering windbreak trees (H_windbreak_trees)
- Perimeter drainage canal (H_canal_water)
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from .models import ExternalAttributionVector, SpatialClassificationTier


class MultiHypothesisAttributionEngine:
    """Bayesian hypothesis testing and external nuisance attribution across plot boundaries."""

    @classmethod
    def evaluate_external_causes(
        cls,
        eta_hat_plot: float,
        eta_lower_plot: float,
        bearing_deg: float,
        footprint_centroid_enu_m: Tuple[float, float],
        classification_tier: SpatialClassificationTier,
        observed_delta_db: float,
        rh_air_pct: float = 65.0,
        hour_of_day: float = 14.0,
        adjacent_land_use_map: Optional[Dict[str, str]] = None,
    ) -> ExternalAttributionVector:
        """Computes posterior probabilities across 5 spatial hypotheses and decomposes x_ext."""
        # 1. Priors based on containment
        p_int_prior = max(0.05, min(0.95, eta_hat_plot))
        p_ext_prior = (1.0 - p_int_prior)

        # Distribute external prior among external causes
        # Default land use priors if not explicitly mapped
        p_adj_irrig_prior = p_ext_prior * 0.40
        p_road_prior = p_ext_prior * 0.20
        p_windbreak_prior = p_ext_prior * 0.25
        p_canal_prior = p_ext_prior * 0.15

        # 2. Likelihoods given physical evidence
        # If delta_db is positive and large, water/irrigation is likely
        if observed_delta_db > 1.5:
            l_int = 0.5 if eta_lower_plot >= 0.80 else 0.1
            l_adj_irrig = 0.85 if eta_hat_plot < 0.85 else 0.15
            l_road = 0.05
            l_windbreak = 0.10
            l_canal = 0.70 if eta_hat_plot < 0.70 else 0.20
        elif observed_delta_db < -2.0:
            # Strong attenuation - typical of heavy windbreak foliage or road thermal dryout
            l_int = 0.6 if eta_lower_plot >= 0.80 else 0.2
            l_adj_irrig = 0.05
            l_road = 0.65 if 11.0 <= hour_of_day <= 16.0 else 0.20
            l_windbreak = 0.80
            l_canal = 0.05
        else:
            # Nominal perturbations
            l_int = 0.8 if eta_lower_plot >= 0.80 else 0.3
            l_adj_irrig = 0.2
            l_road = 0.3
            l_windbreak = 0.3
            l_canal = 0.2

        # Compute unnormalized posteriors
        unnorm = {
            "H_internal_crop": p_int_prior * l_int,
            "H_adjacent_irrigation": p_adj_irrig_prior * l_adj_irrig,
            "H_road_metal": p_road_prior * l_road,
            "H_windbreak_trees": p_windbreak_prior * l_windbreak,
            "H_canal_water": p_canal_prior * l_canal,
        }
        total_weight = sum(unnorm.values())
        if total_weight < 1e-9:
            posteriors = {k: 0.2 for k in unnorm}
        else:
            posteriors = {k: v / total_weight for k, v in unnorm.items()}

        dominant_hypothesis = max(posteriors.items(), key=lambda item: item[1])[0]

        # Calculate Shannon entropy H in bits
        entropy_bits = 0.0
        for p in posteriors.values():
            if p > 1e-6:
                entropy_bits -= p * math.log2(p)

        # Decompose external vector x_ext
        ext_sum = 1.0 - posteriors["H_internal_crop"]
        if ext_sum > 1e-4:
            f_irrig = posteriors["H_adjacent_irrigation"] / ext_sum
            f_road = posteriors["H_road_metal"] / ext_sum
            f_trees = posteriors["H_windbreak_trees"] / ext_sum
            f_canal = posteriors["H_canal_water"] / ext_sum
        else:
            f_irrig = f_road = f_trees = f_canal = 0.0

        # Formulate human-auditable explanation
        if dominant_hypothesis == "H_internal_crop":
            explanation = (
                f"True internal crop signal dominates posterior ({posteriors['H_internal_crop']:.1%}). "
                f"External nuisance attribution is negligible."
            )
        elif dominant_hypothesis == "H_adjacent_irrigation":
            explanation = (
                f"Neighboring plot irrigation activity identified as dominant cause "
                f"(P={posteriors['H_adjacent_irrigation']:.1%}). "
                f"RF wetting event rejected from internal plot root-zone state update."
            )
        elif dominant_hypothesis == "H_windbreak_trees":
            explanation = (
                f"Bordering windbreak trees causing volume scatter attenuation "
                f"(P={posteriors['H_windbreak_trees']:.1%}). Displaced from internal canopy index."
            )
        elif dominant_hypothesis == "H_road_metal":
            explanation = (
                f"Perimeter asphalt/track surface dielectric mismatch identified "
                f"(P={posteriors['H_road_metal']:.1%}). Attributed to external infrastructure."
            )
        else:
            explanation = (
                f"Boundary drainage ditch / canal specular reflection detected "
                f"(P={posteriors['H_canal_water']:.1%}). Quarantined."
            )

        return ExternalAttributionVector(
            dominant_hypothesis=dominant_hypothesis,
            hypothesis_posteriors=posteriors,
            attribution_entropy_bits=float(round(entropy_bits, 3)),
            adjacent_plot_irrigation_fraction=float(round(f_irrig, 3)),
            road_metal_reflection_fraction=float(round(f_road, 3)),
            windbreak_foliage_fraction=float(round(f_trees, 3)),
            canal_water_fraction=float(round(f_canal, 3)),
            explanation=explanation,
        )
