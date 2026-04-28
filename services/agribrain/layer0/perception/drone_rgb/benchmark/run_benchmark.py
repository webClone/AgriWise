"""
Drone V1 Competitive Benchmark.

Evaluates:
1. Track B Perception Accuracy (Row azimuth, gap fraction, weed pressure)
2. Mission Execution Quality (Geometric coverage, waste, overlap)
3. QA Robustness (Blur, partial coverage, shadow handling)
"""

import sys

from layer0.perception.drone_rgb.engine import DroneRGBEngine
from layer0.perception.drone_rgb.schemas import DroneRGBInput
from drone_mission.schemas import MissionIntent, FlightMode
from drone_mission.planner import DroneMissionPlanner
from drone_mission.coverage_patterns import compute_execution_quality
from drone_mission.capability_profiles import get_profile
from layer0.perception.drone_rgb.benchmark.cases import BENCHMARK_CASES, _generate_synthetic_ortho
from layer0.perception.common.benchmark_contract import (
    BenchmarkGateResult, finalize, result_to_dict,
    exit_code_from_result, summarize_failures,
)

# ============================================================================
# Pass/Fail Thresholds
# ============================================================================
THRESHOLDS = {
    # Perception
    "row_azimuth_mae_deg": 5.0,       # Target <= 5.0 deg
    "weed_pressure_mae": 0.05,         # Target <= 0.05
    # V1.5 Perception
    "row_break_count_mae": 5,          # Target <= 5
    "tree_count_mae": 5,               # Target <= 5
    "missing_tree_mae": 3,             # Target <= 3
    "canopy_uniformity_ae": 0.3,       # Target <= 0.3
    # Execution
    "coverage_completeness": 0.80,     # Target >= 80%
    "outside_waste": 0.55,             # Target <= 55% (includes irregular polygon stress cases)
    "overlap_compliance": 0.50,        # Target >= 50%
    # QA Gating
    "qa_partial_rejects": False,       # Partial strip should NOT be rejected (degraded ok)
    "qa_blur_rejects": True,           # Heavy blur MUST be rejected
}


def _pass_fail(value: float, threshold: float, higher_is_better: bool) -> str:
    if higher_is_better:
        return "[PASS]" if value >= threshold else "[FAIL]"
    else:
        return "[PASS]" if value <= threshold else "[FAIL]"


