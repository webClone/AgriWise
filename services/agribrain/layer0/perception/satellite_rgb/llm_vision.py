"""
LLM Vision Engine — Semantic crop analysis via Gemini Flash Vision.

Takes an RGB satellite tile (PNG bytes) and produces a structured
agronomic interpretation using Gemini's multimodal capabilities.

This runs as a parallel inference path alongside the traditional CV
pipeline in SatelliteRGBInference. Results are merged (weighted)
to produce a more accurate classification, especially for borderline
cases where statistical thresholding alone misclassifies early emergence
as bare soil.

Circuit breaker: if the API fails, the engine silently returns None
and the traditional CV path continues unaffected.
"""

import os
import json
import time
import base64
import logging
import requests
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

GEMINI_VISION_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# Circuit breaker state
_CIRCUIT_TRIPPED_AT: Optional[float] = None
_CIRCUIT_RESET_AFTER = 300.0  # 5 minutes


@dataclass
class LLMVisionResult:
    """Structured output from LLM vision analysis of a satellite RGB tile."""
    crop_rows_detected: bool = False
    estimated_crop_type: str = "unknown"
    vegetation_pct: float = 0.0        # 0–100
    bare_soil_pct: float = 100.0       # 0–100
    emergence_stage: str = "unknown"   # bare_soil, early_emergence, vegetative, reproductive, senescence
    weed_pressure: str = "none"        # none, low, moderate, high
    confidence: float = 0.0            # 0–1
    raw_explanation: str = ""
    field_uniformity: str = "unknown"  # uniform, patchy, heterogeneous
    irrigation_visible: bool = False


def _circuit_open() -> bool:
    global _CIRCUIT_TRIPPED_AT
    if _CIRCUIT_TRIPPED_AT is None:
        return False
    if time.time() - _CIRCUIT_TRIPPED_AT > _CIRCUIT_RESET_AFTER:
        _CIRCUIT_TRIPPED_AT = None
        return False
    return True


def _trip_circuit(reason: str) -> None:
    global _CIRCUIT_TRIPPED_AT
    _CIRCUIT_TRIPPED_AT = time.time()
    logger.warning(f"[LLM_VISION] Circuit breaker tripped: {reason}. Disabled for {int(_CIRCUIT_RESET_AFTER/60)} min.")


VISION_PROMPT = """You are AgriBrain, an expert agronomist analyzing a satellite RGB image of an agricultural field.

Analyze this image carefully and provide a structured assessment.

IMPORTANT RULES:
- Look for crop ROWS (linear patterns of vegetation)
- Distinguish between: real crops, weeds, and bare soil
- Green patches on brown soil = early emergence, NOT bare soil
- Consider field uniformity: are green areas contiguous or patchy?
- Estimate percentages based on visual area coverage

Respond ONLY with a JSON object (no markdown, no explanation outside JSON):
{
  "crop_rows_detected": true/false,
  "estimated_crop_type": "wheat" | "barley" | "corn" | "legume" | "vegetable" | "orchard" | "unknown",
  "vegetation_pct": 0-100,
  "bare_soil_pct": 0-100,
  "emergence_stage": "bare_soil" | "early_emergence" | "vegetative" | "reproductive" | "senescence",
  "weed_pressure": "none" | "low" | "moderate" | "high",
  "confidence": 0.0-1.0,
  "field_uniformity": "uniform" | "patchy" | "heterogeneous",
  "irrigation_visible": true/false,
  "explanation": "Brief 1-2 sentence agronomic assessment"
}"""


