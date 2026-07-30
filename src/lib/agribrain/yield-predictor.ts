// AgriBrain - Yield Prediction Module
// Estimates crop yield based on weather, inputs, and historical data

import { wilayaCoordinates } from "../weather";

// Crop yield factors by type (quintals per hectare base yield)
const baseYields: Record<string, { min: number; max: number; optimal: number }> = {
  wheat: { min: 10, max: 35, optimal: 25 },
  barley: { min: 8, max: 30, optimal: 22 },
  potato: { min: 150, max: 350, optimal: 280 },
  tomato: { min: 200, max: 500, optimal: 380 },
  olive: { min: 15, max: 50, optimal: 35 },
  date: { min: 40, max: 100, optimal: 70 },
  onion: { min: 150, max: 350, optimal: 250 },
  pepper: { min: 100, max: 250, optimal: 180 },
  citrus: { min: 100, max: 200, optimal: 150 },
  grape: { min: 50, max: 120, optimal: 90 },
};

// Regional yield multipliers based on climate
const regionalMultipliers: Record<string, number> = {
  // Northern (Mediterranean) - best for most crops
  "16": 1.15, // Algiers
  "09": 1.12, // Blida
  "42": 1.10, // Tipaza
  "06": 1.08, // Béjaïa
  "15": 1.05, // Tizi Ouzou
  // Highland plateaus - good for cereals
  "17": 1.10, // Djelfa
  "05": 1.05, // Batna
  "19": 1.08, // Sétif
  "34": 1.00, // Bordj Bou Arreridj
  // Saharan - dates thrive
  "30": 0.60, // Ouargla (general), 1.5 for dates
  "39": 0.55, // El Oued
  "47": 0.50, // Ghardaia
  "07": 0.70, // Biskra
};

interface YieldPredictionInput {
  cropCode: string;
  plotArea: number; // hectares
  wilayaCode: string;
  plantDate: Date;
  irrigationType?: string; // drip, flood, pivot, rainfed
  soilType?: string; // clay, sandy, loamy
  fertilizerUsed?: boolean;
  pestControlApplied?: boolean;
  weatherConditions?: {
    avgTemp: number;
    totalRainfall: number;
    extremeEvents: number;
  };
}

interface YieldPrediction {
  estimatedYield: number; // quintals
  yieldPerHectare: number; // quintals/ha
  confidence: "low" | "medium" | "high";
  factors: {
    name: string;
    nameAr: string;
    impact: "positive" | "negative" | "neutral";
    value: string;
  }[];
  recommendations: string[];
  recommendationsAr: string[];
}

