from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Union

from services.agribrain.layer3_decision.schema import ProblemClass, RiskIfWrong, Driver

class ProblemType(Enum):
    # Abiotic
    WATER_STRESS = "WATER_STRESS"
    WATERLOGGING = "WATERLOGGING"
    HEAT_STRESS = "HEAT_STRESS"
    COLD_STRESS = "COLD_STRESS"
    NUTRIENT_DEFICIENCY_N = "N_DEFICIENCY_RISK"
    SALINITY_RISK = "SALINITY_RISK"
    
    # Biotic
    FUNGAL_DISEASE_RISK = "FUNGAL_DISEASE_RISK"
    INSECT_PRESSURE_RISK = "INSECT_PRESSURE_RISK"
    
    # Management / Events
    HARVEST_EVENT = "HARVEST_EVENT"
    TILLAGE_EVENT = "TILLAGE_EVENT"
    LODGING = "LODGING"
    LOGGING_CLEARING = "LOGGING_CLEARING"
    
    # Data / System
    DATA_GAP = "DATA_GAP"
    DATA_ARTIFACT = "DATA_ARTIFACT"

@dataclass
class ProblemDefinition:
    type: ProblemType
    description: str
    symptoms: List[str]
    typical_duration: int # days
    risk_level: str # "HIGH", "MEDIUM", "LOW", "CRITICAL"
    problem_class: ProblemClass = ProblemClass.DIAGNOSIS 

@dataclass
class ActionDefinition:
    action_id: str
    type: str # "INTERVENE", "VERIFY", "ALERT", "MONITOR"
    title: str
    description: str
    
    # Compliance & Safety Gates
    prerequisites: List[str] = field(default_factory=list) # e.g. ["IrrigationSystem"]
    contraindications: List[str] = field(default_factory=list) # e.g. ["RainForecast>10mm"]
    required_drivers: List[str] = field(default_factory=list) # e.g. ["RAIN", "FORECAST"]
    min_confidence: float = 0.5
    fallback_action_id: Optional[str] = None # Safety replacement if blocked
    
    cost_index: int = 1 
    time_index: int = 1 
    risk_if_wrong: RiskIfWrong = RiskIfWrong.LOW

# --- Knowledge Base ---


