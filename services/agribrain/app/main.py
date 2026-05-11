"""
AgriBrain API - AI Organism Backend
Specialized AIs orchestrated by LLM conductor
"""

# Load environment variables from project root .env file
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root (agriwise directory)
project_root = Path(__file__).parent.parent.parent.parent  # services/agribrain/app/main.py -> agriwise
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"[OK] Loaded environment from: {env_path}")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import json
from datetime import datetime, timedelta

# Import specialized AIs
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.orchestrator import orchestrator, AIOrchestrator
from health.disease_risk import disease_risk_ai
from perception.phenology import phenology_ai
from climate.spray_window import spray_window_ai
from climate.water_stress import water_stress_ai

# Register all specialized AIs
orchestrator.register_ai("disease_risk", disease_risk_ai)
orchestrator.register_ai("phenology", phenology_ai)
orchestrator.register_ai("spray_window", spray_window_ai)
orchestrator.register_ai("water_stress", water_stress_ai)

app = FastAPI(
    title="AgriBrain API",
    description="AI Organism for Agriculture - Specialized Deep Learning modules orchestrated by LLM",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Request/Response Models
# ============================================================================

class OrchestrationRequest(BaseModel):
    """Request to the AI Organism orchestrator"""
    query: str
    context: Dict[str, Any]  # Full plot context (realTime, soil, climate, etc.)
    crop: Optional[str] = "tomato"

class OrchestrationResponse(BaseModel):
    """Response from AI Organism orchestrator"""
    detected_intents: List[str]
    routed_to: List[str]
    ai_results: Dict[str, Any]
    needs_llm_synthesis: bool
    timestamp: str

class SpecializedAIRequest(BaseModel):
    """Direct request to a specific AI"""
    context: Dict[str, Any]
    crop: Optional[str] = "tomato"

class V2RunRequest(BaseModel):
    """Unified Next.js API route payload"""
    context: str  # Base64 encoded context
    query: Optional[str] = ""
    mode: Optional[str] = "chat"
    history: Optional[str] = ""
    exp: Optional[str] = "INTERMEDIATE"
    userMode: Optional[str] = "FARMER"

class V2IntentRequest(BaseModel):
    query: str
    history: Optional[str] = ""

# ============================================================================
# Legacy Endpoints (for backward compatibility)
# ============================================================================

class EORequest(BaseModel):
    field_id: str
    start_date: str
    end_date: str

class YieldRequest(BaseModel):
    field_id: str
    crop: str

@app.get("/")
def root():
    return {
        "status": "healthy",
        "service": "agribrain",
        "version": "2.0.0",
        "capabilities": ["disease-risk", "phenology", "spray-window", "water-stress"],
        "timestamp": datetime.now().isoformat()
    }

@app.get("/debug/sentinel")
def debug_sentinel():
    """
    Diagnostic endpoint to test Sentinel Hub authentication.
    Returns detailed error information to help debug connection issues.
    """
    import requests
    
    # Check environment variables
    client_id = os.getenv("SENTINEL_HUB_CLIENT_ID")
    client_secret = os.getenv("SENTINEL_HUB_CLIENT_SECRET")
    
    result = {
        "env_loaded": True,
        "client_id_present": bool(client_id),
        "client_id_prefix": client_id[:15] + "..." if client_id else None,
        "client_secret_present": bool(client_secret),
        "client_secret_length": len(client_secret) if client_secret else 0,
        "auth_url": "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
        "auth_test": None,
        "error": None
    }
    
    if not client_id or not client_secret:
        result["error"] = "Missing SENTINEL_HUB_CLIENT_ID or SENTINEL_HUB_CLIENT_SECRET"
        return result
    
    # Try authentication
    try:
        auth_url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret
        }
        
        response = requests.post(auth_url, data=payload, timeout=15)
        result["auth_status_code"] = response.status_code
        
        if response.status_code == 200:
            token_data = response.json()
            result["auth_test"] = "SUCCESS"
            result["token_type"] = token_data.get("token_type")
            result["expires_in"] = token_data.get("expires_in")
        else:
            result["auth_test"] = "FAILED"
            result["error"] = response.text[:500]  # Limit error message length
            
    except Exception as e:
        result["auth_test"] = "ERROR"
        result["error"] = str(e)
    
    return result

@app.get("/debug/sar-test")
def debug_sar_test(lat: float = 36.5, lng: float = 2.9):
    """
    Test actual SAR data request to diagnose data fetching issues.
    """
    import requests
    from datetime import datetime, timedelta
    
    result = {
        "lat": lat,
        "lng": lng,
        "steps": []
    }
    
    # Step 1: Get token
    try:
        from eo.sentinel import get_access_token, SENTINEL_STATS_URL
        token = get_access_token()
        result["steps"].append({"step": "get_token", "status": "SUCCESS", "token_prefix": token[:20] + "..."})
    except Exception as e:
        result["steps"].append({"step": "get_token", "status": "ERROR", "error": str(e)})
        return result
    
    # Step 2: Build request
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    start_str = start_date.strftime("%Y-%m-%dT00:00:00Z")
    end_str = end_date.strftime("%Y-%m-%dT23:59:59Z")
    
    delta = 0.002
    bbox = [lng - delta, lat - delta, lng + delta, lat + delta]
    
    evalscript = """
    //VERSION=3
    function setup() {
        return {
            input: ["VV", "VH", "dataMask"],
            output: [
                { id: "vv", bands: 1, sampleType: "FLOAT32" },
                { id: "vh", bands: 1, sampleType: "FLOAT32" },
                { id: "dataMask", bands: 1, sampleType: "UINT8" }
            ]
        };
    }
    function evaluatePixel(s) {
        return {
            vv: [10 * Math.log10(s.VV)],
            vh: [10 * Math.log10(s.VH)],
            dataMask: [s.dataMask]
        };
    }
    """
    
    payload = {
        "input": {
            "bounds": {
                "bbox": bbox,
                "properties": { "crs": "http://www.opengis.net/def/crs/EPSG/0/4326" }
            },
            "data": [{
                "type": "sentinel-1-grd",
                "timeRange": { "from": start_str, "to": end_str },
                "dataFilter": { "acquisitionMode": "IW" }
            }]
        },
        "aggregation": {
            "timeRange": { "from": start_str, "to": end_str },
            "aggregationInterval": { "of": "P90D" },
            "evalscript": evalscript,
            "width": 1,
            "height": 1
        }
    }
    
    result["request"] = {
        "url": SENTINEL_STATS_URL,
        "bbox": bbox,
        "time_range": f"{start_str} to {end_str}"
    }
    
    # Step 3: Make request
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(SENTINEL_STATS_URL, json=payload, headers=headers, timeout=30)
        result["steps"].append({
            "step": "api_request", 
            "status_code": response.status_code
        })
        
        if response.status_code == 200:
            data = response.json()
            result["response"] = data
            result["steps"].append({"step": "parse_response", "status": "SUCCESS", "data_count": len(data.get("data", []))})
        else:
            result["steps"].append({"step": "api_request", "status": "FAILED", "error": response.text[:500]})
            
    except Exception as e:
        result["steps"].append({"step": "api_request", "status": "ERROR", "error": str(e)})
    
    return result

@app.get("/eo/rainfall-climatology")
def get_rainfall_climatology(lat: float, lng: float):
    """
    Get 30-year monthly rainfall normals (1991-2020) from ERA5 via Open-Meteo.
    """
    from eo.sentinel import fetch_rainfall_climatology
    result = fetch_rainfall_climatology(lat, lng)
    if result:
        return result
    return {"error": "Could not fetch rainfall climatology", "lat": lat, "lng": lng}

@app.get("/eo/rainfall-history")
def get_rainfall_history(lat: float, lng: float, years: int = 30):
    """
    Get annual rainfall history for the past N years.
    """
    from eo.sentinel import fetch_rainfall_history
    result = fetch_rainfall_history(lat, lng, years)
    if result:
        return result
    return {"error": "Could not fetch rainfall history", "lat": lat, "lng": lng}

@app.get("/eo/drought-analysis")
def get_drought_analysis(lat: float, lng: float):
    """
    Analyze drought frequency and risk based on historical rainfall.
    """
    from eo.sentinel import calculate_drought_frequency
    result = calculate_drought_frequency(lat, lng)
    if result:
        return result
    return {"error": "Could not perform drought analysis", "lat": lat, "lng": lng}

@app.get("/eo/rainfall-anomaly")
def get_rainfall_anomaly(lat: float, lng: float):
    """
    Compare current year's rainfall to 30-year baseline.
    """
    from eo.sentinel import get_current_rainfall_anomaly
    result = get_current_rainfall_anomaly(lat, lng)
    if result:
        return result
    return {"error": "Could not calculate rainfall anomaly", "lat": lat, "lng": lng}

@app.get("/eo/land-cover")
def get_land_cover_data(lat: float, lng: float):
    """
    Get land cover classification from Sentinel-2 Scene Classification (SCL).
    """
    from eo.sentinel import fetch_land_cover
    result = fetch_land_cover(lat, lng)
    if result:
        return result
    return {"error": "Land cover data unavailable", "lat": lat, "lng": lng}

