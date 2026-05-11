import json
import math
import os
from datetime import datetime, timedelta, timezone
from layer1_fusion.schemas import DataHealthScore
from layer2_intelligence.schemas import Layer2Output, StressEvidence, VegetationFeature, Layer2Provenance, Layer2Diagnostics
from layer2_intelligence.outputs.layer3_adapter import build_layer3_context
from layer3_decision.runner import run_layer3
from layer3_decision.schema import PlotContext

def generate_full_pipeline_data(plot_id, crop, scenario, start_date, days=120):
    history = []
    
    for day in range(days):
        current_date = start_date + timedelta(days=day)
        
        # Base phenology
        if day < 30: stage = "VEGETATIVE"
        elif day < 70: stage = "REPRODUCTIVE"
        elif day < 100: stage = "MATURITY"
        else: stage = "SENESCENCE"
        
        # Default environment
        t_air = 28.0 + math.sin(day/10.0)*4
        et0 = 4.0 + math.sin(day/15.0)*2
        vpd = 1.5 + math.sin(day/10.0)*0.5
        ndvi = min(0.85, 0.2 + day*0.01) if day < 90 else max(0.3, 0.85 - (day-90)*0.02)
        lst = t_air - 3.0 # Healthy cooling
        
        # L2 defaults
        rain_sum_14d = 15.0
        days_since_rain = 5
        saturation_days = 0
        sar_roughness = 0.0
        sar_vv_trend = 0.0
        spatial_stability = "STABLE"
        anomaly_type = "NONE"
        anomaly_severity = 0.0
        growth_velocity = 0.01 if day < 60 else -0.01
        
        sar_available = True
        optical_available = True
        
        # Apply scenarios
        if scenario == "fungal_risk": # Wheat - Fungal
            if day > 40 and day < 60:
                rain_sum_14d = 60.0
                days_since_rain = 1
                saturation_days = 3
                t_air = 22.0 # cooler, wet
                anomaly_type = "STALL"
                anomaly_severity = 0.4
                
        elif scenario == "heat_stress": # Soybean - Heat
            if day > 50 and day < 70:
                t_air = 38.0 + math.sin(day)*2 # Extreme heat
                lst = t_air - 1.0 # struggling but transpiring
                anomaly_type = "STALL"
                anomaly_severity = 0.5
                
        elif scenario == "waterlogging": # Cotton - Waterlogging
            if day > 30 and day < 50:
                rain_sum_14d = 150.0
                days_since_rain = 0
                saturation_days = 6
                anomaly_type = "DROP"
                anomaly_severity = 0.6
                
        elif scenario == "salinity": # Rice - Salinity
            growth_velocity = 0.001 # stunted
            ndvi = min(0.5, 0.2 + day*0.005) # never reaches full canopy
            
        elif scenario == "lodging": # Barley - Lodging
            if day == 80:
                sar_roughness = -6.0 # Sudden flattening
                sar_vv_trend = -3.0
                anomaly_type = "DROP"
                anomaly_severity = 0.4
                
        elif scenario == "insect_pressure": # Potato - Insects
            if day > 40 and day < 60:
                anomaly_type = "DROP"
                anomaly_severity = 0.8
                spatial_stability = "TRANSIENT_VAR" # Patchy
                
        elif scenario == "data_gap": # Canola - Data gap
            if day > 50 and day < 70:
                sar_available = False
                optical_available = False
                
        elif scenario == "transpiration_failure": # Sorghum - TF
            if day > 60 and day < 80:
                drought_factor = (day - 60) / 20.0
                rain_sum_14d = 0.0
                days_since_rain = day - 50
                lst = t_air + (12.0 * drought_factor)
                anomaly_type = "DROP"
                anomaly_severity = drought_factor
                
        elif scenario == "tillage": # Alfalfa - Tillage
            if day == 10:
                stage = "BARE_SOIL"
                sar_roughness = 5.0 # Ploughed
                ndvi = 0.1
                
        elif scenario == "optimal": # Corn - Optimal
            pass
            
        missing_inputs = []
        if not rain_sum_14d: missing_inputs.append("RAIN")
        if not sar_available: missing_inputs.append("SAR_VV")
        if not optical_available: missing_inputs.append("NDVI")
        
        # Mock L2
        veg = [
            VegetationFeature(name="lst_canopy_c", value=lst, confidence=0.9),
            VegetationFeature(name="ndvi_mean", value=ndvi, confidence=0.9),
            VegetationFeature(name="et0_mm", value=et0, confidence=0.8),
            VegetationFeature(name="t_air_c", value=t_air, confidence=0.8),
            VegetationFeature(name="vpd_kpa", value=vpd, confidence=0.8),
        ]
        
        stress_ctx = []
        
        ops_overrides = {
            "sar_available": sar_available, "optical_available": optical_available,
            "rain_available": True, "temp_available": True,
            "sar_obs_count": 5 if sar_available else 0, 
            "optical_obs_count": 5 if optical_available else 0,
            "water_deficit_severity": anomaly_severity if "water" in scenario else 0.0,
            "thermal_severity": anomaly_severity if scenario == "heat_stress" else 0.0,
            "has_anomaly": anomaly_type != "NONE",
            "anomaly_severity": anomaly_severity,
            "anomaly_type": anomaly_type,
            "growth_velocity": growth_velocity,
        }
        
        l2_out = Layer2Output(
            plot_id=plot_id, run_id=f"l2_{day}", layer1_run_id=f"l1_{day}", generated_at=current_date,
            data_health=DataHealthScore(overall=0.9, confidence_ceiling=1.0, status="ok"),
            provenance=Layer2Provenance(run_id=f"l2_{day}", layer1_run_id=f"l1_{day}"),
            diagnostics=Layer2Diagnostics(status="ok", data_health=DataHealthScore(overall=0.9, confidence_ceiling=1.0, status="ok")),
            stress_context=stress_ctx, vegetation_intelligence=veg, phenology_adjusted_indices=[],
            gaps_inherited=[], conflicts_inherited=[]
        )
        
        l3_ctx = build_layer3_context(l2_out)
        l3_ctx.phenology_stage = stage
        l3_ctx.operational_signals.update(ops_overrides)
        
        # To bypass l3_adapter losing fields it doesn't know about, we inject directly into features
        from layer3_decision.features.builder import build_decision_features
        from layer3_decision.diagnosis.inference import DiagnosisEngine
        from layer3_decision.policy.policies import PolicyEngine
        
        plot_ctx = PlotContext(crop_type=crop, irrigation_type="drip")
        features = build_decision_features(l3_ctx, plot_ctx)
        
        # Inject scenario specifics directly into features
        features.rain_sum_14d = rain_sum_14d
        features.days_since_rain = days_since_rain
        features.saturation_days = saturation_days
        features.sar_roughness_change = sar_roughness
        features.sar_vv_trend_7d = sar_vv_trend
        features.spatial_stability = spatial_stability
        
        from layer3_decision.schema import Driver
        if not sar_available:
            features.missing_inputs.append(Driver.SAR_VV)
        if not optical_available:
            features.missing_inputs.append(Driver.NDVI)
            
        engine = DiagnosisEngine()
        diagnoses = engine.diagnose(features, plot_ctx)
        
        policy = PolicyEngine()
        actions = [a.action_id for a in policy.generate_plan(diagnoses, plot_ctx, None, features.missing_inputs)]
        
        snap = {
            "rain": rain_sum_14d, "lst": round(lst, 1), "t_air": round(t_air, 1), "ndvi": round(ndvi, 2),
            "delta": round(lst - t_air, 1), "esi": round(features.esi, 2)
        }
        
        diags = [d.problem_id for d in diagnoses]
        history.append({
            "day": day, "date": current_date.strftime("%Y-%m-%d"), "stage": stage,
            "snap": snap, "diags": diags, "actions": actions
        })
        
    return history

