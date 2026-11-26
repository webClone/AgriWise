"""Chronological 13-State Historical State Reconstruction & Late-Arrival Replay.

Executes ASMAE's genuine 13-state Ensemble Kalman Filter forward chronologically over
OBSERVATION_QUALIFIED historical worldline acquisitions and ERA5 daily weather, storing
versioned posterior checkpoints and emitting ARCHIVE_POSTERIOR_VALIDATED worldline events
only after assimilation, gap tracking, and validation complete.

Capabilities:
  1. Chronological 2015-present 13-state trajectory + 13x13 covariance + support ledger.
  2. Exact deterministic incremental resume from prior versioned checkpoints (matching
     cold full-history reconstruction across state means, sigmas, covariance, model
     versions, event order, and causal forecasts).
  3. Non-destructive late-arrival replay: when an older observation arrives after a later
     state has already been published, recomputes affected history from the nearest prior
     checkpoint and appends superseding checkpoints/worldline events without silently
     mutating previously published history.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import math
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from rasterio.crs import CRS
from rasterio.features import geometry_mask
from rasterio.transform import Affine
from rasterio.warp import Resampling, reproject

from services.agribrain.layer0.asmae_scene_products.scene_product_store import SceneProductStore
from services.agribrain.layer05_asmae.assimilation.filter import (
    _forecast_elapsed_interval,
    _proxy_update_single_obs,
    clamp_ensemble,
    compute_ensemble_statistics,
    initialize_ensemble,
)
from services.agribrain.layer05_asmae.config import (
    N_STATES,
    STATE_BOUNDS,
    STATE_NAMES,
    STATE_SCHEMA_VERSION,
)
from services.agribrain.layer05_asmae.cross_layer_intelligence import (
    CrossLayerChronoState,
    CrossLayerSpecialistBridge,
)
from services.agribrain.layer05_asmae.deterministic import make_rng
from services.agribrain.layer05_asmae.geometry.s1_scene_loader import (
    _normalized_backscatter_feature,
)
from services.agribrain.layer05_asmae.observation.index_state_mapping import (
    INDEX_STATE_REGISTRY,
    validate_forbidden_state_update,
)
from services.agribrain.layer05_asmae.observation.observation_noise import (
    compute_observation_noise,
)
from services.agribrain.layer05_asmae.observation.s1_sar_model import predict_sar_observation
from services.agribrain.layer05_asmae.observation.s2_forward_model import predict_observation
from services.agribrain.layer05_asmae.state.descriptors import (
    AssimilationPolicy,
    STATE_DESCRIPTORS,
)
from services.agribrain.world_model.canonical_worldline import (
    CanonicalWorldlineService,
    WorldlineEventProposal,
    _parse_utc_iso,
)

logger = logging.getLogger(__name__)

RECONSTRUCTOR_MODEL_VERSION = "asmae_hist_cross_layer_v3"
CALIBRATION_VERSION = "asmae_causal_spatial_cal_v7"
POSTERIOR_CHECKPOINT_SCHEMA = "asmae_posterior_checkpoint_v2"

_CAL_DECAY_BY_CHANNEL: Dict[str, float] = {
    "sar_vv": 0.96,
    "sar_vh": 0.96,
    "sar_ratio": 0.96,
    "ndvi": 0.92,
    "ndmi": 0.92,
    "ndre": 0.92,
}
_CAL_TAU_DAYS_BY_CHANNEL: Dict[str, float] = {
    "sar_vv": 12.0,
    "sar_vh": 12.0,
    "sar_ratio": 12.0,
    "ndmi": 10.0,
    "ndvi": 8.0,
    "ndre": 8.0,
}


def filter_causal_daily_weather_at_cutoff(
    daily_weather: Optional[Dict[str, Dict[str, Any]]],
    cutoff_dt: datetime,
    *,
    knowledge_cutoff_dt: Optional[datetime] = None,
    enforce_publication_lag: bool = False,
    stats_out: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Restrict daily weather aggregates strictly to what was observable by `cutoff_dt` (and optional K).

    Daily ERA5 aggregates on `cutoff_dt.date()` are excluded before day-end (`< 23:59`)
    unless explicitly stamped with `observed_before` / `issued_at` / `as_of <= cutoff_dt`.
    When `enforce_publication_lag=True` and `knowledge_cutoff_dt` is supplied, records
    carrying `available_at` later than `knowledge_cutoff_dt` (e.g., 5-day ERA5 backfill lag)
    are withheld as non-available at knowledge cutoff K.
    """
    c_day = cutoff_dt.date()
    c_iso = c_day.isoformat()
    is_day_end = cutoff_dt.hour >= 23 and cutoff_dt.minute >= 59
    prev_complete_iso = c_iso if is_day_end else (c_day - timedelta(days=1)).isoformat()
    out: Dict[str, Dict[str, Any]] = {}
    excluded_valid_cutoff = 0
    excluded_lag_k = 0
    reanalysis_days = 0
    observed_days = 0
    max_lag_days = 0
    for d_str, w in (daily_weather or {}).items():
        if not isinstance(w, dict):
            continue
        d_clean = str(d_str)[:10]
        allow_same_day = False
        if d_clean == c_iso and d_clean > prev_complete_iso:
            ts_tag = w.get("observed_before") or w.get("issued_at") or w.get("as_of")
            if ts_tag:
                try:
                    allow_same_day = _parse_utc_iso(ts_tag) <= cutoff_dt
                except Exception:
                    allow_same_day = False
        if not (d_clean <= prev_complete_iso or allow_same_day):
            excluded_valid_cutoff += 1
            continue
        avail_tag = w.get("available_at")
        if enforce_publication_lag and knowledge_cutoff_dt is not None and avail_tag:
            try:
                if _parse_utc_iso(avail_tag) > knowledge_cutoff_dt:
                    excluded_lag_k += 1
                    continue
            except Exception:
                pass
        row = dict(w)
        reality = str(row.get("source_reality") or "")
        if reality == "reanalysis_archive":
            reanalysis_days += 1
        elif reality == "observed_archive":
            observed_days += 1
        lag_v = int(row.get("reanalysis_lag_days") or 0)
        if lag_v > max_lag_days:
            max_lag_days = lag_v
        out[d_clean] = row
    if stats_out is not None:
        stats_out.update({
            "admitted_days": len(out),
            "excluded_after_valid_cutoff": excluded_valid_cutoff,
            "excluded_reanalysis_lag_count": excluded_lag_k,
            "reanalysis_days": reanalysis_days,
            "observed_days": observed_days,
            "max_reanalysis_lag_days": max_lag_days,
            "enforce_publication_lag": bool(enforce_publication_lag),
        })
    return out


