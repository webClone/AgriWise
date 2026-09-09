"""
Layer 10 Schema: SIRE — Spatial Intelligence & Rendering Engine
================================================================

Layer 10 transforms L1–L8 outputs into map-native intelligence products:
  - Continuous surfaces (vegetation, water, nutrients, risk, uncertainty)
  - Grounded zones with evidence, confidence, and provenance
  - Object-level structural detail (canopy, rows, gaps)
  - Histogram analytics
  - Render manifests and style packs

Invariants:
  - All surfaces aligned to one grid (grid_spec)
  - No semantic value outside its valid range
  - Fine-detail redistribution conserves coarse-cell mean
  - Zone polygons valid and non-overlapping within a family
  - Source dominance weights sum to 1.0 per pixel
  - No action overlay without upstream action evidence
  - Enhancement never changes quantitative surface values
  - Histogram bin counts sum to total valid pixels
  - Every zone has evidence and confidence
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from services.agribrain.layer10_sire.surface_contract import RENDER_AUTHORIZATION_VERSION
from enum import Enum
from services.agribrain.common.plot_namespace import PlotNamespace


# ============================================================================
# ENUMS
# ============================================================================

class SurfaceType(str, Enum):
    """Semantic types for continuous raster surfaces."""
    # Vegetation
    NDVI_CLEAN = "NDVI_CLEAN"
    NDVI_DEVIATION = "NDVI_DEVIATION"
    BASELINE_ANOMALY = "BASELINE_ANOMALY"
    GROWTH_VELOCITY = "GROWTH_VELOCITY"
    GROWTH_ACCELERATION = "GROWTH_ACCELERATION"
    PHENOLOGY_ALIGNMENT = "PHENOLOGY_ALIGNMENT"
    STABILITY_CLASS = "STABILITY_CLASS"
    PERSISTENT_LOW_VIGOR = "PERSISTENT_LOW_VIGOR"

    # Water
    WATER_STRESS_PROB = "WATER_STRESS_PROB"
    SOIL_MOISTURE_PROXY = "SOIL_MOISTURE_PROXY"
    DROUGHT_ACCUMULATION = "DROUGHT_ACCUMULATION"
    DRAINAGE_DEFICIT_MM = "DRAINAGE_DEFICIT_MM"
    VPD_STRESS = "VPD_STRESS"                       # Vapor Pressure Deficit stomatal stress

    # Nutrients
    NUTRIENT_STRESS_PROB = "NUTRIENT_STRESS_PROB"
    N_RESPONSE_POTENTIAL = "N_RESPONSE_POTENTIAL"
    FERTILITY_LIMITATION = "FERTILITY_LIMITATION"
    N_LEACHING_RISK = "N_LEACHING_RISK"
    N_VOLATILIZATION_RISK = "N_VOLATILIZATION_RISK"

    # Salinity / Soil Health / Biophysical
    SALINITY_STRESS = "SALINITY_STRESS"              # Soil salinity stress probability
    SOIL_CARBON = "SOIL_CARBON"                      # Soil organic carbon stocks (t C/ha)
    SOIL_COMPACTION = "SOIL_COMPACTION"              # Soil compaction risk index
    THERMAL_STRESS = "THERMAL_STRESS"                # Crop thermal stress probability

    # Disease / Bio
    BIOTIC_PRESSURE = "BIOTIC_PRESSURE"
    SPREAD_LIKELIHOOD = "SPREAD_LIKELIHOOD"
    WEATHER_PRESSURE = "WEATHER_PRESSURE"

    # Yield
    YIELD_P50 = "YIELD_P50"
    YIELD_P10 = "YIELD_P10"
    YIELD_P90 = "YIELD_P90"
    YIELD_GAP = "YIELD_GAP"
    YIELD_PENALTY = "YIELD_PENALTY"                 # Stress-adjusted yield loss (t/ha)
    YIELD_VALUE_AT_RISK = "YIELD_VALUE_AT_RISK"     # Monetary loss surface (currency/ha)
    PROFIT_SURFACE = "PROFIT_SURFACE"

    # Suitability
    CROP_SUITABILITY = "CROP_SUITABILITY"
    WATER_FEASIBILITY = "WATER_FEASIBILITY"
    BIOTIC_FEASIBILITY = "BIOTIC_FEASIBILITY"
    ECONOMIC_SUITABILITY = "ECONOMIC_SUITABILITY"

    # Risk
    COMPOSITE_RISK = "COMPOSITE_RISK"
    SHOCK_RISK = "SHOCK_RISK"
    EXECUTION_RISK = "EXECUTION_RISK"

    # Trust & Uncertainty
    UNCERTAINTY_SIGMA = "UNCERTAINTY_SIGMA"
    DATA_RELIABILITY = "DATA_RELIABILITY"
    DATA_CONFIDENCE = "DATA_CONFIDENCE"                  # V92.4-BC.2: Separate from DATA_RELIABILITY
    OBSERVED_DATA_MASK_NDVI = "OBSERVED_DATA_MASK_NDVI"
    GAP_FILL_MASK_NDVI = "GAP_FILL_MASK_NDVI"
    VALID_DATA_MASK_NDVI = "VALID_DATA_MASK_NDVI"
    INTERPOLATION_DENSITY = "INTERPOLATION_DENSITY"
    STALENESS = "STALENESS"
    SOURCE_DOMINANCE = "SOURCE_DOMINANCE"
    CONFLICT_DENSITY = "CONFLICT_DENSITY"

    # Temporal Surfaces (14-day window: T-7 → T+7)
    NDVI_DELTA_7D = "NDVI_DELTA_7D"                      # 7-day NDVI change per pixel
    STRESS_MOMENTUM = "STRESS_MOMENTUM"                   # Water stress acceleration vector
    DISEASE_SPREAD_FORECAST = "DISEASE_SPREAD_FORECAST"   # 7-day biotic spread projection
    YIELD_TRAJECTORY = "YIELD_TRAJECTORY"                 # Yield trend (biomass proxy)
    RISK_MOMENTUM = "RISK_MOMENTUM"                       # Risk acceleration/deceleration
    DROUGHT_TREND = "DROUGHT_TREND"                       # Consecutive dry-day trend
    NUTRIENT_DEPLETION_RATE = "NUTRIENT_DEPLETION_RATE"   # Nutrient burn-down rate
    GROWTH_TREND_7D = "GROWTH_TREND_7D"                   # 7-day growth velocity trend
    PRECIPITATION_FORECAST = "PRECIPITATION_FORECAST"     # 7-day precipitation forecast
    TEMPERATURE_FORECAST = "TEMPERATURE_FORECAST"         # 7-day temperature forecast

    # Execution & Intervention (L6/L8)
    EXECUTION_READINESS = "EXECUTION_READINESS"           # Intervention readiness score
    INTERVENTION_PRIORITY = "INTERVENTION_PRIORITY"       # Action priority heatmap
    INTERVENTION_TIMING = "INTERVENTION_TIMING"           # Optimal timing overlay
    CONFLICT_RESOLUTION = "CONFLICT_RESOLUTION"           # Cross-layer conflict heatmap

    # Planning Temporal (L7)
    SUITABILITY_WINDOW = "SUITABILITY_WINDOW"             # Planting window countdown
    SEASON_PROGRESS = "SEASON_PROGRESS"                   # Season progression index

    # Resolution & Ground Truth (V61)
    RESOLUTION_COVERAGE = "RESOLUTION_COVERAGE"           # Stable categorical codes 0..5; see provenance legend
    EXPERIMENTAL_FINE_DETAIL_CANDIDATE = "EXPERIMENTAL_FINE_DETAIL_CANDIDATE"

    # Experimental fine-detail visual overlays (V65F)
    NDVI_CLEAN_EXPERIMENTAL_FINE_DETAIL = "NDVI_CLEAN_EXPERIMENTAL_FINE_DETAIL"
    NDVI_DEVIATION_EXPERIMENTAL_FINE_DETAIL = "NDVI_DEVIATION_EXPERIMENTAL_FINE_DETAIL"
    WATER_STRESS_PROB_EXPERIMENTAL_FINE_DETAIL = "WATER_STRESS_PROB_EXPERIMENTAL_FINE_DETAIL"
    NUTRIENT_STRESS_PROB_EXPERIMENTAL_FINE_DETAIL = "NUTRIENT_STRESS_PROB_EXPERIMENTAL_FINE_DETAIL"
    SALINITY_STRESS_EXPERIMENTAL_FINE_DETAIL = "SALINITY_STRESS_EXPERIMENTAL_FINE_DETAIL"
    COMPOSITE_RISK_EXPERIMENTAL_FINE_DETAIL = "COMPOSITE_RISK_EXPERIMENTAL_FINE_DETAIL"
    DATA_RELIABILITY_EXPERIMENTAL_FINE_DETAIL = "DATA_RELIABILITY_EXPERIMENTAL_FINE_DETAIL"
    BASELINE_ANOMALY_EXPERIMENTAL_FINE_DETAIL = "BASELINE_ANOMALY_EXPERIMENTAL_FINE_DETAIL"
    EXPERIMENTAL_VISUAL_CANOPY = "EXPERIMENTAL_VISUAL_CANOPY"
    EXPERIMENTAL_VISUAL_CANOPY_HIGHRES = "EXPERIMENTAL_VISUAL_CANOPY_HIGHRES"
    EXPERIMENTAL_TEXTURE_CONFIDENCE = "EXPERIMENTAL_TEXTURE_CONFIDENCE"
    EXPERIMENTAL_STRICT_FINE_DETAIL_CANDIDATE_MASK = "EXPERIMENTAL_STRICT_FINE_DETAIL_CANDIDATE_MASK"
    EXPERIMENTAL_GAPFILL_MASK = "EXPERIMENTAL_GAPFILL_MASK"
    EXPERIMENTAL_PARENT_MEAN_ERROR = "EXPERIMENTAL_PARENT_MEAN_ERROR"

    # ASMAE State Surfaces (V82)
    ASMAE_VIGOR = "ASMAE_VIGOR"
    ASMAE_LAI = "ASMAE_LAI"
    ASMAE_CHLOROPHYLL = "ASMAE_CHLOROPHYLL"
    ASMAE_CANOPY_WATER = "ASMAE_CANOPY_WATER"
    ASMAE_ROOT_ZONE_WATER = "ASMAE_ROOT_ZONE_WATER"
    ASMAE_SURFACE_WETNESS_EVENT = "ASMAE_SURFACE_WETNESS_EVENT"
    ASMAE_STRUCTURE = "ASMAE_STRUCTURE"
    ASMAE_BARE_SOIL = "ASMAE_BARE_SOIL"
    ASMAE_SALINITY_STRESS = "ASMAE_SALINITY_STRESS"
    ASMAE_THERMAL_STRESS = "ASMAE_THERMAL_STRESS"
    ASMAE_BIOTIC_CONFOUNDER_RISK = "ASMAE_BIOTIC_CONFOUNDER_RISK"

    # ASMAE Diagnostic Surfaces (V82)
    ASMAE_EFFECTIVE_RESOLUTION = "ASMAE_EFFECTIVE_RESOLUTION"
    ASMAE_POSTERIOR_CONCENTRATION = "ASMAE_POSTERIOR_CONCENTRATION"
    ASMAE_CONFIDENCE = "ASMAE_CONFIDENCE"
    ASMAE_UNCERTAINTY = "ASMAE_UNCERTAINTY"
    ASMAE_RETROVALIDATION_SCORE = "ASMAE_RETROVALIDATION_SCORE"
    ASMAE_BMA_DISAGREEMENT = "ASMAE_BMA_DISAGREEMENT"
    ASMAE_CROSS_LAYER_CONFLICT = "ASMAE_CROSS_LAYER_CONFLICT"
    ASMAE_EXPORT_ELIGIBILITY = "ASMAE_EXPORT_ELIGIBILITY"

    # V92.4-BC.9 ASMAE Visual Intelligence Fusion surfaces
    ASMAE_1M_ADVISORY_MASK = "ASMAE_1M_ADVISORY_MASK"
    ASMAE_2_5M_MODEL_ASSISTED_MASK = "ASMAE_2_5M_MODEL_ASSISTED_MASK"
    ASMAE_5M_GENERALIZED_MASK = "ASMAE_5M_GENERALIZED_MASK"
    ASMAE_EFFECTIVE_RESOLUTION_MAP = "ASMAE_EFFECTIVE_RESOLUTION_MAP"
    ASMAE_ML_AGREEMENT = "ASMAE_ML_AGREEMENT"
    ASMAE_ARCHIVE_SUPPORT = "ASMAE_ARCHIVE_SUPPORT"
    ASMAE_ENKF_SUPPORT = "ASMAE_ENKF_SUPPORT"
    ASMAE_RADIOMETRIC_SUPPORT = "ASMAE_RADIOMETRIC_SUPPORT"
    ASMAE_VISUAL_FUSION_CANOPY = "ASMAE_VISUAL_FUSION_CANOPY"

    # ASMAE Canonical Aliases (V92.4)
    CANOPY_ASMAE_VIGOR = "CANOPY_ASMAE_VIGOR"
    WATER_ASMAE_CANOPY_WATER = "WATER_ASMAE_CANOPY_WATER"
    WATER_ASMAE_ROOT_ZONE_WATER = "WATER_ASMAE_ROOT_ZONE_WATER"
    NUTRIENT_ASMAE_CHLOROPHYLL_PROXY = "NUTRIENT_ASMAE_CHLOROPHYLL_PROXY"
    SALINITY_ASMAE_STRESS = "SALINITY_ASMAE_STRESS"
    RISK_ASMAE_DIAGNOSTIC = "RISK_ASMAE_DIAGNOSTIC"
    CONFIDENCE_ASMAE = "CONFIDENCE_ASMAE"
    RESOLUTION_ASMAE_EFFECTIVE = "RESOLUTION_ASMAE_EFFECTIVE"

    # V92.4-BC.2: Veg Attention ASMAE Aliases
    VEG_ATTENTION_ASMAE_DIAGNOSTIC = "VEG_ATTENTION_ASMAE_DIAGNOSTIC"      # Composite: conflict + disagreement
    VEG_ATTENTION_ASMAE_CONFLICT = "VEG_ATTENTION_ASMAE_CONFLICT"          # Cross-layer conflict alias
    VEG_ATTENTION_ASMAE_DISAGREEMENT = "VEG_ATTENTION_ASMAE_DISAGREEMENT"  # BMA disagreement alias

    # V92.4-BC.10.3: Composite ASMAE & experimental fine detail
    EXPERIMENTAL_TEXTURE_SUPPORT_MASK = "EXPERIMENTAL_TEXTURE_SUPPORT_MASK"
    COMPOSITE_ADVISORY_CANOPY = "COMPOSITE_ADVISORY_CANOPY"
    COMPOSITE_VEG_ATTENTION = "COMPOSITE_VEG_ATTENTION"
    COMPOSITE_WATER_SUPPORT = "COMPOSITE_WATER_SUPPORT"
    COMPOSITE_NUTRIENT_SUPPORT = "COMPOSITE_NUTRIENT_SUPPORT"
    COMPOSITE_SALINITY_STRESS = "COMPOSITE_SALINITY_STRESS"
    COMPOSITE_RISK_DIAGNOSTIC = "COMPOSITE_RISK_DIAGNOSTIC"
    COMPOSITE_CONFIDENCE = "COMPOSITE_CONFIDENCE"
    COMPOSITE_EFFECTIVE_RESOLUTION = "COMPOSITE_EFFECTIVE_RESOLUTION"
    COMPOSITE_UNCERTAINTY = "COMPOSITE_UNCERTAINTY"
    COMPOSITE_BMA_DISAGREEMENT = "COMPOSITE_BMA_DISAGREEMENT"
    COMPOSITE_ARCHIVE_SUPPORT = "COMPOSITE_ARCHIVE_SUPPORT"
    COMPOSITE_RETRO_SCORE = "COMPOSITE_RETRO_SCORE"
    COMPOSITE_ML_SUPPORT = "COMPOSITE_ML_SUPPORT"
    COMPOSITE_TEXTURE_DETAIL = "COMPOSITE_TEXTURE_DETAIL"


# ASMAE Groupings
ASMAE_STATE_SURFACES = {
    SurfaceType.ASMAE_VIGOR,
    SurfaceType.ASMAE_LAI,
    SurfaceType.ASMAE_CHLOROPHYLL,
    SurfaceType.ASMAE_CANOPY_WATER,
    SurfaceType.ASMAE_ROOT_ZONE_WATER,
    SurfaceType.ASMAE_SURFACE_WETNESS_EVENT,
    SurfaceType.ASMAE_STRUCTURE,
    SurfaceType.ASMAE_BARE_SOIL,
    SurfaceType.ASMAE_SALINITY_STRESS,
    SurfaceType.ASMAE_THERMAL_STRESS,
    SurfaceType.ASMAE_BIOTIC_CONFOUNDER_RISK,
}

ASMAE_DIAGNOSTIC_SURFACES = {
    SurfaceType.ASMAE_EFFECTIVE_RESOLUTION,
    SurfaceType.ASMAE_POSTERIOR_CONCENTRATION,
    SurfaceType.ASMAE_UNCERTAINTY,
    SurfaceType.ASMAE_RETROVALIDATION_SCORE,
    SurfaceType.ASMAE_BMA_DISAGREEMENT,
    SurfaceType.ASMAE_CROSS_LAYER_CONFLICT,
    SurfaceType.ASMAE_EXPORT_ELIGIBILITY,
    SurfaceType.ASMAE_1M_ADVISORY_MASK,
    SurfaceType.ASMAE_2_5M_MODEL_ASSISTED_MASK,
    SurfaceType.ASMAE_5M_GENERALIZED_MASK,
    SurfaceType.ASMAE_EFFECTIVE_RESOLUTION_MAP,
    SurfaceType.ASMAE_ML_AGREEMENT,
    SurfaceType.ASMAE_ARCHIVE_SUPPORT,
    SurfaceType.ASMAE_ENKF_SUPPORT,
    SurfaceType.ASMAE_RADIOMETRIC_SUPPORT,
    SurfaceType.ASMAE_VISUAL_FUSION_CANOPY,
    SurfaceType.EXPERIMENTAL_TEXTURE_SUPPORT_MASK,
    SurfaceType.COMPOSITE_ADVISORY_CANOPY,
    SurfaceType.COMPOSITE_VEG_ATTENTION,
    SurfaceType.COMPOSITE_WATER_SUPPORT,
    SurfaceType.COMPOSITE_NUTRIENT_SUPPORT,
    SurfaceType.COMPOSITE_SALINITY_STRESS,
    SurfaceType.COMPOSITE_RISK_DIAGNOSTIC,
    SurfaceType.COMPOSITE_CONFIDENCE,
    SurfaceType.COMPOSITE_EFFECTIVE_RESOLUTION,
    SurfaceType.COMPOSITE_UNCERTAINTY,
    SurfaceType.COMPOSITE_BMA_DISAGREEMENT,
    SurfaceType.COMPOSITE_ARCHIVE_SUPPORT,
    SurfaceType.COMPOSITE_RETRO_SCORE,
    SurfaceType.COMPOSITE_ML_SUPPORT,
    SurfaceType.COMPOSITE_TEXTURE_DETAIL,
}

ASMAE_VISUAL_ONLY_SURFACES = set()  # Dynamically resolved or default empty set


class GroundingClass(str, Enum):
    """How a surface's spatial pattern was derived."""
    RASTER_GROUNDED = "RASTER_GROUNDED"                     # Direct from 4D tensor pixel data (observed_ratio >= 0.90)
    PARTIAL_RASTER_GROUNDED = "PARTIAL_RASTER_GROUNDED"     # Real raster but gap-filled/model-assisted (0.3 <= observed_ratio < 0.90)
    MODEL_ASSISTED_RASTER = "MODEL_ASSISTED_RASTER"         # Spatially driven by raster but with heavy model calibration/interpolation (observed_ratio < 0.3 but has raster_basis)
    ZONE_GROUNDED = "ZONE_GROUNDED"                         # Per-zone values rasterized to grid
    PROXY_SPATIAL = "PROXY_SPATIAL"                         # Field value × NDVI ratio or other proxy (no direct raster basis for this mode)
    UNIFORM = "UNIFORM"                                     # Single value broadcast to all pixels

