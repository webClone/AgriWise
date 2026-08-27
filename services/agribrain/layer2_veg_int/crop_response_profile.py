"""
Layer 2: Crop Response Profile, Biological Progress, and Hierarchical Parameter System
=======================================================================================
Provides a crop-conditioned biological state-estimation foundation for Layer 2.

Core Components:
  - ParameterEstimate: Uncertainty-aware parameter with provenance, authority, and adaptability.
  - CropStageGraph: Detailed biological stage topology mapped to CanonicalAgriBrainStage.
  - CropResponseProfile: Unified scientific profile consumed by phenology, canopy, productivity,
    anomaly, and stress engines.
  - CropParameterResolver: Hierarchical partial pooling (Cultivar → Species → Architecture → Global).
  - CausalBiologicalProgress: Non-leaking causal biological progress coordinate τ ∈ [0, 1].
  - CropContextConsistency: Normalized likelihood ratio watchdog for detecting crop-context mismatch.

References:
  - Wardlow & Egbert (2008), Bolton & Friedl (2013), Potter et al. (1993 CASA)
  - Sánchez et al. (2014), Chuine (2000), Steduto et al. (2009 AquaCrop)
"""

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

from layer2_veg_int.schema import PhenologyStage


# =============================================================================
# Provenance, Authority, and Adaptability Enums
# =============================================================================

class ParameterSource(str, Enum):
    LOCAL_MEASUREMENT = "LOCAL_MEASUREMENT"
    LITERATURE_SPECIFIC = "LITERATURE_SPECIFIC"
    LITERATURE_CROP = "LITERATURE_CROP"
    ARCHITECTURE_PRIOR = "ARCHITECTURE_PRIOR"
    GLOBAL_PRIOR = "GLOBAL_PRIOR"


class AuthorityLevel(str, Enum):
    CALIBRATED = "CALIBRATED"
    TRANSFERRED = "TRANSFERRED"
    PRIOR_ONLY = "PRIOR_ONLY"


class AdaptabilityClass(str, Enum):
    FIXED_BIOLOGY = "FIXED_BIOLOGY"           # e.g., C3/C4, stage topology
    CALIBRATABLE_TRAIT = "CALIBRATABLE_TRAIT" # e.g., Tb, To, LUE prior
    SEASON_ADAPTIVE = "SEASON_ADAPTIVE"       # e.g., Sowing date, peak timing/amplitude
    DYNAMIC_STATE = "DYNAMIC_STATE"           # e.g., Stage posterior, LAI, anomaly


class TemporalMorphology(str, Enum):
    SINGLE_CYCLE_DOUBLE_LOGISTIC = "single_cycle_double_logistic"
    MULTI_CYCLE_REGROWTH = "multi_cycle_regrowth"       # e.g., Alfalfa
    EVERGREEN_SEASONAL = "evergreen_seasonal"           # e.g., Olive, citrus
    DECIDUOUS_PERENNIAL = "deciduous_perennial"         # e.g., Fruit orchards
    PROTECTED_CROP = "protected_crop"                   # e.g., Greenhouse tomato
    INDETERMINATE_FRUITING = "indeterminate_fruiting"   # e.g., Pepper, eggplant


# =============================================================================
# Parameter Estimate with Uncertainty & Lineage
# =============================================================================

@dataclass
class ParameterEstimate:
    """Probabilistic parameter estimate with provenance and governance metadata."""
    mean: float
    variance: float
    source_tier: ParameterSource
    source_id: str
    crop: str
    cultivar: Optional[str] = None
    region: Optional[str] = None
    stage: Optional[str] = None
    validity_domain: Tuple[float, float] = (0.0, 1.0)
    calibrated_on: Optional[str] = None
    update_class: AdaptabilityClass = AdaptabilityClass.CALIBRATABLE_TRAIT
    allowable_range: Tuple[float, float] = (0.0, 100.0)

    @property
    def std(self) -> float:
        return math.sqrt(max(1e-8, self.variance))


# =============================================================================
# Crop Stage Graph & Ontologies
# =============================================================================

@dataclass
class CropStageNode:
    stage_id: str
    canonical_stage: PhenologyStage
    expected_gdd_fraction: float  # [0, 1] relative to cycle
    min_duration_days: int
    expected_duration_days: int
    description: str


