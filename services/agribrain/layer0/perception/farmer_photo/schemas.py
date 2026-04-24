"""
Farmer Photo Engine — Input/Output Schemas.

Plant recognition + symptom evidence engine.
Accepts close-range phone/camera photos of crops and emits structured,
uncertainty-aware observations about crop identity, organ type, and symptoms.

Scope: LOCAL ("point") — a single photo cannot represent an entire field.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..common.contracts import (
    PerceptionEngineInput,
    PerceptionEngineOutput,
    PerceptionEngineFamily,
    PerceptionVariable,
    PerceptionArtifact,
    ZoneOutput,
)


# ============================================================================
# Scene / Organ / Symptom class constants
# ============================================================================

class SceneClass:
    """Primary scene classification — the first gate."""
    FIELD = "field"                # Open field view, ground-level
    CROP_CLOSEUP = "crop_closeup"  # Close-range crop detail (leaf, fruit, stem)
    NON_FIELD = "non_field"        # Not agricultural (indoor, selfie, document)
    UNUSABLE = "unusable"          # Too dark, too blurry, corrupted


class CropClass:
    """Recognized crop families."""
    WHEAT = "wheat"
    MAIZE = "maize"
    TOMATO = "tomato"
    POTATO = "potato"
    OLIVE = "olive"
    CITRUS = "citrus"
    UNKNOWN = "unknown_crop"


class OrganClass:
    """What part of the plant is visible."""
    CANOPY = "canopy"
    LEAF = "leaf"
    FRUIT = "fruit"
    STEM = "stem"
    SOIL = "soil"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class SymptomClass:
    """Visible symptom categories — symptom-first, not disease-first."""
    HEALTHY = "healthy"
    CHLOROSIS = "chlorosis"          # Yellowing
    NECROSIS = "necrosis"            # Tissue death / browning
    SPOTS = "spots"                  # Discrete lesions
    MILDEW_LIKE = "mildew_like"      # Powdery/downy coating
    RUST_LIKE = "rust_like"          # Rust-colored pustules
    BLIGHT_LIKE = "blight_like"      # Rapid necrosis/wilting
    INSECT_DAMAGE = "insect_damage"  # Chewing, mining, etc.
    WILT = "wilt"                    # Turgor loss
    UNKNOWN_STRESS = "unknown_stress"


ALL_SYMPTOM_CLASSES = [
    SymptomClass.HEALTHY,
    SymptomClass.CHLOROSIS,
    SymptomClass.NECROSIS,
    SymptomClass.SPOTS,
    SymptomClass.MILDEW_LIKE,
    SymptomClass.RUST_LIKE,
    SymptomClass.BLIGHT_LIKE,
    SymptomClass.INSECT_DAMAGE,
    SymptomClass.WILT,
    SymptomClass.UNKNOWN_STRESS,
]


# ============================================================================
# Engine Input
# ============================================================================

@dataclass
class FarmerPhotoEngineInput(PerceptionEngineInput):
    """
    Input for the Farmer Photo perception engine.

    Accepts any phone/camera photo. The engine gates non-field
    and unusable images before running any inference.
    """
    # Required
    image_ref: str = ""                  # URI or path to photo
    image_bytes: Optional[bytes] = None  # raw image bytes (memory ingress)
    image_content_hash: str = ""         # content hash for caching
    image_width: int = 0
    image_height: int = 0

    # Strongly recommended — GPS + timestamp
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    plot_centroid_lat: Optional[float] = None
    plot_centroid_lng: Optional[float] = None

    # Optional metadata
    exif: Optional[Dict[str, Any]] = None
    user_label: Optional[str] = None      # "leaf", "canopy", "soil", etc.
    crop_hint: Optional[str] = None       # Plot metadata for crop type hint

    # Pixel statistics (pre-computed or from synthetic test data)
    pixel_stats: Optional[Dict[str, Any]] = None
    synthetic_pixels: Optional[Dict[str, Any]] = None

    def validate(self) -> Tuple[bool, List[str]]:
        """Validate mandatory fields."""
        errors = []
        if not self.image_ref and self.image_bytes is None and self.synthetic_pixels is None and self.pixel_stats is None:
            errors.append("image_ref, image_bytes, pixel_stats, or synthetic_pixels required")
        if self.image_width <= 0 and self.pixel_stats is None and self.image_bytes is None and self.image_ref == "":
            errors.append("image_width must be positive or image content/stats provided")
        if self.image_height <= 0 and self.pixel_stats is None and self.image_bytes is None and self.image_ref == "":
            errors.append("image_height must be positive or image content/stats provided")
        return len(errors) == 0, errors


# ============================================================================
# Classifier Results (internal, used by engine pipeline)
# ============================================================================

@dataclass
class SceneResult:
    """Scene classification result."""
    scene_class: str = SceneClass.UNUSABLE
    confidence: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)  # E1.1: diagnostic subclass


@dataclass
class CropResult:
    """Crop classification result."""
    crop_class: str = CropClass.UNKNOWN
    confidence: float = 0.0
    top_candidates: Dict[str, float] = field(default_factory=dict)
    assisted_by_hint: bool = False


@dataclass
class OrganResult:
    """Organ classification result."""
    organ_class: str = OrganClass.UNKNOWN
    confidence: float = 0.0
    assisted_by_user_label: bool = False


@dataclass
class SymptomResult:
    """Symptom detection result — symptom-first, not disease-first."""
    # Per-class probabilities (sum to ~1.0)
    symptom_scores: Dict[str, float] = field(default_factory=dict)

    # Derived
    primary_symptom: str = SymptomClass.HEALTHY
    primary_confidence: float = 0.0
    severity: float = 0.0            # 0 = none, 1 = extreme
    disease_candidate: str = ""       # Best-guess disease name (weak)
    disease_confidence: float = 0.0   # Gated by crop confidence

    @property
    def has_symptoms(self) -> bool:
        return self.primary_symptom != SymptomClass.HEALTHY


# ============================================================================
# Engine Output
# ============================================================================

@dataclass
class FarmerPhotoEngineOutput(PerceptionEngineOutput):
    """
    Output from the Farmer Photo perception engine.

    V1 outputs:
      - Scene classification (field / crop_closeup / non_field / unusable)
      - Crop classification (wheat / maize / ... / unknown)
      - Organ classification (leaf / canopy / fruit / ...)
      - Symptom detection (symptom-first, disease candidate secondary)
      - Local canopy cover (only if canopy-valid)
      - Local phenology hint
      - All outputs carry sigma and are point-scoped

    geometry_scope is ALWAYS "point" — enforced in __post_init__.
    """
    # Classification results
    scene_class: str = SceneClass.UNUSABLE
    scene_confidence: float = 0.0
    crop_class: str = CropClass.UNKNOWN
    crop_confidence: float = 0.0
    organ_class: str = OrganClass.UNKNOWN
    organ_confidence: float = 0.0

    # Symptom results
    primary_symptom: str = SymptomClass.HEALTHY
    symptom_confidence: float = 0.0
    symptom_severity: float = 0.0
    disease_candidate: str = ""
    disease_confidence: float = 0.0

    # Local observations (point-scoped)
    local_canopy_cover: float = 0.0
    phenology_stage_est: float = 0.0
    plant_identity_confidence: float = 0.0

    # Classification provenance — tracks user influence
    crop_assisted_by_hint: bool = False
    organ_from_user_label: bool = False

    def __post_init__(self):
        # Enforce local scope — a single photo is never plot-wide
        self.engine_family = PerceptionEngineFamily.FARMER_PHOTO
        self.geometry_scope = "point"