class ZoneFamily(str, Enum):
    """Zone categorization families — zones within a family must not overlap."""
    AGRONOMIC = "AGRONOMIC"         # low vigor, water stress, nutrient risk, etc.
    STRUCTURAL = "STRUCTURAL"       # crowns, rows, gaps, compaction
    DECISION = "DECISION"           # verify, scout, irrigate, fertilize, spray, blocked
    TRUST = "TRUST"                 # low confidence, stale data, conflicting, interpolated
    MANAGEMENT = "MANAGEMENT"       # data-driven management zones (e.g. K-Means clustering)


class ZoneType(str, Enum):
    """Semantic types for synthesized zones."""
    # Agronomic
    LOW_VIGOR = "LOW_VIGOR"
    WATER_STRESS = "WATER_STRESS"
    NUTRIENT_RISK = "NUTRIENT_RISK"
    SALINITY_RISK = "SALINITY_RISK"
    DISEASE_RISK = "DISEASE_RISK"
    YIELD_GAP = "YIELD_GAP"
    HIGH_VIGOR = "HIGH_VIGOR"
    # Structural
    CANOPY = "CANOPY"
    GAP = "GAP"
    ROW_SEGMENT = "ROW_SEGMENT"
    # Decision
    SCOUT_ZONE = "SCOUT_ZONE"
    IRRIGATE_ZONE = "IRRIGATE_ZONE"
    FERTILIZE_ZONE = "FERTILIZE_ZONE"
    SPRAY_ZONE = "SPRAY_ZONE"
    BLOCKED_ZONE = "BLOCKED_ZONE"
    WAIT_ZONE = "WAIT_ZONE"
    # Trust
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    STALE_DATA = "STALE_DATA"
    HIGH_CONFLICT = "HIGH_CONFLICT"


