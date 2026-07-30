"""
Sentinel-1 SAR Quality.
Speckle noise detection and filtering utilities.
"""
import numpy as np

class S1Quality:
    def __init__(self):
        pass

    def detect_speckles(self, db_data: np.ndarray, window_size: int = 3, threshold: float = 2.0) -> np.ndarray:
        """
        Flags pixels that have high local deviation (speckle noise)
        compared to their local neighborhood.
        Returns a boolean mask where True indicates a speckle-affected pixel.
        """
        # Convert dB to linear scale for noise statistics
        linear = 10.0 ** (db_data / 10.0)
        
        # Fast local mean and standard deviation using uniform filter / simple convolution
        # To avoid external scipy dependency, we can use numpy sliding window or basic loops/kernels.
        # Since these are small 10x10 cropped footprint arrays, a basic numpy pad & roll or slide is extremely fast
        # and doesn't require importing scipy.ndimage.
        
        padded = np.pad(linear, pad_width=window_size//2, mode='edge')
        local_means = np.zeros_like(linear)
        local_stds = np.zeros_like(linear)
        
        half = window_size // 2
        for r in range(linear.shape[0]):
            for c in range(linear.shape[1]):
                window = padded[r : r + window_size, c : c + window_size]
                local_means[r, c] = np.mean(window)
                local_stds[r, c] = np.std(window)
                
        # Speckle index is local standard deviation / local mean (coefficient of variation)
        safe_mean = np.where(local_means > 0.0, local_means, 1e-5)
        speckle_index = local_stds / safe_mean
        
        # Flag if speckle_index exceeds threshold
        return speckle_index > threshold
