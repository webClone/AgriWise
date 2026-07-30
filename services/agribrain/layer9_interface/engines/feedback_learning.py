"""
feedback_learning.py - Adaptive Learning from Farmer Interactions
===================================================================

Learns from farmer feedback to continuously improve response quality:
  1. Implicit feedback: follow-up questions → previous answer was incomplete
  2. Explicit feedback: thumbs up/down → direct quality signal
  3. Correction detection: "no, I meant..." → misunderstanding
  4. Engagement tracking: long conversations → interesting topic
  5. Re-ask detection: same question rephrased → first answer was bad

Uses these signals to:
  - Adjust prompt templates over time
  - Weight knowledge graph lookups vs LLM generation
  - Track per-intent quality scores
  - Generate improvement recommendations
"""

import os
import json
import time
import re
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict


@dataclass
class FeedbackSignal:
    """A feedback signal from farmer interaction."""
    signal_type: str       # "implicit_negative", "implicit_positive", "explicit_up", 
                           # "explicit_down", "correction", "re_ask", "engagement"
    intent: str
    query: str
    timestamp: float
    strength: float        # 0.0-1.0
    details: str = ""


@dataclass
class IntentQuality:
    """Tracked quality metrics per intent category."""
    intent: str
    total_queries: int = 0
    positive_signals: int = 0
    negative_signals: int = 0
    corrections: int = 0
    re_asks: int = 0
    avg_conversation_length: float = 1.0
    quality_score: float = 0.7  # Running average 0.0-1.0

    @property
    def satisfaction_rate(self) -> float:
        total = self.positive_signals + self.negative_signals
        if total == 0:
            return 0.5
        return self.positive_signals / total


