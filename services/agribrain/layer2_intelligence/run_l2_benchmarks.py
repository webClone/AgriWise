"""
Layer 2 Intelligence — Performance Benchmarks.

Runs deterministic benchmarking for the L2 Engine.
Outputs ops/sec and latency percentiles to a JSON report.
Does NOT depend on external benchmarking libraries (e.g. pytest-benchmark)
to remain CI-friendly and standalone.

Usage:
    py -m layer2_intelligence.run_l2_benchmarks
"""

import json
import time
import statistics
from pathlib import Path

from layer1_fusion.schemas import DataHealthScore, Layer2InputContext, SpatialIndex, ZoneRef
from layer2_intelligence.engine import Layer2IntelligenceEngine


def _build_benchmark_payload(num_zones: int) -> Layer2InputContext:
    """Build a payload with the specified number of zones."""
    
    zones = [ZoneRef(zone_id=f"z{i}") for i in range(num_zones)]
    
    water_ctx = {"ndmi_mean": {"value": 0.2, "confidence": 0.8}}
    veg_ctx = {"ndvi_mean": {"value": 0.5, "confidence": 0.8}}
    env_ctx = {"temp_max": {"value": 30.0, "confidence": 0.8}}
    
    # Add zone-scoped features
    for i in range(num_zones):
        # Sprinkle some stress to ensure attribution logic runs per zone
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


def run_benchmarks():
    engine = Layer2IntelligenceEngine()
    
    scenarios = [
        {"name": "plot_only", "zones": 0, "iterations": 1000},
        {"name": "10_zones", "zones": 10, "iterations": 500},
        {"name": "100_zones", "zones": 100, "iterations": 100},
    ]
    
    results = []
    
    print()
    print("=" * 80)
    print("LAYER 2 PERFORMANCE BENCHMARK")
    print("=" * 80)
    print(f"{'Scenario':<15} {'Zones':>6} {'Iter':>6} | {'Ops/sec':>10} | {'p50(ms)':>8} {'p90(ms)':>8} {'p99(ms)':>8}")
    print("-" * 80)
    
    for sc in scenarios:
        payload = _build_benchmark_payload(sc["zones"])
        iterations = sc["iterations"]
        
        # Warmup
        for _ in range(5):
            engine.analyze(payload, run_id="warmup")
            
        latencies = []
        
        t_start = time.perf_counter()
        for i in range(iterations):
            t0 = time.perf_counter()
            engine.analyze(payload, run_id=f"bench_{i}")
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000.0) # ms
            
        t_end = time.perf_counter()
        total_time_s = t_end - t_start
        ops_per_sec = iterations / total_time_s
        
        latencies.sort()
        p50 = statistics.median(latencies)
        p90 = latencies[int(len(latencies) * 0.9)]
        p99 = latencies[int(len(latencies) * 0.99)]
        
        print(f"{sc['name']:<15} {sc['zones']:>6} {iterations:>6} | {ops_per_sec:>10.1f} | {p50:>8.2f} {p90:>8.2f} {p99:>8.2f}")
        
        results.append({
            "scenario": sc["name"],
            "zones": sc["zones"],
            "iterations": iterations,
            "ops_per_sec": round(ops_per_sec, 2),
            "latency_ms": {
                "p50": round(p50, 3),
                "p90": round(p90, 3),
                "p99": round(p99, 3),
                "mean": round(statistics.mean(latencies), 3),
                "max": round(max(latencies), 3)
            }
        })
        
    print("=" * 80)
    
    # Save JSON report
    report = {
        "engine_version": engine.ENGINE_VERSION,
        "timestamp": time.time(),
        "benchmarks": results
    }
    
    artifacts_dir = Path(__file__).resolve().parent.parent / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    report_path = artifacts_dir / "l2_benchmark_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
        
    print(f"\nJSON report saved to: {report_path}")

if __name__ == "__main__":
    run_benchmarks()
