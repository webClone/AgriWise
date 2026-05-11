import json
import math
import os
from datetime import datetime, timedelta, timezone

from layer1_fusion.schemas import DataHealthScore
from layer2_intelligence.schemas import Layer2Output, StressEvidence, VegetationFeature, Layer2Provenance, Layer2Diagnostics
from layer2_intelligence.outputs.layer3_adapter import build_layer3_context
from layer3_decision.runner import run_layer3
from layer3_decision.schema import PlotContext

def generate_season_data(plot_id, crop, scenario, start_date, days):
    history = []
    
    for day in range(days):
        current_date = start_date + timedelta(days=day)
        
        # Base phenology
        if day < 20: stage = "VEGETATIVE"
        elif day < 60: stage = "REPRODUCTIVE"
        elif day < 90: stage = "MATURITY"
        else: stage = "SENESCENCE"
        
        # Default environment
        t_air = 28.0 + math.sin(day/10.0)*4
        et0 = 4.0 + math.sin(day/15.0)*2
        vpd = 1.5 + math.sin(day/10.0)*0.5
        ndvi = min(0.85, 0.2 + day*0.01) if day < 80 else max(0.3, 0.85 - (day-80)*0.02)
        
        lst = t_air - 3.0 # Default healthy cooling
        stress_severity = 0.0
        
        if scenario == "drought":
            if day > 40 and day < 80:
                # Progressive drought
                drought_factor = (day - 40) / 40.0
                lst = t_air + (15.0 * drought_factor) # Canopy heats up
                vpd += 2.0 * drought_factor
                ndvi -= 0.1 * drought_factor
                stress_severity = drought_factor
        elif scenario == "recovered":
            if day > 30 and day < 50:
                # Temporary drought
                stress_factor = (day - 30) / 20.0
                lst = t_air + (10.0 * stress_factor)
                stress_severity = stress_factor * 0.8
            elif day >= 50:
                # Recovery via irrigation
                lst = t_air - 4.0
                stress_severity = 0.0
                
        # Build mock L2 output to simulate data arriving from L1/L0
        veg = [
            VegetationFeature(name="lst_canopy_c", value=lst, confidence=0.9),
            VegetationFeature(name="ndvi_mean", value=ndvi, confidence=0.9),
            VegetationFeature(name="et0_mm", value=et0, confidence=0.8),
            VegetationFeature(name="t_air_c", value=t_air, confidence=0.8),
            VegetationFeature(name="vpd_kpa", value=vpd, confidence=0.8),
        ]
        
        stress_ctx = []
        if stress_severity > 0.3:
            stress_ctx.append(StressEvidence(
                stress_id=f"se_{day}", stress_type="WATER",
                severity=stress_severity, confidence=0.8, uncertainty=0.1,
                primary_driver="rain_deficit",
                contributing_evidence_ids=["e1"],
                explanation_basis=["observed deficit"],
                data_health_at_attribution=0.9,
            ))
            
        ops_overrides = {
            "sar_available": True, "optical_available": True,
            "rain_available": True, "temp_available": True,
            "sar_obs_count": 5, "optical_obs_count": 5,
            "water_deficit_severity": stress_severity,
            "thermal_severity": 0.0,
            "has_anomaly": stress_severity > 0.5,
            "anomaly_severity": stress_severity,
            "anomaly_type": "DROP" if stress_severity > 0.5 else "NONE",
            "growth_velocity": 0.01 if stress_severity < 0.5 else -0.01,
        }
        
        l2_out = Layer2Output(
            plot_id=plot_id,
            run_id=f"l2_{day}",
            layer1_run_id=f"l1_{day}",
            generated_at=current_date,
            data_health=DataHealthScore(overall=0.9, confidence_ceiling=1.0, status="ok"),
            provenance=Layer2Provenance(run_id=f"l2_{day}", layer1_run_id=f"l1_{day}"),
            diagnostics=Layer2Diagnostics(status="ok", data_health=DataHealthScore(overall=0.9, confidence_ceiling=1.0, status="ok")),
            stress_context=stress_ctx,
            vegetation_intelligence=veg,
            phenology_adjusted_indices=[],
            gaps_inherited=[],
            conflicts_inherited=[]
        )
        
        l3_ctx = build_layer3_context(l2_out)
        l3_ctx.phenology_stage = stage
        l3_ctx.operational_signals.update(ops_overrides)
        
        plot_ctx = PlotContext(crop_type=crop, irrigation_type="drip" if scenario != "drought" else "rainfed")
        l3_out = run_layer3(l3_ctx, plot_context=plot_ctx, run_id=f"l3_{day}", run_timestamp=current_date)
        
        # Extract audit data
        snap = l3_out.audit.features_snapshot
        diagnoses = [d.problem_id for d in l3_out.diagnoses]
        actions = [r.action_id for r in l3_out.recommendations]
        
        history.append({
            "day": day,
            "date": current_date.strftime("%Y-%m-%d"),
            "stage": stage,
            "l0_lst": round(lst, 1),
            "l1_t_air": round(t_air, 1),
            "l2_stress_severity": round(stress_severity, 2),
            "l3_esi": round(snap.get("esi", 0), 2),
            "l3_cwsi": round(snap.get("cwsi", 0), 2),
            "l3_delta_t": round(snap.get("canopy_air_delta_c", 0), 1),
            "l3_diagnoses": diagnoses,
            "l3_actions": actions
        })
        
    return history

if __name__ == "__main__":
    start = datetime(2026, 5, 1, tzinfo=timezone.utc)
    plots = [
        {"id": "Plot_A_Corn_Optimal", "crop": "corn", "scenario": "optimal"},
        {"id": "Plot_B_Wheat_Drought", "crop": "wheat", "scenario": "drought"},
        {"id": "Plot_C_Soy_Recovered", "crop": "soybean", "scenario": "recovered"},
    ]
    
    results = {}
    for p in plots:
        results[p["id"]] = generate_season_data(p["id"], p["crop"], p["scenario"], start, 100)
        
    out_path = os.path.join(os.path.dirname(__file__), "season_audit.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Simulation complete. Results written to {out_path}")
