"""
Extended Season Simulation — 10 plots with UserInputPackage driving the full pipeline.

Each plot has:
  - Real plot polygon + soil analysis + crop-specific parameters from UserInputAdapter
  - Irrigation events (timed according to scenario)
  - Management events (sowing, fertilizer, harvest)
  - Full L0 → L1 → L2 → L3 flow using crop_params from the adapter

This proves that user-declared inputs (polygon, crop, soil, irrigation) propagate
through the entire pipeline and influence the Kalman state estimation, feature builder,
diagnosis engine, and policy engine.
"""

import json
import math
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

# L0 User Input
from layer0.user_input_schema import (
    PlotRegistration, SoilAnalysis, IrrigationEvent, ManagementEvent,
    UserInputPackage,
)
from layer0.user_input_adapter import UserInputAdapter, CROP_PARAMS_LIBRARY

# L1 Fusion
from layer1_fusion.schemas import DataHealthScore

# L2 Intelligence
from layer2_intelligence.schemas import (
    Layer2Output, StressEvidence, VegetationFeature,
    Layer2Provenance, Layer2Diagnostics,
)
from layer2_intelligence.outputs.layer3_adapter import build_layer3_context

# L3 Decision
from layer3_decision.runner import run_layer3
from layer3_decision.schema import PlotContext
from layer3_decision.features.builder import build_decision_features
from layer3_decision.diagnosis.inference import DiagnosisEngine
from layer3_decision.policy.policies import PolicyEngine


# ============================================================================
# 10 Real Plot Definitions
# ============================================================================

SEASON_START = datetime(2026, 5, 1, tzinfo=timezone.utc)
SEASON_DAYS = 120

