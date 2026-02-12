"use server";

import { format, subDays } from "date-fns";

const AGRO_API_URL = "http://api.agromonitoring.com/agro/1.0";
const OPENWEATHER_API_URL = "https://api.openweathermap.org/data/3.0/onecall";

export interface SatelliteLayer {
  date: string;
  ndvi: number;
  ndmi: number;
  evi?: number;
  savi?: number;
  cloudCover: number;
  imageUrl: string; 
  zoneMapUrl?: string; 
}

export interface WeatherData {
    temp: number;
    humidity: number;
    clouds: number;
    wind_speed: number;
    description: string;
}

export interface OneSoilProfile {
  lastUpdated: string;
  layers: SatelliteLayer[];
  trend: { 
    date: string; 
    ndvi: number; 
    ndmi: number; 
    evi: number; 
    savi: number;
  }[];
  productivityZones: { high: number; medium: number; low: number; };
  isSimulation: boolean;
  debugInfo?: string;
  weather?: WeatherData;
}

function getRandomNdvi(val?: number) {
    if (val !== undefined && !isNaN(val)) return parseFloat(val.toFixed(2));
    return parseFloat((0.2 + Math.random() * 0.6).toFixed(2));
}

const WEATHER_2_5_URL = "https://api.openweathermap.org/data/2.5/weather";

// REAL WEATHER CLIENT (One Call 3.0)
async function getWeatherData(lat: number, lng: number, key: string) {
    let debug = "";
    try {
        // Attempt 1: OneCall 3.0 (Best Data)
        const res = await fetch(`${OPENWEATHER_API_URL}?lat=${lat}&lon=${lng}&exclude=minutely,hourly,daily&units=metric&appid=${key}`);
        if (res.ok) {
            const data = await res.json();
            if(data.current) {
                return {
                    data: {
                        temp: data.current.temp,
                        humidity: data.current.humidity,
                        clouds: data.current.clouds,
                        wind_speed: data.current.wind_speed,
                        description: data.current.weather[0].description
                    },
                    source: "OneCall 3.0"
                };
            }
        } else {
            debug += `OneCall 3.0 Failed (${res.status}); `;
        }

        // Attempt 2: Weather 2.5 (Standard Free)
        const res2 = await fetch(`${WEATHER_2_5_URL}?lat=${lat}&lon=${lng}&units=metric&appid=${key}`);
        if (res2.ok) {
            const data = await res2.json();
            if(data.main) {
                return {
                    data: {
                        temp: data.main.temp,
                        humidity: data.main.humidity,
                        clouds: data.clouds ? data.clouds.all : 0,
                        wind_speed: data.wind ? data.wind.speed : 0,
                        description: data.weather[0].description
                    },
                    source: "Weather 2.5"
                };
            }
        } else {
             debug += `Weather 2.5 Failed (${res2.status}); `;
        }
    } catch (e: any) {
        console.error("Weather API Error:", e);
        debug += `Exception: ${e.message}`;
    }
    return { data: null, debug };
}

