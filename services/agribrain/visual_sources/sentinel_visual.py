import sys
import json
import urllib.request
from typing import Optional, Dict, Any, List
from visual_sources.cbers import VisualSourceConfig

SENTINEL_STAC_TIMEOUT = 2.0


def find_latest_sentinel_scene(
    bbox: List[float],
    config: VisualSourceConfig
) -> Optional[Dict[str, Any]]:
    """
    Find the latest Sentinel-2 L2A RGB 10m scene matching the bbox.
    
    Sources (in priority order):
      1. AWS Earth Search (element84) — public COG TIFs on S3, no auth needed
      2. Copernicus Dataspace STAC — fallback, uses thumbnail URL
    
    If offline or all STAC queries fail, returns None to allow Esri basemap fallback.
    """
    # 1. Try AWS Earth Search first (best: public COGs with visual composite)
    result = _search_aws_earth_search(bbox, config)
    if result:
        return result
    
    # 2. Fallback: Copernicus Dataspace STAC
    result = _search_copernicus_dataspace(bbox, config)
    if result:
        return result
    
    return None


def _search_aws_earth_search(
    bbox: List[float],
    config: VisualSourceConfig
) -> Optional[Dict[str, Any]]:
    """Search AWS Earth Search (element84) for Sentinel-2 L2A with public COG URLs."""
    try:
        stac_url = "https://earth-search.aws.element84.com/v1/search"
        
        # Try the newer Collection 1 first, then legacy
        for collection in ["sentinel-2-c1-l2a", "sentinel-2-l2a"]:
            payload = {
                "bbox": bbox,
                "collections": [collection],
                "limit": 5,
                "query": {
                    "eo:cloud_cover": {"lt": config.sentinel_max_cloud}
                }
            }
            
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                stac_url,
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            import os
            raw_timeout = os.environ.get("L10_EXTERNAL_PROVIDER_TIMEOUT_MS")
            timeout_val = float(raw_timeout) / 1000.0 if raw_timeout else SENTINEL_STAC_TIMEOUT
            
            with urllib.request.urlopen(req, timeout=timeout_val) as response:
                raw = response.read().decode("utf-8")
                if not raw.strip() or raw.strip().startswith("<"):
                    continue
                    
                res = json.loads(raw)
                features = res.get("features", [])
                if features:
                    features.sort(key=lambda f: f.get("properties", {}).get("datetime", ""), reverse=True)
                    top = features[0]
                    props = top.get("properties", {})
                    assets = top.get("assets", {})
                    
                    # AWS Earth Search asset priority:
                    # 'visual' = pre-rendered RGB composite COG (best for basemap)
                    # 'red'/'green'/'blue' = individual band COGs
                    cog_url = ""
                    for k in ["visual", "red", "thumbnail"]:
                        if k in assets:
                            href = assets[k].get("href", "")
                            if href and not href.startswith("s3://"):
                                cog_url = href
                                break
                            elif href.startswith("s3://"):
                                # Convert s3:// to https:// for public buckets
                                # s3://sentinel-cogs.s3.us-west-2.amazonaws.com/... -> https://...
                                if "sentinel-cogs" in href:
                                    cog_url = href.replace("s3://sentinel-cogs.s3.us-west-2.amazonaws.com/", "https://sentinel-cogs.s3.us-west-2.amazonaws.com/")
                                elif "e84-earth-search" in href:
                                    cog_url = href.replace("s3://", "https://").replace(".s3.us-west-2.amazonaws.com", ".s3.us-west-2.amazonaws.com")
                                else:
                                    cog_url = href
                                break
                    
                    if cog_url:
                        return {
                            "scene_id": top.get("id"),
                            "datetime": props.get("datetime", "2026-01-01")[:10],
                            "collection": collection,
                            "cloud_cover": props.get("eo:cloud_cover", 0.0),
                            "cog_asset": cog_url,
                            "native_resolution_m": 10.0,
                        }
    except Exception as e:
        print(f"[Sentinel-AWS] Search failed: {e}", file=sys.stderr)
    
    return None


def _search_copernicus_dataspace(
    bbox: List[float],
    config: VisualSourceConfig
) -> Optional[Dict[str, Any]]:
    """Search Copernicus Dataspace STAC as fallback."""
    try:
        stac_url = "https://catalogue.dataspace.copernicus.eu/stac/search"
        payload = {
            "bbox": bbox,
            "collections": ["sentinel-2-l2a"],
            "limit": 5,
            "query": {
                "eo:cloud_cover": {"lt": config.sentinel_max_cloud}
            }
        }
        
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            stac_url,
            data=req_data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        import os
        raw_timeout = os.environ.get("L10_EXTERNAL_PROVIDER_TIMEOUT_MS")
        timeout_val = float(raw_timeout) / 1000.0 if raw_timeout else SENTINEL_STAC_TIMEOUT
        
        with urllib.request.urlopen(req, timeout=timeout_val) as response:
            res = json.loads(response.read().decode("utf-8"))
            features = res.get("features", [])
            if features:
                features.sort(key=lambda f: f.get("properties", {}).get("datetime", ""), reverse=True)
                top = features[0]
                props = top.get("properties", {})
                assets = top.get("assets", {})
                
                # Use thumbnail (public HTTPS) or Product download URL
                cog_url = ""
                for k in ["TCI_10m", "TCI_20m", "thumbnail", "Product"]:
                    if k in assets:
                        href = assets[k].get("href", "")
                        if href and not href.startswith("s3://"):
                            cog_url = href
                            break
                
                if cog_url:
                    return {
                        "scene_id": top.get("id"),
                        "datetime": props.get("datetime", "2026-01-01")[:10],
                        "collection": "sentinel-2-l2a",
                        "cloud_cover": props.get("eo:cloud_cover", 0.0),
                        "cog_asset": cog_url,
                        "native_resolution_m": 10.0,
                    }
    except Exception as e:
        print(f"[Sentinel-Copernicus] Search failed: {e}", file=sys.stderr)
    
    return None


