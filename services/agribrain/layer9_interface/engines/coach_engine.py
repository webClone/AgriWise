"""
Engine 8: Coach Engine v9.6.0

Behavioral nudge system with psychology-aware coaching.
"""
import logging
from typing import Dict, Any, List
from layer9_interface.schema import Layer9Input, PersonaConfig, ExpertiseLevel

logger = logging.getLogger(__name__)


class CoachEngine:
    """Psychology-aware coaching nudges based on data gaps."""

    def generate_coaching(self, l9_input: Layer9Input, persona: PersonaConfig) -> Dict[str, Any]:
        exp = persona.expertise_level
        tips: List[str] = []
        score = self._compute_data_quality_score(l9_input)

        # Data quality coaching
        if score < 0.5:
            if exp == ExpertiseLevel.NOVICE:
                tips.append("Adding a soil photo would really help us help you better! 📸")
            else:
                tips.append(f"Data quality score: {score:.0%}. Consider adding sensor readings.")
        elif score < 0.8:
            if exp == ExpertiseLevel.NOVICE:
                tips.append("You're building great data! One more reading would make it even better 🎯")
            else:
                tips.append(f"Data quality at {score:.0%}. Near optimal — one more source would complete the picture.")
        else:
            if exp == ExpertiseLevel.NOVICE:
                tips.append("Amazing data quality! Your field analysis is super reliable 🎉")
            else:
                tips.append(f"Data quality excellent ({score:.0%}). Full-confidence analysis enabled.")

        # Conflict coaching
        if l9_input.conflicts:
            if exp == ExpertiseLevel.NOVICE:
                tips.append("We found some mixed signals — a quick field check would clear things up! 🔍")
            else:
                tips.append(f"{len(l9_input.conflicts)} source conflict(s). Field verification recommended.")

        # L2 phenological stage coaching (v9.7 advanced wiring)
        l2_data = l9_input.l2_vegetation_data
        if l2_data and l2_data.get("stage") == "REPRODUCTIVE":
            if exp == ExpertiseLevel.NOVICE:
                tips.append("Your crop is in the reproductive stage! Keep soil moist and avoid high stress 🌸")
            else:
                tips.append(f"Crop phenology is REPRODUCTIVE (BBCH {l2_data.get('bbch')}). Maintain optimal soil water tension.")

        # L6 leaching mitigation coaching (v9.7 advanced wiring)
        l6_data = l9_input.l6_execution_data
        if l6_data and l6_data.get("nitrogen_leaching_fraction", 0.0) > 0.2:
            if exp == ExpertiseLevel.NOVICE:
                tips.append("Split your nitrogen fertilizer into smaller doses to stop it washing away! 💧")
            else:
                tips.append(f"Nitrogen leaching fraction at {l6_data.get('nitrogen_leaching_fraction'):.0%}. Recommend split N applications.")

        # L7 planning options coaching (v9.7 advanced wiring)
        l7_data = l9_input.l7_planning_data
        if l7_data and l7_data.get("options"):
            best_opt = max(l7_data["options"], key=lambda o: o.get("expected_profit", 0.0))
            if best_opt.get("expected_profit", 0.0) > 1000.0:
                if exp == ExpertiseLevel.NOVICE:
                    tips.append(f"Planning tip: Planting '{best_opt['crop']}' next season could boost your earnings! 📈")
                else:
                    tips.append(f"L7 rotation planning: '{best_opt['crop']}' shows high suitability ({best_opt.get('suitability_percentage', 0.0):.1f}%) and expected profit ({best_opt.get('expected_profit', 0.0):.0f} EUR/ha).")

        return {
            "tips": tips,
            "data_quality_score": round(score, 2),
            "improvement_delta": 0.0,
            "engine": "coach",
        }

    def _compute_data_quality_score(self, l9_input: Layer9Input) -> float:
        grade_scores = {"A": 1.0, "B": 0.8, "C": 0.6, "D": 0.3, "F": 0.1}
        base = grade_scores.get(l9_input.audit_grade.upper(), 0.5)
        conflict_penalty = min(0.3, len(l9_input.conflicts) * 0.1)
        reliability_bonus = 0.0
        if l9_input.source_reliability:
            avg_rel = sum(l9_input.source_reliability.values()) / len(l9_input.source_reliability)
            reliability_bonus = avg_rel * 0.2
        return max(0.0, min(1.0, base - conflict_penalty + reliability_bonus))


coach_engine = CoachEngine()
