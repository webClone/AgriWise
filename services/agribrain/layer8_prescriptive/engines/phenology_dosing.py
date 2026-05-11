"""
Layer 8 Engine: Phenology-Aware Dosing v8.2.0
=============================================
BBCH-scale crop stage lookup with absorption coefficients.
Scales application rates to match actual physiological demand.
"""
import logging
from typing import Dict, Optional, List
from layer8_prescriptive.schema import (
    ActionCard, ActionType, BBCHStageInfo, RateRange,
)

logger = logging.getLogger(__name__)

# BBCH Tables: (crop, stage) -> parameters
_BBCH_TABLE = {
    ("corn", "EMERGENCE"):     {"bbch": 9,  "name": "VE",          "critical": False, "absorption": {"N": 0.02, "P": 0.03, "K": 0.02}, "water": 0.4, "growth": 0.3},
    ("corn", "VEGETATIVE"):    {"bbch": 16, "name": "V6",          "critical": False, "absorption": {"N": 0.12, "P": 0.08, "K": 0.10}, "water": 0.7, "growth": 0.8},
    ("corn", "REPRODUCTIVE"):  {"bbch": 65, "name": "R1-Silking",  "critical": True,  "absorption": {"N": 0.55, "P": 0.50, "K": 0.65}, "water": 1.8, "growth": 1.0},
    ("corn", "SENESCENCE"):    {"bbch": 87, "name": "R6-Maturity", "critical": False, "absorption": {"N": 0.95, "P": 0.92, "K": 0.90}, "water": 0.5, "growth": 0.1},
    ("wheat", "EMERGENCE"):    {"bbch": 10, "name": "Coleoptile",  "critical": False, "absorption": {"N": 0.03, "P": 0.04, "K": 0.03}, "water": 0.4, "growth": 0.3},
    ("wheat", "VEGETATIVE"):   {"bbch": 25, "name": "Tillering",   "critical": False, "absorption": {"N": 0.20, "P": 0.15, "K": 0.18}, "water": 0.7, "growth": 0.8},
    ("wheat", "REPRODUCTIVE"): {"bbch": 61, "name": "Anthesis",    "critical": True,  "absorption": {"N": 0.65, "P": 0.55, "K": 0.70}, "water": 1.6, "growth": 0.9},
    ("wheat", "SENESCENCE"):   {"bbch": 87, "name": "Hard-Dough",  "critical": False, "absorption": {"N": 0.95, "P": 0.90, "K": 0.92}, "water": 0.4, "growth": 0.1},
    ("soybean", "EMERGENCE"):    {"bbch": 10, "name": "VE",        "critical": False, "absorption": {"N": 0.02, "P": 0.03, "K": 0.02}, "water": 0.4, "growth": 0.3},
    ("soybean", "VEGETATIVE"):   {"bbch": 18, "name": "V4-V6",    "critical": False, "absorption": {"N": 0.10, "P": 0.08, "K": 0.08}, "water": 0.6, "growth": 0.7},
    ("soybean", "REPRODUCTIVE"): {"bbch": 65, "name": "R3-Pod",   "critical": True,  "absorption": {"N": 0.50, "P": 0.55, "K": 0.60}, "water": 1.7, "growth": 1.0},
    ("soybean", "SENESCENCE"):   {"bbch": 89, "name": "R8-Mat",   "critical": False, "absorption": {"N": 0.95, "P": 0.93, "K": 0.90}, "water": 0.3, "growth": 0.05},
    ("rice", "EMERGENCE"):    {"bbch": 10, "name": "Seedling",     "critical": False, "absorption": {"N": 0.03, "P": 0.03, "K": 0.02}, "water": 0.5, "growth": 0.3},
    ("rice", "VEGETATIVE"):   {"bbch": 25, "name": "Tillering",    "critical": False, "absorption": {"N": 0.25, "P": 0.18, "K": 0.20}, "water": 1.0, "growth": 0.9},
    ("rice", "REPRODUCTIVE"): {"bbch": 55, "name": "Panicle-Init", "critical": True,  "absorption": {"N": 0.60, "P": 0.55, "K": 0.65}, "water": 1.8, "growth": 1.0},
    ("rice", "SENESCENCE"):   {"bbch": 87, "name": "Grain-Fill",   "critical": False, "absorption": {"N": 0.92, "P": 0.90, "K": 0.88}, "water": 0.8, "growth": 0.2},
    ("cotton", "EMERGENCE"):    {"bbch": 9,  "name": "Cotyledon",  "critical": False, "absorption": {"N": 0.02, "P": 0.02, "K": 0.02}, "water": 0.3, "growth": 0.2},
    ("cotton", "VEGETATIVE"):   {"bbch": 19, "name": "5th-Node",   "critical": False, "absorption": {"N": 0.10, "P": 0.08, "K": 0.08}, "water": 0.6, "growth": 0.7},
    ("cotton", "REPRODUCTIVE"): {"bbch": 65, "name": "Peak-Bloom", "critical": True,  "absorption": {"N": 0.55, "P": 0.50, "K": 0.60}, "water": 1.7, "growth": 1.0},
    ("cotton", "SENESCENCE"):   {"bbch": 85, "name": "Boll-Open",  "critical": False, "absorption": {"N": 0.90, "P": 0.88, "K": 0.85}, "water": 0.4, "growth": 0.1},
    ("potato", "EMERGENCE"):    {"bbch": 9,  "name": "Sprout",     "critical": False, "absorption": {"N": 0.03, "P": 0.03, "K": 0.03}, "water": 0.3, "growth": 0.3},
    ("potato", "VEGETATIVE"):   {"bbch": 30, "name": "Stolon-Init","critical": True,  "absorption": {"N": 0.25, "P": 0.20, "K": 0.22}, "water": 0.8, "growth": 0.9},
    ("potato", "REPRODUCTIVE"): {"bbch": 65, "name": "Tuber-Bulk", "critical": True,  "absorption": {"N": 0.65, "P": 0.60, "K": 0.70}, "water": 1.6, "growth": 1.0},
    ("potato", "SENESCENCE"):   {"bbch": 90, "name": "Vine-Kill",  "critical": False, "absorption": {"N": 0.95, "P": 0.92, "K": 0.95}, "water": 0.3, "growth": 0.05},
}

