// AgriBrain - Harvest Timing Optimizer
// Determines optimal harvest window based on crop, weather, and market

interface HarvestInput {
  cropCode: string;
  plantDate: Date;
  currentDate?: Date;
  growthStage: string;
  weatherForecast: {
    date: string;
    tempMax: number;
    tempMin: number;
    precipitationProbability: number;
    condition: string;
  }[];
  marketPrices?: {
    current: number;
    trend: "up" | "down" | "stable";
    forecast?: number;
  };
}

interface HarvestRecommendation {
  isReady: boolean;
  optimalWindowStart: Date;
  optimalWindowEnd: Date;
  daysUntilReady: number;
  harvestUrgency: "not_ready" | "can_wait" | "optimal" | "urgent" | "overdue";
  bestHarvestDay: Date | null;
  reasons: string[];
  reasonsAr: string[];
  weatherWarnings: string[];
  weatherWarningsAr: string[];
  marketAdvice?: string;
  marketAdviceAr?: string;
}

// Average growing days for crops in Algeria
const growingDays: Record<string, { min: number; optimal: number; max: number }> = {
  wheat: { min: 120, optimal: 150, max: 180 },
  barley: { min: 100, optimal: 130, max: 160 },
  potato: { min: 90, optimal: 110, max: 130 },
  tomato: { min: 60, optimal: 80, max: 100 },
  onion: { min: 100, optimal: 120, max: 150 },
  pepper: { min: 70, optimal: 90, max: 120 },
  olive: { min: 180, optimal: 200, max: 240 },
  date: { min: 150, optimal: 180, max: 210 },
  citrus: { min: 240, optimal: 280, max: 320 },
  grape: { min: 150, optimal: 170, max: 200 },
};

export function calculateHarvestTiming(input: HarvestInput): HarvestRecommendation {
  const now = input.currentDate || new Date();
  const plantDate = new Date(input.plantDate);
  const daysSincePlanting = Math.floor((now.getTime() - plantDate.getTime()) / (1000 * 60 * 60 * 24));
  
  const crop = growingDays[input.cropCode] || growingDays.wheat;
  
  // Calculate optimal harvest window
  const optimalStart = new Date(plantDate);
  optimalStart.setDate(optimalStart.getDate() + crop.min);
  
  const optimalEnd = new Date(plantDate);
  optimalEnd.setDate(optimalEnd.getDate() + crop.max);
  
  const optimalPeak = new Date(plantDate);
  optimalPeak.setDate(optimalPeak.getDate() + crop.optimal);
  
  // Determine readiness
  const daysUntilReady = crop.min - daysSincePlanting;
  const isReady = daysSincePlanting >= crop.min;
  const isPastOptimal = daysSincePlanting > crop.optimal;
  const isOverdue = daysSincePlanting > crop.max;
  
  // Determine urgency
  let harvestUrgency: HarvestRecommendation["harvestUrgency"] = "not_ready";
  if (isOverdue) {
    harvestUrgency = "overdue";
  } else if (isPastOptimal) {
    harvestUrgency = "urgent";
  } else if (daysSincePlanting >= crop.min && daysSincePlanting <= crop.optimal) {
    harvestUrgency = "optimal";
  } else if (daysUntilReady <= 7) {
    harvestUrgency = "can_wait";
  }
  
  const reasons: string[] = [];
  const reasonsAr: string[] = [];
  const weatherWarnings: string[] = [];
  const weatherWarningsAr: string[] = [];
  
  // Add readiness reasons
  if (!isReady) {
    reasons.push(`Crop needs ${daysUntilReady} more days to mature`);
    reasonsAr.push(`المحصول يحتاج ${daysUntilReady} يوم إضافي للنضج`);
  } else if (harvestUrgency === "optimal") {
    reasons.push("Crop is at optimal maturity for harvest");
    reasonsAr.push("المحصول في النضج الأمثل للحصاد");
  } else if (harvestUrgency === "urgent") {
    reasons.push("Harvest soon to prevent quality loss");
    reasonsAr.push("احصد قريباً لمنع فقدان الجودة");
  } else if (harvestUrgency === "overdue") {
    reasons.push("Harvest immediately - quality is decreasing");
    reasonsAr.push("احصد فوراً - الجودة تتناقص");
  }
  
  // Analyze weather forecast for best harvest day
  let bestDay: Date | null = null;
  let bestScore = -1;
  
  for (const day of input.weatherForecast) {
    let score = 100;
    const dayDate = new Date(day.date);
    
    // Skip days before crop is ready
    const daysSincePlant = Math.floor((dayDate.getTime() - plantDate.getTime()) / (1000 * 60 * 60 * 24));
    if (daysSincePlant < crop.min) continue;
    
    // Penalize rain
    if (day.precipitationProbability > 50) {
      score -= 40;
      if (!weatherWarnings.includes("Avoid harvesting during rain")) {
        weatherWarnings.push("Avoid harvesting during rain");
        weatherWarningsAr.push("تجنب الحصاد أثناء المطر");
      }
    } else if (day.precipitationProbability > 30) {
      score -= 20;
    }
    
    // Penalize extreme heat
    if (day.tempMax > 40) {
      score -= 30;
      if (!weatherWarnings.includes("Harvest in early morning to avoid heat")) {
        weatherWarnings.push("Harvest in early morning to avoid heat");
        weatherWarningsAr.push("احصد في الصباح الباكر لتجنب الحرارة");
      }
    }
    
    // Penalize cold (for some crops)
    if (day.tempMin < 5 && ["tomato", "pepper", "date"].includes(input.cropCode)) {
      score -= 25;
    }
    
    // Prefer days within optimal window
    if (daysSincePlant >= crop.min && daysSincePlant <= crop.optimal) {
      score += 20;
    }
    
    // Check for best day
    if (score > bestScore) {
      bestScore = score;
      bestDay = dayDate;
    }
  }
  
  // Market advice
  let marketAdvice: string | undefined;
  let marketAdviceAr: string | undefined;
  
  if (input.marketPrices) {
    if (input.marketPrices.trend === "up" && harvestUrgency !== "overdue") {
      marketAdvice = "Prices trending up - consider waiting a few days if crop allows";
      marketAdviceAr = "الأسعار في ارتفاع - فكر في الانتظار بضعة أيام إذا سمح المحصول";
    } else if (input.marketPrices.trend === "down" && isReady) {
      marketAdvice = "Prices declining - harvest and sell soon for better returns";
      marketAdviceAr = "الأسعار في انخفاض - احصد وبع قريباً لعوائد أفضل";
    }
  }
  
  return {
    isReady,
    optimalWindowStart: optimalStart,
    optimalWindowEnd: optimalEnd,
    daysUntilReady: Math.max(0, daysUntilReady),
    harvestUrgency,
    bestHarvestDay: bestDay,
    reasons,
    reasonsAr,
    weatherWarnings,
    weatherWarningsAr,
    marketAdvice,
    marketAdviceAr,
  };
}