@app.get("/tools/eo/get_field_indicators")
def get_field_indicators(field_id: str, start_date: str, end_date: str):
    """Legacy EO endpoint - now routes to Crop Observation AI"""
    return {
        "field_id": field_id,
        "date_range": {"start": start_date, "end": end_date},
        "ndvi": 0.65,
        "ndmi": 0.42,
        "source": "LEGACY_FALLBACK",
        "message": "Use /orchestrate for AI Organism routing"
    }

# ============================================================================
# Multi-Source Earth Observation Endpoints
# ============================================================================

@app.get("/eo/indices")
def get_vegetation_indices(lat: float, lng: float):
    """
    Get multiple vegetation indices from Sentinel-2:
    - NDVI: Vegetation health
    - EVI: Enhanced vegetation (better for dense canopy)
    - NDWI: Water content in vegetation
    - NDMI: Moisture stress
    """
    from eo.sentinel import fetch_vegetation_indices
    result = fetch_vegetation_indices(lat, lng)
    if result:
        return result
    return {"error": "Could not fetch vegetation indices", "lat": lat, "lng": lng}

@app.get("/eo/soil-moisture")
def get_soil_moisture(lat: float, lng: float):
    """
    Get Sentinel-1 SAR backscatter as soil moisture proxy.
    VV/VH polarization ratio correlates with soil moisture.
    """
    from eo.sentinel import fetch_soil_moisture_proxy
    result = fetch_soil_moisture_proxy(lat, lng)
    if result:
        return result
    return {"error": "Could not fetch SAR data", "lat": lat, "lng": lng}

@app.get("/eo/sar-timeseries")
def get_sar_timeseries(lat: float, lng: float, days: int = 30):
    """
    Get 30-day Sentinel-1 SAR time-series (VV/VH).
    Cloud-independent data for trend analysis.
    """
    from eo.sentinel import fetch_sar_timeseries
    result = fetch_sar_timeseries(lat, lng, days)
    if result:
        return result
    return {"error": "Could not fetch SAR timeseries", "lat": lat, "lng": lng}

@app.get("/eo/sar-biomass")
def get_sar_biomass(lat: float, lng: float):
    """
    Get crop biomass estimate from Sentinel-1 VH backscatter.
    Higher VH = denser/taller vegetation.
    """
    from eo.sentinel import fetch_biomass_estimate
    result = fetch_biomass_estimate(lat, lng)
    if result:
        return result
    return {"error": "Could not fetch biomass data", "lat": lat, "lng": lng}

@app.get("/eo/sar-flood")
def get_sar_flood(lat: float, lng: float):
    """
    Detect flooded vs dry soil using Sentinel-1 SAR.
    Low VV indicates water (specular reflection).
    """
    from eo.sentinel import detect_flood_status
    result = detect_flood_status(lat, lng)
    if result:
        return result
    return {"error": "Could not detect flood status", "lat": lat, "lng": lng}

@app.get("/eo/sar-emergence")
def get_sar_emergence(lat: float, lng: float):
    """
    Detect early crop emergence from VH temporal rise.
    SAR sees crop structure BEFORE NDVI reacts.
    """
    from eo.sentinel import detect_crop_emergence
    result = detect_crop_emergence(lat, lng)
    if result:
        return result
    return {"error": "Could not detect crop emergence", "lat": lat, "lng": lng}

@app.get("/eo/historical-weather")
def get_historical_weather(lat: float, lng: float, start_date: str, end_date: str):
    """
    Get ERA5 historical climate data via Open-Meteo.
    Useful for training data and climate pattern analysis.
    """
    from eo.sentinel import fetch_historical_weather
    result = fetch_historical_weather(lat, lng, start_date, end_date)
    if result:
        return result
    return {"error": "Could not fetch historical weather", "lat": lat, "lng": lng}

@app.get("/eo/fire-risk")
def get_fire_risk(lat: float, lng: float, radius_km: int = 50):
    """
    Get active fire data from NASA FIRMS (MODIS/VIIRS).
    Returns fire detections within radius in the last 7 days.
    """
    from eo.sentinel import fetch_fire_risk
    result = fetch_fire_risk(lat, lng, radius_km)
    if result:
        return result
    return {"error": "Could not fetch fire data", "lat": lat, "lng": lng}

@app.get("/eo/all")
def get_all_eo_data(lat: float, lng: float):
    """
    Fetch ALL available EO data for a location in one call.
    Combines: Sentinel-2 indices, Sentinel-1 SAR, soil, solar, air quality, elevation, fire risk
    """
    from eo.sentinel import fetch_all_eo_data
    return fetch_all_eo_data(lat, lng)

@app.get("/eo/soil-layers")
def get_soil_moisture_layers(lat: float, lng: float):
    """
    Get multi-layer soil moisture from Open-Meteo (ERA5-Land).
    Returns moisture at 0-7cm, 7-28cm, 28-100cm, and 100-255cm depths.
    FREE - no API key required.
    """
    from eo.sentinel import fetch_soil_moisture_layers
    result = fetch_soil_moisture_layers(lat, lng)
    if result:
        return result
    return {"error": "Could not fetch soil moisture layers", "lat": lat, "lng": lng}

@app.get("/eo/water-balance")
def get_water_balance(lat: float, lng: float, days_past: int = 30, days_future: int = 7):
    """
    Get Water Balance (Precipitation - ET0) for past and future.
    Used for Water Stress Analysis.
    """
    from eo.sentinel import fetch_water_balance
    result = fetch_water_balance(lat, lng, days_past, days_future)
    if result:
        return result
    return {"error": "Could not calculate water balance", "lat": lat, "lng": lng}

@app.get("/eo/land-cover")
def get_land_cover(lat: float, lng: float):
    """
    Get Land Cover classification (Sentinel-2 SCL).
    """
    from eo.sentinel import fetch_land_cover
    result = fetch_land_cover(lat, lng)
    if result:
        return result
    return {"error": "Could not fetch land cover", "lat": lat, "lng": lng}

@app.get("/eo/sar-analysis")
def get_sar_analysis(lat: float, lng: float):
    """
    Get comprehensive SAR analysis (Moisture, Biomass, Flood, Emergence).
    Aggregates multiple SAR-based metrics into one response.
    """
    from eo.sentinel import (
        fetch_soil_moisture_proxy, 
        fetch_biomass_estimate, 
        detect_flood_status, 
        detect_crop_emergence
    )
    
    # We could run these in parallel threads for speed, but for now sequential is fine or
    # reliance on Sentinel Hub cache will make subsequent calls fast.
    
    moisture = fetch_soil_moisture_proxy(lat, lng)
    biomass = fetch_biomass_estimate(lat, lng)
    flood = detect_flood_status(lat, lng)
    emergence = detect_crop_emergence(lat, lng)
    
    return {
        "moisture": moisture if moisture else {"error": "Unavailable"},
        "biomass": biomass if biomass else {"error": "Unavailable"},
        "flood": flood if flood else {"error": "Unavailable"},
        "emergence": emergence if emergence else {"error": "Unavailable"}
    }

@app.get("/eo/environment-analysis")
def get_environment_analysis(lat: float, lng: float):
    """
    Get environmental context (Air Quality, Fire Risk, Elevation).
    """
    from eo.sentinel import (
        fetch_air_quality,
        fetch_fire_risk,
        fetch_elevation
    )
    
    air = fetch_air_quality(lat, lng)
    fire = fetch_fire_risk(lat, lng)
    elevation = fetch_elevation(lat, lng)
    
    return {
        "air_quality": air if air else {"error": "Unavailable"},
        "fire_risk": fire if fire else {"error": "Unavailable"},
        "elevation": elevation if elevation else {"error": "Unavailable"}
    }

@app.get("/eo/soil-properties")
def get_soil_properties(lat: float, lng: float):
    """
    Get soil properties from SoilGrids (ISRIC).
    Returns: pH, organic carbon, nitrogen, clay/sand/silt content, CEC.
    FREE - no API key required.
    """
    from eo.sentinel import fetch_soil_properties
    result = fetch_soil_properties(lat, lng)
    if result:
        return result
    return {"error": "Could not fetch soil properties", "lat": lat, "lng": lng}

@app.get("/eo/solar")
def get_solar_radiation(lat: float, lng: float, days: int = 7):
    """
    Get solar radiation and GDD (Growing Degree Days) from NASA POWER.
    FREE - no API key required.
    """
    from eo.sentinel import fetch_solar_radiation
    result = fetch_solar_radiation(lat, lng, days)
    if result:
        return result
    return {"error": "Could not fetch solar data", "lat": lat, "lng": lng}

@app.get("/eo/elevation")
def get_elevation(lat: float, lng: float):
    """
    Get elevation data from Open-Elevation API.
    FREE - no API key required.
    """
    from eo.sentinel import fetch_elevation
    result = fetch_elevation(lat, lng)
    if result:
        return result
    return {"error": "Could not fetch elevation", "lat": lat, "lng": lng}

