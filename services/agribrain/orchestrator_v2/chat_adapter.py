import os
import requests
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

from orchestrator_v2.schema import RunArtifact, GlobalDegradation

from enum import Enum

class SignalDirection(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    STABLE = "STABLE"

@dataclass
class ChatSignal:
    name: str
    value: str
    direction: SignalDirection

@dataclass
class ChatDiagnosis:
    id: str
    prob: float
    conf: float
    type: str # "DIAGNOSIS" or "THREAT"

@dataclass
class ChatAction:
    title: str
    priority: str
    is_allowed: bool
    why: List[str]

@dataclass
class ChatTask:
    task: str
    when: str
    depends_on: List[str]

@dataclass
class ChatCitation:
    source: str
    ref: str

@dataclass
class ChatVisual:
    id: str
    type: str # "TIMESERIES", "BAR", "GAUGE"
    title: str
    data: List[Dict[str, Any]] # [{"x": ..., "y": ...}]
    axis_label: str
    color_hint: str # "BLUE", "RED", "GREEN"

@dataclass
class ChatPayload:
    """
    Simplified payload for LLM consumption.
    """
    run_id: str
    global_quality: Dict[str, Any]
    summary: Dict[str, Any]
    diagnoses: List[ChatDiagnosis]
    actions: List[ChatAction]
    plan: Dict[str, List[ChatTask]]
    citations: List[ChatCitation]
    assistant_mode: str = "MONITORING" # ADVISORY | DATA_GAP | VERIFY_REQUIRED | MONITORING
    assistant_style: str = "TUTOR" # TUTOR | CONCISE | DEBUG
    questions_for_user: List[str] = field(default_factory=list)
    # ARF-v2 fields
    arf: Optional[Dict[str, Any]] = None # Parsed JSON from ARF-v2
    memory: Dict[str, Any] = field(default_factory=dict) # Farmer level, open loops, known context
    ui_hints: Dict[str, Any] = field(default_factory=dict) # Display config
    visuals: List[ChatVisual] = field(default_factory=list) # Rich charts
    data_inventory: Dict[str, str] = field(default_factory=dict) # ✅/⚠️/❌ summary

from orchestrator_v2.intents import Intent

def build_chat_payload(
    artifact: RunArtifact, 
    user_query: Optional[str] = None,
    intent: Intent = Intent.DECISION,
    history: Optional[List[Dict[str, str]]] = None,
) -> ChatPayload:
    """
    Transform the massive RunArtifact into a clean ChatPayload.
    """
    if intent == Intent.DATA_QUERY:
        return _build_data_only_payload(artifact, user_query)
        
    # Determine Assistant Mode based on Intent
    if intent == Intent.DIAGNOSIS:
        assistant_mode = "MONITORING" # Focus on threats
    elif intent == Intent.NUTRIENT:
        assistant_mode = "NUTRIENT"
    elif intent == Intent.EXECUTION_STATUS:
        assistant_mode = "EXECUTION"
    elif intent == Intent.DECISION:
        assistant_mode = "ADVISORY" # Default for Decision
    elif intent == Intent.PLANNING:
        assistant_mode = "PLANNING"
    else:
        assistant_mode = "MONITORING" # Fallback
        
    # 1. Global Quality
    gq = artifact.global_quality
    quality_summary = {
        "reliability": gq.reliability_score,
        "degradation_modes": [m.value for m in gq.modes],
        "alerts": gq.critical_errors + gq.missing_drivers
    }
    
    # 2. Key Signals (Heuristic selection)
    signals = []
    
    # L1: Rain
    if artifact.layer_1 and artifact.layer_1.output:
        ts = getattr(artifact.layer_1.output, "plot_timeseries", [])
        if ts:
            last_14 = ts[-14:]
            rain_sum = sum(r.get("rain", 0.0) for r in last_14)
            signals.append(ChatSignal("Rain (14d)", f"{rain_sum:.1f} mm", SignalDirection.LOW if rain_sum < 10 else SignalDirection.NORMAL))
            
    # L2: NDVI
    if artifact.layer_2 and artifact.layer_2.output:
        pheno = getattr(artifact.layer_2.output, "phenology", None)
        stage = "UNKNOWN"
        if pheno and pheno.stage_by_day:
            stage = pheno.stage_by_day[-1]
            
        curve = getattr(artifact.layer_2.output, "curve", None)
        trend = SignalDirection.STABLE
        if curve and curve.ndvi_fit_d1:
            last_d1 = curve.ndvi_fit_d1[-1]
            if last_d1 > 0.01: trend = SignalDirection.POSITIVE
            elif last_d1 < -0.01: trend = SignalDirection.NEGATIVE
            
        signals.append(ChatSignal("NDVI Trend", trend.value, trend))
        
    summary = {
        "headline": "Analysis Complete", # Placeholder
        "period": f"{artifact.inputs.date_range['start']} to {artifact.inputs.date_range['end']}",
        "stage": stage if 'stage' in locals() else "UNKNOWN",
        "key_signals": [s.__dict__ for s in signals]
    }
    
    # 3. Diagnoses (L3 + L5)
    diags = []
    citations = []
    
    # L3
    if artifact.layer_3 and artifact.layer_3.output:
        l3_diags = getattr(artifact.layer_3.output, "diagnoses", [])
        for d in l3_diags:
            diags.append(ChatDiagnosis(
                id=d.problem_id,
                prob=d.probability,
                conf=d.confidence,
                type="DIAGNOSIS"
            ))
            citations.append(ChatCitation("Layer3.diagnosis", d.problem_id))
            
    # L5
    if artifact.layer_5 and artifact.layer_5.output:
        l5_threats = getattr(artifact.layer_5.output, "threat_states", {})
        for tid, state in l5_threats.items():
            if state.probability > 0.3:
                diags.append(ChatDiagnosis(
                    id=tid,
                    prob=state.probability,
                    conf=state.confidence,
                    type="THREAT"
                ))
                citations.append(ChatCitation("Layer5.threat", tid))

    # 4. Actions & Plan
    actions = []
    tasks = []
    
    # Plan Generation
    # Ensure Plan visibility is gated by L7 recommendation if applicable
    l7_is_allowed = True
    if artifact.layer_7 and artifact.layer_7.output:
        l7_rec = getattr(artifact.layer_7.output, "chosen_plan", None)
        if l7_rec:
            l7_is_allowed = l7_rec.is_allowed

    if artifact.final_execution_plan:
        for t in artifact.final_execution_plan.tasks:
            task_status = "Pending" if l7_is_allowed else "BLOCKED (Review L7 Constraints)"
            tasks.append(ChatTask(
                task=f"{t.type}: {t.instructions}",
                when=task_status,
                depends_on=t.depends_on
            ))
            
    # Actions mostly come from L3 policy or L5 recommnedations
    if artifact.layer_3 and artifact.layer_3.output:
        l3_rec = getattr(artifact.layer_3.output, "recommendations", [])
        for r in l3_rec:
            actions.append(ChatAction(
                title=f"{r.action_type}: {r.action_id}",
                priority=f"P-Score {r.priority_score:.1f}",
                is_allowed=r.is_allowed,
                why=r.blocked_reason if not r.is_allowed else []
            ))
            
    # L5 actions
    if artifact.layer_5 and artifact.layer_5.output:
         l5_rec = getattr(artifact.layer_5.output, "recommended_actions", [])
         for r in l5_rec:
             actions.append(ChatAction(
                title=f"{r.action_type}: {r.action_id}",
                priority=f"Impact {r.expected_impact:.1f}",
                is_allowed=r.is_allowed,
                why=r.blocked_reason if not r.is_allowed else []
            ))
            
    # L7 Actions (Season Planning)
    print("DEBUG L7_MAP type:", type(artifact.layer_7.output if artifact.layer_7 else None))
    print("DEBUG L7_MAP keys/attrs:", dir(artifact.layer_7.output) if artifact.layer_7 and artifact.layer_7.output else "N/A")
    if artifact.layer_7 and artifact.layer_7.output:
         l7_rec = getattr(artifact.layer_7.output, "chosen_plan", None)
         l7_options = getattr(artifact.layer_7.output, "options", [])
         if l7_rec:
             why_reasons = []
             if not l7_rec.is_allowed:
                 if l7_rec.blocked_reason:
                     why_reasons.append(l7_rec.blocked_reason)
                 if l7_rec.risk_if_wrong:
                     why_reasons.append(f"Risk if ignored: {l7_rec.risk_if_wrong}")
                     
             actions.append(ChatAction(
                title=f"{l7_rec.decision_id}: {l7_rec.crop}",
                priority=f"Planning Decision",
                is_allowed=l7_rec.is_allowed,
                why=why_reasons
             ))
             
             # Extract cognitive planning metrics
             chosen_opt = next((o for o in l7_options if o.crop == l7_rec.crop), None)
             if chosen_opt:
                 
                 # 4b. Extract Driver Coverage Matrix (Traces that applied penalties or bonuses)
                 driver_matrix = []
                 for state in [chosen_opt.window, chosen_opt.soil, getattr(chosen_opt, 'water', None), getattr(chosen_opt, 'biotic', None)]:
                     if state and getattr(state, "evidence_trace", None):
                         for trace in state.evidence_trace:
                             if abs(trace.logit_delta) > 0.1: # Only include meaningful driver shifts
                                 source_info = f" [{','.join(trace.source_refs)}]" if getattr(trace, "source_refs", None) else ""
                                 driver_matrix.append(f"{trace.driver.value if hasattr(trace.driver, 'value') else str(trace.driver)}: {trace.condition} (Weight: {trace.weight}){source_info}")
                 
                 summary["planning_context"] = {
                     "crop": chosen_opt.crop,
                     "overall_score": chosen_opt.overall_rank_score,
                     "window_prob": chosen_opt.window.probability_ok,
                     "water_prob": getattr(chosen_opt.water, "probability_ok", 0.0),
                     "biotic_prob": getattr(chosen_opt.biotic, "probability_ok", 0.0),
                     "expected_yield": chosen_opt.yield_dist.mean,
                     "downside_risk_p10": chosen_opt.yield_dist.p10,
                     "expected_profit": chosen_opt.econ.expected_profit,
                     "break_even_yield": chosen_opt.econ.break_even_yield,
                     "suitability_percentage": getattr(chosen_opt, "suitability_percentage", 0.0),
                     "driver_matrix": driver_matrix
                 }

         # Phase D+: Extract Zone Suitability Breakdown from L7 (Institutional-Grade)
         plot_suit = getattr(artifact.layer_7.output, "plot_suitability", None)
         if plot_suit and hasattr(plot_suit, "zone_breakdown") and plot_suit.zone_breakdown:
             zone_cards = []
             for zs in plot_suit.zone_breakdown:
                 zone_cards.append({
                     "zone_key": zs.zone_key,
                     "semantic_label": getattr(zs, "semantic_label", zs.zone_key),
                     "spatial_label": zs.spatial_label,
                     "area_pct": zs.area_pct,
                     "suitability_pct": zs.suitability_pct,
                     "confidence": zs.confidence,
                     "confidence_narrative": getattr(zs, "confidence_narrative", ""),
                     "limiting_factors": zs.limiting_factors,
                     "driver_scores": zs.driver_scores,
                     "multi_driver_narrative": getattr(zs, "multi_driver_narrative", ""),
                     "intervention_delta": getattr(zs, "intervention_delta", 0),
                     "notes": zs.notes,
                 })
             summary["zone_suitability"] = {
                 "plot_suitability": plot_suit.suitability_pct,
                 "plot_confidence": plot_suit.confidence,
                 "weakest_zone": plot_suit.weakest_zone_key,
                 "strongest_zone": plot_suit.strongest_zone_key,
                 "risk_concentration_index": getattr(plot_suit, "risk_concentration_index", 0),
                 "risk_distribution": getattr(plot_suit, "risk_distribution", ""),
                 "zone_cards": zone_cards,
             }

    # 5. Assistant Mode Logic & Thresholding
    
    # Threshold Gating: Only surface certain stressors
    high_impact_diags = [d for d in diags if d.prob > 0.6 and d.conf > 0.6]
    
    # In PLANNING mode, we suppress L3/L5 diagnostics from dominating unless Extremely critical
    if assistant_mode == "PLANNING":
        high_impact_diags = [d for d in high_impact_diags if d.prob > 0.8 and d.conf > 0.8]
        
    low_impact_diags = [d for d in diags if d not in high_impact_diags]
    
    # Refine Assistant Mode (Intent vs Reality)
    mode = assistant_mode
    
    # Degradation Overrides
    reliability = quality_summary["reliability"]
    has_datagap = "NO_SAR" in quality_summary["degradation_modes"] or "PARTIAL_DATA" in quality_summary["degradation_modes"]
    has_intervene = any(a.title.startswith("INTERVENE") for a in actions)
    has_verify = any(a.title.startswith("VERIFY") for a in actions)
    
    # DATA_GAP should NOT be primary headline unless reliability is critical
    if reliability < 0.6 and has_datagap and mode not in ["DATA_ONLY", "PLANNING"]:
        mode = "DATA_GAP"
    elif has_intervene and mode == "MONITORING":
        mode = "ADVISORY"
    elif has_verify and mode == "MONITORING":
        mode = "VERIFY_REQUIRED"
    
    # If we have NO high impact diags and NO forced mode, keep it MONITORING even if low diags exist
    
    # 6. Memory Integration & ARF-v2
    from orchestrator_v2.chat_memory import load_memory, save_memory
    
    # IDs
    plot_id = artifact.inputs.plot_id
    conversation_id = getattr(artifact.meta, "conversation_id", "local_dev_session") 
    
    # Load Memory
    chat_memory = load_memory(plot_id)
    
    memory_context = {
        "experience_level": chat_memory.experience_level,
        "known_context": chat_memory.known_context,
        "open_loops": chat_memory.open_loops
    }
    
    # Generate ARF-v2 Response
    arf_json = _generate_arf_v2(
        summary=summary,
        diags=high_impact_diags, 
        actions=actions,
        tasks=tasks,
        memory=chat_memory,
        user_query=user_query,
        mode=mode,
        quality=quality_summary,
        history=history
    )
    
    # Add low-impact to limitations if ARF succeeded
    if "error" not in arf_json:
        if low_impact_diags:
            limitations = arf_json.setdefault("limitations", [])
            limitations.append(
                f"Low-probability indicators ignored: {', '.join(d.id for d in low_impact_diags)}"
            )
        if has_datagap and mode != "DATA_GAP":
            arf_json.setdefault("limitations", []).append("Limited SAR coverage; assessing via optical/weather proxies.")
            
        # Extract UI Hints
        ui_hints = {
             "show_reliability_banner": reliability < 0.6,
             "show_blocked_banner": any(not a.is_allowed for a in actions),
             "card_ordering": [c.get("type", "UNKNOWN") for c in arf_json.get("reasoning_cards", [])]
        }
            
        # Update Memory
        if user_query:
            chat_memory.last_questions.append(user_query)
            if len(chat_memory.last_questions) > 10:
                chat_memory.last_questions.pop(0)
        
        if arf_json.get("followups"):
            chat_memory.asked_followups.extend([f.get("question") for f in arf_json["followups"] if f.get("question")])
            
        mem_updates = arf_json.get("internal_memory_updates")
        if mem_updates:
            if mem_updates.get("experience_level_upgrade"):
                chat_memory.experience_level = mem_updates["experience_level_upgrade"]
            if mem_updates.get("new_known_facts"):
                chat_memory.known_context.update(mem_updates["new_known_facts"])
            if mem_updates.get("closed_loops"):
                for cl in mem_updates["closed_loops"]:
                    if cl in chat_memory.open_loops:
                        chat_memory.open_loops.remove(cl)
            
        save_memory(plot_id, chat_memory)
    
    else:
        # Fallback if ARF failed
        ui_hints = {}
        summary["explanation"] = f"Analysis complete. (System Note: {arf_json['error']})"
        summary["headline"] = "System Notification"

    # 7. Feature Snapshot (Visual Debugging)
    snapshot = {}
    if artifact.layer_1 and artifact.layer_1.output:
        ts = getattr(artifact.layer_1.output, "plot_timeseries", [])
        static_props = getattr(artifact.layer_1.output, "static", {})
        
        if ts:
             last = ts[-1]
             snapshot["rain_14d"] = summary.get("key_signals", [{}])[0].get("value", "N/A")
             snapshot["soil_moisture"] = last.get("soil_moisture_proxy", "N/A")
             snapshot["sar_vv"] = last.get("vv_db", last.get("vv", "N/A"))
             
        if static_props:
             snapshot["soil_texture"] = static_props.get("texture_class", "UNKNOWN")
             snapshot["soil_clay"] = f"{static_props.get('soil_clay_mean', 'N/A')}%"
             snapshot["soil_sand"] = f"{static_props.get('soil_sand_mean', 'N/A')}%"
             snapshot["soil_ph"] = static_props.get("soil_ph_mean", "N/A")
             snapshot["soil_soc"] = static_props.get("soil_org_c_mean", "N/A")
             
        # Extract 7-Day Forecast Extremes
        forecast_7d = getattr(artifact.layer_1.output, "forecast_7d", [])
        if forecast_7d:
             min_temps = [f.get("temp_min", 99) for f in forecast_7d if f.get("temp_min") is not None]
             max_winds = [f.get("wind_speed", 0) for f in forecast_7d if f.get("wind_speed") is not None]
             max_pops = [f.get("pop", 0) for f in forecast_7d if f.get("pop") is not None]
             
             snapshot["forecast_min_temp_7d"] = f"{min(min_temps)}°C" if min_temps else "N/A"
             snapshot["forecast_max_wind_7d"] = f"{max(max_winds)} km/h" if max_winds else "N/A"
             snapshot["forecast_max_rain_probability"] = f"{max(max_pops)*100:.0f}%" if max_pops else "N/A"

    summary["feature_snapshot"] = snapshot
    
    # 7b. Management Zone Context (Phase 12: Spatial Heterogeneity)
    zone_context_str = ""
    if artifact.layer_1 and artifact.layer_1.output:
        zones = getattr(artifact.layer_1.output, "zones", {})
        if zones and len(zones) > 1:
            zone_lines = []
            for z_id, z_data in zones.items():
                label = z_data.get("label", z_id)
                area = z_data.get("area_pct", 0)
                spatial = z_data.get("spatial_label", "unknown location")
                sig = z_data.get("signature", {})
                ndvi_med = sig.get("ndvi_median", "N/A")
                zone_lines.append(f"    - {z_id} ({spatial}, {area}% of field): {label} | NDVI median: {ndvi_med}")
            zone_context_str = "\n".join(zone_lines)
            summary["management_zones"] = {
                z_id: {
                    "label": z_data.get("label"),
                    "area_pct": z_data.get("area_pct"),
                    "spatial_label": z_data.get("spatial_label"),
                    "ndvi_median": z_data.get("signature", {}).get("ndvi_median"),
                    "geometry": z_data.get("geometry"),  # GeoJSON Feature (data-driven zone shape)
                } for z_id, z_data in zones.items()
            }
    summary["_zone_context_str"] = zone_context_str

    # 8. Questions Logic (Context Retrieval)
    questions = arf_json.get("next_questions", []) if "error" not in arf_json else []
    
    # Fallback to rule-based if LLM didn't return questions
    if not questions:
        missing_drivers = gq.missing_drivers
        if "Layer3.SAR_VV" in missing_drivers or "NO_SAR" in quality_summary["degradation_modes"]:
            questions.append("Sentinel-1 data is missing. Do you have recent drone imagery or photos?")
        # ... other rules ...
        # Add Context Question Strategy
        ctx_q = _select_context_question(artifact.inputs, artifact.global_quality, mode=mode)
        if ctx_q: questions.append(ctx_q)

    # 9. Visuals Generation
    visuals = []
    if artifact.layer_1 and artifact.layer_1.output:
        ts = getattr(artifact.layer_1.output, "plot_timeseries", [])
        if ts:
            # Rain Chart
            rain_data = [{"x": r.get("date"), "y": float(r.get("rain", 0.0) or 0.0)} for r in ts]
            visuals.append(ChatVisual(
                id="rain_daily",
                type="BAR",
                title="Daily Rainfall (mm)",
                data=rain_data[-30:], # Last 30 days
                axis_label="mm",
                color_hint="BLUE"
            ))
            
            # NDVI Chart (if data exists)
            ndvi_data = [{"x": r.get("date"), "y": float(r.get("ndvi", 0.0) or 0.0)} for r in ts if r.get("ndvi") is not None]
            if ndvi_data:
                visuals.append(ChatVisual(
                    id="ndvi_trend",
                    type="TIMESERIES",
                    title="Vegetation Health (NDVI)",
                    data=ndvi_data[-60:], # Last 60 days context
                    axis_label="NDVI",
                    color_hint="GREEN"
                ))

    # 10. Data Inventory 
    data_inv = {
        "SAR": "❌ Missing",
        "Optical": "❌ Missing", 
        "Historical Weather": "❌ Missing",
        "Forecast": "❌ Missing",
        "Soil Data": "❌ Missing"
    }
    
    if artifact.layer_1 and artifact.layer_1.output:
        l1o = artifact.layer_1.output
        if any(r.get("vv_db") is not None for r in getattr(l1o, "plot_timeseries", [])): data_inv["SAR"] = "✅ Present"
        if any(r.get("ndvi") is not None for r in getattr(l1o, "plot_timeseries", [])): data_inv["Optical"] = "✅ Present"
        if any(r.get("rain") is not None for r in getattr(l1o, "plot_timeseries", [])): data_inv["Historical Weather"] = "✅ Present"
        if getattr(l1o, "forecast_7d", []): data_inv["Forecast"] = "✅ Present"
        if getattr(l1o, "static", {}).get("soil_clay_mean"): data_inv["Soil Data"] = "✅ Present"

    return ChatPayload(
        run_id=artifact.meta.orchestrator_run_id,
        global_quality=quality_summary,
        summary=summary,
        diagnoses=diags,
        actions=actions,
        plan={"tasks": tasks},
        citations=citations,
        assistant_mode=mode,
        assistant_style="TUTOR",
        questions_for_user=questions,
        arf=arf_json,
        memory=memory_context,
        ui_hints=ui_hints,
        visuals=visuals,
        data_inventory=data_inv
    )

def _generate_arf_v2(
    summary: Dict, 
    diags: List[ChatDiagnosis], 
    actions: List[ChatAction], 
    tasks: List[ChatTask],
    memory: Any, # ChatMemory
    user_query: Optional[str] = None,
    mode: str = "MONITORING",
    quality: Dict[str, Any] = None,
    history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Calls OpenRouter to generate ARF-v2 strict JSON response.
    """

    
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return {"error": "LLM Key missing"}

    # Format Diagnoses
    diag_str = [f"{d.id} (P:{d.prob:.2f}, C:{d.conf:.2f})" for d in diags]
    
    # Format Actions
    action_str = []
    for a in actions:
        status = "ALLOWED" if a.is_allowed else f"BLOCKED: {a.why}"
        action_str.append(f"{a.title} Priority:{a.priority} Status:{status}")

    # Format Tasks
    task_str = []
    for t in tasks:
        task_str.append(f"Task: {t.task} | Status: {t.when} | Depends on: {t.depends_on}")

    # Build Planning Context String
    planning_str = ""
    if "planning_context" in summary:
        p_ctx = summary["planning_context"]
        planning_str = f"""
    [PLANNING FEASIBILITY & ECONOMICS] (PRIMARY FOCUS)
    - Target Crop: {p_ctx.get('crop')}
    - True Feasibility Index: {p_ctx.get('suitability_percentage', 0):.1f}% (Calculated via 5-factor weighted ensemble)
    - Window Probability: {p_ctx.get('window_prob', 0):.2f}
    - Water Probability: {p_ctx.get('water_prob', 0):.2f}
    - Biotic Probability: {p_ctx.get('biotic_prob', 0):.2f}
    - Yield Potential (Mean): {p_ctx.get('expected_yield', 0):.1f} t/ha
    - Yield Risk (p10): {p_ctx.get('downside_risk_p10', 0):.1f} t/ha
    - Break-Even Yield: {p_ctx.get('break_even_yield', 0):.1f} t/ha
    - Expected Profit: ${p_ctx.get('expected_profit', 0):.1f}
    
    [L7 DRIVER COVERAGE MATRIX] (WHY probabilities changed)
    {chr(10).join(f'    - {d}' for d in p_ctx.get('driver_matrix', []))}
        """

    # Build Zone Context for LLM (Institutional-Grade)
    zone_ctx = summary.get('_zone_context_str', '')
    zone_suit = summary.get('zone_suitability', {})
    zone_block = ""
    if zone_ctx or zone_suit:
        zone_lines = []
        zone_lines.append("    [MANAGEMENT ZONES] (WITHIN-FIELD SPATIAL VARIABILITY — CRITICAL)")
        zone_lines.append("    The field has been segmented into management zones. You MUST use SEMANTIC LABELS (not Zone A/B/C).")
        
        if zone_ctx:
            zone_lines.append(zone_ctx)
        
        if zone_suit:
            zone_lines.append(f"    Plot Suitability: {zone_suit.get('plot_suitability', 'N/A')}% (Conf: {zone_suit.get('plot_confidence', 'N/A')})")
            zone_lines.append(f"    Weakest: {zone_suit.get('weakest_zone', 'N/A')} | Strongest: {zone_suit.get('strongest_zone', 'N/A')}")
            rci = zone_suit.get('risk_concentration_index', 0)
            rd = zone_suit.get('risk_distribution', '')
            if rci > 0:
                zone_lines.append(f"    Risk Concentration Index: {rci} — {rd}")
            
            for zc in zone_suit.get('zone_cards', []):
                sem = zc.get('semantic_label', zc['zone_key'])
                lf = ', '.join(zc.get('limiting_factors', [])) or 'None'
                mdn = zc.get('multi_driver_narrative', '')
                cn = zc.get('confidence_narrative', '')
                delta = zc.get('intervention_delta', 0)
                zone_lines.append(f"    - {sem} ({zc['spatial_label']}, {zc['area_pct']}%): Suit={zc['suitability_pct']}%, Limiting: [{lf}]")
                if mdn:
                    zone_lines.append(f"      Drivers: {mdn}")
                if cn:
                    zone_lines.append(f"      {cn}")
                if delta > 0:
                    zone_lines.append(f"      Intervention Impact: Fixing this zone raises plot suitability by +{delta:.1f}%")
        
        zone_block = "\n".join(zone_lines)
    
    context_str = f"""
    {planning_str}
    {zone_block}
    
    [FIELD CONTEXT] (SECONDARY CONSTRAINTS)
    - Stage: {summary.get('stage')}
    - Signals: {json.dumps(summary.get('key_signals', []))}
    - Hyper-Local Variables (MUST CITE THESE NUMBERS IN REASONING): {json.dumps(summary.get('feature_snapshot', {}))}
    - Diagnoses (High Cert): {diag_str}
    - Proposed Actions: {action_str}
    - Execution Plan Tasks: {task_str}
    - Quality Issues: {quality.get('degradation_modes', []) if quality else []}
    """
    
    memory_str = f"""
    [FARMER PROFILE]
    - Experience Level: {memory.experience_level}
    - Known Field Traits: {json.dumps(memory.known_context)}
    - Open Loops (Pending tasks we asked them to do): {memory.open_loops}
    - Recent Follow-ups Asked: {memory.asked_followups[-5:] if memory.asked_followups else []}
    """

    system_prompt = f"""
    You are AgriBrain, an expert agronomist + teacher + safety-first AI.
    
    INPUT CONTEXT:
    {context_str}
    {memory_str}
    
    CRITICAL RULES:
    1. Respond ONLY in valid JSON matching the schema below. No markdown outside the JSON.
    2. Adapt teaching depth to Farmer Experience Level ({memory.experience_level}).
    3. DECOUPLE SUITABILITY FROM CONFIDENCE: You must separate pure agronomic feasibility from epistemic certainty.
       - "Suitability Score" is the sheer mathematical probability of success based on knowns.
       - "Confidence Badge" represents how much data is missing.
       - If Quality Issues include NO_SAR or PARTIAL_DATA, your Confidence is LOW or MED. But DO NOT say "Not advisable due to data gaps".
       - DECISION RULES:
         a) Suitability > 70% & Confidence is HIGH/MED -> "Proceed"
         b) Suitability 50-70% OR (High Suitability but LOW Confidence) -> "Proceed with verification" (Advise caution, list verifications as prerequisites).
         c) Suitability < 50% -> "Delay" 
       - NEVER block a decision purely because of missing data if the calculated Suitability remains > 50%. Instead, recommend proceeding *after* verifying the missing variable.
    4. Provide contextual follow-up questions but DO NOT repeat 'Recent Follow-ups Asked'.
    5. ELITE AGRONOMIST TONE: Act as a senior, highly-paid agronomic consultant. You MUST use conversational, advisory phrasing (e.g., "Before planting, I recommend confirming soil moisture..."). YOU ARE STRICTLY FORBIDDEN from using robotic, capitalized prefixes like "VERIFY: " or "MONITOR: " in your recommendation titles. Make them sound human.
    6. CAUSAL FORECAST NARRATIVE: You MUST explicitly link the *future* 7-day forecast variables (temperature, rain, frost) found in the L7 DRIVER COVERAGE MATRIX to your final feasibility score. Do not just list static facts. State *why* the score shifted (e.g., "The forecasted 30mm rain degrades seedbed trafficability and pushes feasibility down to 65%").
    7. ECONOMIC SENSITIVITY: Explicitly incorporate economic variance into your narrative. You MUST clearly state how data gaps or harsh forecasts impact the downside risk (p10) or break-even margin (e.g., "Under current water quota constraints, expected yield variance widens. Downside risk increases if irrigation efficiency falls.").
    8. AVOID REDUNDANT DATA REQUESTS: Since you are already receiving the 7-day forecast evaluations (Rain risk, Frost risk) in the L7 MATRIX, DO NOT recommend that the user "check the weather forecast". You already did that.
    9. HYPER-LOCAL GEOGRAPHIC SPECIFICITY: You MUST cite exact numeric values from the "Hyper-Local Variables" block in your reasoning cards.
       - SOIL: If soil_clay, soil_sand, or soil_silt values are present, you MUST write them as evidence (e.g., "Clay: 34%, Sand: 48% (SoilGrids 250m)"). Do not say "loam" without backing it up with numbers.
       - FORECAST: If forecast_min_temp_7d, forecast_max_wind_7d, or forecast_max_rain_probability are present, you MUST reference them (e.g., "Next 7 nights stay above 8°C — frost is unlikely", "Max wind exposure reaches 35 km/h — consider windbreak for young seedlings").
       - If these values are "N/A", acknowledge the missing data source explicitly and state impact on confidence.
    10. SPATIAL AWARENESS (HETEROGENEITY): If the MANAGEMENT ZONES block is present, you MUST speak in spatial terms. NEVER say "the field is stressed" — say "the south-east corner (Zone C, 31%) is showing severe lag, while Zone A remains vigorous". Call out patchiness and recommend targeted interventions rather than blanket applications.
    11. ZONE-SPECIFIC REASONING: When zone suitability data is available for each zone, EVERY reasoning card MUST reference the specific zone it applies to. Example: "Zone C (south-west, 31%) has a suitability of 45% vs Zone A's 72% — the 27-point gap is driven by lower water probability (0.52 vs 0.78)."
    12. ZONE CARDS IN RECOMMENDATIONS: Show worst 1 zone and best 1 zone in detail. Collapse others into a summary sentence. For the worst zone, always include: (a) its spatial label, (b) the primary limiting factor, (c) a targeted action for that specific zone, (d) confidence level.
    13. WEAKEST ZONE PROTOCOL: If the user asks "which part is weakest" or "where is the problem", you MUST respond with: zone identifier, spatial descriptor, primary limiting driver with numeric evidence, targeted zone-specific action, and confidence statement tied to data coverage in that zone. Example: "Zone C (south-west, 31% of your field) is the weakest right now — suitability is only 45% (confidence: LOW). The bottleneck is water availability (0.52 probability) compounded by sparse SAR coverage. I'd recommend checking soil moisture at 10cm depth specifically in that zone first."
    
    RESPONSE JSON SCHEMA:
    {{
        "headline": "1 sentence title summarizing field status",
        "direct_answer": "Direct answer to user's specific question",
        "suitability_score": "Pure agronomic feasibility percentage e.g., '65%'",
        "confidence_badge": "HIGH" | "MED" | "LOW",
        "confidence_reason": "Why the confidence badge is what it is (e.g., 'Missing SAR data')",
        "what_it_means": "Agronomic interpretation of the situation",
        "reasoning_cards": [
            {{
                "type": "EVIDENCE" | "THREAT",
                "claim": "Summary of finding (e.g., High fungal risk)",
                "evidence": "What data supports this",
                "uncertainty": "What could be wrong/missing"
            }}
        ],
        "recommendations": [
            {{
                "type": "VERIFY" | "MONITOR" | "INTERVENE",
                "title": "Natural human sentence (e.g., 'Confirm soil moisture at 10cm depth')",
                "is_allowed": true/false (must match INPUT CONTEXT),
                "blocked_reasons": ["if not allowed, why"],
                "why_it_matters": "Benefit of doing this",
                "how_to_do_it_steps": ["step 1", "step 2"],
                "risk_if_wrong": "LOW" | "MED" | "HIGH"
            }}
        ],
        "learning": {{
            "level": "BEGINNER" | "INTERMEDIATE" | "EXPERT",
            "micro_lesson": "A 3-8 line educational snippet tailored to the user's level about the core concepts involved today.",
            "definitions": {{"Term": "Meaning"}}
        }},
        "followups": [
            {{
                "question": "Ask a relevant question to clarify context or progress. Exclude already known context.",
                "why": "Why are you asking this?"
            }}
        ],
        "internal_memory_updates": {{
            "experience_level_upgrade": "Optional string (INTERMEDIATE or EXPERT) if they demonstrate higher knowledge, else null",
            "new_known_facts": {{"FactKey": "FactValue learned in this turn"}},
            "closed_loops": ["IDs or names of pending tasks the user just confirmed they did"]
        }}
    }}
    """
    
    user_prompt = user_query if user_query else "Acknowledge the context and ask the user what they would like to know about their field."
    
    messages = [{"role": "system", "content": system_prompt}]
    
    if history:
        for msg in history[-8:]:  # Provide last 8 turns of context
            r = msg.get("role", "user")
            # Map 'model' to 'assistant' for OpenRouter compliance
            if r == "model":
                r = "assistant"
            # Ensure text isn't massive and strip ARF logic
            c = msg.get("content", "")[:2000]
            if c.strip():
                messages.append({"role": r, "content": c})
                
    messages.append({"role": "user", "content": user_prompt})

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://agriwise.app", 
                "X-Title": "AgriWise"
            },
            json={
                "model": "qwen/qwen-2.5-72b-instruct", 
                "messages": messages,
                "temperature": 0.4, # Lower temperature for stable JSON structure
                "max_tokens": 1500, # Large structure needs tokens
                "response_format": {"type": "json_object"}
            },
            timeout=20
        )
        
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"].strip()
            # Clean possible markdown block wrappers
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
                
            raw_json = json.loads(content)
            
            # --- ARF Sanitizer ---
            # 1. Fix strings in recommendations
            recs = raw_json.get("recommendations", [])
            if isinstance(recs, list):
                sanitized_recs = []
                for r in recs:
                    if isinstance(r, str):
                        sanitized_recs.append({
                            "type": "MONITOR",
                            "title": r,
                            "is_allowed": True,
                            "blocked_reasons": [],
                            "why_it_matters": "",
                            "how_to_do_it_steps": [],
                            "risk_if_wrong": "LOW"
                        })
                    elif isinstance(r, dict):
                        sanitized_recs.append(r)
                raw_json["recommendations"] = sanitized_recs
                
            # 2. Fix strings in followups
            fups = raw_json.get("followups", [])
            if isinstance(fups, list):
                sanitized_fups = []
                for f in fups:
                    if isinstance(f, str):
                        sanitized_fups.append({"question": f, "why": "Clarifying context"})
                    elif isinstance(f, dict):
                        sanitized_fups.append(f)
                raw_json["followups"] = sanitized_fups

            # 3. Fix strings in reasoning_cards
            cards = raw_json.get("reasoning_cards", [])
            if isinstance(cards, list):
                sanitized_cards = []
                for c in cards:
                    if isinstance(c, str):
                        sanitized_cards.append({
                            "type": "EVIDENCE",
                            "claim": c,
                            "evidence": "",
                            "uncertainty": ""
                        })
                    elif isinstance(c, dict):
                        sanitized_cards.append(c)
                raw_json["reasoning_cards"] = sanitized_cards
                
            # 4. Fix missing or bad learning block
            learning = raw_json.get("learning", {})
            if isinstance(learning, str):
                raw_json["learning"] = {
                    "level": "INTERMEDIATE",
                    "micro_lesson": learning,
                    "definitions": {}
                }
            elif not learning or not isinstance(learning, dict):
                raw_json["learning"] = {
                    "level": "INTERMEDIATE",
                    "micro_lesson": "No learning module provided.",
                    "definitions": {}
                }
            
            # STRIKE: Strict Pydantic Validation
            from orchestrator_v2.arf_schema import ARFResponse
            try:
                validated_arf = ARFResponse(**raw_json)
                return validated_arf.dict() # Return valid dict representing ARF
            except Exception as e:
                print(f"DEBUG: LLM schema validation failed even after sanitization: {e}")
                # Safe Fallback Payload
                return {
                    "headline": summary.get("headline", "Analysis available"),
                    "direct_answer": summary.get("explanation", "I analyzed the field, but the response format was incomplete."),
                    "suitability_score": "N/A",
                    "confidence_badge": "MED",
                    "confidence_reason": "Structured explanation formatting failed",
                    "what_it_means": "Core pipeline ran, but the natural-language formatter needs fallback shaping.",
                    "reasoning_cards": [],
                    "recommendations": [],
                    "learning": {
                        "level": "INTERMEDIATE",
                        "micro_lesson": "You can still use the map and layer diagnostics while the explanation formatter is repaired.",
                        "definitions": {}
                    },
                    "followups": [],
                    "internal_memory_updates": None
                }
        else:
            return {"error": f"AI unavailable: {resp.status_code}"}
            
    except Exception as e:
        print(f"DEBUG: LLM Error: {e}")
        return {"error": str(e)}

def _extract_headline(text: str) -> str:
    # First sentence or first 50 chars
    # If text is an error message or "Thinking...", provide a safe default based on signals? 
    # But we don't have signals here easily.
    # Just clean up the text.
    if "AI unavailable" in text or "AI error" in text:
        return "Field Status Update (Offline Mode)"
        
    if "." in text:
        return text.split(".")[0] + "."
    return text[:60] + "..."

def _build_data_only_payload(artifact: RunArtifact, user_query: Optional[str] = None) -> ChatPayload:
    """
    Deterministic payload for pure data queries. No diagnoses, no actions.
    Query-aware: detects whether user asks about weather or soil and surfaces the right data.
    """
    signals = []
    
    summary = {
        "headline": "Data Retrieval Complete",
        "period": f"{artifact.inputs.date_range['start']} to {artifact.inputs.date_range['end']}",
        "stage": "OBSERVATIONAL",
        "key_signals": []
    }
    
    q = (user_query or "").lower()
    is_soil_query = any(k in q for k in ["soil", "moisture", "clay", "sand", "silt", "ph", "organic", "texture", "nitrogen", "carbon"])
    is_weather_query = any(k in q for k in ["rain", "raining", "temp", "temperature", "weather", "precipitation", "wind", "frost", "humidity"])
    
    # Default to weather if neither detected
    if not is_soil_query and not is_weather_query:
        is_weather_query = True

    # ---- WEATHER SIGNALS ----
    rain_val = 0.0
    days_count = 0
    if artifact.layer_1 and artifact.layer_1.output:
        ts = getattr(artifact.layer_1.output, "plot_timeseries", [])
        if ts:
            rain_val = sum(float(r.get("rain", 0.0) or 0.0) for r in ts)
            days_count = sum(1 for r in ts if float(r.get("rain", 0.0) or 0.0) > 0.1)
            
            if is_weather_query:
                signals.append(ChatSignal("Rainfall (Total)", f"{rain_val:.1f} mm", SignalDirection.NORMAL))
                signals.append(ChatSignal("Days with Rain", str(days_count), SignalDirection.NORMAL))
                
                # Temperature
                tmeans = [float(r.get("tmean", 0)) for r in ts if r.get("tmean") is not None]
                if tmeans:
                    signals.append(ChatSignal("Avg Temperature", f"{sum(tmeans)/len(tmeans):.1f} °C", SignalDirection.NORMAL))
            
            # NDVI always useful
            ndvis = [float(r.get("ndvi")) for r in ts if r.get("ndvi") is not None]
            if ndvis:
                signals.append(ChatSignal("Avg NDVI", f"{sum(ndvis)/len(ndvis):.2f}", SignalDirection.NORMAL))

    # ---- SOIL SIGNALS (SoilGrids + Open-Meteo) ----
    soil_static = {}
    soil_moisture_data = {}
    
    if is_soil_query and artifact.layer_1 and artifact.layer_1.output:
        # 1. SoilGrids static data (already in tensor.static from L1)
        soil_static = getattr(artifact.layer_1.output, "static", {}) or {}
        
        if soil_static:
            clay = soil_static.get("soil_clay_mean")
            sand = soil_static.get("soil_sand_mean")
            silt = soil_static.get("soil_silt_mean")
            ph = soil_static.get("soil_ph_mean")
            soc = soil_static.get("soil_org_c_mean")
            texture = soil_static.get("texture_class", "unknown")
            
            if clay is not None:
                signals.append(ChatSignal("Clay Content", f"{clay}%", SignalDirection.NORMAL))
            if sand is not None:
                signals.append(ChatSignal("Sand Content", f"{sand}%", SignalDirection.NORMAL))
            if silt is not None:
                signals.append(ChatSignal("Silt Content", f"{silt}%", SignalDirection.NORMAL))
            if ph is not None:
                signals.append(ChatSignal("Soil pH", f"{ph}", SignalDirection.NORMAL))
            if soc is not None:
                signals.append(ChatSignal("Organic Carbon", f"{soc} g/kg", SignalDirection.NORMAL))
            if texture and texture != "unknown":
                signals.append(ChatSignal("Texture Class", texture, SignalDirection.NORMAL))
        
        # 2. Real-time soil moisture from Open-Meteo (fetch live)
        try:
            lat = float(artifact.inputs.operational_context.get("lat", 0))
            lng = float(artifact.inputs.operational_context.get("lng", 0))
            if lat != 0 and lng != 0:
                from eo.sentinel import fetch_soil_moisture_layers
                sm = fetch_soil_moisture_layers(lat, lng)
                if sm:
                    soil_moisture_data = sm
                    m = sm.get("moisture", {})
                    if m.get("0_7cm") is not None:
                        signals.append(ChatSignal("Moisture 0-7cm", f"{m['0_7cm']:.3f} m³/m³", SignalDirection.NORMAL))
                    if m.get("7_28cm") is not None:
                        signals.append(ChatSignal("Moisture 7-28cm", f"{m['7_28cm']:.3f} m³/m³", SignalDirection.NORMAL))
                    if m.get("28_100cm") is not None:
                        signals.append(ChatSignal("Moisture 28-100cm", f"{m['28_100cm']:.3f} m³/m³", SignalDirection.NORMAL))
                    
                    t = sm.get("temperature", {})
                    if t.get("0_7cm") is not None:
                        signals.append(ChatSignal("Soil Temp 0-7cm", f"{t['0_7cm']:.1f} °C", SignalDirection.NORMAL))
        except Exception as e:
            print(f"⚠️ [Chat] Soil moisture fetch failed: {e}")

    summary["key_signals"] = [s.__dict__ for s in signals]
    
    # ---- BUILD NARRATIVE ----
    period_days = 14
    try:
        start = datetime.strptime(artifact.inputs.date_range['start'], "%Y-%m-%d")
        end = datetime.strptime(artifact.inputs.date_range['end'], "%Y-%m-%d")
        period_days = (end - start).days + 1
    except:
        pass

    if is_soil_query:
        # Soil-focused narrative
        parts = []
        if soil_static:
            clay = soil_static.get("soil_clay_mean", "N/A")
            sand = soil_static.get("soil_sand_mean", "N/A")
            silt = soil_static.get("soil_silt_mean", "N/A")
            ph = soil_static.get("soil_ph_mean", "N/A")
            soc = soil_static.get("soil_org_c_mean", "N/A")
            texture = soil_static.get("texture_class", "unknown")
            parts.append(f"**Soil Profile** (SoilGrids 250m, ISRIC): {texture} — Clay: {clay}%, Sand: {sand}%, Silt: {silt}% | pH: {ph} | Organic Carbon: {soc} g/kg.")
        else:
            parts.append("Soil profile data from SoilGrids is not available for this location.")
            
        if soil_moisture_data:
            m = soil_moisture_data.get("moisture", {})
            t = soil_moisture_data.get("temperature", {})
            ts_str = soil_moisture_data.get("timestamp", "now")
            m_07 = f"{m.get('0_7cm', 'N/A'):.3f}" if m.get('0_7cm') is not None else "N/A"
            m_728 = f"{m.get('7_28cm', 'N/A'):.3f}" if m.get('7_28cm') is not None else "N/A"
            m_28100 = f"{m.get('28_100cm', 'N/A'):.3f}" if m.get('28_100cm') is not None else "N/A"
            t_07 = f"{t.get('0_7cm', 'N/A'):.1f}°C" if t.get('0_7cm') is not None else "N/A"
            parts.append(f"\n**Current Soil Moisture** (Open-Meteo ERA5-Land, {ts_str}): Surface (0-7cm): {m_07} m³/m³ | Root zone (7-28cm): {m_728} m³/m³ | Deep (28-100cm): {m_28100} m³/m³ | Surface Temp: {t_07}.")
        else:
            parts.append("\nReal-time soil moisture data is not available.")
        
        # Interpretation
        if soil_moisture_data and soil_moisture_data.get("moisture", {}).get("0_7cm") is not None:
            sm_surface = soil_moisture_data["moisture"]["0_7cm"]
            if sm_surface < 0.15:
                interpretation = "Surface soil moisture is low. Consider monitoring irrigation needs."
            elif sm_surface < 0.30:
                interpretation = "Soil moisture is in a healthy range for most crops."
            else:
                interpretation = "Soil moisture is high — waterlogging risk for sensitive crops."
        else:
            interpretation = "Without real-time moisture readings, assess field conditions visually."
        
        parts.append(f"\n**What it means**: {interpretation}")
        
        teaching = "Soil moisture between 0.15–0.30 m³/m³ at surface depth typically supports healthy root uptake. Sandy soils drain faster (need more frequent irrigation), while clay soils retain more water but risk waterlogging."
        parts.append(f"\n**Quick Lesson**: {teaching}")
        
        narrative = "\n".join(parts)
        headline = f"Soil Data for Your Field"
    else:
        # Weather-focused narrative (existing logic)
        avg_weekly = (rain_val / period_days) * 7 if period_days > 0 else 0
        
        interpretation = "This is within the normal seasonal range."
        if avg_weekly < 10:
            interpretation = "This is below the typical 25mm/week threshold for many crops, suggesting potential dryness."
        elif avg_weekly > 50:
            interpretation = "This is substantial rainfall, likely refilling the soil profile but increasing fungal risk."
        
        teaching = "Rule of thumb: 25-35 mm/week often maintains crops in mid-season, though sandy soils drain faster."
        
        narrative = f"During this period ({artifact.inputs.date_range['start']} to {artifact.inputs.date_range['end']}), your field received {rain_val:.1f} mm of rainfall over {days_count} wet days.\n\n"
        narrative += f"**What it means**: {interpretation}\n\n"
        narrative += f"**Why**: Data from Layer 1 Weather Aggregation shows {days_count} precipitation events.\n\n"
        narrative += f"**Quick Lesson**: {teaching}"
        headline = _extract_headline(narrative)
    
    summary["explanation"] = narrative
    summary["headline"] = headline
    
    # Feature Snapshot
    snapshot = {"rain_total": rain_val}
    if soil_static:
        snapshot["soil_clay"] = soil_static.get("soil_clay_mean")
        snapshot["soil_sand"] = soil_static.get("soil_sand_mean")
        snapshot["soil_ph"] = soil_static.get("soil_ph_mean")
        snapshot["soil_texture"] = soil_static.get("texture_class")
    if soil_moisture_data:
        snapshot["soil_moisture_0_7cm"] = soil_moisture_data.get("moisture", {}).get("0_7cm")
        snapshot["soil_moisture_7_28cm"] = soil_moisture_data.get("moisture", {}).get("7_28cm")
    summary["feature_snapshot"] = snapshot

    # Context Question
    ctx_q = _select_context_question(artifact.inputs, artifact.global_quality)
    questions_for_user = [ctx_q] if ctx_q else []
        
    arf = {
        "headline": headline,
        "direct_answer": narrative,
        "suitability_score": "N/A",
        "confidence_badge": "HIGH",
        "confidence_reason": "Based directly on verifiable deterministic telemetry from SoilGrids (ISRIC) and Open-Meteo ERA5-Land." if is_soil_query else "Based directly on verifiable deterministic telemetry and local station data.",
        "what_it_means": interpretation,
        "reasoning_cards": [],
        "recommendations": [],
        "learning": {
            "level": "INTERMEDIATE",
            "micro_lesson": teaching,
            "definitions": {}
        },
        "followups": [{"question": ctx_q, "why": "Context needed"}] if ctx_q else [],
        "internal_memory_updates": None
    }
    
    # Validate through Schema
    from orchestrator_v2.arf_schema import ARFResponse
    arf = ARFResponse(**arf).dict()

    return ChatPayload(
        run_id=artifact.meta.orchestrator_run_id,
        global_quality={"reliability": 1.0, "degradation_modes": [], "alerts": []},
        summary=summary,
        diagnoses=[],
        actions=[],
        plan={"tasks": []},
        citations=[],
        assistant_mode="DATA_ONLY",
        assistant_style="TUTOR",
        questions_for_user=questions_for_user,
        arf=arf,
        memory={},
        ui_hints={"show_reliability_banner": False, "show_blocked_banner": False, "card_ordering": []},
        visuals=[]
    )

def _select_context_question(inputs, quality, mode: str = "MONITORING") -> Optional[str]:
    """
    Selects the single most valuable missing piece of context, adapted to the current mode.
    """
    # Priority 0: Mode-Specific Critical Gaps
    if mode == "DATA_GAP":
        return "Data is sparse. Do you have local rain gauge logs or soil sensors?"
        
    if mode == "VERIFY_REQUIRED":
        return "To confirm this diagnosis, can you upload a close-up photo of the lower leaves?"
        
    if mode == "ADVISORY":
        # Decisions need context
        irrig = inputs.operational_context.get("irrigation_type", None)
        if not irrig:
            return "For accurate advice, do you use drip, pivot, or flood irrigation?"
        soil = inputs.operational_context.get("soil_type", None)
        if not soil:
            return "Soil texture affects water retention. Is your field Sandy, Clay, or Loam?"
            
    # Priority 1: Crop Config (Universal Baseline)
    crop = inputs.crop_config.get("crop", "Unknown")
    if crop in ["Unknown", "Generic"]:
        return "To improve stress analysis, what crop are you growing here?"
        
    # Priority 2: General Context 
    # (If we are in MONITORING/DATA_ONLY but have context gaps)
    irrig = inputs.operational_context.get("irrigation_type", None)
    if not irrig:
        return "Do you use irrigation (drip, pivot) or is this rainfed?"
        
    # Priority 3: Quality Boosters
    if quality.reliability_score < 0.8:
        return "Reliability is slightly low. Can you upload a field photo to verify condition?"
        
    return None

def _generate_llm_answer_arf_v1(
    summary: Dict,
    diags: List[ChatDiagnosis],
    actions: List[ChatAction],
    tasks: List[ChatTask],
    memory_context: Dict,
    user_query: Optional[str] = None,
    mode: str = "MONITORING"
) -> Dict[str, Any]:
    """
    Implements Agronomy Reasoning Framework v1 (ARF-v1).
    Returns structured JSON.
    """
    import os
    import requests
    import json
    
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return {"error": "LLM Key missing"}

    # Safety Guard
    safe_actions = actions
    if mode == "DATA_GAP":
        safe_actions = [a for a in actions if "INTERVENE" not in a.title]

    # Construct FIELD_CONTEXT
    field_context = {
        "assistant_mode": mode,
        "global_quality": summary.get("global_quality", {}), # passed in via summary? No, check caller.
        # Caller passes summary which has 'key_signals'.
        # We need to ensure summary has quality info or pass it separate.
        # In build_chat_payload, summary doesn't have quality. artifact.global_quality is separate.
        # I'll rely on what's passed or add quality to arguments?
        # For now, summary has 'period' and 'stage'.
        "summary": summary,
        "diagnoses": [d.__dict__ for d in diags],
        "actions": [a.__dict__ for a in safe_actions],
        "memory": memory_context
    }
    
    ARF_V1_SYSTEM_PROMPT = """
