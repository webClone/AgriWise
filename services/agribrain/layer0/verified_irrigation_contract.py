"""L0-B2B07: Verified Delivered Irrigation & Water Balance Physical Contracts (v3).

Production Target Domain: akaloris/layer0/verified-delivered-irrigation/v3
Production Purpose:       physical_delivered_irrigation_forcing

Implements:
1. Strict asymmetric KMS cryptographic signing (Ed25519 & ECDSA P-256 / ES256).
2. Deterministic canonical byte encoding (RFC 8785 JSON Canonicalization Scheme).
3. Authoritative physical claims binding:
   - Tenant, plot, geometry version/hash, and zone support.
   - Exact UTC start/end delivery interval.
   - Metered physical delivered volume in liters (> 0).
   - Wetted surface area in square meters (> 0).
   - Calibrated delivery efficiency fraction (0, 1].
   - Verified net infiltrated depth in mm matching:
     net_depth_mm = (volume_liters * efficiency) / area_m2
   - Calibration ID and source evidence CAS root.
   - Depth uncertainty standard deviation (sigma > 0).
   - Replay idempotency key and DurableRevocationAuthority anchor.
4. Total separation of authority:
   - scientific_publication_authorized is permanently False.
   - actuator_control_authorized is permanently False.
   - Receipt cannot be reused for positive state observation or actuator command.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from typing import Any, Mapping, Optional, Sequence, Set, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, ed25519

from services.agribrain.layer0.durable_revocation_authority import (
    DurableRevocationAuthority,
    _ensure_utc,
)
from services.agribrain.layer0.v3_kms_signed_issuer import (
    KmsAlgorithm,
    KmsPublicKeyEntry,
    KmsPublicKeyRegistry,
    canonical_grant_bytes,
)

VERIFIED_IRRIGATION_DOMAIN = "akaloris/layer0/verified-delivered-irrigation/v3"
VERIFIED_IRRIGATION_PURPOSE = "physical_delivered_irrigation_forcing"
_ALLOWED_IRRIGATION_ALGORITHMS = frozenset(("Ed25519", "ES256"))


def _parse_iso_utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"invalid ISO timestamp {value!r}") from exc
    else:
        raise TypeError(f"expected ISO timestamp string or datetime, got {type(value).__name__}")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"timestamp {value!r} must have timezone")
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class VerifiedDeliveredIrrigationGrant:
    """Authoritative physical delivery grant claims."""
    domain: str
    version: str
    algorithm: str
    key_id: str
    issuer_id: str
    purpose: str
    receipt_id: str
    tenant_id: str
    plot_id: str
    geometry_hash: str
    geometry_version: int
    zone_id: str
    delivery_start: str
    delivery_end: str
    delivered_volume_liters: float
    wetted_area_m2: float
    delivery_efficiency_fraction: float
    net_infiltrated_depth_mm: float
    conversion_calibration_id: str
    depth_uncertainty_sigma_mm: float
    source_evidence_cas_root: str
    replay_idempotency_key: str
    revocation_revision_anchor: int
    issued_at: str
    expires_at: str
    scientific_publication_authorized: bool = False
    actuator_control_authorized: bool = False

    def __post_init__(self) -> None:
        if self.domain != VERIFIED_IRRIGATION_DOMAIN:
            raise ValueError(f"invalid domain {self.domain!r}; expected {VERIFIED_IRRIGATION_DOMAIN!r}")
        if self.purpose != VERIFIED_IRRIGATION_PURPOSE:
            raise ValueError(f"invalid purpose {self.purpose!r}; expected {VERIFIED_IRRIGATION_PURPOSE!r}")
        if self.version != "v3":
            raise ValueError(f"unsupported version {self.version!r}")
        if self.algorithm not in _ALLOWED_IRRIGATION_ALGORITHMS:
            raise ValueError(f"unsupported algorithm {self.algorithm!r}")

        # Scientific state separation: never grant publication or actuation rights
        if self.scientific_publication_authorized is not False:
            raise ValueError("scientific publication authorization cannot be granted by physical delivery receipt")
        if self.actuator_control_authorized is not False:
            raise ValueError("actuator control authorization cannot be granted by physical delivery receipt")

        # Identity and string checks
        str_fields = {
            "key_id": self.key_id,
            "issuer_id": self.issuer_id,
            "receipt_id": self.receipt_id,
            "tenant_id": self.tenant_id,
            "plot_id": self.plot_id,
            "geometry_hash": self.geometry_hash,
            "zone_id": self.zone_id,
            "conversion_calibration_id": self.conversion_calibration_id,
            "source_evidence_cas_root": self.source_evidence_cas_root,
            "replay_idempotency_key": self.replay_idempotency_key,
        }
        for name, val in str_fields.items():
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"{name} must be a non-empty string")

        if not isinstance(self.geometry_version, int) or isinstance(self.geometry_version, bool) or self.geometry_version < 1:
            raise ValueError("geometry_version must be integer >= 1")
        if not isinstance(self.revocation_revision_anchor, int) or isinstance(self.revocation_revision_anchor, bool) or self.revocation_revision_anchor < 0:
            raise ValueError("revocation_revision_anchor must be integer >= 0")

        # Numeric physical checks
        num_fields = {
            "delivered_volume_liters": self.delivered_volume_liters,
            "wetted_area_m2": self.wetted_area_m2,
            "delivery_efficiency_fraction": self.delivery_efficiency_fraction,
            "net_infiltrated_depth_mm": self.net_infiltrated_depth_mm,
            "depth_uncertainty_sigma_mm": self.depth_uncertainty_sigma_mm,
        }
        for name, val in num_fields.items():
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
                raise ValueError(f"{name} must be finite number")

        if self.delivered_volume_liters <= 0.0:
            raise ValueError("zero_or_negative_volume")
        if self.wetted_area_m2 <= 0.0:
            raise ValueError("zero_or_negative_wetted_area")
        if not (0.0 < self.delivery_efficiency_fraction <= 1.0):
            raise ValueError("invalid_delivery_efficiency")
        if self.net_infiltrated_depth_mm <= 0.0:
            raise ValueError("invalid_net_infiltrated_depth")
        if self.depth_uncertainty_sigma_mm <= 0.0:
            raise ValueError("invalid_depth_uncertainty")

        # Physical dimensional conversion verification:
        # 1 liter on 1 m2 = 1 mm depth
        # net_depth_mm = (delivered_volume_liters * delivery_efficiency_fraction) / wetted_area_m2
        expected_net_depth = (self.delivered_volume_liters * self.delivery_efficiency_fraction) / self.wetted_area_m2
        if not math.isclose(self.net_infiltrated_depth_mm, expected_net_depth, rel_tol=1e-5, abs_tol=1e-6):
            raise ValueError(
                f"inconsistent depth conversion: net_infiltrated_depth_mm={self.net_infiltrated_depth_mm} "
                f"does not match calculated {expected_net_depth:.6f} mm"
            )

        # Temporal validity
        t_start = _parse_iso_utc(self.delivery_start)
        t_end = _parse_iso_utc(self.delivery_end)
        t_issued = _parse_iso_utc(self.issued_at)
        t_expires = _parse_iso_utc(self.expires_at)

        if t_end < t_start:
            raise ValueError("delivery_end cannot precede delivery_start")
        if t_expires <= t_issued:
            raise ValueError("expires_at must be strictly after issued_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "version": self.version,
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "issuer_id": self.issuer_id,
            "purpose": self.purpose,
            "receipt_id": self.receipt_id,
            "tenant_id": self.tenant_id,
            "plot_id": self.plot_id,
            "geometry_hash": self.geometry_hash,
            "geometry_version": self.geometry_version,
            "zone_id": self.zone_id,
            "delivery_start": self.delivery_start,
            "delivery_end": self.delivery_end,
            "delivered_volume_liters": self.delivered_volume_liters,
            "wetted_area_m2": self.wetted_area_m2,
            "delivery_efficiency_fraction": self.delivery_efficiency_fraction,
            "net_infiltrated_depth_mm": self.net_infiltrated_depth_mm,
            "conversion_calibration_id": self.conversion_calibration_id,
            "depth_uncertainty_sigma_mm": self.depth_uncertainty_sigma_mm,
            "source_evidence_cas_root": self.source_evidence_cas_root,
            "replay_idempotency_key": self.replay_idempotency_key,
            "revocation_revision_anchor": self.revocation_revision_anchor,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "scientific_publication_authorized": self.scientific_publication_authorized,
            "actuator_control_authorized": self.actuator_control_authorized,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> VerifiedDeliveredIrrigationGrant:
        return cls(
            domain=data["domain"],
            version=data["version"],
            algorithm=data["algorithm"],
            key_id=data["key_id"],
            issuer_id=data["issuer_id"],
            purpose=data["purpose"],
            receipt_id=data["receipt_id"],
            tenant_id=data["tenant_id"],
            plot_id=data["plot_id"],
            geometry_hash=data["geometry_hash"],
            geometry_version=data["geometry_version"],
            zone_id=data["zone_id"],
            delivery_start=data["delivery_start"],
            delivery_end=data["delivery_end"],
            delivered_volume_liters=data["delivered_volume_liters"],
            wetted_area_m2=data["wetted_area_m2"],
            delivery_efficiency_fraction=data["delivery_efficiency_fraction"],
            net_infiltrated_depth_mm=data["net_infiltrated_depth_mm"],
            conversion_calibration_id=data["conversion_calibration_id"],
            depth_uncertainty_sigma_mm=data["depth_uncertainty_sigma_mm"],
            source_evidence_cas_root=data["source_evidence_cas_root"],
            replay_idempotency_key=data["replay_idempotency_key"],
            revocation_revision_anchor=data["revocation_revision_anchor"],
            issued_at=data["issued_at"],
            expires_at=data["expires_at"],
            scientific_publication_authorized=data.get("scientific_publication_authorized", False),
            actuator_control_authorized=data.get("actuator_control_authorized", False),
        )


@dataclass(frozen=True)
class VerifiedDeliveredIrrigationReceipt:
    """Detached cryptographic receipt enclosing physical delivery grant and signature."""
    grant: VerifiedDeliveredIrrigationGrant
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
    def from_dict(cls, data: Mapping[str, Any]) -> VerifiedDeliveredIrrigationReceipt:
        if not isinstance(data, Mapping) or set(data) != {"grant", "signature", "key_id", "algorithm"}:
            raise ValueError("malformed VerifiedDeliveredIrrigationReceipt structure")
        grant = VerifiedDeliveredIrrigationGrant.from_dict(data["grant"])
        if grant.key_id != data["key_id"] or grant.algorithm != data["algorithm"]:
            raise ValueError("receipt envelope header mismatch")
        return cls(
            grant=grant,
            signature=data["signature"],
            key_id=data["key_id"],
            algorithm=data["algorithm"],
        )


@dataclass(frozen=True)
class AdmittedDeliveredIrrigation:
    """Authoritative output of successful physical delivery admission."""
    receipt_id: str
    net_infiltrated_depth_mm: float
    depth_uncertainty_sigma_mm: float
    tenant_id: str
    plot_id: str
    zone_id: str
    geometry_hash: str
    geometry_version: int
    delivery_start: str
    delivery_end: str
    conversion_calibration_id: str
    replay_idempotency_key: str
    scientific_publication_authorized: bool = False
    actuator_control_authorized: bool = False
    provenance: dict[str, Any] = field(default_factory=dict)


class VerifiedDeliveredIrrigationSigner:
    """Privileged signer for testing and L3 authority generation."""

    def __init__(self, key_id: str, issuer_id: str, algorithm: str, private_key: Any) -> None:
        self.key_id = key_id
        self.issuer_id = issuer_id
        self.algorithm = algorithm
        self._private_key = private_key

    def sign(self, grant_claims: Mapping[str, Any] | VerifiedDeliveredIrrigationGrant) -> VerifiedDeliveredIrrigationReceipt:
        grant = (
            grant_claims if isinstance(grant_claims, VerifiedDeliveredIrrigationGrant)
            else VerifiedDeliveredIrrigationGrant.from_dict(grant_claims)
        )
        if grant.key_id != self.key_id:
            raise ValueError(f"grant key_id {grant.key_id!r} does not match signer {self.key_id!r}")
        if grant.algorithm != self.algorithm:
            raise ValueError(f"grant algorithm {grant.algorithm!r} does not match signer {self.algorithm!r}")

        canonical_bytes = canonical_grant_bytes(grant.to_dict())

        if self.algorithm == "Ed25519":
            raw_sig = self._private_key.sign(canonical_bytes)
        elif self.algorithm == "ES256":
            raw_sig = self._private_key.sign(canonical_bytes, ec.ECDSA(hashes.SHA256(), deterministic_signing=True))
        else:
            raise ValueError(f"unsupported algorithm: {self.algorithm}")

        sig_b64 = base64.urlsafe_b64encode(raw_sig).decode("ascii")
        return VerifiedDeliveredIrrigationReceipt(
            grant=grant,
            signature=sig_b64,
            key_id=self.key_id,
            algorithm=self.algorithm,
        )


class VerifiedDeliveredIrrigationVerifier:
    """Asymmetric KMS Verifier for Layer 0 Physical Delivered Irrigation Admission."""

    def __init__(
        self,
        public_key_registry: KmsPublicKeyRegistry,
        revocation_authority: Optional[DurableRevocationAuthority] = None,
    ) -> None:
        self.public_key_registry = public_key_registry
        self.revocation_authority = revocation_authority
        self.seen_replay_keys: Set[str] = set()
        self.seen_receipt_ids: Set[str] = set()

    def verify_and_admit(
        self,
        receipt_data: Mapping[str, Any] | VerifiedDeliveredIrrigationReceipt,
        *,
        expected_day: str,
        expected_plot_id: str,
        expected_zone_id: str,
        expected_geometry_hash: str = "",
        expected_geometry_version: Optional[int] = None,
        expected_tenant_id: str = "",
        cutoff: Optional[datetime] = None,
    ) -> AdmittedDeliveredIrrigation:
        """Verify detached L3 delivery receipt and admit physical forcing."""
        receipt = (
            receipt_data if isinstance(receipt_data, VerifiedDeliveredIrrigationReceipt)
            else VerifiedDeliveredIrrigationReceipt.from_dict(receipt_data)
        )
        grant = receipt.grant

        # 1. Public key lookup
        key_entry = self.public_key_registry.get_entry(grant.key_id)
        if key_entry is None:
            raise ValueError(f"unknown KMS key_id: {grant.key_id!r}")
        if key_entry.issuer_id != grant.issuer_id:
            raise ValueError(f"issuer_id mismatch: {grant.issuer_id!r} != {key_entry.issuer_id!r}")
        if key_entry.algorithm != grant.algorithm:
            raise ValueError(f"algorithm mismatch: {grant.algorithm!r} != {key_entry.algorithm!r}")

        # 2. Cryptographic signature verification
        canonical_bytes = canonical_grant_bytes(grant.to_dict())
        try:
            raw_sig = base64.urlsafe_b64decode(receipt.signature.encode("ascii"))
        except Exception:
            raise ValueError("tampered_receipt_signature")

        try:
            if grant.algorithm == "Ed25519":
                key_entry.public_key.verify(raw_sig, canonical_bytes)
            elif grant.algorithm == "ES256":
                key_entry.public_key.verify(raw_sig, canonical_bytes, ec.ECDSA(hashes.SHA256()))
            else:
                raise ValueError(f"unsupported algorithm: {grant.algorithm}")
        except InvalidSignature:
            raise ValueError("tampered_receipt_signature") from None

        # 3. Temporal validity checks
        delivery_end_dt = _parse_iso_utc(grant.delivery_end)
        delivery_day = delivery_end_dt.date().isoformat()
        if expected_day and delivery_day != expected_day:
            raise ValueError("unqualified_event_time")

        if cutoff is not None:
            cutoff_utc = _ensure_utc(cutoff)
            if delivery_end_dt > cutoff_utc:
                raise ValueError("future_or_unavailable_event")

        # 4. Scope matching
        if expected_plot_id and grant.plot_id != expected_plot_id:
            raise ValueError("unbound_or_foreign_plot")
        if expected_zone_id and grant.zone_id != expected_zone_id:
            raise ValueError("event_outside_zone")
        if expected_geometry_hash and grant.geometry_hash != expected_geometry_hash:
            raise ValueError("unbound_or_foreign_geometry")
        if expected_geometry_version is not None and grant.geometry_version != expected_geometry_version:
            raise ValueError("unbound_or_foreign_geometry_version")
        if expected_tenant_id and grant.tenant_id != expected_tenant_id:
            raise ValueError("foreign_tenant_scope")

        # 5. Durable revocation ledger checks
        if self.revocation_authority is not None:
            rev_ok, rev_reason = self.revocation_authority.check_authority(
                grant.key_id,
                delivery_end_dt,
                revision_anchor=grant.revocation_revision_anchor,
                plot_id=grant.plot_id,
                zone_id=grant.zone_id,
                grant_id=grant.replay_idempotency_key,
            )
            if not rev_ok:
                raise ValueError(rev_reason)

        # Key validity at time of delivery
        if not key_entry.is_valid_at(delivery_end_dt):
            raise ValueError("key_expired_or_not_yet_valid")

        # Receipt validity
        expires_at_dt = _parse_iso_utc(grant.expires_at)
        if delivery_end_dt > expires_at_dt:
            raise ValueError("receipt_expired")

        # 6. Replay & Idempotency fencing
        if grant.replay_idempotency_key in self.seen_replay_keys:
            raise ValueError("duplicate_replay_key")
        if grant.receipt_id in self.seen_receipt_ids:
            raise ValueError("duplicate_receipt_id")

        self.seen_replay_keys.add(grant.replay_idempotency_key)
        self.seen_receipt_ids.add(grant.receipt_id)

        # 7. Admitted token
        return AdmittedDeliveredIrrigation(
            receipt_id=grant.receipt_id,
            net_infiltrated_depth_mm=grant.net_infiltrated_depth_mm,
            depth_uncertainty_sigma_mm=grant.depth_uncertainty_sigma_mm,
            tenant_id=grant.tenant_id,
            plot_id=grant.plot_id,
            zone_id=grant.zone_id,
            geometry_hash=grant.geometry_hash,
            geometry_version=grant.geometry_version,
            delivery_start=grant.delivery_start,
            delivery_end=grant.delivery_end,
            conversion_calibration_id=grant.conversion_calibration_id,
            replay_idempotency_key=grant.replay_idempotency_key,
            scientific_publication_authorized=False,
            actuator_control_authorized=False,
            provenance={
                "algorithm": grant.algorithm,
                "key_id": grant.key_id,
                "issuer_id": grant.issuer_id,
                "source_evidence_cas_root": grant.source_evidence_cas_root,
                "delivered_volume_liters": grant.delivered_volume_liters,
                "wetted_area_m2": grant.wetted_area_m2,
                "delivery_efficiency_fraction": grant.delivery_efficiency_fraction,
                "revocation_revision_anchor": grant.revocation_revision_anchor,
            },
        )
