"""
Layer 2 Intelligence — Zone Intelligence.

Computes per-zone vegetation metrics using spatial_index_ref and fused features.
Produces zone-level VegetationFeatures and ZoneStressSummary.

Key metrics per zone:
  - vigor_index: mean NDVI in zone
  - uniformity_cv: coefficient of variation within zone
  - zone_vs_plot_deviation: how different zone is from plot mean
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .schemas import (
    StressEvidence,
    VegetationFeature,
    ZoneStressSummary,
    SpatialIndex,
)


def compute_zone_vegetation(
    vegetation_features: Dict[str, Any],
    spatial_index: Optional[SpatialIndex],
) -> List[VegetationFeature]:
    """Compute per-zone vegetation features.

    If zone-scoped features exist (scope_id != None), produce zone-level metrics.
    Always produces plot-level summary as well.
    """
    features: List[VegetationFeature] = []

    # Plot-level vigor
    ndvi_val = _extract_value(vegetation_features, "ndvi_mean", "ndvi")
    if ndvi_val is not None:
        features.append(VegetationFeature(
            name="vigor_index",
            value=round(ndvi_val, 4),
            unit="index",
            spatial_scope="plot",
            confidence=_extract_confidence(vegetation_features, "ndvi_mean", "ndvi"),
            uncertainty=_extract_uncertainty(vegetation_features, "ndvi_mean", "ndvi"),
            source_evidence_ids=_extract_evidence_ids(vegetation_features, "ndvi_mean", "ndvi"),
        ))

    # Canopy cover proxy from vegetation fraction
    veg_frac = _extract_value(vegetation_features, "vegetation_fraction_scl")
    if veg_frac is not None:
        features.append(VegetationFeature(
            name="canopy_cover_proxy",
            value=round(veg_frac, 4),
            unit="fraction",
            spatial_scope="plot",
            confidence=_extract_confidence(vegetation_features, "vegetation_fraction_scl"),
            source_evidence_ids=_extract_evidence_ids(vegetation_features, "vegetation_fraction_scl"),
        ))

    # Zone-scoped features (from L1 zone-scoped fused features)
    if spatial_index:
        for zone in spatial_index.zones:
            zone_features = _find_zone_features(vegetation_features, zone.zone_id)
            if zone_features:
                zone_ndvi = zone_features.get("value")
                if zone_ndvi is not None:
                    features.append(VegetationFeature(
                        name="vigor_index",
                        value=round(zone_ndvi, 4),
                        unit="index",
                        spatial_scope="zone",
                        scope_id=zone.zone_id,
                        confidence=zone_features.get("confidence", 0.5),
                        uncertainty=zone_features.get("uncertainty"),
                    ))

                    # Zone vs plot deviation
                    if ndvi_val is not None:
                        deviation = round(zone_ndvi - ndvi_val, 4)
                        features.append(VegetationFeature(
                            name="zone_vs_plot_deviation",
                            value=deviation,
                            unit="index",
                            spatial_scope="zone",
                            scope_id=zone.zone_id,
                            confidence=min(
                                zone_features.get("confidence", 0.5),
                                _extract_confidence(vegetation_features, "ndvi_mean", "ndvi"),
                            ),
                        ))

    return features


def build_zone_stress_map(
    stress_items: List[StressEvidence],
    vegetation_features: List[VegetationFeature],
    spatial_index: Optional[SpatialIndex],
) -> Dict[str, ZoneStressSummary]:
    """Build per-zone stress summaries."""
    zone_map: Dict[str, ZoneStressSummary] = {}

    # Group stress by scope
    for s in stress_items:
        zone_id = s.scope_id or "plot"
        if zone_id not in zone_map:
            zone_map[zone_id] = ZoneStressSummary(zone_id=zone_id)

        summary = zone_map[zone_id]
        summary.stress_count += 1
        summary.stress_items.append(s.stress_id)

        # Running averages
        n = summary.stress_count
        summary.avg_severity = round(
            ((n - 1) * summary.avg_severity + s.severity) / n, 3
        )
        summary.avg_confidence = round(
            ((n - 1) * summary.avg_confidence + s.confidence) / n, 3
        )
        summary.max_severity = max(summary.max_severity, s.severity)

    # Determine dominant stress type per zone
    for zone_id, summary in zone_map.items():
        zone_stresses = [s for s in stress_items if (s.scope_id or "plot") == zone_id]
        if zone_stresses:
            dominant = max(zone_stresses, key=lambda s: s.severity)
            summary.dominant_stress_type = dominant.stress_type

    # Attach zone-level vegetation features
    for vf in vegetation_features:
        zone_id = vf.scope_id or "plot"
        if zone_id in zone_map:
            zone_map[zone_id].vegetation_features.append(vf)

    return zone_map


def _find_zone_features(
    features: Dict[str, Any], zone_id: str,
) -> Optional[Dict[str, Any]]:
    import math
    for key, entry in features.items():
        if isinstance(entry, dict) and entry.get("scope_id") == zone_id:
            # Check if value is valid
            val = entry.get("value")
            if val is not None and (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
                return None
            return entry
    return None


def _extract_value(features: Dict[str, Any], *keys: str) -> Optional[float]:
    for k in keys:
        entry = features.get(k)
        if entry is not None:
            if isinstance(entry, dict):
                return entry.get("value")
            return entry
    return None


def _extract_confidence(features: Dict[str, Any], *keys: str) -> float:
    for k in keys:
        entry = features.get(k)
        if isinstance(entry, dict):
            return entry.get("confidence", 0.5)
    return 0.5


def _extract_uncertainty(features: Dict[str, Any], *keys: str) -> Optional[float]:
    for k in keys:
        entry = features.get(k)
        if isinstance(entry, dict):
            return entry.get("uncertainty")
    return None


def _extract_evidence_ids(features: Dict[str, Any], *keys: str) -> List[str]:
    ids = []
    for k in keys:
        entry = features.get(k)
        if isinstance(entry, dict):
            for eid in entry.get("source_weights", {}).keys():
                if eid not in ids:
                    ids.append(eid)
    return ids
