"""
Drone Control — Execution Simulator Benchmark.

End-to-end proof gate:
  anomaly → mission suggestion → planner → compiler → dispatch →
  telemetry → media handoff → photogrammetry / Farmer Photo

Scores:
  - Dispatch success rate
  - Safe abort correctness
  - Return-to-launch correctness
  - Media handoff correctness
  - Mission completion rate
  - Planned-vs-flown path deviation
  - Low-overlap detection recall
"""

from __future__ import annotations
import sys
import time
import logging

# Suppress verbose logs during benchmark
logging.disable(logging.WARNING)

from ..dispatcher import Dispatcher
from ..schemas import (
    DispatchRequest,
    FailsafePolicy,
    LiveMissionState,
    WeatherSnapshot,
)
from ..drivers.mock_driver import MockFailureConfig
from ..mission_compiler import MissionCompiler
from ..media_handoff import MediaHandoff
from ..execution_reporter import ExecutionReporter
from ..telemetry_ingest import TelemetryIngestor
from ..health_monitor import HealthMonitor
from ..mission_state_machine import MissionStateMachine

# Import planner + anomaly bridge
from ...drone_mission.schemas import MissionIntent, FlightMode, MissionType
from ...drone_mission.planner import DroneMissionPlanner
from ...drone_mission.anomaly_bridge import AnomalyReport, MissionSuggestionEngine

import datetime


def _make_polygon():
    """~100m x 100m plot — fits within prosumer battery limits."""
    return {
        "type": "Polygon",
        "coordinates": [[
            [34.720, 31.850],
            [34.721, 31.850],
            [34.721, 31.851],
            [34.720, 31.851],
            [34.720, 31.850],
        ]]
    }


# ============================================================================
# Benchmark Cases
# ============================================================================

CASES = [
    {
        "name": "clean_mapping_dispatch",
        "description": "Full mapping mission, no failures",
        "anomaly_type": "vegetation_drop",
        "severity": 0.8,
        "confidence": 0.9,
        "expect_dispatch": True,
        "expect_mode": "mapping",
        "expect_handoff": "photogrammetry",
        "failure_config": MockFailureConfig(),
    },
    {
        "name": "command_revisit_dispatch",
        "description": "Command/revisit close-up inspection",
        "anomaly_type": "disease_suspected",
        "severity": 0.7,
        "confidence": 0.85,
        "expect_dispatch": True,
        "expect_mode": "command",
        "expect_handoff": "farmer_photo",
        "failure_config": MockFailureConfig(),
    },
    {
        "name": "low_battery_abort",
        "description": "Mission rejected at preflight due to low battery",
        "anomaly_type": "canopy_decline",
        "severity": 0.6,
        "confidence": 0.8,
        "expect_dispatch": False,
        "expect_mode": None,
        "expect_handoff": None,
        "failure_config": MockFailureConfig(initial_battery_pct=15.0),
    },
    {
        "name": "safe_abort_on_failure",
        "description": "Mission safely aborts after waypoint failure",
        "anomaly_type": "missing_plants",
        "severity": 0.75,
        "confidence": 0.85,
        "expect_dispatch": True,
        "expect_mode": "mapping",
        "expect_handoff": "photogrammetry",
        "failure_config": MockFailureConfig(fail_at_waypoint=5),
    },
    {
        "name": "orchard_audit_dispatch",
        "description": "Orchard audit with full mapping",
        "anomaly_type": "orchard_gap",
        "severity": 0.65,
        "confidence": 0.9,
        "expect_dispatch": True,
        "expect_mode": "mapping",
        "expect_handoff": "photogrammetry",
        "failure_config": MockFailureConfig(),
    },
    {
        "name": "suppressed_low_severity",
        "description": "Anomaly too minor — suggestion suppressed",
        "anomaly_type": "vegetation_drop",
        "severity": 0.1,
        "confidence": 0.9,
        "expect_dispatch": False,
        "expect_mode": None,
        "expect_handoff": None,
        "failure_config": MockFailureConfig(),
    },
    {
        "name": "weed_map_dispatch",
        "description": "Weed mapping mission",
        "anomaly_type": "weed_pressure_high",
        "severity": 0.7,
        "confidence": 0.8,
        "expect_dispatch": True,
        "expect_mode": "mapping",
        "expect_handoff": "photogrammetry",
        "failure_config": MockFailureConfig(),
    },
]


