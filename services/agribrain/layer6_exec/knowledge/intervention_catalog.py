"""
Layer 6 Knowledge Base — Intervention Catalog & Cost Models

Agronomic knowledge for intervention planning:
  - Crop-specific intervention templates
  - Cost estimation models (per-hectare)
  - Timing windows by phenology stage
  - Resource requirements
  - Expected impact curves

References:
  - FAO Crop Production Guidelines
  - USDA Extension Service intervention standards
  - European Commission IPM Directive 2009/128/EC

This module provides the KNOWLEDGE, not the LOGIC.
The logic lives in the engines; this module provides the data they consume.
"""

from typing import Dict, Any, List, Optional
from layer6_exec.schema import InterventionDomain, ResourceType


# ============================================================================
# Intervention Templates
# ============================================================================

INTERVENTION_TEMPLATES: Dict[str, Dict[str, Any]] = {
    # ── Irrigation Interventions ──────────────────────────────────────────
    "IRR_DEFICIT_CORRECTION": {
        "domain": InterventionDomain.IRRIGATION,
        "title": "Deficit Irrigation Correction",
        "instructions": "Apply supplemental irrigation to restore soil moisture to field capacity in the root zone (0-60cm). Target 70-80% of available water capacity.",
        "cost_per_ha_eur": 25.0,
        "resource_type": ResourceType.WATER,
        "resource_qty_per_ha": 30.0,  # mm
        "resource_unit": "mm",
        "timing_urgency_days": 3,
        "expected_impact": 0.6,
        "applicable_stages": ["VEGETATIVE", "REPRODUCTIVE", "FLOWERING"],
    },
    "IRR_STRESS_PREVENTION": {
        "domain": InterventionDomain.IRRIGATION,
        "title": "Pre-emptive Stress Prevention Irrigation",
        "instructions": "Light irrigation (15-20mm) to prevent onset of water stress before critical reproductive stage.",
        "cost_per_ha_eur": 15.0,
        "resource_type": ResourceType.WATER,
        "resource_qty_per_ha": 18.0,
        "resource_unit": "mm",
        "timing_urgency_days": 5,
        "expected_impact": 0.4,
        "applicable_stages": ["VEGETATIVE", "REPRODUCTIVE"],
    },

    # ── Nutrient Interventions ────────────────────────────────────────────
    "NUT_N_TOPDRESS": {
        "domain": InterventionDomain.NUTRIENT,
        "title": "Nitrogen Top-Dressing",
        "instructions": "Apply split nitrogen top-dressing at recommended rate. Use urea or UAN solution. Apply early morning or late afternoon to minimize volatilization losses.",
        "cost_per_ha_eur": 80.0,
        "resource_type": ResourceType.CHEMICAL,
        "resource_qty_per_ha": 40.0,  # kg N/ha
        "resource_unit": "kg_N/ha",
        "timing_urgency_days": 7,
        "expected_impact": 0.7,
        "applicable_stages": ["VEGETATIVE", "REPRODUCTIVE"],
    },
    "NUT_PK_CORRECTION": {
        "domain": InterventionDomain.NUTRIENT,
        "title": "P/K Foliar Correction",
        "instructions": "Apply foliar phosphorus-potassium supplement. Target deficiency symptoms visible in lower canopy.",
        "cost_per_ha_eur": 45.0,
        "resource_type": ResourceType.CHEMICAL,
        "resource_qty_per_ha": 5.0,  # L/ha
        "resource_unit": "L/ha",
        "timing_urgency_days": 10,
        "expected_impact": 0.4,
        "applicable_stages": ["VEGETATIVE", "REPRODUCTIVE", "FLOWERING"],
    },
    "NUT_MICRONUTRIENT": {
        "domain": InterventionDomain.NUTRIENT,
        "title": "Micronutrient Foliar Spray",
        "instructions": "Apply chelated micronutrient solution (Zn, Mn, Fe, B) via foliar spray. Target rate: consult soil analysis.",
        "cost_per_ha_eur": 35.0,
        "resource_type": ResourceType.CHEMICAL,
        "resource_qty_per_ha": 3.0,
        "resource_unit": "L/ha",
        "timing_urgency_days": 14,
        "expected_impact": 0.3,
        "applicable_stages": ["VEGETATIVE", "REPRODUCTIVE"],
    },

    # ── Phytosanitary Interventions ───────────────────────────────────────
    "PHYTO_FUNGICIDE_CLASS": {
        "domain": InterventionDomain.PHYTOSANITARY,
        "title": "Fungicide Application (Class-Level)",
        "instructions": "Apply registered fungicide appropriate for detected disease class. Consult local extension service for approved products. Respect pre-harvest interval.",
        "cost_per_ha_eur": 60.0,
        "resource_type": ResourceType.CHEMICAL,
        "resource_qty_per_ha": 2.0,
        "resource_unit": "L/ha",
        "timing_urgency_days": 3,
        "expected_impact": 0.75,
        "applicable_stages": ["VEGETATIVE", "REPRODUCTIVE", "FLOWERING", "MATURATION"],
    },
    "PHYTO_INSECTICIDE_CLASS": {
        "domain": InterventionDomain.PHYTOSANITARY,
        "title": "Insecticide Application (Class-Level)",
        "instructions": "Apply registered insecticide for detected pest class. Use IPM thresholds — only treat if economic threshold exceeded. Prefer selective products.",
        "cost_per_ha_eur": 50.0,
        "resource_type": ResourceType.CHEMICAL,
        "resource_qty_per_ha": 1.5,
        "resource_unit": "L/ha",
        "timing_urgency_days": 5,
        "expected_impact": 0.65,
        "applicable_stages": ["VEGETATIVE", "REPRODUCTIVE", "FLOWERING"],
    },
    "PHYTO_HERBICIDE_CLASS": {
        "domain": InterventionDomain.PHYTOSANITARY,
        "title": "Herbicide Application (Class-Level)",
        "instructions": "Apply post-emergence herbicide for detected weed pressure. Follow label rates. Observe buffer zones and wind restrictions.",
        "cost_per_ha_eur": 40.0,
        "resource_type": ResourceType.CHEMICAL,
        "resource_qty_per_ha": 2.5,
        "resource_unit": "L/ha",
        "timing_urgency_days": 7,
        "expected_impact": 0.6,
        "applicable_stages": ["VEGETATIVE", "REPRODUCTIVE"],
    },

    # ── Mechanical Interventions ──────────────────────────────────────────
    "MECH_CULTIVATION": {
        "domain": InterventionDomain.MECHANICAL,
        "title": "Mechanical Weed Cultivation",
        "instructions": "Inter-row mechanical cultivation to suppress weed pressure. Depth: 3-5cm. Avoid root zone damage.",
        "cost_per_ha_eur": 30.0,
        "resource_type": ResourceType.EQUIPMENT,
        "resource_qty_per_ha": 1.0,
        "resource_unit": "passes",
        "timing_urgency_days": 10,
        "expected_impact": 0.5,
        "applicable_stages": ["VEGETATIVE"],
    },

    # ── Monitoring Interventions ──────────────────────────────────────────
    "MON_FIELD_SCOUT": {
        "domain": InterventionDomain.MONITORING,
        "title": "Field Scouting Visit",
        "instructions": "Conduct systematic field walk. Observe plant health, pest/disease symptoms, weed pressure, soil surface conditions. Photograph anomalies.",
        "cost_per_ha_eur": 10.0,
        "resource_type": ResourceType.LABOR,
        "resource_qty_per_ha": 0.5,
        "resource_unit": "hours",
        "timing_urgency_days": 3,
        "expected_impact": 0.2,  # Scouting itself doesn't fix anything, but enables future interventions
        "applicable_stages": ["VEGETATIVE", "REPRODUCTIVE", "FLOWERING", "MATURATION"],
    },
    "MON_PHOTO_VERIFICATION": {
        "domain": InterventionDomain.MONITORING,
        "title": "Photo-Based Verification",
        "instructions": "Take close-up photos of symptomatic plants. Capture leaf spots, discoloration, pest damage, weed species. Upload for AI analysis.",
        "cost_per_ha_eur": 5.0,
        "resource_type": ResourceType.LABOR,
        "resource_qty_per_ha": 0.25,
        "resource_unit": "hours",
        "timing_urgency_days": 2,
        "expected_impact": 0.15,
        "applicable_stages": ["VEGETATIVE", "REPRODUCTIVE", "FLOWERING", "MATURATION"],
    },
    "MON_SOIL_SAMPLE": {
        "domain": InterventionDomain.MONITORING,
        "title": "Soil Sampling for Lab Analysis",
        "instructions": "Collect soil samples from representative locations. 15-20 cores per composite sample. Depth: 0-30cm. Submit for N/P/K/pH/EC analysis.",
        "cost_per_ha_eur": 15.0,
        "resource_type": ResourceType.LABOR,
        "resource_qty_per_ha": 1.0,
        "resource_unit": "hours",
        "timing_urgency_days": 14,
        "expected_impact": 0.1,
        "applicable_stages": ["VEGETATIVE", "REPRODUCTIVE", "POST_HARVEST"],
    },
    "MON_TRAP_INSTALL": {
        "domain": InterventionDomain.MONITORING,
        "title": "Install Pest Monitoring Traps",
        "instructions": "Deploy pheromone or sticky traps for target pest species. Place at field borders and interior. Check weekly.",
        "cost_per_ha_eur": 8.0,
        "resource_type": ResourceType.EQUIPMENT,
        "resource_qty_per_ha": 0.5,
        "resource_unit": "units",
        "timing_urgency_days": 7,
        "expected_impact": 0.1,
        "applicable_stages": ["VEGETATIVE", "REPRODUCTIVE", "FLOWERING"],
    },
}


