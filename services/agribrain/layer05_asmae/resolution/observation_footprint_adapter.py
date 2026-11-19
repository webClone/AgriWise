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
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .state_cell_support import EvidenceFootprint, STATE_NAMES, SpatialSupportViolation
from ..chain_integrity import compute_h_matrix_digest
from ..geometry.psf import get_psf_model

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Physical & epistemic sensor specifications
S2_OPTICAL_STATES = (
    "vigor", "lai", "chlorophyll", "canopy_water",
    "structure", "bare_soil_fraction", "phenology_progress",
)
# C-band SAR directly senses surface roughness and near-surface moisture (top ~5cm).
# Root-zone soil moisture is an indirect modeled coupling (EnKF propagation), never a direct observation.
S1_SAR_STATES = (
    "surface_wetness_event", "structure",
)

S2_OPERATOR_SHA256 = hashlib.sha256(b"akaloris/operator/s2_msi/spatial_v1").hexdigest()
S2_CALIBRATED_OPERATOR_SHA256 = hashlib.sha256(b"akaloris/operator/s2_msi/calibrated_psf_v1").hexdigest()

S1_OPERATOR_SHA256 = hashlib.sha256(b"akaloris/operator/s1_cband_sar/spatial_v1").hexdigest()
S1_CALIBRATED_OPERATOR_SHA256 = hashlib.sha256(b"akaloris/operator/s1_cband_sar/calibrated_psf_v1").hexdigest()

# IR04-5CC: verifier-only, externally configured Ed25519 public-key trust.
# No production issuer secret or receipt-signing function is available here.
from .admission_trust import (
    ADMISSION_DOMAIN as ADMISSION_GRANT_DOMAIN,
    get_trusted_admission_keyring,
    verify_admission_grant,
)


def compute_scene_asset_sha256(scene: Any) -> Optional[str]:
    """Compute deterministic SHA-256 over exact physical scene asset bytes/arrays."""
    h = hashlib.sha256()

    # 1. Raw byte payloads
    for attr in ("asset_bytes", "raw_asset_bytes", "source_bytes"):
        val = getattr(scene, attr, None)
        if isinstance(val, (bytes, bytearray)) and len(val) > 0:
            h.update(val)
            return h.hexdigest()

    # 2. Multi-band array payloads
    bands = getattr(scene, "bands", None)
    if isinstance(bands, Mapping) and bands:
        has_arrays = False
        for b_name in sorted(bands.keys()):
            arr = bands[b_name]
            h.update(str(b_name).encode("utf-8"))
            if hasattr(arr, "shape") and hasattr(arr, "dtype") and hasattr(arr, "tobytes"):
                has_arrays = True
                h.update(str(arr.shape).encode("utf-8"))
                h.update(str(arr.dtype).encode("utf-8"))
                h.update(arr.tobytes())
            elif isinstance(arr, (bytes, bytearray)):
                has_arrays = True
                h.update(arr)
            elif hasattr(arr, "tobytes"):
                has_arrays = True
                h.update(arr.tobytes())
            elif isinstance(arr, (int, float, bool, str)):
                h.update(str(arr).encode("utf-8"))
        if has_arrays:
            return h.hexdigest()

    # 3. Single raster array
    for attr in ("raster", "raster_data", "data"):
        arr = getattr(scene, attr, None)
        if arr is not None and hasattr(arr, "shape") and hasattr(arr, "dtype") and hasattr(arr, "tobytes"):
            h.update(str(arr.shape).encode("utf-8"))
            h.update(str(arr.dtype).encode("utf-8"))
            h.update(arr.tobytes())
            return h.hexdigest()

    return None


def verify_scene_admission_receipt(
    receipt: Any,
    *,
    scene: Any,
    tenant_id: str,
    farm_id: str,
    plot_id: str,
    geometry_sha256: str,
    operator_sha256: str,
    calibrated_operator_sha256: Optional[str] = None,
    valid_time: str,
    committed_at: str,
    trusted_keyring: Optional[Mapping[str, Any]] = None,
    now: Optional[datetime] = None,
) -> Tuple[bool, str]:
    """Verify externally signed Ed25519 authority; never sign in ASMAE."""
    if trusted_keyring is not None:
        # Runtime caller must not inject arbitrary verification roots.
        return False, "caller_supplied_trust_forbidden"
    return verify_admission_grant(
        receipt,
        scene_source=getattr(scene, "sensor", None),
        tenant_id=str(tenant_id), farm_id=str(farm_id), plot_id=str(plot_id),
        geometry_sha256=str(geometry_sha256),
        asset_sha256=compute_scene_asset_sha256(scene),
        operator_sha256=str(operator_sha256),
        calibrated_operator_sha256=str(calibrated_operator_sha256 or operator_sha256),
        valid_time=valid_time, committed_at=committed_at, now=now,
    )


