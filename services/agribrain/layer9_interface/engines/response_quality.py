"""
Engine 14: Response Quality v9.6.1

Scores every response on groundedness, completeness, coherence, naturalness.
Naturalness uses a 5-signal heuristic scorer that can be calibrated against
human ratings when a feedback pipeline is available.
"""
import re
import logging
from typing import Dict, Any, List, Optional
from collections import Counter
from layer9_interface.schema import (
    Layer9Input, InterfaceOutput, ResponseQuality,
    PersonaConfig, ExpertiseLevel,
)

logger = logging.getLogger(__name__)

# Naturalness signal weights
_SIGNAL_WEIGHTS = {
    "length_adequacy": 0.20,
    "sentence_structure": 0.20,
    "repetition_penalty": 0.20,
    "vocabulary_diversity": 0.20,
    "persona_alignment": 0.20,
}


class ResponseQualityEngine:
    """Scores response quality for ML feedback loops."""

    def score(self, l9_input: Layer9Input, output: InterfaceOutput,
              hallucination_flags: int = 0,
              persona: Optional[PersonaConfig] = None) -> ResponseQuality:
        groundedness = self._groundedness(output, hallucination_flags)
        completeness = self._completeness(l9_input, output)
        coherence = self._coherence(output)
        naturalness = self._naturalness(output, persona)

        return ResponseQuality(
            groundedness_score=round(groundedness, 3),
            completeness_score=round(completeness, 3),
            coherence_score=round(coherence, 3),
            naturalness_score=round(naturalness, 3),
            hallucination_flags=hallucination_flags,
        )

    def _groundedness(self, output: InterfaceOutput, flags: int) -> float:
        # Perfect if no flags
        if flags == 0:
            return 1.0
        # Degrade based on flag count
        return max(0.0, 1.0 - (flags * 0.15))

    def _completeness(self, l9_input: Layer9Input, output: InterfaceOutput) -> float:
        total_items = 0
        referenced = 0

        # Check diagnoses referenced
        for d in l9_input.diagnoses:
            if isinstance(d, dict) and d.get("probability", 0) > 0.3:
                total_items += 1
                pid = d.get("problem_id", "")
                if any(pid in (e.evidence_id or "") for e in output.explanations):
                    referenced += 1

        # Check zones referenced
        if isinstance(l9_input.zone_plan, dict):
            for zid in l9_input.zone_plan:
                total_items += 1
                if any(zid == c.zone_id for c in output.zone_cards):
                    referenced += 1

        if total_items == 0:
            return 1.0
        return referenced / total_items

    def _coherence(self, output: InterfaceOutput) -> float:
        score = 1.0
        # Summary present
        if not output.summary:
            score -= 0.3
        # Citations present
        if not output.citations:
            score -= 0.2
        # Render hints valid
        if not output.render_hints:
            score -= 0.1
        return max(0.0, score)

    # ================================================================
    # Naturalness — 5-signal heuristic scorer
    # ================================================================

    def _naturalness(self, output: InterfaceOutput,
                     persona: Optional[PersonaConfig] = None) -> float:
        """
        Score naturalness on 5 linguistic signals [0,1].

        Signals:
          1. Length adequacy    — not too short, not too verbose
          2. Sentence structure — has natural sentence breaks
          3. Repetition penalty — penalizes repeated n-grams
          4. Vocabulary diversity — type-token ratio
          5. Persona alignment  — persona-level signals present
        """
        text = output.summary or ""
        # Also incorporate explanation text for richer signal
        for exp in output.explanations[:5]:
            text += " " + (exp.statement or "")
        text = text.strip()

        if not text:
            return 0.5  # neutral for empty output

        signals = {
            "length_adequacy": self._sig_length(text),
            "sentence_structure": self._sig_sentences(text),
            "repetition_penalty": self._sig_repetition(text),
            "vocabulary_diversity": self._sig_vocabulary(text),
            "persona_alignment": self._sig_persona(output, persona),
        }

        score = sum(signals[k] * _SIGNAL_WEIGHTS[k] for k in signals)
        return max(0.0, min(1.0, score))

    def _sig_length(self, text: str) -> float:
        """Optimal length: 30–1500 chars. Penalize extremes."""
        n = len(text)
        if n < 10:
            return 0.2
        if n < 30:
            return 0.5
        if n <= 1500:
            return 1.0
        if n <= 2500:
            return 0.7
        return 0.4  # extremely verbose

    def _sig_sentences(self, text: str) -> float:
        """Natural text has sentence endings (. ! ?)."""
        endings = len(re.findall(r'[.!?]', text))
        if endings == 0:
            return 0.3  # no sentence structure at all
        # 1–10 sentences is ideal
        if endings <= 10:
            return 1.0
        # More than 20 sentence breaks suggests fragmentation
        if endings <= 20:
            return 0.8
        return 0.6

    def _sig_repetition(self, text: str) -> float:
        """Penalize repeated 3-grams (sign of template stuttering)."""
        words = text.lower().split()
        if len(words) < 6:
            return 1.0  # too short to judge
        trigrams = [tuple(words[i:i+3]) for i in range(len(words) - 2)]
        counts = Counter(trigrams)
        if not counts:
            return 1.0
        max_repeat = max(counts.values())
        total = len(trigrams)
        repeat_ratio = (max_repeat - 1) / max(total, 1)
        # 0% repeat -> 1.0, 20%+ repeat -> 0.2
        return max(0.2, 1.0 - repeat_ratio * 4)

    def _sig_vocabulary(self, text: str) -> float:
        """Type-token ratio: unique words / total words."""
        words = re.findall(r'\w+', text.lower())
        if len(words) < 3:
            return 0.5
        ttr = len(set(words)) / len(words)
        # TTR > 0.5 is good for generated text
        if ttr >= 0.6:
            return 1.0
        if ttr >= 0.4:
            return 0.8
        if ttr >= 0.25:
            return 0.5
        return 0.3  # very repetitive vocabulary

    def _sig_persona(self, output: InterfaceOutput,
                     persona: Optional[PersonaConfig] = None) -> float:
        """Check that output matches the expected persona signals."""
        if persona is None:
            return 0.7  # neutral when persona unknown

        text = (output.summary or "") + " ".join(
            e.statement or "" for e in output.explanations[:3]
        )
        exp = persona.expertise_level

        if exp == ExpertiseLevel.NOVICE:
            # Expect warmer language, simpler words
            has_simple = bool(re.search(r'\b(your|you|we|let\'s|look|help)\b', text, re.I))
            return 1.0 if has_simple else 0.5

        if exp == ExpertiseLevel.RESEARCHER:
            # Expect data-dense language
            has_data = bool(re.search(r'\b(probability|severity|confidence|grade|%)\b', text, re.I))
            return 1.0 if has_data else 0.5

        if exp == ExpertiseLevel.AGRONOMIST:
            has_technical = bool(re.search(r'\b(detected|recommended|action|issue|zone)\b', text, re.I))
            return 1.0 if has_technical else 0.6

        # FARMER / TECHNICIAN — neutral-to-good for most outputs
        return 0.8


response_quality_engine = ResponseQualityEngine()
