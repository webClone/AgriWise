// AgriBrain - Smart Irrigation Module
// Calculates optimal irrigation timing and amounts

import type {
  IrrigationSystemType,
  AutomationMode,
  EventStatus,
  ValidationOutcome,
} from '@/lib/irrigation/types';

interface IrrigationInput {
  cropCode: string;
  growthStage: "seedling" | "vegetative" | "flowering" | "fruiting" | "mature";
  plotArea: number; // hectares
  soilType: string;
  lastIrrigationDate?: Date;
  currentWeather: {
    temperature: number;
    humidity: number;
    windSpeed: number;
    precipitation: number; // mm expected
  };
}

interface IrrigationRecommendation {
  shouldIrrigate: boolean;
  urgency: "none" | "low" | "medium" | "high" | "critical";
  waterAmount: number; // liters per hectare
  totalWater: number; // liters for entire plot
  nextIrrigationDays: number;
  message: string;
  messageAr: string;
  tips: string[];
  tipsAr: string[];
}

// Crop water needs (liters per hectare per day at peak growth)
const cropWaterNeeds: Record<string, { base: number; peak: number }> = {
  wheat: { base: 3000, peak: 5000 },
  barley: { base: 2500, peak: 4500 },
  potato: { base: 4000, peak: 7000 },
  tomato: { base: 5000, peak: 8000 },
  olive: { base: 2000, peak: 4000 },
  date: { base: 8000, peak: 12000 },
  onion: { base: 3500, peak: 5500 },
  pepper: { base: 4500, peak: 7000 },
  citrus: { base: 6000, peak: 9000 },
  grape: { base: 3000, peak: 5000 },
};

// Growth stage multipliers
const stageMultipliers: Record<string, number> = {
  seedling: 0.4,
  vegetative: 0.7,
  flowering: 1.0,
  fruiting: 0.9,
  mature: 0.5,
};

// Soil water retention (days between irrigation)
const soilRetention: Record<string, number> = {
  clay: 5,
  loamy: 3,
  sandy: 1.5,
  rocky: 1,
};

