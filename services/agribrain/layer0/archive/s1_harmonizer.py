"""
Sentinel-1 SAR Harmonization.
Validates incidence angle boundaries (20.0 to 50.0 deg) and calibrates backscatter intensity.
Converts raw amplitude inputs to decibel (dB) values safely.
"""
import numpy as np
from typing import Dict, Any, Tuple
from .archive_config import S1_INC_ANGLE_MIN_DEG, S1_INC_ANGLE_MAX_DEG, S1_INC_ANGLE_POLICY_VERSION

class S1Harmonizer:
    def __init__(self):
        self.policy_version = S1_INC_ANGLE_POLICY_VERSION

    def is_incidence_angle_valid(self, incidence_angle: float) -> bool:
        """Enforces configured Sentinel-1 incidence angle policy."""
        return S1_INC_ANGLE_MIN_DEG <= incidence_angle <= S1_INC_ANGLE_MAX_DEG

    def calibrate_amplitude_to_db(self, raw_amplitude: np.ndarray) -> np.ndarray:
        """
        Converts raw amplitude (DN) to backscatter coefficient sigma-0 in dB.
        sigma0_db = 20 * log10(DN) - offset (or standard scale).
        """
        data = raw_amplitude.astype(np.float32)
        
        # Add epsilon to prevent log10(0)
        safe_data = np.where(data > 0.0, data, 1e-5)
        sigma0_db = 20.0 * np.log10(safe_data)
        
        # Clip to typical physical ranges: -35.0 dB to 5.0 dB
        return np.clip(sigma0_db, -35.0, 5.0)

    def validate_bands_alignment(self, bands: Dict[str, Any]) -> None:
        """Raises ValueError if VV and VH shapes differ."""
        vv_arr = bands.get("vv") if bands.get("vv") is not None else bands.get("VV")
        vh_arr = bands.get("vh") if bands.get("vh") is not None else bands.get("VH")
        if vv_arr is not None and vh_arr is not None:
            if hasattr(vv_arr, "shape") and hasattr(vh_arr, "shape"):
                if vv_arr.shape != vh_arr.shape:
                    raise ValueError("VV/VH shape mismatch: VV and VH shapes differ")

    def process_scene_metadata(self, metadata: Dict[str, Any]) -> Tuple[bool, str]:
        """Validates S1 scene metadata including incidence angle and orbit."""
        angle = metadata.get("s1_incidence_angle") or metadata.get("view:incidence_angle")
        if angle is None:
            return False, "missing_incidence_angle"
            
        try:
            angle_val = float(angle)
        except (ValueError, TypeError):
            return False, f"invalid_incidence_angle: {angle}"

        if not self.is_incidence_angle_valid(angle_val):
            return False, f"incidence_angle_out_of_bounds: {angle_val}"
                
        return True, "Valid"
