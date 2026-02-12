

import { format, subDays } from "date-fns";
import { OneSoilProfile, SatelliteLayer } from "../onesoil-service";
import { calculateZones } from "./satellite-utils";

const SENTINEL_AUTH_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token";
const SENTINEL_STATS_URL = "https://sh.dataspace.copernicus.eu/api/v1/statistics";
const SENTINEL_PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process";

let tokenCache: { token: string; expires: number } | null = null;

export async function getAccessToken(): Promise<string> {
  if (tokenCache && tokenCache.expires > Date.now()) {
    return tokenCache.token;
  }

  const clientId = process.env.SENTINEL_HUB_CLIENT_ID;
  const clientSecret = process.env.SENTINEL_HUB_CLIENT_SECRET;

  if (!clientId || !clientSecret) {
    throw new Error("Sentinel Hub credentials missing in .env");
  }

  const response = await fetch(SENTINEL_AUTH_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "client_credentials",
      client_id: clientId,
      client_secret: clientSecret,
    }),
  });

  if (!response.ok) {
    const errorBody = await response.text();
    console.error(`[Sentinel Auth] Failed: ${response.status} - ${errorBody}`);
    throw new Error(`Auth Failed: ${response.status} - ${errorBody}`);
  }

  const data = await response.json();
  tokenCache = {
    token: data.access_token,
    expires: Date.now() + (data.expires_in - 300) * 1000,
  };

  return data.access_token;
}

// ----------------------------------------------------------------------------
// EVALSCRIPTS (Analytical & Visual)
// ----------------------------------------------------------------------------

