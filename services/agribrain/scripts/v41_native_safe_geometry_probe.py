#!/usr/bin/env python3
"""
V41 — Native SAFE Geometry Feasibility Probe

V40 proved that CDSE/Sentinel Hub Process API rasters are fixed-grid locked.
V41 tests whether native STAC/SAFE/JP2 assets expose any residual geometry
that the Process API hides.

Run from services/agribrain:
    PYTHONPATH=. python scripts/v41_native_safe_geometry_probe.py --max-scenes 12 --max-cloud 20

Dry run:
    PYTHONPATH=. python scripts/v41_native_safe_geometry_probe.py --dry-run

Optional asset download fallback:
    PYTHONPATH=. python scripts/v41_native_safe_geometry_probe.py --max-scenes 12 --max-cloud 20 --download-assets
"""

from __future__ import annotations

import argparse
import json
import math
import os
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

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
DEFAULT_PLOT_ID = "v41_real_polygon_el_oued"

STAC_ENDPOINTS = [
    "https://stac.dataspace.copernicus.eu/v1/search",
    "https://catalogue.dataspace.copernicus.eu/stac/search",
]


def bbox_from_polygon(poly: Any) -> List[float]:
    pts = poly[0]
    xs = [float(p[0]) for p in pts]
    ys = [float(p[1]) for p in pts]
    return [min(xs), min(ys), max(xs), max(ys)]


def expand_bbox_degree(bbox: List[float], buffer_m: float, lat_hint: float) -> List[float]:
    lon_min, lat_min, lon_max, lat_max = bbox
    meters_per_deg_lat = 111320.0
    meters_per_deg_lon = 111320.0 * max(0.2, math.cos(math.radians(lat_hint)))
    dlon = buffer_m / meters_per_deg_lon
    dlat = buffer_m / meters_per_deg_lat
    return [lon_min - dlon, lat_min - dlat, lon_max + dlon, lat_max + dlat]


def safe_float(x: Any, default: float = float("nan")) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def get_access_token_optional() -> Optional[str]:
    try:
        from eo.auth import get_access_token
        return get_access_token()
    except Exception:
        try:
            from eo.sentinel import get_access_token
            return get_access_token()
        except Exception:
            return None


def stac_search(bbox: List[float], days: int, max_cloud: float, limit: int) -> Dict[str, Any]:
    import requests

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    payload = {
        "collections": ["sentinel-2-l2a"],
        "bbox": bbox,
        "datetime": f"{start.date().isoformat()}T00:00:00Z/{end.date().isoformat()}T23:59:59Z",
        "limit": min(100, max(limit * 3, limit)),
        "query": {"eo:cloud_cover": {"lt": max_cloud}},
        "sortby": [{"field": "properties.datetime", "direction": "desc"}],
    }

    token = get_access_token_optional()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    errors = []
    for url in STAC_ENDPOINTS:
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=45)
            if r.status_code == 200:
                data = r.json()
                features = data.get("features", [])
                return {"endpoint": url, "features": features[:limit], "raw_count": len(features)}
            errors.append({"endpoint": url, "status": r.status_code, "text": r.text[:300]})
        except Exception as e:
            errors.append({"endpoint": url, "error": str(e)[:300]})
    return {"endpoint": None, "features": [], "errors": errors}


def parse_scene_metadata(feature: Dict[str, Any]) -> Dict[str, Any]:
    props = feature.get("properties", {})
    assets = feature.get("assets", {})
    return {
        "id": feature.get("id"),
        "datetime": props.get("datetime"),
        "cloud_cover": props.get("eo:cloud_cover", props.get("cloudCover")),
        "relative_orbit": props.get("sat:relative_orbit") or props.get("relativeOrbitNumber"),
        "orbit_direction": props.get("sat:orbit_state") or props.get("orbitDirection"),
        "mgrs_tile": props.get("grid:code") or props.get("tileId") or props.get("s2:mgrs_tile"),
        "processing_baseline": props.get("s2:processing_baseline") or props.get("processingBaseline"),
        "sun_azimuth": props.get("view:sun_azimuth"),
        "sun_elevation": props.get("view:sun_elevation"),
        "view_azimuth": props.get("view:azimuth"),
        "view_incidence_angle": props.get("view:incidence_angle"),
        "asset_keys": list(assets.keys()),
    }


def asset_score(key: str, asset: Dict[str, Any], band: str) -> int:
    text = " ".join([
        key,
        str(asset.get("title", "")),
        str(asset.get("description", "")),
        str(asset.get("href", "")),
        " ".join(asset.get("roles", []) or []),
    ]).lower()
    score = 0
    if band.lower() in text:
        score += 5
    if "jp2" in text or "jpeg2000" in text:
        score += 3
    if "10m" in text and band in ("B04", "B08"):
        score += 2
    if "20m" in text and band == "B11":
        score += 2
    if "visual" in text:
        score -= 2
    return score


