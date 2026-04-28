"""
Layer 1 API Serializer.

Deterministic JSON serialization of Layer1ContextPackage.

Rules (correction #11):
- Sorted keys
- ISO timestamps in UTC
- No object memory addresses
- No unordered set iteration
- Stable float rounding (4 decimal places)
- Explicit run_timestamp only
- Stable ordering for evidence/conflicts/gaps
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict

from layer1_fusion.schemas import Layer1ContextPackage


def _default_serializer(obj: Any) -> Any:
    """JSON default handler: datetime → ISO, set → sorted list."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, set):
        return sorted(obj)
    if isinstance(obj, frozenset):
        return sorted(obj)
    return str(obj)


def serialize_package(pkg: Layer1ContextPackage) -> str:
    """Serialize Layer1ContextPackage to deterministic JSON.

    Same package → same JSON bytes → same hash.
    """
    data = _package_to_dict(pkg)
    return json.dumps(data, sort_keys=True, default=_default_serializer, indent=2)


def compute_package_hash(pkg: Layer1ContextPackage) -> str:
    """Compute deterministic SHA-256 hash of the package."""
    serialized = serialize_package(pkg)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:32]


def _package_to_dict(pkg: Layer1ContextPackage) -> Dict[str, Any]:
    """Convert package to a serializable dict with stable ordering."""
    return {
        "plot_id": pkg.plot_id,
        "run_id": pkg.run_id,
        "generated_at": pkg.generated_at,
        "time_window": {
            "start": pkg.time_window.start,
            "end": pkg.time_window.end,
            "label": pkg.time_window.label,
        },
        "spatial_index": {
            "plot_id": pkg.spatial_index.plot_id,
            "zones": [
                {"zone_id": z.zone_id, "label": z.label, "area_fraction": z.area_fraction}
                for z in sorted(pkg.spatial_index.zones, key=lambda z: z.zone_id)
            ],
            "points": [
                {"point_id": p.point_id, "device_id": p.device_id, "placement": p.placement}
                for p in sorted(pkg.spatial_index.points, key=lambda p: p.point_id)
            ],
            "edge_regions": [
                {"edge_id": e.edge_id, "contamination_score": e.contamination_score}
                for e in sorted(pkg.spatial_index.edge_regions, key=lambda e: e.edge_id)
            ],
            "raster_refs": [
                {"raster_id": r.raster_id, "variable": r.variable, "resolution_m": r.resolution_m}
                for r in sorted(pkg.spatial_index.raster_refs, key=lambda r: r.raster_id)
            ],
        },
        "fused_features": {
            "water": [_feature_to_dict(f) for f in pkg.fused_features.water_context],
            "vegetation": [_feature_to_dict(f) for f in pkg.fused_features.vegetation_context],
            "phenology": [_feature_to_dict(f) for f in pkg.fused_features.phenology_context],
            "stress_evidence": [_feature_to_dict(f) for f in pkg.fused_features.stress_evidence_context],
            "soil_site": [_feature_to_dict(f) for f in pkg.fused_features.soil_site_context],
            "operational": [_feature_to_dict(f) for f in pkg.fused_features.operational_context],
            "data_quality": [_feature_to_dict(f) for f in pkg.fused_features.data_quality_context],
        },
        "state_summary": {
            "water_context_status": pkg.state_summary.water_context_status,
            "vegetation_context_status": pkg.state_summary.vegetation_context_status,
            "usable_for_layer2": pkg.state_summary.usable_for_layer2,
            "confidence_ceiling": _round4(pkg.state_summary.confidence_ceiling),
            "blocking_gaps": sorted(pkg.state_summary.blocking_gaps),
            "unresolved_major_conflicts": sorted(pkg.state_summary.unresolved_major_conflicts),
            "data_health_status": pkg.state_summary.data_health_status,
        },
        "conflicts": [
            {
                "conflict_id": c.conflict_id,
                "type": c.conflict_type,
                "severity": c.severity,
                "source_a": c.source_a,
                "source_b": c.source_b,
            }
            for c in sorted(pkg.conflicts, key=lambda c: c.conflict_id)
        ],
        "gaps": [
            {
                "gap_id": g.gap_id,
                "type": g.gap_type,
                "severity": g.severity,
            }
            for g in sorted(pkg.gaps, key=lambda g: g.gap_id)
        ],
        "provenance": {
            "run_id": pkg.provenance.run_id,
            "engine_version": pkg.provenance.engine_version,
            "contract_version": pkg.provenance.contract_version,
            "evidence_count": pkg.provenance.evidence_count,
            "fused_feature_count": pkg.provenance.fused_feature_count,
            "conflicts_count": pkg.provenance.conflicts_count,
            "gaps_count": pkg.provenance.gaps_count,
            "quarantined_count": pkg.provenance.quarantined_count,
            "input_package_ids": {
                k: sorted(v) for k, v in sorted(pkg.provenance.input_package_ids.items())
            },
        },
        "diagnostics": {
            "status": pkg.diagnostics.status,
            "data_health_overall": _round4(pkg.diagnostics.data_health.overall),
            "quarantined_count": pkg.diagnostics.quarantined_evidence_count,
        },
    }


def _feature_to_dict(f: Any) -> Dict[str, Any]:
    return {
        "name": f.name,
        "value": _round4(f.value) if isinstance(f.value, float) else f.value,
        "unit": f.unit,
        "confidence": _round4(f.confidence),
        "freshness": _round4(f.freshness),
        "spatial_scope": f.spatial_scope,
        "scope_id": f.scope_id,
        "temporal_scope": f.temporal_scope,
        "source_evidence_ids": sorted(f.source_evidence_ids),
        "source_count": len(f.source_evidence_ids),
        "source_weights": {k: _round4(v) for k, v in sorted(f.source_weights.items())},
        "conflict_status": f.conflict_status,
        "flags": sorted(f.flags),
    }


def _round4(v: Any) -> Any:
    if isinstance(v, float):
        return round(v, 4)
    return v
