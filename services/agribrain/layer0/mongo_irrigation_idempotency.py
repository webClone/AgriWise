"""B07-SEC-05/06: cross-process irrigation receipt and state commit ledger.

For deployment with a common MongoDB replica set or sharded cluster capable
of multi-document transactions. A single live transaction commits receipt
consumption and the Kalman scientific-state snapshot. Memory is published
only after that transaction. An ambiguous network result fails closed; the
durable snapshot is available for explicit recovery, not automatic replay.

One-node JSON stores are intentionally never accepted in signed production.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from typing import Any, Callable, Mapping, Optional, Sequence

from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError, PyMongoError

from services.agribrain.layer0.verified_irrigation_contract import (
    IrrigationIdempotencyReservation,
    VerifiedDeliveredIrrigationGrant,
)
from services.agribrain.layer0.v3_kms_signed_issuer import canonical_grant_bytes


def _scope_state_id(rec: Mapping[str, Any]) -> str:
    fields = (
        "tenant_id", "plot_id", "zone_id", "geometry_hash",
        "geometry_version", "day",
    )
    return hashlib.sha256(
        "\0".join(str(rec[k]) for k in fields).encode("utf-8")
    ).hexdigest()


class MongoIrrigationIdempotencyStore:
    """A shared transaction-backed, fail-closed receipt+state ledger.

    Pending claims are written with unique indexes, not Python-only sets.
    Crash-left STAGED claims must be reconciled by a privileged operator:
    never implicitly expire/reclaim them, which would allow double apply.

    Historical recomputation may be enabled only with a SERVER-SIDE
    authorizer callable. A client boolean alone cannot mint permission.
    Recomputed states do not overwrite the live committed state journal.
    """

    production_shared = True

    def __init__(
        self, database: Any, *,
        historical_recompute_authorizer: Optional[
            Callable[[VerifiedDeliveredIrrigationGrant, str], bool]
        ] = None,
    ):
        if database is None or not callable(getattr(database, "command", None)):
            raise TypeError("connected_mongodb_database_required")
        if not callable(getattr(getattr(database, "client", None), "start_session", None)):
            raise TypeError("mongodb_transactional_session_required")
        database.command("ping")
        self._db = database
        self._client = database.client
        self._receipts = database["Layer0IrrigationReceiptConsumption"]
        self._states = database["Layer0IrrigationCommittedState"]
        self._receipts.create_index([("replay_key", ASCENDING)], unique=True)
        self._states.create_index(
            [("tenant_id", ASCENDING), ("plot_id", ASCENDING),
             ("zone_id", ASCENDING), ("day", ASCENDING)]
        )
        self._historical_authorizer = historical_recompute_authorizer
        self._pending_receipts: dict[str, IrrigationIdempotencyReservation] = {}
        self._pending_replay_keys: dict[str, IrrigationIdempotencyReservation] = {}

    def _matching_committed(
        self, record: Mapping[str, Any], grant: VerifiedDeliveredIrrigationGrant,
        day: str, digest: str,
    ) -> bool:
        return bool(
            record
            and record.get("status") == "COMMITTED"
            and record.get("_id") == grant.receipt_id
            and record.get("replay_key") == grant.replay_idempotency_key
            and record.get("grant_digest") == digest
            and record.get("tenant_id") == grant.tenant_id
            and record.get("plot_id") == grant.plot_id
            and record.get("geometry_hash") == grant.geometry_hash
            and record.get("geometry_version") == grant.geometry_version
            and record.get("zone_id") == grant.zone_id
            and record.get("day") == day
        )

    def stage_reservation(
        self, grant: VerifiedDeliveredIrrigationGrant, day: str,
        allow_historical_recompute: bool = False,
    ) -> IrrigationIdempotencyReservation:
        digest = hashlib.sha256(canonical_grant_bytes(grant.to_dict())).hexdigest()
        nonce = os.urandom(24).hex()
        doc = {
            "_id": grant.receipt_id,
            "replay_key": grant.replay_idempotency_key,
            "grant_digest": digest,
            "tenant_id": grant.tenant_id,
            "plot_id": grant.plot_id,
            "geometry_hash": grant.geometry_hash,
            "geometry_version": grant.geometry_version,
            "zone_id": grant.zone_id,
            "day": day,
            "status": "STAGED",
            "claim_nonce": nonce,
            "staged_at": datetime.now(timezone.utc),
        }
        historical = False
        try:
            self._receipts.insert_one(doc)  # atomic receipt/replay uniqueness
        except DuplicateKeyError:
            existing = self._receipts.find_one({"_id": grant.receipt_id})
            if (
                not allow_historical_recompute
                or not self._matching_committed(existing, grant, day, digest)
                or self._historical_authorizer is None
                or self._historical_authorizer(grant, day) is not True
            ):
                raise ValueError("duplicate_receipt_or_replay_key") from None
            # Read-only scientific recomputation of the exact original grant;
            # NEVER mutate the live committed receipt or overwrite state.
            historical = True
        except PyMongoError as exc:
            raise RuntimeError("idempotency_store_unavailable") from exc

        res = IrrigationIdempotencyReservation(
            store=self,
            receipt_id=grant.receipt_id, replay_key=grant.replay_idempotency_key,
            tenant_id=grant.tenant_id, plot_id=grant.plot_id,
            geometry_hash=grant.geometry_hash,
            geometry_version=grant.geometry_version,
            day=day, grant_digest=digest,
        )
        res.claim_nonce = nonce
        res.zone_id = grant.zone_id
        res.historical_readonly = historical
        self._pending_receipts[res.receipt_id] = res
        self._pending_replay_keys[res.replay_key] = res
        return res

    def reservation_is_live(self, res: IrrigationIdempotencyReservation) -> bool:
        if res.status != "STAGED":
            return False
        if self._pending_receipts.get(res.receipt_id) is not res:
            return False
        if self._pending_replay_keys.get(res.replay_key) is not res:
            return False
        try:
            if getattr(res, "historical_readonly", False):
                row = self._receipts.find_one({"_id": res.receipt_id})
                return bool(
                    row and row.get("status") == "COMMITTED"
                    and row.get("grant_digest") == res.grant_digest
                    and row.get("replay_key") == res.replay_key
                    and row.get("tenant_id") == res.tenant_id
                    and row.get("plot_id") == res.plot_id
                    and row.get("geometry_hash") == res.geometry_hash
                    and row.get("geometry_version") == res.geometry_version
                    and row.get("day") == res.day
                )
            row = self._receipts.find_one({
                "_id": res.receipt_id,
                "replay_key": res.replay_key,
                "claim_nonce": res.claim_nonce,
                "status": "STAGED",
            })
            return row is not None
        except PyMongoError:
            return False

    def commit_many(
        self, reservations: Sequence[IrrigationIdempotencyReservation],
        *, state_snapshot: Optional[Mapping[str, Any]] = None,
    ) -> None:
        tokens = list(reservations)
        if not tokens:
            return
        if state_snapshot is None:
            raise RuntimeError("durable_state_snapshot_required_for_receipt_commit")
        if len({r.receipt_id for r in tokens}) != len(tokens):
            raise ValueError("duplicate_receipt_in_transaction")
        if len({r.replay_key for r in tokens}) != len(tokens):
            raise ValueError("duplicate_replay_key_in_transaction")
        if any(not self.reservation_is_live(r) for r in tokens):
            raise RuntimeError("idempotency_reservation_not_staged")
        snap = dict(state_snapshot)
        expected = ("tenant_id", "plot_id", "zone_id", "geometry_hash",
                    "geometry_version", "day", "state", "covariance")
        if any(key not in snap for key in expected):
            raise ValueError("incomplete_scientific_state_snapshot")
        if any(
            r.tenant_id != snap["tenant_id"]
            or r.plot_id != snap["plot_id"]
            or r.geometry_hash != snap["geometry_hash"]
            or r.geometry_version != snap["geometry_version"]
            or r.day != snap["day"]
            or getattr(r, "zone_id", "") != snap["zone_id"]
            for r in tokens
        ):
            raise ValueError("receipt_snapshot_scope_mismatch")
        historical = all(getattr(r, "historical_readonly", False) for r in tokens)
        if any(getattr(r, "historical_readonly", False) != historical for r in tokens):
            raise ValueError("mixed_historical_and_live_commit")
        if historical:
            # Permission was verified at admission; this is a read-only
            # recomputation and MUST NOT publish/alter live state journal.
            for r in tokens:
                if not self.reservation_is_live(r):
                    raise RuntimeError("historical_recompute_revoked")
            for r in tokens:
                self._pending_receipts.pop(r.receipt_id, None)
                self._pending_replay_keys.pop(r.replay_key, None)
                r.status = "COMMITTED"
            return

        snapshot_id = _scope_state_id(snap)
        record = {
            "_id": snapshot_id,
            **snap,
            "receipt_ids": [r.receipt_id for r in tokens],
            "replay_keys": [r.replay_key for r in tokens],
            "committed_at": datetime.now(timezone.utc),
        }
        # Multi-document transaction = state snapshot and receipt uses either
        # BOTH become committed or NEITHER does.
        try:
            with self._client.start_session() as session:
                with session.start_transaction():
                    for r in tokens:
                        outcome = self._receipts.update_one(
                            {"_id": r.receipt_id, "replay_key": r.replay_key,
                             "claim_nonce": r.claim_nonce, "status": "STAGED"},
                            {"$set": {"status": "COMMITTED",
                                      "state_snapshot_id": snapshot_id,
                                      "committed_at": datetime.now(timezone.utc)}},
                            session=session,
                        )
                        if outcome.matched_count != 1:
                            raise RuntimeError("receipt_reservation_changed")
                    # No replacing previously published state on replay.
                    self._states.insert_one(record, session=session)
        except Exception as exc:
            # Includes unknown transaction-commit outcome: fail closed. A
            # durable record may exist; privileged recovery must inspect it.
            raise RuntimeError("irrigation_state_commit_unconfirmed") from exc
        for r in tokens:
            self._pending_receipts.pop(r.receipt_id, None)
            self._pending_replay_keys.pop(r.replay_key, None)
            r.status = "COMMITTED"

    def _commit_reservation(self, res: IrrigationIdempotencyReservation) -> None:
        raise RuntimeError("shared_store_requires_atomic_state_snapshot")

    def _rollback_reservation(self, res: IrrigationIdempotencyReservation) -> None:
        self._pending_receipts.pop(res.receipt_id, None)
        self._pending_replay_keys.pop(res.replay_key, None)
        if getattr(res, "historical_readonly", False):
            return
        try:
            self._receipts.delete_one({
                "_id": res.receipt_id, "replay_key": res.replay_key,
                "claim_nonce": res.claim_nonce, "status": "STAGED",
            })
        except PyMongoError as exc:
            # Persistent pending reservation remains safely unavailable until
            # privileged reconciliation. Never expire it on an untrusted clock.
            raise RuntimeError("idempotency_rollback_unconfirmed") from exc

    def recover_snapshot(
        self, *, tenant_id: str, plot_id: str, zone_id: str,
        geometry_hash: str, geometry_version: int, day: str,
    ) -> dict[str, Any] | None:
        """Explicit crash recovery; never replay a committed receipt."""
        row = self._states.find_one({
            "_id": _scope_state_id({
                "tenant_id": tenant_id, "plot_id": plot_id,
                "zone_id": zone_id, "geometry_hash": geometry_hash,
                "geometry_version": geometry_version, "day": day,
            })
        })
        if row is None:
            return None
        exact = (
            row["tenant_id"] == tenant_id
            and row["plot_id"] == plot_id
            and row["zone_id"] == zone_id
            and row["geometry_hash"] == geometry_hash
            and row["geometry_version"] == geometry_version
            and row["day"] == day
        )
        if not exact:
            raise RuntimeError("recovered_state_scope_mismatch")
        return dict(row)
