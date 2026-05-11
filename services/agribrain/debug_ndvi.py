"""Debug NDVI raw output structure."""
from eo.sentinel import get_access_token, _build_process_bounds, SENTINEL_STATS_URL
from datetime import datetime, timedelta
import requests, json

lat, lng = 36.0, 3.0
token = get_access_token()
end_date = datetime.now()
start_date = end_date - timedelta(days=90)

start_str = start_date.strftime("%Y-%m-%dT00:00:00Z")
end_str = end_date.strftime("%Y-%m-%dT23:59:59Z")
bounds = _build_process_bounds(None, lat, lng)

evalscript = """
//VERSION=3
function setup() {
    return {
        input: ["B04", "B08", "dataMask"],
        output: [
            { id: "default", bands: 1, sampleType: "FLOAT32" },
            { id: "dataMask", bands: 1, sampleType: "UINT8" }
        ]
    };
}
function evaluatePixel(sample) {
    let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
    return {
        default: [ndvi],
        dataMask: [sample.dataMask]
    };
}
"""

payload = {
    "input": {"bounds": bounds, "data": [{"type": "sentinel-2-l2a", "timeRange": {"from": start_str, "to": end_str}}]},
    "aggregation": {"timeRange": {"from": start_str, "to": end_str}, "aggregationInterval": {"of": "P5D"}, "evalscript": evalscript, "resolution": 100}
}

response = requests.post(SENTINEL_STATS_URL, json=payload, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
data = response.json()

# Print FULL structure of first item
if data.get("data"):
    print("=== First item full structure ===")
    print(json.dumps(data["data"][0], indent=2))