@app.get("/eo/air-quality")
def get_air_quality(lat: float, lng: float):
    """
    Get air quality data from Open-Meteo.
    Returns: PM2.5, PM10, Ozone, NO2, SO2, AQI.
    FREE - no API key required.
    """
    from eo.sentinel import fetch_air_quality
    result = fetch_air_quality(lat, lng)
    if result:
        return result
    return {"error": "Could not fetch air quality", "lat": lat, "lng": lng}

@app.get("/eo/weather")
def get_openweather(lat: float, lng: float):
    """
    Get current weather from OpenWeatherMap.
    Uses your OPENWEATHER_API_KEY from .env file.
    """
    from eo.sentinel import fetch_openweather_data
    result = fetch_openweather_data(lat, lng)
    if result:
        return result
    return {"error": "Could not fetch weather", "lat": lat, "lng": lng}

@app.get("/eo/forecast")
def get_openweather_forecast(lat: float, lng: float):
    """
    Get 5-day weather forecast from OpenWeatherMap.
    Uses your OPENWEATHER_API_KEY from .env file.
    """
    from eo.sentinel import fetch_openweather_forecast
    result = fetch_openweather_forecast(lat, lng)
    if result:
        return result
    return {"error": "Could not fetch forecast", "lat": lat, "lng": lng}





# ============================================================================
# PHENOLOGY & GROWTH STAGE ENDPOINTS
# ============================================================================

@app.get("/phenology/calendar")
def get_crop_calendar_endpoint(crop: str):
    """
    Get crop calendar with planting/harvest windows and GDD requirements.
    Available crops: tomato, wheat, corn, potato, olive, grape, citrus, date_palm
    """
    from eo.sentinel import get_crop_calendar
    result = get_crop_calendar(crop)
    if result:
        return result
    return {"error": f"No calendar found for crop: {crop}", "available_crops": ["tomato", "wheat", "corn", "potato", "olive", "grape", "citrus", "date_palm"]}

@app.get("/phenology/kc")
def get_crop_kc_endpoint(crop: str, growth_stage: str = None):
    """
    Get FAO crop coefficients (Kc) for water requirement estimation.
    Available crops: tomato, wheat, corn, potato, olive, grape, citrus, date_palm, cotton, rice, soybean, sunflower, barley
    """
    from eo.sentinel import get_crop_kc
    result = get_crop_kc(crop, growth_stage)
    if result:
        return result
    return {"error": f"No Kc found for crop: {crop}"}

@app.get("/phenology/gdd")
def get_gdd_accumulation(lat: float, lng: float, crop: str = "tomato", days: int = 90):
    """
    Calculate cumulative Growing Degree Days (GDD) for a location.
    Returns current growth stage based on GDD accumulation.
    """
    from eo.sentinel import fetch_gdd_accumulation
    result = fetch_gdd_accumulation(lat, lng, crop, days)
    if result:
        return result
    return {"error": "Could not calculate GDD", "lat": lat, "lng": lng}

@app.get("/phenology/all")
def get_comprehensive_phenology(lat: float, lng: float, crop: str = "tomato"):
    """
    Get comprehensive phenology data: crop calendar, Kc values, GDD, and current growth stage.
    """
    from eo.sentinel import fetch_comprehensive_phenology
    return fetch_comprehensive_phenology(lat, lng, crop)

@app.get("/phenology/crops")
def get_available_crops():
    """
    Get list of all supported crops with their data.
    """
    from eo.sentinel import CROP_CALENDARS, CROP_KC_COEFFICIENTS
    return {
        "crops_with_calendar": list(CROP_CALENDARS.keys()),
        "crops_with_kc": list(CROP_KC_COEFFICIENTS.keys()),
        "source": "fao-crop-data"
    }

@app.post("/tools/ml/predict_yield")
def predict_yield(req: YieldRequest):
    """Legacy ML endpoint - now routes to Yield Prediction AI"""
    return {
        "field_id": req.field_id,
        "crop": req.crop,
        "predicted_yield_t_ha": 45.0,
        "confidence": 0.82,
        "source": "LEGACY_FALLBACK",
        "message": "Use /orchestrate for AI Organism routing"
    }

# ============================================================================
# AI Organism Endpoints
# ============================================================================

@app.post("/orchestrate", response_model=OrchestrationResponse)
def orchestrate(req: OrchestrationRequest):
    """
    Main AI Organism endpoint.
    Routes query to specialized AIs based on intent classification.
    Returns structured results for LLM synthesis.
    """
    # Add crop to context
    context = req.context.copy()
    context["crop"] = req.crop
    
    # Route through orchestrator
    result = orchestrator.route_query(req.query, context)
    
    return OrchestrationResponse(
        detected_intents=result["detected_intents"],
        routed_to=result["routed_to"],
        ai_results=result["results"],
        needs_llm_synthesis=True,  # LLM should always synthesize
        timestamp=datetime.now().isoformat()
    )


# ============================================================================
# /v2/satellite-tile  RGB Tile Runtime (Weekly Cache)
# ============================================================================

class SatelliteTileRequest(BaseModel):
    """Request for satellite RGB tile."""
    plot_id: str
    lat: float
    lng: float
    polygon: Optional[Any] = None
    force: bool = False

@app.post("/v2/satellite-tile")
def api_satellite_tile(req: SatelliteTileRequest):
    """
    Fetch a Sentinel-2 True Color RGB tile for a plot polygon.
    Cached for 7 days. Frontend calls once on plot page load.
    """
    try:
        from layer0.perception.satellite_rgb.tile_runtime import (
            fetch_rgb_tile, get_tile_metadata, _is_cache_valid
        )
        
        if not req.force and _is_cache_valid(req.plot_id):
            meta = get_tile_metadata(req.plot_id)
            return {"status": "cached", "plot_id": req.plot_id, "metadata": meta}
        
        image_bytes = fetch_rgb_tile(
            plot_id=req.plot_id, lat=req.lat, lng=req.lng,
            polygon_coords=req.polygon, force=req.force,
        )
        
        if image_bytes:
            meta = get_tile_metadata(req.plot_id)
            return {"status": "fetched", "plot_id": req.plot_id, "tile_size_bytes": len(image_bytes), "metadata": meta}
        else:
            return {"status": "unavailable", "plot_id": req.plot_id, "message": "Could not fetch satellite tile."}
    except Exception as e:
        return {"status": "error", "plot_id": req.plot_id, "error": str(e)}

@app.post("/v2/satellite-vision")
def api_satellite_vision(req: SatelliteTileRequest):
    """Run LLM vision analysis on a cached satellite tile."""
    try:
        from layer0.perception.satellite_rgb.tile_runtime import get_cached_tile
        from layer0.perception.satellite_rgb.llm_vision import analyze_tile, _CIRCUIT_TRIPPED_AT
        import layer0.perception.satellite_rgb.llm_vision as llm_mod

        # Force reset circuit breaker on each call (it was tripped from stale session)
        llm_mod._CIRCUIT_TRIPPED_AT = None

        image_bytes = get_cached_tile(req.plot_id)
        if not image_bytes:
            return {"status": "no_tile", "plot_id": req.plot_id, "message": "No cached tile. Call /v2/satellite-tile first."}

        print(f"[VISION_API] Running vision on {len(image_bytes)} bytes for plot {req.plot_id}")
        result = analyze_tile(image_bytes=image_bytes, plot_context={"region": "Algeria"})

        if result:
            vision_dict = {
                "crop_rows_detected": result.crop_rows_detected,
                "estimated_crop_type": result.estimated_crop_type,
                "vegetation_pct": result.vegetation_pct,
                "bare_soil_pct": result.bare_soil_pct,
                "emergence_stage": result.emergence_stage,
                "weed_pressure": result.weed_pressure,
                "confidence": result.confidence,
                "field_uniformity": result.field_uniformity,
                "irrigation_visible": result.irrigation_visible,
                "explanation": result.raw_explanation,
            }

            # Cache for orchestrator cross-pipeline access
            from layer0.perception.satellite_rgb.tile_runtime import cache_vision_result
            cache_vision_result(req.plot_id, vision_dict)

            return {
                "status": "analyzed", "plot_id": req.plot_id,
                "vision": vision_dict,
            }
        else:
            return {"status": "vision_unavailable", "plot_id": req.plot_id, "message": "LLM vision analysis failed or rate-limited."}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "plot_id": req.plot_id, "error": str(e)}

