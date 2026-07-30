"""Cross-process contract for publication-ready Layer 10 surfaces.

This module deliberately contains no Layer 10 schema imports. Both the API
process and the scientific worker can therefore classify the same serialized
envelope without import-mode dependent behaviour.
"""

from enum import Enum
from typing import Any, Mapping, Tuple


# Old entries did not bind publication authority or scientific run identity.
SURFACES_SCHEMA_VERSION = "v924_bc10_21r5_publication_authority_v1"

# Render authorization contract version — must be present and non-empty on every cached payload.
RENDER_AUTHORIZATION_VERSION = "v924_bc10_18_render_auth_v1"

RENDER_POLICIES = ("satellite", "experimental", "asmae_diagnostic", "hybrid")
RENDER_MODES = (
    "canopy",
    "water",
    "nutrients",
    "salinity",
    "risk",
    "veg_attention",
    "uncertainty",
    "resolution_coverage",
)
RENDER_ROLES = ("base", "overlay", "candidate", "inspector", "dependency")


class PublicationStatus(str, Enum):
    """Exhaustive, fail-closed status of a serialized publication."""

    VALID_NORMAL = "VALID_NORMAL"
    VALID_DEGRADED = "VALID_DEGRADED"
    INVALID_PUBLICATION = "INVALID_PUBLICATION"
    FAILED_PUBLICATION = "FAILED_PUBLICATION"


VALID_PUBLICATION_STATUSES = frozenset(
    {PublicationStatus.VALID_NORMAL.value, PublicationStatus.VALID_DEGRADED.value}
)
ALL_PUBLICATION_STATUSES = frozenset(status.value for status in PublicationStatus)


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _nested(value: Any, *names: str, default: Any = None) -> Any:
    current = value
    for name in names:
        current = _field(current, name, None)
        if current is None:
            return default
    return current


def _non_empty_mapping(value: Any) -> bool:
    return isinstance(value, Mapping) and bool(value)


def classify_surface_publication(payload: Any) -> Tuple[str, str]:
    """Derive status solely from the publication envelope.

    The declared status is ignored during derivation; callers compare it with
    this result. An incomplete envelope therefore cannot authorize itself by
    merely writing a status flag.
    """
    if payload is None:
        return PublicationStatus.FAILED_PUBLICATION.value, "payload_missing"

    explicit_state = str(_field(payload, "status", "") or "").strip().lower()
    layer10_state = str(
        _nested(payload, "layer_results", "layer_10", "status", default="") or ""
    ).strip().lower()
    if explicit_state in {"failed", "error"} or layer10_state in {"failed", "error"}:
        return PublicationStatus.FAILED_PUBLICATION.value, "execution_failed"

    surfaces = _field(payload, "surfaces", None)
    if surfaces is None:
        surfaces = _field(payload, "surface_pack", None)
    if not isinstance(surfaces, (list, tuple)):
        return PublicationStatus.INVALID_PUBLICATION.value, "surfaces_not_a_sequence"
    has_surfaces = bool(surfaces)

    quality = _field(payload, "quality", None)
    if quality is None:
        quality = _field(payload, "quality_report", {})
    provenance = _field(payload, "provenance", {}) or {}
    degradation = str(
        _field(payload, "degradation_mode", "")
        or _field(quality, "degradation_mode", "")
        or _field(provenance, "degradation", "")
        or ""
    )
    if "." in degradation:
        degradation = degradation.rsplit(".", 1)[-1]
    degradation = degradation.upper()
    spatial_short_circuit = bool(
        _field(provenance, "spatial_processing_short_circuited", False)
    )
    terminal_no_data = (
        not has_surfaces
        and (
            _field(payload, "placeholder_only", False) is True
            or explicit_state == "degraded"
            or degradation in {"DATA_GAP", "NO_SPATIAL", "DEGRADED"}
            or spatial_short_circuit
        )
    )
    if not has_surfaces and not terminal_no_data:
        return PublicationStatus.INVALID_PUBLICATION.value, "surface_inventory_empty"

    if _field(payload, "render_authorization_version", "") != RENDER_AUTHORIZATION_VERSION:
        return PublicationStatus.INVALID_PUBLICATION.value, "render_authorization_version_invalid"
    if not _non_empty_mapping(_field(payload, "render_authorizations", None)):
        return PublicationStatus.INVALID_PUBLICATION.value, "render_authorizations_missing"
    if not _non_empty_mapping(_field(payload, "asmae_proof", None)):
        return PublicationStatus.INVALID_PUBLICATION.value, "asmae_proof_missing"
    if not _non_empty_mapping(_field(payload, "mode_display_state", None)):
        return PublicationStatus.INVALID_PUBLICATION.value, "mode_display_state_missing"
    if not _non_empty_mapping(_field(payload, "source_policy_display_state", None)):
        return PublicationStatus.INVALID_PUBLICATION.value, "source_policy_display_state_missing"
    core_asmae = _field(payload, "core_asmae_evidence_state", None) or _field(
        payload, "asmae_evidence_state", None
    )
    if not _non_empty_mapping(core_asmae):
        return PublicationStatus.INVALID_PUBLICATION.value, "core_asmae_evidence_state_missing"
    if not _non_empty_mapping(_field(payload, "publication_surface_state", None)):
        return PublicationStatus.INVALID_PUBLICATION.value, "publication_surface_state_missing"

    publication_id = _field(payload, "publication_id", "") or _field(
        provenance, "publication_id", ""
    )
    publication_run_id = _field(payload, "publication_run_id", "") or _field(
        provenance, "publication_run_id", ""
    )
    scientific_run_id = _field(payload, "run_id", "")
    if not publication_id:
        return PublicationStatus.INVALID_PUBLICATION.value, "publication_id_missing"
    if not publication_run_id or not scientific_run_id:
        return PublicationStatus.INVALID_PUBLICATION.value, "publication_run_identity_missing"
    if str(publication_run_id) != str(scientific_run_id):
        return PublicationStatus.INVALID_PUBLICATION.value, "publication_run_identity_mismatch"

    schema_version = (
        _field(payload, "schema_version", "")
        or _field(payload, "version", "")
        or _field(payload, "surface_schema_version", "")
        or _field(provenance, "surface_schema_version", "")
    )
    if schema_version != SURFACES_SCHEMA_VERSION:
        return PublicationStatus.INVALID_PUBLICATION.value, "surface_schema_version_invalid"

    demotion = _field(payload, "publication_demotion", {}) or {}
    degraded = (
        terminal_no_data
        or explicit_state == "degraded"
        or _field(payload, "placeholder_only", False) is True
        or degradation not in {"", "NORMAL"}
        or _field(demotion, "applied", False) is True
    )
    return (
        PublicationStatus.VALID_DEGRADED.value
        if degraded
        else PublicationStatus.VALID_NORMAL.value,
        "degraded_authoritative_envelope" if degraded else "normal_authoritative_envelope",
    )


