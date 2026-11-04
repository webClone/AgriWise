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


class PrismaPlotOwnershipStore:
    """Read the *actual* Prisma MongoDB Plot -> Farm -> User relationship.

    Prisma models in this repository map to Mongo collections "Plot", "Farm",
    "User" (case-sensitive); not assumed lowercase "plots"/"farms".

    plot.geometryVersion, geometryHash, isActive and isRevoked are required
    migration/ownership-write fields, even if the Prisma schema supplies
    application defaults. Existing unbackfilled documents FAIL CLOSED.

    The adapter accepts a trusted pymongo Database, or a collection provider
    exposing db["Plot"], db["Farm"], and db["User"]. No HTTP body metadata is
    ever used as an owner proof. It does not cache identities.
    """

    def __init__(self, database: Any):
        if database is None:
            raise TypeError("authoritative_prisma_mongodb_required")
        try:
            self._plots = database["Plot"]
            self._farms = database["Farm"]
            self._users = database["User"]
            if not all(callable(getattr(c, "find_one", None)) for c in (
                self._plots, self._farms, self._users
            )):
                raise TypeError("invalid_prisma_collections")
        except (KeyError, AttributeError, TypeError):
            raise TypeError("authoritative_prisma_mongodb_required") from None

    def get_active_plot(self, plot_id: str) -> PlotOwnershipRecord | None:
        """Perform current linked lookups; reject missing, revoked, or stale epochs."""
        from .spatial_tenant_contract import canonical_geometry_hash

        if not isinstance(plot_id, str) or len(plot_id) != 24:
            return None
        try:
            from bson import ObjectId
            if not ObjectId.is_valid(plot_id):
                return None
            key = ObjectId(plot_id)
            plot = self._plots.find_one({"_id": key})
            if not isinstance(plot, Mapping):
                return None
            if (
                str(plot.get("_id")) != plot_id
                or plot.get("isActive") is not True
                or plot.get("isRevoked") is not False
                or plot.get("deletedAt") is not None
            ):
                return None

            farm_id = plot.get("farmId")
            if not isinstance(farm_id, ObjectId):
                return None
            farm = self._farms.find_one({"_id": farm_id})
            if not isinstance(farm, Mapping) or farm.get("_id") != farm_id:
                return None
            if (
                farm.get("isActive") is False
                or farm.get("isRevoked") is True
                or farm.get("deletedAt") is not None
            ):
                return None

            user_id = farm.get("userId")
            if not isinstance(user_id, ObjectId):
                return None
            user = self._users.find_one({"_id": user_id})
            if (
                not isinstance(user, Mapping)
                or user.get("_id") != user_id
                or user.get("isActive") is not True
            ):
                return None

            version = plot.get("geometryVersion")
            persisted_hash = plot.get("geometryHash")
            geometry = plot.get("geoJson")
            if (
                type(version) is not int or version <= 0
                or not isinstance(persisted_hash, str)
                or len(persisted_hash) != 64
                or not isinstance(geometry, Mapping)
            ):
                return None
            from .spatial_tenant_contract import normalize_plot_polygon
            canonical_polygon = normalize_plot_polygon(geometry)
            computed = canonical_geometry_hash(canonical_polygon)
            if persisted_hash != computed:
                return None
            return PlotOwnershipRecord(
                tenant_id=str(user_id), plot_id=plot_id,
                geometry_version=version, geometry_hash=computed,
                polygon_geojson=canonical_polygon,
            )
        except Exception:
            # Never fall back to request-supplied geometry or previous ownership.
            return None
