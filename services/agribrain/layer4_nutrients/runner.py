"""
Layer 4 Runner v4.0 — Clean L3->L4 Interface.

Orchestrates all Layer 4 engines (22 engines):
  Original (v2.0):
    1. SWB (Soil Water Balance) — FAO-56 with user soil + irrigation
    2. SAR Tillage Detection + SOC dynamics
    3. CDU (Crop Demand) — multi-crop uptake curves
    4. NOP (Nutrient Observation Proxy) — spectral + soil lab evidence
    5. Inference — Full N/P/K/S Bayesian
    6. Optimization — response curve portfolio
    7. Planner — phenology-aware DAG

  New in v3.0:
    8.  Nutrient Interactions — Liebig minimum + antagonism matrix
    9.  CEC — Cation exchange capacity estimation
    10. Liming — pH management with SMP buffer method
    11. VRA — Variable rate application from L2 zones
    12. Residual Credit — legume/cover crop N credits
    13. NUE — Nutrient use efficiency tracking
    14. Tissue Analysis — DRIS + sufficiency ranges

Accepts either full OrchestratorInput or a simplified L4InputContext
for standalone use and testing.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from layer4_nutrients.schema import (
    NutrientIntelligenceOutput, RunMeta, QualityMetricsL4, AuditSnapshot,
    ParentRunIds, Nutrient, MACRO_NUTRIENTS,
    TillageDetection, SOCDynamics, NutrientBudget, SoilWaterBalanceOutput,
)
from layer1_fusion.schemas import DataHealthScore

# Original engines (v2.0)
from layer4_nutrients.soil_water_balance.engine import SoilWaterBalanceEngine
from layer4_nutrients.crop_demand.engine import CropDemandUptakeEngine
from layer4_nutrients.proxies.engine import (
    NutrientObservationProxyEngine, detect_tillage, estimate_soc_mineralization,
)
from layer4_nutrients.inference.engine import NutrientInferenceEngine
from layer4_nutrients.optimization.engine import OptimizationEngine
from layer4_nutrients.planner.engine import PlanningEngine
from layer4_nutrients.invariants import enforce_layer4_invariants

# New engines (v3.0)
from layer4_nutrients.nutrient_interactions.engine import NutrientInteractionEngine
from layer4_nutrients.soil_chemistry.cec_engine import CECEngine
from layer4_nutrients.soil_chemistry.liming_engine import LimingEngine
from layer4_nutrients.vra.engine import VRAEngine
from layer4_nutrients.residual_credit.engine import ResidualCreditEngine
from layer4_nutrients.nue.engine import NUEEngine
from layer4_nutrients.tissue_analysis.engine import TissueAnalysisEngine

# New engines (v4.0)
from layer4_nutrients.phosphorus_sorption.engine import PhosphorusSorptionEngine
from layer4_nutrients.salinity.engine import SalinityEngine
from layer4_nutrients.biological_fixation.engine import BiologicalFixationEngine
from layer4_nutrients.micronutrient_chemistry.engine import MicronutrientChemistryEngine
from layer4_nutrients.soil_respiration.engine import SoilRespirationEngine
from layer4_nutrients.photosynthesis_nue.engine import PhotosynthesisNUEEngine
from layer4_nutrients.environmental_losses.engine import EnvironmentalLossEngine

L4_VERSION = "4.0.0"
ENGINE_VERSIONS = {
    "swb": "2.1.0", "cdu": "2.0.0", "proxies": "2.0.0",
    "inference": "2.1.0", "optimization": "2.0.0", "planner": "2.0.0",
    "tillage_detection": "1.0.0", "soc_dynamics": "1.0.0",
    # v3.0 engines
    "nutrient_interactions": "1.0.0", "cec": "1.0.0",
    "liming": "1.0.0", "vra": "1.0.0",
    "residual_credit": "1.0.0", "nue": "1.0.0",
    "tissue_analysis": "1.0.0",
    # v4.0 engines
    "phosphorus_sorption": "1.0.0", "salinity": "1.0.0",
    "biological_fixation": "1.0.0", "micronutrient_chemistry": "1.0.0",
    "soil_respiration": "1.0.0", "photosynthesis_nue": "1.0.0",
    "environmental_losses": "1.0.0",
}


def _deterministic_run_id(plot_id: str, l3_run_id: str, policy: Dict) -> str:
    policy_str = json.dumps(policy, sort_keys=True, default=str)
    raw = f"{plot_id}|{l3_run_id}|{policy_str}|{L4_VERSION}"
    return f"L4-{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


def run_layer4_standalone(
    plot_id: str = "P1",
    crop_type: str = "unknown",
    management_goal: str = "yield_max",
    irrigation_type: str = "rainfed",
    planting_date: str = "",
    constraints: Optional[Dict] = None,
    # User soil analysis (from L0 UserInputAdapter)
    soil_props: Optional[Dict[str, Any]] = None,
    crop_params: Optional[Dict[str, Any]] = None,
    # Spectral/environmental data
    daily_weather: Optional[List[Dict]] = None,
    stages: Optional[List[str]] = None,
    ndvi: Optional[float] = None,  # No synthetic default — None preserves true observational missingness
    ndre: Optional[float] = None,
    growth_velocity: float = 0.01,
    spatial_heterogeneity: bool = False,
    # SAR data for tillage
    sar_vv_pre: Optional[float] = None,
    sar_vv_post: Optional[float] = None,
    sar_vh_pre: Optional[float] = None,
    sar_vh_post: Optional[float] = None,
    sar_coherence_drop: float = 0.0,
    # Irrigation events
    irrigation_events: Optional[List[Dict]] = None,
    # L3 decision output
    l3_decision: Any = None,
    l3_run_id: str = "",
    # v3.0: L1 Kalman soil moisture (CONTRACT-1 FIX)
    initial_soil_moisture_mm: Optional[float] = None,
    # v3.0: Previous crop for residual credits
    previous_crop: str = "",
    previous_crop_harvest_type: str = "grain_harvest",
    cover_crop: str = "",
    cover_crop_termination_weeks: int = 4,
    # v3.0: Tissue test data
    tissue_data: Optional[Dict[str, float]] = None,
    # v3.0: Zone data for VRA
    zone_data: Optional[List[Dict]] = None,
    field_area_ha: float = 10.0,
    # v4.0: L2 biophysical features
    l2_biophysical: Optional[Dict[str, Any]] = None,
    # v4.0: Salinity data
    ec_ds_m: float = 0.0,
    irrigation_water_ec: float = 0.0,
    # v4.0: Field topography
    slope_pct: float = 2.0,
    # v8.1: ASMAE Features from central accessor
    asmae_features: Optional[Dict[str, Any]] = None,
    # Canonical Layer 2 crop/phenology authority and hashes.  When supplied,
    # production prescriptions fail closed unless both species and stage are
    # authorized; standalone research calls may omit it.
    semantic_lineage: Optional[Dict[str, Any]] = None,
) -> NutrientIntelligenceOutput:
    """Run the full Layer 4 pipeline standalone.

    This is the primary entry point for testing and simulation.
    """
    constraints = constraints or {}
    soil_props = soil_props or {}
    semantic_lineage = dict(semantic_lineage or {})
    semantic_gate_active = bool(semantic_lineage)
    species_allowed = bool(semantic_lineage.get("species_specific_allowed"))
    stage_allowed = bool(semantic_lineage.get("stage_specific_allowed"))

    # v8.1: Calibrate LAI from ASMAE if available
    if asmae_features:
        lai_feat = asmae_features.get("ASMAE_LAI")
        if lai_feat:
            l2_biophysical = l2_biophysical or {}
            l2_biophysical["lai_current"] = lai_feat.value

    # 1. SAR Tillage Detection
    tillage = detect_tillage(
        sar_vv_pre=sar_vv_pre, sar_vv_post=sar_vv_post,
        sar_vh_pre=sar_vh_pre, sar_vh_post=sar_vh_post,
        coherence_drop=sar_coherence_drop,
    )

    # 2. SOC Dynamics
    soc_pct = soil_props.get("organic_matter_pct", None)
    if soc_pct is not None:
        soc_pct = soc_pct * 0.58  # OM to SOC (van Bemmelen factor)
    soc_source = "user_lab" if "organic_matter_pct" in soil_props else "estimated"
    clay_pct = soil_props.get("clay_pct", 22.0)
    avg_temp = 22.0  # Default seasonal average
    if daily_weather and (not semantic_gate_active or (species_allowed and stage_allowed)):
        temps = [w.get("t_max") for w in daily_weather if w.get("t_max") is not None]
        avg_temp = sum(temps) / len(temps) if temps else 22.0

    soc = estimate_soc_mineralization(
        soc_pct=soc_pct, soc_source=soc_source,
        tillage=tillage, clay_pct=clay_pct, temperature_c=avg_temp,
    )

    # 3. SWB (CONTRACT-1 FIX: pass L1 Kalman soil moisture)
    if daily_weather:
        swb_engine = SoilWaterBalanceEngine()
        swb = swb_engine.run(
            daily_weather=daily_weather,
            crop_type=crop_type,
            stages=stages,
            soil_props=soil_props,
            irrigation_events=irrigation_events,
            initial_soil_moisture_mm=initial_soil_moisture_mm,
        )
    else:
        swb = SoilWaterBalanceOutput(
            theta_fc=0.30,
            theta_wp=0.15,
            theta_sat=0.45,
            taw_mm=150.0,
            raw_mm=75.0,
            water_stress_index=0.0,
            leaching_risk_index=0.0,
            drainage_accum_mm=0.0,
            soil_moisture_mm=0.0,
            is_water_limiting=False,
            deep_percolation_mm=0.0,
            n_leaching_kg_ha=0.0,
            irrigation_applied_mm=0.0,
            effective_precipitation_mm=0.0,
        )

    # 4. CDU
    cdu_engine = CropDemandUptakeEngine()
    weather_len = len(daily_weather) if daily_weather else 0
    stg = stages or ["unknown"] * weather_len
    if semantic_gate_active:
        demands = cdu_engine.compute_posterior_demand(
            stages=stg,
            semantic_lineage=semantic_lineage,
            management_goal=management_goal,
        )
    else:
        demands = cdu_engine.compute_demand(
            crop_type=crop_type, stages=stg,
            management_goal=management_goal,
        )

    # 5. NOP (Proxies)
    nop_engine = NutrientObservationProxyEngine()
    current_stage = stg[-1] if stg else "unknown"
    evidence = nop_engine.extract_features(
        ndvi=ndvi, stage=current_stage, crop_type=crop_type,
        ndre=ndre, growth_velocity=growth_velocity,
        spatial_heterogeneity=spatial_heterogeneity,
        user_soil_n_ppm=soil_props.get("nitrogen_ppm"),
        user_soil_p_ppm=soil_props.get("phosphorus_ppm"),
        user_soil_k_ppm=soil_props.get("potassium_ppm"),
        user_soil_ph=soil_props.get("ph"),
    )

    # v8.1: Feed ASMAE features into evidence dict
    if asmae_features:
        if "ASMAE_CHLOROPHYLL" in asmae_features:
            evidence["asmae_chlorophyll"] = asmae_features["ASMAE_CHLOROPHYLL"].value
        if "ASMAE_CANOPY_WATER" in asmae_features:
            evidence["asmae_water_stress"] = asmae_features["ASMAE_CANOPY_WATER"].value
        if "ASMAE_SALINITY_STRESS" in asmae_features:
            evidence["inferred_salinity_pressure"] = asmae_features["ASMAE_SALINITY_STRESS"].value
        if "ASMAE_BIOTIC_CONFOUNDER_RISK" in asmae_features:
            evidence["asmae_biotic_risk"] = asmae_features["ASMAE_BIOTIC_CONFOUNDER_RISK"].value

    # 6. Inference
    nie_engine = NutrientInferenceEngine()
    states = nie_engine.infer_states(
        evidence=evidence, swb=swb, demands=demands,
        l3_decision=l3_decision, soc=soc, tillage=tillage,
    )

    # ===========================================================
    # v3.0 NEW: Tissue Analysis Integration (SCI-6)
    # ===========================================================
    tissue_result = None
    if tissue_data:
        tissue_engine = TissueAnalysisEngine()
        tissue_result = tissue_engine.interpret(
            tissue_data=tissue_data,
            crop_type=crop_type,
            growth_stage=current_stage,
        )

    # ===========================================================
    # v3.0 NEW: CEC & Base Saturation Analysis
    # ===========================================================
    cec_engine = CECEngine()
    cec_result = cec_engine.estimate_cec(
        clay_pct=soil_props.get("clay_pct", 22.0),
        sand_pct=soil_props.get("sand_pct", 40.0),
        organic_matter_pct=soil_props.get("organic_matter_pct", 2.0),
        ph=soil_props.get("ph"),
    )

    # ===========================================================
    # v3.0 NEW: Liming Engine
    # ===========================================================
    lime_result = None
    soil_ph = soil_props.get("ph")
    if soil_ph is not None and soil_ph < 6.0:
        liming_engine = LimingEngine()
        lime_result = liming_engine.compute_lime_requirement(
            current_ph=soil_ph,
            crop_type=crop_type,
            cec=cec_result.cec_estimated,
            clay_pct=soil_props.get("clay_pct", 22.0),
            organic_matter_pct=soil_props.get("organic_matter_pct", 2.0),
            mg_saturation_low=cec_result.mg_deficiency_risk,
        )

    # ===========================================================
    # v3.0 NEW: Residual N Credit Engine (SCI-4)
    # ===========================================================
    residual_engine = ResidualCreditEngine()
    residual_credits = residual_engine.compute_credits(
        previous_crop=previous_crop,
        harvest_type=previous_crop_harvest_type,
        cover_crop=cover_crop,
        cover_crop_termination_weeks=cover_crop_termination_weeks,
        avg_temperature_c=avg_temp,
    )

    # ===========================================================
    # v3.0 NEW: Nutrient Interaction Analysis (Liebig + Antagonisms)
    # ===========================================================
    interaction_engine = NutrientInteractionEngine()
    interactions = interaction_engine.analyze(states=states)

    # ===========================================================
    # v4.0 NEW: Phosphorus Sorption Engine (Langmuir + fixation)
    # ===========================================================
    p_sorption_engine = PhosphorusSorptionEngine()
    # Get P prescription rate if already estimated from proxies
    p_rate_estimate = 0.0
    for nut, st in states.items():
        if nut == Nutrient.P and st.estimated_demand_kg_ha:
            p_rate_estimate = max(0, (st.estimated_demand_kg_ha or 0) - (st.estimated_available_kg_ha or 0))
    p_sorption_result = p_sorption_engine.compute_p_availability(
        soil_ph=soil_props.get("ph", 6.5),
        clay_pct=soil_props.get("clay_pct", 22.0),
        organic_matter_pct=soil_props.get("organic_matter_pct", 2.0),
        soil_p_ppm=soil_props.get("phosphorus_ppm"),
        p_applied_kg_ha=p_rate_estimate,
    )

    # ===========================================================
    # v4.0 NEW: Salinity Engine (Maas-Hoffman)
    # ===========================================================
    salinity_engine = SalinityEngine()
    inferred_sal = 0.0
    persistent_retro = False
    if asmae_features and "ASMAE_SALINITY_STRESS" in asmae_features:
        sal_feat = asmae_features["ASMAE_SALINITY_STRESS"]
        inferred_sal = sal_feat.value
        persistent_retro = (sal_feat.retro_status == "success_with_holdouts")

    salinity_result = salinity_engine.assess_salinity_impact(
        ec_ds_m=ec_ds_m,
        crop_type=crop_type,
        irrigation_water_ec=irrigation_water_ec,
        inferred_salinity_pressure=inferred_sal,
        historical_salinity_zones=soil_props.get("historical_salinity_zones", False),
        farmer_validation=soil_props.get("farmer_validation", False),
        persistent_retrovalidation=persistent_retro,
    )

    # ===========================================================
    # v4.0 NEW: Biological N Fixation Engine
    # ===========================================================
    bnf_engine = BiologicalFixationEngine()
    bnf_result = bnf_engine.estimate_bnf(
        crop_type=crop_type,
        yield_target_t_ha=demands.yield_target_t_ha if demands else 5.0,
        soil_n_ppm=soil_props.get("nitrogen_ppm", 20.0),
        ph=soil_props.get("ph", 6.5),
        avg_temperature_c=avg_temp,
        water_stress_index=swb.water_stress_index if swb else 0.0,
        organic_matter_pct=soil_props.get("organic_matter_pct", 2.0),
    )

    # ===========================================================
    # v4.0 NEW: Micronutrient Chemistry Engine
    # ===========================================================
    micro_engine = MicronutrientChemistryEngine()
    micro_result = micro_engine.assess_availability(
        ph=soil_props.get("ph", 6.5),
        organic_matter_pct=soil_props.get("organic_matter_pct", 2.0),
        clay_pct=soil_props.get("clay_pct", 22.0),
        water_stress_index=swb.water_stress_index if swb else 0.0,
        p_applied_kg_ha=p_rate_estimate,
        crop_type=crop_type,
    )

    # ===========================================================
    # v4.0 NEW: Soil Respiration Engine (dynamic N mineralization)
    # ===========================================================
    resp_engine = SoilRespirationEngine()
    tillage_cls = tillage.tillage_class.value if tillage and tillage.tillage_class else "UNKNOWN"
    resp_result = resp_engine.compute_seasonal_mineralization(
        daily_weather=daily_weather,
        soc_pct=soc.soc_pct if soc and soc.soc_pct else 1.5,
        clay_pct=soil_props.get("clay_pct", 22.0),
        organic_matter_pct=soil_props.get("organic_matter_pct", 2.0),
        tillage_class=tillage_cls,
        theta_fc=swb.theta_fc if swb else 0.30,
        theta_wp=swb.theta_wp if swb else 0.15,
    )

    # ===========================================================
    # v4.0 NEW: Photosynthesis-NUE Coupling Engine
    # ===========================================================
    l2bp = l2_biophysical or {}
    photo_nue_engine = PhotosynthesisNUEEngine()
    photo_nue_result = photo_nue_engine.analyze(
        crop_type=crop_type,
        lai_current=l2bp.get("lai_current", 3.0),
        fpar_current=l2bp.get("fpar_current", 0.5),
        npp_g_c_m2_day=l2bp.get("npp_current", 5.0),
        wue_from_l2=l2bp.get("wue", 0.0),
        n_applied_kg_ha=0.0,  # Pre-optimization — no prescriptions yet
        soil_n_supply_kg_ha=(
            resp_result.cumulative_n_mineralization_kg_ha +
            bnf_result.total_bnf_kg_ha +
            residual_credits.total_n_credit_kg_ha
        ),
        growth_stage=current_stage,
        days_in_season=len(daily_weather),
    )

    # ===========================================================
    # v4.0 NEW: Environmental Loss Pathways Engine
    # ===========================================================
    env_loss_engine = EnvironmentalLossEngine()
    # We'll compute losses based on the CURRENT soil N status
    # (pre-optimization), then the optimization engine can use
    # these loss fractions to adjust recommendations.
    preliminary_n_rate = 0.0
    n_state = states.get(Nutrient.N)
    if n_state and n_state.estimated_demand_kg_ha:
        preliminary_n_rate = max(0, (n_state.estimated_demand_kg_ha or 0))
    env_loss_result = env_loss_engine.compute_all_losses(
        n_applied_kg_ha=preliminary_n_rate,
        soil_ph=soil_props.get("ph", 6.5),
        clay_pct=soil_props.get("clay_pct", 22.0),
        organic_matter_pct=soil_props.get("organic_matter_pct", 2.0),
        temperature_c=avg_temp,
        total_drainage_mm=swb.deep_percolation_mm if swb else 0.0,
        soil_moisture_vwc=swb.soil_moisture_mm / 300.0 if swb and swb.soil_moisture_mm else 0.25,
        theta_fc=swb.theta_fc if swb else 0.30,
        theta_sat=swb.theta_sat if swb else 0.45,
        root_depth_cm=60.0,
        slope_pct=slope_pct,
        crop_cover_fraction=l2bp.get("vegetation_fraction", 0.5),
    )

    # 7. Optimization
    opt_engine = OptimizationEngine()
    prescriptions = opt_engine.optimize(
        states=states, swb_out=swb,
        crop_type=crop_type, management_goal=management_goal,
        soil_ph=soil_props.get("ph"),
        irrigation_type=irrigation_type, constraints=constraints,
    )

    # ===========================================================
    # v3.0 NEW: Variable Rate Application (VRA)
    # ===========================================================
    vra_results = {}
    if zone_data:
        vra_engine = VRAEngine()
        for rx in prescriptions:
            if rx.rate_kg_ha > 0:
                vra_out = vra_engine.generate_vra_prescription(
                    nutrient=rx.nutrient,
                    base_rate_kg_ha=rx.rate_kg_ha,
                    zone_data=zone_data,
                    field_area_ha=field_area_ha,
                )
                vra_results[rx.nutrient.value] = vra_out
                # Populate zone_rates on the prescription
                rx.zone_rates = {
                    zr.zone_id: zr.adjusted_rate_kg_ha
                    for zr in vra_out.zone_rates
                }

    # 8. Planning
    plan_engine = PlanningEngine()
    plan = plan_engine.create_plan(
        states=states, prescriptions=prescriptions,
        planting_date=planting_date,
    )

    # 9. Nutrient budgets (SCI-3 FIX: add volatilization + immobilization)
    budgets = {}
    for nut in MACRO_NUTRIENTS:
        state = states.get(nut)
        if state and state.estimated_demand_kg_ha is not None:
            # v4.0: Use process-based loss models from EnvironmentalLossEngine
            vol_loss = 0.0
            denitrif_loss = 0.0
            leach_loss = 0.0
            immob_loss = 0.0
            if nut == Nutrient.N:
                vol_loss = env_loss_result.volatilization.loss_kg_ha
                denitrif_loss = env_loss_result.denitrification.loss_kg_ha
                leach_loss = env_loss_result.leaching.loss_kg_ha
                # Immobilization: high C:N residue ties up N
                immob_loss = max(0, -residual_credits.previous_crop_n_credit_kg_ha)

            # v4.0: Use dynamic mineralization from SoilRespirationEngine
            n_mineralization = (
                resp_result.cumulative_n_mineralization_kg_ha
                if nut == Nutrient.N else 0
            )

            # v4.0: Use BNF from BiologicalFixationEngine
            bio_fixation = bnf_result.total_bnf_kg_ha if nut == Nutrient.N else 0

            budgets[nut] = NutrientBudget(
                nutrient=nut,
                crop_removal=state.estimated_demand_kg_ha or 0,
                mineralization=n_mineralization,
                atmospheric_deposition=8.0 if nut == Nutrient.N else 0,
                biological_fixation=bio_fixation,
                soil_test_available=(soil_props.get("nitrogen_ppm", 0) * 3.0
                                    if nut == Nutrient.N else 0),
                leaching_loss=leach_loss if nut == Nutrient.N else 0,
                volatilization_loss=vol_loss,
                denitrification_loss=denitrif_loss,
                immobilization=immob_loss,
                residual_credit=residual_credits.total_n_credit_kg_ha if nut == Nutrient.N else 0,
            )

    # Downstream crop/phenology authority gate.  Nutrient states remain useful
    # diagnostics, but crop-demand rates and timing cannot become executable
    # prescriptions from a declaration, crop group, or UNKNOWN stage.
    semantic_penalties = []
    if semantic_gate_active and not species_allowed:
        semantic_penalties.append({
            "driver": "crop_identity",
            "penalty": 0.40,
            "reason": "species-specific crop demand not authorized",
        })
    if semantic_gate_active and not stage_allowed:
        semantic_penalties.append({
            "driver": "phenology",
            "penalty": 0.35,
            "reason": "stage-specific nutrient timing not authorized",
        })
    if semantic_penalties:
        for state in states.values():
            state.confidence = min(float(state.confidence), 0.30)
            qualifier = (
                "Generic/mixture crop demand only; species-specific deficiency "
                "interpretation is unavailable until canonical crop and stage "
                "authority are present."
            )
            state.notes = f"{state.notes} {qualifier}".strip()
        for prescription in prescriptions:
            prescription.is_allowed = False
            for reason in (
                "crop_identity_uncertain" if not species_allowed else None,
                "phenology_unknown_or_uncertain" if not stage_allowed else None,
            ):
                if reason and reason not in prescription.blocked_reason:
                    prescription.blocked_reason.append(reason)

    # If real NDVI is missing, penalize confidence to reflect widened epistemic uncertainty (Finding #29)
    if ndvi is None or ndvi <= 0.0:
        for s in states.values():
            s.confidence = round(max(0.1, float(s.confidence) * 0.75), 3)

    # 10. Quality metrics
    user_soil_available = any(k in soil_props for k in ("nitrogen_ppm", "phosphorus_ppm", "potassium_ppm"))
    quality = QualityMetricsL4(
        decision_reliability=(
            (min(s.confidence for s in states.values()) if states else 0.0)
            * (1.0 if not semantic_gate_active else (1.0 if species_allowed and stage_allowed else 0.4))
        ),
        missing_drivers=([
            reason for reason, missing in (
                ("CROP_SPECIES_AUTHORITY", not species_allowed),
                ("PHENOLOGY_POSTERIOR", not stage_allowed),
                ("NDVI_SPECTRAL", ndvi is None or ndvi <= 0.0),
            ) if (missing and (semantic_gate_active or reason == "NDVI_SPECTRAL"))
        ]),
        data_completeness={
            "soil_analysis": 1.0 if user_soil_available else 0.0,
            "spectral": 1.0 if ndvi is not None and ndvi > 0 else 0.0,
            "sar_tillage": 1.0 if tillage.detected else 0.0,
            "tissue_test": 1.0 if tissue_data else 0.0,
            "cec": 1.0 if cec_result.cec_source == "user_lab" else 0.3,
            "previous_crop": 1.0 if previous_crop else 0.0,
            "vra_zones": 1.0 if zone_data else 0.0,
        },
        penalties_applied=semantic_penalties,
        user_soil_analysis_available=user_soil_available,
        sar_tillage_available=tillage.detected,
    )

    # 11. Audit
    audit = AuditSnapshot(
        features_snapshot={**evidence, "crop_phenology_lineage": semantic_lineage},
        policy_snapshot={**constraints, "crop_phenology_gate": semantic_lineage},
        model_versions=ENGINE_VERSIONS,
        nutrient_budgets={k.value: {
            "supply": v.total_supply, "demand": v.total_demand,
            "losses": v.total_losses, "balance": v.balance,
            "fertilizer_need": v.fertilizer_need_kg_ha,
        } for k, v in budgets.items()},
        tillage_detection=tillage,
        soc_dynamics=soc,
    )

    # 12. Run meta
    run_id = _deterministic_run_id(
        plot_id, l3_run_id,
        {**constraints, "crop_phenology_lineage": semantic_lineage},
    )
    meta = RunMeta(
        run_id=run_id,
        parent_run_ids=ParentRunIds(l3=l3_run_id),
        generated_at=datetime.now(timezone.utc).isoformat(),
        engine_version=L4_VERSION,
    )

    # 13. Data health
    overall_health = 0.5
    if user_soil_available:
        overall_health += 0.2
    if tillage.detected:
        overall_health += 0.05
    if ndre is not None:
        overall_health += 0.05
    if tissue_data:
        overall_health += 0.10
    if previous_crop:
        overall_health += 0.05
    if zone_data:
        overall_health += 0.05
    
    dh_overall = min(1.0, overall_health)
    dh_ceiling = min(s.confidence for s in states.values()) if states else 0.0
    dh_status = "ok" if overall_health > 0.4 else "degraded"

    # Cap confidence ceiling and overall health if partial weather is present to avoid faking metrics
    has_partial_weather = False
    if daily_weather:
        for w in daily_weather:
            if isinstance(w, dict) and (w.get("rain_mm") is None or w.get("et0") is None or w.get("t_max") is None):
                has_partial_weather = True
                break
    if has_partial_weather:
        dh_overall = min(dh_overall, 0.3)
        dh_ceiling = min(dh_ceiling, 0.3)
        dh_status = "degraded"

    if crop_type == "unknown":
        dh_overall = min(dh_overall, 0.3)
        dh_ceiling = min(dh_ceiling, 0.3)
        dh_status = "degraded"

    if semantic_penalties:
        dh_overall = min(dh_overall, 0.3)
        dh_ceiling = min(dh_ceiling, 0.3)
        dh_status = "degraded"

    data_health = DataHealthScore(
        overall=dh_overall,
        confidence_ceiling=dh_ceiling,
        status=dh_status,
    )

    output = NutrientIntelligenceOutput(
        run_meta=meta,
        nutrient_states=states,
        nutrient_budgets=budgets,
        prescriptions=prescriptions,
        verification_plan=plan,
        swb_output=swb,
        crop_demand=demands,
        tillage_detection=tillage,
        soc_dynamics=soc,
        # v3.0 new engine outputs
        nutrient_interactions=interactions,
        cec_analysis=cec_result,
        lime_requirement=lime_result,
        vra_prescriptions=vra_results,
        residual_credits=residual_credits,
        tissue_analysis=tissue_result,
        # v4.0 new engine outputs
        phosphorus_sorption=p_sorption_result,
        salinity_assessment=salinity_result,
        biological_fixation=bnf_result,
        micronutrient_chemistry=micro_result,
        soil_respiration=resp_result,
        photosynthesis_nue=photo_nue_result,
        environmental_losses=env_loss_result,
        l2_biophysical_snapshot=l2bp,
        # Quality
        quality_metrics=quality,
        data_health=data_health,
        audit=audit,
    )

    # 14. Enforce invariants
    enforce_layer4_invariants(output)

    return output


# ===========================================================================
# Orchestrator-Facing Entry Point
# ===========================================================================

def run_layer4_nutrients(
    inputs: Any,
    l1_output: Any = None,
    l2_output: Any = None,
    l3_output: Any = None,
) -> NutrientIntelligenceOutput:
    """Orchestrator-compatible entry point for Layer 4 Nutrients.

    Called by the orchestrator via:
        _safe_run(LayerId.L4, inputs, l1_output, l2_output, l3_output)

    Also supports legacy test signature:
        run_layer4_nutrients(OrchestratorInput, FieldTensor, VegIntOutput, DecisionOutput)

    Extracts crop config, spectral data, SAR data, weather, phenology, and
    soil analysis from upstream layer outputs, then delegates to
    run_layer4_standalone.
    """

    # v8.1: Extract ASMAE features using the central accessor
    from layer1_fusion.outputs.asmae_feature_view import (
        get_asmae_state_feature,
        is_asmae_state_usable,
    )
    asmae_features = {}
    if l2_output:
        for var in [
            "ASMAE_SALINITY_STRESS",
            "ASMAE_CHLOROPHYLL",
            "ASMAE_LAI",
            "ASMAE_CANOPY_WATER",
            "ASMAE_BIOTIC_CONFOUNDER_RISK"
        ]:
            feat = get_asmae_state_feature(l2_output, var)
            if feat and is_asmae_state_usable(feat):
                asmae_features[var] = feat

    # --- Extract from OrchestratorInput ---
    plot_id = getattr(inputs, "plot_id", "P1") if inputs else "P1"
    crop_cfg = getattr(inputs, "crop_config", {}) or {}
    op_ctx = getattr(inputs, "operational_context", {}) or {}
    policy = getattr(inputs, "policy_snapshot", {}) or {}

    from services.agribrain.common.downstream_crop_context import resolve_downstream_crop_phenology

    crop_semantics = resolve_downstream_crop_phenology(
        inputs=inputs, l2_output=l2_output,
    )
    crop_type = crop_semantics.crop_for_species_engine.lower()
    planting_date = crop_cfg.get("planting_date", "")
    irrigation_type = op_ctx.get("irrigation_type", "rainfed")
    management_goal = op_ctx.get("management_goal", "yield_max")

    # Constraints: merge operational_context.constraints + policy
    constraints = {}
    if isinstance(op_ctx, dict) and "constraints" in op_ctx:
        constraints.update(op_ctx["constraints"])
    if isinstance(policy, dict):
        for k, v in policy.items():
            if "limit" in k.lower() or "max" in k.lower():
                constraints.setdefault(k, v)
    # Also check top-level operational_context keys for NVZ limits
    for k in ("nitrogen_limit_kg_ha", "n_max_kg_ha"):
        if k in op_ctx and k not in constraints:
            constraints[k] = op_ctx[k]

    # --- Extract from L1 FieldTensor ---
    # PRIORITY: Read Kalman daily_state FIRST (uncertainty-aware, gap-filled)
    # FALLBACK: Read raw plot_timeseries only when daily_state is unavailable
    daily_weather = []
    stages_from_l1 = []
    ndvi = None  # NO synthetic fallback — None means "genuinely unknown"
    latest_ts_ndvi = None
    ndvi_from_kalman = False  # Track data provenance
    ndre = None
    sar_vv_pre = None
    sar_vv_post = None
    sar_vh_pre = None
    sar_vh_post = None
    sar_coherence_drop = 0.0
    soil_props = {}

    if l1_output:
        # =============================================================
        # PATH A: Kalman daily_state (preferred — uncertainty-aware)
        # The Kalman filter produces LAI, soil moisture, and canopy
        # stress estimates even through cloud gaps. This is far more
        # informative than raw NDVI for nutrient inference.
        # =============================================================
        kalman_state = getattr(l1_output, "daily_state", {})

        # Kalman output is {zone_id: [day_dicts]} — use "plot" zone
        if isinstance(kalman_state, dict):
            plot_states = kalman_state.get("plot", [])
            if isinstance(plot_states, list) and plot_states:
                # Extract the LAST day's Kalman state for current snapshot
                last_state = plot_states[-1] if plot_states else {}
                if isinstance(last_state, dict):
                    # LAI → approximate NDVI using Beer-Lambert relationship
                    # NDVI ≈ 1 - exp(-k * LAI), k ≈ 0.5 for most crops
                    kalman_lai = last_state.get("lai")
                    if kalman_lai is not None:
                        import math
                        ndvi = 1.0 - math.exp(-0.5 * float(kalman_lai))
                        ndvi_from_kalman = True
                        print(f"[L4] Using Kalman LAI={kalman_lai:.2f} -> NDVI~={ndvi:.3f}")

                    # Also extract soil moisture from Kalman state
                    kalman_sm = last_state.get("soil_moisture_0_10")
                    if kalman_sm is not None:
                        soil_props.setdefault("soil_moisture_pct", float(kalman_sm) * 100)

            # Check for user_soil_analysis in daily_state
            user_soil = kalman_state.get("user_soil_analysis", {})
            if isinstance(user_soil, dict):
                for k in ("nitrogen_ppm", "phosphorus_ppm", "potassium_ppm", "ph",
                           "clay_pct", "organic_matter_pct"):
                    if k in user_soil and k not in soil_props:
                        soil_props[k] = float(user_soil[k])

        # =============================================================
        # PATH B: Raw plot_timeseries (fallback for weather + SAR)
        # Weather data is always sourced from timeseries (Kalman uses
        # it as drivers, not as state). SAR is also extracted here
        # since the Kalman state only stores derived soil moisture.
        # =============================================================
        ts = getattr(l1_output, "plot_timeseries", [])
        if ts and isinstance(ts, list):
            for entry in ts:
                if isinstance(entry, dict):
                    w = {}
                    # Weather (always from timeseries — this is real data)
                    rain = entry.get("precipitation", entry.get("rainfall_mm", entry.get("rain")))
                    if rain is not None:
                        w["rain_mm"] = float(rain)
                    et0 = entry.get("et0", entry.get("ET0"))
                    if et0 is not None:
                        w["et0"] = float(et0)
                    tmax = entry.get("temp_max", entry.get("tmax"))
                    if tmax is not None:
                        w["t_max"] = float(tmax)
                    if w:
                        # Do not default missing fields, preserve them as None to avoid fabrication
                        if "rain_mm" not in w:
                            w["rain_mm"] = None
                        if "et0" not in w:
                            w["et0"] = None
                        if "t_max" not in w:
                            w["t_max"] = None
                        daily_weather.append(w)

                    # NDVI from raw timeseries (collect latest valid real observation)
                    if ndvi is None:
                        ndvi_val = entry.get("ndvi")
                        if ndvi_val is not None:
                            try:
                                candidate = float(ndvi_val)
                                is_observed = entry.get("is_observed", True)
                                if is_observed and candidate > 0.0:
                                    latest_ts_ndvi = candidate
                            except (TypeError, ValueError):
                                pass

                    # NDRE (if available)
                    ndre_val = entry.get("ndre")
                    if ndre_val is not None:
                        ndre = float(ndre_val)

                    # SAR: collect first and last VV/VH for tillage detection
                    vv = entry.get("vv")
                    vh = entry.get("vh")
                    if vv is not None:
                        if sar_vv_pre is None:
                            sar_vv_pre = float(vv)
                        sar_vv_post = float(vv)
                    if vh is not None:
                        if sar_vh_pre is None:
                            sar_vh_pre = float(vh)
                        sar_vh_post = float(vh)

        # Adopt latest valid timeseries NDVI if Kalman did not provide one
        if ndvi is None and latest_ts_ndvi is not None:
            ndvi = latest_ts_ndvi

        # =============================================================
        # Finding #29: Forbid synthetic NDVI default substitution.
        # When no real NDVI is available, keep ndvi as None so that
        # true observational missingness is reported to downstream checks.
        # =============================================================
        if ndvi is None:
            print("[L4] INFO: No real NDVI data available from Kalman or timeseries. "
                  "Preserving ndvi as None — true observational missingness reported.")

        # Soil from FieldTensor static properties
        static = getattr(l1_output, "static", {})
        if isinstance(static, dict):
            if "soil_clay" in static or "soil_clay_mean" in static:
                soil_props["clay_pct"] = float(static.get("soil_clay", static.get("soil_clay_mean", 22.0)))
            if "soil_ph" in static or "soil_ph_mean" in static:
                soil_props["ph"] = float(static.get("soil_ph", static.get("soil_ph_mean", 6.5)))
            if "soil_org_carbon" in static or "soil_org_c_mean" in static:
                soc_val = static.get("soil_org_carbon", static.get("soil_org_c_mean"))
                if soc_val is not None:
                    # SOC → OM conversion (reverse van Bemmelen)
                    soil_props["organic_matter_pct"] = float(soc_val) / 0.58

    # GAP 7: Extract soil lab values from user_evidence (frontend soil analyses)
    # user_evidence comes via operational_context["user_evidence"] with source_type="soil"
    user_evidence_list = op_ctx.get("user_evidence", [])
    if isinstance(user_evidence_list, list):
        for ev in user_evidence_list:
            if not isinstance(ev, dict):
                continue
            if ev.get("source_type") != "soil":
                continue
            payload = ev.get("payload", {}) or {}
            if not isinstance(payload, dict):
                continue
            # Map common frontend keys -> internal soil_props keys
            _soil_key_map = {
                "nitrogen": "nitrogen_ppm",
                "nitrogen_ppm": "nitrogen_ppm",
                "phosphorus": "phosphorus_ppm",
                "phosphorus_ppm": "phosphorus_ppm",
                "potassium": "potassium_ppm",
                "potassium_ppm": "potassium_ppm",
                "ph": "ph",
                "soil_ph": "ph",
                "clay": "clay_pct",
                "clay_pct": "clay_pct",
                "organic_matter": "organic_matter_pct",
                "organic_matter_pct": "organic_matter_pct",
                "organic_carbon": "organic_matter_pct",
            }
            for src_key, dst_key in _soil_key_map.items():
                val = payload.get(src_key)
                if val is not None and dst_key not in soil_props:
                    try:
                        # organic_carbon → OM conversion (van Bemmelen factor)
                        fval = float(val)
                        if src_key == "organic_carbon":
                            fval = fval / 0.58
                        soil_props[dst_key] = fval
                    except (TypeError, ValueError):
                        pass

    # --- Extract from L2 VegIntOutput ---
    stages = []
    spatial_het = False
    growth_velocity = 0.01
    l2_biophysical = {}  # v4.0: populated from L2 health/curve/anomaly data

    if l2_output:
        pheno = getattr(l2_output, "phenology", None)
        if pheno:
            sbd = []  # canonical posterior below is the only stage authority
            if sbd:
                stages = [s.value if hasattr(s, "value") else str(s) for s in sbd]

        # Stability
        stability = getattr(l2_output, "stability", None)
        if stability:
            sc = getattr(stability, "stability_class", "STABLE")
            if sc in ("HETEROGENEOUS", "TRANSIENT_VAR"):
                spatial_het = True

        # Growth velocity from curve derivative
        curve = getattr(l2_output, "curve", None)
        if curve:
            d1 = getattr(curve, "ndvi_fit_d1", [])
            if d1 and isinstance(d1, list):
                growth_velocity = d1[-1] if d1 else 0.01

        # ===========================================================
        # v4.0: Extract L2 biophysical features for new engines
        # ===========================================================
        health = getattr(l2_output, "health_index", None)
        if health:
            l2_biophysical["lai_current"] = getattr(health, "lai_estimate", 0.0)
            l2_biophysical["cwsi"] = getattr(health, "water_stress_index", 0.0)
            l2_biophysical["et_actual"] = getattr(health, "et_actual", 0.0)
            l2_biophysical["et_deficit"] = getattr(health, "et_deficit", 0.0)
            l2_biophysical["fpar_current"] = getattr(health, "fpar_current", 0.0)
            l2_biophysical["vegetation_fraction"] = getattr(health, "vegetation_fraction", 0.0)
            l2_biophysical["wue"] = getattr(health, "wue", 0.0)
            l2_biophysical["crop_water_productivity"] = getattr(health, "crop_water_productivity", 0.0)
            l2_biophysical["ndvi_health"] = getattr(health, "ndvi_health", 0.5)
            l2_biophysical["vigor_trend"] = getattr(health, "vigor_trend", "STABLE")
            l2_biophysical["vigor_slope"] = getattr(health, "vigor_slope", 0.0)

        # Curve-derived time series
        if curve:
            lai_s = getattr(curve, "lai_series", [])
            if lai_s:
                l2_biophysical["lai_series"] = lai_s
            cwsi_s = getattr(curve, "cwsi_series", [])
            if cwsi_s:
                l2_biophysical["cwsi_series"] = cwsi_s
            fpar_s = getattr(curve, "fpar_series", [])
            if fpar_s:
                l2_biophysical["fpar_series"] = fpar_s
            npp_s = getattr(curve, "npp_series", [])
            if npp_s:
                l2_biophysical["npp_series"] = npp_s
                l2_biophysical["npp_current"] = npp_s[-1] if npp_s else 0.0

        # Growth metrics
        gm = getattr(l2_output, "growth_metrics", None)
        if gm:
            l2_biophysical["peak_ndvi"] = getattr(gm, "peak_ndvi", 0.0)
            l2_biophysical["auc_season"] = getattr(gm, "auc_season", 0.0)
            l2_biophysical["sos_date"] = getattr(gm, "sos_date", "")
            l2_biophysical["eos_date"] = getattr(gm, "eos_date", "")
            l2_biophysical["los_days"] = getattr(gm, "los_days", 0)

        # Anomaly attribution — extract nutrient deficiency evidence
        anomalies = getattr(l2_output, "anomalies", [])
        nutrient_anomaly_scores = []
        for anom in (anomalies or []):
            attr = getattr(anom, "attribution", None)
            if attr:
                nd = getattr(attr, "nutrient_deficiency", 0.0)
                if nd > 0.2:
                    nutrient_anomaly_scores.append(nd)
        if nutrient_anomaly_scores:
            l2_biophysical["nutrient_anomaly_score"] = max(nutrient_anomaly_scores)
            l2_biophysical["nutrient_anomaly_count"] = len(nutrient_anomaly_scores)

        # Spatial stability metrics
        if stability:
            l2_biophysical["morans_i"] = getattr(stability, "morans_i", 0.0)
            l2_biophysical["cusum_alarm"] = getattr(stability, "cusum_alarm", False)
            zone_health = getattr(stability, "zone_health_scores", {})
            if zone_health:
                l2_biophysical["zone_health_scores"] = zone_health

    # If no stages from L2, use crop config stage if available
    if not stages:
        config_stage = crop_semantics.stage_for_discrete_engine
        if config_stage and config_stage.lower() != "unknown":
            n = max(len(daily_weather), 30) if daily_weather else 30
            stages = [config_stage.lower()] * n
            print(f"[L4] Using canonical Layer 2 stage '{config_stage}'")
        else:
            n = max(len(daily_weather), 30) if daily_weather else 30
            stages = ["unknown"] * n
            print("[L4] WARNING: No growth stage data — mapping to 'unknown' stage")

    # If no weather from L1, we CANNOT run SWB reliably
    # We do not default daily_weather here to prevent fabricating it.

    # Ensure stages and weather are same length
    if len(stages) != len(daily_weather):
        min_len = min(len(stages), len(daily_weather))
        stages = stages[:min_len] if len(stages) > min_len else stages + [stages[-1]] * (min_len - len(stages))
        daily_weather = daily_weather[:min_len]

    # Extract supported crop management and field history inputs (Finding #28)
    previous_crop = op_ctx.get("previous_crop", crop_cfg.get("previous_crop", ""))
    cover_crop = op_ctx.get("cover_crop", crop_cfg.get("cover_crop", ""))
    tissue_data = op_ctx.get("tissue_data", None)
    initial_soil_moisture_mm = op_ctx.get("initial_soil_moisture_mm", None)

    return run_layer4_standalone(
        plot_id=plot_id,
        crop_type=crop_type,
        management_goal=management_goal,
        irrigation_type=irrigation_type,
        planting_date=planting_date,
        constraints=constraints,
        soil_props=soil_props,
        daily_weather=daily_weather,
        stages=stages,
        ndvi=ndvi,
        ndre=ndre,
        growth_velocity=growth_velocity,
        spatial_heterogeneity=spatial_het,
        sar_vv_pre=sar_vv_pre,
        sar_vv_post=sar_vv_post,
        sar_vh_pre=sar_vh_pre,
        sar_vh_post=sar_vh_post,
        sar_coherence_drop=sar_coherence_drop,
        l3_decision=l3_output,
        l3_run_id=getattr(l3_output, "run_id_l3", "") if l3_output else "",
        initial_soil_moisture_mm=initial_soil_moisture_mm,
        previous_crop=previous_crop,
        cover_crop=cover_crop,
        tissue_data=tissue_data,
        # v4.0: L2 biophysical features
        l2_biophysical=l2_biophysical if l2_biophysical else None,
        # v8.1: ASMAE features
        asmae_features=asmae_features,
        semantic_lineage={
            **crop_semantics.lineage(),
            "selected_crop": crop_semantics.selected_crop,
            "selected_group": crop_semantics.selected_group,
            "phenology_stage": crop_semantics.phenology_stage,
            "crop_mixture": dict(crop_semantics.crop_mixture),
            "stage_posterior": dict(crop_semantics.stage_posterior),
            "crop_stage_evidence_class": (
                "species_stage_posterior" if crop_semantics.prescriptive_ready
                else "group_mixture" if crop_semantics.crop_resolution == "group_only"
                else "generic_bounded_mixture"
            ),
        },
    )

