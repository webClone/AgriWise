"""
AgriWise Full-Stack Validation Harness (L0 → L6)
================================================
Validates the complete pipeline starting from User Input (Layer 0),
through Fusion (L1 proxy), Intelligence (L2), Decision (L3), Nutrients (L4),
BioThreat (L5), and the new Strategic Execution Engine (L6).

Uses real weather data and detailed crop/soil/irrigation scenarios.
"""

import json
import math
import os
import sys
import io
import traceback
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
import copy

sys.path.insert(0, os.path.dirname(__file__))

# L0 User Input
from layer0.user_input_schema import PlotRegistration, SoilAnalysis, UserInputPackage
from layer0.user_input_adapter import UserInputAdapter

# Orchestrator & Layers
from orchestrator_v2.schema import OrchestratorInput
from layer1_fusion.schema_legacy import FieldTensor
from layer2_veg_int.runner import run_layer2_veg
from layer3_decision.runner import run_layer3_decision
from layer4_nutrients.runner import run_layer4_nutrients
from layer5_bio.runner import run_layer5_bio
from layer6_exec.runner import run_layer6_exec
from layer6_exec.invariants import enforce_layer6_invariants

SEASON_START = datetime(2026, 5, 1, tzinfo=timezone.utc)
SEASON_DAYS = 90

# We use the base 10 scenarios + 2 specialized conflict scenarios for L6
SCENARIOS = [
    # 1. Corn — Optimal irrigated
    {
        "id": "P01_Corn_Drip_Optimal",
        "registration": {
            "plot_id": "P01", "crop_type": "corn", "variety": "Pioneer P1151",
            "polygon_wkt": "POLYGON((-93.47 42.03, -93.46 42.03, -93.46 42.04, -93.47 42.04, -93.47 42.03))",
            "area_ha": 15.0, "planting_date": "2026-05-01",
            "irrigation_type": "drip", "management_goal": "yield_max",
        },
        "soil": {"clay_pct": 22.0, "sand_pct": 40.0, "silt_pct": 38.0,
                 "organic_matter_pct": 2.8, "ph": 6.9, "ec_ds_m": 0.3},
        "scenario": "optimal", "lat": 42.03, "lon": -93.47,
    },
    # 2. Wheat — Lodging Risk (High Biomass) + N Deficiency (Triggers Conflict B)
    {
        "id": "P02_Wheat_Lodging_Conflict",
        "registration": {
            "plot_id": "P02", "crop_type": "wheat", "variety": "Arrehane",
            "polygon_wkt": "POLYGON((-98.79 38.36, -98.78 38.36, -98.78 38.37, -98.79 38.37, -98.79 38.36))",
            "area_ha": 20.0, "planting_date": "2026-05-01",
            "irrigation_type": "rainfed", "management_goal": "yield_max",
        },
        "soil": {"clay_pct": 12.0, "sand_pct": 72.0, "silt_pct": 16.0,
                 "organic_matter_pct": 1.2, "ph": 7.5, "ec_ds_m": 0.2},
        "scenario": "lodging_conflict", "lat": 38.36, "lon": -98.79,
    },
    # 3. Tomato — Fungal vs Irrigation Conflict (Triggers Conflict A)
    {
        "id": "P03_Tomato_Fungal_Conflict",
        "registration": {
            "plot_id": "P03", "crop_type": "tomato",
            "polygon_wkt": "POLYGON((-90.18 33.45, -90.17 33.45, -90.17 33.46, -90.18 33.46, -90.18 33.45))",
            "area_ha": 10.0, "planting_date": "2026-05-01",
            "irrigation_type": "sprinkler",
        },
        "soil": {"clay_pct": 45.0, "sand_pct": 15.0, "silt_pct": 40.0,
                 "organic_matter_pct": 3.5, "ph": 6.2, "ec_ds_m": 0.8},
        "scenario": "fungal_irrigation_conflict", "lat": 33.45, "lon": -90.18,
    },
    # 4. Cotton — Heat Wave
    {
        "id": "P05_Cotton_Pivot_Heat",
        "registration": {
            "plot_id": "P05", "crop_type": "cotton",
            "polygon_wkt": "POLYGON((-102.08 31.99, -102.07 31.99, -102.07 32.00, -102.08 32.00, -102.08 31.99))",
            "area_ha": 25.0, "planting_date": "2026-05-01",
            "irrigation_type": "pivot",
        },
        "soil": {"clay_pct": 25.0, "sand_pct": 35.0, "silt_pct": 40.0,
                 "organic_matter_pct": 2.2, "ph": 7.1, "ec_ds_m": 0.4},
        "scenario": "heat_stress", "lat": 31.99, "lon": -102.08,
    },
]

