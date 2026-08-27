import hashlib
import json
import math
import struct
from typing import Any, Dict, List, Union, Sequence, Optional
import numpy as np

SURFACE_HASH_CONTRACT_VERSION = "r5_hash_v3_surface_identity"


def _canonical_json(obj: Any) -> str:
    """Produces consistent, deterministic JSON string for hashing."""
    def _normalize(item: Any) -> Any:
        if isinstance(item, dict):
            return {k: _normalize(v) for k, v in sorted(item.items())}
        elif isinstance(item, (list, tuple)):
            return [_normalize(x) for x in item]
        elif isinstance(item, float):
            if math.isnan(item):
                return "NaN"
            if math.isinf(item):
                raise ValueError("Infinity values are not supported in canonical JSON hashing")
            if item == 0.0:
                return 0.0
            return round(item, 10)
        return item

    normalized = _normalize(obj)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def compute_raster_bytes_hash(
    data: Any,
    mask: Any = None
) -> str:
    """
    Computes a host-independent 64-character SHA-256 hash of raster data floats and optional boolean mask.
    Supports 1D and 2D arrays/lists. Canonicalizes -0.0 -> +0.0, preserves quiet NaN bit patterns,
    rejects infinities, packs masks with bitorder='big', and binds grid dimensions.
    """
    hasher = hashlib.sha256()
    hasher.update(SURFACE_HASH_CONTRACT_VERSION.encode("utf-8"))

    if data is None:
        data = []

    if isinstance(data, bytes):
        hasher.update(data)
    else:
        arr = np.asarray(data, dtype=np.float64)
        if arr.size > 0:
            if arr.ndim != 2:
                raise ValueError(f"Raster data must be a 2D matrix, got shape {arr.shape} ({arr.ndim}D)")
            if np.any(np.isinf(arr)):
                raise ValueError("Infinity float encountered in raster hashing")

            # Canonicalize -0.0 -> +0.0
            arr_clean = np.where(arr == 0.0, 0.0, arr)
            # Preserve quiet NaNs using standard numpy float64 representation
            arr_clean = np.where(np.isnan(arr_clean), np.nan, arr_clean)
            
            # Encode shape dimensions into hasher
            shape_str = "x".join(str(d) for d in arr.shape)
            hasher.update(shape_str.encode("utf-8"))
            hasher.update(arr_clean.astype("<f8").tobytes())
        else:
            hasher.update(b"empty")

    if mask is not None:
        if isinstance(mask, bytes):
            hasher.update(mask)
        else:
            mask_arr = np.asarray(mask, dtype=bool)
            if not isinstance(data, bytes) and 'arr' in locals() and arr.size > 0 and mask_arr.shape != arr.shape:
                raise ValueError(f"Mask shape {mask_arr.shape} does not match raster shape {arr.shape}")
            mask_bits = np.packbits(mask_arr, bitorder="big").tobytes()
            hasher.update(mask_bits)

    return hasher.hexdigest()


def compute_surface_content_hash(
    surface_data: Dict[str, Any]
) -> str:
    """
    Computes deterministic 64-character surface content hash from surface properties.
    """
    grid_data = surface_data.get("grid_data")
    if grid_data is None:
        grid_data = surface_data.get("values")
    if grid_data is None:
        grid_data = surface_data.get("raster")
    if grid_data is None:
        grid_data = []

    mask_data = surface_data.get("mask")
    if mask_data is None:
        mask_data = surface_data.get("valid_mask")

    raster_hash = compute_raster_bytes_hash(grid_data, mask_data)

    spec = {
        "contract_version": SURFACE_HASH_CONTRACT_VERSION,
        "dimensions": surface_data.get("dimensions") or surface_data.get("shape"),
        "units": str(surface_data.get("units") or ""),
        "evidence_class": str(surface_data.get("evidence_class") or surface_data.get("support_class") or ""),
        "raster_hash": raster_hash,
    }

    hasher = hashlib.sha256()
    hasher.update(_canonical_json(spec).encode("utf-8"))
    return hasher.hexdigest()


def compute_surface_inventory_hash(
    surfaces: List[Dict[str, Any]]
) -> str:
    """
    Computes deterministic 64-character inventory hash over sorted surface inventory entries.
    Tuple: (surface_id, surface_type, surface_content_hash, grid_spec_hash, authorization_version)
    Requires producer-issued surface IDs and rejects duplicate IDs.
    """
    sorted_tuples = []
    seen_ids = set()

    for s in surfaces:
        if not isinstance(s, dict):
            raise ValueError("Surface inventory entry must be a mapping")
        surf_id = str(s.get("surface_id") or "").strip()
        surf_type = str(s.get("surface_type") or s.get("type") or "").strip()
        if not surf_id:
            raise ValueError("Surface inventory entry is missing mandatory surface_id")
        if not surf_type:
            raise ValueError(f"Surface inventory entry {surf_id!r} is missing surface type")
        if surf_id in seen_ids:
            raise ValueError(f"Duplicate surface_id detected in surface inventory: {surf_id}")
        seen_ids.add(surf_id)

        surf_content_hash = str(s.get("surface_content_hash") or s.get("content_hash") or compute_surface_content_hash(s)).strip()
        grid_spec_hash = str(s.get("grid_specification_hash") or s.get("grid_spec_hash") or s.get("grid_hash") or "").strip()
        auth_version = str(s.get("authorization_version") or s.get("render_authorization_version") or s.get("auth_version") or "").strip()

        sorted_tuples.append((surf_id, surf_type, surf_content_hash, grid_spec_hash, auth_version))

    # Sort lexicographically by (surface_id, surface_type, ...)
    sorted_tuples.sort(key=lambda x: (x[0], x[1], x[2], x[3], x[4]))

    raw_canonical = _canonical_json({
        "contract_version": SURFACE_HASH_CONTRACT_VERSION,
        "inventory": sorted_tuples
    })
    return hashlib.sha256(raw_canonical.encode("utf-8")).hexdigest()
