from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional


@dataclass
class SensorRepresentativeness:
    """The geographic extent over which this sensor's observation is considered valid."""
    observation_scope: Literal["point", "zone", "plot", "irrigation_block", "farm"]
    update_scope: Literal["none", "point", "zone", "plot"]
    confidence: float
    representative_zone_id: Optional[str] = None
    placement_flags: List[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class SensorQAResult:
    """Quality assurance assessment of an individual sensor reading or aggregate."""
    usable: bool
    quality_class: Literal["excellent", "good", "degraded", "unusable"]

    qa_score: float
    reading_reliability: float           # True data quality (calibration × health × representativeness × qa)
    state_update_reliability: float      # 0.0 if update_allowed=False, else reading_reliability
    update_allowed: bool                 # Whether this reading may mutate Kalman state
    reliability_weight: float            # Backward compat: Kalman adapter uses this (= state_update_reliability)
    sigma_multiplier: float

    range_score: float
    spike_score: float
    flatline_score: float
    dropout_score: float
    battery_score: float
    signal_score: float
    calibration_score: float
    placement_score: float
    representativeness_score: float

    flags: List[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class SensorAggregate:
    """A stable, low-frequency representation of high-frequency sensor readings."""
    device_id: str
    variable: str
    window_start: datetime
    window_end: datetime
    aggregate_type: Literal[
        "daily_mean", "daily_min", "daily_max", "daily_delta",
        "drydown_slope", "post_rain_response", "post_irrigation_response",
        "surface_root_gradient", "root_zone_weighted_moisture",
        "rain_event_total", "irrigation_event_total"
    ]
    value: float
    unit: str
    sample_count: int
    confidence: float


@dataclass
class SensorContextPackage:
    """The final layer0 evidence and observation output of the Sensor Engine."""
    plot_id: str
    window_start: datetime
    window_end: datetime

    devices: List[Any] = field(default_factory=list)     # List[SensorDeviceRegistration]
    readings: List[Any] = field(default_factory=list)    # List[NormalizedSensorReading]
    qa_results: List[SensorQAResult] = field(default_factory=list)
    aggregates: List[SensorAggregate] = field(default_factory=list)

    placement_context: Dict[str, Any] = field(default_factory=dict)
    observation_packets: List[Dict[str, Any]] = field(default_factory=list)
    kalman_observations: List[Any] = field(default_factory=list)
    process_forcing_events: List[Any] = field(default_factory=list)
    validation_events: List[Dict[str, Any]] = field(default_factory=list)

    diagnostics: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)