class FeedbackLearningEngine:
    """Learns from farmer interactions to improve response quality."""

    DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "..", "data", "feedback_learning")

    # Patterns indicating the previous answer was inadequate
    NEGATIVE_PATTERNS = [
        r"^no[,.]",
        r"that's not what i (meant|asked)",
        r"i (already )?know that",
        r"more specific",
        r"you didn't answer",
        r"what i (really )?mean",
        r"be more (clear|precise|specific|helpful)",
        r"that doesn't help",
        r"wrong",
        r"incorrect",
    ]

    # Patterns indicating the previous answer was good
    POSITIVE_PATTERNS = [
        r"^(thanks|thank you|merci|شكرا)",
        r"^(great|good|perfect|excellent|helpful)",
        r"that (makes sense|helps|is clear)",
        r"^(ok|okay|got it|understood)",
        r"now (what|how|when)",  # Moved to next topic = satisfied
    ]

    # Patterns indicating correction
    CORRECTION_PATTERNS = [
        r"no[,.]?\s*(i mean|i meant|what i|actually)",
        r"not .+[,.]?\s*(but|rather|instead)",
        r"i said .+ not .+",
        r"i was asking about .+",
    ]

    def __init__(self):
        os.makedirs(self.DATA_DIR, exist_ok=True)
        self._intent_quality: Dict[str, IntentQuality] = {}
        self._signals: List[FeedbackSignal] = []
        self._recent_queries: List[str] = []  # For re-ask detection
        self._lock = __import__('threading').Lock()  # GAP-3 fix: thread safety for file writes
        self._load_state()

    def _state_path(self) -> str:
        return os.path.join(self.DATA_DIR, "feedback_state.json")

    def _load_state(self):
        path = self._state_path()
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for iq_data in data.get("intent_quality", []):
                    iq = IntentQuality(**iq_data)
                    self._intent_quality[iq.intent] = iq
            except Exception:
                pass

    def _save_state(self):
        """BUG-7 fix: Persist quality with explicit field serialization (not asdict which drops @property)."""
        path = self._state_path()
        try:
            with self._lock:
                data = {
                    "intent_quality": [
                        {
                            "intent": iq.intent,
                            "total_queries": iq.total_queries,
                            "positive_signals": iq.positive_signals,
                            "negative_signals": iq.negative_signals,
                            "corrections": iq.corrections,
                            "re_asks": iq.re_asks,
                            "avg_conversation_length": iq.avg_conversation_length,
                            "quality_score": iq.quality_score,
                        }
                        for iq in self._intent_quality.values()
                    ],
                    "signal_count": len(self._signals),
                    "last_updated": time.time(),
                }
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
        except Exception:
            pass

    def analyze_turn(self, query: str, intent: str,
                     response: str, history: Optional[List[Dict]] = None) -> List[FeedbackSignal]:
        """Analyze a conversation turn for feedback signals.
        
        Should be called AFTER each query-response pair.
        """
        signals = []
        ql = query.lower().strip()
        now = time.time()

        # Check for re-ask (similar to recent query)
        if self._is_reask(ql):
            signals.append(FeedbackSignal(
                signal_type="re_ask", intent=intent, query=query,
                timestamp=now, strength=0.8,
                details="Farmer rephrased a recent question — previous answer likely inadequate"
            ))

        # Check for correction patterns
        for pattern in self.CORRECTION_PATTERNS:
            if re.search(pattern, ql, re.IGNORECASE):
                signals.append(FeedbackSignal(
                    signal_type="correction", intent=intent, query=query,
                    timestamp=now, strength=0.9,
                    details=f"Correction detected: {query[:100]}"
                ))
                break

        # Check for negative feedback
        for pattern in self.NEGATIVE_PATTERNS:
            if re.search(pattern, ql, re.IGNORECASE):
                signals.append(FeedbackSignal(
                    signal_type="implicit_negative", intent=intent, query=query,
                    timestamp=now, strength=0.7,
                    details=f"Negative signal: {query[:100]}"
                ))
                break

        # Check for positive feedback
        for pattern in self.POSITIVE_PATTERNS:
            if re.search(pattern, ql, re.IGNORECASE):
                signals.append(FeedbackSignal(
                    signal_type="implicit_positive", intent=intent, query=query,
                    timestamp=now, strength=0.6,
                    details=f"Positive signal: {query[:100]}"
                ))
                break

        # Track conversation engagement
        if history and len(history) > 6:
            signals.append(FeedbackSignal(
                signal_type="engagement", intent=intent, query=query,
                timestamp=now, strength=0.5,
                details=f"Long conversation ({len(history)} turns) — farmer is engaged"
            ))

        # Update intent quality metrics
        self._update_quality(intent, signals)

        # Track for re-ask detection
        self._recent_queries.append(ql)
        self._recent_queries = self._recent_queries[-20:]

        self._signals.extend(signals)
        self._save_state()

        return signals

    def _is_reask(self, query_lower: str) -> bool:
        """Check if this query is a rephrased version of a recent query."""
        if not self._recent_queries:
            return False

        query_words = set(re.findall(r'\b\w{3,}\b', query_lower))
        if not query_words:
            return False

        for recent in self._recent_queries[-5:]:
            recent_words = set(re.findall(r'\b\w{3,}\b', recent))
            if not recent_words:
                continue
            overlap = len(query_words & recent_words) / max(len(query_words), 1)
            if overlap > 0.6 and query_lower != recent:
                return True

        return False

    def _update_quality(self, intent: str, signals: List[FeedbackSignal]):
        """Update quality metrics for an intent based on signals."""
        if intent not in self._intent_quality:
            self._intent_quality[intent] = IntentQuality(intent=intent)

        iq = self._intent_quality[intent]
        iq.total_queries += 1

        for signal in signals:
            if signal.signal_type in ("implicit_positive", "explicit_up"):
                iq.positive_signals += 1
            elif signal.signal_type in ("implicit_negative", "explicit_down"):
                iq.negative_signals += 1
            elif signal.signal_type == "correction":
                iq.corrections += 1
            elif signal.signal_type == "re_ask":
                iq.re_asks += 1

        # Update running quality score
        sat = iq.satisfaction_rate
        correction_penalty = min(0.3, iq.corrections / max(iq.total_queries, 1))
        reask_penalty = min(0.2, iq.re_asks / max(iq.total_queries, 1))
        iq.quality_score = max(0.0, sat - correction_penalty - reask_penalty)

    def explicit_feedback(self, intent: str, query: str, is_positive: bool):
        """Record explicit thumbs up/down feedback from UI."""
        now = time.time()
        signal_type = "explicit_up" if is_positive else "explicit_down"
        signal = FeedbackSignal(
            signal_type=signal_type, intent=intent, query=query,
            timestamp=now, strength=1.0
        )
        self._signals.append(signal)
        self._update_quality(intent, [signal])
        self._save_state()

    def get_quality_report(self) -> Dict[str, Any]:
        """Generate a quality report across all intents."""
        report = {
            "total_signals": len(self._signals),
            "intents": {},
        }
        for intent, iq in self._intent_quality.items():
            report["intents"][intent] = {
                "total_queries": iq.total_queries,
                "quality_score": round(iq.quality_score, 3),
                "satisfaction_rate": round(iq.satisfaction_rate, 3),
                "corrections": iq.corrections,
                "re_asks": iq.re_asks,
            }

        # Overall quality
        if self._intent_quality:
            scores = [iq.quality_score for iq in self._intent_quality.values()]
            report["overall_quality"] = round(sum(scores) / len(scores), 3)
        else:
            report["overall_quality"] = 0.5

        return report

    def get_prompt_adjustments(self, intent: str) -> Dict[str, Any]:
        """Get prompt adjustments based on learned quality for this intent.
        
        Returns adjustments that can modify prompt generation behavior.
        """
        iq = self._intent_quality.get(intent)
        if not iq or iq.total_queries < 5:
            return {}  # Not enough data

        adjustments = {}

        # If many corrections → add more examples
        if iq.corrections / max(iq.total_queries, 1) > 0.2:
            adjustments["add_examples"] = True
            adjustments["emphasize_clarity"] = True

        # If many re-asks → responses are too vague
        if iq.re_asks / max(iq.total_queries, 1) > 0.15:
            adjustments["increase_specificity"] = True
            adjustments["add_numbers"] = True

        # If low satisfaction → use CoT for this intent
        if iq.quality_score < 0.5:
            adjustments["force_cot"] = True

        # If high satisfaction → can use direct prompting
        if iq.quality_score > 0.8:
            adjustments["allow_direct"] = True

        return adjustments


# Singleton
_engine = None

def get_feedback_engine() -> FeedbackLearningEngine:
    global _engine
    if _engine is None:
        _engine = FeedbackLearningEngine()
    return _engine
