"""
Data Gateway Metrics — Cache performance tracking.

Tracks per-source, per-plot metrics:
  - Hit/miss counts and hit rate
  - Fetch latency percentiles (p50, p95, p99)
  - Error counts by type
  - Storage size per plot
  - Source health (consecutive failures, last success)

Thread-safe via simple locking. Metrics are held in-memory with
periodic flush to MongoDB (if available) for the admin dashboard.

Usage:
    from layer0.data_gateway.metrics import metrics

    metrics.record_hit("soilgrids", "plot_abc")
    metrics.record_miss("soilgrids", "plot_abc", latency_ms=245)
    metrics.record_error("openweather_current", "plot_abc", "timeout")

    stats = metrics.get_stats("soilgrids")
    # → {"hits": 42, "misses": 3, "hit_rate": 0.933, ...}
"""

from __future__ import annotations

import time
import threading
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("agribrain.gateway.metrics")


@dataclass
class SourceMetrics:
    """Metrics for a single source type."""
    hits: int = 0
    misses: int = 0
    errors: int = 0
    error_types: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    latencies_ms: List[float] = field(default_factory=list)
    last_hit_at: Optional[float] = None
    last_miss_at: Optional[float] = None
    last_error_at: Optional[float] = None
    last_error_msg: str = ""
    consecutive_errors: int = 0

    @property
    def total_requests(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        total = self.total_requests
        return self.hits / total if total > 0 else 0.0

    @property
    def latency_p50(self) -> float:
        return self._percentile(50)

    @property
    def latency_p95(self) -> float:
        return self._percentile(95)

    @property
    def latency_p99(self) -> float:
        return self._percentile(99)

    def _percentile(self, p: int) -> float:
        if not self.latencies_ms:
            return 0.0
        sorted_lat = sorted(self.latencies_ms)
        idx = int(len(sorted_lat) * p / 100)
        idx = min(idx, len(sorted_lat) - 1)
        return sorted_lat[idx]

    def to_dict(self) -> Dict:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "errors": self.errors,
            "total_requests": self.total_requests,
            "hit_rate": round(self.hit_rate, 4),
            "latency_p50_ms": round(self.latency_p50, 1),
            "latency_p95_ms": round(self.latency_p95, 1),
            "latency_p99_ms": round(self.latency_p99, 1),
            "consecutive_errors": self.consecutive_errors,
            "last_error": self.last_error_msg if self.last_error_msg else None,
        }


