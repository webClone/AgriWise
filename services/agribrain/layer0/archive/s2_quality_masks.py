"""
Sentinel-2 Quality Masks.
Generates validity masks from S2 Scene Classification Layer (SCL) band.
"""
import numpy as np

# SCL Pixel Classification Values:
# 0: NO_DATA (invalid)
# 1: SATURATED_OR_DEFECTIVE (invalid)
# 2: DARK_AREA_PIXELS (invalid)
# 3: CLOUD_SHADOWS (invalid)
# 4: VEGETATION (valid)
# 5: NOT_VEGETATED (valid)
# 6: WATER (valid)
# 7: UNCLASSIFIED (valid)
# 8: CLOUD_MEDIUM_PROBABILITY (invalid)
# 9: CLOUD_HIGH_PROBABILITY (invalid)
# 10: THIN_CIRRUS (invalid)
# 11: SNOW_OR_ICE (invalid)

VALID_SCL_CLASSES = {4, 5, 6, 7}

class S2QualityMasks:
    def __init__(self):
        pass

    def generate_validity_mask(self, scl: np.ndarray) -> np.ndarray:
        """
        Given a numpy array representing the SCL band,
        returns a boolean array of the same shape where True means valid.
        """
        # Element-wise check for membership in VALID_SCL_CLASSES
        mask = np.isin(scl, list(VALID_SCL_CLASSES))
        return mask

    def calculate_valid_pixel_fraction(self, scl: np.ndarray) -> float:
        """Returns the fraction of valid pixels (0.0 to 1.0) in the SCL array."""
        if scl.size == 0:
            return 0.0
        mask = self.generate_validity_mask(scl)
        return float(np.sum(mask) / scl.size)
