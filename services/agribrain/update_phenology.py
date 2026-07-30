import sys
import os

from layer7_planning.engines.ccl_crop_library import _CROP_DATA

archetype_mapping = {
    # Cereal / Grass
    "corn": "CEREAL", "wheat": "CEREAL", "barley": "CEREAL", "rice": "CEREAL", "sorghum": "CEREAL",
    "pearl_millet": "CEREAL", "finger_millet": "CEREAL", "teff": "CEREAL", "sugarcane": "CEREAL",
    "canola": "CEREAL", "mustard": "CEREAL", "sunflower": "CEREAL", "safflower": "CEREAL", "sesame": "CEREAL", "flax": "CEREAL",
    
    # Legume
    "soybean": "LEGUME", "chickpea": "LEGUME", "lentil": "LEGUME", "fava_bean": "LEGUME",
    "cowpea": "LEGUME", "groundnut": "LEGUME", "pigeon_pea": "LEGUME", "bambara_groundnut": "LEGUME",
    "alfalfa": "LEGUME",
    
    # Root & Tuber
    "potato": "ROOT", "cassava": "ROOT", "yam": "ROOT", "sweet_potato": "ROOT", "taro": "ROOT",
    "carrot": "ROOT", "beetroot": "ROOT", "radish": "ROOT", "turnip": "ROOT", "garlic": "ROOT", "onion": "ROOT",
    "saffron": "ROOT",
    
    # Fruit / Fruiting Veg
    "tomato": "FRUIT", "eggplant": "FRUIT", "bell_pepper": "FRUIT", "chili_pepper": "FRUIT",
    "cucumber": "FRUIT", "zucchini": "FRUIT", "pumpkin": "FRUIT", "watermelon": "FRUIT", "melon": "FRUIT",
    "okra": "FRUIT", "strawberry": "FRUIT", "blueberry": "FRUIT", "raspberry": "FRUIT", "blackberry": "FRUIT",
    "grape": "FRUIT", "pineapple": "FRUIT", "cumin": "FRUIT",
    
    # Tree & Plantation
    "apple": "TREE", "pear": "TREE", "citrus_orange": "TREE", "citrus_lemon": "TREE", "mango": "TREE",
    "papaya": "TREE", "avocado": "TREE", "cashew": "TREE", "macadamia": "TREE", "olive": "TREE",
    "date_palm": "TREE", "fig": "TREE", "almond": "TREE", "pomegranate": "TREE", "carob": "TREE",
    "argan": "TREE", "cocoa": "TREE", "coffee_arabica": "TREE", "coffee_robusta": "TREE", "rubber": "TREE",
    "tea": "TREE", "banana": "TREE", "plantain": "TREE",
    
    # Fiber
    "cotton": "FIBER", "hemp": "FIBER", "jute": "FIBER", "sisal": "FIBER",
    
    # Leafy / Stalk
    "cabbage": "LEAFY", "broccoli": "LEAFY", "cauliflower": "LEAFY", "spinach": "LEAFY",
    "lettuce": "LEAFY", "celery": "LEAFY", "asparagus": "LEAFY", "artichoke": "LEAFY",
    "coriander": "LEAFY"
}

# Auto-assign any missing crops from _CROP_DATA
for row in _CROP_DATA:
    cid = row[0]
    if cid not in archetype_mapping:
        archetype_mapping[cid] = "CEREAL" # fallback

