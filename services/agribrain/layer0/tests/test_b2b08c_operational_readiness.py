"""B2B-08C-I: non-secret operational readiness and fail-closed gates."""
from types import SimpleNamespace

import pytest
from services.agribrain.app import layer0_operational_readiness as ops


class FakeMongo:
    def __init__(self, *, reachable=True, sessions=True, replica=True):
        self.reachable = reachable
        self.sessions = sessions
        self.replica = replica
        self.client = SimpleNamespace(start_session=lambda: None) if sessions else object()
        self.commands = []

    def command(self, name):
        self.commands.append(name)
        if not self.reachable:
            raise RuntimeError("never reveal mongo_uri/password")
        if name == "ping":
            return {"ok": 1}
        if name == "hello":
            return {
                "setName": "rs0" if self.replica else None,
                "logicalSessionTimeoutMinutes": 30 if self.sessions else None,
            }
        raise AssertionError(name)


@pytest.fixture(autouse=True)
def strict_flags(monkeypatch):
    for flag in (
        "AKALORIS_LAYER0_REQUIRE_SIGNED_INPUTS",
        "AKALORIS_LAYER0_REQUIRE_V3_KMS",
        "AKALORIS_LAYER0_REQUIRE_LIVE_REVOCATION",
        "AKALORIS_LAYER0_REQUIRE_PLOT_SCOPE",
        "AKALORIS_LAYER0_ENABLE_SCOPED_PACKET_RUN",
        "AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION",
    ):
        monkeypatch.setenv(flag, "true")
    monkeypatch.setenv("NODE_ENV", "development")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ENV", "development")


def app_configured():
    return SimpleNamespace(state=SimpleNamespace(
        layer0_packet_ownership_store=SimpleNamespace(get_active_plot=lambda x: None),
        layer0_positive_admission_verifier=object(),
        layer0_verified_irrigation_verifier=object(),
    ))


def test_ready_requires_both_live_source_and_delivery_checks(monkeypatch):
    monkeypatch.setattr(ops, "_source_trust_ready", lambda verifier, now: True)
    monkeypatch.setattr(ops, "_delivery_trust_ready", lambda verifier, db, now: True)
    result = ops.assess_layer0_operational_readiness(app_configured(), FakeMongo())
    assert result["ready"] is True
    assert result["mongo_transaction_executed"] is False
    assert result["scientific_publication_authorized"] is False
    assert result["actuator_control_authorized"] is False


@pytest.mark.parametrize("failure", ["source", "delivery", "mongo", "standalone", "sessions", "ownership"])
def test_lost_authority_or_transaction_topology_returns_not_ready(monkeypatch, failure):
    monkeypatch.setattr(ops, "_source_trust_ready", lambda verifier, now: failure != "source")
    monkeypatch.setattr(ops, "_delivery_trust_ready", lambda verifier, db, now: failure != "delivery")
    database = FakeMongo(
        reachable=failure != "mongo",
        sessions=failure != "sessions",
        replica=failure != "standalone",
    )
    app = app_configured()
    if failure == "ownership":
        app.state.layer0_packet_ownership_store = None
    result = ops.assess_layer0_operational_readiness(app, database)
    assert result["ready"] is False


def test_disabled_runtime_is_not_reported_ready(monkeypatch):
    monkeypatch.setenv("AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION", "false")
    monkeypatch.setattr(ops, "_source_trust_ready", lambda v, n: True)
    result = ops.assess_layer0_operational_readiness(app_configured(), FakeMongo())
    assert result["ready"] is False
    assert result["components"]["verified_delivery_runtime"] == "disabled"


def test_invalid_flag_fails_closed_without_echoing_config(monkeypatch):
    monkeypatch.setenv("AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION", "surprise-secret")
    result = ops.assess_layer0_operational_readiness(app_configured(), FakeMongo())
    assert not result["ready"]
    assert "surprise-secret" not in str(result)


def test_report_has_fixed_allowlisted_shape_no_sensitive_material(monkeypatch):
    monkeypatch.setattr(ops, "_source_trust_ready", lambda v, n: True)
    monkeypatch.setattr(ops, "_delivery_trust_ready", lambda v, db, n: True)
    report = ops.assess_layer0_operational_readiness(app_configured(), FakeMongo())
    assert set(report) == {
        "contract", "ready", "components", "mongo_transaction_executed",
        "field_calibration_qualified", "scientific_publication_authorized",
        "actuator_control_authorized",
    }
    assert set(report["components"]) == {
        "mongo_connection", "mongo_transaction_topology", "signed_scope_policy",
        "plot_ownership", "scoped_packet_runtime", "verified_delivery_runtime",
        "source_live_revocation", "delivery_live_revocation",
    }
    assert set(report["components"].values()) <= {"ready", "unavailable", "disabled"}


def test_source_or_delivery_probe_exception_cannot_mark_ready(monkeypatch):
    def broken(*args):
        raise RuntimeError("secret key bytes must stay internal")
    monkeypatch.setattr(ops, "_source_trust_ready", broken)
    monkeypatch.setattr(ops, "_delivery_trust_ready", broken)
    result = ops.assess_layer0_operational_readiness(app_configured(), FakeMongo())
    assert not result["ready"]
    assert "secret" not in str(result)
