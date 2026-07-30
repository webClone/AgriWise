export interface NASAPowerData {
  annualRainfall: number; // mm/year
  solarInsolation: number; // kW-hr/m^2/day (Annual Avg)
  droughtRiskIndex: number; // 0-10 derived
}

/**
 * Fetches Climatology (Long Term Averages) from NASA POWER.
 * NOTE: Direct Next.js fetching is disabled. Route via Python backend Layer 0 instead.
 */
export async function fetchNASAPowerData(lat: number, lng: number): Promise<NASAPowerData | null> {
  console.warn("[FAO Service] Direct Next.js fetch to NASA Power is disabled. Route via Python backend Layer 0 instead.");
  return null;
}
