import os
import json
import cv2
import numpy as np

def generate_drone_fixture(path, pattern, w, h):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    
    if "clean" in pattern:
        # High resolution clean field map (green rows on brown soil)
        img[:, :] = (30, 60, 100) # Brown soil
        noise = np.random.normal(0, 30, (h, w, 3)).astype(np.int16)
        img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
            
        for i in range(0, w, 120):
            cv2.line(img, (i, 0), (i, h), (40, 150, 40), 40) # Green rows
            
    elif "blur" in pattern:
        # Fast drone motion blur
        img[:, :] = (30, 60, 100)
        noise = np.random.randint(-20, 20, (h, w, 3), dtype=np.int16)
        img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        
        for i in range(0, w, 120):
            cv2.line(img, (i, 0), (i, h), (40, 150, 40), 40)
        # Apply heavy vertical motion blur to simulate bad flight speed
        kernel = np.zeros((50, 50))
        kernel[:, int((50-1)/2)] = np.ones(50)
        kernel /= 50
        img = cv2.filter2D(img, -1, kernel)
        
    elif "stitched_poorly" in pattern:
        # Simulate stitching artifacts: black gaps and discontinuities
        img[:, :] = (30, 60, 100)
        noise = np.random.normal(0, 30, (h, w, 3)).astype(np.int16)
        img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
            
        for i in range(0, w, 120):
            cv2.line(img, (i, 0), (i, int(h/2)), (40, 150, 40), 40)
            # Offset rows in second half
            cv2.line(img, (i + 40, int(h/2)), (i + 40, h), (40, 150, 40), 40)
        
        # Black gap representing missing coverage
        img[int(h/2)-20:int(h/2)+20, :] = 0
        
    elif "dark" in pattern:
        # Underexposed
        img[:, :] = (10, 20, 30)
        noise = np.random.normal(0, 15, (h, w, 3)).astype(np.int16)
        img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
            
        for i in range(0, w, 120):
            cv2.line(img, (i, 0), (i, h), (15, 40, 15), 40)
    
    cv2.imwrite(path, img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    # Simple hash of file contents
    with open(path, "rb") as f:
        import hashlib
        hsh = hashlib.sha256(f.read()).hexdigest()
    return hsh

def main():
    print("Generating drone RGB fixtures...")
    fixtures = {
        "clean_ortho": {"pattern": "clean", "w": 2000, "h": 2000},
        "blurry_ortho": {"pattern": "blur", "w": 2000, "h": 2000},
        "poor_stitch": {"pattern": "stitched_poorly", "w": 2000, "h": 2000},
        "dark_ortho": {"pattern": "dark", "w": 2000, "h": 2000},
    }
    
    manifest = {"fixtures": {}}
    out_dir = os.path.join(os.path.dirname(__file__), "fixtures")
    os.makedirs(out_dir, exist_ok=True)
    
    for name, spec in fixtures.items():
        path = os.path.join(out_dir, f"{name}.jpg")
        hsh = generate_drone_fixture(path, spec["pattern"], spec["w"], spec["h"])
        manifest["fixtures"][name] = {
            "file": f"fixtures/{name}.jpg",
            "hash": hsh,
            "pattern": spec["pattern"]
        }
        print(f"Generated {name}.jpg (hash: {hsh[:8]})")
        
    manifest_path = os.path.join(os.path.dirname(__file__), "fixtures_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Manifest written to {manifest_path}")

if __name__ == "__main__":
    main()
