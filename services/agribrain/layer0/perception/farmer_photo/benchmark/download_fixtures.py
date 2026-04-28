import os
import cv2
import numpy as np
import json
import hashlib

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "fixtures_manifest.json")

def generate_fixture(name: str, width: int, height: int, pattern: str) -> str:
    img = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Base field (closer up, detailed)
    img[:, :] = [30, 120, 40]  # BGR for leaf green
    noise = np.random.normal(0, 30, img.shape).astype(np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    # Blur
    if "blur" in pattern:
        img = cv2.GaussianBlur(img, (51, 51), 20)

    # Underexposure
    if "dark" in pattern:
        img = (img.astype(float) * 0.3).astype(np.uint8)

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
    print("Generating farmer photo fixtures...")
    fixtures = {
        "clean_photo": {"pattern": "clean", "w": 1200, "h": 1200},
        "blurry_photo": {"pattern": "blur", "w": 1200, "h": 1200},
        "dark_photo": {"pattern": "dark", "w": 1200, "h": 1200},
    }
    
    manifest = {"fixtures": {}}
    for name, config in fixtures.items():
        path = generate_fixture(name, config["w"], config["h"], config["pattern"])
        h = hash_file(path)
        manifest["fixtures"][name] = {
            "file": f"fixtures/{name}.jpg",
            "hash": h,
            "pattern": config["pattern"]
        }
        print(f"Generated {name}.jpg (hash: {h[:8]})")

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Manifest written to {MANIFEST_PATH}")

if __name__ == "__main__":
    main()
