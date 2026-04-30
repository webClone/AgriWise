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


def build_layer2_context(pkg: Layer1ContextPackage) -> Layer2InputContext:
    """Build the Layer 2 input payload from a Layer 1 context package.

    Layer 2 receives:
    - 7 feature-group dicts with fused values, confidence, uncertainty, source IDs
    - Conflicts and gaps (preserved, not hidden)
    - Confidence + uncertainty maps per feature group
    - Spatial index reference
    - Data health score
    - Provenance reference
    """
    return Layer2InputContext(
        plot_id=pkg.plot_id,
        crop_context=None,  # Populated by orchestrator

        water_context=_features_to_dict(pkg.fused_features.water_context),
        vegetation_context=_features_to_dict(pkg.fused_features.vegetation_context),
        phenology_context=_features_to_dict(pkg.fused_features.phenology_context),
        stress_evidence_context=_features_to_dict(pkg.fused_features.stress_evidence_context),
        soil_site_context=_features_to_dict(pkg.fused_features.soil_site_context),
        operational_context=_features_to_dict(pkg.fused_features.operational_context),
        data_quality_context=_features_to_dict(pkg.fused_features.data_quality_context),

        conflicts=pkg.conflicts,
        gaps=pkg.gaps,
        confidence=_build_confidence_map(pkg),
        uncertainty=_build_uncertainty_map(pkg),
        provenance_ref=pkg.provenance.run_id,
        spatial_index_ref=pkg.spatial_index,
        data_health=pkg.diagnostics.data_health,
    )


def _features_to_dict(features: List[FusedFeature]) -> Dict[str, Any]:
    """Convert fused features to a queryable dict."""
    result: Dict[str, Any] = {}
    for ff in features:
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