@app.get("/v2/satellite-tile-image/{plot_id}")
def api_satellite_tile_image(plot_id: str):
    """Serve the cached satellite tile as a PNG image."""
    from fastapi.responses import Response
    try:
        from layer0.perception.satellite_rgb.tile_runtime import get_cached_tile, get_tile_metadata
        image_bytes = get_cached_tile(plot_id)
        if not image_bytes:
            raise HTTPException(status_code=404, detail="No cached tile for this plot")
        meta = get_tile_metadata(plot_id) or {}
        return Response(
            content=image_bytes,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=604800",  # 7 days
                "X-Tile-Source": meta.get("source", "sentinel-2-l2a"),
                "X-Tile-Date": meta.get("fetched_date", ""),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v2/satellite-tile-meta/{plot_id}")
def api_satellite_tile_meta(plot_id: str):
    """Get metadata about a cached satellite tile."""
    try:
        from layer0.perception.satellite_rgb.tile_runtime import get_tile_metadata, _is_cache_valid
        meta = get_tile_metadata(plot_id)
        if not meta:
            return {"exists": False, "plot_id": plot_id}
        return {
            "exists": True,
            "plot_id": plot_id,
            "fresh": _is_cache_valid(plot_id),
            **meta,
        }
    except Exception as e:
        return {"exists": False, "plot_id": plot_id, "error": str(e)}


# ============================================================================
# /v2/plot-intelligence  Unified Dashboard Data Endpoint
# ============================================================================
# Single endpoint that collects ALL intelligence for the plot overview.
# The frontend calls this ONCE. AgriBrain handles all data collection.
# ============================================================================

class PlotIntelligenceRequest(BaseModel):
    """Request for plot intelligence data."""
    lat: float = 36.0
    lng: float = 3.0
    crop: Optional[str] = "generic"
    polygon: Optional[Any] = None
    expert_mode: bool = False
    days_past: int = 7
    days_future: int = 7
    plant_date: Optional[str] = None        # ISO date string (e.g. "2026-03-15")
    crop_stage_label: Optional[str] = None  # Human label from DB crop cycle
    force_refresh_weather: bool = False
    # GAP 2: User-declared ground truth from frontend
    irrigation_type: Optional[str] = None   # "Drip", "Sprinkler", "Rainfed", etc.
    soil_type: Optional[str] = None         # "Sandy", "Loam", "Clay", etc.
    soil_analysis: Optional[Dict] = None    # Lab results: {ph, nitrogen_ppm, ...}
    physical_constraints: Optional[List[str]] = None  # ["Slope present", "Salinity"]
    area_ha: Optional[float] = None         # Real plot area in hectares
    # GAP SENSOR: Live IoT field telemetry from DB
    sensor_readings: Optional[List[Dict]] = None  # [{device_id, type, latest: {temperature, soil_moisture, ...}}]


@app.post("/v2/plot-intelligence")
def api_plot_intelligence(req: PlotIntelligenceRequest):
    """
    Unified Plot Intelligence Endpoint.
    Delegates data fetching & timeline to pi_helpers for testability.
    """
    import traceback
    from datetime import timezone
    from app.pi_helpers import fetch_all_sources, build_timeline, compute_phenology, hargreaves_et0 as _hargreaves_et0
    
    lat, lng = req.lat, req.lng
    now = datetime.now(timezone.utc)
    now_str = now.isoformat()

    # ---- Data Collection (delegated to pi_helpers) ----
    results = fetch_all_sources(lat, lng, req.days_past, req.days_future)

    weather_data  = results.get("weather")
    forecast_data = results.get("forecast")
    indices_data  = results.get("indices")
    sar_ts_data   = results.get("sar_ts")
    sar_data      = results.get("sar")
    soil_data     = results.get("soil")
    water_data    = results.get("water")
    hist_weather  = results.get("hist")
    ndvi_ts       = results.get("ndvi_ts")

    # ---- GAP 2: Override SoilGrids with user-declared lab data ----
    user_soil_override = False
    if req.soil_analysis and isinstance(req.soil_analysis, dict):
        has_values = any(v is not None and v != 0 for k, v in req.soil_analysis.items() if k != "sample_date")
        if has_values:
            user_soil_override = True
            # Merge user lab data into soil_data (overrides SoilGrids proxy)
            if not soil_data or not isinstance(soil_data, dict):
                soil_data = {}
            soil_data["user_declared"] = True
            soil_data["is_generic_fallback"] = False  # User data is NOT a fallback
            for k, v in req.soil_analysis.items():
                if v is not None:
                    soil_data[k] = v
            print(f"[PI] Using user-declared soil analysis (overrides SoilGrids)")

    # Attach irrigation/management context for engine use
    user_irrigation = req.irrigation_type
    user_soil_type = req.soil_type
    user_constraints = req.physical_constraints or []
    user_area_ha = req.area_ha

    # ---- GAP SENSOR: Process live IoT sensor telemetry ----
    sensor_context = {
        "count": 0,
        "active": 0,
        "types": [],
        "soil_moisture_pct": None,
        "soil_ec_ds_m": None,
        "field_temperature_c": None,
        "field_humidity_pct": None,
        "field_wind_speed_ms": None,
        "field_rainfall_mm": None,
        "data_source": "none",
    }
    if req.sensor_readings and isinstance(req.sensor_readings, list):
        sensor_context["count"] = len(req.sensor_readings)
        active_sensors = [s for s in req.sensor_readings if s.get("status") == "ACTIVE"]
        sensor_context["active"] = len(active_sensors)
        sensor_context["types"] = list(set(s.get("type", "") for s in req.sensor_readings))

        for sr in req.sensor_readings:
            latest = sr.get("latest", {})
            if not latest:
                continue
            sr_type = sr.get("type", "")

            # Soil moisture sensor  override satellite proxy
            if sr_type == "MOISTURE" and latest.get("soil_moisture") is not None:
                sensor_context["soil_moisture_pct"] = latest["soil_moisture"]
                sensor_context["data_source"] = "field_sensor"
                print(f"[PI] Sensor soil moisture: {latest['soil_moisture']}% (overrides satellite proxy)")

            # EC sensor  salinity context
            if sr_type == "EC" and latest.get("ec") is not None:
                sensor_context["soil_ec_ds_m"] = latest["ec"]
                print(f"[PI] Sensor EC: {latest['ec']} dS/m")

            # Weather station  supplement/override remote weather
            if sr_type == "WEATHER":
                if latest.get("temperature") is not None:
                    sensor_context["field_temperature_c"] = latest["temperature"]
                if latest.get("humidity") is not None:
                    sensor_context["field_humidity_pct"] = latest["humidity"]
                if latest.get("wind_speed") is not None:
                    sensor_context["field_wind_speed_ms"] = latest["wind_speed"]
                if latest.get("rainfall") is not None:
                    sensor_context["field_rainfall_mm"] = latest["rainfall"]
                sensor_context["data_source"] = "field_sensor"
                print(f"[PI] Field weather station active: T={latest.get('temperature')}C, H={latest.get('humidity')}%")

            # Temp sensor  field temperature
            if sr_type in ("TEMP", "MOISTURE") and latest.get("temperature") is not None:
                if sensor_context["field_temperature_c"] is None:
                    sensor_context["field_temperature_c"] = latest["temperature"]

        print(f"[PI] Sensor context: {sensor_context['active']}/{sensor_context['count']} active, types={sensor_context['types']}")


    # ---- Build Timeline (delegated to pi_helpers) ----
    timeline, ndvi_records, hist_records, forecast_records = build_timeline(
        results, lat, req.days_past, req.days_future
    )

    # Derive real statuses from actual data presence
    temp_str = ""
    if weather_data and isinstance(weather_data, dict):
        t = weather_data.get("temperature", {})
        if isinstance(t, dict):
            temp_str = f"{t.get('current', '--')}C, Humidity {weather_data.get('humidity', '--')}%, Wind {weather_data.get('wind', {}).get('speed_ms', '--')} m/s"
        else:
            temp_str = f"{t}C" if t else "Active"

    ndvi_val = indices_data.get("ndvi", 0) if indices_data else 0
    evi_val = indices_data.get("evi", 0) if indices_data else 0

    sources_active = sum(1 for x in [weather_data, indices_data, sar_data] if x)

    # GAP SENSOR: Count field sensors as an additional data source
    has_active_sensors = sensor_context["active"] > 0
    if has_active_sensors:
        sources_active += 1  # Field sensors count as a source

    # Derive today's ET0 from water balance records
    today_str = now.strftime("%Y-%m-%d")
    et0_today = 0.0
    if water_data and isinstance(water_data, dict):
        for rec in water_data.get("records", []):
            if rec.get("date") == today_str:
                et0_today = rec.get("et0") or 0.0
                break
        if et0_today == 0.0:
            # fallback: last historical record
            hist_recs = [r for r in water_data.get("records", []) if r.get("type") == "historical"]
            if hist_recs:
                et0_today = hist_recs[-1].get("et0") or 0.0

    # Biotic risk from weather (temp 20-30C + humidity >70% = high risk window)
    biotic_status = "Low"
    biotic_detail = "Low risk"
    temp_now = 15.0
    hum_now = 50
    if weather_data:
        temp_now = weather_data.get("temperature", {}).get("current", 15) if isinstance(weather_data.get("temperature"), dict) else 15
        hum_now = weather_data.get("humidity", 50)

    # GAP SENSOR: Field sensor temp/humidity override remote API (higher accuracy)
    if sensor_context.get("field_temperature_c") is not None:
        temp_now = sensor_context["field_temperature_c"]
        print(f"[PI] Using field sensor temperature: {temp_now}C (overrides remote API)")
    if sensor_context.get("field_humidity_pct") is not None:
        hum_now = sensor_context["field_humidity_pct"]
        print(f"[PI] Using field sensor humidity: {hum_now}% (overrides remote API)")

    if 20 <= temp_now <= 32 and hum_now >= 70:
        biotic_status = "High"
        biotic_detail = f"High: T={temp_now:.1f}C, RH={hum_now}%"
    elif 15 <= temp_now <= 32 and hum_now >= 55:
        biotic_status = "Moderate"
        biotic_detail = f"Moderate: T={temp_now:.1f}C, RH={hum_now}%"
    else:
        biotic_detail = f"Low: T={temp_now:.1f}C, RH={hum_now}%"
    
    # Tag data source for biotic risk
    if sensor_context.get("field_temperature_c") is not None or sensor_context.get("field_humidity_pct") is not None:
        biotic_detail += " [field sensor]"
            
    # Hargreaves ET0 Fallback -- use real temp extremes when available
    et0_is_fallback = False
    if et0_today == 0.0:
        et0_is_fallback = True
        if weather_data and isinstance(weather_data, dict):
            t_info = weather_data.get("temperature", {})
            t_max = t_info.get("max")
            t_min = t_info.get("min")
            # Only use synthetic as absolute last resort
            if t_max is None:
                t_max = temp_now + 5
            if t_min is None:
                t_min = temp_now - 5
        else:
            t_max = temp_now + 5
            t_min = temp_now - 5
            
        doy = now.timetuple().tm_yday
        et0_today = _hargreaves_et0(t_max, t_min, lat, doy)

    # Extract explicit rain probability for L0 expert mode
    rain_prob_today = 0
    if forecast_records and len(forecast_records) > 0:
        rain_prob_today = forecast_records[0].get("rain_prob", 0)

    # L4 Soil Fallback Logic (respects user-declared override)
    is_fallback = soil_data.get('is_generic_fallback') if isinstance(soil_data, dict) else False
    if user_soil_override:
        proxy_reason = "User Lab Analysis (Ground Truth)"
        conf_mod = 1.2  # Highest confidence  real lab data
        is_fallback = False
    elif is_fallback:
        proxy_reason = "Assumed Baseline (No Satellite Coverage)"
        conf_mod = 0.1
    else:
        proxy_reason = "Unverified Proxy (SoilGrids Global Model)"
        conf_mod = 1.0

    wind_str = f"{weather_data.get('wind', {}).get('speed_ms', '--')} m/s" if weather_data else "--"

    # ---- Helper functions for REAL computed values (no synthetic data) ----

    def _compute_canopy_cover(ndvi):
        """Beer-Lambert canopy cover from NDVI via LAI inversion.
        CC = 1 - exp(-k * LAI), where LAI ~ -ln(1 - NDVI) / 0.5 for k=0.5
        This is a physically-based conversion, not a linear fabrication."""
        import math
        if not ndvi or ndvi <= 0:
            return 0.0
        ndvi_c = min(max(ndvi, 0.01), 0.95)  # Clamp to avoid log(0)
        lai = -math.log(1.0 - ndvi_c) / 0.5
        cc = (1.0 - math.exp(-0.5 * lai)) * 100.0
        return round(min(cc, 99.0), 1)

    def _compute_spatial_variability(sar_ts, ndvi_timeseries):
        """Compute spatial variability from SAR temporal coefficient of variation.
        Returns 'Low', 'Moderate', or 'High' based on actual data spread."""
        if sar_ts and isinstance(sar_ts, dict):
            ts_list = sar_ts.get("timeseries", [])
            if ts_list and len(ts_list) >= 3:
                vv_vals = [e.get("vv_db") for e in ts_list if e.get("vv_db") is not None]
                if len(vv_vals) >= 3:
                    mean_vv = sum(vv_vals) / len(vv_vals)
                    if mean_vv != 0:
                        std_vv = (sum((v - mean_vv) ** 2 for v in vv_vals) / len(vv_vals)) ** 0.5
                        cv = abs(std_vv / mean_vv)
                        if cv > 0.15:
                            return "High"
                        elif cv > 0.08:
                            return "Moderate"
                        return "Low"
        # NDVI timeseries fallback
        if ndvi_timeseries and isinstance(ndvi_timeseries, dict):
            obs = ndvi_timeseries.get("data", [])
            if obs and len(obs) >= 3:
                vals = [e.get("ndvi") for e in obs if e.get("ndvi") is not None]
                if len(vals) >= 3:
                    mean_n = sum(vals) / len(vals)
                    if mean_n > 0:
                        std_n = (sum((v - mean_n) ** 2 for v in vals) / len(vals)) ** 0.5
                        cv = std_n / mean_n
                        if cv > 0.2:
                            return "High"
                        elif cv > 0.1:
                            return "Moderate"
                        return "Low"
        return "Unknown (insufficient data)"

    def _build_fusion_summary(wx, optical, sar):
        """Build an accurate fusion summary listing only sources that are actually present."""
        sources = []
        if optical:
            sources.append("satellite imagery (Sentinel-2)")
        if sar:
            sources.append("SAR radar (Sentinel-1)")
        if wx:
            sources.append("local weather")
        if len(sources) == 0:
            return "No data sources currently available. Awaiting satellite passes and weather feeds."
        elif len(sources) == 1:
            return f"Currently operating on {sources[0]} only. Other sources are temporarily unavailable."
        else:
            merged = ", ".join(sources[:-1]) + f" and {sources[-1]}"
            return f"Successfully merged {merged}."

    def _compute_yield_class(ndvi, has_indices, has_weather, biotic_risk):
        """Compute yield potential with honest confidence based on data availability."""
        if not ndvi or ndvi <= 0:
            return "Unknown", 0.1, "Insufficient data for yield estimation"
        cls = "High" if ndvi > 0.65 else "Moderate" if ndvi > 0.4 else "Low"
        # Confidence depends on data quality, not hardcoded
        conf = 0.3  # Base: NDVI-only proxy is low confidence
        reason = "NDVI empirical proxy only"
        if has_indices:
            conf += 0.25
            reason = "S2 NDVI direct observation"
        if has_weather:
            conf += 0.15
            reason += " + weather context"
        if biotic_risk == "High":
            cls = "Moderate" if cls == "High" else cls
            conf -= 0.1
            reason += " (downgraded: biotic pressure)"
        return cls, round(min(conf, 0.85), 2), reason

    # Engine card builder helper
    def _engine(id, name, icon, status, value, detail, expert_data=None):
        card = {
            "id": id, "name": name, "icon": icon,
            "status": status, "value": value, "detail": detail,
            # 'summary' always present so test assertions pass
            "summary": (expert_data or {}).get("farmer_summary") or detail or value,
            # 'data' always present for frontend consumption
            "data": expert_data or {},
        }
        if req.expert_mode and expert_data:
            card["expert"] = expert_data
        return card

    engines = [
        _engine("L0", "Environment & Weather", "",
                "OK" if weather_data else "DEGRADED",
                temp_str or "No data",
                temp_str or "Awaiting weather data",
                {
                    "weather": weather_data, 
                    "data_freshness": "Live", 
                    "rain_prob": rain_prob_today, 
                    "temp_current": temp_now, 
                    "et0_today": et0_today,
                    "farmer_summary": f"Currently {temp_now:.1f}C with {rain_prob_today}% chance of rain. Weather data is updating live." if weather_data else "Awaiting live weather stream.",
                    "why_it_matters": "Real-time microclimate data drives all other agronomic models, from disease pressure to evapotranspiration.",
                    "expert_metrics": [
                        {"name": "Temperature", "value": f"{temp_now:.1f}C", "confidence": 0.95 if weather_data else 0.0, "reason": "Live API feed"},
                        {"name": "Humidity", "value": f"{hum_now}%", "confidence": 0.95 if weather_data else 0.0, "reason": "Live API feed"},
                        {"name": "Wind Speed", "value": f"{wind_str}", "confidence": 0.95 if weather_data else 0.0, "reason": "Live API feed"},
                        {"name": "Rain Probability", "value": f"{rain_prob_today}%", "confidence": 0.85 if forecast_records else 0.0, "reason": "NWP Forecast Model"},
                    ]
                }),
        _engine("L1", "Data Fusion", "Link",
                "OK" if sources_active >= 2 else "DEGRADED",
                "Multi-Source Fusion",
                f"{sources_active}/{4 if has_active_sensors else 3} sources active",
                {
                    "sources": {"weather": bool(weather_data), "optical": bool(indices_data), "sar": bool(sar_data), "field_sensors": has_active_sensors},
                    "sources_active": sources_active,
                    "farmer_summary": _build_fusion_summary(weather_data, indices_data, sar_data) + (" Field sensors are providing live ground-truth data." if has_active_sensors else ""),
                    "why_it_matters": "Combining multiple data sources reduces the error margin of any single sensor and bridges gaps during cloudy days.",
                    "expert_metrics": [
                        {"name": "Optical (S2)", "value": "Active" if indices_data else "Missing", "confidence": 0.9 if indices_data else 0.1, "reason": "Sentinel-2 L2A BOA Reflectance" if indices_data else "Cloud occlusion or gap"},
                        {"name": "Radar (S1)", "value": "Active" if sar_data else "Missing", "confidence": 0.85 if sar_data else 0.1, "reason": "Sentinel-1 GRD VV/VH" if sar_data else "Acquisition gap"},
                        {"name": "Weather", "value": "Active" if weather_data else "Missing", "confidence": 0.95 if weather_data else 0.1, "reason": "OpenMeteo Agronomic API" if weather_data else "API unreachable"},
                        {"name": "Field Sensors", "value": f"{sensor_context['active']} active" if has_active_sensors else "None", "confidence": 0.95 if has_active_sensors else 0.0, "reason": f"IoT ({', '.join(sensor_context['types'])})" if has_active_sensors else "No sensors registered"},
                    ]
                }),
        _engine("L2", "Vegetation Intelligence", "",
                "OK" if indices_data else "DEGRADED",
                "Active" if indices_data else "Estimated",
                f"NDVI {ndvi_val:.2f}, EVI {evi_val:.2f}" if indices_data else f"Estimated NDVI {ndvi_val:.2f} (no recent satellite pass)",
                {
                    "ndvi": ndvi_val, "evi": evi_val, "ndvi_mean": ndvi_val, 
                    "canopy_cover_pct": _compute_canopy_cover(ndvi_val),
                    "spatial_variability": _compute_spatial_variability(sar_ts_data, ndvi_ts),
                    "ndmi": indices_data.get("ndmi") if indices_data else None,
                    "ndwi": indices_data.get("ndwi") if indices_data else None,
                    "farmer_summary": f"Crop canopy is developing well with an NDVI of {ndvi_val:.2f}." if ndvi_val > 0.4 else f"Crop canopy is sparse or emerging (NDVI {ndvi_val:.2f}).",
                    "why_it_matters": "NDVI is the core indicator of plant vigor and photosynthetic capacity, directly driving yield potential.",
                    "expert_metrics": [
                        {"name": "Mean NDVI", "value": f"{ndvi_val:.2f}", "confidence": 0.9 if indices_data else 0.4, "reason": "Direct S2 observation" if indices_data else "No recent satellite pass"},
                        {"name": "Canopy Cover", "value": f"{_compute_canopy_cover(ndvi_val)}%", "confidence": 0.65 if indices_data else 0.3, "reason": "Beer-Lambert LAI inversion (k=0.5)"},
                        {"name": "Moisture (NDMI)", "value": f"{indices_data.get('ndmi', 0):.2f}" if indices_data and indices_data.get('ndmi') else "N/A", "confidence": 0.9 if indices_data and indices_data.get('ndmi') else 0.0, "reason": "Direct S2 observation" if indices_data and indices_data.get('ndmi') else "Requires SWIR bands, missing"},
                    ]
                }),
        _engine("L3", "Water Stress Engine", "",
                "OK" if water_data else "DEGRADED",
                "PM-Full" if water_data else "Hargreaves Fallback",
                f"ET0 {et0_today:.1f} mm/day" if water_data else f"ET0 {et0_today:.1f} mm/day (Awaiting PM model)",
                {
                    "et0_today": et0_today,
                    "deficit_mm": water_data.get("summary", {}).get("final_deficit_mm") if water_data else None,
                    "stress_index": water_data.get("summary", {}).get("stress_index") if water_data else None,
                    "farmer_summary": f"Your crop has a water deficit of {abs(water_data.get('summary', {}).get('final_deficit_mm') or 0):.1f}mm." if water_data and (water_data.get("summary", {}).get("final_deficit_mm") or 0) < -5 else "Soil moisture levels are adequate, no significant water stress detected.",
                    "why_it_matters": "Precise evapotranspiration tracking prevents both yield-destroying drought stress and wasteful over-irrigation.",
                    "expert_metrics": [
                        {"name": "Daily ET0", "value": f"{et0_today:.1f} mm", "confidence": 0.85 if water_data else 0.6, "reason": "Penman-Monteith full model" if water_data else "Hargreaves-Samani fallback"},
                        {"name": "Root Zone Deficit", "value": f"{(water_data.get('summary', {}).get('final_deficit_mm') or 0):.1f} mm", "confidence": 0.8 if water_data else 0.3, "reason": "Continuous daily mass balance"},
                        {"name": "Stress Index (Ks)", "value": f"{(water_data.get('summary', {}).get('stress_index') or 0):.2f}", "confidence": 0.75 if water_data else 0.2, "reason": "Soil water depletion fraction"},
                    ]
                }),
        _engine("L4", "Nutrient Analysis", "",
                "OK" if (soil_data and isinstance(soil_data, dict) and not is_fallback) else "DEGRADED",
                "Assumed Baseline" if is_fallback else ("SoilGrids Proxy" if soil_data else "No soil data"),
                f"pH {soil_data.get('ph', '--')} | {soil_data.get('texture_class', '').capitalize()} | OC {soil_data.get('organic_carbon', '--')} g/kg" if soil_data and isinstance(soil_data, dict) else "Awaiting soil data",
                {
                    **(soil_data or {}),
                    "farmer_summary": f"{'WARNING: This field is in a region with no satellite soil coverage. We are using standard generic baseline assumptions.' if is_fallback else ''} Your soil texture is {soil_data.get('texture_class', 'unknown')} ({soil_data.get('sand', '--')}% sand, {soil_data.get('silt', '--')}% silt, {soil_data.get('clay', '--')}% clay). This indicates its water holding capacity and base drainage. The baseline pH is {soil_data.get('ph', '--')}, with an estimated {soil_data.get('organic_carbon', '--')} g/kg of organic carbon. Note: This is an unverified estimate, not a physical lab test." if soil_data and isinstance(soil_data, dict) else "We lack physical soil data for this field.",
                    "why_it_matters": "Base soil characteristics determine nutrient retention (CEC), fertilizer efficiency, and water holding capacity.",
                    "expert_metrics": [
                        {"name": "Soil pH (H2O)", "value": str(soil_data.get('ph', '--')) if soil_data and isinstance(soil_data, dict) else "N/A", "confidence": 0.35 * conf_mod if soil_data else 0.0, "reason": proxy_reason},
                        {"name": "Total Nitrogen", "value": f"{soil_data.get('nitrogen', '--')} g/kg" if soil_data and isinstance(soil_data, dict) else "N/A", "confidence": 0.30 * conf_mod if soil_data else 0.0, "reason": proxy_reason},
                        {"name": "Organic Carbon", "value": f"{soil_data.get('organic_carbon', '--')} g/kg" if soil_data and isinstance(soil_data, dict) else "N/A", "confidence": 0.40 * conf_mod if soil_data else 0.0, "reason": proxy_reason},
                        {"name": "CEC", "value": f"{soil_data.get('cec', '--')} meq/100g" if soil_data and isinstance(soil_data, dict) else "N/A", "confidence": 0.35 * conf_mod if soil_data else 0.0, "reason": proxy_reason},
                        {"name": "Bulk Density", "value": f"{soil_data.get('bdod', '--')} g/cm" if soil_data and isinstance(soil_data, dict) else "N/A", "confidence": 0.45 * conf_mod if soil_data else 0.0, "reason": proxy_reason},
                        {"name": "Clay %", "value": f"{soil_data.get('clay', '--')}%" if soil_data and isinstance(soil_data, dict) else "N/A", "confidence": 0.50 * conf_mod if soil_data else 0.0, "reason": proxy_reason},
                        {"name": "Sand %", "value": f"{soil_data.get('sand', '--')}%" if soil_data and isinstance(soil_data, dict) else "N/A", "confidence": 0.50 * conf_mod if soil_data else 0.0, "reason": proxy_reason},
                        {"name": "Silt %", "value": f"{soil_data.get('silt', '--')}%" if soil_data and isinstance(soil_data, dict) else "N/A", "confidence": 0.50 * conf_mod if soil_data else 0.0, "reason": proxy_reason},
                    ]
                }),
        _engine("L5", "Biotic Pressure", "",
                "OK" if weather_data else "DEGRADED",
                f"{biotic_status} Risk" if weather_data else "No data",
                biotic_detail,
                {
                    "risk_level": biotic_status, "temp": temp_now, "humidity": hum_now,
                    "farmer_summary": f"Current weather (Temp: {temp_now:.1f}C, Humidity: {hum_now}%) creates a {biotic_status.lower()} risk for fungal infections." if weather_data else "Unable to calculate fungal risk due to missing weather data.",
                    "why_it_matters": "Fungal pathogens require specific temperature and leaf wetness windows to sporulate and infect.",
                    "expert_metrics": [
                        {"name": "Infection Risk", "value": biotic_status, "confidence": 0.55 if weather_data else 0.15, "reason": "Simplified Temp/RH threshold (not crop-specific disease model)" if weather_data else "Missing microclimate data"},
                        {"name": "Leaf Wetness Proxy", "value": f"{hum_now}% RH", "confidence": 0.5 if weather_data else 0.1, "reason": "RH proxy (no actual leaf wetness sensor)"},
                        {"name": "Temp Window", "value": f"{temp_now:.1f}C", "confidence": 0.95 if weather_data else 0.3, "reason": "Optimal fungal growth is 20-30C"},
                    ]
                }),
    ]

    # ---- Assimilation ----
    sources_used = [
        s for s in [
            weather_data and "OpenMeteo",
            indices_data and "Sentinel-2",
            sar_data and "Sentinel-1-SAR",
            sar_ts_data and "Sentinel-1-SAR-TS",
            water_data and "Water-Balance",
            soil_data and "SoilGrids-ISRIC",
            forecast_data and "Weather-Forecast",
        ] if s
    ]

    # ---- GAP B: Real L6-L9 engine cards ----
    # Compute now so L9 can reference sources_used
    _wb_summary = water_data.get("summary", {}) if water_data and isinstance(water_data.get("summary"), dict) else {}
    _deficit = _wb_summary.get("final_deficit_mm") or 0.0
    _stress_idx = _wb_summary.get("stress_index") or 0.0
    _yield_class, _yield_conf, _yield_reason = _compute_yield_class(ndvi_val, bool(indices_data), bool(weather_data), biotic_status)
    _nlg_ok = bool(os.getenv("OPENROUTER_API_KEY"))

    _l6 = _engine(
        "L6", "Yield Estimation", "",
        "OK" if indices_data else "DEGRADED",
        f"NDVI {ndvi_val:.2f}  {_yield_class} potential",
        f"Estimated yield potential: {_yield_class} (NDVI {ndvi_val:.2f}). Refine with area + crop Kc data.",
        {
            "ndvi": ndvi_val, "yield_class": _yield_class.upper(), "basis": "NDVI-proxy",
            "farmer_summary": f"Based on current vegetative health, your crop is on track for a {_yield_class.lower()} yield." if ndvi_val else "Not enough data to project final yield.",
            "why_it_matters": "Early yield projection allows for mid-season course corrections (e.g., late nitrogen application).",
            "expert_metrics": [
                {"name": "Yield Potential", "value": _yield_class, "confidence": _yield_conf, "reason": _yield_reason},
                {"name": "Biomass Proxy", "value": f"{ndvi_val:.2f} NDVI", "confidence": 0.85 if indices_data else 0.35, "reason": "Direct proxy for LAI" if indices_data else "No direct satellite observation"},
            ]
        },
    )

    if _deficit < -20:
        _l7_label = "Irrigate: deficit detected"
        _l7_summary = f"Deficit {abs(_deficit):.0f}mm  schedule irrigation this week"
        _l7_farmer = f"Your field has lost {abs(_deficit):.0f}mm of water. We highly recommend scheduling an irrigation event soon to avoid yield loss."
    elif biotic_status == "High":
        _l7_label = "Scout field: biotic risk elevated"
        _l7_summary = f"Biotic risk {biotic_status.lower()}  scout for disease/pest signs"
        _l7_farmer = "Weather conditions are perfect for fungal disease. Please walk the field and inspect lower leaves for early signs of infection."
    else:
        _l7_label = "Monitor: conditions stable"
        _l7_summary = "No urgent interventions required this week"
        _l7_farmer = "Conditions are stable. No urgent interventions are required for irrigation or crop protection at this time."

    _l7 = _engine(
        "L7", "Planning & Calendar", "",
        "OK" if water_data else "DEGRADED",
        _l7_label, _l7_summary,
        {
            "water_deficit_mm": _deficit if _wb_summary else None, "biotic_risk": biotic_status,
            "farmer_summary": _l7_farmer,
            "why_it_matters": "A prioritized task list prevents critical timing errors in irrigation or fungicide application.",
            "expert_metrics": [
                {"name": "Primary Intervention", "value": _l7_label.split(":")[0], "confidence": 0.7 if water_data else 0.4, "reason": "Rule-based triage (decision tree, not a planning model)"},
                {"name": "Action Window", "value": "24-48 Hours" if "Irrigate" in _l7_label or "Scout" in _l7_label else "Next 7 Days", "confidence": 0.6 if forecast_data else 0.3, "reason": "Based on forecast" if forecast_data else "No forecast for timing"},
            ]
        },
    )

    if _deficit < -10:
        _l8_label = "Irrigation prescription ready"
        _l8_summary = f"Apply {abs(_deficit):.0f}mm irrigation (stress index {_stress_idx:.2f})"
        _l8_type = "IRRIGATION"
        _l8_farmer = f"Based on water balance, your field needs approximately {abs(_deficit):.0f}mm of irrigation."
    else:
        _l8_label = "Monitoring prescription active"
        _l8_summary = f"No urgent prescription. NDVI {ndvi_val:.2f} stable."
        _l8_type = "MONITOR"
        _l8_farmer = "No spatial prescription map is currently required. Maintain standard monitoring protocols."

    _l8 = _engine(
        "L8", "Prescriptive Actions", "",
        "OK" if (water_data or indices_data) else "DEGRADED",
        _l8_label, _l8_summary,
        {
            "prescription_type": _l8_type,
            "farmer_summary": _l8_farmer,
            "why_it_matters": "Translates agronomic analysis into actionable field-level recommendations.",
            "expert_metrics": [
                {"name": "Action Type", "value": _l8_type, "confidence": 0.7 if water_data else 0.3, "reason": "Derived from L3 water balance" if water_data else "Insufficient data"},
                {"name": "VRA Map", "value": "Not available", "confidence": 0.0, "reason": "Variable-rate application maps not yet implemented"},
            ]
        },
    )

    _l9 = _engine(
        "L9", "Interface & NLG", "",
        "OK" if _nlg_ok else "DEGRADED",
        "LLM online" if _nlg_ok else "LLM offline (no API key)",
        f"Natural language generation {'active' if _nlg_ok else 'degraded'}. "
        f"{len(sources_used)} data source{'s' if len(sources_used) != 1 else ''} wired into advisor context.",
        {
            "llm_available": _nlg_ok, "sources_in_context": len(sources_used),
            "farmer_summary": "AgriBrain Chat is fully loaded with your field's exact data. You can ask it to explain any of these insights in detail.",
            "why_it_matters": "A conversational interface allows you to query complex agronomic data without needing to interpret charts yourself.",
            "expert_metrics": [
                {"name": "LLM Engine", "value": os.getenv("OPENROUTER_MODEL", "openrouter/auto"), "confidence": 1.0 if _nlg_ok else 0.0, "reason": "OpenRouter API" if _nlg_ok else "No API key configured"},
                {"name": "Context Sources", "value": f"{len(sources_used)} active", "confidence": min(1.0, len(sources_used) / 5.0), "reason": "Active data feeds wired to advisor"},
                {"name": "Reasoning Mode", "value": "Enabled" if _nlg_ok else "Disabled", "confidence": 1.0 if _nlg_ok else 0.0, "reason": "Chain-of-thought routing"},
            ]
        },
    )

    engines.extend([_l6, _l7, _l8, _l9])
    
    # Compute real L10 quality from actual pipeline data
    _l10_gates = [
        bool(weather_data),          # G1: Weather online
        bool(forecast_data),         # G2: Forecast available
        bool(indices_data),          # G3: Optical indices
        bool(sar_data),              # G4: SAR data
        bool(soil_data),             # G5: Soil properties
        bool(water_data),            # G6: Water balance
        bool(hist_weather),          # G7: Historical weather
        bool(ndvi_ts),               # G8: NDVI timeseries
        len(ndvi_records) > 0,       # G9: Kalman output
        et0_today > 0,               # G10: ET0 computed
        sources_active >= 2,         # G11: Multi-source fusion
        not is_fallback,             # G12: Real soil (not generic)
        has_active_sensors,          # G13: Field sensor telemetry
    ]
    _l10_passed = sum(_l10_gates)
    _l10_quality = round(_l10_passed / len(_l10_gates), 3)
    _l10_mode = "NORMAL" if _l10_quality >= 0.7 else ("DEGRADED" if _l10_quality >= 0.4 else "CRITICAL")
    l10_data = {
        "overall_quality_score": _l10_quality,
        "hard_gates_passed": _l10_passed,
        "total_gates": len(_l10_gates),
        "spatial_anomaly_trustworthy": ndvi_val > 0.2,
        "degradation_mode": _l10_mode,
    }
    engines.append(_engine("L10", "SIRE Orchestrator", "",
                           "OK" if _l10_quality >= 0.7 else "DEGRADED", _l10_mode,
                           f"{_l10_passed}/{len(_l10_gates)} quality gates passed", l10_data))

    try:
        from layer10_sire.packetizer import enrich_engines_with_explainability
        engines = enrich_engines_with_explainability(engines)
    except Exception as e:
        print(f"[PI] Failed to enrich engines: {e}")

    assimilation = {
        "dataAge_days": 0,
        "sources_used": sources_used,
        "sources_count": len(sources_used),
        "freshness_score": min(1.0, len(sources_used) / 6.0),
        "assimilated": len(sources_used) >= 2,
        "raw_available": req.expert_mode,
    }

    # Crop phenology (delegated to pi_helpers)
    crop_phenology = compute_phenology(req.plant_date, req.crop_stage_label, ndvi_val)

    # ---- Response ----
    response = {
        "success": True,
        "timestamp": now_str,
        "timeline": timeline,
        "engines": engines,
        "current": {
            "weather": weather_data,
            "indices": indices_data,
            "soil": soil_data,
            "waterBalance": water_data,
        },
        "assimilation": assimilation,
        "crop_phenology": crop_phenology,
        # GAP 2: User-declared management context (from DB  proxy  here)
        "user_inputs": {
            "irrigation_type": user_irrigation,
            "soil_type": user_soil_type,
            "soil_analysis": req.soil_analysis if user_soil_override else None,
            "soil_source": proxy_reason,
            "physical_constraints": user_constraints,
            "area_ha": user_area_ha,
        },
        # GAP SENSOR: Live field sensor telemetry context
        "sensor_context": sensor_context,
    }

    # ---- Expert Raw Data ----
    if req.expert_mode:
        response["rawData"] = {
            "weather_raw": weather_data,
            "forecast_raw": forecast_data,
            "sentinel2_raw": indices_data,
            "sentinel1_raw": sar_data,
            "sar_timeseries": sar_ts_data,
            "soilgrids_raw": soil_data,
            "water_balance_raw": water_data,
            "historical_weather": hist_weather,
            "user_soil_analysis": req.soil_analysis if user_soil_override else None,
            "sensor_readings_raw": req.sensor_readings or [],
        }

    return response

@app.post("/v2/intent")
def api_v2_intent(req: V2IntentRequest):
    """
    Ultra-fast intent routing endpoint for live UI updates.
    """
    from layer9_interface.intent_router import route_intent
    import json
    
    history_obj = []
    if req.history:
        try:
            history_obj = json.loads(req.history)
        except Exception:
            pass
            
    decision = route_intent(req.query, history_obj)
    return decision

@app.post("/v2/run")
def api_v2_run(req: V2RunRequest):
    """
    Unified entrypoint as a persistent FastAPI endpoint. 
    Replaces the slow subprocess.spawn("py", "run_entrypoint.py") approach.
    """
    from orchestrator_v2.run_entrypoint import (
        _parse_context, run_chat_mode, run_full_mode, run_surfaces_mode
    )
    
    try:
        ctx = _parse_context(req.context)
        
        # Construct mock args for run_chat_mode to read history/exp
        class MockArgs:
            history = req.history
            exp = req.exp
            userMode = req.userMode
            
        args = MockArgs()
        query = req.query.strip() if req.query else ""
        
        if req.mode == "chat":
            result = run_chat_mode(ctx, query, args)
        elif req.mode == "full":
            result = run_full_mode(ctx, query)
        elif req.mode == "surfaces":
            result = run_surfaces_mode(ctx, query)
            try:
                from app.pi_helpers import fetch_all_sources, build_timeline

                safe_lat = ctx.get("lat")
                safe_lat = float(safe_lat) if safe_lat is not None else 36.0

                safe_lng = ctx.get("lng")
                safe_lng = float(safe_lng) if safe_lng is not None else 3.0

                # Use the SAME shared helpers as /v2/plot-intelligence (unified pipeline)
                pi_results = fetch_all_sources(safe_lat, safe_lng, 7, 7)
                tl, _, _, _ = build_timeline(pi_results, safe_lat, 7, 7)

                result["timeline"] = tl
                result["current"] = {
                    "weather": pi_results.get("weather"),
                    "indices": pi_results.get("indices"),
                    "soil": pi_results.get("soil"),
                    "waterBalance": pi_results.get("water"),
                }
            except Exception as e:
                print(f"[API] Failed to fetch PI bundle: {e}")
        else:
            raise HTTPException(status_code=400, detail=f"Unknown mode: {req.mode}")
            
        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail={"error": str(e), "type": "AgriBrainRunError"})

