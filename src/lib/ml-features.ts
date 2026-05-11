/**
 * ML Feature Extraction Engine
 * =============================
 * Extracts flat numeric feature vectors from AgriBrain intelligence responses.
 * These features are stored per-snapshot for instant ML training data access,
 * and accumulated into PlotDNA for permanent learning.
 *
 * Feature categories:
 *   - Vegetation (NDVI, velocity, uncertainty)
 *   - Water stress (probability, drought days, ET0)
 *   - Nutrients (N/P/K deficiency probabilities)
 *   - Disease (biotic pressure, weather pressure)
 *   - Weather (temperature, humidity, precipitation, wind)
 *   - Phenology (crop stage, DAP)
 *   - Composite (risk, reliability, freshness)
 *   - Sensor (IoT ground-truth readings)
 */

// ── Types ───────────────────────────────────────────────────────────

export interface MLFeatureVector {
  // Vegetation
  ndvi_mean: number | null;
  ndvi_d1: number | null;
  ndvi_unc: number | null;
  ndvi_spatial_var: number | null;

  // Water
  water_stress_prob: number | null;
  soil_moisture_pct: number | null;
  drought_days: number | null;
  et0_mm: number | null;
  precip_7d_mm: number | null;

  // Nutrients
  nutrient_stress_prob: number | null;
  n_deficiency: number | null;
  p_deficiency: number | null;
  k_deficiency: number | null;
  fertility_limitation: number | null;

  // Disease
  biotic_pressure: number | null;
  weather_pressure: number | null;

  // Weather
  temp_c: number | null;
  temp_min_c: number | null;
  temp_max_c: number | null;
  humidity_pct: number | null;
  precip_mm: number | null;
  wind_ms: number | null;
  solar_rad: number | null;

  // Phenology
  dap: number | null;
  crop_stage_idx: number | null; // Encoded: BARE_SOIL=0, EMERGENCE=1, VEGETATIVE=2...

  // Composite (from L10 surfaces)
  risk_composite: number | null;
  risk_p10: number | null;
  risk_p90: number | null;
  data_reliability: number | null;
  uncertainty_sigma: number | null;

  // Sensor (IoT ground truth)
  sensor_moisture: number | null;
  sensor_ec: number | null;
  sensor_temp: number | null;

  // Meta
  freshness_score: number | null;
  source_count: number | null;
}

export interface SurfaceStatEntry {
  id: string;
  type: string;
  mean: number;
  p10: number;
  p50: number;
  p90: number;
  min: number;
  max: number;
  spread: number;
  grounding: string;
}

// ── Stage Encoder ───────────────────────────────────────────────────

const STAGE_INDEX: Record<string, number> = {
  BARE_SOIL: 0,
  EMERGENCE: 1,
  VEGETATIVE: 2,
  REPRODUCTIVE: 3,
  SENESCENCE: 4,
  HARVESTED: 5,
  UNKNOWN: -1,
};

// ── Engine Value Extraction ─────────────────────────────────────────

function findEngineValue(
  engines: any[],
  engineId: string,
  key: string
): number | null {
  const raw = findEngineRawValue(engines, engineId, key);
  return typeof raw === "number" ? raw : null;
}

// Returns any value type (string, number, boolean) — use for non-numeric fields
function findEngineRawValue(
  engines: any[],
  engineId: string,
  key: string
): any {
  if (!engines || !Array.isArray(engines)) return null;
  const engine = engines.find(
    (e: any) => e.id === engineId || e.name?.includes(engineId)
  );
  if (!engine) return null;

  // Search in engine.data, engine.expert, and flat engine properties
  const sources = [engine.data, engine.expert, engine];
  for (const src of sources) {
    if (src && typeof src === "object") {
      if (key in src && src[key] !== undefined && src[key] !== null) return src[key];
      // Try nested: engine.data.water_stress.probability
      for (const v of Object.values(src)) {
        if (v && typeof v === "object" && key in (v as any)) {
          const val = (v as any)[key];
          if (val !== undefined && val !== null) return val;
        }
      }
    }
  }
  return null;
}

// ── Main Extraction ─────────────────────────────────────────────────

