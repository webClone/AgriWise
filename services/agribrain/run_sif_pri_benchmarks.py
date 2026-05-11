"""
SIF/PRI Pipeline — Performance Benchmarks & Calibration Validation.

Runs deterministic benchmarks and calibration checks across 12 real-world
agronomic scenarios, exercising the full L0→L1→L2 SIF/PRI pipeline.

Usage:
    py -m run_sif_pri_benchmarks

Outputs:
    1. Scenario calibration table (expected vs actual outcomes)
    2. Performance benchmarks (ops/sec, latency percentiles)
    3. Determinism verification
    4. JSON report to artifacts/
"""

import json
import math
import time
import statistics
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

from layer0.observation_model import ObservationModel
from layer0.state_vector import N_STATES, IDX_LAI, IDX_PHOTO_EFF

from layer1_fusion.schemas import (
    DataHealthScore, Layer1InputBundle, Layer2InputContext, SpatialIndex, ZoneRef,
)
from layer1_fusion.engine import Layer1FusionEngine
from layer2_intelligence.engine import Layer2IntelligenceEngine
from layer2_intelligence.stress_attributor import attribute_stress


_TS = datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)


# ══════════════════════════════════════════════════════════════════════════
# Real-world scenario library
# ══════════════════════════════════════════════════════════════════════════

SCENARIOS = [
    {
        "id": "sahel_heat_wave",
        "name": "Sahel Heat Wave",
        "description": "42°C, VPD=4.5kPa. Canopy green but photosynthesis dead.",
        "inputs": {"sif": 0.08, "ndvi": 0.65, "temp": 42.0, "vpd": 4.5, "ndmi": 0.30},
        "expect": {"shutdown": True, "severity_min": 0.6, "water": False},
    },
    {
        "id": "flash_drought",
        "name": "Flash Drought (Corn Belt)",
        "description": "Soil drying fast. SIF drops before NDVI. SM=0.12.",
        "inputs": {"sif": 0.15, "ndvi": 0.60, "sm": 0.12, "ndmi": 0.15, "vpd": 3.0},
        "expect": {"shutdown": True, "water": True, "severity_min": 0.3},
    },
    {
        "id": "healthy_irrigated",
        "name": "Healthy Irrigated Wheat",
        "description": "Well-watered, moderate temperature. Perfect conditions.",
        "inputs": {"sif": 1.1, "ndvi": 0.72, "temp": 28.0, "vpd": 1.5, "ndmi": 0.38, "sm": 0.30},
        "expect": {"shutdown": False, "water": False, "thermal": False},
    },
    {
        "id": "senescence",
        "name": "Natural Senescence",
        "description": "End-of-season. Both SIF and NDVI declining together. Water adequate.",
        "inputs": {"sif": 0.12, "ndvi": 0.30, "temp": 30.0, "vpd": 2.0, "ndmi": 0.35, "sm": 0.28},
        "expect": {"shutdown": False, "nutrient": True},
    },
    {
        "id": "bare_fallow",
        "name": "Bare Fallow Field",
        "description": "No crop, post-harvest. No signals.",
        "inputs": {"sif": 0.0, "ndvi": 0.10},
        "expect": {"shutdown": False, "water": False},
    },
    {
        "id": "early_morning_dew",
        "name": "Early Morning Dew Stress",
        "description": "SIF temporarily low from morning stomatal regulation, VPD moderate.",
        "inputs": {"sif": 0.28, "ndvi": 0.68, "temp": 25.0, "vpd": 1.8},
        "expect": {"shutdown": True, "severity_max": 0.55},
    },
    {
        "id": "full_corroboration",
        "name": "Full Corroboration Cascade",
        "description": "All signals agree: SIF crashed, PRI negative, extreme VPD+temp.",
        "inputs": {"sif": 0.05, "pri": -0.04, "ndvi": 0.70, "temp": 40.0, "vpd": 4.0},
        "expect": {"shutdown": True, "severity_min": 0.7},
    },
    {
        "id": "partial_stress_recovery",
        "name": "Partial Recovery Post-Heat",
        "description": "SIF at 0.50, recovering. Temperature back to normal.",
        "inputs": {"sif": 0.50, "ndvi": 0.65, "temp": 30.0, "vpd": 1.5},
        "expect": {"shutdown": False},
    },
    {
        "id": "tropical_lowland_rice",
        "name": "Tropical Lowland Rice",
        "description": "High humidity, adequate water, but extreme heat.",
        "inputs": {"sif": 0.20, "ndvi": 0.62, "temp": 38.0, "vpd": 3.2, "ndmi": 0.35, "sm": 0.35},
        "expect": {"shutdown": True, "water": False, "severity_min": 0.3},
    },
    {
        "id": "cold_snap_wheat",
        "name": "Cold Snap on Spring Wheat",
        "description": "SIF low due to cold-induced photoinhibition. Temp=5°C.",
        "inputs": {"sif": 0.18, "ndvi": 0.58, "temp": 5.0, "vpd": 0.4},
        "expect": {"shutdown": True, "thermal": False},
    },
    {
        "id": "nitrogen_deficiency",
        "name": "Nitrogen Deficiency",
        "description": "NDVI declining, water OK, SIF moderate (still photosynthesizing).",
        "inputs": {"sif": 0.55, "ndvi": 0.35, "ndmi": 0.38, "sm": 0.28, "temp": 28.0},
        "expect": {"shutdown": False, "nutrient": True},
    },
    {
        "id": "drip_irrigated_olive",
        "name": "Drip-Irrigated Olive Grove",
        "description": "Mediterranean, water OK, moderate heat. SIF normal.",
        "inputs": {"sif": 0.75, "ndvi": 0.55, "temp": 35.0, "vpd": 2.8, "ndmi": 0.30},
        "expect": {"shutdown": False},
    },
]


