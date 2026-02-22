
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
    parser.add_argument("--exp", type=str, default="INTERMEDIATE", help="Farmer experience level")
    parser.add_argument("--cid", type=str, default="local_dev_session", help="Conversation ID")
    
    args = parser.parse_args()
    
    try:
        ctx = json.loads(args.context)
        
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

        inputs = OrchestratorInput(
            plot_id=plot_id,
            geometry_hash="UNKNOWN_GEO",
            date_range=date_range,
            crop_config={"crop": ctx.get("crop", "unknown"), "stage": ctx.get("stage", "unknown")},
            operational_context={
                "sensors": ctx.get("sensors", {}),
                "lat": ctx.get("lat", 0.0),
                "lng": ctx.get("lng", 0.0)
            },
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
