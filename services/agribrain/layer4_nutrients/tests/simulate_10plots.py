"""
10-Plot Seasonal Simulation for Layer 4 v2.0.
"""
import json
from layer4_nutrients.runner import run_layer4_standalone

PLOTS = [
    {"id": "P1", "name": "Corn Irrigated NVZ", "crop": "corn", "irrig": "drip",
     "soil": {"nitrogen_ppm": 12, "phosphorus_ppm": 25, "potassium_ppm": 150, "ph": 6.8, "clay_pct": 30, "organic_matter_pct": 2.5},
     "ndvi": 0.75, "ndre": 0.35, "sar": (-12, -11, None, None, 0.1), "goal": "yield_max",
     "constraints": {"nitrogen_limit_kg_ha": 170}},
    {"id": "P2", "name": "Wheat Rainfed N-Deficit", "crop": "wheat", "irrig": "rainfed",
     "soil": {"nitrogen_ppm": 5, "ph": 7.2, "clay_pct": 20, "organic_matter_pct": 1.2},
     "ndvi": 0.50, "ndre": 0.20, "sar": (-10, -4, None, None, 0.4), "goal": "yield_max", "constraints": {}},
    {"id": "P3", "name": "Soybean No-Till High SOC", "crop": "soybean", "irrig": "rainfed",
     "soil": {"nitrogen_ppm": 20, "phosphorus_ppm": 8, "potassium_ppm": 180, "ph": 6.2, "clay_pct": 25, "organic_matter_pct": 4.0},
     "ndvi": 0.82, "ndre": 0.40, "sar": (-13, -12.5, None, None, 0.05), "goal": "sustainable", "constraints": {}},
    {"id": "P4", "name": "Corn Alkaline Volatile", "crop": "corn", "irrig": "rainfed",
     "soil": {"nitrogen_ppm": 10, "ph": 8.2, "clay_pct": 35, "organic_matter_pct": 1.8},
     "ndvi": 0.60, "ndre": None, "sar": (-11, -6, None, None, 0.3), "goal": "yield_max", "constraints": {}},
    {"id": "P5", "name": "Rice Waterlogged", "crop": "rice", "irrig": "flood",
     "soil": {"nitrogen_ppm": 15, "phosphorus_ppm": 12, "potassium_ppm": 90, "ph": 5.5, "clay_pct": 45, "organic_matter_pct": 3.5},
     "ndvi": 0.70, "ndre": 0.30, "sar": None, "goal": "yield_max", "constraints": {}},
    {"id": "P6", "name": "Potato Sandy Leach Risk", "crop": "potato", "irrig": "pivot",
     "soil": {"nitrogen_ppm": 8, "ph": 6.0, "clay_pct": 8, "sand_pct": 75, "organic_matter_pct": 0.8},
     "ndvi": 0.55, "ndre": 0.22, "sar": (-9, -5, None, None, 0.35), "goal": "yield_max", "constraints": {}},
    {"id": "P7", "name": "Barley Cost Min", "crop": "barley", "irrig": "rainfed",
     "soil": {"nitrogen_ppm": 18, "phosphorus_ppm": 30, "potassium_ppm": 200, "ph": 7.0, "clay_pct": 22, "organic_matter_pct": 2.2},
     "ndvi": 0.78, "ndre": 0.38, "sar": (-12, -11, None, None, 0.08), "goal": "cost_min", "constraints": {}},
    {"id": "P8", "name": "Cotton P-Deficit", "crop": "cotton", "irrig": "drip",
     "soil": {"nitrogen_ppm": 22, "phosphorus_ppm": 4, "potassium_ppm": 120, "ph": 7.8, "clay_pct": 40, "organic_matter_pct": 1.5},
     "ndvi": 0.65, "ndre": 0.28, "sar": (-11, -7, None, None, 0.25), "goal": "yield_max", "constraints": {}},
    {"id": "P9", "name": "Sunflower Sparse Data", "crop": "sunflower", "irrig": "rainfed",
     "soil": {"clay_pct": 18, "organic_matter_pct": 1.0},
     "ndvi": 0.45, "ndre": None, "sar": None, "goal": "yield_max", "constraints": {}},
    {"id": "P10", "name": "Canola Heavy NVZ", "crop": "canola", "irrig": "rainfed",
     "soil": {"nitrogen_ppm": 7, "phosphorus_ppm": 15, "potassium_ppm": 100, "ph": 6.5, "clay_pct": 28, "organic_matter_pct": 2.8},
     "ndvi": 0.58, "ndre": 0.24, "sar": (-12, -5, None, None, 0.5), "goal": "sustainable",
     "constraints": {"nitrogen_limit_kg_ha": 140}},
]

