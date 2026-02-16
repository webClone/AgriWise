"""
AgriBrain Orchestrator.
Runs the full 9-Layer Intelligence Stack for a given plot.
Usage: python orchestrator.py --plot_id <id> --config <json> [--query <question>]
"""

import sys
import json
import argparse
from datetime import datetime
from typing import Dict, Any

# Layer Imports
import os
# Add the directory containing orchestrator.py to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# --- IMPORT BLOCK ---
# Attempt to import layers. We split this into "Heavy" (Scientific) and "Light" (Interface)
# so that missing numpy/pandas doesn't break the Chat/Q&A interface.

# Setup Project Root for package-relative imports (if needed)
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)

# 1. HEAVY LAYERS (Yield, Risk, Prescriptive) - May fail without numpy/pandas
try:
    try:
        from layer7_risk.risk_composite import risk_engine
        from layer6_yield.yield_forecast import yield_engine
        from layer8_prescriptive.action_ranker import action_ranker
        from layer8_prescriptive.scheduler import scheduler
    except ImportError:
        from services.agribrain.layer7_risk.risk_composite import risk_engine
        from services.agribrain.layer6_yield.yield_forecast import yield_engine
        from services.agribrain.layer8_prescriptive.action_ranker import action_ranker
        from services.agribrain.layer8_prescriptive.scheduler import scheduler
except ImportError as e:
    print(f"[AgriBrain] Warning: Scientific Layers Disabled (Missing: {e})", file=sys.stderr)

# 2. LIGHT LAYERS (Interface, Q&A) - Sould work with pure Python
try:
    try:
        from layer9_interface.advisor_llm import advisor
        from layer9_interface.qa_llm import qa_bot
    except ImportError:
        from services.agribrain.layer9_interface.advisor_llm import advisor
        from services.agribrain.layer9_interface.qa_llm import qa_bot
except ImportError as e:
    print(f"[AgriBrain] Warning: Interface Layers Disabled (Missing: {e})", file=sys.stderr)

