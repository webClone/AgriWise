from typing import List, Dict, Any

from sensor_runtime.registry import SensorDeviceRegistration
from layer0.sensors.schemas import SensorQAResult

def build_diagnostics(
    devices: List[SensorDeviceRegistration],
    qa_results: List[SensorQAResult],
    validation_events: List[Dict[str, Any]]
) -> Dict[str, Any]:
    
    active_devices = len([d for d in devices if d.status == "active"])
    
    # We group QA by device (simplified: just counting overall usable vs unusable readings for now)
    # A more complex system would map QA to devices strictly.
    usable_count = len([q for q in qa_results if q.usable])
    unusable_count = len([q for q in qa_results if not q.usable])
    
    flags = set()
    for qa in qa_results:
        flags.update(qa.flags)
        
    for val in validation_events:
        flags.add(val["type"])
        
    return {
        "sensor_summary": {
            "active_devices": active_devices,
            "trusted_readings": usable_count,
            "degraded_or_unusable_readings": unusable_count,
            "offline_devices": len([d for d in devices if d.status in ["offline", "lost"]])
        },
        "flags": list(flags),
        "cross_validation": {
            "events_count": len(validation_events)
        }
    }
