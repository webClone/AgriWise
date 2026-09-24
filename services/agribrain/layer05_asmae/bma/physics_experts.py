"""Independent, input-specific physics experts for ASMAE BMA.

Each expert predicts only its declared target states from its own evidence
family.  It does not begin by copying the EnKF posterior.  Missing inputs make
an expert unavailable rather than a pass-through model.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Mapping, Optional

from ..config import N_STATES, STATE_BOUNDS, STATE_NAMES


def _finite(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        value = float(value)
        return value if math.isfinite(value) else None
    try:
        import numpy as np
        array = np.asarray(value, dtype=float)
        values = array[np.isfinite(array)]
        return float(np.mean(values)) if values.size else None
    except (TypeError, ValueError):
        return None


def _clip(state: str, value: float) -> float:
    lo, hi = STATE_BOUNDS[state]
    return max(lo, min(hi, float(value)))


def _real_scenes(context: Mapping[str, Any]) -> List[Any]:
    result = []
    for scene in context.get("scenes", []) or []:
        reality = str(getattr(scene, "source_reality", "unknown"))
        authority = str(getattr(scene, "authority", "real"))
        binding = str(getattr(scene, "product_binding", "") or "")
        if (
            getattr(scene, "real_provider_product", False) is True
            and reality in {
                "real_raster",
                "real_provider_raster",
                "provider_observation",
            }
            and authority in {"real", "production", "certified_production"}
            and (not binding or binding == "exact_catalog_item")
        ):
            result.append(scene)
    return result


def _scene_signal(scenes: Iterable[Any], aliases: Iterable[str]) -> Optional[float]:
    values: List[float] = []
    aliases = tuple(aliases)
    for scene in scenes:
        bands = getattr(scene, "bands", {}) or {}
        found = None
        for key in aliases:
            if key in bands:
                found = _finite(bands[key])
                if found is not None:
                    break
        if found is not None:
            values.append(found)
    return sum(values) / len(values) if values else None


def _sar_db_signal(scenes: Iterable[Any], polarization: str) -> Optional[float]:
    values: List[float] = []
    key = polarization.upper()
    for scene in scenes:
        bands = getattr(scene, 'bands', {}) or {}
        if key not in bands:
            continue
        raw = _finite(bands[key])
        units = str((getattr(scene, 'sar_units', {}) or {}).get(key, 'unknown'))
        if raw is None:
            continue
        if units == 'db':
            values.append(raw)
        elif units == 'linear_sigma0' and raw > 0.0:
            values.append(10.0 * math.log10(raw))
    return sum(values) / len(values) if values else None


def _prediction(nodes: Iterable[str], values: Mapping[str, float]) -> Dict[str, List[Optional[float]]]:
    result: Dict[str, List[Optional[float]]] = {}
    for node in nodes:
        vector: List[Optional[float]] = [None] * N_STATES
        for state, value in values.items():
            vector[STATE_NAMES.index(state)] = _clip(state, value)
        result[str(node)] = vector
    return result


def _optical(nodes: List[str], context: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    scenes = [scene for scene in _real_scenes(context) if getattr(scene, "sensor", "") == "S2"]
    ndvi = _scene_signal(scenes, ("ndvi", "NDVI"))
    if ndvi is None:
        nir = _scene_signal(scenes, ("B08", "b08", "nir"))
        red = _scene_signal(scenes, ("B04", "b04", "red"))
        if nir is not None and red is not None and abs(nir + red) > 1e-9:
            ndvi = (nir - red) / (nir + red)
    evi = _scene_signal(scenes, ("evi", "EVI"))
    ndre = _scene_signal(scenes, ("ndre", "NDRE", "reip", "REIP"))
    ndmi = _scene_signal(scenes, ("ndmi", "NDMI"))
    primary = ndvi if ndvi is not None else evi
    if primary is None:
        return None
    vigor = max(0.0, min(1.0, (primary + 0.1) / 0.9))
    values = {
        "vigor": vigor,
        "lai": min(8.0, max(0.0, -2.2 * math.log(max(0.03, 1.0 - 0.92 * vigor)))),
        "bare_soil_fraction": 1.0 - vigor,
    }
    if ndre is not None:
        values["chlorophyll"] = max(0.0, min(80.0, ((ndre + 0.05) / 0.65) * 80.0))
    if ndmi is not None:
        values["canopy_water"] = max(0.0, min(1.0, (ndmi + 1.0) / 2.0))
    scene_ids = [str(getattr(scene, "scene_id", "")) for scene in scenes]
    return {
        "predictions": _prediction(nodes, values),
        "target_states": list(values),
        "input_evidence": scene_ids,
        "independence_key": "real_s2_optical_radiometry",
        "model_version": "optical_physiology_v1",
    }


def _sar(nodes: List[str], context: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    scenes = [scene for scene in _real_scenes(context) if getattr(scene, "sensor", "") == "S1"]
    vv = _sar_db_signal(scenes, 'VV')
    vh = _sar_db_signal(scenes, 'VH')
    if vv is None and vh is None:
        return None
    values: Dict[str, float] = {}
    if vv is not None:
        values["surface_wetness_event"] = max(0.0, min(1.0, (vv + 25.0) / 20.0))
    if vh is not None:
        values["structure"] = max(0.0, min(1.0, (vh + 30.0) / 20.0))
    if vv is not None and vh is not None:
        ratio = vv - vh
        values["canopy_water"] = max(0.0, min(1.0, 1.0 - ratio / 20.0))
    return {
        "predictions": _prediction(nodes, values),
        "target_states": list(values),
        "input_evidence": [str(getattr(scene, "scene_id", "")) for scene in scenes],
        "independence_key": "real_s1_backscatter",
        "model_version": "sar_structure_moisture_v1",
        'observation_units': 'db_calibrated',
    }


def _records(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, Mapping):
        return [dict(item) for item in value.values() if isinstance(item, Mapping)]
    if isinstance(value, (list, tuple)):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _find_numeric(value: Any, aliases: Iterable[str]) -> Optional[float]:
    if not isinstance(value, Mapping):
        return None
    aliases = {item.lower() for item in aliases}
    queue = [value]
    while queue:
        current = queue.pop(0)
        for key, item in current.items():
            if str(key).lower() in aliases:
                found = _finite(item)
                if found is not None:
                    return found
            if isinstance(item, Mapping):
                queue.append(item)
    return None


def _water_balance(nodes: List[str], context: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    weather = _records(context.get("weather_daily_series", {}))
    if not weather:
        return None
    rainfall = sum(
        value for row in weather
        if (value := _find_numeric(row, ("precipitation_mm", "precipitation", "rainfall_mm", "rain"))) is not None
    )
    et0 = sum(
        value for row in weather
        if (value := _find_numeric(row, ("et0_mm", "et0", "evapotranspiration"))) is not None
    )
    tmax = [
        value for row in weather
        if (value := _find_numeric(row, ("temp_max_c", "temp_max", "temperature_max", "tmax"))) is not None
    ]
    soil = context.get("soil_context", {}) or {}
    root_initial = _find_numeric(soil, ("root_zone_water", "soil_moisture", "sm_10_40"))
    field_capacity_observed = _find_numeric(soil, ("field_capacity", "theta_fc"))
    wilting_observed = _find_numeric(soil, ("wilting_point", "theta_wp"))
    if root_initial is None and field_capacity_observed is None and wilting_observed is None:
        return None
    field_capacity = field_capacity_observed or 0.35
    wilting = wilting_observed or 0.12
    if root_initial is None:
        root_initial = (field_capacity + wilting) / 2.0
    rooting_depth = _find_numeric(soil, ("rooting_depth", "root_depth_m")) or 0.4
    storage_mm = max(25.0, rooting_depth * 1000.0 * max(field_capacity - wilting, 0.05))
    root = root_initial + (rainfall - et0) / storage_mm
    canopy = root + (rainfall - et0) / max(storage_mm * 0.6, 1.0)
    values: Dict[str, float] = {
        "root_zone_water": root,
        "canopy_water": canopy,
        "surface_wetness_event": min(1.0, rainfall / max(10.0 + et0, 1.0)),
    }
    if tmax:
        crop = context.get("crop_context", {}) or {}
        optimum = _find_numeric(crop, ("t_opt", "optimal_temperature")) or 25.0
        maximum = max(_find_numeric(crop, ("t_max", "maximum_temperature")) or 40.0, optimum + 1.0)
        values["thermal_stress"] = (max(tmax) - optimum) / (maximum - optimum)
    return {
        "predictions": _prediction(nodes, values),
        "target_states": list(values),
        "input_evidence": ["weather_daily_series", "soil_context"],
        "independence_key": "weather_soil_water_balance",
        "model_version": "water_balance_v1",
    }


def _spatial(nodes: List[str], context: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    spatial = context.get("spatial_prior_by_microzone")
    graph = context.get("graph")
    if not isinstance(spatial, Mapping) or graph is None or not hasattr(graph, "neighbors"):
        return None
    predictions: Dict[str, List[Optional[float]]] = {}
    target_states = set()
    for node in nodes:
        local = spatial.get(node)
        if not isinstance(local, Mapping):
            continue
        vector: List[Optional[float]] = [None] * N_STATES
        for state in STATE_NAMES:
            own = _finite(local.get(state))
            if own is None:
                continue
            weighted = own
            weight_total = 1.0
            for edge in graph.neighbors(node):
                neighbor_id = edge.target if edge.source == node else edge.source
                neighbor = spatial.get(neighbor_id)
                value = _finite(neighbor.get(state)) if isinstance(neighbor, Mapping) else None
                if value is not None:
                    weight = max(0.0, _finite(getattr(edge, 'combined_weight', 0.0)) or 0.0)
                    weighted += weight * value
                    weight_total += weight
            vector[STATE_NAMES.index(state)] = _clip(state, weighted / weight_total)
            target_states.add(state)
        predictions[node] = vector
    if not target_states:
        return None
    return {
        "predictions": predictions,
        "target_states": sorted(target_states),
        "input_evidence": ["coarse_spatial_prior", "microzone_graph"],
        "independence_key": "coarse_prior_graph_laplacian",
        "model_version": "graph_regularized_spatial_v1",
    }


def _phenology(nodes: List[str], context: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    timeseries = _records(context.get("plot_timeseries", []))
    canonical = context.get("phenology_posterior", {}) or {}
    if not isinstance(canonical, Mapping):
        return None
    stage = str(
        canonical.get("current_stage")
        or canonical.get("most_likely_stage")
        or "UNKNOWN"
    ).upper()
    authority = str(
        canonical.get("stage_authority")
        or canonical.get("authority")
        or "unavailable"
    ).lower()
    if stage == "UNKNOWN" or authority not in {"diagnostic", "calibrated"}:
        return None
    ndvi = []
    for row in timeseries:
        value = _find_numeric(row, ("ndvi", "ndvi_clean", "ndvi_interpolated"))
        if value is not None:
            ndvi.append(value)
    progress = _find_numeric(canonical.get("season_progress", {}), ("mean",))
    if progress is None:
        return None
    stress_memory = 0.0
    if ndvi:
        peak = max(ndvi)
        stress_memory = max(0.0, min(1.0, peak - ndvi[-1]))
    values = {
        "phenology_progress": progress,
        "stress_memory": stress_memory,
    }
    return {
        "predictions": _prediction(nodes, values),
        "target_states": list(values),
        "input_evidence": ["canonical_phenology_posterior"] + (["plot_timeseries"] if ndvi else []),
        "independence_key": "canonical_phenology_memory",
        "model_version": "canonical_phenology_memory_v2",
    }


def compute_physics_experts(
    means: Mapping[str, Any],
    context: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    context = context or {}
    nodes = [str(node) for node in means]
    builders = {
        "optical_physiology": _optical,
        "sar_structure": _sar,
        "water_balance": _water_balance,
        "spatial_smooth": _spatial,
        "phenology_memory": _phenology,
    }
    result = {}
    for name, builder in builders.items():
        expert = builder(nodes, context)
        if expert is not None:
            result[name] = expert
    return result
