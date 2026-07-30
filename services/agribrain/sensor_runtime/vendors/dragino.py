from typing import List, Dict, Any
import uuid
from sensor_runtime.schemas import RawSensorMessage, NormalizedSensorReading
from sensor_runtime.decoder import DecoderResult, normalize_to_canonical


def decode(raw: RawSensorMessage, strict: bool = False) -> DecoderResult:
    result = DecoderResult(strict=strict)
    if not isinstance(raw.payload, dict):
        return result

    # Dragino LHT65/LSE01 payload mapping: raw_key → (canonical_variable, raw_unit, transform)
    mapping = {
        "BatV": ("battery_pct", "percent", lambda x: max(0, min(100, (x - 2.5) / (3.6 - 2.5) * 100))),
        "TempC_DS": ("soil_temperature_c", "c", lambda x: x),
        "water_SOIL": ("soil_moisture_vwc", "percent", lambda x: x),
    }

    for key, val in raw.payload.items():
        if key in mapping:
            var_name, raw_unit, transform = mapping[key]
            raw_value = transform(val)
            canon_val, canon_unit, orig_val, orig_unit = normalize_to_canonical(var_name, raw_value, raw_unit)
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
                vendor="dragino",
                protocol=raw.protocol,
                raw_payload_ref=raw.raw_payload_ref
            ))
        else:
            result.ignored_keys.append(key)

    if result.ignored_keys and strict:
        raise ValueError(f"Dragino decoder: unknown payload keys: {result.ignored_keys}")

    return result
