"""Read-only B2B-05 ownership resolver for an authoritative plot registry.

Neither HTTP body tenant IDs nor observation packets can mint ownership.
The collection must be supplied by trusted application infrastructure and
reflect current Prisma plot ownership and geometry epochs.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from .spatial_tenant_contract import PlotOwnershipRecord


class PlotOwnershipStore(Protocol):
    def get_active_plot(self, plot_id: str) -> PlotOwnershipRecord | None:
        """Fresh authoritative read; no stale cache or caller fallback."""


class CollectionPlotOwnershipStore:
    """Mongo-style reference adapter to a trusted plot-authority registry.

    Required fields: plot_id, tenant_id, active=True, revoked=False,
    deleted_at=None, geometry_version, geometry_hash, polygon_geojson.
    This does not automatically connect to frontend Prisma; deployment must
    implement authoritative synchronization or a direct trusted adapter.
    """

    def __init__(self, collection: Any):
        if not callable(getattr(collection, "find_one", None)):
            raise TypeError("trusted_plot_authority_collection_required")
        self._collection = collection

    def get_active_plot(self, plot_id: str) -> PlotOwnershipRecord | None:
        if not isinstance(plot_id, str) or not plot_id or len(plot_id) > 256:
            return None
        try:
            doc = self._collection.find_one({
                "plot_id": plot_id, "active": True, "revoked": False,
            })
        except Exception:
            return None
        if not isinstance(doc, Mapping) or (
            doc.get("plot_id") != plot_id
            or doc.get("active") is not True
            or doc.get("revoked") is not False
            or doc.get("deleted_at") is not None
        ):
            return None
        tenant, version = doc.get("tenant_id"), doc.get("geometry_version")
        digest, geojson = doc.get("geometry_hash"), doc.get("polygon_geojson")
        if (
            not isinstance(tenant, str) or not tenant.strip()
            or type(version) is not int or version <= 0
            or not isinstance(digest, str) or not digest
            or not isinstance(geojson, Mapping)
        ):
            return None
        return PlotOwnershipRecord(
            tenant_id=tenant, plot_id=plot_id,
            geometry_version=version, geometry_hash=digest,
            polygon_geojson=geojson,
        )
