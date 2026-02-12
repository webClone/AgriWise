

import { format, subDays } from "date-fns";
import { OneSoilProfile, SatelliteLayer } from "../onesoil-service";

// ============================================================================
// NASA POWER API CONFIGURATION
// ============================================================================

const NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point";
const NASA_EARTH_ASSETS_URL = "https://api.nasa.gov/planetary/earth/assets";
const NASA_EARTH_IMAGERY_URL = "https://api.nasa.gov/planetary/earth/imagery";
const NASA_API_KEY = process.env.NASA_API_KEY || "DEMO_KEY";

console.log(`[NASA Service] Initialized with Key: ${NASA_API_KEY.slice(0, 4)}... (from env: ${!!process.env.NASA_API_KEY})`);

// Parameters available from NASA POWER (Agroclimatology)
const CLIMATE_PARAMS = [
  "T2M",           // Temperature at 2 Meters (°C)
  "T2M_MAX",       // Maximum Temperature at 2 Meters (°C)
  "T2M_MIN",       // Minimum Temperature at 2 Meters (°C)
  "RH2M",          // Relative Humidity at 2 Meters (%)
  "PRECTOTCORR",   // Precipitation (mm/day)
  "ALLSKY_SFC_SW_DWN", // Solar Radiation (MJ/m²/day)
  "WS2M",          // Wind Speed at 2 Meters (m/s)
].join(",");

// ============================================================================
// CLIMATE DATA INTERFACE
// ============================================================================

export interface NasaClimateData {
  date: string;
  temperature: number;
  tempMax: number;
  tempMin: number;
  humidity: number;
  precipitation: number;
  solarRadiation: number;
  windSpeed: number;
}

// ============================================================================
// MAIN FETCH FUNCTION
// ============================================================================

