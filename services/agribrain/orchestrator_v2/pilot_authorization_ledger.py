"""Phase 1E-A: durable, deny-by-default V2 candidate ledger and revocation.

This is NOT the positive authorization issuer. All records have immutable
status QUARANTINED. Neither this module nor a successful HMAC verification
permits farmer-facing action export. The public V2 serializer quarantine stays.

Requires an explicit, server-owned 32+ byte secret supplied by the caller.
Never reuses the predictable development proof-attestation fallback.
SQLite is appropriate for a single-node pilot; shared cloud deployment needs
one transactional shared store, never separate replica-local ledgers.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import sqlite3
from typing import Any, Mapping

from services.agribrain.scientific_contracts.exceptions import ContractViolation
from services.agribrain.scientific_contracts.prescription_authorization import (
    PrescriptionAuthorizationEnvelopeV2,
    _required_hash,
    _required_text,
    _utc_instant,
    canonical_hash,
    validate_published_pilot_envelope,
)
from services.agribrain.orchestrator_v2.pilot_publication_gate import (
    read_trusted_current_asmae_publication,
)
from services.agribrain.common.plot_namespace import PlotNamespace

SCHEMA_VERSION = "pilot_v2_quarantined_candidate_v1"
HMAC_DOMAIN = b"akaloris/pilot-v2/quarantined-candidate/v1\x00"

AUTHORIZED_SCHEMA_VERSION = "pilot_v2_authorized_prescription_v1"
AUTHORIZED_HMAC_DOMAIN = b"akaloris/pilot-v2/authorized-prescription/v1\x00"

ISSUER_VERIFICATION_HMAC_DOMAIN = b"akaloris/pilot-v2/issuer-verification/v1\x00"


def _parse_time(value: str, label: str) -> datetime:
    return datetime.fromisoformat(_utc_instant(value, label).replace("Z", "+00:00"))


def _required_key(secret: bytes) -> bytes:
    if not isinstance(secret, bytes) or len(secret) < 32 or not any(secret):
        raise ContractViolation("Pilot candidate ledger requires an explicit 32-byte-or-longer issuer key")
    return secret


def _sign(payload_hash: str, key: bytes, domain: bytes = HMAC_DOMAIN) -> str:
    return hmac.new(_required_key(key), domain + payload_hash.encode("ascii"), hashlib.sha256).hexdigest()


def _payload_hash(payload: Mapping[str, Any]) -> str:
    return canonical_hash(dict(payload))


class PilotCandidateLedger:
    """Persistent candidate storage; intentionally has NO method granting authority.

    A record is only trusted after reloading from SQLite, rechecking the HMAC,
    expiry, exact current publication and revocation row. This remains merely
    QUARANTINED even if all those checks pass.
    """

    def __init__(
        self,
        database_path: Path,
        *,
        key_id: str,
        signing_key: bytes,
        issuer_verification_key: Optional[bytes] = None,
    ):
        self.path = Path(database_path)
        self.key_id = _required_text(key_id, "pilot signing key_id")
        self._key = _required_key(signing_key)
        self._issuer_verification_key = (
            _required_key(issuer_verification_key)
            if issuer_verification_key is not None
            else self._key
        )
        if self.path == Path(":memory:"):
            raise ContractViolation("Pilot revocation ledger must be durable")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(str(self.path), timeout=10, isolation_level=None)
        try:
            conn.execute("PRAGMA busy_timeout=10000")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
        finally:
            conn.close()

    def _init(self):
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS candidates (
                  candidate_id TEXT PRIMARY KEY,
                  envelope_hash TEXT NOT NULL,
                  plot_id TEXT NOT NULL,
                  snapshot_id TEXT NOT NULL,
                  record_json TEXT NOT NULL
                )""")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS revocations (
                  candidate_id TEXT PRIMARY KEY REFERENCES candidates(candidate_id),
                  revoked_at TEXT NOT NULL,
                  reason TEXT NOT NULL
                )""")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scope_blocks (
                  tenant_id TEXT NOT NULL,
                  farm_id TEXT NOT NULL,
                  plot_id TEXT NOT NULL,
                  blocked_at TEXT NOT NULL,
                  reason TEXT NOT NULL,
                  PRIMARY KEY(tenant_id, farm_id, plot_id)
                )""")
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_candidates_envelope
                ON candidates(envelope_hash)
            """)

    def register_quarantined_candidate(
        self,
        *,
        namespace: PlotNamespace,
        geometry_hash: str,
        crop_cycle_id: str,
        envelope: PrescriptionAuthorizationEnvelopeV2,
        now: str,
    ) -> dict[str, Any]:
        """Prepare a signed *audit candidate*; not physical-action authority.

        Independently re-fetches current authenticated ASMAE publication and
        requires a verified proof attestation. Does not accept head JSON from
        caller and does not treat structural proof roots as certified admission.
        """
        if not isinstance(namespace, PlotNamespace) or not namespace.is_valid():
            raise ContractViolation("Pilot candidate requires trusted PlotNamespace")
        if not isinstance(envelope, PrescriptionAuthorizationEnvelopeV2):
            raise ContractViolation("Pilot candidate requires V2")
        if (envelope.tenant_id, envelope.farm_id, envelope.plot_id) != (
            namespace.tenant_id, namespace.farm_id, namespace.plot_id
        ):
            raise ContractViolation("Pilot candidate namespace mismatch")
        head = read_trusted_current_asmae_publication(
            namespace,
            expected_snapshot_id=envelope.snapshot_id,
            expected_geometry_hash=geometry_hash,
            expected_crop_cycle_id=crop_cycle_id,
            require_proof_attestation=True,
        )
        if head.get("proof_attestation_valid") is not True:
            raise ContractViolation("Pilot candidate has no authenticated proof attestation")
        attestation = head.get("proof_attestation")
        if not isinstance(attestation, Mapping):
            raise ContractViolation("Pilot candidate attestation missing")
        for attr, field in (
            ("admitted_evidence_root_hash", "admitted_evidence_root_hash"),
            ("bounded_uncertainty_receipt_hash", "bounded_uncertainty_receipt_hash"),
            ("scientific_posterior_hash", "scientific_posterior_hash"),
        ):
            if head.get(field) != attestation.get(attr):
                raise ContractViolation("Pilot candidate roots do not match authenticated attestation")
        checked_at = _utc_instant(now, "candidate recorded_at")
        validate_published_pilot_envelope(
            envelope, canonical_head=head,
            tenant_id=namespace.tenant_id, farm_id=namespace.farm_id,
            plot_id=namespace.plot_id, geometry_hash=geometry_hash,
            crop_cycle_id=crop_cycle_id, now=checked_at,
            verified_uncertainty_receipt_hash=head["bounded_uncertainty_receipt_hash"],
        )
        _required_hash(head.get("proof_attestation_hash"), "proof attestation hash")
        fields = {
            "schema_version": SCHEMA_VERSION,
            "candidate_id": secrets.token_hex(16),
            "state": "QUARANTINED",
            "tenant_id": namespace.tenant_id,
            "farm_id": namespace.farm_id,
            "plot_id": namespace.plot_id,
            "geometry_hash": envelope.geometry_hash,
            "crop_cycle_id": envelope.crop_cycle_id,
            "snapshot_id": envelope.snapshot_id,
            "publication_receipt_hash": envelope.canonical_publication_receipt_hash,
            "envelope_hash": envelope.content_hash,
            "attestation_hash": head["proof_attestation_hash"],
            "admitted_evidence_root_hash": head["admitted_evidence_root_hash"],
            "bounded_uncertainty_receipt_hash": head["bounded_uncertainty_receipt_hash"],
            "scientific_posterior_hash": head["scientific_posterior_hash"],
            "recorded_at": checked_at,
            "expires_at": envelope.expires_at,
            "key_id": self.key_id,
        }
        payload_hash = _payload_hash(fields)
        record = {**fields, "content_hash": payload_hash, "hmac": _sign(payload_hash, self._key)}
        serialized = json.dumps(record, sort_keys=True, separators=(",", ":"))
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            blocked = conn.execute(
                "SELECT 1 FROM scope_blocks WHERE tenant_id=? AND farm_id=? AND plot_id=?",
                (namespace.tenant_id, namespace.farm_id, namespace.plot_id),
            ).fetchone()
            if blocked:
                raise ContractViolation("Pilot plot scope is administratively blocked")
            conn.execute(
                "INSERT INTO candidates(candidate_id, envelope_hash, plot_id, snapshot_id, record_json) VALUES (?,?,?,?,?)",
                (record["candidate_id"], envelope.content_hash, namespace.plot_id, envelope.snapshot_id, serialized),
            )
            conn.commit()
        return record

    def _verify_issuer_token(
        self,
        token: str,
        *,
        envelope_hash: str,
        snapshot_id: str,
        publication_receipt_hash: str,
        admitted_evidence_root_hash: str,
        bounded_uncertainty_receipt_hash: str,
        policy_snapshot_hash: str,
        issued_at: str,
    ) -> bool:
        """Internal fail-closed verification of scientific issuer token capability."""
        if not isinstance(token, str) or not token.strip():
            return False
        payload = {
            "admitted_evidence_root_hash": _required_hash(admitted_evidence_root_hash, "admitted_evidence_root_hash"),
            "bounded_uncertainty_receipt_hash": _required_hash(bounded_uncertainty_receipt_hash, "bounded_uncertainty_receipt_hash"),
            "envelope_hash": _required_hash(envelope_hash, "envelope_hash"),
            "issued_at": _utc_instant(issued_at, "issued_at"),
            "policy_snapshot_hash": _required_hash(policy_snapshot_hash, "policy_snapshot_hash"),
            "publication_receipt_hash": _required_hash(publication_receipt_hash, "publication_receipt_hash"),
            "snapshot_id": _required_text(snapshot_id, "snapshot_id"),
        }
        token_payload_hash = _payload_hash(payload)
        expected = hmac.new(
            self._issuer_verification_key,
            ISSUER_VERIFICATION_HMAC_DOMAIN + token_payload_hash.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(token, expected)

    def register_authorized_prescription(
        self,
        *,
        namespace: PlotNamespace,
        geometry_hash: str,
        crop_cycle_id: str,
        envelope: PrescriptionAuthorizationEnvelopeV2,
        now: str,
        issuer_token: str,
    ) -> dict[str, Any]:
        """Record an authentic, server-verified positive V2 prescription authorization.

        Requires independently verified publication, valid proof attestation,
        matching proof roots, envelope validity, and an authentic issuer verification token.
        """
        if not isinstance(issuer_token, str) or not issuer_token.strip():
            raise ContractViolation("Direct authorized registration rejected: requires trusted issuer scientific verification token")
        if not isinstance(namespace, PlotNamespace) or not namespace.is_valid():
            raise ContractViolation("Pilot authorization requires trusted PlotNamespace")
        if not isinstance(envelope, PrescriptionAuthorizationEnvelopeV2):
            raise ContractViolation("Pilot authorization requires V2")
        if (envelope.tenant_id, envelope.farm_id, envelope.plot_id) != (
            namespace.tenant_id, namespace.farm_id, namespace.plot_id
        ):
            raise ContractViolation("Pilot candidate namespace mismatch")
        head = read_trusted_current_asmae_publication(
            namespace,
            expected_snapshot_id=envelope.snapshot_id,
            expected_geometry_hash=geometry_hash,
            expected_crop_cycle_id=crop_cycle_id,
            require_proof_attestation=True,
        )
        if head.get("proof_attestation_valid") is not True:
            raise ContractViolation("Pilot candidate has no authenticated proof attestation")
        attestation = head.get("proof_attestation")
        if not isinstance(attestation, Mapping):
            raise ContractViolation("Pilot candidate attestation missing")
        for attr, field in (
            ("admitted_evidence_root_hash", "admitted_evidence_root_hash"),
            ("bounded_uncertainty_receipt_hash", "bounded_uncertainty_receipt_hash"),
            ("scientific_posterior_hash", "scientific_posterior_hash"),
        ):
            if head.get(field) != attestation.get(attr):
                raise ContractViolation("Pilot candidate roots do not match authenticated attestation")
        checked_at = _utc_instant(now, "candidate recorded_at")
        validate_published_pilot_envelope(
            envelope, canonical_head=head,
            tenant_id=namespace.tenant_id, farm_id=namespace.farm_id,
            plot_id=namespace.plot_id, geometry_hash=geometry_hash,
            crop_cycle_id=crop_cycle_id, now=checked_at,
            verified_uncertainty_receipt_hash=head["bounded_uncertainty_receipt_hash"],
        )
        _required_hash(head.get("proof_attestation_hash"), "proof attestation hash")

        if not self._verify_issuer_token(
            issuer_token,
            envelope_hash=envelope.content_hash,
            snapshot_id=envelope.snapshot_id,
            publication_receipt_hash=envelope.canonical_publication_receipt_hash,
            admitted_evidence_root_hash=head["admitted_evidence_root_hash"],
            bounded_uncertainty_receipt_hash=head["bounded_uncertainty_receipt_hash"],
            policy_snapshot_hash=envelope.policy_snapshot_hash,
            issued_at=checked_at,
        ):
            raise ContractViolation("Direct authorized registration rejected: invalid or forged issuer verification token")

        for action in envelope.actions:
            if action.machine_execution_allowed:
                raise ContractViolation("Machine execution is never allowed")
            if not action.requires_confirmation:
                raise ContractViolation("Farmer confirmation is strictly required")

        fields = {
            "schema_version": AUTHORIZED_SCHEMA_VERSION,
            "candidate_id": secrets.token_hex(16),
            "state": "AUTHORIZED",
            "tenant_id": namespace.tenant_id,
            "farm_id": namespace.farm_id,
            "plot_id": namespace.plot_id,
            "geometry_hash": envelope.geometry_hash,
            "crop_cycle_id": envelope.crop_cycle_id,
            "snapshot_id": envelope.snapshot_id,
            "publication_receipt_hash": envelope.canonical_publication_receipt_hash,
            "envelope_hash": envelope.content_hash,
            "attestation_hash": head["proof_attestation_hash"],
            "admitted_evidence_root_hash": head["admitted_evidence_root_hash"],
            "bounded_uncertainty_receipt_hash": head["bounded_uncertainty_receipt_hash"],
            "scientific_posterior_hash": head["scientific_posterior_hash"],
            "policy_snapshot_hash": envelope.policy_snapshot_hash,
            "issuer_token": issuer_token,
            "recorded_at": checked_at,
            "expires_at": envelope.expires_at,
            "key_id": self.key_id,
        }
        payload_hash = _payload_hash(fields)
        record = {**fields, "content_hash": payload_hash, "hmac": _sign(payload_hash, self._key, AUTHORIZED_HMAC_DOMAIN)}
        serialized = json.dumps(record, sort_keys=True, separators=(",", ":"))
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            blocked = conn.execute(
                "SELECT 1 FROM scope_blocks WHERE tenant_id=? AND farm_id=? AND plot_id=?",
                (namespace.tenant_id, namespace.farm_id, namespace.plot_id),
            ).fetchone()
            if blocked:
                raise ContractViolation("Pilot plot scope is administratively blocked")
            conn.execute(
                "INSERT INTO candidates(candidate_id, envelope_hash, plot_id, snapshot_id, record_json) VALUES (?,?,?,?,?)",
                (record["candidate_id"], envelope.content_hash, namespace.plot_id, envelope.snapshot_id, serialized),
            )
            conn.commit()
        return record

    def _checked_record(self, candidate_id: str, *, now: str) -> dict[str, Any]:
        candidate_id = _required_text(candidate_id, "candidate_id")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT record_json, envelope_hash, plot_id, snapshot_id FROM candidates WHERE candidate_id=?",
                (candidate_id,),
            ).fetchone()
            revoked = conn.execute(
                "SELECT 1 FROM revocations WHERE candidate_id=?", (candidate_id,)
            ).fetchone()
        if not row:
            raise ContractViolation("Unknown or unavailable candidate record")
        if revoked:
            raise ContractViolation("Pilot candidate has been revoked")
        try:
            record = json.loads(row[0])
        except (ValueError, TypeError) as exc:
            raise ContractViolation("Corrupt candidate registry record") from exc
        if not isinstance(record, dict) or record.get("candidate_id") != candidate_id:
            raise ContractViolation("Candidate record identity mismatch")
        if record.get("schema_version") != SCHEMA_VERSION or record.get("state") != "QUARANTINED":
            raise ContractViolation("Pilot candidate is not in quarantined state")
        if (row[1], row[2], row[3]) != (
            record.get("envelope_hash"), record.get("plot_id"), record.get("snapshot_id")
        ):
            raise ContractViolation("Candidate registry index disagrees with immutable record")
        if record.get("key_id") != self.key_id:
            raise ContractViolation("Pilot candidate issuer key is unavailable or rotated")
        payload = {k: v for k, v in record.items() if k not in ("content_hash", "hmac")}
        actual_hash = _payload_hash(payload)
        if (not isinstance(record.get("content_hash"), str)
                or not hmac.compare_digest(record["content_hash"], actual_hash)
                or not isinstance(record.get("hmac"), str)
                or not hmac.compare_digest(record["hmac"], _sign(actual_hash, self._key))):
            raise ContractViolation("Candidate audit integrity or signature mismatch")
        checked_time = _parse_time(now, "candidate validation time")
        if not _parse_time(record["recorded_at"], "candidate recorded_at") <= checked_time < _parse_time(
            record["expires_at"], "candidate expiry"
        ):
            raise ContractViolation("Pilot candidate not yet valid or expired")
        return record

    def inspect_candidate(
        self, candidate_id: str, *, now: str, namespace: PlotNamespace,
    ) -> dict[str, Any]:
        """Negative/inspection path. No caller receives permitted actions."""
        if not isinstance(namespace, PlotNamespace) or not namespace.is_valid():
            raise ContractViolation("Inspection requires authenticated namespace")
        record = self._checked_record(candidate_id, now=now)
        for k in ("tenant_id", "farm_id", "plot_id"):
            if record[k] != getattr(namespace, k):
                raise ContractViolation("Pilot candidate belongs to another namespace")
        with self._connect() as conn:
            blocked = conn.execute(
                "SELECT 1 FROM scope_blocks WHERE tenant_id=? AND farm_id=? AND plot_id=?",
                (namespace.tenant_id, namespace.farm_id, namespace.plot_id),
            ).fetchone()
        if blocked:
            raise ContractViolation("Pilot plot scope is administratively blocked")
        head = read_trusted_current_asmae_publication(
            namespace,
            expected_snapshot_id=record["snapshot_id"],
            expected_geometry_hash=record["geometry_hash"],
            expected_crop_cycle_id=record["crop_cycle_id"],
            require_proof_attestation=True,
        )
        for name, field in (
            ("snapshot_id", "snapshot_id"),
            ("geometry_hash", "geometry_hash"),
            ("crop_cycle_id", "crop_cycle_id"),
            ("publication_receipt_hash", "publication_receipt_hash"),
            ("attestation_hash", "proof_attestation_hash"),
            ("admitted_evidence_root_hash", "admitted_evidence_root_hash"),
            ("bounded_uncertainty_receipt_hash", "bounded_uncertainty_receipt_hash"),
            ("scientific_posterior_hash", "scientific_posterior_hash"),
        ):
            if record[name] != head.get(field):
                raise ContractViolation(f"Pilot candidate {name} no longer matches current publication")
        return {
            "candidate_id": candidate_id, "state": "QUARANTINED",
            "snapshot_id": record["snapshot_id"], "envelope_hash": record["envelope_hash"],
            "valid_export_authorization": False,
            "authorized_actions": [],
        }

    def revoke(self, candidate_id: str, *, reason: str, at: str) -> None:
        """Durable, idempotent, no-unrevoke revocation; unknown ID fails closed."""
        reason = _required_text(reason, "revocation reason")
        at = _utc_instant(at, "revoked_at")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT 1 FROM candidates WHERE candidate_id=?", (candidate_id,)
            ).fetchone()
            if row is None:
                raise ContractViolation("Cannot revoke unknown candidate")
            conn.execute(
                "INSERT OR IGNORE INTO revocations(candidate_id,revoked_at,reason) VALUES (?,?,?)",
                (candidate_id, at, reason),
            )
            conn.commit()

    def block_scope(self, namespace: PlotNamespace, *, reason: str, at: str) -> None:
        """Emergency persistent plot block; this module provides no unblock."""
        if not isinstance(namespace, PlotNamespace) or not namespace.is_valid():
            raise ContractViolation("Scope block requires authenticated namespace")
        reason = _required_text(reason, "scope block reason")
        at = _utc_instant(at, "scope blocked_at")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT OR IGNORE INTO scope_blocks(tenant_id,farm_id,plot_id,blocked_at,reason) VALUES (?,?,?,?,?)",
                (namespace.tenant_id, namespace.farm_id, namespace.plot_id, at, reason),
            )
            conn.commit()

    def authorize_export(
        self,
        candidate_id: Optional[str] = None,
        *,
        envelope: Optional[PrescriptionAuthorizationEnvelopeV2] = None,
        envelope_hash: Optional[str] = None,
        namespace: Optional[PlotNamespace] = None,
        now: Optional[str] = None,
    ) -> dict[str, Any]:
        """Authorize farmer-facing action export for a previously verified positive record.

        Guarded export gate: checks ledger state == AUTHORIZED, HMAC signature,
        non-revoked, scope unblocked, unexpired, and matching current publication.
        Fails closed on quarantined candidates, unknown records, or tampering.
        """
        if candidate_id is None and envelope is None and envelope_hash is None:
            raise ContractViolation("V2 action export remains quarantined; no positive record specified")

        target_hash = envelope.content_hash if envelope is not None else envelope_hash
        with self._connect() as conn:
            if candidate_id:
                row = conn.execute(
                    "SELECT candidate_id, record_json, envelope_hash, plot_id, snapshot_id FROM candidates WHERE candidate_id=?",
                    (candidate_id,),
                ).fetchone()
            elif target_hash:
                row = conn.execute(
                    "SELECT candidate_id, record_json, envelope_hash, plot_id, snapshot_id FROM candidates WHERE envelope_hash=?",
                    (target_hash,),
                ).fetchone()
            else:
                raise ContractViolation("Cannot authorize export without candidate identity")

            if not row:
                raise ContractViolation("Unknown or unavailable candidate record")
            cid = row[0]
            revoked = conn.execute(
                "SELECT 1 FROM revocations WHERE candidate_id=?", (cid,)
            ).fetchone()

        if revoked:
            raise ContractViolation("Pilot candidate has been revoked")

        try:
            record = json.loads(row[1])
        except (ValueError, TypeError) as exc:
            raise ContractViolation("Corrupt candidate registry record") from exc

        if not isinstance(record, dict) or record.get("candidate_id") != cid:
            raise ContractViolation("Candidate record identity mismatch")

        if record.get("state") == "QUARANTINED":
            raise ContractViolation("Pilot candidate is quarantined; cannot authorize export")

        if record.get("schema_version") != AUTHORIZED_SCHEMA_VERSION or record.get("state") != "AUTHORIZED":
            raise ContractViolation("Pilot candidate is not in authorized state")

        if not isinstance(record.get("issuer_token"), str) or not record["issuer_token"].strip():
            raise ContractViolation("Pilot candidate lacks trusted issuer verification token")

        if envelope is not None and record.get("policy_snapshot_hash") and envelope.policy_snapshot_hash != record.get("policy_snapshot_hash"):
            raise ContractViolation("Envelope policy snapshot hash mismatch with authorization record")

        if (row[2], row[3], row[4]) != (
            record.get("envelope_hash"), record.get("plot_id"), record.get("snapshot_id")
        ):
            raise ContractViolation("Candidate registry index disagrees with immutable record")

        if target_hash and target_hash != record.get("envelope_hash"):
            raise ContractViolation("Envelope hash mismatch with authorization record")

        if record.get("key_id") != self.key_id:
            raise ContractViolation("Pilot candidate issuer key is unavailable or rotated")

        payload = {k: v for k, v in record.items() if k not in ("content_hash", "hmac")}
        actual_hash = _payload_hash(payload)
        expected_sig = _sign(actual_hash, self._key, AUTHORIZED_HMAC_DOMAIN)
        if (not isinstance(record.get("content_hash"), str)
                or not hmac.compare_digest(record["content_hash"], actual_hash)
                or not isinstance(record.get("hmac"), str)
                or not hmac.compare_digest(record["hmac"], expected_sig)):
            raise ContractViolation("Candidate audit integrity or signature mismatch")

        ns = namespace or PlotNamespace(record["tenant_id"], record["farm_id"], record["plot_id"])
        if not ns.is_valid():
            raise ContractViolation("Export requires valid PlotNamespace")
        for k in ("tenant_id", "farm_id", "plot_id"):
            if record[k] != getattr(ns, k):
                raise ContractViolation("Pilot candidate belongs to another namespace")

        with self._connect() as conn:
            blocked = conn.execute(
                "SELECT 1 FROM scope_blocks WHERE tenant_id=? AND farm_id=? AND plot_id=?",
                (ns.tenant_id, ns.farm_id, ns.plot_id),
            ).fetchone()
        if blocked:
            raise ContractViolation("Pilot plot scope is administratively blocked")

        effective_now = _utc_instant(now, "export authorization time") if now else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        checked_time = _parse_time(effective_now, "export check time")
        if not _parse_time(record["recorded_at"], "candidate recorded_at") <= checked_time < _parse_time(
            record["expires_at"], "candidate expiry"
        ):
            raise ContractViolation("Pilot candidate not yet valid or expired")

        head = read_trusted_current_asmae_publication(
            ns,
            expected_snapshot_id=record["snapshot_id"],
            expected_geometry_hash=record["geometry_hash"],
            expected_crop_cycle_id=record["crop_cycle_id"],
            require_proof_attestation=True,
        )
        for name, field in (
            ("snapshot_id", "snapshot_id"),
            ("geometry_hash", "geometry_hash"),
            ("crop_cycle_id", "crop_cycle_id"),
            ("publication_receipt_hash", "publication_receipt_hash"),
            ("attestation_hash", "proof_attestation_hash"),
            ("admitted_evidence_root_hash", "admitted_evidence_root_hash"),
            ("bounded_uncertainty_receipt_hash", "bounded_uncertainty_receipt_hash"),
            ("scientific_posterior_hash", "scientific_posterior_hash"),
        ):
            if record[name] != head.get(field):
                raise ContractViolation(f"Pilot candidate {name} no longer matches current publication")

        if not self._verify_issuer_token(
            record["issuer_token"],
            envelope_hash=record["envelope_hash"],
            snapshot_id=record["snapshot_id"],
            publication_receipt_hash=record["publication_receipt_hash"],
            admitted_evidence_root_hash=head["admitted_evidence_root_hash"],
            bounded_uncertainty_receipt_hash=head["bounded_uncertainty_receipt_hash"],
            policy_snapshot_hash=record.get("policy_snapshot_hash", ""),
            issued_at=record["recorded_at"],
        ):
            raise ContractViolation("Authorization record issuer verification token is invalid or tampered")

        return {
            "candidate_id": cid,
            "state": "AUTHORIZED",
            "snapshot_id": record["snapshot_id"],
            "envelope_hash": record["envelope_hash"],
            "valid_export_authorization": True,
            "authorized_at": effective_now,
            "record": record,
        }