PLOTS = [
    # 1. Corn — Optimal irrigated (Drip, Loamy soil, no stress)
    {
        "id": "P01_Corn_Drip_Optimal",
        "registration": {
            "plot_id": "P01", "crop_type": "corn", "variety": "Pioneer P1151",
            "polygon_wkt": "POLYGON((-7.62 33.59, -7.61 33.59, -7.61 33.60, -7.62 33.60, -7.62 33.59))",
            "area_ha": 15.0, "planting_date": "2026-04-15",
            "irrigation_type": "drip", "management_goal": "yield_max",
            "constraints": {"water_quota_mm": 600},
        },
        "soil": {"clay_pct": 22.0, "sand_pct": 40.0, "silt_pct": 38.0,
                 "organic_matter_pct": 2.8, "ph": 6.9, "ec_ds_m": 0.3,
                 "nitrogen_ppm": 50.0, "phosphorus_ppm": 25.0, "potassium_ppm": 200.0},
        "scenario": "optimal_irrigated",
    },
    # 2. Wheat — Rainfed Drought (No irrigation, Sandy Loam → fast drainage)
    {
        "id": "P02_Wheat_Rainfed_Drought",
        "registration": {
            "plot_id": "P02", "crop_type": "wheat", "variety": "Arrehane",
            "polygon_wkt": "POLYGON((-7.55 33.55, -7.54 33.55, -7.54 33.56, -7.55 33.56, -7.55 33.55))",
            "area_ha": 20.0, "planting_date": "2026-04-01",
            "irrigation_type": "rainfed", "management_goal": "cost_min",
        },
        "soil": {"clay_pct": 12.0, "sand_pct": 72.0, "silt_pct": 16.0,
                 "organic_matter_pct": 1.2, "ph": 7.5, "ec_ds_m": 0.2},
        "scenario": "rainfed_drought",
    },
    # 3. Soybean — Flood Irrigation, Waterlogging
    {
        "id": "P03_Soy_Flood_Waterlog",
        "registration": {
            "plot_id": "P03", "crop_type": "soybean",
            "polygon_wkt": "POLYGON((-7.50 33.52, -7.49 33.52, -7.49 33.53, -7.50 33.53, -7.50 33.52))",
            "area_ha": 10.0, "planting_date": "2026-04-20",
            "irrigation_type": "flood",
        },
        "soil": {"clay_pct": 45.0, "sand_pct": 15.0, "silt_pct": 40.0,
                 "organic_matter_pct": 3.5, "ph": 6.2, "ec_ds_m": 0.8},
        "scenario": "over_irrigation_waterlog",
    },
    # 4. Rice — Paddy, Saline Soil
    {
        "id": "P04_Rice_Saline",
        "registration": {
            "plot_id": "P04", "crop_type": "rice",
            "polygon_wkt": "POLYGON((-7.45 33.50, -7.44 33.50, -7.44 33.51, -7.45 33.51, -7.45 33.50))",
            "area_ha": 8.0, "planting_date": "2026-04-10",
            "irrigation_type": "flood",
        },
        "soil": {"clay_pct": 35.0, "sand_pct": 25.0, "silt_pct": 40.0,
                 "organic_matter_pct": 2.0, "ph": 8.2, "ec_ds_m": 4.5,  # SALINE
                 "nitrogen_ppm": 30.0, "phosphorus_ppm": 10.0, "potassium_ppm": 120.0},
        "scenario": "saline_soil",
    },
    # 5. Cotton — Pivot Irrigation, Heat Wave
    {
        "id": "P05_Cotton_Pivot_Heat",
        "registration": {
            "plot_id": "P05", "crop_type": "cotton",
            "polygon_wkt": "POLYGON((-7.40 33.48, -7.39 33.48, -7.39 33.49, -7.40 33.49, -7.40 33.48))",
            "area_ha": 25.0, "planting_date": "2026-04-25",
            "irrigation_type": "pivot", "constraints": {"water_quota_mm": 800},
        },
        "soil": {"clay_pct": 25.0, "sand_pct": 35.0, "silt_pct": 40.0,
                 "organic_matter_pct": 2.2, "ph": 7.1, "ec_ds_m": 0.4},
        "scenario": "heat_wave",
    },
    # 6. Barley — Rainfed, Fungal Disease after wet period
    {
        "id": "P06_Barley_Fungal",
        "registration": {
            "plot_id": "P06", "crop_type": "barley",
            "polygon_wkt": "POLYGON((-7.58 33.57, -7.57 33.57, -7.57 33.58, -7.58 33.58, -7.58 33.57))",
            "area_ha": 12.0, "planting_date": "2026-03-25",
            "irrigation_type": "rainfed",
        },
        "soil": {"clay_pct": 30.0, "sand_pct": 30.0, "silt_pct": 40.0,
                 "organic_matter_pct": 3.0, "ph": 6.5, "ec_ds_m": 0.3},
        "scenario": "fungal_wet_period",
    },
    # 7. Potato — Sprinkler, Insect Pressure
    {
        "id": "P07_Potato_Insects",
        "registration": {
            "plot_id": "P07", "crop_type": "potato",
            "polygon_wkt": "POLYGON((-7.63 33.61, -7.62 33.61, -7.62 33.62, -7.63 33.62, -7.63 33.61))",
            "area_ha": 5.0, "planting_date": "2026-04-05",
            "irrigation_type": "sprinkler",
        },
        "soil": {"clay_pct": 18.0, "sand_pct": 45.0, "silt_pct": 37.0,
                 "organic_matter_pct": 4.0, "ph": 6.0, "ec_ds_m": 0.2,
                 "nitrogen_ppm": 60.0, "phosphorus_ppm": 30.0, "potassium_ppm": 250.0},
        "scenario": "insect_pressure",
    },
    # 8. Sorghum — Drip, Progressive Transpiration Failure
    {
        "id": "P08_Sorghum_TF",
        "registration": {
            "plot_id": "P08", "crop_type": "sorghum",
            "polygon_wkt": "POLYGON((-7.48 33.53, -7.47 33.53, -7.47 33.54, -7.48 33.54, -7.48 33.53))",
            "area_ha": 18.0, "planting_date": "2026-04-18",
            "irrigation_type": "drip", "constraints": {"water_quota_mm": 200},
        },
        "soil": {"clay_pct": 15.0, "sand_pct": 65.0, "silt_pct": 20.0,
                 "organic_matter_pct": 1.0, "ph": 7.8, "ec_ds_m": 0.5},
        "scenario": "transpiration_failure",
    },
    # 9. Canola — Data Gap scenario (cloud cover blocks sensors)
    {
        "id": "P09_Canola_DataGap",
        "registration": {
            "plot_id": "P09", "crop_type": "canola",
            "polygon_wkt": "POLYGON((-7.53 33.56, -7.52 33.56, -7.52 33.57, -7.53 33.57, -7.53 33.56))",
            "area_ha": 14.0, "planting_date": "2026-04-08",
            "irrigation_type": "rainfed",
        },
        "soil": {"clay_pct": 28.0, "sand_pct": 32.0, "silt_pct": 40.0,
                 "organic_matter_pct": 2.5, "ph": 6.7, "ec_ds_m": 0.3},
        "scenario": "data_gap",
    },
    # 10. Alfalfa — Drip, Recovery after irrigation intervention
    {
        "id": "P10_Alfalfa_Recovery",
        "registration": {
            "plot_id": "P10", "crop_type": "alfalfa",
            "polygon_wkt": "POLYGON((-7.60 33.58, -7.59 33.58, -7.59 33.59, -7.60 33.59, -7.60 33.58))",
            "area_ha": 10.0, "planting_date": "2026-04-12",
            "irrigation_type": "drip",
        },
        "soil": {"clay_pct": 20.0, "sand_pct": 40.0, "silt_pct": 40.0,
                 "organic_matter_pct": 3.2, "ph": 7.0, "ec_ds_m": 0.25},
        "scenario": "stress_then_recovery",
    },
]


