"""B2B-05 authoritative MongoDB geometry lifecycle with optimistic CAS.

Use only after authenticated plot ownership is established. MongoDB's single
document find_one_and_update is atomic; geometry, hash and version change in
one write. Cache deletion is post-commit best effort: stale epochs are denied
independently by the live ownership verifier.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from bson import ObjectId
from pymongo import ReturnDocument

from .plot_ownership_store import PrismaPlotOwnershipStore
from .spatial_tenant_contract import (
    AuthenticatedPrincipal, ScopedPlotRequest, SpatialTenantDenied,
    authorize_plot_scope, canonical_geometry_hash, normalize_plot_polygon,
)


class PlotGeometryEpochConflict(RuntimeError):
    """Missing owner, stale epoch or contested atomic write."""


@dataclass(frozen=True)
class PlotGeometryEpochReceipt:
    plot_id: str
    tenant_id: str
    geometry_version: int
    geometry_hash: str
    previous_scope_hash: str
    scope_hash: str
    invalidated_cache_entries: int
    cache_invalidation_attempted: bool
    authority: str = "plot_geometry_epoch_only"


def _valid_id(value: str) -> ObjectId:
    if not isinstance(value, str) or not ObjectId.is_valid(value):
        raise PlotGeometryEpochConflict("invalid_plot_or_farm_identity")
    return ObjectId(value)


class PlotGeometryEpochService:
    """A trusted application component, NOT a public write-through utility.

    Mandatory inputs: externally authenticated principal and farm ID from the
    validated internal service namespace. The Mongo collections and broker
    must come from server startup configuration, never the request body.
    """

    def __init__(self, database: Any, broker: Any):
        if database is None or not callable(
            getattr(getattr(broker, "storage", None), "invalidate", None)
        ):
            raise TypeError("trusted_database_and_broker_required")
        self._plots = database["Plot"]
        self._farms = database["Farm"]
        self._users = database["User"]
        self._store = PrismaPlotOwnershipStore(database)
        self._broker = broker
        if not callable(getattr(self._plots, "find_one_and_update", None)):
            raise TypeError("atomic_plot_collection_required")

    def _owner_links(
        self, *, principal: AuthenticatedPrincipal, plot_id: str, farm_id: str,
    ) -> dict:
        """Resolve current Plot → Farm → User and require exact namespace."""
        if (
            not isinstance(principal, AuthenticatedPrincipal)
            or principal.authenticated is not True
            or principal.tenant_id != str(_valid_id(principal.tenant_id))
        ):
            raise PlotGeometryEpochConflict("authenticated_owner_required")
        plot_oid, farm_oid = _valid_id(plot_id), _valid_id(farm_id)
        try:
            doc = self._plots.find_one({"_id": plot_oid})
            if (
                not isinstance(doc, Mapping)
                or doc.get("_id") != plot_oid
                or doc.get("farmId") != farm_oid
                or doc.get("isActive") is not True
                or doc.get("isRevoked") is not False
                or doc.get("deletedAt") is not None
            ):
                raise PlotGeometryEpochConflict("plot_not_owned_or_inactive")
            farm = self._farms.find_one({"_id": farm_oid})
            if (
                not isinstance(farm, Mapping)
                or farm.get("_id") != farm_oid
                or str(farm.get("userId")) != principal.tenant_id
                or farm.get("isActive") is False
                or farm.get("isRevoked") is True
                or farm.get("deletedAt") is not None
            ):
                raise PlotGeometryEpochConflict("plot_farm_owner_mismatch")
            user = self._users.find_one({"_id": _valid_id(principal.tenant_id)})
            if (
                not isinstance(user, Mapping)
                or str(user.get("_id")) != principal.tenant_id
                or user.get("isActive") is not True
            ):
                raise PlotGeometryEpochConflict("inactive_plot_owner")
            return dict(doc)
        except PlotGeometryEpochConflict:
            raise
        except Exception:
            raise PlotGeometryEpochConflict("authoritative_plot_lookup_failed") from None

    @staticmethod
    def _storage_geometry(geojson: Mapping[str, Any]) -> dict[str, Any]:
        polygon = normalize_plot_polygon(geojson)
        if geojson.get("type") == "Feature":
            # Preserve the API's Feature envelope, but never its foreign CRS.
            properties = geojson.get("properties")
            if properties is not None and not isinstance(properties, Mapping):
                raise PlotGeometryEpochConflict("malformed_feature_properties")
            return {
                "type": "Feature", "geometry": polygon,
                "properties": dict(properties or {}),
            }
        return polygon

    def _invalidate_previous_scope(self, scope_hash: str) -> tuple[int, bool]:
        try:
            count = self._broker.storage.invalidate("b2b05_" + scope_hash)
            return max(int(count), 0), True
        except Exception:
            # The commit cannot be rolled back. Every old scope is rejected
            # by a new live authority read even if physical TTL cleanup fails.
            return 0, False

    def initialize_geometry(
        self, *, principal: AuthenticatedPrincipal, plot_id: str,
        farm_id: str, geojson: Mapping[str, Any],
    ) -> PlotGeometryEpochReceipt:
        """Initialize only a genuinely unversioned, authenticated new plot."""
        before = self._owner_links(principal=principal, plot_id=plot_id, farm_id=farm_id)
        if before.get("geometryVersion") is not None or before.get("geometryHash") is not None:
            raise PlotGeometryEpochConflict("plot_geometry_already_initialized")
        geo = self._storage_geometry(geojson)
        digest = canonical_geometry_hash(geo)
        if before.get("geoJson") is not None:
            if canonical_geometry_hash(before["geoJson"]) != digest:
                raise PlotGeometryEpochConflict("initial_geometry_mismatch")
        changed = self._plots.find_one_and_update(
            {
                "_id": _valid_id(plot_id), "farmId": _valid_id(farm_id),
                "isActive": True, "isRevoked": False,
                "geometryVersion": None, "geometryHash": None,
                "geoJson": before.get("geoJson"),
            },
            {"$set": {
                "geoJson": geo, "geometryVersion": 1,
                "geometryHash": digest, "updatedAt": datetime.now(timezone.utc),
            }},
            return_document=ReturnDocument.AFTER,
        )
        if not isinstance(changed, Mapping):
            raise PlotGeometryEpochConflict("plot_geometry_initialization_conflict")
        current = authorize_plot_scope(
            principal,
            ScopedPlotRequest(principal.tenant_id, plot_id, digest, 1),
            self._store.get_active_plot,
        )
        return PlotGeometryEpochReceipt(
            plot_id, principal.tenant_id, 1, digest,
            "", current.scope_hash, 0, False,
        )

    def update_geometry(
        self, *, principal: AuthenticatedPrincipal, plot_id: str,
        farm_id: str, expected_version: int, expected_hash: str,
        geojson: Mapping[str, Any],
    ) -> PlotGeometryEpochReceipt:
        """Atomic compare-and-swap of geometry, hash and monotone version."""
        if type(expected_version) is not int or expected_version < 1:
            raise PlotGeometryEpochConflict("invalid_expected_geometry_epoch")
        before = self._owner_links(principal=principal, plot_id=plot_id, farm_id=farm_id)
        old_scope = authorize_plot_scope(
            principal,
            ScopedPlotRequest(
                principal.tenant_id, plot_id, expected_hash, expected_version,
            ),
            self._store.get_active_plot,
        )
        if before.get("geometryVersion") != expected_version or before.get("geometryHash") != expected_hash:
            raise PlotGeometryEpochConflict("stale_geometry_epoch")
        new_geo = self._storage_geometry(geojson)
        new_hash = canonical_geometry_hash(new_geo)
        if new_hash == expected_hash:
            raise PlotGeometryEpochConflict("unchanged_geometry")
        try:
            changed = self._plots.find_one_and_update(
                {
                    "_id": _valid_id(plot_id), "farmId": _valid_id(farm_id),
                    "isActive": True, "isRevoked": False,
                    "geometryVersion": expected_version,
                    "geometryHash": expected_hash,
                    "geoJson": before.get("geoJson"),
                },
                {
                    "$set": {
                        "geoJson": new_geo, "geometryHash": new_hash,
                        "updatedAt": datetime.now(timezone.utc),
                    },
                    "$inc": {"geometryVersion": 1},
                },
                return_document=ReturnDocument.AFTER,
            )
        except Exception:
            raise PlotGeometryEpochConflict("atomic_geometry_update_failed") from None
        if (
            not isinstance(changed, Mapping)
            or changed.get("geometryVersion") != expected_version + 1
            or changed.get("geometryHash") != new_hash
        ):
            raise PlotGeometryEpochConflict("concurrent_geometry_epoch_conflict")
        new_scope = authorize_plot_scope(
            principal,
            ScopedPlotRequest(
                principal.tenant_id, plot_id, new_hash, expected_version + 1,
            ),
            self._store.get_active_plot,
        )
        invalidated, attempted = self._invalidate_previous_scope(old_scope.scope_hash)
        return PlotGeometryEpochReceipt(
            plot_id, principal.tenant_id, expected_version + 1, new_hash,
            old_scope.scope_hash, new_scope.scope_hash, invalidated, attempted,
        )
