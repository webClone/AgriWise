from datetime import datetime, timezone
import json
from sensor_runtime.ingestion import ingest_sensor_payload
from sensor_runtime.device_identity import DeviceIdentity
from sensor_runtime.security import verify_webhook_signature

def handle_http_webhook(request_body: str, signature: str, secret: str):
    """Entry point for HTTP webhooks (e.g. from a vendor cloud)."""
    if not verify_webhook_signature(request_body.encode("utf-8"), signature, secret):
        raise ValueError("Invalid webhook signature")
    
    payload = json.loads(request_body)
    device_id = payload.get("device_id")
    identity = DeviceIdentity(device_id=device_id)
    
    return ingest_sensor_payload(
        protocol="http_webhook",
        device_id=device_id,
        payload=payload,
        received_at=datetime.now(timezone.utc),
        identity=identity
    )

def handle_mqtt_message(topic: str, payload: bytes):
    """Entry point for direct MQTT ingestion."""
    # Mock extracting device_id from topic e.g. "sensors/device123/uplink"
    device_id = topic.split("/")[1] if len(topic.split("/")) > 1 else "unknown"
    identity = DeviceIdentity(device_id=device_id)
    
    return ingest_sensor_payload(
        protocol="mqtt",
        device_id=device_id,
        payload=payload,
        received_at=datetime.now(timezone.utc),
        identity=identity
    )

def handle_lorawan_uplink(deveui: str, payload_hex: str, fport: int, rssi: float, snr: float, gateway_id: str):
    """Entry point for LoRaWAN Network Server integrations (e.g. TTN, ChirpStack)."""
    identity = DeviceIdentity(device_id=deveui, network_id=deveui)
    
    return ingest_sensor_payload(
        protocol="lorawan",
        device_id=deveui,
        payload={"hex": payload_hex, "fport": fport},
        received_at=datetime.now(timezone.utc),
        identity=identity,
        rssi=rssi,
        snr=snr,
        gateway_id=gateway_id
    )

def handle_cellular_json(device_id: str, payload: dict):
    """Entry point for direct cellular TCP/UDP JSON connections."""
    identity = DeviceIdentity(device_id=device_id)
    return ingest_sensor_payload(
        protocol="cellular_json",
        device_id=device_id,
        payload=payload,
        received_at=datetime.now(timezone.utc),
        identity=identity
    )

def handle_modbus_reading(device_id: str, registers: list):
    """Entry point for Modbus gateway integrations."""
    identity = DeviceIdentity(device_id=device_id)
    return ingest_sensor_payload(
        protocol="modbus",
        device_id=device_id,
        payload={"registers": registers},
        received_at=datetime.now(timezone.utc),
        identity=identity
    )

def handle_csv_import(device_id: str, csv_row: dict, timestamp: datetime):
    """Entry point for historical CSV uploads."""
    identity = DeviceIdentity(device_id=device_id)
    return ingest_sensor_payload(
        protocol="csv_import",
        device_id=device_id,
        payload=csv_row,
        received_at=timestamp, # trust CSV timestamp
        identity=identity
    )
