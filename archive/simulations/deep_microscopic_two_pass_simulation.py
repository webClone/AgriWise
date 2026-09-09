"""
Deep Microscopic Two-Pass ASMAE & Physics-Informed Layer 2/3 Simulation.

Full architectural realization of:
  Pass 1: Layer 1 Coarse Alignment -> Layer 2 Initial Phenology & Crop Posterior
  Pass 2: ASMAE Prior Bridge -> ASMAE Foundation Multi-Modal Inversion
  Pass 3: Refined Layer 2 Stress Attribution & Bayesian Simplex
          -> Layer 3 SPAC 5-Layer Richards / Van Genuchten / Feddes Infiltration
          -> Layer 3 1D Optimal Interpolation Kalman Filter
          -> Layer 3 Closed-Loop Receding Horizon MPC Optimization
          -> Layer 3 Decision Probabilistic Log-Odds & Policy DAG Task Execution
"""

import math
import sys
import os
import datetime
from datetime import timezone
from typing import Dict, Any, List, Tuple

# Path setup
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "agribrain")))

import numpy as np

# Layer 1
from layer1_fusion.schemas import (
    Layer2InputContext,
    CropCycleContext,
    DataHealthScore,
    EvidenceConflict,
    EvidenceGap,
)

# Layer 2
from layer2_contracts.state_contracts import (
    UncertaintyBudget,
    StressMagnitudeState,
    StressHypothesisState,
    StressImpactEstimate,
    VegetationState,
)
from layer2_contracts.state_transition import VegetationStateTransitionModel
from layer2_veg_int.growth_engine import GrowthCurveEngine
from layer2_veg_int.phenology_engine import PhenologyEngine
from layer2_veg_int.schema import PhenologyStage, VegIntOutput, SpatialMetrics
from layer2_veg_int.asmae_prior_bridge import build_asmae_crop_prior, ASMAECropPrior
from layer2_intelligence.engine import Layer2IntelligenceEngine
from layer2_intelligence.stress_attributor import attribute_stress
from layer2_intelligence.outputs.layer3_adapter import build_layer3_context

# Layer 3 Water
from layer3_water.runner import WaterIntelligenceEngine
from layer3_water.contracts.atmospheric_state import CanopyTemperatureState
from layer3_water.contracts.assimilation_state import SoilObservationVector
from layer3_water.contracts.irrigation_state import (
    IrrigationConstraints,
    IrrigationObjective,
    IrrigationMethod,
)
from layer3_water.contracts.water_state import SoilWaterState, InfiltrationState, SoilEvaporationState

# Layer 3 Decision
from layer3_decision.runner import DecisionIntelligenceEngine
from layer3_decision.schema import PlotContext


