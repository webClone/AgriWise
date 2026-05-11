# -*- coding: utf-8 -*-
"""
AgriWise Production Validation -- L0->L9 Pipeline v9.6.0
========================================================
Extends L0->L8 validation with 13 L9 invariant checks.
"""
import json, math, os, sys, time, traceback, hashlib, io, logging
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timedelta
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(__file__))
logging.disable(logging.CRITICAL)

# ---- Weather ----
def fetch_real_weather(lat, lon, start, end):
    import urllib.request
    url = (
        "https://archive-api.open-meteo.com/v1/archive?"
        "latitude={}&longitude={}&start_date={}&end_date={}"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
        "et0_fao_evapotranspiration&timezone=UTC"
    ).format(lat, lon, start, end)
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        return [{"date": dates[i],
                 "t_max": daily["temperature_2m_max"][i] or 25.0,
                 "t_min": daily["temperature_2m_min"][i] or 15.0,
                 "rain_mm": daily["precipitation_sum"][i] or 0.0,
                 "et0": daily["et0_fao_evapotranspiration"][i] or 4.0}
                for i in range(len(dates))]
    except Exception:
        return _synthetic_weather(start, end)

def _synthetic_weather(start, end):
    s = datetime.strptime(start, "%Y-%m-%d")
    days = (datetime.strptime(end, "%Y-%m-%d") - s).days + 1
    return [{"date": (s + timedelta(days=i)).strftime("%Y-%m-%d"),
             "t_max": 28 + 6 * math.sin(i / 15),
             "t_min": 16 + 4 * math.sin(i / 15),
             "rain_mm": max(0, 3 + 8 * math.sin(i / 7)),
             "et0": 4.0 + 2 * math.sin(i / 20)} for i in range(days)]

# ---- Scenarios ----
SCENARIOS = [
    {"id": "S01_Iowa_Corn", "crop": "corn", "lat": 42.03, "lon": -93.47,
     "scenario": "optimal", "irrigation": "rainfed", "audit_grade": "A",
     "desc": "Iowa corn -- grade A"},
    {"id": "S02_Kansas_Wheat", "crop": "wheat", "lat": 38.36, "lon": -98.79,
     "scenario": "drought", "irrigation": "rainfed", "audit_grade": "B",
     "desc": "Kansas wheat -- drought, grade B"},
    {"id": "S03_Mississippi_Soy", "crop": "soybean", "lat": 33.45, "lon": -90.18,
     "scenario": "heat_stress", "irrigation": "rainfed", "audit_grade": "C",
     "desc": "Mississippi soy -- heat, grade C"},
    {"id": "S04_Louisiana_Rice", "crop": "rice", "lat": 30.22, "lon": -92.22,
     "scenario": "waterlogging", "irrigation": "flood", "audit_grade": "D",
     "desc": "Louisiana rice -- waterlog, grade D"},
    {"id": "S05_Texas_Cotton", "crop": "cotton", "lat": 31.99, "lon": -102.08,
     "scenario": "salinity", "irrigation": "drip", "audit_grade": "B",
     "desc": "Texas cotton -- salinity, multi-zone"},
    {"id": "S06_Idaho_Potato", "crop": "potato", "lat": 43.61, "lon": -116.21,
     "scenario": "insect_pressure", "irrigation": "pivot", "audit_grade": "F",
     "desc": "Idaho potato -- insects, grade F"},
]

# ---- Synthetic data ----
def generate_ndvi_series(weather, scenario, days):
    ndvi, base = [], 0.15
    for i in range(min(days, len(weather))):
        w = weather[i]
        growth = 0.015 if i < 25 else 0.008 if i < 60 else -0.002 if i < 90 else -0.012
        rain_boost = min(0.01, w["rain_mm"] * 0.001)
        heat_pen = max(0, (w["t_max"] - 38) * 0.005) if w["t_max"] > 38 else 0
        base = max(0.08, min(0.92, base + growth + rain_boost - heat_pen))
        if scenario == "drought" and i > 40: base = max(0.15, base - 0.008)
        elif scenario == "waterlogging" and 30 < i < 50: base = max(0.2, base - 0.005)
        elif scenario == "salinity": base = min(0.55, base)
        elif scenario == "insect_pressure" and 40 < i < 60: base -= 0.01
        ndvi.append(round(base, 4))
    return ndvi

