"""
Satellite RGB Tile Runtime — Fetches actual Sentinel-2 True Color tiles.

This runtime is triggered when a user enters a plot page. It:
  1. Checks if a cached tile exists and is < 7 days old
  2. If not, fetches a new True Color RGB tile from Sentinel Hub Process API
  3. Saves the PNG bytes to a local cache directory
  4. Returns the image bytes for downstream LLM vision analysis

The tile is clipped to the plot polygon and returned as a PNG image.
This is the bridge between real satellite imagery and the LLM vision engine.
"""

import os
import io
import json
import time
import math
import logging
import hashlib
import requests
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Cache directory for satellite tiles
TILE_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "artifacts", "satellite_tiles")
CACHE_MAX_AGE_SECONDS = 7 * 24 * 3600  # 7 days

# ── Vision Result Cache (cross-pipeline access) ──────────────────────────────
# Stores the latest LLM vision observation per plot so the orchestrator can
# use it to enrich fallback guidance when raster zone data is unavailable.
_VISION_CACHE: Dict[str, Dict[str, Any]] = {}

def cache_vision_result(plot_id: str, vision: Dict[str, Any]) -> None:
    """Cache the latest satellite vision observation for a plot."""
    _VISION_CACHE[plot_id] = {
        **vision,
        "_cached_at": time.time(),
    }
    logger.info(f"[Vision Cache] Stored vision result for plot {plot_id}")

