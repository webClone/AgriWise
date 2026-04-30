"""
Layer 1 Fusion Rules.

Transforms evidence into fused features across 7 canonical groups.
Each fused feature retains source_evidence_ids and source_weights.

Rules:
- No diagnosis or recommendation
- Evidence vocabulary only
- Missing data stays missing (no fake fill)
- Group by (variable, spatial_scope, scope_id, temporal_scope) — never
  collapse scopes or mix temporal horizons
- Weighted average uses weight = confidence × reliability
- Every fused feature MUST have source_evidence_ids (no orphans)
- Forecast evidence only fuses into forecast-scoped features
- Uncertainty propagated via inverse-variance weighting
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from .schemas import EvidenceItem, FusedFeature, FusedFeatureSet


def fuse_features(
    evidence: List[EvidenceItem],
    run_id: str = "",
) -> FusedFeatureSet:
    """Build fused feature set from evidence."""
    return FusedFeatureSet(
        water_context=_fuse_water(evidence),
        vegetation_context=_fuse_vegetation(evidence),
        phenology_context=_fuse_phenology(evidence),
        stress_evidence_context=_fuse_stress(evidence),
        soil_site_context=_fuse_soil_site(evidence),
        operational_context=_fuse_operational(evidence),
        data_quality_context=_fuse_data_quality(evidence, run_id),
    )


# The grouping key: (variable, spatial_scope, scope_id, temporal_scope)
# This prevents collapsing zone-level NDVI into plot-level NDVI,
# AND prevents fusing observed daily evidence with forecast or static evidence.
def _group_key(e: EvidenceItem) -> Tuple[str, str, Optional[str], str]:
    return (e.variable, e.spatial_scope, e.scope_id, e.temporal_scope)


def _fuse_group(
    evidence: List[EvidenceItem],
    variable_filters: List[str],
    group_name: str,
) -> List[FusedFeature]:
    """Generic fusion: group evidence by (variable, spatial_scope, scope_id, temporal_scope).

    RC4 hardening:
    - Weighted average uses weight = confidence × reliability (per CONTRACT.md)
    - Forecast evidence only fuses into forecast-scoped features
    - Source evidence IDs on every fused feature (no orphans)
    - Scope and temporal_scope persisted from grouping key
    """
    features: List[FusedFeature] = []

    # Filter relevant evidence
    relevant = [
        e for e in evidence
        if any(f in e.variable for f in variable_filters)
    ]

    # Group by (variable, spatial_scope, scope_id, temporal_scope)
    by_key: Dict[Tuple[str, str, Optional[str], str], List[EvidenceItem]] = {}
    for e in relevant:
        key = _group_key(e)
        by_key.setdefault(key, []).append(e)

    for (var, scope, scope_id, temporal_scope), items in by_key.items():
        # Filter to state-updatable (non-diagnostic) for value fusion
        updatable = [e for e in items if e.state_update_allowed and not e.diagnostic_only]
        all_items = items  # keep all for provenance

        if not updatable:
            # Diagnostic-only: report as evidence, not fused state
            for e in items:
                features.append(FusedFeature(
                    name=f"{var}_evidence",
                    value=e.value,
                    unit=e.unit,
                    spatial_scope=scope,
                    scope_id=scope_id,
                    temporal_scope=temporal_scope,
                    confidence=e.confidence,
                    freshness=e.freshness_score,
                    source_evidence_ids=[e.evidence_id],
                    source_weights={e.source_family: 1.0},
                    diagnostic_only=True,
                    flags=["DIAGNOSTIC_ONLY"],
                ))
            continue

        # Numeric fusion: weighted average by confidence × reliability
        numeric = [e for e in updatable if isinstance(e.value, (int, float))]

        if numeric:
            # weight = confidence × reliability (per CONTRACT.md)
            weights_raw = [(e, e.confidence * e.reliability) for e in numeric]
            total_weight = sum(w for _, w in weights_raw) or 1.0
            fused_value = sum(e.value * w for e, w in weights_raw) / total_weight
            # Accumulate weights per source_family (not overwrite)
            source_weights: Dict[str, float] = {}
            for e, w in weights_raw:
                source_weights[e.source_family] = (
                    source_weights.get(e.source_family, 0.0)
                    + round(w / total_weight, 4)
                )
            avg_freshness = sum(e.freshness_score for e in numeric) / len(numeric)
            max_confidence = min(0.95, max(e.confidence for e in numeric))

            # Uncertainty propagation: inverse-variance weighting
            # fused_sigma = 1 / sqrt(sum(1 / sigma_i²))
            fused_uncertainty = None
            sigmas = [e.sigma for e in numeric if e.sigma is not None and e.sigma > 0]
            if sigmas:
                inv_var_sum = sum(1.0 / (s * s) for s in sigmas)
                fused_uncertainty = round(1.0 / math.sqrt(inv_var_sum), 4)

            features.append(FusedFeature(
                name=var,
                value=round(fused_value, 4),
                unit=numeric[0].unit,
                spatial_scope=scope,
                scope_id=scope_id,
                temporal_scope=temporal_scope,
                confidence=max_confidence,
                uncertainty=fused_uncertainty,
                freshness=avg_freshness,
                source_evidence_ids=[e.evidence_id for e in all_items],
                source_weights=source_weights,
            ))
        else:
            # Non-numeric: take highest-confidence value
            best = max(updatable, key=lambda e: e.confidence)
            features.append(FusedFeature(
                name=var,
                value=best.value,
                unit=best.unit,
                spatial_scope=scope,
                scope_id=scope_id,
                temporal_scope=temporal_scope,
                confidence=best.confidence,
                freshness=best.freshness_score,
                source_evidence_ids=[e.evidence_id for e in all_items],
                source_weights={best.source_family: 1.0},
            ))

    return features


def _fuse_water(evidence: List[EvidenceItem]) -> List[FusedFeature]:
    return _fuse_group(
        evidence,
        ["moisture", "wetness", "precip", "rain", "irrigation", "water", "whc", "field_capacity", "wilting"],
        "water",
    )


def _fuse_vegetation(evidence: List[EvidenceItem]) -> List[FusedFeature]:
    return _fuse_group(
        evidence,
        ["ndvi", "ndmi", "ndre", "evi", "lai", "vegetation", "canopy", "chlorophyll", "bsi", "bare_soil"],
        "vegetation",
    )


def _fuse_phenology(evidence: List[EvidenceItem]) -> List[FusedFeature]:
    return _fuse_group(
        evidence,
        ["gdd", "stage", "planting", "emergence", "harvest", "senescence"],
        "phenology",
    )


def _fuse_stress(evidence: List[EvidenceItem]) -> List[FusedFeature]:
    return _fuse_group(
        evidence,
        ["stress", "frost", "thermal", "drought", "flood", "disease_weather", "vpd"],
        "stress_evidence",
    )


def _fuse_soil_site(evidence: List[EvidenceItem]) -> List[FusedFeature]:
    return _fuse_group(
        evidence,
        ["soil_", "elevation", "slope", "aspect", "landcover", "cropland", "wapor"],
        "soil_site",
    )


def _fuse_operational(evidence: List[EvidenceItem]) -> List[FusedFeature]:
    return _fuse_group(
        evidence,
        ["user_", "sensor_event", "forecast_risk"],
        "operational",
    )


def _fuse_data_quality(evidence: List[EvidenceItem], run_id: str = "") -> List[FusedFeature]:
    """Summarize data quality across sources.

    Fix #3: data-quality features now have provenance via
    ledger_summary:<run_id> marker and reference all contributing evidence IDs.
    """
    features: List[FusedFeature] = []
    all_ids = [e.evidence_id for e in evidence]
    provenance_marker = f"ledger_summary:{run_id}" if run_id else "ledger_summary:unknown"

    # Source completeness
    sources_present = set(e.source_family for e in evidence)
    completeness = len(sources_present) / 9.0

    features.append(FusedFeature(
        name="source_completeness",
        value=round(completeness, 2),
        unit="fraction",
        spatial_scope="plot",
        confidence=0.95,
        freshness=1.0,
        source_evidence_ids=[provenance_marker] + all_ids,
        source_weights={"ledger_summary": 1.0},
    ))

    # Average freshness
    if evidence:
        avg_fresh = sum(e.freshness_score for e in evidence) / len(evidence)
        features.append(FusedFeature(
            name="average_freshness",
            value=round(avg_fresh, 2),
            unit="score",
            spatial_scope="plot",
            confidence=0.95,
            freshness=1.0,
            source_evidence_ids=[provenance_marker] + all_ids,
            source_weights={"ledger_summary": 1.0},
        ))

    return features