def _ensure_utc_iso(dt: Any) -> Optional[str]:
    """Convert datetime or ISO string to standard UTC ISO-8601 string.

    Prohibits naive timestamp timezone inference: any string or datetime
    without an explicit timezone offset ('Z', '+', '-') is rejected.
    """
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            # Explicitly reject naive datetime (no inference)
            return None
        return dt.astimezone(timezone.utc).isoformat()
    if isinstance(dt, str):
        val = dt.strip()
        if not val:
            return None
        # Must have an explicit timezone indicator: 'Z' or '+HH:MM' or '-HH:MM'
        if not (val.endswith("Z") or ("+" in val[10:]) or ("-" in val[10:] and len(val) > 19)):
            return None
        try:
            parsed = datetime.fromisoformat(val.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return None
            return parsed.astimezone(timezone.utc).isoformat()
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
    operator: Optional[Any] = None,
    require_operator_binding: bool = False,
) -> Optional[EvidenceFootprint]:
    """Translate an admitted scene into an EvidenceFootprint or fail closed (return None).

    Strict admission requirements:
    1. Tenant/farm/plot namespace and geometry digest must match.
    2. Scene must be production-usable or scientifically admitted (not test/diagnostic-only).
    3. Scene CRS must match target projected metric CRS.
    4. Valid non-degenerate bounding box and UTC timestamp required.
    5. When operator is supplied or required, binds to genuine H_t matrix digest and PSF model.
    """
    if not all((tenant_id, farm_id, plot_id, geometry_sha256, target_crs)):
        return None
    if not _SHA256_RE.fullmatch(geometry_sha256):
        return None

    # Check scene admission / reality attributes (HNEW-05, C752-P1-02)
    if getattr(scene, "test_override", False):
        return None
    if getattr(scene, "diagnostic_only", False):
        return None

    is_prod_usable = bool(
        getattr(scene, "production_usable", False)
        or getattr(scene, "scientifically_admitted", False)
    )
    if not is_prod_usable:
        return None

    # Namespace match: mandatory in production/operator-binding mode (C752-P1-02)
    scene_tenant = getattr(scene, "tenant_id", None)
    scene_farm = getattr(scene, "farm_id", None)
    scene_plot = getattr(scene, "plot_id", None)
    scene_geom = getattr(scene, "geometry_sha256", None) or getattr(scene, "geometry_hash", None)

    if require_operator_binding:
        # Mandatory namespace & geometry identity on scene
        if not all((scene_tenant, scene_farm, scene_plot, scene_geom)):
            return None
        if not _SHA256_RE.fullmatch(str(scene_geom)):
            return None

    if scene_tenant and str(scene_tenant) != str(tenant_id):
        return None
    if scene_farm and str(scene_farm) != str(farm_id):
        return None
    if scene_plot and str(scene_plot) != str(plot_id):
        return None
    if scene_geom and str(scene_geom) != str(geometry_sha256):
        return None

    if require_operator_binding:
        # Positive signed admission & verified provider binding required (C752-P1-02, IR04-665-01)
        # Syntactic hashes, metadata flags, or provider product IDs alone are NOT authority.
        if getattr(scene, "forged_asset_hash", False) or getattr(scene, "unverified_asset_hash", False):
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

    # Bitemporal commitment extraction (HNEW-02, C752-P1-01)
    scene_comm = (
        getattr(scene, "committed_at", None)
        or getattr(scene, "journal_committed_at", None)
        or getattr(scene, "journal_entry_time", None)
    )
    if require_operator_binding and not scene_comm:
        # Mandatory genuine journal commitment timestamp in operator binding mode
        return None
    # Caller committed_at is only used in non-operator-binding mode or if matching;
    # in operator binding mode, native journal commitment is strictly preserved.
    # Engine must pass committed_at=None so query K never overwrites scene commitment.
    commit_input = scene_comm if require_operator_binding else (committed_at if committed_at is not None else scene_comm)
    commit_iso = _ensure_utc_iso(commit_input)
    if not commit_iso:
        # Prohibits ungrounded temporal commitment: never fall back to valid_time
        return None

    # Sensor classification
    sensor_raw = str(getattr(scene, "sensor", "") or "").upper()
    if sensor_raw in ("S2", "SENTINEL-2", "SENTINEL_2", "S2_MSI"):
        sensor = "S2"
        supported_states = S2_OPTICAL_STATES
        cloud_frac = float(getattr(scene, "cloud_fraction", 0.0) or 0.0)
        # When per-cell valid_support or operator valid support mask is provided,
        # cell validity is enforced cell-by-cell. Observability for unmasked cells
        # is determined by radiometric QA score (or 0.95), not penalized by whole-scene clouds.
        if (hasattr(scene, "valid_support") and scene.valid_support is not None) or (
            operator is not None and getattr(operator, "valid_support_hash", "")
        ):
            qa = getattr(scene, "qa_score", None)
            observability = float(qa) if qa is not None and 0 <= float(qa) <= 1 else 0.95
        else:
            observability = max(0.0, min(1.0, 1.0 - cloud_frac))
    elif sensor_raw in ("S1", "SENTINEL-1", "SENTINEL_1", "S1_SAR"):
        sensor = "S1"
        supported_states = S1_SAR_STATES
        qa = getattr(scene, "qa_score", None)
        observability = float(qa) if qa is not None and 0 <= float(qa) <= 1 else 0.85
    else:
        # Unknown or uncalibrated sensor: cannot confer calibrated local footprint
        return None

    band = str(getattr(scene, "band", "") or (getattr(operator, "band", "") if operator else "") or "").upper()
    if not band and sensor == "S2":
        bands_dict = getattr(scene, "bands", None)
        if isinstance(bands_dict, dict) and bands_dict:
            b_keys = {str(k).upper() for k in bands_dict.keys()}
            s2_20m = {"B05", "B06", "B07", "B8A", "B11", "B12"}
            s2_60m = {"B01", "B09", "B10"}
            s2_10m = {"B02", "B03", "B04", "B08"}
            if b_keys & s2_20m:
                band = "B05"
            elif b_keys & s2_60m:
                band = "B01"
            elif b_keys & s2_10m:
                band = "B04"
            else:
                band = "B05"
        else:
            tf = getattr(scene, "transform", None)
            if tf and len(tf) >= 6 and max(abs(float(tf[1])), abs(float(tf[5]))) > 12.0:
                band = "B05"
            else:
                band = "B04"

    # PSF & Resolution calibration
    if operator is not None:
        blur_sigma = float(getattr(operator, "blur_sigma_m", 0.0) or 0.0)
        if blur_sigma > 0:
            psf_model = get_psf_model(sensor, band=band, custom_sigma_m=blur_sigma)
        else:
            psf_model = get_psf_model(sensor, band=band)
        psf_fwhm = round(psf_model.fwhm_m, 4)

        src_res = float(getattr(operator, "source_resolution_m", 0.0) or 0.0)
        if src_res > 0:
            if sensor == "S2" and band in ("B05", "B06", "B07", "B8A", "B11", "B12"):
                native_res = max(src_res, 20.0)
            else:
                native_res = src_res
        elif sensor == "S2":
            native_res = 20.0 if band in ("B05", "B06", "B07", "B8A", "B11", "B12") else 10.0
        else:
            native_res = 20.0
    else:
        if require_operator_binding:
            return None
        psf_model = get_psf_model(sensor, band=band)
        psf_fwhm = round(psf_model.fwhm_m, 4)
        if hasattr(scene, "psf_fwhm_m") and scene.psf_fwhm_m is not None:
            psf_fwhm = float(scene.psf_fwhm_m)
        if hasattr(scene, "native_resolution_m") and scene.native_resolution_m is not None:
            native_res = float(scene.native_resolution_m)
        elif sensor == "S2":
            native_res = 20.0 if band in ("B05", "B06", "B07", "B8A", "B11", "B12") else 10.0
        else:
            native_res = 20.0

    valid_cell_indices: Optional[Tuple[int, ...]] = None
    valid_support_hash: Optional[str] = None

    if operator is not None:
        if getattr(operator, "scene_id", "") and str(operator.scene_id) != scene_id:
            return None
        op_target_crs = str(getattr(operator, "target_crs", "") or "").upper()
        if op_target_crs and op_target_crs != str(target_crs).upper():
            return None
        op_source_crs = str(getattr(operator, "source_crs", "") or "").upper()
        if op_source_crs and op_source_crs != scene_crs:
            return None

        h_mat = getattr(operator, "H_matrix", None)
        matrix_digest = compute_h_matrix_digest(h_mat)
        if not matrix_digest or not _SHA256_RE.fullmatch(matrix_digest):
            return None
        op_sha = matrix_digest

        if h_mat is not None and hasattr(h_mat, "indices"):
            valid_cell_indices = tuple(sorted(set(int(idx) for idx in h_mat.indices)))

        op_valid_hash = getattr(operator, "valid_support_hash", "") or ""
        if op_valid_hash:
            valid_support_hash = op_valid_hash
            if hasattr(scene, "valid_support") and scene.valid_support is not None:
                supp_str = str(scene.valid_support).encode()
                actual_supp_hash = hashlib.sha256(supp_str).hexdigest()
                if op_valid_hash != actual_supp_hash:
                    return None

        op_id = getattr(operator, "operator_id", "") or scene_id
        cal_op_sha = hashlib.sha256(
            f"{op_id}:{matrix_digest}:{psf_fwhm:.4f}:{native_res}".encode()
        ).hexdigest()
    else:
        if require_operator_binding:
            return None
        op_sha = getattr(scene, "operator_sha256", None) or (S2_OPERATOR_SHA256 if sensor == "S2" else S1_OPERATOR_SHA256)
        cal_op_sha = getattr(scene, "calibrated_operator_sha256", None) or (S2_CALIBRATED_OPERATOR_SHA256 if sensor == "S2" else S1_CALIBRATED_OPERATOR_SHA256)
        # HNEW-04: Without bound operator, scene-pixel indices must NOT be mapped to target graph cells
        valid_cell_indices = None

    # Deterministic source content hash and signed admission verification (HNEW-01, IR04-665-01)
    computed_asset_sha = compute_scene_asset_sha256(scene)

    if require_operator_binding:
        # IR04-665-01: Positive Signed Source & Asset Admission Validation
        # 1. Physical asset arrays/bytes required
        if not computed_asset_sha or not _SHA256_RE.fullmatch(computed_asset_sha):
            return None

        # 2. Swapped asset hash protection: if scene claims content_hash, it must match exact bytes
        scene_content_hash = (
            getattr(scene, "content_hash", None)
            or getattr(scene, "source_asset_sha256", None)
            or getattr(scene, "sha256", None)
        )
        if scene_content_hash and str(scene_content_hash).lower() != computed_asset_sha.lower():
            return None

        # 3. Signed admission receipt required & verified against trusted key
        binding_proof = getattr(scene, "binding_proof", None)
        admission_receipt = getattr(scene, "admission_receipt", None) or (
            binding_proof.get("admission_receipt") if isinstance(binding_proof, dict) else None
        )
        if not admission_receipt or not isinstance(admission_receipt, dict):
            return None

        valid_receipt, _reason = verify_scene_admission_receipt(
            admission_receipt,
            scene=scene,
            tenant_id=tenant_id,
            farm_id=farm_id,
            plot_id=plot_id,
            geometry_sha256=geometry_sha256,
            operator_sha256=op_sha,
            calibrated_operator_sha256=cal_op_sha,
            valid_time=valid_time,
            committed_at=commit_iso,
        )
        if not valid_receipt:
            return None

        src_hash = computed_asset_sha
    else:
        src_hash = (
            computed_asset_sha
            or getattr(scene, "content_hash", None)
            or getattr(scene, "sha256", None)
            or getattr(scene, "source_asset_sha256", None)
            or getattr(scene, "immutable_source_sha256", None)
            or (getattr(operator, "source_sha256", None) if operator else None)
        )
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
            valid_cell_indices=valid_cell_indices,
            valid_support_hash=valid_support_hash,
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
    operator_bundle: Optional[Any] = None,
    operators: Optional[Sequence[Any]] = None,
    require_operator_binding: bool = False,
) -> Tuple[EvidenceFootprint, ...]:
    """Translate a sequence of scenes into EvidenceFootprint instances.

    Filters out scenes that fail admission, CRS match, or namespace boundaries.
    Binds post-selection operators when provided via operator_bundle or operators.
    """
    ops_list = []
    if operator_bundle is not None:
        ops_list.extend(getattr(operator_bundle, "operators", ()) or ())
    if operators:
        ops_list.extend(operators)
    op_map = {getattr(op, "scene_id", ""): op for op in ops_list if getattr(op, "scene_id", "")}

    footprints: List[EvidenceFootprint] = []
    seen_ids = set()
    for scene in scenes:
        s_id = str(getattr(scene, "scene_id", "") or "").strip()
        matched_op = op_map.get(s_id)
        fp = adapt_scene_to_footprint(
            scene,
            tenant_id=tenant_id,
            farm_id=farm_id,
            plot_id=plot_id,
            geometry_sha256=geometry_sha256,
            target_crs=target_crs,
            committed_at=committed_at,
            operator=matched_op,
            require_operator_binding=require_operator_binding,
        )
        if fp is not None and fp.observation_id not in seen_ids:
            footprints.append(fp)
            seen_ids.add(fp.observation_id)
    return tuple(footprints)
