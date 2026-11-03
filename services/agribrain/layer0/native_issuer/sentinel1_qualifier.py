"""B2B-03A read-only Sentinel-1 native evidence / orbit / radar QA screen.

Replays B2B-01/B2B-02B source evidence, not client metadata. Even positive
structural QA is *not* calibrated measurement noise, independent plot/zone
authority, a signed state-input grant, or pilot publication authorization.

Temporary use of S2's geometry/time helpers is intentionally confined to
non-authorizing diagnostic pixel-center support, pending MESIA B2B-05.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Any, Mapping
import hashlib
import json
import math
import tarfile

import numpy as np

from services.agribrain.layer0.archive.raster_store import RasterStore
from services.agribrain.layer0.asmae_scene_products.product_binding import (
    normalize_product_id, verify_exact_product_binding,
)
from services.agribrain.layer0.asmae_scene_products.scene_product_schema import SceneProduct
from services.agribrain.layer0.native_issuer.acquisition_evidence import (
    NativeEvidenceError, NativeEvidenceStore, OriginClass, _reject_duplicate_keys,
)
from services.agribrain.layer0.native_issuer.sentinel2_qualifier import (
    TrustedPlotContext, _canonical, _polygon_mask, _time, _validate_scope,
)

DOMAIN = "akaloris/layer0/sentinel1-native-structure-screen/v1"
_CATALOG = "https://sh.dataspace.copernicus.eu/catalog/v1/search"
_PROCESS = "https://sh.dataspace.copernicus.eu/process/v1"
_REQUIRED = frozenset(("VV", "VH", "DATAMASK"))
_MAX_MEMBERS = 40
_MAX_TIFF_BYTES = 48 * 1024 * 1024
_MAX_USERDATA_BYTES = 1024 * 1024
_MAX_TIFF_PIXELS = 2_000_000
_MAX_PIXEL_CENTER_SUPPORT = 1024 * 1024
_MAX_POLYGON_VERTICES = 256
_MIN_VALID_FRACTION = 0.70
_ACCEPTED_CALIBRATIONS = frozenset(("SIGMA0_ELLIPSOID", "SIGMA0_TERRAIN"))


class S1ScreenStatus(str, Enum):
    REJECTED = "REJECTED"
    DEFERRED_NATIVE_AUTHORITY = "DEFERRED_NATIVE_AUTHORITY"
    SCREENED_NATIVE_SAR_STRUCTURE = "SCREENED_NATIVE_SAR_STRUCTURE"


@dataclass(frozen=True)
class S1NativeQAScreen:
    status: S1ScreenStatus
    reason: str
    proof_hash: str | None = None
    diagnostic_metrics: dict[str, Any] = field(default_factory=dict)
    eligible_for_state_grant: bool = False
    scientific_publication_authorized: bool = False


def _reject(reason: str) -> S1NativeQAScreen:
    return S1NativeQAScreen(S1ScreenStatus.REJECTED, reason)


def _defer(reason: str) -> S1NativeQAScreen:
    return S1NativeQAScreen(S1ScreenStatus.DEFERRED_NATIVE_AUTHORITY, reason)


def _orbit_number(value: Any, *, relative: bool) -> int | None:
    if type(value) is int:
        raw = value
    elif isinstance(value, str):
        token = value.strip().upper()
        if relative and token.startswith("R"):
            token = token[1:]
        if not token.isdigit():
            return None
        raw = int(token)
    else:
        return None
    upper = 175 if relative else 1_000_000
    return raw if 1 <= raw <= upper else None


def _orbit_pass(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return {
        "ASCENDING": "ASCENDING", "ASC": "ASCENDING", "A": "ASCENDING",
        "DESCENDING": "DESCENDING", "DESC": "DESCENDING", "D": "DESCENDING",
    }.get(value.strip().upper())


def _read_sar_process_tar(payload: bytes) -> tuple[dict[str, np.ndarray], dict]:
    """No extraction to disk; preflight TIFF dimensions before decode."""
    try:
        import tifffile
    except ImportError:
        raise NativeEvidenceError("sar_tiff_decoder_unavailable") from None
    bands: dict[str, np.ndarray] = {}
    userdata = None
    try:
        with tarfile.open(fileobj=BytesIO(payload), mode="r:") as archive:
            members = archive.getmembers()
            if len(members) > _MAX_MEMBERS:
                raise NativeEvidenceError("oversized_sar_archive")
            for member in members:
                if not member.isfile() or member.issym() or member.islnk():
                    raise NativeEvidenceError("unsafe_sar_archive_member")
                if (
                    member.size <= 0 or member.size > _MAX_TIFF_BYTES
                    or Path(member.name).name != member.name
                    or ".." in Path(member.name).parts
                ):
                    raise NativeEvidenceError("unsafe_sar_archive_path_or_size")
                descriptor = archive.extractfile(member)
                if descriptor is None:
                    raise NativeEvidenceError("unreadable_sar_archive_member")
                blob = descriptor.read(_MAX_TIFF_BYTES + 1)
                if len(blob) != member.size:
                    raise NativeEvidenceError("truncated_sar_archive_member")
                lower = member.name.lower()
                if lower.endswith((".tif", ".tiff")):
                    name = member.name.rsplit(".", 1)[0].upper()
                    if name in bands:
                        raise NativeEvidenceError("duplicate_sar_raster_band")
                    if name not in _REQUIRED:
                        raise NativeEvidenceError("unapproved_sar_process_raster")
                    with tifffile.TiffFile(BytesIO(blob)) as tif:
                        if len(tif.series) != 1:
                            raise NativeEvidenceError("ambiguous_sar_tiff_series")
                        series = tif.series[0]
                        shape = series.shape
                        if (
                            len(shape) != 2 or min(shape) < 1
                            or math.prod(shape) > _MAX_TIFF_PIXELS
                        ):
                            raise NativeEvidenceError("oversized_or_invalid_sar_tiff")
                        bands[name] = np.asarray(series.asarray())
                elif lower.endswith(".json"):
                    if userdata is not None or len(blob) > _MAX_USERDATA_BYTES:
                        raise NativeEvidenceError("ambiguous_sar_process_userdata")
                    userdata = json.loads(
                        blob.decode("utf-8"),
                        object_pairs_hook=_reject_duplicate_keys,
                    )
                    if not isinstance(userdata, dict):
                        raise NativeEvidenceError("invalid_sar_process_userdata")
                else:
                    raise NativeEvidenceError("unapproved_sar_archive_member")
    except (tarfile.TarError, OSError, UnicodeError, ValueError, TypeError):
        raise NativeEvidenceError("invalid_native_sar_process_archive") from None
    if not _REQUIRED.issubset(bands) or userdata is None:
        raise NativeEvidenceError("missing_sar_polarization_mask_or_userdata")
    return bands, userdata


def _stable_sar_hash(bands: Mapping[str, np.ndarray]) -> str:
    # Same algorithm as s1_real_scene_product_fetcher._stable_array_hash.
    dig = hashlib.sha256()
    for name in sorted(bands):
        arr = np.ascontiguousarray(np.asarray(bands[name]))
        dig.update(name.encode("ascii"))
        dig.update(str(arr.dtype).encode("ascii"))
        dig.update(np.asarray(arr.shape, dtype=np.int64).tobytes())
        dig.update(arr.tobytes())
    return dig.hexdigest()


def _check_request(
    request: Mapping[str, Any], *, sensor: str,
    scene: SceneProduct, catalog_time, expected_sha: str,
    is_process: bool,
) -> bool:
    try:
        if hashlib.sha256(_canonical(request)).hexdigest() != expected_sha:
            return False
        if is_process:
            source = request["input"]["data"]
            if not isinstance(source, list) or len(source) != 1:
                return False
            src = source[0]
            if src.get("type") != "sentinel-1-grd":
                return False
            filters = src.get("dataFilter", {})
            if filters.get("mosaickingOrder") != "mostRecent":
                return False
            start, end = src["timeRange"]["from"], src["timeRange"]["to"]
            bbox = request["input"]["bounds"]["bbox"]
            crs = request["input"]["bounds"]["properties"]["crs"]
            out = request["output"]
            if (
                crs != "http://www.opengis.net/def/crs/EPSG/0/4326"
                or type(out.get("width")) is not int or out["width"] != scene.width
                or type(out.get("height")) is not int or out["height"] != scene.height
            ):
                return False
            names = [x.get("identifier") for x in out["responses"] if isinstance(x,dict)]
            if len(names) != len(set(names)) or not {
                "VV", "VH", "dataMask", "userdata"
            }.issubset(names):
                return False
            script = request.get("evalscript")
            if not isinstance(script, str) or json.dumps(scene.provider_product_id) not in script:
                return False
        else:
            collections = request["collections"]
            if collections != ["sentinel-1-grd"]:
                return False
            bbox = request["bbox"]
            start, end = request["datetime"].split("/")
        if not _time(start) <= catalog_time <= _time(end):
            return False
        if (
            not isinstance(bbox, list) or len(bbox) != 4
            or any(type(v) not in (int,float) or not math.isfinite(v) for v in bbox)
            or not bbox[0] < bbox[2] or not bbox[1] < bbox[3]
        ):
            return False
        if is_process:
            transform = (
                bbox[0], (bbox[2]-bbox[0])/scene.width, 0.,
                bbox[3], 0., -(bbox[3]-bbox[1])/scene.height,
            )
            if (
                not isinstance(scene.transform, tuple) or len(scene.transform) != 6
                or any(
                    type(v) not in (int,float) or not math.isfinite(v)
                    for v in scene.transform
                )
                or any(
                    not math.isclose(float(a), float(b), rel_tol=0, abs_tol=1e-12)
                    for a,b in zip(scene.transform, transform)
                )
                or scene.crs != "EPSG:4326"
            ):
                return False
        return True
    except (KeyError, TypeError, ValueError, AttributeError, ZeroDivisionError):
        return False


def _verify_orbit(
    properties: Mapping[str, Any], userdata: Mapping[str, Any],
    scene: SceneProduct,
) -> tuple[int, str, int | None] | None:
    relative = _orbit_number(properties.get("sat:relative_orbit"), relative=True)
    direction = _orbit_pass(properties.get("sat:orbit_state"))
    if relative is None or direction is None:
        return None
    absolute = _orbit_number(properties.get("sat:absolute_orbit"), relative=False)
    payload = userdata.get("userData", userdata)
    tiles = payload.get("tiles") if isinstance(payload, dict) else None
    if not isinstance(tiles, list) or not tiles:
        return None
    for tile in tiles:
        if not isinstance(tile, dict):
            return None
        tile_relative = _orbit_number(tile.get("relativeOrbitNumber"), relative=True)
        tile_direction = _orbit_pass(tile.get("orbitDirection"))
        if tile_relative is None or tile_direction is None:
            return None
        if tile_relative != relative or tile_direction != direction:
            raise NativeEvidenceError("sar_catalog_process_orbit_conflict")
        reported_absolute = tile.get("orbitId")
        if reported_absolute is not None and absolute is not None:
            if _orbit_number(reported_absolute, relative=False) != absolute:
                raise NativeEvidenceError("sar_catalog_process_absolute_orbit_conflict")
    scene_relative = _orbit_number(scene.provider_relative_orbit, relative=True)
    scene_direction = _orbit_pass(scene.provider_orbit_pass)
    if scene_relative is None or scene_direction is None:
        return None
    if scene_relative != relative or scene_direction != direction:
        raise NativeEvidenceError("sar_scene_orbit_conflicts_with_captured_provider")
    return relative, direction, absolute


def screen_sentinel1_native(
    *, scene: SceneProduct, evidence_store: NativeEvidenceStore,
    trusted_plot: TrustedPlotContext | None = None,
    min_valid_fraction: float = 0.70,
) -> S1NativeQAScreen:
    """Structural SAR screen only. No state grant regardless of outcome."""
    try:
        if (
            type(min_valid_fraction) is not float
            or not _MIN_VALID_FRACTION <= min_valid_fraction <= 1.0
        ):
            return _reject("invalid_sar_qa_policy")
        if (
            not isinstance(scene, SceneProduct) or scene.sensor != "S1"
            or scene.test_override or scene.source_reality != "real_raster"
            or not isinstance(evidence_store, NativeEvidenceStore)
            or not scene.native_catalog_acquisition_id
            or not scene.native_process_acquisition_id
            or not scene.provider_product_id
        ):
            return _reject("missing_native_sar_evidence")
        catalog = evidence_store.verified_cache_receipt(scene.native_catalog_acquisition_id)
        process = evidence_store.verified_cache_receipt(scene.native_process_acquisition_id)
        if (
            catalog.sensor != "S1" or process.sensor != "S1"
            or catalog.provider != "sentinel_hub" or process.provider != "sentinel_hub"
            or catalog.endpoint != _CATALOG or process.endpoint != _PROCESS
            or catalog.origin_class != OriginClass.PROVENANCE_VERIFIED_CACHE
            or process.origin_class != OriginClass.PROVENANCE_VERIFIED_CACHE
            or scene.native_evidence_status not in (
                "CAPTURED_UNQUALIFIED", "PROVENANCE_VERIFIED_CACHE",
            )
            or process.provider_product_id != scene.provider_product_id
            or normalize_product_id(scene.catalog_item_id) != normalize_product_id(
                scene.provider_product_id
            )
            or scene.provider_response_hash != process.response_sha256
            or scene.process_request_hash != process.request_sha256
        ):
            return _reject("unbound_sar_catalog_process_evidence")
        catalog_bytes = evidence_store._path("objects", catalog.object_id).read_bytes()
        process_bytes = evidence_store._path("objects", process.object_id).read_bytes()
        payload = json.loads(
            catalog_bytes, object_pairs_hook=_reject_duplicate_keys,
        )
        features = payload.get("features") if isinstance(payload, dict) else None
        if not isinstance(features, list):
            return _reject("invalid_sar_catalog_features")
        matches = [
            f for f in features if isinstance(f,dict)
            and normalize_product_id(f.get("id")) == normalize_product_id(
                scene.provider_product_id
            )
        ]
        if len(matches) != 1:
            return _reject("missing_or_ambiguous_sar_catalog_product")
        selected = matches[0]
        if selected.get("collection") != "sentinel-1-grd":
            return _reject("wrong_sar_catalog_collection")
        properties = selected.get("properties")
        if not isinstance(properties, dict):
            return _reject("missing_sar_catalog_properties")
        item_time = _time(properties.get("datetime"))
        if (
            scene.acquisition_datetime.tzinfo is None
            or scene.acquisition_datetime.utcoffset() is None
            or scene.acquisition_datetime.astimezone(timezone.utc) != item_time
        ):
            return _reject("sar_acquisition_timestamp_mismatch")
        if _time(catalog.retrieved_at) < item_time or _time(process.retrieved_at) < item_time:
            return _reject("sar_response_predates_acquisition")
        # Only truly documented dual-pol products are eligible even for
        # a structural screen; absent/ambiguous STAC SAR metadata defers.
        polarizations = properties.get("sar:polarizations")
        if polarizations is None or properties.get("sar:product_type") is None:
            return _defer("native_sar_polarization_product_proof_missing")
        if (
            not isinstance(polarizations, list)
            or len(polarizations) != 2
            or set(polarizations) != {"VV","VH"}
            or properties.get("sar:product_type") != "GRD"
        ):
            return _reject("sar_product_or_polarization_conflicts_with_required_dual_pol_grd")
        bands, userdata = _read_sar_process_tar(process_bytes)
        binding = verify_exact_product_binding(
            scene.provider_product_id, userdata, "S1",
        )
        if (
            not binding["is_exact"] or scene.product_binding != "exact_catalog_item"
            or not isinstance(scene.binding_proof, dict)
            or scene.binding_proof != binding["proof"]
        ):
            return _reject("sar_catalog_process_product_mismatch")
        orbit = _verify_orbit(properties, userdata, scene)
        if orbit is None:
            return _defer("sar_orbit_not_proven_or_mixed")
        relative, direction, absolute = orbit
        try:
            catalog_request = evidence_store.verified_request_body(catalog.acquisition_id)
            process_request = evidence_store.verified_request_body(process.acquisition_id)
        except NativeEvidenceError as exc:
            if str(exc) == "captured_request_not_retained":
                return _defer("historical_sar_request_not_retained")
            return _reject("invalid_original_sar_request_evidence")
        if (
            not _check_request(
                catalog_request, sensor="S1", scene=scene,
                catalog_time=item_time, expected_sha=catalog.request_sha256,
                is_process=False,
            )
            or not _check_request(
                process_request, sensor="S1", scene=scene,
                catalog_time=item_time, expected_sha=process.request_sha256,
                is_process=True,
            )
        ):
            return _reject("captured_sar_request_grid_time_or_product_mismatch")
        # The current live S1 fetcher does not declare a calibrated
        # backscatter coefficient. Structural checks can continue, but the
        # missing configuration must prevent a positive screen.
        src = process_request["input"]["data"][0]
        processing = src.get("processing", {})
        coefficient = processing.get("backCoeff")
        if coefficient not in _ACCEPTED_CALIBRATIONS:
            return _defer("sar_backscatter_calibration_not_proven")
        if (
            any(a.shape != (scene.height,scene.width) for a in bands.values())
            or type(scene.height) is not int or type(scene.width) is not int
            or scene.height < 1 or scene.width < 1
            or scene.height*scene.width > _MAX_TIFF_PIXELS
        ):
            return _reject("sar_grid_shape_mismatch")
        raw_hash = _stable_sar_hash(bands)
        legacy_hash = _stable_sar_hash({k:bands[k] for k in ("VV","VH")})
        if scene.content_hash != raw_hash and not (
            scene.native_evidence_status == "PROVENANCE_VERIFIED_CACHE"
            and scene.content_hash == legacy_hash
        ):
            return _reject("sar_source_content_hash_mismatch")
        loader = RasterStore()
        for name in sorted(_REQUIRED):
            ref = (
                scene.mask_refs.get("DATAMASK") or scene.mask_refs.get("dataMask")
                if name == "DATAMASK"
                else scene.band_refs.get(name)
            )
            if not isinstance(ref,str) or not ref:
                return _reject("missing_stored_sar_band_or_mask")
            cached = np.asarray(loader.load_band(ref))
            native = bands[name]
            if (
                cached.shape != native.shape or cached.dtype != native.dtype
                or not np.array_equal(
                    cached,native,
                    equal_nan=bool(np.issubdtype(cached.dtype,np.inexact)),
                )
            ):
                return _reject("sar_cached_raster_differs_from_provider_bytes")
        if (
            any(not np.issubdtype(x.dtype,np.number) for x in bands.values())
            or np.any(~np.isfinite(bands["DATAMASK"]))
            or np.any(~np.isin(bands["DATAMASK"],(0,1)))
        ):
            return _reject("invalid_sar_data_mask")
        if any(scene.band_units.get(k) != "linear_power" for k in ("VV","VH")):
            return _reject("sar_power_units_not_proven")
        if trusted_plot is None:
            return _defer("trusted_sar_plot_geometry_missing")
        ring = _validate_scope(trusted_plot)
        if (
            scene.height*scene.width > _MAX_PIXEL_CENTER_SUPPORT
            or len(ring) > _MAX_POLYGON_VERTICES
        ):
            return _defer("robust_mesia_sar_support_required")
        bounds=(
            scene.transform[0],
            scene.transform[3]+scene.height*scene.transform[5],
            scene.transform[0]+scene.width*scene.transform[1],
            scene.transform[3],
        )
        if any(
            not (bounds[0]-1e-12<=x<=bounds[2]+1e-12
                 and bounds[1]-1e-12<=y<=bounds[3]+1e-12)
            for x,y in ring
        ):
            return _reject("sar_plot_outside_raster_extent")
        centers = _polygon_mask(scene.width,scene.height,scene.transform,ring)
        count=int(centers.sum())
        if count == 0:
            return _reject("sar_zero_plot_pixel_support")
        vv,vh,mask=bands["VV"],bands["VH"],bands["DATAMASK"]
        usable=(
            (mask==1) & np.isfinite(vv) & np.isfinite(vh)
            & (vv>0) & (vh>0)
        )
        good=int(np.count_nonzero(usable & centers))
        fraction=good/count
        if fraction < min_valid_fraction:
            return _reject("sar_insufficient_clear_polarization_support")
        # Do not assert that positive dual-pol pixels alone prove calibrated
        # incidence angle, border noise removal, speckle independence or
        # scientifically valid moisture/biomass inference.
        metrics={
            "relative_orbit": relative,
            "orbit_pass": direction,
            "absolute_orbit": absolute,
            "polarizations": ["VV","VH"],
            "valid_fraction": fraction,
            "plot_pixel_centers": count,
            "valid_pixel_centers": good,
            "backscatter_coefficient": coefficient,
            "incidence_angle_proven": False,
            "border_noise_removed_proven": False,
            "speckle_calibrated": False,
            "observation_sigma_calibrated": False,
            "support_method": "EPSG4326_PIXEL_CENTER_SAMPLE_ONLY",
            "independent_multitemporal_eligibility": False,
        }
        proof={
            "domain":DOMAIN,
            "catalog_acquisition_id":catalog.acquisition_id,
            "process_acquisition_id":process.acquisition_id,
            "catalog_request_sha256":catalog.request_sha256,
            "process_request_sha256":process.request_sha256,
            "product_id":scene.provider_product_id,
            "catalog_datetime":item_time.isoformat(),
            "binding_proof":binding["proof"],
            "source_raster_sha256":raw_hash,
            "plot_id":trusted_plot.plot_id,
            "plot_geometry_hash":trusted_plot.geometry_hash,
            "plot_geometry_version":trusted_plot.geometry_version,
            "grid_crs":scene.crs,
            "grid_transform":list(scene.transform),
            "grid_size":[scene.height,scene.width],
            "quality_policy":{"domain":DOMAIN,"min_valid_fraction":min_valid_fraction},
            "diagnostic_metrics":metrics,
        }
        return S1NativeQAScreen(
            S1ScreenStatus.SCREENED_NATIVE_SAR_STRUCTURE,
            "bounded_sar_structure_pass_not_radar_measurement_or_state_authority",
            hashlib.sha256(_canonical(proof)).hexdigest(),metrics,
        )
    except (NativeEvidenceError, OSError, TypeError, ValueError, AttributeError,
            KeyError, OverflowError, tarfile.TarError) as err:
        return _reject(
            str(err) if isinstance(err,NativeEvidenceError)
            else "invalid_or_unverifiable_native_sar_evidence"
        )
