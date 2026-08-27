"""Typed lineage for Layer 10 surfaces derived from admitted raster evidence."""
from __future__ import annotations

from typing import Any, Dict, Iterable


_DERIVED_TYPES = {
    "NDVI_DEVIATION": ("provider_derived", "ndvi_deviation_v1"),
    "BASELINE_ANOMALY": ("model_assisted", "baseline_anomaly_v1"),
    "WATER_STRESS_PROB": ("model_assisted", "water_stress_v1"),
    "WATER_FEASIBILITY": ("model_assisted", "water_feasibility_v1"),
    "RESOLUTION_COVERAGE": ("provider_derived", "resolution_coverage_v1"),
    "NUTRIENT_STRESS_PROB": ("model_assisted", "nutrient_stress_v5"),
    "SALINITY_STRESS": ("model_assisted", "salinity_stress_v2"),
    "COMPOSITE_RISK": ("model_assisted", "composite_risk_v4"),
}


def _metadata_for_basis(l1_data: Any, basis: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    metadata = getattr(l1_data, "raster_metadata", {}) or {}
    result: Dict[str, Dict[str, Any]] = {}
    for name in basis:
        item = metadata.get(name) or metadata.get(str(name).lower()) or metadata.get(str(name).upper())
        if isinstance(item, dict):
            result[str(name)] = item
    return result


def attach_derived_surface_lineage(surface: Any, l1_data: Any) -> bool:
    semantic = getattr(surface, "semantic_type", "")
    semantic = semantic.value if hasattr(semantic, "value") else str(semantic)
    contract = _DERIVED_TYPES.get(str(semantic).upper())
    basis = list(getattr(surface, "raster_basis", []) or [])
    if contract is None or not basis:
        return False
    parents = _metadata_for_basis(l1_data, basis)
    if len(parents) != len(set(basis)):
        return False
    provider_realities = {
        "provider_temporal_composite_raster", "real_raster",
        "real_provider_raster", "full_scene_stack",
    }
    if not all(
        str(item.get("source_reality") or "").lower() in provider_realities
        and item.get("real_provider_product") is True
        for item in parents.values()
    ):
        return False
    grid = getattr(surface, "grid_spec", None) or getattr(l1_data, "grid_spec", None) or {}
    crs = grid.get("crs") if isinstance(grid, dict) else None
    transform = grid.get("transform") if isinstance(grid, dict) else None
    closure = all(
        (item.get("crs") in (None, crs))
        and (
            item.get("transform") is None
            or list(item.get("transform") or []) == list(transform or [])
        )
        for item in parents.values()
    )
    derivation_class, operator_version = contract
    provenance = dict(getattr(surface, "provenance", {}) or {})
    provenance.update({
        "derived_from_surface_ids": [
            item.get("raster_id") or name for name, item in sorted(parents.items())
        ],
        "derived_from_content_hashes": [
            item.get("content_hash") for _, item in sorted(parents.items()) if item.get("content_hash")
        ],
        "operator_model_version": operator_version,
        "derivation_authority": "diagnostic",
        "derivation_class": derivation_class,
        "source_reality": "provider_derived",
        "observed_support_ratio": float(getattr(surface, "observed_ratio", 0.0) or 0.0),
        "crs_transform_closure": bool(closure),
        "uncertainty_propagation": "parent_support_and_model_confidence",
        "production_usable": all(item.get("production_usable") is True for item in parents.values()),
        "real_provider_product": False,
        "diagnostic_only": True,
        "state_update_allowed": False,
        "prescription_driver_allowed": False,
        "state_update_authority": "none",
        "prescription_authority": "blocked_diagnostic_only",
    })
    surface.provenance = provenance
    return True
