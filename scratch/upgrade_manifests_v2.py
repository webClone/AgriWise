"""Upgrade all fixture manifests to dual-provenance schema."""
import json
import os

ROOT = r"c:\Users\E-C\Desktop\agriwise\services\agribrain\layer0\perception"

MANIFESTS = [
    os.path.join(ROOT, "drone_rgb", "benchmark", "fixtures_manifest.json"),
    os.path.join(ROOT, "farmer_photo", "benchmark", "fixtures_manifest.json"),
    os.path.join(ROOT, "satellite_rgb", "benchmark", "fixtures_manifest.json"),
]

for mpath in MANIFESTS:
    with open(mpath, "r") as f:
        data = json.load(f)

    for name, entry in data["fixtures"].items():
        # Migrate source_url -> original_source_url + local_mirror_url
        old_url = entry.pop("source_url", "")
        if "original_source_url" not in entry:
            if "synthetic" in old_url:
                entry["original_source_url"] = f"https://synthetic.agriwise.internal/fixtures/{name}"
            else:
                entry["original_source_url"] = old_url or f"https://registry.agriwise.internal/real/{name}"
        if "local_mirror_url" not in entry:
            entry["local_mirror_url"] = f"file://./{entry.get('local_path', 'fixtures/' + name + '.jpg')}"

    with open(mpath, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Upgraded: {mpath}")

print("Done.")
