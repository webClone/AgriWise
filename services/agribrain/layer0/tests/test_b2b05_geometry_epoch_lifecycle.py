"""B2B-05 startup identity context, Prisma-Mongo CAS and cache epoch lifecycle.

All Mongo operations use synchronous in-memory collection doubles; these
tests do not claim a live Mongo/Next.js deployment or a full FastAPI smoke.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from bson import ObjectId

from services.agribrain.app.plot_scope_context import (
    bind_authenticated_plot_namespace, current_authenticated_plot_principal,
)
from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.layer0.data_gateway import request_broker as broker_module
from services.agribrain.layer0.data_gateway.request_broker import DataRequestBroker
from services.agribrain.layer0.plot_geometry_epoch import (
    PlotGeometryEpochService, PlotGeometryEpochConflict,
)
from services.agribrain.layer0.plot_ownership_store import PrismaPlotOwnershipStore
from services.agribrain.layer0.spatial_tenant_contract import (
    AuthenticatedPrincipal, ScopedPlotRequest, SpatialTenantDenied,
    canonical_geometry_hash, normalize_plot_polygon,
)

P = ObjectId("100000000000000000000001")
F = ObjectId("200000000000000000000002")
U = ObjectId("300000000000000000000003")
OTHER = ObjectId("400000000000000000000004")


def polygon(w=3.0, s=36.0, e=3.002, n=36.002):
    return {"type": "Polygon", "coordinates": [[
        [w, s], [e, s], [e, n], [w, n], [w, s],
    ]]}


def feature(geom=None):
    return {"type": "Feature", "geometry": geom or polygon(), "properties": {"crop": "wheat"}}


class Collection:
    def __init__(self, docs):
        self.rows = docs
        self.writes = 0
        self.race = False

    def find_one(self, query):
        return next((row for row in self.rows
            if all(row.get(key) == val for key, val in query.items())), None)

    def find_one_and_update(self, query, update, return_document=None):
        if self.race:
            self.rows[0]["geometryVersion"] = 99
            return None
        row = self.find_one(query)
        if row is None:
            return None
        for field, value in update.get("$set", {}).items():
            row[field] = value
        for field, value in update.get("$inc", {}).items():
            row[field] = row[field] + value
        self.writes += 1
        return dict(row)


class Storage:
    def __init__(self):
        self.entries = {}
        self.fetch_count = 0
        self.invalidations = []

    def get_or_fetch(self, *, source, plot_id, lat, lng, fetch_fn,
                     force_refresh=False, context=None, param_hash="",
                     candidate_validator=None):
        key = (plot_id, source, param_hash)
        if not force_refresh and key in self.entries:
            return self.entries[key]
        self.fetch_count += 1
        result = fetch_fn(lat, lng)
        self.entries[key] = result
        return result

    def invalidate(self, plot_id, source=None):
        self.invalidations.append(plot_id)
        keys = [key for key in self.entries if key[0] == plot_id]
        for key in keys:
            del self.entries[key]
        return len(keys)


def registry(initial=None):
    initial = initial or feature()
    return {
        "Plot": Collection([{
            "_id": P, "farmId": F, "geoJson": initial, "area": 0.04,
            "isActive": True, "isRevoked": False,
        }]),
        "Farm": Collection([{"_id": F, "userId": U}]),
        "User": Collection([{"_id": U, "isActive": True}]),
    }


def namespace():
    return PlotNamespace(tenant_id=str(U), farm_id=str(F), plot_id=str(P))


def principal():
    return AuthenticatedPrincipal(str(U), "trusted-signer", True)


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_PLOT_SCOPE", "1")
    db = registry()
    storage = Storage()
    broker = DataRequestBroker.__new__(DataRequestBroker)
    broker._storage = storage
    broker._consolidator = SimpleNamespace(should_consolidate=lambda source: False)
    broker.configure_plot_authority(
        PrismaPlotOwnershipStore(db), current_authenticated_plot_principal,
    )
    monkeypatch.setattr(
        broker_module, "get_fetch_fn",
        lambda source: lambda lat, lng, **kw: {"data": [{"observation": 1.0}]},
    )
    monkeypatch.setattr(broker_module.external_provider_circuit, "before_request", lambda source: None)
    monkeypatch.setattr(broker_module.external_provider_circuit, "record_success", lambda source: None)
    manager = PlotGeometryEpochService(db, broker)
    return db, storage, broker, manager


def initialize(manager):
    return manager.initialize_geometry(
        principal=principal(), plot_id=str(P), farm_id=str(F), geojson=feature(),
    )


def update(manager, version, digest, new_polygon):
    return manager.update_geometry(
        principal=principal(), plot_id=str(P), farm_id=str(F),
        expected_version=version, expected_hash=digest, geojson=new_polygon,
    )


def test_signed_request_principal_isolated_and_reset():
    with pytest.raises(SpatialTenantDenied):
        current_authenticated_plot_principal()
    with bind_authenticated_plot_namespace(namespace(), signature_verified=True):
        assert current_authenticated_plot_principal().tenant_id == str(U)
        with bind_authenticated_plot_namespace(namespace(), signature_verified=False):
            with pytest.raises(SpatialTenantDenied):
                current_authenticated_plot_principal()
        assert current_authenticated_plot_principal().tenant_id == str(U)
    with pytest.raises(SpatialTenantDenied):
        current_authenticated_plot_principal()


def test_feature_geometry_hash_matches_polygon_and_excludes_properties():
    f = feature()
    assert canonical_geometry_hash(f) == canonical_geometry_hash(f["geometry"])
    assert normalize_plot_polygon(f)["type"] == "Polygon"
    f["properties"]["crop"] = "barley"
    assert canonical_geometry_hash(f) == canonical_geometry_hash(polygon())


def test_initialize_then_fetch_then_atomic_update_invalidates_old_scoped_cache(env):
    db, storage, broker, manager = env
    with bind_authenticated_plot_namespace(namespace(), signature_verified=True):
        initial = initialize(manager)
        assert initial.geometry_version == 1
        assert initial.previous_scope_hash == ""
        assert db["Plot"].rows[0]["geometryHash"] == initial.geometry_hash
        old_request = ScopedPlotRequest(str(U), str(P), initial.geometry_hash, 1)
        old_data = broker.get(
            "openweather_current", str(P), 36.001, 3.001,
            plot_scope=old_request,
        )
        assert old_data is not None
        old_key = "b2b05_" + initial.scope_hash
        assert any(key[0] == old_key for key in storage.entries)
        new = update(manager, 1, initial.geometry_hash,
                     feature(polygon(2.999, 35.999, 3.003, 36.003)))
        assert new.geometry_version == 2
        assert new.previous_scope_hash == initial.scope_hash
        assert new.invalidated_cache_entries == 1
        assert old_key in storage.invalidations
        assert not any(key[0] == old_key for key in storage.entries)
        assert broker.get(
            "openweather_current", str(P), 36.001, 3.001,
            plot_scope=old_request,
        ) is None
        new_request = ScopedPlotRequest(str(U), str(P), new.geometry_hash, 2)
        assert broker.get(
            "openweather_current", str(P), 36.001, 3.001,
            plot_scope=new_request,
        ) is not None
        assert storage.fetch_count == 2


def test_concurrent_stale_epoch_rejected_without_double_write(env):
    db, storage, broker, manager = env
    init = initialize(manager)
    update(manager, 1, init.geometry_hash, polygon(2.999, 35.999, 3.003, 36.003))
    with pytest.raises((PlotGeometryEpochConflict, SpatialTenantDenied)):
        update(manager, 1, init.geometry_hash, polygon(2.998, 35.998, 3.004, 36.004))
    assert db["Plot"].writes == 2


def test_failing_cas_does_not_claim_success_or_invalidate(env):
    db, storage, broker, manager = env
    initial = initialize(manager)
    db["Plot"].race = True
    with pytest.raises(PlotGeometryEpochConflict):
        update(manager, 1, initial.geometry_hash, polygon(2.999, 35.999, 3.003, 36.003))
    assert not storage.invalidations


@pytest.mark.parametrize("mutation", [
    lambda db: db["Plot"].rows[0].update(isRevoked=True),
    lambda db: db["Plot"].rows[0].update(isActive=False),
    lambda db: db["Farm"].rows[0].update(userId=OTHER),
    lambda db: db["User"].rows[0].update(isActive=False),
])
def test_revoked_plot_or_foreign_owner_cannot_mutate_geometry(env, mutation):
    db, storage, broker, manager = env
    initial = initialize(manager)
    mutation(db)
    with pytest.raises((PlotGeometryEpochConflict, SpatialTenantDenied)):
        update(manager, 1, initial.geometry_hash, polygon(2.999, 35.999, 3.003, 36.003))
    assert db["Plot"].writes == 1


def test_malformed_or_wrong_crs_geometry_cannot_be_initialized(env):
    db, storage, broker, manager = env
    invalid = feature()
    invalid["crs"] = {"type": "name", "properties": {"name": "EPSG:3857"}}
    with pytest.raises((PlotGeometryEpochConflict, SpatialTenantDenied)):
        manager.initialize_geometry(
            principal=principal(), plot_id=str(P), farm_id=str(F), geojson=invalid,
        )
    assert db["Plot"].writes == 0


def test_uninitialized_legacy_plot_cannot_be_reassigned_new_polygon(env):
    db, storage, broker, manager = env
    with pytest.raises(PlotGeometryEpochConflict, match="initial_geometry_mismatch"):
        manager.initialize_geometry(
            principal=principal(), plot_id=str(P), farm_id=str(F),
            geojson=polygon(2.99, 35.99, 3.003, 36.003),
        )
    assert db["Plot"].writes == 0


def test_unsigned_context_never_gets_broker_plot_access(env):
    db, storage, broker, manager = env
    initial = initialize(manager)
    with bind_authenticated_plot_namespace(namespace(), signature_verified=False):
        assert broker.get(
            "openweather_current", str(P), 36.001, 3.001,
            plot_scope=ScopedPlotRequest(str(U), str(P), initial.geometry_hash, 1),
        ) is None
    assert storage.entries == {}
