#!/usr/bin/env python3
"""
V59 — Full-Plot Drone Coverage & Tiled Mosaic Validation Pack Asset Preparer

Compiles persistent, non-transient high-fidelity tiled media assets under:
services/agribrain/artifacts/v59_field_data/
utilizing LZW compression to keep 5000x5000 files lightweight on disk.
"""

from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
import numpy as np
import rasterio
from rasterio.transform import from_origin


def prepare_v59_assets() -> None:
    print("======================================================================")
    print(" PREPARING V59 — TILED DRONE COVERS & PERSISTENT FIELD PACK ASSETS")
    print("======================================================================")

    # Setup directories
    workspace_root = Path(__file__).parent.parent.parent.parent.resolve()
    agribrain_root = workspace_root / "services" / "agribrain"
    field_data_dir = agribrain_root / "artifacts" / "v59_field_data"
    field_data_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Creating persistent field pack directory: {field_data_dir}")

    # Paths to source fixtures
    ip_camera_fixture = agribrain_root / "layer0" / "perception" / "ip_camera" / "benchmark" / "fixtures" / "healthy_canopy.jpg"
    farmer_photo_fixture = agribrain_root / "layer0" / "perception" / "farmer_photo" / "benchmark" / "fixtures" / "clean_photo.jpg"

    # Targets in field pack
    camera_frame_path = field_data_dir / "camera_frame.bin"
    camera_meta_path = field_data_dir / "camera_meta.json"
    photo_path = field_data_dir / "farmer_photo.jpg"
    photo_exif_path = field_data_dir / "farmer_exif.json"
    iot_path = field_data_dir / "iot_sensors.csv"
    input_path = field_data_dir / "farmer_inputs.json"

    # 1. Generate 4 adjacent 5000x5000 tiles with 3cm GSD under EPSG:32632 (UTM Zone 32N)
    # Total extent per tile = 150m x 150m = 22,500 m2
    # Combined extent = 300m x 300m = 90,000 m2 (9.0 ha)
    utm_x = 300000.0
    utm_y = 3800000.0
    
    tiles_cfg = [
        {"name": "drone_tile_0.tif", "x": utm_x,       "y": utm_y},
        {"name": "drone_tile_1.tif", "x": utm_x + 150, "y": utm_y},
        {"name": "drone_tile_2.tif", "x": utm_x,       "y": utm_y - 150},
        {"name": "drone_tile_3.tif", "x": utm_x + 150, "y": utm_y - 150}
    ]

    for tile in tiles_cfg:
        tile_path = field_data_dir / tile["name"]
        print(f"Generating adjacent tile {tile['name']} at UTM origin ({tile['x']}, {tile['y']})...")
        
        transform = from_origin(tile["x"], tile["y"], 0.03, 0.03)
        # Create a compressed single-band float32 raster
        # LZW compression compresses all ones down to practically 0 bytes
        data = np.ones((5000, 5000), dtype=np.float32)
        # Add some mock variations
        data[2000:3000, 2000:3000] = 0.82
        
        with rasterio.open(
            tile_path, "w", driver="GTiff", height=5000, width=5000, count=1,
            dtype="float32", crs="EPSG:32632", transform=transform, compress="lzw"
        ) as dst:
            dst.write(data, 1)
        print(f" -> Saved: {tile_path} ({tile_path.stat().st_size / 1024:.2f} KB)")

    # 2. Compile IP Camera assets
    if ip_camera_fixture.exists():
        print(f"Copying real IP camera frame bytes from {ip_camera_fixture.name}...")
        camera_frame_path.write_bytes(ip_camera_fixture.read_bytes())
    else:
        camera_frame_path.write_bytes(b"\xFF\xD8\xFF\xE0RealIPCameraMockBytes" * 20)
        
    camera_meta_path.write_text(json.dumps({
        "crop_stage": "peak_growth",
        "confidence": 0.96,
        "status": "healthy"
    }, indent=2), encoding="utf-8")

    # 3. Compile Farmer Photo assets
    if farmer_photo_fixture.exists():
        print(f"Copying real farmer photo bytes from {farmer_photo_fixture.name}...")
        photo_path.write_bytes(farmer_photo_fixture.read_bytes())
    else:
        photo_path.write_bytes(b"\xFF\xD8\xFF\xE1RealFarmerPhotoMockBytes" * 50)
        
    photo_exif_path.write_text(json.dumps({
        "gps": {"latitude": 34.2, "longitude": 6.1},
        "observation": "healthy_crop",
        "confidence": 0.95
    }, indent=2), encoding="utf-8")

    # 4. Generate persistent daily IoT soil moisture CSV logs
    print("Writing persistent daily IoT sensor time-series telemetry...")
    base_time = datetime.now(timezone.utc) - timedelta(days=30)
    with iot_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "sensor_id", "moisture_level", "temperature", "confidence"])
        for day in range(31):
            ts = base_time + timedelta(days=day)
            writer.writerow([ts.isoformat(), "iot_s1", "optimal_moisture", 24.2 + (day % 3) * 0.5, 0.99])

    # 5. Generate historical Farmer Input event calendar JSON
    print("Writing persistent Farmer Inputs JSON calendar log...")
    with input_path.open("w", encoding="utf-8") as f:
        json.dump([
            {
                "source_id": "input_s1",
                "event_type": "planting",
                "confidence": 1.0,
                "timestamp": (base_time + timedelta(days=1)).isoformat()
            },
            {
                "source_id": "input_s1",
                "event_type": "irrigation",
                "confidence": 1.0,
                "timestamp": (base_time + timedelta(days=15)).isoformat()
            },
            {
                "source_id": "input_s1",
                "event_type": "fertilizer",
                "confidence": 1.0,
                "timestamp": (base_time + timedelta(days=20)).isoformat()
            }
        ], f, indent=2)

    print("\nSUCCESS: All V59 persistent tiled assets compiled successfully on disk.")


if __name__ == "__main__":
    prepare_v59_assets()
