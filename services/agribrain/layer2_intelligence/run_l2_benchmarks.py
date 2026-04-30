"""
Layer 2 Intelligence — Performance Benchmarks.

Runs deterministic benchmarking for the L2 Engine.
Outputs ops/sec, latency percentiles, memory usage, and determinism check
to a JSON report.

Usage:
    py -m layer2_intelligence.run_l2_benchmarks
"""

import json
import time
import statistics
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

from layer1_fusion.schemas import DataHealthScore, Layer2InputContext, SpatialIndex, ZoneRef
from layer2_intelligence.engine import Layer2IntelligenceEngine


_TS = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


def _build_benchmark_payload(num_zones: int) -> Layer2InputContext:
    """Build a payload with the specified number of zones."""
    zones = [ZoneRef(zone_id=f"z{i}") for i in range(num_zones)]

    water_ctx = {"ndmi_mean": {"value": 0.2, "confidence": 0.8}}
    veg_ctx = {"ndvi_mean": {"value": 0.5, "confidence": 0.8}}
    env_ctx = {"temp_max": {"value": 30.0, "confidence": 0.8}}

    for i in range(num_zones):
        val = 0.1 if i % 10 == 0 else 0.4
        water_ctx[f"ndmi_z{i}"] = {"value": val, "confidence": 0.8, "scope_id": f"z{i}"}
        veg_ctx[f"ndvi_z{i}"] = {"value": 0.5, "confidence": 0.8, "scope_id": f"z{i}"}

    return Layer2InputContext(
        plot_id="bench_plot",
        water_context=water_ctx,
        vegetation_context=veg_ctx,
        stress_evidence_context=env_ctx,
        phenology_context={},
        operational_context={},
        soil_site_context={},
        conflicts=[],
        gaps=[],
        provenance_ref="bench_l1",
        spatial_index_ref=SpatialIndex(plot_id="bench_plot", zones=zones) if num_zones > 0 else None,
        data_health=DataHealthScore(overall=0.8, confidence_ceiling=0.9, status="ok"),
    )


def _benchmark_scenario(engine, payload, iterations, run_prefix="bench"):
    """Run a single benchmark scenario, return latencies and memory delta."""
    # Warmup
    for _ in range(5):
        engine.analyze(payload, run_id="warmup")

    tracemalloc.start()
    snap_before = tracemalloc.take_snapshot()
    latencies = []

    for i in range(iterations):
        t0 = time.perf_counter()
        engine.analyze(payload, run_id=f"{run_prefix}_{i}")
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)

    snap_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    # Memory delta
    stats = snap_after.compare_to(snap_before, "lineno")
    mem_delta_kb = sum(s.size_diff for s in stats[:20]) / 1024.0

    return latencies, mem_delta_kb


def _run_determinism_check(engine, payload, n=10):
    """Run N times and verify all produce the same content_hash."""
    hashes = set()
    for i in range(n):
        pkg = engine.analyze(payload, run_id="determ_check", run_timestamp=_TS)
        hashes.add(pkg.content_hash())
    return len(hashes) == 1, hashes


def run_benchmarks():
    engine = Layer2IntelligenceEngine()

    scenarios = [
        {"name": "plot_only", "zones": 0, "iterations": 1000},
        {"name": "10_zones", "zones": 10, "iterations": 500},
        {"name": "100_zones", "zones": 100, "iterations": 100},
        {"name": "stress_heavy", "zones": 0, "iterations": 500},
    ]

    results = []

    print()
    print("=" * 100)
    print("LAYER 2 PERFORMANCE BENCHMARK")
    print("=" * 100)
    print(f"{'Scenario':<15} {'Zones':>6} {'Iter':>6} | "
          f"{'Ops/sec':>10} | {'p50(ms)':>8} {'p90(ms)':>8} {'p99(ms)':>8} | "
          f"{'Mem(KB)':>8}")
    print("-" * 100)

    for sc in scenarios:
        if sc["name"] == "stress_heavy":
            # Special payload with maximum stress signals
            payload = Layer2InputContext(
                plot_id="bench_stress",
                water_context={
                    "ndmi_mean": {"value": 0.05, "confidence": 0.7, "source_weights": {}},
                    "soil_moisture_vwc": {"value": 0.08, "confidence": 0.6, "source_weights": {}},
                },
                vegetation_context={"ndvi_mean": {"value": 0.20, "confidence": 0.7, "source_weights": {}}},
                stress_evidence_context={
                    "temp_max": {"value": 42.0, "confidence": 0.8, "source_weights": {}},
                    "vpd": {"value": 4.0, "confidence": 0.7, "source_weights": {}},
                },
                operational_context={"precipitation_mm": {"value": 0.0, "confidence": 0.8, "source_weights": {}}},
                soil_site_context={},
                conflicts=[], gaps=[],
                provenance_ref="bench_stress_l1",
                data_health=DataHealthScore(overall=0.6, confidence_ceiling=0.8, status="ok"),
            )
        else:
            payload = _build_benchmark_payload(sc["zones"])

        latencies, mem_kb = _benchmark_scenario(engine, payload, sc["iterations"])

        latencies.sort()
        p50 = statistics.median(latencies)
        p90 = latencies[int(len(latencies) * 0.9)]
        p99 = latencies[int(len(latencies) * 0.99)]
        ops_per_sec = sc["iterations"] / (sum(latencies) / 1000.0)

        print(f"{sc['name']:<15} {sc['zones']:>6} {sc['iterations']:>6} | "
              f"{ops_per_sec:>10.1f} | {p50:>8.2f} {p90:>8.2f} {p99:>8.2f} | "
              f"{mem_kb:>8.1f}")

        results.append({
            "scenario": sc["name"],
            "zones": sc["zones"],
            "iterations": sc["iterations"],
            "ops_per_sec": round(ops_per_sec, 2),
            "latency_ms": {
                "p50": round(p50, 3),
                "p90": round(p90, 3),
                "p99": round(p99, 3),
                "mean": round(statistics.mean(latencies), 3),
                "max": round(max(latencies), 3),
            },
            "memory_delta_kb": round(mem_kb, 1),
        })

    print("=" * 100)

    # Determinism check
    print("\nDeterminism verification (10 runs, same input)...")
    payload = _build_benchmark_payload(10)
    is_deterministic, hashes = _run_determinism_check(engine, payload, n=10)
    determ_status = "PASS" if is_deterministic else "FAIL"
    print(f"  Result: {determ_status} — {len(hashes)} unique hash(es)")

    # Save JSON report
    report = {
        "engine_version": engine.ENGINE_VERSION,
        "timestamp": time.time(),
        "determinism_check": is_deterministic,
        "benchmarks": results,
    }

    artifacts_dir = Path(__file__).resolve().parent.parent / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    report_path = artifacts_dir / "l2_benchmark_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nJSON report saved to: {report_path}")


if __name__ == "__main__":
    run_benchmarks()

