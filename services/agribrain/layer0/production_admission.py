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
