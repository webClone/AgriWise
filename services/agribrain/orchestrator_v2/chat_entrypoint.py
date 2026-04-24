
import sys
import json
import argparse
from datetime import datetime, timedelta

# Fix path to allow importing services
import os
sys.path.insert(0, os.getcwd())

from services.agribrain.orchestrator_v2.runner import run_for_chat
from services.agribrain.orchestrator_v2.schema import OrchestratorInput
from services.agribrain.orchestrator_v2.chat_adapter import ChatPayload

from dotenv import load_dotenv
load_dotenv()

def main():
    parser = argparse.ArgumentParser(description="Orchestrator v2 Chat Entrypoint")
    parser.add_argument("--context", type=str, required=True, help="JSON context from Node.js")
    parser.add_argument("--query", type=str, help="User query (unused by strict orchestrator, but kept for compat)")
    parser.add_argument("--history", type=str, default="", help="Base64-encoded chat history for multi-turn memory")
    parser.add_argument("--exp", type=str, default="INTERMEDIATE", help="Farmer experience level")
    parser.add_argument("--cid", type=str, default="local_dev_session", help="Conversation ID")
    
    args = parser.parse_args()
    
    try:
        import base64
        try:
            decoded = base64.b64decode(args.context).decode('utf-8')
            ctx = json.loads(decoded)
        except Exception:
            ctx = json.loads(args.context)
        from services.agribrain.orchestrator_v2.intents import detect_intent, Intent
        
        query_text = args.query.strip() if args.query else ""
        plot_id_early = ctx.get("plot_id", "UNKNOWN")
        intent = detect_intent(query_text, has_context=(plot_id_early != "UNKNOWN"))
        
        if intent == Intent.GREETING:
            # 0. Early Exit for Greetings (Do not run Orchestrator)
            from services.agribrain.orchestrator_v2.chat_adapter import ChatPayload
            from services.agribrain.orchestrator_v2.arf_schema import ARFResponse, LearningModule
            
            arf = ARFResponse(
                headline="Hi 👋 I am AgriBrain.",
                direct_answer="I can help with crop health, irrigation decisions, pests/disease risk, and rainfall summaries.",
                suitability_score="N/A",
                confidence_badge="HIGH",
                confidence_reason="System online.",
                what_it_means="I am ready to analyze your field data context.",
                reasoning_cards=[],
                recommendations=[],
                learning=LearningModule(
                    level=args.exp,
                    micro_lesson="You can check specific things like 'show me rainfall', 'check fungal risk', or 'irrigation needs'.",
                    definitions={}
                ),
                followups=[],
                internal_memory_updates=None
            ).dict()

            payload = ChatPayload(
                run_id="GREETING_ONLY",
                global_quality={"reliability": 1.0, "degradation_modes": [], "alerts": []},
                summary={"headline": "AgriBrain Online", "explanation": "Ready."},
                diagnoses=[], 
                actions=[],   
                plan={"tasks": []}, 
                citations=[],
                assistant_mode="WELCOME",
                assistant_style="TUTOR",
                questions_for_user=["What do you want to check today: field status, rain last 30 days, irrigation need, or disease pressure?"],
                arf=arf,
                memory={"experience_level": args.exp, "known_context": {}, "open_loops": []},
                ui_hints={"show_reliability_banner": False, "show_blocked_banner": False, "card_ordering": []},
                visuals=[]
            )
            print(json.dumps(payload, default=lambda o: o.__dict__, indent=2))
            sys.exit(0)
            
        if intent == Intent.GENERAL:
            # 0.5 Early Exit for General Agronomy (LLM only, no orchestrator)
            from services.agribrain.orchestrator_v2.chat_adapter import ChatPayload
            import os
            
            # Create a mock summary for context
            mock_summary = {
                "headline": "Agronomy Knowledge",
                "explanation": "General agronomic information requested."
            }
            
            # Load memory to get experience level
            plot_id = ctx.get("plot_id", "UNKNOWN")
            exp_level = args.exp
            mem = None
            if plot_id != "UNKNOWN":
                from services.agribrain.orchestrator_v2.chat_memory import load_memory
                mem = load_memory(plot_id)
                exp_level = mem.experience_level
                
            API_KEY = os.getenv("OPENROUTER_API_KEY")

            prompt = f"User asked a general agronomic question: '{query_text}'. Provide a conceptual explanation. Do not hallucinate field data. If they ask about their field, remind them to provide context."
            
            if API_KEY:
                # We can reuse the arf generator. We pass empty actions and diags.
                import requests
                sys_prompt = f"""
                You are AgriBrain, an expert agronomist + teacher.
                The user has asked a General Knowledge question. Do not assume any specific field context.
                Adapt teaching depth to Farmer Experience Level: {exp_level}.
                Respond ONLY in valid JSON matching the schema below.
                
                RESPONSE JSON SCHEMA:
                {{
                    "headline": "Brief title of the topic",
                    "direct_answer": "Clear, direct answer to the user's question",
                    "suitability_score": "N/A",
                    "confidence_badge": "HIGH",
                    "confidence_reason": "General established agronomic knowledge",
                    "what_it_means": "Why this concept is important in farming",
                    "reasoning_cards": [],
                    "recommendations": [
                        {
                            "type": "MONITOR",
                            "title": "Application of this concept",
                            "is_allowed": true,
                            "blocked_reasons": [],
                            "why_it_matters": "Why applying this concept matters",
                            "how_to_do_it_steps": ["Step 1", "Step 2"],
                            "risk_if_wrong": "LOW"
                        }
                    ],
                    "learning": {{
                        "level": "{exp_level}",
                        "micro_lesson": "A detailed explanation of the concept tailored to their level.",
                        "definitions": {{"Term": "Meaning"}}
                    }},
                    "followups": [{{"question": "Ask if they want to apply this to their specific field", "why": "Context discovery"}}],
                    "internal_memory_updates": null
                }}
                """
                
                try:
                    resp = requests.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {API_KEY}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://agriwise.app", 
                            "X-Title": "AgriWise"
                        },
                        json={
                            "model": "qwen/qwen-2.5-72b-instruct", 
                            "messages": [
                                {"role": "system", "content": sys_prompt},
                                {"role": "user", "content": prompt}
                            ],
                            "temperature": 0.3, 
                            "response_format": {"type": "json_object"}
                        },
                        timeout=15
                    )
                    raw_json = json.loads(resp.json()["choices"][0]["message"]["content"].strip().replace('```json', '').replace('```', ''))
                    
                    from services.agribrain.orchestrator_v2.arf_schema import ARFResponse
                    arf_dict = ARFResponse(**raw_json).dict()
                except Exception as e:
                    arf_dict = {"error": f"LLM Failure: {str(e)}"}
            else:
                 arf_dict = {"error": "No API Key"}

            payload = ChatPayload(
                run_id="GENERAL_KNOWLEDGE",
                global_quality={"reliability": 1.0, "degradation_modes": [], "alerts": []},
                summary=mock_summary,
                diagnoses=[], 
                actions=[],   
                plan={"tasks": []}, 
                citations=[],
                assistant_mode="GENERAL",
                assistant_style="TUTOR",
                questions_for_user=[],
                arf=arf_dict,
                memory={"experience_level": exp_level, "known_context": {}, "open_loops": []},
                ui_hints={"show_reliability_banner": False, "show_blocked_banner": False, "card_ordering": []},
                visuals=[]
            )
            print(json.dumps(payload, default=lambda o: o.__dict__, indent=2))
            sys.exit(0)
            
        # 1. Construct Inputs
        end_date = datetime.now()
        start_date = end_date - timedelta(days=14)
        
        date_range = {
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d")
        }
        
        plot_id = ctx.get("plot_id", "UNKNOWN")
        
        # Update Memory explicitly if passed
        if plot_id != "UNKNOWN":
            from services.agribrain.orchestrator_v2.chat_memory import load_memory, save_memory
            mem = load_memory(plot_id)
            if args.exp: mem.experience_level = args.exp
            # Sync context
            mem.known_context["irrigation_type"] = ctx.get("irrigation_type")
            mem.known_context["soil_type"] = ctx.get("soil_type")
            save_memory(plot_id, mem)

        op_ctx = {
            "sensors": ctx.get("sensors", {}),
            "lat": ctx.get("lat", 0.0),
            "lng": ctx.get("lng", 0.0)
        }
        if plot_id != "UNKNOWN" and 'mem' in locals():
            op_ctx.update(mem.known_context)

        inputs = OrchestratorInput(
            plot_id=plot_id,
            geometry_hash="UNKNOWN_GEO",
            date_range=date_range,
            crop_config={"crop": ctx.get("crop", "unknown"), "stage": ctx.get("stage", "unknown")},
            operational_context=op_ctx,
            policy_snapshot={}
        )
        
        # 2. Run Pipeline (Suppress Stdout to avoid JSON corruption)
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
             # Inject metadata before run (runner doesn't overwrite it)
             # OrchestratorInput doesn't have metadata field, Runner attaches it.
             # We will just pass it to run_for_chat which doesn't take meta. 
             # We can patch runner.py or just let chat_adapter read it from where we can inject.
             # Easier: Just let chat_adapter read memory from plot_id.
             payload: ChatPayload = run_for_chat(inputs, user_query=args.query)
        
        # Optional: Print captured logs to stderr for debugging
        # print(f.getvalue(), file=sys.stderr)
        
        # 3. Output JSON
        # Convert dataclass to dict via __dict__ (recursive manually or using asdict)
        # Using default=vars for simple dataclasses
        print(json.dumps(payload, default=lambda o: o.__dict__, indent=2))
        
    except Exception as e:
        # Print error as JSON so Node.js can parse it gracefully
        err_response = {"error": str(e), "type": "OrchestratorExecutionError"}
        print(json.dumps(err_response))
        sys.exit(1)

if __name__ == "__main__":
    main()
