"""Cross-process contract for publication-ready Layer 10 surfaces.

This module deliberately contains no Layer 10 schema imports. Both the API
process and the scientific worker can therefore classify the same serialized
envelope without import-mode dependent behaviour.
"""

from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Tuple


# Old entries did not bind publication authority or scientific run identity.
SURFACES_SCHEMA_VERSION = "v925_bc10_24r5_phenology_authority_v2"

# Render authorization contract version — must be present and non-empty on every cached payload.
RENDER_AUTHORIZATION_VERSION = "v924_bc10_22r5_render_identity_v1"

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


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _strict_bool(val: Any) -> Optional[bool]:
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        v = val.strip().lower()
        if v in ("true", "1", "t", "yes", "y"):
            return True
        if v in ("false", "0", "f", "no", "n", ""):
            return False
    return False


def _grid_spec_dict(value: Any) -> Any:
    """Return a JSON-safe grid specification without importing schema types."""
    if value is None or isinstance(value, Mapping):
        return dict(value) if isinstance(value, Mapping) else None
    if hasattr(value, "to_dict"):
        return value.to_dict()
    fields = ("crs", "transform", "width", "height", "bounds", "resolution")
    result = {
        name: getattr(value, name)
        for name in fields
        if getattr(value, name, None) is not None
    }
    return result or None


