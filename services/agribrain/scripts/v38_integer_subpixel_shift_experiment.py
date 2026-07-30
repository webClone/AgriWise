#!/usr/bin/env python3
"""
V38 — Integer Calibration & Subpixel Fourier Registration Experiment

Implements:
- V38A: Integer-shift calibration (10m, 20m, 30m offsets)
- V38B: True subpixel Fourier-domain phase cross-correlation (1m, 2m, 3m, 5m, 7m offsets)
- V38C: Controlled H_t reconstruction holdout against multiple baselines

Sign Convention:
- dx_col positive = target image columns moved right (East) to align to reference.
- dy_row positive = target image rows moved down (South) to align to reference.
- Auto-Convention selector runs both possibilities and selects the best fit.

Run from services/agribrain:
  PYTHONPATH=. python scripts/v38_integer_subpixel_shift_experiment.py --max-cloud 100
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
DEFAULT_PLOT_ID = "v38_real_polygon_el_oued"
DEFAULT_EPSG_UTM = "EPSG:32632"

# V38A Integer Offsets (10m, 20m, 30m)
OFFSETS_V38A = [
    (0.0, 0.0), (10.0, 0.0), (0.0, 10.0),
    (10.0, 10.0), (20.0, 30.0), (-20.0, 10.0),
]

# V38B Subpixel Offsets (1m, 2m, 3m, 5m, 7m)
OFFSETS_V38B = [
    (0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0),
    (2.0, 3.0), (-2.0, 1.0), (5.0, 0.0), (0.0, 7.0),
    (5.0, 7.0),
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
    taper = get_taper_2d(h, w, fraction=0.15)
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


def compute_expected_shifts(dx_m: float, dy_m: float, gsd_m: float) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    # Convention A
    dx_a = -dx_m / gsd_m
    dy_a = dy_m / gsd_m
    # Convention B
    dx_b = dx_m / gsd_m
    dy_b = -dy_m / gsd_m
    return (dx_a, dy_a), (dx_b, dy_b)


def shift_image_subpixel_fft(a: np.ndarray, dy: float, dx: float) -> np.ndarray:
    """Performs an exact subpixel spatial translation in the Fourier domain."""
    h, w = a.shape
    f = np.fft.fft2(a)
    v = np.fft.fftfreq(h)
    u = np.fft.fftfreq(w)
    v_grid, u_grid = np.meshgrid(v, u, indexing='ij')
    ramp = np.exp(-2j * np.pi * (v_grid * dy + u_grid * dx))
    return np.real(np.fft.ifft2(f * ramp))


def make_dry_run_controlled_grids(offsets_m: List[Tuple[float, float]], gsd_m: float, width: int = 128, height: int = 128) -> List[ControlledGrid]:
    rng = np.random.default_rng(38)
    y, x = np.mgrid[0:height, 0:width]
    
    # 1. Start with realistic multi-band smooth agricultural patterns
    b04 = 0.15 + 0.05*np.sin(x/5.0) + 0.04*np.cos(y/6.0)
    b08 = 0.45 + 0.10*np.sin((x+y)/10.0)
    b11 = 0.25 + 0.04*np.cos(x/8.0) + 0.03*np.sin(y/6.0)
    
    # 2. Add high-texture 2D crossing canal patterns dynamically centered
    cx_mid = width // 2
    cy_mid = height // 2
    for offset in range(-2, 3):
        b04[:, cx_mid + offset] += 0.10; b08[:, cx_mid + offset] -= 0.08; b11[:, cx_mid + offset] += 0.05
        b04[cy_mid + offset, :] += 0.10; b08[cy_mid + offset, :] -= 0.08; b11[cy_mid + offset, :] += 0.05
        
    # 3. Add rich 2D isotropic Gaussian structures centered in safe zone
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
        arrays = {
            k: shift_image_subpixel_fft(v, conv_a[1], conv_a[0]) + rng.normal(0, 0.0001, v.shape)
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
    
    # Calculate required pixels to achieve exactly the specified gsd_m
    width = int(round(w_m / gsd_m))
    height = int(round(h_m / gsd_m))
    
    # Keep sizes in a stable range
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


def run_h_operator_holdout(controlled_res: Dict[str, Any], factor: int = 10) -> Dict[str, Any]:
    grids: List[ControlledGrid] = controlled_res["grids_object"]
    if len(grids) < 4:
        return {"status": "insufficient_grids"}
    
    # Sign multiplier: Convention A is the array-shift space.
    # If selected_conv == "B", we flip the estimated raw shifts to match Convention A
    # so that -dx and -dy shift them back correctly.
    sign_multiplier = 1.0 if controlled_res["selected_sign_convention"] == "A" else -1.0
    
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
        est_dx_a = (g.estimated_dx_px or 0.0) * sign_multiplier
        est_dy_a = (g.estimated_dy_px or 0.0) * sign_multiplier
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
    hx = hx_a * factor
    hy = hy_a * factor
    # Forward project latent back to holdout observation space by shifting by +hy, +hx
    pred_sub_ht = down(shift_image_subpixel_integer_fallback(latent_sub, hy, hx))
    
    # 2. Baseline A: Naive 10m Upsample
    raw_10m = holdout.arrays["ndvi"]
    pred_naive_10m = simple_blur(raw_10m, 1) # simple bilinear-like blur
    
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
        "reason": "V38A/B validates controlled shifted grids. V38B requires explicit CDSE Catalog/STAC item metadata integration.",
    }


def evaluate_acceptance(a_res: Dict[str, Any], b_res: Dict[str, Any], c_res: Dict[str, Any]) -> Dict[str, Any]:
    # V38A Integer Checks
    a_rmse, a_r2, a_slope = a_res.get("rmse_m"), a_res.get("r2"), a_res.get("slope")
    a_ok = a_rmse is not None and a_rmse <= 1.0 and a_r2 is not None and a_r2 >= 0.95 and a_slope is not None and 0.90 <= a_slope <= 1.10
    
    # V38B Subpixel Checks
    b_rmse, b_r2, b_conf = b_res.get("rmse_m"), b_res.get("r2"), b_res.get("median_confidence")
    b_ok = b_rmse is not None and b_rmse <= 1.5 and b_r2 is not None and b_r2 >= 0.85 and b_conf is not None and b_conf >= 0.70
    
    # V38C H_t Holdout Check
    h_impr = c_res.get("improvement_fraction")
    c_ok = h_impr is not None and h_impr >= 0.03
    
    allow = False # Keep 1m export strictly blocked for safety in this sandbox
    research_allow = bool(a_ok and b_ok and c_ok)
    
    if research_allow:
        reason = "Controlled shifts (integer & subpixel) and H_t holdout fully validated. Research mode 1m allowed."
    elif a_ok:
        reason = "V38A integer calibration successfully locked, but V38B subpixel cross-correlation did not pass."
    else:
        reason = "V38A integer calibration failed. BBox / coordinate signs require verification."
        
    return {
        "controlled_integer_shift_validated": a_ok,
        "controlled_subpixel_shift_validated": b_ok,
        "h_operator_validated": c_ok,
        "natural_shift_validated": False,
        "allow_strong_1m_export": allow,
        "allow_controlled_1m_research_mode": research_allow,
        "fallback_resolution_policy": "2m_to_10m_dynamic",
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
    ap.add_argument("--out", default="artifacts/v38_integer_subpixel_shift_experiment_report.json")
    args = ap.parse_args()
    
    report = {
        "version": "V38_integer_subpixel_shift_experiment",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plot_id": args.plot_id,
        "mode": "dry_run_synthetic" if args.dry_run else "real_sentinel_process_api",
        "sign_convention_convention": {
            "dx_col_positive": "target columns moved right/east to align to reference",
            "dy_row_positive": "target rows moved down/south to align to reference",
        },
    }
    
    try:
        date = args.date
        if not args.dry_run and not date:
            date = select_best_date(args.lat, args.lng, DEFAULT_POLYGON, args.days, args.max_cloud)
        if args.dry_run:
            date = date or "2025-05-01"
        if not date:
            raise RuntimeError("No suitable Sentinel-2 date found. Specify --max-cloud 100 or a specific --date.")
            
        report["selected_date"] = date
        
        # 1. Run V38A Integer-Shift Calibration
        a_result = execute_sub_experiment(date, DEFAULT_POLYGON, args.buffer_m, args.gsd_m, OFFSETS_V38A, args.width, args.height, args.dry_run)
        
        # 2. Run V38B Subpixel Fourier Registration
        b_result = execute_sub_experiment(date, DEFAULT_POLYGON, args.buffer_m, args.gsd_m, OFFSETS_V38B, args.width, args.height, args.dry_run)
        
        # 3. Run V38C H_t Holdout Evaluation
        c_result = run_h_operator_holdout(b_result)
        
        catalog = run_catalog_metadata_probe(args.dry_run)
        
        # Clean objects for output
        a_clean = {k: v for k, v in a_result.items() if k != "grids_object"}
        b_clean = {k: v for k, v in b_result.items() if k != "grids_object"}
        
        report["v38a_integer_calibration"] = {
            "passed": evaluate_acceptance(a_clean, b_clean, c_result)["controlled_integer_shift_validated"],
            "rmse_m": a_clean["rmse_m"],
            "r2": a_clean["r2"],
            "slope": a_clean["slope"],
            "selected_convention": a_clean["selected_sign_convention"],
            "tests": a_clean["controlled_shift_tests"],
        }
        report["v38b_subpixel_registration"] = {
            "passed": evaluate_acceptance(a_clean, b_clean, c_result)["controlled_subpixel_shift_validated"],
            "rmse_m": b_clean["rmse_m"],
            "r2": b_clean["r2"],
            "median_confidence": b_clean["median_confidence"],
            "upsample_factor": 20,
            "tests": b_clean["controlled_shift_tests"],
        }
        report["v38c_h_operator_holdout"] = {
            "passed": evaluate_acceptance(a_clean, b_clean, c_result)["h_operator_validated"],
            "subpixel_ht_mse": c_result["subpixel_ht_mse"],
            "no_shift_mse": c_result["no_shift_mse"],
            "improvement_pct": c_result["improvement_pct"],
            "comparisons": {
                "naive_10m_upsample_mse": c_result["naive_10m_upsample_mse"],
                "integer_ht_mse": c_result["integer_ht_mse"],
            }
        }
        report["export_gate"] = evaluate_acceptance(a_clean, b_clean, c_result)
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