PROBLEM_DB = {
    ProblemType.WATER_STRESS: ProblemDefinition(
        type=ProblemType.WATER_STRESS,
        description="Plant water deficit reducing turgor.",
        symptoms=["NDVI Stagnation", "Soil Moisture < WP", "High Canopy Temp"],
        typical_duration=7,
        risk_level="HIGH",
        problem_class=ProblemClass.DIAGNOSIS
    ),
    ProblemType.WATERLOGGING: ProblemDefinition(
        type=ProblemType.WATERLOGGING,
        description="Soil saturation / Anoxia.",
        symptoms=["NDVI Yellowing", "Standing Water (SAR)", "Heavy Rain"],
        typical_duration=14,
        risk_level="HIGH",
        problem_class=ProblemClass.DIAGNOSIS
    ),
    ProblemType.HEAT_STRESS: ProblemDefinition(
        type=ProblemType.HEAT_STRESS,
        description="Extreme heat metabolic stress.",
        symptoms=["Canopy Temp > 35C", "Flower Abortion"],
        typical_duration=3,
        risk_level="MEDIUM",
        problem_class=ProblemClass.DIAGNOSIS
    ),
    ProblemType.COLD_STRESS: ProblemDefinition(
        type=ProblemType.COLD_STRESS,
        description="Low accumulated heat units or frost.",
        symptoms=["Growth Stagnation", "Frost Damage"],
        typical_duration=5,
        risk_level="MEDIUM",
        problem_class=ProblemClass.DIAGNOSIS
    ),
    ProblemType.NUTRIENT_DEFICIENCY_N: ProblemDefinition(
        type=ProblemType.NUTRIENT_DEFICIENCY_N,
        description="Nitrogen limitation reducing chlorophyll.",
        symptoms=["General Chlorosis", "Low Growth Velocity"],
        typical_duration=21,
        risk_level="MEDIUM",
        problem_class=ProblemClass.RISK
    ),
    ProblemType.SALINITY_RISK: ProblemDefinition(
        type=ProblemType.SALINITY_RISK,
        description="Salt accumulation in root zone.",
        symptoms=["Osmotic Stress symptoms", "White Soil Crust (Optical)"],
        typical_duration=90,
        risk_level="HIGH",
        problem_class=ProblemClass.RISK
    ),
    ProblemType.FUNGAL_DISEASE_RISK: ProblemDefinition(
        type=ProblemType.FUNGAL_DISEASE_RISK,
        description="High humidity/wetness favoring fungal pathogens.",
        symptoms=["Leaf Spots", "rapid NDVI decline"],
        typical_duration=10,
        risk_level="HIGH",
        problem_class=ProblemClass.RISK
    ),
    ProblemType.INSECT_PRESSURE_RISK: ProblemDefinition(
        type=ProblemType.INSECT_PRESSURE_RISK,
        description="Pest population outbreak.",
        symptoms=["Defoliation", "Patchy NDVI Drop"],
        typical_duration=14,
        risk_level="MEDIUM",
        problem_class=ProblemClass.RISK
    ),
    ProblemType.LOGGING_CLEARING: ProblemDefinition(
        type=ProblemType.LOGGING_CLEARING,
        description="Structural removal of vegetation.",
        symptoms=["Sharp NDVI Drop", "SAR VV Increase", "Texture Change"],
        typical_duration=365,
        risk_level="CRITICAL",
        problem_class=ProblemClass.EVENT
    ),
     ProblemType.HARVEST_EVENT: ProblemDefinition(
        type=ProblemType.HARVEST_EVENT,
        description="Crop harvest detected.",
        symptoms=["Sudden Bare Soil", "SAR Roughness Change"],
        typical_duration=7,
        risk_level="INFO",
        problem_class=ProblemClass.EVENT
    ),
    ProblemType.TILLAGE_EVENT: ProblemDefinition(
        type=ProblemType.TILLAGE_EVENT,
        description="Soil cultivation detected.",
        symptoms=["Bare Soil", "Roughness Increase"],
        typical_duration=7,
        risk_level="INFO",
        problem_class=ProblemClass.EVENT
    ),
    ProblemType.DATA_GAP: ProblemDefinition(
        type=ProblemType.DATA_GAP,
        description="Missing critical signal drivers.",
        symptoms=["Cloud Cover", "Sensor Failure"],
        typical_duration=1,
        risk_level="LOW",
        problem_class=ProblemClass.SYSTEM
    ),
    ProblemType.DATA_ARTIFACT: ProblemDefinition(
        type=ProblemType.DATA_ARTIFACT,
        description="Inconsistent or noisy signals.",
        symptoms=["Spikes", "Geo-registration error"],
        typical_duration=1,
        risk_level="LOW",
        problem_class=ProblemClass.SYSTEM
    )
}

