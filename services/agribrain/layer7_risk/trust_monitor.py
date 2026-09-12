"""
Layer 7.4: Drift & Trust Monitor.
Evaluates data quality and model confidence.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone

class TrustMonitor:
    
    def evaluate_trust(self, 
                       last_satellite_date: datetime, 
                       sensor_active: bool,
                       forecast_available: bool,
                       current_time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Compute Trust Score based on data freshness and availability.
        Accepts optional current_time for deterministic replay (Task A16).
        """
        if current_time is not None:
            now = current_time
        elif last_satellite_date.tzinfo is not None:
            now = datetime.now(timezone.utc)
        else:
            now = datetime.now()
        days_since_sat = (now - last_satellite_date).days
        
        score = 100
        issues = []
        actions = []
        
        # 1. Satellite Freshness
        if days_since_sat > 10:
            score -= 30
            issues.append(f"No Satellite Image for {days_since_sat} days")
            actions.append("Upload drone/phone photo")
        elif days_since_sat > 5:
            score -= 10
            issues.append("Satellite Data aging")
            
        # 2. Sensor Health
        if not sensor_active:
            score -= 20
            issues.append("No active Soil Sensor (Model-only mode)")
            actions.append("Consider installing sensor for precision")
            
        # 3. Forecast
        if not forecast_available:
            score -= 20
            issues.append("Missing Weather Forecast")
            
        # Clamp
        score = max(0, score)
        
        level = "High"
        if score < 80: level = "Moderate"
        if score < 50: level = "Low"
        
        return {
            "trust_score": score,
            "trust_level": level,
            "issues": issues,
            "suggested_actions": actions
        }

    def evaluate_cross_layer_conflict(self, 
                                      asmae_features: Dict[str, Any], 
                                      non_asmae_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate cross-layer contradiction score between ASMAE observations and other evidence layers.
        """
        conflict_score = 0.0
        reasons = []
        agreement = True

        if not asmae_features:
            return {
                "conflict_score": 0.0,
                "reasons": [],
                "agreement": True
            }

        # 1. Water Contradiction Check
        # ASMAE Canopy Water (stress) vs Measured Soil Moisture
        water_feat = asmae_features.get("ASMAE_CANOPY_WATER")
        soil_moisture = non_asmae_data.get("soil_moisture_vwc")
        if water_feat and soil_moisture is not None:
            if soil_moisture > 0.30 and getattr(water_feat, "value", 0.0) > 0.7:
                conflict_score += 0.4
                reasons.append("water_conflict_high_moisture_with_high_canopy_stress")

        # 2. Salinity Contradiction Check
        # ASMAE Salinity Stress vs Measured EC
        sal_feat = asmae_features.get("ASMAE_SALINITY_STRESS")
        measured_ec = non_asmae_data.get("ec_ds_m")
        if sal_feat and measured_ec is not None:
            if measured_ec < 1.0 and getattr(sal_feat, "value", 0.0) > 0.7:
                conflict_score += 0.5
                reasons.append("salinity_conflict_low_ec_with_high_asmae_salinity")

        # 3. Biotic Contradiction Check
        # ASMAE Biotic Risk vs Mechanical Damage or other explanations
        biotic_feat = asmae_features.get("ASMAE_BIOTIC_CONFOUNDER_RISK")
        mechanical_damage = non_asmae_data.get("mechanical_damage")
        if biotic_feat and mechanical_damage:
            if getattr(biotic_feat, "value", 0.0) > 0.6 and mechanical_damage > 0.5:
                conflict_score += 0.3
                reasons.append("biotic_conflict_high_risk_explained_by_mechanical_damage")

        # 4. Nutrient Contradiction Check
        # ASMAE Chlorophyll vs Soil Lab Nitrogen
        chloro_feat = asmae_features.get("ASMAE_CHLOROPHYLL")
        soil_n = non_asmae_data.get("nitrogen_ppm")
        if chloro_feat and soil_n is not None:
            if getattr(chloro_feat, "value", 0.0) < 0.3 and soil_n > 50.0:
                conflict_score += 0.3
                reasons.append("nutrient_conflict_low_chlorophyll_with_high_soil_n")

        # BMA disagreement check
        for feat in asmae_features.values():
            bma_disagreement = getattr(feat, "bma_disagreement", 0.0)
            if isinstance(feat, dict):
                bma_disagreement = feat.get("bma_disagreement", 0.0)
            if bma_disagreement > 0.3:
                conflict_score += 0.3
                reasons.append("bma_disagreement_high")

        conflict_score = min(1.0, conflict_score)
        if conflict_score > 0.4:
            agreement = False

        return {
            "conflict_score": round(conflict_score, 2),
            "reasons": reasons,
            "agreement": agreement
        }

# Singleton
trust_monitor = TrustMonitor()
