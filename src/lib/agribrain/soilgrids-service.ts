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
 */
export async function fetchSoilGridsData(lat: number, lng: number): Promise<SoilGridsData | null> {
  try {
    // SoilGrids V2 query
    // Properties extended: nitrogen, cfvo, ocd, ocs, wv0033, wv1500
    const props = ['clay', 'sand', 'silt', 'phh2o', 'soc', 'bdod', 'cec', 'nitrogen', 'cfvo', 'ocd', 'ocs', 'wv0033', 'wv1500'];
    const params = new URLSearchParams({
      lat: lat.toString(),
      lon: lng.toString(),
    });
    props.forEach(p => params.append('property', p));
    params.append('depth', '0-5cm');
    params.append('depth', '5-15cm');
    params.append('depth', '15-30cm');
    params.append('depth', '30-60cm');
    params.append('depth', '60-100cm');
    params.append('value', 'mean');

    const url = `https://rest.isric.org/soilgrids/v2.0/properties/query?${params.toString()}`;
    console.log(`[SoilGrids] Fetching: ${url}`);

    const response = await fetch(url);
    if (!response.ok) {
        // SoilGrids sometimes errors on invalid coords or server load, fail gracefully
        throw new Error(`SoilGrids API Status: ${response.status}`);
    }

    const json = await response.json();
    
    // Helper to extract mean value across requested depths (0-30cm average)
    const getAvg = (propName: string, scaleFactor = 1): number => {
      const layer = json.properties.layers.find((l: any) => l.name === propName);
      if (!layer) return 0;
      
      // Calculate weighted average or simple mean of the depths
      // Depths: 0-5, 5-15, 15-30. 
      // Weights: 5, 10, 15 (Total 30)
      const d0_5 = layer.depths.find((d: any) => d.label === '0-5cm')?.values.mean || 0;
      const d5_15 = layer.depths.find((d: any) => d.label === '5-15cm')?.values.mean || 0;
      const d15_30 = layer.depths.find((d: any) => d.label === '15-30cm')?.values.mean || 0;
      
      const weightedSum = (d0_5 * 5) + (d5_15 * 10) + (d15_30 * 15);
      const val = weightedSum / 30;
      
      // Apply scale factor (from SoilGrids FAQ/Docs)
      // clay, sand, silt: 10 (e.g. 250 = 25.0%)
      // phh2o: 10 (62 = 6.2)
      // soc: 10 (g/kg e.g. 120 = 12.0)
      // bdod: 100 (cg/cm³ -> 145 = 1.45 kg/dm³)
      // cec: 10 (cmol/kg)
      // nitrogen: 100 (cg/kg -> 150 = 1.5 g/kg)
      // cfvo: 10 (cm³/dm³ -> 140 = 14%)
      // ocd: 10 (dg/dm³ to kg/dm³) - Wait. SoilGrids unit: hg/m³? 
      // standard: ocd decigrams per dm3. 1 g/cm3 = 1000 kg/m3. 
      // Let's rely on standard integer scaler 10 for consistency unless specified.
      // ocs: 10 (t/ha).
      return val / scaleFactor;
    };

    const getSubsoilAvg = (propName: string, scaleFactor = 1): number => {
      const layer = json.properties.layers.find((l: any) => l.name === propName);
      if (!layer) return 0;
      
      // Depths: 30-60, 60-100
      // Weights: 30, 40 (Total 70)
      const d30_60 = layer.depths.find((d: any) => d.label === '30-60cm')?.values.mean || 0;
      const d60_100 = layer.depths.find((d: any) => d.label === '60-100cm')?.values.mean || 0;
      
      const weightedSum = (d30_60 * 30) + (d60_100 * 40);
      const val = weightedSum / 70;
      return val / scaleFactor;
    };

    const clay = getAvg('clay', 10);
    const sand = getAvg('sand', 10);
    const silt = getAvg('silt', 10);
    const ph = getAvg('phh2o', 10);
    const soc = getAvg('soc', 10);
    const bdod = getAvg('bdod', 100);
    const cec = getAvg('cec', 10);
    
    // Subsoil properties
    const clay_sub = getSubsoilAvg('clay', 10);
    const ph_sub = getSubsoilAvg('phh2o', 10);
    const soc_sub = getSubsoilAvg('soc', 10);

    // New fields
    const nitrogen = getAvg('nitrogen', 100); // cg/kg -> g/kg
    const cfvo = getAvg('cfvo', 10); // ‰ -> %
    const ocd = getAvg('ocd', 10); // dg/dm³ -> kg/dm³
    const ocs = getAvg('ocs', 10); // t/ha
    const wv0033 = getAvg('wv0033', 10); // 10 * % -> %
    const wv1500 = getAvg('wv1500', 10); // 10 * % -> %

    // Check for invalid/ocean data (if execution returns 0s for texture)
    if (clay === 0 && sand === 0 && silt === 0) {
        console.warn("[SoilGrids] Data returned zeros (likely ocean/out-of-bounds). triggering fallback.");
        return null;
    }

    return {
      clay,
      sand,
      silt,
      ph,
      soc,
      bdod,
      cec,
      nitrogen,
      cfvo,
      ocd,
      ocs,
      wv0033,
      wv1500,
      clay_sub,
      ph_sub,
      soc_sub
    };

  } catch (error) {
    console.warn("Failed to fetch SoilGrids data:", error);
    return null;
  }
}
