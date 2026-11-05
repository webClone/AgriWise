"""B2B-08A: opt-in server-owned L3 physical-delivery admission bootstrap.

This module provisions PUBLIC verification keys and a live durable revocation
snapshot, bound to a transaction-capable *shared* MongoDB backend.
It cannot sign grants, and has no HTTP/user-payload configuration inputs.

Production remains fail-closed:
  - no explicit enable => L3 delivery authority not installed;
  - explicit enable + missing trust root => startup fails, not a weak fallback.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping

from services.agribrain.layer0.production_admission import (
    Layer0AdmissionRequiredError,
    configure_server_delivery_verifier,
    live_revocation_required,
    signed_inputs_required,
    v3_kms_required,
)
from services.agribrain.layer0.durable_revocation_authority import (
    DurableRevocationAuthority,
    DurableRevocationSnapshot,
)
from services.agribrain.layer0.v3_kms_signed_issuer import KmsPublicKeyRegistry
from services.agribrain.layer0.verified_irrigation_contract import (
    VERIFIED_IRRIGATION_PURPOSE,
)

ENABLE_FLAG = "AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION"
KEYS_FLAG = "AKALORIS_LAYER0_L3_PUBLIC_KEYS_JSON"
REVOCATION_FLAG = "AKALORIS_LAYER0_L3_DURABLE_REVOCATION_PATH"
REQUIRE_SCOPE_FLAG = "AKALORIS_LAYER0_REQUIRE_PLOT_SCOPE"


def _truth_flag(raw: str | None, label: str) -> bool:
    flag = (raw or "").strip().lower()
    if flag in ("", "0", "false", "no"):
        return False
    if flag in ("1", "true", "yes"):
        return True
    raise Layer0AdmissionRequiredError(
        f"invalid {label} deployment flag"
    )


def verified_irrigation_enabled() -> bool:
    """Explicit backend opt-in, never from request or packet fields."""
    return _truth_flag(os.getenv(ENABLE_FLAG), ENABLE_FLAG)


def _unique_json(raw: str, what: str) -> Mapping[str, Any]:
    def check_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    try:
        result = json.loads(raw, object_pairs_hook=check_pairs)
    except (ValueError, TypeError):
        raise Layer0AdmissionRequiredError(f"malformed {what} deployment configuration") from None
    if not isinstance(result, dict) or not result:
        raise Layer0AdmissionRequiredError(f"empty {what} deployment configuration")
    return result


def _utc_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("expected explicit UTC timestamp")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("timezone missing")
    return dt.astimezone(timezone.utc)


def _load_l3_keys(raw: str) -> KmsPublicKeyRegistry:
    specs = _unique_json(raw, "L3 public key registry")
    registry = KmsPublicKeyRegistry()
    expected = {
        "issuer_id", "source", "algorithm", "public_key_pem",
        "valid_from", "valid_until",
    }
    for key_id, spec in specs.items():
        if not isinstance(spec, dict) or set(spec) != expected:
            raise Layer0AdmissionRequiredError("invalid L3 public key schema")
        public = spec["public_key_pem"]
        if (
            not isinstance(public, str)
            or "-----BEGIN PUBLIC KEY-----" not in public
            or "PRIVATE KEY" in public
            or not public.strip().endswith("-----END PUBLIC KEY-----")
        ):
            raise Layer0AdmissionRequiredError("L3 verifier only accepts public keys")
        if spec["algorithm"] not in ("Ed25519", "ES256"):
            raise Layer0AdmissionRequiredError("unsupported L3 signature algorithm")
        try:
            registry.register_public_key(
                key_id=key_id,
                issuer_id=spec["issuer_id"],
                source=spec["source"],
                algorithm=spec["algorithm"],
                public_key_pem_or_bytes=public,
                valid_from=_utc_time(spec["valid_from"]),
                valid_until=_utc_time(spec["valid_until"]),
                permitted_purposes=(VERIFIED_IRRIGATION_PURPOSE,),
            )
        except Exception:
            # Cryptography may also raise UnsupportedAlgorithm on malformed
            # imported public keys. No raw configuration is included in error
            # reports or logs from this untrusted deployment surface.
            raise Layer0AdmissionRequiredError("invalid L3 public key entry") from None
    return registry


def _load_revocation_snapshot(path: Path) -> DurableRevocationSnapshot:
    if not path.is_file():
        raise Layer0AdmissionRequiredError(
            "L3 durable revocation snapshot unavailable"
        )
    try:
        raw = path.read_text(encoding="utf-8")
        data = _unique_json(raw, "L3 revocation snapshot")
        return DurableRevocationSnapshot.from_dict(data)
    except (OSError, ValueError, TypeError, UnicodeError):
        raise Layer0AdmissionRequiredError(
            "invalid L3 durable revocation snapshot"
        ) from None


def bootstrap_server_verified_irrigation(database: Any = None):
    """Create trusted L3 verifier from server deployment configuration only.

    Caller must never pass database or source configs from HTTP inputs.
    The disabled path makes no MongoDB calls. An enabled path requires a
    transaction-capable replica set/sharded cluster, public-only keyring and
    fresh, dynamically reloaded durable revocation snapshot.
    """
    if not verified_irrigation_enabled():
        return None

    if not (
        signed_inputs_required()
        and v3_kms_required()
        and live_revocation_required()
        and _truth_flag(os.getenv(REQUIRE_SCOPE_FLAG), REQUIRE_SCOPE_FLAG)
    ):
        raise Layer0AdmissionRequiredError(
            "L3 physical delivery requires signed v3, live revocation and authenticated plot scope"
        )
    if database is None:
        raise Layer0AdmissionRequiredError(
            "L3 physical delivery requires connected server MongoDB"
        )

    try:
        database.command("ping")
        topology = database.command("hello")
        is_transactional = (
            isinstance(topology, dict)
            and (bool(topology.get("setName")) or topology.get("msg") == "isdbgrid")
        )
    except Exception:
        raise Layer0AdmissionRequiredError(
            "L3 physical delivery MongoDB topology unavailable"
        ) from None
    if not is_transactional:
        raise Layer0AdmissionRequiredError(
            "L3 physical delivery requires a transaction-capable replica set"
        )

    raw_keys = os.getenv(KEYS_FLAG, "").strip()
    path = os.getenv(REVOCATION_FLAG, "").strip()
    if not raw_keys or not path:
        raise Layer0AdmissionRequiredError(
            "L3 public keys and live revocation snapshot are required"
        )
    registry = _load_l3_keys(raw_keys)
    rev_path = Path(path)
    initial = _load_revocation_snapshot(rev_path)

    def live_snapshot():
        return _load_revocation_snapshot(rev_path)

    authority = DurableRevocationAuthority(
        initial_snapshot=initial,
        snapshot_provider=live_snapshot,
        max_snapshot_age_seconds=300,
    )
    # There must be an issuer currently active under the live revocation
    # policy, not merely a syntactically well-formed snapshot.
    now = datetime.now(timezone.utc)
    entries = registry._entries  # read only; registry holds public keys
    if not any(
        entry.is_valid_at(now)
        and authority.check_authority(key_id, now)[0]
        for key_id, entry in entries.items()
    ):
        raise Layer0AdmissionRequiredError(
            "L3 public key and live revocation authority are not active"
        )
    try:
        return configure_server_delivery_verifier(
            database=database,
            public_key_registry=registry,
            revocation_authority=authority,
        )
    except Exception:
        raise Layer0AdmissionRequiredError(
            "L3 trusted transactional verifier initialization failed"
        ) from None


def create_server_layer0_state_engine(
    app: Any, *, plot_ownership_store: Any,
    principal_provider: Any, positive_admission_verifier: Any,
):
    """Server-only engine construction; NEVER pass caller-defined verifiers.

    The consumer must resolve tenant/plot/geometry independently using the
    existing B2B-05 ownership store and authenticated principal.
    """
    from services.agribrain.layer0.state_engine import Layer0StateEngine

    enabled = verified_irrigation_enabled()
    # A disabled deployment never imports an accidental/stale verifier from
    # mutable app.state, even if another server component assigned one.
    verifier = (
        getattr(app.state, "layer0_verified_irrigation_verifier", None)
        if enabled else None
    )
    if enabled and verifier is None:
        raise Layer0AdmissionRequiredError(
            "enabled L3 authority is unavailable in application runtime"
        )
    return Layer0StateEngine(
        positive_admission_verifier=positive_admission_verifier,
        plot_ownership_store=plot_ownership_store,
        principal_provider=principal_provider,
        verified_delivery_verifier=verifier,
    )
