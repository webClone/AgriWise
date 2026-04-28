"""
IP Camera QA — Fixed-camera quality assessment with image-structural checks.

12 checks:
  1. Darkness / night                     (scalar)
  2. Blur / compression                   (scalar)
  3. Camera moved / framing drift         (scalar)
  4. Rain on lens — tile Laplacian CoV    (image-structural)
  5. Lens obstruction — connected comps   (image-structural)
  6. Sky/background dominance             (scalar)
  7. Stale frame — SSIM vs previous       (image-structural)
  8. Overexposure                         (scalar)
  9. Stale repeated frame                 (image-structural)
 10. Rain droplet pattern                 (image-structural)
 11. Obstruction blobs                    (image-structural)
 12. Spatial uniformity                   (image-structural)

Output: IPCameraQAResult -> determines reliability weight and sigma inflation.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from datetime import datetime

try:
    import numpy as np
    import cv2
    HAS_CV2 = True
except ImportError:
    np = None  # type: ignore
    cv2 = None  # type: ignore
    HAS_CV2 = False

from layer0.perception.ip_camera.schemas import IPCameraEngineInput, IPCameraQAResult
from layer0.perception.ip_camera.preprocess import PreprocessResult


class IPCameraQAFlag:
    CLEAN = "CLEAN"
    TOO_DARK = "too_dark"
    HIGH_BLUR = "high_blur"
    CAMERA_MOVED = "camera_moved"
    RAIN_ON_LENS = "rain_on_lens"
    LENS_OBSTRUCTION = "lens_obstruction"
    SKY_DOMINANCE = "sky_dominance"
    STALE_FRAME = "stale_frame"
    OVEREXPOSED = "overexposed"
    LOW_CONFIDENCE = "low_confidence"
    STALE_REPEATED = "stale_repeated"
    RAIN_DROPLETS = "rain_droplets"
    OBSTRUCTION_BLOB = "obstruction_blob"
    SPATIAL_NON_UNIFORM = "spatial_non_uniform"


class IPCameraQA:
    """
    QA gating specialized for fixed IP cameras.
    Each sub-assessment returns a 0-1 score. The overall qa_score is
    (min + average) / 2 — same strategy as farmer_photo/qa.py.
    """

    # Thresholds
    DARK_BRIGHTNESS = 40.0
    SHARP_LAP_VAR = 100.0
    MODERATE_LAP_VAR = 50.0
    BLURRY_LAP_VAR = 20.0
    SEVERE_BLUR_LAP_VAR = 10.0
    CAMERA_SHIFT_PX = 15.0

    def __init__(self):
        # Per-camera state for stale-frame detection
        self._previous_thumbnails: Dict[str, Any] = {}
        self._previous_timestamps: Dict[str, datetime] = {}

    def assess_quality(
        self,
        input_data: IPCameraEngineInput,
        preprocess: PreprocessResult,
    ) -> IPCameraQAResult:
        result = IPCameraQAResult(usable=True, qa_score=1.0)
        flags: List[str] = []
        scores: List[float] = []

        # --- 1. Darkness / night ---
        dark_score = self._assess_darkness(preprocess)
        scores.append(dark_score)
        if dark_score < 0.3:
            result.night_low_light = True
            flags.append(IPCameraQAFlag.TOO_DARK)

        # --- 2. Blur / compression ---
        blur_score = self._assess_blur(preprocess)
        scores.append(blur_score)
        result.blur_score = 1.0 - blur_score
        if blur_score < 0.3:
            flags.append(IPCameraQAFlag.HIGH_BLUR)

        # --- 3. Camera moved ---
        move_score = self._assess_camera_movement(preprocess)
        scores.append(move_score)
        if move_score < 0.3:
            result.camera_moved = True
            flags.append(IPCameraQAFlag.CAMERA_MOVED)

        # --- 4. Rain on lens (heuristic) ---
        rain_score = self._assess_rain_on_lens(preprocess)
        scores.append(rain_score)
        if rain_score < 0.5:
            result.rain_on_lens_detected = True
            flags.append(IPCameraQAFlag.RAIN_ON_LENS)

        # --- 5. Lens obstruction (heuristic) ---
        obstruction_score = self._assess_lens_obstruction(preprocess)
        scores.append(obstruction_score)
        result.lens_occlusion_score = 1.0 - obstruction_score
        if obstruction_score < 0.4:
            flags.append(IPCameraQAFlag.LENS_OBSTRUCTION)

        # --- 6. Sky/background dominance ---
        coverage_score = self._assess_coverage(preprocess)
        scores.append(coverage_score)
        if coverage_score < 0.3:
            flags.append(IPCameraQAFlag.SKY_DOMINANCE)

        # --- 7. Stale frame (timestamp) ---
        stale_score = self._assess_staleness(input_data)
        scores.append(stale_score)
        if stale_score < 0.5:
            flags.append(IPCameraQAFlag.STALE_FRAME)

        # --- 8. Overexposure ---
        exposure_score = self._assess_overexposure(preprocess)
        scores.append(exposure_score)
        if exposure_score < 0.4:
            flags.append(IPCameraQAFlag.OVEREXPOSED)

        # --- 9. Stale repeated frame (SSIM) ---
        ssim_score = self._assess_stale_frame_similarity(input_data, preprocess)
        scores.append(ssim_score)
        if ssim_score < 0.3:
            flags.append(IPCameraQAFlag.STALE_REPEATED)

        # --- 10. Rain droplet pattern (tile Laplacian CoV) ---
        droplet_score = self._assess_rain_droplet_pattern(preprocess)
        scores.append(droplet_score)
        if droplet_score < 0.4:
            flags.append(IPCameraQAFlag.RAIN_DROPLETS)

        # --- 11. Obstruction blobs (connected components) ---
        blob_score = self._assess_obstruction_blobs(preprocess)
        scores.append(blob_score)
        if blob_score < 0.4:
            flags.append(IPCameraQAFlag.OBSTRUCTION_BLOB)

        # --- 12. Spatial uniformity (quadrant brightness) ---
        uniformity_score = self._assess_spatial_uniformity(preprocess)
        scores.append(uniformity_score)
        if uniformity_score < 0.3:
            flags.append(IPCameraQAFlag.SPATIAL_NON_UNIFORM)

        # --- Overall score: (min + mean) / 2 ---
        if scores:
            result.qa_score = (min(scores) + sum(scores) / len(scores)) / 2
        result.qa_score = max(0.0, min(1.0, result.qa_score))

        result.exposure_score = exposure_score

        # --- Usability hard gates ---
        if dark_score < 0.3 or blur_score < 0.15 or move_score < 0.3:
            result.usable = False
        elif result.qa_score < 0.15:
            result.usable = False

        # --- Reliability / sigma ---
        result.reliability_weight = self._score_to_reliability(result.qa_score)
        result.sigma_inflation = self._score_to_sigma_inflation(result.qa_score)

        if result.qa_score < 0.3 and result.usable:
            flags.append(IPCameraQAFlag.LOW_CONFIDENCE)

        if not flags:
            flags.append(IPCameraQAFlag.CLEAN)

        result.flags = flags
        result.details = {
            "dark_score": round(dark_score, 3),
            "blur_score": round(blur_score, 3),
            "move_score": round(move_score, 3),
            "rain_score": round(rain_score, 3),
            "obstruction_score": round(obstruction_score, 3),
            "coverage_score": round(coverage_score, 3),
            "stale_score": round(stale_score, 3),
            "exposure_score": round(exposure_score, 3),
            "ssim_score": round(ssim_score, 3),
            "droplet_score": round(droplet_score, 3),
            "blob_score": round(blob_score, 3),
            "uniformity_score": round(uniformity_score, 3),
        }

        return result

    # ================================================================
    # Original scalar sub-assessments
    # ================================================================

    def _assess_darkness(self, p: PreprocessResult) -> float:
        b = p.brightness_mean
        if b < 20:
            return 0.0
        if b < self.DARK_BRIGHTNESS:
            return 0.2
        if b < 60:
            return 0.6
        return 1.0

    def _assess_blur(self, p: PreprocessResult) -> float:
        lap = p.laplacian_var
        if lap is None:
            return 0.5
        if lap > self.SHARP_LAP_VAR:
            return 1.0
        if lap > self.MODERATE_LAP_VAR:
            return 0.8
        if lap > self.BLURRY_LAP_VAR:
            return 0.5
        if lap > self.SEVERE_BLUR_LAP_VAR:
            return 0.2
        return 0.1

    def _assess_camera_movement(self, p: PreprocessResult) -> float:
        max_shift = max(abs(p.shift_x), abs(p.shift_y))
        if max_shift > 30:
            return 0.0
        if max_shift > self.CAMERA_SHIFT_PX:
            return 0.2
        if max_shift > 8:
            return 0.6
        return 1.0

    def _assess_rain_on_lens(self, p: PreprocessResult) -> float:
        if p.saturation_mean < 20 and p.brightness_std > 80:
            return 0.2
        if p.saturation_mean < 30 and p.brightness_std > 60:
            return 0.5
        return 1.0

    def _assess_lens_obstruction(self, p: PreprocessResult) -> float:
        if p.underexposed_pct > 60 or p.overexposed_pct > 60:
            return 0.2
        if p.underexposed_pct > 40 or p.overexposed_pct > 40:
            return 0.5
        return 1.0

    def _assess_coverage(self, p: PreprocessResult) -> float:
        gcf = p.green_coverage_fraction
        if gcf < 0.05:
            return 0.1
        if gcf < 0.15:
            return 0.4
        if gcf < 0.25:
            return 0.7
        return 1.0

    def _assess_staleness(self, input_data: IPCameraEngineInput) -> float:
        ts = input_data.timestamp
        if ts is None:
            return 0.7
        age_hours = (datetime.now() - ts).total_seconds() / 3600
        if age_hours < 2:
            return 1.0
        if age_hours < 6:
            return 0.8
        if age_hours < 24:
            return 0.5
        return 0.3

    def _assess_overexposure(self, p: PreprocessResult) -> float:
        if p.overexposed_pct > 30:
            return 0.2
        if p.overexposed_pct > 15:
            return 0.5
        if p.brightness_mean > 230:
            return 0.3
        return 1.0

    # ================================================================
    # New image-structural sub-assessments
    # ================================================================

    def _assess_stale_frame_similarity(
        self, input_data: IPCameraEngineInput, p: PreprocessResult
    ) -> float:
        """
        Compare current frame thumbnail to previous frame via SSIM.
        If nearly identical (>0.98) and time gap > 30min -> stale/frozen feed.
        """
        camera_id = input_data.camera_id
        current_thumb = p.gray_thumbnail_64

        if current_thumb is None or not HAS_CV2:
            # No thumbnail available (mock path) -> pass
            return 1.0

        prev_thumb = self._previous_thumbnails.get(camera_id)
        prev_ts = self._previous_timestamps.get(camera_id)

        # Update state
        self._previous_thumbnails[camera_id] = current_thumb.copy()
        self._previous_timestamps[camera_id] = input_data.timestamp or datetime.now()

        if prev_thumb is None:
            return 1.0  # First frame, nothing to compare

        # Compute SSIM manually (simple implementation for 64x64)
        ssim = self._compute_ssim(current_thumb, prev_thumb)

        # Check time gap
        current_ts = input_data.timestamp or datetime.now()
        if prev_ts:
            gap_minutes = (current_ts - prev_ts).total_seconds() / 60
        else:
            gap_minutes = 0

        # Nearly identical frame after long gap -> frozen feed
        if ssim > 0.98 and gap_minutes > 30:
            return 0.1  # Very likely frozen
        if ssim > 0.95 and gap_minutes > 60:
            return 0.2
        if ssim > 0.99 and gap_minutes > 5:
            return 0.3  # Suspiciously similar even after short gap

        return 1.0

    def _compute_ssim(self, img1: Any, img2: Any) -> float:
        """
        Simplified SSIM computation between two grayscale images.
        Uses the standard SSIM formula with default constants.
        """
        if not HAS_CV2:
            return 0.5

        img1 = img1.astype(np.float64)
        img2 = img2.astype(np.float64)

        c1 = (0.01 * 255) ** 2
        c2 = (0.03 * 255) ** 2

        mu1 = cv2.GaussianBlur(img1, (7, 7), 1.5)
        mu2 = cv2.GaussianBlur(img2, (7, 7), 1.5)

        mu1_sq = mu1 ** 2
        mu2_sq = mu2 ** 2
        mu1_mu2 = mu1 * mu2

        sigma1_sq = cv2.GaussianBlur(img1 ** 2, (7, 7), 1.5) - mu1_sq
        sigma2_sq = cv2.GaussianBlur(img2 ** 2, (7, 7), 1.5) - mu2_sq
        sigma12 = cv2.GaussianBlur(img1 * img2, (7, 7), 1.5) - mu1_mu2

        ssim_map = ((2 * mu1_mu2 + c1) * (2 * sigma12 + c2)) / \
                   ((mu1_sq + mu2_sq + c1) * (sigma1_sq + sigma2_sq + c2))

        return float(np.mean(ssim_map))

    def _assess_rain_droplet_pattern(self, p: PreprocessResult) -> float:
        """
        Rain droplets create localized high-frequency bokeh patterns.
        Measured via coefficient of variation of per-tile Laplacian variance.
        High CoV = some tiles sharp, others blurred by droplets.
        """
        tiles = p.tile_laplacian_values
        if tiles is None or len(tiles) < 4:
            return 1.0  # No tile data (mock path)

        mean_lap = sum(tiles) / len(tiles)
        if mean_lap < 1e-6:
            return 0.5  # Very uniform (could be very dark)

        variance = sum((t - mean_lap) ** 2 for t in tiles) / len(tiles)
        std_lap = variance ** 0.5
        cov = std_lap / mean_lap  # Coefficient of variation

        # High CoV = very uneven sharpness across tiles = likely rain/condensation
        if cov > 2.0:
            return 0.2
        if cov > 1.5:
            return 0.4
        if cov > 1.0:
            return 0.7
        return 1.0

    def _assess_obstruction_blobs(self, p: PreprocessResult) -> float:
        """
        Detect large dark or bright blobs that indicate obstruction.
        Uses connected component analysis on the gray thumbnail.
        """
        thumb = p.gray_thumbnail_64
        if thumb is None or not HAS_CV2:
            return 1.0

        h, w = thumb.shape
        total_px = h * w

        # Check dark blobs (< 30 intensity)
        dark_mask = (thumb < 30).astype(np.uint8)
        n_labels_dark, labels_dark, stats_dark, _ = cv2.connectedComponentsWithStats(
            dark_mask, connectivity=8
        )
        for i in range(1, n_labels_dark):  # skip background
            area = stats_dark[i, cv2.CC_STAT_AREA]
            if area > total_px * 0.20:
                return 0.2  # Large dark blob = obstruction

        # Check bright blobs (> 240 intensity)
        bright_mask = (thumb > 240).astype(np.uint8)
        n_labels_bright, labels_bright, stats_bright, _ = cv2.connectedComponentsWithStats(
            bright_mask, connectivity=8
        )
        for i in range(1, n_labels_bright):
            area = stats_bright[i, cv2.CC_STAT_AREA]
            if area > total_px * 0.20:
                return 0.3  # Large bright blob = lens flare

        return 1.0

    def _assess_spatial_uniformity(self, p: PreprocessResult) -> float:
        """
        Check brightness uniformity across 4 quadrants.
        Large disparity indicates partial obstruction or lens dirt.
        """
        quads = p.quadrant_brightness
        if quads is None or len(quads) < 4:
            return 1.0  # No data (mock path)

        max_b = max(quads)
        min_b = min(quads)

        if min_b < 1:
            min_b = 1  # avoid division by zero

        ratio = max_b / min_b

        if ratio > 4.0:
            return 0.1  # Extreme non-uniformity
        if ratio > 3.0:
            return 0.3
        if ratio > 2.0:
            return 0.6
        return 1.0

    # ================================================================
    # Score -> reliability/sigma
    # ================================================================

    @staticmethod
    def _score_to_reliability(score: float) -> float:
        if score > 0.8:
            return 0.85
        if score > 0.6:
            return 0.65
        if score > 0.4:
            return 0.40
        if score > 0.2:
            return 0.15
        return 0.05

    @staticmethod
    def _score_to_sigma_inflation(score: float) -> float:
        if score > 0.8:
            return 1.0
        if score > 0.6:
            return 1.5
        if score > 0.4:
            return 2.5
        if score > 0.2:
            return 4.0
        return 8.0
