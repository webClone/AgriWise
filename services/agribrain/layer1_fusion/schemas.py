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
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Tuple


# ============================================================================
# Canonical constants
# ============================================================================

SOURCE_FAMILIES = (
    "sentinel2",
    "sentinel1",
    "environment",
    "weather_forecast",
    "geo_context",
    "sensor",
    "perception",
    "user_event",
    "history",
)

OBSERVATION_TYPES = (
    "measurement",
    "model_estimate",
    "forecast",
    "static_prior",
    "derived_feature",
    "diagnostic",
    "event",
    "state_estimate",
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
    "m2", "cm", "L", "L_min", "deg", "min", "bar", "V",
    "mm_h", "ratio", "score", "index", "count", "bool", "class",
    "linear_power", "db",
}

# Diagnosis vocabulary that must NEVER appear in Layer 1 outputs
FORBIDDEN_DIAGNOSIS_TERMS = frozenset({
    "nitrogen deficiency", "phosphorus deficiency", "potassium deficiency",
    "fungal disease", "bacterial disease", "viral disease",
    "irrigate now", "apply fertilizer", "spray fungicide",
    "yield loss", "severe stress", "recommended action",
    "nutrient prescription", "disease diagnosis",
    "irrigation recommendation", "harvest now",
})


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
    unit: Optional[str]  # must be in CANONICAL_UNITS or None

    source_family: str   # one of SOURCE_FAMILIES
    source_id: str

    observation_type: str  # one of OBSERVATION_TYPES

    spatial_scope: str     # one of SPATIAL_SCOPES
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
    diagnostic_only: bool = False
    state_update_allowed: bool = True


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


# ============================================================================
# Evidence gap
# ============================================================================

GAP_TYPES = (
    "NO_RECENT_SENTINEL2",
    "NO_RECENT_SENTINEL1",
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
    suggested_action: str = ""


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


@dataclass
class RasterRef:
    raster_id: str
    variable: str = ""
    resolution_m: float = 10.0
    content_hash: Optional[str] = None


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
    confidence_ceiling: float = 1.0
    status: Literal["ok", "degraded", "unusable"] = "ok"


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
    layer0_state_package: Any = None
    sentinel2_packages: List[Any] = field(default_factory=list)
    sentinel1_packages: List[Any] = field(default_factory=list)
    environment_package: Any = None
    weather_forecast_package: Any = None
    geo_context_package: Any = None
    sensor_context_package: Any = None
    perception_packages: List[Any] = field(default_factory=list)

    user_events: List[Any] = field(default_factory=list)
    historical_layer1_package: Any = None


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

    conflicts: List[EvidenceConflict] = field(default_factory=list)
    gaps: List[EvidenceGap] = field(default_factory=list)
    confidence: Dict[str, float] = field(default_factory=dict)
    provenance_ref: str = ""

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

    # Downstream payloads
    layer2_input: Any = None
    layer10_payload: Dict[str, Any] = field(default_factory=dict)

    def content_hash(self) -> str:
        """Deterministic hash for reproducibility verification.

        Uses the full deterministic API serializer, so identical packages
        always produce identical hashes, and any change in values, confidence,
        provenance, flags, etc. produces a different hash.
        """
        from .outputs.api_serializer import compute_package_hash
        return compute_package_hash(self)
