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
        self.model = "qwen/qwen3-vl-235b-a22b-thinking"

    def answer(
        self,
        query: str,
        l9_input: Layer9Input,
        persona: PersonaConfig,
    ) -> Dict[str, Any]:
        """Answer a user query grounded in upstream data."""
        if not query or not query.strip():
            return self._grounded_fallback("No query provided", l9_input, persona)

        # Build context snapshot from l9_input
        context = self._build_context_snapshot(l9_input)

        # Try LLM first, fall back to data-grounded deterministic
        if self.api_key:
            try:
                return self._call_llm(query, context, persona)
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
        }

    def _call_llm(self, query: str, context: dict, persona: PersonaConfig) -> Dict[str, Any]:
        """Call LLM with persona-adaptive system prompt."""
        import requests

        persona_prompt = _PERSONA_PROMPTS.get(
            persona.expertise_level,
            _PERSONA_PROMPTS[ExpertiseLevel.FARMER],
        )

        system_prompt = f"""{persona_prompt}

{_GROUNDING_RULES}

Current Verified Context:
{json.dumps(context, indent=2)}
"""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://agriwise.app",
            "X-Title": "AgriWise",
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
            return {
                "answer": parsed.get("answer", content),
                "evidence": parsed.get("evidence", []),
                "confidence": parsed.get("confidence", "Medium"),
                "engine": "qa",
            }
        except json.JSONDecodeError:
            return {
                "answer": content,
                "evidence": ["Generated by AI"],
                "confidence": "Medium",
                "engine": "qa",
            }

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
            answer = self._agronomist_answer(grade, n_diag, n_act, n_zones, n_conflicts, top_diag, top_action)
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

    def _agronomist_answer(self, grade, n_diag, n_act, n_zones, n_conflicts, top_diag, top_action):
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

        return " ".join(parts)


qa_engine = QAEngine()
