"""
Unified Crop Registry — 200+ species, single source of truth.

Every field consumed by any agribrain layer is stored here:
  - L2 veg_int   : architecture, gdd_base_temp (phenology GDD configs)
  - L2 intel     : water_stress_sensitivity (phenology adjuster)
  - L3 decision  : kc_init/mid/end, max_root_depth_cm, water_stress_sensitivity
  - L4 nutrients  : removal_n/p/k, attainable_yield, n_ceiling, kcb_*,
                    response_a/c/n, price_usd_per_ton
  - L6 yield      : harvest_index
  - Orchestrator  : architecture (NDVI–phenology thresholds are per-architecture)

Sources:
  - FAO-56 (Allen et al., 1998): Kc, Kcb, root depth
  - IPNI (2014): Nutrient removal rates
  - Ciampitti & Vyn (2012): Uptake curves
  - Saxton & Rawls (2006): Soil hydraulics
  - FAO EcoCrop: Temperature, water requirements
  - Hsiao et al. (2009): Water stress sensitivities
  - Regional market data (FAO GIEWS, USDA)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# =============================================================================
# CropSpec — the universal crop profile
# =============================================================================

@dataclass(frozen=True)
class CropSpec:
    """Immutable crop specification used by all pipeline layers."""

    # ── Identity ────────────────────────────────────────────────────────────
    code: str                           # canonical key, e.g. "wheat"
    name: str                           # English name
    name_ar: str                        # Arabic name
    scientific_name: str                # Binomial
    family: str                         # Botanical family

    # ── Classification ──────────────────────────────────────────────────────
    architecture: str                   # cereal|maize|rice|legume|vegetable|perennial|cotton|tropical_tree
    region_tags: tuple                  # e.g. ("mediterranean","mena","temperate")

    # ── Phenology ───────────────────────────────────────────────────────────
    gdd_base_temp: float                # Growing degree-day base (°C)
    growing_days: int                   # Typical cycle length
    optimal_temp_min: float             # Optimal growth range
    optimal_temp_max: float

    # ── Water ───────────────────────────────────────────────────────────────
    water_needs: str                    # low|medium|high
    max_root_depth_cm: float
    kc_init: float                      # FAO-56 crop coefficients
    kc_mid: float
    kc_end: float
    # Basal crop coefficients per stage (FAO-56 Table 12)
    kcb_initial: float
    kcb_vegetative: float
    kcb_reproductive: float
    kcb_maturity: float
    kcb_senescence: float
    # Stage-specific water stress sensitivity [0–1] (Hsiao 2009)
    water_stress_sensitivity: Dict[str, float]

    # ── Nutrients ───────────────────────────────────────────────────────────
    removal_n: float                    # kg N per ton product
    removal_p: float                    # kg P per ton product
    removal_k: float                    # kg K per ton product
    attainable_yield_t_ha: float        # Attainable yield under good mgmt
    n_ceiling_kg_ha: float              # Maximum N application (kg/ha/yr)

    # ── Nutrient response (Mitscherlich) ────────────────────────────────────
    response_a_max: float               # Maximum yield (t/ha)
    response_c_rate: float              # Curvature parameter
    response_n_soil_default: float      # Default soil N (ppm)

    # ── Tissue Analysis (SRA) ──────────────────────────────────────────────
    # Critical concentrations: {stage: (deficient, low, sufficient_max, high_above)}
    # Macros in %, micros in ppm.  Source: Mills & Jones (1996), Reuter & Robinson (1997)
    tissue_norms: Dict[str, Dict[str, tuple]]  # {nutrient: {stage: (def, low, suf, high)}}

    # ── DRIS Norms ─────────────────────────────────────────────────────────
    # Optimal nutrient ratio norms: {ratio: (mean, cv)}
    # Source: Walworth & Sumner (1987)
    dris_norms: Dict[str, tuple]

    # ── NUE Benchmarks ─────────────────────────────────────────────────────
    # Source: Dobermann (2007), Cassman et al. (2002)
    nue_ae_range: tuple                 # (min, max) kg grain / kg N
    nue_pfp_range: tuple                # (min, max) kg grain / kg N
    nue_re_range: tuple                 # (min, max) fraction
    grain_n_pct: float                  # % N in harvested grain/product

    # ── Economics ────────────────────────────────────────────────────────────
    harvest_index: float                # Economic yield / total biomass
    price_usd_per_ton: float            # Approximate market price

    # ── Salinity (FAO-29 Maas-Hoffman 1977) ────────────────────────────────
    ec_threshold_ds_m: float            # Salinity threshold (dS/m)
    ec_slope_pct: float                 # Yield decline rate (%/dS·m⁻¹)
    salt_tolerance_class: str           # sensitive|mod_sensitive|mod_tolerant|tolerant

    # ── BNF (Herridge et al. 2008, Peoples et al. 2009) ────────────────────
    is_legume: bool                     # Rhizobium-legume symbiotic N₂ fixation
    bnf_ndfa_range: tuple               # (min, max) Ndfa fraction [0-1]
    bnf_typical_kg_ha: float            # Typical fixation (kg N/ha)
    bnf_type: str                       # symbiotic|associative|free_living_only
    residue_cn_ratio: float             # Residue C:N ratio

    # ── N Dilution Curve (Lemaire & Gastal 1997) ───────────────────────────
    photosynthetic_pathway: str         # C3|C4|CAM
    n_dilution_a: float                 # Critical N curve: N_crit = a × W^(-b)
    n_dilution_b: float                 # Critical N curve exponent
    rue_g_mj: float                     # Radiation Use Efficiency (g DM / MJ PAR)

    # ── Spectral Baselines ─────────────────────────────────────────────────
    ndvi_baselines: Dict[str, tuple]    # {stage: (mean, std)} for healthy crop


# =============================================================================
# Architecture class defaults
# =============================================================================

_STRESS = {
    "BARE_SOIL": 0.0, "EMERGENCE": 0.5, "VEGETATIVE": 0.4,
    "REPRODUCTIVE": 0.9, "SENESCENCE": 0.1, "HARVESTED": 0.0,
}

_ARCH_DEFAULTS: Dict[str, dict] = {
    "cereal": dict(
        gdd_base_temp=0.0, growing_days=140, optimal_temp_min=12, optimal_temp_max=25,
        water_needs="medium", max_root_depth_cm=120, kc_init=0.30, kc_mid=1.15, kc_end=0.25,
        kcb_initial=0.15, kcb_vegetative=0.50, kcb_reproductive=1.10, kcb_maturity=0.25, kcb_senescence=0.15,
        water_stress_sensitivity={"BARE_SOIL":0.0,"EMERGENCE":0.4,"VEGETATIVE":0.3,"REPRODUCTIVE":0.9,"SENESCENCE":0.1,"HARVESTED":0.0},
        removal_n=20.0, removal_p=3.5, removal_k=5.0, attainable_yield_t_ha=7.0, n_ceiling_kg_ha=220,
        response_a_max=8.0, response_c_rate=0.020, response_n_soil_default=40,
        harvest_index=0.42, price_usd_per_ton=250,
        # Tissue norms: flag leaf at boot/heading (Mills & Jones 1996)
        tissue_norms={
            "N":  {"vegetative": (2.8, 3.2, 4.2, 5.0), "reproductive": (2.0, 2.5, 3.5, 4.5)},
            "P":  {"vegetative": (0.20, 0.25, 0.40, 0.60)},
            "K":  {"vegetative": (1.5, 1.8, 2.5, 3.5)},
            "S":  {"vegetative": (0.15, 0.20, 0.35, 0.50)},
            "Zn": {"vegetative": (15.0, 20.0, 70.0, 200.0)},
            "B":  {"vegetative": (5.0, 8.0, 25.0, 100.0)},
            "Fe": {"vegetative": (25.0, 50.0, 250.0, 500.0)},
            "Mn": {"vegetative": (15.0, 25.0, 150.0, 300.0)},
            "Cu": {"vegetative": (3.0, 5.0, 20.0, 50.0)},
        },
        dris_norms={"N/P": (11.0, 3.0), "N/K": (1.4, 0.3), "N/S": (14.0, 3.0)},
        nue_ae_range=(8.0, 20.0), nue_pfp_range=(30.0, 60.0), nue_re_range=(0.30, 0.50),
        grain_n_pct=2.0,
        # v4.0 new fields
        ec_threshold_ds_m=5.0, ec_slope_pct=7.0, salt_tolerance_class="mod_tolerant",
        is_legume=False, bnf_ndfa_range=(0.0, 0.0), bnf_typical_kg_ha=0.0,
        bnf_type="free_living_only", residue_cn_ratio=60.0,
        photosynthetic_pathway="C3", n_dilution_a=5.35, n_dilution_b=0.442, rue_g_mj=2.7,
        ndvi_baselines={"initial": (0.25, 0.05), "vegetative": (0.72, 0.08),
                        "reproductive": (0.80, 0.05), "maturity": (0.50, 0.12), "senescence": (0.25, 0.08)},
    ),
    "maize": dict(
        gdd_base_temp=10.0, growing_days=130, optimal_temp_min=18, optimal_temp_max=33,
        water_needs="high", max_root_depth_cm=150, kc_init=0.30, kc_mid=1.20, kc_end=0.60,
        kcb_initial=0.15, kcb_vegetative=0.50, kcb_reproductive=1.15, kcb_maturity=0.50, kcb_senescence=0.15,
        water_stress_sensitivity={"BARE_SOIL":0.0,"EMERGENCE":0.6,"VEGETATIVE":0.5,"REPRODUCTIVE":1.0,"SENESCENCE":0.2,"HARVESTED":0.0},
        removal_n=15.0, removal_p=3.5, removal_k=4.0, attainable_yield_t_ha=12.0, n_ceiling_kg_ha=280,
        response_a_max=14.0, response_c_rate=0.018, response_n_soil_default=50,
        harvest_index=0.50, price_usd_per_ton=180,
        # Tissue norms: ear leaf at V6-VT (Mills & Jones 1996)
        tissue_norms={
            "N":  {"vegetative": (2.5, 2.8, 3.5, 4.5), "reproductive": (2.2, 2.5, 3.2, 4.0), "maturity": (1.5, 2.0, 2.8, 3.5)},
            "P":  {"vegetative": (0.20, 0.25, 0.40, 0.60), "reproductive": (0.18, 0.22, 0.35, 0.50)},
            "K":  {"vegetative": (1.5, 1.8, 2.5, 3.5), "reproductive": (1.2, 1.5, 2.2, 3.0)},
            "S":  {"vegetative": (0.15, 0.18, 0.30, 0.50)},
            "Zn": {"vegetative": (15.0, 20.0, 50.0, 200.0)},
            "B":  {"vegetative": (4.0, 6.0, 20.0, 100.0)},
            "Fe": {"vegetative": (20.0, 50.0, 250.0, 500.0)},
            "Mn": {"vegetative": (15.0, 20.0, 150.0, 300.0)},
            "Cu": {"vegetative": (3.0, 6.0, 20.0, 50.0)},
        },
        dris_norms={"N/P": (12.0, 2.5), "N/K": (1.5, 0.3), "N/S": (15.0, 3.0), "K/Mg": (8.0, 2.0), "P/Zn": (0.015, 0.005)},
        nue_ae_range=(10.0, 25.0), nue_pfp_range=(40.0, 80.0), nue_re_range=(0.30, 0.50),
        grain_n_pct=1.4,
        # v4.0 new fields
        ec_threshold_ds_m=1.7, ec_slope_pct=12.0, salt_tolerance_class="mod_sensitive",
        is_legume=False, bnf_ndfa_range=(0.0, 0.0), bnf_typical_kg_ha=0.0,
        bnf_type="free_living_only", residue_cn_ratio=50.0,
        photosynthetic_pathway="C4", n_dilution_a=3.40, n_dilution_b=0.370, rue_g_mj=3.8,
        ndvi_baselines={"initial": (0.20, 0.05), "vegetative": (0.75, 0.08),
                        "reproductive": (0.85, 0.05), "maturity": (0.60, 0.12), "senescence": (0.30, 0.10)},
    ),
    "rice": dict(
        gdd_base_temp=10.0, growing_days=140, optimal_temp_min=20, optimal_temp_max=35,
        water_needs="high", max_root_depth_cm=60, kc_init=1.05, kc_mid=1.20, kc_end=0.75,
        kcb_initial=1.00, kcb_vegetative=1.10, kcb_reproductive=1.15, kcb_maturity=0.90, kcb_senescence=0.60,
        water_stress_sensitivity={"BARE_SOIL":0.0,"EMERGENCE":0.7,"VEGETATIVE":0.6,"REPRODUCTIVE":1.0,"SENESCENCE":0.3,"HARVESTED":0.0},
        removal_n=14.0, removal_p=2.8, removal_k=3.0, attainable_yield_t_ha=8.0, n_ceiling_kg_ha=200,
        response_a_max=9.0, response_c_rate=0.020, response_n_soil_default=35,
        harvest_index=0.45, price_usd_per_ton=350,
        # Tissue norms: Y-leaf at tillering/panicle init (Dobermann & Fairhurst 2000)
        tissue_norms={
            "N":  {"vegetative": (2.5, 2.8, 3.5, 4.5), "reproductive": (2.0, 2.3, 3.0, 4.0)},
            "P":  {"vegetative": (0.18, 0.22, 0.35, 0.60)},
            "K":  {"vegetative": (1.5, 1.8, 2.5, 3.5)},
            "S":  {"vegetative": (0.14, 0.18, 0.30, 0.50)},
            "Zn": {"vegetative": (15.0, 20.0, 50.0, 150.0)},
            "B":  {"vegetative": (3.0, 6.0, 20.0, 100.0)},
            "Fe": {"vegetative": (50.0, 70.0, 300.0, 500.0)},
            "Mn": {"vegetative": (30.0, 40.0, 300.0, 600.0)},
            "Cu": {"vegetative": (3.0, 5.0, 15.0, 50.0)},
        },
        dris_norms={"N/P": (12.0, 2.5), "N/K": (1.3, 0.3), "N/S": (15.0, 3.0)},
        nue_ae_range=(8.0, 18.0), nue_pfp_range=(35.0, 70.0), nue_re_range=(0.25, 0.45),
        grain_n_pct=1.2,
        # v4.0 new fields
        ec_threshold_ds_m=3.0, ec_slope_pct=12.0, salt_tolerance_class="mod_sensitive",
        is_legume=False, bnf_ndfa_range=(0.05, 0.15), bnf_typical_kg_ha=15.0,
        bnf_type="associative", residue_cn_ratio=55.0,
        photosynthetic_pathway="C3", n_dilution_a=5.20, n_dilution_b=0.440, rue_g_mj=2.5,
        ndvi_baselines={"initial": (0.22, 0.05), "vegetative": (0.65, 0.08),
                        "reproductive": (0.75, 0.06), "maturity": (0.55, 0.10), "senescence": (0.30, 0.08)},
    ),
    "legume": dict(
        gdd_base_temp=10.0, growing_days=120, optimal_temp_min=15, optimal_temp_max=28,
        water_needs="medium", max_root_depth_cm=90, kc_init=0.40, kc_mid=1.15, kc_end=0.50,
        kcb_initial=0.15, kcb_vegetative=0.50, kcb_reproductive=1.10, kcb_maturity=0.30, kcb_senescence=0.15,
        water_stress_sensitivity={"BARE_SOIL":0.0,"EMERGENCE":0.5,"VEGETATIVE":0.4,"REPRODUCTIVE":0.90,"SENESCENCE":0.15,"HARVESTED":0.0},
        removal_n=40.0, removal_p=4.5, removal_k=10.0, attainable_yield_t_ha=4.0, n_ceiling_kg_ha=50,
        response_a_max=4.0, response_c_rate=0.012, response_n_soil_default=60,
        harvest_index=0.38, price_usd_per_ton=400,
        # Tissue norms: uppermost fully expanded trifoliate (Reuter & Robinson 1997)
        tissue_norms={
            "N":  {"vegetative": (3.5, 4.0, 5.0, 6.0), "reproductive": (3.0, 3.5, 4.5, 5.5)},
            "P":  {"vegetative": (0.20, 0.26, 0.40, 0.60)},
            "K":  {"vegetative": (1.5, 1.7, 2.5, 3.5)},
            "S":  {"vegetative": (0.15, 0.20, 0.35, 0.50)},
            "Zn": {"vegetative": (15.0, 21.0, 50.0, 200.0)},
            "B":  {"vegetative": (15.0, 20.0, 50.0, 200.0)},
            "Fe": {"vegetative": (30.0, 50.0, 300.0, 500.0)},
            "Mn": {"vegetative": (15.0, 21.0, 100.0, 300.0)},
            "Cu": {"vegetative": (3.0, 5.0, 15.0, 30.0)},
        },
        dris_norms={"N/P": (14.0, 3.0), "N/K": (2.0, 0.4), "N/S": (15.0, 3.0)},
        nue_ae_range=(5.0, 12.0), nue_pfp_range=(50.0, 120.0), nue_re_range=(0.15, 0.35),
        grain_n_pct=5.5,
        # v4.0 new fields
        ec_threshold_ds_m=1.5, ec_slope_pct=14.0, salt_tolerance_class="sensitive",
        is_legume=True, bnf_ndfa_range=(0.40, 0.80), bnf_typical_kg_ha=100.0,
        bnf_type="symbiotic", residue_cn_ratio=15.0,
        photosynthetic_pathway="C3", n_dilution_a=5.10, n_dilution_b=0.320, rue_g_mj=2.0,
        ndvi_baselines={"initial": (0.22, 0.05), "vegetative": (0.70, 0.08),
                        "reproductive": (0.78, 0.06), "maturity": (0.50, 0.10), "senescence": (0.25, 0.08)},
    ),
    "vegetable": dict(
        gdd_base_temp=10.0, growing_days=100, optimal_temp_min=15, optimal_temp_max=30,
        water_needs="high", max_root_depth_cm=60, kc_init=0.60, kc_mid=1.05, kc_end=0.80,
        kcb_initial=0.15, kcb_vegetative=0.50, kcb_reproductive=1.00, kcb_maturity=0.70, kcb_senescence=0.15,
        water_stress_sensitivity={"BARE_SOIL":0.0,"EMERGENCE":0.6,"VEGETATIVE":0.5,"REPRODUCTIVE":0.85,"SENESCENCE":0.2,"HARVESTED":0.0},
        removal_n=3.0, removal_p=0.5, removal_k=4.0, attainable_yield_t_ha=40.0, n_ceiling_kg_ha=250,
        response_a_max=50.0, response_c_rate=0.014, response_n_soil_default=50,
        harvest_index=0.65, price_usd_per_ton=200,
        # Tissue norms: most recent mature leaf (MRML) (Reuter & Robinson 1997)
        tissue_norms={
            "N":  {"vegetative": (2.5, 3.0, 5.0, 6.5), "reproductive": (2.0, 2.5, 4.5, 6.0)},
            "P":  {"vegetative": (0.20, 0.25, 0.50, 0.80)},
            "K":  {"vegetative": (2.0, 2.5, 4.5, 6.0)},
            "S":  {"vegetative": (0.15, 0.20, 0.40, 0.60)},
            "Zn": {"vegetative": (15.0, 20.0, 80.0, 200.0)},
            "B":  {"vegetative": (15.0, 20.0, 60.0, 200.0)},
            "Fe": {"vegetative": (30.0, 50.0, 300.0, 500.0)},
            "Mn": {"vegetative": (15.0, 25.0, 200.0, 400.0)},
            "Cu": {"vegetative": (3.0, 5.0, 20.0, 50.0)},
        },
        dris_norms={"N/P": (10.0, 3.0), "N/K": (1.0, 0.3), "N/S": (12.0, 3.0)},
        nue_ae_range=(50.0, 200.0), nue_pfp_range=(100.0, 400.0), nue_re_range=(0.30, 0.55),
        grain_n_pct=0.3,  # Fresh-weight basis for vegetables
        # v4.0 new fields
        ec_threshold_ds_m=2.0, ec_slope_pct=10.0, salt_tolerance_class="mod_sensitive",
        is_legume=False, bnf_ndfa_range=(0.0, 0.0), bnf_typical_kg_ha=0.0,
        bnf_type="free_living_only", residue_cn_ratio=20.0,
        photosynthetic_pathway="C3", n_dilution_a=4.50, n_dilution_b=0.400, rue_g_mj=2.2,
        ndvi_baselines={"initial": (0.22, 0.06), "vegetative": (0.68, 0.10),
                        "reproductive": (0.75, 0.06), "maturity": (0.55, 0.10), "senescence": (0.28, 0.08)},
    ),
    "perennial": dict(
        gdd_base_temp=10.0, growing_days=200, optimal_temp_min=15, optimal_temp_max=35,
        water_needs="medium", max_root_depth_cm=200, kc_init=0.50, kc_mid=0.80, kc_end=0.65,
        kcb_initial=0.30, kcb_vegetative=0.50, kcb_reproductive=0.70, kcb_maturity=0.50, kcb_senescence=0.30,
        water_stress_sensitivity={"BARE_SOIL":0.0,"EMERGENCE":0.3,"VEGETATIVE":0.3,"REPRODUCTIVE":0.80,"SENESCENCE":0.1,"HARVESTED":0.0},
        removal_n=10.0, removal_p=2.0, removal_k=8.0, attainable_yield_t_ha=10.0, n_ceiling_kg_ha=200,
        response_a_max=10.0, response_c_rate=0.012, response_n_soil_default=30,
        harvest_index=0.30, price_usd_per_ton=500,
        # Tissue norms: spring-flush leaf 4-7 months old (Embleton et al. 1973)
        tissue_norms={
            "N":  {"vegetative": (2.0, 2.2, 2.8, 3.5), "reproductive": (1.8, 2.0, 2.6, 3.2)},
            "P":  {"vegetative": (0.09, 0.12, 0.20, 0.30)},
            "K":  {"vegetative": (0.70, 1.0, 1.7, 2.5)},
            "S":  {"vegetative": (0.14, 0.20, 0.30, 0.50)},
            "Zn": {"vegetative": (15.0, 25.0, 80.0, 200.0)},
            "B":  {"vegetative": (20.0, 30.0, 80.0, 250.0)},
            "Fe": {"vegetative": (40.0, 60.0, 200.0, 500.0)},
            "Mn": {"vegetative": (15.0, 25.0, 100.0, 300.0)},
            "Cu": {"vegetative": (3.0, 5.0, 15.0, 30.0)},
        },
        dris_norms={"N/P": (16.0, 4.0), "N/K": (1.8, 0.4), "N/S": (12.0, 3.0)},
        nue_ae_range=(30.0, 100.0), nue_pfp_range=(40.0, 120.0), nue_re_range=(0.20, 0.40),
        grain_n_pct=0.2,  # Fresh fruit basis
        # v4.0 new fields
        ec_threshold_ds_m=3.0, ec_slope_pct=10.0, salt_tolerance_class="mod_sensitive",
        is_legume=False, bnf_ndfa_range=(0.0, 0.0), bnf_typical_kg_ha=0.0,
        bnf_type="free_living_only", residue_cn_ratio=40.0,
        photosynthetic_pathway="C3", n_dilution_a=3.20, n_dilution_b=0.280, rue_g_mj=1.5,
        ndvi_baselines={"initial": (0.30, 0.06), "vegetative": (0.55, 0.08),
                        "reproductive": (0.60, 0.06), "maturity": (0.55, 0.08), "senescence": (0.40, 0.08)},
    ),
    "cotton": dict(
        gdd_base_temp=15.6, growing_days=180, optimal_temp_min=20, optimal_temp_max=35,
        water_needs="high", max_root_depth_cm=150, kc_init=0.35, kc_mid=1.15, kc_end=0.70,
        kcb_initial=0.15, kcb_vegetative=0.45, kcb_reproductive=1.10, kcb_maturity=0.50, kcb_senescence=0.15,
        water_stress_sensitivity={"BARE_SOIL":0.0,"EMERGENCE":0.5,"VEGETATIVE":0.4,"REPRODUCTIVE":0.95,"SENESCENCE":0.2,"HARVESTED":0.0},
        removal_n=50.0, removal_p=10.0, removal_k=15.0, attainable_yield_t_ha=1.5, n_ceiling_kg_ha=200,
        response_a_max=2.0, response_c_rate=0.020, response_n_soil_default=40,
        harvest_index=0.35, price_usd_per_ton=1500,
        # Tissue norms: 4th main-stem leaf from top, early bloom (Constable & Rochester 1988)
        tissue_norms={
            "N":  {"vegetative": (3.0, 3.5, 4.5, 5.5), "reproductive": (2.5, 3.0, 4.0, 5.0)},
            "P":  {"vegetative": (0.20, 0.25, 0.40, 0.60)},
            "K":  {"vegetative": (1.5, 1.8, 2.5, 4.0)},
            "S":  {"vegetative": (0.20, 0.25, 0.50, 0.80)},
            "Zn": {"vegetative": (15.0, 20.0, 60.0, 200.0)},
            "B":  {"vegetative": (15.0, 20.0, 60.0, 200.0)},
            "Fe": {"vegetative": (30.0, 50.0, 300.0, 500.0)},
            "Mn": {"vegetative": (15.0, 25.0, 300.0, 600.0)},
            "Cu": {"vegetative": (3.0, 5.0, 15.0, 30.0)},
        },
        dris_norms={"N/P": (12.0, 3.0), "N/K": (1.6, 0.3), "N/S": (10.0, 2.5)},
        nue_ae_range=(3.0, 8.0), nue_pfp_range=(5.0, 15.0), nue_re_range=(0.25, 0.45),
        grain_n_pct=3.0,  # Lint + seed combined
        # v4.0 new fields
        ec_threshold_ds_m=7.7, ec_slope_pct=5.2, salt_tolerance_class="tolerant",
        is_legume=False, bnf_ndfa_range=(0.0, 0.0), bnf_typical_kg_ha=0.0,
        bnf_type="free_living_only", residue_cn_ratio=45.0,
        photosynthetic_pathway="C3", n_dilution_a=3.80, n_dilution_b=0.350, rue_g_mj=2.0,
        ndvi_baselines={"initial": (0.20, 0.05), "vegetative": (0.65, 0.08),
                        "reproductive": (0.75, 0.06), "maturity": (0.55, 0.10), "senescence": (0.28, 0.08)},
    ),
    "tropical_tree": dict(
        gdd_base_temp=15.0, growing_days=365, optimal_temp_min=22, optimal_temp_max=35,
        water_needs="high", max_root_depth_cm=200, kc_init=0.90, kc_mid=1.00, kc_end=0.95,
        kcb_initial=0.80, kcb_vegetative=0.90, kcb_reproductive=0.95, kcb_maturity=0.90, kcb_senescence=0.80,
        water_stress_sensitivity={"BARE_SOIL":0.0,"EMERGENCE":0.4,"VEGETATIVE":0.4,"REPRODUCTIVE":0.85,"SENESCENCE":0.2,"HARVESTED":0.0},
        removal_n=12.0, removal_p=2.0, removal_k=10.0, attainable_yield_t_ha=15.0, n_ceiling_kg_ha=200,
        response_a_max=15.0, response_c_rate=0.010, response_n_soil_default=40,
        harvest_index=0.25, price_usd_per_ton=600,
        # Tissue norms: 3rd-4th leaf from apex, non-fruiting branch (Robinson 1986)
        tissue_norms={
            "N":  {"vegetative": (2.2, 2.5, 3.5, 4.5), "reproductive": (2.0, 2.3, 3.2, 4.0)},
            "P":  {"vegetative": (0.15, 0.20, 0.35, 0.50)},
            "K":  {"vegetative": (1.5, 2.0, 3.5, 5.0)},
            "S":  {"vegetative": (0.15, 0.20, 0.35, 0.60)},
            "Zn": {"vegetative": (15.0, 20.0, 80.0, 200.0)},
            "B":  {"vegetative": (10.0, 15.0, 40.0, 150.0)},
            "Fe": {"vegetative": (30.0, 50.0, 300.0, 500.0)},
            "Mn": {"vegetative": (20.0, 25.0, 200.0, 500.0)},
            "Cu": {"vegetative": (3.0, 5.0, 15.0, 30.0)},
        },
        dris_norms={"N/P": (13.0, 3.0), "N/K": (1.2, 0.3), "N/S": (12.0, 3.0)},
        nue_ae_range=(30.0, 100.0), nue_pfp_range=(50.0, 150.0), nue_re_range=(0.20, 0.40),
        grain_n_pct=0.2,  # Fresh fruit basis
        # v4.0 new fields
        ec_threshold_ds_m=2.0, ec_slope_pct=12.0, salt_tolerance_class="mod_sensitive",
        is_legume=False, bnf_ndfa_range=(0.0, 0.0), bnf_typical_kg_ha=0.0,
        bnf_type="free_living_only", residue_cn_ratio=30.0,
        photosynthetic_pathway="C3", n_dilution_a=3.00, n_dilution_b=0.250, rue_g_mj=1.8,
        ndvi_baselines={"initial": (0.28, 0.06), "vegetative": (0.50, 0.08),
                        "reproductive": (0.55, 0.06), "maturity": (0.50, 0.08), "senescence": (0.38, 0.08)},
    ),
}


# =============================================================================
# Raw crop data — 200+ entries
# Only fields that DIFFER from the architecture default are specified.
# =============================================================================

_RAW: Dict[str, dict] = {
    # ═══════════════════════════════════════════════════════════════════════
    # CEREALS  (architecture = cereal)
    # ═══════════════════════════════════════════════════════════════════════
    "wheat": dict(arch="cereal", name="Wheat", name_ar="قمح", sci="Triticum aestivum", fam="Poaceae",
        tags=("mediterranean","mena","temperate","subtropical"), growing_days=150,
        max_root_depth_cm=150, kc_mid=1.15, removal_n=22.0, attainable_yield_t_ha=7.0,
        harvest_index=0.45, price_usd_per_ton=250),
    "durum_wheat": dict(arch="cereal", name="Durum Wheat", name_ar="قمح صلب", sci="Triticum durum", fam="Poaceae",
        tags=("mediterranean","mena"), growing_days=145, max_root_depth_cm=140,
        removal_n=24.0, attainable_yield_t_ha=5.5, harvest_index=0.42, price_usd_per_ton=300),
    "barley": dict(arch="cereal", name="Barley", name_ar="شعير", sci="Hordeum vulgare", fam="Poaceae",
        tags=("mediterranean","mena","temperate"), growing_days=130, optimal_temp_max=22,
        kc_mid=1.10, removal_n=18.0, n_ceiling_kg_ha=180, attainable_yield_t_ha=6.0,
        harvest_index=0.42, price_usd_per_ton=200),
    "oat": dict(arch="cereal", name="Oat", name_ar="شوفان", sci="Avena sativa", fam="Poaceae",
        tags=("temperate","mediterranean"), growing_days=130, harvest_index=0.40, price_usd_per_ton=220),
    "rye": dict(arch="cereal", name="Rye", name_ar="جاودار", sci="Secale cereale", fam="Poaceae",
        tags=("temperate",), growing_days=140, max_root_depth_cm=130, harvest_index=0.38, price_usd_per_ton=200),
    "triticale": dict(arch="cereal", name="Triticale", name_ar="تريتيكال", sci="× Triticosecale", fam="Poaceae",
        tags=("temperate","mediterranean"), growing_days=135, harvest_index=0.42, price_usd_per_ton=210),
    "sorghum": dict(arch="cereal", name="Sorghum", name_ar="ذرة رفيعة", sci="Sorghum bicolor", fam="Poaceae",
        tags=("subsaharan","mena","tropical","subtropical"), gdd_base_temp=10.0, growing_days=120,
        optimal_temp_min=20, optimal_temp_max=35, max_root_depth_cm=150,
        kc_mid=1.10, removal_n=16.0, n_ceiling_kg_ha=200, attainable_yield_t_ha=8.0,
        response_a_max=8.0, harvest_index=0.40, price_usd_per_ton=170),
    "pearl_millet": dict(arch="cereal", name="Pearl Millet", name_ar="دخن لؤلؤي", sci="Pennisetum glaucum", fam="Poaceae",
        tags=("subsaharan","mena","tropical"), gdd_base_temp=10.0, growing_days=90,
        optimal_temp_min=25, optimal_temp_max=40, water_needs="low", max_root_depth_cm=120,
        kc_mid=1.00, removal_n=12.0, attainable_yield_t_ha=3.0, n_ceiling_kg_ha=100,
        harvest_index=0.25, price_usd_per_ton=250),
    "finger_millet": dict(arch="cereal", name="Finger Millet", name_ar="دخن إصبعي", sci="Eleusine coracana", fam="Poaceae",
        tags=("subsaharan","tropical"), gdd_base_temp=10.0, growing_days=100,
        water_needs="low", attainable_yield_t_ha=2.5, harvest_index=0.25, price_usd_per_ton=280),
    "teff": dict(arch="cereal", name="Teff", name_ar="تيف", sci="Eragrostis tef", fam="Poaceae",
        tags=("subsaharan",), gdd_base_temp=10.0, growing_days=100,
        max_root_depth_cm=40, attainable_yield_t_ha=2.0, removal_n=18.0,
        harvest_index=0.28, price_usd_per_ton=600),
    "fonio": dict(arch="cereal", name="Fonio", name_ar="فونيو", sci="Digitaria exilis", fam="Poaceae",
        tags=("subsaharan",), gdd_base_temp=12.0, growing_days=80, water_needs="low",
        max_root_depth_cm=30, attainable_yield_t_ha=1.0, harvest_index=0.20, price_usd_per_ton=800),
    "buckwheat": dict(arch="cereal", name="Buckwheat", name_ar="حنطة سوداء", sci="Fagopyrum esculentum", fam="Polygonaceae",
        tags=("temperate",), growing_days=75, gdd_base_temp=5.0,
        attainable_yield_t_ha=2.5, harvest_index=0.30, price_usd_per_ton=400),
    "quinoa": dict(arch="cereal", name="Quinoa", name_ar="كينوا", sci="Chenopodium quinoa", fam="Amaranthaceae",
        tags=("mediterranean","subtropical"), gdd_base_temp=3.0, growing_days=110,
        water_needs="low", max_root_depth_cm=80, attainable_yield_t_ha=3.0,
        harvest_index=0.35, price_usd_per_ton=2500),
    "amaranth": dict(arch="cereal", name="Amaranth", name_ar="قطيفة", sci="Amaranthus spp.", fam="Amaranthaceae",
        tags=("tropical","subtropical"), gdd_base_temp=10.0, growing_days=90,
        attainable_yield_t_ha=3.0, harvest_index=0.30, price_usd_per_ton=700),
    "spelt": dict(arch="cereal", name="Spelt", name_ar="حنطة الكوسرة", sci="Triticum spelta", fam="Poaceae",
        tags=("temperate","mediterranean"), growing_days=160,
        attainable_yield_t_ha=4.5, harvest_index=0.38, price_usd_per_ton=350),
    "emmer": dict(arch="cereal", name="Emmer Wheat", name_ar="قمح إيمر", sci="Triticum dicoccum", fam="Poaceae",
        tags=("mediterranean","mena"), growing_days=155,
        attainable_yield_t_ha=4.0, harvest_index=0.35, price_usd_per_ton=400),

    # ═══════════════════════════════════════════════════════════════════════
    # MAIZE  (architecture = maize)
    # ═══════════════════════════════════════════════════════════════════════
    "corn": dict(arch="maize", name="Corn / Maize", name_ar="ذرة", sci="Zea mays", fam="Poaceae",
        tags=("temperate","subtropical","tropical","mena","subsaharan","mediterranean")),
    "maize": dict(arch="maize", name="Maize / Corn", name_ar="ذرة", sci="Zea mays", fam="Poaceae",
        tags=("temperate","subtropical","tropical","mena","subsaharan","mediterranean")),
    "sweet_corn": dict(arch="maize", name="Sweet Corn", name_ar="ذرة حلوة", sci="Zea mays var. saccharata", fam="Poaceae",
        tags=("temperate","subtropical"), growing_days=90, attainable_yield_t_ha=20.0,
        harvest_index=0.35, price_usd_per_ton=300),
    "popcorn": dict(arch="maize", name="Popcorn", name_ar="ذرة فشار", sci="Zea mays var. everta", fam="Poaceae",
        tags=("temperate","subtropical"), growing_days=110, attainable_yield_t_ha=5.0,
        harvest_index=0.45, price_usd_per_ton=500),

    # ═══════════════════════════════════════════════════════════════════════
    # RICE  (architecture = rice)
    # ═══════════════════════════════════════════════════════════════════════
    "rice": dict(arch="rice", name="Rice", name_ar="أرز", sci="Oryza sativa", fam="Poaceae",
        tags=("tropical","subtropical","mena","mediterranean")),
    "upland_rice": dict(arch="rice", name="Upland Rice", name_ar="أرز مرتفعات", sci="Oryza sativa", fam="Poaceae",
        tags=("tropical","subsaharan"), water_needs="medium", kc_init=0.50, kc_mid=1.00),
    "wild_rice": dict(arch="rice", name="Wild Rice", name_ar="أرز بري", sci="Zizania palustris", fam="Poaceae",
        tags=("temperate",), growing_days=120, attainable_yield_t_ha=2.0, price_usd_per_ton=1500),

    # ═══════════════════════════════════════════════════════════════════════
    # LEGUMES  (architecture = legume)
    # ═══════════════════════════════════════════════════════════════════════
    "soybean": dict(arch="legume", name="Soybean", name_ar="فول الصويا", sci="Glycine max", fam="Fabaceae",
        tags=("temperate","subtropical","tropical"), gdd_base_temp=10.0,
        removal_n=55.0, removal_p=5.5, removal_k=14.0, attainable_yield_t_ha=4.0,
        response_a_max=4.5, harvest_index=0.40, price_usd_per_ton=400),
    "chickpea": dict(arch="legume", name="Chickpea", name_ar="حمص", sci="Cicer arietinum", fam="Fabaceae",
        tags=("mediterranean","mena","subtropical"), gdd_base_temp=5.0, growing_days=120,
        max_root_depth_cm=100, response_a_max=3.5, attainable_yield_t_ha=3.5,
        harvest_index=0.35, price_usd_per_ton=500),
    "lentil": dict(arch="legume", name="Lentil", name_ar="عدس", sci="Lens culinaris", fam="Fabaceae",
        tags=("mediterranean","mena","temperate"), gdd_base_temp=5.0, growing_days=110,
        max_root_depth_cm=80, attainable_yield_t_ha=2.5, response_a_max=3.0,
        harvest_index=0.35, price_usd_per_ton=550),
    "fava_bean": dict(arch="legume", name="Fava Bean", name_ar="فول", sci="Vicia faba", fam="Fabaceae",
        tags=("mediterranean","mena"), gdd_base_temp=5.0, growing_days=140,
        kc_init=0.50, kc_mid=1.15, kc_end=1.10, attainable_yield_t_ha=4.0,
        harvest_index=0.35, price_usd_per_ton=350),
    "pea": dict(arch="legume", name="Pea", name_ar="بازلاء", sci="Pisum sativum", fam="Fabaceae",
        tags=("temperate","mediterranean"), gdd_base_temp=5.0, growing_days=100,
        max_root_depth_cm=70, kc_init=0.50, kc_mid=1.15, kc_end=1.10,
        harvest_index=0.40, price_usd_per_ton=300),
    "groundnut": dict(arch="legume", name="Groundnut / Peanut", name_ar="فول سوداني", sci="Arachis hypogaea", fam="Fabaceae",
        tags=("tropical","subtropical","subsaharan","mena"), growing_days=130,
        max_root_depth_cm=60, removal_n=45.0, attainable_yield_t_ha=3.5,
        harvest_index=0.35, price_usd_per_ton=500),
    "cowpea": dict(arch="legume", name="Cowpea", name_ar="لوبيا", sci="Vigna unguiculata", fam="Fabaceae",
        tags=("subsaharan","tropical","mena"), growing_days=80, water_needs="low",
        attainable_yield_t_ha=2.0, harvest_index=0.30, price_usd_per_ton=400),
    "pigeon_pea": dict(arch="legume", name="Pigeon Pea", name_ar="بسلة حمام", sci="Cajanus cajan", fam="Fabaceae",
        tags=("tropical","subsaharan"), growing_days=160,
        attainable_yield_t_ha=2.0, harvest_index=0.30, price_usd_per_ton=450),
    "mung_bean": dict(arch="legume", name="Mung Bean", name_ar="ماش", sci="Vigna radiata", fam="Fabaceae",
        tags=("tropical","subtropical","mena"), growing_days=70,
        attainable_yield_t_ha=1.5, harvest_index=0.30, price_usd_per_ton=600),
    "black_eyed_pea": dict(arch="legume", name="Black-Eyed Pea", name_ar="لوبيا سوداء العين", sci="Vigna unguiculata subsp.", fam="Fabaceae",
        tags=("tropical","subsaharan","mena"), growing_days=80,
        attainable_yield_t_ha=2.0, harvest_index=0.30, price_usd_per_ton=400),
    "lima_bean": dict(arch="legume", name="Lima Bean", name_ar="فاصوليا ليما", sci="Phaseolus lunatus", fam="Fabaceae",
        tags=("tropical","subtropical"), growing_days=100,
        attainable_yield_t_ha=2.5, harvest_index=0.35, price_usd_per_ton=500),
    "kidney_bean": dict(arch="legume", name="Kidney Bean", name_ar="فاصوليا حمراء", sci="Phaseolus vulgaris", fam="Fabaceae",
        tags=("temperate","subtropical","mediterranean"), growing_days=90,
        attainable_yield_t_ha=3.0, harvest_index=0.38, price_usd_per_ton=500),
    "white_bean": dict(arch="legume", name="White Bean", name_ar="فاصوليا بيضاء", sci="Phaseolus vulgaris", fam="Fabaceae",
        tags=("temperate","mediterranean"), growing_days=90,
        attainable_yield_t_ha=3.0, harvest_index=0.38, price_usd_per_ton=480),
    "common_bean": dict(arch="legume", name="Common Bean", name_ar="فاصوليا شائعة", sci="Phaseolus vulgaris", fam="Fabaceae",
        tags=("temperate","mediterranean","subtropical"), growing_days=90,
        attainable_yield_t_ha=2.5, harvest_index=0.35, price_usd_per_ton=500),
    "lupin": dict(arch="legume", name="Lupin", name_ar="ترمس", sci="Lupinus spp.", fam="Fabaceae",
        tags=("mediterranean","temperate"), growing_days=130,
        attainable_yield_t_ha=2.5, harvest_index=0.30, price_usd_per_ton=350),
    "vetch": dict(arch="legume", name="Vetch", name_ar="بيقية", sci="Vicia sativa", fam="Fabaceae",
        tags=("mediterranean","temperate"), growing_days=120,
        attainable_yield_t_ha=3.0, harvest_index=0.30, price_usd_per_ton=300),
    "alfalfa": dict(arch="legume", name="Alfalfa", name_ar="برسيم حجازي", sci="Medicago sativa", fam="Fabaceae",
        tags=("mediterranean","mena","temperate","subtropical"), gdd_base_temp=5.0, growing_days=365,
        max_root_depth_cm=200, kc_init=0.40, kc_mid=1.20, kc_end=1.15,
        removal_n=27.0, removal_k=22.0, attainable_yield_t_ha=12.0, n_ceiling_kg_ha=30,
        response_a_max=15.0, response_c_rate=0.008, response_n_soil_default=100,
        harvest_index=0.90, price_usd_per_ton=200),
    "clover": dict(arch="legume", name="Clover", name_ar="برسيم", sci="Trifolium spp.", fam="Fabaceae",
        tags=("mediterranean","temperate","mena"), growing_days=365,
        max_root_depth_cm=100, kc_mid=1.05, attainable_yield_t_ha=10.0,
        harvest_index=0.85, price_usd_per_ton=180),
    "lablab": dict(arch="legume", name="Lablab", name_ar="لوبيا أفريقية", sci="Lablab purpureus", fam="Fabaceae",
        tags=("tropical","subsaharan"), growing_days=120,
        attainable_yield_t_ha=2.0, harvest_index=0.30, price_usd_per_ton=350),
    "bambara_groundnut": dict(arch="legume", name="Bambara Groundnut", name_ar="فول بامبارا", sci="Vigna subterranea", fam="Fabaceae",
        tags=("subsaharan","tropical"), growing_days=130, water_needs="low",
        attainable_yield_t_ha=1.5, harvest_index=0.35, price_usd_per_ton=500),

    # ═══════════════════════════════════════════════════════════════════════
    # VEGETABLES — Fruit Vegetables
    # ═══════════════════════════════════════════════════════════════════════
    "tomato": dict(arch="vegetable", name="Tomato", name_ar="طماطم", sci="Solanum lycopersicum", fam="Solanaceae",
        tags=("mediterranean","mena","subtropical","tropical"),
        max_root_depth_cm=70, kc_init=0.60, kc_mid=1.15, kc_end=0.80,
        removal_n=3.0, attainable_yield_t_ha=80.0, response_a_max=100.0,
        harvest_index=0.60, price_usd_per_ton=120,
        # Tomato-specific: 4th-5th leaf from growing tip at 1st fruit set (Mills & Jones 1996)
        tissue_norms={
            "N":  {"vegetative": (3.0, 3.5, 5.0, 6.0), "reproductive": (2.5, 3.0, 4.5, 5.5)},
            "P":  {"vegetative": (0.25, 0.30, 0.50, 0.80)},
            "K":  {"vegetative": (2.5, 3.0, 5.0, 7.0)},  # Tomatoes are K-hungry
            "S":  {"vegetative": (0.20, 0.30, 0.60, 1.00)},
            "Zn": {"vegetative": (18.0, 25.0, 80.0, 200.0)},
            "B":  {"vegetative": (25.0, 30.0, 80.0, 200.0)},  # High B demand
            "Mn": {"vegetative": (25.0, 30.0, 200.0, 400.0)},
        },
        nue_ae_range=(80.0, 300.0), nue_pfp_range=(200.0, 500.0), nue_re_range=(0.35, 0.60),
        grain_n_pct=0.18),  # Fruit N%
    "pepper": dict(arch="vegetable", name="Pepper", name_ar="فلفل", sci="Capsicum annuum", fam="Solanaceae",
        tags=("mediterranean","mena","subtropical","tropical"), max_root_depth_cm=70,
        kc_mid=1.05, kc_end=0.90, attainable_yield_t_ha=40.0, response_a_max=40.0,
        harvest_index=0.55, price_usd_per_ton=300),
    "hot_pepper": dict(arch="vegetable", name="Hot Pepper / Chili", name_ar="فلفل حار", sci="Capsicum annuum var.", fam="Solanaceae",
        tags=("tropical","mena","subtropical"), max_root_depth_cm=60,
        attainable_yield_t_ha=20.0, harvest_index=0.50, price_usd_per_ton=600),
    "eggplant": dict(arch="vegetable", name="Eggplant", name_ar="باذنجان", sci="Solanum melongena", fam="Solanaceae",
        tags=("mediterranean","mena","subtropical","tropical"), max_root_depth_cm=80,
        kc_mid=1.05, attainable_yield_t_ha=40.0, harvest_index=0.55, price_usd_per_ton=200),
    "cucumber": dict(arch="vegetable", name="Cucumber", name_ar="خيار", sci="Cucumis sativus", fam="Cucurbitaceae",
        tags=("mediterranean","mena","subtropical","tropical"), max_root_depth_cm=70,
        kc_mid=1.00, attainable_yield_t_ha=50.0, harvest_index=0.55, price_usd_per_ton=200),
    "zucchini": dict(arch="vegetable", name="Zucchini", name_ar="كوسة", sci="Cucurbita pepo", fam="Cucurbitaceae",
        tags=("mediterranean","mena","subtropical"), max_root_depth_cm=60,
        attainable_yield_t_ha=40.0, harvest_index=0.55, price_usd_per_ton=180),
    "squash": dict(arch="vegetable", name="Squash", name_ar="قرع", sci="Cucurbita maxima", fam="Cucurbitaceae",
        tags=("temperate","subtropical","mena"), max_root_depth_cm=80,
        attainable_yield_t_ha=30.0, harvest_index=0.50, price_usd_per_ton=200),
    "pumpkin": dict(arch="vegetable", name="Pumpkin", name_ar="يقطين", sci="Cucurbita moschata", fam="Cucurbitaceae",
        tags=("tropical","subtropical","mena","mediterranean"), max_root_depth_cm=100,
        attainable_yield_t_ha=25.0, harvest_index=0.50, price_usd_per_ton=150),
    "watermelon": dict(arch="vegetable", name="Watermelon", name_ar="بطيخ", sci="Citrullus lanatus", fam="Cucurbitaceae",
        tags=("mediterranean","mena","tropical","subsaharan"), max_root_depth_cm=100,
        kc_init=0.40, kc_mid=1.00, growing_days=90, attainable_yield_t_ha=50.0,
        harvest_index=0.60, price_usd_per_ton=100),
    "melon": dict(arch="vegetable", name="Melon", name_ar="شمام", sci="Cucumis melo", fam="Cucurbitaceae",
        tags=("mediterranean","mena","subtropical"), max_root_depth_cm=100,
        kc_init=0.50, kc_mid=1.05, growing_days=90, attainable_yield_t_ha=35.0,
        harvest_index=0.55, price_usd_per_ton=150),
    "okra": dict(arch="vegetable", name="Okra", name_ar="بامية", sci="Abelmoschus esculentus", fam="Malvaceae",
        tags=("tropical","mena","subsaharan","mediterranean"), max_root_depth_cm=60,
        attainable_yield_t_ha=15.0, harvest_index=0.45, price_usd_per_ton=400),
    "bitter_gourd": dict(arch="vegetable", name="Bitter Gourd", name_ar="كارلا", sci="Momordica charantia", fam="Cucurbitaceae",
        tags=("tropical","subtropical"), attainable_yield_t_ha=20.0,
        harvest_index=0.45, price_usd_per_ton=300),
    "bottle_gourd": dict(arch="vegetable", name="Bottle Gourd", name_ar="قرع عسلي", sci="Lagenaria siceraria", fam="Cucurbitaceae",
        tags=("tropical","mena"), attainable_yield_t_ha=25.0, harvest_index=0.50, price_usd_per_ton=150),
    "tomatillo": dict(arch="vegetable", name="Tomatillo", name_ar="توماتيلو", sci="Physalis philadelphica", fam="Solanaceae",
        tags=("subtropical",), attainable_yield_t_ha=25.0, harvest_index=0.50, price_usd_per_ton=250),

    # ═══════════════════════════════════════════════════════════════════════
    # VEGETABLES — Root / Tuber
    # ═══════════════════════════════════════════════════════════════════════
    "potato": dict(arch="vegetable", name="Potato", name_ar="بطاطا", sci="Solanum tuberosum", fam="Solanaceae",
        tags=("mediterranean","mena","temperate","subtropical"),
        gdd_base_temp=7.0, growing_days=110, max_root_depth_cm=60,
        kc_init=0.50, kc_mid=1.15, kc_end=0.75,
        water_stress_sensitivity={"BARE_SOIL":0.0,"EMERGENCE":0.6,"VEGETATIVE":0.5,"REPRODUCTIVE":0.95,"SENESCENCE":0.3,"HARVESTED":0.0},
        removal_n=3.5, removal_p=0.5, removal_k=5.5, attainable_yield_t_ha=40.0, n_ceiling_kg_ha=250,
        response_a_max=50.0, harvest_index=0.75, price_usd_per_ton=200,
        # Potato-specific tissue norms: 4th leaf from tip at tuber init (Westermann 2005)
        tissue_norms={
            "N":  {"vegetative": (3.0, 3.5, 5.0, 6.5), "reproductive": (2.5, 3.0, 4.5, 6.0)},
            "P":  {"vegetative": (0.22, 0.25, 0.50, 0.80)},
            "K":  {"vegetative": (3.5, 4.0, 6.0, 8.0)},  # Potatoes need high K
            "S":  {"vegetative": (0.15, 0.20, 0.40, 0.60)},
            "Zn": {"vegetative": (15.0, 20.0, 60.0, 200.0)},
            "B":  {"vegetative": (15.0, 20.0, 50.0, 150.0)},
            "Mn": {"vegetative": (20.0, 30.0, 200.0, 400.0)},
        },
        nue_ae_range=(60.0, 200.0), nue_pfp_range=(120.0, 350.0), nue_re_range=(0.35, 0.60),
        grain_n_pct=0.32),  # Tuber N%
    "sweet_potato": dict(arch="vegetable", name="Sweet Potato", name_ar="بطاطا حلوة", sci="Ipomoea batatas", fam="Convolvulaceae",
        tags=("tropical","subsaharan","subtropical"), gdd_base_temp=15.0, growing_days=130,
        max_root_depth_cm=80, water_needs="medium", attainable_yield_t_ha=25.0,
        harvest_index=0.65, price_usd_per_ton=180),
    "cassava": dict(arch="vegetable", name="Cassava", name_ar="كسافا", sci="Manihot esculenta", fam="Euphorbiaceae",
        tags=("tropical","subsaharan"), gdd_base_temp=15.0, growing_days=270,
        water_needs="low", max_root_depth_cm=80, kc_init=0.30, kc_mid=0.80, kc_end=0.30,
        attainable_yield_t_ha=25.0, n_ceiling_kg_ha=100, harvest_index=0.55, price_usd_per_ton=80),
    "yam": dict(arch="vegetable", name="Yam", name_ar="يام", sci="Dioscorea rotundata", fam="Dioscoreaceae",
        tags=("tropical","subsaharan"), gdd_base_temp=15.0, growing_days=240,
        max_root_depth_cm=80, attainable_yield_t_ha=20.0,
        harvest_index=0.50, price_usd_per_ton=200),
    "taro": dict(arch="vegetable", name="Taro", name_ar="قلقاس", sci="Colocasia esculenta", fam="Araceae",
        tags=("tropical","subsaharan","mena"), gdd_base_temp=15.0, growing_days=240,
        water_needs="high", max_root_depth_cm=60, attainable_yield_t_ha=15.0,
        harvest_index=0.50, price_usd_per_ton=250),
    "onion": dict(arch="vegetable", name="Onion", name_ar="بصل", sci="Allium cepa", fam="Amaryllidaceae",
        tags=("mediterranean","mena","temperate","subtropical","tropical"),
        gdd_base_temp=5.0, growing_days=120, max_root_depth_cm=40,
        kc_init=0.70, kc_mid=1.05, kc_end=0.75, removal_n=2.5,
        attainable_yield_t_ha=50.0, response_a_max=50.0, harvest_index=0.70, price_usd_per_ton=150),
    "garlic": dict(arch="vegetable", name="Garlic", name_ar="ثوم", sci="Allium sativum", fam="Amaryllidaceae",
        tags=("mediterranean","mena","temperate","subtropical"),
        gdd_base_temp=5.0, growing_days=150, max_root_depth_cm=40,
        kc_init=0.70, kc_mid=1.00, kc_end=0.70, attainable_yield_t_ha=15.0,
        harvest_index=0.65, price_usd_per_ton=500),
    "carrot": dict(arch="vegetable", name="Carrot", name_ar="جزر", sci="Daucus carota", fam="Apiaceae",
        tags=("mediterranean","mena","temperate"),
        gdd_base_temp=5.0, growing_days=100, max_root_depth_cm=50,
        kc_init=0.70, kc_mid=1.05, kc_end=0.95, attainable_yield_t_ha=45.0,
        harvest_index=0.70, price_usd_per_ton=180),
    "beetroot": dict(arch="vegetable", name="Beetroot", name_ar="شمندر", sci="Beta vulgaris", fam="Amaranthaceae",
        tags=("mediterranean","temperate"), gdd_base_temp=5.0, growing_days=90,
        max_root_depth_cm=50, attainable_yield_t_ha=40.0, harvest_index=0.65, price_usd_per_ton=200),
    "radish": dict(arch="vegetable", name="Radish", name_ar="فجل", sci="Raphanus sativus", fam="Brassicaceae",
        tags=("mediterranean","mena","temperate"), gdd_base_temp=5.0, growing_days=45,
        max_root_depth_cm=30, attainable_yield_t_ha=25.0, harvest_index=0.60, price_usd_per_ton=200),
    "turnip": dict(arch="vegetable", name="Turnip", name_ar="لفت", sci="Brassica rapa", fam="Brassicaceae",
        tags=("mediterranean","temperate","mena"), gdd_base_temp=5.0, growing_days=60,
        max_root_depth_cm=40, attainable_yield_t_ha=30.0, harvest_index=0.60, price_usd_per_ton=150),
    "parsnip": dict(arch="vegetable", name="Parsnip", name_ar="جزر أبيض", sci="Pastinaca sativa", fam="Apiaceae",
        tags=("temperate",), gdd_base_temp=5.0, growing_days=120,
        max_root_depth_cm=60, attainable_yield_t_ha=30.0, harvest_index=0.65, price_usd_per_ton=250),
    "ginger": dict(arch="vegetable", name="Ginger", name_ar="زنجبيل", sci="Zingiber officinale", fam="Zingiberaceae",
        tags=("tropical","subtropical"), gdd_base_temp=15.0, growing_days=240,
        max_root_depth_cm=40, attainable_yield_t_ha=20.0, harvest_index=0.50, price_usd_per_ton=800),
    "turmeric": dict(arch="vegetable", name="Turmeric", name_ar="كركم", sci="Curcuma longa", fam="Zingiberaceae",
        tags=("tropical","subtropical"), gdd_base_temp=15.0, growing_days=240,
        max_root_depth_cm=40, attainable_yield_t_ha=15.0, harvest_index=0.45, price_usd_per_ton=1000),
    "sugar_beet": dict(arch="vegetable", name="Sugar Beet", name_ar="شمندر سكري", sci="Beta vulgaris subsp.", fam="Amaranthaceae",
        tags=("temperate","mediterranean"), gdd_base_temp=3.0, growing_days=180,
        max_root_depth_cm=80, kc_mid=1.20, attainable_yield_t_ha=60.0,
        n_ceiling_kg_ha=200, harvest_index=0.60, price_usd_per_ton=50),
    "leek": dict(arch="vegetable", name="Leek", name_ar="كراث", sci="Allium ampeloprasum", fam="Amaryllidaceae",
        tags=("mediterranean","temperate"), gdd_base_temp=5.0, growing_days=120,
        max_root_depth_cm=40, attainable_yield_t_ha=30.0, harvest_index=0.65, price_usd_per_ton=250),

    # ═══════════════════════════════════════════════════════════════════════
    # VEGETABLES — Leaf / Brassica
    # ═══════════════════════════════════════════════════════════════════════
    "lettuce": dict(arch="vegetable", name="Lettuce", name_ar="خس", sci="Lactuca sativa", fam="Asteraceae",
        tags=("mediterranean","mena","temperate","subtropical"),
        gdd_base_temp=5.0, growing_days=60, max_root_depth_cm=30,
        kc_init=0.70, kc_mid=1.00, kc_end=0.95, attainable_yield_t_ha=30.0,
        harvest_index=0.85, price_usd_per_ton=250),
    "cabbage": dict(arch="vegetable", name="Cabbage", name_ar="ملفوف", sci="Brassica oleracea", fam="Brassicaceae",
        tags=("mediterranean","mena","temperate"),
        gdd_base_temp=5.0, growing_days=100, max_root_depth_cm=50,
        kc_mid=1.05, attainable_yield_t_ha=40.0, harvest_index=0.75, price_usd_per_ton=150),
    "spinach": dict(arch="vegetable", name="Spinach", name_ar="سبانخ", sci="Spinacia oleracea", fam="Amaranthaceae",
        tags=("mediterranean","mena","temperate"),
        gdd_base_temp=3.0, growing_days=50, max_root_depth_cm=30,
        attainable_yield_t_ha=20.0, harvest_index=0.85, price_usd_per_ton=300),
    "chard": dict(arch="vegetable", name="Swiss Chard", name_ar="سلق", sci="Beta vulgaris subsp. vulgaris", fam="Amaranthaceae",
        tags=("mediterranean","mena","temperate"), growing_days=60,
        max_root_depth_cm=35, attainable_yield_t_ha=25.0, harvest_index=0.80, price_usd_per_ton=250),
    "kale": dict(arch="vegetable", name="Kale", name_ar="كيل", sci="Brassica oleracea var. sabellica", fam="Brassicaceae",
        tags=("temperate","mediterranean"), growing_days=70,
        attainable_yield_t_ha=20.0, harvest_index=0.80, price_usd_per_ton=350),
    "broccoli": dict(arch="vegetable", name="Broccoli", name_ar="بروكلي", sci="Brassica oleracea var. italica", fam="Brassicaceae",
        tags=("temperate","mediterranean"), growing_days=80,
        max_root_depth_cm=50, attainable_yield_t_ha=15.0, harvest_index=0.40, price_usd_per_ton=400),
    "cauliflower": dict(arch="vegetable", name="Cauliflower", name_ar="قرنبيط", sci="Brassica oleracea var. botrytis", fam="Brassicaceae",
        tags=("temperate","mediterranean","mena"), growing_days=90,
        max_root_depth_cm=50, attainable_yield_t_ha=20.0, harvest_index=0.40, price_usd_per_ton=300),
    "celery": dict(arch="vegetable", name="Celery", name_ar="كرفس", sci="Apium graveolens", fam="Apiaceae",
        tags=("temperate","mediterranean"), growing_days=100,
        max_root_depth_cm=40, attainable_yield_t_ha=50.0, harvest_index=0.75, price_usd_per_ton=250),
    "asparagus": dict(arch="vegetable", name="Asparagus", name_ar="هليون", sci="Asparagus officinalis", fam="Asparagaceae",
        tags=("temperate","mediterranean"), growing_days=365,
        max_root_depth_cm=150, attainable_yield_t_ha=5.0, harvest_index=0.30, price_usd_per_ton=2000),
    "artichoke": dict(arch="vegetable", name="Artichoke", name_ar="خرشوف", sci="Cynara cardunculus", fam="Asteraceae",
        tags=("mediterranean",), growing_days=200,
        max_root_depth_cm=100, attainable_yield_t_ha=12.0, harvest_index=0.35, price_usd_per_ton=500),
    "fennel": dict(arch="vegetable", name="Fennel", name_ar="شمار", sci="Foeniculum vulgare", fam="Apiaceae",
        tags=("mediterranean",), growing_days=100,
        max_root_depth_cm=50, attainable_yield_t_ha=25.0, harvest_index=0.60, price_usd_per_ton=300),
    "arugula": dict(arch="vegetable", name="Arugula / Rocket", name_ar="جرجير", sci="Eruca vesicaria", fam="Brassicaceae",
        tags=("mediterranean","mena"), growing_days=40,
        max_root_depth_cm=25, attainable_yield_t_ha=15.0, harvest_index=0.85, price_usd_per_ton=400),
    "endive": dict(arch="vegetable", name="Endive", name_ar="هندباء", sci="Cichorium endivia", fam="Asteraceae",
        tags=("mediterranean","temperate"), growing_days=80,
        attainable_yield_t_ha=20.0, harvest_index=0.80, price_usd_per_ton=350),
    "moringa": dict(arch="vegetable", name="Moringa", name_ar="مورينجا", sci="Moringa oleifera", fam="Moringaceae",
        tags=("tropical","subsaharan","mena"), growing_days=365,
        water_needs="low", max_root_depth_cm=200, attainable_yield_t_ha=6.0,
        harvest_index=0.40, price_usd_per_ton=1200),
    "nopal": dict(arch="vegetable", name="Nopal / Prickly Pear Pad", name_ar="صبار", sci="Opuntia ficus-indica", fam="Cactaceae",
        tags=("mena","mediterranean","subsaharan"), growing_days=365,
        water_needs="low", max_root_depth_cm=150, attainable_yield_t_ha=30.0,
        harvest_index=0.50, price_usd_per_ton=200),

    # ═══════════════════════════════════════════════════════════════════════
    # HERBS & SPICES  (architecture = vegetable)
    # ═══════════════════════════════════════════════════════════════════════
    "parsley": dict(arch="vegetable", name="Parsley", name_ar="بقدونس", sci="Petroselinum crispum", fam="Apiaceae",
        tags=("mediterranean","mena","temperate"), growing_days=70,
        max_root_depth_cm=30, attainable_yield_t_ha=10.0, harvest_index=0.80, price_usd_per_ton=500),
    "coriander": dict(arch="vegetable", name="Coriander / Cilantro", name_ar="كزبرة", sci="Coriandrum sativum", fam="Apiaceae",
        tags=("mediterranean","mena","tropical"), growing_days=60,
        max_root_depth_cm=30, attainable_yield_t_ha=8.0, harvest_index=0.75, price_usd_per_ton=600),
    "mint": dict(arch="vegetable", name="Mint", name_ar="نعناع", sci="Mentha spp.", fam="Lamiaceae",
        tags=("mediterranean","mena","temperate"), growing_days=90,
        max_root_depth_cm=30, attainable_yield_t_ha=10.0, harvest_index=0.80, price_usd_per_ton=500),
    "basil": dict(arch="vegetable", name="Basil", name_ar="ريحان", sci="Ocimum basilicum", fam="Lamiaceae",
        tags=("mediterranean","tropical"), growing_days=70,
        max_root_depth_cm=30, attainable_yield_t_ha=8.0, harvest_index=0.80, price_usd_per_ton=700),
    "dill": dict(arch="vegetable", name="Dill", name_ar="شبت", sci="Anethum graveolens", fam="Apiaceae",
        tags=("mediterranean","temperate"), growing_days=60,
        max_root_depth_cm=30, attainable_yield_t_ha=6.0, harvest_index=0.75, price_usd_per_ton=600),
    "cumin": dict(arch="vegetable", name="Cumin", name_ar="كمون", sci="Cuminum cyminum", fam="Apiaceae",
        tags=("mena","mediterranean"), growing_days=120,
        water_needs="low", max_root_depth_cm=40, attainable_yield_t_ha=1.5,
        harvest_index=0.30, price_usd_per_ton=3000),
    "fenugreek": dict(arch="vegetable", name="Fenugreek", name_ar="حلبة", sci="Trigonella foenum-graecum", fam="Fabaceae",
        tags=("mena","mediterranean","tropical"), growing_days=100,
        max_root_depth_cm=40, attainable_yield_t_ha=2.0, harvest_index=0.35, price_usd_per_ton=1500),
    "saffron": dict(arch="vegetable", name="Saffron", name_ar="زعفران", sci="Crocus sativus", fam="Iridaceae",
        tags=("mena","mediterranean"), growing_days=200,
        water_needs="low", max_root_depth_cm=20, attainable_yield_t_ha=0.005,
        harvest_index=0.02, price_usd_per_ton=5000000),
    "thyme": dict(arch="vegetable", name="Thyme", name_ar="زعتر", sci="Thymus vulgaris", fam="Lamiaceae",
        tags=("mediterranean","mena"), growing_days=365, water_needs="low",
        max_root_depth_cm=30, attainable_yield_t_ha=5.0, harvest_index=0.70, price_usd_per_ton=1000),
    "rosemary": dict(arch="vegetable", name="Rosemary", name_ar="إكليل الجبل", sci="Salvia rosmarinus", fam="Lamiaceae",
        tags=("mediterranean",), growing_days=365, water_needs="low",
        max_root_depth_cm=80, attainable_yield_t_ha=4.0, harvest_index=0.60, price_usd_per_ton=1200),
    "oregano": dict(arch="vegetable", name="Oregano", name_ar="أوريجانو", sci="Origanum vulgare", fam="Lamiaceae",
        tags=("mediterranean",), growing_days=365, water_needs="low",
        max_root_depth_cm=30, attainable_yield_t_ha=4.0, harvest_index=0.70, price_usd_per_ton=1500),
    "sage": dict(arch="vegetable", name="Sage", name_ar="مريمية", sci="Salvia officinalis", fam="Lamiaceae",
        tags=("mediterranean",), growing_days=365, water_needs="low",
        max_root_depth_cm=50, attainable_yield_t_ha=3.0, harvest_index=0.60, price_usd_per_ton=1200),
    "lavender": dict(arch="vegetable", name="Lavender", name_ar="لافندر", sci="Lavandula angustifolia", fam="Lamiaceae",
        tags=("mediterranean",), growing_days=365, water_needs="low",
        max_root_depth_cm=60, attainable_yield_t_ha=3.0, harvest_index=0.50, price_usd_per_ton=2000),
    "anise": dict(arch="vegetable", name="Anise", name_ar="يانسون", sci="Pimpinella anisum", fam="Apiaceae",
        tags=("mediterranean","mena"), growing_days=120,
        max_root_depth_cm=40, attainable_yield_t_ha=1.5, harvest_index=0.30, price_usd_per_ton=2500),
    "sesame": dict(arch="vegetable", name="Sesame", name_ar="سمسم", sci="Sesamum indicum", fam="Pedaliaceae",
        tags=("mena","tropical","subsaharan"), growing_days=110,
        water_needs="low", max_root_depth_cm=60, attainable_yield_t_ha=1.5,
        harvest_index=0.25, price_usd_per_ton=1200),
    "nigella": dict(arch="vegetable", name="Nigella / Black Seed", name_ar="حبة البركة", sci="Nigella sativa", fam="Ranunculaceae",
        tags=("mena","mediterranean"), growing_days=100,
        max_root_depth_cm=30, attainable_yield_t_ha=1.0, harvest_index=0.25, price_usd_per_ton=3000),
    "caraway": dict(arch="vegetable", name="Caraway", name_ar="كراوية", sci="Carum carvi", fam="Apiaceae",
        tags=("mediterranean","temperate"), growing_days=120,
        max_root_depth_cm=40, attainable_yield_t_ha=1.5, harvest_index=0.30, price_usd_per_ton=2000),
    "black_pepper": dict(arch="vegetable", name="Black Pepper", name_ar="فلفل أسود", sci="Piper nigrum", fam="Piperaceae",
        tags=("tropical",), growing_days=365, gdd_base_temp=18.0,
        max_root_depth_cm=60, attainable_yield_t_ha=3.0, harvest_index=0.30, price_usd_per_ton=5000),

    # ═══════════════════════════════════════════════════════════════════════
    # PERENNIAL FRUIT TREES  (architecture = perennial)
    # ═══════════════════════════════════════════════════════════════════════
    "olive": dict(arch="perennial", name="Olive", name_ar="زيتون", sci="Olea europaea", fam="Oleaceae",
        tags=("mediterranean","mena"),
        water_needs="low", max_root_depth_cm=200, kc_init=0.65, kc_mid=0.70, kc_end=0.65,
        water_stress_sensitivity={"BARE_SOIL":0.0,"EMERGENCE":0.2,"VEGETATIVE":0.2,"REPRODUCTIVE":0.7,"SENESCENCE":0.1,"HARVESTED":0.0},
        removal_n=15.0, removal_k=20.0, attainable_yield_t_ha=8.0,
        response_a_max=8.0, harvest_index=0.15, price_usd_per_ton=800,
        # Olive-specific: July leaves, current year shoots (Fernandez-Escobar 2017)
        tissue_norms={
            "N":  {"vegetative": (1.4, 1.5, 2.0, 2.5)},
            "P":  {"vegetative": (0.08, 0.10, 0.15, 0.30)},
            "K":  {"vegetative": (0.60, 0.80, 1.2, 1.8)},
            "S":  {"vegetative": (0.08, 0.10, 0.20, 0.40)},
            "Zn": {"vegetative": (10.0, 15.0, 50.0, 150.0)},
            "B":  {"vegetative": (14.0, 19.0, 50.0, 150.0)},
            "Fe": {"vegetative": (30.0, 50.0, 150.0, 300.0)},
            "Mn": {"vegetative": (15.0, 20.0, 100.0, 300.0)},
        },
        dris_norms={"N/P": (15.0, 4.0), "N/K": (1.5, 0.4), "N/S": (14.0, 3.0)},
        nue_ae_range=(20.0, 60.0), nue_pfp_range=(30.0, 80.0), nue_re_range=(0.15, 0.35),
        grain_n_pct=0.15),  # Olive fruit N%
    "date_palm": dict(arch="perennial", name="Date Palm", name_ar="نخيل التمر", sci="Phoenix dactylifera", fam="Arecaceae",
        tags=("mena","subsaharan","tropical"),
        gdd_base_temp=18.0, optimal_temp_min=25, optimal_temp_max=45,
        max_root_depth_cm=250, kc_init=0.90, kc_mid=0.95, kc_end=0.95,
        attainable_yield_t_ha=12.0, response_a_max=12.0,
        harvest_index=0.20, price_usd_per_ton=1000),
    "citrus": dict(arch="perennial", name="Citrus", name_ar="حمضيات", sci="Citrus spp.", fam="Rutaceae",
        tags=("mediterranean","mena","subtropical","tropical"),
        gdd_base_temp=13.0, max_root_depth_cm=150,
        kc_init=0.70, kc_mid=0.65, kc_end=0.65,
        water_stress_sensitivity={"BARE_SOIL":0.0,"EMERGENCE":0.3,"VEGETATIVE":0.3,"REPRODUCTIVE":0.85,"SENESCENCE":0.15,"HARVESTED":0.0},
        attainable_yield_t_ha=40.0, response_a_max=40.0,
        harvest_index=0.30, price_usd_per_ton=300,
        # Citrus-specific: 5-7 month old spring flush leaves (Embleton et al. 1973)
        tissue_norms={
            "N":  {"vegetative": (2.2, 2.4, 2.8, 3.2)},
            "P":  {"vegetative": (0.09, 0.12, 0.17, 0.30)},
            "K":  {"vegetative": (0.70, 1.2, 1.7, 2.4)},
            "S":  {"vegetative": (0.14, 0.20, 0.30, 0.50)},
            "Zn": {"vegetative": (18.0, 25.0, 80.0, 300.0)},
            "B":  {"vegetative": (31.0, 36.0, 100.0, 250.0)},  # Citrus high B demand
            "Fe": {"vegetative": (36.0, 60.0, 120.0, 300.0)},
            "Mn": {"vegetative": (18.0, 25.0, 100.0, 300.0)},
            "Cu": {"vegetative": (3.6, 5.0, 16.0, 30.0)},
        },
        dris_norms={"N/P": (18.0, 4.0), "N/K": (1.8, 0.4), "N/S": (13.0, 3.0)},
        nue_ae_range=(50.0, 150.0), nue_pfp_range=(80.0, 200.0), nue_re_range=(0.20, 0.40),
        grain_n_pct=0.15),  # Fruit N%
    "orange": dict(arch="perennial", name="Orange", name_ar="برتقال", sci="Citrus sinensis", fam="Rutaceae",
        tags=("mediterranean","mena","subtropical","tropical"),
        gdd_base_temp=13.0, max_root_depth_cm=150, kc_init=0.70, kc_mid=0.65, kc_end=0.65,
        attainable_yield_t_ha=40.0, harvest_index=0.30, price_usd_per_ton=280),
    "lemon": dict(arch="perennial", name="Lemon", name_ar="ليمون", sci="Citrus limon", fam="Rutaceae",
        tags=("mediterranean","mena","subtropical"),
        gdd_base_temp=13.0, max_root_depth_cm=130, kc_mid=0.65,
        attainable_yield_t_ha=30.0, harvest_index=0.28, price_usd_per_ton=350),
    "mandarin": dict(arch="perennial", name="Mandarin", name_ar="يوسفي", sci="Citrus reticulata", fam="Rutaceae",
        tags=("mediterranean","mena","subtropical"),
        gdd_base_temp=13.0, attainable_yield_t_ha=30.0, harvest_index=0.30, price_usd_per_ton=350),
    "clementine": dict(arch="perennial", name="Clementine", name_ar="كلمنتينا", sci="Citrus clementina", fam="Rutaceae",
        tags=("mediterranean","mena","subtropical"),
        gdd_base_temp=13.0, attainable_yield_t_ha=28.0, harvest_index=0.30, price_usd_per_ton=380),
    "grapefruit": dict(arch="perennial", name="Grapefruit", name_ar="جريب فروت", sci="Citrus × paradisi", fam="Rutaceae",
        tags=("subtropical","tropical"), gdd_base_temp=13.0,
        attainable_yield_t_ha=45.0, harvest_index=0.30, price_usd_per_ton=250),
    "grape": dict(arch="perennial", name="Grape / Vine", name_ar="عنب", sci="Vitis vinifera", fam="Vitaceae",
        tags=("mediterranean","temperate","mena","subtropical"),
        kc_init=0.30, kc_mid=0.85, kc_end=0.45,
        attainable_yield_t_ha=15.0, response_a_max=15.0,
        harvest_index=0.40, price_usd_per_ton=400),
    "fig": dict(arch="perennial", name="Fig", name_ar="تين", sci="Ficus carica", fam="Moraceae",
        tags=("mediterranean","mena"),
        water_needs="low", kc_init=0.40, kc_mid=0.85, kc_end=0.55,
        attainable_yield_t_ha=10.0, harvest_index=0.30, price_usd_per_ton=600),
    "pomegranate": dict(arch="perennial", name="Pomegranate", name_ar="رمان", sci="Punica granatum", fam="Lythraceae",
        tags=("mediterranean","mena","subtropical"),
        max_root_depth_cm=150, kc_init=0.45, kc_mid=0.85, kc_end=0.65,
        attainable_yield_t_ha=15.0, harvest_index=0.30, price_usd_per_ton=500),
    "almond": dict(arch="perennial", name="Almond", name_ar="لوز", sci="Prunus dulcis", fam="Rosaceae",
        tags=("mediterranean","mena","temperate"),
        gdd_base_temp=7.0, kc_init=0.40, kc_mid=0.90, kc_end=0.65,
        attainable_yield_t_ha=4.0, harvest_index=0.20, price_usd_per_ton=3000),
    "pistachio": dict(arch="perennial", name="Pistachio", name_ar="فستق", sci="Pistacia vera", fam="Anacardiaceae",
        tags=("mediterranean","mena"), water_needs="low",
        gdd_base_temp=7.0, kc_mid=0.80, max_root_depth_cm=250,
        attainable_yield_t_ha=3.0, harvest_index=0.15, price_usd_per_ton=6000),
    "walnut": dict(arch="perennial", name="Walnut", name_ar="جوز", sci="Juglans regia", fam="Juglandaceae",
        tags=("temperate","mediterranean"),
        gdd_base_temp=7.0, max_root_depth_cm=250,
        attainable_yield_t_ha=5.0, harvest_index=0.20, price_usd_per_ton=3000),
    "pecan": dict(arch="perennial", name="Pecan", name_ar="بقان", sci="Carya illinoinensis", fam="Juglandaceae",
        tags=("temperate","subtropical"),
        gdd_base_temp=7.0, max_root_depth_cm=250,
        attainable_yield_t_ha=3.0, harvest_index=0.18, price_usd_per_ton=3500),
    "hazelnut": dict(arch="perennial", name="Hazelnut", name_ar="بندق", sci="Corylus avellana", fam="Betulaceae",
        tags=("temperate","mediterranean"),
        gdd_base_temp=7.0, attainable_yield_t_ha=3.0, harvest_index=0.18, price_usd_per_ton=4000),
    "chestnut": dict(arch="perennial", name="Chestnut", name_ar="كستناء", sci="Castanea sativa", fam="Fagaceae",
        tags=("temperate","mediterranean"),
        gdd_base_temp=7.0, attainable_yield_t_ha=4.0, harvest_index=0.20, price_usd_per_ton=2500),
    "carob": dict(arch="perennial", name="Carob", name_ar="خروب", sci="Ceratonia siliqua", fam="Fabaceae",
        tags=("mediterranean","mena"), water_needs="low",
        attainable_yield_t_ha=5.0, harvest_index=0.25, price_usd_per_ton=800),
    "apricot": dict(arch="perennial", name="Apricot", name_ar="مشمش", sci="Prunus armeniaca", fam="Rosaceae",
        tags=("mediterranean","mena","temperate"),
        gdd_base_temp=7.0, kc_init=0.40, kc_mid=0.90, kc_end=0.65,
        attainable_yield_t_ha=12.0, harvest_index=0.30, price_usd_per_ton=500),
    "peach": dict(arch="perennial", name="Peach", name_ar="خوخ", sci="Prunus persica", fam="Rosaceae",
        tags=("mediterranean","temperate","mena"),
        gdd_base_temp=7.0, kc_init=0.45, kc_mid=0.90, kc_end=0.65,
        attainable_yield_t_ha=20.0, harvest_index=0.35, price_usd_per_ton=400),
    "plum": dict(arch="perennial", name="Plum", name_ar="برقوق", sci="Prunus domestica", fam="Rosaceae",
        tags=("mediterranean","temperate"), gdd_base_temp=7.0,
        attainable_yield_t_ha=15.0, harvest_index=0.35, price_usd_per_ton=400),
    "cherry": dict(arch="perennial", name="Cherry", name_ar="كرز", sci="Prunus avium", fam="Rosaceae",
        tags=("temperate","mediterranean"), gdd_base_temp=7.0,
        attainable_yield_t_ha=8.0, harvest_index=0.25, price_usd_per_ton=1500),
    "apple": dict(arch="perennial", name="Apple", name_ar="تفاح", sci="Malus domestica", fam="Rosaceae",
        tags=("temperate","mediterranean"),
        gdd_base_temp=7.0, kc_init=0.50, kc_mid=0.95, kc_end=0.70,
        attainable_yield_t_ha=30.0, harvest_index=0.35, price_usd_per_ton=350),
    "pear": dict(arch="perennial", name="Pear", name_ar="إجاص", sci="Pyrus communis", fam="Rosaceae",
        tags=("temperate","mediterranean"), gdd_base_temp=7.0,
        kc_mid=0.90, attainable_yield_t_ha=25.0, harvest_index=0.35, price_usd_per_ton=400),
    "quince": dict(arch="perennial", name="Quince", name_ar="سفرجل", sci="Cydonia oblonga", fam="Rosaceae",
        tags=("mediterranean","temperate"), gdd_base_temp=7.0,
        attainable_yield_t_ha=15.0, harvest_index=0.35, price_usd_per_ton=350),
    "persimmon": dict(arch="perennial", name="Persimmon", name_ar="كاكا", sci="Diospyros kaki", fam="Ebenaceae",
        tags=("subtropical","mediterranean"), gdd_base_temp=10.0,
        attainable_yield_t_ha=15.0, harvest_index=0.35, price_usd_per_ton=500),
    "loquat": dict(arch="perennial", name="Loquat", name_ar="بشملة", sci="Eriobotrya japonica", fam="Rosaceae",
        tags=("mediterranean","subtropical"), gdd_base_temp=10.0,
        attainable_yield_t_ha=10.0, harvest_index=0.30, price_usd_per_ton=600),
    "avocado": dict(arch="perennial", name="Avocado", name_ar="أفوكادو", sci="Persea americana", fam="Lauraceae",
        tags=("subtropical","tropical","mediterranean"),
        gdd_base_temp=10.0, water_needs="high", max_root_depth_cm=150,
        attainable_yield_t_ha=12.0, harvest_index=0.25, price_usd_per_ton=1500),
    "argan": dict(arch="perennial", name="Argan", name_ar="أرغان", sci="Argania spinosa", fam="Sapotaceae",
        tags=("mena",), water_needs="low", max_root_depth_cm=300,
        attainable_yield_t_ha=3.0, harvest_index=0.10, price_usd_per_ton=8000),
    "jujube": dict(arch="perennial", name="Jujube", name_ar="عناب", sci="Ziziphus jujuba", fam="Rhamnaceae",
        tags=("mena","mediterranean","subtropical"), water_needs="low",
        attainable_yield_t_ha=10.0, harvest_index=0.30, price_usd_per_ton=600),
    "mulberry": dict(arch="perennial", name="Mulberry", name_ar="توت", sci="Morus alba", fam="Moraceae",
        tags=("mediterranean","subtropical","temperate"),
        attainable_yield_t_ha=10.0, harvest_index=0.30, price_usd_per_ton=500),
    "prickly_pear": dict(arch="perennial", name="Prickly Pear (Fruit)", name_ar="تين شوكي", sci="Opuntia ficus-indica", fam="Cactaceae",
        tags=("mena","mediterranean","subsaharan"), water_needs="low",
        max_root_depth_cm=150, attainable_yield_t_ha=20.0,
        harvest_index=0.40, price_usd_per_ton=300),

    # ═══════════════════════════════════════════════════════════════════════
    # BERRIES  (architecture = perennial)
    # ═══════════════════════════════════════════════════════════════════════
    "strawberry": dict(arch="perennial", name="Strawberry", name_ar="فراولة", sci="Fragaria × ananassa", fam="Rosaceae",
        tags=("temperate","mediterranean","subtropical"),
        max_root_depth_cm=30, growing_days=120, kc_init=0.40, kc_mid=0.85, kc_end=0.75,
        attainable_yield_t_ha=25.0, harvest_index=0.55, price_usd_per_ton=1500),
    "raspberry": dict(arch="perennial", name="Raspberry", name_ar="توت العليق", sci="Rubus idaeus", fam="Rosaceae",
        tags=("temperate",), max_root_depth_cm=60,
        attainable_yield_t_ha=8.0, harvest_index=0.40, price_usd_per_ton=3000),
    "blueberry": dict(arch="perennial", name="Blueberry", name_ar="توت أزرق", sci="Vaccinium corymbosum", fam="Ericaceae",
        tags=("temperate",), max_root_depth_cm=40,
        attainable_yield_t_ha=8.0, harvest_index=0.40, price_usd_per_ton=4000),
    "blackberry": dict(arch="perennial", name="Blackberry", name_ar="توت أسود", sci="Rubus fruticosus", fam="Rosaceae",
        tags=("temperate","mediterranean"), max_root_depth_cm=80,
        attainable_yield_t_ha=10.0, harvest_index=0.45, price_usd_per_ton=2500),

    # ═══════════════════════════════════════════════════════════════════════
    # TROPICAL FRUITS & TREES  (architecture = tropical_tree)
    # ═══════════════════════════════════════════════════════════════════════
    "banana": dict(arch="tropical_tree", name="Banana", name_ar="موز", sci="Musa spp.", fam="Musaceae",
        tags=("tropical","subtropical"),
        gdd_base_temp=14.0, max_root_depth_cm=80,
        kc_init=0.50, kc_mid=1.10, kc_end=1.00,
        attainable_yield_t_ha=40.0, harvest_index=0.35, price_usd_per_ton=300),
    "plantain": dict(arch="tropical_tree", name="Plantain", name_ar="موز الطبخ", sci="Musa × paradisiaca", fam="Musaceae",
        tags=("tropical","subsaharan"), gdd_base_temp=14.0,
        attainable_yield_t_ha=25.0, harvest_index=0.35, price_usd_per_ton=200),
    "mango": dict(arch="tropical_tree", name="Mango", name_ar="مانجو", sci="Mangifera indica", fam="Anacardiaceae",
        tags=("tropical","subtropical","mena"),
        attainable_yield_t_ha=15.0, harvest_index=0.30, price_usd_per_ton=500),
    "papaya": dict(arch="tropical_tree", name="Papaya", name_ar="بابايا", sci="Carica papaya", fam="Caricaceae",
        tags=("tropical",), attainable_yield_t_ha=40.0,
        harvest_index=0.40, price_usd_per_ton=300),
    "pineapple": dict(arch="tropical_tree", name="Pineapple", name_ar="أناناس", sci="Ananas comosus", fam="Bromeliaceae",
        tags=("tropical",), max_root_depth_cm=60,
        attainable_yield_t_ha=50.0, harvest_index=0.45, price_usd_per_ton=250),
    "guava": dict(arch="tropical_tree", name="Guava", name_ar="جوافة", sci="Psidium guajava", fam="Myrtaceae",
        tags=("tropical","subtropical","mena"),
        attainable_yield_t_ha=20.0, harvest_index=0.35, price_usd_per_ton=400),
    "passion_fruit": dict(arch="tropical_tree", name="Passion Fruit", name_ar="فاكهة العاطفة", sci="Passiflora edulis", fam="Passifloraceae",
        tags=("tropical","subtropical"),
        attainable_yield_t_ha=15.0, harvest_index=0.30, price_usd_per_ton=600),
    "coconut": dict(arch="tropical_tree", name="Coconut", name_ar="جوز الهند", sci="Cocos nucifera", fam="Arecaceae",
        tags=("tropical",), max_root_depth_cm=200,
        attainable_yield_t_ha=5.0, harvest_index=0.20, price_usd_per_ton=250),
    "jackfruit": dict(arch="tropical_tree", name="Jackfruit", name_ar="جاك فروت", sci="Artocarpus heterophyllus", fam="Moraceae",
        tags=("tropical",), attainable_yield_t_ha=20.0, harvest_index=0.30, price_usd_per_ton=350),
    "breadfruit": dict(arch="tropical_tree", name="Breadfruit", name_ar="فاكهة الخبز", sci="Artocarpus altilis", fam="Moraceae",
        tags=("tropical",), attainable_yield_t_ha=15.0, harvest_index=0.35, price_usd_per_ton=200),
    "tamarind": dict(arch="tropical_tree", name="Tamarind", name_ar="تمر هندي", sci="Tamarindus indica", fam="Fabaceae",
        tags=("tropical","subsaharan","mena"),
        attainable_yield_t_ha=8.0, harvest_index=0.25, price_usd_per_ton=800),
    "lychee": dict(arch="tropical_tree", name="Lychee", name_ar="ليتشي", sci="Litchi chinensis", fam="Sapindaceae",
        tags=("tropical","subtropical"),
        attainable_yield_t_ha=10.0, harvest_index=0.25, price_usd_per_ton=1500),
    "dragon_fruit": dict(arch="tropical_tree", name="Dragon Fruit", name_ar="فاكهة التنين", sci="Hylocereus undatus", fam="Cactaceae",
        tags=("tropical","subtropical"), water_needs="low",
        attainable_yield_t_ha=20.0, harvest_index=0.40, price_usd_per_ton=1500),
    "cashew": dict(arch="tropical_tree", name="Cashew", name_ar="كاجو", sci="Anacardium occidentale", fam="Anacardiaceae",
        tags=("tropical","subsaharan"),
        attainable_yield_t_ha=1.5, harvest_index=0.10, price_usd_per_ton=5000),
    "macadamia": dict(arch="tropical_tree", name="Macadamia", name_ar="مكاديميا", sci="Macadamia integrifolia", fam="Proteaceae",
        tags=("tropical","subtropical"),
        attainable_yield_t_ha=3.0, harvest_index=0.12, price_usd_per_ton=8000),

    # ═══════════════════════════════════════════════════════════════════════
    # INDUSTRIAL / FIBER / CASH CROPS  (architecture = cotton)
    # ═══════════════════════════════════════════════════════════════════════
    "cotton": dict(arch="cotton", name="Cotton", name_ar="قطن", sci="Gossypium hirsutum", fam="Malvaceae",
        tags=("tropical","subtropical","mena","mediterranean")),
    "flax": dict(arch="cotton", name="Flax / Linseed", name_ar="كتان", sci="Linum usitatissimum", fam="Linaceae",
        tags=("temperate","mediterranean"), gdd_base_temp=5.0, growing_days=120,
        removal_n=25.0, attainable_yield_t_ha=2.5,
        harvest_index=0.30, price_usd_per_ton=800),
    "hemp": dict(arch="cotton", name="Hemp", name_ar="قنب", sci="Cannabis sativa", fam="Cannabaceae",
        tags=("temperate","subtropical"), gdd_base_temp=5.0, growing_days=120,
        attainable_yield_t_ha=8.0, harvest_index=0.30, price_usd_per_ton=400),
    "jute": dict(arch="cotton", name="Jute", name_ar="جوت", sci="Corchorus capsularis", fam="Malvaceae",
        tags=("tropical",), gdd_base_temp=15.0, growing_days=120,
        attainable_yield_t_ha=3.0, harvest_index=0.35, price_usd_per_ton=500),
    "sisal": dict(arch="cotton", name="Sisal", name_ar="سيسال", sci="Agave sisalana", fam="Asparagaceae",
        tags=("tropical","subsaharan"), growing_days=365, water_needs="low",
        attainable_yield_t_ha=2.0, harvest_index=0.20, price_usd_per_ton=1000),
    "kenaf": dict(arch="cotton", name="Kenaf", name_ar="كيناف", sci="Hibiscus cannabinus", fam="Malvaceae",
        tags=("tropical","subtropical"), growing_days=120,
        attainable_yield_t_ha=12.0, harvest_index=0.35, price_usd_per_ton=300),

    # Oilseeds (use cereal architecture for annual oilseeds)
    "sunflower": dict(arch="cereal", name="Sunflower", name_ar="عباد الشمس", sci="Helianthus annuus", fam="Asteraceae",
        tags=("temperate","mediterranean","mena","subtropical"),
        gdd_base_temp=6.0, growing_days=120, max_root_depth_cm=150,
        removal_n=30.0, removal_p=7.0, removal_k=12.0, attainable_yield_t_ha=3.0, n_ceiling_kg_ha=150,
        response_a_max=3.5, harvest_index=0.30, price_usd_per_ton=400),
    "canola": dict(arch="cereal", name="Canola / Rapeseed", name_ar="كانولا", sci="Brassica napus", fam="Brassicaceae",
        tags=("temperate","mediterranean"),
        gdd_base_temp=5.0, growing_days=140,
        removal_n=35.0, removal_p=6.0, removal_k=8.0, attainable_yield_t_ha=3.5, n_ceiling_kg_ha=200,
        response_a_max=4.0, harvest_index=0.25, price_usd_per_ton=450),

    # Sugar & stimulants (use maize arch for sugarcane, tropical_tree for others)
    "sugarcane": dict(arch="maize", name="Sugarcane", name_ar="قصب السكر", sci="Saccharum officinarum", fam="Poaceae",
        tags=("tropical","subtropical"),
        gdd_base_temp=12.0, growing_days=365, max_root_depth_cm=150,
        kc_init=0.40, kc_mid=1.25, kc_end=0.75,
        removal_n=1.0, removal_k=2.0, attainable_yield_t_ha=80.0, n_ceiling_kg_ha=250,
        response_a_max=100.0, harvest_index=0.80, price_usd_per_ton=40),
    "tobacco": dict(arch="vegetable", name="Tobacco", name_ar="تبغ", sci="Nicotiana tabacum", fam="Solanaceae",
        tags=("subtropical","tropical","mena"),
        growing_days=120, max_root_depth_cm=80,
        kc_mid=1.10, attainable_yield_t_ha=3.0,
        harvest_index=0.50, price_usd_per_ton=3000),
    "coffee": dict(arch="tropical_tree", name="Coffee", name_ar="قهوة", sci="Coffea arabica", fam="Rubiaceae",
        tags=("tropical","subtropical"),
        max_root_depth_cm=150, kc_init=0.90, kc_mid=0.95, kc_end=0.95,
        attainable_yield_t_ha=2.5, harvest_index=0.20, price_usd_per_ton=3000),
    "cocoa": dict(arch="tropical_tree", name="Cocoa", name_ar="كاكاو", sci="Theobroma cacao", fam="Malvaceae",
        tags=("tropical",), kc_init=1.00, kc_mid=1.05, kc_end=1.05,
        attainable_yield_t_ha=1.5, harvest_index=0.15, price_usd_per_ton=3500),
    "tea": dict(arch="tropical_tree", name="Tea", name_ar="شاي", sci="Camellia sinensis", fam="Theaceae",
        tags=("tropical","subtropical"),
        max_root_depth_cm=150, attainable_yield_t_ha=3.0,
        harvest_index=0.30, price_usd_per_ton=2500),
    "oil_palm": dict(arch="tropical_tree", name="Oil Palm", name_ar="نخيل الزيت", sci="Elaeis guineensis", fam="Arecaceae",
        tags=("tropical",), max_root_depth_cm=200,
        attainable_yield_t_ha=20.0, harvest_index=0.25, price_usd_per_ton=400),
    "rubber": dict(arch="tropical_tree", name="Rubber", name_ar="مطاط", sci="Hevea brasiliensis", fam="Euphorbiaceae",
        tags=("tropical",), max_root_depth_cm=200,
        attainable_yield_t_ha=2.0, harvest_index=0.10, price_usd_per_ton=1500),
    "henna": dict(arch="perennial", name="Henna", name_ar="حناء", sci="Lawsonia inermis", fam="Lythraceae",
        tags=("mena","tropical","subsaharan"), water_needs="low",
        attainable_yield_t_ha=2.0, harvest_index=0.40, price_usd_per_ton=1500),

    # ═══════════════════════════════════════════════════════════════════════
    # FORAGE  (architecture = legume or cereal)
    # ═══════════════════════════════════════════════════════════════════════
    "ryegrass": dict(arch="cereal", name="Ryegrass", name_ar="راي غراس", sci="Lolium perenne", fam="Poaceae",
        tags=("temperate","mediterranean"), growing_days=365,
        kc_mid=1.05, attainable_yield_t_ha=12.0, harvest_index=0.85, price_usd_per_ton=150),
    "bermuda_grass": dict(arch="cereal", name="Bermuda Grass", name_ar="نجيل", sci="Cynodon dactylon", fam="Poaceae",
        tags=("tropical","subtropical","mena"), gdd_base_temp=10.0, growing_days=365,
        water_needs="low", attainable_yield_t_ha=15.0, harvest_index=0.80, price_usd_per_ton=120),
    "sudan_grass": dict(arch="cereal", name="Sudan Grass", name_ar="ذرة سودانية", sci="Sorghum × drummondii", fam="Poaceae",
        tags=("tropical","subtropical","mena"), gdd_base_temp=10.0, growing_days=90,
        attainable_yield_t_ha=12.0, harvest_index=0.80, price_usd_per_ton=140),
    "berseem": dict(arch="legume", name="Berseem / Egyptian Clover", name_ar="برسيم مصري", sci="Trifolium alexandrinum", fam="Fabaceae",
        tags=("mena","mediterranean"), growing_days=150,
        attainable_yield_t_ha=15.0, harvest_index=0.85, price_usd_per_ton=180),
    "oat_forage": dict(arch="cereal", name="Oat (Forage)", name_ar="شوفان علفي", sci="Avena sativa", fam="Poaceae",
        tags=("temperate","mediterranean","mena"), growing_days=100,
        attainable_yield_t_ha=10.0, harvest_index=0.85, price_usd_per_ton=150),
    "sorghum_forage": dict(arch="cereal", name="Sorghum (Forage)", name_ar="ذرة رفيعة علفية", sci="Sorghum bicolor", fam="Poaceae",
        tags=("tropical","subtropical","mena"), gdd_base_temp=10.0, growing_days=80,
        attainable_yield_t_ha=20.0, harvest_index=0.85, price_usd_per_ton=100),

    # ═══════════════════════════════════════════════════════════════════════
    # AFRICAN ORPHAN CROPS  (various architectures)
    # ═══════════════════════════════════════════════════════════════════════
    "enset": dict(arch="tropical_tree", name="Enset / False Banana", name_ar="إنسيت", sci="Ensete ventricosum", fam="Musaceae",
        tags=("subsaharan",), growing_days=365,
        max_root_depth_cm=80, attainable_yield_t_ha=15.0, harvest_index=0.40, price_usd_per_ton=200),
    "baobab": dict(arch="tropical_tree", name="Baobab", name_ar="باوباب", sci="Adansonia digitata", fam="Malvaceae",
        tags=("subsaharan",), water_needs="low",
        attainable_yield_t_ha=5.0, harvest_index=0.15, price_usd_per_ton=3000),
    "shea": dict(arch="tropical_tree", name="Shea", name_ar="شيا", sci="Vitellaria paradoxa", fam="Sapotaceae",
        tags=("subsaharan",), water_needs="low",
        attainable_yield_t_ha=3.0, harvest_index=0.10, price_usd_per_ton=2000),
    "tiger_nut": dict(arch="vegetable", name="Tiger Nut", name_ar="حب العزيز", sci="Cyperus esculentus", fam="Cyperaceae",
        tags=("mena","subsaharan","mediterranean"), growing_days=120,
        max_root_depth_cm=30, attainable_yield_t_ha=8.0, harvest_index=0.40, price_usd_per_ton=1000),
    "roselle": dict(arch="vegetable", name="Roselle / Hibiscus", name_ar="كركديه", sci="Hibiscus sabdariffa", fam="Malvaceae",
        tags=("mena","subsaharan","tropical"), growing_days=150,
        max_root_depth_cm=50, attainable_yield_t_ha=2.0, harvest_index=0.25, price_usd_per_ton=2000),
    "vernonia": dict(arch="vegetable", name="Vernonia (Oilseed)", name_ar="فرنونيا", sci="Vernonia galamensis", fam="Asteraceae",
        tags=("subsaharan",), growing_days=120,
        attainable_yield_t_ha=2.0, harvest_index=0.25, price_usd_per_ton=600),

    # ═══════════════════════════════════════════════════════════════════════
    # ADDITIONAL — reach 200+
    # ═══════════════════════════════════════════════════════════════════════
    "jojoba": dict(arch="perennial", name="Jojoba", name_ar="جوجوبا", sci="Simmondsia chinensis", fam="Simmondsiaceae",
        tags=("mena","subsaharan"), water_needs="low", max_root_depth_cm=300,
        attainable_yield_t_ha=2.0, harvest_index=0.15, price_usd_per_ton=5000),
    "safflower": dict(arch="cereal", name="Safflower", name_ar="قرطم", sci="Carthamus tinctorius", fam="Asteraceae",
        tags=("mena","mediterranean","temperate"), growing_days=130, water_needs="low",
        attainable_yield_t_ha=2.5, harvest_index=0.25, price_usd_per_ton=600),
    "rambutan": dict(arch="tropical_tree", name="Rambutan", name_ar="رامبوتان", sci="Nephelium lappaceum", fam="Sapindaceae",
        tags=("tropical",), attainable_yield_t_ha=10.0, harvest_index=0.25, price_usd_per_ton=1200),
    "mangosteen": dict(arch="tropical_tree", name="Mangosteen", name_ar="مانغوستين", sci="Garcinia mangostana", fam="Clusiaceae",
        tags=("tropical",), attainable_yield_t_ha=8.0, harvest_index=0.25, price_usd_per_ton=2500),
    "star_fruit": dict(arch="tropical_tree", name="Star Fruit / Carambola", name_ar="فاكهة النجمة", sci="Averrhoa carambola", fam="Oxalidaceae",
        tags=("tropical",), attainable_yield_t_ha=15.0, harvest_index=0.35, price_usd_per_ton=800),
    "durian": dict(arch="tropical_tree", name="Durian", name_ar="دوريان", sci="Durio zibethinus", fam="Malvaceae",
        tags=("tropical",), attainable_yield_t_ha=10.0, harvest_index=0.20, price_usd_per_ton=3000),
    "longan": dict(arch="tropical_tree", name="Longan", name_ar="لونجان", sci="Dimocarpus longan", fam="Sapindaceae",
        tags=("tropical","subtropical"),
        attainable_yield_t_ha=10.0, harvest_index=0.25, price_usd_per_ton=1500),
    "cocoyam": dict(arch="vegetable", name="Cocoyam", name_ar="كوكويام", sci="Xanthosoma sagittifolium", fam="Araceae",
        tags=("tropical","subsaharan"), gdd_base_temp=15.0, growing_days=240,
        max_root_depth_cm=50, attainable_yield_t_ha=12.0, harvest_index=0.45, price_usd_per_ton=200),
    "african_rice": dict(arch="rice", name="African Rice", name_ar="أرز أفريقي", sci="Oryza glaberrima", fam="Poaceae",
        tags=("subsaharan",), growing_days=130, attainable_yield_t_ha=3.0, price_usd_per_ton=400),
    "locust_bean": dict(arch="tropical_tree", name="Locust Bean / Dawadawa", name_ar="خرنوب أفريقي", sci="Parkia biglobosa", fam="Fabaceae",
        tags=("subsaharan",), water_needs="low",
        attainable_yield_t_ha=2.0, harvest_index=0.15, price_usd_per_ton=1500),
    "marula": dict(arch="tropical_tree", name="Marula", name_ar="مارولا", sci="Sclerocarya birrea", fam="Anacardiaceae",
        tags=("subsaharan",), water_needs="low",
        attainable_yield_t_ha=4.0, harvest_index=0.20, price_usd_per_ton=2000),
    "neem": dict(arch="tropical_tree", name="Neem", name_ar="نيم", sci="Azadirachta indica", fam="Meliaceae",
        tags=("tropical","subsaharan","mena"), water_needs="low",
        attainable_yield_t_ha=5.0, harvest_index=0.15, price_usd_per_ton=500),
    "acacia_gum": dict(arch="perennial", name="Gum Arabic / Acacia", name_ar="صمغ عربي", sci="Senegalia senegal", fam="Fabaceae",
        tags=("mena","subsaharan"), water_needs="low", max_root_depth_cm=300,
        attainable_yield_t_ha=0.3, harvest_index=0.05, price_usd_per_ton=5000),
    "sorrel": dict(arch="vegetable", name="Sorrel", name_ar="حماض", sci="Rumex acetosa", fam="Polygonaceae",
        tags=("mediterranean","temperate"), growing_days=60,
        max_root_depth_cm=30, attainable_yield_t_ha=15.0, harvest_index=0.80, price_usd_per_ton=350),
    "purslane": dict(arch="vegetable", name="Purslane", name_ar="رجلة", sci="Portulaca oleracea", fam="Portulacaceae",
        tags=("mediterranean","mena","temperate"), growing_days=45,
        water_needs="low", max_root_depth_cm=20, attainable_yield_t_ha=12.0,
        harvest_index=0.80, price_usd_per_ton=400),
    "green_bean": dict(arch="legume", name="Green Bean / Snap Bean", name_ar="فاصوليا خضراء", sci="Phaseolus vulgaris", fam="Fabaceae",
        tags=("mediterranean","temperate","subtropical","tropical"), growing_days=65,
        attainable_yield_t_ha=12.0, harvest_index=0.55, price_usd_per_ton=350),
    "luffa": dict(arch="vegetable", name="Luffa / Sponge Gourd", name_ar="لوف", sci="Luffa aegyptiaca", fam="Cucurbitaceae",
        tags=("tropical","mena"), growing_days=120,
        max_root_depth_cm=60, attainable_yield_t_ha=15.0, harvest_index=0.40, price_usd_per_ton=250),
    "chayote": dict(arch="vegetable", name="Chayote", name_ar="شايوتي", sci="Sechium edule", fam="Cucurbitaceae",
        tags=("tropical","subtropical"), growing_days=150,
        max_root_depth_cm=80, attainable_yield_t_ha=30.0, harvest_index=0.55, price_usd_per_ton=200),
    "brussels_sprouts": dict(arch="vegetable", name="Brussels Sprouts", name_ar="كرنب بروكسل", sci="Brassica oleracea var. gemmifera", fam="Brassicaceae",
        tags=("temperate",), gdd_base_temp=5.0, growing_days=150,
        max_root_depth_cm=50, attainable_yield_t_ha=12.0, harvest_index=0.35, price_usd_per_ton=500),
    "vanilla": dict(arch="tropical_tree", name="Vanilla", name_ar="فانيلا", sci="Vanilla planifolia", fam="Orchidaceae",
        tags=("tropical",), max_root_depth_cm=30,
        attainable_yield_t_ha=0.5, harvest_index=0.10, price_usd_per_ton=50000),
    "cardamom": dict(arch="tropical_tree", name="Cardamom", name_ar="هيل", sci="Elettaria cardamomum", fam="Zingiberaceae",
        tags=("tropical",), max_root_depth_cm=50,
        attainable_yield_t_ha=0.3, harvest_index=0.10, price_usd_per_ton=25000),
    "clove": dict(arch="tropical_tree", name="Clove", name_ar="قرنفل", sci="Syzygium aromaticum", fam="Myrtaceae",
        tags=("tropical",), attainable_yield_t_ha=1.0, harvest_index=0.10, price_usd_per_ton=8000),
    "nutmeg": dict(arch="tropical_tree", name="Nutmeg", name_ar="جوزة الطيب", sci="Myristica fragrans", fam="Myristicaceae",
        tags=("tropical",), attainable_yield_t_ha=2.0, harvest_index=0.10, price_usd_per_ton=12000),
    "cinnamon": dict(arch="tropical_tree", name="Cinnamon", name_ar="قرفة", sci="Cinnamomum verum", fam="Lauraceae",
        tags=("tropical",), attainable_yield_t_ha=1.5, harvest_index=0.10, price_usd_per_ton=4000),
    "kiwi": dict(arch="perennial", name="Kiwi", name_ar="كيوي", sci="Actinidia deliciosa", fam="Actinidiaceae",
        tags=("temperate","subtropical","mediterranean"),
        gdd_base_temp=7.0, kc_mid=0.95, max_root_depth_cm=80,
        attainable_yield_t_ha=25.0, harvest_index=0.40, price_usd_per_ton=1000),
    "cranberry": dict(arch="perennial", name="Cranberry", name_ar="توت بري", sci="Vaccinium macrocarpon", fam="Ericaceae",
        tags=("temperate",), max_root_depth_cm=20,
        attainable_yield_t_ha=15.0, harvest_index=0.45, price_usd_per_ton=2000),
    "lime": dict(arch="perennial", name="Lime", name_ar="ليم", sci="Citrus aurantiifolia", fam="Rutaceae",
        tags=("tropical","subtropical","mena"),
        gdd_base_temp=13.0, max_root_depth_cm=130,
        kc_init=0.70, kc_mid=0.65, kc_end=0.65,
        attainable_yield_t_ha=25.0, harvest_index=0.28, price_usd_per_ton=400),
}


# =============================================================================
# v4.0 species-level overrides: salinity, BNF, N dilution, RUE, C:N, baselines
#
# Merged into _RAW entries. Architecture defaults apply for unlisted crops.
# Sources: FAO-29, Herridge 2008, Peoples 2009, Lemaire 1997, NRCS
# =============================================================================

_V4_OVERRIDES: Dict[str, dict] = {
    # ─── CEREALS ────────────────────────────────────────────────────────────
    "wheat":        dict(ec_threshold_ds_m=6.0, ec_slope_pct=7.1, salt_tolerance_class="mod_tolerant",
                         n_dilution_a=5.35, n_dilution_b=0.442, rue_g_mj=2.8, residue_cn_ratio=80.0,
                         ndvi_baselines={"initial":(0.25,0.05),"vegetative":(0.70,0.08),"reproductive":(0.80,0.05),"maturity":(0.50,0.12),"senescence":(0.25,0.08)}),
    "durum_wheat":  dict(ec_threshold_ds_m=5.9, ec_slope_pct=7.1, salt_tolerance_class="mod_tolerant",
                         rue_g_mj=2.7, residue_cn_ratio=75.0),
    "barley":       dict(ec_threshold_ds_m=8.0, ec_slope_pct=5.0, salt_tolerance_class="tolerant",
                         rue_g_mj=2.6, residue_cn_ratio=80.0),
    "oat":          dict(ec_threshold_ds_m=5.0, ec_slope_pct=7.1, residue_cn_ratio=70.0, rue_g_mj=2.5),
    "rye":          dict(ec_threshold_ds_m=11.4, ec_slope_pct=2.5, salt_tolerance_class="tolerant",
                         residue_cn_ratio=75.0, rue_g_mj=2.5),
    "triticale":    dict(ec_threshold_ds_m=6.0, ec_slope_pct=7.1, residue_cn_ratio=70.0),
    "sorghum":      dict(ec_threshold_ds_m=6.8, ec_slope_pct=16.0, salt_tolerance_class="mod_tolerant",
                         photosynthetic_pathway="C4", n_dilution_a=3.40, n_dilution_b=0.370, rue_g_mj=3.5,
                         residue_cn_ratio=55.0,
                         ndvi_baselines={"initial":(0.18,0.05),"vegetative":(0.72,0.08),"reproductive":(0.82,0.05),"maturity":(0.55,0.10),"senescence":(0.28,0.08)}),
    "pearl_millet":  dict(ec_threshold_ds_m=5.0, ec_slope_pct=7.1,
                          photosynthetic_pathway="C4", n_dilution_a=3.40, n_dilution_b=0.370, rue_g_mj=3.3,
                          residue_cn_ratio=50.0),
    "finger_millet": dict(ec_threshold_ds_m=4.0, ec_slope_pct=8.0,
                          photosynthetic_pathway="C4", n_dilution_a=3.40, n_dilution_b=0.370, rue_g_mj=3.0),
    "teff":          dict(ec_threshold_ds_m=4.0, ec_slope_pct=8.0,
                          photosynthetic_pathway="C4", n_dilution_a=3.40, n_dilution_b=0.370, rue_g_mj=2.8,
                          residue_cn_ratio=40.0),
    "quinoa":       dict(ec_threshold_ds_m=8.0, ec_slope_pct=4.0, salt_tolerance_class="tolerant",
                         n_dilution_a=4.80, n_dilution_b=0.400, rue_g_mj=2.2, residue_cn_ratio=35.0),
    "amaranth":     dict(ec_threshold_ds_m=3.0, ec_slope_pct=10.0,
                         photosynthetic_pathway="C4", n_dilution_a=3.40, n_dilution_b=0.370, rue_g_mj=3.0),
    # ─── MAIZE ──────────────────────────────────────────────────────────────
    "corn":         dict(ec_threshold_ds_m=1.7, ec_slope_pct=12.0, residue_cn_ratio=55.0,
                         ndvi_baselines={"initial":(0.20,0.05),"vegetative":(0.72,0.08),"reproductive":(0.85,0.05),"maturity":(0.60,0.12),"senescence":(0.30,0.10)}),
    "maize":        dict(ec_threshold_ds_m=1.7, ec_slope_pct=12.0, residue_cn_ratio=55.0),
    "sweet_corn":   dict(ec_threshold_ds_m=1.7, ec_slope_pct=12.0, residue_cn_ratio=45.0),
    # ─── LEGUMES ────────────────────────────────────────────────────────────
    "soybean":      dict(ec_threshold_ds_m=5.0, ec_slope_pct=20.0, salt_tolerance_class="mod_tolerant",
                         bnf_ndfa_range=(0.50,0.85), bnf_typical_kg_ha=150.0,
                         n_dilution_a=5.50, n_dilution_b=0.300, rue_g_mj=2.0, residue_cn_ratio=25.0,
                         ndvi_baselines={"initial":(0.20,0.05),"vegetative":(0.68,0.08),"reproductive":(0.78,0.06),"maturity":(0.48,0.10),"senescence":(0.22,0.08)}),
    "chickpea":     dict(ec_threshold_ds_m=1.5, ec_slope_pct=14.0,
                         bnf_ndfa_range=(0.40,0.80), bnf_typical_kg_ha=80.0, residue_cn_ratio=18.0),
    "lentil":       dict(ec_threshold_ds_m=1.5, ec_slope_pct=14.0,
                         bnf_ndfa_range=(0.40,0.75), bnf_typical_kg_ha=60.0, residue_cn_ratio=16.0),
    "fava_bean":    dict(ec_threshold_ds_m=1.6, ec_slope_pct=19.0,
                         bnf_ndfa_range=(0.60,0.90), bnf_typical_kg_ha=175.0, residue_cn_ratio=12.0),
    "pea":          dict(ec_threshold_ds_m=1.5, ec_slope_pct=14.0,
                         bnf_ndfa_range=(0.45,0.80), bnf_typical_kg_ha=90.0, residue_cn_ratio=16.0),
    "cowpea":       dict(ec_threshold_ds_m=4.9, ec_slope_pct=12.0, salt_tolerance_class="mod_tolerant",
                         bnf_ndfa_range=(0.40,0.75), bnf_typical_kg_ha=70.0, residue_cn_ratio=15.0),
    "pigeon_pea":   dict(ec_threshold_ds_m=2.0, ec_slope_pct=12.0,
                         bnf_ndfa_range=(0.40,0.80), bnf_typical_kg_ha=100.0, residue_cn_ratio=18.0),
    "groundnut":    dict(ec_threshold_ds_m=3.2, ec_slope_pct=29.0,
                         bnf_ndfa_range=(0.30,0.70), bnf_typical_kg_ha=100.0, residue_cn_ratio=20.0),
    "common_bean":  dict(ec_threshold_ds_m=1.0, ec_slope_pct=19.0, salt_tolerance_class="sensitive",
                         bnf_ndfa_range=(0.30,0.65), bnf_typical_kg_ha=50.0, residue_cn_ratio=18.0),
    "mung_bean":    dict(ec_threshold_ds_m=1.8, ec_slope_pct=14.0,
                         bnf_ndfa_range=(0.40,0.70), bnf_typical_kg_ha=50.0, residue_cn_ratio=15.0),
    "lupin":        dict(ec_threshold_ds_m=1.5, ec_slope_pct=14.0,
                         bnf_ndfa_range=(0.60,0.90), bnf_typical_kg_ha=150.0, residue_cn_ratio=14.0),
    "alfalfa":      dict(ec_threshold_ds_m=2.0, ec_slope_pct=7.3, salt_tolerance_class="mod_sensitive",
                         bnf_ndfa_range=(0.55,0.90), bnf_typical_kg_ha=200.0, residue_cn_ratio=12.0),
    "clover":       dict(bnf_ndfa_range=(0.60,0.90), bnf_typical_kg_ha=180.0, residue_cn_ratio=13.0),
    "vetch":        dict(bnf_ndfa_range=(0.50,0.85), bnf_typical_kg_ha=120.0, residue_cn_ratio=14.0),
    # ─── VEGETABLES ─────────────────────────────────────────────────────────
    "tomato":       dict(ec_threshold_ds_m=2.5, ec_slope_pct=9.9,
                         n_dilution_a=4.50, n_dilution_b=0.400, rue_g_mj=2.2, residue_cn_ratio=22.0,
                         ndvi_baselines={"initial":(0.20,0.06),"vegetative":(0.70,0.08),"reproductive":(0.78,0.06),"maturity":(0.55,0.10),"senescence":(0.25,0.08)}),
    "pepper":       dict(ec_threshold_ds_m=1.5, ec_slope_pct=14.0, salt_tolerance_class="sensitive",
                         n_dilution_a=4.50, n_dilution_b=0.400, rue_g_mj=2.0),
    "eggplant":     dict(ec_threshold_ds_m=1.1, ec_slope_pct=6.9, salt_tolerance_class="sensitive"),
    "potato":       dict(ec_threshold_ds_m=1.7, ec_slope_pct=12.0, salt_tolerance_class="sensitive",
                         n_dilution_a=5.21, n_dilution_b=0.560, rue_g_mj=2.5, residue_cn_ratio=25.0),
    "onion":        dict(ec_threshold_ds_m=1.2, ec_slope_pct=16.0, salt_tolerance_class="sensitive"),
    "carrot":       dict(ec_threshold_ds_m=1.0, ec_slope_pct=14.0, salt_tolerance_class="sensitive"),
    "lettuce":      dict(ec_threshold_ds_m=1.3, ec_slope_pct=13.0, salt_tolerance_class="sensitive"),
    "cucumber":     dict(ec_threshold_ds_m=2.5, ec_slope_pct=13.0),
    "melon":        dict(ec_threshold_ds_m=2.2, ec_slope_pct=7.3),
    "watermelon":   dict(ec_threshold_ds_m=2.2, ec_slope_pct=7.3),
    "strawberry":   dict(ec_threshold_ds_m=1.0, ec_slope_pct=33.0, salt_tolerance_class="sensitive"),
    "spinach":      dict(ec_threshold_ds_m=2.0, ec_slope_pct=7.6),
    "cabbage":      dict(ec_threshold_ds_m=1.8, ec_slope_pct=9.7),
    "cauliflower":  dict(ec_threshold_ds_m=1.8, ec_slope_pct=6.2),
    "broccoli":     dict(ec_threshold_ds_m=2.8, ec_slope_pct=9.2),
    "garlic":       dict(ec_threshold_ds_m=1.7, ec_slope_pct=12.0),
    "asparagus":    dict(ec_threshold_ds_m=4.1, ec_slope_pct=2.0, salt_tolerance_class="tolerant"),
    "sweet_potato": dict(ec_threshold_ds_m=1.5, ec_slope_pct=11.0, salt_tolerance_class="sensitive"),
    "okra":         dict(ec_threshold_ds_m=1.2, ec_slope_pct=12.0, salt_tolerance_class="sensitive"),
    "zucchini":     dict(ec_threshold_ds_m=2.7, ec_slope_pct=10.0),
    "pumpkin":      dict(ec_threshold_ds_m=2.5, ec_slope_pct=10.0),
    "turnip":       dict(ec_threshold_ds_m=0.9, ec_slope_pct=9.0, salt_tolerance_class="sensitive"),
    "beetroot":     dict(ec_threshold_ds_m=4.0, ec_slope_pct=9.0, salt_tolerance_class="mod_tolerant"),
    "radish":       dict(ec_threshold_ds_m=1.2, ec_slope_pct=13.0, salt_tolerance_class="sensitive"),
    "celery":       dict(ec_threshold_ds_m=1.8, ec_slope_pct=6.2),
    # ─── PERENNIALS ─────────────────────────────────────────────────────────
    "olive":        dict(ec_threshold_ds_m=2.7, ec_slope_pct=10.0,
                         n_dilution_a=3.00, n_dilution_b=0.250, rue_g_mj=1.5, residue_cn_ratio=35.0,
                         ndvi_baselines={"initial":(0.30,0.05),"vegetative":(0.55,0.06),"reproductive":(0.60,0.05),"maturity":(0.55,0.06),"senescence":(0.45,0.06)}),
    "grape":        dict(ec_threshold_ds_m=1.5, ec_slope_pct=9.6, salt_tolerance_class="sensitive",
                         n_dilution_a=3.50, n_dilution_b=0.300, rue_g_mj=1.8, residue_cn_ratio=30.0),
    "apple":        dict(ec_threshold_ds_m=1.7, ec_slope_pct=16.0, salt_tolerance_class="sensitive",
                         n_dilution_a=3.50, n_dilution_b=0.300, rue_g_mj=1.6),
    "almond":       dict(ec_threshold_ds_m=1.5, ec_slope_pct=19.0, salt_tolerance_class="sensitive",
                         n_dilution_a=3.00, n_dilution_b=0.250, rue_g_mj=1.3),
    "fig":          dict(ec_threshold_ds_m=2.7, ec_slope_pct=10.0),
    "pomegranate":  dict(ec_threshold_ds_m=3.0, ec_slope_pct=10.0),
    "pistachio":    dict(ec_threshold_ds_m=5.0, ec_slope_pct=5.0, salt_tolerance_class="mod_tolerant"),
    "walnut":       dict(ec_threshold_ds_m=1.5, ec_slope_pct=16.0, salt_tolerance_class="sensitive"),
    "pecan":        dict(ec_threshold_ds_m=1.5, ec_slope_pct=16.0, salt_tolerance_class="sensitive"),
    "cherry":       dict(ec_threshold_ds_m=1.7, ec_slope_pct=16.0, salt_tolerance_class="sensitive"),
    "peach":        dict(ec_threshold_ds_m=1.7, ec_slope_pct=21.0, salt_tolerance_class="sensitive"),
    "apricot":      dict(ec_threshold_ds_m=1.6, ec_slope_pct=24.0, salt_tolerance_class="sensitive"),
    "plum":         dict(ec_threshold_ds_m=1.5, ec_slope_pct=18.0, salt_tolerance_class="sensitive"),
    "pear":         dict(ec_threshold_ds_m=1.7, ec_slope_pct=16.0, salt_tolerance_class="sensitive"),
    # ─── CITRUS ─────────────────────────────────────────────────────────────
    "orange":       dict(ec_threshold_ds_m=1.7, ec_slope_pct=16.0, salt_tolerance_class="sensitive",
                         n_dilution_a=3.20, n_dilution_b=0.280, rue_g_mj=1.5),
    "lemon":        dict(ec_threshold_ds_m=1.7, ec_slope_pct=16.0, salt_tolerance_class="sensitive"),
    "mandarin":     dict(ec_threshold_ds_m=1.7, ec_slope_pct=16.0, salt_tolerance_class="sensitive"),
    "clementine":   dict(ec_threshold_ds_m=1.7, ec_slope_pct=16.0, salt_tolerance_class="sensitive"),
    "grapefruit":   dict(ec_threshold_ds_m=1.8, ec_slope_pct=16.0, salt_tolerance_class="sensitive"),
    # ─── TROPICAL ───────────────────────────────────────────────────────────
    "date_palm":    dict(ec_threshold_ds_m=4.0, ec_slope_pct=3.6, salt_tolerance_class="mod_tolerant"),
    "banana":       dict(ec_threshold_ds_m=1.1, ec_slope_pct=12.0, salt_tolerance_class="sensitive"),
    "coffee":       dict(ec_threshold_ds_m=1.5, ec_slope_pct=12.0, salt_tolerance_class="sensitive"),
    "cocoa":        dict(ec_threshold_ds_m=1.0, ec_slope_pct=15.0, salt_tolerance_class="sensitive"),
    "coconut":      dict(ec_threshold_ds_m=3.0, ec_slope_pct=8.0, salt_tolerance_class="mod_sensitive"),
    "mango":        dict(ec_threshold_ds_m=1.5, ec_slope_pct=12.0, salt_tolerance_class="sensitive"),
    "avocado":      dict(ec_threshold_ds_m=1.3, ec_slope_pct=15.0, salt_tolerance_class="sensitive"),
    "papaya":       dict(ec_threshold_ds_m=1.5, ec_slope_pct=12.0, salt_tolerance_class="sensitive"),
    "pineapple":    dict(ec_threshold_ds_m=3.0, ec_slope_pct=8.0, salt_tolerance_class="mod_sensitive"),
    # ─── OIL / INDUSTRIAL ───────────────────────────────────────────────────
    "sunflower":    dict(ec_threshold_ds_m=2.0, ec_slope_pct=5.0,
                         n_dilution_a=4.53, n_dilution_b=0.420, rue_g_mj=2.2, residue_cn_ratio=40.0),
    "canola":       dict(ec_threshold_ds_m=2.5, ec_slope_pct=8.0,
                         n_dilution_a=4.48, n_dilution_b=0.250, rue_g_mj=2.3, residue_cn_ratio=45.0),
    "sugarcane":    dict(ec_threshold_ds_m=1.7, ec_slope_pct=5.9,
                         photosynthetic_pathway="C4", n_dilution_a=3.20, n_dilution_b=0.350, rue_g_mj=3.5,
                         bnf_type="associative", bnf_ndfa_range=(0.10,0.30), bnf_typical_kg_ha=40.0,
                         residue_cn_ratio=80.0),
    "sugar_beet":   dict(ec_threshold_ds_m=7.0, ec_slope_pct=5.9, salt_tolerance_class="tolerant",
                         residue_cn_ratio=35.0),
}

# Merge v4.0 overrides into _RAW
for _code, _overrides in _V4_OVERRIDES.items():
    if _code in _RAW:
        _RAW[_code].update(_overrides)


# =============================================================================
# Build the CROP_REGISTRY
# =============================================================================

CROP_REGISTRY: Dict[str, CropSpec] = {}

for code, raw in _RAW.items():
    arch_key = raw.get("arch", "cereal")
    defaults = _ARCH_DEFAULTS[arch_key]

    # Merge: defaults ← raw overrides
    # Merge tissue norms: architecture default ← crop-level overrides
    merged_tissue = dict(defaults["tissue_norms"])  # Copy arch defaults
    raw_tissue = raw.get("tissue_norms")
    if raw_tissue:
        for nut_key, stages in raw_tissue.items():
            merged_tissue[nut_key] = stages  # Crop override replaces per-nutrient

    # Merge DRIS norms
    merged_dris = dict(defaults["dris_norms"])
    raw_dris = raw.get("dris_norms")
    if raw_dris:
        merged_dris.update(raw_dris)

    CROP_REGISTRY[code] = CropSpec(
        code=code,
        name=raw.get("name", code.replace("_", " ").title()),
        name_ar=raw.get("name_ar", ""),
        scientific_name=raw.get("sci", ""),
        family=raw.get("fam", ""),
        architecture=arch_key,
        region_tags=raw.get("tags", ()),
        gdd_base_temp=raw.get("gdd_base_temp", defaults["gdd_base_temp"]),
        growing_days=raw.get("growing_days", defaults["growing_days"]),
        optimal_temp_min=raw.get("optimal_temp_min", defaults["optimal_temp_min"]),
        optimal_temp_max=raw.get("optimal_temp_max", defaults["optimal_temp_max"]),
        water_needs=raw.get("water_needs", defaults["water_needs"]),
        max_root_depth_cm=raw.get("max_root_depth_cm", defaults["max_root_depth_cm"]),
        kc_init=raw.get("kc_init", defaults["kc_init"]),
        kc_mid=raw.get("kc_mid", defaults["kc_mid"]),
        kc_end=raw.get("kc_end", defaults["kc_end"]),
        kcb_initial=raw.get("kcb_initial", defaults["kcb_initial"]),
        kcb_vegetative=raw.get("kcb_vegetative", defaults["kcb_vegetative"]),
        kcb_reproductive=raw.get("kcb_reproductive", defaults["kcb_reproductive"]),
        kcb_maturity=raw.get("kcb_maturity", defaults["kcb_maturity"]),
        kcb_senescence=raw.get("kcb_senescence", defaults["kcb_senescence"]),
        water_stress_sensitivity=raw.get("water_stress_sensitivity", defaults["water_stress_sensitivity"]),
        removal_n=raw.get("removal_n", defaults["removal_n"]),
        removal_p=raw.get("removal_p", defaults["removal_p"]),
        removal_k=raw.get("removal_k", defaults["removal_k"]),
        attainable_yield_t_ha=raw.get("attainable_yield_t_ha", defaults["attainable_yield_t_ha"]),
        n_ceiling_kg_ha=raw.get("n_ceiling_kg_ha", defaults["n_ceiling_kg_ha"]),
        response_a_max=raw.get("response_a_max", defaults["response_a_max"]),
        response_c_rate=raw.get("response_c_rate", defaults["response_c_rate"]),
        response_n_soil_default=raw.get("response_n_soil_default", defaults["response_n_soil_default"]),
        tissue_norms=merged_tissue,
        dris_norms=merged_dris,
        nue_ae_range=raw.get("nue_ae_range", defaults["nue_ae_range"]),
        nue_pfp_range=raw.get("nue_pfp_range", defaults["nue_pfp_range"]),
        nue_re_range=raw.get("nue_re_range", defaults["nue_re_range"]),
        grain_n_pct=raw.get("grain_n_pct", defaults["grain_n_pct"]),
        harvest_index=raw.get("harvest_index", defaults["harvest_index"]),
        price_usd_per_ton=raw.get("price_usd_per_ton", defaults["price_usd_per_ton"]),
        # v4.0 new fields
        ec_threshold_ds_m=raw.get("ec_threshold_ds_m", defaults["ec_threshold_ds_m"]),
        ec_slope_pct=raw.get("ec_slope_pct", defaults["ec_slope_pct"]),
        salt_tolerance_class=raw.get("salt_tolerance_class", defaults["salt_tolerance_class"]),
        is_legume=raw.get("is_legume", defaults["is_legume"]),
        bnf_ndfa_range=raw.get("bnf_ndfa_range", defaults["bnf_ndfa_range"]),
        bnf_typical_kg_ha=raw.get("bnf_typical_kg_ha", defaults["bnf_typical_kg_ha"]),
        bnf_type=raw.get("bnf_type", defaults["bnf_type"]),
        residue_cn_ratio=raw.get("residue_cn_ratio", defaults["residue_cn_ratio"]),
        photosynthetic_pathway=raw.get("photosynthetic_pathway", defaults["photosynthetic_pathway"]),
        n_dilution_a=raw.get("n_dilution_a", defaults["n_dilution_a"]),
        n_dilution_b=raw.get("n_dilution_b", defaults["n_dilution_b"]),
        rue_g_mj=raw.get("rue_g_mj", defaults["rue_g_mj"]),
        ndvi_baselines=raw.get("ndvi_baselines", defaults["ndvi_baselines"]),
    )


# =============================================================================
# Alias resolution
# =============================================================================

_ALIASES: Dict[str, str] = {
    # Common alternative names → canonical codes
    "maïs": "corn", "mais": "corn", "maize": "corn",
    "soy": "soybean",
    "faba": "fava_bean", "faba_bean": "fava_bean", "bean": "fava_bean", "broad_bean": "fava_bean",
    "paddy": "rice",
    "vine": "grape",
    "peanut": "groundnut",
    "rapeseed": "canola",
    "date": "date_palm",
    "millet": "pearl_millet",
    "lupine": "lupin",
}


# =============================================================================
# Public API
# =============================================================================

_DEFAULT = CROP_REGISTRY["wheat"]  # Safe fallback


def resolve_crop_code(name: str) -> str:
    """Resolve a crop name/alias to its canonical code.

    Supports: exact match, alias, underscore/space normalization, substring.
    Returns ``"unknown"`` if no match is found — never silently defaults
    to wheat.
    """
    if not name:
        return "unknown"
    key = name.strip().lower().replace(" ", "_").replace("-", "_")

    # Direct match
    if key in CROP_REGISTRY:
        return key

    # Alias
    if key in _ALIASES:
        return _ALIASES[key]

    # Substring match (e.g. "durum_wheat" contains "wheat")
    for code in CROP_REGISTRY:
        if code in key:
            return code

    return "unknown"


def get_crop(name: str) -> CropSpec:
    """Get a full CropSpec by name/alias. Never returns None.

    If the name cannot be resolved, returns the wheat default spec
    for backward compatibility — but callers should check
    :func:`resolve_crop_code` first to avoid silently using wheat.
    """
    code = resolve_crop_code(name)
    if code == "unknown":
        return _DEFAULT  # backward compat: still returns wheat spec
    return CROP_REGISTRY.get(code, _DEFAULT)


def get_crop_with_provenance(name: str) -> tuple:
    """Resolve a crop name and return (CropSpec, code, used_default).

    Returns a 3-tuple so callers can detect when the default was used::

        spec, code, used_default = get_crop_with_provenance(user_input)
        if used_default:
            # The input was unrecognized — spec is wheat fallback
            ...
    """
    code = resolve_crop_code(name)
    if code == "unknown":
        return (_DEFAULT, "unknown", True)
    spec = CROP_REGISTRY.get(code, _DEFAULT)
    return (spec, code, False)


def get_architecture_class(name: str) -> str:
    """Return the architecture class for a crop name."""
    return get_crop(name).architecture


def list_crop_codes() -> List[str]:
    """Return all registered crop codes."""
    return sorted(CROP_REGISTRY.keys())


def list_crops(region: str = None) -> List[CropSpec]:
    """List all crops, optionally filtered by region tag."""
    if region:
        tag = region.lower()
        return [c for c in CROP_REGISTRY.values() if tag in c.region_tags]
    return list(CROP_REGISTRY.values())