# ============================================================================
# Direct Specialized AI Endpoints
# ============================================================================

@app.post("/ai/disease_risk")
def disease_risk(req: SpecializedAIRequest):
    """Direct access to Disease Risk AI"""
    context = req.context.copy()
    context["crop"] = req.crop
    return disease_risk_ai.predict(context)

@app.post("/ai/phenology")
def phenology(req: SpecializedAIRequest):
    """Direct access to Phenology AI"""
    context = req.context.copy()
    context["crop"] = req.crop
    return phenology_ai.predict(context)

@app.post("/ai/spray_window")
def spray_window(req: SpecializedAIRequest):
    """Direct access to Spray Window AI"""
    return spray_window_ai.predict(req.context)

@app.post("/ai/water_stress")
def water_stress(req: SpecializedAIRequest):
    """Direct access to Water Stress AI"""
    context = req.context.copy()
    context["crop"] = req.crop
    return water_stress_ai.predict(context)

# ============================================================================
# Pipeline & Training Endpoints
# ============================================================================

class PipelineRunRequest(BaseModel):
    """Request to run a training pipeline"""
    config: Optional[Dict[str, Any]] = None

@app.post("/pipeline/{ai_name}/run")
def run_pipeline(ai_name: str, req: PipelineRunRequest = None):
    """Trigger a training pipeline for specified AI"""
    try:
        from pipelines.disease_risk_pipeline import create_pipeline
        
        pipeline = create_pipeline(ai_name)
        if not pipeline:
            raise HTTPException(status_code=404, detail=f"Pipeline not found for: {ai_name}")
        
        config = req.config if req else {}
        run = pipeline.execute(config)
        
        return {
            "status": "completed" if run.status.value == "completed" else "failed",
            "run_id": run.run_id,
            "stages": run.stages,
            "artifacts": run.artifacts
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/pipeline/{ai_name}/status")
def pipeline_status(ai_name: str):
    """Get pipeline status and run history"""
    from pathlib import Path
    pipeline_dir = Path(__file__).parent.parent / "pipelines" / ai_name / "runs"
    
    if not pipeline_dir.exists():
        return {"ai_name": ai_name, "runs": [], "message": "No runs yet"}
    
    runs = []
    for run_dir in sorted(pipeline_dir.iterdir(), reverse=True)[:10]:
        state_file = run_dir / "run_state.json"
        if state_file.exists():
            with open(state_file) as f:
                runs.append(json.load(f))
    
    return {"ai_name": ai_name, "runs": runs}

@app.get("/models")
def list_models():
    """List all registered trained models"""
    from core.pipeline import model_registry
    return model_registry.list_models()

@app.get("/models/{model_name}")
def get_model(model_name: str, version: str = None):
    """Get specific model info"""
    from core.pipeline import model_registry
    model = model_registry.get_model(model_name, version)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_name}")
    return model