class ObjectType(str, Enum):
    """Structural micro-object types."""
    CROWN = "CROWN"
    ROW_SEGMENT = "ROW_SEGMENT"
    GAP_CLUSTER = "GAP_CLUSTER"
    CANOPY_PATCH = "CANOPY_PATCH"


class RenderMode(str, Enum):
    """Named rendering modes for the frontend map."""
    TRUE_COLOR = "TRUE_COLOR"
    VIGOR = "VIGOR"
    WATER_STRESS = "WATER_STRESS"
    NUTRIENT = "NUTRIENT"
    DISEASE = "DISEASE"
    YIELD = "YIELD"
    SUITABILITY = "SUITABILITY"
    RISK = "RISK"
    UNCERTAINTY = "UNCERTAINTY"
    SOURCE_DOMINANCE = "SOURCE_DOMINANCE"
    DECISION_HALO = "DECISION_HALO"
    CONFIDENCE_FOG = "CONFIDENCE_FOG"
    CAUSAL_LENS = "CAUSAL_LENS"
    TIME_PEEL = "TIME_PEEL"
    PLANT_NEAR = "PLANT_NEAR"
    SALINITY = "SALINITY"                 # Soil salinity heatmap
    EXECUTION = "EXECUTION"               # L6/L8 execution overlay
    TEMPORAL_DELTA = "TEMPORAL_DELTA"     # 14-day temporal change
    FORECAST = "FORECAST"                 # 7-day forecast overlay
    SOIL_CARBON = "SOIL_CARBON"
    SOIL_COMPACTION = "SOIL_COMPACTION"
    THERMAL_STRESS = "THERMAL_STRESS"
    N_LOSS = "N_LOSS"

    # ASMAE Render Modes (V82)
    ASMAE_VIGOR = "ASMAE_VIGOR"
    ASMAE_LAI = "ASMAE_LAI"
    ASMAE_CHLOROPHYLL = "ASMAE_CHLOROPHYLL"
    ASMAE_CANOPY_WATER = "ASMAE_CANOPY_WATER"
    ASMAE_ROOT_ZONE_WATER = "ASMAE_ROOT_ZONE_WATER"
    ASMAE_SURFACE_WETNESS_EVENT = "ASMAE_SURFACE_WETNESS_EVENT"
    ASMAE_STRUCTURE = "ASMAE_STRUCTURE"
    ASMAE_BARE_SOIL = "ASMAE_BARE_SOIL"
    ASMAE_SALINITY_STRESS = "ASMAE_SALINITY_STRESS"
    ASMAE_THERMAL_STRESS = "ASMAE_THERMAL_STRESS"
    ASMAE_BIOTIC_CONFOUNDER_RISK = "ASMAE_BIOTIC_CONFOUNDER_RISK"
    ASMAE_EFFECTIVE_RESOLUTION = "ASMAE_EFFECTIVE_RESOLUTION"
    ASMAE_POSTERIOR_CONCENTRATION = "ASMAE_POSTERIOR_CONCENTRATION"
    ASMAE_CONFIDENCE = "ASMAE_CONFIDENCE"
    ASMAE_UNCERTAINTY = "ASMAE_UNCERTAINTY"
    ASMAE_RETROVALIDATION_SCORE = "ASMAE_RETROVALIDATION_SCORE"
    ASMAE_BMA_DISAGREEMENT = "ASMAE_BMA_DISAGREEMENT"
    ASMAE_CROSS_LAYER_CONFLICT = "ASMAE_CROSS_LAYER_CONFLICT"
    ASMAE_EXPORT_ELIGIBILITY = "ASMAE_EXPORT_ELIGIBILITY"

    # ASMAE Canonical Aliases (V92.4)
    CANOPY_ASMAE_VIGOR = "CANOPY_ASMAE_VIGOR"
    WATER_ASMAE_CANOPY_WATER = "WATER_ASMAE_CANOPY_WATER"
    WATER_ASMAE_ROOT_ZONE_WATER = "WATER_ASMAE_ROOT_ZONE_WATER"
    NUTRIENT_ASMAE_CHLOROPHYLL_PROXY = "NUTRIENT_ASMAE_CHLOROPHYLL_PROXY"
    SALINITY_ASMAE_STRESS = "SALINITY_ASMAE_STRESS"
    RISK_ASMAE_DIAGNOSTIC = "RISK_ASMAE_DIAGNOSTIC"
    CONFIDENCE_ASMAE = "CONFIDENCE_ASMAE"
    RESOLUTION_ASMAE_EFFECTIVE = "RESOLUTION_ASMAE_EFFECTIVE"

    # V92.4-BC.2: Veg Attention ASMAE Aliases (temporary RenderMode mirroring for compat)
    VEG_ATTENTION_ASMAE_DIAGNOSTIC = "VEG_ATTENTION_ASMAE_DIAGNOSTIC"
    VEG_ATTENTION_ASMAE_CONFLICT = "VEG_ATTENTION_ASMAE_CONFLICT"
    VEG_ATTENTION_ASMAE_DISAGREEMENT = "VEG_ATTENTION_ASMAE_DISAGREEMENT"

    # V92.4-BC.10.3: Composite ASMAE & experimental fine detail
    EXPERIMENTAL_TEXTURE_SUPPORT_MASK = "EXPERIMENTAL_TEXTURE_SUPPORT_MASK"
    COMPOSITE_ADVISORY_CANOPY = "COMPOSITE_ADVISORY_CANOPY"
    COMPOSITE_VEG_ATTENTION = "COMPOSITE_VEG_ATTENTION"
    COMPOSITE_WATER_SUPPORT = "COMPOSITE_WATER_SUPPORT"
    COMPOSITE_NUTRIENT_SUPPORT = "COMPOSITE_NUTRIENT_SUPPORT"
    COMPOSITE_SALINITY_STRESS = "COMPOSITE_SALINITY_STRESS"
    COMPOSITE_RISK_DIAGNOSTIC = "COMPOSITE_RISK_DIAGNOSTIC"
    COMPOSITE_CONFIDENCE = "COMPOSITE_CONFIDENCE"
    COMPOSITE_EFFECTIVE_RESOLUTION = "COMPOSITE_EFFECTIVE_RESOLUTION"
    COMPOSITE_UNCERTAINTY = "COMPOSITE_UNCERTAINTY"
    COMPOSITE_BMA_DISAGREEMENT = "COMPOSITE_BMA_DISAGREEMENT"
    COMPOSITE_ARCHIVE_SUPPORT = "COMPOSITE_ARCHIVE_SUPPORT"
    COMPOSITE_RETRO_SCORE = "COMPOSITE_RETRO_SCORE"
    COMPOSITE_ML_SUPPORT = "COMPOSITE_ML_SUPPORT"
    COMPOSITE_TEXTURE_DETAIL = "COMPOSITE_TEXTURE_DETAIL"


