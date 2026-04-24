"""
Drone V1 Competitive Benchmark.

Evaluates:
1. Track B Perception Accuracy (Row azimuth, gap fraction, weed pressure)
2. Mission Execution Quality (Geometric coverage, waste, overlap)
3. QA Robustness (Blur, partial coverage, shadow handling)
"""

import sys
import os

_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)

from services.agribrain.layer0.perception.drone_rgb.engine import DroneRGBEngine
from services.agribrain.layer0.perception.drone_rgb.schemas import DroneRGBInput
from services.agribrain.drone_mission.schemas import MissionIntent, FlightMode
from services.agribrain.drone_mission.planner import DroneMissionPlanner
from services.agribrain.drone_mission.coverage_patterns import compute_execution_quality
from services.agribrain.drone_mission.capability_profiles import get_profile
from services.agribrain.layer0.perception.drone_rgb.benchmark.cases import BENCHMARK_CASES, _generate_synthetic_ortho

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
        return "✅" if value >= threshold else "❌"
    else:
        return "✅" if value <= threshold else "❌"


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

    # ====================================================================
    # Phase B: Mission Intelligence Benchmark
    # ====================================================================
    _run_autonomy_benchmark()


def _run_autonomy_benchmark():
    """Benchmark Phase B mission intelligence features."""
    from datetime import datetime, timedelta
    from services.agribrain.drone_mission.anomaly_bridge import AnomalyReport, MissionSuggestionEngine
    from services.agribrain.drone_mission.mission_history import MissionRecord, MissionHistory
    from services.agribrain.drone_mission.temporal_diff import TemporalDiffEngine
    from services.agribrain.drone_mission.refly_planner import ReflyPlanner
    from services.agribrain.drone_mission.hotspot_summarizer import HotspotSummarizer
    from services.agribrain.layer0.observation_packet import ObservationPacket, ObservationSource, ObservationType, QAMetadata
    from services.agribrain.layer0.perception.drone_rgb.benchmark.cases import STANDARD_POLYGON

    print("\n" + "=" * 60)
    print(" PHASE B: MISSION INTELLIGENCE BENCHMARK")
    print("=" * 60)

    NOW = datetime(2026, 4, 24, 12, 0, 0)
    suggestion_engine = MissionSuggestionEngine()
    temporal_engine = TemporalDiffEngine()
    refly_planner = ReflyPlanner()
    hotspot_summarizer = HotspotSummarizer()

    # --- Track 1: Auto-suggestion accuracy ---
    print("\n[Track 1] Auto-Suggestion Accuracy")
    suggestion_cases = [
        ("vegetation_drop",    0.7, 0.8, False, "row_audit"),
        ("weed_pressure_high", 0.6, 0.7, False, "weed_map"),
        ("disease_suspected",  0.8, 0.9, False, "concern_zone_command"),
        ("canopy_decline",     0.5, 0.6, False, "full_plot_map"),
        ("orchard_gap",        0.7, 0.8, False, "orchard_audit"),
        ("vegetation_drop",    0.1, 0.8, True,  "row_audit"),       # Low severity → suppress
        ("disease_suspected",  0.8, 0.2, True,  "concern_zone_command"), # Low confidence → suppress
    ]
    suggest_correct = 0
    suggest_total = len(suggestion_cases)

    for anomaly_type, severity, confidence, expect_suppressed, expect_mission in suggestion_cases:
        report = AnomalyReport(
            source="satellite_rgb", plot_id="bench",
            anomaly_type=anomaly_type, severity=severity, confidence=confidence,
            polygon_geojson=STANDARD_POLYGON, timestamp=NOW,
        )
        suggestion = suggestion_engine.evaluate(report)

        type_correct = suggestion.intent.mission_type.value == expect_mission
        suppress_correct = suggestion.suppressed == expect_suppressed
        both = type_correct and suppress_correct

        status = "✓" if both else "✗"
        print(f"  {status} {anomaly_type} (sev={severity}, conf={confidence}) "
              f"→ {suggestion.intent.mission_type.value} "
              f"{'[SUPPRESSED]' if suggestion.suppressed else '[ACTIVE]'}")

        if both:
            suggest_correct += 1

    # Recency suppression case
    report_recent = AnomalyReport(
        source="satellite_rgb", plot_id="bench",
        anomaly_type="vegetation_drop", severity=0.7, confidence=0.8,
        polygon_geojson=STANDARD_POLYGON, timestamp=NOW,
    )
    recent_ts = {"bench:vegetation_drop:": NOW - timedelta(hours=12)}
    suggestion_recent = suggestion_engine.evaluate(report_recent, recent_ts)
    recency_ok = suggestion_recent.suppressed
    suggest_total += 1
    if recency_ok:
        suggest_correct += 1
    print(f"  {'✓' if recency_ok else '✗'} Recency gate (12h ago) → "
          f"{'[SUPPRESSED]' if suggestion_recent.suppressed else '[ACTIVE]'}")

    suggest_accuracy = suggest_correct / suggest_total
    pf = "✅" if suggest_accuracy >= 0.80 else "❌"
    print(f"  {pf} Auto-suggestion accuracy: {suggest_accuracy:.0%} ({suggest_correct}/{suggest_total})")

    # --- Track 2: Temporal direction accuracy ---
    print("\n[Track 2] Temporal Direction Accuracy")
    temporal_cases = [
        # (metric, prev_val, cur_val, expect_direction)
        ("weed_pressure", 0.05, 0.25, "worsened"),
        ("weed_pressure", 0.25, 0.05, "improved"),
        ("canopy_cover", 0.50, 0.80, "improved"),
        ("canopy_cover", 0.80, 0.50, "worsened"),
        ("tree_count", 16, 14, "worsened"),
        ("canopy_cover", 0.70, 0.71, "stable"),
    ]
    temporal_correct = 0
    temporal_total = len(temporal_cases)

    for metric, prev_val, cur_val, expect_dir in temporal_cases:
        prev = MissionRecord(mission_id="prev", plot_id="p1", timestamp=NOW - timedelta(days=7))
        curr = MissionRecord(mission_id="curr", plot_id="p1", timestamp=NOW)
        setattr(prev, metric, prev_val)
        setattr(curr, metric, cur_val)

        changes = temporal_engine.compare(curr, prev)
        change = next((c for c in changes if c.metric == metric), None)
        got_dir = change.direction if change else "error"
        ok = got_dir == expect_dir
        status = "✓" if ok else "✗"
        print(f"  {status} {metric}: {prev_val} → {cur_val} = {got_dir} (expected {expect_dir})")
        if ok:
            temporal_correct += 1

    temporal_accuracy = temporal_correct / temporal_total
    pf = "✅" if temporal_accuracy >= 0.90 else "❌"
    print(f"  {pf} Temporal direction accuracy: {temporal_accuracy:.0%} ({temporal_correct}/{temporal_total})")

    # --- Track 3: Refly targeting precision ---
    print("\n[Track 3] Refly Targeting Precision")
    refly_cases = [
        # (qa, coverage, expect_refly, desc)
        (0.9, 0.60, True,  "Low coverage → refly"),
        (0.3, 0.95, True,  "Low QA → refly"),
        (0.95, 0.98, False, "Full coverage + good QA → no refly"),
    ]
    refly_correct = 0
    refly_total = len(refly_cases)

    for qa, cov, expect_refly, desc in refly_cases:
        zones = refly_planner.identify_weak_zones(
            qa_score=qa, coverage_completeness=cov,
            plot_polygon=STANDARD_POLYGON,
        )
        plan = refly_planner.plan_refly(zones, STANDARD_POLYGON, plot_id="bench")
        got_refly = plan is not None
        ok = got_refly == expect_refly
        status = "✓" if ok else "✗"

        # Check zone targeting
        zone_info = ""
        if got_refly and zones:
            has_bbox = any(z.zone_bbox for z in zones)
            wps = len(plan.waypoints) if plan else 0
            zone_info = f" [zones={len(zones)}, bbox={'yes' if has_bbox else 'no'}, wps={wps}]"

        print(f"  {status} {desc}: refly={'yes' if got_refly else 'no'}{zone_info}")
        if ok:
            refly_correct += 1

    # Sub-polygon targeting test: gap map with one quadrant of gaps
    gap_grid = [[0.0] * 20 for _ in range(20)]
    # Fill top-left quadrant with gaps
    for y in range(10):
        for x in range(10):
            gap_grid[y][x] = 1.0

    from services.agribrain.layer0.perception.drone_rgb.schemas import DroneStructuralMap
    gap_smap = DroneStructuralMap(map_type="stand_gaps", resolution_cm=10.0, data_grid=gap_grid)
    zones_targeted = refly_planner.identify_weak_zones(
        qa_score=0.9, coverage_completeness=0.95,
        spatial_maps=[gap_smap], plot_polygon=STANDARD_POLYGON,
    )
    has_targeted_zones = len(zones_targeted) > 0
    has_bbox = any(z.zone_bbox for z in zones_targeted)
    not_all_quadrants = len(zones_targeted) < 4  # Should only flag the gappy quadrant

    refly_total += 1
    targeted_ok = has_targeted_zones and has_bbox and not_all_quadrants
    if targeted_ok:
        refly_correct += 1
    status = "✓" if targeted_ok else "✗"
    print(f"  {status} Quadrant gap detection: zones={len(zones_targeted)}, "
          f"bbox={'yes' if has_bbox else 'no'}, targeted={not_all_quadrants}")

    refly_precision = refly_correct / refly_total
    pf = "✅" if refly_precision >= 0.70 else "❌"
    print(f"  {pf} Refly precision: {refly_precision:.0%} ({refly_correct}/{refly_total})")

    # --- Track 4: Hotspot consensus accuracy ---
    print("\n[Track 4] Hotspot Consensus Accuracy")
    def _pkt(symptom, qa_score=0.8):
        pkt = ObservationPacket(
            source=ObservationSource.FARMER_PHOTO,
            obs_type=ObservationType.IMAGE,
            payload={"top_symptom": symptom},
        )
        pkt.qa = QAMetadata(scene_score=qa_score)
        return pkt

    hotspot_cases = [
        # (packets, expect_symptom, expect_consensus, desc)
        (
            [_pkt("chlorosis"), _pkt("chlorosis"), _pkt("chlorosis")],
            "chlorosis", "unanimous", "3/3 chlorosis → unanimous"
        ),
        (
            [_pkt("chlorosis"), _pkt("chlorosis"), _pkt("necrosis")],
            "chlorosis", "majority", "2/3 chlorosis → majority"
        ),
        (
            [_pkt("chlorosis", 0.5), _pkt("chlorosis", 0.5),
             _pkt("necrosis", 0.9), _pkt("healthy", 0.4)],
            "necrosis", "mixed_evidence", "Best frame disagrees → mixed"
        ),
        (
            [_pkt("chlorosis", 0.7)] * 4 + [_pkt("necrosis", 0.9)],
            "chlorosis", "majority", "4/5 majority holds over best frame"
        ),
    ]
    hotspot_correct = 0
    hotspot_total = len(hotspot_cases)

    for packets, expect_sym, expect_cons, desc in hotspot_cases:
        summary = hotspot_summarizer.summarize(packets, "zone_bench", "m_bench")
        sym_ok = summary.top_symptom == expect_sym
        cons_ok = summary.consensus_type == expect_cons
        ok = sym_ok and cons_ok
        status = "✓" if ok else "✗"
        print(f"  {status} {desc}: got {summary.top_symptom}/{summary.consensus_type}")
        if ok:
            hotspot_correct += 1

    hotspot_accuracy = hotspot_correct / hotspot_total
    pf = "✅" if hotspot_accuracy >= 0.80 else "❌"
    print(f"  {pf} Hotspot consensus accuracy: {hotspot_accuracy:.0%} ({hotspot_correct}/{hotspot_total})")

    # --- Phase B Summary ---
    print("\n" + "-" * 60)
    print(" PHASE B SCORECARD")
    print("-" * 60)
    pf_s = "✅" if suggest_accuracy >= 0.80 else "❌"
    pf_t = "✅" if temporal_accuracy >= 0.90 else "❌"
    pf_r = "✅" if refly_precision >= 0.70 else "❌"
    pf_h = "✅" if hotspot_accuracy >= 0.80 else "❌"
    print(f"  {pf_s} [Autonomy]  Suggestion Accuracy: {suggest_accuracy:.0%}      (Target >= 80%)")
    print(f"  {pf_t} [Autonomy]  Temporal Direction:   {temporal_accuracy:.0%}      (Target >= 90%)")
    print(f"  {pf_r} [Autonomy]  Refly Precision:      {refly_precision:.0%}      (Target >= 70%)")
    print(f"  {pf_h} [Autonomy]  Hotspot Consensus:    {hotspot_accuracy:.0%}      (Target >= 80%)")
    print("=" * 60)


if __name__ == "__main__":
    run_benchmark()