export function calculateIrrigation(input: IrrigationInput): IrrigationRecommendation {
  const cropNeeds = cropWaterNeeds[input.cropCode] || cropWaterNeeds.wheat;
  const stageFactor = stageMultipliers[input.growthStage] || 0.7;
  const retention = soilRetention[input.soilType] || 3;
  
  // Calculate base water need
  let dailyNeed = (cropNeeds.base + (cropNeeds.peak - cropNeeds.base) * stageFactor);
  
  // Adjust for weather
  const { temperature, humidity, windSpeed, precipitation } = input.currentWeather;
  
  // Temperature adjustment (higher temp = more water)
  if (temperature > 35) {
    dailyNeed *= 1.3;
  } else if (temperature > 30) {
    dailyNeed *= 1.15;
  } else if (temperature < 15) {
    dailyNeed *= 0.7;
  }
  
  // Humidity adjustment (lower humidity = more water)
  if (humidity < 30) {
    dailyNeed *= 1.2;
  } else if (humidity > 70) {
    dailyNeed *= 0.8;
  }
  
  // Wind adjustment (more wind = more evaporation)
  if (windSpeed > 30) {
    dailyNeed *= 1.15;
  }
  
  // Precipitation reduces need
  const precipitationContribution = precipitation * 10 * input.plotArea; // mm to liters approx
  
  // Calculate if irrigation is needed
  const daysSinceIrrigation = input.lastIrrigationDate 
    ? Math.floor((Date.now() - input.lastIrrigationDate.getTime()) / (1000 * 60 * 60 * 24))
    : 999;
  
  const waterDeficit = daysSinceIrrigation > retention;
  const precipitationSufficient = precipitation >= 10; // 10mm of rain is significant
  
  // Calculate amounts
  const waterPerHectare = Math.round(dailyNeed * retention);
  const totalWater = Math.round(waterPerHectare * input.plotArea);
  
  // Determine urgency
  let urgency: IrrigationRecommendation["urgency"] = "none";
  let shouldIrrigate = false;
  
  if (precipitationSufficient) {
    urgency = "none";
    shouldIrrigate = false;
  } else if (daysSinceIrrigation >= retention * 2) {
    urgency = "critical";
    shouldIrrigate = true;
  } else if (daysSinceIrrigation >= retention * 1.5) {
    urgency = "high";
    shouldIrrigate = true;
  } else if (daysSinceIrrigation >= retention) {
    urgency = "medium";
    shouldIrrigate = true;
  } else if (daysSinceIrrigation >= retention * 0.8) {
    urgency = "low";
    shouldIrrigate = false;
  }
  
  // Generate messages
  let message = "";
  let messageAr = "";
  const tips: string[] = [];
  const tipsAr: string[] = [];
  
  if (precipitationSufficient) {
    message = "Rain expected - no irrigation needed";
    messageAr = "أمطار متوقعة - لا حاجة للري";
  } else if (urgency === "critical") {
    message = "Critical: Irrigate immediately to prevent crop stress";
    messageAr = "حرج: اسقِ فوراً لمنع إجهاد المحصول";
  } else if (urgency === "high") {
    message = "Irrigation recommended within 24 hours";
    messageAr = "ينصح بالري خلال 24 ساعة";
  } else if (urgency === "medium") {
    message = "Plan irrigation for the next 2-3 days";
    messageAr = "خطط للري خلال 2-3 أيام";
  } else {
    message = "Soil moisture is adequate";
    messageAr = "رطوبة التربة كافية";
  }
  
  // Add tips
  if (temperature > 30) {
    tips.push("Water in early morning (5-7 AM) to reduce evaporation");
    tipsAr.push("اسقِ في الصباح الباكر (5-7 ص) لتقليل التبخر");
  }
  
  if (input.growthStage === "flowering") {
    tips.push("Flowering stage needs consistent moisture - don't skip irrigation");
    tipsAr.push("مرحلة الإزهار تحتاج رطوبة مستقرة - لا تفوت الري");
  }
  
  if (input.soilType === "sandy") {
    tips.push("Sandy soil drains quickly - consider more frequent, lighter watering");
    tipsAr.push("التربة الرملية تصرف الماء بسرعة - فكر في ري متكرر وخفيف");
  }
  
  if (windSpeed > 20) {
    tips.push("Avoid sprinkler irrigation in windy conditions");
    tipsAr.push("تجنب الرش في الرياح القوية");
  }
  
  // Calculate next irrigation
  let nextIrrigationDays = retention - daysSinceIrrigation;
  if (nextIrrigationDays < 0) nextIrrigationDays = 0;
  if (precipitationSufficient) nextIrrigationDays = retention;
  
  return {
    shouldIrrigate,
    urgency,
    waterAmount: waterPerHectare,
    totalWater,
    nextIrrigationDays: Math.max(0, Math.round(nextIrrigationDays)),
    message,
    messageAr,
    tips,
    tipsAr,
  };
}

// Calculate evapotranspiration (simplified Hargreaves method)
export function calculateET0(
  tempMin: number, 
  tempMax: number, 
  latitude: number,
  dayOfYear: number
): number {
  const tempAvg = (tempMin + tempMax) / 2;
  const tempRange = tempMax - tempMin;
  
  // Solar radiation estimate (simplified)
  const Ra = 15 + 10 * Math.cos((dayOfYear - 172) * 2 * Math.PI / 365);
  
  // Hargreaves equation
  const ET0 = 0.0023 * (tempAvg + 17.8) * Math.sqrt(tempRange) * Ra;
  
  return Math.max(0, Math.round(ET0 * 10) / 10);
}


// ============================================================================
// Real-Time Telemetry Bridge (v2.0)
// Connects legacy optimizer to the irrigation_runtime dispatcher pipeline.
// ============================================================================


