"""
Archive Cleanup Manager.
Enforces storage quotas per plot. If a plot's cache exceeds quotas,
evicts scenes (oldest first) until within limits.
"""
import os
import shutil
from typing import List, Optional
from .archive_config import ARCHIVE_MAX_STORAGE_MB_PER_PLOT
from .cache_index import CacheIndex
from .scene_manifest import HistoricalSceneRecord

class ArchiveCleanupManager:
    def __init__(self, cache_dir: str, cache_index: Optional[CacheIndex] = None):
        self.cache_dir = cache_dir
        self.cache_index = cache_index or CacheIndex(self.cache_dir)

    def calculate_plot_cache_size_mb(self, plot_id: str) -> float:
        """Calculates total size of cached files for the given plot in MB."""
        plot_path = os.path.join(self.cache_dir, plot_id)
        if not os.path.exists(plot_path):
            return 0.0
            
        total_bytes = 0
        for root, _, files in os.walk(plot_path):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    total_bytes += os.path.getsize(fp)
                except OSError:
                    pass
        return total_bytes / (1024 * 1024)

    def enforce_quota(self, plot_id: str) -> List[str]:
        """
        Enforces plot storage quota. Evicts the oldest scenes
        (chronologically) if storage limit is exceeded.
        Returns the list of evicted scene IDs.
        """
        evicted_scenes = []
        plot_path = os.path.join(self.cache_dir, plot_id)
        if not os.path.exists(plot_path):
            return evicted_scenes

        current_size = self.calculate_plot_cache_size_mb(plot_id)
        if current_size <= ARCHIVE_MAX_STORAGE_MB_PER_PLOT:
            return evicted_scenes

        # Find all scene directories under plot/geom_hash
        # Collect scene ID, acquisition_time, and path
        scenes_found = []
        for geom_hash in os.listdir(plot_path):
            geom_path = os.path.join(plot_path, geom_hash)
            if not os.path.isdir(geom_path):
                continue
                
            for scene_id in os.listdir(geom_path):
                scene_path = os.path.join(geom_path, scene_id)
                if not os.path.isdir(scene_path):
                    continue
                    
                # Read metadata.json if available to get acquisition_time
                meta_path = os.path.join(scene_path, "metadata.json")
                acq_time = "1970-01-01T00:00:00Z"
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            import json
                            meta = json.load(f)
                            acq_time = meta.get("datetime") or meta.get("start_datetime") or acq_time
                    except Exception:
                        pass
                
                # Estimate scene size
                scene_bytes = 0
                for root, _, files in os.walk(scene_path):
                    for f in files:
                        try:
                            scene_bytes += os.path.getsize(os.path.join(root, f))
                        except OSError:
                            pass
                scene_mb = scene_bytes / (1024 * 1024)
                
                scenes_found.append({
                    "scene_id": scene_id,
                    "acq_time": acq_time,
                    "path": scene_path,
                    "size_mb": scene_mb,
                    "geom_hash": geom_hash
                })

        # Sort chronologically (oldest scenes first)
        scenes_found.sort(key=lambda x: x["acq_time"])

        for scene in scenes_found:
            if current_size <= ARCHIVE_MAX_STORAGE_MB_PER_PLOT:
                break
                
            # Evict this scene
            try:
                shutil.rmtree(scene["path"])
                current_size -= scene["size_mb"]
                evicted_scenes.append(scene["scene_id"])
                
                # Unregister from index
                self.cache_index.unregister_scene(
                    plot_id=plot_id,
                    geom_hash=scene["geom_hash"],
                    scene_id=scene["scene_id"]
                )
            except Exception:
                pass

        return evicted_scenes