class CropStageGraph:
    """Crop-specific biological stage graph mapped to canonical Layer 2 stages."""

    def __init__(self, crop_code: str, nodes: List[CropStageNode]):
        self.crop_code = crop_code
        self.nodes = nodes
        self._node_map = {n.stage_id: n for n in nodes}

    @classmethod
    def create_for_crop(cls, crop_code: str, architecture: str) -> "CropStageGraph":
        code = (crop_code or "").lower()
        if "wheat" in code or "barley" in code or "oat" in code or "rye" in code:
            nodes = [
                CropStageNode("EMERGENCE", PhenologyStage.EMERGENCE, 0.08, 5, 12, "Germination & seedling emergence"),
                CropStageNode("TILLERING", PhenologyStage.VEGETATIVE, 0.22, 10, 25, "Tillering & crown root development"),
                CropStageNode("STEM_ELONGATION", PhenologyStage.VEGETATIVE, 0.40, 10, 20, "Jointing & rapid canopy growth"),
                CropStageNode("BOOTING_HEADING", PhenologyStage.REPRODUCTIVE, 0.55, 7, 14, "Flag leaf emergence & ear emergence"),
                CropStageNode("ANTHESIS", PhenologyStage.REPRODUCTIVE, 0.65, 5, 10, "Flowering & pollination"),
                CropStageNode("GRAIN_FILLING", PhenologyStage.REPRODUCTIVE, 0.82, 12, 25, "Milk, dough & starch accumulation"),
                CropStageNode("MATURITY", PhenologyStage.SENESCENCE, 0.95, 7, 15, "Ripening & canopy dry-down"),
                CropStageNode("HARVESTED", PhenologyStage.HARVESTED, 1.00, 3, 10, "Stubble & post-harvest residue"),
            ]
        elif "corn" in code or "maize" in code or "sorghum" in code:
            nodes = [
                CropStageNode("VE_EMERGENCE", PhenologyStage.EMERGENCE, 0.06, 5, 10, "Coleoptile emergence"),
                CropStageNode("V_VEGETATIVE", PhenologyStage.VEGETATIVE, 0.38, 15, 35, "V1-Vn whorl leaf expansion"),
                CropStageNode("VT_TASSELING", PhenologyStage.REPRODUCTIVE, 0.52, 5, 10, "Tassel emergence"),
                CropStageNode("R1_SILKING", PhenologyStage.REPRODUCTIVE, 0.60, 5, 8, "Silk emergence & pollination"),
                CropStageNode("R2_R5_GRAIN_FILL", PhenologyStage.REPRODUCTIVE, 0.85, 15, 30, "Blister, milk, dough & dent stages"),
                CropStageNode("R6_MATURITY", PhenologyStage.SENESCENCE, 0.96, 7, 14, "Black layer physiological maturity"),
                CropStageNode("HARVESTED", PhenologyStage.HARVESTED, 1.00, 3, 10, "Harvested"),
            ]
        elif "potato" in code:
            nodes = [
                CropStageNode("EMERGENCE", PhenologyStage.EMERGENCE, 0.10, 7, 15, "Sprout emergence"),
                CropStageNode("CANOPY_EXPANSION", PhenologyStage.VEGETATIVE, 0.35, 12, 25, "Vegetative shoot expansion"),
                CropStageNode("TUBER_INITIATION", PhenologyStage.REPRODUCTIVE, 0.50, 7, 14, "Hooking stolons & tuber initiation"),
                CropStageNode("TUBER_BULKING", PhenologyStage.REPRODUCTIVE, 0.82, 20, 45, "Rapid tuber growth & starch deposition"),
                CropStageNode("MATURATION", PhenologyStage.SENESCENCE, 0.95, 10, 20, "Canopy yellowing & skin setting"),
                CropStageNode("HARVESTED", PhenologyStage.HARVESTED, 1.00, 3, 10, "Harvested"),
            ]
        elif "olive" in code or "citrus" in code or architecture in ("perennial", "tropical_tree"):
            nodes = [
                CropStageNode("DORMANCY_QUIESCENCE", PhenologyStage.DORMANCY, 0.10, 14, 60, "Winter rest / bud dormancy"),
                CropStageNode("BUDBREAK_SHOOT", PhenologyStage.EMERGENCE, 0.30, 10, 25, "Bud burst & new shoot flush"),
                CropStageNode("FLOWERING", PhenologyStage.REPRODUCTIVE, 0.48, 7, 18, "Inflorescence & bloom"),
                CropStageNode("FRUIT_SET", PhenologyStage.REPRODUCTIVE, 0.65, 14, 40, "Fruit set & initial cell division"),
                CropStageNode("FRUIT_GROWTH_OIL", PhenologyStage.REPRODUCTIVE, 0.90, 30, 90, "Fruit expansion & lipogenesis"),
                CropStageNode("POST_HARVEST", PhenologyStage.SENESCENCE, 1.00, 14, 45, "Post-harvest rest"),
            ]
        elif "alfalfa" in code or "forage" in code or "clover" in code:
            nodes = [
                CropStageNode("EARLY_REGROWTH", PhenologyStage.EMERGENCE, 0.20, 4, 8, "Crown bud shoot emergence"),
                CropStageNode("RAPID_VEGETATIVE", PhenologyStage.VEGETATIVE, 0.60, 8, 18, "Rapid canopy expansion"),
                CropStageNode("EARLY_BUD_BLOOM", PhenologyStage.REPRODUCTIVE, 0.90, 5, 12, "Pre-bloom to 10% flower"),
                CropStageNode("HARVEST_CUT", PhenologyStage.HARVESTED, 1.00, 2, 5, "Swathing / mechanical cut"),
            ]
        else:
            # Generic annual default
            nodes = [
                CropStageNode("EMERGENCE", PhenologyStage.EMERGENCE, 0.10, 5, 12, "Emergence"),
                CropStageNode("VEGETATIVE", PhenologyStage.VEGETATIVE, 0.40, 14, 35, "Vegetative canopy expansion"),
                CropStageNode("REPRODUCTIVE", PhenologyStage.REPRODUCTIVE, 0.75, 14, 35, "Flowering & seed/fruit development"),
                CropStageNode("SENESCENCE", PhenologyStage.SENESCENCE, 0.95, 7, 20, "Maturation & senescence"),
                CropStageNode("HARVESTED", PhenologyStage.HARVESTED, 1.00, 3, 10, "Harvested"),
            ]
        return cls(crop_code=code, nodes=nodes)

    def map_to_canonical(self, stage_name: str) -> PhenologyStage:
        """Map biological sub-stage identifier to canonical PhenologyStage."""
        sn = str(stage_name).upper().strip()
        if sn in self._node_map:
            return self._node_map[sn].canonical_stage
        for node in self.nodes:
            if sn in node.stage_id or node.stage_id in sn:
                return node.canonical_stage
        try:
            return PhenologyStage(sn)
        except Exception:
            return PhenologyStage.UNKNOWN


# =============================================================================
# Unified Crop Response Profile
# =============================================================================

