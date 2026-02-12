export interface NASAPowerData {
  annualRainfall: number; // mm/year
  solarInsolation: number; // kW-hr/m^2/day (Annual Avg)
  droughtRiskIndex: number; // 0-10 derived
}

/**
 * Fetches Climatology (Long Term Averages) from NASA POWER.
 * Uses the 'AG' (Agroclimatology) community.
 */
export async function fetchNASAPowerData(lat: number, lng: number): Promise<NASAPowerData | null> {
  try {
    // NASA POWER Point Climatology
    // Parameters: PRECTOTCORR (Precipitation), ALLSKY_SFC_SW_DWN (Solar)
    const params = new URLSearchParams({
      parameters: 'PRECTOTCORR,ALLSKY_SFC_SW_DWN',
      community: 'AG',
      longitude: lng.toString(),
      latitude: lat.toString(),
      format: 'JSON'
    });

    const url = `https://power.larc.nasa.gov/api/temporal/climatology/point?${params.toString()}`;
    console.log(`[NASA POWER] Fetching: ${url}`);

    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`NASA Power API Status: ${response.status}`);
    }

    const json = await response.json();
    const properties = json?.properties?.parameter;
    
    if (!properties) return null;

    // PRECTOTCORR is monthly avg. Sum for annual.
    const precMonthly = properties.PRECTOTCORR;
    let annualRainfall = 0;
    // Iterate object keys "JAN"..."DEC", usually keys are 1..12 or month names wait, NASA returns "JAN": val
    // But sometimes it returns "13" as Annual? Let's sum explicitly to be safe or use key 'ANN' if present.
    
    if (properties.PRECTOTCORR.ANN) {
        annualRainfall = properties.PRECTOTCORR.ANN * 365; // Wait check units.
        // Climatology PRECTOTCORR is usually mm/day for that month?
        // Docs: "Precipitation Corrected (mm/day)"
        // So ANN avg mm/day * 365 = Total Annual.
        annualRainfall = properties.PRECTOTCORR.ANN * 365;
    }

    // Solar: ALLSKY_SFC_SW_DWN (kWh/m^2/day)
    const solarAnn = properties.ALLSKY_SFC_SW_DWN.ANN || 0;

    // Drought Risk Calculation (heuristic)
    // < 200mm = Extreme/Desert, < 400mm = High, < 600mm = Medium
    const droughtRiskIndex = annualRainfall < 250 ? 9 : annualRainfall < 400 ? 7 : annualRainfall < 600 ? 5 : 2;

    return {
        annualRainfall,
        solarInsolation: solarAnn,
        droughtRiskIndex
    };

  } catch (error) {
    console.warn("Failed to fetch NASA Power data:", error);
    return null;
  }
}