/**
 * Live telemetry snapshot from an actuator device,
 * pushed via WebSocket or polled from /api/irrigation.
 */
export interface ActuatorTelemetry {
  device_id: string;
  zone_id: string;
  timestamp: string;
  flow_rate_lpm: number;
  pressure_bar: number;
  soil_moisture_vwc: number;
  volume_delivered_l: number;
  is_running: boolean;
  error_code: string;
}

/**
 * Merged recommendation: original optimizer output + runtime status.
 */
export interface EnhancedIrrigationRecommendation extends IrrigationRecommendation {
  // Runtime telemetry overlay
  runtime: {
    has_actuator: boolean;
    device_id: string;
    system_type: IrrigationSystemType;
    automation_mode: AutomationMode;
    current_event_status: EventStatus | null;
    last_validation: ValidationOutcome | null;
    delivery_efficiency: number;       // 0-1, from closed-loop validation
    calibration_factor: number;        // volume adjustment from validation history
    live_soil_moisture_vwc: number;    // real-time from sensor
    live_flow_rate_lpm: number;        // real-time from actuator
  };
}

/**
 * Convert a legacy IrrigationRecommendation into an L8-compatible
 * ActionCard that the irrigation_runtime scheduler can process.
 */
export function toActionCard(
  recommendation: IrrigationRecommendation,
  plotId: string,
  zoneId: string,
  deviceId: string,
  systemType: IrrigationSystemType = 'DRIP',
): Record<string, unknown> {
  // Convert liters-per-hectare to mm (1mm on 1ha = 10,000L)
  const volumeMm = recommendation.waterAmount / 10000;

  const urgencyMap: Record<string, string> = {
    critical: 'CRITICAL',
    high: 'HIGH',
    medium: 'NORMAL',
    low: 'LOW',
    none: 'LOW',
  };

  return {
    action_type: 'IRRIGATE',
    action_id: `ACT-OPT-${Date.now()}`,
    plot_id: plotId,
    zone_id: zoneId,
    device_id: deviceId,
    system_type: systemType,
    volume_mm: Math.round(volumeMm * 100) / 100,
    rate_min: Math.round(volumeMm * 100) / 100,
    urgency: urgencyMap[recommendation.urgency] || 'NORMAL',
    rationale: recommendation.message,
    source: 'irrigation-optimizer.ts',
  };
}

/**
 * Merge a base recommendation with live runtime telemetry
 * to produce an EnhancedIrrigationRecommendation.
 */
export function mergeWithTelemetry(
  base: IrrigationRecommendation,
  telemetry: ActuatorTelemetry | null,
  runtimeMeta?: {
    device_id?: string;
    system_type?: IrrigationSystemType;
    automation_mode?: AutomationMode;
    event_status?: EventStatus;
    last_validation?: ValidationOutcome;
    delivery_efficiency?: number;
    calibration_factor?: number;
  },
): EnhancedIrrigationRecommendation {
  const calibration = runtimeMeta?.calibration_factor ?? 1.0;

  // Apply calibration: adjust water amount based on delivery history
  const calibratedAmount = Math.round(base.waterAmount * calibration);
  const calibratedTotal = Math.round(base.totalWater * calibration);

  return {
    ...base,
    waterAmount: calibratedAmount,
    totalWater: calibratedTotal,
    runtime: {
      has_actuator: !!runtimeMeta?.device_id,
      device_id: runtimeMeta?.device_id || '',
      system_type: runtimeMeta?.system_type || 'DRIP',
      automation_mode: runtimeMeta?.automation_mode || 'MANUAL',
      current_event_status: runtimeMeta?.event_status || null,
      last_validation: runtimeMeta?.last_validation || null,
      delivery_efficiency: runtimeMeta?.delivery_efficiency ?? 0,
      calibration_factor: calibration,
      live_soil_moisture_vwc: telemetry?.soil_moisture_vwc ?? 0,
      live_flow_rate_lpm: telemetry?.flow_rate_lpm ?? 0,
    },
  };
}
