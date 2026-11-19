"""IR04-5CC source-review negative controls for the verifier-only trust boundary.

All signing is test-only with ephemeral Ed25519 private keys. No production
signer, default secret or embedded trust key may be imported from ASMAE.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from services.agribrain.layer05_asmae.resolution import (
    observation_footprint_adapter as adapter,
)
from services.agribrain.layer05_asmae.resolution.admission_trust import (
    ADMISSION_ALGORITHM, ADMISSION_DOMAIN, ADMISSION_PURPOSE,
    CANONICALIZATION_VERSION, TRUST_ENV, canonical_grant_bytes,
    get_trusted_admission_keyring,
)
from services.agribrain.layer05_asmae.resolution.bitemporal_receipt_verifier import (
    verify_bitemporal_replay_receipt,
)
from services.agribrain.world_model.canonical_worldline import (
    CanonicalWorldlineService,
)

TENANT, FARM, PLOT = "tenant-ir04", "farm-ir04", "plot-ir04"
GEOMETRY = "a" * 64
OP_HASH, CAL_HASH = "b" * 64, "c" * 64
T = datetime(2026, 9, 5, 12, tzinfo=timezone.utc)
K = datetime(2026, 9, 20, 12, tzinfo=timezone.utc)


def _scene(sensor="S2"):
    return SimpleNamespace(
        sensor=sensor,
        acquisition_time=T,
        committed_at=K,
        bands={"B08": np.ones((2, 2), dtype=np.float32) * 0.2},
    )


def _trusted(monkeypatch, *, source="S2", configured=True):
    signer = Ed25519PrivateKey.generate()
    public_bytes = signer.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    if configured:
        config = {
            "test-external-layer0-issuer": {
                "public_key_b64": base64.b64encode(public_bytes).decode("ascii"),
                "source": source, "purpose": ADMISSION_PURPOSE,
                "domain": ADMISSION_DOMAIN,
            }
        }
        monkeypatch.setenv(TRUST_ENV, json.dumps(config))
    else:
        monkeypatch.delenv(TRUST_ENV, raising=False)
        monkeypatch.setenv("AKALORIS_LAYER0_ISSUER_KEYS", '{"legacy":"known-secret"}')
    return signer


def _grant(scene, *, signer, purpose=ADMISSION_PURPOSE, domain=ADMISSION_DOMAIN,
           source="S2", now=None):
    issued = now or datetime.now(timezone.utc)
    fields = {
        "algorithm": ADMISSION_ALGORITHM,
        "canonicalization": CANONICALIZATION_VERSION,
        "domain": domain, "purpose": purpose,
        "key_id": "test-external-layer0-issuer", "source": source,
        "tenant_id": TENANT, "farm_id": FARM, "plot_id": PLOT,
        "geometry_hash": GEOMETRY,
        "asset_sha256": adapter.compute_scene_asset_sha256(scene),
        "operator_sha256": OP_HASH,
        "calibrated_operator_sha256": CAL_HASH,
        "observation_valid_time": T.isoformat(),
        "committed_at": K.isoformat(),
        "issued_at": issued.isoformat(),
        "expires_at": (issued + timedelta(days=30)).isoformat(),
    }
    return {
        "grant": fields,
        "signature": base64.b64encode(signer.sign(canonical_grant_bytes(fields))).decode("ascii"),
    }


def _verify(scene, receipt, **updates):
    kwargs = {
        "scene": scene, "tenant_id": TENANT, "farm_id": FARM, "plot_id": PLOT,
        "geometry_sha256": GEOMETRY, "operator_sha256": OP_HASH,
        "calibrated_operator_sha256": CAL_HASH,
        "valid_time": T.isoformat(), "committed_at": K.isoformat(),
    }
    kwargs.update(updates)
    return adapter.verify_scene_admission_receipt(receipt, **kwargs)


def test_valid_external_ed25519_grant_is_verified(monkeypatch):
    signer = _trusted(monkeypatch)
    scene = _scene()
    ok, reason = _verify(scene, _grant(scene, signer=signer))
    assert ok is True
    assert reason == "verified_external_issuer_admission"


def test_production_exposes_no_signing_function_or_default_secret(monkeypatch):
    assert not hasattr(adapter, "create_scene_admission_receipt")
    assert not hasattr(adapter, "DEFAULT_ADMISSION_SECRET")
    assert not hasattr(adapter, "register_trusted_admission_key")
    _trusted(monkeypatch, configured=False)
    assert get_trusted_admission_keyring() == {}
    signer = Ed25519PrivateKey.generate()
    scene = _scene()
    assert _verify(scene, _grant(scene, signer=signer))[0] is False


def test_legacy_public_hmac_keyring_never_grants_authority(monkeypatch):
    _trusted(monkeypatch, configured=False)
    scene = _scene()
    receipt = {"grant": {"key_id": "legacy"}, "mac": "0" * 64}
    assert _verify(scene, receipt) == (False, "invalid_admission_envelope_or_legacy_mac")


@pytest.mark.parametrize("mutation", ["signature", "asset", "purpose", "domain", "source"])
def test_issuer_or_grant_substitution_fails_closed(monkeypatch, mutation):
    signer = _trusted(monkeypatch)
    scene = _scene()
    receipt = _grant(scene, signer=signer)
    if mutation == "signature":
        receipt["signature"] = base64.b64encode(b"\0" * 64).decode("ascii")
    if mutation == "asset":
        scene.bands["B08"][0, 0] = 0.99
    if mutation in ("purpose", "domain", "source"):
        change = {
            "purpose": ("purpose", "diagnostic_only"),
            "domain": ("domain", "akaloris/other-purpose/v1"),
            "source": ("source", "S1"),
        }[mutation]
        # Adversarial issuer signs a wrong-scope grant with a valid private key.
        receipt["grant"][change[0]] = change[1]
        receipt["signature"] = base64.b64encode(
            signer.sign(canonical_grant_bytes(receipt["grant"]))
        ).decode("ascii")
    assert _verify(scene, receipt)[0] is False


def test_wrong_issuer_sensor_scope_is_rejected(monkeypatch):
    signer = _trusted(monkeypatch, source="S1")
    scene = _scene()
    assert _verify(scene, _grant(scene, signer=signer))[0] is False


def test_unconfigured_or_corrupt_verifier_config_fails_closed(monkeypatch):
    signer = _trusted(monkeypatch)
    scene = _scene()
    receipt = _grant(scene, signer=signer)
    monkeypatch.setenv(TRUST_ENV, '{"test-external-layer0-issuer":{"secret_b64":"AAAA"}}')
    assert get_trusted_admission_keyring() == {}
    assert _verify(scene, receipt)[0] is False


def test_grant_expiry_is_required_and_enforced(monkeypatch):
    signer = _trusted(monkeypatch)
    scene = _scene()
    receipt = _grant(scene, signer=signer, now=datetime(2026, 9, 21, tzinfo=timezone.utc))
    assert _verify(scene, receipt, now=datetime(2026, 11, 1, tzinfo=timezone.utc))[0] is False
    receipt["grant"].pop("expires_at")
    assert _verify(scene, receipt)[0] is False


def test_caller_injected_keyring_cannot_override_configured_trust(monkeypatch):
    signer = _trusted(monkeypatch)
    scene = _scene()
    receipt = _grant(scene, signer=signer)
    assert _verify(scene, receipt, trusted_keyring={"attacker": ("S2", b"fake")}) == (
        False, "caller_supplied_trust_forbidden",
    )


def _journal_with_event(tmp_path):
    anchor = tmp_path / "anchor"
    anchor.mkdir()
    worldline = CanonicalWorldlineService(
        root=tmp_path / "journal",
        durable_anchor_root=anchor,
        require_durable_anchor=True,
    )
    worldline.commit_event(
        plot_id=PLOT, tenant_id=TENANT, namespace="default",
        geometry_hash=GEOMETRY, event_type="CROP_POSTERIOR",
        payload={"crop_posterior": {
            "content_hash": "d" * 64, "lineage_id": "s2-day-5",
            "states": {"vigor": 0.72}, "sigmas": {"vigor": 0.04},
        }},
        authority="SCIENTIFIC",
        observation_or_valid_time=T,
        effective_at=K,
    )
    return worldline


def test_journal_replay_receipt_is_reconciled_from_durable_events(tmp_path):
    worldline = _journal_with_event(tmp_path)
    q_T = "2026-09-10T12:00:00Z"
    q_K = "2026-09-21T12:00:00Z"
    context = worldline.hydrate_context(
        PLOT, {"tenant_id": TENANT, "worldline_namespace": "default",
               "geometry_hash": GEOMETRY},
        valid_time_T=q_T, knowledge_cutoff_K=q_K,
    )
    receipt = context["bitemporal_replay_receipt"]
    T_verified, K_verified, reason = verify_bitemporal_replay_receipt(
        receipt, tenant_id=TENANT, plot_id=PLOT,
        geometry_sha256=GEOMETRY, worldline_namespace="default",
        worldline_service=worldline,
    )
    assert (T_verified, K_verified) == (
        "2026-09-10T12:00:00+00:00", "2026-09-21T12:00:00+00:00",
    )
    assert reason == "verified_against_durable_worldline_journal"


def test_forged_future_knowledge_cutoff_cannot_reuse_old_digest(tmp_path):
    worldline = _journal_with_event(tmp_path)
    context = worldline.hydrate_context(
        PLOT, {"tenant_id": TENANT, "worldline_namespace": "default",
               "geometry_hash": GEOMETRY},
        valid_time_T="2026-09-10T12:00:00Z",
        knowledge_cutoff_K="2026-09-21T12:00:00Z",
    )
    forged = deepcopy(context["bitemporal_replay_receipt"])
    forged["query_parameters"]["knowledge_cutoff_time"] = "2026-09-10T12:00:00Z"
    assert verify_bitemporal_replay_receipt(
        forged, tenant_id=TENANT, plot_id=PLOT,
        geometry_sha256=GEOMETRY, worldline_namespace="default",
        worldline_service=worldline,
    )[0] is None


def test_unauthenticated_bare_time_and_unmounted_anchor_fail_closed(tmp_path):
    worldline = _journal_with_event(tmp_path)
    assert verify_bitemporal_replay_receipt(
        {"query_parameters": {"knowledge_cutoff_time": "2099-01-01T00:00:00Z"}},
        tenant_id=TENANT, plot_id=PLOT, geometry_sha256=GEOMETRY,
        worldline_namespace="default", worldline_service=worldline,
    )[0] is None
    context = worldline.hydrate_context(
        PLOT, {"tenant_id": TENANT, "worldline_namespace": "default",
               "geometry_hash": GEOMETRY},
        valid_time_T="2026-09-10T12:00:00Z",
        knowledge_cutoff_K="2026-09-21T12:00:00Z",
    )
    receipt = deepcopy(context["bitemporal_replay_receipt"])
    receipt["durable_anchor_bound"] = False
    assert verify_bitemporal_replay_receipt(
        receipt, tenant_id=TENANT, plot_id=PLOT,
        geometry_sha256=GEOMETRY, worldline_namespace="default",
        worldline_service=worldline,
    )[0] is None