# ============================================================================
# Data Collector Endpoints
# ============================================================================

class PlotRegistrationRequest(BaseModel):
    """Request to register a plot for data collection"""
    farm_id: str
    plot_id: str
    coordinates: Dict[str, float]
    crop: str
    area: Optional[float] = 0

@app.post("/collector/register-plot")
def register_plot(req: PlotRegistrationRequest):
    """Register a new plot for automatic data collection"""
    from core.data_collector import data_collector
    
    result = data_collector.register_plot(
        farm_id=req.farm_id,
        plot_id=req.plot_id,
        coordinates=req.coordinates,
        crop=req.crop,
        area=req.area
    )
    return {
        "status": "registered",
        "plot": result,
        "message": "Plot registered for data collection. Initial weather snapshot captured."
    }

@app.post("/collector/snapshot/{farm_id}/{plot_id}")
def capture_snapshot(farm_id: str, plot_id: str, data_type: str = "weather"):
    """Manually trigger a data snapshot for a plot"""
    from core.data_collector import data_collector
    
    if data_type == "weather":
        result = data_collector.capture_weather_snapshot(farm_id, plot_id)
    elif data_type == "satellite":
        result = data_collector.capture_satellite_snapshot(farm_id, plot_id)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown data_type: {data_type}")
    
    if result:
        return {"status": "captured", "observation": result}
    else:
        raise HTTPException(status_code=404, detail="Plot not found or capture failed")

@app.post("/collector/collect-all")
def collect_all_weather():
    """Trigger weather collection for ALL registered plots"""
    from core.data_collector import data_collector
    result = data_collector.collect_all_weather()
    return result

@app.get("/collector/status")
def collector_status():
    """Get overall data collection status"""
    from core.data_collector import data_collector
    return data_collector.get_status()

@app.get("/data/{farm_id}/{plot_id}/observations")
def get_plot_observations(farm_id: str, plot_id: str, start_date: str = None, end_date: str = None):
    """Get collected observations for a plot"""
    from core.data_collector import data_collector
    return data_collector.get_plot_data(farm_id, plot_id, start_date, end_date)

# ============================================================================
# Startup
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)


