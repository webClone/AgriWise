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
