"""
Layer 0.1: ObservationPacket — Universal Ingestion Schema

Every data source (S2, S1, weather, soil, sensor, user, drone, camera)
is normalized into ObservationPackets before entering the assimilation engine.

Each packet carries:
  - payload (the actual data)
  - QA metadata (cloud %, incidence angle, noise floor, sensor health)
  - uncertainty model (per-band sigma or measurement error)
  - provenance (processing steps, version, license)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import json


# ============================================================================
# Enums
# ============================================================================

class ObservationSource(str, Enum):
    """All sources that can produce observations."""
    SENTINEL2 = "sentinel2"
    SENTINEL1 = "sentinel1"
    WEATHER_STATION = "weather_station"
    WEATHER_REANALYSIS = "weather_reanalysis"  # Open-Meteo / ERA5
    WEATHER_FORECAST = "weather_forecast"
    SOILGRIDS = "soilgrids"
    FAO = "fao"
    SENSOR_IOT = "sensor_iot"
    USER_EVENT = "user_event"          # sowing, irrigation, fertilizer
    USER_OBSERVATION = "user_observation"  # phone photo, field note
    DRONE = "drone"
    IP_CAMERA = "ip_camera"
    NASA_POWER = "nasa_power"
    MODIS_FIRMS = "modis_firms"
    SATELLITE_RGB = "satellite_rgb"    # High-res RGB structural intelligence
    FARMER_PHOTO = "farmer_photo"      # Close-range plant recognition + symptom evidence
    SENTINEL5P = "sentinel5p"          # TROPOMI — Solar-Induced Fluorescence (SIF)


class ObservationType(str, Enum):
    """Geometry/format of the observation."""
    RASTER = "raster"              # gridded imagery (S2, S1, drone ortho)
    POINT_TIMESERIES = "point_ts"  # weather station, soil sensor
    VECTOR = "vector"              # polygon/point event (sowing, irrigation)
    IMAGE = "image"                # phone/camera photo (unstructured)
    TABULAR = "tabular"            # SoilGrids point query, FAO lookup


class QAFlag(str, Enum):
    """Quality flags that can be attached to an observation."""
    CLEAN = "clean"
    CLOUD_CONTAMINATED = "cloud_contaminated"
    CLOUD_EDGE = "cloud_edge"
    HIGH_INCIDENCE_ANGLE = "high_incidence_angle"
    BORDER_NOISE = "border_noise"
    SENSOR_DRIFT = "sensor_drift"
    OUTLIER = "outlier"
    STALE = "stale"                # data is old / from cache
    INTERPOLATED = "interpolated"  # not a direct measurement
    LOW_CONFIDENCE = "low_confidence"
    PARTIAL_COVERAGE = "partial_coverage"


# ============================================================================
# Core Schema
# ============================================================================

@dataclass
class UncertaintyModel:
    """
    Per-variable measurement uncertainty.
    
    For rasters: sigma per band/index.
    For point measurements: scalar sigma.
    For categorical: confusion matrix or probability.
    """
    sigmas: Dict[str, float] = field(default_factory=dict)
    # e.g. {"ndvi": 0.02, "evi": 0.03, "ndmi": 0.04}
    #      {"vv": 1.5, "vh": 2.0}  (dB)
    #      {"temperature_2m": 0.5}  (°C)
    
    error_model: str = "gaussian"  # "gaussian", "uniform", "laplace"
    
    # For rasters: optional per-pixel uncertainty scale factor
    spatial_variance_factor: float = 1.0
    
    def get_sigma(self, variable: str, default: float = 1.0) -> float:
        return self.sigmas.get(variable, default)


@dataclass
class Provenance:
    """
    Tracks where data came from and how it was processed.
    """
    processing_chain: List[str] = field(default_factory=list)
    # e.g. ["download_scihub", "atmospheric_correction_L2A", "cloud_mask_SCL", "index_computation"]
    
    software_version: str = "agriwise-layer0-v1"
    source_url: Optional[str] = None       # API endpoint or file path
    license: str = "copernicus-open"
    download_timestamp: Optional[datetime] = None
    cache_hit: bool = False


@dataclass
class QAMetadata:
    """
    Source-specific quality assessment.
    """
    flags: List[QAFlag] = field(default_factory=list)
    
    # Optical (S2)
    cloud_probability: Optional[float] = None   # 0–1
    shadow_probability: Optional[float] = None  # 0–1
    valid_pixel_fraction: Optional[float] = None # 0–1
    view_zenith_angle: Optional[float] = None    # degrees
    sun_zenith_angle: Optional[float] = None     # degrees
    scene_classification: Optional[str] = None   # SCL class
    
    # SAR (S1)
    incidence_angle: Optional[float] = None      # degrees
    orbit_direction: Optional[str] = None        # "ascending" / "descending"
    relative_orbit: Optional[int] = None
    
    # Weather
    station_distance_km: Optional[float] = None  # distance to nearest station
    reanalysis_bias: Optional[float] = None      # estimated bias vs station
    
    # Sensor
    sensor_health: Optional[float] = None        # 0–1
    calibration_age_days: Optional[int] = None
    
    # General
    scene_score: float = 1.0  # 0–1 overall quality score
    
    def is_clean(self) -> bool:
        return QAFlag.CLEAN in self.flags or len(self.flags) == 0
    
    def compute_scene_score(self) -> float:
        """Compute an aggregate quality score from individual QA metrics."""
        score = 1.0
        
        if self.cloud_probability is not None:
            score *= max(0.0, 1.0 - self.cloud_probability)
        if self.shadow_probability is not None:
            score *= max(0.0, 1.0 - self.shadow_probability * 0.5)
        if self.valid_pixel_fraction is not None:
            score *= self.valid_pixel_fraction
        if self.incidence_angle is not None:
            # Quality degrades at steep angles (> 40°)
            if self.incidence_angle > 40:
                score *= max(0.3, 1.0 - (self.incidence_angle - 40) / 30)
        if self.sensor_health is not None:
            score *= self.sensor_health
        
        # Penalty for flags
        penalty_flags = {
            QAFlag.CLOUD_CONTAMINATED: 0.3,
            QAFlag.CLOUD_EDGE: 0.5,
            QAFlag.HIGH_INCIDENCE_ANGLE: 0.7,
            QAFlag.BORDER_NOISE: 0.4,
            QAFlag.SENSOR_DRIFT: 0.6,
            QAFlag.OUTLIER: 0.2,
            QAFlag.STALE: 0.8,
        }
        for flag in self.flags:
            if flag in penalty_flags:
                score *= penalty_flags[flag]
        
        self.scene_score = max(0.0, min(1.0, score))
        return self.scene_score


@dataclass
class ObservationPacket:
    """
    Universal ingestion schema. Every data source maps into this format
    before entering the assimilation engine.
    """
    # Identity
    packet_id: str = ""   # auto-generated hash
    source: ObservationSource = ObservationSource.SENTINEL2
    obs_type: ObservationType = ObservationType.RASTER
    
    # Temporal
    timestamp: datetime = field(default_factory=datetime.now)
    timestamp_end: Optional[datetime] = None  # for aggregation windows
    
    # Spatial
    geometry_type: str = "bbox"  # "bbox", "point", "polygon"
    bbox: Optional[Tuple[float, float, float, float]] = None  # (min_lng, min_lat, max_lng, max_lat)
    point: Optional[Tuple[float, float]] = None  # (lat, lng)
    polygon_wkt: Optional[str] = None
    
    # Data
    payload: Dict[str, Any] = field(default_factory=dict)
    # Raster:  {"ndvi": [...], "evi": [...], "bands": {...}}
    # Point:   {"temperature_2m": 25.3, "precipitation": 0.0}
    # Event:   {"event_type": "irrigation", "amount_mm": 20}
    # Image:   {"image_path": "...", "metadata": {...}}
    
    # Quality
    qa: QAMetadata = field(default_factory=QAMetadata)
    uncertainty: UncertaintyModel = field(default_factory=UncertaintyModel)
    provenance: Provenance = field(default_factory=Provenance)
    
    # Dynamic reliability (updated by cross-source validation)
    reliability_weight: float = 1.0  # 0–1, adjusted by validation_graph
    
    def __post_init__(self):
        if not self.packet_id:
            self.packet_id = self._generate_id()
    
    def _generate_id(self) -> str:
        """Deterministic hash from source + timestamp + geometry."""
        key = f"{self.source.value}:{self.timestamp.isoformat()}:{self.bbox or self.point}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]
    
    def effective_weight(self) -> float:
        """Combined quality × reliability weight for assimilation."""
        return self.qa.scene_score * self.reliability_weight
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "source": self.source.value,
            "obs_type": self.obs_type.value,
            "timestamp": self.timestamp.isoformat(),
            "timestamp_end": self.timestamp_end.isoformat() if self.timestamp_end else None,
            "geometry_type": self.geometry_type,
            "bbox": self.bbox,
            "point": self.point,
            "qa_score": self.qa.scene_score,
            "qa_flags": [f.value for f in self.qa.flags],
            "reliability": self.reliability_weight,
            "effective_weight": self.effective_weight(),
            "uncertainty": self.uncertainty.sigmas,
            "provenance_chain": self.provenance.processing_chain,
            "payload_keys": list(self.payload.keys()),
        }


# ============================================================================
# Observation Registry — stores packets per field per day
# ============================================================================

class ObservationRegistry:
    """
    In-memory registry of ObservationPackets for a field.
    Supports querying by source, time range, and quality threshold.
    
    In production this would back onto a database; here we keep it
    in-memory per pipeline run for simplicity.
    """
    
    def __init__(self):
        self._packets: List[ObservationPacket] = []
        self._by_source: Dict[str, List[ObservationPacket]] = {}
        self._by_day: Dict[str, List[ObservationPacket]] = {}
    
    def register(self, packet: ObservationPacket) -> str:
        """Register a packet and index it."""
        # Compute QA score if not already done
        packet.qa.compute_scene_score()
        
        self._packets.append(packet)
        
        # Index by source
        src = packet.source.value
        if src not in self._by_source:
            self._by_source[src] = []
        self._by_source[src].append(packet)
        
        # Index by day
        day_key = packet.timestamp.strftime("%Y-%m-%d")
        if day_key not in self._by_day:
            self._by_day[day_key] = []
        self._by_day[day_key].append(packet)
        
        return packet.packet_id
    
    def get_by_source(self, source: ObservationSource,
                      min_quality: float = 0.0) -> List[ObservationPacket]:
        """Retrieve packets from a specific source, optionally filtered by quality."""
        packets = self._by_source.get(source.value, [])
        if min_quality > 0:
            packets = [p for p in packets if p.qa.scene_score >= min_quality]
        return sorted(packets, key=lambda p: p.timestamp)
    
    def get_by_day(self, day: str) -> List[ObservationPacket]:
        """Retrieve all packets for a specific day (YYYY-MM-DD)."""
        return self._by_day.get(day, [])
    
    def get_by_range(self, start: datetime, end: datetime,
                     source: Optional[ObservationSource] = None) -> List[ObservationPacket]:
        """Retrieve packets within a time range, optionally filtered by source."""
        results = []
        for p in self._packets:
            if start <= p.timestamp <= end:
                if source is None or p.source == source:
                    results.append(p)
        return sorted(results, key=lambda p: p.timestamp)
    
    def get_latest(self, source: ObservationSource,
                   before: Optional[datetime] = None) -> Optional[ObservationPacket]:
        """Get the most recent packet from a source."""
        packets = self._by_source.get(source.value, [])
        if before:
            packets = [p for p in packets if p.timestamp <= before]
        if not packets:
            return None
        return max(packets, key=lambda p: p.timestamp)
    
    def summary(self) -> Dict[str, Any]:
        """Registry statistics."""
        return {
            "total_packets": len(self._packets),
            "sources": {src: len(pkts) for src, pkts in self._by_source.items()},
            "days_covered": len(self._by_day),
            "quality_distribution": {
                "high": sum(1 for p in self._packets if p.qa.scene_score >= 0.7),
                "medium": sum(1 for p in self._packets if 0.3 <= p.qa.scene_score < 0.7),
                "low": sum(1 for p in self._packets if p.qa.scene_score < 0.3),
            },
        }
    
    def __len__(self) -> int:
        return len(self._packets)
    
    def __repr__(self) -> str:
        return f"ObservationRegistry({len(self._packets)} packets, {len(self._by_day)} days)"
