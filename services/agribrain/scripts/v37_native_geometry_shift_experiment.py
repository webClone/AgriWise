#!/usr/bin/env python3
"""
V37 — Native / Controlled Geometry Shift Experiment

Implements:
- V37A: controlled shifted-grid + buffered registration
- V37B: natural scene geometry evidence diagnostics
- V37C: controlled H_t reconstruction holdout

Run from services/agribrain:
  PYTHONPATH=. python scripts/v37_native_geometry_shift_experiment.py --max-cloud 100
  PYTHONPATH=. python scripts/v37_native_geometry_shift_experiment.py --dry-run
"""

from __future__ import annotations

import argparse, io, json, math, tarfile, traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
    load_dotenv(".env.local", override=True)
except Exception:
    pass

DEFAULT_POLYGON = [[
    [6.86000, 33.34800],
    [6.86300, 33.34800],
    [6.86300, 33.35100],
    [6.86000, 33.35100],
    [6.86000, 33.34800],
]]
DEFAULT_LAT = 33.3495
DEFAULT_LNG = 6.8615
DEFAULT_PLOT_ID = "v37_real_polygon_el_oued"
DEFAULT_EPSG_UTM = "EPSG:32632"

CONTROLLED_OFFSETS_M = [
    (0.0, 0.0), (1.0, 0.0), (0.0, 1.0),
    (1.0, 1.0), (2.0, 3.0), (-2.0, 1.0),
]


@dataclass
class ControlledGrid:
    label: str
    requested_east_m: float
    requested_north_m: float
    expected_dx_px: float
    expected_dy_px: float
    arrays: Dict[str, np.ndarray]
    valid_registration_mask: np.ndarray
    estimated_dx_px: Optional[float] = None
    estimated_dy_px: Optional[float] = None
    estimated_confidence: Optional[float] = None
    shift_error_m: Optional[float] = None


def safe_float(x: Any, default: float = float("nan")) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def bbox_from_polygon(polygon_coords: Any) -> List[float]:
    pts = polygon_coords[0]
    xs = [float(p[0]) for p in pts]
    ys = [float(p[1]) for p in pts]
    return [min(xs), min(ys), max(xs), max(ys)]


def degree_expand_shift_bbox(bbox: List[float], buffer_m: float, dx_m: float, dy_m: float, lat_hint: float) -> List[float]:
    lon_min, lat_min, lon_max, lat_max = bbox
    meters_per_deg_lat = 111320.0
    meters_per_deg_lon = 111320.0 * max(0.2, math.cos(math.radians(lat_hint)))
    return [
        lon_min - buffer_m/meters_per_deg_lon + dx_m/meters_per_deg_lon,
        lat_min - buffer_m/meters_per_deg_lat + dy_m/meters_per_deg_lat,
        lon_max + buffer_m/meters_per_deg_lon + dx_m/meters_per_deg_lon,
        lat_max + buffer_m/meters_per_deg_lat + dy_m/meters_per_deg_lat,
    ]


def utm_expand_shift_bbox(polygon_coords: Any, buffer_m: float, dx_m: float, dy_m: float, epsg_utm: str = DEFAULT_EPSG_UTM) -> Tuple[List[float], str]:
    bbox = bbox_from_polygon(polygon_coords)
    lat_hint = (bbox[1] + bbox[3]) / 2.0
    try:
        from shapely.geometry import Polygon
        from shapely.ops import transform
        from shapely import affinity
        from pyproj import Transformer
        poly = Polygon(polygon_coords[0])
        to_utm = Transformer.from_crs("EPSG:4326", epsg_utm, always_xy=True).transform
        to_wgs = Transformer.from_crs(epsg_utm, "EPSG:4326", always_xy=True).transform
        shifted = affinity.translate(transform(to_utm, poly).buffer(buffer_m), xoff=dx_m, yoff=dy_m)
        return list(transform(to_wgs, shifted).bounds), "utm"
    except Exception:
        return degree_expand_shift_bbox(bbox, buffer_m, dx_m, dy_m, lat_hint), "degree_fallback"


