"""B2B-05 scoped broker + plot registry + packet admission counterexamples.

No external network or production DB is used: trusted adapters are controlled
in memory. Separate deployment must bind actual Prisma authoritative records.
"""
from contextvars import ContextVar
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from services.agribrain.layer0.data_gateway import request_broker as broker_module
from services.agribrain.layer0.data_gateway.request_broker import DataRequestBroker
from services.agribrain.layer0.data_gateway.request_consolidator import RequestConsolidator
from services.agribrain.layer0.observation_packet import ObservationPacket
from services.agribrain.layer0.plot_ownership_store import CollectionPlotOwnershipStore
from services.agribrain.layer0.spatial_tenant_contract import (
    AuthenticatedPrincipal, ScopedPlotRequest, SpatialTenantDenied,
    authorize_plot_scope, canonical_geometry_hash, verify_pixel_footprint,
)


def poly(w=3.0, s=36.0, e=3.002, n=36.002):
    return {"type": "Polygon", "coordinates": [[
        [w, s], [e, s], [e, n], [w, n], [w, s],
    ]]}


PLOT = poly()
DIGEST = canonical_geometry_hash(PLOT)
CURRENT = ContextVar("b2b05_current_authenticated_principal", default=None)


class Collection:
    def __init__(self):
        self.rows = {
            "plot-A": {
                "plot_id": "plot-A", "tenant_id": "tenant-A",
                "active": True, "revoked": False,
                "geometry_version": 1, "geometry_hash": DIGEST,
                "polygon_geojson": PLOT,
            },
            "plot-B": {
                "plot_id": "plot-B", "tenant_id": "tenant-B",
                "active": True, "revoked": False,
                "geometry_version": 1, "geometry_hash": DIGEST,
                "polygon_geojson": PLOT,
            },
        }
        self.reads = 0

    def find_one(self, query):
        self.reads += 1
        row = self.rows.get(query.get("plot_id"))
        if not row:
            return None
        if any(row.get(k) != v for k, v in query.items()):
            return None
        return row


class Storage:
    def __init__(self):
        self.entries = {}
        self.reads = []
        self.fetches = 0
        self.archive_queries = []
        self.invalidations = []

    def get_or_fetch(self, *, source, plot_id, lat, lng, fetch_fn,
                     force_refresh=False, context=None, param_hash="",
                     candidate_validator=None):
        key = (plot_id, source, round(lat, 4), round(lng, 4), param_hash)
        self.reads.append(key)
        if not force_refresh and key in self.entries:
            return self.entries[key]
        self.fetches += 1
        result = fetch_fn(lat, lng)
        if result is not None:
            self.entries[key] = result
        return result

    def get_freshness_report(self, plot_id, sources=None):
        self.reads.append(("freshness", plot_id))
        return {}

    def invalidate(self, plot_id, source=None):
        self.invalidations.append(plot_id)
        return 1

    def query_archive(self, plot_id, **kwargs):
        self.archive_queries.append(plot_id)
        return []


def scope(plot_id, tenant_id, version=1, digest=DIGEST):
    return ScopedPlotRequest(tenant_id, plot_id, digest, version)


@pytest.fixture
def setup(monkeypatch):
    collection = Collection()
    storage = Storage()
    broker = DataRequestBroker.__new__(DataRequestBroker)
    broker._storage = storage
    broker._consolidator = RequestConsolidator(ttl_seconds=300)
    broker.configure_plot_authority(
        CollectionPlotOwnershipStore(collection), lambda: CURRENT.get(),
    )
    network_requests = []
    def fake_fetch(source):
        if source != "openweather_current":
            return None
        def fetch(lat, lng, **kwargs):
            network_requests.append((lat, lng))
            return {"data": [{"provider_value": 1.0}], "provider": "fake"}
        return fetch
    monkeypatch.setattr(broker_module, "get_fetch_fn", fake_fetch)
    monkeypatch.setattr(
        broker_module.external_provider_circuit, "before_request",
        lambda source: None,
    )
    monkeypatch.setattr(
        broker_module.external_provider_circuit, "record_success",
        lambda source: None,
    )
    monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_PLOT_SCOPE", "1")
    token = CURRENT.set(AuthenticatedPrincipal("tenant-A", "user-A", True))
    yield broker, storage, collection, network_requests
    CURRENT.reset(token)


