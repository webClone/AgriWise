"""Phase 1F: read-only scientific pilot observation gate.

A narrow projection of the *existing, current, server-verified* ASMAE
publication. This does not ingest observations, run ASMAE, create/authorize a
prescription, write publication state, or control irrigation.

The caller must obtain PlotNamespace and expected geometry/cycle/snapshot
from independently authenticated, server-owned state. Do not expose these
parameters directly as public request authority.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from typing import Any

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.orchestrator_v2.pilot_publication_gate import (
    read_trusted_current_asmae_publication,
)
from services.agribrain.scientific_contracts.exceptions import ContractViolation

SIGNED_IRRIGATION_FLAG = "AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION"
_DISABLED_VALUES = frozenset(("", "false", "0", "off", "no"))
_OBSERVATION_MAX_AGE = timedelta(days=7)
SCHEMA_VERSION = "akaloris/pilot/observation-only-readout/v1"


def require_observation_only_runtime() -> None:
    """Fail closed *before any read* when signed delivery might be enabled."""
    value = os.getenv(SIGNED_IRRIGATION_FLAG, "").strip().lower()
    if value not in _DISABLED_VALUES:
        raise ContractViolation("observation_only_pilot_requires_signed_irrigation_disabled")


def _aware_instant(value: Any, label: str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise ContractViolation(f"{label}_invalid") from exc
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ContractViolation(f"{label}_not_utc_aware")
    return value.astimezone(timezone.utc)


def read_observation_only_pilot_status(
    namespace: PlotNamespace,
    *,
    expected_snapshot_id: str,
    expected_geometry_hash: str,
    expected_crop_cycle_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Read one authenticated plot's current ASMAE head; grant *no* authority.

    Reuses the canonical native publication reader (10 validation flags,
    owner/plot/geometry/crop-cycle/snapshot and temporal binding). This is
    an integrity/readability gate, not evidence of independently calibrated
    ground truth or a complete sensor-to-browser integration.
    """
    require_observation_only_runtime()
    if not isinstance(namespace, PlotNamespace) or not namespace.is_valid():
        raise ContractViolation("observation_only_requires_trusted_plot_namespace")
    observed_at = _aware_instant(now if now is not None else datetime.now(timezone.utc), "evaluation_time")
    publication = read_trusted_current_asmae_publication(
        namespace,
        expected_snapshot_id=expected_snapshot_id,
        expected_geometry_hash=expected_geometry_hash,
        expected_crop_cycle_id=expected_crop_cycle_id,
        require_proof_attestation=False,  # L8 proof is NOT an observation prerequisite
    )
    published_at = _aware_instant(publication["published_at"], "publication_time")
    if published_at > observed_at:
        raise ContractViolation("observation_publication_from_future")
    age = observed_at - published_at
    if age < timedelta(0):
        raise ContractViolation("negative_observation_publication_age")

    # Strict output allowlist. Do not return internal L8 plan/actions, signed
    # receipt material, attestation signatures, or any prescription envelope.
    return {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "OBSERVATION_ONLY_READABLE"
            if age <= _OBSERVATION_MAX_AGE
            else "STALE_OBSERVATION_ONLY"
        ),
        "snapshot_kind": "asmae",
        "plot_id": namespace.plot_id,
        "snapshot_id": publication["snapshot_id"],
        "publication_receipt_hash": publication["publication_receipt_hash"],
        "job_manifest_hash": publication["manifest_hash"],
        "evidence_cutoff_at": publication["evidence_cutoff_at"],
        "observation_window": dict(publication["observation_window"]),
        "published_at": publication["published_at"],
        "evaluated_at": observed_at.isoformat(),
        "age_seconds": int(age.total_seconds()),
        "publication_integrity_checked": True,
        "publication_validation_flags_checked": 10,
        "independent_field_accuracy_verified": False,
        "live_sensor_to_asmae_chain_verified": False,
        "real_time_observation_claim": False,
        "signed_irrigation_enabled": False,
        "scientific_publication_authorized": False,
        "actuator_control_authorized": False,
        "machine_execution_allowed": False,
        "requires_confirmation": True,
        "recommendations": [],
        "actions": [],
    }
