"""Independent Physical & Field Evidence Validation for ASMAE Historical Intelligence.

Evaluates withheld physical domain evidence (SoilAnalysis lab records, IoT Soil
Moisture/EC/Temp SensorReadings, MESIA multi-strata radio bridges, CropObservation
scouting notes, and CropTask management records) against ASMAE's independent
satellite + ERA5 state reconstructions WITHOUT feeding validation targets back
into the assimilation filter or tuning model parameters on evaluation plots.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from services.agribrain.layer05_asmae.history.historical_retrovalidation import _parse_dt
from services.agribrain.mesia.assimilation.spatial_lattice import LatticeStrata
from services.agribrain.mesia.contracts.behaviour import BehaviourLikelihood
from services.agribrain.mesia.integration_layer3 import MesiaLayer3WaterBridge

# Standard USDA soil texture hydrology priors (van Genuchten / FAO-56 class means)
_TEXTURE_HYDROLOGY: Dict[str, Dict[str, float]] = {
    "SAND": {
        "field_capacity": 0.16,
        "wilting_point": 0.06,
        "saturation": 0.43,
        "drainage_fraction": 0.72,
        "runoff_fraction": 0.05,
        "rooting_depth_m": 0.50,
    },
    "SANDY": {
        "field_capacity": 0.21,
        "wilting_point": 0.08,
        "saturation": 0.44,
        "drainage_fraction": 0.65,
        "runoff_fraction": 0.08,
        "rooting_depth_m": 0.55,
    },
    "SANDY_LOAM": {
        "field_capacity": 0.23,
        "wilting_point": 0.10,
        "saturation": 0.45,
        "drainage_fraction": 0.60,
        "runoff_fraction": 0.10,
        "rooting_depth_m": 0.60,
    },
    "LOAM": {
        "field_capacity": 0.29,
        "wilting_point": 0.13,
        "saturation": 0.47,
        "drainage_fraction": 0.48,
        "runoff_fraction": 0.12,
        "rooting_depth_m": 0.70,
    },
    "CLAY_LOAM": {
        "field_capacity": 0.36,
        "wilting_point": 0.19,
        "saturation": 0.49,
        "drainage_fraction": 0.35,
        "runoff_fraction": 0.18,
        "rooting_depth_m": 0.65,
    },
    "CLAY": {
        "field_capacity": 0.40,
        "wilting_point": 0.23,
        "saturation": 0.50,
        "drainage_fraction": 0.25,
        "runoff_fraction": 0.22,
        "rooting_depth_m": 0.60,
    },
}

_CROP_PHYSICS_DEFAULTS: Dict[str, Dict[str, float]] = {
    "citrus": {"crop_coefficient": 0.75, "t_opt": 25.0, "t_max": 39.0, "t_base": 12.0, "rooting_depth_m": 0.85},
    "orange": {"crop_coefficient": 0.75, "t_opt": 25.0, "t_max": 39.0, "t_base": 12.0, "rooting_depth_m": 0.85},
    "tomato": {"crop_coefficient": 1.05, "t_opt": 24.0, "t_max": 37.0, "t_base": 10.0, "rooting_depth_m": 0.55},
    "wheat": {"crop_coefficient": 0.95, "t_opt": 20.0, "t_max": 34.0, "t_base": 4.0, "rooting_depth_m": 0.80},
    "potato": {"crop_coefficient": 1.00, "t_opt": 20.0, "t_max": 33.0, "t_base": 7.0, "rooting_depth_m": 0.45},
    "olive": {"crop_coefficient": 0.60, "t_opt": 26.0, "t_max": 42.0, "t_base": 10.0, "rooting_depth_m": 1.00},
    "date_palm": {"crop_coefficient": 0.90, "t_opt": 30.0, "t_max": 46.0, "t_base": 14.0, "rooting_depth_m": 1.20},
}


def build_soil_and_crop_context_from_domain(
    *,
    plot_doc: Optional[Dict[str, Any]] = None,
    soil_analysis: Optional[Dict[str, Any]] = None,
    crop_cycle: Optional[Dict[str, Any]] = None,
    fallback_crop: str = "citrus",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Translate Plot, SoilAnalysis, and CropCycle domain metadata into physical ASMAE priors."""
    p = plot_doc or {}
    sa = soil_analysis or {}
    cc = crop_cycle or {}

    raw_tex = str(sa.get("texture") or p.get("soilType") or "LOAM").strip().upper().replace(" ", "_")
    hyd = dict(_TEXTURE_HYDROLOGY.get(raw_tex, _TEXTURE_HYDROLOGY["LOAM"]))
    soil_ctx: Dict[str, Any] = {
        "texture": raw_tex,
        **hyd,
    }
    if sa.get("ec") is not None and math.isfinite(float(sa["ec"])):
        soil_ctx["electrical_conductivity"] = float(sa["ec"])
    if sa.get("ph") is not None and math.isfinite(float(sa["ph"])):
        soil_ctx["ph"] = float(sa["ph"])
    if sa.get("organicMatter") is not None and math.isfinite(float(sa["organicMatter"])):
        om = float(sa["organicMatter"])
        soil_ctx["organic_matter_pct"] = om
        # Slight organic-matter water retention refinement (Saxton & Rawls sign direction)
        soil_ctx["field_capacity"] = round(min(0.48, soil_ctx["field_capacity"] + 0.008 * max(0.0, om - 1.5)), 4)

    raw_crop = str(cc.get("cropCode") or cc.get("cropType") or p.get("cropType") or fallback_crop).strip().lower()
    crop_key = raw_crop if raw_crop in _CROP_PHYSICS_DEFAULTS else fallback_crop
    crop_params = dict(_CROP_PHYSICS_DEFAULTS.get(crop_key, _CROP_PHYSICS_DEFAULTS["citrus"]))
    if crop_params.get("rooting_depth_m"):
        soil_ctx["rooting_depth_m"] = float(crop_params["rooting_depth_m"])
    crop_ctx: Dict[str, Any] = {
        "crop_type": crop_key,
        "variety": cc.get("variety"),
        "stage": cc.get("stage") or cc.get("status"),
        "crop_coefficient": crop_params["crop_coefficient"],
        "optimal_temperature": crop_params["t_opt"],
        "maximum_temperature": crop_params["t_max"],
        "base_temperature": crop_params["t_base"],
    }
    return soil_ctx, crop_ctx


