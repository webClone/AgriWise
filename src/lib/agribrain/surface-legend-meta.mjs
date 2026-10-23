const EXACT_SURFACE_META = Object.freeze({
  NDVI_CLEAN: {
    label: "Canopy (NDVI)", unit: "NDVI", lowLabel: "Bare / stressed",
    midLabel: "Moderate", highLabel: "Dense / healthy",
    stopLabels: ["Very low", "Low", "Moderate", "Good", "Healthy"],
    colors: ["rgb(255, 0, 0)", "rgb(255, 255, 0)", "rgb(0, 204, 0)"],
  },
  CANOPY_ASMAE_VIGOR: {
    label: "ASMAE Canopy Vigor", unit: "fraction", lowLabel: "Low vigor",
    midLabel: "Moderate", highLabel: "High vigor",
    stopLabels: ["Very low", "Low", "Moderate", "Good", "High"],
    colors: ["#8B0000", "#FFD700", "#006400"],
  },
  WATER_ASMAE_CANOPY_WATER: {
    label: "Canopy Water State", unit: "fraction", lowLabel: "Low canopy water",
    midLabel: "Moderate", highLabel: "High canopy water",
    stopLabels: ["Very low", "Low", "Moderate", "High", "Very high"],
    colors: ["#c0392b", "#f1c40f", "#1a5276"],
  },
  WATER_ASMAE_ROOT_ZONE_WATER: {
    label: "Root-Zone Water State", unit: "fraction", lowLabel: "Low root-zone water",
    midLabel: "Moderate", highLabel: "High root-zone water",
    stopLabels: ["Very low", "Low", "Moderate", "High", "Very high"],
    colors: ["#c0392b", "#f1c40f", "#1a5276"],
  },
  ASMAE_PHENOLOGY_PROGRESS: {
    label: "Phenology Progress", unit: "fraction", lowLabel: "Vegetative / early",
    midLabel: "Mid cycle", highLabel: "Maturity / senescent",
    stopLabels: ["Early", "Developing", "Mid cycle", "Advanced", "Mature"],
    colors: ["#8B0000", "#FFD700", "#006400"],
  },
  ASMAE_STRESS_MEMORY: {
    label: "Stress Memory", unit: "fraction", lowLabel: "Low persistence",
    midLabel: "Moderate", highLabel: "Severe memory",
    stopLabels: ["None", "Low", "Moderate", "High", "Critical"],
    colors: ["#fff7bc", "#fc8d59", "#b91c1c"],
  },
  NUTRIENT_ASMAE_CHLOROPHYLL_PROXY: {
    label: "Chlorophyll State", unit: "µg/cm²", lowLabel: "Low chlorophyll",
    midLabel: "Moderate", highLabel: "High chlorophyll",
    stopLabels: ["Very low", "Low", "Moderate", "High", "Very high"],
    colors: ["#c0392b", "#f1c40f", "#27ae60"],
  },
});

const PALETTE_COLORS = Object.freeze({
  VIGOR_GREEN: ["#8B0000", "#FFD700", "#006400"],
  STRESS_RED: ["#fff7bc", "#fc8d59", "#b91c1c"],
  UNCERTAINTY_GRAY: ["#f8fafc", "#94a3b8", "#1e293b"],
  RISK_HEAT: ["#ffffbf", "#fc8d59", "#d73027"],
  DISEASE_ORANGE: ["#fff7bc", "#fd8d3c", "#7f0000"],
  NUTRIENT_YELLOW: ["#c0392b", "#f1c40f", "#27ae60"],
  YIELD_BLUE: ["#c0392b", "#f1c40f", "#1a5276"],
  SALINITY_TEAL: ["#0d9488", "#22d3ee", "#ef4444"],
  RAW_GRAYSCALE: ["#f8fafc", "#94a3b8", "#1e293b"],
  CARBON_BROWN: ["#fef3c7", "#a16207", "#451a03"],
  COMPACTION_PURPLE: ["#f3e8ff", "#a855f7", "#581c87"],
  THERMAL_ORANGE: ["#fff7ed", "#fb923c", "#9a3412"],
});

const VISUAL_LENS_COLORS = Object.freeze({
  thermal: ["rgb(255, 0, 0)", "rgb(255, 255, 0)", "rgb(0, 204, 0)"],
  chlorophyll: ["rgb(20, 40, 160)", "rgb(40, 180, 40)", "rgb(230, 230, 20)"],
  chluoro: ["rgb(20, 40, 160)", "rgb(40, 180, 40)", "rgb(230, 230, 20)"],
  chroma: ["rgb(99, 102, 241)", "rgb(236, 72, 153)", "rgb(234, 179, 8)"],
});

const CATEGORICAL_SURFACES = new Set([
  "RESOLUTION_COVERAGE", "ZONE_POLICY", "FALLBACK_REASON", "GROWTH_STAGE_CLASS",
]);

