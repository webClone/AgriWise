"""
Engine 4: Advisory Engine v9.6.0

Persona-adaptive field overview narrative generator.
Deterministic template-based — no LLM dependency for core summaries.
"""
import logging
from typing import Dict, Any, List, Optional

from layer9_interface.schema import (
    Layer9Input, ExpertiseLevel, PersonaConfig, PhrasingMode,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Persona-aware template sets
# ============================================================================

_SUMMARY_TEMPLATES = {
    ExpertiseLevel.NOVICE: {
        PhrasingMode.CONFIDENT: "Good news! Your field is doing well overall 🌾. {n_actions} thing(s) to take care of this week.",
        PhrasingMode.HEDGED: "Your field looks okay, but we're not 100% sure about a few things 🤔. {n_actions} suggestion(s) to check on.",
        PhrasingMode.RESTRICTED: "We need a bit more information about your field before giving advice. Can you take a look around? 🔍",
    },
    ExpertiseLevel.FARMER: {
        PhrasingMode.CONFIDENT: "Field status: {n_diagnoses} issue(s) identified. {n_actions} action(s) recommended.",
        PhrasingMode.HEDGED: "{n_diagnoses} potential issue(s). {n_actions} action(s) suggested — confirm in field first.",
        PhrasingMode.RESTRICTED: "Data gaps limit analysis. {n_diagnoses} possible issue(s) flagged. Scout before intervening.",
    },
    ExpertiseLevel.TECHNICIAN: {
        PhrasingMode.CONFIDENT: "Analysis complete: {n_diagnoses} diagnosed condition(s), {n_actions} prescriptive action(s) at high confidence.",
        PhrasingMode.HEDGED: "{n_diagnoses} condition(s) detected at moderate confidence. {n_actions} action(s) pending field verification.",
        PhrasingMode.RESTRICTED: "Insufficient data quality (grade {grade}). {n_diagnoses} preliminary diagnosis(es). Field validation required.",
    },
    ExpertiseLevel.AGRONOMIST: {
        PhrasingMode.CONFIDENT: "L3 diagnosis: {n_diagnoses} condition(s). L8 prescription: {n_actions} action(s). Confidence: HIGH.",
        PhrasingMode.HEDGED: "L3: {n_diagnoses} condition(s), moderate confidence. L8: {n_actions} action(s), pending L0 grade uplift.",
        PhrasingMode.RESTRICTED: "L0 grade {grade}. Pipeline reliability compromised. {n_diagnoses} flag(s) require ground-truth calibration.",
    },
    ExpertiseLevel.RESEARCHER: {
        PhrasingMode.CONFIDENT: "Pipeline output: n_diag={n_diagnoses}, n_act={n_actions}. L0 grade={grade}. All invariants satisfied.",
        PhrasingMode.HEDGED: "n_diag={n_diagnoses}, n_act={n_actions}. L0={grade}. Posterior uncertainty warrants field sampling.",
        PhrasingMode.RESTRICTED: "L0={grade}. Data provenance insufficient. n_diag={n_diagnoses} (unvalidated). Recommend recalibration.",
    },
}

_ISSUE_TEMPLATES = {
    ExpertiseLevel.NOVICE: "⚠️ {problem}: This could be affecting your crops. {action_hint}",
    ExpertiseLevel.FARMER: "{problem} detected ({prob:.0%} probability, severity {sev:.0%}). {action_hint}",
    ExpertiseLevel.TECHNICIAN: "{problem}: P={prob:.2f}, severity={sev:.2f}, confidence={conf:.2f}. {action_hint}",
    ExpertiseLevel.AGRONOMIST: "{problem} — p(diagnosis)={prob:.3f}, s={sev:.3f}, CI={conf:.3f}. {action_hint}",
    ExpertiseLevel.RESEARCHER: "{problem}: posterior_p={prob:.4f}, severity_index={sev:.4f}, model_confidence={conf:.4f}. {action_hint}",
}

_ACTION_TEMPLATES = {
    ExpertiseLevel.NOVICE: "👉 {action_type}: {description}",
    ExpertiseLevel.FARMER: "→ {action_type} (priority {priority:.1f}): {description}",
    ExpertiseLevel.TECHNICIAN: "{action_type} [priority={priority:.2f}, allowed={allowed}]: {description}",
    ExpertiseLevel.AGRONOMIST: "Rx: {action_type}, P_score={priority:.3f}, gate={allowed}. {description}",
    ExpertiseLevel.RESEARCHER: "ActionCard({action_type}, priority={priority:.4f}, is_allowed={allowed}). {description}",
}


class AdvisoryEngine:
    """Generates structured field overview narratives from L8 actions + L3 diagnoses."""

    def generate(
        self,
        l9_input: Layer9Input,
        persona: PersonaConfig,
        phrasing_mode: PhrasingMode,
    ) -> Dict[str, Any]:
        """
        Returns a structured advisory dict with sections:
          summary, issues, actions, outlook
        """
        exp = persona.expertise_level

        n_actions = len([a for a in l9_input.actions
                         if isinstance(a, dict) and a.get("is_allowed", True)])
        n_diagnoses = len([d for d in l9_input.diagnoses
                           if isinstance(d, dict) and d.get("probability", 0) > 0.3])

        # --- Summary ---
        template_set = _SUMMARY_TEMPLATES.get(exp, _SUMMARY_TEMPLATES[ExpertiseLevel.FARMER])
        summary_tpl = template_set.get(phrasing_mode, template_set[PhrasingMode.CONFIDENT])
        summary = summary_tpl.format(
            n_actions=n_actions,
            n_diagnoses=n_diagnoses,
            grade=l9_input.audit_grade,
        )

        # --- Issues ---
        issue_tpl = _ISSUE_TEMPLATES.get(exp, _ISSUE_TEMPLATES[ExpertiseLevel.FARMER])
        issues = []
        for diag in l9_input.diagnoses:
            if isinstance(diag, dict) and diag.get("probability", 0) > 0.3:
                problem = diag.get("problem_id", "unknown").replace("_", " ").title()
                issues.append(issue_tpl.format(
                    problem=problem,
                    prob=diag.get("probability", 0),
                    sev=diag.get("severity", 0),
                    conf=diag.get("confidence", 0),
                    action_hint=self._get_action_hint(diag, l9_input.actions, exp),
                ))

        # --- Actions ---
        action_tpl = _ACTION_TEMPLATES.get(exp, _ACTION_TEMPLATES[ExpertiseLevel.FARMER])
        actions = []
        for act in l9_input.actions:
            if isinstance(act, dict) and act.get("is_allowed", True):
                actions.append(action_tpl.format(
                    action_type=act.get("action_type", "UNKNOWN"),
                    priority=act.get("priority_score", 0),
                    allowed=act.get("is_allowed", True),
                    description=act.get("action_id", ""),
                ))

        # --- Outlook ---
        outlook = self._build_outlook(l9_input, exp, phrasing_mode)

        return {
            "summary": summary,
            "issues": issues,
            "actions": actions,
            "outlook": outlook,
            "engine": "advisory",
        }

    def _get_action_hint(self, diag: dict, actions: list, exp: ExpertiseLevel) -> str:
        """Link diagnosis to a relevant action if available."""
        pid = diag.get("problem_id", "")
        for a in actions:
            if isinstance(a, dict) and a.get("is_allowed", True):
                if pid.lower() in a.get("action_id", "").lower():
                    if exp == ExpertiseLevel.NOVICE:
                        return f"We suggest: {a.get('action_type', 'action')}"
                    return f"See action: {a.get('action_id', '')}"
        return ""

    def _build_outlook(self, l9_input: Layer9Input, exp: ExpertiseLevel,
                       mode: PhrasingMode) -> str:
        if mode == PhrasingMode.RESTRICTED:
            if exp == ExpertiseLevel.NOVICE:
                return "Let's get better data before making plans 📊"
            return "Outlook unavailable — data quality insufficient."

        forecast = l9_input.outcome_forecast
        if not forecast:
            if exp == ExpertiseLevel.NOVICE:
                return "Keep up the good work! Check back soon for updates 🌱"
            return "No forecast data available. Monitor and reassess."

        if exp == ExpertiseLevel.NOVICE:
            return "Looking ahead, things should improve if you follow the suggestions above! 🌟"
        elif exp in (ExpertiseLevel.FARMER, ExpertiseLevel.TECHNICIAN):
            return "Forecast indicates manageable conditions. Execute scheduled actions on time."
        else:
            return f"Forecast metrics: {forecast}. Evaluate against management thresholds."


advisory_engine = AdvisoryEngine()
