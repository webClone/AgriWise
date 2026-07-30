"""
Yearly Backtest.
Orchestrates cross-validation backtesting over historical scene slices.
Runs assimilation on training subsets and measures prediction residuals on validation holdouts.
"""
from typing import List, Dict, Any
from datetime import datetime
import numpy as np

from .archive_holdouts import ArchiveHoldouts
from .archive_metrics import ArchiveMetrics
from ..history.historical_assimilation_runner import HistoricalAssimilationRunner
from ..geometry.scene_stack_builder import SceneStack
from layer0.observation_model import get_observation_model

class YearlyBacktest:
    def __init__(self, runner: HistoricalAssimilationRunner):
        self.runner = runner
        self.holdouts = ArchiveHoldouts()
        self.metrics = ArchiveMetrics()

    def run_backtest(
        self,
        plot_id: str,
        geometry_hash: str,
        scenes: List[Dict[str, Any]],
        daily_weather: Dict[str, Dict[str, float]]
    ) -> Dict[str, Any]:
        """
        Executes leave-one-scene-out backtesting over the historical scenes.
        Computes RMSE, MAE, and R2 of model predictions on the left-out holdouts.
        """
        # Create folds using leave-one-scene-out splits
        # We need at least 3 scenes to perform meaningful cross-validation
        if len(scenes) < 3:
            return {"status": "insufficient_data", "rmse": 0.0, "mae": 0.0, "r2": 0.0}

        splits = self.holdouts.leave_one_scene_out_splits(scenes)
        
        y_true = []
        y_pred = []
        
        for train_scenes, val_scene in splits:
            # Re-compile train scenes into a SceneStack
            train_stack = SceneStack()
            train_stack.scenes = train_scenes
            train_stack.sensor_counts = {}
            for s in train_scenes:
                sensor = s["runtime"].sensor
                train_stack.sensor_counts[sensor] = train_stack.sensor_counts.get(sensor, 0) + 1
            train_stack.mode = "sar_assisted"

            # Run assimilation on training subset
            try:
                output = self.runner.run_assimilation(
                    plot_id=plot_id,
                    geometry_hash=geometry_hash,
                    stack=train_stack,
                    daily_weather=daily_weather
                )
            except Exception:
                continue

            # Extract the validation scene day
            val_runtime = val_scene["runtime"]
            val_day_str = val_runtime.acquisition_time.strftime("%Y-%m-%d")
            
            # Find the state index for val_day_str in output
            match_idx = -1
            for idx, dt in enumerate(output.timestamps):
                if dt.strftime("%Y-%m-%d") == val_day_str:
                    match_idx = idx
                    break
                    
            if match_idx == -1:
                continue

            # State vector at that step
            state_vals = output.states_smoothed[match_idx]

            # Project state_vals to observation space
            sensor = val_runtime.sensor
            
            if sensor == "S2":
                # Compute predicted NDVI
                try:
                    model_fn = get_observation_model("ndvi")
                    ndvi_pred, _, _ = model_fn(state_vals)
                    ndvi_obs = val_runtime.bands.get("ndvi")
                    if ndvi_obs is not None:
                        y_true.append(float(ndvi_obs))
                        y_pred.append(float(ndvi_pred))
                except Exception:
                    pass
            elif sensor == "S1":
                # Compute predicted VV
                try:
                    model_fn = get_observation_model("vv")
                    vv_pred, _, _ = model_fn(state_vals)
                    vv_obs = val_runtime.bands.get("vv")
                    if vv_obs is not None:
                        y_true.append(float(vv_obs))
                        y_pred.append(float(vv_pred))
                except Exception:
                    pass

        # Evaluate global predictions
        eval_res = self.metrics.evaluate_predictions(y_true, y_pred)
        eval_res["status"] = "success"
        eval_res["num_folds"] = len(y_true)
        
        return eval_res
