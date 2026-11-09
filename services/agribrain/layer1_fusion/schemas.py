"""
Layer 1 Fusion Context Engine V1 — Canonical Schemas.

All contracts for input, evidence, fusion output, and downstream payloads.
This is the ONLY canonical schema file. schema_legacy.py provides backward
compatibility for FieldTensor consumers.

Contract version: 1.0.0
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Tuple


# ============================================================================
# Canonical constants
# ============================================================================

SOURCE_FAMILIES = (
    "sentinel2",
    "sentinel1",
    "sentinel5p",
    "eo_foundation",
    "environment",
    "weather_forecast",
    "geo_context",
    "sensor",
    "perception",
    "user_event",
    "history",
    "drone_structural",
    "l0_state",
    "raster_composite",    # Pixel-level raster evidence from orchestrator
    "zone_segmentation",   # Engine-derived zone evidence from quantile segmentation
    "microzone",           # Engine-derived high-res microzone deconvolution/baseline evidence
    "asmae",
)

CORE_SOURCE_FAMILIES = {
    "sentinel2",
    "sentinel1",
    "environment",
    "geo_context",
}

OPTIONAL_SOURCE_FAMILIES = {
    "sensor",
    "user_event",
    "perception",
    "weather_forecast",
    "drone_structural",
    "history",
}

DATA_STATUSES = (
    "observed",
    "estimated",
    "interpolated",
    "assimilated",
    "fallback",
    "simulated",
    "unavailable",
    "reconstruction",
)

DATA_STATUS_CEILING = {
    "observed": 1.0,
    "estimated": 0.75,
    "interpolated": 0.65,
    "assimilated": 0.80,
    "reconstruction": 0.50,
    "fallback": 0.35,
    "simulated": 0.20,
    "unavailable": 0.05,
}

OBSERVATION_TYPES = (
    "measurement",
    "model_estimate",
    "forecast",
    "static_prior",
    "derived_feature",
    "diagnostic",
    "event",
    "state_estimate",
    "derived",              # Engine-derived observations (zone segmentation, composites)
)

SPATIAL_SCOPES = (
    "plot",
    "zone",
    "edge",
    "point",
    "irrigation_block",
    "raster",
    "farm",
)

# ASCII-safe canonical internal units (display names are separate)
CANONICAL_UNITS = {
    "degC", "fraction", "percent", "mm", "mm_day", "m_s", "kPa",
    "dS_m", "pH", "kg_ha", "W_m2", "umol_m2_s", "dBm", "dB",
    "m2", "m", "cm", "L", "L_min", "deg", "min", "bar", "V",
    "mm_h", "ratio", "score", "index", "count", "bool", "class",
    "linear_power", "db",
}

# ── Agronomic Vocabulary Boundary ────────────────────────────────────────────
#
# Layer 1 describes CONTEXT — what the sensors observe.
# Layer 2+ performs DIAGNOSIS — what it means agronomically.
#
# Boundary example:
#   L1 says: "NDVI=0.28, chlorophyll_index=0.15, confidence=0.7"
#   L2 says: "nitrogen deficiency likely (72% probability)"
#
# Each category maps to a specific analytical domain that requires
# specialized models, calibration data, or expert interpretation
# beyond sensor fusion.
#
FORBIDDEN_VOCABULARY = {
    # Nutrient diagnosis — requires tissue analysis, soil lab results,
    # or calibrated crop nutrition models (QUEFTS, DSSAT-N)
    "nutrient_diagnosis": frozenset({
        "nitrogen deficiency", "phosphorus deficiency", "potassium deficiency",
        "nutrient prescription", "micronutrient deficit",
        "sulfur deficiency", "zinc deficiency", "boron toxicity",
    }),
    # Pathology diagnosis — requires field scouting, validated CNN/ViT
    # classifiers, or epidemiological models (e.g., EPIRICE, STEMRUST)
    "pathology_diagnosis": frozenset({
        "fungal disease", "bacterial disease", "viral disease",
        "disease diagnosis", "blight", "rust", "wilt",
        "fusarium", "septoria", "anthracnose", "downy mildew",
    }),
    # Management prescriptions — requires integration of economic models,
    # input costs, application timing windows, and regulatory constraints
    "management_prescription": frozenset({
        "irrigate now", "apply fertilizer", "spray fungicide",
        "irrigation recommendation", "harvest now",
        "recommended action", "apply herbicide", "prune now",
        "schedule irrigation", "adjust fertilizer rate",
    }),
    # Yield/impact predictions — requires process-based crop models
    # (APSIM, DSSAT, AquaCrop) or calibrated statistical models
    "yield_prediction": frozenset({
        "yield loss", "severe stress", "yield forecast",
        "expected yield", "production estimate",
        "economic loss", "crop failure",
    }),
}

# Flattened for fast O(1) runtime lookup by prohibition #2
FORBIDDEN_DIAGNOSIS_TERMS = frozenset(
    term for group in FORBIDDEN_VOCABULARY.values() for term in group
)


# ============================================================================
# Time window
# ============================================================================

@dataclass
class TimeWindow:
    """Canonical time window for Layer 1 operations."""
    start: datetime
    end: datetime
    label: str = ""  # e.g. "daily", "7d_trailing", "season_to_date"


# ============================================================================
# Source envelope (every source must provide this)
# ============================================================================

@dataclass
class SourceEnvelope:
    """Metadata envelope wrapping every source entering Layer 1.

    Sources that cannot provide this metadata are quarantined.
    """
    source_id: str
    source_family: str   # one of SOURCE_FAMILIES
    source_name: str     # human-readable: "Sentinel-2 L2A", "Dragino LHT65"

    package_id: str      # stable ID of the Layer 0 package
    package_version: str
    input_hash: Optional[str] = None  # hash of package contents for provenance

    produced_at: Optional[datetime] = None
    observed_start: Optional[datetime] = None
    observed_end: Optional[datetime] = None

    spatial_scope: str = "plot"    # one of SPATIAL_SCOPES
    temporal_scope: str = "daily"  # instant, hourly, daily, 7d, season, static

    trust_score: float = 0.5
    source_status: Literal[
        "ok", "degraded", "missing", "stale", "conflicted", "unusable"
    ] = "ok"

    provenance: Dict[str, Any] = field(default_factory=dict)
    diagnostics: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Evidence item (the atomic unit of Layer 1)
# ============================================================================

@dataclass
class EvidenceItem:
    """Everything entering Layer 1 becomes evidence.

    Evidence is typed, scoped, provenanced, and carries confidence.
    """
    evidence_id: str
    plot_id: str
    variable: str
    value: Any
    source_family: str   # one of SOURCE_FAMILIES
    source_id: str

    observation_type: str  # one of OBSERVATION_TYPES

    spatial_scope: str     # one of SPATIAL_SCOPES
    unit: Optional[str] = None  # must be in CANONICAL_UNITS or None
    scope_id: Optional[str] = None
    geometry_ref: Optional[str] = None

    observed_at: Optional[datetime] = None
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None

    confidence: float = 0.5
    sigma: Optional[float] = None
    reliability: float = 0.5
    freshness_score: float = 0.5

    provenance_ref: str = ""
    flags: List[str] = field(default_factory=list)

    # Temporal scope (persisted by engine from assign_temporal_window)
    temporal_scope: str = "daily"

    # Correction #5: diagnostic scope flags
    diagnostic_only: bool = True
    state_update_allowed: bool = False

    data_status: str = "unknown"

    # V92.4-BC.10.5 Truth Governance
    truth_class: str = "unknown"
    source_reality: Optional[str] = None
    production_usable: bool = False
    real_provider_product: bool = False
    grounding_class: Optional[str] = None
    parent_truth_class: Optional[str] = None
    parent_source_reality: Optional[str] = None

    visualization_allowed: bool = True
    experimental_visual_allowed: bool = True
    composite_advisory_allowed: bool = False
    scientific_surface_allowed: bool = False
    prescription_driver_allowed: bool = False
    current_1m_approval_allowed: bool = False

    # Identity of a real dated provider observation. Spatial composites use a
    # separate contract and must not be promoted into historical dates.
    temporal_basis: Optional[str] = None
    content_hash: Optional[str] = None
    provider_product_id: Optional[str] = None
    valid_fraction: Optional[float] = None

    # Weather/forecast completeness
    completeness_status: Optional[str] = None
    missing_variables: List[str] = field(default_factory=list)
    forecast_confidence: Optional[float] = None

    # Lineage / superseding pointer
    supersedes_evidence_id: Optional[str] = None



# ============================================================================
# Quarantined evidence (correction #3)
# ============================================================================

@dataclass
class QuarantinedEvidence:
    """Evidence that failed validation and was quarantined.

    Still visible in diagnostics — broken sensors or unit mismatches
    should appear in data health, not silently vanish.
    """
    evidence_id: str
    reason_codes: List[str]
    original_source_family: str
    variable: Optional[str]
    severity: Literal["warning", "error", "blocking"]
    can_override: bool = False
    original_value: Any = None
    original_unit: Optional[str] = None


# ============================================================================
# Evidence conflict
# ============================================================================

CONFLICT_TYPES = (
    "SENSOR_VS_SAR_MOISTURE_CONFLICT",
    "SENSOR_VS_WEATHER_RAIN_CONFLICT",
    "S2_VS_SENSOR_VEGETATION_CONFLICT",
    "GEO_BOUNDARY_CONTAMINATION_CONFLICT",
    "FORECAST_VS_OBSERVED_WEATHER_CONFLICT",
    "USER_EVENT_VS_SENSOR_EVENT_CONFLICT",
    "S1_WETNESS_WITHOUT_RAIN_OR_IRRIGATION",
    "S2_STRESS_WITH_ADEQUATE_WATER",
    "WAPOR_ET_VS_LOCAL_WATER_BALANCE",
    "SCOPE_MISMATCH",                        # Point vs broad-scope disagreement
)


@dataclass
class EvidenceConflict:
    """A detected conflict between two or more evidence sources."""
    conflict_id: str
    conflict_type: str           # one of CONFLICT_TYPES
    variable_group: str
    spatial_scope: str
    scope_id: Optional[str] = None

    source_a: str = ""
    source_b: str = ""
    severity: Literal["minor", "moderate", "major"] = "minor"
    confidence_impact: float = 0.0

    description: str = ""
    likely_explanations: List[str] = field(default_factory=list)
    downstream_blockers: List[str] = field(default_factory=list)

    threshold_source: str = "heuristic_v1"
    calibration_status: str = "uncalibrated"


# ============================================================================
# Evidence gap
# ============================================================================

GAP_TYPES = (
    "NO_RECENT_SENTINEL2",
    "NO_RECENT_SENTINEL1",
    "NO_SIF_DATA",
    "NO_EO_EMBEDDING",
    "NO_SENSOR_FOR_ROOT_ZONE",
    "NO_RAIN_GAUGE",
    "NO_IRRIGATION_FLOW_SENSOR",
    "NO_CROP_STAGE_DECLARED",
    "NO_VALID_WEATHER_FORECAST",
    "NO_GEO_CONTEXT",
    "NO_LANDCOVER_VALIDITY",
    "NO_WAPOR_CONTEXT",
    "NO_USER_MANAGEMENT_EVENTS",
)


@dataclass
class EvidenceGap:
    """A detected gap in evidence coverage."""
    gap_id: str
    gap_type: str                # one of GAP_TYPES
    severity: Literal["info", "warning", "blocking"] = "info"
    affected_features: List[str] = field(default_factory=list)
    data_improvement_hint: str = ""

    @property
    def suggested_action(self) -> str:
        """Compatibility alias for data_improvement_hint."""
        return self.data_improvement_hint


# ============================================================================
# Fused feature
# ============================================================================

@dataclass
class FusedFeature:
    """A canonical fused feature with full provenance.

    Every fused value retains its source basis and conflict status.
    """
    name: str
    value: Any
    unit: Optional[str]

    spatial_scope: str
    scope_id: Optional[str] = None
    temporal_scope: str = "daily"

    confidence: float = 0.5
    uncertainty: Optional[float] = None
    freshness: float = 0.5

    source_evidence_ids: List[str] = field(default_factory=list)
    source_weights: Dict[str, float] = field(default_factory=dict)
    conflict_status: Literal["none", "minor", "major", "unresolved"] = "none"

    # Propagated from evidence: diagnostic features should not drive state updates
    diagnostic_only: bool = False
    state_update_allowed: bool = False

    flags: List[str] = field(default_factory=list)
    explanation_basis: List[str] = field(default_factory=list)


# ============================================================================
# Fused feature set (7 canonical groups)
# ============================================================================

@dataclass
class FusedFeatureSet:
    """The 7 canonical feature groups produced by Layer 1 fusion."""
    water_context: List[FusedFeature] = field(default_factory=list)
    vegetation_context: List[FusedFeature] = field(default_factory=list)
    phenology_context: List[FusedFeature] = field(default_factory=list)
    stress_evidence_context: List[FusedFeature] = field(default_factory=list)
    soil_site_context: List[FusedFeature] = field(default_factory=list)
    operational_context: List[FusedFeature] = field(default_factory=list)
    data_quality_context: List[FusedFeature] = field(default_factory=list)


# ============================================================================
# Spatial index
# ============================================================================

@dataclass
class ZoneRef:
    zone_id: str
    label: str = ""
    area_fraction: float = 0.0
    geometry_ref: Optional[str] = None


@dataclass
class PointRef:
    point_id: str
    device_id: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    placement: str = "unknown"


@dataclass
class EdgeRegionRef:
    edge_id: str
    contamination_score: float = 0.0
    geometry_ref: Optional[str] = None


@dataclass
class IrrigationBlockRef:
    block_id: str
    area_fraction: float = 0.0


def normalize_geographic_grid_contract(
    *,
    crs: Any,
    bounds: Any,
    transform: Any,
    width: Any,
    height: Any,
    resolution_m: Any,
    expected_width: Optional[int] = None,
    expected_height: Optional[int] = None,
) -> Tuple[Optional[Dict[str, Any]], str]:
    """Validate and normalize the minimum contract for spatial authority.

    Pixel dimensions are not geography.  A raster is spatially admissible only
    when it has a named CRS, positive-area finite bounds, an invertible affine,
    positive dimensions, and a positive resolution.  Both GDAL geotransform
    order ``(c, a, b, f, d, e)`` and rasterio Affine order
    ``(a, b, c, d, e, f)`` are accepted because both exist at the Layer 0/1
    boundary today.
    """
    if not isinstance(crs, str) or not crs.strip():
        return None, "missing_crs"

    if not isinstance(bounds, (list, tuple)) or len(bounds) != 4:
        return None, "missing_bounds"
    try:
        normalized_bounds = tuple(float(value) for value in bounds)
    except (TypeError, ValueError):
        return None, "invalid_bounds"
    if not all(math.isfinite(value) for value in normalized_bounds):
        return None, "non_finite_bounds"
    min_x, min_y, max_x, max_y = normalized_bounds
    if max_x <= min_x or max_y <= min_y:
        return None, "zero_area_bounds"

    if not isinstance(transform, (list, tuple)) or len(transform) != 6:
        return None, "missing_transform"
    try:
        normalized_transform = tuple(float(value) for value in transform)
    except (TypeError, ValueError):
        return None, "invalid_transform"
    if not all(math.isfinite(value) for value in normalized_transform):
        return None, "non_finite_transform"

    gdal_determinant = (
        normalized_transform[1] * normalized_transform[5]
        - normalized_transform[2] * normalized_transform[4]
    )
    affine_determinant = (
        normalized_transform[0] * normalized_transform[4]
        - normalized_transform[1] * normalized_transform[3]
    )
    if abs(gdal_determinant) <= 1e-15 and abs(affine_determinant) <= 1e-15:
        return None, "singular_transform"

    def _positive_dimension(value: Any) -> Optional[int]:
        if isinstance(value, bool):
            return None
        try:
            numeric = float(value)
            integer = int(numeric)
        except (TypeError, ValueError, OverflowError):
            return None
        if not math.isfinite(numeric) or numeric != integer or integer <= 0:
            return None
        return integer

    normalized_width = _positive_dimension(width)
    normalized_height = _positive_dimension(height)
    if normalized_width is None or normalized_height is None:
        return None, "invalid_dimensions"
    if expected_width is not None and normalized_width != expected_width:
        return None, "grid_array_shape_mismatch"
    if expected_height is not None and normalized_height != expected_height:
        return None, "grid_array_shape_mismatch"

    try:
        normalized_resolution = float(resolution_m)
    except (TypeError, ValueError):
        return None, "invalid_resolution"
    if not math.isfinite(normalized_resolution) or normalized_resolution <= 0:
        return None, "invalid_resolution"

    return {
        "crs": crs.strip(),
        "bounds": normalized_bounds,
        "transform": normalized_transform,
        "width": normalized_width,
        "height": normalized_height,
        "resolution_m": normalized_resolution,
    }, "ok"


def raster_grid_matches_dimensions(grid: Any, height: int, width: int) -> bool:
    """Return whether an in-memory grid is rectangular and exactly H x W."""
    if grid is None:
        return True

    shape = getattr(grid, "shape", None)
    if shape is not None:
        try:
            return len(shape) >= 2 and int(shape[0]) == height and int(shape[1]) == width
        except (TypeError, ValueError, IndexError):
            return False

    if not isinstance(grid, (list, tuple)) or len(grid) != height:
        return False
    return all(
        isinstance(row, (list, tuple)) and len(row) == width
        for row in grid
    )


@dataclass
class RasterRef:
    raster_id: str
    variable: str = ""
    resolution_m: Optional[float] = None
    content_hash: Optional[str] = None
    width: int = 0
    height: int = 0
    crs: Optional[str] = None
    bounds: Optional[tuple] = None
    transform: Optional[tuple] = None
    grid: Any = None              # small in-memory grid for L10
    artifact_ref: Optional[str] = None  # future COG/TileStore reference
    valid_pixel_count: int = 0
    observed_ratio: float = 0.0

    # Spatial truth/authority travels with the pixels.  These mirror the
    # EvidenceItem contract so a RasterRef cannot be interpreted more
    # authoritatively than the evidence from which it was admitted.
    truth_class: str = "unknown"
    source_reality: str = "unknown"
    real_provider_product: bool = False
    production_usable: bool = False
    grounding_class: Optional[str] = None
    visualization_allowed: bool = False
    experimental_visual_allowed: bool = False
    composite_advisory_allowed: bool = False
    scientific_surface_allowed: bool = False
    current_1m_approval_allowed: bool = False

    # ASMAE metadata fields (defaulting to False/True/diagnostic for quarantine safety)
    state_update_allowed: bool = False
    observed_spatial_surface: bool = False
    diagnostic_only: bool = True
    asmae_channel: str = "diagnostic"
    source_basis: str = ""
    confidence: float = 0.0
    uncertainty: float = 0.0
    source_run_id: Optional[str] = None
    source_schema_version: Optional[str] = None
    artifact_instance_hash: Optional[str] = None
    prescription_driver_allowed: bool = False
    authority_block_reason: Optional[str] = None
    sentinel_archive_used: bool = False
    archive_scene_count: int = 0
    archive_date_range: Optional[str] = None
    scene_stack_mode: Optional[str] = None

    # Computed admission result.  Caller-supplied values are deliberately
    # overwritten in __post_init__ so a serialized placeholder cannot promote
    # itself by setting this flag.
    geographic_grid_valid: bool = False
    grid_validation_reason: str = "not_validated"

    def __post_init__(self) -> None:
        normalized, reason = normalize_geographic_grid_contract(
            crs=self.crs,
            bounds=self.bounds,
            transform=self.transform,
            width=self.width,
            height=self.height,
            resolution_m=self.resolution_m,
        )
        if normalized is not None and not raster_grid_matches_dimensions(
            self.grid, normalized["height"], normalized["width"]
        ):
            normalized = None
            reason = "grid_array_shape_mismatch"

        self.geographic_grid_valid = normalized is not None
        self.grid_validation_reason = reason
        if normalized is not None:
            self.crs = normalized["crs"]
            self.bounds = normalized["bounds"]
            self.transform = normalized["transform"]
            self.width = normalized["width"]
            self.height = normalized["height"]
            self.resolution_m = normalized["resolution_m"]
            return

        # Invalid geography may remain attached for diagnostics, but it cannot
        # authorize rendering, scientific/state use, or prescriptions.
        self.production_usable = False
        self.visualization_allowed = False
        self.experimental_visual_allowed = False
        self.composite_advisory_allowed = False
        self.scientific_surface_allowed = False
        self.current_1m_approval_allowed = False
        self.state_update_allowed = False
        self.observed_spatial_surface = False
        self.diagnostic_only = True
        self.prescription_driver_allowed = False
        if self.asmae_channel == "state_evidence":
            self.asmae_channel = "diagnostic"
        if not self.authority_block_reason:
            self.authority_block_reason = f"invalid_geospatial_grid:{reason}"


def raster_ref_has_geographic_authority(ref: Any) -> bool:
    """Revalidate a RasterRef so post-construction mutation also fails closed."""
    normalized, _ = normalize_geographic_grid_contract(
        crs=getattr(ref, "crs", None),
        bounds=getattr(ref, "bounds", None),
        transform=getattr(ref, "transform", None),
        width=getattr(ref, "width", None),
        height=getattr(ref, "height", None),
        resolution_m=getattr(ref, "resolution_m", None),
    )
    if normalized is None:
        return False
    return raster_grid_matches_dimensions(
        getattr(ref, "grid", None), normalized["height"], normalized["width"]
    )


@dataclass
class SpatialIndex:
    """Canonical spatial index. Downstream layers use this instead of
    inventing their own geography."""
    plot_id: str
    zones: List[ZoneRef] = field(default_factory=list)
    points: List[PointRef] = field(default_factory=list)
    edge_regions: List[EdgeRegionRef] = field(default_factory=list)
    irrigation_blocks: List[IrrigationBlockRef] = field(default_factory=list)
    raster_refs: List[RasterRef] = field(default_factory=list)


# ============================================================================
# Data health score (correction #12)
# ============================================================================

@dataclass
class DataHealthScore:
    """Formal data health scoring. Layer 2 needs this to decide
    how strongly it is allowed to reason."""
    overall: float = 0.0
    source_completeness: float = 0.0
    provenance_completeness: float = 0.0
    freshness: float = 0.0
    spatial_fidelity: float = 0.0
    conflict_penalty: float = 0.0
    gap_penalty: float = 0.0
    confidence_ceiling: float = 0.0
    status: Literal["ok", "degraded", "unusable"] = "unusable"


# ============================================================================
# Source health report
# ============================================================================

@dataclass
class SourceHealthReport:
    """Per-source health summary."""
    envelopes: List[SourceEnvelope] = field(default_factory=list)
    source_counts: Dict[str, int] = field(default_factory=dict)
    source_statuses: Dict[str, str] = field(default_factory=dict)
    missing_sources: List[str] = field(default_factory=list)


# ============================================================================
# Layer 1 state summary
# ============================================================================

@dataclass
class Layer1StateSummary:
    """Non-diagnostic summary of context state.

    No diagnosis vocabulary allowed here.
    """
    water_context_status: str = "unknown"
    vegetation_context_status: str = "unknown"
    phenology_context_status: str = "unknown"
    soil_site_context_status: str = "unknown"
    operational_context_status: str = "unknown"
    data_health_status: str = "unknown"

    usable_for_layer2: bool = False
    usable_for_layer10: bool = False
    confidence_ceiling: float = 0.0

    blocking_gaps: List[str] = field(default_factory=list)
    unresolved_major_conflicts: List[str] = field(default_factory=list)

    data_health: DataHealthScore = field(default_factory=DataHealthScore)


# ============================================================================
# Provenance
# ============================================================================

@dataclass
class Layer1Provenance:
    """Full provenance trace for a fusion run.

    Hard rule: no fused feature without source evidence IDs.
    No source evidence without provenance ref.
    """
    run_id: str = ""
    engine_version: str = "layer1_fusion_v1"
    contract_version: str = "1.0.0"

    # Fix #11: list per source family to preserve multiple packages
    input_package_ids: Dict[str, List[str]] = field(default_factory=dict)
    source_hashes: Dict[str, str] = field(default_factory=dict)
    adapter_versions: Dict[str, str] = field(default_factory=dict)

    evidence_count: int = 0
    fused_feature_count: int = 0
    conflicts_count: int = 0
    gaps_count: int = 0
    quarantined_count: int = 0

    generated_at: Optional[datetime] = None

    # Invariant violations (from context_invariants.enforce_context_invariants)
    invariant_violations: List[Dict[str, Any]] = field(default_factory=list)


# ============================================================================
# Diagnostics
# ============================================================================

@dataclass
class Layer1Diagnostics:
    """Detailed diagnostics for debugging and audit."""
    status: Literal["ok", "degraded", "unusable"] = "ok"

    source_counts: Dict[str, int] = field(default_factory=dict)
    source_health: Dict[str, str] = field(default_factory=dict)
    confidence_distribution: Dict[str, float] = field(default_factory=dict)

    quarantined_evidence: List[QuarantinedEvidence] = field(default_factory=list)
    quarantined_evidence_count: int = 0

    conflict_summary: Dict[str, int] = field(default_factory=dict)
    gap_summary: Dict[str, int] = field(default_factory=dict)

    hard_prohibition_results: Dict[str, bool] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    data_health: DataHealthScore = field(default_factory=DataHealthScore)


# ============================================================================
# Crop cycle context (passed through from orchestrator)
# ============================================================================

@dataclass
class CropCycleContext:
    """Crop cycle context — declared by user or inferred by earlier layers."""
    crop_type: str = ""
    variety: str = ""
    planting_date: Optional[datetime] = None
    emergence_date: Optional[datetime] = None
    harvest_date: Optional[datetime] = None
    current_stage: str = ""
    gdd_base_temp: float = 10.0
    gdd_accumulated: float = 0.0

    # User-declared context (from L0 UserInputAdapter)
    irrigation_type: str = "rainfed"       # "drip", "pivot", "flood", "rainfed"
    soil_texture_class: str = ""            # "clay", "loam", "sandy_loam", etc.
    soil_ec_ds_m: Optional[float] = None   # Electrical conductivity


# ============================================================================
# Layer 1 input bundle
# ============================================================================

@dataclass
class Layer1InputBundle:
    """The complete input to Layer 1. Pre-fetched Layer 0 packages.

    Layer 1 never performs live data acquisition.
    """
    plot_id: str
    run_id: str
    run_timestamp: datetime

    window_start: datetime
    window_end: datetime

    plot_geometry: Any = None
    plot_grid: Any = None
    crop_cycle: Optional[CropCycleContext] = None

    # Layer 0 packages (any can be None — creates a gap, not fake data)
    layer0_state_package: Optional[Any] = None
    sentinel2_packages: List[Any] = field(default_factory=list)
    sentinel1_packages: List[Any] = field(default_factory=list)
    environment_package: Any = None
    weather_forecast_package: Any = None
    geo_context_package: Any = None
    sensor_context_package: Any = None
    perception_packages: List[Any] = field(default_factory=list)

    user_events: List[Any] = field(default_factory=list)
    user_input_package: Any = None         # UserInputPackage from L0 user adapter
    historical_layer1_package: Any = None
    sentinel5p_packages: List[Any] = field(default_factory=list)
    drone_structural_packages: List[Any] = field(default_factory=list)

    layer0_source_packages: Dict[str, List[Any]] = field(default_factory=dict)

    # ASMAE Engine output package (optional)
    asmae_output: Optional[Dict[str, Any]] = None
    asmae_run_record: Optional[Dict[str, Any]] = None

    # Pre-fetched raster composites from orchestrator (optional).
    # Dict mapping variable name → raster dict with keys:
    #   pixel_array (List[List[float]]), grid_spec, valid_pixel_count, resolution_m
    # Layer 1 never fetches rasters — orchestrator provides them.
    raster_composites: Dict[str, Any] = field(default_factory=dict)

    # Optional path to an ONNX-exported EO Foundation Model.
    # When provided, the engine runs learned spectral embedding inference.
    # When absent, falls back to pure-Python spectral encoder.
    eo_model_path: Optional[str] = None


# ============================================================================
# Layer 2 input context (downstream payload)
# ============================================================================

@dataclass
class Layer2InputContext:
    """What Layer 2 receives. Layer 2 should not need raw Layer 0 packages."""
    plot_id: str = ""
    crop_context: Optional[CropCycleContext] = None

    water_context: Dict[str, Any] = field(default_factory=dict)
    vegetation_context: Dict[str, Any] = field(default_factory=dict)
    phenology_context: Dict[str, Any] = field(default_factory=dict)
    stress_evidence_context: Dict[str, Any] = field(default_factory=dict)
    soil_site_context: Dict[str, Any] = field(default_factory=dict)
    operational_context: Dict[str, Any] = field(default_factory=dict)
    data_quality_context: Dict[str, Any] = field(default_factory=dict)
    diagnostic_values: Dict[str, Any] = field(default_factory=dict)
    asmae_features: Dict[str, Any] = field(default_factory=dict)

    conflicts: List[EvidenceConflict] = field(default_factory=list)
    gaps: List[EvidenceGap] = field(default_factory=list)
    confidence: Dict[str, float] = field(default_factory=dict)
    uncertainty: Dict[str, float] = field(default_factory=dict)
    provenance_ref: str = ""

    spatial_index_ref: Optional[SpatialIndex] = None
    data_health: DataHealthScore = field(default_factory=DataHealthScore)


# ============================================================================
# Layer 1 context package (the master output)
# ============================================================================

@dataclass
class Layer1ContextPackage:
    """The canonical output of Layer 1.

    This is a structured evidence package, not one flat JSON.
    Every downstream layer receives this.
    """
    plot_id: str = ""
    run_id: str = ""
    generated_at: Optional[datetime] = None

    time_window: TimeWindow = field(
        default_factory=lambda: TimeWindow(
            start=datetime.min, end=datetime.min
        )
    )
    spatial_index: SpatialIndex = field(
        default_factory=lambda: SpatialIndex(plot_id="")
    )

    # Authoritative plot footprint supplied by the orchestrator.  This must
    # remain distinct from SpatialIndex/RasterRef bounds, which are rectangular
    # grid extents and cannot represent an irregular field boundary.
    plot_geometry: Any = None

    # Core outputs
    fused_features: FusedFeatureSet = field(default_factory=FusedFeatureSet)
    state_summary: Layer1StateSummary = field(default_factory=Layer1StateSummary)
    source_health: SourceHealthReport = field(default_factory=SourceHealthReport)
    conflicts: List[EvidenceConflict] = field(default_factory=list)
    gaps: List[EvidenceGap] = field(default_factory=list)

    # Fix #7: queryable evidence list (serializable snapshot of the ledger)
    evidence_items: List[EvidenceItem] = field(default_factory=list)

    # Provenance and diagnostics
    provenance: Layer1Provenance = field(default_factory=Layer1Provenance)
    diagnostics: Layer1Diagnostics = field(default_factory=Layer1Diagnostics)

    # Fusion audit log (per-decision trace)
    audit_log: List[Dict[str, Any]] = field(default_factory=list)

    # Downstream payloads
    layer2_input: Any = None
    layer10_payload: Dict[str, Any] = field(default_factory=dict)
    
    # ASMAE run record (optional)
    asmae_run_record: Optional[Dict[str, Any]] = None
    asmae_output: Optional[Dict[str, Any]] = None

    def content_hash(self) -> str:
        """Deterministic hash for reproducibility verification.

        Self-contained: uses stdlib only to avoid circular imports.
        Hashes the core identity + provenance fields. For full
        deterministic serialization, use api_serializer.compute_package_hash().
        """
        parts = [
            self.plot_id,
            self.run_id,
            self.generated_at.isoformat() if self.generated_at else "",
            str(self.provenance.evidence_count),
            str(self.provenance.fused_feature_count),
            str(self.provenance.conflicts_count),
            str(self.provenance.gaps_count),
            str(self.provenance.quarantined_count),
            self.provenance.engine_version,
            self.provenance.contract_version,
            # Include sorted evidence IDs for content sensitivity
            ",".join(sorted(f"{e.evidence_id}:{e.variable}:{e.value}:{e.sigma}:{e.confidence}" for e in self.evidence_items)),
        ]
        raw = "|".join(parts).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:32]
