"""Prisma Mongo plot ownership and Layer 0 trusted scoped state admission.

Local Mongo collection doubles; no live database, network, or CI run.
Issuer-purpose signed admission is separately exercised by existing tests.
"""
from datetime import datetime, timezone
import pytest
from bson import ObjectId

from services.agribrain.layer0 import state_engine as engine_module
from services.agribrain.layer0.observation_packet import ObservationPacket, ObservationSource
from services.agribrain.layer0.plot_ownership_store import PrismaPlotOwnershipStore
from services.agribrain.layer0.source_package import Layer0StatePackage
from services.agribrain.layer0.spatial_tenant_contract import (
    AuthenticatedPrincipal, ScopedPlotRequest, authorize_plot_scope,
    canonical_geometry_hash, verify_pixel_footprint,
)
from services.agribrain.layer0.production_admission import Layer0AdmissionRequiredError

P = ObjectId("100000000000000000000001")
F = ObjectId("200000000000000000000002")
U = ObjectId("300000000000000000000003")
OTHER = ObjectId("400000000000000000000004")


def box(w=3, s=36, e=3.002, n=36.002):
    return {"type": "Polygon", "coordinates": [[
        [w, s], [e, s], [e, n], [w, n], [w, s],
    ]]}


G = box()
H = canonical_geometry_hash(G)


class Collection:
    def __init__(self, docs):
        self.docs = docs
        self.queries = []

    def find_one(self, query):
        self.queries.append(dict(query))
        return next(
            (doc for doc in self.docs if all(doc.get(k) == v for k, v in query.items())),
            None,
        )


def database():
    return {
        "Plot": Collection([{
            "_id": P, "farmId": F, "geoJson": G, "area": 0.04,
            "geometryVersion": 2, "geometryHash": H,
            "isActive": True, "isRevoked": False,
        }]),
        "Farm": Collection([{"_id": F, "userId": U}]),
        "User": Collection([{"_id": U, "isActive": True}]),
    }


def principal():
    return AuthenticatedPrincipal(str(U), "trusted-subject", True)


def scope(db):
    return authorize_plot_scope(
        principal(), ScopedPlotRequest(str(U), str(P), H, 2),
        PrismaPlotOwnershipStore(db).get_active_plot,
    )


def packet(verified, footprint=None):
    support = verify_pixel_footprint(
        verified, footprint or box(3.0002, 36.0002, 3.0004, 36.0004),
    )
    p = ObservationPacket(
        source=ObservationSource.WEATHER_REANALYSIS, plot_id=str(P),
        timestamp=datetime(2026, 11, 1, 12, tzinfo=timezone.utc),
        payload={"temp_max": 25, "temp_min": 5, "precipitation": 0, "et0": 2},
    )
    p.bind_spatial_context(verified, support)
    return p


@pytest.fixture
def context(monkeypatch):
    # Separate spatial checks from the issuer-signature contract tests.
    monkeypatch.setattr(engine_module, "signed_inputs_required", lambda: False)
    monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_PLOT_SCOPE", "1")
    db = database()
    ver = scope(db)
    e = engine_module.Layer0StateEngine(
        plot_ownership_store=PrismaPlotOwnershipStore(db), principal_provider=principal,
    )
    captures = []

    def fake_run(**kw):
        captures.append(kw)
        return Layer0StatePackage(
            plot_id=kw["plot_id"], geometry_hash=kw["geometry_hash"],
            geometry_version=kw["geometry_version"],
            health_report={}, provenance={},
        )

    e.run = fake_run
    return db, ver, e, captures


def invoke(ctx, packets, **override):
    db, ver, engine, captures = ctx
    args = dict(
        plot_id=str(P), packets=packets, start_date="2026-11-01",
        end_date="2026-11-01", geometry_hash=H, geometry_version=2,
        tenant_id=str(U), scope_hash=ver.scope_hash,
    )
    args.update(override)
    return engine.run_from_packets(**args)


def test_actual_prisma_collection_names_and_objectid_owner_join():
    db = database()
    own = PrismaPlotOwnershipStore(db).get_active_plot(str(P))
    assert own.tenant_id == str(U)
    assert own.geometry_hash == H and own.geometry_version == 2
    assert db["Plot"].queries == [{"_id": P}]
    assert db["Farm"].queries == [{"_id": F}]
    assert db["User"].queries == [{"_id": U}]


