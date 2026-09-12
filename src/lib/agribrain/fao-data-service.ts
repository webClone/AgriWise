"use server";

// ============================================================================
// FIELD-LEVEL PROVENANCE TRACKING (v5.1)
// ============================================================================
export type SoilFieldSource =
  | "soilgrids"
  | "user_declared"
  | "snapshot"
  | "fallback_default"
  | "missing";

export interface SoilDataCompleteness {
  requiredFields: string[];
  presentFields: string[];
  missingFields: string[];
  fallbackFields: string[];
  soilgridsFields: string[];
  completenessFraction: number;
  confidence: "HIGH" | "MEDIUM" | "LOW";
  fieldSources: Record<string, SoilFieldSource>;
}

export interface SuitabilityDataCompleteness {
  soil: SoilDataCompleteness;
  climate: {
    hasAnnualRainfall: boolean;
    hasMeanTemp: boolean;
    hasEt0: boolean;
    hasFrostDays: boolean;
    hasHeatDays: boolean;
    missingFields: string[];
    confidence: "HIGH" | "MEDIUM" | "LOW";
  };
  terrain: {
    hasSlope: boolean;
    hasElevation: boolean;
    confidence: "HIGH" | "MEDIUM" | "LOW";
  };
  irrigation: {
    source: "user_declared" | "plot_profile" | "default_unknown";
    confidence: "HIGH" | "MEDIUM" | "LOW";
  };
  overallSuitabilityConfidence: "HIGH" | "MEDIUM" | "LOW";
}

export interface FAOIntelligenceProfile {
  soil: {
    textureClass: string;
    clay: number; // %
    sand: number; // %
    silt: number; // %
    ph: number;
    organicCarbon: number; // %
    bulkDensity: number; // g/cm³
    cec: number; // cmol(+)/kg
    nitrogen: number; // g/kg
    cfvo: number; // % (Coarse Fragments)
    ocd: number; // kg/dm³
    ocs: number; // t/ha
    wv0033: number; // % (Field Capacity)
    wv1500: number; // % (Wilting Point)
    awc: number; // % (Available Water Capacity)
    panClass: 'None' | 'Possible Argillic' | 'Argillic Horizon'; // Stratification
    cnRatio: number; // Carbon:Nitrogen
    cecToClayRatio: number; // Mineralogy proxy
    mineralogyClass: 'Kaolinitic (Low Activity)' | 'Illitic/Mixed' | 'Smectitic (High Activity)';
    phosphorusIndex: 'Low' | 'Medium' | 'High'; // Derived from pH
    potassiumIndex: 'Low' | 'Medium' | 'High'; // Derived from CEC
    depthToBedrock: number; // cm
    fertilityClass: 'High' | 'Medium' | 'Low';
    drainageClass: 'Well Drained' | 'Moderately Well Drained' | 'Poorly Drained';
    salinity: number; // dS/m
  };
  subsoil: {
    clay: number; // % (30-100cm)
    ph: number;   // pH
    organicCarbon: number; // %
  };
  // v5.1: nullable — suitability now comes from Python engine, not frontend
  landSuitability: {
    gaezScore: number;
    suitabilityClass: 'Highly Suitable' | 'Moderately Suitable' | 'Marginally Suitable' | 'Unsuitable';
    limitingFactors: string[];
    potentialYield: number;
    attainableYield: number;
  } | null;
  water: {
    stressIndex: number; // 0-10
    scarcityClass: 'None' | 'Low' | 'Moderate' | 'High' | 'Severe';
    irrigationEfficiencyPotential: number; // %
    annualRainfall: number; // mm
  };
  // v5.1: nullable — requires real data
  climate: {
    growingDegreeDays: number;
    aridityIndex: number;
    droughtRisk: 'Low' | 'Medium' | 'High';
    erosionRisk: 'Low' | 'Moderate' | 'High' | 'Severe';
  } | null;
  // v5.1: nullable — requires real satellite data
  satellite: {
    ndvi: number;
    evi: number;
    landCoverClass: 'Cropland' | 'Grassland' | 'Shrubland' | 'Barren';
    vegetationHealth: 'Excellent' | 'Good' | 'Fair' | 'Poor';
  } | null;
  // Real-time data from Open-Meteo
  realTime?: {
    temp: number;
    humidity: number;
    soilMoisture: number; // m³/m³
    deepSoilMoisture: number; // m³/m³ (27-81cm)
    soilTemp: number; // °C
    et0: number; // mm/day
    windSpeed: number; // km/h
    solarRad: number; // W/m²
    rain: number; // mm
    vpd: number; // kPa
    leafWetness: number; // %
    elevation: number; // m
    cloudCover: number; // %
    pressure: number; // hPa
    windDir: number; // degrees
    windGusts: number; // km/h
    solarDiffuse: number; // W/m²
    solarDirect: number; // W/m²
    uvIndex: number; // index
    soilTemp18: number; // °C
    soilTemp54: number; // °C
    freezingLevel: number; // m
    visibility: number; // m
    // Agronomic Physics
    deltaT: number; // °C
    dewPoint: number; // °C
    soilTension: number; // kPa (0-30cm)
    deepSoilTension: number; // kPa (27-81cm)
  };
  // v5.1: field-level provenance tracking
  soilCompleteness: SoilDataCompleteness;
}

