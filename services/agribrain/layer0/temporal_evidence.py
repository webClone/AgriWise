"""Canonical admission contract for plot-scoped temporal provider evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Tuple


ADMITTED_SOURCE_REALITIES = {
    "provider_daily_statistical_aggregate",
    "provider_catalog_scene_observation",
    "provider_scene_observation",
    "provider_temporal_observation",
    "real_provider_raster",
    "provider_observation",
    "real_raster",
}


def _has_numeric(record: Dict[str, Any], keys: Tuple[str, ...]) -> bool:
    return any(
        isinstance(record.get(key), (int, float))
        and not isinstance(record.get(key), bool)
        for key in keys
    )


def is_admitted_temporal_record(
    record: Dict[str, Any],
    *,
    value_keys: Tuple[str, ...] = (
        "ndvi", "ndvi_mean", "evi", "evi_mean", "ndmi", "ndmi_mean",
        "vv", "vv_db", "vv_db_mean", "vh", "vh_db", "vh_db_mean",
        "vv_vh_ratio", "rvi", "rvi_mean",
    ),
) -> bool:
    """Default-deny scientific admission shared by all temporal consumers."""
    if not isinstance(record, dict):
        return False
    source_reality = record.get("source_reality")
    is_daily_aggregate = source_reality == "provider_daily_statistical_aggregate"
    identity = (
        record.get("provider_product_id")
        or record.get("scene_id")
        or record.get("observation_id")
        or (record.get("request_hash") if is_daily_aggregate else None)
    )
    quality = str(record.get("quality_class", "")).lower()
    return (
        source_reality in ADMITTED_SOURCE_REALITIES
        and bool(identity)
        and bool(record.get("content_hash"))
        and _has_numeric(record, value_keys)
        and record.get("usable") is True
        and quality in {"good", "acceptable", "clear", "valid"}
        and record.get("production_usable") is True
        and (is_daily_aggregate or record.get("real_provider_product") is True)
        and record.get("diagnostic_only") is False
        and (
            not is_daily_aggregate
            or (
                record.get("quality_admitted") is True
                and bool(record.get("geometry_hash"))
                and isinstance(record.get("valid_pixel_count"), int)
                and record.get("valid_pixel_count") > 0
            )
        )
    )


def build_temporal_admission_ledger(
    records: Iterable[Dict[str, Any]], *, value_keys: Tuple[str, ...]
) -> Dict[str, Any]:
    """Return admitted/rejected records plus explicit health counters."""
    items = list(records)
    admitted = [item for item in items if is_admitted_temporal_record(item, value_keys=value_keys)]
    return {
        "contract_version": "temporal_evidence_admission_v1",
        "transport_received": bool(items),
        "input_count": len(items),
        "quality_admitted_count": len(admitted),
        "rejected_count": len(items) - len(admitted),
        "state_eligible": bool(admitted),
        "scientifically_healthy": bool(admitted),
        "admitted_records": admitted,
    }