# ============================================================================
# Scenario-specific daily environment generator
# ============================================================================

def generate_daily_environment(scenario: str, day: int, crop_params: Dict) -> Dict[str, Any]:
    """Generate daily environmental signals based on scenario."""
    t_base = crop_params.get("t_base", 10.0)
    t_air = 28.0 + math.sin(day / 10.0) * 4
    et0 = 4.0 + math.sin(day / 15.0) * 2
    vpd = 1.5 + math.sin(day / 10.0) * 0.5
    rain_mm = 0.0
    lst = t_air - 3.0  # Healthy transpiration cooling

    # Default L2 ops
    ndvi = min(0.85, 0.2 + day * 0.008) if day < 90 else max(0.3, 0.85 - (day - 90) * 0.02)
    rain_sum_14d = 15.0
    days_since_rain = 5
    saturation_days = 0
    sar_roughness = 0.0
    anomaly_type = "NONE"
    anomaly_severity = 0.0
    spatial_stability = "STABLE"
    sar_available = True
    optical_available = True
    growth_velocity = 0.01 if day < 60 else -0.01
    irrigation_today_mm = 0.0

    if scenario == "optimal_irrigated":
        # Regular drip irrigation every 5 days
        if day % 5 == 0 and day > 5:
            irrigation_today_mm = 20.0
            rain_sum_14d = 25.0  # Effective soil recharge

    elif scenario == "rainfed_drought":
        # No rain after day 40
        if day < 40:
            rain_sum_14d = 12.0
            if day % 7 == 0:
                rain_mm = 5.0
        else:
            rain_sum_14d = max(0, 12.0 - (day - 40) * 0.6)
            days_since_rain = day - 40
            drought_factor = min(1.0, (day - 40) / 30.0)
            lst = t_air + 10.0 * drought_factor
            anomaly_type = "DROP" if drought_factor > 0.3 else "NONE"
            anomaly_severity = drought_factor

    elif scenario == "over_irrigation_waterlog":
        # Excessive flood irrigation during reproductive stage
        if 30 < day < 55:
            irrigation_today_mm = 80.0 if day % 3 == 0 else 0.0
            rain_sum_14d = 120.0
            saturation_days = min(7, (day - 30) // 3)
            anomaly_type = "DROP"
            anomaly_severity = min(0.8, saturation_days * 0.12)

    elif scenario == "saline_soil":
        # Chronic salinity: stunted growth, never reaches peak NDVI
        ndvi = min(0.45, 0.15 + day * 0.004)
        growth_velocity = 0.002
        anomaly_severity = 0.3  # Persistent low-level

    elif scenario == "heat_wave":
        # Extreme heat from day 50 to 70
        if 50 < day < 70:
            t_air = 40.0 + math.sin(day) * 2
            lst = t_air - 1.0  # Barely transpiring
            anomaly_type = "STALL"
            anomaly_severity = 0.6
        # Pivot irrigation continues
        if day % 4 == 0 and day > 5:
            irrigation_today_mm = 30.0
            rain_sum_14d = 30.0

    elif scenario == "fungal_wet_period":
        # Heavy rain + cool temperatures from day 35-55
        if 35 < day < 55:
            rain_sum_14d = 65.0
            rain_mm = 10.0 if day % 2 == 0 else 5.0
            days_since_rain = 1
            saturation_days = 4
            t_air = 20.0  # Cool + wet = fungal heaven
            anomaly_type = "STALL"
            anomaly_severity = 0.4

    elif scenario == "insect_pressure":
        # Sudden patchy NDVI loss from day 40-60
        if 40 < day < 60:
            ndvi = max(0.3, ndvi - 0.2)
            anomaly_type = "DROP"
            anomaly_severity = 0.7
            spatial_stability = "TRANSIENT_VAR"
        # Sprinkler keeps going
        if day % 3 == 0 and day > 5:
            irrigation_today_mm = 15.0

    elif scenario == "transpiration_failure":
        # Progressive drought from day 60 onward — drip system has quota limit
        if day < 60:
            if day % 5 == 0 and day > 5:
                irrigation_today_mm = 15.0  # Quota-limited drip
        else:
            # Quota exhausted, no more irrigation
            drought_factor = min(1.0, (day - 60) / 20.0)
            rain_sum_14d = 0.0
            days_since_rain = day - 55
            lst = t_air + 14.0 * drought_factor
            anomaly_type = "DROP"
            anomaly_severity = drought_factor

    elif scenario == "data_gap":
        # Satellite data blocked day 50-70
        if 50 < day < 70:
            sar_available = False
            optical_available = False

    elif scenario == "stress_then_recovery":
        # Stress days 40-60, then irrigation intervention rescues the crop
        if 40 < day < 60:
            rain_sum_14d = 0.0
            days_since_rain = day - 38
            drought_factor = min(1.0, (day - 40) / 20.0)
            lst = t_air + 8.0 * drought_factor
            anomaly_type = "DROP"
            anomaly_severity = drought_factor
        elif day >= 60:
            # Rescue irrigation kicks in
            if day % 3 == 0:
                irrigation_today_mm = 25.0
            rain_sum_14d = 20.0
            lst = t_air - 4.0  # Full transpiration recovery

    # Phenology from crop params
    gdd_total = sum(max(0, (28.0 + math.sin(d / 10.0) * 4) - t_base) for d in range(day + 1))
    gdd_veg = crop_params.get("gdd_vegetative", 200)
    gdd_flow = crop_params.get("gdd_flowering", 800)
    gdd_rip = crop_params.get("gdd_ripening", 1200)
    gdd_sen = crop_params.get("gdd_senescence", 1600)

    if gdd_total < gdd_veg:
        stage = "VEGETATIVE"
    elif gdd_total < gdd_flow:
        stage = "REPRODUCTIVE"
    elif gdd_total < gdd_rip:
        stage = "MATURITY"
    elif gdd_total < gdd_sen:
        stage = "SENESCENCE"
    else:
        stage = "SENESCENCE"

    return {
        "t_air": t_air, "et0": et0, "vpd": vpd, "lst": lst, "ndvi": ndvi,
        "rain_mm": rain_mm, "rain_sum_14d": rain_sum_14d,
        "days_since_rain": days_since_rain, "saturation_days": saturation_days,
        "sar_roughness": sar_roughness, "anomaly_type": anomaly_type,
        "anomaly_severity": anomaly_severity, "spatial_stability": spatial_stability,
        "sar_available": sar_available, "optical_available": optical_available,
        "growth_velocity": growth_velocity, "stage": stage,
        "irrigation_today_mm": irrigation_today_mm,
    }


# ============================================================================
# Full pipeline simulation per plot
# ============================================================================

def simulate_plot(plot_def: Dict, start_date: datetime, days: int) -> Dict:
    """Full L0→L3 simulation for a single plot."""

    # === STEP 1: L0 User Input Adapter ===
    reg_kwargs = dict(plot_def["registration"])
    reg_kwargs["registered_at"] = start_date - timedelta(days=30)
    registration = PlotRegistration(**reg_kwargs)

    soil_kwargs = dict(plot_def.get("soil", {}))
    soil_kwargs["plot_id"] = registration.plot_id
    soil_kwargs["sample_date"] = (start_date - timedelta(days=60)).strftime("%Y-%m-%d")
    soil = SoilAnalysis(**soil_kwargs)

    # Pre-generate irrigation events based on scenario
    irrigation_events = []
    management_events = [
        ManagementEvent(
            plot_id=registration.plot_id,
            timestamp=start_date,
            event_type="sowing",
            details={"seed_rate_kg_ha": 80},
        )
    ]

    package = UserInputPackage(
        plot_registration=registration,
        soil_analyses=[soil],
        irrigation_events=irrigation_events,
        management_events=management_events,
    )

    adapter = UserInputAdapter()
    adapter_output = adapter.ingest(package)

    # Build PlotContext from adapter output
    ctx_overrides = adapter_output.plot_context_overrides
    plot_ctx = PlotContext(
        crop_type=ctx_overrides.get("crop_type", "unknown"),
        variety=ctx_overrides.get("variety"),
        planting_date=ctx_overrides.get("planting_date", ""),
        irrigation_type=ctx_overrides.get("irrigation_type", "rainfed"),
        management_goal=ctx_overrides.get("management_goal", "yield_max"),
        constraints=ctx_overrides.get("constraints", {}),
        polygon_wkt=ctx_overrides.get("polygon_wkt"),
        area_ha=ctx_overrides.get("area_ha"),
        soil_texture_class=ctx_overrides.get("soil_texture_class", ""),
        soil_clay_pct=ctx_overrides.get("soil_clay_pct"),
        soil_om_pct=ctx_overrides.get("soil_om_pct"),
        soil_ph=ctx_overrides.get("soil_ph"),
        soil_ec_ds_m=ctx_overrides.get("soil_ec_ds_m"),
    )

    crop_params = adapter_output.crop_params
    soil_props = adapter_output.soil_props
    scenario = plot_def["scenario"]

    # === STEP 2: Daily simulation L2 → L3 ===
    history = []
    for day in range(days):
        current_date = start_date + timedelta(days=day)
        env = generate_daily_environment(scenario, day, crop_params)

        # Mock L2 output
        veg = [
            VegetationFeature(name="lst_canopy_c", value=env["lst"], confidence=0.9),
            VegetationFeature(name="ndvi_mean", value=env["ndvi"], confidence=0.9),
            VegetationFeature(name="et0_mm", value=env["et0"], confidence=0.8),
            VegetationFeature(name="t_air_c", value=env["t_air"], confidence=0.8),
            VegetationFeature(name="vpd_kpa", value=env["vpd"], confidence=0.8),
        ]

        l2_out = Layer2Output(
            plot_id=registration.plot_id, run_id=f"l2_{day}",
            layer1_run_id=f"l1_{day}", generated_at=current_date,
            data_health=DataHealthScore(overall=0.9, confidence_ceiling=1.0, status="ok"),
            provenance=Layer2Provenance(run_id=f"l2_{day}", layer1_run_id=f"l1_{day}"),
            diagnostics=Layer2Diagnostics(
                status="ok",
                data_health=DataHealthScore(overall=0.9, confidence_ceiling=1.0, status="ok"),
            ),
            stress_context=[], vegetation_intelligence=veg,
            phenology_adjusted_indices=[], gaps_inherited=[], conflicts_inherited=[],
        )

        l3_ctx = build_layer3_context(l2_out)
        l3_ctx.phenology_stage = env["stage"]

        # Inject scenario signals
        l3_ctx.operational_signals.update({
            "sar_available": env["sar_available"],
            "optical_available": env["optical_available"],
            "rain_available": True, "temp_available": True,
            "sar_obs_count": 5 if env["sar_available"] else 0,
            "optical_obs_count": 5 if env["optical_available"] else 0,
            "water_deficit_severity": env["anomaly_severity"] if "drought" in scenario or "transpiration" in scenario or "recovery" in scenario else 0.0,
            "thermal_severity": env["anomaly_severity"] if scenario == "heat_wave" else 0.0,
            "has_anomaly": env["anomaly_type"] != "NONE",
            "anomaly_severity": env["anomaly_severity"],
            "anomaly_type": env["anomaly_type"],
            "growth_velocity": env["growth_velocity"],
        })

        # Build features
        features = build_decision_features(l3_ctx, plot_ctx)

        # Inject environment into features
        features.rain_sum_14d = env["rain_sum_14d"]
        features.days_since_rain = env["days_since_rain"]
        features.saturation_days = env["saturation_days"]
        features.sar_roughness_change = env["sar_roughness"]
        features.spatial_stability = env["spatial_stability"]

        from layer3_decision.schema import Driver
        if not env["sar_available"]:
            features.missing_inputs.append(Driver.SAR_VV)
        if not env["optical_available"]:
            features.missing_inputs.append(Driver.NDVI)

        # Diagnose
        engine = DiagnosisEngine()
        diagnoses = engine.diagnose(features, plot_ctx)

        # Policy
        policy = PolicyEngine()
        actions = [a.action_id for a in policy.generate_plan(diagnoses, plot_ctx, None, features.missing_inputs)]

        delta_t = round(env["lst"] - env["t_air"], 1)
        esi = round(features.esi, 2) if hasattr(features, 'esi') else 0.0

        snap = {
            "day": day, "date": current_date.strftime("%Y-%m-%d"),
            "stage": env["stage"],
            "t_air": round(env["t_air"], 1), "lst": round(env["lst"], 1),
            "delta_t": delta_t, "esi": esi,
            "ndvi": round(env["ndvi"], 2),
            "rain_14d": round(env["rain_sum_14d"], 1),
            "irr_mm": env["irrigation_today_mm"],
            "diags": [d.problem_id for d in diagnoses],
            "actions": actions,
        }
        history.append(snap)

    return {
        "plot_id": plot_def["id"],
        "crop": registration.crop_type,
        "irrigation_type": registration.irrigation_type,
        "soil_texture": soil.texture_class(),
        "soil_whc": soil_props.get("whc_mm_per_m"),
        "area_ha": registration.area_ha,
        "polygon_wkt": registration.polygon_wkt[:40] + "...",
        "adapter_packets": len(adapter_output.observation_packets),
        "crop_params_used": list(crop_params.keys()),
        "history": history,
    }


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    results = {}
    for p in PLOTS:
        print(f"Simulating {p['id']}...")
        results[p["id"]] = simulate_plot(p, SEASON_START, SEASON_DAYS)

    out_path = os.path.join(os.path.dirname(__file__), "user_input_season_audit.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSimulation complete. Results written to {out_path}")

    # Print summary
    print("\n" + "=" * 80)
    print("EXTENDED SEASON SIMULATION SUMMARY")
    print("=" * 80)
    for pid, data in results.items():
        history = data["history"]
        all_diags = set()
        first_diag_day = {}
        for snap in history:
            for d in snap["diags"]:
                all_diags.add(d)
                if d not in first_diag_day:
                    first_diag_day[d] = snap["day"]

        soil_info = f"Soil={data['soil_texture']} (WHC={data['soil_whc']}mm/m)"
        irr_info = f"Irrig={data['irrigation_type']}"
        print(f"\n{pid} | {data['crop']} | {irr_info} | {soil_info}")
        print(f"  Adapter packets: {data['adapter_packets']} | Crop params: {len(data['crop_params_used'])} keys")
        if all_diags:
            for diag in sorted(all_diags):
                print(f"  -> {diag} (first on Day {first_diag_day[diag]})")
        else:
            print(f"  -> No diagnoses (optimal)")
