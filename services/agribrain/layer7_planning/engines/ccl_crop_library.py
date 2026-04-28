from dataclasses import dataclass, field
from typing import Dict, List, Optional
from layer7_planning.schema import SuitabilityDriver

@dataclass
class CultivarOption:
    name: str # e.g. "Spunta", "Desiree"
    maturity_days: int # Days from plant to harvest
    base_yield_t_ha: float
    disease_resistance: List[str] # e.g. ["late_blight", "nematode"]
    water_demand_class: str # "HIGH", "MODERATE", "LOW"

@dataclass
class CropProfile:
    id: str # internal key
    display_name: str
    
    # Thermal Requirements
    base_temp_c: float
    optimal_temp_min_c: float
    optimal_temp_max_c: float
    frost_sensitivity_c: float
    flowering_heat_stress_c: float
    target_gdd: float # Growing degree days required to mature
    
    # Soil & Operations
    preferred_soil_type: List[str]
    max_planting_rain_7d_mm: float # Workability limit (compaction / rot risk)
    min_planting_temp_c: float # Required for sprouting/germination
    
    # Calendars (Agro-climatic regions mapping -> [start_month, end_month])
    planting_windows: Dict[str, List[Dict[str, int]]] 
    
    # Cultivars available
    varieties: List[CultivarOption]
    
    # Economics (Base defaults, overridden by user context)
    default_price_per_ton: float 
    base_production_cost_per_ha: float 

# --- Knowledge Base (Deterministic / Versioned) ---

CROP_DATABASE: Dict[str, CropProfile] = {
    "potato": CropProfile(
        id="potato",
        display_name="Potato (Solanum tuberosum)",
        base_temp_c=7.0,
        optimal_temp_min_c=15.0,
        optimal_temp_max_c=25.0,
        frost_sensitivity_c=-1.0,
        flowering_heat_stress_c=28.0, # Tuberization drops above 28C
        target_gdd=1400.0,
        preferred_soil_type=["loam", "sandy loam", "silt loam"],
        max_planting_rain_7d_mm=40.0, # Rot risk if too wet
        min_planting_temp_c=8.0, 
        planting_windows={
            "north_africa": [
                {"start_month": 1, "end_month": 3},   # Spring Spunta
                {"start_month": 8, "end_month": 10}   # Late Arrier season
            ]
        },
        varieties=[
             CultivarOption("Spunta", 110, 35.0, ["drought_tolerant"], "MODERATE"),
             CultivarOption("Desiree", 120, 30.0, ["scab"], "HIGH")
        ],
        default_price_per_ton=400.0,
        base_production_cost_per_ha=3000.0
    ),
    "wheat": CropProfile(
        id="wheat",
        display_name="Wheat (Triticum aestivum)",
        base_temp_c=0.0,
        optimal_temp_min_c=10.0,
        optimal_temp_max_c=25.0,
        frost_sensitivity_c=-8.0,
        flowering_heat_stress_c=30.0,
        target_gdd=2000.0,
        preferred_soil_type=["loam", "clay loam", "heavy clay"],
        max_planting_rain_7d_mm=55.0, # machinery trafficability is the actual limit for wheat
        min_planting_temp_c=4.0,
        planting_windows={
            "north_africa": [
                {"start_month": 10, "end_month": 12}
            ]
        },
        varieties=[
             CultivarOption("Vitron (Durum)", 150, 4.0, ["rust"], "LOW"),
             CultivarOption("HD2967", 140, 5.0, [], "MODERATE")
        ],
        default_price_per_ton=300.0,
        base_production_cost_per_ha=800.0
    )
}

def get_crop_profile(crop_id: str) -> Optional[CropProfile]:
    """Retrieve the core agronomic priors for a specific crop."""
    return CROP_DATABASE.get(crop_id.lower().strip(), None)
