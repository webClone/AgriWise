
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

from services.agribrain.orchestrator_v2.schema import RunArtifact, GlobalDegradation

@dataclass
class ChatSignal:
    name: str
    value: str
    direction: str # "LOW", "HIGH", "STABLE", "NEGATIVE"

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
    context_question: Optional[str] = None
    structured_response: Optional[Dict[str, Any]] = None # ARF-v1 JSON Output
    memory_context: Dict[str, Any] = field(default_factory=dict) # Snapshot of what LLM knew
    visuals: List[ChatVisual] = field(default_factory=list) # Rich charts

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
            signals.append(ChatSignal("Rain (14d)", f"{rain_sum:.1f} mm", "LOW" if rain_sum < 10 else "NORMAL"))
            
    # L2: NDVI
    if artifact.layer_2 and artifact.layer_2.output:
        pheno = getattr(artifact.layer_2.output, "phenology", None)
        stage = "UNKNOWN"
        if pheno and pheno.stage_by_day:
            stage = pheno.stage_by_day[-1]
            
        curve = getattr(artifact.layer_2.output, "curve", None)
        trend = "STABLE"
        if curve and curve.ndvi_fit_d1:
            last_d1 = curve.ndvi_fit_d1[-1]
            if last_d1 > 0.01: trend = "POSITIVE"
            elif last_d1 < -0.01: trend = "NEGATIVE"
            
        signals.append(ChatSignal("NDVI Trend", trend, trend))
        
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
    
    if artifact.final_execution_plan:
        for t in artifact.final_execution_plan.tasks:
            tasks.append(ChatTask(
                task=f"{t.type}: {t.instructions}",
                when="Pending",
                depends_on=t.depends_on
            ))
            
    # Actions mostly come from L3 policy or L5 recommnedations
    # We can extract them from the plan implicitly or from layer outputs
    # For now, simplistic extraction from plan tasks
    seen_actions = set()
    for t in tasks:
        key = t.task.split(":")[0]
        if key not in seen_actions:
            actions.append(ChatAction(
                title=t.task,
                priority="HIGH", # infer
                is_allowed=True,
                why=[]
            ))
            seen_actions.add(key)

    # 5. Assistant Mode Logic & Thresholding
    
    # Threshold Gating: Only surface certain stressors
    high_impact_diags = [d for d in diags if d.prob > 0.6 and d.conf > 0.6]
    low_impact_diags = [d for d in diags if d not in high_impact_diags]
    
    # Refine Assistant Mode (Intent vs Reality)
    mode = assistant_mode
    
    # Degradation Overrides
    reliability = quality_summary["reliability"]
    has_datagap = "NO_SAR" in quality_summary["degradation_modes"] or "PARTIAL_DATA" in quality_summary["degradation_modes"]
    has_intervene = any(a.title.startswith("INTERVENE") for a in actions)
    has_verify = any(a.title.startswith("VERIFY") for a in actions)
    
    # DATA_GAP should NOT be primary headline unless reliability is critical
    if reliability < 0.6 and has_datagap and mode != "DATA_ONLY":
        mode = "DATA_GAP"
    elif has_intervene and mode == "MONITORING":
        mode = "ADVISORY"
    elif has_verify and mode == "MONITORING":
        mode = "VERIFY_REQUIRED"
    
    # If we have NO high impact diags and NO forced mode, keep it MONITORING even if low diags exist
    
    # 6. Memory Integration & ARF-v1
    from services.agribrain.memory.store import MemoryStore
    store = MemoryStore()
    
    # IDs
    plot_id = artifact.inputs.plot_id
    conversation_id = getattr(artifact.meta, "conversation_id", "local_dev_session") 
    
    # Load Context
    profile = store.get_profile(plot_id)
    session = store.get_session(conversation_id)
    
    memory_context = {
        "profile": profile,
        "session_summary": session.get("summary", ""),
        "last_turns": session.get("turns", [])[-3:] # Last 3 turns
    }
    
    # Generate ARF-v1 Response - Pass FILTERED diags as primary
    arf_json = _generate_llm_answer_arf_v1(
        summary=summary,
        diags=high_impact_diags, # Only show high-certainty ones in main narrative
        actions=actions,
        tasks=tasks,
        memory_context=memory_context,
        user_query=user_query,
        mode=mode
    )
    
    # Add low-impact to limitations if ARF succeeded
    if "error" not in arf_json:
        if low_impact_diags:
            arf_json.setdefault("limitations", []).append(
                f"Low-probability indicators: {', '.join(d.id for d in low_impact_diags)} (p<0.6 or c<0.6)"
            )
        if has_datagap and mode != "DATA_GAP":
            arf_json.setdefault("limitations", []).append("Limited SAR coverage; assessing via optical/weather proxies.")
    
    # Fallback if ARF failed
    if "error" in arf_json:
        explanation = f"Analysis complete. (System Note: {arf_json['error']})"
        summary["explanation"] = explanation
        summary["headline"] = "System Notification"
    else:
        # Construct Markdown from ARF JSON
        # Headline
        headline = arf_json.get("headline", "Field Analysis")
        summary["headline"] = headline
        
        # Narrative
        md = f"**{arf_json.get('direct_answer', 'Analysis Complete')}**\n\n"
        md += f"**What it means**: {arf_json.get('what_it_means', '')}\n\n"
        
        if arf_json.get("evidence"):
            md += "**Evidence**:\n"
            for ev in arf_json["evidence"]:
                md += f"- {ev.get('signal')}: {ev.get('value')} ({ev.get('interpretation')})\n"
            md += "\n"
            
        if arf_json.get("teaching_note"):
            md += f"**Quick Lesson**: {arf_json['teaching_note']}\n"
            
        explanation = md
        summary["explanation"] = explanation
        
        # Persist Turn
        store.append_turn(conversation_id, user_query or "Status Update", arf_json)

    # 7. Feature Snapshot (Visual Debugging)
    snapshot = {}
    if artifact.layer_1 and artifact.layer_1.output:
        ts = getattr(artifact.layer_1.output, "plot_timeseries", [])
        if ts:
             last = ts[-1]
             snapshot["rain_14d"] = summary.get("key_signals", [{}])[0].get("value", "N/A")
             snapshot["soil_moisture"] = last.get("soil_moisture_proxy", "N/A")
             snapshot["sar_vv"] = last.get("vv", "N/A")

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
        context_question=None, # Deprecated
        structured_response=arf_json,
        memory_context=memory_context,
        visuals=visuals
    )

