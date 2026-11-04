"""L0-B2B06: Asymmetric KMS Signed-Issuer Interface & Verification Contracts (v3).

Production Target Domain: akaloris/layer0/positive-state-input/v3
Zonal Target Domain:      akaloris/layer0/positive-zone-state-input/v3

Implements:
1. Strict asymmetric KMS cryptographic signing (Ed25519 & ECDSA P-256 / ES256).
2. Deterministic canonical byte encoding (RFC 8785 JSON Canonicalization Scheme).
3. Complete signed claims schema including evidence ID, qualification decision ID,
   immutable scientific support root, tenant/plot scope, geometry epoch, and
   revocation revision anchor.
4. Total key isolation: signing private keys live in an isolated privileged signer
   interface (KmsAsymmetricSigner), while Layer 0 verifiers hold ONLY public keys.
5. Permitted observation variable enforcement.
6. Integration with DurableRevocationAuthority.
7. Explicit minting of V3StateGrantToken on successful admission.
"""
from __future__ import annotations

import abc
import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
from typing import Any, Mapping, Optional, Sequence, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    load_pem_public_key,
)

from services.agribrain.layer0.durable_revocation_authority import (
    DurableRevocationAuthority,
    _ensure_utc,
)
from services.agribrain.layer0.spatial_tenant_contract import (
    VerifiedPlotScope,
    FractionalPixelSupport,
    SpatialTenantDenied,
)


V3_GRANT_DOMAIN = "akaloris/layer0/positive-state-input/v3"
V3_ZONE_GRANT_DOMAIN = "akaloris/layer0/positive-zone-state-input/v3"

GRANT_PURPOSE = "kalman_state_observation"
WEATHER_GRANT_PURPOSE = "weather_state_forcing"
_ALLOWED_PURPOSES = frozenset((GRANT_PURPOSE, WEATHER_GRANT_PURPOSE))


class KmsAlgorithm(str, Enum):
    ED25519 = "Ed25519"
    ES256 = "ES256"


_V3_BASE_FIELDS = frozenset((
    "domain",
    "version",
    "algorithm",
    "key_id",
    "issuer_id",
    "purpose",
    "source",
    "permitted_variables",
    "packet_digest",
    "qualification_decision_id",
    "native_evidence_id",
    "policy_version",
    "qa_version",
    "scientific_support_root",
    "tenant_id",
    "plot_id",
    "geometry_hash",
    "geometry_version",
    "spatial_scope",
    "acquisition_start",
    "acquisition_end",
    "provenance_type",
    "temporal_role",
    "issued_at",
    "expires_at",
    "revocation_revision_anchor",
    "issuer_decision_ledger_id",
    "replay_idempotency_key",
))

_V3_ZONE_FIELDS = _V3_BASE_FIELDS | {"zone_id", "zone_geometry_hash", "mesia_support_root"}


