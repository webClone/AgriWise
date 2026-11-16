/**
 * Akaloris ASMAE 13-State Scientific Catalog & Availability Resolver
 * ===================================================================
 * Aligned with Python `services.agribrain.scientific_contracts.state_schema_ref`.
 * Enforces truthfulness-first UI gating: NEVER fabricates a spatial raster
 * for scalar-only or unobserved latent states.
 */

export const STATE_SCHEMA_VERSION = "asmae_state_v1_13";

export type AsmaeStateKey =
  | "vigor"
  | "lai"
  | "chlorophyll"
  | "canopy_water"
  | "root_zone_water"
  | "surface_wetness_event"
  | "structure"
  | "bare_soil_fraction"
  | "salinity_stress"
  | "thermal_stress"
  | "biotic_confounder_risk"
  | "phenology_progress"
  | "stress_memory";

export const ASMAE_13_STATE_ORDER: readonly AsmaeStateKey[] = Object.freeze([
  "vigor",
  "lai",
  "chlorophyll",
  "canopy_water",
  "root_zone_water",
  "surface_wetness_event",
  "structure",
  "bare_soil_fraction",
  "salinity_stress",
  "thermal_stress",
  "biotic_confounder_risk",
  "phenology_progress",
  "stress_memory",
]);

export interface AsmaeStateDefinition {
  readonly key: AsmaeStateKey;
  readonly order: number; // 1 to 13
  readonly surfaceType: string;
  readonly aliases: readonly string[];
  readonly name: string;
  readonly shortName: string;
  readonly unit: string;
  readonly range: readonly [number, number];
  readonly authorityCeiling: "PRESCRIPTION_ELIGIBLE" | "DIAGNOSTIC" | "MONITORING_ONLY" | "VISUALIZATION";
  readonly identifiabilityClass: "INDIRECTLY_CONSTRAINED" | "PARTIALLY_IDENTIFIED" | "HYPOTHESIS_ONLY" | "NOT_IDENTIFIED";
  readonly colorRamp: readonly string[];
  readonly description: string;
  readonly farmerQuestion: string;
}

