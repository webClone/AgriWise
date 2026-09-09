"""
Comprehensive Simulation Suite for Layer 2 and Layer 3 Integration.

Simulates 10 rigorous, real-world agronomic and meteorological scenarios
exercising every diagnostic functionality across:
  - Layer 2 Vegetation & Stress Intelligence Engine
  - Layer 3 Canonical Water Intelligence World Model (SPAC)
  - Layer 3 Decision & Action Intelligence Engine (Log-Odds Inference, Policy Gating, DAG Execution)
"""

import math
import sys
import datetime
from datetime import timezone
from typing import Dict, Any, List

# Add repository root and agribrain to python path
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "agribrain")))

# Layer 1 Data Contracts
from layer1_fusion.schemas import (
    Layer2InputContext,
    DataHealthScore,
    EvidenceConflict,
    EvidenceGap,
    SpatialIndex,
    CropCycleContext,
)

# Layer 2 Contracts & Engines
from layer2_intelligence.engine import Layer2IntelligenceEngine
from layer2_intelligence.outputs.layer3_adapter import build_layer3_context
from layer2_intelligence.schemas import Layer2Output

# Layer 3 Water Intelligence (SPAC Model)
from layer3_water.runner import WaterIntelligenceEngine
from layer3_water.contracts.authority import SolverFidelity
from layer3_water.contracts.atmospheric_state import AtmosphericInputQuality, CanopyTemperatureState
from layer3_water.contracts.assimilation_state import SoilObservationVector
from layer3_water.contracts.irrigation_state import IrrigationConstraints, IrrigationObjective, IrrigationMethod
from layer3_water.contracts.water_state import HydraulicStressMemoryState

# Layer 3 Decision Intelligence
from layer3_decision.runner import DecisionIntelligenceEngine
from layer3_decision.schema import PlotContext, ProblemClass, RiskIfWrong, DecisionOutput