def analyze_tile(image_bytes: bytes, plot_context: Optional[Dict] = None) -> Optional[LLMVisionResult]:
    """
    Analyze a satellite RGB tile using Gemini Vision.

    Args:
        image_bytes: PNG image bytes of the satellite tile
        plot_context: Optional dict with {"crop_type", "ndvi_mean", "region"} for grounding

    Returns:
        LLMVisionResult or None on failure
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("[LLM_VISION] No GEMINI_API_KEY in environment, skipping vision analysis")
        return None

    if _circuit_open():
        return None

    if not image_bytes or len(image_bytes) < 100:
        logger.debug("[LLM_VISION] Image too small, skipping")
        return None

    # Encode image to base64
    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    # Build context-enhanced prompt
    prompt = VISION_PROMPT
    if plot_context:
        context_str = "\n\nAdditional context about this field:\n"
        if plot_context.get("crop_type"):
            context_str += f"- Expected crop: {plot_context['crop_type']}\n"
        if plot_context.get("ndvi_mean") is not None:
            context_str += f"- Current NDVI mean: {plot_context['ndvi_mean']:.3f}\n"
        if plot_context.get("region"):
            context_str += f"- Region: {plot_context['region']}\n"
        prompt += context_str

    # Try multiple models — ordered by reliability for structured JSON output
    MODELS = [
        "gemini-3-flash-preview", # Gemini 3 — has separate quota, supports JSON mode
        "gemini-2.0-flash",
        "gemini-2.5-flash",
        "gemma-4-26b-a4b-it",    # Gemma 4 26B — no JSON mode, needs post-processing
        "gemini-2.0-flash-lite",
    ]

    resp = None
    for model in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        print(f"[LLM_VISION] Trying {model} with {len(image_bytes)} byte image...")

        # Gemma doesn't support responseMimeType, only use JSON mode for Gemini
        gen_config = {"temperature": 0.2, "maxOutputTokens": 1024}
        if model.startswith("gemini-"):
            gen_config["responseMimeType"] = "application/json"

        model_payload = {
            "contents": [{"parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/png", "data": b64_image}}
            ]}],
            "generationConfig": gen_config,
        }

        try:
            resp = requests.post(url, json=model_payload, timeout=30)
        except requests.Timeout:
            print(f"[LLM_VISION] {model} timed out, trying next...")
            continue
        except Exception as e:
            print(f"[LLM_VISION] {model} request error: {e}")
            continue

        if resp.status_code == 200:
            print(f"[LLM_VISION] {model} succeeded!")
            break
        elif resp.status_code == 429:
            print(f"[LLM_VISION] {model} rate limited (429), trying next...")
            continue
        elif resp.status_code in (401, 403):
            _trip_circuit(f"HTTP {resp.status_code} auth error")
            print(f"[LLM_VISION] Auth error: {resp.text[:200]}")
            return None
        elif resp.status_code == 404:
            print(f"[LLM_VISION] {model} not found (404), trying next...")
            continue
        else:
            print(f"[LLM_VISION] {model} returned {resp.status_code}: {resp.text[:200]}")
            continue

    if resp is None or resp.status_code != 200:
        error_msg = resp.text[:200] if resp else "All models failed"
        print(f"[LLM_VISION] All models exhausted. Last error: {error_msg}")
        _trip_circuit("All models rate-limited")
        return None

    # --- Parse response ---
    try:
        resp_json = resp.json()

        # Extract text from response
        candidates = resp_json.get("candidates", [])
        if not candidates:
            print("[LLM_VISION] No candidates in response")
            return None

        content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        if not content:
            print("[LLM_VISION] Empty content in response")
            return None

        # Parse JSON (strip markdown if present, extract from verbose output)
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # Try direct JSON parse first
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Try to fix truncated JSON by closing it
            import re
            # Attempt: close the JSON object if truncated
            for suffix in ["}", '"}', '"}']:
                try:
                    data = json.loads(content + suffix)
                    print("[LLM_VISION] Fixed truncated JSON")
                    break
                except json.JSONDecodeError:
                    continue
            else:
                # Fallback: extract JSON from verbose text (Gemma wraps JSON in explanation)
                match = re.search(r'\{[^{}]*"crop_rows_detected"[^{}]*\}', content, re.DOTALL)
                if not match:
                    match = re.search(r'\{[^{}]*"vegetation_pct"[^{}]*\}', content, re.DOTALL)
                if match:
                    print("[LLM_VISION] Extracted JSON from verbose output")
                    data = json.loads(match.group())
                else:
                    raise json.JSONDecodeError("No JSON found in response", content[:200], 0)

        result = LLMVisionResult(
            crop_rows_detected=bool(data.get("crop_rows_detected", False)),
            estimated_crop_type=str(data.get("estimated_crop_type", "unknown")),
            vegetation_pct=float(data.get("vegetation_pct", 0)),
            bare_soil_pct=float(data.get("bare_soil_pct", 100)),
            emergence_stage=str(data.get("emergence_stage", "unknown")),
            weed_pressure=str(data.get("weed_pressure", "none")),
            confidence=min(1.0, max(0.0, float(data.get("confidence", 0)))),
            raw_explanation=str(data.get("explanation", "")),
            field_uniformity=str(data.get("field_uniformity", "unknown")),
            irrigation_visible=bool(data.get("irrigation_visible", False)),
        )

        print(
            f"[LLM_VISION] OK - Analysis complete: veg={result.vegetation_pct:.0f}%, "
            f"soil={result.bare_soil_pct:.0f}%, stage={result.emergence_stage}, "
            f"rows={result.crop_rows_detected}, conf={result.confidence:.2f}"
        )

        return result

    except json.JSONDecodeError as e:
        print(f"[LLM_VISION] JSON parse error: {e}. Raw: {content[:200] if content else 'empty'}")
        return None
    except Exception as e:
        print(f"[LLM_VISION] Parse error: {e}")
        return None