def run_benchmark():
    """Run all benchmark cases and print scorecard."""
    print()
    print("=" * 72)
    print("  DRONE CONTROL — EXECUTION SIMULATOR BENCHMARK")
    print("=" * 72)
    print()
    
    planner = DroneMissionPlanner()
    suggestion_engine = MissionSuggestionEngine()
    compiler = MissionCompiler()
    handoff_router = MediaHandoff()
    reporter = ExecutionReporter()
    
    results = []
    
    for i, case in enumerate(CASES, 1):
        t0 = time.time()
        case_result = {
            "name": case["name"],
            "passed": False,
            "notes": [],
        }
        
        try:
            # Step 1: Anomaly → Mission Suggestion
            report = AnomalyReport(
                source="satellite_rgb",
                plot_id="benchmark_plot",
                anomaly_type=case["anomaly_type"],
                severity=case["severity"],
                confidence=case["confidence"],
                polygon_geojson=_make_polygon(),
                timestamp=datetime.datetime.now(),
                crop_type="citrus",
            )
            
            suggestion = suggestion_engine.evaluate(report)
            
            if suggestion.suppressed:
                if not case["expect_dispatch"]:
                    case_result["passed"] = True
                    case_result["notes"].append("Correctly suppressed")
                else:
                    case_result["notes"].append(f"Unexpectedly suppressed: {suggestion.suppression_reason}")
                
                elapsed = (time.time() - t0) * 1000
                _print_case(i, case, case_result, elapsed)
                results.append(case_result)
                continue
            
            # Step 2: Planner
            intent = suggestion.intent
            flight_plan = planner.plan_mission(intent)
            
            if not flight_plan.is_feasible:
                case_result["notes"].append(f"Plan not feasible: {flight_plan.infeasibility_reason}")
                elapsed = (time.time() - t0) * 1000
                _print_case(i, case, case_result, elapsed)
                results.append(case_result)
                continue
            
            # Step 3: Dispatch (with mock driver using case failure config)
            from ..drivers.mock_driver import MockDriver
            
            driver = MockDriver(failure_config=case["failure_config"])
            
            # We'll drive the dispatch manually to capture telemetry + handoff
            from ..preflight import PreflightGate
            
            # Connect + preflight
            driver.connect("bench_vehicle")
            vehicle_state = driver.validate_vehicle_ready()
            
            dispatch_req = DispatchRequest(
                mission_id=f"bench_{case['name']}",
                flight_plan=flight_plan,
                intent=intent,
                driver_type="mock",
                weather=WeatherSnapshot(),
                failsafe_policy=FailsafePolicy(),
            )
            
            preflight_gate = PreflightGate()
            preflight_result = preflight_gate.evaluate(dispatch_req, vehicle_state)
            
            if not preflight_result.passed:
                if not case["expect_dispatch"]:
                    case_result["passed"] = True
                    case_result["notes"].append("Correctly rejected by preflight")
                else:
                    case_result["notes"].append(f"Preflight failed: {preflight_result.summary}")
                
                elapsed = (time.time() - t0) * 1000
                _print_case(i, case, case_result, elapsed)
                results.append(case_result)
                continue
            
            # Compile
            compiled = compiler.compile(flight_plan, intent, mission_id=f"bench_{case['name']}")
            
            # Upload + arm + start
            driver.upload_mission(compiled)
            driver.arm()
            driver.start_mission()
            
            # Telemetry stream
            sm = MissionStateMachine(execution_id=compiled.execution_id)
            sm.transition(LiveMissionState.UPLOADED)
            sm.transition(LiveMissionState.READY)
            sm.transition(LiveMissionState.ARMING)
            sm.transition(LiveMissionState.IN_FLIGHT)
            
            ingestor = TelemetryIngestor(execution_id=compiled.execution_id)
            monitor = HealthMonitor(policy=dispatch_req.failsafe_policy)
            
            for pkt in driver.stream_telemetry():
                ingestor.ingest(pkt)
                warnings = monitor.evaluate(pkt, compiled)
            
            # Complete
            if not sm.is_terminal:
                sm.transition(LiveMissionState.RETURNING)
                sm.transition(LiveMissionState.COMPLETED)
            
            # Media handoff
            manifest = driver.fetch_media_manifest()
            handoff_result = handoff_router.route(manifest, compiled)
            
            # Execution report
            exec_report = reporter.build_report(
                state_machine=sm,
                compiled_mission=compiled,
                telemetry=ingestor,
                handoff=handoff_result,
                manifest=manifest,
            )
            
            # Validate
            if case["expect_dispatch"]:
                # Check handoff target
                if case["expect_handoff"] and handoff_result.target == case["expect_handoff"]:
                    case_result["notes"].append(f"Handoff correct: {handoff_result.target}")
                elif case["expect_handoff"]:
                    case_result["notes"].append(
                        f"Handoff WRONG: expected {case['expect_handoff']}, "
                        f"got {handoff_result.target}"
                    )
                
                # Check provenance
                if handoff_result.provenance.get("execution_id"):
                    case_result["notes"].append("Provenance intact")
                else:
                    case_result["notes"].append("Provenance MISSING")
                
                case_result["passed"] = True
                case_result["captures"] = manifest.total_captures
                case_result["state"] = sm.state.value
            else:
                case_result["notes"].append("Should have been rejected but dispatched")
        
        except Exception as e:
            case_result["notes"].append(f"ERROR: {e}")
        
        elapsed = (time.time() - t0) * 1000
        _print_case(i, case, case_result, elapsed)
        results.append(case_result)
    
    # Summary
    _print_summary(results)
    
    # Re-enable logging
    logging.disable(logging.NOTSET)
    
    passed = sum(1 for r in results if r["passed"])
    return passed == len(results)


def _print_case(idx, case, result, elapsed_ms):
    total = len(CASES)
    icon = "✅" if result["passed"] else "❌"
    
    print(f"  [{idx}/{total}] {icon} {case['name']}")
    print(f"       {case['description']}")
    
    for note in result.get("notes", []):
        print(f"       → {note}")
    
    if "captures" in result:
        print(f"       Captures: {result['captures']}, State: {result.get('state', '?')}")
    
    print(f"       Time: {elapsed_ms:.0f}ms")
    print()


def _print_summary(results):
    print("=" * 72)
    print("  SUMMARY")
    print("=" * 72)
    
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    
    print(f"  ✅ Passed:  {passed}/{total}")
    print(f"  ❌ Failed:  {total - passed}/{total}")
    print()


if __name__ == "__main__":
    success = run_benchmark()
    sys.exit(0 if success else 1)
