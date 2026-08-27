"""
Crop Intelligence v6.0B — Label Schema.

Core dataclasses and validation for the crop-cycle labeling system.

A user confirmation is feedback, not automatically ground truth.  Only labels
from an independently verifiable source, explicitly approved by the backend,
can enter a production-training dataset.

Adjustments applied:
  1. Single MongoDB collection (no dual storage)
  2. Stable UUID labelId (separate from Mongo _id)
  3. Canonical geometry hash (SHA256 of normalized GeoJSON)
  4. Reject unknown crop_code (no wheat default)
  5. L2 = get_crop_group(crop_code) — uses actual CROP_GROUP_MAP
  6. label_schema_version = "6.0B"
"""

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

# ── Constants ────────────────────────────────────────────────────────────────

LABEL_SCHEMA_VERSION = "6.0B"
FEATURE_VECTOR_VERSION = "6.0.0"

ALLOWED_LABEL_SOURCES = frozenset({
    "farmer_confirmed",
    "agronomist_confirmed",
    "field_survey",
    "official_parcel_label",
    "lab_ground_truth",
    "admin_verified",
    "historical_record",
    "imported_dataset",
})

# A source in this set is *capable* of becoming training evidence.  Membership
# alone is insufficient: TrainingDatasetBuilder also requires HIGH confidence,
# backend authority validation, immutable feature/run lineage, geometry, and
# the partitions needed for leakage-safe release evaluation.
TRAINING_ELIGIBLE_LABEL_SOURCES = frozenset({
    "agronomist_confirmed",
    "field_survey",
    "official_parcel_label",
    "lab_ground_truth",
})

ALLOWED_LABEL_CONFIDENCES = frozenset({"HIGH", "MEDIUM", "LOW"})

# Source trust levels for quality scoring
SOURCE_TRUST: Dict[str, float] = {
    "lab_ground_truth": 1.0,
    "field_survey": 0.95,
    "official_parcel_label": 0.95,
    "agronomist_confirmed": 0.85,
    "admin_verified": 0.60,
    "imported_dataset": 0.50,
    "historical_record": 0.40,
    "farmer_confirmed": 0.35,
}

# ── Hierarchy Mapping ────────────────────────────────────────────────────────
# Maps crop_group → (L0, L1) classification levels.
# L2 = crop_group itself, L3 = crop_code itself.
#
# L0: active_crop | non_crop
# L1: annual | perennial | orchard | greenhouse | fallow

_GROUP_TO_L0_L1: Dict[str, tuple] = {
    # Annual crops
    "winter_cereal":    ("active_crop", "annual"),
    "summer_cereal":    ("active_crop", "annual"),
    "pseudo_cereal":    ("active_crop", "annual"),
    "rice":             ("active_crop", "annual"),
    "cool_legume":      ("active_crop", "annual"),
    "warm_legume":      ("active_crop", "annual"),
    "solanaceae_veg":   ("active_crop", "annual"),
    "cucurbit_veg":     ("active_crop", "annual"),
    "root_tuber":       ("active_crop", "annual"),
    "leafy_veg":        ("active_crop", "annual"),
    "oilseed":          ("active_crop", "annual"),
    "cotton_fiber":     ("active_crop", "annual"),
    "sugar_crop":       ("active_crop", "annual"),
    "herb_spice":       ("active_crop", "annual"),
    "forage":           ("active_crop", "annual"),
    # Orchards (deciduous + evergreen)
    "evergreen_orchard": ("active_crop", "orchard"),
    "deciduous_orchard": ("active_crop", "orchard"),
    # Perennials
    "tropical_palm":    ("active_crop", "perennial"),
    # Non-crop
    "non_crop":         ("non_crop", "fallow"),
    # Fallback for unknown groups
    "unknown":          ("unknown", "unknown"),
}


# ── Validation ───────────────────────────────────────────────────────────────

def validate_crop_code(crop_code: str) -> bool:
    """Validate crop_code against the 212-crop registry.

    Returns True if valid, False if unknown.
    Does NOT default to wheat — v5.1 fixed that problem.
    """
    try:
        from crop_database import CROP_REGISTRY
        if crop_code in CROP_REGISTRY:
            return True
    except ImportError:
        pass

    # Fallback: check CROP_GROUP_MAP (covers all registered crops)
    try:
        from layer2_veg_int.crop_science_data import CROP_GROUP_MAP
        return crop_code in CROP_GROUP_MAP
    except ImportError:
        pass

    return False


def validate_label_source(source: str) -> bool:
    """Validate that label_source is in the allowed set."""
    return source in ALLOWED_LABEL_SOURCES