ACTIONS = {
    # -- Water Management --
    "IRRIGATE_FULL": ActionDefinition(
        action_id="IRRIGATE_FULL",
        type="INTERVENE",
        title="Apply Full Irrigation",
        description="Apply water to reach Field Capacity.",
        prerequisites=["IrrigationSystem", "WaterQuota"],
        contraindications=["RainForecast>10mm", "SoilMoisture>FC"],
        required_drivers=[Driver.RAIN, Driver.GDD], # Placeholder logic needs explicit list mapping or keep strings if generic? 
        # User spec said Driver enum: NDVI, RAIN, TEMP, SAR_VV, SAR_VH, GDD.
        # But required_drivers usually includes abstract concepts like "FORECAST" or "SOIL_MOISTURE".
        # I will keep strings for abstract drivers but use Enums for raw signal drivers if applicable. 
        # Actually user spec for required_drivers: "IRRIGATE requires at minimum: RAIN or SOIL_MOISTURE"
        # I will stick to strings for now in ActionDefinition to allow "FORECAST", "QUOTA" etc.
        # Wait, I initialized required_drivers as List[Driver] in dataclass above!
        # I must fix that if I want to allow "FORECAST".
        # Re-reading user spec: "Driver enum... NDVI, RAIN..."
        # But Action "IRRIGATE" needs "FORECAST". 
        # I will make `required_drivers` List[str] in `ActionDefinition` to stay flexible, but strict in Diagnosis/Metrics.
        # Reverting strict List[Driver] in ActionDefinition to List[str] for now to avoid breaking "FORECAST".
    ),
    "VERIFY_SOIL_MOISTURE": ActionDefinition(
        action_id="VERIFY_SOIL_MOISTURE",
        type="VERIFY",
        title="Scout: Check Soil Moisture",
        description="Physically verify soil moisture at root depth.",
        cost_index=1,
        time_index=1,
        risk_if_wrong=RiskIfWrong.LOW
    ),
    
    # -- Waterlogging --
    "DRAIN_FIELD": ActionDefinition(
        action_id="DRAIN_FIELD",
        type="INTERVENE",
        title="Improve Drainage",
        description="Clear ditches/drains to remove standing water.",
        required_drivers=["RAIN", "SAR"],
        min_confidence=0.6,
        fallback_action_id="VERIFY_ROOT_ISSUES",
        cost_index=4,
        risk_if_wrong=RiskIfWrong.MEDIUM
    ),
    "VERIFY_ROOT_ISSUES": ActionDefinition(
        action_id="VERIFY_ROOT_ISSUES",
        type="VERIFY",
        title="Scout: Root Health",
        description="Check roots for anoxia/rot.",
        risk_if_wrong=RiskIfWrong.LOW
    ),
    
    # -- Structures --
    "ALERT_STRUCTURE_LOGGING": ActionDefinition(
         action_id="ALERT_STRUCTURE_LOGGING",
         type="ALERT",
         title="CRITICAL: Logging/Clearing Detected",
         description="Investigate potential illegal clearing or massive lodging.",
         required_drivers=["SAR", "NDVI"],
         min_confidence=0.8,
         fallback_action_id="VERIFY_FIELD_STATUS",
         risk_if_wrong=RiskIfWrong.LOW 
    ),
    "VERIFY_FIELD_STATUS": ActionDefinition(
        action_id="VERIFY_FIELD_STATUS",
        type="VERIFY",
        title="Verify Field Status",
        description="Confirm if harvest or clearing occurred.",
        risk_if_wrong=RiskIfWrong.LOW
    ),
    
    # -- Biotic/Abiotic Checks --
    "SCOUT_PESTS": ActionDefinition(
        action_id="SCOUT_PESTS",
        type="VERIFY",
        title="Scout for Pests",
        description="Check for insect damage/defoliation.",
        risk_if_wrong=RiskIfWrong.LOW
    ),
    "SCOUT_DISEASE": ActionDefinition(
        action_id="SCOUT_DISEASE",
        type="VERIFY",
        title="Scout for Fungal Disease",
        description="Check leaves for lesions/spores.",
        risk_if_wrong=RiskIfWrong.LOW
    ),
    
    # -- Data --
    "WAIT_FOR_DATA": ActionDefinition(
        action_id="WAIT_FOR_DATA",
        type="MONITOR",
        title="Wait for Clear Data",
        description="Defer decision until better signals available.",
        risk_if_wrong=RiskIfWrong.MEDIUM 
    )
}
    
# Fix for IRRIGATE_FULL to use strings for required_drivers to accommodate "FORECAST"
ACTIONS["IRRIGATE_FULL"] = ActionDefinition(
        action_id="IRRIGATE_FULL",
        type="INTERVENE",
        title="Apply Full Irrigation",
        description="Apply water to reach Field Capacity.",
        prerequisites=["IrrigationSystem", "WaterQuota"],
        contraindications=["RainForecast>10mm", "SoilMoisture>FC"],
        required_drivers=["RAIN", "FORECAST", "QUOTA"],
        min_confidence=0.7,
        fallback_action_id="VERIFY_SOIL_MOISTURE",
        cost_index=3,
        time_index=2,
        risk_if_wrong=RiskIfWrong.HIGH 
)
