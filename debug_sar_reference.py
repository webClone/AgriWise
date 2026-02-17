
import sys
import os
import json
import logging
from datetime import datetime, timedelta
import requests

# Add project root to path
sys.path.insert(0, os.getcwd())

from services.agribrain.eo.sentinel import get_access_token, fetch_sar_timeseries

def debug_reference_loc():
    print("🛰️ Debugging SAR at REFERENCE Location (Rotterdam Port)...")
    print("   Coords: 51.95, 4.05 (High Traffic, Guaranteed S1 Coverage)")
    
    lat = 51.95
    lng = 4.05
    days = 20
    
    # 1. Test Standard Fetch (DV Polarization) - via sentinel.py
    print("\n--- Test 1: Standard DV Fetch (via sentinel.py) ---")
    try:
        sar_raw = fetch_sar_timeseries(lat, lng, days=days)
        if sar_raw and "timeseries" in sar_raw and len(sar_raw["timeseries"]) > 0:
             print(f"✅ DV Success! Found {len(sar_raw['timeseries'])} items.")
             print(f"   Sample: {sar_raw['timeseries'][0]}")
        else:
             print("❌ DV Fetch returned 0 items or None.")
             if sar_raw and "error" in sar_raw:
                 print(f"   Error: {sar_raw['error']}")
    except Exception as e:
        print(f"❌ DV Exception: {e}")

    # 2. Test No-Filter Fetch (Custom Payload)
    print("\n--- Test 2: No-Filter Fetch (Rotterdam) ---")
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        start_str = start_date.strftime("%Y-%m-%dT00:00:00Z")
        end_str = end_date.strftime("%Y-%m-%dT23:59:59Z")
        token = get_access_token()
        
        evalscript = """
        //VERSION=3
        function setup() {
            return {
                input: ["VV", "dataMask"],
                output: [
                    { id: "vv", bands: 1, sampleType: "FLOAT32" },
                    { id: "dataMask", bands: 1, sampleType: "UINT8" }
                ]
            };
        }
        function evaluatePixel(s) {
            return {
                vv: [10 * Math.log10(s.VV)],
                dataMask: [s.dataMask]
            };
        }
        """

        payload = {
            "input": {
                "bounds": {
                    "bbox": [lng - 0.005, lat - 0.005, lng + 0.005, lat + 0.005],
                    "properties": { "crs": "http://www.opengis.net/def/crs/EPSG/0/4326" }
                },
                "data": [{
                    "type": "sentinel-1-grd",
                    "timeRange": { "from": start_str, "to": end_str },
                    "dataFilter": { "acquisitionMode": "IW" } # NO POLARIZATION FILTER
                }]
            },
            "aggregation": {
                "timeRange": { "from": start_str, "to": end_str },
                "aggregationInterval": { "of": "P5D" },
                "evalscript": evalscript,
                "width": 1,
                "height": 1
            }
        }
        
        r = requests.post("https://sh.dataspace.copernicus.eu/api/v1/statistics", json=payload, headers={"Authorization": f"Bearer {token}"})
        if r.status_code == 200:
            data = r.json().get("data", [])
            valid_count = 0
            for d in data:
                 outs = d.get("outputs", {}).get("vv", {}).get("bands", [{}])[0].get("stats", {})
                 mean_val = outs.get("mean")
                 if mean_val is not None:
                     valid_count += 1
                     print(f"   📅 {d['interval']['from'][:10]}: VV={mean_val:.2f}")
            print(f"📊 No-Filter Results: {valid_count} valid / {len(data)} intervals")
        else:
            print(f"❌ API Error: {r.status_code}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    debug_reference_loc()
