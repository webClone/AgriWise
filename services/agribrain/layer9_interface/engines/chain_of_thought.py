"""
chain_of_thought.py - Structured Multi-Step Reasoning for Small LLMs
=====================================================================

Instead of asking a 4B model to do everything in one call (understand context,
reason about agronomics, generate structured response), we break it into 
3 focused steps:

  Step 1 - EXTRACT: Pull relevant metrics from context (structured JSON)
  Step 2 - REASON:  Apply agronomic logic to extracted metrics
  Step 3 - RESPOND: Generate the farmer-facing natural language response

This dramatically improves quality on small models like Gemma 4 4B because
each step has a narrow, well-defined task.
"""

import json
import time
import re
from typing import Dict, Any, Optional, List, Tuple


class ChainOfThoughtRouter:
    """Multi-step reasoning pipeline for small LLMs."""

    def __init__(self, query_fn=None):
        """
        Args:
            query_fn: Function(question, system_prompt) -> {"answer": str}
                      If None, uses the local_vlm_client.
        """
        self._query_fn = query_fn

    def _query(self, question: str, system_prompt: str) -> str:
        """Send a query to the LLM."""
        if self._query_fn:
            res = self._query_fn(question, system_prompt=system_prompt)
        else:
            from layer9_interface.engines.local_vlm import local_vlm_client
            res = local_vlm_client.query(question, system_prompt=system_prompt)

        if res and isinstance(res, dict):
            return res.get("answer", res.get("error", ""))
        return str(res) if res else ""

    def _extract_json(self, text: str) -> Optional[Dict]:
        """Try to extract a JSON object from LLM text output."""
        # Try direct parse
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try finding first { ... } block
        brace_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        return None

    # ================================================================
    # Step 1: EXTRACT — Pull relevant metrics from context
    # ================================================================

    def step_extract(self, query: str, field_context: str) -> Dict[str, Any]:
        """Extract relevant metrics from the field context for this query."""
        system_prompt = """You are a data extraction assistant. Given a field context 
and a farmer's question, extract ONLY the relevant metrics needed to answer.

Respond in JSON format:
{
    "relevant_metrics": {
        "metric_name": "value with units"
    },
    "query_type": "irrigation|nutrient|disease|weather|soil|growth|planning|general",
    "data_gaps": ["list of data that would help but is missing"]
}

RULES:
- Only include metrics that are PRESENT in the context
- Do NOT invent or estimate values
- Mark missing but needed data in data_gaps"""

        user_msg = f"FIELD CONTEXT:\n{field_context}\n\nFARMER QUESTION: {query}"
        raw = self._query(user_msg, system_prompt)
        extracted = self._extract_json(raw)

        if not extracted:
            # Fallback: return raw text as a simple extraction
            return {
                "relevant_metrics": {"raw_context": field_context[:500]},
                "query_type": "general",
                "data_gaps": [],
                "extraction_quality": "FALLBACK"
            }

        extracted["extraction_quality"] = "OK"
        return extracted

    # ================================================================
    # Step 2: REASON — Apply agronomic logic
    # ================================================================

    def step_reason(self, query: str, extracted: Dict[str, Any]) -> Dict[str, Any]:
        """Apply agronomic reasoning to extracted metrics."""
        metrics_str = json.dumps(extracted.get("relevant_metrics", {}), indent=2)
        query_type = extracted.get("query_type", "general")
        data_gaps = extracted.get("data_gaps", [])

        system_prompt = f"""You are an expert agronomist reasoning engine. 
Given extracted field metrics and a farmer's question, provide agronomic analysis.

The question category is: {query_type}

Respond in JSON format:
{{
    "assessment": "1-2 sentence agronomic assessment",
    "confidence": "HIGH|MEDIUM|LOW",
    "key_findings": ["finding 1", "finding 2"],
    "recommendations": ["action 1", "action 2"],
    "risk_level": "NONE|LOW|MEDIUM|HIGH|CRITICAL",
    "reasoning": "Brief chain of agronomic reasoning connecting metrics to conclusions"
}}

RULES:
- Base ALL conclusions on the provided metrics
- If data is insufficient, say so and set confidence to LOW
- Use standard agronomic thresholds (e.g., soil moisture < 20% = stress for wheat)
- Consider crop stage in your reasoning"""

        user_msg = f"""EXTRACTED METRICS:
{metrics_str}

DATA GAPS: {data_gaps}

FARMER QUESTION: {query}"""

        raw = self._query(user_msg, system_prompt)
        reasoned = self._extract_json(raw)

        if not reasoned:
            return {
                "assessment": raw[:300] if raw else "Unable to reason about the data.",
                "confidence": "LOW",
                "key_findings": [],
                "recommendations": [],
                "risk_level": "UNKNOWN",
                "reasoning": raw[:500] if raw else "",
                "reasoning_quality": "FALLBACK"
            }

        reasoned["reasoning_quality"] = "OK"
        return reasoned

    # ================================================================
    # Step 3: RESPOND — Generate farmer-facing response
    # ================================================================

    def step_respond(self, query: str, reasoned: Dict[str, Any],
                     experience_level: str = "INTERMEDIATE") -> str:
        """Generate the final farmer-facing response."""
        assessment = reasoned.get("assessment", "")
        findings = reasoned.get("key_findings", [])
        recommendations = reasoned.get("recommendations", [])
        risk = reasoned.get("risk_level", "UNKNOWN")
        reasoning = reasoned.get("reasoning", "")
        confidence = reasoned.get("confidence", "MEDIUM")

        system_prompt = f"""You are AgriBrain, a warm and practical agronomist colleague.
Convert the following agronomic analysis into a natural, conversational response.

FARMER EXPERIENCE LEVEL: {experience_level}

STYLE RULES:
- Speak naturally as a colleague, NOT as a textbook
- Use flowing paragraphs, not rigid sections
- For BEGINNER: Use simple analogies, avoid jargon
- For INTERMEDIATE: Use standard farming terms
- For EXPERT: Include technical details
- Be warm, practical, and actionable
- Use metric units (mm, kg/ha, degrees C)
- Bold key numbers and recommendations
- Keep it concise: 3-8 sentences for simple questions, up to 15 for complex ones
- Start with the most important point
- If confidence is LOW, honestly say what data is missing"""

        user_msg = f"""AGRONOMIC ANALYSIS:
Assessment: {assessment}
Confidence: {confidence}
Risk Level: {risk}
Key Findings: {json.dumps(findings)}
Recommendations: {json.dumps(recommendations)}
Reasoning Chain: {reasoning}

ORIGINAL FARMER QUESTION: {query}

Write a natural, conversational response:"""

        response = self._query(user_msg, system_prompt)
        return response

    # ================================================================
    # Full Pipeline
    # ================================================================

    def run(self, query: str, field_context: str,
            experience_level: str = "INTERMEDIATE") -> Dict[str, Any]:
        """Run the full 3-step chain-of-thought pipeline.
        
        Returns:
            {
                "response": str,         # Final farmer-facing text
                "extraction": dict,      # Step 1 output
                "reasoning": dict,       # Step 2 output
                "timing": dict,          # Per-step timing
                "total_latency_ms": float
            }
        """
        t_total = time.time()
        timing = {}

        # Step 1: Extract
        t1 = time.time()
        extracted = self.step_extract(query, field_context)
        timing["extract_ms"] = (time.time() - t1) * 1000

        # Step 2: Reason
        t2 = time.time()
        reasoned = self.step_reason(query, extracted)
        timing["reason_ms"] = (time.time() - t2) * 1000

        # Step 3: Respond
        t3 = time.time()
        response = self.step_respond(query, reasoned, experience_level)
        timing["respond_ms"] = (time.time() - t3) * 1000

        total_ms = (time.time() - t_total) * 1000
        timing["total_ms"] = total_ms

        return {
            "response": response,
            "extraction": extracted,
            "reasoning": reasoned,
            "timing": timing,
            "total_latency_ms": total_ms
        }


# ============================================================================
# Convenience: Single-call CoT for the chat adapter
# ============================================================================

_cot_router = None

def get_cot_router() -> ChainOfThoughtRouter:
    """Get or create the singleton CoT router."""
    global _cot_router
    if _cot_router is None:
        _cot_router = ChainOfThoughtRouter()
    return _cot_router


def cot_query(query: str, field_context: str,
              experience_level: str = "INTERMEDIATE") -> Dict[str, Any]:
    """One-call convenience function for CoT reasoning."""
    router = get_cot_router()
    return router.run(query, field_context, experience_level)
