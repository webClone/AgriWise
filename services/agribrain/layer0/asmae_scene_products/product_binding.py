"""Exact Catalog-to-Process acquisition binding utilities."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, List


def normalize_product_id(value: Any) -> str:
    text = str(value or "").strip().upper().replace("\\", "/")
    text = text.rsplit("/", 1)[-1]
    for suffix in (".SAFE", ".ZIP"):
        if text.endswith(suffix):
            text = text[:-len(suffix)]
    return text


def _tile_records(userdata: Any) -> List[Dict[str, Any]]:
    if not isinstance(userdata, dict):
        return []
    payload = userdata.get("userData")
    if isinstance(payload, dict):
        userdata = payload
    tiles = userdata.get("tiles", [])
    return [dict(tile) for tile in tiles if isinstance(tile, dict)]


def _first(records: Iterable[Dict[str, Any]], keys: Iterable[str]) -> Any:
    for record in records:
        for key in keys:
            value = record.get(key)
            if value not in (None, ""):
                return value
    return None


def verify_exact_product_binding(
    expected_product_id: str,
    userdata: Any,
    sensor: str,
) -> Dict[str, Any]:
    """Verify that Process API returned only the selected Catalog product."""
    records = _tile_records(userdata)
    id_keys = (
        ("sentinel2ProductId", "productId", "id")
        if sensor == "S2"
        else ("sentinel1ProductId", "productId", "id")
    )
    returned_ids = sorted({
        str(value)
        for record in records
        for key in id_keys
        for value in [record.get(key)]
        if value not in (None, "")
    })
    expected = normalize_product_id(expected_product_id)
    normalized_returned = sorted({
        normalize_product_id(value) for value in returned_ids
        if normalize_product_id(value)
    })
    exact = bool(expected and normalized_returned == [expected])
    metadata_hash = hashlib.sha256(
        json.dumps(
            userdata if isinstance(userdata, dict) else {},
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    proof = {
        "binding_schema_version": "exact_catalog_process_v1",
        "expected_catalog_item_id": expected_product_id,
        "expected_normalized_id": expected,
        "returned_product_ids": returned_ids,
        "returned_normalized_ids": normalized_returned,
        "returned_tile_count": len(records),
        "exact_match": exact,
        "process_userdata_hash": metadata_hash,
        "failure_reason": None if exact else (
            "missing_process_tile_metadata" if not records
            else "catalog_process_product_mismatch"
        ),
    }
    return {
        "is_exact": exact,
        "product_binding": "exact_catalog_item" if exact else "binding_mismatch",
        "provider_tile_id": _first(records, ("tileId", "shId", "dataPath")),
        "provider_orbit_id": _first(
            records, ("orbitId", "relativeOrbitNumber", "orbitNumber"),
        ),
        "provider_orbit_pass": _first(
            records, ("orbitDirection", "orbitPass", "sat:orbit_state"),
        ),
        "proof": proof,
    }


def exact_binding_proof_valid(
    expected_product_id: str,
    proof: Any,
) -> bool:
    """Revalidate persisted binding proof without trusting its status label."""
    if not isinstance(proof, dict) or proof.get("exact_match") is not True:
        return False
    expected = normalize_product_id(expected_product_id)
    recorded_expected = normalize_product_id(
        proof.get("expected_catalog_item_id")
        or proof.get("expected_normalized_id"),
    )
    returned = sorted({
        normalize_product_id(value)
        for value in proof.get("returned_product_ids", [])
        if normalize_product_id(value)
    })
    if not returned:
        returned = sorted({
            normalize_product_id(value)
            for value in proof.get("returned_normalized_ids", [])
            if normalize_product_id(value)
        })
    return bool(expected and recorded_expected == expected and returned == [expected])
