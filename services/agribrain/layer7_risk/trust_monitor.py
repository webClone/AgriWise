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

        # Canopy water is content, not a stress probability. High soil water
        # and high canopy water are not evidence of contradiction.
        water_feat = asmae_features.get("ASMAE_CANOPY_WATER")
        if water_feat is not None:
            from services.agribrain.scientific_contracts.asmae_physical_semantics import validate_canopy_water_content
            try:
                validate_canopy_water_content(water_feat)
            except ValueError:
                reasons.append("canopy_water_semantic_unit_unqualified")

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

        # Leaf chlorophyll content cannot be compared to soil N ppm as if
        # they were the same physical variable. A crop-calibrated response
        # operator and uncertainty-aware model are needed for contradiction.
        chloro_feat = asmae_features.get("ASMAE_CHLOROPHYLL")
        if chloro_feat is not None:
            from services.agribrain.scientific_contracts.asmae_physical_semantics import require_tagged_state_quantity
            try:
                require_tagged_state_quantity(chloro_feat, "chlorophyll")
            except ValueError:
                reasons.append("chlorophyll_semantic_unit_unqualified")

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
