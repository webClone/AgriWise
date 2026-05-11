"""
Layer 4 Runner — Clean L3->L4 Interface.

Orchestrates all Layer 4 engines:
  1. SWB (Soil Water Balance) — FAO-56 with user soil + irrigation
  2. SAR Tillage Detection + SOC dynamics
  3. CDU (Crop Demand) — multi-crop uptake curves
  4. NOP (Nutrient Observation Proxy) — spectral + soil lab evidence
  5. Inference — Full N/P/K Bayesian
  6. Optimization — response curve portfolio
  7. Planner — phenology-aware DAG

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
    TillageDetection, SOCDynamics, NutrientBudget,
)
from layer1_fusion.schemas import DataHealthScore

from layer4_nutrients.soil_water_balance.engine import SoilWaterBalanceEngine
from layer4_nutrients.crop_demand.engine import CropDemandUptakeEngine
from layer4_nutrients.proxies.engine import (
    NutrientObservationProxyEngine, detect_tillage, estimate_soc_mineralization,
)
from layer4_nutrients.inference.engine import NutrientInferenceEngine
from layer4_nutrients.optimization.engine import OptimizationEngine
from layer4_nutrients.planner.engine import PlanningEngine
from layer4_nutrients.invariants import enforce_layer4_invariants

L4_VERSION = "2.0.0"
ENGINE_VERSIONS = {
    "swb": "2.0.0", "cdu": "2.0.0", "proxies": "2.0.0",
    "inference": "2.0.0", "optimization": "2.0.0", "planner": "2.0.0",
    "tillage_detection": "1.0.0", "soc_dynamics": "1.0.0",
}


def _deterministic_run_id(plot_id: str, l3_run_id: str, policy: Dict) -> str:
    policy_str = json.dumps(policy, sort_keys=True, default=str)
    raw = f"{plot_id}|{l3_run_id}|{policy_str}|{L4_VERSION}"
    return f"L4-{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


def run_layer4_standalone(
    plot_id: str = "P1",
    crop_type: str = "corn",
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
    ndvi: float = 0.5,  # Conservative default (was 0.7 synthetic "healthy")
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
) -> NutrientIntelligenceOutput:
    """Run the full Layer 4 pipeline standalone.

    This is the primary entry point for testing and simulation.
    """
    constraints = constraints or {}
    soil_props = soil_props or {}

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
    if daily_weather:
        temps = [w.get("t_max", 25.0) for w in daily_weather]
        avg_temp = sum(temps) / len(temps) if temps else 22.0

    soc = estimate_soc_mineralization(
        soc_pct=soc_pct, soc_source=soc_source,
        tillage=tillage, clay_pct=clay_pct, temperature_c=avg_temp,
    )

    # 3. SWB
    swb_engine = SoilWaterBalanceEngine()
    weather = daily_weather or [{"et0": 4.0, "rain_mm": 0.0, "t_max": 25.0}] * 30  # rain=0 not synthetic 3.0
    swb = swb_engine.run(
        daily_weather=weather,
        crop_type=crop_type,
        stages=stages,
        soil_props=soil_props,
        irrigation_events=irrigation_events,
    )

    # 4. CDU
    cdu_engine = CropDemandUptakeEngine()
    stg = stages or ["vegetative"] * len(weather)
    demands = cdu_engine.compute_demand(
        crop_type=crop_type, stages=stg,
        management_goal=management_goal,
    )

    # 5. NOP (Proxies)
    nop_engine = NutrientObservationProxyEngine()
    current_stage = stg[-1] if stg else "vegetative"
    evidence = nop_engine.extract_features(
        ndvi=ndvi, stage=current_stage, crop_type=crop_type,
        ndre=ndre, growth_velocity=growth_velocity,
        spatial_heterogeneity=spatial_heterogeneity,
        user_soil_n_ppm=soil_props.get("nitrogen_ppm"),
        user_soil_p_ppm=soil_props.get("phosphorus_ppm"),
        user_soil_k_ppm=soil_props.get("potassium_ppm"),
        user_soil_ph=soil_props.get("ph"),
    )

    # 6. Inference
    nie_engine = NutrientInferenceEngine()
    states = nie_engine.infer_states(
        evidence=evidence, swb=swb, demands=demands,
        l3_decision=l3_decision, soc=soc, tillage=tillage,
    )

    # 7. Optimization
    opt_engine = OptimizationEngine()
    prescriptions = opt_engine.optimize(
        states=states, swb_out=swb,
        crop_type=crop_type, management_goal=management_goal,
        soil_ph=soil_props.get("ph"),
        irrigation_type=irrigation_type, constraints=constraints,
    )

    # 8. Planning
    plan_engine = PlanningEngine()
    plan = plan_engine.create_plan(
        states=states, prescriptions=prescriptions,
        planting_date=planting_date,
    )

    # 9. Nutrient budgets
    budgets = {}
    for nut in MACRO_NUTRIENTS:
        state = states.get(nut)
        if state and state.estimated_demand_kg_ha is not None:
            budgets[nut] = NutrientBudget(
                nutrient=nut,
                crop_removal=state.estimated_demand_kg_ha or 0,
                mineralization=soc.tillage_adjusted_mineralization if nut == Nutrient.N else 0,
                atmospheric_deposition=8.0 if nut == Nutrient.N else 0,
                soil_test_available=(soil_props.get("nitrogen_ppm", 0) * 3.0
                                    if nut == Nutrient.N else 0),
                leaching_loss=swb.n_leaching_kg_ha if nut == Nutrient.N else 0,
            )

    # 10. Quality metrics
    user_soil_available = any(k in soil_props for k in ("nitrogen_ppm", "phosphorus_ppm", "potassium_ppm"))
    quality = QualityMetricsL4(
        decision_reliability=min(s.confidence for s in states.values()) if states else 0.0,
        missing_drivers=[],
        data_completeness={
            "soil_analysis": 1.0 if user_soil_available else 0.0,
            "spectral": 1.0 if ndvi is not None and ndvi > 0 else 0.0,
            "sar_tillage": 1.0 if tillage.detected else 0.0,
        },
        penalties_applied=[],
        user_soil_analysis_available=user_soil_available,
        sar_tillage_available=tillage.detected,
    )

    # 11. Audit
    audit = AuditSnapshot(
        features_snapshot=evidence,
        policy_snapshot=constraints,
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
    run_id = _deterministic_run_id(plot_id, l3_run_id, constraints)
    meta = RunMeta(
        run_id=run_id,
        parent_run_ids=ParentRunIds(l3=l3_run_id),
        generated_at=datetime.now(timezone.utc).isoformat(),
        engine_version=L4_VERSION,
    )

    # 13. Data health
    overall_health = 0.5
    if user_soil_available:
        overall_health += 0.3
    if tillage.detected:
        overall_health += 0.1
    if ndre is not None:
        overall_health += 0.1
    data_health = DataHealthScore(
        overall=min(1.0, overall_health),
        confidence_ceiling=min(s.confidence for s in states.values()) if states else 0.0,
        status="ok" if overall_health > 0.4 else "degraded",
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

    # --- Extract from OrchestratorInput ---
    plot_id = getattr(inputs, "plot_id", "P1") if inputs else "P1"
    crop_cfg = getattr(inputs, "crop_config", {}) or {}
    op_ctx = getattr(inputs, "operational_context", {}) or {}
    policy = getattr(inputs, "policy_snapshot", {}) or {}

    crop_type = crop_cfg.get("crop", crop_cfg.get("crop_type", "corn")).lower()
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
                        print(f"[L4] Using Kalman LAI={kalman_lai:.2f} → NDVI≈{ndvi:.3f}")

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
                        # Only fill defaults when we have SOME real weather
                        w.setdefault("rain_mm", 0.0)
                        if "et0" not in w:
                            w["et0"] = 4.0  # Reasonable but mark as estimated
                        if "t_max" not in w:
                            w["t_max"] = 25.0
                        daily_weather.append(w)

                    # NDVI from raw timeseries (only if Kalman didn't provide)
                    if ndvi is None:
                        ndvi_val = entry.get("ndvi")
                        if ndvi_val is not None:
                            try:
                                candidate = float(ndvi_val)
                                # Only accept if it's a real observation, not interpolated
                                is_observed = entry.get("is_observed", True)
                                if is_observed:
                                    ndvi = candidate
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

        # =============================================================
        # NDVI: If still None after both paths, use a conservative
        # estimate but FLAG IT clearly — no silent synthetic data
        # =============================================================
        if ndvi is None:
            ndvi = 0.5  # Conservative mid-range (NOT 0.7 "healthy")
            print("[L4] WARNING: No real NDVI data available from Kalman or timeseries. "
                  "Using conservative estimate 0.5 — confidence will be penalized.")

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

    if l2_output:
        pheno = getattr(l2_output, "phenology", None)
        if pheno:
            sbd = getattr(pheno, "stage_by_day", [])
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

    # If no stages from L2, use crop config stage if available
    if not stages:
        config_stage = crop_cfg.get("stage", crop_cfg.get("crop_stage"))
        if config_stage and config_stage.lower() != "unknown":
            n = max(len(daily_weather), 30)
            stages = [config_stage.lower()] * n
            print(f"[L4] Using crop config stage '{config_stage}' (no L2 phenology)")
        else:
            n = max(len(daily_weather), 30)
            stages = ["vegetative"] * n
            print("[L4] WARNING: No growth stage data — using 'vegetative' default")

    # If no weather from L1, we CANNOT run SWB reliably
    if not daily_weather:
        print("[L4] WARNING: No weather data from L1 — using minimal defaults for SWB")
        daily_weather = [{"et0": 4.0, "rain_mm": 0.0, "t_max": 25.0}] * len(stages)

    # Ensure stages and weather are same length
    if len(stages) != len(daily_weather):
        min_len = min(len(stages), len(daily_weather))
        stages = stages[:min_len] if len(stages) > min_len else stages + [stages[-1]] * (min_len - len(stages))
        daily_weather = daily_weather[:min_len]

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
    )

