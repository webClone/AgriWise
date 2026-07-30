"""
query_decomposer.py - Complex Query Decomposition Engine
=========================================================

Breaks complex multi-part farmer questions into atomic sub-queries,
routes each to the appropriate engine, and fuses results.

Example:
  "What is the rain forecast, should I irrigate, and is there disease risk?"
  → Sub-query 1: "rain forecast" → DATA_QUERY → L1
  → Sub-query 2: "should I irrigate" → DECISION → L3
  → Sub-query 3: "disease risk" → DIAGNOSIS → L5
  → Fused response covering all three
"""

import re
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class SubQuery:
    """A decomposed sub-query with its classification."""
    text: str
    intent: str
    priority: int  # 1 = highest
    related_layers: List[str]
    answer: Optional[str] = None


class QueryDecomposer:
    """Decomposes complex queries into atomic sub-queries."""

    # Conjunction patterns for splitting
    SPLIT_PATTERNS = [
        r'\band\b(?:\s+also\b)?',
        r'\balso\b',
        r',\s*(?:and\s+)?',
        r'\?(?:\s+)',
        r'\bthen\b',
        r'\bplus\b',
        r'\bas well as\b',
    ]

    # Intent keyword mappings
    INTENT_KEYWORDS = {
        "DATA_QUERY": ["show", "how much", "how many", "history", "trend", "rain",
                       "temperature", "moisture", "what is the", "tell me"],
        "DECISION": ["should I", "do I need", "recommend", "when to", "is it time"],
        "DIAGNOSIS": ["risk", "problem", "disease", "pest", "stress", "health",
                      "status", "how is"],
        "NUTRIENT": ["nitrogen", "fertilizer", "nutrient", "NPK", "urea", "phosphorus"],
        "PLANNING": ["plant", "crop", "rotation", "season", "variety", "sow"],
        "SCENARIO": ["what if", "simulate", "forecast", "predict", "projection"],
        "GENERAL": ["what is", "explain", "define", "how does", "difference between"],
    }

    # Layer mappings per intent
    INTENT_LAYERS = {
        "DATA_QUERY": ["L1"],
        "DECISION": ["L3", "L6"],
        "DIAGNOSIS": ["L2", "L3", "L5"],
        "NUTRIENT": ["L4"],
        "PLANNING": ["L7", "L10"],
        "SCENARIO": ["L9"],
        "GENERAL": ["L9"],
    }

    def is_complex(self, query: str) -> bool:
        """Detect if a query has multiple parts that need decomposition."""
        q = query.strip()

        # Count question marks
        qmarks = q.count('?')
        if qmarks > 1:
            return True

        # Count conjunction patterns
        conj_count = sum(1 for p in self.SPLIT_PATTERNS
                        if re.search(p, q, re.IGNORECASE))
        if conj_count >= 2:
            return True

        # Count distinct intent keyword matches
        intents_found = set()
        ql = q.lower()
        for intent, keywords in self.INTENT_KEYWORDS.items():
            if any(k in ql for k in keywords):
                intents_found.add(intent)
        if len(intents_found) >= 2:
            return True

        return False

    def decompose(self, query: str) -> List[SubQuery]:
        """Split a complex query into atomic sub-queries."""
        if not self.is_complex(query):
            return [self._classify_single(query, priority=1)]

        # Try splitting by question marks first
        parts = re.split(r'\?\s*', query)
        parts = [p.strip() + '?' for p in parts if p.strip()]

        # If only one part, try splitting by conjunctions
        if len(parts) <= 1:
            combined_pattern = '|'.join(self.SPLIT_PATTERNS)
            parts = re.split(combined_pattern, query, flags=re.IGNORECASE)
            parts = [p.strip().rstrip(',').strip() for p in parts if len(p.strip()) > 5]

        # Classify each part
        sub_queries = []
        for i, part in enumerate(parts):
            sq = self._classify_single(part, priority=i + 1)
            sub_queries.append(sq)

        # De-duplicate by intent (keep first of each)
        seen_intents = set()
        unique = []
        for sq in sub_queries:
            if sq.intent not in seen_intents:
                seen_intents.add(sq.intent)
                unique.append(sq)

        return unique if unique else [self._classify_single(query, priority=1)]

    def _classify_single(self, text: str, priority: int) -> SubQuery:
        """Classify a single sub-query into an intent."""
        tl = text.lower()
        best_intent = "GENERAL"
        best_score = 0

        for intent, keywords in self.INTENT_KEYWORDS.items():
            score = sum(1 for k in keywords if k in tl)
            if score > best_score:
                best_score = score
                best_intent = intent

        layers = self.INTENT_LAYERS.get(best_intent, ["L9"])

        return SubQuery(
            text=text,
            intent=best_intent,
            priority=priority,
            related_layers=layers
        )

    def fuse_answers(self, sub_queries: List[SubQuery]) -> str:
        """Fuse multiple sub-query answers into a coherent response."""
        if not sub_queries:
            return ""

        if len(sub_queries) == 1:
            return sub_queries[0].answer or ""

        parts = []
        for i, sq in enumerate(sub_queries):
            if sq.answer:
                if len(sub_queries) > 2:
                    parts.append(f"**{sq.text.rstrip('?').strip()}:**\n{sq.answer}")
                else:
                    parts.append(sq.answer)

        return "\n\n---\n\n".join(parts)


# ============================================================================
# Singleton
# ============================================================================

_decomposer = None

def get_decomposer() -> QueryDecomposer:
    global _decomposer
    if _decomposer is None:
        _decomposer = QueryDecomposer()
    return _decomposer
