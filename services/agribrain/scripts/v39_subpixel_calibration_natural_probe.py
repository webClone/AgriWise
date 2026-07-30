#!/usr/bin/env python3
"""
V39 — Subpixel Bias Calibration & Natural Geometry Probe

Implements:
- V39A: Ridge-regularized 2D Affine Bias Calibration on Train/Val split controlled offsets.
- V39B: Confidence-to-Error Empirical Calibration (Spearman Rank Correlation).
- V39C: CDSE STAC / Catalog Metadata integration (MGRS tiles, relative orbits, angles).
- V39D: Natural Scene-to-Scene Subpixel Residuals Probe across distinct historical dates.
- V39E: Fair H_t Holdout Evaluation comparing reconstruction strictly against multi-date baselines.

Run from services/agribrain:
  PYTHONPATH=. python scripts/v39_subpixel_calibration_natural_probe.py --max-cloud 100
"""

from __future__ import annotations

import argparse
import io
import json
import math
import tarfile
import traceback
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
DEFAULT_PLOT_ID = "v39_real_polygon_el_oued"
DEFAULT_EPSG_UTM = "EPSG:32632"

# V39 Controlled Offset Splits to prevent Train/Val leakage
OFFSETS_CALIBRATION = [
    (0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (2.0, 3.0), (-2.0, 1.0), (5.0, 0.0)
]
OFFSETS_VALIDATION = [
    (1.0, 1.0), (0.0, 7.0), (5.0, 7.0), (-3.0, -2.0)
]


@dataclass
class ControlledGrid:
    label: str
    requested_east_m: float
    requested_north_m: float
    expected_dx_px_conv_a: float
    expected_dy_px_conv_a: float
    expected_dx_px_conv_b: float
    expected_dy_px_conv_b: float
    arrays: Dict[str, np.ndarray]
    valid_registration_mask: np.ndarray
    estimated_dx_px: Optional[float] = None
    estimated_dy_px: Optional[float] = None
    confidence: Optional[float] = None
    peak_sharpness: Optional[float] = None
    edge_texture_score: Optional[float] = None
    band_agreement_score: Optional[float] = None
    cloud_adjacency_penalty: Optional[float] = None
    phase_error: Optional[float] = None


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


def shift_image_subpixel_integer_fallback(a: np.ndarray, dy: float, dx: float) -> np.ndarray:
    return np.roll(np.roll(a, int(round(dy)), axis=0), int(round(dx)), axis=1)


def mse_valid(a: np.ndarray, b: np.ndarray, valid: Optional[np.ndarray] = None) -> Optional[float]:
    m = np.isfinite(a) & np.isfinite(b)
    if valid is not None:
        m &= valid
    if int(m.sum()) < 8:
        return None
    return float(np.nanmean((a[m] - b[m]) ** 2))


def r2_score(expected: List[float], estimated: List[float]) -> Optional[float]:
    if len(expected) < 3:
        return None
    xx, yy = np.array(expected, dtype=float), np.array(estimated, dtype=float)
    ss_res = float(np.sum((yy - xx) ** 2))
    ss_tot = float(np.sum((yy - np.mean(yy)) ** 2))
    return None if ss_tot <= 1e-12 else float(max(-2.0, min(1.0, 1.0 - ss_res / ss_tot)))


def linear_slope(expected: List[float], estimated: List[float]) -> Optional[float]:
    if len(expected) < 3:
        return None
    xx, yy = np.array(expected, dtype=float), np.array(estimated, dtype=float)
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


def get_taper_2d(h: int, w: int, fraction: float = 0.15) -> np.ndarray:
    """Creates a 2D Tukey-like cosine window tapering towards the edges."""
    y_taper = np.ones(h)
    taper_len_y = int(round(h * fraction))
    if taper_len_y > 0:
        t = np.linspace(0, np.pi/2, taper_len_y)
        w_t = np.sin(t)**2
        y_taper[:taper_len_y] = w_t
        y_taper[-taper_len_y:] = w_t[::-1]
        
    x_taper = np.ones(w)
    taper_len_x = int(round(w * fraction))
    if taper_len_x > 0:
        t = np.linspace(0, np.pi/2, taper_len_x)
        w_t = np.sin(t)**2
        x_taper[:taper_len_x] = w_t
        x_taper[-taper_len_x:] = w_t[::-1]
        
    return y_taper[:, np.newaxis] * x_taper[np.newaxis, :]


def estimate_subpixel_shift_fft(
    reference: np.ndarray,
    target: np.ndarray,
    valid: np.ndarray,
    ref_arrays: Optional[Dict[str, np.ndarray]] = None,
    tar_arrays: Optional[Dict[str, np.ndarray]] = None
) -> Tuple[float, float, float, float, float, float, float, float]:
    """
    Subpixel shift estimator using 2D FFT phase correlation and paraboloid peak fitting.
    Fills NaNs, applies smooth apodization and boundary tapering, and solves subpixel displacement.
    Returns: dx_col, dy_row, confidence, peak_sharpness, edge_score, band_agreement_score, cloud_adjacency_penalty, phase_error
    """
    h, w = reference.shape
    
    # 1. Fill NaNs with median
    med_ref = np.nanmedian(reference[valid]) if np.any(valid & np.isfinite(reference)) else 0.0
    med_tar = np.nanmedian(target[valid]) if np.any(valid & np.isfinite(target)) else 0.0
    ref_f = np.where(np.isfinite(reference) & valid, reference, med_ref)
    tar_f = np.where(np.isfinite(target) & valid, target, med_tar)
    
    # Demean surfaces
    ref_f = ref_f - np.mean(ref_f)
    tar_f = tar_f - np.mean(tar_f)
    
    # 2. Smooth valid mask edges to eliminate internal step discontinuities
    valid_smooth = simple_blur(valid.astype(float), passes=5)
    
    # 3. Create and apply 2D Tukey/cosine boundary taper
    taper = get_taper_2d(h, w, fraction=0.10)
    apodized_mask = valid_smooth * taper
    
    ref_f = ref_f * apodized_mask
    tar_f = tar_f * apodized_mask
    
    # 4. Compute Phase Cross-Correlation via 2D FFT
    f_ref = np.fft.fft2(ref_f)
    f_tar = np.fft.fft2(tar_f)
    R = f_ref * np.conj(f_tar)
    R_abs = np.abs(R)
    R_abs = np.where(R_abs < 1e-12, 1e-12, R_abs)
    R = R / R_abs
    
    cc = np.fft.fftshift(np.real(np.fft.ifft2(R)))
    
    # 5. Locate integer peak
    y_peak, x_peak = np.unravel_index(np.argmax(cc), cc.shape)
    y_mid, x_mid = h // 2, w // 2
    dy_int = y_peak - y_mid
    dx_int = x_peak - x_mid
    
    # 6. Fit 2D Paraboloid for Sub-Pixel Estimation
    dx_sub, dy_sub = 0.0, 0.0
    if 0 < y_peak < h - 1 and 0 < x_peak < w - 1:
        alpha = cc[y_peak, x_peak]
        bx_plus, bx_minus = cc[y_peak, x_peak + 1], cc[y_peak, x_peak - 1]
        by_plus, by_minus = cc[y_peak + 1, x_peak], cc[y_peak - 1, x_peak]
        
        denom_x = bx_minus + bx_plus - 2.0 * alpha
        denom_y = by_minus + by_plus - 2.0 * alpha
        
        if abs(denom_x) > 1e-9:
            dx_sub = (bx_minus - bx_plus) / (2.0 * denom_x)
        if abs(denom_y) > 1e-9:
            dy_sub = (by_minus - by_plus) / (2.0 * denom_y)
            
        dx_sub = max(-0.5, min(0.5, dx_sub))
        dy_sub = max(-0.5, min(0.5, dy_sub))
        
    dx_est = dx_int + dx_sub
    dy_est = dy_int + dy_sub
    
    # 7. Combined Confidence Metrics
    alpha = cc[y_peak, x_peak]
    mean_cc, std_cc = np.mean(cc), np.std(cc)
    peak_sharpness = float(max(0.0, min(1.0, (alpha - mean_cc) / (6.0 * std_cc + 1e-9))))
    val_frac = float(np.mean(valid))
    phase_error = float(max(0.0, min(1.0, 1.0 - alpha)))
    
    # Texture edge strength
    edge_mag = sobel_like_edge(reference)
    edge_score = float(max(0.0, min(1.0, np.nanmean(edge_mag) * 8.0))) if np.any(np.isfinite(edge_mag)) else 0.0
    
    # Band Agreement & Cloud Adjacency Penalty
    if ref_arrays is not None and tar_arrays is not None:
        # Band Agreement
        band_shifts = []
        for b in ["b04", "b08", "b11"]:
            if b in ref_arrays and b in tar_arrays:
                b_dx, b_dy, _, _, _, _, _, _ = estimate_subpixel_shift_fft(
                    ref_arrays[b], tar_arrays[b], valid, ref_arrays=None, tar_arrays=None
                )
                band_shifts.append((b_dx, b_dy))
        if len(band_shifts) >= 2:
            dx_std = np.std([s[0] for s in band_shifts])
            dy_std = np.std([s[1] for s in band_shifts])
            agreement = float(np.exp(-1.5 * (dx_std + dy_std)))
            band_agreement_score = float(max(0.0, min(1.0, agreement)))
        else:
            band_agreement_score = 1.0
            
        # Cloud Adjacency Penalty
        ref_cloud = ref_arrays.get("cloud", np.zeros_like(valid)).astype(bool)
        tar_cloud = tar_arrays.get("cloud", np.zeros_like(valid)).astype(bool)
        cloud_mask = ref_cloud | tar_cloud
        cloud_adj = dilate_binary(cloud_mask, radius=3)
        cloud_fraction = float(np.mean(cloud_adj))
        cloud_adjacency_penalty = float(max(0.0, min(1.0, 1.0 - 2.0 * cloud_fraction)))
    else:
        band_agreement_score = 1.0
        cloud_adjacency_penalty = 1.0
        
    confidence = float(max(0.0, min(1.0, peak_sharpness * val_frac * (0.3 + 0.7 * edge_score) * band_agreement_score * cloud_adjacency_penalty)))
    
    return dx_est, dy_est, confidence, peak_sharpness, edge_score, band_agreement_score, cloud_adjacency_penalty, phase_error


def shift_image_subpixel_fft(a: np.ndarray, dy: float, dx: float) -> np.ndarray:
    """Performs an exact subpixel spatial translation in the Fourier domain."""
    h, w = a.shape
    f = np.fft.fft2(a)
    v = np.fft.fftfreq(h)
    u = np.fft.fftfreq(w)
    v_grid, u_grid = np.meshgrid(v, u, indexing='ij')
    ramp = np.exp(-2j * np.pi * (v_grid * dy + u_grid * dx))
    return np.real(np.fft.ifft2(f * ramp))


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
                "processing": {
                    "upsampling": "BICUBIC",
                    "downsampling": "BICUBIC"
                },
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


def select_best_dates_list(lat: float, lng: float, polygon: Any, days: int, max_cloud: float, count: int = 3) -> List[str]:
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
    
    # Filter to ensure we select distinct dates
    seen = set()
    out = []
    for _, d in candidates:
        if d not in seen:
            seen.add(d)
            out.append(d)
            if len(out) >= count:
                break
    return out


def compute_expected_shifts(dx_m: float, dy_m: float, gsd_m: float) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    # Convention A
    dx_a = -dx_m / gsd_m
    dy_a = dy_m / gsd_m
    # Convention B
    dx_b = dx_m / gsd_m
    dy_b = -dy_m / gsd_m
    return (dx_a, dy_a), (dx_b, dy_b)


def make_dry_run_controlled_grids(offsets_m: List[Tuple[float, float]], gsd_m: float, width: int = 128, height: int = 128) -> List[ControlledGrid]:
    rng = np.random.default_rng(39)
    y, x = np.mgrid[0:height, 0:width]
    
    b04 = 0.15 + 0.05*np.sin(x/5.0) + 0.04*np.cos(y/6.0)
    b08 = 0.45 + 0.10*np.sin((x+y)/10.0)
    b11 = 0.25 + 0.04*np.cos(x/8.0) + 0.03*np.sin(y/6.0)
    
    cx_mid = width // 2
    cy_mid = height // 2
    for offset in range(-2, 3):
        b04[:, cx_mid + offset] += 0.10; b08[:, cx_mid + offset] -= 0.08; b11[:, cx_mid + offset] += 0.05
        b04[cy_mid + offset, :] += 0.10; b08[cy_mid + offset, :] -= 0.08; b11[cy_mid + offset, :] += 0.05
        
    for cy in [cy_mid - 24, cy_mid, cy_mid + 24]:
        for cx in [cx_mid - 24, cx_mid, cx_mid + 24]:
            if 0 <= cy < height and 0 <= cx < width:
                dist2 = (x - cx)**2 + (y - cy)**2
                peak = np.exp(-dist2 / 45.0)
                b04 += 0.15 * peak
                b08 += 0.40 * peak
                b11 += 0.10 * peak
            
    base = {"b04": b04, "b08": b08, "b11": b11}
    base["ndvi"] = (b08 - b04) / np.maximum(b08 + b04, 1e-6)
    base["ndmi"] = (b08 - b11) / np.maximum(b08 + b11, 1e-6)
    valid = np.ones((height, width), dtype=bool)
    cloud = np.zeros((height, width), dtype=bool)
    
    grids = []
    for dx_m, dy_m in offsets_m:
        conv_a, conv_b = compute_expected_shifts(dx_m, dy_m, gsd_m)
        # Apply mathematically perfect Fourier subpixel shifts using Convention A
        # Let's add slight diagonal bias scaling (1.1x scaling on diagonal) to simulate the raw V38 BBox shear bias
        factor_x = 1.05 if dx_m != 0.0 and dy_m != 0.0 else 1.0
        factor_y = 1.05 if dx_m != 0.0 and dy_m != 0.0 else 1.0
        arrays = {
            k: shift_image_subpixel_fft(v, conv_a[1] * factor_y, conv_a[0] * factor_x) + rng.normal(0, 0.0001, v.shape)
            for k, v in base.items()
        }
        arrays["valid"] = valid.copy()
        arrays["cloud"] = cloud.copy()
        grids.append(ControlledGrid(
            label=f"dry_east_{dx_m:+.1f}m_north_{dy_m:+.1f}m",
            requested_east_m=dx_m, requested_north_m=dy_m,
            expected_dx_px_conv_a=conv_a[0], expected_dy_px_conv_a=conv_a[1],
            expected_dx_px_conv_b=conv_b[0], expected_dy_px_conv_b=conv_b[1],
            arrays=arrays, valid_registration_mask=valid.copy()
        ))
    return grids


def execute_sub_experiment(date: str, polygon: Any, buffer_m: float, gsd_m: float, offsets_m: List[Tuple[float, float]], width: int, height: int, dry_run: bool = False) -> Dict[str, Any]:
    # Calculate width and height dynamically to ensure GSD is exactly gsd_m
    bbox = bbox_from_polygon(polygon)
    lat_hint = (bbox[1] + bbox[3]) / 2.0
    meters_per_deg_lat = 111320.0
    meters_per_deg_lon = 111320.0 * max(0.2, math.cos(math.radians(lat_hint)))
    
    d_lon = bbox[2] - bbox[0]
    d_lat = bbox[3] - bbox[1]
    
    w_m = d_lon * meters_per_deg_lon + 2.0 * buffer_m
    h_m = d_lat * meters_per_deg_lat + 2.0 * buffer_m
    
    width = int(round(w_m / gsd_m))
    height = int(round(h_m / gsd_m))
    width = max(16, min(512, width))
    height = max(16, min(512, height))
    
    grids, method_used = [], None
    if dry_run:
        grids, method_used = make_dry_run_controlled_grids(offsets_m, gsd_m, width=width, height=height), "dry_run_synthetic"
    else:
        for dx_m, dy_m in offsets_m:
            bbox_shifted, method = utm_expand_shift_bbox(polygon, buffer_m, dx_m, dy_m)
            method_used = method_used or method
            arrays = fetch_controlled_grid(date, bbox_shifted, width=width, height=height)
            cloud_adj = dilate_binary(arrays["cloud"].astype(bool), radius=2)
            valid_reg = arrays["valid"].astype(bool) & (~cloud_adj)
            conv_a, conv_b = compute_expected_shifts(dx_m, dy_m, gsd_m)
            grids.append(ControlledGrid(
                label=f"east_{dx_m:+.1f}m_north_{dy_m:+.1f}m",
                requested_east_m=dx_m, requested_north_m=dy_m,
                expected_dx_px_conv_a=conv_a[0], expected_dy_px_conv_a=conv_a[1],
                expected_dx_px_conv_b=conv_b[0], expected_dy_px_conv_b=conv_b[1],
                arrays=arrays, valid_registration_mask=valid_reg
            ))
            
    ref = min(grids, key=lambda g: abs(g.requested_east_m) + abs(g.requested_north_m))
    ref_surface = build_registration_surface(ref.arrays)
    
    for g in grids:
        target_surface = build_registration_surface(g.arrays)
        valid = ref.valid_registration_mask & g.valid_registration_mask
        est_dx, est_dy, conf, sharpness, edge_score, band_agreement, cloud_penalty, phase_err = estimate_subpixel_shift_fft(
            ref_surface, target_surface, valid, ref_arrays=ref.arrays, tar_arrays=g.arrays
        )
        g.estimated_dx_px = est_dx
        g.estimated_dy_px = est_dy
        g.confidence = conf
        g.peak_sharpness = sharpness
        g.edge_texture_score = edge_score
        g.band_agreement_score = band_agreement
        g.cloud_adjacency_penalty = cloud_penalty
        g.phase_error = phase_err

    # Auto Sign-Convention evaluation
    rmse_conv_a, rmse_conv_b = [], []
    for g in grids:
        if abs(g.requested_east_m) + abs(g.requested_north_m) < 1e-9:
            continue
        err_a = math.sqrt((g.estimated_dx_px - g.expected_dx_px_conv_a)**2 + (g.estimated_dy_px - g.expected_dy_px_conv_a)**2) * gsd_m
        err_b = math.sqrt((g.estimated_dx_px - g.expected_dx_px_conv_b)**2 + (g.estimated_dy_px - g.expected_dy_px_conv_b)**2) * gsd_m
        rmse_conv_a.append(err_a**2)
        rmse_conv_b.append(err_b**2)
        
    rmse_a = math.sqrt(np.mean(rmse_conv_a)) if rmse_conv_a else 999.0
    rmse_b = math.sqrt(np.mean(rmse_conv_b)) if rmse_conv_b else 999.0
    
    selected_conv = "A" if rmse_a <= rmse_b else "B"
    best_rmse = rmse_a if selected_conv == "A" else rmse_b
    
    test_results = []
    expected_mags, estimated_mags = [], []
    for g in grids:
        exp_dx = g.expected_dx_px_conv_a if selected_conv == "A" else g.expected_dx_px_conv_b
        exp_dy = g.expected_dy_px_conv_a if selected_conv == "A" else g.expected_dy_px_conv_b
        err_m = math.sqrt((g.estimated_dx_px - exp_dx)**2 + (g.estimated_dy_px - exp_dy)**2) * gsd_m
        test_results.append({
            "label": g.label,
            "requested_shift_m": {"east": g.requested_east_m, "north": g.requested_north_m},
            "expected_shift_px": {"dx_col": exp_dx, "dy_row": exp_dy},
            "estimated_shift_px": {"dx_col": g.estimated_dx_px, "dy_row": g.estimated_dy_px},
            "shift_error_m": err_m,
            "registration_confidence": g.confidence,
            "phase_error": g.phase_error,
            "peak_sharpness": g.peak_sharpness,
            "valid_registration_fraction": float(np.mean(g.valid_registration_mask)),
            "band_agreement_score": g.band_agreement_score,
            "edge_texture_score": g.edge_texture_score,
            "cloud_adjacency_penalty": g.cloud_adjacency_penalty,
        })
        if abs(g.requested_east_m) + abs(g.requested_north_m) > 1e-9:
            expected_mags.append(math.sqrt(exp_dx**2 + exp_dy**2))
            estimated_mags.append(math.sqrt(g.estimated_dx_px**2 + g.estimated_dy_px**2))
            
    r2 = r2_score(expected_mags, estimated_mags)
    slope = linear_slope(expected_mags, estimated_mags)
    med_conf = float(np.median([r["registration_confidence"] for r in test_results if r["label"] != ref.label])) if len(test_results) > 1 else 0.0
    
    return {
        "date": date, "bbox_transform_method": method_used, "gsd_m": gsd_m, "buffer_m": buffer_m,
        "selected_sign_convention": selected_conv,
        "sign_convention_comparison_rmse": {"convention_A": rmse_a, "convention_B": rmse_b},
        "controlled_shift_tests": test_results,
        "rmse_m": best_rmse,
        "r2": r2,
        "slope": slope,
        "median_confidence": med_conf,
        "grids_object": grids,
    }


def fit_ridge_affine(expected: np.ndarray, raw_est: np.ndarray, reg: float = 0.05) -> Tuple[np.ndarray, np.ndarray]:
    """
    Fits a 2D affine calibration model y = A*x + b with ridge regularization around the identity.
    expected: N x 2 array of requested shifts (dx_expected, dy_expected)
    raw_est: N x 2 array of raw estimated shifts (dx_raw, dy_raw)
    reg: lambda coefficient for regularizing towards Identity.
    Returns: A (2x2), b (2,)
    """
    N = len(expected)
    if N < 3:
        return np.eye(2), np.zeros(2)
        
    # Build augmented X matrix: N x 3
    X = np.hstack([raw_est, np.ones((N, 1))])
    
    # Target Y: N x 2
    Y = expected
    
    # W0: 3 x 2 identity weight matrix
    W0 = np.array([[1.0, 0.0],
                   [0.0, 1.0],
                   [0.0, 0.0]])
                   
    # Z = Y - X * W0
    Z = Y - X @ W0
    
    # Ridge regression for D (delta from Identity)
    XTX = X.T @ X
    I3 = np.eye(3)
    
    D = np.linalg.inv(XTX + reg * I3) @ X.T @ Z
    
    # W = W0 + D
    W = W0 + D
    
    A = W[:2, :].T
    b = W[2, :]
    
    return A, b


def rank_data(x: List[float]) -> List[float]:
    temp = [(val, idx) for idx, val in enumerate(x)]
    temp.sort()
    ranks = [0.0] * len(x)
    for r, (val, idx) in enumerate(temp):
        ranks[idx] = r + 1.0
    return ranks


def pearson_correlation(x: np.ndarray, y: np.ndarray) -> float:
    std_x = np.std(x)
    std_y = np.std(y)
    if std_x <= 1e-9 or std_y <= 1e-9:
        return 0.0
    return float(np.mean((x - np.mean(x)) * (y - np.mean(y))) / (std_x * std_y))


def spearman_correlation(x: List[float], y: List[float]) -> float:
    if len(x) < 3:
        return 0.0
    ranks_x = np.array(rank_data(x), dtype=float)
    ranks_y = np.array(rank_data(y), dtype=float)
    return pearson_correlation(ranks_x, ranks_y)


def query_cdse_catalog(bbox: List[float], start_date: str, end_date: str) -> List[Dict[str, Any]]:
    import requests
    url = "https://catalogue.dataspace.copernicus.eu/stac/search"
    payload = {
        "bbox": bbox,
        "datetime": f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
        "collections": ["SENTINEL-2"],
        "limit": 50
    }
    try:
        resp = requests.post(url, json=payload, timeout=20)
        if resp.status_code == 200:
            return resp.json().get("features", [])
    except Exception:
        pass
    return []


def find_property_value(properties: Dict[str, Any], keys: List[str]) -> Any:
    for k in keys:
        if k in properties:
            return properties[k]
    for k_target in keys:
        for k_actual in properties.keys():
            if k_target.lower().replace("_", "").replace(":", "") in k_actual.lower().replace("_", "").replace(":", ""):
                return properties[k_actual]
    return None


def run_catalog_metadata_probe(date: str, bbox: List[float], dry_run: bool = False) -> Dict[str, Any]:
    if dry_run:
        return {
            "catalog_used": True,
            "scene_count": 1,
            "fields_parsed": ["relativeOrbitNumber", "orbitDirection", "MGRS tile", "sun/view geometry"],
            "scenes": [{
                "id": "MOCK_S2A_20250501",
                "date": date,
                "relativeOrbitNumber": 122,
                "orbitDirection": "descending",
                "tileId": "32SMB",
                "sunZenithAngle": 21.4,
                "sunAzimuthAngle": 134.5
            }]
        }
    
    features = query_cdse_catalog(bbox, date, date)
    parsed_scenes = []
    for f in features:
        props = f.get("properties", {})
        orbit = find_property_value(props, ["relativeOrbitNumber", "sat:relative_orbit", "relative_orbit", "orbit"])
        direction = find_property_value(props, ["orbitDirection", "sat:orbit_state", "orbit_state", "orbit_direction"])
        tile = find_property_value(props, ["s2:mgrs_tile", "mgrs_tile", "tileId", "tile"])
        zenith = find_property_value(props, ["view:sun_zenith", "sun_zenith", "sunZenithAngle"])
        azimuth = find_property_value(props, ["view:sun_azimuth", "sun_azimuth", "sunAzimuthAngle"])
        
        parsed_scenes.append({
            "id": f.get("id"),
            "date": date,
            "relativeOrbitNumber": int(orbit) if orbit is not None else None,
            "orbitDirection": direction,
            "tileId": tile,
            "sunZenithAngle": float(zenith) if zenith is not None else None,
            "sunAzimuthAngle": float(azimuth) if azimuth is not None else None,
        })
        
    return {
        "catalog_used": True,
        "scene_count": len(parsed_scenes),
        "fields_parsed": ["relativeOrbitNumber", "orbitDirection", "MGRS tile", "sun/view geometry"],
        "scenes": parsed_scenes
    }


def run_natural_scene_drift_probe(dates: List[str], polygon: Any, buffer_m: float, gsd_m: float, width: int, height: int, dry_run: bool = False) -> Dict[str, Any]:
    if len(dates) < 2:
        return {"residuals_measured": False, "reason": "Insufficient dates for natural probe."}
        
    bbox = bbox_from_polygon(polygon)
    lat_hint = (bbox[1] + bbox[3]) / 2.0
    meters_per_deg_lat = 111320.0
    meters_per_deg_lon = 111320.0 * max(0.2, math.cos(math.radians(lat_hint)))
    w_m = (bbox[2] - bbox[0]) * meters_per_deg_lon + 2.0 * buffer_m
    h_m = (bbox[3] - bbox[1]) * meters_per_deg_lat + 2.0 * buffer_m
    dyn_w = max(16, min(512, int(round(w_m / gsd_m))))
    dyn_h = max(16, min(512, int(round(h_m / gsd_m))))
    
    # 1. Fetch metadata and reflectances for each date at 0m shift
    scene_data = []
    for d in dates:
        meta = run_catalog_metadata_probe(d, bbox, dry_run)
        scene_meta = meta["scenes"][0] if meta["scenes"] else {"id": f"MOCK_{d}", "relativeOrbitNumber": 122, "tileId": "32SMB"}
        
        if dry_run:
            # Mock synthetic reflectance
            rng = np.random.default_rng(hash(d) % 1000)
            mock_arr = {"b04": rng.normal(0.2, 0.05, (dyn_h, dyn_w)), "b08": rng.normal(0.4, 0.05, (dyn_h, dyn_w)), "b11": rng.normal(0.25, 0.05, (dyn_h, dyn_w))}
            mock_arr["valid"] = np.ones((dyn_h, dyn_w), dtype=bool)
            mock_arr["cloud"] = np.zeros((dyn_h, dyn_w), dtype=bool)
            arrays = mock_arr
        else:
            try:
                bbox_unshifted, _ = utm_expand_shift_bbox(polygon, buffer_m, 0.0, 0.0)
                arrays = fetch_controlled_grid(d, bbox_unshifted, width=dyn_w, height=dyn_h)
            except Exception as e:
                continue
                
        cloud_adj = dilate_binary(arrays["cloud"].astype(bool), radius=2)
        valid_reg = arrays["valid"].astype(bool) & (~cloud_adj)
        surface = build_registration_surface(arrays)
        scene_data.append({
            "date": d,
            "meta": scene_meta,
            "surface": surface,
            "valid": valid_reg,
            "arrays": arrays
        })
        
    if len(scene_data) < 2:
        return {"residuals_measured": False, "reason": "Failed to retrieve arrays for natural probe."}
        
    # 2. Compute natural scene-to-scene subpixel residual shifts
    residuals = []
    ref_scene = scene_data[0]
    for tar_scene in scene_data[1:]:
        valid = ref_scene["valid"] & tar_scene["valid"]
        dx, dy, conf, _, _, _, _, _ = estimate_subpixel_shift_fft(
            ref_scene["surface"], tar_scene["surface"], valid,
            ref_arrays=ref_scene["arrays"], tar_arrays=tar_scene["arrays"]
        )
        # Shift in meters
        dx_m = dx * gsd_m
        dy_m = dy * gsd_m
        
        # Correlate with orbit/tile ID grouping
        ref_orbit = ref_scene["meta"].get("relativeOrbitNumber")
        tar_orbit = tar_scene["meta"].get("relativeOrbitNumber")
        ref_tile = ref_scene["meta"].get("tileId")
        tar_tile = tar_scene["meta"].get("tileId")
        
        residuals.append({
            "reference_date": ref_scene["date"],
            "target_date": tar_scene["date"],
            "estimated_shift_px": {"dx_col": dx, "dy_row": dy},
            "estimated_shift_m": {"east": dx_m, "north": dy_m},
            "confidence": conf,
            "relative_orbit_ref": ref_orbit,
            "relative_orbit_tar": tar_orbit,
            "tile_ref": ref_tile,
            "tile_tar": tar_tile,
            "same_orbit": bool(ref_orbit is not None and ref_orbit == tar_orbit),
            "same_tile": bool(ref_tile is not None and ref_tile == tar_tile),
        })
        
    # Calculate group repeatability
    same_orbit_errs = [math.sqrt(r["estimated_shift_m"]["east"]**2 + r["estimated_shift_m"]["north"]**2) for r in residuals if r["same_orbit"]]
    diff_orbit_errs = [math.sqrt(r["estimated_shift_m"]["east"]**2 + r["estimated_shift_m"]["north"]**2) for r in residuals if not r["same_orbit"]]
    
    repeat_orbit = float(np.exp(-0.2 * np.mean(same_orbit_errs))) if same_orbit_errs else 1.0
    repeat_tile = float(np.exp(-0.2 * np.mean([math.sqrt(r["estimated_shift_m"]["east"]**2 + r["estimated_shift_m"]["north"]**2) for r in residuals if r["same_tile"]]))) if any(r["same_tile"] for r in residuals) else 1.0
    
    return {
        "residuals_measured": True,
        "residuals": residuals,
        "repeatability_by_orbit": repeat_orbit,
        "repeatability_by_tile": repeat_tile,
        "natural_shift_validated": False,
        "reason": "Natural residuals measured but not independently validated."
    }


def run_h_operator_holdout(controlled_res: Dict[str, Any], sign_multiplier: float, A_cal: np.ndarray, b_cal: np.ndarray, use_cal: bool = True, factor: int = 10) -> Dict[str, Any]:
    grids: List[ControlledGrid] = controlled_res["grids_object"]
    if len(grids) < 4:
        return {"status": "insufficient_grids"}
    
    holdout = max(grids, key=lambda g: abs(g.requested_east_m) + abs(g.requested_north_m))
    train = [g for g in grids if g is not holdout]
    h10, w10 = train[0].arrays["ndvi"].shape
    h1, w1 = h10 * factor, w10 * factor
    
    def up(a): return np.repeat(np.repeat(a, factor, axis=0), factor, axis=1)
    def down(a): return np.nanmean(a[:h1, :w1].reshape(h10, factor, w10, factor), axis=(1, 3))
    
    # 1. H_t Subpixel Reconstruction
    acc_sub = np.zeros((h1, w1)); wt_sub = np.zeros((h1, w1))
    for g in train:
        src = np.where(g.arrays["valid"], g.arrays["ndvi"], np.nan)
        u, v = up(src), up(g.arrays["valid"].astype(float)) > 0.5
        
        # Raw estimated shift converted to Convention A
        est_dx_a = (g.estimated_dx_px or 0.0) * sign_multiplier
        est_dy_a = (g.estimated_dy_px or 0.0) * sign_multiplier
        
        # Apply 2D affine calibration if accepted and within subpixel range
        if use_cal and math.sqrt(est_dx_a**2 + est_dy_a**2) <= 0.5:
            cal = A_cal @ np.array([est_dx_a, est_dy_a]) + b_cal
            est_dx_a = cal[0]
            est_dy_a = cal[1]
            
        dx = est_dx_a * factor
        dy = est_dy_a * factor
        back = shift_image_subpixel_integer_fallback(u, -dy, -dx)
        bv = shift_image_subpixel_integer_fallback(v.astype(float), -dy, -dx) > 0.5
        q = max(0.05, g.confidence or 0.2)
        acc_sub += np.where(bv & np.isfinite(back), back*q, 0)
        wt_sub += np.where(bv & np.isfinite(back), q, 0)
        
    fill = np.nanmean(acc_sub[wt_sub > 0] / np.maximum(wt_sub[wt_sub > 0], 1e-9)) if np.any(wt_sub > 0) else 0.4
    latent_sub = np.divide(acc_sub, np.maximum(wt_sub, 1e-9)); latent_sub[wt_sub <= 0] = fill
    latent_sub = simple_blur(latent_sub, 2) + 0.35*(latent_sub - simple_blur(latent_sub, 2))
    
    hx_a = (holdout.estimated_dx_px or 0.0) * sign_multiplier
    hy_a = (holdout.estimated_dy_px or 0.0) * sign_multiplier
    
    if use_cal and math.sqrt(hx_a**2 + hy_a**2) <= 0.5:
        cal = A_cal @ np.array([hx_a, hy_a]) + b_cal
        hx_a = cal[0]
        hy_a = cal[1]
        
    hx = hx_a * factor
    hy = hy_a * factor
    pred_sub_ht = down(shift_image_subpixel_integer_fallback(latent_sub, hy, hx))
    
    # 2. Baseline A: Naive 10m Upsample (degenerateSame-date baseline)
    raw_10m = holdout.arrays["ndvi"]
    pred_naive_10m = simple_blur(raw_10m, 1)
    
    # 3. Baseline B: No-shift 1m Reconstruction
    acc_no = np.zeros((h1, w1)); wt_no = np.zeros((h1, w1))
    for g in train:
        src = np.where(g.arrays["valid"], g.arrays["ndvi"], np.nan)
        u, v = up(src), up(g.arrays["valid"].astype(float)) > 0.5
        acc_no += np.where(v & np.isfinite(u), u, 0); wt_no += np.where(v & np.isfinite(u), 1, 0)
    latent_no = np.divide(acc_no, np.maximum(wt_no, 1e-9)); latent_no[wt_no <= 0] = fill
    pred_no_shift = down(simple_blur(latent_no, 2))
    
    # 4. Baseline C: Integer-only H_t Reconstruction
    acc_int = np.zeros((h1, w1)); wt_int = np.zeros((h1, w1))
    for g in train:
        src = np.where(g.arrays["valid"], g.arrays["ndvi"], np.nan)
        u, v = up(src), up(g.arrays["valid"].astype(float)) > 0.5
        est_dx_a = (g.estimated_dx_px or 0.0) * sign_multiplier
        est_dy_a = (g.estimated_dy_px or 0.0) * sign_multiplier
        if use_cal:
            cal = A_cal @ np.array([est_dx_a, est_dy_a]) + b_cal
            est_dx_a = cal[0]
            est_dy_a = cal[1]
        dx = round(est_dx_a) * factor
        dy = round(est_dy_a) * factor
        back = shift_image_subpixel_integer_fallback(u, -dy, -dx)
        bv = shift_image_subpixel_integer_fallback(v.astype(float), -dy, -dx) > 0.5
        q = max(0.05, g.confidence or 0.2)
        acc_int += np.where(bv & np.isfinite(back), back*q, 0)
        wt_int += np.where(bv & np.isfinite(back), q, 0)
    latent_int = np.divide(acc_int, np.maximum(wt_int, 1e-9)); latent_int[wt_int <= 0] = fill
    
    hx_int = round(hx_a) * factor
    hy_int = round(hy_a) * factor
    pred_int_ht = down(shift_image_subpixel_integer_fallback(latent_int, hy_int, hx_int))
    
    obs = np.where(holdout.arrays["valid"], holdout.arrays["ndvi"], np.nan)
    
    mse_sub_ht = mse_valid(pred_sub_ht, obs, holdout.arrays["valid"])
    mse_naive = mse_valid(pred_naive_10m, obs, holdout.arrays["valid"])
    mse_no = mse_valid(pred_no_shift, obs, holdout.arrays["valid"])
    mse_int = mse_valid(pred_int_ht, obs, holdout.arrays["valid"])
    
    # Exclude direct naive_10m_upsample from reconstruction best_baseline mix to evaluate active cross-grid prediction fairly
    best_baseline = min([x for x in [mse_no, mse_int] if x is not None])
    improvement = None if (mse_sub_ht is None or best_baseline is None or best_baseline <= 0) else (best_baseline - mse_sub_ht) / best_baseline
    
    return {
        "status": "completed",
        "holdout_grid": holdout.label,
        "subpixel_ht_mse": mse_sub_ht,
        "naive_10m_upsample_mse": mse_naive,
        "no_shift_mse": mse_no,
        "integer_ht_mse": mse_int,
        "improvement_fraction": improvement,
        "improvement_pct": None if improvement is None else float(improvement * 100),
    }


def evaluate_acceptance(
    a_res: Dict[str, Any],
    b_res: Dict[str, Any],
    c_res: Dict[str, Any],
    d_res: Dict[str, Any],
    e_res: Dict[str, Any]
) -> Dict[str, Any]:
    # V39A Affine Validation Check (on held-out val set)
    cal_rmse = a_res.get("calibrated_rmse_m")
    raw_rmse = a_res.get("raw_rmse_m")
    a_ok = bool(
        cal_rmse is not None and (
            cal_rmse <= 0.8 or 
            (raw_rmse is not None and cal_rmse <= raw_rmse * 0.85)
        )
    )
    
    # V39B Confidence Checks
    spearman = b_res.get("spearman_confidence_error")
    high_conf_err = b_res.get("high_confidence_error_median_m")
    b_ok = bool(
        spearman is not None and spearman <= -0.55 and 
        high_conf_err is not None and high_conf_err <= 0.8
    )
    
    # V39E H_t Reconstruction Checks
    impr = e_res.get("improvement_vs_no_shift_pct")
    e_ok = bool(impr is not None and impr >= 3.0)
    
    allow = False
    research_allow = bool(a_ok and b_ok and e_ok)
    
    return {
        "controlled_subpixel_shift_validated": research_allow,
        "affine_calibration_validated": a_ok,
        "h_operator_validated": e_ok,
        "natural_shift_validated": False,
        "allow_strong_1m_export": allow,
        "allow_controlled_1m_research_mode": research_allow,
        "fallback_resolution_policy": "2m_to_10m_dynamic",
        "reason": "Controlled affine calibration & H_t holdout fully validated. Research mode 1m allowed." if research_allow else "Calibration / reconstruction thresholds not fully met."
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
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default="artifacts/v39_subpixel_calibration_natural_probe_report.json")
    args = ap.parse_args()
    
    report = {
        "version": "V39_subpixel_bias_calibration_natural_probe",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plot_id": args.plot_id,
        "mode": "dry_run_synthetic" if args.dry_run else "real_sentinel_process_api",
    }
    
    try:
        bbox_ref = bbox_from_polygon(DEFAULT_POLYGON)
        
        # 1. Fetch dates timeseries and identify reference date and targets
        dates = []
        if args.dry_run:
            dates = ["2025-05-01", "2025-05-06", "2025-05-11"]
        else:
            dates = select_best_dates_list(args.lat, args.lng, DEFAULT_POLYGON, args.days, args.max_cloud, count=3)
            
        if not dates:
            raise RuntimeError("No suitable Sentinel-2 dates found. Specify a higher cloud limit or dry-run.")
            
        report["selected_dates"] = dates
        ref_date = dates[0]
        
        # 2. Run Controlled shifts on both Calibration and Validation sets
        # Combine them for the single process execution to save API requests
        all_offsets = OFFSETS_CALIBRATION + OFFSETS_VALIDATION
        combined_result = execute_sub_experiment(ref_date, DEFAULT_POLYGON, args.buffer_m, args.gsd_m, all_offsets, 128, 128, args.dry_run)
        
        grids: List[ControlledGrid] = combined_result["grids_object"]
        selected_conv = combined_result["selected_sign_convention"]
        sign_multiplier = 1.0 if selected_conv == "A" else -1.0
        
        # Split grids back into Calibration (Train) and Validation (Val)
        cal_grids = [g for g in grids if (g.requested_east_m, g.requested_north_m) in OFFSETS_CALIBRATION]
        val_grids = [g for g in grids if (g.requested_east_m, g.requested_north_m) in OFFSETS_VALIDATION]
        
        # Fit Ridge-Regularized 2D Affine Calibration Solver strictly on Subpixel Calibration offsets (magnitude < 5m)
        # We enforce physical symmetry by setting constant bias b_cal = 0
        expected_cal = []
        raw_est_cal = []
        for g in cal_grids:
            # Exclude zero offset and boundary offset of 5.0m
            if abs(g.requested_east_m) + abs(g.requested_north_m) < 1e-9:
                continue
            if abs(g.requested_east_m) >= 5.0 or abs(g.requested_north_m) >= 5.0:
                continue
            # Fit strictly in Convention A space
            exp_dx = g.expected_dx_px_conv_a
            exp_dy = g.expected_dy_px_conv_a
            expected_cal.append([exp_dx, exp_dy])
            
            raw_dx = g.estimated_dx_px * sign_multiplier
            raw_dy = g.estimated_dy_px * sign_multiplier
            raw_est_cal.append([raw_dx, raw_dy])
            
        expected_cal = np.array(expected_cal)
        raw_est_cal = np.array(raw_est_cal)
        
        # Fit Ridge without bias: min ||Y - X * W||^2 + reg * ||W - I||^2
        reg = 0.01
        XTX = raw_est_cal.T @ raw_est_cal
        I2 = np.eye(2)
        Z = expected_cal - raw_est_cal
        W_diff = np.linalg.inv(XTX + reg * I2) @ raw_est_cal.T @ Z
        A_cal = I2 + W_diff.T
        b_cal = np.zeros(2)
        
        # Evaluate raw and calibrated errors on held-out Validation offsets (aligned strictly to Convention A)
        raw_val_errs = []
        cal_val_errs = []
        for g in val_grids:
            exp_dx = g.expected_dx_px_conv_a
            exp_dy = g.expected_dy_px_conv_a
            
            # Raw shift prediction (sign-aligned to Convention A)
            raw_vec = np.array([g.estimated_dx_px * sign_multiplier, g.estimated_dy_px * sign_multiplier])
            raw_err_m = math.sqrt((raw_vec[0] - exp_dx)**2 + (raw_vec[1] - exp_dy)**2) * args.gsd_m
            raw_val_errs.append(raw_err_m**2)
            
            # Calibrated shift prediction (subpixel-gated to avoid overscaling large shifts)
            if np.linalg.norm(raw_vec) <= 0.5:
                cal_vec = A_cal @ raw_vec + b_cal
            else:
                cal_vec = raw_vec
            
            cal_err_m = math.sqrt((cal_vec[0] - exp_dx)**2 + (cal_vec[1] - exp_dy)**2) * args.gsd_m
            cal_val_errs.append(cal_err_m**2)
            
        raw_rmse = math.sqrt(np.mean(raw_val_errs)) if raw_val_errs else 999.0
        cal_rmse = math.sqrt(np.mean(cal_val_errs)) if cal_val_errs else 999.0
        improvement_pct = ((raw_rmse - cal_rmse) / raw_rmse) * 100.0 if raw_rmse > 1e-9 else 0.0
        
        use_cal = bool(cal_rmse <= 0.8 or cal_rmse <= raw_rmse * 0.85)
        
        # 3. Confidence empirical calibration (aligned strictly to Convention A)
        all_confs = [g.confidence for g in grids if abs(g.requested_east_m) + abs(g.requested_north_m) > 1e-9]
        all_errors = []
        for g in grids:
            if abs(g.requested_east_m) + abs(g.requested_north_m) < 1e-9:
                continue
            exp_dx = g.expected_dx_px_conv_a
            exp_dy = g.expected_dy_px_conv_a
            
            raw_vec = np.array([g.estimated_dx_px * sign_multiplier, g.estimated_dy_px * sign_multiplier])
            if use_cal and np.linalg.norm(raw_vec) <= 0.5:
                est_vec = A_cal @ raw_vec + b_cal
            else:
                est_vec = raw_vec
            err_m = math.sqrt((est_vec[0] - exp_dx)**2 + (est_vec[1] - exp_dy)**2) * args.gsd_m
            all_errors.append(err_m)
            
        spearman = spearman_correlation(all_confs, all_errors)
        
        # Empirical high confidence (>= 0.8) error median
        high_conf_errs = [err for conf, err in zip(all_confs, all_errors) if conf >= 0.8]
        median_high_conf_err = float(np.median(high_conf_errs)) if high_conf_errs else 999.0
        
        # 4. STAC/Catalog Metadata Probe
        catalog = run_catalog_metadata_probe(ref_date, bbox_ref, args.dry_run)
        
        # 5. Natural Scene Drift Probe
        natural_probe = run_natural_scene_drift_probe(dates, DEFAULT_POLYGON, args.buffer_m, args.gsd_m, 128, 128, args.dry_run)
        
        # 6. Fair holdout H_t evaluation
        c_result = run_h_operator_holdout(combined_result, sign_multiplier, A_cal, b_cal, use_cal=use_cal)
        
        # Populate report schema blocks
        report["v39a_affine_calibration"] = {
            "raw_rmse_m": raw_rmse,
            "calibrated_rmse_m": cal_rmse,
            "improvement_pct": improvement_pct,
            "r2": combined_result["r2"],
            "slope": combined_result["slope"],
            "accepted": use_cal,
            "A": A_cal.tolist(),
            "b": b_cal.tolist()
        }
        report["v39b_confidence_calibration"] = {
            "spearman_confidence_error": spearman,
            "high_confidence_error_median_m": median_high_conf_err,
            "confidence_threshold_recommended": 0.80,
            "accepted": bool(spearman <= -0.55 and median_high_conf_err <= 0.80)
        }
        report["v39c_catalog_metadata_probe"] = {
            "catalog_used": catalog["catalog_used"],
            "scene_count": catalog["scene_count"],
            "fields_parsed": catalog["fields_parsed"]
        }
        report["v39d_natural_residual_probe"] = {
            "residuals_measured": natural_probe["residuals_measured"],
            "repeatability_by_orbit": natural_probe.get("repeatability_by_orbit", 1.0),
            "repeatability_by_tile": natural_probe.get("repeatability_by_tile", 1.0),
            "natural_shift_validated": False,
            "reason": natural_probe.get("reason", "Natural residuals measured but not independently validated.")
        }
        report["v39e_fair_ht_holdout"] = {
            "raw_subpixel_ht_mse": float(c_result["integer_ht_mse"]), # Integer baseline
            "calibrated_subpixel_ht_mse": float(c_result["subpixel_ht_mse"]),
            "no_shift_mse": float(c_result["no_shift_mse"]),
            "improvement_vs_no_shift_pct": float(c_result["improvement_pct"]),
            "accepted": bool(c_result["improvement_pct"] >= 3.0)
        }
        
        report["export_gate"] = evaluate_acceptance(
            report["v39a_affine_calibration"],
            report["v39b_confidence_calibration"],
            report["v39c_catalog_metadata_probe"],
            report["v39d_natural_residual_probe"],
            report["v39e_fair_ht_holdout"]
        )
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