def _surface_value(surface: Any, provenance: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        value = _field(surface, name, None)
        if value is not None:
            return value
    for name in names:
        value = provenance.get(name)
        if value is not None:
            return value
    return None


def resolve_surface_block_reasons(*sources: Any) -> List[str]:
    """Compute a canonical, deduplicated union of restriction/block reasons across all carriers.

    Preserves insertion order, eliminates duplicates, filters out empty/None values,
    and ensures that no active restriction in any carrier is masked or lost by another carrier.
    """
    seen: set = set()
    result: List[str] = []

    def _add(item: Any) -> None:
        if item is None:
            return
        if isinstance(item, (list, tuple, set)):
            for sub in item:
                _add(sub)
            return
        s = str(item).strip()
        if s and s not in seen:
            seen.add(s)
            result.append(s)

    for src in sources:
        if src is None:
            continue
        if isinstance(src, Mapping):
            for key in (
                "block_reasons",
                "blockReasons",
                "restriction_reasons",
                "restrictionReasons",
                "exclusion_reason",
                "exclusionReason",
            ):
                val = src.get(key)
                if val is not None:
                    _add(val)
            nested_prov = src.get("provenance")
            if isinstance(nested_prov, Mapping):
                for key in (
                    "block_reasons",
                    "blockReasons",
                    "restriction_reasons",
                    "restrictionReasons",
                    "exclusion_reason",
                    "exclusionReason",
                ):
                    val = nested_prov.get(key)
                    if val is not None:
                        _add(val)
        elif isinstance(src, (list, tuple, set)):
            for item in src:
                _add(item)
        elif hasattr(src, "block_reasons") or hasattr(src, "provenance"):
            attr_blocks = getattr(src, "block_reasons", None)
            if attr_blocks is not None:
                _add(attr_blocks)
            prov = getattr(src, "provenance", None)
            if isinstance(prov, Mapping):
                for key in (
                    "block_reasons",
                    "blockReasons",
                    "restriction_reasons",
                    "restrictionReasons",
                    "exclusion_reason",
                    "exclusionReason",
                ):
                    val = prov.get(key)
                    if val is not None:
                        _add(val)
        else:
            _add(src)

    return result


def serialize_surface_artifact(surface: Any) -> dict:
    """Serialize one surface with mandatory immutable artifact identity.

    This is the sole serializer used by both normal Layer 10 responses and
    canonical ASMAE reintegration. Missing identity is a producer error; a
    consumer must never derive it from semantic type, ordering, or provenance.
    """
    surface_id = str(_field(surface, "surface_id", "") or "").strip()
    if not surface_id:
        raise ValueError("Layer 10 surface is missing mandatory surface_id")
    semantic_type = str(_enum_value(_field(surface, "semantic_type", "")) or "").strip()
    if not semantic_type:
        raise ValueError(f"Layer 10 surface {surface_id!r} is missing semantic_type")
    provenance = _field(surface, "provenance", {}) or {}
    if not isinstance(provenance, Mapping):
        raise ValueError(f"Layer 10 surface {surface_id!r} provenance is not a mapping")
    surface_role = _surface_value(surface, provenance, "surface_role", "surfaceRole")
    if not surface_role:
        surface_role = (
            "render_dependency"
            if semantic_type in {
                "OBSERVED_DATA_MASK_NDVI",
                "GAP_FILL_MASK_NDVI",
                "VALID_DATA_MASK_NDVI",
            }
            else "agronomic_surface"
        )
    grounding_class_val = str(_enum_value(_field(surface, "grounding_class", None)) or "UNIFORM")
    # Restrictive consistency: default permissions to False, intersect ceilings and restrictions
    block_reasons_raw = _surface_value(surface, provenance, "block_reasons", "blockReasons") or []
    restriction_reasons_raw = _surface_value(surface, provenance, "restriction_reasons", "restrictionReasons") or []
    exclusion_reason_raw = _surface_value(surface, provenance, "exclusion_reason", "exclusionReason")
    authority_block_reason = _surface_value(
        surface, provenance, "authority_block_reason", "authorityBlockReason"
    )
    all_restrictions = []
    for r in (block_reasons_raw, restriction_reasons_raw):
        if isinstance(r, (list, tuple, set)):
            all_restrictions.extend(str(item) for item in r if item)
        elif isinstance(r, str) and r:
            all_restrictions.append(r)
    if exclusion_reason_raw:
        all_restrictions.append(str(exclusion_reason_raw))
    if authority_block_reason:
        all_restrictions.append(str(authority_block_reason))
    has_restrictions = len(all_restrictions) > 0

    attr_state_update = _strict_bool(_field(surface, "state_update_allowed", None))
    prov_state_update = _strict_bool(provenance.get("state_update_allowed"))
    prov_camel_state = _strict_bool(provenance.get("stateUpdateAllowed"))
    state_candidates = [c for c in (attr_state_update, prov_state_update, prov_camel_state) if c is not None]

    if False in state_candidates or has_restrictions or grounding_class_val == "INTERPOLATED_PROXY":
        state_update_allowed = False
    elif True in state_candidates:
        state_update_allowed = True
    else:
        state_update_allowed = False

    attr_prescription = _strict_bool(_field(surface, "prescription_driver_allowed", None))
    prov_prescription = _strict_bool(provenance.get("prescription_driver_allowed"))
    prov_camel_presc = _strict_bool(provenance.get("prescriptionDriverAllowed"))
    presc_candidates = [c for c in (attr_prescription, prov_prescription, prov_camel_presc) if c is not None]

    if False in presc_candidates or has_restrictions or grounding_class_val == "INTERPOLATED_PROXY":
        prescription_driver_allowed = False
    elif True in presc_candidates:
        prescription_driver_allowed = True
    else:
        prescription_driver_allowed = False

    authority_ceiling = str(
        _surface_value(surface, provenance, "authority_ceiling", "authorityCeiling") or ""
    ).upper()
    if authority_ceiling in ("VISUALIZATION", "MONITORING_ONLY", "DIAGNOSTIC"):
        state_update_allowed = False
        prescription_driver_allowed = False
    elif authority_ceiling == "STATE_UPDATE":
        prescription_driver_allowed = False

    if grounding_class_val == "INTERPOLATED_PROXY":
        state_update_allowed = False
        prescription_driver_allowed = False
        if not authority_block_reason:
            authority_block_reason = (
                "INTERPOLATED_PROXY surfaces have an authority ceiling and cannot drive state updates or variable-rate prescriptions"
            )

    doc = {
        "surface_id": surface_id,
        "type": semantic_type,
        "semantic_type": semantic_type,
        "values": _field(surface, "values", []) or [],
        "grounding_class": grounding_class_val,
        "raster_basis": list(_field(surface, "raster_basis", []) or []),
        "observed_ratio": float(_field(surface, "observed_ratio", 0.0) or 0.0),
        "native_resolution_m": float(_surface_value(surface, provenance, "native_resolution_m", "nativeResolutionM") or 10.0),
        "display_resolution_m": float(_surface_value(surface, provenance, "display_resolution_m", "displayResolutionM") or 1.0),
        "effective_resolution_m": float(_surface_value(surface, provenance, "effective_resolution_m", "effectiveResolutionM") or 10.0),
        "observed_mask": _surface_value(surface, provenance, "observed_mask", "observedMask"),
        "inferred_mask": _surface_value(surface, provenance, "inferred_mask", "inferredMask"),
        "units": _field(surface, "units", "") or "",
        "render_range": list(_field(surface, "render_range", [0, 1]) or [0, 1]),
        "palette_id": _enum_value(_field(surface, "palette_id", "viridis")),
        "source_layers": list(_field(surface, "source_layers", []) or []),
        "provenance": dict(provenance),
        "grid_spec": _grid_spec_dict(_field(surface, "grid_spec", None)),
        "render_kind": _surface_value(surface, provenance, "render_kind", "renderKind"),
        "display_level": _surface_value(surface, provenance, "display_level", "displayLevel"),
        "display_grid_spec": _grid_spec_dict(
            _surface_value(surface, provenance, "display_grid_spec", "displayGridSpec")
        ),
        "source_grid_spec": _grid_spec_dict(
            _surface_value(surface, provenance, "source_grid_spec", "sourceGridSpec")
        ),
        "source_reality": _surface_value(surface, provenance, "source_reality", "sourceReality"),
        "diagnostic_only": _surface_value(surface, provenance, "diagnostic_only", "diagnosticOnly"),
        "state_update_allowed": state_update_allowed,
        "prescription_driver_allowed": prescription_driver_allowed,
        "confidence": _surface_value(surface, provenance, "confidence"),
        "uncertainty": _surface_value(surface, provenance, "uncertainty"),
        "authority_block_reason": authority_block_reason,
        "surface_role": surface_role,
        "grid_ref": _field(surface, "grid_ref", None),
        "cog_ref": _field(surface, "cog_ref", None),
        "tile_ref": _field(surface, "tile_ref", None),
        "stac_item_ref": _field(surface, "stac_item_ref", None),
    }

    combined_blocks = resolve_surface_block_reasons(
        _field(surface, "block_reasons", None),
        _field(surface, "blockReasons", None),
        provenance,
    )
    if combined_blocks:
        doc["block_reasons"] = list(combined_blocks)

    return doc


def serialize_surface_pack(surfaces: Any) -> List[dict]:
    """Serialize a collection or sequence of surface artifacts."""
    if surfaces is None:
        return []
    if isinstance(surfaces, Mapping):
        surfaces = surfaces.values()
    return [serialize_surface_artifact(s) for s in surfaces]


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
    surface_ids = []
    for surface in surfaces:
        surface_id = str(_field(surface, "surface_id", "") or "").strip()
        if not surface_id:
            return PublicationStatus.INVALID_PUBLICATION.value, "surface_id_missing"
        surface_ids.append(surface_id)
    if len(surface_ids) != len(set(surface_ids)):
        return PublicationStatus.INVALID_PUBLICATION.value, "surface_id_duplicate"

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
    comp_failures = _field(quality, "component_failures", []) or []
    degradation_codes = _field(quality, "degradation_codes", []) or []
    phenology_context = _field(payload, "phenology_context", {}) or {}
    resolved_crop_stage = str(
        _field(payload, "resolved_crop_stage", "")
        or _field(phenology_context, "resolved_crop_stage", "")
        or ""
    ).strip().upper()
    # UNKNOWN is a valid, truthful publication state.  NDVI or a declared crop
    # must never force a phenology inference.  Conversely, a known stage must
    # carry the canonical Layer-2 receipt and its authority.
    if resolved_crop_stage not in {"", "UNKNOWN", "UNDEFINED"}:
        phenology_source = str(_field(phenology_context, "phenology_source", ""))
        phenology_authority = str(
            _field(phenology_context, "phenology_authority", "")
            or _field(phenology_context, "phenology_evidence_class", "")
        ).lower()
        phenology_hash = str(
            _field(phenology_context, "phenology_posterior_hash", "")
        ).lower()
        if (
            phenology_source != "layer2_canonical_phenology"
            or phenology_authority not in {"diagnostic", "calibrated"}
            or len(phenology_hash) != 64
            or any(ch not in "0123456789abcdef" for ch in phenology_hash)
            or _field(phenology_context, "phenology_receipt_valid", True) is not True
        ):
            return PublicationStatus.INVALID_PUBLICATION.value, "phenology_receipt_invalid"
    has_materialization_failure = any(
        (isinstance(f, dict) and f.get("component") == "asmae_spatial_materialization")
        or (hasattr(f, "component") and getattr(f, "component") == "asmae_spatial_materialization")
        for f in comp_failures
    ) or "ASMAE_SURFACE_MATERIALIZATION_FAILED" in degradation_codes

    degraded = (
        terminal_no_data
        or explicit_state == "degraded"
        or _field(payload, "placeholder_only", False) is True
        or degradation not in {"", "NORMAL"}
        or _field(demotion, "applied", False) is True
        or has_materialization_failure
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



ALL_CANONICAL_SURFACES = (
    "NDVI_CLEAN", "NDVI_DEVIATION", "BASELINE_ANOMALY",
    "WATER_STRESS_PROB", "NUTRIENT_STRESS_PROB", "SALINITY_STRESS",
    "COMPOSITE_RISK", "DATA_RELIABILITY", "DATA_CONFIDENCE", "UNCERTAINTY_SIGMA",
    "RESOLUTION_COVERAGE", "GAP_FILL_MASK",
    "CANOPY_ASMAE_VIGOR", "WATER_ASMAE_CANOPY_WATER", "WATER_ASMAE_ROOT_ZONE_WATER",
    "NUTRIENT_ASMAE_CHLOROPHYLL_PROXY", "SALINITY_ASMAE_STRESS", "RISK_ASMAE_DIAGNOSTIC",
    "ASMAE_POSTERIOR_CONCENTRATION", "RESOLUTION_ASMAE_EFFECTIVE", "ASMAE_VISUAL_FUSION_CANOPY",
    "COMPOSITE_ADVISORY_CANOPY", "COMPOSITE_VEG_ATTENTION",
    "COMPOSITE_WATER_SUPPORT", "COMPOSITE_NUTRIENT_SUPPORT",
    "COMPOSITE_SALINITY_STRESS", "COMPOSITE_RISK_DIAGNOSTIC",
    "COMPOSITE_CONFIDENCE", "COMPOSITE_EFFECTIVE_RESOLUTION",
    "COMPOSITE_TEXTURE_DETAIL",
    "NDVI_CLEAN_EXPERIMENTAL_FINE_DETAIL",
    "EXPERIMENTAL_VISUAL_CANOPY",
    "EXPERIMENTAL_VISUAL_CANOPY_HIGHRES",
    "EXPERIMENTAL_TEXTURE_SUPPORT_MASK",
    "EXPERIMENTAL_STRICT_FINE_DETAIL_CANDIDATE_MASK",
    "EXPERIMENTAL_TEXTURE_CONFIDENCE",
    "EXPERIMENTAL_GAPFILL_MASK",
    "EXPERIMENTAL_PARENT_MEAN_ERROR",
    "COMPOSITE_ARCHIVE_SUPPORT",
    "COMPOSITE_RETRO_SCORE",
    "COMPOSITE_ML_SUPPORT",
    "COMPOSITE_BMA_DISAGREEMENT",
    "COMPOSITE_UNCERTAINTY",
    # ASMAE 13 Canonical State Surfaces
    "ASMAE_VIGOR",
    "ASMAE_LAI",
    "ASMAE_CHLOROPHYLL",
    "ASMAE_CANOPY_WATER",
    "ASMAE_ROOT_ZONE_WATER",
    "ASMAE_SURFACE_WETNESS_EVENT",
    "ASMAE_STRUCTURE",
    "ASMAE_BARE_SOIL",
    "ASMAE_SALINITY_STRESS",
    "ASMAE_THERMAL_STRESS",
    "ASMAE_BIOTIC_CONFOUNDER_RISK",
    "ASMAE_PHENOLOGY_PROGRESS",
    "ASMAE_STRESS_MEMORY",
)


def build_no_data_surface_inventory(reason: str = "insufficient_evidence") -> dict:
    """Return explicit missing status for all known surfaces in no-data/terminal envelopes."""
    return {
        st: {
            "surfaceType": st,
            "status": "missing",
            "reason": reason,
        }
        for st in ALL_CANONICAL_SURFACES
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
