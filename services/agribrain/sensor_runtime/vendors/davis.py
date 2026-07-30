from typing import List, Dict, Any
import uuid
from sensor_runtime.schemas import RawSensorMessage, NormalizedSensorReading
from sensor_runtime.decoder import DecoderResult, normalize_to_canonical


def decode(raw: RawSensorMessage, strict: bool = False) -> DecoderResult:
    result = DecoderResult(strict=strict)
    if not isinstance(raw.payload, dict):
        return result

    # Davis Vantage Pro2 / WeatherLink payload mapping
    # Davis outputs imperial units; we convert to SI canonical
    mapping = {
        "temp_in": ("air_temperature_c", "f"),
        "hum_in": ("relative_humidity_pct", "percent"),
        "rain_day_in": ("rainfall_mm", "in"),
        "wind_mph": ("wind_speed_ms", "mph"),
        "wind_dir": ("wind_direction_deg", "deg"),
    }

    for key, val in raw.payload.items():
        if key in mapping:
            var_name, raw_unit = mapping[key]
            canon_val, canon_unit, orig_val, orig_unit = normalize_to_canonical(var_name, float(val), raw_unit)
            result.readings.append(NormalizedSensorReading(
                reading_id=str(uuid.uuid4()),
                device_id=raw.device_id,
                plot_id="unknown_plot",
                zone_id=None,
                timestamp=raw.received_at,
                received_at=raw.received_at,
                variable=var_name,
                value=canon_val,
                unit=canon_unit,
                original_value=orig_val,
                original_unit=orig_unit,
                vendor="davis",
                protocol=raw.protocol,
                raw_payload_ref=raw.raw_payload_ref
            ))
        else:
            result.ignored_keys.append(key)

    if result.ignored_keys and strict:
        raise ValueError(f"Davis decoder: unknown payload keys: {result.ignored_keys}")

    return result
