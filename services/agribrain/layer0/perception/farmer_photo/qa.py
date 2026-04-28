"""
Farmer Photo QA — Camera/Phone Quality Assessment + Field Gate.

This is NOT satellite QA (cloud, haze, resolution).
This is close-range camera QA:

  1. Blur / motion (Laplacian variance or resolution proxy)
  2. Exposure (brightness, over/underexposed pixels)
  3. Color sanity (white balance, saturation extremes)
  4. Field gate — is this even an agronomic image?
  5. GPS validation (distance to plot centroid)
  6. Timestamp sanity (photo age)
  7. Framing (aspect ratio, resolution adequacy)

The FIELD GATE is the most important check.
Without it, random user photos poison the engine.

Output: FarmerPhotoQAResult -> determines reliability weight and sigma inflation.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
import math

from layer0.perception.common.contracts import QAResult
from layer0.perception.farmer_photo.schemas import SceneResult, SceneClass


# ============================================================================
# QA Flag constants
# ============================================================================

class FarmerPhotoQAFlag:
    CLEAN = "CLEAN"
    NON_FIELD = "NON_FIELD"
    NO_PLANT_VISIBLE = "NO_PLANT_VISIBLE"
    BLURRY = "BLURRY"
    OVEREXPOSED = "OVEREXPOSED"
    UNDEREXPOSED = "UNDEREXPOSED"
    COLOR_CAST = "COLOR_CAST"
    BAD_FRAMING = "BAD_FRAMING"
    GPS_FAR = "GPS_FAR"
    GPS_MISSING = "GPS_MISSING"
    STALE = "STALE"
    LOW_RESOLUTION = "LOW_RESOLUTION"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    LOAD_ERROR = "LOAD_ERROR"


# ============================================================================
# QA Result
# ============================================================================

@dataclass
class FarmerPhotoQAResult(QAResult):
    """
    Camera-specific QA result extending the shared QAResult.

    Sub-scores feed into overall qa_score / reliability_weight / sigma_inflation.
    """
    blur_score: float = 1.0         # 1.0 = sharp, 0.0 = very blurry
    exposure_score: float = 1.0     # 1.0 = well exposed
    color_score: float = 1.0        # 1.0 = natural colors
    framing_score: float = 1.0      # 1.0 = good composition
    geo_score: float = 1.0          # 1.0 = GPS matches plot
    timestamp_score: float = 1.0    # 1.0 = fresh

    # Field gate result
    field_likelihood: float = 0.5   # 0=definitely not field, 1=clearly field
    plant_visible: bool = True


# ============================================================================
# QA Engine
# ============================================================================

class FarmerPhotoQA:
    """
    Quality assessment engine for farmer phone/camera photos.

    The most important check is the field gate: is this actually
    an agronomic image? Without this, random photos poison the engine.
    """

    # Blur thresholds (Laplacian variance)
    SHARP_LAP_VAR = 100.0
    MODERATE_LAP_VAR = 50.0
    BLURRY_LAP_VAR = 20.0

    # Resolution thresholds
    MIN_MEGAPIXELS = 0.3       # below this, image is too small
    GOOD_MEGAPIXELS = 2.0

    # GPS distance thresholds (km)
    GPS_CLOSE_KM = 0.1
    GPS_MODERATE_KM = 0.5
    GPS_FAR_KM = 2.0
    GPS_REJECT_KM = 10.0

    # Staleness thresholds (days)
    FRESH_DAYS = 1
    MODERATE_DAYS = 7
    STALE_DAYS = 30

    def assess(
        self,
        image_width: int = 0,
        image_height: int = 0,
        pixel_stats: Optional[Dict[str, Any]] = None,
        exif: Optional[Dict[str, Any]] = None,
        gps_lat: Optional[float] = None,
        gps_lng: Optional[float] = None,
        plot_centroid_lat: Optional[float] = None,
        plot_centroid_lng: Optional[float] = None,
        recentness_days: Optional[int] = None,
        user_label: Optional[str] = None,
        scene: Optional[SceneResult] = None,
        load_error: Optional[str] = None,
    ) -> FarmerPhotoQAResult:
        """
        Assess farmer photo quality.

        Args:
            image_width, image_height: image dimensions in pixels
            pixel_stats: pre-computed pixel statistics (optional)
            exif: EXIF data dict (optional)
            gps_lat, gps_lng: photo GPS coordinates
            plot_centroid_lat, plot_centroid_lng: plot centroid for distance check
            recentness_days: days since photo was taken
            user_label: user-provided label ("leaf", "canopy", etc.)
        """
        result = FarmerPhotoQAResult()
        flags: List[str] = []
        stats = pixel_stats or {}

        # --- 1. Blur ---
        result.blur_score = self._assess_blur(stats, image_width, image_height)
        if result.blur_score < 0.4:
            flags.append(FarmerPhotoQAFlag.BLURRY)

        # --- 2. Exposure ---
        result.exposure_score = self._assess_exposure(stats, exif)
        if result.exposure_score < 0.4:
            brightness = stats.get("brightness_mean", 128)
            if brightness < 60:
                flags.append(FarmerPhotoQAFlag.UNDEREXPOSED)
            else:
                flags.append(FarmerPhotoQAFlag.OVEREXPOSED)

        # --- 3. Color sanity ---
        result.color_score = self._assess_color(stats)
        if result.color_score < 0.5:
            flags.append(FarmerPhotoQAFlag.COLOR_CAST)

        # --- 4. Field gate (most important check) ---
        if scene is not None:
            if scene.scene_class in (SceneClass.NON_FIELD, SceneClass.UNUSABLE):
                result.field_likelihood = 1.0 - scene.confidence
            else:
                result.field_likelihood = scene.confidence
                
            result.plant_visible = scene.scene_class not in (SceneClass.NON_FIELD, SceneClass.UNUSABLE, "soil_scene")
            if scene.scene_class == SceneClass.NON_FIELD:
                flags.append(FarmerPhotoQAFlag.NON_FIELD)
            elif not result.plant_visible and scene.scene_class != "soil_scene":
                flags.append(FarmerPhotoQAFlag.NO_PLANT_VISIBLE)
        else:
            # Fallback if scene gate not provided
            result.field_likelihood = self._assess_field_gate(
                stats, image_width, image_height, user_label
            )
            result.plant_visible = result.field_likelihood > 0.3
            if result.field_likelihood < 0.25:
                flags.append(FarmerPhotoQAFlag.NON_FIELD)
            elif not result.plant_visible:
                flags.append(FarmerPhotoQAFlag.NO_PLANT_VISIBLE)

        # --- 5. GPS ---
        result.geo_score = self._assess_geo(
            gps_lat, gps_lng, plot_centroid_lat, plot_centroid_lng
        )
        if gps_lat is None or gps_lng is None:
            flags.append(FarmerPhotoQAFlag.GPS_MISSING)
        elif result.geo_score < 0.4:
            flags.append(FarmerPhotoQAFlag.GPS_FAR)

        # --- 6. Timestamp ---
        result.timestamp_score = self._assess_timestamp(recentness_days)
        if result.timestamp_score <= 0.4:
            flags.append(FarmerPhotoQAFlag.STALE)

        # --- 7. Framing ---
        result.framing_score = self._assess_framing(
            stats, image_width, image_height
        )
        if result.framing_score < 0.4:
            flags.append(FarmerPhotoQAFlag.BAD_FRAMING)

        # --- Resolution check ---
        megapixels = (image_width * image_height) / 1e6
        if megapixels < self.MIN_MEGAPIXELS and image_width > 0:
            flags.append(FarmerPhotoQAFlag.LOW_RESOLUTION)

        # --- Compute overall score ---
        scores = [
            result.blur_score,
            result.exposure_score,
            result.color_score,
            result.field_likelihood,
            result.geo_score,
            result.timestamp_score,
            result.framing_score,
        ]
        # Min-pooling + average (same strategy as satellite QA)
        result.qa_score = (min(scores) + sum(scores) / len(scores)) / 2
        result.qa_score = max(0.0, min(1.0, result.qa_score))
        
        if load_error:
            flags.append(FarmerPhotoQAFlag.LOAD_ERROR)
            result.qa_score = 0.0

        # --- Usability ---
        # Non-field images are not usable for agronomic inference
        is_field = FarmerPhotoQAFlag.NON_FIELD not in flags
        result.usable = result.qa_score >= 0.1 and is_field and not load_error

        # --- Reliability and sigma inflation ---
        if load_error:
            result.reliability_weight = 0.0
            result.sigma_inflation = 10.0
        else:
            result.reliability_weight = self._score_to_reliability(result.qa_score)
            result.sigma_inflation = self._score_to_sigma_inflation(result.qa_score)

        # --- Low confidence flag ---
        if result.qa_score < 0.3 and not load_error:
            flags.append(FarmerPhotoQAFlag.LOW_CONFIDENCE)

        # --- Clean flag ---
        if not flags:
            flags.append(FarmerPhotoQAFlag.CLEAN)

        result.flags = flags
        result.details = {
            "blur_score": round(result.blur_score, 3),
            "exposure_score": round(result.exposure_score, 3),
            "color_score": round(result.color_score, 3),
            "field_likelihood": round(result.field_likelihood, 3),
            "geo_score": round(result.geo_score, 3),
            "timestamp_score": round(result.timestamp_score, 3),
            "framing_score": round(result.framing_score, 3),
            "plant_visible": result.plant_visible,
        }
        return result

    # ================================================================
    # Individual assessments
    # ================================================================

    def _assess_blur(self, stats: Dict, width: int, height: int) -> float:
        """Blur detection via Laplacian variance or resolution proxy."""
        laplacian_var = stats.get("laplacian_var")
        if laplacian_var is not None:
            if laplacian_var > self.SHARP_LAP_VAR:
                return 1.0
            elif laplacian_var > self.MODERATE_LAP_VAR:
                return 0.8
            elif laplacian_var > self.BLURRY_LAP_VAR:
                return 0.5
            return 0.2

        # Fallback: resolution proxy
        mp = (width * height) / 1e6
        if mp >= 5.0:
            return 0.9
        elif mp >= self.GOOD_MEGAPIXELS:
            return 0.7
        elif mp >= 0.5:
            return 0.5
        elif mp > 0:
            return 0.3
        return 0.1  # No size info

    def _assess_exposure(self, stats: Dict, exif: Optional[Dict]) -> float:
        """Exposure assessment from brightness statistics or EXIF."""
        brightness = stats.get("brightness_mean")
        overexposed_pct = stats.get("overexposed_pct", 0)
        underexposed_pct = stats.get("underexposed_pct", 0)

        score = 1.0
        if brightness is not None:
            if brightness < 30:
                score = 0.2
            elif brightness < 60:
                score = 0.6
            elif brightness > 240:
                score = 0.2
            elif brightness > 200:
                score = 0.6

        if overexposed_pct > 30:
            score = min(score, 0.3)
        elif overexposed_pct > 10:
            score = min(score, 0.6)
        if underexposed_pct > 40:
            score = min(score, 0.3)

        # EXIF fallback
        if brightness is None and exif:
            iso = exif.get("iso", 100)
            if iso > 3200:
                score = 0.4
            elif iso > 1600:
                score = 0.6

        return score

    def _assess_color(self, stats: Dict) -> float:
        """Color sanity: white balance, saturation extremes."""
        green_ratio = stats.get("green_ratio")
        saturation = stats.get("saturation_mean")

        score = 1.0
        if green_ratio is not None:
            if green_ratio < 0.10 or green_ratio > 0.65:
                score = 0.4  # Extreme color cast
            elif green_ratio < 0.15 or green_ratio > 0.55:
                score = 0.6

        if saturation is not None:
            if saturation < 15:
                score = min(score, 0.3)  # Nearly grayscale
            elif saturation > 220:
                score = min(score, 0.5)  # Oversaturated

        return score

    def _assess_field_gate(
        self,
        stats: Dict,
        width: int,
        height: int,
        user_label: Optional[str],
    ) -> float:
        """
        Field / agronomic image gate — the most important check.

        Uses color/brightness/saturation distributions to estimate
        whether this is actually agricultural content.

        Returns 0–1 field likelihood. Below 0.25 = NON_FIELD.
        """
        # User label override — if user says it's a leaf, trust partially
        if user_label and user_label.lower() in (
            "leaf", "canopy", "fruit", "stem", "soil", "field", "crop"
        ):
            label_boost = 0.3
        else:
            label_boost = 0.0

        score = 0.0
        penalty = 0.0

        green_ratio = stats.get("green_ratio")
        saturation = stats.get("saturation_mean")
        brightness = stats.get("brightness_mean")

        has_evidence = False

        # Green vegetation presence — the primary field indicator
        if green_ratio is not None:
            has_evidence = True
            if green_ratio > 0.30:
                score += 0.40  # Strong vegetation signal
            elif green_ratio > 0.20:
                score += 0.20  # Some vegetation or soil
            elif green_ratio > 0.12:
                score += 0.08  # Very weak
            else:
                penalty += 0.20  # Strong non-field indicator

        # Outdoor lighting signature (moderate saturation)
        if saturation is not None:
            has_evidence = True
            if 40 < saturation < 180:
                score += 0.25  # Outdoor-like lighting
            elif saturation < 20:
                penalty += 0.15  # Indoor / grayscale / document
            else:
                score += 0.05

        # Brightness — secondary signal
        if brightness is not None:
            has_evidence = True
            if 40 < brightness < 200:
                score += 0.15
            else:
                score += 0.03

        # Resolution — weak secondary signal
        if width > 0 and height > 0:
            has_evidence = True
            mp = (width * height) / 1e6
            if mp >= 1.0:
                score += 0.10
            elif mp >= 0.3:
                score += 0.05

        # If no evidence, assume uncertain
        if not has_evidence:
            return 0.35 + label_boost

        # Apply penalty — low green + low saturation is a strong negative
        likelihood = max(0.0, min(1.0, score - penalty + label_boost))
        return likelihood

    def _assess_geo(
        self,
        gps_lat: Optional[float],
        gps_lng: Optional[float],
        plot_lat: Optional[float],
        plot_lng: Optional[float],
    ) -> float:
        """GPS validation: distance from photo to plot centroid."""
        if gps_lat is None or gps_lng is None:
            return 0.5  # Missing GPS -> moderate uncertainty

        if plot_lat is None or plot_lng is None:
            return 0.8  # Can't validate, assume OK

        dist_km = self._haversine(gps_lat, gps_lng, plot_lat, plot_lng)
        if dist_km > self.GPS_REJECT_KM:
            return 0.1
        elif dist_km > self.GPS_FAR_KM:
            return 0.3
        elif dist_km > self.GPS_MODERATE_KM:
            return 0.6
        elif dist_km > self.GPS_CLOSE_KM:
            return 0.8
        return 1.0

    def _assess_timestamp(self, recentness_days: Optional[int]) -> float:
        """Photo age assessment."""
        if recentness_days is None:
            return 0.5  # Unknown age
        if recentness_days <= self.FRESH_DAYS:
            return 1.0
        elif recentness_days <= self.MODERATE_DAYS:
            return 0.8
        elif recentness_days <= self.STALE_DAYS:
            return 0.5
        # Beyond stale threshold: drops below 0.4 rapidly
        return max(0.1, 0.4 - (recentness_days - self.STALE_DAYS) / 90.0)

    def _assess_framing(
        self, stats: Dict, width: int, height: int
    ) -> float:
        """Framing quality: aspect ratio, composition heuristics."""
        if width <= 0 or height <= 0:
            return 0.3

        aspect = max(width, height) / max(min(width, height), 1)
        score = 1.0
        if aspect > 3.0:
            score = 0.5  # Very elongated
        elif aspect > 2.0:
            score = 0.7

        # Very small images are poorly framed
        mp = (width * height) / 1e6
        if mp < self.MIN_MEGAPIXELS:
            score = min(score, 0.3)

        return score

    # ================================================================
    # Score -> reliability/sigma conversion
    # ================================================================

    @staticmethod
    def _score_to_reliability(score: float) -> float:
        """Convert QA score to Kalman reliability weight."""
        if score > 0.8:
            return 0.75   # Slightly lower ceiling than satellite
        elif score > 0.6:
            return 0.55
        elif score > 0.4:
            return 0.35
        elif score > 0.2:
            return 0.15
        return 0.05

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
        return 8.0

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine distance in km."""
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
