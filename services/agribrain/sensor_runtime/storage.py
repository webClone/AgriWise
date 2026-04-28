from typing import List

from sensor_runtime.schemas import RawSensorMessage, NormalizedSensorReading

# Mock storage in V1
_RAW_STORAGE = {}
_NORMALIZED_STORAGE = []

def store_raw_message(msg: RawSensorMessage) -> None:
    """Store immutable raw payload."""
    if msg.message_id in _RAW_STORAGE:
        raise ValueError("Raw message is immutable and cannot be overwritten.")
    _RAW_STORAGE[msg.message_id] = msg
    
def store_normalized_reading(reading: NormalizedSensorReading) -> None:
    """Store versioned normalized reading."""
    _NORMALIZED_STORAGE.append(reading)

def get_raw_message(message_id: str) -> RawSensorMessage | None:
    return _RAW_STORAGE.get(message_id)