def find_band_asset(feature: Dict[str, Any], band: str) -> Optional[Dict[str, Any]]:
    assets = feature.get("assets", {})
    candidates = []
    for k, a in assets.items():
        sc = asset_score(k, a, band)
        if sc > 0:
            candidates.append((sc, k, a))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    sc, key, asset = candidates[0]
    return {"key": key, "href": asset.get("href"), "type": asset.get("type"), "score": sc}


def read_remote_raster_info(href: str, token: Optional[str] = None) -> Dict[str, Any]:
    try:
        import rasterio
        env_kwargs = {}
        if token:
            env_kwargs["GDAL_HTTP_HEADERS"] = f"Authorization: Bearer {token}"
        with rasterio.Env(**env_kwargs):
            with rasterio.open(href) as ds:
                return {
                    "ok": True,
                    "driver": ds.driver,
                    "width": ds.width,
                    "height": ds.height,
                    "count": ds.count,
                    "crs": str(ds.crs),
                    "transform": tuple(ds.transform)[:6],
                    "bounds": list(ds.bounds),
                    "res": list(ds.res),
                }
    except Exception as e:
        return {"ok": False, "error": str(e)[:500]}


def download_asset_if_needed(href: str, out_path: Path, token: Optional[str]) -> Dict[str, Any]:
    import requests
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.get(href, headers=headers, timeout=90, stream=True)
        if r.status_code != 200:
            return {"ok": False, "status": r.status_code, "text": r.text[:300]}
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
        return {"ok": True, "path": str(out_path), "bytes": out_path.stat().st_size}
    except Exception as e:
        return {"ok": False, "error": str(e)[:500]}


def estimate_transform_variance(infos: List[Dict[str, Any]]) -> Dict[str, Any]:
    ok = [x for x in infos if x.get("ok")]
    if len(ok) < 2:
        return {"enough_native_transforms": False, "reason": "Fewer than two readable native rasters.", "readable_count": len(ok)}

    transforms = np.array([x["transform"] for x in ok], dtype=float)
    res = np.array([x["res"] for x in ok], dtype=float)
    origin_x = transforms[:, 2]
    origin_y = transforms[:, 5]
    res_x = res[:, 0]
    res_y = np.abs(res[:, 1])
    return {
        "enough_native_transforms": True,
        "readable_count": len(ok),
        "origin_x_variance": float(np.var(origin_x)),
        "origin_y_variance": float(np.var(origin_y)),
        "res_x_mean": float(np.mean(res_x)),
        "res_y_mean": float(np.mean(res_y)),
        "res_x_variance": float(np.var(res_x)),
        "res_y_variance": float(np.var(res_y)),
        "unique_crs": sorted(list(set(x.get("crs") for x in ok))),
        "sample_transforms": [x["transform"] for x in ok[:3]],
    }