def run_benchmark():
    engine = DroneRGBEngine()
    planner = DroneMissionPlanner()
    profile = get_profile("standard_prosumer")
    
    print("=" * 60)
    print(" DRONE V1 COMPETITIVE BENCHMARK (TRACK B + EXECUTION)")
    print("=" * 60)
    
    row_errors = []
    weed_errors = []
    coverage_scores = []
    waste_scores = []
    overlap_scores = []
    
    # V1.5 metrics
    row_break_errors = []
    tree_count_errors = []
    missing_tree_errors = []
    canopy_cv_errors = []
    
    for case in BENCHMARK_CASES:
        print(f"\n[{case.case_id}] {case.description}")
        
        # 1. Mission Execution Quality (Planner)
        intent = MissionIntent(
            intent_id=f"bench_intent_{case.case_id}",
            plot_id="bench_plot",
            mission_type=case.mission_type,
            flight_mode=case.flight_mode,
            polygon_geojson=case.polygon_geojson,
            target_gsd_cm=case.target_gsd_cm
        )
        
        plan = planner.plan_mission(intent)
        
        # 2. Real Geometric Execution Quality
        # Compute camera footprint from profile at planned altitude
        footprint_w, footprint_h = profile.calculate_footprint(plan.flight_altitude_m)
        polygon_coords = case.polygon_geojson.get("coordinates", [[]])[0]
        
        eq = compute_execution_quality(
            polygon_coords=polygon_coords,
            waypoints=plan.waypoints,
            footprint_w_m=footprint_w,
            footprint_h_m=footprint_h,
            required_overlap_pct=intent.required_overlap_pct,
            sample_density=100,
        )
        
        print(f"  Execution: Feasible={plan.is_feasible}, Waypoints={len(plan.waypoints)}, "
              f"Est. Time={plan.estimated_flight_time_min:.1f}m")
        if case.flight_mode == FlightMode.MAPPING_MODE:
            print(f"  Execution: Coverage={eq.coverage_completeness:.0%}, "
                  f"Waste={eq.outside_polygon_waste:.0%}, "
                  f"Overlap={eq.overlap_compliance:.0%}")
        else:
            print(f"  Execution: Coverage={eq.coverage_completeness:.0%}, "
                  f"Waste={eq.outside_polygon_waste:.0%}, "
                  f"Overlap={eq.overlap_compliance:.0%}  "
                  f"(not scored — command/orbit mission)")
              
        if plan.is_feasible and case.flight_mode == FlightMode.MAPPING_MODE:
            coverage_scores.append(eq.coverage_completeness)
            waste_scores.append(eq.outside_polygon_waste)
            overlap_scores.append(eq.overlap_compliance)
              
        if not plan.is_feasible:
            print(f"  Reason: {plan.infeasibility_reason}")
            continue # Skip perception if mission isn't feasible
            
        # 3. Perception Quality (Layer 0 Engine)
        pixels = _generate_synthetic_ortho(case)
        
        inp = DroneRGBInput(
            plot_id="bench_plot",
            mission_id=plan.plan_id,
            flight_mode=case.flight_mode,
            mission_type=case.mission_type,
            synthetic_ortho_pixels=pixels if case.flight_mode == "mapping_mode" else None,
            synthetic_frame_pixels=[pixels] if case.flight_mode == "command_revisit" else None
        )
        
        result = engine.process_full(inp)
        if not result:
            print("  Engine returned None")
            continue
            
        out, packets = result
        
        # QA-focused cases: print diagnostics
        if case.case_id.startswith("qa_"):
            print(f"  QA: Valid={out.is_valid}, Score={out.qa_score:.2f}")
            if out.rejection_reason:
                print(f"  QA: Rejected — {out.rejection_reason}")
            if not out.is_valid:
                continue
        
        if not out.is_valid:
            continue
            
        if out.row_azimuth_deg is not None:
            print(f"  Perception: Row Azimuth={out.row_azimuth_deg:.1f} (GT: {case.gt_row_azimuth_deg})")
            print(f"  Perception: Weed Index={out.weed_pressure_index:.2f} (GT: {case.gt_weed_pressure})")
            print(f"  Packets emitted: {len(packets)}")
            
            if case.gt_row_azimuth_deg is not None and out.row_azimuth_deg is not None:
                # Handle circular angle difference (0-180)
                diff = abs(case.gt_row_azimuth_deg - out.row_azimuth_deg)
                diff = min(diff, 180 - diff)
                row_errors.append(diff)
                
            if case.gt_weed_pressure is not None and out.weed_pressure_index is not None:
                weed_errors.append(abs(case.gt_weed_pressure - out.weed_pressure_index))
        
        else:
            print(f"  Command Mode: Routed {out.routed_frame_count} frames to Farmer Photo")
            print(f"  Packets emitted (from Farmer Photo): {len(packets)}")
        
        # V1.5 Diagnostics
        if out.row_count > 0:
            print(f"  V1.5: Rows={out.row_count}, Breaks={len(out.row_breaks)}, "
                  f"Continuity Mean={sum(out.row_continuity_scores)/max(1,len(out.row_continuity_scores)):.2f}")
            if case.gt_row_break_count is not None:
                row_break_errors.append(abs(case.gt_row_break_count - len(out.row_breaks)))
        
        if out.in_row_weed_fraction > 0 or out.inter_row_weed_fraction > 0:
            print(f"  V1.5: In-Row Weed={out.in_row_weed_fraction:.3f}, "
                  f"Inter-Row Weed={out.inter_row_weed_fraction:.3f}")
        
        if out.tree_count > 0:
            print(f"  V1.5: Trees={out.tree_count}, Missing={out.missing_tree_count}, "
                  f"CV={out.canopy_uniformity_cv:.2f}")
            if case.gt_tree_count is not None:
                tree_count_errors.append(abs(case.gt_tree_count - out.tree_count))
            if case.gt_missing_tree_count is not None:
                missing_tree_errors.append(abs(case.gt_missing_tree_count - out.missing_tree_count))
            if case.gt_canopy_uniformity_cv is not None:
                canopy_cv_errors.append(abs(case.gt_canopy_uniformity_cv - out.canopy_uniformity_cv))
            
    # ====================================================================
    # Scorecard with Pass/Fail Thresholds
    # ====================================================================
    print("\n" + "=" * 60)
    print(" SCORECARD")
    print("=" * 60)
    
    # Perception
    if row_errors:
        mae_row = sum(row_errors) / len(row_errors)
        pf = _pass_fail(mae_row, THRESHOLDS["row_azimuth_mae_deg"], higher_is_better=False)
        print(f"  {pf} [Perception] Row Azimuth MAE:   {mae_row:.1f} deg  "
              f"(Target <= {THRESHOLDS['row_azimuth_mae_deg']} deg)")
    if weed_errors:
        mae_weed = sum(weed_errors) / len(weed_errors)
        pf = _pass_fail(mae_weed, THRESHOLDS["weed_pressure_mae"], higher_is_better=False)
        print(f"  {pf} [Perception] Weed Pressure MAE: {mae_weed:.3f}      "
              f"(Target <= {THRESHOLDS['weed_pressure_mae']})")
    
    # V1.5 Perception
    if row_break_errors:
        mae_rb = sum(row_break_errors) / len(row_break_errors)
        pf = _pass_fail(mae_rb, THRESHOLDS["row_break_count_mae"], higher_is_better=False)
        print(f"  {pf} [V1.5 Perc.] Row Break MAE:     {mae_rb:.1f}        "
              f"(Target <= {THRESHOLDS['row_break_count_mae']})")
    if tree_count_errors:
        mae_tc = sum(tree_count_errors) / len(tree_count_errors)
        pf = _pass_fail(mae_tc, THRESHOLDS["tree_count_mae"], higher_is_better=False)
        print(f"  {pf} [V1.5 Perc.] Tree Count MAE:    {mae_tc:.1f}        "
              f"(Target <= {THRESHOLDS['tree_count_mae']})")
    if missing_tree_errors:
        mae_mt = sum(missing_tree_errors) / len(missing_tree_errors)
        pf = _pass_fail(mae_mt, THRESHOLDS["missing_tree_mae"], higher_is_better=False)
        print(f"  {pf} [V1.5 Perc.] Missing Tree MAE:  {mae_mt:.1f}        "
              f"(Target <= {THRESHOLDS['missing_tree_mae']})")
    if canopy_cv_errors:
        mae_cv = sum(canopy_cv_errors) / len(canopy_cv_errors)
        pf = _pass_fail(mae_cv, THRESHOLDS["canopy_uniformity_ae"], higher_is_better=False)
        print(f"  {pf} [V1.5 Perc.] Canopy Uniform. AE:{mae_cv:.2f}        "
              f"(Target <= {THRESHOLDS['canopy_uniformity_ae']})")
        
    # Execution (averaged over feasible mapping cases)
    if coverage_scores:
        avg_cov = sum(coverage_scores) / len(coverage_scores)
        pf = _pass_fail(avg_cov, THRESHOLDS["coverage_completeness"], higher_is_better=True)
        print(f"  {pf} [Execution]  Coverage Complete: {avg_cov:.0%}      "
              f"(Target >= {THRESHOLDS['coverage_completeness']:.0%})")
    if waste_scores:
        avg_waste = sum(waste_scores) / len(waste_scores)
        pf = _pass_fail(avg_waste, THRESHOLDS["outside_waste"], higher_is_better=False)
        print(f"  {pf} [Execution]  Outside Waste:     {avg_waste:.0%}      "
              f"(Target <= {THRESHOLDS['outside_waste']:.0%})")
    if overlap_scores:
        avg_overlap = sum(overlap_scores) / len(overlap_scores)
        pf = _pass_fail(avg_overlap, THRESHOLDS["overlap_compliance"], higher_is_better=True)
        print(f"  {pf} [Execution]  Overlap Compliance:{avg_overlap:.0%}      "
              f"(Target >= {THRESHOLDS['overlap_compliance']:.0%})")

    print("\n" + "=" * 60)

    # --- Aggregate metric enforcement via shared contract ---
    import json, os
    gate = BenchmarkGateResult(engine="drone_rgb")

    metric_checks = [
        ("row_azimuth_mae", row_errors, THRESHOLDS["row_azimuth_mae_deg"], False),
        ("weed_pressure_mae", weed_errors, THRESHOLDS["weed_pressure_mae"], False),
        ("coverage_completeness", coverage_scores, THRESHOLDS["coverage_completeness"], True),
        ("outside_waste", waste_scores, THRESHOLDS["outside_waste"], False),
        ("overlap_compliance", overlap_scores, THRESHOLDS["overlap_compliance"], True),
    ]

    for name, values, threshold, higher_better in metric_checks:
        if not values:
            continue
        avg = sum(values) / len(values)
        if higher_better:
            passed = avg >= threshold
        else:
            passed = avg <= threshold
        gate.scorecard[name] = {"value": round(avg, 4), "threshold": threshold, "passed": passed}
        if not passed:
            gate.aggregate_failures += 1
            gate.failing_metrics.append(name)

    gate = finalize(gate)

    # Save gate artifact
    out_dir = os.path.dirname(os.path.abspath(__file__))
    gate_dict = result_to_dict(gate)
    gate_path = os.path.join(out_dir, "benchmark_gate_result.json")
    with open(gate_path, "w") as f:
        json.dump(gate_dict, f, indent=2)
    print(f"\n  Gate artifact saved to: {gate_path}")

    return gate


if __name__ == "__main__":
    gate_result = run_benchmark()
    print(f"\n{summarize_failures(gate_result)}")
    sys.exit(exit_code_from_result(gate_result))
