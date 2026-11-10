"""
Layer 1 → Layer 2 Output Adapter.

Builds Layer2InputContext from Layer1ContextPackage.
Layer 2 should NOT need raw Layer 0 packages.

Provides:
- 7 feature-group dicts with fused values, confidence, uncertainty, source IDs
- Conflicts and gaps (preserved, not hidden)
- Confidence and uncertainty maps per feature group
- Spatial index reference
- Data health score
- Provenance reference
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional

from layer1_fusion.schemas import (
    DataHealthScore,
    EvidenceConflict,
    EvidenceGap,
    FusedFeature,
    Layer1ContextPackage,
    Layer2InputContext,
)


def _extract_asmae_features(pkg: Layer1ContextPackage) -> Dict[str, Any]:
    """Collect all ASMAE features into a dedicated dictionary."""
    from rollout.rollout_policy import should_run_asmae
    if not should_run_asmae(pkg.plot_id):
        return {}
    import json
    groups = [
        pkg.fused_features.water_context,
        pkg.fused_features.vegetation_context,
        pkg.fused_features.phenology_context,
        pkg.fused_features.stress_evidence_context,
        pkg.fused_features.soil_site_context,
        pkg.fused_features.operational_context,
        pkg.fused_features.data_quality_context,
    ]
    
    # 1. Parse global ASMAE_DIAGNOSTICS if present
    asmae_diag = {}
    for g in groups:
        for ff in g:
            if ff.name == "ASMAE_DIAGNOSTICS":
                val = ff.value
                if val and isinstance(val, str):
                    try:
                        asmae_diag = json.loads(val)
                    except Exception:
                        pass
                break

    # 2. Map raster_refs by uppercase variable name
    raster_map = {}
    if pkg.spatial_index and pkg.spatial_index.raster_refs:
        for r in pkg.spatial_index.raster_refs:
            if r.variable:
                raster_map[r.variable.upper()] = r

    asmae_features = {}
    for g in groups:
        for ff in g:
            if ff.name.upper().startswith("ASMAE_"):
                name = ff.name.upper()
                if name.endswith("_EVIDENCE"):
                    name = name[:-9]
                
                # Defaults
                resolution_m = 10.0
                asmae_channel = "diagnostic"
                c_hash = None
                a_hash = None
                source_basis = "asmae"
                source_run_id = None
                source_schema_version = None
                retro_status = asmae_diag.get("retro_status")
                bma_status = asmae_diag.get("bma_status")
                bma_disagreement = asmae_diag.get("bma_mean_disagreement", asmae_diag.get("bma_disagreement", 0.0))
                cross_layer_conflict = asmae_diag.get("cross_layer_conflict", 0.0)

                # Look up from matching RasterRef (matching variable name)
                ref = None
                for k, r in raster_map.items():
                    if k == name or k == f"ASMAE_{name}" or name == f"ASMAE_{k}" or k.replace("ASMAE_", "") == name.replace("ASMAE_", ""):
                        ref = r
                        break

                if ref:
                    resolution_m = ref.resolution_m
                    asmae_channel = ref.asmae_channel
                    c_hash = ref.content_hash
                    a_hash = ref.artifact_instance_hash
                    source_basis = ref.source_basis
                    source_run_id = ref.source_run_id
                    source_schema_version = ref.source_schema_version
                    retro_status = getattr(ref, "retro_status", retro_status) or retro_status
                    bma_status = getattr(ref, "bma_status", bma_status) or bma_status
                    bma_disagreement = getattr(ref, "bma_disagreement", bma_disagreement) or bma_disagreement
                    cross_layer_conflict = getattr(ref, "cross_layer_conflict", cross_layer_conflict) or cross_layer_conflict

                asmae_features[name] = {
                    "value": ff.value,
                    "unit": ff.unit,
                    "confidence": round(ff.confidence, 3),
                    "uncertainty": round(ff.uncertainty, 4) if ff.uncertainty is not None else None,
                    "freshness": round(ff.freshness, 3),
                    "spatial_scope": ff.spatial_scope,
                    "scope_id": ff.scope_id,
                    "source_count": len(ff.source_evidence_ids),
                    "source_weights": ff.source_weights,
                    "conflict_status": ff.conflict_status,
                    "diagnostic_only": ff.diagnostic_only,
                    "state_update_allowed": bool(getattr(ff, "state_update_allowed", False)),
                    "flags": ff.flags,
                    "resolution_m": resolution_m,
                    "asmae_channel": asmae_channel,
                    "content_hash": c_hash,
                    "artifact_instance_hash": a_hash,
                    "source_basis": source_basis,
                    "source_run_id": source_run_id,
                    "source_schema_version": source_schema_version,
                    "retro_status": retro_status,
                    "bma_status": bma_status,
                    "bma_disagreement": float(bma_disagreement or 0.0),
                    "cross_layer_conflict": float(cross_layer_conflict or 0.0),
                }
    return asmae_features


def build_layer2_context(pkg: Layer1ContextPackage) -> Layer2InputContext:
    """Build the Layer 2 input payload from a Layer 1 context package.

    Layer 2 receives:
    - 7 feature-group dicts with fused values, confidence, uncertainty, source IDs (excluding ASMAE)
    - Dedicate asmae_features dict for ASMAE variables
    - Conflicts and gaps (preserved, not hidden)
    - Confidence + uncertainty maps per feature group
    - Spatial index reference
    - Data health score
    - Provenance reference
    """
    # Collect all diagnostic-only features across all groups
    groups = [
        pkg.fused_features.water_context,
        pkg.fused_features.vegetation_context,
        pkg.fused_features.phenology_context,
        pkg.fused_features.stress_evidence_context,
        pkg.fused_features.soil_site_context,
        pkg.fused_features.operational_context,
        pkg.fused_features.data_quality_context,
    ]
    diag_vals = {}
    for g in groups:
        diag_vals.update(_features_to_dict(g, include_diagnostic=True))

    asmae_features = _extract_asmae_features(pkg)

    return Layer2InputContext(
        plot_id=pkg.plot_id,
        crop_context=None,  # Populated by orchestrator

        water_context=_features_to_dict(pkg.fused_features.water_context, include_diagnostic=False),
        vegetation_context=_features_to_dict(pkg.fused_features.vegetation_context, include_diagnostic=False),
        phenology_context=_features_to_dict(pkg.fused_features.phenology_context, include_diagnostic=False),
        stress_evidence_context=_features_to_dict(pkg.fused_features.stress_evidence_context, include_diagnostic=False),
        soil_site_context=_features_to_dict(pkg.fused_features.soil_site_context, include_diagnostic=False),
        operational_context=_features_to_dict(pkg.fused_features.operational_context, include_diagnostic=False),
        data_quality_context=_features_to_dict(pkg.fused_features.data_quality_context, include_diagnostic=False),
        diagnostic_values=diag_vals,
        asmae_features=asmae_features,

        conflicts=pkg.conflicts,
        gaps=pkg.gaps,
        confidence=_build_confidence_map(pkg),
        uncertainty=_build_uncertainty_map(pkg),
        provenance_ref=pkg.provenance.run_id,
        spatial_index_ref=pkg.spatial_index,
        data_health=pkg.diagnostics.data_health,
    )


def _features_to_dict(features: List[FusedFeature], include_diagnostic: bool = False) -> Dict[str, Any]:
    """Convert fused features to a queryable dict, separating diagnostic-only ones.
    
    Downstream safety: strictly blocks raw ASMAE features from being directly exposed.
    """
    result: Dict[str, Any] = {}
    for ff in features:
        if ff.name.upper().startswith("ASMAE_") and ff.name.upper() != "ASMAE_DIAGNOSTICS":
            continue
        if ff.diagnostic_only != include_diagnostic:
            continue
        result[ff.name] = {
            "value": ff.value,
            "unit": ff.unit,
            "confidence": round(ff.confidence, 3),
            "uncertainty": round(ff.uncertainty, 4) if ff.uncertainty is not None else None,
            "freshness": round(ff.freshness, 3),
            "spatial_scope": ff.spatial_scope,
            "scope_id": ff.scope_id,
            "source_count": len(ff.source_evidence_ids),
            "source_weights": ff.source_weights,
            "source_evidence_ids": list(ff.source_evidence_ids),
            "conflict_status": ff.conflict_status,
            "diagnostic_only": ff.diagnostic_only,
            "flags": ff.flags,
        }
    return result


def _build_confidence_map(pkg: Layer1ContextPackage) -> Dict[str, float]:
    """Build per-group average confidence map."""
    groups = {
        "water": pkg.fused_features.water_context,
        "vegetation": pkg.fused_features.vegetation_context,
        "phenology": pkg.fused_features.phenology_context,
        "stress_evidence": pkg.fused_features.stress_evidence_context,
        "soil_site": pkg.fused_features.soil_site_context,
        "operational": pkg.fused_features.operational_context,
        "data_quality": pkg.fused_features.data_quality_context,
    }
    result: Dict[str, float] = {}
    for name, features in groups.items():
        if features:
            avg = sum(f.confidence for f in features) / len(features)
            result[name] = round(avg, 3)
        else:
            result[name] = 0.0
    return result


def _build_uncertainty_map(pkg: Layer1ContextPackage) -> Dict[str, float]:
    """Build per-group average uncertainty map.

    Only includes groups where at least one feature has a non-None uncertainty.
    """
    groups = {
        "water": pkg.fused_features.water_context,
        "vegetation": pkg.fused_features.vegetation_context,
        "phenology": pkg.fused_features.phenology_context,
        "stress_evidence": pkg.fused_features.stress_evidence_context,
        "soil_site": pkg.fused_features.soil_site_context,
        "operational": pkg.fused_features.operational_context,
    }
    result: Dict[str, float] = {}
    for name, features in groups.items():
        unc_vals = [f.uncertainty for f in features if f.uncertainty is not None]
        if unc_vals:
            result[name] = round(sum(unc_vals) / len(unc_vals), 4)
    return result

