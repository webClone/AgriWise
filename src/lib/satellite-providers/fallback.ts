

import { format, subDays } from "date-fns";
import { OneSoilProfile, SatelliteLayer } from "../onesoil-service";

export async function fallbackSimulation(
  lat: number,
  lng: number,
  debugInfo: string
): Promise<OneSoilProfile> {
  const today = new Date();
  const layers: SatelliteLayer[] = [];
  const trend: { date: string; ndvi: number; ndmi: number; evi: number; savi: number }[] = [];

  // Generate 12 months of trend but only 5 layers for performance
  for (let i = 0; i < 12; i++) {
    const date = subDays(today, i * 15);
    const dateStr = format(date, 'yyyy-MM-dd');
    
    // Simple seasonality heuristic
    const month = date.getMonth(); 
    let baseNdvi = 0.2;
    if (month >= 2 && month <= 6) baseNdvi = 0.6 + (Math.random() * 0.2); 
    else if (month > 6 && month <= 9) baseNdvi = 0.4 + (Math.random() * 0.2); 
    else baseNdvi = 0.3 + (Math.random() * 0.1); 
    
    const ndvi = Number((baseNdvi + (Math.random() * 0.05 - 0.025)).toFixed(2));
    const ndmi = Number((baseNdvi * 0.8 + (Math.random() * 0.1)).toFixed(2));

    const layer: SatelliteLayer = {
      date: dateStr,
      ndvi,
      ndmi,
      evi: Number((ndvi * 0.9).toFixed(2)),
      savi: Number((ndvi * 0.75).toFixed(2)),
      cloudCover: Math.floor(Math.random() * 20), 
      imageUrl: `https://mt1.google.com/vt/lyrs=s&x=${Math.floor(lng)}&y=${Math.floor(lat)}&z=15`, 
    };

    if (i < 5) layers.push(layer); 
    trend.push({ 
      date: dateStr, 
      ndvi,
      ndmi,
      evi: layer.evi || (ndvi * 0.9),
      savi: layer.savi || (ndvi * 0.75)
    });
  }

  return {
    lastUpdated: format(today, 'yyyy-MM-dd'),
    layers,
    trend: trend.reverse(),
    productivityZones: { high: 35, medium: 45, low: 20 },
    isSimulation: true,
    debugInfo: `Fallback: ${debugInfo}`,
  };
}