def simple_blur(a: np.ndarray, passes: int = 2) -> np.ndarray:
    out = a.astype(float).copy()
    fill = np.nanmean(out) if np.isfinite(out).any() else 0.0
    out = np.where(np.isfinite(out), out, fill)
    for _ in range(max(0, passes)):
        out = (out + np.roll(out,1,0) + np.roll(out,-1,0) + np.roll(out,1,1) + np.roll(out,-1,1)) / 5.0
    return out


def sobel_like_edge(a: np.ndarray) -> np.ndarray:
    fill = np.nanmean(a) if np.isfinite(a).any() else 0.0
    x = np.where(np.isfinite(a), a, fill)
    gx = (np.roll(x, -1, 1) - np.roll(x, 1, 1)) / 2.0
    gy = (np.roll(x, -1, 0) - np.roll(x, 1, 0)) / 2.0
    return np.sqrt(gx*gx + gy*gy)


def dilate_binary(mask: np.ndarray, radius: int = 2) -> np.ndarray:
    out = mask.astype(bool).copy()
    base = out.copy()
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx*dx + dy*dy <= radius*radius:
                out |= np.roll(np.roll(base, dy, axis=0), dx, axis=1)
    return out


def shift_integer(a: np.ndarray, dy: float, dx: float) -> np.ndarray:
    return np.roll(np.roll(a, int(round(dy)), axis=0), int(round(dx)), axis=1)


def mse_valid(a: np.ndarray, b: np.ndarray, valid: Optional[np.ndarray] = None) -> Optional[float]:
    m = np.isfinite(a) & np.isfinite(b)
    if valid is not None:
        m &= valid
    if int(m.sum()) < 8:
        return None
    return float(np.nanmean((a[m] - b[m]) ** 2))


def r2_score(x: List[float], y: List[float]) -> Optional[float]:
    if len(x) < 3:
        return None
    xx, yy = np.array(x, dtype=float), np.array(y, dtype=float)
    ss_res = float(np.sum((yy - xx) ** 2))
    ss_tot = float(np.sum((yy - np.mean(yy)) ** 2))
    return None if ss_tot <= 1e-12 else 1.0 - ss_res / ss_tot


def linear_slope(x: List[float], y: List[float]) -> Optional[float]:
    if len(x) < 3:
        return None
    xx, yy = np.array(x, dtype=float), np.array(y, dtype=float)
    denom = float(np.sum((xx - np.mean(xx)) ** 2))
    return None if denom <= 1e-12 else float(np.sum((xx - np.mean(xx)) * (yy - np.mean(yy))) / denom)


def build_registration_surface(arrays: Dict[str, np.ndarray]) -> np.ndarray:
    b04, b08, b11 = arrays["b04"], arrays["b08"], arrays["b11"]
    bare_soil_proxy = b11 - 0.35*b08 + 0.15*b04
    edge_mag = np.sqrt(sobel_like_edge(b04)**2 + sobel_like_edge(b08)**2 + sobel_like_edge(b11)**2)
    layers = []
    for z in [b04, b08, b11, bare_soil_proxy, edge_mag]:
        med, q1, q9 = np.nanmedian(z), np.nanpercentile(z, 20), np.nanpercentile(z, 80)
        layers.append((z - med) / max(1e-6, q9 - q1))
    return np.nanmean(np.stack(layers, axis=0), axis=0)


