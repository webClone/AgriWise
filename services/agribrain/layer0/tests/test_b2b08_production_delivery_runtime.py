"""B2B-08A: trust-root provisioning and fail-closed service runtime tests.

The tests deliberately never put a signer private key into the runtime.
They verify startup decisions and server factory injection; a full real
FastAPI/packet-run acceptance belongs to B2B-08B/B2B-08C.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat,
)

from services.agribrain.app import production_delivery_runtime as runtime
from services.agribrain.layer0.durable_revocation_authority import (
    DurableRevocationSnapshot,
)
from services.agribrain.layer0.production_admission import (
    Layer0AdmissionRequiredError,
)
from services.agribrain.layer0.verified_irrigation_contract import (
    VERIFIED_IRRIGATION_PURPOSE,
)


ALL_FLAGS = (
    "AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION",
    "AKALORIS_LAYER0_REQUIRE_SIGNED_INPUTS",
    "AKALORIS_LAYER0_REQUIRE_V3_KMS",
    "AKALORIS_LAYER0_REQUIRE_LIVE_REVOCATION",
    "AKALORIS_LAYER0_REQUIRE_PLOT_SCOPE",
    "AKALORIS_LAYER0_L3_PUBLIC_KEYS_JSON",
    "AKALORIS_LAYER0_L3_DURABLE_REVOCATION_PATH",
)


@pytest.fixture(autouse=True)
def clear_l3_config(monkeypatch):
    for key in ALL_FLAGS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("NODE_ENV", "development")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ENV", "development")


class FakeDatabase:
    def __init__(self, replica_set=True):
        self.commands = []
        self.replica_set = replica_set

    def command(self, cmd):
        self.commands.append(cmd)
        if cmd == "ping":
            return {"ok": 1}
        if cmd == "hello":
            return {"ok": 1, "setName": "rs0"} if self.replica_set else {"ok": 1}
        raise AssertionError("unexpected command")


def _enable_policy(monkeypatch):
    for name in ALL_FLAGS[:5]:
        monkeypatch.setenv(name, "true")


def _write_snapshot(tmp_path, key_status="active", *, aged_seconds=0, revision=0):
    issued = datetime.now(timezone.utc) - timedelta(seconds=aged_seconds)
    snapshot = DurableRevocationSnapshot(
        revision=revision,
        issued_at=issued,
        expires_at=issued + timedelta(hours=1),
        key_statuses={"l3-runtime-key": key_status},
    )
    path = tmp_path / "live_l3_revocation.json"
    path.write_text(json.dumps(snapshot.to_dict()), encoding="utf-8")
    return path


def _config(monkeypatch, tmp_path, *, status="active", aged_seconds=0):
    _enable_policy(monkeypatch)
    private = Ed25519PrivateKey.generate()
    pem = private.public_key().public_bytes(
        Encoding.PEM, PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    start = datetime.now(timezone.utc) - timedelta(days=1)
    end = datetime.now(timezone.utc) + timedelta(days=1)
    entry = {
        "l3-runtime-key": {
            "issuer_id": "trusted-l3-irrigation",
            "source": "sensor_iot",
            "algorithm": "Ed25519",
            "public_key_pem": pem,
            "valid_from": start.isoformat(),
            "valid_until": end.isoformat(),
        }
    }
    monkeypatch.setenv(runtime.KEYS_FLAG, json.dumps(entry))
    path = _write_snapshot(tmp_path, status, aged_seconds=aged_seconds)
    monkeypatch.setenv(runtime.REVOCATION_FLAG, str(path))
    return entry, path


def test_disabled_runtime_does_not_access_database_or_create_verifier():
    db = FakeDatabase()
    assert runtime.bootstrap_server_verified_irrigation(db) is None
    assert db.commands == []


@pytest.mark.parametrize("value", ["gibberish", "maybe", "auto", "enabled"])
def test_unknown_runtime_flag_fails_closed(monkeypatch, value):
    monkeypatch.setenv(runtime.ENABLE_FLAG, value)
    with pytest.raises(Layer0AdmissionRequiredError, match="deployment flag"):
        runtime.bootstrap_server_verified_irrigation(FakeDatabase())


@pytest.mark.parametrize("missing", [
    "AKALORIS_LAYER0_REQUIRE_SIGNED_INPUTS",
    "AKALORIS_LAYER0_REQUIRE_V3_KMS",
    "AKALORIS_LAYER0_REQUIRE_LIVE_REVOCATION",
    "AKALORIS_LAYER0_REQUIRE_PLOT_SCOPE",
])
def test_enabled_runtime_requires_all_trusted_policies(monkeypatch, missing):
    _enable_policy(monkeypatch)
    monkeypatch.delenv(missing)
    with pytest.raises(Layer0AdmissionRequiredError, match="requires signed v3"):
        runtime.bootstrap_server_verified_irrigation(FakeDatabase())


def test_enabled_without_database_fails_before_key_load(monkeypatch):
    _enable_policy(monkeypatch)
    with pytest.raises(Layer0AdmissionRequiredError, match="connected server MongoDB"):
        runtime.bootstrap_server_verified_irrigation(None)


def test_standalone_mongo_rejected(monkeypatch):
    _enable_policy(monkeypatch)
    with pytest.raises(Layer0AdmissionRequiredError, match="transaction-capable replica"):
        runtime.bootstrap_server_verified_irrigation(FakeDatabase(replica_set=False))


def test_key_and_snapshot_required_no_unsafe_fallback(monkeypatch):
    _enable_policy(monkeypatch)
    with pytest.raises(Layer0AdmissionRequiredError, match="public keys and live revocation"):
        runtime.bootstrap_server_verified_irrigation(FakeDatabase())


def test_public_only_key_and_live_revocation_success(monkeypatch, tmp_path):
    _config(monkeypatch, tmp_path)
    observed = {}
    def fake_factory(**kwargs):
        observed.update(kwargs)
        return object()

    monkeypatch.setattr(runtime, "configure_server_delivery_verifier", fake_factory)
    sentinel = runtime.bootstrap_server_verified_irrigation(FakeDatabase())
    assert sentinel is not None
    assert len(observed["public_key_registry"]) == 1
    key = observed["public_key_registry"].get_entry("l3-runtime-key")
    assert key is not None
    assert key.permitted_purposes == frozenset({VERIFIED_IRRIGATION_PURPOSE})
    assert observed["revocation_authority"].check_authority(
        "l3-runtime-key", datetime.now(timezone.utc),
    )[0]


def test_live_revocation_is_rechecked_not_startup_cached(monkeypatch, tmp_path):
    _, path = _config(monkeypatch, tmp_path)
    captured = {}
    def fake_factory(**kwargs):
        captured.update(kwargs)
        return object()
    monkeypatch.setattr(runtime, "configure_server_delivery_verifier", fake_factory)
    runtime.bootstrap_server_verified_irrigation(FakeDatabase())
    authority = captured["revocation_authority"]
    path = _write_snapshot(tmp_path, "revoked", revision=1)
    assert path.is_file()
    ok, reason = authority.check_authority(
        "l3-runtime-key", datetime.now(timezone.utc),
    )
    assert not ok and reason == "issuer_key_revoked"


@pytest.mark.parametrize("status,age", [
    ("revoked", 0),
    ("retired", 0),
    ("active", 900),
])
def test_revoked_retired_or_stale_key_blocks_startup(
    monkeypatch, tmp_path, status, age,
):
    _config(monkeypatch, tmp_path, status=status, aged_seconds=age)
    with pytest.raises(Layer0AdmissionRequiredError, match="not active"):
        runtime.bootstrap_server_verified_irrigation(FakeDatabase())


def test_private_signing_key_config_cannot_enter_verifier(monkeypatch, tmp_path):
    values, _ = _config(monkeypatch, tmp_path)
    values["l3-runtime-key"]["public_key_pem"] = "-----BEGIN PRIVATE KEY-----\nBAD\n-----END PRIVATE KEY-----"
    monkeypatch.setenv(runtime.KEYS_FLAG, json.dumps(values))
    with pytest.raises(Layer0AdmissionRequiredError, match="only accepts public keys"):
        runtime.bootstrap_server_verified_irrigation(FakeDatabase())


def test_duplicate_json_key_id_rejected(monkeypatch, tmp_path):
    values, _ = _config(monkeypatch, tmp_path)
    one = json.dumps(values["l3-runtime-key"])
    monkeypatch.setenv(runtime.KEYS_FLAG, '{"key":' + one + ',"key":' + one + '}')
    with pytest.raises(Layer0AdmissionRequiredError, match="malformed L3 public key"):
        runtime.bootstrap_server_verified_irrigation(FakeDatabase())


def test_no_client_defined_trust_root_in_server_factory(monkeypatch):
    import services.agribrain.layer0.state_engine as engine_module

    captured = {}
    def fake_engine(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(**kwargs)
    monkeypatch.setattr(engine_module, "Layer0StateEngine", fake_engine)
    app = SimpleNamespace(state=SimpleNamespace(layer0_verified_irrigation_verifier="stale"))
    result = runtime.create_server_layer0_state_engine(
        app,
        plot_ownership_store="server-owned-store",
        principal_provider="server-owned-principal",
        positive_admission_verifier="server-owned-state-grants",
    )
    assert result.verified_delivery_verifier is None

    monkeypatch.setenv(runtime.ENABLE_FLAG, "true")
    app.state.layer0_verified_irrigation_verifier = None
    with pytest.raises(Layer0AdmissionRequiredError, match="unavailable"):
        runtime.create_server_layer0_state_engine(
            app,
            plot_ownership_store="server-owned-store",
            principal_provider="server-owned-principal",
            positive_admission_verifier="server-owned-state-grants",
        )
