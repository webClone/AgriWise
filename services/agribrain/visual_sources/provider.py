import os
import json
import sys
from typing import Dict, Any, List, Optional
from visual_sources.cbers import VisualSourceConfig, find_latest_cbers_scene
from visual_sources.sentinel_visual import find_latest_sentinel_scene
from visual_sources.landsat_visual import find_latest_landsat_scene
from visual_sources.scene_store import save_scene

def get_visual_source_for_plot(
    plot_id: str,
    bbox: List[float],
    config: Optional[VisualSourceConfig] = None
) -> Dict[str, Any]:
    """
    Get the best available visual source metadata for a plot.
    
    Priority Flow (best free visual basemap strategy):
      1. CBERS-4A/WPM 2m — highest-res free satellite imagery
      2. Sentinel-2 L2A 10m RGB — reliable global fallback
      3. Landsat C2 L2 30m — third-tier free fallback
      4. Esri World Imagery ~1m — global mosaic safety net
      
    Real satellite imagery by default; falls back to synthetic preview under test or gap-fill scenarios.
    Visual imagery is map context only — never affects agronomic inference.
    """
    if config is None:
        config = VisualSourceConfig()

    visual_source: Dict[str, Any] = {}

    # Offline provider mode (V83.1)
    offline_mode = (
        os.getenv("AGRIWISE_OFFLINE_TEST_MODE", "").lower() in ("true", "1", "yes") or
        os.getenv("L10_DISABLE_LIVE_VISUAL_PROVIDERS", "").lower() in ("true", "1", "yes") or
        os.getenv("L10_DISABLE_LIVE_VISUAL_PROVIDERS_IN_SURFACE_RUN", "").lower() in ("true", "1", "yes")
    )
    if offline_mode:
        allow_synthetic = os.getenv("ALLOW_SYNTHETIC_VISUAL_PREVIEW", "false").lower() == "true"
        if allow_synthetic:
            visual_source = {
                "status": "synthetic_preview",
                "provider": "local_synthetic_visual",
                "collection": "LOCAL-SYNTHETIC-WPM-2M",
                "native_resolution_m": 2.0,
                "scene_date": "2026-06-01",
                "cog_asset": "local_synthetic",
                "tile_url": f"/api/agribrain/visual-tile/local_synthetic/{{z}}/{{x}}/{{y}}?scene_id=synthetic_{plot_id}",
                "is_mock": True,
                "role": "map_context_only",
                "state_update_allowed": False,
                "used_for_agronomic_inference": False,
                "fallback_used": True,
                "visual_source": "synthetic_preview",
                "fallback_reason": "Offline mode active: used deterministic local synthetic visual source."
            }
        else:
            visual_source = {
                "status": "unavailable",
                "provider": "none",
                "collection": "none",
                "native_resolution_m": 0.0,
                "scene_date": "2026-06-01",
                "cog_asset": "none",
                "tile_url": None,
                "is_mock": False,
                "role": "map_context_only",
                "state_update_allowed": False,
                "used_for_agronomic_inference": False,
                "fallback_used": True,
                "visual_source": "unavailable",
                "fallback_reason": "Visual imagery is not available for this plot."
            }
        if visual_source.get("role") != "map_context_only":
            raise RuntimeError("Visual basemap must only act as map context")
        if visual_source.get("state_update_allowed") is not False:
            raise RuntimeError("Visual basemap must never allow state updates")
        if visual_source.get("used_for_agronomic_inference") is not False:
            raise RuntimeError("Visual basemap must never affect agronomic inferences")
        return visual_source

    # Configurable TiTiler Base URL
    titiler_base_url = os.getenv("TITILER_BASE_URL", "https://titiler.xyz").rstrip("/")
    titiler_mode = "public_demo" if "titiler.xyz" in titiler_base_url else "self_hosted"
    if os.getenv("TITILER_DISABLED", "false").lower() == "true":
        titiler_mode = "disabled"

    # ── Tier 1: CBERS-4A/WPM 2m ─────────────────────────────────────────
    cbers = find_latest_cbers_scene(bbox, config)
    if cbers:
        save_scene(
            scene_id=cbers["scene_id"],
            provider="cbers",
            cog_asset=cbers["cog_asset"],
            datetime=cbers["datetime"],
            native_resolution_m=2.0
        )
        
        visual_source = {
            "status": "available",
            "provider": "CBERS-4A/WPM",
            "collection": cbers["collection"],
            "native_resolution_m": 2.0,
            "scene_date": cbers["datetime"],
            "cog_asset": cbers["cog_asset"],
            "asset_kind": "cog",
            "scene_id": cbers["scene_id"],
            "tile_url": f"/api/agribrain/visual-tile/cbers/{{z}}/{{x}}/{{y}}?scene_id={cbers['scene_id']}",
            "titiler_base_url": titiler_base_url,
            "titiler_mode": titiler_mode,
            "is_mock": False,
            "role": "map_context_only",
            "state_update_allowed": False,
            "used_for_agronomic_inference": False
        }
    else:
        # ── Tier 2: Sentinel-2 L2A 10m ──────────────────────────────────
        s2 = find_latest_sentinel_scene(bbox, config)
        if s2:
            save_scene(
                scene_id=s2["scene_id"],
                provider="sentinel",
                cog_asset=s2["cog_asset"],
                datetime=s2["datetime"],
                native_resolution_m=10.0
            )
            
            visual_source = {
                "status": "available",
                "provider": "Sentinel-2",
                "collection": s2["collection"],
                "native_resolution_m": 10.0,
                "scene_date": s2["datetime"],
                "cog_asset": s2["cog_asset"],
                "asset_kind": "cog",
                "scene_id": s2["scene_id"],
                "tile_url": f"/api/agribrain/visual-tile/sentinel/{{z}}/{{x}}/{{y}}?scene_id={s2['scene_id']}",
                "titiler_base_url": titiler_base_url,
                "titiler_mode": titiler_mode,
                "is_mock": False,
                "role": "map_context_only",
                "state_update_allowed": False,
                "used_for_agronomic_inference": False,
                "fallback_reason": "No CBERS scene found — using Sentinel-2 10m"
            }
        else:
            allow_synthetic = os.getenv("ALLOW_SYNTHETIC_VISUAL_PREVIEW", "false").lower() == "true"
            if allow_synthetic:
                visual_source = {
                    "status": "synthetic_preview",
                    "provider": "local_synthetic_visual",
                    "collection": "LOCAL-SYNTHETIC-WPM-2M",
                    "native_resolution_m": 2.0,
                    "scene_date": "2026-06-01",
                    "cog_asset": "local_synthetic",
                    "tile_url": f"/api/agribrain/visual-tile/local_synthetic/{{z}}/{{x}}/{{y}}?scene_id=synthetic_{plot_id}",
                    "is_mock": True,
                    "role": "map_context_only",
                    "state_update_allowed": False,
                    "used_for_agronomic_inference": False,
                    "fallback_reason": "All live providers unavailable; generated preview tile for no-blank-map safety."
                }
            else:
                # Normal mode fallback: return unavailable if synthetic is not allowed
                visual_source = {
                    "status": "unavailable",
                    "provider": "none",
                    "collection": "none",
                    "native_resolution_m": 0.0,
                    "scene_date": "2026-06-01",
                    "cog_asset": "none",
                    "tile_url": None,
                    "is_mock": False,
                    "role": "map_context_only",
                    "state_update_allowed": False,
                    "used_for_agronomic_inference": False,
                    "fallback_used": True,
                    "visual_source": "unavailable",
                    "fallback_reason": "Visual imagery is not available for this plot."
                }

    if visual_source.get("role") != "map_context_only":
        raise RuntimeError("Visual basemap must only act as map context")
    if visual_source.get("state_update_allowed") is not False:
        raise RuntimeError("Visual basemap must never allow state updates")
    if visual_source.get("used_for_agronomic_inference") is not False:
        raise RuntimeError("Visual basemap must never affect agronomic inferences")

    return visual_source