def estimate_shift_bruteforce(reference: np.ndarray, target: np.ndarray, valid: np.ndarray, search_radius_px: int = 2) -> Tuple[float, float, float]:
    ref = np.where(np.isfinite(reference), reference, np.nanmean(reference))
    tar = np.where(np.isfinite(target), target, np.nanmean(target))
    ref, tar = ref - np.nanmean(ref), tar - np.nanmean(tar)
    best_score, best_dx, best_dy = -1e30, 0, 0
    scores = []
    for dy in range(-search_radius_px, search_radius_px + 1):
        for dx in range(-search_radius_px, search_radius_px + 1):
            shifted = shift_integer(tar, dy, dx)
            m = valid & np.isfinite(ref) & np.isfinite(shifted)
            if int(m.sum()) < 20:
                continue
            score = float(np.nanmean(ref[m] * shifted[m]))
            scores.append(score)
            if score > best_score:
                best_score, best_dx, best_dy = score, dx, dy
    if not scores:
        return 0.0, 0.0, 0.0
    scores = sorted(scores, reverse=True)
    conf = 0.0 if len(scores) < 2 else (scores[0] - scores[1]) / (abs(scores[0]) + 1e-9)
    return float(best_dx), float(best_dy), float(max(0.0, min(1.0, conf * 5.0)))


def _parse_tar_to_arrays(content: bytes) -> Dict[str, np.ndarray]:
    try:
        import tifffile
    except Exception as e:
        raise RuntimeError("tifffile is required: pip install tifffile") from e
    out = {}
    with tarfile.open(fileobj=io.BytesIO(content)) as tar:
        for member in tar.getmembers():
            if not member.isfile() or not member.name.lower().endswith((".tif", ".tiff")):
                continue
            f = tar.extractfile(member)
            if f is None:
                continue
            with tifffile.TiffFile(io.BytesIO(f.read())) as tif:
                out[Path(member.name).stem.lower()] = tif.asarray().astype(float)
    return out