def make_dry_run_features(n: int = 8) -> List[Dict[str, Any]]:
    features = []
    for i in range(n):
        features.append({
            "id": f"DRY_S2_SCENE_{i:02d}",
            "properties": {
                "datetime": f"2026-05-{27-i:02d}T10:20:00Z",
                "eo:cloud_cover": float((i * 3) % 20),
                "sat:relative_orbit": 22 if i % 2 == 0 else 65,
                "sat:orbit_state": "descending",
                "grid:code": "32SLC" if i % 3 else "32SMC",
                "s2:processing_baseline": "05.11",
            },
            "assets": {
                "B04_10m": {"href": f"https://example.invalid/scene_{i}_B04.jp2", "type": "image/jp2"},
                "B08_10m": {"href": f"https://example.invalid/scene_{i}_B08.jp2", "type": "image/jp2"},
                "B11_20m": {"href": f"https://example.invalid/scene_{i}_B11.jp2", "type": "image/jp2"},
            }
        })
    return features


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plot-id", default=DEFAULT_PLOT_ID)
    ap.add_argument("--days", type=int, default=1800)
    ap.add_argument("--max-scenes", type=int, default=12)
    ap.add_argument("--max-cloud", type=float, default=20.0)
    ap.add_argument("--buffer-m", type=float, default=200.0)
    ap.add_argument("--download-assets", action="store_true")
    ap.add_argument("--cache-dir", default="artifacts/v41_native_safe_cache")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default="artifacts/v41_native_safe_geometry_probe_report.json")
    args = ap.parse_args()

    report: Dict[str, Any] = {
        "version": "V41_native_safe_geometry_feasibility_probe",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plot_id": args.plot_id,
        "mode": "dry_run" if args.dry_run else "live_stac_native_asset_probe",
        "purpose": "Determine whether native SAFE/JP2/STAC assets expose geometry residuals that Process API hides.",
        "science_gate": {
            "process_api_natural_shift_validated": False,
            "native_geometry_required": True,
            "production_1m_export_allowed": False,
        },
    }

    try:
        bbox = bbox_from_polygon(DEFAULT_POLYGON)
        buffered_bbox = expand_bbox_degree(bbox, args.buffer_m, DEFAULT_LAT)
        report["query"] = {
            "bbox": bbox,
            "buffered_bbox": buffered_bbox,
            "days": args.days,
            "max_cloud": args.max_cloud,
            "max_scenes": args.max_scenes,
        }

        if args.dry_run:
            features = make_dry_run_features(args.max_scenes)
            endpoint = "dry_run"
            raw_count = len(features)
        else:
            search = stac_search(buffered_bbox, args.days, args.max_cloud, args.max_scenes)
            features = search.get("features", [])
            endpoint = search.get("endpoint")
            raw_count = search.get("raw_count", 0)
            report["stac_search_errors"] = search.get("errors")

        report["stac"] = {"endpoint": endpoint, "raw_count": raw_count, "selected_count": len(features)}

        token = get_access_token_optional()
        scenes = []
        native_infos_by_band = {"B04": [], "B08": [], "B11": []}

        for idx, feat in enumerate(features):
            meta = parse_scene_metadata(feat)
            band_assets = {band: find_band_asset(feat, band) for band in ["B04", "B08", "B11"]}
            meta["band_assets"] = band_assets

            for band, asset in band_assets.items():
                if not asset or not asset.get("href") or args.dry_run:
                    continue
                href = asset["href"]
                info = read_remote_raster_info(href, token=token)
                info.update({"scene_id": meta.get("id"), "datetime": meta.get("datetime"), "band": band, "asset_key": asset.get("key")})

                if not info.get("ok") and args.download_assets:
                    suffix = ".jp2" if ".jp2" in href.lower() else ".bin"
                    local_path = Path(args.cache_dir) / str(meta.get("id", f"scene_{idx}")) / f"{band}{suffix}"
                    dl = download_asset_if_needed(href, local_path, token=token)
                    info["download_attempt"] = dl
                    if dl.get("ok"):
                        info = read_remote_raster_info(str(local_path), token=None)
                        info.update({"scene_id": meta.get("id"), "datetime": meta.get("datetime"), "band": band, "asset_key": asset.get("key"), "local_path": str(local_path)})

                native_infos_by_band[band].append(info)

            scenes.append(meta)

        report["scene_metadata"] = scenes
        report["native_asset_transform_probe"] = {
            band: estimate_transform_variance(native_infos_by_band[band])
            for band in ["B04", "B08", "B11"]
        }

        b04_probe = report["native_asset_transform_probe"]["B04"]
        readable = b04_probe.get("readable_count", 0) if b04_probe.get("enough_native_transforms") else 0
        origin_var = 0.0
        if b04_probe.get("enough_native_transforms"):
            origin_var = max(safe_float(b04_probe.get("origin_x_variance"), 0.0), safe_float(b04_probe.get("origin_y_variance"), 0.0))

        native_geometry_residual_possible = bool(readable >= 2 and origin_var > 0.0)

        report["v41_decision"] = {
            "native_assets_discovered": any(s.get("band_assets", {}).get("B04") for s in scenes),
            "native_rasters_readable": readable >= 2,
            "native_transform_variance_nonzero": origin_var > 0.0,
            "native_geometry_residual_possible": native_geometry_residual_possible,
            "recommended_next": (
                "V42 native JP2 residual-shift holdout test"
                if native_geometry_residual_possible
                else "Proceed with V41A production-safe adaptive Process API MicroZone and keep native geometry research separate"
            ),
        }

        report["export_gate"] = {
            "allow_strong_1m_export": False,
            "allow_controlled_1m_research_mode": True,
            "allow_natural_1m_research_mode": bool(native_geometry_residual_possible),
            "fallback_resolution_policy": "adaptive_2m_to_10m",
            "reason": (
                "Native transform variance suggests possible residual geometry; continue to V42."
                if native_geometry_residual_possible
                else "No usable native residual geometry proven yet."
            ),
        }
        report["status"] = "completed"

    except Exception as e:
        report["status"] = "failed"
        report["error"] = {"type": type(e).__name__, "message": str(e)}
        report["traceback"] = traceback.format_exc()[-5000:]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
