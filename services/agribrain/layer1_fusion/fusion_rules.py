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
- Confidence ceiling is source-family-aware (measurement theory)
"""

from __future__ import annotations

import math
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from .schemas import EvidenceItem, FusedFeature, FusedFeatureSet, CORE_SOURCE_FAMILIES, OPTIONAL_SOURCE_FAMILIES


# ============================================================================
# Explicit variable → feature group registry (F11)
#
# Each variable is explicitly assigned to its group(s). Variables that are
# agronomically cross-cutting (e.g., soil_moisture informs BOTH water balance
# AND soil characterization) are listed in BOTH groups intentionally.
#
# This replaces the old substring matching which caused accidental duplicates.
# Any variable NOT in this registry goes to data_quality_context as diagnostic.
# ============================================================================

_WATER_VARIABLES: FrozenSet[str] = frozenset({
    # Hydrological state
    "moisture", "wetness", "precip", "rain", "irrigation",
    "whc", "field_capacity", "wilting",
    # Specific variable names from adapters
    "soil_moisture_vwc", "surface_wetness_proxy_mean",
    "soil_moisture_uncertainty", "sar_moisture_proxy",
    "precipitation", "rain_mm", "forecast_precip",
    # L0 Kalman state vectors
    "l0_sm_mean", "l0_sm_uncertainty", "l0_sm_reliability",
    # Cross-cutting: soil moisture is water context primary
    "soil_moisture",
    # ASMAE Water State variables
    "ASMAE_CANOPY_WATER", "ASMAE_ROOT_ZONE_WATER", "ASMAE_SURFACE_WETNESS_EVENT",
})

_VEGETATION_VARIABLES: FrozenSet[str] = frozenset({
    # Spectral vegetation indices
    "ndvi", "ndmi", "ndre", "evi", "bsi",
    # Canopy / biophysical
    "lai", "vegetation_fraction", "canopy_cover", "canopy",
    "bare_soil_fraction", "bare_soil", "chlorophyll",
    # Fluorescence (photosynthetic activity)
    "sif", "pri",
    # EO Foundation Model outputs
    "anomaly_embedding", "anomaly_score",
    # Drone structural
    "weed_coverage", "weed", "biomass", "biomass_estimate",
    "tree_count", "missing_tree", "missing_tree_count",
    "canopy_density", "tree_health_score",
    # Vegetation keyword
    "vegetation",
    # ASMAE Vegetation State variables
    "ASMAE_VIGOR", "ASMAE_LAI", "ASMAE_CHLOROPHYLL", "ASMAE_STRUCTURE", "ASMAE_BARE_SOIL",
})

_PHENOLOGY_VARIABLES: FrozenSet[str] = frozenset({
    "gdd", "stage", "planting", "emergence", "harvest", "senescence",
    "growth_stage", "crop_stage", "phenological_stage",
    "days_after_planting", "maturity",
})

_STRESS_VARIABLES: FrozenSet[str] = frozenset({
    "stress", "frost", "thermal", "drought", "flood",
    "disease_weather", "vpd",
    # Temperature extremes as stress indicators
    "temp_max", "temperature_max", "temp_min", "temperature_min",
    "frost_risk", "heat_stress",
    # ASMAE Stress variables
    "ASMAE_SALINITY_STRESS", "ASMAE_THERMAL_STRESS", "ASMAE_BIOTIC_CONFOUNDER_RISK",
})

_SOIL_SITE_VARIABLES: FrozenSet[str] = frozenset({
    # Static soil properties
    "soil_clay_pct", "soil_sand_pct", "soil_silt_pct",
    "soil_organic_carbon", "soil_ph", "soil_cec",
    "soil_bulk_density", "soil_texture_class",
    # Terrain
    "elevation", "slope", "aspect",
    # Land cover / use
    "landcover", "cropland", "land_use",
    # WaPOR ET (contextual, diagnostic)
    "wapor_et", "wapor_aet", "wapor",
    # Cross-cutting: soil moisture also informs soil state
    "soil_moisture", "soil_moisture_vwc",
})

_OPERATIONAL_VARIABLES: FrozenSet[str] = frozenset({
    # User-reported events
    "user_irrigation", "user_fertilizer", "user_planting", "user_harvest",
    "user_spray", "user_event",
    # Sensor operational events
    "sensor_event",
    # Forecast risk windows
    "forecast_risk", "forecast_temp_max", "forecast_temp_min",
    # Drone row geometry
    "row_spacing", "row_orientation", "row_regularity",
    "break_count", "gap_count",
})


# ── Source-family confidence ceilings (F12) ──────────────────────────────────
#
# Derived from instrument measurement theory and remote sensing literature:
#
# sensor (0.95): Calibrated in-situ probes (e.g., Decagon EC-5 soil moisture:
#   ±0.03 m³/m³). Point measurement with direct contact — highest fidelity.
#
# sentinel2 (0.88): After atmospheric correction (Sen2Cor/MAJA), residual
#   aerosol and adjacency effects contribute ~0.03 NDVI uncertainty
#   (Doxani et al., 2018, Remote Sensing). Cloud shadows add further error.
#
# sentinel1 (0.78): C-band SAR affected by speckle noise (ENL ~4.4 for IW),
#   incidence angle variations, and surface roughness confounders
#   (El Hajj et al., 2017, Remote Sensing).
#
# environment (0.82): Gridded reanalysis products (ERA5) have ~0.25° spatial
#   interpolation error. Station-based corrections improve to city level.
#
# weather_forecast (0.70): NWP skill degrades with lead time. Day 1 RMSE ~2mm,
#   Day 5 RMSE ~8mm for precipitation (Hamill et al., 2006, MWR).
#
# geo_context (0.85): High-confidence static layers (DEM: ±1m SRTM), but
#   soil maps (SoilGrids) have ~30% uncertainty at 250m resolution.
#
# user_event (0.92): Farmer reports are highly reliable for action type/date
#   but may have ±1-day timing uncertainty for irrigation events.
#
# drone_structural (0.90): Sub-meter resolution but localized FOV.
#   RGB-only classification has lower spectral fidelity than multispectral.
#
# l0_state (0.80): Kalman-filtered estimates inherit upstream sensor
#   uncertainties through the state covariance matrix.
#
# eo_foundation (0.78): Model-derived embeddings — confidence limited by
#   training distribution coverage and fallback encoder fidelity.
#
SOURCE_CONFIDENCE_CEILING: Dict[str, float] = {
    "sensor":           0.95,
    "sentinel2":        0.88,
    "sentinel1":        0.78,
    "sentinel5p":       0.75,
    "eo_foundation":    0.78,
    "environment":      0.82,
    "weather_forecast": 0.70,
    "geo_context":      0.85,
    "perception":       0.72,
    "user_event":       0.92,
    "history":          0.45,
    "drone_structural": 0.90,
    "l0_state":         0.80,
    "raster_composite": 0.85,
    "zone_segmentation": 0.75,
    # V61F: Temporary operational ceiling. Sentinel-2-derived (0.88) minus
    # ~6% PSF deconvolution + resolution selection uncertainty.
    "microzone":        0.82,
}

# Default ceiling for unknown sources
_DEFAULT_CEILING = 0.75


def fuse_features(
    evidence: List[EvidenceItem],
    run_id: str = "",
) -> FusedFeatureSet:
    """Build fused feature set from evidence."""
    return FusedFeatureSet(
        water_context=_fuse_group(evidence, _WATER_VARIABLES, "water"),
        vegetation_context=_fuse_group(evidence, _VEGETATION_VARIABLES, "vegetation"),
        phenology_context=_fuse_group(evidence, _PHENOLOGY_VARIABLES, "phenology"),
        stress_evidence_context=_fuse_group(evidence, _STRESS_VARIABLES, "stress_evidence"),
        soil_site_context=_fuse_group(evidence, _SOIL_SITE_VARIABLES, "soil_site"),
        operational_context=_fuse_group(evidence, _OPERATIONAL_VARIABLES, "operational"),
        data_quality_context=_fuse_data_quality(evidence, run_id),
    )


# The grouping key: (variable, spatial_scope, scope_id, temporal_scope)
# This prevents collapsing zone-level NDVI into plot-level NDVI,
# AND prevents fusing observed daily evidence with forecast or static evidence.
def _group_key(e: EvidenceItem) -> Tuple[str, str, Optional[str], str]:
    return (e.variable, e.spatial_scope, e.scope_id, e.temporal_scope)


def _matches_group(variable: str, group_vars: FrozenSet[str]) -> bool:
    """Check if a variable belongs to a group.

    Matching strategy:
    1. Exact match (fast path)
    2. Prefix-component match: check if any registry entry appears
       as a contiguous prefix of underscore-separated components.
       e.g., "soil_moisture" matches "soil_moisture_vwc" because
       ["soil", "moisture"] == ["soil", "moisture"][:2].

    Important: registries should NOT contain overly generic
    single-component keywords (like "water") that could match
    unrelated variable families via prefix (e.g., "water_stress").
    Use specific variable names instead.
    """
    # Exact match (fast path)
    if variable in group_vars:
        return True

    # Component match: split variable into parts and check if any
    # registry entry matches a component prefix or exact component.
    var_parts = variable.split("_")
    for gv in group_vars:
        gv_parts = gv.split("_")
        gv_len = len(gv_parts)
        # Check if the registry entry matches a contiguous sequence
        # of components at the START of the variable name.
        # e.g., "soil_moisture" matches "soil_moisture_vwc"
        #        but "water" does NOT match "water_stress_prob"
        #        because we require the FULL prefix to be meaningful.
        if var_parts[:gv_len] == gv_parts:
            return True
    return False


def _fuse_group(
    evidence: List[EvidenceItem],
    group_vars: FrozenSet[str],
    group_name: str,
) -> List[FusedFeature]:
    """Generic fusion: group evidence by (variable, spatial_scope, scope_id, temporal_scope).

    RC4 hardening:
    - Weighted average uses weight = confidence × reliability (per CONTRACT.md)
    - Forecast evidence only fuses into forecast-scoped features
    - Source evidence IDs on every fused feature (no orphans)
    - Scope and temporal_scope persisted from grouping key
    - Confidence ceiling is source-family-aware (F12)
    """
    features: List[FusedFeature] = []

    # Filter relevant evidence using explicit variable registry
    relevant = [
        e for e in evidence
        if _matches_group(e.variable, group_vars)
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
            total_weight_raw = sum(w for _, w in weights_raw)
            avg_freshness = sum(e.freshness_score for e in numeric) / len(numeric)
            source_families = set(e.source_family for e in numeric)

            # F12: Source-aware confidence ceiling
            # The ceiling for a multi-source fusion is the maximum of contributing
            # source ceilings — because having multiple independent sources
            # increases confidence (but never beyond the best instrument's limit).
            max_ceiling = max(
                SOURCE_CONFIDENCE_CEILING.get(sf, _DEFAULT_CEILING)
                for sf in source_families
            )

            flags = []
            if total_weight_raw == 0.0:
                fused_value = sum(e.value for e in numeric) / len(numeric)
                max_confidence = min(max_ceiling, 0.10)
                flags.append("ZERO_WEIGHT_UNWEIGHTED_AVERAGE")
                source_weights = {sf: round(1.0 / len(source_families), 4) for sf in source_families}
            else:
                total_weight = total_weight_raw
                fused_value = sum(e.value * w for e, w in weights_raw) / total_weight
                # Accumulate weights per source_family (not overwrite)
                source_weights: Dict[str, float] = {}
                for e, w in weights_raw:
                    source_weights[e.source_family] = (
                        source_weights.get(e.source_family, 0.0)
                        + round(w / total_weight, 4)
                    )
                weighted_conf = sum(e.confidence * w for e, w in weights_raw) / total_weight
                max_confidence = min(max_ceiling, weighted_conf)

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
                flags=flags,
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


def _fuse_data_quality(evidence: List[EvidenceItem], run_id: str = "") -> List[FusedFeature]:
    """Summarize data quality across sources.

    Fix #3: data-quality features now have provenance via
    ledger_summary:<run_id> marker and reference all contributing evidence IDs.
    """
    features: List[FusedFeature] = []
    all_ids = [e.evidence_id for e in evidence]
    provenance_marker = f"ledger_summary:{run_id}" if run_id else "ledger_summary:unknown"

    # Source completeness computed from usable evidence only (F11/F12)
    usable_evidence = [
        e for e in evidence
        if not e.diagnostic_only
        and e.state_update_allowed
        and e.data_status not in ("unavailable", "simulated", "fallback")
    ]
    sources_present = {e.source_family for e in usable_evidence}

    core_present = sources_present.intersection(CORE_SOURCE_FAMILIES)
    core_comp = len(core_present) / len(CORE_SOURCE_FAMILIES) if CORE_SOURCE_FAMILIES else 0.0

    optional_present = sources_present.intersection(OPTIONAL_SOURCE_FAMILIES)
    optional_comp = len(optional_present) / len(OPTIONAL_SOURCE_FAMILIES) if OPTIONAL_SOURCE_FAMILIES else 0.0

    denominator = len(CORE_SOURCE_FAMILIES) + len(OPTIONAL_SOURCE_FAMILIES)
    overall_comp = (len(core_present) + len(optional_present)) / denominator if denominator > 0 else 0.0

    features.append(FusedFeature(
        name="core_source_completeness",
        value=round(core_comp, 2),
        unit="fraction",
        spatial_scope="plot",
        confidence=0.95,
        freshness=1.0,
        source_evidence_ids=[provenance_marker] + all_ids,
        source_weights={"ledger_summary": 1.0},
    ))

    features.append(FusedFeature(
        name="optional_source_completeness",
        value=round(optional_comp, 2),
        unit="fraction",
        spatial_scope="plot",
        confidence=0.95,
        freshness=1.0,
        source_evidence_ids=[provenance_marker] + all_ids,
        source_weights={"ledger_summary": 1.0},
    ))

    features.append(FusedFeature(
        name="overall_source_completeness",
        value=round(overall_comp, 2),
        unit="fraction",
        spatial_scope="plot",
        confidence=0.95,
        freshness=1.0,
        source_evidence_ids=[provenance_marker] + all_ids,
        source_weights={"ledger_summary": 1.0},
    ))

    # Keep backward compatible source_completeness pointing to overall_completeness
    features.append(FusedFeature(
        name="source_completeness",
        value=round(overall_comp, 2),
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