class MetricsCollector:
    """Thread-safe in-memory metrics collector for the Data Gateway.

    Tracks per-source and per-plot performance metrics.
    Designed for the admin dashboard and ML pattern monitoring.
    """

    # Maximum latency samples to keep per source (circular buffer)
    MAX_LATENCY_SAMPLES = 1000

    def __init__(self):
        self._lock = threading.Lock()
        # Global per-source metrics
        self._source_metrics: Dict[str, SourceMetrics] = defaultdict(SourceMetrics)
        # Per-plot per-source metrics
        self._plot_metrics: Dict[str, Dict[str, SourceMetrics]] = defaultdict(
            lambda: defaultdict(SourceMetrics)
        )
        self._start_time = time.time()

    # ── Recording ──────────────────────────────────────────────────

    def record_hit(self, source: str, plot_id: Optional[str] = None):
        """Record a cache hit."""
        with self._lock:
            sm = self._source_metrics[source]
            sm.hits += 1
            sm.last_hit_at = time.time()
            sm.consecutive_errors = 0

            if plot_id:
                pm = self._plot_metrics[plot_id][source]
                pm.hits += 1
                pm.last_hit_at = time.time()

    def record_miss(
        self, source: str, plot_id: Optional[str] = None,
        latency_ms: float = 0.0,
    ):
        """Record a cache miss (data was fetched from API)."""
        with self._lock:
            sm = self._source_metrics[source]
            sm.misses += 1
            sm.last_miss_at = time.time()
            sm.consecutive_errors = 0

            if latency_ms > 0:
                sm.latencies_ms.append(latency_ms)
                if len(sm.latencies_ms) > self.MAX_LATENCY_SAMPLES:
                    sm.latencies_ms = sm.latencies_ms[-self.MAX_LATENCY_SAMPLES:]

            if plot_id:
                pm = self._plot_metrics[plot_id][source]
                pm.misses += 1
                pm.last_miss_at = time.time()
                if latency_ms > 0:
                    pm.latencies_ms.append(latency_ms)
                    if len(pm.latencies_ms) > self.MAX_LATENCY_SAMPLES:
                        pm.latencies_ms = pm.latencies_ms[-self.MAX_LATENCY_SAMPLES:]

    def record_error(
        self, source: str, plot_id: Optional[str] = None,
        error_type: str = "unknown", error_msg: str = "",
    ):
        """Record a fetch error."""
        with self._lock:
            sm = self._source_metrics[source]
            sm.errors += 1
            sm.error_types[error_type] += 1
            sm.last_error_at = time.time()
            sm.last_error_msg = error_msg
            sm.consecutive_errors += 1

            if sm.consecutive_errors >= 5:
                logger.warning(
                    "Source %s has %d consecutive errors: %s",
                    source, sm.consecutive_errors, error_msg,
                )

            if plot_id:
                pm = self._plot_metrics[plot_id][source]
                pm.errors += 1
                pm.last_error_at = time.time()
                pm.last_error_msg = error_msg
                pm.consecutive_errors += 1

    def record_promotion(self, source: str, plot_id: str, obs_count: int = 1):
        """Record observation promotion to warm tier."""
        # Lightweight tracking — just count for now
        pass

    # ── Queries ─────────────────────────────────────────────────────

    def get_source_stats(self, source: str) -> Dict:
        """Get metrics for a single source."""
        with self._lock:
            return self._source_metrics[source].to_dict()

    def get_all_source_stats(self) -> Dict[str, Dict]:
        """Get metrics for all sources."""
        with self._lock:
            return {
                source: sm.to_dict()
                for source, sm in sorted(self._source_metrics.items())
                if sm.total_requests > 0
            }

    def get_plot_stats(self, plot_id: str) -> Dict[str, Dict]:
        """Get per-source metrics for a specific plot."""
        with self._lock:
            if plot_id not in self._plot_metrics:
                return {}
            return {
                source: sm.to_dict()
                for source, sm in sorted(self._plot_metrics[plot_id].items())
                if sm.total_requests > 0
            }

    def get_global_summary(self) -> Dict:
        """Get a high-level summary of all gateway metrics."""
        with self._lock:
            total_hits = sum(sm.hits for sm in self._source_metrics.values())
            total_misses = sum(sm.misses for sm in self._source_metrics.values())
            total_errors = sum(sm.errors for sm in self._source_metrics.values())
            total = total_hits + total_misses

            # Source health
            unhealthy_sources = [
                source for source, sm in self._source_metrics.items()
                if sm.consecutive_errors >= 3
            ]

            return {
                "uptime_seconds": int(time.time() - self._start_time),
                "total_requests": total,
                "total_hits": total_hits,
                "total_misses": total_misses,
                "total_errors": total_errors,
                "global_hit_rate": round(total_hits / total, 4) if total > 0 else 0.0,
                "active_sources": len([
                    s for s in self._source_metrics.values()
                    if s.total_requests > 0
                ]),
                "active_plots": len(self._plot_metrics),
                "unhealthy_sources": unhealthy_sources,
            }

    def is_source_healthy(self, source: str) -> bool:
        """Check if a source is healthy (< 3 consecutive errors)."""
        with self._lock:
            return self._source_metrics[source].consecutive_errors < 3

    # ── Reset ──────────────────────────────────────────────────────

    def reset(self):
        """Reset all metrics. Used for testing."""
        with self._lock:
            self._source_metrics.clear()
            self._plot_metrics.clear()
            self._start_time = time.time()


# ── Global singleton ───────────────────────────────────────────────────
metrics = MetricsCollector()
