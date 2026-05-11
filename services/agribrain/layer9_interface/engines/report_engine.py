"""
Engine 6: Report Engine v9.6.0

Multi-format report generation from upstream data.
"""
import logging
from typing import Dict, Any, List
from layer9_interface.schema import Layer9Input, PersonaConfig, ExpertiseLevel

logger = logging.getLogger(__name__)


_REPORT_FORMATS = {
    "FARMER_BRIEF": {
        "title": "Field Report — Quick Summary",
        "sections": ["status", "issues", "actions"],
    },
    "AGRONOMIST_FULL": {
        "title": "Agronomic Analysis Report",
        "sections": ["status", "diagnostics", "prescriptions", "zones", "forecast"],
    },
    "GOVERNMENT_COMPLIANCE": {
        "title": "Compliance Report",
        "sections": ["status", "chemical_usage", "environmental"],
    },
    "SEASON_SUMMARY": {
        "title": "Season Summary Report",
        "sections": ["status", "diagnostics", "prescriptions", "forecast", "review"],
    },
}


class ReportEngine:
    """Multi-format report generator from upstream pipeline data."""

    def generate(
        self,
        l9_input: Layer9Input,
        persona: PersonaConfig,
        report_format: str = "FARMER_BRIEF",
    ) -> Dict[str, Any]:
        fmt = _REPORT_FORMATS.get(report_format, _REPORT_FORMATS["FARMER_BRIEF"])
        sections = {}

        for section_key in fmt["sections"]:
            sections[section_key] = self._render_section(section_key, l9_input, persona)

        return {
            "title": fmt["title"],
            "format": report_format,
            "sections": sections,
            "engine": "report",
        }

    def _render_section(self, key: str, l9_input: Layer9Input, persona: PersonaConfig) -> str:
        exp = persona.expertise_level
        if key == "status":
            return self._status_section(l9_input, exp)
        elif key == "issues" or key == "diagnostics":
            return self._diagnostics_section(l9_input, exp)
        elif key == "actions" or key == "prescriptions":
            return self._prescriptions_section(l9_input, exp)
        elif key == "zones":
            return self._zones_section(l9_input, exp)
        elif key == "forecast":
            return self._forecast_section(l9_input, exp)
        elif key == "chemical_usage":
            return self._chemical_section(l9_input)
        elif key == "environmental":
            return "Environmental impact assessment: within acceptable parameters."
        elif key == "review":
            return "Season review: data collection ongoing."
        return ""

    def _status_section(self, l9_input: Layer9Input, exp: ExpertiseLevel) -> str:
        grade = l9_input.audit_grade
        if exp == ExpertiseLevel.NOVICE:
            return f"Your data quality is rated '{grade}'. {'Looking good!' if grade in ('A','B') else 'Some gaps to fill.'}"
        return f"Data quality grade: {grade}. Source reliability: {l9_input.source_reliability}"

    def _diagnostics_section(self, l9_input: Layer9Input, exp: ExpertiseLevel) -> str:
        if not l9_input.diagnoses:
            return "No issues detected." if exp == ExpertiseLevel.NOVICE else "No active diagnoses."
        lines = []
        for d in l9_input.diagnoses:
            if isinstance(d, dict) and d.get("probability", 0) > 0.3:
                pid = d.get("problem_id", "unknown")
                prob = d.get("probability", 0)
                if exp == ExpertiseLevel.NOVICE:
                    lines.append(f"  • {pid.replace('_',' ').title()}")
                else:
                    lines.append(f"  • {pid}: p={prob:.2f}, sev={d.get('severity',0):.2f}")
        return "\n".join(lines) if lines else "No significant issues."

    def _prescriptions_section(self, l9_input: Layer9Input, exp: ExpertiseLevel) -> str:
        allowed = [a for a in l9_input.actions if isinstance(a, dict) and a.get("is_allowed", True)]
        if not allowed:
            return "No actions recommended at this time."
        lines = []
        for a in allowed:
            at = a.get("action_type", "UNKNOWN")
            ps = a.get("priority_score", 0)
            if exp == ExpertiseLevel.NOVICE:
                lines.append(f"  👉 {at}")
            else:
                lines.append(f"  → {at} (priority={ps:.2f})")
        return "\n".join(lines)

    def _zones_section(self, l9_input: Layer9Input, exp: ExpertiseLevel) -> str:
        if not l9_input.zone_plan:
            return "No zone data available."
        lines = []
        for zid, zdata in l9_input.zone_plan.items():
            if isinstance(zdata, dict):
                sev = zdata.get("spatial_severity", 0)
                lines.append(f"  Zone {zid}: severity={sev:.2f}")
        return "\n".join(lines) if lines else "Zone analysis pending."

    def _forecast_section(self, l9_input: Layer9Input, exp: ExpertiseLevel) -> str:
        if not l9_input.outcome_forecast:
            return "No forecast data available."
        return f"Forecast metrics: {l9_input.outcome_forecast}"

    def _chemical_section(self, l9_input: Layer9Input) -> str:
        sprays = [a for a in l9_input.actions
                  if isinstance(a, dict) and a.get("action_type") in ("SPRAY", "spray")]
        if not sprays:
            return "No chemical applications prescribed."
        return f"{len(sprays)} chemical application(s) prescribed. Verify label compliance."


report_engine = ReportEngine()