def _generate_llm_explanation(
    summary: Dict, 
    diags: List[ChatDiagnosis], 
    actions: List[ChatAction], 
    tasks: List[ChatTask],
    user_query: Optional[str] = None,
    mode: str = "MONITORING"
) -> str:
    """
    Calls OpenRouter to generate a user-friendly explanation.
    """
    import os
    import requests
    import json
    
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return "Analysis complete. (LLM Key missing)"

    # Safety Guard: If DATA_GAP, remove Interventions from context
    safe_actions = actions
    if mode == "DATA_GAP":
        safe_actions = [a for a in actions if "INTERVENE" not in a.title]

    # Adaptive Depth
    depth_instr = "Provide a structured agronomic explanation."
    if user_query and len(user_query.split()) < 5:
        depth_instr = "Provide a concise but educational explanation."

    # Construct Context (Hidden State)
    # Format Diagnoses to show Prob vs Conf
    diag_str = []
    for d in diags:
        diag_str.append(f"{d.id} (Prob: {d.prob:.2f}, Conf: {d.conf:.2f})")
        
    context_str = f"""
    [FIELD STATUS]
    - Stage: {summary.get('stage')}
    - Signals: {json.dumps(summary.get('key_signals', []))}
    - Diagnoses: {diag_str}
    - Actions: {[a.title for a in safe_actions]}
    - Pending Tasks: {len(tasks)}
    [END FIELD STATUS]
    """
    
    system_prompt = f"""
    You are AgriBrain, an expert agronomist and intelligent farming assistant.
    
    Your Capabilities:
    1. **Field Analysis**: You have access to real-time satellite/sensor data for the user's field (provided in [FIELD STATUS]). Use this ONLY when the user asks about *their* field.
    2. **General Knowledge**: You are a world-class expert on agronomy.
    
    Current Field Data (Hidden from user):
    {context_str}
    
    Guidelines:
    - **Structure your response in 4 layers**:
      1. **Direct Answer**: Short, precise response to the user's question.
      2. **Agronomic Meaning**: What does this mean strictly biologically?
      3. **Evidence**: Which signals (Rain, NDVI, etc.) triggered this?
      4. **Quick Lesson**: A general agronomy rule or principle (e.g., "Fungal pathogens require moisture duration...").
    
    - **Probability vs Confidence**: If diagnosing, explain that Probability is the likelihood of the stress, while Confidence reflects data quality/completeness.
    - **Expert Tone**: Professional but accessible.
    - {depth_instr}
    """
    
    user_prompt = user_query if user_query else "Provide a brief status update for my field."
    
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
                "temperature": 0.7,
                # Increased limit for structured explanation
                "max_tokens": 600
            },
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        else:
            return f"Analysis complete. (AI unavailable: {resp.status_code})"
            
    except Exception as e:
        print(f"DEBUG: LLM Error: {e}")
        fallback = f"Analysis complete based on stored data. (LLM Unavailable: {str(e)})"
        return fallback

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
                direction="NORMAL" # We don't have L2/L3 to judge 'normal', maybe omit? Or simple heuristic?
            ))
            
            # RAIN DAYS
            rain_days = sum(1 for r in ts if float(r.get("rain", 0.0) or 0.0) > 0.1)
            signals.append(ChatSignal("Days with Rain", str(rain_days), "N/A"))
            
            # NDVI (Avg of last if available)
            # Check last valid
            ndvis = [float(r.get("ndvi")) for r in ts if r.get("ndvi") is not None]
            if ndvis:
                signals.append(ChatSignal("Avg NDVI", f"{sum(ndvis)/len(ndvis):.2f}", "N/A"))
                
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
        questions_for_user=[],
        context_question=ctx_q
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