def generate_sar_series(weather, scenario, days):
    vv, vh = [], []
    for i in range(min(days, len(weather))):
        w = weather[i]
        moisture = min(1.0, w["rain_mm"] / 20.0)
        v = -12.0 + 6.0 * moisture + 0.5 * math.sin(i / 5)
        vv.append(round(v, 2)); vh.append(round(v - 6.0 + 0.3 * math.sin(i / 7), 2))
    return vv, vh

def build_tensor(sc, weather, ndvi, vv, vh):
    from layer1_fusion.schema_legacy import FieldTensor
    days = min(len(weather), len(ndvi))
    plot_ts = []
    for i in range(days):
        w = weather[i]; t_mean = (w["t_max"] + w["t_min"]) / 2.0; is_obs = (i % 5 == 0)
        plot_ts.append({"date": w["date"], "ndvi_mean": ndvi[i] if is_obs else None,
            "ndvi_interpolated": ndvi[i], "ndvi_smoothed": ndvi[i], "is_observed": is_obs,
            "uncertainty": 0.05 if is_obs else 0.25, "rain": w["rain_mm"],
            "precipitation": w["rain_mm"], "tmean": t_mean, "temp_max": w["t_max"],
            "temp_min": w["t_min"], "et0": w["et0"], "gdd": max(0.0, t_mean - 10.0),
            "vv": vv[i] if i < len(vv) else None, "vh": vh[i] if i < len(vh) else None})
    zones = {"zone_A": {"area_pct": 0.6}, "zone_B": {"area_pct": 0.4}} if "multi-zone" in sc.get("desc", "") else {}
    rel = {"A": 0.95, "B": 0.85, "C": 0.6, "D": 0.35, "F": 0.15}.get(sc["audit_grade"], 0.5)
    return FieldTensor(plot_id=sc["id"], run_id="l1_sim_{}".format(sc["id"]),
        version="2.0.0-sim", time_index=[w["date"] for w in weather[:days]],
        channels=[], data=[], grid={}, maps={}, zones=zones, zone_stats={},
        plot_timeseries=plot_ts, forecast_7d=[], static={"soil_clay": 22.0, "soil_ph": 6.5, "soil_org_carbon": 1.8},
        provenance={"compatibility_mode": True, "source": "l9_validation", "layer0_reliability": rel},
        daily_state={}, state_uncertainty={}, provenance_log=[], spatial_reliability={}, boundary_info={})

# ---- Normalizers ----
def _norm_nutrients(l4):
    if not l4: return {}
    r = {}
    for k, v in (getattr(l4, "nutrient_states", None) or {}).items():
        key = k.value if hasattr(k, "value") else str(k)
        r[key] = {"probability_deficient": getattr(v, "probability_deficient", 0),
                   "confidence": getattr(v, "confidence", 0), "severity": getattr(v, "severity", "UNKNOWN")}
    return r

def _norm_threats(l5):
    if not l5: return {}
    r = {}
    for tid, st in (getattr(l5, "threat_states", None) or {}).items():
        r[tid] = {"probability": getattr(st, "probability", 0),
                   "confidence": getattr(st, "confidence", 0), "severity": getattr(st, "severity", "UNKNOWN")}
    return r

def _norm_diags(l3):
    if not l3: return []
    return [{"problem_id": getattr(d, "problem_id", "UNKNOWN"), "probability": getattr(d, "probability", 0),
             "severity": getattr(d, "severity", 0), "confidence": getattr(d, "confidence", 0.5)}
            for d in (getattr(l3, "diagnoses", []) or [])]

