import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

from services.agribrain.orchestrator_v2.schema import LayerResult, OrchestratorInput, GlobalDegradation
from services.agribrain.layer3_decision.schema import ExecutionPlan
from services.agribrain.layer7_planning.schema import Layer7Output, CropOptionEvaluation

# 8 Engines
from services.agribrain.layer7_planning.engines.ccl_crop_library import get_crop_profile
from services.agribrain.layer7_planning.engines.pwe_planting_window import compute_planting_window
from services.agribrain.layer7_planning.engines.ste_seedbed import compute_soil_workability
from services.agribrain.layer7_planning.engines.wfe_water_feasibility import compute_water_feasibility
from services.agribrain.layer7_planning.engines.brf_biotic_risk import compute_biotic_risk
from services.agribrain.layer7_planning.engines.yve_yield_distribution import compute_yield_distribution
from services.agribrain.layer7_planning.engines.eoe_economics import compute_economics
from services.agribrain.layer7_planning.engines.ped_planner import generate_execution_plan

logger = logging.getLogger(__name__)

def run(inputs: OrchestratorInput, l1_res: Any, l5_res: Any = None, chat_memory = None) -> Any:
    """
    Layer 7: Season Planning, Crop Suitability & Economics Intelligence (v7.0)
    Aggregates all 8 probabilistic engines.
    """
    logger.info("[Layer 7] Running advanced Planning Engine...")
    
    # 0. Deterministic Hashing (skipping logic for brevity of this module structure)
    run_meta = {
        "run_id": "L7_RUN_PENDING",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    
    # 1. Inputs Gathering
    raw_crop = inputs.crop_config.get("crop")
    target_crop = (raw_crop or "potato").lower().strip()
    if target_crop == "unknown":
        target_crop = "potato"
        
    current_date = datetime.strptime(inputs.date_range["end"], "%Y-%m-%d")
    l1_out = l1_res
    l5_out = l5_res
        
    soil_texture = "unknown"
    irrigation_type = "unknown"
    
    # 1.a Priorities: L1 Static Data -> Memory -> 'unknown'
    if l1_out and getattr(l1_out, "static", None):
        st = l1_out.static.get("texture_class", "")
        if st and st != "unknown":
            soil_texture = st
            
    if chat_memory and getattr(chat_memory, "known_context", None):
        if soil_texture == "unknown":
            soil_texture = chat_memory.known_context.get("soil_type", "unknown")
        irrigation_type = chat_memory.known_context.get("irrigation_type", "unknown")
        soil_moisture = chat_memory.known_context.get("soil_moisture", "unknown")
    else:
        soil_moisture = "unknown"
        
    # 2. Candidate Evaluation Loop (MVP: Evaluating just the target crop, could expand later)
    options: List[CropOptionEvaluation] = []
    
    # Engine A: CCL
    profile = get_crop_profile(target_crop)
    if not profile:
        from services.agribrain.orchestrator_v2.schema import LayerStatus
        return LayerResult(
            layer_id="L7",
            status=LayerStatus.FAILED,
            output=None,
            errors=[f"Crop {target_crop} unsupported in library. No CCL profile."]
        )
        
    # Engine B: PWE
    window_state = compute_planting_window(current_date, profile, l1_out)
    
    # Engine C: STE
    soil_state = compute_soil_workability(profile, l1_out, soil_texture, soil_moisture)
    
    # Engine D: WFE
    water_state = compute_water_feasibility(profile, l1_out, irrigation_type)
    
    # Engine E: BRF
    biotic_state = compute_biotic_risk(profile, l1_out, l5_out, chat_memory)
    
    # Engine F: YVE
    yield_dist = compute_yield_distribution(profile, window_state, water_state, soil_state, biotic_state)
    
    # Engine G: EOE
    # user_context dict to fetch localized prices
    user_context = {} 
    econ_outcome = compute_economics(profile, yield_dist, user_context)
    
    # 3. Overall Rank Score Synthesis & Suitability Percentage
    # Score is used for sorting candidates
    score = (econ_outcome.expected_profit * 0.4) + (econ_outcome.profit_p10 * 0.3) + (window_state.probability_ok * 1000)
    if window_state.severity == "CRITICAL" or water_state.severity == "CRITICAL":
         score -= 5000
    if soil_state.severity == "CRITICAL":
         score -= 2000
         
    # 4. Rigorous Suitability Percentage f(window, water, soil, disease, economics)
    # Normalize economics roughly (0 to 5000 DZD margin bounds approx)
    econ_prob = max(0.0, min(1.0, econ_outcome.expected_profit / 5000.0))
    
    # Base Weightings: 30% Window, 25% Water, 20% Soil, 10% Biotic, 15% Economics
    base_window_w = 0.30
    base_water_w  = 0.25
    base_soil_w   = 0.20
    base_bio_w    = 0.10
    base_econ_w   = 0.15
    
    # Calculate uncertainty penalties (missing data = lower confidence)
    pen_window = base_window_w * (1.0 - window_state.confidence)
    pen_water  = base_water_w  * (1.0 - water_state.confidence)
    pen_soil   = base_soil_w   * (1.0 - soil_state.confidence)
    pen_bio    = base_bio_w    * (1.0 - biotic_state.confidence)
    
    # Continuous Uncertainty Weighting (Probabilities weighted by base weights)
    raw_suitability = (
        (window_state.probability_ok * base_window_w) +
        (water_state.probability_ok * base_water_w) +
        (soil_state.probability_ok * base_soil_w) +
        (biotic_state.probability_ok * base_bio_w) +
        (econ_prob * base_econ_w)
    )
    
    # Direct penalty to the suitability score based on the aggregate unknown risk
    unknown_risk_penalty = pen_window + pen_water + pen_soil + pen_bio
    raw_suitability -= (unknown_risk_penalty * 0.45) # Penalize continuous uncertainty factor
    
    # Bound the values securely
    raw_suitability = max(0.01, min(1.0, raw_suitability))
    
    # Critical overrides
    if window_state.severity == "CRITICAL" or water_state.severity == "CRITICAL":
        raw_suitability *= 0.3
        
    suitability_pct = round(raw_suitability * 100.0, 1)
         
    opt_eval = CropOptionEvaluation(
        crop=profile.display_name,
        window=window_state,
        soil=soil_state,
        water=water_state,
        biotic=biotic_state,
        yield_dist=yield_dist,
        econ=econ_outcome,
        overall_rank_score=round(score, 2),
        suitability_percentage=suitability_pct
    )
    options.append(opt_eval)
    
    # Engine H: PED
    # Convert best option into DAG
    # Deterministic sort for run_id stability (Rank first, then Crop ASCII)
    options.sort(key=lambda o: (o.overall_rank_score, o.crop), reverse=True)
    best_opt = options[0]
    rec, dag = generate_execution_plan(best_opt, inputs.plot_id)
    
    # ====================================================================
    # PHASE B+: Per-Zone Suitability Evaluation (Institutional-Grade)
    # Semantic labels, multi-driver narrative, confidence narrative,
    # Risk Concentration Index, Intervention Efficiency Ranking
    # ====================================================================
    plot_suitability = None
    try:
        spatial_zone_stats = getattr(l1_out, "spatial_zone_stats", [])
        if spatial_zone_stats and len(spatial_zone_stats) > 1:
            from services.agribrain.layer7_planning.zone_suitability import (
                ZoneSuitability, compute_zone_confidence, aggregate_plot_suitability,
                generate_semantic_label, build_multi_driver_narrative,
                build_confidence_narrative
            )
            
            zone_results = []
            for zs in spatial_zone_stats:
                z_id = zs.get("zone_id", 0)
                z_key = zs.get("zone_key", f"Zone {z_id}")
                z_label = zs.get("zone_label", "UNKNOWN")
                z_spatial = zs.get("spatial_label", "center")
                z_area = zs.get("area_pct", 0)
                z_means = zs.get("feature_means", {})
                
                # Zone modifiers: shift plot-level probabilities based on zone NDVI deviation
                ndvi_zone = z_means.get("NDVI", 0)
                
                # Modifier: zone with higher NDVI → higher probs; lower NDVI → lower probs
                ndvi_modifier = 1.0 + (ndvi_zone * 5.0)
                ndvi_modifier = max(0.5, min(1.5, ndvi_modifier))
                
                # Per-zone driver scores
                z_window = min(1.0, window_state.probability_ok * ndvi_modifier)
                z_water = min(1.0, water_state.probability_ok * ndvi_modifier)
                z_soil = min(1.0, soil_state.probability_ok * ndvi_modifier)
                z_biotic = min(1.0, biotic_state.probability_ok * ndvi_modifier)
                z_econ = min(1.0, econ_prob * ndvi_modifier)
                
                driver_scores = {
                    "planting_window": round(z_window, 3),
                    "water": round(z_water, 3),
                    "soil": round(z_soil, 3),
                    "biotic": round(z_biotic, 3),
                    "economics": round(z_econ, 3),
                }
                
                # Zone suitability (same weighted formula as plot-level)
                z_suit = (
                    z_window * base_window_w +
                    z_water * base_water_w +
                    z_soil * base_soil_w +
                    z_biotic * base_bio_w +
                    z_econ * base_econ_w
                )
                z_suit = max(0.01, min(1.0, z_suit)) * 100.0
                
                # Zone confidence (uncertainty-aware)
                z_conf = compute_zone_confidence(zs, driver_scores)
                
                # Limiting factors (drivers below 0.6 threshold)
                limiting = []
                for driver_name, driver_val in sorted(driver_scores.items(), key=lambda x: x[1]):
                    if driver_val < 0.6:
                        limiting.append(f"{driver_name} ({driver_val:.0%})")
                
                # Semantic label (human-facing)
                semantic = generate_semantic_label(z_label, z_spatial, z_means, limiting)
                
                # Multi-driver narrative (causal chain)
                narrative = build_multi_driver_narrative(zs, driver_scores, limiting)
                
                # Confidence narrative (per-zone asymmetry)
                conf_narrative = build_confidence_narrative(zs, z_conf)
                
                zone_results.append(ZoneSuitability(
                    zone_id=z_id,
                    zone_key=z_key,
                    zone_label=z_label,
                    spatial_label=z_spatial,
                    semantic_label=semantic,
                    area_pct=z_area,
                    suitability_pct=round(z_suit, 1),
                    confidence=round(z_conf, 3),
                    confidence_narrative=conf_narrative,
                    driver_scores=driver_scores,
                    multi_driver_narrative=narrative,
                    limiting_factors=limiting[:3],
                    evidence_traces=zs.get("notes", []),
                    notes=zs.get("notes", []),
                ))
                
                logger.info(f"[Layer 7] {semantic}: Suit={z_suit:.1f}%, Conf={z_conf:.2f}")
            
            # Aggregate to plot-level (includes RCI + IER computation)
            plot_suitability = aggregate_plot_suitability(zone_results)
            logger.info(f"[Layer 7] Plot: {plot_suitability.suitability_pct}% "
                       f"(Conf: {plot_suitability.confidence:.2f}, "
                       f"RCI: {plot_suitability.risk_concentration_index:.2f}, "
                       f"Weakest: {plot_suitability.weakest_zone_key})")
    except Exception as e:
        logger.warning(f"[Layer 7] Zone suitability failed: {e}")
        import traceback
        traceback.print_exc()
        plot_suitability = None
    
    # Bundle Final Output Layer Result
    l7_output = Layer7Output(
        run_meta=run_meta,
        options=options,
        chosen_plan=rec,
        quality_metrics={
            "global_confidence": str(min([best_opt.window.probability_ok, best_opt.soil.probability_ok, best_opt.water.probability_ok, best_opt.biotic.probability_ok]))
        },
        audit_snapshot={
            "derived_DAG_length": len(dag.tasks),
            "economic_inputs": user_context
         }
    )
    
    # Attach zone suitability if available
    if plot_suitability:
        l7_output.plot_suitability = plot_suitability
    
    # We duck-type the execution plan onto layer result so global merge knows where to pull from
    # Since RunArtifact treats L6/L7 differently
    logger.info(f"[Layer 7] Plan derived: {rec.decision_id} tasks: {len(dag.tasks)}")
    
    # Pack DAG into standard LayerResult container schema
    l7_output.execution_plan = dag
    return l7_output