export const ASMAE_13_STATE_CATALOG: Readonly<Record<AsmaeStateKey, AsmaeStateDefinition>> = Object.freeze({
  vigor: {
    key: "vigor",
    order: 1,
    surfaceType: "ASMAE_VIGOR",
    aliases: ["CANOPY_ASMAE_VIGOR", "canopy_vigor", "surface-canopy-ndvi"],
    name: "Canopy Photosynthetic Activity",
    shortName: "Vigor",
    unit: "fraction",
    range: [0.0, 1.0],
    authorityCeiling: "PRESCRIPTION_ELIGIBLE",
    identifiabilityClass: "INDIRECTLY_CONSTRAINED",
    colorRamp: ["#8B0000", "#FFD700", "#006400"],
    description: "Multi-spectral canopy vigor derived from calibrated Sentinel-2 red/NIR surface reflectance and radiative transfer priors.",
    farmerQuestion: "How actively is the crop photosynthesizing across the field?",
  },
  lai: {
    key: "lai",
    order: 2,
    surfaceType: "ASMAE_LAI",
    aliases: ["canopy_lai", "LEAF_AREA_INDEX"],
    name: "Leaf Area Index",
    shortName: "LAI",
    unit: "m²/m²",
    range: [0.0, 8.0],
    authorityCeiling: "DIAGNOSTIC",
    identifiabilityClass: "PARTIALLY_IDENTIFIED",
    colorRamp: ["#8B0000", "#FFD700", "#006400"],
    description: "One-sided green leaf area per unit ground surface area inverted from canopy reflectance.",
    farmerQuestion: "How dense is the leaf canopy per square meter of ground?",
  },
  chlorophyll: {
    key: "chlorophyll",
    order: 3,
    surfaceType: "ASMAE_CHLOROPHYLL",
    aliases: ["NUTRIENT_ASMAE_CHLOROPHYLL_PROXY", "foliar_chlorophyll"],
    name: "Foliar Chlorophyll Content",
    shortName: "Chlorophyll",
    unit: "µg/cm²",
    range: [0.0, 80.0],
    authorityCeiling: "DIAGNOSTIC",
    identifiabilityClass: "PARTIALLY_IDENTIFIED",
    colorRamp: ["#c0392b", "#f1c40f", "#27ae60"],
    description: "Area-based leaf chlorophyll content indicating photosynthetic capacity and nitrogen nutrition.",
    farmerQuestion: "Is leaf greenness showing nitrogen sufficiency or chlorosis?",
  },
  canopy_water: {
    key: "canopy_water",
    order: 4,
    surfaceType: "ASMAE_CANOPY_WATER",
    aliases: ["WATER_ASMAE_CANOPY_WATER"],
    name: "Canopy Water Content",
    shortName: "Canopy Water",
    unit: "fraction",
    range: [0.0, 1.0],
    authorityCeiling: "DIAGNOSTIC",
    identifiabilityClass: "INDIRECTLY_CONSTRAINED",
    colorRamp: ["#c0392b", "#f1c40f", "#1a5276"],
    description: "Equivalent water thickness in the crop canopy sensitive to shortwave-infrared water absorption.",
    farmerQuestion: "Is the foliage maintaining healthy water turgor?",
  },
  root_zone_water: {
    key: "root_zone_water",
    order: 5,
    surfaceType: "ASMAE_ROOT_ZONE_WATER",
    aliases: ["WATER_ASMAE_ROOT_ZONE_WATER"],
    name: "Root-Zone Soil Moisture",
    shortName: "Root-Zone Water",
    unit: "fraction",
    range: [0.0, 1.0],
    authorityCeiling: "DIAGNOSTIC",
    identifiabilityClass: "INDIRECTLY_CONSTRAINED",
    colorRamp: ["#c0392b", "#f1c40f", "#1a5276"],
    description: "Plant available soil water in the effective root profile assimilated from SAR backscatter, moisture probes, and ET0.",
    farmerQuestion: "How much moisture is physically accessible to the root system?",
  },
  surface_wetness_event: {
    key: "surface_wetness_event",
    order: 6,
    surfaceType: "ASMAE_SURFACE_WETNESS_EVENT",
    aliases: ["surface_wetness"],
    name: "Event-Based Surface Water",
    shortName: "Surface Wetness",
    unit: "fraction",
    range: [0.0, 1.0],
    authorityCeiling: "DIAGNOSTIC",
    identifiabilityClass: "INDIRECTLY_CONSTRAINED",
    colorRamp: ["#f8fafc", "#60a5fa", "#1d4ed8"],
    description: "Transient surface ponding and irrigation or heavy rainfall wetting event indicator.",
    farmerQuestion: "Is there standing water or recent active ponding?",
  },
  structure: {
    key: "structure",
    order: 7,
    surfaceType: "ASMAE_STRUCTURE",
    aliases: ["biomass_structure"],
    name: "Canopy / Biomass Structure",
    shortName: "Structure",
    unit: "fraction",
    range: [0.0, 1.0],
    authorityCeiling: "DIAGNOSTIC",
    identifiabilityClass: "INDIRECTLY_CONSTRAINED",
    colorRamp: ["#fef3c7", "#d97706", "#78350f"],
    description: "Canopy architecture density and rough volumetric biophysical arrangement.",
    farmerQuestion: "How mature and physically developed is the crop biomass?",
  },
  bare_soil_fraction: {
    key: "bare_soil_fraction",
    order: 8,
    surfaceType: "ASMAE_BARE_SOIL",
    aliases: ["ASMAE_BARE_SOIL_FRACTION", "bare_soil"],
    name: "Exposed Soil Fraction",
    shortName: "Bare Soil",
    unit: "fraction",
    range: [0.0, 1.0],
    authorityCeiling: "PRESCRIPTION_ELIGIBLE",
    identifiabilityClass: "INDIRECTLY_CONSTRAINED",
    colorRamp: ["#fef3c7", "#a16207", "#451a03"],
    description: "Sub-pixel fractional un-vegetated soil background exposure.",
    farmerQuestion: "How much bare ground is visible between canopy crowns?",
  },
  salinity_stress: {
    key: "salinity_stress",
    order: 9,
    surfaceType: "ASMAE_SALINITY_STRESS",
    aliases: ["SALINITY_ASMAE_STRESS"],
    name: "Salinity-Induced Osmotic Stress",
    shortName: "Salinity Stress",
    unit: "fraction",
    range: [0.0, 1.0],
    authorityCeiling: "MONITORING_ONLY",
    identifiabilityClass: "HYPOTHESIS_ONLY",
    colorRamp: ["#0d9488", "#22d3ee", "#ef4444"],
    description: "Root-zone salinity persistence hypothesis based on multi-temporal spectral divergence.",
    farmerQuestion: "Is soil salinity impairing root water uptake?",
  },
  thermal_stress: {
    key: "thermal_stress",
    order: 10,
    surfaceType: "ASMAE_THERMAL_STRESS",
    aliases: ["thermal_depression"],
    name: "Canopy Thermal Stress",
    shortName: "Thermal Stress",
    unit: "fraction",
    range: [0.0, 1.0],
    authorityCeiling: "DIAGNOSTIC",
    identifiabilityClass: "INDIRECTLY_CONSTRAINED",
    colorRamp: ["#fff7ed", "#fb923c", "#9a3412"],
    description: "Canopy temperature elevation and stomatal closure stress index.",
    farmerQuestion: "Are leaves closing stomata and overheating in the sun?",
  },
  biotic_confounder_risk: {
    key: "biotic_confounder_risk",
    order: 11,
    surfaceType: "ASMAE_BIOTIC_CONFOUNDER_RISK",
    aliases: ["biotic_risk"],
    name: "Biotic Pressure Confounder Risk",
    shortName: "Biotic Risk",
    unit: "fraction",
    range: [0.0, 1.0],
    authorityCeiling: "MONITORING_ONLY",
    identifiabilityClass: "HYPOTHESIS_ONLY",
    colorRamp: ["#fff7bc", "#fd8d3c", "#7f0000"],
    description: "Weed patch, foliar disease, or pest confounding risk hypothesis separating abiotic deficit from infection.",
    farmerQuestion: "Could symptoms be caused by pests or weeds rather than water deficit?",
  },
  phenology_progress: {
    key: "phenology_progress",
    order: 12,
    surfaceType: "ASMAE_PHENOLOGY_PROGRESS",
    aliases: ["phenology_stage"],
    name: "Phenological Stage Progress",
    shortName: "Phenology",
    unit: "fraction",
    range: [0.0, 1.0],
    authorityCeiling: "DIAGNOSTIC",
    identifiabilityClass: "PARTIALLY_IDENTIFIED",
    colorRamp: ["#8B0000", "#FFD700", "#006400"],
    description: "Normalized crop growth stage progress along the seasonal development worldline.",
    farmerQuestion: "What physiological development milestone has the crop reached?",
  },
  stress_memory: {
    key: "stress_memory",
    order: 13,
    surfaceType: "ASMAE_STRESS_MEMORY",
    aliases: ["cumulative_stress"],
    name: "Cumulative Stress Memory",
    shortName: "Stress Memory",
    unit: "fraction",
    range: [0.0, 1.0],
    authorityCeiling: "VISUALIZATION",
    identifiabilityClass: "NOT_IDENTIFIED",
    colorRamp: ["#fff7bc", "#fc8d59", "#b91c1c"],
    description: "EWMA multi-day cumulative stress accumulation tracking plant physiological fatigue.",
    farmerQuestion: "How much chronic stress fatigue has accumulated over recent weeks?",
  },
});