def validate_declared_publication_status(payload: Any) -> Tuple[bool, str, str]:
    """Validate that a producer declared exactly the status its envelope earns."""
    derived, reason = classify_surface_publication(payload)
    provenance = _field(payload, "provenance", {}) or {}
    declared = _field(payload, "publication_status", "") or _field(
        provenance, "publication_status", ""
    )
    if declared not in ALL_PUBLICATION_STATUSES:
        return False, derived, "publication_status_missing_or_unknown"
    if declared != derived:
        return False, derived, f"publication_status_mismatch:{declared}!={derived}:{reason}"
    return declared in VALID_PUBLICATION_STATUSES, derived, reason


def build_no_data_render_authorizations() -> dict:
    """Build a complete deny-by-absence matrix for terminal no-data output."""
    return {
        policy: {
            mode: {role: {} for role in RENDER_ROLES}
            for mode in RENDER_MODES
        }
        for policy in RENDER_POLICIES
    }


def build_no_data_mode_display_state(reason: str = "insufficient_evidence") -> dict:
    """Describe unavailable spatial modes without inventing a raster surface."""
    return {
        mode: {
            "displayLevel": "unavailable",
            "authorityLevel": "monitor",
            "selectedSurfaceType": None,
            "isSpatial": False,
            "spatial": False,
            "canRenderPixels": False,
            "renderKind": "none",
            "reason": reason,
            "trustBadges": ["data unavailable"],
        }
        for mode in RENDER_MODES
    }


def build_no_data_source_policy_display_state(
    requested_policy: str = "satellite",
    reason: str = "insufficient_evidence",
) -> dict:
    """Return an explicit provider-outage state with no silent policy fallback."""
    normalized_policy = (
        "asmae_diagnostic" if requested_policy == "asmae" else requested_policy
    )
    if normalized_policy not in RENDER_POLICIES:
        normalized_policy = "satellite"
    return {
        "requested_policy": normalized_policy,
        "resolved_policy": normalized_policy,
        "fallback_reason": reason,
        "materialization_block_reason": reason,
        "one_meter_advisory_coverage_pct": None,
        "one_meter_physics_coverage_pct": None,
        "model_assisted_2_5m_coverage_pct": None,
        "generalized_5m_coverage_pct": None,
        "experimentalVisualLadder": None,
        "asmaeApprovalLadder": {
            "oneMeterAsmaeApprovalPct": None,
            "modelAssisted2_5mPct": None,
            "generalized5mPct": None,
            "unavailableReason": reason,
        },
    }


def build_default_asmae_proof() -> dict:
    """
    Canonical default ASMAE proof structure used when real proof is unavailable.

    Rules:
      - Every degraded/placeholder Layer 10 output MUST use this.
      - Never serialize ``asmae_proof: {}`` — always emit this structure.
      - Downstream components treat an empty asmae_proof as a cache-poisoning signal.
    """
    return {
        "sentinel_proof": {
            "s2_real_scene_count": 0,
            "s1_real_scene_count": 0,
            "proxy_scene_count": 0,
        },
        "weather_proof": {
            "status": "unavailable",
            "daily_count": 0,
        },
        "enkf_proof": {
            "full_enkf_credit_allowed": False,
            "update_mode": "unavailable",
        },
        "bma_proof": {
            "production_bma_valid": False,
        },
        "ml_proof": {
            "ml_production_weight": 0.0,
            "ml_used_for_approval": False,
        },
        "resolution_proof": {
            "field_approved_1m_mask_source": "unavailable",
        },
        "feature_proof": {
            "assimilated": [],
            "missing": ["proof_unavailable"],
        },
    }


# Version history (do not remove — used for gate verification):
# SURFACES_SCHEMA_VERSION = "v924_bc10_1"
# SURFACES_SCHEMA_VERSION = "v924_bc10_3"
# SURFACES_SCHEMA_VERSION = "v924_bc10_4"
# SURFACES_SCHEMA_VERSION = "v924_bc10_5"
# SURFACES_SCHEMA_VERSION = "v924_bc10_6"
# SURFACES_SCHEMA_VERSION = "v924_bc10_7"
# SURFACES_SCHEMA_VERSION = "v924_bc10_11"
# SURFACES_SCHEMA_VERSION = "v924_bc10_12"
# SURFACES_SCHEMA_VERSION = "v924_bc10_17"
# SURFACES_SCHEMA_VERSION = "v924_bc10_18"
# SURFACES_SCHEMA_VERSION = "v924_bc10_19_authority_v1"
