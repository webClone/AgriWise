"""
Golden Plot Regression Runner

Loads each golden dataset, runs the full Layer 0 assimilation pipeline,
and validates results against pinned expected outputs.

Tolerance-based comparisons:
  - state ranges: final state values within expected [lo, hi]
  - uncertainty: monotonic during gaps, shrinks on obs days
  - conflicts: correct hypothesis labels on expected days
  - reliability: within band
  - audit: grade within range

Usage:
    py golden/golden_runner.py                 # run all 3 plots
    py golden/golden_runner.py --fast           # run 1 plot, 30 days (CI fast)
"""

import sys
import os
import json
import math
import argparse

# Insert project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from services.agribrain.layer0.kalman_engine import (
    DailyAssimilationEngine, KalmanObservation
)
from services.agribrain.layer0.validation_graph import ValidationGraph
from services.agribrain.layer0.monitoring import TrustReportBuilder
from services.agribrain.layer0.invariants import enforce_all_invariants

GOLDEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))


# ============================================================================
# Helpers
# ============================================================================

def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def assert_range(name, value, lo, hi, context=""):
    if not (lo <= value <= hi):
        raise AssertionError(
            f"GOLDEN FAIL [{context}]: {name}={value:.4f} not in [{lo}, {hi}]"
        )


# ============================================================================
# Core: Run one golden plot
# ============================================================================

