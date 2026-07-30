#!/usr/bin/env python3
"""
V36 — Real Sentinel Scene-Stack Shift-Selection Prototype

Purpose
-------
Run the first real-data version of the MicroZone shift-selection idea using the
existing AgriWise / AgriBrain EO stack.

This script:
1. Authenticates through the existing eo.sentinel module.
2. Uses real Sentinel-2 NDVI time-series to select candidate scene dates.
3. Fetches per-date Sentinel-2 raster stacks via the Sentinel Hub Process API.
4. Builds multiple geometry/shift candidates:
   - metadata/zero-shift baseline
   - global image-correlation shift
   - local tile-based shift
   - hybrid gated shift
5. Selects the shift model by internal held-out scene prediction.
6. Evaluates the selected model on final holdout scenes.
7. Generates a Layer 1 adapter preview:
   - value raster
   - uncertainty raster
   - resolution raster
   - retrovalidation score raster
   - selected shift model

Important scientific note
-------------------------
This is V36A: a real Sentinel Process-API prototype.

The current AgriWise EO functions request a fixed processing grid from Sentinel Hub.
That means this script can estimate *image residual displacement* between fetched
per-date rasters, but it still does not expose the raw native Sentinel granule
footprint/geotransform. Full V36B should add a true catalog/native-scene stack with
scene transform, relative orbit, tile id, view/sun geometry, and residual
co-registration metadata.

Run from services/agribrain:
    PYTHONPATH=. python scripts/v36_real_scene_stack_shift_selection.py

Optional:
    PYTHONPATH=. python scripts/v36_real_scene_stack_shift_selection.py --days 1800 --max-scenes 72
    PYTHONPATH=. python scripts/v36_real_scene_stack_shift_selection.py --dry-run
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import tarfile
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
    load_dotenv(".env.local", override=True)
except Exception:
    pass


# ---------------------------------------------------------------------
# Default real test polygon: El Oued / Oued Souf irrigated agriculture
# ---------------------------------------------------------------------

DEFAULT_POLYGON = [[
    [6.86000, 33.34800],
    [6.86300, 33.34800],
    [6.86300, 33.35100],
    [6.86000, 33.35100],
    [6.86000, 33.34800],
]]
DEFAULT_LAT = 33.3495
DEFAULT_LNG = 6.8615
DEFAULT_PLOT_ID = "v36_real_polygon_el_oued"


# ---------------------------------------------------------------------
# Small numerical helpers
# ---------------------------------------------------------------------

def safe_float(x: Any, default: float = float("nan")) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def nanmean_or_none(a: np.ndarray) -> Optional[float]:
    if a.size == 0 or not np.isfinite(a).any():
        return None
    return float(np.nanmean(a))


def simple_blur(a: np.ndarray, passes: int = 2) -> np.ndarray:
    """Dependency-light smoothing."""
    out = a.astype(float).copy()
    fill = np.nanmean(out) if np.isfinite(out).any() else 0.0
    out = np.where(np.isfinite(out), out, fill)
    for _ in range(max(0, passes)):
        out = (
            out
            + np.roll(out, 1, 0) + np.roll(out, -1, 0)
            + np.roll(out, 1, 1) + np.roll(out, -1, 1)
        ) / 5.0
    return out


def shift_image_integer(a: np.ndarray, dy: float, dx: float) -> np.ndarray:
    """Integer-pixel shift fallback. dx/dy are in 10 m pixels for scene rasters."""
    return np.roll(np.roll(a, int(round(dy)), axis=0), int(round(dx)), axis=1)


def upsample_10_to_1(a: np.ndarray, factor: int = 10) -> np.ndarray:
    return np.repeat(np.repeat(a, factor, axis=0), factor, axis=1)


def downsample_1_to_10(a: np.ndarray, h10: int, w10: int, factor: int = 10) -> np.ndarray:
    h1, w1 = h10 * factor, w10 * factor
    x = a[:h1, :w1]
    return np.nanmean(x.reshape(h10, factor, w10, factor), axis=(1, 3))


def mse_valid(a: np.ndarray, b: np.ndarray) -> Optional[float]:
    valid = np.isfinite(a) & np.isfinite(b)
    if int(valid.sum()) < 4:
        return None
    return float(np.nanmean((a[valid] - b[valid]) ** 2))


def estimate_shift_global(ref: np.ndarray, img: np.ndarray, mask: Optional[np.ndarray] = None) -> Tuple[float, float, float]:
    """
    Lightweight global shift estimator using brute-force integer correlation.
    Returns dx, dy in 10 m pixel units plus confidence.
    """
    if mask is None:
        mask = np.isfinite(ref) & np.isfinite(img)
    best = (-1e18, 0, 0)
    scores = []
    r0 = np.where(np.isfinite(ref), ref, np.nanmean(ref))
    i0 = np.where(np.isfinite(img), img, np.nanmean(img))
    r0 = r0 - np.nanmean(r0)
    i0 = i0 - np.nanmean(i0)

    for dy in range(-2, 3):
        for dx in range(-2, 3):
            shifted = shift_image_integer(i0, dy, dx)
            valid = mask & np.isfinite(shifted) & np.isfinite(r0)
            if int(valid.sum()) < 8:
                continue
            score = float(np.nanmean(r0[valid] * shifted[valid]))
            scores.append(score)
            if score > best[0]:
                best = (score, dx, dy)

    if not scores:
        return 0.0, 0.0, 0.0
    scores = sorted(scores, reverse=True)
    sharpness = (scores[0] - scores[1]) / (abs(scores[0]) + 1e-9) if len(scores) > 1 else 0.0
    conf = float(max(0.0, min(1.0, sharpness * 5.0)))
    return float(best[1]), float(best[2]), conf


def estimate_shift_local(ref: np.ndarray, img: np.ndarray, valid: np.ndarray, tile: int = 8) -> Tuple[float, float, float]:
    """
    Tile-based robust median shift from multiple local windows.
    Returns dx, dy in 10 m pixel units plus confidence.
    """
    h, w = ref.shape
    estimates = []
    confs = []
    for y0 in range(0, h, tile):
        for x0 in range(0, w, tile):
            sl = np.s_[y0:min(h, y0+tile), x0:min(w, x0+tile)]
            if int(np.isfinite(ref[sl]).sum()) < max(6, tile):
                continue
            if int(np.isfinite(img[sl]).sum()) < max(6, tile):
                continue
            if int(valid[sl].sum()) < max(6, tile):
                continue
            dx, dy, c = estimate_shift_global(ref[sl], img[sl], valid[sl])
            if c > 0.05:
                estimates.append((dx, dy))
                confs.append(c)
    if not estimates:
        return 0.0, 0.0, 0.0
    arr = np.array(estimates, dtype=float)
    dx = float(np.median(arr[:, 0]))
    dy = float(np.median(arr[:, 1]))
    spread = float(np.median(np.sqrt((arr[:,0]-dx)**2 + (arr[:,1]-dy)**2)))
    conf = float(max(0.0, min(1.0, np.mean(confs) * (1.0 / (1.0 + spread)))))
    return dx, dy, conf


# ---------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------

@dataclass
class V36Scene:
    date: str
    ndvi: np.ndarray
    ndmi: np.ndarray
    structure: np.ndarray
    valid: np.ndarray
    cloud_cover: float
    quality: float
    shifts: Dict[str, Tuple[float, float]]
    confidences: Dict[str, float]


# ---------------------------------------------------------------------
# Sentinel Hub fetching
# ---------------------------------------------------------------------

def _parse_tar_to_arrays(content: bytes) -> Dict[str, np.ndarray]:
    try:
        import tifffile
    except Exception as e:
        raise RuntimeError("tifffile is required. Install with: pip install tifffile") from e

    out: Dict[str, np.ndarray] = {}
    with tarfile.open(fileobj=io.BytesIO(content)) as tar:
        for m in tar.getmembers():
            if not m.isfile() or not (m.name.endswith(".tif") or m.name.endswith(".tiff")):
                continue
            f = tar.extractfile(m)
            if f is None:
                continue
            raw = f.read()
            band = Path(m.name).stem.lower()
            with tifffile.TiffFile(io.BytesIO(raw)) as tif:
                out[band] = tif.asarray().astype(float)
    return out


def fetch_scene_stack_for_date(
    date: str,
    lat: float,
    lng: float,
    polygon_coords: Any,
    target_resolution_m: float = 10.0,
    timeout: int = 35,
) -> Optional[Dict[str, np.ndarray]]:
    """
    Fetch a single-date Sentinel-2 stack:
    NDVI, NDMI, structure proxy, valid mask.

    structure proxy here is NIR reflectance adjusted by red/SWIR context. It is
    not a physical canopy-height product. It is only used for shift estimation.
    """
    import requests
    from eo.sentinel import (
        get_access_token,
        SENTINEL_PROCESS_URL,
        _build_process_bounds,
        _compute_raster_dimensions,
    )

    token = get_access_token()
    bounds = _build_process_bounds(polygon_coords, lat, lng)
    w, h = _compute_raster_dimensions(polygon_coords, lat, lng, target_resolution_m)

    evalscript = """
    //VERSION=3
    function setup() {
      return {
        input: [{bands:["B03","B04","B08","B11","SCL","dataMask"]}],
        output: [
          {id:"ndvi", bands:1, sampleType:"FLOAT32"},
          {id:"ndmi", bands:1, sampleType:"FLOAT32"},
          {id:"structure", bands:1, sampleType:"FLOAT32"},
          {id:"valid", bands:1, sampleType:"UINT8"}
        ]
      };
    }
    function evaluatePixel(s) {
      var scl = s.SCL;
      var valid = (s.dataMask == 1 && (scl == 4 || scl == 5));
      if (!valid) return {ndvi:[-9999], ndmi:[-9999], structure:[-9999], valid:[0]};
      var ndviDen = s.B08 + s.B04;
      var ndmiDen = s.B08 + s.B11;
      var ndvi = ndviDen > 0 ? (s.B08 - s.B04) / ndviDen : -9999;
      var ndmi = ndmiDen > 0 ? (s.B08 - s.B11) / ndmiDen : -9999;
      // structure-like proxy used only for registration: NIR/green-red contrast
      var structure = (s.B08 + 0.5*s.B03 - 0.3*s.B04);
      return {ndvi:[ndvi], ndmi:[ndmi], structure:[structure], valid:[1]};
    }
    """

    start = f"{date}T00:00:00Z"
    end = f"{date}T23:59:59Z"
    payload = {
        "input": {
            "bounds": bounds,
            "data": [{
                "type": "sentinel-2-l2a",
                "dataFilter": {"mosaickingOrder": "leastCC"},
                "timeRange": {"from": start, "to": end},
            }],
        },
        "output": {
            "width": w,
            "height": h,
            "responses": [
                {"identifier": "ndvi", "format": {"type": "image/tiff"}},
                {"identifier": "ndmi", "format": {"type": "image/tiff"}},
                {"identifier": "structure", "format": {"type": "image/tiff"}},
                {"identifier": "valid", "format": {"type": "image/tiff"}},
            ],
        },
        "evalscript": evalscript,
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/tar",
    }
    resp = requests.post(SENTINEL_PROCESS_URL, json=payload, headers=headers, timeout=timeout)
    if resp.status_code != 200:
        print(f"[WARN] Scene {date} failed: HTTP {resp.status_code} {resp.text[:160]}")
        return None

    arrays = _parse_tar_to_arrays(resp.content)
    if "ndvi" not in arrays or "valid" not in arrays:
        print(f"[WARN] Scene {date} missing expected arrays: {list(arrays.keys())}")
        return None

    for k in ["ndvi", "ndmi", "structure"]:
        arrays[k] = np.where(arrays[k] <= -9000, np.nan, arrays[k])
    arrays["valid"] = arrays["valid"] > 0
    return arrays


def select_candidate_dates(lat: float, lng: float, polygon: Any, days: int, max_scenes: int, max_cloud: float) -> List[Dict[str, Any]]:
    from eo.sentinel import fetch_ndvi_timeseries
    ts = fetch_ndvi_timeseries(lat, lng, days=days, polygon_coords=polygon)
    data = ts.get("data", []) if isinstance(ts, dict) else []
    clean = []
    for row in data:
        cc = safe_float(row.get("cloud_cover"), 100.0)
        ndvi = safe_float(row.get("ndvi"))
        date = row.get("date")
        if date and np.isfinite(ndvi) and cc <= max_cloud:
            clean.append({"date": date, "cloud_cover": cc, "ndvi": ndvi})
    # Spread dates across the archive instead of taking only latest scenes.
    if len(clean) <= max_scenes:
        return clean
    idx = np.linspace(0, len(clean)-1, max_scenes).round().astype(int)
    return [clean[int(i)] for i in idx]


def build_real_scene_stack(
    lat: float,
    lng: float,
    polygon: Any,
    days: int,
    max_scenes: int,
    max_cloud: float,
    target_resolution_m: float,
) -> List[V36Scene]:
    candidates = select_candidate_dates(lat, lng, polygon, days, max_scenes, max_cloud)
    print(f"[V36] Candidate dates after cloud filter: {len(candidates)}")

    scenes: List[V36Scene] = []
    for i, c in enumerate(candidates, 1):
        date = c["date"]
        arrays = fetch_scene_stack_for_date(date, lat, lng, polygon, target_resolution_m)
        if arrays is None:
            continue
        valid = arrays["valid"] & np.isfinite(arrays["ndvi"])
        coverage = float(np.mean(valid)) if valid.size else 0.0
        if coverage < 0.08:
            print(f"[V36] Skip {date}: low valid coverage {coverage:.2f}")
            continue
        q = float(max(0.01, min(1.0, coverage * (1.0 - c.get("cloud_cover", 100)/100.0))))
        scenes.append(V36Scene(
            date=date,
            ndvi=arrays["ndvi"],
            ndmi=arrays.get("ndmi", arrays["ndvi"] * np.nan),
            structure=arrays.get("structure", arrays["ndvi"]),
            valid=valid,
            cloud_cover=float(c.get("cloud_cover", 100.0)),
            quality=q,
            shifts={},
            confidences={},
        ))
        print(f"[V36] {len(scenes):03d} scene {date}: coverage={coverage:.2f}, cloud={c.get('cloud_cover', 100):.1f}, quality={q:.2f}")

    return scenes


# ---------------------------------------------------------------------
# Shift candidates, reconstruction, validation
# ---------------------------------------------------------------------

def add_shift_candidates(scenes: List[V36Scene]) -> None:
    if not scenes:
        return
    # Reference = highest-quality scene.
    ref = max(scenes, key=lambda s: s.quality)
    ref_stack = np.nanmean(np.stack([
        np.where(ref.valid, ref.ndvi, np.nan),
        np.where(ref.valid, ref.ndmi, np.nan),
        np.where(ref.valid, ref.structure, np.nan),
    ]), axis=0)

    for sc in scenes:
        # metadata baseline: fixed Process API grid => zero residual image shift.
        sc.shifts["metadata"] = (0.0, 0.0)
        sc.confidences["metadata"] = 0.65

        sc_stack = np.nanmean(np.stack([
            np.where(sc.valid, sc.ndvi, np.nan),
            np.where(sc.valid, sc.ndmi, np.nan),
            np.where(sc.valid, sc.structure, np.nan),
        ]), axis=0)
        mask = ref.valid & sc.valid & np.isfinite(ref_stack) & np.isfinite(sc_stack)

        gdx, gdy, gc = estimate_shift_global(ref_stack, sc_stack, mask)
        ldx, ldy, lc = estimate_shift_local(ref_stack, sc_stack, mask, tile=max(6, min(ref_stack.shape)//3))

        sc.shifts["global_phase"] = (gdx, gdy)
        sc.confidences["global_phase"] = gc
        sc.shifts["local_multiband"] = (ldx, ldy)
        sc.confidences["local_multiband"] = lc

        # Hybrid gate: only move away from metadata if correction is confident and moderate.
        if lc > 0.45 and math.hypot(ldx, ldy) <= 1.75:
            alpha = min(0.70, 0.25 + 0.60*lc)
            sc.shifts["hybrid_gated"] = (alpha*ldx, alpha*ldy)
            sc.confidences["hybrid_gated"] = lc
        elif gc > 0.50 and math.hypot(gdx, gdy) <= 1.50:
            alpha = min(0.50, 0.20 + 0.45*gc)
            sc.shifts["hybrid_gated"] = (alpha*gdx, alpha*gdy)
            sc.confidences["hybrid_gated"] = gc
        else:
            sc.shifts["hybrid_gated"] = (0.0, 0.0)
            sc.confidences["hybrid_gated"] = 0.65


def reconstruct_latent_1m(scenes: List[V36Scene], shift_model: str, factor: int = 10) -> np.ndarray:
    h10, w10 = scenes[0].ndvi.shape
    h1, w1 = h10*factor, w10*factor
    acc = np.zeros((h1, w1), dtype=float)
    weight = np.zeros((h1, w1), dtype=float)

    for sc in scenes:
        src = np.where(sc.valid & np.isfinite(sc.ndvi), sc.ndvi, np.nan)
        up = upsample_10_to_1(src, factor)
        valid = upsample_10_to_1((sc.valid & np.isfinite(sc.ndvi)).astype(float), factor) > 0.5

        dx10, dy10 = sc.shifts.get(shift_model, (0.0, 0.0))
        # Convert 10m-pixel estimated shift to 1m-cell shift.
        back = shift_image_integer(up, -dy10*factor, -dx10*factor)
        back_valid = shift_image_integer(valid.astype(float), -dy10*factor, -dx10*factor) > 0.5

        q = sc.quality * max(0.2, sc.confidences.get(shift_model, 0.5))
        acc += np.where(back_valid & np.isfinite(back), back*q, 0.0)
        weight += np.where(back_valid & np.isfinite(back), q, 0.0)

    fill = np.nanmean(acc[weight > 0] / np.maximum(weight[weight > 0], 1e-9)) if np.any(weight > 0) else 0.4
    latent = np.divide(acc, np.maximum(weight, 1e-9))
    latent[weight <= 0] = fill
    # PSF-aware smoothing + detail preservation.
    smooth = simple_blur(latent, passes=2)
    detail = latent - smooth
    out = smooth + 0.35*detail
    return np.clip(out, -0.2, 1.0)


def predict_scene_from_latent(latent: np.ndarray, scene: V36Scene, shift_model: str, factor: int = 10) -> np.ndarray:
    h10, w10 = scene.ndvi.shape
    dx10, dy10 = scene.shifts.get(shift_model, (0.0, 0.0))
    shifted = shift_image_integer(latent, dy10*factor, dx10*factor)
    pred = downsample_1_to_10(shifted, h10, w10, factor)
    return pred


def evaluate_scenes(latent: np.ndarray, scenes: List[V36Scene], shift_model: str) -> Optional[float]:
    errs = []
    for sc in scenes:
        pred = predict_scene_from_latent(latent, sc, shift_model)
        obs = np.where(sc.valid, sc.ndvi, np.nan)
        e = mse_valid(pred, obs)
        if e is not None:
            errs.append(e)
    return float(np.mean(errs)) if errs else None


def split_scenes(scenes: List[V36Scene]) -> Tuple[List[V36Scene], List[V36Scene], List[V36Scene]]:
    scenes = sorted(scenes, key=lambda s: s.date)
    n = len(scenes)
    n_train = max(6, int(n * 0.65))
    n_val = max(3, int(n * 0.17))
    train = scenes[:n_train]
    val = scenes[n_train:n_train+n_val]
    holdout = scenes[n_train+n_val:]
    if len(holdout) < 2 and n >= 10:
        holdout = scenes[-2:]
        val = scenes[n_train:-2]
    return train, val, holdout


def run_shift_selection(scenes: List[V36Scene]) -> Dict[str, Any]:
    add_shift_candidates(scenes)
    train, val, holdout = split_scenes(scenes)
    models = ["metadata", "global_phase", "local_multiband", "hybrid_gated"]
    results: Dict[str, Dict[str, Any]] = {}

    for m in models:
        latent = reconstruct_latent_1m(train, m)
        results[m] = {
            "internal_validation_mse": evaluate_scenes(latent, val, m),
            "final_holdout_mse": evaluate_scenes(latent, holdout, m),
            "latent_mean": nanmean_or_none(latent),
        }

    valid_models = [m for m in models if results[m]["internal_validation_mse"] is not None]
    selected = min(valid_models, key=lambda m: results[m]["internal_validation_mse"]) if valid_models else "metadata"

    selected_latent = reconstruct_latent_1m(train, selected)
    metadata_latent = reconstruct_latent_1m(train, "metadata")

    # Native baseline = metadata model on final holdout for Process-API fixed grid.
    native_mse = results["metadata"]["final_holdout_mse"]

    # Uncertainty/disagreement map.
    latents = [reconstruct_latent_1m(train, m) for m in models]
    disagreement = np.nanstd(np.stack(latents, axis=0), axis=0)
    denom = np.nanpercentile(disagreement, 90) + 1e-9
    confidence = np.clip(1.0 - disagreement / denom, 0, 1)

    selected_mse = results[selected]["final_holdout_mse"]
    beats_metadata = (
        selected_mse is not None and native_mse is not None and selected_mse < native_mse
    )

    if beats_metadata:
        resolution = np.where(confidence > 0.82, 1, np.where(confidence > 0.66, 2, np.where(confidence > 0.48, 3, np.where(confidence > 0.30, 5, 10))))
    else:
        resolution = np.where(confidence > 0.70, 2, np.where(confidence > 0.52, 3, np.where(confidence > 0.34, 5, 10)))

    fracs = {f"{r}m": float(np.mean(resolution == r)) for r in [1,2,3,5,10]}

    shift_summary = {}
    for m in models:
        vals = [math.hypot(*sc.shifts.get(m, (0,0))) for sc in scenes]
        confs = [sc.confidences.get(m, 0.0) for sc in scenes]
        shift_summary[m] = {
            "mean_abs_shift_pixels_10m": float(np.mean(vals)),
            "median_abs_shift_pixels_10m": float(np.median(vals)),
            "mean_confidence": float(np.mean(confs)),
        }

    return {
        "scene_counts": {"total": len(scenes), "train": len(train), "validation": len(val), "holdout": len(holdout)},
        "models": results,
        "selected_model": selected,
        "selected_beats_metadata_holdout": beats_metadata,
        "metadata_holdout_mse": native_mse,
        "selected_holdout_mse": selected_mse,
        "export_resolution_fraction": fracs,
        "shift_summary": shift_summary,
        "layer1_adapter_preview": {
            "raster_composites": [
                "microzone_ndvi_like_value",
                "microzone_uncertainty",
                "microzone_resolution_m",
                "microzone_retrovalidation_score",
                "microzone_registration_uncertainty_m",
                "microzone_shift_model_selected",
            ],
            "target_handoff": "Layer1InputBundle.raster_composites",
        },
    }


# ---------------------------------------------------------------------
# Dry-run synthetic fallback
# ---------------------------------------------------------------------

def make_dry_run_scenes() -> List[V36Scene]:
    rng = np.random.default_rng(36)
    h, w = 30, 28
    y, x = np.mgrid[0:h, 0:w]
    base = 0.48 + 0.12*np.sin(x/4.5) + 0.08*np.cos(y/5.0) - 0.16*np.exp(-((x-19)**2+(y-11)**2)/55)
    scenes = []
    for i in range(30):
        cloud = float(np.clip(rng.beta(2, 8), 0.02, 0.7))
        noise = rng.normal(0, 0.012 + cloud*0.02, (h,w))
        ndvi = base + 0.015*np.sin(i/5) + noise
        valid = rng.random((h,w)) > cloud
        ndmi = ndvi - 0.07 + rng.normal(0, 0.01, (h,w))
        structure = simple_blur(ndvi, 1) + rng.normal(0, 0.006, (h,w))
        scenes.append(V36Scene(
            date=(datetime(2025,1,1)+timedelta(days=i*10)).strftime("%Y-%m-%d"),
            ndvi=np.where(valid, ndvi, np.nan),
            ndmi=np.where(valid, ndmi, np.nan),
            structure=np.where(valid, structure, np.nan),
            valid=valid,
            cloud_cover=cloud*100,
            quality=float(np.mean(valid)*(1-cloud)),
            shifts={},
            confidences={},
        ))
    return scenes


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, default=DEFAULT_LAT)
    ap.add_argument("--lng", type=float, default=DEFAULT_LNG)
    ap.add_argument("--days", type=int, default=1800)
    ap.add_argument("--max-scenes", type=int, default=72)
    ap.add_argument("--max-cloud", type=float, default=65.0)
    ap.add_argument("--resolution-m", type=float, default=10.0)
    ap.add_argument("--plot-id", type=str, default=DEFAULT_PLOT_ID)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", type=str, default="artifacts/v36_real_scene_stack_shift_selection_report.json")
    args = ap.parse_args()

    report: Dict[str, Any] = {
        "version": "V36_real_sentinel_scene_stack_shift_selection",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plot_id": args.plot_id,
        "constraints": {
            "latent_grid_target_m": 1,
            "satellite_shifting_core": True,
            "no_drones": True,
            "no_cameras": True,
            "no_field_sensors": True,
        },
        "note": "V36A uses per-date Process API rasters. V36B should add native Sentinel granule geometry/transform metadata.",
    }

    try:
        if args.dry_run:
            report["mode"] = "dry_run_synthetic"
            scenes = make_dry_run_scenes()
        else:
            report["mode"] = "real_sentinel_process_api"
            scenes = build_real_scene_stack(
                lat=args.lat,
                lng=args.lng,
                polygon=DEFAULT_POLYGON,
                days=args.days,
                max_scenes=args.max_scenes,
                max_cloud=args.max_cloud,
                target_resolution_m=args.resolution_m,
            )

        report["acquisition"] = {
            "scene_count": len(scenes),
            "dates": [s.date for s in scenes[:8]] + (["..."] if len(scenes) > 8 else []),
            "mean_cloud_cover": float(np.mean([s.cloud_cover for s in scenes])) if scenes else None,
            "mean_quality": float(np.mean([s.quality for s in scenes])) if scenes else None,
        }

        if len(scenes) < 12:
            report["status"] = "insufficient_scenes"
            report["reason"] = "Need at least ~12 valid per-date scenes for train/validation/holdout shift selection."
        else:
            report["shift_selection"] = run_shift_selection(scenes)
            report["status"] = "completed"

    except Exception as e:
        report["status"] = "failed"
        report["error"] = {"type": type(e).__name__, "message": str(e)}
        report["traceback"] = traceback.format_exc()[-4000:]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