# ============================================================================
# Cost of Inaction Models
# ============================================================================

COST_OF_INACTION: Dict[str, Dict[str, float]] = {
    # problem_id or threat_id → estimated yield loss % and EUR/ha
    "WATER_STRESS": {"yield_loss_pct": 15.0, "eur_per_ha": 120.0},
    "WATERLOGGING": {"yield_loss_pct": 20.0, "eur_per_ha": 160.0},
    "NITROGEN_DEFICIENCY": {"yield_loss_pct": 25.0, "eur_per_ha": 200.0},
    "PHOSPHORUS_DEFICIENCY": {"yield_loss_pct": 10.0, "eur_per_ha": 80.0},
    "POTASSIUM_DEFICIENCY": {"yield_loss_pct": 8.0, "eur_per_ha": 65.0},
    "FUNGAL_LEAF_SPOT": {"yield_loss_pct": 12.0, "eur_per_ha": 95.0},
    "FUNGAL_RUST": {"yield_loss_pct": 18.0, "eur_per_ha": 145.0},
    "DOWNY_MILDEW": {"yield_loss_pct": 20.0, "eur_per_ha": 160.0},
    "POWDERY_MILDEW": {"yield_loss_pct": 10.0, "eur_per_ha": 80.0},
    "BACTERIAL_BLIGHT": {"yield_loss_pct": 15.0, "eur_per_ha": 120.0},
    "CHEWING_INSECTS": {"yield_loss_pct": 12.0, "eur_per_ha": 95.0},
    "SUCKING_INSECTS": {"yield_loss_pct": 8.0, "eur_per_ha": 65.0},
    "BORERS": {"yield_loss_pct": 22.0, "eur_per_ha": 175.0},
    "WEED_PRESSURE": {"yield_loss_pct": 20.0, "eur_per_ha": 160.0},
    "LODGING_RISK": {"yield_loss_pct": 30.0, "eur_per_ha": 240.0},
}