def run_microscopic_two_pass_simulation():
    print("=" * 95)
    print("MICROSCOPIC TWO-PASS ASMAE + LAYER 2 + LAYER 3 INTEGRATION SIMULATION")
    print("=" * 95)

    timestamp = datetime.datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    plot_id = "plot_chlef_pivot_07"

    # =========================================================================
    # PASS 1: COARSE LAYER 1/2 STATE & PHENOLOGY ESTIMATION
    # =========================================================================
    print("\n" + "-" * 35 + " [PASS 1: COARSE PHENOLOGY & PRIOR DISCOVERY] " + "-" * 35)
    
    # 60 days of historical S2 NDVI telemetry for wheat
    d_history = 60
    history_dates = [(datetime.date(2026, 3, 21) + datetime.timedelta(days=i)).isoformat() for i in range(d_history)]
    raw_ndvi_series = [0.20 + 0.55 / (1.0 + math.exp(-0.10 * (i - 28))) + np.random.normal(0, 0.02) for i in range(d_history)]
    ndvi_unc = [0.03] * d_history

    growth_engine = GrowthCurveEngine()
    fitted_ndvi, derivs, fit_unc = growth_engine.fit_growth_curve(history_dates, raw_ndvi_series, ndvi_unc)
    
    gdd_series = [12.5 * (i + 1) for i in range(d_history)]
    pheno_engine = PhenologyEngine(
        crop_config={
            "transitions": {
                "emergence_min_gdd": 120, "vegetative_min_gdd": 350,
                "reproductive_min_gdd": 800, "senescence_min_gdd": 1500,
            }
        },
        latitude=36.2,
    )
    stages, confs = pheno_engine.infer_daily_stages(fitted_ndvi, derivs["velocity"], history_dates, gdd_series)
    
    current_stage = stages[-1].name
    current_ndvi = fitted_ndvi[-1]
    current_lai = growth_engine.estimate_lai([current_ndvi])[0]
    current_fvc = growth_engine.compute_fvc([current_ndvi])[0]

    print(f"  * Pass 1 Fitted Growth State: NDVI = {current_ndvi:.3f} | LAI = {current_lai:.2f} m2/m2 | FVC = {current_fvc:.2%}")
    print(f"  * Inferred Biological Stage: {current_stage} (Confidence: {confs[-1]:.2%}) | Total Thermal Time: {gdd_series[-1]:.1f} GDD")

    # Construct Mock VegIntOutput to pass to ASMAE Prior Bridge
    class SyntheticVegInt:
        def __init__(self):
            self.provenance = {"crop_type": "wheat", "identified_crop": "durum_wheat"}
            self.phenology = type("P", (), {"stage_by_day": [s.name for s in stages]})()
            self.spatial = SpatialMetrics(stability_class="STABLE", mean_spatial_var=0.04, std_spatial_var=0.01)
            self.anomalies = []

    # =========================================================================
    # PASS 2: ASMAE FOUNDATION PRIOR BRIDGE & LATENT INVERSION
    # =========================================================================
    print("\n" + "-" * 35 + " [PASS 2: ASMAE FOUNDATION INVERSION & PRIORS] " + "-" * 35)
    
    asmae_crop_prior: ASMAECropPrior = build_asmae_crop_prior(SyntheticVegInt())
    print(f"  * ASMAE Prior Bridge Emitted: available={asmae_crop_prior.available}, crop_group={asmae_crop_prior.crop_group_used}")
    print(f"  * Ingested Biophysical Constraints: LAI Bounds = {asmae_crop_prior.lai_bounds}, Chlorophyll = {asmae_crop_prior.chlorophyll_bounds}")

    # Simulated ASMAE Calibrated Multi-Channel Feature Vectors
    calibrated_asmae_features = {
        "ASMAE_CANOPY_WATER_THICKNESS": {
            "value": 0.14,
            "confidence": 0.94,
            "uncertainty": 0.03,
            "resolution_m": 10.0,
            "channel": "SCWA_SWIR_INVERSION",
        },
        "ASMAE_ROOT_ZONE_ANOMALY": {
            "value": 0.68,
            "confidence": 0.91,
            "uncertainty": 0.04,
            "resolution_m": 20.0,
            "channel": "S1_SAR_POLARIMETRIC_INVERSION",
        },
        "ASMAE_STRUCTURAL_TEXTURE": {
            "value": 0.88,
            "confidence": 0.96,
            "uncertainty": 0.02,
            "resolution_m": 10.0,
            "channel": "MSI_TEXTURE_ENTROPY",
        },
        "ASMAE_VIGOR": {
            "value": 0.62,
            "confidence": 0.95,
            "uncertainty": 0.03,
            "resolution_m": 10.0,
            "channel": "DIAGNOSTIC_VIGOR",
        },
    }
    print("  * ASMAE Multi-Channel Features Synthesized:")
    for k, v in calibrated_asmae_features.items():
        print(f"    - [{k}] Val: {v['value']:.2f}, Conf: {v['confidence']:.2f}, Res: {v['resolution_m']}m ({v['channel']})")

    # =========================================================================
    # PASS 3: REFINED LAYER 2 & LAYER 3 CLOSED-LOOP INTEGRATION
    # =========================================================================
    print("\n" + "-" * 35 + " [PASS 3: REFINED STRESS ATTRIBUTION & SPAC WORLD MODEL] " + "-" * 35)

    # 1. Execute Refined Layer 2 Intelligence with Ingested ASMAE Features
    l2_input_context = Layer2InputContext(
        plot_id=plot_id,
        crop_context=CropCycleContext(
            crop_type="wheat",
            variety="Simeto",
            current_stage=current_stage,
            gdd_accumulated=gdd_series[-1],
            irrigation_type="drip",
            soil_texture_class="loam",
        ),
        water_context={
            "ndmi_mean": {"value": 0.08, "source_evidence_ids": ["ev_s2_ndmi_01"]},
            "soil_moisture_vwc": {"value": 0.11, "source_evidence_ids": ["ev_probe_01"]},
            "precipitation_mm": {"value": 0.0, "source_evidence_ids": ["ev_rain_01"]},
        },
        vegetation_context={
            "ndvi_mean": {"value": current_ndvi, "source_evidence_ids": ["ev_s2_ndvi_01"]},
            "evi_mean": {"value": 0.35, "source_evidence_ids": ["ev_s2_evi_01"]},
            "lai": {"value": current_lai, "source_evidence_ids": ["ev_lai_01"]},
        },
        stress_evidence_context={
            "temp_max": {"value": 39.5, "source_evidence_ids": ["ev_weather_tmax_01"]},
            "vpd": {"value": 3.8, "source_evidence_ids": ["ev_weather_vpd_01"]},
            "wind_speed_ms": {"value": 3.5, "source_evidence_ids": ["ev_weather_wind_01"]},
        },
        soil_site_context={
            "soil_ec_ds_m": {"value": 4.5, "source_evidence_ids": ["ev_soil_ec_01"]},
        },
        asmae_features=calibrated_asmae_features,
        operational_context={
            "growth_velocity": derivs["velocity"][-1],
            "current_stage": current_stage,
            "days_since_rain": 14,
            "rain_sum_14d": 0.0,
            "real_rain_available": True,
            "real_rain_sum_14d": 0.0,
            "real_days_since_rain": 14,
            "soil_ec_ds_m": 4.5,
            "sar_available": True,
            "sar_obs_count": 2,
        },
        data_health=DataHealthScore(overall=0.94, confidence_ceiling=0.98, status="ok"),
    )

    l2_engine = Layer2IntelligenceEngine()
    l2_output = l2_engine.analyze(l2_input_context, run_timestamp=timestamp)

    print(f"\n[LAYER 2 ATTRIBUTED DIAGNOSTICS]")
    for s in l2_output.stress_context:
        syn = f" (Synergy x{s.compound_synergy_factor:.2f} with {s.compound_partner})" if s.compound_partner else ""
        print(f"  * [{s.stress_type:10s}] Mag: {s.stress_magnitude:.3f}, Impact: {s.biological_impact:.3f}, Conf: {s.confidence:.3f}{syn}")
        print(f"    Driver: {s.primary_driver}")

    # 2. Execute Layer 3 SPAC Multi-Layer Richards & Van Genuchten Physics
    print(f"\n[LAYER 3 SPAC CANONICAL WORLD MODEL (VAN GENUCHTEN & FEDDES)]")
    
    water_engine = WaterIntelligenceEngine()
    
    # Atmospheric forcing
    t_max = 39.5
    t_min = 21.0
    rn_mj_m2 = 23.4
    vpd_kpa = 3.8
    
    # In-situ TDR probe profile assimilation across 5 discrete depths
    probe_assimilation = SoilObservationVector(
        timestamp=timestamp,
        soil_probe_moisture_profile=[0.105, 0.122, 0.148, 0.185, 0.220],
        satellite_surface_moisture_m3_m3=0.095,
        canopy_cooling_differential_c=4.8,
    )

    water_state, feedback_l2 = water_engine.execute_pipeline(
        plot_id=plot_id,
        timestamp=timestamp,
        weather_observations={
            "t_max_c": t_max,
            "t_min_c": t_min,
            "net_radiation_mj_m2": rn_mj_m2,
            "wind_speed_2m_m_s": 3.5,
            "rh_min_pct": 18.0,
            "rh_max_pct": 45.0,
            "precipitation_mm": 0.0,
        },
        soil_type="loam",
        soil_observations=probe_assimilation,
        canopy_temperature_state=CanopyTemperatureState(
            canopy_temperature_c=t_max + 4.8,
            air_temperature_c=t_max,
            vapor_pressure_deficit_kpa=vpd_kpa,
            evaporative_cooling_deficit_c=4.8,
        ),
        irrigation_constraints=IrrigationConstraints(max_single_dose_mm=45.0),
        irrigation_objective=IrrigationObjective(),
    )

    # Inspect 5-layer vertical matric potential & unsaturated conductivity
    depths = water_state.soil_water.layer_depths_cm
    thetas = water_state.soil_water.theta_profile
    psi_m = water_state.soil_water.matric_potential_profile_mpa
    k_unsat = water_state.soil_water.unsaturated_conductivity_profile_cm_day

    print(f"  * Reference Evapotranspiration: ET0 = {water_state.fluxes.potential.et0_mm:.2f} mm/day | VPD = {water_state.atmospheric_quality.overall_confidence:.2f}")
    print(f"  * Canopy Demand Partition: Kcb = {water_state.fluxes.potential.kcb:.2f}, Ke = {water_state.fluxes.potential.ke:.2f} -> ETp = {water_state.fluxes.potential.etp_mm:.2f} mm/day")
    print(f"  * 5-Layer Vertical Soil Hydraulic Discretization:")
    for j in range(len(depths)):
        psi_str = f"{psi_m[j]:.3f} MPa" if j < len(psi_m) else "N/A"
        k_str = f"{k_unsat[j]:.4f} cm/d" if j < len(k_unsat) else "N/A"
        print(f"    - Layer {j+1} (Depth 0-{depths[j]:3.0f} cm): theta = {thetas[j]:.3f} m3/m3 | Suction psi_m = {psi_str} | K(theta) = {k_str}")

    print(f"  * Root-Zone Water Stress Factor: Ks = {water_state.root_zone.stress_factor_ks:.3f} (TAW = {water_state.root_zone.total_available_water_mm:.1f}mm, Dr = {water_state.root_zone.root_zone_depletion_mm:.1f}mm)")
    print(f"  * Realized Fluxes: Tact = {water_state.fluxes.actual.actual_transpiration_mm:.2f} mm/day, Transpiration Deficit = {water_state.fluxes.actual.transpiration_deficit_mm:.2f} mm/day")
    print(f"  * Data Assimilation: Method = {water_state.assimilation_diagnostic.assimilation_method} (Variance Reduction = {water_state.assimilation_diagnostic.variance_reduction_fraction:.1%})")
    print(f"  * Closed-Loop MPC Optimization: Action = {water_state.active_decision.action.value} -> Net: {water_state.active_decision.recommended_net_mm:.1f}mm, Gross: {water_state.active_decision.recommended_gross_mm:.1f}mm (Urgency: {water_state.active_decision.urgency.value})")

    # 3. Execute Layer 3 Decision Intelligence Engine (Log-Odds & Execution DAG)
    print(f"\n[LAYER 3 DECISION INTELLIGENCE & DAG EXECUTION PLAN]")
    
    l3_adapter_context = build_layer3_context(l2_output)
    decision_engine = DecisionIntelligenceEngine()
    plot_context = PlotContext(crop_type="wheat", irrigation_type="drip", soil_texture_class="loam")
    
    forecast_7d = [
        {"date": "2026-05-21", "temp_max": 40.0, "temp_min": 22.0, "rain": 0.0, "et0": 7.8},
        {"date": "2026-05-22", "temp_max": 41.0, "temp_min": 23.0, "rain": 0.0, "et0": 8.1},
        {"date": "2026-05-23", "temp_max": 38.0, "temp_min": 21.0, "rain": 0.0, "et0": 7.4},
        {"date": "2026-05-24", "temp_max": 36.0, "temp_min": 20.0, "rain": 0.0, "et0": 6.9},
        {"date": "2026-05-25", "temp_max": 34.0, "temp_min": 18.0, "rain": 0.0, "et0": 6.2},
    ]

    l3_output = decision_engine.run_decision_cycle(
        l3_context=l3_adapter_context,
        plot_context=plot_context,
        weather_forecast=forecast_7d,
        run_timestamp=timestamp,
    )

    print(f"  * Decision Reliability Score: {l3_output.quality_metrics.decision_reliability:.3f}")
    print(f"  * Diagnoses ({len(l3_output.diagnoses)}):")
    for d in l3_output.diagnoses:
        print(f"    - [{d.problem_id}] P = {d.probability:.1%}, Severity = {d.severity:.3f}, Confidence = {d.confidence:.3f}")
        for tr in d.evidence_trace[:2]:
            print(f"      * {tr.feature_name}: score={tr.score:+.2f}, wt={tr.weight:.1f}, contrib={tr.contribution:+.2f}")

    print(f"  * Policy Recommendations ({len(l3_output.recommendations)}):")
    for r in l3_output.recommendations:
        print(f"    - [{r.action_id}] Type: {r.action_type}, Priority: {r.priority_score:.3f}, Status: {'ALLOWED' if r.is_allowed else 'BLOCKED'}")
        print(f"      Explain: {r.explain}")

    print(f"  * Execution Plan DAG Tasks ({len(l3_output.execution_plan.tasks)}):")
    for task in l3_output.execution_plan.tasks:
        deps = f" -> Depends on: {', '.join(task.depends_on)}" if task.depends_on else ""
        print(f"    - Task ID: {task.task_id} [{task.type}]{deps}")

    print("\n" + "=" * 95)
    print("MICROSCOPIC TWO-PASS ASMAE + L2 + L3 SIMULATION COMPLETED SUCCESSFULLY!")
    print("=" * 95 + "\n")


if __name__ == "__main__":
    run_microscopic_two_pass_simulation()
