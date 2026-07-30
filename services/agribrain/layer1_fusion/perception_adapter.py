"""
Layer 0 Perception Adapter — Minimal Observation Handoff
=========================================================
Converts raw user/media evidence (photos, drone, IP camera, soil analysis,
sensors) into standardized observation products BEFORE Layer 1 fusion.

Each observation carries:
  - source_type
  - scope_type  (plot | zone | point | image_region)
  - confidence
  - supports_spatial_rendering: bool

This is the strict contract that Layer 1 and downstream layers consume.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum


# ── Enums ──────────────────────────────────────────────────────────────────────

class ScopeType(str, Enum):
    PLOT = "plot"
    ZONE = "zone"
    POINT = "point"
    IMAGE_REGION = "image_region"


class ObservationSourceType(str, Enum):
    PHOTO = "photo"
    DRONE = "drone"
    IP_CAMERA = "ip_camera"
    SOIL_ANALYSIS = "soil_analysis"
    SENSOR = "sensor"
    USER_NOTE = "user_note"


class ImageQualityGrade(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNUSABLE = "unusable"


# ── Observation Dataclasses ────────────────────────────────────────────────────

@dataclass
class ImageObservation:
    """Observation product derived from a photo, drone frame, or IP camera."""
    rgb_reference: Optional[str] = None           # URI or path to best image
    resolution_estimate: Optional[str] = None      # e.g. "high", "medium", "low"
    timestamp: Optional[str] = None
    gps_overlap: bool = False                      # does GPS match the plot?
    blur_detected: bool = False
    low_information: bool = False
    darkness_detected: bool = False
    image_quality: ImageQualityGrade = ImageQualityGrade.MEDIUM
    spatial_support_level: ScopeType = ScopeType.PLOT


@dataclass
class RowFeatureObservation:
    """Lightweight row/canopy structural cues from imagery."""
    row_direction: Optional[float] = None          # degrees from North
    row_regularity: Optional[float] = None         # 0-1 score
    visible_canopy_coverage: Optional[float] = None  # 0-1
    edge_irregularity: Optional[float] = None      # 0-1
    confidence: float = 0.0


@dataclass
class SoilObservation:
    """Structured soil analysis observation."""
    ph: Optional[float] = None
    ec: Optional[float] = None                     # dS/m
    om: Optional[float] = None                     # organic matter %
    nitrogen: Optional[float] = None               # mg/kg or ppm
    phosphorus: Optional[float] = None
    potassium: Optional[float] = None
    sample_date: Optional[str] = None
    sample_scope: ScopeType = ScopeType.PLOT       # whole-plot, zone, point
    sample_depth_cm: Optional[tuple] = None        # (from, to)
    sample_location: Optional[str] = None          # free text or GPS


@dataclass
class SensorObservation:
    """Normalized sensor observation summary."""
    sensor_type: str = ""                          # e.g. "soil_moisture", "temp"
    current_value: Optional[float] = None
    recent_trend: Optional[str] = None             # "rising", "stable", "falling"
    trust: float = 0.5
    quality: Optional[str] = None                  # "good", "degraded", "offline"
    spatial_scope: ScopeType = ScopeType.POINT


@dataclass
class PerceptionObservation:
    """Single normalized observation product with scope metadata."""
    source_type: ObservationSourceType
    scope_type: ScopeType
    confidence: float
    supports_spatial_rendering: bool
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[str] = None


@dataclass
class PerceptionObservationBundle:
    """
    The complete set of observation products extracted from a single run's
    raw user/media inputs. This is what Layer 1 fusion consumes.
    """
    image_observations: List[ImageObservation] = field(default_factory=list)
    row_features: Optional[RowFeatureObservation] = None
    soil_observations: List[SoilObservation] = field(default_factory=list)
    sensor_observations: List[SensorObservation] = field(default_factory=list)
    
    # Flattened typed observation list for direct injection into evidence pool
    observation_products: List[PerceptionObservation] = field(default_factory=list)
    
    # Aggregate flags for downstream layers
    plot_level_observations: List[PerceptionObservation] = field(default_factory=list)
    spatially_supported_observations: List[PerceptionObservation] = field(default_factory=list)


# ── Builder Functions ──────────────────────────────────────────────────────────

def _assess_image_quality(photo: Dict[str, Any]) -> ImageQualityGrade:
    """Heuristic image quality assessment from metadata."""
    # Check for known quality-degrading flags
    if photo.get("blur") or photo.get("blurry"):
        return ImageQualityGrade.LOW
    if photo.get("dark") or photo.get("darkness"):
        return ImageQualityGrade.LOW
    if photo.get("resolution") and photo["resolution"] in ("low", "thumbnail"):
        return ImageQualityGrade.LOW
    
    # Check timestamp freshness
    ts = photo.get("timestamp") or photo.get("date") or photo.get("created_at")
    if ts:
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            age_days = (datetime.now(dt.tzinfo) - dt).days if dt.tzinfo else (datetime.now() - dt).days
            if age_days > 30:
                return ImageQualityGrade.MEDIUM  # Aging image
        except (ValueError, TypeError):
            pass
    
    # Check GPS overlap
    has_gps = bool(photo.get("lat") or photo.get("latitude") or photo.get("gps"))
    if has_gps:
        return ImageQualityGrade.HIGH
    
    return ImageQualityGrade.MEDIUM


def _build_image_observation(photo: Dict[str, Any]) -> ImageObservation:
    """Convert a raw photo/drone/camera record into an ImageObservation."""
    quality = _assess_image_quality(photo)
    has_gps = bool(photo.get("lat") or photo.get("latitude") or photo.get("gps"))
    
    # Determine spatial support
    source = (photo.get("source") or photo.get("type") or "").lower()
    if source in ("drone", "uav") and has_gps:
        spatial_support = ScopeType.IMAGE_REGION
    elif has_gps:
        spatial_support = ScopeType.POINT
    else:
        spatial_support = ScopeType.PLOT
    
    return ImageObservation(
        rgb_reference=photo.get("url") or photo.get("uri") or photo.get("path"),
        resolution_estimate=photo.get("resolution", "medium"),
        timestamp=str(photo.get("timestamp") or photo.get("date") or photo.get("created_at") or ""),
        gps_overlap=has_gps,
        blur_detected=bool(photo.get("blur") or photo.get("blurry")),
        low_information=bool(photo.get("low_info")),
        darkness_detected=bool(photo.get("dark") or photo.get("darkness")),
        image_quality=quality,
        spatial_support_level=spatial_support,
    )


def _build_soil_observation(soil: Dict[str, Any]) -> SoilObservation:
    """Convert a soil analysis record into a SoilObservation."""
    # Determine scope from sampling location metadata
    scope_str = (soil.get("scope") or soil.get("sampling_location") or "plot").lower()
    if "zone" in scope_str:
        scope = ScopeType.ZONE
    elif "point" in scope_str or "gps" in scope_str:
        scope = ScopeType.POINT
    else:
        scope = ScopeType.PLOT
    
    depth = soil.get("depth") or soil.get("sampling_depth")
    depth_tuple = None
    if isinstance(depth, (list, tuple)) and len(depth) >= 2:
        depth_tuple = (depth[0], depth[1])
    elif isinstance(depth, dict):
        depth_tuple = (depth.get("from", 0), depth.get("to", 30))
    
    return SoilObservation(
        ph=_safe_float(soil.get("ph") or soil.get("pH")),
        ec=_safe_float(soil.get("ec") or soil.get("EC")),
        om=_safe_float(soil.get("om") or soil.get("organic_matter")),
        nitrogen=_safe_float(soil.get("n") or soil.get("nitrogen") or soil.get("N")),
        phosphorus=_safe_float(soil.get("p") or soil.get("phosphorus") or soil.get("P")),
        potassium=_safe_float(soil.get("k") or soil.get("potassium") or soil.get("K")),
        sample_date=str(soil.get("date") or soil.get("sample_date") or ""),
        sample_scope=scope,
        sample_depth_cm=depth_tuple,
        sample_location=soil.get("sampling_location") or soil.get("location"),
    )


def _build_sensor_observation(sensor: Dict[str, Any]) -> SensorObservation:
    """Convert a sensor packet into a SensorObservation."""
    scope_str = (sensor.get("scope") or sensor.get("coverage") or "point").lower()
    if "zone" in scope_str:
        scope = ScopeType.ZONE
    elif "plot" in scope_str or "field" in scope_str or "representative" in scope_str:
        scope = ScopeType.PLOT
    else:
        scope = ScopeType.POINT
    
    # Detect quality
    status = (sensor.get("status") or "").lower()
    quality = "good"
    if status in ("offline", "error", "fault"):
        quality = "offline"
    elif status in ("degraded", "low_battery", "noisy"):
        quality = "degraded"
    
    # Detect trend from recent readings
    readings = sensor.get("recent_readings") or sensor.get("history") or []
    trend = None
    if isinstance(readings, list) and len(readings) >= 3:
        try:
            last_3 = [float(r) if isinstance(r, (int, float)) else float(r.get("value", 0)) for r in readings[-3:]]
            delta = last_3[-1] - last_3[0]
            if delta > 0.05 * abs(last_3[0] + 0.001):
                trend = "rising"
            elif delta < -0.05 * abs(last_3[0] + 0.001):
                trend = "falling"
            else:
                trend = "stable"
        except (ValueError, TypeError, KeyError):
            pass
    
    return SensorObservation(
        sensor_type=sensor.get("type") or sensor.get("sensor_type") or "unknown",
        current_value=_safe_float(sensor.get("value") or sensor.get("current_value")),
        recent_trend=trend or sensor.get("trend"),
        trust=float(sensor.get("trust", sensor.get("confidence", 0.5))),
        quality=quality,
        spatial_scope=scope,
    )


def _attempt_row_features(image_obs_list: List[ImageObservation]) -> Optional[RowFeatureObservation]:
    """
    Attempt to compute lightweight row/canopy features from imagery.
    In production this would call a CV model; here we return None with
    confidence metadata to avoid fabrication.
    """
    # Only attempt if we have at least one high-quality, GPS-tagged image
    usable = [o for o in image_obs_list if o.image_quality in (ImageQualityGrade.HIGH, ImageQualityGrade.MEDIUM) and o.gps_overlap]
    if not usable:
        return None
    
    # Placeholder: return a zero-confidence stub indicating "attempted but no CV model"
    return RowFeatureObservation(
        row_direction=None,
        row_regularity=None,
        visible_canopy_coverage=None,
        edge_irregularity=None,
        confidence=0.0,  # Explicit: we didn't compute anything real
    )


def _safe_float(val: Any) -> Optional[float]:
    """Safely convert to float."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ── Main Entry Point ───────────────────────────────────────────────────────────

