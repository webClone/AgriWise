"""
Akaloris / AgriBrain — Shared Canonical Geometry Contract (v1)

Enforces cross-language byte-for-byte deterministic geometry hashing
between Python and TypeScript / JavaScript runtimes.

Contract:
- Canonicalize GeoJSON: recursively sort object keys, traverse arrays
- Normalize numbers: floats with integer values (.is_integer()) format as integers
- Compact serialization: separators=(",", ":"), ensure_ascii=False
- Digest format: sha256:{hex64}
"""

import hashlib
import json
from typing import Any, Union


GEOMETRY_CONTRACT_VERSION = "canonical_geojson_sha256_v1"


def canonicalize_geojson(value: Any) -> Any:
    """Recursively canonicalize GeoJSON structures.

    Sorts dictionary keys alphabetically, preserves array order,
    and normalizes floats whose integer value is exact.
    """
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return [canonicalize_geojson(item) for item in value]
    if isinstance(value, dict):
        return {key: canonicalize_geojson(value[key]) for key in sorted(value.keys())}
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return value
    return value


def compute_geometry_hash(geometry: Union[dict, list, str, None]) -> str:
    """Compute cross-language deterministic geometry hash with 'sha256:' prefix.

    Matches TypeScript computeGeometryHash() byte-for-byte across all
    GeoJSON geometries, features, holes, multipolygons, and property structures.
    """
    if not geometry:
        return "empty_geometry"
    if isinstance(geometry, str):
        try:
            target = json.loads(geometry)
        except Exception:
            digest = hashlib.sha256(geometry.encode("utf-8")).hexdigest()
            return f"sha256:{digest}"
    else:
        target = geometry

    canonical = canonicalize_geojson(target)
    canonical_bytes = json.dumps(
        canonical, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    digest = hashlib.sha256(canonical_bytes).hexdigest()
    return f"sha256:{digest}"
