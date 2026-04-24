/**
 * fieldInsightAdapter.ts — Humanization Layer
 *
 * Transforms raw Layer10Result / ZoneData into natural-language content
 * for FieldInsightBar and ZoneSheet. This is the "copywriting engine"
 * that makes AgriWise feel like a product, not a technical tool.
 */

import type { Layer10Result, ZoneData, MapMode } from "@/hooks/useLayer10";
import { MODE_ZONE_SURFACE_MAP } from "@/hooks/useLayer10";

// ── Driver humanization ──────────────────────────────────────────────────────

const DRIVER_MAP: Record<string, string> = {
  WATER_STRESS_PROB: "water stress",
  NDVI_CLEAN: "vegetation health changes",
  NUTRIENT_STRESS_PROB: "nutrient deficiency",
  COMPOSITE_RISK: "combined stress factors",
  UNCERTAINTY_SIGMA: "data uncertainty",
  SOIL_MOISTURE: "soil moisture variation",
  THERMAL_ANOMALY: "temperature anomaly",
  CANOPY_STRESS: "canopy stress",
  irrigation_deficit: "uneven irrigation",
  compaction: "soil compaction",
  drainage_issue: "drainage problems",
  pest_pressure: "possible pest activity",
  nutrient_deficiency: "nutrient imbalance",
  salinity: "salinity buildup",
  erosion: "soil erosion",
  shade: "shading effects",
};

export function humanizeDriver(driverKey: string): string {
  const key = driverKey.trim();
  if (DRIVER_MAP[key]) return DRIVER_MAP[key];

  // Fallback: convert SNAKE_CASE to readable
  return key
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c); // keep lowercase for readability
}

// ── Confidence humanization ──────────────────────────────────────────────────

export function humanizeConfidence(score: number): string {
  if (score >= 0.8) return "High confidence";
  if (score >= 0.6) return "Confident";
  if (score >= 0.4) return "Estimated";
  if (score >= 0.2) return "Low confidence";
  return "Uncertain";
}

// ── Action humanization ──────────────────────────────────────────────────────

const ACTION_MAP: Record<string, string> = {
  CHECK_IRRIGATION: "Check irrigation uniformity",
  SOIL_SAMPLE: "Take a soil sample in this area",
  SCOUT_FIELD: "Scout this zone for visual symptoms",
  ADJUST_FERTILIZER: "Consider adjusting fertilizer application",
  MONITOR: "Continue monitoring during the next pass",
  DRAIN_CHECK: "Inspect drainage in this section",
  RESEED: "Evaluate for reseeding if condition persists",
  CONSULT_AGRONOMIST: "Consult your agronomist about this pattern",
};

