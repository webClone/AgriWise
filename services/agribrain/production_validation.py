"""
AgriWise Production Validation Harness v3
==========================================
End-to-end L2->L3->L4->L5 pipeline validation with real-world weather data.
Constructs hydrated FieldTensors with proper plot_timeseries so all layers
can execute successfully.
"""

import json
import math
import os
import sys
import time
import traceback
import hashlib
import io
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(__file__))


# ============================================================================
# Real Weather Data Fetcher (Open-Meteo -- no API key needed)
# ============================================================================

def fetch_real_weather(lat, lon, start, end):
    """Fetch real daily weather from Open-Meteo archive API."""
    import urllib.request
    url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat}&longitude={lon}"
        f"&start_date={start}&end_date={end}"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
        f"et0_fao_evapotranspiration"
        f"&timezone=UTC"
    )
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        result = []
        for i, d in enumerate(dates):
            result.append({
                "date": d,
                "t_max": daily["temperature_2m_max"][i] or 25.0,
                "t_min": daily["temperature_2m_min"][i] or 15.0,
                "rain_mm": daily["precipitation_sum"][i] or 0.0,
                "et0": daily["et0_fao_evapotranspiration"][i] or 4.0,
            })
        return result
    except Exception as e:
        print(f"  [!] Weather fetch failed ({e}), using synthetic fallback")
        return _synthetic_weather(start, end)


def _synthetic_weather(start, end):
    s = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end, "%Y-%m-%d")
    days = (e - s).days + 1
    result = []
    for i in range(days):
        d = s + timedelta(days=i)
        result.append({
            "date": d.strftime("%Y-%m-%d"),
            "t_max": 28 + 6 * math.sin(i / 15),
            "t_min": 16 + 4 * math.sin(i / 15),
            "rain_mm": max(0, 3 + 8 * math.sin(i / 7)),
            "et0": 4.0 + 2 * math.sin(i / 20),
        })
    return result


# ============================================================================
# Scenario Definitions
# ============================================================================

SCENARIOS = [
    {"id": "S01_Iowa_Corn_Optimal", "crop": "corn", "lat": 42.03, "lon": -93.47,
     "scenario": "optimal", "irrigation": "rainfed",
     "desc": "Iowa corn belt -- ideal growing season"},
    {"id": "S02_Kansas_Wheat_Drought", "crop": "wheat", "lat": 38.36, "lon": -98.79,
     "scenario": "drought", "irrigation": "rainfed",
     "desc": "Kansas winter wheat under drought stress"},
    {"id": "S03_Mississippi_Soy_Heat", "crop": "soybean", "lat": 33.45, "lon": -90.18,
     "scenario": "heat_stress", "irrigation": "rainfed",
     "desc": "Mississippi Delta soybean -- extreme heat"},
    {"id": "S04_Louisiana_Rice_Flood", "crop": "rice", "lat": 30.22, "lon": -92.22,
     "scenario": "waterlogging", "irrigation": "flood",
     "desc": "Louisiana rice paddy -- waterlogging risk"},
    {"id": "S05_Texas_Cotton_Salinity", "crop": "cotton", "lat": 31.99, "lon": -102.08,
     "scenario": "salinity", "irrigation": "drip",
     "desc": "West Texas cotton -- saline groundwater"},
    {"id": "S06_Montana_Barley_Lodging", "crop": "barley", "lat": 47.50, "lon": -111.29,
     "scenario": "lodging", "irrigation": "rainfed",
     "desc": "Montana barley -- wind/lodging event"},
    {"id": "S07_Idaho_Potato_Insects", "crop": "potato", "lat": 43.61, "lon": -116.21,
     "scenario": "insect_pressure", "irrigation": "pivot",
     "desc": "Idaho potato -- Colorado beetle pressure"},
    {"id": "S08_NorthDakota_Canola_DataGap", "crop": "canola", "lat": 48.23, "lon": -101.30,
     "scenario": "data_gap", "irrigation": "rainfed",
     "desc": "North Dakota canola -- persistent cloud cover"},
    {"id": "S09_Nebraska_Sorghum_TF", "crop": "sorghum", "lat": 40.82, "lon": -96.70,
     "scenario": "transpiration_failure", "irrigation": "rainfed",
     "desc": "Nebraska sorghum -- transpiration collapse"},
    {"id": "S10_California_Alfalfa_Tillage", "crop": "alfalfa", "lat": 36.74, "lon": -119.77,
     "scenario": "tillage", "irrigation": "flood",
     "desc": "California alfalfa -- post-tillage bare soil"},
]


