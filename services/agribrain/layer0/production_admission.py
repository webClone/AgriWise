"""Mandatory state-input authority policy for Layer 0 runtime entrypoints.

The policy is derived from server process configuration, never from a packet,
API body, tenant preference, or source-provided health flags. Production and
staging cannot opt out. Scientific/research compatibility defaults to legacy
unless explicitly enabled by the trusted deployment.
"""
from __future__ import annotations

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


def require_trusted_verifier(verifier: object) -> None:
    """Reject missing keyring or required live revocation authority."""
    if signed_inputs_required() and verifier is None:
        raise Layer0AdmissionRequiredError(
            "Layer 0 signed state-input policy is mandatory but no trusted "
            "source-admission verifier is provisioned"
        )
    if (
        live_revocation_required()
        and not getattr(verifier, "revocation_enforced", False)
    ):
        raise Layer0AdmissionRequiredError(
            "Live issuer revocation policy required but no trusted authority is provisioned"
        )


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

    raw = os.getenv("AKALORIS_LAYER0_ISSUER_KEYS_JSON", "")
    if not raw:
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
        configured = json.loads(raw, object_pairs_hook=reject_duplicate_keys)
        if not isinstance(configured, dict) or not configured:
            raise ValueError("empty issuer registry")
        issuer_keys = {}
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
        if live_revocation_required() and not revocation_path:
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
        return PositiveObservationAdmissionVerifier(
            issuer_keys,
            revocation_gate=gate,
            trusted_zone_registry=zone_registry,
        )
    except (ValueError, TypeError, binascii.Error, UnicodeError, OSError) as exc:
        # Do not propagate or log any raw configuration or secret bytes.
        raise Layer0AdmissionRequiredError(
            "Invalid deployment-provisioned Layer 0 issuer registry"
        ) from None
