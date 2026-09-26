"""
Historical Assimilation Runner.
Executes forward EnKF filtering and backward RTS smoothing over a scene stack.
Enforces observation rules, no-effect guard, and builds diagnostics report.
"""
from datetime import datetime, timedelta
import numpy as np
from typing import List, Dict, Any, Optional

from layer0.kalman_engine import ZoneKalmanFilter, KalmanObservation
import layer0.kalman_engine as ke

from .history_schema import HistoricalSmootherOutput
from .smoother import RTSSmoother
from .history_diagnostics import HistoryDiagnostics
from .history_no_effect_guard import HistoryNoEffectGuard
from .history_observation_rules import HistoryObservationRules
from .crop_season_segmenter import CropSeasonSegmenter
from .event_detector import IntraSeasonalEventDetector
from ..geometry.scene_stack_builder import SceneStack

class HistoricalAssimilationRunner:
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self.smoother = RTSSmoother()
        self.diagnostics = HistoryDiagnostics()
        self.no_effect_guard = HistoryNoEffectGuard(self.workspace_root)
        self.observation_rules = HistoryObservationRules()
        self.segmenter = CropSeasonSegmenter()
        self.event_detector = IntraSeasonalEventDetector()

    def run_assimilation(
        self,
        plot_id: str,
        geometry_hash: str,
        stack: SceneStack,
        daily_weather: Dict[str, Dict[str, float]],
        crop_params: Optional[Dict[str, Any]] = None,
        management_events: Optional[List[Any]] = None,
    ) -> HistoricalSmootherOutput:
        """
        Runs the complete forward Kalman filter and backward RTS smoother.
        Enforces physical rules, no-effect checksums, and compiles diagnostics.
        """
        # 1. Run No-Effect Guard: record pre-run checksums
        pre_checksums = self.no_effect_guard.record_pre_run_checksums()

        # Determine run timeline
        included_scenes = stack.scenes
        if not included_scenes:
            # Empty output if no scenes
            return HistoricalSmootherOutput(
                plot_id=plot_id,
                geometry_hash=geometry_hash,
                timestamps=[],
                states_smoothed=[],
                covariances_smoothed=[]
            )

        start_dt = min(s["runtime"].acquisition_time for s in included_scenes)
        end_dt = max(s["runtime"].acquisition_time for s in included_scenes)
        
        # Timeline days list
        timeline: List[datetime] = []
        curr = start_dt
        while curr.date() <= end_dt.date():
            timeline.append(curr)
            curr += timedelta(days=1)

        # Map scenes by date string
        scenes_by_day: Dict[str, List[Dict[str, Any]]] = {}
        for s in included_scenes:
            day_str = s["runtime"].acquisition_time.strftime("%Y-%m-%d")
            scenes_by_day.setdefault(day_str, []).append(s)

        # 2. Define patched get_observation_model to apply rules locally (DI)
        from layer0.observation_model import get_observation_model as standard_get_model
        
        def patched_get_model(obs_type):
            orig_fn = standard_get_model(obs_type)
            def wrapped_fn(state_values):
                y_pred, H, R_base = orig_fn(state_values)
                # Apply rules to zero out forbidden states in H
                H_new = self.observation_rules.apply_rules(obs_type, H)
                return y_pred, H_new, R_base
            return wrapped_fn

        try:
            # Initialize filter using dependency injection (no global patching)
            filt = ZoneKalmanFilter(
                zone_id=f"hist_zone_{plot_id}",
                crop_params=crop_params,
                observation_model_provider=patched_get_model
            )
            start_day_str = timeline[0].strftime("%Y-%m-%d")
            filt.initialize(start_day_str)

            # Lists for RTS backward pass
            states_pred: List[np.ndarray] = []
            covs_pred: List[np.ndarray] = []
            states_upd: List[np.ndarray] = []
            covs_upd: List[np.ndarray] = []

            # Forward Filter loop
            for dt in timeline:
                day_str = dt.strftime("%Y-%m-%d")
                
                weather = daily_weather.get(day_str)
                if weather is None:
                    # Predict with high uncertainty — DO NOT skip, timeline must remain contiguous
                    high_unc_state, high_unc_cov = filt.predict_missing_weather(day_str)
                    states_pred.append(high_unc_state)
                    covs_pred.append(high_unc_cov)
                    # No observation update — skip update step only
                    states_upd.append(high_unc_state)
                    covs_upd.append(high_unc_cov)
                    continue

                # A. Predict Step
                filt.predict(day_str, weather)
                states_pred.append(np.array(filt.state.values))
                covs_pred.append(np.array(filt.covariance.P))

                # B. Collect Observations
                day_scenes = scenes_by_day.get(day_str, [])
                observations = []
                for s in day_scenes:
                    runtime = s["runtime"]
                    sensor = runtime.sensor
                    qa_score = s["quality"].overall

                    if sensor == "S2":
                        # Missing bands are absent observations, never default
                        # NDVI/EVI values.
                        ndvi = self._band_scalar(runtime.bands.get("ndvi"))
                        evi = self._band_scalar(runtime.bands.get("evi"))
                        if ndvi is not None:
                            observations.append(KalmanObservation(
                                obs_type="ndvi", value=ndvi, sigma=0.05,
                                reliability=qa_score, source="sentinel2"
                            ))
                        if evi is not None:
                            observations.append(KalmanObservation(
                                obs_type="evi", value=evi, sigma=0.05,
                                reliability=qa_score, source="sentinel2"
                            ))
                    elif sensor == "S1":
                        vv = self._band_scalar(runtime.bands.get("vv"))
                        vh = self._band_scalar(runtime.bands.get("vh"))
                        if vv is not None:
                            observations.append(KalmanObservation(
                                obs_type="vv", value=vv, sigma=0.1,
                                reliability=qa_score, source="sentinel1"
                            ))
                        if vh is not None:
                            observations.append(KalmanObservation(
                                obs_type="vh", value=vh, sigma=0.1,
                                reliability=qa_score, source="sentinel1"
                            ))

                # C. Update Step ( Joseph form )
                if observations:
                    filt.update(observations)

                states_upd.append(np.array(filt.state.values))
                covs_upd.append(np.array(filt.covariance.P))

            # 3. RTS backward pass smoothing
            states_smooth, covs_smooth = self.smoother.smooth(
                states_pred=states_pred,
                covs_pred=covs_pred,
                states_upd=states_upd,
                covs_upd=covs_upd
            )

        finally:
            pass

        # Build output object
        output = HistoricalSmootherOutput(
            plot_id=plot_id,
            geometry_hash=geometry_hash,
            timestamps=timeline,
            states_smoothed=states_smooth,
            covariances_smoothed=covs_smooth
        )

        # 4. Compute diagnostics
        diag = self.diagnostics.compute_run_diagnostics(output)

        # 4b. Seasonal Segmentation & Intra-Seasonal Event Detection
        try:
            segments = self.segmenter.segment_scenes(included_scenes, daily_weather=daily_weather)
            diag["seasonal_segments"] = []
            all_events = []
            scenes_map = {s["runtime"].scene_id: s for s in included_scenes if isinstance(s, dict) and "runtime" in s}

            for seg in segments:
                seg_scenes = [scenes_map[m.scene_id] for m in seg.scenes if m.scene_id in scenes_map]
                events = self.event_detector.detect_events(
                    season_id=seg.season_id,
                    start_date=seg.start_date,
                    end_date=seg.end_date,
                    scenes=seg_scenes,
                    daily_weather=daily_weather,
                    management_events=management_events,
                )
                seg_dict = {
                    "season_id": seg.season_id,
                    "start_date": seg.start_date.isoformat(),
                    "end_date": seg.end_date.isoformat(),
                    "is_active_crop": seg.is_active_crop,
                    "peak_date": seg.peak_date.isoformat() if seg.peak_date else None,
                    "peak_ndvi": seg.peak_ndvi,
                    "gdd_accumulated": seg.gdd_accumulated,
                    "events": [e.to_dict() for e in events]
                }
                diag["seasonal_segments"].append(seg_dict)
                all_events.extend([e.to_dict() for e in events])
            diag["detected_events"] = all_events
        except Exception as exc:
            diag["seasonal_segmentation_error"] = str(exc)

        output.diagnostics = diag

        # 5. Assert No-Effect Guard: verify production files remained unchanged
        self.no_effect_guard.assert_post_run_unchanged(pre_checksums)

        return output

    @staticmethod
    def _band_scalar(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            array = np.asarray(value, dtype=float)
            finite = array[np.isfinite(array)]
            return float(np.mean(finite)) if finite.size else None
        except (TypeError, ValueError):
            return None
