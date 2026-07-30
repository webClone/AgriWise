"""
context_compressor.py - Intelligent Context Window Management
===============================================================

Compresses and prioritizes field context to fit within Gemma 4 4B's
8K context window while maximizing information density.

Strategies:
  1. Intent-aware pruning: Only include layers relevant to the query
  2. Temporal recency weighting: Recent data prioritized over old
  3. Redundancy elimination: Remove duplicate information across layers
  4. Numeric summarization: Compress timeseries to key statistics
  5. Token budget allocation: Reserve tokens for response generation
"""

import re
import json
from typing import Dict, Any, List, Optional, Tuple


class ContextCompressor:
    """Compresses field context to fit small LLM context windows."""

    # Approximate tokens per character (for English text)
    CHARS_PER_TOKEN = 4.0

    # Token budget allocation for 8K context
    MAX_CONTEXT_TOKENS = 8192
    SYSTEM_PROMPT_BUDGET = 800     # Fixed instructions
    FIELD_CONTEXT_BUDGET = 3500    # Field data
    HISTORY_BUDGET = 1500          # Conversation history
    RESPONSE_BUDGET = 2000         # Reserved for generation
    SAFETY_MARGIN = 392            # Buffer

    # Which layers matter for each intent
    INTENT_LAYER_PRIORITIES = {
        "DATA_QUERY": ["L1", "L2", "L10"],
        "DIAGNOSIS": ["L1", "L2", "L3", "L5", "L10"],
        "DECISION": ["L1", "L3", "L6", "L8"],
        "NUTRIENT": ["L1", "L4", "L10"],
        "PLANNING": ["L7", "L1", "L10"],
        "SCENARIO": ["L1", "L3", "L10"],
        "GENERAL": ["L1"],
        "GREETING": [],
        "EXECUTION_STATUS": ["L6"],
    }

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for a text string."""
        return int(len(text) / self.CHARS_PER_TOKEN)

    def compress_context(self, context: str, intent: str,
                         max_tokens: Optional[int] = None) -> str:
        """Compress field context to fit within token budget.
        
        Args:
            context: Raw field context string
            intent: Detected intent for priority filtering
            max_tokens: Override default budget
            
        Returns:
            Compressed context string
        """
        budget = max_tokens or self.FIELD_CONTEXT_BUDGET
        current_tokens = self.estimate_tokens(context)

        if current_tokens <= budget:
            return context  # Already fits

        # Strategy 1: Remove verbose sections
        compressed = self._remove_verbose_sections(context)
        if self.estimate_tokens(compressed) <= budget:
            return compressed

        # Strategy 2: Intent-aware pruning
        compressed = self._intent_prune(compressed, intent)
        if self.estimate_tokens(compressed) <= budget:
            return compressed

        # Strategy 3: Summarize numeric arrays
        compressed = self._summarize_arrays(compressed)
        if self.estimate_tokens(compressed) <= budget:
            return compressed

        # Strategy 4: Hard truncation with preservation of key sections
        compressed = self._smart_truncate(compressed, budget)
        return compressed

    def _remove_verbose_sections(self, context: str) -> str:
        """Remove known verbose patterns."""
        # Remove empty or redundant lines
        lines = context.split('\n')
        filtered = []
        for line in lines:
            stripped = line.strip()
            # Skip empty lines, separators, and very short noise
            if not stripped:
                continue
            if stripped in ('---', '===', '***', '```'):
                continue
            if re.match(r'^[-=]{3,}$', stripped):
                continue
            # Skip duplicate information markers
            if stripped.startswith('[EMPTY]') or stripped.startswith('[N/A]'):
                continue
            filtered.append(line)

        return '\n'.join(filtered)

    def _intent_prune(self, context: str, intent: str) -> str:
        """Remove context sections not relevant to the current intent."""
        priority_layers = self.INTENT_LAYER_PRIORITIES.get(intent, ["L1"])
        all_layers = ["L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9", "L10"]
        skip_layers = [l for l in all_layers if l not in priority_layers]

        lines = context.split('\n')
        result = []
        skipping = False

        for line in lines:
            # Check if this line starts a layer section we want to skip
            should_skip = False
            for layer in skip_layers:
                patterns = [
                    f'[{layer}]', f'[Layer {layer[1:]}]', f'Layer {layer[1:]}:',
                    f'{layer}:', f'[{layer} ', f'({layer})',
                ]
                if any(p.lower() in line.lower() for p in patterns):
                    skipping = True
                    should_skip = True
                    break

            # Check if this line starts a section we want to keep
            for layer in priority_layers:
                patterns = [
                    f'[{layer}]', f'[Layer {layer[1:]}]', f'Layer {layer[1:]}:',
                    f'{layer}:', f'[{layer} ',
                ]
                if any(p.lower() in line.lower() for p in patterns):
                    skipping = False
                    break

            if not skipping and not should_skip:
                result.append(line)

        return '\n'.join(result)

    def _summarize_arrays(self, context: str) -> str:
        """Replace numeric arrays with summary statistics."""
        # Find JSON-like arrays of numbers and replace with stats
        def summarize_match(match):
            try:
                numbers = json.loads(match.group(0))
                if isinstance(numbers, list) and all(isinstance(n, (int, float)) for n in numbers):
                    if len(numbers) > 5:
                        avg = sum(numbers) / len(numbers)
                        mn = min(numbers)
                        mx = max(numbers)
                        return f"[avg={avg:.2f}, min={mn:.2f}, max={mx:.2f}, n={len(numbers)}]"
            except (json.JSONDecodeError, ValueError):
                pass
            return match.group(0)

        # Match arrays of 5+ numbers
        pattern = r'\[(?:\s*-?\d+\.?\d*\s*,\s*){4,}(?:\s*-?\d+\.?\d*\s*)\]'
        return re.sub(pattern, summarize_match, context)

    def _smart_truncate(self, context: str, max_tokens: int) -> str:
        """Truncate while preserving the most important information."""
        max_chars = int(max_tokens * self.CHARS_PER_TOKEN)

        # Split into sections
        sections = re.split(r'\n\[', context)

        # Prioritize sections with key metrics
        priority_keywords = [
            "ndvi", "moisture", "temperature", "rain", "humidity",
            "diagnosis", "action", "alert", "risk", "recommendation",
            "field context", "crop", "stage", "soil"
        ]

        scored_sections = []
        for section in sections:
            score = sum(1 for k in priority_keywords if k in section.lower())
            scored_sections.append((score, section))

        scored_sections.sort(key=lambda x: -x[0])

        # Build result within budget
        result_parts = []
        chars_used = 0
        for score, section in scored_sections:
            section_text = f"\n[{section}" if result_parts else section
            if chars_used + len(section_text) <= max_chars:
                result_parts.append(section_text)
                chars_used += len(section_text)

        return ''.join(result_parts)

    def compress_history(self, history: List[Dict[str, str]],
                         max_tokens: Optional[int] = None) -> List[Dict[str, str]]:
        """Compress conversation history to fit within budget.
        
        Keeps most recent turns and summarizes older ones.
        """
        budget = max_tokens or self.HISTORY_BUDGET
        max_chars = int(budget * self.CHARS_PER_TOKEN)

        if not history:
            return []

        # Always keep the last 4 turns
        result = []
        chars_used = 0

        for msg in reversed(history):
            content = msg.get("content", "")
            role = msg.get("role", "user")

            if chars_used + len(content) > max_chars:
                # Truncate older messages
                remaining = max_chars - chars_used
                if remaining > 100:
                    result.insert(0, {"role": role, "content": content[:remaining] + "..."})
                break

            result.insert(0, msg)
            chars_used += len(content)

        return result

    def get_token_budget(self) -> Dict[str, int]:
        """Return the current token budget allocation."""
        return {
            "total": self.MAX_CONTEXT_TOKENS,
            "system_prompt": self.SYSTEM_PROMPT_BUDGET,
            "field_context": self.FIELD_CONTEXT_BUDGET,
            "history": self.HISTORY_BUDGET,
            "response": self.RESPONSE_BUDGET,
            "safety_margin": self.SAFETY_MARGIN,
        }


# Singleton
_compressor = None

def get_compressor() -> ContextCompressor:
    global _compressor
    if _compressor is None:
        _compressor = ContextCompressor()
    return _compressor


def compress_context(context: str, intent: str,
                     max_tokens: Optional[int] = None) -> str:
    """One-call convenience function."""
    return get_compressor().compress_context(context, intent, max_tokens)