export function extractMLFeatures(response: any): MLFeatureVector {
  const engines = response.engines || [];
  const current = response.current || {};
  const weather = current.weather || {};
  const indices = current.indices || {};
  const wb = current.waterBalance || {};
  const pheno = response.crop_phenology || response.cropPhenology || {};
  const sensor = response.sensor_context || response.sensorContext || {};
  const assm = response.assimilation || {};

  // Weather timeline aggregation (last 7 days precipitation)
  let precip_7d = null;
  const timeline = response.timeline || {};
  if (timeline.weather && Array.isArray(timeline.weather)) {
    const recent = timeline.weather.slice(-7);
    const precips = recent
      .map((d: any) => d.precipitation ?? d.precip ?? 0)
      .filter((v: number) => typeof v === "number");
    if (precips.length > 0) {
      precip_7d = precips.reduce((a: number, b: number) => a + b, 0);
    }
  }

  // Parse weather data — backend uses nested objects:
  //   temperature: { current, min, max } or flat number
  //   wind: { speed_ms } or flat number
  const tempData = weather.temperature;
  const tempCurrent = typeof tempData === "object" ? tempData?.current : tempData;
  const tempMin = typeof tempData === "object" ? tempData?.min : null;
  const tempMax = typeof tempData === "object" ? tempData?.max : null;
  const windData = weather.wind;
  const windSpeed = typeof windData === "object" ? windData?.speed_ms : windData;

  // Parse water balance summary
  const wbSummary = wb?.summary || {};
  const deficit_mm = wbSummary.final_deficit_mm ?? null;
  const stress_index = wbSummary.stress_index ?? null;

  return {
    // Vegetation — from L2 engine data or current.indices
    ndvi_mean:
      findEngineValue(engines, "L2", "ndvi") ??
      findEngineValue(engines, "L2", "ndvi_mean") ??
      indices.ndvi ??
      null,
    ndvi_d1: indices.ndvi_velocity ?? indices.ndvi_d1 ?? null,
    ndvi_unc: indices.ndvi_uncertainty ?? null,
    ndvi_spatial_var:
      indices.ndvi_spatial_var ?? null,

    // Water — from L3 engine data (actual keys: stress_index, deficit_mm, et0_today)
    water_stress_prob:
      findEngineValue(engines, "L3", "stress_index") ??
      (stress_index !== null ? stress_index : null),
    soil_moisture_pct:
      sensor.soil_moisture_pct ?? null,
    drought_days: null, // Not directly available in current engine cards
    et0_mm:
      findEngineValue(engines, "L3", "et0_today") ??
      (wb?.et0 ?? null),
    precip_7d_mm: precip_7d,

    // Nutrients — L4 has flat soil properties, no per-nutrient deficiency probs
    // Use soil values as proxies (low nitrogen = high deficiency risk)
    nutrient_stress_prob: null, // Would require L10 surface stats
    n_deficiency:
      findEngineValue(engines, "L4", "nitrogen") ?? null,
    p_deficiency: null, // No phosphorus in engine card
    k_deficiency: null, // No potassium in engine card
    fertility_limitation:
      findEngineValue(engines, "L4", "cec") ?? null,

    // Disease — L5 actual keys: risk_level (string), temp, humidity
    // BUG 17 fix: Use findEngineRawValue since risk_level is a string, not a number
    biotic_pressure: encodeBioticRisk(
      findEngineRawValue(engines, "L5", "risk_level")
    ),
    weather_pressure:
      findEngineValue(engines, "L5", "humidity") ?? null,

    // Weather — handle nested temperature/wind objects
    temp_c:
      findEngineValue(engines, "L0", "temp_current") ??
      (typeof tempCurrent === "number" ? tempCurrent : null) ??
      sensor.field_temperature_c ??
      null,
    temp_min_c: typeof tempMin === "number" ? tempMin : null,
    temp_max_c: typeof tempMax === "number" ? tempMax : null,
    humidity_pct:
      (typeof weather.humidity === "number" ? weather.humidity : null) ??
      sensor.field_humidity_pct ??
      null,
    precip_mm: weather.precipitation ?? null,
    wind_ms:
      (typeof windSpeed === "number" ? windSpeed : null) ??
      sensor.field_wind_speed_ms ??
      null,
    solar_rad: weather.solar_radiation ?? null,

    // Phenology
    dap: pheno.dap ?? null,
    crop_stage_idx: pheno.stage
      ? STAGE_INDEX[pheno.stage.toUpperCase()] ?? -1
      : null,

    // Composite — L10 actual keys: overall_quality_score, hard_gates_passed
    risk_composite:
      findEngineValue(engines, "L10", "overall_quality_score") ?? null,
    risk_p10: null, // Only available from L10 surface stats
    risk_p90: null, // Only available from L10 surface stats
    data_reliability:
      findEngineValue(engines, "L10", "hard_gates_passed") ?? null,
    uncertainty_sigma: null, // Only available from L10 surface stats

    // Sensor
    sensor_moisture: sensor.soil_moisture_pct ?? null,
    sensor_ec: sensor.soil_ec_ds_m ?? null,
    sensor_temp: sensor.field_temperature_c ?? null,

    // Meta
    freshness_score: assm.freshness_score ?? null,
    source_count: assm.sources_count ?? null,
  };
}

