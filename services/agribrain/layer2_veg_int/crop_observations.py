"""Canonical field-crop observations derived from physical Sentinel-2 scenes.

This module is deliberately upstream of crop inference.  It converts one
provider acquisition into one QA-admitted, plot-scoped observation and keeps
provider processing products as lineage rather than independent evidence.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np

try:
    from scientific_contracts.crop_evidence import (
        CROP_OBSERVATION_CONTRACT_VERSION,
        CanonicalCropObservationV2,
        CropEvidenceLedgerV2,
    )
except ModuleNotFoundError:  # package-qualified test/import mode
    from services.agribrain.scientific_contracts.crop_evidence import (
        CROP_OBSERVATION_CONTRACT_VERSION,
        CanonicalCropObservationV2,
        CropEvidenceLedgerV2,
    )


_S2_PRODUCT_RE = re.compile(
    r"(?P<mission>S2[A-Z])_MSIL\w+_"
    r"(?P<sensing>\d{8}T\d{6})_"
    r"(?P<baseline>N\d{4})_"
    r"(?P<orbit>R\d{3})_"
    r"(?P<tile>T\d{2}[A-Z]{3})_"
    r"(?P<processing>\d{8}T\d{6})",
    re.IGNORECASE,
)

_S1_PRODUCT_RE = re.compile(
    r"(?P<mission>S1[A-Z])_[A-Z0-9]+_[A-Z0-9]+_[A-Z0-9]+_"
    r"(?P<sensing>\d{8}T\d{6})_"
    r"(?P<stop>\d{8}T\d{6})_"
    r"(?P<absolute_orbit>\d{6})_",
    re.IGNORECASE,
)

_REFLECTANCE_BANDS = (
    "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B11", "B12",
)
_REQUIRED_BANDS = ("B04", "B08")
_CLEAR_CROP_SCL = (4, 5)
_CLOUD_SCL = (7, 8, 9, 10)
_SHADOW_SCL = (2, 3)
_SNOW_SCL = (11,)
_ACCEPTED_REFLECTANCE_UNITS = {
    "reflectance", "reflectance_0_1", "unitless_reflectance", "surface_reflectance",
    "scaled_0_10000",
}
_S1_DB_UNITS = frozenset({
    "db", "decibel", "decibels", "sigma0_db", "gamma0_db", "db_sigma0",
    "db_gamma0",
})
_S1_LINEAR_POWER_UNITS = frozenset({
    # Bare ``sigma0``/``gamma0`` are deliberately excluded: providers use
    # those labels for both linear and logarithmic products, so they do not
    # prove the conversion direction.
    "linear_power", "linear_sigma0", "linear_gamma0",
})


def _mapping(value: Any) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "__dict__"):
        return {
            key: item for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return {}


def _iso_provider_time(value: str) -> str:
    parsed = datetime.strptime(value.upper(), "%Y%m%dT%H%M%S")
    return parsed.replace(tzinfo=timezone.utc).isoformat()


def _canonical_mission(value: Any) -> str:
    raw = re.sub(r"[^A-Z0-9]", "", str(value or "").upper())
    match = re.search(r"(?:SENTINEL)?2([A-Z])$", raw)
    return f"S2{match.group(1)}" if match else raw


def _canonical_orbit(value: Any) -> str:
    raw = str(value or "").strip().upper()
    match = re.fullmatch(r"R?(\d+)", raw)
    return f"R{int(match.group(1)):03d}" if match else raw


def _canonical_tile(value: Any) -> str:
    raw = str(value or "").strip().upper()
    if raw and not raw.startswith("T") and re.fullmatch(r"\d{2}[A-Z]{3}", raw):
        raw = "T" + raw
    return raw


def sentinel2_physical_identity(
    metadata: Mapping[str, Any], *, geometry_hash: str = "",
    plot_namespace: Any = None,
) -> Dict[str, Any]:
    """Return acquisition identity independent of provider processing version."""
    product_id = str(
        metadata.get("provider_product_id")
        or metadata.get("catalog_item_id")
        or metadata.get("scene_id")
        or ""
    )
    match = _S2_PRODUCT_RE.search(product_id)
    # A parseable provider product id is the primary identity authority.  It
    # avoids metadata spelling variants (Sentinel-2B/S2B, 108/R108) splitting
    # one physical pass into multiple observations.
    mission = _canonical_mission(
        match.group("mission") if match else metadata.get("mission")
    )
    sensing = (
        _iso_provider_time(match.group("sensing")) if match else
        metadata.get("sensing_timestamp") or metadata.get("sensing_datetime")
    )
    if isinstance(sensing, datetime):
        if sensing.tzinfo is None:
            sensing = sensing.replace(tzinfo=timezone.utc)
        sensing = sensing.astimezone(timezone.utc).isoformat()
    elif sensing:
        try:
            parsed = datetime.fromisoformat(str(sensing).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            sensing = parsed.astimezone(timezone.utc).isoformat()
        except ValueError:
            sensing = str(sensing)
    tile = _canonical_tile(
        match.group("tile") if match else
        metadata.get("mgrs_tile_id") or metadata.get("tile_id")
    )
    orbit = _canonical_orbit(
        match.group("orbit") if match else
        metadata.get("relative_orbit") or metadata.get("orbit_number")
    )
    geometry = str(
        geometry_hash or metadata.get("plot_geometry_hash")
        or metadata.get("geometry_hash") or ""
    )
    namespace_value = plot_namespace or metadata.get("plot_namespace") or {
        "tenant_id": metadata.get("tenant_id"),
        "farm_id": metadata.get("farm_id"),
        "plot_id": metadata.get("plot_id"),
    }
    namespace = _mapping(namespace_value)
    normalized_namespace = {
        key: str(namespace.get(key) or "").strip()
        for key in ("tenant_id", "farm_id", "plot_id")
    }
    processing_timestamp = (
        _iso_provider_time(match.group("processing")) if match else
        metadata.get("processing_timestamp")
    )
    processing_baseline = (
        match.group("baseline").upper() if match else metadata.get("processing_baseline")
    )
    complete = all((mission, sensing, tile, orbit, geometry)) and all(
        normalized_namespace.values()
    )
    physical = {
        "mission": mission or None,
        "sensing_timestamp": sensing or None,
        "tile_id": tile or None,
        "relative_orbit": orbit or None,
        "plot_geometry_hash": geometry or None,
        "plot_namespace": normalized_namespace,
    }
    physical_key = None
    if complete:
        encoded = json.dumps(
            physical, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ).encode("utf-8")
        # Keep the complete SHA-256 digest.  Truncation is unnecessary here and
        # weakens a key that is used as scientific independence identity.
        physical_key = "S2ACQ-" + hashlib.sha256(encoded).hexdigest()
    return {
        **physical,
        "physical_identity_complete": complete,
        "physical_acquisition_key": physical_key,
        "processing_timestamp": processing_timestamp,
        "processing_baseline": processing_baseline,
    }


def _canonical_s1_mission(value: Any) -> str:
    raw = re.sub(r"[^A-Z0-9]", "", str(value or "").upper())
    match = re.search(r"(?:SENTINEL)?1([A-Z])$", raw)
    return f"S1{match.group(1)}" if match else raw


def _canonical_s1_orbit_pass(value: Any) -> str:
    normalized = str(value or "").strip().upper()
    aliases = {
        "ASC": "ASCENDING", "A": "ASCENDING",
        "DES": "DESCENDING", "DESC": "DESCENDING", "D": "DESCENDING",
    }
    return aliases.get(normalized, normalized) if normalized else ""


def _canonical_s1_relative_orbit(value: Any) -> str:
    canonical = _canonical_orbit(value)
    match = re.fullmatch(r"R(\d{3})", canonical)
    if not match:
        return ""
    number = int(match.group(1))
    return canonical if 1 <= number <= 175 else ""


def _metadata_records(value: Any) -> List[Mapping[str, Any]]:
    """Flatten provider metadata envelopes without inventing field values."""
    records: List[Mapping[str, Any]] = []
    pending: List[Any] = [value]
    seen: set[int] = set()
    while pending:
        current = pending.pop(0)
        if isinstance(current, Mapping):
            marker = id(current)
            if marker in seen:
                continue
            seen.add(marker)
            records.append(current)
            for key in (
                "userData", "userdata", "tiles", "properties", "metadata",
                "process_metadata", "process_api_metadata", "catalog_metadata",
                "stac_metadata", "official_product_identity",
            ):
                nested = current.get(key)
                if isinstance(nested, (Mapping, list, tuple)):
                    pending.append(nested)
        elif isinstance(current, (list, tuple)):
            pending.extend(current)
    return records


def _first_metadata_value(
    records: Iterable[Mapping[str, Any]], aliases: Sequence[str],
) -> Any:
    for record in records:
        for alias in aliases:
            value = record.get(alias)
            if value not in (None, ""):
                return value
    return None


def _canonical_timestamp(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        parsed = value
    elif value not in (None, ""):
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _resolve_s1_metadata_value(
    tiers: Sequence[Tuple[str, Sequence[Mapping[str, Any]]]],
    aliases: Sequence[str],
    normalizer: Any,
    validator: Any,
) -> Tuple[Any, Optional[str]]:
    """Resolve the first *valid* value in the S1 authority hierarchy.

    A malformed Process API field is not evidence and must not suppress a
    valid Catalog/STAC value.  Values are therefore normalized and validated
    within each tier before the resolver falls through to the next source.
    """
    for source_name, records in tiers:
        for record in records:
            for alias in aliases:
                raw = record.get(alias)
                if raw in (None, ""):
                    continue
                normalized = normalizer(raw)
                if validator(normalized):
                    return normalized, source_name
    return None, None


def sentinel1_physical_identity(
    metadata: Mapping[str, Any], *, geometry_hash: str = "",
    plot_namespace: Any = None,
) -> Dict[str, Any]:
    """Return a fail-closed S1 pass identity with explicit source precedence.

    Identity fields resolve from Process API metadata first, Catalog/STAC
    metadata second, and official product identity last.  A SAFE product name
    can prove mission and sensing time, but it cannot prove orbit direction or
    relative orbit; those two fields therefore remain mandatory metadata.
    """
    product_id = str(
        metadata.get("official_product_id")
        or metadata.get("provider_product_id")
        or metadata.get("catalog_item_id")
        or metadata.get("scene_id")
        or ""
    )
    match = _S1_PRODUCT_RE.search(product_id)
    process_envelopes = [
        metadata.get(key) for key in (
            "process_metadata", "process_api_metadata", "process_userdata",
            "provider_process_metadata",
        ) if metadata.get(key) not in (None, "")
    ]
    # These normalized provider fields are emitted from Process API userdata
    # by the Layer-0 exact-binding adapter and retain highest precedence.
    process_records = [{
        "mission": metadata.get("process_mission"),
        "sensing_timestamp": metadata.get("process_sensing_timestamp"),
        "relative_orbit": (
            metadata.get("provider_relative_orbit")
            or metadata.get("process_relative_orbit")
        ),
        "orbit_pass": metadata.get("provider_orbit_pass"),
    }]
    for envelope in process_envelopes:
        process_records.extend(_metadata_records(envelope))
    catalog_records: List[Mapping[str, Any]] = []
    for key in (
        "catalog_metadata", "catalog_properties", "stac_metadata",
        "stac_properties",
    ):
        value = metadata.get(key)
        if value not in (None, ""):
            catalog_records.extend(_metadata_records(value))
    catalog_records.append(metadata)
    official_records: List[Mapping[str, Any]] = []
    for key in ("official_product_identity", "product_identity"):
        value = metadata.get(key)
        if value not in (None, ""):
            official_records.extend(_metadata_records(value))

    mission_aliases = (
        "mission", "platform", "satellite", "spacecraftName",
        "platformShortName", "constellation",
    )
    sensing_aliases = (
        "sensing_timestamp", "sensing_datetime", "acquisition_datetime",
        "datetime", "timestamp", "date",
    )
    relative_orbit_aliases = (
        "relative_orbit", "relative_orbit_number", "relativeOrbitNumber",
        "sat:relative_orbit", "s1:relative_orbit",
    )
    pass_aliases = (
        "orbit_pass", "orbit_direction", "orbitDirection", "orbitPass",
        "sat:orbit_state", "s1:orbit_state",
    )

    official_product_records = list(official_records)
    if match:
        official_product_records.append({
            "mission": match.group("mission"),
            "sensing_timestamp": _iso_provider_time(match.group("sensing")),
        })
    tiers = (
        ("process_metadata", tuple(process_records)),
        ("catalog_stac_metadata", tuple(catalog_records)),
        ("official_product_fields", tuple(official_product_records)),
    )
    mission, mission_source = _resolve_s1_metadata_value(
        tiers, mission_aliases, _canonical_s1_mission,
        lambda value: value in {"S1A", "S1B", "S1C", "S1D"},
    )
    sensing, sensing_source = _resolve_s1_metadata_value(
        tiers, sensing_aliases, _canonical_timestamp, bool,
    )
    orbit_reference, relative_orbit_source = _resolve_s1_metadata_value(
        tiers, relative_orbit_aliases, _canonical_s1_relative_orbit, bool,
    )
    orbit_reference = orbit_reference or ""
    orbit_reference_kind = "relative_orbit" if orbit_reference else None

    orbit_pass, orbit_pass_source = _resolve_s1_metadata_value(
        tiers, pass_aliases, _canonical_s1_orbit_pass,
        lambda value: value in {"ASCENDING", "DESCENDING"},
    )
    orbit_pass = orbit_pass or ""
    geometry = str(
        geometry_hash or metadata.get("plot_geometry_hash")
        or metadata.get("geometry_hash") or ""
    ).strip()
    namespace_value = plot_namespace or metadata.get("plot_namespace") or {
        "tenant_id": metadata.get("tenant_id"),
        "farm_id": metadata.get("farm_id"),
        "plot_id": metadata.get("plot_id"),
    }
    namespace = _mapping(namespace_value)
    normalized_namespace = {
        key: str(namespace.get(key) or "").strip()
        for key in ("tenant_id", "farm_id", "plot_id")
    }
    pass_valid = orbit_pass in {"ASCENDING", "DESCENDING"}
    complete = bool(
        mission in {"S1A", "S1B", "S1C", "S1D"}
        and sensing and orbit_reference and pass_valid and geometry
        and all(normalized_namespace.values())
    )
    physical = {
        "mission": mission or None,
        "sensing_timestamp": sensing or None,
        "orbit_reference_kind": orbit_reference_kind,
        "orbit_reference": orbit_reference or None,
        "orbit_pass": orbit_pass or None,
        "plot_geometry_hash": geometry or None,
        "plot_namespace": normalized_namespace,
    }
    physical_key = None
    if complete:
        encoded = json.dumps(
            physical, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ).encode("utf-8")
        physical_key = "S1ACQ-" + hashlib.sha256(encoded).hexdigest()
    return {
        **physical,
        "relative_orbit": (
            orbit_reference if orbit_reference_kind == "relative_orbit" else None
        ),
        "provider_orbit_id": metadata.get("provider_orbit_id"),
        "provider_orbit_pass": metadata.get("provider_orbit_pass"),
        "identity_resolution": {
            "mission_source": mission_source,
            "sensing_source": sensing_source,
            "relative_orbit_source": relative_orbit_source,
            "orbit_pass_source": orbit_pass_source,
        },
        "physical_identity_complete": complete,
        "physical_acquisition_key": physical_key,
        "processing_timestamp": _canonical_timestamp(
            metadata.get("processing_timestamp")
        ),
        "processing_baseline": metadata.get("processing_baseline"),
    }


def _normalize_band_key(name: Any) -> str:
    key = str(name or "").strip().upper().replace("DATA_MASK", "DATAMASK")
    return "DATAMASK" if key == "DATAMASK" else key


def _load_np_array(path: str) -> np.ndarray:
    payload = np.load(path, allow_pickle=False)
    try:
        if isinstance(payload, np.lib.npyio.NpzFile):
            if "data" not in payload.files:
                raise KeyError(f"missing data array in {path}")
            array = payload["data"]
        else:
            array = payload
    finally:
        if isinstance(payload, np.lib.npyio.NpzFile):
            payload.close()
    if np.asarray(array).dtype == object:
        raise ValueError("object arrays are forbidden")
    return np.asarray(array)


def _load_scene_arrays(package: Any) -> Tuple[Dict[str, np.ndarray], List[str]]:
    package_map = _mapping(package)
    arrays: Dict[str, np.ndarray] = {}
    errors: List[str] = []
    raw_arrays = package_map.get("band_arrays") or getattr(package, "band_arrays", None)
    if isinstance(raw_arrays, Mapping):
        for name, value in raw_arrays.items():
            if value is None:
                continue
            key = _normalize_band_key(name)
            try:
                array = np.asarray(value)
                if array.dtype == object:
                    raise ValueError("object arrays are forbidden")
                arrays[key] = array
            except (TypeError, ValueError):
                errors.append(f"invalid_array:{key}")

    refs: Dict[str, Any] = {}
    for candidate in (
        package_map.get("local_cache_refs"), package_map.get("band_refs"),
        package_map.get("mask_refs"), getattr(package, "local_cache_refs", None),
        getattr(package, "mask_refs", None),
    ):
        if isinstance(candidate, Mapping):
            refs.update({_normalize_band_key(key): value for key, value in candidate.items()})
    for key, path in refs.items():
        if key in arrays or not path:
            continue
        try:
            arrays[key] = _load_np_array(os.fspath(path))
        except (OSError, KeyError, TypeError, ValueError):
            errors.append(f"unreadable_array:{key}")
    return arrays, sorted(set(errors))


def _geometry_ring(value: Any) -> List[Tuple[float, float]]:
    if isinstance(value, Mapping):
        if value.get("type") == "Feature":
            return _geometry_ring(value.get("geometry"))
        if str(value.get("type") or "").lower() in {"polygon", "multipolygon"}:
            return _geometry_ring(value.get("coordinates"))
        if "lng" in value and "lat" in value:
            return [(float(value["lng"]), float(value["lat"]))]
        if "lon" in value and "lat" in value:
            return [(float(value["lon"]), float(value["lat"]))]
        for key in ("polygon_coords", "coordinates", "geometry"):
            if key in value:
                ring = _geometry_ring(value[key])
                if ring:
                    return ring
        return []
    if not isinstance(value, (list, tuple)) or not value:
        return []
    if all(isinstance(item, Mapping) for item in value):
        ring: List[Tuple[float, float]] = []
        for item in value:
            ring.extend(_geometry_ring(item))
        return ring
    if (
        len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    ):
        return [(float(value[0]), float(value[1]))]
    if all(
        isinstance(item, (list, tuple))
        and len(item) >= 2
        and isinstance(item[0], (int, float))
        and isinstance(item[1], (int, float))
        for item in value
    ):
        return [(float(item[0]), float(item[1])) for item in value]
    for item in value:
        ring = _geometry_ring(item)
        if len(ring) >= 3:
            return ring
    return []


def _geometry_polygons(
    value: Any,
) -> List[Tuple[List[Tuple[float, float]], List[List[Tuple[float, float]]]]]:
    """Normalize GeoJSON/legacy plot geometry without dropping holes or parts."""
    if isinstance(value, Mapping):
        geometry_type = str(value.get("type") or "").lower()
        if geometry_type == "feature":
            return _geometry_polygons(value.get("geometry"))
        coordinates = value.get("coordinates")
        if geometry_type == "polygon" and isinstance(coordinates, (list, tuple)):
            rings = [_geometry_ring(item) for item in coordinates]
            if rings and len(rings[0]) >= 3:
                return [(rings[0], [ring for ring in rings[1:] if len(ring) >= 3])]
            return []
        if geometry_type == "multipolygon" and isinstance(coordinates, (list, tuple)):
            polygons = []
            for coordinate_set in coordinates:
                polygons.extend(_geometry_polygons({
                    "type": "Polygon", "coordinates": coordinate_set,
                }))
            return polygons
        for key in ("polygon_coords", "geometry"):
            if key in value:
                polygons = _geometry_polygons(value[key])
                if polygons:
                    return polygons
        return []
    ring = _geometry_ring(value)
    return [(ring, [])] if len(ring) >= 3 else []


def _ring_mask(
    ring: Sequence[Tuple[float, float]], x: np.ndarray, y: np.ndarray,
) -> np.ndarray:
    inside = np.zeros(x.shape, dtype=bool)
    points = list(ring) + ([ring[0]] if ring[0] != ring[-1] else [])
    for (xi, yi), (xj, yj) in zip(points, points[1:]):
        crosses = (yi > y) != (yj > y)
        boundary_x = (xj - xi) * (y - yi) / ((yj - yi) or 1e-15) + xi
        inside ^= crosses & (x < boundary_x)
    return inside


def _canonical_crs(value: Any) -> Optional[str]:
    if isinstance(value, Mapping):
        value = (
            value.get("name")
            or _mapping(value.get("properties")).get("name")
            or value.get("code")
        )
    raw = str(value or "").strip().upper().replace(" ", "")
    if not raw:
        return None
    epsg = re.search(r"EPSG(?::|::|/)(\d+)$", raw)
    if epsg:
        return f"EPSG:{int(epsg.group(1))}"
    if raw.isdigit():
        return f"EPSG:{int(raw)}"
    return raw


def _plot_geometry_crs(plot_geometry: Any, explicit_crs: Any) -> Optional[str]:
    if explicit_crs:
        return _canonical_crs(explicit_crs)
    if isinstance(plot_geometry, Mapping):
        if plot_geometry.get("crs"):
            return _canonical_crs(plot_geometry.get("crs"))
        geometry = plot_geometry.get("geometry")
        if isinstance(geometry, Mapping) and geometry.get("crs"):
            return _canonical_crs(geometry.get("crs"))
        # RFC 7946 GeoJSON coordinates are WGS84 longitude/latitude.
        if str(plot_geometry.get("type") or "").lower() in {
            "feature", "polygon", "multipolygon",
        }:
            return "EPSG:4326"
    return None


def _plot_mask(
    shape: Tuple[int, int], transform: Any, plot_geometry: Any, *,
    scene_crs: Any, plot_geometry_crs: Any,
) -> Tuple[np.ndarray, str, Optional[str], Optional[str]]:
    scene_crs_norm = _canonical_crs(scene_crs)
    geometry_crs_norm = _plot_geometry_crs(plot_geometry, plot_geometry_crs)
    polygons = _geometry_polygons(plot_geometry)
    if not polygons:
        return (
            np.zeros(shape, dtype=bool), "missing_plot_geometry",
            scene_crs_norm, geometry_crs_norm,
        )
    if scene_crs_norm is None:
        return np.zeros(shape, dtype=bool), "missing_scene_crs", None, geometry_crs_norm
    if geometry_crs_norm is None:
        return np.zeros(shape, dtype=bool), "missing_plot_geometry_crs", scene_crs_norm, None
    if scene_crs_norm != geometry_crs_norm:
        return (
            np.zeros(shape, dtype=bool), "plot_scene_crs_mismatch",
            scene_crs_norm, geometry_crs_norm,
        )
    if not isinstance(transform, (list, tuple)) or len(transform) != 6:
        return np.zeros(shape, dtype=bool), "invalid_transform", scene_crs_norm, geometry_crs_norm
    gt = tuple(float(value) for value in transform)
    rows, cols = np.indices(shape, dtype=float)
    x = gt[0] + (cols + 0.5) * gt[1] + (rows + 0.5) * gt[2]
    y = gt[3] + (cols + 0.5) * gt[4] + (rows + 0.5) * gt[5]
    inside = np.zeros(shape, dtype=bool)
    for exterior, holes in polygons:
        polygon_mask = _ring_mask(exterior, x, y)
        for hole in holes:
            polygon_mask &= ~_ring_mask(hole, x, y)
        inside |= polygon_mask
    return inside, "plot_polygon_gdal_affine", scene_crs_norm, geometry_crs_norm


def _band_scale(unit: Any) -> Optional[float]:
    normalized = str(unit or "").strip().lower()
    if normalized not in _ACCEPTED_REFLECTANCE_UNITS:
        return None
    return 1.0 / 10000.0 if normalized == "scaled_0_10000" else 1.0


def _stats(values: np.ndarray, support: np.ndarray) -> Dict[str, float]:
    selected = np.asarray(values, dtype=np.float64)[support]
    selected = selected[np.isfinite(selected)]
    if selected.size == 0:
        return {}
    return {
        "valid_count": int(selected.size),
        "mean": round(float(np.mean(selected)), 6),
        "median": round(float(np.median(selected)), 6),
        "std": round(float(np.std(selected)), 6),
        "variance": round(float(np.var(selected)), 6),
        "p10": round(float(np.quantile(selected, 0.10)), 6),
        "p25": round(float(np.quantile(selected, 0.25)), 6),
        "p75": round(float(np.quantile(selected, 0.75)), 6),
        "p90": round(float(np.quantile(selected, 0.90)), 6),
    }


def _pixel_support_hash(
    support: np.ndarray, grid_identity: Mapping[str, Any],
) -> str:
    payload = (
        json.dumps(
            dict(grid_identity), sort_keys=True, separators=(",", ":"),
        ).encode("ascii")
        + b"\0"
        + np.packbits(np.asarray(support, dtype=bool), bitorder="little").tobytes()
    )
    return hashlib.sha256(payload).hexdigest()


def _scene_array_content_hash(
    arrays: Mapping[str, np.ndarray], *, prefix: str = "S2CONTENT",
) -> str:
    """Hash full scientific array content without NumPy string truncation."""
    digest = hashlib.sha256()
    for name in sorted(arrays):
        value = np.asarray(arrays[name])
        if value.dtype == object:
            raise ValueError("object arrays are forbidden")
        # Canonicalize byte order so the same scientific values hash identically
        # across little- and big-endian workers.
        if value.dtype.byteorder == ">" or (
            value.dtype.byteorder == "=" and not np.little_endian
        ):
            value = value.byteswap().view(value.dtype.newbyteorder("<"))
        value = np.ascontiguousarray(value)
        header = {
            "name": str(name),
            "shape": list(value.shape),
            "dtype": value.dtype.newbyteorder("<").str,
        }
        digest.update(json.dumps(
            header, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ).encode("ascii"))
        digest.update(b"\0")
        digest.update(value.tobytes(order="C"))
        digest.update(b"\0")
    return str(prefix).strip().upper() + "-" + digest.hexdigest()


def _ratio(
    numerator: np.ndarray, denominator: np.ndarray, support: np.ndarray,
    *, offset: float = 0.0, valid_range: Tuple[float, float] = (-math.inf, math.inf),
) -> Tuple[np.ndarray, np.ndarray]:
    result = np.full(numerator.shape, np.nan, dtype=np.float64)
    valid = support & np.isfinite(numerator) & np.isfinite(denominator) & (np.abs(denominator) > 1e-10)
    np.divide(numerator, denominator, out=result, where=valid)
    result += offset
    valid &= np.isfinite(result) & (result >= valid_range[0]) & (result <= valid_range[1])
    result[~valid] = np.nan
    return result, valid


def _index_arrays(
    bands: Mapping[str, np.ndarray], support: np.ndarray,
) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    result: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    b = bands
    if all(key in b for key in ("B04", "B08")):
        result["ndvi"] = _ratio(b["B08"] - b["B04"], b["B08"] + b["B04"], support, valid_range=(-1, 1))
    if all(key in b for key in ("B02", "B04", "B08")):
        result["evi"] = _ratio(2.5 * (b["B08"] - b["B04"]), b["B08"] + 6 * b["B04"] - 7.5 * b["B02"] + 1, support, valid_range=(-1, 1.5))
    if all(key in b for key in ("B05", "B8A")):
        result["ndre"] = _ratio(b["B8A"] - b["B05"], b["B8A"] + b["B05"], support, valid_range=(-1, 1))
    if all(key in b for key in ("B05", "B8A")):
        result["cired"] = _ratio(b["B8A"], b["B05"], support, offset=-1, valid_range=(-1, 15))
    if all(key in b for key in ("B08", "B11")):
        moisture = _ratio(b["B08"] - b["B11"], b["B08"] + b["B11"], support, valid_range=(-1, 1))
        result["ndmi"] = moisture
        result["lswi"] = moisture
    if all(key in b for key in ("B02", "B04", "B06")):
        result["psri"] = _ratio(b["B04"] - b["B02"], b["B06"], support, valid_range=(-1, 1))
    if all(key in b for key in ("B04", "B05", "B06")):
        result["mtci"] = _ratio(b["B06"] - b["B05"], b["B05"] - b["B04"], support, valid_range=(-2, 10))
    if all(key in b for key in ("B04", "B05")):
        values = (b["B05"] - b["B04"]) / 40.0
        result["red_edge_slope_1"] = (values, support & np.isfinite(values))
    if all(key in b for key in ("B05", "B06")):
        values = (b["B06"] - b["B05"]) / 35.0
        result["red_edge_slope_2"] = (values, support & np.isfinite(values))
    if all(key in b for key in ("B06", "B07")):
        values = (b["B07"] - b["B06"]) / 43.0
        result["red_edge_slope_3"] = (values, support & np.isfinite(values))
    return result


def _ndvi_texture(ndvi: np.ndarray, valid: np.ndarray) -> Dict[str, Optional[float]]:
    neighbour_diffs: List[np.ndarray] = []
    horizontal = valid[:, 1:] & valid[:, :-1]
    vertical = valid[1:, :] & valid[:-1, :]
    if np.any(horizontal):
        neighbour_diffs.append(np.abs(ndvi[:, 1:] - ndvi[:, :-1])[horizontal])
    if np.any(vertical):
        neighbour_diffs.append(np.abs(ndvi[1:, :] - ndvi[:-1, :])[vertical])
    if not neighbour_diffs:
        return {"mean_absolute_neighbor_difference": None, "p90_absolute_neighbor_difference": None}
    values = np.concatenate(neighbour_diffs)
    return {
        "mean_absolute_neighbor_difference": round(float(np.mean(values)), 6),
        "p90_absolute_neighbor_difference": round(float(np.quantile(values, 0.9)), 6),
    }


def _s1_unit_kind(value: Any) -> Optional[str]:
    normalized = str(value or "").strip().lower().replace("-", "_")
    if normalized in _S1_DB_UNITS:
        return "db"
    if normalized in _S1_LINEAR_POWER_UNITS:
        return "linear_power"
    return None


def _s1_to_db_and_linear(
    values: np.ndarray, unit_kind: str,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    raw = np.asarray(values, dtype=np.float64)
    if unit_kind == "db":
        valid = np.isfinite(raw)
        db_values = np.array(raw, copy=True)
        with np.errstate(over="ignore", invalid="ignore"):
            linear_values = np.power(10.0, db_values / 10.0)
        valid &= np.isfinite(linear_values) & (linear_values > 0.0)
    elif unit_kind == "linear_power":
        valid = np.isfinite(raw) & (raw > 0.0)
        linear_values = np.array(raw, copy=True)
        db_values = np.full(raw.shape, np.nan, dtype=np.float64)
        with np.errstate(divide="ignore", invalid="ignore"):
            np.log10(linear_values, out=db_values, where=valid)
        db_values *= 10.0
        valid &= np.isfinite(db_values)
    else:  # Callers must verify the declared unit before conversion.
        raise ValueError("unverified_s1_backscatter_unit")
    db_values[~valid] = np.nan
    linear_values[~valid] = np.nan
    return db_values, linear_values, valid


def _neighbor_texture(
    values: np.ndarray, support: np.ndarray,
) -> Dict[str, Optional[float]]:
    return _ndvi_texture(values, support)


def _parse_day(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value:
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
        except ValueError:
            return None
    return None


def _gdd_until(
    acquisition_day: date, weather_records: Iterable[Any], season_start: Any,
) -> Tuple[Optional[float], Optional[str]]:
    coordinates, primary = _gdd_coordinates_until(
        acquisition_day, weather_records, season_start,
    )
    if not primary:
        return None, None
    return coordinates[primary], "season_start_weather_gdd_base_10c"


def _gdd_coordinates_until(
    acquisition_day: date, weather_records: Iterable[Any], season_start: Any,
) -> Tuple[Dict[str, float], Optional[str]]:
    """Build neutral crop-independent thermal axes from admitted weather."""
    start = _parse_day(season_start)
    if start is None:
        return {}, None
    bases = (0.0, 5.0, 10.0, 12.0)
    totals = {base: 0.0 for base in bases}
    used = {base: 0 for base in bases}
    for raw in weather_records or []:
        row = _mapping(raw)
        day = _parse_day(row.get("date") or row.get("timestamp"))
        if day is None or day < start or day > acquisition_day:
            continue
        explicit = row.get("gdd")
        mean = row.get("temp_mean", row.get("temp_mean_c", row.get("tmean")))
        if not isinstance(mean, (int, float)):
            low, high = row.get("temp_min"), row.get("temp_max")
            if isinstance(low, (int, float)) and isinstance(high, (int, float)):
                mean = (float(low) + float(high)) / 2.0
        if isinstance(mean, (int, float)) and math.isfinite(float(mean)):
            for base in bases:
                totals[base] += max(0.0, float(mean) - base)
                used[base] += 1
            continue
        # A provider-supplied daily GDD value has no transferable base
        # semantics.  Preserve it only on the historical base-10 axis.
        if isinstance(explicit, (int, float)) and math.isfinite(float(explicit)):
            totals[10.0] += max(0.0, float(explicit))
            used[10.0] += 1
    coordinates = {
        f"GDD{int(base)}": round(totals[base], 3)
        for base in bases if used[base]
    }
    primary = "GDD10" if "GDD10" in coordinates else None
    return coordinates, primary


def build_sentinel2_crop_observation(
    package: Any, *, plot_geometry: Any = None, geometry_hash: str = "",
    plot_geometry_crs: Any = None,
    plot_namespace: Any = None,
    crop_cycle_id: Optional[str] = None,
    weather_records: Iterable[Any] = (), season_start: Any = None,
) -> Optional[Dict[str, Any]]:
    """Build one canonical crop observation from a real Sentinel-2 raster."""
    package_map = _mapping(package)
    metadata = _mapping(package_map.get("metadata") or getattr(package, "metadata", None))
    combined = {**metadata, **{key: value for key, value in package_map.items() if value is not None}}
    effective_namespace = plot_namespace or combined.get("plot_namespace") or {
        "tenant_id": combined.get("tenant_id"),
        "farm_id": combined.get("farm_id"),
        "plot_id": combined.get("plot_id") or package_map.get("plot_id"),
    }
    refs = package_map.get("local_cache_refs") or package_map.get("band_refs") or getattr(package, "local_cache_refs", None)
    raw_arrays = package_map.get("band_arrays") or getattr(package, "band_arrays", None)
    available = {
        _normalize_band_key(key)
        for mapping in (refs, raw_arrays)
        if isinstance(mapping, Mapping)
        for key, value in mapping.items() if value is not None
    }
    if not set(_REQUIRED_BANDS).issubset(available):
        return None
    if combined.get("source_reality") != "real_raster":
        return None

    arrays, load_errors = _load_scene_arrays(package)
    scientific_content_hash = str(combined.get("content_hash") or "").strip()
    if not scientific_content_hash:
        scientific_content_hash = _scene_array_content_hash(arrays)
    identity = sentinel2_physical_identity(
        combined, geometry_hash=geometry_hash, plot_namespace=effective_namespace,
    )
    rejection_reasons = list(load_errors)
    for band in _REQUIRED_BANDS:
        if band not in arrays:
            rejection_reasons.append(f"missing_band:{band}")
    if "SCL" not in arrays:
        rejection_reasons.append("missing_mask:SCL")

    anchor = arrays.get("B04")
    shape = tuple(anchor.shape) if isinstance(anchor, np.ndarray) and anchor.ndim == 2 else None
    if shape is None:
        rejection_reasons.append("invalid_grid:B04")
        shape = (0, 0)
    normalized_bands: Dict[str, np.ndarray] = {}
    reflectance_scales: Dict[str, float] = {}
    units = _mapping(package_map.get("band_units") or metadata.get("band_units"))
    normalized_units = {_normalize_band_key(key): value for key, value in units.items()}
    if shape != (0, 0):
        for name in _REFLECTANCE_BANDS:
            if name not in arrays:
                continue
            array = np.asarray(arrays[name])
            if array.shape != shape:
                rejection_reasons.append(f"misaligned_band:{name}")
                continue
            scale = _band_scale(normalized_units.get(name))
            if scale is None:
                rejection_reasons.append(f"unverified_units:{name}")
                continue
            normalized_bands[name] = array.astype(np.float64, copy=False) * scale
            reflectance_scales[name] = scale
    if not set(_REQUIRED_BANDS).issubset(normalized_bands):
        rejection_reasons.append("required_reflectance_unavailable")

    effective_plot_geometry = plot_geometry or combined.get("plot_geometry")
    field_mask, mask_basis, scene_crs, geometry_crs = _plot_mask(
        shape,
        combined.get("transform"),
        effective_plot_geometry,
        scene_crs=combined.get("crs"),
        plot_geometry_crs=plot_geometry_crs or combined.get("plot_geometry_crs"),
    )
    if mask_basis != "plot_polygon_gdal_affine":
        rejection_reasons.append(mask_basis)
    field_pixel_count = int(np.count_nonzero(field_mask))
    if field_pixel_count == 0:
        rejection_reasons.append("empty_plot_support")
    datamask = np.zeros(shape, dtype=bool)
    if "DATAMASK" in arrays and np.asarray(arrays["DATAMASK"]).shape == shape:
        raw_datamask = np.asarray(arrays["DATAMASK"])
        datamask = np.isfinite(raw_datamask) & (raw_datamask > 0)
    elif "DATAMASK" not in arrays:
        rejection_reasons.append("missing_mask:DATAMASK")
    else:
        rejection_reasons.append("misaligned_mask:DATAMASK")
    scl = np.asarray(arrays.get("SCL", np.zeros(shape)), dtype=np.int16)
    if scl.shape != shape:
        rejection_reasons.append("misaligned_mask:SCL")
        scl = np.zeros(shape, dtype=np.int16)
    crop_support = field_mask & datamask & np.isin(scl, _CLEAR_CROP_SCL)
    if set(_REQUIRED_BANDS).issubset(normalized_bands):
        crop_support &= np.isfinite(normalized_bands["B04"]) & np.isfinite(normalized_bands["B08"])
    else:
        crop_support &= False
    # This is the immutable base support shared by every derived statistic:
    # plot geometry ∩ DATAMASK ∩ clear-crop SCL ∩ finite core reflectance.
    crop_support.setflags(write=False)
    normalized_transform = (
        [round(float(value), 12) for value in combined.get("transform")]
        if isinstance(combined.get("transform"), (list, tuple))
        and len(combined.get("transform")) == 6
        else None
    )
    support_grid_identity = {
        "shape": list(shape),
        "transform": normalized_transform,
        "scene_crs": scene_crs,
        "plot_geometry_crs": geometry_crs,
        "plot_geometry_hash": identity.get("plot_geometry_hash"),
    }
    pixel_support_hash = _pixel_support_hash(crop_support, support_grid_identity)
    valid_pixel_count = int(np.count_nonzero(crop_support))
    valid_fraction = valid_pixel_count / field_pixel_count if field_pixel_count else 0.0
    cloud_fraction = float(np.count_nonzero(field_mask & np.isin(scl, _CLOUD_SCL)) / field_pixel_count) if field_pixel_count else 0.0
    shadow_fraction = float(np.count_nonzero(field_mask & np.isin(scl, _SHADOW_SCL)) / field_pixel_count) if field_pixel_count else 0.0
    snow_fraction = float(np.count_nonzero(field_mask & np.isin(scl, _SNOW_SCL)) / field_pixel_count) if field_pixel_count else 0.0
    nodata_fraction = float(np.count_nonzero(field_mask & ~datamask) / field_pixel_count) if field_pixel_count else 1.0

    if combined.get("production_usable") is not True:
        rejection_reasons.append("not_production_usable")
    if combined.get("real_provider_product") is not True:
        rejection_reasons.append("not_real_provider_product")
    if combined.get("diagnostic_only") is not False:
        rejection_reasons.append("diagnostic_only")
    if not identity["physical_identity_complete"]:
        rejection_reasons.append("incomplete_physical_acquisition_identity")
    if valid_pixel_count < 4:
        rejection_reasons.append("insufficient_valid_pixels")
    if valid_fraction < 0.40:
        rejection_reasons.append("low_valid_fraction")
    if cloud_fraction > 0.50:
        rejection_reasons.append("cloud_dominated")
    if shadow_fraction > 0.45:
        rejection_reasons.append("shadow_dominated")

    metrics: Dict[str, Any] = {}
    band_statistics: Dict[str, Dict[str, float]] = {}
    feature_support_contracts: Dict[str, Dict[str, Dict[str, Any]]] = {
        "bands": {}, "indices": {},
    }
    for name, values in normalized_bands.items():
        support = crop_support & np.isfinite(values)
        stats = _stats(values, support)
        if stats:
            band_statistics[name] = stats
            feature_support_contracts["bands"][name] = {
                "support_hash": _pixel_support_hash(
                    support, support_grid_identity,
                ),
                "valid_pixel_count": int(np.count_nonzero(support)),
                "support_definition": f"base_crop_support&finite_{name}",
            }
            for stat_name, value in stats.items():
                metrics[f"{name.lower()}_{stat_name}"] = value
    indices = _index_arrays(normalized_bands, crop_support)
    index_statistics: Dict[str, Dict[str, float]] = {}
    for name, (values, support) in indices.items():
        stats = _stats(values, support)
        if stats:
            index_statistics[name] = stats
            feature_support_contracts["indices"][name] = {
                "support_hash": _pixel_support_hash(
                    support, support_grid_identity,
                ),
                "valid_pixel_count": int(np.count_nonzero(support)),
                "support_definition": f"base_crop_support&finite_formula_{name}",
            }
            for stat_name, value in stats.items():
                metrics[f"{name}_{stat_name}"] = value
    if "ndvi" not in index_statistics:
        rejection_reasons.append("ndvi_unavailable")

    ndvi_texture = (
        _ndvi_texture(*indices["ndvi"]) if "ndvi" in indices else {
            "mean_absolute_neighbor_difference": None,
            "p90_absolute_neighbor_difference": None,
        }
    )
    acquisition_value = identity.get("sensing_timestamp") or combined.get("acquisition_datetime")
    acquisition_day = _parse_day(acquisition_value)
    gdd_coordinates, primary_gdd_basis = _gdd_coordinates_until(
        acquisition_day, weather_records, season_start,
    ) if acquisition_day else ({}, None)
    gdd = (
        gdd_coordinates.get(primary_gdd_basis)
        if primary_gdd_basis else None
    )
    gdd_basis = (
        "season_start_weather_gdd_base_10c" if primary_gdd_basis else None
    )
    reliability = max(
        0.0, min(0.95, valid_fraction * (1.0 - cloud_fraction) * (1.0 - 0.5 * shadow_fraction)),
    )
    rejection_reasons = sorted(set(rejection_reasons))
    admitted = not rejection_reasons
    quality_class = (
        "good" if admitted and valid_fraction >= 0.70 and cloud_fraction <= 0.20
        else "acceptable" if admitted else "rejected"
    )
    product_id = combined.get("provider_product_id") or combined.get("catalog_item_id")
    lineage = {
        "provider_product_id": product_id,
        "catalog_item_id": combined.get("catalog_item_id"),
        "processing_timestamp": identity.get("processing_timestamp"),
        "processing_baseline": identity.get("processing_baseline"),
        "content_hash": scientific_content_hash,
        "process_request_hash": combined.get("process_request_hash"),
        "provider_response_hash": combined.get("provider_response_hash"),
    }
    observation = {
        "contract_version": CROP_OBSERVATION_CONTRACT_VERSION,
        "record_type": "CanonicalCropObservation",
        "observation_id": (
            "CROPOBS-" + str(identity.get("physical_acquisition_key") or hashlib.sha256(str(product_id).encode()).hexdigest())[-24:]
        ),
        "timestamp": acquisition_value,
        "date": acquisition_day.isoformat() if acquisition_day else None,
        "day_of_year": acquisition_day.timetuple().tm_yday if acquisition_day else None,
        "crop_cycle_id": crop_cycle_id or combined.get("crop_cycle_id"),
        "gdd_accumulated": gdd,
        "gdd_basis": gdd_basis,
        "gdd_coordinates": gdd_coordinates,
        "primary_gdd_basis": primary_gdd_basis,
        **identity,
        "provider_product_id": product_id,
        "scene_id": combined.get("scene_id"),
        "content_hash": scientific_content_hash,
        "geometry_hash": identity.get("plot_geometry_hash"),
        "source": "sentinel2",
        "source_family": "sentinel2",
        "provider": str(combined.get("provider") or "copernicus"),
        "sensor": str(combined.get("sensor") or "MSI"),
        "source_reality": "real_raster",
        "temporal_basis": "physical_scene_observation",
        "data_status": "observed" if admitted else "unavailable",
        "production_usable": combined.get("production_usable") is True,
        "real_provider_product": combined.get("real_provider_product") is True,
        "diagnostic_only": combined.get("diagnostic_only") is not False,
        "state_update_allowed": admitted,
        "usable": admitted,
        "quality_admitted": admitted,
        "quality_class": quality_class,
        "quality_rejection_reasons": rejection_reasons,
        "reading_reliability": round(reliability if admitted else 0.0, 6),
        "valid_fraction": round(valid_fraction, 6),
        "clear_crop_fraction": round(valid_fraction, 6),
        "cloud_fraction": round(cloud_fraction, 6),
        "shadow_fraction": round(shadow_fraction, 6),
        "snow_fraction": round(snow_fraction, 6),
        "nodata_fraction": round(nodata_fraction, 6),
        "valid_pixel_count": valid_pixel_count,
        "sample_count": field_pixel_count,
        "field_pixel_count": field_pixel_count,
        "plot_mask_basis": mask_basis,
        "pixel_support_contract": {
            "contract_version": "crop_pixel_support_v1",
            "support_hash": pixel_support_hash,
            "support_definition": (
                "plot_geometry&DATAMASK&SCL_4_5&finite_B04_B08"
            ),
            "shape": list(shape),
            "grid_identity": support_grid_identity,
            "immutable": True,
        },
        "reflectance_scale_by_band": reflectance_scales,
        "reflectance_units_verified": not any(
            reason.startswith("unverified_units:") for reason in rejection_reasons
        ),
        "independence_identity_available": bool(
            identity.get("physical_acquisition_key")
        ),
        "independent_observation_count": 1 if admitted else 0,
        "processing_lineage": [lineage],
        "processing_lineage_count": 1,
        "band_statistics": band_statistics,
        "index_statistics": index_statistics,
        "feature_support_contracts": feature_support_contracts,
        "spatial_distribution": {
            "ndvi_within_field_variance": index_statistics.get("ndvi", {}).get("variance"),
            "ndvi_iqr": (
                round(index_statistics["ndvi"]["p75"] - index_statistics["ndvi"]["p25"], 6)
                if "ndvi" in index_statistics else None
            ),
            "ndvi_texture": ndvi_texture,
        },
        "environmental_context": {
            "day_of_year": acquisition_day.timetuple().tm_yday if acquisition_day else None,
            "gdd_accumulated": gdd,
            "gdd_basis": gdd_basis,
            "gdd_coordinates": gdd_coordinates,
            "primary_gdd_basis": primary_gdd_basis,
            **gdd_coordinates,
            "season_start": str(season_start) if season_start else None,
        },
        "direct_observation": True,
        "parent_observation_ids": [],
        **metrics,
    }
    # Compatibility aliases consumed by the current rule path.
    observation["ndvi"] = observation.get("ndvi_mean")
    observation["evi"] = observation.get("evi_mean")
    observation["ndmi"] = observation.get("ndmi_mean")
    observation["ndre"] = observation.get("ndre_mean")
    return CanonicalCropObservationV2.from_mapping(
        observation, plot_namespace=effective_namespace,
    ).to_dict()


def _available_scene_array_names(package: Any) -> set[str]:
    package_map = _mapping(package)
    names: set[str] = set()
    for candidate in (
        package_map.get("band_arrays"), package_map.get("local_cache_refs"),
        package_map.get("band_refs"), package_map.get("mask_refs"),
        getattr(package, "band_arrays", None),
        getattr(package, "local_cache_refs", None),
        getattr(package, "band_refs", None), getattr(package, "mask_refs", None),
    ):
        if isinstance(candidate, Mapping):
            names.update(
                _normalize_band_key(key)
                for key, value in candidate.items() if value is not None
            )
    return names


def _is_sentinel1_raster_candidate(package: Any) -> bool:
    package_map = _mapping(package)
    metadata = _mapping(
        package_map.get("metadata") or getattr(package, "metadata", None)
    )
    combined = {**metadata, **package_map}
    available = _available_scene_array_names(package)
    sensor_identity = str(
        combined.get("source_family") or combined.get("sensor")
        or combined.get("mission") or combined.get("platform")
        or combined.get("provider_product_id") or ""
    ).strip().upper().replace("-", "").replace("_", "")
    return bool(
        available.intersection({"VV", "VH"})
        and (
            sensor_identity.startswith("S1")
            or sensor_identity.startswith("SENTINEL1")
            or {"VV", "VH"}.issubset(available)
        )
    )


def build_sentinel1_crop_observation(
    package: Any, *, plot_geometry: Any = None, geometry_hash: str = "",
    plot_geometry_crs: Any = None, plot_namespace: Any = None,
    crop_cycle_id: Optional[str] = None,
    weather_records: Iterable[Any] = (), season_start: Any = None,
) -> Optional[Dict[str, Any]]:
    """Build one canonical crop observation from calibrated S1 VV/VH rasters."""
    if not _is_sentinel1_raster_candidate(package):
        return None
    package_map = _mapping(package)
    metadata = _mapping(
        package_map.get("metadata") or getattr(package, "metadata", None)
    )
    combined = {
        **metadata,
        **{key: value for key, value in package_map.items() if value is not None},
    }
    if combined.get("source_reality") != "real_raster":
        return None
    effective_namespace = plot_namespace or combined.get("plot_namespace") or {
        "tenant_id": combined.get("tenant_id"),
        "farm_id": combined.get("farm_id"),
        "plot_id": combined.get("plot_id") or package_map.get("plot_id"),
    }
    identity = sentinel1_physical_identity(
        combined, geometry_hash=geometry_hash,
        plot_namespace=effective_namespace,
    )
    acquisition_value = (
        identity.get("sensing_timestamp")
        or _canonical_timestamp(combined.get("acquisition_datetime"))
    )
    # A canonical scientific observation cannot be assigned a fabricated time.
    if not acquisition_value:
        return None

    arrays, load_errors = _load_scene_arrays(package)
    scientific_content_hash = str(combined.get("content_hash") or "").strip()
    if not scientific_content_hash:
        scientific_content_hash = _scene_array_content_hash(
            arrays, prefix="S1CONTENT",
        )
    rejection_reasons = list(load_errors)
    for band in ("VV", "VH"):
        if band not in arrays:
            rejection_reasons.append(f"missing_band:{band}")
    anchor = arrays.get("VV")
    if not isinstance(anchor, np.ndarray) or anchor.ndim != 2:
        anchor = arrays.get("VH")
    shape = (
        tuple(anchor.shape)
        if isinstance(anchor, np.ndarray) and anchor.ndim == 2 else (0, 0)
    )
    if shape == (0, 0):
        rejection_reasons.append("invalid_grid:S1")

    declared_units = _mapping(
        package_map.get("band_units") or metadata.get("band_units")
    )
    declared_units = {
        _normalize_band_key(key): str(value).strip()
        for key, value in declared_units.items()
    }
    unit_kinds = {
        band: _s1_unit_kind(declared_units.get(band))
        for band in ("VV", "VH")
    }
    db_bands: Dict[str, np.ndarray] = {}
    linear_bands: Dict[str, np.ndarray] = {}
    unit_validity: Dict[str, np.ndarray] = {}
    if shape != (0, 0):
        for band in ("VV", "VH"):
            raw = arrays.get(band)
            if raw is None:
                continue
            if np.asarray(raw).shape != shape:
                rejection_reasons.append(f"misaligned_band:{band}")
                continue
            unit_kind = unit_kinds[band]
            if unit_kind is None:
                rejection_reasons.append(f"unverified_units:{band}")
                continue
            db_values, linear_values, valid = _s1_to_db_and_linear(
                np.asarray(raw), unit_kind,
            )
            db_bands[band] = db_values
            linear_bands[band] = linear_values
            unit_validity[band] = valid
    if not {"VV", "VH"}.issubset(db_bands):
        rejection_reasons.append("required_backscatter_unavailable")

    effective_plot_geometry = plot_geometry or combined.get("plot_geometry")
    field_mask, mask_basis, scene_crs, geometry_crs = _plot_mask(
        shape, combined.get("transform"), effective_plot_geometry,
        scene_crs=combined.get("crs"),
        plot_geometry_crs=(
            plot_geometry_crs or combined.get("plot_geometry_crs")
        ),
    )
    if mask_basis != "plot_polygon_gdal_affine":
        rejection_reasons.append(mask_basis)
    field_pixel_count = int(np.count_nonzero(field_mask))
    if field_pixel_count == 0:
        rejection_reasons.append("empty_plot_support")
    datamask = np.zeros(shape, dtype=bool)
    if "DATAMASK" not in arrays:
        rejection_reasons.append("missing_mask:DATAMASK")
    elif np.asarray(arrays["DATAMASK"]).shape != shape:
        rejection_reasons.append("misaligned_mask:DATAMASK")
    else:
        raw_datamask = np.asarray(arrays["DATAMASK"])
        datamask = np.isfinite(raw_datamask) & (raw_datamask > 0)

    shared_support = field_mask & datamask
    if {"VV", "VH"}.issubset(unit_validity):
        shared_support &= unit_validity["VV"] & unit_validity["VH"]
    else:
        shared_support &= False
    # Every S1 feature below is derived from this exact immutable pixel set.
    shared_support.setflags(write=False)
    normalized_transform = (
        [round(float(value), 12) for value in combined.get("transform")]
        if isinstance(combined.get("transform"), (list, tuple))
        and len(combined.get("transform")) == 6 else None
    )
    support_grid_identity = {
        "shape": list(shape),
        "transform": normalized_transform,
        "scene_crs": scene_crs,
        "plot_geometry_crs": geometry_crs,
        "plot_geometry_hash": identity.get("plot_geometry_hash"),
    }
    pixel_support_hash = _pixel_support_hash(
        shared_support, support_grid_identity,
    )
    valid_pixel_count = int(np.count_nonzero(shared_support))
    valid_fraction = (
        valid_pixel_count / field_pixel_count if field_pixel_count else 0.0
    )
    nodata_fraction = (
        1.0 - valid_fraction if field_pixel_count else 1.0
    )

    if combined.get("production_usable") is not True:
        rejection_reasons.append("not_production_usable")
    if combined.get("real_provider_product") is not True:
        rejection_reasons.append("not_real_provider_product")
    if combined.get("diagnostic_only") is not False:
        rejection_reasons.append("diagnostic_only")
    if not identity["physical_identity_complete"]:
        rejection_reasons.append("incomplete_physical_acquisition_identity")
    if identity.get("orbit_pass") not in {"ASCENDING", "DESCENDING"}:
        rejection_reasons.append("invalid_or_missing_orbit_pass")
    if valid_pixel_count < 4:
        rejection_reasons.append("insufficient_valid_pixels")
    if valid_fraction < 0.40:
        rejection_reasons.append("low_valid_fraction")

    band_statistics: Dict[str, Dict[str, float]] = {}
    index_statistics: Dict[str, Dict[str, float]] = {}
    support_descriptor = {
        "support_hash": pixel_support_hash,
        "valid_pixel_count": valid_pixel_count,
        "support_definition": "shared_s1_crop_support",
    }
    feature_support_contracts: Dict[str, Dict[str, Dict[str, Any]]] = {
        "bands": {}, "indices": {},
    }
    metrics: Dict[str, Any] = {}
    for band in ("VV", "VH"):
        if band not in db_bands:
            continue
        stats = _stats(db_bands[band], shared_support)
        if stats:
            band_statistics[band] = stats
            feature_support_contracts["bands"][band] = dict(support_descriptor)
            for statistic, value in stats.items():
                metrics[f"{band.lower()}_db_{statistic}"] = value

    derived_arrays: Dict[str, np.ndarray] = {}
    if {"VV", "VH"}.issubset(linear_bands):
        vv_linear = linear_bands["VV"]
        vh_linear = linear_bands["VH"]
        denominator = vv_linear + vh_linear
        derived_arrays = {
            "vv_vh_ratio": np.divide(
                vv_linear, vh_linear,
                out=np.full(shape, np.nan), where=shared_support,
            ),
            "vv_minus_vh_db": db_bands["VV"] - db_bands["VH"],
            "rvi": np.divide(
                4.0 * vh_linear, denominator,
                out=np.full(shape, np.nan), where=shared_support,
            ),
            "cross_pol_fraction": np.divide(
                vh_linear, denominator,
                out=np.full(shape, np.nan), where=shared_support,
            ),
        }
    for name, values in derived_arrays.items():
        stats = _stats(values, shared_support)
        if stats:
            index_statistics[name] = stats
            feature_support_contracts["indices"][name] = dict(
                support_descriptor,
            )
            for statistic, value in stats.items():
                metrics[f"{name}_{statistic}"] = value

    texture_summary = {
        "support_hash": pixel_support_hash,
        "support_definition": "shared_s1_crop_support_neighbor_pairs",
        "vv_db": (
            _neighbor_texture(db_bands["VV"], shared_support)
            if "VV" in db_bands else {}
        ),
        "vh_db": (
            _neighbor_texture(db_bands["VH"], shared_support)
            if "VH" in db_bands else {}
        ),
    }
    reliability = max(0.0, min(0.95, valid_fraction))
    rejection_reasons = sorted(set(rejection_reasons))
    admitted = not rejection_reasons
    quality_class = (
        "good" if admitted and valid_fraction >= 0.70
        else "acceptable" if admitted else "rejected"
    )
    product_id = (
        combined.get("provider_product_id") or combined.get("catalog_item_id")
        or combined.get("scene_id")
    )
    lineage = {
        "provider_product_id": product_id,
        "catalog_item_id": combined.get("catalog_item_id"),
        "processing_timestamp": identity.get("processing_timestamp"),
        "processing_baseline": identity.get("processing_baseline"),
        "content_hash": scientific_content_hash,
        "process_request_hash": combined.get("process_request_hash"),
        "provider_response_hash": combined.get("provider_response_hash"),
    }
    acquisition_day = _parse_day(acquisition_value)
    gdd_coordinates, primary_gdd_basis = _gdd_coordinates_until(
        acquisition_day, weather_records, season_start,
    ) if acquisition_day else ({}, None)
    observation = {
        "contract_version": CROP_OBSERVATION_CONTRACT_VERSION,
        "record_type": "CanonicalCropObservation",
        "observation_id": (
            "CROPOBS-" + str(
                identity.get("physical_acquisition_key")
                or hashlib.sha256(
                    f"{product_id}|{acquisition_value}".encode("utf-8")
                ).hexdigest()
            )[-24:]
        ),
        "timestamp": acquisition_value,
        "date": acquisition_day.isoformat() if acquisition_day else None,
        "day_of_year": (
            acquisition_day.timetuple().tm_yday if acquisition_day else None
        ),
        "gdd_accumulated": (
            gdd_coordinates.get(primary_gdd_basis)
            if primary_gdd_basis else None
        ),
        "gdd_basis": (
            "season_start_weather_gdd_base_10c" if primary_gdd_basis else None
        ),
        "gdd_coordinates": gdd_coordinates,
        "primary_gdd_basis": primary_gdd_basis,
        "crop_cycle_id": crop_cycle_id or combined.get("crop_cycle_id"),
        **identity,
        "provider_product_id": product_id,
        "scene_id": combined.get("scene_id"),
        "content_hash": scientific_content_hash,
        "geometry_hash": identity.get("plot_geometry_hash"),
        "geometry_version": identity.get("plot_geometry_hash") or "unavailable",
        "source": "sentinel1",
        "source_family": "sentinel1",
        "provider": str(combined.get("provider") or "copernicus"),
        "sensor": str(combined.get("sensor") or "C-SAR"),
        "source_reality": "real_raster",
        "temporal_basis": "physical_scene_observation",
        "data_status": "observed" if admitted else "unavailable",
        "production_usable": combined.get("production_usable") is True,
        "real_provider_product": combined.get("real_provider_product") is True,
        "diagnostic_only": combined.get("diagnostic_only") is not False,
        "state_update_allowed": admitted,
        "usable": admitted,
        "quality_admitted": admitted,
        "quality_class": quality_class,
        "quality_rejection_reasons": rejection_reasons,
        "reading_reliability": round(reliability if admitted else 0.0, 6),
        "valid_fraction": round(valid_fraction, 6),
        "cloud_fraction": None,
        "shadow_fraction": None,
        "snow_fraction": None,
        "nodata_fraction": round(nodata_fraction, 6),
        "valid_pixel_count": valid_pixel_count,
        "sample_count": field_pixel_count,
        "field_pixel_count": field_pixel_count,
        "plot_mask_basis": mask_basis,
        "pixel_support_contract": {
            "contract_version": "crop_pixel_support_v1",
            "support_hash": pixel_support_hash,
            "support_definition": (
                "plot_geometry&DATAMASK&finite_positive_calibrated_VV_VH"
            ),
            "shape": list(shape),
            "grid_identity": support_grid_identity,
            "immutable": True,
        },
        "backscatter_input_units": declared_units,
        "backscatter_unit_kind_by_band": unit_kinds,
        "canonical_backscatter_unit": "db",
        "backscatter_units_verified": all(unit_kinds.values()),
        "independence_identity_available": bool(
            identity.get("physical_acquisition_key")
        ),
        "independent_observation_count": 1 if admitted else 0,
        "processing_lineage": [lineage],
        "processing_lineage_count": 1,
        "band_statistics": band_statistics,
        "index_statistics": index_statistics,
        "feature_support_contracts": feature_support_contracts,
        "spectral_summary": {},
        "sar_summary": {
            "canonical_backscatter_unit": "db",
            "input_unit_kind_by_band": unit_kinds,
            "backscatter_statistics": band_statistics,
            "polarimetric_statistics": index_statistics,
            "physical_acquisition": {
                "orbit_reference_kind": identity.get("orbit_reference_kind"),
                "orbit_reference": identity.get("orbit_reference"),
                "orbit_pass": identity.get("orbit_pass"),
            },
        },
        "spatial_distribution": {
            "vv_db_within_field_variance": band_statistics.get("VV", {}).get("variance"),
            "vh_db_within_field_variance": band_statistics.get("VH", {}).get("variance"),
            "rvi_within_field_variance": index_statistics.get("rvi", {}).get("variance"),
        },
        "texture_summary": texture_summary,
        "environmental_context": {
            "day_of_year": (
                acquisition_day.timetuple().tm_yday if acquisition_day else None
            ),
            "gdd_accumulated": (
                gdd_coordinates.get(primary_gdd_basis)
                if primary_gdd_basis else None
            ),
            "gdd_basis": (
                "season_start_weather_gdd_base_10c"
                if primary_gdd_basis else None
            ),
            "gdd_coordinates": gdd_coordinates,
            "primary_gdd_basis": primary_gdd_basis,
            **gdd_coordinates,
            "season_start": str(season_start) if season_start else None,
        },
        "direct_observation": True,
        "parent_observation_ids": [],
        **metrics,
    }
    observation["vv"] = observation.get("vv_db_mean")
    observation["vh"] = observation.get("vh_db_mean")
    observation["vv_vh_ratio"] = observation.get("vv_vh_ratio_mean")
    observation["rvi"] = observation.get("rvi_mean")
    return CanonicalCropObservationV2.from_mapping(
        observation, plot_namespace=effective_namespace,
    ).to_dict()


def _lineage_key(item: Mapping[str, Any]) -> Tuple[str, str, str]:
    return (
        str(item.get("processing_timestamp") or ""),
        str(item.get("provider_product_id") or ""),
        str(item.get("content_hash") or ""),
    )


def deduplicate_physical_acquisitions(records: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Count a sensing event once while retaining every processing lineage."""
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    order: List[str] = []
    for index, raw in enumerate(records or []):
        row = dict(raw)
        physical_key = row.get("physical_acquisition_key")
        fallback = row.get("content_hash") or row.get("observation_id") or row.get("scene_id")
        group_key = f"physical:{physical_key}" if physical_key else f"fallback:{fallback or index}"
        if group_key not in grouped:
            grouped[group_key] = []
            order.append(group_key)
        grouped[group_key].append(row)

    result: List[Dict[str, Any]] = []
    for group_key in order:
        candidates = grouped[group_key]
        selected = max(
            candidates,
            key=lambda row: (
                row.get("quality_admitted") is True,
                float(row.get("valid_fraction") or 0.0),
                float(row.get("reading_reliability") or 0.0),
                str(row.get("processing_timestamp") or ""),
                str(row.get("content_hash") or ""),
            ),
        )
        lineages: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        for candidate in candidates:
            items = candidate.get("processing_lineage") or []
            if not items:
                items = [{
                    "provider_product_id": candidate.get("provider_product_id"),
                    "processing_timestamp": candidate.get("processing_timestamp"),
                    "processing_baseline": candidate.get("processing_baseline"),
                    "content_hash": candidate.get("content_hash"),
                }]
            for item in items:
                mapped = dict(item)
                lineages[_lineage_key(mapped)] = mapped
        merged = dict(selected)
        merged["processing_lineage"] = [lineages[key] for key in sorted(lineages)]
        merged["processing_lineage_count"] = len(lineages)
        merged["duplicate_processing_product_count"] = max(0, len(candidates) - 1)
        identity_available = merged.get("independence_identity_available") is not False
        merged["independent_observation_count"] = (
            1
            if merged.get("quality_admitted") is True and identity_available
            else 0
        )
        if (
            merged.get("contract_version") == CROP_OBSERVATION_CONTRACT_VERSION
            or merged.get("record_type") == "CanonicalCropObservationV2"
        ):
            merged.pop("observation_hash", None)
            merged = CanonicalCropObservationV2.from_mapping(
                merged, plot_namespace=merged.get("plot_namespace"),
            ).to_dict()
        result.append(merged)
    return sorted(result, key=lambda row: str(row.get("timestamp") or row.get("date") or ""))


