"""
response_ranker.py - Response Quality Scoring & Auto-Retry
===========================================================

Lightweight post-processor that scores LLM output quality:
  1. Hallucination detection (check if cited numbers exist in context)
  2. Completeness scoring (did it address all parts of the question?)
  3. Actionability scoring (does it contain concrete steps?)
  4. Auto-retry with modified prompt if score < threshold

Works with any LLM backend (local or cloud).
"""

import re
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class QualityScore:
    """Quality assessment of an LLM response."""
    hallucination_score: float = 1.0    # 0.0 = hallucinated, 1.0 = grounded
    completeness_score: float = 1.0     # 0.0 = incomplete, 1.0 = complete
    actionability_score: float = 1.0    # 0.0 = vague, 1.0 = actionable
    coherence_score: float = 1.0        # 0.0 = incoherent, 1.0 = coherent
    overall: float = 1.0               # Weighted average
    issues: List[str] = field(default_factory=list)
    should_retry: bool = False

    def compute_overall(self, weights: Optional[Dict[str, float]] = None):
        """Compute weighted overall score."""
        w = weights or {
            "hallucination": 0.40,  # Heaviest — wrong info is worse than incomplete
            "completeness": 0.25,
            "actionability": 0.20,
            "coherence": 0.15,
        }
        self.overall = (
            self.hallucination_score * w["hallucination"] +
            self.completeness_score * w["completeness"] +
            self.actionability_score * w["actionability"] +
            self.coherence_score * w["coherence"]
        )
        self.should_retry = self.overall < 0.5