export const EVALSCRIPTS = {
  'true-color': `//VERSION=3\nfunction setup(){return{input:["B02","B03","B04","dataMask"],output:[{id:"default",bands:3,sampleType:"AUTO"},{id:"dataMask",bands:1,sampleType:"UINT8"}]};}\nfunction evaluatePixel(sample){return{default:[sample.B04*2.5,sample.B03*2.5,sample.B02*2.5],dataMask:[sample.dataMask]};}`,
  
  'false-color': `//VERSION=3\nfunction setup(){return{input:["B08","B04","B03","dataMask"],output:[{id:"default",bands:3,sampleType:"AUTO"},{id:"dataMask",bands:1,sampleType:"UINT8"}]};}\nfunction evaluatePixel(sample){return{default:[sample.B08*2.5,sample.B04*2.5,sample.B03*2.5],dataMask:[sample.dataMask]};}`,
  
  'nir-r-g': `//VERSION=3\nfunction setup(){return{input:["B08","B04","B03","dataMask"],output:[{id:"default",bands:3,sampleType:"AUTO"},{id:"dataMask",bands:1,sampleType:"UINT8"}]};}\nfunction evaluatePixel(sample){return{default:[sample.B08*2.5,sample.B04*2.5,sample.B03*2.5],dataMask:[sample.dataMask]};}`,
  
  'ndvi': `//VERSION=3\nfunction setup(){return{input:["B04","B08","dataMask"],output:[{id:"default",bands:3},{id:"dataMask",bands:1,sampleType:"UINT8"}]};}function evaluatePixel(sample){var v=(sample.B08-sample.B04)/(sample.B08+sample.B04);var c=[0,0,0];if(v<0)c=[0.4,0.4,0.4];else if(v<0.2)c=[0.6,0.3,0];else if(v<0.4)c=[0.8,0.7,0.2];else if(v<0.6)c=[0.4,0.8,0.2];else c=[0,0.5,0];return{default:c,dataMask:[sample.dataMask]};}`,
  
  'evi': `//VERSION=3\nfunction setup(){return{input:["B02","B04","B08","dataMask"],output:[{id:"default",bands:3},{id:"dataMask",bands:1,sampleType:"UINT8"}]};}function evaluatePixel(sample){var v=2.5*((sample.B08-sample.B04)/(sample.B08+6*sample.B04-7.5*sample.B02+1));var c=[0,0,0];if(v<0)c=[0.5,0,0];else if(v<0.2)c=[0.9,0.5,0.2];else if(v<0.4)c=[0.7,0.8,0.2];else if(v<0.6)c=[0.3,0.7,0.2];else c=[0,0.5,0];return{default:c,dataMask:[sample.dataMask]};}`,
  
  'savi': `//VERSION=3\nfunction setup(){return{input:["B04","B08","dataMask"],output:[{id:"default",bands:3},{id:"dataMask",bands:1,sampleType:"UINT8"}]};}function evaluatePixel(sample){var v=((sample.B08-sample.B04)/(sample.B08+sample.B04+0.5))*1.5;var c=[0,0,0];if(v<0)c=[0.5,0,0];else if(v<0.2)c=[0.9,0.5,0.2];else if(v<0.4)c=[0.7,0.8,0.2];else if(v<0.6)c=[0.3,0.7,0.2];else c=[0,0.5,0];return{default:c,dataMask:[sample.dataMask]};}`,
  
  'ndmi': `//VERSION=3\nfunction setup(){return{input:["B08","B11","dataMask"],output:[{id:"default",bands:3},{id:"dataMask",bands:1,sampleType:"UINT8"}]};}function evaluatePixel(sample){var v=(sample.B08-sample.B11)/(sample.B08+sample.B11);var c=[0,0,0];if(v<0)c=[0.9,0.9,0.9];else if(v<0.1)c=[0.7,0.8,0.9];else if(v<0.3)c=[0.3,0.5,0.9];else c=[0,0.2,0.6];return{default:c,dataMask:[sample.dataMask]};}`,
  
  'moisture-index': `//VERSION=3\nfunction setup(){return{input:["B08","B11","dataMask"],output:[{id:"default",bands:3},{id:"dataMask",bands:1,sampleType:"UINT8"}]};}function evaluatePixel(sample){var v=(sample.B08-sample.B11)/(sample.B08+sample.B11);var c=[0,0,0];if(v<0)c=[0.9,0.9,0.9];else if(v<0.1)c=[0.7,0.8,0.9];else if(v<0.3)c=[0.3,0.5,0.9];else c=[0,0.2,0.6];return{default:c,dataMask:[sample.dataMask]};}`,
  
  'moisture-stress': `//VERSION=3\nfunction setup(){return{input:["B08","B11","dataMask"],output:[{id:"default",bands:3},{id:"dataMask",bands:1,sampleType:"UINT8"}]};}function evaluatePixel(sample){var v=(sample.B08-sample.B11)/(sample.B08+sample.B11);var c=[0,0,0];if(v<-0.1)c=[0.9,0.3,0.2];else if(v<0.1)c=[0.9,0.6,0.3];else if(v<0.3)c=[0.5,0.7,0.8];else c=[0.2,0.4,0.8];return{default:c,dataMask:[sample.dataMask]};}`,
  
  'ndwi': `//VERSION=3\nfunction setup(){return{input:["B03","B08","dataMask"],output:[{id:"default",bands:3},{id:"dataMask",bands:1,sampleType:"UINT8"}]};}function evaluatePixel(sample){var v=(sample.B03-sample.B08)/(sample.B03+sample.B08);var c=[0,0,0];if(v<-0.2)c=[0.95,0.95,0.95];else if(v<0)c=[0.8,0.8,1];else if(v<0.2)c=[0.3,0.5,1];else c=[0,0.1,0.7];return{default:c,dataMask:[sample.dataMask]};}`,
  
  'agriculture': `//VERSION=3\nfunction setup(){return{input:["B11","B08","B02","dataMask"],output:[{id:"default",bands:3,sampleType:"AUTO"},{id:"dataMask",bands:1,sampleType:"UINT8"}]};}\nfunction evaluatePixel(sample){return{default:[sample.B11*2.5,sample.B08*2.5,sample.B02*2.5],dataMask:[sample.dataMask]};}`,
  
  'barren-soil': `//VERSION=3\nfunction setup(){return{input:["B11","B12","B02","dataMask"],output:[{id:"default",bands:3,sampleType:"AUTO"},{id:"dataMask",bands:1,sampleType:"UINT8"}]};}\nfunction evaluatePixel(sample){return{default:[sample.B11*2.5,sample.B12*2.5,sample.B02*2.5],dataMask:[sample.dataMask]};}`
};

