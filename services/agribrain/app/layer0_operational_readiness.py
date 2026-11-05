"""B2B-08C-I: sanitized, authenticated Layer 0 operational readiness.

This is a non-mutating readiness signal. A successful topology check cannot
replace the live Mongo transaction, signed HTTP assessment, field calibration,
HSM service qualification, or publication/actuator release gates.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from types import SimpleNamespace
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from services.agribrain.app.internal_service_auth import require_internal_service_request
from services.agribrain.app.production_delivery_runtime import (
    _truth_flag, verified_irrigation_enabled,
)
from services.agribrain.app.scoped_packet_run import signed_packet_run_enabled
from services.agribrain.layer0.production_admission import (
    signed_inputs_required, v3_kms_required, live_revocation_required,
)

router = APIRouter()


def _mongo_checks(database: Any) -> tuple[bool, bool]:
    """Read-only ping and supported session topology; NOT a transaction test."""
    if database is None:
        return False, False
    try:
        database.command("ping")
    except Exception:
        return False, False
    try:
        hello = database.command("hello")
        topology = (
            isinstance(hello, dict)
            and (bool(hello.get("setName")) or hello.get("msg") == "isdbgrid")
            and type(hello.get("logicalSessionTimeoutMinutes")) is int
            and hello["logicalSessionTimeoutMinutes"] > 0
            and callable(getattr(getattr(database, "client", None), "start_session", None))
        )
        return True, topology
    except Exception:
        return True, False


def _active_public_key_authority(registry: Any, authority: Any, now: datetime,
                                 required_purposes: tuple[str, ...]) -> bool:
    """Check active public verification keys with fresh live revocation.

    Key IDs, key bytes, revisions and ledger errors must never leave this
    function. Every purpose needs at least one currently valid authority.
    """
    from services.agribrain.layer0.durable_revocation_authority import (
        DurableRevocationAuthority,
    )
    from services.agribrain.layer0.v3_kms_signed_issuer import KmsPublicKeyRegistry

    if (not isinstance(registry, KmsPublicKeyRegistry)
            or not isinstance(authority, DurableRevocationAuthority)):
        return False
    entries = getattr(registry, "_entries", None)
    if not isinstance(entries, dict) or not entries:
        return False
    for purpose in required_purposes:
        if not any(
            purpose in entry.permitted_purposes
            and entry.is_valid_at(now)
            and authority.check_authority(key_id, now)[0]
            for key_id, entry in entries.items()
        ):
            return False
    return True


def _source_trust_ready(verifier: Any, now: datetime) -> bool:
    from services.agribrain.layer0.v3_kms_signed_issuer import V3KmsGrantVerifier
    from services.agribrain.layer0.v3_state_admission import UnifiedAdmissionVerifier
    from services.agribrain.layer0.positive_observation_admission import (
        GRANT_PURPOSE, WEATHER_GRANT_PURPOSE,
    )
    if isinstance(verifier, UnifiedAdmissionVerifier):
        if not verifier.enforces_v3_only:
            return False
        verifier = verifier.v3_verifier
    if not isinstance(verifier, V3KmsGrantVerifier):
        return False
    return _active_public_key_authority(
        verifier.registry, verifier._revocation, now,
        (GRANT_PURPOSE, WEATHER_GRANT_PURPOSE),
    )


def _delivery_trust_ready(verifier: Any, database: Any,
                          now: datetime) -> bool:
    from services.agribrain.layer0.verified_irrigation_contract import (
        VERIFIED_IRRIGATION_PURPOSE, VerifiedDeliveredIrrigationVerifier,
    )
    from services.agribrain.layer0.mongo_irrigation_idempotency import (
        MongoIrrigationIdempotencyStore,
    )
    if not isinstance(verifier, VerifiedDeliveredIrrigationVerifier):
        return False
    store = verifier.idempotency_store
    # Prevent a superficially healthy verifier that points to a different
    # database or a non-transactional in-memory store.
    if (not isinstance(store, MongoIrrigationIdempotencyStore)
            or getattr(store, "_db", None) is not database):
        return False
    return _active_public_key_authority(
        verifier.public_key_registry, verifier.revocation_authority, now,
        (VERIFIED_IRRIGATION_PURPOSE,),
    )


def assess_layer0_operational_readiness(
    app: Any, database: Any, *, now: datetime | None = None,
) -> dict[str, Any]:
    """Allowlisted status only. No exceptions, paths, secrets or identities."""
    if now is None:
        now = datetime.now(timezone.utc)
    state = getattr(app, "state", SimpleNamespace())
    connected, topology = _mongo_checks(database)

    try:
        required_policy = (
            signed_inputs_required()
            and v3_kms_required()
            and live_revocation_required()
            and _truth_flag(
                os.getenv("AKALORIS_LAYER0_REQUIRE_PLOT_SCOPE"),
                "AKALORIS_LAYER0_REQUIRE_PLOT_SCOPE",
            )
        )
        packet_enabled = signed_packet_run_enabled()
        delivery_enabled = verified_irrigation_enabled()
    except Exception:
        required_policy = False
        packet_enabled = False
        delivery_enabled = False

    ownership = (
        callable(getattr(
            getattr(state, "layer0_packet_ownership_store", None),
            "get_active_plot", None,
        ))
    )
    source_ok = False
    delivery_ok = False
    # Source and L3 trust roots must be evaluated at request time, not
    # assumed valid because they passed the process startup gate.
    if required_policy and packet_enabled and ownership:
        try:
            source_ok = _source_trust_ready(
                getattr(state, "layer0_positive_admission_verifier", None),
                now,
            )
        except Exception:
            source_ok = False
    if required_policy and delivery_enabled and topology:
        try:
            delivery_ok = _delivery_trust_ready(
                getattr(state, "layer0_verified_irrigation_verifier", None),
                database, now,
            )
        except Exception:
            delivery_ok = False

    status = {
        "mongo_connection": "ready" if connected else "unavailable",
        "mongo_transaction_topology": "ready" if topology else "unavailable",
        "signed_scope_policy": "ready" if required_policy else "unavailable",
        "plot_ownership": "ready" if ownership else "unavailable",
        "scoped_packet_runtime": (
            "disabled" if not packet_enabled else
            "ready" if source_ok else "unavailable"
        ),
        "verified_delivery_runtime": (
            "disabled" if not delivery_enabled else
            "ready" if delivery_ok else "unavailable"
        ),
        "source_live_revocation": "ready" if source_ok else "unavailable",
        "delivery_live_revocation": "ready" if delivery_ok else "unavailable",
    }
    ready = all(value == "ready" for value in status.values())
    return {
        "contract": "layer0-b2b08c-readiness-v1",
        "ready": ready,
        "components": status,
        "mongo_transaction_executed": False,
        "field_calibration_qualified": False,
        "scientific_publication_authorized": False,
        "actuator_control_authorized": False,
    }


@router.get("/v2/b2b08/internal/readiness", include_in_schema=False)
def internal_layer0_readiness(
    request: Request,
    response: Response,
    _namespace: Any = Depends(require_internal_service_request),
):
    """HMAC-signed internal service only; never allow unsigned dev fallback."""
    if not request.headers.get("X-AgriBrain-Signature"):
        raise HTTPException(status_code=401, detail="signed_internal_request_required")
    response.headers["Cache-Control"] = "no-store"
    try:
        from app.mongo_client import get_db
        database = get_db()
    except Exception:
        database = None
    report = assess_layer0_operational_readiness(request.app, database)
    if not report["ready"]:
        response.status_code = 503
    return report
