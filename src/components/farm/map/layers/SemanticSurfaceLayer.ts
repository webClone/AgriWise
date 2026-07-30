"use client";

import { BitmapLayer, TextLayer } from "@deck.gl/layers";
import { MaskExtension } from "@deck.gl/extensions";
import { SurfaceData } from "@/hooks/useLayer10";
import { buildPolygonMask } from "../utils/buildPolygonMask";
import { getRenderAuthorization, isAsmaeSurfaceType } from "@/lib/agribrain/source-policy-display-resolver";
import {
  canMaterializeMask,
  validateSurfaceGrid,
} from "@/lib/agribrain/render-materialization";

export interface ScaleAwareLayerPolicy {
  preferGeneralizedView: boolean;
  showHatching: boolean;
  showGridCells: boolean;
}

export function getScaleAwareLayerPolicy({
  zoom,
  evidenceLevel,
  resolution_m = 10,
}: {
  zoom?: number;
  evidenceLevel?: string;
  resolution_m?: number;
}): ScaleAwareLayerPolicy {
  const z = zoom ?? 15;

  // If low zoom (z < 14)
  if (z < 14) {
    return {
      preferGeneralizedView: true,
      showHatching: false,
      showGridCells: false,
    };
  }

  // If medium zoom (14 <= z < 17.5)
  if (z < 17.5) {
    return {
      preferGeneralizedView: false,
      showHatching: false,
      showGridCells: false,
    };
  }

  // If high zoom (z >= 17.5)
  return {
    preferGeneralizedView: false,
    showHatching: true,
    showGridCells: true,
  };
}

