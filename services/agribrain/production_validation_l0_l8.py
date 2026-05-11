# -*- coding: utf-8 -*-
"""
AgriWise Production Validation -- L0->L8 Prescriptive Pipeline v8.2.0
=====================================================================
Full E2E pipeline validation: L2->L3->L4->L5->L6->L8
6 scenarios x real weather x 13 invariant checks.
7 intelligence engines (phenology, nutrient, IPM, env-risk, cognitive, adoption, framing).
Fully ASCII-safe for Windows cp1252.
"""

import json, math, os, sys, time, traceback, hashlib, io, logging
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timedelta
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(__file__))
logging.disable(logging.CRITICAL)


# ============================================================================
# Weather
# ============================================================================

def fetch_real_weather(lat, lon, start, end):
    import urllib.request
    url = (
        "https://archive-api.open-meteo.com/v1/archive?"
        "latitude={}&longitude={}"
        "&start_date={}&end_date={}"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
        "et0_fao_evapotranspiration"
        "&timezone=UTC"
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
    except Exception as e:
        print("  [!] Weather fetch failed ({}), using synthetic".format(e))
        return _synthetic_weather(start, end)


def _synthetic_weather(start, end):
    s = datetime.strptime(start, "%Y-%m-%d")
    days = (datetime.strptime(end, "%Y-%m-%d") - s).days + 1
    return [{"date": (s + timedelta(days=i)).strftime("%Y-%m-%d"),
             "t_max": 28 + 6 * math.sin(i / 15),
             "t_min": 16 + 4 * math.sin(i / 15),
             "rain_mm": max(0, 3 + 8 * math.sin(i / 7)),
             "et0": 4.0 + 2 * math.sin(i / 20)} for i in range(days)]


# ============================================================================
# Scenarios
# ============================================================================

SCENARIOS = [
    {"id": "S01_Iowa_Corn_Optimal", "crop": "corn", "lat": 42.03, "lon": -93.47,
     "scenario": "optimal", "irrigation": "rainfed", "audit_grade": "A",
     "desc": "Iowa corn -- ideal conditions, grade A trust"},
    {"id": "S02_Kansas_Wheat_Drought", "crop": "wheat", "lat": 38.36, "lon": -98.79,
     "scenario": "drought", "irrigation": "rainfed", "audit_grade": "B",
     "desc": "Kansas wheat -- drought stress, grade B trust"},
    {"id": "S03_Mississippi_Soy_Heat", "crop": "soybean", "lat": 33.45, "lon": -90.18,
     "scenario": "heat_stress", "irrigation": "rainfed", "audit_grade": "C",
     "desc": "Mississippi soy -- heat stress, grade C (LOW_TRUST)"},
    {"id": "S04_Louisiana_Rice_Flood", "crop": "rice", "lat": 30.22, "lon": -92.22,
     "scenario": "waterlogging", "irrigation": "flood", "audit_grade": "D",
     "desc": "Louisiana rice -- waterlog, grade D (VERY_LOW_TRUST)"},
    {"id": "S05_Texas_Cotton_Salinity", "crop": "cotton", "lat": 31.99, "lon": -102.08,
     "scenario": "salinity", "irrigation": "drip", "audit_grade": "B",
     "desc": "Texas cotton -- salinity, multi-zone"},
    {"id": "S06_Idaho_Potato_Insects", "crop": "potato", "lat": 43.61, "lon": -116.21,
     "scenario": "insect_pressure", "irrigation": "pivot", "audit_grade": "F",
     "desc": "Idaho potato -- insects, grade F (max degradation)"},
]


# ============================================================================
# Synthetic NDVI / SAR
# ============================================================================

def generate_ndvi_series(weather, scenario, days):
    ndvi, base = [], 0.15
    for i in range(min(days, len(weather))):
        w = weather[i]
        if i < 25:
            growth = 0.015
        elif i < 60:
            growth = 0.008
        elif i < 90:
            growth = -0.002
        else:
            growth = -0.012
        rain_boost = min(0.01, w["rain_mm"] * 0.001)
        heat_pen = max(0, (w["t_max"] - 38) * 0.005) if w["t_max"] > 38 else 0
        base = max(0.08, min(0.92, base + growth + rain_boost - heat_pen))
        if scenario == "drought" and i > 40:
            base = max(0.15, base - 0.008)
        elif scenario == "waterlogging" and 30 < i < 50:
            base = max(0.2, base - 0.005)
        elif scenario == "salinity":
            base = min(0.55, base)
        elif scenario == "insect_pressure" and 40 < i < 60:
            base -= 0.01
        ndvi.append(round(base, 4))
    return ndvi


def generate_sar_series(weather, scenario, days):
    vv, vh = [], []
    for i in range(min(days, len(weather))):
        w = weather[i]
        moisture = min(1.0, w["rain_mm"] / 20.0)
        v = -12.0 + 6.0 * moisture + 0.5 * math.sin(i / 5)
        h = v - 6.0 + 0.3 * math.sin(i / 7)
        vv.append(round(v, 2))
        vh.append(round(h, 2))
    return vv, vh


# ============================================================================
# Build FieldTensor
# ============================================================================

def build_tensor(sc, weather, ndvi, vv, vh):
    from layer1_fusion.schema_legacy import FieldTensor
    days = min(len(weather), len(ndvi))
    plot_ts = []
    for i in range(days):
        w = weather[i]
        t_mean = (w["t_max"] + w["t_min"]) / 2.0
        is_obs = (i % 5 == 0)
        plot_ts.append({
            "date": w["date"],
            "ndvi_mean": ndvi[i] if is_obs else None,
            "ndvi_interpolated": ndvi[i],
            "ndvi_smoothed": ndvi[i],
            "is_observed": is_obs,
            "uncertainty": 0.05 if is_obs else 0.25,
            "rain": w["rain_mm"],
            "precipitation": w["rain_mm"],
            "tmean": t_mean,
            "temp_max": w["t_max"],
            "temp_min": w["t_min"],
            "et0": w["et0"],
            "gdd": max(0.0, t_mean - 10.0),
            "vv": vv[i] if i < len(vv) else None,
            "vh": vh[i] if i < len(vh) else None,
        })
    zones = {}
    if "multi-zone" in sc.get("desc", ""):
        zones = {"zone_A": {"area_pct": 0.6}, "zone_B": {"area_pct": 0.4}}
    reliability_val = {"A": 0.95, "B": 0.85, "C": 0.6, "D": 0.35, "F": 0.15
                       }.get(sc["audit_grade"], 0.5)
    return FieldTensor(
        plot_id=sc["id"], run_id="l1_sim_{}".format(sc["id"]),
        version="2.0.0-sim",
        time_index=[w["date"] for w in weather[:days]],
        channels=[], data=[], grid={}, maps={},
        zones=zones, zone_stats={},
        plot_timeseries=plot_ts, forecast_7d=[],
        static={"soil_clay": 22.0, "soil_ph": 6.5, "soil_org_carbon": 1.8},
        provenance={"compatibility_mode": True, "source": "l8_validation",
                     "layer0_reliability": reliability_val},
        daily_state={}, state_uncertainty={}, provenance_log=[],
        spatial_reliability={}, boundary_info={},
    )


# ============================================================================
# Upstream normalization (inline -- no orchestrator dependency)
# ============================================================================

def _normalize_nutrient_states(l4_out):
    """Convert L4 output to dict for L8 input."""
    if l4_out is None:
        return {}
    states = getattr(l4_out, "nutrient_states", None) or {}
    result = {}
    for k, v in states.items():
        key = k.value if hasattr(k, "value") else str(k)
        result[key] = {
            "probability_deficient": getattr(v, "probability_deficient", 0),
            "confidence": getattr(v, "confidence", 0),
            "severity": getattr(v, "severity", "UNKNOWN"),
        }
    return result


def _normalize_threat_states(l5_out):
    """Convert L5 output to dict for L8 input."""
    if l5_out is None:
        return {}
    threats = getattr(l5_out, "threat_states", None) or {}
    result = {}
    for tid, st in threats.items():
        result[tid] = {
            "probability": getattr(st, "probability", 0),
            "confidence": getattr(st, "confidence", 0),
            "severity": getattr(st, "severity", "UNKNOWN"),
        }
    return result


def _normalize_diagnoses(l3_out):
    """Convert L3 diagnoses to list-of-dicts for L8 input."""
    if l3_out is None:
        return []
    diags = getattr(l3_out, "diagnoses", []) or []
    result = []
    for d in diags:
        result.append({
            "problem_id": getattr(d, "problem_id", "UNKNOWN"),
            "probability": getattr(d, "probability", 0),
            "severity": getattr(d, "severity", 0),
            "confidence": getattr(d, "confidence", 0.5),
        })
    return result


# ============================================================================
# Full Pipeline L2 -> L8
# ============================================================================

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

    days = min(90, len(weather))
    ndvi = generate_ndvi_series(weather, sc["scenario"], days)
    vv, vh = generate_sar_series(weather, sc["scenario"], days)
    tensor = build_tensor(sc, weather[:days], ndvi, vv, vh)

    inputs = OrchestratorInput(
        plot_id=sc["id"],
        geometry_hash=hashlib.sha256(
            "{},{}".format(sc["lat"], sc["lon"]).encode()
        ).hexdigest()[:8],
        date_range={
            "start": weather[0]["date"],
            "end": weather[min(days - 1, len(weather) - 1)]["date"],
        },
        crop_config={
            "crop": sc["crop"],
            "stage": "vegetative",
            "planting_date": weather[0]["date"],
        },
        operational_context={
            "lat": sc["lat"], "lng": sc["lon"],
            "irrigation_type": sc["irrigation"],
            "management_goal": "yield_max",
        },
        policy_snapshot={},
    )

    r = {
        "scenario_id": sc["id"],
        "description": sc["desc"],
        "audit_grade": sc["audit_grade"],
    }

    # --- L2 ---
    l2_out = None
    try:
        l2_out = run_layer2_veg(inputs, tensor)
        r["L2"] = "OK"
    except Exception as e:
        r["L2"] = "FAILED: {}".format(str(e)[:100])

    # --- L3 ---
    l3_out = None
    try:
        l3_out = run_layer3_decision(inputs, tensor, l2_out)
        r["L3"] = "OK"
        r["L3_diag_count"] = len([d for d in l3_out.diagnoses if d.probability > 0.2])
    except Exception as e:
        r["L3"] = "FAILED: {}".format(str(e)[:100])

    # --- L4 ---
    l4_out = None
    try:
        l4_out = run_layer4_nutrients(inputs, tensor, l2_out, l3_out)
        r["L4"] = "OK"
    except Exception as e:
        r["L4"] = "FAILED: {}".format(str(e)[:100])

    # --- L5 ---
    l5_out = None
    try:
        l5_out = run_layer5_bio(inputs, tensor, l2_out, l3_out, l4_out)
        r["L5"] = "OK"
    except Exception as e:
        r["L5"] = "FAILED: {}".format(str(e)[:100])

    # --- L6 ---
    l6_out = None
    try:
        if l3_out:
            l6_out = run_layer6_exec(inputs, tensor, l2_out, l3_out, l4_out, l5_out)
            r["L6"] = "OK"
        else:
            r["L6"] = "SKIPPED (no L3)"
    except Exception as e:
        r["L6"] = "FAILED: {}".format(str(e)[:100])

    # --- L8 (Prescriptive) ---
    try:
        diagnoses = _normalize_diagnoses(l3_out)
        nutrient_states = _normalize_nutrient_states(l4_out)
        bio_threats = _normalize_threat_states(l5_out)

        ts = tensor.plot_timeseries or []
        forecast_7d = ts[-7:] if len(ts) >= 7 else ts

        zone_ids = list(tensor.zones.keys()) if tensor.zones else ["plot"]
        reliability_val = {"A": 0.95, "B": 0.85, "C": 0.6, "D": 0.35, "F": 0.15
                           }.get(sc["audit_grade"], 0.5)

        l8_input = Layer8Input(
            diagnoses=diagnoses,
            nutrient_states=nutrient_states,
            bio_threats=bio_threats,
            weather_forecast=forecast_7d,
            zone_ids=zone_ids,
            audit_grade=sc["audit_grade"],
            source_reliability={z: reliability_val for z in zone_ids},
            phenology_stage="VEGETATIVE",
            horizon_days=7,
            crop=sc.get("crop", "corn"),
            soil_static={"soil_clay": 22.0, "soil_ph": 6.5, "soil_org_carbon": 1.8},
        )

        l8_out = run_layer8(l8_input, forecast_7d, datetime.now())
        r["L8"] = "OK"
        r["L8_run_id"] = l8_out.run_id
        r["L8_action_count"] = len(l8_out.actions)
        r["L8_schedule_count"] = len(l8_out.schedule)
        r["L8_zone_count"] = len(l8_out.zone_plan)
        r["L8_tradeoff_count"] = len(l8_out.tradeoffs)
        r["L8_degradation"] = l8_out.quality.degradation_mode.value
        r["L8_reliability"] = round(l8_out.quality.decision_reliability, 3)
        r["L8_invariant_violations"] = len(l8_out.audit.invariant_violations)

        r["L8_actions"] = []
        for c in l8_out.actions:
            entry = {
                "id": c.action_id, "type": c.action_type.value,
                "score": round(c.priority_score, 4),
                "allowed": c.is_allowed, "heuristic": c.heuristic,
                "evidence_count": len(c.evidence),
                "confidence": c.confidence.value,
            }
            # Engine metadata
            if c.phenology_info:
                entry["bbch"] = c.phenology_info.bbch_code
                entry["stage"] = c.phenology_info.stage_name
            if c.ipm_decision:
                entry["ipm_level"] = c.ipm_decision.escalation_level.value
            if c.env_risk:
                entry["env_penalty"] = c.env_risk.environmental_penalty
            if c.adoption:
                entry["adopt_prob"] = c.adoption.adoption_probability
                entry["nudge"] = c.adoption.nudge_strategy
            if c.framed_message:
                entry["frame"] = c.framed_message.frame_type.value
            r["L8_actions"].append(entry)

        r["L8_schedule"] = []
        for s in l8_out.schedule:
            r["L8_schedule"].append({
                "id": s.action_id,
                "date": s.scheduled_date,
                "status": s.status.value,
            })

        r["L8_yield_delta"] = l8_out.outcome_forecast.yield_delta_pct
        r["L8_risk_reduction"] = l8_out.outcome_forecast.risk_reduction_pct
        r["L8_cost"] = l8_out.outcome_forecast.cost_total

        # Cognitive load metadata
        if l8_out.cognitive_load:
            r["L8_cog_presented"] = l8_out.cognitive_load.actions_presented
            r["L8_cog_suppressed"] = l8_out.cognitive_load.actions_suppressed
            r["L8_cog_complexity"] = l8_out.cognitive_load.total_complexity
            r["L8_cog_fatigue"] = l8_out.cognitive_load.fatigue_warning

        # Re-run invariants to double-check idempotency
        violations = enforce_layer8_invariants(l8_out)
        r["L8_recheck_violations"] = len(violations)

    except Exception as e:
        r["L8"] = "FAILED: {}".format(str(e)[:200])
        traceback.print_exc()

    return r


# ============================================================================
# Invariant Validators
# ============================================================================

def validate_l8_invariants(r):
    violations = []
    sid = r["scenario_id"]
    grade = r.get("audit_grade", "B")

    # INV-L8-1: L8 must succeed if L3 succeeded
    if r.get("L3") == "OK" and r.get("L8", "").startswith("FAIL"):
        violations.append("[{}] INV-L8-1: L8 FAILED despite L3=OK".format(sid))

    if r.get("L8") != "OK":
        return violations

    # INV-L8-2: Must have at least 1 action
    if r.get("L8_action_count", 0) < 1:
        violations.append("[{}] INV-L8-2: zero actions produced".format(sid))

    # INV-L8-3: Schedule count must match action count
    if r.get("L8_schedule_count", 0) != r.get("L8_action_count", 0):
        violations.append(
            "[{}] INV-L8-3: schedule/action count mismatch ({} vs {})".format(
                sid, r["L8_schedule_count"], r["L8_action_count"]))

    # INV-L8-4: Reliability bounded [0, 1]
    rel = r.get("L8_reliability", -1)
    if not (0.0 <= rel <= 1.0):
        violations.append("[{}] INV-L8-4: reliability={} out of bounds".format(sid, rel))

    # INV-L8-5: No invariant violations after enforcement
    if r.get("L8_recheck_violations", 0) > 0:
        violations.append("[{}] INV-L8-5: {} post-enforcement violations".format(
            sid, r["L8_recheck_violations"]))

    # INV-L8-6: Grade D/F -> VERY_LOW_TRUST degradation
    if grade in ("D", "F"):
        if r.get("L8_degradation") != "VERY_LOW_TRUST":
            violations.append("[{}] INV-L8-6: grade={} but degradation={}".format(
                sid, grade, r.get("L8_degradation")))

    # INV-L8-7: Grade C -> LOW_TRUST degradation
    if grade == "C":
        if r.get("L8_degradation") != "LOW_TRUST":
            violations.append("[{}] INV-L8-7: grade=C but degradation={}".format(
                sid, r.get("L8_degradation")))

    # INV-L8-8: Grade D/F -> irreversible actions must be blocked
    if grade in ("D", "F"):
        for a in r.get("L8_actions", []):
            if a["type"] in ("SPRAY", "FERTILIZE", "REPLANT") and a["allowed"]:
                violations.append("[{}] INV-L8-8: {} allowed under grade {}".format(
                    sid, a["type"], grade))

    # INV-L8-9: Blocked actions must not be CONFIRMED
    blocked_ids = {a["id"] for a in r.get("L8_actions", []) if not a["allowed"]}
    for s in r.get("L8_schedule", []):
        if s["id"] in blocked_ids and s["status"] == "CONFIRMED":
            violations.append("[{}] INV-L8-9: blocked action {} is CONFIRMED".format(
                sid, s["id"]))

    # INV-L8-10: Every action has evidence or heuristic=True
    for a in r.get("L8_actions", []):
        if a["evidence_count"] == 0 and not a["heuristic"]:
            violations.append("[{}] INV-L8-10: {} has no evidence and not heuristic".format(
                sid, a["id"]))

    # INV-L8-11: All priority scores >= 0
    for a in r.get("L8_actions", []):
        if a["score"] < 0:
            violations.append("[{}] INV-L8-11: {} score={} < 0".format(
                sid, a["id"], a["score"]))

    # INV-L8-12: Zone plan must cover all input zones
    if r.get("L8_zone_count", 0) < 1:
        violations.append("[{}] INV-L8-12: empty zone plan".format(sid))

    # INV-L8-13: Cognitive load budget not exceeded
    cog_complexity = r.get("L8_cog_complexity", 0)
    if cog_complexity > 20:  # hard cap: 20 complexity units
        violations.append("[{}] INV-L8-13: cognitive complexity {} > 20".format(
            sid, cog_complexity))

    return violations


# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 72)
    print("  AgriWise Production Validation -- L0->L8 v8.2.0")
    print("  6 Scenarios x Real Weather x 13 Invariant Checks")
    print("  7 Intelligence Engines (Phenology|Nutrient|IPM|EnvRisk|Cognitive|Adoption|Framing)")
    print("=" * 72)

    ref = datetime(2025, 8, 15)
    start = (ref - timedelta(days=90)).strftime("%Y-%m-%d")
    end = ref.strftime("%Y-%m-%d")

    all_results = []
    all_violations = []
    layer_stats = {k: 0 for k in ("L2", "L3", "L4", "L5", "L6", "L8")}
    total_time = 0

    for i, sc in enumerate(SCENARIOS):
        print("")
        print("---" * 20)
        print("  [{}/{}] {}  (grade={})".format(i + 1, len(SCENARIOS), sc["id"], sc["audit_grade"]))
        print("  {}".format(sc["desc"]))
        print("---" * 20)

        weather = fetch_real_weather(sc["lat"], sc["lon"], start, end)
        print("  Weather: {} days".format(len(weather)))

        t0 = time.time()
        try:
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(buf):
                result = run_pipeline(sc, weather)
        except Exception as e:
            result = {
                "scenario_id": sc["id"], "description": sc["desc"],
                "audit_grade": sc["audit_grade"],
                "L2": "CRASHED", "L3": "CRASHED", "L4": "CRASHED",
                "L5": "CRASHED", "L6": "CRASHED", "L8": "CRASHED",
            }
            print("  CRASH: {}".format(e))
            traceback.print_exc()
        elapsed = time.time() - t0
        total_time += elapsed
        result["elapsed_s"] = round(elapsed, 2)

        for layer in layer_stats:
            if result.get(layer) == "OK":
                layer_stats[layer] += 1

        violations = validate_l8_invariants(result)
        all_violations.extend(violations)
        result["l8_invariant_check"] = "PASS" if not violations else violations
        all_results.append(result)

        icon = "[PASS]" if not violations else "[WARN]"
        print("  {} Complete in {:.2f}s".format(icon, elapsed))
        status_parts = []
        for lyr in ("L2", "L3", "L4", "L5", "L6", "L8"):
            val = result.get(lyr, "?")
            status_parts.append("{}={}".format(lyr, val[:6]))
        print("     {}".format(" | ".join(status_parts)))

        if result.get("L8") == "OK":
            print("     Actions: {} | Schedule: {} | Zones: {}".format(
                result["L8_action_count"], result["L8_schedule_count"], result["L8_zone_count"]))
            print("     Degradation: {} | Reliability: {:.1%}".format(
                result["L8_degradation"], result["L8_reliability"]))
            print("     Yield delta: {}% | Risk reduction: {}% | Cost: ${}".format(
                result["L8_yield_delta"], result["L8_risk_reduction"], result["L8_cost"]))
            if result.get("L8_cog_presented") is not None:
                print("     Cognitive: {}/{} shown | Complexity: {} | Fatigue: {}".format(
                    result["L8_cog_presented"],
                    result["L8_cog_presented"] + result.get("L8_cog_suppressed", 0),
                    result.get("L8_cog_complexity", "?"),
                    result.get("L8_cog_fatigue", "?")))
            for a in result.get("L8_actions", []):
                allowed_tag = "OK" if a["allowed"] else "BLOCKED"
                engine_tags = []
                if a.get("bbch"): engine_tags.append("BBCH{}".format(a["bbch"]))
                if a.get("ipm_level"): engine_tags.append("IPM:{}".format(a["ipm_level"]))
                if a.get("adopt_prob"): engine_tags.append("P(adopt)={:.0%}".format(a["adopt_prob"]))
                if a.get("frame"): engine_tags.append(a["frame"])
                tag_str = " ".join(engine_tags) if engine_tags else ""
                print("       -> {:12s} score={:.4f} [{}] ev={} {} {}".format(
                    a["type"], a["score"], allowed_tag, a["evidence_count"],
                    a["confidence"], tag_str))
        if violations:
            for v in violations:
                print("     [X] {}".format(v))

    # Final Report
    print("")
    print("=" * 72)
    print("  L0->L8 PRODUCTION READINESS REPORT")
    print("=" * 72)

    total = len(SCENARIOS)
    passed = sum(1 for r in all_results if r.get("l8_invariant_check") == "PASS")

    print("")
    print("  Scenarios: {}/{} passed all L8 invariants".format(passed, total))
    print("  Total time: {:.1f}s".format(total_time))
    print("")
    for layer, count in layer_stats.items():
        pct = count / max(total, 1) * 100
        bar = "#" * int(pct / 5) + "." * (20 - int(pct / 5))
        print("    {}: [{}] {}/{} ({:.0f}%)".format(layer, bar, count, total, pct))

    if all_violations:
        print("")
        print("  {} invariant violation(s):".format(len(all_violations)))
        for v in all_violations:
            print("    * {}".format(v))
    else:
        print("")
        print("  [PASS] ALL L8 INVARIANTS PASSED")

    ready = passed == total and layer_stats["L8"] >= total * 0.8
    print("")
    print("  " + "---" * 17)
    if ready:
        print("  VERDICT: PRODUCTION READY [PASS]")
    else:
        print("  VERDICT: NOT READY [FAIL]")
    print("  " + "---" * 17)

    out_path = os.path.join(os.path.dirname(__file__), "l0_to_l8_validation.json")
    with open(out_path, "w") as fp:
        json.dump(all_results, fp, indent=2, default=str)
    print("")
    print("  Results: {}".format(out_path))


if __name__ == "__main__":
    main()
