from typing import Dict, Any
import json

def parse_mqtt_envelope(topic: str, payload: bytes) -> Dict[str, Any]:
    """Parse standard MQTT topic routing and payload."""
    try:
        data = json.loads(payload.decode('utf-8'))
    except json.JSONDecodeError:
        data = {"raw_payload": payload.hex()}
        
    parts = topic.split('/')
    device_id = parts[-1] if parts else "unknown"
    
    return {
        "device_id": device_id,
        "topic": topic,
        "payload": data
    }