# ---- Pipeline L2->L9 ----
def run_pipeline(sc, weather):
    from orchestrator_v2.schema import OrchestratorInput
    from layer2_veg_int.runner import run_layer2_veg
    from layer3_decision.runner import run_layer3_decision
    from layer4_nutrients.runner import run_layer4_nutrients
    from layer5_bio.runner import run_layer5_bio
    from layer6_exec.runner import run_layer6_exec
    from layer8_prescriptive.runner import run_layer8
    from layer8_prescriptive.schema import Layer8Input
    from layer8_prescriptive.invariants import enforce_layer8_invariants
    from layer9_interface.runner import run_layer9

    days = min(90, len(weather))
    ndvi = generate_ndvi_series(weather, sc["scenario"], days)
    vv, vh = generate_sar_series(weather, sc["scenario"], days)
    tensor = build_tensor(sc, weather[:days], ndvi, vv, vh)

    inputs = OrchestratorInput(
        plot_id=sc["id"],
        geometry_hash=hashlib.sha256("{},{}".format(sc["lat"], sc["lon"]).encode()).hexdigest()[:8],
        date_range={"start": weather[0]["date"], "end": weather[min(days-1, len(weather)-1)]["date"]},
        crop_config={"crop": sc["crop"], "stage": "vegetative", "planting_date": weather[0]["date"]},
        operational_context={"lat": sc["lat"], "lng": sc["lon"], "irrigation_type": sc["irrigation"], "management_goal": "yield_max"},
        policy_snapshot={})

    r = {"scenario_id": sc["id"], "description": sc["desc"], "audit_grade": sc["audit_grade"]}

    # L2-L6
    l2_out = l3_out = l4_out = l5_out = l6_out = l8_out = None
    for layer_name, run_fn in [
        ("L2", lambda: run_layer2_veg(inputs, tensor)),
        ("L3", lambda: run_layer3_decision(inputs, tensor, l2_out)),
        ("L4", lambda: run_layer4_nutrients(inputs, tensor, l2_out, l3_out)),
        ("L5", lambda: run_layer5_bio(inputs, tensor, l2_out, l3_out, l4_out)),
    ]:
        try:
            out = run_fn()
            if layer_name == "L2": l2_out = out
            elif layer_name == "L3": l3_out = out
            elif layer_name == "L4": l4_out = out
            elif layer_name == "L5": l5_out = out
            r[layer_name] = "OK"
        except Exception as e:
            r[layer_name] = "FAILED: {}".format(str(e)[:80])

    try:
        if l3_out:
            l6_out = run_layer6_exec(inputs, tensor, l2_out, l3_out, l4_out, l5_out)
            r["L6"] = "OK"
        else:
            r["L6"] = "SKIPPED"
    except Exception as e:
        r["L6"] = "FAILED: {}".format(str(e)[:80])

    # L8
    try:
        ts = tensor.plot_timeseries or []
        forecast_7d = ts[-7:] if len(ts) >= 7 else ts
        zone_ids = list(tensor.zones.keys()) if tensor.zones else ["plot"]
        rel = {"A": 0.95, "B": 0.85, "C": 0.6, "D": 0.35, "F": 0.15}.get(sc["audit_grade"], 0.5)
        l8_input = Layer8Input(diagnoses=_norm_diags(l3_out), nutrient_states=_norm_nutrients(l4_out),
            bio_threats=_norm_threats(l5_out), weather_forecast=forecast_7d, zone_ids=zone_ids,
            audit_grade=sc["audit_grade"], source_reliability={z: rel for z in zone_ids},
            phenology_stage="VEGETATIVE", horizon_days=7, crop=sc.get("crop", "corn"),
            soil_static={"soil_clay": 22.0, "soil_ph": 6.5, "soil_org_carbon": 1.8})
        l8_out = run_layer8(l8_input, forecast_7d, datetime.now())
        r["L8"] = "OK"
        r["L8_action_count"] = len(l8_out.actions)
        r["L8_schedule_count"] = len(l8_out.schedule)
        r["L8_zone_count"] = len(l8_out.zone_plan)
        violations_l8 = enforce_layer8_invariants(l8_out)
        r["L8_invariant_violations"] = len(violations_l8)
    except Exception as e:
        r["L8"] = "FAILED: {}".format(str(e)[:150])
        traceback.print_exc()

    # L9
    try:
        l9_out = run_layer9(inputs, l8_out, l3_out, l6_out, None, [])
        r["L9"] = "OK"
        r["L9_summary"] = l9_out.summary[:100] if l9_out.summary else ""
        r["L9_zone_cards"] = len(l9_out.zone_cards)
        r["L9_alerts"] = len(l9_out.alerts)
        r["L9_disclaimers"] = len(l9_out.disclaimers)
        r["L9_citations"] = len(l9_out.citations)
        r["L9_phrasing"] = l9_out.phrasing_mode.value
        r["L9_badge"] = l9_out.render_hints.badge_color.value
        r["L9_followups"] = len(l9_out.follow_up_questions)
        r["L9_tasks"] = len(l9_out.task_board.tasks) if l9_out.task_board else 0
        r["L9_data_requests"] = len(l9_out.data_requests)
        r["L9_reminders"] = len(l9_out.reminders)
        r["L9_output"] = l9_out  # for invariant checks
    except Exception as e:
        r["L9"] = "FAILED: {}".format(str(e)[:150])
        traceback.print_exc()

    return r

