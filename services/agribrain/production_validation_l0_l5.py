"""
AgriWise Full-Stack Validation Harness (L0 → L5)
================================================
Validates the complete pipeline starting from User Input (Layer 0),
through Fusion (L1 proxy), Intelligence (L2), Decision (L3), Nutrients (L4),
and BioThreat (L5).

Uses real weather data and 10 detailed crop/soil/irrigation scenarios.
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
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(__file__))

# L0 User Input
from layer0.user_input_schema import (
    PlotRegistration, SoilAnalysis, IrrigationEvent, ManagementEvent,
    UserInputPackage,
)
from layer0.user_input_adapter import UserInputAdapter

# Orchestrator & Layers
from orchestrator_v2.schema import OrchestratorInput
from layer1_fusion.schema_legacy import FieldTensor
from layer2_veg_int.runner import run_layer2_veg
from layer3_decision.runner import run_layer3_decision
from layer4_nutrients.runner import run_layer4_nutrients
from layer5_bio.runner import run_layer5_bio


# ============================================================================
# Scenario Definitions (from L0 simulation)
# ============================================================================
SEASON_START = datetime(2026, 5, 1, tzinfo=timezone.utc)
SEASON_DAYS = 90

SCENARIOS = [
    # 1. Corn — Optimal irrigated
    {
        "id": "P01_Corn_Drip_Optimal",
        "registration": {
            "plot_id": "P01", "crop_type": "corn", "variety": "Pioneer P1151",
            "polygon_wkt": "POLYGON((-93.47 42.03, -93.46 42.03, -93.46 42.04, -93.47 42.04, -93.47 42.03))", # Iowa
            "area_ha": 15.0, "planting_date": "2026-05-01",
            "irrigation_type": "drip", "management_goal": "yield_max",
        },
        "soil": {"clay_pct": 22.0, "sand_pct": 40.0, "silt_pct": 38.0,
                 "organic_matter_pct": 2.8, "ph": 6.9, "ec_ds_m": 0.3},
        "scenario": "optimal", "lat": 42.03, "lon": -93.47,
    },
    # 2. Wheat — Rainfed Drought
    {
        "id": "P02_Wheat_Rainfed_Drought",
        "registration": {
            "plot_id": "P02", "crop_type": "wheat", "variety": "Arrehane",
            "polygon_wkt": "POLYGON((-98.79 38.36, -98.78 38.36, -98.78 38.37, -98.79 38.37, -98.79 38.36))", # Kansas
            "area_ha": 20.0, "planting_date": "2026-05-01",
            "irrigation_type": "rainfed", "management_goal": "cost_min",
        },
        "soil": {"clay_pct": 12.0, "sand_pct": 72.0, "silt_pct": 16.0,
                 "organic_matter_pct": 1.2, "ph": 7.5, "ec_ds_m": 0.2},
        "scenario": "drought", "lat": 38.36, "lon": -98.79,
    },
    # 3. Soybean — Flood Irrigation, Waterlogging
    {
        "id": "P03_Soy_Flood_Waterlog",
        "registration": {
            "plot_id": "P03", "crop_type": "soybean",
            "polygon_wkt": "POLYGON((-90.18 33.45, -90.17 33.45, -90.17 33.46, -90.18 33.46, -90.18 33.45))", # Mississippi
            "area_ha": 10.0, "planting_date": "2026-05-01",
            "irrigation_type": "flood",
        },
        "soil": {"clay_pct": 45.0, "sand_pct": 15.0, "silt_pct": 40.0,
                 "organic_matter_pct": 3.5, "ph": 6.2, "ec_ds_m": 0.8},
        "scenario": "waterlogging", "lat": 33.45, "lon": -90.18,
    },
    # 4. Rice — Paddy, Saline Soil
    {
        "id": "P04_Rice_Saline",
        "registration": {
            "plot_id": "P04", "crop_type": "rice",
            "polygon_wkt": "POLYGON((-92.22 30.22, -92.21 30.22, -92.21 30.23, -92.22 30.23, -92.22 30.22))", # Louisiana
            "area_ha": 8.0, "planting_date": "2026-05-01",
            "irrigation_type": "flood",
        },
        "soil": {"clay_pct": 35.0, "sand_pct": 25.0, "silt_pct": 40.0,
                 "organic_matter_pct": 2.0, "ph": 8.2, "ec_ds_m": 4.5}, # SALINE
        "scenario": "salinity", "lat": 30.22, "lon": -92.22,
    },
    # 5. Cotton — Pivot Irrigation, Heat Wave
    {
        "id": "P05_Cotton_Pivot_Heat",
        "registration": {
            "plot_id": "P05", "crop_type": "cotton",
            "polygon_wkt": "POLYGON((-102.08 31.99, -102.07 31.99, -102.07 32.00, -102.08 32.00, -102.08 31.99))", # Texas
            "area_ha": 25.0, "planting_date": "2026-05-01",
            "irrigation_type": "pivot",
        },
        "soil": {"clay_pct": 25.0, "sand_pct": 35.0, "silt_pct": 40.0,
                 "organic_matter_pct": 2.2, "ph": 7.1, "ec_ds_m": 0.4},
        "scenario": "heat_stress", "lat": 31.99, "lon": -102.08,
    },
    # 6. Barley — Rainfed, Lodging
    {
        "id": "P06_Barley_Lodging",
        "registration": {
            "plot_id": "P06", "crop_type": "barley",
            "polygon_wkt": "POLYGON((-111.29 47.50, -111.28 47.50, -111.28 47.51, -111.29 47.51, -111.29 47.50))", # Montana
            "area_ha": 12.0, "planting_date": "2026-05-01",
            "irrigation_type": "rainfed",
        },
        "soil": {"clay_pct": 30.0, "sand_pct": 30.0, "silt_pct": 40.0,
                 "organic_matter_pct": 3.0, "ph": 6.5, "ec_ds_m": 0.3},
        "scenario": "lodging", "lat": 47.50, "lon": -111.29,
    },
    # 7. Potato — Sprinkler, Insect Pressure
    {
        "id": "P07_Potato_Insects",
        "registration": {
            "plot_id": "P07", "crop_type": "potato",
            "polygon_wkt": "POLYGON((-116.21 43.61, -116.20 43.61, -116.20 43.62, -116.21 43.62, -116.21 43.61))", # Idaho
            "area_ha": 5.0, "planting_date": "2026-05-01",
            "irrigation_type": "sprinkler",
        },
        "soil": {"clay_pct": 18.0, "sand_pct": 45.0, "silt_pct": 37.0,
                 "organic_matter_pct": 4.0, "ph": 6.0, "ec_ds_m": 0.2},
        "scenario": "insect_pressure", "lat": 43.61, "lon": -116.21,
    },
    # 8. Sorghum — Drip, Progressive Transpiration Failure
    {
        "id": "P08_Sorghum_TF",
        "registration": {
            "plot_id": "P08", "crop_type": "sorghum",
            "polygon_wkt": "POLYGON((-96.70 40.82, -96.69 40.82, -96.69 40.83, -96.70 40.83, -96.70 40.82))", # Nebraska
            "area_ha": 18.0, "planting_date": "2026-05-01",
            "irrigation_type": "drip",
        },
        "soil": {"clay_pct": 15.0, "sand_pct": 65.0, "silt_pct": 20.0,
                 "organic_matter_pct": 1.0, "ph": 7.8, "ec_ds_m": 0.5},
        "scenario": "transpiration_failure", "lat": 40.82, "lon": -96.70,
    },
    # 9. Canola — Data Gap scenario (cloud cover blocks sensors)
    {
        "id": "P09_Canola_DataGap",
        "registration": {
            "plot_id": "P09", "crop_type": "canola",
            "polygon_wkt": "POLYGON((-101.30 48.23, -101.29 48.23, -101.29 48.24, -101.30 48.24, -101.30 48.23))", # North Dakota
            "area_ha": 14.0, "planting_date": "2026-05-01",
            "irrigation_type": "rainfed",
        },
        "soil": {"clay_pct": 28.0, "sand_pct": 32.0, "silt_pct": 40.0,
                 "organic_matter_pct": 2.5, "ph": 6.7, "ec_ds_m": 0.3},
        "scenario": "data_gap", "lat": 48.23, "lon": -101.30,
    },
    # 10. Alfalfa — Tillage bare soil
    {
        "id": "P10_Alfalfa_Tillage",
        "registration": {
            "plot_id": "P10", "crop_type": "alfalfa",
            "polygon_wkt": "POLYGON((-119.77 36.74, -119.76 36.74, -119.76 36.75, -119.77 36.75, -119.77 36.74))", # California
            "area_ha": 10.0, "planting_date": "2026-05-01",
            "irrigation_type": "flood",
        },
        "soil": {"clay_pct": 20.0, "sand_pct": 40.0, "silt_pct": 40.0,
                 "organic_matter_pct": 3.2, "ph": 7.0, "ec_ds_m": 0.25},
        "scenario": "tillage", "lat": 36.74, "lon": -119.77,
    },
]

# ============================================================================
# Weather & Synthetic Signals
# ============================================================================

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
# FieldTensor Hydration
# ============================================================================

def build_hydrated_field_tensor(plot_id, scenario_cfg, weather, ndvi_series, vv_series, vh_series, soil_props):
    days = min(len(weather), len(ndvi_series))
    plot_ts = []
    
    for i in range(days):
        w = weather[i]
        t_mean = (w["t_max"] + w["t_min"]) / 2.0
        gdd_day = max(0.0, t_mean - 10.0)
        
        is_observed = (i % 5 == 0)
        if scenario_cfg["scenario"] == "data_gap" and 50 < i < 70:
            is_observed = False
            
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

    return FieldTensor(
        plot_id=plot_id,
        run_id=f"l1_sim_{plot_id}",
        version="2.0.0-sim",
        time_index=[w["date"] for w in weather[:days]],
        channels=[], data=[], grid={}, maps={}, zones={}, zone_stats={},
        plot_timeseries=plot_ts, forecast_7d=[],
        static=static_props,
        provenance={"source": "L0_to_L5_harness", "layer0_reliability": 0.90},
        daily_state={}, state_uncertainty={}, provenance_log=[],
        spatial_reliability={}, boundary_info={},
    )


# ============================================================================
# Main Pipeline Runner
# ============================================================================

def main():
    print("=" * 80)
    print("  AgriWise Full-Stack Validation (L0 -> L5)")
    print("  10 Scenarios using UserInputAdapter + Real Weather")
    print("=" * 80)

    ref = datetime(2025, 8, 15)
    start_str = (ref - timedelta(days=SEASON_DAYS)).strftime("%Y-%m-%d")
    end_str = ref.strftime("%Y-%m-%d")

    all_results = []
    layer_stats = {"L0": 0, "L2": 0, "L3": 0, "L4": 0, "L5": 0}
    
    for i, sc in enumerate(SCENARIOS):
        pid = sc["id"]
        print(f"\n--- [{i+1}/10] {pid} ---")
        
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
            
            result["L0_status"] = "OK"
            result["soil_texture"] = soil_props.get("texture_class", "unknown")
            layer_stats["L0"] += 1
        except Exception as e:
            result["L0_status"] = "FAILED"
            result["L0_error"] = str(e)
            print(f"  [!] L0 Failed: {e}")
            all_results.append(result)
            continue
            
        # === LAYER 1 (Proxy) ===
        weather = fetch_real_weather(sc["lat"], sc["lon"], start_str, end_str)
        if not weather:
            weather = [{"date": (ref - timedelta(days=d)).strftime("%Y-%m-%d"), "t_max":25, "t_min":15, "rain_mm":2, "et0":4} for d in range(SEASON_DAYS, -1, -1)]
            
        days = min(SEASON_DAYS, len(weather))
        ndvi = generate_ndvi_series(weather, sc["scenario"], days)
        vv, vh = generate_sar_series(weather, sc["scenario"], days)
        tensor = build_hydrated_field_tensor(pid, sc, weather[:days], ndvi, vv, vh, soil_props)
        
        # Build L3 input context from L0 overrides
        inputs = OrchestratorInput(
            plot_id=pid,
            geometry_hash="geom123",
            date_range={"start": weather[0]["date"], "end": weather[days-1]["date"]},
            crop_config={
                "crop": ctx_overrides.get("crop_type"),
                "variety": ctx_overrides.get("variety"),
                "planting_date": ctx_overrides.get("planting_date"),
                "lat": sc["lat"], "lon": sc["lon"]
            },
            operational_context={
                "irrigation_type": ctx_overrides.get("irrigation_type"),
                "management_goal": ctx_overrides.get("management_goal"),
                "lat": sc["lat"], "lon": sc["lon"]
            },
            policy_snapshot={}
        )

        # === LAYER 2 ===
        l2_out = None
        try:
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(buf):
                l2_out = run_layer2_veg(inputs, tensor)
            result["L2_status"] = "OK"
            layer_stats["L2"] += 1
        except Exception as e:
            result["L2_status"] = "FAILED"
            result["error"] = str(e)
            print(f"  [!] L2 Failed: {e}")
            all_results.append(result)
            continue

        # === LAYER 3 ===
        l3_out = None
        try:
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(buf):
                l3_out = run_layer3_decision(inputs, tensor, l2_out)
            result["L3_status"] = "OK"
            layer_stats["L3"] += 1
        except Exception as e:
            result["L3_status"] = "FAILED"
            result["error"] = str(e)
            print(f"  [!] L3 Failed: {e}")
            all_results.append(result)
            continue
            
        # === LAYER 4 ===
        l4_out = None
        try:
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(buf):
                l4_out = run_layer4_nutrients(inputs, tensor, l2_out, l3_out)
            result["L4_status"] = "OK"
            layer_stats["L4"] += 1
        except Exception as e:
            result["L4_status"] = "FAILED"
            result["error"] = str(e)
            print(f"  [!] L4 Failed: {e}")
            all_results.append(result)
            continue
            
        # === LAYER 5 ===
        l5_out = None
        try:
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(buf):
                l5_out = run_layer5_bio(inputs, tensor, l2_out, l3_out, l4_out)
            result["L5_status"] = "OK"
            
            threats = l5_out.threat_states or {}
            if threats:
                top_t = max(threats.values(), key=lambda x: x.probability)
                result["L5_top_threat"] = f"{top_t.threat_id.value} (p={top_t.probability:.1%})"
            else:
                result["L5_top_threat"] = "None"
            
            layer_stats["L5"] += 1
            print(f"  [OK] Full pipeline succeeded! Top BioThreat: {result['L5_top_threat']}")
        except Exception as e:
            result["L5_status"] = "FAILED"
            result["error"] = str(e)
            print(f"  [!] L5 Failed: {e}")
            all_results.append(result)
            continue
            
        all_results.append(result)

    print("\n" + "=" * 80)
    print("  L0 -> L5 VALIDATION SUMMARY")
    print("=" * 80)
    for k, v in layer_stats.items():
        print(f"  {k}: {v}/10 passed")
        
    passed_all = layer_stats["L5"] == 10
    print(f"\n  VERDICT: {'PRODUCTION READY' if passed_all else 'FAILED'}")
    
    out_path = os.path.join(os.path.dirname(__file__), "l0_to_l5_validation.json")
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"  Results saved to: {out_path}")

if __name__ == "__main__":
    main()
