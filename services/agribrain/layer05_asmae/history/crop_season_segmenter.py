"""
Crop Season Segmenter.
Partitions chronological scene list into active crop and fallow periods.
Uses NDVI/RVI thresholds to detect vegetation status transitions.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any
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

    def segment_scenes(self, scenes: List[Dict[str, Any]]) -> List[CropSeasonSegment]:
        """
        Segments a list of chronologically sorted scenes into active crop
        and fallow periods.
        """
        if not scenes:
            return []

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
                    segments.append(CropSeasonSegment(
                        season_id=seg_id,
                        start_date=segment_start_dt,
                        end_date=current_scenes[-1].acquisition_time,
                        is_active_crop=is_current_active,
                        scenes=list(current_scenes)
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
            segments.append(CropSeasonSegment(
                season_id=seg_id,
                start_date=segment_start_dt,
                end_date=current_scenes[-1].acquisition_time,
                is_active_crop=is_current_active,
                scenes=list(current_scenes)
            ))
            
        return segments
