"""
AgriBrain 50-Plot Simulation Harness
=====================================
Runs the full orchestrator pipeline across procedurally generated plots,
seasons, and scenarios. Collects structured metrics from the canonical
AgriBrainRun JSON schema returned by run_surfaces_mode().

Output: simulation_metrics.json
"""

import os
import sys
import json
import random
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestrator_v2.run_entrypoint import run_surfaces_mode


# ============================================================================
# 1. Procedural Plot Generation
# ============================================================================

BASE_LAT, BASE_LNG = 36.75, 3.06  # Mediterranean agricultural region (Algeria)


def generate_polygon(lat, lng, size_deg=0.002):
    return [
        [lng, lat],
        [lng + size_deg, lat],
        [lng + size_deg, lat - size_deg],
        [lng, lat - size_deg],
        [lng, lat]
    ]


NUM_PLOTS = 50  # Original design: 50 plots

plots = []
for i in range(NUM_PLOTS):
    lat = BASE_LAT + random.uniform(-0.5, 0.5)
    lng = BASE_LNG + random.uniform(-0.5, 0.5)
    plots.append({
        "plot_id": f"SIM_PLOT_{i:04d}",
        "lat": lat,
        "lng": lng,
        "polygon": generate_polygon(lat, lng),
        "crop": random.choice(["wheat", "corn", "soybean", "potato", "tomato"])
    })


# ============================================================================
# 2. Seasons & Scenarios
# ============================================================================

seasons = ["2023", "2024", "2025"]

scenarios = [
    {"name": "OPTIMAL", "soil_type": "loam", "irrigation_type": "drip", "weather_modifier": "ideal"},
    {"name": "DROUGHT", "soil_type": "sandy_loam", "irrigation_type": "rainfed", "weather_modifier": "dry"},
    {"name": "BIOTIC", "soil_type": "clay", "irrigation_type": "sprinkler", "weather_modifier": "humid"}
]


# ============================================================================
# 3. Metric Collection — aligned to canonical AgriBrainRun schema
# ============================================================================

metrics = {
    "total_runs": 0,
    "total_errors": 0,
    "total_time_ms": 0.0,
    "avg_time_ms": 0.0,

    "architectural": {
        "layer_status_counts": {},    # {layer_id: {OK: N, DEGRADED: N, FAILED: N, SKIPPED: N}}
        "ok_layer_runs": 0,
        "degraded_layer_runs": 0,
        "failed_layer_runs": 0,
        "skipped_layer_runs": 0,
        "degradation_modes": {},
        "critical_failure_count": 0,
    },

    "psychological": {
        "phrasing_modes": {},         # from result.interface.phrasing_mode
        "trust_badges": {},           # from interface.zone_cards[].confidence_badge
        "explainability_generated": 0,  # count of runs with non-empty explainability_pack
        "disclaimer_count": 0,
    },

    "scientific": {
        "surfaces_generated_total": 0,
        "surface_type_counts": {},    # {NDVI_DELTA_7D: N, STRESS_MOMENTUM: N, ...}
        "temporal_surfaces": 0,
        "execution_surfaces": 0,
        "avg_reliability": 0.0,
        "avg_layer_confidence": {},   # {layer_id: avg_confidence}
    },

    "agronomical": {
        "zones_generated_total": 0,
        "zone_types_generated": {},   # {YIELD_GAP: N, STRESS_CLUSTER: N, ...}
        "recommendations_count": 0,
        "recommendations_by_source": {},  # {L3_DECISION: N, L4_NUTRIENTS: N}
        "top_findings_count": 0,
    },

    "financial": {
        "profit_surface_generated": 0,
        "avg_yield_gap_severity": 0.0,
    }
}

# Accumulators
total_reliability = 0.0
layer_confidence_sums = {}
layer_confidence_counts = {}
total_yield_gap_sev = 0.0
yield_gap_count = 0

TEMPORAL_SURFACE_TYPES = {
    "NDVI_DELTA_7D", "STRESS_MOMENTUM", "DROUGHT_TREND",
    "RISK_MOMENTUM", "GROWTH_TREND_7D", "YIELD_TRAJECTORY"
}
EXECUTION_SURFACE_TYPES = {
    "EXECUTION_READINESS", "INTERVENTION_PRIORITY", "INTERVENTION_TIMING"
}


# ============================================================================
# 4. Run Simulation
# ============================================================================

total_runs_planned = len(plots) * len(seasons) * len(scenarios)
print(f"Starting simulation of {total_runs_planned} combinations "
      f"({NUM_PLOTS} plots x {len(seasons)} seasons x {len(scenarios)} scenarios)...")

