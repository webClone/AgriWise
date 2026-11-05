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
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
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

_ADMISSION_SECRET: bytes = os.urandom(32)


def _compute_admission_seal(
    receipt_id: str,
    net_infiltrated_depth_mm: float,
    depth_uncertainty_sigma_mm: float,
    replay_idempotency_key: str,
    tenant_id: str,
    plot_id: str,
    zone_id: str,
    geometry_hash: str,
    geometry_version: int,
    delivery_start: str,
    delivery_end: str,
    conversion_calibration_id: str,
    grant_digest: str,
    claim_nonce: str,
    issued_at: str = "",
    expires_at: str = "",
    key_id: str = "",
    revocation_revision_anchor: int = 0,
) -> str:
    # Canonical JSON avoids ':' concatenation ambiguity, and exact float.hex()
    # prevents same-seal values differing below eight decimal places.
    msg = json.dumps({
        "receipt_id": receipt_id,
        "depth_hex": float(net_infiltrated_depth_mm).hex(),
        "sigma_hex": float(depth_uncertainty_sigma_mm).hex(),
        "replay": replay_idempotency_key,
        "tenant": tenant_id, "plot": plot_id, "zone": zone_id,
        "geometry_hash": geometry_hash, "geometry_version": geometry_version,
        "delivery_start": delivery_start, "delivery_end": delivery_end,
        "calibration": conversion_calibration_id,
        "grant_digest": grant_digest, "claim_nonce": claim_nonce,
        "issued_at": issued_at, "expires_at": expires_at,
        "key_id": key_id, "revocation_revision_anchor": revocation_revision_anchor,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hmac.new(_ADMISSION_SECRET, msg.encode("utf-8"), hashlib.sha256).hexdigest()


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


def physical_evidence_fingerprint(
    grant: VerifiedDeliveredIrrigationGrant,
) -> str:
    """Same physical delivery cannot gain additional state authority through
    a second signer-issued receipt/replay ID. Two genuinely different meter
    evidence roots or nonidentical delivery intervals remain distinct.
    """
    fields = {
        "tenant_id": grant.tenant_id,
        "plot_id": grant.plot_id,
        "zone_id": grant.zone_id,
        "geometry_hash": grant.geometry_hash,
        "geometry_version": grant.geometry_version,
        # The immutable source record and interval identify ONE physical
        # delivery. Claiming a different volume, efficiency or calibration
        # for that same source/interval MUST NOT mint another application.
        "source_evidence_cas_root": grant.source_evidence_cas_root,
        "delivery_start": _parse_iso_utc(grant.delivery_start).isoformat(),
        "delivery_end": _parse_iso_utc(grant.delivery_end).isoformat(),
    }
    return hashlib.sha256(
        json.dumps(fields, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


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


@dataclass
class IrrigationIdempotencyReservation:
    """Staged two-phase reservation for a verified delivered irrigation receipt."""
    store: DurableIrrigationIdempotencyStore
    receipt_id: str
    replay_key: str
    tenant_id: str
    plot_id: str
    geometry_hash: str
    geometry_version: int
    day: str
    grant_digest: str = ""
    evidence_fingerprint: str = ""
    status: str = "STAGED"  # "STAGED", "COMMITTED", "ROLLED_BACK"

    def commit(self) -> None:
        if self.status == "COMMITTED":
            return
        if self.status == "ROLLED_BACK":
            raise RuntimeError("cannot commit a rolled back reservation")
        self.store.commit_many([self])
        self.status = "COMMITTED"

    def rollback(self) -> None:
        if self.status == "ROLLED_BACK":
            return
        if self.status == "COMMITTED":
            raise RuntimeError("cannot roll back an already committed reservation")
        self.store._rollback_reservation(self)
        self.status = "ROLLED_BACK"


class DurableIrrigationIdempotencyStore:
    """Durable receipt and replay fencing for physical delivered irrigation."""

    def __init__(self, storage_path: Optional[str | Path] = None) -> None:
        self.storage_path = Path(storage_path) if storage_path is not None else None
        self._committed_receipts: dict[str, dict[str, Any]] = {}
        self._committed_replay_keys: dict[str, dict[str, Any]] = {}
        self._pending_receipts: dict[str, IrrigationIdempotencyReservation] = {}
        self._pending_replay_keys: dict[str, IrrigationIdempotencyReservation] = {}
        self._pending_evidence_keys: dict[str, IrrigationIdempotencyReservation] = {}
        self._committed_evidence_keys: dict[str, dict[str, Any]] = {}
        self._load_from_storage()

    def _load_from_storage(self) -> None:
        if self.storage_path is None or not self.storage_path.is_file():
            return
        try:
            raw = self.storage_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            for rec in data.get("committed", []):
                rcpt_id = rec["receipt_id"]
                rep_key = rec["replay_key"]
                self._committed_receipts[rcpt_id] = rec
                self._committed_replay_keys[rep_key] = rec
                if rec.get("evidence_fingerprint"):
                    if rec["evidence_fingerprint"] in self._committed_evidence_keys:
                        raise RuntimeError("duplicate_physical_evidence_in_history")
                    self._committed_evidence_keys[rec["evidence_fingerprint"]] = rec
        except Exception as exc:
            raise RuntimeError(f"failed to load idempotency store from {self.storage_path}: {exc}") from exc

    def _flush_to_storage(self, candidate: Optional[dict[str, dict[str, Any]]] = None) -> None:
        if self.storage_path is None:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "1.0",
            "committed": list(
                (candidate if candidate is not None else self._committed_receipts).values()
            ),
        }
        raw = json.dumps(data, indent=2, sort_keys=True)
        tmp_path = self.storage_path.with_suffix(f".tmp.{os.getpid()}.{os.urandom(4).hex()}")
        tmp_path.write_text(raw, encoding="utf-8")
        tmp_path.replace(self.storage_path)

    def is_consumed(
        self,
        receipt_id: str,
        replay_key: str,
        *,
        day: str,
        plot_id: str,
        geometry_hash: str,
        geometry_version: int,
        tenant_id: str,
        allow_historical_recompute: bool = False,
        receipt_digest: str = "",
    ) -> tuple[bool, str]:
        if replay_key in self._pending_replay_keys:
            return True, "duplicate_replay_key"
        if receipt_id in self._pending_receipts:
            return True, "duplicate_receipt_id"

        rec = self._committed_replay_keys.get(replay_key) or self._committed_receipts.get(receipt_id)
        if rec is not None:
            if allow_historical_recompute:
                # Historical replay must identify the EXACT original receipt,
                # signature-verified grant content, scope and day. Reusing one
                # replay key for a different receipt is always forbidden.
                matches_scope = (
                    rec.get("receipt_id") == receipt_id
                    and rec.get("replay_key") == replay_key
                    and bool(receipt_digest)
                    and rec.get("grant_digest") == receipt_digest
                    and rec.get("plot_id") == plot_id
                    and rec.get("geometry_hash") == geometry_hash
                    and rec.get("geometry_version") == geometry_version
                    and rec.get("tenant_id") == tenant_id
                    and rec.get("day") == day
                )
                if matches_scope:
                    return False, ""
                return True, "duplicate_replay_key_cross_scope_conflict"
            if replay_key in self._committed_replay_keys:
                return True, "duplicate_replay_key"
            return True, "duplicate_receipt_id"

        return False, ""

    def stage_reservation(
        self,
        grant: VerifiedDeliveredIrrigationGrant,
        day: str,
        allow_historical_recompute: bool = False,
    ) -> IrrigationIdempotencyReservation:
        digest = hashlib.sha256(canonical_grant_bytes(grant.to_dict())).hexdigest()
        consumed, reason = self.is_consumed(
            grant.receipt_id,
            grant.replay_idempotency_key,
            day=day,
            plot_id=grant.plot_id,
            geometry_hash=grant.geometry_hash,
            geometry_version=grant.geometry_version,
            tenant_id=grant.tenant_id,
            allow_historical_recompute=allow_historical_recompute,
            receipt_digest=digest,
        )
        if consumed:
            raise ValueError(reason)

        evidence_key = physical_evidence_fingerprint(grant)
        pending = self._pending_evidence_keys.get(evidence_key)
        committed = self._committed_evidence_keys.get(evidence_key)
        if pending is not None or (
            committed is not None
            and not (
                allow_historical_recompute
                and committed.get("receipt_id") == grant.receipt_id
                and committed.get("replay_key") == grant.replay_idempotency_key
                and committed.get("grant_digest") == digest
            )
        ):
            raise ValueError("duplicate_physical_delivery_evidence")

        reservation = IrrigationIdempotencyReservation(
            store=self,
            receipt_id=grant.receipt_id,
            replay_key=grant.replay_idempotency_key,
            tenant_id=grant.tenant_id,
            plot_id=grant.plot_id,
            geometry_hash=grant.geometry_hash,
            geometry_version=grant.geometry_version,
            day=day,
            grant_digest=digest,
            evidence_fingerprint=evidence_key,
            status="STAGED",
        )
        self._pending_evidence_keys[evidence_key] = reservation
        self._pending_receipts[grant.receipt_id] = reservation
        self._pending_replay_keys[grant.replay_idempotency_key] = reservation
        return reservation

    def commit_many(
        self, reservations: Sequence[IrrigationIdempotencyReservation],
        *, state_snapshot: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Single durable write before any reservation becomes consumed.

        Research-only file backend: atomic replace on one process, NOT a
        distributed locking/CAS store. Production must use the shared Mongo
        transactional backend. On fsync/replace failure, neither the
        committed dictionaries nor reservation statuses are changed.
        """
        unique = list(reservations)
        if not unique:
            return
        if len({r.receipt_id for r in unique}) != len(unique):
            raise ValueError("duplicate_receipt_in_transaction")
        if len({r.replay_key for r in unique}) != len(unique):
            raise ValueError("duplicate_replay_key_in_transaction")
        if len({r.evidence_fingerprint for r in unique}) != len(unique):
            raise ValueError("duplicate_physical_delivery_evidence")
        if any(not self.reservation_is_live(r) or r.status != "STAGED" for r in unique):
            raise RuntimeError("idempotency_reservation_not_staged")
        candidate = dict(self._committed_receipts)
        replay = dict(self._committed_replay_keys)
        evidence = dict(self._committed_evidence_keys)
        for res in unique:
            if res.receipt_id in candidate or res.replay_key in replay:
                # Explicit historical research recomputation retains the same
                # previously committed grant but never overwrites its record.
                old = candidate.get(res.receipt_id)
                if old is None or old != replay.get(res.replay_key) or (
                    old.get("grant_digest") != res.grant_digest
                    or old.get("tenant_id") != res.tenant_id
                    or old.get("plot_id") != res.plot_id
                    or old.get("geometry_hash") != res.geometry_hash
                    or old.get("geometry_version") != res.geometry_version
                    or old.get("day") != res.day
                ):
                    raise ValueError("historical_recompute_identity_conflict")
                continue
            if res.evidence_fingerprint in evidence:
                raise ValueError("duplicate_physical_delivery_evidence")
            rec = {
                "receipt_id": res.receipt_id,
                "replay_key": res.replay_key,
                "tenant_id": res.tenant_id,
                "plot_id": res.plot_id,
                "geometry_hash": res.geometry_hash,
                "geometry_version": res.geometry_version,
                "day": res.day,
                "grant_digest": res.grant_digest,
                "evidence_fingerprint": res.evidence_fingerprint,
                "committed_at": datetime.now(timezone.utc).isoformat(),
            }
            candidate[res.receipt_id] = rec
            replay[res.replay_key] = rec
            evidence[res.evidence_fingerprint] = rec
        self._flush_to_storage(candidate)
        self._committed_receipts = candidate
        self._committed_replay_keys = replay
        self._committed_evidence_keys = evidence
        for res in unique:
            self._pending_receipts.pop(res.receipt_id, None)
            self._pending_replay_keys.pop(res.replay_key, None)
            self._pending_evidence_keys.pop(res.evidence_fingerprint, None)
            res.status = "COMMITTED"

    def _commit_reservation(self, res: IrrigationIdempotencyReservation) -> None:
        self.commit_many([res])

    def reservation_is_live(self, res: IrrigationIdempotencyReservation) -> bool:
        return (
            self._pending_receipts.get(res.receipt_id) is res
            and self._pending_replay_keys.get(res.replay_key) is res
            and self._pending_evidence_keys.get(res.evidence_fingerprint) is res
        )

    def _rollback_reservation(self, res: IrrigationIdempotencyReservation) -> None:
        if self._pending_receipts.get(res.receipt_id) is res:
            self._pending_receipts.pop(res.receipt_id, None)
        if self._pending_replay_keys.get(res.replay_key) is res:
            self._pending_replay_keys.pop(res.replay_key, None)
        if self._pending_evidence_keys.get(res.evidence_fingerprint) is res:
            self._pending_evidence_keys.pop(res.evidence_fingerprint, None)


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
    issued_at: str = ""
    expires_at: str = ""
    key_id: str = ""
    revocation_revision_anchor: int = 0
    scientific_publication_authorized: bool = False
    actuator_control_authorized: bool = False
    provenance: dict[str, Any] = field(default_factory=dict)
    _admission_seal: str = field(default="", repr=False)
    _reservation: Optional[IrrigationIdempotencyReservation] = field(default=None, repr=False)

    def is_authoritative(self) -> bool:
        if self.scientific_publication_authorized is not False:
            return False
        if self.actuator_control_authorized is not False:
            return False
        if not self._admission_seal:
            return False
        expected_seal = _compute_admission_seal(
            receipt_id=self.receipt_id,
            net_infiltrated_depth_mm=self.net_infiltrated_depth_mm,
            depth_uncertainty_sigma_mm=self.depth_uncertainty_sigma_mm,
            replay_idempotency_key=self.replay_idempotency_key,
            tenant_id=self.tenant_id,
            plot_id=self.plot_id,
            zone_id=self.zone_id,
            geometry_hash=self.geometry_hash,
            geometry_version=self.geometry_version,
            delivery_start=self.delivery_start,
            delivery_end=self.delivery_end,
            conversion_calibration_id=self.conversion_calibration_id,
            grant_digest=self._reservation.grant_digest if self._reservation else "",
            claim_nonce=getattr(self._reservation, "claim_nonce", ""),
            issued_at=self.issued_at, expires_at=self.expires_at,
            key_id=self.key_id,
            revocation_revision_anchor=self.revocation_revision_anchor,
        )
        return hmac.compare_digest(self._admission_seal, expected_seal)

    def applies_to_filter(
        self, *, tenant_id: str, plot_id: str, zone_id: str,
        geometry_hash: str, geometry_version: int | None,
        day: str, cutoff: datetime | None = None,
    ) -> bool:
        """Re-bind an admitted token to the exact consuming filter.

        The verifier's HMAC seal does not by itself authorize a different
        plot, management zone, day, or second application. The reservation
        must still be in the live staged set (not committed/rolled back).
        """
        if not self.is_authoritative():
            return False
        reservation = self._reservation
        if (
            not isinstance(reservation, IrrigationIdempotencyReservation)
            or reservation.status != "STAGED"
            or not reservation.store.reservation_is_live(reservation)
            or not all((tenant_id, plot_id, zone_id, geometry_hash, day))
            or type(geometry_version) is not int
            or self.tenant_id != tenant_id
            or self.plot_id != plot_id
            or self.zone_id != zone_id
            or self.geometry_hash != geometry_hash
            or self.geometry_version != geometry_version
            or reservation.receipt_id != self.receipt_id
            or reservation.replay_key != self.replay_idempotency_key
            or reservation.day != day
            or reservation.tenant_id != tenant_id
            or reservation.plot_id != plot_id
            or reservation.geometry_hash != geometry_hash
            or reservation.geometry_version != geometry_version
        ):
            return False
        try:
            start = _parse_iso_utc(self.delivery_start)
            end = _parse_iso_utc(self.delivery_end)
            if (
                start > end or end.date().isoformat() != day
                or (cutoff is not None and end > _ensure_utc(cutoff))
            ):
                return False
        except (ValueError, TypeError):
            return False
        return True

    def commit_idempotency(self) -> None:
        if self._reservation is not None:
            self._reservation.commit()

    def rollback_idempotency(self) -> None:
        if self._reservation is not None:
            self._reservation.rollback()



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
        revocation_authority: DurableRevocationAuthority,
        idempotency_store: Optional[DurableIrrigationIdempotencyStore] = None,
    ) -> None:
        if revocation_authority is None:
            raise ValueError("revocation_authority is required")
        if not isinstance(revocation_authority, DurableRevocationAuthority):
            raise TypeError("revocation_authority must be an instance of DurableRevocationAuthority")
        self.public_key_registry = public_key_registry
        self.revocation_authority = revocation_authority
        self.idempotency_store = idempotency_store or DurableIrrigationIdempotencyStore()

    def revalidate_for_commit(
        self, token: AdmittedDeliveredIrrigation, *,
        cutoff: Optional[datetime] = None,
    ) -> None:
        """Re-check live signer, expiry and revocation after prediction.

        This is the final application-level gate before a Mongo transaction.
        Future deployments should place revocation revision fencing into the
        same server-side transactional authority to eliminate the last
        check/commit race against an external file-backed revocation source.
        """
        if not isinstance(token, AdmittedDeliveredIrrigation) or not token.is_authoritative():
            raise ValueError("untrusted_l3_admission_token")
        current = datetime.now(timezone.utc)
        issued = _parse_iso_utc(token.issued_at)
        expires = _parse_iso_utc(token.expires_at)
        assessment = _ensure_utc(cutoff) if cutoff is not None else current
        if issued > assessment:
            raise ValueError("receipt_issued_after_assessment_cutoff")
        if assessment >= expires:
            raise ValueError("receipt_expired_at_assessment")
        if current >= expires and not getattr(token._reservation, "historical_readonly", False):
            raise ValueError("receipt_expired_at_commit")
        key_entry = self.public_key_registry.get_entry(token.key_id)
        if key_entry is None or not key_entry.is_valid_at(current):
            raise ValueError("l3_key_not_currently_valid")
        ok, reason = self.revocation_authority.check_authority(
            token.key_id, current,
            revision_anchor=token.revocation_revision_anchor,
            plot_id=token.plot_id, zone_id=token.zone_id,
            grant_id=token.replay_idempotency_key,
        )
        if not ok:
            raise ValueError(reason)

    @property
    def seen_replay_keys(self) -> Set[str]:
        return set(self.idempotency_store._committed_replay_keys) | set(self.idempotency_store._pending_replay_keys)

    @property
    def seen_receipt_ids(self) -> Set[str]:
        return set(self.idempotency_store._committed_receipts) | set(self.idempotency_store._pending_receipts)

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
        allow_historical_recompute: bool = False,
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

        # 3. Receipt authorization-time and event-time are distinct.
        # A receipt created after an assessment cutoff cannot retroactively
        # alter that assessment; historical delivery time alone is insufficient.
        authorization_time = datetime.now(timezone.utc)
        assessment_time = _ensure_utc(cutoff) if cutoff is not None else authorization_time
        issued_at_dt = _parse_iso_utc(grant.issued_at)
        expires_at_dt = _parse_iso_utc(grant.expires_at)
        if issued_at_dt > assessment_time:
            raise ValueError("receipt_issued_after_assessment_cutoff")
        if assessment_time >= expires_at_dt:
            raise ValueError("receipt_expired_at_assessment")
        if (
            authorization_time >= expires_at_dt
            and not allow_historical_recompute
        ):
            raise ValueError("receipt_expired_at_authorization")
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
                authorization_time,
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

        # Receipt must remain valid at the actual delivery time as well.
        if delivery_end_dt > expires_at_dt:
            raise ValueError("receipt_expired")

        # 6. Replay & Idempotency fencing (two-phase reservation)
        reservation = self.idempotency_store.stage_reservation(
            grant,
            delivery_day,
            allow_historical_recompute=allow_historical_recompute,
        )

        # 7. Unforgeable process-secret admission seal
        admission_seal = _compute_admission_seal(
            receipt_id=grant.receipt_id,
            net_infiltrated_depth_mm=grant.net_infiltrated_depth_mm,
            depth_uncertainty_sigma_mm=grant.depth_uncertainty_sigma_mm,
            replay_idempotency_key=grant.replay_idempotency_key,
            tenant_id=grant.tenant_id,
            plot_id=grant.plot_id,
            zone_id=grant.zone_id,
            geometry_hash=grant.geometry_hash,
            geometry_version=grant.geometry_version,
            delivery_start=grant.delivery_start,
            delivery_end=grant.delivery_end,
            conversion_calibration_id=grant.conversion_calibration_id,
            grant_digest=reservation.grant_digest,
            claim_nonce=getattr(reservation, "claim_nonce", ""),
            issued_at=grant.issued_at, expires_at=grant.expires_at,
            key_id=grant.key_id,
            revocation_revision_anchor=grant.revocation_revision_anchor,
        )

        # 8. Admitted token
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
            issued_at=grant.issued_at, expires_at=grant.expires_at,
            key_id=grant.key_id,
            revocation_revision_anchor=grant.revocation_revision_anchor,
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
            _admission_seal=admission_seal,
            _reservation=reservation,
        )
