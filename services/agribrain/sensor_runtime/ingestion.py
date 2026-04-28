from datetime import datetime, timezone
from typing import Any, Dict, List
import uuid

from sensor_runtime.schemas import RawSensorMessage, NormalizedSensorReading
from sensor_runtime.device_identity import DeviceIdentity
from sensor_runtime.security import detect_replay, check_rate_limit, quarantine_payload
from sensor_runtime.decoder import decode_raw_message, DecoderResult

# Mock seen message tracking for V1
_SEEN_MESSAGES = set()


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
    if not message_id:
        message_id = str(uuid.uuid4())

    if not identity.is_authenticated():
        return []

    if not check_rate_limit(device_id, received_at):
        return []

    if detect_replay(message_id, _SEEN_MESSAGES):
        return []

    _SEEN_MESSAGES.add(message_id)

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
        provenance={"ingested_at": datetime.now(timezone.utc).isoformat()}
    )

    # Decode and normalize
    decoder_result = decode_raw_message(raw_msg)
    readings = decoder_result.readings

    # Inject transport-level signal metadata as canonical health readings
    if rssi is not None:
        readings.append(NormalizedSensorReading(
            reading_id=str(uuid.uuid4()),
            device_id=device_id,
            plot_id="unknown_plot",
            zone_id=None,
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
            reading_id=str(uuid.uuid4()),
            device_id=device_id,
            plot_id="unknown_plot",
            zone_id=None,
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

    return readings
