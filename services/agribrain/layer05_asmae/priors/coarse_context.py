"""Evidence-conservative coarse Layer 2-8 context pass.

The pass runs before ASMAE and exposes every downstream prior family without
executing recommendations.  Numeric values are emitted only when Layer 1,
weather, soil, crop, or management evidence supports them.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional


def _dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "__dict__"):
        return {key: item for key, item in vars(value).items() if not key.startswith("_")}
    return {}


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        value = float(value)
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        for key in ("mean", "value", "estimate", "current"):
            if key in value:
                found = _number(value[key])
                if found is not None:
                    return found
    return None


def _rows(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, Mapping):
        return [_dict(item) for item in value.values() if _dict(item)]
    if isinstance(value, (list, tuple)):
        return [_dict(item) for item in value if _dict(item)]
    return []


def _values(rows: Iterable[Mapping[str, Any]], aliases: Iterable[str]) -> List[float]:
    result = []
    for row in rows:
        for key in aliases:
            if key in row:
                value = _number(row[key])
                if value is not None:
                    result.append(value)
                    break
    return result


def _unavailable(layer: str, reason: str) -> Dict[str, Any]:
    return {
        "status": "unavailable",
        "confidence": 0.0,
        "source_layer": layer,
        "source_timestamp": datetime.now(timezone.utc).isoformat(),
        "evidence": [],
        "reason": reason,
    }


def build_coarse_layer_outputs(
    layer1_output: Any,
    *,
    crop_context: Any,
    weather_records: Any,
    management_events: Any,
) -> Dict[str, Dict[str, Any]]:
    timeseries = _rows(getattr(layer1_output, "plot_timeseries", []) if layer1_output is not None else [])
    static = _dict(getattr(layer1_output, "static", {}) if layer1_output is not None else {})
    weather = _rows(weather_records)
    management = _rows(management_events)
    now = datetime.now(timezone.utc).isoformat()

    ndvi = _values(timeseries, ("ndvi", "ndvi_clean", "ndvi_interpolated", "NDVI"))
    ndre = _values(timeseries, ("ndre", "REIP", "reip"))
    rain = _values(weather or timeseries, ("precipitation_mm", "precipitation", "rainfall_mm", "rain"))
    et0 = _values(weather or timeseries, ("et0_mm", "et0", "evapotranspiration"))
    tmax = _values(weather or timeseries, ("temp_max_c", "temp_max", "temperature_max", "tmax"))
    humidity = _values(weather or timeseries, ("humidity_mean_pct", "humidity", "relative_humidity", "rh"))

    result = {
        key: _unavailable(key, "required_coarse_evidence_missing")
        for key in (
            "layer2_intelligence", "layer3_water", "layer4_nutrients",
            "layer5_biotic", "layer6_yield", "layer7_risk", "layer8_action",
        )
    }

    if ndvi:
        current = ndvi[-1]
        peak = max(ndvi)
        peak_index = ndvi.index(peak)
        if len(ndvi) < 3:
            growth_position = None
            stage = "unknown"
        elif peak_index == len(ndvi) - 1:
            growth_position = 0.5 * peak_index / max(len(ndvi) - 1, 1)
            stage = "vegetative"
        else:
            growth_position = 0.5 + 0.5 * (len(ndvi) - 1 - peak_index) / max(len(ndvi) - 1, 1)
            stage = "senescence" if current < peak * 0.8 else "reproductive"
        result["layer2_intelligence"] = {
            "status": "available",
            "confidence": min(0.9, 0.45 + 0.05 * len(ndvi)),
            "source_layer": "layer1_coarse_temporal",
            "source_timestamp": now,
            "evidence": ["NDVI"],
            "phenology_stage": stage,
            "growth_position": growth_position,
            "vigor": max(0.0, min(1.0, (current + 0.1) / 0.9)),
        }

    soil_moisture = None
    for key in ("root_zone_water", "soil_moisture", "sm_10_40"):
        soil_moisture = _number(static.get(key))
        if soil_moisture is not None:
            break
    if rain or et0 or soil_moisture is not None:
        rain_total = sum(rain)
        et0_total = sum(et0)
        water_balance = None
        if soil_moisture is not None:
            water_balance = max(0.0, min(1.0, soil_moisture + (rain_total - et0_total) / 150.0))
        result["layer3_water"] = {
            "status": "available" if water_balance is not None else "partial",
            "confidence": 0.7 if soil_moisture is not None else 0.5,
            "source_layer": "weather_soil_coarse_process",
            "source_timestamp": now,
            "evidence": (["soil_moisture"] if soil_moisture is not None else []) + (["weather"] if rain or et0 else []),
            "et0": et0_total if et0 else None,
            "water_balance": water_balance,
            "root_zone_water": water_balance,
        }

    salinity = _number(static.get("salinity")) or _number(static.get("electrical_conductivity"))
    if ndre or salinity is not None:
        chlorophyll = max(0.0, min(80.0, ((ndre[-1] + 0.05) / 0.65) * 80.0)) if ndre else None
        salinity_risk = max(0.0, min(1.0, salinity / 8.0)) if salinity is not None else None
        result["layer4_nutrients"] = {
            "status": "available",
            "confidence": 0.65 if ndre and salinity is not None else 0.5,
            "source_layer": "optical_soil_coarse_context",
            "source_timestamp": now,
            "evidence": (["NDRE_REIP"] if ndre else []) + (["soil_salinity"] if salinity is not None else []),
            "chlorophyll_proxy": chlorophyll,
            "salinity_risk": salinity_risk,
        }

    if humidity and tmax:
        suitability = max(0.0, min(1.0, (sum(humidity) / len(humidity)) / 100.0))
        result["layer5_biotic"] = {
            "status": "partial",
            "confidence": 0.4,
            "source_layer": "weather_disease_suitability",
            "source_timestamp": now,
            "evidence": ["humidity", "temperature"],
            "biotic_threat_risk": None,
            "weather_disease_suitability": suitability,
            "outbreak_probability": None,
        }

    if ndvi:
        variability = max(ndvi) - min(ndvi)
        result["layer6_yield"] = {
            "status": "partial",
            "confidence": 0.35,
            "source_layer": "vegetation_sensitivity_context",
            "source_timestamp": now,
            "evidence": ["NDVI_trajectory"],
            "yield_sensitivity": min(1.0, variability),
            "scouting_priority": min(1.0, variability),
        }

    if tmax or (rain or et0):
        heat = max(0.0, (max(tmax) - 35.0) / 10.0) if tmax else 0.0
        deficit = max(0.0, (sum(et0) - sum(rain)) / max(sum(et0), 1.0)) if et0 else 0.0
        result["layer7_risk"] = {
            "status": "available",
            "confidence": 0.6,
            "source_layer": "weather_risk_coarse_context",
            "source_timestamp": now,
            "evidence": ["weather"],
            "climate_shock_risk": min(1.0, max(heat, deficit)),
            "forecast_uncertainty": None,
            "future_stress_windows": [],
        }

    if weather or management:
        result["layer8_action"] = {
            "status": "partial",
            "confidence": 0.5,
            "source_layer": "constraint_only_coarse_context",
            "source_timestamp": now,
            "evidence": (["weather"] if weather else []) + (["management"] if management else []),
            "do_not_prescribe_zones": [],
            "action_feasibility": {},
            "spray_drift_risk": None,
            "phenology_dosing_windows": [],
            "salinity_leaching_windows": [],
            "is_constraint_only": True,
            "contains_recommendations": False,
        }

    return result