def test_scoped_broker_success_uses_tenant_and_epoch_cache_namespace(setup):
    broker, storage, _, calls = setup
    result = broker.get("openweather_current", "plot-A", 36.001, 3.001,
                        plot_scope=scope("plot-A", "tenant-A"))
    assert result and result["provider"] == "fake"
    assert storage.fetches == 1
    assert calls == [(36.001, 3.001)]
    assert storage.reads[0][0].startswith("b2b05_")
    assert len(storage.reads[0][-1]) == 64
    repeated = broker.get("openweather_current", "plot-A", 36.001, 3.001,
                          plot_scope=scope("plot-A", "tenant-A"))
    assert repeated == result
    assert storage.fetches == 1


@pytest.mark.parametrize("plot_scope", [
    None,
    scope("plot-B", "tenant-B"),
    scope("plot-A", "tenant-B"),
    scope("plot-A", "tenant-A", version=2),
    scope("plot-A", "tenant-A", digest="forged"),
])
def test_rejected_scope_never_reaches_cache_or_provider(setup, plot_scope):
    broker, storage, collection, calls = setup
    result = broker.get("openweather_current", "plot-A", 36.001, 3.001,
                        plot_scope=plot_scope)
    assert result is None
    assert not storage.reads and not calls


def test_unauthenticated_principal_fails_before_cache_lookup(setup):
    broker, storage, _, _ = setup
    token = CURRENT.set(AuthenticatedPrincipal("tenant-A", "anonymous", False))
    try:
        assert broker.get("openweather_current", "plot-A", 36.001, 3.001,
                          plot_scope=scope("plot-A", "tenant-A")) is None
    finally:
        CURRENT.reset(token)
    assert not storage.reads


def test_neighbour_coordinate_outside_authorized_polygon_is_denied(setup):
    broker, storage, _, calls = setup
    assert broker.get("openweather_current", "plot-A", 36.2, 3.2,
                      plot_scope=scope("plot-A", "tenant-A")) is None
    assert storage.reads == [] and calls == []


def test_same_coordinate_different_tenant_never_shares_cache_or_batch(setup):
    broker, storage, collection, calls = setup
    a = broker.get("openweather_current", "plot-A", 36.001, 3.001,
                   plot_scope=scope("plot-A", "tenant-A"))
    assert a is not None
    token = CURRENT.set(AuthenticatedPrincipal("tenant-B", "user-B", True))
    try:
        b = broker.get("openweather_current", "plot-B", 36.001, 3.001,
                       plot_scope=scope("plot-B", "tenant-B"))
    finally:
        CURRENT.reset(token)
    assert b is not None
    assert storage.fetches == 2
    assert len(calls) == 2
    assert storage.reads[0][0] != storage.reads[1][0]
    assert storage.reads[0][-1] != storage.reads[1][-1]


def test_geometry_supersession_invalidates_prior_scoped_cache(setup):
    broker, storage, collection, calls = setup
    old = scope("plot-A", "tenant-A")
    assert broker.get("openweather_current", "plot-A", 36.001, 3.001, plot_scope=old)
    row = collection.rows["plot-A"]
    row["geometry_version"] = 2
    row["polygon_geojson"] = poly(2.999, 35.999, 3.003, 36.003)
    row["geometry_hash"] = canonical_geometry_hash(row["polygon_geojson"])
    reads_before = len(storage.reads)
    assert broker.get("openweather_current", "plot-A", 36.001, 3.001,
                      plot_scope=old) is None
    assert len(storage.reads) == reads_before
    new = scope("plot-A", "tenant-A", 2, row["geometry_hash"])
    assert broker.get("openweather_current", "plot-A", 36.001, 3.001,
                      plot_scope=new)
    assert storage.fetches == 2
    assert storage.reads[0][0] != storage.reads[-1][0]


def test_revoked_plot_prevents_warm_and_hot_cache_access(setup):
    broker, storage, collection, calls = setup
    collection.rows["plot-A"]["revoked"] = True
    assert broker.get("openweather_current", "plot-A", 36.001, 3.001,
                      plot_scope=scope("plot-A", "tenant-A")) is None
    assert not storage.reads and not calls


def test_get_bulk_propagates_authenticated_context_into_workers(setup):
    broker, storage, collection, calls = setup
    result = broker.get_bulk(
        ["openweather_current"], "plot-A", 36.001, 3.001,
        plot_scope=scope("plot-A", "tenant-A"),
    )
    assert result["openweather_current"] is not None
    assert storage.fetches == 1