// REAL API CLIENT (Agromonitoring)
async function getAgroData(lat: number, lng: number, key: string): Promise<{ data: OneSoilProfile | null, error?: string }> {
    try {
        // 1. Create/Find Polygon (approx 800m box)
        const p1 = [lng - 0.005, lat - 0.005];
        const p2 = [lng + 0.005, lat - 0.005];
        const p3 = [lng + 0.005, lat + 0.005];
        const p4 = [lng - 0.005, lat + 0.005];

        const geoJson = {
           name: `AgriWise AOI ${lat.toFixed(3)}_${lng.toFixed(3)}`, 
           geo_json: {
              type: "Feature",
              properties: {},
              geometry: {
                 type: "Polygon",
                 coordinates: [[p1, p2, p3, p4, p1]]
              }
           }
        };

        const polyRes = await fetch(`${AGRO_API_URL}/polygons?appid=${key}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(geoJson)
        });
        
        let polyId;
        if (polyRes.ok) {
            const polyData = await polyRes.json();
            polyId = polyData.id;
        } else {
             const errorText = await polyRes.text();
             
             // Handle Duplicate Polygon (422)
             if (polyRes.status === 422) {
                 try {
                     const errJson = JSON.parse(errorText);
                     if (errJson.message && errJson.message.includes("already existed polygon")) {
                         // Extract ID: ... duplicate of 'ID' ...
                         const match = errJson.message.match(/polygon '([a-f0-9]+)'/);
                         if (match && match[1]) {
                             polyId = match[1];
                             console.log("Recovered existing Polygon ID:", polyId);
                         }
                     }
                 } catch(e) { console.error("Error parsing 422:", e); }
             }

             if (!polyId) {
                return { data: null, error: `Agro Polygon Error ${polyRes.status}: ${errorText}` };
             }
        }

        // 2. Setup Dates (Last 365 days)
        const end = Math.floor(Date.now() / 1000);
        const start = end - (365 * 24 * 60 * 60); 

        // 3. Search for Imagery
        const imgRes = await fetch(`${AGRO_API_URL}/image/search?polyid=${polyId}&start=${start}&end=${end}&appid=${key}`);
        let imageUrl = `https://mt1.google.com/vt/lyrs=s&x=${Math.floor(lng)}&y=${Math.floor(lat)}&z=15`; // Default to Google Satellite
        let bestImageDate = null;

        if (imgRes.ok) {
            const images = await imgRes.json();
            if (Array.isArray(images) && images.length > 0) {
                 const validImages = images.filter((i: any) => i.clouds < 20); // Prioritize low cloud coverage
                 const bestImage = validImages.sort((a: any, b: any) => b.dt - a.dt)[0] || images[0];
                 
                 if (bestImage && bestImage.image) {
                    imageUrl = bestImage.image.truecolor || bestImage.image.ndvi || imageUrl;
                    bestImageDate = bestImage.dt;
                 }
            }
        }

        // 4. Fetch ALL Indices (NDVI, NDMI, EVI) in Parallel
        const startTrend = start;
        
        const [ndviRes, ndmiRes, eviRes] = await Promise.all([
            fetch(`${AGRO_API_URL}/ndvi/history?polyid=${polyId}&start=${startTrend}&end=${end}&appid=${key}`),
            fetch(`${AGRO_API_URL}/ndmi/history?polyid=${polyId}&start=${startTrend}&end=${end}&appid=${key}`),
            fetch(`${AGRO_API_URL}/evi/history?polyid=${polyId}&start=${startTrend}&end=${end}&appid=${key}`)
        ]);

        const [ndviData, ndmiData, eviData] = await Promise.all([
            ndviRes.ok ? ndviRes.json() : [],
            ndmiRes.ok ? ndmiRes.json() : [],
            eviRes.ok ? eviRes.json() : []
        ]);

        // Merge Data by Date
        const dataMap: Record<string, { date: string; ndvi?: number; ndmi?: number; evi?: number }> = {};

        // Helper to process stats array
        const processStats = (stats: { dt: number; data: { mean: number } }[], key: 'ndvi' | 'ndmi' | 'evi') => {
            if (Array.isArray(stats)) {
                stats.forEach((s) => {
                    const date = format(new Date(s.dt * 1000), 'yyyy-MM-dd');
                    if (!dataMap[date]) dataMap[date] = { date };
                    dataMap[date][key] = s.data.mean;
                });
            }
        };

        processStats(ndviData, 'ndvi');
        processStats(ndmiData, 'ndmi');
        processStats(eviData, 'evi');

        // Convert to array and sort
        const trend = Object.values(dataMap)
            .filter((d) => d.ndvi !== undefined)
            .map((d) => ({
                date: d.date,
                value: d.ndvi!,
                ndvi: d.ndvi!,
                ndmi: d.ndmi || (d.ndvi! * 0.8),
                evi: d.evi || (d.ndvi! * 0.9)
            }))
            .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());

        console.log("DEBUG AGRO STATS:", {
            polyId: polyId,
            ndviCount: ndviData.length,
            ndmiCount: ndmiData.length,
            eviCount: eviData.length,
            trendCount: trend.length
        });

        // If no actual data, return null to trigger simulation fallback
        if (trend.length === 0) {
            console.log("AGRO API: No trend data found, falling back to simulation");
            return { data: null, error: `Agro API returned no data (Counts: NDVI=${ndviData.length}, NDMI=${ndmiData.length}, EVI=${eviData.length}). Polygon may still be processing.` };
        }

        // 5. Fetch Live Weather
        const weatherRes = await getWeatherData(lat, lng, key);

        const today = new Date();
        const dateStr = bestImageDate 
            ? format(new Date(bestImageDate * 1000), 'yyyy-MM-dd') 
            : format(today, 'yyyy-MM-dd');

        // Current Layer Logic: Use latest trend data
        const latestStats = trend[trend.length - 1];
        
        return { 
            data: {
                lastUpdated: dateStr,
                layers: [{
                    date: dateStr,
                    ndvi: latestStats.ndvi,
                    ndmi: latestStats.ndmi, 
                    evi: latestStats.evi,
                    cloudCover: (weatherRes?.data as any)?.clouds || 5, // Cast for safety if needed
                    imageUrl: imageUrl
                }],
                trend: trend.map(t => ({ date: t.date, ndvi: t.ndvi, ndmi: t.ndmi, evi: t.evi })),
                productivityZones: { high: 40, medium: 40, low: 20 },
                isSimulation: false,
                debugInfo: `Sentinel-2 Live [Counts: NDVI=${ndviData.length}, NDMI=${ndmiData.length}]`,
                weather: weatherRes?.data || undefined
            } 
        };

    } catch (err: any) {
        console.error("OpenWeather Agro Error:", err);
        return { data: null, error: err.message };
    }
}