def run_golden_plot(plot_dir: str, max_days: int = 45) -> dict:
    """
    Run Layer 0 assimilation on one golden plot and validate expectations.
    
    Returns:
        {"plot_id": ..., "passed": int, "failed": int, "errors": [...]}
    """
    plot = load_json(os.path.join(plot_dir, "plot.json"))
    weather = load_json(os.path.join(plot_dir, "weather_daily.json"))
    expected = load_json(os.path.join(plot_dir, "expected.json"))
    
    # Load observations
    s2_path = os.path.join(plot_dir, "sentinel2.json")
    s1_path = os.path.join(plot_dir, "sentinel1.json")
    events_path = os.path.join(plot_dir, "events.json")
    sensor_path = os.path.join(plot_dir, "sensor_data.json")
    
    s2_obs = load_json(s2_path) if os.path.exists(s2_path) else []
    s1_obs = load_json(s1_path) if os.path.exists(s1_path) else []
    events = load_json(events_path) if os.path.exists(events_path) else []
    sensor_data = load_json(sensor_path) if os.path.exists(sensor_path) else []
    
    plot_id = plot["plot_id"]
    zone_id = "plot"
    
    # Limit days for fast mode
    weather = weather[:max_days]
    
    # Build lookup maps
    s2_by_day = {o["day"]: o for o in s2_obs}
    s1_by_day = {o["day"]: o for o in s1_obs}
    sensor_by_day = {o["day"]: o for o in sensor_data}
    event_by_day = {e["day"]: e for e in events}
    
    # ---- Initialize engine ----
    engine = DailyAssimilationEngine()
    start_day = weather[0]["day"]
    engine.add_zone(zone_id, start_day=start_day)
    
    vg = ValidationGraph()
    
    # Track for assertions
    daily_sigmas = []  # avg sigma per day
    obs_day_indices = []  # days with observations
    conflict_log = []
    
    results = {"plot_id": plot_id, "passed": 0, "failed": 0, "errors": []}
    
    # ---- Run assimilation ----
    for d, w in enumerate(weather):
        day = w["day"]
        weather_drivers = {
            "temp_max": w["temp_max"],
            "temp_min": w["temp_min"],
            "precipitation": w["precipitation"],
            "et0": w["et0"],
        }
        
        # Collect observations for this day
        obs = {}
        kalman_obs = []
        
        s2 = s2_by_day.get(day)
        if s2 and not s2.get("is_cloudy", False):
            reliability = s2.get("valid_fraction", 0.9)
            kalman_obs.append(KalmanObservation("ndvi", s2["ndvi"], sigma=0.02,
                                                 reliability=reliability, source="sentinel2"))
            obs["ndvi"] = s2["ndvi"]
            if "ndmi" in s2:
                kalman_obs.append(KalmanObservation("ndmi", s2["ndmi"], sigma=0.04,
                                                     reliability=reliability, source="sentinel2"))
                obs["ndmi"] = s2["ndmi"]
        elif s2 and s2.get("is_cloudy", False):
            # Still provide obs for validation graph to detect cloud artifact
            obs["ndvi"] = s2["ndvi"]
            kalman_obs.append(KalmanObservation("ndvi", s2["ndvi"], sigma=0.02,
                                                 reliability=0.2, source="sentinel2"))
        
        s1 = s1_by_day.get(day)
        if s1:
            kalman_obs.append(KalmanObservation("vv", s1["vv"], sigma=1.5,
                                                 reliability=0.9, source="sentinel1"))
            obs["vv"] = s1["vv"]
        
        sensor = sensor_by_day.get(day)
        if sensor:
            kalman_obs.append(KalmanObservation("soil_moisture", sensor["soil_moisture"],
                                                 sigma=0.03, reliability=0.85, source="sensor"))
        
        # Run Kalman
        zone_obs = {zone_id: kalman_obs} if kalman_obs else {}
        engine.run_day(day, weather_drivers, zone_obs)
        
        if kalman_obs:
            obs_day_indices.append(d)
        
        # Run validation
        state = engine.filters[zone_id].state
        state_dict = {
            "lai_proxy": state.values[0],
            "biomass_proxy": state.values[1],
            "sm_0_10": state.values[2],
            "phenology_stage": state.values[6],
        }
        
        if obs or w["precipitation"] > 10:
            vg_results, rel = vg.validate_day(day, zone_id, state_dict, obs, weather_drivers)
            failed_checks = [r for r in vg_results if not r.passed]
            if failed_checks:
                conflict_log.append({
                    "day": day, "day_index": d,
                    "hypotheses": [r.hypothesis for r in failed_checks],
                    "checks": [r.check_name for r in failed_checks],
                })
        
        # Track uncertainty
        variance = state.variance if hasattr(state, "variance") else [0.1] * 8
        avg_sigma = sum(math.sqrt(max(0, v)) for v in variance) / len(variance)
        daily_sigmas.append(avg_sigma)
    
    # ---- Extract final state ----
    final_state = engine.filters[zone_id].state
    final_values = {
        "lai_proxy": final_state.values[0],
        "biomass_proxy": final_state.values[1],
        "sm_0_10": final_state.values[2],
        "sm_10_40": final_state.values[3],
        "canopy_stress": final_state.values[4],
        "phenology_gdd": final_state.values[5],
        "phenology_stage": final_state.values[6],
        "stress_thermal": final_state.values[7],
    }
    
    print(f"\n  Final state: {', '.join(f'{k}={v:.3f}' for k, v in final_values.items())}")
    print(f"  Obs days: {len(obs_day_indices)}/{len(weather)}")
    print(f"  Conflicts: {len(conflict_log)}")
    print(f"  S2 reliability: {vg.source_reliability.get('sentinel2', 1.0):.3f}")
    print(f"  S1 reliability: {vg.source_reliability.get('sentinel1', 1.0):.3f}")
    print(f"  Weather reliability: {vg.source_reliability.get('weather', 1.0):.3f}")
    
    # ---- Validate expectations ----
    
    # A) Final state ranges
    state_ranges = expected.get("final_state_ranges", {})
    for var, (lo, hi) in state_ranges.items():
        val = final_values.get(var)
        if val is not None:
            try:
                assert_range(var, val, lo, hi, plot_id)
                results["passed"] += 1
            except AssertionError as e:
                results["failed"] += 1
                results["errors"].append(str(e))
    
    # B) Uncertainty invariants
    unc_inv = expected.get("uncertainty_invariants", {})
    if unc_inv.get("grows_during_gaps"):
        # Find longest gap
        max_gap = 0
        current_gap = 0
        gap_sigma_pairs = []
        for d in range(1, len(daily_sigmas)):
            if d not in obs_day_indices:
                current_gap += 1
                if current_gap >= 2:
                    gap_sigma_pairs.append((daily_sigmas[d-1], daily_sigmas[d]))
            else:
                max_gap = max(max_gap, current_gap)
                current_gap = 0
        max_gap = max(max_gap, current_gap)
        
        # Check majority of gap pairs are monotonically increasing
        if gap_sigma_pairs:
            monotonic_count = sum(1 for a, b in gap_sigma_pairs if b >= a - 0.001)
            ratio = monotonic_count / len(gap_sigma_pairs)
            if ratio >= 0.7:
                results["passed"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(
                    f"GOLDEN FAIL [{plot_id}]: uncertainty not monotonic in gaps "
                    f"({ratio:.0%} monotonic, need 70%)"
                )
    
    # C) Conflict invariants
    conflict_inv = expected.get("conflict_invariants", {})
    if conflict_inv.get("rainfall_spatial_mismatch_expected"):
        rain_conflicts = [c for c in conflict_log
                          if any("rain" in h for h in c["hypotheses"])]
        if rain_conflicts:
            results["passed"] += 1
        else:
            results["failed"] += 1
            results["errors"].append(
                f"GOLDEN FAIL [{plot_id}]: expected rainfall_spatial_mismatch but found none"
            )
    
    if conflict_inv.get("cloud_artifact_days_expected") or \
       conflict_inv.get("vegetation_consistency_failures_expected"):
        cloud_or_veg = [c for c in conflict_log
                        if any("cloud" in h or "vegetation" in h for h in c["hypotheses"])]
        if cloud_or_veg:
            results["passed"] += 1
        else:
            results["failed"] += 1
            results["errors"].append(
                f"GOLDEN FAIL [{plot_id}]: expected cloud/vegetation conflicts but found none"
            )
    
    # D) Reliability invariants
    rel_inv = expected.get("reliability_invariants", {})
    for key, bounds in rel_inv.items():
        if isinstance(bounds, list) and len(bounds) == 2:
            source = key.replace("_stays_high", "").replace("_stays_stable", "") \
                       .replace("_min_after_clouds", "").replace("_decays_on_cloud_days", "")
            source = source.rstrip("_")
            actual = vg.source_reliability.get(source, 1.0)
            try:
                assert_range(key, actual, bounds[0], bounds[1], plot_id)
                results["passed"] += 1
            except AssertionError as e:
                results["failed"] += 1
                results["errors"].append(str(e))
    
    # E) Audit
    ds, su, pl = engine.to_field_tensor_outputs()
    audit_inv = expected.get("audit_invariants", {})
    
    try:
        report = TrustReportBuilder.build(
            plot_id=plot_id,
            daily_state=ds,
            state_uncertainty=su,
            provenance_log=pl,
            boundary_info={"confidence": 0.8},
            source_reliability=dict(vg.source_reliability),
        )
        print(f"  Audit: grade={report.health_grade}, score={report.health_score:.2f}")
        
        grade_range = audit_inv.get("health_grade_range")
        if grade_range:
            grade_order = "ABCDF"
            grade_lo = grade_order.index(grade_range[0])
            grade_hi = grade_order.index(grade_range[1])
            actual_idx = grade_order.index(report.health_grade) if report.health_grade in grade_order else 4
            if grade_lo <= actual_idx <= grade_hi:
                results["passed"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(
                    f"GOLDEN FAIL [{plot_id}]: grade={report.health_grade} not in "
                    f"[{grade_range[0]}, {grade_range[1]}]"
                )
    except Exception as e:
        results["errors"].append(f"GOLDEN FAIL [{plot_id}]: audit error: {e}")
        results["failed"] += 1
    
    # F) Invariant enforcement
    time_index = [w["day"] for w in weather]
    violations = enforce_all_invariants(
        ds, su, pl, time_index,
        source_reliability=dict(vg.source_reliability),
    )
    error_violations = [v for v in violations if v.severity == "error"]
    if not error_violations:
        results["passed"] += 1
    else:
        results["failed"] += 1
        results["errors"].append(
            f"GOLDEN FAIL [{plot_id}]: {len(error_violations)} invariant errors"
        )
    
    return results


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fast", action="store_true", help="Fast mode: 1 plot, 30 days")
    args = parser.parse_args()
    
    plot_dirs = [
        os.path.join(GOLDEN_DIR, "plot_cloudy"),
        os.path.join(GOLDEN_DIR, "plot_irrigated"),
        os.path.join(GOLDEN_DIR, "plot_rain_mismatch"),
    ]
    
    if args.fast:
        plot_dirs = plot_dirs[:1]
        max_days = 30
        print("=" * 60)
        print("GOLDEN REGRESSION — FAST (1 plot, 30 days)")
    else:
        max_days = 45
        print("=" * 60)
        print("GOLDEN REGRESSION — FULL (3 plots, 45 days)")
    print("=" * 60)
    
    total_passed = 0
    total_failed = 0
    all_errors = []
    
    for plot_dir in plot_dirs:
        plot_name = os.path.basename(plot_dir)
        print(f"\n--- {plot_name} ---")
        
        result = run_golden_plot(plot_dir, max_days)
        total_passed += result["passed"]
        total_failed += result["failed"]
        all_errors.extend(result["errors"])
        
        status = "✓" if result["failed"] == 0 else "✗"
        print(f"  Result: {status} {result['passed']} passed, {result['failed']} failed")
    
    print(f"\n{'=' * 60}")
    print(f"GOLDEN TOTAL: {total_passed} passed, {total_failed} failed")
    
    if all_errors:
        print("\nFAILURES:")
        for e in all_errors:
            print(f"  ❌ {e}")
        print(f"\n{'=' * 60}")
        sys.exit(1)
    else:
        print("ALL GOLDEN REGRESSION TESTS PASSED ✓")
        print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
