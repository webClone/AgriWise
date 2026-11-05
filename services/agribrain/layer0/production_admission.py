"""Mandatory state-input authority policy for Layer 0 runtime entrypoints.

The policy is derived from server process configuration, never from a packet,
API body, tenant preference, or source-provided health flags. Production and
staging cannot opt out. Scientific/research compatibility defaults to legacy
unless explicitly enabled by the trusted deployment.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os


class Layer0AdmissionRequiredError(RuntimeError):
    """Fail-closed scientific state input or required trust root."""


def signed_inputs_required() -> bool:
    """Return mandatory policy at runtime, not at import time.

    Environment detection mirrors the internal service auth module. An explicit
    `AKALORIS_LAYER0_REQUIRE_SIGNED_INPUTS=true` can also harden development
    tests and research deployments. `false` never disables production.
    """
    # Treat ANY deployment environment declaring production/staging as
    # authoritative; a stray NODE_ENV=development cannot cancel ENV=prod.
    environments = (
        os.getenv(name, "").strip().lower()
        for name in ("NODE_ENV", "ENVIRONMENT", "ENV", "APP_ENV")
    )
    return any(name in ("production", "prod", "staging") for name in environments) or (
        os.getenv("AKALORIS_LAYER0_REQUIRE_SIGNED_INPUTS", "")
        .strip().lower() in ("true", "1", "yes")
    )


def live_revocation_required() -> bool:
    """Opt-in deployment migration gate for a continuously checked registry."""
    return (
        signed_inputs_required()
        and os.getenv("AKALORIS_LAYER0_REQUIRE_LIVE_REVOCATION", "")
        .strip().lower() in ("true", "1", "yes")
    )


def v3_kms_required() -> bool:
    """Opt-in deployment gate for mandatory v3 KMS asymmetric issuance."""
    return (
        signed_inputs_required()
        and os.getenv("AKALORIS_LAYER0_REQUIRE_V3_KMS", "")
        .strip().lower() in ("true", "1", "yes")
    )


def require_trusted_verifier(verifier: object) -> None:
    """Reject missing keyring or required live revocation authority."""
    if signed_inputs_required() and verifier is None:
        raise Layer0AdmissionRequiredError(
            "Layer 0 signed state-input policy is mandatory but no trusted "
            "source-admission verifier is provisioned"
        )
    # A legacy HMAC verifier can legitimately advertise revocation_enforced,
    # but MUST NOT satisfy a mandatory asymmetric-v3 policy. Check the exact
    # underlying v3 verifier; an aggregate property is insufficient.
    if v3_kms_required():
        from services.agribrain.layer0.v3_kms_signed_issuer import V3KmsGrantVerifier
        from services.agribrain.layer0.v3_state_admission import UnifiedAdmissionVerifier

        if isinstance(verifier, V3KmsGrantVerifier):
            trusted_v3 = verifier
        elif (
            isinstance(verifier, UnifiedAdmissionVerifier)
            and verifier.enforces_v3_only
            and isinstance(verifier.v3_verifier, V3KmsGrantVerifier)
        ):
            trusted_v3 = verifier.v3_verifier
        else:
            raise Layer0AdmissionRequiredError(
                "Mandatory v3 KMS policy requires a trusted asymmetric v3 verifier"
            )
        if not trusted_v3.revocation_enforced:
            raise Layer0AdmissionRequiredError(
                "Mandatory v3 KMS verifier requires durable revocation authority"
            )
    elif live_revocation_required() and not getattr(verifier, "revocation_enforced", False):
        raise Layer0AdmissionRequiredError(
            "Live issuer revocation policy required but no trusted authority is provisioned"
        )


def require_trusted_delivery_verifier(verifier: object) -> None:
    """Reject untrusted physical delivery verifier or missing live revocation authority."""
    if verifier is None:
        return
    from services.agribrain.layer0.verified_irrigation_contract import (
        VerifiedDeliveredIrrigationVerifier,
    )
    from services.agribrain.layer0.durable_revocation_authority import (
        DurableRevocationAuthority,
    )

    if not isinstance(verifier, VerifiedDeliveredIrrigationVerifier):
        raise Layer0AdmissionRequiredError(
            "Delivered irrigation verifier must be an authoritative VerifiedDeliveredIrrigationVerifier"
        )
    if (
        verifier.revocation_authority is None
        or not isinstance(verifier.revocation_authority, DurableRevocationAuthority)
    ):
        raise Layer0AdmissionRequiredError(
            "Authoritative delivered irrigation verifier requires active durable revocation authority"
        )
    # A JSON file or an in-memory set is process-local and does not fence
    # receipt replay between horizontally scaled production workers.
    # An absent verifier is safe (no physical forcing), but a configured
    # production verifier MUST use the same transactional Mongo authority.
    if signed_inputs_required():
        from services.agribrain.layer0.mongo_irrigation_idempotency import (
            MongoIrrigationIdempotencyStore,
        )
        if not isinstance(
            verifier.idempotency_store, MongoIrrigationIdempotencyStore
        ):
            raise Layer0AdmissionRequiredError(
                "Production delivered irrigation requires shared Mongo transaction journal"
            )


def configure_server_delivery_verifier(
    *, database, public_key_registry, revocation_authority,
    historical_recompute_authorizer=None,
    require_transactional_revocation: bool = True,
):
    """Trusted backend factory: fail closed without a shared Mongo ledger.

    Never accept database/registry/authorizer from HTTP payloads. The
    deployment must supply a transaction-capable Mongo replica set and L3
    public keys from its own protected configuration.
    Mandates in-transaction revocation write fencing in production.
    """
    if require_transactional_revocation is not True:
        raise Layer0AdmissionRequiredError("transactional_revocation_required_in_production")
    from services.agribrain.layer0.mongo_irrigation_idempotency import (
        MongoIrrigationIdempotencyStore,
    )
    from services.agribrain.layer0.verified_irrigation_contract import (
        VerifiedDeliveredIrrigationVerifier,
    )
    # Provision/sync active keys into Layer0RevocationLedger in MongoDB so that
    # in-transaction write-fencing is provisioned from the trusted public key registry
    if database is not None and callable(getattr(database, "command", None)):
        rev_coll = database["Layer0RevocationLedger"]
        entries = getattr(public_key_registry, "_entries", {})
        now_utc = datetime.now(timezone.utc)
        for key_id, entry in entries.items():
            status = "active"
            if revocation_authority and callable(getattr(revocation_authority, "check_authority", None)):
                ok, _ = revocation_authority.check_authority(key_id, now_utc)
                if not ok:
                    status = "revoked"
            rev_coll.update_one(
                {"_id": key_id},
                {"$setOnInsert": {"_id": key_id, "status": status, "initialized_at": now_utc}},
                upsert=True,
            )

    store = MongoIrrigationIdempotencyStore(
        database,
        historical_recompute_authorizer=historical_recompute_authorizer,
        require_transactional_revocation=require_transactional_revocation,
    )
    verifier = VerifiedDeliveredIrrigationVerifier(
        public_key_registry=public_key_registry,
        revocation_authority=revocation_authority,
        idempotency_store=store,
    )
    require_trusted_delivery_verifier(verifier)
    return verifier


def load_server_issuer_verifier():
    """Read a backend-only issuer registry provisioned via deployment secrets.

    Deployment injects AKALORIS_LAYER0_ISSUER_KEYS_JSON from its secrets
    manager; it is NEVER accepted from an HTTP request, plot data, or packet.
    Format: {"key-id":{"source":"sentinel2","secret_b64":"..."}}.
    Missing/malformed configuration fails closed in mandatory mode. A secret
    manager deployment remains an external operational requirement.
    """
    import base64
    import binascii
    import json
    from services.agribrain.layer0.positive_observation_admission import (
        PositiveObservationAdmissionVerifier,
    )
    from services.agribrain.layer0.issuer_revocation import (
        IssuerRevocationSnapshot, TrustedRevocationGate,
    )
    from datetime import datetime
    from pathlib import Path

    from services.agribrain.layer0.v3_kms_signed_issuer import (
        KmsPublicKeyRegistry,
        V3KmsGrantVerifier,
    )
    from services.agribrain.layer0.v3_state_admission import UnifiedAdmissionVerifier
    from services.agribrain.layer0.durable_revocation_authority import (
        DurableRevocationAuthority,
        DurableRevocationSnapshot,
    )

    kms_raw = os.getenv("AKALORIS_LAYER0_KMS_PUBLIC_KEYS_JSON", "").strip()
    raw = os.getenv("AKALORIS_LAYER0_ISSUER_KEYS_JSON", "").strip()

    if v3_kms_required() and not kms_raw:
        raise Layer0AdmissionRequiredError(
            "Mandatory v3 KMS policy requires deployment-provisioned KMS public keys"
        )

    if not raw and not kms_raw:
        if signed_inputs_required():
            raise Layer0AdmissionRequiredError(
                "Mandatory Layer 0 admission requires deployment-provisioned issuer keys"
            )
        return None

    def reject_duplicate_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate issuer configuration key")
            result[key] = value
        return result

    try:
        issuer_keys = {}
        if raw:
            configured = json.loads(raw, object_pairs_hook=reject_duplicate_keys)
            if not isinstance(configured, dict) or not configured:
                raise ValueError("empty issuer registry")
            for key_id, config in configured.items():
                if not isinstance(config, dict) or set(config) != {"source", "secret_b64"}:
                    raise ValueError("malformed issuer rule")
                encoded = config["secret_b64"]
                if not isinstance(encoded, str):
                    raise ValueError("malformed issuer secret encoding")
                key_bytes = base64.b64decode(encoded, validate=True)
                if len(key_bytes) < 32:
                    raise ValueError("issuer secret is too short")
                issuer_keys[key_id] = (config["source"], key_bytes)
        # These protected deployment paths are not packet/request inputs.
        # Revocation snapshots are re-read on every verifier call, allowing a
        # trusted backend to rotate/revoke without restarting the worker.
        revocation_path = os.getenv("AKALORIS_LAYER0_REVOCATION_SNAPSHOT_PATH", "").strip()
        gate = None
        if (raw or not v3_kms_required()) and live_revocation_required() and not revocation_path:
            raise Layer0AdmissionRequiredError(
                "Live issuer revocation is mandatory but no trusted policy path is provisioned"
            )
        if revocation_path:
            def live_revocation_snapshot():
                raw_snapshot = Path(revocation_path).read_text(encoding="utf-8")
                record = json.loads(raw_snapshot, object_pairs_hook=reject_duplicate_keys)
                if (
                    not isinstance(record, dict)
                    or set(record) != {"revision", "issued_at", "expires_at", "key_statuses"}
                    or not isinstance(record["issued_at"], str)
                    or not isinstance(record["expires_at"], str)
                ):
                    raise ValueError("invalid trusted revocation record")
                return IssuerRevocationSnapshot(
                    revision=record["revision"],
                    issued_at=datetime.fromisoformat(record["issued_at"].replace("Z", "+00:00")),
                    expires_at=datetime.fromisoformat(record["expires_at"].replace("Z", "+00:00")),
                    key_statuses=record["key_statuses"],
                )
            gate = TrustedRevocationGate(live_revocation_snapshot)

        zone_registry_path = os.getenv("AKALORIS_LAYER0_ZONE_REGISTRY_PATH", "").strip()
        zone_registry = None
        if zone_registry_path:
            zone_registry = json.loads(
                Path(zone_registry_path).read_text(encoding="utf-8"),
                object_pairs_hook=reject_duplicate_keys,
            )
        legacy_verifier = None
        if issuer_keys:
            legacy_verifier = PositiveObservationAdmissionVerifier(
                issuer_keys,
                revocation_gate=gate,
                trusted_zone_registry=zone_registry,
            )

        v3_verifier = None
        if kms_raw:
            kms_configured = json.loads(kms_raw, object_pairs_hook=reject_duplicate_keys)
            if not isinstance(kms_configured, dict) or not kms_configured:
                raise ValueError("empty KMS public key registry")
            registry = KmsPublicKeyRegistry()
            for k_id, k_cfg in kms_configured.items():
                registry.register_public_key(
                    k_id,
                    issuer_id=k_cfg["issuer_id"],
                    source=k_cfg["source"],
                    algorithm=k_cfg["algorithm"],
                    public_key_pem_or_bytes=k_cfg["public_key_pem"],
                    valid_from=datetime.fromisoformat(k_cfg["valid_from"].replace("Z", "+00:00")),
                    valid_until=datetime.fromisoformat(k_cfg["valid_until"].replace("Z", "+00:00")),
                    permitted_purposes=k_cfg.get("permitted_purposes", ("kalman_state_observation", "weather_state_forcing")),
                )
            durable_auth = None
            durable_rev_path = os.getenv("AKALORIS_LAYER0_DURABLE_REVOCATION_PATH", "").strip()
            if (v3_kms_required() or live_revocation_required()) and not durable_rev_path:
                raise Layer0AdmissionRequiredError(
                    "Mandatory v3 KMS policy requires a trusted durable revocation path"
                )
            if durable_rev_path:
                rev_file = Path(durable_rev_path)
                if not rev_file.is_file():
                    raise Layer0AdmissionRequiredError(
                        f"Durable revocation snapshot file not found: {durable_rev_path}"
                    )

                def live_durable_snapshot() -> DurableRevocationSnapshot:
                    d_snap_raw = Path(durable_rev_path).read_text(encoding="utf-8")
                    d_snap_data = json.loads(d_snap_raw, object_pairs_hook=reject_duplicate_keys)
                    return DurableRevocationSnapshot.from_dict(d_snap_data)

                initial_snap = live_durable_snapshot()
                durable_auth = DurableRevocationAuthority(
                    initial_snapshot=initial_snap,
                    snapshot_provider=live_durable_snapshot,
                )
            v3_verifier = V3KmsGrantVerifier(
                registry,
                revocation_authority=durable_auth,
                trusted_zone_registry=zone_registry,
            )

        if v3_verifier and not legacy_verifier:
            return v3_verifier
        if legacy_verifier and not v3_verifier and not v3_kms_required():
            return legacy_verifier
        return UnifiedAdmissionVerifier(
            v3_verifier=v3_verifier,
            legacy_verifier=legacy_verifier,
            enforce_v3_only=v3_kms_required(),
        )
    except (ValueError, TypeError, binascii.Error, UnicodeError, OSError) as exc:
        # Do not propagate or log any raw configuration or secret bytes.
        raise Layer0AdmissionRequiredError(
            "Invalid deployment-provisioned Layer 0 issuer registry"
        ) from None