def test_scoped_user_data_write_and_read_surfaces_are_isolated(setup):
    broker, storage, collection, calls = setup
    ingested = []
    class User:
        def __getattr__(self, name):
            def ingest(*args):
                ingested.append((name, args))
                return True
            return ingest
    broker._user_engine = User()
    assert broker.ingest_user_data(
        "user_photo", "plot-A", 36.001, 3.001,
        {"source_type": "forged", "plot_id": "plot-B"},
        plot_scope=scope("plot-A", "tenant-A"),
    )
    assert ingested[0][1][0].startswith("b2b05_")
    assert ingested[0][1][-1]["_b2b05_original_plot_id"] == "plot-A"
    assert broker.freshness("plot-A", plot_scope=scope("plot-A", "tenant-A")) == {}
    assert broker.invalidate("plot-A", plot_scope=scope("plot-A", "tenant-A")) == 1
    assert broker.query_archive("plot-A", plot_scope=scope("plot-A", "tenant-A")) == []
    assert storage.invalidations[-1] == ingested[0][1][0]
    assert storage.archive_queries[-1] == ingested[0][1][0]


def test_unscoped_user_data_and_archive_read_are_denied_in_strict_mode(setup):
    broker, storage, _, _ = setup
    class User:
        def __getattr__(self, name):
            raise AssertionError("untrusted user path was touched")
    broker._user_engine = User()
    # Unknown user handler would otherwise be looked up; authorization goes first.
    assert not broker.ingest_user_data("user_photo", "plot-A", 36.001, 3.001, {})
    assert broker.freshness("plot-A") == {}
    assert broker.invalidate("plot-A") == 0
    assert broker.query_archive("plot-A") == []
    assert not storage.reads and not storage.archive_queries


def test_store_collection_errors_and_missing_required_fields_fail_closed():
    collection = Collection()
    store = CollectionPlotOwnershipStore(collection)
    assert store.get_active_plot("plot-A").tenant_id == "tenant-A"
    collection.rows["plot-A"]["geometry_version"] = True
    assert store.get_active_plot("plot-A") is None
    class Broken:
        def find_one(self, *args):
            raise ConnectionError("registry unavailable")
    assert CollectionPlotOwnershipStore(Broken()).get_active_plot("plot-A") is None


def test_bound_packet_requires_matching_scope_and_full_pixel_support(setup):
    broker, _, collection, _ = setup
    identity = AuthenticatedPrincipal("tenant-A", "user-A", True)
    verified = authorize_plot_scope(identity, scope("plot-A", "tenant-A"),
                                  broker._plot_ownership_store.get_active_plot)
    inside = verify_pixel_footprint(verified, poly(3.0002, 36.0002, 3.0004, 36.0004))
    packet = ObservationPacket(
        timestamp=datetime(2026, 11, 1, tzinfo=timezone.utc),
        plot_id="plot-A", spatial_scope="pixel",
        payload={"ndvi_mean": 0.4},
    )
    prior_hash = packet.content_hash
    packet.bind_spatial_context(verified, inside)
    assert packet.tenant_id == "tenant-A"
    assert packet.scope_hash == verified.scope_hash
    assert packet.content_hash != prior_hash
    assert packet.effective_weight() > 0
    assert packet.to_dict()["spatial_provenance"]["eligible_for_state_grant"] is False
    assert packet.to_dict()["spatial_provenance"]["source_qualified"] is False

    partial = verify_pixel_footprint(verified, poly(3.0019, 36.0005, 3.0023, 36.0009))
    packet2 = ObservationPacket(
        plot_id="plot-A", spatial_scope="pixel", payload={"ndvi_mean": 0.3},
    )
    packet2.bind_spatial_context(verified, partial)
    assert packet2.spatial_provenance["spatial_classification"] == "FRACTIONAL_BOUNDARY"
    assert packet2.effective_weight() == 0
    assert packet2.spatial_provenance["geometry_support_verified"] is False


def test_untrusted_packet_provenance_dict_cannot_self_qualify(setup):
    forged = ObservationPacket(
        plot_id="plot-A", tenant_id="tenant-A", scope_hash="arbitrary",
        spatial_scope="pixel",
        spatial_provenance={
            "tenant_id": "tenant-A", "scope_hash": "arbitrary",
            "spatial_classification": "FULL_CONTAINED",
            "geometry_support_verified": True,
            "source_qualified": False, "eligible_for_state_grant": False,
        },
    )
    assert forged.effective_weight() == 0


def test_foreign_scope_binding_is_rejected(setup):
    broker, _, collection, _ = setup
    verified = authorize_plot_scope(
        AuthenticatedPrincipal("tenant-A", "user-A", True),
        scope("plot-A", "tenant-A"), broker._plot_ownership_store.get_active_plot,
    )
    support = verify_pixel_footprint(verified, poly(3.0002, 36.0002, 3.0004, 36.0004))
    packet = ObservationPacket(plot_id="plot-B")
    with pytest.raises(SpatialTenantDenied):
        packet.bind_spatial_context(verified, support)