def summarize_weather_provenance(
    daily_weather: Optional[Dict[str, Dict[str, Any]]],
    *,
    knowledge_cutoff_dt: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Summarize daily weather provenance roles, reanalysis publication lag, and K exposure."""
    rows = [w for w in (daily_weather or {}).values() if isinstance(w, dict)]
    roles = sorted({str(w.get("source_role")) for w in rows if w.get("source_role")})
    realities = sorted({str(w.get("source_reality")) for w in rows if w.get("source_reality")})
    reanalysis_cnt = sum(1 for w in rows if w.get("source_reality") == "reanalysis_archive" or w.get("is_reanalysis_backfill"))
    observed_cnt = sum(1 for w in rows if w.get("source_reality") == "observed_archive")
    max_lag = max((int(w.get("reanalysis_lag_days") or 0) for w in rows), default=0)
    lag_exposed = 0
    if knowledge_cutoff_dt is not None:
        for w in rows:
            av = w.get("available_at")
            if av:
                try:
                    if _parse_utc_iso(av) > knowledge_cutoff_dt:
                        lag_exposed += 1
                except Exception:
                    pass
    return {
        "total_days": len(rows),
        "source_realities": realities,
        "source_roles": roles,
        "reanalysis_backfill_days": reanalysis_cnt,
        "observed_station_days": observed_cnt,
        "max_reanalysis_lag_days": max_lag,
        "days_beyond_reanalysis_lag_at_k": lag_exposed,
        "weather_availability_note": (
            f"ERA5 reanalysis records carry {max_lag}d publication lag metadata (`available_at`); historical replay assumes full historical availability unless `enforce_publication_lag=True`."
            if reanalysis_cnt > 0
            else "No reanalysis publication-lag records detected."
        ),
    }


def build_prospective_weather_series(
    daily_weather: Optional[Dict[str, Dict[str, Any]]],
    issue_dt: datetime,
    horizon_end_dt: datetime,
    *,
    strict_previous_complete_day: bool = True,
) -> Dict[str, Dict[str, Any]]:
    """Build strictly causal weather dict without intraday afternoon leakage.

    By default (`strict_previous_complete_day=True`), complete daily summaries on
    `issue_dt.date()` are withheld (since afternoon Tmax/rain were unknown at morning
    satellite overpass, e.g. 10:30 UTC) unless `issue_dt` is at day end (>=23:59) or
    the weather record carries an explicit timestamp (`issued_at`/`observed_before`)
    `<= issue_dt`. Dates from the cutoff onward use causal DOY/trailing climatology.
    """
    issue_day = issue_dt.date()
    end_day = horizon_end_dt.date()
    issue_iso = issue_day.isoformat()
    is_day_end = issue_dt.hour >= 23 and issue_dt.minute >= 59
    if strict_previous_complete_day and not is_day_end:
        realized_cutoff_iso = (issue_day - timedelta(days=1)).isoformat()
        forecast_start_day = issue_day
    else:
        realized_cutoff_iso = issue_iso
        forecast_start_day = issue_day + timedelta(days=1)

    out: Dict[str, Dict[str, Any]] = {}
    past_rows: List[Tuple[datetime, Dict[str, Any]]] = []
    for d_str, w in (daily_weather or {}).items():
        d_clean = str(d_str)[:10]
        if not isinstance(w, dict):
            continue
        allow_same_day = False
        if d_clean == issue_iso and d_clean > realized_cutoff_iso:
            ts_tag = w.get("observed_before") or w.get("issued_at") or w.get("as_of")
            if ts_tag:
                try:
                    allow_same_day = _parse_utc_iso(ts_tag) <= issue_dt
                except Exception:
                    allow_same_day = False
        if d_clean <= realized_cutoff_iso or allow_same_day:
            out[d_clean] = dict(w)
            try:
                past_rows.append((datetime.fromisoformat(d_clean), w))
            except Exception:
                continue

    past_rows.sort(key=lambda item: item[0])
    recent_tail = [w for _, w in past_rows[-7:]] if past_rows else []

    def _doy_dist(d1: int, d2: int) -> int:
        diff = abs(d1 - d2)
        return min(diff, 365 - diff)

    def _mean_field(rows: List[Dict[str, Any]], key: str, default_val: float) -> float:
        vals = [float(r[key]) for r in rows if isinstance(r.get(key), (int, float)) and math.isfinite(float(r[key]))]
        return round(float(np.mean(vals)), 3) if vals else default_val

    cur = forecast_start_day
    while cur <= end_day:
        c_iso = cur.isoformat()
        if c_iso in out:
            cur += timedelta(days=1)
            continue
        c_doy = cur.timetuple().tm_yday
        doy_rows = [
            w for p_dt, w in past_rows
            if p_dt.year < cur.year and _doy_dist(c_doy, p_dt.timetuple().tm_yday) <= 21
        ]
        ref_rows = doy_rows if doy_rows else recent_tail
        if ref_rows:
            t_max = _mean_field(ref_rows, "temp_max", 22.0)
            t_min = _mean_field(ref_rows, "temp_min", 12.0)
            et0_v = _mean_field(ref_rows, "et0", 3.0)
            precip_vals = [
                float(r["precipitation"]) for r in ref_rows
                if isinstance(r.get("precipitation"), (int, float)) and math.isfinite(float(r["precipitation"]))
            ]
            # Expected daily climatological precipitation (no future storm knowledge)
            precip_exp = round(float(np.mean(precip_vals)), 3) if precip_vals else 0.0
            out[c_iso] = {
                "temp_max": t_max,
                "temp_min": t_min,
                "precipitation": precip_exp,
                "et0": et0_v,
                "source_role": "causal_doy_climatology_projection",
            }
        cur += timedelta(days=1)
    return out


def apply_causal_channel_calibration(
    cal_entry: Optional[Dict[str, Any]],
    *,
    obs_name: str,
    raw_pred_mean: float,
    raw_pred_var: float,
    obs_sigma: float,
    elapsed_days: float = 0.0,
    now_dt: Optional[datetime] = None,
) -> Dict[str, float]:
    """Apply strictly causal Bayesian slope/offset operator + damped AR(1) residual anchor."""
    st = cal_entry or {}
    eff_n = float(st.get("eff_n", 0.0) or 0.0)
    sum_x = float(st.get("sum_x", 0.0) or 0.0)
    sum_y = float(st.get("sum_y", 0.0) or 0.0)
    sum_xx = float(st.get("sum_xx", 0.0) or 0.0)
    sum_xy = float(st.get("sum_xy", 0.0) or 0.0)
    sum_err = float(st.get("sum_err", 0.0) or 0.0)

    slope_prior = 1.0
    bias_prior = 0.0
    if eff_n > 0.0:
        if sum_x != 0.0 or sum_y != 0.0:
            mx = sum_x / eff_n
            my = sum_y / eff_n
            if eff_n >= 4.0:
                s_xx = max(0.0, sum_xx - (sum_x * sum_x) / eff_n)
                s_xy = sum_xy - (sum_x * sum_y) / eff_n
                kappa = 0.25
                slope_prior = float(np.clip((s_xy + kappa * 1.0) / (s_xx + kappa), 0.55, 1.55))
            # Avoid shrinking permanent sensor offsets away by 14% once eff_n >= 2
            bias_prior = float(np.clip((eff_n / (eff_n + 0.20)) * (my - slope_prior * mx), -0.65, 0.65))
        else:
            bias_prior = float(np.clip(sum_err / (eff_n + 0.20), -0.65, 0.65))

    lo_b, hi_b = _CHANNEL_BOUNDS.get(obs_name, (-1.0, 1.0))
    base_cal = float(np.clip(slope_prior * raw_pred_mean + bias_prior, lo_b, hi_b))

    age_days = max(0.0, float(elapsed_days))
    last_ts = st.get("last_obs_ts")
    if last_ts and now_dt is not None:
        try:
            age_days = max(0.0, (now_dt - _parse_utc_iso(last_ts)).total_seconds() / 86400.0)
        except Exception:
            pass
    tau = _CAL_TAU_DAYS_BY_CHANNEL.get(obs_name, 10.0)
    resid_last = float(st.get("last_post_resid", 0.0) or 0.0)
    anch = float(np.clip(resid_last, -0.30, 0.30)) * math.exp(-age_days / tau) if eff_n >= 2.0 else 0.0
    cal_pred_mean = float(np.clip(base_cal + anch, lo_b, hi_b))

    bias_epistemic_var = (0.08 ** 2) / (eff_n + 2.0)
    gap_infl_var = 0.00018 * min(45.0, age_days)
    base_var = max(
        1e-8,
        (slope_prior * slope_prior) * raw_pred_var + (obs_sigma * obs_sigma) + bias_epistemic_var + gap_infl_var,
    )
    z2_prev = float(st.get("z2_ema", 1.0) if st.get("z2_ema") is not None else 1.0)
    # Hierarchical Bayesian shrinkage during cold warmup only (fades to 0 as obs_count >= 8)
    obs_cnt_cal = int(st.get("obs_count", 0) or 0)
    warmup_weight = 1.5 * math.exp(-0.35 * obs_cnt_cal)
    shrunk_z2 = (eff_n * z2_prev + warmup_weight) / max(1e-6, eff_n + warmup_weight)
    var_scale_prior = float(min(4.5, max(0.008, shrunk_z2)))
    if obs_cnt_cal >= 6 and st.get("cov1_ema") is not None:
        cov1_ema = float(st["cov1_ema"])
        if cov1_ema > 0.71:
            var_scale_prior *= math.exp(-2.2 * min(0.35, cov1_ema - 0.6827))
        elif cov1_ema < 0.65:
            var_scale_prior *= math.exp(2.0 * min(0.35, 0.6827 - cov1_ema))
        var_scale_prior = float(min(4.5, max(0.008, var_scale_prior)))
    cal_var = max(1e-8, base_var * var_scale_prior)
    return {
        "cal_pred_mean": cal_pred_mean,
        "base_cal_mean": base_cal,
        "bias_prior": bias_prior,
        "slope_prior": slope_prior,
        "cal_sigma": math.sqrt(cal_var),
        "unscaled_sigma": math.sqrt(base_var),
        "var_scale_prior": var_scale_prior,
    }


def update_channel_cal_entry(
    cal_entry: Optional[Dict[str, Any]],
    *,
    obs_val: float,
    raw_pred: float,
    cal_pred: float,
    unscaled_sig: float,
    obs_name: str = "ndvi",
    obs_dt: Optional[datetime] = None,
    post_raw_pred: Optional[float] = None,
    var_scale_used: Optional[float] = None,
) -> Dict[str, Any]:
    """Update causal sufficient statistics and post-update AR(1) anchor AFTER scoring obs_val."""
    st = cal_entry or {}
    decay = _CAL_DECAY_BY_CHANNEL.get(obs_name, 0.92)
    eff_n = decay * float(st.get("eff_n", 0.0) or 0.0) + 1.0
    sum_x = decay * float(st.get("sum_x", 0.0) or 0.0) + float(raw_pred)
    sum_y = decay * float(st.get("sum_y", 0.0) or 0.0) + float(obs_val)
    sum_xx = decay * float(st.get("sum_xx", 0.0) or 0.0) + float(raw_pred) * float(raw_pred)
    sum_xy = decay * float(st.get("sum_xy", 0.0) or 0.0) + float(raw_pred) * float(obs_val)
    sum_err = decay * float(st.get("sum_err", 0.0) or 0.0) + (float(obs_val) - float(raw_pred))

    slope = 1.0
    mx = sum_x / eff_n
    my = sum_y / eff_n
    if eff_n >= 4.0:
        s_xx = max(0.0, sum_xx - (sum_x * sum_x) / eff_n)
        s_xy = sum_xy - (sum_x * sum_y) / eff_n
        slope = float(np.clip((s_xy + 0.25 * 1.0) / (s_xx + 0.25), 0.55, 1.55))
    bias = float(np.clip((eff_n / (eff_n + 0.20)) * (my - slope * mx), -0.65, 0.65))
    post_ref_raw = float(post_raw_pred if post_raw_pred is not None else raw_pred)
    post_cal = slope * post_ref_raw + bias
    raw_resid = float(obs_val - post_cal)
    prev_r = float(st.get("last_post_resid", raw_resid) if st.get("last_post_resid") is not None else raw_resid)
    # Lightly smooth single-orbit SAR speckle in the innovation carryover
    if obs_name.startswith("sar_"):
        last_post_resid = 0.65 * raw_resid + 0.35 * prev_r
    else:
        last_post_resid = raw_resid

    z2_sample = ((float(obs_val) - float(cal_pred)) ** 2) / max(1e-6, float(unscaled_sig) * float(unscaled_sig))
    z2_prev = float(st.get("z2_ema", 1.0) if st.get("z2_ema") is not None else 1.0)
    v_used = float(var_scale_used if var_scale_used is not None else max(0.008, z2_prev))
    prior_sig = max(1e-6, float(unscaled_sig) * math.sqrt(max(0.008, v_used)))
    hit_1s = 1.0 if abs(float(obs_val) - float(cal_pred)) <= prior_sig else 0.0
    cov1_prev = float(st.get("cov1_ema", 0.6827) if st.get("cov1_ema") is not None else 0.6827)
    return {
        "sum_err": round(sum_err, 8),
        "sum_x": round(sum_x, 8),
        "sum_y": round(sum_y, 8),
        "sum_xx": round(sum_xx, 8),
        "sum_xy": round(sum_xy, 8),
        "eff_n": round(eff_n, 6),
        "z2_ema": round(0.86 * z2_prev + 0.14 * min(3.5, z2_sample), 6),
        "cov1_ema": round(0.88 * cov1_prev + 0.12 * hit_1s, 6),
        "last_post_resid": round(last_post_resid, 6),
        "last_obs_ts": obs_dt.isoformat() if obs_dt is not None else st.get("last_obs_ts"),
        "obs_count": int(st.get("obs_count", 0) or 0) + 1,
    }

_CHANNEL_BOUNDS: Dict[str, Tuple[float, float]] = {
    "ndvi": (-1.0, 1.0),
    "ndmi": (-1.0, 1.0),
    "ndre": (-1.0, 1.0),
    "sar_vv": (0.0, 1.0),
    "sar_vh": (0.0, 1.0),
}

_SPATIALLY_SUPPORTED_STATES: Tuple[str, ...] = (
    "vigor",
    "lai",
    "chlorophyll",
    "canopy_water",
    "root_zone_water",
    "surface_wetness_event",
    "structure",
    "bare_soil_fraction",
    "phenology_progress",
    "stress_memory",
)
_OPTICAL_SPATIAL_COUPLINGS: Dict[str, Tuple[float, float]] = {
    # state: (w_ndvi_anom, w_ndmi_anom)
    "vigor": (0.85, 0.10),
    "lai": (3.20, 0.70),
    "chlorophyll": (28.0, 6.0),
    "canopy_water": (0.20, 0.65),
    "root_zone_water": (0.05, 0.28),
    "bare_soil_fraction": (-0.65, -0.15),
    "phenology_progress": (0.18, 0.04),
    "stress_memory": (-0.22, -0.34),
}
_SAR_SPATIAL_COUPLINGS: Dict[str, Tuple[float, float]] = {
    # state: (w_vv_anom, w_vh_anom)
    "structure": (0.38, 0.58),
    "surface_wetness_event": (0.72, -0.15),
    "root_zone_water": (0.34, 0.14),
    "canopy_water": (0.12, 0.18),
    "stress_memory": (-0.18, -0.12),
}


def _rng_state_to_json(state: Any) -> Any:
    """Convert random.Random.getstate() tuple structure into pure JSON lists."""
    if isinstance(state, tuple):
        return [_rng_state_to_json(x) for x in state]
    return state


def _rng_state_from_json(state: Any) -> Any:
    """Restore nested tuple structure expected by random.Random.setstate()."""
    if isinstance(state, list) and len(state) == 3:
        return (int(state[0]), tuple(int(x) for x in state[1]), state[2])
    return tuple(state) if isinstance(state, list) else state


def _extract_polygon_geom(polygon_geojson: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Extract normalized Polygon/MultiPolygon GeoJSON geometry when present."""
    if not isinstance(polygon_geojson, dict):
        return None
    geom = polygon_geojson.get("geometry") if polygon_geojson.get("type") == "Feature" else polygon_geojson
    if isinstance(geom, dict) and geom.get("type") in ("Polygon", "MultiPolygon") and geom.get("coordinates"):
        return geom
    return None


def _polygon_mask(
    polygon_geojson: Optional[Dict[str, Any]],
    transform_vals: Any,
    height: int,
    width: int,
) -> np.ndarray:
    """Compute boolean interior mask (True = inside parcel polygon)."""
    geom = _extract_polygon_geom(polygon_geojson)
    if geom is None or not transform_vals or len(transform_vals) != 6:
        return np.ones((height, width), dtype=bool)
    tr = Affine.from_gdal(*(float(x) for x in transform_vals))
    return geometry_mask([geom], out_shape=(height, width), transform=tr, invert=True, all_touched=True)


def _extract_polygon_bounds(polygon_geojson: Optional[Dict[str, Any]]) -> Optional[List[float]]:
    """Return [min_lng, min_lat, max_lng, max_lat] from GeoJSON Polygon/MultiPolygon."""
    geom = _extract_polygon_geom(polygon_geojson)
    if geom is None:
        return None
    pts: List[Tuple[float, float]] = []

    def _walk(node: Any) -> None:
        if isinstance(node, (list, tuple)):
            if len(node) >= 2 and isinstance(node[0], (int, float)) and isinstance(node[1], (int, float)):
                pts.append((float(node[0]), float(node[1])))
            else:
                for ch in node:
                    _walk(ch)

    _walk(geom.get("coordinates"))
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return [min(xs), min(ys), max(xs), max(ys)]


def build_canonical_parcel_grid(
    polygon_geojson: Optional[Dict[str, Any]],
    target_step_deg: float = 0.0001,
) -> Optional[Dict[str, Any]]:
    """Build deterministic ~10m canonical parcel grid anchored to polygon bounds."""
    bounds = _extract_polygon_bounds(polygon_geojson)
    if bounds is None:
        return None
    minx, miny, maxx, maxy = bounds
    span_x = max(1e-4, maxx - minx)
    span_y = max(1e-4, maxy - miny)
    width = max(12, min(120, int(round(span_x / target_step_deg))))
    height = max(12, min(120, int(round(span_y / target_step_deg))))
    dx = span_x / float(width)
    dy = span_y / float(height)
    # Affine GDAL 6-tuple order: [x0, dx, 0.0, y_max, 0.0, -dy]
    transform = [minx, dx, 0.0, maxy, 0.0, -dy]
    inside_mask = _polygon_mask(polygon_geojson, transform, height, width)
    inside_count = int(np.sum(inside_mask))
    lat_mid = 0.5 * (miny + maxy)
    dx_m = dx * 111320.0 * max(0.2, math.cos(math.radians(lat_mid)))
    dy_m = dy * 111320.0
    pixel_area_m2 = float(inside_count) * dx_m * dy_m
    geom_obj = _extract_polygon_geom(polygon_geojson)
    poly_area_m2 = pixel_area_m2
    if geom_obj is not None:
        def _ring_area(ring_coords: Any) -> float:
            if not isinstance(ring_coords, (list, tuple)) or len(ring_coords) < 3:
                return 0.0
            pts_xy = [
                (float(pt[0]) * 111320.0 * max(0.2, math.cos(math.radians(lat_mid))), float(pt[1]) * 111320.0)
                for pt in ring_coords
                if isinstance(pt, (list, tuple)) and len(pt) >= 2
            ]
            if len(pts_xy) < 3:
                return 0.0
            s = 0.0
            for idx_p in range(len(pts_xy)):
                x1, y1 = pts_xy[idx_p]
                x2, y2 = pts_xy[(idx_p + 1) % len(pts_xy)]
                s += x1 * y2 - x2 * y1
            return abs(s) * 0.5
        coords_raw = geom_obj.get("coordinates") or []
        if geom_obj.get("type") == "Polygon" and coords_raw:
            outer = _ring_area(coords_raw[0])
            holes = sum(_ring_area(h) for h in coords_raw[1:])
            if outer > 0.0:
                poly_area_m2 = max(1.0, outer - holes)
        elif geom_obj.get("type") == "MultiPolygon" and coords_raw:
            total_mp = sum(max(0.0, _ring_area(poly_r[0]) - sum(_ring_area(h) for h in poly_r[1:])) for poly_r in coords_raw if poly_r)
            if total_mp > 0.0:
                poly_area_m2 = total_mp
    area_m2 = round(min(pixel_area_m2, poly_area_m2), 2)
    return {
        "crs": "EPSG:4326",
        "height": height,
        "width": width,
        "transform": transform,
        "bounds": [minx, miny, maxx, maxy],
        "inside_mask": inside_mask,
        "inside_count": inside_count,
        "cell_width_m": round(dx_m, 3),
        "cell_height_m": round(dy_m, 3),
        "area_m2": area_m2,
        "resolution_m": 10.0,
    }


def _reproject_band_to_canonical(
    src_arr: np.ndarray,
    src_crs: Any,
    src_transform_vals: Any,
    canonical_grid: Optional[Dict[str, Any]],
    *,
    categorical: bool = False,
) -> np.ndarray:
    """Reproject a scene raster cleanly onto canonical EPSG:4326 parcel grid."""
    if canonical_grid is None or not src_transform_vals or len(src_transform_vals) != 6:
        return np.asarray(src_arr, dtype=np.float32 if not categorical else np.int32)
    dst_h = int(canonical_grid["height"])
    dst_w = int(canonical_grid["width"])
    src_2d = np.asarray(src_arr)
    if src_2d.shape[:2] == (dst_h, dst_w):
        # Fast exact check when transform already aligns closely
        st = [float(x) for x in src_transform_vals]
        ct = [float(x) for x in canonical_grid["transform"]]
        if all(abs(st[i] - ct[i]) < 1e-6 for i in range(6)):
            return src_2d.astype(np.int32 if categorical else np.float32)

    src_t = Affine.from_gdal(*(float(x) for x in src_transform_vals))
    dst_t = Affine.from_gdal(*(float(x) for x in canonical_grid["transform"]))
    try:
        crs_obj = CRS.from_user_input(src_crs or "EPSG:4326")
    except Exception:
        crs_obj = CRS.from_epsg(4326)
    dst_crs = CRS.from_epsg(4326)

    if categorical:
        dst = np.zeros((dst_h, dst_w), dtype=np.int32)
        reproject(
            source=src_2d.astype(np.int32),
            destination=dst,
            src_transform=src_t,
            src_crs=crs_obj,
            dst_transform=dst_t,
            dst_crs=dst_crs,
            resampling=Resampling.nearest,
            src_nodata=-9999,
            dst_nodata=-9999,
        )
        return dst
    dst = np.full((dst_h, dst_w), np.nan, dtype=np.float32)
    reproject(
        source=src_2d.astype(np.float32),
        destination=dst,
        src_transform=src_t,
        src_crs=crs_obj,
        dst_transform=dst_t,
        dst_crs=dst_crs,
        resampling=Resampling.bilinear,
        src_nodata=np.nan,
        dst_nodata=np.nan,
    )
    return dst


def _compute_ensemble_covariance_13x13(
    ensemble: Dict[str, List[List[float]]],
    node_ids: Sequence[str],
) -> List[List[float]]:
    """Compute sample 13x13 state covariance matrix across active microzones & ensemble members."""
    rows: List[List[float]] = []
    for nid in node_ids:
        for member in ensemble.get(nid, []):
            rows.append([float(member[i]) for i in range(N_STATES)])
    if len(rows) < 2:
        return [[0.0 for _ in range(N_STATES)] for _ in range(N_STATES)]
    mat = np.asarray(rows, dtype=float)
    cov = np.cov(mat, rowvar=False, ddof=1)
    if cov.ndim == 0:
        cov = np.zeros((N_STATES, N_STATES), dtype=float)
    return [[round(float(cov[r, c]), 8) for c in range(N_STATES)] for r in range(N_STATES)]


def _summarize_13_state_ensemble(
    ensemble: Dict[str, List[List[float]]],
    node_ids: Sequence[str],
) -> Tuple[Dict[str, float], Dict[str, float], List[List[float]], Dict[str, List[float]], Dict[str, List[float]]]:
    """Return parcel-wide means/stds, 13x13 covariance, and per-node stats."""
    stats = compute_ensemble_statistics(ensemble, list(node_ids))
    per_node_means = stats.get("means", {})
    per_node_stds = stats.get("sigmas", {})

    all_members: List[List[float]] = []
    for nid in node_ids:
        for member in ensemble.get(nid, []):
            all_members.append(member)
    arr = np.asarray(all_members, dtype=float) if all_members else np.zeros((1, N_STATES), dtype=float)
    means_vec = np.mean(arr, axis=0)
    stds_vec = np.std(arr, axis=0, ddof=1) if arr.shape[0] > 1 else np.zeros(N_STATES, dtype=float)
    cov_13 = _compute_ensemble_covariance_13x13(ensemble, node_ids)

    state_means = {STATE_NAMES[i]: round(float(means_vec[i]), 6) for i in range(N_STATES)}
    state_stds = {STATE_NAMES[i]: round(float(stds_vec[i]), 6) for i in range(N_STATES)}
    return state_means, state_stds, cov_13, per_node_means, per_node_stds


_UNSUPPORTED_UNOBSERVED_STATES = frozenset({
    "thermal_stress",
    "salinity_stress",
    "biotic_confounder_risk",
})

_STATE_ADAPTIVE_RES_BASE: Dict[str, Tuple[float, str, str]] = {
    "vigor": (10.0, "S2_10M", "Sentinel-2 10m NIR/Red vegetation bands"),
    "bare_soil_fraction": (10.0, "S2_10M", "Sentinel-2 10m optical fraction"),
    "lai": (20.0, "S2_20M", "Sentinel-2 20m red-edge & SWIR structural proxy"),
    "chlorophyll": (20.0, "S2_20M", "Sentinel-2 20m red-edge chlorophyll bands"),
    "canopy_water": (20.0, "S2_20M", "Sentinel-2 20m SWIR B11 NDMI moisture band"),
    "phenology_progress": (20.0, "S2_20M", "Multi-date 20m optical-thermal stage coupling"),
    "structure": (30.0, "S1_SAR", "Sentinel-1 GRD SAR multi-look speckle smoothing"),
    "surface_wetness_event": (30.0, "S1_SAR", "Sentinel-1 VV roughness & multi-look kernel"),
    "root_zone_water": (40.0, "COUPLED_WATER", "Coupled SAR backscatter + L3 water balance"),
    "stress_memory": (40.0, "COUPLED_STRESS", "Multi-sensor seasonal stress memory"),
}


def compute_adaptive_state_spatial_resolution(
    state_name: str,
    *,
    accepted_count: int,
    has_spatial_rasters: bool,
    canonical_grid: Optional[Dict[str, Any]] = None,
    accepted_counts: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """Compute honest state-dependent effective resolution and whether 2D spatial detail is supported."""
    if state_name in _UNSUPPORTED_UNOBSERVED_STATES or accepted_count <= 0 or not has_spatial_rasters or canonical_grid is None:
        return {
            "effective_resolution_m": None,
            "spatial_support": "unavailable",
            "block_factor": 1,
            "suppress_surface": True,
            "limiting_factor": "no_direct_spatial_support",
        }

    base_res, driver, note = _STATE_ADAPTIVE_RES_BASE.get(state_name, (30.0, "COUPLED", "Derived field"))
    grid_res_m = max(10.0, float(canonical_grid.get("resolution_m", 10.0) or 10.0))
    inside_count = int(canonical_grid.get("inside_count") or 0)
    if inside_count <= 0 and isinstance(canonical_grid.get("inside_mask"), np.ndarray):
        inside_count = int(np.sum(canonical_grid["inside_mask"]))
    cw_m = float(canonical_grid.get("cell_width_m") or 0.0)
    ch_m = float(canonical_grid.get("cell_height_m") or 0.0)
    if canonical_grid.get("area_m2") is not None and float(canonical_grid["area_m2"]) > 0.0:
        area_m2 = float(canonical_grid["area_m2"])
    elif cw_m > 0.0 and ch_m > 0.0:
        area_m2 = inside_count * cw_m * ch_m
    else:
        area_m2 = inside_count * grid_res_m * grid_res_m
    cell_scale_m = math.sqrt(cw_m * ch_m) if (cw_m > 0.0 and ch_m > 0.0) else grid_res_m

    counts_map = accepted_counts or {}
    s2_n = int(counts_map.get("vigor", 0) or 0)
    s1_n = int(counts_map.get("structure", 0) or counts_map.get("surface_wetness_event", 0) or 0)

    eff_res = max(grid_res_m, base_res)
    limiting = note
    if driver in ("S1_SAR", "COUPLED_WATER"):
        if s1_n < 3:
            if driver == "S1_SAR":
                return {
                    "effective_resolution_m": None,
                    "spatial_support": "parcel_scalar_only",
                    "block_factor": 1,
                    "suppress_surface": True,
                    "limiting_factor": f"insufficient_s1_scenes:{s1_n}<3",
                }
            eff_res += 10.0
            limiting = f"low_sar_support:{s1_n}_scenes"
        elif s1_n < 8:
            eff_res += 10.0
            limiting = f"moderate_sar_support:{s1_n}_scenes"
    elif driver in ("S2_10M", "S2_20M"):
        if s2_n < 3:
            eff_res += 10.0
            limiting = f"low_s2_stack:{s2_n}_scenes"
        elif s2_n < 8:
            eff_res += 10.0
            limiting = f"sparse_s2_stack:{s2_n}_scenes"

    # Never claim sub-parcel grid detail when fewer than 3 independent cells of eff_res fit inside parcel
    if area_m2 > 0.0 and (area_m2 / (eff_res * eff_res)) < 3.0:
        return {
            "effective_resolution_m": None,
            "spatial_support": "parcel_scalar_only",
            "block_factor": 1,
            "suppress_surface": True,
            "limiting_factor": f"parcel_area_below_3_independent_{int(eff_res)}m_cells",
        }

    eff_res = max(10.0, float(round(eff_res)))  # Preserve strict 1m hold
    block_factor = max(1, int(round(eff_res / max(3.5, cell_scale_m))))
    return {
        "effective_resolution_m": eff_res,
        "spatial_support": f"adaptive_{int(eff_res)}m_{driver.lower()}",
        "block_factor": block_factor,
        "suppress_surface": False,
        "limiting_factor": limiting,
    }


def _build_historical_support_ledger(
    accepted_counts: Dict[str, int],
    *,
    has_spatial_rasters: bool = False,
    canonical_grid: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Build honest per-state support ledger reflecting real S1/S2 assimilation & adaptive spatial support."""
    ledger: Dict[str, Dict[str, Any]] = {}
    for idx, name in enumerate(STATE_NAMES):
        desc = STATE_DESCRIPTORS[idx]
        count = int(accepted_counts.get(name, 0) or 0)
        not_assimilated = (
            desc.assimilation_policy == AssimilationPolicy.NOT_ASSIMILATED
            or name in _UNSUPPORTED_UNOBSERVED_STATES
        )
        eff_res_m: Optional[float] = None
        if count > 0 and not not_assimilated:
            support_status = "temporally_conditioned"
            if has_spatial_rasters and name in _SPATIALLY_SUPPORTED_STATES and canonical_grid is not None:
                res_info = compute_adaptive_state_spatial_resolution(
                    name,
                    accepted_count=count,
                    has_spatial_rasters=True,
                    canonical_grid=canonical_grid,
                    accepted_counts=accepted_counts,
                )
                spatial_support = str(res_info["spatial_support"])
                eff_res_m = res_info["effective_resolution_m"]
            elif has_spatial_rasters and name in _SPATIALLY_SUPPORTED_STATES:
                base_r, drv, _ = _STATE_ADAPTIVE_RES_BASE.get(name, (30.0, "COUPLED", ""))
                eff_res_m = float(base_r)
                spatial_support = f"adaptive_{int(base_r)}m_{drv.lower()}"
            else:
                spatial_support = "parcel_assimilated"
            obs_rel = "direct" if name in ("vigor", "canopy_water", "surface_wetness_event", "structure") else "indirect"
            blocks: List[str] = []
        elif not_assimilated:
            support_status = "unsupported"
            spatial_support = "unavailable"
            obs_rel = "none"
            blocks = ["no_direct_physical_observation_channel"]
        else:
            support_status = "prior_constrained"
            spatial_support = "unavailable"
            obs_rel = "none"
            blocks = ["no_accepted_state_update"]

        ledger[name] = {
            "state": name,
            "accepted_update_count": count,
            "support_status": support_status,
            "spatial_support": spatial_support,
            "effective_resolution_m": eff_res_m,
            "certified_1m": False,
            "observation_relationship": obs_rel,
            "field_approval_eligible": False,  # Historical reconstruction remains diagnostic-only
            "block_reasons": blocks,
        }
    return ledger


_SAFE_DIR_CACHE: Dict[str, Dict[str, Path]] = {}


def _resolve_safe_dir(
    store_base: Path,
    plot_id: str,
    obs_record: Dict[str, Any],
) -> Optional[Path]:
    """Resolve real .SAFE product directory across direct scene_id, product_id, hash, or acq timestamp."""
    plot_dir = store_base if str(store_base.name) == str(plot_id) else (
        store_base / plot_id if (store_base / plot_id).is_dir() else store_base
    )
    scene_id = str(obs_record.get("scene_id") or "")
    for cand_name in (
        scene_id,
        str(obs_record.get("provider_product_id") or ""),
        str(obs_record.get("catalog_item_id") or ""),
    ):
        if cand_name:
            cand = plot_dir / cand_name
            if (cand / "metadata.json").is_file():
                return cand

    cache_key = str(plot_dir.resolve()) if plot_dir.exists() else str(plot_dir)
    idx = _SAFE_DIR_CACHE.get(cache_key)
    if idx is None or len(idx) == 0:
        idx = {}
        if plot_dir.is_dir():
            for sd in sorted(plot_dir.iterdir()):
                mp = sd / "metadata.json"
                if not sd.is_dir() or not mp.is_file():
                    continue
                try:
                    meta = json.loads(mp.read_text(encoding="utf-8"))
                except Exception:
                    continue
                is_s2 = (sd / "B04.npz").is_file() or "s2" in str(meta.get("sensor") or "").lower()
                is_s1 = (sd / "VV.npz").is_file() or "s1" in str(meta.get("sensor") or "").lower()
                sens = "sentinel2" if is_s2 else ("sentinel1" if is_s1 else "")
                for k in (
                    f"dir:{sd.name}",
                    f"prod:{meta.get('provider_product_id') or ''}",
                    f"cat:{meta.get('catalog_item_id') or ''}",
                    f"hash:{meta.get('content_hash') or ''}",
                ):
                    if not k.endswith(":"):
                        idx[k] = sd
                acq = str(meta.get("acquisition_datetime") or "")
                if acq:
                    idx[f"acq:{sens}:{acq[:19]}"] = sd
                    idx[f"acq_day:{sens}:{acq[:10]}"] = sd
                    idx[f"acq_any:{acq[:19]}"] = sd
        _SAFE_DIR_CACHE[cache_key] = idx

    source_raw = str(obs_record.get("source") or "").lower()
    src_norm = "sentinel2" if ("s2" in source_raw or "sentinel2" in source_raw) else (
        "sentinel1" if ("s1" in source_raw or "sentinel1" in source_raw) else ""
    )
    acq_obs = str(obs_record.get("acquisition_time") or obs_record.get("observation_time") or "")
    expected_hash = str(obs_record.get("source_content_hash") or "")
    for lookup in (
        f"prod:{obs_record.get('provider_product_id') or ''}",
        f"cat:{obs_record.get('catalog_item_id') or ''}",
        f"hash:{expected_hash}",
        f"acq:{src_norm}:{acq_obs[:19]}",
        f"acq_day:{src_norm}:{acq_obs[:10]}",
        f"acq_any:{acq_obs[:19]}",
    ):
        if lookup in idx:
            return idx[lookup]
    return None


def _load_scene_raster_observations(
    obs_record: Dict[str, Any],
    scene_store: Optional[SceneProductStore],
    plot_id: str,
    polygon_geojson: Optional[Dict[str, Any]],
    canonical_grid: Optional[Dict[str, Any]] = None,
    return_grids: bool = False,
) -> Any:
    """Extract EnKF scalar & optional canonical-grid 2D observations from worldline/disk rasters."""
    metrics = dict(obs_record.get("metrics") or {})
    source = str(obs_record.get("source") or "").lower()
    scene_id = str(obs_record.get("scene_id") or "")
    expected_hash = str(obs_record.get("source_content_hash") or "")
    grids_out: Dict[str, np.ndarray] = {}

    def _ret(chans: Dict[str, float]) -> Any:
        return (chans, grids_out) if return_grids else chans

    # Prefer direct raster extraction from cached SceneProductStore when present
    if scene_store is not None:
        store_base = Path(getattr(scene_store, "base_dir", ""))
        safe_dir = _resolve_safe_dir(store_base, plot_id, obs_record)
        meta_path = (safe_dir / "metadata.json") if safe_dir is not None else Path("")
        if safe_dir is not None and meta_path.is_file():
            try:
                if "sentinel2" in source or source == "s2":
                    b04_p = safe_dir / "B04.npz"
                    b08_p = safe_dir / "B08.npz"
                    b11_p = safe_dir / "B11.npz"
                    scl_p = safe_dir / "SCL.npz"
                    dm_p = safe_dir / "DATAMASK.npz"
                    if not dm_p.is_file():
                        dm_p = safe_dir / "dataMask.npz"
                    if b04_p.is_file() and b08_p.is_file():
                        b04_raw = np.asarray(scene_store.raster_store.load_band(str(b04_p)), dtype=np.float64)
                        b08_raw = np.asarray(scene_store.raster_store.load_band(str(b08_p)), dtype=np.float64)
                        meta = json.loads(meta_path.read_text(encoding="utf-8"))
                        src_crs = meta.get("crs")
                        src_tf = meta.get("transform")
                        if canonical_grid is not None and src_tf:
                            b04 = _reproject_band_to_canonical(b04_raw, src_crs, src_tf, canonical_grid).astype(np.float64)
                            b08 = _reproject_band_to_canonical(b08_raw, src_crs, src_tf, canonical_grid).astype(np.float64)
                            inside = canonical_grid["inside_mask"]
                            H, W = int(canonical_grid["height"]), int(canonical_grid["width"])
                        else:
                            b04, b08 = b04_raw, b08_raw
                            H, W = b04.shape[:2]
                            inside = _polygon_mask(polygon_geojson, src_tf, H, W)

                        valid = inside & np.isfinite(b04) & np.isfinite(b08) & ((b08 + b04) > 1e-6)
                        if dm_p.is_file():
                            dm_raw = np.asarray(scene_store.raster_store.load_band(str(dm_p)), dtype=np.float64)
                            dm = (
                                _reproject_band_to_canonical(dm_raw, src_crs, src_tf, canonical_grid, categorical=True)
                                if canonical_grid is not None and src_tf else dm_raw
                            )
                            if dm.shape[:2] == (H, W):
                                valid &= (dm > 0)
                        if scl_p.is_file():
                            scl_raw = np.rint(scene_store.raster_store.load_band(str(scl_p))).astype(np.int32)
                            if canonical_grid is not None and src_tf:
                                scl = _reproject_band_to_canonical(scl_raw, src_crs, src_tf, canonical_grid, categorical=True)
                            else:
                                scl = scl_raw
                            if scl.shape[:2] == (H, W):
                                valid &= ~np.isin(scl, [-9999, 0, 1, 3, 8, 9, 10, 11])
                        extracted: Dict[str, float] = {}
                        if int(np.sum(valid)) > 0:
                            ndvi_arr = np.full((H, W), np.nan, dtype=np.float32)
                            ndvi_vals = np.clip((b08[valid] - b04[valid]) / (b08[valid] + b04[valid]), -1.0, 1.0)
                            ndvi_arr[valid] = ndvi_vals.astype(np.float32)
                            extracted["ndvi"] = round(float(np.mean(ndvi_vals)), 6)
                            if return_grids and canonical_grid is not None:
                                grids_out["ndvi"] = ndvi_arr
                            if b11_p.is_file():
                                b11_raw = np.asarray(scene_store.raster_store.load_band(str(b11_p)), dtype=np.float64)
                                b11 = (
                                    _reproject_band_to_canonical(b11_raw, src_crs, src_tf, canonical_grid).astype(np.float64)
                                    if canonical_grid is not None and src_tf else b11_raw
                                )
                                ndmi_m = valid & np.isfinite(b11) & ((b08 + b11) > 1e-6)
                                if int(np.sum(ndmi_m)) > 0:
                                    ndmi_arr = np.full((H, W), np.nan, dtype=np.float32)
                                    ndmi_vals = np.clip((b08[ndmi_m] - b11[ndmi_m]) / (b08[ndmi_m] + b11[ndmi_m]), -1.0, 1.0)
                                    ndmi_arr[ndmi_m] = ndmi_vals.astype(np.float32)
                                    extracted["ndmi"] = round(float(np.mean(ndmi_vals)), 6)
                                    if return_grids and canonical_grid is not None:
                                        grids_out["ndmi"] = ndmi_arr
                        if extracted:
                            return _ret(extracted)
                elif "sentinel1" in source or source == "s1":
                    vv_p = safe_dir / "VV.npz"
                    vh_p = safe_dir / "VH.npz"
                    if vv_p.is_file():
                        vv_raw = np.asarray(scene_store.raster_store.load_band(str(vv_p)), dtype=np.float64)
                        meta = json.loads(meta_path.read_text(encoding="utf-8"))
                        src_crs = meta.get("crs")
                        src_tf = meta.get("transform")
                        raw_inside = _polygon_mask(polygon_geojson, src_tf, vv_raw.shape[0], vv_raw.shape[1])
                        vv_unit = str((meta.get("band_units") or {}).get("VV", "")).lower()
                        vv_is_db = "db" in vv_unit or bool(np.any(vv_raw[raw_inside & np.isfinite(vv_raw)] < 0.0))
                        # Reproject S1 normalized feature linearly in dB/intensity space safely
                        if canonical_grid is not None and src_tf:
                            vv = _reproject_band_to_canonical(vv_raw, src_crs, src_tf, canonical_grid).astype(np.float64)
                            inside = canonical_grid["inside_mask"]
                            H, W = int(canonical_grid["height"]), int(canonical_grid["width"])
                        else:
                            vv = vv_raw
                            inside = raw_inside
                            H, W = vv.shape[:2]

                        valid = inside & np.isfinite(vv) & (True if vv_is_db else (vv > 1e-12))
                        extracted_s1: Dict[str, float] = {}
                        if int(np.sum(valid)) > 0:
                            vv_norm = _normalized_backscatter_feature(vv[valid], "VV", vv_is_db)
                            vv_arr = np.full((H, W), np.nan, dtype=np.float32)
                            vv_arr[valid] = np.asarray(vv_norm, dtype=np.float32)
                            extracted_s1["sar_vv"] = round(float(np.mean(vv_norm)), 6)
                            if return_grids and canonical_grid is not None:
                                grids_out["sar_vv"] = vv_arr
                            if vh_p.is_file():
                                vh_raw = np.asarray(scene_store.raster_store.load_band(str(vh_p)), dtype=np.float64)
                                vh_unit = str((meta.get("band_units") or {}).get("VH", "")).lower()
                                vh_is_db = "db" in vh_unit or bool(np.any(vh_raw[raw_inside & np.isfinite(vh_raw)] < 0.0))
                                vh = (
                                    _reproject_band_to_canonical(vh_raw, src_crs, src_tf, canonical_grid).astype(np.float64)
                                    if canonical_grid is not None and src_tf else vh_raw
                                )
                                vh_m = valid & np.isfinite(vh) & (True if vh_is_db else (vh > 1e-12))
                                if int(np.sum(vh_m)) > 0:
                                    vh_norm = _normalized_backscatter_feature(vh[vh_m], "VH", vh_is_db)
                                    vh_arr = np.full((H, W), np.nan, dtype=np.float32)
                                    vh_arr[vh_m] = np.asarray(vh_norm, dtype=np.float32)
                                    extracted_s1["sar_vh"] = round(float(np.mean(vh_norm)), 6)
                                    if return_grids and canonical_grid is not None:
                                        grids_out["sar_vh"] = vh_arr
                        if extracted_s1:
                            return _ret(extracted_s1)
            except Exception as exc:
                logger.debug("Fallback to metrics on scene %s (hash=%s): %s", scene_id, expected_hash[:12], exc)

    # Fallback directly from verified worldline metrics payload
    obs_out: Dict[str, float] = {}
    if "sentinel2" in source or source == "s2":
        for key in ("ndvi", "ndvi_mean"):
            val = metrics.get(key)
            if isinstance(val, (int, float)) and not isinstance(val, bool) and math.isfinite(float(val)):
                obs_out["ndvi"] = round(float(np.clip(float(val), -1.0, 1.0)), 6)
                break
        for key in ("ndmi", "ndmi_mean"):
            val = metrics.get(key)
            if isinstance(val, (int, float)) and not isinstance(val, bool) and math.isfinite(float(val)):
                obs_out["ndmi"] = round(float(np.clip(float(val), -1.0, 1.0)), 6)
                break
        for key in ("ndre", "ndre_mean"):
            val = metrics.get(key)
            if isinstance(val, (int, float)) and not isinstance(val, bool) and math.isfinite(float(val)):
                obs_out["ndre"] = round(float(np.clip(float(val), -1.0, 1.0)), 6)
                break
    elif "sentinel1" in source or source == "s1":
        vv_db = metrics.get("vv_mean_db")
        if isinstance(vv_db, (int, float)) and not isinstance(vv_db, bool) and math.isfinite(float(vv_db)):
            obs_out["sar_vv"] = round(float(_normalized_backscatter_feature(np.array([float(vv_db)]), "VV", True)[0]), 6)
        vh_db = metrics.get("vh_mean_db")
        if isinstance(vh_db, (int, float)) and not isinstance(vh_db, bool) and math.isfinite(float(vh_db)):
            obs_out["sar_vh"] = round(float(_normalized_backscatter_feature(np.array([float(vh_db)]), "VH", True)[0]), 6)
    return _ret(obs_out)


@dataclass
class PosteriorCheckpoint:
    checkpoint_id: str
    schema_version: str
    plot_id: str
    tenant_id: str
    namespace: str
    geometry_hash: str
    model_version: str
    state_schema_version: str
    calibration_version: str
    cutoff_valid_time: str
    knowledge_cutoff_time: str
    boundary_reason: str
    last_obs_event_id: str
    last_obs_time: str
    assimilated_observation_ids: List[str]
    ensemble_members: Dict[str, List[List[float]]]
    rng_state_json: Any
    state_means: Dict[str, float]
    state_stds: Dict[str, float]
    state_covariance: List[List[float]]
    per_node_means: Dict[str, List[float]]
    per_node_stds: Dict[str, List[float]]
    accepted_update_counts: Dict[str, int]
    state_support_ledger: Dict[str, Dict[str, Any]]
    parent_checkpoint_id: Optional[str] = None
    supersedes_checkpoint_id: Optional[str] = None
    late_arrival_event_ids: List[str] = field(default_factory=list)
    trajectory_segment: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = ""
    channel_calibration: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    canonical_grid: Optional[Dict[str, Any]] = None
    spatial_artifact: Optional[str] = None
    has_spatial_observations: bool = False
    specialist_chrono_state: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PosteriorCheckpoint":
        allowed = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in allowed})

    def summary_dict(self) -> Dict[str, Any]:
        """Lightweight metadata view omitting full ensemble arrays for reports."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "cutoff_valid_time": self.cutoff_valid_time,
            "knowledge_cutoff_time": self.knowledge_cutoff_time,
            "boundary_reason": self.boundary_reason,
            "model_version": self.model_version,
            "state_schema_version": self.state_schema_version,
            "calibration_version": self.calibration_version,
            "assimilated_observation_count": len(self.assimilated_observation_ids),
            "last_obs_event_id": self.last_obs_event_id,
            "parent_checkpoint_id": self.parent_checkpoint_id,
            "supersedes_checkpoint_id": self.supersedes_checkpoint_id,
            "late_arrival_event_ids": list(self.late_arrival_event_ids),
            "has_spatial_observations": bool(self.has_spatial_observations),
            "spatial_artifact": self.spatial_artifact,
            "state_means": dict(self.state_means),
            "state_stds": dict(self.state_stds),
            "state_covariance": self.state_covariance,
        }


class HistoricalStateReconstructor:
    """Reconstructs 13-state ASMAE history chronologically with versioned checkpoints & late-arrival replay."""

    def __init__(
        self,
        worldline: Optional[CanonicalWorldlineService] = None,
        checkpoint_root: Optional[Path] = None,
        scene_store: Optional[SceneProductStore] = None,
        n_zone_rows: int = 2,
        n_zone_cols: int = 2,
        n_ensemble: int = 25,
        checkpoint_stride: int = 20,
    ) -> None:
        self.worldline = worldline or CanonicalWorldlineService()
        self.checkpoint_root = Path(
            checkpoint_root or (self.worldline.root.parent / "historical_posterior_checkpoints")
        ).resolve()
        self.checkpoint_root.mkdir(parents=True, exist_ok=True)
        self.scene_store = scene_store
        self.n_zone_rows = max(1, int(n_zone_rows))
        self.n_zone_cols = max(1, int(n_zone_cols))
        self.n_ensemble = max(6, int(n_ensemble))
        self.checkpoint_stride = max(1, int(checkpoint_stride))
        self.cross_layer_bridge = CrossLayerSpecialistBridge()
        self.node_ids = [
            f"mz_{r:03d}_{c:03d}"
            for r in range(self.n_zone_rows)
            for c in range(self.n_zone_cols)
        ]

    def _plot_cp_dir(self, plot_id: str, tenant_id: str, namespace: str) -> Path:
        d = self.checkpoint_root / tenant_id / namespace / CanonicalWorldlineService._plot_key(plot_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _index_path(self, plot_id: str, tenant_id: str, namespace: str) -> Path:
        return self._plot_cp_dir(plot_id, tenant_id, namespace) / "checkpoint_index.json"

    def load_checkpoint_index(
        self, plot_id: str, tenant_id: str = "default_tenant", namespace: str = "default"
    ) -> Dict[str, Any]:
        p = self._index_path(plot_id, tenant_id, namespace)
        if not p.exists():
            return {"active_chain": [], "historical_chains": [], "latest_worldline_posterior_event_id": None}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"active_chain": [], "historical_chains": []}
        except Exception:
            return {"active_chain": [], "historical_chains": []}

    def load_checkpoint(
        self, plot_id: str, checkpoint_id: str, tenant_id: str = "default_tenant", namespace: str = "default"
    ) -> Optional[PosteriorCheckpoint]:
        cp_path = self._plot_cp_dir(plot_id, tenant_id, namespace) / "checkpoints" / f"{checkpoint_id}.json"
        if not cp_path.exists():
            return None
        try:
            return PosteriorCheckpoint.from_dict(json.loads(cp_path.read_text(encoding="utf-8")))
        except Exception as exc:
            logger.warning("Failed loading posterior checkpoint %s: %s", checkpoint_id, exc)
            return None

    def _save_checkpoint(
        self,
        cp: PosteriorCheckpoint,
        spatial_arrays: Optional[Dict[str, np.ndarray]] = None,
    ) -> None:
        cp_dir = self._plot_cp_dir(cp.plot_id, cp.tenant_id, cp.namespace) / "checkpoints"
        cp_dir.mkdir(parents=True, exist_ok=True)
        if spatial_arrays:
            npz_name = f"{cp.checkpoint_id}.npz"
            npz_path = cp_dir / npz_name
            if not npz_path.exists():
                tmp_npz = cp_dir / f"{cp.checkpoint_id}.tmp.npz"
                np.savez_compressed(tmp_npz, **spatial_arrays)
                tmp_npz.replace(npz_path)
            cp.spatial_artifact = npz_name
        target = cp_dir / f"{cp.checkpoint_id}.json"
        if not target.exists():
            tmp = target.with_suffix(".tmp")
            tmp.write_text(json.dumps(cp.to_dict(), sort_keys=True), encoding="utf-8")
            tmp.replace(target)

    def _load_spatial_arrays(
        self,
        cp: PosteriorCheckpoint,
    ) -> Optional[Dict[str, np.ndarray]]:
        if not cp.spatial_artifact:
            return None
        cp_dir = self._plot_cp_dir(cp.plot_id, cp.tenant_id, cp.namespace) / "checkpoints"
        npz_path = cp_dir / str(cp.spatial_artifact)
        if not npz_path.exists():
            return None
        try:
            with np.load(npz_path, allow_pickle=False) as d:
                return {k: np.asarray(d[k]) for k in d.files}
        except Exception as exc:
            logger.warning("Failed loading spatial npz for checkpoint %s: %s", cp.checkpoint_id, exc)
            return None

    def _save_checkpoint_index(
        self, plot_id: str, tenant_id: str, namespace: str, index_data: Dict[str, Any]
    ) -> None:
        p = self._index_path(plot_id, tenant_id, namespace)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(index_data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(p)

    def load_qualified_observations(
        self,
        *,
        plot_id: str,
        valid_time_T: Any,
        knowledge_cutoff_K: Any,
        tenant_id: str = "default_tenant",
        namespace: str = "default",
    ) -> List[Dict[str, Any]]:
        """Query canonical OBSERVATION_QUALIFIED events filtered at (T, K)."""
        events = self.worldline.select_eligible_events(
            plot_id=plot_id,
            event_type="OBSERVATION_QUALIFIED",
            valid_time_T=valid_time_T,
            knowledge_cutoff_K=knowledge_cutoff_K,
            tenant_id=tenant_id,
            namespace=namespace,
            fail_on_corrupt=True,
        )
        events.sort(
            key=lambda ev: (
                _parse_utc_iso(ev.get("observation_or_valid_time") or ev.get("effective_at")),
                str((ev.get("payload") or {}).get("observation_qualified", {}).get("scene_id") or ""),
                str(ev.get("event_id") or ""),
            )
        )
        return events

    @staticmethod
    def _checkpoint_identity(
        *,
        plot_id: str,
        geometry_hash: str,
        cutoff_valid_time: str,
        assimilated_observation_ids: Sequence[str],
        parent_checkpoint_id: Optional[str],
    ) -> str:
        raw = json.dumps(
            {
                "plot_id": plot_id,
                "geometry_hash": geometry_hash,
                "model_version": RECONSTRUCTOR_MODEL_VERSION,
                "state_schema_version": STATE_SCHEMA_VERSION,
                "calibration_version": CALIBRATION_VERSION,
                "cutoff_valid_time": cutoff_valid_time,
                "assimilated_observation_ids": list(assimilated_observation_ids),
                "parent_checkpoint_id": parent_checkpoint_id,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return f"cp13_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]}"

    @staticmethod
    def _predict_pre_update_channels(
        ensemble: Dict[str, List[List[float]]],
        node_ids: Sequence[str],
        obs_channels: Dict[str, float],
        scene_meta: Dict[str, Any],
        channel_cal: Optional[Dict[str, Dict[str, Any]]] = None,
        elapsed_days: float = 0.0,
        obs_dt: Optional[datetime] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Evaluate forward models + strictly causal operator calibration BEFORE assimilating scene_i."""
        preds: Dict[str, Dict[str, Any]] = {}
        cloud_frac = float(scene_meta.get("cloud_score", 0.0) or 0.0)
        valid_frac = float(scene_meta.get("valid_pixel_fraction", 1.0) or 1.0)
        if valid_frac <= 0.0:
            valid_frac = 0.5
        cal_map = channel_cal or {}
        for obs_name, obs_val in sorted(obs_channels.items()):
            mapping = INDEX_STATE_REGISTRY.get(obs_name)
            if mapping is None:
                continue
            member_preds: List[float] = []
            for nid in node_ids:
                for member in ensemble.get(nid, []):
                    y_hat = (
                        predict_sar_observation(obs_name, member)
                        if mapping.sensor == "S1"
                        else predict_observation(obs_name, member)
                    )
                    if y_hat is not None and math.isfinite(float(y_hat)):
                        member_preds.append(float(y_hat))
            if not member_preds:
                continue
            sigma_obs = compute_observation_noise(
                obs_name,
                cloud_fraction=cloud_frac,
                valid_support_fraction=valid_frac,
            )
            raw_pred_mean = float(np.mean(member_preds))
            pred_var = float(np.var(member_preds, ddof=1)) if len(member_preds) > 1 else 0.0
            raw_var = max(1e-8, pred_var + sigma_obs * sigma_obs)
            raw_sigma = math.sqrt(raw_var)

            # Strictly causal prior linear-shrinkage, innovation anchor & spread calibration from t < now
            cal = apply_causal_channel_calibration(
                cal_map.get(obs_name),
                obs_name=obs_name,
                raw_pred_mean=raw_pred_mean,
                raw_pred_var=pred_var,
                obs_sigma=sigma_obs,
                elapsed_days=elapsed_days,
                now_dt=obs_dt,
            )
            cal_pred_mean = cal["cal_pred_mean"]
            bias_prior = cal["bias_prior"]
            slope_prior = cal["slope_prior"]
            cal_sigma = cal["cal_sigma"]
            unscaled_sigma = cal["unscaled_sigma"]
            var_scale_prior = cal["var_scale_prior"]

            residual_cal = float(obs_val) - cal_pred_mean
            residual_raw = float(obs_val) - raw_pred_mean
            preds[obs_name] = {
                "sensor": mapping.sensor,
                "y_obs": round(float(obs_val), 6),
                "y_pred_prior": round(cal_pred_mean, 6),
                "y_pred_calibrated": round(cal_pred_mean, 6),
                "y_pred_raw": round(raw_pred_mean, 6),
                "bias_offset_applied": round(bias_prior, 6),
                "slope_applied": round(slope_prior, 6),
                "pred_sigma": round(cal_sigma, 6),
                "unscaled_pred_sigma": round(unscaled_sigma, 6),
                "raw_pred_sigma": round(raw_sigma, 6),
                "var_scale_applied": round(var_scale_prior, 4),
                "obs_sigma": round(float(sigma_obs), 6),
                "residual": round(residual_cal, 6),
                "raw_residual": round(residual_raw, 6),
                "z_score": round(residual_cal / cal_sigma, 4) if cal_sigma > 1e-8 else 0.0,
                "raw_z_score": round(residual_raw / raw_sigma, 4) if raw_sigma > 1e-8 else 0.0,
            }
        return preds

    @staticmethod
    def _update_spatial_anomaly_field(
        *,
        spatial_delta: np.ndarray,
        spatial_var: np.ndarray,
        spatial_obs_count: np.ndarray,
        inside_mask: np.ndarray,
        obs_grids: Dict[str, np.ndarray],
        elapsed_days: float,
        post_stds: Dict[str, float],
        has_spatial_observations: bool,
    ) -> bool:
        """Advance & assimilate spatially resolved canonical 10m state anomaly fields."""
        if not has_spatial_observations and not obs_grids:
            return False

        # Decay anomalies & grow spatial uncertainty over elapsed days
        if elapsed_days > 0.0:
            decay = math.exp(-min(90.0, elapsed_days) / 42.0)
            spatial_delta[:, inside_mask] *= decay
            for s_idx, s_name in enumerate(_SPATIALLY_SUPPORTED_STATES):
                lo, hi = STATE_BOUNDS[s_name]
                span = max(0.25, hi - lo)
                q_var = ((0.03 * span) ** 2) * min(35.0, elapsed_days) / 14.0
                spatial_var[s_idx, inside_mask] = np.minimum(
                    (0.45 * span) ** 2,
                    spatial_var[s_idx, inside_mask] + q_var,
                )

        if not obs_grids:
            return has_spatial_observations

        updated_any = False
        # Compute centered optical & SAR spatial anomalies inside valid pixels
        anom: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
        for ch_name, grid in obs_grids.items():
            valid = inside_mask & np.isfinite(grid)
            if int(np.sum(valid)) >= 4:
                ch_anom = np.zeros_like(grid, dtype=np.float32)
                mean_val = float(np.mean(grid[valid]))
                ch_anom[valid] = (grid[valid] - mean_val).astype(np.float32)
                anom[ch_name] = (ch_anom, valid)

        if not anom:
            return has_spatial_observations

        state_pos = {name: i for i, name in enumerate(_SPATIALLY_SUPPORTED_STATES)}
        any_valid_union = np.zeros_like(inside_mask, dtype=bool)
        for ch_anom, valid_m in anom.values():
            any_valid_union |= valid_m

        # Update optical-coupled states from NDVI/NDMI spatial anomalies
        if "ndvi" in anom or "ndmi" in anom:
            opt_valid = np.zeros_like(inside_mask, dtype=bool)
            d_ndvi = np.zeros_like(inside_mask, dtype=np.float32)
            d_ndmi = np.zeros_like(inside_mask, dtype=np.float32)
            if "ndvi" in anom:
                d_ndvi, v1 = anom["ndvi"]
                opt_valid |= v1
            if "ndmi" in anom:
                d_ndmi, v2 = anom["ndmi"]
                opt_valid |= v2
            for s_name, (w_ndvi, w_ndmi) in _OPTICAL_SPATIAL_COUPLINGS.items():
                k = state_pos[s_name]
                target_anom = (w_ndvi * d_ndvi[opt_valid] + w_ndmi * d_ndmi[opt_valid]).astype(np.float32)
                spatial_delta[k, opt_valid] = 0.55 * spatial_delta[k, opt_valid] + 0.45 * target_anom
                p_std = max(0.01, float(post_stds.get(s_name, 0.05)))
                spatial_var[k, opt_valid] = 0.55 * spatial_var[k, opt_valid] + 0.45 * (p_std * p_std)
                updated_any = True

        # Update SAR-coupled states from VV/VH spatial backscatter anomalies
        if "sar_vv" in anom or "sar_vh" in anom:
            sar_valid = np.zeros_like(inside_mask, dtype=bool)
            d_vv = np.zeros_like(inside_mask, dtype=np.float32)
            d_vh = np.zeros_like(inside_mask, dtype=np.float32)
            if "sar_vv" in anom:
                d_vv, v1 = anom["sar_vv"]
                sar_valid |= v1
            if "sar_vh" in anom:
                d_vh, v2 = anom["sar_vh"]
                sar_valid |= v2
            for s_name, (w_vv, w_vh) in _SAR_SPATIAL_COUPLINGS.items():
                k = state_pos[s_name]
                target_anom = (w_vv * d_vv[sar_valid] + w_vh * d_vh[sar_valid]).astype(np.float32)
                alpha_sar = 0.40 if "root" in s_name else 0.45
                spatial_delta[k, sar_valid] = (1.0 - alpha_sar) * spatial_delta[k, sar_valid] + alpha_sar * target_anom
                p_std = max(0.01, float(post_stds.get(s_name, 0.05)))
                spatial_var[k, sar_valid] = 0.60 * spatial_var[k, sar_valid] + 0.40 * (p_std * p_std)
                updated_any = True

        if updated_any:
            spatial_obs_count[any_valid_union] += 1
        return bool(has_spatial_observations or updated_any)

    @staticmethod
    def build_spatial_surfaces_payload(
        *,
        canonical_grid: Optional[Dict[str, Any]],
        state_means: Dict[str, float],
        state_stds: Dict[str, float],
        accepted_counts: Dict[str, int],
        spatial_delta: Optional[np.ndarray],
        spatial_var: Optional[np.ndarray],
        has_spatial_observations: bool,
        spatial_obs_count: Optional[np.ndarray] = None,
    ) -> List[Dict[str, Any]]:
        """Assemble Layer-10 compatible 2D state surfaces with spatially varying local effective resolution."""
        if not has_spatial_observations or canonical_grid is None or spatial_delta is None:
            return []
        H = int(canonical_grid["height"])
        W = int(canonical_grid["width"])
        inside = np.asarray(canonical_grid["inside_mask"], dtype=bool)
        if inside.shape != (H, W) or not np.any(inside):
            return []
        bounds = canonical_grid.get("bounds")
        grid_res_m = float(canonical_grid.get("resolution_m", 10.0) or 10.0)

        # Perimeter / edge pixels experience Sentinel PSF mixed-pixel boundary contamination
        padded = np.pad(inside, 1, mode="constant", constant_values=False)
        interior_4 = padded[1:-1, 1:-1] & padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:]
        edge_mask = inside & (~interior_4)

        low_obs_mask = np.zeros((H, W), dtype=bool)
        very_low_obs_mask = np.zeros((H, W), dtype=bool)
        if spatial_obs_count is not None and spatial_obs_count.shape == (H, W):
            obs_inside = spatial_obs_count[inside]
            med_obs = float(np.median(obs_inside)) if obs_inside.size > 0 else 0.0
            if med_obs >= 2.0:
                low_obs_mask = inside & (spatial_obs_count < 0.70 * med_obs)
                very_low_obs_mask = inside & (spatial_obs_count < 0.40 * med_obs)

        # Map ASMAE state key -> Layer 10 frontend surfaceType expected by asmae-13-states.ts
        surface_type_map = {
            "vigor": "ASMAE_VIGOR",
            "lai": "ASMAE_LAI",
            "chlorophyll": "ASMAE_CHLOROPHYLL",
            "canopy_water": "ASMAE_CANOPY_WATER",
            "root_zone_water": "ASMAE_ROOT_ZONE_WATER",
            "surface_wetness_event": "ASMAE_SURFACE_WETNESS_EVENT",
            "structure": "ASMAE_STRUCTURE",
            "bare_soil_fraction": "ASMAE_BARE_SOIL",
            "phenology_progress": "ASMAE_PHENOLOGY_PROGRESS",
            "stress_memory": "ASMAE_STRESS_MEMORY",
        }
        surfaces: List[Dict[str, Any]] = []
        for s_idx, s_name in enumerate(_SPATIALLY_SUPPORTED_STATES):
            if s_name in _UNSUPPORTED_UNOBSERVED_STATES:
                continue
            acc_cnt = int(accepted_counts.get(s_name, 0) or 0)
            if acc_cnt <= 0:
                continue
            res_info = compute_adaptive_state_spatial_resolution(
                s_name,
                accepted_count=acc_cnt,
                has_spatial_rasters=True,
                canonical_grid=canonical_grid,
                accepted_counts=accepted_counts,
            )
            if res_info.get("suppress_surface") or res_info.get("effective_resolution_m") is None:
                continue
            eff_res_m = float(res_info["effective_resolution_m"])
            block_k = max(1, int(res_info.get("block_factor", 1) or 1))

            mean_val = float(state_means.get(s_name, 0.0))
            lo, hi = STATE_BOUNDS[s_name]
            arr = np.full((H, W), np.nan, dtype=np.float32)
            vals_in = np.clip(mean_val + spatial_delta[s_idx, inside], lo, hi)
            if len(vals_in) > 0:
                shift = mean_val - float(np.mean(vals_in))
                vals_in = np.clip(vals_in + shift, lo, hi)
            arr[inside] = vals_in.astype(np.float32)

            unc_arr = np.full((H, W), np.nan, dtype=np.float32)
            if spatial_var is not None:
                unc_arr[inside] = np.sqrt(np.maximum(1e-8, spatial_var[s_idx, inside])).astype(np.float32)
            else:
                unc_arr[inside] = float(state_stds.get(s_name, 0.05))

            # Spatially varying per-pixel local resolution driven by boundary mixing,
            # local observation density, and local uncertainty dispersion.
            high_disp_mask = np.zeros((H, W), dtype=bool)
            unc_in = unc_arr[inside]
            med_unc = float(np.median(unc_in)) if unc_in.size > 0 else 0.05
            if med_unc > 1e-6:
                high_disp_mask = inside & (unc_arr > 1.22 * med_unc)

            local_block = np.ones((H, W), dtype=np.int32)
            local_block[inside] = block_k
            bump = np.zeros((H, W), dtype=np.int32)
            bump[edge_mask] += 1
            bump[low_obs_mask] += 1
            bump[very_low_obs_mask] += 1
            bump[high_disp_mask] += 1
            if not np.any(interior_4) and np.any(edge_mask):
                bump[edge_mask] -= 1
            local_block[inside] = np.clip(block_k + bump[inside], block_k, 6)

            local_res_arr = np.full((H, W), np.nan, dtype=np.float32)
            local_res_arr[inside] = np.maximum(
                eff_res_m,
                np.round(grid_res_m * local_block[inside], 1),
            ).astype(np.float32)

            # Locally coarsen pixels matching each cell's effective support radius
            if np.any(local_block[inside] > 1):
                arr_coarse = np.full((H, W), np.nan, dtype=np.float32)
                unc_coarse = np.full((H, W), np.nan, dtype=np.float32)
                for r in range(H):
                    for c in range(W):
                        if not inside[r, c] or not math.isfinite(float(arr[r, c])):
                            continue
                        k_loc = int(local_block[r, c])
                        if k_loc <= 1:
                            arr_coarse[r, c] = arr[r, c]
                            unc_coarse[r, c] = unc_arr[r, c]
                            continue
                        half_lo = k_loc // 2
                        half_hi = k_loc - half_lo
                        r0, r1 = max(0, r - half_lo), min(H, r + half_hi)
                        c0, c1 = max(0, c - half_lo), min(W, c + half_hi)
                        m_blk = inside[r0:r1, c0:c1] & np.isfinite(arr[r0:r1, c0:c1])
                        if not np.any(m_blk):
                            arr_coarse[r, c] = arr[r, c]
                            unc_coarse[r, c] = unc_arr[r, c]
                            continue
                        blk_vals = arr[r0:r1, c0:c1][m_blk]
                        blk_mean = float(np.mean(blk_vals))
                        blk_rep_var = float(np.var(blk_vals)) if blk_vals.size > 1 else 0.0
                        blk_base_var = float(np.mean(np.square(unc_arr[r0:r1, c0:c1][m_blk])))
                        arr_coarse[r, c] = blk_mean
                        unc_coarse[r, c] = math.sqrt(max(1e-8, blk_base_var + 0.5 * blk_rep_var))
                arr = arr_coarse
                unc_arr = unc_coarse

            inside_res_vals = local_res_arr[inside]
            min_loc_m = round(float(np.min(inside_res_vals)), 1) if inside_res_vals.size > 0 else eff_res_m
            med_loc_m = round(float(np.median(inside_res_vals)), 1) if inside_res_vals.size > 0 else eff_res_m
            max_loc_m = round(float(np.max(inside_res_vals)), 1) if inside_res_vals.size > 0 else eff_res_m
            res_summary = {
                "base_m": eff_res_m,
                "min_m": min_loc_m,
                "median_m": med_loc_m,
                "max_m": max_loc_m,
                "is_spatially_varying": bool(max_loc_m > min_loc_m + 1e-6),
                "edge_degraded_pixels": int(np.sum(edge_mask)) if np.any(interior_4) else 0,
                "low_support_pixels": int(np.sum(low_obs_mask)),
                "high_dispersion_pixels": int(np.sum(high_disp_mask)),
            }

            values_list = [
                [round(float(arr[r, c]), 5) if bool(inside[r, c]) and math.isfinite(float(arr[r, c])) else None for c in range(W)]
                for r in range(H)
            ]
            unc_list = [
                [round(float(unc_arr[r, c]), 5) if bool(inside[r, c]) and math.isfinite(float(unc_arr[r, c])) else None for c in range(W)]
                for r in range(H)
            ]
            local_res_list = [
                [round(float(local_res_arr[r, c]), 1) if bool(inside[r, c]) and math.isfinite(float(local_res_arr[r, c])) else None for c in range(W)]
                for r in range(H)
            ]
            stype = surface_type_map[s_name]
            is_sar_driven = s_name in ("root_zone_water", "surface_wetness_event", "structure")
            surfaces.append({
                "surface_id": f"hist_{stype.lower()}",
                "type": stype,
                "surface_type": stype,
                "semantic_type": stype,
                "diagnostic_only": True,
                "prescription_driver_allowed": False,
                "state_update_allowed": False,
                "spatial_estimation_mode": "inferred_state_anomaly_field",
                "direct_pixel_measurement": False,
                "resolution_m": grid_res_m,
                "effective_resolution_m": eff_res_m,
                "local_resolution_map_m": local_res_list,
                "resolution_summary": res_summary,
                "spatial_support_tier": res_info["spatial_support"],
                "aggregation_factor": block_k,
                "limiting_factor": res_info["limiting_factor"],
                "certified_1m": False,
                "bounds": bounds,
                "values": values_list,
                "uncertainty": unc_list,
                "observed_ratio": round(float(np.mean(inside)), 4),
                "provenance": {
                    "has_spatial_grid": True,
                    "reprojected_to_canonical_grid": True,
                    "spatial_estimation_mode": "inferred_state_anomaly_field",
                    "direct_pixel_measurement": False,
                    "effective_resolution_m": eff_res_m,
                    "resolution_summary": res_summary,
                    "spatial_support_tier": res_info["spatial_support"],
                    "limiting_factor": res_info["limiting_factor"],
                    "certified_1m": False,
                    "grounding_note": (
                        f"Inferred {int(min_loc_m)}-{int(max_loc_m)}m adaptive field combining Sentinel-1 SAR anomalies with L3 water balance & EnKF posterior mean ({res_info['limiting_factor']})."
                        if is_sar_driven and res_summary["is_spatially_varying"]
                        else (
                            f"Inferred {int(eff_res_m)}m field combining Sentinel-1 SAR anomalies with L3 water balance & EnKF posterior mean ({res_info['limiting_factor']})."
                            if is_sar_driven
                            else (
                                f"Inferred {int(min_loc_m)}-{int(max_loc_m)}m adaptive field combining Sentinel-2 spectral anomalies with EnKF posterior mean ({res_info['limiting_factor']})."
                                if res_summary["is_spatially_varying"]
                                else f"Inferred {int(eff_res_m)}m field combining Sentinel-2 spectral anomalies with EnKF posterior mean ({res_info['limiting_factor']})."
                            )
                        )
                    ),
                    "crs": canonical_grid.get("crs", "EPSG:4326"),
                    "transform": canonical_grid.get("transform"),
                },
            })
        return surfaces

    def reconstruct(
        self,
        *,
        plot_id: str,
        geometry_hash: str,
        tenant_id: str = "default_tenant",
        namespace: str = "default",
        valid_time_T: Optional[Any] = None,
        knowledge_cutoff_K: Optional[Any] = None,
        daily_weather: Optional[Dict[str, Dict[str, Any]]] = None,
        crop_context: Optional[Dict[str, Any]] = None,
        soil_context: Optional[Dict[str, Any]] = None,
        management_events: Optional[List[Any]] = None,
        polygon_geojson: Optional[Dict[str, Any]] = None,
        emit_worldline_posterior: bool = True,
        use_cross_layer_priors: bool = True,
        retrovalidation_fn: Optional[Callable[[List[Dict[str, Any]], Dict[str, Any]], Dict[str, Any]]] = None,
        event_memory_fn: Optional[Callable[[List[Dict[str, Any]], Dict[str, Any]], Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Reconstruct 13-state posterior history incrementally or via non-destructive late-arrival replay."""
        now_utc = datetime.now(timezone.utc).isoformat()
        cutoff_T = str(valid_time_T or now_utc)
        cutoff_K = str(knowledge_cutoff_K or now_utc)
        weather_series = dict(daily_weather or {})
        crop_ctx = dict(crop_context or {})
        soil_ctx = dict(soil_context or {})
        mgmt_events = list(management_events or [])

        eligible_events = self.load_qualified_observations(
            plot_id=plot_id,
            valid_time_T=cutoff_T,
            knowledge_cutoff_K=cutoff_K,
            tenant_id=tenant_id,
            namespace=namespace,
        )
        if not eligible_events:
            return {
                "status": "no_qualified_observations",
                "plot_id": plot_id,
                "geometry_hash": geometry_hash,
                "observation_count": 0,
                "checkpoints": [],
                "trajectory": [],
            }

        ordered_obs_ids = [str(ev["event_id"]) for ev in eligible_events]
        index_data = self.load_checkpoint_index(plot_id, tenant_id, namespace)
        active_cp_ids: List[str] = list(index_data.get("active_chain") or [])
        prior_worldline_posterior_id = index_data.get("latest_worldline_posterior_event_id")

        loaded_chain: List[PosteriorCheckpoint] = []
        for cp_id in active_cp_ids:
            cp = self.load_checkpoint(plot_id, cp_id, tenant_id, namespace)
            if (
                cp is not None
                and cp.geometry_hash == geometry_hash
                and cp.model_version == RECONSTRUCTOR_MODEL_VERSION
                and cp.state_schema_version == STATE_SCHEMA_VERSION
                and cp.calibration_version == CALIBRATION_VERSION
            ):
                loaded_chain.append(cp)

        # Determine whether to resume cleanly from tail checkpoint, anchor before late arrivals, or run cold
        mode = "cold_full_reconstruction"
        anchor_cp: Optional[PosteriorCheckpoint] = None
        preserved_prefix_cps: List[PosteriorCheckpoint] = []
        late_arrival_ids: List[str] = []
        superseded_cp_ids: List[str] = []

        if loaded_chain:
            tail_cp = loaded_chain[-1]
            tail_ids = list(tail_cp.assimilated_observation_ids)
            if len(tail_ids) <= len(ordered_obs_ids) and ordered_obs_ids[: len(tail_ids)] == tail_ids:
                if len(tail_ids) == len(ordered_obs_ids):
                    # Everything already assimilated; still ensure steps available from replay/live needs
                    mode = "up_to_date"
                    anchor_cp = tail_cp
                    preserved_prefix_cps = list(loaded_chain)
                else:
                    mode = "incremental_continuation"
                    anchor_cp = tail_cp
                    preserved_prefix_cps = list(loaded_chain)
            else:
                # Late arrival (or earlier historical insertion) detected before tail_cp cutoff
                first_div_idx = 0
                for idx in range(min(len(tail_ids), len(ordered_obs_ids))):
                    if tail_ids[idx] != ordered_obs_ids[idx]:
                        break
                    first_div_idx = idx + 1
                known_tail_set = set(tail_ids)
                tail_cutoff_dt = _parse_utc_iso(tail_cp.cutoff_valid_time)
                late_arrival_ids = [
                    str(ev["event_id"])
                    for ev in eligible_events
                    if str(ev["event_id"]) not in known_tail_set
                    and _parse_utc_iso(ev.get("observation_or_valid_time") or ev.get("effective_at"))
                    <= tail_cutoff_dt
                ]
                mode = "late_arrival_replay"
                # Pick latest unaffected checkpoint whose assimilated prefix strictly precedes divergence
                for cp in loaded_chain:
                    cp_len = len(cp.assimilated_observation_ids)
                    if cp_len <= first_div_idx and ordered_obs_ids[:cp_len] == list(cp.assimilated_observation_ids):
                        anchor_cp = cp
                        preserved_prefix_cps.append(cp)
                    else:
                        superseded_cp_ids.append(cp.checkpoint_id)

        canonical_grid = build_canonical_parcel_grid(polygon_geojson) if polygon_geojson else None
        k_dt_obj = _parse_utc_iso(cutoff_K)
        first_obs_dt = _parse_utc_iso(eligible_events[0].get("observation_or_valid_time") or eligible_events[0].get("effective_at"))
        rng = make_rng("asmae_hist_recon", plot_id, geometry_hash, STATE_SCHEMA_VERSION)
        if anchor_cp is not None:
            start_idx = len(anchor_cp.assimilated_observation_ids)
            ensemble: Dict[str, List[List[float]]] = copy.deepcopy(anchor_cp.ensemble_members)
            rng.setstate(_rng_state_from_json(anchor_cp.rng_state_json))
            prev_scene_time: Optional[datetime] = _parse_utc_iso(anchor_cp.last_obs_time)
            accepted_counts: Dict[str, int] = dict(anchor_cp.accepted_update_counts)
            parent_cp_id: Optional[str] = anchor_cp.checkpoint_id
            assimilated_ids: List[str] = list(anchor_cp.assimilated_observation_ids)
            channel_cal: Dict[str, Dict[str, Any]] = copy.deepcopy(anchor_cp.channel_calibration or {})
            has_spatial_obs = bool(anchor_cp.has_spatial_observations)
            chrono_state = CrossLayerChronoState.from_dict(anchor_cp.specialist_chrono_state)
            if not chrono_state.layer_theta_profile:
                chrono_state = self.cross_layer_bridge.initialize_chrono_state(
                    crop_context=crop_ctx, soil_context=soil_ctx
                )
            if canonical_grid is None and isinstance(anchor_cp.canonical_grid, dict):
                canonical_grid = dict(anchor_cp.canonical_grid)
                canonical_grid["inside_mask"] = _polygon_mask(
                    polygon_geojson,
                    canonical_grid.get("transform"),
                    int(canonical_grid["height"]),
                    int(canonical_grid["width"]),
                )
        else:
            start_idx = 0
            chrono_state = self.cross_layer_bridge.initialize_chrono_state(
                crop_context=crop_ctx, soil_context=soil_ctx
            )
            init_priors: Dict[str, Any] = {}
            if use_cross_layer_priors:
                self.cross_layer_bridge.advance_chrono_state(
                    chrono_state,
                    start_time=first_obs_dt - timedelta(days=5),
                    end_time=first_obs_dt,
                    weather_daily_series=weather_series,
                    crop_context=crop_ctx,
                    soil_context=soil_ctx,
                    management_events=mgmt_events,
                )
                init_bundle = self.cross_layer_bridge.evaluate_step_priors(
                    state=chrono_state,
                    timestamp=first_obs_dt,
                    knowledge_cutoff=k_dt_obj,
                    crop_context=crop_ctx,
                    soil_context=soil_ctx,
                )
                init_priors = init_bundle.get("priors") or {}
            ensemble, _ = initialize_ensemble(
                node_ids=self.node_ids,
                n_ensemble=self.n_ensemble,
                priors=init_priors,
                crop_context=crop_ctx,
                rng=rng,
                scenes=[],
                initial_posterior=None,
            )
            prev_scene_time = None
            accepted_counts = {name: 0 for name in STATE_NAMES}
            parent_cp_id = None
            assimilated_ids = []
            channel_cal = {}
            has_spatial_obs = False

        # Allocate or restore spatial state anomaly arrays on canonical parcel grid
        spatial_delta: Optional[np.ndarray] = None
        spatial_var: Optional[np.ndarray] = None
        spatial_obs_count: Optional[np.ndarray] = None
        if canonical_grid is not None:
            H_c = int(canonical_grid["height"])
            W_c = int(canonical_grid["width"])
            if anchor_cp is not None and anchor_cp.spatial_artifact:
                loaded_sp = self._load_spatial_arrays(anchor_cp)
                if (
                    loaded_sp is not None
                    and loaded_sp.get("spatial_delta", np.empty(0)).shape == (len(_SPATIALLY_SUPPORTED_STATES), H_c, W_c)
                ):
                    spatial_delta = loaded_sp["spatial_delta"].astype(np.float32).copy()
                    spatial_var = loaded_sp["spatial_var"].astype(np.float32).copy()
                    spatial_obs_count = loaded_sp["spatial_obs_count"].astype(np.int32).copy()
                    if "inside_mask" in loaded_sp and loaded_sp["inside_mask"].shape == (H_c, W_c):
                        canonical_grid["inside_mask"] = loaded_sp["inside_mask"].astype(bool)
            if spatial_delta is None:
                spatial_delta = np.zeros((len(_SPATIALLY_SUPPORTED_STATES), H_c, W_c), dtype=np.float32)
                spatial_var = np.full((len(_SPATIALLY_SUPPORTED_STATES), H_c, W_c), 0.015, dtype=np.float32)
                spatial_obs_count = np.zeros((H_c, W_c), dtype=np.int32)

        step_records: List[Dict[str, Any]] = []
        prefix_trajectory: List[Dict[str, Any]] = []
        for cp in preserved_prefix_cps:
            if cp.trajectory_segment:
                prefix_trajectory.extend(cp.trajectory_segment)
        segment_buffer: List[Dict[str, Any]] = []
        new_checkpoints: List[PosteriorCheckpoint] = []
        gap_events: List[Dict[str, Any]] = []
        total_missing_weather_days = 0
        total_elapsed_days = 0

        pending_events = eligible_events[start_idx:]
        prev_ndvi_sign_active: Optional[bool] = None

        for local_i, ev in enumerate(pending_events):
            global_i = start_idx + local_i
            payload = (ev.get("payload") or {}).get("observation_qualified") or {}
            obs_time = _parse_utc_iso(ev.get("observation_or_valid_time") or ev.get("effective_at"))
            ev_id = str(ev["event_id"])

            # Count exact weather & observation gaps strictly between prev_scene_time and obs_time
            elapsed_days = 0.0
            missing_w_in_step = 0
            if prev_scene_time is not None and obs_time > prev_scene_time:
                elapsed_days = (obs_time - prev_scene_time).total_seconds() / 86400.0
                total_elapsed_days += int(round(elapsed_days))
                day_cur = prev_scene_time.date()
                while day_cur < obs_time.date():
                    if day_cur.isoformat() not in weather_series:
                        missing_w_in_step += 1
                    day_cur += timedelta(days=1)
                total_missing_weather_days += missing_w_in_step
                if elapsed_days >= 18.0:
                    gap_events.append({
                        "gap_start": prev_scene_time.isoformat(),
                        "gap_end": obs_time.isoformat(),
                        "gap_days": round(elapsed_days, 2),
                        "missing_weather_days": missing_w_in_step,
                    })

            # Advance specialist L2-L7 models strictly causally up to obs_time BEFORE ASMAE forecast/update
            step_weather = filter_causal_daily_weather_at_cutoff(weather_series, obs_time)
            step_pre_bundle: Optional[Dict[str, Any]] = None
            step_priors: Dict[str, Any] = {}
            if use_cross_layer_priors:
                self.cross_layer_bridge.advance_chrono_state(
                    chrono_state,
                    start_time=prev_scene_time or (obs_time - timedelta(days=5)),
                    end_time=obs_time,
                    weather_daily_series=step_weather,
                    crop_context=crop_ctx,
                    soil_context=soil_ctx,
                    management_events=mgmt_events,
                )
                step_pre_bundle = self.cross_layer_bridge.evaluate_step_priors(
                    state=chrono_state,
                    timestamp=obs_time,
                    knowledge_cutoff=k_dt_obj,
                    crop_context=crop_ctx,
                    soil_context=soil_ctx,
                )
                step_priors = step_pre_bundle.get("priors") or {}

            # Propagate 13-state ensemble forward over daily intervals
            if prev_scene_time is not None and obs_time > prev_scene_time:
                ensemble, _ = _forecast_elapsed_interval(
                    ensemble=ensemble,
                    previous_time=prev_scene_time,
                    current_time=obs_time,
                    priors=step_priors,
                    crop_context=crop_ctx,
                    rng=rng,
                    scenes=[],
                    weather_daily_series=step_weather,
                    soil_context=soil_ctx,
                    management_events=mgmt_events,
                )
            prev_scene_time = obs_time

            obs_channels, obs_grids = _load_scene_raster_observations(
                payload,
                self.scene_store,
                plot_id,
                polygon_geojson,
                canonical_grid=canonical_grid,
                return_grids=True,
            )
            prior_means, prior_stds, _, _, _ = _summarize_13_state_ensemble(ensemble, self.node_ids)
            prior_predictions = self._predict_pre_update_channels(
                ensemble,
                self.node_ids,
                obs_channels,
                payload,
                channel_cal=channel_cal,
                elapsed_days=elapsed_days,
                obs_dt=obs_time,
            )

            # Update assimilated channels in model-operator frame (obs - causal_prior_bias)
            # so biased NDMI/SAR-VV offsets do not trigger cross-sensor oscillation
            cloud_frac = float(payload.get("cloud_score", 0.0) or 0.0)
            valid_frac = float(payload.get("valid_pixel_fraction", 1.0) or 1.0)
            updated_channels: List[str] = []
            pending_cal_updates: List[Tuple[str, float, Dict[str, Any], float]] = []
            for obs_name, obs_val in sorted(obs_channels.items()):
                mapping = INDEX_STATE_REGISTRY.get(obs_name)
                if mapping is None:
                    continue
                target_indices = [
                    s for s in mapping.target_state_indices
                    if 0 <= s < N_STATES
                    and not validate_forbidden_state_update(obs_name, s)
                    and STATE_DESCRIPTORS[s].assimilation_policy != AssimilationPolicy.NOT_ASSIMILATED
                ]
                if not target_indices:
                    continue
                sigma_obs = compute_observation_noise(
                    obs_name,
                    cloud_fraction=cloud_frac,
                    valid_support_fraction=max(0.05, valid_frac),
                )
                pred_rec = prior_predictions.get(obs_name) or {}
                bias_prior = float(pred_rec.get("bias_offset_applied", 0.0) or 0.0)
                slope_prior = max(0.20, float(pred_rec.get("slope_applied", 1.0) or 1.0))
                lo_b, hi_b = _CHANNEL_BOUNDS.get(obs_name, (-1.0, 1.0))
                obs_for_filter = float(np.clip((float(obs_val) - bias_prior) / slope_prior, lo_b, hi_b))
                r_var = (sigma_obs * sigma_obs) / max(0.30, slope_prior * slope_prior)
                _proxy_update_single_obs(
                    ensemble, self.node_ids, obs_name, obs_for_filter,
                    mapping, sigma_obs, r_var, rng, target_indices=target_indices,
                )
                for s_idx in target_indices:
                    s_name = STATE_NAMES[s_idx]
                    accepted_counts[s_name] = accepted_counts.get(s_name, 0) + 1
                updated_channels.append(obs_name)
                if pred_rec:
                    pending_cal_updates.append((obs_name, float(obs_val), pred_rec, float(sigma_obs)))

            ensemble = clamp_ensemble(ensemble)
            assimilated_ids.append(ev_id)

            post_means, post_stds, post_cov, _, _ = _summarize_13_state_ensemble(ensemble, self.node_ids)
            post_vec = [float(post_means.get(n, 0.25)) for n in STATE_NAMES]
            for obs_name, obs_val_f, pred_rec, sigma_obs_f in pending_cal_updates:
                mp_c = INDEX_STATE_REGISTRY.get(obs_name)
                post_raw = (
                    predict_sar_observation(obs_name, post_vec)
                    if (mp_c is not None and mp_c.sensor == "S1")
                    else predict_observation(obs_name, post_vec)
                )
                raw_pred = float(pred_rec.get("y_pred_raw", obs_val_f))
                cal_pred = float(pred_rec.get("y_pred_calibrated", obs_val_f))
                unscaled_sig = max(1e-4, float(pred_rec.get("unscaled_pred_sigma", pred_rec.get("raw_pred_sigma", sigma_obs_f))))
                channel_cal[obs_name] = update_channel_cal_entry(
                    channel_cal.get(obs_name),
                    obs_val=obs_val_f,
                    raw_pred=raw_pred,
                    cal_pred=cal_pred,
                    unscaled_sig=unscaled_sig,
                    obs_name=obs_name,
                    obs_dt=obs_time,
                    post_raw_pred=float(post_raw) if (post_raw is not None and math.isfinite(float(post_raw))) else raw_pred,
                    var_scale_used=pred_rec.get("var_scale_applied"),
                )
            support_step_ledger = _build_historical_support_ledger(
                accepted_counts,
                has_spatial_rasters=has_spatial_obs,
                canonical_grid=canonical_grid,
            )

            # Update causal NDVI & NDMI buffers for next step AFTER scoring current step
            if use_cross_layer_priors:
                if isinstance(obs_channels.get("ndvi"), (int, float)):
                    exp_v = float((step_priors.get("layer2") or {}).get("expected_vigor", 0.55) or 0.55)
                    chrono_state.recent_ndvi_window.append((obs_time.isoformat()[:10], float(obs_channels["ndvi"]), exp_v))
                    if len(chrono_state.recent_ndvi_window) > 10:
                        chrono_state.recent_ndvi_window = chrono_state.recent_ndvi_window[-10:]
                if isinstance(obs_channels.get("ndmi"), (int, float)):
                    chrono_state.recent_ndmi_window.append(float(obs_channels["ndmi"]))
                    if len(chrono_state.recent_ndmi_window) > 8:
                        chrono_state.recent_ndmi_window = chrono_state.recent_ndmi_window[-8:]

            refined_step_bundle: Optional[Dict[str, Any]] = None
            if use_cross_layer_priors and step_pre_bundle is not None:
                refined_step_bundle = self.cross_layer_bridge.refine_after_asmae(
                    pre_bundle=step_pre_bundle,
                    posterior_means=post_means,
                    posterior_stds=post_stds,
                    state_support_ledger=support_step_ledger,
                    crop_context=crop_ctx,
                    obs_channels=obs_channels,
                    gap_days=elapsed_days,
                )

            if canonical_grid is not None and spatial_delta is not None and spatial_var is not None and spatial_obs_count is not None:
                has_spatial_obs = self._update_spatial_anomaly_field(
                    spatial_delta=spatial_delta,
                    spatial_var=spatial_var,
                    spatial_obs_count=spatial_obs_count,
                    inside_mask=canonical_grid["inside_mask"],
                    obs_grids=obs_grids,
                    elapsed_days=elapsed_days,
                    post_stds=post_stds,
                    has_spatial_observations=has_spatial_obs,
                )

            metrics = dict(payload.get("metrics") or {})

            step_entry = {
                "step_index": global_i,
                "event_id": ev_id,
                "scene_id": str(payload.get("scene_id") or ""),
                "source": str(payload.get("source") or ""),
                "acquisition_time": obs_time.isoformat(),
                "committed_at": str(ev.get("committed_at") or ""),
                "elapsed_days": round(elapsed_days, 3),
                "missing_weather_days": missing_w_in_step,
                "obs_channels": obs_channels,
                "raw_metrics": metrics,
                "updated_channels": updated_channels,
                "prior_predictions": prior_predictions,
                "prior_state_means": prior_means,
                "prior_state_stds": prior_stds,
                "posterior_state_means": post_means,
                "posterior_state_stds": post_stds,
                "channel_calibration_snapshot": copy.deepcopy(channel_cal),
                "has_spatial_rasters": bool(obs_grids),
                "cross_layer_priors": step_pre_bundle.get("priors") if step_pre_bundle else {},
                "cross_layer_refined": refined_step_bundle or {},
            }
            step_records.append(step_entry)
            segment_buffer.append(step_entry)

            # Determine boundary checkpoint conditions (year rollover, active/fallow transition, stride, or final)
            ndvi_val = obs_channels.get("ndvi")
            is_last = local_i == (len(pending_events) - 1)
            next_year_rollover = False
            if not is_last:
                next_dt = _parse_utc_iso(pending_events[local_i + 1].get("observation_or_valid_time"))
                next_year_rollover = next_dt.year != obs_time.year
            season_flip = False
            if ndvi_val is not None:
                is_act = ndvi_val >= 0.28
                if prev_ndvi_sign_active is not None and is_act != prev_ndvi_sign_active:
                    season_flip = True
                prev_ndvi_sign_active = is_act

            boundary_reason: Optional[str] = None
            if is_last:
                boundary_reason = "late_arrival_recompute" if late_arrival_ids else "horizon_end"
            elif next_year_rollover:
                boundary_reason = "annual_seasonal_boundary"
            elif season_flip and (len(assimilated_ids) % max(2, min(5, self.checkpoint_stride)) == 0):
                boundary_reason = "phenology_regime_boundary"
            elif (local_i + 1) % self.checkpoint_stride == 0:
                boundary_reason = "observation_stride_boundary"

            if boundary_reason is not None:
                cp_id = self._checkpoint_identity(
                    plot_id=plot_id,
                    geometry_hash=geometry_hash,
                    cutoff_valid_time=obs_time.isoformat(),
                    assimilated_observation_ids=assimilated_ids,
                    parent_checkpoint_id=parent_cp_id,
                )
                grid_meta = (
                    {k: v for k, v in canonical_grid.items() if k != "inside_mask"}
                    if canonical_grid is not None else None
                )
                cp_obj = PosteriorCheckpoint(
                    checkpoint_id=cp_id,
                    schema_version=POSTERIOR_CHECKPOINT_SCHEMA,
                    plot_id=plot_id,
                    tenant_id=tenant_id,
                    namespace=namespace,
                    geometry_hash=geometry_hash,
                    model_version=RECONSTRUCTOR_MODEL_VERSION,
                    state_schema_version=STATE_SCHEMA_VERSION,
                    calibration_version=CALIBRATION_VERSION,
                    cutoff_valid_time=obs_time.isoformat(),
                    knowledge_cutoff_time=cutoff_K,
                    boundary_reason=boundary_reason,
                    last_obs_event_id=ev_id,
                    last_obs_time=obs_time.isoformat(),
                    assimilated_observation_ids=list(assimilated_ids),
                    ensemble_members=copy.deepcopy(ensemble),
                    rng_state_json=_rng_state_to_json(rng.getstate()),
                    state_means=post_means,
                    state_stds=post_stds,
                    state_covariance=post_cov,
                    per_node_means={},
                    per_node_stds={},
                    accepted_update_counts=dict(accepted_counts),
                    state_support_ledger=_build_historical_support_ledger(
                        accepted_counts,
                        has_spatial_rasters=has_spatial_obs,
                        canonical_grid=canonical_grid,
                    ),
                    parent_checkpoint_id=parent_cp_id,
                    supersedes_checkpoint_id=superseded_cp_ids[-1] if (is_last and superseded_cp_ids) else None,
                    late_arrival_event_ids=list(late_arrival_ids) if is_last else [],
                    trajectory_segment=list(segment_buffer),
                    created_at=now_utc,
                    channel_calibration=copy.deepcopy(channel_cal),
                    canonical_grid=grid_meta,
                    has_spatial_observations=has_spatial_obs,
                    specialist_chrono_state=chrono_state.to_dict(),
                )
                sp_arrays = (
                    {
                        "spatial_delta": spatial_delta,
                        "spatial_var": spatial_var,
                        "spatial_obs_count": spatial_obs_count,
                        "inside_mask": canonical_grid["inside_mask"].astype(np.uint8),
                    }
                    if (has_spatial_obs and canonical_grid is not None and spatial_delta is not None and spatial_var is not None and spatial_obs_count is not None)
                    else None
                )
                self._save_checkpoint(cp_obj, spatial_arrays=sp_arrays)
                new_checkpoints.append(cp_obj)
                segment_buffer.clear()
                parent_cp_id = cp_id

        full_trajectory = prefix_trajectory + step_records
        if len(full_trajectory) < len(ordered_obs_ids) and not prefix_trajectory:
            full_trajectory = step_records

        final_chain = preserved_prefix_cps + new_checkpoints
        if not final_chain and anchor_cp is not None:
            final_chain = preserved_prefix_cps

        tail_checkpoint = final_chain[-1]
        final_means = tail_checkpoint.state_means
        final_stds = tail_checkpoint.state_stds
        final_cov = tail_checkpoint.state_covariance
        support_ledger = tail_checkpoint.state_support_ledger

        gap_summary = {
            "total_elapsed_days": total_elapsed_days,
            "missing_weather_days": total_missing_weather_days,
            "long_observation_gaps_count": len(gap_events),
            "long_observation_gaps": gap_events[:50],
        }

        context_summary = {
            "plot_id": plot_id,
            "geometry_hash": geometry_hash,
            "daily_weather": weather_series,
            "crop_context": crop_ctx,
            "soil_context": soil_ctx,
            "management_events": mgmt_events,
            "state_support_ledger": support_ledger,
            "tail_checkpoint": tail_checkpoint.summary_dict(),
            "checkpoints_chain": final_chain,
            "node_ids": list(self.node_ids),
            "canonical_grid": canonical_grid,
        }

        event_memory_result: Dict[str, Any] = {}
        if event_memory_fn is not None:
            event_memory_result = event_memory_fn(full_trajectory, context_summary)

        retro_result: Dict[str, Any] = {}
        if retrovalidation_fn is not None:
            retro_result = retrovalidation_fn(full_trajectory, context_summary)

        qual_info = retro_result.get("qualification") if isinstance(retro_result, dict) else None
        qual_passed = bool(retrovalidation_fn is not None and isinstance(qual_info, dict) and qual_info.get("passed") is True)
        if retrovalidation_fn is None:
            block_reasons = ["retrovalidation_not_executed"]
            qual_status = "diagnostic_unvalidated"
        elif qual_passed:
            block_reasons = []
            qual_status = "validated_qualified"
        else:
            block_reasons = list(
                (qual_info.get("block_reasons") if isinstance(qual_info, dict) else None)
                or ["retrovalidation_qualification_failed"]
            )
            qual_status = "diagnostic_failed_qualification"

        emitted_event_type = "ARCHIVE_POSTERIOR_VALIDATED" if qual_passed else "ARCHIVE_POSTERIOR_DIAGNOSTIC"

        # Update checkpoint index append-only (retain historical chains before late arrival!)
        historical_chains = list(index_data.get("historical_chains") or [])
        if mode == "late_arrival_replay" and active_cp_ids:
            historical_chains.append({
                "superseded_at": now_utc,
                "late_arrival_event_ids": list(late_arrival_ids),
                "prior_active_chain": list(active_cp_ids),
                "prior_worldline_posterior_event_id": prior_worldline_posterior_id,
            })

        # Authority gate: emit ARCHIVE_POSTERIOR_VALIDATED ONLY when retrovalidation ran & passed criteria;
        # otherwise emit ARCHIVE_POSTERIOR_DIAGNOSTIC explicitly flagged as unvalidated/failed-qualification.
        emitted_event_id: Optional[str] = prior_worldline_posterior_id
        if emit_worldline_posterior and (new_checkpoints or mode == "cold_full_reconstruction"):
            evidence_digest = hashlib.sha256(
                json.dumps(ordered_obs_ids, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            parents: List[str] = [ordered_obs_ids[-1]]
            if prior_worldline_posterior_id and prior_worldline_posterior_id not in parents:
                parents.append(prior_worldline_posterior_id)

            archive_posterior_payload = {
                "schema_version": "archive_posterior_validated_v2" if qual_passed else "archive_posterior_diagnostic_v2",
                "geometry_hash": geometry_hash,
                "model_version": RECONSTRUCTOR_MODEL_VERSION,
                "state_schema_version": STATE_SCHEMA_VERSION,
                "calibration_version": CALIBRATION_VERSION,
                "publication_authority": "DIAGNOSTIC_ONLY",
                "claims_numerical_authority": False,
                "qualification_passed": qual_passed,
                "qualification_status": qual_status,
                "validation_block_reasons": block_reasons,
                "effective_resolution": "adaptive_state_dependent_min_10m",
                "effective_resolution_by_state": {
                    k: v.get("effective_resolution_m")
                    for k, v in support_ledger.items()
                    if v.get("effective_resolution_m") is not None
                },
                "calibration_status": "causally_calibrated_diagnostic" if channel_cal else "uncalibrated_diagnostic",
                "has_spatial_observations": bool(tail_checkpoint.has_spatial_observations),
                "canonical_grid": tail_checkpoint.canonical_grid,
                "observation_count": len(ordered_obs_ids),
                "assimilated_observation_ids_hash": evidence_digest,
                "cutoff_valid_time": tail_checkpoint.cutoff_valid_time,
                "state_means": final_means,
                "state_stds": final_stds,
                "state_covariance": final_cov,
                "state_support_ledger": support_ledger,
                "supported_layers": [
                    k for k, v in support_ledger.items() if v.get("support_status") == "temporally_conditioned"
                ],
                "unsupported_layers": [
                    {"layer": f"ASMAE_{k.upper()}", "reason": (v.get("block_reasons") or ["unsupported"])[0]}
                    for k, v in support_ledger.items()
                    if v.get("support_status") != "temporally_conditioned"
                ],
                "checkpoint_id": tail_checkpoint.checkpoint_id,
                "checkpoint_chain_length": len(final_chain),
                "reconstruction_mode": mode,
                "late_arrival_event_ids": list(late_arrival_ids),
                "supersedes_event_id": prior_worldline_posterior_id if late_arrival_ids else None,
                "prior_publication_preserved": True,
                "gap_summary": gap_summary,
                "event_memory_summary": event_memory_result.get("summary", {}),
                "retrovalidation_summary": retro_result.get("summary", {}),
                "bma_weights": retro_result.get("bma", {}).get("weights", {}),
                "bma_status": retro_result.get("bma", {}).get("archive_bma_status", "diagnostic"),
            }
            wl_payload = {
                "archive_posterior": archive_posterior_payload,
                "historical_metrics": retro_result.get("summary", {}),
                "baseline": retro_result.get("baselines", {}),
                "archive_bma": retro_result.get("bma", {}),
                "retrovalidation": retro_result.get("seasonal_scorecard", {}),
                "multi_horizon": retro_result.get("multi_horizon", {}),
                "qualification": qual_info or {"passed": False, "block_reasons": block_reasons},
                "archive_metrics_hash": hashlib.sha256(
                    json.dumps(archive_posterior_payload, sort_keys=True, default=str).encode("utf-8")
                ).hexdigest(),
            }
            proposal = WorldlineEventProposal(
                event_type=emitted_event_type,
                geometry_version=geometry_hash[:16],
                evidence_set_hash=evidence_digest,
                payload=wl_payload,
                model_version=RECONSTRUCTOR_MODEL_VERSION,
                calibration_version=CALIBRATION_VERSION,
                authority_contract_version="auth_asmae_hist_v2",
                authority_ref="asmae:historical_state_intelligence",
                state_schema_version=STATE_SCHEMA_VERSION,
                observation_or_valid_time=tail_checkpoint.cutoff_valid_time,
                parent_event_ids=parents,
            )
            committed = self.worldline.commit_proposal(
                plot_id=plot_id,
                proposal=proposal,
                namespace=namespace,
                tenant_id=tenant_id,
                effective_at=tail_checkpoint.cutoff_valid_time,
            )
            emitted_event_id = committed.get("event_id")

        self._save_checkpoint_index(
            plot_id,
            tenant_id,
            namespace,
            {
                "active_chain": [cp.checkpoint_id for cp in final_chain],
                "historical_chains": historical_chains,
                "latest_worldline_posterior_event_id": emitted_event_id,
                "latest_worldline_posterior_event_type": emitted_event_type,
                "updated_at": now_utc,
            },
        )

        # Build canonical spatial maps for tail state if real rasters were assimilated
        tail_surfaces: List[Dict[str, Any]] = []
        if canonical_grid is not None and has_spatial_obs and spatial_delta is not None:
            tail_surfaces = self.build_spatial_surfaces_payload(
                canonical_grid=canonical_grid,
                state_means=final_means,
                state_stds=final_stds,
                accepted_counts=tail_checkpoint.accepted_update_counts,
                spatial_delta=spatial_delta,
                spatial_var=spatial_var,
                has_spatial_observations=has_spatial_obs,
                spatial_obs_count=spatial_obs_count,
            )

        tail_cross_layer = (full_trajectory[-1].get("cross_layer_refined") or {}) if full_trajectory else {}
        return {
            "status": "COMPLETED",
            "mode": mode,
            "plot_id": plot_id,
            "geometry_hash": geometry_hash,
            "model_version": RECONSTRUCTOR_MODEL_VERSION,
            "state_schema_version": STATE_SCHEMA_VERSION,
            "calibration_version": CALIBRATION_VERSION,
            "use_cross_layer_priors": bool(use_cross_layer_priors),
            "observation_count": len(ordered_obs_ids),
            "newly_assimilated_count": len(pending_events),
            "resumed_from_checkpoint_id": anchor_cp.checkpoint_id if anchor_cp else None,
            "tail_checkpoint_id": tail_checkpoint.checkpoint_id,
            "worldline_posterior_event_id": emitted_event_id,
            "worldline_posterior_event_type": emitted_event_type,
            "qualification_passed": qual_passed,
            "qualification_status": qual_status,
            "validation_block_reasons": block_reasons,
            "superseded_checkpoint_ids": superseded_cp_ids,
            "late_arrival_event_ids": late_arrival_ids,
            "checkpoints": [cp.summary_dict() for cp in final_chain],
            "state_means": final_means,
            "state_stds": final_stds,
            "state_covariance": final_cov,
            "state_support_ledger": support_ledger,
            "channel_calibration": copy.deepcopy(tail_checkpoint.channel_calibration),
            "canonical_grid": tail_checkpoint.canonical_grid,
            "has_spatial_observations": bool(tail_checkpoint.has_spatial_observations),
            "spatial_surfaces_count": len(tail_surfaces),
            "effective_resolution_by_state": {
                s["surface_type"]: s.get("effective_resolution_m")
                for s in tail_surfaces
            },
            "resolution_summary_by_state": {
                s["surface_type"]: s.get("resolution_summary")
                for s in tail_surfaces
                if s.get("resolution_summary") is not None
            },
            "weather_provenance_summary": summarize_weather_provenance(weather_series),
            "cross_layer_intelligence": tail_cross_layer,
            "gap_summary": gap_summary,
            "trajectory": full_trajectory,
            "newly_assimilated_trajectory": step_records,
            "event_memory": event_memory_result,
            "retrovalidation": retro_result,
        }

    def query_as_of(
        self,
        *,
        plot_id: str,
        geometry_hash: str,
        valid_time_T: Any,
        knowledge_cutoff_K: Optional[Any] = None,
        tenant_id: str = "default_tenant",
        namespace: str = "default",
        daily_weather: Optional[Dict[str, Dict[str, Any]]] = None,
        crop_context: Optional[Dict[str, Any]] = None,
        soil_context: Optional[Dict[str, Any]] = None,
        management_events: Optional[List[Any]] = None,
        polygon_geojson: Optional[Dict[str, Any]] = None,
        forecast_horizons_days: Sequence[int] = (7, 14, 28),
    ) -> Dict[str, Any]:
        """Read-only causal time-travel query at (valid_time_T, knowledge_cutoff_K)."""
        t_dt = _parse_utc_iso(valid_time_T)
        k_dt = (
            _parse_utc_iso(knowledge_cutoff_K)
            if knowledge_cutoff_K is not None
            else datetime.now(timezone.utc)
        )
        eligible_events = self.load_qualified_observations(
            plot_id=plot_id,
            valid_time_T=t_dt.isoformat(),
            knowledge_cutoff_K=k_dt.isoformat(),
            tenant_id=tenant_id,
            namespace=namespace,
        )
        # Strictly respect knowledge_cutoff_K so scenes committed after K never leak into available_dates!
        all_obs_all_time = self.load_qualified_observations(
            plot_id=plot_id,
            valid_time_T="2100-01-01T00:00:00+00:00",
            knowledge_cutoff_K=k_dt.isoformat(),
            tenant_id=tenant_id,
            namespace=namespace,
        )
        available_dates = [
            str(ev.get("observation_or_valid_time") or ev.get("effective_at") or "")[:10]
            for ev in all_obs_all_time
            if ev.get("observation_or_valid_time") or ev.get("effective_at")
        ]

        if not eligible_events:
            return {
                "available": False,
                "reason": "no_qualified_observations_before_cutoff",
                "plot_id": plot_id,
                "valid_time_T": t_dt.isoformat(),
                "knowledge_cutoff_K": k_dt.isoformat(),
                "eligible_event_ids": [],
                "available_dates": sorted(set(available_dates)),
                "spatial_surfaces": [],
                "effective_resolution_by_state": {},
                "state_means": {},
                "state_stds": {},
                "state_support_ledger": _build_historical_support_ledger({}),
            }

        ordered_ids = [str(ev["event_id"]) for ev in eligible_events]
        index_data = self.load_checkpoint_index(plot_id, tenant_id, namespace)
        active_cps: List[PosteriorCheckpoint] = []
        for cp_id in index_data.get("active_chain") or []:
            cp = self.load_checkpoint(plot_id, cp_id, tenant_id, namespace)
            if (
                cp is not None
                and cp.geometry_hash == geometry_hash
                and cp.model_version == RECONSTRUCTOR_MODEL_VERSION
                and cp.calibration_version == CALIBRATION_VERSION
            ):
                active_cps.append(cp)

        # Pick nearest stored checkpoint whose assimilated prefix matches eligible_events[:n]
        anchor_cp: Optional[PosteriorCheckpoint] = None
        for cp in active_cps:
            n = len(cp.assimilated_observation_ids)
            if n <= len(ordered_ids) and ordered_ids[:n] == list(cp.assimilated_observation_ids):
                anchor_cp = cp

        canonical_grid = build_canonical_parcel_grid(polygon_geojson) if polygon_geojson else None
        effective_cutoff_dt = min(t_dt, k_dt)
        effective_day_limit = effective_cutoff_dt.date().isoformat()
        weather_series = filter_causal_daily_weather_at_cutoff(daily_weather, effective_cutoff_dt)
        crop_ctx = dict(crop_context or {"crop_type": "citrus", "crop_coefficient": 0.75})
        soil_ctx = dict(soil_context or {})
        mgmt_events = [
            ev for ev in (management_events or [])
            if not isinstance(ev, dict)
            or str(ev.get("effective_start") or ev.get("timestamp") or ev.get("date") or "")[:10] <= effective_day_limit
        ]

        first_q_dt = _parse_utc_iso(eligible_events[0].get("observation_or_valid_time") or eligible_events[0].get("effective_at"))
        rng = make_rng("asmae_hist_recon", plot_id, geometry_hash, STATE_SCHEMA_VERSION)
        if anchor_cp is not None:
            start_idx = len(anchor_cp.assimilated_observation_ids)
            ensemble = copy.deepcopy(anchor_cp.ensemble_members)
            rng.setstate(_rng_state_from_json(anchor_cp.rng_state_json))
            prev_scene_time = _parse_utc_iso(anchor_cp.last_obs_time)
            accepted_counts = dict(anchor_cp.accepted_update_counts)
            channel_cal = copy.deepcopy(anchor_cp.channel_calibration or {})
            has_spatial_obs = bool(anchor_cp.has_spatial_observations)
            q_chrono = CrossLayerChronoState.from_dict(anchor_cp.specialist_chrono_state)
            if not q_chrono.layer_theta_profile:
                q_chrono = self.cross_layer_bridge.initialize_chrono_state(crop_context=crop_ctx, soil_context=soil_ctx)
            if canonical_grid is None and isinstance(anchor_cp.canonical_grid, dict):
                canonical_grid = dict(anchor_cp.canonical_grid)
                canonical_grid["inside_mask"] = _polygon_mask(
                    polygon_geojson,
                    canonical_grid.get("transform"),
                    int(canonical_grid["height"]),
                    int(canonical_grid["width"]),
                )
        else:
            start_idx = 0
            q_chrono = self.cross_layer_bridge.initialize_chrono_state(crop_context=crop_ctx, soil_context=soil_ctx)
            self.cross_layer_bridge.advance_chrono_state(
                q_chrono, start_time=first_q_dt - timedelta(days=5), end_time=first_q_dt,
                weather_daily_series=weather_series, crop_context=crop_ctx, soil_context=soil_ctx, management_events=mgmt_events,
            )
            init_b = self.cross_layer_bridge.evaluate_step_priors(
                state=q_chrono, timestamp=first_q_dt, knowledge_cutoff=k_dt, crop_context=crop_ctx, soil_context=soil_ctx,
            )
            ensemble, _ = initialize_ensemble(
                node_ids=self.node_ids,
                n_ensemble=self.n_ensemble,
                priors=init_b.get("priors") or {},
                crop_context=crop_ctx,
                rng=rng,
                scenes=[],
                initial_posterior=None,
            )
            prev_scene_time = None
            accepted_counts = {name: 0 for name in STATE_NAMES}
            channel_cal = {}
            has_spatial_obs = False

        spatial_delta: Optional[np.ndarray] = None
        spatial_var: Optional[np.ndarray] = None
        spatial_obs_count: Optional[np.ndarray] = None
        if canonical_grid is not None:
            H_c, W_c = int(canonical_grid["height"]), int(canonical_grid["width"])
            if anchor_cp is not None and anchor_cp.spatial_artifact:
                sp = self._load_spatial_arrays(anchor_cp)
                if sp is not None and sp.get("spatial_delta", np.empty(0)).shape == (len(_SPATIALLY_SUPPORTED_STATES), H_c, W_c):
                    spatial_delta = sp["spatial_delta"].astype(np.float32).copy()
                    spatial_var = sp["spatial_var"].astype(np.float32).copy()
                    spatial_obs_count = sp["spatial_obs_count"].astype(np.int32).copy()
            if spatial_delta is None:
                spatial_delta = np.zeros((len(_SPATIALLY_SUPPORTED_STATES), H_c, W_c), dtype=np.float32)
                spatial_var = np.full((len(_SPATIALLY_SUPPORTED_STATES), H_c, W_c), 0.015, dtype=np.float32)
                spatial_obs_count = np.zeros((H_c, W_c), dtype=np.int32)

        # Replay only tail delta from anchor_cp up to valid_time_T in memory (zero writes)
        replayed_steps: List[Dict[str, Any]] = []
        for cp in active_cps:
            if len(cp.assimilated_observation_ids) <= start_idx and cp.trajectory_segment:
                replayed_steps.extend(cp.trajectory_segment)

        for local_i, ev in enumerate(eligible_events[start_idx:]):
            payload = (ev.get("payload") or {}).get("observation_qualified") or {}
            obs_time = _parse_utc_iso(ev.get("observation_or_valid_time") or ev.get("effective_at"))
            step_weather_q = filter_causal_daily_weather_at_cutoff(weather_series, obs_time)
            self.cross_layer_bridge.advance_chrono_state(
                q_chrono,
                start_time=prev_scene_time or (obs_time - timedelta(days=5)),
                end_time=obs_time,
                weather_daily_series=step_weather_q,
                crop_context=crop_ctx,
                soil_context=soil_ctx,
                management_events=mgmt_events,
            )
            q_step_pre = self.cross_layer_bridge.evaluate_step_priors(
                state=q_chrono, timestamp=obs_time, knowledge_cutoff=k_dt, crop_context=crop_ctx, soil_context=soil_ctx,
            )
            q_step_priors = q_step_pre.get("priors") or {}
            elapsed_days = 0.0
            if prev_scene_time is not None and obs_time > prev_scene_time:
                elapsed_days = (obs_time - prev_scene_time).total_seconds() / 86400.0
                ensemble, _ = _forecast_elapsed_interval(
                    ensemble=ensemble,
                    previous_time=prev_scene_time,
                    current_time=obs_time,
                    priors=q_step_priors,
                    crop_context=crop_ctx,
                    rng=rng,
                    scenes=[],
                    weather_daily_series=step_weather_q,
                    soil_context=soil_ctx,
                    management_events=mgmt_events,
                )
            prev_scene_time = obs_time
            obs_channels, obs_grids = _load_scene_raster_observations(
                payload,
                self.scene_store,
                plot_id,
                polygon_geojson,
                canonical_grid=canonical_grid,
                return_grids=True,
            )
            prior_preds = self._predict_pre_update_channels(
                ensemble, self.node_ids, obs_channels, payload,
                channel_cal=channel_cal, elapsed_days=elapsed_days, obs_dt=obs_time,
            )
            cloud_frac = float(payload.get("cloud_score", 0.0) or 0.0)
            valid_frac = float(payload.get("valid_pixel_fraction", 1.0) or 1.0)
            pending_cal_q: List[Tuple[str, float, Dict[str, Any], float]] = []
            for obs_name, obs_val in sorted(obs_channels.items()):
                mapping = INDEX_STATE_REGISTRY.get(obs_name)
                if mapping is None:
                    continue
                target_indices = [
                    s for s in mapping.target_state_indices
                    if 0 <= s < N_STATES
                    and not validate_forbidden_state_update(obs_name, s)
                    and STATE_DESCRIPTORS[s].assimilation_policy != AssimilationPolicy.NOT_ASSIMILATED
                ]
                if not target_indices:
                    continue
                sigma_obs = compute_observation_noise(
                    obs_name, cloud_fraction=cloud_frac, valid_support_fraction=max(0.05, valid_frac)
                )
                pred_rec = prior_preds.get(obs_name) or {}
                bias_prior = float(pred_rec.get("bias_offset_applied", 0.0) or 0.0)
                slope_prior = max(0.20, float(pred_rec.get("slope_applied", 1.0) or 1.0))
                lo_b, hi_b = _CHANNEL_BOUNDS.get(obs_name, (-1.0, 1.0))
                obs_for_filter = float(np.clip((float(obs_val) - bias_prior) / slope_prior, lo_b, hi_b))
                r_var_q = (sigma_obs * sigma_obs) / max(0.30, slope_prior * slope_prior)
                _proxy_update_single_obs(
                    ensemble, self.node_ids, obs_name, obs_for_filter,
                    mapping, sigma_obs, r_var_q, rng, target_indices=target_indices,
                )
                for s_idx in target_indices:
                    accepted_counts[STATE_NAMES[s_idx]] = accepted_counts.get(STATE_NAMES[s_idx], 0) + 1
                if pred_rec:
                    pending_cal_q.append((obs_name, float(obs_val), pred_rec, float(sigma_obs)))
            ensemble = clamp_ensemble(ensemble)
            step_means, step_stds, _, _, _ = _summarize_13_state_ensemble(ensemble, self.node_ids)
            step_vec_q = [float(step_means.get(n, 0.25)) for n in STATE_NAMES]
            for obs_name, obs_val_f, pred_rec, sigma_obs_f in pending_cal_q:
                mp_c = INDEX_STATE_REGISTRY.get(obs_name)
                post_raw = (
                    predict_sar_observation(obs_name, step_vec_q)
                    if (mp_c is not None and mp_c.sensor == "S1")
                    else predict_observation(obs_name, step_vec_q)
                )
                raw_pred = float(pred_rec.get("y_pred_raw", obs_val_f))
                cal_pred = float(pred_rec.get("y_pred_calibrated", obs_val_f))
                unscaled_sig = max(1e-4, float(pred_rec.get("unscaled_pred_sigma", pred_rec.get("raw_pred_sigma", sigma_obs_f))))
                channel_cal[obs_name] = update_channel_cal_entry(
                    channel_cal.get(obs_name),
                    obs_val=obs_val_f,
                    raw_pred=raw_pred,
                    cal_pred=cal_pred,
                    unscaled_sig=unscaled_sig,
                    obs_name=obs_name,
                    obs_dt=obs_time,
                    post_raw_pred=float(post_raw) if (post_raw is not None and math.isfinite(float(post_raw))) else raw_pred,
                    var_scale_used=pred_rec.get("var_scale_applied"),
                )
            if isinstance(obs_channels.get("ndvi"), (int, float)):
                exp_v = float((q_step_priors.get("layer2") or {}).get("expected_vigor", 0.55) or 0.55)
                q_chrono.recent_ndvi_window.append((obs_time.isoformat()[:10], float(obs_channels["ndvi"]), exp_v))
                if len(q_chrono.recent_ndvi_window) > 10:
                    q_chrono.recent_ndvi_window = q_chrono.recent_ndvi_window[-10:]
            if isinstance(obs_channels.get("ndmi"), (int, float)):
                q_chrono.recent_ndmi_window.append(float(obs_channels["ndmi"]))
                if len(q_chrono.recent_ndmi_window) > 8:
                    q_chrono.recent_ndmi_window = q_chrono.recent_ndmi_window[-8:]
            if canonical_grid is not None and spatial_delta is not None and spatial_var is not None and spatial_obs_count is not None:
                has_spatial_obs = self._update_spatial_anomaly_field(
                    spatial_delta=spatial_delta,
                    spatial_var=spatial_var,
                    spatial_obs_count=spatial_obs_count,
                    inside_mask=canonical_grid["inside_mask"],
                    obs_grids=obs_grids,
                    elapsed_days=elapsed_days,
                    post_stds=step_stds,
                    has_spatial_observations=has_spatial_obs,
                )
            replayed_steps.append({
                "step_index": start_idx + local_i,
                "event_id": str(ev["event_id"]),
                "scene_id": str(payload.get("scene_id") or ""),
                "source": str(payload.get("source") or ""),
                "acquisition_time": obs_time.isoformat(),
                "committed_at": str(ev.get("committed_at") or ""),
                "elapsed_days": round(elapsed_days, 3),
                "obs_channels": obs_channels,
                "raw_metrics": dict(payload.get("metrics") or {}),
                "prior_predictions": prior_preds,
                "prior_state_means": copy.deepcopy(q_step_priors),
                "posterior_state_means": step_means,
                "posterior_state_stds": step_stds,
                "cross_layer_priors": q_step_priors,
            })

        # Advance specialist hydrological/phenological model to exact valid_time_T
        self.cross_layer_bridge.advance_chrono_state(
            q_chrono,
            start_time=prev_scene_time or t_dt,
            end_time=t_dt,
            weather_daily_series=weather_series,
            crop_context=crop_ctx,
            soil_context=soil_ctx,
            management_events=mgmt_events,
        )
        q_pre_T = self.cross_layer_bridge.evaluate_step_priors(
            state=q_chrono, timestamp=t_dt, knowledge_cutoff=k_dt, crop_context=crop_ctx, soil_context=soil_ctx,
        )
        q_priors_T = q_pre_T.get("priors") or {}

        # Propagate strictly forward from last observation up to valid_time_T if T > prev_scene_time
        state_age_days = 0.0
        if prev_scene_time is not None and t_dt > prev_scene_time:
            state_age_days = (t_dt - prev_scene_time).total_seconds() / 86400.0
            ensemble, _ = _forecast_elapsed_interval(
                ensemble=ensemble,
                previous_time=prev_scene_time,
                current_time=t_dt,
                priors=q_priors_T,
                crop_context=crop_ctx,
                rng=rng,
                scenes=[],
                weather_daily_series=weather_series,
                soil_context=soil_ctx,
                management_events=mgmt_events,
            )
            ensemble = clamp_ensemble(ensemble)
            if canonical_grid is not None and spatial_delta is not None and spatial_var is not None and spatial_obs_count is not None:
                _, cur_stds, _, _, _ = _summarize_13_state_ensemble(ensemble, self.node_ids)
                self._update_spatial_anomaly_field(
                    spatial_delta=spatial_delta,
                    spatial_var=spatial_var,
                    spatial_obs_count=spatial_obs_count,
                    inside_mask=canonical_grid["inside_mask"],
                    obs_grids={},
                    elapsed_days=state_age_days,
                    post_stds=cur_stds,
                    has_spatial_observations=has_spatial_obs,
                )

        means_T, stds_T, cov_T, _, _ = _summarize_13_state_ensemble(ensemble, self.node_ids)
        ledger_T = _build_historical_support_ledger(
            accepted_counts,
            has_spatial_rasters=has_spatial_obs,
            canonical_grid=canonical_grid,
        )
        surfaces_T = self.build_spatial_surfaces_payload(
            canonical_grid=canonical_grid,
            state_means=means_T,
            state_stds=stds_T,
            accepted_counts=accepted_counts,
            spatial_delta=spatial_delta,
            spatial_var=spatial_var,
            has_spatial_observations=has_spatial_obs,
            spatial_obs_count=spatial_obs_count,
        )
        suppressed_spatial = {
            name: {
                "spatial_support": rec.get("spatial_support"),
                "reason": (
                    compute_adaptive_state_spatial_resolution(
                        name,
                        accepted_count=int(accepted_counts.get(name, 0) or 0),
                        has_spatial_rasters=has_spatial_obs,
                        canonical_grid=canonical_grid,
                        accepted_counts=accepted_counts,
                    ).get("limiting_factor")
                ),
            }
            for name, rec in ledger_T.items()
            if name in _SPATIALLY_SUPPORTED_STATES
            and (
                not has_spatial_obs
                or compute_adaptive_state_spatial_resolution(
                    name,
                    accepted_count=int(accepted_counts.get(name, 0) or 0),
                    has_spatial_rasters=has_spatial_obs,
                    canonical_grid=canonical_grid,
                    accepted_counts=accepted_counts,
                ).get("suppress_surface")
            )
        }
        q_refined_T = self.cross_layer_bridge.refine_after_asmae(
            pre_bundle=q_pre_T,
            posterior_means=means_T,
            posterior_stds=stds_T,
            state_support_ledger=ledger_T,
            crop_context=crop_ctx,
            gap_days=state_age_days,
        )

        # Causal multi-horizon forward forecast issued at T using strict D-1 issuance weather + causal DOY climatology
        sorted_horizons = sorted({int(h) for h in forecast_horizons_days if int(h) > 0})
        max_h = max(sorted_horizons) if sorted_horizons else 28
        causal_fc_weather = build_prospective_weather_series(
            weather_series, t_dt, t_dt + timedelta(days=max_h),
            strict_previous_complete_day=True,
        )
        causal_forecasts: List[Dict[str, Any]] = []
        fc_ens = copy.deepcopy(ensemble)
        fc_rng = make_rng("asmae_causal_fc", plot_id, geometry_hash, t_dt.isoformat())
        cur_fc_dt = t_dt
        for h_days in sorted_horizons:
            target_fc_dt = t_dt + timedelta(days=h_days)
            fc_ens, _ = _forecast_elapsed_interval(
                ensemble=fc_ens,
                previous_time=cur_fc_dt,
                current_time=target_fc_dt,
                priors=q_priors_T,
                crop_context=crop_ctx,
                rng=fc_rng,
                scenes=[],
                weather_daily_series=causal_fc_weather,
                soil_context=soil_ctx,
                management_events=[],
            )
            fc_ens = clamp_ensemble(fc_ens)
            cur_fc_dt = target_fc_dt
            fc_means, fc_stds, _, _, _ = _summarize_13_state_ensemble(fc_ens, self.node_ids)
            fc_preds = self._predict_pre_update_channels(
                fc_ens,
                self.node_ids,
                {"ndvi": 0.0, "ndmi": 0.0, "sar_vv": 0.0, "sar_vh": 0.0},
                {"cloud_score": 0.1, "valid_pixel_fraction": 0.9},
                channel_cal=channel_cal,
                elapsed_days=float(h_days),
                obs_dt=target_fc_dt,
            )
            causal_forecasts.append({
                "horizon_days": h_days,
                "target_valid_time": target_fc_dt.isoformat(),
                "predicted_states": {k: fc_means[k] for k in ("vigor", "lai", "canopy_water", "root_zone_water", "stress_memory")},
                "predicted_state_stds": {k: fc_stds[k] for k in ("vigor", "lai", "canopy_water", "root_zone_water", "stress_memory")},
                "predicted_channels": {
                    ch: {
                        "mean": p["y_pred_calibrated"],
                        "raw_mean": p["y_pred_raw"],
                        "sigma": p["pred_sigma"],
                    }
                    for ch, p in fc_preds.items()
                },
            })

        return {
            "available": True,
            "plot_id": plot_id,
            "geometry_hash": geometry_hash,
            "publication_authority": "DIAGNOSTIC_ONLY",
            "claims_numerical_authority": False,
            "valid_time_T": t_dt.isoformat(),
            "knowledge_cutoff_K": k_dt.isoformat(),
            "resumed_from_checkpoint_id": anchor_cp.checkpoint_id if anchor_cp else None,
            "eligible_event_ids": ordered_ids,
            "assimilated_observation_count": len(eligible_events),
            "last_observation_time": prev_scene_time.isoformat() if prev_scene_time else None,
            "days_since_last_observation": round(state_age_days, 2),
            "available_dates": sorted(set(available_dates)),
            "state_means": means_T,
            "state_stds": stds_T,
            "state_covariance": cov_T,
            "state_support_ledger": ledger_T,
            "canonical_grid": {k: v for k, v in canonical_grid.items() if k != "inside_mask"} if canonical_grid else None,
            "has_spatial_observations": bool(has_spatial_obs),
            "spatial_surfaces": surfaces_T,
            "effective_resolution_by_state": {
                s["surface_type"]: s.get("effective_resolution_m")
                for s in surfaces_T
            },
            "resolution_summary_by_state": {
                s["surface_type"]: s.get("resolution_summary")
                for s in surfaces_T
                if s.get("resolution_summary") is not None
            },
            "weather_provenance_summary": summarize_weather_provenance(
                weather_series,
                knowledge_cutoff_dt=k_dt,
            ),
            "suppressed_spatial_states": suppressed_spatial,
            "cross_layer_pre_priors": q_priors_T,
            "cross_layer_intelligence": q_refined_T,
            "causal_forecasts": causal_forecasts,
            "trajectory": replayed_steps,
        }
