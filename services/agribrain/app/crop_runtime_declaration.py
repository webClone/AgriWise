"""Authenticated crop declarations backed by the canonical ``CropCycle``.

The crop-label collection is an audit/training-candidate store. It is not the
runtime crop authority consumed by an AgriBrain run. This module closes that
gap by placing a farmer declaration on the same active ``CropCycle`` that the
Next.js run route reads.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from services.agribrain.common.plot_namespace import PlotNamespace


CROP_RUNTIME_DECLARATION_VERSION = "crop_runtime_declaration_v1"
FARMER_DECLARATION_AUTHORITY = "FARMER_CONFIRMED"
FARMER_DECLARATION_SOURCE = "authenticated_farmer_crop_identity"
TERMINAL_CROP_CYCLE_STATUSES = frozenset({"FAILED", "HARVESTED"})
ACTIVE_CROP_CYCLE_STATUSES = frozenset({
    "PLANNED",
    "PLANTED",
    "GROWING",
    "FLOWERING",
    "FRUITING",
    "READY_TO_HARVEST",
})


def _canonical_hash(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _iso(value: datetime) -> str:
    normalized = value
    if normalized.tzinfo is None:
        normalized = normalized.replace(tzinfo=timezone.utc)
    return normalized.astimezone(timezone.utc).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


def normalize_declared_crop_code(value: Any) -> str:
    return (
        str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    )


def _mongo_identity(value: str) -> Any:
    """Use ObjectId for production Mongo identifiers, strings for test stores."""

    try:
        from bson import ObjectId

        return ObjectId(value) if ObjectId.is_valid(value) else value
    except ImportError:  # pragma: no cover - bson is installed in production
        return value


@dataclass(frozen=True)
class CropRuntimeDeclarationReceipt:
    tenant_id: str
    farm_id: str
    plot_id: str
    crop_cycle_id: str
    crop_code: str
    authority: str
    declared_at: str
    source: str
    cycle_created: bool
    plant_date_asserted: bool = False
    contract_version: str = CROP_RUNTIME_DECLARATION_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "contract_version": self.contract_version,
            "plot_namespace": {
                "tenant_id": self.tenant_id,
                "farm_id": self.farm_id,
                "plot_id": self.plot_id,
            },
            "crop_cycle_id": self.crop_cycle_id,
            "crop_code": self.crop_code,
            "authority": self.authority,
            "declared_at": self.declared_at,
            "source": self.source,
            "cycle_created": self.cycle_created,
            # A crop identity declaration never manufactures planting evidence.
            "plant_date_asserted": self.plant_date_asserted,
        }
        return {**payload, "content_hash": _canonical_hash(payload)}


def persist_farmer_crop_declaration(
    database: Any,
    *,
    namespace: PlotNamespace,
    crop_code: str,
    declared_at: Optional[datetime] = None,
) -> CropRuntimeDeclarationReceipt:
    """Persist a farmer declaration on the active canonical crop cycle.

    Active-cycle selection mirrors ``/api/agribrain/run``: newest ``updatedAt``
    among non-terminal cycles. Existing planting evidence is preserved. A
    newly created cycle has explicitly unknown/null planting fields because
    declaring crop identity is not declaring a planting date.
    """

    normalized_crop = normalize_declared_crop_code(crop_code)
    if not normalized_crop:
        raise ValueError("crop_code is required")
    if not namespace.is_valid():
        raise ValueError("complete plot namespace is required")

    plot_key = _mongo_identity(namespace.plot_id)
    plot = database["Plot"].find_one({"_id": plot_key})
    if not plot:
        raise LookupError("plot_not_found")
    if str(plot.get("farmId") or "") != namespace.farm_id:
        raise PermissionError("plot_namespace_farm_mismatch")
    farm_key = _mongo_identity(namespace.farm_id)
    farm = database["Farm"].find_one({"_id": farm_key})
    if not farm:
        raise LookupError("farm_not_found")
    if str(farm.get("userId") or "") != namespace.tenant_id:
        raise PermissionError("plot_namespace_tenant_mismatch")

    now = declared_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    cycle_query = {
        "plotId": plot_key,
        # A closed allow-list keeps future/invalid terminal workflow states
        # from silently becoming the current scientific crop cycle.
        "status": {"$in": sorted(ACTIVE_CROP_CYCLE_STATUSES)},
    }
    cycle = database["CropCycle"].find_one(
        cycle_query,
        sort=[("updatedAt", -1)],
    )
    declaration_fields = {
        "cropCode": normalized_crop,
        "declaredCropAuthority": FARMER_DECLARATION_AUTHORITY,
        "declaredCropAt": now,
        "declaredCropSource": FARMER_DECLARATION_SOURCE,
        "updatedAt": now,
    }

    created = cycle is None
    if cycle is None:
        cycle_id = _mongo_identity(uuid.uuid4().hex[:24])
        cycle = {
            "_id": cycle_id,
            "plotId": plot_key,
            **declaration_fields,
            "cropNameAr": None,
            "variety": None,
            "status": "PLANNED",
            "plantDate": None,
            "plantDateStatus": "unknown",
            "plantDateSource": "unknown",
            "plantDateConfidence": None,
            "plantDateMin": None,
            "plantDateMax": None,
            "expectedHarvest": None,
            "actualHarvest": None,
            "createdAt": now,
        }
        database["CropCycle"].insert_one(cycle)
    else:
        cycle_id = cycle["_id"]
        database["CropCycle"].update_one(
            {"_id": cycle_id, "plotId": plot_key},
            {"$set": declaration_fields},
        )

    return CropRuntimeDeclarationReceipt(
        tenant_id=namespace.tenant_id,
        farm_id=namespace.farm_id,
        plot_id=namespace.plot_id,
        crop_cycle_id=str(cycle_id),
        crop_code=normalized_crop,
        authority=FARMER_DECLARATION_AUTHORITY,
        declared_at=_iso(now),
        source=FARMER_DECLARATION_SOURCE,
        cycle_created=created,
        plant_date_asserted=False,
    )


__all__ = [
    "CROP_RUNTIME_DECLARATION_VERSION",
    "FARMER_DECLARATION_AUTHORITY",
    "FARMER_DECLARATION_SOURCE",
    "ACTIVE_CROP_CYCLE_STATUSES",
    "TERMINAL_CROP_CYCLE_STATUSES",
    "CropRuntimeDeclarationReceipt",
    "normalize_declared_crop_code",
    "persist_farmer_crop_declaration",
]
