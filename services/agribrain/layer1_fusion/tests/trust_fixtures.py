"""Isolated test authority trust fixtures for Layer 1 fusion tests (R12-01).

Prohibits private key generation and self-provisioning in production verifiers.
Private keys are strictly confined to test fixtures and never derived from predictable seeds.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric import ed25519

from ..truth_bridge import (
    SensorAttestationReceipt,
    PublicationAttestationReceipt,
    register_trusted_issuer_public_key,
    compute_reading_content_digest,
    compute_sensor_receipt_canonical_bytes,
    compute_publication_receipt_canonical_bytes,
    get_revocation_store,
)

_TEST_FIXTURE_PRIVATE_KEYS: Dict[str, ed25519.Ed25519PrivateKey] = {}


def provision_test_issuer_keypair(issuer: str) -> Tuple[ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey]:
    """Generate a random Ed25519 keypair for test assertions and register the public root (R12-01)."""
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()
    register_trusted_issuer_public_key(issuer, pub)
    _TEST_FIXTURE_PRIVATE_KEYS[issuer] = priv
    return priv, pub


def get_test_issuer_private_key(issuer: str) -> ed25519.Ed25519PrivateKey:
    """Retrieve test private key or provision fresh isolated keypair (R12-01)."""
    if issuer in _TEST_FIXTURE_PRIVATE_KEYS:
        return _TEST_FIXTURE_PRIVATE_KEYS[issuer]
    priv, _ = provision_test_issuer_keypair(issuer)
    return priv


def sign_test_sensor_receipt_data(
    receipt_id: str,
    issuer: str,
    device_id: str,
    plot_id: str,
    variable: str,
    calibration_profile_id: str,
    status: str = "active",
    content_digest: Optional[str] = None,
    observation_instant: Optional[str] = None,
    first_available_at: Optional[str] = None,
    revocation_epoch: Optional[int] = None,
    private_key: Optional[ed25519.Ed25519PrivateKey] = None,
) -> str:
    """Sign sensor receipt data using test private key."""
    if private_key is None:
        private_key = get_test_issuer_private_key(issuer)
    eff_epoch = get_revocation_store().revocation_epoch if revocation_epoch is None else int(revocation_epoch)
    canonical = compute_sensor_receipt_canonical_bytes(
        receipt_id=receipt_id,
        issuer=issuer,
        device_id=device_id,
        plot_id=plot_id,
        variable=variable,
        calibration_profile_id=calibration_profile_id,
        status=status,
        content_digest=content_digest,
        observation_instant=observation_instant,
        first_available_at=first_available_at,
        revocation_epoch=eff_epoch,
    )
    sig_bytes = private_key.sign(canonical)
    return "ed25519:" + sig_bytes.hex()


def create_signed_sensor_receipt(
    receipt_id: str,
    issuer: str,
    device_id: str,
    plot_id: str,
    variable: str,
    calibration_profile_id: str,
    status: str = "active",
    content_digest: Optional[str] = None,
    observation_instant: Optional[str] = None,
    first_available_at: Optional[str] = None,
    revocation_epoch: Optional[int] = None,
    private_key: Optional[Any] = None,
    reading_value: Optional[Any] = None,
    reading_unit: Optional[str] = None,
    observed_at: Optional[Any] = None,
) -> SensorAttestationReceipt:
    """Create a fully signed, authentic cryptographic sensor attestation receipt in test harness (R10-01, R11-02, R12-01)."""
    if observation_instant is None:
        obs = observed_at or datetime(2026, 11, 9, 10, tzinfo=timezone.utc)
        observation_instant = obs.isoformat() if hasattr(obs, "isoformat") else str(obs)

    if content_digest is None:
        val = 0.35 if reading_value is None else reading_value
        obs_for_digest = observed_at or observation_instant
        content_digest = compute_reading_content_digest(
            device_id=device_id,
            plot_id=plot_id,
            variable=variable,
            value=val,
            unit=reading_unit or "fraction",
            observed_at=obs_for_digest,
        )

    eff_epoch = get_revocation_store().revocation_epoch if revocation_epoch is None else int(revocation_epoch)
    sig = sign_test_sensor_receipt_data(
        receipt_id=receipt_id,
        issuer=issuer,
        device_id=device_id,
        plot_id=plot_id,
        variable=variable,
        calibration_profile_id=calibration_profile_id,
        status=status,
        content_digest=content_digest,
        observation_instant=observation_instant,
        first_available_at=first_available_at,
        revocation_epoch=eff_epoch,
        private_key=private_key,
    )
    return SensorAttestationReceipt(
        receipt_id=receipt_id,
        issuer=issuer,
        device_id=device_id,
        plot_id=plot_id,
        variable=variable,
        calibration_profile_id=calibration_profile_id,
        status=status,
        content_digest=content_digest,
        observation_instant=observation_instant,
        first_available_at=first_available_at,
        revocation_epoch=eff_epoch,
        signature=sig,
    )


def sign_test_publication_receipt_data(
    receipt_id: str,
    issuer: str,
    source_family: str,
    acquisition_id: str,
    published_at: Any,
    content_hash: Optional[str] = None,
    status: str = "active",
    private_key: Optional[ed25519.Ed25519PrivateKey] = None,
) -> str:
    """Sign publication receipt data using test private key."""
    if private_key is None:
        private_key = get_test_issuer_private_key(issuer)
    canonical = compute_publication_receipt_canonical_bytes(
        receipt_id=receipt_id,
        issuer=issuer,
        source_family=source_family,
        acquisition_id=acquisition_id,
        published_at=published_at,
        content_hash=content_hash,
        status=status,
    )
    sig_bytes = private_key.sign(canonical)
    return "ed25519:" + sig_bytes.hex()


def create_signed_publication_receipt(
    receipt_id: str,
    issuer: str,
    source_family: str,
    acquisition_id: str,
    published_at: Any,
    content_hash: Optional[str] = None,
    status: str = "active",
    private_key: Optional[Any] = None,
) -> PublicationAttestationReceipt:
    """Create a fully signed, authentic cryptographic publication attestation receipt in test harness (R10-02, R11-03, R12-01)."""
    pub_iso = published_at.isoformat() if hasattr(published_at, "isoformat") else str(published_at)
    sig = sign_test_publication_receipt_data(
        receipt_id=receipt_id,
        issuer=issuer,
        source_family=source_family,
        acquisition_id=acquisition_id,
        published_at=pub_iso,
        content_hash=content_hash,
        status=status,
        private_key=private_key,
    )
    return PublicationAttestationReceipt(
        receipt_id=receipt_id,
        issuer=issuer,
        source_family=source_family,
        acquisition_id=acquisition_id,
        published_at=pub_iso,
        content_hash=content_hash,
        status=status,
        signature=sig,
    )
