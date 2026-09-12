"""
V79A Phase 1: Scene stack reality classifier.

Classifies the scene stack into one of three modes:
  - real_raster: at least 1 scene with real pixel dimensions and band arrays
  - degraded_mean_only: all scenes have width==0 or height==0 or no pixel arrays
  - no_scenes: len(scenes) == 0

This classification gates the entire downstream pipeline:
  - no_scenes → partial, no rasters, no weak labels
  - degraded_mean_only → no adaptive resolution, no L1/L10 export, no weak labels
  - real_raster → full pipeline allowed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List


@dataclass
class SceneStackClassification:
    """Result of classifying the scene stack reality level."""
    mode: str  # "real_raster" | "degraded_mean_only" | "no_scenes"
    n_total: int = 0
    n_real_raster: int = 0
    n_mean_only: int = 0
    n_excluded: int = 0
    n_provider_real: int = 0
    n_proxy: int = 0
    n_diagnostic: int = 0
    reasons: List[str] = field(default_factory=list)
    current_1m_approval_allowed: bool = False

    # Derived gates
    @property
    def production_allowed(self) -> bool:
        return (
            self.mode == "real_raster"
            and self.n_provider_real > 0
            and self.n_proxy == 0
            and self.n_diagnostic == 0
        )

    @property
    def _strict_provider_real(self) -> bool:
        return (
            self.mode == "real_raster"
            and self.n_provider_real > 0
            and self.n_proxy == 0
            and self.n_diagnostic == 0
        )

    @property
    def adaptive_resolution_allowed(self) -> bool:
        return self._strict_provider_real

    @property
    def weak_label_export_allowed(self) -> bool:
        return self._strict_provider_real

    @property
    def state_update_allowed(self) -> bool:
        return self._strict_provider_real

    @property
    def layer1_export_allowed(self) -> bool:
        return self._strict_provider_real

    @property
    def layer10_scientific_surface_allowed(self) -> bool:
        return self._strict_provider_real


def classify_scene_stack(scenes: list) -> SceneStackClassification:
    """Classify scene stack into reality level.

    A scene is 'real_raster' if it has:
      - width > 0 AND height > 0
      - at least one band with array data (not scalar-only)

    A scene is 'mean_only' if:
      - width == 0 or height == 0
      - OR all bands are scalars / empty

    Returns SceneStackClassification with mode and counts.
    """
    if not scenes:
        return SceneStackClassification(
            mode="no_scenes",
            n_total=0,
            reasons=["scene list is empty"],
        )

    from layer05_asmae.truth_contract import classify_asmae_scene_reality

    n_real = 0
    n_mean = 0
    n_excluded = 0
    n_provider_real = 0
    n_proxy = 0
    n_diagnostic = 0
    reasons: List[str] = []

    for scene in scenes:
        w = getattr(scene, "width", 0) or 0
        h = getattr(scene, "height", 0) or 0
        bands = getattr(scene, "bands", {}) or {}

        if w == 0 or h == 0:
            n_mean += 1
            reasons.append(
                f"{getattr(scene, 'scene_id', '?')}: width={w}, height={h} → mean_only"
            )
            continue

        # Check if bands contain real arrays (not just scalars)
        has_array_band = False
        for band_name, band_data in bands.items():
            if _is_real_array(band_data):
                has_array_band = True
                break

        if has_array_band:
            n_real += 1
            truth = classify_asmae_scene_reality(scene)
            if truth.truth_class == "provider_real_raster":
                n_provider_real += 1
            elif truth.truth_class == "raster_composite_proxy":
                n_proxy += 1
            else:
                n_diagnostic += 1
        else:
            n_mean += 1
            reasons.append(
                f"{getattr(scene, 'scene_id', '?')}: no array bands → mean_only"
            )

    n_total = n_real + n_mean

    if n_real > 0:
        mode = "real_raster"
    elif n_mean > 0:
        mode = "degraded_mean_only"
    else:
        mode = "no_scenes"

    from ..evidence_classifier import _is_valid_proof
    current_1m_approval_allowed = any(_is_valid_proof(s) for s in scenes)

    return SceneStackClassification(
        mode=mode,
        n_total=n_total,
        n_real_raster=n_real,
        n_mean_only=n_mean,
        n_excluded=n_excluded,
        n_provider_real=n_provider_real,
        n_proxy=n_proxy,
        n_diagnostic=n_diagnostic,
        reasons=reasons,
        current_1m_approval_allowed=current_1m_approval_allowed,
    )


def _is_real_array(band_data: Any) -> bool:
    """Check if band data is a real 2D array (not a scalar or empty)."""
    try:
        import numpy as np
        if isinstance(band_data, np.ndarray):
            return band_data.ndim >= 2 and band_data.size > 1
    except ImportError:
        pass

    if isinstance(band_data, (list, tuple)):
        if len(band_data) > 1:
            # Check if it's a 2D list
            if isinstance(band_data[0], (list, tuple)):
                return True
        return False

    # Scalar
    return False