def build_perception_bundle(
    photos: Optional[List[Dict[str, Any]]] = None,
    soil_analyses: Optional[List[Dict[str, Any]]] = None,
    sensors: Optional[List[Dict[str, Any]]] = None,
) -> PerceptionObservationBundle:
    """
    Main entry point: converts raw user context dicts into a typed
    PerceptionObservationBundle ready for Layer 1 fusion consumption.
    """
    bundle = PerceptionObservationBundle()
    
    # ── 5.1 Photos / Drone / IP Camera ─────────────────────────────────────
    for photo in (photos or []):
        img_obs = _build_image_observation(photo)
        bundle.image_observations.append(img_obs)
        
        supports_spatial = img_obs.spatial_support_level in (ScopeType.IMAGE_REGION, ScopeType.ZONE)
        confidence = 0.7 if img_obs.image_quality == ImageQualityGrade.HIGH else 0.4 if img_obs.image_quality == ImageQualityGrade.MEDIUM else 0.15
        
        source_str = (photo.get("source") or photo.get("type") or "photo").lower()
        if source_str in ("drone", "uav"):
            obs_source = ObservationSourceType.DRONE
        elif source_str in ("ip_camera", "webcam", "camera"):
            obs_source = ObservationSourceType.IP_CAMERA
        else:
            obs_source = ObservationSourceType.PHOTO
        
        obs = PerceptionObservation(
            source_type=obs_source,
            scope_type=img_obs.spatial_support_level,
            confidence=confidence,
            supports_spatial_rendering=supports_spatial,
            payload={
                "rgb_reference": img_obs.rgb_reference,
                "image_quality": img_obs.image_quality.value,
                "gps_overlap": img_obs.gps_overlap,
                "resolution": img_obs.resolution_estimate,
            },
            timestamp=img_obs.timestamp,
        )
        bundle.observation_products.append(obs)
    
    # ── 5.4 Attempt row features from imagery ──────────────────────────────
    bundle.row_features = _attempt_row_features(bundle.image_observations)
    
    # ── 5.2 Soil Analysis ──────────────────────────────────────────────────
    for soil in (soil_analyses or []):
        soil_obs = _build_soil_observation(soil)
        bundle.soil_observations.append(soil_obs)
        
        supports_spatial = soil_obs.sample_scope in (ScopeType.ZONE, ScopeType.IMAGE_REGION)
        confidence = 0.85 if soil_obs.ph is not None else 0.5  # lab data is high-trust
        
        obs = PerceptionObservation(
            source_type=ObservationSourceType.SOIL_ANALYSIS,
            scope_type=soil_obs.sample_scope,
            confidence=confidence,
            supports_spatial_rendering=supports_spatial,
            payload={
                "ph": soil_obs.ph,
                "ec": soil_obs.ec,
                "om": soil_obs.om,
                "n": soil_obs.nitrogen,
                "p": soil_obs.phosphorus,
                "k": soil_obs.potassium,
                "sample_depth_cm": soil_obs.sample_depth_cm,
            },
            timestamp=soil_obs.sample_date,
        )
        bundle.observation_products.append(obs)
    
    # ── 5.3 Sensors ────────────────────────────────────────────────────────
    for sensor in (sensors or []):
        sensor_obs = _build_sensor_observation(sensor)
        bundle.sensor_observations.append(sensor_obs)

        supports_spatial = sensor_obs.spatial_scope in (ScopeType.ZONE,)
        
        obs = PerceptionObservation(
            source_type=ObservationSourceType.SENSOR,
            scope_type=sensor_obs.spatial_scope,
            confidence=sensor_obs.trust,
            supports_spatial_rendering=supports_spatial,
            payload={
                "sensor_type": sensor_obs.sensor_type,
                "current_value": sensor_obs.current_value,
                "recent_trend": sensor_obs.recent_trend,
                "quality": sensor_obs.quality,
            },
            timestamp=None,
        )
        bundle.observation_products.append(obs)
    
    # ── Partition into plot-level vs spatially-supported ────────────────────
    for obs in bundle.observation_products:
        if obs.supports_spatial_rendering:
            bundle.spatially_supported_observations.append(obs)
        else:
            bundle.plot_level_observations.append(obs)
    
    return bundle
