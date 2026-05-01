"""
Layer 3 Benchmarks.

Measures latency, memory, and determinism for the L3 decision pipeline.

Run: py -m layer3_decision.run_l3_benchmarks
"""

from __future__ import annotations

import json
import sys
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from layer1_fusion.schemas import DataHealthScore
from layer2_intelligence.outputs.layer3_adapter import Layer3InputContext
from layer3_decision.runner import run_layer3
from layer3_decision.schema import PlotContext


def _make_context(severity: float = 0.0, zones: int = 0) -> Layer3InputContext:
    zone_status = {}
    if zones > 0:
        for i in range(zones):
            zone_status[f"zone_{i}"] = {
                "dominant_stress_type": "WATER" if severity > 0.3 else None,
                "severity": severity * (0.5 + 0.5 * (i / zones)),
                "confidence": 0.8,
                "stress_count": 1 if severity > 0.3 else 0,
            }

    return Layer3InputContext(
        plot_id="bench_plot",
        layer1_run_id="l1_bench",
        layer2_run_id="l2_bench",
        stress_summary={"WATER": severity} if severity > 0.1 else {},
        zone_status=zone_status,
        phenology_stage="vegetative",
        data_health=DataHealthScore(
            overall=0.8, confidence_ceiling=0.9, status="ok",
        ),
        confidence_ceiling=0.9,
        usable_for_layer3=True,
        operational_signals={
            "sar_available": True, "optical_available": True,
            "rain_available": True, "temp_available": True,
            "optical_obs_count": 10, "sar_obs_count": 8,
            "water_deficit_severity": severity,
            "thermal_severity": 0.0,
            "has_anomaly": severity > 0.3,
            "anomaly_severity": severity * 0.7,
            "anomaly_type": "DROP" if severity > 0.3 else "NONE",
            "growth_velocity": 0.01 - severity * 0.008,
        },
    )

def _make_dag_stress_context() -> Layer3InputContext:
    """Creates a maximal conflict context: water stress, thermal stress, disease risk."""
    return Layer3InputContext(
        plot_id="bench_dag_stress",
        stress_summary={
            "WATER": 0.9,
            "THERMAL": 0.8,
            "MECHANICAL": 0.5,
        },
        phenology_stage="yield_formation",
        operational_signals={
            "sar_available": True, "optical_available": True,
            "rain_available": True, "temp_available": True,
            "optical_obs_count": 20, "sar_obs_count": 15,
            "water_deficit_severity": 0.8,
            "thermal_severity": 0.9,
            "has_anomaly": True,
            "anomaly_severity": 0.9,
            "anomaly_type": "DROUGHT",
            "growth_velocity": -1.5,
        },
        data_health=DataHealthScore(overall=0.9, confidence_ceiling=0.9, status="ok"),
        confidence_ceiling=0.9,
        usable_for_layer3=True
    )


def benchmark_latency(label: str, ctx: Layer3InputContext, iterations: int = 100) -> Dict:
    times = []
    for i in range(iterations):
        t0 = time.perf_counter()
        run_layer3(ctx, run_id=f"bench_{i}")
        times.append((time.perf_counter() - t0) * 1000)

    times.sort()
    return {
        "label": label,
        "iterations": iterations,
        "p50_ms": round(times[len(times) // 2], 3),
        "p95_ms": round(times[int(len(times) * 0.95)], 3),
        "p99_ms": round(times[int(len(times) * 0.99)], 3),
        "min_ms": round(times[0], 3),
        "max_ms": round(times[-1], 3),
    }


def benchmark_memory(label: str, ctx: Layer3InputContext) -> Dict:
    tracemalloc.start()
    run_layer3(ctx, run_id="mem_bench")
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "label": label,
        "current_kb": round(current / 1024, 1),
        "peak_kb": round(peak / 1024, 1),
    }


def benchmark_determinism(ctx: Layer3InputContext, runs: int = 10) -> Dict:
    hashes = set()
    for i in range(runs):
        output = run_layer3(ctx, run_id="det_bench")
        hashes.add(output.content_hash())

    return {
        "runs": runs,
        "unique_hashes": len(hashes),
        "deterministic": len(hashes) == 1,
    }


def run_benchmarks():
    ts = datetime.now(timezone.utc)

    print("=" * 60)
    print("Layer 3 Benchmarks")
    print(f"Timestamp: {ts.isoformat()}")
    print("=" * 60)

    # Scenarios
    ctx_simple = _make_context(severity=0.0, zones=0)
    ctx_stress = _make_context(severity=0.7, zones=0)
    ctx_zones = _make_context(severity=0.5, zones=5)
    ctx_dag = _make_dag_stress_context()

    # Latency
    print("\n--- Latency ---")
    results_latency = []
    for label, ctx in [
        ("Plot-only (no stress)", ctx_simple),
        ("Stress-heavy", ctx_stress),
        ("5-zone aware", ctx_zones),
        ("DAG Combinatorial", ctx_dag),
    ]:
        r = benchmark_latency(label, ctx)
        results_latency.append(r)
        print(f"  {label}: p50={r['p50_ms']:.2f}ms  p95={r['p95_ms']:.2f}ms  p99={r['p99_ms']:.2f}ms")

    # Memory
    print("\n--- Memory ---")
    results_memory = []
    for label, ctx in [
        ("Plot-only", ctx_simple),
        ("Stress-heavy", ctx_stress),
        ("5-zone aware", ctx_zones),
        ("DAG Combinatorial", ctx_dag),
    ]:
        r = benchmark_memory(label, ctx)
        results_memory.append(r)
        print(f"  {label}: peak={r['peak_kb']:.1f}KB")

    # Determinism
    print("\n--- Determinism ---")
    det = benchmark_determinism(ctx_stress)
    print(f"  10-run hash check: {'PASS' if det['deterministic'] else 'FAIL'} "
          f"({det['unique_hashes']} unique hashes)")

    # Report
    report = {
        "timestamp": ts.isoformat(),
        "latency": results_latency,
        "memory": results_memory,
        "determinism": det,
    }

    report_dir = Path(__file__).parent / "artifacts"
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / "l3_benchmark_report.json"
    report_path.write_text(json.dumps(report, indent=2))

    print(f"\n{'=' * 60}")
    print(f"Report: {report_path}")

    # Pass/fail
    all_ok = det["deterministic"]
    for r in results_latency:
        if r["p50_ms"] > 10.0:
            print(f"WARNING: {r['label']} p50 > 10ms")
            all_ok = False

    print(f"Result: {'ALL PASS' if all_ok else 'WARNINGS'}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    run_benchmarks()
