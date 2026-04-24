"""
Satellite RGB QA — Quality Assessment for satellite RGB imagery.

NOT a reuse of the legacy camera/phone QA (blur, exposure, framing).
This module assesses satellite-specific quality factors:

  1. Cloud contamination
  2. Haze detection
  3. Plot coverage fraction (valid pixels inside polygon)
  4. Resolution sufficiency (plot area vs pixel count)
  5. Boundary contamination
  6. Acquisition recentness

Output: SatelliteRGBQAResult → determines reliability weight and sigma inflation.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import math

from ..common.contracts import QAResult


# ============================================================================
# QA Flag constants (these are QA flags, NOT measurement variables)
# ============================================================================

class SatelliteRGBQAFlag:
    CLEAN = "CLEAN"
    CLOUD_CONTAMINATED = "CLOUD_CONTAMINATED"
    HAZY = "HAZY"
    LOW_RESOLUTION = "LOW_RESOLUTION"
    INSUFFICIENT_PIXELS = "INSUFFICIENT_PIXELS"
    BOUNDARY_CONTAMINATED = "BOUNDARY_CONTAMINATED"
    STALE = "STALE"
    PARTIAL_COVERAGE = "PARTIAL_COVERAGE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


# ============================================================================
# QA Result
# ============================================================================

@dataclass
class SatelliteRGBQAResult(QAResult):
    """
    Satellite-specific QA result extending the shared QAResult.
    
    Carries satellite-specific sub-scores that feed into the
    overall qa_score / reliability_weight / sigma_inflation.
    """
    cloud_score: float = 1.0       # 1.0 = clear, 0.0 = fully cloudy
    haze_score: float = 1.0        # 1.0 = clear, 0.0 = fully hazy
    coverage_score: float = 1.0    # fraction of plot covered by valid pixels
    resolution_score: float = 1.0  # 1.0 = sufficient, 0.0 = too coarse
    boundary_score: float = 1.0    # 1.0 = clean edges, 0.0 = heavy contamination
    recentness_score: float = 1.0  # 1.0 = fresh, 0.0 = very stale

    # Computed feasibility flags
    resolution_sufficient_for_rows: bool = False


# ============================================================================
# QA Engine
# ============================================================================

class SatelliteRGBQA:
    """
    Quality assessment engine for satellite RGB imagery.
    
    Evaluates cloud, haze, coverage, resolution, boundary, and recentness.
    Does NOT check blur/exposure/color-cast (those are camera QA concerns).
    
    Usage:
        qa = SatelliteRGBQA()
        result = qa.assess(engine_input)
    """

    # Resolution thresholds
    MIN_RESOLUTION_FOR_BASIC = 30.0     # meters — below this, no useful analysis
    MIN_RESOLUTION_FOR_ROWS = 2.0       # meters — needed for row detection
    MIN_PIXELS_FOR_PLOT = 16            # absolute minimum pixel count inside plot

    # Recentness thresholds (days)
    FRESH_DAYS = 5
    MODERATE_DAYS = 15
    STALE_DAYS = 30

    def assess(
        self,
        ground_resolution_m: float,
        image_width: int,
        image_height: int,
        cloud_estimate: Optional[float] = None,
        haze_score: Optional[float] = None,
        recentness_days: Optional[int] = None,
        plot_area_ha: Optional[float] = None,
        coverage_fraction: Optional[float] = None,
        boundary_pixel_fraction: Optional[float] = None,
        sun_angle: Optional[float] = None,
        view_angle: Optional[float] = None,
    ) -> SatelliteRGBQAResult:
        """
        Assess satellite RGB image quality.
        
        Args:
            ground_resolution_m: pixel GSD in meters
            image_width, image_height: image dimensions in pixels
            cloud_estimate: 0–1 fraction of cloudy pixels over the plot
            haze_score: 0–1 haze level (0=clear, 1=fully hazy)
            recentness_days: days since acquisition
            plot_area_ha: plot area in hectares (for pixel sufficiency check)
            coverage_fraction: fraction of plot polygon covered by image
            boundary_pixel_fraction: fraction of pixels near the polygon boundary
            sun_angle: solar zenith angle in degrees
            view_angle: view zenith angle in degrees
        
        Returns:
            SatelliteRGBQAResult with all sub-scores and flags.
        """
        result = SatelliteRGBQAResult()
        flags: List[str] = []

        # --- 1. Cloud contamination ---
        result.cloud_score = self._assess_cloud(cloud_estimate)
        if result.cloud_score < 0.5:
            flags.append(SatelliteRGBQAFlag.CLOUD_CONTAMINATED)

        # --- 2. Haze ---
        result.haze_score = self._assess_haze(haze_score)
        if result.haze_score < 0.5:
            flags.append(SatelliteRGBQAFlag.HAZY)

        # --- 3. Plot coverage ---
        result.coverage_score = self._assess_coverage(
            coverage_fraction, image_width, image_height, ground_resolution_m, plot_area_ha
        )
        if result.coverage_score < 0.3:
            flags.append(SatelliteRGBQAFlag.PARTIAL_COVERAGE)

        # --- 4. Resolution sufficiency ---
        result.resolution_score = self._assess_resolution(
            ground_resolution_m, plot_area_ha
        )
        if result.resolution_score < 0.3:
            flags.append(SatelliteRGBQAFlag.LOW_RESOLUTION)

        # Check pixel count
        if plot_area_ha and ground_resolution_m > 0:
            plot_area_m2 = plot_area_ha * 10000
            pixel_area_m2 = ground_resolution_m ** 2
            estimated_pixels = plot_area_m2 / pixel_area_m2
            if estimated_pixels < self.MIN_PIXELS_FOR_PLOT:
                flags.append(SatelliteRGBQAFlag.INSUFFICIENT_PIXELS)
                result.resolution_score = min(result.resolution_score, 0.1)

        # Row detection feasibility
        result.resolution_sufficient_for_rows = (
            ground_resolution_m > 0 and
            ground_resolution_m <= self.MIN_RESOLUTION_FOR_ROWS
        )

        # --- 5. Boundary contamination ---
        result.boundary_score = self._assess_boundary(boundary_pixel_fraction)
        if result.boundary_score < 0.5:
            flags.append(SatelliteRGBQAFlag.BOUNDARY_CONTAMINATED)

        # --- 6. Recentness ---
        result.recentness_score = self._assess_recentness(recentness_days)
        if result.recentness_score <= 0.5:
            flags.append(SatelliteRGBQAFlag.STALE)

        # --- Compute overall score ---
        scores = [
            result.cloud_score,
            result.haze_score,
            result.coverage_score,
            result.resolution_score,
            result.boundary_score,
            result.recentness_score,
        ]
        # Min-pooling + average: one bad dimension drags it down
        result.qa_score = (min(scores) + sum(scores) / len(scores)) / 2
        result.qa_score = max(0.0, min(1.0, result.qa_score))

        # --- Determine usability ---
        result.usable = result.qa_score >= 0.1

        # --- Derive reliability and sigma inflation ---
        result.reliability_weight = self._score_to_reliability(result.qa_score)
        result.sigma_inflation = self._score_to_sigma_inflation(result.qa_score)

        # --- Low confidence flag ---
        if result.qa_score < 0.3:
            flags.append(SatelliteRGBQAFlag.LOW_CONFIDENCE)

        # --- Clean flag ---
        if not flags:
            flags.append(SatelliteRGBQAFlag.CLEAN)

        result.flags = flags
        result.details = {
            "cloud_score": round(result.cloud_score, 3),
            "haze_score": round(result.haze_score, 3),
            "coverage_score": round(result.coverage_score, 3),
            "resolution_score": round(result.resolution_score, 3),
            "boundary_score": round(result.boundary_score, 3),
            "recentness_score": round(result.recentness_score, 3),
            "ground_resolution_m": ground_resolution_m,
            "row_detection_feasible": result.resolution_sufficient_for_rows,
        }

        return result

    # ================================================================
    # Individual assessments
    # ================================================================

    def _assess_cloud(self, cloud_estimate: Optional[float]) -> float:
        """Cloud contamination: 0=fully cloudy, 1=clear."""
        if cloud_estimate is None:
            return 0.7  # Unknown cloud → moderate uncertainty
        return max(0.0, 1.0 - cloud_estimate)

    def _assess_haze(self, haze_score: Optional[float]) -> float:
        """Haze assessment: input is 0=clear, 1=hazy; output is 0=bad, 1=good."""
        if haze_score is None:
            return 0.8  # Unknown haze → assume mostly clear
        return max(0.0, 1.0 - haze_score)

    def _assess_coverage(
        self,
        coverage_fraction: Optional[float],
        width: int,
        height: int,
        resolution_m: float,
        plot_area_ha: Optional[float],
    ) -> float:
        """Plot coverage: what fraction of the plot polygon has valid pixels."""
        if coverage_fraction is not None:
            return max(0.0, min(1.0, coverage_fraction))

        # Estimate from image dimensions and plot area
        if plot_area_ha and resolution_m > 0:
            image_area_ha = (width * resolution_m * height * resolution_m) / 10000
            coverage = min(1.0, plot_area_ha / max(image_area_ha, 0.01))
            return max(0.0, coverage)

        return 0.7  # Unknown → moderate

    def _assess_resolution(
        self,
        resolution_m: float,
        plot_area_ha: Optional[float],
    ) -> float:
        """Resolution sufficiency for the plot."""
        if resolution_m <= 0:
            return 0.0

        if resolution_m > self.MIN_RESOLUTION_FOR_BASIC:
            return 0.1  # Too coarse for any useful analysis

        if resolution_m <= 1.0:
            return 1.0  # Excellent (sub-meter)
        elif resolution_m <= 5.0:
            return 0.9  # Good (typical high-res)
        elif resolution_m <= 10.0:
            return 0.7  # Acceptable (Sentinel-2)
        elif resolution_m <= 20.0:
            return 0.5  # Marginal
        else:
            return max(0.1, 1.0 - resolution_m / 50.0)

    def _assess_boundary(self, boundary_pixel_fraction: Optional[float]) -> float:
        """Boundary contamination: fraction of boundary-adjacent pixels."""
        if boundary_pixel_fraction is None:
            return 0.8  # Unknown → assume moderate
        # High boundary fraction = more contamination = lower score
        return max(0.0, 1.0 - boundary_pixel_fraction * 2.0)

    def _assess_recentness(self, recentness_days: Optional[int]) -> float:
        """Acquisition recentness: fresher is better."""
        if recentness_days is None:
            return 0.7  # Unknown age → moderate

        if recentness_days <= self.FRESH_DAYS:
            return 1.0
        elif recentness_days <= self.MODERATE_DAYS:
            return 0.8
        elif recentness_days <= self.STALE_DAYS:
            return 0.5
        else:
            return max(0.1, 1.0 - recentness_days / 90.0)

    # ================================================================
    # Score → reliability/sigma conversion
    # ================================================================

    @staticmethod
    def _score_to_reliability(score: float) -> float:
        """Convert QA score to Kalman reliability weight."""
        if score > 0.8:
            return 0.85
        elif score > 0.6:
            return 0.65
        elif score > 0.4:
            return 0.40
        elif score > 0.2:
            return 0.20
        return 0.05  # Nearly ignored

    @staticmethod
    def _score_to_sigma_inflation(score: float) -> float:
        """Convert QA score to sigma multiplier."""
        if score > 0.8:
            return 1.0
        elif score > 0.6:
            return 1.5
        elif score > 0.4:
            return 2.5
        elif score > 0.2:
            return 4.0
        return 8.0  # Very uncertain
