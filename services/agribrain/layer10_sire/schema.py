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
from enum import Enum


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

    # Nutrients
    NUTRIENT_STRESS_PROB = "NUTRIENT_STRESS_PROB"
    N_RESPONSE_POTENTIAL = "N_RESPONSE_POTENTIAL"
    FERTILITY_LIMITATION = "FERTILITY_LIMITATION"

    # Disease / Bio
    BIOTIC_PRESSURE = "BIOTIC_PRESSURE"
    SPREAD_LIKELIHOOD = "SPREAD_LIKELIHOOD"
    WEATHER_PRESSURE = "WEATHER_PRESSURE"

    # Yield
    YIELD_P50 = "YIELD_P50"
    YIELD_P10 = "YIELD_P10"
    YIELD_P90 = "YIELD_P90"
    YIELD_GAP = "YIELD_GAP"
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


class GroundingClass(str, Enum):
    """How a surface's spatial pattern was derived."""
    RASTER_GROUNDED = "RASTER_GROUNDED"   # Direct from 4D tensor pixel data
    ZONE_GROUNDED = "ZONE_GROUNDED"       # Per-zone values rasterized to grid
    PROXY_SPATIAL = "PROXY_SPATIAL"       # Field value × NDVI ratio or other proxy
    UNIFORM = "UNIFORM"                   # Single value broadcast to all pixels

class ZoneFamily(str, Enum):
    """Zone categorization families — zones within a family must not overlap."""
    AGRONOMIC = "AGRONOMIC"         # low vigor, water stress, nutrient risk, etc.
    STRUCTURAL = "STRUCTURAL"       # crowns, rows, gaps, compaction
    DECISION = "DECISION"           # verify, scout, irrigate, fertilize, spray, blocked
    TRUST = "TRUST"                 # low confidence, stale data, conflicting, interpolated


class ZoneType(str, Enum):
    """Semantic types for synthesized zones."""
    # Agronomic
    LOW_VIGOR = "LOW_VIGOR"
    WATER_STRESS = "WATER_STRESS"
    NUTRIENT_RISK = "NUTRIENT_RISK"
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
    EXECUTION = "EXECUTION"               # L6/L8 execution overlay
    TEMPORAL_DELTA = "TEMPORAL_DELTA"     # 14-day temporal change
    FORECAST = "FORECAST"                 # 7-day forecast overlay


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
    RAW_GRAYSCALE = "RAW_GRAYSCALE"


class SIREDegradation(str, Enum):
    """Layer 10 degradation modes."""
    NORMAL = "NORMAL"
    NO_SPATIAL = "NO_SPATIAL"           # No grid_spec available
    L1_ONLY = "L1_ONLY"                 # Only L1/L2 data, no downstream layers
    NO_DOWNSTREAM = "NO_DOWNSTREAM"     # Missing L3-L8 → surfaces limited
    LOW_RESOLUTION = "LOW_RESOLUTION"   # Resolution too coarse for structural detail
    DATA_GAP = "DATA_GAP"               # Insufficient data for reliable surfaces


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


# ============================================================================
# I/O
# ============================================================================

@dataclass
class Layer10Input:
    """
    Unified input to SIRE from L1–L9.

    Required: field_tensor (L1), veg_int (L2)
    Optional: everything else — L10 degrades gracefully
    """
    # Required
    field_tensor: Any                            # FieldTensor from L1
    veg_int: Any                                 # VegIntOutput from L2

    # Optional upstream layers
    spatial_tensor: Any = None                   # SpatialTensor (if available)
    decision: Any = None                         # L3 DecisionOutput
    nutrients: Any = None                        # L4 NutrientIntelligenceOutput
    bio: Any = None                              # L5 BioThreatIntelligenceOutput
    exec_state: Any = None                       # L6 Layer6Output
    planning: Any = None                         # L7 Layer7Output
    prescriptive: Any = None                     # L8 Layer8Output
    interface: Any = None                        # L9 InterfaceOutput

    # Temporal context (14-day window: T-7 → T+7)
    temporal_window: Optional[Dict[str, Any]] = None    # Historical context
    forecast_context: Optional[Any] = None              # ForecastContext or dict
    reference_date: str = ""                            # T₀ anchor date (ISO)

    # Scene references (for imagery compositing)
    scene_refs: Dict[str, Any] = field(default_factory=dict)

    # Configuration
    render_profile: str = "AGRO_POP"             # Style pack name
    requested_modes: List[str] = field(default_factory=lambda: ["VIGOR"])
    grid_height: int = 10
    grid_width: int = 10
    resolution_m: float = 10.0

    # Provenance
    plot_id: str = ""
    run_id_prefix: str = "L10"


@dataclass
class Layer10Output:
    """
    Full Layer 10 output — map-native intelligence products.

    Invariants:
      - All surfaces aligned to grid_height × grid_width
      - run_id is unique and deterministic for same inputs
      - Every zone in zone_pack has evidence and confidence
    """
    run_id: str
    timestamp: str

    # Input lineage
    input_run_ids: Dict[str, str] = field(default_factory=dict)

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

    # Phase B OS Contracts
    explainability_pack: Dict[str, ExplainabilityPack] = field(default_factory=dict)

    # Temporal Intelligence (14-day: T-7 → T+7)
    temporal_bundle: TemporalBundle = field(default_factory=TemporalBundle)

    # Scenario & History Packs (Phase C)
    scenario_pack: List[Dict[str, Any]] = field(default_factory=list)
    history_pack: List[Dict[str, Any]] = field(default_factory=list)