// Encode string risk level to numeric for ML
function encodeBioticRisk(level: any): number | null {
  if (typeof level === "number") return level;
  if (typeof level !== "string") return null;
  const map: Record<string, number> = {
    LOW: 0.2,
    MODERATE: 0.5,
    HIGH: 0.85,
  };
  return map[level.toUpperCase()] ?? null;
}

// ── Surface Statistics ──────────────────────────────────────────────

export function extractSurfaceStats(l10Data: any): SurfaceStatEntry[] {
  if (!l10Data?.surfaces || !Array.isArray(l10Data.surfaces)) return [];

  return l10Data.surfaces.map((s: any) => {
    const vals: number[] = [];
    if (s.values && Array.isArray(s.values)) {
      for (const row of s.values) {
        if (Array.isArray(row)) {
          for (const v of row) {
            if (v !== null && typeof v === "number") vals.push(v);
          }
        }
      }
    }

    vals.sort((a, b) => a - b);
    const n = vals.length;
    const mean = n > 0 ? vals.reduce((a, b) => a + b, 0) / n : 0;
    const p10 = n > 0 ? vals[Math.floor(n * 0.1)] : 0;
    const p50 = n > 0 ? vals[Math.floor(n * 0.5)] : 0;
    const p90 = n > 0 ? vals[Math.floor(n * 0.9)] : 0;

    return {
      id: s.surface_id || s.id || "",
      type: s.semantic_type || s.type || "",
      mean: Math.round(mean * 10000) / 10000,
      p10: Math.round(p10 * 10000) / 10000,
      p50: Math.round(p50 * 10000) / 10000,
      p90: Math.round(p90 * 10000) / 10000,
      min: n > 0 ? vals[0] : 0,
      max: n > 0 ? vals[n - 1] : 0,
      spread: n > 0 ? Math.round((vals[n - 1] - vals[0]) * 10000) / 10000 : 0,
      grounding: s.grounding_class || "UNKNOWN",
    };
  });
}

// ── Surface Digest (SHA-256 for change detection) ───────────────────

export async function computeSurfaceDigest(l10Data: any): Promise<string> {
  if (!l10Data?.surfaces) return "empty";

  // BUG 18 fix: Build a digest from surface statistics (mean, min, max per surface)
  // instead of just [0][0] — catches changes anywhere in the grid
  const sig = (l10Data.surfaces || [])
    .map((s: any) => {
      const type = s.semantic_type || s.type || "unknown";
      if (!s.values || !Array.isArray(s.values)) return `${type}:empty`;

      // Compute lightweight stats for digest: sum, count, min, max
      let sum = 0, count = 0, min = Infinity, max = -Infinity;
      for (const row of s.values) {
        if (!Array.isArray(row)) continue;
        for (const v of row) {
          if (v !== null && typeof v === "number") {
            sum += v;
            count++;
            if (v < min) min = v;
            if (v > max) max = v;
          }
        }
      }
      const mean = count > 0 ? (sum / count).toFixed(6) : "0";
      return `${type}:n=${count},u=${mean},mn=${min === Infinity ? 0 : min.toFixed(4)},mx=${max === -Infinity ? 0 : max.toFixed(4)}`;
    })
    .sort()
    .join("|");

  // Use Web Crypto API (available in Edge Runtime and Node 18+)
  if (typeof globalThis.crypto?.subtle !== "undefined") {
    const encoded = new TextEncoder().encode(sig);
    const hash = await crypto.subtle.digest("SHA-256", encoded);
    const bytes = new Uint8Array(hash);
    return Array.from(bytes)
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  }

  // Fallback: simple hash
  let h = 0;
  for (let i = 0; i < sig.length; i++) {
    h = ((h << 5) - h + sig.charCodeAt(i)) | 0;
  }
  return `fallback_${Math.abs(h).toString(16)}`;
}

// ── Feature Vector to CSV Row ───────────────────────────────────────

export function featureVectorToCSVHeaders(): string {
  const sample = extractMLFeatures({});
  return Object.keys(sample).join(",");
}

export function featureVectorToCSVRow(
  features: MLFeatureVector,
  meta?: { plotId?: string; date?: string; cropCode?: string }
): string {
  const prefix = meta
    ? `${meta.plotId ?? ""},${meta.date ?? ""},${meta.cropCode ?? ""},`
    : "";
  const values = Object.values(features)
    .map((v) => (v === null ? "" : String(v)))
    .join(",");
  return prefix + values;
}