@dataclass
class CropResponseProfile:
    """Comprehensive, probabilistic crop-response profile consumed by all L2 engines."""

    # ── Identity ──
    crop_code: str
    cultivar: Optional[str]
    family: str
    architecture: str
    is_perennial: bool
    photosynthetic_pathway: str  # "C3" | "C4" | "CAM"
    temporal_morphology: TemporalMorphology

    # ── Phenology Thermal Parameters ──
    t_base: ParameterEstimate
    t_opt_pheno: ParameterEstimate
    t_max_pheno: ParameterEstimate
    gdd_total_cycle: ParameterEstimate
    stage_gdd_fractions: Dict[PhenologyStage, float]

    # ── Photoperiod & Vernalization ──
    is_short_day: bool
    p_critical: ParameterEstimate
    photo_sensitivity: ParameterEstimate
    requires_vernalization: bool
    v_required: ParameterEstimate

    # ── Photosynthesis & Productivity ──
    lue_max: ParameterEstimate               # Maximum light use efficiency (gC / MJ PAR)
    t_opt_photo: ParameterEstimate          # Photosynthetic optimal temperature
    t_min_photo: ParameterEstimate          # Photosynthetic minimum temperature
    t_max_photo: ParameterEstimate          # Photosynthetic maximum temperature

    # ── Canopy & Spectral Priors ──
    k_extinction: ParameterEstimate         # Beer-Lambert extinction coefficient (~0.5)
    lai_max_expected: ParameterEstimate     # Peak healthy LAI
    fvc_soil_baseline: ParameterEstimate    # NDVI soil reference prior
    fvc_veg_asymptote: ParameterEstimate    # NDVI full canopy prior
    ndvi_peak_expected: ParameterEstimate   # Expected peak NDVI
    ndvi_trough_expected: ParameterEstimate # Expected trough NDVI
    stage_ndvi_priors: Dict[PhenologyStage, Tuple[float, float]]  # {Stage: (mean, std)}

    # ── Stress Sensitivity Surfaces (s_k(c, z) ∈ [0, 1]) ──
    water_sensitivity: Dict[PhenologyStage, float]
    heat_sensitivity: Dict[PhenologyStage, float]
    cold_sensitivity: Dict[PhenologyStage, float]
    salinity_sensitivity: Dict[PhenologyStage, float]
    nutrient_sensitivity: Dict[PhenologyStage, float]

    # ── Stage Topology ──
    stage_graph: CropStageGraph
    min_durations: Dict[PhenologyStage, int]
    expected_durations: Dict[PhenologyStage, int]

    # ── Defaults & Provenance (all defaulted fields must be at bottom) ──
    v_base: float = -1.0
    v_opt_min: float = 2.0
    v_opt_max: float = 6.0
    v_max: float = 9.0
    rue_g_dm_mj: Optional[float] = None
    provenance_tier: ParameterSource = ParameterSource.LITERATURE_CROP
    authority: AuthorityLevel = AuthorityLevel.TRANSFERRED
    fallback_count: int = 0
    fallback_levels: List[str] = field(default_factory=list)
    profile_version: str = "4.0.0"

    def get_compound_synergy(
        self,
        stage: PhenologyStage,
        stress_type_a: str,
        stress_type_b: str,
        env_context: Optional[Dict[str, float]] = None,
    ) -> float:
        """Crop-, stage-, and environment-conditioned compound stress interaction factor β(c, z, a, b, env).

        Physiological basis (Mittler 2006, Suzuki et al. 2014, Zandalinas et al. 2018):
        - Co-occurring water and heat stress during reproductive flowering/anthesis
          produces catastrophic supra-additive damage due to tapetum sterility
          and inability to cool canopy via transpiration.
        - Maize (C4 grass): silking-anthesis interval (ASI) desynchronization produces β ≈ 1.85 at flowering.
        - Wheat/Barley (C3 cereal): floret abortion and pollen sterility produce β ≈ 1.75 at anthesis.
        - Potato/Solanaceae: tuber bulking inhibition produces β ≈ 1.65 at reproductive bulking.
        - Olive/Perennial tree: sclerophyllous leaves buffer moderate stress, β ≈ 1.35 at bloom.
        - Environmental modulation (VPD, extreme heat) further elevates vulnerability.
        - Strictly bounded to [1.0, 1.95] to prevent unphysical multiplicative explosion.
        """
        pair = tuple(sorted((stress_type_a.upper(), stress_type_b.upper())))
        code = (self.crop_code or "").lower()
        family = (self.family or "").lower()
        arch = (self.architecture or "").lower()

        # Explicit Additive Vulnerability Model:
        # β = 1.0 + Δβ_crop_pair + Δβ_stage + Δβ_environment
        
        # 1. Base crop-pair interaction delta Δβ_crop_pair
        if self.crop_code == "UNKNOWN_VEGETATION" or self.architecture == "UNKNOWN":
            pair_deltas = {
                ("THERMAL", "WATER"): 0.20,
                ("NUTRIENT", "WATER"): 0.10,
                ("BIOTIC", "THERMAL"): 0.10,
                ("SALINITY", "WATER"): 0.25,
                ("SALINITY", "THERMAL"): 0.10,
            }
            stage_deltas = {}  # No stage amplification for unknown vegetation
        elif "corn" in code or "maize" in code or "sorghum" in code:
            pair_deltas = {
                ("THERMAL", "WATER"): 0.35,
                ("NUTRIENT", "WATER"): 0.15,
                ("BIOTIC", "THERMAL"): 0.15,
                ("SALINITY", "WATER"): 0.30,
                ("SALINITY", "THERMAL"): 0.15,
            }
            stage_deltas = {PhenologyStage.REPRODUCTIVE: 0.30, PhenologyStage.SENESCENCE: 0.12, PhenologyStage.VEGETATIVE: 0.00}
        elif "wheat" in code or "barley" in code or "oat" in code or "rye" in code:
            pair_deltas = {
                ("THERMAL", "WATER"): 0.30,
                ("NUTRIENT", "WATER"): 0.15,
                ("BIOTIC", "THERMAL"): 0.12,
                ("SALINITY", "WATER"): 0.35,
                ("SALINITY", "THERMAL"): 0.20,
            }
            stage_deltas = {PhenologyStage.REPRODUCTIVE: 0.25, PhenologyStage.SENESCENCE: 0.15, PhenologyStage.VEGETATIVE: 0.00}
        elif "potato" in code or "tomato" in code or "solanaceae" in family:
            pair_deltas = {
                ("THERMAL", "WATER"): 0.28,
                ("NUTRIENT", "WATER"): 0.25,
                ("BIOTIC", "THERMAL"): 0.18,
                ("SALINITY", "WATER"): 0.40,
                ("SALINITY", "THERMAL"): 0.15,
            }
            stage_deltas = {PhenologyStage.REPRODUCTIVE: 0.22, PhenologyStage.SENESCENCE: 0.10, PhenologyStage.VEGETATIVE: 0.00}
        elif "olive" in code or "citrus" in code or arch in ("perennial", "tropical_tree"):
            pair_deltas = {
                ("THERMAL", "WATER"): 0.18,
                ("NUTRIENT", "WATER"): 1.10 - 1.0,
                ("BIOTIC", "THERMAL"): 1.10 - 1.0,
                ("SALINITY", "WATER"): 0.22,
                ("SALINITY", "THERMAL"): 1.10 - 1.0,
            }
            stage_deltas = {PhenologyStage.REPRODUCTIVE: 0.10, PhenologyStage.SENESCENCE: 0.05, PhenologyStage.VEGETATIVE: 0.00}
        else:
            pair_deltas = {
                ("THERMAL", "WATER"): 0.25,
                ("NUTRIENT", "WATER"): 0.15,
                ("BIOTIC", "THERMAL"): 0.10,
                ("SALINITY", "WATER"): 0.30,
                ("SALINITY", "THERMAL"): 0.15,
            }
            stage_deltas = {PhenologyStage.REPRODUCTIVE: 0.20, PhenologyStage.SENESCENCE: 0.10, PhenologyStage.VEGETATIVE: 0.00}

        delta_pair = pair_deltas.get(pair, 0.0)
        if delta_pair <= 0.0:
            return 1.0

        # 2. Stage vulnerability delta Δβ_stage
        delta_stage = stage_deltas.get(stage, 0.0)
        
        # 3. Environmental demand delta Δβ_environment
        delta_env = 0.0
        if env_context:
            vpd = env_context.get("vpd")
            temp_max = env_context.get("temp_max")
            if vpd is not None and vpd > 3.0:
                delta_env += min(0.12, (vpd - 3.0) * 0.04)
            if temp_max is not None and temp_max > 36.0:
                delta_env += min(0.08, (temp_max - 36.0) * 0.02)

        # Composite additive formulation: β = 1.0 + Δβ_pair + Δβ_stage + Δβ_env
        beta_final = 1.0 + delta_pair + delta_stage + delta_env
        return round(min(1.95, max(1.0, beta_final)), 3)


