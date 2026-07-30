
import math
from typing import List, Dict, Any, Tuple, Optional

from layer3_decision.schema import Diagnosis, PlotContext, EvidenceTerm, Driver
from layer3_decision.features.builder import DecisionFeatures
from layer3_decision.knowledge.ontology import ProblemType, PROBLEM_DB

# FAO-33 Yield Response Factors (Doorenbos & Kassam, 1979)
# Ky > 1.0 = catastrophic loss when stressed at that stage
# Ky < 0.5 = resilient, plant recovers
# SCI-5: Crop-specific Ky factors
_KY_BY_CROP_STAGE = {
    # Default (generic cereal)
    "_default": {
        "BARE_SOIL": 0.0, "EMERGENCE": 0.2, "VEGETATIVE": 0.2,
        "REPRODUCTIVE": 1.25, "MATURITY": 0.8, "SENESCENCE": 0.2, "UNKNOWN": 0.5,
    },
    # Wheat (Doorenbos & Kassam 1979, Table 39)
    "wheat": {
        "BARE_SOIL": 0.0, "EMERGENCE": 0.2, "VEGETATIVE": 0.2,
        "REPRODUCTIVE": 0.55, "MATURITY": 0.65, "SENESCENCE": 0.2, "UNKNOWN": 0.4,
    },
    "barley": {
        "BARE_SOIL": 0.0, "EMERGENCE": 0.2, "VEGETATIVE": 0.2,
        "REPRODUCTIVE": 0.50, "MATURITY": 0.60, "SENESCENCE": 0.2, "UNKNOWN": 0.4,
    },
    # Maize (highest flowering sensitivity)
    "maize": {
        "BARE_SOIL": 0.0, "EMERGENCE": 0.4, "VEGETATIVE": 0.4,
        "REPRODUCTIVE": 1.50, "MATURITY": 0.5, "SENESCENCE": 0.2, "UNKNOWN": 0.5,
    },
    "corn": {
        "BARE_SOIL": 0.0, "EMERGENCE": 0.4, "VEGETATIVE": 0.4,
        "REPRODUCTIVE": 1.50, "MATURITY": 0.5, "SENESCENCE": 0.2, "UNKNOWN": 0.5,
    },
    # Cotton
    "cotton": {
        "BARE_SOIL": 0.0, "EMERGENCE": 0.2, "VEGETATIVE": 0.2,
        "REPRODUCTIVE": 0.85, "MATURITY": 0.45, "SENESCENCE": 0.2, "UNKNOWN": 0.4,
    },
    # Rice
    "rice": {
        "BARE_SOIL": 0.0, "EMERGENCE": 0.2, "VEGETATIVE": 0.2,
        "REPRODUCTIVE": 1.00, "MATURITY": 0.6, "SENESCENCE": 0.2, "UNKNOWN": 0.5,
    },
    # Tree/perennial (low sensitivity across stages)
    "citrus": {
        "BARE_SOIL": 0.0, "EMERGENCE": 0.1, "VEGETATIVE": 0.15,
        "REPRODUCTIVE": 0.50, "MATURITY": 0.3, "SENESCENCE": 0.1, "UNKNOWN": 0.3,
    },
    "olive": {
        "BARE_SOIL": 0.0, "EMERGENCE": 0.1, "VEGETATIVE": 0.15,
        "REPRODUCTIVE": 0.65, "MATURITY": 0.3, "SENESCENCE": 0.1, "UNKNOWN": 0.3,
    },
}

def _get_ky(crop_type: str, stage: str) -> float:
    """Get crop-specific Ky factor. Falls back to default."""
    crop_key = crop_type.lower().strip() if crop_type else "_default"
    table = _KY_BY_CROP_STAGE.get(crop_key, _KY_BY_CROP_STAGE["_default"])
    return table.get(stage, 0.5)

# Mutual exclusion pairs: logically contradictory diagnoses
_MUTUAL_EXCLUSION_PAIRS = [
    (ProblemType.WATER_STRESS.value, ProblemType.WATERLOGGING.value),
    (ProblemType.LOGGING_CLEARING.value, ProblemType.HARVEST_EVENT.value),
]

