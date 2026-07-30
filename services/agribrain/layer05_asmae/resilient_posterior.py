"""Plot-level resilient posterior estimation for ASMAE no-scene runs.

This module deliberately produces no spatial surfaces.  It conditions only
states supported by certified archive state, plot-level temporal observations,
or explicit numeric process priors.  An unsupported state is represented by a
null mean/sigma; physical-range midpoints are never emitted as estimates.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from .config import STATE_BOUNDS, STATE_NAMES


ARCHIVE_POSTERIOR_CONTRACT_VERSION = "asmae_archive_posterior_v1"
_VALID_ARCHIVE_STATUSES = {
    "certified",
    "validated",
    "success",
    "passed",
    "production_validated",
}


def _clip(state: str, value: float) -> float:
    lo, hi = STATE_BOUNDS[state]
    return max(lo, min(hi, float(value)))


def _finite_scalar(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        value = float(value)
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        for key in ("mean", "value", "estimate", "current", "median"):
            if key in value:
                found = _finite_scalar(value[key])
                if found is not None:
                    return found
        return None
    if isinstance(value, (list, tuple)):
        values = [v for item in value if (v := _finite_scalar(item)) is not None]
        return sum(values) / len(values) if values else None
    return None


def _first_finite(record: Mapping[str, Any], *keys: str) -> Optional[float]:
    """Return the first finite value while preserving meaningful zeroes."""
    for key in keys:
        if key in record:
            value = _finite_scalar(record[key])
            if value is not None:
                return value
    return None


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "__dict__"):
        return {
            key: item for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return {}


def _parse_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                return None
    return None


def _parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime.min.time())
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = datetime.combine(date.fromisoformat(value[:10]), datetime.min.time())
            except ValueError:
                return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _crop_identity(value: Any) -> str:
    data = _as_dict(value)
    return str(data.get("crop") or data.get("crop_type") or data.get("name") or "").strip().lower()


def validate_archive_posterior(
    archive: Any,
    *,
    geometry_hash: str,
    crop_context: Any,
) -> Tuple[bool, List[str]]:
    """Validate the complete historical-posterior authority contract."""
    data = _as_dict(archive)
    reasons: List[str] = []
    required = (
        "contract_version",
        "state_means",
        "state_covariance",
        "last_update_date",
        "geometry_hash",
        "crop_context",
        "state_support_ledger",
        "content_distinct_scene_ids",
        "historical_validation_status",
    )
    for key in required:
        if key not in data:
            reasons.append(f"missing_{key}")

    if data.get("contract_version") != ARCHIVE_POSTERIOR_CONTRACT_VERSION:
        reasons.append("unsupported_contract_version")
    if not geometry_hash or data.get("geometry_hash") != geometry_hash:
        reasons.append("geometry_hash_mismatch")

    expected_crop = _crop_identity(crop_context)
    archive_crop = _crop_identity(data.get("crop_context"))
    if (
        expected_crop not in ("", "unknown")
        and archive_crop not in ("", "unknown")
        and expected_crop != archive_crop
    ):
        reasons.append("crop_context_mismatch")

    if str(data.get("historical_validation_status", "")).lower() not in _VALID_ARCHIVE_STATUSES:
        reasons.append("historical_validation_not_accepted")
    if _parse_date(data.get("last_update_date")) is None:
        reasons.append("invalid_last_update_date")

    means = _as_dict(data.get("state_means"))
    supported_means = {
        state: _finite_scalar(means.get(state))
        for state in STATE_NAMES
    }
    if not any(value is not None for value in supported_means.values()):
        reasons.append("no_supported_state_means")

    covariance = data.get("state_covariance")
    covariance_valid = False
    if isinstance(covariance, Mapping):
        covariance_valid = any(
            (_finite_scalar(covariance.get(state)) or 0.0) > 0.0
            for state in STATE_NAMES
        )
    elif isinstance(covariance, (list, tuple)) and len(covariance) == len(STATE_NAMES):
        covariance_valid = all(
            isinstance(row, (list, tuple)) and len(row) == len(STATE_NAMES)
            for row in covariance
        )
    if not covariance_valid:
        reasons.append("invalid_state_covariance")

    ledger = data.get("state_support_ledger")
    if not isinstance(ledger, (Mapping, list, tuple)) or not ledger:
        reasons.append("missing_state_support_ledger")

    scene_ids = data.get("content_distinct_scene_ids")
    if not isinstance(scene_ids, (list, tuple)):
        reasons.append("invalid_content_distinct_scene_ids")
    else:
        distinct = {str(item).strip() for item in scene_ids if str(item).strip()}
        if len(distinct) < 2:
            reasons.append("insufficient_content_distinct_scenes")

    return not reasons, reasons


def _archive_variance(covariance: Any, state: str) -> Optional[float]:
    if isinstance(covariance, Mapping):
        raw = covariance.get(state)
        if isinstance(raw, Mapping):
            raw = raw.get(state, raw.get("variance"))
        value = _finite_scalar(raw)
        return value if value is not None and value > 0.0 else None
    if isinstance(covariance, (list, tuple)):
        index = STATE_NAMES.index(state)
        try:
            value = _finite_scalar(covariance[index][index])
            return value if value is not None and value > 0.0 else None
        except (IndexError, TypeError):
            return None
    return None


def _archive_support(ledger: Any, state: str) -> List[str]:
    entry: Any = None
    if isinstance(ledger, Mapping):
        entry = ledger.get(state)
    elif isinstance(ledger, (list, tuple)):
        entry = next(
            (item for item in ledger if _as_dict(item).get("state") == state),
            None,
        )
    data = _as_dict(entry)
    support = (
        data.get("source_feature_ids")
        or data.get("support")
        or data.get("sources")
        or data.get("observations")
        or []
    )
    if isinstance(support, str):
        support = [support]
    if not isinstance(support, (list, tuple)):
        support = []
    return [str(item) for item in support if str(item).strip()]


def _records_as_of(records: List[Dict[str, Any]], as_of: Any) -> List[Dict[str, Any]]:
    if as_of is None:
        return records
    cutoff = _parse_datetime(as_of)
    if cutoff is None:
        return []
    frozen = []
    for row in records:
        raw_date = (
            row.get('acquired_at') or row.get('datetime')
            or row.get('timestamp') or row.get('date')
        )
        stamp = _parse_datetime(raw_date)
        if stamp is not None and stamp <= cutoff:
            frozen.append(row)
    return frozen


def _weather_records(inp: Any, as_of: Any = None) -> List[Dict[str, Any]]:
    raw = getattr(inp, "weather_daily_series", {}) or {}
    records: List[Dict[str, Any]] = []
    if isinstance(raw, Mapping):
        for key, value in raw.items():
            row = _as_dict(value)
            row.setdefault("date", str(key))
            records.append(row)
    elif isinstance(raw, (list, tuple)):
        records = [_as_dict(item) for item in raw]
    return _records_as_of([item for item in records if item], as_of)


def _propagate_archive_state(
    state: str,
    mean: float,
    variance: float,
    age_days: int,
    inp: Any,
    as_of: Any = None,
) -> Tuple[float, float, List[str]]:
    """Age-propagate a certified state and inflate its covariance."""
    support: List[str] = ["certified_archive_posterior"]
    age = max(0, age_days)
    lo, hi = STATE_BOUNDS[state]
    span = max(hi - lo, 1e-6)
    process_rate = {
        "vigor": 0.00035,
        "lai": 0.00055,
        "chlorophyll": 0.00045,
        "canopy_water": 0.0008,
        "root_zone_water": 0.00065,
        "surface_wetness_event": 0.0015,
        "structure": 0.00025,
        "bare_soil_fraction": 0.0003,
        "salinity_stress": 0.0002,
        "thermal_stress": 0.0012,
        "biotic_confounder_risk": 0.0006,
        "phenology_progress": 0.0004,
        "stress_memory": 0.0005,
    }.get(state, 0.0005)
    variance = max(variance, 1e-9) + age * process_rate * (span ** 2)

    weather = _weather_records(inp, as_of)
    if weather and state in {"root_zone_water", "canopy_water", "thermal_stress", "phenology_progress", "stress_memory"}:
        recent = weather[-min(len(weather), max(age, 1), 30):]
        rain = sum(
            value for row in recent
            if (value := _first_finite(row, "precipitation_mm", "precipitation", "rainfall_mm", "rain")) is not None
        )
        et0 = sum(
            value for row in recent
            if (value := _first_finite(row, "et0_mm", "et0", "evapotranspiration")) is not None
        )
        tmax_values = [
            value for row in recent
            if (value := _first_finite(row, "temp_max_c", "temp_max", "temperature_max", "tmax")) is not None
        ]
        if state == "root_zone_water":
            mean += (rain - et0) / 250.0
        elif state == "canopy_water":
            mean += (rain - et0) / 160.0
        elif state == "thermal_stress" and tmax_values:
            crop = _as_dict(getattr(inp, "crop_context", {}))
            optimum = _finite_scalar(crop.get("t_opt")) or 25.0
            maximum = max(_finite_scalar(crop.get("t_max")) or 40.0, optimum + 1.0)
            observed = max(tmax_values)
            weather_stress = max(0.0, min(1.0, (observed - optimum) / (maximum - optimum)))
            mean = 0.65 * mean + 0.35 * weather_stress
        elif state == "phenology_progress":
            tmean = [
                value for row in recent
                if (value := _first_finite(row, "temp_mean_c", "tmean", "temperature_mean")) is not None
            ]
            if tmean:
                base = _finite_scalar(_as_dict(getattr(inp, "crop_context", {})).get("t_base")) or 5.0
                mean += sum(max(0.0, value - base) for value in tmean) / 1800.0
        elif state == "stress_memory":
            mean *= math.exp(-age / 45.0)
        support.append("weather_process_propagation")

    return _clip(state, mean), variance, support


def _normalize_timeseries(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, Mapping):
        for key in ("records", "series", "values", "data", "plot_timeseries"):
            if key in value:
                return _normalize_timeseries(value[key])
        rows = []
        for key, item in value.items():
            row = _as_dict(item)
            if row:
                row.setdefault("date", str(key))
                rows.append(row)
        return rows
    if isinstance(value, (list, tuple)):
        return [_as_dict(item) for item in value if _as_dict(item)]
    return []


_SIGNAL_ALIASES = {
    "ndvi": ("ndvi", "ndvi_clean", "ndvi_interpolated", "NDVI", "NDVI_CLEAN"),
    "evi": ("evi", "EVI"),
    "ndre": ("ndre", "NDRE"),
    "reip": ("reip", "REIP"),
    "ndmi": ("ndmi", "NDMI"),
    "vv": ("vv", "sar_vv", "VV"),
    "vh": ("vh", "sar_vh", "VH"),
}


def _extract_signal(row: Mapping[str, Any], signal: str) -> Optional[float]:
    # 1. Top-level aliases (fast path)
    for key in _SIGNAL_ALIASES[signal]:
        if key in row:
            value = _finite_scalar(row[key])
            if value is not None:
                return value
    # 2. Payload-nested look-through: supports ndvi_mean, evi_mean, etc.
    payload = row.get("payload")
    if isinstance(payload, Mapping):
        for key in _SIGNAL_ALIASES[signal]:
            if key in payload:
                value = _finite_scalar(payload[key])
                if value is not None:
                    return value
        # {signal}_mean convention
        mean_key = f"{signal}_mean"
        value = _finite_scalar(payload.get(mean_key))
        if value is not None:
            return value
    return None


def _extract_signal_uncertainty(row: Mapping[str, Any], signal: str) -> Optional[float]:
    direct_keys = (
        f"{signal}_uncertainty",
        f"{signal}_sigma",
        f"{signal}_stddev",
        "measurement_uncertainty",
        "observation_uncertainty",
        "uncertainty",
        "sigma",
        "stddev",
    )
    for key in direct_keys:
        if key not in row:
            continue
        raw = row[key]
        if isinstance(raw, Mapping):
            candidates = (signal, *_SIGNAL_ALIASES[signal])
            raw = next((raw[name] for name in candidates if name in raw), None)
        value = _finite_scalar(raw)
        if value is not None and value > 0.0:
            return value
    # Payload look-through for uncertainty
    payload = row.get("payload")
    if isinstance(payload, Mapping):
        for key in direct_keys:
            if key in payload:
                raw = payload[key]
                if not isinstance(raw, Mapping):
                    value = _finite_scalar(raw)
                    if value is not None and value > 0.0:
                        return value
    return None


def _weighted_temporal_slope(
    observations: List[Tuple[datetime, float, float, str]],
) -> float:
    if len(observations) < 2:
        return 0.0
    origin = observations[0][0]
    xs = [(stamp - origin).total_seconds() / 86400.0 for stamp, _, _, _ in observations]
    weights = [1.0 / max(measurement_variance, 1e-9) for _, _, measurement_variance, _ in observations]
    weight_sum = sum(weights)
    if weight_sum <= 0.0:
        return 0.0
    x_bar = sum(weight * x for weight, x in zip(weights, xs)) / weight_sum
    y_bar = sum(weight * item[1] for weight, item in zip(weights, observations)) / weight_sum
    denominator = sum(weight * ((x - x_bar) ** 2) for weight, x in zip(weights, xs))
    if denominator <= 1e-12:
        return 0.0
    numerator = sum(
        weight * (x - x_bar) * (item[1] - y_bar)
        for weight, x, item in zip(weights, xs, observations)
    )
    return numerator / denominator


def _signal_estimate(records: List[Dict[str, Any]], signal: str) -> Optional[Dict[str, Any]]:
    dated_observations: List[Tuple[datetime, float, float, str]] = []
    undated_observations: List[Tuple[float, float]] = []
    explicit_uncertainty_count = 0
    for row in records:
        value = _extract_signal(row, signal)
        if value is None:
            continue
        quality = _finite_scalar(row.get("quality") or row.get("qa_score") or row.get("valid_fraction"))
        quality = max(0.15, min(1.0, quality if quality is not None else 0.65))
        uncertainty = _extract_signal_uncertainty(row, signal)
        if uncertainty is not None:
            measurement_variance = max(1e-8, uncertainty ** 2)
            explicit_uncertainty_count += 1
        else:
            measurement_variance = max(0.001, (1.0 - quality) * 0.08)
        raw_date = row.get("acquired_at") or row.get("datetime") or row.get("timestamp") or row.get("date")
        parsed_date = _parse_datetime(raw_date)
        if parsed_date is None:
            undated_observations.append((value, measurement_variance))
            continue
        dated_observations.append((parsed_date, value, measurement_variance, str(raw_date)))

    # Recursive temporal conditioning is chronological by contract. Undated
    # records may support a static estimate, but never influence trend.
    dated_observations.sort(key=lambda item: item[0])
    if not dated_observations and not undated_observations:
        return None

    if not dated_observations:
        weights = [1.0 / max(variance, 1e-9) for _, variance in undated_observations]
        total_weight = sum(weights)
        mean = sum(weight * item[0] for weight, item in zip(weights, undated_observations)) / total_weight
        return {
            "mean": mean,
            "variance": 1.0 / total_weight,
            "trend": 0.0,
            "trend_unit": "signal_units_per_day",
            "count": len(undated_observations),
            "dated_count": 0,
            "undated_count": len(undated_observations),
            "dates": [],
            "explicit_uncertainty_count": explicit_uncertainty_count,
        }

    first_stamp, mean, first_measurement_variance, _ = dated_observations[0]
    variance = max(1e-8, first_measurement_variance)
    previous_stamp = first_stamp
    for stamp, value, measurement_variance, _ in dated_observations[1:]:
        elapsed_days = max(1.0, (stamp - previous_stamp).total_seconds() / 86400.0)
        variance += 0.0025 * min(elapsed_days, 30.0)
        gain = variance / (variance + measurement_variance)
        mean = mean + gain * (value - mean)
        variance = max(1e-6, (1.0 - gain) * variance)
        previous_stamp = stamp
    trend = _weighted_temporal_slope(dated_observations)
    return {
        "mean": mean,
        "variance": variance,
        "trend": trend,
        "trend_unit": "signal_units_per_day",
        "count": len(dated_observations) + len(undated_observations),
        "dated_count": len(dated_observations),
        "undated_count": len(undated_observations),
        "dates": [item[3] for item in dated_observations],
        "explicit_uncertainty_count": explicit_uncertainty_count,
    }


def _timeseries_state_estimates(inp: Any, as_of: Any = None) -> Dict[str, Dict[str, Any]]:
    records = _normalize_timeseries(getattr(inp, "plot_timeseries", []))
    records = _records_as_of(records, as_of)
    signals = {name: _signal_estimate(records, name) for name in _SIGNAL_ALIASES}
    result: Dict[str, Dict[str, Any]] = {}

    ndvi = signals["ndvi"]
    evi = signals["evi"]
    optical = ndvi or evi
    if optical:
        sources = [name for name, estimate in (("NDVI", ndvi), ("EVI", evi)) if estimate]
        consistency = {
            "signals": sources,
            "status": "single_signal",
            "absolute_disagreement": None,
        }
        if ndvi and evi:
            ndvi_weight = 1.0 / max(ndvi["variance"], 1e-9)
            evi_weight = 1.0 / max(evi["variance"], 1e-9)
            value = (ndvi_weight * ndvi["mean"] + evi_weight * evi["mean"]) / (ndvi_weight + evi_weight)
            disagreement = abs(ndvi["mean"] - evi["mean"])
            optical_variance = (1.0 / (ndvi_weight + evi_weight)) + (disagreement ** 2) / 4.0
            optical_count = ndvi["count"] + evi["count"]
            consistency = {
                "signals": sources,
                "status": "consistent" if disagreement <= 0.20 else "cross_index_disagreement",
                "absolute_disagreement": disagreement,
            }
        else:
            value = optical["mean"]
            optical_variance = optical["variance"]
            optical_count = optical["count"]
        vigor = max(0.0, min(1.0, (value + 0.1) / 0.9))
        result["vigor"] = {
            "mean": vigor,
            "variance": max(0.0025, optical_variance),
            "status": "timeseries_conditioned",
            "support": sources,
            "observation_count": optical_count,
            "update_mode": "direct_temporal_filter",
            "cross_index_consistency": consistency,
        }
        lai = min(8.0, max(0.0, -2.2 * math.log(max(0.03, 1.0 - 0.92 * vigor))))
        result["lai"] = {
            "mean": lai,
            "variance": max(0.04, optical_variance * 18.0),
            "status": "timeseries_conditioned",
            "support": sources,
            "observation_count": optical_count,
            "update_mode": "indirect_physiology_mapping",
            "cross_index_consistency": consistency,
        }

    pigment = signals["ndre"] or signals["reip"]
    if pigment:
        source = "NDRE" if signals["ndre"] else "REIP"
        normalized = max(0.0, min(1.0, (pigment["mean"] + 0.05) / 0.65))
        result["chlorophyll"] = {
            "mean": normalized * 80.0,
            "variance": max(4.0, pigment["variance"] * 3200.0),
            "status": "timeseries_conditioned",
            "support": [source],
            "observation_count": pigment["count"],
            "update_mode": "direct_temporal_filter",
        }

    ndmi = signals["ndmi"]
    if ndmi:
        result["canopy_water"] = {
            "mean": max(0.0, min(1.0, (ndmi["mean"] + 1.0) / 2.0)),
            "variance": max(0.003, ndmi["variance"] / 4.0),
            "status": "timeseries_conditioned",
            "support": ["NDMI"],
            "observation_count": ndmi["count"],
            "update_mode": "direct_temporal_filter",
        }

    vv = signals["vv"]
    vh = signals["vh"]
    if vv:
        result["surface_wetness_event"] = {
            "mean": max(0.0, min(1.0, (vv["mean"] + 25.0) / 20.0)),
            "variance": max(0.005, vv["variance"] / 100.0),
            "status": "timeseries_conditioned",
            "support": ["S1_VV"],
            "observation_count": vv["count"],
            "update_mode": "direct_temporal_filter",
        }
    if vh:
        result["structure"] = {
            "mean": max(0.0, min(1.0, (vh["mean"] + 30.0) / 20.0)),
            "variance": max(0.005, vh["variance"] / 100.0),
            "status": "timeseries_conditioned",
            "support": ["S1_VH"],
            "observation_count": vh["count"],
            "update_mode": "direct_temporal_filter",
        }

    return result


def _lookup_numeric(context: Any, aliases: Iterable[str]) -> Optional[float]:
    wanted = {alias.lower() for alias in aliases}
    queue = [_as_dict(context)]
    seen = 0
    while queue and seen < 500:
        current = queue.pop(0)
        seen += 1
        for key, value in current.items():
            if str(key).lower() in wanted:
                found = _finite_scalar(value)
                if found is not None:
                    return found
            child = _as_dict(value)
            if child:
                queue.append(child)
    return None


def _prior_state_estimates(inp: Any, as_of: Any = None) -> Dict[str, Dict[str, Any]]:
    coarse = getattr(inp, "coarse_layer_outputs", {}) or {}
    soil = getattr(inp, "soil_context", {}) or {}
    result: Dict[str, Dict[str, Any]] = {}
    if as_of is not None:
        coarse = {}
    mappings = {
        "root_zone_water": ((soil, ("root_zone_water", "soil_moisture", "sm_10_40", "water_content")), (coarse, ("root_zone_water", "water_balance", "soil_moisture"))),
        "chlorophyll": ((coarse, ("chlorophyll_proxy", "chlorophyll")),),
        "salinity_stress": ((soil, ("salinity_stress", "salinity_risk", "salinity")), (coarse, ("salinity_risk", "salinity_stress"))),
        "biotic_confounder_risk": ((coarse, ("biotic_threat_risk", "outbreak_probability", "biotic_risk")),),
        "phenology_progress": ((coarse, ("growth_position", "phenology_progress")),),
        "stress_memory": ((coarse, ("climate_shock_risk", "stress_memory")),),
    }
    for state, sources in mappings.items():
        for context, aliases in sources:
            value = _lookup_numeric(context, aliases)
            if value is None:
                continue
            if state == "chlorophyll" and value <= 1.0:
                value *= 80.0
            result[state] = {
                "mean": _clip(state, value),
                "variance": ((STATE_BOUNDS[state][1] - STATE_BOUNDS[state][0]) * 0.30) ** 2,
                "status": "prior_constrained",
                "support": ["soil_context" if context is soil else "coarse_layer_prior"],
                "observation_count": 0,
                "update_mode": "numeric_process_prior",
            }
            break

    weather = _weather_records(inp, as_of)
    if weather:
        tmax = [
            value for row in weather[-14:]
            if (value := _finite_scalar(row.get("temp_max") or row.get("temperature_max") or row.get("tmax"))) is not None
        ]
        if tmax:
            crop = _as_dict(getattr(inp, "crop_context", {}))
            optimum = _finite_scalar(crop.get("t_opt")) or 25.0
            maximum = max(_finite_scalar(crop.get("t_max")) or 40.0, optimum + 1.0)
            stress = max(0.0, min(1.0, (max(tmax) - optimum) / (maximum - optimum)))
            result["thermal_stress"] = {
                "mean": stress,
                "variance": 0.04,
                "status": "prior_constrained",
                "support": ["weather_temperature_process"],
                "observation_count": len(tmax),
                "update_mode": "weather_process_model",
            }
    return result


def estimate_resilient_plot_posterior(inp: Any, as_of: Any = None) -> Dict[str, Any]:
    """Build the non-spatial posterior and its per-state evidence ledger."""
    archive = getattr(inp, "archive_posterior", {}) or {}
    valid_archive, archive_rejections = validate_archive_posterior(
        archive,
        geometry_hash=str(getattr(inp, "geometry_hash", "") or ""),
        crop_context=getattr(inp, "crop_context", {}),
    ) if archive else (False, ["archive_posterior_missing"])

    requested_as_of = as_of
    effective_as_of = _parse_datetime(requested_as_of)
    if effective_as_of is None:
        effective_as_of = _parse_datetime(getattr(inp, 'end_date', None))
    states: Dict[str, Dict[str, Any]] = {}
    if valid_archive:
        data = _as_dict(archive)
        means = _as_dict(data["state_means"])
        covariance = data["state_covariance"]
        support_ledger = data["state_support_ledger"]
        last_update = _parse_date(data["last_update_date"])
        as_of = getattr(inp, "end_date", None)
        as_of = as_of if isinstance(as_of, date) else date.today()
        age_days = max(0, (as_of - last_update).days) if last_update else 0
        if requested_as_of is not None and effective_as_of is not None:
            cutoff_date = effective_as_of.date()
            if last_update and last_update > cutoff_date:
                valid_archive = False
                archive_rejections.append('archive_postdates_as_of_cutoff')
            age_days = max(0, (cutoff_date - last_update).days) if last_update else 0
        for state in STATE_NAMES:
            if not valid_archive:
                break
            mean = _finite_scalar(means.get(state))
            variance = _archive_variance(covariance, state)
            support = _archive_support(support_ledger, state)
            if mean is None or variance is None or not support:
                continue
            mean, variance, process_support = _propagate_archive_state(
                state, _clip(state, mean), variance, age_days, inp,
                as_of=(effective_as_of if requested_as_of is not None else None),
            )
            states[state] = {
                "mean": mean,
                "variance": variance,
                "status": "archive_conditioned",
                "support": list(dict.fromkeys(support + process_support)),
                "observation_count": len(support),
                "update_mode": "certified_archive_age_propagation",
                "archive_age_days": age_days,
            }

    timeseries_states = _timeseries_state_estimates(
        inp, effective_as_of if requested_as_of is not None else None,
    )
    for state, temporal in timeseries_states.items():
        if state in states:
            prior = states[state]
            prior_var = max(float(prior["variance"]), 1e-9)
            obs_var = max(float(temporal["variance"]), 1e-9)
            gain = prior_var / (prior_var + obs_var)
            prior["mean"] = _clip(
                state,
                float(prior["mean"]) + gain * (float(temporal["mean"]) - float(prior["mean"])),
            )
            prior["variance"] = max(1e-9, (1.0 - gain) * prior_var)
            prior["status"] = "archive_timeseries_conditioned"
            prior["support"] = list(dict.fromkeys(prior["support"] + temporal["support"]))
            prior["observation_count"] += temporal["observation_count"]
            prior["update_mode"] = "scalar_kalman_archive_temporal_update"
            prior["kalman_gain"] = gain
        else:
            states[state] = temporal

    prior_states = _prior_state_estimates(
        inp, effective_as_of if requested_as_of is not None else None,
    )
    for state, prior in prior_states.items():
        states.setdefault(state, prior)

    has_archive_state = any("archive" in str(item.get("status")) for item in states.values())
    has_temporal_state = any("timeseries" in str(item.get("status")) for item in states.values())
    has_prior_state = any(item.get("status") == "prior_constrained" for item in states.values())
    crop_identity = _crop_identity(getattr(inp, "crop_context", {}))
    has_context_constraints = bool(
        crop_identity not in {"", "unknown"}
        or _as_dict(getattr(inp, "soil_context", {}))
        or list(getattr(inp, "management_events", []) or [])
    )
    if has_archive_state:
        availability = "ARCHIVE_CONDITIONED"
    elif has_temporal_state:
        availability = "TIMESERIES_CONDITIONED"
    elif has_prior_state or has_context_constraints:
        availability = "PRIOR_ONLY"
    else:
        availability = "UNAVAILABLE"

    posterior: Dict[str, Dict[str, Any]] = {}
    ledger: Dict[str, Dict[str, Any]] = {}
    normalized_sigmas: List[float] = []
    for state in STATE_NAMES:
        item = states.get(state)
        if item is None:
            posterior[state] = {
                "mean": None,
                "sigma": None,
                "status": "unsupported",
                "support": [],
                "reason": "no_state_specific_evidence",
                "spatial_support": "none",
            }
            ledger[state] = {
                "state": state,
                "support_status": "unsupported",
                "observation_relationship": "none",
                "accepted_update_count": 0,
                "source_feature_ids": [],
                "spatial_support": "none",
                "authority_ceiling": "DIAGNOSTIC",
                "block_reasons": ["no_state_specific_evidence"],
                "usable_for_field_approval": False,
            }
            continue

        mean = _clip(state, float(item["mean"]))
        sigma = math.sqrt(max(0.0, float(item["variance"])))
        lo, hi = STATE_BOUNDS[state]
        normalized_sigmas.append(min(1.0, sigma / max(hi - lo, 1e-9)))
        status_val = item["status"]
        if status_val in (
            "timeseries_conditioned",
            "archive_timeseries_conditioned",
            "archive_conditioned",
        ):
            status_val = "temporally_conditioned"
        posterior[state] = {
            "mean": round(mean, 6),
            "sigma": round(sigma, 6),
            "status": status_val,
            "support": item["support"],
            "spatial_support": "plot_level_only",
        }
        if "archive_age_days" in item:
            posterior[state]["archive_age_days"] = item["archive_age_days"]
        ledger[state] = {
            "state": state,
            "support_status": status_val,
            "observation_relationship": (
                "indirect" if int(item.get("observation_count", 0)) > 0 else "none"
            ),
            "accepted_update_count": int(item.get("observation_count", 0)),
            "source_feature_ids": item["support"],
            "spatial_support": "plot_level_only",
            "authority_ceiling": "DIAGNOSTIC",
            "block_reasons": (
                [] if int(item.get("observation_count", 0)) > 0 else ["prior_only"]
            ),
            "update_mode": item.get("update_mode"),
            "kalman_gain": round(float(item.get("kalman_gain", 0.0)), 6),
            "prior_variance": None,
            "posterior_variance": round(float(item["variance"]), 8),
            "information_gain": None,
            "usable_for_field_approval": False,
        }

    return {
        "state_availability": availability,
        "posterior_available": availability != "UNAVAILABLE",
        "plot_level_posterior": posterior,
        "state_support_ledger": ledger,
        "normalized_uncertainty": (
            round(sum(normalized_sigmas) / len(normalized_sigmas), 6)
            if normalized_sigmas else 1.0
        ),
        "archive_contract_valid": valid_archive,
        "archive_rejection_reasons": archive_rejections,
        "supported_state_count": len(states),
        "unsupported_state_count": len(STATE_NAMES) - len(states),
    }


def build_archive_posterior_contract(
    historical_output: Any,
    *,
    crop_context: Mapping[str, Any],
    scene_ids: Iterable[str],
    historical_validation_status: str,
    state_support_ledger: Mapping[str, Any],
) -> Dict[str, Any]:
    """Adapt the final Layer-0 historical RTS state to the ASMAE contract."""
    states = list(getattr(historical_output, "states_smoothed", []) or [])
    covariances = list(getattr(historical_output, "covariances_smoothed", []) or [])
    timestamps = list(getattr(historical_output, "timestamps", []) or [])
    if not states or not covariances or not timestamps:
        raise ValueError("historical smoother output is empty")

    vector = list(states[-1])
    covariance = covariances[-1]
    # Layer-0 historical state -> ASMAE state. Unsupported ASMAE states remain absent.
    mapping = {
        "lai": (0, 1.0),
        "structure": (1, 1.0),
        "surface_wetness_event": (2, 1.0),
        "root_zone_water": (3, 1.0),
        "stress_memory": (4, 1.0),
        "phenology_progress": (6, 0.25),
        "thermal_stress": (7, 1.0),
        "vigor": (8, 1.0),
    }
    state_means: Dict[str, float] = {}
    state_variances: Dict[str, float] = {}
    ledger: Dict[str, Any] = {}
    for state, (index, scale) in mapping.items():
        if index >= len(vector) or state not in state_support_ledger:
            continue
        value = _finite_scalar(vector[index])
        try:
            variance = _finite_scalar(covariance[index][index])
        except (IndexError, TypeError):
            variance = None
        if value is None or variance is None or variance <= 0.0:
            continue
        state_means[state] = _clip(state, value * scale)
        state_variances[state] = variance * (scale ** 2)
        ledger[state] = state_support_ledger[state]

    if not state_means:
        raise ValueError("historical output has no state-specific support")
    distinct_ids = list(dict.fromkeys(str(item) for item in scene_ids if str(item).strip()))
    return {
        "contract_version": ARCHIVE_POSTERIOR_CONTRACT_VERSION,
        "state_means": state_means,
        "state_covariance": state_variances,
        "last_update_date": timestamps[-1].isoformat() if hasattr(timestamps[-1], "isoformat") else str(timestamps[-1]),
        "geometry_hash": str(getattr(historical_output, "geometry_hash", "")),
        "crop_context": dict(crop_context),
        "state_support_ledger": ledger,
        "content_distinct_scene_ids": distinct_ids,
        "historical_validation_status": historical_validation_status,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def build_historical_state_support_ledger(
    stack: Any,
    daily_weather: Mapping[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Describe which accepted historical inputs support each adapted state."""
    optical_ids: List[str] = []
    sar_vv_ids: List[str] = []
    sar_vh_ids: List[str] = []
    for item in getattr(stack, "scenes", []) or []:
        runtime = item.get("runtime") if isinstance(item, Mapping) else None
        if runtime is None:
            continue
        scene_id = str(getattr(runtime, "scene_id", ""))
        bands = getattr(runtime, "bands", {}) or {}
        if getattr(runtime, "sensor", "") == "S2" and any(
            bands.get(key) is not None for key in ("ndvi", "evi")
        ):
            optical_ids.append(scene_id)
        if getattr(runtime, "sensor", "") == "S1":
            if bands.get("vv") is not None:
                sar_vv_ids.append(scene_id)
            if bands.get("vh") is not None:
                sar_vh_ids.append(scene_id)
    weather_dates = [str(key) for key, value in daily_weather.items() if value]
    ledger: Dict[str, Dict[str, Any]] = {}
    if optical_ids:
        support = list(dict.fromkeys(optical_ids))
        ledger["vigor"] = {
            "state": "vigor", "support_status": "temporally_conditioned",
            "observation_relationship": "direct", "source_feature_ids": support,
            "accepted_update_count": len(support), "spatial_support": "plot_level_only",
            "authority_ceiling": "DIAGNOSTIC", "block_reasons": [],
            "update_mode": "historical_optical_filter",
        }
        ledger["lai"] = {**ledger["vigor"], "state": "lai"}
    if sar_vh_ids:
        ledger["structure"] = {
            "state": "structure", "support_status": "temporally_conditioned",
            "observation_relationship": "indirect",
            "source_feature_ids": list(dict.fromkeys(sar_vh_ids)),
            "accepted_update_count": len(set(sar_vh_ids)),
            "spatial_support": "plot_level_only", "authority_ceiling": "DIAGNOSTIC",
            "block_reasons": [],
            "update_mode": "historical_sar_filter",
        }
    if sar_vv_ids:
        ledger["surface_wetness_event"] = {
            "state": "surface_wetness_event", "support_status": "temporally_conditioned",
            "observation_relationship": "indirect",
            "source_feature_ids": list(dict.fromkeys(sar_vv_ids)),
            "accepted_update_count": len(set(sar_vv_ids)),
            "spatial_support": "plot_level_only", "authority_ceiling": "DIAGNOSTIC",
            "block_reasons": [],
            "update_mode": "historical_sar_filter",
        }
    if weather_dates:
        weather_support = [f"weather:{item}" for item in weather_dates]
        for state in ("root_zone_water", "thermal_stress", "phenology_progress", "stress_memory"):
            ledger[state] = {
                "state": state, "support_status": "temporally_conditioned",
                "observation_relationship": "indirect",
                "source_feature_ids": weather_support,
                "accepted_update_count": len(weather_support),
                "spatial_support": "plot_level_only", "authority_ceiling": "DIAGNOSTIC",
                "block_reasons": [],
                "update_mode": "historical_weather_process",
            }
    return ledger
