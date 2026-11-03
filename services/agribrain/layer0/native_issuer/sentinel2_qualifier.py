"""B2B-02: independent, *non-authorizing* Sentinel-2 native QA screen.

This reader replays captured Catalog/Process response bytes and compares their
product identity, geospatial grid and original optical pixels to the cached
SceneProduct. It never signs an observation grant, mutates the scene's existing
production flags, or grants pilot publication/actuation authority.

Even a successful screen is NOT trusted physical/tenant plot authorization:
a deployment-backed registry, MESIA full polygon support, immutable source
objects and a separated KMS issuer remain distinct release gates.
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

from services.agribrain.layer0.asmae_scene_products.product_binding import (
    normalize_product_id, verify_exact_product_binding,
)
from services.agribrain.layer0.asmae_scene_products.scene_product_schema import SceneProduct
from services.agribrain.layer0.archive.raster_store import RasterStore
from services.agribrain.layer0.native_issuer.acquisition_evidence import (
    NativeEvidenceError, NativeEvidenceStore, OriginClass,
)

QUALIFIER_DOMAIN = "akaloris/layer0/sentinel2-native-qa-screen/v1"
_INVALID_SCL = frozenset({0, 1, 2, 3, 6, 7, 8, 9, 10, 11})
_REQUIRED_BANDS = ("B04", "B08", "SCL", "DATAMASK")
_HASH_BANDS = ("B04", "B08", "B11", "SCL", "DATAMASK")
_MAX_ARCHIVE_MEMBERS = 40
_MAX_TIFF_BYTES = 48 * 1024 * 1024
_MAX_PIXELS = 8192 * 8192


class S2ScreenStatus(str, Enum):
    REJECTED = "REJECTED"
    DEFERRED_SPATIAL_AUTHORITY = "DEFERRED_SPATIAL_AUTHORITY"
    SCREENED_NATIVE_QA = "SCREENED_NATIVE_QA"


@dataclass(frozen=True)
class TrustedPlotContext:
    """Typed *input* expected from a separately authorized backend resolver.

    Construction of this object does not prove IAM, tenant ownership, or
    MESIA containment. Never accept it directly from a web/client payload.
    """

    plot_id: str
    geometry_hash: str
    geometry_version: int
    polygon_wgs84: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class S2NativeQAScreen:
    status: S2ScreenStatus
    reason: str
    proof_hash: str | None = None
    diagnostic_metrics: dict[str, Any] = field(default_factory=dict)
    eligible_for_state_grant: bool = False
    scientific_publication_authorized: bool = False


def _deny(reason: str) -> S2NativeQAScreen:
    return S2NativeQAScreen(S2ScreenStatus.REJECTED, reason)


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise NativeEvidenceError("invalid_catalog_scene_timestamp")
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise NativeEvidenceError("invalid_catalog_scene_timestamp") from None
    if t.tzinfo is None or t.utcoffset() is None:
        raise NativeEvidenceError("naive_catalog_scene_timestamp")
    return t.astimezone(timezone.utc)


def _array_hash(bands: Mapping[str, np.ndarray]) -> str:
    # Exact same byte layout as S2 live acquisition _stable_array_hash().
    digest = hashlib.sha256()
    for name in sorted(bands):
        a = np.ascontiguousarray(bands[name])
        digest.update(name.upper().encode("utf-8"))
        digest.update(str(a.dtype).encode("ascii"))
        digest.update(np.asarray(a.shape, dtype=np.int64).tobytes())
        digest.update(a.tobytes())
    return digest.hexdigest()


def _read_captured_process(raw: bytes) -> tuple[dict[str, np.ndarray], dict]:
    """Bounded TAR parsing. No extraction onto the filesystem."""
    try:
        import tifffile
    except ImportError:
        raise NativeEvidenceError("tiff_decoder_unavailable") from None
    bands: dict[str, np.ndarray] = {}
    userdata: dict[str, Any] | None = None
    try:
        with tarfile.open(fileobj=BytesIO(raw), mode="r:") as archive:
            members = archive.getmembers()
            if len(members) > _MAX_ARCHIVE_MEMBERS:
                raise NativeEvidenceError("oversized_process_archive")
            for member in members:
                if not member.isfile() or member.issym() or member.islnk():
                    raise NativeEvidenceError("unsafe_process_archive_member")
                if member.size <= 0 or member.size > _MAX_TIFF_BYTES:
                    raise NativeEvidenceError("oversized_process_member")
                path = Path(member.name)
                if path.name != member.name or ".." in path.parts:
                    raise NativeEvidenceError("unsafe_process_archive_path")
                fd = archive.extractfile(member)
                if fd is None:
                    raise NativeEvidenceError("unreadable_process_member")
                blob = fd.read(_MAX_TIFF_BYTES + 1)
                if len(blob) != member.size or len(blob) > _MAX_TIFF_BYTES:
                    raise NativeEvidenceError("truncated_process_member")
                if member.name.lower().endswith((".tif", ".tiff")):
                    name = member.name.split(".")[0].upper()
                    if name in bands:
                        raise NativeEvidenceError("duplicate_process_band")
                    if name not in ("B04", "B08", "B11", "SCL", "DATAMASK"):
                        continue
                    with tifffile.TiffFile(BytesIO(blob)) as tif:
                        arr = np.asarray(tif.asarray())
                    if arr.ndim != 2 or arr.size > _MAX_PIXELS or arr.size == 0:
                        raise NativeEvidenceError("invalid_process_band_shape")
                    bands[name] = arr
                elif member.name.lower().endswith(".json"):
                    if userdata is not None:
                        raise NativeEvidenceError("ambiguous_process_userdata")
                    userdata = json.loads(blob.decode("utf-8"))
                    if not isinstance(userdata, dict):
                        raise NativeEvidenceError("invalid_process_userdata")
    except (tarfile.TarError, OSError, UnicodeError, ValueError, TypeError) as exc:
        if isinstance(exc, NativeEvidenceError):
            raise
        raise NativeEvidenceError("invalid_captured_process_archive") from None
    if any(name not in bands for name in _REQUIRED_BANDS):
        raise NativeEvidenceError("missing_native_optical_or_mask_bands")
    if userdata is None:
        raise NativeEvidenceError("missing_process_userdata")
    return bands, userdata


def _polygon_mask(
    width: int, height: int, transform: tuple[float, ...],
    ring: tuple[tuple[float, float], ...],
) -> np.ndarray:
    # Pixel-center sampling only; this is explicitly NOT an area-accurate
    # MESIA support proof for partial pixels or fine boundary edges.
    mask = np.zeros((height, width), dtype=bool)
    for r in range(height):
        for c in range(width):
            x = transform[0] + (c + .5) * transform[1] + (r + .5) * transform[2]
            y = transform[3] + (c + .5) * transform[4] + (r + .5) * transform[5]
            inside = False
            for idx, (x1, y1) in enumerate(ring):
                x2, y2 = ring[(idx + 1) % len(ring)]
                if ((y1 > y) != (y2 > y)) and x < (
                    (x2 - x1) * (y - y1) / (y2 - y1) + x1
                ):
                    inside = not inside
            mask[r, c] = inside
    return mask


def _validate_scope(scope: TrustedPlotContext | None) -> tuple[tuple[float, float], ...]:
    if scope is None:
        raise NativeEvidenceError("trusted_plot_scope_missing")
    if (
        not isinstance(scope, TrustedPlotContext)
        or not isinstance(scope.plot_id, str) or not scope.plot_id
        or not isinstance(scope.geometry_hash, str) or not scope.geometry_hash
        or type(scope.geometry_version) is not int or scope.geometry_version < 0
    ):
        raise NativeEvidenceError("invalid_trusted_plot_scope")
    ring = scope.polygon_wgs84
    if (
        not isinstance(ring, tuple) or len(ring) < 3 or len(ring) > 10000
        or any(
            not isinstance(point, tuple) or len(point) != 2
            or any(
                type(v) not in (int, float) or not math.isfinite(v)
                for v in point
            )
            for point in ring
        )
    ):
        raise NativeEvidenceError("invalid_trusted_plot_polygon")
    if ring[0] == ring[-1]:
        ring = ring[:-1]
    if len(set(ring)) < 3:
        raise NativeEvidenceError("degenerate_plot_polygon")
    for lon, lat in ring:
        if not -180 <= lon <= 180 or not -90 <= lat <= 90:
            raise NativeEvidenceError("plot_polygon_outside_wgs84")
    twice_area = sum(
        x1*y2-x2*y1 for (x1,y1),(x2,y2) in zip(ring,ring[1:]+ring[:1])
    )
    if not math.isfinite(twice_area) or abs(twice_area) <= 1e-14:
        raise NativeEvidenceError("degenerate_plot_polygon")
    return ring


def screen_sentinel2_native(
    *, scene: SceneProduct, evidence_store: NativeEvidenceStore,
    trusted_plot: TrustedPlotContext | None = None,
    min_valid_fraction: float = 0.70,
) -> S2NativeQAScreen:
    """Fail-closed, read-only structural and pixel QA; never issue a grant.

    This deliberately stops short of state-input authorization even after
    SCREENED_NATIVE_QA, because plot IAM, provider-signature provenance,
    MESIA full support and asymmetric issuer decisions are not here.
    """
    try:
        if type(min_valid_fraction) is not float or not 0.0 < min_valid_fraction <= 1.0:
            return _deny("invalid_qa_policy")
        if (
            not isinstance(scene, SceneProduct) or scene.sensor != "S2"
            or scene.test_override or scene.source_reality != "real_raster"
            or not isinstance(evidence_store, NativeEvidenceStore)
            or not scene.native_catalog_acquisition_id
            or not scene.native_process_acquisition_id
        ):
            return _deny("missing_native_scene_evidence")
        catalog = evidence_store.verified_cache_receipt(scene.native_catalog_acquisition_id)
        process = evidence_store.verified_cache_receipt(scene.native_process_acquisition_id)
        if (
            catalog.sensor != "S2" or process.sensor != "S2"
            or catalog.provider != "sentinel_hub" or process.provider != "sentinel_hub"
            or not catalog.endpoint.endswith("/catalog/v1/search")
            or not process.endpoint.endswith("/process/v1")
            or catalog.origin_class != OriginClass.PROVENANCE_VERIFIED_CACHE
            or process.origin_class != OriginClass.PROVENANCE_VERIFIED_CACHE
            or scene.native_evidence_status not in (
                "CAPTURED_UNQUALIFIED", "PROVENANCE_VERIFIED_CACHE",
            )
            or process.provider_product_id != scene.provider_product_id
            or scene.provider_product_id != scene.catalog_item_id
            or scene.provider_response_hash != process.response_sha256
            or scene.process_request_hash != process.request_sha256
        ):
            return _deny("unbound_catalog_process_capture")

        raw_catalog = evidence_store._path("objects", catalog.object_id).read_bytes()
        raw_process = evidence_store._path("objects", process.object_id).read_bytes()
        catalog_data = json.loads(raw_catalog)
        features = catalog_data.get("features") if isinstance(catalog_data, dict) else None
        if not isinstance(features, list):
            return _deny("invalid_catalog_features")
        matching = [
            f for f in features if isinstance(f, dict)
            and normalize_product_id(f.get("id")) == normalize_product_id(scene.provider_product_id)
        ]
        if len(matching) != 1:
            return _deny("missing_or_ambiguous_catalog_product")
        item = matching[0]
        if item.get("collection") != "sentinel-2-l2a":
            return _deny("wrong_catalog_collection")
        props = item.get("properties")
        if not isinstance(props, dict):
            return _deny("missing_catalog_properties")
        item_time = _time(props.get("datetime"))
        scene_time = scene.acquisition_datetime
        if (
            not isinstance(scene_time, datetime)
            or scene_time.tzinfo is None or scene_time.utcoffset() is None
            or scene_time.astimezone(timezone.utc) != item_time
        ):
            return _deny("catalog_scene_timestamp_mismatch")

        bands, userdata = _read_captured_process(raw_process)
        binding = verify_exact_product_binding(scene.provider_product_id, userdata, "S2")
        if not binding["is_exact"] or scene.product_binding != "exact_catalog_item":
            return _deny("catalog_process_product_mismatch")
        if (
            not isinstance(scene.binding_proof, dict)
            or scene.binding_proof != binding["proof"]
        ):
            return _deny("unmatched_original_process_binding_proof")
        required_shape = (scene.height, scene.width)
        if (
            type(scene.height) is not int or type(scene.width) is not int
            or scene.height < 1 or scene.width < 1
            or scene.height*scene.width > _MAX_PIXELS
            or any(arr.shape != required_shape for arr in bands.values())
        ):
            return _deny("raster_grid_shape_mismatch")
        if _array_hash({name: bands[name] for name in _HASH_BANDS if name in bands}) != scene.content_hash:
            return _deny("scene_raster_content_hash_mismatch")

        # Compare every science-driving pixel to the independently captured
        # TIFF bytes, not only to mutable scene metadata hashes.
        loader = RasterStore()
        for name in _REQUIRED_BANDS + (("B11",) if "B11" in bands else ()):
            ref = scene.band_refs.get(name) or scene.band_refs.get(
                "dataMask" if name == "DATAMASK" else name
            )
            if not isinstance(ref, str) or not ref:
                return _deny("missing_persisted_raster")
            cache_pixels = np.asarray(loader.load_band(ref))
            if (
                cache_pixels.shape != bands[name].shape
                or cache_pixels.dtype != bands[name].dtype
                or not np.array_equal(
                    cache_pixels, bands[name],
                    equal_nan=bool(np.issubdtype(cache_pixels.dtype, np.inexact))
                )
            ):
                return _deny("cached_raster_differs_from_captured_process")

        if (
            scene.crs != "EPSG:4326"
            or not isinstance(scene.transform, tuple)
            or len(scene.transform) != 6
            or any(type(x) not in (int, float) or not math.isfinite(x) for x in scene.transform)
            or abs(scene.transform[2]) > 1e-12 or abs(scene.transform[4]) > 1e-12
            or scene.transform[1] <= 0 or scene.transform[5] >= 0
        ):
            return _deny("unqualified_grid_crs_or_affine")
        red, nir = bands["B04"], bands["B08"]
        scl, dm = bands["SCL"], bands["DATAMASK"]
        if (
            any(not np.issubdtype(a.dtype, np.number) for a in (red,nir,scl,dm))
            or np.any(~np.isfinite(scl)) or np.any(scl != np.floor(scl))
            or np.any((scl < 0) | (scl > 11))
            or np.any(~np.isfinite(dm)) or np.any((dm != 0) & (dm != 1))
        ):
            return _deny("invalid_scl_or_data_mask")

        if trusted_plot is None:
            return S2NativeQAScreen(
                S2ScreenStatus.DEFERRED_SPATIAL_AUTHORITY,
                "trusted_plot_geometry_required",
            )
        ring = _validate_scope(trusted_plot)
        # The context is injected by a server adapter; its authenticity and
        # plot ownership must later be established by the trusted registry.
        x0,y0,x1,y1 = (
            scene.transform[0], scene.transform[3]+scene.height*scene.transform[5],
            scene.transform[0]+scene.width*scene.transform[1], scene.transform[3],
        )
        if any(not (x0-1e-12<=x<=x1+1e-12 and y0-1e-12<=y<=y1+1e-12)
               for x,y in ring):
            return _deny("plot_outside_native_raster_extent")
        inside = _polygon_mask(scene.width,scene.height,scene.transform,ring)
        support_count = int(inside.sum())
        if support_count == 0:
            return _deny("zero_pixel_center_plot_support")
        has_finite_reflectance = (
            np.isfinite(red) & np.isfinite(nir)
            & (red >= 0) & (red <= 1)
            & (nir >= 0) & (nir <= 1)
        )
        clear = ((dm == 1) & ~np.isin(scl,list(_INVALID_SCL))
                 & has_finite_reflectance)
        valid_count = int((clear & inside).sum())
        valid_fraction = valid_count/support_count
        if valid_fraction < min_valid_fraction:
            return _deny("insufficient_masked_plot_pixel_quality")
        if any(
            scene.band_units.get(b) != "reflectance" for b in ("B04", "B08")
        ):
            return _deny("unqualified_reflectance_units")
        ndvi_values = (nir[clear & inside]-red[clear & inside]) / (
            nir[clear & inside]+red[clear & inside]+1e-12
        )
        if not np.all(np.isfinite(ndvi_values)):
            return _deny("invalid_native_ndvi")
        mean_ndvi = float(np.mean(ndvi_values))
        metrics = {
            "valid_fraction": valid_fraction,
            "plot_pixel_centers": support_count,
            "valid_pixel_centers": valid_count,
            "ndvi_mean": mean_ndvi,
            "support_method": "EPSG4326_PIXEL_CENTER_SAMPLE_ONLY",
            "raster_sha256": scene.content_hash,
        }
        proof = {
            "domain": QUALIFIER_DOMAIN,
            "catalog_acquisition_id": catalog.acquisition_id,
            "process_acquisition_id": process.acquisition_id,
            "product_id": scene.provider_product_id,
            "catalog_datetime_utc": item_time.isoformat(),
            "binding_userdata_hash": binding["proof"]["process_userdata_hash"],
            "plot_id": trusted_plot.plot_id,
            "geometry_hash": trusted_plot.geometry_hash,
            "geometry_version": trusted_plot.geometry_version,
            "crs": scene.crs,
            "transform": list(scene.transform),
            "shape": [scene.height, scene.width],
            "quality_policy": {
                "schema": QUALIFIER_DOMAIN,
                "min_valid_fraction": min_valid_fraction,
                "invalid_scl_classes": sorted(_INVALID_SCL),
            },
            "metrics": metrics,
        }
        return S2NativeQAScreen(
            status=S2ScreenStatus.SCREENED_NATIVE_QA,
            reason="bounded_native_pixel_qa_pass_not_state_authority",
            proof_hash=hashlib.sha256(_canonical(proof)).hexdigest(),
            diagnostic_metrics=metrics,
        )
    except (NativeEvidenceError, OSError, ValueError, TypeError, KeyError,
            AttributeError, OverflowError, tarfile.TarError) as exc:
        return _deny(
            "invalid_or_unverifiable_native_scene_evidence"
            if not isinstance(exc, NativeEvidenceError) else str(exc)
        )
