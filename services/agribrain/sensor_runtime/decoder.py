from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import uuid

from sensor_runtime.schemas import RawSensorMessage, NormalizedSensorReading
from sensor_runtime.normalization import apply_unit_conversion


# Canonical target units for each variable — the ONLY units allowed in NormalizedSensorReading
CANONICAL_UNIT_MAP = {
    "soil_moisture_vwc": "fraction",
    "soil_water_tension_kpa": "kpa",
    "soil_temperature_c": "c",
    "soil_ec_ds_m": "ds/m",
    "soil_ph": "ph",
    "air_temperature_c": "c",
    "relative_humidity_pct": "percent",
    "dew_point_c": "c",
    "vpd_kpa": "kpa",
    "rainfall_mm": "mm",
    "rain_rate_mm_h": "mm/h",
    "wind_speed_ms": "m/s",
    "wind_gust_ms": "m/s",
    "wind_direction_deg": "deg",
    "solar_radiation_w_m2": "w/m2",
    "par_umol_m2_s": "umol/m2/s",
    "leaf_wetness": "fraction",
    "leaf_wetness_duration_min": "min",
    "irrigation_flow_l_min": "l/min",
    "irrigation_volume_l": "l",
    "irrigation_pressure_bar": "bar",
    "pump_state": "bool",
    "tank_level_pct": "percent",
    "water_ec_ds_m": "ds/m",
    "water_ph": "ph",
    "water_temperature_c": "c",
    "battery_voltage_v": "v",
    "battery_pct": "percent",
    "signal_rssi_dbm": "dbm",
    "signal_snr_db": "db",
}

CANONICAL_VARIABLES = set(CANONICAL_UNIT_MAP.keys())


@dataclass
class DecoderResult:
    """Wraps decoded readings with diagnostics about ignored/unknown payload keys."""
    readings: List[NormalizedSensorReading] = field(default_factory=list)
    ignored_keys: List[str] = field(default_factory=list)
    decoder_flags: List[str] = field(default_factory=list)
    strict: bool = False


def normalize_to_canonical(variable: str, raw_value: float, raw_unit: str) -> tuple:
    """Convert a raw value+unit to canonical value+unit. Returns (canonical_value, canonical_unit, original_value, original_unit)."""
    canonical_unit = CANONICAL_UNIT_MAP.get(variable)
    if canonical_unit is None:
        raise ValueError(f"No canonical unit defined for variable: {variable}")

    if raw_unit.lower() == canonical_unit.lower():
        return raw_value, canonical_unit, raw_value, raw_unit

    canonical_value = apply_unit_conversion(raw_value, raw_unit, canonical_unit)
    return canonical_value, canonical_unit, raw_value, raw_unit


def _generic_decoder(raw: RawSensorMessage, strict: bool = False) -> DecoderResult:
    """Decoder for pre-normalized JSON payloads. Requires explicit unit metadata."""
    result = DecoderResult(strict=strict)

    if not isinstance(raw.payload, dict):
        return result

    # Support two payload formats:
    # Format A: {"readings": [{"variable": "...", "value": ..., "unit": "..."}]}
    # Format B: {"soil_moisture_vwc": 31.2, "_unit_metadata": {"soil_moisture_vwc": "percent"}}
    if "readings" in raw.payload and isinstance(raw.payload["readings"], list):
        for entry in raw.payload["readings"]:
            variable = entry.get("variable")
            value = entry.get("value")
            unit = entry.get("unit")
            if variable is None or value is None or unit is None:
                result.decoder_flags.append(f"INCOMPLETE_READING_ENTRY: {entry}")
                continue
            if variable not in CANONICAL_VARIABLES:
                if strict:
                    raise ValueError(f"Unknown payload key or non-canonical variable: {variable}")
                result.ignored_keys.append(variable)
                continue
            canon_val, canon_unit, orig_val, orig_unit = normalize_to_canonical(variable, float(value), unit)
            result.readings.append(NormalizedSensorReading(
                reading_id=str(uuid.uuid4()),
                device_id=raw.device_id,
                plot_id="unknown_plot",
                zone_id=None,
                timestamp=raw.received_at,
                received_at=raw.received_at,
                variable=variable,
                value=canon_val,
                unit=canon_unit,
                original_value=orig_val,
                original_unit=orig_unit,
                vendor="generic",
                protocol=raw.protocol,
                raw_payload_ref=raw.raw_payload_ref
            ))
        return result

    # Format B: flat dict with _unit_metadata
    unit_metadata = raw.payload.get("_unit_metadata", {})
    for variable, value in raw.payload.items():
        if variable in ("device_id", "timestamp", "_unit_metadata"):
            continue

        if variable not in CANONICAL_VARIABLES:
            if strict:
                raise ValueError(f"Unknown payload key or non-canonical variable: {variable}")
            result.ignored_keys.append(variable)
            continue

        raw_unit = unit_metadata.get(variable)
        if raw_unit is None:
            # No unit metadata → reject or quarantine
            if strict:
                raise ValueError(f"Missing unit metadata for variable: {variable}")
            result.decoder_flags.append(f"MISSING_UNIT_METADATA: {variable}")
            result.ignored_keys.append(variable)
            continue

        canon_val, canon_unit, orig_val, orig_unit = normalize_to_canonical(variable, float(value), raw_unit)
        result.readings.append(NormalizedSensorReading(
            reading_id=str(uuid.uuid4()),
            device_id=raw.device_id,
            plot_id="unknown_plot",
            zone_id=None,
            timestamp=raw.received_at,
            received_at=raw.received_at,
            variable=variable,
            value=canon_val,
            unit=canon_unit,
            original_value=orig_val,
            original_unit=orig_unit,
            vendor="generic",
            protocol=raw.protocol,
            raw_payload_ref=raw.raw_payload_ref
        ))

    return result


def decode_raw_message(raw_msg: RawSensorMessage, vendor: str = "generic", strict: bool = False) -> DecoderResult:
    """Route the raw message to the correct vendor adapter."""

    if vendor == "dragino":
        from sensor_runtime.vendors import dragino
        return dragino.decode(raw_msg, strict=strict)
    elif vendor == "milesight":
        from sensor_runtime.vendors import milesight
        return milesight.decode(raw_msg, strict=strict)
    elif vendor == "sensecap":
        from sensor_runtime.vendors import sensecap
        return sensecap.decode(raw_msg, strict=strict)
    elif vendor == "davis":
        from sensor_runtime.vendors import davis
        return davis.decode(raw_msg, strict=strict)

    return _generic_decoder(raw_msg, strict=strict)
