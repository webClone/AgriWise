"""B2B-05: non-authorizing plot ownership and area-exact spatial support boundary.

An upstream authenticated principal and an independently queried ownership
resolver are REQUIRED.  Request metadata is never an authority source.
Geometry is resolved from the authoritative plot record, never a packet.
This module does NOT issue provider, Kalman, MESIA or prescription grants.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any


CONTRACT_VERSION = "akaloris/layer0/b2b05/spatial-tenant/v1"
_FULL_COVERAGE_EPS = 1e-9


class SpatialTenantDenied(ValueError):
    """Fail-closed admission; callers should not expose owner details."""


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    tenant_id: str
    subject_id: str
    authenticated: bool = False


@dataclass(frozen=True)
class ScopedPlotRequest:
    tenant_id: str
    plot_id: str
    geometry_hash: str
    geometry_version: int


@dataclass(frozen=True)
class PlotOwnershipRecord:
    """Only a trusted store adapter may provide this, NEVER a request body."""
    tenant_id: str
    plot_id: str
    geometry_version: int
    geometry_hash: str
    polygon_geojson: Mapping[str, Any]


@dataclass(frozen=True)
class VerifiedPlotScope:
    tenant_id: str
    plot_id: str
    geometry_version: int
    geometry_hash: str
    geometry_json: str  # immutable canonical geometry snapshot
    scope_hash: str
    contract_version: str = CONTRACT_VERSION
    source_qualified: bool = False
    eligible_for_state_grant: bool = False


@dataclass(frozen=True)
class FractionalPixelSupport:
    scope_hash: str
    footprint_hash: str
    containment_fraction: float
    interior_area_m2: float
    footprint_area_m2: float
    external_area_m2: float
    classification: str
    geometry_support_verified: bool
    source_qualified: bool = False
    eligible_for_state_grant: bool = False


def _identity(value: Any) -> bool:
    return isinstance(value, str) and 0 < len(value) <= 256 and value.strip() == value


def _validate_geometry(geojson: Any):
    """Reject malformed, foreign-CRS, oversized and ambiguous polygons."""
    from shapely.geometry import shape

    if not isinstance(geojson, Mapping) or geojson.get("type") not in ("Polygon", "MultiPolygon"):
        raise SpatialTenantDenied("unsupported_plot_geometry")

    def walk(coords):
        if not isinstance(coords, (list, tuple)) or not coords:
            raise SpatialTenantDenied("invalid_polygon_coordinates")
        if isinstance(coords[0], (int, float)):
            if len(coords) != 2 or any(isinstance(v, bool) or not math.isfinite(v) for v in coords):
                raise SpatialTenantDenied("invalid_polygon_coordinates")
            lon, lat = coords
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                raise SpatialTenantDenied("coordinate_out_of_wgs84_range")
            return
        for part in coords:
            walk(part)

    walk(geojson.get("coordinates"))
    try:
        geom = shape(geojson)
        bounds = geom.bounds
        if (
            geom.is_empty or not geom.is_valid or geom.area <= 0
            or len(bounds) != 4 or not all(map(math.isfinite, bounds))
            or bounds[2] - bounds[0] >= 5.0
            or bounds[3] - bounds[1] >= 5.0
        ):
            raise SpatialTenantDenied("invalid_or_unsupported_polygon")
        return geom
    except SpatialTenantDenied:
        raise
    except Exception:
        raise SpatialTenantDenied("invalid_or_unsupported_polygon") from None


def _geometry_json(geometry: Any) -> str:
    from shapely.geometry import mapping
    return json.dumps(
        mapping(geometry), sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def normalize_plot_polygon(geojson: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve stored GeoJSON Feature or geometry into canonical WGS84 polygon.

    Explicit foreign CRS declarations fail closed. Geometry hash deliberately
    excludes unrelated Feature properties while retaining the original
    GeoJSON container in the application database.
    """
    if not isinstance(geojson, Mapping) or geojson.get("crs") is not None:
        raise SpatialTenantDenied("invalid_or_foreign_geometry_crs")
    candidate = geojson
    if geojson.get("type") == "Feature":
        candidate = geojson.get("geometry")
    if not isinstance(candidate, Mapping) or candidate.get("crs") is not None:
        raise SpatialTenantDenied("invalid_or_foreign_geometry_crs")
    geom = _validate_geometry(candidate)
    return json.loads(_geometry_json(geom))


