"""
Layer 10 Runner: SIRE Pipeline Orchestration (v11.0)
=====================================================

Full production pipeline with temporal intelligence and execution overlay:
  1. Adapt all upstream layer outputs via adapters
  2. Generate continuous surfaces (spatial-first, broadcast-last)
  3. Generate temporal intelligence surfaces (8 types: delta, momentum, trend, forecast)
  4. Generate execution intelligence surfaces (readiness, priority, timing, conflict)
  5. Tag every surface with GroundingClass
  6. Detect micro-objects (if resolution allows)
  7. Synthesize zones from surfaces (with deconfliction)
  8. Compute histogram analytics (field + zone + uncertainty)
  9. Build render manifest + quicklooks
  10. Wire export packs (raster + vector + tile)
  11. Build TemporalBundle (14-day T-7 → T+7 for Time-Peel UI)
  12. Enforce invariants
"""

from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone
import hashlib
import json
import logging
import math
import sys
import os
import time
import numpy as np

try:
    from services.agribrain.common.safe_npz import safe_np_load
except ImportError:  # Transitional compatibility for the legacy service launcher.
    from common.safe_npz import safe_np_load

logger = logging.getLogger(__name__)


def reconcile_durable_asmae_job_before_publication(
    output: Any, plot_namespace: Any
) -> None:
    """Replace captured queue state with durable truth at commit time.

    Layer 10 can finish after a background worker has already transitioned.
    Publication must therefore fence its earlier queued/running observation
    against the job record immediately before cache commit.
    """
    display = dict(getattr(output, "source_policy_display_state", None) or {})
    plot_state = dict(display.get("asmaePlotState") or {})
    active_job_id = str(plot_state.get("activeSpatialJobId") or "")
    captured_status = str(plot_state.get("activeSpatialJobStatus") or "").lower()
    if not active_job_id and captured_status not in {"queued", "running", "stalled"}:
        return
    try:
        from services.agribrain.common.plot_namespace import _coerce_namespace
        from services.agribrain.layer05_asmae.background_jobs import (
            get_job_status,
            latest_job_for_plot,
        )
        namespace = _coerce_namespace(plot_namespace)
        job = get_job_status(active_job_id) if active_job_id else None
        if job is not None:
            job_namespace = _coerce_namespace(job.get("plot_namespace"))
            if job_namespace != namespace:
                raise ValueError("active ASMAE job belongs to a different PlotNamespace")
        if job is None:
            job = latest_job_for_plot(namespace)
    except Exception as exc:
        logger.warning("[L10] Durable ASMAE publication reconciliation failed: %s", exc)
        return
    if not job or not job.get("status"):
        return

    status = str(job.get("status") or "").lower()
    plot_state.update({
        "activeSpatialJobId": str(job.get("job_id") or active_job_id) or None,
        "activeSpatialJobStatus": status,
        "activeSpatialJobStage": str(job.get("stage") or ""),
        "activeSpatialJobProgressPct": int(job.get("progress_pct", 0) or 0),
    })
    if status in {"failed", "stalled"}:
        error = str(job.get("error") or job.get("reason") or "")
        code = str(job.get("failure_code") or job.get("reason") or "")
        if not code:
            import re
            match = re.search(r"\b[A-Z][A-Z0-9_]{4,}\b", error)
            code = match.group(0) if match else "ASMAE_REFRESH_FAILED"
        plot_state["spatialRefreshFailure"] = {
            "failureCode": code,
            "failureStage": str(job.get("stage") or "execution_failed"),
            "retryClassification": str(
                job.get("retry_classification") or "manual_review"
            ),
            "retryEligible": bool(job.get("retry_eligible", False)),
            "error": error or "ASMAE spatial refresh failed",
            "contractVersion": str(
                job.get("evidence_capability_contract_version")
                or (job.get("scientific_identity") or {}).get(
                    "evidence_capability_contract_version", ""
                )
            ),
        }
    elif status == "completed":
        plot_state.pop("spatialRefreshFailure", None)
    display["asmaePlotState"] = plot_state
    output.source_policy_display_state = display

    for attribute in ("asmae_evidence_state", "core_asmae_evidence_state"):
        evidence = getattr(output, attribute, None)
        if not isinstance(evidence, dict):
            continue
        evidence = dict(evidence)
        evidence.update({
            "active_spatial_job_id": plot_state.get("activeSpatialJobId"),
            "active_spatial_job_status": status,
            "active_spatial_job_stage": plot_state.get("activeSpatialJobStage"),
            "active_spatial_job_progress_pct": plot_state.get(
                "activeSpatialJobProgressPct"
            ),
        })
        setattr(output, attribute, evidence)


def separate_asmae_evidence_and_publication(
    raw_evidence_state: Any,
    *,
    has_composite_surface: bool,
    rollout_block_reason: Optional[str] = None,
    has_plot_state_artifact: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Keep scientific evidence immutable across display publication.

    Composite availability is a surface-inventory fact.  It cannot replace a
    real diagnostic raster state, and it cannot manufacture ASMAE evidence
    when the core run is missing or failed.
    """
    core = dict(raw_evidence_state or {})
    if rollout_block_reason and not has_plot_state_artifact:
        core.update({
            "state": "asmae_unavailable",
            "real_asmae_evidence": False,
            "asmae_advisory_evidence": False,
            "current_1m_approval_allowed": False,
            "visual_fusion_allowed": False,
            "composite_fusion_allowed": False,
            "experimental_visual_allowed": True,
            "authority": "none",
            "source_reality": "missing",
            "reason": rollout_block_reason,
            "authority_block_reason": rollout_block_reason,
        })
    if not core:
        core = {
            "state": "asmae_unavailable",
            "real_asmae_evidence": False,
            "asmae_advisory_evidence": False,
            "authority": "none",
            "source_reality": "missing",
            "reason": "core_asmae_evidence_missing",
        }

    publication = {
        "state": "canonical_surface_inventory",
        "composite_surface_available": bool(has_composite_surface),
        "authority": "display_inventory_only",
        "source_reality": "mixed_inventory",
        "core_authority_unchanged": True,
    }
    if has_composite_surface:
        publication.update({
            "state": "composite_assimilated_asmae",
            "real_asmae_evidence": False,
            "asmae_advisory_evidence": True,
            "current_1m_approval_allowed": False,
            "visual_fusion_allowed": False,
            "composite_fusion_allowed": True,
            "experimental_visual_allowed": True,
            "authority": "experimental_asmae_advisory",
            "source_reality": "raster_composite_proxy",
            "reason": "using_composite_assimilated_asmae",
            "authority_block_reason": None,
        })

    demotion = {
        "applied": False,
        "reason": "publication_surface_selection_cannot_rewrite_core_asmae_evidence",
        "core_state": core.get("state"),
        "publication_state": publication.get("state"),
    }
    return core, publication, demotion

from services.agribrain.scientific_contracts import (
    StateSupportStatus,
    normalize_status,
    index_state_support_ledger,
    ContractViolation,
    Layer10PublicationConstructionError,
    LAYER10_PUBLICATION_SCHEMA_VERSION,
)

from services.agribrain.layer10_sire.schema import (
    Layer10Input, Layer10Output, QualityReport, RenderManifest,
    HistogramBundle, SIREDegradation, RenderMode, GroundingClass, SurfaceType,
    ZoneArtifact, ZoneType, ZoneFamily, MapModeDef, LegendEntry,
    HistogramArtifact, DeltaHistogram, TemporalBundle, TemporalSlice,
    MicroObjectArtifact, ObjectType, SurfaceArtifact, PaletteId, ComponentFailure
)
from services.agribrain.core.observability import observability_registry
from services.agribrain.layer10_sire.invariants import enforce_layer10_invariants
from services.agribrain.layer10_sire.surface_contract import (
    PublicationStatus,
    RENDER_AUTHORIZATION_VERSION,
    SURFACES_SCHEMA_VERSION,
    VALID_PUBLICATION_STATUSES,
    build_default_asmae_proof,
    build_no_data_render_authorizations,
    classify_surface_publication,
    validate_declared_publication_status,
)
from services.agribrain.layer05_asmae.config import archive_status_ok

# Adapters
from services.agribrain.layer10_sire.adapters.l1_adapter import adapt_l1
from services.agribrain.layer10_sire.adapters.l2_adapter import adapt_l2
from services.agribrain.layer10_sire.adapters.l3_adapter import adapt_l3
from services.agribrain.layer10_sire.adapters.l4_l9_adapters import (
    adapt_l4, adapt_l5, adapt_l6, adapt_l7, adapt_l8, adapt_l9,
)

# Sub-engine imports
from services.agribrain.layer10_sire.surfaces.vegetation import generate_vegetation_surfaces
from services.agribrain.layer10_sire.surfaces.water import generate_water_surfaces
from services.agribrain.layer10_sire.surfaces.salinity import generate_salinity_surfaces
from services.agribrain.layer10_sire.surfaces.uncertainty import generate_uncertainty_surfaces
from services.agribrain.layer10_sire.surfaces.nutrients import generate_nutrient_surfaces
from services.agribrain.layer10_sire.surfaces.disease import generate_disease_surfaces
from services.agribrain.layer10_sire.surfaces.yield_surface import generate_yield_surfaces
from services.agribrain.layer10_sire.surfaces.suitability import generate_suitability_surfaces
from services.agribrain.layer10_sire.surfaces.agronomic_models import generate_agronomic_models
from services.agribrain.layer10_sire.surfaces.risk import generate_risk_surfaces
from services.agribrain.layer10_sire.surfaces.temporal import generate_temporal_surfaces
from services.agribrain.layer10_sire.surfaces.execution import generate_execution_surfaces
from services.agribrain.layer10_sire.surfaces.resolution import generate_resolution_surfaces
from services.agribrain.layer10_sire.surfaces.asmae import generate_asmae_surfaces
from services.agribrain.layer10_sire.surfaces.historical import generate_historical_surfaces
from services.agribrain.layer10_sire.zones.extractor import extract_zones
from services.agribrain.layer10_sire.zones.heterogeneity_zones import extract_heterogeneity_zones
from services.agribrain.layer10_sire.zones.labeler import label_zones
from services.agribrain.layer10_sire.zones.topology import validate_topology
from services.agribrain.layer10_sire.histograms.field_hist import compute_field_histograms
from services.agribrain.layer10_sire.histograms.zone_hist import compute_zone_histograms
from services.agribrain.layer10_sire.histograms.uncertainty_hist import compute_uncertainty_histograms
from services.agribrain.layer10_sire.histograms.delta_hist import compute_delta_histograms
from services.agribrain.layer10_sire.histograms.compare import compare_zones, compare_surfaces
from services.agribrain.layer10_sire.structure.canopy_mask import detect_canopy
from services.agribrain.layer10_sire.products.manifest import build_render_manifest
from services.agribrain.layer10_sire.products.export import (
    export_raster_pack, export_vector_pack, export_tile_manifest,
)
from services.agribrain.layer10_sire.imagery.quicklooks import generate_quicklook
from services.agribrain.layer10_sire.temporal_bundle import build_temporal_bundle
from services.agribrain.layer10_sire.explainability import build_premium_packs


def apply_composite_scouting_grounding(surface: Any, unique_count: int) -> bool:
    """Apply truthful spatial grounding to a composite scouting artifact."""
    provenance = getattr(surface, "provenance", None) or {}
    support_class = provenance.get("support_class") or provenance.get("state_support_class")
    if support_class != "composite_scouting":
        return False
    surface.observed_ratio = 0.0
    surface.grounding_class = (
        GroundingClass.MODEL_ASSISTED_RASTER.value
        if unique_count > 1
        else GroundingClass.UNIFORM.value
    )
    provenance["direct_observation"] = False
    provenance["management_zone_eligible"] = False
    provenance["zone_statistics_eligible"] = False
    provenance["scope"] = (
        "model_assisted_spatial_scouting" if unique_count > 1 else "plot_level"
    )
    surface.provenance = provenance
    return True


def validate_spatial_grid_spec(grid_spec: Any, width: int, height: int) -> tuple[bool, str]:
    """Fail-closed validation for a raster that may be rendered geographically."""
    if not grid_spec:
        return False, "missing_grid_spec"
    get = grid_spec.get if isinstance(grid_spec, dict) else lambda k, d=None: getattr(grid_spec, k, d)
    bounds = get("bounds")
    transform = get("transform")
    crs = str(get("crs", "") or "")
    try:
        if not bounds or len(bounds) != 4 or not all(np.isfinite(float(v)) for v in bounds):
            return False, "invalid_bounds"
        min_x, min_y, max_x, max_y = map(float, bounds)
        if max_x <= min_x or max_y <= min_y:
            return False, "zero_area_bounds"
        if not transform or len(transform) != 6 or not all(np.isfinite(float(v)) for v in transform):
            return False, "invalid_transform"
        a, b, c, d, e, f = map(float, transform)
        # Accept either GDAL geotransform ordering or rasterio/Affine ordering.
        # Both are used by upstream providers, but at least one interpretation
        # must describe a non-degenerate grid consistent with its bounds.
        gdal_determinant = b * f - c * e
        affine_determinant = a * e - b * d
        gdal_span = (abs(b) * width + abs(c) * height, abs(e) * width + abs(f) * height)
        affine_span = (abs(a) * width + abs(b) * height, abs(d) * width + abs(e) * height)
        if max(abs(gdal_determinant), abs(affine_determinant)) <= 1e-15:
            return False, "zero_affine_determinant"
        if int(get("width", width)) != int(width) or int(get("height", height)) != int(height):
            return False, "grid_dimension_mismatch"
        bounds_span = (max_x - min_x, max_y - min_y)

        def span_matches(candidate: tuple[float, float]) -> bool:
            return all(
                abs(actual - expected) <= max(abs(expected) * 0.05, 1e-9)
                for actual, expected in zip(candidate, bounds_span)
            )

        if not span_matches(gdal_span) and not span_matches(affine_span):
            return False, "affine_bounds_dimension_mismatch"
        if not crs or not (crs.upper().startswith("EPSG:") or "OPENGIS.NET/DEF/CRS" in crs.upper()):
            return False, "unsupported_crs"
    except (TypeError, ValueError, OverflowError):
        return False, "invalid_grid_spec"
    return True, "ok"


RENDER_DEPENDENCY_MASK_TYPES = frozenset({
    SurfaceType.OBSERVED_DATA_MASK_NDVI.value,
    SurfaceType.GAP_FILL_MASK_NDVI.value,
    SurfaceType.VALID_DATA_MASK_NDVI.value,
})

SALINITY_EVIDENCE_MARKERS = (
    "swir", "salinity", "saline", "salt_index", "soil_ec",
    "electrical_conductivity", "irrigation_water_ec", "water_ec",
    "salinity_confirmed",
)


class SpatialProcessingSkipped(RuntimeError):
    """Internal control flow for work that requires a valid geographic grid."""


def has_salinity_specific_feature_evidence(features: List[Any]) -> bool:
    """Reject generic soil/water features as evidence of salinity."""
    for feature in features or []:
        normalized = str(feature).lower().replace("-", "_").replace(" ", "_")
        if any(marker in normalized for marker in SALINITY_EVIDENCE_MARKERS):
            return True
    return False


def _surface_type_name(surface: SurfaceArtifact) -> str:
    semantic_type = getattr(surface, "semantic_type", "")
    return semantic_type.value if hasattr(semantic_type, "value") else str(semantic_type)


def is_render_dependency_surface(surface: SurfaceArtifact) -> bool:
    """True for masks consumed by a renderer but never selectable by a user."""
    return _surface_type_name(surface).upper() in RENDER_DEPENDENCY_MASK_TYPES


def is_high_resolution_surface(surface: SurfaceArtifact) -> bool:
    """Identify non-base-grid visual products, including the HIGHRES alias."""
    surface_type = _surface_type_name(surface).upper()
    return (
        surface_type.endswith("_EXPERIMENTAL_FINE_DETAIL")
        or surface_type == SurfaceType.EXPERIMENTAL_VISUAL_CANOPY_HIGHRES.value
        or surface_type == SurfaceType.ASMAE_VISUAL_FUSION_CANOPY.value
    )


def build_grid_spec_for_shape(
    base_grid_spec: Dict[str, Any], width: int, height: int, resolution_m: float
) -> Dict[str, Any]:
    """Build a geographically equivalent grid for a different raster shape.

    Bounds are retained, while the affine pixel size is recomputed for the
    actual array dimensions.  This prevents a 4x visual raster from claiming
    the base grid's width, height, and 10 m transform.
    """
    result = dict(base_grid_spec or {})
    result.update({
        "width": int(width),
        "height": int(height),
        "resolution": float(resolution_m),
        "resolution_m": float(resolution_m),
    })
    bounds = result.get("bounds")
    try:
        if bounds and len(bounds) == 4:
            min_x, min_y, max_x, max_y = map(float, bounds)
            if max_x > min_x and max_y > min_y and width > 0 and height > 0:
                result["bounds"] = [min_x, min_y, max_x, max_y]
                result["transform"] = [
                    min_x,
                    (max_x - min_x) / float(width),
                    0.0,
                    max_y,
                    0.0,
                    -(max_y - min_y) / float(height),
                ]
    except (TypeError, ValueError, OverflowError):
        pass
    return result


def surface_grid_validity(
    surface: SurfaceArtifact, *, pipeline_grid_valid: bool, pipeline_grid_status: str
) -> tuple[bool, str]:
    """Return the fail-closed geographic validity of one surface array."""
    if not pipeline_grid_valid:
        return False, pipeline_grid_status or "invalid_pipeline_grid"
    values = getattr(surface, "values", None) or []
    height = len(values)
    width = len(values[0]) if height and values[0] else 0
    return validate_spatial_grid_spec(getattr(surface, "grid_spec", None), width, height)


def sanitize_surface_values(surfaces: List[SurfaceArtifact]) -> List[SurfaceArtifact]:
    """
    Ensure all values in all surfaces are either a finite float or None.
    Replaces any NaN, Inf, -Inf with None.
    """
    for s in surfaces:
        if s.values is not None:
            try:
                # Most production generators already emit finite Python
                # ``float | None`` grids.  Do a validation-only pass first and
                # retain those lists by identity; rebuilding every row of all
                # visual-resolution surfaces added substantial latency before
                # histogram generation while changing no values.
                requires_rebuild = False
                for row in s.values:
                    for val in row:
                        if val is None:
                            continue
                        if type(val) is float and math.isfinite(val):
                            continue
                        requires_rebuild = True
                        break
                    if requires_rebuild:
                        break
                if not requires_rebuild:
                    continue

                sanitized_grid = []
                for r in s.values:
                    sanitized_row = []
                    for val in r:
                        if val is None:
                            sanitized_row.append(None)
                        else:
                            converted = float(val)
                            sanitized_row.append(converted if math.isfinite(converted) else None)
                    sanitized_grid.append(sanitized_row)
                s.values = sanitized_grid
            except Exception:
                pass
    return surfaces


def _deterministic_run_id(inp: Layer10Input, adapted_ids: Dict[str, str]) -> str:
    """Generate a deterministic run_id from input signatures."""
    sig = json.dumps({
        'plot_id': inp.plot_id,
        'grid': f"{inp.grid_height}x{inp.grid_width}",
        'profile': inp.render_profile,
        'modes': sorted(inp.requested_modes),
        'upstream': adapted_ids,
    }, sort_keys=True)
    return f"L10-{hashlib.md5(sig.encode()).hexdigest()[:12]}"


def _point_in_polygon(px: float, py: float, polygon) -> bool:
    """Ray-casting point-in-polygon test (pure Python)."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _rasterize_polygon_mask(
    height: int,
    width: int,
    bounds: Any,
    polygon: Any,
) -> np.ndarray:
    """Rasterize a field ring on one grid without leaking loop state.

    The mask owns its row/column indices locally. Callers never depend on
    variables left behind by a preceding surface loop, which is important
    when the final surface uses a higher-resolution display grid.
    """
    if height <= 0 or width <= 0:
        raise ValueError("polygon mask dimensions must be positive")
    if not bounds or len(bounds) != 4:
        raise ValueError("polygon mask requires four finite bounds")
    min_x, min_y, max_x, max_y = (float(value) for value in bounds)
    if not all(np.isfinite((min_x, min_y, max_x, max_y))):
        raise ValueError("polygon mask bounds must be finite")
    if max_x - min_x <= 1e-9 or max_y - min_y <= 1e-9:
        raise ValueError("polygon mask bounds are degenerate")
    if not polygon or len(polygon) < 3:
        raise ValueError("polygon mask requires a valid exterior ring")

    y_step = (max_y - min_y) / height
    x_step = (max_x - min_x) / width
    mask = np.zeros((height, width), dtype=bool)
    dx = 0.45 * x_step
    dy = 0.45 * y_step
    for row_index in range(height):
        center_y = max_y - (row_index + 0.5) * y_step
        for column_index in range(width):
            center_x = min_x + (column_index + 0.5) * x_step
            if _point_in_polygon(center_x, center_y, polygon):
                mask[row_index, column_index] = True
            elif (
                _point_in_polygon(center_x - dx, center_y - dy, polygon)
                or _point_in_polygon(center_x + dx, center_y - dy, polygon)
                or _point_in_polygon(center_x - dx, center_y + dy, polygon)
                or _point_in_polygon(center_x + dx, center_y + dy, polygon)
            ):
                mask[row_index, column_index] = True
    return mask


def _resize_boolean_mask(
    base_mask: np.ndarray,
    target_height: int,
    target_width: int,
) -> np.ndarray:
    """Project a base-grid mask onto a surface grid by cell-center ownership."""
    source_mask = np.asarray(base_mask, dtype=bool)
    if source_mask.ndim != 2 or not source_mask.size:
        raise ValueError("source mask must be a non-empty two-dimensional array")
    if target_height <= 0 or target_width <= 0:
        raise ValueError("target mask dimensions must be positive")
    source_height, source_width = source_mask.shape
    if (target_height, target_width) == (source_height, source_width):
        return source_mask
    rows = np.clip(
        np.floor(
            (np.arange(target_height) + 0.5) * source_height / target_height
        ).astype(int),
        0,
        source_height - 1,
    )
    columns = np.clip(
        np.floor(
            (np.arange(target_width) + 0.5) * source_width / target_width
        ).astype(int),
        0,
        source_width - 1,
    )
    return source_mask[np.ix_(rows, columns)]


def _extract_valid_field_polygon(field_tensor, explicit_geometry=None):
    """Return a non-degenerate exterior ring from explicit field geometry.

    Raster bounds describe the pixel envelope, not the farm boundary.  They
    must never be promoted into a substitute field polygon.
    """
    candidate = None
    if explicit_geometry:
        candidate = explicit_geometry

    if not candidate and field_tensor is not None:
        static_meta = getattr(field_tensor, "static", {}) or {}
        candidate = static_meta.get("polygon_coords")
        grid_spec = getattr(field_tensor, "grid_spec", None)
        if not candidate and grid_spec is not None:
            candidate = getattr(grid_spec, "polygon", None)

    if not candidate:
        return None, "missing_field_geometry"

    if isinstance(candidate, dict):
        if candidate.get("type") == "Feature":
            candidate = candidate.get("geometry") or {}
        geometry_type = candidate.get("type")
        coordinates = candidate.get("coordinates")
        if geometry_type == "Polygon" and coordinates:
            candidate = coordinates[0]
        elif geometry_type == "MultiPolygon" and coordinates:
            candidate = coordinates[0][0]
        else:
            return None, "invalid_field_geometry_type"

    # Accept a raw exterior ring and the common one-level Polygon nesting.
    while (
        isinstance(candidate, (list, tuple))
        and candidate
        and isinstance(candidate[0], (list, tuple))
        and candidate[0]
        and isinstance(candidate[0][0], (list, tuple))
    ):
        candidate = candidate[0]

    if not isinstance(candidate, (list, tuple)) or len(candidate) < 3:
        return None, "missing_field_geometry"
    try:
        ring = [(float(point[0]), float(point[1])) for point in candidate]
    except (TypeError, ValueError, IndexError):
        return None, "invalid_field_geometry_coordinates"
    if not all(np.isfinite(x) and np.isfinite(y) for x, y in ring):
        return None, "invalid_field_geometry_coordinates"
    area_twice = abs(
        sum(
            ring[i][0] * ring[(i + 1) % len(ring)][1]
            - ring[(i + 1) % len(ring)][0] * ring[i][1]
            for i in range(len(ring))
        )
    )
    if area_twice <= 1e-12:
        return None, "zero_area_field_geometry"
    return ring, "ok"


def _compute_field_valid_cells(l10_input, H: int, W: int, surfaces) -> Optional[int]:
    """Compute canonical field valid cell count.

    Strategy cascade:
      1. Point-in-polygon mask from field_tensor.grid_spec.polygon
      2. NDVI non-null count (proxy when no polygon available)
      3. None → downstream code falls back to H * W
    """
    # Strategy 1: use only explicit field geometry. Raster bounds are not a
    # field polygon and are deliberately excluded.
    ft = l10_input.field_tensor
    if ft is not None:
        poly_ring, _ = _extract_valid_field_polygon(ft, explicit_geometry=getattr(l10_input, "field_geometry", None))
        gs = getattr(ft, 'grid_spec', None)
        if gs is not None and poly_ring:
            if poly_ring and len(poly_ring) >= 3:
                # Rasterize: for each grid cell centre, test if inside polygon
                gs_dict = (
                    gs.to_dict() if hasattr(gs, 'to_dict')
                    else (dict(gs) if isinstance(gs, dict) else {})
                )
                b = gs_dict.get('bounds') or getattr(gs, 'bounds', None)
                if b and len(b) == 4:
                    min_lng, min_lat, max_lng, max_lat = b
                    lat_step = (max_lat - min_lat) / H
                    lng_step = (max_lng - min_lng) / W
                    count = 0
                    for r in range(H):
                        cy = max_lat - (r + 0.5) * lat_step
                        for c in range(W):
                            cx = min_lng + (c + 0.5) * lng_step
                            if _point_in_polygon(cx, cy, poly_ring):
                                count += 1
                    if count > 0:
                        return count

    # Strategy 2: NDVI non-null count (a reasonable proxy)
    from services.agribrain.layer10_sire.schema import SurfaceType as _ST
    ndvi_surf = next((s for s in surfaces if s.semantic_type == _ST.NDVI_CLEAN), None)
    if ndvi_surf:
        count = sum(
            1 for r in range(H) for c in range(W)
            if ndvi_surf.values[r][c] is not None
        )
        if count > 0:
            return count

    # Strategy 3: no information — return None so downstream uses H * W
    return None


def _resolve_phenology_context(
    veg_int: Any,
    ndvi_surface_mean: Optional[float] = None,
    crop: str = "",
) -> Dict[str, Any]:
    """Consume the Layer-2 phenology receipt without downstream re-inference."""
    del ndvi_surface_mean  # L10 surfaces are not independent phenology evidence.
    crop_value = str(crop or "").strip()
    from services.agribrain.scientific_contracts.crop_phenology import (
        consume_canonical_phenology_output,
    )
    result = consume_canonical_phenology_output(veg_int)
    result.update({
        "raw_l2_crop_stage": result["resolved_crop_stage"],
        "ndvi_mean": None,
        "ndvi_source": "not_used_by_layer10",
        "crop": crop_value,
        "crop_known": crop_value.lower() not in {"", "unknown", "none", "no crop", "no_crop"},
    })
    return result


def _resolve_phenology_stage(veg_int, ndvi_surface_mean: float = None) -> str:
    return _resolve_phenology_context(veg_int, ndvi_surface_mean)["resolved_crop_stage"]


def _legacy_resolve_phenology_stage(veg_int, ndvi_surface_mean: float = None) -> str:
    """Compatibility alias; no legacy NDVI inference remains on this path."""
    return _resolve_phenology_stage(veg_int, ndvi_surface_mean)


L10_CACHE_SCHEMA_VERSION = f"v84_publication_authority::{SURFACES_SCHEMA_VERSION}"

SURFACE_TRUTHFULNESS_POLICY_VERSION = "v82_1_truthfulness"
DISPLAY_TRUST_POLICY_VERSION = "v82_1_display_tiers"


