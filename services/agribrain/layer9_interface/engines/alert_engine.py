"""
Engine 7: Alert Engine v9.6.0

Persona-aware multi-channel alert dispatch with severity routing.
"""
import logging
from typing import Dict, Any, List
from layer9_interface.schema import (
    Layer9Input, PersonaConfig, ExpertiseLevel, AlertSeverity,
)

logger = logging.getLogger(__name__)


class AlertEngine:
    """Multi-channel alert engine with persona-aware tone."""

    def generate_alerts(self, l9_input: Layer9Input, persona: PersonaConfig) -> List[Dict[str, Any]]:
        alerts: List[Dict[str, Any]] = []
        exp = persona.expertise_level
        grade = l9_input.audit_grade.upper()

        if grade in ("C", "D", "F"):
            alerts.append(self._fmt(
                "DATA_QUALITY",
                "CRITICAL" if grade in ("D", "F") else "WARNING",
                f"Data quality grade: {grade}", "L0_audit", exp,
            ))

        for diag in l9_input.diagnoses:
            if isinstance(diag, dict) and diag.get("probability", 0) > 0.6:
                pid = diag.get("problem_id", "unknown")
                sev = diag.get("severity", 0)
                alerts.append(self._fmt(
                    "DISEASE", "CRITICAL" if sev > 0.7 else "WARNING",
                    f"{pid}: p={diag.get('probability',0):.2f}", pid, exp,
                ))

        for act in l9_input.actions:
            if isinstance(act, dict) and not act.get("is_allowed", True):
                alerts.append(self._fmt(
                    "SYSTEM", "WARNING",
                    f"Action '{act.get('action_type','?')}' blocked",
                    act.get("action_id", ""), exp,
                ))
        return alerts

    def _fmt(self, atype, severity, raw, eid, exp):
        if exp == ExpertiseLevel.NOVICE:
            msg = f"⚠️ {raw.split(':')[0].replace('_',' ').title()}"
        else:
            msg = raw
        return {"alert_type": atype, "severity": severity, "message": msg,
                "evidence_id": eid, "channel": "PUSH" if severity == "CRITICAL" else "IN_APP",
                "engine": "alert"}


alert_engine = AlertEngine()