# =============================================================================
# Hierarchical Crop Parameter Resolver
# =============================================================================

class CropParameterResolver:
    """Hierarchical parameter resolver (Cultivar → Species → Architecture → Global)."""

    @staticmethod
    def resolve(
        crop_name: Optional[str],
        cultivar: Optional[str] = None,
        operational_context: Optional[Dict[str, Any]] = None,
    ) -> CropResponseProfile:
        """Resolve a full CropResponseProfile from registry + agronomic priors."""
        crop_clean = (crop_name or "").strip().lower()
        cultivar_clean = (cultivar or "").strip() or None
        operational = operational_context or {}

        # 1. Fetch CropSpec from registry
        from crop_database.registry import get_crop, CropSpec
        spec: Optional[CropSpec] = None
        is_unknown_crop = False
        spec = None
        if crop_clean:
            try:
                from crop_database import get_crop_with_provenance
                spec, resolved_code, used_default = get_crop_with_provenance(crop_clean)
                is_unknown_crop = used_default or (resolved_code == "unknown")
            except Exception:
                spec = None

        if spec is None or is_unknown_crop:
            # Genuine UNKNOWN_VEGETATION profile: uninformative broad prior, no cereal physiology assumptions
            return CropResponseProfile(
                crop_code=crop_clean or "UNKNOWN_VEGETATION",
                cultivar=None,
                family="UNKNOWN",
                architecture="UNKNOWN",
                is_perennial=False,
                photosynthetic_pathway="UNKNOWN",
                temporal_morphology=TemporalMorphology.SINGLE_CYCLE_DOUBLE_LOGISTIC,
                t_base=ParameterEstimate(mean=5.0, variance=16.0, source_tier=ParameterSource.GLOBAL_PRIOR, source_id="global_plant_prior", crop="unknown", allowable_range=(-5.0, 20.0)),
                t_opt_pheno=ParameterEstimate(mean=22.0, variance=25.0, source_tier=ParameterSource.GLOBAL_PRIOR, source_id="global_plant_prior", crop="unknown", allowable_range=(5.0, 40.0)),
                t_max_pheno=ParameterEstimate(mean=38.0, variance=30.0, source_tier=ParameterSource.GLOBAL_PRIOR, source_id="global_plant_prior", crop="unknown", allowable_range=(25.0, 55.0)),
                gdd_total_cycle=ParameterEstimate(mean=1500.0, variance=600.0, source_tier=ParameterSource.GLOBAL_PRIOR, source_id="global_plant_prior", crop="unknown", allowable_range=(400.0, 4000.0)),
                stage_gdd_fractions={
                    PhenologyStage.BARE_SOIL: 0.0,
                    PhenologyStage.EMERGENCE: 0.10,
                    PhenologyStage.VEGETATIVE: 0.40,
                    PhenologyStage.REPRODUCTIVE: 0.75,
                    PhenologyStage.SENESCENCE: 0.95,
                    PhenologyStage.HARVESTED: 1.00,
                    PhenologyStage.DORMANCY: 0.0,
                },
                is_short_day=False,
                p_critical=ParameterEstimate(mean=14.0, variance=2.0, source_tier=ParameterSource.GLOBAL_PRIOR, source_id="global_plant_prior", crop="unknown", allowable_range=(10.0, 16.0)),
                photo_sensitivity=ParameterEstimate(mean=0.0, variance=0.0, source_tier=ParameterSource.GLOBAL_PRIOR, source_id="global_plant_prior", crop="unknown", allowable_range=(0.0, 3.0)),
                requires_vernalization=False,
                v_required=ParameterEstimate(mean=0.0, variance=0.0, source_tier=ParameterSource.GLOBAL_PRIOR, source_id="global_plant_prior", crop="unknown", allowable_range=(0.0, 100.0)),
                lue_max=ParameterEstimate(mean=0.80, variance=0.40, source_tier=ParameterSource.GLOBAL_PRIOR, source_id="global_plant_prior", crop="unknown", allowable_range=(0.2, 2.5)),
                t_opt_photo=ParameterEstimate(mean=22.0, variance=25.0, source_tier=ParameterSource.GLOBAL_PRIOR, source_id="global_plant_prior", crop="unknown", allowable_range=(5.0, 40.0)),
                t_min_photo=ParameterEstimate(mean=5.0, variance=16.0, source_tier=ParameterSource.GLOBAL_PRIOR, source_id="global_plant_prior", crop="unknown", allowable_range=(-5.0, 20.0)),
                t_max_photo=ParameterEstimate(mean=38.0, variance=30.0, source_tier=ParameterSource.GLOBAL_PRIOR, source_id="global_plant_prior", crop="unknown", allowable_range=(25.0, 55.0)),
                k_extinction=ParameterEstimate(mean=0.50, variance=0.15, source_tier=ParameterSource.GLOBAL_PRIOR, source_id="global_plant_prior", crop="unknown", allowable_range=(0.3, 0.9)),
                lai_max_expected=ParameterEstimate(mean=4.0, variance=2.0, source_tier=ParameterSource.GLOBAL_PRIOR, source_id="global_plant_prior", crop="unknown", allowable_range=(0.5, 8.0)),
                fvc_soil_baseline=ParameterEstimate(mean=0.15, variance=0.05, source_tier=ParameterSource.GLOBAL_PRIOR, source_id="global_plant_prior", crop="unknown", allowable_range=(0.05, 0.30)),
                fvc_veg_asymptote=ParameterEstimate(mean=0.80, variance=0.10, source_tier=ParameterSource.GLOBAL_PRIOR, source_id="global_plant_prior", crop="unknown", allowable_range=(0.50, 0.95)),
                ndvi_peak_expected=ParameterEstimate(mean=0.65, variance=0.20, source_tier=ParameterSource.GLOBAL_PRIOR, source_id="global_plant_prior", crop="unknown", allowable_range=(0.30, 0.95)),
                ndvi_trough_expected=ParameterEstimate(mean=0.12, variance=0.05, source_tier=ParameterSource.GLOBAL_PRIOR, source_id="global_plant_prior", crop="unknown", allowable_range=(0.05, 0.30)),
                stage_ndvi_priors={s: (0.45, 0.25) for s in PhenologyStage},
                water_sensitivity={s: 0.5 for s in PhenologyStage},
                heat_sensitivity={s: 0.5 for s in PhenologyStage},
                cold_sensitivity={s: 0.5 for s in PhenologyStage},
                salinity_sensitivity={s: 0.5 for s in PhenologyStage},
                nutrient_sensitivity={s: 0.5 for s in PhenologyStage},
                stage_graph=CropStageGraph.create_for_crop("unknown", "generic_vegetation"),
                min_durations={s: 5 for s in PhenologyStage},
                expected_durations={s: 25 for s in PhenologyStage},
                provenance_tier=ParameterSource.GLOBAL_PRIOR,
                authority=AuthorityLevel.PRIOR_ONLY,
                fallback_count=1,
                fallback_levels=["UNKNOWN_VEGETATION_UNINFORMATIVE_PRIOR"],
            )

        # 2. Extract architecture & morphology
        arch = spec.architecture or "cereal"
        is_perennial = arch in ("perennial", "tropical_tree") or "olive" in crop_clean
        pathway = getattr(spec, "photosynthetic_pathway", "C3").upper()
        if pathway not in ("C3", "C4", "CAM"):
            pathway = "C4" if arch in ("maize", "sorghum") else "C3"

        # Determine morphology
        if "alfalfa" in crop_clean or "clover" in crop_clean:
            morphology = TemporalMorphology.MULTI_CYCLE_REGROWTH
        elif "olive" in crop_clean or "citrus" in crop_clean:
            morphology = TemporalMorphology.EVERGREEN_SEASONAL
        elif is_perennial:
            morphology = TemporalMorphology.DECIDUOUS_PERENNIAL
        elif operational.get("is_greenhouse") or operational.get("protected_crop"):
            morphology = TemporalMorphology.PROTECTED_CROP
        else:
            morphology = TemporalMorphology.SINGLE_CYCLE_DOUBLE_LOGISTIC

        fallback_levels = []
        source_tier = ParameterSource.LITERATURE_CROP if not is_unknown_crop else ParameterSource.GLOBAL_PRIOR
        authority = AuthorityLevel.TRANSFERRED if not is_unknown_crop else AuthorityLevel.PRIOR_ONLY

        if is_unknown_crop:
            fallback_levels.append("UNKNOWN_CROP_GLOBAL_FALLBACK")

        # 3. Phenology Cardinal Temperatures
        t_base_val = float(getattr(spec, "gdd_base_temp", 0.0) or 0.0)
        t_opt_min = float(getattr(spec, "optimal_temp_min", 12.0) or 12.0)
        t_opt_max = float(getattr(spec, "optimal_temp_max", 25.0) or 25.0)
        t_opt_mean = (t_opt_min + t_opt_max) / 2.0
        t_max_val = max(35.0, t_opt_max + 10.0)

        # Variance widening when uncalibrated
        t_var = 1.0 if not is_unknown_crop else 4.0

        p_t_base = ParameterEstimate(
            mean=t_base_val, variance=t_var, source_tier=source_tier,
            source_id="crop_registry", crop=spec.code, allowable_range=(-5.0, 20.0),
        )
        p_t_opt = ParameterEstimate(
            mean=t_opt_mean, variance=t_var * 1.5, source_tier=source_tier,
            source_id="crop_registry", crop=spec.code, allowable_range=(5.0, 40.0),
        )
        p_t_max = ParameterEstimate(
            mean=t_max_val, variance=t_var * 2.0, source_tier=source_tier,
            source_id="crop_registry", crop=spec.code, allowable_range=(25.0, 55.0),
        )

        growing_days = int(getattr(spec, "growing_days", 140) or 140)
        # Approximate GDD cycle = growing_days * max(5, t_opt_mean - t_base_val) * 0.7
        gdd_est = float(growing_days * max(6.0, t_opt_mean - t_base_val) * 0.75)
        p_gdd_total = ParameterEstimate(
            mean=round(gdd_est, 1), variance=gdd_est * 0.15, source_tier=source_tier,
            source_id="crop_registry", crop=spec.code, allowable_range=(400.0, 4000.0),
        )

        # 4. Photoperiod & Vernalization
        is_short_day = crop_clean in ("rice", "sorghum", "millet", "soybean", "cotton", "maize", "corn")
        p_p_crit = ParameterEstimate(
            mean=13.0 if is_short_day else 14.0, variance=0.5, source_tier=source_tier,
            source_id="agronomic_literature", crop=spec.code, allowable_range=(10.0, 16.0),
        )
        p_photo_sens = ParameterEstimate(
            mean=1.5 if is_short_day else 0.0, variance=0.2, source_tier=source_tier,
            source_id="agronomic_literature", crop=spec.code, allowable_range=(0.0, 3.0),
        )

        requires_vern = (arch == "cereal" and "winter" in crop_clean) or ("winter" in (cultivar_clean or "").lower())
        p_v_req = ParameterEstimate(
            mean=45.0 if requires_vern else 0.0, variance=10.0 if requires_vern else 0.1,
            source_tier=source_tier, source_id="richardson_chuine", crop=spec.code,
            allowable_range=(0.0, 80.0),
        )

        # 5. Photosynthetic Parameters & LUE (separated from phenology)
        # C4 crops have higher LUE (~1.25-1.50 gC/MJ), C3 crops (~0.60-0.85 gC/MJ), CAM (~0.40 gC/MJ)
        if pathway == "C4":
            lue_mean = 1.30
        elif pathway == "CAM":
            lue_mean = 0.45
        else:
            lue_mean = 0.65

        p_lue = ParameterEstimate(
            mean=lue_mean, variance=0.04, source_tier=ParameterSource.LITERATURE_SPECIFIC,
            source_id="monteith_potter_casa", crop=spec.code, allowable_range=(0.2, 2.5),
        )
        # True photosynthetic temperature response (acclimation window)
        p_t_opt_photo = ParameterEstimate(
            mean=t_opt_mean, variance=t_var * 2.0, source_tier=source_tier,
            source_id="crop_registry_photo_fallback", crop=spec.code, allowable_range=(10.0, 38.0),
        )
        p_t_min_photo = ParameterEstimate(
            mean=max(0.0, t_opt_min - 7.0), variance=4.0, source_tier=source_tier,
            source_id="photo_envelope", crop=spec.code, allowable_range=(-5.0, 15.0),
        )
        p_t_max_photo = ParameterEstimate(
            mean=min(50.0, t_opt_max + 12.0), variance=6.0, source_tier=source_tier,
            source_id="photo_envelope", crop=spec.code, allowable_range=(30.0, 55.0),
        )

        # 6. Canopy & Spectral Trajectory Priors from CROP_NDVI_SIGNATURES or CropSpec
        from layer2_veg_int.crop_science_data import CROP_NDVI_SIGNATURES
        sig = CROP_NDVI_SIGNATURES.get(crop_clean, {})
        peak_ndvi = float(sig.get("peak_ndvi", 0.75))
        trough_ndvi = float(sig.get("trough_ndvi", 0.12))

        p_ndvi_peak = ParameterEstimate(
            mean=peak_ndvi, variance=0.005, source_tier=source_tier,
            source_id="crop_science_signatures", crop=spec.code, allowable_range=(0.3, 0.95),
        )
        p_ndvi_trough = ParameterEstimate(
            mean=trough_ndvi, variance=0.003, source_tier=source_tier,
            source_id="crop_science_signatures", crop=spec.code, allowable_range=(0.02, 0.50),
        )
        p_k_ext = ParameterEstimate(
            mean=0.50, variance=0.01, source_tier=ParameterSource.GLOBAL_PRIOR,
            source_id="myneni_beer_lambert", crop=spec.code, allowable_range=(0.3, 0.8),
        )
        p_lai_max = ParameterEstimate(
            mean=round(min(7.0, max(1.5, (peak_ndvi - 0.10) * 6.5)), 1),
            variance=0.35, source_tier=source_tier,
            source_id="beer_lambert_prior", crop=spec.code, allowable_range=(0.5, 9.0),
        )
        p_fvc_soil = ParameterEstimate(
            mean=trough_ndvi, variance=0.002, source_tier=source_tier,
            source_id="fvc_soil_prior", crop=spec.code, allowable_range=(0.04, 0.25),
        )
        p_fvc_veg = ParameterEstimate(
            mean=peak_ndvi, variance=0.003, source_tier=source_tier,
            source_id="fvc_veg_prior", crop=spec.code, allowable_range=(0.60, 0.95),
        )

        # Stage NDVI expectations tailored to crop
        mid_ndvi = (peak_ndvi + trough_ndvi) / 2.0
        stage_ndvi_priors = {
            PhenologyStage.BARE_SOIL: (trough_ndvi, 0.05),
            PhenologyStage.EMERGENCE: (trough_ndvi + 0.25 * (peak_ndvi - trough_ndvi), 0.07),
            PhenologyStage.VEGETATIVE: (mid_ndvi, 0.10),
            PhenologyStage.REPRODUCTIVE: (peak_ndvi, 0.08),
            PhenologyStage.SENESCENCE: (mid_ndvi * 0.9, 0.10),
            PhenologyStage.HARVESTED: (trough_ndvi + 0.04, 0.05),
            PhenologyStage.DORMANCY: (trough_ndvi + 0.40 * (peak_ndvi - trough_ndvi), 0.08),
        }

        # 7. Stress Sensitivity Surfaces
        # Sourced from CropSpec.water_stress_sensitivity + FAO-33 / Hsiao
        raw_wss = getattr(spec, "water_stress_sensitivity", {}) or {}
        water_sens = {
            PhenologyStage.BARE_SOIL: float(raw_wss.get("BARE_SOIL", 0.0)),
            PhenologyStage.EMERGENCE: float(raw_wss.get("EMERGENCE", 0.4)),
            PhenologyStage.VEGETATIVE: float(raw_wss.get("VEGETATIVE", 0.3)),
            PhenologyStage.REPRODUCTIVE: float(raw_wss.get("REPRODUCTIVE", 0.9)),
            PhenologyStage.SENESCENCE: float(raw_wss.get("SENESCENCE", 0.1)),
            PhenologyStage.HARVESTED: float(raw_wss.get("HARVESTED", 0.0)),
            PhenologyStage.DORMANCY: 0.1,
        }
        heat_sens = {
            PhenologyStage.BARE_SOIL: 0.0,
            PhenologyStage.EMERGENCE: 0.4,
            PhenologyStage.VEGETATIVE: 0.3,
            PhenologyStage.REPRODUCTIVE: 0.95,  # Anthesis/flowering extreme sensitivity
            PhenologyStage.SENESCENCE: 0.2,
            PhenologyStage.HARVESTED: 0.0,
            PhenologyStage.DORMANCY: 0.1,
        }
        cold_sens = {
            PhenologyStage.BARE_SOIL: 0.0,
            PhenologyStage.EMERGENCE: 0.6,
            PhenologyStage.VEGETATIVE: 0.3,
            PhenologyStage.REPRODUCTIVE: 0.8,
            PhenologyStage.SENESCENCE: 0.1,
            PhenologyStage.HARVESTED: 0.0,
            PhenologyStage.DORMANCY: 0.05,
        }
        salinity_sens = {
            PhenologyStage.BARE_SOIL: 0.0,
            PhenologyStage.EMERGENCE: 0.7,
            PhenologyStage.VEGETATIVE: 0.5,
            PhenologyStage.REPRODUCTIVE: 0.6,
            PhenologyStage.SENESCENCE: 0.2,
            PhenologyStage.HARVESTED: 0.0,
            PhenologyStage.DORMANCY: 0.1,
        }
        nutrient_sens = {
            PhenologyStage.BARE_SOIL: 0.0,
            PhenologyStage.EMERGENCE: 0.3,
            PhenologyStage.VEGETATIVE: 0.8,
            PhenologyStage.REPRODUCTIVE: 0.6,
            PhenologyStage.SENESCENCE: 0.1,
            PhenologyStage.HARVESTED: 0.0,
            PhenologyStage.DORMANCY: 0.1,
        }

        # 8. Stage graph & duration distributions
        stage_graph = CropStageGraph.create_for_crop(spec.code, arch)
        min_durations = {
            PhenologyStage.BARE_SOIL: 5,
            PhenologyStage.EMERGENCE: 5,
            PhenologyStage.VEGETATIVE: 12,
            PhenologyStage.REPRODUCTIVE: 10,
            PhenologyStage.SENESCENCE: 7,
            PhenologyStage.HARVESTED: 3,
            PhenologyStage.DORMANCY: 14,
        }
        expected_durations = {
            PhenologyStage.BARE_SOIL: 20,
            PhenologyStage.EMERGENCE: max(7, int(growing_days * 0.08)),
            PhenologyStage.VEGETATIVE: max(15, int(growing_days * 0.35)),
            PhenologyStage.REPRODUCTIVE: max(15, int(growing_days * 0.35)),
            PhenologyStage.SENESCENCE: max(10, int(growing_days * 0.18)),
            PhenologyStage.HARVESTED: 15,
            PhenologyStage.DORMANCY: 60,
        }

        stage_gdd_fracs = {
            PhenologyStage.BARE_SOIL: 0.0,
            PhenologyStage.EMERGENCE: 0.08,
            PhenologyStage.VEGETATIVE: 0.35,
            PhenologyStage.REPRODUCTIVE: 0.70,
            PhenologyStage.SENESCENCE: 0.92,
            PhenologyStage.HARVESTED: 1.00,
            PhenologyStage.DORMANCY: 0.0,
        }

        return CropResponseProfile(
            crop_code=crop_clean if is_unknown_crop else spec.code,
            cultivar=cultivar_clean,
            family=spec.family or "Poaceae",
            architecture=arch,
            is_perennial=is_perennial,
            photosynthetic_pathway=pathway,
            temporal_morphology=morphology,
            t_base=p_t_base,
            t_opt_pheno=p_t_opt,
            t_max_pheno=p_t_max,
            gdd_total_cycle=p_gdd_total,
            stage_gdd_fractions=stage_gdd_fracs,
            is_short_day=is_short_day,
            p_critical=p_p_crit,
            photo_sensitivity=p_photo_sens,
            requires_vernalization=requires_vern,
            v_required=p_v_req,
            lue_max=p_lue,
            t_opt_photo=p_t_opt_photo,
            t_min_photo=p_t_min_photo,
            t_max_photo=p_t_max_photo,
            rue_g_dm_mj=getattr(spec, "rue_g_mj", None),
            k_extinction=p_k_ext,
            lai_max_expected=p_lai_max,
            fvc_soil_baseline=p_fvc_soil,
            fvc_veg_asymptote=p_fvc_veg,
            ndvi_peak_expected=p_ndvi_peak,
            ndvi_trough_expected=p_ndvi_trough,
            stage_ndvi_priors=stage_ndvi_priors,
            water_sensitivity=water_sens,
            heat_sensitivity=heat_sens,
            cold_sensitivity=cold_sens,
            salinity_sensitivity=salinity_sens,
            nutrient_sensitivity=nutrient_sens,
            stage_graph=stage_graph,
            min_durations=min_durations,
            expected_durations=expected_durations,
            provenance_tier=source_tier,
            authority=authority,
            fallback_count=len(fallback_levels),
            fallback_levels=fallback_levels,
        )


