"""
Stage B — Per-Frame QA.

Evaluates each frame independently for quality before it enters the
reconstruction pipeline. Produces a FrameQAResult per frame.

Policy (matches Layer 0 QA philosophy):
  - Reject unusable frames early (binary gate).
  - Downweight weak frames via quality_weight (sigma-like control).
  - QA drives reliability, not just acceptance.

V1: Heuristic blur/exposure/shadow estimation from pixel statistics.
V2: CNN-based blur detection, learned exposure model.
"""

from __future__ import annotations
from typing import List
import logging
import math

from .schemas import FrameMetadata, FrameQAResult

logger = logging.getLogger(__name__)


class FrameQA:
    """Per-frame quality assessor for photogrammetry input frames."""
    
    # Hard rejection thresholds
    BLUR_REJECT = 0.70          # Reject if blur > 70%
    EXPOSURE_REJECT = 0.20      # Reject if exposure < 20%
    HORIZON_REJECT = 0.60       # Reject if > 60% sky
    
    # Soft penalty thresholds
    BLUR_PENALTY_START = 0.30   # Start penalizing blur above 30%
    SHADOW_PENALTY_START = 0.40 # Start penalizing shadow above 40%
    
    def assess_batch(self, frames: List[FrameMetadata]) -> List[FrameQAResult]:
        """Assess quality of all frames in a manifest.
        
        Args:
            frames: List of ingested frame metadata.
            
        Returns:
            Parallel list of FrameQAResult (one per frame).
        """
        results = []
        for frame in frames:
            qa = self.assess_single(frame)
            results.append(qa)
        
        # Summary logging
        usable = sum(1 for r in results if r.usable)
        logger.info(
            f"[FrameQA] Assessed {len(results)} frames: "
            f"{usable} usable, {len(results) - usable} rejected"
        )
        
        return results
    
    def assess_single(self, frame: FrameMetadata) -> FrameQAResult:
        """Assess quality of a single frame.
        
        V1 heuristic: uses pixel statistics to estimate blur, exposure,
        shadow, and horizon contamination. Skipped frames get default
        mid-quality scores to avoid false rejection.
        """
        qa = FrameQAResult(frame_id=frame.frame_id)
        
        # If we have synthetic pixels, compute from them
        if frame.synthetic_pixels and "green" in frame.synthetic_pixels:
            self._assess_from_pixels(frame.synthetic_pixels, qa)
        else:
            # No pixel data — assign moderate defaults
            qa.blur_score = 0.10
            qa.exposure_score = 0.85
            qa.shadow_severity = 0.10
            qa.vegetation_content = 0.50
        
        # Horizon contamination from pitch angle
        if abs(frame.gps.pitch_deg) > 15:
            qa.horizon_contamination = min(1.0, abs(frame.gps.pitch_deg) / 45.0)
        
        # Rolling shutter risk from camera metadata
        if frame.camera.rolling_shutter and frame.camera.rolling_shutter_readout_ms > 10:
            qa.rolling_shutter_risk = min(
                1.0, frame.camera.rolling_shutter_readout_ms / 30.0
            )
        
        # Motion smear from shutter speed and altitude
        if frame.shutter_speed_s > 0:
            # At 5 m/s drone speed, 1/200s shutter → 2.5cm blur
            # At GSD 2cm, that's ~1.25 pixel blur → acceptable
            smear_cm = 5.0 * frame.shutter_speed_s * 100  # cm blur
            gsd_cm = frame.camera.calculate_gsd_cm(frame.gps.altitude_m or 50.0)
            pixel_blur = smear_cm / max(gsd_cm, 0.1)
            qa.motion_smear = min(1.0, pixel_blur / 5.0)
        
        # --- Hard rejection gates ---
        if qa.blur_score > self.BLUR_REJECT:
            qa.usable = False
            qa.rejection_reason = f"Severe blur ({qa.blur_score:.2f})"
        elif qa.exposure_score < self.EXPOSURE_REJECT:
            qa.usable = False
            qa.rejection_reason = f"Unusable exposure ({qa.exposure_score:.2f})"
        elif qa.horizon_contamination > self.HORIZON_REJECT:
            qa.usable = False
            qa.rejection_reason = f"Too much sky ({qa.horizon_contamination:.2f})"
        
        # --- Compute quality weight ---
        if qa.usable:
            weight = 1.0
            
            # Blur penalty
            if qa.blur_score > self.BLUR_PENALTY_START:
                blur_penalty = (qa.blur_score - self.BLUR_PENALTY_START) / (
                    self.BLUR_REJECT - self.BLUR_PENALTY_START
                )
                weight *= max(0.2, 1.0 - blur_penalty)
            
            # Shadow penalty
            if qa.shadow_severity > self.SHADOW_PENALTY_START:
                shadow_penalty = (qa.shadow_severity - self.SHADOW_PENALTY_START) / 0.6
                weight *= max(0.3, 1.0 - shadow_penalty * 0.5)
            
            # Motion smear penalty
            weight *= max(0.3, 1.0 - qa.motion_smear * 0.7)
            
            # Rolling shutter penalty
            weight *= max(0.5, 1.0 - qa.rolling_shutter_risk * 0.5)
            
            qa.quality_weight = round(weight, 3)
        else:
            qa.quality_weight = 0.0
        
        return qa
    
    def _assess_from_pixels(
        self, pixels: dict, qa: FrameQAResult
    ) -> None:
        """Compute QA metrics from synthetic pixel arrays.
        
        V1 heuristic: uses basic statistics. No learned models.
        """
        green = pixels.get("green", [])
        red = pixels.get("red", [])
        blue = pixels.get("blue", [])
        
        if not green or not green[0]:
            return
        
        h, w = len(green), len(green[0])
        total = h * w
        
        # --- Blur score (Laplacian variance proxy) ---
        laplacians = []
        for y in range(1, h - 1, 3):
            for x in range(1, w - 1, 3):
                g_val = green[y][x]
                if g_val > 0:
                    lap = (
                        green[y-1][x] + green[y+1][x] +
                        green[y][x-1] + green[y][x+1] - 4 * g_val
                    )
                    laplacians.append(lap)
        
        if laplacians:
            mean_l = sum(laplacians) / len(laplacians)
            var_l = sum((v - mean_l) ** 2 for v in laplacians) / len(laplacians)
            # Sharp images: var > 500. Blurred: var < 50.
            qa.blur_score = max(0.0, min(1.0, 1.0 - var_l / 500.0))
        
        # --- Exposure score ---
        sample_vals = []
        for y in range(0, h, 4):
            for x in range(0, w, 4):
                brightness = (red[y][x] + green[y][x] + blue[y][x]) / 3.0
                sample_vals.append(brightness)
        
        if sample_vals:
            mean_bright = sum(sample_vals) / len(sample_vals)
            # Good exposure: brightness 60-200
            if mean_bright < 30:
                qa.exposure_score = mean_bright / 30.0
            elif mean_bright > 230:
                qa.exposure_score = (255 - mean_bright) / 25.0
            else:
                qa.exposure_score = 1.0
            
            # Saturation check: how many pixels are near 255
            blown = sum(1 for v in sample_vals if v > 250)
            qa.saturation_score = blown / len(sample_vals)
        
        # --- Shadow severity ---
        if sample_vals:
            dark = sum(1 for v in sample_vals if v < 40)
            qa.shadow_severity = dark / len(sample_vals)
        
        # --- Vegetation content proxy ---
        veg_count = 0
        sample_count = 0
        for y in range(0, h, 4):
            for x in range(0, w, 4):
                r, g, b = red[y][x], green[y][x], blue[y][x]
                total_rgb = r + g + b
                if total_rgb > 0 and g / total_rgb > 0.38:
                    veg_count += 1
                sample_count += 1
        
        if sample_count > 0:
            qa.vegetation_content = veg_count / sample_count
