export interface SoilGridsData {
  clay: number; // %
  sand: number; // %
  silt: number; // %
  ph: number;   // pH
  soc: number;  // g/kg (Organic Carbon)
  bdod: number; // kg/dm³ (Bulk Density)
  cec: number;  // cmol/kg
  nitrogen: number; // g/kg (Now fetched directly)
  cfvo: number; // % (Coarse Fragments)
  ocd: number; // kg/dm³ (Organic Carbon Density)
  ocs: number; // t/ha (Organic Carbon Stocks 0-30cm)
  wv0033: number; // % (Field Capacity)
  wv1500: number; // % (Wilting Point)
  clay_sub: number; // % (Subsoil 30-100cm)
  ph_sub: number;   // pH (Subsoil)
  soc_sub: number;  // g/kg (Subsoil Carbon)
}

/**
 * Fetches real soil data from ISRIC SoilGrids Lat/Lon Query.
 * Uses the 0-30cm average (Topsoil) for agricultural relevance.
 * NOTE: Direct Next.js fetching is disabled. Route via Python backend Layer 0 instead.
 */
export async function fetchSoilGridsData(lat: number, lng: number): Promise<SoilGridsData | null> {
  console.warn("[FAO Service] Direct Next.js fetch to SoilGrids is disabled. Route via Python backend Layer 0 instead.");
  return null;
}
