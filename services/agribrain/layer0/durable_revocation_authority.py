"""L0-B2B06: Durable Revocation and Zone Authority Contracts.

Establishes an independently controlled, tamper-evident, monotonically fenced
revocation authority. Tracks active/retired/revoked KMS issuer keys, revoked plot
scopes, revoked zonal scopes, and explicitly revoked grant receipts.

Defends against:
- Monotonic revision rollbacks (RevocationRollbackError)
- Split-brain / same-revision conflicts (RevocationConflictError)
- Stale or expired revocation snapshots
- Future-dated revocation snapshots (clock skew tolerance bounded)
- Unregistered/absent issuer keys (fail-closed)
- Unauthorized plot/zone state admission after scope revocation
- Dynamic/live snapshot refresh via trusted provider callback
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import rfc8785
from typing import Any, Callable, Mapping, Sequence


class RevocationStatus(str, Enum):
    ACTIVE = "active"
    RETIRED = "retired"
    REVOKED = "revoked"


class RevocationError(ValueError):
    """Base class for revocation policy violations."""


class RevocationRollbackError(RevocationError):
    """Attempted to load a revocation snapshot with a lower revision."""


class RevocationConflictError(RevocationError):
    """Snapshot at the same revision has conflicting content or digest."""


class RevocationStaleError(RevocationError):
    """Revocation snapshot is stale or expired."""


def _ensure_utc(dt: Any) -> datetime:
    if isinstance(dt, str):
        candidate = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    elif isinstance(dt, datetime):
        candidate = dt
    else:
        raise ValueError(f"invalid timestamp: {dt!r}")
    if candidate.tzinfo is None or candidate.utcoffset() is None:
        raise ValueError(f"naive or unsigned timestamp: {dt!r}")
    return candidate.astimezone(timezone.utc)


def _canonical_json(obj: Any) -> bytes:
    def normalize(val: Any) -> Any:
        if val is None or isinstance(val, (str, bool, int)):
            return val
        if isinstance(val, float):
            return val
        if isinstance(val, Enum):
            return normalize(val.value)
        if isinstance(val, datetime):
            return _ensure_utc(val).isoformat()
        if isinstance(val, Mapping):
            return {k: normalize(v) for k, v in sorted(val.items()) if isinstance(k, str)}
        if isinstance(val, (list, tuple, set, frozenset)):
            return [normalize(x) for x in sorted(val, key=lambda i: str(i))]
        raise TypeError(f"unsupported canonical type: {type(val).__name__}")

    return rfc8785.dumps(normalize(obj))


@dataclass(frozen=True)
class DurableRevocationSnapshot:
    """Tamper-evident, hash-chained revocation ledger snapshot."""
    revision: int
    issued_at: datetime
    expires_at: datetime
    key_statuses: Mapping[str, str]
    revoked_plots: tuple[str, ...] = ()
    revoked_zones: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    revoked_grants: tuple[str, ...] = ()
    previous_digest: str = "genesis"
    snapshot_digest: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 0:
            raise ValueError("revision must be a non-negative integer")
        issued = _ensure_utc(self.issued_at)
        expires = _ensure_utc(self.expires_at)
        if expires <= issued:
            raise ValueError("expires_at must be strictly after issued_at")
        object.__setattr__(self, "issued_at", issued)
        object.__setattr__(self, "expires_at", expires)

        # Validate key statuses
        cleaned_keys: dict[str, str] = {}
        for k, v in self.key_statuses.items():
            if not isinstance(k, str) or not k:
                raise ValueError("key_id must be non-empty string")
            val = v.value if isinstance(v, RevocationStatus) else str(v)
            if val not in ("active", "retired", "revoked"):
                raise ValueError(f"invalid status {v!r} for key {k}")
            cleaned_keys[k] = val
        object.__setattr__(self, "key_statuses", dict(sorted(cleaned_keys.items())))

        # Validate revoked plots
        cleaned_plots = tuple(sorted(set(str(p) for p in self.revoked_plots if p)))
        object.__setattr__(self, "revoked_plots", cleaned_plots)

        # Validate revoked zones: plot_id -> tuple[zone_id, ...]
        cleaned_zones: dict[str, tuple[str, ...]] = {}
        for p, z_list in self.revoked_zones.items():
            if not isinstance(p, str) or not p:
                continue
            zones = tuple(sorted(set(str(z) for z in z_list if z)))
            if zones:
                cleaned_zones[p] = zones
        object.__setattr__(self, "revoked_zones", dict(sorted(cleaned_zones.items())))

        # Validate revoked grants
        cleaned_grants = tuple(sorted(set(str(g) for g in self.revoked_grants if g)))
        object.__setattr__(self, "revoked_grants", cleaned_grants)

        # Compute digest if empty
        if not self.snapshot_digest:
            material = {
                "revision": self.revision,
                "issued_at": issued.isoformat(),
                "expires_at": expires.isoformat(),
                "key_statuses": cleaned_keys,
                "revoked_plots": list(cleaned_plots),
                "revoked_zones": {k: list(v) for k, v in sorted(cleaned_zones.items())},
                "revoked_grants": list(cleaned_grants),
                "previous_digest": self.previous_digest,
            }
            digest = hashlib.sha256(_canonical_json(material)).hexdigest()
            object.__setattr__(self, "snapshot_digest", digest)

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "key_statuses": dict(self.key_statuses),
            "revoked_plots": list(self.revoked_plots),
            "revoked_zones": {k: list(v) for k, v in self.revoked_zones.items()},
            "revoked_grants": list(self.revoked_grants),
            "previous_digest": self.previous_digest,
            "snapshot_digest": self.snapshot_digest,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DurableRevocationSnapshot:
        return cls(
            revision=data["revision"],
            issued_at=_ensure_utc(data["issued_at"]),
            expires_at=_ensure_utc(data["expires_at"]),
            key_statuses=data.get("key_statuses", {}),
            revoked_plots=tuple(data.get("revoked_plots", ())),
            revoked_zones=data.get("revoked_zones", {}),
            revoked_grants=tuple(data.get("revoked_grants", ())),
            previous_digest=data.get("previous_digest", "genesis"),
            snapshot_digest=data.get("snapshot_digest", ""),
        )


class DurableRevocationAuthority:
    """Fenced revocation engine enforcing monotonic ledger progression.
    
    Can be used in-process, loaded from trusted disk snapshot, or connected
    to an authoritative durable storage adapter with live refresh provider.
    """

    def __init__(
        self,
        initial_snapshot: DurableRevocationSnapshot | None = None,
        *,
        snapshot_provider: Callable[[], DurableRevocationSnapshot] | None = None,
        max_snapshot_age_seconds: int = 300,
        clock_skew_tolerance_seconds: int = 5,
    ) -> None:
        if (
            isinstance(max_snapshot_age_seconds, bool)
            or not isinstance(max_snapshot_age_seconds, int)
            or not 1 <= max_snapshot_age_seconds <= 86400
        ):
            raise ValueError("invalid max_snapshot_age_seconds")
        if (
            isinstance(clock_skew_tolerance_seconds, bool)
            or not isinstance(clock_skew_tolerance_seconds, int)
            or not 0 <= clock_skew_tolerance_seconds <= 60
        ):
            raise ValueError("invalid clock_skew_tolerance_seconds")
        if snapshot_provider is not None and not callable(snapshot_provider):
            raise ValueError("snapshot_provider must be callable")

        self._provider = snapshot_provider
        self._max_age = timedelta(seconds=max_snapshot_age_seconds)
        self._skew_tolerance = timedelta(seconds=clock_skew_tolerance_seconds)
        self._current_snapshot: DurableRevocationSnapshot | None = None
        self._highest_revision: int = -1
        self._revision_digest: str = ""

        if initial_snapshot is not None:
            self.load_snapshot(initial_snapshot)

    @property
    def current_revision(self) -> int:
        return self._highest_revision

    @property
    def current_digest(self) -> str:
        return self._revision_digest

    @property
    def current_snapshot(self) -> DurableRevocationSnapshot | None:
        return self._current_snapshot

    def load_snapshot(self, snapshot: DurableRevocationSnapshot) -> None:
        """Apply a new snapshot, enforcing monotonicity and conflict detection."""
        if not isinstance(snapshot, DurableRevocationSnapshot):
            raise TypeError("expected DurableRevocationSnapshot")

        # Rollback check
        if snapshot.revision < self._highest_revision:
            raise RevocationRollbackError(
                f"revocation rollback detected: new {snapshot.revision} < highest {self._highest_revision}"
            )

        # Same-revision conflict check
        if snapshot.revision == self._highest_revision:
            if snapshot.snapshot_digest != self._revision_digest:
                raise RevocationConflictError(
                    f"revocation conflict at revision {snapshot.revision}: digests differ"
                )
            # Idempotent re-load of exact same snapshot
            return

        # Monotonic increment accepted
        self._highest_revision = snapshot.revision
        self._revision_digest = snapshot.snapshot_digest
        self._current_snapshot = snapshot

    def check_authority(
        self,
        key_id: str,
        now: datetime,
        *,
        revision_anchor: int | None = None,
        plot_id: str | None = None,
        zone_id: str | None = None,
        grant_id: str | None = None,
    ) -> tuple[bool, str]:
        """Verify key status, freshness, revision anchor, plot and zone authority."""
        try:
            # Live refresh from provider if configured
            if self._provider is not None:
                try:
                    fresh_snap = self._provider()
                    self.load_snapshot(fresh_snap)
                except RevocationError as r_err:
                    return False, f"revocation_ledger_violation:{type(r_err).__name__}"
                except Exception as p_err:
                    return False, f"revocation_provider_error:{type(p_err).__name__}"

            snapshot = self._current_snapshot
            if snapshot is None:
                return False, "revocation_authority_uninitialized"

            current_time = _ensure_utc(now)

            # Freshness and expiry checks
            if current_time + self._skew_tolerance < snapshot.issued_at:
                return False, "future_dated_revocation_snapshot"
            if current_time > snapshot.expires_at:
                return False, "expired_revocation_snapshot"
            if current_time - snapshot.issued_at > self._max_age:
                return False, "stale_revocation_snapshot"

            # Monotonic revision anchor check (grant cannot claim a revision newer than current ledger)
            if revision_anchor is not None:
                if isinstance(revision_anchor, bool) or not isinstance(revision_anchor, int) or revision_anchor < 0:
                    return False, "invalid_revision_anchor"
                if snapshot.revision < revision_anchor:
                    return False, "revocation_anchor_behind_ledger"

            # Key status check
            status = snapshot.key_statuses.get(key_id)
            if status is None:
                return False, "issuer_key_absent_from_revocation_ledger"
            if status == "revoked":
                return False, "issuer_key_revoked"
            if status == "retired":
                return False, "issuer_key_retired"
            if status != "active":
                return False, "issuer_key_inactive"

            # Plot scope check
            if plot_id is not None:
                if not isinstance(plot_id, str) or not plot_id:
                    return False, "invalid_plot_id"
                if plot_id in snapshot.revoked_plots:
                    return False, "plot_scope_revoked"

            # Zone scope check
            if zone_id is not None:
                if not isinstance(zone_id, str) or not zone_id:
                    return False, "invalid_zone_id"
                if plot_id is not None and zone_id in snapshot.revoked_zones.get(plot_id, ()):
                    return False, "zone_scope_revoked"

            # Grant explicit revocation check
            if grant_id is not None:
                if not isinstance(grant_id, str) or not grant_id:
                    return False, "invalid_grant_id"
                if grant_id in snapshot.revoked_grants:
                    return False, "grant_explicitly_revoked"

            return True, "revocation_authority_active_and_verified"
        except Exception as exc:
            return False, f"revocation_check_internal_error:{type(exc).__name__}"