# ── Geometry Canonicalization ────────────────────────────────────────────────

def _round_coords(coords, precision: int = 7):
    """Recursively round coordinate arrays to fixed precision."""
    if isinstance(coords, (int, float)):
        return round(float(coords), precision)
    return [_round_coords(c, precision) for c in coords]


def _ensure_ring_closed(ring: list) -> list:
    """Ensure a polygon ring is closed (first == last point)."""
    if not ring:
        return ring
    if ring[0] != ring[-1]:
        ring = ring + [ring[0]]
    return ring


def _normalize_ring_orientation(ring: list, is_exterior: bool = True) -> list:
    """Normalize ring orientation: exterior=CCW, interior=CW.

    Uses the shoelace formula to determine orientation.
    """
    if len(ring) < 4:
        return ring

    # Compute signed area (shoelace formula)
    area = 0.0
    for i in range(len(ring) - 1):
        x0, y0 = ring[i][0], ring[i][1]
        x1, y1 = ring[i + 1][0], ring[i + 1][1]
        area += (x1 - x0) * (y1 + y0)

    is_cw = area > 0

    # Exterior rings should be CCW (area < 0), interior CW (area > 0)
    if is_exterior and is_cw:
        ring = ring[::-1]
    elif not is_exterior and not is_cw:
        ring = ring[::-1]

    return ring


def _canonicalize_polygon(coords: list) -> list:
    """Canonicalize a single polygon's coordinate rings."""
    result = []
    for i, ring in enumerate(coords):
        ring = _round_coords(ring)
        ring = _ensure_ring_closed(ring)
        ring = _normalize_ring_orientation(ring, is_exterior=(i == 0))
        result.append(ring)
    return result


def canonicalize_geometry_hash(geojson: Optional[dict]) -> str:
    """Compute SHA256 of canonical GeoJSON geometry.

    Canonicalization includes:
      - Rounded coordinate precision (7 decimal places ≈ 1.1cm)
      - Closed rings
      - Normalized ring orientation (exterior CCW, interior CW)
      - Sorted multipolygon parts by first coordinate
      - No UI-only metadata (only geometry type + coordinates)

    Returns SHA256 hex digest, or "NO_GEOMETRY" if input is None/empty.
    """
    if not geojson:
        return "NO_GEOMETRY"

    # Extract geometry from Feature or raw geometry
    geom = geojson
    if geom.get("type") == "Feature":
        geom = geom.get("geometry", {})
    if geom.get("type") == "FeatureCollection":
        features = geom.get("features", [])
        if features:
            geom = features[0].get("geometry", {})
        else:
            return "NO_GEOMETRY"

    geom_type = geom.get("type", "")
    coords = geom.get("coordinates")
    if not coords:
        return "NO_GEOMETRY"

    if geom_type == "Polygon":
        canonical_coords = _canonicalize_polygon(coords)
    elif geom_type == "MultiPolygon":
        polys = [_canonicalize_polygon(p) for p in coords]
        # Sort by first coordinate for deterministic ordering
        polys.sort(key=lambda p: (p[0][0][0], p[0][0][1]) if p and p[0] else (0, 0))
        canonical_coords = polys
    elif geom_type == "Point":
        canonical_coords = _round_coords(coords)
    else:
        # Fallback: just round coordinates
        canonical_coords = _round_coords(coords)

    # Build minimal canonical representation
    canonical = {
        "type": geom_type,
        "coordinates": canonical_coords,
    }

    # Deterministic JSON serialization
    canonical_json = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


# ── Hierarchy Targets ────────────────────────────────────────────────────────

def get_hierarchy_targets(crop_code: str, crop_group: str) -> Dict[str, str]:
    """Map a crop to all 4 hierarchy levels.

    L0: active_crop | non_crop
    L1: annual | perennial | orchard | greenhouse | fallow
    L2: crop_group (from CROP_GROUP_MAP — the actual value)
    L3: crop_code (from 212-crop registry)

    Unknown groups remain epistemically unknown at every unsupported level;
    they never imply an active annual crop.
    """
    normalized_group = str(crop_group or "unknown").strip() or "unknown"
    normalized_crop = str(crop_code or "unknown").strip() or "unknown"
    l0_l1 = _GROUP_TO_L0_L1.get(normalized_group, ("unknown", "unknown"))
    return {
        "L0": l0_l1[0],
        "L1": l0_l1[1],
        "L2": normalized_group,
        "L3": normalized_crop,
    }


