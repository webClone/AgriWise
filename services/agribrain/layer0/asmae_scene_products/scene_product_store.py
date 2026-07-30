import os
import numpy as np
from ..archive.raster_store import RasterStore

class SceneProductStore:
    def __init__(self, plot_id: str, run_id: str = None, provider_product_id: str = None):
        self.plot_id = plot_id
        self.run_id = run_id
        self.provider_product_id = provider_product_id
        # Persistent per-plot directory to cache real scenes across runs
        real_scenes_dir = os.path.abspath(os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "artifacts",
            "real_scenes"
        ))
        if provider_product_id:
            self.base_dir = os.path.join(real_scenes_dir, plot_id, provider_product_id)
        else:
            self.base_dir = os.path.join(real_scenes_dir, plot_id)
            
        os.makedirs(self.base_dir, exist_ok=True)
        self.raster_store = RasterStore()

    def save_band(self, scene_id: str, band_name: str, array: np.ndarray) -> str:
        # If storing in provider subfolder, we can use the band_name directly, otherwise prefix it
        if self.provider_product_id:
            file_name = f"{band_name}.npz"
        else:
            file_name = f"{scene_id}_{band_name}.npz"
        file_path = os.path.join(self.base_dir, file_name)
        self.raster_store.save_band(file_path, array)
        return os.path.abspath(file_path)
