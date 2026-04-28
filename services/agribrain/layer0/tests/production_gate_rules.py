"""
Production gate hard no-go rules.

Evaluates a production_gate_report.json and returns gate_passed = True
only if ALL conditions are met. No human interpretation needed.
"""
import json
from pathlib import Path
from typing import Dict, Any, List


REQUIRED_FIELDS = [
    "package_reproducibility_ok",
    "fixture_governance_ok",
    "sentinel2_engine_ok",
    "sentinel2_tests",
    "sentinel1_engine_ok",
    "sentinel1_tests",
    "environment_engine_ok",
    "environment_tests",
    "weather_forecast_engine_ok",
    "weather_forecast_tests",
    "geo_context_engine_ok",
    "geo_context_tests",
    "satellite_rgb_ok",
    "farmer_photo_ok",
    "drone_rgb_ok",
    "sensor_runtime_ok",
    "sensor_runtime_tests",
    "sensor_engine_ok",
    "sensor_engine_tests",
    "sensor_hard_prohibitions",
    "sensor_scope_rules_ok",
    "sensor_calibration_rules_ok",
    "sensor_health_rules_ok",
    "sensor_no_live_network_tests",
    "sensor_normalization_rules_ok",
    "sensor_canonical_variables_ok",
    "sensor_test_padding_removed",
    "sensor_diagnostic_scope_separated",
    "sensor_irrigation_forcing_ok",
    # Layer 1 Fusion
    "layer1_fusion_ok",
    "layer1_fusion_tests",
    "layer1_hard_prohibitions",
    "gate_passed",
]

REQUIRED_SUITE_NAMES = [
    "Sentinel-2 Tests",
    "Sentinel-1 SAR Tests",
    "Environment Tests",
    "Environment Forecast Tests",
    "Geo Context Tests",
    "Unit & Integration Tests",
    "Fixture Governance",
    "Satellite RGB Benchmark",
    "Farmer Photo Benchmark",
    "Drone RGB Benchmark",
    "Sensor Runtime Tests",
    "Layer 0 Sensor Tests",
    "Layer 1 Fusion Tests",
]


