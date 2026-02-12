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
  landSuitability: {
    gaezScore: number; // 0-100
    suitabilityClass: 'Highly Suitable' | 'Moderately Suitable' | 'Marginally Suitable' | 'Unsuitable';
    limitingFactors: string[];
    potentialYield: number; // tonnes/ha (rainfed)
    attainableYield: number; // tonnes/ha (irrigated)
  };
  water: {
    stressIndex: number; // 0-10
    scarcityClass: 'None' | 'Low' | 'Moderate' | 'High' | 'Severe';
    irrigationEfficiencyPotential: number; // %
    annualRainfall: number; // mm
  };
  climate: {
    growingDegreeDays: number;
    aridityIndex: number;
    droughtRisk: 'Low' | 'Medium' | 'High';
    erosionRisk: 'Low' | 'Moderate' | 'High' | 'Severe'; // t/ha/yr proxy
  };
  satellite: {
    ndvi: number; // 0-1 (Normalized Difference Vegetation Index)
    evi: number; // Encahnced Vegetation Index
    landCoverClass: 'Cropland' | 'Grassland' | 'Shrubland' | 'Barren';
    vegetationHealth: 'Excellent' | 'Good' | 'Fair' | 'Poor';
  };
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
}

import { fetchOpenMeteoAgriData } from "./open-meteo-service";
import { fetchSoilGridsData } from "./soilgrids-service";
import { fetchNASAPowerData } from "./nasa-power-service";
import { calculateDeltaT, calculateDewPoint, calculateSoilTension } from "./physics-engine";

// ============================================================================
// CROP REQUIREMENTS DATABASE
// ============================================================================
interface CropRequirements {
  optimalPH: { min: number; max: number };
  optimalTextures: string[];
  waterNeeds: 'low' | 'medium' | 'high';
  baseYield: number; // t/ha
  irrigatedBonus: number; // t/ha
  minRainfall: number; // mm/year
}

const CROP_REQUIREMENTS: Record<string, CropRequirements> = {
  wheat:      { optimalPH: { min: 6.0, max: 7.5 }, optimalTextures: ['Loam', 'Clay Loam'], waterNeeds: 'medium', baseYield: 3.5, irrigatedBonus: 2.0, minRainfall: 350 },
  barley:     { optimalPH: { min: 6.0, max: 8.0 }, optimalTextures: ['Loam', 'Sandy Loam'], waterNeeds: 'low', baseYield: 2.8, irrigatedBonus: 1.5, minRainfall: 250 },
  olive:      { optimalPH: { min: 6.0, max: 8.5 }, optimalTextures: ['Loam', 'Clay Loam', 'Sandy Loam'], waterNeeds: 'low', baseYield: 4.0, irrigatedBonus: 2.0, minRainfall: 300 },
  date:       { optimalPH: { min: 7.0, max: 8.5 }, optimalTextures: ['Sandy Loam', 'Loam'], waterNeeds: 'medium', baseYield: 8.0, irrigatedBonus: 4.0, minRainfall: 100 },
  potato:     { optimalPH: { min: 5.5, max: 6.5 }, optimalTextures: ['Loam', 'Sandy Loam'], waterNeeds: 'high', baseYield: 25.0, irrigatedBonus: 10.0, minRainfall: 500 },
  tomato:     { optimalPH: { min: 6.0, max: 7.0 }, optimalTextures: ['Loam', 'Sandy Loam'], waterNeeds: 'high', baseYield: 40.0, irrigatedBonus: 20.0, minRainfall: 500 },
  chickpea:   { optimalPH: { min: 6.5, max: 7.5 }, optimalTextures: ['Loam', 'Clay Loam'], waterNeeds: 'low', baseYield: 1.5, irrigatedBonus: 0.8, minRainfall: 350 },
  lentil:     { optimalPH: { min: 6.0, max: 7.5 }, optimalTextures: ['Loam', 'Clay Loam'], waterNeeds: 'low', baseYield: 1.2, irrigatedBonus: 0.5, minRainfall: 300 },
  onion:      { optimalPH: { min: 6.0, max: 7.0 }, optimalTextures: ['Loam', 'Sandy Loam'], waterNeeds: 'medium', baseYield: 30.0, irrigatedBonus: 15.0, minRainfall: 400 },
  watermelon: { optimalPH: { min: 6.0, max: 7.0 }, optimalTextures: ['Sandy Loam', 'Loam'], waterNeeds: 'high', baseYield: 35.0, irrigatedBonus: 15.0, minRainfall: 400 },
};