# =============================================================================
# Causal Biological Progress Coordinate τ ∈ [0, 1]
# =============================================================================

class CausalBiologicalProgress:
    """Computes causal biological progress τ_t without retrospective full-season leakage."""

    @staticmethod
    def compute_daily_progress(
        t_mean_series: List[Optional[float]],
        dates: List[str],
        profile: CropResponseProfile,
        t_max_series: Optional[List[Optional[float]]] = None,
        delta_days: Optional[List[float]] = None,
        vernalization_series: Optional[List[float]] = None,
        initial_gdd: float = 0.0,
        day_length_fn = None,
    ) -> List[float]:
        """Compute causal biological progress τ_t ∈ [0, 1] for each day t.

        Physiological Formulation:
          ΔD_t = max(0, T_mean,t - T_base) * f_heat(T_max,t) * f_P(P_t) * Δt
          τ_t = min(1.0, D_t / D_cycle)
        """
        tau_series = []
        d_accum = max(0.0, initial_gdd)
        d_total = max(100.0, profile.gdd_total_cycle.mean)
        t_base = profile.t_base.mean
        t_opt = profile.t_opt_pheno.mean
        t_max = profile.t_max_pheno.mean

        for i, t_mean in enumerate(t_mean_series):
            if t_mean is not None:
                dt = delta_days[i] if (delta_days and i < len(delta_days) and delta_days[i] is not None) else 1.0
                t_max_val = t_max_series[i] if (t_max_series and i < len(t_max_series) and t_max_series[i] is not None) else t_mean + 5.0

                # 1. Thermal time increment GDD_t = max(0, T_mean - T_base) * Δt
                gdd_t = max(0.0, t_mean - t_base) * dt

                # 2. High-temperature inhibition factor f_heat(T_max)
                if t_max_val > t_max:
                    f_heat = 0.0
                elif t_max_val > t_opt:
                    f_heat = max(0.0, 1.0 - (t_max_val - t_opt) / max(1.0, t_max - t_opt))
                else:
                    f_heat = 1.0

                delta_d = gdd_t * f_heat

                # Photoperiod factor if short day
                if profile.is_short_day and day_length_fn:
                    date_str = dates[i] if i < len(dates) else ""
                    p_len = day_length_fn(date_str)
                    if p_len is not None:
                        k = profile.photo_sensitivity.mean or 1.5
                        p_crit = profile.p_critical.mean
                        photo_factor = 1.0 / (1.0 + math.exp(k * (p_len - p_crit)))
                        delta_d *= max(0.1, min(1.0, photo_factor))

                d_accum += delta_d

            tau = min(1.0, max(0.0, d_accum / d_total))
            tau_series.append(round(tau, 3))

        return tau_series

    @staticmethod
    def expected_ndvi_at_progress(
        tau: float,
        profile: CropResponseProfile,
    ) -> Tuple[float, float]:
        """Expected NDVI and standard deviation given biological progress τ.

        E[NDVI | c, τ] modeled as bell-shaped canopy trajectory.
        """
        trough = profile.ndvi_trough_expected.mean
        peak = profile.ndvi_peak_expected.mean
        amp = peak - trough

        if profile.temporal_morphology == TemporalMorphology.EVERGREEN_SEASONAL:
            # Flatter bounded seasonal variation around high vegetative baseline
            val = trough + 0.6 * amp + 0.4 * amp * math.sin(math.pi * tau)
            sigma = 0.08
        elif profile.temporal_morphology == TemporalMorphology.MULTI_CYCLE_REGROWTH:
            # Multi-cut forage / alfalfa: cyclical regrowth cycles
            cycle_phase = (tau * 4.0) % 1.0
            frac = (1.0 - math.cos(math.pi * cycle_phase)) / 2.0
            val = trough + amp * frac
            sigma = 0.12
        elif profile.temporal_morphology == TemporalMorphology.PROTECTED_CROP:
            # Greenhouse: rapid reach to high canopy plateau, no weather dry-down
            frac = min(1.0, tau / 0.3)
            val = trough + amp * frac
            sigma = 0.06
        elif profile.temporal_morphology == TemporalMorphology.DECIDUOUS_PERENNIAL:
            # Budburst (0.0-0.3) -> full canopy (0.3-0.75) -> leaf fall (0.75-1.0)
            if tau <= 0.3:
                frac = (1.0 - math.cos(math.pi * (tau / 0.3))) / 2.0
            elif tau <= 0.75:
                frac = 1.0
            else:
                frac = (1.0 + math.cos(math.pi * ((tau - 0.75) / 0.25))) / 2.0
            val = trough + amp * frac
            sigma = 0.09
        else:
            # Single cycle canopy expansion and senescence
            if tau <= 0.5:
                frac = (1.0 - math.cos(math.pi * (tau / 0.5))) / 2.0
                val = trough + amp * frac
            else:
                frac = (1.0 + math.cos(math.pi * ((tau - 0.5) / 0.5))) / 2.0
                val = trough + amp * frac
            sigma = 0.10

        return max(0.05, min(0.95, round(val, 3))), sigma


