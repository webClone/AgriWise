import urllib.request
import json
import time

plot_id = "69de624047f8c01c4979d381"
farm_id = "697ddd3bd4195b809226a680"

# 1. Trigger Base Snapshot
print("Step 1: Creating base snapshot via /api/agribrain/plot-intelligence...")
url_intel = "http://localhost:3000/api/agribrain/plot-intelligence"
intel_data = {
    "plotId": plot_id,
    "farmId": farm_id,
    "forceRefresh": True
}
req_intel = urllib.request.Request(
    url_intel,
    data=json.dumps(intel_data).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
res_intel = urllib.request.urlopen(req_intel)
parsed_intel = json.loads(res_intel.read().decode("utf-8"))
print("Base snapshot created successfully!")

# 2. Trigger Surfaces run
print("\nStep 2: Generating surfaces via /api/agribrain/run...")
url_run = "http://localhost:3000/api/agribrain/run"
run_data = {
    "plotId": plot_id,
    "mode": "surfaces",
    "query": "",
    "visualIntensity": 0.40,
    "sourcePolicy": "asmae"
}
req_run = urllib.request.Request(
    url_run,
    data=json.dumps(run_data).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
res_run = urllib.request.urlopen(req_run)
parsed_run = json.loads(res_run.read().decode("utf-8"))
print("Surfaces run finished!")

# 3. Verify Latest Surface
print("\nStep 3: Querying latest surfaces to verify cache...")
url_latest = "http://localhost:3000/api/agribrain/surfaces/latest"
latest_data = {
    "plotId": plot_id,
    "sourcePolicy": "asmae"
}
req_latest = urllib.request.Request(
    url_latest,
    data=json.dumps(latest_data).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
res_latest = urllib.request.urlopen(req_latest)
parsed_latest = json.loads(res_latest.read().decode("utf-8"))
print("STATUS:", parsed_latest.get("status"))
print("KEYS PRESENT:", list(parsed_latest.keys()))
print("MODE DISPLAY STATE FOR CANOPY:")
print(json.dumps(parsed_latest.get("mode_display_state", {}).get("canopy"), indent=2))
