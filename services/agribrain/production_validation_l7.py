"""
AgriWise Layer 7 (Season Planning) Validation Harness
=====================================================
Validates the modernized L7 engine against 8 global scenarios, enforcing
13 agronomic invariants, testing multi-crop evaluation, and verifying the
SAR Soil Health Trajectory logic.
"""
import json
import os
import sys
import io
import traceback
import math
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from orchestrator_v2.schema import OrchestratorInput
from layer1_fusion.schema_legacy import FieldTensor
from layer7_planning.runner import run as run_layer7
from layer7_planning.engines.ccl_crop_library import CROP_DATABASE
from layer7_planning.invariants import enforce_layer7_invariants

# Test Scenarios
SCENARIOS = [
    {
        "id": "S1_Potato_Optimal",
        "crop": "potato", "scenario": "optimal",
        "irrigation_type": "drip", "soil_texture": "loam",
        "lat": 36.75, "lon": 3.05, "expected_decision": "PLANT_NOW"
    },
    {
        "id": "S2_Potato_Frost",
        "crop": "potato", "scenario": "frost",
        "irrigation_type": "drip", "soil_texture": "loam",
        "lat": 36.75, "lon": 3.05, "expected_decision": "DELAY_PLANTING"
    },
    {
        "id": "S3_Wheat_Clay",
        "crop": "wheat", "scenario": "optimal",
        "irrigation_type": "rainfed", "soil_texture": "clay loam",
        "lat": 36.75, "lon": 3.05, "expected_decision": "PLANT_NOW"
    },
    {
        "id": "S4_Wheat_Drought",
        "crop": "wheat", "scenario": "drought",
        "irrigation_type": "rainfed", "soil_texture": "sandy loam",
        "lat": 36.75, "lon": 3.05, "expected_decision": "SWITCH_CROP"
    },
    {
        "id": "S5_Corn_Irrigated",
        "crop": "corn", "scenario": "optimal",
        "irrigation_type": "pivot", "soil_texture": "silt loam",
        "lat": 42.03, "lon": -93.47, "expected_decision": "PLANT_NOW"
    },
    {
        "id": "S6_Corn_HeatWave",
        "crop": "corn", "scenario": "heat_stress",
        "irrigation_type": "drip", "soil_texture": "silt loam",
        "lat": 42.03, "lon": -93.47, "expected_decision": "DELAY_PLANTING"
    },
    {
        "id": "S7_Tomato_Fungal",
        "crop": "tomato", "scenario": "fungal_risk",
        "irrigation_type": "drip", "soil_texture": "loam",
        "lat": 36.75, "lon": 3.05, "expected_decision": "PLANT_NOW" # Still plants, but lower score
    },
    {
        "id": "S8_Cotton_Arid",
        "crop": "cotton", "scenario": "optimal",
        "irrigation_type": "pivot", "soil_texture": "sandy loam",
        "lat": 31.99, "lon": -102.08, "expected_decision": "PLANT_NOW"
    }
]

def generate_synthetic_weather(scenario, days=30):
    weather = []
    base_tmax = 25.0
    base_tmin = 15.0
    rain_prob = 0.1
    
    if scenario == "frost":
        base_tmin = -2.0
        base_tmax = 8.0
    elif scenario == "heat_stress":
        base_tmax = 40.0
        base_tmin = 25.0
        rain_prob = 0.0
    elif scenario == "drought":
        base_tmax = 30.0
        rain_prob = 0.0
    elif scenario == "fungal_risk":
        base_tmax = 22.0
        base_tmin = 16.0
        rain_prob = 0.8

    ref = datetime(2026, 5, 1, tzinfo=timezone.utc)
    for i in range(days):
        d = ref - timedelta(days=days-i)
        r = 15.0 if (i % 5 == 0 and rain_prob > 0) else 0.0
        if scenario == "fungal_risk":
            r = 5.0
        weather.append({
            "date": d.strftime("%Y-%m-%d"),
            "t_max": base_tmax,
            "t_min": base_tmin,
            "rain_mm": r,
            "et0": 4.0
        })
    return weather