function humanizeSurfaceType(surfaceType) {
  return String(surfaceType || "Scientific raster")
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function resolveSurfacePalette(surface, fallback = null, visualLens = "standard") {
  if (!surface) return fallback;
  const surfaceType = String(surface.type || surface.semantic_type || "").toUpperCase();
  const lens = String(visualLens || "standard").toLowerCase();
  if (!CATEGORICAL_SURFACES.has(surfaceType) && VISUAL_LENS_COLORS[lens]) {
    return [...VISUAL_LENS_COLORS[lens]];
  }
  const exact = EXACT_SURFACE_META[surfaceType];
  if (exact?.colors) return [...exact.colors];
  const palette = PALETTE_COLORS[String(surface.palette_id || "").toUpperCase()];
  return palette ? [...palette] : fallback;
}

function finiteSurfaceValues(surface) {
  const rows = Array.isArray(surface?.values) ? surface.values : [];
  const values = [];
  for (const row of rows) {
    for (const raw of Array.isArray(row) ? row : [row]) {
      const value = Number(raw);
      if (raw !== null && raw !== undefined && Number.isFinite(value)) values.push(value);
    }
  }
  return values;
}

/**
 * One numerical display contract for both raster pixels and their legend.
 * Field-percentile displays remain diagnostic/scouting-relative and disclose
 * both the active stretch and the declared physical contract.
 */
export function resolveSurfaceDisplayScale(
  surface,
  { activeMode = "canopy", detailMode = "farmer" } = {},
) {
  const declared = Array.isArray(surface?.render_range) && surface.render_range.length >= 2
    ? [Number(surface.render_range[0]), Number(surface.render_range[1])]
    : [0, 1];
  let [min, max] = declared;
  const type = String(surface?.type || surface?.semantic_type || "").toUpperCase();
  const mode = String(activeMode || "canopy").toLowerCase();
  const isAbsoluteMode = mode === "vegetation" || mode === "canopy";
  const isDiverging = mode === "veg_attention";
  const useFieldStretch = !isAbsoluteMode || type.includes("ASMAE") || type.includes("EXPERIMENTAL");
  const values = finiteSurfaceValues(surface);
  let lowPercentile = null;
  let highPercentile = null;

  if (useFieldStretch && values.length > 10) {
    values.sort((a, b) => a - b);
    if (isDiverging) {
      lowPercentile = 0.02;
      highPercentile = 0.98;
      const pLow = values[Math.floor(values.length * lowPercentile)];
      const pHigh = values[Math.floor(values.length * highPercentile)];
      const maxAbs = Math.max(Math.abs(pLow), Math.abs(pHigh));
      if (maxAbs > 0) [min, max] = [-maxAbs, maxAbs];
    } else {
      lowPercentile = isAbsoluteMode ? 0.05 : (detailMode === "expert" ? 0.01 : 0.02);
      highPercentile = isAbsoluteMode ? 0.95 : (detailMode === "expert" ? 0.99 : 0.98);
      const pLow = values[Math.floor(values.length * lowPercentile)];
      const pHigh = values[Math.floor(values.length * highPercentile)];
      if (pHigh > pLow) [min, max] = [pLow, pHigh];
    }
  }

  const stretched = useFieldStretch && (min !== declared[0] || max !== declared[1]);
  return {
    min,
    max,
    declaredMin: declared[0],
    declaredMax: declared[1],
    policy: stretched ? "field_percentile" : "declared_physical_range",
    lowPercentile,
    highPercentile,
    labels: stretched
      ? ["Lower in this field", "Typical in this field", "Higher in this field"]
      : null,
  };
}

export function resolveCommittedSurfaceLegend(surface, fallback, visualLens = "standard") {
  if (!surface) return fallback;
  const surfaceType = String(surface.type || surface.semantic_type || "").toUpperCase();
  const exact = EXACT_SURFACE_META[surfaceType];
  const palette = resolveSurfacePalette(surface, null, visualLens);
  if (exact) {
    return {
      ...fallback,
      label: exact.label,
      unit: exact.unit || surface.units || fallback.unit,
      lowColor: palette?.[0] || exact.colors[0],
      midColor: palette?.[1] || exact.colors[1],
      highColor: palette?.[2] || exact.colors[2],
      lowLabel: exact.lowLabel,
      midLabel: exact.midLabel,
      highLabel: exact.highLabel,
      stopLabels: exact.stopLabels,
    };
  }
  return {
    ...fallback,
    label: humanizeSurfaceType(surfaceType),
    unit: String(surface.units || fallback.unit || "value"),
    ...(palette ? {
      lowColor: palette[0], midColor: palette[1], highColor: palette[2],
    } : {}),
  };
}