class PaletteId(str, Enum):
    """Named color palette references."""
    VIGOR_GREEN = "VIGOR_GREEN"
    STRESS_RED = "STRESS_RED"
    UNCERTAINTY_GRAY = "UNCERTAINTY_GRAY"
    RISK_HEAT = "RISK_HEAT"
    DISEASE_ORANGE = "DISEASE_ORANGE"
    NUTRIENT_YELLOW = "NUTRIENT_YELLOW"
    YIELD_BLUE = "YIELD_BLUE"
    SOURCE_SPECTRAL = "SOURCE_SPECTRAL"
    DECISION_CATEGORICAL = "DECISION_CATEGORICAL"
    SALINITY_TEAL = "SALINITY_TEAL"                   # Teal → Cyan → Red salinity ramp
    RAW_GRAYSCALE = "RAW_GRAYSCALE"
    CARBON_BROWN = "CARBON_BROWN"
    COMPACTION_PURPLE = "COMPACTION_PURPLE"
    THERMAL_ORANGE = "THERMAL_ORANGE"
    STRESS_WATER = "STRESS_WATER"
    RESOLUTION_CATEGORICAL = "resolution_categorical"
    EXPERIMENTAL_FINE_DETAIL = "experimental_fine_detail"


class SIREDegradation(str, Enum):
    """Layer 10 degradation modes."""
    NORMAL = "NORMAL"
    NO_SPATIAL = "NO_SPATIAL"           # No grid_spec available
    L1_ONLY = "L1_ONLY"                 # Only L1/L2 data, no downstream layers
    NO_DOWNSTREAM = "NO_DOWNSTREAM"     # Missing L3-L8 → surfaces limited
    LOW_RESOLUTION = "LOW_RESOLUTION"   # Resolution too coarse for structural detail
    DATA_GAP = "DATA_GAP"               # Insufficient data for reliable surfaces
    DEGRADED = "DEGRADED"               # Post-invariant quality or materialization failure
    ASMAE_SURFACE_MATERIALIZATION_FAILED = "ASMAE_SURFACE_MATERIALIZATION_FAILED"


