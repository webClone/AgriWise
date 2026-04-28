from typing import List

from sensor_runtime.schemas import RawSensorMessage, NormalizedSensorReading
from sensor_runtime.decoder import decode_raw_message

def replay_raw_message(msg: RawSensorMessage) -> List[NormalizedSensorReading]:
    """
    Replays a raw message through the current decoder and normalizer.
    Preserves original received_at, updates normalization_version.
    """
    readings = decode_raw_message(msg)
    # The decoder should already preserve received_at since it comes from the raw_msg.
    # We could bump normalization_version here if desired.
    for r in readings:
        r.normalization_version = "1.1_replay"
        
    return readings