# ============================================================================
# Synthetic NDVI/SAR Generators (conditioned on real weather)
# ============================================================================

def generate_ndvi_series(weather, scenario, days):
    ndvi = []
    base = 0.15
    for i in range(min(days, len(weather))):
        w = weather[i]
        if i < 25: growth = 0.015
        elif i < 60: growth = 0.008
        elif i < 90: growth = -0.002
        else: growth = -0.012
        rain_boost = min(0.01, w["rain_mm"] * 0.001)
        heat_pen = max(0, (w["t_max"] - 38) * 0.005) if w["t_max"] > 38 else 0
        base = max(0.08, min(0.92, base + growth + rain_boost - heat_pen))
        # Scenario modifiers
        if scenario == "drought" and i > 40: base = max(0.15, base - 0.008)
        elif scenario == "waterlogging" and 30 < i < 50: base = max(0.2, base - 0.005)
        elif scenario == "salinity": base = min(0.55, base)
        elif scenario == "lodging" and i == 75: base = max(0.25, base - 0.2)
        elif scenario == "insect_pressure" and 40 < i < 60: base -= 0.01
        elif scenario == "tillage" and i < 15: base = 0.1
        elif scenario == "transpiration_failure" and 55 < i < 75: base = max(0.2, base - 0.01)
        ndvi.append(round(base, 4))
    return ndvi


def generate_sar_series(weather, scenario, days):
    vv_list, vh_list = [], []
    for i in range(min(days, len(weather))):
        if scenario == "data_gap" and 50 < i < 70:
            vv_list.append(None); vh_list.append(None); continue
        w = weather[i]
        moisture = min(1.0, w["rain_mm"] / 20.0)
        vv = -12.0 + 6.0 * moisture + 0.5 * math.sin(i / 5)
        vh = vv - 6.0 + 0.3 * math.sin(i / 7)
        if scenario == "lodging" and i == 75: vv -= 4.0; vh -= 3.0
        vv_list.append(round(vv, 2))
        vh_list.append(round(vh, 2))
    return vv_list, vh_list


# ============================================================================
# Build Hydrated FieldTensor
# ============================================================================

def build_hydrated_field_tensor(scenario_cfg, weather, ndvi_series, vv_series, vh_series):
    """Construct a FieldTensor with fully populated plot_timeseries."""
    from layer1_fusion.schema_legacy import FieldTensor

    days = min(len(weather), len(ndvi_series))
    plot_ts = []
    gdd_acc = 0.0

    for i in range(days):
        w = weather[i]
        t_mean = (w["t_max"] + w["t_min"]) / 2.0
        gdd_day = max(0.0, t_mean - 10.0)  # Base 10C
        gdd_acc += gdd_day

        # Observation flag: every 5 days for optical (Sentinel-2 revisit)
        is_observed = (i % 5 == 0)
        if scenario_cfg["scenario"] == "data_gap" and 50 < i < 70:
            is_observed = False

        entry = {
            "date": w["date"],
            "ndvi_mean": ndvi_series[i] if is_observed else None,
            "ndvi_interpolated": ndvi_series[i],  # Always available (gap-filled)
            "ndvi_smoothed": ndvi_series[i],        # Alias for L5 remote_signature
            "is_observed": is_observed,
            "uncertainty": 0.05 if is_observed else 0.25,
            "rain": w["rain_mm"],
            "precipitation": w["rain_mm"],
            "tmean": t_mean,
            "temp_max": w["t_max"],
            "temp_min": w["t_min"],
            "et0": w["et0"],
            "gdd": gdd_day,
            "vv": vv_series[i] if i < len(vv_series) else None,
            "vh": vh_series[i] if i < len(vh_series) else None,
        }
        plot_ts.append(entry)

    tensor = FieldTensor(
        plot_id=scenario_cfg["id"],
        run_id=f"l1_sim_{scenario_cfg['id']}",
        version="2.0.0-sim",
        time_index=[w["date"] for w in weather[:days]],
        channels=[],
        data=[],
        grid={},
        maps={},
        zones={},
        zone_stats={},
        plot_timeseries=plot_ts,
        forecast_7d=[],
        static={
            "soil_clay": 22.0,
            "soil_ph": 6.5,
            "soil_org_carbon": 1.8,
        },
        provenance={
            "compatibility_mode": True,
            "source": "production_validation_harness",
            "layer0_reliability": 0.85,
        },
        daily_state={},
        state_uncertainty={},
        provenance_log=[],
        spatial_reliability={},
        boundary_info={},
    )
    return tensor


