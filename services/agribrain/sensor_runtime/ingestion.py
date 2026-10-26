import logging
import math
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# F37: Ensure namespace parity between sensor_runtime and services.agribrain.sensor_runtime
for _sub in ("schemas", "device_identity", "security", "decoder", "registry", "calibration", "storage", "ingestion"):
    _full = f"services.agribrain.sensor_runtime.{_sub}"
    _short = f"sensor_runtime.{_sub}"
    if _full in sys.modules and _short not in sys.modules:
        sys.modules[_short] = sys.modules[_full]
    elif _short in sys.modules and _full not in sys.modules:
        sys.modules[_full] = sys.modules[_short]

from sensor_runtime.schemas import RawSensorMessage, NormalizedSensorReading
from sensor_runtime.device_identity import DeviceIdentity
from sensor_runtime.security import detect_replay, check_rate_limit, quarantine_payload, is_production, save_nonce, release_nonce
from sensor_runtime.decoder import decode_raw_message, DecoderResult
from sensor_runtime.registry import get_device_registration
from sensor_runtime.calibration import get_calibration_profile
from sensor_runtime.storage import store_raw_message, store_normalized_reading

# Deduplication state tracking for ingested message IDs
_SEEN_MESSAGES = set()


VARIABLE_FAMILIES = {
    "soil_moisture": {"soil_moisture", "vwc", "volumetric_water_content", "soil_moisture_vwc"},
    "soil_temperature": {"soil_temperature", "soil_temp", "soil_temperature_c"},
    "air_temperature": {"air_temperature", "temp_air", "temperature", "air_temperature_c"},
    "humidity": {"humidity", "relative_humidity", "rh", "relative_humidity_pct"},
    "rain": {"rain", "rain_mm", "precipitation_mm", "rainfall_mm"},
    "ec": {"ec", "electrical_conductivity", "soil_ec_ds_m"},
    "ph": {"ph", "soil_ph"},
}


def are_variables_compatible(sensor_var: str, cal_var: str) -> bool:
    if sensor_var == cal_var:
        return True
    for family, aliases in VARIABLE_FAMILIES.items():
        if sensor_var in aliases and cal_var in aliases:
            return True
    return False


def is_registered_variable_allowed(reading_var: str, registered_vars: List[str]) -> bool:
    return any(
        are_variables_compatible(reading_var, reg_var)
        for reg_var in registered_vars
    )


