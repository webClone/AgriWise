"""
IP Camera Benchmark Runner — scored regression suite.

Feeds 9 test scenarios through the real engine and validates:
  - Expected output variables (values within tolerance)
  - Expected QA flags
  - Expected validation checks
  - Expected reliability_weight ranges
"""

from layer0.perception.ip_camera.benchmark.cases import BENCHMARK_CASES
from layer0.perception.ip_camera.engine import IPCameraEngine
from layer0.perception.ip_camera.schemas import IPCameraEngineInput


def generate_mock_input(case_name: str) -> IPCameraEngineInput:
    """Generate specific test payloads for each scenario."""
    mock_stats = {
        "mean_brightness": 120.0,
        "sharpness": 50.0,
        "green_fraction": 0.6,
        "yellow_fraction": 0.05,
        "shift_x": 0.0,
        "shift_y": 0.0,
        "phenology_stage_est": 2.0,
    }
    weather_context = {}
    satellite_context = {}

    if case_name == "phenology_progression":
        mock_stats["phenology_stage_est"] = 2.5
        weather_context["gdd_stage"] = 2.5
    elif case_name == "heat_stress_visual":
        mock_stats["yellow_fraction"] = 0.6
        weather_context["max_temp_c"] = 38.0
    elif case_name == "rain_recovery":
        mock_stats["yellow_fraction"] = 0.1
        weather_context["recent_rain_mm"] = 15.0
    elif case_name == "satellite_cloud_false_positive":
        mock_stats["green_fraction"] = 0.9
        satellite_context["recent_ndvi_drop"] = 0.4
    elif case_name == "camera_framing_shift":
        mock_stats["shift_x"] = 25.0
    elif case_name == "low_bandwidth_compression":
        mock_stats["sharpness"] = 15.0
    elif case_name == "sun_angle_shadow_drift":
        mock_stats["mean_brightness"] = 190.0

    return IPCameraEngineInput(
        camera_id="cam_bench_01",
        weather_context=weather_context,
        satellite_context=satellite_context,
        metadata={"mock_frame_stats": mock_stats},
    )


def run_benchmarks():
    """
    Execute all benchmark cases and validate outputs.
    Returns True only if all cases pass.
    """
    engine = IPCameraEngine()
    print(f"Running {len(BENCHMARK_CASES)} IP Camera benchmark cases...")

    passed = 0

    for case in BENCHMARK_CASES:
        print(f"\n--- {case.case_name} ---")
        inp = generate_mock_input(case.case_name)
        output = engine.process(inp)

        case_pass = True

        # --- QA flags ---
        expected_qa = case.expected_qa_failures or []
        for eqa in expected_qa:
            if eqa not in output.qa_flags:
                print(f"  [FAIL] Missing QA flag: {eqa}. Got: {output.qa_flags}")
                case_pass = False

        # --- Validation checks ---
        validations = [v.check_name for v in output.validation_checks]
        expected_vals = case.expected_validations or []
        for ev in expected_vals:
            if ev not in validations:
                print(f"  [FAIL] Missing validation: {ev}. Got: {validations}")
                case_pass = False

        # --- Output variables ---
        if case.expected_outputs:
            for k, v in case.expected_outputs.items():
                if k == "scene_change_type":
                    if output.scene_context and output.scene_context.scene_change_type.value != v:
                        print(f"  [FAIL] scene_change_type: expected {v}, got {output.scene_context.scene_change_type.value}")
                        case_pass = False
                else:
                    var = next((x for x in output.variables if x.name == k), None)
                    if var is None:
                        # May be suppressed by QA — check if that's expected
                        if not expected_qa:
                            print(f"  [FAIL] Variable {k} not found")
                            case_pass = False
                    elif isinstance(v, float) and abs(var.value - v) > 0.15:
                        print(f"  [FAIL] {k}: expected ~{v}, got {var.value}")
                        case_pass = False

        # --- Reliability weight range ---
        if expected_qa and len(expected_qa) > 0:
            if output.reliability_weight > 0.7:
                print(f"  [FAIL] reliability_weight should be degraded, got {output.reliability_weight}")
                case_pass = False

        if case_pass:
            print(f"  [PASS] qa_score={output.qa_score:.2f} reliability={output.reliability_weight:.2f}")
            passed += 1

    print(f"\nResult: {passed}/{len(BENCHMARK_CASES)} Passed.")
    return passed == len(BENCHMARK_CASES)


if __name__ == "__main__":
    success = run_benchmarks()
    import sys
    sys.exit(0 if success else 1)
