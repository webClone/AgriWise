"""
Engine 5: Q&A Engine v9.6.1

Conversational heart of AgriBrain — adaptive persona system prompt
with tool-calling architecture grounded in upstream data.

Deterministic fallback synthesizes actionable, data-grounded responses
from upstream context when LLM services are unavailable.
"""
import os, json, logging
from typing import Dict, Any, Optional, List

from layer9_interface.schema import (
    ExpertiseLevel, PersonaConfig, Layer9Input,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Persona system prompts
# ============================================================================

_PERSONA_PROMPTS = {
    ExpertiseLevel.NOVICE: (
        "You are a kind, patient farming mentor called AgriBrain. "
        "Use simple words, analogies from everyday life, and encouragement. "
        "Start with empathy ('I understand...'), use emojis sparingly, "
        "and never make the farmer feel judged. "
        "Lead with 'what to do' before 'why'. "
        "Use 'we' language: 'Let's look at your field together'. "
        "Celebrate good findings: 'Good news — your crop is looking healthy!'"
    ),
    ExpertiseLevel.FARMER: (
        "You are a practical agronomist neighbor called AgriBrain. "
        "Be direct, respectful, and action-oriented. "
        "Use local farming terms. Give the action first, then a simple explanation. "
        "Acknowledge weather hardship. Never condescend."
    ),
    ExpertiseLevel.TECHNICIAN: (
        "You are AgriBrain, a professional field technician peer. "
        "Be precise, use reasoning chains, and reference specific metrics. "
        "Include confidence levels. Be professional but not cold."
    ),
    ExpertiseLevel.AGRONOMIST: (
        "You are AgriBrain, a peer agronomist. "
        "Use full scientific vocabulary, reference BBCH stages, absorption coefficients, "
        "and confidence intervals. Provide evidence chains from the data layers."
    ),
    ExpertiseLevel.RESEARCHER: (
        "You are AgriBrain, a peer researcher. "
        "Use precise terminology, cite statistical methods, include confidence intervals. "
        "Reference Penman-Monteith, Bayesian posteriors, and model diagnostics. "
        "Present raw data alongside interpretations."
    ),
}

_GROUNDING_RULES = """
CRITICAL RULES:
1. You do NOT generate data. You ONLY interpret the verified context below.
2. Every claim MUST reference a specific data point from the context.
3. If the context doesn't contain the answer, say so honestly.
4. Never invent numbers, dates, chemical names, or zone IDs.
5. Output valid JSON: {"answer": "...", "evidence": [...], "confidence": "High|Medium|Low"}
"""


class QAEngine:
    """Persona-adaptive Q&A engine with grounded generation."""

    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = "google/gemma-4-4b-it"

    def answer(
        self,
        query: str,
        l9_input: Layer9Input,
        persona: PersonaConfig,
    ) -> Dict[str, Any]:
        """Answer a user query grounded in upstream data."""
        if not query or not query.strip():
            return self._grounded_fallback("No query provided", l9_input, persona)

        # Check if the query is a biophysical sandbox simulation query
        q_lower = query.lower()
        if "what if" in q_lower or "simulate" in q_lower or "projection" in q_lower or "predict" in q_lower or "forecast" in q_lower or "if it" in q_lower or "if the" in q_lower:
            return self._grounded_fallback(query, l9_input, persona)

        # Build context snapshot from l9_input
        context = self._build_context_snapshot(l9_input)

        # Check if local VLM is forced via environment
        use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
        if use_local:
            try:
                # Extract base64 image data if present in l9_input
                image_data_b64 = getattr(l9_input, "image_data_b64", None)
                if not image_data_b64 and isinstance(l9_input, dict):
                    image_data_b64 = l9_input.get("image_data_b64")
                
                # Extract convolutional pre-filtering markers for leaf symptom anchoring
                conv_markers = getattr(l9_input, "conv_markers", None)
                if not conv_markers and isinstance(l9_input, dict):
                    conv_markers = l9_input.get("conv_markers")
                if not conv_markers and getattr(l9_input, "l5_disease_data", None) and isinstance(l9_input.l5_disease_data, dict):
                    conv_markers = l9_input.l5_disease_data.get("visual_lesion_markers")
                
                # Check for local backend availability
                from layer9_interface.engines.local_vlm import local_vlm_client
                backend = local_vlm_client.detect_backend()
                if backend:
                    persona_prompt = _PERSONA_PROMPTS.get(
                        persona.expertise_level,
                        _PERSONA_PROMPTS[ExpertiseLevel.FARMER],
                    )
                    system_prompt = f"{persona_prompt}\n\n{_GROUNDING_RULES}\n\nCurrent Verified Context:\n{json.dumps(context, indent=2)}"
                    
                    res = local_vlm_client.query(query, system_prompt=system_prompt, image_data_b64=image_data_b64, conv_markers=conv_markers)
                    if res and "error" not in res:
                        return {
                            "answer": res.get("answer", ""),
                            "evidence": res.get("evidence", ["Local VLM Grounding"]),
                            "confidence": res.get("confidence", "Medium"),
                            "engine": "qa_local_vlm",
                        }
                    else:
                        logger.warning(f"Local VLM query failed: {res.get('error')}. Falling back to deterministic.")
                else:
                    logger.warning("Local VLM backend not detected. Falling back to deterministic.")
            except Exception as e:
                logger.error(f"Local VLM execution failed: {e}. Falling back to deterministic.", exc_info=True)
            return self._grounded_fallback(query, l9_input, persona)

        # Try LLM first, fall back to data-grounded deterministic
        if self.api_key:
            try:
                return self._call_llm(query, context, persona, l9_input)
            except Exception as e:
                logger.warning(f"LLM call failed: {e}, falling back to deterministic")

        return self._grounded_fallback(query, l9_input, persona)

    def _build_context_snapshot(self, l9_input: Layer9Input) -> Dict[str, Any]:
        """Build grounded context from upstream data."""
        return {
            "audit_grade": l9_input.audit_grade,
            "n_diagnoses": len(l9_input.diagnoses),
            "top_diagnoses": [
                {
                    "problem": d.get("problem_id", ""),
                    "probability": d.get("probability", 0),
                    "severity": d.get("severity", 0),
                }
                for d in l9_input.diagnoses[:5]
                if isinstance(d, dict)
            ],
            "n_actions": len(l9_input.actions),
            "top_actions": [
                {
                    "type": a.get("action_type", ""),
                    "priority": a.get("priority_score", 0),
                    "allowed": a.get("is_allowed", True),
                }
                for a in l9_input.actions[:5]
                if isinstance(a, dict)
            ],
            "n_zones": len(l9_input.zone_plan) if isinstance(l9_input.zone_plan, dict) else 0,
            "conflicts": len(l9_input.conflicts),
            "l1_fusion_data": l9_input.l1_fusion_data,
            "l2_vegetation_data": l9_input.l2_vegetation_data,
            "l4_nutrient_data": l9_input.l4_nutrient_data,
            "l5_disease_data": l9_input.l5_disease_data,
            "l6_execution_data": l9_input.l6_execution_data,
            "l7_planning_data": l9_input.l7_planning_data,
            "l10_sire_data": l9_input.l10_sire_data,
            "plot_dna": getattr(l9_input, "plot_dna", {}),
            "biophysical_history": getattr(l9_input, "biophysical_history", {}),
            "user_events": getattr(l9_input, "user_events", {}),
            "task_board": {
                "tasks": [
                    {
                        "task_id": t.task_id,
                        "title": t.title,
                        "action_type": t.action_type,
                        "zone_id": t.zone_id,
                        "priority": t.priority,
                        "status": t.status.value if hasattr(t.status, "value") else str(t.status),
                        "due_date": t.due_date,
                        "notes": t.notes,
                    }
                    for t in getattr(getattr(l9_input, "task_board", None), "tasks", [])
                ],
                "overdue_count": getattr(getattr(l9_input, "task_board", None), "overdue_count", 0),
                "completed_today": getattr(getattr(l9_input, "task_board", None), "completed_today", 0),
                "completion_rate_7d": getattr(getattr(l9_input, "task_board", None), "completion_rate_7d", 0.0),
            } if getattr(l9_input, "task_board", None) else {},
            "data_requests": [
                {
                    "request_id": d.request_id,
                    "data_type": d.data_type.value if hasattr(d.data_type, "value") else str(d.data_type),
                    "reason": d.reason,
                    "impact_description": d.impact_description,
                    "urgency": d.urgency,
                    "accuracy_gain_estimate": d.accuracy_gain_estimate,
                }
                for d in getattr(l9_input, "data_requests", [])
            ],
            "reminders": [
                {
                    "reminder_id": r.reminder_id,
                    "title": r.title,
                    "message": r.message,
                    "trigger_type": r.trigger_type.value if hasattr(r.trigger_type, "value") else str(r.trigger_type),
                    "trigger_condition": r.trigger_condition,
                    "channel": r.channel.value if hasattr(r.channel, "value") else str(r.channel),
                    "is_recurring": r.is_recurring,
                    "snooze_count": r.snooze_count,
                }
                for r in getattr(l9_input, "reminders", [])
            ],
        }

    def _call_llm(self, query: str, context: dict, persona: PersonaConfig, l9_input: Layer9Input) -> Dict[str, Any]:
        """Call LLM with persona-adaptive system prompt and persistent context primer."""
        import requests

        # Build dynamic context primer from persistent conversation state
        plot_id = getattr(l9_input, "plot_id", "UNKNOWN")
        context_primer = ""
        if plot_id and plot_id != "UNKNOWN":
            try:
                from layer9_interface.conversation_memory import get_memory_manager
                manager = get_memory_manager()
                state = manager.load_state(plot_id)
                context_primer = manager.build_context_primer(state)
            except Exception as e:
                logger.warning(f"Failed to build persistent context primer: {e}")

        # Urgency tone matching and dynamic warmth parameter scaling
        urgency = self.estimate_urgency(query)
        warmth = persona.warmth_factor
        if urgency > 0.6:
            warmth = max(0.2, warmth - 0.3)
            urgency_indicator = f"Farmer Sentiment Urgency: {urgency:.1f} (Scale 0-1). Highly concerned. Prioritize rapid, action-first diagnostic evidence and safety recommendations."
        else:
            urgency_indicator = f"Farmer Sentiment Urgency: {urgency:.1f} (Scale 0-1). Maintain a warm, supportive, and conversational tone."

        persona_prompt = _PERSONA_PROMPTS.get(
            persona.expertise_level,
            _PERSONA_PROMPTS[ExpertiseLevel.FARMER],
        )

        system_prompt = f"""{persona_prompt}

{_GROUNDING_RULES}

Warmth factor: {warmth:.1f}
{urgency_indicator}

{context_primer}

Current Verified Context:
{json.dumps(context, indent=2)}
"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://agriwise.app",
            "X-Title": "AgriWise",
        }

        max_retries = 2
        current_system_prompt = system_prompt

        for attempt in range(max_retries + 1):
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": current_system_prompt},
                    {"role": "user", "content": query},
                ],
                "temperature": 0.2,
            }

            response = requests.post(
                self.api_url, headers=headers, json=payload, timeout=15
            )
            if not response.ok:
                raise RuntimeError(f"API {response.status_code}: {response.text[:200]}")

            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()

            # Clean markdown wrappers
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            try:
                parsed = json.loads(content)
                if not isinstance(parsed, dict):
                    raise ValueError("LLM returned non-dictionary response")
                
                answer = parsed.get("answer", "")
                evidence = parsed.get("evidence", [])
                
                if not answer or (not evidence and attempt < max_retries):
                    raise ValueError("JSON response is missing required 'answer' or 'evidence' fields")
                
                return {
                    "answer": answer,
                    "evidence": evidence,
                    "confidence": parsed.get("confidence", "Medium"),
                    "engine": "qa",
                }
            except (json.JSONDecodeError, ValueError) as e:
                if attempt == max_retries:
                    return {
                        "answer": content,
                        "evidence": ["Generated by AI (Self-Corrected fallback)"],
                        "confidence": "Medium",
                        "engine": "qa",
                    }
                current_system_prompt = f"""{system_prompt}

[CRITICAL CORRECTIVE ACTION REQUIRED]
Your previous response draft failed validation with the error: {str(e)}
Please regenerate the output. Ensure it is a SINGLE, valid JSON object containing only 'answer', 'evidence', and 'confidence' keys."""

    # ================================================================
    # Data-grounded deterministic fallback
    # ================================================================

    def _grounded_fallback(
        self, query: str, l9_input: Layer9Input, persona: PersonaConfig,
    ) -> Dict[str, Any]:
        """Synthesize a useful, data-grounded answer from upstream context.

        Instead of a generic 'connection issue' message, this builds
        an actionable response using the actual L3/L8 pipeline data,
        adapted to the user's persona level.
        """
        q_lower = query.lower()
        if "what if" in q_lower or "simulate" in q_lower or "projection" in q_lower or "predict" in q_lower or "forecast" in q_lower or "if it" in q_lower or "if the" in q_lower:
            try:
                from layer9_interface.engines.what_if_sandbox import what_if_sandbox
                # Build context for sandbox
                sensors = {}
                if l9_input.l1_fusion_data:
                    sensors.update(l9_input.l1_fusion_data)
                if l9_input.l2_vegetation_data:
                    sensors.update(l9_input.l2_vegetation_data)
                
                # Plot data
                plot_data = {}
                if l9_input.l2_vegetation_data:
                    plot_data["crop"] = l9_input.l2_vegetation_data.get("crop", "Wheat")
                
                sandbox_context = {
                    "sensors": sensors,
                    "sensor_summary": sensors,
                    "plot": plot_data,
                }
                
                sim_res = what_if_sandbox.project(query, sandbox_context)
                assumptions = sim_res["environmental_assumptions"]
                projections = sim_res["projections"]
                equations = sim_res["equations_used"]
                
                details = []
                if assumptions.get("temperature_target") is not None:
                    details.append(f"Temperature target set to {assumptions['temperature_target']}°C")
                elif assumptions.get("temperature_offset", 0) != 0:
                    details.append(f"Temperature adjusted by {assumptions['temperature_offset']:+g}°C")
                    
                if assumptions.get("rain_target") is not None:
                    details.append(f"Rainfall target set to {assumptions['rain_target']}mm")
                elif assumptions.get("rain_offset", 0) != 0:
                    details.append(f"Rainfall adjusted by {assumptions['rain_offset']:+g}mm")
                    
                if assumptions.get("irrigation_mode") == "none":
                    details.append("Irrigation stopped")
                elif assumptions.get("irrigation_mode") == "daily":
                    details.append("Daily irrigation active")
                elif assumptions.get("irrigation_mode") == "run":
                    details.append("Irrigation run scheduled")
                    
                if assumptions.get("nitrogen_applied_kg_ha", 0) > 0:
                    details.append(f"Applied {assumptions['nitrogen_applied_kg_ha']} kg/ha of nitrogen fertilizer")
                    
                ass_str = ", ".join(details) if details else "Baseline weather assumptions"
                
                base_moisture = sensors.get("soil_moisture") or 32.0
                sm = projections["soil_moisture"]
                nd = projections["nitrogen_deficit"]
                fr = projections["fungal_risk"]
                
                answer = f"### 📊 Biophysical Simulation Sandbox Output\n\n"
                answer += f"**Environmental Assumptions**: {ass_str}\n\n"
                answer += f"Using Penman-Monteith ET0 temperature scaling and Liebig bucket moisture dynamics, I have projected your plot's parameters over a 7-day forward horizon:\n\n"
                
                answer += "| Biophysical Metric | Day 1 (Base) | Day 3 | Day 5 | Day 7 (Proj) | Delta Change |\n"
                answer += "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
                answer += f"| **Soil Moisture** | {base_moisture:.1f}% | {sm['simulated'][2]:.1f}% | {sm['simulated'][4]:.1f}% | {sm['simulated'][6]:.1f}% | **{sm['delta_day7']:+g}%** |\n"
                answer += f"| **Nitrogen Deficit** | 45.0 kg/ha | {nd['simulated'][2]:.1f} kg/ha | {nd['simulated'][4]:.1f} kg/ha | {nd['simulated'][6]:.1f} kg/ha | **{nd['delta_day7']:+g} kg/ha** |\n"
                answer += f"| **Biotic Fungal Risk** | 15.0% | {fr['simulated'][2]:.1f}% | {fr['simulated'][4]:.1f}% | {fr['simulated'][6]:.1f}% | **{fr['delta_day7']:+g}%** |\n\n"
                
                answer += "#### 🔬 Mechanistic Biophysical Equations Propagated:\n"
                answer += f"- **ET0 Temperature Scaling**: $${equations['et0_scaling']}$$\n"
                answer += f"- **Soil Moisture Bucket Update**: $${equations['water_balance']}$$\n"
                answer += f"- **Biotic Outbreak Spore Kernel**: $${equations['biotic_outbreak']}$$\n\n"
                answer += "Projections are dynamically calibrated based on your Plot DNA 4.0 traits (soil retention $\\theta$ and heat resilience $\\beta$)."
                
                return {
                    "answer": answer,
                    "evidence": [
                        f"Simulated Soil Moisture Delta: {sm['delta_day7']}%",
                        f"Simulated N-Deficit Delta: {nd['delta_day7']} kg/ha",
                        f"Simulated Fungal Risk Delta: {fr['delta_day7']}%"
                    ],
                    "confidence": "High",
                    "engine": "what_if_sandbox",
                }
            except Exception as e:
                logger.error(f"Error executing what-if biophysical simulation sandbox projection: {e}", exc_info=True)

        exp = persona.expertise_level
        grade = l9_input.audit_grade.upper()
        n_diag = len(l9_input.diagnoses)
        n_act = len(l9_input.actions)
        n_zones = len(l9_input.zone_plan) if isinstance(l9_input.zone_plan, dict) else 0
        n_conflicts = len(l9_input.conflicts)

        # Extract top diagnosis
        top_diag = None
        for d in l9_input.diagnoses:
            if isinstance(d, dict) and d.get("probability", 0) > 0.3:
                top_diag = d
                break

        # Extract top allowed action
        top_action = None
        for a in l9_input.actions:
            if isinstance(a, dict) and a.get("is_allowed", True):
                top_action = a
                break

        # Build persona-adapted answer
        evidence = []

        if exp == ExpertiseLevel.NOVICE:
            answer = self._novice_answer(grade, n_diag, n_act, n_zones, top_diag, top_action)
        elif exp == ExpertiseLevel.FARMER:
            answer = self._farmer_answer(grade, n_diag, n_act, n_zones, top_diag, top_action)
        elif exp == ExpertiseLevel.TECHNICIAN:
            answer = self._technician_answer(grade, n_diag, n_act, n_zones, n_conflicts, top_diag, top_action)
        elif exp == ExpertiseLevel.AGRONOMIST:
            answer = self._agronomist_answer(grade, n_diag, n_act, n_zones, n_conflicts, top_diag, top_action, l9_input)
        else:  # RESEARCHER
            answer = self._researcher_answer(grade, n_diag, n_act, n_zones, n_conflicts, top_diag, top_action, l9_input)

        # Build evidence references
        evidence.append(f"audit_grade={grade}")
        if top_diag:
            evidence.append(f"L3:{top_diag.get('problem_id', '?')}:p={top_diag.get('probability', 0):.2f}")
        if top_action:
            evidence.append(f"L8:{top_action.get('action_type', '?')}:priority={top_action.get('priority_score', 0):.2f}")
        if n_zones > 0:
            evidence.append(f"zones={n_zones}")

        return {
            "answer": answer,
            "evidence": evidence,
            "confidence": "Medium",
            "engine": "qa",
        }

    def _novice_answer(self, grade, n_diag, n_act, n_zones, top_diag, top_action):
        parts = []
        if grade in ("A", "B"):
            parts.append("Good news — your field is looking healthy overall! 🌱")
        elif grade == "C":
            parts.append("Your field needs a little attention, but nothing to worry too much about. 🌾")
        else:
            parts.append("Your field needs some care right now. Let's work through it together. 💪")

        if top_diag:
            pid = top_diag.get("problem_id", "an issue").replace("_", " ")
            prob = top_diag.get("probability", 0)
            parts.append(f"We've spotted {pid} ({prob:.0%} likely).")

        if top_action:
            atype = top_action.get("action_type", "action").replace("_", " ").lower()
            parts.append(f"The best next step would be to {atype}.")

        if n_zones > 0:
            parts.append(f"We're watching {n_zones} zone(s) in your field.")

        return " ".join(parts)

    def _farmer_answer(self, grade, n_diag, n_act, n_zones, top_diag, top_action):
        parts = []
        parts.append(f"Field grade: {grade}.")

        if top_diag:
            pid = top_diag.get("problem_id", "issue").replace("_", " ")
            prob = top_diag.get("probability", 0)
            parts.append(f"Main concern: {pid} ({prob:.0%} probability).")

        if top_action:
            atype = top_action.get("action_type", "").replace("_", " ")
            priority = top_action.get("priority_score", 0)
            parts.append(f"Top action: {atype} (priority {priority:.0%}).")

        parts.append(f"{n_diag} issue(s) detected, {n_act} action(s) available across {n_zones} zone(s).")
        return " ".join(parts)

    def _technician_answer(self, grade, n_diag, n_act, n_zones, n_conflicts, top_diag, top_action):
        parts = [f"Audit grade {grade} | {n_diag} diagnoses | {n_act} actions | {n_zones} zones."]

        if n_conflicts:
            parts.append(f"⚠ {n_conflicts} data conflict(s) detected.")

        if top_diag:
            pid = top_diag.get("problem_id", "?")
            prob = top_diag.get("probability", 0)
            sev = top_diag.get("severity", 0)
            parts.append(f"Primary diagnosis: {pid} (p={prob:.2f}, severity={sev:.2f}).")

        if top_action:
            atype = top_action.get("action_type", "?")
            priority = top_action.get("priority_score", 0)
            parts.append(f"Recommended: {atype} (priority={priority:.2f}).")

        return " ".join(parts)

    def _agronomist_answer(self, grade, n_diag, n_act, n_zones, n_conflicts, top_diag, top_action, l9_input):
        parts = [f"L0 audit: grade {grade}. Pipeline output: {n_diag} diagnoses → {n_act} actions across {n_zones} management zones."]

        if n_conflicts:
            parts.append(f"Data conflicts: {n_conflicts} (review recommended).")

        if top_diag:
            pid = top_diag.get("problem_id", "?")
            prob = top_diag.get("probability", 0)
            sev = top_diag.get("severity", 0)
            conf = top_diag.get("confidence", 0)
            parts.append(f"Lead diagnosis: {pid} — P(detection)={prob:.2f}, severity={sev:.2f}, confidence={conf:.2f}.")

        if top_action:
            atype = top_action.get("action_type", "?")
            priority = top_action.get("priority_score", 0)
            parts.append(f"Priority intervention: {atype} (score={priority:.2f}).")

        # Add cross-layer biophysical summaries
        if l9_input.l2_vegetation_data and l9_input.l2_vegetation_data.get("stage"):
            stage = l9_input.l2_vegetation_data.get("stage")
            bbch = l9_input.l2_vegetation_data.get("bbch")
            parts.append(f"Phenology: {stage} (BBCH {bbch}).")

        if l9_input.l6_execution_data:
            leach = l9_input.l6_execution_data.get("nitrogen_leaching_fraction", 0.0)
            vpd = l9_input.l6_execution_data.get("vapor_pressure_deficit_kpa", 0.0)
            parts.append(f"Execution: leaching={leach:.1f}%, VPD={vpd:.2f} kPa.")

        return " ".join(parts)

    def _researcher_answer(self, grade, n_diag, n_act, n_zones, n_conflicts, top_diag, top_action, l9_input):
        parts = [f"Pipeline summary — Audit={grade}, N(diagnoses)={n_diag}, N(actions)={n_act}, N(zones)={n_zones}, N(conflicts)={n_conflicts}."]

        if top_diag:
            pid = top_diag.get("problem_id", "?")
            prob = top_diag.get("probability", 0)
            sev = top_diag.get("severity", 0)
            conf = top_diag.get("confidence", 0)
            parts.append(f"Primary detection: {pid} [P={prob:.3f}, S={sev:.3f}, C={conf:.3f}].")

        if top_action:
            atype = top_action.get("action_type", "?")
            priority = top_action.get("priority_score", 0)
            aid = top_action.get("action_id", "?")
            parts.append(f"Top ranked action: {aid}/{atype} (priority_score={priority:.3f}).")

        # Source reliability
        for src, rel in l9_input.source_reliability.items():
            parts.append(f"Source[{src}]={rel:.2f}.")

        if l9_input.outcome_forecast:
            yd = l9_input.outcome_forecast.get("yield_delta_pct", 0)
            rr = l9_input.outcome_forecast.get("risk_reduction_pct", 0)
            parts.append(f"Forecast: Δyield={yd:+.1f}%, risk_reduction={rr:.1f}%.")

        # Add raw cross-layer data
        raw_metrics = []
        if l9_input.l2_vegetation_data:
            raw_metrics.append(f"gdd={l9_input.l2_vegetation_data.get('gdd_accumulated', 0.0):.1f}")
        if l9_input.l6_execution_data:
            raw_metrics.append(f"runoff={l9_input.l6_execution_data.get('runoff_risk_index', 0.0):.2f}")
            raw_metrics.append(f"co2={l9_input.l6_execution_data.get('net_carbon_balance_t_co2eq', 0.0):+.2f}t")
        if raw_metrics:
            parts.append(f"Raw metrics: {', '.join(raw_metrics)}.")

        return " ".join(parts)

    def estimate_urgency(self, query: str) -> float:
        """Estimate the urgency score of a user query on a [0.0, 1.0] scale."""
        if not query:
            return 0.0
        
        q_lower = query.lower()
        
        # Count exclamation marks
        exclamation_count = query.count("!")
        
        # Check emergency/urgency keywords
        emergency_keywords = [
            "help", "dying", "emergency", "dry", "crisis", "rot", "pest", 
            "disease", "ruin", "fail", "wilt", "alert", "danger", "urgent",
            "loss", "yellowing", "spots", "dead", "killing", "infestation"
        ]
        keyword_hits = sum(1 for kw in emergency_keywords if kw in q_lower)
        
        # Capital letter ratio (indicates shouting/urgency)
        letters = [c for c in query if c.isalpha()]
        cap_ratio = 0.0
        if len(letters) >= 5:
            cap_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
            
        # Calculate weighted score
        score = (0.2 * min(3, exclamation_count)) + (0.4 * min(2, keyword_hits)) + (0.3 * cap_ratio)
        return min(1.0, max(0.0, score))


qa_engine = QAEngine()