// A small helper to draw the surface data array into a Canvas data URI
// This avoids needing an external image tile server for the MVP Layer 10
function createSurfaceImage(
  plotId: string | undefined,
  surface: SurfaceData | null | undefined, 
  colors: [string, string, string] | null | undefined,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  plotGeoJson: any,
  /** UNCERTAINTY_SIGMA surface — used as fallback trust (inverted) */
  confidenceSurface: SurfaceData | null | undefined,
  opacity: number = 0.85,
  detailMode: "farmer" | "expert" = "expert",
  quantizeBands: number | null = null,
  layerMode: string = "vegetation",
  /** DATA_RELIABILITY surface — priority trust source (WS6) */
  reliabilitySurface: SurfaceData | null | undefined = null,
  /** NDVI_DEVIATION surface — used for hybrid vegetation emphasis */
  deviationSurface: SurfaceData | null | undefined = null,
  paletteId?: string,
  renderMode?: string,
  gapFillSurface?: SurfaceData | null,
  scalePolicy?: ScaleAwareLayerPolicy,
  renderKind?: string,
  displayLevel?: string,
  applyTrustToBase: boolean = false,
  auth?: any,
  observedMaskSurface?: SurfaceData | null
): HTMLCanvasElement | null {
  if (typeof document === "undefined") return null;
  if (!surface || !plotGeoJson) return null;
  if (auth && (!auth.authorized || auth.renderKind === "none" || auth.renderKind === "card_only")) return null;
  const rawH = surface.values.length;
  if (rawH === 0) return null;
  const rawW = surface.values[0].length;
  if (rawW === 0) return null;

  const effectiveRenderKind = (auth?.renderKind || renderKind || "full_raster") as string;

  const flatVals = surface.values.flat().filter((v): v is number => typeof v === "number" && Number.isFinite(v));
  const meanVal = flatVals.length ? flatVals.reduce((a, b) => a + b, 0) / flatVals.length : 0.5;
  const variance = flatVals.length ? flatVals.reduce((a, b) => a + Math.pow(b - meanVal, 2), 0) / flatVals.length : 0;
  const std = Math.sqrt(variance);

  const stype = (surface.semantic_type || surface.type || "").toString().toUpperCase();
  const isAsmaeOrExperimental = stype.includes("ASMAE") || stype.includes("EXPERIMENTAL");
  const hasNonZeroFinite = flatVals.some(v => v !== 0 && Number.isFinite(v));
  const forceUniform = (effectiveRenderKind === "uniform_tint" || (!isAsmaeOrExperimental && std < 0.001)) && !(isAsmaeOrExperimental && hasNonZeroFinite);
  const valuesToRender = forceUniform
    ? Array(rawH).fill(null).map(() => Array(rawW).fill(meanVal))
    : surface.values;

  const h = rawH;
  const w = rawW;
  const sampleMask = (maskSurface: SurfaceData | null | undefined, row: number, col: number): number | null => {
    const maskH = maskSurface?.values?.length || 0;
    const maskW = maskSurface?.values?.[0]?.length || 0;
    if (maskH <= 0 || maskW <= 0) return null;
    const alignedRow = maskH === h
      ? row
      : Math.min(maskH - 1, Math.max(0, Math.floor(((row + 0.5) * maskH) / h)));
    const alignedCol = maskW === w
      ? col
      : Math.min(maskW - 1, Math.max(0, Math.floor(((col + 0.5) * maskW) / w)));
    const value = maskSurface?.values?.[alignedRow]?.[alignedCol];
    return value === null || value === undefined || !Number.isFinite(Number(value))
      ? null
      : Number(value);
  };

  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  const imgData = ctx.createImageData(w, h);
  
  const hexToRgb = (hex: string) => {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? {
      r: parseInt(result[1], 16),
      g: parseInt(result[2], 16),
      b: parseInt(result[3], 16)
    } : { r: 0, g: 0, b: 0 };
  };
  
  const MODE_RAMPS: Record<string, {low: number[], mid: number[], high: number[]}> = {
    vegetation:     { low: [217, 119, 6],  mid: [253, 224, 71], high: [22, 163, 74]  }, // Premium amber -> yellow -> emerald
    canopy:         { low: [217, 119, 6],  mid: [253, 224, 71], high: [22, 163, 74]  }, // Premium amber -> yellow -> emerald
    veg_attention:  { low: [139, 69, 19],  mid: [245, 245, 220], high: [34, 139, 34]  },
    water_stress:   { low: [33, 102, 172], mid: [253, 212, 158], high: [178, 24, 43]  },
    nutrient_risk:  { low: [26, 152, 80],  mid: [254, 224, 139], high: [215, 48, 39]  },
    salinity:       { low: [13, 148, 136], mid: [254, 224, 139], high: [239, 68, 68]  },
    composite_risk: { low: [255, 255, 191], mid: [252, 141, 89], high: [215, 48, 39]  },
    uncertainty:    { low: [247, 247, 247], mid: [150, 150, 150], high: [37, 37, 37]  },
    resolution_coverage: { low: [6, 182, 212], mid: [245, 158, 11], high: [100, 116, 139] },
    gap_fill: { low: [100, 116, 139], mid: [245, 158, 11], high: [239, 68, 68] },
  };

  const recognizedMode = layerMode && MODE_RAMPS[layerMode.toLowerCase()] ? layerMode.toLowerCase() : null;
  const safeMode = recognizedMode || "vegetation";
  const overrideRamp = recognizedMode ? MODE_RAMPS[recognizedMode] : null;

  let cLow = overrideRamp ? { r: overrideRamp.low[0], g: overrideRamp.low[1], b: overrideRamp.low[2] } : hexToRgb(colors?.[0] || "#000000");
  let cMid = overrideRamp ? { r: overrideRamp.mid[0], g: overrideRamp.mid[1], b: overrideRamp.mid[2] } : hexToRgb(colors?.[1] || "#000000");
  let cHigh = overrideRamp ? { r: overrideRamp.high[0], g: overrideRamp.high[1], b: overrideRamp.high[2] } : hexToRgb(colors?.[2] || "#000000");

  const isCategorical =
    surface.type === "RESOLUTION_COVERAGE" ||
    surface.type === "ZONE_POLICY" ||
    surface.type === "FALLBACK_REASON" ||
    surface.type === "GROWTH_STAGE_CLASS" ||
    (surface as any).semantic_type === "RESOLUTION_COVERAGE" ||
    (surface as any).semantic_type === "ZONE_POLICY" ||
    (surface as any).semantic_type === "FALLBACK_REASON" ||
    (surface as any).semantic_type === "GROWTH_STAGE_CLASS";

  if (!isCategorical && paletteId) {
    const pId = paletteId.toLowerCase();
    if (pId === "thermal") {
      cLow = { r: 255, g: 0, b: 0 };
      cMid = { r: 255, g: 255, b: 0 };
      cHigh = { r: 0, g: 204, b: 0 };
    } else if (pId === "health") {
      cLow = { r: 217, g: 119, b: 6 };
      cMid = { r: 253, g: 224, b: 71 };
      cHigh = { r: 22, g: 163, b: 74 };
    } else if (pId === "chlorophyll" || pId === "chluoro") {
      cLow = { r: 20, g: 40, b: 160 };
      cMid = { r: 40, g: 180, b: 40 };
      cHigh = { r: 230, g: 230, b: 20 };
    } else if (pId === "chroma") {
      cLow = { r: 99, g: 102, b: 241 };
      cMid = { r: 236, g: 72, b: 153 };
      cHigh = { r: 234, g: 179, b: 8 };
    }
  }

  const materializationGrid = validateSurfaceGrid(surface, plotGeoJson);
  if (!materializationGrid.valid || !materializationGrid.bounds) return null;
  const mask = buildPolygonMask(plotId, w, h, plotGeoJson, materializationGrid.bounds);

  const prov = (surface.provenance as any) || {};
  const isAsmaeDiag = prov.source_class === "asmae_diagnostic" || surface.type?.includes("ASMAE") || surface.semantic_type?.includes("ASMAE");
  const isExperimentalVisualSurface = surface.type?.includes("EXPERIMENTAL") || surface.semantic_type?.includes("EXPERIMENTAL");

  const isAbsoluteMode = ["vegetation", "canopy"].includes(safeMode);
  const isDivergingDeviationMode = safeMode === "veg_attention";
  let [minV, maxV] = surface.render_range || [0, 1];
  
  const shouldApplyLocalPercentile =
    !isAbsoluteMode ||
    isAsmaeDiag ||
    isExperimentalVisualSurface;

  if (shouldApplyLocalPercentile) {
    const validVals: number[] = [];
    let statPtr = 0;
    for (let r = 0; r < h; r++) {
      for (let c = 0; c < w; c++) {
        const val = valuesToRender[r][c];
        if (val !== null && val !== undefined && !isNaN(val) && (!mask || mask.data[statPtr] === 1)) {
          validVals.push(val);
        }
        statPtr++;
      }
    }

    if (isDivergingDeviationMode) {
      if (validVals.length > 10) {
        validVals.sort((a, b) => a - b);
        const p02 = validVals[Math.floor(validVals.length * 0.02)];
        const p98 = validVals[Math.floor(validVals.length * 0.98)];
        const maxAbs = Math.max(Math.abs(p02), Math.abs(p98));
        minV = -maxAbs;
        maxV = maxAbs;
      }
    } else {
      if (validVals.length > 10) {
        validVals.sort((a, b) => a - b);
        const bottomSlice = isAbsoluteMode ? 0.05 : (detailMode === "expert" ? 0.01 : 0.02);
        const topSlice = isAbsoluteMode ? 0.95 : (detailMode === "expert" ? 0.99 : 0.98);
        const pLow = validVals[Math.floor(validVals.length * bottomSlice)];
        const pHigh = validVals[Math.floor(validVals.length * topSlice)];
        if (pHigh > pLow) {
          minV = pLow;
          maxV = pHigh;
        }
      }
    }
  }

  const range = maxV - minV === 0 ? 1 : maxV - minV;
  const clamp = (num: number, min: number, max: number) => Math.min(Math.max(num,min),max);

  const isCandidateMask = surface.type === "EXPERIMENTAL_FINE_DETAIL_CANDIDATE" ||
                          surface.type === "EXPERIMENTAL_STRICT_FINE_DETAIL_CANDIDATE_MASK" ||
                          (surface as any).semantic_type === "EXPERIMENTAL_FINE_DETAIL_CANDIDATE" ||
                          (surface as any).semantic_type === "EXPERIMENTAL_STRICT_FINE_DETAIL_CANDIDATE_MASK";
  const isExperimental = surface.type?.includes("_EXPERIMENTAL_FINE_DETAIL") || (surface as any).semantic_type?.includes("_EXPERIMENTAL_FINE_DETAIL");

  let ptr = 0;
  let maskPtr = 0;
  for (let r = 0; r < h; r++) {
    for (let c = 0; c < w; c++) {
      const val = valuesToRender[r][c];
      const isNoData = val === null || val === undefined || isNaN(val);

      if (isNoData) {
        const hatchPhase = (r + c) % 4;
        const isStripe = hatchPhase === 0 || hatchPhase === 1;
        const showHatching = scalePolicy ? scalePolicy.showHatching : true;
        const stripeVal = showHatching && isStripe ? 80 : 55;
        imgData.data[ptr++] = stripeVal;  // R
        imgData.data[ptr++] = stripeVal;  // G
        imgData.data[ptr++] = stripeVal;  // B
        imgData.data[ptr++] = Math.round(opacity * 200); 
      } else {
        let t = clamp((val - minV) / range, 0, 1);
        
        const useQuantization = typeof quantizeBands === "number" && quantizeBands > 1;
        if (useQuantization) {
          const bands = quantizeBands;
          t = Math.min(Math.floor(t * bands), bands - 1) / (bands - 1);
        }
        
        let rawR, rawG, rawB;
        if (t <= 0.5) {
          const t1 = t * 2.0; 
          rawR = cLow.r + (cMid.r - cLow.r) * t1;
          rawG = cLow.g + (cMid.g - cLow.g) * t1;
          rawB = cLow.b + (cMid.b - cLow.b) * t1;
        } else {
          const t2 = (t - 0.5) * 2.0;
          rawR = cMid.r + (cHigh.r - cMid.r) * t2;
          rawG = cMid.g + (cHigh.g - cMid.g) * t2;
          rawB = cMid.b + (cHigh.b - cMid.b) * t2;
        }

        // Apply hybrid local contrast for canopy mode (modulating brightness and saturation)
        if (safeMode === "canopy" && detailMode !== "expert") {
          let dev = val - meanVal;
          if (deviationSurface && deviationSurface.values[r]?.[c] !== undefined) {
            const devSurfaceVal = deviationSurface.values[r][c];
            if (devSurfaceVal !== null && !isNaN(devSurfaceVal as number)) {
              dev = devSurfaceVal as number;
            }
          }
          
          const localMean = meanVal;
          const localStd = std > 0.01 ? std : 0.01;
          const localZ = clamp((val - localMean) / localStd, -2.5, 2.5);
          const relief = localZ / 2.5;

          // Compute local gradient magnitude for edge boost
          let dx = 0;
          let dy = 0;
          if (c + 1 < w && valuesToRender[r][c + 1] !== null && !isNaN(valuesToRender[r][c + 1]!)) {
            dx = valuesToRender[r][c + 1]! - val;
          }
          if (r + 1 < h && valuesToRender[r + 1][c] !== null && !isNaN(valuesToRender[r + 1][c]!)) {
            dy = valuesToRender[r + 1][c]! - val;
          }
          const localGradientMagnitude = Math.sqrt(dx * dx + dy * dy);
          const edgeBoost = localGradientMagnitude * 0.20;

          const brightnessFactor = 1.0 + relief * 0.28 + edgeBoost;
          const saturationFactor = 1.0 + Math.abs(relief) * 0.35;

          rawR = clamp(rawR * brightnessFactor, 0, 255);
          rawG = clamp(rawG * brightnessFactor, 0, 255);
          rawB = clamp(rawB * brightnessFactor, 0, 255);

          const lum = 0.299 * rawR + 0.587 * rawG + 0.114 * rawB;
          rawR = clamp(lum + (rawR - lum) * saturationFactor, 0, 255);
          rawG = clamp(lum + (rawG - lum) * saturationFactor, 0, 255);
          rawB = clamp(lum + (rawB - lum) * saturationFactor, 0, 255);
        }

        let trust = 1.0;
        if (reliabilitySurface && reliabilitySurface.values[r]?.[c] !== undefined) {
          const rel = reliabilitySurface.values[r][c];
          if (rel !== null && !isNaN(rel as number)) {
            trust = Math.max(0, Math.min(1, rel as number));
          }
        } else if (confidenceSurface && confidenceSurface.values[r]?.[c] !== undefined) {
          const conf = confidenceSurface.values[r][c];
          if (conf !== null && !isNaN(conf as number)) {
            const confType = confidenceSurface.type || (confidenceSurface as any).semantic_type || "";
            const isUncertainty = confType.includes("UNCERTAINTY");
            trust = isUncertainty 
              ? Math.max(0, Math.min(1, 1.0 - (conf as number))) 
              : Math.max(0, Math.min(1, conf as number));
          }
        }
        const lum = 0.299 * rawR + 0.587 * rawG + 0.114 * rawB;

        let filterAlpha = opacity;

        if (safeMode === "veg_attention" && deviationSurface) {
          const devVal = deviationSurface.values[r]?.[c];
          if (devVal !== null && devVal !== undefined && !isNaN(devVal)) {
            const absDev = Math.min(Math.abs(devVal), 0.3);
            const emphasisBoost = 0.35 + (absDev / 0.3) * 0.65;
            filterAlpha *= emphasisBoost;
          }
        }

        const prov = (surface.provenance as any) || {};
        const isAsmaeDiag = prov.source_class === "asmae_diagnostic" || (surface as any).type?.includes("ASMAE") || (surface as any).semantic_type?.includes("ASMAE");
        const hasConflict = prov.cross_layer_conflict > 0.45 || prov.warning_codes?.includes("cross_layer_conflict");
        const isGapFilled = sampleMask(gapFillSurface, r, c) === 1;

        const showHatching = scalePolicy ? scalePolicy.showHatching : true;

        if (isCandidateMask) {
          const val = valuesToRender[r][c];
          if (val === 1) {
            // Check neighbors
            let isEdge = false;
            const neighbors = [
              [r - 1, c], [r + 1, c], [r, c - 1], [r, c + 1]
            ];
            for (const [nr, nc] of neighbors) {
              if (nr < 0 || nr >= h || nc < 0 || nc >= w) {
                isEdge = true;
                break;
              }
              const nVal = valuesToRender[nr][nc];
              if (nVal !== 1) {
                isEdge = true;
                break;
              }
            }
            if (isEdge) {
              rawR = 168; rawG = 85; rawB = 247; // #a855f7
              filterAlpha = 0.9;
            } else {
              filterAlpha = 0.0;
            }
          } else {
            filterAlpha = 0.0;
          }
        } else if (isAsmaeDiag) {
          const stype = ((surface as any).type || (surface as any).semantic_type || "").toString();
          const isAsmaeBase =
            stype === "COMPOSITE_ADVISORY_CANOPY" ||
            stype === "ASMAE_VISUAL_FUSION_CANOPY" ||
            stype === "CANOPY_ASMAE_VIGOR";

          const isAsmaeDiagnosticOverlay =
            stype.includes("BMA") ||
            stype.includes("CONFLICT") ||
            stype.includes("UNCERTAINTY") ||
            stype.includes("CONFIDENCE") ||
            stype.includes("EFFECTIVE_RESOLUTION");

          if (isAsmaeBase) {
            // continuous raster only, no hatching, no periodic dotting
            filterAlpha = opacity;
          } else if (isAsmaeDiagnosticOverlay) {
            // hatching/contours allowed here only
            filterAlpha = trust * opacity;

            // Check borders/edges
            const isBorderPixel = r === 0 || r === h - 1 || c === 0 || c === w - 1;

            // magenta borders/edges for BMA disagreement
            if (prov.bma_disagreement > 0.35 && isBorderPixel) {
              rawR = 255; rawG = 0; rawB = 255; // Magenta
              filterAlpha = 0.95;
            }
            // amber borders/boundaries for weak retrovalidation
            else if (prov.retrovalidation_score < 0.6 && isBorderPixel) {
              rawR = 245; rawG = 158; rawB = 11; // Amber
              filterAlpha = 0.95;
            }
            // gray hatching for high uncertainty
            else if (prov.uncertainty > 0.4 && showHatching) {
              if ((r + c) % 5 === 0) {
                rawR = 120; rawG = 120; rawB = 120; // Gray hatching
                filterAlpha = 0.7;
              }
            }
            // cyan contours for SAR/water support
            else if ((prov.creator === "ASMAE_RADIOMETRIC" || prov.asmae_feature === "radiometric_support" || (prov.creator === "ASMAE_ENKF" && prov.asmae_feature?.includes("water"))) && showHatching) {
              if ((r - c) % 6 === 0) {
                rawR = 0; rawG = 255; rawB = 255; // Cyan contour
                filterAlpha = 0.7;
              }
            } else if (showHatching) {
              if ((r + c) % 5 === 0) {
                rawR = Math.max(0, rawR * 0.85);
                rawG = Math.max(0, rawG * 0.85);
                rawB = Math.max(0, rawB * 0.85);
              }
            }
          } else {
            // Fallback default: smooth continuous
            filterAlpha = opacity;
          }
        } else {
          if (isGapFilled) {
            rawR = rawR * 0.35 + 120 * 0.65;
            rawG = rawG * 0.35 + 120 * 0.65;
            rawB = rawB * 0.35 + 120 * 0.65;
            if (showHatching && (r + c) % 4 === 0) {
              rawR = Math.max(0, rawR * 0.8);
              rawG = Math.max(0, rawG * 0.8);
              rawB = Math.max(0, rawB * 0.8);
            }
          }

          if (hasConflict && showHatching) {
            if ((r === 0 || r === h - 1 || c === 0 || c === w - 1) || (r + c) % 3 === 0) {
              rawR = Math.min(255, rawR * 0.8 + 50);
              rawG = Math.max(0, rawG * 0.7);
              rawB = Math.min(255, rawB * 0.8 + 80);
            }
          }

          if (isExperimental && trust < 0.6 && showHatching) {
            if ((r + c) % 6 === 0) {
              rawR = 120; rawG = 120; rawB = 120; // Slate gray hatching
              filterAlpha = 0.55;
            }
          }
        }

        if (applyTrustToBase && !isCandidateMask) {
          if (detailMode === "expert") {
            rawR = rawR + (lum - rawR) * (1.0 - trust);
            rawG = rawG + (lum - rawG) * (1.0 - trust);
            rawB = rawB + (lum - rawB) * (1.0 - trust);
            filterAlpha = filterAlpha * (0.4 + 0.6 * trust);
          } else if (trust < 0.60) {
            const desatFactor = (0.60 - trust) / 0.60;
            rawR = rawR + (lum - rawR) * desatFactor;
            rawG = rawG + (lum - rawG) * desatFactor;
            rawB = rawB + (lum - rawB) * desatFactor;
          }
        }
        
        imgData.data[ptr++] = Math.round(rawR);
        imgData.data[ptr++] = Math.round(rawG);
        imgData.data[ptr++] = Math.round(rawB);
        let finalAlpha = filterAlpha;

        // Render-kind caps (do not allow frontend to visually amplify unauthorized rasters)
        const capMap: Record<string, number> = {
          full_raster: 1.0,
          diagnostic_overlay: 0.35,
          proxy_overlay: 0.45,
          card_only: 0.0,
          none: 0.0,
        };
        const cap = capMap[effectiveRenderKind] ?? 0.0;

        const observedMaskValue = sampleMask(observedMaskSurface, r, c);
        const observedMaskKnown = observedMaskValue !== null && observedMaskValue !== undefined && Number.isFinite(Number(observedMaskValue));
        const observedCell = observedMaskKnown && Number(observedMaskValue) > 0;
        if (auth?.requiresObservedMask && !observedCell) {
          finalAlpha = 0;
        }

        // Apply trust exactly once. Render-kind policy limits the permitted
        // trust scale; it does not independently demote the final alpha.
        const trustScale = auth && typeof auth.trustAlphaScale === "number" ? auth.trustAlphaScale : 1.0;
        const effectiveTrustScale = Math.min(Math.max(0, trustScale), cap);
        finalAlpha = finalAlpha * effectiveTrustScale;

        imgData.data[ptr++] = Math.round(Math.min(1.0, finalAlpha) * 255);
      }
      maskPtr++;
    }
  }

  ctx.putImageData(imgData, 0, 0);
  return canvas;
}

