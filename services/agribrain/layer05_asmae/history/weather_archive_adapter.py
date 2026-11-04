# -*- coding: utf-8 -*-
"""Canonical, lineage-preserving weather archive adapter.

Historical/reanalysis evidence and forecasts are deliberately kept in separate
series.  Forecast records can drive an explicitly future process step, but they
must never be mistaken for historical truth during initialization or replay.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional
import os


def _reconcile_record_with_native_acquisition(
    acq_id: str,
    record_date: str,
    record_values: Mapping[str, Any],
    record_reality: str,
    record_role: str = "",
) -> bool:
    """Independently verify receipt screening and reconcile date, role, and physical values with stored CAS payload."""
    result = _reconcile_variable_evidence(
        acq_id, record_date, record_values, record_reality, record_role,
    )
    if result is None:
        return False
    # Legacy boolean: True only when every non-None core variable is verified.
    for var in CORE_VARIABLES:
        if record_values.get(var) is not None and not result.get(var, False):
            return False
    return True


# Mapping from normalized variable name to CAS daily payload key.
_CAS_VARIABLE_MAP: Dict[str, str] = {
    "precipitation_mm": "precipitation_sum",
    "temp_min_c": "temperature_2m_min",
    "temp_max_c": "temperature_2m_max",
    "et0_mm": "et0_fao_evapotranspiration",
}


def _reconcile_variable_evidence(
    acq_id: str,
    record_date: str,
    record_values: Mapping[str, Any],
    record_reality: str,
    record_role: str = "",
) -> Optional[Dict[str, bool]]:
    """Per-variable CAS reconciliation.

    Returns a dict mapping each core variable name to ``True`` if the record
    value matches the CAS payload within tolerance, ``False`` if it diverges,
    or ``None`` if the acquisition cannot be structurally verified at all
    (screening failure, wrong product, wrong date, etc.).
    """
    if not acq_id or not isinstance(acq_id, str):
        return None
    if acq_id.startswith("weather:"):
        return None
    root = (
        os.getenv("AKALORIS_LAYER0_NATIVE_WEATHER_EVIDENCE_ROOT", "").strip()
        or os.getenv("AKALORIS_LAYER0_NATIVE_EVIDENCE_ROOT", "").strip()
    )
    if not root:
        return None

    try:
        from services.agribrain.layer0.native_issuer.weather_acquisition_evidence import (
            NativeWeatherEvidenceStore,
        )
        from services.agribrain.layer0.native_issuer.weather_qualifier import (
            screen_native_weather_receipt,
            WeatherScreenStatus,
        )
        from services.agribrain.layer0.native_issuer.weather_product_registry import (
            WeatherProductId,
        )

        store = NativeWeatherEvidenceStore(root)
        receipt = store.verified_cache_receipt(acq_id)
        if not receipt or not receipt.response_sha256:
            return None

        # 1. Scientific Screening Verification
        screen = screen_native_weather_receipt(receipt, store)
        if screen.status is not WeatherScreenStatus.SCREENED_NATIVE_QA:
            return None

        # 2. Product & Role Consistency
        if record_reality == "reanalysis_archive":
            if receipt.product_id != WeatherProductId.OPEN_METEO_HISTORICAL_REANALYSIS.value:
                return None
            if record_role and record_role not in ("REANALYSIS_MODEL", "HISTORICAL_REANALYSIS"):
                return None
        elif record_reality == "forecast":
            if receipt.product_id not in (
                WeatherProductId.OPEN_METEO_LIVE_FORECAST.value,
                WeatherProductId.OPENWEATHER_ONECALL_3_0.value,
            ):
                return None
            if record_role and record_role != "FORECAST_MODEL":
                return None

        # 3. Date Reconciliation
        req_start, req_end = receipt.valid_interval
        if req_start and req_end:
            if not (req_start <= record_date <= req_end):
                return None

        # 4. Load raw CAS payload and reconcile physical values for record_date
        raw_bytes = store.read_response_bytes(receipt.object_id)
        cas_payload = json.loads(raw_bytes.decode("utf-8"))
        if not isinstance(cas_payload, dict):
            return None

        daily = cas_payload.get("daily")
        if not isinstance(daily, dict):
            return None

        times = daily.get("time")
        if not isinstance(times, list) or record_date not in times:
            return None

        idx = times.index(record_date)

        # 5. Per-variable reconciliation
        var_result: Dict[str, bool] = {}
        for var_name, cas_key in _CAS_VARIABLE_MAP.items():
            rec_val = record_values.get(var_name)
            if rec_val is None:
                # Variable not present in record -- nothing to verify or deny.
                var_result[var_name] = False
                continue
            cas_series = daily.get(cas_key)
            if not isinstance(cas_series, list) or idx >= len(cas_series):
                var_result[var_name] = False
                continue
            cas_val = cas_series[idx]
            if cas_val is None:
                var_result[var_name] = False
                continue
            if abs(float(rec_val) - float(cas_val)) > 1e-3:
                var_result[var_name] = False
            else:
                var_result[var_name] = True

        return var_result
    except Exception:
        return None



VARIABLES = (
    "temp_min_c",
    "temp_max_c",
    "precipitation_mm",
    "et0_mm",
    "humidity_mean_pct",
    "wind_speed_m_s",
)
CORE_VARIABLES = ("temp_min_c", "temp_max_c", "precipitation_mm", "et0_mm")


def stable_value_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _as_mapping(value: Any) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return {}


def _first_non_none(record: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in record and record[key] is not None:
            return record[key]
    return None


def _finite_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _consensus_value(variables: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key not in variables:
            continue
        entry = _as_mapping(variables[key])
        if entry:
            value = _first_non_none(entry, "selected_value", "value")
        else:
            value = variables[key]
        if value is not None:
            return value
    return None


def _unwrap_records(raw_weather: Any) -> List[Any]:
    if raw_weather is None:
        return []
    if hasattr(raw_weather, "evidence_records"):
        records = getattr(raw_weather, "evidence_records")
        return list(records or [])
    if isinstance(raw_weather, Mapping):
        for key in ("evidence_records", "weather_records", "weather_consensus", "records"):
            if key in raw_weather:
                value = raw_weather.get(key)
                return list(value or []) if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else []
        daily = raw_weather.get("daily")
        if isinstance(daily, Mapping):
            dates = list(daily.get("time") or [])
            records = []
            for index, day in enumerate(dates):
                row: Dict[str, Any] = {"date": day, "data_kind": raw_weather.get("data_kind", "unknown")}
                for key, values in daily.items():
                    if key == "time" or not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
                        continue
                    row[key] = values[index] if index < len(values) else None
                records.append(row)
            return records
        # A date-keyed already-normalized series is also accepted.
        if raw_weather and all(isinstance(value, Mapping) for value in raw_weather.values()):
            return [{"date": str(day), **dict(value)} for day, value in raw_weather.items()]
        return []
    if isinstance(raw_weather, Sequence) and not isinstance(raw_weather, (str, bytes)):
        return list(raw_weather)
    return []


def _record_reality(record: Mapping[str, Any]) -> str:
    from services.agribrain.layer0.environment.weather.source_roles import (
        classify_weather_record_admission,
    )
    admission = classify_weather_record_admission(record)
    if admission in ("reanalysis_archive", "forecast"):
        return admission
    return "unknown"


def _normalize_record(raw: Any) -> Optional[Dict[str, Any]]:
    outer = _as_mapping(raw)
    if not outer:
        return None
    payload = _as_mapping(outer.get("payload"))
    record = {**outer, **payload}
    # Admission uses the original outer+payload envelope; flattening first
    # would erase denied roles carried only by the outer packet.
    outer_reality = _record_reality(outer)
    variables = _as_mapping(record.get("variable_consensus") or record.get("variables"))
    date = str(_first_non_none(record, "date", "timestamp", "valid_time") or "")[:10]
    if len(date) != 10:
        return None

    values = {
        "temp_min_c": _finite_float(_first_non_none(record, "temp_min_c", "temp_min", "tmin_c", "temperature_2m_min")),
        "temp_max_c": _finite_float(_first_non_none(record, "temp_max_c", "temp_max", "tmax_c", "temperature_2m_max")),
        "precipitation_mm": _finite_float(_first_non_none(record, "precipitation_mm", "precipitation", "precipitation_sum", "precipitation_sum_mm")),
        "et0_mm": _finite_float(_first_non_none(record, "et0_mm", "et0", "et0_sum_mm", "et0_fao_evapotranspiration", "reference_et0_mm")),
        "humidity_mean_pct": _finite_float(_first_non_none(record, "humidity_mean_pct", "humidity", "relative_humidity_mean", "relative_humidity_mean_pct", "relative_humidity_2m")),
        "wind_speed_m_s": _finite_float(_first_non_none(record, "wind_speed_m_s", "wind_speed", "wind_speed_max", "wind_speed_10m_max", "wind_speed_mean_10m_ms")),
    }
    consensus_aliases = {
        "temp_min_c": ("temp_min", "tmin_c", "temperature_2m_min"),
        "temp_max_c": ("temp_max", "tmax_c", "temperature_2m_max"),
        "precipitation_mm": ("precipitation_sum", "precipitation_sum_mm", "precipitation"),
        "et0_mm": ("et0_mm", "et0_sum_mm", "reference_et0_mm"),
        "humidity_mean_pct": ("relative_humidity_mean", "relative_humidity_mean_pct", "humidity_mean_pct"),
        "wind_speed_m_s": ("wind_speed_max", "wind_speed_mean_10m_ms", "wind_speed_10m_max"),
    }
    for key, aliases in consensus_aliases.items():
        if values[key] is None:
            values[key] = _finite_float(_consensus_value(variables, *aliases))

    source_role = str(_first_non_none(record, "source_role", "role", "data_role") or "").upper()
    reality = _record_reality(record)
    if reality == "unknown" or reality != outer_reality:
        # Do not permit an unqualified provider 'current' context to
        # enter historical ASMAE weather as observed truth.
        return None

    native_ids = record.get("native_acquisition_ids") or []
    if isinstance(native_ids, str):
        native_ids = [native_ids]

    # Per-variable evidence: maps variable name -> list of acquisition IDs that verified it
    variable_evidence: Dict[str, List[str]] = {var: [] for var in CORE_VARIABLES}
    verified_native_ids: List[str] = []

    for raw_id in native_ids:
        aid = str(raw_id)
        var_ev = _reconcile_variable_evidence(aid, date, values, reality, source_role)
        if var_ev is None:
            continue
        any_verified = False
        for var_name, verified in var_ev.items():
            if verified:
                variable_evidence[var_name].append(aid)
                any_verified = True
        if any_verified:
            verified_native_ids.append(aid)

    raw_ev_ids = record.get("evidence_ids")
    if isinstance(raw_ev_ids, str):
        raw_ev_ids = [raw_ev_ids]
    elif not isinstance(raw_ev_ids, list):
        single = _first_non_none(record, "evidence_id", "content_hash", "packet_id")
        raw_ev_ids = [str(single)] if single else []

    final_evidence_ids = list(verified_native_ids)
    if not final_evidence_ids:
        for eid in raw_ev_ids:
            aid = str(eid)
            var_ev = _reconcile_variable_evidence(aid, date, values, reality, source_role)
            if var_ev is None:
                continue
            any_verified = False
            for var_name, verified in var_ev.items():
                if verified:
                    variable_evidence[var_name].append(aid)
                    any_verified = True
            if any_verified:
                final_evidence_ids.append(aid)

    authority = str(record.get("authority") or "")

    synthetic_fallback = "weather:" + stable_value_hash({"date": date, "reality": reality, **values})
    if not final_evidence_ids:
        if native_ids:
            final_evidence_ids = [synthetic_fallback]
        else:
            clean_raw = [str(eid) for eid in raw_ev_ids if not str(eid).startswith("native_")]
            final_evidence_ids = clean_raw if clean_raw else [synthetic_fallback]

    reconciled_native = [
        str(x) for x in final_evidence_ids
        if _reconcile_record_with_native_acquisition(
            str(x), date, values, reality, source_role
        )
    ]

    # All-variables-verified: True only when every present core variable has
    # at least one verified acquisition backing it.
    all_vars_verified = all(
        bool(variable_evidence.get(var))
        for var in CORE_VARIABLES
        if values.get(var) is not None
    ) and any(values.get(var) is not None for var in CORE_VARIABLES)

    normalized = {
        **values,
        "date": date,
        "source_reality": reality,
        "evidence_ids": final_evidence_ids,
        "native_evidence_ids": reconciled_native,
        "variable_evidence": variable_evidence,
        "all_variables_verified": all_vars_verified,
        "authority_refs": [authority] if authority else [],
        "overall_confidence": _finite_float(record.get("overall_confidence")),
    }
    return normalized


def _merge_day(existing: Optional[Dict[str, Any]], incoming: Dict[str, Any]) -> Dict[str, Any]:
    if existing is None:
        return incoming
    # Cross-provenance daily merge is strictly prohibited to prevent model-derived
    # variables from inheriting observational reality or cross-role contamination.
    if existing.get("source_reality") != incoming.get("source_reality"):
        raise ValueError(
            f"cross_provenance_daily_merge_prohibited: cannot merge {existing.get('source_reality')} "
            f"and {incoming.get('source_reality')} for date {incoming.get('date')}"
        )
    merged = dict(existing)

    # Per-variable evidence: when filling a None field from incoming, use
    # incoming's variable evidence for that field, NOT existing's evidence.
    existing_var_ev = existing.get("variable_evidence") or {}
    incoming_var_ev = incoming.get("variable_evidence") or {}
    merged_var_ev: Dict[str, List[str]] = {}
    for var in CORE_VARIABLES:
        merged_var_ev[var] = list(existing_var_ev.get(var) or [])

    for key in VARIABLES:
        if merged.get(key) is None:
            incoming_val = incoming.get(key)
            merged[key] = incoming_val
            # Variable came from incoming record: use incoming's evidence for this var.
            if incoming_val is not None and key in merged_var_ev:
                merged_var_ev[key] = list(incoming_var_ev.get(key) or [])

    merged["evidence_ids"] = sorted(set(existing.get("evidence_ids", [])) | set(incoming.get("evidence_ids", [])))
    merged["authority_refs"] = sorted(set(existing.get("authority_refs", [])) | set(incoming.get("authority_refs", [])))
    merged["variable_evidence"] = merged_var_ev

    # Recompute native_evidence_ids: only IDs that back ALL present core variables.
    all_acq_ids = sorted(set(existing.get("native_evidence_ids", [])) | set(incoming.get("native_evidence_ids", [])))
    merged["native_evidence_ids"] = [
        aid for aid in all_acq_ids
        if all(
            aid in merged_var_ev.get(var, [])
            for var in CORE_VARIABLES
            if merged.get(var) is not None
        )
    ]

    # Recompute all_variables_verified from merged variable evidence.
    merged["all_variables_verified"] = all(
        bool(merged_var_ev.get(var))
        for var in CORE_VARIABLES
        if merged.get(var) is not None
    ) and any(merged.get(var) is not None for var in CORE_VARIABLES)

    return merged


def _empty_archive() -> Dict[str, Any]:
    return {
        "weather_archive_status": "unavailable",
        "weather_source_reality": "missing",
        "weather_daily_series": {},
        "weather_forecast_series": {},
        "weather_archive_hash": stable_value_hash({}),
        "missing_variables": list(VARIABLES),
        "variable_completeness": {key: 0.0 for key in VARIABLES},
        "weather_evidence_ids": [],
    }


def normalize_weather_archive(raw_weather: Any) -> Dict[str, Any]:
    """Normalize weather without truth/forecast mixing or zero-value loss."""
    normalized = [row for row in (_normalize_record(item) for item in _unwrap_records(raw_weather)) if row]
    if not normalized:
        return _empty_archive()

    historical: Dict[str, Dict[str, Any]] = {}
    forecast: Dict[str, Dict[str, Any]] = {}
    for row in normalized:
        target = forecast if row["source_reality"] == "forecast" else historical
        target[row["date"]] = _merge_day(target.get(row["date"]), row)

    denominator = len(historical)
    counts = {key: sum(1 for row in historical.values() if row.get(key) is not None) for key in VARIABLES}
    completeness = {key: round(count / denominator, 3) if denominator else 0.0 for key, count in counts.items()}
    missing = [key for key, count in counts.items() if count == 0]
    if denominator and all(completeness[key] == 1.0 for key in CORE_VARIABLES):
        status = "available"
    elif denominator and any(completeness[key] > 0.0 for key in CORE_VARIABLES):
        status = "partial"
    else:
        status = "unavailable"

    realities = {row["source_reality"] for row in historical.values()}
    if realities == {"observed_archive"}:
        reality = "observed_archive"
    elif realities == {"reanalysis_archive"}:
        reality = "reanalysis_archive"
    elif realities:
        reality = "mixed_historical"
    else:
        reality = "forecast_only" if forecast else "missing"

    evidence_ids = sorted({evidence_id for row in normalized for evidence_id in row.get("evidence_ids", [])})
    # After merging, collect native evidence from merged daily rows, not raw normalized.
    all_rows = list(historical.values()) + list(forecast.values())
    verified_native_ids = sorted({
        acq_id for row in all_rows for acq_id in row.get("native_evidence_ids", [])
    })
    # native_evidence_verified requires every merged row to have all its
    # present core variables backed by at least one verified acquisition.
    all_rows_verified = (
        bool(all_rows)
        and all(row.get("all_variables_verified", False) for row in all_rows)
    )
    hash_payload = {"historical": historical, "forecast": forecast, "evidence_ids": evidence_ids}
    return {
        "weather_archive_status": status,
        "weather_source_reality": reality,
        "weather_daily_series": historical,
        "weather_forecast_series": forecast,
        "weather_archive_hash": stable_value_hash(hash_payload),
        "missing_variables": missing,
        "variable_completeness": completeness,
        "weather_evidence_ids": evidence_ids,
        "weather_native_evidence_ids": verified_native_ids,
        "native_evidence_verified": all_rows_verified,
    }
