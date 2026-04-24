"""
Layer 0.8: Image QA — Quality Assessment for Camera/Drone/Phone Imagery

⚠️  LEGACY MODULE — This camera/phone/drone QA will be superseded by
    engine-specific QA modules. Each perception engine implements QA
    tuned to its source type:
      - satellite_rgb/qa.py  → cloud, haze, coverage, resolution, recentness
      - farmer_photo/qa.py   → blur, exposure, framing, GPS (planned)
      - drone/qa.py          → GSD, alignment, overlap (planned)
      - ip_camera/qa.py      → focus, exposure, timestamp drift (planned)

    Do not add new logic here. Existing callers will be migrated
    to engine-specific paths. This module is preserved for backward
    compatibility during migration.

Original QA checks:
  1. Blur / motion (variance of Laplacian)
  2. Exposure (over/under-exposed pixels)
  3. Color sanity (white balance, color cast)
  4. Occlusion / framing (is this actually field imagery)
  5. Timestamp sanity (camera clock drift)
  6. GPS sanity (distance to plot centroid)
  7. Drone-specific: GSD, alignment, seam artifacts

Output: ImageQAResult with flags + overall score → determines reliability weight.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import math
import hashlib


# ============================================================================
# QA Flags (same mental model as Sentinel2QA)
# ============================================================================

class ImageQAFlag:
    CLEAN = "CLEAN"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    BLUR = "BLUR"
    OVEREXPOSED = "OVEREXPOSED"
    UNDEREXPOSED = "UNDEREXPOSED"
    COLOR_CAST = "COLOR_CAST"
    OCCLUDED = "OCCLUDED"
    BAD_FRAMING = "BAD_FRAMING"
    TIMESTAMP_STALE = "TIMESTAMP_STALE"
    GPS_MISMATCH = "GPS_MISMATCH"
    PARTIAL_COVERAGE = "PARTIAL_COVERAGE"
    LOW_GSD = "LOW_GSD"


@dataclass
class ImageQAResult:
    """
    Complete QA assessment for one image.
    
    Consumed by perception_packet_factory to set ObservationPacket
    reliability_weight and uncertainty inflation.
    """
    image_hash: str = ""
    source_type: str = ""  # "phone", "ip_camera", "drone_ortho", "drone_frame"
    
    # Individual scores (0 = terrible, 1 = perfect)
    blur_score: float = 1.0
    exposure_score: float = 1.0
    color_score: float = 1.0
    framing_score: float = 1.0
    timestamp_score: float = 1.0
    geo_score: float = 1.0
    
    # Drone-specific
    gsd_m: Optional[float] = None
    alignment_score: float = 1.0
    
    # Overall
    overall_score: float = 1.0
    flags: List[str] = field(default_factory=list)
    
    # Derived
    reliability_weight: float = 1.0
    sigma_inflation: float = 1.0  # Multiply base sigma by this
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_hash": self.image_hash,
            "source_type": self.source_type,
            "blur_score": round(self.blur_score, 2),
            "exposure_score": round(self.exposure_score, 2),
            "color_score": round(self.color_score, 2),
            "framing_score": round(self.framing_score, 2),
            "timestamp_score": round(self.timestamp_score, 2),
            "geo_score": round(self.geo_score, 2),
            "overall_score": round(self.overall_score, 2),
            "reliability_weight": round(self.reliability_weight, 3),
            "sigma_inflation": round(self.sigma_inflation, 2),
            "flags": self.flags,
        }


# ============================================================================
# Image QA Engine
# ============================================================================

class ImageQAEngine:
    """
    Assesses image quality BEFORE any ML inference.
    
    Pure Python implementation — works with pixel statistics or metadata.
    Does NOT require OpenCV/PIL for the assessment itself (though actual
    pixel analysis helpers are provided for when those libraries exist).
    
    Usage:
        qa = ImageQAEngine()
        result = qa.assess(image_metadata, plot_context)
    """
    
    def assess(
        self,
        metadata: Dict[str, Any],
        plot_context: Optional[Dict[str, Any]] = None,
    ) -> ImageQAResult:
        """
        Assess image quality from metadata + optional pixel statistics.
        
        Args:
            metadata: {
                "source_type": "phone" | "ip_camera" | "drone_ortho" | "drone_frame",
                "width": int, "height": int,
                "timestamp": str (ISO format),
                "gps_lat": float, "gps_lng": float,  (optional)
                "pixel_stats": {  (optional, from actual pixel analysis)
                    "brightness_mean": float (0-255),
                    "brightness_std": float,
                    "laplacian_var": float (blur metric),
                    "green_ratio": float,
                    "saturation_mean": float,
                    "overexposed_pct": float,
                    "underexposed_pct": float,
                },
                "exif": {  (optional)
                    "focal_length": float,
                    "exposure_time": float,
                    "iso": int,
                    "orientation": int,
                },
                "drone": {  (optional, for drone imagery)
                    "altitude_m": float,
                    "gsd_m": float,
                    "overlap_pct": float,
                    "flight_quality": str,
                },
            }
            plot_context: {
                "lat": float, "lng": float,
                "area_ha": float,
                "current_date": str,
            }
        
        Returns:
            ImageQAResult with all scores and flags.
        """
        source_type = metadata.get("source_type", "phone")
        result = ImageQAResult(source_type=source_type)
        
        # Generate image hash for caching
        hash_input = f"{metadata.get('width', 0)}_{metadata.get('height', 0)}_{metadata.get('timestamp', '')}"
        result.image_hash = hashlib.md5(hash_input.encode()).hexdigest()[:12]
        
        # --- 1. Blur ---
        result.blur_score = self._assess_blur(metadata)
        
        # --- 2. Exposure ---
        result.exposure_score = self._assess_exposure(metadata)
        
        # --- 3. Color sanity ---
        result.color_score = self._assess_color(metadata)
        
        # --- 4. Framing / occlusion ---
        result.framing_score = self._assess_framing(metadata)
        
        # --- 5. Timestamp ---
        result.timestamp_score = self._assess_timestamp(metadata, plot_context)
        
        # --- 6. GPS ---
        result.geo_score = self._assess_geo(metadata, plot_context)
        
        # --- 7. Drone-specific ---
        if source_type in ("drone_ortho", "drone_frame"):
            drone = metadata.get("drone", {})
            result.gsd_m = drone.get("gsd_m")
            result.alignment_score = self._assess_drone(metadata)
        
        # --- Compute overall score ---
        scores = [
            result.blur_score,
            result.exposure_score,
            result.color_score,
            result.framing_score,
            result.timestamp_score,
            result.geo_score,
        ]
        if source_type in ("drone_ortho", "drone_frame"):
            scores.append(result.alignment_score)
        
        # Min-pooling: one bad score brings overall down significantly
        result.overall_score = (min(scores) + sum(scores) / len(scores)) / 2
        
        # --- Generate flags ---
        result.flags = self._generate_flags(result)
        
        # --- Derive reliability and sigma inflation ---
        result.reliability_weight = self._score_to_reliability(result.overall_score)
        result.sigma_inflation = self._score_to_sigma_inflation(result.overall_score)
        
        return result
    
    # ================================================================
    # Individual assessments
    # ================================================================
    
    def _assess_blur(self, meta: Dict) -> float:
        """Blur detection via Laplacian variance or resolution heuristic."""
        stats = meta.get("pixel_stats", {})
        laplacian_var = stats.get("laplacian_var")
        
        if laplacian_var is not None:
            # Laplacian variance: >100 = sharp, <20 = very blurry
            if laplacian_var > 100:
                return 1.0
            elif laplacian_var > 50:
                return 0.8
            elif laplacian_var > 20:
                return 0.5
            else:
                return 0.2
        
        # Fallback: resolution heuristic
        w = meta.get("width", 0)
        h = meta.get("height", 0)
        megapixels = (w * h) / 1e6
        if megapixels >= 5:
            return 0.9
        elif megapixels >= 2:
            return 0.7
        elif megapixels >= 0.5:
            return 0.5
        return 0.3
    
    def _assess_exposure(self, meta: Dict) -> float:
        """Exposure assessment from brightness statistics."""
        stats = meta.get("pixel_stats", {})
        
        brightness = stats.get("brightness_mean")
        overexposed = stats.get("overexposed_pct", 0)
        underexposed = stats.get("underexposed_pct", 0)
        
        score = 1.0
        
        if brightness is not None:
            if brightness < 30:
                score = 0.2  # Very dark
            elif brightness < 60:
                score = 0.6
            elif brightness > 240:
                score = 0.2  # Washed out
            elif brightness > 200:
                score = 0.6
        
        # Penalty for extreme exposure patches
        if overexposed > 30:
            score = min(score, 0.3)
        elif overexposed > 10:
            score = min(score, 0.6)
        
        if underexposed > 40:
            score = min(score, 0.3)
        
        # If no pixel stats, use EXIF heuristic
        if brightness is None:
            exif = meta.get("exif", {})
            iso = exif.get("iso", 100)
            if iso > 3200:
                score = 0.4  # Very high ISO = low light = noise
            elif iso > 1600:
                score = 0.6
        
        return score
    
    def _assess_color(self, meta: Dict) -> float:
        """Color sanity: white balance, color cast."""
        stats = meta.get("pixel_stats", {})
        green_ratio = stats.get("green_ratio")
        saturation = stats.get("saturation_mean")
        
        score = 1.0
        
        if green_ratio is not None:
            # In agricultural scenes, green should be 0.3–0.5
            # Very low green = bare soil or wrong white balance
            # Very high green = color cast
            if green_ratio < 0.15 or green_ratio > 0.6:
                score = 0.5
        
        if saturation is not None:
            # Extremely low saturation = grayscale/fog
            if saturation < 20:
                score = min(score, 0.4)
            # Extremely high = oversaturated
            elif saturation > 200:
                score = min(score, 0.6)
        
        return score
    
    def _assess_framing(self, meta: Dict) -> float:
        """Is this actually a field image (not a random photo)?"""
        stats = meta.get("pixel_stats", {})
        
        # Basic check: reasonable aspect ratio
        w = meta.get("width", 1)
        h = meta.get("height", 1)
        aspect = max(w, h) / max(min(w, h), 1)
        
        score = 1.0
        if aspect > 3:
            score = 0.6  # Very wide/tall = panoramic or cropped oddly
        
        # Green ratio as vegetation indicator
        green_ratio = stats.get("green_ratio")
        if green_ratio is not None and green_ratio < 0.1:
            score = min(score, 0.4)  # Probably not a field photo
        
        return score
    
    def _assess_timestamp(self, meta: Dict, context: Optional[Dict]) -> float:
        """Timestamp sanity check."""
        ts = meta.get("timestamp")
        if not ts:
            return 0.5  # No timestamp = uncertain
        
        if not context or "current_date" not in context:
            return 0.9  # Can't validate, assume OK
        
        try:
            from datetime import datetime
            img_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            cur_dt = datetime.fromisoformat(context["current_date"])
            
            days_old = abs((cur_dt - img_dt).days)
            
            if days_old > 30:
                return 0.2  # Very stale
            elif days_old > 7:
                return 0.5
            elif days_old > 1:
                return 0.8
            return 1.0
        except (ValueError, TypeError):
            return 0.5
    
    def _assess_geo(self, meta: Dict, context: Optional[Dict]) -> float:
        """GPS geotag sanity."""
        lat = meta.get("gps_lat")
        lng = meta.get("gps_lng")
        
        if lat is None or lng is None:
            return 0.5  # No GPS = moderate uncertainty
        
        if not context or "lat" not in context:
            return 0.8  # Can't validate distance
        
        # Haversine distance to plot centroid
        plot_lat = context["lat"]
        plot_lng = context["lng"]
        dist_km = self._haversine(lat, lng, plot_lat, plot_lng)
        
        if dist_km > 10:
            return 0.1  # Way too far
        elif dist_km > 2:
            return 0.3
        elif dist_km > 0.5:
            return 0.6
        elif dist_km > 0.1:
            return 0.8
        return 1.0
    
    def _assess_drone(self, meta: Dict) -> float:
        """Drone-specific quality checks."""
        drone = meta.get("drone", {})
        score = 1.0
        
        gsd = drone.get("gsd_m")
        if gsd is not None:
            if gsd > 1.0:
                score = 0.3  # Very low resolution
            elif gsd > 0.3:
                score = 0.6
            elif gsd > 0.1:
                score = 0.8
        
        overlap = drone.get("overlap_pct", 70)
        if overlap < 50:
            score = min(score, 0.5)  # Low overlap = poor mosaic
        
        quality = drone.get("flight_quality", "good")
        if quality == "poor":
            score = min(score, 0.4)
        
        return score
    
    # ================================================================
    # Score → reliability/sigma conversion
    # ================================================================
    
    @staticmethod
    def _score_to_reliability(score: float) -> float:
        """Convert QA score to Kalman reliability weight."""
        if score > 0.8:
            return 0.9
        elif score > 0.6:
            return 0.7
        elif score > 0.4:
            return 0.4
        elif score > 0.2:
            return 0.2
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
    
    @staticmethod
    def _generate_flags(result: ImageQAResult) -> List[str]:
        """Generate human-readable flags."""
        flags = []
        if result.blur_score < 0.5:
            flags.append(ImageQAFlag.BLUR)
        if result.exposure_score < 0.5:
            if result.exposure_score < 0.3:
                flags.append(ImageQAFlag.UNDEREXPOSED)
            else:
                flags.append(ImageQAFlag.OVEREXPOSED)
        if result.color_score < 0.5:
            flags.append(ImageQAFlag.COLOR_CAST)
        if result.framing_score < 0.5:
            flags.append(ImageQAFlag.BAD_FRAMING)
        if result.timestamp_score < 0.5:
            flags.append(ImageQAFlag.TIMESTAMP_STALE)
        if result.geo_score < 0.5:
            flags.append(ImageQAFlag.GPS_MISMATCH)
        if not flags:
            flags.append(ImageQAFlag.CLEAN)
        return flags
    
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