def evaluate_gate_rules(report: Dict[str, Any]) -> Dict[str, Any]:
    """Apply hard no-go rules to a production gate report.

    Returns a dict with:
      - gate_passed: bool
      - violations: list of strings describing each violation
    """
    violations: List[str] = []

    # Rule 1: All required fields must be present
    for field in REQUIRED_FIELDS:
        if field not in report:
            violations.append(f"Missing required field: {field}")

    # Rule 2: Archive reproducibility (pytest) must pass
    if not report.get("package_reproducibility_ok", False):
        violations.append("Archive reproducibility (pytest) failed")

    # Rule 3: Fixture governance must pass
    if not report.get("fixture_governance_ok", False):
        violations.append("Fixture governance verification failed")

    # Rule 4: Sentinel-2 Tests must pass
    if not report.get("sentinel2_engine_ok", False):
        violations.append("Sentinel-2 Engine tests failed")
    s2_tests = report.get("sentinel2_tests", {})
    if s2_tests.get("failed", 0) > 0:
        violations.append(f"Sentinel-2 test failures: {s2_tests['failed']}")
    if s2_tests.get("passed", 0) < 89:
        violations.append(f"Insufficient Sentinel-2 tests: {s2_tests.get('passed', 0)} < 89")

    # Rule 5: Sentinel-1 SAR Tests must pass
    if not report.get("sentinel1_engine_ok", False):
        violations.append("Sentinel-1 SAR Engine tests failed")
    s1_tests = report.get("sentinel1_tests", {})
    if s1_tests.get("failed", 0) > 0:
        violations.append(f"Sentinel-1 test failures: {s1_tests['failed']}")
    if s1_tests.get("passed", 0) < 95:
        violations.append(f"Insufficient Sentinel-1 tests: {s1_tests.get('passed', 0)} < 95")

    # Rule 5b: Environment Tests must pass
    if not report.get("environment_engine_ok", False):
        violations.append("Environment Engine tests failed")
    env_tests = report.get("environment_tests", {})
    if env_tests.get("failed", 0) > 0:
        violations.append(f"Environment test failures: {env_tests['failed']}")
    if env_tests.get("passed", 0) < 130:
        violations.append(f"Insufficient Environment tests: {env_tests.get('passed', 0)} < 130")

    # Rule 5c: Environment Forecast Tests must pass
    if not report.get("weather_forecast_engine_ok", False):
        violations.append("Weather Forecast Engine tests failed")
    forecast_tests = report.get("weather_forecast_tests", {})
    if forecast_tests.get("failed", 0) > 0:
        violations.append(f"Forecast test failures: {forecast_tests['failed']}")
    if forecast_tests.get("passed", 0) < 120:
        violations.append(f"Insufficient Forecast tests: {forecast_tests.get('passed', 0)} < 120")

    # Rule 5d: Forecast hard prohibitions
    prohibs = report.get("forecast_hard_prohibitions", {})
    for key in ["no_current_kalman_update", "no_canopy_stress_from_wind",
                "no_forecast_historical_mixing", "wind_direction_circular",
                "horizon_cap_enforced"]:
        if not prohibs.get(key, False):
            violations.append(f"Forecast hard prohibition violated: {key}")

    # Rule 5e: Geo Context Tests must pass
    if not report.get("geo_context_engine_ok", False):
        violations.append("Geo Context Engine tests failed")
    geo_tests = report.get("geo_context_tests", {})
    if geo_tests.get("failed", 0) > 0:
        violations.append(f"Geo Context test failures: {geo_tests['failed']}")
    if geo_tests.get("passed", 0) < 90:
        violations.append(f"Insufficient Geo Context tests: {geo_tests.get('passed', 0)} < 90")

    # Rule 5f: Geo Context hard prohibitions
    geo_prohibs = report.get("geo_context_hard_prohibitions", {})
    for key in ["no_direct_kalman_updates", "dem_not_soil_moisture_truth",
                "landcover_not_crop_health", "wapor_not_plot_truth",
                "dynamic_world_not_crop_health", "sensor_placement_not_state_update"]:
        if not geo_prohibs.get(key, False):
            violations.append(f"Geo Context hard prohibition violated: {key}")

    # Rule 6: All engine benchmarks must pass
    for engine_field in ["satellite_rgb_ok", "farmer_photo_ok", "drone_rgb_ok"]:
        if not report.get(engine_field, False):
            violations.append(f"Engine benchmark failed: {engine_field}")

    # Rule 6b: Sensor Rules
    if not report.get("sensor_runtime_ok", False):
        violations.append("Sensor Runtime Engine tests failed")
    sr_tests = report.get("sensor_runtime_tests", {})
    if sr_tests.get("failed", 0) > 0:
        violations.append(f"Sensor Runtime test failures: {sr_tests['failed']}")
    if sr_tests.get("passed", 0) < 90:
        violations.append(f"Insufficient Sensor Runtime tests: {sr_tests.get('passed', 0)} < 90")

    if not report.get("sensor_engine_ok", False):
        violations.append("Layer 0 Sensor Engine tests failed")
    le_tests = report.get("sensor_engine_tests", {})
    if le_tests.get("failed", 0) > 0:
        violations.append(f"Layer 0 Sensor test failures: {le_tests['failed']}")
    if le_tests.get("passed", 0) < 80:
        violations.append(f"Insufficient Layer 0 Sensor tests: {le_tests.get('passed', 0)} < 80")

    sensor_prohibs = report.get("sensor_hard_prohibitions", {})
    for key in [
        "uncalibrated_sensor_no_high_trust",
        "unknown_placement_no_plot_wide_update",
        "edge_sensor_no_plot_wide_update",
        "wet_lowspot_sensor_not_plot_mean",
        "flatline_sensor_no_kalman",
        "spike_sensor_degraded_or_rejected",
        "bad_battery_degrades_reliability",
        "bad_signal_degrades_reliability",
        "wind_no_direct_canopy_stress",
        "leaf_wetness_no_direct_disease_diagnosis",
        "forecast_not_sensor_truth",
        "irrigation_flow_not_soil_moisture_without_response",
        "point_sensor_scope_respected"
    ]:
        if not sensor_prohibs.get(key, False):
            violations.append(f"Sensor hard prohibition violated: {key}")

    for sub_rule in [
        "sensor_scope_rules_ok", "sensor_calibration_rules_ok",
        "sensor_health_rules_ok", "sensor_no_live_network_tests",
        "sensor_normalization_rules_ok", "sensor_canonical_variables_ok",
        "sensor_test_padding_removed", "sensor_diagnostic_scope_separated",
        "sensor_irrigation_forcing_ok",
    ]:
        if not report.get(sub_rule, False):
            violations.append(f"Sensor sub-rule violated: {sub_rule}")

    # Rule 6c: Layer 1 Fusion Rules
    if not report.get("layer1_fusion_ok", False):
        violations.append("Layer 1 Fusion Engine tests failed")
    l1_tests = report.get("layer1_fusion_tests", {})
    if l1_tests.get("failed", 0) > 0:
        violations.append(f"Layer 1 Fusion test failures: {l1_tests['failed']}")
    if l1_tests.get("passed", 0) < 150:
        violations.append(f"Insufficient Layer 1 Fusion tests: {l1_tests.get('passed', 0)} < 150")

    l1_prohibs = report.get("layer1_hard_prohibitions", {})
    for key in [
        "no_fake_fallback_evidence",
        "no_diagnosis_or_recommendation",
        "no_forecast_as_observation",
        "no_point_sensor_to_plot_truth_without_scope",
        "no_geo_context_as_crop_state",
        "no_weather_as_crop_diagnosis",
        "no_wapor_as_plot_truth",
        "no_unprovenanced_fused_feature",
        "no_conflict_suppression",
        "no_unit_mismatch_allowed",
        "no_spatial_scope_collapse",
        "no_temporal_leakage_future_to_present",
        "no_simulated_data_in_user_facing_context",
    ]:
        if not l1_prohibs.get(key, False):
            violations.append(f"Layer 1 hard prohibition violated: {key}")

    # Rule 7: No critical case failures
    if report.get("critical_case_failures", 0) > 0:
        violations.append(
            f"Critical case failures: {report['critical_case_failures']}"
        )

    # Rule 6: No aggregate metric failures
    if report.get("aggregate_metric_failures", 0) > 0:
        violations.append(
            f"Aggregate metric failures: {report['aggregate_metric_failures']}"
        )

    # Rule 7: No required suite skipped
    skipped = report.get("skipped_required_suites", [])
    if skipped:
        violations.append(f"Required suites skipped: {skipped}")

    # Rule 8: Cross-check executed steps against required suites
    steps = report.get("steps", [])
    executed_names = {s.get("step", "") for s in steps}
    for suite_name in REQUIRED_SUITE_NAMES:
        if suite_name not in executed_names:
            violations.append(f"Required suite not executed: {suite_name}")

    # Rule 9: Benchmark verdicts must be present and valid
    verdicts = report.get("benchmark_verdicts", {})
    for bench_name in ["Satellite RGB Benchmark", "Farmer Photo Benchmark", "Drone RGB Benchmark"]:
        v = verdicts.get(bench_name)
        if not v:
            violations.append(f"Missing benchmark verdict: {bench_name}")
        elif not v.get("valid", False):
            violations.append(f"Invalid benchmark artifact: {bench_name} - {v.get('errors', [])}")
        else:
            data = v.get("data", {})
            # Rule 10: gate_passed in verdict must be consistent with failure counts
            agg = data.get("aggregate_failures", 0)
            crit = data.get("critical_failures", 0)
            expected_pass = (agg == 0 and crit == 0)
            if data.get("gate_passed") != expected_pass:
                violations.append(
                    f"Benchmark verdict contradiction in {bench_name}: "
                    f"gate_passed={data.get('gate_passed')}, "
                    f"aggregate_failures={agg}, critical_failures={crit}"
                )

    gate_passed = len(violations) == 0
    return {
        "gate_passed": gate_passed,
        "violations": violations,
    }


def verify_report_file(report_path: Path) -> bool:
    """Load a report JSON and evaluate it. Returns True if gate passes."""
    with open(report_path, "r") as f:
        report = json.load(f)
    result = evaluate_gate_rules(report)
    if result["gate_passed"]:
        print("[PASS] Production gate rules satisfied.")
    else:
        print("[FAIL] Production gate rule violations:")
        for v in result["violations"]:
            print(f"  - {v}")
    return result["gate_passed"]