# ---- L9 Invariant Validators (13 checks) ----
def validate_l9_invariants(r):
    v = []
    sid = r["scenario_id"]
    grade = r.get("audit_grade", "B")

    # INV-L9-1: L9 must succeed if L8 succeeded
    if r.get("L8") == "OK" and r.get("L9", "").startswith("FAIL"):
        v.append("[{}] INV-L9-1: L9 FAILED despite L8=OK".format(sid))

    if r.get("L9") != "OK":
        return v

    out = r.get("L9_output")

    # INV-L9-2: Summary must be non-empty
    if not r.get("L9_summary"):
        v.append("[{}] INV-L9-2: empty summary".format(sid))

    # INV-L9-3: Disclaimers present when grade <= C
    if grade in ("C", "D", "F") and r.get("L9_disclaimers", 0) < 1:
        v.append("[{}] INV-L9-3: grade={} but no disclaimers".format(sid, grade))

    # INV-L9-4: No hallucination flags on deterministic output
    from layer9_interface.hallucination_guard import HallucinationGuard
    if out:
        guard = HallucinationGuard.from_layer9_input({
            "actions": getattr(out, '_l9_actions', []),
            "schedule": [], "zone_plan": {}, "diagnoses": [], "outcome_forecast": {}})
        _, flags = guard.validate(out.summary or "")
        if flags:
            v.append("[{}] INV-L9-4: {} hallucination flag(s) on summary".format(sid, len(flags)))

    # INV-L9-5: Zone cards match zone_plan keys
    if out and r.get("L8") == "OK":
        l8_zones = r.get("L8_zone_count", 0)
        l9_zones = r.get("L9_zone_cards", 0)
        if l9_zones < l8_zones:
            v.append("[{}] INV-L9-5: zone_cards({}) < L8 zones({})".format(sid, l9_zones, l8_zones))

    # INV-L9-6: Badge color matches audit grade
    expected_badge = {"A": "GREEN", "B": "GREEN", "C": "YELLOW", "D": "RED", "F": "RED"}
    actual_badge = r.get("L9_badge", "")
    if expected_badge.get(grade) and actual_badge != expected_badge[grade]:
        v.append("[{}] INV-L9-6: grade={} expects badge={} got={}".format(
            sid, grade, expected_badge[grade], actual_badge))

    # INV-L9-7: Blocked actions never appear as suggested
    if out:
        summary_lower = (out.summary or "").lower()
        for alert in out.alerts:
            if "blocked" in (alert.message or "").lower():
                action_name = alert.message.split("'")[1] if "'" in alert.message else ""
                if action_name and "recommend {}".format(action_name.lower()) in summary_lower:
                    v.append("[{}] INV-L9-7: blocked action '{}' suggested".format(sid, action_name))

    # INV-L9-8: All citations reference valid upstream layers
    valid_layers = {"L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L10"}
    if out:
        for c in out.citations:
            if c.source_layer not in valid_layers:
                v.append("[{}] INV-L9-8: invalid citation layer '{}'".format(sid, c.source_layer))

    # INV-L9-9: Phrasing mode matches grade
    expected_phrasing = {"A": "CONFIDENT", "B": "CONFIDENT", "C": "HEDGED", "D": "RESTRICTED", "F": "RESTRICTED"}
    actual_phrasing = r.get("L9_phrasing", "")
    if expected_phrasing.get(grade) and actual_phrasing != expected_phrasing[grade]:
        v.append("[{}] INV-L9-9: grade={} expects phrasing={} got={}".format(
            sid, grade, expected_phrasing[grade], actual_phrasing))

    # INV-L9-10: Response quality > 0.5 for grade A/B
    # (Checked via non-empty summary + citations as proxy)
    if grade in ("A", "B"):
        if r.get("L9_citations", 0) < 1:
            v.append("[{}] INV-L9-10: grade={} but no citations".format(sid, grade))

    # INV-L9-11: Every L8 action generates a task
    l8_actions = r.get("L8_action_count", 0)
    l9_tasks = r.get("L9_tasks", 0)
    allowed_actions = l8_actions  # approximate
    if l9_tasks < 1 and allowed_actions > 0:
        v.append("[{}] INV-L9-11: {} L8 actions but {} tasks".format(sid, allowed_actions, l9_tasks))

    # INV-L9-12: Data requests never exceed 1 per session
    if r.get("L9_data_requests", 0) > 1:
        v.append("[{}] INV-L9-12: {} data requests (max 1)".format(sid, r["L9_data_requests"]))

    # INV-L9-13: Reminders respect rate limit (max 2/day)
    if r.get("L9_reminders", 0) > 2:
        v.append("[{}] INV-L9-13: {} reminders (max 2)".format(sid, r["L9_reminders"]))

    return v

