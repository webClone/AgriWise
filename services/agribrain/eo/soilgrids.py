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
        properties = [
            "clay", "sand", "silt", "phh2o", "soc", "bdod", "cec", 
            "nitrogen", "cfvo", "ocd", "ocs", "wv0033", "wv1500"
        ]
        depths = ["0-5cm", "5-15cm", "15-30cm", "30-60cm", "60-100cm"]
        prop_query = "".join(f"&property={p}" for p in properties)
        depth_query = "".join(f"&depth={d}" for d in depths)
        url = f"https://rest.isric.org/soilgrids/v2.0/properties/query?lon={t_lng}&lat={t_lat}{prop_query}{depth_query}&value=mean"
        
        resp = requests.get(url, headers={"Accept": "application/json"}, timeout=_SOILGRIDS_OFFSET_TIMEOUT)
        if resp.status_code != 200:
            return None, False  # None data, API down/error
        
        data = resp.json()
        layers = data.get("properties", {}).get("layers", [])
        if not layers:
            return None, True
            
        def get_avg(prop_name: str, scale_factor: float = 1.0) -> float:
            layer = next((l for l in layers if l.get("name") == prop_name), None)
            if not layer:
                return 0.0
            
            d_depths = layer.get("depths", [])
            d0_5 = next((d.get("values", {}).get("mean", 0.0) for d in d_depths if d.get("label") == "0-5cm"), 0.0) or 0.0
            d5_15 = next((d.get("values", {}).get("mean", 0.0) for d in d_depths if d.get("label") == "5-15cm"), 0.0) or 0.0
            d15_30 = next((d.get("values", {}).get("mean", 0.0) for d in d_depths if d.get("label") == "15-30cm"), 0.0) or 0.0
            
            weighted_sum = (d0_5 * 5.0) + (d5_15 * 10.0) + (d15_30 * 15.0)
            return (weighted_sum / 30.0) / scale_factor
            
        def get_subsoil_avg(prop_name: str, scale_factor: float = 1.0) -> float:
            layer = next((l for l in layers if l.get("name") == prop_name), None)
            if not layer:
                return 0.0
            
            d_depths = layer.get("depths", [])
            d30_60 = next((d.get("values", {}).get("mean", 0.0) for d in d_depths if d.get("label") == "30-60cm"), 0.0) or 0.0
            d60_100 = next((d.get("values", {}).get("mean", 0.0) for d in d_depths if d.get("label") == "60-100cm"), 0.0) or 0.0
            
            weighted_sum = (d30_60 * 30.0) + (d60_100 * 40.0)
            return (weighted_sum / 70.0) / scale_factor
            
        parsed = {}
        has_any_data = False
        for layer in layers:
            if layer.get("depths"):
                has_any_data = True
                break
        if not has_any_data:
            return None, True
            
        parsed["clay"] = get_avg("clay", 10.0)
        parsed["sand"] = get_avg("sand", 10.0)
        parsed["silt"] = get_avg("silt", 10.0)
        parsed["ph"] = get_avg("phh2o", 10.0)
        parsed["soc"] = get_avg("soc", 10.0)
        parsed["organic_carbon"] = parsed["soc"]
        parsed["bdod"] = get_avg("bdod", 100.0)
        parsed["cec"] = get_avg("cec", 10.0)
        parsed["nitrogen"] = get_avg("nitrogen", 100.0)
        parsed["cfvo"] = get_avg("cfvo", 10.0)
        parsed["ocd"] = get_avg("ocd", 10.0)
        parsed["ocs"] = get_avg("ocs", 10.0)
        parsed["wv0033"] = get_avg("wv0033", 10.0)
        parsed["wv1500"] = get_avg("wv1500", 10.0)
        
        parsed["clay_sub"] = get_subsoil_avg("clay", 10.0)
        parsed["ph_sub"] = get_subsoil_avg("phh2o", 10.0)
        parsed["soc_sub"] = get_subsoil_avg("soc", 10.0)
        
        clay = parsed.get("clay", 0.0)
        sand = parsed.get("sand", 0.0)
        silt = parsed.get("silt", 100.0 - (clay + sand))
        
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
        if time.monotonic() - loop_start > _SOILGRIDS_TOTAL_TIMEOUT:
            print(f"[WARN] SoilGrids jitter loop exceeded {_SOILGRIDS_TOTAL_TIMEOUT}s budget, using fallback")
            break
        try:
            parsed_data, api_is_up = _fetch_point(lat + dlat, lng + dlng)
            if parsed_data:
                return parsed_data
            if not api_is_up:
                break
        except Exception as e:
            print(f"SoilGrids offset fetch error: {e}")
            break
            
    return {
        "clay": 25.0,
        "sand": 40.0,
        "silt": 35.0,
        "ph": 6.5,
        "soc": 20.0,
        "organic_carbon": 20.0,
        "bdod": 1.3,
        "cec": 15.0,
        "nitrogen": 1.5,
        "cfvo": 5.0,
        "ocd": 3.0,
        "ocs": 40.0,
        "wv0033": 28.0,
        "wv1500": 14.0,
        "clay_sub": 30.0,
        "ph_sub": 6.7,
        "soc_sub": 12.0,
        "texture_class": "loam",
        "is_generic_fallback": True
    }
