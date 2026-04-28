"""
Download real JPEG benchmark fixtures from public domain sources.
Run once to populate benchmark/fixtures/ with actual farm camera images.
"""

import os
import sys
import urllib.request

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

# Public-domain images from Pixabay and Pexels (royalty-free)
FIXTURE_SOURCES = {
    "healthy_canopy.jpg": "https://images.pexels.com/photos/974314/pexels-photo-974314.jpeg?auto=compress&cs=tinysrgb&w=640",
    "shadow_drift.jpg": "https://images.pexels.com/photos/1595108/pexels-photo-1595108.jpeg?auto=compress&cs=tinysrgb&w=640",
    "bare_soil.jpg": "https://images.pexels.com/photos/5505026/pexels-photo-5505026.jpeg?auto=compress&cs=tinysrgb&w=640",
    "overexposed_sky.jpg": "https://images.pexels.com/photos/158827/field-corn-air-frisch-158827.jpeg?auto=compress&cs=tinysrgb&w=640",
    "night_frame.jpg": "https://cdn.pixabay.com/photo/2015/04/23/22/00/tree-736885_640.jpg",
    "orchard_rows.jpg": "https://images.pexels.com/photos/442116/pexels-photo-442116.jpeg?auto=compress&cs=tinysrgb&w=640",
}


def download_fixtures():
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    
    for name, url in FIXTURE_SOURCES.items():
        path = os.path.join(FIXTURE_DIR, name)
        if os.path.exists(path):
            print(f"  [skip] {name} already exists")
            continue
        print(f"  Downloading {name}...")
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            with urllib.request.urlopen(req) as resp:
                with open(path, "wb") as f:
                    f.write(resp.read())
            size = os.path.getsize(path)
            print(f"  [ok] {name} ({size} bytes)")
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
    
    print(f"\nFixtures in {FIXTURE_DIR}:")
    for f in os.listdir(FIXTURE_DIR):
        print(f"  {f}: {os.path.getsize(os.path.join(FIXTURE_DIR, f))} bytes")


if __name__ == "__main__":
    download_fixtures()