def _canonical_normalize(value: Any) -> Any:
    """Normalize values for RFC 8785 deterministic JSON encoding."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite float in signed grant")
        # Format integer floats as integers
        if value.is_integer():
            return int(value)
        return value
    if isinstance(value, Enum):
        return _canonical_normalize(value.value)
    if isinstance(value, datetime):
        return _ensure_utc(value).isoformat()
    if isinstance(value, Mapping):
        if any(not isinstance(k, str) for k in value):
            raise TypeError("signed grant dictionary keys must be strings")
        return {k: _canonical_normalize(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_canonical_normalize(x) for x in value]
    raise TypeError(f"unsupported canonical type: {type(value).__name__}")


def canonical_grant_bytes(grant_claims: Mapping[str, Any]) -> bytes:
    """Return deterministic canonical RFC 8785 bytes for grant claims."""
    normalized = _canonical_normalize(grant_claims)
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


@dataclass(frozen=True)
class V3PositiveStateInputGrant:
    """Authoritative v3 cryptographic grant claims."""
    domain: str
    version: str
    algorithm: str
    key_id: str
    issuer_id: str
    purpose: str
    source: str
    permitted_variables: tuple[str, ...]
    packet_digest: str
    qualification_decision_id: str
    native_evidence_id: str
    policy_version: str
    qa_version: str
    scientific_support_root: str
    tenant_id: str
    plot_id: str
    geometry_hash: str
    geometry_version: int
    spatial_scope: str
    acquisition_start: str
    acquisition_end: str
    provenance_type: str
    temporal_role: str
    issued_at: str
    expires_at: str
    revocation_revision_anchor: int
    issuer_decision_ledger_id: str
    replay_idempotency_key: str
    zone_id: Optional[str] = None
    zone_geometry_hash: Optional[str] = None
    mesia_support_root: Optional[str] = None

    def __post_init__(self) -> None:
        if self.version != "v3":
            raise ValueError(f"invalid grant version: {self.version!r}")
        if self.algorithm not in ("Ed25519", "ES256"):
            raise ValueError(f"unsupported KMS algorithm: {self.algorithm!r}")
        if self.purpose not in _ALLOWED_PURPOSES:
            raise ValueError(f"unsupported grant purpose: {self.purpose!r}")
        if self.spatial_scope not in ("plot", "zone"):
            raise ValueError(f"invalid spatial scope: {self.spatial_scope!r}")
        if self.spatial_scope == "zone":
            if self.domain != V3_ZONE_GRANT_DOMAIN:
                raise ValueError("zone scope requires V3_ZONE_GRANT_DOMAIN")
            if not self.zone_id or not self.zone_geometry_hash or not self.mesia_support_root:
                raise ValueError("zone scope requires zone_id, zone_geometry_hash, and mesia_support_root")
        else:
            if self.domain != V3_GRANT_DOMAIN:
                raise ValueError("plot scope requires V3_GRANT_DOMAIN")

        # Validate types
        if isinstance(self.geometry_version, bool) or not isinstance(self.geometry_version, int) or self.geometry_version <= 0:
            raise ValueError("geometry_version must be a positive integer")
        if isinstance(self.revocation_revision_anchor, bool) or not isinstance(self.revocation_revision_anchor, int) or self.revocation_revision_anchor < 0:
            raise ValueError("revocation_revision_anchor must be a non-negative integer")

        # Validate SHA-256 digests
        for digest_name, digest_val in (
            ("packet_digest", self.packet_digest),
            ("scientific_support_root", self.scientific_support_root),
        ):
            if not isinstance(digest_val, str) or len(digest_val) != 64:
                raise ValueError(f"invalid {digest_name} hex digest")
            int(digest_val, 16)

        # Validate timestamps
        t_issue = _ensure_utc(self.issued_at)
        t_expire = _ensure_utc(self.expires_at)
        if t_expire <= t_issue:
            raise ValueError("expires_at must be strictly after issued_at")

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "domain": self.domain,
            "version": self.version,
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "issuer_id": self.issuer_id,
            "purpose": self.purpose,
            "source": self.source,
            "permitted_variables": list(self.permitted_variables),
            "packet_digest": self.packet_digest,
            "qualification_decision_id": self.qualification_decision_id,
            "native_evidence_id": self.native_evidence_id,
            "policy_version": self.policy_version,
            "qa_version": self.qa_version,
            "scientific_support_root": self.scientific_support_root,
            "tenant_id": self.tenant_id,
            "plot_id": self.plot_id,
            "geometry_hash": self.geometry_hash,
            "geometry_version": self.geometry_version,
            "spatial_scope": self.spatial_scope,
            "acquisition_start": self.acquisition_start,
            "acquisition_end": self.acquisition_end,
            "provenance_type": self.provenance_type,
            "temporal_role": self.temporal_role,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "revocation_revision_anchor": self.revocation_revision_anchor,
            "issuer_decision_ledger_id": self.issuer_decision_ledger_id,
            "replay_idempotency_key": self.replay_idempotency_key,
        }
        if self.spatial_scope == "zone":
            d["zone_id"] = self.zone_id
            d["zone_geometry_hash"] = self.zone_geometry_hash
            d["mesia_support_root"] = self.mesia_support_root
        return d

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> V3PositiveStateInputGrant:
        return cls(
            domain=data["domain"],
            version=data["version"],
            algorithm=data["algorithm"],
            key_id=data["key_id"],
            issuer_id=data["issuer_id"],
            purpose=data["purpose"],
            source=data["source"],
            permitted_variables=tuple(data.get("permitted_variables", ())),
            packet_digest=data["packet_digest"],
            qualification_decision_id=data["qualification_decision_id"],
            native_evidence_id=data["native_evidence_id"],
            policy_version=data["policy_version"],
            qa_version=data["qa_version"],
            scientific_support_root=data["scientific_support_root"],
            tenant_id=data["tenant_id"],
            plot_id=data["plot_id"],
            geometry_hash=data["geometry_hash"],
            geometry_version=data["geometry_version"],
            spatial_scope=data["spatial_scope"],
            acquisition_start=data["acquisition_start"],
            acquisition_end=data["acquisition_end"],
            provenance_type=data["provenance_type"],
            temporal_role=data["temporal_role"],
            issued_at=data["issued_at"],
            expires_at=data["expires_at"],
            revocation_revision_anchor=data["revocation_revision_anchor"],
            issuer_decision_ledger_id=data["issuer_decision_ledger_id"],
            replay_idempotency_key=data["replay_idempotency_key"],
            zone_id=data.get("zone_id"),
            zone_geometry_hash=data.get("zone_geometry_hash"),
            mesia_support_root=data.get("mesia_support_root"),
        )


@dataclass(frozen=True)
class V3SignedReceipt:
    """Detached cryptographic receipt containing grant and asymmetric signature."""
    grant: V3PositiveStateInputGrant
    signature: str  # base64url-encoded signature
    key_id: str
    algorithm: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "grant": self.grant.to_dict(),
            "signature": self.signature,
            "key_id": self.key_id,
            "algorithm": self.algorithm,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> V3SignedReceipt:
        if not isinstance(data, Mapping) or set(data) != {"grant", "signature", "key_id", "algorithm"}:
            raise ValueError("malformed V3SignedReceipt structure")
        grant = V3PositiveStateInputGrant.from_dict(data["grant"])
        if grant.key_id != data["key_id"] or grant.algorithm != data["algorithm"]:
            raise ValueError("receipt envelope header mismatch")
        return cls(
            grant=grant,
            signature=data["signature"],
            key_id=data["key_id"],
            algorithm=data["algorithm"],
        )


@dataclass(frozen=True)
class V3StateGrantToken:
    """Authoritative proof of state grant admission minted ONLY upon verifier acceptance."""
    admitted: bool
    eligible_for_state_grant: bool
    source_qualified: bool
    authority: str
    grant_digest: str
    key_id: str
    issuer_id: str
    revocation_revision: int
    admitted_at: str
    admitted_variables: tuple[str, ...]
    spatial_classification: str


class KmsAsymmetricSigner(abc.ABC):
    """Abstract interface for isolated privileged KMS signing service / HSM."""

    @abc.abstractmethod
    def sign_grant(self, grant_claims: Mapping[str, Any], key_id: str) -> V3SignedReceipt:
        """Sign grant claims using the isolated private key for key_id."""

    @abc.abstractmethod
    def get_public_key_pem(self, key_id: str) -> str:
        """Export the public key in PEM format."""

    @abc.abstractmethod
    def get_public_key_bytes(self, key_id: str) -> bytes:
        """Export raw public key bytes."""

    @property
    @abc.abstractmethod
    def algorithm(self) -> str:
        """Algorithm name (Ed25519 or ES256)."""


class LocalKmsAsymmetricSigner(KmsAsymmetricSigner):
    """Hermetic KMS signer implementation using cryptography.
    
    Private keys are strictly encapsulated inside this instance and are NEVER exported.
    """

    def __init__(self, algorithm: KmsAlgorithm = KmsAlgorithm.ED25519) -> None:
        self._algo = KmsAlgorithm(algorithm)
        self._private_keys: dict[str, Any] = {}
        self._public_keys: dict[str, Any] = {}

    @property
    def algorithm(self) -> str:
        return self._algo.value

    def provision_key(self, key_id: str) -> str:
        """Generate a new isolated private/public key pair, returning key_id."""
        if not isinstance(key_id, str) or not key_id:
            raise ValueError("key_id must be non-empty string")
        if key_id in self._private_keys:
            raise ValueError(f"key_id {key_id!r} already provisioned")

        if self._algo == KmsAlgorithm.ED25519:
            priv = ed25519.Ed25519PrivateKey.generate()
            pub = priv.public_key()
        elif self._algo == KmsAlgorithm.ES256:
            priv = ec.generate_private_key(ec.SECP256R1())
            pub = priv.public_key()
        else:
            raise ValueError(f"unsupported algorithm: {self._algo}")

        self._private_keys[key_id] = priv
        self._public_keys[key_id] = pub
        return key_id

    def get_public_key_pem(self, key_id: str) -> str:
        pub = self._public_keys.get(key_id)
        if pub is None:
            raise KeyError(f"unknown key_id {key_id!r}")
        pem = pub.public_bytes(
            encoding=Encoding.PEM,
            format=PublicFormat.SubjectPublicKeyInfo,
        )
        return pem.decode("ascii")

    def get_public_key_bytes(self, key_id: str) -> bytes:
        pub = self._public_keys.get(key_id)
        if pub is None:
            raise KeyError(f"unknown key_id {key_id!r}")
        if self._algo == KmsAlgorithm.ED25519:
            return pub.public_bytes(
                encoding=Encoding.Raw,
                format=PublicFormat.Raw,
            )
        return pub.public_bytes(
            encoding=Encoding.DER,
            format=PublicFormat.SubjectPublicKeyInfo,
        )

    def sign_grant(self, grant_claims: Mapping[str, Any], key_id: str) -> V3SignedReceipt:
        priv = self._private_keys.get(key_id)
        if priv is None:
            raise KeyError(f"unknown KMS key_id: {key_id!r}")

        grant = (
            grant_claims
            if isinstance(grant_claims, V3PositiveStateInputGrant)
            else V3PositiveStateInputGrant.from_dict(grant_claims)
        )
        if grant.key_id != key_id:
            raise ValueError(f"grant claims key_id {grant.key_id!r} does not match signer {key_id!r}")
        if grant.algorithm != self._algo.value:
            raise ValueError(f"grant algorithm {grant.algorithm!r} does not match signer {self._algo.value!r}")

        canonical_bytes = canonical_grant_bytes(grant.to_dict())

        if self._algo == KmsAlgorithm.ED25519:
            raw_sig = priv.sign(canonical_bytes)
        elif self._algo == KmsAlgorithm.ES256:
            # Deterministic ECDSA signature over SHA-256
            raw_sig = priv.sign(canonical_bytes, ec.ECDSA(hashes.SHA256()))
        else:
            raise ValueError(f"unsupported algorithm: {self._algo}")

        sig_b64 = base64.urlsafe_b64encode(raw_sig).decode("ascii")
        return V3SignedReceipt(
            grant=grant,
            signature=sig_b64,
            key_id=key_id,
            algorithm=self._algo.value,
        )


@dataclass(frozen=True)
class KmsPublicKeyEntry:
    """Public key registration entry with authorization parameters."""
    key_id: str
    issuer_id: str
    source: str
    algorithm: str
    public_key: Any  # Ed25519PublicKey or EllipticCurvePublicKey
    valid_from: datetime
    valid_until: datetime
    permitted_purposes: frozenset[str] = field(default_factory=lambda: _ALLOWED_PURPOSES)

    def is_valid_at(self, t: datetime) -> bool:
        utc = _ensure_utc(t)
        return self.valid_from <= utc <= self.valid_until


class KmsPublicKeyRegistry:
    """Registry holding ONLY public keys and their authorized scope."""

    def __init__(self) -> None:
        self._entries: dict[str, KmsPublicKeyEntry] = {}

    def register_public_key(
        self,
        key_id: str,
        issuer_id: str,
        source: str,
        algorithm: str,
        public_key_pem_or_bytes: str | bytes,
        *,
        valid_from: datetime,
        valid_until: datetime,
        permitted_purposes: Sequence[str] = (GRANT_PURPOSE, WEATHER_GRANT_PURPOSE),
    ) -> None:
        if not isinstance(key_id, str) or not key_id:
            raise ValueError("key_id must be non-empty string")
        if not isinstance(issuer_id, str) or not issuer_id:
            raise ValueError("issuer_id must be non-empty string")
        if not isinstance(source, str) or not source:
            raise ValueError("source must be non-empty string")
        if algorithm not in ("Ed25519", "ES256"):
            raise ValueError(f"unsupported algorithm: {algorithm}")

        t_from = _ensure_utc(valid_from)
        t_until = _ensure_utc(valid_until)
        if t_until <= t_from:
            raise ValueError("valid_until must be strictly after valid_from")

        # Parse public key
        if isinstance(public_key_pem_or_bytes, str):
            pub = load_pem_public_key(public_key_pem_or_bytes.encode("ascii"))
        elif isinstance(public_key_pem_or_bytes, bytes):
            if algorithm == "Ed25519" and len(public_key_pem_or_bytes) == 32:
                pub = ed25519.Ed25519PublicKey.from_public_bytes(public_key_pem_or_bytes)
            else:
                pub = load_pem_public_key(public_key_pem_or_bytes)
        else:
            raise TypeError("public key must be PEM string or bytes")

        entry = KmsPublicKeyEntry(
            key_id=key_id,
            issuer_id=issuer_id,
            source=source,
            algorithm=algorithm,
            public_key=pub,
            valid_from=t_from,
            valid_until=t_until,
            permitted_purposes=frozenset(permitted_purposes),
        )
        self._entries[key_id] = entry

    def get_entry(self, key_id: str) -> KmsPublicKeyEntry | None:
        return self._entries.get(key_id)

    def __contains__(self, key_id: str) -> bool:
        return key_id in self._entries

    def __len__(self) -> int:
        return len(self._entries)


class V3KmsGrantVerifier:
    """Asymmetric KMS Grant Verifier for Layer 0 State Input Admission.
    
    Verifies:
    1. Cryptographic signature against KMS public key.
    2. Exact packet digest binding against current observation content.
    3. Caller scope binding (tenant_id, plot_id, geometry_hash, geometry_version).
    4. Permitted variables allowlist.
    5. Durable revocation ledger status (key active, plot/zone not revoked).
    6. Mints V3StateGrantToken with eligible_for_state_grant=True only upon full pass.
    """

    def __init__(
        self,
        key_registry: KmsPublicKeyRegistry,
        revocation_authority: DurableRevocationAuthority | None = None,
        *,
        trusted_zone_registry: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        if not isinstance(key_registry, KmsPublicKeyRegistry):
            raise TypeError("key_registry must be KmsPublicKeyRegistry")
        self._registry = key_registry
        self._revocation = revocation_authority
        self._zone_registry = dict(trusted_zone_registry or {})

    @property
    def revocation_enforced(self) -> bool:
        return self._revocation is not None

    @property
    def zone_authority_configured(self) -> bool:
        return bool(self._zone_registry)

    @property
    def revocation_revision(self) -> int | None:
        return self._revocation.current_revision if self._revocation else None

    @property
    def revocation_snapshot_digest(self) -> str | None:
        return self._revocation.current_digest if self._revocation else None

    def verify(
        self,
        receipt: Any,
        packet: Any,
        *,
        plot_id: str,
        geometry_hash: str,
        geometry_version: int | None,
        run_timestamp: datetime,
        purpose: str = GRANT_PURPOSE,
        variables: Sequence[str] | None = None,
        tenant_id: str | None = None,
    ) -> tuple[bool, str]:
        """Verify v3 receipt, returning (valid, reason) for Layer 0 verifier compatibility."""
        valid, reason, _token = self.verify_grant(
            receipt,
            packet,
            plot_id=plot_id,
            geometry_hash=geometry_hash,
            geometry_version=geometry_version,
            run_timestamp=run_timestamp,
            purpose=purpose,
            variables=variables,
            tenant_id=tenant_id,
        )
        return valid, reason

    def verify_grant(
        self,
        receipt: Any,
        packet: Any,
        *,
        plot_id: str,
        geometry_hash: str,
        geometry_version: int | None,
        run_timestamp: datetime,
        purpose: str = GRANT_PURPOSE,
        variables: Sequence[str] | None = None,
        tenant_id: str | None = None,
    ) -> tuple[bool, str, Optional[V3StateGrantToken]]:
        """Verify v3 receipt against KMS public key, packet content, scope, and revocation."""
        try:
            # 1. Purpose check
            if purpose not in _ALLOWED_PURPOSES:
                return False, "unsupported_grant_purpose", None

            # 2. Scope inputs check
            if (
                not isinstance(plot_id, str) or not plot_id
                or not isinstance(geometry_hash, str) or not geometry_hash
                or isinstance(geometry_version, bool)
                or not isinstance(geometry_version, int)
                or geometry_version <= 0
            ):
                return False, "missing_authoritative_caller_scope", None

            run_time = _ensure_utc(run_timestamp)

            # 3. Parse receipt structure
            if not isinstance(receipt, (Mapping, V3SignedReceipt)):
                return False, "missing_or_malformed_v3_receipt", None

            signed_receipt = (
                receipt
                if isinstance(receipt, V3SignedReceipt)
                else V3SignedReceipt.from_dict(receipt)
            )
            grant = signed_receipt.grant

            # 4. Key registration lookup
            entry = self._registry.get_entry(grant.key_id)
            if entry is None:
                return False, "unregistered_kms_key", None

            # 5. Key authorization rules
            if entry.algorithm != grant.algorithm or entry.issuer_id != grant.issuer_id:
                return False, "kms_key_issuer_mismatch", None
            source_val = getattr(getattr(packet, "source", None), "value", None) or getattr(packet, "source", None)
            if entry.source != grant.source or entry.source != source_val:
                return False, "kms_key_source_mismatch", None
            if purpose not in entry.permitted_purposes or grant.purpose != purpose:
                return False, "kms_key_purpose_unauthorized", None
            if not entry.is_valid_at(run_time):
                return False, "kms_key_temporal_out_of_bounds", None

            # 6. Cryptographic signature check
            canonical_bytes = canonical_grant_bytes(grant.to_dict())
            raw_sig = base64.urlsafe_b64decode(signed_receipt.signature.encode("ascii"))

            try:
                if grant.algorithm == "Ed25519":
                    entry.public_key.verify(raw_sig, canonical_bytes)
                elif grant.algorithm == "ES256":
                    entry.public_key.verify(raw_sig, canonical_bytes, ec.ECDSA(hashes.SHA256()))
                else:
                    return False, "unsupported_kms_algorithm", None
            except InvalidSignature:
                return False, "bad_kms_signature", None

            # 7. Scope binding checks
            if tenant_id is not None and grant.tenant_id != tenant_id:
                return False, "wrong_grant_tenant_scope", None
            if grant.plot_id != plot_id or grant.geometry_hash != geometry_hash or grant.geometry_version != geometry_version:
                return False, "wrong_grant_plot_geometry_scope", None

            packet_plot = getattr(packet, "plot_id", None)
            packet_geom = getattr(packet, "geometry_hash", None)
            packet_ver = getattr(packet, "geometry_version", None)
            if packet_plot != plot_id or packet_geom != geometry_hash or packet_ver != geometry_version:
                return False, "packet_scope_mismatch", None

            # 8. Zonal checks if zone scope
            if grant.spatial_scope == "zone":
                if purpose != GRANT_PURPOSE:
                    return False, "zone_weather_forcing_not_authorized", None
                payload = getattr(packet, "payload", {}) or {}
                zone_id = payload.get("zone_id") or getattr(packet, "zone_id", None)
                zone_hash = payload.get("zone_geometry_hash")
                trusted_plot = self._zone_registry.get(plot_id)
                if (
                    not zone_id or not zone_hash
                    or grant.zone_id != zone_id
                    or grant.zone_geometry_hash != zone_hash
                    or trusted_plot is None
                    or trusted_plot.get("geometry_hash") != geometry_hash
                    or trusted_plot.get("geometry_version") != geometry_version
                    or trusted_plot.get("zones", {}).get(zone_id) != zone_hash
                ):
                    return False, "unregistered_or_foreign_zone_geometry", None

            # 9. Packet digest binding
            from services.agribrain.layer0.positive_observation_admission import observation_packet_digest
            expected_digest = observation_packet_digest(packet)
            if grant.packet_digest != expected_digest:
                return False, "packet_content_digest_mismatch", None

            # 10. Temporal validity
            t_issue = _ensure_utc(grant.issued_at)
            t_expire = _ensure_utc(grant.expires_at)
            if run_time < t_issue or run_time > t_expire:
                return False, "grant_temporal_window_expired_or_future", None

            # 11. Permitted variables check
            if variables is not None:
                missing = [v for v in variables if v not in grant.permitted_variables]
                if missing:
                    return False, f"unpermitted_variables_in_state_input:{','.join(missing)}", None

            # 12. Durable revocation check
            if self._revocation is not None:
                zone_id_check = grant.zone_id if grant.spatial_scope == "zone" else None
                rev_ok, rev_reason = self._revocation.check_authority(
                    grant.key_id,
                    run_time,
                    revision_anchor=grant.revocation_revision_anchor,
                    plot_id=grant.plot_id,
                    zone_id=zone_id_check,
                    grant_id=grant.replay_idempotency_key,
                )
                if not rev_ok:
                    return False, rev_reason, None

            # 13. Mint V3StateGrantToken
            grant_digest = hashlib.sha256(canonical_bytes).hexdigest()
            token = V3StateGrantToken(
                admitted=True,
                eligible_for_state_grant=True,
                source_qualified=True,
                authority="v3_asymmetric_kms_authorized",
                grant_digest=grant_digest,
                key_id=grant.key_id,
                issuer_id=grant.issuer_id,
                revocation_revision=(
                    self._revocation.current_revision if self._revocation else grant.revocation_revision_anchor
                ),
                admitted_at=run_time.isoformat(),
                admitted_variables=grant.permitted_variables,
                spatial_classification=(
                    getattr(getattr(packet, "spatial_provenance", {}), "get", lambda *_: "FULL_CONTAINED")(
                        "spatial_classification", "FULL_CONTAINED"
                    )
                ),
            )

            return True, "verified_v3_kms_grant", token

        except Exception as exc:
            return False, f"v3_verification_error:{type(exc).__name__}", None
