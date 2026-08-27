import type { IllustrativeWorld } from "./schema";
import opticalMeta from "./demo-optical.meta.json";

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

export function validateIllustrativeWorld(world: IllustrativeWorld): ValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];
  const idSet = new Set<string>();

  // Helper to check polygon ring closure
  const isRingClosed = (coords: [number, number][]) => {
    if (coords.length < 4) return false;
    const first = coords[0];
    const last = coords[coords.length - 1];
    return first[0] === last[0] && first[1] === last[1];
  };

  // Helper to check if coordinate is inside optical bounds [west, south, east, north]
  const [w, s, e, n] = opticalMeta.bounds;
  const isInsideOpticalBounds = (coord: [number, number]) => {
    // Add small tolerance (0.005deg) for edge points
    const tol = 0.005;
    return coord[0] >= w - tol && coord[0] <= e + tol && coord[1] >= s - tol && coord[1] <= n + tol;
  };

  // 1. Validate Meta
  if (!world.meta || !world.meta.primaryPlotId || !world.meta.primaryLineage) {
    errors.push("Meta block missing or incomplete");
  }

  // 2. Validate Plots
  const plotMap = new Map<string, typeof world.plots[0]>();
  for (const plot of world.plots) {
    if (idSet.has(plot.id)) errors.push(`Duplicate ID: ${plot.id}`);
    idSet.add(plot.id);
    plotMap.set(plot.id, plot);

    if (!isRingClosed(plot.coordinates)) {
      errors.push(`Plot ${plot.id} polygon ring is not closed`);
    }

    for (const pt of plot.coordinates) {
      if (!isInsideOpticalBounds(pt)) {
        warnings.push(`Plot ${plot.id} coordinate [${pt[0]}, ${pt[1]}] extends beyond optical image bounds`);
      }
    }
  }

  // 3. Validate Farms
  const farmMap = new Map<string, typeof world.farms[0]>();
  for (const farm of world.farms) {
    if (idSet.has(farm.id)) errors.push(`Duplicate ID: ${farm.id}`);
    idSet.add(farm.id);
    farmMap.set(farm.id, farm);

    for (const pId of farm.plotIds) {
      if (!plotMap.has(pId)) {
        errors.push(`Farm ${farm.id} references non-existent plot: ${pId}`);
      }
    }
  }

  // 4. Validate Portfolios
  const portfolioMap = new Map<string, typeof world.portfolios[0]>();
  for (const pf of world.portfolios) {
    if (idSet.has(pf.id)) errors.push(`Duplicate ID: ${pf.id}`);
    idSet.add(pf.id);
    portfolioMap.set(pf.id, pf);

    for (const fId of pf.farmIds) {
      if (!farmMap.has(fId)) {
        errors.push(`Portfolio ${pf.id} references non-existent farm: ${fId}`);
      }
    }
  }

  // 5. Validate Regions
  const regionMap = new Map<string, typeof world.regions[0]>();
  for (const reg of world.regions) {
    if (idSet.has(reg.id)) errors.push(`Duplicate ID: ${reg.id}`);
    idSet.add(reg.id);
    regionMap.set(reg.id, reg);

    if (!isRingClosed(reg.coordinates)) {
      errors.push(`Region ${reg.id} polygon ring is not closed`);
    }
  }

  // 6. Validate Country
  if (!world.country) {
    errors.push("Country entity missing");
  } else {
    if (world.country.geometryClass === "REFERENCE_GEOGRAPHY" && !world.country.referenceSource) {
      errors.push("Country referenceSource metadata missing for REFERENCE_GEOGRAPHY");
    }
    if (!isRingClosed(world.country.coordinates)) {
      errors.push("Country polygon ring is not closed");
    }
  }

  // 7. Validate Primary Lineage Chain
  const lineage = world.meta.primaryLineage;
  if (lineage.length !== 5) {
    errors.push("Primary lineage must contain 5 entities: [plot, farm, portfolio, region, country]");
  } else {
    const [pId, fId, pfId, rId, cId] = lineage;
    const plot = plotMap.get(pId);
    if (!plot) errors.push(`Primary lineage plot missing: ${pId}`);
    else if (plot.farmId !== fId) errors.push(`Primary lineage plot farmId mismatch: ${plot.farmId} vs ${fId}`);

    const farm = farmMap.get(fId);
    if (!farm) errors.push(`Primary lineage farm missing: ${fId}`);
    else if (farm.portfolioId !== pfId) errors.push(`Primary lineage farm portfolioId mismatch: ${farm.portfolioId} vs ${pfId}`);

    const pf = portfolioMap.get(pfId);
    if (!pf) errors.push(`Primary lineage portfolio missing: ${pfId}`);
    else if (pf.regionId !== rId) errors.push(`Primary lineage portfolio regionId mismatch: ${pf.regionId} vs ${rId}`);

    const reg = regionMap.get(rId);
    if (!reg) errors.push(`Primary lineage region missing: ${rId}`);
    else if (reg.countryId !== cId) errors.push(`Primary lineage region countryId mismatch: ${reg.countryId} vs ${cId}`);
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
  };
}

// Executable CLI runner
if (typeof window === "undefined" && typeof process !== "undefined" && process.argv && process.argv[1] && process.argv[1].includes("validation.ts")) {
  const worldData = require("./illustrative-world.v1.json");
  const res = validateIllustrativeWorld(worldData);
  if (res.valid) {
    console.log("[AgriWise World Validator] ✓ Validation PASSED cleanly with 0 errors.");
    if (res.warnings.length > 0) {
      console.log(`[AgriWise World Validator] Warnings (${res.warnings.length}):`, res.warnings);
    }
    process.exit(0);
  } else {
    console.error("[AgriWise World Validator] ✗ Validation FAILED with errors:", res.errors);
    process.exit(1);
  }
}