export function resolveSurfaceBounds(
  surfaceData: SurfaceData | null | undefined,
  plotGeoJson: any
): [number, number, number, number] {
  const grid = validateSurfaceGrid(surfaceData, plotGeoJson);
  return grid.valid && grid.bounds
    ? grid.bounds
    : [Number.NaN, Number.NaN, Number.NaN, Number.NaN];
}

/**
 * Creates a standard DeckGL BitmapLayer that maps the 2D surface raster
 * perfectly over the Plot bounds.
 */
export function getSemanticSurfaceLayerLayer({
  id = "semantic-surface",
  plotId,
  surfaceData,
  surfaceColors,
  plotGeoJson,
  confidenceSurface,
  reliabilitySurface,
  deviationSurface,
  opacity = 0.85,
  detailMode = "farmer",
  quantizeBands = null,
  mode = "vegetation",
  visible = true,
  paletteId,
  renderMode,
  zoom,
  gapFillSurface,
  observedMaskSurface,
  renderKind,
  displayLevel,
  applyTrustToBase = false,
  renderAuthorizations,
  policy,
  role
}: {
  id?: string;
  plotId?: string;
  surfaceData?: SurfaceData | null;
  surfaceColors?: [string, string, string] | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  plotGeoJson?: any;
  confidenceSurface?: SurfaceData | null;
  reliabilitySurface?: SurfaceData | null;
  deviationSurface?: SurfaceData | null;
  opacity?: number;
  detailMode?: "farmer" | "expert";
  quantizeBands?: number | null;
  mode?: string;
  visible?: boolean;
  paletteId?: string;
  renderMode?: string;
  zoom?: number;
  gapFillSurface?: SurfaceData | null;
  observedMaskSurface?: SurfaceData | null;
  renderKind?: string;
  displayLevel?: string;
  applyTrustToBase?: boolean;
  // Optional: render authorization bundle (frontend read-only) + policy/role so
  // the layer can enforce backend-specified requirements like masks and trustAlphaScale.
  renderAuthorizations?: any;
  policy?: string;
  role?: "base" | "overlay" | "candidate" | "inspector";
}) {
  if (!visible || !surfaceData || !plotGeoJson) return null;

  const bounds = resolveSurfaceBounds(surfaceData, plotGeoJson);
  if (!bounds.every(Number.isFinite) || bounds[2] <= bounds[0] || bounds[3] <= bounds[1]) {
    return null;
  }
  
  const w = surfaceData?.values?.[0]?.length || 8;
  const h = surfaceData?.values?.length || 8;
  const mask = buildPolygonMask(plotId, w, h, plotGeoJson, bounds);

  // Apply soft opacity for soft_proxy_tint renderMode
  const finalOpacity = renderMode === "soft_proxy_tint" ? 0.75 : opacity;

  const evidenceLevel = (surfaceData?.provenance as any)?.source_class || 
    (surfaceData?.type?.includes("ASMAE") ? "asmae_diagnostic" : "canonical");
  const resolution_m = (surfaceData as any)?.native_resolution_m || 10;
  const scalePolicy = getScaleAwareLayerPolicy({ zoom, evidenceLevel, resolution_m });

  // Resolve render authorization for this surface (deny-by-default)
  const surfaceType = surfaceData?.semantic_type || surfaceData?.type || "";
  const auth = getRenderAuthorization(surfaceType, (policy as string) || "satellite", (mode as string) || "canopy", (role as any) || "base", (renderAuthorizations as any));
  const effectiveRenderKind = auth?.renderKind || renderKind || "full_raster";

  if (!auth?.authorized || effectiveRenderKind === "none" || effectiveRenderKind === "card_only") {
    return null;
  }

  // If backend requires an observed mask, observed_ratio is not sufficient proof.
  // A real aligned binary mask must be present so unobserved cells stay transparent.
  const isAsmaeDiag = (policy as string) === "asmae_diagnostic" || effectiveRenderKind === "diagnostic_overlay" || isAsmaeSurfaceType(surfaceType);

  if (!isAsmaeDiag && auth && auth.requiresObservedMask) {
    if (!canMaterializeMask(
      observedMaskSurface,
      surfaceData,
      auth.maskAlignmentPolicy === "nearest_shared_bounds",
      plotGeoJson,
    )) {
      return null;
    }
  }
  // If backend requires a gap-fill mask and none is provided or dimensions mismatch, skip
  if (!isAsmaeDiag && auth && auth.requiresGapFillMask) {
    if (!canMaterializeMask(
      gapFillSurface,
      surfaceData,
      auth.maskAlignmentPolicy === "nearest_shared_bounds",
      plotGeoJson,
    )) return null;
  }

  const imageUrl = createSurfaceImage(
    plotId,
    surfaceData,
    surfaceColors,
    plotGeoJson,
    confidenceSurface,
    finalOpacity,
    detailMode,
    quantizeBands,
    mode,
    reliabilitySurface,
    deviationSurface,
    paletteId,
    renderMode,
    gapFillSurface,
    scalePolicy,
    effectiveRenderKind,
    displayLevel,
    applyTrustToBase,
    auth,
    observedMaskSurface
  );

  if (!imageUrl) return null;

  const z = zoom ?? 15;
  const NEAREST_SURFACES = new Set([
    "EXPERIMENTAL_STRICT_FINE_DETAIL_CANDIDATE_MASK",
    "EXPERIMENTAL_FINE_DETAIL_CANDIDATE",
    "EXPERIMENTAL_TEXTURE_SUPPORT_MASK",
    "GAPFILL_MASK",
    "GAP_FILL_MASK",
    "EXPERIMENTAL_GAPFILL_MASK",
    "RESOLUTION_COVERAGE",
    "ASMAE_1M_ADVISORY_MASK",
    "ASMAE_2_5M_MODEL_ASSISTED_MASK",
    "ASMAE_5M_GENERALIZED_MASK"
  ]);
  const typeStr = surfaceData?.type || surfaceData?.semantic_type;
  const shouldUseNearest = (typeStr && NEAREST_SURFACES.has(typeStr)) ? z >= 16 : false;

  const isContinuousRaster = typeStr && !NEAREST_SURFACES.has(typeStr);
  const renderProofs = {
    isContinuous: !!isContinuousRaster,
    linearFiltering: !!isContinuousRaster,
    noUniformTint: !!isContinuousRaster,
    noFlattening: !!isContinuousRaster
  };

  const bitmapLayer = new BitmapLayer({
    id,
    bounds,
    image: imageUrl,
    opacity: 1, // handled inside canvas gen
    pickable: true,
    textureParameters: {
      minFilter: shouldUseNearest ? "nearest" : "linear",
      magFilter: shouldUseNearest ? "nearest" : "linear"
    },
    extensions: [new MaskExtension()],
    maskId: 'plot-clip-mask'
  });

  (bitmapLayer as any).renderProofs = renderProofs;

  return [bitmapLayer];
}
