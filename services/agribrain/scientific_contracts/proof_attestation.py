"""Immutable child proof attestation for canonical ASMAE publications.

Layer 5 simulation nodes and Layer 10 publications produce an immutable
canonical publication receipt.  This proof attestation document anchors the
scientific evidence membership root, uncertainty bounds root, and posterior
hash to that publication receipt with a server-owned digital signature.

Chain of authority:
  Immutable ASMAE node
    --> Canonical publication receipt
      --> Proof attestation V1 (child attestation referencing receipt)
        --> Binds: admitted evidence witness root
        --> Binds: bounded uncertainty witness root
        --> Binds: scientific posterior hash
        --> Signed by: server-owned issuer key
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import re
from typing import Any, Mapping, Optional

from .exceptions import ContractViolation
from .prescription_authorization import (
    canonical_data,
    canonical_hash,
    _required_text,
    _required_hash,
    _utc_instant,
)

ASMAE_PROOF_ATTESTATION_V1 = "asmae_proof_attestation_v1"
DEFAULT_ISSUER_KEY_ID = "pilot-issuer-key-v1"


def _get_signing_secret(override: Optional[str] = None) -> str:
    if override:
        return override.strip()
    secret = os.getenv("AGRIBRAIN_INTERNAL_SERVICE_SECRET", "").strip()
    if not secret:
        env = os.getenv(
            "NODE_ENV",
            os.getenv("ENVIRONMENT", os.getenv("ENV", os.getenv("APP_ENV", "development"))),
        ).lower()
        if env in ("production", "prod", "staging"):
            raise RuntimeError(
                "AGRIBRAIN_INTERNAL_SERVICE_SECRET must be set in non-development environments"
            )
        return "agribrain-internal-dev-secret-key-32bytes"
    return secret


def _compute_attestation_signature(attestation_hash: str, key_id: str, secret: str) -> str:
    key_bytes = hmac.new(secret.encode("utf-8"), key_id.encode("utf-8"), hashlib.sha256).digest()
    return hmac.new(key_bytes, attestation_hash.encode("utf-8"), hashlib.sha256).hexdigest()


@dataclass(frozen=True, kw_only=True)
class AsmaeProofAttestationV1:
    """Immutable, signed proof attestation linking publication receipt to evidence roots."""

    tenant_id: str
    farm_id: str
    plot_id: str
    geometry_hash: str
    crop_cycle_id: str
    snapshot_id: str
    canonical_publication_receipt_hash: str
    admitted_evidence_root_hash: str
    bounded_uncertainty_receipt_hash: str
    scientific_posterior_hash: str
    issued_at: str
    issuer_key_id: str = DEFAULT_ISSUER_KEY_ID
    signature: str = ""
    attestation_hash: str = ""
    schema_version: str = ASMAE_PROOF_ATTESTATION_V1

    def __post_init__(self) -> None:
        if self.schema_version != ASMAE_PROOF_ATTESTATION_V1:
            raise ContractViolation("Unsupported proof attestation schema")
        for name in ("tenant_id", "farm_id", "plot_id", "crop_cycle_id", "issuer_key_id"):
            object.__setattr__(self, name, _required_text(getattr(self, name), name))
        snapshot = _required_text(self.snapshot_id, "snapshot_id")
        if not snapshot.startswith("ASMAE-SNAPSHOT-"):
            raise ContractViolation("Proof attestation requires an ASMAE snapshot identity")
        object.__setattr__(self, "snapshot_id", snapshot)

        for name in (
            "geometry_hash",
            "canonical_publication_receipt_hash",
            "admitted_evidence_root_hash",
            "bounded_uncertainty_receipt_hash",
            "scientific_posterior_hash",
        ):
            object.__setattr__(self, name, _required_hash(getattr(self, name), name))

        object.__setattr__(self, "issued_at", _utc_instant(self.issued_at, "issued_at"))

    def unsigned_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "tenant_id": self.tenant_id,
            "farm_id": self.farm_id,
            "plot_id": self.plot_id,
            "geometry_hash": self.geometry_hash,
            "crop_cycle_id": self.crop_cycle_id,
            "snapshot_id": self.snapshot_id,
            "canonical_publication_receipt_hash": self.canonical_publication_receipt_hash,
            "admitted_evidence_root_hash": self.admitted_evidence_root_hash,
            "bounded_uncertainty_receipt_hash": self.bounded_uncertainty_receipt_hash,
            "scientific_posterior_hash": self.scientific_posterior_hash,
            "issued_at": self.issued_at,
            "issuer_key_id": self.issuer_key_id,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self.unsigned_payload()
        payload["attestation_hash"] = self.attestation_hash
        payload["signature"] = self.signature
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AsmaeProofAttestationV1":
        if not isinstance(data, Mapping):
            raise ContractViolation("Proof attestation must be a mapping")
        if data.get("schema_version") != ASMAE_PROOF_ATTESTATION_V1:
            raise ContractViolation("Unsupported proof attestation schema version")
        return cls(
            tenant_id=data.get("tenant_id", ""),
            farm_id=data.get("farm_id", ""),
            plot_id=data.get("plot_id", ""),
            geometry_hash=data.get("geometry_hash", ""),
            crop_cycle_id=data.get("crop_cycle_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            canonical_publication_receipt_hash=data.get("canonical_publication_receipt_hash", ""),
            admitted_evidence_root_hash=data.get("admitted_evidence_root_hash", ""),
            bounded_uncertainty_receipt_hash=data.get("bounded_uncertainty_receipt_hash", ""),
            scientific_posterior_hash=data.get("scientific_posterior_hash", ""),
            issued_at=data.get("issued_at", ""),
            issuer_key_id=data.get("issuer_key_id", DEFAULT_ISSUER_KEY_ID),
            signature=data.get("signature", ""),
            attestation_hash=data.get("attestation_hash", ""),
            schema_version=data.get("schema_version", ASMAE_PROOF_ATTESTATION_V1),
        )


def create_proof_attestation(
    *,
    tenant_id: str,
    farm_id: str,
    plot_id: str,
    geometry_hash: str,
    crop_cycle_id: str,
    snapshot_id: str,
    canonical_publication_receipt_hash: str,
    admitted_evidence_root_hash: str,
    bounded_uncertainty_receipt_hash: str,
    scientific_posterior_hash: str,
    issuer_key_id: str = DEFAULT_ISSUER_KEY_ID,
    issued_at: Optional[str] = None,
    secret: Optional[str] = None,
) -> AsmaeProofAttestationV1:
    """Create and sign an immutable AsmaeProofAttestationV1."""
    now_str = (
        issued_at
        if issued_at is not None
        else datetime.now(timezone.utc).isoformat()
    )
    base = AsmaeProofAttestationV1(
        tenant_id=tenant_id,
        farm_id=farm_id,
        plot_id=plot_id,
        geometry_hash=geometry_hash,
        crop_cycle_id=crop_cycle_id,
        snapshot_id=snapshot_id,
        canonical_publication_receipt_hash=canonical_publication_receipt_hash,
        admitted_evidence_root_hash=admitted_evidence_root_hash,
        bounded_uncertainty_receipt_hash=bounded_uncertainty_receipt_hash,
        scientific_posterior_hash=scientific_posterior_hash,
        issued_at=now_str,
        issuer_key_id=issuer_key_id,
    )
    unsigned = base.unsigned_payload()
    computed_hash = canonical_hash(unsigned)
    effective_secret = _get_signing_secret(secret)
    computed_sig = _compute_attestation_signature(computed_hash, base.issuer_key_id, effective_secret)

    signed = AsmaeProofAttestationV1(
        tenant_id=base.tenant_id,
        farm_id=base.farm_id,
        plot_id=base.plot_id,
        geometry_hash=base.geometry_hash,
        crop_cycle_id=base.crop_cycle_id,
        snapshot_id=base.snapshot_id,
        canonical_publication_receipt_hash=base.canonical_publication_receipt_hash,
        admitted_evidence_root_hash=base.admitted_evidence_root_hash,
        bounded_uncertainty_receipt_hash=base.bounded_uncertainty_receipt_hash,
        scientific_posterior_hash=base.scientific_posterior_hash,
        issued_at=base.issued_at,
        issuer_key_id=base.issuer_key_id,
        signature=computed_sig,
        attestation_hash=computed_hash,
    )
    return signed


def verify_proof_attestation(
    attestation: AsmaeProofAttestationV1 | Mapping[str, Any],
    *,
    secret: Optional[str] = None,
) -> AsmaeProofAttestationV1:
    """Cryptographically verify an immutable proof attestation.

    Fails closed if the hash does not match the canonical unsigned content or
    the server-owned HMAC signature is invalid.
    """
    att = (
        attestation
        if isinstance(attestation, AsmaeProofAttestationV1)
        else AsmaeProofAttestationV1.from_dict(attestation)
    )
    if not att.attestation_hash or not att.signature:
        raise ContractViolation("Proof attestation missing hash or signature")

    unsigned = att.unsigned_payload()
    expected_hash = canonical_hash(unsigned)
    if not hmac.compare_digest(att.attestation_hash, expected_hash):
        raise ContractViolation("Proof attestation content hash is invalid or tampered")

    effective_secret = _get_signing_secret(secret)
    expected_sig = _compute_attestation_signature(att.attestation_hash, att.issuer_key_id, effective_secret)
    if not hmac.compare_digest(att.signature, expected_sig):
        raise ContractViolation("Proof attestation digital signature is invalid or forged")

    return att
