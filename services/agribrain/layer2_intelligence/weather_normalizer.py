"""
Weather Normalizer — Normalizes weather inputs for Layer 2.
Maps precipitation, temp_max, vpd, and et0 from timeseries or context
while preserving evidence ID provenance.
"""

from typing import Any, Dict, List, Optional

def normalize_weather_context(context: Any, tensor: Any = None) -> None:
    """Normalize weather variables into canonical keys in Layer2InputContext."""
    if context is None:
        return

    # Helper to find existing feature entry in context groups
    def _find_in_context(groups, key_names):
        for g in groups:
            if not g:
                continue
            for kn in key_names:
                if kn in g and g[kn] is not None:
                    # Return both the entry and which key was matched
                    return g[kn], kn
        return None, None

    # Helper to find latest in timeseries
    def _find_latest_in_timeseries(key_names):
        if not tensor or not getattr(tensor, "plot_timeseries", None):
            return None, None
        for r in reversed(tensor.plot_timeseries):
            for kn in key_names:
                v = r.get(kn)
                if v is not None:
                    return v, kn
        return None, None

    # Helper to build provenance/metadata
    def _build_weather_feature(val, unit, source_evidence_ids, source_family, normalized_from, is_diagnostic=False, flags=None):
        if flags is None:
            flags = []
        return {
            "value": val,
            "unit": unit,
            "confidence": 0.40 if is_diagnostic else 0.85,
            "source_evidence_ids": source_evidence_ids,
            "source_family": source_family,
            "normalized_from": normalized_from,
            "diagnostic_only": is_diagnostic,
            "flags": flags
        }

    # 1. Precipitation
    precip_keys = ["precipitation_mm", "precip_recent", "rain_mm", "rain"]
    existing_precip_val, existing_key = _find_in_context([context.water_context, context.operational_context, context.stress_evidence_context], precip_keys)
    
    if existing_precip_val:
        source_ids = list(existing_precip_val.get("source_evidence_ids") or [])
        is_diag = existing_precip_val.get("diagnostic_only", False)
        flags = list(existing_precip_val.get("flags", []))
        
        if not source_ids:
            is_diag = True
            if "weather_missing_source_evidence_ids" not in flags:
                flags.append("weather_missing_source_evidence_ids")
        
        context.water_context["precipitation_mm"] = _build_weather_feature(
            val=existing_precip_val.get("value"),
            unit="mm",
            source_evidence_ids=source_ids,
            source_family="environment",
            normalized_from=existing_key,
            is_diagnostic=is_diag,
            flags=flags
        )
    else:
        ts_val, ts_key = _find_latest_in_timeseries(["rain", "rain_mm", "precipitation_mm", "precip_recent"])
        if ts_val is not None:
            context.water_context["precipitation_mm"] = _build_weather_feature(
                val=ts_val,
                unit="mm",
                source_evidence_ids=[],
                source_family="environment",
                normalized_from=ts_key,
                is_diagnostic=True,
                flags=["weather_missing_source_evidence_ids", "weather_normalizer_fallback"]
            )

    # 2. Temp Max
    temp_keys = ["temp_max", "temperature_max"]
    existing_temp_val, existing_key = _find_in_context([context.stress_evidence_context, context.operational_context], temp_keys)
    
    if existing_temp_val:
        source_ids = list(existing_temp_val.get("source_evidence_ids") or [])
        is_diag = existing_temp_val.get("diagnostic_only", False)
        flags = list(existing_temp_val.get("flags", []))
        
        if not source_ids:
            is_diag = True
            if "weather_missing_source_evidence_ids" not in flags:
                flags.append("weather_missing_source_evidence_ids")
        
        context.stress_evidence_context["temp_max"] = _build_weather_feature(
            val=existing_temp_val.get("value"),
            unit="C",
            source_evidence_ids=source_ids,
            source_family="environment",
            normalized_from=existing_key,
            is_diagnostic=is_diag,
            flags=flags
        )
    else:
        ts_val, ts_key = _find_latest_in_timeseries(["temp_max", "temperature_max", "tmean"])
        if ts_val is not None:
            context.stress_evidence_context["temp_max"] = _build_weather_feature(
                val=ts_val,
                unit="C",
                source_evidence_ids=[],
                source_family="environment",
                normalized_from=ts_key,
                is_diagnostic=True,
                flags=["weather_missing_source_evidence_ids", "weather_normalizer_fallback"]
            )

    # 3. VPD
    vpd_keys = ["vpd", "vapor_pressure_deficit"]
    existing_vpd_val, existing_key = _find_in_context([context.stress_evidence_context, context.operational_context], vpd_keys)
    
    if existing_vpd_val:
        source_ids = list(existing_vpd_val.get("source_evidence_ids") or [])
        is_diag = existing_vpd_val.get("diagnostic_only", False)
        flags = list(existing_vpd_val.get("flags", []))
        
        if not source_ids:
            is_diag = True
            if "weather_missing_source_evidence_ids" not in flags:
                flags.append("weather_missing_source_evidence_ids")
        
        context.stress_evidence_context["vpd"] = _build_weather_feature(
            val=existing_vpd_val.get("value"),
            unit="kPa",
            source_evidence_ids=source_ids,
            source_family="environment",
            normalized_from=existing_key,
            is_diagnostic=is_diag,
            flags=flags
        )
    else:
        ts_val, ts_key = _find_latest_in_timeseries(["vpd", "vapor_pressure_deficit"])
        if ts_val is not None:
            context.stress_evidence_context["vpd"] = _build_weather_feature(
                val=ts_val,
                unit="kPa",
                source_evidence_ids=[],
                source_family="environment",
                normalized_from=ts_key,
                is_diagnostic=True,
                flags=["weather_missing_source_evidence_ids", "weather_normalizer_fallback"]
            )

    # 4. ET0
    et_keys = ["et0_mm", "et0"]
    existing_et_val, existing_key = _find_in_context([context.stress_evidence_context, context.operational_context], et_keys)
    
    if existing_et_val:
        source_ids = list(existing_et_val.get("source_evidence_ids") or [])
        is_diag = existing_et_val.get("diagnostic_only", False)
        flags = list(existing_et_val.get("flags", []))
        
        if not source_ids:
            is_diag = True
            if "weather_missing_source_evidence_ids" not in flags:
                flags.append("weather_missing_source_evidence_ids")
        
        context.stress_evidence_context["et0_mm"] = _build_weather_feature(
            val=existing_et_val.get("value"),
            unit="mm",
            source_evidence_ids=source_ids,
            source_family="environment",
            normalized_from=existing_key,
            is_diagnostic=is_diag,
            flags=flags
        )
    else:
        ts_val, ts_key = _find_latest_in_timeseries(["et0", "et0_mm"])
        if ts_val is not None:
            context.stress_evidence_context["et0_mm"] = _build_weather_feature(
                val=ts_val,
                unit="mm",
                source_evidence_ids=[],
                source_family="environment",
                normalized_from=ts_key,
                is_diagnostic=True,
                flags=["weather_missing_source_evidence_ids", "weather_normalizer_fallback"]
            )
