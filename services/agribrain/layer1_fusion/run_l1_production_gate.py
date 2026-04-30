"""
Layer 1 Production Gate Runner.

Mirrors Layer 0's run_production_gate.py — runs all calibration scenarios,
asserts prohibitions, invariants, and health. Outputs a report table.

Usage:
    python -m layer1_fusion.run_l1_production_gate
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from layer1_fusion.engine import Layer1FusionEngine
from layer1_fusion.schemas import Layer1InputBundle, Layer1ContextPackage


# ============================================================================
# Fixture dataclasses (minimal — shared across scenarios)
# ============================================================================

_TS = datetime(2026, 4, 15, 12, 0, 0, tzinfo=timezone.utc)


@dataclass
class _S2Meta:
    scene_id: str = "S2A_GATE"
    acquisition_datetime: datetime = field(default_factory=lambda: _TS - timedelta(days=2))
    qa_version: str = "s2qa_v1"
    grid_alignment_hash: str = "h1"

@dataclass
class _S2QA:
    usable: bool = True
    reliability_weight: float = 0.85
    cloud_fraction: float = 0.05

@dataclass
class _S2PlotSummary:
    ndvi_mean: float = 0.65
    ndmi_mean: float = 0.30
    ndre_mean: float = 0.18
    evi_mean: float = 0.38
    bsi_mean: float = 0.10
    vegetation_fraction_scl: float = 0.78
    bare_soil_fraction_scl: float = 0.06

@dataclass
class _S2ZoneSummary:
    zone_id: str = "zone_a"
    ndvi_mean: float = 0.70
    ndmi_mean: float = 0.32
    ndre_mean: float = 0.20
    reliability: float = 0.80
    cloud_fraction: float = 0.05

@dataclass
class _S2Pkg:
    plot_id: str = "gate_plot"
    metadata: _S2Meta = field(default_factory=_S2Meta)
    qa: _S2QA = field(default_factory=_S2QA)
    plot_summary: _S2PlotSummary = field(default_factory=_S2PlotSummary)
    zone_summaries: list = field(default_factory=list)
    indices: dict = field(default_factory=dict)

@dataclass
class _Reading:
    device_id: str = "d1"
    variable: str = "soil_moisture_vwc"
    value: float = 0.32
    unit: str = "fraction"
    timestamp: datetime = field(default_factory=lambda: _TS - timedelta(hours=2))

@dataclass
class _SensorQA:
    usable: bool = True
    reading_reliability: float = 0.88
    update_allowed: bool = True

@dataclass
class _SensorPkg:
    plot_id: str = "gate_plot"
    readings: list = field(default_factory=lambda: [_Reading()])
    qa_results: list = field(default_factory=lambda: [_SensorQA()])
    aggregates: list = field(default_factory=list)
    process_forcing_events: list = field(default_factory=list)
    window_start: datetime = field(default_factory=lambda: _TS - timedelta(hours=6))
    window_end: datetime = field(default_factory=lambda: _TS)

@dataclass
class _FPF:
    date: str = "day_0"
    precipitation_mm: float = 5.0
    et0_mm: float = 4.2
    temp_max: float = 32.0
    temp_min: float = 18.0

@dataclass
class _ForecastPkg:
    plot_id: str = "gate_plot"
    forecast_process_forcing: list = field(
        default_factory=lambda: [_FPF(date="day_0"), _FPF(date="day_1")])


def _bundle(**kw) -> Layer1InputBundle:
    defaults = dict(
        plot_id="gate_plot", run_id="gate_run", run_timestamp=_TS,
        window_start=_TS - timedelta(days=30), window_end=_TS,
    )
    defaults.update(kw)
    return Layer1InputBundle(**defaults)


# ============================================================================
# Scenarios
# ============================================================================

def _build_scenarios() -> List[Tuple[str, Layer1InputBundle]]:
    return [
        ("Full-stack", _bundle(
            sentinel2_packages=[_S2Pkg()],
            sensor_context_package=_SensorPkg(),
        )),
        ("Sensor-only", _bundle(
            sensor_context_package=_SensorPkg(),
        )),
        ("Satellite-only", _bundle(
            sentinel2_packages=[_S2Pkg()],
        )),
        ("Multi-scene", _bundle(
            sentinel2_packages=[
                _S2Pkg(),
                _S2Pkg(metadata=_S2Meta(scene_id="S2A_OLD",
                       acquisition_datetime=_TS - timedelta(days=8))),
            ],
            sensor_context_package=_SensorPkg(),
        )),
        ("Stale-data", _bundle(
            sentinel2_packages=[_S2Pkg(
                metadata=_S2Meta(acquisition_datetime=_TS - timedelta(days=14)))],
        )),
        ("Empty-plot", _bundle()),
        ("Zone-aware", _bundle(
            sentinel2_packages=[_S2Pkg(zone_summaries=[
                _S2ZoneSummary(zone_id="z_n", ndvi_mean=0.8),
                _S2ZoneSummary(zone_id="z_s", ndvi_mean=0.4),
            ])],
            sensor_context_package=_SensorPkg(),
        )),
        ("Forecast-heavy", _bundle(
            weather_forecast_package=_ForecastPkg(
                forecast_process_forcing=[
                    _FPF(date=f"day_{i}", precipitation_mm=2.0 * i)
                    for i in range(5)
                ]
            ),
        )),
        ("WSR-enriched", _bundle(
            sentinel2_packages=[_S2Pkg(zone_summaries=[
                _S2ZoneSummary(zone_id="z1", ndvi_mean=0.6),
                _S2ZoneSummary(zone_id="z2", ndvi_mean=0.4),
            ])],
            layer0_state_package={
                "zone_summaries": [
                    {"zone_id": "z1", "label": "healthy", "area_fraction": 0.7},
                    {"zone_id": "z2", "label": "weak", "area_fraction": 0.3},
                ]
            },
        )),
        ("Edge-contaminated", _bundle(
            layer0_state_package={
                "edge_contamination": [
                    {"edge_id": "edge_e", "contamination_score": 0.85},
                ]
            },
        )),
    ]


# ============================================================================
# Gate runner
# ============================================================================

def run_gate() -> bool:
    """Run the production gate. Returns True if all checks pass."""
    engine = Layer1FusionEngine()
    scenarios = _build_scenarios()
    results = []
    all_pass = True

    for name, bundle in scenarios:
        t0 = time.perf_counter()
        pkg = engine.fuse(bundle)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        # Check prohibitions
        prohib_pass = sum(1 for v in pkg.diagnostics.hard_prohibition_results.values() if v)
        prohib_total = len(pkg.diagnostics.hard_prohibition_results)
        has_evidence = len(pkg.evidence_items) > 0

        # Data-bearing scenarios: all prohibitions must pass
        # Degraded (zero-evidence) scenarios: health must correctly report degraded/unusable
        if has_evidence:
            prohib_ok = prohib_pass == prohib_total
        else:
            prohib_ok = pkg.diagnostics.data_health.status in ("degraded", "unusable")

        # Check invariants
        error_violations = [
            v for v in pkg.provenance.invariant_violations
            if v.get("severity") == "error"
        ]
        invariants_ok = len(error_violations) == 0

        # Performance
        perf_ok = elapsed_ms < 1000

        scenario_pass = prohib_ok and invariants_ok and perf_ok
        if not scenario_pass:
            all_pass = False

        results.append({
            "name": name,
            "evidence": len(pkg.evidence_items),
            "fused": sum(len(g) for g in [
                pkg.fused_features.water_context,
                pkg.fused_features.vegetation_context,
                pkg.fused_features.phenology_context,
                pkg.fused_features.stress_evidence_context,
                pkg.fused_features.soil_site_context,
                pkg.fused_features.operational_context,
                pkg.fused_features.data_quality_context,
            ]),
            "conflicts": len(pkg.conflicts),
            "gaps": len(pkg.gaps),
            "health": pkg.diagnostics.data_health.overall,
            "status": pkg.diagnostics.data_health.status,
            "prohib": f"{prohib_pass}/{prohib_total}",
            "invariants": len(pkg.provenance.invariant_violations),
            "inv_errors": len(error_violations),
            "audit": len(pkg.audit_log),
            "spatial_fid": pkg.diagnostics.data_health.spatial_fidelity,
            "prov_compl": pkg.diagnostics.data_health.provenance_completeness,
            "hash": pkg.content_hash()[:12],
            "ms": round(elapsed_ms, 1),
            "pass": "PASS" if scenario_pass else "FAIL",
            "prohibition_matrix": dict(pkg.diagnostics.hard_prohibition_results),
        })

    # Print report
    print("\n" + "=" * 130)
    print("LAYER 1 PRODUCTION GATE REPORT")
    print("=" * 130)
    print(f"{'Scenario':<20} {'Evid':>5} {'Fused':>5} {'Conf':>5} "
          f"{'Gaps':>5} {'Health':>6} {'Status':<10} "
          f"{'Prohib':<7} {'Inv':>4} {'SpFi':>5} {'PrCo':>5} "
          f"{'Hash':<14} {'ms':>6} {'Result':<6}")
    print("-" * 130)
    for r in results:
        print(f"{r['name']:<20} {r['evidence']:>5} {r['fused']:>5} "
              f"{r['conflicts']:>5} {r['gaps']:>5} {r['health']:>6.3f} "
              f"{r['status']:<10} {r['prohib']:<7} {r['invariants']:>4} "
              f"{r['spatial_fid']:>5.2f} {r['prov_compl']:>5.2f} "
              f"{r['hash']:<14} {r['ms']:>6.1f} {r['pass']:<6}")
    print("=" * 130)

    gate_status = "PASSED" if all_pass else "FAILED"
    print(f"\nGATE STATUS: {gate_status}")
    print(f"Scenarios: {len(results)}, "
          f"Passed: {sum(1 for r in results if r['pass'] == 'PASS')}, "
          f"Failed: {sum(1 for r in results if r['pass'] == 'FAIL')}")

    # Emit JSON report for reproducibility and CI
    _emit_json_report(results, all_pass)

    return all_pass


def _emit_json_report(results: List[Dict], gate_passed: bool) -> None:
    """Write a structured JSON gate report to artifacts/."""
    import json
    import subprocess
    import re
    from pathlib import Path

    report = {
        "timestamp": time.time(),
        "engine_version": "layer1_fusion_v1",
        "contract_version": "1.0.0",
        "gate_passed": gate_passed,
        "scenario_count": len(results),
        "passed_count": sum(1 for r in results if r["pass"] == "PASS"),
        "failed_count": sum(1 for r in results if r["pass"] == "FAIL"),
        "scenarios": results,
    }

    # Cross-layer test metrics (run pytest --co -q for counts)
    try:
        here = Path(__file__).resolve().parent.parent
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "layer0/", "layer1_fusion/",
             "--co", "-q", "--no-header"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(here), timeout=30,
        )
        match = re.search(r"(\d+) tests? collected", proc.stdout)
        if match:
            report["cross_layer_test_count"] = int(match.group(1))
        else:
            report["cross_layer_test_count"] = 0

        # Per-layer counts
        for layer_name, layer_path in [("layer0", "layer0/"), ("layer1", "layer1_fusion/")]:
            proc2 = subprocess.run(
                [sys.executable, "-m", "pytest", layer_path,
                 "--co", "-q", "--no-header"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                cwd=str(here), timeout=30,
            )
            match2 = re.search(r"(\d+) tests? collected", proc2.stdout)
            report[f"{layer_name}_test_count"] = int(match2.group(1)) if match2 else 0
    except Exception:
        report["cross_layer_test_count"] = -1

    # Write to artifacts/
    try:
        artifacts_dir = Path(__file__).resolve().parent.parent / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        report_path = artifacts_dir / "l1_production_gate_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\nJSON report saved to: {report_path}")
    except Exception as e:
        print(f"\n⚠️ Failed to save JSON report: {e}")


if __name__ == "__main__":
    success = run_gate()
    sys.exit(0 if success else 1)