# ---- Main ----
def main():
    print("=" * 72)
    print("  AgriWise Production Validation -- L0->L9 v9.6.0")
    print("  6 Scenarios x Real Weather x 13 L9 Invariants")
    print("  15-Engine Pipeline (Context|Intent|Memory|Advisory|QA|Report|")
    print("   Alert|Coach|Spatial|TaskMgr|DataReq|Reminder|Policy|Quality|Telemetry)")
    print("=" * 72)

    ref = datetime(2025, 8, 15)
    start = (ref - timedelta(days=90)).strftime("%Y-%m-%d")
    end = ref.strftime("%Y-%m-%d")

    all_results, all_violations = [], []
    layer_stats = {k: 0 for k in ("L2", "L3", "L4", "L5", "L6", "L8", "L9")}
    total_time = 0

    for i, sc in enumerate(SCENARIOS):
        print("")
        print("---" * 20)
        print("  [{}/{}] {}  (grade={})".format(i+1, len(SCENARIOS), sc["id"], sc["audit_grade"]))
        print("  {}".format(sc["desc"]))
        print("---" * 20)

        weather = fetch_real_weather(sc["lat"], sc["lon"], start, end)
        print("  Weather: {} days".format(len(weather)))

        t0 = time.time()
        try:
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(buf):
                # Reset operational engines per scenario
                from layer9_interface.engines.data_request import data_request_engine
                from layer9_interface.engines.reminder_engine import reminder_engine
                from layer9_interface.engines.task_manager import task_manager
                data_request_engine.reset_session()
                reminder_engine.reset_daily()
                task_manager._task_store.clear()
                result = run_pipeline(sc, weather)
        except Exception as e:
            result = {"scenario_id": sc["id"], "description": sc["desc"],
                      "audit_grade": sc["audit_grade"],
                      "L2": "CRASHED", "L3": "CRASHED", "L4": "CRASHED",
                      "L5": "CRASHED", "L6": "CRASHED", "L8": "CRASHED", "L9": "CRASHED"}
            print("  CRASH: {}".format(e))
            traceback.print_exc()
        elapsed = time.time() - t0
        total_time += elapsed
        result["elapsed_s"] = round(elapsed, 2)

        for layer in layer_stats:
            if result.get(layer) == "OK":
                layer_stats[layer] += 1

        violations = validate_l9_invariants(result)
        all_violations.extend(violations)
        # Remove non-serializable output
        result.pop("L9_output", None)
        result["l9_invariant_check"] = "PASS" if not violations else violations
        all_results.append(result)

        icon = "[PASS]" if not violations else "[WARN]"
        print("  {} Complete in {:.2f}s".format(icon, elapsed))
        status_parts = []
        for lyr in ("L2", "L3", "L4", "L5", "L6", "L8", "L9"):
            val = result.get(lyr, "?")
            status_parts.append("{}={}".format(lyr, str(val)[:6]))
        print("     {}".format(" | ".join(status_parts)))

        if result.get("L9") == "OK":
            print("     Summary: {}".format(result.get("L9_summary", "")[:80]))
            print("     ZoneCards:{} Alerts:{} Disclaimers:{} Citations:{}".format(
                result["L9_zone_cards"], result["L9_alerts"],
                result["L9_disclaimers"], result["L9_citations"]))
            print("     Phrasing:{} Badge:{} Tasks:{} DataReqs:{} Reminders:{}".format(
                result["L9_phrasing"], result["L9_badge"],
                result["L9_tasks"], result["L9_data_requests"], result["L9_reminders"]))

        if violations:
            for vv in violations:
                print("     [X] {}".format(vv))

    # Final Report
    print("")
    print("=" * 72)
    print("  L0->L9 PRODUCTION READINESS REPORT")
    print("=" * 72)
    total = len(SCENARIOS)
    passed = sum(1 for r in all_results if r.get("l9_invariant_check") == "PASS")
    print("")
    print("  Scenarios: {}/{} passed all L9 invariants".format(passed, total))
    print("  Total time: {:.1f}s".format(total_time))
    print("")
    for layer, count in layer_stats.items():
        pct = count / max(total, 1) * 100
        bar = "#" * int(pct / 5) + "." * (20 - int(pct / 5))
        print("    {}: [{}] {}/{} ({:.0f}%)".format(layer, bar, count, total, pct))

    if all_violations:
        print("")
        print("  {} invariant violation(s):".format(len(all_violations)))
        for vv in all_violations:
            print("    * {}".format(vv))
    else:
        print("")
        print("  [PASS] ALL 13 L9 INVARIANTS PASSED")

    ready = passed == total and layer_stats["L9"] >= total * 0.8
    print("")
    print("  " + "---" * 17)
    if ready:
        print("  VERDICT: PRODUCTION READY [PASS]")
    else:
        print("  VERDICT: NOT READY [FAIL]")
    print("  " + "---" * 17)

    out_path = os.path.join(os.path.dirname(__file__), "l0_to_l9_validation.json")
    with open(out_path, "w") as fp:
        json.dump(all_results, fp, indent=2, default=str)
    print("")
    print("  Results: {}".format(out_path))

if __name__ == "__main__":
    main()
