
from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class CropProfile:
    name: str
    gdd_base_temp: float
    
    # Vulnerability Factors (0.0 - 1.0)
    # Higher = More sensitive to stress at this stage
    water_stress_sensitivity: Dict[str, float]
    # e.g. {"VEGETATIVE": 0.3, "REPRODUCTIVE": 0.9}
    
    # Expected Parameters
    max_root_depth_cm: float
    kc_init: float
    kc_mid: float
    kc_end: float

CROP_DB = {
    "generic_cereal": CropProfile(
        name="Generic Cereal",
        gdd_base_temp=10.0,
        water_stress_sensitivity={
            "BARE_SOIL": 0.0,
            "EMERGENCE": 0.5,
            "VEGETATIVE": 0.4,
            "REPRODUCTIVE": 0.9, # Critical period
            "SENESCENCE": 0.1,
            "HARVESTED": 0.0
        },
        max_root_depth_cm=120.0,
        kc_init=0.3,
        kc_mid=1.15,
        kc_end=0.4
    ),
    "corn": CropProfile(
        name="Corn (Maize)",
        gdd_base_temp=10.0,
        water_stress_sensitivity={
            "BARE_SOIL": 0.0,
            "EMERGENCE": 0.6,
            "VEGETATIVE": 0.5,
            "REPRODUCTIVE": 1.0, # Silking/Pollination is extremely sensitive
            "SENESCENCE": 0.2,
            "HARVESTED": 0.0
        },
        max_root_depth_cm=150.0,
        kc_init=0.3,
        kc_mid=1.2,
        kc_end=0.6 # Silage vs Grain differs
    )
}

def get_crop_profile(crop_name: str) -> CropProfile:
    key = crop_name.lower().replace(" ", "_")
    return CROP_DB.get(key, CROP_DB["generic_cereal"])
