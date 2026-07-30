"""
Archive Cache Manager.
Orchestrates band raster reads/writes and metadata caching.
"""
import os
import json
import tempfile
from typing import Optional, Dict, Any
import numpy as np

from .raster_store import RasterStore

class ArchiveCache:
    def __init__(self, cache_dir: Optional[str] = None):
        if not cache_dir:
            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            cache_dir = os.path.join(base, "data", "archive_cache")
        self.cache_dir = cache_dir
        self.raster_store = RasterStore()

    def _get_scene_dir(self, plot_id: str, geom_hash: str, scene_id: str) -> str:
        return os.path.join(self.cache_dir, plot_id, geom_hash, scene_id)

    def has_scene(self, plot_id: str, geom_hash: str, scene_id: str) -> bool:
        """Checks if the scene directory exists."""
        return os.path.exists(self._get_scene_dir(plot_id, geom_hash, scene_id))

    def get_band(self, plot_id: str, geom_hash: str, scene_id: str, band: str) -> Optional[np.ndarray]:
        """Retrieves a band array if cached, otherwise returns None."""
        file_path = os.path.join(self._get_scene_dir(plot_id, geom_hash, scene_id), f"{band}.npz")
        if not os.path.exists(file_path):
            return None
        try:
            return self.raster_store.load_band(file_path)
        except Exception:
            return None

    def put_band(self, plot_id: str, geom_hash: str, scene_id: str, band: str, data: np.ndarray) -> None:
        """Caches a band array atomically."""
        scene_dir = self._get_scene_dir(plot_id, geom_hash, scene_id)
        os.makedirs(scene_dir, exist_ok=True)
        file_path = os.path.join(scene_dir, f"{band}.npz")
        self.raster_store.save_band(file_path, data)

    def get_scene_metadata(self, plot_id: str, geom_hash: str, scene_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves cached metadata dict if exists, otherwise returns None."""
        file_path = os.path.join(self._get_scene_dir(plot_id, geom_hash, scene_id), "metadata.json")
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def put_scene_metadata(self, plot_id: str, geom_hash: str, scene_id: str, metadata: Dict[str, Any]) -> None:
        """Caches scene metadata atomically."""
        scene_dir = self._get_scene_dir(plot_id, geom_hash, scene_id)
        os.makedirs(scene_dir, exist_ok=True)
        file_path = os.path.join(scene_dir, "metadata.json")
        
        # Write atomically
        fd, temp_path = tempfile.mkstemp(dir=scene_dir, suffix=".tmp")
        os.close(fd)
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)
            os.replace(temp_path, file_path)
        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise e