def normalize_soil_moisture_vwc(raw_val: Any) -> Optional[float]:
    """Normalize IoT volumetric moisture reading (% or m3/m3) into [0.0, 0.70] m3/m3."""
    if raw_val is None or isinstance(raw_val, bool):
        return None
    try:
        v = float(raw_val)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v) or v < 0.0:
        return None
    if v > 1.5:
        v = v / 100.0
    if v > 0.75:
        return None
    return round(v, 5)


def _parse_probe_depth_cm(rec: Dict[str, Any]) -> Optional[float]:
    """Extract probe sensing depth in centimetres when reported."""
    meta = rec.get("metadata") if isinstance(rec.get("metadata"), dict) else {}
    for key in ("depth_cm", "sensorDepthCm", "probeDepthCm", "depthCm", "depth"):
        val = rec.get(key) if rec.get(key) is not None else meta.get(key)
        if val is None or isinstance(val, bool):
            continue
        if isinstance(val, (int, float)) and math.isfinite(float(val)) and float(val) >= 0.0:
            return float(val)
        txt = str(val).strip().lower()
        if not txt:
            continue
        if "surface" in txt or "0-5" in txt or "0_5" in txt:
            return 2.5
        if "root" in txt:
            return 20.0
        import re as _re
        m_m = _re.search(r"(\d+(?:\.\d+)?)\s*m\b", txt)
        if m_m and "cm" not in txt and "mm" not in txt:
            return float(m_m.group(1)) * 100.0
        m_cm = _re.search(r"(\d+(?:\.\d+)?)", txt)
        if m_cm:
            return float(m_cm.group(1))
    for key in ("depth_m", "depthM"):
        val = rec.get(key) if rec.get(key) is not None else meta.get(key)
        if isinstance(val, (int, float)) and not isinstance(val, bool) and math.isfinite(float(val)) and float(val) >= 0.0:
            return float(val) * 100.0
    return None


def _classify_depth_zone(depth_cm: Optional[float], max_root_depth_cm: float = 120.0) -> Tuple[str, bool, str]:
    """Classify probe depth compatibility against ASMAE `root_zone_water`."""
    if depth_cm is None:
        return "unspecified", True, "probe_depth_not_reported_provisional"
    if depth_cm <= 7.5:
        return "surface_0_5cm", False, "surface_probe_incompatible_with_root_zone_vwc"
    if depth_cm <= min(75.0, max(45.0, max_root_depth_cm)):
        return "root_zone_5_60cm", True, "compatible_root_zone_depth"
    return "sub_root_zone_deep", False, "deep_sub_root_probe_excluded_from_root_zone_vwc"


