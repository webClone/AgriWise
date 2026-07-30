"""
Sentinel-5P Scene Loader for ASMAE.

Converts Sentinel-5P atmospheric/SIF data into ASMAESceneRuntime objects.
S5P provides:
  - Solar Induced Fluorescence (SIF) — direct photosynthesis proxy
  - NO₂, SO₂, CH₄ — atmospheric context
  - Aerosol index — radiometric correction context

S5P data is coarse (~3.5km–7km) and used as atmospheric context only.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..schema import ASMAESceneRuntime
from .scene_quality import SceneQualityResult

logger = logging.getLogger(__name__)


def load_s5p_scenes(
    s5p_data: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Convert S5P atmospheric data into scene dicts.

    S5P data is typically provided as aggregated atmospheric context
    rather than per-scene packages. This loader wraps it as a single
    scene for the ASMAE pipeline.
    """
    if not s5p_data or not isinstance(s5p_data, dict):
        return []

    results = []
    try:
        scene_id = s5p_data.get("scene_id", "s5p_atmospheric")
        acq_str = s5p_data.get("acquisition_time", "")
        acq_dt = datetime.now(timezone.utc)
        if acq_str:
            try:
                acq_dt = datetime.fromisoformat(acq_str).replace(tzinfo=timezone.utc)
            except Exception:
                pass

        bands = {}
        for key in ("sif", "no2", "so2", "ch4", "aerosol_index"):
            val = s5p_data.get(key)
            if val is not None:
                bands[key] = val

        if not bands:
            return []

        runtime = ASMAESceneRuntime(
            scene_id=scene_id,
            sensor="S5P",
            acquisition_time=acq_dt,
            crs=s5p_data.get("crs", "EPSG:4326"),
            transform=s5p_data.get("transform", [3500.0, 0, 0, 0, -3500.0, 0]),
            width=0,
            height=0,
            bands=bands,
            masks={},
            qa_score=0.5,  # Coarse data gets moderate quality
            provenance_ref=f"s5p_loader_{scene_id}",
        )

        quality = SceneQualityResult(
            scene_id=scene_id,
            sensor="S5P",
            clear_pixel_fraction=0.8,
            valid_polygon_coverage=0.5,
            radiometric_quality=0.7,
            temporal_spacing_score=0.5,
            metadata_completeness=0.6,
            sensor_specific_quality=0.7,
        )
        quality.compute()
        runtime.qa_score = quality.overall

        results.append({
            "runtime": runtime,
            "quality": quality,
            "packets": [],
            "metadata": {"band_list": list(bands.keys())},
        })
    except Exception as e:
        logger.warning("Failed to load S5P data: %s", e)

    return results
