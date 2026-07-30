"""
performance_monitor.py - System Performance & Quality Dashboard
=================================================================

Tracks real-time performance metrics across the entire AgriBrain
chat pipeline:
  - LLM inference latency (per-query and rolling average)
  - Token usage and efficiency
  - Strategy distribution (Direct vs CoT vs Knowledge vs Cached)
  - Response quality scores over time
  - Cache hit rates
  - Error rates and failure modes
  - Per-intent performance breakdown
"""

import time
import json
import os
import threading
from typing import Dict, Any, List, Optional
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict


@dataclass
class QueryMetrics:
    """Metrics for a single query."""
    timestamp: float
    query_hash: str
    intent: str
    strategy: str          # DIRECT, COT, KNOWLEDGE, CACHED, DECOMPOSED
    latency_ms: float
    tokens_used: int
    quality_score: float
    cache_hit: bool
    error: Optional[str] = None


class PerformanceMonitor:
    """Real-time performance monitoring for AgriBrain chat."""

    DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "..", "data", "performance")

    def __init__(self, window_size: int = 100):
        os.makedirs(self.DATA_DIR, exist_ok=True)
        self._metrics: deque = deque(maxlen=window_size)
        self._lock = threading.Lock()
        self._session_start = time.time()
        self._counters = defaultdict(int)

    def record(self, metrics: QueryMetrics):
        """Record metrics for a single query."""
        with self._lock:
            self._metrics.append(metrics)
            self._counters["total_queries"] += 1
            self._counters[f"strategy_{metrics.strategy}"] += 1
            self._counters[f"intent_{metrics.intent}"] += 1
            if metrics.cache_hit:
                self._counters["cache_hits"] += 1
            if metrics.error:
                self._counters["errors"] += 1
            self._counters["total_tokens"] += metrics.tokens_used
            self._counters["total_latency_ms"] += metrics.latency_ms

    def record_query(self, intent: str, strategy: str, latency_ms: float,
                     tokens: int = 0, quality: float = 0.5,
                     cache_hit: bool = False, error: str = None):
        """Convenience method to record a query."""
        import hashlib
        qm = QueryMetrics(
            timestamp=time.time(),
            query_hash=hashlib.md5(f"{time.time()}".encode()).hexdigest()[:8],
            intent=intent, strategy=strategy,
            latency_ms=latency_ms, tokens_used=tokens,
            quality_score=quality, cache_hit=cache_hit, error=error
        )
        self.record(qm)

    def get_dashboard(self) -> Dict[str, Any]:
        """Get a real-time performance dashboard."""
        with self._lock:
            metrics = list(self._metrics)

        if not metrics:
            return {"status": "no_data", "message": "No queries recorded yet"}

        # Latency stats
        latencies = [m.latency_ms for m in metrics]
        qualities = [m.quality_score for m in metrics]

        dashboard = {
            "session_duration_s": round(time.time() - self._session_start, 1),
            "total_queries": self._counters["total_queries"],
            "latency": {
                "avg_ms": round(sum(latencies) / len(latencies), 1),
                "p50_ms": round(sorted(latencies)[len(latencies)//2], 1),
                "p95_ms": round(sorted(latencies)[int(len(latencies)*0.95)], 1) if len(latencies) >= 20 else None,
                "min_ms": round(min(latencies), 1),
                "max_ms": round(max(latencies), 1),
            },
            "quality": {
                "avg_score": round(sum(qualities) / len(qualities), 3),
                "min_score": round(min(qualities), 3),
                "max_score": round(max(qualities), 3),
            },
            "strategy_distribution": {
                "DIRECT": self._counters.get("strategy_DIRECT", 0),
                "COT": self._counters.get("strategy_COT", 0),
                "KNOWLEDGE": self._counters.get("strategy_KNOWLEDGE", 0),
                "CACHED": self._counters.get("strategy_CACHED", 0),
                "DECOMPOSED": self._counters.get("strategy_DECOMPOSED", 0),
                "COT_RETRY": self._counters.get("strategy_COT_RETRY", 0),
            },
            "cache": {
                "hit_rate": round(
                    self._counters.get("cache_hits", 0) /
                    max(self._counters["total_queries"], 1), 3
                ),
                "total_hits": self._counters.get("cache_hits", 0),
            },
            "errors": {
                "total": self._counters.get("errors", 0),
                "error_rate": round(
                    self._counters.get("errors", 0) /
                    max(self._counters["total_queries"], 1), 3
                ),
            },
            "tokens": {
                "total_used": self._counters.get("total_tokens", 0),
                "avg_per_query": round(
                    self._counters.get("total_tokens", 0) /
                    max(self._counters["total_queries"], 1), 1
                ),
            },
        }

        # Per-intent breakdown
        intent_stats = {}
        intent_groups = defaultdict(list)
        for m in metrics:
            intent_groups[m.intent].append(m)

        for intent, group in intent_groups.items():
            lat = [m.latency_ms for m in group]
            qual = [m.quality_score for m in group]
            intent_stats[intent] = {
                "count": len(group),
                "avg_latency_ms": round(sum(lat) / len(lat), 1),
                "avg_quality": round(sum(qual) / len(qual), 3),
            }
        dashboard["per_intent"] = intent_stats

        return dashboard

    def save_report(self, filename: Optional[str] = None):
        """Save performance report to disk."""
        fname = filename or os.path.join(
            self.DATA_DIR, f"perf_report_{int(time.time())}.json"
        )
        dashboard = self.get_dashboard()
        try:
            with open(fname, 'w', encoding='utf-8') as f:
                json.dump(dashboard, f, indent=2)
        except Exception:
            pass

    def print_dashboard(self):
        """Print dashboard to console."""
        d = self.get_dashboard()
        if d.get("status") == "no_data":
            print("  No queries recorded yet")
            return

        print(f"\n  {'='*50}")
        print(f"  AgriBrain Performance Dashboard")
        print(f"  {'='*50}")
        print(f"  Queries: {d['total_queries']} | Session: {d['session_duration_s']}s")
        print(f"  Latency: avg={d['latency']['avg_ms']}ms, p50={d['latency']['p50_ms']}ms")
        print(f"  Quality: avg={d['quality']['avg_score']}")
        print(f"  Cache Hit Rate: {d['cache']['hit_rate']*100:.1f}%")
        print(f"  Error Rate: {d['errors']['error_rate']*100:.1f}%")
        print(f"  Strategies: {json.dumps(d['strategy_distribution'])}")


# Singleton
_monitor = None

def get_monitor() -> PerformanceMonitor:
    global _monitor
    if _monitor is None:
        _monitor = PerformanceMonitor()
    return _monitor
