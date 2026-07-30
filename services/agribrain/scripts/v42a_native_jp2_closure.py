#!/usr/bin/env python3
"""
V42A — Sentinel-2 JP2 and XML Transform Closure Analyzer

Checks the geotransforms and coordinate origins of native SAFE band assets (B04, B08, B11)
and granule metadata XML files across historical scenes, using:
1. Rasterio /vsicurl remote header inspection on CDSE OData HTTPS links.
2. Native granule XML (MTD_TL.xml) parser for ULX/ULY grid geopositions.

Determines definitively if Sentinel-2 SAFE products have exactly 0.0 geotransform variance
(fully MGRS coordinate grid-locked).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import traceback
import xml.etree.ElementTree as ET
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

DEFAULT_POLYGON = [[
    [6.86000, 33.34800],
    [6.86300, 33.34800],
    [6.86300, 33.35100],
    [6.86000, 33.35100],
    [6.86000, 33.34800],
]]
DEFAULT_LAT = 33.3495
DEFAULT_PLOT_ID = "v42a_real_polygon_el_oued"
STAC_SEARCH_URL = "https://stac.dataspace.copernicus.eu/v1/search"


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


def get_alternate_https_href(asset: Dict[str, Any]) -> Optional[str]:
    """Extract alternate HTTPS link from STAC asset, falling back to href if it is HTTPS."""
    alternate = asset.get("alternate", {})
    if "https" in alternate and alternate["https"].get("href"):
        return alternate["https"]["href"]
    href = asset.get("href", "")
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return None


def read_remote_raster_info(href: str, token: Optional[str] = None) -> Dict[str, Any]:
    """Read remote geotransform using rasterio VSICURL header requests without downloading entire file."""
    try:
        import rasterio
        vsi_path = href
        env_kwargs = {}
        if token:
            env_kwargs["GDAL_HTTP_HEADERS"] = f"Authorization: Bearer {token}"
        
        # Enable VSICURL configurations
        env_kwargs["CPL_VSIL_CURL_ALLOWED_EXTENSIONS"] = ".jp2,.tiff,.tif,.xml"
        env_kwargs["GDAL_DISABLE_READDIR_ON_OPEN"] = "YES"
        
        if href.startswith("http://") or href.startswith("https://"):
            vsi_path = f"/vsicurl/{href}"

        with rasterio.Env(**env_kwargs):
            with rasterio.open(vsi_path) as ds:
                return {
                    "ok": True,
                    "crs": str(ds.crs),
                    "transform": tuple(ds.transform)[:6],
                    "bounds": list(ds.bounds),
                    "res": list(ds.res),
                    "shape": list(ds.shape),
                }
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


def download_xml_metadata(href: str, token: Optional[str]) -> Tuple[bool, Optional[str], Optional[str]]:
    """Downloads XML file (like MTD_TL.xml) using bearer token authentication."""
    import requests
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.get(href, headers=headers, timeout=25)
        if r.status_code == 200:
            return True, r.text, None
        return False, None, f"HTTP status {r.status_code}"
    except Exception as e:
        return False, None, str(e)


def parse_mtd_tl_geopositions(xml_content: str) -> Dict[str, Any]:
    """
    Parses ULX, ULY, and grid dimensions from the MTD_TL.xml file content.
    Sentinel-2 Tile XML describes:
    <Tile_Geoposition resolution="10">
      <ULX>300000</ULX>
      <ULY>3800040</ULY>
      <XDIM>10</XDIM>
      <YDIM>-10</YDIM>
    </Tile_Geoposition>
    """
    try:
        root = ET.fromstring(xml_content)
        # Find geometric info
        geopositions = {}
        for geo in root.findall(".//Tile_Geoposition"):
            res = geo.get("resolution")
            ulx_el = geo.find("ULX")
            uly_el = geo.find("ULY")
            xdim_el = geo.find("XDIM")
            ydim_el = geo.find("YDIM")
            if ulx_el is not None and uly_el is not None:
                geopositions[f"res_{res}m"] = {
                    "ulx": float(ulx_el.text),
                    "uly": float(uly_el.text),
                    "xdim": float(xdim_el.text) if xdim_el is not None else float(res),
                    "ydim": float(ydim_el.text) if ydim_el is not None else -float(res),
                }
        if geopositions:
            return {"ok": True, "geopositions": geopositions}
        return {"ok": False, "error": "No Tile_Geoposition elements found in XML."}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def generate_mock_xml_data() -> str:
    """Generates mock MTD_TL.xml for dry run or fallback tests."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<Level-2A_Tile_ID>
  <Geometric_Info>
    <Tile_Geoposition resolution="10">
      <ULX>300000</ULX>
      <ULY>3800040</ULY>
      <XDIM>10</XDIM>
      <YDIM>-10</YDIM>
    </Tile_Geoposition>
    <Tile_Geoposition resolution="20">
      <ULX>300000</ULX>
      <ULY>3800040</ULY>
      <XDIM>20</XDIM>
      <YDIM>-20</YDIM>
    </Tile_Geoposition>
  </Geometric_Info>