# ============================================================================
# Pipeline Executor -- Direct L2->L3->L4->L5
# ============================================================================

def run_pipeline(scenario_cfg, weather):
    """Execute L2->L3->L4->L5 with hydrated FieldTensor."""
    from orchestrator_v2.schema import OrchestratorInput, LayerStatus
    from layer2_veg_int.runner import run_layer2_veg
    from layer3_decision.runner import run_layer3_decision
    from layer4_nutrients.runner import run_layer4_nutrients
    from layer5_bio.runner import run_layer5_bio

    days = min(90, len(weather))
    ndvi = generate_ndvi_series(weather, scenario_cfg["scenario"], days)
    vv, vh = generate_sar_series(weather, scenario_cfg["scenario"], days)
    tensor = build_hydrated_field_tensor(scenario_cfg, weather[:days], ndvi, vv, vh)

    inputs = OrchestratorInput(
        plot_id=scenario_cfg["id"],
        geometry_hash=hashlib.sha256(
            f"{scenario_cfg['lat']},{scenario_cfg['lon']}".encode()
        ).hexdigest()[:8],
        date_range={"start": weather[0]["date"], "end": weather[min(days-1, len(weather)-1)]["date"]},
        crop_config={
            "crop": scenario_cfg["crop"],
            "stage": "vegetative",
            "planting_date": weather[0]["date"],
        },
        operational_context={
            "lat": scenario_cfg["lat"],
            "lng": scenario_cfg["lon"],
            "irrigation_type": scenario_cfg["irrigation"],
            "management_goal": "yield_max",
        },
        policy_snapshot={},
    )

    result = {
        "scenario_id": scenario_cfg["id"],
        "description": scenario_cfg["desc"],
        "crop": scenario_cfg["crop"],
        "location": f"{scenario_cfg['lat']}, {scenario_cfg['lon']}",
        "weather_days": days,
        "ndvi_range": [round(min(ndvi), 3), round(max(ndvi), 3)],
    }

    # --- L2: Vegetation Intelligence ---
    l2_out = None
    try:
        l2_out = run_layer2_veg(inputs, tensor)
        result["L2_status"] = "OK"
        result["L2_run_id"] = l2_out.run_id
        result["L2_anomaly_count"] = len(l2_out.anomalies)
        result["L2_stability"] = l2_out.stability.stability_class
        pheno = l2_out.phenology
        if pheno and pheno.stage_by_day:
            result["L2_final_stage"] = pheno.stage_by_day[-1]
        result["L2_curve_rmse"] = round(l2_out.curve.quality.rmse, 4)
    except Exception as e:
        result["L2_status"] = "FAILED"
        result["L2_error"] = str(e)[:200]
        traceback.print_exc()

    # --- L3: Decision Intelligence ---
    l3_out = None
    try:
        l3_out = run_layer3_decision(inputs, tensor, l2_out)
        result["L3_status"] = "OK"
        result["L3_run_id"] = l3_out.run_id_l3
        diags = [d for d in l3_out.diagnoses if d.probability > 0.3]
        result["L3_diagnoses"] = [
            {"id": d.problem_id, "prob": round(d.probability, 3),
             "sev": round(d.severity, 3), "conf": round(d.confidence, 3)}
            for d in diags
        ]
        result["L3_recommendation_count"] = len(l3_out.recommendations)
        result["L3_task_count"] = len(l3_out.execution_plan.tasks) if l3_out.execution_plan else 0
        qm = l3_out.quality_metrics
        result["L3_reliability"] = round(qm.decision_reliability, 3)
        result["L3_degradation_mode"] = qm.degradation_mode.value if hasattr(qm.degradation_mode, 'value') else str(qm.degradation_mode)
        # Hard prohibition check
        hp = l3_out.diagnostics.hard_prohibition_results
        result["L3_prohibitions_passed"] = all(hp.values()) if hp else True
    except Exception as e:
        result["L3_status"] = "FAILED"
        result["L3_error"] = str(e)[:200]
        traceback.print_exc()

    # --- L4: Nutrient Intelligence ---
    l4_out = None
    try:
        l4_out = run_layer4_nutrients(inputs, tensor, l2_out, l3_out)
        result["L4_status"] = "OK"
        result["L4_run_id"] = l4_out.run_meta.run_id
        states = l4_out.nutrient_states or {}
        result["L4_nutrients"] = {}
        for k, v in states.items():
            key = k.value if hasattr(k, "value") else str(k)
            result["L4_nutrients"][key] = {
                "prob_def": round(getattr(v, "probability_deficient", 0), 3),
                "conf": round(getattr(v, "confidence", 0), 3),
                "severity": getattr(v, "severity", "UNKNOWN"),
            }
        result["L4_tillage_detected"] = l4_out.tillage_detection.detected
        result["L4_soc_mineralization"] = round(l4_out.soc_dynamics.tillage_adjusted_mineralization, 2)
        result["L4_data_health"] = round(l4_out.data_health.overall, 3)
    except Exception as e:
        result["L4_status"] = "FAILED"
        result["L4_error"] = str(e)[:200]
        traceback.print_exc()

    # --- L5: BioThreat Intelligence ---
    l5_out = None
    try:
        l5_out = run_layer5_bio(inputs, tensor, l2_out, l3_out, l4_out)
        result["L5_status"] = "OK"
        result["L5_run_id"] = l5_out.run_meta.run_id
        result["L5_degradation"] = l5_out.run_meta.degradation_mode.value if hasattr(l5_out.run_meta.degradation_mode, 'value') else str(l5_out.run_meta.degradation_mode)
        result["L5_reliability"] = round(l5_out.quality_metrics.decision_reliability, 3)
        threats = l5_out.threat_states or {}
        result["L5_threats"] = {}
        for tid, st in threats.items():
            result["L5_threats"][tid] = {
                "prob": round(st.probability, 3),
                "conf": round(st.confidence, 3),
                "severity": st.severity.value if hasattr(st.severity, 'value') else str(st.severity),
                "class": st.threat_class.value if hasattr(st.threat_class, 'value') else str(st.threat_class),
            }
        result["L5_recommendation_count"] = len(l5_out.recommendations)
        result["L5_task_count"] = len(l5_out.execution_plan.tasks) if l5_out.execution_plan else 0
        # Run L5 invariants
        from layer5_bio.invariants import enforce_layer5_invariants
        l5_violations = enforce_layer5_invariants(l5_out)
        result["L5_invariant_violations"] = len(l5_violations)
    except Exception as e:
        result["L5_status"] = "FAILED"
        result["L5_error"] = str(e)[:200]
        traceback.print_exc()

    return result