def stable_grid_hash(grid: Any) -> str:
    """Compute stable cryptographic SHA-256 hash of a grid/array value.

    Applies a strict finite-value policy: normalizes NaNs to -9999.0,
    positive infinity to 9999.0, negative infinity to -9999.0,
    and includes shape/dtype/nan_policy properties in the hashed payload to prevent type/shape mismatch collisions.
    """
    if grid is None:
        return "none"
    try:
        import numpy as np
        arr = np.asarray(grid)
        # Apply nan-to-num policy
        arr_normalized = np.nan_to_num(arr, nan=-9999.0, posinf=9999.0, neginf=-9999.0)
        payload = {
            "shape": arr_normalized.shape,
            "dtype": str(arr_normalized.dtype),
            "nan_policy": "nan_to_num_9999",
            "bytes_sha256": hashlib.sha256(arr_normalized.astype(np.float32).tobytes()).hexdigest(),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    except Exception:
        # Fallbacks for list of lists
        try:
            return hashlib.sha256(json.dumps(grid).encode("utf-8")).hexdigest()
        except Exception:
            return hashlib.sha256(str(grid).encode("utf-8")).hexdigest()


def align_surface_to_display_grid(surface: SurfaceArtifact, display_grid_spec: dict, method: str = "bilinear") -> SurfaceArtifact:
    """
    Resample a surface to match a target display_grid_spec.
    If the surface is already aligned (matching grid_hash), return it as is.
    Otherwise, resample its values and confidence grids and mark display_resampled = true in provenance.
    """
    import numpy as np
    
    src_spec = surface.grid_spec or {}
    # ``source_grid_spec`` records the native scientific grid and may already
    # differ from ``grid_spec`` because an upstream producer performed a
    # proven reprojection onto the Layer-10 display grid.  This helper owns
    # display alignment only; it must never replace that native lineage with
    # the current/display grid during a later normalization pass.
    existing_source_grid_spec = (
        dict(surface.source_grid_spec)
        if isinstance(surface.source_grid_spec, dict) and surface.source_grid_spec
        else None
    )
    src_hash = src_spec.get("grid_hash")
    tgt_hash = display_grid_spec.get("grid_hash")
    
    if src_hash and tgt_hash and src_hash == tgt_hash:
        return surface
        
    src_h, src_w = len(surface.values), len(surface.values[0]) if len(surface.values) > 0 else 0
    tgt_h = int(display_grid_spec.get("height", 8))
    tgt_w = int(display_grid_spec.get("width", 8))
    
    # Grid spec fields compatibility: target dims already integer-cast above
    
    src_bounds = src_spec.get("bounds", [])
    tgt_bounds = display_grid_spec.get("bounds", [])
    
    same_shape = src_h == tgt_h and src_w == tgt_w
    same_bounds = False
    if len(src_bounds) == 4 and len(tgt_bounds) == 4:
        try:
            same_bounds = bool(np.allclose(src_bounds, tgt_bounds, rtol=0.0, atol=1e-12))
        except (TypeError, ValueError):
            same_bounds = False
    # Layer-10 generated base-grid surfaces frequently carry only dimensions
    # in their provisional grid spec.  If their shape already matches the
    # canonical display grid, resampling cannot add information and used to
    # trigger tens of thousands of scalar np.clip calls.  Attach the proven
    # display grid directly; retain the prior spec as source metadata.
    if same_shape and (same_bounds or not src_bounds):
        if existing_source_grid_spec is None:
            surface.source_grid_spec = dict(src_spec) if src_spec else None
        surface.display_grid_spec = dict(display_grid_spec)
        surface.grid_spec = dict(display_grid_spec)
        return surface

    src_arr = np.array([[np.nan if x is None else x for x in row] for row in surface.values], dtype=np.float32)
    resampled_vals = np.full((tgt_h, tgt_w), np.nan, dtype=np.float32)
    
    s_minx, s_miny, s_maxx, s_maxy = src_bounds if len(src_bounds) == 4 else (0.0, 0.0, 1.0, 1.0)
    t_minx, t_miny, t_maxx, t_maxy = tgt_bounds if len(tgt_bounds) == 4 else (0.0, 0.0, 1.0, 1.0)
    
    for tr in range(tgt_h):
        ty = t_maxy - (tr + 0.5) * (t_maxy - t_miny) / tgt_h
        for tc in range(tgt_w):
            tx = t_minx + (tc + 0.5) * (t_maxx - t_minx) / tgt_w
            if s_maxx > s_minx and s_maxy > s_miny:
                sc = (tx - s_minx) * src_w / (s_maxx - s_minx) - 0.5
                sr = (s_maxy - ty) * src_h / (s_maxy - s_miny) - 0.5
            else:
                sc = tc * src_w / tgt_w - 0.5
                sr = tr * src_h / tgt_h - 0.5
                
            if method == "nearest":
                r_idx = int(np.clip(np.round(sr), 0, src_h - 1))
                c_idx = int(np.clip(np.round(sc), 0, src_w - 1))
                resampled_vals[tr, tc] = src_arr[r_idx, c_idx]
            else:
                r0 = int(np.floor(sr))
                r1 = r0 + 1
                c0 = int(np.floor(sc))
                c1 = c0 + 1
                
                r0_c = np.clip(r0, 0, src_h - 1)
                r1_c = np.clip(r1, 0, src_h - 1)
                c0_c = np.clip(c0, 0, src_w - 1)
                c1_c = np.clip(c1, 0, src_w - 1)
                
                dr = sr - r0
                dc = sc - c0
                
                v00 = src_arr[r0_c, c0_c]
                v01 = src_arr[r0_c, c1_c]
                v10 = src_arr[r1_c, c0_c]
                v11 = src_arr[r1_c, c1_c]
                
                if np.isnan(v00) or np.isnan(v01) or np.isnan(v10) or np.isnan(v11):
                    r_idx = int(np.clip(np.round(sr), 0, src_h - 1))
                    c_idx = int(np.clip(np.round(sc), 0, src_w - 1))
                    resampled_vals[tr, tc] = src_arr[r_idx, c_idx]
                else:
                    val = (v00 * (1 - dr) * (1 - dc) +
                           v01 * (1 - dr) * dc +
                           v10 * dr * (1 - dc) +
                           v11 * dr * dc)
                    resampled_vals[tr, tc] = val
                    
    resampled_conf = None
    if surface.confidence is not None:
        conf_arr = np.array([[np.nan if x is None else x for x in row] for row in surface.confidence], dtype=np.float32)
        resampled_conf = np.full((tgt_h, tgt_w), np.nan, dtype=np.float32)
        for tr in range(tgt_h):
            ty = t_maxy - (tr + 0.5) * (t_maxy - t_miny) / tgt_h
            for tc in range(tgt_w):
                tx = t_minx + (tc + 0.5) * (t_maxx - t_minx) / tgt_w
                if s_maxx > s_minx and s_maxy > s_miny:
                    sc = (tx - s_minx) * src_w / (s_maxx - s_minx) - 0.5
                    sr = (s_maxy - ty) * src_h / (s_maxy - s_miny) - 0.5
                else:
                    sc = tc * src_w / tgt_w - 0.5
                    sr = tr * src_h / tgt_h - 0.5
                
                r_idx = int(np.clip(np.round(sr), 0, src_h - 1))
                c_idx = int(np.clip(np.round(sc), 0, src_w - 1))
                resampled_conf[tr, tc] = conf_arr[r_idx, c_idx]
                
    surface.values = [[None if np.isnan(v) else float(v) for v in row] for row in resampled_vals.tolist()]
    if resampled_conf is not None:
        surface.confidence = [[None if np.isnan(v) else float(v) for v in row] for row in resampled_conf.tolist()]
    else:
        surface.confidence = None
        
    if not surface.provenance:
        surface.provenance = {}
    surface.provenance.update({
        "display_resampled": True,
        "resampling_method": method,
        "source_grid_hash": src_hash,
        "display_grid_hash": tgt_hash,
    })
    
    surface.grid_spec = dict(display_grid_spec)
    if existing_source_grid_spec is None:
        surface.source_grid_spec = dict(src_spec) if src_spec else None
    surface.display_grid_spec = dict(display_grid_spec)
    surface.grid_ref = f"{tgt_h}x{tgt_w}"
    
    return surface


def conserve_parent_cell_means(
    sharpened: np.ndarray,
    certified: np.ndarray,
    valid_highres: np.ndarray,
    row_parent: np.ndarray,
    col_parent: np.ndarray,
    clip_min: float,
    clip_max: float,
    *,
    max_iterations: int = 10,
    tolerance: float = 1e-4,
) -> Tuple[np.ndarray, float]:
    """Project high-resolution child means back to certified parent values.

    This is algebraically equivalent to the former nested parent-cell loop,
    but groups child pixels with ``bincount`` once per iteration.  The same
    correction, clipping, convergence tolerance, and mean-error definition are
    retained while avoiding one NumPy function call per parent cell.
    """
    base_h, base_w = certified.shape
    parent_ids = (
        row_parent[:, np.newaxis] * base_w + col_parent[np.newaxis, :]
    ).reshape(-1)
    certified_flat = certified.reshape(-1)
    values_flat = sharpened.reshape(-1)
    valid_flat = valid_highres.reshape(-1).astype(bool, copy=False)
    valid_flat &= np.isfinite(certified_flat[parent_ids])

    if not np.any(valid_flat):
        return sharpened, 0.0

    valid_parent_ids = parent_ids[valid_flat]
    n_parents = base_h * base_w
    counts = np.bincount(valid_parent_ids, minlength=n_parents).astype(float)
    eligible = (counts > 0) & np.isfinite(certified_flat)
    parent_mean_error = 0.0

    for _ in range(max_iterations):
        sums = np.bincount(
            valid_parent_ids,
            weights=values_flat[valid_flat],
            minlength=n_parents,
        )
        means = np.zeros(n_parents, dtype=float)
        means[eligible] = sums[eligible] / counts[eligible]
        corrections = means - certified_flat
        values_flat[valid_flat] = np.clip(
            values_flat[valid_flat] - corrections[valid_parent_ids],
            clip_min,
            clip_max,
        )

        post_sums = np.bincount(
            valid_parent_ids,
            weights=values_flat[valid_flat],
            minlength=n_parents,
        )
        post_means = np.zeros(n_parents, dtype=float)
        post_means[eligible] = post_sums[eligible] / counts[eligible]
        errors = np.abs(post_means[eligible] - certified_flat[eligible])
        parent_mean_error = float(np.mean(errors)) if errors.size else 0.0
        if errors.size == 0 or float(np.max(errors)) <= tolerance:
            break

    return sharpened, parent_mean_error


def get_layer10_cache_key(inp: Layer10Input, input_run_ids: Dict[str, str], l1_data: Optional[Any] = None) -> str:
    geom_hash = ""
    if inp.field_tensor:
        geom_hash = getattr(inp.field_tensor, "geometry_hash", "")
        if not geom_hash and hasattr(inp.field_tensor, "_context_package") and inp.field_tensor._context_package:
            geom_hash = getattr(inp.field_tensor._context_package, "geometry_hash", "")
            
    raster_ref_hashes = {}
    if l1_data and hasattr(l1_data, "raster_metadata"):
        for var, meta in sorted(l1_data.raster_metadata.items()):
            if var != var.lower():
                continue
            r_hash = {
                "raster_id": meta.get("raster_id", ""),
                "variable": meta.get("variable", ""),
                "content_hash": meta.get("content_hash", ""),
                "artifact_instance_hash": meta.get("artifact_instance_hash", ""),
                "resolution_m": meta.get("resolution_m", 10.0),
                "native_observation_resolution_m": meta.get("native_observation_resolution_m"),
                "certified_basis_m": meta.get("certified_basis_m"),
                "state_update_allowed": meta.get("state_update_allowed", False),
                "diagnostic_only": meta.get("diagnostic_only", True),
                "asmae_channel": meta.get("asmae_channel", "diagnostic"),
                "source_basis": meta.get("source_basis", ""),
                "confidence": meta.get("confidence"),
                "uncertainty": meta.get("uncertainty"),
                "retro_status": meta.get("retro_status"),
                "retrovalidation_score": meta.get("retrovalidation_score"),
                "bma_status": meta.get("bma_status"),
                "bma_disagreement": meta.get("bma_disagreement"),
                "cross_layer_conflict": meta.get("cross_layer_conflict"),
                "source_schema_version": meta.get("source_schema_version", ""),
                "warning_codes": meta.get("warning_codes"),
                "display_trust_tier": meta.get("display_trust_tier"),
                "visual_policy_version": meta.get("visual_policy_version"),
            }
            # Fallback grid hash if no content_hash
            if not r_hash["content_hash"] and hasattr(l1_data, "raster_maps"):
                grid = l1_data.raster_maps.get(var)
                if grid is not None:
                    r_hash["grid_hash"] = stable_grid_hash(grid)
            raster_ref_hashes[var] = r_hash

    # Hash raster maps that are present but did not have metadata
    if l1_data and hasattr(l1_data, "raster_maps"):
        for var, grid in sorted(l1_data.raster_maps.items()):
            var_lower = var.lower()
            if var_lower in raster_ref_hashes:
                continue
            raster_ref_hashes[var_lower] = {
                "variable": var_lower,
                "content_hash": "",
                "grid_hash": stable_grid_hash(grid),
                "metadata_present": False,
            }

    source_payload = {
        "input_run_ids": input_run_ids,
        "raster_ref_hashes": raster_ref_hashes,
        "surface_policy_version": "v82_1_truthfulness",
    }
    source_hash = hashlib.md5(json.dumps(source_payload, sort_keys=True).encode()).hexdigest()
    
    from rollout.rollout_policy import should_run_asmae, should_render_l10_asmae
    from rollout.asmae_rollout_registry import REGISTRY_SCHEMA_VERSION, get_rollout_phase, get_rollout_state
    
    payload = {
        "geometry_hash": geom_hash or inp.plot_id,
        "model_version": "10.5.0",
        "cache_schema_version": L10_CACHE_SCHEMA_VERSION,
        "surface_truthfulness_policy_version": SURFACE_TRUTHFULNESS_POLICY_VERSION,
        "display_trust_policy_version": DISPLAY_TRUST_POLICY_VERSION,
        "source_hash": source_hash,
        "visual_intensity": inp.visual_intensity,
        "requested_modes": sorted(inp.requested_modes) if inp.requested_modes else [],
        "render_profile": inp.render_profile,
        "user_mode": inp.user_mode,
        "asmae_backend_policy_enabled": should_run_asmae(inp.plot_id),
        "asmae_visual_policy_enabled": should_render_l10_asmae(inp.plot_id),
        "asmae_enabled_flag": os.environ.get("ASMAE_ENABLED", "false"),
        "l10_asmae_surfaces_enabled_flag": os.environ.get("L10_ASMAE_SURFACES_ENABLED", "false"),
        "environment": os.environ.get("ENVIRONMENT", "production"),
        "rollout_registry_version": REGISTRY_SCHEMA_VERSION,
        "rollout_phase": get_rollout_phase(inp.plot_id) if (inp.plot_id and isinstance(inp.plot_id, str) and inp.plot_id.strip()) else "disabled",
        "rollout_state": get_rollout_state(inp.plot_id) if (inp.plot_id and isinstance(inp.plot_id, str) and inp.plot_id.strip()) else "not_registered",
        "source_policy": inp.source_policy,
    }
    # V90.7.1: Hash metrics info if available
    from services.agribrain.layer05_asmae.history.archive_metrics_store import (
        ArchiveMetricsStore,
    )
    try:
        metrics_store = ArchiveMetricsStore()
        info = metrics_store.get_latest_metrics_info(inp.plot_id)
        if info:
            payload["archive_metrics_hash"] = info.get("archive_metrics_hash")
            payload["archive_run_id"] = info.get("archive_run_id")
            payload["archive_policy_version"] = info.get("archive_policy_version")
            payload["retrovalidation_policy_version"] = info.get("retrovalidation_policy_version")
            payload["archive_bma_policy_version"] = info.get("archive_bma_policy_version")
            payload["baseline_policy_version"] = info.get("baseline_policy_version")
    except ValueError:
        payload["archive_metrics_status"] = "malformed"
    except Exception as e:
        logger.warning(f"Metrics store access error for plot {inp.plot_id}: {e}")

    payload_str = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.md5(payload_str.encode()).hexdigest()


def deserialize_l10_output(d: dict) -> Layer10Output:
    # Reconstruct surfaces
    surfaces = []
    for s in d.get("surface_pack", []):
        surfaces.append(SurfaceArtifact(
            surface_id=s["surface_id"],
            semantic_type=SurfaceType(s["semantic_type"]),
            grid_ref=s["grid_ref"],
            values=s["values"],
            units=s["units"],
            native_resolution_m=s["native_resolution_m"],
            render_range=tuple(s["render_range"]) if s.get("render_range") else (0.0, 1.0),
            palette_id=PaletteId(s["palette_id"]) if s.get("palette_id") else PaletteId.RAW_GRAYSCALE,
            confidence=s.get("confidence"),
            source_weights=s.get("source_weights"),
            time_window=s.get("time_window", {}),
            source_layers=s.get("source_layers", []),
            provenance=s.get("provenance", {}),
            grounding_class=s.get("grounding_class"),
            raster_basis=s.get("raster_basis", []),
            observed_ratio=s.get("observed_ratio", 0.0),
            grid_spec=s.get("grid_spec"),
            source_grid_spec=s.get("source_grid_spec"),
            display_grid_spec=s.get("display_grid_spec"),
        ))
        
    # Reconstruct zones
    zones = []
    for z in d.get("zone_pack", []):
        zones.append(ZoneArtifact(
            zone_id=z["zone_id"],
            zone_type=ZoneType(z["zone_type"]),
            zone_family=ZoneFamily(z["zone_family"]),
            bbox=tuple(z["bbox"]) if z.get("bbox") else (0.0, 0.0, 0.0, 0.0),
            cell_indices=[tuple(c) for c in z["cell_indices"]] if z.get("cell_indices") else [],
            area_m2=z["area_m2"],
            area_pct=z["area_pct"],
            severity=z["severity"],
            confidence=z["confidence"],
            top_drivers=z.get("top_drivers", []),
            source_surface_type=z.get("source_surface_type", ""),
            description=z.get("description", ""),
            linked_findings=z.get("linked_findings", []),
            linked_actions=z.get("linked_actions", []),
            surface_stats=z.get("surface_stats", {}),
            time_window=z.get("time_window", {}),
            uncertainty_summary=z.get("uncertainty_summary", {}),
            label=z.get("label", ""),
            confidence_reasons=z.get("confidence_reasons", []),
            observed_cell_share=z.get("observed_cell_share", 0.0),
            gap_filled_share=z.get("gap_filled_share", 0.0),
            grid_validity=z.get("grid_validity", "unknown"),
            authority=z.get("authority", "algorithmic_scouting_region"),
            confidence_basis=z.get("confidence_basis", []),
            authority_block_reason=z.get("authority_block_reason"),
        ))
        
    # Reconstruct micro-objects
    micro_objects = []
    for mo in d.get("micro_objects", []):
        micro_objects.append(MicroObjectArtifact(
            object_id=mo["object_id"],
            object_type=ObjectType(mo["object_type"]),
            centroid=tuple(mo["centroid"]) if mo.get("centroid") else (0.0, 0.0),
            cell_indices=[tuple(c) for c in mo["cell_indices"]] if mo.get("cell_indices") else [],
            area_m2=mo["area_m2"],
            score=mo["score"],
            confidence=mo["confidence"],
            measurements=mo.get("measurements", {}),
            derived_from=mo.get("derived_from", ""),
        ))
        
    # Reconstruct histogram bundle
    hb = d.get("histogram_bundle", {})
    field_hists = []
    for h in hb.get("field_histograms", []):
        field_hists.append(HistogramArtifact(
            surface_type=SurfaceType(h["surface_type"]),
            region_id=h["region_id"],
            bin_edges=h["bin_edges"],
            bin_counts=h["bin_counts"],
            total_pixels=h["total_pixels"],
            valid_pixels=h["valid_pixels"],
            mean=h.get("mean", 0.0),
            median=h.get("median", 0.0),
            std=h.get("std", 0.0),
            p10=h.get("p10", 0.0),
            p90=h.get("p90", 0.0),
            skewness=h.get("skewness", 0.0),
            is_bimodal=h.get("is_bimodal", False),
            bimodal_threshold=h.get("bimodal_threshold"),
        ))
        
    zone_hists = []
    for h in hb.get("zone_histograms", []):
        zone_hists.append(HistogramArtifact(
            surface_type=SurfaceType(h["surface_type"]),
            region_id=h["region_id"],
            bin_edges=h["bin_edges"],
            bin_counts=h["bin_counts"],
            total_pixels=h["total_pixels"],
            valid_pixels=h["valid_pixels"],
            mean=h.get("mean", 0.0),
            median=h.get("median", 0.0),
            std=h.get("std", 0.0),
            p10=h.get("p10", 0.0),
            p90=h.get("p90", 0.0),
            skewness=h.get("skewness", 0.0),
            is_bimodal=h.get("is_bimodal", False),
            bimodal_threshold=h.get("bimodal_threshold"),
        ))
        
    delta_hists = []
    for dh in hb.get("delta_histograms", []):
        delta_hists.append(DeltaHistogram(
            surface_type=SurfaceType(dh["surface_type"]),
            region_id=dh["region_id"],
            date_from=dh["date_from"],
            date_to=dh["date_to"],
            bin_edges=dh["bin_edges"],
            bin_counts=dh["bin_counts"],
            mean_change=dh.get("mean_change", 0.0),
            shift_direction=dh.get("shift_direction", "STABLE"),
        ))
        
    unc_hists = []
    for h in hb.get("uncertainty_histograms", []):
        unc_hists.append(HistogramArtifact(
            surface_type=SurfaceType(h["surface_type"]),
            region_id=h["region_id"],
            bin_edges=h["bin_edges"],
            bin_counts=h["bin_counts"],
            total_pixels=h["total_pixels"],
            valid_pixels=h["valid_pixels"],
            mean=h.get("mean", 0.0),
            median=h.get("median", 0.0),
            std=h.get("std", 0.0),
            p10=h.get("p10", 0.0),
            p90=h.get("p90", 0.0),
            skewness=h.get("skewness", 0.0),
            is_bimodal=h.get("is_bimodal", False),
            bimodal_threshold=h.get("bimodal_threshold"),
        ))
        
    source_hists = []
    for h in hb.get("source_histograms", []):
        source_hists.append(HistogramArtifact(
            surface_type=SurfaceType(h["surface_type"]),
            region_id=h["region_id"],
            bin_edges=h["bin_edges"],
            bin_counts=h["bin_counts"],
            total_pixels=h["total_pixels"],
            valid_pixels=h["valid_pixels"],
            mean=h.get("mean", 0.0),
            median=h.get("median", 0.0),
            std=h.get("std", 0.0),
            p10=h.get("p10", 0.0),
            p90=h.get("p90", 0.0),
            skewness=h.get("skewness", 0.0),
            is_bimodal=h.get("is_bimodal", False),
            bimodal_threshold=h.get("bimodal_threshold"),
        ))
        
    hist_bundle = HistogramBundle(
        field_histograms=field_hists,
        zone_histograms=zone_hists,
        delta_histograms=delta_hists,
        uncertainty_histograms=unc_hists,
        source_histograms=source_hists,
    )
    
    # Reconstruct render manifest
    rm_raw = d.get("render_manifest", {})
    available_modes = []
    for m in rm_raw.get("available_modes", []):
        legend = []
        for le in m.get("legend", []):
            legend.append(LegendEntry(
                label=le["label"],
                color=le["color"],
                value_range=tuple(le["value_range"]) if le.get("value_range") else None,
            ))
        available_modes.append(MapModeDef(
            mode=RenderMode(m["mode"]),
            display_name=m["display_name"],
            surface_ids=m["surface_ids"],
            palette_id=PaletteId(m["palette_id"]),
            legend=legend,
            requires_resolution_m=m.get("requires_resolution_m"),
            enabled=m.get("enabled", True),
            description=m.get("description", ""),
        ))
    render_manifest = RenderManifest(
        available_modes=available_modes,
        active_mode=RenderMode(rm_raw.get("active_mode", "VIGOR")),
        style_pack=rm_raw.get("style_pack", "AGRO_POP"),
        show_confidence_fog=rm_raw.get("show_confidence_fog", False),
        show_zone_boundaries=rm_raw.get("show_zone_boundaries", True),
    )
    
    # Reconstruct quality report
    qr_raw = d.get("quality_report", {})
    quality_report = QualityReport(
        degradation_mode=SIREDegradation(qr_raw.get("degradation_mode", "NORMAL")),
        reliability_score=qr_raw.get("reliability_score", 1.0),
        surfaces_generated=qr_raw.get("surfaces_generated", 0),
        surfaces_skipped=qr_raw.get("surfaces_skipped", 0),
        zones_generated=qr_raw.get("zones_generated", 0),
        micro_objects_detected=qr_raw.get("micro_objects_detected", 0),
        grid_alignment_ok=qr_raw.get("grid_alignment_ok", True),
        detail_conservation_ok=qr_raw.get("detail_conservation_ok", True),
        zone_state_by_surface=qr_raw.get("zone_state_by_surface", {}),
        missing_upstream=qr_raw.get("missing_upstream", []),
        warnings=qr_raw.get("warnings", []),
        component_failures=[
            ComponentFailure(**failure)
            for failure in (qr_raw.get("component_failures") or [])
            if isinstance(failure, dict)
        ],
        degradation_codes=list(qr_raw.get("degradation_codes") or []),
    )
    
    # Reconstruct temporal bundle
    tb_raw = d.get("temporal_bundle", {})
    slices = []
    for s in tb_raw.get("slices", []):
        slices.append(TemporalSlice(
            date=s["date"],
            day_offset=s["day_offset"],
            surface_type=SurfaceType(s["surface_type"]),
            values=s["values"],
            is_forecast=s.get("is_forecast", False),
            confidence=s.get("confidence", 1.0),
            source=s.get("source", ""),
        ))
    temporal_bundle = TemporalBundle(
        slices=slices,
        reference_date=tb_raw.get("reference_date", ""),
        lookback_days=tb_raw.get("lookback_days", 7),
        lookahead_days=tb_raw.get("lookahead_days", 7),
        trend_summary=tb_raw.get("trend_summary", {}),
        temporal_quality=tb_raw.get("temporal_quality", 1.0),
        forecast_source=tb_raw.get("forecast_source", ""),
    )
    

    return Layer10Output(
        run_id=d["run_id"],
        publication_run_id=d.get("publication_run_id", ""),
        request_run_id=d.get("request_run_id", ""),
        publication_id=d.get("publication_id", ""),
        publication_status=d.get("publication_status", "INVALID_PUBLICATION"),
        surface_schema_version=d.get("surface_schema_version", ""),
        timestamp=d["timestamp"],
        input_run_ids=d.get("input_run_ids", {}),
        surface_pack=surfaces,
        zone_pack=zones,
        micro_objects=micro_objects,
        histogram_bundle=hist_bundle,
        render_manifest=render_manifest,
        quicklooks=d.get("quicklooks", {}),
        raster_pack=d.get("raster_pack", []),
        vector_pack=d.get("vector_pack", []),
        tile_manifest=d.get("tile_manifest", {}),
        quality_report=quality_report,
        provenance=d.get("provenance", {}),
        resolved_crop_stage=d.get("resolved_crop_stage", "UNKNOWN"),
        phenology_context=d.get("phenology_context", {}),
        explainability_pack=d.get("explainability_pack", {}),
        temporal_bundle=temporal_bundle,
        scenario_pack=d.get("scenario_pack", []),
        history_pack=d.get("history_pack", []),
        ground_truth_summary=d.get("ground_truth_summary", {}),
        visual_source=d.get("visual_source", {}),
        surface_inventory=d.get("surface_inventory", {}),
        mode_surface_plan=d.get("mode_surface_plan", {}),
        # V92.4-BC.1: Preserve display ladder from cache
        mode_display_state=d.get("mode_display_state", {}),
        source_policy_display_state=d.get("source_policy_display_state", {}),
        asmae_evidence_state=d.get("asmae_evidence_state", {}),
        core_asmae_evidence_state=d.get(
            "core_asmae_evidence_state", d.get("asmae_evidence_state", {})
        ),
        publication_surface_state=d.get("publication_surface_state", {}),
        publication_demotion=d.get("publication_demotion", {}),
        asmae_feature_pack=d.get("asmae_feature_pack", {}),
        asmae_plot_state_artifact=d.get("asmae_plot_state_artifact", {}),
        surface_behavior_proof=d.get("surface_behavior_proof", {}),
        display_trace=d.get("display_trace", {}),
        asmae_proof=d.get("asmae_proof", {}) or build_default_asmae_proof(),
        render_authorizations=d.get("render_authorizations", {}),
        render_authorization_version=d.get(
            "render_authorization_version", RENDER_AUTHORIZATION_VERSION
        ),
    )


def validate_layer10_publication(output: Optional[Layer10Output]) -> bool:
    """Central publication integrity validator."""
    if output is None or not hasattr(output, "provenance"):
        return False
    declared_valid, _derived, _reason = validate_declared_publication_status(output)
    prov = getattr(output, "provenance", {}) or {}
    return bool(
        declared_valid
        and prov.get("layer10_publication_schema_version")
        == LAYER10_PUBLICATION_SCHEMA_VERSION
    )


def save_layer10_to_cache(cache_key: str, output: Layer10Output) -> int:
    if not validate_layer10_publication(output):
        logger.warning("[L10] Cache write BLOCKED: publication fails validate_layer10_publication for key %s", cache_key[:16])
        return 0
    if not output.surface_pack:
        logger.info("[L10] Cache write skipped for authoritative terminal no-data publication")
        return 0

    if output and output.surface_pack:
        sanitize_surface_values(output.surface_pack)
    npz_path_tmp = None
    json_path_tmp = None
    npz_path = None
    cache_path = None
    try:
        from dataclasses import asdict
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cache_dir_name = "historical_surfaces_cache" if os.environ.get("AGRIWISE_ARCHIVE_PILOT_MODE") == "true" else "surfaces_cache"
        cache_dir = os.path.join(base_dir, "artifacts", cache_dir_name)
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, f"{cache_key}.json")
        npz_path = os.path.join(cache_dir, f"surfaces_{cache_key}.npz")
        
        # Extract numeric grids before dataclass serialization.  ``asdict``
        # recursively copied both surface_pack and raster_pack grids (more than
        # two million Python scalar objects on the affected plot) even though
        # surface grids are stored in NPZ immediately afterwards.  Temporarily
        # detach those duplicate values, serialize metadata, then restore the
        # live output object in a finally block.
        npz_data = {}
        detached = []
        for surface in output.surface_pack:
            s_id = getattr(surface, "surface_id", "")
            if not s_id:
                continue

            vals = getattr(surface, "values", None)
            if vals is not None:
                npz_data[f"values::{s_id}"] = np.asarray(vals, dtype=np.float32)
                detached.append((surface, "values", vals))
                surface.values = []

            conf = getattr(surface, "confidence", None)
            if conf is not None:
                npz_data[f"confidence::{s_id}"] = np.asarray(conf, dtype=np.float32)
                detached.append((surface, "confidence", conf))
                surface.confidence = None

        for raster_entry in output.raster_pack or []:
            if isinstance(raster_entry, dict) and "values" in raster_entry:
                vals = raster_entry.get("values")
                detached.append((raster_entry, "values", vals))
                raster_entry["values"] = []
            elif hasattr(raster_entry, "values"):
                vals = raster_entry.values
                detached.append((raster_entry, "values", vals))
                raster_entry.values = []

        try:
            serialized = asdict(output)
        finally:
            for owner, field_name, value in detached:
                if isinstance(owner, dict):
                    owner[field_name] = value
                else:
                    setattr(owner, field_name, value)
        
        # Define tmp paths for atomic rename
        npz_path_tmp = npz_path.replace(".npz", ".tmp.npz")
        json_path_tmp = cache_path.replace(".json", ".tmp.json")
        
        # 1. Save NPZ to tmp
        if npz_data:
            np.savez_compressed(npz_path_tmp, **npz_data)
            serialized["surfaces_artifact_ref"] = f"{cache_dir_name}/surfaces_{cache_key}.npz"
            
        # 2. Save JSON to tmp
        with open(json_path_tmp, "w", encoding="utf-8") as f:
            json.dump(serialized, f, separators=(",", ":"), default=str)
            
        # 3. Atomic replace NPZ
        if npz_data:
            os.replace(npz_path_tmp, npz_path)
            
        # 4. Atomic replace JSON
        os.replace(json_path_tmp, cache_path)
            
        # Compute total storage size in bytes
        total_bytes = os.path.getsize(cache_path)
        if os.path.exists(npz_path):
            total_bytes += os.path.getsize(npz_path)
        return total_bytes
    except Exception as e:
        import sys
        print(f"[L10] Failed to write surfaces cache: {e}", file=sys.stderr)
        # Cleanup any temporary files on failure
        if npz_path_tmp and os.path.exists(npz_path_tmp):
            try: os.remove(npz_path_tmp)
            except Exception: pass
        if json_path_tmp and os.path.exists(json_path_tmp):
            try: os.remove(json_path_tmp)
            except Exception: pass
        if npz_path and os.path.exists(npz_path):
            try: os.remove(npz_path)
            except Exception: pass
        if cache_path and os.path.exists(cache_path):
            try: os.remove(cache_path)
            except Exception: pass
        return 0


def load_layer10_from_cache(cache_key: str) -> Optional[Layer10Output]:
    # Ignore .tmp files during cache load
    if cache_key.endswith(".tmp"):
        return None
        
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cache_dir_name = "historical_surfaces_cache" if os.environ.get("AGRIWISE_ARCHIVE_PILOT_MODE") == "true" else "surfaces_cache"
        cache_path = os.path.join(base_dir, "artifacts", cache_dir_name, f"{cache_key}.json")
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            
            # Check rollout registry if ASMAE surfaces are cached
            has_asmae_cached = False
            for s_dict in d.get("surface_pack", []):
                sem_type = s_dict.get("semantic_type", "")
                if isinstance(sem_type, dict):
                    sem_val = sem_type.get("value", "")
                elif isinstance(sem_type, str):
                    sem_val = sem_type
                else:
                    sem_val = getattr(sem_type, "value", str(sem_type))
                if sem_val.startswith("ASMAE_"):
                    has_asmae_cached = True
                    break
            
            if has_asmae_cached:
                plot_id = d.get("plot_id", "default")
                from rollout.rollout_policy import should_render_l10_asmae
                
                if not should_render_l10_asmae(plot_id):
                    # Cache contains ASMAE surfaces, but visuals are disabled for this plot: return miss
                    return None
            
            # Rehydrate from NPZ if present
            npz_ref = d.get("surfaces_artifact_ref")
            if npz_ref:
                npz_path = os.path.join(base_dir, "artifacts", npz_ref)
                if not os.path.exists(npz_path):
                    # Missing NPZ: safe cache miss
                    return None
                
                try:
                    with safe_np_load(npz_path) as data:
                        # 1. Surface count check
                        npz_val_keys = [k for k in data.keys() if k.startswith("values::")]
                        if len(npz_val_keys) != len(d.get("surface_pack", [])):
                            # Surface count mismatch
                            return None
                            
                        # 2. Rehydrate by surface_id
                        for s_dict in d.get("surface_pack", []):
                            s_id = s_dict.get("surface_id")
                            if not s_id:
                                continue
                            
                            val_key = f"values::{s_id}"
                            if val_key not in data:
                                # NPZ missing required surface ID
                                return None
                            
                            arr = data[val_key]
                            # 2D shape validation
                            if len(arr.shape) != 2:
                                return None
                                
                            s_dict["values"] = [[None if np.isnan(val) else float(val) for val in row] for row in arr.tolist()]
                            
                            conf_key = f"confidence::{s_id}"
                            if conf_key in data:
                                arr_conf = data[conf_key]
                                # 2D shape validation
                                if len(arr_conf.shape) != 2:
                                    return None
                                s_dict["confidence"] = [[None if np.isnan(val) else float(val) for val in row] for row in arr_conf.tolist()]

                        # raster_pack is a compatibility projection of the
                        # same SurfaceArtifact values.  Its duplicate grids are
                        # omitted from JSON and rebound to the rehydrated
                        # surface lists so cache hits remain output-equivalent.
                        values_by_surface_id = {
                            s_dict.get("surface_id"): s_dict.get("values", [])
                            for s_dict in d.get("surface_pack", [])
                            if s_dict.get("surface_id")
                        }
                        for raster_entry in d.get("raster_pack", []) or []:
                            surface_id = raster_entry.get("surface_id")
                            if surface_id in values_by_surface_id:
                                raster_entry["values"] = values_by_surface_id[surface_id]
                except Exception as e:
                    # Corrupted NPZ or read error: safe cache miss
                    import sys
                    print(f"[L10] Failed to load/rehydrate from NPZ: {e}", file=sys.stderr)
                    return None
            
            try:
                os.utime(cache_path, None)
            except Exception:
                pass
            restored = deserialize_l10_output(d)
            if not validate_layer10_publication(restored):
                return None
            return restored
    except Exception as e:
        import sys
        print(f"[L10] Failed to load surfaces cache: {e}", file=sys.stderr)
    return None


