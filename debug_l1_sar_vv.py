
import sys
import os
import json
import logging
from datetime import datetime, timedelta
import requests

# Add project root to path
sys.path.insert(0, os.getcwd())

from services.agribrain.eo.sentinel import get_access_token

def debug_sar_vv_only():
    print("🛰️ Debugging SAR (VV-Only Check)...")
    
    lat = 36.0
    lng = 3.0
    days = 20
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    start_str = start_date.strftime("%Y-%m-%dT00:00:00Z")
    end_str = end_date.strftime("%Y-%m-%dT23:59:59Z")
    
    token = get_access_token()
    
    # Custom Payload for VV Only
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
                "bbox": [lng - 0.005, lat - 0.005, lng + 0.005, lat + 0.005], # Wider bbox
                "properties": { "crs": "http://www.opengis.net/def/crs/EPSG/0/4326" }
            },
            "data": [{
                "type": "sentinel-1-grd",
                "timeRange": { "from": start_str, "to": end_str },
                "dataFilter": { 
                    "acquisitionMode": "IW"
                    # No polarization filter, default to whatever is there
                }
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
    
    print("\n🌍 Requesting VV-Only from Stats API...")
    try:
        url = "https://sh.dataspace.copernicus.eu/api/v1/statistics"
        headers = { "Authorization": f"Bearer {token}", "Content-Type": "application/json" }
        r = requests.post(url, json=payload, headers=headers)
        
        if r.status_code == 200:
            data = r.json().get("data", [])
            print(f"✅ Success! Received {len(data)} intervals.")
            
            valid = 0
            for d in data:
                print(f"DEBUG ITEM: {d}")
                try:
                    # Check for valid pixels
                    outs = d.get("outputs", {}).get("vv", {}).get("bands", [{}])[0].get("stats", {})
                    mean_val = outs.get("mean")
                    if mean_val is not None:
                        valid += 1
                        date_str = d["interval"]["from"][:10]
                        print(f"   📅 {date_str}: VV Mean = {mean_val:.2f} dB")
                except Exception as ex:
                    print(f"   ⚠️ Parsing Error: {ex}")
            
            print(f"\n📊 Valid Data Points: {valid}/{len(data)}")
        else:
            print(f"❌ API Error: {r.status_code} - {r.text}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    debug_sar_vv_only()
