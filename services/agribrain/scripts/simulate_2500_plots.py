import sys
import os
import json
import time
import random
import multiprocessing
import traceback
from datetime import datetime, timedelta, timezone
from concurrent.futures import ProcessPoolExecutor, as_completed

# Add agribrain to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from orchestrator_v2.runner import run_orchestrator
from orchestrator_v2.schema import OrchestratorInput
from orchestrator_v2.run_schema import artifact_to_run
from orchestrator_v2.run_entrypoint import _serialize_l10_output

CROPS = ["corn", "wheat", "soy", "cotton", "vineyard", "rice", "sugarcane"]
STAGES = ["emerging", "vegetative", "flowering", "yield_formation", "ripening"]
SOILS = ["clay", "sandy", "loam", "silt", "peat"]
IRRIGATION = ["drip", "sprinkler", "flood", "rainfed", "pivot"]

def simulate_run(args):
    plot_idx, season_idx = args
    try:
        now = datetime.now(timezone.utc)
        offset_days = season_idx * 90
        target_end = now - timedelta(days=offset_days)
        target_start = target_end - timedelta(days=14)
        
        random.seed(plot_idx * 10 + season_idx)
        crop = random.choice(CROPS)
        stage = random.choice(STAGES)
        soil = random.choice(SOILS)
        irrig = random.choice(IRRIGATION)
        
        lat = 35.0 + random.uniform(-10, 10)
        lng = -90.0 + random.uniform(-20, 20)
        
        inputs = OrchestratorInput(
            plot_id=f"SIM_PLOT_{plot_idx:04d}",
            geometry_hash=f"HASH_{plot_idx:04d}_{season_idx}",
            date_range={
                "start": target_start.strftime("%Y-%m-%d"),
                "end": target_end.strftime("%Y-%m-%d"),
            },
            crop_config={"crop": crop, "stage": stage},
            operational_context={
                "lat": lat,
                "lng": lng,
                "soil_type": soil,
                "irrigation_type": irrig,
                "sensors": {},
                "user_evidence": []
            },
            policy_snapshot={}
        )
        
        t0 = time.time()
        artifact = run_orchestrator(inputs)
        t1 = time.time()
        
        l10_payload = _serialize_l10_output(artifact.layer_10.output) if artifact.layer_10 and artifact.layer_10.output else {}
        
        quality = l10_payload.get("quality", {})
        qr_alerts = quality.get("warnings", [])
        
        # Analyze explainability
        exp = l10_payload.get("explainability_pack", {})
        explainability_score = 0
        if exp:
            for k, pack in exp.items():
                explainability_score += len(pack.get("top_drivers", []))
                explainability_score += len(pack.get("charts", []))
                
        metrics = {
            "plot_id": inputs.plot_id,
            "season": season_idx,
            "crop": crop,
            "execution_time_sec": t1 - t0,
            "surfaces_generated": quality.get("surfaces_generated", 0),
            "zones_generated": quality.get("zones_generated", 0),
            "reliability_score": quality.get("reliability_score", 0.0),
            "invariants_ok": quality.get("grid_alignment_ok", True) and quality.get("detail_conservation_ok", True),
            "warnings": len(qr_alerts),
            "explainability_depth": explainability_score,
            "intervention_triggered": any(z.get("zone_type") == "INTERVENTION_PRIORITY" for z in l10_payload.get("zones", [])),
            "compute_cost_estimate": 0.0015 * (quality.get("surfaces_generated", 0)), # Mock $ cost
        }
        return {"status": "ok", "metrics": metrics}
    except Exception as e:
        return {"status": "error", "error": str(e), "plot_idx": plot_idx, "season_idx": season_idx}

def main():
    NUM_PLOTS = 2500
    SEASONS = 3
    TOTAL_RUNS = NUM_PLOTS * SEASONS
    
    print(f"Starting Multi-Season Simulation: {NUM_PLOTS} plots x {SEASONS} seasons = {TOTAL_RUNS} total runs")
    
    tasks = [(p, s) for p in range(NUM_PLOTS) for s in range(SEASONS)]
    results = []
    errors = 0
    
    t_start = time.time()
    
    with ProcessPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
        futures = {executor.submit(simulate_run, task): task for task in tasks}
        
        for i, future in enumerate(as_completed(futures)):
            res = future.result()
            if res["status"] == "ok":
                results.append(res["metrics"])
            else:
                errors += 1
            
            if (i + 1) % 100 == 0:
                elapsed = time.time() - t_start
                rate = (i + 1) / elapsed
                rem = (TOTAL_RUNS - (i + 1)) / rate
                print(f"Progress: {i+1}/{TOTAL_RUNS} (Errors: {errors}) - {rate:.2f} runs/sec - ETA: {rem:.1f}s")
    
    t_end = time.time()
    print(f"Simulation completed in {t_end - t_start:.2f} seconds.")
    
    # Save results
    output_path = os.path.join(os.path.dirname(__file__), "simulation_results.json")
    with open(output_path, "w") as f:
        json.dump({"total_runs": TOTAL_RUNS, "errors": errors, "duration_sec": t_end - t_start, "metrics": results}, f, indent=2)
    
    print(f"Results saved to {output_path}")

if __name__ == "__main__":
    main()