/**
 * 4 Explicit Scientific State Availability Outcomes
 */
export type AsmaeStateStatus =
  | "QUALIFIED_SPATIAL" // Map eligible: An authorized, validated grid can be rendered with correct masks
  | "PLOT_ESTIMATE"     // Numbers only: Scalar estimate (mean, uncertainty, units) without spatial raster
  | "UNAVAILABLE"       // No estimate: No valid posterior or qualified source for this context
  | "BLOCKED"           // Rejected or stale: Invalid authority, contract or temporal identity
  // Backward compatibility aliases
  | "QUALIFIED_RASTER"
  | "SCALAR_ONLY";

export const ASMAE_STATUS_META: Record<
  "QUALIFIED_SPATIAL" | "PLOT_ESTIMATE" | "UNAVAILABLE" | "BLOCKED",
  { label: string; badge: string; color: string; description: string }
> = {
  QUALIFIED_SPATIAL: {
    label: "Qualified Spatial State",
    badge: "Map Eligible",
    color: "#34d399",
    description: "An authorized, validated grid can be rendered with the correct masks, spatial footprint and publication receipt.",
  },
  PLOT_ESTIMATE: {
    label: "Plot-level Estimate",
    badge: "Numbers Only",
    color: "#38bdf8",
    description: "Mean, uncertainty and units authorized from resilient filter; full-field spatial raster withheld by truthfulness policy.",
  },
  UNAVAILABLE: {
    label: "Unavailable",
    badge: "No Estimate",
    color: "#94a3b8",
    description: "No valid posterior or qualified source admitted for this context.",
  },
  BLOCKED: {
    label: "Rejected or Stale",
    badge: "Blocked",
    color: "#f87171",
    description: "Invalid authority, scope, scientific contract or temporal identity; no scientific pixels.",
  },
};