def _packet_rows(package: Any) -> List[Dict[str, Any]]:
    package_map = _mapping(package)
    metadata = _mapping(package_map.get("metadata") or getattr(package, "metadata", None))
    packets = package_map.get("packets") or getattr(package, "packets", None) or []
    rows: List[Dict[str, Any]] = []
    for packet in packets:
        row = _mapping(packet)
        payload = _mapping(row.get("payload"))
        if payload:
            row = {**payload, **row}
        if not row:
            continue
        row.setdefault("source_reality", metadata.get("source_reality"))
        row.setdefault("content_hash", metadata.get("content_hash"))
        row.setdefault("provider_product_id", metadata.get("provider_product_id") or metadata.get("scene_id"))
        row.setdefault("real_provider_product", metadata.get("real_provider_product"))
        row.setdefault("production_usable", metadata.get("production_usable"))
        row.setdefault("diagnostic_only", metadata.get("diagnostic_only"))
        row.setdefault("temporal_basis", metadata.get("temporal_basis"))
        row.setdefault("geometry_hash", metadata.get("plot_geometry_hash"))
        row.setdefault("ndvi", row.get("ndvi_mean"))
        row.setdefault("evi", row.get("evi_mean"))
        row.setdefault("ndmi", row.get("ndmi_mean"))
        row.setdefault("ndwi", row.get("ndwi_mean"))
        row.setdefault("vv", row.get("vv_db_mean", row.get("vv_db")))
        row.setdefault("vh", row.get("vh_db_mean", row.get("vh_db")))
        family = str(
            row.get("source_family")
            or row.get("source")
            or package_map.get("source_family")
            or metadata.get("source_family")
            or ""
        ).lower().replace("-", "").replace("_", "")
        provider_product_id = str(row.get("provider_product_id") or "")
        is_sentinel2 = (
            family in {"sentinel2", "s2", "optical"}
            or provider_product_id.upper().startswith("S2")
        )
        if is_sentinel2:
            identity = sentinel2_physical_identity(
                {**metadata, **package_map, **row},
                geometry_hash=str(
                    row.get("plot_geometry_hash")
                    or row.get("geometry_hash")
                    or ""
                ),
                plot_namespace=(
                    row.get("plot_namespace")
                    or package_map.get("plot_namespace")
                    or metadata.get("plot_namespace")
                    or {
                        "tenant_id": row.get("tenant_id") or metadata.get("tenant_id"),
                        "farm_id": row.get("farm_id") or metadata.get("farm_id"),
                        "plot_id": row.get("plot_id") or metadata.get("plot_id"),
                    }
                ),
            )
            row.update(identity)
            identity_available = bool(identity.get("physical_acquisition_key"))
            row["independence_identity_available"] = identity_available
            if not identity_available:
                # A Sentinel packet without a physical acquisition identity can
                # remain visible as lineage, but cannot count as independent
                # crop evidence.
                row["independent_observation_count"] = 0
            row.setdefault("processing_lineage", [{
                "provider_product_id": row.get("provider_product_id"),
                "processing_timestamp": identity.get("processing_timestamp"),
                "processing_baseline": identity.get("processing_baseline"),
                "content_hash": row.get("content_hash"),
            }])
        rows.append(row)
    return rows


