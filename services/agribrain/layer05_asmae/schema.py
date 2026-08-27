"""
ASMAE Canonical Schemas.

All data contracts for the Adaptive Scientific MicroZone Assimilation Engine.

Design rules:
  1. Runtime objects may use np.ndarray for in-memory computation.
  2. Persisted/serializable manifests must NOT use np.ndarray.
     They use artifact refs, shape tuples, dtype strings, and content hashes.
  3. Every output carries resolution + uncertainty + provenance.
  4. No ASMAE output may be called "direct 1m satellite observation."
  5. Deterministic content_hash() for reproducibility.

Schema pairs:
  ASMAESceneRuntime  — in-memory scene with numpy arrays
  ASMAESceneManifest — serializable scene metadata for storage/API

  ObservationOperatorRuntime  — in-memory H_t with scipy sparse
  ObservationOperatorManifest — serializable H_t metadata
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional, Tuple

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore[assignment]

try:
    from scipy import sparse as sp
except ImportError:
    sp = None  # type: ignore[assignment]

from .config import (
    ASMAE_SCHEMA_VERSION,
    N_STATES,
    STATE_NAMES,
    STATE_BOUNDS,
    ASMAE_MODES,
)


# ============================================================================
# Input
# ============================================================================

@dataclass
class ASMAEInput:
    """Top-level input bundle for an ASMAE run.

    Consumed by the ASMAE runner after the orchestrator has:
      1. Completed Layer 0 acquisition
      2. Completed Layer 1 coarse fusion
      3. Completed Layers 2–8 coarse priors (pass A)
    """
    plot_id: str
    run_id: str
    polygon_geojson: dict
    geometry_hash: str
    start_date: date
    end_date: date

    # Layer 0 data
    layer0_source_packages: dict
    layer0_state_package: Optional[dict] = None

    # Layer 1 coarse pass
    layer1_context_package: Optional[dict] = None

    # Layers 2–8 coarse priors
    coarse_layer_outputs: dict = field(default_factory=dict)

    # Raster composites from orchestrator
    raster_composites: dict = field(default_factory=dict)

    # Sentinel archive metadata
    historical_scene_refs: list = field(default_factory=list)
    archive_metrics: dict = field(default_factory=dict)
    archive_baselines: dict = field(default_factory=dict)
    archive_bma: dict = field(default_factory=dict)
    retrovalidation_residuals: dict = field(default_factory=dict)
    phenology_envelopes: dict = field(default_factory=dict)
    archive_metrics_status: Optional[str] = None
    archive_metrics_hash: Optional[str] = None
    archive_posterior: dict = field(default_factory=dict)
    plot_timeseries: Any = field(default_factory=list)

    # Crop context
    crop_context: dict = field(default_factory=dict)
    crop_posterior: dict = field(default_factory=dict)
    crop_posterior_lineage: Optional[str] = None
    crop_evidence_ledger: dict = field(default_factory=dict)
    crop_evidence_ledger_hash: Optional[str] = None
    crop_influence_manifest: dict = field(default_factory=dict)
    crop_influence_manifest_hash: Optional[str] = None
    soil_context: dict = field(default_factory=dict)
    management_events: List[dict] = field(default_factory=list)
    user_observations: List[dict] = field(default_factory=list)

    # Mode (see config.ASMAE_MODES)
    mode: str = "shadow"
    is_pseudo: bool = False
    source_policy: Optional[str] = None
    asmae_scene_fetch_telemetry: Optional[dict] = None
    evidence_capability_contract_version: str = "unknown"
    capability_plan_hash: str = ""

    # Authority/cache identity.  These fields are scientific inputs because a
    # rollout demotion must not reuse an artifact serialized under old rights.
    execution_permissions: dict = field(default_factory=dict)
    permission_contract_version: str = "unknown"
    authority_phase: str = "disabled"
    rollout_state: str = "not_registered"

    # Weather Archive (BC.10.17 P0.7)
    weather_archive_status: str = "unavailable"
    weather_source_reality: str = "missing"
    weather_daily_series: dict = field(default_factory=dict)
    weather_archive_hash: Optional[str] = None
    missing_variables: list = field(default_factory=list)
    variable_completeness: dict = field(default_factory=dict)

    # Fine spatial candidates are rejected before allocating H matrices or
    # ensembles when this scientific resource ceiling is exceeded.
    resource_memory_limit_mb: Optional[float] = None

    def __post_init__(self) -> None:
        if self.mode not in ASMAE_MODES:
            raise ValueError(
                f"Invalid ASMAE mode '{self.mode}'. "
                f"Must be one of: {ASMAE_MODES}"
            )
        ledger = None
        if self.crop_evidence_ledger:
            from services.agribrain.scientific_contracts.crop_evidence import CropEvidenceLedgerV2
            ledger = CropEvidenceLedgerV2.from_dict(self.crop_evidence_ledger)
            if ledger.plot_namespace.plot_id != str(self.plot_id):
                raise ValueError("Crop evidence ledger plot namespace mismatch")
            if (
                self.crop_evidence_ledger_hash
                and ledger.ledger_hash != str(self.crop_evidence_ledger_hash)
            ):
                raise ValueError("Crop evidence ledger hash mismatch")
            self.crop_evidence_ledger = ledger.to_dict()
            self.crop_evidence_ledger_hash = ledger.ledger_hash
        if self.crop_influence_manifest:
            from services.agribrain.scientific_contracts.crop_governance import (
                CropInfluenceManifestV1,
            )
            manifest = CropInfluenceManifestV1.from_dict(
                self.crop_influence_manifest
            )
            if manifest.namespace.plot_id != str(self.plot_id):
                raise ValueError("Crop influence manifest plot namespace mismatch")
            if (
                self.crop_posterior_lineage
                and manifest.crop_posterior_parent_hash
                != str(self.crop_posterior_lineage)
            ):
                raise ValueError("Crop influence manifest posterior lineage mismatch")
            if (
                self.crop_influence_manifest_hash
                and manifest.content_hash
                != str(self.crop_influence_manifest_hash)
            ):
                raise ValueError("Crop influence manifest hash mismatch")
            if ledger is not None:
                admitted_cluster_ids = {
                    cluster.cluster_id
                    for cluster in ledger.independence_clusters
                    if cluster.independence_eligible and cluster.admitted
                }
                if set(manifest.independent_evidence_ids) != admitted_cluster_ids:
                    raise ValueError(
                        "Crop influence manifest independent evidence does not match ledger"
                    )
            self.crop_influence_manifest = manifest.to_dict()
            self.crop_influence_manifest_hash = manifest.content_hash


# ============================================================================
# Scene — Runtime vs Manifest
# ============================================================================

@dataclass
class ASMAESceneRuntime:
    """In-memory scene with numpy arrays for computation.

    This object exists only during a run. It is NEVER persisted directly.
    For storage, convert to ASMAESceneManifest.
    """
    scene_id: str
    sensor: str  # "S2", "S1", "S5P", "EXTERNAL"
    acquisition_time: datetime

    crs: str
    transform: List[float]
    width: int
    height: int

    # Runtime-only: numpy arrays
    bands: Dict[str, Any]          # {band_name: np.ndarray}
    masks: Dict[str, Any]          # {mask_name: np.ndarray}

    # Metadata
    sun_angles: Optional[dict] = None
    incidence_angle: Optional[Any] = None   # np.ndarray or None
    cloud_fraction: Optional[float] = None
    qa_score: float = 0.0

    # Provenance and telemetry attributes
    transform_convention: str = 'gdal'
    valid_support: Optional[Any] = None
    valid_support_hash: str = ''
    valid_fraction: float = 0.0
    spatial_normalization: Dict[str, Any] = field(default_factory=dict)
    source_reality: str = "unknown"
    real_provider_product: bool = False
    test_override: bool = False
    production_usable: bool = False
    diagnostic_only: bool = True

    visualization_allowed: bool = True
    experimental_visual_allowed: bool = True
    composite_advisory_allowed: bool = True
    scientific_surface_allowed: bool = False
    prescription_driver_allowed: bool = False
    current_1m_approval_allowed: bool = False
    state_update_allowed: bool = False

    provenance_ref: str = ""
    authority: str = "diagnostic"
    provider_product_id: Optional[str] = None
    catalog_item_id: Optional[str] = None
    provider_tile_id: Optional[str] = None
    provider_orbit_id: Optional[str] = None
    provider_orbit_pass: Optional[str] = None
    product_binding: str = "unknown"
    binding_proof: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ASMAESceneManifest:
    """Serializable scene metadata for storage, API, and reproducibility.

    Contains artifact references instead of raw arrays.
    """
    scene_id: str
    sensor: str
    acquisition_time: str              # ISO 8601

    crs: str
    transform: List[float]
    shape: Tuple[int, int]             # (height, width)
    dtype: str = "float32"

    # Artifact references (paths or content-addressed IDs)
    band_refs: Dict[str, str] = field(default_factory=dict)
    mask_refs: Dict[str, str] = field(default_factory=dict)

    # Metadata
    sun_angles: Optional[dict] = None
    incidence_angle_ref: Optional[str] = None
    cloud_fraction: Optional[float] = None
    qa_score: float = 0.0

    content_hash: str = ""
    provenance_ref: str = ""
    provider_product_id: Optional[str] = None
    catalog_item_id: Optional[str] = None
    provider_tile_id: Optional[str] = None
    provider_orbit_id: Optional[str] = None
    provider_orbit_pass: Optional[str] = None
    product_binding: str = "unknown"
    binding_proof: Dict[str, Any] = field(default_factory=dict)


    transform_convention: str = 'gdal'
    valid_support_hash: str = ''


# ============================================================================
# MicroZone State Vector
# ============================================================================

@dataclass
class MicroZoneStateVector:
    """State vector for a single micro-zone.

    13 agronomic state variables — NDVI is NOT a state, it is an observation.
    Each state carries its own uncertainty (sigma).
    """
    microzone_id: str
    resolution_m: int
    day: str                           # ISO date

    # State values (indexed by config.STATE_NAMES)
    values: List[float] = field(default_factory=lambda: [0.0] * N_STATES)
    sigma: List[float] = field(default_factory=lambda: [0.1] * N_STATES)

    # Provenance
    last_observation_day: Optional[str] = None
    days_since_observation: int = 0
    update_count: int = 0

    def clamp(self) -> None:
        """Clamp state values to physical bounds."""
        for i, name in enumerate(STATE_NAMES):
            lo, hi = STATE_BOUNDS[name]
            self.values[i] = max(lo, min(hi, self.values[i]))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "microzone_id": self.microzone_id,
            "resolution_m": self.resolution_m,
            "day": self.day,
            "state": {name: round(self.values[i], 6) for i, name in enumerate(STATE_NAMES)},
            "sigma": {name: round(self.sigma[i], 6) for i, name in enumerate(STATE_NAMES)},
            "days_since_observation": self.days_since_observation,
            "update_count": self.update_count,
        }


# ============================================================================
# Observation Operator — Runtime vs Manifest
# ============================================================================

@dataclass
class ObservationOperatorRuntime:
    """In-memory H_t observation operator with scipy sparse matrix.

    y_t = H_t · x_t + ε_t

    The sparse matrix maps micro-zone states to observed pixel values,
    accounting for geometry, PSF blur, and fractional overlap.

    This object exists only during a run. For storage, use
    ObservationOperatorManifest + .npz artifact.
    """
    operator_id: str
    scene_id: str
    sensor: str
    source_resolution_m: float
    target_resolution_m: int

    source_crs: str
    target_crs: str
    source_transform: List[float]
    target_transform: List[float]

    # Runtime-only: scipy sparse matrix
    H_matrix: Optional[Any] = None    # scipy.sparse.csr_matrix

    # PSF model
    psf_model: str = "gaussian"
    blur_sigma_m: float = 0.0

    # Quality
    support_score: float = 0.0
    condition_number_proxy: float = 0.0
    registration_uncertainty_m: float = 0.0

    # Valid mask reference
    valid_support_hash: str = ''
    transform_convention: str = 'gdal'
    valid_mask_ref: str = ""


@dataclass
class ObservationOperatorManifest:
    """Serializable H_t metadata for storage and reproducibility.

    The actual sparse matrix is stored as a .npz artifact, referenced
    by h_matrix_artifact_ref. The manifest carries shape, format, and
    provenance information.
    """
    operator_id: str
    scene_id: str
    sensor: str
    source_resolution_m: float
    target_resolution_m: int

    source_crs: str
    target_crs: str
    source_transform: List[float]
    target_transform: List[float]

    # Sparse matrix artifact reference
    h_matrix_artifact_ref: str = ""
    h_matrix_format: str = "csr_v1"
    h_matrix_shape: Tuple[int, int] = (0, 0)   # (n_pixels, n_microzones * n_states)
    h_matrix_nnz: int = 0
    h_matrix_dtype: str = "float32"

    # PSF model
    psf_model: str = "gaussian"
    blur_sigma_m: float = 0.0

    # Quality
    support_score: float = 0.0
    condition_number_proxy: float = 0.0
    registration_uncertainty_m: float = 0.0

    content_hash: str = ""


    valid_support_hash: str = ''
    transform_convention: str = 'gdal'


# ============================================================================
# Resolution Decision
# ============================================================================

@dataclass
class ResolutionDecision:
    """Full resolution evaluation result.

    Every ASMAE run evaluates all candidate resolutions and selects
    the best scientifically justified one.
    """
    candidate_resolutions_tested_m: List[int] = field(default_factory=list)

    selected_effective_resolution_m: int = 10
    selected_visual_resolution_m: int = 10
    selected_state_update_resolution_m: int = 10
    selected_training_resolution_m: int = 10
    research_resolution_m: int = 1

    safe_for_1m_claim: bool = False

    demoted_candidates: List[Dict[str, Any]] = field(default_factory=list)
    candidate_scores: Dict[int, float] = field(default_factory=dict)
    reason_codes: Dict[int, List[str]] = field(default_factory=dict)
    resource_plans: Dict[int, Dict[str, Any]] = field(default_factory=dict)


# ============================================================================
# Certification
# ============================================================================

@dataclass
class ASMAECertification:
    """Plot-level ASMAE certification status."""
    plot_id: str
    certification_level: str = "provisional"  # provisional | retrovalidated | certified | demoted
    max_certified_resolution_m: int = 10
    certification_date: Optional[str] = None
    retro_score: float = 0.0
    validation_count: int = 0
    drift_detected: bool = False
    last_validation_date: Optional[str] = None


# ============================================================================
# Output
# ============================================================================

@dataclass
class ASMAEOutput:
    """Canonical output of an ASMAE run.

    All outputs include resolution + uncertainty + provenance.
    No output may be called "direct 1m satellite observation."
    """
    schema_version: str = ASMAE_SCHEMA_VERSION
    plot_id: str = ""
    run_id: str = ""
    generated_at: Optional[datetime] = None

    # Resolution decision
    resolution_decision: Optional[ResolutionDecision] = None

    # Raster outputs (state name → 2D grid)
    raster_maps: Dict[str, List[List[float]]] = field(default_factory=dict)
    uncertainty_maps: Dict[str, List[List[float]]] = field(default_factory=dict)
    confidence_maps: Dict[str, List[List[float]]] = field(default_factory=dict)

    # Validation rasters
    retrovalidation_maps: Dict[str, List[List[float]]] = field(default_factory=dict)
    bma_maps: Dict[str, List[List[float]]] = field(default_factory=dict)

    # References (stored as artifact IDs)
    microzone_graph_ref: str = ""
    state_timeline_ref: str = ""
    observation_operator_refs: List[str] = field(default_factory=list)
    grid_spec: Dict[str, Any] = field(default_factory=dict)

    # Training
    weak_labels: List[dict] = field(default_factory=list)

    # Certification
    certification: Optional[ASMAECertification] = None

    # Layer integration outputs
    layer1_raster_composites: dict = field(default_factory=dict)
    layer10_surfaces: dict = field(default_factory=dict)

    # Diagnostics & provenance
    diagnostics: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)
    asmae_evidence_state: Dict[str, Any] = field(default_factory=dict)
    asmae_feature_pack: Dict[str, Any] = field(default_factory=dict)
    asmae_proof: Dict[str, Any] = field(default_factory=dict)
    plot_state_artifact: Dict[str, Any] = field(default_factory=dict)

    def content_hash(self) -> str:
        """Output content hash — deterministic, excludes run_id/timestamps.

        V79A: Hashes actual scientific output values, not just metadata.
        Same scientific input + same seed → same output_content_hash.
        """
        from .deterministic import hash_grid_dict, hash_weak_labels

        payload = {
            "schema_version": self.schema_version,
            "resolution": self.resolution_decision.selected_effective_resolution_m
                if self.resolution_decision else 10,
            "raster_values_hash": hash_grid_dict(self.raster_maps),
            "uncertainty_values_hash": hash_grid_dict(self.uncertainty_maps),
            "grid_spec": self.grid_spec,
            "weak_label_values_hash": hash_weak_labels(self.weak_labels),
            "weak_label_count": len(self.weak_labels),
            "cert_level": self.certification.certification_level
                if self.certification else "none",
        }
        raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        plot_state_science = {
            key: value for key, value in dict(self.plot_state_artifact or {}).items()
            if key not in {'run_id', 'generated_at', 'content_hash'}
        }
        payload.update({
            'confidence_values_hash': hash_grid_dict(self.confidence_maps),
            'retrovalidation_values_hash': hash_grid_dict(self.retrovalidation_maps),
            'bma_values_hash': hash_grid_dict(self.bma_maps),
            'operator_refs': list(self.observation_operator_refs),
            'plot_state_science': plot_state_science,
            'evidence_state': dict(self.asmae_evidence_state or {}),
            'production_usable': bool(
                (self.diagnostics or {}).get('production_usable', False)
            ),
            'radiometric_pass': bool(
                (
                    (self.diagnostics or {}).get('radiometric', {})
                    if isinstance((self.diagnostics or {}).get('radiometric', {}), dict)
                    else {}
                ).get('overall_pass', False)
            ),
            'retro_score': (self.diagnostics or {}).get('retro_score'),
            'bma_status': (self.diagnostics or {}).get('bma_status'),
        })
        raw = json.dumps(payload, sort_keys=True, default=str).encode('utf-8')
        return hashlib.sha256(raw).hexdigest()

    def artifact_instance_hash(self) -> str:
        """Instance hash — includes run_id and timestamps.

        Different run_id → different instance hash, even if content is same.
        """
        payload = {
            "output_content_hash": self.content_hash(),
            "plot_id": self.plot_id,
            "run_id": self.run_id,
            "generated_at": self.generated_at.isoformat() if self.generated_at else "",
        }
        if isinstance(self.diagnostics, dict) and "shadow_ml" in self.diagnostics:
            payload["shadow_ml"] = self.diagnostics["shadow_ml"]
        raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