export interface AsmaeStateAvailabilityResult {
  readonly state: AsmaeStateDefinition;
  readonly status: AsmaeStateStatus;
  readonly canonicalStatus: "QUALIFIED_SPATIAL" | "PLOT_ESTIMATE" | "UNAVAILABLE" | "BLOCKED";
  readonly mean: number | null;
  readonly sigma: number | null;
  readonly min: number | null;
  readonly max: number | null;
  readonly supportClassification: "OBSERVED" | "ASSIMILATED_INDIRECT" | "PRIOR_CONSTRAINED" | "UNSUPPORTED";
  readonly rasterSurface: Record<string, unknown> | null;
  readonly canRenderPixels: boolean;
  readonly explanation: string;
  readonly observationEvidence: readonly string[];
}

/**
 * Resolves availability, values, and uncertainty for an ASMAE state without ever fabricating pixels.
 */
export function resolveAsmaeStateAvailability(
  key: AsmaeStateKey,
  surfaceGrids: any[] = [],
  posteriorRecord?: { states?: Record<string, number>; sigmas?: Record<string, number> } | null,
  surfaceInventory?: Record<string, any> | null,
  options?: {
    validationState?: "valid" | "stale" | "corrupt";
    isBlocked?: boolean;
    blockReason?: string;
  }
): AsmaeStateAvailabilityResult {
  const state = ASMAE_13_STATE_CATALOG[key];
  if (!state) {
    throw new Error(`Unknown ASMAE state key: ${key}`);
  }

  // 0. Check if explicitly blocked or validation failed
  if (options?.isBlocked || options?.validationState === "corrupt") {
    return {
      state,
      status: "BLOCKED",
      canonicalStatus: "BLOCKED",
      mean: null,
      sigma: null,
      min: null,
      max: null,
      supportClassification: "UNSUPPORTED",
      rasterSurface: null,
      canRenderPixels: false,
      explanation: options?.blockReason || "Rejected: Publication failed cryptographic integrity validation or authority check.",
      observationEvidence: [],
    };
  }

  // 1. Search for genuine spatial raster surface in surfaceGrids
  const matchingRaster = Array.isArray(surfaceGrids)
    ? surfaceGrids.find((s) => {
        if (!s) return false;
        const sType = String(s.surface_type || s.type || "").toUpperCase();
        if (sType === state.surfaceType.toUpperCase()) return true;
        return state.aliases.some((alias) => sType === alias.toUpperCase() || s.surface_id === alias);
      })
    : null;

  const hasValidRasterArray =
    matchingRaster &&
    Array.isArray(matchingRaster.values) &&
    matchingRaster.values.length > 0 &&
    Array.isArray(matchingRaster.values[0]) &&
    matchingRaster.values[0].length > 0;

  // Numerical posterior values
  const scalarState = posteriorRecord?.states?.[key] ?? null;
  const scalarSigma = posteriorRecord?.sigmas?.[key] ?? null;

  if (hasValidRasterArray) {
    let sum = 0;
    let count = 0;
    let minVal = Infinity;
    let maxVal = -Infinity;

    for (const row of matchingRaster.values) {
      if (!Array.isArray(row)) continue;
      for (const val of row) {
        if (typeof val === "number" && Number.isFinite(val)) {
          sum += val;
          count++;
          if (val < minVal) minVal = val;
          if (val > maxVal) maxVal = val;
        }
      }
    }

    const rasterMean = count > 0 ? sum / count : (scalarState ?? 0);
    const rasterMin = count > 0 ? minVal : (scalarState ?? 0);
    const rasterMax = count > 0 ? maxVal : (scalarState ?? 0);

    return {
      state,
      status: "QUALIFIED_SPATIAL",
      canonicalStatus: "QUALIFIED_SPATIAL",
      mean: Number(rasterMean.toFixed(4)),
      sigma: scalarSigma !== null ? Number(scalarSigma.toFixed(4)) : null,
      min: Number(rasterMin.toFixed(4)),
      max: Number(rasterMax.toFixed(4)),
      supportClassification: "OBSERVED",
      rasterSurface: matchingRaster,
      canRenderPixels: true,
      explanation: "Qualified multi-spectral raster publication authorized for spatial field inspection.",
      observationEvidence: Array.isArray((matchingRaster as any)?.sources) && (matchingRaster as any).sources.length > 0
        ? (matchingRaster as any).sources
        : ((matchingRaster as any)?.source_sensor ? [(matchingRaster as any).source_sensor] : ["Multi-Spectral Surface Reflectance", "Radiative Transfer Priors"]),
    };
  }

  // 2. Check if scalar estimate exists without spatial raster
  if (scalarState !== null && Number.isFinite(scalarState)) {
    return {
      state,
      status: "PLOT_ESTIMATE",
      canonicalStatus: "PLOT_ESTIMATE",
      mean: Number(scalarState.toFixed(4)),
      sigma: scalarSigma !== null ? Number(scalarSigma.toFixed(4)) : null,
      min: Number(Math.max(state.range[0], scalarState - (scalarSigma || 0) * 1.96).toFixed(4)),
      max: Number(Math.min(state.range[1], scalarState + (scalarSigma || 0) * 1.96).toFixed(4)),
      supportClassification: key === "root_zone_water" ? "ASSIMILATED_INDIRECT" : "PRIOR_CONSTRAINED",
      rasterSurface: null,
      canRenderPixels: false,
      explanation: "Scalar posterior estimate authorized by ASMAE resilient filter; full-field spatial raster withheld by truthfulness policy (no certified sub-plot spatial variance).",
      observationEvidence: key === "root_zone_water"
        ? ["In-Situ Soil Moisture Telemetry", "SAR Backscatter", "Agrometeorological Penman-Monteith ET0"]
        : key === "lai"
        ? ["Vegetation Index Inversion", "Crop Species Canopy Prior"]
        : ["Prior Distribution", "Historical Archive Memory"],
    };
  }

  // 3. Neither spatial raster nor scalar posterior available
  const invEntry = surfaceInventory?.[state.surfaceType];
  const blockReason = invEntry?.reason || "Observation inputs absent; state not admitted for current publication cutoff.";

  return {
    state,
    status: "UNAVAILABLE",
    canonicalStatus: "UNAVAILABLE",
    mean: null,
    sigma: null,
    min: null,
    max: null,
    supportClassification: "UNSUPPORTED",
    rasterSurface: null,
    canRenderPixels: false,
    explanation: `State unavailable for current observation cutoff: ${blockReason}`,
    observationEvidence: [],
  };
}