@pytest.mark.parametrize("change", [
    lambda d: d["Plot"].docs[0].pop("geometryVersion"),
    lambda d: d["Plot"].docs[0].pop("geometryHash"),
    lambda d: d["Plot"].docs[0].update(geometryHash="f" * 64),
    lambda d: d["Plot"].docs[0].update(geometryVersion=True),
    lambda d: d["Plot"].docs[0].update(isActive=False),
    lambda d: d["Plot"].docs[0].update(isRevoked=True),
    lambda d: d["Plot"].docs[0].update(deletedAt=datetime.now(timezone.utc)),
    lambda d: d["Plot"].docs[0].update(geoJson={"type": "Point", "coordinates": [3, 36]}),
    lambda d: d["Farm"].docs[0].update(userId=OTHER),
    lambda d: d["User"].docs[0].update(isActive=False),
])
def test_stale_missing_revoked_or_foreign_plot_authority_fails_closed(change):
    db = database()
    change(db)
    assert PrismaPlotOwnershipStore(db).get_active_plot(str(P)) is None


def test_invalid_objectid_is_denied():
    assert PrismaPlotOwnershipStore(database()).get_active_plot("not-a-mongo-id") is None


def test_scoped_packet_is_admitted_with_live_owner_and_epoch(context):
    db, verified, engine, calls = context
    result = invoke(context, [packet(verified)])
    assert calls[0]["plot_id"] == str(P)
    assert calls[0]["daily_weather"]["2026-11-01"]["precipitation"] == 0
    assert result.health_report["b2b05_scope_mode"] == "TRUSTED_ACTIVE_PLOT_SCOPE"


def test_foreign_tenant_packet_cannot_inject_weather(context):
    db, verified, engine, calls = context
    p = packet(verified)
    p.tenant_id = str(OTHER)
    p.content_hash = p._generate_content_hash()
    result = invoke(context, [p])
    assert calls[0]["daily_weather"] == {}
    assert result.health_report["state_packets_excluded_by_status"]["skipped_foreign_tenant"] == 1


def test_deserialized_spatial_claim_cannot_inject_weather(context):
    db, verified, engine, calls = context
    bound = packet(verified)
    forged = ObservationPacket(
        source=bound.source, plot_id=bound.plot_id, timestamp=bound.timestamp,
        geometry_hash=bound.geometry_hash, geometry_version=bound.geometry_version,
        tenant_id=bound.tenant_id, scope_hash=bound.scope_hash,
        spatial_provenance=dict(bound.spatial_provenance), payload=dict(bound.payload),
    )
    assert forged._spatial_binding_verified is False
    result = invoke(context, [forged])
    assert calls[0]["daily_weather"] == {}
    assert result.health_report["state_packets_excluded_by_status"]["skipped_unverified_spatial_scope"] == 1


def test_fractional_pixel_packet_cannot_inject_weather(context):
    db, verified, engine, calls = context
    p = packet(verified, box(3.0019, 36.0005, 3.0023, 36.0009))
    assert p.spatial_provenance["spatial_classification"] == "FRACTIONAL_BOUNDARY"
    result = invoke(context, [p])
    assert calls[0]["daily_weather"] == {}
    assert result.health_report["state_packets_excluded_by_status"]["skipped_unverified_spatial_scope"] == 1


@pytest.mark.parametrize("overrides", [
    {"tenant_id": str(OTHER)}, {"scope_hash": "forged"},
    {"geometry_hash": "stale"}, {"geometry_version": 3},
    {"scope_hash": ""}, {"tenant_id": ""},
])
def test_foreign_or_missing_caller_scope_fails_before_run(context, overrides):
    db, verified, engine, calls = context
    with pytest.raises(Layer0AdmissionRequiredError):
        invoke(context, [packet(verified)], **overrides)
    assert calls == []


def test_direct_scalar_run_is_blocked_under_strict_plot_scope(context):
    db, verified, engine, calls = context
    with pytest.raises(Layer0AdmissionRequiredError):
        engine_module.Layer0StateEngine.run(
            engine, plot_id=str(P), start_date="2026-11-01",
            end_date="2026-11-01", daily_weather={},
            observations_by_day={}, events_by_day={},
        )


def test_geometry_epoch_change_during_state_run_blocks_release(context):
    db, verified, engine, calls = context
    previous = engine.run
    def change_owner(**kw):
        output = previous(**kw)
        db["Plot"].docs[0]["geometryVersion"] += 1
        return output
    engine.run = change_owner
    with pytest.raises(Layer0AdmissionRequiredError):
        invoke(context, [packet(verified)])
    assert len(calls) == 1


def test_missing_trusted_store_denies_scoped_state_run(context):
    db, verified, engine, calls = context
    engine._plot_ownership_store = None
    with pytest.raises(Layer0AdmissionRequiredError):
        invoke(context, [packet(verified)])
    assert not calls


def test_legacy_run_never_admits_scoped_packet_claims(context, monkeypatch):
    db, verified, engine, calls = context
    monkeypatch.delenv("AKALORIS_LAYER0_REQUIRE_PLOT_SCOPE", raising=False)
    result = invoke(context, [packet(verified)], tenant_id="", scope_hash="")
    assert calls[0]["daily_weather"] == {}
    assert result.health_report["state_packets_excluded_by_status"]["skipped_unverified_spatial_scope"] == 1
