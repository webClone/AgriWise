import sys
import os
import json
import urllib.request
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

@dataclass(frozen=True)
class VisualSourceConfig:
    cbers_max_cloud: float = 40.0
    sentinel_max_cloud: float = 20.0
    landsat_max_cloud: float = 20.0
    max_scene_age_days: Optional[int] = None
    prefer_provider: str = "cbers"

CBERS_STAC_TIMEOUT = 2.0


def find_latest_cbers_scene(
    bbox: List[float],
    config: VisualSourceConfig
) -> Optional[Dict[str, Any]]:
    """
    Find the latest CBERS-4A WPM 2m visual scene matching the bbox.
    Queries the INPE STAC catalog at data.inpe.br.
    
    Searches multiple collections:
      1. CB4A-WPM-PCA-FUSED-1 — pan-sharpened RGB (mainly Brazil)
      2. CB4A-WPM-L2-DN-1 — Level-2 raw bands (global coverage incl. Algeria)
    
    If offline or STAC fails, returns None to allow Sentinel/Landsat/Esri fallback.
    """
    stac_url = "https://data.inpe.br/bdc/stac/v1/search"
    
    # Search both PCA-FUSED (pre-rendered RGB, preferred) and L2-DN (raw bands, global)
    collections_to_try = [
        "CB4A-WPM-PCA-FUSED-1",  # Pan-sharpened RGB composite (Brazil mainly)
        "CB4A-WPM-L2-DN-1",      # Level-2 DN raw bands (global, incl. Algeria)
    ]
    
    for collection in collections_to_try:
        try:
            payload = {
                "bbox": bbox,
                "collections": [collection],
                "limit": 5,
            }
            
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                stac_url,
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            raw_timeout = os.environ.get("L10_EXTERNAL_PROVIDER_TIMEOUT_MS")
            timeout_val = float(raw_timeout) / 1000.0 if raw_timeout else CBERS_STAC_TIMEOUT
            
            with urllib.request.urlopen(req, timeout=timeout_val) as response:
                raw = response.read().decode("utf-8")
                if not raw.strip() or raw.strip().startswith("<"):
                    continue
                
                res = json.loads(raw)
                features = res.get("features", [])
                if features:
                    # Sort by date descending to get the latest scene
                    features.sort(key=lambda f: f.get("properties", {}).get("datetime", ""), reverse=True)
                    top = features[0]
                    props = top.get("properties", {})
                    assets = top.get("assets", {})
                    
                    # Asset priority:
                    # PCA-FUSED: 'tci' (True Color Image GeoTIFF)
                    # L2-DN: 'BAND0' (panchromatic), 'BAND1/2/3' (RGB), 'thumbnail'
                    cog_url = ""
                    for k in ["tci", "BAND1", "BAND0", "visual", "thumbnail"]:
                        if k in assets:
                            cog_url = assets[k].get("href", "")
                            break
                    
                    if not cog_url and assets:
                        # Fallback to first asset href
                        cog_url = list(assets.values())[0].get("href", "")
                    
                    if cog_url:
                        return {
                            "scene_id": top.get("id"),
                            "datetime": props.get("datetime", "2026-01-01")[:10],
                            "collection": collection,
                            "cloud_cover": props.get("eo:cloud_cover", 0.0),
                            "cog_asset": cog_url,
                            "native_resolution_m": 2.0,
                        }
        except Exception as e:
            print(f"[CBERS-STAC] Search failed for {collection}: {e}", file=sys.stderr)
    
    return None