class DiagnosisEngine:
    """
    Research-Grade Probabilistic Inference.
    Separates BELIEF (Log-Odds Probability) from TRUST (Confidence).
    """
    
    def _to_log_odds(self, p: float) -> float:
        p = max(0.001, min(0.999, p))
        return math.log(p / (1 - p))
        
    def _to_prob(self, lo: float) -> float:
        return 1.0 / (1.0 + math.exp(-lo))
    
    def _add_evidence(
        self, 
        feature: str, 
        window: str, 
        value: Any, 
        score: float, 
        weight: float, 
        trace: List[EvidenceTerm]
    ) -> float:
        """Generates EvidenceTerm and returns logit delta."""
        # Bound score to [-1, 1] for safety
        score = max(-1.0, min(1.0, score))
        
        delta = score * weight
        term = EvidenceTerm(
            feature_name=feature,
            window=window,
            value=float(value) if isinstance(value, (int, float)) else 0.0,
            score=score,
            weight=weight,
            contribution=delta
        )
        trace.append(term)
        return delta

    def _build_diagnosis(
        self, 
        problem_id: str, 
        prob: float, 
        severity: float, 
        conf: float, 
        trace: List[EvidenceTerm], 
        features: DecisionFeatures,
        drivers_used: List[Driver]
    ) -> Diagnosis:
        """
        Standardized Factory for v4.0 Contract.
        Populates problem_class, drivers_used, drivers_missing.
        """
        p_def = PROBLEM_DB.get(ProblemType(problem_id), None)
        p_class = p_def.problem_class if p_def else "SYSTEM"
        
        # Intersect features.missing_inputs (List[Driver]) with drivers_used
        missing_rel = [d for d in drivers_used if d in features.missing_inputs]
        
        return Diagnosis(
            problem_id=problem_id,
            probability=prob,
            severity=severity,
            confidence=conf,
            evidence_trace=trace,
            contra_trace=[],
            supports={}, 
            problem_class=p_class,
            drivers_used=drivers_used,
            drivers_missing=missing_rel
        )

    def diagnose(self, features: DecisionFeatures, context: PlotContext,
                 weather_forecast: Optional[List[Dict]] = None) -> List[Diagnosis]:
        forecast = weather_forecast or []
        diagnoses = []
        
        # --- 1. Water Stress (Abiotic) ---
        d_ws = self._diagnose_water_stress(features, context)
        if d_ws: diagnoses.append(d_ws)
        
        # --- 2. Waterlogging (Abiotic) ---
        d_wl = self._diagnose_waterlogging(features)
        if d_wl: diagnoses.append(d_wl)
        
        # --- 3. Heat Stress (Abiotic) ---
        d_ht = self._diagnose_heat_stress(features)
        if d_ht: diagnoses.append(d_ht)

        # --- 4. Cold Stress (Abiotic) ---
        d_cs = self._diagnose_cold_stress(features, context)
        if d_cs: diagnoses.append(d_cs)

        # --- 5. Nitrogen Deficiency (Abiotic) ---
        d_n = self._diagnose_n_deficiency(features, d_ws.probability if d_ws else 0.0)
        if d_n: diagnoses.append(d_n)
        
        # --- 6. Logging / Clearing (Structural) ---
        d_log = self._diagnose_structure_loss(features)
        if d_log: diagnoses.append(d_log)
        
        # --- 7. Biotic Risks ---
        d_fung = self._diagnose_fungal_risk(features)
        if d_fung: diagnoses.append(d_fung)
        
        # --- 8. Events ---
        d_harv = self._diagnose_harvest(features)
        if d_harv: diagnoses.append(d_harv)
        
        d_till = self._diagnose_tillage(features)
        if d_till: diagnoses.append(d_till)

        # --- 9. Biotic Risks (Extended) ---
        d_salt = self._diagnose_salinity_risk(features)
        if d_salt: diagnoses.append(d_salt)

        d_insect = self._diagnose_insect_pressure(features)
        if d_insect: diagnoses.append(d_insect)

        # --- 10. Data Quality ---
        d_artifact = self._diagnose_data_artifact(features)
        if d_artifact: diagnoses.append(d_artifact)

        d_gap = self._diagnose_data_gap(features)
        if d_gap: diagnoses.append(d_gap)

        # --- 11. Transpiration Failure (Energy Balance) ---
        d_tf = self._diagnose_transpiration_failure(features, d_ws.probability if d_ws else 0.0)
        if d_tf: diagnoses.append(d_tf)

        # --- 12. Drone: Weed Pressure ---
        d_weed = self._diagnose_weed_pressure(features)
        if d_weed: diagnoses.append(d_weed)

        # --- 13. Drone: Mechanical Damage ---
        d_mech = self._diagnose_mechanical_damage(features)
        if d_mech: diagnoses.append(d_mech)

        # --- 14. Lodging (ENH-6) ---
        d_lodge = self._diagnose_lodging(features)
        if d_lodge: diagnoses.append(d_lodge)

        # --- 15. Frost Risk — forecast-aware (ENH-4) ---
        d_frost = self._diagnose_frost_risk(features)
        if d_frost: diagnoses.append(d_frost)

        # --- Post-processing: Mutual Exclusion (ENH-3) ---
        self._apply_mutual_exclusion(diagnoses)

        # Sort by Probability (Belief)
        diagnoses.sort(key=lambda x: x.probability, reverse=True)
        return diagnoses

    # --- Specific Diagnosis Logics ---

    def _diagnose_water_stress(self, f: DecisionFeatures, context: PlotContext = None) -> Optional[Diagnosis]:
        # Prior: Low (0.1)
        lo = self._to_log_odds(0.1)
        trace = []
        
        # Evidence: Rain deficit
        if f.rain_sum_14d < 5.0:
            lo += self._add_evidence("rain_sum_14d", "14d", f.rain_sum_14d, 1.0, 2.0, trace)
        elif f.rain_sum_14d > 30.0:
            # Strong contraindication if rain is abundant (Expert Grade: lowered from 40 to 30)
            lo += self._add_evidence("rain_sum_14d", "14d", f.rain_sum_14d, -1.0, 4.0, trace)
            
        if f.days_since_rain > 12: # increased from 10 to 12
             lo += self._add_evidence("days_since_rain", "current", f.days_since_rain, 1.0, 1.5, trace)

        
        if f.has_anomaly and f.anomaly_type in ["DROP", "STALL"]:
            lo += self._add_evidence("ndvi_anomaly", "current", f.anomaly_severity, 1.0, 1.5, trace)
            
        # Contraindication: Waterlogging signals
        if f.saturation_days > 2:
            lo += self._add_evidence("saturation_days", "7d", f.saturation_days, -1.0, 3.0, trace)

        # ── Energy Balance Evidence (LST from L0→L1→L2) ──
        # These signals come from satellite thermal data ingested at L0

        if f.lst_available:
            # Canopy-air temperature differential: plant overheating
            if f.canopy_air_delta_c > 3.0:
                score = min(1.0, (f.canopy_air_delta_c - 3.0) / 7.0)
                lo += self._add_evidence(
                    "canopy_air_delta", "current", f.canopy_air_delta_c,
                    score, 2.0, trace
                )
            elif f.canopy_air_delta_c < -1.0:
                # Plant is cooler than air → transpiring well (contraindication)
                lo += self._add_evidence(
                    "canopy_air_delta", "current", f.canopy_air_delta_c,
                    -0.8, 1.5, trace
                )

        # ESI: direct evaporative stress signal
        # FIX (BUG-1): Restructured to handle full ESI range.
        # Old code had unreachable `elif esi < 0.1` inside `if esi > 0.1` guard.
        if f.esi > 0.4:
            # Strong evaporative stress — stomata closing
            score = min(1.0, f.esi / 0.8)
            weight = 1.5 if f.lst_available else 0.5  # Much weaker if VPD-only proxy
            lo += self._add_evidence("esi", "current", f.esi, score, weight, trace)
        elif f.esi > 0.1:
            # Mild evaporative stress — early warning
            score = min(0.5, f.esi / 0.8)
            weight = 0.8 if f.lst_available else 0.3
            lo += self._add_evidence("esi", "current", f.esi, score, weight, trace)
        elif f.esi < 0.05 and f.lst_available:
            # ESI near zero + LST confirmed = plant is transpiring well (contraindication)
            lo += self._add_evidence("esi", "current", f.esi, -0.5, 1.0, trace)

        # SCI-1: VPD evidence (atmospheric demand driver)
        if f.vpd_kpa > 3.0:
            score = min(1.0, (f.vpd_kpa - 2.0) / 4.0)
            lo += self._add_evidence("vpd", "current", f.vpd_kpa, score, 1.5, trace)
        elif f.vpd_kpa > 0.0 and f.vpd_kpa < 1.0:
            # Low VPD = low evaporative demand (contraindication)
            lo += self._add_evidence("vpd", "current", f.vpd_kpa, -0.3, 0.8, trace)

        # Transpiration efficiency: below 50% = stomatal distress
        if f.transpiration_efficiency < 0.5 and f.lst_available:
            score = min(1.0, (0.5 - f.transpiration_efficiency) / 0.4)
            lo += self._add_evidence(
                "transpiration_efficiency", "current", f.transpiration_efficiency,
                score, 1.5, trace
            )
            
        prob = self._to_prob(lo)
        
        # Confidence Calculation (Lock: only subtract)
        # Drivers: RAIN, NDVI, TEMP, LST, ET0
        conf = 1.0
        if Driver.RAIN in f.missing_inputs: conf -= 0.5
        if not f.optical_available: conf -= 0.2
        # LST boosts confidence when available (doesn't penalize when missing)
        if f.lst_available:
            conf = min(1.0, conf + 0.1)
        conf = max(0.0, conf)
        
        drivers_used = [Driver.RAIN, Driver.NDVI, Driver.TEMP]
        if f.lst_available:
            drivers_used.extend([Driver.LST, Driver.ET0])
        
        if prob > 0.2:
            # ENH-2/SCI-5: Crop-specific Ky stage multiplier for severity
            crop = context.crop_type if context else "unknown"
            ky = _get_ky(crop, f.current_stage)
            # ENH-5: Evidence-proportional severity
            evidence_severity = self._compute_evidence_severity(trace)
            base_severity = f.anomaly_severity if f.has_anomaly else evidence_severity
            severity = min(1.0, base_severity * (0.5 + ky))  # Ky scales severity

            return self._build_diagnosis(
                problem_id=ProblemType.WATER_STRESS.value,
                prob=prob,
                severity=severity,
                conf=conf,
                trace=trace,
                features=f,
                drivers_used=drivers_used
            )
        return None

    def _diagnose_waterlogging(self, f: DecisionFeatures) -> Optional[Diagnosis]:
        lo = self._to_log_odds(0.05) # Rare
        trace = []
        
        if f.saturation_days >= 2:
            lo += self._add_evidence("saturation_days", "7d", f.saturation_days, 1.0, 2.5, trace)
        
        if f.rain_sum_7d > 50.0:
            lo += self._add_evidence("rain_sum_7d", "7d", f.rain_sum_7d, 1.0, 1.5, trace)
            
        if f.has_anomaly and f.anomaly_type == "DROP":
            lo += self._add_evidence("ndvi_drop", "current", f.anomaly_severity, 0.5, 1.0, trace)

        # Contraindication: dry conditions
        if f.rain_sum_7d < 5.0 and f.days_since_rain > 7:
            lo += self._add_evidence("dry_conditions", "7d", f.rain_sum_7d, -1.0, 2.0, trace)
            
        prob = self._to_prob(lo)
        conf = 1.0
        if not f.rain_available: conf -= 0.5
        conf = max(0.0, conf)
        
        if prob > 0.3:
            # BUG-6 FIX: evidence-proportional severity
            severity = min(1.0, self._compute_evidence_severity(trace) * 1.3)
            return self._build_diagnosis(ProblemType.WATERLOGGING.value, prob, severity, conf, trace, f, [Driver.RAIN, Driver.SAR_VV, Driver.NDVI])
        return None

    def _diagnose_heat_stress(self, f: DecisionFeatures) -> Optional[Diagnosis]:
        """BUG-7 FIX: Multi-evidence heat stress diagnosis.

        Evidence sources:
          - Observed heat days (temp_max > 35°C)
          - Forecast heat days (proactive warning)
          - ESI (evaporative stress from heat-driven demand)
          - VPD (atmospheric demand driver)
          - Canopy overheating (direct thermal observation)
          - Growth velocity decline (heat damage effect)
          - Stage sensitivity (reproductive = critical)
        """
        lo = self._to_log_odds(0.1)
        trace = []
        
        # Primary: observed heat stress days
        if f.heat_stress_days > 2:
            lo += self._add_evidence("heat_days", "7d", f.heat_stress_days, 1.0, 2.5, trace)
        elif f.heat_stress_days > 0:
            lo += self._add_evidence("heat_days", "7d", f.heat_stress_days, 0.5, 1.5, trace)

        # Forecast heat wave (proactive)
        if f.forecast_heat_days >= 3:
            lo += self._add_evidence("forecast_heat", "7d_forecast", f.forecast_heat_days, 1.0, 2.0, trace)
        elif f.forecast_heat_days >= 1:
            lo += self._add_evidence("forecast_heat", "7d_forecast", f.forecast_heat_days, 0.5, 1.0, trace)

        # VPD > 3 kPa = extreme atmospheric demand
        if f.vpd_kpa > 3.0:
            score = min(1.0, (f.vpd_kpa - 2.0) / 4.0)
            lo += self._add_evidence("vpd_heat", "current", f.vpd_kpa, score, 1.5, trace)

        # Canopy overheating from LST
        if f.lst_available and f.canopy_air_delta_c > 5.0:
            score = min(1.0, (f.canopy_air_delta_c - 3.0) / 7.0)
            lo += self._add_evidence("canopy_overheating", "current", f.canopy_air_delta_c, score, 2.0, trace)

        # ESI corroboration (evaporative stress from heat)
        if f.esi > 0.4:
            lo += self._add_evidence("esi_heat", "current", f.esi, min(1.0, f.esi / 0.8), 1.0, trace)

        # Growth velocity decline (heat damage effect)
        if f.growth_velocity_7d < 0.002 and f.current_stage in ["VEGETATIVE", "REPRODUCTIVE"]:
            lo += self._add_evidence("growth_stall", "7d", f.growth_velocity_7d, 0.5, 1.0, trace)

        # Stage sensitivity
        if f.current_stage == "REPRODUCTIVE":
            lo += self._add_evidence("stage_sensitive", "current", 1.0, 0.5, 1.0, trace)

        # Contraindication: cool conditions
        if f.heat_stress_days == 0 and f.forecast_heat_days == 0 and f.vpd_kpa < 1.5:
            lo += self._add_evidence("cool_conditions", "current", 0.0, -0.8, 2.0, trace)

        prob = self._to_prob(lo)
        conf = 1.0
        if Driver.TEMP in f.missing_inputs: conf = 0.0 # Critical missing
        
        if prob > 0.4:
            # BUG-6 FIX: evidence-proportional severity
            severity = min(1.0, self._compute_evidence_severity(trace) * 1.2)
            drivers = [Driver.TEMP]
            if f.lst_available: drivers.append(Driver.LST)
            return self._build_diagnosis(ProblemType.HEAT_STRESS.value, prob, severity, conf, trace, f, drivers)
        return None

    def _diagnose_cold_stress(self, f: DecisionFeatures, context: PlotContext = None) -> Optional[Diagnosis]:
        """SCI-2: Cold stress with Ky stage multiplier."""
        lo = self._to_log_odds(0.05)
        trace = []
        
        if f.cold_stress_days > 2:
             lo += self._add_evidence("cold_days", "7d", f.cold_stress_days, 1.0, 3.0, trace)
        elif f.cold_stress_days > 0:
             lo += self._add_evidence("cold_days", "7d", f.cold_stress_days, 0.5, 1.5, trace)

        # Corroboration: forecast cold days
        if f.forecast_cold_days >= 2:
            lo += self._add_evidence("forecast_cold", "7d_forecast", f.forecast_cold_days, 0.7, 1.5, trace)

        # Stage sensitivity (SCI-2)
        crop = context.crop_type if context else "unknown"
        ky = _get_ky(crop, f.current_stage)
        if ky > 0.5:
            lo += self._add_evidence("stage_sensitivity", "current", ky, 0.5, 1.0, trace)

        prob = self._to_prob(lo)
        conf = 1.0
        if Driver.TEMP in f.missing_inputs: conf = 0.0 
        
        if prob > 0.4:
            severity = min(1.0, self._compute_evidence_severity(trace) * (0.5 + ky))
            return self._build_diagnosis(ProblemType.COLD_STRESS.value, prob, severity, conf, trace, f, [Driver.TEMP])
        return None

    def _diagnose_n_deficiency(self, f: DecisionFeatures, prob_water_stress: float) -> Optional[Diagnosis]:
        # Logic: Low Growth Velocity AND No Water Stress AND In Vegetative Stage
        lo = self._to_log_odds(0.05)
        trace = []
        
        # 1. Growth Velocity Low? (Proxy for Chlorosis/Stunting)
        if f.growth_velocity_7d < 0.005 and f.current_stage in ["VEGETATIVE", "REPRODUCTIVE"]:
            lo += self._add_evidence("growth_velocity", "7d", f.growth_velocity_7d, 1.0, 1.5, trace)
            
        # 2. Contraindication: Water Stress explains it?
        if prob_water_stress > 0.6:
            lo += self._add_evidence("water_stress_explain", "current", prob_water_stress, -1.0, 2.0, trace)
            
        prob = self._to_prob(lo)
        conf = 1.0
        if not f.optical_available: conf -= 0.3
        conf *= f.stage_confidence 
        
        if prob > 0.3:
            severity = min(1.0, self._compute_evidence_severity(trace) * 1.0)
            return self._build_diagnosis(ProblemType.NUTRIENT_DEFICIENCY_N.value, prob, severity, conf, trace, f, [Driver.NDVI])
        return None

    def _diagnose_structure_loss(self, f: DecisionFeatures) -> Optional[Diagnosis]:
        lo = self._to_log_odds(0.01)
        trace = []
        
        # Primary Driver: SAR VV Increase (Roughness) or textural change
        # User spec: "never produce high confidence if sar_coverage < threshold"
        
        if f.sar_vv_trend_7d > 0.5:
            lo += self._add_evidence("sar_vv_trend", "7d", f.sar_vv_trend_7d, 1.0, 4.0, trace)
        elif f.sar_vv_trend_7d < -0.5:
             lo += self._add_evidence("sar_vv_trend", "7d", f.sar_vv_trend_7d, -1.0, 2.0, trace)
             
        if f.has_anomaly and f.anomaly_type == "DROP":
             lo += self._add_evidence("ndvi_drop", "current", f.anomaly_severity, 1.0, 1.0, trace)
             
        prob = self._to_prob(lo)
        
        # Strict Confidence Gating
        conf = 1.0
        if not f.sar_available: 
            conf = 0.0 # Cannot diagnose logging without SAR structure data
            
        if prob > 0.2 and conf > 0.0:
            return self._build_diagnosis(ProblemType.LOGGING_CLEARING.value, prob, 1.0, conf, trace, f, [Driver.SAR_VV, Driver.NDVI])
        return None

    def _diagnose_fungal_risk(self, f: DecisionFeatures) -> Optional[Diagnosis]:
        """BUG-8 FIX: Fungal disease risk using temperature×humidity interaction.

        Fusarium Head Blight (FHB) requires: warm + wet + flowering.
        Leaf rust: moderate temp + prolonged leaf wetness.
        General: >20mm rain/7d + temp 15-30°C = high risk.

        Evidence:
          - Rain > 20mm/7d (prolonged wetness)
          - Temperature in 15-30°C range (fungal optimum)
          - Reproductive/vegetative stage (dense canopy = humidity trap)
          - Forecast rain (proactive warning)
          - Growth velocity decline (fungal damage effect)
        Contraindication:
          - Dry conditions
          - Very hot (>38°C kills most fungi)
          - Bare soil (no host)
        """
        lo = self._to_log_odds(0.1)
        trace = []

        # Primary: wet conditions (prolonged leaf wetness proxy)
        if f.rain_sum_7d > 20.0:
            score = min(1.0, (f.rain_sum_7d - 15.0) / 30.0)
            lo += self._add_evidence("wet_conditions", "7d", f.rain_sum_7d, score, 2.0, trace)

        # Temperature in fungal optimum range (15-30°C)
        # Note: heat_stress_days > 3 means too hot for most fungi
        if f.heat_stress_days == 0 and not (f.cold_stress_days > 2):
            # Moderate temperature = good for fungi
            lo += self._add_evidence("temp_optimal", "7d", 1.0, 0.5, 1.0, trace)
        elif f.heat_stress_days > 3:
            # Very hot = kills most fungi (contraindication)
            lo += self._add_evidence("too_hot_for_fungi", "7d", f.heat_stress_days, -0.8, 2.0, trace)

        # Stage sensitivity: flowering = FHB critical window
        if f.current_stage == "REPRODUCTIVE":
            lo += self._add_evidence("flowering_fhb_window", "current", 1.0, 1.0, 2.0, trace)
        elif f.current_stage in ["VEGETATIVE"]:
            lo += self._add_evidence("vegetative_canopy", "current", 1.0, 0.5, 1.0, trace)
        elif f.current_stage == "BARE_SOIL":
            lo += self._add_evidence("no_host", "current", 0.0, -1.0, 3.0, trace)

        # Forecast rain = early warning
        if f.forecast_rain_3d > 15.0:
            lo += self._add_evidence("forecast_rain", "3d_forecast", f.forecast_rain_3d, 0.7, 1.5, trace)

        # Contraindication: dry
        if f.rain_sum_7d < 5.0 and f.days_since_rain > 7:
            lo += self._add_evidence("dry_conditions", "7d", f.rain_sum_7d, -1.0, 3.0, trace)

        prob = self._to_prob(lo)
        conf = 1.0
        if Driver.RAIN in f.missing_inputs: conf = 0.0
        
        if prob > 0.4:
            severity = min(1.0, self._compute_evidence_severity(trace) * 1.1)
            return self._build_diagnosis(ProblemType.FUNGAL_DISEASE_RISK.value, prob, severity, conf, trace, f, [Driver.RAIN, Driver.TEMP])
        return None

    def _diagnose_harvest(self, f: DecisionFeatures) -> Optional[Diagnosis]:
        # Sharp Drop + SAR Change + Late Stage
        lo = self._to_log_odds(0.01)
        trace = []
        
        if f.current_stage in ["MATURITY", "SENESCENCE"]:
            lo += self._add_evidence("stage_mature", "current", 1.0, 1.0, 2.0, trace)
            
        if f.has_anomaly and f.anomaly_type == "DROP":
             lo += self._add_evidence("ndvi_drop", "current", f.anomaly_severity, 1.0, 2.0, trace)
             
        if abs(f.sar_roughness_change) > 0.5: # Structure changed
             lo += self._add_evidence("sar_roughness", "7d", f.sar_roughness_change, 1.0, 2.0, trace)
             
        prob = self._to_prob(lo)
        conf = f.spatial_confidence
        
        if prob > 0.5:
             return self._build_diagnosis(ProblemType.HARVEST_EVENT.value, prob, 0.0, conf, trace, f, [Driver.SAR_VV, Driver.NDVI])
        return None

    def _diagnose_tillage(self, f: DecisionFeatures) -> Optional[Diagnosis]:
        # Bare Soil + Roughness Change
        lo = self._to_log_odds(0.01)
        trace = []
        
        if f.current_stage == "BARE_SOIL":
             lo += self._add_evidence("stage_bare", "current", 1.0, 1.0, 1.0, trace)
             
        if f.sar_roughness_change > 1.0: # Significant roughening
             lo += self._add_evidence("sar_roughening", "7d", f.sar_roughness_change, 1.0, 3.0, trace)
             
        prob = self._to_prob(lo)
        conf = 1.0 if f.sar_available else 0.0
        
        if prob > 0.5:
             return self._build_diagnosis(ProblemType.TILLAGE_EVENT.value, prob, 0.0, conf, trace, f, [Driver.SAR_VV, Driver.NDVI])
        return None

    def _diagnose_salinity_risk(self, f: DecisionFeatures) -> Optional[Diagnosis]:
        # Salinity often presents as "White Crust" (High Reflectance) + Stunted Growth
        # Proxy: Low Growth Velocity but High Optical Brightness (Not available in current features, using NDVI/Veg only)
        # Heuristic: Persistent Low NDVI in specific zones (Spatial Stability HETEROGENEOUS)
        
        lo = self._to_log_odds(0.01) # Rare
        trace = []
        
        if f.spatial_stability == "HETEROGENEOUS":
            lo += self._add_evidence("spatial_heterogeneity", "current", 1.0, 1.0, 2.0, trace)
            
        if f.growth_velocity_7d < 0.002: # Stunted
             lo += self._add_evidence("stunted_growth", "7d", f.growth_velocity_7d, 1.0, 1.0, trace)
             
        prob = self._to_prob(lo)
        
        # Low confidence without Soil EC data
        if prob > 0.3:
            severity = min(1.0, self._compute_evidence_severity(trace) * 0.9)
            return self._build_diagnosis(ProblemType.SALINITY_RISK.value, prob, severity, 0.3, trace, f, [Driver.NDVI]) # Conf 0.3 (Low)
        return None

    def _diagnose_insect_pressure(self, f: DecisionFeatures) -> Optional[Diagnosis]:
        # Pests = Patchy removal (High Spatial Variance) + Rapid Drop
        lo = self._to_log_odds(0.05)
        trace = []
        
        if f.has_anomaly and f.anomaly_type == "DROP":
             lo += self._add_evidence("ndvi_drop", "current", f.anomaly_severity, 1.0, 1.5, trace)
             
        if f.spatial_stability == "TRANSIENT_VAR": # rapid change in variance
             lo += self._add_evidence("transient_variance", "current", 1.0, 1.0, 2.0, trace)
             
        # Contraindication: Rain (insects often hide/wash off, fungal promotes)
        # Weak logic but acceptable for verifying the slot exists
        
        prob = self._to_prob(lo)
        conf = f.spatial_confidence
        
        if prob > 0.3:
            # NUM-3 FIX: evidence-proportional severity (was hardcoded 0.6)
            severity = min(1.0, self._compute_evidence_severity(trace) * 1.1)
            return self._build_diagnosis(ProblemType.INSECT_PRESSURE_RISK.value, prob, severity, conf, trace, f, [Driver.NDVI])
        return None

    def _diagnose_data_gap(self, f: DecisionFeatures) -> Optional[Diagnosis]:
        # Only count CORE drivers for data gap diagnosis.
        # Enhancement drivers (LST, ET0) improve confidence when present
        # but their absence is not a data gap — it's normal degradation.
        CORE_DRIVERS = {Driver.RAIN, Driver.TEMP, Driver.SAR_VV, Driver.NDVI}
        core_missing = [d for d in f.missing_inputs if d in CORE_DRIVERS]
        if not core_missing: return None
        
        count = len(core_missing)
        
        # User spec: "Confidence must be computed from data quality only"
        # If we have degraded components (e.g. valid checks failed elsewhere), reduce conf.
        # But for 'DATA_GAP' diagnosis itself, we are confident that data IS missing.
        # However, to avoid 1.0/1.0 appearing authoritative in degraded mode:
        
        conf = 1.0
        # If we have critical missing inputs (SAR/RAIN), we reduce confidence slightly
        # to ensure it doesn't look like a "perfect" diagnosis in a broken system.
        if Driver.SAR_VV in core_missing or Driver.RAIN in core_missing:
             conf = 0.8
             
        # LOGIC-4 FIX: divisor is 4.0 (matching 4 core drivers: RAIN, TEMP, SAR_VV, NDVI)
        return self._build_diagnosis(
            ProblemType.DATA_GAP.value,
            1.0, 
            count / 4.0, 
            conf,
            [EvidenceTerm("missing_inputs", "current", count, 1.0, 4.0, count)],
            f,
            []
        )

    def _diagnose_data_artifact(self, f: DecisionFeatures) -> Optional[Diagnosis]:
        # Simple heuristic: Extreme Values or Physical Impossibility
        # Not fully implemented in features yet, but can use Sar Roughness extreme
        if abs(f.sar_roughness_change) > 5.0: # Very suspicious
             return self._build_diagnosis(
                ProblemType.DATA_ARTIFACT.value,
                0.8,
                0.5,
                1.0,
                [EvidenceTerm("extreme_sar_roughness", "7d", f.sar_roughness_change, 1.0, 5.0, 5.0)],
                f,
                [Driver.SAR_VV]
             )
        return None

    def _diagnose_transpiration_failure(self, f: DecisionFeatures, prob_water_stress: float) -> Optional[Diagnosis]:
        """Diagnose transpiration cooling failure from satellite LST.

        The plant's primary cooling mechanism is transpiration (sweating).
        When it fails, the canopy heats up above ambient air temperature.
        This is a DIRECT physical observation of water stress — not a proxy.

        Fires when:
          - ESI > 0.6 (evaporation significantly below potential)
          - Canopy temp > air temp by 5°C+ (stomata closed, cooling failed)
          - LST satellite data is actually available

        Data source: L0 Landsat/ECOSTRESS thermal → L1 environment → L2 → L3
        """
        if not f.lst_available:
            return None  # Cannot diagnose without satellite thermal data

        lo = self._to_log_odds(0.05)  # Low prior — needs strong physical evidence
        trace = []

        # Primary evidence: canopy overheating (T_canopy >> T_air)
        if f.canopy_air_delta_c > 5.0:
            score = min(1.0, (f.canopy_air_delta_c - 5.0) / 5.0)
            lo += self._add_evidence(
                "canopy_overheating", "current", f.canopy_air_delta_c,
                score, 3.0, trace
            )

        # Corroborating evidence: ESI confirms evaporative shutdown
        if f.esi > 0.6:
            score = min(1.0, (f.esi - 0.4) / 0.5)
            lo += self._add_evidence(
                "esi_shutdown", "current", f.esi,
                score, 2.5, trace
            )

        # Corroborating: CWSI > 0.6 (crop water stress confirmed)
        if f.cwsi > 0.6:
            lo += self._add_evidence(
                "cwsi", "current", f.cwsi,
                min(1.0, f.cwsi), 1.5, trace
            )

        # Corroborating: existing water stress boosts probability
        if prob_water_stress > 0.5:
            lo += self._add_evidence(
                "water_stress_corroboration", "current", prob_water_stress,
                0.5, 1.0, trace
            )

        # Contraindication: If canopy is cooler than air, transpiration is working
        if f.canopy_air_delta_c < 0:
            lo += self._add_evidence(
                "canopy_cooling_ok", "current", f.canopy_air_delta_c,
                -1.0, 4.0, trace  # Strong contraindication
            )

        # ET deficit magnitude (mm/day gap)
        if f.et_deficit_mm > 2.0:
            lo += self._add_evidence(
                "et_deficit", "current", f.et_deficit_mm,
                min(1.0, f.et_deficit_mm / 5.0), 1.0, trace
            )

        prob = self._to_prob(lo)

        # Severity: proportional to ESI (direct measure of cooling failure)
        severity = min(1.0, f.esi * 1.2) if f.esi > 0.4 else 0.3

        # Confidence: high when we have LST + corroborating rain data
        conf = 0.7  # LST is direct physical observation
        if Driver.RAIN not in f.missing_inputs:
            conf += 0.15  # Rain corroborates water availability
        if f.et_potential_mm > 0:
            conf += 0.10  # ET0 from weather station available
        conf = min(1.0, conf)

        if prob > 0.4:
            return self._build_diagnosis(
                problem_id=ProblemType.TRANSPIRATION_FAILURE.value,
                prob=prob,
                severity=severity,
                conf=conf,
                trace=trace,
                features=f,
                drivers_used=[Driver.LST, Driver.ET0, Driver.TEMP, Driver.RAIN]
            )
        return None

    def _diagnose_weed_pressure(self, f: DecisionFeatures) -> Optional[Diagnosis]:
        """Diagnose weed competition from drone structural intelligence.

        Fires when drone RGB analysis detected weed patches via L0→L1→L2.
        Primary drivers:
          - weed_pressure_severity (from L2 BIOTIC stress with weed driver)
          - canopy_uniformity_cv (high CV = patchy growth = possible weed zones)
          - bare_soil_ratio (exposed soil in crop rows = weed opportunity)

        Data source: L0 DroneRGBEngine → L1 structural adapter → L2 stress → L3
        """
        if not f.has_drone_structural:
            return None  # Cannot diagnose without drone structural data

        lo = self._to_log_odds(0.05)  # Low prior — needs drone evidence
        trace = []

        # Primary evidence: L2-attributed weed pressure severity
        if f.weed_pressure_severity > 0.1:
            score = min(1.0, f.weed_pressure_severity / 0.7)
            lo += self._add_evidence(
                "weed_pressure_severity", "current", f.weed_pressure_severity,
                score, 3.0, trace
            )

        # Corroborating: high canopy non-uniformity
        if f.canopy_uniformity_cv > 0.3:
            score = min(1.0, (f.canopy_uniformity_cv - 0.2) / 0.5)
            lo += self._add_evidence(
                "canopy_uniformity_cv", "current", f.canopy_uniformity_cv,
                score, 1.5, trace
            )

        # Corroborating: bare soil patches (weeds often found in gaps)
        if f.bare_soil_ratio > 0.15:
            score = min(1.0, (f.bare_soil_ratio - 0.1) / 0.4)
            lo += self._add_evidence(
                "bare_soil_ratio", "current", f.bare_soil_ratio,
                score, 1.0, trace
            )

        # Contraindication: if stage is BARE_SOIL or SENESCENCE, suppress
        if f.current_stage in ["BARE_SOIL", "SENESCENCE"]:
            lo += self._add_evidence(
                "stage_suppression", "current", 0.0,
                -1.0, 3.0, trace
            )

        prob = self._to_prob(lo)

        # Severity: proportional to weed pressure index
        severity = min(1.0, f.weed_pressure_severity * 1.2) if f.weed_pressure_severity > 0.1 else 0.2

        # Confidence: drone data is direct observation, moderately high
        conf = 0.70
        if f.weed_pressure_severity > 0.3:
            conf += 0.15  # Stronger L2 attribution
        conf = min(1.0, conf)

        if prob > 0.3:
            return self._build_diagnosis(
                problem_id=ProblemType.WEED_PRESSURE.value,
                prob=prob,
                severity=severity,
                conf=conf,
                trace=trace,
                features=f,
                drivers_used=[Driver.NDVI]  # Drone-derived, NDVI is the closest driver enum
            )
        return None

    def _diagnose_mechanical_damage(self, f: DecisionFeatures) -> Optional[Diagnosis]:
        """Diagnose structural/mechanical crop damage from drone data.

        Fires when drone detected structural damage (row breaks, gaps,
        equipment tracks, hail damage) via L0→L1→L2 MECHANICAL stress.

        Primary drivers:
          - mechanical_damage_severity (from L2 MECHANICAL stress type)
          - NDVI anomaly correlation (vegetation decline confirms physical damage)

        Data source: L0 DroneRGBEngine → L1 structural adapter → L2 stress → L3
        """
        if not f.has_drone_structural:
            return None

        if not f.mechanical_damage_detected:
            return None  # No mechanical damage signal from L2

        lo = self._to_log_odds(0.10)  # Moderate prior when L2 already detected it
        trace = []

        # Primary evidence: L2-attributed mechanical damage severity
        if f.mechanical_damage_severity > 0.1:
            score = min(1.0, f.mechanical_damage_severity / 0.6)
            lo += self._add_evidence(
                "mechanical_damage_severity", "current", f.mechanical_damage_severity,
                score, 3.5, trace
            )

        # Corroborating: NDVI anomaly confirms vegetation loss at damage site
        if f.has_anomaly and f.anomaly_type == "DROP":
            lo += self._add_evidence(
                "ndvi_drop_corroboration", "current", f.anomaly_severity,
                min(1.0, f.anomaly_severity), 1.5, trace
            )

        # Corroborating: missing trees in orchard mode
        if f.missing_tree_count > 0 and f.tree_count > 0:
            missing_pct = f.missing_tree_count / max(1, f.tree_count)
            if missing_pct > 0.02:  # >2% missing
                lo += self._add_evidence(
                    "missing_trees", "current", f.missing_tree_count,
                    min(1.0, missing_pct * 10.0), 2.0, trace
                )

        prob = self._to_prob(lo)

        # Severity: direct from damage magnitude
        severity = min(1.0, f.mechanical_damage_severity)

        # Confidence: high (drone is direct observation)
        conf = 0.75
        if f.has_anomaly and f.anomaly_type == "DROP":
            conf += 0.10  # NDVI corroborates
        conf = min(1.0, conf)

        if prob > 0.3:
            return self._build_diagnosis(
                problem_id=ProblemType.MECHANICAL_DAMAGE.value,
                prob=prob,
                severity=severity,
                conf=conf,
                trace=trace,
                features=f,
                drivers_used=[Driver.NDVI, Driver.SAR_VV]
            )
        return None

    def _diagnose_lodging(self, f: DecisionFeatures) -> Optional[Diagnosis]:
        """Diagnose crop lodging (ENH-6).

        Lodging occurs when stems bend or break under wind + rain + crop weight.
        Most critical during reproductive/maturity when grain head is heavy.

        Evidence:
          - Heavy recent rain (rain_sum_7d > 30mm) — water-weakened stems
          - Reproductive/maturity stage — tall, heavy canopy
          - SAR roughness change — canopy structure disruption
          - NDVI spatial heterogeneity — patchy damage pattern

        Contraindication:
          - Bare soil / emergence — no canopy to lodge
          - No SAR data — cannot observe structural change
        """
        lo = self._to_log_odds(0.02)  # Rare event
        trace = []

        # Heavy rain weakens stems
        if f.rain_sum_7d > 30.0:
            score = min(1.0, (f.rain_sum_7d - 25.0) / 40.0)
            lo += self._add_evidence("heavy_rain", "7d", f.rain_sum_7d, score, 1.5, trace)

        # Tall crop at vulnerable stage
        if f.current_stage in ["REPRODUCTIVE", "MATURITY"]:
            lo += self._add_evidence("stage_vulnerable", "current", 1.0, 1.0, 2.0, trace)
        elif f.current_stage in ["BARE_SOIL", "EMERGENCE"]:
            lo += self._add_evidence("stage_impossible", "current", 0.0, -1.0, 4.0, trace)

        # SAR roughness change (structural disruption)
        if abs(f.sar_roughness_change) > 0.5:
            lo += self._add_evidence(
                "sar_roughness_disruption", "7d", f.sar_roughness_change,
                min(1.0, abs(f.sar_roughness_change) / 2.0), 2.5, trace
            )

        # SCI-6: Wind speed — PRIMARY physical driver of lodging
        if f.wind_available and f.wind_speed_ms > 10.0:
            score = min(1.0, (f.wind_speed_ms - 8.0) / 12.0)
            lo += self._add_evidence("wind_speed", "current", f.wind_speed_ms, score, 3.0, trace)
        elif f.wind_available and f.wind_speed_ms > 6.0:
            score = min(1.0, (f.wind_speed_ms - 5.0) / 10.0)
            lo += self._add_evidence("wind_speed", "current", f.wind_speed_ms, score, 1.5, trace)

        # Spatial heterogeneity corroborates patchy damage
        if f.spatial_stability == "HETEROGENEOUS":
            lo += self._add_evidence("spatial_heterogeneity", "current", 1.0, 0.7, 1.0, trace)

        prob = self._to_prob(lo)

        # Confidence: needs SAR for structural verification
        conf = 0.6 if f.sar_available else 0.2
        if f.rain_available:
            conf = min(1.0, conf + 0.1)

        # ENH-5: evidence-proportional severity
        severity = min(1.0, self._compute_evidence_severity(trace) * 1.2)

        if prob > 0.3:
            return self._build_diagnosis(
                ProblemType.LODGING.value, prob, severity, conf, trace, f,
                [Driver.SAR_VV, Driver.RAIN, Driver.NDVI]
            )
        return None

    def _diagnose_frost_risk(self, f: DecisionFeatures) -> Optional[Diagnosis]:
        """Forecast-aware frost risk prediction (ENH-4).

        Uses 7-day weather forecast to predict frost events proactively.
        Critical for MENA winter cereals (wheat, barley) during flowering.

        Algorithm:
          - Scan forecast for temp_min < 2°C
          - Imminence: 1-3 days = high probability, 4-7 days = moderate
          - Severity scaled by crop stage (reproductive = critical)
        """
        if not f.forecast_available or f.forecast_cold_days == 0:
            return None

        lo = self._to_log_odds(0.10)  # Moderate prior when forecast data exists
        trace = []

        # Number of cold days in forecast
        if f.forecast_cold_days >= 3:
            lo += self._add_evidence(
                "forecast_cold_days", "7d_forecast", f.forecast_cold_days,
                1.0, 3.0, trace
            )
        elif f.forecast_cold_days >= 1:
            lo += self._add_evidence(
                "forecast_cold_days", "7d_forecast", f.forecast_cold_days,
                0.6, 2.0, trace
            )

        # How cold: sub-zero = severe frost, 0-2°C = light frost
        if f.forecast_min_temp < 0.0:
            score = min(1.0, abs(f.forecast_min_temp) / 5.0)
            lo += self._add_evidence(
                "forecast_min_temp", "7d_forecast", f.forecast_min_temp,
                score, 2.5, trace
            )
        elif f.forecast_min_temp < 2.0:
            lo += self._add_evidence(
                "forecast_min_temp", "7d_forecast", f.forecast_min_temp,
                0.3, 1.5, trace
            )

        # Stage sensitivity: reproductive is catastrophic
        ky = _get_ky("unknown", f.current_stage)  # Use default crop for frost
        if ky > 0.8:
            lo += self._add_evidence(
                "stage_sensitivity", "current", ky,
                0.8, 1.5, trace
            )

        # Contraindication: warm forecast overall
        if f.forecast_min_temp > 5.0:
            lo += self._add_evidence(
                "warm_forecast", "7d_forecast", f.forecast_min_temp,
                -1.0, 3.0, trace
            )

        prob = self._to_prob(lo)

        # Severity: proportional to temperature severity × stage sensitivity
        temp_severity = min(1.0, max(0.0, (2.0 - f.forecast_min_temp) / 7.0))
        severity = min(1.0, temp_severity * (0.5 + ky))

        # Confidence: forecast-based = moderately high
        conf = 0.65
        if f.forecast_cold_days >= 3:
            conf += 0.15
        conf = min(1.0, conf)

        if prob > 0.3:
            return self._build_diagnosis(
                ProblemType.FROST_RISK.value, prob, severity, conf, trace, f,
                [Driver.TEMP]
            )
        return None

    # ============================================================================
    # Post-processing helpers
    # ============================================================================

    def _apply_mutual_exclusion(self, diagnoses: List[Diagnosis]) -> None:
        """ENH-3: Bayesian mutual exclusion for contradictory diagnoses.

        When two logically contradictory diagnoses co-occur (e.g., water stress +
        waterlogging), the stronger hypothesis suppresses the weaker one.
        This prevents impossible co-diagnoses from confusing the policy engine.
        """
        diag_map = {d.problem_id: d for d in diagnoses}

        for id_a, id_b in _MUTUAL_EXCLUSION_PAIRS:
            if id_a in diag_map and id_b in diag_map:
                d_a = diag_map[id_a]
                d_b = diag_map[id_b]

                if d_a.probability > 0.3 and d_b.probability > 0.3:
                    # Suppress the weaker one
                    if d_a.probability >= d_b.probability:
                        old_b = d_b.probability
                        d_b.probability *= (1.0 - d_a.probability * 0.5)
                        # NUM-4 FIX: floor lowered from 0.05 to 0.01 to prevent
                        # false elevation of sub-threshold diagnoses
                        d_b.probability = max(0.01, d_b.probability)
                        # ROB-3: Audit trail for mutual exclusion
                        d_b.evidence_trace.append(EvidenceTerm(
                            "mutual_exclusion_suppressed_by", "post", old_b,
                            -(old_b - d_b.probability), 1.0,
                            -(old_b - d_b.probability),
                        ))
                    else:
                        old_a = d_a.probability
                        d_a.probability *= (1.0 - d_b.probability * 0.5)
                        d_a.probability = max(0.01, d_a.probability)
                        d_a.evidence_trace.append(EvidenceTerm(
                            "mutual_exclusion_suppressed_by", "post", old_a,
                            -(old_a - d_a.probability), 1.0,
                            -(old_a - d_a.probability),
                        ))

    def _compute_evidence_severity(self, trace: List[EvidenceTerm]) -> float:
        """ENH-5: Compute severity proportional to evidence magnitude.

        Replaces hardcoded severity values with data-driven computation.
        severity = sum(positive contributions) / max_possible_positive_contribution

        NUM-1 FIX: Denominator now only sums weights of POSITIVE-score
        evidence terms. Previously included contraindication weights,
        which diluted severity when strong contra-evidence was present.
        """
        if not trace:
            return 0.3  # Default when no evidence

        positive_sum = sum(abs(e.contribution) for e in trace if e.contribution > 0)
        # NUM-1 FIX: Only sum weights of positive-score terms
        # (e.score > 0 means evidence FOR the hypothesis)
        max_possible = sum(e.weight for e in trace if e.score > 0)

        if max_possible < 0.01:
            return 0.3

        return min(1.0, max(0.1, positive_sum / max_possible))
