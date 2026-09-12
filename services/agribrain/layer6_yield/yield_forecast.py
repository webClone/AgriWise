"""
Layer 6.1: Yield Forecasting Engine (Hybrid).
Predicts yield using Biomass Baseline and Stress Penalties (Water, Nutrient, Disease).
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Mapping, Optional
import math

from crop_database import get_crop, CROP_REGISTRY

class YieldForecastEngine:
    
    def __init__(self):
        # Harvest indices are now sourced from the centralized
        # crop_database (209+ crops). No local table needed.
        pass
        
    def predict_yield(self, 
                      crop_type: str,
                      final_biomass_kg_ha: float,
                      cumulative_stress: Dict[str, float],
                      confidence_scores: Dict[str, float] = None,
                      input_hash: Optional[str] = None,
                      asmae_features: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Hybrid Prediction with Uncertainty Propagation & Versioning.
        Y_final = (Biomass * HI) * (1 - Loss_Water) * (1 - Loss_Nutri) * (1 - Loss_Dis)
        """
        if not input_hash or input_hash == "mock_hash":
            import hashlib
            hash_src = f"{crop_type}-{final_biomass_kg_ha:.2f}-{sorted(cumulative_stress.items())}"
            input_hash = hashlib.sha256(hash_src.encode("utf-8")).hexdigest()[:16]

        if confidence_scores is None:
            confidence_scores = {"biomass": 0.8, "stress": 0.7}
            
        hi = get_crop(crop_type).harvest_index
        
        # 1. Potential/Baseline Yield
        y_potential = final_biomass_kg_ha * hi / 1000.0
        
        # 2. Stress Penalties (Multiplicative with Capping)
        l_water = cumulative_stress.get("water_loss_factor", 0.0)
        l_nutri = cumulative_stress.get("nutrient_loss_factor", 0.0)
        l_disease = cumulative_stress.get("disease_loss_factor", 0.0)
        
        # Double-Counting / Leakage Prevention
        # Correlated risks: Water Stress often causes "Nutrient-like" symptoms.
        # If both are high, we don't multiply full overlap.
        # Simple heuristic: Max(L_water, L_nutri) + 0.2 * Min(...) instead of independent?
        # For now, we will just cap the TOTAL loss to prevent absurd drops (e.g. 0.1 yield).
        
        # Calculate naive reduction first
        naive_factor = (1 - l_water) * (1 - l_nutri) * (1 - l_disease)
        total_loss = 1.0 - naive_factor
        
        # Cap Loss at 70% unless catastrophic failure confirm
        if total_loss > 0.7:
            total_loss = 0.7 
            
        reduction_factor = 1.0 - total_loss
        y_final = y_potential * reduction_factor

        # ASMAE Vigor and LAI integration
        asmae_unc_contrib = 0.0
        if asmae_features:
            # 1. ASMAE Vigor Calibration
            vigor_feat = asmae_features.get("ASMAE_VIGOR")
            if vigor_feat:
                if hasattr(vigor_feat, "confidence") and vigor_feat.confidence >= 0.6 and vigor_feat.uncertainty <= 0.4:
                    vigor_adj = 1.0 + (vigor_feat.value - 0.7) * 0.3
                    y_final *= max(0.5, min(1.5, vigor_adj))
                    asmae_unc_contrib += vigor_feat.uncertainty * 0.1
                elif isinstance(vigor_feat, dict) and vigor_feat.get("confidence", 0.5) >= 0.6 and vigor_feat.get("uncertainty", 0.1) <= 0.4:
                    vigor_adj = 1.0 + (vigor_feat.get("value", 0.7) - 0.7) * 0.3
                    y_final *= max(0.5, min(1.5, vigor_adj))
                    asmae_unc_contrib += vigor_feat.get("uncertainty", 0.1) * 0.1
            
            # 2. ASMAE LAI Calibration
            lai_feat = asmae_features.get("ASMAE_LAI")
            if lai_feat:
                if hasattr(lai_feat, "confidence") and lai_feat.confidence >= 0.6 and lai_feat.uncertainty <= 0.4:
                    lai_adj = 1.0 + (lai_feat.value - 3.0) * 0.1
                    y_final *= max(0.5, min(1.5, lai_adj))
                    asmae_unc_contrib += lai_feat.uncertainty * 0.1
                elif isinstance(lai_feat, dict) and lai_feat.get("confidence", 0.5) >= 0.6 and lai_feat.get("uncertainty", 0.1) <= 0.4:
                    lai_adj = 1.0 + (lai_feat.get("value", 3.0) - 3.0) * 0.1
                    y_final *= max(0.5, min(1.5, lai_adj))
                    asmae_unc_contrib += lai_feat.get("uncertainty", 0.1) * 0.1
        
        # 3. Attribution
        attribution = {
            "water": 0.0, "nutrient": 0.0, "disease": 0.0, "unknown": 0.1
        }
        sum_raw_loss = l_water + l_nutri + l_disease
        if sum_raw_loss > 0:
            attribution["water"] = round(l_water / sum_raw_loss * (total_loss - 0.1), 2)
            attribution["nutrient"] = round(l_nutri / sum_raw_loss * (total_loss - 0.1), 2)
            attribution["disease"] = round(l_disease / sum_raw_loss * (total_loss - 0.1), 2)
            attribution["unknown"] = 0.1 # Residual uncertainty
            
        # 4. Uncertainty Propagation
        # Base uncertainty from Biomass (Sensor/Model error)
        biomass_conf = confidence_scores.get("biomass", 0.8)
        stress_conf = confidence_scores.get("stress", 0.7)
        
        # Lower confidence = Wider interval
        # Base CV (Coefficient of Variation)
        base_cv = 0.1 + (1 - biomass_conf) * 0.2 # 10-30%
        # Add stress uncertainty
        stress_cv = (1 - stress_conf) * 0.15 # additional 0-15%
        
        total_cv = base_cv + stress_cv + asmae_unc_contrib
        std_dev = y_final * total_cv
        
        # Trust Tier
        avg_conf = (biomass_conf + stress_conf) / 2
        trust = "Low"
        if avg_conf > 0.6: trust = "Moderate"
        if avg_conf > 0.8: trust = "High"

        # Calculate data coverage completeness based on present stress indicators
        coverage_pct = sum(1 for k in ["water_loss_factor", "nutrient_loss_factor", "disease_loss_factor"] if k in cumulative_stress) / 3.0
        coverage_str = "complete" if coverage_pct == 1.0 else ("partial" if coverage_pct > 0.0 else "none")

        return {
            "yield_mean_t_ha": round(y_final, 2),
            "yield_p10": round(max(0, y_final - 1.645 * std_dev), 2),
            "yield_p90": round(y_final + 1.645 * std_dev, 2),
            "confidence_score": round(avg_conf, 2),
            "trust_tier": trust,
            "potential_yield_t_ha": round(y_potential, 2),
            "reduction_factor": round(reduction_factor, 2),
            "attribution": attribution,
            "asmae_uncertainty_contribution": round(asmae_unc_contrib, 4),
            "crop_stage_evidence_class": "declared_scenario_assumption",
            "crop_posterior_hash": "",
            "phenology_posterior_hash": "",
            "identity_uncertainty_variance": 0.0,
            "phenology_uncertainty_variance": 0.0,
            "production_eligible": False,
            "meta": {
                "model_version": "L6_HYBRID_V1.1",
                "input_hash": input_hash,
                "coverage": coverage_str
            }
        }

    def predict_yield_posterior(
        self,
        *,
        semantic_context: Any,
        final_biomass_kg_ha: float,
        cumulative_stress: Dict[str, float],
        confidence_scores: Dict[str, float] = None,
        input_hash: str = "",
        asmae_features: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Forecast across canonical crop/stage hypotheses.

        Identity variance and phenology variance remain separate so callers
        cannot mistake a narrow biomass interval for crop certainty.
        """
        def normalise(raw: Any) -> Dict[str, float]:
            if not isinstance(raw, Mapping):
                return {}
            clean = {}
            for key, value in raw.items():
                try:
                    probability = float(value)
                except (TypeError, ValueError):
                    continue
                if math.isfinite(probability) and probability > 0.0:
                    clean[str(key).lower()] = probability
            total = sum(clean.values())
            return ({key: value / total for key, value in clean.items()}
                    if total > 0.0 else {})

        crop_mix = normalise(getattr(semantic_context, "crop_mixture", {}))
        species_allowed = bool(getattr(semantic_context, "species_specific_allowed", False))
        resolution = str(getattr(semantic_context, "crop_resolution", "unknown"))
        selected = str(getattr(semantic_context, "selected_crop", "") or "").lower()
        if species_allowed and selected and not crop_mix:
            crop_mix = {selected: 1.0}
        elif not species_allowed and resolution == "group_only":
            expanded = {}
            for group, probability in crop_mix.items():
                matches = [
                    code for code, spec in CROP_REGISTRY.items()
                    if str(spec.architecture).lower() == group
                ]
                for code in matches:
                    expanded[code] = expanded.get(code, 0.0) + probability / max(1, len(matches))
            crop_mix = normalise(expanded)
        if not crop_mix:
            representatives = {}
            for code, spec in CROP_REGISTRY.items():
                representatives.setdefault(str(spec.architecture).lower(), code)
            crop_mix = normalise({code: 1.0 for code in representatives.values()})

        branches = []
        for crop_code, probability in crop_mix.items():
            if crop_code not in CROP_REGISTRY:
                continue
            branch = self.predict_yield(
                crop_type=crop_code,
                final_biomass_kg_ha=final_biomass_kg_ha,
                cumulative_stress=cumulative_stress,
                confidence_scores=confidence_scores,
                input_hash=input_hash or "posterior",
                asmae_features=asmae_features,
            )
            branches.append((probability, branch))
        if not branches:
            raise ValueError("no compatible crop hypotheses for yield forecast")
        total = sum(weight for weight, _ in branches) or 1.0
        mean = sum(weight / total * branch["yield_mean_t_ha"] for weight, branch in branches)
        identity_variance = sum(
            weight / total * (branch["yield_mean_t_ha"] - mean) ** 2
            for weight, branch in branches
        )
        within_variance = sum(
            weight / total
            * ((branch["yield_p90"] - branch["yield_p10"]) / (2 * 1.645)) ** 2
            for weight, branch in branches
        )

        stage_mix = normalise(getattr(semantic_context, "stage_posterior", {}))
        if stage_mix:
            entropy = -sum(p * math.log(p) for p in stage_mix.values())
            max_entropy = math.log(max(2, len(stage_mix)))
            entropy_fraction = min(1.0, entropy / max_entropy) if max_entropy else 0.0
        else:
            entropy_fraction = 1.0
        stage_allowed = bool(getattr(semantic_context, "stage_specific_allowed", False))
        phenology_variance = (mean * (0.04 if stage_allowed else 0.15) * entropy_fraction) ** 2
        total_std = math.sqrt(max(0.0, within_variance + identity_variance + phenology_variance))

        return {
            "yield_mean_t_ha": round(mean, 2),
            "yield_p10": round(max(0.0, mean - 1.645 * total_std), 2),
            "yield_p90": round(mean + 1.645 * total_std, 2),
            "identity_uncertainty_variance": round(identity_variance, 6),
            "phenology_uncertainty_variance": round(phenology_variance, 6),
            "crop_stage_evidence_class": (
                "canonical_species_stage_posterior"
                if species_allowed and stage_allowed else "hypothesis_ensemble"
            ),
            "crop_posterior_hash": str(getattr(semantic_context, "crop_posterior_hash", "") or ""),
            "phenology_posterior_hash": str(getattr(semantic_context, "phenology_posterior_hash", "") or ""),
            "hypothesis_weights": crop_mix,
            "production_eligible": species_allowed and stage_allowed,
            "meta": {"model_version": "L6_HYBRID_POSTERIOR_V2", "input_hash": input_hash},
        }

# Singleton
yield_engine = YieldForecastEngine()


def predict_yield(
    crop_type: str,
    final_biomass_kg_ha: float,
    cumulative_stress: Dict[str, float],
    confidence_scores: Dict[str, float] = None,
    input_hash: Optional[str] = None,
    asmae_features: Dict[str, Any] = None,
) -> Dict[str, Any]:
    return yield_engine.predict_yield(
        crop_type=crop_type,
        final_biomass_kg_ha=final_biomass_kg_ha,
        cumulative_stress=cumulative_stress,
        confidence_scores=confidence_scores,
        input_hash=input_hash,
        asmae_features=asmae_features,
    )


def predict_yield_posterior(**kwargs) -> Dict[str, Any]:
    return yield_engine.predict_yield_posterior(**kwargs)
