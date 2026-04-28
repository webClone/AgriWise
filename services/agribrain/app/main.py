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
    print(f"✅ Loaded environment from: {env_path}")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import json
from datetime import datetime

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



@app.get("/eo/soil-properties")
def get_soil_properties(lat: float, lng: float):
    """
    Get soil properties (pH, nutrients, texture) from SoilGrids.
    """
    from eo.sentinel import fetch_soil_properties
    result = fetch_soil_properties(lat, lng)
    if result:
        return result
    return {"error": "Could not fetch soil properties", "lat": lat, "lng": lng}

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
            
        args = MockArgs()
        query = req.query.strip() if req.query else ""
        
        if req.mode == "chat":
            result = run_chat_mode(ctx, query, args)
        elif req.mode == "full":
            result = run_full_mode(ctx, query)
        elif req.mode == "surfaces":
            result = run_surfaces_mode(ctx, query)
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


