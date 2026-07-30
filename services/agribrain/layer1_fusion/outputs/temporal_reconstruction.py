"""
Temporal Reconstruction — rebuild legacy FieldTensor fields from V1 evidence.

Agronomic Rationale
-------------------
The legacy data_fusion.py builds daily plot_timeseries records by iterating
evidence items and merging by date. We replicate this EXACTLY — same keys,
same fill strategy, same smoothing — but from V1's typed EvidenceItem objects.

The result is STRICTLY BETTER because:
  • V1 evidence carries per-datum confidence & reliability
  • Conflicts and gaps are annotated (not silently swallowed)
  • Source provenance is traceable per record
  • Interpolation quality is tracked via is_observed flag

Key design decisions:
  1. Variable → legacy key mapping is explicit (no substring guessing)
  2. Interpolation: linear forward-fill then back-fill (same as legacy)
  3. Smoothing: moving average window=5 for NDVI only (same as legacy)
  4. GDD: max(0, tmean - 10) using base 10°C (same as legacy line 1176)
  5. Missing values stay None — never fabricate (V1 guarantee)

Usage:
    from layer1_fusion.outputs.temporal_reconstruction import (
        rebuild_daily_timeseries, rebuild_forecast_7d,
        rebuild_daily_state, rebuild_static, rebuild_zone_stats,
    )
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from layer1_fusion.schemas import EvidenceItem


# ============================================================================
# Variable → legacy timeseries key mapper
# ============================================================================
# V1 adapters emit typed variable names. Legacy consumers expect flat keys.
# This map is the SINGLE SOURCE OF TRUTH for the translation.

_V1_VAR_TO_NDVI_KEY = {
    "ndvi": "ndvi_mean",
}

_V1_VAR_TO_SAR_KEYS = {
    "vv_db": "vv",
    "vh_db": "vh",
}

_V1_VAR_TO_WEATHER_KEYS = {
    "weather_precipitation_mm": "rain",
    "weather_temp_mean": "tmean",
    "weather_temp_max": "temp_max",
    "weather_temp_min": "temp_min",
    "weather_et0_mm": "et0",
    "weather_vpd_kpa": "vpd",
    # Direct precipitation (from some adapters)
    "precipitation": "rain",
}

_V1_COVERAGE_VARS = frozenset({"vegetation_fraction", "cloud_cover"})


# ============================================================================
# Public API
# ============================================================================

def rebuild_daily_timeseries(
    evidence_items: List[EvidenceItem],
    window_start: datetime,
    window_end: datetime,
) -> List[Dict[str, Any]]:
    """Reconstruct legacy plot_timeseries from V1 evidence items.

    Strategy:
      1. Generate daily date axis (window_start → window_end)
      2. Group evidence by date using observed_at (plot-scoped only)
      3. For each date, extract NDVI, SAR, weather values
      4. Apply gap-fill (forward-fill + back-fill, same as legacy)
      5. Apply smoothing (moving average window=5 for NDVI)
      6. Compute derived fields (GDD, uncertainty, is_observed)
      7. Emit one record per day in EXACTLY the legacy schema

    Returns:
        List of dicts, one per day. Each dict has keys:
          date, ndvi_mean, ndvi_interpolated, ndvi_smoothed,
          vv, vh, vv_interpolated, vh_interpolated,
          rain, tmean, temp_max, temp_min, et0, gdd, wind_speed,
          is_observed, uncertainty, coverage, confidence
    """
    # 1. Generate date axis
    date_strs = _generate_date_range(window_start, window_end)
    if not date_strs:
        return []

    # 2. Build per-date maps from evidence (plot-scoped only)
    ndvi_map = _build_dated_value_map(evidence_items, {"ndvi"}, scope="plot")
    sar_map = _build_dated_sar_map(evidence_items, scope="plot")
    weather_map = _build_dated_weather_map(evidence_items)
    coverage_map = _build_dated_coverage_map(evidence_items)
    confidence_map = _build_dated_confidence_map(evidence_items, {"ndvi"}, scope="plot")

    # 3. Build raw daily records
    records: List[Dict[str, Any]] = []
    ndvi_values: List[Optional[float]] = []
    vv_values: List[Optional[float]] = []
    vh_values: List[Optional[float]] = []

    for d in date_strs:
        rec: Dict[str, Any] = {"date": d, "is_observed": False, "uncertainty": 0.5}

        # NDVI
        ndvi_val = ndvi_map.get(d)
        if ndvi_val is not None:
            rec["ndvi_mean"] = ndvi_val
            rec["is_observed"] = True
            rec["uncertainty"] = 0.1
            rec["coverage"] = coverage_map.get(d, 0.8)
            rec["confidence"] = confidence_map.get(d, 0.5)
        else:
            rec["ndvi_mean"] = None
        ndvi_values.append(rec["ndvi_mean"])

        # SAR
        sar = sar_map.get(d, {})
        vv = sar.get("vv")
        vh = sar.get("vh")
        rec["vv"] = vv
        rec["vh"] = vh
        vv_values.append(vv)
        vh_values.append(vh)

        # Weather
        wx = weather_map.get(d, {})
        rain = wx.get("rain")
        tmean = wx.get("tmean")
        tmax = wx.get("temp_max")
        tmin = wx.get("temp_min")
        et0 = wx.get("et0")

        rec["rain"] = float(rain) if rain is not None else None
        rec["tmean"] = float(tmean) if tmean is not None else None
        rec["temp_max"] = float(tmax) if tmax is not None else None
        rec["temp_min"] = float(tmin) if tmin is not None else None
        rec["et0"] = float(et0) if et0 is not None else None
        rec["wind_speed"] = float(wx.get("wind_speed") or 0.0) if wx.get("wind_speed") is not None else None

        # V91.2: GDD only from real observed temperature — not from defaults.
        # Zero is a real agronomic value; fabricating GDD from missing data is forbidden.
        if rec["tmean"] is not None:
            rec["gdd"] = max(0.0, rec["tmean"] - 10.0)
        else:
            rec["gdd"] = None

        records.append(rec)

    # 4. Gap-fill (same algorithm as legacy _perform_temporal_fusion_pure)
    filled_ndvi = _fill_linear(ndvi_values)
    filled_vv = _fill_linear(vv_values)
    filled_vh = _fill_linear(vh_values)

    # V91.2: Preserve None — zero is a real agronomic value
    ndvi_num = [float(v) if v is not None else None for v in filled_ndvi]
    vv_num = [float(v) if v is not None else None for v in filled_vv]
    vh_num = [float(v) if v is not None else None for v in filled_vh]

    # SIG-1: Graduated uncertainty (V1 path).
    # Replaces binary 0.1/0.5 with distance-based scaling.
    n = len(records)
    dist_to_obs = [0] * n
    last_obs = -999
    for i in range(n):
        if records[i]["is_observed"]:
            last_obs = i
        dist_to_obs[i] = i - last_obs if last_obs >= 0 else 999
    next_obs = n + 999
    for i in range(n - 1, -1, -1):
        if records[i]["is_observed"]:
            next_obs = i
        back_dist = next_obs - i if next_obs < n + 999 else 999
        dist_to_obs[i] = min(dist_to_obs[i], back_dist)
    max_gap = max(max(dist_to_obs), 1) if dist_to_obs else 1
    for i in range(n):
        if not records[i]["is_observed"]:
            records[i]["uncertainty"] = round(0.1 + 0.4 * (dist_to_obs[i] / max_gap), 3)

    # 5. Smoothing (moving average window=5 for NDVI, same as legacy)
    ndvi_smoothed = _moving_average(ndvi_num, window=5)

    # 6. Store interpolated + smoothed values
    for i in range(len(records)):
        records[i]["ndvi_interpolated"] = ndvi_num[i]
        records[i]["ndvi_smoothed"] = ndvi_smoothed[i]
        records[i]["vv_interpolated"] = vv_num[i]
        records[i]["vh_interpolated"] = vh_num[i]

    return records


def rebuild_forecast_7d(
    evidence_items: List[EvidenceItem],
) -> List[Dict[str, Any]]:
    """Extract forecast evidence into legacy forecast_7d format.

    Filters evidence by temporal_scope == 'forecast' and groups by date.
    """
    forecast: List[Dict[str, Any]] = []
    forecast_items = [
        e for e in evidence_items
        if e.temporal_scope == "forecast" and e.observed_at is not None
    ]

    # Group by date
    by_date: Dict[str, Dict[str, Any]] = {}
    for e in forecast_items:
        d = e.observed_at.strftime("%Y-%m-%d")
        if d not in by_date:
            by_date[d] = {"date": d, "source": "v1_forecast_adapter"}
        var = e.variable
        val = e.value
        if isinstance(val, (int, float)):
            if "temp_max" in var:
                by_date[d]["temp_max"] = val
            elif "temp_min" in var:
                by_date[d]["temp_min"] = val
            elif "precip" in var:
                by_date[d]["precipitation"] = val
            elif "et0" in var:
                by_date[d]["et0"] = val
            elif "risk" in var:
                by_date[d].setdefault("risks", []).append(
                    {"type": var, "value": val}
                )

    for d in sorted(by_date.keys()):
        forecast.append(by_date[d])

    return forecast


def rebuild_daily_state(
    evidence_items: List[EvidenceItem],
) -> Dict[str, List[Dict]]:
    """Reconstruct FieldTensor.daily_state from L0 Kalman evidence.

    L0 State adapter emits evidence with variables like:
      l0_sm_mean, l0_lai, l0_ndvi, l0_sm_uncertainty, etc.
    Scoped at zone level (spatial_scope='zone', scope_id='zone_a').

    We group by (scope_id, observed_at.date) and rebuild:
      { "zone_a": [ {day: "2024-01-01", sm_0_10: 0.3, lai: 1.2, ...}, ... ] }
    """
    daily_state: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(
        lambda: defaultdict(dict)
    )

    l0_items = [
        e for e in evidence_items
        if e.source_family == "l0_state"
        and e.observed_at is not None
        and e.scope_id is not None
        and isinstance(e.value, (int, float))
    ]

    for e in l0_items:
        zone = e.scope_id
        day = e.observed_at.strftime("%Y-%m-%d")
        # Strip l0_ prefix for cleaner keys
        var_key = e.variable
        if var_key.startswith("l0_"):
            var_key = var_key[3:]
        daily_state[zone][day][var_key] = e.value

    # Convert nested dicts to sorted lists
    result: Dict[str, List[Dict]] = {}
    for zone, day_map in daily_state.items():
        sorted_days = sorted(day_map.keys())
        result[zone] = [
            {"day": d, **day_map[d]}
            for d in sorted_days
        ]

    return result


def rebuild_static(
    evidence_items: List[EvidenceItem],
) -> Dict[str, Any]:
    """Reconstruct FieldTensor.static from soil/site evidence.

    Maps V1 variable names to the legacy static dict keys that
    downstream layers expect.
    """
    static: Dict[str, Any] = {}

    # Soil properties from environment adapter
    soil_map = {
        "soil_clay": "soil_clay_mean",
        "soil_sand": "soil_sand_mean",
        "soil_silt": "soil_silt_mean",
        "soil_ph": "soil_ph_mean",
        "soil_soc": "soil_org_c_mean",
        "soil_organic_carbon": "soil_org_c_mean",
        "soil_cec": "soil_cec_mean",
        "soil_nitrogen": "soil_nitrogen_mean",
    }

    for e in evidence_items:
        if e.source_family in ("environment", "geo_context"):
            # Only include static priors (soil, site), not weather time series
            if e.observation_type not in ("static_prior", "geo_prior"):
                continue
            if isinstance(e.value, (int, float)):
                key = soil_map.get(e.variable, e.variable)
                static[key] = e.value

    # Compute texture class if clay/sand present
    clay = static.get("soil_clay_mean")
    sand = static.get("soil_sand_mean")
    if clay is not None and sand is not None:
        silt = round(100.0 - clay - sand, 1)
        static.setdefault("soil_silt_mean", silt)
        static["texture_class"] = _classify_texture(clay, sand, silt)
    else:
        static.setdefault("texture_class", "unknown")

    static.setdefault("data_source", "v1_evidence_reconstruction")

    return static


def rebuild_zone_stats(
    evidence_items: List[EvidenceItem],
    spatial_index: Any = None,
) -> Dict[str, Any]:
    """Reconstruct FieldTensor.zone_stats from zone-scoped evidence.

    Structure: { variable: { zone_id: [timeseries_of_values] } }
    """
    zone_stats: Dict[str, Dict[str, List[Tuple[str, float]]]] = defaultdict(
        lambda: defaultdict(list)
    )

    zone_items = [
        e for e in evidence_items
        if e.spatial_scope == "zone"
        and e.scope_id is not None
        and e.observed_at is not None
        and isinstance(e.value, (int, float))
    ]

    for e in zone_items:
        zone_stats[e.variable][e.scope_id].append(
            (e.observed_at.strftime("%Y-%m-%d"), e.value)
        )

    # Sort by date and convert to simple format
    result: Dict[str, Any] = {}
    for var, zones in zone_stats.items():
        result[var] = {}
        for zone_id, pairs in zones.items():
            pairs.sort(key=lambda x: x[0])
            result[var][zone_id] = [
                {"date": d, "value": v} for d, v in pairs
            ]

    return result


def rebuild_provenance(pkg: Any) -> Dict[str, Any]:
    """Build provenance dict for FieldTensor from V1 context package."""
    prov = pkg.provenance
    diag = pkg.diagnostics
    return {
        "compatibility_mode": True,
        "source_context_package_ref": pkg.run_id,
        "engine_version": prov.engine_version,
        "contract_version": prov.contract_version,
        "evidence_count": prov.evidence_count,
        "fused_feature_count": prov.fused_feature_count,
        "missing_values_preserved": True,
        "gaps_ref": [g.gap_type for g in pkg.gaps],
        "conflicts_ref": [c.conflict_type for c in pkg.conflicts],
        "data_health_status": diag.data_health.status,
        "data_health_overall": diag.data_health.overall,
        # V1 enrichments (new data for downstream layers)
        "v1_active": True,
        "conflict_count": len(pkg.conflicts),
        "gap_count": len(pkg.gaps),
        "quarantined_count": prov.quarantined_count,
        "invariant_violations": getattr(prov, "invariant_violations", []),
    }


def rebuild_provenance_log(pkg: Any) -> List[Dict]:
    """Build provenance_log for FieldTensor from V1 audit log."""
    return getattr(pkg, "audit_log", []) or []


# ============================================================================
# Internal helpers
# ============================================================================

def _generate_date_range(start: datetime, end: datetime) -> List[str]:
    """Generate inclusive daily date strings."""
    if start is None or end is None:
        return []
    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return dates


def _build_dated_value_map(
    items: List[EvidenceItem],
    variables: set,
    scope: str = "plot",
) -> Dict[str, float]:
    """Build date → value map for specific variables at given scope.

    When multiple evidence items exist for the same date,
    use confidence-weighted average (V1 improvement over legacy last-write-wins).
    """
    by_date: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
    for e in items:
        if (e.variable in variables
                and e.spatial_scope == scope
                and e.observed_at is not None
                and isinstance(e.value, (int, float))
                and _is_real_temporal_observation(e)):
            d = e.observed_at.strftime("%Y-%m-%d")
            by_date[d].append((e.value, e.confidence))

    result: Dict[str, float] = {}
    for d, pairs in by_date.items():
        if len(pairs) == 1:
            result[d] = pairs[0][0]
        else:
            # Confidence-weighted average
            total_w = sum(c for _, c in pairs)
            if total_w > 0:
                result[d] = sum(v * c for v, c in pairs) / total_w
            else:
                result[d] = pairs[0][0]
    return result


def _build_dated_sar_map(
    items: List[EvidenceItem],
    scope: str = "plot",
) -> Dict[str, Dict[str, float]]:
    """Build date → {vv, vh} map from SAR evidence."""
    result: Dict[str, Dict[str, float]] = {}
    for e in items:
        if (e.source_family == "sentinel1"
                and e.spatial_scope == scope
                and e.observed_at is not None
                and isinstance(e.value, (int, float))
                and _is_real_temporal_observation(e)):
            d = e.observed_at.strftime("%Y-%m-%d")
            if d not in result:
                result[d] = {}
            if e.variable in _V1_VAR_TO_SAR_KEYS:
                key = _V1_VAR_TO_SAR_KEYS[e.variable]
                result[d][key] = e.value
    return result


def _build_dated_weather_map(
    items: List[EvidenceItem],
) -> Dict[str, Dict[str, float]]:
    """Build date → weather dict from environment evidence."""
    result: Dict[str, Dict[str, float]] = {}
    for e in items:
        if (e.source_family == "environment"
                and e.observation_type in ("model_estimate", "forcing")
                and isinstance(e.value, (int, float))):
            # Weather evidence may use observed_at or window_start
            dt = e.observed_at or e.window_start
            if dt is None:
                # Try to extract date from evidence_id (env_wx_YYYY-MM-DD_var)
                eid = e.evidence_id or ""
                if "env_wx_" in eid:
                    parts = eid.split("_")
                    for p in parts:
                        if len(p) == 10 and p[4] == '-' and p[7] == '-':
                            d = p
                            if d not in result:
                                result[d] = {}
                            key = _V1_VAR_TO_WEATHER_KEYS.get(e.variable)
                            if key:
                                result[d][key] = e.value
                continue
            d = dt.strftime("%Y-%m-%d")
            if d not in result:
                result[d] = {}
            key = _V1_VAR_TO_WEATHER_KEYS.get(e.variable)
            if key:
                result[d][key] = e.value
    return result


def _build_dated_coverage_map(
    items: List[EvidenceItem],
) -> Dict[str, float]:
    """Build date → coverage fraction from S2 evidence."""
    result: Dict[str, float] = {}
    for e in items:
        if (e.variable == "vegetation_fraction"
                and e.observed_at is not None
                and isinstance(e.value, (int, float))):
            d = e.observed_at.strftime("%Y-%m-%d")
            result[d] = e.value
    return result


def _build_dated_confidence_map(
    items: List[EvidenceItem],
    variables: set,
    scope: str = "plot",
) -> Dict[str, float]:
    """Build date → confidence from evidence items."""
    result: Dict[str, float] = {}
    for e in items:
        if (e.variable in variables
                and e.spatial_scope == scope
                and e.observed_at is not None
                and _is_real_temporal_observation(e)):
            d = e.observed_at.strftime("%Y-%m-%d")
            result[d] = e.confidence
    return result


def _is_real_temporal_observation(e: EvidenceItem) -> bool:
    """Accept provider scenes and admitted provider daily plot statistics.

    A Statistical API daily aggregate is real provider temporal evidence, but it
    is intentionally *not* a provider raster product.  Requiring
    ``real_provider_product`` here erased those admitted observations between
    Layer 1 and Layer 2.
    """
    common_admission = (
        e.source_family in {"sentinel1", "sentinel2"}
        and bool(e.content_hash)
        and bool(e.provider_product_id or e.source_id)
        and e.data_status == "observed"
        and e.production_usable is True
        and e.diagnostic_only is False
    )
    if not common_admission:
        return False

    if (
        e.temporal_basis == "daily_plot_statistic"
        and e.truth_class == "provider_plot_timeseries"
        and e.state_update_allowed is True
        and e.source_reality == "provider_daily_statistical_aggregate"
    ):
        return True

    return (
        e.temporal_basis == "scene_observation"
        and e.real_provider_product is True
        and e.source_reality in {
            "provider_scene_observation",
            "provider_temporal_observation",
            "real_provider_raster",
            "provider_observation",
            "real_raster",
        }
    )


def _fill_linear(vals: List[Optional[float]]) -> List[Optional[float]]:
    """Gap-fill using forward-fill then back-fill.

    Exact replication of legacy data_fusion.py _perform_temporal_fusion_pure
    fill_linear function (lines 748-775).
    """
    out = vals[:]
    # Forward fill
    last = None
    for i in range(len(out)):
        if out[i] is None:
            out[i] = last
        else:
            last = out[i]
    # Back fill for leading Nones
    nextv = None
    for i in reversed(range(len(out))):
        if out[i] is None:
            out[i] = nextv
        else:
            nextv = out[i]
    # V91.2: If still all None, preserve missing — zero is a real agronomic value
    if all(v is None for v in out):
        return [None for _ in out]
    return out


def _moving_average(vals: List[Optional[float]], window: int = 5) -> List[Optional[float]]:
    """Moving average smoother.

    V91.2: Handles None values — skip Nones in the window.
    If a position is None, the smoothed value is also None.
    """
    if window <= 1:
        return vals
    out: List[Optional[float]] = []
    half = window // 2
    n = len(vals)
    for i in range(n):
        if vals[i] is None:
            out.append(None)
            continue
        a = max(0, i - half)
        b = min(n, i + half + 1)
        chunk = [v for v in vals[a:b] if v is not None]
        out.append(sum(chunk) / max(1, len(chunk)) if chunk else None)
    return out


def _classify_texture(clay: float, sand: float, silt: float) -> str:
    """Simple USDA texture triangle classification."""
    if clay >= 40:
        return "clay"
    elif sand >= 85:
        return "sand"
    elif silt >= 80:
        return "silt"
    elif clay >= 27 and sand >= 20:
        return "clay_loam"
    elif sand >= 52 and clay < 20:
        return "sandy_loam"
    elif silt >= 50:
        return "silt_loam"
    else:
        return "loam"