# ============================================================================
# Conflict Rules
# ============================================================================

CONFLICT_RULES: List[Dict[str, Any]] = [
    {
        "type": "IRRIGATION_VS_FUNGAL",
        "condition_a": {"layer": "L3", "problem_ids": ["WATER_STRESS"]},
        "condition_b": {"layer": "L5", "threat_ids": ["FUNGAL_LEAF_SPOT", "FUNGAL_RUST", "DOWNY_MILDEW"]},
        "threshold_b": 0.5,  # L5 threat probability threshold
        "resolution": "PRIORITIZE_SAFETY",
        "rationale": "High fungal risk: avoid overhead irrigation. Prefer drip/subsurface if available. Otherwise delay and scout.",
    },
    {
        "type": "NITROGEN_VS_LODGING",
        "condition_a": {"layer": "L4", "nutrient": "N"},
        "condition_b": {"layer": "L3", "problem_ids": ["LODGING_RISK"]},
        "threshold_b": 0.4,
        "resolution": "COMPROMISE",
        "rationale": "Lodging risk present: reduce nitrogen rate by 20-30% and apply growth regulator if available.",
    },
    {
        "type": "HERBICIDE_VS_CROP_STAGE",
        "condition_a": {"layer": "L5", "threat_ids": ["WEED_PRESSURE"]},
        "condition_b": {"layer": "L2", "late_stages": ["FLOWERING", "MATURATION"]},
        "threshold_b": 0.0,  # Any late stage
        "resolution": "SUPPRESS_LOWER",
        "rationale": "Crop too advanced for herbicide application. Mechanical cultivation or hand-weeding only.",
    },
]


# ============================================================================
# Phenology-Aware Timing Multipliers
# ============================================================================

TIMING_URGENCY_BY_STAGE: Dict[str, float] = {
    "EMERGENCE": 0.6,       # Low urgency, plant can recover
    "VEGETATIVE": 0.7,
    "REPRODUCTIVE": 1.0,    # Highest urgency — yield-forming period
    "FLOWERING": 1.0,
    "GRAIN_FILL": 0.9,
    "MATURATION": 0.4,      # Too late for most interventions
    "SENESCENCE": 0.2,
    "POST_HARVEST": 0.1,
}


def get_timing_urgency(stage: str) -> float:
    """Get urgency multiplier for a phenology stage."""
    return TIMING_URGENCY_BY_STAGE.get(stage.upper(), 0.7)
