
from typing import List, Dict, Any, Optional
import datetime

from services.agribrain.layer3_decision.schema import Diagnosis, Recommendation, PlotContext
from services.agribrain.layer3_decision.knowledge.ontology import ACTIONS, ProblemType, ActionDefinition

class PolicyEngine:
    """
    Deterministically maps Diagnoses -> Actions.
    Resolves trade-offs, priorities, COMPLIANCE, and SAFETY.
    """
    
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
                        # CREATE FALLBACK
                        fallback_rec = self._create_recommendation(
                            d, fallback_def, context, half_week_rain, missing_drivers, is_fallback=True
                        )
                        # Append the BLOCKED primary as 'info' or just append fallback?
                        # User spec: "If blocked: must produce a safe alternative"
                        # We append the fallback. We might also keep the primary to show it was considered but blocked.
                        # Let's append primary (marked blocked) AND fallback.
                        recommendations.append(rec)
                        recommendations.append(fallback_rec)
                    else:
                        recommendations.append(rec) # No fallback
                else:
                    recommendations.append(rec)
            else:
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
        if problem_id == ProblemType.COLD_STRESS.value: return None # No action for cold yet
        if problem_id == ProblemType.NUTRIENT_DEFICIENCY_N.value: return None # Layer 4
        if problem_id == ProblemType.FUNGAL_DISEASE_RISK.value: return ACTIONS.get("SCOUT_DISEASE")
        if problem_id == ProblemType.INSECT_PRESSURE_RISK.value: return ACTIONS.get("SCOUT_PESTS")
        if problem_id == ProblemType.HARVEST_EVENT.value: return ACTIONS.get("VERIFY_FIELD_STATUS")
        
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
             quota = context.constraints.get("water_quota_mm", 9999)
             if quota < 25.0: # Hardcoded assumption for IS_ALLOWED check implies volume check
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
        
        return Recommendation(
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
            timing={"start": "Today", "end": "3 Days"}
        )
