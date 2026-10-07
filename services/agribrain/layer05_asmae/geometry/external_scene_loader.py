"""
External Scene Loader for ASMAE.

Handles non-Sentinel external imagery:
  - Ground-truth/farmer photos (via Layer 0 perception)
  - Drone imagery
  - Aerial survey data
  - Third-party satellite (Planet, Maxar, etc.)

External scenes are tagged as "EXTERNAL" sensor and receive moderate
quality scores since they lack standardized QA metadata.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..schema import ASMAESceneRuntime
from .scene_quality import SceneQualityResult

logger = logging.getLogger(__name__)


def load_external_scenes(
    external_data: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Convert external imagery records into scene dicts.

    Args:
        external_data: List of external image metadata dicts, each with:
            - scene_id: str
            - acquisition_time: str (ISO 8601)
            - source: str (e.g., "drone", "planet", "farmer_photo")
            - resolution_m: float
            - crs: str
            - bands: dict
    """
    if not external_data:
        return []

    results = []
    for record in external_data:
        if not isinstance(record, dict):
            continue
        try:
            scene_id = record.get("scene_id", f"ext_{len(results)}")
            acq_str = record.get("acquisition_time", "")
            try:
                acq_dt = datetime.fromisoformat(acq_str)
                if acq_dt.tzinfo is None:
                    acq_dt = acq_dt.replace(tzinfo=timezone.utc)
                else:
                    acq_dt = acq_dt.astimezone(timezone.utc)
            except Exception as e:
                logger.warning("External scene %s has invalid/unparseable acquisition_time '%s' — rejecting: %s", scene_id, acq_str, e)
                continue

            bands = record.get("bands", {})
            if not isinstance(bands, dict):
                bands = {}

            crs = str(record.get("crs") or "").strip()
            transform = record.get("transform")
            width = record.get("width")
            height = record.get("height")
            if not (
                crs
                and isinstance(transform, (list, tuple))
                and len(transform) == 6
                and all(isinstance(value, (int, float)) for value in transform)
                and isinstance(width, int) and width > 0
                and isinstance(height, int) and height > 0
            ):
                logger.warning(
                    "External scene %s has no explicit spatial grid contract; rejecting",
                    scene_id,
                )
                continue

            runtime = ASMAESceneRuntime(
                scene_id=scene_id,
                sensor="EXTERNAL",
                acquisition_time=acq_dt,
                crs=crs,
                transform=list(transform),
                width=width,
                height=height,
                bands=bands,
                masks={},
                qa_score=0.5,
                provenance_ref=f"ext_loader_{scene_id}",
            )

            quality = SceneQualityResult(
                scene_id=scene_id,
                sensor="EXTERNAL",
                clear_pixel_fraction=0.9,
                valid_polygon_coverage=record.get("coverage", 0.5),
                radiometric_quality=0.5,
                temporal_spacing_score=0.5,
                metadata_completeness=0.5,
                sensor_specific_quality=0.7,
            )
            quality.compute()
            runtime.qa_score = quality.overall

            # Resolve spatial resolution from metadata or transform
            raw_res = record.get("resolution_m")
            if raw_res is not None:
                try:
                    resolution_m = float(raw_res)
                except (ValueError, TypeError):
                    resolution_m = float(abs(transform[0])) if transform[0] else 10.0
            elif isinstance(transform, (list, tuple)) and len(transform) >= 2 and transform[0]:
                resolution_m = float(abs(transform[0]))
            else:
                resolution_m = 10.0

            results.append({
                "runtime": runtime,
                "quality": quality,
                "packets": [],
                "metadata": {
                    "source": record.get("source", "unknown"),
                    "resolution_m": resolution_m,
                },
            })
        except Exception as e:
            logger.warning("Failed to load external scene: %s", e)

    return results
