"""Authoritative terminal Layer 10 publication envelopes."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional

from .schema import (
    HistogramBundle,
    Layer10Output,
    QualityReport,
    RenderManifest,
    SIREDegradation,
)
from .surface_contract import (
    SURFACES_SCHEMA_VERSION,
    build_default_asmae_proof,
    build_no_data_mode_display_state,
    build_no_data_render_authorizations,
    build_no_data_source_policy_display_state,
    classify_surface_publication,
)


def build_terminal_no_data_output(
    *,
    run_id: str,
    request_run_id: str,
    timestamp: str,
    reason: str,
    geometry_hash: Optional[str] = None,
    source_policy: str = "satellite",
    input_run_ids: Optional[Dict[str, Any]] = None,
    core_asmae_evidence_state: Optional[Dict[str, Any]] = None,
) -> Layer10Output:
    """Build a complete VALID_DEGRADED no-spatial publication."""
    scientific_run_id = str(run_id)
    publication_seed = "|".join((
        scientific_run_id,
        str(request_run_id),
        str(geometry_hash or ""),
        str(reason),
        SURFACES_SCHEMA_VERSION,
    ))
    publication_id = "pub_" + hashlib.sha256(
        publication_seed.encode("utf-8"),
    ).hexdigest()[:20]
    core_state = dict(core_asmae_evidence_state or {})
    core_state.update({
        "status": core_state.get("status", "unavailable"),
        "production_usable": False,
        "scientific_surface_allowed": False,
        "spatial_materialization_allowed": False,
        "spatial_materialization_block_reason": reason,
    })
    output = Layer10Output(
        run_id=scientific_run_id,
        publication_run_id=scientific_run_id,
        request_run_id=str(request_run_id),
        publication_id=publication_id,
        surface_schema_version=SURFACES_SCHEMA_VERSION,
        timestamp=timestamp,
        input_run_ids=dict(input_run_ids or {}),
        surface_pack=[],
        zone_pack=[],
        micro_objects=[],
        histogram_bundle=HistogramBundle(),
        render_manifest=RenderManifest(available_modes=[]),
        canonical_geometry_hash=geometry_hash,
        source_geometry_hash=geometry_hash,
        quality_report=QualityReport(
            degradation_mode=SIREDegradation.DATA_GAP,
            reliability_score=0.0,
            surfaces_generated=0,
            surfaces_skipped=0,
            zones_generated=0,
            micro_objects_detected=0,
            grid_alignment_ok=False,
            detail_conservation_ok=False,
            warnings=[reason],
        ),
        provenance={
            "status": "degraded",
            "pipeline": "SIRE_terminal_publication_v1",
            "degradation": SIREDegradation.DATA_GAP.value,
            "degradation_mode": SIREDegradation.DATA_GAP.value,
            "warning_codes": [reason],
            "rendered_scientific_surfaces": 0,
            "placeholder_only": True,
            "spatial_processing_short_circuited": True,
            "spatial_processing_block_reason": reason,
            "surface_schema_version": SURFACES_SCHEMA_VERSION,
            "publication_run_id": scientific_run_id,
            "request_run_id": str(request_run_id),
            "publication_id": publication_id,
        },
        mode_display_state=build_no_data_mode_display_state(reason),
        source_policy_display_state=build_no_data_source_policy_display_state(
            source_policy, reason,
        ),
        asmae_evidence_state=dict(core_state),
        core_asmae_evidence_state=dict(core_state),
        publication_surface_state={
            "state": "terminal_no_spatial_publication",
            "authority": "display_inventory_only",
            "surface_available": False,
            "reason": reason,
        },
        publication_demotion={
            "applied": True,
            "reason": reason,
            "publication_state": "terminal_no_spatial_publication",
        },
        surface_behavior_proof={
            "active_surface_type": None,
            "active_policy": source_policy,
            "source_signal_used": None,
            "target_shape": None,
            "native_resolution_m": None,
            "finite_pct": 0.0,
        },
        display_trace={
            "requested_policy": source_policy,
            "resolved_policy": source_policy,
            "active_surface_type_backend": None,
            "available_surface_types": [],
            "experimental_visual_surface_used": None,
        },
        asmae_proof=build_default_asmae_proof(),
        render_authorizations=build_no_data_render_authorizations(),
    )
    output.placeholder_only = True
    status, _ = classify_surface_publication(output)
    output.publication_status = status
    output.provenance["publication_status"] = status
    return output