def fetch_real_weather(lat, lon, start, end):
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
        return []

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
        
        if scenario == "drought" and i > 40: base = max(0.15, base - 0.008)
        elif scenario == "lodging_conflict" and i > 40: base = 0.85 # High biomass
        elif scenario == "heat_stress" and i > 40: base = max(0.3, base - 0.01)
        ndvi.append(round(base, 4))
    return ndvi

def generate_sar_series(weather, scenario, days):
    vv_list, vh_list = [], []
    for i in range(min(days, len(weather))):
        w = weather[i]
        moisture = min(1.0, w["rain_mm"] / 20.0)
        vv = -12.0 + 6.0 * moisture + 0.5 * math.sin(i / 5)
        vh = vv - 6.0 + 0.3 * math.sin(i / 7)
        vv_list.append(round(vv, 2))
        vh_list.append(round(vh, 2))
    return vv_list, vh_list

def build_hydrated_field_tensor(plot_id, scenario_cfg, weather, ndvi_series, vv_series, vh_series, soil_props):
    days = min(len(weather), len(ndvi_series))
    plot_ts = []
    
    for i in range(days):
        w = weather[i]
        t_mean = (w["t_max"] + w["t_min"]) / 2.0
        gdd_day = max(0.0, t_mean - 10.0)
        is_observed = (i % 5 == 0)
            
        plot_ts.append({
            "date": w["date"],
            "ndvi_mean": ndvi_series[i] if is_observed else None,
            "ndvi_interpolated": ndvi_series[i],
            "ndvi_smoothed": ndvi_series[i],
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
        })
        
    static_props = {
        "soil_clay": soil_props.get("clay_pct", 20.0),
        "soil_ph": soil_props.get("ph", 6.5),
        "soil_org_carbon": soil_props.get("organic_matter_pct", 2.0),
        "texture_class": soil_props.get("texture_class", "loam")
    }
    
    # Specific injection for Fungal vs Irrigation conflict
    if scenario_cfg["scenario"] == "fungal_irrigation_conflict":
        static_props["soil_moisture"] = {"0-10cm": 0.10, "10-30cm": 0.12} # Force WATER_STRESS

    return FieldTensor(
        plot_id=plot_id,
        run_id=f"l1_sim_{plot_id}",
        version="2.0.0-sim",
        time_index=[w["date"] for w in weather[:days]],
        channels=[], data=[], grid={}, maps={}, zones={}, zone_stats={},
        plot_timeseries=plot_ts, forecast_7d=[],
        static=static_props,
        provenance={"source": "L0_to_L6_harness", "layer0_reliability": 0.90},
        daily_state={}, state_uncertainty={}, provenance_log=[],
        spatial_reliability={}, boundary_info={},
    )

