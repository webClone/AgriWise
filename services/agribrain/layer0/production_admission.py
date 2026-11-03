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
    environment = os.getenv(
        "NODE_ENV",
        os.getenv("ENVIRONMENT", os.getenv("ENV", os.getenv("APP_ENV", "development"))),
    ).strip().lower()
    return environment in ("production", "prod", "staging") or (
        os.getenv("AKALORIS_LAYER0_REQUIRE_SIGNED_INPUTS", "")
        .strip().lower() in ("true", "1", "yes")
    )


def require_trusted_verifier(verifier: object) -> None:
    """Reject construction of mandatory production estimator without keyring."""
    if signed_inputs_required() and verifier is None:
        raise Layer0AdmissionRequiredError(
            "Layer 0 signed state-input policy is mandatory but no trusted "
            "source-admission verifier is provisioned"
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
        return PositiveObservationAdmissionVerifier(issuer_keys)
    except (ValueError, TypeError, binascii.Error, UnicodeError) as exc:
        # Do not propagate or log any raw configuration or secret bytes.
        raise Layer0AdmissionRequiredError(
            "Invalid deployment-provisioned Layer 0 issuer registry"
        ) from None