// Default requirements for unknown crops
const DEFAULT_REQUIREMENTS: CropRequirements = {
  optimalPH: { min: 6.0, max: 7.5 },
  optimalTextures: ['Loam'],
  waterNeeds: 'medium',
  baseYield: 5.0,
  irrigatedBonus: 2.0,
  minRainfall: 400
};

// ============================================================================
// CROP SUITABILITY CALCULATOR
// ============================================================================
function calculateCropSuitability(
  cropCode: string,
  soil: { textureClass: string; ph: number; awc: number },
  water: { stressIndex: number; annualRainfall: number }
): { score: number; suitabilityClass: 'Highly Suitable' | 'Moderately Suitable' | 'Marginally Suitable' | 'Unsuitable'; limitingFactors: string[] } {
  
  const reqs = CROP_REQUIREMENTS[cropCode] || DEFAULT_REQUIREMENTS;
  const limitingFactors: string[] = [];
  let score = 100;

  // 1. pH Compatibility (30 points max penalty)
  if (soil.ph < reqs.optimalPH.min) {
    const deficit = reqs.optimalPH.min - soil.ph;
    score -= Math.min(30, deficit * 15);
    limitingFactors.push(`Soil pH too acidic (${soil.ph} < ${reqs.optimalPH.min})`);
  } else if (soil.ph > reqs.optimalPH.max) {
    const excess = soil.ph - reqs.optimalPH.max;
    score -= Math.min(30, excess * 15);
    limitingFactors.push(`Soil pH too alkaline (${soil.ph} > ${reqs.optimalPH.max})`);
  }

  // 2. Texture Compatibility (20 points max penalty)
  if (!reqs.optimalTextures.includes(soil.textureClass)) {
    score -= 20;
    limitingFactors.push(`Suboptimal soil texture (${soil.textureClass})`);
  }

  // 3. Water Availability (30 points max penalty)
  const waterNeedsMap = { low: 3, medium: 5, high: 7 };
  const cropWaterScore = waterNeedsMap[reqs.waterNeeds];
  
  if (water.stressIndex > cropWaterScore) {
    const waterDeficit = water.stressIndex - cropWaterScore;
    score -= Math.min(30, waterDeficit * 10);
    limitingFactors.push(`Water stress too high for ${reqs.waterNeeds}-water crop`);
  }

  // 4. Rainfall Check (20 points max penalty)
  if (water.annualRainfall < reqs.minRainfall) {
    const rainfallDeficit = (reqs.minRainfall - water.annualRainfall) / reqs.minRainfall;
    score -= Math.min(20, rainfallDeficit * 40);
    limitingFactors.push(`Insufficient rainfall (${water.annualRainfall}mm < ${reqs.minRainfall}mm)`);
  }

  // Clamp score
  score = Math.max(0, Math.min(100, Math.round(score)));

  // Determine class
  const suitabilityClass = 
    score >= 80 ? 'Highly Suitable' :
    score >= 60 ? 'Moderately Suitable' :
    score >= 40 ? 'Marginally Suitable' : 'Unsuitable';

  return { score, suitabilityClass, limitingFactors: limitingFactors.length ? limitingFactors : ['None'] };
}

