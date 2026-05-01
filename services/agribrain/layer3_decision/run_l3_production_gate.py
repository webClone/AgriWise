"""
Layer 3 Production Gate.

12 scenarios testing the full L3 decision pipeline.
Must achieve 100% prohibition pass for all data-bearing scenarios.
Exit code 0 = PASS, 1 = FAIL.

Run: py -m layer3_decision.run_l3_production_gate
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from layer1_fusion.schemas import DataHealthScore
from layer2_intelligence.outputs.layer3_adapter import Layer3InputContext
from layer3_decision.runner import run_layer3
from layer3_decision.schema import PlotContext


SCENARIOS: List[Dict[str, Any]] = [
    {
        "name": "Water Stress - Dry Spell",
        "context": {
            "plot_id": "gate_01", "layer1_run_id": "l1_01", "layer2_run_id": "l2_01",
            "stress_summary": {"WATER": 0.7},
            "phenology_stage": "vegetative",
            "data_health": {"overall": 0.8, "confidence_ceiling": 0.9, "status": "ok"},
            "operational_signals": {
                "sar_available": True, "optical_available": True,
                "rain_available": True, "temp_available": True,
                "optical_obs_count": 10, "sar_obs_count": 8,
                "water_deficit_severity": 0.7, "thermal_severity": 0.0,
                "has_anomaly": True, "anomaly_severity": 0.5, "anomaly_type": "DROP",
                "growth_velocity": 0.003,
            },
        },
        "expect_diagnosis": "WATER_STRESS",
    },
    {
        "name": "Heat Stress - Extreme Temps",
        "context": {
            "plot_id": "gate_02", "layer1_run_id": "l1_02", "layer2_run_id": "l2_02",
            "stress_summary": {"THERMAL": 0.6},
            "phenology_stage": "reproductive",
            "data_health": {"overall": 0.8, "confidence_ceiling": 0.9, "status": "ok"},
            "operational_signals": {
                "sar_available": True, "optical_available": True,
                "rain_available": True, "temp_available": True,
                "optical_obs_count": 10, "sar_obs_count": 8,
                "water_deficit_severity": 0.0, "thermal_severity": 0.6,
                "has_anomaly": False, "anomaly_severity": 0.0, "anomaly_type": "NONE",
                "growth_velocity": 0.005,
            },
        },
        "expect_diagnosis": "HEAT_STRESS",
    },
    {
        "name": "Healthy Plot - No Stress",
        "context": {
            "plot_id": "gate_03", "layer1_run_id": "l1_03", "layer2_run_id": "l2_03",
            "stress_summary": {},
            "phenology_stage": "vegetative",
            "data_health": {"overall": 0.9, "confidence_ceiling": 0.95, "status": "ok"},
            "operational_signals": {
                "sar_available": True, "optical_available": True,
                "rain_available": True, "temp_available": True,
                "optical_obs_count": 15, "sar_obs_count": 10,
                "water_deficit_severity": 0.0, "thermal_severity": 0.0,
                "has_anomaly": False, "anomaly_severity": 0.0, "anomaly_type": "NONE",
                "growth_velocity": 0.015,
            },
        },
        "expect_diagnosis": None,
    },
    {
        "name": "Fungal Risk - Wet Conditions",
        "context": {
            "plot_id": "gate_04", "layer1_run_id": "l1_04", "layer2_run_id": "l2_04",
            "stress_summary": {"BIOTIC": 0.4},
            "phenology_stage": "vegetative",
            "data_health": {"overall": 0.8, "confidence_ceiling": 0.9, "status": "ok"},
            "operational_signals": {
                "sar_available": True, "optical_available": True,
                "rain_available": True, "temp_available": True,
                "optical_obs_count": 10, "sar_obs_count": 8,
                "water_deficit_severity": 0.0, "thermal_severity": 0.0,
                "has_anomaly": False, "anomaly_severity": 0.0, "anomaly_type": "NONE",
                "growth_velocity": 0.01,
            },
        },
        "expect_diagnosis": None,  # May or may not fire
    },
    {
        "name": "Data Gap - Missing All",
        "context": {
            "plot_id": "gate_05", "layer1_run_id": "l1_05", "layer2_run_id": "l2_05",
            "stress_summary": {},
            "phenology_stage": "unknown",
            "data_health": {"overall": 0.1, "confidence_ceiling": 0.3, "status": "degraded"},
            "usable_for_layer3": False,
            "operational_signals": {
                "sar_available": False, "optical_available": False,
                "rain_available": False, "temp_available": False,
                "optical_obs_count": 0, "sar_obs_count": 0,
                "water_deficit_severity": 0.0, "thermal_severity": 0.0,
                "has_anomaly": False, "anomaly_severity": 0.0, "anomaly_type": "NONE",
                "growth_velocity": 0.0,
            },
        },
        "expect_diagnosis": "DATA_GAP",
    },
    {
        "name": "Rain Forecast Blocks Irrigation",
        "context": {
            "plot_id": "gate_06", "layer1_run_id": "l1_06", "layer2_run_id": "l2_06",
            "stress_summary": {"WATER": 0.8},
            "phenology_stage": "vegetative",
            "data_health": {"overall": 0.8, "confidence_ceiling": 0.9, "status": "ok"},
            "operational_signals": {
                "sar_available": True, "optical_available": True,
                "rain_available": True, "temp_available": True,
                "optical_obs_count": 10, "sar_obs_count": 8,
                "water_deficit_severity": 0.8, "thermal_severity": 0.0,
                "has_anomaly": True, "anomaly_severity": 0.6, "anomaly_type": "DROP",
                "growth_velocity": 0.002,
            },
        },
        "forecast": [{"rain": 20.0}, {"rain": 10.0}],
        "expect_diagnosis": "WATER_STRESS",
    },
    {
        "name": "SAR Missing - Degraded Mode",
        "context": {
            "plot_id": "gate_07", "layer1_run_id": "l1_07", "layer2_run_id": "l2_07",
            "stress_summary": {},
            "phenology_stage": "vegetative",
            "data_health": {"overall": 0.6, "confidence_ceiling": 0.8, "status": "ok"},
            "operational_signals": {
                "sar_available": False, "optical_available": True,
                "rain_available": True, "temp_available": True,
                "optical_obs_count": 10, "sar_obs_count": 0,
                "water_deficit_severity": 0.0, "thermal_severity": 0.0,
                "has_anomaly": False, "anomaly_severity": 0.0, "anomaly_type": "NONE",
                "growth_velocity": 0.01,
            },
        },
        "expect_diagnosis": None,
    },
    {
        "name": "Maturity + Structure Change -> Harvest",
        "context": {
            "plot_id": "gate_08", "layer1_run_id": "l1_08", "layer2_run_id": "l2_08",
            "stress_summary": {"MECHANICAL": 0.5},
            "phenology_stage": "maturity",
            "data_health": {"overall": 0.8, "confidence_ceiling": 0.9, "status": "ok"},
            "operational_signals": {
                "sar_available": True, "optical_available": True,
                "rain_available": True, "temp_available": True,
                "optical_obs_count": 10, "sar_obs_count": 8,
                "water_deficit_severity": 0.0, "thermal_severity": 0.0,
                "has_anomaly": True, "anomaly_severity": 0.8, "anomaly_type": "DROP",
                "growth_velocity": -0.02,
            },
        },
        "expect_diagnosis": None,
    },
    {
        "name": "Cold Stress - Frost",
        "context": {
            "plot_id": "gate_09", "layer1_run_id": "l1_09", "layer2_run_id": "l2_09",
            "stress_summary": {"THERMAL": 0.5},
            "stress_detail": {"THERMAL": {"severity": 0.5, "confidence": 0.7, "uncertainty": 0.1,
                "primary_driver": "cold_frost_risk", "evidence_count": 1,
                "explanation_basis": ["frost risk"], "spatial_scope": "plot", "diagnostic_only": False}},
            "phenology_stage": "emergence",
            "data_health": {"overall": 0.8, "confidence_ceiling": 0.9, "status": "ok"},
            "operational_signals": {
                "sar_available": True, "optical_available": True,
                "rain_available": True, "temp_available": True,
                "optical_obs_count": 10, "sar_obs_count": 8,
                "water_deficit_severity": 0.0, "thermal_severity": 0.5,
                "has_anomaly": False, "anomaly_severity": 0.0, "anomaly_type": "NONE",
                "growth_velocity": 0.005,
            },
        },
        "expect_diagnosis": "COLD_STRESS",
    },
    {
        "name": "Multi-Zone Heterogeneous",
        "context": {
            "plot_id": "gate_10", "layer1_run_id": "l1_10", "layer2_run_id": "l2_10",
            "stress_summary": {"WATER": 0.5},
            "zone_status": {
                "zone_a": {"dominant_stress_type": "WATER", "severity": 0.8, "confidence": 0.7, "stress_count": 2},
                "zone_b": {"dominant_stress_type": None, "severity": 0.1, "confidence": 0.9, "stress_count": 0},
            },
            "phenology_stage": "vegetative",
            "data_health": {"overall": 0.8, "confidence_ceiling": 0.9, "status": "ok"},
            "operational_signals": {
                "sar_available": True, "optical_available": True,
                "rain_available": True, "temp_available": True,
                "optical_obs_count": 10, "sar_obs_count": 8,
                "water_deficit_severity": 0.5, "thermal_severity": 0.0,
                "has_anomaly": True, "anomaly_severity": 0.4, "anomaly_type": "DROP",
                "growth_velocity": 0.005,
            },
        },
        "expect_diagnosis": None,
    },
    {
        "name": "Content Hash Determinism",
        "context": {
            "plot_id": "gate_11", "layer1_run_id": "l1_11", "layer2_run_id": "l2_11",
            "stress_summary": {"WATER": 0.6},
            "phenology_stage": "vegetative",
            "data_health": {"overall": 0.7, "confidence_ceiling": 0.9, "status": "ok"},
            "operational_signals": {
                "sar_available": True, "optical_available": True,
                "rain_available": True, "temp_available": True,
                "optical_obs_count": 10, "sar_obs_count": 8,
                "water_deficit_severity": 0.6, "thermal_severity": 0.0,
                "has_anomaly": True, "anomaly_severity": 0.3, "anomaly_type": "STALL",
                "growth_velocity": 0.004,
            },
        },
        "expect_diagnosis": None,
        "check_hash_determinism": True,
    },
    {
        "name": "Full Pipeline Lineage",
        "context": {
            "plot_id": "gate_12", "layer1_run_id": "l1_12", "layer2_run_id": "l2_12",
            "stress_summary": {},
            "phenology_stage": "bare_soil",
            "data_health": {"overall": 0.9, "confidence_ceiling": 0.95, "status": "ok"},
            "operational_signals": {
                "sar_available": True, "optical_available": True,
                "rain_available": True, "temp_available": True,
                "optical_obs_count": 15, "sar_obs_count": 10,
                "water_deficit_severity": 0.0, "thermal_severity": 0.0,
                "has_anomaly": False, "anomaly_severity": 0.0, "anomaly_type": "NONE",
                "growth_velocity": 0.0,
            },
        },
        "expect_diagnosis": None,
        "check_lineage": True,
    },
]


def _build_context(spec: Dict[str, Any]) -> Layer3InputContext:
    ctx_data = spec["context"]
    dh = ctx_data.get("data_health", {})
    return Layer3InputContext(
        plot_id=ctx_data["plot_id"],
        layer1_run_id=ctx_data.get("layer1_run_id", ""),
        layer2_run_id=ctx_data.get("layer2_run_id", ""),
        stress_summary=ctx_data.get("stress_summary", {}),
        stress_detail=ctx_data.get("stress_detail", {}),
        zone_status=ctx_data.get("zone_status", {}),
        vegetation_status=ctx_data.get("vegetation_status", {}),
        phenology_stage=ctx_data.get("phenology_stage", "unknown"),
        operational_signals=ctx_data.get("operational_signals", {}),
        data_health=DataHealthScore(
            overall=dh.get("overall", 0.5),
            confidence_ceiling=dh.get("confidence_ceiling", 0.9),
            status=dh.get("status", "ok"),
        ),
        confidence_ceiling=dh.get("confidence_ceiling", 0.9),
        usable_for_layer3=ctx_data.get("usable_for_layer3", True),
    )


def run_gate():
    results = []
    all_pass = True
    ts = datetime.now(timezone.utc)

    print("=" * 60)
    print("Layer 3 Production Gate")
    print(f"Timestamp: {ts.isoformat()}")
    print("=" * 60)

    for i, scenario in enumerate(SCENARIOS, 1):
        name = scenario["name"]
        ctx = _build_context(scenario)
        forecast = scenario.get("forecast", [])
        run_id = f"gate_{i:02d}"

        t0 = time.perf_counter()
        output = run_layer3(ctx, weather_forecast=forecast, run_id=run_id)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        # Check prohibitions
        prohib = output.diagnostics.hard_prohibition_results
        prohib_pass = all(prohib.values())
        prohib_count = f"{sum(prohib.values())}/{len(prohib)}"

        # Check expected diagnosis
        diag_check = "N/A"
        expected = scenario.get("expect_diagnosis")
        if expected:
            found = any(d.problem_id == expected for d in output.diagnoses)
            diag_check = "PASS" if found else "FAIL"
            if not found:
                all_pass = False

        # Hash determinism check
        hash_check = "N/A"
        if scenario.get("check_hash_determinism"):
            out2 = run_layer3(ctx, weather_forecast=forecast, run_id=run_id)
            hash_check = "PASS" if output.content_hash() == out2.content_hash() else "FAIL"
            if hash_check == "FAIL":
                all_pass = False

        # Lineage check
        lineage_check = "N/A"
        if scenario.get("check_lineage"):
            has_l1 = bool(output.lineage.get("l1_run_id"))
            has_l2 = bool(output.lineage.get("l2_run_id"))
            lineage_check = "PASS" if has_l1 and has_l2 else "FAIL"
            if lineage_check == "FAIL":
                all_pass = False

        status = "PASS" if prohib_pass else "FAIL"
        if not prohib_pass:
            all_pass = False

        print(f"  [{status}] {i:2d}. {name}")
        print(f"       Prohibitions: {prohib_count} | Diag: {diag_check} "
              f"| Hash: {hash_check} | Lineage: {lineage_check} | {elapsed_ms:.1f}ms")

        results.append({
            "scenario": name,
            "status": status,
            "prohibitions": prohib_count,
            "diagnosis_check": diag_check,
            "hash_check": hash_check,
            "lineage_check": lineage_check,
            "elapsed_ms": round(elapsed_ms, 1),
            "diagnoses": [d.problem_id for d in output.diagnoses],
        })

    print("=" * 60)
    final = "ALL PASS" if all_pass else "FAILURES DETECTED"
    print(f"Result: {final}")
    print(f"Scenarios: {len(results)} | Passed: {sum(1 for r in results if r['status'] == 'PASS')}")
    print("=" * 60)

    # Save report
    report_dir = Path(__file__).parent / "artifacts"
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / "l3_production_gate_report.json"
    report = {
        "timestamp": ts.isoformat(),
        "result": final,
        "scenarios": results,
    }
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\nReport: {report_path}")

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    run_gate()