# ============================================================================
# SURFACE ARTIFACTS
# ============================================================================

@dataclass
class SurfaceArtifact:
    """
    A single continuous spatial surface aligned to the field grid.

    Invariants:
      - len(values) == grid_height and len(values[0]) == grid_width
      - All values within render_range (if set)
      - confidence same shape as values
      - source_weights values sum to ~1.0 per pixel
    """
    surface_id: str                         # e.g. "NDVI_CLEAN_2025-06-30"
    semantic_type: SurfaceType
    grid_ref: str                           # Reference to the SpatialGridSpec used

    # 2D raster [H][W] — None means masked/nodata
    values: List[List[Optional[float]]]
    units: str                              # e.g. "index", "probability", "kg/ha", "mm"
    native_resolution_m: float              # Source resolution in meters

    # Display range for normalization
    render_range: Tuple[float, float] = (0.0, 1.0)
    palette_id: PaletteId = PaletteId.RAW_GRAYSCALE

    # Confidence surface [H][W] — same shape
    confidence: Optional[List[List[Optional[float]]]] = None

    # Source dominance weights [H][W] → Dict per pixel
    source_weights: Optional[List[List[Optional[Dict[str, float]]]]] = None

    # Provenance
    time_window: Dict[str, str] = field(default_factory=dict)   # {start, end}
    source_layers: List[str] = field(default_factory=list)       # ["L1", "L2", "L3"]
    provenance: Dict[str, Any] = field(default_factory=dict)

    # Grounding classification — what strategy produced this surface's spatial pattern
    grounding_class: Optional[str] = None  # GroundingClass value or None
    raster_basis: List[str] = field(default_factory=list)
    observed_ratio: float = 0.0

    # V92.4 GIS specifications & STAC reference points
    grid_spec: Optional[Dict[str, Any]] = None
    source_grid_spec: Optional[Dict[str, Any]] = None
    display_grid_spec: Optional[Dict[str, Any]] = None
    raster_ref: Optional[str] = None
    cog_ref: Optional[str] = None
    tile_ref: Optional[str] = None
    stac_item_ref: Optional[str] = None