You are AgriBrain, an expert agronomist and farm advisor who also teaches.
You MUST follow the Agronomy Reasoning Framework v1 (ARF-v1).

You will be given a JSON object called FIELD_CONTEXT.
You MUST:
- Ground ALL field-specific claims in FIELD_CONTEXT only.
- If a signal/driver is missing, state that clearly and reduce certainty.
- Never invent sensor readings, satellite values, disease names, or actions.

SAFETY + GOVERNANCE:
- If assistant_mode is DATA_GAP: you MUST NOT recommend any INTERVENE action.
  Only VERIFY and MONITOR are allowed. (Even if probability is high.)
- If an action is marked is_allowed=false or blocked_reason is non-empty,
  you must treat it as blocked and offer safer alternatives.

PROBABILITY vs CONFIDENCE:
- Probability = how likely the hypothesis is given evidence.
- Confidence = trust in data quality (degrades when drivers missing).
Explain this simply when diagnoses are present.

OUTPUT REQUIREMENTS:
Return ONLY valid JSON with keys:
headline, direct_answer, what_it_means, evidence, diagnoses, actions,
teaching_note, next_questions, limitations.

STYLE:
- Be advanced but clear. Teach as you go.
- Prefer short sections; no long paragraphs.
- If the user asked a pure data question ("how much rain..."), answer directly
  and add a short teaching_note.
"""

    user_prompt = f"""
FIELD_CONTEXT:
{json.dumps(field_context, indent=2)}

USER_QUESTION:
{user_query or "Status update"}

Now produce ARF-v1 JSON output.
"""

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://agriwise.app", 
                "X-Title": "AgriWise"
            },
            json={
                "model": "qwen/qwen-2.5-72b-instruct", 
                "messages": [
                    {"role": "system", "content": ARF_V1_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.5, # Lower temp for JSON stability
                "max_tokens": 1000,
                "response_format": {"type": "json_object"} # Force JSON if supported
            },
            timeout=15
        )
        
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            try:
                # Clean markdown code blocks if any
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                return json.loads(content.strip())
            except Exception as e:
                print(f"JSON Parse Error: {e}")
                return {"error": "Failed to parse ARF JSON", "raw": content}
        else:
            return {"error": f"LLM Error {resp.status_code}"}
            
    except Exception as e:
        print(f"Request Error: {e}")
        return {"error": str(e)}