# ── Core Dataclasses ─────────────────────────────────────────────────────────

@dataclass
class CropLabel:
    """A single confirmed crop-cycle label.

    This is the atomic unit of crop-label evidence.  It is not necessarily
    ground truth and is denied production-training authority by default.

    Fields:
      label_id: Stable UUID (separate from MongoDB _id)
      plot_id: MongoDB ObjectId of the plot
      geometry_hash: SHA256 of canonical GeoJSON at label time
      layer1_run_id: L1 run that produced the feature vector (optional)
      feature_vector_version: Version of CropFeatureVector used
      label_schema_version: Schema version for forward compatibility

      crop_code: From 212-crop registry (validated)
      crop_group: From CROP_GROUP_MAP (computed)

      planting_date: ISO date string (optional)
      harvest_date: ISO date string (optional)

      label_source: One of ALLOWED_LABEL_SOURCES
      label_confidence: HIGH | MEDIUM | LOW
      created_by: User ID (optional)
      notes: Free-text notes (optional)

      feature_vector_ref: Reference key for stored feature vector
      feature_vector_snapshot: Flattened CropFeatureVector at label time

      created_at: ISO timestamp
      superseded_by: Label ID if this label was corrected
      is_active: False if superseded
    """

    label_id: str
    plot_id: str
    geometry_hash: str

    crop_code: str
    crop_group: str

    label_source: str
    label_confidence: str

    # Optional fields
    layer1_run_id: Optional[str] = None
    feature_vector_version: str = FEATURE_VECTOR_VERSION
    label_schema_version: str = LABEL_SCHEMA_VERSION

    planting_date: Optional[str] = None
    harvest_date: Optional[str] = None

    created_by: Optional[str] = None
    notes: Optional[str] = None

    feature_vector_ref: Optional[str] = None
    feature_vector_snapshot: Optional[Dict] = None
    crop_model_input_receipt: Optional[Dict] = None
    crop_model_input_receipt_hash: Optional[str] = None
    runtime_declaration_receipt: Optional[Dict] = None

    created_at: str = ""
    superseded_by: Optional[str] = None
    is_active: bool = True
    synthetic: bool = False

    # Authority and leakage-control metadata.  These values are populated by
    # trusted backend ingestion, never accepted as authority from a browser.
    authority_validated: bool = False
    tenant_id: Optional[str] = None
    farm_id: Optional[str] = None
    crop_cycle_id: Optional[str] = None
    region_partition: Optional[str] = None
    season_partition: Optional[str] = None
    sensor_regime: Optional[str] = None
    # Partial labels train only the levels independently verified by the
    # source. A group-level parcel label must not fabricate a species target.
    supported_hierarchy_levels: List[str] = field(
        default_factory=lambda: ["L0", "L1", "L2", "L3"]
    )

    def __post_init__(self):
        if not self.label_id:
            self.label_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        levels = list(dict.fromkeys(str(level).upper() for level in self.supported_hierarchy_levels))
        if any(level not in {"L0", "L1", "L2", "L3"} for level in levels):
            raise ValueError("supported_hierarchy_levels contains an invalid level")
        self.supported_hierarchy_levels = levels

    def to_dict(self) -> Dict:
        """Serialize to dict for MongoDB storage."""
        return {
            "labelId": self.label_id,
            "plotId": self.plot_id,
            "geometryHash": self.geometry_hash,
            "cropCode": self.crop_code,
            "cropGroup": self.crop_group,
            "labelSource": self.label_source,
            "labelConfidence": self.label_confidence,
            "layer1RunId": self.layer1_run_id,
            "featureVectorVersion": self.feature_vector_version,
            "labelSchemaVersion": self.label_schema_version,
            "plantingDate": self.planting_date,
            "harvestDate": self.harvest_date,
            "createdBy": self.created_by,
            "notes": self.notes,
            "featureVectorRef": self.feature_vector_ref,
            "featureVectorSnapshot": self.feature_vector_snapshot,
            "cropModelInputReceipt": self.crop_model_input_receipt,
            "cropModelInputReceiptHash": self.crop_model_input_receipt_hash,
            "runtimeDeclarationReceipt": self.runtime_declaration_receipt,
            "createdAt": self.created_at,
            "supersededBy": self.superseded_by,
            "isActive": self.is_active,
            "synthetic": self.synthetic,
            "authorityValidated": self.authority_validated,
            "tenantId": self.tenant_id,
            "farmId": self.farm_id,
            "cropCycleId": self.crop_cycle_id,
            "regionPartition": self.region_partition,
            "seasonPartition": self.season_partition,
            "sensorRegime": self.sensor_regime,
            "supportedHierarchyLevels": list(self.supported_hierarchy_levels),
        }

    @classmethod
    def from_dict(cls, doc: Dict) -> "CropLabel":
        """Deserialize from MongoDB document."""
        return cls(
            label_id=doc.get("labelId", ""),
            plot_id=doc.get("plotId", ""),
            geometry_hash=doc.get("geometryHash", ""),
            crop_code=doc.get("cropCode", ""),
            crop_group=doc.get("cropGroup", ""),
            label_source=doc.get("labelSource", ""),
            label_confidence=doc.get("labelConfidence", ""),
            layer1_run_id=doc.get("layer1RunId"),
            feature_vector_version=doc.get("featureVectorVersion", FEATURE_VECTOR_VERSION),
            label_schema_version=doc.get("labelSchemaVersion", LABEL_SCHEMA_VERSION),
            planting_date=doc.get("plantingDate"),
            harvest_date=doc.get("harvestDate"),
            created_by=doc.get("createdBy"),
            notes=doc.get("notes"),
            feature_vector_ref=doc.get("featureVectorRef"),
            feature_vector_snapshot=doc.get("featureVectorSnapshot"),
            crop_model_input_receipt=doc.get("cropModelInputReceipt"),
            crop_model_input_receipt_hash=doc.get(
                "cropModelInputReceiptHash"
            ),
            runtime_declaration_receipt=doc.get(
                "runtimeDeclarationReceipt"
            ),
            created_at=doc.get("createdAt", ""),
            superseded_by=doc.get("supersededBy"),
            is_active=doc.get("isActive", True),
            synthetic=doc.get("synthetic", False),
            authority_validated=doc.get("authorityValidated", False),
            tenant_id=doc.get("tenantId"),
            farm_id=doc.get("farmId"),
            crop_cycle_id=doc.get("cropCycleId"),
            region_partition=doc.get("regionPartition"),
            season_partition=doc.get("seasonPartition"),
            sensor_regime=doc.get("sensorRegime"),
            # Missing legacy metadata cannot be interpreted as a fully
            # verified species label.  Fail closed until an authority process
            # explicitly declares which hierarchy levels were observed.
            supported_hierarchy_levels=(
                doc.get("supportedHierarchyLevels") or []
            ),
        )


