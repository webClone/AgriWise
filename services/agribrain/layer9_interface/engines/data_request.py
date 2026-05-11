"""
Engine 11: Data Request Engine v9.6.0

Proactive data acquisition — identifies missing data and requests it
from the farmer to improve accuracy.
"""
import logging
from typing import Dict, Any, List
from layer9_interface.schema import (
    Layer9Input, PersonaConfig, ExpertiseLevel,
    DataRequest, DataRequestType,
)

logger = logging.getLogger(__name__)

_MAX_REQUESTS_PER_SESSION = 1


class DataRequestEngine:
    """Proactive data gap analysis and request generation."""

    def __init__(self):
        self._requests_this_session = 0

    def scan(self, l9_input: Layer9Input, persona: PersonaConfig) -> List[DataRequest]:
        """Scan for data gaps and generate prioritized requests."""
        if self._requests_this_session >= _MAX_REQUESTS_PER_SESSION:
            return []

        candidates: List[DataRequest] = []
        exp = persona.expertise_level
        grade = l9_input.audit_grade.upper()

        # Low reliability sources
        for src, rel in l9_input.source_reliability.items():
            if rel < 0.5:
                candidates.append(DataRequest(
                    data_type=DataRequestType.SENSOR_READING,
                    reason=f"Source '{src}' reliability is {rel:.0%}",
                    impact_description=self._impact_msg(
                        "sensor reading", rel, 0.85, exp),
                    urgency=0.7,
                    accuracy_gain_estimate=round(0.85 - rel, 2),
                ))

        # Grade-based requests
        if grade in ("C", "D", "F"):
            candidates.append(DataRequest(
                data_type=DataRequestType.SOIL_PHOTO,
                reason=f"Audit grade {grade} — visual confirmation would help",
                impact_description=self._impact_msg("soil photo", 0.6, 0.85, exp),
                urgency=0.6 if grade == "C" else 0.9,
                accuracy_gain_estimate=0.20,
            ))

        # Diagnosis uncertainty
        for diag in l9_input.diagnoses:
            if isinstance(diag, dict):
                conf = diag.get("confidence", 1.0)
                if conf < 0.6:
                    pid = diag.get("problem_id", "issue")
                    candidates.append(DataRequest(
                        data_type=DataRequestType.PEST_PHOTO,
                        reason=f"Low confidence ({conf:.0%}) on {pid}",
                        impact_description=self._impact_msg(
                            "close-up photo", conf, 0.85, exp),
                        urgency=0.8,
                        accuracy_gain_estimate=round(0.85 - conf, 2),
                    ))

        # Sort by impact and return top 1
        candidates.sort(key=lambda r: -(r.accuracy_gain_estimate * r.urgency))
        result = candidates[:1]
        if result:
            self._requests_this_session += 1
        return result

    def reset_session(self):
        self._requests_this_session = 0

    def _impact_msg(self, data_type, current, target, exp):
        if exp == ExpertiseLevel.NOVICE:
            return (f"A {data_type} would really help us give you better advice! "
                    f"Right now we're about {current:.0%} sure, "
                    f"but with your help we could reach ~{target:.0%} 📈")
        elif exp == ExpertiseLevel.FARMER:
            return (f"A {data_type} would improve diagnosis confidence "
                    f"from {current:.0%} to ~{target:.0%}.")
        else:
            return (f"{data_type}: current_conf={current:.2f}, "
                    f"estimated_post={target:.2f}, "
                    f"gain={target-current:.2f}")


data_request_engine = DataRequestEngine()
