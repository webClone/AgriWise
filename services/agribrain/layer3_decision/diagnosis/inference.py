
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
        
        # Sort by Probability (Belief)
        diagnoses.sort(key=lambda x: x.probability, reverse=True)
        return diagnoses

    # --- Specific Diagnosis Logics ---

    def _diagnose_water_stress(self, f: DecisionFeatures) -> Optional[Diagnosis]:
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
        if f.esi > 0.1:
            if f.esi > 0.4:
                score = min(1.0, f.esi / 0.8)
                weight = 1.5 if f.lst_available else 0.5  # Much weaker if VPD-only proxy
                lo += self._add_evidence("esi", "current", f.esi, score, weight, trace)
            elif f.esi < 0.1:
                lo += self._add_evidence("esi", "current", f.esi, -0.5, 1.0, trace)

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
            return self._build_diagnosis(
                problem_id=ProblemType.WATER_STRESS.value,
                prob=prob,
                severity=f.anomaly_severity if f.has_anomaly else 0.3,
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