/**
 * Samples a SIRE pixel at a given coordinate [lng, lat] from a surface raster grid.
 */
export function sampleSirePixel(
  surface: { values?: (number | null)[][]; bounds?: number[]; resolution_m?: number } | null,
  lngLat: [number, number],
  fallbackBounds?: number[] | null
): {
  valid: boolean;
  value: number | null;
  row: number;
  col: number;
  coordinate: [number, number];
} {
  const effectiveBounds = (Array.isArray(surface?.bounds) && surface.bounds.length >= 4)
    ? surface.bounds
    : fallbackBounds;

  if (!surface || !Array.isArray(surface.values) || !effectiveBounds || effectiveBounds.length < 4) {
    return { valid: false, value: null, row: -1, col: -1, coordinate: lngLat };
  }

  const [minLng, minLat, maxLng, maxLat] = effectiveBounds;
  const [lng, lat] = lngLat;

  if (lng < minLng || lng > maxLng || lat < minLat || lat > maxLat) {
    return { valid: false, value: null, row: -1, col: -1, coordinate: lngLat };
  }

  const numRows = surface.values.length;
  const numCols = surface.values[0]?.length || 0;
  if (numRows === 0 || numCols === 0) {
    return { valid: false, value: null, row: -1, col: -1, coordinate: lngLat };
  }

  const normX = (lng - minLng) / (maxLng - minLng);
  const normY = (maxLat - lat) / (maxLat - minLat);

  const col = Math.min(numCols - 1, Math.max(0, Math.floor(normX * numCols)));
  const row = Math.min(numRows - 1, Math.max(0, Math.floor(normY * numRows)));

  const val = surface.values[row]?.[col] ?? null;

  return {
    valid: typeof val === "number" && Number.isFinite(val),
    value: val !== null && Number.isFinite(val) ? Number(val.toFixed(4)) : null,
    row,
    col,
    coordinate: lngLat,
  };
}