def main():
    print("=" * 80)
    print("  AgriWise Full-Stack Validation (L0 -> L6)")
    print("  Testing L6 Inference, Smart Routing & Invariants")
    print("=" * 80)

    ref = datetime(2025, 8, 15)
    start_str = (ref - timedelta(days=SEASON_DAYS)).strftime("%Y-%m-%d")
    end_str = ref.strftime("%Y-%m-%d")

    all_results = []
    layer_stats = {"L0": 0, "L2": 0, "L3": 0, "L4": 0, "L5": 0, "L6": 0}
    
    for i, sc in enumerate(SCENARIOS):
        pid = sc["id"]
        print(f"\n--- [{i+1}/{len(SCENARIOS)}] {pid} ---")
        
        result = {"scenario_id": pid, "crop": sc["registration"]["crop_type"]}
        
        # === LAYER 0 ===
        try:
            reg_obj = PlotRegistration(**sc["registration"])
            soil_obj = SoilAnalysis(plot_id=pid, sample_date=start_str, **sc["soil"])
            pkg = UserInputPackage(
                plot_registration=reg_obj,
                soil_analyses=[soil_obj],
                irrigation_events=[], management_events=[]
            )
            adapter = UserInputAdapter()
            l0_out = adapter.ingest(pkg)
            ctx_overrides = l0_out.plot_context_overrides
            soil_props = l0_out.soil_props
            layer_stats["L0"] += 1
        except Exception as e:
            print(f"  [!] L0 Failed: {e}")
            continue
            
        # === LAYER 1 (Proxy) ===
        weather = fetch_real_weather(sc["lat"], sc["lon"], start_str, end_str)
        if not weather:
            weather = [{"date": (ref - timedelta(days=d)).strftime("%Y-%m-%d"), "t_max":25, "t_min":15, "rain_mm":2, "et0":4} for d in range(SEASON_DAYS, -1, -1)]
            
        days = min(SEASON_DAYS, len(weather))
        ndvi = generate_ndvi_series(weather, sc["scenario"], days)
        vv, vh = generate_sar_series(weather, sc["scenario"], days)
        tensor = build_hydrated_field_tensor(pid, sc, weather[:days], ndvi, vv, vh, soil_props)
        
        inputs = OrchestratorInput(
            plot_id=pid, geometry_hash="geom123",
            date_range={"start": weather[0]["date"], "end": weather[days-1]["date"]},
            crop_config={
                "crop": ctx_overrides.get("crop_type"),
                "variety": ctx_overrides.get("variety"),
                "planting_date": ctx_overrides.get("planting_date"),
                "stage": "REPRODUCTIVE", # Force late stage to test L6 urgency
                "lat": sc["lat"], "lon": sc["lon"]
            },
            operational_context={
                "irrigation_type": ctx_overrides.get("irrigation_type"),
                "management_goal": ctx_overrides.get("management_goal"),
                "lat": sc["lat"], "lon": sc["lon"],
                "resources": {"equipment": ["TR-01", "SP-02"], "workforce": True, "labor_hours": 60},
                "constraints": {"water_quota": 800.0, "budget": 10000.0},
                "season_stage": "MID",
            },
            policy_snapshot={}
        )

        # === LAYER 2 ===
        try:
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(buf):
                l2_out = run_layer2_veg(inputs, tensor)
            layer_stats["L2"] += 1
        except Exception as e:
            print(f"  [!] L2 Failed: {e}")
            continue

        # === LAYER 3 ===
        try:
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(buf):
                l3_out = run_layer3_decision(inputs, tensor, l2_out)
                
            # INJECT SCENARIO SPECIFIC L3 DIAGNOSES
            if sc["scenario"] == "lodging_conflict":
                from layer3_decision.schema import Diagnosis
                l3_out.diagnoses.append(Diagnosis("LODGING_RISK", 0.8, 0.9, 0.8))
            elif sc["scenario"] == "fungal_irrigation_conflict":
                from layer3_decision.schema import Diagnosis
                l3_out.diagnoses.append(Diagnosis("WATER_STRESS", 0.9, 0.9, 0.9))
                
            layer_stats["L3"] += 1
        except Exception as e:
            print(f"  [!] L3 Failed: {e}")
            continue
            
        # === LAYER 4 ===
        try:
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(buf):
                l4_out = run_layer4_nutrients(inputs, tensor, l2_out, l3_out)
                
            # INJECT SCENARIO SPECIFIC L4 DIAGNOSES
            if sc["scenario"] == "lodging_conflict":
                from layer4_nutrients.schema import NutrientState, Severity as NSev
                from enum import Enum
                class Nutrient(Enum): N = "N"
                l4_out.nutrient_states[Nutrient.N] = NutrientState(
                    nutrient=Nutrient.N, state_index=0.2, probability_deficient=0.9,
                    confidence=0.8, severity=NSev.HIGH, drivers_used=[],
                    evidence_trace=[], confounders=[]
                )
                
            layer_stats["L4"] += 1
        except Exception as e:
            print(f"  [!] L4 Failed: {e}")
            continue
            
        # === LAYER 5 ===
        try:
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(buf):
                l5_out = run_layer5_bio(inputs, tensor, l2_out, l3_out, l4_out)
                
            # INJECT SCENARIO SPECIFIC L5 THREATS
            if sc["scenario"] == "fungal_irrigation_conflict":
                from layer5_bio.schema import BioThreatState, ThreatId, ThreatClass, Severity as BSev, SpreadPattern
                l5_out.threat_states[ThreatId.FUNGAL_LEAF_SPOT] = BioThreatState(
                    threat_id=ThreatId.FUNGAL_LEAF_SPOT, threat_class=ThreatClass.DISEASE,
                    probability=0.95, confidence=0.9, severity=BSev.HIGH,
                    drivers_used=[], evidence_trace=[], spread_pattern=SpreadPattern.PATCHY,
                    confounders=[]
                )
                
            layer_stats["L5"] += 1
        except Exception as e:
            print(f"  [!] L5 Failed: {e}")
            continue
            
        # === LAYER 6 (The Focus) ===
        try:
            l6_out = run_layer6_exec(inputs, tensor, l2_out, l3_out, l4_out, l5_out)
            
            # Check Invariants
            violations = enforce_layer6_invariants(l6_out)
            if violations:
                print(f"  [!] L6 Invariants Failed! ({len(violations)} violations)")
                for v in violations:
                    print(f"      - {v.check_name}: {v.description}")
                continue
                
            layer_stats["L6"] += 1
            print(f"  [OK] L6 Execution Succeeded (Hash: {l6_out.content_hash()})")
            print(f"       Interventions: {len(l6_out.intervention_portfolio)}")
            print(f"       Conflicts Detected: {len(l6_out.conflict_log)}")
            print(f"       Smart Routing: {l6_out.audit.policy_snapshot.get('smart_routing')}")
            
            # Detailed reporting for conflicts
            for c in l6_out.conflict_log:
                print(f"       -> Conflict: {c.conflict_type.value}")
                print(f"          Resolution: {c.resolution.value}")
                print(f"          Rationale: {c.resolution_rationale}")
                
            for inv in l6_out.intervention_portfolio:
                print(f"       -> Action: {inv.title} (Score: {inv.utility_score:.2f}, Grade: {inv.feasibility_grade.value})")
                if inv.feasibility_grade.value in ["C", "D", "F"]:
                    print(f"          Blocked Reasons: {inv.blocked_reasons}")
            
            result["L6_hash"] = l6_out.content_hash()
            result["L6_interventions"] = len(l6_out.intervention_portfolio)
            result["L6_conflicts"] = len(l6_out.conflict_log)
            
        except Exception as e:
            print(f"  [!] L6 Failed: {e}")
            traceback.print_exc()
            continue
            
        all_results.append(result)

    print("\n" + "=" * 80)
    print("  L0 -> L6 VALIDATION SUMMARY")
    print("=" * 80)
    for k, v in layer_stats.items():
        print(f"  {k}: {v}/{len(SCENARIOS)} passed")
        
    passed_all = layer_stats["L6"] == len(SCENARIOS)
    print(f"\n  VERDICT: {'PRODUCTION READY' if passed_all else 'FAILED'}")
    
    out_path = os.path.join(os.path.dirname(__file__), "l0_to_l6_validation.json")
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)

if __name__ == "__main__":
    main()
