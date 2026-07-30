"""
Archive Holdouts.
Implements data partition splits for historical retrovalidation:
  - Leave-one-scene-out split
  - Temporal fraction split
  - Sensor-based holdout split
"""
import random
from typing import List, Tuple, Any

class ArchiveHoldouts:
    def __init__(self):
        pass

    def leave_one_scene_out_splits(
        self,
        scenes: List[Any]
    ) -> List[Tuple[List[Any], Any]]:
        """
        Creates split folds where each fold leaves out exactly one scene for validation.
        Returns a list of (train_scenes, validation_scene) tuples.
        """
        splits = []
        for i in range(len(scenes)):
            train = [scenes[j] for j in range(len(scenes)) if j != i]
            val = scenes[i]
            splits.append((train, val))
        return splits

    def temporal_holdout_split(
        self,
        scenes: List[Any],
        holdout_fraction: float = 0.2,
        seed: int = 42
    ) -> Tuple[List[Any], List[Any]]:
        """
        Splits scenes into train and validation sets based on a temporal fraction.
        E.g. leaves out 20% of scenes systematically or randomly.
        """
        if not scenes:
            return [], []
            
        n_val = max(1, int(len(scenes) * holdout_fraction))
        
        # Sort chronologically first
        sorted_scenes = sorted(scenes, key=lambda s: s["runtime"].acquisition_time)
        
        # Seeded random selection of holdout indices to keep it deterministic
        rng = random.Random(seed)
        val_indices = set(rng.sample(range(len(sorted_scenes)), n_val))
        
        train = [sorted_scenes[i] for i in range(len(sorted_scenes)) if i not in val_indices]
        val = [sorted_scenes[i] for i in range(len(sorted_scenes)) if i in val_indices]
        
        return train, val

    def sensor_holdout_split(
        self,
        scenes: List[Any],
        holdout_sensor: str
    ) -> Tuple[List[Any], List[Any]]:
        """
        Splits scenes by leaving out a specific sensor entirely (e.g. S1 or S2).
        Returns (train_scenes, validation_scenes).
        """
        train = []
        val = []
        for s in scenes:
            sensor = s["runtime"].sensor.upper()
            if sensor == holdout_sensor.upper() or (holdout_sensor.upper() == "S2" and sensor == "SENTINEL2") or (holdout_sensor.upper() == "S1" and sensor == "SENTINEL1"):
                val.append(s)
            else:
                train.append(s)
        return train, val