// ============================================================================
// CROP YIELD ESTIMATOR
// ============================================================================
function estimateCropYield(
  cropCode: string,
  suitabilityScore: number
): { potentialYield: number; attainableYield: number } {
  const reqs = CROP_REQUIREMENTS[cropCode] || DEFAULT_REQUIREMENTS;
  
  // Scale yield by suitability (0-100 → 0.4-1.0 multiplier)
  const yieldMultiplier = 0.4 + (suitabilityScore / 100) * 0.6;
  
  const potentialYield = parseFloat((reqs.baseYield * yieldMultiplier).toFixed(1));
  const attainableYield = parseFloat(((reqs.baseYield + reqs.irrigatedBonus) * yieldMultiplier).toFixed(1));
  
  return { potentialYield, attainableYield };
}

/**
 * Mocks fetching data from FAO SoilGrids, GAEZ, and AQUASTAT based on location.
 * Now UPGRADED to fetch REAL data from Open-Meteo, SoiIGrids, and NASA POWER.
 */
export async function getFAOLandIntelligence(
  latitude: number,
  longitude: number,
  cropCode: string
): Promise<FAOIntelligenceProfile> {
  // Parallel execution: ALL Providers
  const [openMeteoData, soilGridsData, nasaData] = await Promise.all([
    fetchOpenMeteoAgriData(latitude, longitude),
    fetchSoilGridsData(latitude, longitude),
    fetchNASAPowerData(latitude, longitude),
    // Keep a small delay just to prevent instant-flicker if APIs are too fast (UX)
    new Promise(resolve => setTimeout(resolve, 600))
  ]);

  // Deterministic "random" generation (FALLBACK ONLY)
  const seed = Math.abs(latitude * 100 + longitude * 100);
  
  // 1. PROCESS SOIL DATA (Prioritize SoilGrids > Fallback Simulation)
  let clay, sand, silt, ph, organicCarbon, bulkDensity, cec, nitrogen, cfvo, ocd, ocs, wv0033, wv1500, awc;
  let clay_sub, ph_sub, soc_sub;

  if (soilGridsData) {
      clay = soilGridsData.clay;
      sand = soilGridsData.sand;
      silt = soilGridsData.silt;
      ph = soilGridsData.ph;
      organicCarbon = soilGridsData.soc;
      bulkDensity = soilGridsData.bdod;
      cec = soilGridsData.cec;
      nitrogen = soilGridsData.nitrogen;
      cfvo = soilGridsData.cfvo;
      ocd = soilGridsData.ocd;
      ocs = soilGridsData.ocs;
      wv0033 = soilGridsData.wv0033;
      wv1500 = soilGridsData.wv1500;
      wv0033 = soilGridsData.wv0033;
      wv1500 = soilGridsData.wv1500;
      awc = wv0033 - wv1500; // Derived Available Water Capacity
      clay_sub = soilGridsData.clay_sub;
      ph_sub = soilGridsData.ph_sub;
      soc_sub = soilGridsData.soc_sub;
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

  // 3. CALCULATE CROP-SPECIFIC SUITABILITY
  const suitabilityResult = calculateCropSuitability(
    cropCode,
    { textureClass, ph, awc },
    { stressIndex, annualRainfall }
  );
  const { score: gaezScore, suitabilityClass, limitingFactors } = suitabilityResult;
  
  // 4. ESTIMATE CROP-SPECIFIC YIELD
  const yieldResult = estimateCropYield(cropCode, gaezScore);
  const { potentialYield, attainableYield } = yieldResult;

  
  // 4. GENERATE SATELLITE DATA (Mocked for now)
  const ndvi = 0.45;
  const evi = 0.3;
  const landCoverClass = 'Cropland';
  const vegetationHealth = 'Good';

  // Process Real Data (Open-Meteo)
  let realTimeData = undefined;
  if (openMeteoData) {
    realTimeData = {
      temp: openMeteoData.current.temperature_2m,
      humidity: openMeteoData.current.relative_humidity_2m,
      soilMoisture: openMeteoData.current.soil_moisture_3_to_9cm, // Root zone start
      deepSoilMoisture: openMeteoData.current.soil_moisture_27_to_81cm, // Deep root zone
      soilTemp: openMeteoData.current.soil_temperature_0cm,
      et0: openMeteoData.daily.et0_fao_evapotranspiration[0] || 0,
      windSpeed: openMeteoData.current.wind_speed_10m,
      solarRad: openMeteoData.current.shortwave_radiation,
      rain: openMeteoData.current.rain,
      vpd: openMeteoData.current.vapor_pressure_deficit || 0,
      leafWetness: openMeteoData.current.leaf_wetness_probability || 0,
      elevation: openMeteoData.elevation || 0,
      cloudCover: openMeteoData.current.cloud_cover,
      pressure: openMeteoData.current.surface_pressure,
      windDir: openMeteoData.current.wind_direction_10m,
      windGusts: openMeteoData.current.wind_gusts_10m,
      solarDiffuse: openMeteoData.current.diffuse_radiation || 0,
      solarDirect: openMeteoData.current.direct_normal_irradiance || 0,
      uvIndex: openMeteoData.current.uv_index || 0,
      soilTemp18: openMeteoData.current.soil_temperature_18cm || 0,
      soilTemp54: openMeteoData.current.soil_temperature_54cm || 0,
      freezingLevel: openMeteoData.current.freezing_level_height || 0,
      visibility: openMeteoData.current.visibility || 10000,
      
      // Derived Physics
      deltaT: calculateDeltaT(openMeteoData.current.temperature_2m, openMeteoData.current.relative_humidity_2m),
      dewPoint: calculateDewPoint(openMeteoData.current.temperature_2m, openMeteoData.current.relative_humidity_2m),
      soilTension: calculateSoilTension(openMeteoData.current.soil_moisture_3_to_9cm, clay, sand),
      deepSoilTension: calculateSoilTension(openMeteoData.current.soil_moisture_27_to_81cm, clay, sand)
    };
  }

  return {
    soil: {
      textureClass,
      clay: parseFloat(clay.toFixed(1)),
      sand: parseFloat(sand.toFixed(1)),
      silt: parseFloat(silt.toFixed(1)),
      ph: parseFloat(ph.toFixed(1)),
      organicCarbon: parseFloat(organicCarbonPct.toFixed(2)), // Corrected to %
      bulkDensity: parseFloat(bulkDensity.toFixed(2)),
      cec: parseFloat(cec.toFixed(1)),
      nitrogen: parseFloat(nitrogen.toFixed(2)),
      cfvo: parseFloat(cfvo.toFixed(1)), // %
      ocd: parseFloat(ocd.toFixed(1)), // kg/dm³
      ocs: parseFloat(ocs.toFixed(1)), // t/ha
      wv0033: parseFloat(wv0033.toFixed(1)), // %
      wv1500: parseFloat(wv1500.toFixed(1)), // %
      awc: parseFloat(awc.toFixed(1)), // %
      panClass,
      cnRatio: parseFloat(cnRatio.toFixed(1)),
      cecToClayRatio: parseFloat(cecRatio.toFixed(2)),
      mineralogyClass,
      phosphorusIndex,
      potassiumIndex,
      depthToBedrock: 150, // Mock
      fertilityClass: cec > 20 ? 'High' : 'Medium',
      drainageClass: bulkDensity < 1.4 ? 'Well Drained' : 'Moderately Well Drained',
      salinity: 0.5, // Mock
    },
    subsoil: {
      clay: parseFloat(clay_sub.toFixed(1)),
      ph: parseFloat(ph_sub.toFixed(1)),
      organicCarbon: parseFloat(subsoilCarbonPct.toFixed(2)), // Corrected to %
    },
    landSuitability: {
      gaezScore,
      suitabilityClass,
      limitingFactors,
      potentialYield,
      attainableYield,
    },
    water: {
      stressIndex: Math.floor(stressIndex),
      scarcityClass,
      irrigationEfficiencyPotential: 85,
      annualRainfall: Math.floor(annualRainfall),
    },
    climate: {
      growingDegreeDays: 2000,
      aridityIndex: 0.5,
      droughtRisk: stressIndex > 7 ? 'High' : 'Low',
      erosionRisk: 'Low',
    },
    satellite: {
      ndvi,
      evi,
      landCoverClass,
      vegetationHealth
    },
    realTime: realTimeData
  };
}