# ============================================================================
# ZONE ARTIFACTS
# ============================================================================

@dataclass
class ZoneArtifact:
    """
    A map-ready zone with evidence, confidence, and action linkage.

    Every zone must answer:
      - what is it
      - how severe is it
      - how sure are we
      - what supports it
      - what action follows
    """
    zone_id: str
    zone_type: ZoneType
    zone_family: ZoneFamily

    # Geometry — bounding box + cell mask indices
    bbox: Tuple[float, float, float, float]     # (min_y, min_x, max_y, max_x) in grid coords
    cell_indices: List[Tuple[int, int]]          # [(row, col), ...] grid cells in this zone
    area_m2: float
    area_pct: float                              # fraction of field

    # Assessment
    severity: float                              # 0.0 – 1.0
    confidence: float                            # 0.0 – 1.0
    top_drivers: List[str]                       # What caused this zone to exist
    source_surface_type: str = ""                 # The surface that owns this zone (canonical ownership)
    description: str = ""

    # Linkage to upstream evidence
    linked_findings: List[Dict[str, Any]] = field(default_factory=list)

    # Linkage to L8 actions
    linked_actions: List[str] = field(default_factory=list)      # action_ids from L8

    # Stats summary
    surface_stats: Dict[str, Dict[str, float]] = field(default_factory=dict)
    # e.g. {"NDVI_CLEAN": {"mean": 0.4, "p10": 0.3, "p90": 0.5}}

    time_window: Dict[str, str] = field(default_factory=dict)
    uncertainty_summary: Dict[str, float] = field(default_factory=dict)

    # Human-readable spatial label (WS5 – populated by labeler.py)
    label: str = ""

    # Confidence scoring reasons (WS9 – populated by extractor.py)
    confidence_reasons: List[str] = field(default_factory=list)

    observed_cell_share: float = 0.0
    gap_filled_share: float = 0.0
    grid_validity: str = "unknown"
    authority: str = "algorithmic_scouting_region"
    confidence_basis: List[str] = field(default_factory=list)
    # A non-empty value means the cell-index geometry is not authorized for
    # geographic materialization.  Serializers must omit those cell indices.
    authority_block_reason: Optional[str] = None


# ============================================================================
# MICRO-OBJECT ARTIFACTS
# ============================================================================

@dataclass
class MicroObjectArtifact:
    """
    Plant-near / object-near structural detection.

    Only produced when source resolution allows it.
    """
    object_id: str
    object_type: ObjectType

    # Geometry — centroid + cell indices
    centroid: Tuple[float, float]                # (row, col) in grid coords
    cell_indices: List[Tuple[int, int]]
    area_m2: float

    # Assessment
    score: float                                 # Detection confidence
    confidence: float

    # Derived measurements
    measurements: Dict[str, float] = field(default_factory=dict)
    # e.g. {"diameter_m": 3.5, "height_proxy": 0.8, "vigor_index": 0.65}

    derived_from: str = ""                       # e.g. "NDVI_10m + RGB_1m"


# ============================================================================
# HISTOGRAM ARTIFACTS
# ============================================================================

@dataclass
class HistogramArtifact:
    """Single histogram for a surface over a spatial region."""
    surface_type: SurfaceType
    region_id: str                               # "field" or zone_id
    bin_edges: List[float]
    bin_counts: List[int]
    total_pixels: int
    valid_pixels: int

    # Quantile stats
    mean: float = 0.0
    median: float = 0.0
    std: float = 0.0
    p10: float = 0.0
    p90: float = 0.0
    skewness: float = 0.0

    # Optional: bimodality flag
    is_bimodal: bool = False
    bimodal_threshold: Optional[float] = None


@dataclass
class DeltaHistogram:
    """Change histogram between two time steps."""
    surface_type: SurfaceType
    region_id: str
    date_from: str
    date_to: str
    bin_edges: List[float]
    bin_counts: List[int]
    mean_change: float = 0.0
    shift_direction: str = "STABLE"              # "IMPROVING", "DEGRADING", "STABLE"


@dataclass
class HistogramBundle:
    """Complete histogram analytics for a Layer 10 run."""
    field_histograms: List[HistogramArtifact] = field(default_factory=list)
    zone_histograms: List[HistogramArtifact] = field(default_factory=list)
    delta_histograms: List[DeltaHistogram] = field(default_factory=list)
    uncertainty_histograms: List[HistogramArtifact] = field(default_factory=list)
    source_histograms: List[HistogramArtifact] = field(default_factory=list)


# ============================================================================
# RENDER MANIFEST
# ============================================================================

@dataclass
class LegendEntry:
    """One entry in a map legend."""
    label: str
    color: str                                   # hex color #RRGGBB
    value_range: Optional[Tuple[float, float]] = None


@dataclass
class MapModeDef:
    """Definition of a renderable map mode."""
    mode: RenderMode
    display_name: str
    surface_ids: List[str]                       # Which surfaces to composite
    palette_id: PaletteId
    legend: List[LegendEntry] = field(default_factory=list)
    requires_resolution_m: Optional[float] = None  # e.g. PLANT_NEAR requires <5m
    enabled: bool = True
    description: str = ""