_DEFAULT_STAGE = {
    "bbch": 30, "name": "GENERIC_VEG", "critical": False,
    "absorption": {"N": 0.20, "P": 0.15, "K": 0.15},
    "water": 0.7, "growth": 0.6,
}


class PhenologyDosingEngine:
    """Scales application rates by crop-stage absorption coefficients."""

    def lookup_stage(self, crop, phenology_stage):
        key = (crop.lower(), phenology_stage.upper())
        p = _BBCH_TABLE.get(key, _DEFAULT_STAGE)
        return BBCHStageInfo(
            bbch_code=p["bbch"], stage_name=p["name"], crop=crop.lower(),
            absorption_coefficients=dict(p["absorption"]),
            critical_period=p["critical"],
            water_demand_factor=p["water"], growth_rate_factor=p["growth"],
        )

    def adjust_rates(self, action_cards, crop, phenology_stage):
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
        logger.debug("Phenology: crop=%s BBCH=%d critical=%s",
                     crop, stage.bbch_code, stage.critical_period)
        return action_cards

    @staticmethod
    def _infer_nutrient(card):
        for ev in card.evidence:
            ref = ev.reference_id.upper()
            if "N_DEF" in ref or "NITROGEN" in ref: return "N"
            if "P_DEF" in ref or "PHOSPH" in ref: return "P"
            if "K_DEF" in ref or "POTASS" in ref: return "K"
        return "N"


phenology_engine = PhenologyDosingEngine()