def _feature(value, confidence=0.7):
    return {"value": value, "confidence": confidence, "source_weights": {}}


def _run_scenario(sc):
    """Run a scenario through the stress attributor."""
    inputs = sc["inputs"]
    veg = {}
    if "sif" in inputs and inputs["sif"] is not None:
        veg["sif"] = _feature(inputs["sif"])
    if "pri" in inputs:
        veg["pri"] = _feature(inputs["pri"])
    if "ndvi" in inputs:
        veg["ndvi_mean"] = _feature(inputs["ndvi"])

    water = {}
    if "ndmi" in inputs:
        water["ndmi_mean"] = _feature(inputs["ndmi"])
    if "sm" in inputs:
        water["soil_moisture_vwc"] = _feature(inputs["sm"], 0.6)

    env = {}
    if "temp" in inputs:
        env["temp_max"] = _feature(inputs["temp"], 0.8)
    if "vpd" in inputs:
        env["vpd"] = _feature(inputs["vpd"], 0.7)

    return attribute_stress(
        water_features=water, vegetation_features=veg,
        environment_features=env, operational_features={},
        soil_site_features={}, conflicts=[],
        data_health=DataHealthScore(
            overall=0.8, confidence_ceiling=0.9, status="ok",
        ),
        plot_id=sc["id"], run_id=f"bench_{sc['id']}",
    )


def _check_scenario(sc, items):
    """Validate scenario expectations. Returns (pass, errors)."""
    errors = []
    types = set(s.stress_type for s in items)
    shutdowns = [s for s in items if s.stress_type == "PHOTOSYNTHETIC_SHUTDOWN"]
    expect = sc["expect"]

    if expect.get("shutdown", False):
        if not shutdowns:
            errors.append("EXPECTED shutdown but none detected")
    else:
        if shutdowns:
            errors.append(f"UNEXPECTED shutdown detected (severity={shutdowns[0].severity:.3f})")

    if shutdowns:
        sev = shutdowns[0].severity
        if "severity_min" in expect and sev < expect["severity_min"]:
            errors.append(f"Severity {sev:.3f} below minimum {expect['severity_min']}")
        if "severity_max" in expect and sev > expect["severity_max"]:
            errors.append(f"Severity {sev:.3f} above maximum {expect['severity_max']}")

    for stress_type in ["water", "thermal", "nutrient"]:
        upper = stress_type.upper()
        if stress_type in expect:
            if expect[stress_type] and upper not in types:
                errors.append(f"EXPECTED {upper} but not detected")
            elif not expect[stress_type] and upper in types:
                errors.append(f"UNEXPECTED {upper} detected")

    return len(errors) == 0, errors