class AgriBrainOrchestrator:
    
    def __init__(self):
        self.status_log = []

    def log(self, step: str):
        # Force flush to ensure it appears in Node logs
        print(f"[AgriBrain] {step}", file=sys.stderr, flush=True)
        self.status_log.append({"timestamp": datetime.now().isoformat(), "step": step})

    def run_analysis(self, plot_id: str, config: Dict[str, Any] = None, user_query: str = None, injected_context: Dict[str, Any] = None):
        """
        Execute Layers 1-9 sequentially.
        If user_query is provided, runs Q&A logic (L9.2) using the context from L1-L8.
        If injected_context is provided (from DB), it overrides default/mock metadata.
        """
        self.log(f"Starting analysis for Plot {plot_id}")
        
        # --- LAYER 1: DATA INGESTION ---
        self.log("L1: Ingesting Field Data...")
        
        # Default / Mock Metadata
        plot_meta = {"id": plot_id, "crop": "Wheat", "stage": "Vegetative"}
        
        # OVERRIDE with Real Data if provided
        if injected_context:
            self.log("L1: Using Injected Real Data")
            plot_meta.update({
                "crop": injected_context.get("crop", "Wheat"),
                "stage": injected_context.get("stage", "Vegetative"),
                "area": injected_context.get("area", 0),
                "lat": injected_context.get("lat"),
                "lng": injected_context.get("lng")
            })

        # In real/full v2, this calls DataFusionEngine (fetching Sentinel/Weather)
        # For now, we simulate weather AND use sensor readings if available
        weather_forecast = [
             {"day": 1, "temp_max": 28, "precip_mm": 0, "wind": 10},
             {"day": 2, "temp_max": 29, "precip_mm": 0, "wind": 5},
             {"day": 3, "temp_max": 25, "precip_mm": 15, "wind": 20}
        ]
        
        # Override Weather/Stress with Sensor Data
        stress_state = {
            "water_loss_factor": 0.2, # Default Moderate drought
            "nutrient_loss_factor": 0.1,
            "disease_loss_factor": 0.05
        }

        if injected_context and "sensors" in injected_context:
            s = injected_context["sensors"]
            # If soil moisture is low (< 30%), increase water stress
            if "soil_moisture" in s:
                sm = s["soil_moisture"]
                # ranges usually 0-100 or 0-1. Assuming 0-100
                if sm < 30:
                    stress_state["water_loss_factor"] = 0.5 + ((30 - sm) / 60) # High stress
                elif sm > 80:
                     stress_state["water_loss_factor"] = 0.1 # Low stress (maybe too wet?)
                else:
                    stress_state["water_loss_factor"] = 0.0 # Optimal

            # Adjust weather forecast temp based on real temp
            if "temperature" in s:
                current_temp = s["temperature"]
                weather_forecast[0]["temp_max"] = current_temp # Update today's temp
        
        # --- LAYER 2-5: DIAGNOSTICS (Mocked Inputs for L6+) ---
        self.log("L2-L5: Running Biophysical Diagnostics...")
        # Stress factors now potentially driven by real sensors
        
        # --- LAYER 6: YIELD ---
        self.log("L6: Forecasting Yield...")
        # Call Actual Engine (simulated import if missing)
        try:
            yield_res = yield_engine.predict_yield(
                plot_meta["crop"], 
                final_biomass_kg_ha=12000, 
                cumulative_stress=stress_state
            )
        except NameError:
            # Dynamic Yield Calculation based on Stress
            base_yield = 7.0 if plot_meta["crop"] == "Wheat" else 80.0 # Tomato yield higher tonnage
            
            # Simple penalty model
            penalty = (stress_state["water_loss_factor"] * 0.4) + \
                      (stress_state["nutrient_loss_factor"] * 0.3) + \
                      (stress_state["disease_loss_factor"] * 0.3)
            
            est_yield = base_yield * (1.0 - penalty)
            
            yield_res = {
                "yield_mean_t_ha": round(est_yield, 1), 
                "attribution": {
                    "water": stress_state["water_loss_factor"],
                    "nutrient": stress_state["nutrient_loss_factor"],
                    "disease": stress_state["disease_loss_factor"]
                }
            }
 
        # --- LAYER 7: RISK ---
        self.log("L7: Assessing Risk...")
        try:
            risk_res = risk_engine.calculate_composite_risk(
                water_stress_prob=int(stress_state["water_loss_factor"]*100), 
                nutrient_stress_prob=10, 
                disease_risk_prob=10, climate_shock_prob=5, stage_label=plot_meta["stage"]
            )
            # Add Trust Report
            trust_res = {"trust_score": 85, "trust_level": "High", "issues": []}
        except NameError:
             water_risk = int(stress_state["water_loss_factor"] * 100)
             risk_score = (water_risk * 0.5) + 10
             
             risk_res = {
                 "risk_score": round(risk_score, 1), 
                 "risk_level": "High" if risk_score > 50 else "Moderate" if risk_score > 20 else "Low", 
                 "top_drivers": ["Water"] if water_risk > 20 else ["Meteo"]
             }
             trust_res = {"trust_score": 92 if "sensors" in injected_context else 70, "trust_level": "High"}
 
        # --- LAYER 8: PRESCRIPTIVE ---
        self.log("L8: prioritizing Actions...")
        try:
            # Scenarios
            scenarios = [
                {"scenario": "Irrigate", "profit_delta_usd": 150, "roi_pct": 200, "cost": 25},
                {"scenario": "Spray Fungicide", "profit_delta_usd": 50, "roi_pct": 50, "cost": 30}
            ]
            ranked = action_ranker.rank_actions(scenarios, trust_score=trust_res["trust_score"])
            
            # Schedule
            sched = scheduler.schedule_actions(ranked, weather_forecast, datetime.now())
        except NameError:
             if stress_state["water_loss_factor"] > 0.3:
                 ranked = [{"action": "Irrigate", "confidence": "High", "expected_profit": 150}]
                 sched = [{"action": "Irrigate", "scheduled_date": "Tomorrow"}]
             else:
                 ranked = [{"action": "Monitor", "confidence": "High", "expected_profit": 0}]
                 sched = []
 
        # --- CONTEXT SNAPSHOT ---
        context_snapshot = {
            "plot": plot_meta,
            "yield": yield_res,
            "risk": risk_res,
            "trust": trust_res,
            "top_actions": ranked,
            "schedule": sched,
            "sensors": injected_context.get("sensors", {}) if injected_context else {},
            "soil": injected_context.get("soil", {}) if injected_context else {}
        }

        # --- LAYER 9: INTERFACE ---
        
        # A) Chat Mode
        if user_query:
            self.log(f"L9.2: Processing Query: {user_query}")
            try:
                # Use QABot to generating human-friendly answer
                answer = qa_bot.handle_query(user_query, context_snapshot)
                print(json.dumps(answer, indent=2))
                return
            except NameError:
                 # Fallback if module not loaded
                 print(json.dumps({
                     "answer": "I can't access the Q&A module right now, but I see high water stress.", 
                     "error": "ImportError"
                 }, indent=2))
                 return

        # B) Report Mode (Default)
        self.log("L9.1: Generating Advisory...")
        try:
            prompt_context = advisor.prepare_context(plot_meta, trust_res, yield_res, risk_res, ranked)
            # In a real app, this calls OpenAI or uses a template.
            advisory_text = advisor.mock_response(prompt_context)
        except NameError:
             advisory_text = {"summary": "Yield limited by Water Stress.", "actions": "Irrigate."}

        # FINAL OUTPUT
        output = {
            "meta": {"plot_id": plot_id, "timestamp": datetime.now().isoformat()},
            "analysis": advisory_text,
            "metrics": {
                "yield": yield_res,
                "risk": risk_res,
                "trust": trust_res
            },
            "plan": {
                "actions": ranked,
                "schedule": sched
            }
        }
        
        # Dump to Stdout for Node.js
        print(json.dumps(output, indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--plot_id", required=True)
    parser.add_argument("--config", help="Optional JSON config")
    parser.add_argument("--query", help="User Question for Q&A")
    parser.add_argument("--context", help="Injected Context from DB (JSON)")
    args = parser.parse_args()
    
    injected_ctx = {}
    if args.context:
        try:
            injected_ctx = json.loads(args.context)
        except:
            pass
            
    orch = AgriBrainOrchestrator()
    orch.run_analysis(args.plot_id, user_query=args.query, injected_context=injected_ctx)