export async function fetchSentinelImage(bbox: number[], date: string, metric: string = 'true-color'): Promise<string> {
  try {
    const token = await getAccessToken();
    const evalscript = EVALSCRIPTS[metric as keyof typeof EVALSCRIPTS] || EVALSCRIPTS['true-color'];
    
    const response = await fetch(SENTINEL_PROCESS_URL, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "image/png",
      },
      body: JSON.stringify({
        input: {
          bounds: { 
            bbox,
            properties: { crs: "http://www.opengis.net/def/crs/EPSG/0/4326" }
          },
          data: [{ 
            type: "sentinel-2-l2a", 
            timeRange: { from: `${date}T00:00:00Z`, to: `${date}T23:59:59Z` } 
          }],
        },
        output: { width: 512, height: 512, responses: [{ identifier: "default", format: { type: "image/png" } }] },
        evalscript: evalscript,
      }),
    });

    if (!response.ok) return "";
    const buffer = await response.arrayBuffer();
    const base64 = Buffer.from(buffer).toString('base64');
    return `data:image/png;base64,${base64}`;
  } catch (err) {
    console.error("fetchSentinelImage error", err);
    return "";
  }
}

async function fetchSatelliteStatistics(lat: number, lng: number, startDate: string, endDate: string) {
  const token = await getAccessToken();
  const delta = 0.001; 
  const bbox = [lng - delta, lat - delta, lng + delta, lat + delta];

  const requestBody = {
    input: {
      bounds: { 
        bbox,
        properties: { crs: "http://www.opengis.net/def/crs/EPSG/0/4326" }
      },
      data: [{ 
        type: "sentinel-2-l2a", 
        timeRange: { from: `${startDate}T00:00:00Z`, to: `${endDate}T23:59:59Z` } 
      }],
    },
    aggregation: {
      timeRange: { from: `${startDate}T00:00:00Z`, to: `${endDate}T23:59:59Z` },
      aggregationInterval: { of: "P15D" },
      evalscript: `
//VERSION=3
function setup() {
  return {
    input: ["B02", "B04", "B08", "B11", "dataMask"],
    output: [
      { id: "default", bands: 4, sampleType: "FLOAT32" },
      { id: "dataMask", bands: 1, sampleType: "UINT8" }
    ]
  };
}
function evaluatePixel(sample) {
  let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
  let ndmi = (sample.B08 - sample.B11) / (sample.B08 + sample.B11);
  let evi = 2.5 * ((sample.B08 - sample.B04) / (sample.B08 + 6 * sample.B04 - 7.5 * sample.B02 + 1));
  let savi = ((sample.B08 - sample.B04) / (sample.B08 + sample.B04 + 0.5)) * (1.5);
  return {
    default: [ndvi, ndmi, evi, savi],
    dataMask: [sample.dataMask]
  };
}
`,
      width: 1,
      height: 1,
    },
  };

  const response = await fetch(SENTINEL_STATS_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(requestBody),
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error(`[Sentinel Stats] Failed (${response.status}): ${errorText.slice(0, 500)}`);
    throw new Error(`Sentinel Hub stats failed: ${response.status}`);
  }

  const result = await response.json();
  
  if (!result.data || !Array.isArray(result.data)) {
    return [];
  }

  return result.data.map((item: any) => {
    const bands = item.outputs?.default?.bands;
    return {
      date: item.interval.from.split("T")[0],
      ndvi: bands?.[0]?.stats?.mean ?? 0.5, // Reference by index as it is multi-band FLOAT32
      ndmi: bands?.[1]?.stats?.mean ?? 0.4,
      evi: bands?.[2]?.stats?.mean ?? 0.45,
      savi: bands?.[3]?.stats?.mean ?? 0.4,
    };
  });
}

