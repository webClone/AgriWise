"""Adversarial and Regression Qualification Suite for B2B-06 KMS v3 Contracts.

Tests:
1. Canonical RFC 8785 determinism and non-finite rejection
2. Asymmetric key isolation (private key encapsulated in signer, verifier has only public key)
3. Cryptographic signature verification for Ed25519 and ES256 (P-256)
4. Detection of tampered signature, tampered claims, and altered packet digest
5. Scope isolation: foreign tenant, mismatched plot ID, stale geometry version/hash
6. Variable restrictions: unpermitted observation variable rejected
7. Purpose restrictions: observation purpose vs weather forcing purpose separation
8. Zonal authority & MESIA binding: unregistered zone or invalid zone hash rejected
9. Durable revocation ledger: monotonic progression, rollback rejection, conflict rejection
10. Durable revocation key statuses: active, retired, revoked, absent
11. Durable revocation snapshot freshness: future, expired, stale
12. Revision anchor fencing: grant revision anchor ahead of ledger rejected
13. Plot, zone, and explicit grant revocation gates
14. State grant separation: self-asserted eligible_for_state_grant=True rejected
15. Spatial support requirement: partial/boundary pixel support rejected from state grant
16. Unified admission verifier: v3 KMS and legacy routing, mandatory v3 enforcement
17. End-to-end Layer0StateEngine assimilation with v3 KMS verifier
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import json
import os
import pytest

from services.agribrain.layer0.durable_revocation_authority import (
    DurableRevocationAuthority,
    DurableRevocationSnapshot,
    RevocationConflictError,
    RevocationRollbackError,
    RevocationStatus,
)
from services.agribrain.layer0.observation_packet import (
    DataStatus,
    ObservationPacket,
    ObservationSource,
    ObservationType,
    QAFlag,
    QAMetadata,
    UncertaintyModel,
)
from services.agribrain.layer0.positive_observation_admission import (
    observation_packet_digest,
)
from services.agribrain.layer0.spatial_tenant_contract import (
    FractionalPixelSupport,
    VerifiedPlotScope,
    package_spatial_provenance,
)
from services.agribrain.layer0.v3_kms_signed_issuer import (
    GRANT_PURPOSE,
    WEATHER_GRANT_PURPOSE,
    KmsAlgorithm,
    KmsPublicKeyRegistry,
    LocalKmsAsymmetricSigner,
    V3KmsGrantVerifier,
    V3PositiveStateInputGrant,
    V3SignedReceipt,
    V3_GRANT_DOMAIN,
    V3_ZONE_GRANT_DOMAIN,
    canonical_grant_bytes,
)
from services.agribrain.layer0.v3_state_admission import (
    StateGrantSeparationViolation,
    UnifiedAdmissionVerifier,
    certify_state_grant_eligibility,
)


def _make_sample_packet(
    plot_id: str = "plot-b2b06-test",
    geometry_hash: str = "geom_hash_001",
    geometry_version: int = 1,
    tenant_id: str = "tenant-alpha",
    source: ObservationSource = ObservationSource.SENTINEL2,
    obs_type: ObservationType = ObservationType.TABULAR,
    ndvi: float = 0.72,
    evi: float = 0.45,
    timestamp: datetime | None = None,
) -> ObservationPacket:
    ts = timestamp or datetime(2026, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
    packet = ObservationPacket(
        source=source,
        obs_type=obs_type,
        data_status=DataStatus.OBSERVED,
        timestamp=ts,
        plot_id=plot_id,
        geometry_hash=geometry_hash,
        geometry_version=geometry_version,
        tenant_id=tenant_id,
        payload={
            "ndvi_mean": ndvi,
            "evi_mean": evi,
            "real_provider_product": True,
            "production_usable": True,
            "state_update_allowed": True,
        },
        qa=QAMetadata(flags=[QAFlag.CLEAN], scene_score=1.0),
        uncertainty=UncertaintyModel(sigmas={"ndvi": 0.02, "evi": 0.03}),
    )
    return packet


def _bind_test_scope(
    packet: ObservationPacket,
    plot_id: str = "plot-b2b06-test",
    geometry_hash: str = "geom_hash_001",
    geometry_version: int = 1,
    tenant_id: str = "tenant-alpha",
    classification: str = "FULL_CONTAINED",
) -> tuple[VerifiedPlotScope, FractionalPixelSupport]:
    scope = VerifiedPlotScope(
        tenant_id=tenant_id,
        plot_id=plot_id,
        geometry_version=geometry_version,
        geometry_hash=geometry_hash,
        geometry_json='{"type":"Polygon","coordinates":[[[0,0],[0,1],[1,1],[1,0],[0,0]]]}',
        scope_hash=f"scope_{tenant_id}_{plot_id}_{geometry_version}",
    )
    support = FractionalPixelSupport(
        scope_hash=scope.scope_hash,
        footprint_hash="footprint_test_001",
        containment_fraction=1.0 if classification == "FULL_CONTAINED" else 0.45,
        interior_area_m2=10000.0,
        footprint_area_m2=10000.0,
        external_area_m2=0.0 if classification == "FULL_CONTAINED" else 5500.0,
        classification=classification,
        geometry_support_verified=classification == "FULL_CONTAINED",
    )
    packet.bind_spatial_context(scope, support)
    return scope, support


def _make_v3_grant_claims(
    packet: ObservationPacket,
    key_id: str,
    algorithm: str = "Ed25519",
    issuer_id: str = "copernicus-sentinel2",
    purpose: str = GRANT_PURPOSE,
    permitted_variables: tuple[str, ...] = ("ndvi", "evi"),
    spatial_scope: str = "plot",
    revocation_anchor: int = 0,
    valid_hours: int = 24,
    zone_id: str | None = None,
    zone_hash: str | None = None,
    mesia_root: str | None = None,
) -> dict[str, Any]:
    now = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
    digest = observation_packet_digest(packet)
    domain = V3_ZONE_GRANT_DOMAIN if spatial_scope == "zone" else V3_GRANT_DOMAIN
    claims = {
        "domain": domain,
        "version": "v3",
        "algorithm": algorithm,
        "key_id": key_id,
        "issuer_id": issuer_id,
        "purpose": purpose,
        "source": getattr(packet.source, "value", str(packet.source)),
        "permitted_variables": list(permitted_variables),
        "packet_digest": digest,
        "qualification_decision_id": "qual_dec_s2_20260615_001",
        "native_evidence_id": "cas_acq_s2_l2a_001",
        "policy_version": "v1",
        "qa_version": "v1",
        "scientific_support_root": "a" * 64,
        "tenant_id": packet.tenant_id,
        "plot_id": packet.plot_id,
        "geometry_hash": packet.geometry_hash,
        "geometry_version": packet.geometry_version,
        "spatial_scope": spatial_scope,
        "acquisition_start": (now - timedelta(hours=1)).isoformat(),
        "acquisition_end": now.isoformat(),
        "provenance_type": "observation",
        "temporal_role": "OBSERVED",
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=valid_hours)).isoformat(),
        "revocation_revision_anchor": revocation_anchor,
        "issuer_decision_ledger_id": "ledger_dec_20260615_001",
        "replay_idempotency_key": f"idem_{packet.packet_id}",
    }
    if spatial_scope == "zone":
        claims["zone_id"] = zone_id or "zone_1"
        claims["zone_geometry_hash"] = zone_hash or "zone_hash_001"
        claims["mesia_support_root"] = mesia_root or ("b" * 64)
    return claims


# ============================================================================
# 1. Canonical RFC 8785 Serialization Determinism
# ============================================================================

def test_canonical_json_rfc8785_determinism():
    dict1 = {"b": 2, "a": 1, "c": [3, 2, 1], "d": {"y": "val2", "x": "val1"}}
    dict2 = {"a": 1, "d": {"x": "val1", "y": "val2"}, "c": [3, 2, 1], "b": 2}
    bytes1 = canonical_grant_bytes(dict1)
    bytes2 = canonical_grant_bytes(dict2)
    assert bytes1 == bytes2
    assert b" " not in bytes1
    assert b"\n" not in bytes1

    # Rejection of non-finite floats
    with pytest.raises(ValueError, match="non-finite"):
        canonical_grant_bytes({"val": float("nan")})
    with pytest.raises(ValueError, match="non-finite"):
        canonical_grant_bytes({"val": float("inf")})


# ============================================================================
# 2. Key Isolation & Asymmetric Cryptography (Ed25519 & ES256)
# ============================================================================

def test_asymmetric_key_isolation_and_ed25519_verification():
    signer = LocalKmsAsymmetricSigner(KmsAlgorithm.ED25519)
    key_id = "kms-key-ed25519-01"
    signer.provision_key(key_id)

    # Verifier registry holds ONLY public key PEM
    pub_pem = signer.get_public_key_pem(key_id)
    assert "BEGIN PUBLIC KEY" in pub_pem
    assert "PRIVATE" not in pub_pem

    registry = KmsPublicKeyRegistry()
    registry.register_public_key(
        key_id=key_id,
        issuer_id="copernicus-sentinel2",
        source="sentinel2",
        algorithm="Ed25519",
        public_key_pem_or_bytes=pub_pem,
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )

    verifier = V3KmsGrantVerifier(registry)

    # Sign a valid packet grant
    packet = _make_sample_packet()
    _bind_test_scope(packet)
    claims = _make_v3_grant_claims(packet, key_id, algorithm="Ed25519")
    receipt = signer.sign_grant(claims, key_id)

    # Verify receipt passes
    valid, reason = verifier.verify(
        receipt,
        packet,
        plot_id=packet.plot_id,
        geometry_hash=packet.geometry_hash,
        geometry_version=packet.geometry_version,
        run_timestamp=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
        purpose=GRANT_PURPOSE,
        variables=["ndvi", "evi"],
        tenant_id=packet.tenant_id,
    )
    assert valid is True
    assert reason == "verified_v3_kms_grant"

    # Signature tampering fails
    bad_receipt = V3SignedReceipt(
        grant=receipt.grant,
        signature="A" * len(receipt.signature),
        key_id=receipt.key_id,
        algorithm=receipt.algorithm,
    )
    valid, reason = verifier.verify(
        bad_receipt,
        packet,
        plot_id=packet.plot_id,
        geometry_hash=packet.geometry_hash,
        geometry_version=packet.geometry_version,
        run_timestamp=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert valid is False
    assert reason == "bad_kms_signature"


def test_asymmetric_es256_verification():
    signer = LocalKmsAsymmetricSigner(KmsAlgorithm.ES256)
    key_id = "kms-key-es256-01"
    signer.provision_key(key_id)

    pub_pem = signer.get_public_key_pem(key_id)
    registry = KmsPublicKeyRegistry()
    registry.register_public_key(
        key_id=key_id,
        issuer_id="copernicus-sentinel2",
        source="sentinel2",
        algorithm="ES256",
        public_key_pem_or_bytes=pub_pem,
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    verifier = V3KmsGrantVerifier(registry)

    packet = _make_sample_packet()
    _bind_test_scope(packet)
    claims = _make_v3_grant_claims(packet, key_id, algorithm="ES256")
    receipt = signer.sign_grant(claims, key_id)

    valid, reason = verifier.verify(
        receipt,
        packet,
        plot_id=packet.plot_id,
        geometry_hash=packet.geometry_hash,
        geometry_version=packet.geometry_version,
        run_timestamp=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
        purpose=GRANT_PURPOSE,
    )
    assert valid is True
    assert reason == "verified_v3_kms_grant"


# ============================================================================
# 3. Scope, Content, and Claims Tamper Rejections
# ============================================================================

def test_v3_tampered_packet_digest_rejection():
    signer = LocalKmsAsymmetricSigner(KmsAlgorithm.ED25519)
    key_id = "kms-key-01"
    signer.provision_key(key_id)
    registry = KmsPublicKeyRegistry()
    registry.register_public_key(
        key_id=key_id,
        issuer_id="copernicus-sentinel2",
        source="sentinel2",
        algorithm="Ed25519",
        public_key_pem_or_bytes=signer.get_public_key_pem(key_id),
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    verifier = V3KmsGrantVerifier(registry)

    packet = _make_sample_packet(ndvi=0.72)
    _bind_test_scope(packet)
    claims = _make_v3_grant_claims(packet, key_id)
    receipt = signer.sign_grant(claims, key_id)

    # Tamper with packet content after signing
    packet.payload["ndvi_mean"] = 0.99
    valid, reason = verifier.verify(
        receipt,
        packet,
        plot_id=packet.plot_id,
        geometry_hash=packet.geometry_hash,
        geometry_version=packet.geometry_version,
        run_timestamp=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert valid is False
    assert reason == "packet_content_digest_mismatch"


def test_v3_foreign_tenant_and_plot_scope_rejection():
    signer = LocalKmsAsymmetricSigner(KmsAlgorithm.ED25519)
    key_id = "kms-key-01"
    signer.provision_key(key_id)
    registry = KmsPublicKeyRegistry()
    registry.register_public_key(
        key_id=key_id,
        issuer_id="copernicus-sentinel2",
        source="sentinel2",
        algorithm="Ed25519",
        public_key_pem_or_bytes=signer.get_public_key_pem(key_id),
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    verifier = V3KmsGrantVerifier(registry)

    packet = _make_sample_packet(tenant_id="tenant-alpha", plot_id="plot-1")
    _bind_test_scope(packet, tenant_id="tenant-alpha", plot_id="plot-1")
    claims = _make_v3_grant_claims(packet, key_id)
    receipt = signer.sign_grant(claims, key_id)

    # Foreign tenant caller
    valid, reason = verifier.verify(
        receipt, packet,
        plot_id="plot-1", geometry_hash=packet.geometry_hash,
        geometry_version=packet.geometry_version,
        run_timestamp=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
        tenant_id="tenant-beta",
    )
    assert valid is False
    assert reason == "wrong_grant_tenant_scope"

    # Mismatched plot ID
    valid, reason = verifier.verify(
        receipt, packet,
        plot_id="plot-foreign", geometry_hash=packet.geometry_hash,
        geometry_version=packet.geometry_version,
        run_timestamp=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert valid is False
    assert reason == "wrong_grant_plot_geometry_scope"


# ============================================================================
# 4. Variable Restrictions & Purpose Isolation
# ============================================================================

def test_v3_permitted_variables_restriction():
    signer = LocalKmsAsymmetricSigner(KmsAlgorithm.ED25519)
    key_id = "kms-key-01"
    signer.provision_key(key_id)
    registry = KmsPublicKeyRegistry()
    registry.register_public_key(
        key_id=key_id,
        issuer_id="copernicus-sentinel2",
        source="sentinel2",
        algorithm="Ed25519",
        public_key_pem_or_bytes=signer.get_public_key_pem(key_id),
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    verifier = V3KmsGrantVerifier(registry)

    packet = _make_sample_packet()
    _bind_test_scope(packet)
    # Grant permits ONLY ndvi
    claims = _make_v3_grant_claims(packet, key_id, permitted_variables=("ndvi",))
    receipt = signer.sign_grant(claims, key_id)

    # Asking for ndvi succeeds
    valid, _ = verifier.verify(
        receipt, packet,
        plot_id=packet.plot_id, geometry_hash=packet.geometry_hash,
        geometry_version=packet.geometry_version,
        run_timestamp=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
        variables=["ndvi"],
    )
    assert valid is True

    # Asking for evi (unpermitted) fails
    valid, reason = verifier.verify(
        receipt, packet,
        plot_id=packet.plot_id, geometry_hash=packet.geometry_hash,
        geometry_version=packet.geometry_version,
        run_timestamp=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
        variables=["ndvi", "evi"],
    )
    assert valid is False
    assert "unpermitted_variables" in reason


def test_v3_purpose_isolation():
    signer = LocalKmsAsymmetricSigner(KmsAlgorithm.ED25519)
    key_id = "kms-key-01"
    signer.provision_key(key_id)
    registry = KmsPublicKeyRegistry()
    registry.register_public_key(
        key_id=key_id,
        issuer_id="copernicus-sentinel2",
        source="sentinel2",
        algorithm="Ed25519",
        public_key_pem_or_bytes=signer.get_public_key_pem(key_id),
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    verifier = V3KmsGrantVerifier(registry)

    packet = _make_sample_packet()
    _bind_test_scope(packet)
    claims = _make_v3_grant_claims(packet, key_id, purpose=GRANT_PURPOSE)
    receipt = signer.sign_grant(claims, key_id)

    # Cross-purpose verification for weather_state_forcing fails
    valid, reason = verifier.verify(
        receipt, packet,
        plot_id=packet.plot_id, geometry_hash=packet.geometry_hash,
        geometry_version=packet.geometry_version,
        run_timestamp=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
        purpose=WEATHER_GRANT_PURPOSE,
    )
    assert valid is False
    assert reason == "kms_key_purpose_unauthorized"


# ============================================================================
# 5. Durable Revocation Authority & Monotonicity
# ============================================================================

def test_durable_revocation_ledger_progression():
    t_base = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
    snap0 = DurableRevocationSnapshot(
        revision=0,
        issued_at=t_base,
        expires_at=t_base + timedelta(hours=24),
        key_statuses={"kms-key-01": "active", "kms-key-old": "retired"},
        revoked_plots=("plot-banned",),
    )
    auth = DurableRevocationAuthority(snap0)
    assert auth.current_revision == 0

    # Revision rollback detected
    snap_rollback = DurableRevocationSnapshot(
        revision=-1 if False else 0,  # can't pass -1, but passing lower revision later
        issued_at=t_base,
        expires_at=t_base + timedelta(hours=24),
        key_statuses={"kms-key-01": "active"},
    )
    # Monotonic advance to rev 1
    snap1 = DurableRevocationSnapshot(
        revision=1,
        issued_at=t_base + timedelta(hours=1),
        expires_at=t_base + timedelta(hours=25),
        key_statuses={"kms-key-01": "active", "kms-key-old": "revoked"},
        previous_digest=snap0.snapshot_digest,
    )
    auth.load_snapshot(snap1)
    assert auth.current_revision == 1

    # Attempt rollback to revision 0 fails
    with pytest.raises(RevocationRollbackError, match="rollback detected"):
        auth.load_snapshot(snap0)

    # Conflict at same revision fails
    snap1_conflict = DurableRevocationSnapshot(
        revision=1,
        issued_at=t_base + timedelta(hours=1),
        expires_at=t_base + timedelta(hours=25),
        key_statuses={"kms-key-01": "revoked"},  # different content
        previous_digest=snap0.snapshot_digest,
    )
    with pytest.raises(RevocationConflictError, match="conflict at revision 1"):
        auth.load_snapshot(snap1_conflict)


def test_durable_revocation_key_status_and_scope_checks():
    t_now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    snapshot = DurableRevocationSnapshot(
        revision=2,
        issued_at=t_now - timedelta(minutes=5),
        expires_at=t_now + timedelta(hours=2),
        key_statuses={
            "key-active": "active",
            "key-retired": "retired",
            "key-revoked": "revoked",
        },
        revoked_plots=("plot-revoked-01",),
        revoked_zones={"plot-active-01": ("zone-revoked-01",)},
        revoked_grants=("idem_revoked_grant",),
    )
    auth = DurableRevocationAuthority(snapshot)

    # Active key passes
    ok, _ = auth.check_authority("key-active", t_now, plot_id="plot-active-01")
    assert ok is True

    # Retired key fails
    ok, reason = auth.check_authority("key-retired", t_now)
    assert ok is False and reason == "issuer_key_retired"

    # Revoked key fails
    ok, reason = auth.check_authority("key-revoked", t_now)
    assert ok is False and reason == "issuer_key_revoked"

    # Absent key fails
    ok, reason = auth.check_authority("key-unknown", t_now)
    assert ok is False and reason == "issuer_key_absent_from_revocation_ledger"

    # Revoked plot fails
    ok, reason = auth.check_authority("key-active", t_now, plot_id="plot-revoked-01")
    assert ok is False and reason == "plot_scope_revoked"

    # Revoked zone fails
    ok, reason = auth.check_authority("key-active", t_now, plot_id="plot-active-01", zone_id="zone-revoked-01")
    assert ok is False and reason == "zone_scope_revoked"

    # Revoked grant fails
    ok, reason = auth.check_authority("key-active", t_now, grant_id="idem_revoked_grant")
    assert ok is False and reason == "grant_explicitly_revoked"

    # Anchor newer than ledger fails
    ok, reason = auth.check_authority("key-active", t_now, revision_anchor=5)
    assert ok is False and reason == "revocation_anchor_behind_ledger"


# ============================================================================
# 6. State Grant Separation Gate & Anti-Self-Promotion
# ============================================================================

def test_state_grant_separation_gate():
    signer = LocalKmsAsymmetricSigner(KmsAlgorithm.ED25519)
    key_id = "kms-key-01"
    signer.provision_key(key_id)
    registry = KmsPublicKeyRegistry()
    registry.register_public_key(
        key_id=key_id,
        issuer_id="copernicus-sentinel2",
        source="sentinel2",
        algorithm="Ed25519",
        public_key_pem_or_bytes=signer.get_public_key_pem(key_id),
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    verifier = V3KmsGrantVerifier(registry)

    packet = _make_sample_packet()
    scope, support = _bind_test_scope(packet)
    claims = _make_v3_grant_claims(packet, key_id)
    receipt = signer.sign_grant(claims, key_id)

    # 1. Valid certification succeeds and mints V3StateGrantToken
    ok, reason, token = certify_state_grant_eligibility(
        packet, receipt, scope, support, verifier,
        now=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert ok is True
    assert token is not None
    assert token.eligible_for_state_grant is True
    assert token.source_qualified is True
    assert token.authority == "v3_asymmetric_kms_authorized"
    assert getattr(packet, "_state_grant_authorized", False) is True

    # 2. Rejection of unverified packet attempting self-promotion
    bad_packet = _make_sample_packet()
    bad_packet.spatial_provenance = {
        "eligible_for_state_grant": True,  # Self-promotion attack!
        "source_qualified": True,
    }
    with pytest.raises(StateGrantSeparationViolation, match="unauthorized_state_grant_self_promotion"):
        certify_state_grant_eligibility(
            bad_packet, receipt, scope, support, verifier,
        )

    # 3. Fractional / boundary pixel support rejected from state grant
    packet_frac = _make_sample_packet()
    scope_frac, support_frac = _bind_test_scope(packet_frac, classification="FRACTIONAL_BOUNDARY")
    ok, reason, token = certify_state_grant_eligibility(
        packet_frac, receipt, scope_frac, support_frac, verifier,
    )
    assert ok is False
    assert reason == "fractional_or_partial_spatial_support_not_eligible"


# ============================================================================
# 7. Unified Admission Verifier & Mandatory v3 Enforcement
# ============================================================================

def test_unified_admission_verifier_and_mandatory_v3():
    signer = LocalKmsAsymmetricSigner(KmsAlgorithm.ED25519)
    key_id = "kms-key-01"
    signer.provision_key(key_id)
    registry = KmsPublicKeyRegistry()
    registry.register_public_key(
        key_id=key_id,
        issuer_id="copernicus-sentinel2",
        source="sentinel2",
        algorithm="Ed25519",
        public_key_pem_or_bytes=signer.get_public_key_pem(key_id),
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    v3_ver = V3KmsGrantVerifier(registry)

    # Unified verifier without mandatory v3
    unified = UnifiedAdmissionVerifier(v3_verifier=v3_ver, enforce_v3_only=False)

    packet = _make_sample_packet()
    _bind_test_scope(packet)
    claims = _make_v3_grant_claims(packet, key_id)
    receipt = signer.sign_grant(claims, key_id)

    valid, reason = unified.verify(
        receipt.to_dict(),
        packet,
        plot_id=packet.plot_id,
        geometry_hash=packet.geometry_hash,
        geometry_version=packet.geometry_version,
        run_timestamp=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert valid is True
    assert reason == "verified_v3_kms_grant"

    # Enforce v3-only: legacy grant must be rejected
    unified_v3_only = UnifiedAdmissionVerifier(v3_verifier=v3_ver, enforce_v3_only=True)
    legacy_receipt = {
        "grant": {"domain": "akaloris/layer0/positive-state-observation/v1"},
        "mac": "0" * 64,
    }
    valid, reason = unified_v3_only.verify(
        legacy_receipt,
        packet,
        plot_id=packet.plot_id,
        geometry_hash=packet.geometry_hash,
        geometry_version=packet.geometry_version,
        run_timestamp=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert valid is False
    assert reason == "legacy_v1_v2_grant_prohibited_under_v3_kms_policy"


# ============================================================================
# 8. StateEngine Daily Assimilation with v3 KMS Verifier
# ============================================================================

def test_state_engine_daily_assimilation_with_v3_kms():
    from services.agribrain.layer0.state_engine import Layer0StateEngine
    from services.agribrain.layer0.spatial_tenant_contract import (
        canonical_geometry_hash,
        authorize_plot_scope,
        ScopedPlotRequest,
        AuthenticatedPrincipal,
    )
    from services.agribrain.layer0.plot_ownership_store import CollectionPlotOwnershipStore

    signer = LocalKmsAsymmetricSigner(KmsAlgorithm.ED25519)
    key_id = "kms-key-01"
    signer.provision_key(key_id)
    registry = KmsPublicKeyRegistry()
    registry.register_public_key(
        key_id=key_id,
        issuer_id="copernicus-sentinel2",
        source="sentinel2",
        algorithm="Ed25519",
        public_key_pem_or_bytes=signer.get_public_key_pem(key_id),
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    verifier = V3KmsGrantVerifier(registry)

    poly = {"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]}
    geom_hash = canonical_geometry_hash(poly)

    class MockCollection:
        def find_one(self, query):
            if query.get("plot_id") == "plot-se-01":
                return {
                    "plot_id": "plot-se-01",
                    "tenant_id": "tenant-se",
                    "active": True,
                    "revoked": False,
                    "deleted_at": None,
                    "geometry_version": 1,
                    "geometry_hash": geom_hash,
                    "polygon_geojson": poly,
                }
            return None

    store = CollectionPlotOwnershipStore(MockCollection())
    principal = AuthenticatedPrincipal(tenant_id="tenant-se", subject_id="sub-01", authenticated=True)
    scope = authorize_plot_scope(
        principal,
        ScopedPlotRequest("tenant-se", "plot-se-01", geom_hash, 1),
        store.get_active_plot,
    )

    engine = Layer0StateEngine(
        positive_admission_verifier=verifier,
        plot_ownership_store=store,
        principal_provider=lambda: principal,
    )

    packet = _make_sample_packet(
        plot_id="plot-se-01",
        geometry_hash=geom_hash,
        geometry_version=1,
        tenant_id="tenant-se",
        timestamp=datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
    )
    support = FractionalPixelSupport(
        scope_hash=scope.scope_hash,
        footprint_hash="footprint_se_01",
        containment_fraction=1.0,
        interior_area_m2=10000.0,
        footprint_area_m2=10000.0,
        external_area_m2=0.0,
        classification="FULL_CONTAINED",
        geometry_support_verified=True,
    )
    packet.bind_spatial_context(scope, support)

    claims = _make_v3_grant_claims(packet, key_id)
    receipt = signer.sign_grant(claims, key_id)

    digest = observation_packet_digest(packet)
    receipts_map = {digest: receipt.to_dict()}

    state_pkg = engine.run_from_packets(
        plot_id="plot-se-01",
        geometry_hash=geom_hash,
        geometry_version=1,
        tenant_id="tenant-se",
        scope_hash=scope.scope_hash,
        start_date="2026-06-15",
        end_date="2026-06-15",
        packets=[packet],
        positive_admission_receipts=receipts_map,
        run_timestamp=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert state_pkg is not None
    assert state_pkg.plot_id == "plot-se-01"
    assert digest in state_pkg.health_report["positive_admitted_observation_digests"]
    assert state_pkg.health_report["signed_state_input_count"] == 1


# ============================================================================
# 9. Zonal Scope Authority & MESIA Binding
# ============================================================================

def test_v3_zonal_scope_authority_and_mesia_binding():
    signer = LocalKmsAsymmetricSigner(KmsAlgorithm.ED25519)
    key_id = "kms-key-01"
    signer.provision_key(key_id)
    registry = KmsPublicKeyRegistry()
    registry.register_public_key(
        key_id=key_id,
        issuer_id="copernicus-sentinel2",
        source="sentinel2",
        algorithm="Ed25519",
        public_key_pem_or_bytes=signer.get_public_key_pem(key_id),
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    zone_registry = {
        "plot-b2b06-test": {
            "geometry_hash": "geom_hash_001",
            "geometry_version": 1,
            "zones": {"zone_1": "zone_hash_001"},
        }
    }
    verifier = V3KmsGrantVerifier(registry, trusted_zone_registry=zone_registry)

    packet = _make_sample_packet()
    packet.spatial_scope = "zone"
    packet.payload["zone_id"] = "zone_1"
    packet.payload["zone_geometry_hash"] = "zone_hash_001"
    _bind_test_scope(packet)

    claims = _make_v3_grant_claims(
        packet, key_id,
        spatial_scope="zone",
        zone_id="zone_1",
        zone_hash="zone_hash_001",
        mesia_root="b" * 64,
    )
    receipt = signer.sign_grant(claims, key_id)

    # Valid zonal grant passes
    valid, reason = verifier.verify(
        receipt, packet,
        plot_id=packet.plot_id,
        geometry_hash=packet.geometry_hash,
        geometry_version=packet.geometry_version,
        run_timestamp=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
        purpose=GRANT_PURPOSE,
    )
    assert valid is True
    assert reason == "verified_v3_kms_grant"

    # Foreign unregistered zone fails
    claims_foreign = _make_v3_grant_claims(
        packet, key_id,
        spatial_scope="zone",
        zone_id="zone_foreign",
        zone_hash="zone_hash_foreign",
        mesia_root="b" * 64,
    )
    packet.payload["zone_id"] = "zone_foreign"
    packet.payload["zone_geometry_hash"] = "zone_hash_foreign"
    receipt_foreign = signer.sign_grant(claims_foreign, key_id)
    valid, reason = verifier.verify(
        receipt_foreign, packet,
        plot_id=packet.plot_id,
        geometry_hash=packet.geometry_hash,
        geometry_version=packet.geometry_version,
        run_timestamp=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
        purpose=GRANT_PURPOSE,
    )
    assert valid is False
    assert reason == "unregistered_or_foreign_zone_geometry"


# ============================================================================
# 10. Temporal Window Bounds & Revocation Freshness
# ============================================================================

def test_v3_grant_temporal_window_bounds():
    signer = LocalKmsAsymmetricSigner(KmsAlgorithm.ED25519)
    key_id = "kms-key-01"
    signer.provision_key(key_id)
    registry = KmsPublicKeyRegistry()
    registry.register_public_key(
        key_id=key_id,
        issuer_id="copernicus-sentinel2",
        source="sentinel2",
        algorithm="Ed25519",
        public_key_pem_or_bytes=signer.get_public_key_pem(key_id),
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    verifier = V3KmsGrantVerifier(registry)

    packet = _make_sample_packet()
    _bind_test_scope(packet)
    # Grant issued at 10:00, valid for 24 hours (until next day 10:00)
    claims = _make_v3_grant_claims(packet, key_id, valid_hours=24)
    receipt = signer.sign_grant(claims, key_id)

    # 1. Run time before issued_at fails
    valid, reason = verifier.verify(
        receipt, packet,
        plot_id=packet.plot_id,
        geometry_hash=packet.geometry_hash,
        geometry_version=packet.geometry_version,
        run_timestamp=datetime(2026, 6, 15, 9, 0, 0, tzinfo=timezone.utc),
    )
    assert valid is False
    assert reason == "grant_temporal_window_expired_or_future"

    # 2. Run time after expires_at fails
    valid, reason = verifier.verify(
        receipt, packet,
        plot_id=packet.plot_id,
        geometry_hash=packet.geometry_hash,
        geometry_version=packet.geometry_version,
        run_timestamp=datetime(2026, 6, 16, 11, 0, 0, tzinfo=timezone.utc),
    )
    assert valid is False
    assert reason == "grant_temporal_window_expired_or_future"


def test_durable_revocation_snapshot_freshness():
    t_now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)

    # Future snapshot
    snap_future = DurableRevocationSnapshot(
        revision=1,
        issued_at=t_now + timedelta(minutes=10),
        expires_at=t_now + timedelta(hours=2),
        key_statuses={"k1": "active"},
    )
    auth_future = DurableRevocationAuthority(snap_future)
    ok, reason = auth_future.check_authority("k1", t_now)
    assert ok is False
    assert reason == "future_dated_revocation_snapshot"

    # Expired snapshot
    snap_expired = DurableRevocationSnapshot(
        revision=1,
        issued_at=t_now - timedelta(hours=3),
        expires_at=t_now - timedelta(hours=1),
        key_statuses={"k1": "active"},
    )
    auth_expired = DurableRevocationAuthority(snap_expired)
    ok, reason = auth_expired.check_authority("k1", t_now)
    assert ok is False
    assert reason == "expired_revocation_snapshot"

    # Stale snapshot (> 300 seconds default max age)
    snap_stale = DurableRevocationSnapshot(
        revision=1,
        issued_at=t_now - timedelta(minutes=10),
        expires_at=t_now + timedelta(hours=1),
        key_statuses={"k1": "active"},
    )
    auth_stale = DurableRevocationAuthority(snap_stale, max_snapshot_age_seconds=300)
    ok, reason = auth_stale.check_authority("k1", t_now)
    assert ok is False
    assert reason == "stale_revocation_snapshot"


# ============================================================================
# 11. Mandatory v3 KMS Production Configuration
# ============================================================================

def test_mandatory_v3_kms_production_admission_config(tmp_path, monkeypatch):
    from services.agribrain.layer0.production_admission import (
        load_server_issuer_verifier,
        Layer0AdmissionRequiredError,
    )

    signer = LocalKmsAsymmetricSigner(KmsAlgorithm.ED25519)
    key_id = "kms-prod-01"
    signer.provision_key(key_id)
    pub_pem = signer.get_public_key_pem(key_id)

    kms_config = {
        key_id: {
            "issuer_id": "copernicus-sentinel2",
            "source": "sentinel2",
            "algorithm": "Ed25519",
            "public_key_pem": pub_pem,
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_until": "2027-01-01T00:00:00Z",
            "permitted_purposes": ["kalman_state_observation"],
        }
    }

    t_now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    rev_file = tmp_path / "prod_revocation.json"
    snap = DurableRevocationSnapshot(
        revision=1,
        issued_at=t_now - timedelta(seconds=10),
        expires_at=t_now + timedelta(hours=1),
        key_statuses={key_id: "active"},
    )
    rev_file.write_text(json.dumps(snap.to_dict()), encoding="utf-8")

    # 1. Configured KMS keys and durable revocation successfully return V3KmsGrantVerifier
    monkeypatch.setenv("AKALORIS_LAYER0_KMS_PUBLIC_KEYS_JSON", json.dumps(kms_config))
    monkeypatch.setenv("AKALORIS_LAYER0_DURABLE_REVOCATION_PATH", str(rev_file))
    monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_V3_KMS", "true")
    monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_SIGNED_INPUTS", "true")

    verifier = load_server_issuer_verifier()
    assert isinstance(verifier, V3KmsGrantVerifier)

    # 2. Mandatory v3 without KMS keys fails closed
    monkeypatch.setenv("AKALORIS_LAYER0_KMS_PUBLIC_KEYS_JSON", "")
    with pytest.raises(Layer0AdmissionRequiredError, match="Mandatory v3 KMS policy requires"):
        load_server_issuer_verifier()


# ============================================================================
# 12. Corrective Batch Verification Tests (RFC 8785 JCS, Deterministic ES256,
#     Direct Spatial Containment Gate, Dynamic Durable Revocation & Key Isolation)
# ============================================================================

def test_rfc8785_official_test_vectors():
    import rfc8785
    # Numbers formatting
    assert rfc8785.dumps({"x": 1e-7}) == b'{"x":1e-7}'
    assert rfc8785.dumps({"x": 1e-6}) == b'{"x":0.000001}'
    assert rfc8785.dumps({"x": 1e21}) == b'{"x":1e+21}'
    assert rfc8785.dumps({"x": -0.0}) == b'{"x":0}'
    assert rfc8785.dumps({"x": 0.0}) == b'{"x":0}'
    assert rfc8785.dumps({"x": 100.0}) == b'{"x":100}'

    # Key sorting UTF-16 code units: emoji surrogate pairs vs BMP characters
    # \U0001F600 has UTF-16 code units (0xD83D, 0xDE00).
    # \uFFFF has UTF-16 code unit 0xFFFF.
    # In UTF-16 code units, 0xD83D < 0xFFFF, so \U0001F600 must sort before \uFFFF
    data = {"\uffff": 1, "\U0001F600": 2}
    encoded = rfc8785.dumps(data)
    assert encoded.startswith(b'{"\xf0\x9f\x98\x80":2,"\xef\xbf\xbf":1}')

    # Canonical grant bytes determinism
    claims = {
        "domain": V3_GRANT_DOMAIN,
        "version": "v3",
        "algorithm": "Ed25519",
        "key_id": "k1",
        "nested": {"z": 1e-7, "a": -0.0},
    }
    b1 = canonical_grant_bytes(claims)
    b2 = canonical_grant_bytes(claims)
    assert b1 == b2
    assert b'"nested":{"a":0,"z":1e-7}' in b1


def test_es256_rfc6979_deterministic_signatures():
    signer = LocalKmsAsymmetricSigner(KmsAlgorithm.ES256)
    key_id = "kms-es256-det"
    signer.provision_key(key_id)

    packet = _make_sample_packet()
    _bind_test_scope(packet)
    claims = _make_v3_grant_claims(packet, key_id, algorithm="ES256")

    receipt1 = signer.sign_grant(claims, key_id)
    receipt2 = signer.sign_grant(claims, key_id)

    # Deterministic ECDSA (RFC 6979) guarantees byte-identical signatures for identical claims
    assert receipt1.signature == receipt2.signature
    assert isinstance(receipt1.signature, str)
    assert len(receipt1.signature) > 60


def test_direct_verify_grant_spatial_containment_gate():
    signer = LocalKmsAsymmetricSigner(KmsAlgorithm.ED25519)
    key_id = "kms-spatial-01"
    signer.provision_key(key_id)
    registry = KmsPublicKeyRegistry()
    registry.register_public_key(
        key_id=key_id,
        issuer_id="copernicus-sentinel2",
        source="sentinel2",
        algorithm="Ed25519",
        public_key_pem_or_bytes=signer.get_public_key_pem(key_id),
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    verifier = V3KmsGrantVerifier(registry)

    # 1. Direct call on unbound packet fails closed with unverified_or_fractional_spatial_support
    packet_raw = _make_sample_packet()
    claims_raw = _make_v3_grant_claims(packet_raw, key_id)
    receipt_raw = signer.sign_grant(claims_raw, key_id)

    valid, reason, token = verifier.verify_grant(
        receipt_raw,
        packet_raw,
        plot_id=packet_raw.plot_id,
        geometry_hash=packet_raw.geometry_hash,
        geometry_version=packet_raw.geometry_version,
        run_timestamp=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert valid is False
    assert reason == "unverified_or_fractional_spatial_support"
    assert token is None

    # 2. Direct call on FRACTIONAL_BOUNDARY packet fails closed
    packet_frac = _make_sample_packet()
    _bind_test_scope(packet_frac, classification="FRACTIONAL_BOUNDARY")
    claims_frac = _make_v3_grant_claims(packet_frac, key_id)
    receipt_frac = signer.sign_grant(claims_frac, key_id)

    valid, reason, token = verifier.verify_grant(
        receipt_frac,
        packet_frac,
        plot_id=packet_frac.plot_id,
        geometry_hash=packet_frac.geometry_hash,
        geometry_version=packet_frac.geometry_version,
        run_timestamp=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert valid is False
    assert reason == "unverified_or_fractional_spatial_support"
    assert token is None

    # 3. Direct call on self-asserted packet fails closed with unauthorized_state_grant_self_promotion
    packet_self = _make_sample_packet()
    _bind_test_scope(packet_self, classification="FULL_CONTAINED")
    # Mutate to self-assert state grant
    packet_self.spatial_provenance["eligible_for_state_grant"] = True
    claims_self = _make_v3_grant_claims(packet_self, key_id)
    receipt_self = signer.sign_grant(claims_self, key_id)

    valid, reason, token = verifier.verify_grant(
        receipt_self,
        packet_self,
        plot_id=packet_self.plot_id,
        geometry_hash=packet_self.geometry_hash,
        geometry_version=packet_self.geometry_version,
        run_timestamp=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert valid is False
    assert reason == "unauthorized_state_grant_self_promotion"
    assert token is None

    # 4. Valid FULL_CONTAINED packet succeeds and mints valid token
    packet_ok = _make_sample_packet()
    _bind_test_scope(packet_ok, classification="FULL_CONTAINED")
    claims_ok = _make_v3_grant_claims(packet_ok, key_id)
    receipt_ok = signer.sign_grant(claims_ok, key_id)

    valid, reason, token = verifier.verify_grant(
        receipt_ok,
        packet_ok,
        plot_id=packet_ok.plot_id,
        geometry_hash=packet_ok.geometry_hash,
        geometry_version=packet_ok.geometry_version,
        run_timestamp=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert valid is True
    assert reason == "verified_v3_kms_grant"
    assert token is not None
    assert token.spatial_classification == "FULL_CONTAINED"
    assert token.eligible_for_state_grant is True


def test_mandatory_v3_durable_revocation_missing_or_stale(tmp_path, monkeypatch):
    from services.agribrain.layer0.production_admission import (
        load_server_issuer_verifier,
        require_trusted_verifier,
        Layer0AdmissionRequiredError,
    )

    signer = LocalKmsAsymmetricSigner(KmsAlgorithm.ED25519)
    key_id = "kms-dyn-01"
    signer.provision_key(key_id)
    pub_pem = signer.get_public_key_pem(key_id)

    kms_config = {
        key_id: {
            "issuer_id": "copernicus-sentinel2",
            "source": "sentinel2",
            "algorithm": "Ed25519",
            "public_key_pem": pub_pem,
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_until": "2027-01-01T00:00:00Z",
            "permitted_purposes": ["kalman_state_observation"],
        }
    }

    monkeypatch.setenv("AKALORIS_LAYER0_KMS_PUBLIC_KEYS_JSON", json.dumps(kms_config))
    monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_V3_KMS", "true")
    monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_SIGNED_INPUTS", "true")

    # 1. Missing durable revocation path fails closed
    monkeypatch.delenv("AKALORIS_LAYER0_DURABLE_REVOCATION_PATH", raising=False)
    with pytest.raises(Layer0AdmissionRequiredError, match="requires a trusted durable revocation path"):
        load_server_issuer_verifier()

    # 2. Non-existent file path fails closed
    missing_file = str(tmp_path / "non_existent_revocation.json")
    monkeypatch.setenv("AKALORIS_LAYER0_DURABLE_REVOCATION_PATH", missing_file)
    with pytest.raises(Layer0AdmissionRequiredError, match="snapshot file not found"):
        load_server_issuer_verifier()

    # 3. Create valid initial snapshot file
    t_now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    rev_file = tmp_path / "durable_revocation.json"
    snap1 = DurableRevocationSnapshot(
        revision=1,
        issued_at=t_now - timedelta(seconds=10),
        expires_at=t_now + timedelta(hours=1),
        key_statuses={key_id: "active"},
    )
    rev_file.write_text(json.dumps(snap1.to_dict()), encoding="utf-8")
    monkeypatch.setenv("AKALORIS_LAYER0_DURABLE_REVOCATION_PATH", str(rev_file))

    verifier = load_server_issuer_verifier()
    assert isinstance(verifier, V3KmsGrantVerifier)
    require_trusted_verifier(verifier)

    packet = _make_sample_packet()
    _bind_test_scope(packet)
    claims = _make_v3_grant_claims(packet, key_id, revocation_anchor=1)
    receipt = signer.sign_grant(claims, key_id)

    valid, reason = verifier.verify(
        receipt, packet,
        plot_id=packet.plot_id,
        geometry_hash=packet.geometry_hash,
        geometry_version=packet.geometry_version,
        run_timestamp=t_now,
    )
    assert valid is True

    # 4. Modify snapshot on disk to revoke the key -> dynamic reload detects revoked key
    snap2 = DurableRevocationSnapshot(
        revision=2,
        issued_at=t_now - timedelta(seconds=5),
        expires_at=t_now + timedelta(hours=1),
        key_statuses={key_id: "revoked"},
        previous_digest=snap1.snapshot_digest,
    )
    rev_file.write_text(json.dumps(snap2.to_dict()), encoding="utf-8")

    valid, reason = verifier.verify(
        receipt, packet,
        plot_id=packet.plot_id,
        geometry_hash=packet.geometry_hash,
        geometry_version=packet.geometry_version,
        run_timestamp=t_now,
    )
    assert valid is False
    assert reason == "issuer_key_revoked"

    # 5. Rollback attack on disk (lower revision) -> dynamic reload detects rollback error
    snap_rollback = DurableRevocationSnapshot(
        revision=1,
        issued_at=t_now - timedelta(seconds=5),
        expires_at=t_now + timedelta(hours=1),
        key_statuses={key_id: "active"},
    )
    rev_file.write_text(json.dumps(snap_rollback.to_dict()), encoding="utf-8")

    valid, reason = verifier.verify(
        receipt, packet,
        plot_id=packet.plot_id,
        geometry_hash=packet.geometry_hash,
        geometry_version=packet.geometry_version,
        run_timestamp=t_now,
    )
    assert valid is False
    assert reason == "revocation_ledger_violation:RevocationRollbackError"


def test_production_configuration_no_private_keys(tmp_path, monkeypatch):
    from services.agribrain.layer0.production_admission import (
        load_server_issuer_verifier,
        require_trusted_verifier,
    )

    signer = LocalKmsAsymmetricSigner(KmsAlgorithm.ED25519)
    key_id = "kms-prod-key-no-priv"
    signer.provision_key(key_id)
    pub_pem = signer.get_public_key_pem(key_id)

    kms_config = {
        key_id: {
            "issuer_id": "copernicus-sentinel2",
            "source": "sentinel2",
            "algorithm": "Ed25519",
            "public_key_pem": pub_pem,
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_until": "2027-01-01T00:00:00Z",
            "permitted_purposes": ["kalman_state_observation"],
        }
    }

    t_now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    rev_file = tmp_path / "prod_revocation.json"
    snap = DurableRevocationSnapshot(
        revision=1,
        issued_at=t_now - timedelta(seconds=10),
        expires_at=t_now + timedelta(hours=1),
        key_statuses={key_id: "active"},
    )
    rev_file.write_text(json.dumps(snap.to_dict()), encoding="utf-8")

    monkeypatch.setenv("AKALORIS_LAYER0_KMS_PUBLIC_KEYS_JSON", json.dumps(kms_config))
    monkeypatch.setenv("AKALORIS_LAYER0_DURABLE_REVOCATION_PATH", str(rev_file))
    monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_V3_KMS", "true")
    monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_SIGNED_INPUTS", "true")

    verifier = load_server_issuer_verifier()
    assert isinstance(verifier, V3KmsGrantVerifier)
    require_trusted_verifier(verifier)

    # Verify no private key attributes exist in verifier or registry
    entry = verifier.registry.get_entry(key_id)
    assert entry is not None
    assert not hasattr(entry.public_key, "private_bytes")
    assert not hasattr(entry.public_key, "sign")
    assert not hasattr(verifier, "_private_keys")
    assert not hasattr(verifier.registry, "_private_keys")

# ============================================================================
# 18. Mandatory v3 cannot be bypassed by caller-injected legacy verifier
# ============================================================================

def test_mandatory_v3_rejects_legacy_verifier_even_if_revocation_enforced(monkeypatch):
    from services.agribrain.layer0.production_admission import (
        Layer0AdmissionRequiredError, require_trusted_verifier,
    )
    from services.agribrain.layer0.state_engine import Layer0StateEngine

    class RevocationEnabledLegacyVerifier:
        revocation_enforced = True

    monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_SIGNED_INPUTS", "true")
    monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_V3_KMS", "true")
    fake_legacy = RevocationEnabledLegacyVerifier()
    with pytest.raises(Layer0AdmissionRequiredError, match="requires a trusted asymmetric v3 verifier"):
        require_trusted_verifier(fake_legacy)
    with pytest.raises(Layer0AdmissionRequiredError, match="requires a trusted asymmetric v3 verifier"):
        Layer0StateEngine(positive_admission_verifier=fake_legacy)

    # A UnifiedVerifier with only a legacy revocation provider is also denied.
    unified_legacy = UnifiedAdmissionVerifier(
        legacy_verifier=fake_legacy, enforce_v3_only=True,
    )
    with pytest.raises(Layer0AdmissionRequiredError, match="requires a trusted asymmetric v3 verifier"):
        require_trusted_verifier(unified_legacy)


def test_mandatory_v3_requires_its_own_revocation_not_legacy_revocation(monkeypatch):
    from services.agribrain.layer0.production_admission import (
        Layer0AdmissionRequiredError, require_trusted_verifier,
    )

    monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_SIGNED_INPUTS", "true")
    monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_V3_KMS", "true")
    registry = KmsPublicKeyRegistry()
    v3_without_revocation = V3KmsGrantVerifier(registry)

    with pytest.raises(Layer0AdmissionRequiredError, match="requires durable revocation authority"):
        require_trusted_verifier(v3_without_revocation)

    # The aggregate UnifiedVerifier must not use a legacy revocation flag
    # as a stand-in for the v3 verifier's missing revocation protection.
    class RevocationEnabledLegacyVerifier:
        revocation_enforced = True

    unified = UnifiedAdmissionVerifier(
        v3_verifier=v3_without_revocation,
        legacy_verifier=RevocationEnabledLegacyVerifier(),
        enforce_v3_only=True,
    )
    assert unified.revocation_enforced is True
    with pytest.raises(Layer0AdmissionRequiredError, match="requires durable revocation authority"):
        require_trusted_verifier(unified)


def test_unified_v3_only_policy_is_live_and_handles_typed_receipt(monkeypatch):
    monkeypatch.delenv("AKALORIS_LAYER0_REQUIRE_V3_KMS", raising=False)
    signer = LocalKmsAsymmetricSigner(KmsAlgorithm.ED25519)
    key_id = "kms-typed-receipt-v3"
    signer.provision_key(key_id)
    registry = KmsPublicKeyRegistry()
    registry.register_public_key(
        key_id=key_id,
        issuer_id="copernicus-sentinel2",
        source="sentinel2",
        algorithm="Ed25519",
        public_key_pem_or_bytes=signer.get_public_key_pem(key_id),
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    verifier = UnifiedAdmissionVerifier(
        v3_verifier=V3KmsGrantVerifier(registry),
        enforce_v3_only=False,
    )
    p = _make_sample_packet()
    _bind_test_scope(p)
    receipt = signer.sign_grant(_make_v3_grant_claims(p, key_id), key_id)
    valid, reason = verifier.verify(
        receipt, p,
        plot_id=p.plot_id,
        geometry_hash=p.geometry_hash,
        geometry_version=p.geometry_version,
        run_timestamp=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert valid and reason == "verified_v3_kms_grant"

    # Policy flips after verifier construction: legacy is still prohibited.
    monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_V3_KMS", "true")
    assert verifier.enforces_v3_only
    valid, reason = verifier.verify(
        {"grant": {"domain": "akaloris/layer0/positive-state-observation/v1"}, "mac": "0" * 64},
        p,
        plot_id=p.plot_id,
        geometry_hash=p.geometry_hash,
        geometry_version=p.geometry_version,
        run_timestamp=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert not valid and reason == "legacy_v1_v2_grant_prohibited_under_v3_kms_policy"
