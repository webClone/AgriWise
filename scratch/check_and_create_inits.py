"""Check and create missing __init__.py package markers."""
import os

ROOT = r"c:\Users\E-C\Desktop\agriwise"

DIRS = [
    "services",
    "services/agribrain",
    "services/agribrain/layer0",
    "services/agribrain/layer0/perception",
    "services/agribrain/layer0/perception/common",
    "services/agribrain/layer0/perception/satellite_rgb",
    "services/agribrain/layer0/perception/satellite_rgb/benchmark",
    "services/agribrain/layer0/perception/satellite_rgb/tests",
    "services/agribrain/layer0/perception/farmer_photo",
    "services/agribrain/layer0/perception/farmer_photo/benchmark",
    "services/agribrain/layer0/perception/farmer_photo/tests",
    "services/agribrain/layer0/perception/drone_rgb",
    "services/agribrain/layer0/perception/drone_rgb/benchmark",
    "services/agribrain/layer0/perception/ip_camera",
    "services/agribrain/layer0/perception/ip_camera/benchmark",
    "services/agribrain/layer0/tests",
    "services/agribrain/ip_camera_runtime",
    "services/agribrain/drone_control",
    "services/agribrain/drone_mission",
    "services/agribrain/drone_photogrammetry",
    "services/agribrain/layer0/perception_models",
]

for d in DIRS:
    full = os.path.join(ROOT, d)
    if not os.path.isdir(full):
        print(f"DIR MISSING: {d}")
        continue
    init_path = os.path.join(full, "__init__.py")
    if os.path.exists(init_path):
        print(f"EXISTS:  {d}/__init__.py")
    else:
        with open(init_path, "w") as f:
            pass
        print(f"CREATED: {d}/__init__.py")