export async function fetchSentinelData(lat: number, lng: number): Promise<OneSoilProfile> {
  const today = new Date();
  const endDate = format(today, "yyyy-MM-dd");
  const startDate = format(subDays(today, 180), "yyyy-MM-dd");

  try {
    const satelliteStats = await fetchSatelliteStatistics(lat, lng, startDate, endDate);

    if (satelliteStats.length === 0) {
      return createFallbackProfile("No Sentinel-2 data available for this location");
    }

    const layers: SatelliteLayer[] = await Promise.all(
      satelliteStats.slice(-5).map(async (stat: { date: string, ndvi: number, ndmi: number, evi: number, savi: number }) => {
        const delta = 0.005;
        const bbox = [lng - delta, lat - delta, lng + delta, lat + delta];
        const realImageUrl = await fetchSentinelImage(bbox, stat.date);
        
        return {
          date: stat.date,
          ndvi: Math.max(0, Math.min(1, stat.ndvi)),
          ndmi: Math.max(0, Math.min(1, stat.ndmi)),
          evi: Math.max(0, Math.min(1, stat.evi)),
          savi: Math.max(0, Math.min(1, stat.savi)),
          cloudCover: 10,
          imageUrl: realImageUrl || `https://mt1.google.com/vt/lyrs=s&x=${Math.floor(lng)}&y=${Math.floor(lat)}&z=15`,
        };
      })
    );

    const trend = satelliteStats.map((stat: { date: string, ndvi: number, ndmi: number, evi: number, savi: number }) => ({
      date: stat.date,
      ndvi: Math.max(0, Math.min(1, stat.ndvi)),
      ndmi: Math.max(0, Math.min(1, stat.ndmi)),
      evi: Math.max(0, Math.min(1, stat.evi)),
      savi: Math.max(0, Math.min(1, stat.savi)),
    }));

    const latestNdvi = trend[trend.length - 1]?.ndvi || 0.5;

    return {
      lastUpdated: endDate,
      layers,
      trend,
      productivityZones: calculateZones(latestNdvi),
      isSimulation: false,
      debugInfo: `Copernicus Data Space (${satelliteStats.length} observations)`,
    };
  } catch (error) {
    console.error("Sentinel Hub Error:", error);
    return createFallbackProfile(`Sentinel Hub Error: ${error instanceof Error ? error.message : "Unknown"}`);
  }
}

function createFallbackProfile(debugInfo: string): OneSoilProfile {
  const today = new Date();
  const layers: SatelliteLayer[] = [];
  const trend: { date: string; ndvi: number; ndmi: number; evi: number; savi: number }[] = [];

  for (let i = 0; i < 5; i++) {
    const date = subDays(today, i * 15);
    const dateStr = format(date, "yyyy-MM-dd");
    const ndvi = 0.4 + Math.random() * 0.3;
    const ndmi = ndvi * 0.8;
    const evi = ndvi * 0.9;
    const savi = ndvi * 0.75;

    layers.push({
      date: dateStr,
      ndvi,
      ndmi,
      evi,
      savi,
      cloudCover: Math.floor(Math.random() * 20),
      imageUrl: `https://mt1.google.com/vt/lyrs=s&x=${Math.random()}&y=${Math.random()}&z=15`,
    });
    trend.push({ date: dateStr, ndvi, ndmi, evi, savi });
  }

  return {
    lastUpdated: format(today, "yyyy-MM-dd"),
    layers,
    trend,
    productivityZones: { high: 40, medium: 40, low: 20 },
    isSimulation: true,
    debugInfo: debugInfo,
  };
}
