"""
Sentinel-2 Spectral Indices.
Provides safe computations for NDVI, EVI, and other vegetation indices.
Handles division-by-zero errors gracefully.
"""
import numpy as np

class S2Indices:
    def __init__(self):
        pass

    def compute_ndvi(self, red: np.ndarray, nir: np.ndarray) -> np.ndarray:
        """
        Computes NDVI: (NIR - Red) / (NIR + Red)
        """
        # Convert to float to avoid overflow/underflow
        red = red.astype(np.float32)
        nir = nir.astype(np.float32)
        
        denominator = nir + red
        safe_denom = np.where(denominator > 0.0, denominator, 1.0)
        # Use np.where to avoid division by zero
        ndvi = np.where(
            denominator > 0.0,
            (nir - red) / safe_denom,
            0.0
        )
        # Clip to valid NDVI range [-1.0, 1.0]
        return np.clip(ndvi, -1.0, 1.0)

    def compute_evi(self, blue: np.ndarray, red: np.ndarray, nir: np.ndarray) -> np.ndarray:
        """
        Computes EVI: 2.5 * (NIR - Red) / (NIR + 6.0 * Red - 7.5 * Blue + 1.0)
        """
        blue = blue.astype(np.float32)
        red = red.astype(np.float32)
        nir = nir.astype(np.float32)
        
        denominator = nir + 6.0 * red - 7.5 * blue + 1.0
        safe_denom = np.where(denominator > 0.0, denominator, 1.0)
        evi = np.where(
            denominator > 0.0,
            2.5 * (nir - red) / safe_denom,
            0.0
        )
        # Clip to standard range [-1.0, 2.5]
        return np.clip(evi, -1.0, 2.5)