@dataclass
class RenderManifest:
    """Frontend-consumable manifest of available map modes and styles."""
    available_modes: List[MapModeDef]
    active_mode: RenderMode = RenderMode.VIGOR
    style_pack: str = "AGRO_POP"
    show_confidence_fog: bool = False
    show_zone_boundaries: bool = True


@dataclass
class ComponentFailure:
    code: str
    component: str
    stage: str
    message: str
    fallback_used: bool = False
    affected_surface_types: List[str] = field(default_factory=list)


# ============================================================================
# QUALITY & PROVENANCE
# ============================================================================

@dataclass
class QualityReport:
    """Layer 10 quality metrics."""
    degradation_mode: SIREDegradation
    reliability_score: float                     # 0.0 – 1.0
    surfaces_generated: int
    surfaces_skipped: int
    zones_generated: int
    micro_objects_detected: int
    grid_alignment_ok: bool
    detail_conservation_ok: bool
    zone_state_by_surface: Dict[str, str] = field(default_factory=dict)
    missing_upstream: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    component_failures: List[ComponentFailure] = field(default_factory=list)
    degradation_codes: List[str] = field(default_factory=list)


# ============================================================================
# EXPLAINABILITY CONTRACT (Phase B)
# ============================================================================

@dataclass
class DriverWeight:
    name: str
    value: float
    role: str = "neutral"  # "positive", "negative", "uncertainty", "neutral"
    description: str = ""
    formatted_value: str = ""

@dataclass
class ModelEquation:
    label: str
    expression: str
    plain_language: str

@dataclass
class ExplainabilityProvenance:
    sources: List[str]
    timestamps: List[str]
    model_version: str
    run_id: str
    degraded_reasons: List[str]

@dataclass
class ConfidencePenalty:
    reason: str
    impact: float

@dataclass
class ExplainabilityConfidence:
    score: float
    penalties: List[ConfidencePenalty]
    quality_scored_layers: List[str]

@dataclass
class ExplainabilityPack:
    summary: str
    top_drivers: List[DriverWeight]
    equations: List[ModelEquation]
    charts: Dict[str, Any]  # Flex structure for UI chart binding
    provenance: ExplainabilityProvenance
    confidence: ExplainabilityConfidence
    dominant_driver: Optional[str] = None
    evidence: List[str] = field(default_factory=list)
    recommended_action: Optional[str] = None
    driver_confidence: Optional[float] = None
    action_level: Optional[str] = None


# ============================================================================
# TEMPORAL INTELLIGENCE (14-day window: T-7 → T+7)
# ============================================================================

@dataclass
class TemporalSlice:
    """A single time-step spatial snapshot for the temporal bundle."""
    date: str                                        # ISO date string
    day_offset: int                                  # -7 to +7 relative to T₀
    surface_type: SurfaceType
    values: List[List[Optional[float]]]              # [H][W] raster grid
    is_forecast: bool = False                        # True for T+1 to T+7
    confidence: float = 1.0                          # Degrades for forecast
    source: str = ""                                 # e.g. "L1_TENSOR", "L2_CURVE", "FORECAST_API"


@dataclass
class TemporalBundle:
    """Full 14-day temporal context for time-peel mode (T-7 retrospective + T+7 forecast)."""
    slices: List[TemporalSlice] = field(default_factory=list)
    reference_date: str = ""                         # T₀ date
    lookback_days: int = 7
    lookahead_days: int = 7
    trend_summary: Dict[str, str] = field(default_factory=dict)
    # e.g. {"NDVI": "IMPROVING", "WATER_STRESS": "WORSENING", "RISK": "STABLE"}
    temporal_quality: float = 1.0                    # Degrades if fewer real observations
    forecast_source: str = ""                        # "L7_PLANNING", "WEATHER_API", "EXTRAPOLATION"

@dataclass
class ForecastContext:
    """Advanced weather + agronomic forecast for 7-day look-ahead."""
    # Weather forecast (daily for T+1 to T+7)
    precipitation_forecast: List[float] = field(default_factory=list)  # mm/day
    temperature_max_forecast: List[float] = field(default_factory=list)  # °C
    temperature_min_forecast: List[float] = field(default_factory=list)  # °C
    humidity_forecast: List[float] = field(default_factory=list)  # % RH
    wind_speed_forecast: List[float] = field(default_factory=list)  # m/s
    evapotranspiration_forecast: List[float] = field(default_factory=list)  # mm/day
    # Risk indices
    frost_risk_days: List[bool] = field(default_factory=list)
    heat_stress_days: List[bool] = field(default_factory=list)
    leaf_wetness_hours_forecast: List[float] = field(default_factory=list)
    # Source metadata
    forecast_source: str = "ECMWF_ERA5"              # or "OPEN_METEO", "GFS"
    forecast_issued_at: str = ""                     # ISO timestamp
    forecast_confidence: float = 0.7                 # Degrades with horizon
    completeness_status: str = "complete"
    missing_variables: List[str] = field(default_factory=list)


# ============================================================================
# I/O
# ============================================================================

