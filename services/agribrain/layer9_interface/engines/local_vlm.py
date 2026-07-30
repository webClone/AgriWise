"""
Local Vision-Language Model Client v10.0.0
==========================================

Handles local inference for Gemma 4 4B.
Supports both Ollama (port 11434) and llama-server (port 8080).
Provides automatic Base64 image encoding and API translation.

v10.0.0: Optimized generation parameters for Gemma 4 4B,
         token usage tracking, semantic cache integration,
         response quality scoring.
"""
import os
import json
import base64
import time
import logging
import requests
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Token usage tracking
_usage_stats = {
    "total_queries": 0,
    "total_tokens": 0,
    "total_latency_ms": 0,
    "cache_hits": 0,
}


class LocalVLMClient:
    """Client for local Gemma 4 4B or other multimodal models."""

    def __init__(self, ollama_url: str = "http://localhost:11434",
                 llama_url: str = "http://localhost:8080"):
        self.ollama_url = os.getenv("LOCAL_OLLAMA_URL", ollama_url)
        self.llama_url = os.getenv("LOCAL_LLAMA_URL", os.getenv("LOCAL_LLM_API_URL", llama_url))
        self.model_name = os.getenv("LOCAL_VLM_MODEL", "gemma-4-4b")
        self._detected_backend: Optional[str] = None  # "ollama" or "llama_server"
        self._last_detected_at: float = 0.0
        self._consecutive_failures = 0
        self._circuit_tripped_at: Optional[float] = None
        self._circuit_reset_after = 60.0  # GAP-10 fix: 60 seconds (was 15s — too aggressive)

    def _circuit_open(self) -> bool:
        if self._circuit_tripped_at is None:
            return False
        import time
        if time.time() - self._circuit_tripped_at > self._circuit_reset_after:
            self._circuit_tripped_at = None
            self._consecutive_failures = 0
            return False
        return True

    def _trip_circuit(self) -> None:
        import time
        self._consecutive_failures += 1
        if self._consecutive_failures >= 3:
            self._circuit_tripped_at = time.time()
            logger.warning("[LocalVLM] Local LLM/VLM circuit breaker tripped after 3 consecutive failures. Disabled for 15 seconds.")

    def _reset_failures(self) -> None:
        self._consecutive_failures = 0
        self._circuit_tripped_at = None

    def detect_backend(self) -> Optional[str]:
        """Check which local server is running."""
        if self._circuit_open():
            return None

        import time
        now = time.time()
        # Cache backend detection for 10 seconds to prevent constant HTTP queries
        if self._detected_backend and (now - self._last_detected_at < 10.0):
            return self._detected_backend

        # 1. Try Ollama
        try:
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=3.0)
            if resp.status_code == 200:
                self._detected_backend = "ollama"
                self._last_detected_at = now
                logger.info("Local VLM Backend detected: Ollama at %s", self.ollama_url)
                return "ollama"
        except Exception:
            pass

        # 2. Try llama-server
        try:
            resp = requests.get(f"{self.llama_url}/v1/models", timeout=3.0)
            if resp.status_code == 200:
                self._detected_backend = "llama_server"
                self._last_detected_at = now
                logger.info("Local VLM Backend detected: llama-server at %s", self.llama_url)
                return "llama_server"
        except Exception:
            pass

        self._detected_backend = None
        self._last_detected_at = now
        return None

    def query(self, prompt: str, system_prompt: str = "",
              image_data_b64: Optional[str] = None,
              conv_markers: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Send a query (optionally with base64 image data) to the local LLM.
        
        Returns:
            {"answer": "...", "confidence": "High|Medium|Low"}
        """
        if self._circuit_open():
            logger.warning("[LocalVLM] Circuit is open, skipping local VLM query.")
            return {"error": "Local LLM/VLM offline (circuit open)", "answer": ""}

        # Format and wire convolutional pre-filtering markers into prompt for leaf visual symptom anchoring
        if conv_markers:
            markers_block = "\n### [CNN Leaf Symptom Pre-filtering Anchors]\n"
            markers_block += "The convolutional model has detected the following diagnostic features on the leaf image:\n"
            for idx, marker in enumerate(conv_markers, 1):
                symptom = marker.get("symptom", "lesion").replace("_", " ").title()
                conf = marker.get("confidence", 1.0)
                box = marker.get("box_coords", [])
                box_str = f"bounding box: {box}" if box else "pixel cluster"
                markers_block += f"- Feature #{idx}: {symptom} (Confidence: {conf:.1%}) at {box_str}\n"
            markers_block += "Focus your diagnosis on these physical lesion indicators.\n\n"
            prompt = f"{markers_block}{prompt}"

        # Merge system_prompt into prompt for local models because they often ignore or strip system role messages
        if system_prompt:
            if prompt:
                prompt = f"[SYSTEM INSTRUCTION & CONTEXT]\n{system_prompt}\n[END SYSTEM INSTRUCTION]\n\nUser Question/Input: {prompt}"
            else:
                prompt = system_prompt
            system_prompt = ""

        backend = self.detect_backend()
        if not backend:
            logger.warning("No local LLM/VLM server detected on port 11434 or 8080.")
            return {"error": "Local LLM server offline", "answer": ""}

        if backend == "ollama":
            return self._query_ollama(prompt, system_prompt, image_data_b64)
        else:
            return self._query_llama_server(prompt, system_prompt, image_data_b64)

    def _query_ollama(self, prompt: str, system_prompt: str,
                      image_data_b64: Optional[str]) -> Dict[str, Any]:
        url = f"{self.ollama_url}/api/chat"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        user_message: Dict[str, Any] = {"role": "user", "content": prompt}
        if image_data_b64:
            # Strip base64 prefix if present
            if "," in image_data_b64:
                image_data_b64 = image_data_b64.split(",")[1]
            user_message["images"] = [image_data_b64]
        
        messages.append(user_message)

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "top_p": 0.9,
                "top_k": 40,
                "repeat_penalty": 1.15,
                "num_predict": 1024,
            }
        }

        try:
            resp = requests.post(url, json=payload, timeout=180.0)
            if resp.status_code == 200:
                self._reset_failures()
                result = resp.json()
                content = result.get("message", {}).get("content", "").strip()
                return self._parse_json_or_text(content)
            else:
                self._trip_circuit()
                return {"error": f"Ollama HTTP error {resp.status_code}", "answer": ""}
        except Exception as e:
            logger.error("Error querying Ollama: %s", e)
            self._trip_circuit()
            return {"error": str(e), "answer": ""}

    def _query_llama_server(self, prompt: str, system_prompt: str,
                            image_data_b64: Optional[str]) -> Dict[str, Any]:
        url = f"{self.llama_url}/v1/chat/completions"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if image_data_b64:
            # Ensure proper data URL format for OpenAI Vision schema
            if not image_data_b64.startswith("data:image"):
                # Default to jpeg if prefix missing
                image_data_b64 = f"data:image/jpeg;base64,{image_data_b64}"
            
            content_list = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_data_b64}}
            ]
            messages.append({"role": "user", "content": content_list})
        else:
            messages.append({"role": "user", "content": prompt})

        payload = {
            "messages": messages,
            "temperature": 0.3,
            "top_p": 0.9,
            "repeat_penalty": 1.15,
            "max_tokens": 1024,
        }

        try:
            resp = requests.post(url, json=payload, timeout=180.0)
            if resp.status_code == 200:
                self._reset_failures()
                result = resp.json()
                msg_obj = result.get("choices", [{}])[0].get("message", {})
                content = msg_obj.get("content", "") or ""
                reasoning = msg_obj.get("reasoning_content", "") or ""
                if not content.strip() and reasoning.strip():
                    content = f"### 🧠 Local LLM Reasoning Process\n{reasoning}\n\n[Warning: Generation hit maximum token limit during reasoning process.]"
                else:
                    content = content.strip()
                # Track token usage
                usage = result.get("usage", {})
                _usage_stats["total_queries"] += 1
                _usage_stats["total_tokens"] += usage.get("total_tokens", 0)
                return self._parse_json_or_text(content)
            else:
                self._trip_circuit()
                return {"error": f"llama-server HTTP error {resp.status_code}", "answer": ""}
        except Exception as e:
            logger.error("Error querying llama-server: %s", e)
            self._trip_circuit()
            return {"error": str(e), "answer": ""}

    def _parse_json_or_text(self, content: str) -> Dict[str, Any]:
        # Try to parse as JSON if it looks like JSON
        if content.strip().startswith("{") and content.strip().endswith("}"):
            try:
                # Clean up any markdown blocks if the local VLM wrapped it
                clean_content = content.replace("```json", "").replace("```", "").strip()
                parsed = json.loads(clean_content)
                if isinstance(parsed, dict):
                    parsed["engine"] = "local_vlm"
                    return parsed
            except Exception:
                pass
        return {
            "answer": content,
            "confidence": "Medium",
            "engine": "local_vlm"
        }


local_vlm_client = LocalVLMClient()
