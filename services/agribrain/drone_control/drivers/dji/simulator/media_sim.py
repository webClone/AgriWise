"""
DJI Cloud Gateway Simulator — Media Manifest.

Generates a fake media manifest after mission completion,
simulating what a DJI gateway reports via the Cloud API.
"""

from __future__ import annotations
from typing import Dict, Any, List
import datetime

from .device_state import DeviceStateMachine


def generate_media_manifest(
    device: DeviceStateMachine,
    flight_id: str = "",
) -> Dict[str, Any]:
    """Generate a fake media manifest from a completed/failed device.
    
    Returns a DJI Cloud API media manifest structure.
    """
    if device.failure.no_media:
        return {
            "flight_id": flight_id,
            "files": [],
            "total_count": 0,
            "total_size_bytes": 0,
            "complete": False,
        }
    
    files = []
    for i in range(device.vehicle.capture_count):
        files.append({
            "file_name": f"DJI_{flight_id}_{i:04d}.JPG",
            "file_path": f"/DCIM/100MEDIA/DJI_{flight_id}_{i:04d}.JPG",
            "file_size": 8_500_000 + (i * 1000),          # ~8.5MB per image
            "file_type": "photo",
            "capture_index": i,
            "latitude": 31.850 + i * 0.00002,
            "longitude": 34.720 + i * 0.00005,
            "altitude": 50.0,
            "heading": 0.0,
            "timestamp": int(datetime.datetime.now().timestamp() * 1000) + i * 3000,
        })
    
    return {
        "flight_id": flight_id,
        "files": files,
        "total_count": len(files),
        "total_size_bytes": sum(f["file_size"] for f in files),
        "complete": True,
    }
