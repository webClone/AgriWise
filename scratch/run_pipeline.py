import urllib.request
import json

url = "http://localhost:3000/api/agribrain/run"
data = {
    "plotId": "69de624047f8c01c4979d381",
    "mode": "surfaces",
    "query": "",
    "visualIntensity": 0.40,
    "sourcePolicy": "asmae"
}
req = urllib.request.Request(
    url,
    data=json.dumps(data).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

try:
    print("Triggering run...")
    res = urllib.request.urlopen(req)
    body = res.read().decode("utf-8")
    parsed = json.loads(body)
    print("RUN RESPONSE:", json.dumps(parsed, indent=2))
except Exception as e:
    import traceback
    traceback.print_exc()