# =============================================================================
# Normalized Crop-Context Consistency Watchdog
# =============================================================================

class CropContextConsistency:
    """Evaluates whether the observed NDVI trajectory is consistent with the declared crop."""

    @staticmethod
    def evaluate_consistency(
        observed_ndvi: List[Optional[float]],
        tau_series: List[float],
        profile: CropResponseProfile,
    ) -> Dict[str, Any]:
        """Calculates normalized likelihood ratio LR_c = 1/N * [log P(Y | c) - log P(Y | generic)].

        If LR_c << 0, flags CONFIRM_CROP_OR_CYCLE.
        """
        valid_obs = [
            (obs, tau) for obs, tau in zip(observed_ndvi, tau_series)
            if obs is not None and not math.isnan(obs)
        ]
        n_eff = len(valid_obs)
        if n_eff < 4:
            return {
                "consistency": "INSUFFICIENT_EVIDENCE",
                "action": "PROCEED",
                "normalized_log_ratio": 0.0,
                "mismatch_detected": False,
                "recommendation": None,
                "n_evaluated": n_eff,
            }

        log_lik_crop = 0.0
        log_lik_generic = 0.0

        for obs, tau in valid_obs:
            # Crop-conditioned expectation
            mu_c, sig_c = CausalBiologicalProgress.expected_ndvi_at_progress(tau, profile)
            ll_c = -0.5 * ((obs - mu_c) / sig_c) ** 2 - math.log(sig_c)
            log_lik_crop += ll_c

            # Generic uninformative prior (flat Gaussian across wide vegetative range)
            mu_g, sig_g = 0.45, 0.25
            ll_g = -0.5 * ((obs - mu_g) / sig_g) ** 2 - math.log(sig_g)
            log_lik_generic += ll_g

        norm_lr = (log_lik_crop - log_lik_generic) / max(1, n_eff)

        # Decision rule
        if norm_lr < -1.2:
            consistency = "LOW"
            mismatch = True
            rec = "CONFIRM_CROP_OR_CYCLE"
        elif norm_lr < -0.4:
            consistency = "MEDIUM"
            mismatch = False
            rec = None
        else:
            consistency = "HIGH"
            mismatch = False
            rec = None

        return {
            "consistency": consistency,
            "action": "CONFIRM_CROP_OR_CYCLE" if mismatch else "PROCEED",
            "normalized_log_ratio": round(norm_lr, 4),
            "mismatch_detected": mismatch,
            "recommendation": rec,
            "n_evaluated": n_eff,
        }