def get_cached_vision(plot_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve the cached vision result for a plot (max 24h old)."""
    entry = _VISION_CACHE.get(plot_id)
    if entry and (time.time() - entry.get("_cached_at", 0)) < 24 * 3600:
        return entry
    return None

SENTINEL_HUB_URL = "https://sh.dataspace.copernicus.eu"
SENTINEL_PROCESS_URL = f"{SENTINEL_HUB_URL}/api/v1/process"
SENTINEL_AUTH_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"

# Auth token cache (shared with eo/sentinel.py via env)
_token_cache = {"access_token": None, "expires_at": 0}


def _get_access_token() -> str:
    """Get Sentinel Hub OAuth2 token (lightweight, own cache to avoid circular imports)."""
    global _token_cache
    if _token_cache["access_token"] and time.time() < _token_cache["expires_at"]:
        return _token_cache["access_token"]

    client_id = os.getenv("SENTINEL_HUB_CLIENT_ID")
    client_secret = os.getenv("SENTINEL_HUB_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise ValueError("Missing SENTINEL_HUB_CLIENT_ID or SENTINEL_HUB_CLIENT_SECRET")

    resp = requests.post(SENTINEL_AUTH_URL, data={
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }, timeout=10)

    if resp.status_code != 200:
        raise ConnectionError(f"Sentinel Hub auth failed: HTTP {resp.status_code}")

    data = resp.json()
    _token_cache["access_token"] = data["access_token"]
    _token_cache["expires_at"] = time.time() + data["expires_in"] - 60
    return _token_cache["access_token"]


def _plot_id_hash(plot_id: str) -> str:
    """Deterministic short hash for cache filenames."""
    return hashlib.sha256(plot_id.encode()).hexdigest()[:16]


def _get_cache_path(plot_id: str) -> str:
    """Return the cache file path for a given plot."""
    os.makedirs(TILE_CACHE_DIR, exist_ok=True)
    return os.path.join(TILE_CACHE_DIR, f"tile_{_plot_id_hash(plot_id)}.png")


def _get_meta_path(plot_id: str) -> str:
    """Return the metadata cache file path."""
    os.makedirs(TILE_CACHE_DIR, exist_ok=True)
    return os.path.join(TILE_CACHE_DIR, f"tile_{_plot_id_hash(plot_id)}.json")


def _is_cache_valid(plot_id: str) -> bool:
    """Check if a cached tile exists and is less than 7 days old."""
    meta_path = _get_meta_path(plot_id)
    if not os.path.exists(meta_path):
        return False
    try:
        with open(meta_path, "r") as f:
            meta = json.load(f)
        fetched_at = meta.get("fetched_at", 0)
        return (time.time() - fetched_at) < CACHE_MAX_AGE_SECONDS
    except Exception:
        return False


def _build_bounds(polygon_coords: Any, lat: float, lng: float, buffer: float = 0.003) -> Dict:
    """Build bounds for Process API from polygon or fallback to bbox."""
    coords = None
    if isinstance(polygon_coords, dict):
        geom = polygon_coords.get("geometry", polygon_coords) if polygon_coords.get("type") == "Feature" else polygon_coords
        if "coordinates" in geom:
            if geom.get("type") == "Polygon":
                coords = geom["coordinates"][0]
            elif geom.get("type") == "MultiPolygon":
                coords = geom["coordinates"][0][0]
    elif isinstance(polygon_coords, list):
        if len(polygon_coords) > 0 and isinstance(polygon_coords[0], list):
            coords = polygon_coords[0] if isinstance(polygon_coords[0][0], list) else polygon_coords

    if coords and len(coords) >= 3:
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        if coords[0] != coords[-1]:
            coords = list(coords) + [coords[0]]
        return {
            "bbox": [min(xs), min(ys), max(xs), max(ys)],
            "geometry": {"type": "Polygon", "coordinates": [coords]},
            "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
        }

    return {
        "bbox": [lng - buffer, lat - buffer, lng + buffer, lat + buffer],
        "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
    }


def _compute_dimensions(polygon_coords: Any, lat: float, lng: float,
                         target_resolution_m: float = 2.5, max_dim: int = 512,
                         min_dim: int = 256) -> Tuple[int, int]:
    """Compute pixel dimensions for the tile.
    
    Uses 2.5m/pixel for sharp display imagery (Sentinel-2 native is 10m
    for RGB bands, but the Process API resamples smoothly).
    Enforces a minimum of 256px to avoid pixelated UI.
    """
    coords = None
    if isinstance(polygon_coords, dict):
        geom = polygon_coords.get("geometry", polygon_coords) if polygon_coords.get("type") == "Feature" else polygon_coords
        if "coordinates" in geom:
            if geom.get("type") == "Polygon":
                coords = geom["coordinates"][0]
            elif geom.get("type") == "MultiPolygon":
                coords = geom["coordinates"][0][0]
    elif isinstance(polygon_coords, list):
        if len(polygon_coords) > 0 and isinstance(polygon_coords[0], list):
            coords = polygon_coords[0] if isinstance(polygon_coords[0][0], list) else polygon_coords

    if coords and len(coords) >= 3:
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        d_lng = max(xs) - min(xs)
        d_lat = max(ys) - min(ys)
    else:
        d_lng = 0.006
        d_lat = 0.006

    m_per_deg_lat = 111320
    m_per_deg_lng = 111320 * math.cos(math.radians(lat))
    w = max(min_dim, min(max_dim, int((d_lng * m_per_deg_lng) / target_resolution_m)))
    h = max(min_dim, min(max_dim, int((d_lat * m_per_deg_lat) / target_resolution_m)))
    return w, h


def fetch_rgb_tile(
    plot_id: str,
    lat: float,
    lng: float,
    polygon_coords: Any = None,
    force: bool = False,
) -> Optional[bytes]:
    """
    Fetch a Sentinel-2 True Color RGB tile for the plot polygon.

    Returns PNG image bytes, or None on failure.
    Uses a 7-day file cache to avoid redundant API calls.

    Args:
        plot_id: Unique plot identifier (used as cache key)
        lat: Plot center latitude
        lng: Plot center longitude
        polygon_coords: GeoJSON polygon or coordinate list
        force: If True, bypass cache and always fetch fresh

    Returns:
        PNG image bytes or None
    """
    # --- Cache check ---
    if not force and _is_cache_valid(plot_id):
        cache_path = _get_cache_path(plot_id)
        try:
            with open(cache_path, "rb") as f:
                image_bytes = f.read()
            logger.info(f"[TILE_RUNTIME] Cache hit for plot {plot_id}")
            return image_bytes
        except Exception:
            pass  # Fall through to fetch

    # --- Fetch from Sentinel Hub ---
    logger.info(f"[TILE_RUNTIME] Fetching fresh RGB tile for plot {plot_id}")
    try:
        token = _get_access_token()
    except Exception as e:
        logger.warning(f"[TILE_RUNTIME] Auth failed: {e}")
        return None

    bounds = _build_bounds(polygon_coords, lat, lng)
    w, h = _compute_dimensions(polygon_coords, lat, lng, target_resolution_m=10.0)

    # True Color RGB evalscript (B04=Red, B03=Green, B02=Blue)
    # Uses brightness-adjusted output for better visual analysis
    evalscript = """
    //VERSION=3
    function setup() {
        return {
            input: [{bands: ["B04","B03","B02","dataMask"], timeRange: "full"}],
            output: {bands: 3, sampleType: "AUTO"},
            mosaicking: "ORBIT"
        };
    }
    function evaluatePixel(samples) {
        // Use the most recent valid pixel (least cloud)
        for (var i = samples.length - 1; i >= 0; i--) {
            if (samples[i].dataMask == 1) {
                var gain = 3.5;
                return [samples[i].B04 * gain, samples[i].B03 * gain, samples[i].B02 * gain];
            }
        }
        return [0, 0, 0];
    }
    """

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)  # Last 30 days for best cloud-free mosaic

    payload = {
        "input": {
            "bounds": bounds,
            "data": [{
                "type": "sentinel-2-l2a",
                "dataFilter": {"mosaickingOrder": "leastCC", "maxCloudCoverage": 30},
                "timeRange": {
                    "from": start_date.strftime("%Y-%m-%dT00:00:00Z"),
                    "to": end_date.strftime("%Y-%m-%dT23:59:59Z"),
                },
            }],
        },
        "output": {
            "width": w,
            "height": h,
            "responses": [{"identifier": "default", "format": {"type": "image/png"}}],
        },
        "evalscript": evalscript,
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "image/png",
    }

    try:
        resp = requests.post(SENTINEL_PROCESS_URL, json=payload, headers=headers, timeout=30)
        if resp.status_code != 200:
            logger.warning(f"[TILE_RUNTIME] Sentinel Hub returned {resp.status_code}: {resp.text[:200]}")
            return None

        image_bytes = resp.content
        if len(image_bytes) < 100:
            logger.warning(f"[TILE_RUNTIME] Tile too small ({len(image_bytes)} bytes), likely empty")
            return None

        # --- Save to cache ---
        cache_path = _get_cache_path(plot_id)
        meta_path = _get_meta_path(plot_id)
        with open(cache_path, "wb") as f:
            f.write(image_bytes)
        with open(meta_path, "w") as f:
            json.dump({
                "plot_id": plot_id,
                "fetched_at": time.time(),
                "fetched_date": datetime.utcnow().isoformat(),
                "tile_size_bytes": len(image_bytes),
                "dimensions": [w, h],
                "source": "sentinel-2-l2a",
            }, f)

        logger.info(f"[TILE_RUNTIME] Cached {len(image_bytes)} bytes for plot {plot_id} ({w}x{h})")
        return image_bytes

    except requests.Timeout:
        logger.warning(f"[TILE_RUNTIME] Sentinel Hub request timed out for {plot_id}")
        return None
    except Exception as e:
        logger.warning(f"[TILE_RUNTIME] Fetch error for {plot_id}: {e}")
        return None


def get_cached_tile(plot_id: str) -> Optional[bytes]:
    """Get a cached tile if it exists (regardless of age). Used for LLM vision fallback."""
    cache_path = _get_cache_path(plot_id)
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            return f.read()
    return None


def get_tile_metadata(plot_id: str) -> Optional[Dict]:
    """Get metadata about a cached tile."""
    meta_path = _get_meta_path(plot_id)
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            return json.load(f)
    return None
