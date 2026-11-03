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
    # Every tile must have one unambiguous source product ID. The old set
    # comparison silently discarded unidentified and malformed extra tiles.
    payload = userdata.get("userData", userdata) if isinstance(userdata, dict) else {}
    raw_tiles = payload.get("tiles") if isinstance(payload, dict) else None
    records = _tile_records(userdata)
    id_keys = (
        ("sentinel2ProductId", "productId")
        if sensor == "S2"
        else ("sentinel1ProductId", "productId")
    )
    expected = normalize_product_id(expected_product_id)
    identified_ids: list[str] = []
    unidentified_count = 0
    conflicting_count = 0
    if not isinstance(raw_tiles, list):
        raw_tiles = []
    for tile in raw_tiles:
        if not isinstance(tile, dict):
            unidentified_count += 1
            continue
        # `id` is a fallback only when no explicit product ID exists.
        # A tile ID need not be the source product ID.
        candidates = [tile.get(key) for key in id_keys
                      if tile.get(key) not in (None, "")]
        if not candidates and tile.get("id") not in (None, ""):
            candidates = [tile["id"]]
        if not candidates or any(
            not isinstance(value, str) or not normalize_product_id(value)
            for value in candidates
        ):
            unidentified_count += 1
            continue
        canonical = {normalize_product_id(value) for value in candidates}
        if len(canonical) != 1:
            conflicting_count += 1
            continue
        identified_ids.append(candidates[0])
    returned_ids = sorted(set(identified_ids))
    normalized_returned = sorted({
        normalize_product_id(value) for value in returned_ids
    })
    announced_unknown = (
        payload.get("unidentifiedTileCount")
        if isinstance(payload, dict) else None
    )
    announced_expected = (
        payload.get("expectedProductId")
        if isinstance(payload, dict) else None
    )
    telemetry_valid = (
        announced_unknown is None
        or (type(announced_unknown) is int and announced_unknown == 0)
    )
    announced_product_consistent = (
        announced_expected is None
        or (isinstance(announced_expected, str)
            and normalize_product_id(announced_expected) == expected)
    )
    exact = bool(
        expected and sensor in ("S1", "S2")
        and raw_tiles
        and len(identified_ids) == len(raw_tiles)
        and unidentified_count == 0 and conflicting_count == 0
        and normalized_returned == [expected]
        and telemetry_valid and announced_product_consistent
    )
    metadata_hash = hashlib.sha256(
        json.dumps(
            userdata if isinstance(userdata, dict) else {},
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    proof = {
        "binding_schema_version": "exact_catalog_process_v2",
        "expected_catalog_item_id": expected_product_id,
        "expected_normalized_id": expected,
        "returned_product_ids": returned_ids,
        "returned_normalized_ids": normalized_returned,
        "returned_tile_count": len(raw_tiles),
        "identified_tile_count": len(identified_ids),
        "unidentified_tile_count": unidentified_count,
        "conflicting_tile_count": conflicting_count,
        "reported_unidentified_tile_count": announced_unknown,
        "all_returned_tiles_identified": bool(
            raw_tiles and len(identified_ids) == len(raw_tiles)
        ),
        "exact_match": exact,
        "process_userdata_hash": metadata_hash,
        "failure_reason": None if exact else (
            "missing_process_tile_metadata" if not raw_tiles
            else "unidentified_or_conflicting_process_tile"
            if unidentified_count or conflicting_count
            else "catalog_process_product_mismatch"
        ),
    }
    return {
        "is_exact": exact,
        "product_binding": "exact_catalog_item" if exact else "binding_mismatch",
        "provider_tile_id": _first(records, ("tileId", "shId", "dataPath")),
        "provider_relative_orbit": _first(
            records, ("relativeOrbitNumber", "sat:relative_orbit"),
        ),
        "provider_absolute_orbit": _first(
            records, ("orbitId", "orbitNumber", "sat:absolute_orbit"),
        ),
        "provider_orbit_id": _first(
            records, ("orbitId", "relativeOrbitNumber", "orbitNumber"),
        ),
        "provider_orbit_pass": _first(
            records, ("orbitDirection", "orbitPass", "sat:orbit_state"),
        ),
        "process_metadata": (
            dict(userdata) if isinstance(userdata, dict) else {}
        ),
        "proof": proof,
    }


def exact_binding_proof_valid(
    expected_product_id: str,
    proof: Any,
) -> bool:
    """Revalidate persisted binding proof without trusting its status label."""
    if (
        not isinstance(proof, dict)
        or proof.get("binding_schema_version") != "exact_catalog_process_v2"
        or proof.get("exact_match") is not True
        or proof.get("all_returned_tiles_identified") is not True
        or type(proof.get("returned_tile_count")) is not int
        or proof["returned_tile_count"] < 1
        or type(proof.get("identified_tile_count")) is not int
        or proof["returned_tile_count"] != proof["identified_tile_count"]
        or type(proof.get("unidentified_tile_count")) is not int
        or proof["unidentified_tile_count"] != 0
        or type(proof.get("conflicting_tile_count")) is not int
        or proof["conflicting_tile_count"] != 0
        or (
            proof.get("reported_unidentified_tile_count") is not None
            and (
                type(proof["reported_unidentified_tile_count"]) is not int
                or proof["reported_unidentified_tile_count"] != 0
            )
        )
    ):
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