# ══════════════════════════════════════════════════════════════════════════
# L0 Observation Model Benchmarks
# ══════════════════════════════════════════════════════════════════════════

def benchmark_l0_sif_pri():
    """Benchmark L0 SIF/PRI observation models."""
    state = [0.0] * N_STATES
    state[IDX_LAI] = 3.0
    state[IDX_PHOTO_EFF] = 0.85

    n = 50000
    # SIF
    t0 = time.perf_counter()
    for _ in range(n):
        ObservationModel.sentinel5p_sif(state)
    sif_ms = (time.perf_counter() - t0) * 1000.0

    # PRI
    t0 = time.perf_counter()
    for _ in range(n):
        ObservationModel.sentinel2_pri(state)
    pri_ms = (time.perf_counter() - t0) * 1000.0

    return {
        "sif_ops_sec": round(n / (sif_ms / 1000.0), 0),
        "sif_per_call_us": round(sif_ms / n * 1000.0, 2),
        "pri_ops_sec": round(n / (pri_ms / 1000.0), 0),
        "pri_per_call_us": round(pri_ms / n * 1000.0, 2),
    }


# ══════════════════════════════════════════════════════════════════════════
# L1 Engine Benchmark with SIF
# ══════════════════════════════════════════════════════════════════════════

def benchmark_l1_with_sif():
    """Benchmark L1 engine with Sentinel-5P packages."""
    engine = Layer1FusionEngine()
    bundle = Layer1InputBundle(
        plot_id="bench_sif",
        run_id="bench_l1_sif",
        run_timestamp=_TS,
        window_start=_TS,
        window_end=_TS,
        sentinel5p_packages=[{
            "sif_mean": 1.0,
            "pri_mean": 0.005,
            "acquisition_datetime": _TS,
            "scene_id": "BENCH_TROPOMI",
            "cloud_fraction": 0.05,
            "reliability_weight": 0.7,
        }],
    )

    # Warmup
    for _ in range(5):
        engine.fuse(bundle)

    n = 200
    latencies = []
    for i in range(n):
        t0 = time.perf_counter()
        engine.fuse(bundle)
        latencies.append((time.perf_counter() - t0) * 1000.0)

    latencies.sort()
    return {
        "ops_sec": round(n / (sum(latencies) / 1000.0), 1),
        "p50_ms": round(statistics.median(latencies), 3),
        "p90_ms": round(latencies[int(n * 0.9)], 3),
        "p99_ms": round(latencies[int(n * 0.99)], 3),
    }


# ══════════════════════════════════════════════════════════════════════════
# L2 Attribution Benchmark
# ══════════════════════════════════════════════════════════════════════════

def benchmark_l2_attribution():
    """Benchmark L2 stress attributor with SIF scenarios."""
    n = 5000
    latencies = []
    for i in range(n):
        t0 = time.perf_counter()
        _run_scenario(SCENARIOS[0])  # Sahel heat wave
        latencies.append((time.perf_counter() - t0) * 1000.0)

    latencies.sort()
    return {
        "ops_sec": round(n / (sum(latencies) / 1000.0), 1),
        "p50_ms": round(statistics.median(latencies), 3),
        "p99_ms": round(latencies[int(n * 0.99)], 3),
    }


# ══════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════