// Estimate post-harvest losses based on conditions
export function estimatePostHarvestLoss(
  cropCode: string,
  storageType: "open" | "shed" | "cold" | "silo",
  daysSinceHarvest: number,
  temperature: number
): { lossPercentage: number; qualityGrade: string; advice: string; adviceAr: string } {
  const baseLoss: Record<string, number> = {
    tomato: 0.05, // 5% per day
    potato: 0.02,
    onion: 0.015,
    wheat: 0.005,
    barley: 0.005,
    olive: 0.02,
    date: 0.01,
    citrus: 0.03,
  };
  
  const storageFactors: Record<string, number> = {
    open: 2.0,
    shed: 1.0,
    cold: 0.3,
    silo: 0.2,
  };
  
  const base = baseLoss[cropCode] || 0.02;
  const storageFactor = storageFactors[storageType];
  
  // Temperature factor
  let tempFactor = 1.0;
  if (temperature > 30) tempFactor = 1.5;
  if (temperature > 35) tempFactor = 2.0;
  if (storageType === "cold") tempFactor = 0.5;
  
  const dailyLoss = base * storageFactor * tempFactor;
  const totalLoss = Math.min(100, dailyLoss * daysSinceHarvest * 100);
  
  let qualityGrade = "A";
  if (totalLoss > 5) qualityGrade = "B";
  if (totalLoss > 15) qualityGrade = "C";
  if (totalLoss > 30) qualityGrade = "D";
  
  let advice = "Product is in good condition";
  let adviceAr = "المنتج في حالة جيدة";
  
  if (totalLoss > 10) {
    advice = "Sell soon to minimize further losses";
    adviceAr = "بع قريباً لتقليل الخسائر";
  }
  if (totalLoss > 25) {
    advice = "Significant quality loss - consider processing or animal feed";
    adviceAr = "خسارة جودة كبيرة - فكر في التصنيع أو علف الحيوانات";
  }
  
  return {
    lossPercentage: Math.round(totalLoss * 10) / 10,
    qualityGrade,
    advice,
    adviceAr,
  };
}