export function predictYield(input: YieldPredictionInput): YieldPrediction {
  const base = baseYields[input.cropCode] || baseYields.wheat;
  let yieldMultiplier = 1.0;
  const factors: YieldPrediction["factors"] = [];
  const recommendations: string[] = [];
  const recommendationsAr: string[] = [];
  
  // Base yield starts at optimal
  let yieldPerHectare = base.optimal;
  
  // 1. Regional factor
  const regionalFactor = regionalMultipliers[input.wilayaCode] || 0.85;
  
  // Special case for dates in Saharan regions
  if (input.cropCode === "date" && ["30", "39", "47", "07", "33"].includes(input.wilayaCode)) {
    yieldMultiplier *= 1.3;
    factors.push({
      name: "Ideal region for dates",
      nameAr: "منطقة مثالية للتمور",
      impact: "positive",
      value: "+30%",
    });
  } else {
    yieldMultiplier *= regionalFactor;
    if (regionalFactor >= 1.0) {
      factors.push({
        name: "Favorable region",
        nameAr: "منطقة ملائمة",
        impact: "positive",
        value: `+${Math.round((regionalFactor - 1) * 100)}%`,
      });
    } else {
      factors.push({
        name: "Challenging climate",
        nameAr: "مناخ صعب",
        impact: "negative",
        value: `${Math.round((regionalFactor - 1) * 100)}%`,
      });
      recommendationsAr.push("فكر في أصناف مقاومة للجفاف");
      recommendations.push("Consider drought-resistant varieties");
    }
  }
  
  // 2. Irrigation factor
  const irrigationFactors: Record<string, number> = {
    drip: 1.25,
    pivot: 1.20,
    sprinkler: 1.15,
    flood: 1.0,
    rainfed: 0.7,
  };
  const irrigationFactor = irrigationFactors[input.irrigationType || "rainfed"] || 0.7;
  yieldMultiplier *= irrigationFactor;
  
  if (irrigationFactor >= 1.15) {
    factors.push({
      name: "Efficient irrigation",
      nameAr: "ري فعال",
      impact: "positive",
      value: `+${Math.round((irrigationFactor - 1) * 100)}%`,
    });
  } else if (irrigationFactor < 0.9) {
    factors.push({
      name: "Limited water",
      nameAr: "محدودية المياه",
      impact: "negative",
      value: `${Math.round((irrigationFactor - 1) * 100)}%`,
    });
    recommendationsAr.push("فكر في تركيب نظام ري بالتنقيط");
    recommendations.push("Consider installing drip irrigation");
  }
  
  // 3. Soil factor
  const soilFactors: Record<string, number> = {
    loamy: 1.10,
    clay: 0.95,
    sandy: 0.85,
    rocky: 0.70,
  };
  const soilFactor = soilFactors[input.soilType || "loamy"] || 1.0;
  yieldMultiplier *= soilFactor;
  
  if (soilFactor < 0.9) {
    factors.push({
      name: "Soil improvement needed",
      nameAr: "التربة تحتاج تحسين",
      impact: "negative",
      value: `${Math.round((soilFactor - 1) * 100)}%`,
    });
    recommendationsAr.push("أضف مواد عضوية لتحسين التربة");
    recommendations.push("Add organic matter to improve soil");
  }
  
  // 4. Fertilizer factor
  if (input.fertilizerUsed) {
    yieldMultiplier *= 1.15;
    factors.push({
      name: "Fertilizer applied",
      nameAr: "تم التسميد",
      impact: "positive",
      value: "+15%",
    });
  } else {
    recommendationsAr.push("استخدم السماد في الوقت المناسب لزيادة الإنتاج");
    recommendations.push("Apply fertilizer at optimal times");
  }
  
  // 5. Pest control factor
  if (input.pestControlApplied) {
    yieldMultiplier *= 1.10;
    factors.push({
      name: "Pest control active",
      nameAr: "مكافحة الآفات",
      impact: "positive",
      value: "+10%",
    });
  } else {
    recommendationsAr.push("راقب الآفات بانتظام");
    recommendations.push("Monitor for pests regularly");
  }
  
  // 6. Weather conditions (if provided)
  if (input.weatherConditions) {
    const { avgTemp, totalRainfall, extremeEvents } = input.weatherConditions;
    
    // Temperature impact
    if (avgTemp < 5 || avgTemp > 40) {
      yieldMultiplier *= 0.7;
      factors.push({
        name: "Extreme temperature",
        nameAr: "درجة حرارة قاسية",
        impact: "negative",
        value: "-30%",
      });
    } else if (avgTemp >= 15 && avgTemp <= 30) {
      yieldMultiplier *= 1.05;
      factors.push({
        name: "Optimal temperature",
        nameAr: "حرارة مثالية",
        impact: "positive",
        value: "+5%",
      });
    }
    
    // Extreme events
    if (extremeEvents > 3) {
      yieldMultiplier *= 0.85;
      factors.push({
        name: "Weather extremes",
        nameAr: "أحداث مناخية متطرفة",
        impact: "negative",
        value: "-15%",
      });
    }
  }
  
  // Calculate final yield
  yieldPerHectare = Math.round(base.optimal * yieldMultiplier);
  
  // Clamp to realistic range
  yieldPerHectare = Math.max(base.min, Math.min(base.max, yieldPerHectare));
  
  const estimatedYield = yieldPerHectare * input.plotArea;
  
  // Determine confidence
  let confidence: "low" | "medium" | "high" = "medium";
  if (input.weatherConditions && input.fertilizerUsed !== undefined && input.irrigationType) {
    confidence = "high";
  } else if (!input.irrigationType && !input.soilType) {
    confidence = "low";
  }
  
  return {
    estimatedYield: Math.round(estimatedYield),
    yieldPerHectare,
    confidence,
    factors,
    recommendations,
    recommendationsAr,
  };
}

// Calculate potential revenue
export function estimateRevenue(
  yieldQuintals: number, 
  cropCode: string, 
  pricePerQuintal?: number
): { minRevenue: number; maxRevenue: number; avgRevenue: number } {
  // Default prices in DZD per quintal (approximate market prices)
  const defaultPrices: Record<string, { min: number; max: number }> = {
    wheat: { min: 5000, max: 7000 },
    barley: { min: 4500, max: 6000 },
    potato: { min: 3000, max: 6000 },
    tomato: { min: 2000, max: 5000 },
    olive: { min: 15000, max: 25000 },
    date: { min: 20000, max: 50000 },
    onion: { min: 3000, max: 5000 },
  };
  
  const prices = defaultPrices[cropCode] || { min: 4000, max: 6000 };
  const usePrice = pricePerQuintal || (prices.min + prices.max) / 2;
  
  return {
    minRevenue: Math.round(yieldQuintals * prices.min),
    maxRevenue: Math.round(yieldQuintals * prices.max),
    avgRevenue: Math.round(yieldQuintals * usePrice),
  };
}