def ensure_tz(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def ingest_sensor_payload(
    protocol: str,
    device_id: str,
    payload: dict | bytes | str,
    received_at: datetime,
    identity: DeviceIdentity,
    message_id: str = None,
    gateway_id: str = None,
    rssi: float = None,
    snr: float = None,
) -> List[NormalizedSensorReading]:
    """
    Primary entrypoint for all incoming sensor data.
    """
    if is_production():
        # Enforce that env registry and calibration paths are configured
        if not os.getenv("AGRIWISE_SENSOR_REGISTRY_PATH"):
            raise ValueError("sensor_registry_unavailable")
        if not os.getenv("AGRIWISE_SENSOR_CALIBRATION_PATH"):
            raise ValueError("sensor_calibration_unavailable")

    if not message_id:
        message_id = str(uuid.uuid4())

    # 1. Verify signature
    if not identity.is_authenticated():
        return []

    # 2. Check rate limit
    if not check_rate_limit(device_id, received_at):
        return []

    # 3. Check replay
    if detect_replay(message_id, _SEEN_MESSAGES):
        return []

    nonce_released = False
    try:
        # 4. Validate registry/calibration
        reg = get_device_registration(device_id)
        if not reg or not reg.plot_id:
            if not nonce_released:
                release_nonce(message_id, _SEEN_MESSAGES)
                nonce_released = True
            return []

        # Device Status Normalization & Validation
        status = str(reg.status or "").strip().lower()
        if not status:
            status = "missing"
        if status != "active":
            if not nonce_released:
                release_nonce(message_id, _SEEN_MESSAGES)
                nonce_released = True
            ex = ValueError(f"device_inactive: {status}")
            ex.device_status = status
            raise ex

        # Temporary raw message construction to pass to decoder
        temp_msg = RawSensorMessage(
            message_id=message_id,
            protocol=protocol,
            received_at=received_at,
            device_id=device_id,
            payload=payload,
            gateway_id=gateway_id,
            rssi=rssi,
            snr=snr,
            raw_payload_ref=f"s3://raw-sensors/{device_id}/{message_id}",
            provenance={"ingested_at": datetime.now(timezone.utc).isoformat(), "volatile": False}
        )
        
        decoder_result = decode_raw_message(temp_msg)
        readings = decoder_result.readings

        # Identify agronomic readings
        agronomic_readings = []
        for r in readings:
            if r.variable in {
                "battery_voltage",
                "battery_voltage_v",
                "battery_pct",
                "signal_strength",
                "rssi",
                "firmware_version",
                "device_temperature_internal",
                "signal_rssi_dbm",
                "signal_snr_db",
            }:
                continue
            agronomic_readings.append(r)

        # For every decoded agronomic reading, find a compatible calibration profile
        for r in agronomic_readings:
            reg_vars = reg.variables if reg else []
            if not is_registered_variable_allowed(r.variable, reg_vars):
                raise ValueError("sensor_variable_not_registered")

            cal = get_calibration_profile(device_id, r.variable)
            if not cal:
                raise ValueError("sensor_calibration_unavailable")
            if cal.calibration_type == "uncalibrated":
                raise ValueError("sensor_uncalibrated")
            if not are_variables_compatible(r.variable, cal.variable):
                raise ValueError("calibration_variable_mismatch")
                
            # Timezone-safe calibration expiry validation
            if cal.valid_until is None:
                if is_production() or os.getenv("AGRIWISE_STRICT_SECURITY") == "true":
                    raise ValueError("calibration_expiry_missing")
            else:
                if ensure_tz(cal.valid_until) < ensure_tz(received_at):
                    raise ValueError("calibration_expired")

            # Calibration quality validation
            q = cal.calibration_quality
            if q is None:
                raise ValueError("calibration_quality_missing")
            if not isinstance(q, (int, float)) or isinstance(q, bool) or not math.isfinite(q):
                raise ValueError("calibration_quality_invalid")
            if q < 0.5:
                raise ValueError("calibration_quality_too_low")

        # Detect if payload is volatile
        is_volatile = False
        if isinstance(payload, dict):
            if payload.get("provenance", {}).get("volatile") is True:
                is_volatile = True
            elif payload.get("volatile") is True:
                is_volatile = True

        raw_msg = RawSensorMessage(
            message_id=message_id,
            protocol=protocol,
            received_at=received_at,
            device_id=device_id,
            payload=payload,
            gateway_id=gateway_id,
            rssi=rssi,
            snr=snr,
            raw_payload_ref=f"s3://raw-sensors/{device_id}/{message_id}",
            provenance={"ingested_at": datetime.now(timezone.utc).isoformat(), "volatile": is_volatile}
        )

        if not is_volatile:
            store_raw_message(raw_msg)
    except Exception:
        if not nonce_released:
            release_nonce(message_id, _SEEN_MESSAGES)
            nonce_released = True
        raise

    # Override plot_id, zone_id, and prefix reading_id
    for r in readings:
        r.plot_id = reg.plot_id
        r.zone_id = reg.zone_id
        if not r.reading_id.startswith("e_sensor_"):
            r.reading_id = f"e_sensor_{r.reading_id}"

    # Inject transport-level signal metadata as canonical health readings
    if rssi is not None:
        readings.append(NormalizedSensorReading(
            reading_id=f"e_sensor_{uuid.uuid4()}",
            device_id=device_id,
            plot_id=reg.plot_id,
            zone_id=reg.zone_id,
            timestamp=received_at,
            received_at=received_at,
            variable="signal_rssi_dbm",
            value=float(rssi),
            unit="dbm",
            original_value=float(rssi),
            original_unit="dbm",
            vendor="transport",
            protocol=protocol,
            raw_payload_ref=raw_msg.raw_payload_ref
        ))
    if snr is not None:
        readings.append(NormalizedSensorReading(
            reading_id=f"e_sensor_{uuid.uuid4()}",
            device_id=device_id,
            plot_id=reg.plot_id,
            zone_id=reg.zone_id,
            timestamp=received_at,
            received_at=received_at,
            variable="signal_snr_db",
            value=float(snr),
            unit="db",
            original_value=float(snr),
            original_unit="db",
            vendor="transport",
            protocol=protocol,
            raw_payload_ref=raw_msg.raw_payload_ref
        ))

    if not is_volatile:
        for r in readings:
            try:
                store_normalized_reading(r)
            except Exception as store_err:
                logger.error("Failed to store normalized reading %s: %s", r.reading_id, store_err)

    return readings
