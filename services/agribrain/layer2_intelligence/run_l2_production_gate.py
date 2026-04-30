"""
Layer 2 Production Gate — run_l2_production_gate.py

8 calibration scenarios exercising the full L2 intelligence pipeline.
Outputs a deterministic JSON report mirroring the L1 gate pattern.

Usage:
    py -m layer2_intelligence.run_l2_production_gate
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from layer1_fusion.schemas import (
    CropCycleContext,
    DataHealthScore,
    EvidenceConflict,
    EvidenceGap,
    Layer2InputContext,
    SpatialIndex,
    ZoneRef,
)

from layer2_intelligence.engine import Layer2IntelligenceEngine
from layer2_intelligence.schemas import Layer2Output


_TS = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


# ============================================================================
# Scenario definitions
# ============================================================================

def _ctx(
    name, plot_id="gate_plot",
    water=None, veg=None, stress=None,
    operational=None, soil=None,
    conflicts=None, gaps=None,
    data_health=None, spatial_index=None,
    crop_context=None,
) -> tuple:
    ctx = Layer2InputContext(
        plot_id=plot_id,
        crop_context=crop_context,
        water_context=water or {},
        vegetation_context=veg or {},
        stress_evidence_context=stress or {},
        operational_context=operational or {},
        soil_site_context=soil or {},
        conflicts=conflicts or [],
        gaps=gaps or [],
        provenance_ref="l1_gate_run",
        spatial_index_ref=spatial_index,
        data_health=data_health or DataHealthScore(
            overall=0.7, confidence_ceiling=0.85, status="ok",
            source_completeness=0.8, provenance_completeness=1.0,
            freshness=0.9, spatial_fidelity=0.5,
        ),
    )
    return name, ctx


def _build_scenarios() -> List[tuple]:
    scenarios = []

    # 1. Full-stack: water stress + thermal + vegetation
    scenarios.append(_ctx("Full-stack",
        water={
            "ndmi_mean": {"value": 0.12, "confidence": 0.7, "source_weights": {"s2": 0.8}},
            "soil_moisture_vwc": {"value": 0.14, "confidence": 0.6, "source_weights": {"iot": 0.9}},
        },
        veg={
            "ndvi_mean": {"value": 0.42, "confidence": 0.7, "source_weights": {"s2": 0.8}},
            "vegetation_fraction_scl": {"value": 0.6, "confidence": 0.7, "source_weights": {}},
        },
        stress={
            "temp_max": {"value": 38.0, "confidence": 0.8, "source_weights": {"env": 0.9}},
            "vpd": {"value": 2.8, "confidence": 0.6, "source_weights": {}},
        },
        operational={"precipitation_mm": {"value": 1.5, "confidence": 0.8, "source_weights": {}}},
    ))

    # 2. Healthy plot: no stress
    scenarios.append(_ctx("Healthy-plot",
        water={
            "ndmi_mean": {"value": 0.45, "confidence": 0.8, "source_weights": {}},
            "soil_moisture_vwc": {"value": 0.35, "confidence": 0.7, "source_weights": {}},
        },
        veg={
            "ndvi_mean": {"value": 0.75, "confidence": 0.8, "source_weights": {}},
            "vegetation_fraction_scl": {"value": 0.88, "confidence": 0.7, "source_weights": {}},
        },
        stress={"temp_max": {"value": 26.0, "confidence": 0.8, "source_weights": {}}},
    ))

    # 3. Nutrient stress: low NDVI + adequate water
    scenarios.append(_ctx("Nutrient-stress",
        water={
            "ndmi_mean": {"value": 0.40, "confidence": 0.7, "source_weights": {}},
            "soil_moisture_vwc": {"value": 0.30, "confidence": 0.6, "source_weights": {}},
        },
        veg={
            "ndvi_mean": {"value": 0.28, "confidence": 0.7, "source_weights": {}},
            "evi_mean": {"value": 0.20, "confidence": 0.6, "source_weights": {}},
        },
    ))

    # 4. Conflict-heavy
    scenarios.append(_ctx("Conflict-heavy",
        water={"ndmi_mean": {"value": 0.15, "confidence": 0.5, "source_weights": {}}},
        veg={"ndvi_mean": {"value": 0.40, "confidence": 0.5, "source_weights": {}}},
        conflicts=[
            EvidenceConflict(conflict_id="c1", conflict_type="SENSOR_VS_S2", variable_group="water",
                             spatial_scope="plot", severity="major"),
            EvidenceConflict(conflict_id="c2", conflict_type="S2_VPD_MISMATCH", variable_group="stress",
                             spatial_scope="plot", severity="moderate"),
        ],
    ))

    # 5. Low data health
    scenarios.append(_ctx("Low-health",
        water={"ndmi_mean": {"value": 0.18, "confidence": 0.3, "source_weights": {}}},
        veg={"ndvi_mean": {"value": 0.35, "confidence": 0.3, "source_weights": {}}},
        data_health=DataHealthScore(overall=0.15, confidence_ceiling=0.4, status="degraded"),
    ))

    # 6. Zone-aware (2 zones with different stress)
    scenarios.append(_ctx("Zone-aware",
        water={
            "ndmi_mean": {"value": 0.35, "confidence": 0.7, "source_weights": {}},
            "ndmi_z1": {"value": 0.42, "confidence": 0.7, "scope_id": "z1", "source_weights": {}},
            "ndmi_z2": {"value": 0.10, "confidence": 0.7, "scope_id": "z2", "source_weights": {}},
        },
        veg={
            "ndvi_mean": {"value": 0.55, "confidence": 0.7, "source_weights": {}},
            "ndvi_z1": {"value": 0.65, "confidence": 0.7, "scope_id": "z1", "source_weights": {}},
            "ndvi_z2": {"value": 0.30, "confidence": 0.7, "scope_id": "z2", "source_weights": {}},
        },
        spatial_index=SpatialIndex(plot_id="gate_plot", zones=[
            ZoneRef(zone_id="z1"), ZoneRef(zone_id="z2"),
        ]),
    ))

    # 7. Phenology-adjusted (flowering stage)
    scenarios.append(_ctx("Phenology-adjusted",
        water={
            "ndmi_mean": {"value": 0.15, "confidence": 0.7, "source_weights": {}},
            "soil_moisture_vwc": {"value": 0.16, "confidence": 0.6, "source_weights": {}},
        },
        veg={"ndvi_mean": {"value": 0.50, "confidence": 0.7, "source_weights": {}}},
        crop_context=CropCycleContext(current_stage="reproductive", gdd_accumulated=1200),
    ))

    # 8. Empty context (degraded gracefully)
    scenarios.append(_ctx("Empty-context",
        data_health=DataHealthScore(overall=0.3, confidence_ceiling=0.5, status="degraded"),
    ))

    # 9. Multi-stress co-occurrence (water + thermal)
    scenarios.append(_ctx("Multi-stress",
        water={
            "ndmi_mean": {"value": 0.08, "confidence": 0.7, "source_weights": {}},
            "soil_moisture_vwc": {"value": 0.09, "confidence": 0.6, "source_weights": {}},
        },
        veg={"ndvi_mean": {"value": 0.28, "confidence": 0.7, "source_weights": {}}},
        stress={
            "temp_max": {"value": 41.0, "confidence": 0.8, "source_weights": {}},
            "vpd": {"value": 3.8, "confidence": 0.7, "source_weights": {}},
        },
        operational={"precipitation_mm": {"value": 0.0, "confidence": 0.8, "source_weights": {}}},
    ))

    # 10. Borderline threshold (NDMI=0.20 exactly → no water stress)
    scenarios.append(_ctx("Borderline-NDMI",
        water={"ndmi_mean": {"value": 0.20, "confidence": 0.7, "source_weights": {}}},
        veg={"ndvi_mean": {"value": 0.55, "confidence": 0.7, "source_weights": {}}},
    ))

    # 11. Deep senescence (reduced stress sensitivity)
    scenarios.append(_ctx("Senescence",
        water={"ndmi_mean": {"value": 0.15, "confidence": 0.7, "source_weights": {}}},
        veg={"ndvi_mean": {"value": 0.30, "confidence": 0.7, "source_weights": {}}},
        stress={"temp_max": {"value": 38.0, "confidence": 0.8, "source_weights": {}}},
        crop_context=CropCycleContext(current_stage="senescence", gdd_accumulated=2500),
    ))

    # 12. Conflicting zone data (z1 wet, z2 dry)
    scenarios.append(_ctx("Zone-conflict",
        water={
            "ndmi_mean": {"value": 0.30, "confidence": 0.7, "source_weights": {}},
            "ndmi_z1": {"value": 0.50, "confidence": 0.7, "scope_id": "z1", "source_weights": {}},
            "ndmi_z2": {"value": 0.06, "confidence": 0.7, "scope_id": "z2", "source_weights": {}},
        },
        veg={
            "ndvi_mean": {"value": 0.50, "confidence": 0.7, "source_weights": {}},
            "ndvi_z1": {"value": 0.68, "confidence": 0.7, "scope_id": "z1", "source_weights": {}},
            "ndvi_z2": {"value": 0.22, "confidence": 0.7, "scope_id": "z2", "source_weights": {}},
        },
        spatial_index=SpatialIndex(plot_id="gate_plot", zones=[
            ZoneRef(zone_id="z1"), ZoneRef(zone_id="z2"),
        ]),
    ))

    return scenarios


# ============================================================================
# Gate runner
# ============================================================================

def _run_gate():
    engine = Layer2IntelligenceEngine()
    scenarios = _build_scenarios()
    results = []
    all_pass = True

    print()
    print("=" * 120)
    print("LAYER 2 PRODUCTION GATE REPORT")
    print("=" * 120)
    print(f"{'Scenario':<22} {'Stress':>6} {'Veg':>5} {'Pheno':>6} {'Zones':>6} "
          f"{'Health':>7} {'Status':<10} {'Prohib':>8} {'Inv':>4} "
          f"{'Hash':<14} {'ms':>6} {'Result':<6}")
    print("-" * 120)

    for name, ctx in scenarios:
        import time
        t0 = time.perf_counter()
        pkg = engine.analyze(ctx, run_id=f"gate_{name.lower().replace('-', '_')}", run_timestamp=_TS)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        # Prohibition check
        prohib_results = pkg.diagnostics.hard_prohibition_results
        prohib_pass = sum(1 for v in prohib_results.values() if v)
        prohib_total = len(prohib_results)

        # Invariant violations
        inv_count = len(pkg.provenance.invariant_violations)
        inv_errors = sum(1 for v in pkg.provenance.invariant_violations if v.get("severity") == "error")

        # Pass/fail — strict: 100% prohibition pass for data-bearing scenarios
        has_data = len(pkg.stress_context) > 0 or len(pkg.vegetation_intelligence) > 0
        if has_data:
            scenario_pass = (prohib_pass == prohib_total and inv_errors == 0)
        else:
            scenario_pass = (prohib_pass >= prohib_total - 1 and inv_errors == 0)
        if not scenario_pass:
            all_pass = False

        content_hash = pkg.content_hash()[:12]

        result_str = "PASS" if scenario_pass else "FAIL"
        print(f"{name:<22} {len(pkg.stress_context):>6} {len(pkg.vegetation_intelligence):>5} "
              f"{len(pkg.phenology_adjusted_indices):>6} {len(pkg.zone_stress_map):>6} "
              f"{pkg.data_health.overall:>7.3f} {pkg.diagnostics.status:<10} "
              f"{prohib_pass}/{prohib_total:>3}   {inv_count:>4} "
              f"{content_hash:<14} {elapsed_ms:>6.1f} {result_str:<6}")

        results.append({
            "name": name,
            "stress_count": len(pkg.stress_context),
            "veg_count": len(pkg.vegetation_intelligence),
            "pheno_count": len(pkg.phenology_adjusted_indices),
            "zone_count": len(pkg.zone_stress_map),
            "health_overall": round(pkg.data_health.overall, 3),
            "status": pkg.diagnostics.status,
            "prohibition_pass": prohib_pass,
            "prohibition_total": prohib_total,
            "prohibition_matrix": prohib_results,
            "invariant_violations": inv_count,
            "invariant_errors": inv_errors,
            "hash": content_hash,
            "elapsed_ms": round(elapsed_ms, 1),
            "result": result_str,
            "stress_types": sorted(set(s.stress_type for s in pkg.stress_context)),
        })

    print("=" * 120)
    print()
    print(f"GATE STATUS: {'PASSED' if all_pass else 'FAILED'}")
    print(f"Scenarios: {len(results)}, Passed: {sum(1 for r in results if r['result'] == 'PASS')}, "
          f"Failed: {sum(1 for r in results if r['result'] == 'FAIL')}")

    # Count cross-layer tests
    l0_count = _count_tests("layer0")
    l1_count = _count_tests("layer1_fusion")
    l2_count = _count_tests("layer2_intelligence")
    cross_total = l0_count + l1_count + l2_count

    # JSON report
    report = {
        "gate_passed": all_pass,
        "engine_version": engine.ENGINE_VERSION,
        "contract_version": engine.CONTRACT_VERSION,
        "timestamp": _TS.isoformat(),
        "scenario_count": len(results),
        "pass_count": sum(1 for r in results if r["result"] == "PASS"),
        "fail_count": sum(1 for r in results if r["result"] == "FAIL"),
        "layer0_test_count": l0_count,
        "layer1_test_count": l1_count,
        "layer2_test_count": l2_count,
        "cross_layer_test_count": cross_total,
        "scenarios": results,
    }

    artifacts_dir = Path(__file__).resolve().parent.parent / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    report_path = artifacts_dir / "l2_production_gate_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\nJSON report saved to: {report_path}")


def _count_tests(package: str) -> int:
    """Count tests in a package using pytest --collect-only."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", package, "--collect-only", "-q"],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            # Match: "59 tests collected" or "1083 selected"
            if ("test" in line and ("selected" in line or "collected" in line)):
                parts = line.split()
                if parts and parts[0].isdigit():
                    return int(parts[0])
        return 0
    except Exception:
        return 0


if __name__ == "__main__":
    _run_gate()
    # Exit with code for CI integration
    import json
    from pathlib import Path
    report_path = Path(__file__).resolve().parent.parent / "artifacts" / "l2_production_gate_report.json"
    if report_path.exists():
        with open(report_path) as f:
            report = json.load(f)
        sys.exit(0 if report.get("gate_passed") else 1)
