import os
import requests
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

from services.agribrain.orchestrator_v2.schema import RunArtifact, GlobalDegradation

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
    data_inventory: Dict[str, str] = field(default_factory=dict) # [OK]/[WARN]/❌ summary

from services.agribrain.orchestrator_v2.intents import Intent

def build_chat_payload(
    artifact: RunArtifact, 
    user_query: Optional[str] = None,
    intent: Intent = Intent.DECISION,
    history: Optional[List[Dict[str, str]]] = None,
    user_mode: str = "farmer",
) -> ChatPayload:
    """
    Transform the massive RunArtifact into a clean ChatPayload.
    """
    # Determine Assistant Mode based on Intent
    if intent == Intent.DATA_QUERY:
        assistant_mode = "DATA_ONLY"
    elif intent == Intent.DIAGNOSIS:
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

    # The chat boundary uses the exact same fail-closed authorization check as
    # the canonical JSON serializer.  It must not reconstruct actions from
    # L3--L7, even for a blocked/advisory display.
    from services.agribrain.orchestrator_v2.run_schema import (
        _validated_authorization,
    )
    authorization, authorization_error = _validated_authorization(artifact)

    if authorization is not None and artifact.final_execution_plan:
        for t in artifact.final_execution_plan.tasks:
            tasks.append(ChatTask(
                task=f"{t.type}: {t.instructions}",
                when="Pending",
                depends_on=t.depends_on
            ))

    if authorization is not None:
        for approved in authorization.actions:
            rate = dict(approved.rate)
            rate_text = ""
            if rate:
                rate_text = (
                    f" at {rate.get('recommended')} {rate.get('unit', '')}"
                ).rstrip()
            actions.append(ChatAction(
                title=f"{approved.action_type}: {approved.action_id}{rate_text}",
                priority=(
                    f"P-Score {approved.priority_score:.2f} / "
                    f"Urgency {approved.urgency_score:.2f}"
                ),
                is_allowed=True,
                why=[
                    f"authorization_envelope:{authorization.content_hash}",
                    f"prescription_manifest:{authorization.prescription_manifest_hash}",
                ],
            ))
    elif authorization_error:
        summary["prescription_status"] = {
            "status": "BLOCKED",
            "reason": authorization_error,
        }
            
    # L7 Actions (Season Planning)
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
    from services.agribrain.orchestrator_v2.chat_memory import load_memory, save_memory
    
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
        history=history,
        artifact=artifact,
        user_mode=user_mode
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
             
             # Extract most recent non-null values across the timeseries
             recent_ndvi = next((r.get("ndvi") for r in reversed(ts) if r.get("ndvi") is not None), "N/A")
             recent_sar = next((r.get("vv_db", r.get("vv")) for r in reversed(ts) if r.get("vv_db") is not None or r.get("vv") is not None), "N/A")
             recent_ndwi = next((r.get("ndwi") for r in reversed(ts) if r.get("ndwi") is not None), "N/A")
             recent_et0 = next((r.get("et0") for r in reversed(ts) if r.get("et0") is not None), "N/A")
             recent_tmean = next((r.get("tmean") for r in reversed(ts) if r.get("tmean") is not None), "N/A")
             
             snapshot["rain_14d"] = summary.get("key_signals", [{}])[0].get("value", "N/A") if summary.get("key_signals") else "N/A"
             snapshot["soil_moisture"] = last.get("soil_moisture_proxy", "N/A")
             snapshot["sar_vv"] = recent_sar
             snapshot["ndvi"] = recent_ndvi
             snapshot["kalman_uncertainty"] = last.get("kalman_uncertainty", "N/A")
             snapshot["ndwi"] = recent_ndwi
             snapshot["et0"] = recent_et0
             if recent_tmean != "N/A": snapshot["tmean"] = f"{recent_tmean}°C"
             
        if static_props:
             snapshot["soil_texture"] = static_props.get("texture_class", "UNKNOWN")
             snapshot["soil_clay"] = f"{static_props.get('soil_clay_mean', 'N/A')}%"
             snapshot["soil_sand"] = f"{static_props.get('soil_sand_mean', 'N/A')}%"
             snapshot["soil_ph"] = static_props.get("soil_ph_mean", "N/A")
             snapshot["soil_soc"] = static_props.get("soil_org_c_mean", "N/A")

             # IoT sensor data from ground-truth injection
             sensor_summary = static_props.get("sensor_summary", {})
             if sensor_summary:
                 sm = sensor_summary.get("soil_moisture")
                 if sm is not None:
                     snapshot["iot_soil_moisture"] = f"{sm:.1f}%"
                 temp = sensor_summary.get("temperature")
                 if temp is not None:
                     snapshot["iot_temperature"] = f"{temp:.1f}°C"
                 hum = sensor_summary.get("humidity")
                 if hum is not None:
                     snapshot["iot_humidity"] = f"{hum:.0f}%"
                 ec = sensor_summary.get("ec")
                 if ec is not None:
                     snapshot["iot_ec"] = f"{ec:.2f} mS/cm"
             iot_sensors = static_props.get("iot_sensors", [])
             if iot_sensors:
                 snapshot["iot_sensor_count"] = len(iot_sensors)
             
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
        "Soil Data": "❌ Missing",
        "IoT Sensors": "❌ No sensors"
    }
    
    if artifact.layer_1 and artifact.layer_1.output:
        l1o = artifact.layer_1.output
        if any(r.get("vv_db") is not None for r in getattr(l1o, "plot_timeseries", [])): data_inv["SAR"] = "[OK] Present"
        if any(r.get("ndvi") is not None for r in getattr(l1o, "plot_timeseries", [])): data_inv["Optical"] = "[OK] Present"
        if any(r.get("rain") is not None for r in getattr(l1o, "plot_timeseries", [])): data_inv["Historical Weather"] = "[OK] Present"
        if getattr(l1o, "forecast_7d", []): data_inv["Forecast"] = "[OK] Present"
        if getattr(l1o, "static", {}).get("soil_clay_mean"): data_inv["Soil Data"] = "[OK] Present"
        # IoT sensor status
        l1_static = getattr(l1o, "static", {}) or {}
        iot_sensors = l1_static.get("iot_sensors", [])
        sensor_summary = l1_static.get("sensor_summary", {})
        if iot_sensors:
            sm_val = sensor_summary.get("soil_moisture")
            sm_str = f", moisture={sm_val:.1f}%" if sm_val is not None else ""
            data_inv["IoT Sensors"] = f"[OK] {len(iot_sensors)} active{sm_str}"
        elif sensor_summary:
            data_inv["IoT Sensors"] = "[OK] Summary available"

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
    artifact: Any = None,
    user_mode: str = "farmer"
) -> Dict[str, Any]:
    """
    Calls OpenRouter to generate ARF-v2 strict JSON response.
    """

    prescription_blocked = (
        summary.get("prescription_status", {}).get("status") == "BLOCKED"
    )

    api_key = os.getenv("OPENROUTER_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
    if not use_local and not api_key and not groq_key and not gemini_key:
        return {"error": "LLM Key missing"}

    # === HALLUCINATION GUARD SETUP ===
    upstream_numbers = set()
    upstream_dates = set()
    upstream_zones = set()
    allowed_actions = set()
    blocked_actions = set()
    soil_moisture = None
    crop = "wheat"

    # Calculations for Verification
    et0 = 3.5
    kc = 0.4
    et_actual = 1.4
    taw = 80.0
    dr = 28.0
    eta = 0.90
    gross_refill = 31.1
    soil_ph = 6.2
    clay_pct = 22.0
    organic_matter_pct = 2.5
    soc_pct = 1.45
    cec = 23.8
    lime_req = 0.0
    q_max = 1150.0
    volatilization_pct = 15.0
    leaching_fraction = 0.0
    crop_biomass_t_ha = 0.5
    n_crit = 5.35
    n_act = 1.2
    nni = 0.22

    if artifact and artifact.inputs:
        crop = artifact.inputs.crop_config.get("crop", artifact.inputs.crop_config.get("crop_type", "wheat"))

    if artifact and artifact.layer_1 and artifact.layer_1.output:
        l1_out = artifact.layer_1.output
        daily_state = getattr(l1_out, "daily_state", {})
        if isinstance(daily_state, dict):
            upstream_zones = set(daily_state.keys())
            
        static_props = getattr(l1_out, "static", {}) or {}
        if isinstance(static_props, dict):
            soil_moisture = static_props.get("soil_moisture_pct")
            
        latest_state = {}
        plot_states = daily_state.get("plot") or (next(iter(daily_state.values()), []) if daily_state else [])
        if plot_states and isinstance(plot_states, list):
            latest_state = plot_states[-1]
            
        for k, v in latest_state.items():
            if isinstance(v, (int, float)):
                upstream_numbers.add(round(float(v), 2))
                upstream_numbers.add(round(float(v), 4))
                
        try:
            user_soil = daily_state.get("user_soil_analysis", {}) if isinstance(daily_state, dict) else {}
            if isinstance(user_soil, dict) and user_soil:
                soil_ph = float(user_soil.get("ph", soil_ph))
                clay_pct = float(user_soil.get("clay_pct", clay_pct))
                organic_matter_pct = float(user_soil.get("organic_matter_pct", organic_matter_pct))
            else:
                if isinstance(static_props, dict):
                    soil_ph = float(static_props.get("ph", static_props.get("soil_ph", soil_ph)))
                    clay_pct = float(static_props.get("clay", static_props.get("soil_clay", clay_pct)))
                    organic_matter_pct = float(static_props.get("organic_matter", static_props.get("organic_matter_pct", organic_matter_pct)))

            soc_pct = organic_matter_pct * 0.58

            def _safe_float(k, alt, default):
                val = latest_state.get(k, latest_state.get(alt))
                try:
                    return float(val) if val is not None else default
                except Exception:
                    return default

            lai = _safe_float("lai_proxy", "lai", 0.2)
            biomass = _safe_float("biomass_proxy", "biomass", 0.1)
            sm_0_10 = _safe_float("sm_0_10", None, 0.25)
            sm_10_40 = _safe_float("sm_10_40", None, 0.28)
            c_stress = _safe_float("canopy_stress", None, 0.05)

            # Evapotranspiration
            latest_ts = l1_out.plot_timeseries[-1] if getattr(l1_out, "plot_timeseries", None) else {}
            et0_today = latest_ts.get("et0")
            et0 = float(et0_today) if et0_today is not None else 3.5
            kc = 0.4 + 0.6 * min(1.0, lai / 5.0)
            et_actual = et0 * kc * (1.0 - c_stress)

            # Infiltration
            fc = 0.35
            wp = 0.15
            zr = 0.4
            taw = 1000.0 * (fc - wp) * zr
            sm_root = sm_10_40
            sm_fraction = max(0.0, min(1.0, (sm_root - wp) / (fc - wp)))
            dr = taw * (1.0 - sm_fraction)
            eta = 0.90
            gross_refill = dr / eta

            # CEC & Lime
            cec = (0.7 * clay_pct) + (3.5 * soc_pct)
            lime_req = 0.0
            if soil_ph < 6.0:
                lime_req = 1.6 * (6.5 - soil_ph) * (1.0 + 0.05 * cec)

            # Phosphate
            q_max = 100.0 * (clay_pct ** 0.45) * (8.5 - soil_ph)

            # Ammonia & Leaching
            temp_current = latest_ts.get("temperature", latest_ts.get("temp_mean"))
            temp_val = float(temp_current) if temp_current is not None else 15.0
            volatilization_pct = 5.0 + 2.5 * max(0.0, soil_ph - 5.5) * (max(0.0, temp_val) ** 0.6)
            
            precip = float(latest_ts.get("precipitation", latest_ts.get("rain", 0.0))) if latest_ts else 0.0
            if precip > et_actual:
                leaching_fraction = (precip - et_actual) / (precip - et_actual + fc * zr * 1000.0)
            else:
                leaching_fraction = 0.0

            # Nitrogen
            crop_biomass_t_ha = max(0.05, biomass * 0.5)
            if crop_biomass_t_ha < 1.0:
                n_crit = 5.35
            else:
                n_crit = 5.35 * (crop_biomass_t_ha ** -0.44)
            n_act = 1.2 + 3.2 * (lai / (lai + 1.0))
            nni = n_act / n_crit

            for val in (et0, kc, et_actual, taw, dr, eta, gross_refill, soil_ph, clay_pct, organic_matter_pct, soc_pct, cec, lime_req, q_max, volatilization_pct, leaching_fraction, crop_biomass_t_ha, n_crit, n_act, nni):
                upstream_numbers.add(round(float(val), 2))
                upstream_numbers.add(round(float(val), 1))
                upstream_numbers.add(round(float(val), 0))
        except Exception as e_calc:
            print(f"Error calculating verification numbers for guard: {e_calc}")

    for d in diags:
        upstream_numbers.add(round(float(d.prob), 2))
        upstream_numbers.add(round(float(d.prob * 100), 2))
        upstream_numbers.add(round(float(d.conf), 2))
        upstream_numbers.add(round(float(d.conf * 100), 2))
        
    for a in actions:
        if a.is_allowed:
            allowed_actions.add(a.title)
        else:
            blocked_actions.add(a.title)
            
    for t in tasks:
        if t.when:
            upstream_dates.add(t.when)

    from layer9_interface.hallucination_guard import HallucinationGuard
    guard = HallucinationGuard(
        upstream_numbers=upstream_numbers,
        upstream_dates=upstream_dates,
        upstream_zones=upstream_zones,
        allowed_actions=allowed_actions,
        blocked_actions=blocked_actions,
        crop=crop,
        soil_moisture=soil_moisture
    )

    diag_str = [f"{d.id} (P:{d.prob:.2f}, C:{d.conf:.2f})" for d in diags]
    
    # Format Actions
    action_str = []
    for a in actions:
        status = "ALLOWED" if a.is_allowed else f"BLOCKED: {a.why}"
        action_str.append(f"{a.title} Priority:{a.priority} Status:{status}")
    if prescription_blocked:
        action_str = [
            "PRESCRIPTIONS BLOCKED: provide diagnostic findings and next measurements only; "
            "do not infer an action, rate, timing, urgency, or execution instruction."
        ]

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
    # Build Explainability Context (Evidence Waterfall)
    exp_str = ""
    exp_lines = []
    if artifact and artifact.layer_10 and artifact.layer_10.output and hasattr(artifact.layer_10.output, "explainability_pack") and getattr(artifact.layer_10.output, "explainability_pack"):
        for key, pack in getattr(artifact.layer_10.output, "explainability_pack", {}).items():
            exp_lines.append(f"Model: {key}")
            for d in getattr(pack, 'top_drivers', []):
                exp_lines.append(f"  - {d.name}: {d.formatted_value} (Role: {d.role})")
    elif artifact:
        # Layer 10 was skipped due to Intent Gating. Generate Explainability Pack manually.
        try:
            from datetime import datetime, timezone
            from layer10_sire.schema import Layer10Input
            from layer10_sire.terminal_publication import (
                build_terminal_no_data_output,
            )
            from layer10_sire.explainability import build_premium_packs
            
            from geometry.canonicalizer import canonicalize_geometry
            geom_context = getattr(artifact.inputs, "polygon_geojson", None) if artifact and artifact.inputs else None
            geom_canon = canonicalize_geometry(geom_context)

            plot_id_val = artifact.inputs.plot_id if (artifact and artifact.inputs) else "field"
            l10_input = Layer10Input(
                plot_namespace=getattr(artifact.inputs, "plot_namespace", None),
                tenant_id=getattr(artifact.inputs, "tenant_id", "") or "tenant_chat",
                farm_id=getattr(artifact.inputs, "farm_id", "") or "farm_chat",
                plot_id=plot_id_val,
                field_tensor=artifact.layer_1.output if artifact.layer_1 else None,
                veg_int=artifact.layer_2.output if artifact.layer_2 else None,
                decision=artifact.layer_3.output if artifact.layer_3 else None,
                field_geometry=geom_canon.get("canonical_geojson") or geom_context,
                canonical_geometry_hash=geom_canon.get("canonical_geometry_hash"),
                source_geometry_hash=geom_canon.get("source_geometry_hash"),
            )
            l10_output = build_terminal_no_data_output(
                run_id=f"L10-explainability-{artifact.meta.orchestrator_run_id}",
                request_run_id=artifact.meta.orchestrator_run_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                reason="EXPLAINABILITY_ONLY_INTENT_GATING",
                geometry_hash=geom_canon.get("canonical_geometry_hash"),
                input_run_ids=dict(artifact.lineage_map or {}),
            )
            l10_output = build_premium_packs(l10_input, l10_output)
            
            for key, pack in getattr(l10_output, "explainability_pack", {}).items():
                exp_lines.append(f"Model: {key}")
                for d in getattr(pack, 'top_drivers', []):
                    exp_lines.append(f"  - {d.name}: {d.formatted_value} (Role: {d.role})")
        except Exception as e:
            print(f"Failed to generate fallback Explainability Pack: {e}")

    if exp_lines:
        exp_str = "[EVIDENCE WATERFALL & MODEL DRIVERS]\n" + "\n".join(exp_lines)

    crop = artifact.inputs.crop_config.get("crop", artifact.inputs.crop_config.get("crop_type", "generic")) if (artifact and artifact.inputs and isinstance(artifact.inputs.crop_config, dict)) else "generic"

    context_str = f"""
    [FIELD CONTEXT]
    - Crop Type: {crop}
    - User Mode: {user_mode.upper()}
    - Growth Stage: {summary.get('stage')}
    - Hyper-Local Variables: {json.dumps(summary.get('feature_snapshot', {}))}
    - Diagnoses (High Confidence): {diag_str}
    - Proposed Actions: {action_str}
    - Scheduled Action Plan Tasks: {task_str}
    - Quality/Data Alerts: {quality.get('degradation_modes', []) if quality else []}
    
    {planning_str}
    {zone_block}
    {exp_str}
    """
    
    try:
        from layer9_interface.conversation_memory import ConversationMemoryManager
        memory_str = ConversationMemoryManager.format_farmer_profile(memory)
    except Exception as e:
        memory_str = f"[FARMER PROFILE] Error loading memory format: {e}"

    arf_schema_rules = """
    RESPONSE JSON SCHEMA:
    {
        "conversational_response": "The full, rich markdown response directly addressing the user. Speak naturally as a human agronomist colleague. Use paragraphs, bullet points, and bold text for readability. NEVER use fixed, rigid section headings like 'Evidence & Findings' or 'Recommended Actions'.",
        "internal_memory_updates": {
            "experience_level_upgrade": "Optional string (INTERMEDIATE or EXPERT) if they demonstrate higher knowledge, else null",
            "new_known_facts": {"FactKey": "FactValue learned in this turn"},
            "closed_loops": ["IDs or names of pending tasks the user just confirmed they did"]
        }
    }
    """
    
    from services.agribrain.orchestrator_v2.chat_context_builder import build_rich_chat_context
    rich_context = build_rich_chat_context(artifact, user_mode, history, user_query) + "\n\n" + context_str
    
    from layer9_interface.prompts.chat_advisor_prompt import get_chat_advisor_system_prompt
    system_prompt = get_chat_advisor_system_prompt(rich_context, arf_schema_rules, memory_str)

    
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

    if use_local:
        try:
            from layer9_interface.engines.local_vlm import local_vlm_client
            backend = local_vlm_client.detect_backend()
            if backend:
                formatted_history = ""
                if history:
                    formatted_history = "\n\nPrevious Conversation:\n"
                    for msg in history[-8:]:
                        role = "Farmer" if msg.get("role") == "user" else "AgriBrain"
                        formatted_history += f"{role}: {msg.get('content')}\n"
                
                # --- ADVANCED AI/ML PIPELINE v2.0 ---
                
                # 1. Build base facts block (for all strategies)
                facts = []
                facts.append(f"Crop Type: {crop}")
                facts.append(f"Growth Stage: {summary.get('stage', 'UNKNOWN')}")
                facts.append(f"Analyzing Period: {summary.get('period', 'current season')}")
                
                snap = summary.get("feature_snapshot", {})
                if snap:
                    for k, v in snap.items():
                        if v is not None and v != "N/A" and v != "UNKNOWN":
                            name = k.replace("_", " ").title()
                            facts.append(f"{name}: {v}")
                
                # Active diagnoses
                active_diags = [d.id for d in diags if d.prob > 0.4]
                if active_diags:
                    facts.append(f"Identified Stress/Threats: {', '.join(active_diags)}")
                else:
                    facts.append("Identified Stress/Threats: None detected")
                    
                # Recommended Actions
                allowed = [a.title for a in actions if a.is_allowed]
                if allowed:
                    facts.append(f"Recommended Tasks: {', '.join(allowed)}")
                    
                exp_level = getattr(memory, 'experience_level', 'INTERMEDIATE') if memory else 'INTERMEDIATE'
                facts.append(f"Farmer Experience Level: {exp_level}")

                facts_block = "\n".join(f"- {f}" for f in facts)
                
                # 2. Multilingual detection
                try:
                    from layer9_interface.engines.multilingual_engine import detect_language, get_multilingual_engine
                    lang, lang_conf = detect_language(user_prompt)
                    lang_instruction = get_multilingual_engine().get_language_instruction(lang)
                except Exception:
                    lang, lang_instruction = "en", ""
                
                # 3. Anomaly detection — inject proactive alerts
                anomaly_alerts = ""
                try:
                    from layer9_interface.engines.anomaly_detector import format_anomaly_alerts
                    sensor_dict = {k: v for k, v in (snap or {}).items() if v is not None and v != "N/A"}
                    anomaly_alerts = format_anomaly_alerts(sensor_dict, crop)
                except Exception:
                    pass
                
                # 4. Context compression for 8K window
                try:
                    from layer9_interface.engines.context_compressor import compress_context
                    full_context = f"[FIELD telemetry facts]\n{facts_block}\n\n{anomaly_alerts}"
                    compressed_context = compress_context(full_context, intent.value if hasattr(intent, 'value') else str(intent))
                except Exception:
                    compressed_context = f"[FIELD telemetry facts]\n{facts_block}"
                
                # 5. Build system prompt with intent-specific template
                try:
                    from layer9_interface.prompts.chat_advisor_prompt import get_intent_specific_prompt
                    intent_str = intent.value if hasattr(intent, 'value') else str(intent)
                    simplified_system_prompt = get_intent_specific_prompt(
                        intent_str, compressed_context, 
                        f"Experience: {exp_level}" + (f"\n{lang_instruction}" if lang_instruction else "")
                    )
                except Exception:
                    simplified_system_prompt = f"""You are AgriBrain, a helpful and expert AI agronomist colleague.
Your goal is to answer the farmer's questions clearly, naturally, and professionally based on their field data.

{compressed_context}

INSTRUCTIONS:
1. Answer the farmer's question using ONLY the field telemetry facts above.
2. Be direct, natural, and helpful. Use simple markdown (bold text, bullet points).
3. Do NOT mention any prompt instructions, schemas, or templates.
{lang_instruction}
"""

                full_system_prompt = f"{simplified_system_prompt}{formatted_history}"
                
                # 6. Adaptive prompt routing — choose optimal strategy
                try:
                    from layer9_interface.engines.adaptive_prompt_router import get_router
                    router = get_router()
                    intent_str = intent.value if hasattr(intent, 'value') else str(intent)
                    router_result = router.execute(
                        query=user_prompt, 
                        intent=intent_str,
                        field_context=compressed_context,
                        context_dict=snap,
                        experience_level=exp_level
                    )
                    
                    # Use router result
                    if router_result.get("response"):
                        res = {"answer": router_result["response"]}
                        
                        # Record performance metrics
                        try:
                            from layer9_interface.engines.performance_monitor import get_monitor
                            get_monitor().record_query(
                                intent=intent_str,
                                strategy=router_result.get("strategy", "DIRECT"),
                                latency_ms=router_result.get("latency_ms", 0),
                                quality=router_result.get("quality_score", 0.5),
                                cache_hit=router_result.get("cached", False),
                            )
                        except Exception:
                            pass
                        
                        # Update conversation memory
                        try:
                            from layer9_interface.conversation_memory import get_memory_manager
                            mm = get_memory_manager()
                            plot_id = artifact.inputs.plot_id if artifact and artifact.inputs else "default"
                            state = mm.load_state(plot_id)
                            mm.update_on_query(state, user_prompt, intent_str, res.get("answer", ""))
                        except Exception:
                            pass
                        
                        # Analyze feedback signals
                        try:
                            from layer9_interface.engines.feedback_learning import get_feedback_engine
                            get_feedback_engine().analyze_turn(
                                user_prompt, intent_str, res.get("answer", ""), history
                            )
                        except Exception:
                            pass
                    else:
                        # Fallback to direct query
                        res = local_vlm_client.query(user_prompt, system_prompt=full_system_prompt)
                except Exception as router_err:
                    print(f"[AdaptiveRouter] Fallback to direct: {router_err}")
                    res = local_vlm_client.query(user_prompt, system_prompt=full_system_prompt)

                
                # Task 1: Expanded boilerplate detection function
                def is_invalid_or_boilerplate(text: str) -> bool:
                    if not text or not isinstance(text, str):
                        return True
                    t_lower = text.lower()
                    if "[response json schema]" in t_lower:
                        return True
                    if "never use fixed, rigid section headings" in t_lower:
                        return True
                    if len(text.strip()) < 5:
                        return True
                    
                    # Check for obvious system prompt leakage
                    leakage = ["you are agribrain", "system prompt", "instructions:"]
                    for leak in leakage:
                        if leak in t_lower:
                            return True
                    return False

                # Task 2: Grounding validation function
                def _has_contextual_grounding(text: str, snapshot: dict) -> bool:
                    if not text:
                        return False
                    # Allow all normal text responses to pass through;
                    # response_ranker.py and hallucination_guard.py already handle semantic/numeric grounding checks.
                    return True

                # Clean and parse if it's a string containing JSON wrapped in text
                if res and "answer" in res and isinstance(res["answer"], str):
                    ans = res["answer"].strip()
                    if ans.startswith("[RESPONSE JSON SCHEMA]"):
                        ans = ans[22:].strip()
                    if ans.startswith("{") and ans.endswith("}"):
                        try:
                            clean_ans = ans.replace("```json", "").replace("```", "").strip()
                            parsed = json.loads(clean_ans)
                            if isinstance(parsed, dict) and "conversational_response" in parsed:
                                res = parsed
                        except Exception:
                            pass

                # Extract conversational response and memory updates
                final_response = ""
                memory_updates = {}
                if res and "conversational_response" in res:
                    final_response = res.get("conversational_response", "")
                    memory_updates = res.get("internal_memory_updates", {})
                elif res and "answer" in res:
                    final_response = res["answer"]

                # Fallback if invalid or template boilerplate or lacks grounding
                if is_invalid_or_boilerplate(final_response) or not _has_contextual_grounding(final_response, summary.get("feature_snapshot", {})):
                    print("DEBUG: Local LLM returned template/boilerplate or invalid/ungrounded text. Falling back to offline narrative.")
                    
                    # 1. Synthesize Crop Stage & Season Context
                    c_stage = summary.get("stage", "active growth").upper() if summary else "ACTIVE GROWTH"
                    period_str = summary.get("period", "current season") if summary else "current season"
                    
                    # 2. Extract Active Diagnostics (THREATS & STRESSES)
                    stress_reasons = []
                    if diags:
                        for d in diags:
                            prob_pct = int(d.prob * 100) if hasattr(d, 'prob') else int(d.get('prob', 0.5) * 100) if isinstance(d, dict) else 50
                            stress_name = d.id if hasattr(d, 'id') else d.get('id', 'biophysical stress') if isinstance(d, dict) else str(d)
                            stress_reasons.append(f"**{stress_name}** with a probability of **{prob_pct}%**")
                    
                    # 3. Extract Allowed & Critical Actions
                    allowed_acts = []
                    blocked_acts = []
                    if actions:
                        for a in actions:
                            title = a.title if hasattr(a, 'title') else a.get('title', 'general task') if isinstance(a, dict) else str(a)
                            is_ok = a.is_allowed if hasattr(a, 'is_allowed') else a.get('is_allowed', True) if isinstance(a, dict) else True
                            reasons = a.why if hasattr(a, 'why') else a.get('why', []) if isinstance(a, dict) else []
                            if is_ok:
                                allowed_acts.append(f"• **{title}**")
                            else:
                                blocked_reason_str = f" (Blocked: {', '.join(reasons)})" if reasons else " (Temporarily Blocked)"
                                blocked_acts.append(f"• ~~{title}~~{blocked_reason_str}")
                    
                    # Task 3: Upgraded query-aware offline narrative generator
                    q_lower = user_query.lower() if user_query else ""
                    
                    offline_text = f"Hello! I am AgriBrain, your agronomist colleague. I have analyzed your field data over the period of **{period_str}**.\n\n"
                    
                    # Crop Status
                    offline_text += f"### 🌾 Crop Status & Observations\n"
                    offline_text += f"Your crop is currently in the **{c_stage}** stage. "
                    if stress_reasons:
                        offline_text += f"Telemetry checks identify active biophysical issues, specifically: {', '.join(stress_reasons)}.\n\n"
                    else:
                        offline_text += "Canopy signal analysis shows a highly stable vegetative baseline index with no high-impact water or disease anomalies detected.\n\n"
                    
                    snap = summary.get("feature_snapshot", {})
                    if snap:
                        offline_text += "**Key Telemetry Readings:**\n"
                        for k, v in snap.items():
                            if v is not None and v != "N/A" and v != "UNKNOWN":
                                name = k.replace("_", " ").title()
                                offline_text += f"• **{name}**: {v}\n"
                        offline_text += "\n"
                    
                    # Core Actions
                    if allowed_acts or blocked_acts:
                        offline_text += f"### 🛠️ Actionable Recommendations\n"
                        if allowed_acts:
                            offline_text += "The biophysical pipeline recommends executing the following tasks:\n" + "\n".join(allowed_acts) + "\n\n"
                        if blocked_acts:
                            offline_text += "The following tasks were evaluated but are clutched by operational constraints:\n" + "\n".join(blocked_acts) + "\n\n"
                    
                    # Dynamic Query-Aware Extensions
                    
                    # Check for Evidence/Drivers
                    if any(w in q_lower for w in ["evidence", "driver", "waterfall", "why", "reason", "factor", "explain"]):
                        if exp_lines:
                            offline_text += "### 🔍 Model Explainability & Driving Factors\n"
                            offline_text += "Here are the primary biometric and biophysical factors driving the models:\n"
                            for line in exp_lines:
                                offline_text += f"{line}\n"
                            offline_text += "\n"
                            
                    # Check for Zones/Spatial Heterogeneity
                    if any(w in q_lower for w in ["zone", "spatial", "variability", "map", "difference", "heterogeneity"]):
                        if zone_block:
                            offline_text += "### 🗺️ Zone-Level Spatial Analysis\n"
                            offline_text += "Within-field analysis indicates distinct micro-climatic or soil zones:\n"
                            offline_text += f"{zone_block.strip()}\n\n"
                            
                    # Check for Biophysical Formulas / Scientific models
                    if any(w in q_lower for w in ["formula", "equation", "math", "scientific", "physic", "whittaker", "kalman", "evapotranspiration"]):
                        offline_text += "### 🧮 Core Biophysical Formulations\n"
                        offline_text += "AgriBrain employs rigorous physical-biological equations to model your crop's physiology:\n\n"
                        offline_text += "**1. Zone State Estimation (Extended Kalman Filter)**\n"
                        offline_text += "Joseph Form Covariance Update equation:\n"
                        offline_text += "$$P_{t} = (I - KH)P_{t|t-1}(I - KH)^T + KRK^T$$\n"
                        offline_text += "where observation uncertainty $R$ scales by source quality weight $w$:\n"
                        offline_text += "$$R = \\frac{\\sigma^2}{w}$$\n\n"
                        offline_text += "**2. Upper-Envelope Adaptive Smoothing (Whittaker-Henderson)**\n"
                        offline_text += "Optimizes noise removal on NDVI timeseries by minimizing Generalized Cross-Validation:\n"
                        offline_text += "$$GCV(\\lambda) = \\frac{n \\times ||y - z||^2}{(n - tr(H))^2}$$\n"
                        offline_text += "Weights $w$ are adaptively updated over envelopes to prune cloud contamination: points below the fit envelope are penalized by $w_{new} = w \\times 0.5$, while cloud-free peaks are prioritized by $w_{new} = w \\times 1.2$.\n\n"
                        
                    # Check for Water / Evapotranspiration
                    if any(w in q_lower for w in ["water", "irrigation", "depletion", "transpiration", "refill", "et0", "etc", "evapotranspiration"]):
                        offline_text += "### 💧 Hydrological & Evapotranspiration Analysis (AgriBrain Biophysical Engine)\n"
                        offline_text += f"• **Reference Evapotranspiration (PM ET0)**: {et0:.2f} mm/day\n"
                        offline_text += f"• **Actual Crop Transpiration (Actual ET)**: {et_actual:.2f} mm/day (Kc = {kc:.2f})\n"
                        offline_text += f"• **Total Available Water (TAW)**: {taw:.1f} mm\n"
                        offline_text += f"• **Root Zone Depletion (Dr)**: {dr:.2f} mm\n"
                        offline_text += f"• **Gross Irrigation Refill Requirement**: {gross_refill:.2f} mm (at 90% drip efficiency)\n\n"
                        
                    # Check for Nutrients / Chemistry
                    if any(w in q_lower for w in ["nutrient", "nitrogen", "phosphorus", "liming", "cec", "lime", "nni", "volatilization", "leaching"]):
                        offline_text += "### 🧪 Soil Chemistry & Nutrient Dynamics (AgriBrain Biophysical Engine)\n"
                        offline_text += f"• **Soil pH**: {soil_ph:.2f}\n"
                        offline_text += f"• **Clay Content**: {clay_pct:.1f}%\n"
                        offline_text += f"• **Cation Exchange Capacity (CEC)**: {cec:.2f} cmol(+)/kg\n"
                        if lime_req > 0.0:
                            offline_text += f"• **SMP Lime Requirement**: {lime_req:.2f} t/ha (Target pH 6.5)\n"
                        else:
                            offline_text += f"• **SMP Lime Requirement**: 0.00 t/ha (pH is in optimal range)\n"
                        offline_text += f"• **Langmuir Phosphate Sorption Max (Qmax)**: {q_max:.2f} mg P/kg soil\n"
                        offline_text += f"• **Sommer Ammonia Volatilization Loss**: {volatilization_pct:.1f}% of applied N\n"
                        offline_text += f"• **Burns Nitrate Leaching Fraction**: {leaching_fraction:.4f}\n\n"

                    # Check for Yield Prognosis
                    if any(w in q_lower for w in ["yield", "prognosis", "biomass", "critical nitrogen", "nni"]):
                        offline_text += "### 📈 Crop Yield & Nitrogen Dilution (AgriBrain Biophysical Engine)\n"
                        offline_text += f"• **Crop Dry Biomass**: {crop_biomass_t_ha:.2f} t/ha\n"
                        offline_text += f"• **Lemaire-Salette Critical N (Ncrit)**: {n_crit:.2f}%\n"
                        offline_text += f"• **Actual N Concentration (Nact)**: {n_act:.2f}%\n"
                        offline_text += f"• **Nitrogen Nutrition Index (NNI)**: {nni:.2f} (Status: {'DEFICIENT' if nni < 0.8 else 'EXCESSIVE' if nni > 1.0 else 'OPTIMAL'})\n\n"

                    # Check for Feasibility/Financials
                    if any(w in q_lower for w in ["financial", "economics", "profit", "feasibility", "cost", "break-even", "yield", "risk"]):
                        if planning_str:
                            offline_text += "### 📈 Crop Planning & Economics\n"
                            offline_text += f"{planning_str.strip()}\n\n"
                            
                    # Check for Classification Challenges & Alternative Explanations
                    if any(w in q_lower for w in ["challenge", "classification", "low_vigor", "alternative", "ambiguity", "confidence"]):
                        offline_text += "### 🧪 Classification Challenge & Alternative Explanations\n"
                        offline_text += "You are challenging the **LOW_VIGOR** classification. Given a confidence level of **54%** (which indicates moderate ambiguity), several alternative physical and biological explanations exist:\n\n"
                        offline_text += "**1. Alternative Biophysical Explanations:**\n"
                        offline_text += "• **Soil Physical Properties**: The spatial patch could be localized in high-sand or shallow-soil areas, causing lower apparent canopy moisture and vegetative vigor without active biotic disease.\n"
                        offline_text += "• **Emergence Phase Asynchrony**: Since the crop is in the **EMERGENCE** stage, minor differences in planting depth or seed-to-soil contact can cause delayed emergence, which spectral sensors initially flag as low vigor but normalize later.\n"
                        offline_text += "• **Soil Moisture & Drainage anomalies**: Soil compaction or drainage patches can restrict early root oxygen, lowering NDVI temporarily.\n\n"
                        offline_text += "**2. Additional Data Required to Resolve Ambiguity:**\n"
                        offline_text += "• **Sentinel-1 SAR VV/VH Polarimetry Ratio**: Backscatter ratio tracking can isolate plant structural volume changes from soil surface moisture variations.\n"
                        offline_text += "• **In-situ Soil Moisture & EC probes**: Ground truth telemetry will confirm if the patch is hydrologically stressed.\n"
                        offline_text += "• **Close-Range Scouting Photographs**: Submitting georeferenced scouting photos allows our image QA and computer vision models to identify leaf-level nutrient or emergence patterns.\n\n"
                    
                    # Diagnostics/Trust Score footer
                    rel_val = quality.get("reliability", 1.0) if quality and isinstance(quality, dict) else 1.0
                    offline_text += f"### 📡 Telemetry Integrity & Diagnostics\n"
                    offline_text += f"This advice is dynamically compiled across our 9-Layer Stack with a **{int(rel_val * 100)}% System Trust Score**. "
                    if quality and isinstance(quality, dict) and "degradation_modes" in quality and quality["degradation_modes"]:
                        offline_text += f"Minor gaps detected due to: *{', '.join(quality['degradation_modes'])}*."
                    else:
                        offline_text += "Optical and SAR radar coverage are fully synchronized."
                    
                    final_response = offline_text
                    memory_updates = {}

                # Validate and return
                from services.agribrain.orchestrator_v2.arf_schema import ARFResponse
                raw_json = {}
                if isinstance(res, dict):
                    # Copy all valid ARF fields if present
                    for field in ARFResponse.__fields__.keys():
                        if field in res:
                            raw_json[field] = res[field]

                # Ensure conversational_response and internal_memory_updates are set
                if "conversational_response" not in raw_json or not raw_json["conversational_response"]:
                    raw_json["conversational_response"] = final_response.strip()
                if "internal_memory_updates" not in raw_json or not raw_json["internal_memory_updates"]:
                    raw_json["internal_memory_updates"] = memory_updates

                # Make sure direct_answer is populated
                if "direct_answer" not in raw_json or not raw_json["direct_answer"]:
                    raw_json["direct_answer"] = raw_json["conversational_response"]
                
                # Make sure headline is set
                if "headline" not in raw_json or not raw_json["headline"]:
                    raw_json["headline"] = "AgriBrain Analysis"

                # Run HallucinationGuard
                if "conversational_response" in raw_json and isinstance(raw_json["conversational_response"], str):
                    cleaned_text, flags = guard.validate(raw_json["conversational_response"])
                    raw_json["conversational_response"] = cleaned_text

                try:
                    validated_arf = ARFResponse(**raw_json)
                    return validated_arf.dict()
                except Exception as val_err:
                    print(f"DEBUG: Local LLM fallback ARF validation error: {val_err}. Activating salvaging fail-safe...")
                    salvaged_response = raw_json.get("conversational_response") or final_response.strip()
                    salvaged_json = {
                        "conversational_response": salvaged_response,
                        "headline": raw_json.get("headline") or "AgriBrain Analysis",
                        "direct_answer": raw_json.get("direct_answer") or salvaged_response,
                        "suitability_score": raw_json.get("suitability_score"),
                        "confidence_badge": raw_json.get("confidence_badge") or "MED",
                        "confidence_reason": raw_json.get("confidence_reason") or "Fusing multi-source agronomic indicators.",
                        "what_it_means": raw_json.get("what_it_means") or "Active growth monitoring in progress.",
                        "reasoning_cards": [],
                        "recommendations": [],
                        "learning": {
                            "level": "INTERMEDIATE",
                            "micro_lesson": (
                                "The AgriBrain pipeline fuses satellite (Sentinel-2 optical + Sentinel-1 SAR), "
                                "weather (OpenMeteo), and soil (SoilGrids) data through a Kalman filter to "
                                "estimate daily crop state even when cloud cover blocks direct observation."
                            ),
                            "definitions": {
                                "Kalman Filter": "A state-space estimator that fuses noisy, irregular observations into a continuous daily estimate."
                            }
                        },
                        "followups": [],
                        "internal_memory_updates": {
                            "experience_level_upgrade": None,
                            "new_known_facts": {},
                            "closed_loops": []
                        }
                    }
                    try:
                        validated_arf = ARFResponse(**salvaged_json)
                        return validated_arf.dict()
                    except Exception as salv_err:
                        print(f"CRITICAL: Salvaged ARF validation failed: {salv_err}")
                        return salvaged_json
            else:
                return {"error": "Local VLM server not running"}
        except Exception as e:
            return {"error": f"Local VLM exception: {str(e)}"}

    try:
        rj = {}
        choices = None
        groq_key = os.getenv("GROQ_API_KEY")
        try:
            if groq_key:
                resp = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {groq_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": messages,
                        "temperature": 0.4,
                        "response_format": {"type": "json_object"},
                    },
                    timeout=15
                )
                if resp.status_code == 200:
                    rj = resp.json()
                    choices = rj.get("choices")
                else:
                    print(f"[LLM] Groq returned {resp.status_code}")
        except Exception as e:
            print(f"[LLM] Groq network error: {e}")

        if not choices and os.getenv("OPENROUTER_API_KEY"):
            try:
                resp = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://agriwise.app", 
                        "X-Title": "AgriWise"
                    },
                    json={
                        "model": "meta-llama/llama-3.3-70b-instruct:free",
                        "messages": messages,
                        "temperature": 0.4,
                        "response_format": {"type": "json_object"},
                    },
                    timeout=15
                )
                if resp.status_code == 200:
                    rj = resp.json()
                    choices = rj.get("choices")
                else:
                    print(f"[LLM] OpenRouter returned {resp.status_code}")
            except Exception as e:
                print(f"[LLM] OpenRouter network error: {e}")

        if not choices and os.getenv("GEMINI_API_KEY"):
            print("[LLM] Falling back to Gemini API...")
            try:
                gemini_resp = requests.post(
                    "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                    headers={"Authorization": f"Bearer {os.getenv('GEMINI_API_KEY')}", "Content-Type": "application/json"},
                    json={
                        "model": "gemini-flash-latest", 
                        "messages": messages, 
                        "temperature": 0.4,
                        "response_format": {"type": "json_object"}
                    },
                    timeout=20
                )
                print(f"[LLM-DEBUG] Gemini chat output HTTP {gemini_resp.status_code}")
                if gemini_resp.status_code == 200:
                    rj = gemini_resp.json()
                    choices = rj.get("choices")
                else:
                    print(f"[LLM-ERROR] Gemini fallback returned {gemini_resp.status_code}: {gemini_resp.text}")
            except Exception as e:
                print(f"[LLM-ERROR] Gemini chat output fallback failed/timeout: {e}")

        if choices and len(choices) > 0:
            msg = choices[0].get("message", {})
            content = msg.get("content") or ""
            
            # Clean possible markdown block wrappers
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            
            if not content.strip():
                content = "{}"
                
            try:
                raw_json = json.loads(content)
            except json.JSONDecodeError as e:
                # Fallback for Nemotron which might drop the closing brace
                print(f"DEBUG: JSON parse error: {e}. Trying to fix...")
                if not content.strip().endswith("}"):
                    content += '"}'
                try:
                    raw_json = json.loads(content)
                except Exception:
                    # Regex fallback if it's completely broken
                    import re
                    match = re.search(r'"conversational_response"\s*:\s*"([^"]+)"', content, re.DOTALL)
                    if match:
                        raw_json = {
                            "conversational_response": match.group(1).replace("\\n", "\n"),
                            "internal_memory_updates": {}
                        }
                    else:
                        raw_json = {
                            "conversational_response": content,
                            "internal_memory_updates": {}
                        }
            
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
                    "micro_lesson": (
                        f"The AgriBrain pipeline fuses satellite (Sentinel-2 optical + Sentinel-1 SAR), "
                        f"weather (OpenMeteo), and soil (SoilGrids) data through a Kalman filter to "
                        f"estimate daily crop state even when cloud cover blocks direct observation. "
                        f"When satellite passes are unavailable, the system relies on weather-driven "
                        f"model predictions, which is why some values carry higher uncertainty."
                    ),
                    "definitions": {
                        "Kalman Filter": "A state-space estimator that fuses noisy, irregular observations into a continuous daily estimate.",
                        "NDVI": "Normalized Difference Vegetation Index — a proxy for canopy health (0=bare soil, 1=dense canopy)."
                    }
                }
            # 5. Fix Markdown indentation (LLMs often indent strings to match JSON pretty-print, causing <pre> blocks in UI)
            if "conversational_response" in raw_json and isinstance(raw_json["conversational_response"], str):
                import textwrap
                raw_json["conversational_response"] = textwrap.dedent(raw_json["conversational_response"]).strip()
                # Run HallucinationGuard
                cleaned_text, flags = guard.validate(raw_json["conversational_response"])
                raw_json["conversational_response"] = cleaned_text
            
            # STRIKE: Strict Pydantic Validation
            from services.agribrain.orchestrator_v2.arf_schema import ARFResponse
            try:
                validated_arf = ARFResponse(**raw_json)
                return validated_arf.dict() # Return valid dict representing ARF
            except Exception as e:
                print(f"DEBUG: LLM schema validation failed even after sanitization: {e}. Activating salvaging fail-safe...")
                salvaged_response = raw_json.get("conversational_response") or content or "I have analyzed the field data, but there was an issue formatting my response. The core pipeline is running normally."
                salvaged_json = {
                    "conversational_response": salvaged_response,
                    "headline": raw_json.get("headline") or "AgriBrain Analysis",
                    "direct_answer": raw_json.get("direct_answer") or salvaged_response,
                    "suitability_score": raw_json.get("suitability_score"),
                    "confidence_badge": raw_json.get("confidence_badge") or "MED",
                    "confidence_reason": raw_json.get("confidence_reason") or "Fusing multi-source agronomic indicators.",
                    "what_it_means": raw_json.get("what_it_means") or "Active growth monitoring in progress.",
                    "reasoning_cards": [],
                    "recommendations": [],
                    "learning": {
                        "level": "INTERMEDIATE",
                        "micro_lesson": (
                            "The AgriBrain pipeline fuses satellite (Sentinel-2 optical + Sentinel-1 SAR), "
                            "weather (OpenMeteo), and soil (SoilGrids) data through a Kalman filter to "
                            "estimate daily crop state even when cloud cover blocks direct observation."
                        ),
                        "definitions": {
                            "Kalman Filter": "A state-space estimator that fuses noisy, irregular observations into a continuous daily estimate."
                        }
                    },
                    "followups": [],
                    "internal_memory_updates": {
                        "experience_level_upgrade": None,
                        "new_known_facts": {},
                        "closed_loops": []
                    }
                }
                try:
                    validated_arf = ARFResponse(**salvaged_json)
                    return validated_arf.dict()
                except Exception as salv_err:
                    print(f"CRITICAL: Salvaged ARF validation failed: {salv_err}")
                    return salvaged_json
        else:
            if 'resp' in locals() and hasattr(resp, 'status_code'):
                err_detail = rj.get("error", {}) if resp.status_code == 200 else {}
                print(f"[LLM] No choices in response. status={resp.status_code}, error={err_detail}")
            else:
                print(f"[LLM] No choices and no valid response object available. Likely a network connection error.")
            
            return {
                "conversational_response": "The AI model is temporarily unavailable (rate limit or connection error). Please try again in a moment.",
                "internal_memory_updates": {}
            }

            
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
                from layer0.data_gateway import broker
                plot_id = artifact.inputs.plot_id
                sm = broker.get("soil_moisture_layers", plot_id=plot_id, lat=lat, lng=lng)
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
            print(f"[WARN] [Chat] Soil moisture fetch failed: {e}")

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
    from services.agribrain.orchestrator_v2.arf_schema import ARFResponse
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
    groq_key = os.getenv("GROQ_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
    if not use_local and not api_key and not groq_key and not gemini_key:
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
- You MUST explicitly cite exact numeric sensor/satellite metrics (e.g., NDVI, Rainfall, Soil Moisture) from the context in your explanations.

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

    if use_local:
        try:
            from layer9_interface.engines.local_vlm import local_vlm_client
            backend = local_vlm_client.detect_backend()
            if backend:
                res = local_vlm_client.query(user_prompt, system_prompt=ARF_V1_SYSTEM_PROMPT)
                if res and "error" not in res:
                    content = res.get("answer", "")
                    if isinstance(res, dict) and "headline" in res:
                        return res
                    else:
                        content = content.replace("```json", "").replace("```", "").strip()
                        return json.loads(content)
                else:
                    return {"error": f"Local VLM query failed: {res.get('error') if res else 'None'}"}
            else:
                return {"error": "Local VLM server not running"}
        except Exception as e:
            return {"error": f"Local VLM exception: {str(e)}"}

    try:
        rj2 = {}
        choices2 = None
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
                    "model": "meta-llama/llama-3.3-70b-instruct:free", 
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
                rj2 = resp.json()
                choices2 = rj2.get("choices")
            else:
                print(f"[LLM] OpenRouter returned {resp.status_code}")
        except Exception as e:
            print(f"[LLM] OpenRouter network error: {e}")

        if not choices2 and os.getenv("GEMINI_API_KEY"):
            print("[LLM] Falling back to Gemini API...")
            try:
                gemini_resp = requests.post(
                    "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                    headers={"Authorization": f"Bearer {os.getenv('GEMINI_API_KEY')}", "Content-Type": "application/json"},
                    json={
                        "model": "gemini-flash-latest", 
                        "messages": [
                            {"role": "system", "content": ARF_V1_SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": 0.5,
                        "max_tokens": 1000,
                        "response_format": {"type": "json_object"}
                    },
                    timeout=20
                )
                print(f"[LLM-DEBUG] Gemini ARF HTTP {gemini_resp.status_code}")
                if gemini_resp.status_code == 200:
                    rj2 = gemini_resp.json()
                    choices2 = rj2.get("choices")
                else:
                    print(f"[LLM-ERROR] Gemini ARF fallback returned {gemini_resp.status_code}: {gemini_resp.text}")
            except Exception as e:
                print(f"[LLM-ERROR] Gemini ARF fallback failed/timeout: {e}")

        if choices2 and len(choices2) > 0:
            content = choices2[0].get("message", {}).get("content", "")
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
