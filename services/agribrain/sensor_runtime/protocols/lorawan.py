from typing import Dict, Any
import base64
import json

def parse_lorawan_uplink(payload: Dict[str, Any] | bytes) -> Dict[str, Any]:
    """Parse a standard LoRaWAN network server uplink JSON."""
    if isinstance(payload, bytes):
        payload = json.loads(payload.decode('utf-8'))
        
    fport = payload.get("fPort", 0)
    dev_eui = payload.get("devEUI", "")
    data = payload.get("data", "")
    
    # decode base64 if present
    raw_bytes = base64.b64decode(data) if data else b""
    
    return {
        "device_id": dev_eui,
        "fport": fport,
        "raw_bytes": raw_bytes.hex(),
        "metadata": payload
    }