class ResponseRanker:
    """Scores and validates LLM responses before they reach the user."""

    # Numbers that could appear in field context
    CONTEXT_NUMBERS_PATTERN = re.compile(r'(\d+\.?\d*)\s*(%|mm|kg|ha|degrees?|[°]C|dS/m|kPa|m/s|km/h)')

    def __init__(self, retry_threshold: float = 0.5, max_retries: int = 2):
        self.retry_threshold = retry_threshold
        self.max_retries = max_retries

    def extract_numbers_from_text(self, text: str) -> List[Tuple[float, str]]:
        """Extract all number+unit pairs from text."""
        matches = self.CONTEXT_NUMBERS_PATTERN.findall(text)
        result = []
        for num_str, unit in matches:
            try:
                result.append((float(num_str), unit))
            except ValueError:
                pass
        return result

    def check_hallucination(self, response: str, context: str) -> Tuple[float, List[str]]:
        """Check if numbers in the response exist in the context.
        
        Returns:
            (score, issues): Score 0.0-1.0, list of hallucinated claims
        """
        issues = []
        response_numbers = self.extract_numbers_from_text(response)
        context_numbers = self.extract_numbers_from_text(context)

        if not response_numbers:
            return 1.0, []  # No numbers cited = no hallucination risk

        context_values = {n[0] for n in context_numbers}

        # Allow common agronomic constants that don't need context
        KNOWN_CONSTANTS = {
            0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20, 25, 30, 50, 100,
            # Common thresholds
            4.5, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0,  # pH values
            0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9,  # NDVI ranges
        }

        hallucinated = 0
        total_checked = 0

        for num, unit in response_numbers:
            # Skip common constants
            if num in KNOWN_CONSTANTS:
                continue

            total_checked += 1

            # Check if number (or close approximation) exists in context
            found = False
            for ctx_num in context_values:
                if abs(num - ctx_num) < 0.5:  # Allow small rounding
                    found = True
                    break

            if not found:
                hallucinated += 1
                issues.append(f"Number {num}{unit} not found in context")

        if total_checked == 0:
            return 1.0, []

        score = 1.0 - (hallucinated / total_checked)
        return max(0.0, score), issues

    def check_completeness(self, response: str, query: str) -> Tuple[float, List[str]]:
        """Check if the response addresses the question."""
        issues = []

        # Check for empty or very short responses
        if len(response.strip()) < 30:
            issues.append("Response too short")
            return 0.2, issues

        # Check if it's an error message
        if response.startswith("[ERROR]") or response.startswith("[EXCEPTION]"):
            issues.append("Response is an error")
            return 0.0, issues

        # Extract question keywords
        query_lower = query.lower()
        q_keywords = set(re.findall(r'\b\w{4,}\b', query_lower))
        r_lower = response.lower()

        # Check keyword overlap
        if q_keywords:
            overlap = sum(1 for k in q_keywords if k in r_lower)
            ratio = overlap / len(q_keywords)
            if ratio < 0.2:
                issues.append("Response doesn't address the question keywords")
                return 0.3, issues

        # Check for deflection patterns
        deflection_patterns = [
            "i cannot", "i'm unable", "i don't have", "outside my scope",
            "i'm not sure", "i can't determine"
        ]
        deflection_count = sum(1 for p in deflection_patterns if p in r_lower)
        if deflection_count > 2:
            issues.append("Excessive deflection")
            return 0.4, issues

        return 1.0, issues

    def check_actionability(self, response: str, intent: str) -> Tuple[float, List[str]]:
        """Check if the response contains actionable recommendations."""
        issues = []
        r_lower = response.lower()

        # Only check actionability for action-oriented intents
        if intent not in ("DECISION", "NUTRIENT", "PLANNING", "DIAGNOSIS"):
            return 1.0, []

        action_verbs = [
            "apply", "irrigate", "spray", "check", "monitor", "reduce",
            "increase", "adjust", "consider", "schedule", "test", "measure",
            "scout", "wait", "avoid", "ensure", "recommend", "use"
        ]

        action_count = sum(1 for v in action_verbs if v in r_lower)

        if action_count == 0:
            issues.append("No actionable recommendations found")
            return 0.3, issues
        elif action_count == 1:
            return 0.6, []
        else:
            return 1.0, []

    def check_coherence(self, response: str) -> Tuple[float, List[str]]:
        """Check basic coherence of the response."""
        issues = []

        # Check for repetition (same sentence appearing multiple times)
        sentences = re.split(r'[.!?]+', response)
        sentences = [s.strip().lower() for s in sentences if len(s.strip()) > 20]
        if sentences:
            unique = set(sentences)
            if len(unique) < len(sentences) * 0.7:
                issues.append("Excessive repetition detected")
                return 0.4, issues

        # Check for truncated responses
        if response.rstrip()[-1:] not in '.!?")\n' and len(response) > 100:
            issues.append("Response appears truncated")
            return 0.6, issues

        # Check for random characters or encoding issues
        non_ascii = sum(1 for c in response if ord(c) > 127 and ord(c) < 256)
        if non_ascii > len(response) * 0.1:
            issues.append("Encoding issues detected")
            return 0.5, issues

        return 1.0, issues

    def score(self, response: str, context: str, query: str,
              intent: str = "GENERAL") -> QualityScore:
        """Score a response across all dimensions.
        
        Args:
            response: The LLM's response text
            context: The field context provided to the LLM
            query: The original user query
            intent: The detected intent category
            
        Returns:
            QualityScore with per-dimension scores and overall
        """
        qs = QualityScore()

        h_score, h_issues = self.check_hallucination(response, context)
        qs.hallucination_score = h_score
        qs.issues.extend(h_issues)

        c_score, c_issues = self.check_completeness(response, query)
        qs.completeness_score = c_score
        qs.issues.extend(c_issues)

        a_score, a_issues = self.check_actionability(response, intent)
        qs.actionability_score = a_score
        qs.issues.extend(a_issues)

        co_score, co_issues = self.check_coherence(response)
        qs.coherence_score = co_score
        qs.issues.extend(co_issues)

        qs.compute_overall()
        return qs

    def run_self_correcting_loop(self, call_llm_fn, query: str, context_str: str,
                                 system_prompt: str, intent: str = "GENERAL") -> Tuple[str, QualityScore]:
        """
        Executes the self-correcting retry loop using feedback-driven prompting.
        """
        current_system_prompt = system_prompt
        retries = self.max_retries
        
        response = call_llm_fn(current_system_prompt, query)
        qs = self.score(response, context_str, query, intent)
        
        while qs.should_retry and retries > 0:
            issues_str = "\n".join(f"- {issue}" for issue in qs.issues)
            current_system_prompt = (
                f"{system_prompt}\n\n"
                f"[CRITICAL CORRECTIVE ACTION REQUIRED]\n"
                f"Your previous response draft failed the quality safety gate check with the following errors:\n"
                f"{issues_str}\n\n"
                f"REMEDY:\n"
                f"1. Ground all numbers strictly in context.\n"
                f"2. Ensure the response directly answers the user's keywords.\n"
                f"3. Eliminate repetition.\n"
                f"Please regenerate the response correcting these faults."
            )
            response = call_llm_fn(current_system_prompt, query)
            qs = self.score(response, context_str, query, intent)
            retries -= 1
            
        return response, qs


# Singleton
_ranker = None

def get_ranker() -> ResponseRanker:
    global _ranker
    if _ranker is None:
        _ranker = ResponseRanker()
    return _ranker


def score_response(response: str, context: str, query: str,
                   intent: str = "GENERAL") -> QualityScore:
    """One-call convenience function."""
    return get_ranker().score(response, context, query, intent)
