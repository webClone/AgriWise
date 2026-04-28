"""
Scene Stability Analyzer — multi-signal baseline comparison.

Compares current frame against hour-matched baseline using:
  1. Histogram correlation (structural similarity)
  2. Edge density delta (structural change detection)
  3. Scalar stat deltas (secondary signal)

Weighted fusion: 0.5 × histogram_corr + 0.3 × edge_stability + 0.2 × scalar_stability

Change classification:
  CAMERA_SHIFT:   shift_px > threshold OR histogram_corr < 0.5 with stable lighting
  LIGHTING_SHIFT: brightness delta > threshold BUT histogram_corr > 0.7
  CROP_CHANGE:    histogram_corr < 0.7 AND edge_density changed AND lighting stable
  OBSTRUCTION:    histogram_corr < 0.3 AND edge_density dropped sharply
"""

from __future__ import annotations
from typing import Any, Optional
from datetime import datetime

from layer0.perception.ip_camera.schemas import IPCameraSceneContext, SceneChangeType
from layer0.perception.ip_camera.baseline_model import BaselineModel, BaselineEntry
from layer0.perception.ip_camera.preprocess import PreprocessResult


class SceneStabilityAnalyzer:
    """
    Evaluates temporal stability of the scene by comparing
    current frame features against the hour-matched baseline.
    """

    # Thresholds
    GREEN_DELTA_THRESHOLD = 0.15
    BRIGHTNESS_DELTA_THRESHOLD = 40
    SHIFT_THRESHOLD = 10.0
    EDGE_DELTA_THRESHOLD = 0.03
    HIST_CORR_STRONG = 0.7
    HIST_CORR_WEAK = 0.5
    HIST_CORR_OBSTRUCTION = 0.3

    def __init__(self, baseline_model: BaselineModel):
        self.baseline_model = baseline_model

    def analyze(
        self,
        camera_id: str,
        preprocess: PreprocessResult,
        current_time: Optional[datetime] = None,
    ) -> IPCameraSceneContext:
        ctx = IPCameraSceneContext()

        # Populate scene fractions from segmentation
        ctx.visible_crop_fraction = preprocess.green_coverage_fraction
        ctx.visible_soil_fraction = preprocess.soil_fraction

        # Fetch baseline for same hour
        baseline = self.baseline_model.get_time_of_day_baseline(camera_id, current_time)

        if baseline is None:
            ctx.camera_pose_drift_score = 0.0
            ctx.scene_change_type = SceneChangeType.UNKNOWN
            ctx.lighting_match_confidence = 0.5
            return ctx

        # --- Signal 1: Histogram correlation ---
        hist_corr = self.baseline_model.compare_histogram(
            preprocess.hsv_histogram, baseline.hsv_histogram
        )

        # --- Signal 2: Edge density delta ---
        edge_delta = abs(preprocess.edge_density - baseline.edge_density)
        edge_stability = max(0.0, 1.0 - edge_delta / 0.1)

        # --- Signal 3: Scalar stat deltas ---
        green_delta = abs(preprocess.green_ratio - baseline.green_ratio)
        brightness_delta = abs(preprocess.brightness_mean - baseline.brightness_mean)
        max_shift = max(abs(preprocess.shift_x), abs(preprocess.shift_y))

        scalar_green_stability = max(0.0, 1.0 - green_delta / 0.3)
        scalar_brightness_stability = max(0.0, 1.0 - brightness_delta / 80.0)
        scalar_stability = (scalar_green_stability + scalar_brightness_stability) / 2

        # --- Weighted fusion ---
        stability_score = (
            0.5 * hist_corr +
            0.3 * edge_stability +
            0.2 * scalar_stability
        )

        # Camera pose drift
        shift_drift = min(1.0, max_shift / 30.0)
        structural_drift = 1.0 - stability_score
        ctx.camera_pose_drift_score = max(structural_drift, shift_drift)

        # --- Change type classification ---
        has_shift = max_shift > self.SHIFT_THRESHOLD
        has_lighting_change = brightness_delta > self.BRIGHTNESS_DELTA_THRESHOLD
        has_structural_change = green_delta > self.GREEN_DELTA_THRESHOLD
        has_edge_change = edge_delta > self.EDGE_DELTA_THRESHOLD

        if has_shift or (hist_corr < self.HIST_CORR_WEAK and not has_lighting_change):
            ctx.scene_change_type = SceneChangeType.CAMERA_SHIFT
        elif hist_corr < self.HIST_CORR_OBSTRUCTION and edge_delta > 0.05:
            # Drastic structural change + edge density drop = obstruction
            ctx.scene_change_type = SceneChangeType.CAMERA_SHIFT  # closest type
        elif has_lighting_change and hist_corr > self.HIST_CORR_STRONG:
            # Structure unchanged but brightness shifted
            ctx.scene_change_type = SceneChangeType.LIGHTING_SHIFT
        elif hist_corr < self.HIST_CORR_STRONG and has_edge_change:
            ctx.scene_change_type = SceneChangeType.CROP_CHANGE
        else:
            ctx.scene_change_type = SceneChangeType.CROP_CHANGE  # stable = normal

        # Lighting match confidence
        if has_lighting_change:
            ctx.lighting_match_confidence = max(0.1, scalar_brightness_stability)
        else:
            ctx.lighting_match_confidence = 1.0

        return ctx
