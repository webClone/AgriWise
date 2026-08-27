"""
agronomic_knowledge_graph.py - Structured Domain Knowledge Base v2.0
================================================================

Pre-compiled agronomic knowledge for response grounding and validation.
Provides:
  - Crop-specific thresholds (stress levels, optimal ranges)
  - Phenology stage rules (BBCH scale for common crops)
  - Agronomic decision rules (when to irrigate, spray, fertilize)
  - Regional knowledge (Algeria/Mediterranean context)
  - Disease risk models (temperature + humidity thresholds)
  - Kalman state vector interpretation rules (from L0 EKF)
  - Pipeline-aware helpers (L3 water balance, L6 yield, L7 risk)

This replaces hallucination-prone LLM knowledge with hard-coded
ground truth for key agronomic parameters.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class CropThresholds:
    """Agronomic thresholds for a specific crop."""
    crop: str
    # Soil moisture (volumetric %)
    wilting_point: float           # Below this = permanent damage
    stress_threshold: float        # Below this = stress begins
    field_capacity: float          # Optimal upper bound
    waterlogging_threshold: float  # Above this = waterlogging
    # Temperature (C)
    min_germination_temp: float
    optimal_growth_temp_low: float
    optimal_growth_temp_high: float
    heat_stress_temp: float
    frost_damage_temp: float
    # Phenology
    base_temp_gdd: float          # Base temperature for GDD calculation
    gdd_to_heading: float         # Approximate GDD from planting to heading
    gdd_to_maturity: float        # Approximate GDD to maturity
    # Nutrition (kg/ha total season)
    nitrogen_total: Tuple[float, float]   # (min, max) range
    phosphorus_total: Tuple[float, float]
    potassium_total: Tuple[float, float]
    # pH
    optimal_ph_low: float
    optimal_ph_high: float
    # Yield
    potential_yield_t_ha: Tuple[float, float]  # (min, max) range


# ============================================================================
# Pre-compiled Crop Knowledge (9 crops)
# ============================================================================

CROP_KNOWLEDGE: Dict[str, CropThresholds] = {
    "wheat": CropThresholds(
        crop="wheat",
        wilting_point=12.0, stress_threshold=20.0,
        field_capacity=38.0, waterlogging_threshold=45.0,
        min_germination_temp=4.0, optimal_growth_temp_low=15.0,
        optimal_growth_temp_high=25.0, heat_stress_temp=32.0,
        frost_damage_temp=-5.0, base_temp_gdd=0.0,
        gdd_to_heading=1200.0, gdd_to_maturity=1800.0,
        nitrogen_total=(80, 160), phosphorus_total=(30, 60),
        potassium_total=(30, 80), optimal_ph_low=6.0,
        optimal_ph_high=7.5, potential_yield_t_ha=(2.5, 8.0),
    ),
    "durum_wheat": CropThresholds(
        crop="durum_wheat",
        wilting_point=12.0, stress_threshold=18.0,
        field_capacity=36.0, waterlogging_threshold=42.0,
        min_germination_temp=5.0, optimal_growth_temp_low=15.0,
        optimal_growth_temp_high=28.0, heat_stress_temp=34.0,
        frost_damage_temp=-4.0, base_temp_gdd=0.0,
        gdd_to_heading=1100.0, gdd_to_maturity=1700.0,
        nitrogen_total=(80, 140), phosphorus_total=(30, 50),
        potassium_total=(20, 60), optimal_ph_low=6.0,
        optimal_ph_high=8.0, potential_yield_t_ha=(2.0, 6.0),
    ),
    "barley": CropThresholds(
        crop="barley",
        wilting_point=11.0, stress_threshold=18.0,
        field_capacity=35.0, waterlogging_threshold=42.0,
        min_germination_temp=3.0, optimal_growth_temp_low=12.0,
        optimal_growth_temp_high=22.0, heat_stress_temp=30.0,
        frost_damage_temp=-8.0, base_temp_gdd=0.0,
        gdd_to_heading=1100.0, gdd_to_maturity=1600.0,
        nitrogen_total=(60, 120), phosphorus_total=(25, 50),
        potassium_total=(30, 70), optimal_ph_low=6.0,
        optimal_ph_high=8.0, potential_yield_t_ha=(2.0, 7.0),
    ),
    "tomato": CropThresholds(
        crop="tomato",
        wilting_point=10.0, stress_threshold=22.0,
        field_capacity=40.0, waterlogging_threshold=48.0,
        min_germination_temp=11.0, optimal_growth_temp_low=20.0,
        optimal_growth_temp_high=30.0, heat_stress_temp=38.0,
        frost_damage_temp=0.0, base_temp_gdd=10.0,
        gdd_to_heading=800.0, gdd_to_maturity=1400.0,
        nitrogen_total=(120, 200), phosphorus_total=(40, 80),
        potassium_total=(150, 300), optimal_ph_low=6.0,
        optimal_ph_high=6.8, potential_yield_t_ha=(30.0, 100.0),
    ),
    "potato": CropThresholds(
        crop="potato",
        wilting_point=10.0, stress_threshold=25.0,
        field_capacity=42.0, waterlogging_threshold=50.0,
        min_germination_temp=7.0, optimal_growth_temp_low=15.0,
        optimal_growth_temp_high=22.0, heat_stress_temp=30.0,
        frost_damage_temp=-2.0, base_temp_gdd=7.0,
        gdd_to_heading=900.0, gdd_to_maturity=1500.0,
        nitrogen_total=(100, 180), phosphorus_total=(40, 80),
        potassium_total=(120, 250), optimal_ph_low=5.5,
        optimal_ph_high=6.5, potential_yield_t_ha=(15.0, 50.0),
    ),
    "olive": CropThresholds(
        crop="olive",
        wilting_point=8.0, stress_threshold=15.0,
        field_capacity=32.0, waterlogging_threshold=40.0,
        min_germination_temp=10.0, optimal_growth_temp_low=18.0,
        optimal_growth_temp_high=32.0, heat_stress_temp=42.0,
        frost_damage_temp=-7.0, base_temp_gdd=10.0,
        gdd_to_heading=600.0, gdd_to_maturity=2500.0,
        nitrogen_total=(50, 120), phosphorus_total=(20, 40),
        potassium_total=(80, 200), optimal_ph_low=6.5,
        optimal_ph_high=8.5, potential_yield_t_ha=(2.0, 12.0),
    ),
    "date_palm": CropThresholds(
        crop="date_palm",
        wilting_point=6.0, stress_threshold=12.0,
        field_capacity=30.0, waterlogging_threshold=38.0,
        min_germination_temp=18.0, optimal_growth_temp_low=30.0,
        optimal_growth_temp_high=40.0, heat_stress_temp=50.0,
        frost_damage_temp=-5.0, base_temp_gdd=18.0,
        gdd_to_heading=1000.0, gdd_to_maturity=3500.0,
        nitrogen_total=(100, 200), phosphorus_total=(30, 60),
        potassium_total=(100, 300), optimal_ph_low=7.0,
        optimal_ph_high=8.5, potential_yield_t_ha=(4.0, 15.0),
    ),
    "citrus": CropThresholds(
        crop="citrus",
        wilting_point=10.0, stress_threshold=20.0,
        field_capacity=38.0, waterlogging_threshold=45.0,
        min_germination_temp=13.0, optimal_growth_temp_low=20.0,
        optimal_growth_temp_high=32.0, heat_stress_temp=40.0,
        frost_damage_temp=-3.0, base_temp_gdd=13.0,
        gdd_to_heading=700.0, gdd_to_maturity=2800.0,
        nitrogen_total=(120, 250), phosphorus_total=(30, 60),
        potassium_total=(100, 250), optimal_ph_low=5.5,
        optimal_ph_high=7.5, potential_yield_t_ha=(15.0, 50.0),
    ),
    "chickpea": CropThresholds(
        crop="chickpea",
        wilting_point=10.0, stress_threshold=18.0,
        field_capacity=35.0, waterlogging_threshold=40.0,
        min_germination_temp=5.0, optimal_growth_temp_low=15.0,
        optimal_growth_temp_high=25.0, heat_stress_temp=35.0,
        frost_damage_temp=-1.0, base_temp_gdd=5.0,
        gdd_to_heading=900.0, gdd_to_maturity=1400.0,
        nitrogen_total=(20, 40), phosphorus_total=(30, 60),
        potassium_total=(20, 50), optimal_ph_low=6.0,
        optimal_ph_high=8.0, potential_yield_t_ha=(0.8, 3.0),
    ),
    # GAP-8 fix: Added corn/maize — one of the world's top 3 staple crops
    "corn": CropThresholds(
        crop="corn",
        wilting_point=10.0, stress_threshold=22.0,
        field_capacity=40.0, waterlogging_threshold=48.0,
        min_germination_temp=10.0, optimal_growth_temp_low=20.0,
        optimal_growth_temp_high=30.0, heat_stress_temp=38.0,
        frost_damage_temp=-1.0, base_temp_gdd=10.0,
        gdd_to_heading=800.0, gdd_to_maturity=1500.0,
        nitrogen_total=(150, 250), phosphorus_total=(30, 60),
        potassium_total=(40, 100), optimal_ph_low=5.8,
        optimal_ph_high=7.0, potential_yield_t_ha=(5.0, 14.0),
    ),
}


# ============================================================================
# Disease Risk Rules (15 rules across 6 crops)
# ============================================================================

@dataclass
class DiseaseRule:
    """Rule-based disease risk threshold."""
    disease: str
    crop: str
    min_temp: float
    max_temp: float
    min_humidity: float
    rain_trigger_mm: float
    susceptible_stages: List[str]
    risk_description: str


DISEASE_RULES: List[DiseaseRule] = [
    # Wheat diseases
    DiseaseRule("Septoria Leaf Blotch", "wheat", 10, 25, 80, 15,
                ["tillering", "stem_elongation", "booting"],
                "Pycnidiospores splash up from lower leaves during rain events"),
    DiseaseRule("Yellow Rust", "wheat", 5, 15, 70, 10,
                ["tillering", "stem_elongation"],
                "Cool, moist conditions with wind dispersal. Stripe pattern on leaves"),
    DiseaseRule("Brown Rust", "wheat", 15, 25, 80, 10,
                ["heading", "grain_filling"],
                "Warmer temperatures favor Puccinia triticina. Orange-brown pustules"),
    DiseaseRule("Powdery Mildew", "wheat", 15, 22, 60, 0,
                ["tillering", "stem_elongation"],
                "Favored by warm days and cool nights. Does NOT need rain"),
    DiseaseRule("Fusarium Head Blight", "wheat", 20, 30, 85, 20,
                ["heading", "grain_filling"],
                "Most dangerous during anthesis. Produces mycotoxins (DON)"),
    # Barley diseases
    DiseaseRule("Net Blotch", "barley", 10, 25, 75, 10,
                ["tillering", "stem_elongation", "heading"],
                "Spot and net forms. Survives on stubble. Reduces photosynthesis"),
    # Tomato diseases
    DiseaseRule("Late Blight", "tomato", 10, 20, 90, 15,
                ["flowering", "fruiting"],
                "Phytophthora infestans. Rapid spread in cool wet conditions"),
    DiseaseRule("Early Blight", "tomato", 20, 30, 80, 0,
                ["fruiting"],
                "Alternaria solani. Concentric ring lesions. Needs leaf wetness"),
    # Olive diseases
    DiseaseRule("Olive Leaf Spot", "olive", 10, 20, 80, 15,
                ["flowering", "fruiting"],
                "Fusicladium oleagineum. Circular spots on leaves, defoliation"),
    DiseaseRule("Olive Anthracnose", "olive", 15, 25, 85, 20,
                ["fruiting"],
                "Colletotrichum acutatum. Fruit rot, mummification. Fall rains"),
    DiseaseRule("Verticillium Wilt", "olive", 18, 25, 70, 10,
                ["flowering", "fruiting"],
                "Verticillium dahliae. Soil-borne, wilting of branches. No cure"),
    # Citrus diseases
    DiseaseRule("Citrus Canker", "citrus", 20, 35, 80, 15,
                ["flowering", "fruiting"],
                "Xanthomonas citri. Raised corky lesions. Wind-driven rain spread"),
    DiseaseRule("Citrus Greening (HLB)", "citrus", 22, 32, 70, 0,
                ["flowering", "fruiting"],
                "Candidatus Liberibacter. Psyllid vector. Asymmetric yellow mottle"),
    # Chickpea diseases
    DiseaseRule("Ascochyta Blight", "chickpea", 10, 20, 80, 15,
                ["flowering"],
                "Ascochyta rabiei. Most destructive chickpea disease in North Africa"),
    DiseaseRule("Fusarium Wilt", "chickpea", 25, 35, 60, 0,
                ["flowering", "fruiting"],
                "Fusarium oxysporum f.sp. ciceris. Soil-borne vascular wilt"),
]


# ============================================================================
# BBCH Phenology Scale
# ============================================================================

BBCH_STAGES = {
    "wheat": {
        "00-09": {"name": "Germination", "description": "Seed imbibition to coleoptile emergence"},
        "10-19": {"name": "Leaf Development", "description": "1st to 9th leaf unfolded"},
        "20-29": {"name": "Tillering", "description": "Main shoot to 9+ tillers"},
        "30-39": {"name": "Stem Elongation", "description": "Beginning of stem elongation to flag leaf ligule visible"},
        "40-49": {"name": "Booting", "description": "Flag leaf sheath extending to boot swollen"},
        "50-59": {"name": "Heading", "description": "Beginning to end of heading (inflorescence emergence)"},
        "60-69": {"name": "Flowering", "description": "Beginning to end of anthesis"},
        "70-79": {"name": "Grain Development", "description": "Watery to late milk stage"},
        "80-89": {"name": "Ripening", "description": "Early to hard dough"},
        "90-99": {"name": "Senescence", "description": "Over-ripe to harvest"},
    }
}


# ============================================================================
# Regional Knowledge (Algeria / Mediterranean) — Expanded
# ============================================================================

REGIONAL_KNOWLEDGE = {
    "algeria": {
        "climate": "Mediterranean semi-arid",
        "rainy_season": "October to April",
        "dry_season": "May to September",
        "avg_annual_rainfall_mm": {"coastal": "600-800", "inland": "300-500",
                                    "steppe": "200-300", "saharan": "<100"},
        "wheat_planting_window": "October 15 - December 15",
        "wheat_harvest_window": "May - July",
        "common_varieties": {
            "durum": ["Waha", "Simeto", "Chen's", "Mohamed Ben Bachir", "Vitron"],
            "bread": ["Arz", "Hidhab", "Ain Abid"],
            "barley": ["Saida", "Tichedrett", "Jaidor"],
            "olive": ["Chemlal", "Sigoise", "Azeradj", "Limli"],
            "date_palm": ["Deglet Nour", "Ghars", "Degla Beida", "Mech Degla"],
            "citrus": ["Washington Navel", "Thomson", "Valencia", "Clementine"],
            "chickpea": ["ILC 482", "ILC 3279", "Flip 84-92C"],
        },
        "key_risks": [
            "Sirocco wind (hot dry Saharan wind, mainly spring/summer)",
            "Terminal drought during grain filling (April-May)",
            "Late frost during heading (March)",
            "Septoria from winter rains",
            "Soil salinity in irrigated zones (M'zab, Ouargla)",
        ],
        "soil_types": {
            "Mitidja": "Deep alluvial clay-loam, fertile, high water table risk",
            "High Plateaus": "Calcareous, low organic matter, alkaline pH",
            "Tell Atlas": "Red/brown Mediterranean soils, moderate fertility",
            "Hodna Basin": "Saline/gypseous, irrigation drainage issues",
            "Saharan Oases": "Sandy, low organic matter, needs amendment. Date palm adapted",
        },
        "government_programs": [
            "PNDA (Plan National de Developpement Agricole)",
            "FNRDA (Fonds de Regulation et de Developpement Agricole)",
            "Cereals price support (guaranteed floor price)",
            "ITGC (Institut Technique des Grandes Cultures) technical guidance",
        ],
        "wilayas_crop_zones": {
            "cereal_belt": ["Tiaret", "Setif", "Constantine", "Bordj Bou Arreridj", "M'sila", "Mascara", "Sidi Bel Abbes", "Saida"],
            "citrus_belt": ["Blida", "Chlef", "Mostaganem", "Ain Defla"],
            "olive_belt": ["Bejaia", "Tizi Ouzou", "Bouira", "Jijel", "Tlemcen"],
            "date_belt": ["Biskra", "El Oued", "Ouargla", "Ghardaia", "Bechar"],
            "vegetable_belt": ["Tipaza", "Boumerdes", "Ain Defla", "Biskra"],
        },
    }
}


# ============================================================================
# L0 Kalman State Vector Interpretation Rules
# ============================================================================

KALMAN_STATE_RULES = {
    "lai": {
        "index": 0, "label": "Leaf Area Index", "unit": "m\u00b2/m\u00b2",
        "range": (0.0, 10.0),
        "interpretation": {
            (0.0, 0.5): "Very low canopy \u2014 bare soil or early germination",
            (0.5, 1.5): "Low canopy \u2014 seedling or early vegetative stage",
            (1.5, 3.5): "Moderate canopy \u2014 active vegetative growth",
            (3.5, 6.0): "Dense canopy \u2014 peak vegetative stage or heading",
            (6.0, 10.0): "Very dense canopy \u2014 maximum interception, possible lodging risk",
        },
    },
    "biomass": {
        "index": 1, "label": "Structural Biomass", "unit": "relative (SAR-derived)",
        "range": (0.0, 20.0),
        "interpretation": {
            (0.0, 2.0): "Very low biomass \u2014 seedling or stressed",
            (2.0, 6.0): "Low-moderate biomass \u2014 vegetative stage",
            (6.0, 12.0): "Moderate-high biomass \u2014 stem elongation / heading",
            (12.0, 20.0): "High biomass \u2014 peak biomass, grain filling",
        },
    },
    "sm_0_10": {
        "index": 2, "label": "Surface Soil Moisture (0-10cm)", "unit": "vol fraction",
        "range": (0.0, 1.0),
        "interpretation": {
            (0.0, 0.10): "Critically dry surface \u2014 dust conditions",
            (0.10, 0.20): "Dry \u2014 evaporative demand exceeds supply",
            (0.20, 0.35): "Adequate \u2014 normal range for most crops",
            (0.35, 0.50): "Wet \u2014 recently irrigated or rained",
            (0.50, 1.0): "Saturated \u2014 potential waterlogging",
        },
    },
    "sm_10_40": {
        "index": 3, "label": "Root Zone Moisture (10-40cm)", "unit": "vol fraction",
        "range": (0.0, 1.0),
        "interpretation": {
            (0.0, 0.12): "Critically low \u2014 permanent wilting point approached",
            (0.12, 0.22): "Moderate stress \u2014 root water uptake limited",
            (0.22, 0.38): "Adequate \u2014 healthy root zone moisture",
            (0.38, 1.0): "Excess \u2014 percolation or rising water table",
        },
    },
    "canopy_stress": {
        "index": 4, "label": "Canopy Water Stress", "unit": "index [0-1]",
        "range": (0.0, 1.0),
        "interpretation": {
            (0.0, 0.15): "No stress \u2014 optimal transpiration",
            (0.15, 0.35): "Mild stress \u2014 stomatal regulation beginning",
            (0.35, 0.60): "Moderate stress \u2014 yield reduction begins",
            (0.60, 1.0): "Severe stress \u2014 significant yield loss, wilting",
        },
    },
    "phenology_stage": {
        "index": 6, "label": "Phenology Stage Float", "unit": "stage code",
        "range": (0.0, 4.0),
        "interpretation": {
            (0.0, 0.5): "Dormant / pre-emergence",
            (0.5, 1.5): "Vegetative \u2014 tillering, leaf development",
            (1.5, 2.5): "Reproductive \u2014 heading, flowering",
            (2.5, 3.5): "Grain filling / ripening",
            (3.5, 4.0): "Senescence \u2014 maturation and dry-down",
        },
    },
    "stress_thermal": {
        "index": 7, "label": "Thermal Stress", "unit": "index [0-1]",
        "range": (0.0, 1.0),
        "interpretation": {
            (0.0, 0.1): "No thermal stress",
            (0.1, 0.3): "Mild heat or frost stress",
            (0.3, 0.6): "Moderate thermal stress \u2014 yield impact likely",
            (0.6, 1.0): "Severe thermal stress \u2014 heat shock or freeze damage",
        },
    },
    "photosynthetic_efficiency": {
        "index": 8, "label": "Photosynthetic Efficiency", "unit": "index [0-1]",
        "range": (0.0, 1.0),
        "interpretation": {
            (0.0, 0.3): "Severely impaired \u2014 heat/drought shutdown",
            (0.3, 0.6): "Reduced \u2014 stress recovery or partial shutdown",
            (0.6, 0.85): "Normal \u2014 healthy photosynthesis",
            (0.85, 1.0): "Optimal \u2014 peak carbon fixation",
        },
    },
}


def interpret_kalman_state(state_values: List[float], crop: str = "wheat") -> Dict[str, Any]:
    """Interpret a L0 Kalman state vector into human-readable assessments."""
    interpretations = {}
    thresholds = CROP_KNOWLEDGE.get(crop, CROP_KNOWLEDGE.get("wheat"))
    
    for key, rule in KALMAN_STATE_RULES.items():
        idx = rule["index"]
        val = state_values[idx] if idx < len(state_values) else None
        if val is None:
            continue
        interp = {"value": val, "label": rule["label"], "unit": rule["unit"]}
        if "interpretation" in rule:
            for (lo, hi), desc in rule["interpretation"].items():
                if lo <= val <= hi:
                    interp["assessment"] = desc
                    break
        interpretations[key] = interp
    
    # Cross-reference with crop thresholds for water status
    if thresholds and len(state_values) >= 5:
        sm_pct = state_values[2] * 100
        if sm_pct < thresholds.wilting_point:
            interpretations["water_status"] = "CRITICAL"
        elif sm_pct < thresholds.stress_threshold:
            interpretations["water_status"] = "STRESSED"
        elif sm_pct > thresholds.waterlogging_threshold:
            interpretations["water_status"] = "WATERLOGGED"
        else:
            interpretations["water_status"] = "ADEQUATE"
    
    return interpretations


def interpret_gdd_stage(gdd: float, crop: str = "wheat") -> Dict[str, Any]:
    """Report thermal age without publishing a downstream growth stage.

    GDD is an input to Layer 2.  It is not independently sufficient for Layer
    9 to replace the canonical phenology posterior.
    """
    thresholds = CROP_KNOWLEDGE.get(crop, CROP_KNOWLEDGE.get("wheat"))
    if not thresholds:
        return {"stage": "UNKNOWN"}
    
    pct_heading = (gdd / thresholds.gdd_to_heading) * 100
    pct_maturity = (gdd / thresholds.gdd_to_maturity) * 100
    
    return {
        "gdd": gdd,
        "stage": "UNKNOWN",
        "phenology_authority": "unavailable",
        "phenology_evidence_needed_reason": "canonical_layer2_phenology_receipt_required",
        "pct_to_heading": round(min(pct_heading, 100), 1),
        "pct_to_maturity": round(min(pct_maturity, 100), 1),
    }


# ============================================================================
# Water Balance Rules (aligned with L3 water engine)
# ============================================================================

def calculate_pawc(clay_pct: float, sand_pct: float, soc_g_kg: float = 10.0) -> float:
    """Saxton & Rawls (2006) PAWC. Matches L0 GeoContext engine calculation."""
    c = clay_pct / 100.0
    s = sand_pct / 100.0
    om = soc_g_kg * 0.1
    theta_33_star = (-0.251 * s + 0.195 * c + 0.011 * om + 0.006 * (s * om)
                     - 0.027 * (c * om) + 0.452 * (s * c) + 0.299)
    theta_33 = theta_33_star + (1.283 * theta_33_star**2 - 0.374 * theta_33_star - 0.015)
    theta_1500_star = (-0.024 * s + 0.487 * c + 0.006 * om + 0.005 * (s * om)
                       - 0.013 * (c * om) + 0.068 * (s * c) + 0.031)
    theta_1500 = theta_1500_star + (0.14 * theta_1500_star - 0.02)
    return round(max(0, theta_33 - theta_1500) * 1000, 1)


def estimate_water_balance(sm_fraction: float, et0: float, rain_mm: float,
                           crop: str = "wheat", kc: float = 1.0) -> Dict[str, Any]:
    """Simple water balance estimation matching L3 water engine logic."""
    etc = et0 * kc
    net = rain_mm - etc
    thresholds = CROP_KNOWLEDGE.get(crop, CROP_KNOWLEDGE.get("wheat"))
    result = {"et0_mm_day": et0, "etc_mm_day": round(etc, 1),
              "rain_mm": rain_mm, "net_balance_mm": round(net, 1), "sm_fraction": sm_fraction}
    if thresholds:
        sm_pct = sm_fraction * 100
        days_to_stress = (sm_pct - thresholds.stress_threshold) / max(etc, 0.5) if sm_pct > thresholds.stress_threshold else 0
        result["days_to_stress"] = round(max(0, days_to_stress), 1)
        result["deficit_to_fc_mm"] = round((thresholds.field_capacity - sm_pct) * 0.3, 1)
    return result


# ============================================================================
# Yield Loss Rules (aligned with L6 yield engine)
# ============================================================================

YIELD_LOSS_FACTORS = {
    "water_stress": {
        "vegetative": 0.15, "heading": 0.30, "flowering": 0.35,
        "grain_filling": 0.25, "ripening": 0.10,
    },
    "heat_stress": {
        "vegetative": 0.10, "heading": 0.25, "flowering": 0.40, "grain_filling": 0.20,
    },
    "nitrogen_deficiency": {
        "vegetative": 0.15, "tillering": 0.25, "stem_elongation": 0.20, "heading": 0.10,
    },
}


def estimate_yield_loss(stress_type: str, stage: str, stress_intensity: float) -> Dict[str, Any]:
    """Estimate yield loss from stress at a given growth stage."""
    factors = YIELD_LOSS_FACTORS.get(stress_type, {})
    max_loss = factors.get(stage, 0.05)
    actual_loss = max_loss * min(1.0, max(0.0, stress_intensity))
    return {
        "stress_type": stress_type, "stage": stage,
        "stress_intensity": round(stress_intensity, 2),
        "max_possible_loss_pct": round(max_loss * 100, 1),
        "estimated_loss_pct": round(actual_loss * 100, 1),
    }


# ============================================================================
# Irrigation Decision Rules
# ============================================================================

def get_irrigation_recommendation(crop: str, soil_moisture: float,
                                   rain_7d: float, et0_daily: float,
                                   growth_stage: str = "UNKNOWN") -> Dict[str, Any]:
    """Rule-based irrigation recommendation."""
    thresholds = CROP_KNOWLEDGE.get(crop, CROP_KNOWLEDGE.get("wheat"))
    if not thresholds:
        return {"recommend": False, "reason": "Unknown crop"}
    deficit = thresholds.field_capacity - soil_moisture
    days_of_water = (soil_moisture - thresholds.stress_threshold) / max(et0_daily, 0.5)
    result = {
        "soil_moisture_pct": soil_moisture,
        "wilting_point": thresholds.wilting_point,
        "stress_threshold": thresholds.stress_threshold,
        "field_capacity": thresholds.field_capacity,
        "days_until_stress": round(days_of_water, 1),
        "deficit_mm": round(deficit * 0.3, 1),
    }
    if soil_moisture <= thresholds.wilting_point:
        result.update(recommend=True, urgency="CRITICAL",
                     reason=f"Soil moisture ({soil_moisture}%) at/below wilting point ({thresholds.wilting_point}%)",
                     amount_mm=round(deficit * 0.3, 0))
    elif soil_moisture <= thresholds.stress_threshold:
        result.update(recommend=True, urgency="HIGH",
                     reason=f"Soil moisture ({soil_moisture}%) below stress threshold ({thresholds.stress_threshold}%)",
                     amount_mm=round(deficit * 0.25, 0))
    elif days_of_water < 3 and rain_7d < 5:
        result.update(recommend=True, urgency="MEDIUM",
                     reason=f"Only {days_of_water:.0f} days of water remaining, no rain forecast",
                     amount_mm=round(deficit * 0.2, 0))
    elif rain_7d > 20:
        result.update(recommend=False, urgency="NONE",
                     reason=f"Recent rainfall ({rain_7d}mm) provides adequate moisture")
    else:
        result.update(recommend=False, urgency="NONE",
                     reason=f"Soil moisture ({soil_moisture}%) adequate. {days_of_water:.0f} days until stress")
    return result


def get_disease_risk(crop: str, temperature: float, humidity: float,
                     rain_7d: float, stage: str = "UNKNOWN") -> List[Dict[str, Any]]:
    """Rule-based disease risk assessment."""
    risks = []
    for rule in DISEASE_RULES:
        if rule.crop != crop:
            continue
        risk_score = 0.0
        factors = []
        if rule.min_temp <= temperature <= rule.max_temp:
            risk_score += 0.3
            factors.append(f"Temperature {temperature}C in range ({rule.min_temp}-{rule.max_temp}C)")
        if humidity >= rule.min_humidity:
            risk_score += 0.3
            factors.append(f"Humidity {humidity}% >= {rule.min_humidity}%")
        if rain_7d >= rule.rain_trigger_mm:
            risk_score += 0.2
            factors.append(f"Rain {rain_7d}mm >= {rule.rain_trigger_mm}mm trigger")
        if stage in rule.susceptible_stages:
            risk_score += 0.2
            factors.append(f"Stage ({stage}) is susceptible")
        if risk_score >= 0.3:
            level = "HIGH" if risk_score >= 0.7 else "MEDIUM" if risk_score >= 0.5 else "LOW"
            risks.append({"disease": rule.disease, "risk_level": level,
                          "risk_score": round(risk_score, 2), "factors": factors,
                          "description": rule.risk_description})
    return sorted(risks, key=lambda x: -x["risk_score"])


def get_nutrient_recommendation(crop: str, stage: str,
                                soil_n: Optional[float] = None,
                                soil_p: Optional[float] = None) -> Dict[str, Any]:
    """Rule-based nutrient recommendation."""
    thresholds = lookup_crop(crop) or CROP_KNOWLEDGE.get("wheat")
    if not thresholds:
        return {"error": "Unknown crop"}
    n_min, n_max = thresholds.nitrogen_total
    p_min, p_max = thresholds.phosphorus_total
    k_min, k_max = thresholds.potassium_total
    splits = {
        "germination": {"n_fraction": 0.20, "p_fraction": 1.0, "k_fraction": 0.5},
        "tillering": {"n_fraction": 0.40, "p_fraction": 0.0, "k_fraction": 0.0},
        "stem_elongation": {"n_fraction": 0.25, "p_fraction": 0.0, "k_fraction": 0.5},
        "heading": {"n_fraction": 0.15, "p_fraction": 0.0, "k_fraction": 0.0},
    }
    split = splits.get(stage)
    if split is None:
        return {
            "crop": crop,
            "stage": "UNKNOWN",
            "recommendation_available": False,
            "reason": "canonical_layer2_phenology_receipt_required",
        }
    target_n = (n_min + n_max) / 2
    return {
        "crop": crop, "stage": stage,
        "nitrogen_total_range_kg_ha": f"{n_min}-{n_max}",
        "nitrogen_this_stage_kg_ha": round(target_n * split["n_fraction"], 1),
        "phosphorus_total_range_kg_ha": f"{p_min}-{p_max}",
        "potassium_total_range_kg_ha": f"{k_min}-{k_max}",
        "application_note": f"Apply {split['n_fraction']*100:.0f}% of total N at {stage}",
        "urea_equivalent_kg_ha": round(target_n * split["n_fraction"] / 0.46, 1),
    }


# ============================================================================
# Knowledge Lookup API
# ============================================================================

def lookup_crop(crop_name: str) -> Optional[CropThresholds]:
    """Look up crop thresholds by name (fuzzy matching with aliases).
    Compatible with all 200+ crop types from the Crop Registry."""
    name = crop_name.lower().strip().replace(" ", "_").replace("-", "_")
    if name in CROP_KNOWLEDGE:
        return CROP_KNOWLEDGE[name]
    aliases = {
        "ble": "wheat", "ble_dur": "durum_wheat", "orge": "barley",
        "tomate": "tomato", "pomme_de_terre": "potato", "olivier": "olive",
        "palmier_dattier": "date_palm", "agrumes": "citrus", "pois_chiche": "chickpea",
        "soft_wheat": "wheat", "bread_wheat": "wheat", "hard_wheat": "durum_wheat",
        "orange": "citrus", "mandarin": "citrus", "lemon": "citrus",
        "dates": "date_palm", "palm": "date_palm",
        "maize": "corn", "mais": "corn", "sweet_corn": "corn",  # GAP-8 fix
    }
    if name in aliases:
        resolved = aliases[name]
        if resolved in CROP_KNOWLEDGE:
            return CROP_KNOWLEDGE[resolved]
        name = resolved

    # First, try substring/fuzzy match on existing knowledge base
    for key, val in CROP_KNOWLEDGE.items():
        if name in key or key in name:
            return val

    # If not in the pre-compiled 9 crops, dynamically compile from the 200+ Crop Registry
    try:
        from crop_database.registry import CROP_REGISTRY, get_crop, resolve_crop_code
        canonical_code = resolve_crop_code(name)
        if canonical_code in CROP_KNOWLEDGE:
            return CROP_KNOWLEDGE[canonical_code]

        if canonical_code in CROP_REGISTRY:
            spec = get_crop(canonical_code)
            
            # 1. Soil moisture defaults based on water needs class
            if spec.water_needs == "low":
                wp, st, fc, wl = 8.0, 15.0, 32.0, 40.0
            elif spec.water_needs == "high":
                wp, st, fc, wl = 12.0, 24.0, 40.0, 48.0
            else: # "medium"
                wp, st, fc, wl = 10.0, 20.0, 36.0, 44.0
                
            # 2. Temperature and frost defaults based on architecture class
            if spec.architecture == "tropical_tree":
                frost = -2.0
                germ = 15.0
            elif spec.architecture == "vegetable":
                frost = 0.0
                germ = 8.0
            elif spec.architecture == "cereal":
                frost = -6.0
                germ = 4.0
            else: # "legume", "cotton", "perennial"
                frost = -4.0
                germ = 6.0
                
            # Heat stress temperature
            heat = round(spec.optimal_temp_max + 8.0, 1)
            heat = max(30.0, min(50.0, heat))
            
            # 3. Phenology GDD mapping dynamically from growing days and base temperature
            avg_temp = (spec.optimal_temp_min + spec.optimal_temp_max) / 2.0
            daily_gdd = max(2.0, avg_temp - spec.gdd_base_temp)
            gdd_maturity = round(daily_gdd * spec.growing_days, 1)
            gdd_heading = round(gdd_maturity * 0.6, 1)
            
            # 4. Nutrition ranges based on yield removal rates
            if spec.is_legume:
                n_total = (20.0, 40.0)
            else:
                n_need = spec.removal_n * spec.attainable_yield_t_ha
                n_total = (round(n_need * 0.8, 1), round(min(n_need * 1.5, spec.n_ceiling_kg_ha), 1))
                
            p_need = spec.removal_p * spec.attainable_yield_t_ha
            p_total = (round(p_need * 0.8, 1), round(p_need * 1.5, 1))
            
            k_need = spec.removal_k * spec.attainable_yield_t_ha
            k_total = (round(k_need * 0.8, 1), round(k_need * 1.5, 1))
            
            # 5. pH defaults by crop architecture
            if spec.architecture == "legume":
                ph_low, ph_high = 6.0, 7.5
            elif spec.architecture == "vegetable":
                ph_low, ph_high = 6.0, 6.8
            elif spec.architecture == "cereal":
                ph_low, ph_high = 6.0, 7.5
            elif spec.architecture == "tropical_tree":
                ph_low, ph_high = 6.0, 8.0
            else:
                ph_low, ph_high = 6.0, 7.8
                
            # 6. Potential yield range
            y_low = round(spec.attainable_yield_t_ha * 0.6, 1)
            y_high = round(spec.attainable_yield_t_ha * 1.3, 1)
            
            dynamic_thresh = CropThresholds(
                crop=canonical_code,
                wilting_point=wp,
                stress_threshold=st,
                field_capacity=fc,
                waterlogging_threshold=wl,
                min_germination_temp=germ,
                optimal_growth_temp_low=spec.optimal_temp_min,
                optimal_growth_temp_high=spec.optimal_temp_max,
                heat_stress_temp=heat,
                frost_damage_temp=frost,
                base_temp_gdd=spec.gdd_base_temp,
                gdd_to_heading=gdd_heading,
                gdd_to_maturity=gdd_maturity,
                nitrogen_total=n_total,
                phosphorus_total=p_total,
                potassium_total=k_total,
                optimal_ph_low=ph_low,
                optimal_ph_high=ph_high,
                potential_yield_t_ha=(y_low, y_high),
            )
            
            # Cache dynamically to speed up subsequent queries
            CROP_KNOWLEDGE[canonical_code] = dynamic_thresh
            return dynamic_thresh
    except Exception as e:
        print(f"Dynamic crop lookup failed: {e}")


def get_region_info(region: str = "algeria") -> Dict[str, Any]:
    """Get regional agronomic knowledge."""
    return REGIONAL_KNOWLEDGE.get(region.lower(), {})


def get_pipeline_layer_summary() -> Dict[str, str]:
    """Summary of each pipeline layer for chat system awareness."""
    return {
        "L0": "Sensors & EKF: 9-variable Kalman state (LAI, biomass, soil moisture, stress, GDD, phenology, photosynthetic efficiency). 30 engines.",
        "L1": "Fusion: Merges Sentinel-2 optical, Sentinel-1 SAR, weather, IoT sensors into unified FieldTensor.",
        "L2": "Vegetation Intelligence: NDVI curve fitting, phenology staging, anomaly detection, growth velocity, NPP.",
        "L3": "Decision & Diagnosis: Water balance, ET0/ETcrop, diagnoses (probability + confidence), water deficit.",
        "L4": "Nutrient Intelligence: N/P/K deficiency probabilities, deficit estimates, split application plans.",
        "L5": "Biotic Threats: Bayesian disease inference, chemical degradation, spray drift, CNN leaf diagnosis.",
        "L6": "Yield & Profit: P10/P50/P90 yield forecasts, harvest optimizer, gross margin, intervention ROI.",
        "L7": "Risk & Climate: Composite risk score, climate shocks (heatwave/frost/flood), trust monitor, what-if scenarios.",
        "L8": "Prescriptive: Actionable tasks with dosages, safety gates (spray drift, compaction, IPM cascade), adoption model.",
        "L9": "Interface: Chat, explanations, adaptive prompting, multilingual support.",
        "L10": "SIRE: Spatial maps, zone management, GeoJSON export, explainability VaR.",
    }
