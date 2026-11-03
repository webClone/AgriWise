"""L0-004A — Detached positive state-observation admission receipts.

A packet's own flags, provider labels and hashes are not authorities.
A scientific-state grant is valid only when a server-provisioned trusted
issuer key verifies a signature over the packet's *current full content*
and the caller's spatial/temporal scope.

This verifier does not provision keys, authenticate providers, or decide
whether a given underlying scientific measurement is accurate. Production
issuer issuance, key lifecycle and downstream runtime wiring are later
L0-004B integration gates. No hardcoded keys or dev fallbacks exist here.
"""
from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Tuple

from services.agribrain.layer0.issuer_revocation import TrustedRevocationGate
import hashlib
import hmac
import json
import math


GRANT_DOMAIN = "akaloris/layer0/positive-state-observation/v1"
ZONE_GRANT_DOMAIN = "akaloris/layer0/positive-zone-state-observation/v2"
GRANT_PURPOSE = "kalman_state_observation"
WEATHER_GRANT_PURPOSE = "weather_state_forcing"
_ALLOWED_PURPOSES = frozenset((GRANT_PURPOSE, WEATHER_GRANT_PURPOSE))
_GRANT_FIELDS = frozenset((
    "domain", "purpose", "key_id", "source", "plot_id",
    "geometry_hash", "geometry_version", "spatial_scope",
    "packet_digest", "issued_at", "expires_at",
))
_ZONE_GRANT_FIELDS = _GRANT_FIELDS | {"zone_id", "zone_geometry_hash"}