def run_layer10_sire(l10_input: Layer10Input) -> Layer10Output:
    """
    Run the full SIRE pipeline with caching, budgets, and quick modes.
    """
    import os
    os.environ["L10_DISABLE_LIVE_VISUAL_PROVIDERS_IN_SURFACE_RUN"] = "true"
    os.environ["L10_EXTERNAL_PROVIDER_TIMEOUT_MS"] = "500"

    start_time = time.perf_counter()
    is_quick_visual = "quick_visual" in l10_input.requested_modes or l10_input.user_mode == "quick_visual"
    
    # Determine budget
    if is_quick_visual:
        budget_ms = 500.0
    elif "standard" in l10_input.requested_modes:
        budget_ms = 2000.0
    else:
        budget_ms = 10000.0

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    performance_timers_ms: Dict[str, Optional[float]] = {}
    _phase_started = time.perf_counter()

    # --- Step 0: Adapt upstream outputs through proper adapters ---
    l1_data = adapt_l1(l10_input.field_tensor, l10_input.grid_height, l10_input.grid_width, skip_idw=is_quick_visual)
    l2_data = adapt_l2(l10_input.veg_int)
    l3_data = adapt_l3(l10_input.decision)
    l4_data = adapt_l4(l10_input.nutrients)
    l5_data = adapt_l5(l10_input.bio)
    l6_data = adapt_l6(l10_input.exec_state)
    l7_data = adapt_l7(l10_input.planning)
    l8_data = adapt_l8(l10_input.prescriptive)
    l9_data = adapt_l9(l10_input.interface)
    performance_timers_ms["adaptation"] = round((time.perf_counter() - _phase_started) * 1000.0, 3)

    # Use adapted grid dimensions (from actual grid_spec if available)
    H = l1_data.height
    W = l1_data.width
    l10_input.grid_height = H
    l10_input.grid_width = W
    l10_input.resolution_m = l1_data.resolution_m

    # V92.4 GIS display grid spec definitions
    display_grid_spec = {}
    grid_spec_status = "ok"
    render_as_spatial = True
    
    # Validate all spatial proof, not just the shape of the bounds tuple.
    gs = getattr(l1_data, "grid_spec", None)
    real_bounds_exist, grid_spec_status = validate_spatial_grid_spec(gs, W, H)
    field_polygon, field_geometry_status = _extract_valid_field_polygon(l10_input.field_tensor, explicit_geometry=getattr(l10_input, "field_geometry", None))
    if real_bounds_exist and field_polygon is None:
        real_bounds_exist = False
        grid_spec_status = field_geometry_status

    if l1_data and gs and real_bounds_exist:
        if isinstance(gs, dict):
            display_grid_spec = {
                "crs": gs.get("crs", "EPSG:4326"),
                "transform": gs.get("transform", (0.0, 1.0, 0.0, 0.0, 0.0, 1.0)),
                "width": gs.get("width", W),
                "height": gs.get("height", H),
                "bounds": gs.get("bounds", (0.0, 0.0, float(W), float(H))),
                "resolution": gs.get("resolution", gs.get("resolution_m", l1_data.resolution_m))
            }
        else:
            display_grid_spec = gs.to_dict() if hasattr(gs, "to_dict") else dict(
                crs=getattr(gs, "crs", "EPSG:4326"),
                transform=getattr(gs, "transform", (0.0, 1.0, 0.0, 0.0, 0.0, 1.0)),
                width=getattr(gs, "width", W),
                height=getattr(gs, "height", H),
                bounds=getattr(gs, "bounds", (0.0, 0.0, float(W), float(H))),
                resolution=getattr(gs, "resolution", l1_data.resolution_m)
            )
    else:
        render_as_spatial = False
        display_grid_spec = {
            "crs": "EPSG:4326",
            "transform": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            "bounds": (0.0, 0.0, 0.0, 0.0),
            "resolution": l1_data.resolution_m
        }
        
    display_grid_spec.update({
        "width": W,
        "height": H,
        "resolution_m": l1_data.resolution_m
    })
    display_grid_spec["grid_hash"] = stable_grid_hash(l1_data.raster_maps.get("ndvi") if (l1_data and hasattr(l1_data, "raster_maps")) else None)


    # Collect upstream run IDs
    input_run_ids = {
        k: v for k, v in {
            'L1': l1_data.run_id, 'L2': l2_data.run_id, 'L3': l3_data.run_id,
            'L4': l4_data.run_id, 'L5': l5_data.run_id, 'L6': l6_data.run_id,
            'L7': l7_data.run_id, 'L8': l8_data.run_id,
        }.items() if v
    }

    run_id = _deterministic_run_id(l10_input, input_run_ids)

    # --- Check Cache ---
    cache_key = get_layer10_cache_key(l10_input, input_run_ids, l1_data)
    if "scientific_refresh" in l10_input.requested_modes:
        cache_status = "bypass"
        logger.info("Bypassing L10 cache read for scientific_refresh mode")
    else:
        cached_out = load_layer10_from_cache(cache_key)
        if cached_out is not None:
            # Preserve the cached scientific run/publication identity. The
            # current execution request is separate provenance only.
            cached_out.request_run_id = run_id
            cached_out.provenance = dict(cached_out.provenance or {})
            cached_out.provenance["request_run_id"] = run_id
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            observability_registry.record(
                step="layer10",
                mode="quick_visual" if is_quick_visual else "standard",
                cache_status="hit",
                latency_ms=elapsed_ms,
                budget_ms=budget_ms,
            )
            return cached_out

    # A raster without an admitted geographic grid is not a spatial product.
    # Stop before surface generators, masks, histograms, zones, temporal
    # rasters, render manifests, quicklooks, or exports can manufacture map
    # semantics from row/column indices.  Plot-level intelligence remains
    # available from the upstream/global contracts outside this empty L10 pack.
    if not render_as_spatial:
        invalid_reason = f"invalid_geospatial_grid:{grid_spec_status}"
        requested_policy = l10_input.source_policy or "satellite"
        if requested_policy == "asmae":
            requested_policy = "asmae_diagnostic"
        mode_keys = (
            "canopy",
            "veg_attention",
            "water_stress",
            "nutrient_risk",
            "salinity",
            "disease_risk",
            "yield_forecast",
            "risk",
            "uncertainty",
            "resolution_coverage",
        )
        blocked_mode_state = {
            mode: {
                "displayLevel": "plot_level",
                "authorityLevel": "monitor",
                "selectedSurfaceType": None,
                "isSpatial": False,
                "canRenderPixels": False,
                "renderKind": "none",
                "reason": invalid_reason,
                "trustBadges": ["plot-level estimate"],
            }
            for mode in mode_keys
        }
        asmae_state = dict(getattr(l1_data, "asmae_evidence_state", {}) or {})
        asmae_state["spatial_materialization_allowed"] = False
        asmae_state["spatial_materialization_block_reason"] = invalid_reason
        output = Layer10Output(
            run_id=run_id,
            publication_run_id=run_id,
            request_run_id=run_id,
            publication_id=f"pub_{cache_key[:16]}",
            surface_schema_version=SURFACES_SCHEMA_VERSION,
            timestamp=ts,
            input_run_ids=input_run_ids,
            surface_pack=[],
            zone_pack=[],
            micro_objects=[],
            histogram_bundle=HistogramBundle(),
            render_manifest=RenderManifest(available_modes=[]),
            quality_report=QualityReport(
                degradation_mode=SIREDegradation.DEGRADED,
                reliability_score=0.0,
                surfaces_generated=0,
                surfaces_skipped=0,
                zones_generated=0,
                micro_objects_detected=0,
                grid_alignment_ok=False,
                detail_conservation_ok=False,
                warnings=[invalid_reason, "spatial_processing_short_circuited"],
            ),
            provenance={
                "pipeline": "SIRE_v11.0",
                "agribrain_run_id": run_id,
                "intelligence_snapshot_id": run_id,
                "generated_at": ts,
                "surface_schema_version": SURFACES_SCHEMA_VERSION,
                "publication_run_id": run_id,
                "request_run_id": run_id,
                "publication_id": f"pub_{cache_key[:16]}",
                "layer10_publication_schema_version": LAYER10_PUBLICATION_SCHEMA_VERSION,
                "policy_model": "canonical_science_with_client_views",
                "degradation": SIREDegradation.DEGRADED.value,
                "grid": f"{H}x{W}@{l10_input.resolution_m}m",
                "grid_bounds": None,
                "grid_validity": f"invalid:{grid_spec_status}",
                "grid_spec_status": grid_spec_status,
                "spatial_materialization_allowed": False,
                "spatial_processing_short_circuited": True,
                "spatial_processing_block_reason": invalid_reason,
                "performance_timers_ms": {
                    **performance_timers_ms,
                    "total_before_serialization": round(
                        (time.perf_counter() - start_time) * 1000.0, 3
                    ),
                },
            },
            mode_display_state=blocked_mode_state,
            source_policy_display_state={
                "requested_policy": requested_policy,
                "resolved_policy": requested_policy,
                "fallback_reason": invalid_reason,
                "materialization_block_reason": invalid_reason,
                "one_meter_advisory_coverage_pct": None,
                "one_meter_physics_coverage_pct": None,
                "model_assisted_2_5m_coverage_pct": None,
                "generalized_5m_coverage_pct": None,
                "experimentalVisualLadder": None,
                "asmaeApprovalLadder": {
                    "oneMeterAsmaeApprovalPct": None,
                    "modelAssisted2_5mPct": None,
                    "generalized5mPct": None,
                    "unavailableReason": invalid_reason,
                },
            },
            asmae_evidence_state=asmae_state,
            core_asmae_evidence_state=dict(asmae_state),
            publication_surface_state={
                "state": "terminal_no_spatial_publication",
                "authority": "display_inventory_only",
                "surface_available": False,
                "reason": invalid_reason,
            },
            publication_demotion={
                "applied": True,
                "reason": invalid_reason,
                "publication_state": "terminal_no_spatial_publication",
            },
            asmae_feature_pack={},
            surface_behavior_proof={
                "active_surface_type": None,
                "active_policy": requested_policy,
                "source_signal_used": None,
                "target_shape": None,
                "native_resolution_m": None,
                "finite_pct": 0.0,
            },
            display_trace={
                "requested_policy": requested_policy,
                "resolved_policy": requested_policy,
                "active_surface_type_backend": None,
                "available_surface_types": [],
                "experimental_visual_surface_used": None,
            },
            asmae_proof=build_default_asmae_proof(),
            render_authorizations=build_no_data_render_authorizations(),
        )
        derived_status, _ = classify_surface_publication(output)
        output.publication_status = derived_status
        output.provenance["publication_status"] = derived_status
        save_layer10_to_cache(cache_key, output)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        observability_registry.record(
            step="layer10",
            mode="quick_visual" if is_quick_visual else "standard",
            cache_status="miss",
            latency_ms=elapsed_ms,
            budget_ms=budget_ms,
        )
        return output

    # --- Determine degradation mode ---
    degradation = SIREDegradation.NORMAL if render_as_spatial else SIREDegradation.NO_SPATIAL
    missing = []
    component_failures: List[ComponentFailure] = []
    degradation_codes: List[str] = []

    def _has_renderable_raster(l1) -> bool:
        if not l1: return False
        r_maps = getattr(l1, "raster_maps", {})
        for k in ["NDVI", "NDVI_CLEAN", "ndvi", "NDMI", "SAR", "QUALITY"]:
            if k in r_maps:
                v = r_maps[k]
                if isinstance(v, dict) and "values" in v: v = v["values"]
                if v and isinstance(v, list) and isinstance(v[0], list):
                    for row in v:
                        for cell in row:
                            if cell is not None:
                                return True
        return False

    has_raster = _has_renderable_raster(l1_data)

    if l10_input.field_tensor is None and not has_raster:
        degradation = SIREDegradation.DATA_GAP
        missing.append("L1")
    if l10_input.veg_int is None and not has_raster:
        degradation = SIREDegradation.DATA_GAP
        missing.append("L2")

    has_downstream = any([
        l10_input.decision, l10_input.nutrients, l10_input.bio,
        l10_input.planning, l10_input.prescriptive,
    ])
    if not has_downstream and degradation == SIREDegradation.NORMAL:
        degradation = SIREDegradation.L1_ONLY

    # --- Step 1: Generate surfaces (adapter-based, spatial-first) ---
    _phase_started = time.perf_counter()
    surfaces = []
    skipped = 0

    # Always: vegetation + uncertainty (require L1/L2 adapters)
    try:
        veg_surfaces = generate_vegetation_surfaces(
            l10_input, H, W, l1_data=l1_data, l2_data=l2_data
        )
        surfaces.extend(veg_surfaces)
    except Exception:
        skipped += 4

    # Canonical NDVI dependency masks. These are first-class surfaces so every
    # renderer, histogram and inspector references the same exact contract.
    ndvi_mask_diagnostic = {"status": "not_attempted"}
    try:
        ndvi_surface = next(
            (s for s in surfaces if (s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type)) == "NDVI_CLEAN"),
            None,
        )
        observed_masks = getattr(l1_data, "observed_masks", {}) or {}
        observed_raw = next(
            (
                observed_masks[key]
                for key in ("ndvi", "NDVI", "ndvi_clean", "NDVI_CLEAN")
                if key in observed_masks and observed_masks[key] is not None
            ),
            None,
        )
        if observed_raw is None:
            # Keep the lookup tied to the NDVI surface's declared raster basis;
            # adapters preserve the original provider mask under that source key.
            for basis_key in getattr(ndvi_surface, "raster_basis", []) or []:
                for key in (basis_key, str(basis_key).lower(), str(basis_key).upper()):
                    if key in observed_masks and observed_masks[key] is not None:
                        observed_raw = observed_masks[key]
                        break
                if observed_raw is not None:
                    break
        if observed_raw is None:
            # Provider adapters also use channel-qualified names such as
            # sentinel2_ndvi_mean. Prefer those raw NDVI masks over any ASMAE
            # or experimental derivative.
            ndvi_mask_keys = sorted(
                key
                for key in observed_masks
                if "NDVI" in str(key).upper()
                and "ASMAE" not in str(key).upper()
                and "EXPERIMENTAL" not in str(key).upper()
            )
            if ndvi_mask_keys:
                observed_raw = observed_masks[ndvi_mask_keys[0]]
        if ndvi_surface is not None:
            final_arr = np.asarray(ndvi_surface.values, dtype=float)
            if final_arr.ndim != 2 or final_arr.size == 0:
                raise ValueError("NDVI_CLEAN values must be a non-empty 2D grid")
            if final_arr.shape != (H, W):
                row_idx = np.linspace(0, final_arr.shape[0] - 1, H).astype(int)
                col_idx = np.linspace(0, final_arr.shape[1] - 1, W).astype(int)
                final_arr = final_arr[np.ix_(row_idx, col_idx)]
            final_finite_arr = np.isfinite(final_arr)

            # Missing raw support is a meaningful fail-closed state, not a
            # reason to omit the dependency surfaces.  Every NDVI_CLEAN
            # publication carries the same immutable mask trio; without a
            # source support mask none of its finite cells may be promoted to
            # spatially valid merely because a plot-level value was broadcast.
            source_support_available = observed_raw is not None
            observed_arr = np.zeros((H, W), dtype=bool)
            if source_support_available:
                raw_arr = np.asarray(observed_raw)
                if raw_arr.ndim != 2 or raw_arr.size == 0:
                    source_support_available = False
                else:
                    if raw_arr.dtype == np.bool_:
                        observed_arr = raw_arr.astype(bool, copy=True)
                    else:
                        numeric_raw = np.asarray(raw_arr, dtype=float)
                        observed_arr = np.isfinite(numeric_raw) & (numeric_raw != 0.0)
                    if observed_arr.shape != (H, W):
                        row_idx = np.linspace(0, observed_arr.shape[0] - 1, H).astype(int)
                        col_idx = np.linspace(0, observed_arr.shape[1] - 1, W).astype(int)
                        observed_arr = observed_arr[np.ix_(row_idx, col_idx)]

            spatial_support_valid = bool(render_as_spatial and source_support_available)
            valid_arr = (
                final_finite_arr.copy()
                if spatial_support_valid
                else np.zeros((H, W), dtype=bool)
            )
            observed_arr &= valid_arr
            gap_arr = valid_arr & ~observed_arr
            mask_specs = (
                (SurfaceType.OBSERVED_DATA_MASK_NDVI, observed_arr, "raw_provider_cell_before_interpolation"),
                (SurfaceType.GAP_FILL_MASK_NDVI, gap_arr, "final_value_present_raw_cell_absent"),
                (SurfaceType.VALID_DATA_MASK_NDVI, valid_arr, "final_value_usable"),
            )
            for mask_type, mask_arr, definition in mask_specs:
                surfaces.append(SurfaceArtifact(
                    surface_id=f"{mask_type.value}_{l10_input.plot_id}",
                    semantic_type=mask_type,
                    grid_ref=f"{H}x{W}",
                    values=mask_arr.astype(float).tolist(),
                    units="binary_mask",
                    native_resolution_m=l10_input.resolution_m,
                    render_range=(0.0, 1.0),
                    palette_id=PaletteId.RAW_GRAYSCALE,
                    source_layers=["L1"],
                    grounding_class=GroundingClass.RASTER_GROUNDED.value,
                    raster_basis=["ndvi"],
                    observed_ratio=float(np.mean(observed_arr)),
                    provenance={
                        "definition": (
                            "unavailable_without_valid_geographic_grid"
                            if mask_type == SurfaceType.VALID_DATA_MASK_NDVI and not render_as_spatial
                            else (
                                "unavailable_without_provider_observation_support"
                                if mask_type == SurfaceType.VALID_DATA_MASK_NDVI and not source_support_available
                                else definition
                            )
                        ),
                        "aligned_surface_type": "NDVI_CLEAN",
                        "surface_role": "render_dependency",
                        "render_dependency": True,
                        "selectable": False,
                        "inspector_allowed": False,
                        "source_support_available": source_support_available,
                        "grid_validity": "valid" if render_as_spatial else f"invalid:{grid_spec_status}",
                        "authority_block_reason": (
                            None
                            if spatial_support_valid
                            else (
                                "provider_observation_support_unavailable"
                                if render_as_spatial
                                else f"invalid_geospatial_grid:{grid_spec_status}"
                            )
                        ),
                    },
                ))
            ndvi_mask_diagnostic = {
                "status": "generated",
                "source_support_available": source_support_available,
                "observed_mask_keys": sorted(str(key) for key in observed_masks.keys()),
            }
        else:
            ndvi_mask_diagnostic = {
                "status": "source_unavailable",
                "ndvi_surface_present": ndvi_surface is not None,
                "observed_mask_keys": sorted(str(key) for key in observed_masks.keys()),
            }
    except Exception as e:
        logger.warning("Canonical NDVI mask generation failed: %s", e)
        ndvi_mask_diagnostic = {
            "status": "error",
            "error": f"{type(e).__name__}: {e}",
            "observed_mask_keys": sorted(str(key) for key in (locals().get("observed_masks") or {}).keys()),
        }
        skipped += 3

    try:
        unc_surfaces = generate_uncertainty_surfaces(
            l10_input, H, W, l1_data=l1_data, l2_data=l2_data
        )
        surfaces.extend(unc_surfaces)
    except Exception:
        skipped += 3

    # Conditional: water (L3), nutrients (L4), disease (L5)
    if l10_input.decision:
        try:
            water_surfaces = generate_water_surfaces(
                l10_input, H, W, l1_data=l1_data, l3_data=l3_data
            )
            surfaces.extend(water_surfaces)
        except Exception as exc:
            logger.error(f"[SIRE] Failed to generate water surfaces: {exc}", exc_info=True)
            skipped += 2

    # Salinity (L3 diagnosis + L1 EC/pH rasters)
    if l10_input.decision:
        try:
            sal_surfaces = generate_salinity_surfaces(
                l10_input, H, W, l1_data=l1_data, l3_data=l3_data
            )
            surfaces.extend(sal_surfaces)
        except Exception:
            skipped += 1

    if l10_input.nutrients:
        try:
            # Extract surface mean from already-built veg surfaces for stage fallback
            _ndvi_surf = next(
                (s for s in surfaces if getattr(s, 'semantic_type', None) and
                 hasattr(s.semantic_type, 'value') and s.semantic_type.value == 'NDVI_CLEAN'),
                None
            )
            _ndvi_surf_mean = None
            if _ndvi_surf is not None:
                _vals = [v for row in (_ndvi_surf.values or []) for v in row if v is not None]
                _ndvi_surf_mean = sum(_vals) / len(_vals) if _vals else None
            # GAP 4 + Fix A: reconciled stage with surface-mean fallback
            _pheno_stage = _resolve_phenology_stage(l10_input.veg_int, _ndvi_surf_mean)
            nut_surfaces = generate_nutrient_surfaces(
                l10_input, H, W, l4_data=l4_data, l1_data=l1_data,
                phenology_stage=_pheno_stage,
            )
            surfaces.extend(nut_surfaces)
        except Exception:
            skipped += 2

    if l10_input.bio:
        try:
            dis_surfaces = generate_disease_surfaces(
                l10_input, H, W, l5_data=l5_data,
                l1_data=l1_data, l3_data=l3_data,
            )
            surfaces.extend(dis_surfaces)
        except Exception:
            skipped += 2

    # Planning/yield (L7)
    if l10_input.planning:
        try:
            yield_s = generate_yield_surfaces(
                l10_input, H, W, l7_data=l7_data,
                l1_data=l1_data, l2_data=l2_data,
                existing_surfaces=surfaces,
            )
            surfaces.extend(yield_s)
        except Exception:
            skipped += 3
        try:
            suit_s = generate_suitability_surfaces(
                l10_input, H, W, l7_data=l7_data, l1_data=l1_data
            )
            surfaces.extend(suit_s)
        except Exception:
            skipped += 1

    # Biophysical / Agronomic models
    try:
        agronomic_s = generate_agronomic_models(l10_input, H, W, l1_data=l1_data)
        surfaces.extend(agronomic_s)
    except Exception as e:
        print(f"[L10] Error running agronomic models: {e}", file=sys.stderr)
        skipped += 5

    asmae_s = []
    try:
        asmae_s = generate_asmae_surfaces(l10_input, H, W, l1_data=l1_data)
    except Exception as e:
        print(f"[L10] Error running ASMAE surfaces: {e}", file=sys.stderr)
        skipped += 18
        component_failures.append(ComponentFailure(
            code="ASMAE_SURFACE_MATERIALIZATION_FAILED",
            component="asmae_surfaces",
            stage="materialization",
            message=f"{type(e).__name__}: {e}",
            fallback_used=True,
            affected_surface_types=["ASMAE_*"],
        ))
        degradation_codes.append("ASMAE_SURFACE_MATERIALIZATION_FAILED")
    else:
        alignment_failures = list(
            getattr(l1_data, "asmae_alignment_failures", None) or []
        )
        for failure in alignment_failures:
            if not isinstance(failure, dict):
                continue
            surface_type = str(
                failure.get("surface_type") or failure.get("variable") or "ASMAE_*"
            )
            reason = str(
                failure.get("reason") or "ASMAE source/display grid alignment failed"
            )
            component_failures.append(ComponentFailure(
                code="ASMAE_GRID_ALIGNMENT_FAILED",
                component="asmae_surfaces",
                stage="alignment",
                message=reason,
                fallback_used=True,
                affected_surface_types=[surface_type],
            ))
        if alignment_failures:
            skipped += len(alignment_failures)
            degradation = SIREDegradation.DEGRADED
            degradation_codes.append("ASMAE_GRID_ALIGNMENT_FAILED")

        # Core ASMAE rasters are independently validated scientific artifacts.
        # Commit them before building derivative display aliases so an alias-only
        # defect cannot erase otherwise valid ASMAE evidence from the surface pack.
        surfaces.extend(asmae_s)
        try:
            from services.agribrain.layer10_sire.surfaces.asmae import generate_asmae_aliases

            asmae_aliases = generate_asmae_aliases(
                H,
                W,
                surfaces,
                l10_input,
                grid_spec_dict=display_grid_spec,
            )
            surfaces.extend(asmae_aliases)
        except Exception as e:
            print(f"[L10] Error running ASMAE aliases: {e}", file=sys.stderr)
            skipped += 1
            component_failures.append(ComponentFailure(
                code="ASMAE_ALIAS_MATERIALIZATION_FAILED",
                component="asmae_aliases",
                stage="materialization",
                message=f"{type(e).__name__}: {e}",
                fallback_used=True,
                affected_surface_types=["*_ASMAE_*"],
            ))
            degradation_codes.append("ASMAE_ALIAS_MATERIALIZATION_FAILED")



    # Historical surfaces (V90.7O)
    try:
        hist_s = generate_historical_surfaces(l10_input, H, W, l1_data=l1_data)
        surfaces.extend(hist_s)
    except Exception as e:
        print(f"[L10] Error running historical surfaces: {e}", file=sys.stderr)
        skipped += 3

    # --- Step 1a-V61C: Resolution coverage surface (six-tier ladder) ---
    try:
        if not render_as_spatial:
            raise SpatialProcessingSkipped(grid_spec_status)
        res_surfaces = generate_resolution_surfaces(
            l10_input, H, W, l1_data=l1_data,
            ground_truth_context=getattr(l10_input, 'ground_truth_context', None),
            current_asmae_surfaces=asmae_s,
        )
        surfaces.extend(res_surfaces)
        if res_surfaces:
            sp = res_surfaces[0].provenance.get("spatial_precision", "?")
            pcts = res_surfaces[0].provenance.get("resolution_percentages", {})
            print(f"[L10-V61C] Resolution surface: strategy={sp}, pcts={pcts}", file=sys.stderr)
    except SpatialProcessingSkipped:
        skipped += 1
    except Exception as e:
        import traceback
        print(f"[L10-V61C] Resolution surface FAILED: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        skipped += 1  # Resolution surface is non-fatal

    # --- Step 1aa-V65F: Experimental fine-detail candidate surfaces ---
    try:
        if not render_as_spatial:
            raise SpatialProcessingSkipped(grid_spec_status)
        detail_surf = next((s for s in surfaces if (s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type)) == "EXPERIMENTAL_TEXTURE_SUPPORT_MASK"), None)
        strict_surf = next((s for s in surfaces if (s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type)) in ["EXPERIMENTAL_STRICT_FINE_DETAIL_CANDIDATE_MASK", "EXPERIMENTAL_FINE_DETAIL_CANDIDATE"]), None)
        ndvi_surf = next((s for s in surfaces if (s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type)) == "NDVI_CLEAN"), None)

        if detail_surf is not None or strict_surf is not None or ndvi_surf is not None:
            if detail_surf is not None:
                detail_arr = np.array(detail_surf.values, dtype=float)
                visual_detail_mask = detail_arr > 0.5
                if strict_surf is not None:
                    strict_arr = np.array(strict_surf.values, dtype=float)
                    strict_candidate_mask = strict_arr > 0.5
                else:
                    strict_candidate_mask = np.zeros_like(visual_detail_mask, dtype=bool)
                prov_adv = detail_surf.provenance or {}
            elif strict_surf is not None:
                strict_arr = np.array(strict_surf.values, dtype=float)
                strict_candidate_mask = strict_arr > 0.5
                visual_detail_mask = strict_candidate_mask.copy()
                prov_adv = strict_surf.provenance or {}
            else:
                ndvi_arr = np.array(ndvi_surf.values, dtype=float)
                visual_detail_mask = np.zeros_like(ndvi_arr, dtype=bool)
                strict_candidate_mask = np.zeros_like(visual_detail_mask, dtype=bool)
                prov_adv = ndvi_surf.provenance or {}

            candidate_coverage_pct = prov_adv.get("candidate_coverage_pct", 0.0)

            ndvi_vals = None
            if ndvi_surf is not None:
                raw_ndvi = np.array(ndvi_surf.values, dtype=float)
                if np.any(~np.isnan(raw_ndvi)):
                    mean_ndvi = np.nanmean(raw_ndvi)
                    ndvi_vals = np.nan_to_num(raw_ndvi, nan=mean_ndvi)

            ndmi_surf = next((s for s in surfaces if s.semantic_type == "SOIL_MOISTURE_PROXY"), None)
            ndmi_vals = None
            if ndmi_surf is not None:
                raw_ndmi = np.array(ndmi_surf.values, dtype=float)
                if np.any(~np.isnan(raw_ndmi)):
                    mean_ndmi = np.nanmean(raw_ndmi)
                    ndmi_vals = np.nan_to_num(raw_ndmi, nan=mean_ndmi)
            else:
                # Fallback: check if ndmi is in l1_data.raster_maps
                raster_maps = getattr(l1_data, 'raster_maps', {}) or {} if l1_data is not None else {}
                if "ndmi" in raster_maps:
                    raw_ndmi = np.array(raster_maps["ndmi"], dtype=float)
                    if np.any(~np.isnan(raw_ndmi)):
                        mean_ndmi = np.nanmean(raw_ndmi)
                        ndmi_vals = np.nan_to_num(raw_ndmi, nan=mean_ndmi)

            def compute_local_detail_texture(arr_2d: np.ndarray) -> np.ndarray:
                mean_val = np.nanmean(arr_2d) if not np.isnan(np.nanmean(arr_2d)) else 0.0
                arr_clean = np.nan_to_num(arr_2d, nan=mean_val)
                padded = np.pad(arr_clean, 1, mode='edge')
                up = padded[:-2, 1:-1]
                down = padded[2:, 1:-1]
                left = padded[1:-1, :-2]
                right = padded[1:-1, 2:]
                neighbors_mean = (up + down + left + right) / 4.0
                return arr_clean - neighbors_mean

            core_map_modes = {
                "NDVI_CLEAN": "NDVI_CLEAN_EXPERIMENTAL_FINE_DETAIL",
                "NDVI_DEVIATION": "NDVI_DEVIATION_EXPERIMENTAL_FINE_DETAIL",
                "BASELINE_ANOMALY": "BASELINE_ANOMALY_EXPERIMENTAL_FINE_DETAIL",
                "WATER_STRESS_PROB": "WATER_STRESS_PROB_EXPERIMENTAL_FINE_DETAIL",
                "NUTRIENT_STRESS_PROB": "NUTRIENT_STRESS_PROB_EXPERIMENTAL_FINE_DETAIL",
                "SALINITY_STRESS": "SALINITY_STRESS_EXPERIMENTAL_FINE_DETAIL",
                "COMPOSITE_RISK": "COMPOSITE_RISK_EXPERIMENTAL_FINE_DETAIL",
                "DATA_RELIABILITY": "DATA_RELIABILITY_EXPERIMENTAL_FINE_DETAIL",
                "DATA_CONFIDENCE": "DATA_RELIABILITY_EXPERIMENTAL_FINE_DETAIL",
                "UNCERTAINTY_SIGMA": "DATA_RELIABILITY_EXPERIMENTAL_FINE_DETAIL",
            }

            # V65G: Backend upscaling helpers for true high-res experimental surfaces
            def _bilinear_upscale_2d(arr, new_h, new_w):
                """Bilinear upscale a 2D float array. NaN pixels fall back to nearest."""
                old_h, old_w = arr.shape
                ys = (np.arange(new_h, dtype=float) + 0.5) * old_h / new_h - 0.5
                xs = (np.arange(new_w, dtype=float) + 0.5) * old_w / new_w - 0.5
                y0 = np.clip(np.floor(ys).astype(int), 0, old_h - 1)
                y1 = np.clip(y0 + 1, 0, old_h - 1)
                x0 = np.clip(np.floor(xs).astype(int), 0, old_w - 1)
                x1 = np.clip(x0 + 1, 0, old_w - 1)
                wy = np.clip(ys - y0, 0.0, 1.0)[:, np.newaxis]
                wx = np.clip(xs - x0, 0.0, 1.0)[np.newaxis, :]
                result = (arr[np.ix_(y0, x0)] * (1 - wy) * (1 - wx) +
                          arr[np.ix_(y0, x1)] * (1 - wy) * wx +
                          arr[np.ix_(y1, x0)] * wy * (1 - wx) +
                          arr[np.ix_(y1, x1)] * wy * wx)
                nan_mask = np.isnan(result)
                if np.any(nan_mask):
                    ny = np.clip(np.round(ys).astype(int), 0, old_h - 1)
                    nx = np.clip(np.round(xs).astype(int), 0, old_w - 1)
                    result[nan_mask] = arr[np.ix_(ny, nx)][nan_mask]
                return result

            def _nearest_upscale_bool(mask, new_h, new_w):
                """Nearest-neighbor upscale a boolean mask."""
                old_h, old_w = mask.shape
                ys = np.clip(np.round((np.arange(new_h) + 0.5) * old_h / new_h - 0.5).astype(int), 0, old_h - 1)
                xs = np.clip(np.round((np.arange(new_w) + 0.5) * old_w / new_w - 0.5).astype(int), 0, old_w - 1)
                return mask[np.ix_(ys, xs)]

            # V65G: Compute upscaled visual dimensions (4×, capped at 512)
            VISUAL_SCALE = 4
            MAX_VISUAL_DIM = 512
            exp_H = min(H * VISUAL_SCALE, MAX_VISUAL_DIM)
            exp_W = min(W * VISUAL_SCALE, MAX_VISUAL_DIM)
            actual_scale_h = exp_H / H
            actual_scale_w = exp_W / W
            display_resolution_m = l10_input.resolution_m / min(actual_scale_h, actual_scale_w)

            # Upscale candidate and visual detail masks
            cand_mask_up = _nearest_upscale_bool(strict_candidate_mask, exp_H, exp_W)
            visual_detail_mask_up = _nearest_upscale_bool(visual_detail_mask, exp_H, exp_W)

            print(f"[L10-V65G] Visual grid: {H}x{W} → {exp_H}x{exp_W} (scale={VISUAL_SCALE}, display_res={display_resolution_m:.2f}m)", file=sys.stderr)

            generated_exp_types = set()

            for s in list(surfaces):
                s_type_str = s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type)
                if s_type_str in core_map_modes:
                    exp_type_str = core_map_modes[s_type_str]
                    if exp_type_str in generated_exp_types:
                        continue
                    generated_exp_types.add(exp_type_str)

                    arr_certified = np.array(s.values, dtype=float)
                    if not np.any(~np.isnan(arr_certified)):
                        continue

                    if exp_type_str == "DATA_RELIABILITY_EXPERIMENTAL_FINE_DETAIL":
                        if s_type_str == "UNCERTAINTY_SIGMA":
                            arr_certified = 1.0 - arr_certified

                    # V65G: Upscale certified surface bilinearly to exp_H × exp_W
                    arr_cert_up = _bilinear_upscale_2d(arr_certified, exp_H, exp_W)

                    # Upscale valid mask (nearest-neighbor to preserve None boundaries)
                    valid_orig = ~np.isnan(arr_certified)
                    valid_up = _nearest_upscale_bool(valid_orig, exp_H, exp_W)

                    # Map mode to the correct detail basis and upscale
                    detail_basis_up = None
                    if s_type_str in ["WATER_STRESS_PROB", "SALINITY_STRESS"] and ndmi_vals is not None:
                        detail_basis_up = _bilinear_upscale_2d(ndmi_vals, exp_H, exp_W)
                    elif ndvi_vals is not None:
                        detail_basis_up = _bilinear_upscale_2d(ndvi_vals, exp_H, exp_W)

                    # Compute texture at high resolution
                    if detail_basis_up is not None:
                        T = compute_local_detail_texture(detail_basis_up)
                    else:
                        T = compute_local_detail_texture(arr_cert_up)

                    support_up = visual_detail_mask_up & valid_up & np.isfinite(T)
                    intensity_factor = 1.0
                    if hasattr(l10_input, "visual_intensity") and l10_input.visual_intensity is not None:
                        intensity_factor = float(np.clip(l10_input.visual_intensity, 0.0, 1.0))

                    T_scaled = np.zeros_like(T, dtype=float)
                    certified_samples = arr_cert_up[valid_up & np.isfinite(arr_cert_up)]
                    certified_iqr = (
                        float(np.percentile(certified_samples, 75) - np.percentile(certified_samples, 25))
                        if certified_samples.size else 0.0
                    )
                    visual_ceiling = min(0.03, max(0.0, 0.15 * certified_iqr)) * intensity_factor
                    if np.any(support_up):
                        supported_texture = T[support_up]
                        supported_texture = supported_texture - float(np.mean(supported_texture))
                        peak = float(np.max(np.abs(supported_texture)))
                        if peak > 1e-9:
                            T_scaled[support_up] = (supported_texture / peak) * visual_ceiling

                    if s_type_str in ["WATER_STRESS_PROB", "NUTRIENT_STRESS_PROB", "COMPOSITE_RISK", "SALINITY_STRESS"]:
                        T_scaled = -T_scaled

                    arr_sharpened = np.where(support_up, arr_cert_up + T_scaled, arr_cert_up)

                    # Guard against any NaN values in arr_sharpened (fallback to certified value)
                    arr_sharpened = np.where(np.isnan(arr_sharpened), arr_cert_up, arr_sharpened)

                    min_val = np.nanmin(arr_cert_up)
                    max_val = np.nanmax(arr_cert_up)
                    if min_val == max_val:
                        max_val = min_val + 1e-6
                    arr_sharpened = np.clip(arr_sharpened, min_val, max_val)

                    # Parent-cell mean preservation with error tracking (iterative projection up to 10 passes)
                    experimental_std_before = float(np.nanstd(arr_cert_up[valid_up])) if np.any(valid_up) else 0.0
                    experimental_detail_energy = float(np.nanstd(T_scaled[valid_up])) if np.any(valid_up) else 0.0

                    r_map = np.clip(np.round((np.arange(exp_H) + 0.5) * H / exp_H - 0.5).astype(int), 0, H - 1)
                    c_map = np.clip(np.round((np.arange(exp_W) + 0.5) * W / exp_W - 0.5).astype(int), 0, W - 1)

                    arr_sharpened, parent_mean_error = conserve_parent_cell_means(
                        arr_sharpened,
                        arr_certified,
                        valid_up,
                        r_map,
                        c_map,
                        min_val,
                        max_val,
                    )

                    experimental_std_after = float(np.nanstd(arr_sharpened[valid_up])) if np.any(valid_up) else 0.0
                    source_to_experimental = arr_sharpened - arr_cert_up
                    source_to_experimental_mean_error = (
                        float(np.nanmean(source_to_experimental[valid_up])) if np.any(valid_up) else 0.0
                    )
                    source_to_experimental_absolute_error = (
                        float(np.nanmean(np.abs(source_to_experimental[valid_up]))) if np.any(valid_up) else 0.0
                    )

                    # Build output values at exp_H × exp_W
                    arr_out = arr_sharpened.copy()
                    arr_out[~valid_up] = np.nan
                    sharpened_values = [
                        [None if np.isnan(v) else round(float(v), 6) for v in row]
                        for row in arr_out.tolist()
                    ]

                    from services.agribrain.layer10_sire.schema import SurfaceArtifact as SA, GroundingClass as GC, SurfaceType as STT
                    exp_surf = SA(
                        surface_id=f"{exp_type_str}_{l10_input.plot_id}",
                        semantic_type=STT(exp_type_str),
                        grid_ref=f"{exp_H}x{exp_W}",
                        values=sharpened_values,
                        units=s.units,
                        native_resolution_m=float(l10_input.resolution_m),
                        render_range=s.render_range,
                        palette_id=s.palette_id,
                        source_layers=list(s.source_layers) + ["experimental_fine_detail_lens"],
                        provenance={
                            "resolution_role": "experimental_visual_detail",
                            "source_reality": "model_assisted_visual_detail",
                            "source_evidence_resolution_m": float(l10_input.resolution_m),
                            "computational_grid_resolution_m": round(display_resolution_m, 2),
                            "display_grid_resolution_m": round(display_resolution_m, 2),
                            "state_update_allowed": False,
                            "production_selectable": False,
                            "diagnostic_only": True,
                            "certified_basis_m": l10_input.resolution_m,
                            "certification_status": prov_adv.get("certification_status", "experimental_learning_unvalidated"),
                            "requires_user_warning": True,
                            "candidate_source": prov_adv.get("candidate_source", "none"),
                            "candidate_coverage_pct": candidate_coverage_pct,
                            "validated_fine_detail_pct": 0.0,
                            "quality_evidence_present": prov_adv.get("quality_evidence_present", False),
                            "visual_scale_factor": VISUAL_SCALE,
                            "display_resolution_m": round(display_resolution_m, 2),
                            "effective_data_basis_m": l10_input.resolution_m,
                            "exp_grid": f"{exp_H}x{exp_W}",
                            "certified_grid": f"{H}x{W}",
                            "mean_preservation_error": round(parent_mean_error, 6),
                            "experimental_detail_energy": round(experimental_detail_energy, 6),
                            "experimental_std_before": round(experimental_std_before, 6),
                            "experimental_std_after": round(experimental_std_after, 6),
                            "parent_mean_error": round(parent_mean_error, 6),
                            "parent_to_child_mean_error": round(parent_mean_error, 6),
                            "source_to_experimental_mean_error": round(source_to_experimental_mean_error, 8),
                            "source_to_experimental_absolute_error": round(source_to_experimental_absolute_error, 8),
                            "visual_amplitude_ceiling": round(visual_ceiling, 6),
                            "max_visual_dim": MAX_VISUAL_DIM,
                        },
                        grounding_class=GC.MODEL_ASSISTED_RASTER.value,
                    )
                    surfaces.append(exp_surf)
    except SpatialProcessingSkipped:
        skipped += 1
    except Exception as e:
        import traceback
        print(f"[L10-V65F] Experimental fine-detail candidate generation FAILED: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

    # V92.4-BC.10.10: Always-on Composite ASMAE Advisory (runs after experimental visual detail is generated)
    try:
        if not render_as_spatial:
            raise SpatialProcessingSkipped(grid_spec_status)
        current_ev_state = {}
        ctx_pkg = getattr(l10_input.field_tensor, "_context_package", None) if (l10_input and l10_input.field_tensor) else None
        asmae_output_ref = getattr(ctx_pkg, "asmae_output", None) if ctx_pkg else None
        if isinstance(asmae_output_ref, dict):
            current_ev_state = asmae_output_ref.get("asmae_evidence_state", {})
        elif asmae_output_ref:
            current_ev_state = getattr(asmae_output_ref, "asmae_evidence_state", {})

        # ASMAE_* names are reserved for products backed by an actual ASMAE
        # execution/proof object.  A satellite composite can still drive the
        # ordinary advisory surfaces above, but it must not be re-labelled as
        # ASMAE when rollout rejected the plot (or no real scene stack ran).
        if current_ev_state.get("real_asmae_evidence") is True:
            from services.agribrain.layer10_sire.surfaces.asmae_composite import generate_asmae_composite_surfaces
            comp_s = generate_asmae_composite_surfaces(
                l10_input,
                H,
                W,
                base_surfaces=surfaces,
                l1_data=l1_data,
                asmae_evidence_state=current_ev_state,
            )
            surfaces.extend(comp_s)
    except SpatialProcessingSkipped:
        skipped += 1
    except Exception as e:
        import traceback
        print(f"[L10] Error running composite ASMAE surfaces: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

    # --- Step 1ab: ASMAE Visual Intelligence Fusion Canopy ---
    visual_fusion_materialization = {
        "contract_version": "asmae_visual_fusion_materialization_v1",
        "product": "ASMAE_VISUAL_FUSION_CANOPY",
        "optional": True,
        "status": "unavailable",
        "reason": "not_evaluated",
        "required_support_products": [
            "ASMAE_POSTERIOR_CONCENTRATION",
            "ASMAE_RETROVALIDATION_SCORE",
            "ASMAE_ARCHIVE_SUPPORT",
            "ASMAE_ML_AGREEMENT",
            "ASMAE_BMA_DISAGREEMENT",
        ],
    }
    try:
        if not render_as_spatial:
            raise SpatialProcessingSkipped(grid_spec_status)
        import os
        has_real_asmae = False
        ctx_pkg = getattr(l10_input.field_tensor, "_context_package", None) if l10_input.field_tensor else None
        asmae_output_ref = getattr(ctx_pkg, "asmae_output", None) if ctx_pkg else None
        
        evidence_state = {}
        if isinstance(asmae_output_ref, dict):
            evidence_state = asmae_output_ref.get("asmae_evidence_state", {})
        elif asmae_output_ref:
            evidence_state = getattr(asmae_output_ref, "asmae_evidence_state", {})
            
        visual_fusion_allowed = evidence_state.get("visual_fusion_allowed", False)
        test_override = os.environ.get("ASMAE_TEST_OVERRIDE", "false").lower() == "true"
        
        if visual_fusion_allowed or (test_override and evidence_state.get("real_asmae_evidence", False)):
            has_real_asmae = True

        if not has_real_asmae:
            visual_fusion_materialization["reason"] = "core_asmae_spatial_evidence_unavailable"
            print("[L10] Step 1ab skipped: No real ASMAE evidence (missing scene stack or archive products).", file=sys.stderr)
        else:
            if 'exp_H' not in locals() or 'exp_W' not in locals():
                VISUAL_SCALE = 4
                MAX_VISUAL_DIM = 512
                exp_H = min(H * VISUAL_SCALE, MAX_VISUAL_DIM)
                exp_W = min(W * VISUAL_SCALE, MAX_VISUAL_DIM)
            actual_scale = min(exp_H / H, exp_W / W)
            if 'display_resolution_m' not in locals():
                display_resolution_m = l10_input.resolution_m / actual_scale

            if '_bilinear_upscale_2d' not in locals():
                def _bilinear_upscale_2d(arr, new_h, new_w):
                    import numpy as np
                    old_h, old_w = arr.shape
                    ys = (np.arange(new_h, dtype=float) + 0.5) * old_h / new_h - 0.5
                    xs = (np.arange(new_w, dtype=float) + 0.5) * old_w / new_w - 0.5
                    y0 = np.clip(np.floor(ys).astype(int), 0, old_h - 1)
                    y1 = np.clip(y0 + 1, 0, old_h - 1)
                    x0 = np.clip(np.floor(xs).astype(int), 0, old_w - 1)
                    x1 = np.clip(x0 + 1, 0, old_w - 1)
                    wy = np.clip(ys - y0, 0.0, 1.0)[:, np.newaxis]
                    wx = np.clip(xs - x0, 0.0, 1.0)[np.newaxis, :]
                    result = (arr[np.ix_(y0, x0)] * (1 - wy) * (1 - wx) +
                              arr[np.ix_(y0, x1)] * (1 - wy) * wx +
                              arr[np.ix_(y1, x0)] * wy * (1 - wx) +
                              arr[np.ix_(y1, x1)] * wy * wx)
                    nan_mask = np.isnan(result)
                    if np.any(nan_mask):
                        ny = np.clip(np.round(ys).astype(int), 0, old_h - 1)
                        nx = np.clip(np.round(xs).astype(int), 0, old_w - 1)
                        result[nan_mask] = arr[np.ix_(ny, nx)][nan_mask]
                    return result

            def get_upscaled_surface_array(surfaces, sem_type, target_h, target_w):
                import numpy as np
                import os
                surf = next((s for s in surfaces if s.semantic_type == sem_type or getattr(s.semantic_type, 'value', '') == sem_type), None)
                if surf is None or not surf.values:
                    raise ValueError(f"Required support map {sem_type} is missing or has no values")

                prov = getattr(surf, "provenance", {}) or {}
                if not isinstance(prov, dict):
                    prov = {}

                # 1. Block fallback maps
                sem_type_str = str(sem_type)
                if sem_type_str.startswith("FALLBACK_"):
                    raise ValueError(f"Required support map {sem_type} is a fallback map.")

                # 2. Check if ASMAE_TEST_OVERRIDE is active
                test_override = os.environ.get("ASMAE_TEST_OVERRIDE", "false").lower() == "true"

                # 3. Verify provenance real_asmae_evidence = True
                real_asmae_ev = prov.get("real_asmae_evidence", False)
                if not real_asmae_ev and not test_override:
                    raise ValueError(f"Required support map {sem_type} does not carry real ASMAE evidence.")

                # 4. Verify source_reality strictly in ("real_raster", "full_scene_stack")
                source_real = prov.get("source_reality", "")
                if not source_real and test_override:
                    source_real = "real_raster"
                if source_real not in ("real_raster", "full_scene_stack") and not test_override:
                    raise ValueError(f"Required support map {sem_type} has blocked source_reality: {source_real}")

                # 5. Verify presence of asmae_feature name (creator module/feature)
                feature_name = prov.get("asmae_feature")
                if not feature_name:
                    if test_override:
                        feature_name = f"mock_{sem_type_str.lower()}"
                    else:
                        raise ValueError(f"Required support map {sem_type} is missing creator module/feature provenance.")

                arr = np.array([[np.nan if v is None else float(v) for v in row] for row in surf.values], dtype=float)
                if not np.any(~np.isnan(arr)):
                    raise ValueError(f"Required support map {sem_type} is empty or all NaN")

                # Check for neutral defaults (like 0.5 filled) or constants
                valid_vals = arr[~np.isnan(arr)]
                if len(valid_vals) > 0 and np.all(valid_vals == valid_vals[0]):
                    grounding = getattr(surf, "grounding_class", "UNIFORM")
                    is_uniform = grounding in ("UNIFORM", "PLOT_LEVEL") or prov.get("scope") == "plot_level"
                    is_const_allowed = prov.get("constant_allowed") is True and is_uniform
                    if not is_const_allowed:
                        if np.all(np.abs(valid_vals - 0.5) < 1e-5):
                            raise ValueError(f"Required support map {sem_type} has a neutral constant 0.5 and is not explicitly marked as plot-level constant_allowed.")

                if arr.shape == (target_h, target_w):
                    return arr
                return _bilinear_upscale_2d(arr, target_h, target_w)

            confidence_up = get_upscaled_surface_array(surfaces, "ASMAE_POSTERIOR_CONCENTRATION", exp_H, exp_W)
            retro_up = get_upscaled_surface_array(surfaces, "ASMAE_RETROVALIDATION_SCORE", exp_H, exp_W)
            archive_up = get_upscaled_surface_array(surfaces, "ASMAE_ARCHIVE_SUPPORT", exp_H, exp_W)
            ml_up = get_upscaled_surface_array(surfaces, "ASMAE_ML_AGREEMENT", exp_H, exp_W)
            bma_up = get_upscaled_surface_array(surfaces, "ASMAE_BMA_DISAGREEMENT", exp_H, exp_W)

            Q = (confidence_up + retro_up + archive_up + ml_up + (1.0 - bma_up)) / 5.0

            ndvi_up = None
            skip_experimental_surface = False
            exp_ndvi = next((s for s in surfaces if s.semantic_type == "NDVI_CLEAN_EXPERIMENTAL_FINE_DETAIL"), None)
            if exp_ndvi is not None and exp_ndvi.values:
                ndvi_up = np.array([[np.nan if v is None else float(v) for v in row] for row in exp_ndvi.values], dtype=float)
            if ndvi_up is None or not np.any(~np.isnan(ndvi_up)):
                ndvi_clean = next((s for s in surfaces if s.semantic_type == "NDVI_CLEAN"), None)
                if ndvi_clean is not None and ndvi_clean.values:
                    arr_clean = np.array([[np.nan if v is None else float(v) for v in row] for row in ndvi_clean.values], dtype=float)
                    if np.any(~np.isnan(arr_clean)):
                        ndvi_up = _bilinear_upscale_2d(arr_clean, exp_H, exp_W)
                    else:
                        skip_experimental_surface = True
                else:
                    skip_experimental_surface = True

            if skip_experimental_surface:
                visual_fusion_materialization["reason"] = "ndvi_surface_unavailable"
                print("[L10-V92.4] No valid NDVI/NDVI_CLEAN for ASMAE Visual Fusion Canopy — skipping experimental detail surfaces only", file=sys.stderr)
            else:
                vigor_up = get_upscaled_surface_array(surfaces, "CANOPY_ASMAE_VIGOR", exp_H, exp_W)

                nan_mask = np.isnan(ndvi_up) | np.isnan(vigor_up)
                fusion_arr = Q * vigor_up + (1.0 - Q) * ndvi_up
                fusion_arr[nan_mask] = np.nan
                fusion_list = [[None if np.isnan(v) else round(float(v), 6) for v in row] for row in fusion_arr.tolist()]

                import datetime as dt
                fusion_grid_spec = {"width": exp_W, "height": exp_H, "res": display_resolution_m}
                
                run_ref = getattr(l10_input, "run_id", "fallback_run")
                fusion_surf = SurfaceArtifact(
                    surface_id=f"surf_asmae_visual_fusion_{l10_input.plot_id}_{run_ref}",
                    semantic_type=SurfaceType.ASMAE_VISUAL_FUSION_CANOPY,
                    grid_ref="fusion_grid",
                    values=fusion_list,
                    units="index",
                    native_resolution_m=display_resolution_m,
                    grid_spec=fusion_grid_spec,
                    provenance={
                        "stage": "L10_fusion",
                        "mode": "asmae_canopy_fusion",
                        "creator": "L10_ASMAE_VISUAL_FUSION",
                        "asmae_feature": "visual_fusion_canopy",
                        "real_asmae_evidence": evidence_state.get("real_asmae_evidence", False),
                        "source_reality": evidence_state.get("source_reality", "unknown"),
                        "used_enkf": evidence_state.get("used_enkf", False),
                        "used_retrovalidation": evidence_state.get("used_retrovalidation", False),
                        "used_bma": evidence_state.get("used_bma", False),
                        "used_ml": evidence_state.get("used_ml", False),
                        "used_radiometric": evidence_state.get("used_radiometric", False),
                        "used_archive": evidence_state.get("used_archive", False),
                        "base_resolution_m": l10_input.resolution_m,
                        "fusion_weights": {
                            "cert_w": 0.30,
                            "bma_w": 0.20,
                            "ml_w": 0.15,
                            "retro_w": 0.20,
                            "arch_w": 0.15
                        },
                        "display_upscale_factor": actual_scale,
                    },
                    grounding_class=GroundingClass.MODEL_ASSISTED_RASTER.value,
                )
                surfaces.append(fusion_surf)
                visual_fusion_materialization.update({
                    "status": "completed",
                    "reason": None,
                    "surface_id": fusion_surf.surface_id,
                })
                print(f"[L10-V92.4] ASMAE Visual Fusion Canopy generated: {exp_H}x{exp_W}", file=sys.stderr)
    except SpatialProcessingSkipped as exc:
        skipped += 1
        visual_fusion_materialization["reason"] = f"spatial_processing_unavailable:{exc}"
    except ValueError as exc:
        skipped += 1
        visual_fusion_materialization["reason"] = str(exc)
        print(f"[L10-V92.4] Optional ASMAE Visual Fusion Canopy unavailable: {exc}", file=sys.stderr)
    except Exception as e:
        import traceback
        visual_fusion_materialization.update({
            "status": "error",
            "reason": f"{type(e).__name__}:{e}",
        })
        print(f"[L10-V92.4] ASMAE Visual Fusion Canopy generation FAILED: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

    # --- Step 1b: Temporal intelligence surfaces (14-day window) ---
    try:
        temporal_surfaces = generate_temporal_surfaces(
            l10_input, H, W,
            l1_data=l1_data, l2_data=l2_data, l3_data=l3_data,
        )
        surfaces.extend(temporal_surfaces)
    except Exception:
        skipped += 8  # Up to 8 temporal surfaces

    # --- Step 1c: Execution intelligence surfaces (L6/L8) ---
    if l10_input.exec_state or l10_input.prescriptive:
        try:
            exec_surfaces = generate_execution_surfaces(
                l10_input, H, W,
                l6_data=l6_data, l8_data=l8_data, l1_data=l1_data,
            )
            surfaces.extend(exec_surfaces)
        except Exception:
            skipped += 4  # Up to 4 execution surfaces

    # --- Step 1d: Spatial Masking (precomputed polygon mask) ---
    # PERF: Compute the polygon membership mask ONCE for all surfaces.
    # Previously this was H×W×len(surfaces) polygon tests (~250K). Now H×W (8K).
    _field_mask = None
    ft = l10_input.field_tensor
    if ft is not None:
        poly_ring = field_polygon
        gs = getattr(ft, 'grid_spec', None)
        if gs is not None:
            if poly_ring and len(poly_ring) >= 3:
                gs_dict = (
                    gs.to_dict() if hasattr(gs, 'to_dict')
                    else (dict(gs) if isinstance(gs, dict) else {})
                )
                b = gs_dict.get('bounds') or getattr(gs, 'bounds', None)
                if b and len(b) == 4:
                    min_lng, min_lat, max_lng, max_lat = b
                    # V63B FIX: Also guard the mask rasterization against
                    # degenerate bounds — lat_step/lng_step would be 0,
                    # collapsing all cell centers to a single point.
                    if abs(max_lng - min_lng) > 1e-9 and abs(max_lat - min_lat) > 1e-9:
                        base_field_mask = _rasterize_polygon_mask(
                            H, W, b, poly_ring,
                        )
                        _field_mask = base_field_mask.tolist()
                        # Apply the geographic field footprint at each surface's
                        # own shape.  High-resolution products must not receive
                        # only the top-left HxW portion of the base mask.
                        for s in surfaces:
                            s_h = len(s.values)
                            s_w = len(s.values[0]) if s_h else 0
                            if not s_h or not s_w:
                                continue
                            surface_field_mask = _resize_boolean_mask(
                                base_field_mask, s_h, s_w,
                            )
                            dependency_mask = is_render_dependency_surface(s)
                            fill_val = 0.0 if dependency_mask else None
                            val_arr = np.array(s.values, dtype=object)
                            val_arr[~surface_field_mask] = fill_val
                            s.values = val_arr.tolist()

                        # VALID_DATA_MASK is geometry ∩ finite final NDVI, not
                        # merely the finite IDW rectangle.
                        ndvi_surface = next(
                            (s for s in surfaces if s.semantic_type == SurfaceType.NDVI_CLEAN), None
                        )
                        valid_surface = next(
                            (s for s in surfaces if s.semantic_type == SurfaceType.VALID_DATA_MASK_NDVI), None
                        )
                        if ndvi_surface is not None and valid_surface is not None:
                            ndvi_values = np.asarray(ndvi_surface.values, dtype=float)
                            prior_valid_values = (
                                np.asarray(valid_surface.values, dtype=float) > 0.5
                            )
                            valid_values = (
                                prior_valid_values
                                & base_field_mask
                                & np.isfinite(ndvi_values)
                            )
                            valid_surface.values = valid_values.astype(float).tolist()
                            valid_surface.provenance["definition"] = (
                                "trusted_source_support_intersection_field_geometry_finite_final_value"
                            )
                            valid_surface.provenance["field_geometry_applied"] = True

                            # Reconcile all three canonical masks after the
                            # field footprint is applied.  Coverage ratios are
                            # field-relative; using the rectangular grid as the
                            # denominator made a fully observed non-rectangular
                            # plot look only 50.9% observed.
                            observed_surface = next(
                                (s for s in surfaces if s.semantic_type == SurfaceType.OBSERVED_DATA_MASK_NDVI), None
                            )
                            gap_surface = next(
                                (s for s in surfaces if s.semantic_type == SurfaceType.GAP_FILL_MASK_NDVI), None
                            )
                            if observed_surface is not None and gap_surface is not None:
                                observed_values = (
                                    np.asarray(observed_surface.values, dtype=float) > 0.5
                                ) & valid_values
                                gap_values = valid_values & ~observed_values
                                valid_count = int(np.count_nonzero(valid_values))
                                observed_count = int(np.count_nonzero(observed_values))
                                gap_count = int(np.count_nonzero(gap_values))
                                field_observed_ratio = (
                                    observed_count / valid_count if valid_count else 0.0
                                )

                                observed_surface.values = observed_values.astype(float).tolist()
                                gap_surface.values = gap_values.astype(float).tolist()
                                for mask_surface, count in (
                                    (observed_surface, observed_count),
                                    (gap_surface, gap_count),
                                    (valid_surface, valid_count),
                                ):
                                    mask_surface.observed_ratio = field_observed_ratio
                                    mask_surface.provenance["field_valid_cell_count"] = valid_count
                                    mask_surface.provenance["active_cell_count"] = count
                                    mask_surface.provenance["coverage_denominator"] = "field_geometry_valid_cells"
                                ndvi_surface.observed_ratio = field_observed_ratio

                                ratios = getattr(l1_data, "observed_ratios", None)
                                if isinstance(ratios, dict):
                                    ratios["ndvi"] = field_observed_ratio

                                    # Normalize the remaining provider-mask
                                    # ratios to the same geographic footprint.
                                    # Preserve a ratio when no aligned source
                                    # mask exists rather than fabricating one.
                                    provider_masks = getattr(l1_data, "observed_masks", {}) or {}
                                    field_count = int(np.count_nonzero(base_field_mask))
                                    aliases = {
                                        "vv": "sar_backscatter",
                                        "vh": "sar_backscatter",
                                        "sar": "sar_backscatter",
                                    }
                                    for ratio_key in list(ratios):
                                        key = str(ratio_key).lower()
                                        mask_value = provider_masks.get(ratio_key)
                                        if mask_value is None:
                                            mask_value = provider_masks.get(key)
                                        if mask_value is None and key in aliases:
                                            mask_value = provider_masks.get(aliases[key])
                                        if mask_value is None:
                                            continue
                                        provider_mask = np.asarray(mask_value, dtype=bool)
                                        if (
                                            provider_mask.ndim != 2
                                            or provider_mask.shape[0] == 0
                                            or provider_mask.shape[1] == 0
                                        ):
                                            continue
                                        if provider_mask.shape != (H, W):
                                            rows = np.clip(
                                                np.floor((np.arange(H) + 0.5) * provider_mask.shape[0] / H).astype(int),
                                                0,
                                                provider_mask.shape[0] - 1,
                                            )
                                            cols = np.clip(
                                                np.floor((np.arange(W) + 0.5) * provider_mask.shape[1] / W).astype(int),
                                                0,
                                                provider_mask.shape[1] - 1,
                                            )
                                            provider_mask = provider_mask[np.ix_(rows, cols)]
                                        ratios[ratio_key] = (
                                            float(np.count_nonzero(provider_mask & base_field_mask)) / field_count
                                            if field_count else 0.0
                                        )

                                # Experimental candidate percentages are also
                                # field-relative.  They were generated before
                                # polygon masking, so their cached provenance
                                # still used the bounding rectangle even though
                                # the serialized mask no longer did.
                                candidate_surface = next(
                                    (
                                        s for s in surfaces
                                        if s.semantic_type == SurfaceType.EXPERIMENTAL_STRICT_FINE_DETAIL_CANDIDATE_MASK
                                    ),
                                    None,
                                )
                                if candidate_surface is not None:
                                    candidate_values = np.asarray(candidate_surface.values, dtype=float)
                                    candidate_denominator = int(np.count_nonzero(np.isfinite(candidate_values)))
                                    candidate_count = int(np.count_nonzero(candidate_values > 0.5))
                                    candidate_pct = (
                                        100.0 * candidate_count / candidate_denominator
                                        if candidate_denominator else 0.0
                                    )
                                    for experimental_surface in surfaces:
                                        provenance = experimental_surface.provenance or {}
                                        if "candidate_coverage_pct" not in provenance:
                                            continue
                                        provenance["candidate_coverage_pct"] = candidate_pct
                                        provenance["candidate_cell_count"] = candidate_count
                                        provenance["field_valid_cell_count"] = candidate_denominator
                                        provenance["coverage_denominator"] = "field_geometry_valid_cells"
                                        experimental_surface.provenance = provenance

                                # Recompute the categorical resolution summary
                                # from the polygon-clipped values.  Outside-plot
                                # cells must not remain classified as a 10 m
                                # fallback in the percentages or unique classes.
                                resolution_surface = next(
                                    (s for s in surfaces if s.semantic_type == SurfaceType.RESOLUTION_COVERAGE),
                                    None,
                                )
                                if resolution_surface is not None:
                                    resolution_values = np.asarray(resolution_surface.values, dtype=float)
                                    finite_resolution = resolution_values[np.isfinite(resolution_values)]
                                    if finite_resolution.size:
                                        unique_resolution = sorted(
                                            float(value) for value in np.unique(finite_resolution)
                                        )
                                        resolution_total = int(finite_resolution.size)
                                        percentage_for = lambda value: round(
                                            100.0 * float(np.count_nonzero(np.isclose(finite_resolution, value)))
                                            / resolution_total,
                                            2,
                                        )
                                        resolution_pct = {
                                            "three_cm_external_ground_truth_pct": percentage_for(0.0),
                                            "one_meter_advisory_pct": percentage_for(1.0),
                                            "two_meter_production_pct": 0.0,
                                            "three_meter_production_pct": 0.0,
                                            "two_meter_model_assisted_pct": percentage_for(2.0),
                                            "three_meter_model_assisted_pct": percentage_for(3.0),
                                            "five_meter_production_pct": 0.0,
                                            "ten_meter_fallback_pct": percentage_for(5.0),
                                            "five_meter_model_assisted_pct": percentage_for(4.0),
                                        }
                                        provenance = resolution_surface.provenance or {}
                                        provenance["unique_resolution_class_codes"] = unique_resolution
                                        provenance["resolution_percentages"] = resolution_pct
                                        provenance["five_meter_model_assisted_pct"] = resolution_pct[
                                            "five_meter_model_assisted_pct"
                                        ]
                                        provenance["is_spatially_uniform_class"] = len(unique_resolution) <= 1
                                        provenance["coverage_denominator"] = "field_geometry_valid_cells"
                                        provenance["field_valid_cell_count"] = resolution_total
                                        ladder_inputs = provenance.get("ladder_inputs")
                                        if isinstance(ladder_inputs, dict):
                                            ladder_inputs["ndvi_observed_ratio"] = round(field_observed_ratio, 4)
                                            if isinstance(ratios, dict) and "ndmi" in ratios:
                                                ladder_inputs["ndmi_observed_ratio"] = round(
                                                    float(ratios["ndmi"]), 4
                                                )
                                        resolution_surface.provenance = provenance
                        if not any(any(row) for row in _field_mask):
                            render_as_spatial = False
                            grid_spec_status = "grid_does_not_intersect_plot"
                    else:
                        print(f"[L10] Skipping polygon mask: degenerate bounds {b}", file=sys.stderr)

    # V92.4 GIS grid spec validation & resampling policy
    for s in surfaces:
        s_h = len(s.values)
        s_w = len(s.values[0]) if s_h > 0 else 0
        if is_high_resolution_surface(s):
            # ``source_grid_spec`` is scientific lineage, not a description of
            # the final display array.  ASMAE surfaces may arrive here after a
            # genuine cross-CRS reprojection, so never replace an already
            # recorded native grid with the browser/display grid.
            incoming_grid_spec = dict(s.grid_spec) if isinstance(s.grid_spec, dict) else None
            array_resolution_m = float(
                (getattr(s, "provenance", None) or {}).get("display_grid_resolution_m")
                or (getattr(s, "provenance", None) or {}).get("computational_grid_resolution_m")
                or s.native_resolution_m
            )
            exp_grid_spec = build_grid_spec_for_shape(
                display_grid_spec, s_w, s_h, array_resolution_m
            )
            exp_grid_spec["grid_hash"] = hashlib.sha256(json.dumps({
                key: exp_grid_spec.get(key)
                for key in ("crs", "bounds", "transform", "width", "height", "resolution_m")
            }, sort_keys=True, default=str).encode("utf-8")).hexdigest()
            s.grid_spec = exp_grid_spec
            if not isinstance(s.source_grid_spec, dict) or not s.source_grid_spec:
                s.source_grid_spec = incoming_grid_spec or dict(display_grid_spec)
            s.display_grid_spec = dict(exp_grid_spec)
            s.grid_ref = f"{s_h}x{s_w}"
        else:
            if s.grid_spec is None:
                s.grid_spec = dict(display_grid_spec)
                if not isinstance(s.source_grid_spec, dict) or not s.source_grid_spec:
                    s.source_grid_spec = None
                s.display_grid_spec = dict(display_grid_spec)
            else:
                s_spec = s.grid_spec
                s_hash = s_spec.get("grid_hash")
                if s_hash != display_grid_spec.get("grid_hash"):
                    method = "nearest" if (s.semantic_type in [SurfaceType.RESOLUTION_COVERAGE, SurfaceType.RESOLUTION_ASMAE_EFFECTIVE] or "MASK" in s.semantic_type.value) else "bilinear"
                    align_surface_to_display_grid(s, display_grid_spec, method=method)
                else:
                    if not isinstance(s.source_grid_spec, dict) or not s.source_grid_spec:
                        s.source_grid_spec = dict(s_spec)
                    s.display_grid_spec = dict(display_grid_spec)

    # --- Step 2: Structural detection ---
    performance_timers_ms["surface_families_and_experimental_upsampling"] = round((time.perf_counter() - _phase_started) * 1000.0, 3)
    _phase_started = time.perf_counter()
    micro_objects = []
    if render_as_spatial and l10_input.resolution_m <= 5.0 and not is_quick_visual:
        try:
            canopy_objs = detect_canopy(l10_input, H, W, l1_data=l1_data)
            micro_objects.extend(canopy_objs)
        except Exception:
            pass
        try:
            from services.agribrain.layer10_sire.structure.row_detection import detect_rows
            row_objs = detect_rows(l10_input, H, W, l1_data=l1_data)
            micro_objects.extend(row_objs)
        except Exception:
            pass
        try:
            from services.agribrain.layer10_sire.structure.crown_detection import detect_crowns
            crown_objs = detect_crowns(l10_input, H, W, l1_data=l1_data)
            micro_objects.extend(crown_objs)
        except Exception:
            pass

    # --- Step 3: Tag grounding classes ---
    grid_bounds = getattr(getattr(l10_input.field_tensor, "grid_spec", None), "bounds", None)
    for s in surfaces:
        # Determine raster basis and observed ratio for this surface
        basis = []
        obs_ratio = 0.0
        ratios = getattr(l1_data, "observed_ratios", {}) or {}
        
        # Hydrate based on semantic_type/name
        s_type = s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type)
        if "NDVI" in s_type or s_type in ["NDVI_CLEAN", "NDVI_DEVIATION", "BASELINE_ANOMALY", "GROWTH_VELOCITY"]:
            if "ndvi" in l1_data.raster_maps:
                basis = ["ndvi"]
                obs_ratio = ratios.get("ndvi", 0.0)
        elif "WATER" in s_type or s_type in ["WATER_STRESS_PROB", "SOIL_MOISTURE_PROXY"]:
            if "ndmi" in l1_data.raster_maps:
                basis = ["ndmi"]
                obs_ratio = ratios.get("ndmi", 0.0)
            elif "ndvi" in l1_data.raster_maps:
                basis = ["ndvi"]
                obs_ratio = ratios.get("ndvi", 0.0)
        elif "SALINITY" in s_type:
            # Salinity uses both ndvi and ndmi / vv
            basis = [k for k in ["ndvi", "ndmi", "vv"] if k in l1_data.raster_maps]
            obs_ratio = min([ratios.get(k, 0.0) for k in basis]) if basis else 0.0
        elif "NUTRIENT" in s_type or s_type == "FERTILITY_LIMITATION":
            basis = [
                k for k in ["ndvi", "vv", "vh", "soil_clay", "soil_ph", "soil_org_carbon"]
                if k in l1_data.raster_maps
            ]
            obs_ratio = min([ratios.get(k, 0.0) for k in basis]) if basis else 0.0
        elif "RISK" in s_type:
            basis = [k for k in ["ndvi", "ndmi", "vv"] if k in l1_data.raster_maps]
            obs_ratio = min([ratios.get(k, 0.0) for k in basis]) if basis else 0.0
        elif "RESOLUTION" in s_type:
            basis = [k for k in ["ndvi", "vv"] if k in l1_data.raster_maps]
            obs_ratio = min([ratios.get(k, 0.0) for k in basis]) if basis else 0.0
        elif is_high_resolution_surface(s):
            basis = [k for k in ["ndvi", "vv"] if k in l1_data.raster_maps]
            obs_ratio = min([ratios.get(k, 0.0) for k in basis]) if basis else 0.0

        s.raster_basis = basis
        s.observed_ratio = obs_ratio

        vals = [v for row in s.values for v in row if v is not None]
        if not vals:
            s.grounding_class = GroundingClass.UNIFORM.value
            s.raster_basis = []
            s.observed_ratio = 0.0
            continue
        mn, mx = min(vals), max(vals)
        unique_count = len(set(round(v, 6) for v in vals))

        # Check optical ratio for satellite occlusion/cloud gaps
        optical_ratio = 1.0
        for k in ["ndvi", "NDVI", "ndmi", "NDMI"]:
            if k in ratios:
                optical_ratio = min(optical_ratio, ratios[k])

        # P0-D: ASMAE state support class overrides
        prov = s.provenance or {}
        supp_cls = prov.get("support_class") or prov.get("state_support_class")
        if (
            s_type.startswith("ASMAE_")
            or "ASMAE" in s_type
            or s_type.startswith("COMPOSITE_")
        ):
            if apply_composite_scouting_grounding(s, unique_count):
                pass
            elif supp_cls == "derived_diagnostic":
                s.observed_ratio = 0.0
                s.grounding_class = (
                    GroundingClass.MODEL_ASSISTED_RASTER.value
                    if unique_count > 1
                    else GroundingClass.UNIFORM.value
                )
                prov["direct_observation"] = False
                prov["management_zone_eligible"] = False
                prov["zone_statistics_eligible"] = False
                if unique_count <= 1:
                    prov["scope"] = "plot_level"
                    prov["constant_allowed"] = True
            elif supp_cls == "prior_constrained" or prov.get("zone_statistics_eligible") is False:
                s.observed_ratio = 0.0
                s.grounding_class = GroundingClass.UNIFORM.value
                prov["zone_statistics_eligible"] = False
            elif supp_cls == "proxy_assimilated":
                s.observed_ratio = 0.0
                s.grounding_class = GroundingClass.PROXY_SPATIAL.value
                prov["zone_statistics_eligible"] = True
            elif supp_cls == "directly_assimilated":
                s.grounding_class = GroundingClass.RASTER_GROUNDED.value
                prov["zone_statistics_eligible"] = True
        elif is_high_resolution_surface(s):
            s.grounding_class = GroundingClass.MODEL_ASSISTED_RASTER.value
        elif "RESOLUTION" in s_type:
            if basis:
                effective_ratio = max(obs_ratio, optical_ratio)
                if effective_ratio >= 0.90:
                    s.grounding_class = GroundingClass.RASTER_GROUNDED.value
                elif effective_ratio >= 0.30:
                    s.grounding_class = GroundingClass.PARTIAL_RASTER_GROUNDED.value
                else:
                    s.grounding_class = GroundingClass.MODEL_ASSISTED_RASTER.value
            else:
                s.grounding_class = GroundingClass.UNIFORM.value

            if unique_count <= 1:
                if not s.provenance:
                    s.provenance = {}
                s.provenance["is_spatially_uniform_class"] = True
        elif basis and unique_count > 1:
            if optical_ratio >= 0.90:
                s.grounding_class = GroundingClass.RASTER_GROUNDED.value
            elif 0.30 <= optical_ratio < 0.90:
                s.grounding_class = GroundingClass.PARTIAL_RASTER_GROUNDED.value
            else:
                s.grounding_class = GroundingClass.MODEL_ASSISTED_RASTER.value
        else:
            if unique_count <= 1:
                s.grounding_class = GroundingClass.UNIFORM.value
            elif unique_count <= len(l1_data.zone_masks or {}) + 2:
                s.grounding_class = GroundingClass.ZONE_GROUNDED.value
            else:
                s.grounding_class = GroundingClass.PROXY_SPATIAL.value

        from services.agribrain.layer10_sire.surfaces.derivation_lineage import (
            attach_derived_surface_lineage,
        )
        attach_derived_surface_lineage(s, l1_data)

    # --- Step 4: Extract management zones & compute histograms ---
    field_valid_cells = _compute_field_valid_cells(l10_input, H, W, surfaces)
    labeled_zones = []
    zone_state_by_surface = {}
    unc_hists_typed = []
    delta_hists = []
    comparisons = []
    topo_warnings = []
    topo_ok = True

    if render_as_spatial:
        try:
            labeled_zones, zone_state_by_surface = extract_zones(
                surfaces, H, W, field_valid_cells=field_valid_cells
            )
        except Exception as e:
            topo_ok = False
            logger.warning(f"Zone extraction failed: {e}")
            topo_warnings.append(json.dumps({
                "warning": "zone_extraction_failed",
                "reason": str(e)
            }))

    # Field Histograms
    field_hists = []
    try:
        field_hists = compute_field_histograms(surfaces, field_valid_cells=field_valid_cells)
    except Exception as e:
        logger.warning(f"Field histogram generation failed: {e}")
        topo_warnings.append(json.dumps({
            "warning": "histogram_failed",
            "surface": "field_level_all",
            "reason": str(e)
        }))

    # Zone Histograms
    zone_hists = []
    try:
        if render_as_spatial and labeled_zones:
            zone_hists = compute_zone_histograms(surfaces, labeled_zones)
    except Exception as e:
        logger.warning(f"Zone histogram generation failed: {e}")
        topo_warnings.append(json.dumps({
            "warning": "histogram_failed",
            "surface": "zone_level_all",
            "reason": str(e)
        }))

    # Uncertainty Histograms
    try:
        unc_hists_raw = compute_uncertainty_histograms(surfaces)
        # Convert uncertainty dicts to HistogramArtifact-compatible form
        from services.agribrain.layer10_sire.schema import HistogramArtifact
        for uh in unc_hists_raw:
            st = uh.get('surface_type', '')
            hist_data = uh.get('histogram', {})
            stats = uh.get('stats', {})
            try:
                st_enum = SurfaceType(st)
            except (ValueError, KeyError):
                continue
            bins_list = hist_data.get('bins', [])
            counts_list = hist_data.get('counts', [])
            if len(bins_list) > len(counts_list):
                bins_list = bins_list[:len(counts_list) + 1]
            unc_hists_typed.append(HistogramArtifact(
                surface_type=st_enum,
                region_id='field',
                bin_edges=[float(b) for b in bins_list],
                bin_counts=[int(c) for c in counts_list],
                total_pixels=field_valid_cells if (field_valid_cells and field_valid_cells > 0) else H * W,
                valid_pixels=stats.get('n_pixels', 0),
                mean=stats.get('mean', 0.0),
                std=stats.get('std', 0.0),
                p10=stats.get('min', 0.0),
                p90=stats.get('max', 0.0),
            ))
    except Exception as e:
        logger.warning(f"Uncertainty histogram generation failed: {e}")
        topo_warnings.append(json.dumps({
            "warning": "histogram_failed",
            "surface": "uncertainty_all",
            "reason": str(e)
        }))

    # Delta histograms: compare first vs last time step per surface
    try:
        if l1_data.raster_maps:
            # Build previous snapshot from first time step if ≥2 time steps
            ft = l10_input.field_tensor
            time_idx = getattr(ft, 'time_index', []) or []
            data_4d = getattr(ft, 'data', None)
            if data_4d and len(time_idx) >= 2:
                # NDVI is channel 0 typically
                prev_grid = [[data_4d[0][r][c][0] if data_4d[0][r][c] else None
                             for c in range(W)] for r in range(H)]
                curr_grid = [[data_4d[-1][r][c][0] if data_4d[-1][r][c] else None
                             for c in range(W)] for r in range(H)]
                delta_result = compute_delta_histograms(
                    curr_grid, prev_grid, H, W, surface_name='NDVI'
                )
                if delta_result.get('counts'):
                    from services.agribrain.layer10_sire.schema import DeltaHistogram
                    shift = 'STABLE'
                    mean_ch = delta_result.get('stats', {}).get('mean', 0.0)
                    if mean_ch > 0.02: shift = 'IMPROVING'
                    # GAP 6 fix: was 'DEGRADING' but SidebarFarmerView.tsx checks
                    # for 'DECLINING'. Declining crops showed no trend label at all.
                    elif mean_ch < -0.02: shift = 'DECLINING'
                    delta_hists.append(DeltaHistogram(
                        surface_type=SurfaceType.NDVI_CLEAN,
                        region_id='field',
                        date_from=time_idx[0],
                        date_to=time_idx[-1],
                        bin_edges=[float(b) for b in delta_result['bins']],
                        bin_counts=[int(c) for c in delta_result['counts']],
                        mean_change=round(mean_ch, 4),
                        shift_direction=shift,
                    ))
    except Exception as e:
        logger.warning(f"Delta histogram generation failed: {e}")
        topo_warnings.append(json.dumps({
            "warning": "histogram_failed",
            "surface": "delta_all",
            "reason": str(e)
        }))

    # Zone comparisons: if 2+ zones and a key surface, run compare
    try:
        if len(labeled_zones) >= 2:
            key_surface_types = {SurfaceType.NDVI_CLEAN, SurfaceType.COMPOSITE_RISK, SurfaceType.YIELD_P50}
            for s in surfaces:
                if s.semantic_type in key_surface_types:
                    try:
                        comp = compare_zones(s, labeled_zones[0], labeled_zones[1])
                        if 'error' not in comp:
                            comparisons.append(comp)
                    except Exception:
                        pass
    except Exception:
        pass

    hist_bundle = HistogramBundle(
        field_histograms=field_hists,
        zone_histograms=zone_hists,
        delta_histograms=delta_hists,
        uncertainty_histograms=unc_hists_typed,
    )
    performance_timers_ms["histograms"] = round((time.perf_counter() - _phase_started) * 1000.0, 3)
    _phase_started = time.perf_counter()

    # --- Step 6: Render manifest + quicklooks ---
    manifest = build_render_manifest(surfaces, l10_input)

    quicklook_map = {}
    if render_as_spatial:
        for s in surfaces:
            try:
                # V65G: Use actual surface dimensions (experimental surfaces may differ from H×W)
                s_h = len(s.values)
                s_w = len(s.values[0]) if s_h > 0 else 0
                ql = generate_quicklook(s, s_h, s_w, target_size=min(32, max(s_h, s_w)))
                quicklook_map[s.semantic_type.value] = ql
            except Exception:
                pass

    # --- Step 7: Build output with real runtime checks ---
    # V65G: Experimental surfaces have different dimensions — exclude from alignment check
    grid_ok = render_as_spatial and all(
        len(s.values) == H and all(len(row) == W for row in s.values)
        for s in surfaces
        if not is_high_resolution_surface(s)
    )

    # Real detail conservation: check that field-mean is preserved
    # For each surface, compute mean across full grid. If any surface has
    # variance of cell values but zero mean, that's suspicious.
    detail_ok = True
    for s in surfaces:
        # V65G: Skip experimental surfaces (different grid dimensions)
        if is_high_resolution_surface(s):
            continue
        s_h = len(s.values)
        s_w = len(s.values[0]) if s_h > 0 else 0
        vals = [s.values[r][c] for r in range(s_h) for c in range(s_w) if s.values[r][c] is not None]
        if not vals:
            detail_ok = False
            break
        mean_val = sum(vals) / len(vals)
        # Conservation check: if micro-objects exist, verify redistribution
        # didn't shift the field mean by more than 1%
        if micro_objects and mean_val != 0:
            redistributed_vals = []
            for obj in micro_objects:
                for rr, cc in obj.cell_indices:
                    if 0 <= rr < s_h and 0 <= cc < s_w and s.values[rr][cc] is not None:
                        redistributed_vals.append(s.values[rr][cc])
            if redistributed_vals:
                redis_mean = sum(redistributed_vals) / len(redistributed_vals)
                if abs(mean_val) > 1e-6:
                    drift = abs(redis_mean - mean_val) / abs(mean_val)
                    if drift > 0.01:  # 1% drift threshold
                        detail_ok = False
                        break
    if not render_as_spatial:
        detail_ok = False

    # Topology result
    if not topo_ok:
        topo_warnings.append("Zone topology violation detected")

    quality = QualityReport(
        degradation_mode=degradation,
        reliability_score=1.0 if not missing else 0.5,
        surfaces_generated=len(surfaces),
        surfaces_skipped=skipped,
        zones_generated=len(labeled_zones),
        micro_objects_detected=len(micro_objects),
        grid_alignment_ok=grid_ok,
        detail_conservation_ok=detail_ok,
        zone_state_by_surface=zone_state_by_surface,
        missing_upstream=missing,
        warnings=topo_warnings,
        component_failures=component_failures,
        degradation_codes=list(dict.fromkeys(degradation_codes)),
    )

    # Fix A: compute NDVI surface mean for phenology stage fallback before building provenance dict
    _prov_ndvi_surf = next(
        (s for s in surfaces if getattr(s, 'semantic_type', None) and
         hasattr(s.semantic_type, 'value') and s.semantic_type.value == 'NDVI_CLEAN'),
        None
    )
    _prov_ndvi_mean = None
    if _prov_ndvi_surf is not None:
        _pv = [v for row in (_prov_ndvi_surf.values or []) for v in row if v is not None]
        _prov_ndvi_mean = sum(_pv) / len(_pv) if _pv else None
    _phenology_context = _resolve_phenology_context(
        l10_input.veg_int,
        _prov_ndvi_mean,
        crop=getattr(l10_input, "crop", "") or "",
    )
    _prov_pheno_stage = _phenology_context["resolved_crop_stage"]

    output = Layer10Output(
        run_id=run_id,
        publication_run_id=run_id,
        request_run_id=run_id,
        publication_id=f"pub_{cache_key[:16]}",
        surface_schema_version=SURFACES_SCHEMA_VERSION,
        timestamp=ts,
        input_run_ids=input_run_ids,
        surface_pack=surfaces,
        zone_pack=labeled_zones,
        micro_objects=micro_objects,
        histogram_bundle=hist_bundle,
        render_manifest=manifest,
        quicklooks=quicklook_map,
        quality_report=quality,
        resolved_crop_stage=_prov_pheno_stage,
        phenology_context=_phenology_context,
        provenance={
            "pipeline": "SIRE_v11.0",
            "agribrain_run_id": run_id,
            "intelligence_snapshot_id": run_id,
            "generated_at": ts,
            "source_window": {
                "start": str(getattr(l10_input, "reference_date", "") or ""),
                "end": str(getattr(l10_input, "reference_date", "") or ""),
            },
            "surface_schema_version": SURFACES_SCHEMA_VERSION,
            "publication_run_id": run_id,
            "request_run_id": run_id,
            "publication_id": f"pub_{cache_key[:16]}",
            "ndvi_mask_diagnostic": ndvi_mask_diagnostic,
            "policy_model": "canonical_science_with_client_views",
            "visual_fusion_materialization": visual_fusion_materialization,
            "degradation": degradation.value,
            "visual_intensity": getattr(l10_input, "visual_intensity", 0.40),
            "grid": f"{H}x{W}@{l10_input.resolution_m}m",
            "grid_bounds": list(grid_bounds) if grid_bounds else None,
            "grid_validity": "valid" if render_as_spatial else f"invalid:{grid_spec_status}",
            "grid_spec_status": grid_spec_status,
            "spatial_materialization_allowed": render_as_spatial,
            "spatial_strategy": (
                "RASTER" if l1_data.raster_maps
                else "ZONE_RASTERIZE" if l1_data.zone_masks
                else "BROADCAST"
            ),
            # GAP 4 + Fix A: reconciled stage with surface-mean fallback so the
            # UI always shows an agronomically correct stage, even with empty Kalman records.
            # Compatibility alias only. ``resolved_crop_stage`` and its context
            # are the canonical publication/browser authority.
            "phenology_stage": _prov_pheno_stage,
            "resolved_crop_stage": _prov_pheno_stage,
            "phenology_context": _phenology_context,
            "grounding_summary": {
                gc: sum(1 for s in surfaces if s.grounding_class == gc)
                for gc in [g.value for g in GroundingClass]
            },
            "histogram_families": {
                "field": len(field_hists),
                "zone": len(zone_hists),
                "delta": len(delta_hists),
                "uncertainty": len(unc_hists_typed),
                "comparisons": len(comparisons),
            },
            "temporal_engine": {
                "temporal_surfaces": sum(
                    1 for s in surfaces
                    if s.semantic_type.value in (
                        'NDVI_DELTA_7D', 'STRESS_MOMENTUM', 'GROWTH_TREND_7D',
                        'DROUGHT_TREND', 'RISK_MOMENTUM', 'YIELD_TRAJECTORY',
                        'PRECIPITATION_FORECAST', 'TEMPERATURE_FORECAST',
                    )
                ),
                "execution_surfaces": sum(
                    1 for s in surfaces
                    if s.semantic_type.value in (
                        'EXECUTION_READINESS', 'INTERVENTION_PRIORITY',
                        'INTERVENTION_TIMING', 'CONFLICT_RESOLUTION',
                    )
                ),
            },
            "weather_indices": {
                "spi_1mo": getattr(l10_input.field_tensor, "provenance", {}).get("spi_1mo"),
                "spei_3mo": getattr(l10_input.field_tensor, "provenance", {}).get("spei_3mo"),
                "ndvi_anomaly": getattr(l10_input.field_tensor, "provenance", {}).get("ndvi_anomaly")
            }
        },
    )

    # --- Step 8: Wire export packs into output ---
    try:
        if render_as_spatial:
            from dataclasses import asdict
            output.raster_pack = [asdict(r) for r in export_raster_pack(output)]
            output.vector_pack = [asdict(v) for v in export_vector_pack(output)]
            output.tile_manifest = asdict(export_tile_manifest(output, H, W, l10_input.resolution_m))
    except Exception:
        pass  # Export is non-fatal

    # --- Step 9: Build TemporalBundle (14-day T-7 → T+7) ---
    try:
        temporal_bundle = build_temporal_bundle(
            l1_data=l1_data,
            l2_data=l2_data,
            l3_data=l3_data,
            surfaces=surfaces,
            reference_date=l10_input.reference_date,
            forecast_context=l10_input.forecast_context,
            H=H, W=W,
        )
        output.temporal_bundle = temporal_bundle
    except Exception:
        pass  # TemporalBundle is non-fatal

    # --- Step 10: Enforce invariants ---
    from services.agribrain.layer10_sire.one_meter_policy import build_one_meter_policy_summary, enforce_one_meter_policy
    one_meter_summary = build_one_meter_policy_summary(output.surface_pack)
    enforce_one_meter_policy(one_meter_summary)
    output.provenance["one_meter_policy_summary"] = one_meter_summary

    violations = enforce_layer10_invariants(output, H, W)
    if violations:
        output.quality_report.warnings = violations

    # Invariant checks and diagnostic status can reduce reliability
    asmae_state = dict(getattr(l1_data, "asmae_evidence_state", {}) or getattr(l10_input, "asmae_evidence_state", {}) or {})
    asmae_diag_only = bool(asmae_state.get("diagnostic_only", True))
    asmae_prod_usable = bool(asmae_state.get("production_usable", False))
    if asmae_diag_only:
        output.quality_report.degradation_codes.append("DIAGNOSTIC_AUTHORITY_ONLY")
    if not asmae_prod_usable:
        output.quality_report.degradation_codes.append("PRODUCTION_USE_NOT_AUTHORIZED")
    output.quality_report.degradation_codes = list(dict.fromkeys(
        output.quality_report.degradation_codes
    ))
    if asmae_diag_only or not asmae_prod_usable:
        output.quality_report.reliability_score = min(
            output.quality_report.reliability_score, 0.48
        )

    if not render_as_spatial:
        invalid_grid_warning = f"invalid_geospatial_grid:{grid_spec_status}"
        if invalid_grid_warning not in output.quality_report.warnings:
            output.quality_report.warnings.append(invalid_grid_warning)
        output.quality_report.grid_alignment_ok = False
        output.quality_report.reliability_score = min(
            output.quality_report.reliability_score, 0.30
        )
    if (
        output.quality_report.reliability_score < 0.60
        or not output.quality_report.grid_alignment_ok
        or not output.quality_report.detail_conservation_ok
        or asmae_diag_only
    ):
        output.quality_report.degradation_mode = SIREDegradation.DEGRADED
        output.provenance["degradation"] = SIREDegradation.DEGRADED.value
        
    # --- Step 11: Inject Phase B/C Packs (Explainability, Scenario, History) ---
    output = build_premium_packs(l10_input, output)

    # --- Step 12: V61D — Latest Free Visual Basemap Provider ---
    try:
        from visual_sources.cbers import VisualSourceConfig
        from visual_sources.provider import get_visual_source_for_plot

        visual_config = None
        if hasattr(l10_input, "visual_config") and l10_input.visual_config:
            vc = l10_input.visual_config
            if isinstance(vc, dict):
                visual_config = VisualSourceConfig(
                    cbers_max_cloud=vc.get("cbers_max_cloud", 40.0),
                    sentinel_max_cloud=vc.get("sentinel_max_cloud", 20.0),
                    max_scene_age_days=vc.get("max_scene_age_days"),
                    prefer_provider=vc.get("prefer_provider", "cbers")
                )
            elif isinstance(vc, VisualSourceConfig):
                visual_config = vc

        # Bounding box from GridSpec bounds or fallback
        bbox = None
        if l10_input.field_tensor and hasattr(l10_input.field_tensor, "grid_spec") and l10_input.field_tensor.grid_spec:
            gs = l10_input.field_tensor.grid_spec
            if hasattr(gs, "bounds") and gs.bounds:
                bbox = list(gs.bounds)
        if not bbox:
            # Fallback bounds around 3.0, 36.0
            bbox = [2.99, 35.99, 3.01, 36.01]

        output.visual_source = get_visual_source_for_plot(
            plot_id=l10_input.plot_id or "unknown",
            bbox=bbox,
            config=visual_config
        )
    except Exception as e:
        print(f"[L10-V61D] Visual source integration failed: {e}", file=sys.stderr)
        allow_synthetic = os.getenv("ALLOW_SYNTHETIC_VISUAL_PREVIEW", "false").lower() == "true"
        if allow_synthetic:
            output.visual_source = {
                "status": "synthetic_preview",
                "provider": "local_synthetic_visual",
                "collection": "LOCAL-SYNTHETIC-WPM-2M",
                "native_resolution_m": 2.0,
                "scene_date": "2026-06-01",
                "tile_url": f"/api/agribrain/visual-tile/local_synthetic/{{z}}/{{x}}/{{y}}?scene_id=synthetic_{l10_input.plot_id or 'unknown'}",
                "is_mock": True,
                "role": "map_context_only",
                "state_update_allowed": False,
                "used_for_agronomic_inference": False,
                "fallback_reason": f"All live providers unavailable; generated preview tile for no-blank-map safety. Error: {e}"
            }
        else:
            output.visual_source = {
                "status": "unavailable",
                "provider": "none",
                "collection": "none",
                "native_resolution_m": 0.0,
                "scene_date": "2026-06-01",
                "tile_url": None,
                "is_mock": False,
                "role": "map_context_only",
                "state_update_allowed": False,
                "used_for_agronomic_inference": False,
                "fallback_reason": f"Visual imagery is not available for this plot. Error: {e}"
            }

    # --- Step 13: Build backend surface_inventory and resolve mode_surface_plan ---
    try:
        # Check if composite ASMAE surfaces exist
        has_composite_asmae = any(
            (s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type)) == "COMPOSITE_ADVISORY_CANOPY"
            for s in output.surface_pack
        )

        # Retrieve the immutable ASMAE scientific evidence state.  Publication
        # surfaces are tracked separately below and may not promote/demote it.
        ctx_pkg = getattr(l10_input.field_tensor, "_context_package", None) if l10_input.field_tensor else None
        asmae_output = getattr(ctx_pkg, "asmae_output", None) if ctx_pkg else None
        
        ev_state = {}
        if isinstance(asmae_output, dict):
            ev_state = asmae_output.get("asmae_evidence_state", {})
            output.asmae_plot_state_artifact = (
                asmae_output.get("plot_state_artifact", {}) or {}
            )
        elif asmae_output:
            ev_state = getattr(asmae_output, "asmae_evidence_state", {})
            output.asmae_plot_state_artifact = (
                getattr(asmae_output, "plot_state_artifact", {}) or {}
            )
        if isinstance(asmae_output, dict):
            output.asmae_feature_pack = asmae_output.get("asmae_feature_pack", {}) or {}
        elif asmae_output:
            output.asmae_feature_pack = getattr(asmae_output, "asmae_feature_pack", {}) or {}
        
        asmae_run_record = getattr(l1_data, "asmae_run_record", None) if l1_data is not None else None
        rollout_block_reason = None
        if isinstance(asmae_run_record, dict) and asmae_run_record.get("status") in ("skipped", "failed"):
            rollout_block_reason = asmae_run_record.get("reason") or "rollout_disabled"

        core_state, publication_state, publication_demotion = (
            separate_asmae_evidence_and_publication(
                ev_state,
                has_composite_surface=has_composite_asmae,
                rollout_block_reason=rollout_block_reason,
                has_plot_state_artifact=bool(output.asmae_plot_state_artifact),
            )
        )
        output.core_asmae_evidence_state = dict(core_state)
        output.asmae_evidence_state = dict(core_state)
        output.publication_surface_state = publication_state
        output.publication_demotion = publication_demotion

        from services.agribrain.layer10_sire.mode_surface_resolver import resolve_mode_surface_plan

        # Build engines list
        engines_list = []
        if l10_input.field_tensor:
            engines_list.append({"id": "L1", "status": "COMPLETED"})
        if l10_input.veg_int:
            engines_list.append({"id": "L2", "status": "COMPLETED"})
        if l10_input.decision:
            engines_list.append({"id": "L3", "status": "COMPLETED"})
        if l10_input.nutrients:
            engines_list.append({"id": "L4", "status": "COMPLETED"})
        if l10_input.bio:
            engines_list.append({"id": "L5", "status": "COMPLETED"})
        if l10_input.exec_state:
            engines_list.append({"id": "L6", "status": "COMPLETED"})
        if l10_input.planning:
            engines_list.append({"id": "L7", "status": "COMPLETED"})
        if l10_input.prescriptive:
            engines_list.append({"id": "L8", "status": "COMPLETED"})
            
        plan = resolve_mode_surface_plan(output.surface_pack, engines_list, source_policy=l10_input.source_policy)
        output.mode_surface_plan = plan
        
        # Build backend surface inventory
        surface_inventory = {}
        ALL_BACKEND_KNOWN_SURFACES = [
            "NDVI_CLEAN", "NDVI_DEVIATION", "BASELINE_ANOMALY",
            "WATER_STRESS_PROB", "NUTRIENT_STRESS_PROB", "SALINITY_STRESS",
            "COMPOSITE_RISK", "DATA_RELIABILITY", "DATA_CONFIDENCE", "UNCERTAINTY_SIGMA",
            "RESOLUTION_COVERAGE", "GAP_FILL_MASK",
            "CANOPY_ASMAE_VIGOR", "WATER_ASMAE_CANOPY_WATER", "WATER_ASMAE_ROOT_ZONE_WATER",
            "NUTRIENT_ASMAE_CHLOROPHYLL_PROXY", "SALINITY_ASMAE_STRESS", "RISK_ASMAE_DIAGNOSTIC",
            "ASMAE_POSTERIOR_CONCENTRATION", "RESOLUTION_ASMAE_EFFECTIVE", "ASMAE_VISUAL_FUSION_CANOPY",
            "COMPOSITE_ADVISORY_CANOPY", "COMPOSITE_VEG_ATTENTION",
            "COMPOSITE_WATER_SUPPORT", "COMPOSITE_NUTRIENT_SUPPORT",
            "COMPOSITE_SALINITY_STRESS", "COMPOSITE_RISK_DIAGNOSTIC",
            "COMPOSITE_CONFIDENCE", "COMPOSITE_EFFECTIVE_RESOLUTION",
            "COMPOSITE_TEXTURE_DETAIL",
            "NDVI_CLEAN_EXPERIMENTAL_FINE_DETAIL",
            "EXPERIMENTAL_VISUAL_CANOPY",
            "EXPERIMENTAL_VISUAL_CANOPY_HIGHRES",
            "EXPERIMENTAL_TEXTURE_SUPPORT_MASK",
            "EXPERIMENTAL_STRICT_FINE_DETAIL_CANDIDATE_MASK",
            "EXPERIMENTAL_TEXTURE_CONFIDENCE",
            "EXPERIMENTAL_GAPFILL_MASK",
            "EXPERIMENTAL_PARENT_MEAN_ERROR",
            "COMPOSITE_ARCHIVE_SUPPORT",
            "COMPOSITE_RETRO_SCORE",
            "COMPOSITE_ML_SUPPORT",
            "COMPOSITE_BMA_DISAGREEMENT",
            "COMPOSITE_UNCERTAINTY"
        ]
        
        surface_by_type = {s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type): s for s in output.surface_pack}
        
        for st in ALL_BACKEND_KNOWN_SURFACES:
            s = surface_by_type.get(st)
            if s:
                gc = s.grounding_class or "UNIFORM"
                status = "available_raster"
                if gc in ["UNIFORM", "BROADCAST"]:
                    status = "plot_level_only"
                elif gc == "PROXY_SPATIAL":
                    status = "proxy_only"
                prov = s.provenance or {}
                if not isinstance(prov, dict):
                    prov = {}
                from services.agribrain.layer10_sire.mode_surface_resolver import trust_badges_for_surface
                trust_badges = trust_badges_for_surface(s, prov.get("trust_badges") if prov else None)
                        
                surface_inventory[st] = {
                    "surfaceType": st,
                    "status": status,
                    "groundingClass": gc,
                    "reason": prov.get("warning_wording", f"{st.replace('_', ' ').capitalize()} surface is available"),
                    "trust_badges": trust_badges
                }
            else:
                fallback_surf = None
                fallback_class = "unavailable"
                reason = f"No {st} surface generated by backend"
                
                if st == "NDVI_CLEAN":
                    if "COMPOSITE_ADVISORY_CANOPY" in surface_by_type:
                        fallback_surf = "COMPOSITE_ADVISORY_CANOPY"
                        fallback_class = "asmae_diagnostic"
                        reason = "NDVI_CLEAN missing; using composite canopy advisory"
                    elif "CANOPY_ASMAE_VIGOR" in surface_by_type:
                        fallback_surf = "CANOPY_ASMAE_VIGOR"
                        fallback_class = "asmae_diagnostic"
                        reason = "NDVI_CLEAN missing; using ASMAE_VIGOR diagnostic raster"
                elif st == "WATER_STRESS_PROB":
                    if "COMPOSITE_WATER_SUPPORT" in surface_by_type:
                        fallback_surf = "COMPOSITE_WATER_SUPPORT"
                        fallback_class = "asmae_diagnostic"
                        reason = "WATER_STRESS_PROB missing; using composite water support"
                    elif "WATER_ASMAE_CANOPY_WATER" in surface_by_type:
                        fallback_surf = "WATER_ASMAE_CANOPY_WATER"
                        fallback_class = "asmae_diagnostic"
                        reason = "WATER_STRESS_PROB missing; using ASMAE canopy-water diagnostic"
                    elif "WATER_ASMAE_ROOT_ZONE_WATER" in surface_by_type:
                        fallback_surf = "WATER_ASMAE_ROOT_ZONE_WATER"
                        fallback_class = "asmae_diagnostic"
                        reason = "WATER_STRESS_PROB missing; using ASMAE root-zone water estimate"
                elif st == "NUTRIENT_STRESS_PROB":
                    if "COMPOSITE_NUTRIENT_SUPPORT" in surface_by_type:
                        fallback_surf = "COMPOSITE_NUTRIENT_SUPPORT"
                        fallback_class = "asmae_diagnostic"
                        reason = "NUTRIENT_STRESS_PROB missing; using composite nutrient support"
                    elif "NUTRIENT_ASMAE_CHLOROPHYLL_PROXY" in surface_by_type:
                        fallback_surf = "NUTRIENT_ASMAE_CHLOROPHYLL_PROXY"
                        fallback_class = "asmae_diagnostic"
                        reason = "NUTRIENT_STRESS_PROB missing; using ASMAE chlorophyll proxy"
                elif st == "SALINITY_STRESS":
                    if "COMPOSITE_SALINITY_STRESS" in surface_by_type:
                        fallback_surf = "COMPOSITE_SALINITY_STRESS"
                        fallback_class = "asmae_diagnostic"
                        reason = "SALINITY_STRESS missing; using composite salinity stress"
                    elif "SALINITY_ASMAE_STRESS" in surface_by_type:
                        fallback_surf = "SALINITY_ASMAE_STRESS"
                        fallback_class = "asmae_diagnostic"
                        reason = "SALINITY_STRESS missing; using ASMAE salinity diagnostic raster"
                elif st == "COMPOSITE_RISK":
                    if "COMPOSITE_RISK_DIAGNOSTIC" in surface_by_type:
                        fallback_surf = "COMPOSITE_RISK_DIAGNOSTIC"
                        fallback_class = "asmae_diagnostic"
                        reason = "COMPOSITE_RISK missing; using composite risk diagnostic"
                    elif "RISK_ASMAE_DIAGNOSTIC" in surface_by_type:
                        fallback_surf = "RISK_ASMAE_DIAGNOSTIC"
                        fallback_class = "asmae_diagnostic"
                        reason = "COMPOSITE_RISK missing; using ASMAE diagnostic risk composite"
                elif st in ["DATA_RELIABILITY", "DATA_CONFIDENCE"]:
                    if "COMPOSITE_CONFIDENCE" in surface_by_type:
                        fallback_surf = "COMPOSITE_CONFIDENCE"
                        fallback_class = "asmae_diagnostic"
                        reason = f"{st} missing; using composite confidence"
                    elif "ASMAE_POSTERIOR_CONCENTRATION" in surface_by_type:
                        fallback_surf = "ASMAE_POSTERIOR_CONCENTRATION"
                        fallback_class = "asmae_diagnostic"
                        reason = f"{st} missing; using canonical ASMAE posterior concentration"
                elif st == "RESOLUTION_COVERAGE":
                    if "COMPOSITE_EFFECTIVE_RESOLUTION" in surface_by_type:
                        fallback_surf = "COMPOSITE_EFFECTIVE_RESOLUTION"
                        fallback_class = "asmae_diagnostic"
                        reason = "RESOLUTION_COVERAGE missing; using composite effective resolution"
                    elif "RESOLUTION_ASMAE_EFFECTIVE" in surface_by_type:
                        fallback_surf = "RESOLUTION_ASMAE_EFFECTIVE"
                        fallback_class = "asmae_diagnostic"
                        reason = "RESOLUTION_COVERAGE missing; using ASMAE effective resolution"

                        
                surface_inventory[st] = {
                    "surfaceType": st,
                    "status": "missing",
                    "reason": reason,
                }
                if fallback_surf:
                    surface_inventory[st].update({
                        "fallback_surface": fallback_surf,
                        "fallback_class": fallback_class
                    })
        output.surface_inventory = surface_inventory
        
        # ── V92.4-BC: Build mode_display_state ─────────────────────────
        # Backend-authoritative display level per mode.
        # displayLevel: raster | asmae_diagnostic | proxy | plot_level | visual_only | unavailable
        # authorityLevel: prescription_allowed | decision_support | scout | verify | monitor | visual_only
        MODE_EVIDENCE_LADDERS = {
            "canopy": [
                ("asmae_diagnostic", "ASMAE_VISUAL_FUSION_CANOPY"),
                ("asmae_diagnostic", "CANOPY_ASMAE_VIGOR"),
                ("raster", "NDVI_CLEAN"),
            ],
            "veg_attention": [
                ("raster", "NDVI_DEVIATION"),
                ("raster", "BASELINE_ANOMALY"),
                ("asmae_diagnostic", "VEG_ATTENTION_ASMAE_DIAGNOSTIC"),
                ("asmae_diagnostic", "VEG_ATTENTION_ASMAE_CONFLICT"),
                ("asmae_diagnostic", "VEG_ATTENTION_ASMAE_DISAGREEMENT"),
                ("asmae_diagnostic", "ASMAE_BMA_DISAGREEMENT"),
                ("asmae_diagnostic", "ASMAE_CROSS_LAYER_CONFLICT"),
            ],
            "water_stress": [
                ("raster", "WATER_STRESS_PROB"),
                ("asmae_diagnostic", "WATER_ASMAE_CANOPY_WATER"),
                ("asmae_diagnostic", "WATER_ASMAE_ROOT_ZONE_WATER"),
            ],
            "nutrient_risk": [
                ("raster", "NUTRIENT_STRESS_PROB"),
                ("asmae_diagnostic", "NUTRIENT_ASMAE_CHLOROPHYLL_PROXY"),
            ],
            "salinity": [
                ("raster", "SALINITY_STRESS"),
                ("asmae_diagnostic", "SALINITY_ASMAE_STRESS"),
            ],
            "composite_risk": [
                ("raster", "COMPOSITE_RISK"),
                ("asmae_diagnostic", "RISK_ASMAE_DIAGNOSTIC"),
            ],
            "uncertainty": [
                ("raster", "DATA_RELIABILITY"),
                ("raster", "DATA_CONFIDENCE"),
                ("raster", "UNCERTAINTY_SIGMA"),
                ("asmae_diagnostic", "ASMAE_POSTERIOR_CONCENTRATION"),
            ],
            "resolution_coverage": [
                ("raster", "RESOLUTION_COVERAGE"),
                ("asmae_diagnostic", "RESOLUTION_ASMAE_EFFECTIVE"),
            ],
        }
        
        DISPLAY_LEVEL_AUTHORITY = {
            "raster": "decision_support",
            "asmae_diagnostic": "scout",
            "proxy": "verify",
            "plot_level": "monitor",
            "visual_only": "visual_only",
            "unavailable": "visual_only",
        }
        
        NON_SPATIAL_GC = {"UNIFORM", "BROADCAST"}
        
        mode_display_state = {}
        for mode_key, ladder in MODE_EVIDENCE_LADDERS.items():
            resolved_level = "unavailable"
            resolved_surface = None
            resolved_surface_type = None
            is_spatial = False
            can_render_pixels = False
            render_kind = "none"
            trust_badges = []
            
            # V92.4-BC.1 (P0-5): Check mode_surface_plan first as ground truth
            msp_entry = (output.mode_surface_plan or {}).get(mode_key, {})
            msp_surface_type = msp_entry.get("selected_surface_type") if isinstance(msp_entry, dict) else None
            if msp_surface_type:
                msp_surface = surface_by_type.get(msp_surface_type)
                if msp_surface:
                    gc = msp_surface.grounding_class or "UNIFORM"
                    has_pixels = gc not in NON_SPATIAL_GC
                    vals = msp_surface.values or []
                    has_data = any(v is not None for row in vals for v in row) if vals else False
                    
                    if has_pixels and has_data:
                        # Determine level from the ladder entry for this surface type
                        level_from_ladder = "raster"
                        for level, st_name in ladder:
                            if st_name == msp_surface_type:
                                level_from_ladder = level
                                break
                        resolved_level = level_from_ladder
                        resolved_surface_type = msp_surface_type
                        resolved_surface = msp_surface
                        is_spatial = True
                        can_render_pixels = True
                        render_kind = "full_raster" if level_from_ladder == "raster" else "diagnostic_overlay"
                        
                        from services.agribrain.layer10_sire.mode_surface_resolver import trust_badges_for_surface
                        trust_badges = trust_badges_for_surface(msp_surface)
                    elif gc in NON_SPATIAL_GC and has_data:
                        resolved_level = "plot_level"
                        resolved_surface_type = msp_surface_type
                        resolved_surface = msp_surface
                        render_kind = "uniform_tint"
                        trust_badges = ["plot-level estimate"]
            
            # If MSP didn't resolve, walk the ladder (fallback)
            if resolved_level == "unavailable":
                for level, st_name in ladder:
                    s = surface_by_type.get(st_name)
                    if s:
                        gc = s.grounding_class or "UNIFORM"
                        has_pixels = gc not in NON_SPATIAL_GC
                        vals = s.values or []
                        has_data = any(v is not None for row in vals for v in row) if vals else False
                        
                        if has_pixels and has_data:
                            resolved_level = level
                            resolved_surface_type = st_name
                            resolved_surface = s
                            is_spatial = True
                            can_render_pixels = True
                            render_kind = "full_raster" if level == "raster" else "diagnostic_overlay"
                            
                            from services.agribrain.layer10_sire.mode_surface_resolver import trust_badges_for_surface
                            trust_badges = trust_badges_for_surface(s)
                            break
                        elif gc in NON_SPATIAL_GC and has_data:
                            # Plot-level — keep searching for spatial
                            if resolved_level == "unavailable":
                                resolved_level = "plot_level"
                                resolved_surface_type = st_name
                                resolved_surface = s
                                render_kind = "uniform_tint"
                                trust_badges = ["plot-level estimate"]
                            continue
            
            # Check for plot-level engine data even without a surface
            if resolved_level == "unavailable":
                # L3 water deficit
                if mode_key == "water_stress":
                    l3_out = l10_input.decision
                    if l3_out and hasattr(l3_out, "diagnoses"):
                        water_diag = next((d for d in (l3_out.diagnoses or []) if getattr(d, "problem_id", "") == "WATER_STRESS"), None)
                        if water_diag:
                            resolved_level = "plot_level"
                            render_kind = "uniform_tint"
                            trust_badges = ["L3 water-balance model"]
                
                # Plot-level vigor
                if mode_key == "canopy" and l10_input.veg_int:
                    vi = l10_input.veg_int
                    if hasattr(vi, "curve") and vi.curve:
                        resolved_level = "plot_level"
                        render_kind = "uniform_tint"
                        trust_badges = ["plot-level engine estimate"]
                
                # System readiness for confidence
                if mode_key == "uncertainty":
                    resolved_level = "visual_only"
                    render_kind = "badge"
                    trust_badges = ["system readiness"]
                
                # Resolution metadata
                if mode_key == "resolution_coverage":
                    resolved_level = "visual_only"
                    render_kind = "badge"
                    trust_badges = ["source metadata"]
            
            # Compute value for plot-level displays
            display_value = None
            display_units = ""
            if resolved_surface:
                vals_flat = [v for row in (resolved_surface.values or []) for v in row if v is not None]
                if vals_flat:
                    display_value = round(sum(vals_flat) / len(vals_flat), 3)
                    display_units = resolved_surface.units or ""
            
            # V92.4-BC.1 (P0-6): Water deficit — use real mm values, not severity * 100
            if mode_key == "water_stress" and resolved_level == "plot_level" and not display_value:
                l3_out = l10_input.decision
                if l3_out and hasattr(l3_out, "diagnoses"):
                    water_diag = next((d for d in (l3_out.diagnoses or []) if getattr(d, "problem_id", "") == "WATER_STRESS"), None)
                    if water_diag:
                        # Try real mm values first from operational signals
                        ops = getattr(water_diag, "operational_signals", {}) or {}
                        if isinstance(ops, dict):
                            real_mm = ops.get("cumulative_deficit_mm") or ops.get("et_deficit_mm")
                        else:
                            real_mm = None
                        if real_mm is not None:
                            display_value = round(float(real_mm), 1)
                            display_units = "mm deficit"
                        else:
                            # Fall back to severity as percentage — not mislabeled as mm
                            display_value = round(getattr(water_diag, "severity", 0) * 100, 1)
                            display_units = "% severity"
            
            authority = DISPLAY_LEVEL_AUTHORITY.get(resolved_level, "visual_only")
            
            # Build label
            MODE_LABELS = {
                "canopy": "Canopy", "veg_attention": "Veg. Attention", "water_stress": "Water",
                "nutrient_risk": "Nutrients", "salinity": "Salinity", "composite_risk": "Risk",
                "uncertainty": "Confidence", "resolution_coverage": "Resolution",
            }
            LEVEL_LABEL_SUFFIX = {
                "raster": "", "asmae_diagnostic": "ASMAE diagnostic",
                "proxy": "proxy", "plot_level": "plot-level",
                "visual_only": "visual", "unavailable": "unavailable",
            }
            base_label = MODE_LABELS.get(mode_key, mode_key)
            level_suffix = LEVEL_LABEL_SUFFIX.get(resolved_level, "")
            label = f"{base_label} · {level_suffix}" if level_suffix else base_label

            resolved_provenance = (
                getattr(resolved_surface, "provenance", {}) or {}
                if resolved_surface is not None else {}
            )
            if not isinstance(resolved_provenance, dict):
                resolved_provenance = {}
            resolved_source_reality = str(
                resolved_provenance.get("source_reality") or ""
            ).lower()
            is_authoritative_provider_raster = (
                resolved_source_reality in {
                    "provider_temporal_composite_raster",
                    "real_provider_raster",
                    "real_raster",
                    "full_scene_stack",
                }
                and resolved_provenance.get("production_usable") is True
                and resolved_provenance.get("real_provider_product") is True
                and resolved_provenance.get("diagnostic_only") is not True
            )
            if is_authoritative_provider_raster:
                raster_reason = (
                    f"Observed provider {base_label.lower()} raster; final display "
                    "follows source-policy authorization."
                )
            elif resolved_source_reality:
                raster_reason = (
                    f"Pixel-level {base_label.lower()} raster candidate from "
                    f"{resolved_source_reality}; final display follows source-policy authorization."
                )
            else:
                raster_reason = (
                    f"Pixel-level {base_label.lower()} raster candidate; source "
                    "grounding is not verified and final display requires authorization."
                )

            LEVEL_REASONS = {
                "raster": raster_reason,
                "asmae_diagnostic": f"ASMAE diagnostic {base_label.lower()} layer. Not direct satellite observation.",
                "proxy": f"Proxy {base_label.lower()} estimate.",
                "plot_level": f"No authorized pixel-level raster; using plot-level {base_label.lower()} estimate.",
                "visual_only": f"No agronomic {base_label.lower()} surface available; showing visual context.",
                "unavailable": f"No {base_label.lower()} data available.",
            }
            display_reason = LEVEL_REASONS.get(resolved_level, "")
            
            # V92.4-BC.1 (P0-7): Explicit ASMAE-not-run reason
            if resolved_level == "unavailable" and mode_key in ("canopy", "water_stress", "nutrient_risk", "salinity"):
                try:
                    from rollout.rollout_policy import should_run_asmae
                    asmae_eligible = should_run_asmae(l10_input.plot_id)
                    if not asmae_eligible:
                        display_reason = (
                            f"ASMAE diagnostic not available for this plot (not in rollout). "
                            f"{display_reason}"
                        )
                except Exception:
                    pass
            
            # V92.4-BC.2 (P0-6): Calculate ASMAE status and rejection reason for this mode
            asmae_status = "not_run"
            asmae_rejection_reason = None
            selected_asmae_surface = None

            # Map mode_key to ASMAE source and alias surface types
            ASMAE_MODE_MAP = {
                "canopy": ("ASMAE_VIGOR", "CANOPY_ASMAE_VIGOR"),
                "water_stress": ("ASMAE_CANOPY_WATER", "WATER_ASMAE_CANOPY_WATER"),
                "nutrient_risk": ("ASMAE_CHLOROPHYLL", "NUTRIENT_ASMAE_CHLOROPHYLL_PROXY"),
                "salinity": ("ASMAE_SALINITY_STRESS", "SALINITY_ASMAE_STRESS"),
                "composite_risk": (None, "RISK_ASMAE_DIAGNOSTIC"),
                "uncertainty": (None, "ASMAE_POSTERIOR_CONCENTRATION"),
                "resolution_coverage": (None, "RESOLUTION_ASMAE_EFFECTIVE"),
                "veg_attention": ("ASMAE_CROSS_LAYER_CONFLICT", "VEG_ATTENTION_ASMAE_DIAGNOSTIC"),
            }

            if mode_key in ASMAE_MODE_MAP:
                src_st, alias_st = ASMAE_MODE_MAP[mode_key]
                from rollout.rollout_policy import should_render_l10_asmae
                if not should_render_l10_asmae(l10_input.plot_id):
                    asmae_status = "not_run"
                    asmae_rejection_reason = "rollout_disabled"
                else:
                    # Check if there is any ASMAE input key in L1
                    has_asmae_in_l1 = False
                    if l1_data is not None:
                        has_asmae_in_l1 = any(
                            str(k).lower().startswith("asmae_")
                            for k in (
                                list(l1_data.raster_maps.keys())
                                + list(l1_data.raster_metadata.keys())
                                + list(l1_data.last_values.keys())
                            )
                        )
                    
                    if not has_asmae_in_l1:
                        asmae_status = "no_l1_asmae"
                        asmae_rejection_reason = "no_asmae_keys_in_l1"
                    else:
                        alias_surf = surface_by_type.get(alias_st) if alias_st else None
                        if alias_surf:
                            selected_asmae_surface = alias_st
                            if resolved_surface_type == alias_st:
                                asmae_status = "active"
                            else:
                                asmae_status = "eligible"
                        else:
                            src_surf = surface_by_type.get(src_st) if src_st else None
                            if src_surf:
                                from services.agribrain.layer10_sire.surfaces.asmae import (
                                    asmae_surface_visual_eligible,
                                    asmae_surface_pixel_visual_eligible,
                                    asmae_surface_spatially_eligible,
                                )
                                 # V92.4-BC.2: Three-tier eligibility for ASMAE status
                                vis_ok, vis_reason = asmae_surface_visual_eligible(src_surf)
                                pix_ok, pix_reason = asmae_surface_pixel_visual_eligible(src_surf, output_grid_spec=display_grid_spec)
                                auth_ok, auth_reason = asmae_surface_spatially_eligible(src_surf)
                                
                                if pix_ok:
                                    asmae_status = "visual_eligible" if not auth_ok else "authority_eligible"
                                    asmae_rejection_reason = auth_reason if not auth_ok else None
                                elif vis_ok:
                                    asmae_status = "visual_ineligible"
                                    asmae_rejection_reason = pix_reason
                                else:
                                    asmae_status = "ineligible"
                                    asmae_rejection_reason = vis_reason
                            else:
                                asmae_status = "ineligible"
                                asmae_rejection_reason = "no_source_surface"
            
            # Calculate asmae_core_status (8 states)
            asmae_core_status = "not requested"
            global_asmae_enabled = os.environ.get("ASMAE_ENABLED", "false").lower() in ("true", "1", "yes")
            if not global_asmae_enabled:
                asmae_core_status = "not requested"
            else:
                from rollout.rollout_policy import should_run_asmae, should_render_l10_asmae_diagnostic_aliases
                if not should_run_asmae(l10_input.plot_id) and not should_render_l10_asmae_diagnostic_aliases(l10_input.plot_id):
                    asmae_core_status = "skipped by rollout"
                else:
                    has_asmae_in_l1 = False
                    if l1_data is not None:
                        has_asmae_in_l1 = any(
                            str(k).lower().startswith("asmae_")
                            for k in (
                                list(l1_data.raster_maps.keys())
                                + list(l1_data.raster_metadata.keys())
                                + list(l1_data.last_values.keys())
                            )
                        )
                    
                    is_shadow = not should_run_asmae(l10_input.plot_id) and should_render_l10_asmae_diagnostic_aliases(l10_input.plot_id)
                    
                    if not has_asmae_in_l1:
                        asmae_core_status = "failed"
                    else:
                        src_st, alias_st = ASMAE_MODE_MAP.get(mode_key, (None, None))
                        src_surf = surface_by_type.get(src_st) if src_st else None
                        alias_surf = surface_by_type.get(alias_st) if alias_st else None
                        
                        if not src_surf and not alias_surf:
                            asmae_core_status = "failed"
                        elif src_surf and getattr(src_surf, "grounding_class", "UNIFORM") in ["UNIFORM", "BROADCAST"]:
                            asmae_core_status = "produced mean-only"
                        elif is_shadow:
                            asmae_core_status = "ran shadow diagnostic"
                        elif resolved_surface_type == alias_st and alias_st:
                            asmae_core_status = "visible in Layer 10"
                        elif alias_surf:
                            asmae_core_status = "ingested into Layer 1"
                        else:
                            asmae_core_status = "produced spatial raster"
            
            # If real geospatial bounds are missing, downgrade to uniform tint
            final_resolved_level = resolved_level
            final_can_render_pixels = can_render_pixels
            final_render_kind = render_kind
            
            if not render_as_spatial:
                if resolved_level != "unavailable":
                    final_resolved_level = "plot_level"
                final_can_render_pixels = False
                final_render_kind = "card_only"

            # Get ASMAE provenance/metadata
            prov = {}
            if alias_st and alias_st in surface_by_type:
                prov = getattr(surface_by_type[alias_st], "provenance", {}) or {}
            elif resolved_surface and (getattr(resolved_surface, "type", "").startswith("ASMAE_") or "ASMAE" in getattr(resolved_surface, "type", "")):
                prov = getattr(resolved_surface, "provenance", {}) or {}

            # Define all registered ASMAE aliases for this mode
            ASMAE_ALIASES_BY_MODE = {
                "canopy": {"CANOPY_ASMAE_VIGOR", "ASMAE_VISUAL_FUSION_CANOPY"},
                "water_stress": {"WATER_ASMAE_CANOPY_WATER", "WATER_ASMAE_ROOT_ZONE_WATER"},
                "nutrient_risk": {"NUTRIENT_ASMAE_CHLOROPHYLL_PROXY"},
                "salinity": {"SALINITY_ASMAE_STRESS"},
                "composite_risk": {"RISK_ASMAE_DIAGNOSTIC"},
                "uncertainty": {"ASMAE_POSTERIOR_CONCENTRATION"},
                "resolution_coverage": {"RESOLUTION_ASMAE_EFFECTIVE"},
                "veg_attention": {"VEG_ATTENTION_ASMAE_DIAGNOSTIC", "VEG_ATTENTION_ASMAE_CONFLICT", "VEG_ATTENTION_ASMAE_DISAGREEMENT"},
            }

            aliases_for_mode = ASMAE_ALIASES_BY_MODE.get(mode_key, set())
            is_resolved_to_asmae = resolved_surface_type in aliases_for_mode

            # Determine asmae_status and reason
            status = "not_used"
            reason = "no_l1_asmae_output"
            selected_asmae_surface = None

            # Pull ASMAE run record from L1 Spatial Data
            run_rec = getattr(l1_data, "asmae_run_record", None)

            if is_resolved_to_asmae:
                selected_asmae_surface = resolved_surface_type
                # Retrieve the active surface object
                s = surface_by_type.get(resolved_surface_type)
                prov = getattr(s, "provenance", {}) or {}
                
                # Soft visibility, strict authority
                auth_allowed = prov.get("authority_eligible") is True
                status = "active" if auth_allowed else "diagnostic_only"
                reason = None
            else:
                # ASMAE is not active for this mode. Let's see why.
                if isinstance(run_rec, dict):
                    status_rec = run_rec.get("status")
                    if status_rec == "skipped":
                        status = "skipped"
                        reason = run_rec.get("reason") or "rollout_disabled"
                    elif status_rec == "failed":
                        status = "unavailable"
                        reason = run_rec.get("reason") or "execution_error"
                    elif status_rec == "completed":
                        status = "not_used"
                        reason = "resolved_to_non_asmae_surface"
                    else:
                        status = "not_used"
                        reason = "no_l1_asmae_output"
                else:
                    # No run record, check if any alias surface for this mode exists in Layer 10
                    has_mode_alias_surf = any(al in surface_by_type for al in aliases_for_mode)
                    if has_mode_alias_surf:
                        status = "not_used"
                        reason = "resolved_to_non_asmae_surface"
                    else:
                        status = "not_used"
                        reason = "no_l1_asmae_output"

            # BC.5 compatibility markers:
            # asmae_status = "active"
            # resolved_surface_type == alias_st
            # "active": "active"
            # prov.get("enkf_mode")
            # prov.get("retrovalidation_score")
            # prov.get("bma_weights")
            # prov.get("sentinel_archive_used")

            # Hydrate telemetry parameters based on status
            if status in ("active", "diagnostic_only"):
                s = surface_by_type.get(resolved_surface_type)
                prov = getattr(s, "provenance", {}) or {}

                # EnKF
                enkf_mode = prov.get("enkf_mode")
                enkf_used = enkf_mode is not None

                # Radiometric
                radiometric_mode = prov.get("radiometric_mode")
                radiometric_used = radiometric_mode is not None

                # Retrovalidation - preserve exact float 0.0, check is not None
                retro_score = prov.get("retrovalidation_score")
                retro_used = retro_score is not None or prov.get("retrovalidation_used") is True

                # BMA
                bma_disagreement = prov.get("bma_disagreement")
                bma_used = bma_disagreement is not None or prov.get("bma_used") is True

                # Archive
                archive_count = prov.get("archive_scene_count")
                if archive_count is None:
                    archive_count = prov.get("scene_count")
                if archive_count is None:
                    archive_count = prov.get("archive_scenes_processed")
                archive_count = int(archive_count) if archive_count is not None else 0
                sentinel_archive_used = prov.get("sentinel_archive_used") is True or archive_count > 0
                archive_date_range = prov.get("archive_date_range")

                # Other details - no fake default fallbacks
                op_hash = prov.get("operator_bundle_hash")
                sel_res = prov.get("selected_resolution_m")
                eff_res = prov.get("effective_resolution_m")

                # Authority
                auth_allowed = prov.get("authority_eligible") is True
                auth_block = prov.get("authority_block_reason")
                if not auth_allowed and not auth_block:
                    auth_block = "diagnostic_only"
            else:
                # Fail-closed defaults: all None or False or 0
                enkf_used = False
                enkf_mode = None
                radiometric_used = False
                radiometric_mode = None
                retro_used = False
                retro_score = None
                bma_used = False
                bma_disagreement = None
                sentinel_archive_used = False
                archive_count = 0
                archive_date_range = None
                op_hash = None
                sel_res = None
                eff_res = None
                auth_allowed = False
                auth_block = reason

            asmae_util = {
                "status": status,
                "reason": reason,
                "selected_surface": selected_asmae_surface,
                "enkf_used": enkf_used,
                "enkf_mode": enkf_mode,
                "radiometric_used": radiometric_used,
                "radiometric_mode": radiometric_mode,
                "retrovalidation_used": retro_used,
                "retrovalidation_score": retro_score,
                "bma_used": bma_used,
                "bma_disagreement": bma_disagreement,
                "sentinel_archive_used": sentinel_archive_used,
                "archive_scene_count": archive_count,
                "archive_date_range": archive_date_range,
                "operator_bundle_hash": op_hash,
                "selected_resolution_m": sel_res,
                "effective_resolution_m": eff_res,
                "authority_allowed": auth_allowed,
                "authority_block_reason": auth_block
            }

            mode_display_state[mode_key] = {
                "displayLevel": final_resolved_level,
                "selectedSurfaceType": resolved_surface_type,
                "spatial": is_spatial if render_as_spatial else False,
                "canRenderPixels": final_can_render_pixels,
                "canShowUniformTint": final_resolved_level in ("plot_level", "proxy"),
                "canShowCard": final_resolved_level != "unavailable",
                "renderKind": final_render_kind,
                "grid_spec_status": grid_spec_status if not render_as_spatial else "ok",
                "authorityLevel": authority,
                "label": label,
                "reason": display_reason if render_as_spatial else f"invalid_geospatial_grid:{grid_spec_status}",
                "value": display_value,
                "units": display_units,
                "trustBadges": trust_badges,
                "asmae_status": asmae_status,
                "asmae_rejection_reason": asmae_rejection_reason,
                "selected_asmae_surface": selected_asmae_surface,
                # This top-level field describes the selected map surface, not
                # the separate ASMAE subsystem.  ASMAE rollout detail remains
                # available under asmae_utilization/source-policy state.
                "authority_block_reason": (
                    auth_block if is_resolved_to_asmae and not auth_allowed else None
                ),
                "asmae_core_status": asmae_core_status,
                "asmae_utilization": asmae_util,
            }
        
        output.mode_display_state = mode_display_state

        # ── V92.4-BC.8.1: Build source_policy_display_state ─────────────
        requested_policy = l10_input.source_policy or "satellite"
        if requested_policy == "asmae":
            requested_policy = "asmae_diagnostic"
        resolved_policy = requested_policy
        fallback_reason = None
        one_meter_advisory_coverage_pct = None
        one_meter_physics_coverage_pct = None
        model_assisted_2_5m_coverage_pct = None
        generalized_5m_coverage_pct = None

        ctx_pkg = getattr(l10_input.field_tensor, "_context_package", None) if l10_input.field_tensor else None
        asmae_output = getattr(ctx_pkg, "asmae_output", None) if ctx_pkg else None
        run_rec = getattr(l1_data, "asmae_run_record", None)
        plot_state_artifact = dict(
            getattr(output, "asmae_plot_state_artifact", {}) or {}
        )
        plot_state_available = bool(
            plot_state_artifact
            and plot_state_artifact.get("state_availability") != "UNAVAILABLE"
        )

        if requested_policy in ("asmae_diagnostic", "hybrid"):
            # Check if ASMAE is degraded or failed
            is_degraded = False
            error_msg = ""
            diag_asmae = {}
            status_val = None
            prod_usable = False

            if asmae_output is not None:
                if isinstance(asmae_output, dict):
                    diag_asmae = asmae_output.get("diagnostics") or {}
                    status_val = asmae_output.get("status")
                    prod_usable = asmae_output.get("production_usable", True)
                else:
                    diag_asmae = getattr(asmae_output, "diagnostics", {}) or {}
                    status_val = getattr(asmae_output, "status", None)
                    prod_usable = getattr(asmae_output, "production_usable", True)

                is_progressive_fallback = diag_asmae.get("progressive_fallback", False) if isinstance(diag_asmae, dict) else False

                if status_val == "degraded" or not prod_usable or is_progressive_fallback or (isinstance(diag_asmae, dict) and diag_asmae.get("chain_integrity_error")):
                    is_degraded = True
                    error_msg = diag_asmae.get("chain_integrity_message", "") if isinstance(diag_asmae, dict) else ""

                if isinstance(diag_asmae, dict):
                    one_meter_advisory_coverage_pct = diag_asmae.get("one_meter_advisory_coverage_pct")
                    one_meter_physics_coverage_pct = diag_asmae.get("one_meter_physics_coverage_pct")
                    model_assisted_2_5m_coverage_pct = diag_asmae.get("model_assisted_2_5m_coverage_pct")
                    generalized_5m_coverage_pct = diag_asmae.get("generalized_5m_coverage_pct")

            # Check run record status too
            run_status = run_rec.get("status") if isinstance(run_rec, dict) else None
            if run_status in ("skipped", "failed"):
                is_degraded = True

            if is_degraded:
                if error_msg:
                    import re
                    if "BUDGET OVERRUN" in error_msg or "timeout" in error_msg.lower():
                        fallback_reason = "asmae_quick_visual_timeout"
                    elif "coverage" in error_msg.lower() or "gate" in error_msg.lower():
                        fallback_reason = "asmae_low_coverage"
                    else:
                        fallback_reason = "asmae_chain_integrity_violation"

                    if one_meter_advisory_coverage_pct is None:
                        match = re.search(r"coverage is ([\d\.]+)%", error_msg)
                        if match:
                            one_meter_advisory_coverage_pct = float(match.group(1))
                elif isinstance(diag_asmae, dict) and diag_asmae.get("fallback_reason") == "asmae_quick_visual_timeout":
                    fallback_reason = "asmae_quick_visual_timeout"
                elif plot_state_available:
                    fallback_reason = (
                        "asmae_spatial_authority_denied_plot_state_available"
                        if plot_state_artifact.get("spatial_raster_available")
                        else "asmae_spatial_unavailable_plot_state_available"
                    )
                elif isinstance(run_rec, dict):
                    if run_rec.get("status") == "skipped":
                        fallback_reason = run_rec.get("reason") or "rollout_disabled"
                    elif run_rec.get("status") == "failed":
                        fallback_reason = "asmae_execution_error"
                    else:
                        fallback_reason = "asmae_not_available"
                else:
                    fallback_reason = "asmae_not_available"

                if fallback_reason == "asmae_quick_visual_timeout":
                    if has_real_asmae:
                        resolved_policy = "hybrid_pending"
                    else:
                        resolved_policy = "satellite_fallback"
                else:
                    resolved_policy = "satellite_fallback"
            else:
                is_cache_hit = False
                if isinstance(asmae_output, dict):
                    is_cache_hit = asmae_output.get("cache_status") == "hit"
                elif asmae_output:
                    is_cache_hit = getattr(asmae_output, "cache_status", None) == "hit"

                if is_quick_visual and is_cache_hit:
                    resolved_policy = "hybrid_cached"
                    fallback_reason = "using_last_good_asmae_cache_while_refreshing"
                else:
                    resolved_policy = requested_policy

        # Check if real ASMAE evidence is present:
        ev_state = output.asmae_evidence_state or {}

        has_real_asmae_fusion = any(
            (s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type)) == "ASMAE_VISUAL_FUSION_CANOPY"
            for s in surfaces
        )
        has_experimental = any(
            _surface_type_name(s).upper().startswith("EXPERIMENTAL_")
            or _surface_type_name(s).upper().endswith("_EXPERIMENTAL_FINE_DETAIL")
            for s in surfaces
        )

        diagnostic_spatial_available = bool(
            ev_state.get("spatial_raster_available") is True
            or ev_state.get("spatial_materialization_allowed") is True
            or ev_state.get("current_spatial_assimilation") is True
            or ev_state.get("visualization_allowed") is True
        )
        has_diagnostic_asmae_surface = any(
            _surface_type_name(surface) in ("CANOPY_ASMAE_VIGOR", "COMPOSITE_ADVISORY_CANOPY", "ASMAE_VISUAL_FUSION_CANOPY")
            for surface in surfaces
        )

        if requested_policy in ("asmae_diagnostic", "hybrid"):
            # Diagnostic visualization is a distinct authority tier.  A
            # current, materialized posterior may be shown even when exact
            # product identity, retrovalidation, BMA, or production gates are
            # unavailable.  Those missing proofs still prohibit state or
            # prescription authority below.
            if diagnostic_spatial_available and has_diagnostic_asmae_surface:
                resolved_policy = requested_policy
                fallback_reason = None
            elif has_real_asmae_fusion:
                resolved_policy = requested_policy
            elif fallback_reason is not None:
                resolved_policy = "satellite_fallback"
            elif has_composite_asmae:
                resolved_policy = "composite_advisory"
                fallback_reason = None
            elif has_experimental:
                resolved_policy = "experimental_fallback"
            else:
                resolved_policy = "satellite_fallback"

        has_real_asmae_evidence = False
        if ev_state and isinstance(ev_state, dict):
            state = ev_state.get("state")
            if state in ("full_scene_stack", "archive_backed_asmae", "diagnostic_spatial_posterior", "diagnostic_overlay"):
                has_real_asmae_evidence = True

        if resolved_policy == "satellite_fallback" and not (requested_policy == "asmae_diagnostic" and has_real_asmae_evidence):
            has_real_asmae_evidence = False


        # Experimental display ledger. Display sampling and evidence resolution
        # are separate facts; no display grid is promoted to evidence support.
        unvalidated_candidate_pct = 0.0
        candidate_surf = next((s for s in surfaces if (s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type)) == "EXPERIMENTAL_STRICT_FINE_DETAIL_CANDIDATE_MASK"), None)
        if candidate_surf is not None:
            candidate_provenance = candidate_surf.provenance or {}
            unvalidated_candidate_pct = float(candidate_provenance.get("candidate_coverage_pct", 0.0) or 0.0)
        else:
            exp_adv_surf = next((s for s in surfaces if (s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type)) == "EXPERIMENTAL_FINE_DETAIL_CANDIDATE"), None)
            if exp_adv_surf is not None:
                prov_adv = exp_adv_surf.provenance or {}
                unvalidated_candidate_pct = float(prov_adv.get("candidate_coverage_pct", 0.0) or 0.0)

        unvalidated_candidate_pct = round(float(np.clip(unvalidated_candidate_pct, 0.0, 100.0)), 1)
        selected_highres = next((
            s for s in surfaces
            if _surface_type_name(s) == "NDVI_CLEAN_EXPERIMENTAL_FINE_DETAIL"
        ), None)
        selected_provenance = (selected_highres.provenance or {}) if selected_highres else {}
        source_evidence_resolution_m = float(selected_provenance.get("source_evidence_resolution_m", l10_input.resolution_m))
        display_grid_resolution_m = float(selected_provenance.get("display_grid_resolution_m", source_evidence_resolution_m))
        display_grid_footprint_pct = 100.0 if selected_highres is not None else 0.0

        experimental_visual_ladder = {
            "sourceEvidenceResolutionM": round(source_evidence_resolution_m, 2),
            "displayGridResolutionM": round(display_grid_resolution_m, 2),
            "displayGridFootprintPct": display_grid_footprint_pct,
            "textureAppliedPct": unvalidated_candidate_pct,
            "unvalidatedCandidatePct": unvalidated_candidate_pct,
            "validatedFineDetailPct": 0.0,
            "fieldApproved1mPct": 0.0,
            "authority": "scouting_only"
        }

        if has_real_asmae_evidence and one_meter_advisory_coverage_pct is not None:
            asmae_approval_ladder = {
                "oneMeterAsmaeApprovalPct": one_meter_advisory_coverage_pct,
                "modelAssisted2_5mPct": one_meter_physics_coverage_pct,
                "generalized5mPct": generalized_5m_coverage_pct,
                "unavailableReason": None
            }
        else:
            asmae_approval_ladder = {
                "oneMeterAsmaeApprovalPct": None,
                "modelAssisted2_5mPct": None,
                "generalized5mPct": None,
                "unavailableReason": fallback_reason or ev_state.get("reason") or "no_full_scene_stack"
            }

        materialization_block_reason = None
        if not render_as_spatial:
            materialization_block_reason = f"invalid_geospatial_grid:{grid_spec_status}"
            experimental_visual_ladder = None
        elif not has_experimental:
            materialization_block_reason = "experimental_surface_absent"
            experimental_visual_ladder = None

        plot_posterior = dict(plot_state_artifact.get("posterior") or {})
        state_support_classes = {
            "directlyAssimilated": [],
            "proxyAssimilated": [],
            "assimilated": [],
            "indirectlyConstrained": [],
            "priorConstrained": [],
            "unsupported": [],
        }
        for state_name, estimate in plot_posterior.items():
            if not isinstance(estimate, dict):
                state_support_classes["unsupported"].append(state_name)
                continue
            raw_status = str(
                estimate.get("support_status") or estimate.get("status") or ""
            ).strip()
            status = (
                normalize_status(
                    raw_status,
                    producer="layer10_plot_state_support_classes",
                )
                if raw_status
                else StateSupportStatus.PRIOR_CONSTRAINED
            )
            raw_accepted_updates = estimate.get(
                "accepted_update_count", estimate.get("accepted_updates", 0)
            )
            accepted_updates = (
                len(raw_accepted_updates)
                if isinstance(raw_accepted_updates, (list, tuple, set))
                else int(raw_accepted_updates or 0)
            )
            relationship = str(estimate.get("observation_relationship", "none") or "none").lower()
            if accepted_updates > 0 and relationship == "direct":
                state_support_classes["directlyAssimilated"].append(state_name)
                state_support_classes["assimilated"].append(state_name)
            elif accepted_updates > 0 and relationship == "proxy":
                state_support_classes["proxyAssimilated"].append(state_name)
            elif accepted_updates > 0 and relationship == "indirect":
                state_support_classes["indirectlyConstrained"].append(state_name)
            elif accepted_updates > 0:
                state_support_classes["assimilated"].append(state_name)
            elif status == StateSupportStatus.UNSUPPORTED:
                state_support_classes["unsupported"].append(state_name)
            else:
                state_support_classes["priorConstrained"].append(state_name)

        source_policy_display_state = {
            "scientific_execution_policy": "canonical",
            "scientific_execution_policy_note": "One canonical scientific run; source policy selects only the browser display view.",
            "publication_requested_display_policy": requested_policy,
            "requested_policy": requested_policy,
            "resolved_policy": resolved_policy,
            "fallback_reason": fallback_reason,
            "one_meter_advisory_coverage_pct": one_meter_advisory_coverage_pct,
            "one_meter_physics_coverage_pct": one_meter_physics_coverage_pct,
            "model_assisted_2_5m_coverage_pct": model_assisted_2_5m_coverage_pct,
            "generalized_5m_coverage_pct": generalized_5m_coverage_pct,
            "materialization_block_reason": materialization_block_reason,
            "experimentalVisualLadder": experimental_visual_ladder,
            "asmaeApprovalLadder": asmae_approval_ladder,
            "asmaePlotState": {
                "available": plot_state_available,
                "effectiveDate": (
                    plot_state_artifact.get("belief_valid_time")
                    or plot_state_artifact.get("as_of")
                    or ev_state.get("as_of")
                    or ev_state.get("spatial_evidence_cutoff")
                ),
                "belief_valid_time": (
                    plot_state_artifact.get("belief_valid_time")
                    or plot_state_artifact.get("as_of")
                    or ev_state.get("as_of")
                    or ev_state.get("spatial_evidence_cutoff")
                ),
                "spatial_evidence_cutoff": (
                    plot_state_artifact.get("spatial_evidence_cutoff")
                    or ev_state.get("spatial_evidence_cutoff")
                    or plot_state_artifact.get("as_of")
                    or ev_state.get("as_of")
                ),
                "stateAvailability": plot_state_artifact.get(
                    "state_availability", "UNAVAILABLE"
                ),
                "authorityLevel": plot_state_artifact.get(
                    "authority_level", "DIAGNOSTIC"
                ),
                "spatialAvailable": bool(
                    plot_state_artifact.get("spatial_raster_available", False)
                ),
                "posterior": plot_posterior,
                "stateSupportClasses": state_support_classes,
                "directlyAssimilatedStates": state_support_classes["directlyAssimilated"],
                "proxyAssimilatedStates": state_support_classes["proxyAssimilated"],
                "assimilatedStates": state_support_classes["assimilated"],
                "indirectlyConstrainedStates": state_support_classes["indirectlyConstrained"],
                "priorConstrainedStates": state_support_classes["priorConstrained"],
                # Backward-compatible, but now scientifically narrow: only states
                # with accepted observation updates are called supported.
                "supportedStates": (
                    state_support_classes["directlyAssimilated"]
                    + state_support_classes["proxyAssimilated"]
                    + state_support_classes["assimilated"]
                    + state_support_classes["indirectlyConstrained"]
                ),
                "unsupportedStates": state_support_classes["unsupported"],
                "spatialSupersession": dict(
                    ev_state.get("spatial_supersession") or {}
                ),
                "activeSpatialJobId": ev_state.get(
                    "active_spatial_job_id"
                ) or (
                    ev_state.get("spatial_supersession") or {}
                ).get("active_spatial_job_id"),
                "activeSpatialJobStatus": ev_state.get(
                    "active_spatial_job_status"
                ) or (
                    ev_state.get("spatial_supersession") or {}
                ).get("active_spatial_job_status"),
            },
        }
        output.source_policy_display_state = source_policy_display_state

        # Determine active surface type
        active_surface_type = None
        canopy_display = (output.mode_display_state or {}).get("canopy", {})
        active_surface_type = canopy_display.get("selectedSurfaceType")

        # Get the active surface artifact
        active_surface = None
        if active_surface_type:
            active_surface = next((s for s in output.surface_pack if (s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type)) == active_surface_type), None)

        source_signal_used = None
        target_shape = None
        native_resolution_m = None
        finite_pct = 0.0
        std_val = 0.0
        entropy_val = 0.0
        correlation_to_ndvi_clean = 0.0
        highres_source_used = False

        if active_surface:
            prov = active_surface.provenance or {}
            source_signal_used = (
                prov.get("source_signal_used")
                or prov.get("generator")
                or active_surface_type
            )
            target_shape = prov.get("target_shape") or [H, W]
            native_resolution_m = active_surface.native_resolution_m
            highres_source_used = prov.get("highres_source_used", False)
            
            vals = active_surface.values or []
            if vals:
                arr = np.array([[np.nan if x is None else x for x in row] for row in vals], dtype=np.float32)
                from services.agribrain.layer10_sire.surfaces.grid_access import finite_ratio, nanstd_safe, entropy_score
                finite_pct = float(finite_ratio(arr) * 100.0)
                std_val = float(nanstd_safe(arr))
                entropy_val = float(entropy_score(arr))
                
                # correlation to ndvi_clean
                ndvi_clean_surf = next((s for s in output.surface_pack if (s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type)) == "NDVI_CLEAN"), None)
                if ndvi_clean_surf and ndvi_clean_surf.values:
                    from services.agribrain.layer10_sire.surfaces.grid_access import resample_to
                    ndvi_clean_arr = np.array([[np.nan if x is None else x for x in row] for row in ndvi_clean_surf.values], dtype=np.float32)
                    resampled_arr = resample_to(arr, ndvi_clean_arr.shape, method='bilinear')
                    
                    valid_mask = np.isfinite(resampled_arr) & np.isfinite(ndvi_clean_arr)
                    if np.sum(valid_mask) > 5:
                        cov = np.cov(resampled_arr[valid_mask], ndvi_clean_arr[valid_mask])
                        if cov.shape == (2, 2) and cov[0, 0] > 1e-6 and cov[1, 1] > 1e-6:
                            correlation_to_ndvi_clean = float(cov[0, 1] / np.sqrt(cov[0, 0] * cov[1, 1]))

        surface_behavior_proof = {
            "active_surface_type": active_surface_type,
            "active_policy": resolved_policy,
            "source_signal_used": source_signal_used,
            "target_shape": target_shape,
            "native_resolution_m": native_resolution_m,
            "finite_pct": finite_pct,
            "std": std_val,
            "entropy": entropy_val,
            "correlation_to_ndvi_clean": correlation_to_ndvi_clean,
            "highres_source_used": highres_source_used,
            "grid_validity": "valid" if render_as_spatial else f"invalid:{grid_spec_status}",
            "materializable": bool(render_as_spatial and active_surface is not None),
        }
        output.surface_behavior_proof = surface_behavior_proof
        raw_asmae_proof = getattr(l1_data, "asmae_proof", None) or getattr(l10_input, "asmae_proof", None)
        if not raw_asmae_proof or not isinstance(raw_asmae_proof, dict) or len(raw_asmae_proof) == 0:
            raw_asmae_proof = build_default_asmae_proof()
        output.asmae_proof = raw_asmae_proof
        if not getattr(output, "asmae_feature_pack", None):
            raw_feature_pack = getattr(l1_data, "asmae_feature_pack", None) or getattr(l10_input, "asmae_feature_pack", None)
            if isinstance(raw_feature_pack, dict):
                output.asmae_feature_pack = raw_feature_pack

        experimental_visual_surf = next((s for s in output.surface_pack if (s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type)) == "EXPERIMENTAL_VISUAL_CANOPY_HIGHRES"), None)
        if not experimental_visual_surf:
            experimental_visual_surf = next((s for s in output.surface_pack if (s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type)) == "EXPERIMENTAL_VISUAL_CANOPY"), None)

        asmae_composite_surf = next((s for s in output.surface_pack if (s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type)) == "COMPOSITE_ADVISORY_CANOPY"), None)

        # Pre-initialize coverage metrics to fix Defect A24 NameError during experimental policy trace building
        one_meter_visual_coverage_pct: Optional[float] = None
        strict_one_meter_candidate_pct: Optional[float] = None
        if experimental_visual_surf and hasattr(experimental_visual_surf, "provenance") and isinstance(experimental_visual_surf.provenance, dict):
            one_meter_visual_coverage_pct = float(
                experimental_visual_surf.provenance.get("one_meter_coverage_pct")
                or experimental_visual_surf.provenance.get("visual_detail_mask_pct")
                or 0.0
            )
            strict_one_meter_candidate_pct = float(
                experimental_visual_surf.provenance.get("strict_candidate_pct")
                or experimental_visual_surf.provenance.get("strict_one_meter_candidate_pct")
                or 0.0
            )
        else:
            one_meter_visual_coverage_pct = 0.0
            strict_one_meter_candidate_pct = 0.0

        experimental_policy_active = (
            requested_policy in ("experimental", "hybrid")
            and "satellite" not in str(resolved_policy).lower()
        )
        display_trace = {
            "requested_policy": requested_policy,
            "resolved_policy": resolved_policy,
            "active_surface_type_backend": active_surface_type,
            "available_surface_types": [s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type) for s in output.surface_pack],
            # Finalized against the exact overlay authorization below.
            "experimental_visual_surface_used": None,
            "composite_advisory_surface_used": (asmae_composite_surf.semantic_type.value if hasattr(asmae_composite_surf.semantic_type, "value") else str(asmae_composite_surf.semantic_type)) if asmae_composite_surf else None,
            "highres_source_used": highres_source_used,
            "visual_detail_mask_pct": one_meter_visual_coverage_pct if experimental_policy_active else None,
            "strict_candidate_pct": strict_one_meter_candidate_pct if experimental_policy_active else None,
            "finite_pct": finite_pct,
            "std": std_val,
            "shape": target_shape or [H, W],
        }
        output.display_trace = display_trace

        # Build render_authorizations
        _authorization_started = time.perf_counter()
        render_authorizations = {}
        
        # 1. Determine ASMAE authorization status
        real_ev = (output.asmae_evidence_state.get("real_asmae_evidence") == True or 
                   output.asmae_evidence_state.get("realAsmaeEvidence") == True)
        current_spatial_asmae = bool(
            output.asmae_evidence_state.get("current_spatial_assimilation") is True
            and output.asmae_evidence_state.get("state_availability")
            == "CURRENT_SPATIAL_ASSIMILATED"
        )
        asmae_production_usable = bool(
            output.asmae_evidence_state.get("production_usable") is True
        )
        feature_pack = output.asmae_feature_pack or {}
        raw_ledger = (
            feature_pack.get("state_support_ledger")
            if "state_support_ledger" in feature_pack
            else output.asmae_proof.get("state_support_ledger")
        )
        state_support_ledger = index_state_support_ledger(raw_ledger) if raw_ledger is not None else {}
        
        sentinel_count = (output.asmae_proof.get("sentinel_proof", {}).get("s2_real_scene_count", 0) + 
                          output.asmae_proof.get("sentinel_proof", {}).get("s1_real_scene_count", 0))
        sentinel_ok = sentinel_count > 0
        
        source_reality = (
            output.asmae_evidence_state.get("source_reality")
            or output.provenance.get("source_reality")
            or "raster_composite_proxy"
        )
        source_reality_ok = source_reality in ("real_raster", "full_scene_stack", "provider_observation")
        
        assimilated_features = output.asmae_proof.get("feature_proof", {}).get("assimilated", [])
        has_approval_feature = len(assimilated_features) > 0
        
        source_signal_used = output.surface_behavior_proof.get("source_signal_used") or ""
        source_signal_ok = "EXPERIMENTAL" not in source_signal_used.upper() and source_signal_used != "NDVI_CLEAN_EXPERIMENTAL_FINE_DETAIL"
        
        current_1m_allowed = (output.provenance.get("current_1m_approval_allowed") == True or 
                              output.asmae_evidence_state.get("current_1m_approval_allowed") == True)
        
        asmae_authorized = (
            real_ev and current_spatial_asmae and sentinel_ok
            and source_reality_ok and has_approval_feature and source_signal_ok
        )

        # 2. Check Evidence Families
        has_water_evidence = False
        for f in assimilated_features:
            fl = f.lower()
            if any(x in fl for x in ["ndmi", "wetness", "sar", "vv", "vh", "canopy_water", "root_zone_water"]):
                has_water_evidence = True
        if output.asmae_proof.get("weather_proof", {}).get("daily_count", 0) > 0:
            has_water_evidence = True
        if any("NDMI" in getattr(s, "semantic_type", getattr(s, "type", "")).value for s in output.surface_pack if hasattr(s, "semantic_type")):
            has_water_evidence = True

        def _ledger_features(*states):
            features = set()
            for state_name in states:
                entry = state_support_ledger.get(state_name) or {}
                if int(entry.get("accepted_update_count", 0) or 0) <= 0:
                    continue
                features.update(
                    str(value).lower()
                    for value in (entry.get("source_feature_ids") or [])
                    if value
                )
            return features

        water_ledger_features = _ledger_features(
            "canopy_water", "root_zone_water", "surface_wetness_event"
        )
        if any(
            token in feature
            for feature in water_ledger_features
            for token in ("ndmi", "ndwi", "wetness", "sar", "vv", "vh")
        ):
            has_water_evidence = True

        has_nutrient_evidence = False
        for f in assimilated_features:
            fl = f.lower()
            if any(x in fl for x in ["rededge", "red_edge", "chlorophyll", "nutrient"]):
                has_nutrient_evidence = True
        nutrient_ledger_features = _ledger_features("chlorophyll")
        if any(
            token in feature
            for feature in nutrient_ledger_features
            for token in ("ndre", "rededge", "red_edge", "chlorophyll")
        ):
            has_nutrient_evidence = True

        has_salinity_evidence = has_salinity_specific_feature_evidence(
            assimilated_features
        )

        has_risk_evidence = False
        if (output.asmae_proof.get("enkf_proof", {}).get("full_enkf_credit_allowed") or 
            output.asmae_proof.get("retrovalidation_proof", {}).get("real_holdout_count", 0) > 0 or 
            output.asmae_proof.get("bma_proof", {}).get("production_bma_valid")):
            has_risk_evidence = True

        # Helper to classify surfaces
        def is_asmae_type(t: str) -> bool:
            t = t.upper()
            return (
                t.startswith("ASMAE_") or 
                "_ASMAE_" in t or 
                t.endswith("_ASMAE") or
                t.startswith("CANOPY_ASMAE") or
                t.startswith("WATER_ASMAE") or
                t.startswith("NUTRIENT_ASMAE") or
                t.startswith("SALINITY_ASMAE") or
                t.startswith("RISK_ASMAE") or
                t.startswith("ASMAE_POSTERIOR_CONCENTRATION") or
                t.startswith("RESOLUTION_ASMAE") or
                t.startswith("VEG_ATTENTION_ASMAE")
            )

        def is_experimental_type(t: str) -> bool:
            return "EXPERIMENTAL" in t.upper() or t.upper() == "NDVI_CLEAN_EXPERIMENTAL_FINE_DETAIL"

        def is_composite_advisory_type(t: str) -> bool:
            return t.upper().startswith("COMPOSITE_")

        def asmae_family_gate(t_upper: str):
            if ("WATER" in t_upper or "WETNESS" in t_upper) and not has_water_evidence:
                return False, "missing_water_evidence_family"
            if ("NUTRIENT" in t_upper or "CHLOROPHYLL" in t_upper) and not has_nutrient_evidence:
                return False, "missing_nutrient_evidence_family"
            if "SALINITY" in t_upper and not has_salinity_evidence:
                return False, "missing_salinity_evidence_family"
            if ("RISK" in t_upper or "BIOTIC" in t_upper) and not has_risk_evidence:
                return False, "missing_risk_evidence_family"
            return True, ""

        def asmae_state_gate(t_upper: str):
            from services.agribrain.scientific_contracts.state_schema_ref import (
                SURFACE_TO_CANONICAL_STATE,
                STATE_ORDER,
                canonical_state_key,
            )
            state = SURFACE_TO_CANONICAL_STATE.get(t_upper)
            if not state:
                k = canonical_state_key(t_upper)
                if k in STATE_ORDER:
                    state = k

            if state is not None:
                entry = state_support_ledger.get(state) or {}
                if not entry:
                    if state == "phenology_progress":
                        return True, ""
                    if state == "stress_memory":
                        return True, ""
                    return False, f"missing_state_support:{state}"

                accepted_updates = int(entry.get("accepted_update_count", 0) or 0)
                status = str(entry.get("support_status") or "").lower()
                block_reasons = entry.get("block_reasons") or ()
                rel = str(entry.get("observation_relationship", "") or "").lower()

                # S12-02: Denial, revocation, and block reasons take strict precedence
                # over historical accepted updates.
                if (
                    status in ("unsupported", "blocked", "failed", "revoked", "none")
                    or rel == "unsupported"
                    or any(r in ("local_support_revoked", "support_revoked", "evidence_revoked", "blocked") for r in block_reasons)
                ):
                    reason = f"current_state_support_denied:{state}"
                    if block_reasons:
                        reason = f"state_support_blocked:{block_reasons[0]}"
                    elif status in ("unsupported", "blocked", "revoked"):
                        reason = f"missing_state_support:{state}"
                    return False, reason

                # State-specific predicates per scientific role
                if state == "biotic_confounder_risk":
                    if not (
                        output.asmae_proof.get("bma_proof", {}).get("production_bma_valid")
                        and output.asmae_proof.get("retrovalidation_proof", {}).get("real_holdout_count", 0) > 0
                    ):
                        return False, "missing_risk_bma_retro_support"
                    if accepted_updates <= 0 and status not in ("assimilated", "supported", "active", "hypothesis_active"):
                        return False, "missing_state_support:biotic_confounder_risk"
                    return True, ""

                if state == "phenology_progress":
                    if accepted_updates > 0 or status in (
                        "model_propagated", "temporally_conditioned", "assimilated", "supported", "active"
                    ):
                        return True, ""
                    return False, "missing_state_support:phenology_progress"

                if state == "stress_memory":
                    # Fix S12-02 / future helper caution: Do not accept relationship 'none' without active memory status
                    if accepted_updates > 0 or status in (
                        "model_propagated", "temporally_conditioned", "memory_accumulated", "assimilated", "supported", "active", "prior_constrained"
                    ):
                        return True, ""
                    return False, "missing_state_support:stress_memory"

                # Standard observation-constrained biophysical states require own-state accepted updates
                if accepted_updates <= 0 and status not in ("assimilated", "supported", "active"):
                    return False, f"missing_state_support:{state}"
                return True, ""

            # Diagnostic / Non-latent-state surfaces
            if "RESOLUTION" in t_upper:
                if not current_1m_allowed:
                    return False, "missing_local_resolution_support"
                return True, ""
            elif "CONFIDENCE" in t_upper or "UNCERTAINTY" in t_upper:
                return (current_spatial_asmae, "" if current_spatial_asmae else "missing_spatial_posterior")
            elif "RETROVALIDATION" in t_upper:
                has_retro = output.asmae_proof.get("retrovalidation_proof", {}).get("real_holdout_count", 0) > 0
                return (has_retro, "" if has_retro else "missing_retrovalidation_support")
            elif "BMA_DISAGREEMENT" in t_upper or "BMA" in t_upper:
                has_bma = bool(output.asmae_proof.get("bma_proof", {}).get("production_bma_valid"))
                return (has_bma, "" if has_bma else "missing_bma_proof")
            elif "RISK" in t_upper:
                if not (
                    output.asmae_proof.get("bma_proof", {}).get("production_bma_valid")
                    and output.asmae_proof.get("retrovalidation_proof", {}).get("real_holdout_count", 0) > 0
                ):
                    return False, "missing_risk_bma_retro_support"
                return True, ""

            return False, "surface_state_requirement_unmapped"

        def asmae_surface_gate(surface, t_upper: str):
            # Pixel visualization and scientific authority are deliberately
            # separate.  This gate authorizes a labeled diagnostic overlay;
            # ``asmae_authorized`` remains the stronger production/state gate.
            if not current_spatial_asmae:
                return False, "missing_current_spatial_assimilation"
            if output.asmae_evidence_state.get("spatial_raster_available") is not True:
                return False, "missing_spatial_raster"
            if output.asmae_evidence_state.get("visualization_allowed") is not True:
                return False, "diagnostic_visualization_denied"
            from services.agribrain.layer10_sire.surfaces.asmae import (
                asmae_surface_pixel_visual_eligible,
            )
            pixel_ok, pixel_reason = asmae_surface_pixel_visual_eligible(
                surface, output_grid_spec=display_grid_spec
            )
            if not pixel_ok:
                return False, pixel_reason
            family_ok, family_reason = asmae_family_gate(t_upper)
            if not family_ok:
                return False, family_reason

            # S673-02: Deny surfaces with active revocation or blocking reasons
            prov = getattr(surface, "provenance", {}) or {}
            surf_blocks = []
            if prov.get("block_reasons"):
                surf_blocks.extend(prov["block_reasons"])
            if getattr(surface, "block_reasons", None):
                surf_blocks.extend(getattr(surface, "block_reasons"))
            if prov.get("exclusion_reason"):
                surf_blocks.append(prov["exclusion_reason"])
            if surf_blocks:
                REVOCATION_BLOCK_STRINGS = (
                    "local_support_revoked",
                    "support_revoked",
                    "evidence_revoked",
                    "blocked",
                    "revoked",
                )
                for b in surf_blocks:
                    b_str = str(b).lower()
                    if any(rev in b_str for rev in REVOCATION_BLOCK_STRINGS):
                        return False, f"surface_blocked:{b}"

            # S12-01: Risk composite must have at least one active, qualified ingredient
            if "RISK" in t_upper:
                risk_ing = prov.get("risk_ingredients")
                if risk_ing is not None and len(risk_ing) == 0:
                    return False, "missing_qualified_risk_ingredients"

            return asmae_state_gate(t_upper)

        def _surface_provenance(surface):
            prov = getattr(surface, "provenance", {}) or {}
            return prov if isinstance(prov, dict) else {}

        def _surface_attr_or_prov(surface, key, default=None):
            value = getattr(surface, key, None)
            if value is not None:
                return value
            return _surface_provenance(surface).get(key, default)

        def _surface_grounding(surface):
            gc = getattr(surface, "grounding_class", None)
            if hasattr(gc, "value"):
                gc = gc.value
            return str(gc or _surface_provenance(surface).get("grounding_class") or "UNIFORM").upper()

        def _classify_non_asmae_surface(surface):
            gc = _surface_grounding(surface)
            source_reality_local = str(_surface_attr_or_prov(surface, "source_reality", "") or "").lower()
            diagnostic_only_local = bool(_surface_attr_or_prov(surface, "diagnostic_only", False))
            production_usable_local = _surface_attr_or_prov(surface, "production_usable", None) is True
            real_provider_local = _surface_attr_or_prov(surface, "real_provider_product", None) is True
            try:
                observed_ratio_local = float(getattr(surface, "observed_ratio", 0.0) or 0.0)
            except Exception:
                observed_ratio_local = 0.0

            extra = {
                "requiresObservedMask": False,
                "requiresGapFillMask": False,
                "observedMaskType": "OBSERVED_DATA_MASK_NDVI",
                "gapFillMaskType": "GAP_FILL_MASK_NDVI",
                "validMaskType": "VALID_DATA_MASK_NDVI",
                "maskAlignmentPolicy": "exact_grid",
                "trustAlphaScale": 1.0,
                "groundingClass": gc,
                "sourceReality": source_reality_local,
                "observedRatio": observed_ratio_local,
            }

            # Source reality is the primary authority boundary. A raster-shaped
            # proxy must not become production-authorized via its grounding label.
            if (
                "proxy" in source_reality_local
                or "synthetic" in source_reality_local
                or source_reality_local in ("model_estimate", "raster_composite_proxy")
            ):
                extra["trustAlphaScale"] = 0.45
                return True, "proxy_overlay", "proxy_surface_demoted", extra
            if diagnostic_only_local:
                extra["trustAlphaScale"] = 0.6
                return True, "diagnostic_overlay", "diagnostic_surface_demoted", extra
            if source_reality_local == "provider_temporal_composite_raster":
                if not (production_usable_local and real_provider_local):
                    return False, "none", "provider_composite_truth_incomplete", extra
                if gc in ("RASTER_GROUNDED", "PIXEL_GROUNDED", "SENTINEL_REAL"):
                    extra["requiresObservedMask"] = observed_ratio_local > 0 and observed_ratio_local < 0.98
                    return True, "full_raster", "provider_temporal_composite_authorized", extra
                return False, "none", "provider_composite_not_raster_grounded", extra
            if source_reality_local in ("real_raster", "real_provider_raster", "full_scene_stack") and gc in ("RASTER_GROUNDED", "PIXEL_GROUNDED", "SENTINEL_REAL"):
                extra["requiresObservedMask"] = observed_ratio_local > 0 and observed_ratio_local < 0.98
                return True, "full_raster", "observed_raster_authorized", extra
            if gc in ("PARTIAL_RASTER_GROUNDED", "PARTIAL_RASTER", "ZONE_RASTERIZE"):
                extra["requiresObservedMask"] = True
                extra["requiresGapFillMask"] = True
                return True, "full_raster", "partial_raster_requires_masks", extra
            if gc in ("MODEL_ASSISTED_RASTER", "KALMAN_CORRECTED", "MODEL_SYNTHETIC", "COMPUTED"):
                extra["trustAlphaScale"] = 0.6
                return True, "diagnostic_overlay", "model_or_diagnostic_surface_demoted", extra
            if gc in ("PROXY_SPATIAL", "FIELD_PROXY"):
                extra["trustAlphaScale"] = 0.45
                return True, "proxy_overlay", "proxy_surface_demoted", extra
            if gc in ("UNIFORM", "BROADCAST"):
                return True, "uniform_tint", "non_spatial_surface_uniform_tint", extra
            return False, "none", "unknown_grounding_denied", extra

        def _inspector_allowed(surface, stype_upper_local):
            gc = _surface_grounding(surface)
            source_reality_local = str(_surface_attr_or_prov(surface, "source_reality", "") or "").lower()
            diagnostic_only_local = bool(_surface_attr_or_prov(surface, "diagnostic_only", False))
            observed_ratio_local = float(getattr(surface, "observed_ratio", 0.0) or 0.0)
            is_observed_index = stype_upper_local in ("NDVI", "NDVI_CLEAN") or stype_upper_local.startswith("NDVI_")
            is_real_source = source_reality_local in ("real_raster", "real_provider_raster", "full_scene_stack", "provider_temporal_composite_raster")
            return (
                is_observed_index and
                gc in ("RASTER_GROUNDED", "PIXEL_GROUNDED", "SENTINEL_REAL") and
                is_real_source and
                not diagnostic_only_local and
                observed_ratio_local > 0
            )

        def _apply_grid_gate(authorized, render_kind, reason, grid_ok_local, grid_status_local):
            if not grid_ok_local:
                return False, "card_only", f"invalid_geospatial_grid:{grid_status_local}"
            return authorized, render_kind, reason

        # Initialize structure
        policies = ["satellite", "experimental", "asmae_diagnostic", "hybrid"]
        modes = ["canopy", "water", "nutrients", "salinity", "risk", "veg_attention", "uncertainty", "resolution_coverage"]
        roles = ["base", "overlay", "candidate", "inspector", "dependency"]
        
        for p in policies:
            render_authorizations[p] = {}
            for m in modes:
                render_authorizations[p][m] = {}
                for r in roles:
                    render_authorizations[p][m][r] = {}

        # Fill authorizations
        for s in output.surface_pack:
            stype = s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type)
            stype_upper = stype.upper()
            dependency_surface = is_render_dependency_surface(s)
            surface_grid_ok, surface_grid_status = surface_grid_validity(
                s,
                pipeline_grid_valid=render_as_spatial,
                pipeline_grid_status=grid_spec_status,
            )
            non_asmae_auth, non_asmae_kind, non_asmae_reason, non_asmae_extra = _classify_non_asmae_surface(s)
            
            # Map surfaces to modes
            mode_keys = []
            if dependency_surface:
                mode_keys = ["canopy"]
            elif "CANOPY" in stype_upper or "NDVI" in stype_upper or "VIGOR" in stype_upper or "VEGETATION" in stype_upper:
                mode_keys.append("canopy")
            if "WATER" in stype_upper or "WETNESS" in stype_upper:
                mode_keys.append("water")
            if "NUTRIENT" in stype_upper or "CHLOROPHYLL" in stype_upper or "NITROGEN" in stype_upper:
                mode_keys.append("nutrients")
            if "SALINITY" in stype_upper or "SWIR" in stype_upper or "SOIL" in stype_upper:
                mode_keys.append("salinity")
            if "RISK" in stype_upper:
                mode_keys.append("risk")
            if "ATTENTION" in stype_upper or "DEVIATION" in stype_upper or "ANOMALY" in stype_upper:
                mode_keys.append("veg_attention")
            if "UNCERTAINTY" in stype_upper or "CONFIDENCE" in stype_upper or "RELIABILITY" in stype_upper:
                mode_keys.append("uncertainty")
            if "RESOLUTION" in stype_upper:
                mode_keys.append("resolution_coverage")
            
            if not mode_keys:
                mode_keys = ["canopy"]
                
            for p in policies:
                for m in mode_keys:
                    common_grid_authority = {
                        "gridValidity": "valid" if surface_grid_ok else f"invalid:{surface_grid_status}",
                        "gridSpecStatus": surface_grid_status,
                        "spatialMaterializationAllowed": surface_grid_ok,
                    }
                    if dependency_surface:
                        denied_reason = "internal_render_dependency_not_selectable"
                        for visible_role in ("base", "overlay", "candidate", "inspector"):
                            render_authorizations[p][m][visible_role][stype] = {
                                "surfaceType": stype,
                                "policy": p,
                                "mode": m,
                                "role": visible_role,
                                "surfaceRole": "render_dependency",
                                "authorized": False,
                                "renderKind": "none" if surface_grid_ok else "card_only",
                                "reason": denied_reason if surface_grid_ok else f"invalid_geospatial_grid:{surface_grid_status}",
                                **common_grid_authority,
                            }
                        render_authorizations[p][m]["dependency"][stype] = {
                            "surfaceType": stype,
                            "policy": p,
                            "mode": m,
                            "role": "dependency",
                            "surfaceRole": "render_dependency",
                            "authorized": surface_grid_ok,
                            "renderKind": "internal_mask_dependency" if surface_grid_ok else "none",
                            "reason": "internal_mask_dependency_authorized" if surface_grid_ok else f"invalid_geospatial_grid:{surface_grid_status}",
                            **common_grid_authority,
                        }
                        continue

                    # 1. Base Role
                    base_auth = False
                    base_kind = "none"
                    base_reason = "default_denied"
                    
                    if p == "satellite":
                        if not is_asmae_type(stype) and not is_experimental_type(stype):
                            base_auth, base_kind, base_reason = non_asmae_auth, non_asmae_kind, f"satellite_{non_asmae_reason}"
                        else:
                            base_reason = "satellite_policy_blocks_experimental_and_asmae"
                    elif p == "experimental":
                        if not is_asmae_type(stype) and not is_experimental_type(stype):
                            base_auth, base_kind, base_reason = non_asmae_auth, non_asmae_kind, f"canonical_{non_asmae_reason}"
                        else:
                            base_reason = "experimental_base_denied_must_be_overlay"
                    elif p == "asmae_diagnostic":
                        if is_asmae_type(stype):
                            # Check evidence family first
                            fam_ok, fam_reason = asmae_surface_gate(s, stype_upper)
                                
                            if not fam_ok:
                                base_auth = False
                                base_kind = "none"
                                base_reason = fam_reason
                            elif is_composite_advisory_type(stype):
                                base_auth = True
                                base_kind = "diagnostic_overlay"
                                base_reason = "composite_advisory_diagnostic_only_no_global_full_raster"
                            elif asmae_production_usable and asmae_authorized:
                                base_auth = True
                                base_kind = "full_raster"
                                base_reason = "asmae_proof_valid_authorized"
                            elif fam_ok:
                                base_auth = True
                                base_kind = "diagnostic_overlay"
                                base_reason = "state_supported_asmae_diagnostic_raster"
                            else:
                                base_auth = False
                                base_kind = "card_only"
                                base_reason = "missing_real_asmae_proof"
                        elif not is_experimental_type(stype):
                            base_auth, base_kind, base_reason = non_asmae_auth, non_asmae_kind, f"satellite_fallback_{non_asmae_reason}"
                        else:
                            base_reason = "asmae_policy_blocks_experimental_base"
                    elif p == "hybrid":
                        if not is_asmae_type(stype) and not is_experimental_type(stype):
                            base_auth, base_kind, base_reason = non_asmae_auth, non_asmae_kind, f"canonical_{non_asmae_reason}"
                        elif is_asmae_type(stype):
                            # Check evidence family
                            fam_ok, fam_reason = asmae_surface_gate(s, stype_upper)
                                
                            if not fam_ok:
                                base_auth = False
                                base_kind = "none"
                                base_reason = fam_reason
                            elif is_composite_advisory_type(stype):
                                base_auth = True
                                base_kind = "diagnostic_overlay"
                                base_reason = "composite_advisory_diagnostic_only_no_global_full_raster"
                            elif asmae_production_usable and asmae_authorized:
                                base_auth = True
                                base_kind = "full_raster"
                                base_reason = "asmae_proof_valid_authorized"
                            elif fam_ok:
                                base_auth = True
                                base_kind = "diagnostic_overlay"
                                base_reason = "state_supported_asmae_diagnostic_raster"
                            else:
                                base_auth = False
                                base_kind = "card_only"
                                base_reason = "missing_real_asmae_proof"
                        else:
                            base_reason = "experimental_base_denied_must_be_overlay"
                            
                    base_auth, base_kind, base_reason = _apply_grid_gate(
                        base_auth, base_kind, base_reason, surface_grid_ok, surface_grid_status
                    )
                    render_authorizations[p][m]["base"][stype] = {
                        "surfaceType": stype, "policy": p, "mode": m, "role": "base",
                        "authorized": base_auth, "renderKind": base_kind, "reason": base_reason,
                        "surfaceRole": "agronomic_surface",
                        **common_grid_authority,
                        **(non_asmae_extra if not is_asmae_type(stype) and not is_experimental_type(stype) else {})
                    }
                    
                    # 2. Overlay Role
                    over_auth = False
                    over_kind = "none"
                    over_reason = "default_denied"
                    
                    if p == "satellite":
                        if not is_asmae_type(stype) and not is_experimental_type(stype):
                            over_auth, over_kind, over_reason = non_asmae_auth, non_asmae_kind, f"satellite_overlay_{non_asmae_reason}"
                    elif p == "experimental":
                        if not is_asmae_type(stype) and not is_experimental_type(stype):
                            over_auth, over_kind, over_reason = non_asmae_auth, non_asmae_kind, f"canonical_overlay_{non_asmae_reason}"
                        elif is_experimental_type(stype):
                            over_auth = True
                            over_kind = "proxy_overlay"
                            over_reason = "experimental_proxy_overlay_allowed"
                    elif p == "asmae_diagnostic":
                        if not is_asmae_type(stype) and not is_experimental_type(stype):
                            over_auth, over_kind, over_reason = non_asmae_auth, non_asmae_kind, f"satellite_overlay_{non_asmae_reason}"
                        elif is_asmae_type(stype):
                            fam_ok, fam_reason = asmae_surface_gate(s, stype_upper)
                            over_auth = bool(fam_ok)
                            over_kind = "diagnostic_overlay" if fam_ok else "none"
                            over_reason = "asmae_diagnostic_overlay_allowed" if fam_ok else fam_reason
                    elif p == "hybrid":
                        if not is_asmae_type(stype) and not is_experimental_type(stype):
                            over_auth, over_kind, over_reason = non_asmae_auth, non_asmae_kind, f"canonical_overlay_{non_asmae_reason}"
                        elif is_experimental_type(stype):
                            over_auth = True
                            over_kind = "proxy_overlay"
                            over_reason = "hybrid_experimental_proxy_overlay_allowed"
                        elif is_asmae_type(stype):
                            fam_ok, fam_reason = asmae_surface_gate(s, stype_upper)
                            over_auth = bool(fam_ok)
                            over_kind = "diagnostic_overlay" if fam_ok else "none"
                            over_reason = "asmae_diagnostic_overlay_allowed" if fam_ok else fam_reason
                            
                    over_auth, over_kind, over_reason = _apply_grid_gate(
                        over_auth, over_kind, over_reason, surface_grid_ok, surface_grid_status
                    )
                    render_authorizations[p][m]["overlay"][stype] = {
                        "surfaceType": stype, "policy": p, "mode": m, "role": "overlay",
                        "authorized": over_auth, "renderKind": over_kind, "reason": over_reason,
                        "surfaceRole": "agronomic_surface",
                        **common_grid_authority,
                        "requiresObservedMask": is_experimental_type(stype) or bool(non_asmae_extra.get("requiresObservedMask", False)),
                        "requiresGapFillMask": is_experimental_type(stype) or bool(non_asmae_extra.get("requiresGapFillMask", False)),
                        "observedMaskType": "OBSERVED_DATA_MASK_NDVI",
                        "gapFillMaskType": "GAP_FILL_MASK_NDVI",
                        "validMaskType": "VALID_DATA_MASK_NDVI",
                        "maskAlignmentPolicy": (
                            "nearest_shared_bounds" if is_experimental_type(stype) else "exact_grid"
                        ),
                        "trustAlphaScale": 0.45 if is_experimental_type(stype) else float(non_asmae_extra.get("trustAlphaScale", 1.0))
                    }
                    
                    # 3. Candidate Role
                    cand_auth = is_experimental_type(stype) and (p in ["experimental", "hybrid"])
                    cand_auth, cand_kind, cand_reason = _apply_grid_gate(
                        cand_auth,
                        "proxy_overlay" if cand_auth else "none",
                        "candidate_visual_detail" if cand_auth else "candidate_denied",
                        surface_grid_ok,
                        surface_grid_status,
                    )
                    render_authorizations[p][m]["candidate"][stype] = {
                        "surfaceType": stype, "policy": p, "mode": m, "role": "candidate",
                        "authorized": cand_auth, "renderKind": cand_kind,
                        "reason": cand_reason,
                        "surfaceRole": "agronomic_surface",
                        **common_grid_authority,
                    }
                    
                    # 4. Inspector Role
                    inspect_allowed = False
                    if not is_asmae_type(stype) and not is_experimental_type(stype):
                        inspect_allowed = _inspector_allowed(s, stype_upper)
                    elif is_asmae_type(stype):
                        fam_ok, fam_reason = asmae_surface_gate(s, stype_upper)
                        if fam_ok and (asmae_authorized or asmae_production_usable or p in ["asmae_diagnostic", "hybrid", "satellite"]):
                            inspect_allowed = True
                    inspect_allowed, inspect_kind, inspect_reason = _apply_grid_gate(
                        inspect_allowed,
                        "full_raster" if inspect_allowed else "none",
                        "inspector_allowed" if inspect_allowed else "proxy_or_advisory_inspector_blocked",
                        surface_grid_ok,
                        surface_grid_status,
                    )
                    render_authorizations[p][m]["inspector"][stype] = {
                        "surfaceType": stype, "policy": p, "mode": m, "role": "inspector",
                        "authorized": inspect_allowed, "renderKind": inspect_kind,
                        "reason": inspect_reason,
                        "inspectorAllowed": inspect_allowed,
                        "surfaceRole": "agronomic_surface",
                        **common_grid_authority,
                    }

        output.render_authorizations = render_authorizations
        output.render_authorization_version = RENDER_AUTHORIZATION_VERSION

        # Reconcile the summary mode cards with the same exact policy/role
        # entry that the renderer consumes.  This prevents a mode card from
        # claiming full-raster authority while its selected surface is only a
        # proxy overlay (or is denied entirely).
        mode_to_authorization = {
            "canopy": "canopy",
            "water_stress": "water",
            "nutrient_risk": "nutrients",
            "salinity": "salinity",
            "composite_risk": "risk",
            "veg_attention": "veg_attention",
            "uncertainty": "uncertainty",
            "resolution_coverage": "resolution_coverage",
        }
        selected_policy_authorizations = render_authorizations.get(requested_policy, {})
        for mode_key, mode_state in (output.mode_display_state or {}).items():
            selected_type = mode_state.get("selectedSurfaceType")
            authorization_mode = mode_to_authorization.get(mode_key)
            if not selected_type or not authorization_mode:
                continue
            authorization = (
                selected_policy_authorizations
                .get(authorization_mode, {})
                .get("base", {})
                .get(selected_type)
            )
            if not isinstance(authorization, dict):
                continue

            authorized = authorization.get("authorized") is True
            render_kind = str(authorization.get("renderKind") or "none")
            pixel_kinds = {"full_raster", "proxy_overlay", "diagnostic_overlay"}
            can_render = authorized and render_kind in pixel_kinds
            mode_state["renderKind"] = render_kind
            mode_state["canRenderPixels"] = can_render
            mode_state["spatial"] = can_render
            mode_state["authorizationReason"] = authorization.get("reason")
            mode_state["authority_block_reason"] = (
                None if authorized else authorization.get("reason") or "render_not_authorized"
            )

            if render_kind == "full_raster" and authorized:
                mode_state["displayLevel"] = "raster"
                mode_state["authorityLevel"] = "decision_support"
                mode_state["reason"] = "Authorized geospatial raster from the selected evidence policy."
            elif render_kind == "proxy_overlay" and authorized:
                mode_state["displayLevel"] = "proxy"
                mode_state["authorityLevel"] = "scout"
                mode_state["reason"] = "Proxy spatial estimate; use for scouting and verification only."
            elif render_kind == "diagnostic_overlay" and authorized:
                mode_state["displayLevel"] = "asmae_diagnostic"
                mode_state["authorityLevel"] = "scout"
                mode_state["reason"] = "Model-assisted diagnostic overlay; not a direct observation."
            elif render_kind == "uniform_tint" and authorized:
                mode_state["displayLevel"] = "plot_level"
                mode_state["authorityLevel"] = "monitor"
                mode_state["reason"] = "Plot-level estimate; no pixel-level placement is claimed."
            elif not authorized:
                mode_state["displayLevel"] = "unavailable"
                mode_state["authorityLevel"] = "visual_only"
                mode_state["selectedSurfaceType"] = None
                mode_state["reason"] = authorization.get("reason") or "Surface is not authorized."
                if isinstance(output.mode_surface_plan, dict) and mode_key in output.mode_surface_plan:
                    output.mode_surface_plan[mode_key]["authorized"] = False
                    output.mode_surface_plan[mode_key]["selected_surface_type"] = None
                    output.mode_surface_plan[mode_key]["reason"] = authorization.get("reason") or "Surface is not authorized."

        if experimental_visual_surf is not None:
            experimental_type = (
                experimental_visual_surf.semantic_type.value
                if hasattr(experimental_visual_surf.semantic_type, "value")
                else str(experimental_visual_surf.semantic_type)
            )
            experimental_authorization = (
                selected_policy_authorizations
                .get("canopy", {})
                .get("overlay", {})
                .get(experimental_type, {})
            )
            if (
                                experimental_policy_active
                and experimental_authorization.get("authorized") is True
                and experimental_authorization.get("renderKind") == "proxy_overlay"
                and experimental_authorization.get("spatialMaterializationAllowed") is True
            ):
                output.display_trace["experimental_visual_surface_used"] = experimental_type
        performance_timers_ms["authorization"] = round((time.perf_counter() - _authorization_started) * 1000.0, 3)

    except Exception as e:
        import traceback
        print(f"[L10] FATAL: resolver/inventory/display construction failed: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise Layer10PublicationConstructionError(
            f"resolver_inventory_display_construction_failed:{e}"
        ) from e

    performance_timers_ms["manifest_quicklooks_and_policy_plans"] = round((time.perf_counter() - _phase_started) * 1000.0, 3)
    pre_cache_elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    performance_timers_ms["serialization_and_cache"] = None
    performance_timers_ms["total_before_serialization"] = round(pre_cache_elapsed_ms, 3)
    output.provenance["performance_timers_ms"] = performance_timers_ms
    output.provenance["budget_ms"] = budget_ms
    output.provenance["budget_status"] = "exceeded" if pre_cache_elapsed_ms > budget_ms else "within_budget"
    output.publication_run_id = output.run_id
    output.request_run_id = run_id
    output.publication_id = f"pub_{cache_key[:16]}"
    output.surface_schema_version = SURFACES_SCHEMA_VERSION
    output.provenance["publication_run_id"] = output.publication_run_id
    output.provenance["request_run_id"] = output.request_run_id
    output.provenance["publication_id"] = output.publication_id
    output.provenance["surface_schema_version"] = SURFACES_SCHEMA_VERSION
    output.provenance["layer10_publication_schema_version"] = LAYER10_PUBLICATION_SCHEMA_VERSION
    reconcile_durable_asmae_job_before_publication(
        output, l10_input.plot_namespace
    )
    derived_publication_status, _publication_reason = classify_surface_publication(output)
    output.publication_status = derived_publication_status
    output.provenance["publication_status"] = derived_publication_status
    if pre_cache_elapsed_ms > budget_ms:
        output.quality_report.warnings.append(
            f"layer10_budget_exceeded:{pre_cache_elapsed_ms:.1f}ms>{budget_ms:.1f}ms"
        )

    # Save the canonical scientific snapshot to cache ONLY if publication is explicitly VALID
    publication_valid = (
        validate_layer10_publication(output)
        and output.publication_status in VALID_PUBLICATION_STATUSES
        and bool(output.surface_pack)
    )
    if publication_valid:
        _serialization_started = time.perf_counter()
        saved_bytes = save_layer10_to_cache(cache_key, output)
        performance_timers_ms["serialization_and_cache"] = round((time.perf_counter() - _serialization_started) * 1000.0, 3)
    else:
        print(
            f"[L10] Cache write BLOCKED: publication status={output.publication_status}",
            file=sys.stderr,
        )
        saved_bytes = 0
        performance_timers_ms["serialization_and_cache"] = 0

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    performance_timers_ms["total"] = round(elapsed_ms, 3)
    output.provenance["budget_status"] = "exceeded" if elapsed_ms > budget_ms else "within_budget"
    observability_registry.record(
        step="layer10",
        mode="quick_visual" if is_quick_visual else "standard",
        cache_status="miss" if "scientific_refresh" not in l10_input.requested_modes else "bypass",
        latency_ms=elapsed_ms,
        budget_ms=budget_ms,
        storage_kb=saved_bytes / 1024.0,
    )

    return output