export async function fetchNasaPowerData(
  lat: number,
  lng: number
): Promise<OneSoilProfile> {
  const today = new Date();
  const endDate = format(subDays(today, 3), "yyyyMMdd"); // NASA has ~2-3 day lag for some parameters
  const startDate = format(subDays(today, 90), "yyyyMMdd");

  try {
    const url = `${NASA_POWER_URL}?parameters=${CLIMATE_PARAMS}&community=AG&longitude=${lng}&latitude=${lat}&start=${startDate}&end=${endDate}&format=JSON`;

    console.log("NASA POWER API Request:", url);

    const response = await fetch(url, {
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      throw new Error(`NASA POWER API failed: ${response.status}`);
    }

    const data = await response.json();
    console.log("NASA POWER Response received");
    const properties = data.properties?.parameter;

    if (!properties) {
      console.error("NASA POWER: Invalid response format", JSON.stringify(data).slice(0, 200));
      throw new Error("Invalid NASA POWER response format");
    }

    // 4. Fetch NASA Satellite Image Availability (Non-blocking with independent timeout)
    const assetsTimeout = new Promise<any[]>((resolve) => setTimeout(() => resolve([]), 5000));
    const assetsFetch = fetchNasaSatelliteAssets(lat, lng);
    const assets = await Promise.race([assetsFetch, assetsTimeout]);
    console.log(`NASA Assets Found: ${assets.length}`);

    // Process climate data
    const climateData = processClimateData(properties);
    
    console.log("NASA POWER Data:", climateData.length, "days");

    if (climateData.length === 0) {
      return createFallbackProfile("No NASA POWER data available");
    }

    // Calculate synthetic NDVI from climate conditions
    // (NASA POWER doesn't provide NDVI directly, but we can estimate vegetation health)
    const layers: SatelliteLayer[] = climateData.slice(-5).map((day) => {
      // Find matching asset for this date (simple date match)
      const matchingAsset = assets.find(a => a.date.startsWith(day.date));
      const ndvi = estimateNdviFromClimate(day);
      
      const imageUrl = matchingAsset 
          ? `${NASA_EARTH_IMAGERY_URL}?lon=${lng}&lat=${lat}&date=${day.date}&dim=0.05&api_key=${NASA_API_KEY}`
          : "";
      
      if (imageUrl) console.log(`[NASA Service] Generated Image URL for ${day.date}: ${imageUrl}`);
      
      return {
        date: day.date,
        ndvi: ndvi,
        ndmi: estimateMoistureFromClimate(day),
        evi: ndvi * 0.9,
        savi: ndvi * 0.75,
        cloudCover: day.solarRadiation < 15 ? 50 : 10,
        imageUrl: imageUrl,
      };
    });

    const trend = climateData.map((day) => {
      const ndvi = estimateNdviFromClimate(day);
      return {
        date: day.date,
        ndvi: ndvi,
        ndmi: estimateMoistureFromClimate(day),
        evi: ndvi * 0.9,
        savi: ndvi * 0.75,
      };
    });

    // Get latest weather for display
    const latest = climateData[climateData.length - 1];

    return {
      lastUpdated: format(today, "yyyy-MM-dd"),
      layers,
      trend,
      productivityZones: calculateProductivityZones(climateData),
      isSimulation: false,
      debugInfo: `NASA POWER (${climateData.length} days of climate data)`,
      weather: latest ? {
        temp: latest.temperature,
        humidity: latest.humidity,
        clouds: latest.solarRadiation < 15 ? 70 : 20,
        wind_speed: latest.windSpeed,
        description: getWeatherDescription(latest),
      } : undefined,
    };
  } catch (error) {
    console.error("NASA POWER Error:", error);
    return createFallbackProfile(`NASA POWER Error: ${error instanceof Error ? error.message : "Unknown"}`);
  }
}

async function fetchNasaSatelliteAssets(lat: number, lng: number): Promise<{date: string, id: string}[]> {
  try {
    const today = new Date();
    const startDate = format(subDays(today, 365), "yyyy-MM-dd"); // Look back 1 year
    const url = `${NASA_EARTH_ASSETS_URL}?lon=${lng}&lat=${lat}&begin=${startDate}&api_key=${NASA_API_KEY}`;
    
    const res = await fetch(url);
    if (!res.ok) return [];
    
    const data = await res.json();
    return data.results || [];
  } catch (err) {
    console.error("NASA Assets Error:", err);
    return [];
  }
}

// ============================================================================
// DATA PROCESSING
// ============================================================================

function processClimateData(params: Record<string, Record<string, number>>): NasaClimateData[] {
  const dates = Object.keys(params.T2M || {});
  
  return dates
    .filter((date) => params.T2M[date] !== -999) // Filter invalid data
    .map((date) => ({
      date: `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}`,
      temperature: params.T2M[date] || 0,
      tempMax: params.T2M_MAX[date] || 0,
      tempMin: params.T2M_MIN[date] || 0,
      humidity: params.RH2M[date] || 0,
      precipitation: params.PRECTOTCORR[date] || 0,
      solarRadiation: params.ALLSKY_SFC_SW_DWN[date] || 0,
      windSpeed: params.WS2M[date] || 0,
    }));
}

// ============================================================================
// VEGETATION INDEX ESTIMATION FROM CLIMATE
// ============================================================================

function estimateNdviFromClimate(data: NasaClimateData): number {
  // Simple heuristic: vegetation thrives with moderate temp, good humidity, some rain
  let ndvi = 0.5; // Base

  // Temperature factor (optimal 15-25°C)
  if (data.temperature >= 15 && data.temperature <= 25) {
    ndvi += 0.15;
  } else if (data.temperature < 5 || data.temperature > 35) {
    ndvi -= 0.2;
  }

  // Humidity factor
  if (data.humidity > 60) {
    ndvi += 0.1;
  } else if (data.humidity < 30) {
    ndvi -= 0.15;
  }

  // Solar radiation (good for photosynthesis)
  if (data.solarRadiation > 15) {
    ndvi += 0.1;
  }

  // Recent precipitation boost
  if (data.precipitation > 0 && data.precipitation < 20) {
    ndvi += 0.05;
  }

  return Math.max(0.1, Math.min(0.9, ndvi));
}

function estimateMoistureFromClimate(data: NasaClimateData): number {
  // NDMI estimation based on humidity and precipitation
  let ndmi = 0.4;

  if (data.humidity > 70) ndmi += 0.2;
  else if (data.humidity > 50) ndmi += 0.1;
  else if (data.humidity < 30) ndmi -= 0.2;

  if (data.precipitation > 5) ndmi += 0.15;

  return Math.max(0.1, Math.min(0.8, ndmi));
}

function getWeatherDescription(data: NasaClimateData): string {
  if (data.precipitation > 10) return "rainy";
  if (data.solarRadiation < 10) return "cloudy";
  if (data.temperature > 35) return "hot";
  if (data.temperature < 5) return "cold";
  return "clear sky";
}

function calculateProductivityZones(data: NasaClimateData[]): { high: number; medium: number; low: number } {
  const avgNdvi = data.reduce((sum, d) => sum + estimateNdviFromClimate(d), 0) / data.length;
  
  if (avgNdvi > 0.6) return { high: 55, medium: 35, low: 10 };
  if (avgNdvi > 0.45) return { high: 40, medium: 40, low: 20 };
  return { high: 25, medium: 40, low: 35 };
}

// ============================================================================
// FALLBACK
// ============================================================================

function createFallbackProfile(debugInfo: string): OneSoilProfile {
  const today = new Date();
  const layers: SatelliteLayer[] = [];
  const trend: { date: string; ndvi: number; ndmi: number; evi: number; savi: number }[] = [];

  for (let i = 0; i < 5; i++) {
    const date = subDays(today, i * 15);
    const ndvi = 0.4 + Math.random() * 0.3;
    
    layers.push({
      date: format(date, "yyyy-MM-dd"),
      ndvi,
      ndmi: ndvi * 0.8,
      evi: ndvi * 0.9,
      savi: ndvi * 0.75,
      cloudCover: Math.floor(Math.random() * 20),
      imageUrl: "",
    });
    
    trend.push({ 
      date: format(date, "yyyy-MM-dd"), 
      ndvi: ndvi,
      ndmi: ndvi * 0.8,
      evi: ndvi * 0.9,
      savi: ndvi * 0.75,
    });
  }

  return {
    lastUpdated: format(today, "yyyy-MM-dd"),
    layers,
    trend: trend.reverse(),
    productivityZones: { high: 35, medium: 45, low: 20 },
    isSimulation: true,
    debugInfo,
  };
}
