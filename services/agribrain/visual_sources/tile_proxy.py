import io
import math
import os
from typing import Union, Optional
from PIL import Image
from visual_sources.scene_store import get_scene

def tile_to_bbox(z: int, x: int, y: int):
    """Convert slippy map tile coordinates to lat/lng bounding box."""
    n = 2.0 ** z
    lon_deg_min = x / n * 360.0 - 180.0
    lat_rad_min = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat_deg_min = math.degrees(lat_rad_min)
    
    lon_deg_max = (x + 1) / n * 360.0 - 180.0
    lat_rad_max = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n)))
    lat_deg_max = math.degrees(lat_rad_max)
    
    return {
        "min_lng": lon_deg_min,
        "max_lng": lon_deg_max,
        "min_lat": lat_deg_max,
        "max_lat": lat_deg_min
    }

def render_tile(
    provider: str,
    z: int,
    x: int,
    y: int,
    scene_id: str
) -> Union[bytes, str]:
    """
    Renders/resolves visual satellite tiles for the frontend map background.
    
    Only serves real satellite imagery:
      - CBERS/Sentinel: Resolves COG from scene store → redirect to TiTiler
      - All other cases: transparent tile so the live Esri basemap shows through
    
    Returns:
      - bytes: Raw image PNG bytes (transparent tile).
      - str: A TiTiler redirect URL to respond with an HTTP 302.
    """

    if provider in ("cbers", "sentinel", "landsat"):
        # Real Visual Imagery Path: Resolve COG from scene store and redirect to TiTiler
        scene = get_scene(scene_id)
        if scene and scene.get("cog_asset"):
            cog_url = scene["cog_asset"]
            # Check if this is a mock scene to avoid redirecting to a non-existent asset
            if scene_id == "CB4A_WPM_20260109" or cog_url == "https://aws.amazon.com/cbers/cog.tif":
                return _render_transparent_tile()
                
            from urllib.parse import quote
            titiler_base_url = os.getenv("TITILER_BASE_URL", "https://titiler.xyz").rstrip("/")
            
            # Construct standard WebMercatorQuad TiTiler tile request
            redirect_url = f"{titiler_base_url}/cog/tiles/WebMercatorQuad/{z}/{x}/{y}.png?url={quote(cog_url)}"
            return redirect_url

    # Fallback: Return a transparent PNG tile so the live Esri basemap shows through
    return _render_transparent_tile()


# In-memory plot bounding box cache
_plot_bbox_cache = {}

def register_plot_bbox(plot_id: str, bbox: list) -> None:
    """Register/cache the plot bounding box in memory."""
    if plot_id and bbox and len(bbox) == 4:
        _plot_bbox_cache[plot_id] = bbox

def extract_plot_id(scene_id: str) -> str:
    """Strips all visual prefixes to recover the clean 24-character hexadecimal MongoDB Plot ID."""
    cleaned = scene_id
    for prefix in ["S2A_MSIL2A_", "CB4A_WPM_"]:
        cleaned = cleaned.replace(prefix, "")
    return cleaned.split("T")[0]


def _render_transparent_tile() -> bytes:
    """Renders a fully transparent 256x256 PNG tile."""
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    out_buf = io.BytesIO()
    img.save(out_buf, format="PNG")
    return out_buf.getvalue()