def run_scenario(
    name: str,
    description: str,
    l2_context: Layer2InputContext,
    plot_context: PlotContext,
    weather_forecast: List[Dict[str, Any]],
    water_model_inputs: Dict[str, Any] = None,
) -> Dict[str, Any]:
    print("=" * 80)
    print(f"SCENARIO: {name}")
    print(f"DESCRIPTION: {description}")
    print("=" * 80)

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Execute Layer 2 Intelligence Engine
    # ─────────────────────────────────────────────────────────────────────────
    l2_engine = Layer2IntelligenceEngine()
    l2_output: Layer2Output = l2_engine.analyze(
        context=l2_context,
        run_timestamp=datetime.datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    print(f"\n[LAYER 2 INTELLIGENCE OUTPUT]")
    print(f"  • Diagnostic Status: {l2_output.diagnostics.status.upper()}")
    print(f"  • Data Health Overall: {l2_output.data_health.overall:.3f} (Ceiling: {l2_output.data_health.confidence_ceiling:.3f})")
    print(f"  • Stress Evidence Items ({len(l2_output.stress_context)}):")
    for s in l2_output.stress_context:
        syn = f" (Synergy x{s.compound_synergy_factor:.2f} with {s.compound_partner})" if s.compound_partner else ""
        bayes = f" [Bayes P={s.hypothesis_posterior:.3f}]" if s.hypothesis_posterior is not None else ""
        print(f"    - [{s.stress_type}] Mag: {s.stress_magnitude:.3f}, Biol Impact: {s.biological_impact:.3f}, Conf: {s.confidence:.3f}, Unc: {s.uncertainty:.3f}{syn}{bayes}")
        print(f"      Driver: {s.primary_driver}")
        for exp in s.explanation_basis[:2]:
            print(f"      Evidence: {exp}")

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Inter-Layer Boundary Adapter: Layer 2 -> Layer 3
    # ─────────────────────────────────────────────────────────────────────────
    l3_input_context = build_layer3_context(l2_output)

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Execute Layer 3 Decision Intelligence Engine
    # ─────────────────────────────────────────────────────────────────────────
    l3_engine = DecisionIntelligenceEngine()
    l3_output: DecisionOutput = l3_engine.run_decision_cycle(
        l3_context=l3_input_context,
        plot_context=plot_context,
        weather_forecast=weather_forecast,
        run_timestamp=datetime.datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    print(f"\n[LAYER 3 DECISION INTELLIGENCE OUTPUT]")
    print(f"  • Reliability Score: {l3_output.quality_metrics.decision_reliability:.3f} ({l3_output.quality_metrics.degradation_mode.value})")
    print(f"  • Diagnoses ({len(l3_output.diagnoses)}):")
    for d in l3_output.diagnoses:
        print(f"    - [{d.problem_id}] P={d.probability:.1%}, Severity={d.severity:.3f}, Conf={d.confidence:.3f}")
        for tr in d.evidence_trace[:2]:
            print(f"      Evidence: {tr.feature_name} (score={tr.score:+.2f}, wt={tr.weight:.1f}, contrib={tr.contribution:+.2f})")
    
    print(f"  • Prescriptive Recommendations ({len(l3_output.recommendations)}):")
    for r in l3_output.recommendations:
        status = "ALLOWED" if r.is_allowed else f"BLOCKED: {', '.join(r.blocked_reason)}"
        dose = f" -> Dose: {r.resource_est.get('irrigation_dose_mm', 0)}mm" if 'irrigation_dose_mm' in r.resource_est else ""
        print(f"    - [{r.action_id}] Type: {r.action_type}, Priority: {r.priority_score:.3f}, Status: {status}{dose}")
        print(f"      Explain: {r.explain}")

    print(f"  • Execution Plan DAG Tasks ({len(l3_output.execution_plan.tasks)}):")
    for t in l3_output.execution_plan.tasks:
        deps = f" (Depends on: {', '.join(t.depends_on)})" if t.depends_on else ""
        print(f"    - Task: {t.task_id} [{t.type}]{deps}")

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Optional: Execute Layer 3 Canonical Water World Model (SPAC)
    # ─────────────────────────────────────────────────────────────────────────
    if water_model_inputs:
        print(f"\n[LAYER 3 CANONICAL WATER WORLD MODEL (SPAC)]")
        water_engine = WaterIntelligenceEngine()
        weather_dict = {
            "t_max_c": water_model_inputs.get("t_max", 28.0),
            "t_min_c": water_model_inputs.get("t_min", 16.0),
            "net_radiation_mj_m2": water_model_inputs.get("r_n", 18.5),
            "wind_speed_2m_m_s": water_model_inputs.get("u2", 2.0),
            "rh_min_pct": water_model_inputs.get("rh_min", 40.0),
            "rh_max_pct": water_model_inputs.get("rh_max", 85.0),
            "precipitation_mm": water_model_inputs.get("precip", 0.0),
        }
        water_state, feedback_l2 = water_engine.execute_pipeline(
            plot_id=l2_context.plot_id,
            timestamp=datetime.datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
            weather_observations=weather_dict,
            soil_type=water_model_inputs.get("soil_texture", "loam"),
            irrigation_applied_mm=water_model_inputs.get("irrigation", 0.0),
            soil_observations=water_model_inputs.get("observations"),
            canopy_temperature_state=water_model_inputs.get("thermal_canopy"),
            irrigation_constraints=IrrigationConstraints(max_single_dose_mm=45.0),
            irrigation_objective=IrrigationObjective(),
        )
        print(f"  • Canopy Demand: ET0={water_state.fluxes.potential.et0_mm:.2f}mm, Kcb={water_state.fluxes.potential.kcb:.2f}, Ke={water_state.fluxes.potential.ke:.2f} -> ETp={water_state.fluxes.potential.etp_mm:.2f} mm/day")
        print(f"  • Root Zone: TAW={water_state.root_zone.total_available_water_mm:.1f}mm, RAW={water_state.root_zone.readily_available_water_mm:.1f}mm, Dr={water_state.root_zone.root_zone_depletion_mm:.1f}mm, Ks={water_state.root_zone.stress_factor_ks:.3f}")
        print(f"  • Realized Fluxes: Tact={water_state.fluxes.actual.actual_transpiration_mm:.2f}mm, Tdeficit={water_state.fluxes.actual.transpiration_deficit_mm:.2f}mm")
        print(f"  • Mass Balance Error: {water_state.mass_balance_error_mm:.5f} mm")
        if water_state.active_decision:
            print(f"  • MPC Decision: {water_state.active_decision.action.value} -> Net: {water_state.active_decision.recommended_net_mm:.1f}mm, Gross: {water_state.active_decision.recommended_gross_mm:.1f}mm (Urgency: {water_state.active_decision.urgency.value})")
        print(f"  • L3->L2 Feedback Receipt: Ks Constraint = {feedback_l2.transpiration_constraint_factor:.3f}, Tdeficit = {feedback_l2.transpiration_deficit_mm:.2f}mm, Depletion Fraction = {feedback_l2.root_zone_depletion_fraction:.3f}")
        print(f"  • Hydraulic Memory: Exposure Class = {water_state.hydraulic_memory.drought_exposure_class}, Consecutive Stress Days = {water_state.hydraulic_memory.consecutive_days_under_limitation}")

    print("\n")
    return {
        "l2_output": l2_output,
        "l3_output": l3_output,
    }


def main():
    print("\n" + "#" * 80)
    print("STARTING HEAVY INTEGRATION SIMULATIONS: LAYER 2 & LAYER 3")
    print("#" * 80 + "\n")

    # =========================================================================
    # SCENARIO 1: Flash Drought & Extreme Heatwave with LST Thermal Overheating
    # =========================================================================
    run_scenario(
        name="1. Flash Drought & Extreme Heatwave (Compound Stress)",
        description="Extreme 41°C heatwave, VPD 4.2 kPa, NDMI drop (0.06), soil moisture 0.09 m3/m3, LST canopy +6.5°C overheating",
        l2_context=Layer2InputContext(
            plot_id="plot_algeria_wheat_01",
            water_context={
                "ndmi_mean": {"value": 0.06, "source_evidence_ids": ["ev_s2_ndmi_01"]},
                "soil_moisture_vwc": {"value": 0.09, "source_evidence_ids": ["ev_probe_sm_01"]},
                "precipitation_mm": {"value": 0.0, "source_evidence_ids": ["ev_rain_01"]},
            },
            vegetation_context={
                "ndvi_mean": {"value": 0.52, "source_evidence_ids": ["ev_s2_ndvi_01"]},
                "evi_mean": {"value": 0.28, "source_evidence_ids": ["ev_s2_evi_01"]},
                "canopy_cover_fraction": {"value": 0.65, "source_evidence_ids": ["ev_drone_cc_01"]},
            },
            stress_evidence_context={
                "temp_max": {"value": 41.0, "source_evidence_ids": ["ev_weather_tmax_01"]},
                "vpd": {"value": 4.2, "source_evidence_ids": ["ev_weather_vpd_01"]},
                "et0_mm": {"value": 7.8, "source_evidence_ids": ["ev_weather_et0_01"]},
            },
            operational_context={
                "lst_canopy_c": 47.5,
                "t_air_c": 41.0,
                "vpd_kpa": 4.2,
                "et0_mm": 7.8,
                "ndvi_mean": 0.52,
            },
            data_health=DataHealthScore(overall=0.92, confidence_ceiling=0.95, status="ok"),
        ),
        plot_context=PlotContext(crop_type="wheat", irrigation_type="drip", soil_texture_class="sandy_loam"),
        weather_forecast=[
            {"date": "2026-06-16", "temp_max": 42.0, "temp_min": 24.0, "rain": 0.0, "et0": 8.1},
            {"date": "2026-06-17", "temp_max": 43.0, "temp_min": 25.0, "rain": 0.0, "et0": 8.4},
            {"date": "2026-06-18", "temp_max": 40.0, "temp_min": 23.0, "rain": 0.0, "et0": 7.9},
            {"date": "2026-06-19", "temp_max": 38.0, "temp_min": 21.0, "rain": 0.0, "et0": 7.2},
            {"date": "2026-06-20", "temp_max": 36.0, "temp_min": 20.0, "rain": 0.0, "et0": 6.8},
        ],
        water_model_inputs={
            "t_max": 41.0, "t_min": 23.0, "r_n": 22.5, "u2": 3.2, "rh_min": 18.0, "rh_max": 45.0,
            "lai": 2.8, "fvc": 0.65, "root_depth": 0.75, "soil_texture": "sandy_loam",
            "precip": 0.0, "irrigation": 0.0,
            "thermal_canopy": CanopyTemperatureState(
                canopy_temperature_c=47.5,
                air_temperature_c=41.0,
                vapor_pressure_deficit_kpa=4.2,
                evaporative_cooling_deficit_c=6.5,
            ),
        }
    )

    # =========================================================================
    # SCENARIO 2: Severe Post-Storm Waterlogging & Hypoxia (Mutual Exclusion)
    # =========================================================================
    run_scenario(
        name="2. Catastrophic Waterlogging & Soil Anoxia (Mutual Exclusion Gating)",
        description="85mm rain storm, soil saturated at 0.48 m3/m3, 4 saturation days, standing water specular drop",
        l2_context=Layer2InputContext(
            plot_id="plot_nile_delta_maize_02",
            water_context={
                "ndmi_mean": {"value": 0.45, "source_evidence_ids": ["ev_s2_ndmi_02"]},
                "soil_moisture_vwc": {"value": 0.48, "source_evidence_ids": ["ev_probe_sm_02"]},
                "precipitation_mm": {"value": 85.0, "source_evidence_ids": ["ev_rain_02"]},
            },
            vegetation_context={
                "ndvi_mean": {"value": 0.48, "source_evidence_ids": ["ev_s2_ndvi_02"]},
                "veg_water_anomaly": {"value": 0.85, "source_evidence_ids": ["ev_s2_anom_02"]},
            },
            stress_evidence_context={
                "temp_max": {"value": 26.0, "source_evidence_ids": ["ev_weather_tmax_02"]},
                "vpd": {"value": 0.8, "source_evidence_ids": ["ev_weather_vpd_02"]},
            },
            operational_context={
                "has_anomaly": True,
                "anomaly_type": "DROP",
                "anomaly_severity": 0.65,
                "saturation_days": 4,
                "rain_sum_7d": 85.0,
            },
            data_health=DataHealthScore(overall=0.90, confidence_ceiling=0.95, status="ok"),
        ),
        plot_context=PlotContext(crop_type="maize", irrigation_type="pivot", soil_texture_class="clay_loam"),
        weather_forecast=[
            {"date": "2026-06-16", "temp_max": 25.0, "temp_min": 17.0, "rain": 25.0, "et0": 3.2},
            {"date": "2026-06-17", "temp_max": 24.0, "temp_min": 16.0, "rain": 12.0, "et0": 3.0},
            {"date": "2026-06-18", "temp_max": 26.0, "temp_min": 18.0, "rain": 0.0, "et0": 4.1},
        ],
        water_model_inputs={
            "t_max": 26.0, "t_min": 17.0, "r_n": 14.0, "u2": 2.1, "rh_mean": 85.0,
            "lai": 3.5, "fvc": 0.80, "root_depth": 0.90, "soil_texture": "clay_loam",
            "precip": 85.0, "irrigation": 0.0,
        }
    )

    # =========================================================================
    # SCENARIO 3: Nitrogen Deficiency vs Drought Disambiguation
    # =========================================================================
    run_scenario(
        name="3. Nitrogen Deficiency (Chlorosis without Water Deficit)",
        description="Low NDVI 0.32, negative growth velocity (-0.004), but soil moisture 0.28 m3/m3, NDMI 0.38 adequate",
        l2_context=Layer2InputContext(
            plot_id="plot_morocco_barley_03",
            crop_context=CropCycleContext(
                crop_type="barley",
                current_stage="VEGETATIVE",
                gdd_accumulated=320.0,
            ),
            water_context={
                "ndmi_mean": {"value": 0.38, "source_evidence_ids": ["ev_s2_ndmi_03"]},
                "soil_moisture_vwc": {"value": 0.28, "source_evidence_ids": ["ev_probe_sm_03"]},
                "precipitation_mm": {"value": 18.0, "source_evidence_ids": ["ev_rain_03"]},
            },
            vegetation_context={
                "ndvi_mean": {"value": 0.32, "source_evidence_ids": ["ev_s2_ndvi_03"]},
                "evi_mean": {"value": 0.19, "source_evidence_ids": ["ev_s2_evi_03"]},
                "canopy_uniformity_cv": {"value": 0.35, "source_evidence_ids": ["ev_drone_cv_03"]},
            },
            stress_evidence_context={
                "temp_max": {"value": 24.0, "source_evidence_ids": ["ev_weather_tmax_03"]},
                "vpd": {"value": 1.2, "source_evidence_ids": ["ev_weather_vpd_03"]},
            },
            operational_context={
                "growth_velocity": -0.004,
                "current_stage": "VEGETATIVE",
                "days_since_rain": 3,
                "rain_sum_14d": 24.0,
                "real_rain_available": True,
                "real_rain_sum_14d": 24.0,
                "real_days_since_rain": 3,
            },
            data_health=DataHealthScore(overall=0.88, confidence_ceiling=0.90, status="ok"),
        ),
        plot_context=PlotContext(crop_type="barley", irrigation_type="sprinkler", soil_texture_class="loam"),
        weather_forecast=[
            {"date": "2026-06-16", "temp_max": 24.0, "temp_min": 14.0, "rain": 0.0, "et0": 4.5},
            {"date": "2026-06-17", "temp_max": 25.0, "temp_min": 15.0, "rain": 0.0, "et0": 4.8},
        ],
    )

    # =========================================================================
    # SCENARIO 4: High-Wind Storm & Crop Lodging (Mechanical Damage)
    # =========================================================================
    run_scenario(
        name="4. High-Wind Storm & Severe Lodging at Flowering Stage",
        description="Reproductive wheat, wind speed 17.5 m/s, rain 38mm, SAR roughness disruption 1.9",
        l2_context=Layer2InputContext(
            plot_id="plot_tunisia_durum_04",
            crop_context=CropCycleContext(
                crop_type="wheat",
                current_stage="REPRODUCTIVE",
                gdd_accumulated=820.0,
            ),
            water_context={
                "ndmi_mean": {"value": 0.32, "source_evidence_ids": ["ev_s2_ndmi_04"]},
                "precipitation_mm": {"value": 38.0, "source_evidence_ids": ["ev_rain_04"]},
            },
            vegetation_context={
                "ndvi_mean": {"value": 0.58, "source_evidence_ids": ["ev_s2_ndvi_04"]},
            },
            stress_evidence_context={
                "temp_max": {"value": 22.0, "source_evidence_ids": ["ev_weather_tmax_04"]},
                "wind_speed_ms": {"value": 17.5, "source_evidence_ids": ["ev_weather_wind_04"]},
            },
            operational_context={
                "wind_speed_ms": 17.5,
                "sar_available": True,
                "sar_obs_count": 2,
                "sar_roughness_change": 1.9,
                "rain_sum_7d": 38.0,
                "current_stage": "REPRODUCTIVE",
                "spatial_stability": "HETEROGENEOUS",
                "mechanical_damage_detected": True,
                "mechanical_damage_severity": 0.75,
                "has_drone_structural": True,
            },
            data_health=DataHealthScore(overall=0.91, confidence_ceiling=0.95, status="ok"),
        ),
        plot_context=PlotContext(crop_type="wheat", irrigation_type="pivot", soil_texture_class="silt_loam"),
        weather_forecast=[
            {"date": "2026-06-16", "temp_max": 21.0, "temp_min": 12.0, "rain": 5.0, "et0": 3.8},
        ],
    )

    # =========================================================================
    # SCENARIO 5: Pre-Flowering Forecast Frost Risk
    # =========================================================================
    run_scenario(
        name="5. Forecast-Driven Frost Warning in Reproductive Stage",
        description="Flowering wheat (Ky=0.85), mild current weather 18°C, but 7-day NWP predicts -3.2°C freeze in 3 days",
        l2_context=Layer2InputContext(
            plot_id="plot_setif_high_plateau_05",
            crop_context=CropCycleContext(
                crop_type="wheat",
                current_stage="REPRODUCTIVE",
                gdd_accumulated=790.0,
            ),
            water_context={
                "ndmi_mean": {"value": 0.35, "source_evidence_ids": ["ev_s2_ndmi_05"]},
                "precipitation_mm": {"value": 12.0, "source_evidence_ids": ["ev_rain_05"]},
            },
            vegetation_context={
                "ndvi_mean": {"value": 0.68, "source_evidence_ids": ["ev_s2_ndvi_05"]},
            },
            stress_evidence_context={
                "temp_max": {"value": 18.0, "source_evidence_ids": ["ev_weather_tmax_05"]},
            },
            operational_context={
                "current_stage": "REPRODUCTIVE",
                "real_rain_available": True,
                "real_rain_sum_14d": 12.0,
                "real_days_since_rain": 4,
            },
            data_health=DataHealthScore(overall=0.94, confidence_ceiling=0.95, status="ok"),
        ),
        plot_context=PlotContext(crop_type="wheat", irrigation_type="sprinkler", soil_texture_class="clay_loam"),
        weather_forecast=[
            {"date": "2026-06-16", "temp_max": 14.0, "temp_min": 4.0, "rain": 0.0, "et0": 3.2},
            {"date": "2026-06-17", "temp_max": 8.0, "temp_min": -1.5, "rain": 0.0, "et0": 2.1},
            {"date": "2026-06-18", "temp_max": 6.0, "temp_min": -3.2, "rain": 0.0, "et0": 1.8},
            {"date": "2026-06-19", "temp_max": 9.0, "temp_min": -0.5, "rain": 0.0, "et0": 2.4},
            {"date": "2026-06-20", "temp_max": 15.0, "temp_min": 3.0, "rain": 0.0, "et0": 3.5},
        ],
    )

    # =========================================================================
    # SCENARIO 6: Arid Soil Salinity & Osmotic Crisis (Allbed & Kumar 2013)
    # =========================================================================
    run_scenario(
        name="6. Severe Soil Salinity & Osmotic Crisis (MENA Arid Basin)",
        description="Soil EC 9.8 dS/m, NDMI depressed 0.11 (salt crusting), EVI/NDVI ratio 0.58, low rainfall context",
        l2_context=Layer2InputContext(
            plot_id="plot_biskra_palm_date_06",
            crop_context=CropCycleContext(
                crop_type="date_palm",
                current_stage="VEGETATIVE",
                gdd_accumulated=1200.0,
            ),
            water_context={
                "ndmi_mean": {"value": 0.11, "source_evidence_ids": ["ev_s2_ndmi_06"]},
                "precipitation_mm": {"value": 0.0, "source_evidence_ids": ["ev_rain_06"]},
            },
            vegetation_context={
                "ndvi_mean": {"value": 0.38, "source_evidence_ids": ["ev_s2_ndvi_06"]},
                "evi_mean": {"value": 0.22, "source_evidence_ids": ["ev_s2_evi_06"]},
            },
            soil_site_context={
                "soil_ec_ds_m": {"value": 9.8, "source_evidence_ids": ["ev_soil_ec_06"]},
            },
            stress_evidence_context={
                "temp_max": {"value": 38.0, "source_evidence_ids": ["ev_weather_tmax_06"]},
                "vpd": {"value": 3.2, "source_evidence_ids": ["ev_weather_vpd_06"]},
            },
            operational_context={
                "spatial_stability": "HETEROGENEOUS",
                "growth_velocity": 0.001,
                "soil_ec_ds_m": 9.8,
                "real_rain_available": True,
                "real_rain_sum_14d": 0.0,
                "real_days_since_rain": 25,
            },
            data_health=DataHealthScore(overall=0.89, confidence_ceiling=0.92, status="ok"),
        ),
        plot_context=PlotContext(crop_type="date_palm", irrigation_type="drip", soil_texture_class="sandy_loam"),
        weather_forecast=[
            {"date": "2026-06-16", "temp_max": 39.0, "temp_min": 24.0, "rain": 0.0, "et0": 7.5},
        ],
    )

    # =========================================================================
    # SCENARIO 7: Fungal Disease Outbreak Window (Warm-Wet Fusarium Risk)
    # =========================================================================
    run_scenario(
        name="7. Fungal Disease Outbreak Microclimate Window (Warm-Wet)",
        description="Rain 34mm/7d, moderate temp 23.5°C, flowering wheat head blight window",
        l2_context=Layer2InputContext(
            plot_id="plot_mitidja_cereal_07",
            water_context={
                "ndmi_mean": {"value": 0.36, "source_evidence_ids": ["ev_s2_ndmi_07"]},
                "precipitation_mm": {"value": 34.0, "source_evidence_ids": ["ev_rain_07"]},
            },
            vegetation_context={
                "ndvi_mean": {"value": 0.65, "source_evidence_ids": ["ev_s2_ndvi_07"]},
            },
            stress_evidence_context={
                "temp_max": {"value": 23.5, "source_evidence_ids": ["ev_weather_tmax_07"]},
            },
            operational_context={
                "rain_sum_7d": 34.0,
                "current_stage": "REPRODUCTIVE",
                "heat_stress_days": 0,
                "cold_stress_days": 0,
            },
            data_health=DataHealthScore(overall=0.92, confidence_ceiling=0.95, status="ok"),
        ),
        plot_context=PlotContext(crop_type="wheat", irrigation_type="sprinkler", soil_texture_class="clay_loam"),
        weather_forecast=[
            {"date": "2026-06-16", "temp_max": 24.0, "temp_min": 16.0, "rain": 18.0, "et0": 3.4},
            {"date": "2026-06-17", "temp_max": 22.0, "temp_min": 15.0, "rain": 15.0, "et0": 3.0},
        ],
    )

    # =========================================================================
    # SCENARIO 8: Drone Weed Pressure & Row Break Structural Damage
    # =========================================================================
    run_scenario(
        name="8. Drone Photogrammetry: Weed Infestation & Row Breaks",
        description="Drone RGB detects weed pressure 0.52, canopy CV 0.42, 4 row breaks, bare soil gaps 0.28",
        l2_context=Layer2InputContext(
            plot_id="plot_constantine_orchard_08",
            water_context={
                "ndmi_mean": {"value": 0.30, "source_evidence_ids": ["ev_s2_ndmi_08"]},
            },
            vegetation_context={
                "ndvi_mean": {"value": 0.45, "source_evidence_ids": ["ev_s2_ndvi_08"]},
                "weed_pressure_index": {"value": 0.52, "source_evidence_ids": ["ev_drone_weed_08"]},
                "canopy_uniformity_cv": {"value": 0.42, "source_evidence_ids": ["ev_drone_cv_08"]},
                "bare_soil_fraction": {"value": 0.28, "source_evidence_ids": ["ev_drone_soil_08"]},
            },
            operational_context={
                "row_continuity_mean": {"value": 0.55, "source_evidence_ids": ["ev_drone_row_08"]},
                "row_break_count": {"value": 4, "source_evidence_ids": ["ev_drone_break_08"]},
                "has_drone_structural": True,
                "weed_pressure_index": 0.52,
                "weed_pressure_severity": 0.52,
                "canopy_uniformity_cv": 0.42,
                "bare_soil_fraction": 0.28,
                "mechanical_damage_detected": True,
                "mechanical_damage_severity": 0.45,
            },
            data_health=DataHealthScore(overall=0.95, confidence_ceiling=0.98, status="ok"),
        ),
        plot_context=PlotContext(crop_type="olive", irrigation_type="drip", soil_texture_class="loam"),
        weather_forecast=[
            {"date": "2026-06-16", "temp_max": 28.0, "temp_min": 17.0, "rain": 0.0, "et0": 5.2},
        ],
    )

    # =========================================================================
    # SCENARIO 9: Multi-Day Hydraulic Stress Memory & Receding Horizon MPC
    # =========================================================================
    run_scenario(
        name="9. Severe Prolonged Drought & Closed-Loop MPC Optimization",
        description="14-day persistent drying across 5 soil layers, in-situ probe assimilation, MPC dosage optimization",
        l2_context=Layer2InputContext(
            plot_id="plot_chlef_citrus_09",
            water_context={
                "ndmi_mean": {"value": 0.09, "source_evidence_ids": ["ev_s2_ndmi_09"]},
                "soil_moisture_vwc": {"value": 0.12, "source_evidence_ids": ["ev_probe_sm_09"]},
                "precipitation_mm": {"value": 0.0, "source_evidence_ids": ["ev_rain_09"]},
            },
            vegetation_context={
                "ndvi_mean": {"value": 0.54, "source_evidence_ids": ["ev_s2_ndvi_09"]},
            },
            stress_evidence_context={
                "temp_max": {"value": 37.0, "source_evidence_ids": ["ev_weather_tmax_09"]},
                "vpd": {"value": 3.4, "source_evidence_ids": ["ev_weather_vpd_09"]},
            },
            operational_context={
                "days_since_rain": 18,
                "rain_sum_14d": 0.0,
                "current_stage": "REPRODUCTIVE",
            },
            data_health=DataHealthScore(overall=0.92, confidence_ceiling=0.95, status="ok"),
        ),
        plot_context=PlotContext(crop_type="citrus", irrigation_type="drip", soil_texture_class="loam"),
        weather_forecast=[
            {"date": "2026-06-16", "temp_max": 37.0, "temp_min": 21.0, "rain": 0.0, "et0": 6.8},
            {"date": "2026-06-17", "temp_max": 38.0, "temp_min": 22.0, "rain": 0.0, "et0": 7.1},
            {"date": "2026-06-18", "temp_max": 36.0, "temp_min": 20.0, "rain": 0.0, "et0": 6.5},
        ],
        water_model_inputs={
            "t_max": 37.0, "t_min": 21.0, "r_n": 21.0, "u2": 2.5, "rh_mean": 32.0,
            "lai": 3.8, "fvc": 0.82, "root_depth": 1.0, "soil_texture": "loam",
            "precip": 0.0, "irrigation": 0.0,
            "observations": SoilObservationVector(
                timestamp=datetime.datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
                soil_probe_moisture_profile=[0.11, 0.13, 0.16, 0.19, 0.22],
                satellite_surface_moisture_m3_m3=0.10,
                canopy_cooling_differential_c=5.5,
            ),
        }
    )

    # =========================================================================
    # SCENARIO 10: Unusable Data Health Guardrails & Hard Prohibitions
    # =========================================================================
    run_scenario(
        name="10. Unusable Data Quality Mode & Hard Prohibitions Guardrails",
        description="L1 data health collapsed (overall 0.08), missing optical/SAR, testing WAIT_FOR_VALID_DATA gate",
        l2_context=Layer2InputContext(
            plot_id="plot_corrupted_sensor_10",
            water_context={},
            vegetation_context={},
            stress_evidence_context={},
            operational_context={},
            conflicts=[
                EvidenceConflict(
                    conflict_id="conf_01",
                    conflict_type="RADAR_OPTICAL_DISCORDANCE",
                    variable_group="vegetation",
                    spatial_scope="plot",
                    severity="major",
                    description="Contradictory radar/optical telemetry",
                )
            ],
            gaps=[EvidenceGap(gap_id="gap_01", gap_type="NO_RECENT_SENTINEL1", severity="major")],
            data_health=DataHealthScore(overall=0.08, confidence_ceiling=0.15, status="unusable"),
        ),
        plot_context=PlotContext(crop_type="wheat", irrigation_type="drip", soil_texture_class="loam"),
        weather_forecast=[],
    )

    print("#" * 80)
    print("ALL 10 HEAVY INTEGRATION SIMULATIONS COMPLETED SUCCESSFULLY!")
    print("#" * 80 + "\n")


if __name__ == "__main__":
    main()