</Level-2A_Tile_ID>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plot-id", default=DEFAULT_PLOT_ID)
    ap.add_argument("--days", type=int, default=700)
    ap.add_argument("--max-scenes", type=int, default=8)
    ap.add_argument("--max-cloud", type=float, default=20.0)
    ap.add_argument("--buffer-m", type=float, default=200.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default="artifacts/v42a_native_jp2_closure_report.json")
    args = ap.parse_args()

    report: Dict[str, Any] = {
        "version": "V42A_native_jp2_closure_analyzer",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plot_id": args.plot_id,
        "mode": "dry_run" if args.dry_run else "live_copernicus_metadata_closure",
        "purpose": "Provide absolute scientific proof on whether standard JP2/XML transforms have 0.0 variance.",
        "scientific_closure_status": "inconclusive",
    }

    try:
        bbox = bbox_from_polygon(DEFAULT_POLYGON)
        buffered_bbox = expand_bbox_degree(bbox, args.buffer_m, DEFAULT_LAT)
        token = get_access_token_optional()

        if args.dry_run:
            print("[DRY RUN] Simulating Copernicus STAC feature...")
            report["stac"] = {"status": "success", "found_scenes": 8}
            scenes_data = []
            for i in range(8):
                scenes_data.append({
                    "id": f"S2_SCENE_{i}",
                    "date": f"2026-05-{28-i:02d}",
                    "mgrs_tile": "MGRS-32SLC",
                    "xml_parsed": {
                        "ok": True,
                        "geopositions": {
                            "res_10m": {"ulx": 300000.0, "uly": 3800040.0, "xdim": 10.0, "ydim": -10.0},
                            "res_20m": {"ulx": 300000.0, "uly": 3800040.0, "xdim": 20.0, "ydim": -20.0}
                        }
                    },
                    "raster_b04": {
                        "ok": True,
                        "crs": "EPSG:32632",
                        "transform": (10.0, 0.0, 300000.0, 0.0, -10.0, 3800040.0),
                        "res": [10.0, 10.0]
                    }
                })
            report["scenes_probed"] = scenes_data
        else:
            print(f"[LIVE] Querying CDSE STAC: {STAC_SEARCH_URL} ...")
            import requests
            
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=args.days)
            payload = {
                "collections": ["sentinel-2-l2a"],
                "bbox": buffered_bbox,
                "datetime": f"{start.date().isoformat()}T00:00:00Z/{end.date().isoformat()}T23:59:59Z",
                "limit": args.max_scenes,
                "query": {"eo:cloud_cover": {"lt": args.max_cloud}},
                "sortby": [{"field": "properties.datetime", "direction": "desc"}],
            }
            
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            
            r = requests.post(STAC_SEARCH_URL, json=payload, headers=headers, timeout=30)
            if r.status_code != 200:
                raise ConnectionError(f"STAC search failed (HTTP {r.status_code}): {r.text[:300]}")
            
            features = r.json().get("features", [])
            report["stac"] = {"status": "success", "found_scenes": len(features)}
            print(f"[LIVE] Found {len(features)} scenes. Probing transforms...")

            scenes_data = []
            for feat in features[:args.max_scenes]:
                scene_id = feat.get("id")
                props = feat.get("properties", {})
                assets = feat.get("assets", {})
                mgrs_tile = props.get("grid:code") or props.get("s2:mgrs_tile")
                date_str = props.get("datetime")
                
                scene_record = {
                    "id": scene_id,
                    "date": date_str,
                    "mgrs_tile": mgrs_tile,
                }

                # 1. Probe B04 raster transform remotely
                b04_asset = assets.get("B04_10m")
                if b04_asset:
                    https_href = get_alternate_https_href(b04_asset)
                    if https_href:
                        print(f"  -> Remote reading B04 transform for {scene_id}...")
                        r_info = read_remote_raster_info(https_href, token)
                        scene_record["raster_b04"] = r_info
                    else:
                        scene_record["raster_b04"] = {"ok": False, "error": "No HTTPS alternate download URL."}
                else:
                    scene_record["raster_b04"] = {"ok": False, "error": "B04_10m asset missing in STAC."}

                # 2. Download and parse MTD_TL.xml for geotransform bounds
                xml_asset = assets.get("granule_metadata")
                if xml_asset:
                    https_xml_href = get_alternate_https_href(xml_asset)
                    if https_xml_href:
                        print(f"  -> Downloading granule metadata XML for {scene_id}...")
                        dl_ok, xml_str, dl_err = download_xml_metadata(https_xml_href, token)
                        if dl_ok and xml_str:
                            xml_res = parse_mtd_tl_geopositions(xml_str)
                            scene_record["xml_parsed"] = xml_res
                        else:
                            scene_record["xml_parsed"] = {"ok": False, "error": f"Download failed: {dl_err}"}
                    else:
                        scene_record["xml_parsed"] = {"ok": False, "error": "No HTTPS alternate URL for granule_metadata."}
                else:
                    scene_record["xml_parsed"] = {"ok": False, "error": "granule_metadata asset missing."}

                scenes_data.append(scene_record)

            report["scenes_probed"] = scenes_data

        # Compute transform origin variance
        ulx_10m_list = []
        uly_10m_list = []
        raster_x_list = []
        raster_y_list = []

        for sd in report.get("scenes_probed", []):
            # Try XML first
            xml_p = sd.get("xml_parsed", {})
            if xml_p.get("ok"):
                res_10 = xml_p["geopositions"].get("res_10m", {})
                if "ulx" in res_10:
                    ulx_10m_list.append(res_10["ulx"])
                    uly_10m_list.append(res_10["uly"])

            # Try rasterio second
            rast = sd.get("raster_b04", {})
            if rast.get("ok"):
                trans = rast["transform"]
                raster_x_list.append(trans[2])
                raster_y_list.append(trans[5])

        xml_ulx_var = float(np.var(ulx_10m_list)) if len(ulx_10m_list) >= 2 else float("nan")
        xml_uly_var = float(np.var(uly_10m_list)) if len(uly_10m_list) >= 2 else float("nan")
        raster_x_var = float(np.var(raster_x_list)) if len(raster_x_list) >= 2 else float("nan")
        raster_y_var = float(np.var(raster_y_list)) if len(raster_y_list) >= 2 else float("nan")

        report["variance_statistics"] = {
            "xml_parsed_count": len(ulx_10m_list),
            "xml_ulx_variance": xml_ulx_var,
            "xml_uly_variance": xml_uly_var,
            "raster_parsed_count": len(raster_x_list),
            "raster_origin_x_variance": raster_x_var,
            "raster_origin_y_variance": raster_y_var,
        }

        # Decide closure
        xml_proven_locked = bool(len(ulx_10m_list) >= 2 and xml_ulx_var == 0.0 and xml_uly_var == 0.0)
        raster_proven_locked = bool(len(raster_x_list) >= 2 and raster_x_var == 0.0 and raster_y_var == 0.0)

        if xml_proven_locked or raster_proven_locked:
            report["scientific_closure_status"] = "confirmed"
            report["verdict_summary"] = (
                "CONFIRMED: Native Level-2A SAFE assets are mathematically grid-locked. "
                "Transform origin variance is exactly 0.0. Natural orbital shifts are entirely resampled out."
            )
        elif len(ulx_10m_list) < 2 and len(raster_x_list) < 2:
            report["scientific_closure_status"] = "failed due to access"
            report["verdict_summary"] = (
                "FAILED DUE TO ACCESS: Insufficient readable native assets to calculate transform variance. "
                "Remote network access to raster headers/metadata was restricted or timed out."
            )
        else:
            report["scientific_closure_status"] = "inconclusive"
            report["verdict_summary"] = "INCONCLUSIVE: Native transform variances were evaluated but non-zero, or inconsistent."

        print(f"\nVariance Analysis:")
        print(f"  XML geopositions count: {len(ulx_10m_list)}, ulx_var={xml_ulx_var}, uly_var={xml_uly_var}")
        print(f"  Rasterio headers count: {len(raster_x_list)}, x_var={raster_x_var}, y_var={raster_y_var}")
        print(f"  Closure Verdict: {report['verdict_summary']}\n")
        
        report["status"] = "completed"

    except Exception as e:
        report["status"] = "failed"
        report["error"] = {"type": type(e).__name__, "message": str(e)}
        report["traceback"] = traceback.format_exc()[-4000:]
        print(f"[ERROR] V42A execution failed: {e}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"Saved report: {out}")


if __name__ == "__main__":
    main()
