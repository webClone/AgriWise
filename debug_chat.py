
import sys
import os
import json
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.getcwd())

from services.agribrain.orchestrator_v2.runner import run_for_chat
from services.agribrain.orchestrator_v2.schema import OrchestratorInput

def debug():
    print("🐞 Debugging Orchestrator Chat...")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=14)
    
    inputs = OrchestratorInput(
        plot_id="DEBUG_PLOT",
        geometry_hash="GEO_DEBUG",
        date_range={
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d")
        },
        crop_config={"crop": "WHEAT", "stage": "VEGETATIVE"},
        operational_context={},
        policy_snapshot={}
    )
    
    try:
        from services.agribrain.orchestrator_v2.runner import run_for_chat
        
        # Test the spatial AI adapter
        user_query = "Please give me a complete summary of this plot and point out any weak zones."
        payload = run_for_chat(inputs, user_query=user_query)
        
        print("\n✅ Payload Generated")
        print("\n--- CHAT RESPONSE ---")
        
        # In a real environment, the LLM processes this payload, but the payload itself contains the prompt.
        from dataclasses import asdict
        print(json.dumps(asdict(payload), indent=2))
        
    except Exception as e:
        print(f"❌ CRITICAL EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug()
