import sys
import json
import urllib.request
from typing import Optional, Dict, Any, List
from visual_sources.cbers import VisualSourceConfig

LANDSAT_STAC_TIMEOUT = 2.0


def find_latest_landsat_scene(
    bbox: List[float],
    config: VisualSourceConfig
) -> Optional[Dict[str, Any]]:
    """
    Find the latest Landsat Collection 2 Level-2 scene matching the bbox.
    Uses AWS Earth Search (element84) which hosts public Landsat COGs.
    
    Landsat 8/9 OLI provides ~30m visual imagery — lower res than Sentinel-2
    but good as a third fallback tier.
    
    If offline or STAC fails, returns None to allow Esri fallback.
    """
    try:
        stac_url = "https://earth-search.aws.element84.com/v1/search"
        payload = {
            "bbox": bbox,
            "collections": ["landsat-c2-l2"],
            "limit": 5,
            "query": {
                "eo:cloud_cover": {"lt": config.landsat_max_cloud}
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
        timeout_val = float(raw_timeout) / 1000.0 if raw_timeout else LANDSAT_STAC_TIMEOUT
        
        with urllib.request.urlopen(req, timeout=timeout_val) as response:
            raw = response.read().decode("utf-8")
            if not raw.strip() or raw.strip().startswith("<"):
                return None
            
            res = json.loads(raw)
            features = res.get("features", [])
            if features:
                features.sort(key=lambda f: f.get("properties", {}).get("datetime", ""), reverse=True)
                top = features[0]
                props = top.get("properties", {})
                assets = top.get("assets", {})
                
                # Landsat visual asset priority:
                # 'reduced_resolution_browse' = pre-rendered visual browse image
                # 'thumbnail' = smaller preview
                # Individual bands: 'red', 'green', 'blue' if available
                cog_url = ""
                for k in ["reduced_resolution_browse", "thumbnail", "red"]:
                    if k in assets:
                        href = assets[k].get("href", "")
                        # Convert s3:// to HTTPS for public USGS bucket
                        if href.startswith("s3://usgs-landsat/"):
                            href = "https://usgs-landsat.s3.us-west-2.amazonaws.com/" + href[len("s3://usgs-landsat/"):]
                        if href:
                            cog_url = href
                            break
                
                if cog_url:
                    return {
                        "scene_id": top.get("id"),
                        "datetime": props.get("datetime", "2026-01-01")[:10],
                        "collection": "landsat-c2-l2",
                        "cloud_cover": props.get("eo:cloud_cover", 0.0),
                        "cog_asset": cog_url,
                        "native_resolution_m": 30.0,
                    }
    except Exception as e:
        print(f"[Landsat-AWS] Search failed: {e}", file=sys.stderr)
    
    return None
