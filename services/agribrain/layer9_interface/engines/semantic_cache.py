"""
semantic_cache.py - TF-IDF Semantic Response Cache
====================================================

Caches LLM responses for similar queries to reduce latency on repeated
common questions. Uses TF-IDF cosine similarity for semantic matching.

Features:
  - TF-IDF vectorization of incoming queries
  - Configurable similarity threshold (default 0.85)
  - Cache invalidation when sensor data changes significantly
  - TTL-based expiry (default 1 hour)
  - Thread-safe singleton
"""

import time
import math
import re
import json
import hashlib
import threading
from typing import Dict, Any, Optional, List, Tuple
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class CacheEntry:
    """A single cached response."""
    query: str
    response: str
    context_hash: str
    timestamp: float
    hit_count: int = 0
    tfidf_vector: Optional[Dict[str, float]] = None


class SemanticCache:
    """TF-IDF based semantic cache for LLM responses."""

    def __init__(self, similarity_threshold: float = 0.85,
                 ttl_seconds: int = 3600, max_entries: int = 200):
        self.threshold = similarity_threshold
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self._idf: Dict[str, float] = {}
        self._df: Dict[str, int] = {}  # document frequency counts (BUG-4 fix)
        self._doc_count = 0

    # ================================================================
    # TF-IDF Engine
    # ================================================================

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Simple tokenizer: lowercase, split on non-alpha, filter stopwords."""
        tokens = re.findall(r'\b[a-z]{2,}\b', text.lower())
        stopwords = {'the', 'is', 'at', 'in', 'of', 'and', 'or', 'a', 'an',
                     'to', 'for', 'on', 'it', 'my', 'do', 'me', 'how', 'what',
                     'does', 'this', 'that', 'with', 'from', 'be', 'was',
                     'are', 'has', 'have', 'can', 'will', 'should', 'would'}
        return [t for t in tokens if t not in stopwords]

    def _compute_tf(self, tokens: List[str]) -> Dict[str, float]:
        """Compute term frequency vector."""
        counts = Counter(tokens)
        total = len(tokens) if tokens else 1
        return {t: c / total for t, c in counts.items()}

    def _compute_tfidf(self, tokens: List[str]) -> Dict[str, float]:
        """Compute TF-IDF vector for a token list."""
        tf = self._compute_tf(tokens)
        tfidf = {}
        for term, tf_val in tf.items():
            idf = self._idf.get(term, math.log(self._doc_count + 1))
            tfidf[term] = tf_val * idf
        return tfidf

    def _update_idf(self, tokens: List[str]):
        """Update IDF counts with new document. (BUG-4 fix: use separate df counter)"""
        self._doc_count += 1
        unique_terms = set(tokens)
        for term in unique_terms:
            self._df[term] = self._df.get(term, 0) + 1
            self._idf[term] = math.log((self._doc_count + 1) / (self._df[term] + 1))

    @staticmethod
    def _cosine_similarity(v1: Dict[str, float], v2: Dict[str, float]) -> float:
        """Cosine similarity between two sparse vectors."""
        all_keys = set(v1.keys()) | set(v2.keys())
        if not all_keys:
            return 0.0

        dot = sum(v1.get(k, 0) * v2.get(k, 0) for k in all_keys)
        mag1 = math.sqrt(sum(v ** 2 for v in v1.values()))
        mag2 = math.sqrt(sum(v ** 2 for v in v2.values()))

        if mag1 == 0 or mag2 == 0:
            return 0.0

        return dot / (mag1 * mag2)

    # ================================================================
    # Context Hashing (for invalidation)
    # ================================================================

    @staticmethod
    def hash_context(context: Dict[str, Any]) -> str:
        """Create a hash of the field context for cache invalidation.
        
        Only hashes values that change frequently (sensor readings),
        not static data (soil type, crop).
        """
        volatile_keys = [
            "soil_moisture", "soil_temperature", "ambient_temperature",
            "humidity", "wind_speed", "rain_mm_last_7d", "ndvi", "ndmi"
        ]

        # Extract volatile values, round to reduce unnecessary invalidation
        vals = {}
        if isinstance(context, dict):
            sensors = context.get("sensors", context)
            for k in volatile_keys:
                v = sensors.get(k) if isinstance(sensors, dict) else None
                if v is not None:
                    # Round to 1 decimal to avoid cache thrashing
                    vals[k] = round(float(v), 1) if isinstance(v, (int, float)) else str(v)

        raw = json.dumps(vals, sort_keys=True)
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    # ================================================================
    # Cache Operations
    # ================================================================

    def get(self, query: str, context: Dict[str, Any]) -> Optional[str]:
        """Look up a cached response for a similar query.
        
        Returns:
            Cached response text if found, None otherwise.
        """
        with self._lock:
            now = time.time()
            tokens = self._tokenize(query)
            query_vec = self._compute_tfidf(tokens)
            ctx_hash = self.hash_context(context)

            best_match = None
            best_sim = 0.0

            # Clean expired entries
            expired = [k for k, v in self._cache.items() if now - v.timestamp > self.ttl]
            for k in expired:
                del self._cache[k]

            for key, entry in self._cache.items():
                # Context must match (same sensor readings)
                if entry.context_hash != ctx_hash:
                    continue

                # Check semantic similarity
                if entry.tfidf_vector:
                    sim = self._cosine_similarity(query_vec, entry.tfidf_vector)
                    if sim > best_sim and sim >= self.threshold:
                        best_sim = sim
                        best_match = entry

            if best_match:
                best_match.hit_count += 1
                return best_match.response

        return None

    def put(self, query: str, response: str, context: Dict[str, Any]):
        """Cache a response for future similar queries."""
        with self._lock:
            tokens = self._tokenize(query)
            self._update_idf(tokens)
            tfidf_vec = self._compute_tfidf(tokens)
            ctx_hash = self.hash_context(context)

            key = hashlib.md5(query.lower().encode()).hexdigest()[:16]

            self._cache[key] = CacheEntry(
                query=query,
                response=response,
                context_hash=ctx_hash,
                timestamp=time.time(),
                tfidf_vector=tfidf_vec
            )

            # Evict oldest if over capacity
            if len(self._cache) > self.max_entries:
                oldest_key = min(self._cache, key=lambda k: self._cache[k].timestamp)
                del self._cache[oldest_key]

    def invalidate_all(self):
        """Clear all cached responses."""
        with self._lock:
            self._cache.clear()

    def stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        with self._lock:
            total_hits = sum(e.hit_count for e in self._cache.values())
            return {
                "entries": len(self._cache),
                "total_hits": total_hits,
                "idf_terms": len(self._idf),
                "doc_count": self._doc_count
            }


# json imported at module top (BUG-3 fix)

# ============================================================================
# Singleton
# ============================================================================

_cache_instance = None

def get_cache() -> SemanticCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = SemanticCache()
    return _cache_instance


def cached_query(query: str, context: Dict[str, Any],
                 query_fn=None) -> Tuple[str, bool]:
    """Try cache first, fall back to query_fn.
    
    Returns:
        (response, was_cached)
    """
    cache = get_cache()
    cached = cache.get(query, context)
    if cached:
        return cached, True

    if query_fn:
        response = query_fn(query)
        if response:
            cache.put(query, response, context)
        return response, False

    return "", False
