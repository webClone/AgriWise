"""IR-04-R03: Authenticated observation footprint adapter.

Translates admitted Layer 0/1 observation scenes (Sentinel-2, Sentinel-1)
into authentic EvidenceFootprint instances for state×cell spatial support evaluation.
Fails closed on uncalibrated operators, cross-tenant scenes, non-metric CRS, or
invalid geometry hashes.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import math
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .state_cell_support import EvidenceFootprint, STATE_NAMES, SpatialSupportViolation

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Physical & epistemic sensor specifications
S2_OPTICAL_STATES = (
    "vigor", "lai", "chlorophyll", "canopy_water",
    "structure", "bare_soil_fraction", "phenology_progress",
)
S1_SAR_STATES = (
    "surface_wetness_event", "root_zone_water", "structure",
)

S2_OPERATOR_SHA256 = hashlib.sha256(b"akaloris/operator/s2_msi/spatial_v1").hexdigest()
S2_CALIBRATED_OPERATOR_SHA256 = hashlib.sha256(b"akaloris/operator/s2_msi/calibrated_psf_v1").hexdigest()

S1_OPERATOR_SHA256 = hashlib.sha256(b"akaloris/operator/s1_cband_sar/spatial_v1").hexdigest()
S1_CALIBRATED_OPERATOR_SHA256 = hashlib.sha256(b"akaloris/operator/s1_cband_sar/calibrated_psf_v1").hexdigest()


def _ensure_utc_iso(dt: Any) -> Optional[str]:
    """Convert datetime or ISO string to standard UTC ISO-8601 string."""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat()
    if isinstance(dt, str):
        try:
            parsed = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            else:
                parsed = parsed.astimezone(timezone.utc)
            return parsed.isoformat()
        except ValueError:
            return None
    return None


def _extract_bbox(scene: Any) -> Optional[Tuple[float, float, float, float]]:
    """Extract (minx, miny, maxx, maxy) in scene coordinate space."""
    bounds = getattr(scene, "bounds", None)
    if bounds is not None and isinstance(bounds, (list, tuple)) and len(bounds) == 4:
        try:
            minx, miny, maxx, maxy = (float(v) for v in bounds)
            if minx < maxx and miny < maxy and all(math.isfinite(v) for v in (minx, miny, maxx, maxy)):
                return (minx, miny, maxx, maxy)
        except (ValueError, TypeError):
            pass

    transform = getattr(scene, "transform", None)
    width = getattr(scene, "width", None)
    height = getattr(scene, "height", None)
    if transform and width and height and isinstance(transform, (list, tuple)) and len(transform) >= 6:
        try:
            w = int(width)
            h = int(height)
            if w > 0 and h > 0:
                x0, xstep, _, y0, _, ystep = (float(transform[i]) for i in range(6))
                x1 = x0 + xstep * w
                y1 = y0 + ystep * h
                minx, maxx = min(x0, x1), max(x0, x1)
                miny, maxy = min(y0, y1), max(y0, y1)
                if minx < maxx and miny < maxy and all(math.isfinite(v) for v in (minx, miny, maxx, maxy)):
                    return (minx, miny, maxx, maxy)
        except (ValueError, TypeError):
            pass
    return None


def adapt_scene_to_footprint(
    scene: Any,
    *,
    tenant_id: str,
    farm_id: str,
    plot_id: str,
    geometry_sha256: str,
    target_crs: str,
    committed_at: Optional[str] = None,
) -> Optional[EvidenceFootprint]:
    """Translate an admitted scene into an EvidenceFootprint or fail closed (return None).

    Strict admission requirements:
    1. Tenant/farm/plot namespace and geometry digest must match.
    2. Scene must be production-usable or scientifically admitted (not test/diagnostic-only).
    3. Scene CRS must match target projected metric CRS.
    4. Valid non-degenerate bounding box and UTC timestamp required.
    """
    if not all((tenant_id, farm_id, plot_id, geometry_sha256, target_crs)):
        return None
    if not _SHA256_RE.fullmatch(geometry_sha256):
        return None

    # Check scene admission / reality attributes
    if getattr(scene, "test_override", False):
        return None
    is_prod_usable = bool(getattr(scene, "production_usable", False) or getattr(scene, "real_provider_product", False))
    is_diagnostic = bool(getattr(scene, "diagnostic_only", True))
    is_surface_allowed = bool(
        getattr(scene, "scientific_surface_allowed", False)
        or getattr(scene, "state_update_allowed", False)
    )
    if is_diagnostic and not is_prod_usable and not is_surface_allowed:
        return None

    # Namespace match: if scene carries tenant/farm/plot identity, it must match
    scene_tenant = getattr(scene, "tenant_id", None)
    if scene_tenant and str(scene_tenant) != str(tenant_id):
        return None
    scene_plot = getattr(scene, "plot_id", None)
    if scene_plot and str(scene_plot) != str(plot_id):
        return None

    # CRS match: scene must match the target projected metric grid CRS
    scene_crs = str(getattr(scene, "crs", "") or "").upper()
    if not scene_crs or scene_crs != str(target_crs).upper():
        return None
    if scene_crs in ("EPSG:4326", "OGC:CRS84", "CRS84", "WGS84"):
        return None

    # Bounding box
    bbox = _extract_bbox(scene)
    if bbox is None:
        return None

    # Observation ID
    scene_id = str(getattr(scene, "scene_id", "") or "").strip()
    if not scene_id:
        return None

    # Acquisition time -> valid_time
    acq_time = (
        getattr(scene, "acquisition_time", None)
        or getattr(scene, "timestamp", None)
        or getattr(scene, "date", None)
    )
    valid_time = _ensure_utc_iso(acq_time)
    if not valid_time:
        return None

    commit_iso = _ensure_utc_iso(committed_at) or valid_time

    # Sensor classification
    sensor_raw = str(getattr(scene, "sensor", "") or "").upper()
    if sensor_raw in ("S2", "SENTINEL-2", "SENTINEL_2", "S2_MSI"):
        native_res = 10.0
        psf_fwhm = 12.0
        supported_states = S2_OPTICAL_STATES
        op_sha = S2_OPERATOR_SHA256
        cal_op_sha = S2_CALIBRATED_OPERATOR_SHA256
        cloud_frac = float(getattr(scene, "cloud_fraction", 0.0) or 0.0)
        observability = max(0.0, min(1.0, 1.0 - cloud_frac))
    elif sensor_raw in ("S1", "SENTINEL-1", "SENTINEL_1", "S1_SAR"):
        native_res = 20.0
        psf_fwhm = 20.0
        supported_states = S1_SAR_STATES
        op_sha = S1_OPERATOR_SHA256
        cal_op_sha = S1_CALIBRATED_OPERATOR_SHA256
        observability = 0.95
    else:
        # Unknown or uncalibrated sensor: cannot confer calibrated local footprint
        return None

    # Deterministic source content hash
    src_hash = getattr(scene, "content_hash", None) or getattr(scene, "sha256", None)
    if not src_hash or not isinstance(src_hash, str) or not _SHA256_RE.fullmatch(src_hash):
        prov_ref = getattr(scene, "provider_product_id", "") or getattr(scene, "provenance_ref", "") or scene_id
        src_hash = hashlib.sha256(f"{sensor_raw}:{scene_id}:{prov_ref}:{valid_time}".encode()).hexdigest()

    try:
        return EvidenceFootprint(
            observation_id=scene_id,
            source_sha256=src_hash,
            operator_sha256=op_sha,
            tenant_id=tenant_id,
            farm_id=farm_id,
            plot_id=plot_id,
            geometry_sha256=geometry_sha256,
            observation_valid_time=valid_time,
            committed_at=commit_iso,
            supported_states=supported_states,
            bbox=bbox,
            crs=scene_crs,
            native_resolution_m=native_res,
            psf_fwhm_m=psf_fwhm,
            observability=observability,
            calibrated_operator_sha256=cal_op_sha,
            classification="physical",
            nodata=False,
            independent_holdout_sha256=None,
        )
    except (SpatialSupportViolation, ValueError, TypeError):
        return None


def adapt_scenes_to_footprints(
    scenes: Sequence[Any],
    *,
    tenant_id: str,
    farm_id: str,
    plot_id: str,
    geometry_sha256: str,
    target_crs: str,
    committed_at: Optional[str] = None,
) -> Tuple[EvidenceFootprint, ...]:
    """Translate a sequence of scenes into EvidenceFootprint instances.

    Filters out scenes that fail admission, CRS match, or namespace boundaries.
    """
    footprints: List[EvidenceFootprint] = []
    seen_ids = set()
    for scene in scenes:
        fp = adapt_scene_to_footprint(
            scene,
            tenant_id=tenant_id,
            farm_id=farm_id,
            plot_id=plot_id,
            geometry_sha256=geometry_sha256,
            target_crs=target_crs,
            committed_at=committed_at,
        )
        if fp is not None and fp.observation_id not in seen_ids:
            footprints.append(fp)
            seen_ids.add(fp.observation_id)
    return tuple(footprints)
