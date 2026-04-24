"use server";

import { OneSoilProfile, fetchOneSoilData } from "../onesoil-service";
import { fetchSentinelData } from "./sentinel-service";
export { fetchSentinelData };
import { fetchNasaPowerData } from "./nasa-power-service";
import { fallbackSimulation } from "./fallback";

// ============================================================================
// PROVIDER TYPES
// ============================================================================

export type SatelliteProvider = 'openweather' | 'sentinel' | 'nasa';

export interface ProviderInfo {
  id: SatelliteProvider;
  name: string;
  description: string;
  dataTypes: string[];
  requiresAuth: boolean;
  isConfigured: boolean;
}

// ============================================================================
// PROVIDER REGISTRY
// ============================================================================

export async function getAvailableProviders(): Promise<ProviderInfo[]> {
  const openweatherKey = process.env.OPENWEATHER_API_KEY;
  const sentinelClientId = process.env.SENTINEL_HUB_CLIENT_ID;
  const sentinelSecret = process.env.SENTINEL_HUB_CLIENT_SECRET;
  const sentinelInstanceId = process.env.SENTINEL_INSTANCE_ID;

  return [
    {
      id: 'sentinel',
      name: 'Copernicus Data Space (Sentinel)',
      description: 'Multi-spectral Sentinel-2 imagery with 10m resolution (Official EU Public Data)',
      dataTypes: ['True Color', 'False Color', 'NDVI', 'EVI', 'Barren Soil', 'Moisture Index', 'Moisture Stress', 'Agriculture', 'SAVI', 'NDWI'],
      requiresAuth: true,
      isConfigured: !!(sentinelClientId && sentinelSecret && sentinelInstanceId)
    },
    {
      id: 'nasa',
      name: 'NASA',
      description: 'Agroclimatology parameters (temperature, humidity, solar radiation)',
      dataTypes: ['Temperature', 'Humidity', 'Solar Radiation', 'Precipitation'],
      requiresAuth: false,
      isConfigured: true // Always available - free API
    },
    {
      id: 'openweather',
      name: 'OpenWeather Agro API',
      description: 'Historical and current indices with simplified processing',
      dataTypes: ['NDVI', 'NDMI', 'EVI'],
      requiresAuth: true,
      isConfigured: !!openweatherKey
    }
  ];
}

export async function fetchSatelliteData(
  provider: SatelliteProvider,
  lat: number,
  lng: number,
  cropCode: string
): Promise<any> {
  // 1. Check local environment and provider status
  const openweatherKey = process.env.OPENWEATHER_API_KEY;
  const sentinelClientId = process.env.SENTINEL_HUB_CLIENT_ID;
  const sentinelSecret = process.env.SENTINEL_HUB_CLIENT_SECRET;
  const sentinelInstanceId = process.env.SENTINEL_INSTANCE_ID;

  console.log(`[SatelliteProvider] Requesting ${provider} data for ${lat},${lng}`);

  try {
    // 2. Route to specific service
    if (provider === 'sentinel' && sentinelClientId && sentinelSecret && sentinelInstanceId) {
      return await fetchSentinelData(lat, lng);
    } 

    if (provider === 'nasa') {
      return await fetchNasaPowerData(lat, lng);
    }

    if (provider === 'openweather' && openweatherKey) {
      const data = await fetchOneSoilData(lat, lng, cropCode);
      if (data) return data;
    }

    // 3. Fallback to simulation if provider unavailable or failed
    console.warn(`[SatelliteProvider] Provider ${provider} unavailable or failed, using simulation`);
    return fallbackSimulation(lat, lng, "");

  } catch (error) {
    console.error(`[SatelliteProvider] Error fetching ${provider} data:`, error);
    return fallbackSimulation(lat, lng, "");
  }
}