export function humanizeAction(actionKey: string): string {
  const key = actionKey.trim();
  if (ACTION_MAP[key]) return ACTION_MAP[key];
  return key.replace(/_/g, " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
}

// ── Zone condition sentence ──────────────────────────────────────────────────

export function generateZoneCondition(zone: ZoneData): string {
  const severityWord =
    zone.severity > 0.7 ? "significant" :
    zone.severity > 0.4 ? "moderate" :
    zone.severity > 0.15 ? "mild" : "slight";

  const typeLabel = zone.zone_type?.replace(/_/g, " ").toLowerCase() || "variation";

  const driverPhrase = zone.top_drivers?.length
    ? `driven by ${humanizeDriver(zone.top_drivers[0])}`
    : "showing complex variability";

  const areaPhrase = zone.area_fraction > 0.3
    ? `across ${Math.round(zone.area_fraction * 100)}% of the plot`
    : zone.area_fraction > 0.1
    ? `in a focused section`
    : `in a localized area`;

  const confidencePhrase = zone.confidence >= 0.7
    ? ""
    : zone.confidence >= 0.4
    ? " (Requires scouting)"
    : " (Low confidence)";

  return `This area exhibits ${severityWord} ${typeLabel}, ${driverPhrase}, ${areaPhrase}.${confidencePhrase}`;
}

// ── Zone human name ──────────────────────────────────────────────────────────

export function humanizeZoneName(zone: ZoneData, index?: number): string {
  // If we have a custom human label that's not just "zone_123"
  if (zone.label && !zone.label.startsWith("zone_") && !zone.label.startsWith("Z_")) {
    return zone.label
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
  }

  // Derive from type, e.g. "nutrient_risk" -> "Nutrient Risk"
  let baseType = (zone.zone_type || "").replace(/_/g, " ");
  
  // Clean up raw statistical terms to agronomic terms
  if (!baseType || baseType.includes("anomaly")) baseType = "Condition";
  if (baseType.includes("vegetation")) baseType = "Vegetation";
  if (baseType.includes("composite")) baseType = "Priority";

  const capitalized = baseType.replace(/\b\w/g, (c) => c.toUpperCase());
  const suffix = zone.severity > 0.6 ? "Focus" : "Area";

  if (index !== undefined) {
    return `${capitalized} ${suffix} ${String.fromCharCode(65 + index)}`;
  }
  return `${capitalized} ${suffix}`;
}

// ── Field-level insight sentence ─────────────────────────────────────────────

const MODE_SUBJECT: Record<string, string> = {
  vegetation: "canopy condition",
  canopy: "canopy condition",
  veg_attention: "vegetation anomalies",
  water_stress: "water stress levels",
  nutrient_risk: "nutrient status",
  composite_risk: "overall field risk",
  uncertainty: "data confidence",
};

const MODE_ZONE_NOUN: Record<string, string> = {
  vegetation: "canopy",
  canopy: "canopy",
  veg_attention: "vegetation anomaly",
  water_stress: "water stress",
  nutrient_risk: "nutrient",
  composite_risk: "risk",
  uncertainty: "uncertainty",
};

export function generateFieldSentence(
  data: Layer10Result,
  activeMode: MapMode,
  grades?: { plotDataAvailable: boolean; spatialSurfaceAvailable: boolean; localizedZoneAvailable: boolean }
): { sentence: string; hasIssues: boolean; topZoneId: string | null } {
  const subject = MODE_SUBJECT[activeMode] || "field conditions";
  const noun = MODE_ZONE_NOUN[activeMode] || "condition";
  const activeZoneSurfaceType = MODE_ZONE_SURFACE_MAP[activeMode];

  // Canopy mode: pure observational — no zone-state lookup, no anomaly language
  if (activeMode === "canopy" || activeMode === "vegetation") {
    return {
      sentence: "Canopy view — showing overall vegetation condition across the plot.",
      hasIssues: false,
      topZoneId: null,
    };
  }

  // Pure Plot-Level mode fallback (Fix 4: Explicit wording when no space mapping config exists)
  if (grades && grades.plotDataAvailable && !grades.spatialSurfaceAvailable && !grades.localizedZoneAvailable) {
     return {
         sentence: `Plot-level analysis provided. Precise spatial maps are currently unavailable for ${subject}.`,
         hasIssues: false,
         topZoneId: null,
     };
  }
  
  const state = activeZoneSurfaceType
    ? (data.quality?.zone_state_by_surface?.[activeZoneSurfaceType] || "none")
    : "none";
  let zones = data.zones || [];
  // Only consider zones that actually belong to this surface's primary driver map
  if (state === "localized") {
    // Try to filter to the actual problem zones for this mode
    const modeZones = zones.filter(z => z.source_surface_type === activeZoneSurfaceType);
    if (modeZones.length > 0) zones = modeZones;
  }

  // 1. Low Confidence State
  if (state === "low_confidence") {
    return {
      sentence: `Spatial confidence is low. Zoning is unavailable for ${subject}.`,
      hasIssues: false,
      topZoneId: null,
    };
  }

  // 1.5. No Data State
  if (state === "no_data") {
    return {
      sentence: `Spatial data unavailable for this period. Cannot generate valid localized zones.`,
      hasIssues: false,
      topZoneId: null,
    };
  }

  // 2. Uniform / None State
  if (state === "none") {
    const noneMessages: Record<string, string> = {
      veg_attention: "No localized vegetation anomaly zones confirmed. Canopy is broadly consistent, with only minor edge variation.",
      water_stress: "No localized water stress zones detected. Moisture conditions appear broadly uniform.",
      nutrient_risk: "No localized nutrient risk zones detected. Nutrient status appears broadly uniform.",
      composite_risk: "No localized risk zones detected. Field risk profile appears broadly uniform.",
      uncertainty: "No localized confidence issues detected. Data quality appears broadly consistent.",
    };
    return {
      sentence: noneMessages[activeMode] || `No localized ${noun} zones detected.`,
      hasIssues: false,
      topZoneId: null,
    };
  }

  // 3. Field-Wide Signal State
  if (state === "field_wide") {
    // If the frontend still has a giant zone passed through, use it for context, though we shouldn't based on new backend rules
    const massiveZone = zones.find(z => z.area_fraction > 0.6);
    const driverHint = massiveZone?.top_drivers?.[0]
      ? `, driven by ${humanizeDriver(massiveZone.top_drivers[0])}`
      : "";
    return {
      sentence: `1 field-wide condition detected. A uniform ${subject.replace(" levels", "")} signal spans the entire field${driverHint}.`,
      hasIssues: true,
      topZoneId: massiveZone?.zone_id || null,
    };
  }

  // 4. Localized Zones
  const ranked = [...zones].sort((a, b) => (b.severity ?? 0) - (a.severity ?? 0));
  const topZone = ranked[0];
  const severeCount = zones.filter((z) => z.severity > 0.5).length;
  const moderateCount = zones.filter((z) => z.severity > 0.25 && z.severity <= 0.5).length;
  const totalActionable = severeCount + moderateCount;

  const countWord = (n: number) => n === 1 ? "One" : n === 2 ? "Two" : n === 3 ? "Three" : `${n}`;

  if (severeCount === 0 && moderateCount === 0) {
    return {
      sentence: `${countWord(zones.length)} minor ${noun} zone${zones.length > 1 ? "s" : ""} detected. Field looks good overall.`,
      hasIssues: false,
      topZoneId: topZone?.zone_id || null,
    };
  }

  if (severeCount === 0) {
    const driverHint = topZone?.top_drivers?.[0]
      ? `, possibly from ${humanizeDriver(topZone.top_drivers[0])}`
      : "";
    return {
      sentence: `${countWord(moderateCount)} ${noun} zone${moderateCount > 1 ? "s" : ""} show${moderateCount === 1 ? "s" : ""} moderate ${subject.replace(" levels", "")}${driverHint}.`,
      hasIssues: true,
      topZoneId: topZone?.zone_id || null,
    };
  }

  const driverHint = topZone?.top_drivers?.[0]
    ? ` The primary concern is ${humanizeDriver(topZone.top_drivers[0])}.`
    : "";

  return {
    sentence: `${countWord(totalActionable)} ${noun} zone${totalActionable > 1 ? "s" : ""} need${totalActionable === 1 ? "s" : ""} attention.${driverHint}`,
    hasIssues: true,
    topZoneId: topZone?.zone_id || null,
  };
}

// ── Micro-legend labels ──────────────────────────────────────────────────────

export const MICRO_LEGEND: Record<string, { low: string; mid: string; high: string }> = {
  vegetation: { low: "Sparse", mid: "Moderate", high: "Dense" },
  water_stress: { low: "Low", mid: "Moderate", high: "High" },
  nutrient_risk: { low: "Adequate", mid: "Watch", high: "Deficient" },
  composite_risk: { low: "Low", mid: "Moderate", high: "High" },
  uncertainty: { low: "Reliable", mid: "Fair", high: "Uncertain" },
};