def run_benchmarks():
    print()
    print("=" * 120)
    print("SIF/PRI PIPELINE - CALIBRATION & PERFORMANCE BENCHMARKS")
    print("=" * 120)

    # -- 1. Scenario Calibration --
    print()
    print("-" * 120)
    print("SCENARIO CALIBRATION TABLE")
    print("-" * 120)
    print(f"{'#':<3} {'Scenario':<30} {'Shutdown?':<12} {'Sev':>6} {'Conf':>6} "
          f"{'Other Stress':<25} {'Status':<8} {'Errors'}")
    print("-" * 120)

    all_pass = True
    calibration_results = []

    for i, sc in enumerate(SCENARIOS):
        items = _run_scenario(sc)
        passed, errors = _check_scenario(sc, items)
        if not passed:
            all_pass = False

        shutdowns = [s for s in items if s.stress_type == "PHOTOSYNTHETIC_SHUTDOWN"]
        other = [s.stress_type for s in items if s.stress_type != "PHOTOSYNTHETIC_SHUTDOWN"]

        sd_str = "YES" if shutdowns else "no"
        sev_str = f"{shutdowns[0].severity:.3f}" if shutdowns else "-"
        conf_str = f"{shutdowns[0].confidence:.3f}" if shutdowns else "-"
        other_str = ", ".join(sorted(set(other))) or "-"
        status = "PASS" if passed else "FAIL"
        err_str = "; ".join(errors) if errors else ""

        print(f"{i+1:<3} {sc['name']:<30} {sd_str:<12} {sev_str:>6} {conf_str:>6} "
              f"{other_str:<25} {status:<8} {err_str}")

        calibration_results.append({
            "scenario": sc["id"],
            "name": sc["name"],
            "shutdown": bool(shutdowns),
            "severity": shutdowns[0].severity if shutdowns else None,
            "confidence": shutdowns[0].confidence if shutdowns else None,
            "other_stress": sorted(set(other)),
            "passed": passed,
            "errors": errors,
        })

    print("-" * 120)
    cal_status = "ALL PASS" if all_pass else "FAILURES DETECTED"
    print(f"Calibration: {cal_status} ({sum(1 for r in calibration_results if r['passed'])}/{len(SCENARIOS)} passed)")
    print()

    # ── 2. Performance Benchmarks ───────────────────────────────────────
    print("-" * 120)
    print("PERFORMANCE BENCHMARKS")
    print("-" * 120)

    l0_bench = benchmark_l0_sif_pri()
    print(f"  L0 SIF model:   {l0_bench['sif_ops_sec']:>10,.0f} ops/sec  ({l0_bench['sif_per_call_us']:.2f} us/call)")
    print(f"  L0 PRI model:   {l0_bench['pri_ops_sec']:>10,.0f} ops/sec  ({l0_bench['pri_per_call_us']:.2f} us/call)")

    l1_bench = benchmark_l1_with_sif()
    print(f"  L1 engine+SIF:  {l1_bench['ops_sec']:>10,.1f} ops/sec  "
          f"(p50={l1_bench['p50_ms']:.2f}ms  p90={l1_bench['p90_ms']:.2f}ms  p99={l1_bench['p99_ms']:.2f}ms)")

    l2_bench = benchmark_l2_attribution()
    print(f"  L2 attributor:  {l2_bench['ops_sec']:>10,.1f} ops/sec  "
          f"(p50={l2_bench['p50_ms']:.2f}ms  p99={l2_bench['p99_ms']:.2f}ms)")

    # ── 3. Determinism ──────────────────────────────────────────────────
    print()
    print("-" * 120)
    print("DETERMINISM VERIFICATION")
    print("-" * 120)
    hashes = set()
    for sc in SCENARIOS[:5]:
        items = _run_scenario(sc)
        h = hash(tuple(sorted((s.stress_type, round(s.severity, 6), round(s.confidence, 6)) for s in items)))
        hashes_for_scenario = set()
        for _ in range(10):
            items2 = _run_scenario(sc)
            h2 = hash(tuple(sorted((s.stress_type, round(s.severity, 6), round(s.confidence, 6)) for s in items2)))
            hashes_for_scenario.add(h2)
        is_det = len(hashes_for_scenario) == 1
        print(f"  {sc['name']:<30} {'PASS' if is_det else 'FAIL'} ({len(hashes_for_scenario)} unique hash)")

    print()
    print("=" * 120)

    # ── 4. Save JSON Report ─────────────────────────────────────────────
    report = {
        "pipeline": "sif_pri_v1",
        "timestamp": time.time(),
        "calibration": {
            "all_pass": all_pass,
            "scenarios": calibration_results,
        },
        "benchmarks": {
            "l0": l0_bench,
            "l1": l1_bench,
            "l2": l2_bench,
        },
    }

    artifacts_dir = Path(__file__).resolve().parent / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    report_path = artifacts_dir / "sif_pri_benchmark_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nJSON report saved to: {report_path}")


if __name__ == "__main__":
    run_benchmarks()
