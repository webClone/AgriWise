"""
Raster Store.
Manages reading and writing cropped numpy arrays to NPZ files.
Strictly enforces allow_pickle=False for security and executes atomic writes.
"""
import os
import tempfile
import numpy as np

class RasterStore:
    def __init__(self):
        pass

    def save_band(self, file_path: str, data: np.ndarray) -> None:
        """Saves a single band numpy array to NPZ atomically with allow_pickle=False."""
        dir_name = os.path.dirname(file_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
            
        # Write to temporary file first in the same directory
        fd, temp_path = tempfile.mkstemp(dir=dir_name, suffix=".npz")
        os.close(fd)
        
        try:
            if data.dtype == object:
                raise ValueError("object arrays forbidden")
            np.savez(temp_path, data=data)
            os.replace(temp_path, file_path)
        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise e

    def load_band(self, file_path: str) -> np.ndarray:
        """Loads a single band numpy array from NPZ, enforcing allow_pickle=False."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Cache file not found: {file_path}")
            
        with np.load(file_path, allow_pickle=False) as data_dict:
            if "data" not in data_dict:
                raise KeyError(f"Expected key 'data' in NPZ file: {file_path}")
            return data_dict["data"]
