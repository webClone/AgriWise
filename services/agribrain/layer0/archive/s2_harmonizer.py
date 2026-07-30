"""
Sentinel-2 Harmonization.
Adjusts digital numbers (DN) to surface reflectance [0.0, 1.0].
Corrects for the baseline 04.00 shift (+1000 DN offset) introduced on 2022-01-25.
"""
import numpy as np
from typing import Dict, Any

class S2Harmonizer:
    def __init__(self):
        pass

    def get_baseline_offset(self, metadata: Dict[str, Any], acquisition_time: str) -> float:
        """
        Determines the DN offset to subtract based on the processing baseline or date.
        Baseline 04.00 and above (deployed 2022-01-25) introduced an offset of 1000 DN.
        """
        # 1. Try processing baseline property
        baseline = metadata.get("sentinel:processing_baseline") or metadata.get("processing:baseline")
        if baseline:
            try:
                # E.g. "04.00" -> 4.0
                val = float(baseline)
                if val >= 4.0:
                    return 1000.0
            except ValueError:
                pass

        # 2. Date fallback: baseline 04.00 was introduced 2022-01-25
        if acquisition_time:
            try:
                # Extract date part
                date_str = acquisition_time.split("T")[0]
                dt = date_str.split("-")
                year = int(dt[0])
                month = int(dt[1])
                day = int(dt[2])
                
                # Compare to 2022-01-25
                if (year > 2022) or (year == 2022 and month > 1) or (year == 2022 and month == 1 and day >= 25):
                    return 1000.0
            except Exception:
                pass
                
        return 0.0

    def validate_bands_alignment(self, bands: Dict[str, np.ndarray]) -> None:
        """Raises ValueError if any bands have mismatched shapes."""
        shapes = {}
        for name, arr in bands.items():
            if isinstance(arr, np.ndarray):
                shapes[name] = arr.shape
        if not shapes:
            return
        first_name, first_shape = list(shapes.items())[0]
        for name, shape in shapes.items():
            if shape != first_shape:
                raise ValueError(f"Misaligned band shapes: {first_name} has {first_shape}, but {name} has {shape}")

    def harmonize_band(self, raw_dn: np.ndarray, metadata: Dict[str, Any], acquisition_time: str) -> np.ndarray:
        """
        Converts raw Digital Numbers (DN) to reflectance values [0.0, 1.0].
        Applies baseline offset subtraction if baseline >= 04.00.
        """
        # Convert to float32
        data = raw_dn.astype(np.float32)
        
        offset = self.get_baseline_offset(metadata, acquisition_time)
        
        # Apply offset and scale factor (10000.0)
        # reflectance = (DN - offset) / 10000.0
        harmonized = (data - offset) / 10000.0
        
        # Clip to valid reflectance range
        clipped = np.clip(harmonized, 0.0, 1.0)
        
        if not np.isfinite(clipped).all():
            raise ValueError("Unexpected non-finite values in harmonized band")
            
        return clipped