# ============================================================================
# Invariant Validators
# ============================================================================

def validate_invariants(r):
    violations = []
    sid = r["scenario_id"]

    # INV-1: L2 must succeed
    if r.get("L2_status") != "OK":
        violations.append(f"[{sid}] INV-1: L2 {r.get('L2_status','?')} - {r.get('L2_error','')[:80]}")

    # INV-2: L3 must succeed if L2 succeeded
    if r.get("L2_status") == "OK" and r.get("L3_status") != "OK":
        violations.append(f"[{sid}] INV-2: L3 {r.get('L3_status','?')} despite L2=OK")

    # INV-3: L4 must succeed if L3 succeeded
    if r.get("L3_status") == "OK" and r.get("L4_status") != "OK":
        violations.append(f"[{sid}] INV-3: L4 {r.get('L4_status','?')} despite L3=OK")

    # INV-4: Reliability in [0,1]
    rel = r.get("L3_reliability", -1)
    if isinstance(rel, (int, float)) and not (0.0 <= rel <= 1.0):
        violations.append(f"[{sid}] INV-4: reliability={rel}")

    # INV-5: No critical issues in optimal scenario
    if "Optimal" in sid:
        diags = r.get("L3_diagnoses", [])
        critical = [d for d in diags if d.get("sev", 0) > 0.7]
        if critical:
            violations.append(f"[{sid}] INV-5: critical diagnoses in optimal: {critical}")

    # INV-6: Diagnoses bounded [0,1]
    for d in r.get("L3_diagnoses", []):
        if not (0.0 <= d["prob"] <= 1.0) or not (0.0 <= d["sev"] <= 1.0):
            violations.append(f"[{sid}] INV-6: diagnosis {d['id']} bounds violation")

    # INV-7: Nutrient confidence bounded [0,1]
    for k, v in r.get("L4_nutrients", {}).items():
        if not (0.0 <= v["conf"] <= 1.0):
            violations.append(f"[{sid}] INV-7: nutrient {k} conf={v['conf']}")

    # INV-8: Hard prohibitions must pass
    if not r.get("L3_prohibitions_passed", True):
        violations.append(f"[{sid}] INV-8: L3 hard prohibitions FAILED")

    # INV-9: L5 must succeed if L2 succeeded
    if r.get("L2_status") == "OK" and r.get("L5_status") != "OK":
        violations.append(f"[{sid}] INV-9: L5 {r.get('L5_status','?')} despite L2=OK - {r.get('L5_error','')[:80]}")

    # INV-10: L5 threat probabilities bounded [0,1]
    for tid, t in r.get("L5_threats", {}).items():
        if not (0.0 <= t["prob"] <= 1.0):
            violations.append(f"[{sid}] INV-10: threat {tid} prob={t['prob']}")

    # INV-11: L5 reliability bounded [0,1]
    l5_rel = r.get("L5_reliability", -1)
    if isinstance(l5_rel, (int, float)) and r.get("L5_status") == "OK" and not (0.0 <= l5_rel <= 1.0):
        violations.append(f"[{sid}] INV-11: L5 reliability={l5_rel}")

    # INV-12: L5 internal invariants passed
    if r.get("L5_invariant_violations", 0) > 0:
        violations.append(f"[{sid}] INV-12: L5 has {r['L5_invariant_violations']} internal invariant violations")

    return violations


# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 72)
    print("  AgriWise Production Validation -- L2/L3/L4/L5 Pipeline")
    print("  10 Scenarios x Real Weather x Full Invariant Check")
    print("=" * 72)

    ref = datetime(2025, 8, 15)
    start = (ref - timedelta(days=90)).strftime("%Y-%m-%d")
    end = ref.strftime("%Y-%m-%d")

    all_results = []
    all_violations = []
    layer_stats = {"L2": 0, "L3": 0, "L4": 0, "L5": 0}
    total_time = 0

    for i, sc in enumerate(SCENARIOS):
        print(f"\n{'---' * 20}")
        print(f"  [{i+1}/10] {sc['id']}")
        print(f"  {sc['desc']}")
        print(f"  Location: {sc['lat']}N, {sc['lon']}W")
        print(f"{'---' * 20}")

        # 1. Fetch weather
        print(f"  Fetching weather data...")
        weather = fetch_real_weather(sc["lat"], sc["lon"], start, end)
        print(f"  Got {len(weather)} days of weather data")

        # 2. Run pipeline (suppress internal prints)
        print(f"  Running full pipeline (L2->L3->L4->L5)...")
        t0 = time.time()
        try:
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(buf):
                result = run_pipeline(sc, weather)
            elapsed = time.time() - t0
        except Exception as e:
            elapsed = time.time() - t0
            result = {
                "scenario_id": sc["id"], "error": str(e),
                "L2_status": "CRASHED", "L3_status": "CRASHED", "L4_status": "CRASHED", "L5_status": "CRASHED",
            }
            print(f"  PIPELINE CRASH: {e}")
            traceback.print_exc()

        total_time += elapsed
        result["elapsed_s"] = round(elapsed, 2)

        # Count successes
        for layer in ("L2", "L3", "L4", "L5"):
            if result.get(f"{layer}_status") == "OK":
                layer_stats[layer] += 1

        # 3. Validate invariants
        violations = validate_invariants(result)
        all_violations.extend(violations)
        result["invariant_violations"] = violations
        result["invariants_passed"] = len(violations) == 0
        all_results.append(result)

        # Print summary
        icon = "[PASS]" if len(violations) == 0 else "[WARN]"
        print(f"  {icon} Pipeline complete in {elapsed:.2f}s")
        print(f"     L2={result.get('L2_status','?')} | L3={result.get('L3_status','?')} | L4={result.get('L4_status','?')} | L5={result.get('L5_status','?')}")
        if result.get("L3_reliability") is not None:
            print(f"     Reliability: {result['L3_reliability']:.1%}")
        diags = result.get("L3_diagnoses", [])
        if diags:
            print(f"     Diagnoses: {', '.join(d['id'] for d in diags[:4])}")
        nuts = result.get("L4_nutrients", {})
        if nuts:
            top = max(nuts.items(), key=lambda x: x[1]["prob_def"])
            print(f"     Top nutrient risk: {top[0]} (p={top[1]['prob_def']:.1%})")
        threats = result.get("L5_threats", {})
        if threats:
            top_t = max(threats.items(), key=lambda x: x[1]["prob"])
            print(f"     Top bio threat: {top_t[0]} (p={top_t[1]['prob']:.1%}, {top_t[1]['severity']})")
            print(f"     L5 recs: {result.get('L5_recommendation_count', 0)}, tasks: {result.get('L5_task_count', 0)}")
        if violations:
            for v in violations:
                print(f"     [X] {v}")

    # ============================================================================
    # Final Report
    # ============================================================================
    print(f"\n{'=' * 72}")
    print(f"  PRODUCTION READINESS REPORT")
    print(f"{'=' * 72}")

    passed = sum(1 for r in all_results if r.get("invariants_passed", False))
    total = len(all_results)

    print(f"\n  Scenarios: {passed}/{total} passed all invariants")
    print(f"  Total time: {total_time:.1f}s ({total_time/max(total,1):.1f}s avg)")
    print(f"\n  Layer Success Rates:")
    for layer, count in layer_stats.items():
        pct = count / max(total, 1) * 100
        bar = "#" * int(pct / 5) + "." * (20 - int(pct / 5))
        print(f"    {layer}: [{bar}] {count}/{total} ({pct:.0f}%)")

    if all_violations:
        print(f"\n  {len(all_violations)} invariant violation(s):")
        for v in all_violations[:15]:
            print(f"    * {v}")
    else:
        print(f"\n  ALL INVARIANTS PASSED -- Pipeline is PRODUCTION READY")

    l2_ok = layer_stats["L2"] >= total * 0.9
    l3_ok = layer_stats["L3"] >= total * 0.9
    l4_ok = layer_stats["L4"] >= total * 0.8
    l5_ok = layer_stats["L5"] >= total * 0.8

    print(f"\n  {'---' * 17}")
    print(f"  VERDICT:")
    print(f"    Layer 2 (VegInt):    {'PRODUCTION READY' if l2_ok else 'NOT READY'} ({layer_stats['L2']}/{total})")
    print(f"    Layer 3 (Decision):  {'PRODUCTION READY' if l3_ok else 'NOT READY'} ({layer_stats['L3']}/{total})")
    print(f"    Layer 4 (Nutrients): {'PRODUCTION READY' if l4_ok else 'NOT READY'} ({layer_stats['L4']}/{total})")
    print(f"    Layer 5 (BioThreat): {'PRODUCTION READY' if l5_ok else 'NOT READY'} ({layer_stats['L5']}/{total})")
    print(f"    Pipeline Overall:    {'PRODUCTION READY' if (l2_ok and l3_ok and l5_ok) else 'NOT READY'}")
    print(f"  {'---' * 17}")

    out_path = os.path.join(os.path.dirname(__file__), "production_validation_results.json")
    with open(out_path, "w") as fp:
        json.dump(all_results, fp, indent=2, default=str)
    print(f"\n  Full results: {out_path}")


if __name__ == "__main__":
    main()