// HYBRID FETCHER
export async function fetchOneSoilData(lat: number, lng: number, cropCode: string): Promise<OneSoilProfile> {
  const apiKey = process.env.OPENWEATHER_API_KEY;
  let debugError = "No API Key found in env";
  let weatherData: WeatherData | undefined = undefined;

  if (apiKey) {
      // 1. Try Agro (Satellite)
      try {
        const result = await getAgroData(lat, lng, apiKey, cropCode);
        if (result.data) {
            return result.data; 
        }
        debugError = result.error || "Unknown Agro API Failure";
      } catch(e: any) {
          debugError = `Agro Error: ${e.message}`;
      }

      // 2. If Agro Failed (usually 401), Try Weather APIs
      try {
          const agroErr = debugError;
          const wRes = await getWeatherData(lat, lng, apiKey);
          if (wRes.data) {
              weatherData = wRes.data;
              debugError = `${agroErr} -> Weather Fallback Success! (${wRes.source})`; 
          }
      } catch(e: any) {
          console.error("Weather fallback failed", e);
          debugError += ` -> Weather Exception: ${e.message}`;
      }
  }

  // 3. Fallback to Simulation
  return createFallbackProfile(lat, lng, debugError, weatherData);
}

function createFallbackProfile(lat: number, lng: number, debugError: string, weatherData?: WeatherData): OneSoilProfile {
  const today = new Date();
  const layers: SatelliteLayer[] = [];
  const trend: { date: string; ndvi: number; ndmi: number; evi: number }[] = [];

  for (let i = 0; i < 12; i++) {
    const date = subDays(today, i * 15);
    const dateStr = format(date, 'yyyy-MM-dd');
    
    // Seasonality
    const month = date.getMonth(); 
    let baseValue = 0.2;
    if (month >= 2 && month <= 6) baseValue = 0.7 + (Math.random() * 0.1); 
    else if (month > 6 && month <= 9) baseValue = 0.5 + (Math.random() * 0.1); 
    else baseValue = 0.3 + (Math.random() * 0.1); 
    
    const ndvi = Number((baseValue + (Math.random() * 0.05 - 0.025)).toFixed(2));
    const ndmi = Number((baseValue * 0.8 + (Math.random() * 0.1)).toFixed(2));
    const evi = Number((baseValue * 0.9 + (Math.random() * 0.1)).toFixed(2));

    if (i < 5) {
      layers.push({
        date: dateStr,
        ndvi,
        ndmi,
        evi,
        cloudCover: (i === 0 && weatherData) ? weatherData.clouds : Math.floor(Math.random() * 20), 
        imageUrl: `https://mt1.google.com/vt/lyrs=s&x=${Math.floor(lng)}&y=${Math.floor(lat)}&z=15`, 
      });
    }
    
    trend.push({ date: dateStr, ndvi, ndmi, evi });
  }

  return {
    lastUpdated: format(today, 'yyyy-MM-dd'),
    layers: layers.reverse(),
    trend: trend.reverse(),
    productivityZones: { high: 35, medium: 45, low: 20 },
    isSimulation: true,
    debugInfo: debugError,
    weather: weatherData
  };
}