def _normalized(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("nonfinite signed evidence")
        return value
    if isinstance(value, Enum):
        return _normalized(value.value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("unsigned or naive timestamp")
        return value.astimezone(timezone.utc).isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _normalized(getattr(value, field.name))
                for field in fields(value)}
    if isinstance(value, Mapping):
        if any(not isinstance(k, str) for k in value):
            raise TypeError("signed evidence requires string keys")
        return {key: _normalized(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_normalized(item) for item in value]
    raise TypeError(f"unsupported signed evidence value: {type(value).__name__}")


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        _normalized(payload), sort_keys=True, ensure_ascii=False,
        allow_nan=False, separators=(",", ":"),
    ).encode("utf-8")


def observation_packet_digest(packet: Any) -> str:
    """SHA256 of current packet evidence, including QA and actual reliability.

    This does not rely solely on stored packet.content_hash (which can be
    cached or supplied by a caller and is not a signature).
    """
    if not hasattr(packet, "source") or not hasattr(packet, "payload"):
        raise TypeError("observation packet required")
    required = (
        "packet_id", "content_hash", "source", "obs_type",
        "timestamp", "timestamp_end", "plot_id", "geometry_hash",
        "geometry_version", "spatial_scope", "crs", "geometry_type",
        "bbox", "point", "polygon_wkt", "data_status", "payload",
        "qa", "uncertainty", "provenance", "reliability_weight",
    )
    material = {name: getattr(packet, name) for name in required}
    return hashlib.sha256(_canonical_bytes(material)).hexdigest()


def _utc_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        candidate = value
    elif isinstance(value, str):
        try:
            candidate = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if candidate.tzinfo is None or candidate.utcoffset() is None:
        return None
    return candidate.astimezone(timezone.utc)


class PositiveObservationAdmissionVerifier:
    """Verifier whose keyring must come from trusted backend configuration.

    `issuer_keys`: key-id -> (authorized ObservationSource.value, secret).
    Keys are never obtained from observations, user payloads or receipts.
    All signature failures return (False, reason) and do not grant state.
    """

    def __init__(
        self,
        issuer_keys: Mapping[str, Tuple[str, bytes]],
        *,
        revocation_gate: TrustedRevocationGate | None = None,
        trusted_zone_registry: Mapping[str, Mapping[str, Any]] | None = None,
    ):
        if revocation_gate is not None and not isinstance(revocation_gate, TrustedRevocationGate):
            raise ValueError("invalid independent issuer revocation authority")
        # Caller must provision this registry from trusted plot/zone metadata,
        # not from incoming packets or the client. Its existence is still
        # not a physical polygon-intersection proof.
        zone_registry = {}
        if trusted_zone_registry is not None:
            if not isinstance(trusted_zone_registry, Mapping):
                raise ValueError("invalid trusted zone registry")
            for plot, scope in trusted_zone_registry.items():
                if (
                    not isinstance(plot, str) or not plot
                    or not isinstance(scope, Mapping)
                    or set(scope) != {"geometry_hash", "geometry_version", "zones"}
                    or not isinstance(scope["geometry_hash"], str)
                    or not scope["geometry_hash"]
                    or isinstance(scope["geometry_version"], bool)
                    or not isinstance(scope["geometry_version"], int)
                    or not isinstance(scope["zones"], Mapping)
                    or any(
                        not isinstance(z, str) or not z or z == "plot"
                        or not isinstance(h, str) or not h
                        for z, h in scope["zones"].items()
                    )
                ):
                    raise ValueError("invalid trusted zone scope")
                zone_registry[plot] = {
                    "geometry_hash": scope["geometry_hash"],
                    "geometry_version": scope["geometry_version"],
                    "zones": dict(scope["zones"]),
                }
        self._zone_registry = zone_registry
        self._revocation_gate = revocation_gate
        keyring = {}
        for key_id, rule in issuer_keys.items():
            if (
                not isinstance(key_id, str) or not key_id
                or not isinstance(rule, tuple) or len(rule) != 2
                or not isinstance(rule[0], str) or not rule[0]
                or not isinstance(rule[1], bytes) or len(rule[1]) < 32
            ):
                raise ValueError("invalid admission verifier trust root")
            keyring[key_id] = rule
        self._issuer_keys = keyring

    @property
    def revocation_enforced(self) -> bool:
        return self._revocation_gate is not None

    @property
    def zone_authority_configured(self) -> bool:
        return bool(self._zone_registry)

    def verify(
        self, receipt: Any, packet: Any, *,
        plot_id: str, geometry_hash: str, geometry_version: int | None,
        run_timestamp: datetime,
        purpose: str = GRANT_PURPOSE,
    ) -> tuple[bool, str]:
        try:
            if purpose not in _ALLOWED_PURPOSES:
                return False, "unsupported_grant_purpose"
            if (
                not isinstance(plot_id, str) or not plot_id
                or not isinstance(geometry_hash, str) or not geometry_hash
                or isinstance(geometry_version, bool)
                or not isinstance(geometry_version, int)
                or geometry_version < 0
            ):
                return False, "missing_authoritative_caller_scope"
            run_time = _utc_time(run_timestamp)
            if run_time is None:
                return False, "invalid_run_timestamp"
            if not isinstance(receipt, dict) or set(receipt) != {"grant", "mac"}:
                return False, "missing_or_malformed_grant"
            grant, mac = receipt["grant"], receipt["mac"]
            if not isinstance(grant, dict):
                return False, "malformed_grant_fields"
            grant_scope = grant.get("spatial_scope")
            required_fields = (
                _ZONE_GRANT_FIELDS if grant_scope == "zone" else _GRANT_FIELDS
            )
            if set(grant) != required_fields:
                return False, "malformed_grant_fields"
            if not isinstance(mac, str) or len(mac) != 64:
                return False, "malformed_grant_signature"
            int(mac, 16)
            key_rule = self._issuer_keys.get(grant["key_id"])
            if key_rule is None:
                return False, "untrusted_or_revoked_issuer"
            source = getattr(getattr(packet, "source", None), "value", None)
            scope = getattr(packet, "spatial_scope", None)
            if (
                source != key_rule[0] or grant["source"] != source
                or grant["domain"] != (
                    ZONE_GRANT_DOMAIN if grant_scope == "zone" else GRANT_DOMAIN
                )
                or grant["purpose"] != purpose
            ):
                return False, "wrong_issuer_source_or_purpose"
            if (
                getattr(packet, "plot_id", None) != plot_id
                or getattr(packet, "geometry_hash", None) != geometry_hash
                or getattr(packet, "geometry_version", None) != geometry_version
                or grant["plot_id"] != plot_id
                or grant["geometry_hash"] != geometry_hash
                or grant["geometry_version"] != geometry_version
                or grant["spatial_scope"] != scope
                or scope not in ("plot", "zone")
            ):
                return False, "wrong_or_unbound_spatial_scope"
            if scope == "zone":
                if purpose != GRANT_PURPOSE:
                    return False, "zone_weather_forcing_not_authorized"
                payload = getattr(packet, "payload", None)
                if not isinstance(payload, dict):
                    return False, "missing_zone_payload"
                zone_id = payload.get("zone_id")
                zone_hash = payload.get("zone_geometry_hash")
                trusted = self._zone_registry.get(plot_id)
                if (
                    not isinstance(zone_id, str) or not zone_id
                    or not isinstance(zone_hash, str) or not zone_hash
                    or grant["zone_id"] != zone_id
                    or grant["zone_geometry_hash"] != zone_hash
                    or trusted is None
                    or trusted["geometry_hash"] != geometry_hash
                    or trusted["geometry_version"] != geometry_version
                    or trusted["zones"].get(zone_id) != zone_hash
                ):
                    return False, "unregistered_or_foreign_zone_geometry"
            stamp = _utc_time(getattr(packet, "timestamp", None))
            issued = _utc_time(grant["issued_at"])
            expiry = _utc_time(grant["expires_at"])
            if (
                stamp is None or issued is None or expiry is None
                or stamp > run_time or issued > run_time
                or expiry < run_time or expiry <= issued
            ):
                return False, "invalid_or_future_grant_time"
            end = getattr(packet, "timestamp_end", None)
            if end is not None:
                end_time = _utc_time(end)
                if end_time is None or end_time < stamp or end_time > run_time:
                    return False, "invalid_observation_time_window"
            if grant["packet_digest"] != observation_packet_digest(packet):
                return False, "packet_content_mismatch"
            canonical = _canonical_bytes(grant)
            expected = hmac.new(key_rule[1], canonical, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, mac):
                return False, "bad_grant_signature"
            if self._revocation_gate is not None:
                allowed, policy_reason = self._revocation_gate.check(
                    grant["key_id"], run_time
                )
                if not allowed:
                    return False, policy_reason
            return True, "verified_positive_source_grant"
        except (ValueError, TypeError, KeyError, OverflowError, AttributeError):
            return False, "invalid_grant_or_packet"
