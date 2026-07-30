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
          summary, issues, actions, outlook, sandbox_cooperative_suggestions
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

        # --- Fetch Crop Specific Thresholds from Agronomic Knowledge Graph ---
        crop_name = ""
        if l9_input.l2_vegetation_data and isinstance(l9_input.l2_vegetation_data, dict) and l9_input.l2_vegetation_data.get("crop"):
            crop_name = l9_input.l2_vegetation_data.get("crop")
        elif l9_input.l7_planning_data and isinstance(l9_input.l7_planning_data, dict) and l9_input.l7_planning_data.get("chosen_crop"):
            crop_name = l9_input.l7_planning_data.get("chosen_crop")

        crop_info = None
        if crop_name:
            try:
                from layer9_interface.engines.agronomic_knowledge_graph import lookup_crop
                crop_info = lookup_crop(crop_name)
            except Exception:
                pass

        # --- Issues & Abiotic Threshold Monitoring ---
        issue_tpl = _ISSUE_TEMPLATES.get(exp, _ISSUE_TEMPLATES[ExpertiseLevel.FARMER])
        issues = []

        # 1. Pipeline-reported diagnoses
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

        # 2. Ground-truth biophysical threshold checking (Abiotic / GDD)
        if crop_info:
            temp = None
            moisture = None
            if l9_input.l1_fusion_data and isinstance(l9_input.l1_fusion_data, dict):
                temp = l9_input.l1_fusion_data.get("temperature_c")
                moisture = l9_input.l1_fusion_data.get("soil_moisture")

            # Check heat stress
            if temp is not None and temp > crop_info.heat_stress_temp:
                issues.append(f"Abiotic Heat Stress: telemetry temperature ({temp:.1f}°C) exceeds the maximum thermal threshold ({crop_info.heat_stress_temp:.1f}°C) for {crop_name}.")
            # Check cold/frost damage
            if temp is not None and temp < crop_info.frost_damage_temp:
                issues.append(f"Critical Frost Hazard: temperature ({temp:.1f}°C) is below the freezing damage threshold ({crop_info.frost_damage_temp:.1f}°C) for {crop_name}.")

            # Check moisture thresholds
            if moisture is not None:
                if moisture < crop_info.wilting_point:
                    issues.append(f"Severe Wilting Hazard: soil moisture ({moisture:.1f}%) is below the permanent wilting point ({crop_info.wilting_point:.1f}%) for {crop_name}.")
                elif moisture < crop_info.stress_threshold:
                    issues.append(f"Active Water Stress: soil moisture ({moisture:.1f}%) is below the transpiration stress threshold ({crop_info.stress_threshold:.1f}%) for {crop_name}.")
                elif moisture > crop_info.waterlogging_threshold:
                    issues.append(f"Anoxia / Waterlogging warning: soil moisture ({moisture:.1f}%) exceeds the aeration threshold ({crop_info.waterlogging_threshold:.1f}%) for {crop_name}.")

            # Phenological GDD Indicators Infusion
            gdd = None
            if l9_input.l2_vegetation_data and isinstance(l9_input.l2_vegetation_data, dict):
                gdd = l9_input.l2_vegetation_data.get("gdd_accumulated")
            if gdd is not None:
                heading_gdd = crop_info.gdd_to_heading
                maturity_gdd = crop_info.gdd_to_maturity
                pct_heading = min(100.0, (gdd / heading_gdd) * 100.0) if heading_gdd else 0.0
                pct_maturity = min(100.0, (gdd / maturity_gdd) * 100.0) if maturity_gdd else 0.0
                issues.append(f"Phenological GDD: crop has accumulated {gdd:.0f} GDD ({pct_heading:.1f}% to heading, {pct_maturity:.1f}% to maturity).")

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
        outlook = self._build_outlook_with_crop(l9_input, exp, phrasing_mode, crop_info)

        # --- Dynamic Cooperative turns (pass advisory context to sandbox simulation ideas) ---
        sandbox_cooperative_suggestions = []
        if n_diagnoses > 0 or len(issues) > 0:
            issues_joined = " ".join(issues).lower()
            if "water" in issues_joined or "moisture" in issues_joined or "wilt" in issues_joined:
                sandbox_cooperative_suggestions.append("What if we apply 20mm of irrigation tomorrow?")
                sandbox_cooperative_suggestions.append("What if no irrigation is applied for the next 7 days?")
            if "nitrogen" in issues_joined or "nutrient" in issues_joined or "leach" in issues_joined:
                sandbox_cooperative_suggestions.append("What if we top-dress 45 kg/ha of nitrogen fertilizer?")
            if "heat" in issues_joined or "temperature" in issues_joined or "sirocco" in issues_joined:
                sandbox_cooperative_suggestions.append("What if daily temperature increases by 4°C due to hot winds?")
        if not sandbox_cooperative_suggestions:
            sandbox_cooperative_suggestions.append("What if we double our daily irrigation runtime?")

        return {
            "summary": summary,
            "issues": issues,
            "actions": actions,
            "outlook": outlook,
            "sandbox_cooperative_suggestions": sandbox_cooperative_suggestions,
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

    def _build_outlook_with_crop(self, l9_input: Layer9Input, exp: ExpertiseLevel,
                                mode: PhrasingMode, crop_info: Optional[Any]) -> str:
        if mode == PhrasingMode.RESTRICTED:
            if exp == ExpertiseLevel.NOVICE:
                return "Let's get better data before making plans 📊"
            return "Outlook unavailable — data quality insufficient."

        forecast = l9_input.outcome_forecast
        
        # Add rich biophysical details for advanced expertise levels
        details = []
        if exp in (ExpertiseLevel.TECHNICIAN, ExpertiseLevel.AGRONOMIST, ExpertiseLevel.RESEARCHER):
            if l9_input.l6_execution_data:
                leach = l9_input.l6_execution_data.get("nitrogen_leaching_fraction", 0.0)
                vpd = l9_input.l6_execution_data.get("vapor_pressure_deficit_kpa", 0.0)
                details.append(f"L6 Leaching: {leach:.1f}%, VPD: {vpd:.2f} kPa")
            if l9_input.l2_vegetation_data:
                gdd = l9_input.l2_vegetation_data.get("gdd_accumulated", 0.0)
                details.append(f"L2 GDD: {gdd:.0f}")
            if l9_input.l7_planning_data and isinstance(l9_input.l7_planning_data, dict) and l9_input.l7_planning_data.get("chosen_crop"):
                details.append(f"L7 Suitability: {l9_input.l7_planning_data.get('chosen_crop')}")
            if crop_info:
                details.append(f"Target: FC={crop_info.field_capacity}%, ST={crop_info.stress_threshold}%, GDD_mat={crop_info.gdd_to_maturity}")

        base_outlook = ""
        if not forecast:
            if exp == ExpertiseLevel.NOVICE:
                base_outlook = "Keep up the good work! Check back soon for updates 🌱"
            else:
                base_outlook = "No forecast data available. Monitor and reassess."
        elif exp == ExpertiseLevel.NOVICE:
            base_outlook = "Looking ahead, things should improve if you follow the suggestions above! 🌟"
        elif exp in (ExpertiseLevel.FARMER, ExpertiseLevel.TECHNICIAN):
            base_outlook = "Forecast indicates manageable conditions. Execute scheduled actions on time."
        else:
            base_outlook = f"Forecast metrics: {forecast}. Evaluate against management thresholds."

        # Add farmer-friendly tips derived from the knowledge graph
        tip = ""
        if crop_info and exp in (ExpertiseLevel.NOVICE, ExpertiseLevel.FARMER):
            tip = f" (Optimal growth temperature: {crop_info.optimal_growth_temp_low}°C - {crop_info.optimal_growth_temp_high}°C. Keep moisture above {crop_info.stress_threshold}%.)"

        if details:
            return f"{base_outlook}{tip} [{', '.join(details)}]"
        return f"{base_outlook}{tip}"

    def _build_outlook(self, l9_input: Layer9Input, exp: ExpertiseLevel,
                       mode: PhrasingMode) -> str:
        """Deprecated: using _build_outlook_with_crop instead for GDD integration."""
        return self._build_outlook_with_crop(l9_input, exp, mode, None)


advisory_engine = AdvisoryEngine()
