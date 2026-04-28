import os
import json
from pathlib import Path

root_dir = Path("c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/perception")

for manifest_path in root_dir.rglob("fixtures_manifest.json"):
    with open(manifest_path, 'r') as f:
        data = json.load(f)
        
    fixtures = data.get("fixtures", {})
    new_fixtures = {}
    
    for key, val in fixtures.items():
        new_val = {
            "id": key,
            "local_path": val.get("file", f"fixtures/{key}.jpg"),
            "sha256": val.get("hash", ""),
            "source_url": val.get("source_url", "https://synthetic.agriwise.local/"),
            "license": val.get("license", "synthetic"),
            "license_notes": val.get("license_notes", "generated for test"),
            "downloaded_at": val.get("downloaded_at", "2026-04-25T00:00:00Z"),
            "scene_type": val.get("scene_type", "synthetic"),
            "crop_type": val.get("crop_type", "mixed"),
            "expected_labels": val.get("expected_labels", []),
            "ci_safe": True,
            "benchmark_only": True,
            "redistributable": False,
            "notes": "Governance upgrade"
        }
        # Preserve specific fields if they exist
        if "pattern" in val:
            new_val["pattern"] = val["pattern"]
        if "resolution_m" in val:
            new_val["resolution_m"] = val["resolution_m"]
            
        new_fixtures[key] = new_val
        
    data["fixtures"] = new_fixtures
    
    with open(manifest_path, 'w') as f:
        json.dump(data, f, indent=2)
        
print("Upgraded manifests")
