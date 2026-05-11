import os
import json
import logging
import asyncio
import aiohttp
import time
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct:free"

SYSTEM_PROMPT = """You are AgriBrain's Conversational Intelligence Engine.
Your task is to take a deterministic baseline template and rewrite it to flow naturally, using the exact numerical facts provided in the raw data.
You must output STRICT JSON matching the schema below.
DO NOT hallucinate facts, numbers, or recommendations.
DO NOT output markdown formatting like ```json.

Output Schema:
{
  "farmer_summary": "Warm, human-readable takeaway (1-2 sentences)",
  "expert_summary": "Analytical summary including numbers and reasoning",
  "why_it_matters": "Contextual reason why this data matters",
  "confidence_reason": "Short explanation of the confidence level"
}
"""

# Circuit breaker for primary (OpenRouter)
_CIRCUIT_TRIPPED_AT: Optional[float] = None
_CIRCUIT_RESET_AFTER = 300.0  # 5 minutes

def _circuit_open() -> bool:
    global _CIRCUIT_TRIPPED_AT
    if _CIRCUIT_TRIPPED_AT is None:
        return False
    if time.time() - _CIRCUIT_TRIPPED_AT > _CIRCUIT_RESET_AFTER:
        _CIRCUIT_TRIPPED_AT = None  # Reset
        return False
    return True

def _trip_circuit(status: int) -> None:
    global _CIRCUIT_TRIPPED_AT
    _CIRCUIT_TRIPPED_AT = time.time()
    logger.warning(f"[LLM] Primary circuit breaker tripped (HTTP {status}). Disabled for {int(_CIRCUIT_RESET_AFTER/60)} min.")

# Circuit breaker for fallback (Gemini API) - Per Model
_GEMINI_CIRCUITS: Dict[str, float] = {}

def _gemini_circuit_open(model: str) -> bool:
    tripped_at = _GEMINI_CIRCUITS.get(model)
    if tripped_at is None:
        return False
    if time.time() - tripped_at > _CIRCUIT_RESET_AFTER:
        del _GEMINI_CIRCUITS[model]
        return False
    return True

def _trip_gemini_circuit(model: str, status: int) -> None:
    _GEMINI_CIRCUITS[model] = time.time()
    logger.warning(f"[LLM] Fallback circuit breaker tripped for {model} (HTTP {status}). Disabled for {int(_CIRCUIT_RESET_AFTER/60)} min.")

async def _call_gemini_api(session: aiohttp.ClientSession, model: str, system_prompt: str, user_prompt: str) -> Optional[str]:
    if not GEMINI_API_KEY or _gemini_circuit_open(model):
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": f"SYSTEM:\n{system_prompt}\n\nUSER:\n{user_prompt}"}]}],
        "generationConfig": {"temperature": 0.3}
    }
    
    # Only use JSON mode for Gemini models, Gemma API throws 500s often with it
    if "gemini" in model.lower():
        payload["generationConfig"]["responseMimeType"] = "application/json"
    try:
        async with session.post(url, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                candidates = data.get("candidates", [])
                if not candidates: return None
                parts = candidates[0].get("content", {}).get("parts", [])
                content = ""
                for p in parts:
                    if not p.get("thought"):
                        content += p.get("text", "")
                return content
            else:
                if resp.status in (429, 403):
                    _trip_gemini_circuit(model, resp.status)
                logger.warning(f"Gemini API returned {resp.status} for model {model}")
                return None
    except Exception as e:
        logger.warning(f"Gemini API error for {model}: {e}")
        # If it's a massive timeout across multiple calls, trip it to save UI latency
        if isinstance(e, asyncio.TimeoutError) or "Timeout" in str(e):
             _trip_gemini_circuit(model, 408)
        return None

async def enhance_explainability(layer_id: str, base_template: dict, raw_data: dict) -> Dict[str, Any]:
    """
    Enhances the baseline deterministic template using an LLM via OpenRouter.
    Falls back to Gemini and then Gemma if OpenRouter fails, times out, or returns invalid JSON.
    """
    prompt = f"""
Layer ID: {layer_id}

Raw Grounding Data:
{json.dumps(raw_data, indent=2, default=str)}

Baseline Template (Rewrite these to flow better, keeping the exact meaning):
{json.dumps(base_template, indent=2, default=str)}

Return ONLY a JSON object matching the Output Schema.
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://agriwise.app", 
        "X-Title": "AgriWise Intelligence",
    }

    payload = {
        "model": DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3, # Low creativity for factual accuracy
        "max_tokens": 500,
        "response_format": {"type": "json_object"}
    }

    try:
        # 15-second timeout to allow fallbacks (Gemini/Gemma) enough time to complete
        timeout = aiohttp.ClientTimeout(total=15.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            content = None
            
            # Try OpenRouter first if circuit is not open
            if OPENROUTER_API_KEY and not _circuit_open():
                try:
                    async with session.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload) as response:
                        if response.status == 200:
                            resp_json = await response.json()
                            choices = resp_json.get("choices")
                            if choices:
                                content = (choices[0].get("message") or {}).get("content") or ""
                        else:
                            if response.status in (401, 402, 403, 429):
                                _trip_circuit(response.status)
                            logger.warning(f"OpenRouter API returned {response.status}.")
                except Exception as e:
                    logger.warning(f"OpenRouter network error: {e}")
            
            # Fallback Chain (Google GenAI)
            # Prioritizing Gemma models because they have a 1,500 RPD free tier limit,
            # whereas Gemini 2.5/3 Flash models are capped at 20 RPD.
            fallback_models = [
                "gemma-4-26b-a4b-it",     # 1500 RPD, faster open-weights
                "gemma-4-31b-it",         # 1500 RPD, large open-weights
                "gemini-3-flash-preview", # 20 RPD
                "gemini-2.5-pro",         # 20 RPD
                "gemini-2.5-flash",       # 20 RPD
            ]
            
            for model_name in fallback_models:
                if not content and not _gemini_circuit_open(model_name):
                    logger.warning(f"Falling back to {model_name} for {layer_id}.")
                    content = await _call_gemini_api(session, model_name, SYSTEM_PROMPT, prompt)

            if not content:
                logger.warning(f"All LLMs failed for {layer_id}. Falling back to template.")
                return base_template

            # Strip potential markdown formatting
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]

            if not content.strip():
                return base_template

            try:
                enhanced_data = json.loads(content)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse LLM JSON for {layer_id}: {content}")
                return base_template
            
            # Merge the enhanced strings back into the original dict, preserving confidence_level
            result = base_template.copy()
            for key in ["farmer_summary", "expert_summary", "why_it_matters", "confidence_reason"]:
                if key in enhanced_data and isinstance(enhanced_data[key], str) and enhanced_data[key].strip():
                    result[key] = enhanced_data[key].strip()
                    
            return result
                
    except asyncio.TimeoutError:
        logger.warning(f"LLM enhancement timed out for {layer_id}. Falling back to template.")
        return base_template
    except Exception as e:
        logger.warning(f"LLM enhancement failed for {layer_id}: {e}. Falling back to template.")
        return base_template
