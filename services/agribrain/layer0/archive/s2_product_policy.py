"""
Sentinel-2 Product Policy.
Enforces L2A atmospheric status and other Sentinel-2 quality constraints.
"""
from typing import Dict, Any
from .archive_policy import HARMONIZATION_POLICY_VERSION
from .scene_manifest import HistoricalSceneRecord

class S2ProductPolicy:
    def __init__(self):
        self.policy_version = HARMONIZATION_POLICY_VERSION

    def is_product_level_supported(self, product_level: str) -> bool:
        """Only L2A (Bottom-Of-Atmosphere surface reflectance) is supported directly."""
        return product_level.upper() == "L2A"

    def validate_scene_product(self, record: HistoricalSceneRecord) -> bool:
        """Validates that a scene meets S2 product standards."""
        if record.source.lower() != "sentinel2":
            return False
        if not self.is_product_level_supported(record.product_level):
            return False
        return True

    def validate_scene_bands(self, record: HistoricalSceneRecord, bands: Dict[str, Any]) -> bool:
        """Validates S2 band requirements (SCL presence and shape matching)."""
        if record.source.lower() != "sentinel2":
            return True
            
        is_l2a = self.is_product_level_supported(record.product_level)
        if is_l2a and "scl" not in bands:
            raise ValueError("Missing SCL band when L2A product is required")
            
        ref_shape = None
        for name, arr in bands.items():
            if name.lower() != "scl" and hasattr(arr, "shape"):
                ref_shape = arr.shape
                break
                
        if "scl" in bands and ref_shape is not None:
            scl_arr = bands["scl"]
            if hasattr(scl_arr, "shape") and scl_arr.shape != ref_shape:
                raise ValueError("SCL shape mismatch: SCL shape does not match reflectance bands")
                
        return True
