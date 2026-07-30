"""
Cache Index.
Maintains a persistent index mapping plot IDs and geometries to local scene cache entries.
"""
import os
import json
import tempfile
from typing import Dict, Any, List, Optional

class CacheIndex:
    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        self.index_path = os.path.join(cache_dir, "cache_index.json")

    def _load(self) -> Dict[str, Any]:
        if not os.path.exists(self.index_path):
            return {"plots": {}}
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"plots": {}}

    def _save(self, index_data: Dict[str, Any]) -> None:
        os.makedirs(self.cache_dir, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(dir=self.cache_dir, suffix=".tmp")
        os.close(fd)
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(index_data, f, indent=2)
            os.replace(temp_path, self.index_path)
        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise e

    def register_scene(
        self,
        plot_id: str,
        geom_hash: str,
        scene_id: str,
        source: str,
        acquisition_time: str,
        size_mb: float
    ) -> None:
        """Registers or updates a scene entry in the cache index."""
        idx = self._load()
        plots = idx.setdefault("plots", {})
        plot_entry = plots.setdefault(plot_id, {})
        geom_entry = plot_entry.setdefault(geom_hash, {})
        scenes = geom_entry.setdefault("scenes", {})
        
        scenes[scene_id] = {
            "source": source,
            "acquisition_time": acquisition_time,
            "size_mb": size_mb,
            "last_accessed": datetime.now().isoformat() if "datetime" in globals() else "2026-06-16T13:25:00Z"
        }
        self._save(idx)

    def unregister_scene(self, plot_id: str, geom_hash: str, scene_id: str) -> None:
        """Removes a scene entry from the cache index."""
        idx = self._load()
        try:
            plots = idx.get("plots", {})
            scenes = plots[plot_id][geom_hash]["scenes"]
            if scene_id in scenes:
                del scenes[scene_id]
                self._save(idx)
        except KeyError:
            pass

    def get_registered_scenes(self, plot_id: str, geom_hash: str) -> Dict[str, Any]:
        """Returns registered scenes dict for a specific plot and geometry."""
        idx = self._load()
        try:
            return idx["plots"][plot_id][geom_hash].get("scenes", {})
        except KeyError:
            return {}
            
# Make datetime import available
from datetime import datetime
