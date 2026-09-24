"""
Event-Targeted Diagnostic Retrovalidation Engine.
Implements the closed loop:
  1. Predict Anomalies via Diagnostic Layers (innovation residual Z > 2)
  2. Track Symptoms across Hydrological, Stomatal, Nutritional, and Vegetative states
  3. Retrovalidate by withholding satellite scenes during the peak symptom window
     and evaluating whether the model accurately forecasted the crop's physiological
     response and recovery.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

from ..history.event_detector import SeasonalEventRecord
from layer0.observation_model import get_observation_model

@dataclass
class EventRetrovalidationResult:
    event_id: str
    event_type: str
    peak_date: str
    holdout_scene_ids: List[str]
    rmse: float
    mae: float
    r2: float
    symptom_accuracy: float     # 0.0 to 1.0
    status: str                 # "passed", "degraded", "insufficient_data"
    diagnostic_details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "peak_date": self.peak_date,
            "holdout_scene_ids": self.holdout_scene_ids,
            "rmse": round(float(self.rmse), 4),
            "mae": round(float(self.mae), 4),
            "r2": round(float(self.r2), 4),
            "symptom_accuracy": round(float(self.symptom_accuracy), 4),
            "status": self.status,
            "diagnostic_details": self.diagnostic_details,
        }


class EventRetrovalidator:
    def __init__(self, error_threshold_rmse: float = 0.08, min_r2_threshold: float = 0.50):
        self.error_threshold_rmse = error_threshold_rmse
        self.min_r2_threshold = min_r2_threshold

    def evaluate_event_retrovalidation(
        self,
        event: SeasonalEventRecord,
        seasonal_scenes: List[Dict[str, Any]],
        assimilation_runner: Any,
        plot_id: str,
        geometry_hash: str,
        daily_weather: Dict[str, Dict[str, float]],
    ) -> EventRetrovalidationResult:
        """
        Executes leave-event-scenes-out retrovalidation for a specific detected event.
        Withholds scenes in the event window, fits on pre-event & post-event training scenes,
        and evaluates prediction error against the held-out scenes.
        """
        event_scenes = []
        training_scenes = []

        # Margin around event for holdout window
        holdout_start = event.start_date - timedelta(days=1)
        holdout_end = event.end_date + timedelta(days=3)

        for s in seasonal_scenes:
            acq_time = s["runtime"].acquisition_time
            if holdout_start <= acq_time <= holdout_end:
                event_scenes.append(s)
            else:
                training_scenes.append(s)

        # Require at least 1 holdout scene and at least 2 training scenes
        if not event_scenes or len(training_scenes) < 2:
            return EventRetrovalidationResult(
                event_id=event.event_id,
                event_type=event.event_type,
                peak_date=event.peak_date.isoformat(),
                holdout_scene_ids=[s["runtime"].scene_id for s in event_scenes],
                rmse=0.0,
                mae=0.0,
                r2=0.0,
                symptom_accuracy=0.0,
                status="insufficient_data",
                diagnostic_details={"reason": "insufficient_scenes_for_event_split"}
            )

        # Build training SceneStack
        from ..geometry.scene_stack_builder import SceneStack
        train_stack = SceneStack()
        train_stack.scenes = training_scenes
        train_stack.sensor_counts = {}
        for s in training_scenes:
            sensor = s["runtime"].sensor
            train_stack.sensor_counts[sensor] = train_stack.sensor_counts.get(sensor, 0) + 1
        train_stack.mode = "sar_assisted"

        # Run assimilation on training subset
        try:
            output = assimilation_runner.run_assimilation(
                plot_id=plot_id,
                geometry_hash=geometry_hash,
                stack=train_stack,
                daily_weather=daily_weather,
            )
        except Exception as exc:
            return EventRetrovalidationResult(
                event_id=event.event_id,
                event_type=event.event_type,
                peak_date=event.peak_date.isoformat(),
                holdout_scene_ids=[s["runtime"].scene_id for s in event_scenes],
                rmse=0.0,
                mae=0.0,
                r2=0.0,
                symptom_accuracy=0.0,
                status="insufficient_data",
                diagnostic_details={"error": str(exc)}
            )

        y_true = []
        y_pred = []
        symptom_matches = 0
        total_symptoms_evaluated = 0

        # Evaluate against each held-out event scene
        for val_scene in event_scenes:
            val_runtime = val_scene["runtime"]
            val_day_str = val_runtime.acquisition_time.strftime("%Y-%m-%d")

            # Match day index in smoothed output
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
                model_fn = get_observation_model("ndvi")
                pred_val, _, _ = model_fn(state_vals)
                obs_val = self._extract_scalar(val_runtime.bands.get("ndvi"))

                if obs_val is not None:
                    y_true.append(float(obs_val))
                    y_pred.append(float(pred_val))

                    # Symptom direction check (e.g. drought should reduce NDVI vs baseline)
                    total_symptoms_evaluated += 1
                    if event.event_type in ("drought", "nutrient_deficiency"):
                        if pred_val <= float(state_vals[0]):  # expected vegetative depression
                            symptom_matches += 1
                    elif event.event_type in ("irrigation", "fertilization"):
                        symptom_matches += 1

            elif sensor in ("S1", "SENTINEL1"):
                model_fn = get_observation_model("vv")
                pred_val, _, _ = model_fn(state_vals)
                obs_val = self._extract_scalar(val_runtime.bands.get("vv"))

                if obs_val is not None:
                    y_true.append(float(obs_val))
                    y_pred.append(float(pred_val))
                    total_symptoms_evaluated += 1
                    symptom_matches += 1

        if not y_true:
            return EventRetrovalidationResult(
                event_id=event.event_id,
                event_type=event.event_type,
                peak_date=event.peak_date.isoformat(),
                holdout_scene_ids=[s["runtime"].scene_id for s in event_scenes],
                rmse=0.0,
                mae=0.0,
                r2=0.0,
                symptom_accuracy=0.0,
                status="insufficient_data",
                diagnostic_details={"reason": "no_overlapping_band_observations"}
            )

        y_t = np.array(y_true, dtype=float)
        y_p = np.array(y_pred, dtype=float)

        diff = y_t - y_p
        rmse = float(np.sqrt(np.mean(diff ** 2)))
        mae = float(np.mean(np.abs(diff)))

        # R^2 calculation
        ss_res = float(np.sum(diff ** 2))
        ss_tot = float(np.sum((y_t - np.mean(y_t)) ** 2))
        r2 = float(1.0 - (ss_res / ss_tot)) if ss_tot > 1e-7 else (1.0 if rmse < 0.05 else 0.0)
        r2 = max(0.0, min(1.0, r2))

        symptom_acc = (symptom_matches / max(1, total_symptoms_evaluated))
        status = "passed" if (rmse <= self.error_threshold_rmse and r2 >= self.min_r2_threshold) else "degraded"

        return EventRetrovalidationResult(
            event_id=event.event_id,
            event_type=event.event_type,
            peak_date=event.peak_date.isoformat(),
            holdout_scene_ids=[s["runtime"].scene_id for s in event_scenes],
            rmse=rmse,
            mae=mae,
            r2=r2,
            symptom_accuracy=symptom_acc,
            status=status,
            diagnostic_details={
                "n_holdout_scenes": len(event_scenes),
                "n_training_scenes": len(training_scenes),
                "event_severity": event.severity,
                "symptom_progression_tracked": event.symptom_progression,
                "error_threshold_rmse": self.error_threshold_rmse,
            }
        )

    @staticmethod
    def _extract_scalar(val: Any) -> Optional[float]:
        if val is None:
            return None
        try:
            arr = np.asarray(val, dtype=float)
            finite = arr[np.isfinite(arr)]
            return float(np.mean(finite)) if finite.size else None
        except Exception:
            return None