def build_canonical_crop_observations(
    source_packages: Mapping[str, Any], *, plot_geometry: Any = None,
    geometry_hash: str = "", plot_geometry_crs: Any = None,
    plot_namespace: Any = None,
    crop_cycle_id: Optional[str] = None,
    weather_records: Iterable[Any] = (),
    season_start: Any = None,
) -> List[Dict[str, Any]]:
    """Extract canonical crop records from all Layer-0 source packages."""
    records: List[Dict[str, Any]] = []
    for package_group in (source_packages or {}).values():
        packages = list(package_group) if isinstance(package_group, (list, tuple)) else [package_group]
        for package in packages:
            observation = build_sentinel2_crop_observation(
                package,
                plot_geometry=plot_geometry,
                geometry_hash=geometry_hash,
                plot_geometry_crs=plot_geometry_crs,
                plot_namespace=plot_namespace,
                crop_cycle_id=crop_cycle_id,
                weather_records=weather_records,
                season_start=season_start,
            )
            if observation is not None:
                records.append(observation)
                continue
            s1_candidate = _is_sentinel1_raster_candidate(package)
            observation = build_sentinel1_crop_observation(
                package,
                plot_geometry=plot_geometry,
                geometry_hash=geometry_hash,
                plot_geometry_crs=plot_geometry_crs,
                plot_namespace=plot_namespace,
                crop_cycle_id=crop_cycle_id,
                weather_records=weather_records,
                season_start=season_start,
            )
            if observation is not None:
                records.append(observation)
            elif not s1_candidate:
                records.extend(_packet_rows(package))
            # A malformed raw S1 candidate is never demoted into a permissive
            # scalar packet.  Missing sensing time/source authority therefore
            # fails closed as no scientific crop observation.
    return deduplicate_physical_acquisitions(records)


def build_crop_evidence_ledger(
    records: Iterable[Mapping[str, Any]], *, plot_namespace: Any,
) -> CropEvidenceLedgerV2:
    """Create the immutable, hash-stable ledger over canonical observations."""
    canonical = [
        record for record in records or []
        if isinstance(record, Mapping)
        and record.get("contract_version") == CROP_OBSERVATION_CONTRACT_VERSION
    ]
    return CropEvidenceLedgerV2.from_observations(plot_namespace, canonical)
