"""
EO SoilGrids Module
Handles soil property fetching from ISRIC SoilGrids REST API.
Includes spatial jitter search for unmapped polygon centroids.
Extracted from sentinel.py for separation of concerns.
"""

import time
import requests
from typing import Dict, Any

from eo.auth import EO_REQUEST_TIMEOUT

# Per-offset timeout for SoilGrids jitter (shorter than general EO timeout)
_SOILGRIDS_OFFSET_TIMEOUT = 5
# Total wall-clock cap for the entire jitter loop
_SOILGRIDS_TOTAL_TIMEOUT = 30


def fetch_soil_properties(lat: float, lng: float) -> Dict[str, Any]:
    """
    Fetches base soil properties from ISRIC SoilGrids REST API.
    If the centroid is an unmapped pixel (e.g. coast/urban), recursively searches nearby pixels.
    Provides fallback static data if the parcel lacks uploaded soil tests and all nearby pixels are unmapped.
    """
    def _fetch_point(t_lat: float, t_lng: float):
        url = f"https://rest.isric.org/soilgrids/v2.0/properties/query?lon={t_lng}&lat={t_lat}&property=clay&property=sand&property=silt&property=soc&property=phh2o&property=nitrogen&property=cec&property=bdod&depth=0-5cm&value=mean"
        resp = requests.get(url, headers={"Accept": "application/json"}, timeout=_SOILGRIDS_OFFSET_TIMEOUT)
        if resp.status_code != 200:
            return None, False  # None data, API down/error
        
        data = resp.json()
        layers = data.get("properties", {}).get("layers", [])
        
        parsed = {}
        for layer in layers:
            name = layer.get("name")
            unit = layer.get("unit_measure", {})
            d_factor = unit.get("d_factor", 10)
            
            depths = layer.get("depths", [])
            if not depths: continue
            
            mean_val = depths[0].get("values", {}).get("mean")
            if mean_val is None: continue
                
            scaled_val = mean_val / float(d_factor)
            
            if name == "clay": parsed["clay"] = scaled_val
            elif name == "sand": parsed["sand"] = scaled_val
            elif name == "silt": parsed["silt"] = scaled_val
            elif name == "phh2o": parsed["ph"] = scaled_val
            elif name == "soc": parsed["organic_carbon"] = scaled_val
            elif name == "nitrogen": parsed["nitrogen"] = scaled_val
            elif name == "cec": parsed["cec"] = scaled_val
            elif name == "bdod": parsed["bdod"] = scaled_val

        if not parsed:
            return None, True  # None data, but API is up (unmapped pixel)
            
        clay = parsed.get("clay", 0)
        sand = parsed.get("sand", 0)
        silt = parsed.get("silt", 100 - (clay + sand))
        
        texture = "loam"
        if clay >= 40: texture = "clay"
        elif sand >= 70: texture = "sand"
        elif silt >= 40 and clay < 27 and sand < 50: texture = "silt"
            
        parsed["texture_class"] = texture
        parsed["is_generic_fallback"] = False
        return parsed, True

    # Spatial offsets: Center, N, S, E, W (250m), then diagonals/500m
    offsets = [
        (0, 0),
        (0.0025, 0), (-0.0025, 0), (0, 0.0025), (0, -0.0025),
        (0.005, 0), (-0.005, 0), (0, 0.005), (0, -0.005)
    ]
    
    loop_start = time.monotonic()
    
    for dlat, dlng in offsets:
        # Total wall-clock guard: abort jitter loop if we exceed budget
        if time.monotonic() - loop_start > _SOILGRIDS_TOTAL_TIMEOUT:
            print(f"[WARN] SoilGrids jitter loop exceeded {_SOILGRIDS_TOTAL_TIMEOUT}s budget, using fallback")
            break
        try:
            parsed_data, api_is_up = _fetch_point(lat + dlat, lng + dlng)
            if parsed_data:
                return parsed_data
            if not api_is_up:
                break  # API is failing, don't loop
        except Exception as e:
            print(f"SoilGrids offset fetch error: {e}")
            break  # Timeout or network error, don't loop
            
    # Fallback for coastal, urban, or no-data polygons where ISRIC returns None everywhere
    return {
        "clay": 25.0,
        "sand": 40.0,
        "silt": 35.0,
        "ph": 6.5,
        "organic_carbon": 20.0,
        "nitrogen": 1.5,
        "cec": 15.0,
        "bdod": 1.3,
        "texture_class": "loam",
        "is_generic_fallback": True
    }
