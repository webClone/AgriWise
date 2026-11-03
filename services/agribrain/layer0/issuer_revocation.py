"""L0-004B2: live revocation snapshot verifier, not an issuance service.

A revocation provider MUST be provisioned by the trusted server, backed by
an independently controlled registry/DB. Never read a snapshot from the
observation packet. Deny unavailable, stale, conflicting, rolled-back or
unknown status. Local monotonicity only fences one worker; durable
cross-worker ordering remains a deployment acceptance requirement.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Mapping
import hashlib
import json


@dataclass(frozen=True)
class IssuerRevocationSnapshot:
    revision: int
    issued_at: datetime
    expires_at: datetime
    # Key IDs absent from the snapshot are unauthorized, not active.
    key_statuses: Mapping[str, str]


class TrustedRevocationGate:
    def __init__(
        self,
        trusted_snapshot_provider: Callable[[], IssuerRevocationSnapshot],
        *,
        max_snapshot_age_seconds: int = 300,
    ) -> None:
        if not callable(trusted_snapshot_provider):
            raise ValueError("revocation snapshot provider must be trusted callable")
        if (
            isinstance(max_snapshot_age_seconds, bool)
            or not isinstance(max_snapshot_age_seconds, int)
            or not 1 <= max_snapshot_age_seconds <= 3600
        ):
            raise ValueError("invalid revocation freshness bound")
        self._provider = trusted_snapshot_provider
        self._max_age = timedelta(seconds=max_snapshot_age_seconds)
        self._highest_revision = -1
        self._revision_digest = ""

    def check(self, key_id: str, now: datetime) -> tuple[bool, str]:
        try:
            snapshot = self._provider()
            if not isinstance(snapshot, IssuerRevocationSnapshot):
                return False, "revocation_snapshot_unavailable"
            if (
                isinstance(snapshot.revision, bool)
                or not isinstance(snapshot.revision, int)
                or snapshot.revision < 0
                or not isinstance(snapshot.key_statuses, Mapping)
                or any(
                    not isinstance(k, str) or not k
                    or v not in ("active", "revoked", "retired")
                    for k, v in snapshot.key_statuses.items()
                )
            ):
                return False, "invalid_revocation_snapshot"
            times = (now, snapshot.issued_at, snapshot.expires_at)
            if any(
                not isinstance(t, datetime)
                or t.tzinfo is None or t.utcoffset() is None
                for t in times
            ):
                return False, "invalid_revocation_time"
            now, issued, expiry = [t.astimezone(timezone.utc) for t in times]
            if issued > now or expiry <= issued or expiry <= now or now - issued > self._max_age:
                return False, "stale_or_future_revocation_snapshot"
            normalized = {
                "revision": snapshot.revision,
                "issued_at": issued.isoformat(),
                "expires_at": expiry.isoformat(),
                "key_statuses": dict(sorted(snapshot.key_statuses.items())),
            }
            digest = hashlib.sha256(
                json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            if snapshot.revision < self._highest_revision:
                return False, "revocation_snapshot_rollback"
            if snapshot.revision == self._highest_revision and digest != self._revision_digest:
                return False, "revocation_snapshot_revision_conflict"
            # Update monotonic fence only after validating a coherent snapshot.
            self._highest_revision = snapshot.revision
            self._revision_digest = digest
            status = snapshot.key_statuses.get(key_id)
            if status is None:
                return False, "issuer_absent_from_revocation_authority"
            if status != "active":
                return False, "issuer_revoked_or_retired"
            return True, "issuer_active_at_current_revocation_revision"
        except Exception:
            # No exception details are returned; a broken backend must not
            # silently authorize an older or uncontrolled key.
            return False, "revocation_authority_unavailable"
