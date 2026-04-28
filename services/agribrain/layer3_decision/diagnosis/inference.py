
import math
from typing import List, Dict, Any, Tuple, Optional

from layer3_decision.schema import Diagnosis, PlotContext, EvidenceTerm, Driver
from layer3_decision.features.builder import DecisionFeatures
from layer3_decision.knowledge.ontology import ProblemType, PROBLEM_DB

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

    def diagnose(self, features: DecisionFeatures, context: PlotContext) -> List[Diagnosis]:
        diagnoses = []
        
        # --- 1. Water Stress (Abiotic) ---
        d_ws = self._diagnose_water_stress(features)
        if d_ws: diagnoses.append(d_ws)
        
        # --- 2. Waterlogging (Abiotic) ---
        d_wl = self._diagnose_waterlogging(features)
        if d_wl: diagnoses.append(d_wl)
        
        # --- 3. Heat Stress (Abiotic) ---
        d_ht = self._diagnose_heat_stress(features)
        if d_ht: diagnoses.append(d_ht)

        # --- 4. Cold Stress (Abiotic) ---
        d_cs = self._diagnose_cold_stress(features)
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

        # --- 9. Data Gaps ---
        d_gap = self._diagnose_data_gap(features)
        if d_gap: diagnoses.append(d_gap)
        
        # Sort by Probability (Belief)
        diagnoses.sort(key=lambda x: x.probability, reverse=True)
        return diagnoses

    # --- Specific Diagnosis Logics ---

    def _diagnose_water_stress(self, f: DecisionFeatures) -> Optional[Diagnosis]:
        # Prior: Low (0.1)
        lo = self._to_log_odds(0.1)
        trace = []
        
        # Evidence
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
            
        prob = self._to_prob(lo)
        
        # Confidence Calculation (Lock: only subtract)
        # Drivers: RAIN, NDVI, TEMP
        conf = 1.0
        if Driver.RAIN in f.missing_inputs: conf -= 0.5
        if not f.optical_available: conf -= 0.2
        conf = max(0.0, conf)
        
        if prob > 0.2:
            return self._build_diagnosis(
                problem_id=ProblemType.WATER_STRESS.value,
                prob=prob,
                severity=f.anomaly_severity if f.has_anomaly else 0.3,
                conf=conf,
                trace=trace,
                features=f,
                drivers_used=[Driver.RAIN, Driver.NDVI, Driver.TEMP]
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
            
        prob = self._to_prob(lo)
        conf = 1.0
        if not f.rain_available: conf -= 0.5
        conf = max(0.0, conf)
        
        if prob > 0.3:
            return self._build_diagnosis(ProblemType.WATERLOGGING.value, prob, 0.7, conf, trace, f, [Driver.RAIN, Driver.SAR_VV, Driver.NDVI])
        return None

    def _diagnose_heat_stress(self, f: DecisionFeatures) -> Optional[Diagnosis]:
        lo = self._to_log_odds(0.1)
        trace = []
        
        if f.heat_stress_days > 2:
            lo += self._add_evidence("heat_days", "7d", f.heat_stress_days, 1.0, 3.0, trace)
            
        prob = self._to_prob(lo)
        conf = 1.0
        if Driver.TEMP in f.missing_inputs: conf = 0.0 # Critical missing
        
        if prob > 0.4:
            return self._build_diagnosis(ProblemType.HEAT_STRESS.value, prob, 0.6, conf, trace, f, [Driver.TEMP])
        return None

    def _diagnose_cold_stress(self, f: DecisionFeatures) -> Optional[Diagnosis]:
        lo = self._to_log_odds(0.05)
        trace = []
        
        if f.cold_stress_days > 2:
             lo += self._add_evidence("cold_days", "7d", f.cold_stress_days, 1.0, 3.0, trace)
             
        prob = self._to_prob(lo)
        conf = 1.0
        if Driver.TEMP in f.missing_inputs: conf = 0.0 
        
        if prob > 0.4:
            return self._build_diagnosis(ProblemType.COLD_STRESS.value, prob, 0.6, conf, trace, f, [Driver.TEMP])
        return None

    def _diagnose_n_deficiency(self, f: DecisionFeatures, prob_water_stress: float) -> Optional[Diagnosis]:
        # Logic: Low Growth Velocity AND No Water Stress AND In Vegetative Stage
        lo = self._to_log_odds(0.05)
        trace = []
        
        # 1. Growth Velocity Low? (Proxy for Chlorosis/Stunting)
        # Assuming typical velocity is > 0.01 NDVI/day in rapid growth
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
            return self._build_diagnosis(ProblemType.NUTRIENT_DEFICIENCY_N.value, prob, 0.5, conf, trace, f, [Driver.NDVI])
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
        # Wet + Warm
        lo = self._to_log_odds(0.1)
        trace = []
        
        if f.rain_sum_7d > 20.0 and f.heat_stress_days < 1: # Wet and not too hot
             lo += self._add_evidence("wet_conditions", "7d", f.rain_sum_7d, 1.0, 2.0, trace)
             
        prob = self._to_prob(lo)
        conf = 1.0
        if Driver.RAIN in f.missing_inputs: conf = 0.0
        
        if prob > 0.4:
            return self._build_diagnosis(ProblemType.FUNGAL_DISEASE_RISK.value, prob, 0.7, conf, trace, f, [Driver.RAIN, Driver.TEMP])
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
            return self._build_diagnosis(ProblemType.SALINITY_RISK.value, prob, 0.4, 0.3, trace, f, [Driver.NDVI]) # Conf 0.3 (Low)
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
            return self._build_diagnosis(ProblemType.INSECT_PRESSURE_RISK.value, prob, 0.6, conf, trace, f, [Driver.NDVI])
        return None

    def _diagnose_data_gap(self, f: DecisionFeatures) -> Optional[Diagnosis]:
        if not f.missing_inputs: return None
        
        count = len(f.missing_inputs)
        
        # User spec: "Confidence must be computed from data quality only"
        # If we have degraded components (e.g. valid checks failed elsewhere), reduce conf.
        # But for 'DATA_GAP' diagnosis itself, we are confident that data IS missing.
        # However, to avoid 1.0/1.0 appearing authoritative in degraded mode:
        
        conf = 1.0
        # If we have critical missing inputs (SAR/RAIN), we reduce confidence slightly
        # to ensure it doesn't look like a "perfect" diagnosis in a broken system.
        if Driver.SAR_VV in f.missing_inputs or Driver.RAIN in f.missing_inputs:
             conf = 0.8
             
        return self._build_diagnosis(
            ProblemType.DATA_GAP.value,
            1.0, 
            count / 5.0, 
            conf,
            [EvidenceTerm("missing_inputs", "current", count, 1.0, 5.0, count)],
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