import { prisma } from "@/lib/db";
import { calculateDeltaT, calculateDewPoint, calculateSoilTension } from "./physics-engine";
import { buildSignedInternalHeaders } from "./internal-service-auth";

// ============================================================================
// LEGACY MOCK DATA REMOVED (v5.1)
// ============================================================================
// The following were removed in v5.1 Scientific Semantics & Provenance Hardening:
//   - CROP_REQUIREMENTS dictionary (10 hardcoded crops)
//   - DEFAULT_REQUIREMENTS constant
//   - calculateCropSuitability() function
//   - estimateCropYield() function
// Suitability is now exclusively computed by the Python CropSuitabilityEngine
// via /v2/crop-suitability. No frontend suitability scoring remains.
// ============================================================================

// Required soil fields for completeness tracking
const REQUIRED_SOIL_FIELDS = [
  'clay', 'sand', 'silt', 'ph', 'soc', 'bdod', 'cec', 'nitrogen',
  'cfvo', 'ocd', 'ocs', 'wv0033', 'wv1500'
] as const;

/**
 * Resolves land intelligence using Python backend Layer 0 components.
 * Checks DB cache (snapshot) first, falling back to local Python broker live/cached queries.
 */
export async function getFAOLandIntelligence(
  latitude: number,
  longitude: number,
  cropCode: string,
  plotId?: string
): Promise<FAOIntelligenceProfile> {
  let openMeteoData: any = null;
  let soilGridsData: any = null;
  let nasaData: any = null;

  // 1. Try to find the latest database snapshot
  let snapshot: any = null;
  try {
    let resolvedPlotId = plotId;
    let resolvedFarmId = "";
    let resolvedTenantId = "";
    if (!resolvedPlotId) {
      // Look for a plot nearby within ~1.1km
      const plot = await prisma.plot.findFirst({
        where: {
          farm: {
            latitude: { gte: latitude - 0.01, lte: latitude + 0.01 },
            longitude: { gte: longitude - 0.01, lte: longitude + 0.01 }
          }
        },
        select: { id: true, farmId: true, farm: { select: { userId: true } } }
      });
      if (plot) {
        resolvedPlotId = plot.id;
        resolvedFarmId = plot.farmId;
        resolvedTenantId = plot.farm?.userId || "";
      }
    } else {
      const plot = await prisma.plot.findUnique({
        where: { id: resolvedPlotId },
        select: { id: true, farmId: true, farm: { select: { userId: true } } }
      });
      if (plot) {
        resolvedFarmId = plot.farmId;
        resolvedTenantId = plot.farm?.userId || "";
      }
    }

    if (resolvedPlotId) {
      snapshot = await prisma.intelligenceSnapshot.findFirst({
        where: { plotId: resolvedPlotId },
        orderBy: { capturedAt: "desc" }
      });
    }
  } catch (dbErr) {
    console.warn(`[FAO Service] DB snapshot lookup failed:`, dbErr);
  }

  // 2. Read snapshot or fetch from Python backend
  if (snapshot) {
    const current = snapshot.current as any;
    openMeteoData = current?.open_meteo_agri || null;
    soilGridsData = current?.soil || null;
    nasaData = current?.nasa_power || null;
  } else {
    console.log(`[FAO Service] Cache miss. Calling Python backend for lat=${latitude}, lng=${longitude}`);
    try {
      const AGRIBRAIN_URL = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 20000);
      
      const payload = {
        lat: latitude,
        lng: longitude,
        crop: cropCode,
        days_past: 7,
        days_future: 7,
        plot_id: plotId || "system"
      };
      const bodyText = JSON.stringify(payload);
      const signedHeaders = buildSignedInternalHeaders(
        "POST",
        "/v2/plot-intelligence",
        {
          tenantId: "system",
          farmId: "system",
          plotId: (plotId || "system").trim(),
        },
        bodyText
      );

      const response = await fetch(`${AGRIBRAIN_URL}/v2/plot-intelligence`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...signedHeaders,
        },
        body: bodyText,
        signal: controller.signal
      });
      clearTimeout(timer);

      if (response.ok) {
        const json = await response.json();
        const current = json?.current;
        openMeteoData = current?.open_meteo_agri || null;
        soilGridsData = current?.soil || null;
        nasaData = current?.nasa_power || null;
      } else {
        console.warn(`[FAO Service] Backend returned status ${response.status}`);
      }
    } catch (err: any) {
      console.warn(`[FAO Service] Failed to call Python backend: ${err.message || err}`);
    }
  }

  // Deterministic "random" generation (FALLBACK ONLY)
  const seed = Math.abs(latitude * 100 + longitude * 100);
  
  // 1. PROCESS SOIL DATA (Prioritize SoilGrids > Fallback Simulation)
  let clay, sand, silt, ph, organicCarbon, bulkDensity, cec, nitrogen, cfvo, ocd, ocs, wv0033, wv1500, awc;
  let clay_sub, ph_sub, soc_sub;

  if (soilGridsData) {
      clay = soilGridsData.clay ?? (latitude > 35 ? 30.0 : 15.0);
      sand = soilGridsData.sand ?? (latitude > 35 ? 20.0 : 70.0);
      silt = soilGridsData.silt ?? (latitude > 35 ? 50.0 : 15.0);
      ph = soilGridsData.ph ?? 7.0;
      organicCarbon = (soilGridsData.soc ?? soilGridsData.organic_carbon ?? 5.0);
      bulkDensity = soilGridsData.bdod ?? 1.4;
      cec = soilGridsData.cec ?? 15.0;
      nitrogen = soilGridsData.nitrogen ?? 0.1;
      cfvo = soilGridsData.cfvo ?? 5.0;
      ocd = soilGridsData.ocd ?? 3.0;
      ocs = soilGridsData.ocs ?? 40.0;
      wv0033 = soilGridsData.wv0033 ?? 28.0;
      wv1500 = soilGridsData.wv1500 ?? 14.0;
      awc = wv0033 - wv1500;
      clay_sub = soilGridsData.clay_sub ?? (clay + 5.0);
      ph_sub = soilGridsData.ph_sub ?? (ph + 0.2);
      soc_sub = soilGridsData.soc_sub ?? (organicCarbon * 0.6);
  } else {
      // Fallback
      if (latitude > 35) { clay = 30; sand = 20; silt = 50; } 
      else { sand = 70; clay = 15; silt = 15; }
      ph = 7.0; organicCarbon = 0.5; bulkDensity = 1.4; cec = 15; nitrogen = 0.1;
      cfvo = 5; ocd = 3.0; ocs = 40;
      cfvo = 5; ocd = 3.0; ocs = 40;
      wv0033 = 28; wv1500 = 14; awc = 14; // Typical Loam values
      clay_sub = clay + 5; ph_sub = ph + 0.2; soc_sub = organicCarbon * 0.6; // Typical depth trends
  }

  // --- DERIVED CHEMICAL INDICES ---
  // Fix: SOC is g/kg, display expects %.
  const organicCarbonPct = organicCarbon / 10; 
  const subsoilCarbonPct = soc_sub / 10;

  // C:N Ratio (Both g/kg)
  const cnRatio = nitrogen > 0 ? organicCarbon / nitrogen : 10;
  
  // CEC Ratio (cmol/kg / %)
  // Kaolinite (~0.1-0.2), Illite (~0.3-0.5), Smectite (>0.7)
  const cecRatio = clay > 0 ? cec / clay : 0.5;
  const mineralogyClass = 
    cecRatio < 0.3 ? 'Kaolinitic (Low Activity)' :
    cecRatio > 0.7 ? 'Smectitic (High Activity)' : 
    'Illitic/Mixed';
    
  // Nutrient Availability Modeling
  // Phosphorus: Optimal 6.0 - 7.5. Fixed by Fe/Al at low pH, Ca at high pH.
  const phosphorusIndex = 
      ph < 5.5 ? 'Low' : 
      ph > 8.5 ? 'Low' : 
      (ph >= 6.0 && ph <= 7.5) ? 'High' : 'Medium';

  // Potassium: Linked to CEC (buffering capacity). Low CEC = leaching risk.
  const potassiumIndex = 
      cec < 10 ? 'Low' : 
      cec > 20 ? 'High' : 'Medium';

  // Stratification Analysis
  const panClass = (clay_sub - clay) > 8 ? 'Argillic Horizon' : (clay_sub - clay) > 3 ? 'Possible Argillic' : 'None';

  const textureClass = 
    sand > 60 ? 'Sandy Loam' :
    clay > 35 ? 'Clay Loam' :
    'Loam';
  
  // 2. GENERATE WATER & CLIMATE (Prioritize NASA > Fallback) - BEFORE suitability calc
  const annualRainfall = nasaData?.annualRainfall || (latitude < 32 ? 50 : 500);
  const stressIndex = nasaData?.droughtRiskIndex || 5;
  const scarcityClass = stressIndex > 8 ? 'Severe' : stressIndex > 5 ? 'High' : 'Low';

  // 4. SATELLITE DATA — v5.1: removed mock values
  // Real satellite data must come from L1/L2 layers, not hardcoded constants.
  // Returning null until real satellite integration is available.
  const satellite = null;

  // 5. LAND SUITABILITY — v5.1: removed frontend suitability calculator
  // Suitability is now exclusively computed by the Python CropSuitabilityEngine.
  // The FAO intelligence profile returns null for landSuitability.
  const landSuitability = null;

  // 6. CLIMATE — v5.1: removed hardcoded values
  // Real climate data must come from L0 broker sources.
  const climate = nasaData ? {
    growingDegreeDays: nasaData.gdd ?? 0,
    aridityIndex: annualRainfall > 0 ? parseFloat((annualRainfall / Math.max(1, (openMeteoData?.current?.temperature_2m ?? 20) + 10)).toFixed(2)) : 0,
    droughtRisk: (stressIndex > 7 ? 'High' : stressIndex > 4 ? 'Medium' : 'Low') as 'Low' | 'Medium' | 'High',
    erosionRisk: 'Low' as const,
  } : null;

  // Process Real Data (Open-Meteo)
  let realTimeData = undefined;
  if (openMeteoData && openMeteoData.current) {
    const cur = openMeteoData.current;
    const daily_et0 = openMeteoData.daily?.et0_fao_evapotranspiration?.[0] || 0;
    
    realTimeData = {
      temp: cur.temperature_2m ?? 20,
      humidity: cur.relative_humidity_2m ?? 60,
      soilMoisture: cur.soil_moisture_3_to_9cm ?? 0.2,
      deepSoilMoisture: cur.soil_moisture_27_to_81cm ?? 0.2,
      soilTemp: cur.soil_temperature_0cm ?? 20,
      et0: daily_et0,
      windSpeed: cur.wind_speed_10m ?? 0,
      solarRad: cur.shortwave_radiation ?? 0,
      rain: cur.rain ?? 0,
      vpd: cur.vapor_pressure_deficit ?? 0,
      leafWetness: cur.leaf_wetness_probability ?? 0,
      elevation: openMeteoData.elevation ?? 0,
      cloudCover: cur.cloud_cover ?? 0,
      pressure: cur.surface_pressure ?? 1013,
      windDir: cur.wind_direction_10m ?? 0,
      windGusts: cur.wind_gusts_10m ?? 0,
      solarDiffuse: cur.diffuse_radiation ?? 0,
      solarDirect: cur.direct_normal_irradiance ?? 0,
      uvIndex: cur.uv_index ?? 0,
      soilTemp18: cur.soil_temperature_18cm ?? 0,
      soilTemp54: cur.soil_temperature_54cm ?? 0,
      freezingLevel: cur.freezing_level_height ?? 0,
      visibility: cur.visibility ?? 10000,
      
      // Derived Physics
      deltaT: calculateDeltaT(cur.temperature_2m ?? 20, cur.relative_humidity_2m ?? 60),
      dewPoint: calculateDewPoint(cur.temperature_2m ?? 20, cur.relative_humidity_2m ?? 60),
      soilTension: calculateSoilTension(cur.soil_moisture_3_to_9cm ?? 0.2, clay, sand),
      deepSoilTension: calculateSoilTension(cur.soil_moisture_27_to_81cm ?? 0.2, clay, sand)
    };
  }

  // 7. BUILD SOIL DATA COMPLETENESS (v5.1)
  const fieldSources: Record<string, SoilFieldSource> = {};
  const soilFieldMap: Record<string, any> = {
    clay: soilGridsData?.clay,
    sand: soilGridsData?.sand,
    silt: soilGridsData?.silt,
    ph: soilGridsData?.ph,
    soc: soilGridsData?.soc ?? soilGridsData?.organic_carbon,
    bdod: soilGridsData?.bdod,
    cec: soilGridsData?.cec,
    nitrogen: soilGridsData?.nitrogen,
    cfvo: soilGridsData?.cfvo,
    ocd: soilGridsData?.ocd,
    ocs: soilGridsData?.ocs,
    wv0033: soilGridsData?.wv0033,
    wv1500: soilGridsData?.wv1500,
  };
  const presentFields: string[] = [];
  const missingFields: string[] = [];
  const fallbackFields: string[] = [];
  const soilgridsFields: string[] = [];

  for (const f of REQUIRED_SOIL_FIELDS) {
    if (soilGridsData && soilFieldMap[f] != null) {
      fieldSources[f] = "soilgrids";
      presentFields.push(f);
      soilgridsFields.push(f);
    } else if (soilGridsData) {
      // SoilGrids was available but this specific field was missing
      fieldSources[f] = "fallback_default";
      fallbackFields.push(f);
    } else {
      fieldSources[f] = "fallback_default";
      fallbackFields.push(f);
    }
  }
  const completenessFraction = REQUIRED_SOIL_FIELDS.length > 0
    ? presentFields.length / REQUIRED_SOIL_FIELDS.length
    : 0;
  const soilConfidence: "HIGH" | "MEDIUM" | "LOW" =
    completenessFraction >= 0.85 ? "HIGH" :
    completenessFraction >= 0.5 ? "MEDIUM" : "LOW";

  const soilCompleteness: SoilDataCompleteness = {
    requiredFields: [...REQUIRED_SOIL_FIELDS],
    presentFields,
    missingFields: REQUIRED_SOIL_FIELDS.filter(f => !presentFields.includes(f)),
    fallbackFields,
    soilgridsFields,
    completenessFraction: parseFloat(completenessFraction.toFixed(2)),
    confidence: soilConfidence,
    fieldSources,
  };

  return {
    soil: {
      textureClass,
      clay: parseFloat((clay ?? 25.0).toFixed(1)),
      sand: parseFloat((sand ?? 40.0).toFixed(1)),
      silt: parseFloat((silt ?? 35.0).toFixed(1)),
      ph: parseFloat((ph ?? 7.0).toFixed(1)),
      organicCarbon: parseFloat((organicCarbonPct ?? 2.0).toFixed(2)),
      bulkDensity: parseFloat((bulkDensity ?? 1.4).toFixed(2)),
      cec: parseFloat((cec ?? 15.0).toFixed(1)),
      nitrogen: parseFloat((nitrogen ?? 0.1).toFixed(2)),
      cfvo: parseFloat((cfvo ?? 5.0).toFixed(1)),
      ocd: parseFloat((ocd ?? 3.0).toFixed(1)),
      ocs: parseFloat((ocs ?? 40.0).toFixed(1)),
      wv0033: parseFloat((wv0033 ?? 28.0).toFixed(1)),
      wv1500: parseFloat((wv1500 ?? 14.0).toFixed(1)),
      awc: parseFloat((awc ?? 14.0).toFixed(1)),
      panClass,
      cnRatio: parseFloat((cnRatio ?? 10.0).toFixed(1)),
      cecToClayRatio: parseFloat((cecRatio ?? 0.5).toFixed(2)),
      mineralogyClass,
      phosphorusIndex,
      potassiumIndex,
      depthToBedrock: 150,
      fertilityClass: (cec ?? 15.0) > 20 ? 'High' : 'Medium',
      drainageClass: (bulkDensity ?? 1.4) < 1.4 ? 'Well Drained' : 'Moderately Well Drained',
      salinity: 0.5,
    },
    subsoil: {
      clay: parseFloat((clay_sub ?? 30.0).toFixed(1)),
      ph: parseFloat((ph_sub ?? 7.2).toFixed(1)),
      organicCarbon: parseFloat((subsoilCarbonPct ?? 1.2).toFixed(2)),
    },
    landSuitability,  // v5.1: null — from Python engine now
    water: {
      stressIndex: Math.floor(stressIndex),
      scarcityClass,
      irrigationEfficiencyPotential: 85,
      annualRainfall: Math.floor(annualRainfall),
    },
    climate,  // v5.1: null when NASA data unavailable
    satellite,  // v5.1: null — requires real L1/L2 data
    realTime: realTimeData,
    soilCompleteness,  // v5.1: field-level provenance
  };
}
