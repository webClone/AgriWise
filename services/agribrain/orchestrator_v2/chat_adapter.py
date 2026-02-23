
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
    data_inventory: Dict[str, str] = field(default_factory=dict) # ✅/⚠️/❌ summary

from services.agribrain.orchestrator_v2.intents import Intent

def build_chat_payload(
    artifact: RunArtifact, 
    user_query: Optional[str] = None,
    intent: Intent = Intent.DECISION
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
                 summary["planning_context"] = {
                     "crop": chosen_opt.crop,
                     "overall_score": chosen_opt.overall_rank_score,
                     "window_prob": chosen_opt.window.probability_ok,
                     "water_prob": getattr(chosen_opt.water, "probability_ok", 0.0),
                     "biotic_prob": getattr(chosen_opt.biotic, "probability_ok", 0.0),
                     "expected_yield": chosen_opt.yield_dist.mean,
                     "downside_risk_p10": chosen_opt.yield_dist.p10,
                     "expected_profit": chosen_opt.econ.expected_profit
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
        quality=quality_summary
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
             snapshot["soil_ph"] = static_props.get("soil_ph_mean", "N/A")
             snapshot["soil_soc"] = static_props.get("soil_org_c_mean", "N/A")

    summary["feature_snapshot"] = snapshot

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
    quality: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Calls OpenRouter to generate ARF-v2 strict JSON response.
    """
    import os
    import requests
    import json
    
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
    if mode == "PLANNING" and "planning_context" in summary:
        p_ctx = summary["planning_context"]
        planning_str = f"""
    [PLANNING FEASIBILITY & ECONOMICS] (PRIMARY FOCUS)
    - Target Crop: {p_ctx.get('crop')}
    - Overall Suitability Score: {p_ctx.get('overall_score', 0):.2f}
    - Window Probability: {p_ctx.get('window_prob', 0):.2f}
    - Water Probability: {p_ctx.get('water_prob', 0):.2f}
    - Biotic Probability: {p_ctx.get('biotic_prob', 0):.2f}
    - Yield Potential (Mean): {p_ctx.get('expected_yield', 0):.1f} t/ha
    - Yield Risk (p10): {p_ctx.get('downside_risk_p10', 0):.1f} t/ha
    - Expected Profit: ${p_ctx.get('expected_profit', 0):.1f}
        """

    context_str = f"""
    {planning_str}
    
    [FIELD CONTEXT] (SECONDARY CONSTRAINTS)
    - Stage: {summary.get('stage')}
    - Signals: {json.dumps(summary.get('key_signals', []))}
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
    3. If Quality Issues include NO_SAR or PARTIAL_DATA, shift to VERIFY actions and explain uncertainty (UNLESS Assistant Mode is PLANNING; for PLANNING, proceed with the Execution Plan Tasks as requested and ignore missing data warnings unless critical).
    4. Provide contextual follow-up questions but DO NOT repeat 'Recent Follow-ups Asked'.
    5. VERY IMPORTANT: If Assistant Mode is PLANNING, do NOT act like a diagnostic monitor. Act like a Season Feasibility Optimizer. Your `headline` MUST be a Decision (e.g., "Planting Decision: Conditional"). Your `direct_answer` MUST state the quantitative expected yield and feasibility score. Your `reasoning_cards` MUST explain the specific water/biotic probabilities. Do NOT focus the narrative on NO_SAR.
    6. STRICTLY NO SPAM / NO DUPLICATION: DO NOT output all available Execution Plan Tasks or Proposed Actions. ONLY select 1-3 recommendations that are DIRECTLY RELEVANT to the user's specific query.
    
    RESPONSE JSON SCHEMA:
    {{
        "headline": "1 sentence title summarizing field status",
        "direct_answer": "Direct answer to user's specific question",
        "reliability_badge": "HIGH" | "MED" | "LOW",
        "reliability_reason": "Why the badge is what it is (e.g., 'Missing SAR data')",
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
                "title": "Action title (ONLY include 1-3 actions directly relevant to the query)",
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
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
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
            
            # STRIKE: Strict Pydantic Validation
            from services.agribrain.orchestrator_v2.arf_schema import ARFResponse
            validated_arf = ARFResponse(**raw_json)
            
            return validated_arf.dict() # Return valid dict representing ARF
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
    simplified payload for pure data queries. No diagnoses, no actions.
    """
    # 1. Extract Signals form L1 (Raw)
    signals = []
    
    summary = {
        "headline": "Data Retrieval Complete",
        "period": f"{artifact.inputs.date_range['start']} to {artifact.inputs.date_range['end']}",
        "stage": "OBSERVATIONAL", # No L2
        "key_signals": []
    }
    
    if artifact.layer_1 and artifact.layer_1.output:
        ts = getattr(artifact.layer_1.output, "plot_timeseries", [])
        if ts:
            # RAIN: Sum EVERYTHING in the returned time series (which matches resolved date range)
            rain_sum = sum(float(r.get("rain", 0.0) or 0.0) for r in ts)
            signals.append(ChatSignal(
                name="Rainfall (Total)", 
                value=f"{rain_sum:.1f} mm", 
                direction=SignalDirection.NORMAL
            ))
            
            # RAIN DAYS
            rain_days = sum(1 for r in ts if float(r.get("rain", 0.0) or 0.0) > 0.1)
            signals.append(ChatSignal("Days with Rain", str(rain_days), SignalDirection.NORMAL))
            
            # NDVI (Avg of last if available)
            # Check last valid
            ndvis = [float(r.get("ndvi")) for r in ts if r.get("ndvi") is not None]
            if ndvis:
                signals.append(ChatSignal("Avg NDVI", f"{sum(ndvis)/len(ndvis):.2f}", SignalDirection.NORMAL))
                
    summary["key_signals"] = [s.__dict__ for s in signals]
    
    # Generate simple explanation (Tutor Style)
    # 4 Layers: Answer, Meaning, Evidence, Teach
    
    # Interpretation Logic
    rain_val = float(summary.get("key_signals", [{}])[0].get("value", "0").split(" ")[0])
    days_count = int(summary.get("key_signals", [{}])[1].get("value", "0"))
    period_days = 30 # Approx def
    try:
        start = datetime.strptime(artifact.inputs.date_range['start'], "%Y-%m-%d")
        end = datetime.strptime(artifact.inputs.date_range['end'], "%Y-%m-%d")
        period_days = (end - start).days + 1
    except:
        pass
        
    avg_weekly = (rain_val / period_days) * 7 if period_days > 0 else 0
    
    interpretation = "This is within the normal seasonal range."
    if avg_weekly < 10:
        interpretation = "This is below the typical 25mm/week threshold for many crops, suggesting potential dryness."
    elif avg_weekly > 50:
        interpretation = "This is substantial rainfall, likely refilling the soil profile but increasing fungal risk."
        
    # Teaching
    teaching = "Rule of thumb: 25-35 mm/week often maintains crops in mid-season, though sandy soils drain faster."
    
    # Construct Narrative
    narrative = f"During this period ({artifact.inputs.date_range['start']} to {artifact.inputs.date_range['end']}), your field received {rain_val:.1f} mm of rainfall over {days_count} wet days.\n\n"
    narrative += f"**What it means**: {interpretation}\n\n"
    narrative += f"**Why**: Data from Layer 1 Weather Aggregation shows {days_count} precipitation events.\n\n"
    narrative += f"**Quick Lesson**: {teaching}"
    
    summary["explanation"] = narrative
    summary["headline"] = _extract_headline(narrative) # Likely "Field Received X mm"
    
    # Feature Snapshot
    snapshot = {}
    if artifact.layer_1 and artifact.layer_1.output:
        ts = getattr(artifact.layer_1.output, "plot_timeseries", [])
        if ts and ts:
             snapshot["rain_total"] = rain_val
    summary["feature_snapshot"] = snapshot

    # Context Question
    ctx_q = _select_context_question(artifact.inputs, artifact.global_quality)
    if ctx_q:
        questions_for_user = [ctx_q]
    else:
        questions_for_user = []
        
    arf = {
        "headline": summary["headline"],
        "direct_answer": narrative, # Using narrative as direct answer for simple data queries
        "reliability_badge": "HIGH",
        "reliability_reason": "Based directly on verifiable deterministic telemetry and local station data.",
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
    
    # Validate through Schema to guarantee compliance
    from services.agribrain.orchestrator_v2.arf_schema import ARFResponse
    arf = ARFResponse(**arf).dict()

    return ChatPayload(
        run_id=artifact.meta.orchestrator_run_id,
        global_quality={"reliability": 1.0, "degradation_modes": [], "alerts": []},
        summary=summary,
        diagnoses=[], # STRICTLY EMPTY
        actions=[],   # STRICTLY EMPTY
        plan={"tasks": []}, # STRICTLY EMPTY
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
