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

        # L2 vegetation anomalies (v9.7 advanced wiring)
        l2_data = l9_input.l2_vegetation_data
        if l2_data and l2_data.get("anomalies_count", 0) > 0:
            max_sev = max(l2_data.get("anomalies_severity", [0.0]))
            if max_sev > 0.5:
                alerts.append(self._fmt(
                    "WEATHER", "CRITICAL" if max_sev > 0.7 else "WARNING",
                    f"Vegetation anomalies: {l2_data['anomalies_count']} stress events, max severity={max_sev:.2f}",
                    "L2_anomalies", exp,
                ))

        # Proactive Anomaly Detection integration (Anomaly Detector Gap Fix)
        try:
            from layer9_interface.engines.anomaly_detector import get_detector
            detector = get_detector()
            sensors = {}
            if l9_input.l1_fusion_data:
                sensors.update(l9_input.l1_fusion_data)
            if l9_input.l2_vegetation_data:
                sensors.update(l9_input.l2_vegetation_data)
            
            crop = "wheat"
            if l9_input.l2_vegetation_data and isinstance(l9_input.l2_vegetation_data, dict):
                crop = l9_input.l2_vegetation_data.get("crop", crop)
            
            detected_anomalies = detector.detect(sensors, crop=crop)
            for anomaly in detected_anomalies:
                # Map anomaly severity to AlertSeverity-compatible values
                # Anomaly uses LOW/MEDIUM/HIGH/CRITICAL; AlertSeverity uses INFO/WARNING/CRITICAL
                _sev_map = {"LOW": "INFO", "MEDIUM": "WARNING", "HIGH": "WARNING", "CRITICAL": "CRITICAL"}
                mapped_severity = _sev_map.get(anomaly.severity, "WARNING")
                alerts.append(self._fmt(
                    anomaly.category.upper(),
                    mapped_severity,
                    anomaly.message,
                    anomaly.id,
                    exp
                ))
        except Exception as e:
            logger.warning(f"Proactive anomaly detector failed: {e}")

        # L4 nutrient deficiencies (v9.7 advanced wiring)
        l4_data = l9_input.l4_nutrient_data
        if l4_data and l4_data.get("nutrient_deficiencies"):
            for nut, info in l4_data["nutrient_deficiencies"].items():
                prob = info.get("probability_deficient", 0.0)
                if prob > 0.6:
                    sev = info.get("severity", "LOW")
                    alerts.append(self._fmt(
                        "NUTRITION", "CRITICAL" if sev == "HIGH" else "WARNING",
                        f"Nutrient {nut} deficiency risk: p={prob:.2f}",
                        f"L4_{nut}_deficiency", exp,
                    ))

        # L5 pathogen/pest risk (v9.7 advanced wiring)
        l5_data = l9_input.l5_disease_data
        if l5_data and l5_data.get("threat_states"):
            for disease, info in l5_data["threat_states"].items():
                prob = info.get("probability", 0.0)
                if prob > 0.6:
                    sev = info.get("severity", "LOW")
                    alerts.append(self._fmt(
                        "DISEASE", "CRITICAL" if sev == "HIGH" else "WARNING",
                        f"Pathogen {disease} outbreak risk: p={prob:.2f}",
                        f"L5_{disease}_outbreak", exp,
                    ))

        # L6 execution safety (v9.7 advanced wiring)
        l6_data = l9_input.l6_execution_data
        if l6_data:
            leach = l6_data.get("nitrogen_leaching_fraction", 0.0)
            if leach > 0.2:
                alerts.append(self._fmt(
                    "WATER", "WARNING",
                    f"Nitrogen leaching fraction high: {leach:.1%}",
                    "L6_n_leaching", exp,
                ))
            runoff = l6_data.get("runoff_risk_index", 0.0)
            if runoff > 0.6:
                alerts.append(self._fmt(
                    "WATER", "CRITICAL" if runoff > 0.8 else "WARNING",
                    f"Runoff risk index warning: {runoff:.2f}",
                    "L6_runoff_risk", exp,
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