def fetch_controlled_grid(date: str, bbox_wgs84: List[float], width: int, height: int, timeout: int = 45) -> Dict[str, np.ndarray]:
    import requests
    from eo.sentinel import get_access_token, SENTINEL_PROCESS_URL
    lon_min, lat_min, lon_max, lat_max = bbox_wgs84
    evalscript = """
    //VERSION=3
    function setup() {
      return {
        input: [{bands:["B04","B08","B11","SCL","dataMask"]}],
        output: [
          {id:"b04", bands:1, sampleType:"FLOAT32"},
          {id:"b08", bands:1, sampleType:"FLOAT32"},
          {id:"b11", bands:1, sampleType:"FLOAT32"},
          {id:"ndvi", bands:1, sampleType:"FLOAT32"},
          {id:"ndmi", bands:1, sampleType:"FLOAT32"},
          {id:"valid", bands:1, sampleType:"UINT8"},
          {id:"cloud", bands:1, sampleType:"UINT8"}
        ]
      };
    }
    function evaluatePixel(s) {
      var scl = s.SCL;
      var cloud = (scl == 3 || scl == 8 || scl == 9 || scl == 10 || scl == 11);
      var valid = (s.dataMask == 1 && !cloud && (scl == 4 || scl == 5 || scl == 6));
      var ndviDen = s.B08 + s.B04;
      var ndmiDen = s.B08 + s.B11;
      var ndvi = ndviDen > 0 ? (s.B08 - s.B04) / ndviDen : -9999;
      var ndmi = ndmiDen > 0 ? (s.B08 - s.B11) / ndmiDen : -9999;
      if (s.dataMask != 1) return {b04:[-9999], b08:[-9999], b11:[-9999], ndvi:[-9999], ndmi:[-9999], valid:[0], cloud:[1]};
      return {b04:[s.B04], b08:[s.B08], b11:[s.B11], ndvi:[ndvi], ndmi:[ndmi], valid:[valid ? 1 : 0], cloud:[cloud ? 1 : 0]};
    }
    """
    payload = {
        "input": {
            "bounds": {"bbox": [lon_min, lat_min, lon_max, lat_max], "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}},
            "data": [{
                "type": "sentinel-2-l2a",
                "dataFilter": {"mosaickingOrder": "leastCC"},
                "timeRange": {"from": f"{date}T00:00:00Z", "to": f"{date}T23:59:59Z"},
            }],
        },
        "output": {
            "width": width, "height": height,
            "responses": [
                {"identifier": k, "format": {"type": "image/tiff"}}
                for k in ["b04", "b08", "b11", "ndvi", "ndmi", "valid", "cloud"]
            ],
        },
        "evalscript": evalscript,
    }
    headers = {"Authorization": f"Bearer {get_access_token()}", "Content-Type": "application/json", "Accept": "application/tar"}
    resp = requests.post(SENTINEL_PROCESS_URL, json=payload, headers=headers, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"Process API failed for {date}: HTTP {resp.status_code}: {resp.text[:400]}")
    arrays = _parse_tar_to_arrays(resp.content)
    for k in ["b04", "b08", "b11", "ndvi", "ndmi"]:
        arrays[k] = np.where(arrays[k] <= -9000, np.nan, arrays[k])
    arrays["valid"] = arrays["valid"] > 0
    arrays["cloud"] = arrays["cloud"] > 0
    return arrays


def select_best_date(lat: float, lng: float, polygon: Any, days: int, max_cloud: float) -> Optional[str]:
    from eo.sentinel import fetch_ndvi_timeseries
    ts = fetch_ndvi_timeseries(lat, lng, days=days, polygon_coords=polygon)
    data = ts.get("data", []) if isinstance(ts, dict) else []
    candidates = []
    for row in data:
        date, ndvi, cloud = row.get("date"), safe_float(row.get("ndvi")), safe_float(row.get("cloud_cover"), 100.0)
        if date and np.isfinite(ndvi) and cloud <= max_cloud:
            score = (1.0 - cloud/100.0) * (0.4 + min(0.6, max(0.0, ndvi)))
            candidates.append((score, date))
    candidates.sort(reverse=True)
    return candidates[0][1] if candidates else None


def compute_expected_shift_px(dx_m: float, dy_m: float, gsd_m: float) -> Tuple[float, float]:
    return -dx_m / gsd_m, dy_m / gsd_m


def make_dry_run_controlled_grids(offsets_m: List[Tuple[float, float]], gsd_m: float, width: int = 80, height: int = 80) -> List[ControlledGrid]:
    rng = np.random.default_rng(37)
    y, x = np.mgrid[0:height, 0:width]
    b04 = 0.18 + 0.04*np.sin(x/4.7) + 0.03*np.cos(y/6.2)
    b08 = 0.42 + 0.08*np.sin((x+y)/8.0) - 0.05*np.exp(-((x-47)**2 + (y-30)**2)/160)
    b11 = 0.27 + 0.05*np.cos(x/7.0) + 0.03*np.sin(y/5.0)
    b04[:, 30:33] += 0.07; b08[:, 30:33] -= 0.05; b11[:, 30:33] += 0.04
    base = {"b04": b04, "b08": b08, "b11": b11}
    base["ndvi"] = (b08 - b04) / np.maximum(b08 + b04, 1e-6)
    base["ndmi"] = (b08 - b11) / np.maximum(b08 + b11, 1e-6)
    valid = np.ones((height, width), dtype=bool); cloud = np.zeros((height, width), dtype=bool)
    grids = []
    for dx_m, dy_m in offsets_m:
        ex_dx, ex_dy = compute_expected_shift_px(dx_m, dy_m, gsd_m)
        arrays = {k: shift_integer(v, ex_dy, ex_dx) + rng.normal(0, 0.0015, v.shape) for k, v in base.items()}
        arrays["valid"] = valid.copy(); arrays["cloud"] = cloud.copy()
        grids.append(ControlledGrid(f"dry_east_{dx_m:+.1f}m_north_{dy_m:+.1f}m", dx_m, dy_m, ex_dx, ex_dy, arrays, valid.copy()))
    return grids


def run_controlled_grid_experiment(date: str, polygon: Any, buffer_m: float, gsd_m: float, offsets_m: List[Tuple[float, float]], width: int, height: int, dry_run: bool = False) -> Dict[str, Any]:
    grids, method_used = [], None
    if dry_run:
        grids, method_used = make_dry_run_controlled_grids(offsets_m, gsd_m), "dry_run_synthetic"
    else:
        for dx_m, dy_m in offsets_m:
            bbox_shifted, method = utm_expand_shift_bbox(polygon, buffer_m, dx_m, dy_m)
            method_used = method_used or method
            arrays = fetch_controlled_grid(date, bbox_shifted, width=width, height=height)
            cloud_adj = dilate_binary(arrays["cloud"].astype(bool), radius=2)
            valid_reg = arrays["valid"].astype(bool) & (~cloud_adj)
            ex_dx, ex_dy = compute_expected_shift_px(dx_m, dy_m, gsd_m)
            grids.append(ControlledGrid(f"east_{dx_m:+.1f}m_north_{dy_m:+.1f}m", dx_m, dy_m, ex_dx, ex_dy, arrays, valid_reg))
    ref = min(grids, key=lambda g: abs(g.requested_east_m) + abs(g.requested_north_m))
    ref_surface = build_registration_surface(ref.arrays)
    results = []
    for g in grids:
        target_surface = build_registration_surface(g.arrays)
        valid = ref.valid_registration_mask & g.valid_registration_mask
        est_dx, est_dy, conf = estimate_shift_bruteforce(ref_surface, target_surface, valid)
        g.estimated_dx_px, g.estimated_dy_px, g.estimated_confidence = est_dx, est_dy, conf
        err_px = math.sqrt((est_dx - g.expected_dx_px)**2 + (est_dy - g.expected_dy_px)**2)
        g.shift_error_m = err_px * gsd_m
        results.append({
            "label": g.label,
            "requested_shift_m": {"east": g.requested_east_m, "north": g.requested_north_m},
            "expected_shift_px": {"dx_col": g.expected_dx_px, "dy_row": g.expected_dy_px},
            "estimated_shift_px": {"dx_col": est_dx, "dy_row": est_dy},
            "shift_error_m": g.shift_error_m,
            "confidence": conf,
            "valid_registration_fraction": float(np.mean(g.valid_registration_mask)),
        })
    nonzero = [r for r in results if abs(r["requested_shift_m"]["east"]) + abs(r["requested_shift_m"]["north"]) > 1e-9]
    rmse = float(math.sqrt(np.mean([r["shift_error_m"]**2 for r in nonzero]))) if nonzero else None
    med_conf = float(np.median([r["confidence"] for r in nonzero])) if nonzero else None
    requested_mag = [math.sqrt(r["expected_shift_px"]["dx_col"]**2 + r["expected_shift_px"]["dy_row"]**2) for r in nonzero]
    estimated_mag = [math.sqrt(r["estimated_shift_px"]["dx_col"]**2 + r["estimated_shift_px"]["dy_row"]**2) for r in nonzero]
    return {
        "date": date, "bbox_transform_method": method_used, "gsd_m": gsd_m, "buffer_m": buffer_m,
        "controlled_shift_tests": results,
        "controlled_shift_rmse_m": rmse,
        "grid_offset_r2": r2_score(requested_mag, estimated_mag),
        "grid_offset_slope": linear_slope(requested_mag, estimated_mag),
        "median_shift_confidence": med_conf,
        "grids_object": grids,
    }


def run_h_operator_holdout(controlled_result: Dict[str, Any], factor: int = 10) -> Dict[str, Any]:
    grids: List[ControlledGrid] = controlled_result["grids_object"]
    if len(grids) < 4:
        return {"status": "insufficient_grids"}
    holdout = max(grids, key=lambda g: abs(g.requested_east_m) + abs(g.requested_north_m))
    train = [g for g in grids if g is not holdout]
    h10, w10 = train[0].arrays["ndvi"].shape
    h1, w1 = h10*factor, w10*factor
    def up(a): return np.repeat(np.repeat(a, factor, axis=0), factor, axis=1)
    def down(a): return np.nanmean(a[:h1, :w1].reshape(h10, factor, w10, factor), axis=(1, 3))
    acc = np.zeros((h1, w1)); wt = np.zeros((h1, w1))
    for g in train:
        src = np.where(g.arrays["valid"], g.arrays["ndvi"], np.nan)
        u = up(src); v = up(g.arrays["valid"].astype(float)) > 0.5
        dx1 = (g.estimated_dx_px or 0.0) * factor; dy1 = (g.estimated_dy_px or 0.0) * factor
        back = shift_integer(u, -dy1, -dx1); bv = shift_integer(v.astype(float), -dy1, -dx1) > 0.5
        q = max(0.05, g.estimated_confidence or 0.2)
        acc += np.where(bv & np.isfinite(back), back*q, 0); wt += np.where(bv & np.isfinite(back), q, 0)
    fill = np.nanmean(acc[wt > 0] / np.maximum(wt[wt > 0], 1e-9)) if np.any(wt > 0) else 0.4
    latent = np.divide(acc, np.maximum(wt, 1e-9)); latent[wt <= 0] = fill
    latent_ht = simple_blur(latent, 2) + 0.35*(latent - simple_blur(latent, 2))
    hx = (holdout.estimated_dx_px or 0.0) * factor; hy = (holdout.estimated_dy_px or 0.0) * factor
    pred_ht = down(shift_integer(latent_ht, hy, hx))
    # no-shift baseline
    acc0 = np.zeros((h1, w1)); wt0 = np.zeros((h1, w1))
    for g in train:
        src = np.where(g.arrays["valid"], g.arrays["ndvi"], np.nan)
        u = up(src); v = up(g.arrays["valid"].astype(float)) > 0.5
        acc0 += np.where(v & np.isfinite(u), u, 0); wt0 += np.where(v & np.isfinite(u), 1, 0)
    latent0 = np.divide(acc0, np.maximum(wt0, 1e-9)); latent0[wt0 <= 0] = fill
    pred0 = down(simple_blur(latent0, 2))
    obs = np.where(holdout.arrays["valid"], holdout.arrays["ndvi"], np.nan)
    mse_ht = mse_valid(pred_ht, obs, holdout.arrays["valid"])
    mse_no = mse_valid(pred0, obs, holdout.arrays["valid"])
    improvement = None if (mse_ht is None or mse_no is None or mse_no <= 0) else (mse_no - mse_ht) / mse_no
    return {
        "status": "completed", "holdout_grid": holdout.label,
        "h_operator_holdout_mse": mse_ht, "no_shift_holdout_mse": mse_no,
        "global_holdout_improvement_fraction": improvement,
        "global_holdout_improvement_pct": None if improvement is None else improvement*100,
    }


def run_catalog_metadata_probe(dry_run: bool = False) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry_run", "catalog_used": False, "natural_scene_shift_observable": False, "reason": "Dry run does not query CDSE Catalog."}
    return {
        "status": "not_yet_integrated",
        "catalog_used": False,
        "exact_scene_ids_available": False,
        "relative_orbit_available": False,
        "mgrs_tile_available": False,
        "sun_view_geometry_available": False,
        "natural_scene_shift_observable": False,
        "reason": "V37A validates controlled shifted grids. V37B requires explicit CDSE Catalog/STAC item metadata integration.",
    }


def evaluate_acceptance(controlled: Dict[str, Any], htest: Dict[str, Any]) -> Dict[str, Any]:
    rmse, r2, slope, conf = controlled.get("controlled_shift_rmse_m"), controlled.get("grid_offset_r2"), controlled.get("grid_offset_slope"), controlled.get("median_shift_confidence")
    h_impr = htest.get("global_holdout_improvement_fraction") if isinstance(htest, dict) else None
    controlled_ok = rmse is not None and rmse <= 1.0 and r2 is not None and r2 >= 0.85 and slope is not None and 0.75 <= slope <= 1.25 and conf is not None and conf >= 0.70
    h_ok = h_impr is not None and h_impr >= 0.03
    natural_ok = False
    allow = bool(controlled_ok and h_ok and natural_ok)
    if allow:
        reason = "Controlled shift, H_t holdout, and natural shift evidence all validated."
    elif controlled_ok and h_ok:
        reason = "Controlled shift and H_t validated, but natural scene shift is not yet validated."
    elif controlled_ok:
        reason = "Controlled shift recovered, but H_t holdout did not pass threshold."
    else:
        reason = "Controlled shift recovery did not pass strict thresholds."
    return {
        "controlled_shift_recovered": controlled_ok,
        "h_operator_validated": h_ok,
        "natural_shift_validated": natural_ok,
        "allow_strong_1m_export": allow,
        "fallback_resolution_policy": "2m_to_10m_dynamic" if not allow else "local_1m_candidates_allowed",
        "reason": reason,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plot-id", default=DEFAULT_PLOT_ID)
    ap.add_argument("--lat", type=float, default=DEFAULT_LAT)
    ap.add_argument("--lng", type=float, default=DEFAULT_LNG)
    ap.add_argument("--days", type=int, default=1800)
    ap.add_argument("--max-cloud", type=float, default=65.0)
    ap.add_argument("--date", default=None)
    ap.add_argument("--buffer-m", type=float, default=200.0)
    ap.add_argument("--gsd-m", type=float, default=10.0)
    ap.add_argument("--width", type=int, default=128)
    ap.add_argument("--height", type=int, default=128)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default="artifacts/v37_native_geometry_shift_experiment_report.json")
    args = ap.parse_args()
    report = {
        "version": "V37_native_controlled_geometry_shift_experiment",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plot_id": args.plot_id,
        "mode": "dry_run_synthetic" if args.dry_run else "real_sentinel_process_api",
        "science_position": {
            "controlled_shift_validates": "registration math and H_t behavior under known grid perturbations",
            "controlled_shift_does_not_validate": "natural satellite orbital drift",
            "strong_1m_product_claim_requires": "natural scene geometry evidence or independently observable residual shifts",
        },
        "sign_convention": {
            "dx_col_positive": "target image must move east/right in columns to align to reference",
            "dy_row_positive": "target image must move south/down in raster rows to align to reference",
            "expected_dx_pixel": "-east_shift_m / GSD",
            "expected_dy_pixel": "north_shift_m / GSD",
        },
        "thresholds": {
            "controlled_shift_rmse_m_max": 1.0,
            "grid_offset_r2_min": 0.85,
            "grid_offset_slope_range": [0.75, 1.25],
            "median_shift_confidence_min": 0.70,
            "global_holdout_mse_improvement_min": 0.03,
            "local_residual_mse_improvement_min": 0.05,
        },
    }
    try:
        date = args.date
        if not args.dry_run and not date:
            date = select_best_date(args.lat, args.lng, DEFAULT_POLYGON, args.days, args.max_cloud)
        if args.dry_run:
            date = date or "2025-05-01"
        if not date:
            raise RuntimeError("No suitable Sentinel-2 date found. Try --max-cloud 100 or specify --date YYYY-MM-DD.")
        report["selected_date"] = date
        controlled = run_controlled_grid_experiment(date, DEFAULT_POLYGON, args.buffer_m, args.gsd_m, CONTROLLED_OFFSETS_M, args.width, args.height, args.dry_run)
        htest = run_h_operator_holdout(controlled)
        catalog = run_catalog_metadata_probe(args.dry_run)
        controlled_clean = {k: v for k, v in controlled.items() if k != "grids_object"}
        report["v37a_controlled_grid_shift"] = controlled_clean
        report["v37b_natural_scene_geometry_evidence"] = catalog
        report["v37c_h_operator_holdout"] = htest
        report["geometry_diagnostics"] = {
            "process_grid_is_fixed": True,
            "controlled_grid_shift_used": True,
            "natural_scene_shift_observable": bool(catalog.get("natural_scene_shift_observable", False)),
            "native_geometry_required_for_natural_shift": True,
        }
        report["acceptance"] = evaluate_acceptance(controlled_clean, htest)
        report["status"] = "completed"
    except Exception as e:
        report["status"] = "failed"
        report["error"] = {"type": type(e).__name__, "message": str(e)}
        report["traceback"] = traceback.format_exc()[-5000:]
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
