import urllib.request
import json
import time

url = "http://localhost:3000/api/agribrain/surfaces/latest"
data = {
    "plotId": "69de624047f8c01c4979d381",
    "sourcePolicy": "asmae"
}

for attempt in range(12):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        res = urllib.request.urlopen(req)
        body = res.read().decode("utf-8")
        parsed = json.loads(body)
        status = parsed.get("status")
        print(f"Attempt {attempt + 1}: STATUS: {status}")
        if status == "fresh":
            print("MODE DISPLAY STATE FOR CANOPY:")
            print(json.dumps(parsed.get("mode_display_state", {}).get("canopy"), indent=2))
            print("PROVENANCE:")
            print(json.dumps(parsed.get("provenance"), indent=2))
            break
        elif status == "generating":
            time.sleep(2)
        else:
            print("Unexpected status:", parsed)
            break
    except Exception as e:
        print("Error during check:", e)
        time.sleep(2)