def _extract_probe_lat_lng(rec: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """Extract (lat, lng) from probe metadata or GeoJSON point."""
    lat = rec.get("lat") if rec.get("lat") is not None else rec.get("latitude")
    lng = rec.get("lng") if rec.get("lng") is not None else (
        rec.get("lon") if rec.get("lon") is not None else rec.get("longitude")
    )
    if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
        if math.isfinite(float(lat)) and math.isfinite(float(lng)):
            return float(lat), float(lng)
    loc = rec.get("location")
    if isinstance(loc, dict) and isinstance(loc.get("coordinates"), (list, tuple)) and len(loc["coordinates"]) >= 2:
        try:
            return float(loc["coordinates"][1]), float(loc["coordinates"][0])
        except (TypeError, ValueError):
            pass
    return None


def _point_in_ring(lat: float, lng: float, ring: Sequence[Sequence[float]], tol_deg: float = 1e-4) -> bool:
    """Ray-casting point-in-ring test with small boundary tolerance (~10m GPS jitter)."""
    if len(ring) < 3:
        return False
    xs = [float(p[0]) for p in ring]
    ys = [float(p[1]) for p in ring]
    if lng < min(xs) - tol_deg or lng > max(xs) + tol_deg or lat < min(ys) - tol_deg or lat > max(ys) + tol_deg:
        return False
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = float(ring[i][0]), float(ring[i][1])
        x2, y2 = float(ring[(i + 1) % n][0]), float(ring[(i + 1) % n][1])
        if ((y1 > lat) != (y2 > lat)) and (lng < (x2 - x1) * (lat - y1) / ((y2 - y1) or 1e-12) + x1):
            inside = not inside
    if inside:
        return True
    # Boundary tolerance check against polygon edges
    for i in range(n):
        x1, y1 = float(ring[i][0]), float(ring[i][1])
        x2, y2 = float(ring[(i + 1) % n][0]), float(ring[(i + 1) % n][1])
        dx, dy = x2 - x1, y2 - y1
        seg2 = dx * dx + dy * dy
        if seg2 > 0:
            t = max(0.0, min(1.0, ((lng - x1) * dx + (lat - y1) * dy) / seg2))
            if math.hypot(lng - (x1 + t * dx), lat - (y1 + t * dy)) <= tol_deg:
                return True
    return False


def _point_in_geojson(lat: float, lng: float, polygon_geojson: Optional[Dict[str, Any]]) -> Optional[bool]:
    """Return True if point falls in polygon, False if outside, or None if geometry missing."""
    if not isinstance(polygon_geojson, dict):
        return None
    geom = polygon_geojson.get("geometry") if polygon_geojson.get("type") == "Feature" else polygon_geojson
    if not isinstance(geom, dict):
        return None
    gtype = geom.get("type")
    coords = geom.get("coordinates") or []
    if gtype == "Polygon" and coords:
        return _point_in_ring(lat, lng, coords[0])
    if gtype == "MultiPolygon" and coords:
        return any(poly and _point_in_ring(lat, lng, poly[0]) for poly in coords)
    return None


def _sample_spatial_surface_at_coord(
    lat: float,
    lng: float,
    spatial_surfaces: Optional[Sequence[Dict[str, Any]]],
    surface_type: str = "ASMAE_ROOT_ZONE_WATER",
) -> Optional[Dict[str, Any]]:
    """Sample local pixel prediction, uncertainty, and local resolution at probe (lat, lng)."""
    for surf in spatial_surfaces or []:
        if not isinstance(surf, dict) or surf.get("surface_type") != surface_type:
            continue
        bounds = surf.get("bounds")
        vals = surf.get("values")
        if not (isinstance(bounds, (list, tuple)) and len(bounds) == 4 and isinstance(vals, list) and vals):
            continue
        min_lng, min_lat, max_lng, max_lat = [float(b) for b in bounds]
        if max_lng <= min_lng or max_lat <= min_lat:
            continue
        if not (min_lng <= lng <= max_lng and min_lat <= lat <= max_lat):
            continue
        H = len(vals)
        W = len(vals[0]) if vals[0] else 0
        if H == 0 or W == 0:
            continue
        r = max(0, min(H - 1, int((max_lat - lat) / (max_lat - min_lat) * H)))
        c = max(0, min(W - 1, int((lng - min_lng) / (max_lng - min_lng) * W)))
        px_v = vals[r][c]
        if px_v is None or not math.isfinite(float(px_v)):
            continue
        u_grid = surf.get("uncertainty")
        px_u = u_grid[r][c] if isinstance(u_grid, list) and r < len(u_grid) and c < len(u_grid[r]) else None
        l_grid = surf.get("local_resolution_map_m")
        px_res = l_grid[r][c] if isinstance(l_grid, list) and r < len(l_grid) and c < len(l_grid[r]) else surf.get("effective_resolution_m")
        return {
            "row": r,
            "col": c,
            "value": float(px_v),
            "sigma": float(px_u) if (px_u is not None and math.isfinite(float(px_u))) else None,
            "local_resolution_m": float(px_res) if px_res is not None else None,
        }
    return None


def _classify_probe_calibration(
    rec: Dict[str, Any],
    vendor: str,
    vwc: float,
    theta_sat: float,
) -> Tuple[bool, str]:
    """Determine if a probe reading represents calibrated, physically plausible instrumentation."""
    if rec.get("isCalibrated") is False or rec.get("calibrated") is False:
        return False, "explicit_uncalibrated"
    cal_st = str(rec.get("calibrationStatus") or rec.get("calibration_status") or "").strip().lower()
    if cal_st in ("uncalibrated", "raw", "draft", "factory_uncalibrated", "pending"):
        return False, f"status_{cal_st}"
    if float(vwc) > float(theta_sat) + 0.08:
        return False, "implausible_above_saturation"
    v_low = str(vendor or "").strip().lower()
    if not v_low or v_low in ("unspecified", "unknown", "none", "unverified"):
        if rec.get("isCalibrated") is True or rec.get("calibrated") is True or cal_st in ("calibrated", "verified"):
            return True, "explicit_calibrated"
        return False, "unspecified_vendor_unverified_calibration"
    return True, "calibrated"


def evaluate_independent_field_evidence(
    *,
    plot_id: str,
    trajectory: Sequence[Dict[str, Any]],
    sensor_readings: Optional[Sequence[Dict[str, Any]]] = None,
    soil_analyses: Optional[Sequence[Dict[str, Any]]] = None,
    crop_observations: Optional[Sequence[Dict[str, Any]]] = None,
    crop_tasks: Optional[Sequence[Dict[str, Any]]] = None,
    mesia_packets: Optional[Sequence[Dict[str, Any]]] = None,
    exclude_mock_vendors: bool = True,
    polygon_geojson: Optional[Dict[str, Any]] = None,
    spatial_surfaces: Optional[List[Dict[str, Any]]] = None,
    soil_context: Optional[Dict[str, Any]] = None,
    max_scene_gap_days: float = 21.0,
    enforce_causal_pre_reading: bool = True,
) -> Dict[str, Any]:
    """Cross-check withheld physical evidence strictly causally, by depth, space, calibration, and independent device-days."""
    parsed_steps: List[Tuple[datetime, Dict[str, Any]]] = []
    for st in trajectory:
        if st.get("acquisition_time") and isinstance(st.get("posterior_state_means"), dict):
            parsed_steps.append((_parse_dt(st["acquisition_time"]), st))
    parsed_steps.sort(key=lambda item: item[0])

    theta_sat = float((soil_context or {}).get("theta_sat") or 0.46)
    max_root_cm = float((soil_context or {}).get("rooting_depth_m") or 1.2) * 100.0

    def _causal_asmae_state(
        ts: datetime,
        max_gap_days: float = max_scene_gap_days,
    ) -> Tuple[Optional[Tuple[float, Dict[str, Any]]], Optional[Tuple[float, Dict[str, Any]]]]:
        """Find strictly causal (step_dt <= ts) match, plus separate post-reading reference."""
        best_pre: Optional[Tuple[float, Dict[str, Any]]] = None
        best_post: Optional[Tuple[float, Dict[str, Any]]] = None
        for dt_s, st in parsed_steps:
            diff_d = (ts - dt_s).total_seconds() / 86400.0
            if 0.0 <= diff_d <= max_gap_days:
                if best_pre is None or diff_d < best_pre[0]:
                    best_pre = (diff_d, st)
            elif -max_gap_days <= diff_d < 0.0:
                lead_d = -diff_d
                if best_post is None or lead_d < best_post[0]:
                    best_post = (lead_d, st)
        return best_pre, best_post

    # 1. In-situ SensorReading validation (Soil Moisture VWC vs ASMAE root_zone_water)
    vwc_comparisons: List[Dict[str, Any]] = []
    post_reading_refs: List[Dict[str, Any]] = []
    grouped_device_days: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    skipped_mock_count = 0
    excluded_post_reading_non_causal = 0
    excluded_surface_depth_count = 0
    excluded_deep_depth_count = 0
    excluded_out_of_plot_count = 0
    unspecified_depth_count = 0
    spatial_pixel_matched_count = 0
    plot_mean_fallback_count = 0
    uncalibrated_or_outlier_count = 0
    depth_breakdown: Dict[str, int] = {}

    for rec in sensor_readings or []:
        vendor = str(rec.get("vendor") or "")
        if exclude_mock_vendors and any(tok in vendor.lower() for tok in ("mock", "simulator", "synthetic")):
            skipped_mock_count += 1
            continue
        vwc = normalize_soil_moisture_vwc(rec.get("soilMoisture"))
        raw_ts = rec.get("timestamp")
        if vwc is None or not raw_ts:
            continue
        ts_dt = _parse_dt(raw_ts)

        depth_cm = _parse_probe_depth_cm(rec)
        depth_zone, depth_compat, depth_note = _classify_depth_zone(depth_cm, max_root_cm)
        depth_breakdown[depth_zone] = depth_breakdown.get(depth_zone, 0) + 1
        if depth_zone == "unspecified":
            unspecified_depth_count += 1
        if not depth_compat:
            if depth_zone == "surface_0_5cm":
                excluded_surface_depth_count += 1
            else:
                excluded_deep_depth_count += 1
            continue

        coords = _extract_probe_lat_lng(rec)
        if coords is not None and polygon_geojson is not None:
            in_poly = _point_in_geojson(coords[0], coords[1], polygon_geojson)
            if in_poly is False:
                excluded_out_of_plot_count += 1
                continue

        pre_match, post_match = _causal_asmae_state(ts_dt, max_gap_days=max_scene_gap_days)
        if pre_match is None:
            if post_match is not None:
                excluded_post_reading_non_causal += 1
                if len(post_reading_refs) < 5:
                    p_gap, p_st = post_match
                    p_mu = float((p_st.get("posterior_state_means") or {}).get("root_zone_water", 0.0))
                    post_reading_refs.append({
                        "timestamp": ts_dt.isoformat(),
                        "device_id": str(rec.get("deviceId") or rec.get("sensorId") or ""),
                        "observed_vwc": vwc,
                        "post_reading_scene_lead_days": round(p_gap, 2),
                        "asmae_rzw_mean_post_reading": round(p_mu, 5),
                        "is_causal": False,
                    })
            if enforce_causal_pre_reading or post_match is None:
                continue
            gap_d, st = post_match
            is_causal_lookup = False
        else:
            gap_d, st = pre_match
            is_causal_lookup = True

        rzw_mu = float((st.get("posterior_state_means") or {}).get("root_zone_water", 0.0))
        rzw_sig = max(0.01, float((st.get("posterior_state_stds") or {}).get("root_zone_water", 0.05)))
        spatial_mode = "plot_mean_no_probe_coords"
        local_res_m: Optional[float] = None
        if coords is not None:
            px_sample = _sample_spatial_surface_at_coord(coords[0], coords[1], spatial_surfaces, "ASMAE_ROOT_ZONE_WATER")
            if px_sample is not None:
                rzw_mu = float(px_sample["value"])
                if px_sample["sigma"] is not None:
                    rzw_sig = max(0.01, float(px_sample["sigma"]))
                local_res_m = px_sample.get("local_resolution_m")
                spatial_mode = "local_canonical_grid_pixel"
                spatial_pixel_matched_count += 1
            else:
                spatial_mode = "plot_mean_coords_unmapped_to_surface"
                plot_mean_fallback_count += 1
        else:
            plot_mean_fallback_count += 1

        is_cal, cal_reason = _classify_probe_calibration(rec, vendor, vwc, theta_sat)
        if not is_cal:
            uncalibrated_or_outlier_count += 1

        err = rzw_mu - vwc
        z_val = abs(err) / rzw_sig
        dev_id = str(rec.get("deviceId") or rec.get("sensorId") or "unknown_device")
        row = {
            "timestamp": ts_dt.isoformat(),
            "date_utc": ts_dt.date().isoformat(),
            "device_id": dev_id,
            "vendor": vendor or "unspecified",
            "depth_cm": depth_cm,
            "depth_zone": depth_zone,
            "depth_note": depth_note,
            "spatial_lookup_mode": spatial_mode,
            "local_resolution_m": local_res_m,
            "is_calibrated": is_cal,
            "calibration_status": cal_reason,
            "is_causal_lookup": is_causal_lookup,
            "observed_vwc": vwc,
            "asmae_rzw_mean": round(rzw_mu, 5),
            "asmae_rzw_sigma": round(rzw_sig, 5),
            "error": round(err, 5),
            "abs_z": round(z_val, 3),
            "within_2sigma": bool(z_val <= 2.0),
            "scene_gap_days": round(gap_d, 2),
        }
        vwc_comparisons.append(row)
        gkey = (str(plot_id), dev_id, ts_dt.date().isoformat())
        grouped_device_days.setdefault(gkey, []).append(row)

    # Collapse repeated timestamps on the same day into statistically independent (plot, device, date_utc) pairs
    independent_rows: List[Dict[str, Any]] = []
    for (_, dev_id, day_iso), grp in sorted(grouped_device_days.items()):
        obs_mean = float(np.mean([r["observed_vwc"] for r in grp]))
        pred_mean = float(grp[0]["asmae_rzw_mean"])
        pred_sig = float(grp[0]["asmae_rzw_sigma"])
        err_i = pred_mean - obs_mean
        z_i = abs(err_i) / max(0.01, pred_sig)
        independent_rows.append({
            "date_utc": day_iso,
            "device_id": dev_id,
            "vendor": grp[0]["vendor"],
            "raw_polls_collapsed": len(grp),
            "depth_zone": grp[0]["depth_zone"],
            "is_calibrated": all(r["is_calibrated"] for r in grp),
            "calibration_status": grp[0]["calibration_status"],
            "spatial_lookup_mode": grp[0]["spatial_lookup_mode"],
            "is_causal_lookup": all(r["is_causal_lookup"] for r in grp),
            "observed_vwc": round(obs_mean, 5),
            "asmae_rzw_mean": round(pred_mean, 5),
            "asmae_rzw_sigma": round(pred_sig, 5),
            "error": round(err_i, 5),
            "abs_z": round(z_i, 3),
            "within_2sigma": bool(z_i <= 2.0),
            "scene_gap_days": round(float(np.mean([r["scene_gap_days"] for r in grp])), 2),
        })

    cal_indep = [r for r in independent_rows if r["is_calibrated"]]
    uncal_indep = [r for r in independent_rows if not r["is_calibrated"]]

    def _agg_subset(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        if not rows:
            return {"n_independent_device_days": 0, "rmse_vwc": None, "mae_vwc": None, "bias_vwc": None, "coverage_2sigma": None}
        e_arr = np.asarray([r["error"] for r in rows], dtype=float)
        return {
            "n_independent_device_days": len(rows),
            "n_independent_devices": len({r["device_id"] for r in rows}),
            "n_independent_days": len({r["date_utc"] for r in rows}),
            "rmse_vwc": round(float(np.sqrt(np.mean(e_arr ** 2))), 5),
            "mae_vwc": round(float(np.mean(np.abs(e_arr))), 5),
            "bias_vwc": round(float(np.mean(e_arr)), 5),
            "coverage_2sigma": round(float(np.mean([1.0 if r["within_2sigma"] else 0.0 for r in rows])), 4),
        }

    # Aggregate VWC metrics deduplicated into independent (plot_id, device_id, date_utc) pairs
    if vwc_comparisons and independent_rows:
        indep_errs = np.asarray([c["error"] for c in independent_rows], dtype=float)
        n_indep_dev = len({r["device_id"] for r in independent_rows})
        n_indep_days = len({r["date_utc"] for r in independent_rows})
        indep_rmse = round(float(np.sqrt(np.mean(indep_errs ** 2))), 5)
        indep_mae = round(float(np.mean(np.abs(indep_errs))), 5)
        indep_bias = round(float(np.mean(indep_errs)), 5)
        indep_cov2 = round(float(np.mean([1.0 if c["within_2sigma"] else 0.0 for c in independent_rows])), 4)
        raw_errs = np.asarray([c["error"] for c in vwc_comparisons], dtype=float)
        vwc_summary = {
            "n_readings": len(independent_rows),
            "raw_readings_matched": len(vwc_comparisons),
            "n_independent_devices": n_indep_dev,
            "n_independent_days": n_indep_days,
            "n_independent_device_days": len(independent_rows),
            "rmse_vwc": indep_rmse,
            "mae_vwc": indep_mae,
            "bias_vwc": indep_bias,
            "coverage_2sigma": indep_cov2,
            "independent_rmse_vwc": indep_rmse,
            "independent_mae_vwc": indep_mae,
            "independent_bias_vwc": indep_bias,
            "independent_coverage_2sigma": indep_cov2,
            "raw_uncollapsed_rmse_vwc": round(float(np.sqrt(np.mean(raw_errs ** 2))), 5),
            "causal_only_enforced": bool(enforce_causal_pre_reading),
            "excluded_post_reading_non_causal": excluded_post_reading_non_causal,
            "excluded_surface_depth_count": excluded_surface_depth_count,
            "excluded_deep_depth_count": excluded_deep_depth_count,
            "unspecified_depth_count": unspecified_depth_count,
            "depth_breakdown": depth_breakdown,
            "excluded_out_of_plot_count": excluded_out_of_plot_count,
            "spatial_pixel_matched_count": spatial_pixel_matched_count,
            "plot_mean_fallback_count": plot_mean_fallback_count,
            "uncalibrated_or_outlier_count": uncalibrated_or_outlier_count,
            "calibrated_only_validation": _agg_subset(cal_indep),
            "uncalibrated_reported_validation": _agg_subset(uncal_indep),
            "skipped_mock_or_simulator": skipped_mock_count,
            "post_reading_reference": post_reading_refs,
            "independent_sample_records": independent_rows[:5],
            "sample_records": vwc_comparisons[:5],
            "deduplication_note": (
                f"Collapsed {len(vwc_comparisons)} probe timestamps into {len(independent_rows)} statistically independent (plot, device, date_utc) pairs ({n_indep_dev} devices across {n_indep_days} days)."
            ),
        }
    else:
        vwc_summary = {
            "n_readings": 0,
            "raw_readings_matched": 0,
            "n_independent_devices": 0,
            "n_independent_days": 0,
            "n_independent_device_days": 0,
            "causal_only_enforced": bool(enforce_causal_pre_reading),
            "excluded_post_reading_non_causal": excluded_post_reading_non_causal,
            "excluded_surface_depth_count": excluded_surface_depth_count,
            "excluded_deep_depth_count": excluded_deep_depth_count,
            "excluded_out_of_plot_count": excluded_out_of_plot_count,
            "skipped_mock_or_simulator": skipped_mock_count,
            "post_reading_reference": post_reading_refs,
            "note": (
                f"No causal pre-reading overlapping real soil moisture sensor timestamps within {int(max_scene_gap_days)} days before reading"
                + (f" ({excluded_post_reading_non_causal} post-reading excluded for causality)." if excluded_post_reading_non_causal else ".")
            ),
        }

    # 2. MESIA multi-strata hydrological comparison via MesiaLayer3WaterBridge (strict causal pre-reading lookup)
    mesia_results: List[Dict[str, Any]] = []
    for m_pkt in mesia_packets or []:
        raw_ts = m_pkt.get("timestamp")
        if not raw_ts:
            continue
        ts_dt = _parse_dt(raw_ts)
        pre_match, _ = _causal_asmae_state(ts_dt, max_gap_days=max_scene_gap_days)
        if pre_match is None:
            continue
        _, st = pre_match
        rzw_mu = float((st.get("posterior_state_means") or {}).get("root_zone_water", 0.25))
        stratum = LatticeStrata.ROOT_ZONE_5_30CM
        lik = BehaviourLikelihood(
            likelihood_id=str(m_pkt.get("likelihood_id") or f"mesia_{plot_id}_{ts_dt.date().isoformat()}"),
            radio_family=str(m_pkt.get("radio_family") or "LORA_RANGING"),
            contract_ref=str(m_pkt.get("contract_ref") or "contract_soil_moisture_v1"),
            target_variable="root_zone_water",
            likelihood_value=float(m_pkt.get("likelihood_value", 0.25)),
        )
        cmp_res = MesiaLayer3WaterBridge.compare_with_hydrological_model(
            plot_id=plot_id,
            stratum=stratum,
            mesia_likelihood=lik,
            layer3_model_vwc=rzw_mu,
            tolerance_vwc=0.06,
            calibrated_vwc=m_pkt.get("calibrated_vwc"),
        )
        mesia_results.append({
            "timestamp": ts_dt.isoformat(),
            "comparison_mode": cmp_res.comparison_mode,
            "is_calibrated_physical_observation": cmp_res.is_calibrated_physical_observation,
            "is_likelihood_consistency_proxy": cmp_res.is_likelihood_consistency_proxy,
            "mesia_vwc_or_proxy": round(float(cmp_res.mesia_observed_vwc), 5),
            "asmae_model_vwc": round(float(cmp_res.model_predicted_vwc), 5),
            "residual_error_vwc": round(float(cmp_res.residual_error_vwc), 5),
            "is_hydrologically_consistent": bool(cmp_res.is_hydrologically_consistent),
        })

    # 3. Scouting (CropObservation) honesty audit vs ASMAE satellite attribution (causal pre-reading)
    scouting_audits: List[Dict[str, Any]] = []
    for obs in crop_observations or []:
        raw_ts = obs.get("createdAt") or obs.get("timestamp")
        if not raw_ts:
            continue
        ts_dt = _parse_dt(raw_ts)
        pre_match, _ = _causal_asmae_state(ts_dt, max_gap_days=max_scene_gap_days)
        if pre_match is None:
            continue
        gap_d, st = pre_match
        means = st.get("posterior_state_means") or {}
        cl_ref = st.get("cross_layer_refined") or {}
        l5 = (cl_ref.get("layers_refined") or {}).get("layer5_biotic") or {}
        scouting_audits.append({
            "timestamp": ts_dt.isoformat(),
            "obs_type": str(obs.get("type") or ""),
            "title": str(obs.get("title") or ""),
            "scene_gap_days": round(gap_d, 2),
            "asmae_vigor": round(float(means.get("vigor", 0.0)), 4),
            "asmae_stress_memory": round(float(means.get("stress_memory", 0.0)), 4),
            "l5_biotic_threat": l5.get("top_threat_hypothesis"),
            "diagnostic_note": "Satellite optical/SAR cannot independently isolate pest/compaction etiology without field scouting.",
        })

    # 4. CropTask verification: strictly segregate unconfirmed planned tasks vs completed/applied management
    applied_tasks = []
    planned_unconfirmed_tasks = []
    for tk in crop_tasks or []:
        is_completed = bool(tk.get("completed")) or str(tk.get("status") or "").upper() in ("COMPLETED", "APPLIED", "OBSERVED_CONFIRMED")
        rec = {
            "type": str(tk.get("type") or ""),
            "title": str(tk.get("title") or ""),
            "dueDate": str(tk.get("dueDate") or "")[:10],
            "completed": is_completed,
        }
        if is_completed:
            applied_tasks.append(rec)
        else:
            planned_unconfirmed_tasks.append(rec)

    # 5. SoilAnalysis inventory
    valid_soils = [
        {
            "date": str(s.get("date") or "")[:10],
            "texture": s.get("texture"),
            "ph": s.get("ph"),
            "ec": s.get("ec"),
            "organicMatter": s.get("organicMatter"),
            "nitrogen": s.get("nitrogen"),
        }
        for s in soil_analyses or []
        if any(s.get(k) is not None for k in ("texture", "ph", "ec", "organicMatter", "nitrogen"))
    ]

    return {
        "plot_id": plot_id,
        "zero_circularity_enforced": True,
        "sensor_vwc_validation": vwc_summary,
        "mesia_hydrological_validation": {
            "n_evaluated": len(mesia_results),
            "native_sigmf_captures_present": False,
            "evaluations": mesia_results,
        },
        "soil_analyses": valid_soils,
        "scouting_records_audited": len(scouting_audits),
        "scouting_sample": scouting_audits[:5],
        "crop_tasks_summary": {
            "applied_or_completed_count": len(applied_tasks),
            "unconfirmed_planned_ignored_count": len(planned_unconfirmed_tasks),
            "unconfirmed_planned_sample": planned_unconfirmed_tasks[:5],
        },
    }
