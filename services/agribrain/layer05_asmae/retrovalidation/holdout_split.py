"""Causal leave-one-date-out splits for scientific retrovalidation."""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional, Tuple


def _scene_time(scene: Any) -> Optional[datetime]:
    value = getattr(scene, "acquisition_time", None)
    return value if isinstance(value, datetime) else None


def _is_production_raster(scene: Any) -> bool:
    reality = str(getattr(scene, "source_reality", "unknown") or "unknown")
    return bool(
        (getattr(scene, "width", 0) or 0) > 0
        and (getattr(scene, "height", 0) or 0) > 0
        and getattr(scene, "real_provider_product", False) is True
        and getattr(scene, "production_usable", False) is True
        and getattr(scene, "diagnostic_only", True) is False
        and reality in {
            "real_raster",
            "real_provider_raster",
            "provider_observation",
        }
    )


def leave_one_out_holdout(scenes: list) -> List[Tuple[list, Any]]:
    """Build rolling-origin, leave-one-date-out folds.

    A holdout is predicted only from strictly earlier acquisition dates.
    Every scene on the holdout date is therefore absent from training. Scenes
    with missing timestamps or diagnostic-only authority cannot certify a
    holdout score.
    """
    ordered = sorted(
        (scene for scene in (scenes or []) if _scene_time(scene) is not None),
        key=lambda scene: _scene_time(scene),
    )
    folds: List[Tuple[list, Any]] = []
    for holdout in ordered:
        if not _is_production_raster(holdout):
            continue
        holdout_day = _scene_time(holdout).date()
        training = [
            scene for scene in ordered
            if _scene_time(scene).date() < holdout_day
        ]
        if training:
            folds.append((training, holdout))
    return folds


def has_real_holdout_scenes(scenes: list) -> bool:
    """Return true only when at least one causal production fold exists."""
    return bool(leave_one_out_holdout(scenes))
