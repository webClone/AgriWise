"""
Yearly Backtest.
Orchestrates cross-validation backtesting over historical scene slices.
Runs assimilation on training subsets and measures prediction residuals on validation holdouts.
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import numpy as np

from .archive_holdouts import ArchiveHoldouts
from .archive_metrics import ArchiveMetrics
from .event_retrovalidation import EventRetrovalidator, EventRetrovalidationResult
from ..history.crop_season_segmenter import CropSeasonSegmenter
from ..history.event_detector import IntraSeasonalEventDetector, SeasonalEventRecord
from ..history.historical_assimilation_runner import HistoricalAssimilationRunner
from ..geometry.scene_stack_builder import SceneStack
from layer0.observation_model import get_observation_model

class YearlyBacktest:
    def __init__(self, runner: HistoricalAssimilationRunner):
        self.runner = runner
        self.holdouts = ArchiveHoldouts()
        self.metrics = ArchiveMetrics()
        self.segmenter = CropSeasonSegmenter()
        self.event_detector = IntraSeasonalEventDetector()
        self.event_retrovalidator = EventRetrovalidator()

    def run_backtest(
        self,
        plot_id: str,
        geometry_hash: str,
        scenes: List[Dict[str, Any]],
        daily_weather: Dict[str, Dict[str, float]],
        soil_profile: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes seasonal and event-targeted cross-validation backtesting over historical scenes.
        Partitions the archive into discrete crop seasons, detects intra-seasonal events
        (irrigation, rain, drought, fertilization, nutrient deficiency, disease risk),
        and retrovalidates predictions across both standard holdouts and event windows.
        """
        if len(scenes) < 3:
            return {
                "status": "insufficient_data",
                "rmse": 0.0,
                "mae": 0.0,
                "r2": 0.0,
                "seasonal_matrix": [],
                "events_detected": [],
                "event_retrovalidation_results": []
            }

        # 1. Segment scenes into seasonal envelopes
        segments = self.segmenter.segment_scenes(scenes, daily_weather=daily_weather)
        scenes_map = {s["runtime"].scene_id: s for s in scenes if isinstance(s, dict) and "runtime" in s}

        seasonal_matrix = []
        all_detected_events = []
        all_event_retro_results = []

        all_y_true = []
        all_y_pred = []

        # 2. Process each season independently
        for seg in segments:
            seg_scenes = [scenes_map[m.scene_id] for m in seg.scenes if m.scene_id in scenes_map]
            if len(seg_scenes) < 2:
                continue

            # Detect intra-seasonal events
            events = self.event_detector.detect_events(
                season_id=seg.season_id,
                start_date=seg.start_date,
                end_date=seg.end_date,
                scenes=seg_scenes,
                daily_weather=daily_weather,
                soil_profile=soil_profile
            )
            seg.detected_events = [e.to_dict() for e in events]
            all_detected_events.extend(seg.detected_events)

            # Event-targeted retrovalidation for this season
            seg_event_results = []
            for ev in events:
                ev_res = self.event_retrovalidator.evaluate_event_retrovalidation(
                    event=ev,
                    seasonal_scenes=seg_scenes,
                    assimilation_runner=self.runner,
                    plot_id=plot_id,
                    geometry_hash=geometry_hash,
                    daily_weather=daily_weather
                )
                seg_event_results.append(ev_res.to_dict())
                all_event_retro_results.append(ev_res.to_dict())

            # Intra-seasonal leave-one-scene-out splits
            splits = self.holdouts.leave_one_scene_out_splits(seg_scenes)
            seg_y_true = []
            seg_y_pred = []

            for train_scenes, val_scene in splits:
                train_stack = SceneStack()
                train_stack.scenes = train_scenes
                train_stack.sensor_counts = {}
                for s in train_scenes:
                    sensor = s["runtime"].sensor
                    train_stack.sensor_counts[sensor] = train_stack.sensor_counts.get(sensor, 0) + 1
                train_stack.mode = "sar_assisted"

                try:
                    output = self.runner.run_assimilation(
                        plot_id=plot_id,
                        geometry_hash=geometry_hash,
                        stack=train_stack,
                        daily_weather=daily_weather
                    )
                except Exception:
                    continue

                val_runtime = val_scene["runtime"]
                val_day_str = val_runtime.acquisition_time.strftime("%Y-%m-%d")

                match_idx = -1
                for idx, dt in enumerate(output.timestamps):
                    if dt.strftime("%Y-%m-%d") == val_day_str:
                        match_idx = idx
                        break

                if match_idx == -1:
                    continue

                state_vals = output.states_smoothed[match_idx]
                sensor = val_runtime.sensor

                if sensor in ("S2", "SENTINEL2"):
                    try:
                        model_fn = get_observation_model("ndvi")
                        ndvi_pred, _, _ = model_fn(state_vals)
                        ndvi_obs = val_runtime.bands.get("ndvi")
                        if ndvi_obs is not None:
                            val_f = float(np.mean(ndvi_obs) if isinstance(ndvi_obs, np.ndarray) else ndvi_obs)
                            seg_y_true.append(val_f)
                            seg_y_pred.append(float(ndvi_pred))
                            all_y_true.append(val_f)
                            all_y_pred.append(float(ndvi_pred))
                    except Exception:
                        pass
                elif sensor in ("S1", "SENTINEL1"):
                    try:
                        model_fn = get_observation_model("vv")
                        vv_pred, _, _ = model_fn(state_vals)
                        vv_obs = val_runtime.bands.get("vv")
                        if vv_obs is not None:
                            val_f = float(np.mean(vv_obs) if isinstance(vv_obs, np.ndarray) else vv_obs)
                            seg_y_true.append(val_f)
                            seg_y_pred.append(float(vv_pred))
                            all_y_true.append(val_f)
                            all_y_pred.append(float(vv_pred))
                    except Exception:
                        pass

            seg_eval = self.metrics.evaluate_predictions(seg_y_true, seg_y_pred)
            seg_summary = {
                "season_id": seg.season_id,
                "is_active_crop": seg.is_active_crop,
                "start_date": seg.start_date.isoformat(),
                "end_date": seg.end_date.isoformat(),
                "peak_date": seg.peak_date.isoformat() if seg.peak_date else None,
                "peak_ndvi": seg.peak_ndvi,
                "gdd_accumulated": seg.gdd_accumulated,
                "scenes_count": len(seg_scenes),
                "events_count": len(events),
                "rmse": seg_eval.get("rmse", 0.0),
                "mae": seg_eval.get("mae", 0.0),
                "r2": seg_eval.get("r2", 0.0),
                "event_results": seg_event_results
            }
            seg.retrovalidation_summary = seg_summary
            seasonal_matrix.append(seg_summary)

        # Evaluate global predictions across all seasons
        if all_y_true:
            eval_res = self.metrics.evaluate_predictions(all_y_true, all_y_pred)
        else:
            eval_res = {"rmse": 0.0, "mae": 0.0, "r2": 0.0}

        eval_res["status"] = "success"
        eval_res["num_folds"] = len(all_y_true)
        eval_res["seasons_evaluated"] = len(seasonal_matrix)
        eval_res["seasonal_matrix"] = seasonal_matrix
        eval_res["events_detected"] = all_detected_events
        eval_res["event_retrovalidation_results"] = all_event_retro_results

        return eval_res