@dataclass
class LabelQualityScore:
    """Quality assessment of a crop label.

    Used by TrainingDatasetBuilder to filter unreliable samples.
    """

    label_id: str

    # Quality dimensions (each 0.0 - 1.0)
    temporal_coverage: float = 0.0   # How much of crop cycle has feature data
    feature_completeness: float = 0.0  # CropFeatureVector.data_completeness
    geometry_stability: float = 1.0  # 1.0 if geometry unchanged, 0.0 if changed
    source_trust: float = 0.5       # From SOURCE_TRUST lookup
    freshness: float = 1.0          # Exponential decay from created_at

    # Composite
    overall_quality: float = 0.0
    quality_tier: str = "D"
    quality_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "label_id": self.label_id,
            "temporal_coverage": self.temporal_coverage,
            "feature_completeness": self.feature_completeness,
            "geometry_stability": self.geometry_stability,
            "source_trust": self.source_trust,
            "freshness": self.freshness,
            "overall_quality": self.overall_quality,
            "quality_tier": self.quality_tier,
            "quality_warnings": self.quality_warnings,
        }


@dataclass
class LabeledSample:
    """A label + its feature vector = one ML training sample.

    This is what TrainingDatasetBuilder produces.
    v6.0C classifiers consume lists of LabeledSample.
    """

    label: CropLabel
    features: Dict[str, Optional[float]]  # From CropFeatureVector.to_flat_dict()
    quality: LabelQualityScore

    # Training metadata
    hierarchy_targets: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.hierarchy_targets:
            self.hierarchy_targets = get_hierarchy_targets(
                self.label.crop_code, self.label.crop_group
            )


@dataclass
class DatasetSummary:
    """Summary of a built training dataset."""

    samples: List[LabeledSample]
    class_distribution: Dict[str, int]
    quality_distribution: Dict[str, int]
    feature_completeness_stats: Dict[str, float]
    target_level: str
    total_samples: int
    warnings: List[str]
    included_samples: int = 0
    excluded_samples: int = 0
    exclusion_reasons: Dict[str, int] = field(default_factory=dict)
    built_at: str = ""

    def __post_init__(self):
        if not self.built_at:
            self.built_at = datetime.now(timezone.utc).isoformat()