def canonical_geometry_hash(polygon_geojson: Mapping[str, Any]) -> str:
    """Stable digest of canonical stored geometry; NOT a signature/ownership proof."""
    geom = _validate_geometry(normalize_plot_polygon(polygon_geojson))
    return hashlib.sha256(
        (CONTRACT_VERSION + "\x00" + _geometry_json(geom)).encode("utf-8")
    ).hexdigest()


def authorize_plot_scope(
    principal: AuthenticatedPrincipal,
    request: ScopedPlotRequest,
    ownership_resolver: Callable[[str], PlotOwnershipRecord | None],
) -> VerifiedPlotScope:
    """Resolve plot ownership from a trusted store and bind exact geometry epoch.

    The resolver must query the authoritative database, not user-controlled
    request fields.  An authenticated principal must be supplied by upstream
    IAM middleware, not constructed from client JSON.
    """
    if (
        not isinstance(principal, AuthenticatedPrincipal)
        or principal.authenticated is not True
        or not _identity(principal.tenant_id)
        or not _identity(principal.subject_id)
        or not isinstance(request, ScopedPlotRequest)
        or not all(_identity(x) for x in (request.tenant_id, request.plot_id))
        or principal.tenant_id != request.tenant_id
        or type(request.geometry_version) is not int
        or request.geometry_version <= 0
    ):
        raise SpatialTenantDenied("plot_scope_denied")
    if not callable(ownership_resolver):
        raise SpatialTenantDenied("trusted_ownership_resolver_required")
    try:
        record = ownership_resolver(request.plot_id)
    except Exception:
        raise SpatialTenantDenied("plot_scope_denied") from None
    if (
        not isinstance(record, PlotOwnershipRecord)
        or record.tenant_id != principal.tenant_id
        or record.plot_id != request.plot_id
        or type(record.geometry_version) is not int
        or record.geometry_version != request.geometry_version
        or not isinstance(record.geometry_hash, str)
    ):
        raise SpatialTenantDenied("plot_scope_denied")

    geom = _validate_geometry(record.polygon_geojson)
    geometry_json = _geometry_json(geom)
    actual_hash = hashlib.sha256(
        (CONTRACT_VERSION + "\x00" + geometry_json).encode("utf-8")
    ).hexdigest()
    if record.geometry_hash != actual_hash or request.geometry_hash != actual_hash:
        raise SpatialTenantDenied("untrusted_or_stale_geometry_epoch")

    material = {
        "contract": CONTRACT_VERSION,
        "tenant_id": record.tenant_id,
        "plot_id": record.plot_id,
        "geometry_hash": actual_hash,
        "geometry_version": record.geometry_version,
    }
    scope_hash = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return VerifiedPlotScope(
        tenant_id=record.tenant_id, plot_id=record.plot_id,
        geometry_version=record.geometry_version,
        geometry_hash=actual_hash, geometry_json=geometry_json,
        scope_hash=scope_hash,
    )