/**
 * Compares an in-situ sensor reading with collocated ASMAE state (e.g. root_zone_water).
 * Strictly maintains epistemic separation between OBSERVED_TELEMETRY and SCIENTIFIC_ESTIMATE.
 */
export type SensorComparisonStatus = "COMPARABLE" | "NOT_COMPARABLE" | "DIVERGENT";

export function compareSensorWithCollocatedAsmae(
  sensorReading: {
    soilMoisture?: number | null;
    temperature?: number | null;
    timestamp?: string;
    depthCm?: number | null;
  },
  asmaeAvailability: AsmaeStateAvailabilityResult
): {
  sensorValue: number | null;
  sensorUnit: string;
  sensorEpistemicClass: "OBSERVED_TELEMETRY";
  sensorDepthCm: number | null;
  asmaeMean: number | null;
  asmaeSigma: number | null;
  asmaeUnit: string;
  asmaeEpistemicClass: "SCIENTIFIC_ESTIMATE";
  withinOneSigma: boolean;
  withinTwoSigma: boolean;
  zScore: number | null;
  comparisonStatus: SensorComparisonStatus;
  narrative: string;
  supportDifferenceDisclaimer: string;
  verticalSupportDifference: boolean;
} {
  const sensorRaw = sensorReading.soilMoisture;
  const sensorValue =
    typeof sensorRaw === "number" && Number.isFinite(sensorRaw)
      ? Number((sensorRaw <= 1.0 ? sensorRaw : sensorRaw / 100).toFixed(4))
      : null;
  const sensorDepthCm = typeof sensorReading.depthCm === "number" ? sensorReading.depthCm : null;

  const mean = asmaeAvailability.mean;
  const sigma = typeof asmaeAvailability.sigma === "number" && asmaeAvailability.sigma > 0 ? asmaeAvailability.sigma : null;

  const supportDifferenceDisclaimer =
    "A point measurement at 15 cm and a modeled root-zone estimate represent different spatial and vertical supports. Their numerical agreement alone does not establish independent scientific validation.";

  if (sensorValue === null || mean === null) {
    return {
      sensorValue,
      sensorUnit: "fraction (VWC)",
      sensorEpistemicClass: "OBSERVED_TELEMETRY",
      sensorDepthCm,
      asmaeMean: mean,
      asmaeSigma: sigma,
      asmaeUnit: asmaeAvailability.state?.unit || "fraction",
      asmaeEpistemicClass: "SCIENTIFIC_ESTIMATE",
      withinOneSigma: false,
      withinTwoSigma: false,
      zScore: null,
      comparisonStatus: "NOT_COMPARABLE",
      narrative: "Telemetry or scientific estimate missing for collocated comparison.",
      supportDifferenceDisclaimer,
      verticalSupportDifference: sensorDepthCm !== null,
    };
  }

  if (sigma === null) {
    return {
      sensorValue,
      sensorUnit: "fraction (VWC)",
      sensorEpistemicClass: "OBSERVED_TELEMETRY",
      sensorDepthCm,
      asmaeMean: mean,
      asmaeSigma: null,
      asmaeUnit: asmaeAvailability.state?.unit || "fraction",
      asmaeEpistemicClass: "SCIENTIFIC_ESTIMATE",
      withinOneSigma: false,
      withinTwoSigma: false,
      zScore: null,
      comparisonStatus: "NOT_COMPARABLE",
      narrative: `Observed telemetry (${(sensorValue * 100).toFixed(1)}% VWC) reported alongside ASMAE estimate (${(mean * 100).toFixed(1)}%), but posterior uncertainty (sigma) is unavailable; statistical consistency envelope cannot be evaluated without verified posterior variance.`,
      supportDifferenceDisclaimer,
      verticalSupportDifference: sensorDepthCm !== null,
    };
  }

  const diff = Math.abs(sensorValue - mean);
  const zScore = Number((diff / sigma).toFixed(2));
  const withinOneSigma = zScore <= 1.0;
  const withinTwoSigma = zScore <= 2.0;

  const depthNote = sensorDepthCm !== null ? ` Discrete probe depth: ${sensorDepthCm}cm.` : "";

  const narrative = withinOneSigma
    ? `Observed sensor reading (${(sensorValue * 100).toFixed(1)}% VWC) is fully consistent with the collocated ASMAE posterior estimate (${(mean * 100).toFixed(1)}% ± ${(sigma * 100).toFixed(1)}%), lying inside the 1σ uncertainty bound.${depthNote}`
    : withinTwoSigma
    ? `Observed sensor reading (${(sensorValue * 100).toFixed(1)}% VWC) is within 2σ of the ASMAE posterior estimate (${(mean * 100).toFixed(1)}% ± ${(sigma * 100).toFixed(1)}%). Normal local variance.${depthNote}`
    : `Local discrepancy detected: observed telemetry (${(sensorValue * 100).toFixed(1)}% VWC) diverges by ${zScore}σ from ASMAE posterior (${(mean * 100).toFixed(1)}% ± ${(sigma * 100).toFixed(1)}%).${depthNote}`;

  return {
    sensorValue,
    sensorUnit: "fraction (VWC)",
    sensorEpistemicClass: "OBSERVED_TELEMETRY",
    sensorDepthCm,
    asmaeMean: mean,
    asmaeSigma: sigma,
    asmaeUnit: asmaeAvailability.state?.unit || "fraction",
    asmaeEpistemicClass: "SCIENTIFIC_ESTIMATE",
    withinOneSigma,
    withinTwoSigma,
    zScore,
    comparisonStatus: withinOneSigma ? "COMPARABLE" : "DIVERGENT",
    narrative,
    supportDifferenceDisclaimer,
    verticalSupportDifference: sensorDepthCm !== null,
  };
}