@dataclass(kw_only=True)
class Layer10Input:
    """
    Unified input to SIRE from L1-L9.

    Required: plot_namespace (PlotNamespace), field_tensor (L1), veg_int (L2)
    Optional: everything else - L10 degrades gracefully
    """
    plot_namespace: Optional[PlotNamespace] = None
    plot_id: str = ""
    tenant_id: str = ""
    farm_id: str = ""
    field_tensor: Any = None                     # FieldTensor from L1
    veg_int: Any = None                          # VegIntOutput from L2
    decision: Optional[Any] = None               # L3 Layer3Output
    nutrients: Optional[Any] = None              # L4 Layer4Output
    bio: Optional[Any] = None                    # L5 Layer5Output
    crop: str = ""                               # Missing stays missing; no scientific default
    exec_state: Any = None                       # L6 Layer6Output
    planning: Any = None                         # L7 Layer7Output
    prescriptive: Any = None                     # L8 Layer8Output
    interface: Any = None                        # L9 InterfaceOutput

    def __post_init__(self):

        if not self.plot_namespace or not isinstance(self.plot_namespace, PlotNamespace):
            t_id = str(self.tenant_id or "").strip()
            f_id = str(self.farm_id or "").strip()
            p_id = str(self.plot_id or "").strip()
            if t_id and f_id and p_id:
                object.__setattr__(self, "plot_namespace", PlotNamespace(
                    tenant_id=t_id,
                    farm_id=f_id,
                    plot_id=p_id,
                ))

        if not self.plot_namespace or not isinstance(self.plot_namespace, PlotNamespace) or not self.plot_namespace.is_valid():
            raise ValueError(f"Layer10Input requires valid non-empty PlotNamespace: {self.plot_namespace}")

        object.__setattr__(self, "tenant_id", self.plot_namespace.tenant_id)
        object.__setattr__(self, "farm_id", self.plot_namespace.farm_id)
        object.__setattr__(self, "plot_id", self.plot_namespace.plot_id)


    # Explicit Geometry Context
    field_geometry: Optional[Dict[str, Any]] = None
    canonical_geometry_hash: Optional[str] = None
    source_geometry_hash: Optional[str] = None

    # Temporal context (14-day window: T-7 -> T+7)
    temporal_window: Optional[Dict[str, Any]] = None
    forecast_context: Optional[Any] = None
    reference_date: str = ""

    # Configuration & Provenance
    render_profile: str = "AGRO_POP"
    requested_modes: List[str] = field(default_factory=lambda: ["VIGOR"])
    grid_height: int = 10
    grid_width: int = 10
    resolution_m: float = 10.0
    visual_intensity: Optional[float] = 0.40
    user_mode: Optional[str] = "farmer"
    run_id: str = ""
    timestamp: str = ""
    ground_truth_context: Dict[str, Any] = field(default_factory=dict)
    visual_config: Optional[Any] = None
    source_policy: Optional[str] = None
    asmae_proof: Dict[str, Any] = field(default_factory=dict)
    raster_composites: Optional[Dict[str, Any]] = None



@dataclass
class Layer10Output:
    """
    Full Layer 10 output - map-native intelligence products.
    """
    run_id: str = ""
    # ``run_id`` is the immutable scientific identity. A cache consumer's
    # request is recorded separately and must never relabel the publication.
    publication_run_id: str = ""
    request_run_id: str = ""
    publication_id: str = ""
    publication_status: str = "INVALID_PUBLICATION"
    surface_inventory_hash: str = ""
    surface_schema_version: str = ""
    timestamp: str = ""
    input_run_ids: Optional[Dict[str, Any]] = field(default_factory=dict)

    # Core products
    surface_pack: List[SurfaceArtifact] = field(default_factory=list)
    zone_pack: List[ZoneArtifact] = field(default_factory=list)
    micro_objects: List[MicroObjectArtifact] = field(default_factory=list)
    histogram_bundle: HistogramBundle = field(default_factory=HistogramBundle)

    # Frontend artifacts
    render_manifest: RenderManifest = field(default_factory=lambda: RenderManifest(
        available_modes=[]
    ))
    quicklooks: Dict[str, str] = field(default_factory=dict)

    # BC.10.21: Explicit Geometry Context
    field_geometry: Optional[Dict[str, Any]] = None
    canonical_geometry_hash: Optional[str] = None
    source_geometry_hash: Optional[str] = None

    # Export packs (populated when export is wired)
    raster_pack: List[Dict[str, Any]] = field(default_factory=list)
    vector_pack: List[Dict[str, Any]] = field(default_factory=list)
    tile_manifest: Dict[str, Any] = field(default_factory=dict)

    # Quality & provenance
    quality_report: QualityReport = field(default_factory=lambda: QualityReport(
        degradation_mode=SIREDegradation.NORMAL,
        reliability_score=1.0,
        surfaces_generated=0,
        surfaces_skipped=0,
        zones_generated=0,
        micro_objects_detected=0,
        grid_alignment_ok=True,
        detail_conservation_ok=True,
    ))
    provenance: Dict[str, Any] = field(default_factory=dict)
    # Canonical authority; clients must not consume raw L2 stage_by_day values.
    resolved_crop_stage: str = "UNKNOWN"
    phenology_context: Dict[str, Any] = field(default_factory=dict)

    # Phase B OS Contracts
    explainability_pack: Dict[str, ExplainabilityPack] = field(default_factory=dict)

    # Temporal Intelligence (14-day: T-7 → T+7)
    temporal_bundle: TemporalBundle = field(default_factory=TemporalBundle)

    # Scenario & History Packs (Phase C)
    scenario_pack: List[Dict[str, Any]] = field(default_factory=list)
    history_pack: List[Dict[str, Any]] = field(default_factory=list)

    # V60B: Ground Truth Registry Summary (pass-through from upstream)
    # Contains: resolution_percentages, drone_3cm, certification_decision, evidence_sources
    ground_truth_summary: Dict[str, Any] = field(default_factory=dict)

    # V61D: Latest Free Visual Basemap Provider metadata for map background
    visual_source: Dict[str, Any] = field(default_factory=dict)

    # V92.4 Mode Completeness and inventory structures
    surface_inventory: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    mode_surface_plan: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # V92.4-BC: Backend-authoritative display state per mode
    # Each key is a mode name, value is ModeDisplayState dict
    mode_display_state: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # V92.4-BC.8.1: Source policy display state
    source_policy_display_state: Dict[str, Any] = field(default_factory=dict)

    # V92.4-BC.9.1: Evidence State
    asmae_evidence_state: Dict[str, Any] = field(default_factory=dict)
    # Immutable scientific truth received from ASMAE.  Surface selection or a
    # display fallback may never rewrite this envelope.
    core_asmae_evidence_state: Dict[str, Any] = field(default_factory=dict)
    # Separate publication/display facts for the currently emitted inventory.
    publication_surface_state: Dict[str, Any] = field(default_factory=dict)
    publication_demotion: Dict[str, Any] = field(default_factory=dict)
    asmae_feature_pack: Dict[str, Any] = field(default_factory=dict)
    # Canonical card-only plot posterior. This is independent of raster
    # availability and must never be materialized as a surface.
    asmae_plot_state_artifact: Dict[str, Any] = field(default_factory=dict)

    # V92.4-BC.12: true spatial behavior lock fields
    surface_behavior_proof: Dict[str, Any] = field(default_factory=dict)
    display_trace: Dict[str, Any] = field(default_factory=dict)
    asmae_proof: Dict[str, Any] = field(default_factory=dict)
    render_authorizations: Dict[str, Any] = field(default_factory=dict)
    render_authorization_version: str = RENDER_AUTHORIZATION_VERSION

