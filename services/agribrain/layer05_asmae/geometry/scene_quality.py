"""
ASMAE Scene Quality Assessment.

Computes per-scene quality scores for the scene stack.
Scene quality determines:
  - Whether a scene is included or excluded
  - How much weight a scene gets in assimilation
  - Whether enough scenes exist for adaptive resolution

Formula:
  scene_quality =
      0.25 * clear_pixel_fraction
    + 0.20 * valid_polygon_coverage
    + 0.15 * radiometric_quality
    + 0.15 * temporal_spacing_score
    + 0.15 * metadata_completeness
    + 0.10 * sensor_specific_quality
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..config import SCENE_QUALITY_THRESHOLD


# ── Weights ──────────────────────────────────────────────────────────────────

W_CLEAR_PIXEL = 0.25
W_POLYGON_COVERAGE = 0.20
W_RADIOMETRIC = 0.15
W_TEMPORAL_SPACING = 0.15
W_METADATA = 0.15
W_SENSOR_SPECIFIC = 0.10


@dataclass
class SceneQualityResult:
    """Quality assessment for a single scene."""
    scene_id: str
    sensor: str

    clear_pixel_fraction: float = 0.0
    valid_polygon_coverage: float = 0.0
    radiometric_quality: float = 0.0
    temporal_spacing_score: float = 0.0
    metadata_completeness: float = 0.0
    sensor_specific_quality: float = 0.0

    overall: float = 0.0
    included: bool = True
    exclusion_reason: str = ""

    def compute(self) -> float:
        """Compute overall quality score from components."""
        self.overall = (
            W_CLEAR_PIXEL * self.clear_pixel_fraction
            + W_POLYGON_COVERAGE * self.valid_polygon_coverage
            + W_RADIOMETRIC * self.radiometric_quality
            + W_TEMPORAL_SPACING * self.temporal_spacing_score
            + W_METADATA * self.metadata_completeness
            + W_SENSOR_SPECIFIC * self.sensor_specific_quality
        )
        self.overall = round(max(0.0, min(1.0, self.overall)), 4)

        if self.clear_pixel_fraction < 0.05 or self.valid_polygon_coverage < 0.05:
            self.included = False
            self.exclusion_reason = (
                f"Zero valid scientific support (clear_fraction={self.clear_pixel_fraction:.3f}, "
                f"polygon_coverage={self.valid_polygon_coverage:.3f})"
            )
        elif self.overall < SCENE_QUALITY_THRESHOLD:
            self.included = False
            self.exclusion_reason = (
                f"Quality {self.overall:.3f} below threshold "
                f"{SCENE_QUALITY_THRESHOLD}"
            )
        return self.overall

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "sensor": self.sensor,
            "clear_pixel_fraction": self.clear_pixel_fraction,
            "valid_polygon_coverage": self.valid_polygon_coverage,
            "radiometric_quality": self.radiometric_quality,
            "temporal_spacing_score": self.temporal_spacing_score,
            "metadata_completeness": self.metadata_completeness,
            "sensor_specific_quality": self.sensor_specific_quality,
            "overall": self.overall,
            "included": self.included,
            "exclusion_reason": self.exclusion_reason,
        }


# ── Score Computation Functions ──────────────────────────────────────────────

def compute_clear_pixel_fraction(
    cloud_cover: Optional[float],
    valid_fraction: Optional[float],
) -> float:
    """Compute clear pixel fraction from cloud cover and valid fraction.

    Uses the minimum of (1 - cloud_cover) and valid_fraction.
    """
    cc = 0.0 if cloud_cover is None else float(cloud_cover)
    vf = 1.0 if valid_fraction is None else float(valid_fraction)

    # Normalize cloud_cover: if > 1, assume it's a percentage
    if cc > 1.0:
        cc = cc / 100.0
    cc = max(0.0, min(1.0, cc))
    vf = max(0.0, min(1.0, vf))

    return min(1.0 - cc, vf)


def compute_polygon_coverage(
    valid_fraction: Optional[float],
    usable: Optional[bool],
) -> float:
    """Estimate how much of the polygon is covered by valid observations."""
    if usable is False:
        return 0.0
    vf = 0.5 if valid_fraction is None else float(valid_fraction)
    return max(0.0, min(1.0, vf))


def compute_radiometric_quality(
    data_status: Optional[str],
    quality_class: Optional[str],
) -> float:
    """Score radiometric quality from data status and quality class.

    'observed' > 'estimated' > 'interpolated' > 'gap_filled'
    """
    status_scores = {
        "observed": 1.0,
        "measured": 1.0,
        "estimated": 0.7,
        "interpolated": 0.5,
        "gap_filled": 0.3,
        "modeled": 0.4,
    }
    quality_scores = {
        "excellent": 1.0,
        "good": 0.85,
        "fair": 0.6,
        "marginal": 0.4,
        "poor": 0.2,
        "bad": 0.1,
    }

    s = status_scores.get(str(data_status).lower(), 0.5)
    q = quality_scores.get(str(quality_class).lower(), 0.7)
    return round((s + q) / 2.0, 4)


def compute_temporal_spacing_score(
    days_since_previous: Optional[float],
    sensor: str = "S2",
) -> float:
    """Score temporal spacing relative to sensor revisit cadence.

    S2 revisit: ~5 days. Scores decay with distance from optimal.
    S1 revisit: ~6 days. SAR is less sensitive to exact timing.
    """
    if days_since_previous is None:
        return 0.5  # Unknown spacing → moderate score

    dsp = float(days_since_previous)
    if dsp <= 0:
        return 0.5

    if sensor == "S1":
        # SAR: optimal at 6-12 days
        if 4 <= dsp <= 14:
            return 1.0
        return max(0.1, 1.0 - abs(dsp - 8) / 30.0)
    else:
        # Optical: optimal at 5-10 days
        if 3 <= dsp <= 12:
            return 1.0
        return max(0.1, 1.0 - abs(dsp - 7) / 30.0)


def compute_metadata_completeness(
    has_crs: bool,
    has_transform: bool,
    has_acquisition_time: bool,
    has_sun_angles: bool = False,
    has_incidence_angle: bool = False,
) -> float:
    """Score metadata completeness based on available fields.

    Critical fields (CRS, transform, time) weighted more heavily.
    """
    score = 0.0
    total = 0.0

    # Critical fields
    if has_crs:
        score += 0.30
    total += 0.30

    if has_transform:
        score += 0.25
    total += 0.25

    if has_acquisition_time:
        score += 0.25
    total += 0.25

    # Optional fields
    if has_sun_angles:
        score += 0.10
    total += 0.10

    if has_incidence_angle:
        score += 0.10
    total += 0.10

    return round(score / total, 4) if total > 0 else 0.0


def compute_sensor_specific_quality(
    sensor: str,
    cloud_cover: Optional[float] = None,
    vv_db_mean: Optional[float] = None,
    vh_db_mean: Optional[float] = None,
    ndvi_mean: Optional[float] = None,
) -> float:
    """Sensor-specific quality heuristics.

    S2: Penalize heavy cloud, check NDVI plausibility.
    S1: Check SAR value ranges (VV/VH in reasonable dB range).
    """
    if sensor == "S2":
        score = 0.8
        if cloud_cover is not None:
            cc = float(cloud_cover)
            if cc > 1.0:
                cc /= 100.0
            if cc > 0.80:
                score = 0.1
            elif cc > 0.50:
                score = 0.4
        if ndvi_mean is not None:
            if -0.2 <= ndvi_mean <= 1.0:
                score = min(score, 0.9)
            else:
                score = min(score, 0.2)  # implausible NDVI
        return score

    elif sensor == "S1":
        score = 0.8
        if vv_db_mean is not None:
            # Typical VV: -25 to 0 dB
            if -30 <= vv_db_mean <= 5:
                score = max(score, 0.85)
            else:
                score = 0.3
        if vh_db_mean is not None:
            # Typical VH: -35 to -5 dB
            if -40 <= vh_db_mean <= 0:
                score = max(score, 0.85)
            else:
                score = 0.3
        return score

    elif sensor in ("S5P", "EXTERNAL"):
        return 0.7  # Default for non-primary sensors

    return 0.5