if __name__ == "__main__":
    start = datetime(2026, 5, 1, tzinfo=timezone.utc)
    plots = [
        {"id": "01_Corn_Optimal", "crop": "corn", "scenario": "optimal"},
        {"id": "02_Wheat_Fungal", "crop": "wheat", "scenario": "fungal_risk"},
        {"id": "03_Soy_Heat", "crop": "soybean", "scenario": "heat_stress"},
        {"id": "04_Cotton_Waterlog", "crop": "cotton", "scenario": "waterlogging"},
        {"id": "05_Rice_Salinity", "crop": "rice", "scenario": "salinity"},
        {"id": "06_Barley_Lodging", "crop": "barley", "scenario": "lodging"},
        {"id": "07_Potato_Insects", "crop": "potato", "scenario": "insect_pressure"},
        {"id": "08_Canola_DataGap", "crop": "canola", "scenario": "data_gap"},
        {"id": "09_Sorghum_TF", "crop": "sorghum", "scenario": "transpiration_failure"},
        {"id": "10_Alfalfa_Tillage", "crop": "alfalfa", "scenario": "tillage"},
    ]
    
    results = {}
    for p in plots:
        print(f"Simulating {p['id']}...")
        results[p["id"]] = generate_full_pipeline_data(p["id"], p["crop"], p["scenario"], start, 120)
        
    out_path = os.path.join(os.path.dirname(__file__), "full_season_audit.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Simulation complete. Results written to {out_path}")
