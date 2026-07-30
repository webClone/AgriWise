import os
import json
import logging
import asyncio
import aiohttp
import time
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DEFAULT_MODEL = "llama-3.3-70b-versatile"

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
_local_sems = {}

def _get_local_sem() -> asyncio.Semaphore:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.Semaphore(1)
    
    loop_id = id(loop)
    if loop_id not in _local_sems:
        _local_sems[loop_id] = asyncio.Semaphore(1)
    return _local_sems[loop_id]

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

# Circuit breaker for local LLM
_LOCAL_CIRCUIT_TRIPPED_AT: Optional[float] = None
_LOCAL_CIRCUIT_RESET_AFTER = 300.0  # 5 minutes

def _local_circuit_open() -> bool:
    global _LOCAL_CIRCUIT_TRIPPED_AT
    if _LOCAL_CIRCUIT_TRIPPED_AT is None:
        return False
    if time.time() - _LOCAL_CIRCUIT_TRIPPED_AT > _LOCAL_CIRCUIT_RESET_AFTER:
        _LOCAL_CIRCUIT_TRIPPED_AT = None  # Reset
        return False
    return True

def _trip_local_circuit(status_or_err: str) -> None:
    global _LOCAL_CIRCUIT_TRIPPED_AT
    _LOCAL_CIRCUIT_TRIPPED_AT = time.time()
    logger.warning(f"[LLM] Local LLM circuit breaker tripped ({status_or_err}). Disabled for {int(_LOCAL_CIRCUIT_RESET_AFTER/60)} min.")

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
    use_local = os.environ.get("USE_LOCAL_LLM", "false").lower() == "true"
    if use_local:
        # Bypass sequential CPU-bound VLM queries in L10 to avoid timeouts/latencies
        return base_template
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

    use_local = os.environ.get("USE_LOCAL_LLM", "false").lower() == "true"
    local_url = os.environ.get("LOCAL_LLM_API_URL", "http://localhost:8080")

    try:
        # 15-second timeout to allow fallbacks for remote APIs, 15-second timeout for local VLM queue
        timeout_val = 15.0
        timeout = aiohttp.ClientTimeout(total=timeout_val)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            content = None
            
            # 0. Try Local VLM/LLM if enabled
            if use_local and not _local_circuit_open():
                try:
                    local_payload = {
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.2,
                        "response_format": {"type": "json_object"}
                    }
                    model_name = os.environ.get("LOCAL_VLM_MODEL", "gemma-4-4b")
                    local_payload["model"] = model_name

                    async with _get_local_sem():
                        # Re-evaluate circuit inside semaphore queue in case it tripped while we were waiting
                        if _local_circuit_open():
                            logger.info(f"Local LLM circuit is open, skipping queued request for {layer_id}.")
                        else:
                            async with session.post(f"{local_url}/v1/chat/completions", json=local_payload) as response:
                                if response.status == 200:
                                    resp_json = await response.json()
                                    choices = resp_json.get("choices")
                                    if choices:
                                        content = (choices[0].get("message") or {}).get("content") or ""
                                else:
                                    logger.warning(f"Local LLM server returned status code {response.status}")
                                    _trip_local_circuit(f"HTTP {response.status}")
                except Exception as e:
                    logger.warning(f"Local LLM query failed: {e}")
                    _trip_local_circuit(str(e))

            # 1. Try Groq first (fastest)
            if not content and GROQ_API_KEY and not use_local and not _circuit_open():
                groq_headers = {
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                }
                groq_payload = payload.copy()
                groq_payload["model"] = "llama-3.3-70b-versatile"
                
                try:
                    async with session.post("https://api.groq.com/openai/v1/chat/completions", headers=groq_headers, json=groq_payload) as response:
                        if response.status == 200:
                            resp_json = await response.json()
                            choices = resp_json.get("choices")
                            if choices:
                                content = (choices[0].get("message") or {}).get("content") or ""
                        else:
                            if response.status in (401, 402, 403, 429):
                                _trip_circuit(response.status)
                            logger.warning(f"Groq API returned {response.status}.")
                except Exception as e:
                    logger.warning(f"Groq network error: {e}")

            # 2. Try OpenRouter if Groq failed or is not configured
            if not content and OPENROUTER_API_KEY and not use_local and not _circuit_open():
                try:
                    openrouter_payload = payload.copy()
                    openrouter_payload["model"] = "meta-llama/llama-3.3-70b-instruct:free"
                    async with session.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=openrouter_payload) as response:
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
                if not content and not use_local and not _gemini_circuit_open(model_name):
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
