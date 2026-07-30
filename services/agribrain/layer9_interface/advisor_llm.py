"""
Layer 9.1: Grounded Advisory Generator.
Constructs prompt context for LLM to generate the "AgriBrain Analysis" narrative.
"""

from typing import Dict, Any, List
import json

class AdvisoryGenerator:
    
    def prepare_context(self, 
                        plot_meta: Dict[str, Any],
                        trust_report: Dict[str, Any],
                        yield_forecast: Dict[str, Any],
                        risk_profile: Dict[str, Any],
                        ranked_actions: List[Dict[str, Any]]) -> str:
        """
        Assemble the 'Ground Truth' JSON for the LLM.
        This forces the LLM to be a 'Narrator', not a 'Predictor'.
        """
        context = {
            "plot": plot_meta,
            "trust": {
                "score": trust_report.get("trust_score"),
                "tier": trust_report.get("trust_level"),
                "reasons": trust_report.get("issues", [])
            },
            "yield": {
                "mean": yield_forecast.get("yield_mean_t_ha"),
                "p10": yield_forecast.get("yield_p10"),
                "p90": yield_forecast.get("yield_p90"),
                "attribution": yield_forecast.get("attribution", {})
            },
            "risk": {
                "score": risk_profile.get("risk_score"),
                "level": risk_profile.get("risk_level"),
                "drivers": risk_profile.get("top_drivers", [])
            },
            "top_actions": [
                {
                    "action": a.get("action"),
                    "profit_gain": a.get("expected_profit"),
                    "confidence": a.get("confidence"),
                    "reason": a.get("reason")
                }
                for a in ranked_actions[:3] # Top 3 only
            ]
        }
        return json.dumps(context, indent=2)

    def generate_prompt(self, context_json: str) -> str:
        """
        Create the System Prompt + User Prompt.
        """
        system_prompt = (
            "You are AgriBrain, an expert AI agronomist. "
            "Your role is to Explain, not Predict. Use the provided JSON data to generate a report. "
            "Do NOT invent numbers. If data is missing or trust is low, explicitely state that."
        )
        
        user_prompt = (
            f"Here is the current plot status:\n{context_json}\n\n"
            "Generate a structured analysis with these sections:\n"
            "1. Summary (1 sentence)\n"
            "2. What's Happening (Yield/Risk context)\n"
            "3. Top Actions (What to do & Why)\n"
            "4. Warnings (Data gaps or low confidence)"
        )
        
        return f"SYSTEM: {system_prompt}\nUSER: {user_prompt}"

    def mock_response(self, context_json: str) -> Dict[str, Any]:
        """
        Simulate LLM generation for testing/offline mode.
        """
        data = json.loads(context_json)
        actions = data.get("top_actions", [])
        risk = data.get("risk", {})
        
        summary = f"Risk is {risk.get('level')} due to {', '.join(risk.get('drivers', []))}."
        action_text = "No urgent actions."
        if actions:
            top = actions[0]
            action_text = f"Priority: {top['action']} to gain ${top['profit_gain']}."
            
        return {
            "summary": summary,
            "what_happening": f"Yield is projected at {data['yield']['mean']}t/ha.",
            "top_actions": action_text,
            "warnings": f"Trust is {data['trust']['tier']}."
        }

# Singleton
advisor = AdvisoryGenerator()
