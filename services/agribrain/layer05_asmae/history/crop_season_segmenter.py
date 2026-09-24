"""
Crop Season Segmenter.
Partitions chronological scene list into active crop and fallow periods.
Uses NDVI/RVI thresholds to detect vegetation status transitions.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from .history_schema import HistoricalSceneMetadata, CropSeasonSegment

class CropSeasonSegmenter:
    def __init__(self, ndvi_threshold: float = 0.25, fallow_days_limit: int = 45):
        self.ndvi_threshold = ndvi_threshold
        self.fallow_days_limit = fallow_days_limit

    def _get_scene_veg_index(self, scene: Dict[str, Any]) -> float:
        """Extracts a proxy vegetation index (NDVI for S2, RVI for S1)."""
        import numpy as np
        runtime = scene["runtime"]
        bands = runtime.bands or {}
        
        if runtime.sensor == "S2":
            val = bands.get("ndvi", 0.0)
            if isinstance(val, np.ndarray):
                return float(np.mean(val))
            return float(val or 0.0)
        elif runtime.sensor == "S1":
            val = bands.get("rvi", 0.0)
            if isinstance(val, np.ndarray):
                return float(np.mean(val))
            return float(val or 0.0)
        return 0.0

    def segment_scenes(
        self,
        scenes: List[Dict[str, Any]],
        daily_weather: Optional[Dict[str, Dict[str, float]]] = None
    ) -> List[CropSeasonSegment]:
        """
        Segments a list of chronologically sorted scenes into active crop
        and fallow periods.
        """
        if not scenes:
            return []

        # Map scenes by id for quick attribute extraction
        scenes_map = {s["runtime"].scene_id: s for s in scenes if isinstance(s, dict) and "runtime" in s}

        # Sort chronologically by acquisition_time
        sorted_scenes = sorted(scenes, key=lambda s: s["runtime"].acquisition_time)
        
        segments: List[CropSeasonSegment] = []
        current_scenes: List[HistoricalSceneMetadata] = []
        is_current_active = False
        segment_start_dt = sorted_scenes[0]["runtime"].acquisition_time
        season_counter = 1

        for i, s in enumerate(sorted_scenes):
            runtime = s["runtime"]
            acq_time = runtime.acquisition_time
            veg_val = self._get_scene_veg_index(s)
            
            # Map to HistoricalSceneMetadata
            meta = HistoricalSceneMetadata(
                scene_id=runtime.scene_id,
                sensor=runtime.sensor,
                acquisition_time=acq_time,
                cloud_cover=runtime.cloud_fraction,
                valid_fraction=s["quality"].clear_pixel_fraction,
                local_path={b: path for b, path in getattr(s.get("metadata", {}), "local_cache_refs", {}).items()}
            )
            
            # Vegetation status classification
            is_veg = veg_val >= self.ndvi_threshold
            
            if i == 0:
                is_current_active = is_veg
                current_scenes.append(meta)
                continue
                
            # If state changes, we might transition
            if is_veg != is_current_active:
                # To prevent rapid oscillation, check the time difference
                # or verify transition
                transition_allowed = True
                
                # Check if gap is too short to split
                time_diff = (acq_time - current_scenes[-1].acquisition_time).days
                if time_diff < 15:
                    transition_allowed = False
                    
                if transition_allowed:
                    # Close current segment
                    seg_id = f"season_{season_counter:03d}_{'active' if is_current_active else 'fallow'}"
                    p_val, p_dt = self._calculate_peak(current_scenes, scenes_map)
                    gdd = self._calculate_gdd(segment_start_dt, current_scenes[-1].acquisition_time, daily_weather)
                    segments.append(CropSeasonSegment(
                        season_id=seg_id,
                        start_date=segment_start_dt,
                        end_date=current_scenes[-1].acquisition_time,
                        is_active_crop=is_current_active,
                        scenes=list(current_scenes),
                        peak_date=p_dt,
                        peak_ndvi=p_val,
                        gdd_accumulated=gdd,
                    ))
                    
                    # Start new segment
                    season_counter += 1
                    segment_start_dt = acq_time
                    is_current_active = is_veg
                    current_scenes = [meta]
                else:
                    current_scenes.append(meta)
            else:
                current_scenes.append(meta)

        # Close final segment
        if current_scenes:
            seg_id = f"season_{season_counter:03d}_{'active' if is_current_active else 'fallow'}"
            p_val, p_dt = self._calculate_peak(current_scenes, scenes_map)
            gdd = self._calculate_gdd(segment_start_dt, current_scenes[-1].acquisition_time, daily_weather)
            segments.append(CropSeasonSegment(
                season_id=seg_id,
                start_date=segment_start_dt,
                end_date=current_scenes[-1].acquisition_time,
                is_active_crop=is_current_active,
                scenes=list(current_scenes),
                peak_date=p_dt,
                peak_ndvi=p_val,
                gdd_accumulated=gdd,
            ))
            
        return segments

    def _calculate_peak(self, current_scenes: List[HistoricalSceneMetadata], scenes_map: Dict[str, Any]) -> tuple:
        max_val = 0.0
        max_dt = None
        for m in current_scenes:
            sc = scenes_map.get(m.scene_id)
            if sc:
                v = self._get_scene_veg_index(sc)
                if v >= max_val:
                    max_val = v
                    max_dt = m.acquisition_time
        return float(max_val), max_dt

    def _calculate_gdd(self, start_dt: datetime, end_dt: datetime, daily_weather: Optional[Dict[str, Dict[str, float]]]) -> float:
        if not daily_weather:
            return 0.0
        gdd = 0.0
        curr = start_dt
        while curr.date() <= end_dt.date():
            d_str = curr.strftime("%Y-%m-%d")
            w = daily_weather.get(d_str)
            if w:
                t_mean = (w.get("temp_max", 20.0) + w.get("temp_min", 10.0)) / 2.0
                gdd += max(0.0, t_mean - 5.0)
            curr += timedelta(days=1)
        return float(round(gdd, 1))