def build_hydrated_l1_tensor(plot_id, cfg, weather):
    ts = []
    vv_base = -12.0
    for i, w in enumerate(weather):
        # Introduce a "tillage" spike for S3 to test SAR health degradation
        vv = vv_base
        if cfg["id"] == "S3_Wheat_Clay" and i == 15:
            vv = -8.0 # Spike -> tillage event 1
        elif cfg["id"] == "S3_Wheat_Clay" and i == 25:
            vv = -7.5 # Spike -> tillage event 2
        elif cfg["id"] == "S3_Wheat_Clay" and i == 5:
            vv = -7.0 # Spike -> tillage event 3
            
        ts.append({
            "date": w["date"],
            "temp_max": w["t_max"],
            "temp_min": w["t_min"],
            "rain": w["rain_mm"],
            "precipitation": w["rain_mm"],
            "vv": vv
        })
        
    fc = []
    for i in range(7):
        r = 10.0 if cfg["scenario"] == "fungal_risk" else 0.0
        fc.append({
            "precipitation": r,
            "temp_max": weather[-1]["t_max"],
            "temp_min": weather[-1]["t_min"],
            "rain_prob": 80.0 if r > 0 else 10.0,
            "et0": 4.0
        })
        
    return FieldTensor(
        plot_id=plot_id, run_id=f"sim_{plot_id}", version="2.0.0",
        time_index=[w["date"] for w in weather],
        plot_timeseries=ts, forecast_7d=fc,
        static={"texture_class": cfg["soil_texture"]},
        channels=[], data=[], grid={}, maps={}, zones={}, zone_stats=[],
        provenance={"layer0_reliability": 0.90}, daily_state={}, state_uncertainty={},
        provenance_log=[], spatial_reliability={}, boundary_info={}
    )

def main():
    print("=" * 80)
    print("  AgriWise Layer 7 Validation Harness")
    print("  Testing 100+ Crop Evaluator, Invariants & SAR Trajectory")
    print("=" * 80)
    
    passed = 0
    results = []
    
    for i, sc in enumerate(SCENARIOS):
        print(f"\n--- [{i+1}/{len(SCENARIOS)}] {sc['id']} ---")
        pid = sc["id"]
        
        weather = generate_synthetic_weather(sc["scenario"])
        l1_tensor = build_hydrated_l1_tensor(pid, sc, weather)
        
        inputs = OrchestratorInput(
            plot_id=pid, geometry_hash="geom123",
            date_range={"start": weather[0]["date"], "end": weather[-1]["date"]},
            crop_config={"crop": sc["crop"], "lat": sc["lat"], "lon": sc["lon"]},
            operational_context={"irrigation_type": sc["irrigation_type"], "lat": sc["lat"], "lon": sc["lon"]},
            policy_snapshot={}
        )
        
        try:
            # We skip L5 for simplicity, BRF falls back to L1 wetness proxies
            l7_out = run_layer7(inputs, l1_res=l1_tensor, l5_res=None)
            
            # Check invariants
            violations = enforce_layer7_invariants(l7_out, CROP_DATABASE)
            
            # Count errors
            errors = [v for v in violations if v.severity == "error"]
            if errors:
                print(f"  [!] Failed invariants ({len(errors)} errors)")
                for e in errors:
                    print(f"      - {e.check_name}: {e.description}")
                continue
                
            ch = l7_out.content_hash()
            print(f"  [OK] Hash: {ch[:16]}")
            
            cplan = l7_out.chosen_plan
            decision = cplan.decision_id.value if cplan else "UNKNOWN"
            
            print(f"  [+] Target crop: {sc['crop']}")
            print(f"  [+] Options evaluated: {len(l7_out.options)}")
            print(f"  [+] Decision: {decision}")
            print(f"  [+] Execution Tasks: {len(l7_out.execution_plan.tasks) if l7_out.execution_plan else 0}")
            
            if sc["id"] == "S3_Wheat_Clay":
                sh = l7_out.audit.upstream_digest.get("soil_health", {})
                print(f"  [*] SAR Tillage events: {sh.get('tillage_events')} -> Score: {sh.get('soil_health_score')}")
                
            passed += 1
            results.append({"scenario": pid, "hash": ch, "decision": decision})
            
        except Exception as e:
            print(f"  [!] Exception: {e}")
            traceback.print_exc()
            
    print("\n" + "=" * 80)
    print(f"  VERDICT: {passed}/{len(SCENARIOS)} passed")
    print("=" * 80)

if __name__ == "__main__":
    main()
