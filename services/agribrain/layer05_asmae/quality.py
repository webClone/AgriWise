"""
ASMAE Quality Assessment.

Quality scoring for scenes, operators, state estimates, and full runs.
Used by the resolution ladder and certification engine to gate outputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SceneQualityScore:
    """Quality assessment for a single observation scene.

    Formula:
      scene_quality =
          0.25 * clear_pixel_fraction
        + 0.20 * valid_polygon_coverage
        + 0.15 * radiometric_quality
        + 0.15 * temporal_spacing_score
        + 0.15 * metadata_completeness
        + 0.10 * sensor_specific_quality
    """
    scene_id: str = ""

    clear_pixel_fraction: float = 0.0
    valid_polygon_coverage: float = 0.0
    radiometric_quality: float = 0.0
    temporal_spacing_score: float = 0.0
    metadata_completeness: float = 0.0
    sensor_specific_quality: float = 0.0

    overall: float = 0.0

    def compute(self) -> float:
        self.overall = (
            0.25 * self.clear_pixel_fraction
            + 0.20 * self.valid_polygon_coverage
            + 0.15 * self.radiometric_quality
            + 0.15 * self.temporal_spacing_score
            + 0.15 * self.metadata_completeness
            + 0.10 * self.sensor_specific_quality
        )
        self.overall = round(max(0.0, min(1.0, self.overall)), 4)
        return self.overall


@dataclass
class OperatorQualityScore:
    """Quality assessment for an observation operator H_t."""
    operator_id: str = ""

    support_fraction: float = 0.0        # fraction of valid pixels
    condition_number_proxy: float = 0.0  # lower is better
    registration_quality: float = 0.0    # 1 - normalized registration error
    psf_appropriateness: float = 0.0     # PSF model suitability

    overall: float = 0.0

    def compute(self) -> float:
        self.overall = (
            0.30 * self.support_fraction
            + 0.25 * max(0.0, 1.0 - self.condition_number_proxy / 100.0)
            + 0.25 * self.registration_quality
            + 0.20 * self.psf_appropriateness
        )
        self.overall = round(max(0.0, min(1.0, self.overall)), 4)
        return self.overall


@dataclass
class StateEstimateQuality:
    """Quality assessment for a micro-zone state estimate."""
    microzone_id: str = ""

    mean_uncertainty: float = 0.0
    observation_count: int = 0
    days_since_observation: int = 0
    radiometric_consistency: float = 0.0
    temporal_plausibility: float = 0.0
    spatial_agreement: float = 0.0

    overall: float = 0.0

    def compute(self) -> float:
        # Decay quality with time since observation
        time_decay = max(0.0, 1.0 - self.days_since_observation / 60.0)
        obs_score = min(1.0, self.observation_count / 5.0)

        self.overall = (
            0.20 * max(0.0, 1.0 - self.mean_uncertainty)
            + 0.20 * obs_score
            + 0.15 * time_decay
            + 0.20 * self.radiometric_consistency
            + 0.15 * self.temporal_plausibility
            + 0.10 * self.spatial_agreement
        )
        self.overall = round(max(0.0, min(1.0, self.overall)), 4)
        return self.overall


@dataclass
class RunQualitySummary:
    """Aggregate quality summary for a full ASMAE run."""
    run_id: str = ""

    scene_count: int = 0
    scene_quality_mean: float = 0.0
    operator_quality_mean: float = 0.0
    state_quality_mean: float = 0.0
    radiometric_pass_rate: float = 0.0
    retrovalidation_score: Optional[float] = None
    bma_disagreement: Optional[float] = None

    invariant_violations_warning: int = 0
    invariant_violations_error: int = 0

    overall: float = 0.0

    def compute(self) -> float:
        weights_sum = 0.0
        score = 0.0

        if self.scene_count > 0:
            score += 0.15 * self.scene_quality_mean
            weights_sum += 0.15

        score += 0.20 * self.operator_quality_mean
        weights_sum += 0.20

        score += 0.25 * self.state_quality_mean
        weights_sum += 0.25

        score += 0.20 * self.radiometric_pass_rate
        weights_sum += 0.20

        if self.retrovalidation_score is not None:
            score += 0.15 * self.retrovalidation_score
            weights_sum += 0.15

        if self.bma_disagreement is not None:
            score += 0.05 * max(0.0, 1.0 - self.bma_disagreement)
            weights_sum += 0.05

        # Penalize invariant errors
        if self.invariant_violations_error > 0:
            score *= 0.5

        self.overall = round(score / max(weights_sum, 0.01), 4)
        self.overall = max(0.0, min(1.0, self.overall))
        return self.overall
