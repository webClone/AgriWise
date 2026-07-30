"""
Core Observability and Performance Registry.
Tracks metrics like cache hit/miss rates, latencies, memory/storage,
and budget overruns across the pipeline.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Define file path for persistent metrics log
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
METRICS_PATH = os.path.join(BASE_DIR, "artifacts", "pipeline_observability_report.json")


@dataclass
class PerformanceMetric:
    pipeline_step: str  # "asmae" or "layer10"
    mode: str
    cache_status: str  # "hit", "miss", "bypass"
    latency_ms: float
    timestamp: str
    budget_ms: float
    budget_overrun: bool
    storage_kb: float = 0.0
    extra_details: Dict[str, Any] = field(default_factory=dict)


class ObservabilityRegistry:
    """Central registry for performance profiling, budget checks, and cache audits."""

    def __init__(self) -> None:
        self._metrics: List[PerformanceMetric] = []

    def record(
        self,
        step: str,
        mode: str,
        cache_status: str,
        latency_ms: float,
        budget_ms: float,
        storage_kb: float = 0.0,
        extra_details: Optional[Dict[str, Any]] = None,
    ) -> PerformanceMetric:
        overrun = latency_ms > budget_ms
        metric = PerformanceMetric(
            pipeline_step=step,
            mode=mode,
            cache_status=cache_status,
            latency_ms=round(latency_ms, 2),
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            budget_ms=budget_ms,
            budget_overrun=overrun,
            storage_kb=round(storage_kb, 2),
            extra_details=extra_details or {},
        )
        self._metrics.append(metric)

        # Log budget overrun warnings
        if overrun:
            import logging
            logging.getLogger(__name__).warning(
                "BUDGET OVERRUN: Step '%s' in mode '%s' took %.1fms (Budget: %.1fms)",
                step, mode, latency_ms, budget_ms
            )

        # Append to report file asynchronously/on every write for persistence
        self.save_report()
        return metric

    def save_report(self) -> None:
        """Write the aggregated report to the artifacts directory."""
        try:
            os.makedirs(os.path.dirname(METRICS_PATH), exist_ok=True)
            report = self.get_summary_report()
            with open(METRICS_PATH, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
        except Exception:
            pass

    def get_summary_report(self) -> Dict[str, Any]:
        """Compile a summary report of hits, misses, latency, and budget compliance."""
        total_runs = len(self._metrics)
        if total_runs == 0:
            return {
                "total_runs": 0,
                "hit_rate_pct": 0.0,
                "avg_latency_ms": 0.0,
                "budget_compliance_pct": 100.0,
                "metrics": [],
            }

        hits = sum(1 for m in self._metrics if m.cache_status == "hit")
        overruns = sum(1 for m in self._metrics if m.budget_overrun)
        latencies = [m.latency_ms for m in self._metrics]

        return {
            "total_runs": total_runs,
            "hit_rate_pct": round((hits / total_runs) * 100, 2),
            "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
            "budget_compliance_pct": round(((total_runs - overruns) / total_runs) * 100, 2),
            "metrics": [
                {
                    "step": m.pipeline_step,
                    "mode": m.mode,
                    "cache": m.cache_status,
                    "latency_ms": m.latency_ms,
                    "budget_ms": m.budget_ms,
                    "overrun": m.budget_overrun,
                    "storage_kb": m.storage_kb,
                    "timestamp": m.timestamp,
                    "details": m.extra_details,
                }
                for m in self._metrics
            ],
        }

    def clear(self) -> None:
        self._metrics.clear()
        if os.path.exists(METRICS_PATH):
            try:
                os.remove(METRICS_PATH)
            except Exception:
                pass


# Global registry instance
observability_registry = ObservabilityRegistry()
