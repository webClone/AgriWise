const PIXEL_GROUNDING_CLASSES = new Set([
  "RASTER_GROUNDED",
  "PARTIAL_RASTER_GROUNDED",
  "MODEL_ASSISTED_RASTER",
  "PROXY_SPATIAL",
]);

function explicitSurfaceFlag(surface, snakeName, camelName) {
  if (!surface || typeof surface !== "object") return false;
  const provenance = surface.provenance && typeof surface.provenance === "object"
    ? surface.provenance
    : {};
  return surface[snakeName] === true
    || surface[camelName] === true
    || provenance[snakeName] === true
    || provenance[camelName] === true;
}

/**
 * Pixel sampling and scientific interpretation are separate permissions.
 * A committed model-assisted raster may be sampled for a scouting hint while
 * diagnostic classes and prescription use remain denied by the backend.
 */
export function resolvePixelInspectorCapabilities({ surface, inspectorAuthorization } = {}) {
  const groundingClass = String(surface?.grounding_class || surface?.groundingClass || "").toUpperCase();
  const hasValues = Array.isArray(surface?.values) && surface.values.some(
    (row) => Array.isArray(row) && row.some((value) => Number.isFinite(value)),
  );
  const canSamplePixel = hasValues && PIXEL_GROUNDING_CLASSES.has(groundingClass);
  const canInterpretForScouting = canSamplePixel;
  const canInterpretDiagnostically = canSamplePixel
    && inspectorAuthorization?.authorized === true
    && inspectorAuthorization?.inspectorAllowed === true;
  const canUseForPrescription = canInterpretDiagnostically
    && explicitSurfaceFlag(surface, "prescription_driver_allowed", "prescriptionDriverAllowed")
    && explicitSurfaceFlag(surface, "management_eligible", "managementEligible");

  return {
    canSamplePixel,
    canInterpretForScouting,
    canInterpretDiagnostically,
    canUseForPrescription,
  };
}

const SURFACE_TITLES = Object.freeze({
  WATER_ASMAE_CANOPY_WATER: "Canopy Water State",
  WATER_ASMAE_ROOT_ZONE_WATER: "Root-Zone Water State",
  NUTRIENT_ASMAE_CHLOROPHYLL_PROXY: "Chlorophyll State",
  WATER_STRESS_PROB: "Water Stress Probability",
  NUTRIENT_STRESS_PROB: "Nutrient Stress Probability",
});

export function resolvePixelInspectorTitle(surfaceType, activeMode) {
  const type = String(surfaceType || "").toUpperCase();
  if (SURFACE_TITLES[type]) return SURFACE_TITLES[type];
  if (activeMode === "water_stress") return "Water Stress / Aridity";
  if (activeMode === "nutrient_risk") return "Nutrient Stress Index";
  return null;
}

export function resolveCropStageLabels(cropName, cropStage) {
  const crop = String(cropName || "").trim();
  const stage = String(cropStage || "").trim();
  const knownStage = stage && !["unknown", "unavailable", "none", "null"].includes(stage.toLowerCase());
  return {
    cropLabel: crop ? `Crop: ${crop}` : null,
    growthStageLabel: knownStage ? `Growth stage: ${stage.replace(/_/g, " ")}` : null,
  };
}
