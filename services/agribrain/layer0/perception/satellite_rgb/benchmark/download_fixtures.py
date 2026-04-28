import os
import cv2
import numpy as np
import json
import hashlib

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "fixtures_manifest.json")

def generate_fixture(name: str, width: int, height: int, pattern: str) -> str:
    img = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Base field
    if "healthy" in pattern:
        img[:, :] = [30, 100, 20]  # BGR for dark green
        noise = np.random.normal(0, 15, img.shape).astype(np.int16)
        img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    elif "sparse" in pattern:
        img[:, :] = [40, 80, 100]  # BGR for brownish green
        noise = np.random.normal(0, 20, img.shape).astype(np.int16)
        img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    else:
        img[:, :] = [40, 90, 30]

    # Add clouds
    if "cloud" in pattern:
        for _ in range(5):
            cx, cy = np.random.randint(0, width), np.random.randint(0, height)
            cv2.circle(img, (cx, cy), 30, (240, 240, 240), -1)
            # blur to make it look like a cloud
            img = cv2.GaussianBlur(img, (21, 21), 0)

    # Add haze
    if "haze" in pattern:
        haze = np.full((height, width, 3), 200, dtype=np.uint8)
        img = cv2.addWeighted(img, 0.6, haze, 0.4, 0)

    # Add boundary road (contamination)
    if "boundary" in pattern:
        img[:, :30] = [120, 120, 120]  # Gray road on the left

    os.makedirs(FIXTURES_DIR, exist_ok=True)
    out_path = os.path.join(FIXTURES_DIR, f"{name}.jpg")
    cv2.imwrite(out_path, img)
    return out_path

def hash_file(path: str) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        hasher.update(f.read())
    return hasher.hexdigest()

def main():
    print("Generating satellite fixtures...")
    fixtures = {
        "healthy_plot": {"pattern": "healthy", "w": 200, "h": 200},
        "cloud_obscured": {"pattern": "healthy_cloud", "w": 200, "h": 200},
        "haze_plot": {"pattern": "healthy_haze", "w": 200, "h": 200},
        "sparse_plot": {"pattern": "sparse", "w": 200, "h": 200},
        "boundary_contaminated": {"pattern": "healthy_boundary", "w": 200, "h": 200},
    }
    
    manifest = {"fixtures": {}}
    for name, config in fixtures.items():
        path = generate_fixture(name, config["w"], config["h"], config["pattern"])
        h = hash_file(path)
        manifest["fixtures"][name] = {
            "file": f"fixtures/{name}.jpg",
            "hash": h,
            "pattern": config["pattern"],
            "resolution_m": 10.0
        }
        print(f"Generated {name}.jpg (hash: {h[:8]})")

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Manifest written to {MANIFEST_PATH}")

if __name__ == "__main__":
    main()