def run_simulation():
    weather = [{"et0": 4.5, "rain_mm": 2.7, "t_max": 27.0}] * 60
    stages = ["initial"]*10 + ["vegetative"]*30 + ["reproductive"]*20
    results = []
    
    for p in PLOTS:
        sar = p.get("sar")
        sar_args = {}
        if sar:
            sar_args = {"sar_vv_pre": sar[0], "sar_vv_post": sar[1],
                        "sar_vh_pre": sar[2], "sar_vh_post": sar[3],
                        "sar_coherence_drop": sar[4]}
        
        out = run_layer4_standalone(
            plot_id=p["id"], crop_type=p["crop"], management_goal=p["goal"],
            irrigation_type=p["irrig"], soil_props=p["soil"],
            daily_weather=weather, stages=stages,
            ndvi=p["ndvi"], ndre=p.get("ndre"),
            constraints=p.get("constraints", {}), **sar_args,
        )
        
        row = {
            "plot": p["id"], "name": p["name"],
            "tillage": out.tillage_detection.tillage_class.value,
            "soc_min": round(out.soc_dynamics.tillage_adjusted_mineralization, 1),
            "n_prob": round(out.nutrient_states.get(out.nutrient_states.__class__().__class__, out.nutrient_states).get(
                __import__("layer4_nutrients.schema", fromlist=["Nutrient"]).Nutrient.N
            ).probability_deficient, 3) if True else 0,
        }

        from layer4_nutrients.schema import Nutrient
        ns = out.nutrient_states
        row["n_prob"] = round(ns[Nutrient.N].probability_deficient, 3)
        row["n_conf"] = round(ns[Nutrient.N].confidence, 2)
        row["p_prob"] = round(ns[Nutrient.P].probability_deficient, 3)
        row["k_prob"] = round(ns[Nutrient.K].probability_deficient, 3)
        
        rx_summary = []
        for rx in out.prescriptions:
            rx_summary.append(f"{rx.nutrient.value}:{rx.action_id.value}@{rx.rate_kg_ha}kg")
        row["prescriptions"] = " | ".join(rx_summary) if rx_summary else "NO_ACTION"
        row["allowed"] = all(rx.is_allowed for rx in out.prescriptions) if out.prescriptions else True
        row["health"] = round(out.data_health.overall, 2)
        row["hash"] = out.content_hash()[:12]
        
        results.append(row)
        
        status = "OK" if row["allowed"] else "WARN"
        print(f"{status} {p['id']:>3} | {p['name']:<25} | Till={row['tillage']:<13} | "
              f"N={row['n_prob']:.2f}(c={row['n_conf']:.1f}) P={row['p_prob']:.2f} K={row['k_prob']:.2f} | "
              f"{row['prescriptions']:<45} | H={row['health']}")
    
    # Invariant checks
    print("\n" + "="*100)
    print("SIMULATION INVARIANT CHECKS")
    print("="*100)
    
    all_pass = True
    for r in results:
        if r["n_prob"] < 0 or r["n_prob"] > 1:
            print(f"FAIL {r['plot']}: N prob out of bounds: {r['n_prob']}")
            all_pass = False
        if r["n_conf"] < 0 or r["n_conf"] > 1:
            print(f"FAIL {r['plot']}: N conf out of bounds: {r['n_conf']}")
            all_pass = False
    
    # Check hash determinism (run twice)
    out_a = run_layer4_standalone(plot_id="P1", crop_type="corn", soil_props=PLOTS[0]["soil"],
                                  ndvi=0.75, daily_weather=weather, stages=stages)
    out_b = run_layer4_standalone(plot_id="P1", crop_type="corn", soil_props=PLOTS[0]["soil"],
                                  ndvi=0.75, daily_weather=weather, stages=stages)
    if out_a.content_hash() == out_b.content_hash():
        print("PASS Deterministic hash")
    else:
        print(f"FAIL Deterministic hash ({out_a.content_hash()[:12]} != {out_b.content_hash()[:12]})")
        all_pass = False
    
    if all_pass:
        print("PASS ALL INVARIANTS")
    
    return results

if __name__ == "__main__":
    run_simulation()
