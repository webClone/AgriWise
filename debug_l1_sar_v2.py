
import sys
import os
import json
import logging
from datetime import datetime, timedelta
import requests

# Add project root to path
sys.path.insert(0, os.getcwd())

# Configure logging to see internal warnings
logging.basicConfig(level=logging.INFO)

from services.agribrain.eo.sentinel import fetch_sar_timeseries, get_access_token

def debug_sar_filtered():
    print("🛰️ Debugging L1 SAR Acquisition (v2 - Filtered)...")
    
    # Use the same parameters as the chat
    lat = 36.0
    lng = 3.0
    days = 20
    
    print("\n🌍 Testing Direct Sentinel Connection with 'DV' polarization...")
    try:
        token = get_access_token()
        print(f"🔑 Token Acquired: {bool(token)}")
        
        # Test SAR Fetch
        print(f"📡 Fetching SAR Timeseries for last {days} days at ({lat}, {lng})...")
        sar_raw = fetch_sar_timeseries(lat, lng, days=days)
        
        if sar_raw:
             print(f"✅ Success! Received Data.")
             if "timeseries" in sar_raw:
                 ts = sar_raw['timeseries']
                 print(f"📊 Timeseries Count: {len(ts)}")
                 for i, p in enumerate(ts):
                     print(f"   [{i}] Date: {p.get('date')} VV: {p.get('vv_db')} VH: {p.get('vh_db')}")
             elif "error" in sar_raw:
                 print(f"❌ API Error: {sar_raw['error']}")
        else:
             print("❌ Raw Result is Still None/Empty.")
             print("   Possible causes: API 503, No Data, or Credentials.")

    except Exception as e:
        print(f"❌ Direct Connection Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_sar_filtered()