content = """\"\"\"
Layer 8 Engine: Phenology-Aware Dosing v8.2.0
=============================================
BBCH-scale crop stage lookup with absorption coefficients.
Scales application rates to match actual physiological demand.
\"\"\"
import logging
from typing import Dict, Optional, List
from layer8_prescriptive.schema import (
    ActionCard, ActionType, BBCHStageInfo, RateRange,
)

logger = logging.getLogger(__name__)

# Archetype BBCH Tables: (archetype, stage) -> parameters
_ARCHETYPE_BBCH = {
    ("CEREAL", "EMERGENCE"):     {"bbch": 10, "name": "Seedling",   "critical": False, "absorption": {"N": 0.03, "P": 0.04, "K": 0.03}, "water": 0.4, "growth": 0.3},
    ("CEREAL", "VEGETATIVE"):    {"bbch": 25, "name": "Tillering",  "critical": False, "absorption": {"N": 0.20, "P": 0.15, "K": 0.18}, "water": 0.7, "growth": 0.8},
    ("CEREAL", "REPRODUCTIVE"):  {"bbch": 61, "name": "Anthesis",   "critical": True,  "absorption": {"N": 0.65, "P": 0.55, "K": 0.70}, "water": 1.6, "growth": 0.9},
    ("CEREAL", "SENESCENCE"):    {"bbch": 87, "name": "Dough",      "critical": False, "absorption": {"N": 0.95, "P": 0.90, "K": 0.92}, "water": 0.4, "growth": 0.1},

    ("LEGUME", "EMERGENCE"):     {"bbch": 10, "name": "VE",         "critical": False, "absorption": {"N": 0.02, "P": 0.03, "K": 0.02}, "water": 0.4, "growth": 0.3},
    ("LEGUME", "VEGETATIVE"):    {"bbch": 18, "name": "V-Stage",    "critical": False, "absorption": {"N": 0.10, "P": 0.08, "K": 0.08}, "water": 0.6, "growth": 0.7},
    ("LEGUME", "REPRODUCTIVE"):  {"bbch": 65, "name": "Pod-Fill",   "critical": True,  "absorption": {"N": 0.50, "P": 0.55, "K": 0.60}, "water": 1.7, "growth": 1.0},
    ("LEGUME", "SENESCENCE"):    {"bbch": 89, "name": "Maturity",   "critical": False, "absorption": {"N": 0.95, "P": 0.93, "K": 0.90}, "water": 0.3, "growth": 0.05},

    ("ROOT", "EMERGENCE"):       {"bbch": 9,  "name": "Sprout",     "critical": False, "absorption": {"N": 0.03, "P": 0.03, "K": 0.03}, "water": 0.3, "growth": 0.3},
    ("ROOT", "VEGETATIVE"):      {"bbch": 30, "name": "Bulking",    "critical": True,  "absorption": {"N": 0.25, "P": 0.20, "K": 0.22}, "water": 0.8, "growth": 0.9},
    ("ROOT", "REPRODUCTIVE"):    {"bbch": 65, "name": "Tuber-Fill", "critical": True,  "absorption": {"N": 0.65, "P": 0.60, "K": 0.70}, "water": 1.6, "growth": 1.0},
    ("ROOT", "SENESCENCE"):      {"bbch": 90, "name": "Senescence", "critical": False, "absorption": {"N": 0.95, "P": 0.92, "K": 0.95}, "water": 0.3, "growth": 0.05},

    ("FIBER", "EMERGENCE"):      {"bbch": 9,  "name": "Cotyledon",  "critical": False, "absorption": {"N": 0.02, "P": 0.02, "K": 0.02}, "water": 0.3, "growth": 0.2},
    ("FIBER", "VEGETATIVE"):     {"bbch": 19, "name": "Leaf-Dev",   "critical": False, "absorption": {"N": 0.10, "P": 0.08, "K": 0.08}, "water": 0.6, "growth": 0.7},
    ("FIBER", "REPRODUCTIVE"):   {"bbch": 65, "name": "Flowering",  "critical": True,  "absorption": {"N": 0.55, "P": 0.50, "K": 0.60}, "water": 1.7, "growth": 1.0},
    ("FIBER", "SENESCENCE"):     {"bbch": 85, "name": "Boll-Open",  "critical": False, "absorption": {"N": 0.90, "P": 0.88, "K": 0.85}, "water": 0.4, "growth": 0.1},
    
    ("FRUIT", "EMERGENCE"):      {"bbch": 10, "name": "Seedling",   "critical": False, "absorption": {"N": 0.04, "P": 0.05, "K": 0.04}, "water": 0.4, "growth": 0.4},
    ("FRUIT", "VEGETATIVE"):     {"bbch": 20, "name": "Shoot-Dev",  "critical": False, "absorption": {"N": 0.20, "P": 0.15, "K": 0.25}, "water": 0.8, "growth": 0.8},
    ("FRUIT", "REPRODUCTIVE"):   {"bbch": 65, "name": "Fruit-Set",  "critical": True,  "absorption": {"N": 0.50, "P": 0.45, "K": 0.80}, "water": 1.5, "growth": 1.0},
    ("FRUIT", "SENESCENCE"):     {"bbch": 89, "name": "Ripening",   "critical": False, "absorption": {"N": 0.85, "P": 0.80, "K": 0.95}, "water": 0.6, "growth": 0.2},

    ("TREE", "EMERGENCE"):       {"bbch": 0,  "name": "Bud-Break",  "critical": False, "absorption": {"N": 0.05, "P": 0.05, "K": 0.05}, "water": 0.3, "growth": 0.2},
    ("TREE", "VEGETATIVE"):      {"bbch": 31, "name": "Shoot-Grow", "critical": False, "absorption": {"N": 0.30, "P": 0.20, "K": 0.25}, "water": 0.9, "growth": 0.7},
    ("TREE", "REPRODUCTIVE"):    {"bbch": 65, "name": "Flowering",  "critical": True,  "absorption": {"N": 0.45, "P": 0.40, "K": 0.60}, "water": 1.4, "growth": 0.9},
    ("TREE", "SENESCENCE"):      {"bbch": 89, "name": "Fruit-Mat",  "critical": False, "absorption": {"N": 0.80, "P": 0.75, "K": 0.90}, "water": 0.7, "growth": 0.1},
    
    ("LEAFY", "EMERGENCE"):      {"bbch": 10, "name": "Seedling",   "critical": False, "absorption": {"N": 0.05, "P": 0.03, "K": 0.04}, "water": 0.5, "growth": 0.4},
    ("LEAFY", "VEGETATIVE"):     {"bbch": 40, "name": "Head-Dev",   "critical": True,  "absorption": {"N": 0.60, "P": 0.30, "K": 0.50}, "water": 1.2, "growth": 1.0},
    ("LEAFY", "REPRODUCTIVE"):   {"bbch": 60, "name": "Bolting",    "critical": False, "absorption": {"N": 0.40, "P": 0.40, "K": 0.60}, "water": 1.0, "growth": 0.6},
    ("LEAFY", "SENESCENCE"):     {"bbch": 89, "name": "Seed-Set",   "critical": False, "absorption": {"N": 0.20, "P": 0.50, "K": 0.40}, "water": 0.4, "growth": 0.1},
}

_CROP_ARCHETYPES = """ + repr(archetype_mapping) + """

_DEFAULT_STAGE = {
    "bbch": 30, "name": "GENERIC_VEG", "critical": False,
    "absorption": {"N": 0.20, "P": 0.15, "K": 0.15},
    "water": 0.7, "growth": 0.6,
}

class PhenologyDosingEngine:
    \"\"\"Scales application rates by crop-stage absorption coefficients.\"\"\"

    def lookup_stage(self, crop: str, phenology_stage: str) -> BBCHStageInfo:
        c_id = crop.lower()
        arch = _CROP_ARCHETYPES.get(c_id, "CEREAL")
        key = (arch, phenology_stage.upper())
        p = _ARCHETYPE_BBCH.get(key, _DEFAULT_STAGE)
        
        return BBCHStageInfo(
            bbch_code=p["bbch"], stage_name=p["name"], crop=c_id,
            absorption_coefficients=dict(p["absorption"]),
            critical_period=p["critical"],
            water_demand_factor=p["water"], growth_rate_factor=p["growth"],
        )

    def adjust_rates(self, action_cards: List[ActionCard], crop: str, phenology_stage: str) -> List[ActionCard]:
        stage = self.lookup_stage(crop, phenology_stage)
        for card in action_cards:
            card.phenology_info = stage
            if card.rate is None:
                continue
            if card.action_type == ActionType.FERTILIZE:
                nutrient = self._infer_nutrient(card)
                coeff = stage.absorption_coefficients.get(nutrient, 0.20)
                sf = max(0.15, min(1.5, coeff * 2.0))
                orig = card.rate.recommended
                adj = round(orig * sf, 1)
                card.rate = RateRange(
                    recommended=adj,
                    min_safe=max(0, round(adj * 0.7, 1)),
                    max_safe=min(card.rate.max_safe, round(adj * 1.3, 1)),
                    unit=card.rate.unit,
                )
                if orig != adj:
                    card.explain += " [pheno BBCH{} {} coeff={:.2f}]".format(
                        stage.bbch_code, stage.stage_name, coeff)
            elif card.action_type == ActionType.IRRIGATE:
                wdf = stage.water_demand_factor
                adj = round(card.rate.recommended * wdf, 1)
                card.rate = RateRange(
                    recommended=min(adj, card.rate.max_safe),
                    min_safe=max(0, round(adj * 0.5, 1)),
                    max_safe=card.rate.max_safe, unit=card.rate.unit,
                )
            if stage.critical_period:
                card.priority_breakdown.urgency_score = min(
                    1.0, card.priority_breakdown.urgency_score + 0.15)
        logger.debug("Phenology: crop=%s archetype=%s BBCH=%d critical=%s",
                     crop, _CROP_ARCHETYPES.get(crop.lower(), "CEREAL"), stage.bbch_code, stage.critical_period)
        return action_cards

    @staticmethod
    def _infer_nutrient(card: ActionCard) -> str:
        for ev in card.evidence:
            ref = ev.reference_id.upper()
            if "N_DEF" in ref or "NITROGEN" in ref: return "N"
            if "P_DEF" in ref or "PHOSPH" in ref: return "P"
            if "K_DEF" in ref or "POTASS" in ref: return "K"
        return "N"

phenology_engine = PhenologyDosingEngine()
"""

with open("layer8_prescriptive/engines/phenology_dosing.py", "w") as f:
    f.write(content)

print("Phenology Dosing Engine updated with full crop support via archetypes.")
