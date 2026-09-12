
from typing import List, Dict, Any, Optional
import datetime

from layer3_decision.schema import Diagnosis, Recommendation, PlotContext
from layer3_decision.knowledge.ontology import ACTIONS, ProblemType, ActionDefinition
from layer3_water.soil import SoilProfileDatabase

class PolicyEngine:
    """
    Deterministically maps Diagnoses -> Actions.
    Resolves trade-offs, priorities, COMPLIANCE, and SAFETY.
    """
    # PERF-1: Canonical soil profile (replaces legacy SoilMoistureModel)
    _soil_profile_db = SoilProfileDatabase
    
    def generate_plan(
        self, 
        diagnoses: List[Diagnosis], 
        context: PlotContext,
        weather_forecast: List[Dict[str, Any]] = None,
        missing_inputs: List[str] = None
    ) -> List[Recommendation]:
        recommendations = []
        forecast = weather_forecast or []
        missing_drivers = set(missing_inputs or [])
        
        # Forecast Summary for constraints
        half_week_rain = 0.0
        if forecast:
            for day in forecast[:3]:
                half_week_rain += day.get("rain", 0.0)
                
        # 1. Map Diagnoses to Primary Actions
        for d in diagnoses:
            action_def = self._map_problem_to_action(d.problem_id)
            if not action_def:
                continue
                
            # Create Recommendation Candidate
            rec = self._create_recommendation(d, action_def, context, half_week_rain, missing_drivers)
            
                # 2. Safety Fallback Logic
            # If blocked or low confidence/feasibility, downgrade to Fallback
            if (not rec.is_allowed) or (rec.confidence < action_def.min_confidence):
                if action_def.fallback_action_id:
                    fallback_def = ACTIONS.get(action_def.fallback_action_id)
                    if fallback_def:
                        # Expert Grade Guard: Prevent soil moisture scouting if NDVI is stable/improving
                        # Unless confidence is very low (Data Gap)
                        if fallback_def.action_id == "VERIFY_SOIL_MOISTURE":
                            # Check L2 trend from signals or features
                            # We don't have features object here easily, but we have diagnoses traces?
                            # Actually, we can check if the diagnosis probability is primarily driven by rain shortfall
                            # vs actual vegetation decline.
                            # For simplicity, we can look at the evidence trace of the diagnosis 'd'.
                            has_veg_issue = any(t.feature_name in ["ndvi_anomaly", "ndvi_drop", "growth_velocity"] and t.score > 0 for t in d.evidence_trace)
                            if not has_veg_issue and d.probability < 0.8:
                                continue # Suppress scouting if no plant-side evidence
                        
                        # CREATE FALLBACK
                        fallback_rec = self._create_recommendation(
                            d, fallback_def, context, half_week_rain, missing_drivers, is_fallback=True
                        )
                        recommendations.append(rec)
                        recommendations.append(fallback_rec)
                    else:
                        recommendations.append(rec) # No fallback
                else:
                    recommendations.append(rec)
            else:
                # Expert Grade Guard for Primary Irrigation as well
                if action_def.action_id == "IRRIGATE_FULL":
                     has_veg_issue = any(t.feature_name in ["ndvi_anomaly", "ndvi_drop", "growth_velocity"] and t.score > 0 for t in d.evidence_trace)
                     if not has_veg_issue and d.probability < 0.9:
                        continue # Suppress intervention if strictly rain-based but plants look fine
                
                # Allowed and confident
                recommendations.append(rec)

        # Sort by Priority
        recommendations.sort(key=lambda x: x.priority_score, reverse=True)
        return recommendations

    def _map_problem_to_action(self, problem_id: str) -> Optional[ActionDefinition]:
        # Mapping Logic
        # This could be moved to ontology, but implicit here is fine for logic
        if problem_id == ProblemType.WATER_STRESS.value: return ACTIONS.get("IRRIGATE_FULL")
        if problem_id == ProblemType.WATERLOGGING.value: return ACTIONS.get("DRAIN_FIELD")
        if problem_id == ProblemType.LOGGING_CLEARING.value: return ACTIONS.get("ALERT_STRUCTURE_LOGGING")
        if problem_id == ProblemType.DATA_GAP.value: return ACTIONS.get("WAIT_FOR_DATA")
        
        # New
        if problem_id == ProblemType.HEAT_STRESS.value: return ACTIONS.get("IRRIGATE_FULL") # Heat needs water
        if problem_id == ProblemType.COLD_STRESS.value: return ACTIONS.get("FROST_PROTECTION")
        if problem_id == ProblemType.FROST_RISK.value: return ACTIONS.get("FROST_PROTECTION")
        if problem_id == ProblemType.NUTRIENT_DEFICIENCY_N.value: return None # Layer 4
        if problem_id == ProblemType.FUNGAL_DISEASE_RISK.value: return ACTIONS.get("SCOUT_DISEASE")
        if problem_id == ProblemType.INSECT_PRESSURE_RISK.value: return ACTIONS.get("SCOUT_PESTS")
        if problem_id == ProblemType.HARVEST_EVENT.value: return ACTIONS.get("VERIFY_FIELD_STATUS")
        if problem_id == ProblemType.TILLAGE_EVENT.value: return ACTIONS.get("VERIFY_FIELD_STATUS")
        if problem_id == ProblemType.TRANSPIRATION_FAILURE.value: return ACTIONS.get("APPLY_DEFICIT_IRRIGATION")
        if problem_id == ProblemType.WEED_PRESSURE.value: return ACTIONS.get("SCOUT_WEEDS")
        if problem_id == ProblemType.MECHANICAL_DAMAGE.value: return ACTIONS.get("ASSESS_MECHANICAL")
        if problem_id == ProblemType.LODGING.value: return ACTIONS.get("APPLY_LODGING_SUPPORT")
        if problem_id == ProblemType.SALINITY_RISK.value: return ACTIONS.get("LEACH_SALTS")
        if problem_id == ProblemType.DATA_ARTIFACT.value: return ACTIONS.get("WAIT_FOR_DATA")
        
        return None

    def _create_recommendation(
        self, 
        d: Diagnosis, 
        action_def: ActionDefinition, 
        context: PlotContext,
        rain_forecast_3d: float,
        missing_drivers: set,
        is_fallback: bool = False
    ) -> Recommendation:
        
        # 1. Feasibility Check (Driver availability)
        feasibility = 1.0
        missing_reqs = []
        for req in action_def.required_drivers:
            if req == "FORECAST" and rain_forecast_3d == 0.0: pass # Hard to check forecast existence strictly here
            # Map generic driver names to missing_inputs keys
            # missing_inputs uses "RAIN_SERIES", "SAR_STRUCTURE", "TEMP_DATA"
            if req == "RAIN" and "RAIN_SERIES" in missing_drivers: missing_reqs.append(req)
            if req == "SAR" and "SAR_STRUCTURE" in missing_drivers: missing_reqs.append(req)
            
        if missing_reqs:
            feasibility = 0.0
        
        # 2. Compliance Constraints
        is_allowed = True
        blocked_reasons = []
        
        # Quota
        if "WaterQuota" in action_def.prerequisites:
             quota = context.constraints.get("water_quota_mm")
             if quota is not None and quota < 25.0:
                 is_allowed = False
                 blocked_reasons.append(f"Insufficient Quota ({quota}mm)")
                 
        # Weather Contraindication
        for contra in action_def.contraindications:
            if "RainForecast>10mm" in contra and rain_forecast_3d > 10.0:
                is_allowed = False
                blocked_reasons.append(f"Rain Forecast {rain_forecast_3d:.1f}mm > 10mm")

        # 3. Priority Calculation
        # Base Impact * Urgency (from diagnosis) * Confidence
        impact = 0.9 if action_def.type == "INTERVENE" else 0.4
        if action_def.type == "ALERT": impact = 1.0
        
        urgency = d.severity
        confidence = d.confidence
        
        if is_fallback:
             # Fallbacks are usually verification, lower priority but high confidence usually?
             impact *= 0.8
        
        score = impact * urgency * confidence
        
        rec = Recommendation(
            action_id=f"ACT_{action_def.action_id}_{d.problem_id}",
            action_type=action_def.type,
            priority_score=score,
            expected_impact=impact,
            urgency=urgency,
            confidence=confidence,
            is_allowed=is_allowed and (feasibility > 0.0), # Block if infeasible
            blocked_reason=blocked_reasons + ([f"Missing Drivers: {missing_reqs}"] if missing_reqs else []),
            risk_if_wrong=action_def.risk_if_wrong,
            linked_diagnosis_ids=[d.problem_id],
            explain=f"{action_def.title} recommended due to {d.problem_id} ({d.probability:.0%}).",
            preconditions=action_def.prerequisites,
            timing={"start": "Today", "end": "3 Days"},
            resource_est=self._estimate_resources(action_def, context, d),
        )
        return rec

    def _estimate_resources(
        self,
        action_def: ActionDefinition,
        context: PlotContext,
        diagnosis: Diagnosis,
    ) -> Dict[str, float]:
        """ENH-7: Compute resource estimates for irrigation recommendations.

        Uses canonical SoilProfileDatabase for TAW calculation and derives
        depletion from evidence trace rather than raw severity.
        GAP-5/GAP-19 FIX: severity is no longer misused as physical depletion.
        """
        resources: Dict[str, float] = {}

        if action_def.action_id in ("IRRIGATE_FULL", "APPLY_DEFICIT_IRRIGATION"):
            soil_type = context.soil_texture_class or "loam"

            # Get TAW from canonical soil profile database
            soil_profile = SoilProfileDatabase.get_canonical_soil_profile(
                soil_type=soil_type, initial_saturation_fraction=0.5,
            )
            # Compute TAW from the profile (FC - WP) across root zone
            taw_mm = 0.0
            prev_d = 0.0
            if context.crop_type and context.species_specific_allowed and context.crop_type != "unknown":
                from layer3_decision.knowledge.crops import get_crop_profile
                root_depth_cm = get_crop_profile(context.crop_type).max_root_depth_cm or 100.0
            else:
                root_depth_cm = 100.0
            for i, d in enumerate(soil_profile.layer_depths_cm):
                if prev_d >= root_depth_cm:
                    break
                active_thickness_mm = (min(d, root_depth_cm) - prev_d) * 10.0
                taw_mm += (soil_profile.field_capacity_profile[i] - soil_profile.wilting_point_profile[i]) * active_thickness_mm
                prev_d = d
            taw_mm = max(1.0, taw_mm)

            # GAP-19 FIX: Derive depletion from evidence-weighted rain deficit
            # and anomaly signals, NOT from raw severity (which mixes VPD, stage, etc.)
            rain_deficit_score = 0.0
            anomaly_score = 0.0
            for ev in diagnosis.evidence_trace:
                if ev.feature_name in ("rain_sum_14d", "days_since_rain") and ev.score > 0:
                    rain_deficit_score = max(rain_deficit_score, ev.score)
                if ev.feature_name in ("ndvi_anomaly", "ndvi_drop", "esi") and ev.score > 0:
                    anomaly_score = max(anomaly_score, ev.score)

            # Depletion estimate: blend physical evidence signals
            evidence_depletion = min(1.0, 0.5 * rain_deficit_score + 0.5 * anomaly_score)
            # Floor at 30% if any diagnosis was triggered
            depletion_pct = max(0.3, evidence_depletion) if diagnosis.probability > 0.5 else evidence_depletion
            depletion_mm = taw_mm * depletion_pct

            # Application efficiency
            eff_map = {"drip": 0.95, "sprinkler": 0.80, "flood": 0.60, "pivot": 0.85}
            eff = eff_map.get(context.irrigation_type, 0.80)

            if action_def.action_id == "IRRIGATE_FULL":
                gross_mm = depletion_mm / eff
            else:
                # Deficit irrigation: 50-70% of full dose
                gross_mm = (depletion_mm * 0.6) / eff

            resources["irrigation_dose_mm"] = round(max(0.0, gross_mm), 1)
            resources["taw_mm"] = round(taw_mm, 1)
            resources["depletion_pct"] = round(depletion_pct, 2)
            resources["efficiency"] = eff

        return resources
