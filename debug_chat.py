
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
        from services.agribrain.orchestrator_v2.runner import run_orchestrator
        # Run raw orchestrator first to see full artifact including errors
        art = run_orchestrator(inputs)
        
        print(f"\n✅ Run ID: {art.meta.orchestrator_run_id}")
        print(f"📊 Global Quality: {art.global_quality}")
        
        print(f"L1: {art.layer_1}")
        print(f"L2: {art.layer_2}")
        print(f"L3: {art.layer_3}")
        print(f"L4: {art.layer_4}")
        print(f"L5: {art.layer_5}")
        print(f"L6: {art.layer_6}")
        
    except Exception as e:
        print(f"❌ CRITICAL EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug()