def verify_pixel_footprint(
    scope: VerifiedPlotScope,
    pixel_footprint_geojson: Mapping[str, Any],
) -> FractionalPixelSupport:
    """Compute real polygon intersection, never point snapping / center inclusion.

    Uses a local WGS84 Lambert azimuthal equal-area projection via rasterio/GDAL.
    The result is fractional *geometric* support, not a radio sensitivity proof,
    a source qualification or permission to update state.
    """
    if (
        not isinstance(scope, VerifiedPlotScope)
        or scope.contract_version != CONTRACT_VERSION
        or scope.source_qualified is not False
        or scope.eligible_for_state_grant is not False
    ):
        raise SpatialTenantDenied("invalid_plot_scope")
    try:
        from shapely.geometry import shape, mapping
        from rasterio.crs import CRS
        from rasterio.warp import transform_geom
        plot = _validate_geometry(json.loads(scope.geometry_json))
        pixel = _validate_geometry(pixel_footprint_geojson)
        if hashlib.sha256(
            (CONTRACT_VERSION + "\x00" + scope.geometry_json).encode()
        ).hexdigest() != scope.geometry_hash:
            raise SpatialTenantDenied("scope_geometry_hash_mismatch")

        center = plot.representative_point()
        local_crs = CRS.from_proj4(
            f"+proj=laea +lat_0={center.y:.9f} +lon_0={center.x:.9f} "
            "+datum=WGS84 +units=m +no_defs"
        )
        proj_plot = shape(transform_geom("EPSG:4326", local_crs, mapping(plot), precision=9))
        proj_pixel = shape(transform_geom("EPSG:4326", local_crs, mapping(pixel), precision=9))
        area = proj_pixel.area
        if not math.isfinite(area) or area <= 0:
            raise SpatialTenantDenied("invalid_projected_pixel_footprint")
        inside = proj_plot.intersection(proj_pixel).area
        if not math.isfinite(inside):
            raise SpatialTenantDenied("invalid_projected_intersection")
        inside = min(area, max(0.0, inside))
        outside = max(0.0, area - inside)
        fraction = inside / area
        classification = (
            "FULL_CONTAINED" if fraction >= 1.0 - _FULL_COVERAGE_EPS
            else "FRACTIONAL_BOUNDARY" if fraction > _FULL_COVERAGE_EPS
            else "EXTERNAL_QUARANTINE"
        )
        return FractionalPixelSupport(
            scope_hash=scope.scope_hash,
            footprint_hash=canonical_geometry_hash(pixel_footprint_geojson),
            containment_fraction=fraction,
            interior_area_m2=inside,
            footprint_area_m2=area,
            external_area_m2=outside,
            classification=classification,
            geometry_support_verified=classification == "FULL_CONTAINED",
        )
    except SpatialTenantDenied:
        raise
    except Exception:
        raise SpatialTenantDenied("pixel_spatial_support_unavailable") from None


def package_spatial_provenance(
    scope: VerifiedPlotScope,
    support: FractionalPixelSupport,
    *,
    claimed_source_evidence_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Non-authorizing envelope: references are claims until separately attested."""
    if (
        not isinstance(scope, VerifiedPlotScope)
        or not isinstance(support, FractionalPixelSupport)
        or scope.scope_hash != support.scope_hash
        or scope.source_qualified is not False
        or support.source_qualified is not False
        or support.eligible_for_state_grant is not False
    ):
        raise SpatialTenantDenied("spatial_provenance_scope_mismatch")
    if (
        isinstance(claimed_source_evidence_ids, (str, bytes))
        or not isinstance(claimed_source_evidence_ids, Sequence)
        or any(not _identity(x) for x in claimed_source_evidence_ids)
    ):
        raise SpatialTenantDenied("invalid_source_evidence_refs")
    return {
        "contract_version": CONTRACT_VERSION,
        "tenant_id": scope.tenant_id,
        "plot_id": scope.plot_id,
        "geometry_hash": scope.geometry_hash,
        "geometry_version": scope.geometry_version,
        "scope_hash": scope.scope_hash,
        "footprint_hash": support.footprint_hash,
        "pixel_interior_fraction": support.containment_fraction,
        "spatial_classification": support.classification,
        "geometry_support_verified": support.geometry_support_verified,
        "claimed_source_evidence_ids": sorted(set(claimed_source_evidence_ids)),
        "source_qualified": False,
        "eligible_for_state_grant": False,
        "authority": "spatial_diagnostic_only",
    }
