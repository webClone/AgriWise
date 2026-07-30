from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Optional, Tuple

CanonicalVariable = Literal[
    "soil_moisture_vwc",
    "soil_water_tension_kpa",
    "soil_temperature_c",
    "soil_ec_ds_m",
    "soil_ph",
    "air_temperature_c",
    "relative_humidity_pct",
    "dew_point_c",
    "vpd_kpa",
    "rainfall_mm",
    "rain_rate_mm_h",
    "wind_speed_ms",
    "wind_gust_ms",
    "wind_direction_deg",
    "solar_radiation_w_m2",
    "par_umol_m2_s",
    "leaf_wetness",
    "leaf_wetness_duration_min",
    "irrigation_flow_l_min",
    "irrigation_volume_l",
    "irrigation_pressure_bar",
    "pump_state",
    "tank_level_pct",
    "water_ec_ds_m",
    "water_ph",
    "water_temperature_c",
    "battery_voltage_v",
    "battery_pct",
    "signal_rssi_dbm",
    "signal_snr_db",
]


@dataclass
class RawSensorMessage:
    """Immutable raw payload exactly as received from a device or protocol."""
    message_id: str
    protocol: str
    received_at: datetime
    device_id: str
    payload: dict | bytes | str

    gateway_id: Optional[str] = None
    rssi: Optional[float] = None
    snr: Optional[float] = None

    raw_payload_ref: str = ""
    provenance: dict = None


@dataclass
class NormalizedSensorReading:
    """A strictly normalized, atomic reading mapped to a CanonicalVariable."""
    reading_id: str
    device_id: str
    plot_id: str
    zone_id: Optional[str]

    timestamp: datetime
    received_at: datetime

    variable: CanonicalVariable
    value: float | int | str | bool | None
    unit: str

    vendor: str
    protocol: str

    depth_cm: Optional[float] = None
    depth_interval_cm: Optional[Tuple[float, float]] = None

    latitude: Optional[float] = None
    longitude: Optional[float] = None

    model: Optional[str] = None

    raw_payload_ref: str = ""
    normalization_version: str = "1.0"
    original_unit: Optional[str] = None
    original_value: Any = None
    
    # Rainfall specific tracking
    rainfall_mode: Optional[Literal["incremental", "cumulative", "event_total"]] = None