for s_idx, season in enumerate(seasons):
    print(f"\n--- Season: {season} ---")
    for sc_idx, scenario in enumerate(scenarios):
        print(f"  Scenario: {scenario['name']}")

        for p_idx, plot in enumerate(plots):
            ctx = {
                "plot_id": plot["plot_id"],
                "lat": plot["lat"],
                "lng": plot["lng"],
                "polygon": plot["polygon"],
                "crop": plot["crop"],
                "soil_type": scenario["soil_type"],
                "irrigation_type": scenario["irrigation_type"],
                "scenario_flag": scenario["name"],
                "season": season
            }

            start_t = time.time()
            try:
                result = run_surfaces_mode(ctx)
                dur = (time.time() - start_t) * 1000
                metrics["total_runs"] += 1
                metrics["total_time_ms"] += dur

                # ---- Architectural Metrics ----
                # Per-layer status from result["layer_results"]
                layer_results = result.get("layer_results", {})
                for lid, summary in layer_results.items():
                    status = summary.get("status", "SKIPPED")

                    if lid not in metrics["architectural"]["layer_status_counts"]:
                        metrics["architectural"]["layer_status_counts"][lid] = {
                            "OK": 0, "DEGRADED": 0, "FAILED": 0, "SKIPPED": 0
                        }
                    bucket = metrics["architectural"]["layer_status_counts"][lid]
                    bucket[status] = bucket.get(status, 0) + 1

                    if status == "OK":
                        metrics["architectural"]["ok_layer_runs"] += 1
                    elif status == "DEGRADED":
                        metrics["architectural"]["degraded_layer_runs"] += 1
                    elif status == "FAILED":
                        metrics["architectural"]["failed_layer_runs"] += 1
                    else:
                        metrics["architectural"]["skipped_layer_runs"] += 1

                    # Per-layer confidence tracking
                    conf = summary.get("confidence", 0.0)
                    if conf and conf > 0:
                        layer_confidence_sums[lid] = layer_confidence_sums.get(lid, 0.0) + conf
                        layer_confidence_counts[lid] = layer_confidence_counts.get(lid, 0) + 1

                # Global quality
                gq = result.get("global_quality", {})
                for mode in gq.get("degradation_modes", []):
                    metrics["architectural"]["degradation_modes"][mode] = (
                        metrics["architectural"]["degradation_modes"].get(mode, 0) + 1
                    )
                if gq.get("critical_failure"):
                    metrics["architectural"]["critical_failure_count"] += 1

                rel = gq.get("reliability", 0.0)
                total_reliability += rel

                # ---- Psychological Metrics ----
                # L9 interface output
                interface = result.get("interface", {})
                pm = interface.get("phrasing_mode", "UNKNOWN") or "UNKNOWN"
                metrics["psychological"]["phrasing_modes"][pm] = (
                    metrics["psychological"]["phrasing_modes"].get(pm, 0) + 1
                )

                # Zone card trust badges
                for zc in interface.get("zone_cards", []):
                    badge = zc.get("confidence_badge", "UNKNOWN")
                    metrics["psychological"]["trust_badges"][badge] = (
                        metrics["psychological"]["trust_badges"].get(badge, 0) + 1
                    )

                # Disclaimers
                metrics["psychological"]["disclaimer_count"] += len(
                    interface.get("disclaimers", [])
                )

                # Explainability
                ep = result.get("explainability_pack", {})
                if ep and len(ep) > 0:
                    metrics["psychological"]["explainability_generated"] += 1

                # ---- Scientific Metrics ----
                surfaces = result.get("surfaces", [])
                metrics["scientific"]["surfaces_generated_total"] += len(surfaces)

                for s in surfaces:
                    stype = s.get("type", s.get("semantic_type", "UNKNOWN"))
                    metrics["scientific"]["surface_type_counts"][stype] = (
                        metrics["scientific"]["surface_type_counts"].get(stype, 0) + 1
                    )
                    if stype in TEMPORAL_SURFACE_TYPES:
                        metrics["scientific"]["temporal_surfaces"] += 1
                    if stype in EXECUTION_SURFACE_TYPES:
                        metrics["scientific"]["execution_surfaces"] += 1

                # ---- Agronomical Metrics ----
                zones = result.get("zones", [])
                metrics["agronomical"]["zones_generated_total"] += len(zones)

                for z in zones:
                    ztype = z.get("zone_type", "UNKNOWN")
                    metrics["agronomical"]["zone_types_generated"][ztype] = (
                        metrics["agronomical"]["zone_types_generated"].get(ztype, 0) + 1
                    )
                    if ztype == "YIELD_GAP":
                        sev = z.get("severity", 0.0)
                        total_yield_gap_sev += sev
                        yield_gap_count += 1

                recs = result.get("recommendations", [])
                metrics["agronomical"]["recommendations_count"] += len(recs)
                for r in recs:
                    src = r.get("source", "UNKNOWN")
                    metrics["agronomical"]["recommendations_by_source"][src] = (
                        metrics["agronomical"]["recommendations_by_source"].get(src, 0) + 1
                    )

                findings = result.get("top_findings", [])
                metrics["agronomical"]["top_findings_count"] += len(findings)

                # ---- Financial Metrics ----
                prof_surfs = [s for s in surfaces if s.get("type") == "PROFIT_SURFACE"]
                metrics["financial"]["profit_surface_generated"] += len(prof_surfs)

            except Exception as e:
                metrics["total_errors"] += 1
                print(f"    ERROR plot {plot['plot_id']}: {e}")


# ============================================================================
# 5. Final Averages & Save
# ============================================================================

if metrics["total_runs"] > 0:
    metrics["avg_time_ms"] = round(metrics["total_time_ms"] / metrics["total_runs"], 3)
    metrics["scientific"]["avg_reliability"] = round(
        total_reliability / metrics["total_runs"], 4
    )

# Per-layer average confidence
for lid, total in layer_confidence_sums.items():
    count = layer_confidence_counts.get(lid, 1)
    metrics["scientific"]["avg_layer_confidence"][lid] = round(total / count, 4)

if yield_gap_count > 0:
    metrics["financial"]["avg_yield_gap_severity"] = round(
        total_yield_gap_sev / yield_gap_count, 4
    )

output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "simulation_metrics.json")
with open(output_path, "w") as f:
    json.dump(metrics, f, indent=2)

print(f"\nSimulation complete. {metrics['total_runs']} runs processed, "
      f"{metrics['total_errors']} errors.")
print(f"Metrics saved to {output_path}")
