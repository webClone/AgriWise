"""
Layer 1 Legacy Compatibility Adapter.

Builds a backward-compatible FieldTensor from Layer1ContextPackage.

CRITICAL RULES:
- compatibility_mode = True (always set)
- source_context_package_ref links to run_id
- missing_values_preserved = True (NEVER fake-fill)
- gaps_ref and conflicts_ref carry forward
- No fabricated NDVI, weather, soil, or moisture values

Existing L2/L3/L4/L5 layers work during the transition period.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from layer1_fusion.schemas import (
    FusedFeature,
    Layer1ContextPackage,
)


def build_legacy_fieldtensor(
    pkg: Layer1ContextPackage,
) -> Dict[str, Any]:
    """Build a backward-compatible FieldTensor dict from Layer1ContextPackage.

    Returns a dict matching the FieldTensor schema that existing layers
    consume. This is a COMPATIBILITY output — not a replacement for
    Layer1ContextPackage.

    Missing values are preserved as None. No fake defaults.
    """
    # Build plot_timeseries from fused features
    plot_ts = _build_plot_timeseries(pkg)

    # Build static dict from soil/site features
    static = _build_static(pkg)

    # Build provenance dict
    provenance = {
        "compatibility_mode": True,
        "source_context_package_ref": pkg.run_id,
        "engine_version": pkg.provenance.engine_version,
        "contract_version": pkg.provenance.contract_version,
        "evidence_count": pkg.provenance.evidence_count,
        "fused_feature_count": pkg.provenance.fused_feature_count,
        "missing_values_preserved": True,
        "gaps_ref": [g.gap_type for g in pkg.gaps],
        "conflicts_ref": [c.conflict_type for c in pkg.conflicts],
        "data_health_status": pkg.diagnostics.data_health.status,
        "data_health_overall": pkg.diagnostics.data_health.overall,
    }

    return {
        "plot_id": pkg.plot_id,
        "run_id": pkg.run_id,
        "version": "2.0.0-compat",

        "time_index": [],
        "channels": [],
        "data": [],

        "grid": {},
        "maps": {},
        "zones": {},
        "zone_stats": {},

        "plot_timeseries": plot_ts,
        "forecast_7d": _build_forecast(pkg),

        "static": static,
        "provenance": provenance,

        "daily_state": {},
        "state_uncertainty": {},
        "provenance_log": [],
        "spatial_reliability": {},
        "boundary_info": {},

        # Compatibility flags
        "_compatibility_mode": True,
        "_source_context_package_ref": pkg.run_id,
        "_missing_values_preserved": True,
        "_gaps_ref": [g.gap_type for g in pkg.gaps],
        "_conflicts_ref": [c.conflict_type for c in pkg.conflicts],
    }


def _build_plot_timeseries(pkg: Layer1ContextPackage) -> List[Dict]:
    """Build plot_timeseries from fused features.

    Only include values that actually exist. No fake fill.
    """
    row: Dict[str, Any] = {}

    # Water context
    for ff in pkg.fused_features.water_context:
        if isinstance(ff.value, (int, float)):
            key = _feature_to_ts_key(ff.name)
            row[key] = ff.value

    # Vegetation context
    for ff in pkg.fused_features.vegetation_context:
        if isinstance(ff.value, (int, float)):
            key = _feature_to_ts_key(ff.name)
            row[key] = ff.value

    if not row:
        return []

    return [row]


def _build_forecast(pkg: Layer1ContextPackage) -> List[Dict]:
    """Build forecast_7d from operational context."""
    forecast = []
    for ff in pkg.fused_features.operational_context:
        if "forecast" in ff.name and isinstance(ff.value, (int, float)):
            forecast.append({
                "variable": ff.name,
                "value": ff.value,
                "confidence": ff.confidence,
            })
    return forecast


def _build_static(pkg: Layer1ContextPackage) -> Dict[str, Any]:
    """Build static soil/site context."""
    static: Dict[str, Any] = {}
    for ff in pkg.fused_features.soil_site_context:
        if isinstance(ff.value, (int, float)):
            static[ff.name] = ff.value
    return static


def _feature_to_ts_key(name: str) -> str:
    """Map fused feature names to legacy timeseries keys."""
    _MAP = {
        "ndvi": "ndvi",
        "ndmi": "ndmi",
        "evi": "evi",
        "soil_moisture_vwc": "sm",
        "weather_precipitation_mm": "rain",
        "weather_temp_max": "temp_max",
        "weather_temp_min": "temp_min",
        "weather_et0_mm": "et0",
    }
    return _MAP.get(name, name)
