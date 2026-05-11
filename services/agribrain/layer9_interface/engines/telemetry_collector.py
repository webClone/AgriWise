"""
Engine 15: Telemetry Collector v9.6.1

Extracts ML-ready feature vectors from every L9 invocation.
Emits telemetry to daily-rotated JSONL files for production analytics.
"""
import json
import os
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional
from layer9_interface.schema import (
    Layer9Input, IntentClassification, ResponseQuality,
    TelemetryVector, UserIntent, ExpertiseLevel,
)

logger = logging.getLogger(__name__)

_TELEMETRY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "config", "telemetry",
)


class TelemetryCollectorEngine:
    """Collects ML-ready feature vectors and emits to JSONL files."""

    def __init__(self):
        self._lock = threading.Lock()
        self._current_date: str = ""
        self._current_file = None
        self._emit_enabled = True

    def collect(
        self,
        l9_input: Layer9Input,
        classification: Optional[IntentClassification] = None,
        quality: Optional[ResponseQuality] = None,
        engine_latencies: Optional[Dict[str, float]] = None,
    ) -> TelemetryVector:
        intent_dist: Dict[str, float] = {}
        if classification:
            intent_dist[classification.primary_intent.value] = classification.confidence
            intent_dist[classification.fallback_intent.value] = 1.0 - classification.confidence

        grade_map = {"A": 1.0, "B": 0.8, "C": 0.6, "D": 0.3, "F": 0.1}
        dq_features = {
            "audit_grade_score": grade_map.get(l9_input.audit_grade.upper(), 0.5),
            "n_conflicts": float(len(l9_input.conflicts)),
            "n_diagnoses": float(len(l9_input.diagnoses)),
            "n_actions": float(len(l9_input.actions)),
            "n_zones": float(len(l9_input.zone_plan) if isinstance(l9_input.zone_plan, dict) else 0),
        }

        resp_features: Dict[str, float] = {}
        if quality:
            resp_features = {
                "groundedness": quality.groundedness_score,
                "completeness": quality.completeness_score,
                "coherence": quality.coherence_score,
                "naturalness": quality.naturalness_score,
                "hallucination_flags": float(quality.hallucination_flags),
            }

        exp_signals: Dict[str, float] = {}
        if classification:
            exp_signals = {
                "detected_level": float(
                    list(ExpertiseLevel).index(classification.detected_expertise)
                ),
                "intent_confidence": classification.confidence,
            }

        return TelemetryVector(
            intent_distribution=intent_dist,
            data_quality_features=dq_features,
            response_features=resp_features,
            expertise_signals=exp_signals,
            engine_latencies=engine_latencies or {},
        )

    def emit(self, vector: TelemetryVector, session_id: str = "") -> bool:
        """Persist a telemetry vector to a daily-rotated JSONL file.

        Thread-safe. Returns True on success, False on failure (never raises).
        """
        if not self._emit_enabled:
            return False

        try:
            record = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "session_id": session_id,
                "intent_distribution": vector.intent_distribution,
                "data_quality_features": vector.data_quality_features,
                "response_features": vector.response_features,
                "expertise_signals": vector.expertise_signals,
                "engine_latencies": vector.engine_latencies,
                "experiment_id": vector.experiment_id,
                "variant": vector.variant,
            }

            today = datetime.utcnow().strftime("%Y-%m-%d")

            with self._lock:
                if today != self._current_date or self._current_file is None:
                    self._rotate(today)

                line = json.dumps(record, separators=(",", ":")) + "\n"
                self._current_file.write(line)
                self._current_file.flush()

            return True

        except Exception as e:
            logger.error("Telemetry emit failed: %s", e)
            return False

    def _rotate(self, today: str):
        """Open a new daily JSONL file. Must be called under self._lock."""
        if self._current_file is not None:
            try:
                self._current_file.close()
            except Exception:
                pass

        os.makedirs(_TELEMETRY_DIR, exist_ok=True)
        filepath = os.path.join(_TELEMETRY_DIR, f"l9_telemetry_{today}.jsonl")
        self._current_file = open(filepath, "a", encoding="utf-8")
        self._current_date = today
        logger.info("Telemetry rotating to %s", filepath)

    def close(self):
        """Flush and close the current file (for graceful shutdown)."""
        with self._lock:
            if self._current_file is not None:
                try:
                    self._current_file.flush()
                    self._current_file.close()
                except Exception:
                    pass
                self._current_file = None


telemetry_collector = TelemetryCollectorEngine()
