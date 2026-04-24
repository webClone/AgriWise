"use client";

import { BitmapLayer } from "@deck.gl/layers";
import { SurfaceData } from "@/hooks/useLayer10";
import { buildPolygonMask } from "../utils/buildPolygonMask";

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
  detailMode: "farmer" | "expert" = "farmer",
  quantizeBands: number | null = null,
  layerMode: string = "vegetation",
  /** DATA_RELIABILITY surface — priority trust source (WS6) */
  reliabilitySurface: SurfaceData | null | undefined = null,
  /** NDVI_DEVIATION surface — used for hybrid vegetation emphasis */
  deviationSurface: SurfaceData | null | undefined = null
): ImageData | null {
  if (!surface || !plotGeoJson) return null;
  const h = surface.values.length;
  if (h === 0) return null;
  const w = surface.values[0].length;
  if (w === 0) return null;

  // 1. We don't need a canvas, we can create ImageData directly
  const imgData = new ImageData(w, h);
  
  // 2. Parse Hex colors
  const hexToRgb = (hex: string) => {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? {
      r: parseInt(result[1], 16),
      g: parseInt(result[2], 16),
      b: parseInt(result[3], 16)
    } : { r: 0, g: 0, b: 0 };
  };
  
  // ColorBrewer-derived ramps — colorblind-safe, semantically distinct from satellite
  const MODE_RAMPS: Record<string, {low: number[], mid: number[], high: number[]}> = {
    vegetation:     { low: [166, 97, 26],  mid: [245, 235, 150], high: [1, 133, 113]  }, // Richer contrast: warm brown → bright straw → vivid teal-green
    water_stress:   { low: [33, 102, 172], mid: [253, 212, 158], high: [178, 24, 43]  }, // Blue→warm→red (diverging)
    nutrient_risk:  { low: [26, 152, 80],  mid: [254, 224, 139], high: [215, 48, 39]  }, // Green→yellow→red
    composite_risk: { low: [255, 255, 191], mid: [252, 141, 89], high: [215, 48, 39]  }, // Yellow→orange→red
    uncertainty:    { low: [247, 247, 247], mid: [150, 150, 150], high: [37, 37, 37]  }, // Neutral gray ramp
  };

  const safeMode = layerMode && MODE_RAMPS[layerMode.toLowerCase()] ? layerMode.toLowerCase() : "vegetation";
  const overrideRamp = MODE_RAMPS[safeMode];

  const cLow = overrideRamp ? { r: overrideRamp.low[0], g: overrideRamp.low[1], b: overrideRamp.low[2] } : hexToRgb(colors?.[0] || "#000000");
  const cMid = overrideRamp ? { r: overrideRamp.mid[0], g: overrideRamp.mid[1], b: overrideRamp.mid[2] } : hexToRgb(colors?.[1] || "#000000");
  const cHigh = overrideRamp ? { r: overrideRamp.high[0], g: overrideRamp.high[1], b: overrideRamp.high[2] } : hexToRgb(colors?.[2] || "#000000");

  // Use the extracted and cached polygon mask
  const mask = buildPolygonMask(plotId, w, h, plotGeoJson);

  // 2b. Compute Render Range mapping (OneSoil-style per-field contrast stretch)
  let [minV, maxV] = surface.render_range || [0, 1];
  
  // Gather valid values strictly within the plot boundary to compute local percentiles
  const validVals: number[] = [];
  let statPtr = 0;
  for (let r = 0; r < h; r++) {
    for (let c = 0; c < w; c++) {
      const val = surface.values[r][c];
      if (val !== null && val !== undefined && !isNaN(val) && (!mask || mask.data[statPtr] === 1)) {
        validVals.push(val);
      }
      statPtr++;
    }
  }

  // Apply P02 - P98 stretch to maximize intra-field contrast and ignore outliers (Farmer)
  // Or P01 - P99 stretch for highest detail (Expert)
  if (validVals.length > 10) {
    validVals.sort((a, b) => a - b);
    const bottomSlice = detailMode === "expert" ? 0.01 : 0.02;
    const topSlice = detailMode === "expert" ? 0.99 : 0.98;
    const p02 = validVals[Math.floor(validVals.length * bottomSlice)];
    const p98 = validVals[Math.floor(validVals.length * topSlice)];
    // Only override if the local contrast is meaningful
    if (p98 > p02) {
      minV = p02;
      maxV = p98;
    }
  }

  const range = maxV - minV === 0 ? 1 : maxV - minV;
  const clamp = (num: number, min: number, max: number) => Math.min(Math.max(num,min),max);

  // 3. Write pixels
  let ptr = 0;
  let maskPtr = 0;
  for (let r = 0; r < h; r++) {
    for (let c = 0; c < w; c++) {
      const val = surface.values[r][c];
      const isOutsideField = mask && mask.data[maskPtr] === 0;
      const isNoData = val === null || val === undefined || isNaN(val);

      if (isOutsideField) {
        // Outside field polygon → fully transparent
        imgData.data[ptr++] = 0;
        imgData.data[ptr++] = 0;
        imgData.data[ptr++] = 0;
        imgData.data[ptr++] = 0;
      } else if (isNoData) {
        // Inside field but no data → gray diagonal hatch pattern
        // Creates a 4px repeating diagonal stripe so "no data" is visually distinct
        const hatchPhase = (r + c) % 4;
        const isStripe = hatchPhase === 0 || hatchPhase === 1;
        imgData.data[ptr++] = isStripe ? 80 : 55;  // R
        imgData.data[ptr++] = isStripe ? 80 : 55;  // G
        imgData.data[ptr++] = isStripe ? 80 : 55;  // B
        imgData.data[ptr++] = Math.round(opacity * 200); // Visible but not dominant
      } else {
        // Normalize value across the dynamic 3-stop ramp range exactly as prescribed
        let t = clamp((val - minV) / range, 0, 1);
        
        // Quantize into crisp visual bands if enforced by policy
        const useQuantization = typeof quantizeBands === "number" && quantizeBands > 1;
        if (useQuantization) {
          const bands = quantizeBands;
          t = Math.min(Math.floor(t * bands), bands - 1) / (bands - 1);
        }
        
        // Base Color Generation
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

        // Trust scoring — WS6: DATA_RELIABILITY has priority over inverted sigma
        let trust = 1.0;
        // Priority 1: DATA_RELIABILITY surface (0=unreliable, 1=fully reliable)
        if (reliabilitySurface && reliabilitySurface.values[r]?.[c] !== undefined) {
          const rel = reliabilitySurface.values[r][c];
          if (rel !== null && !isNaN(rel as number)) {
            trust = Math.max(0, Math.min(1, rel as number));
          }
        } else if (confidenceSurface && confidenceSurface.values[r]?.[c] !== undefined) {
          // Fallback: inverted UNCERTAINTY_SIGMA (higher sigma = less trust)
          const conf = confidenceSurface.values[r][c];
          if (conf !== null && !isNaN(conf as number)) {
            trust = Math.max(0, Math.min(1, 1.0 - (conf as number)));
          }
        }
        // Simple luminance approx
        const lum = 0.299 * rawR + 0.587 * rawG + 0.114 * rawB;

        // V2.3 Cinematic Fusion
        // By modulating the alpha logarithmically against luminance, dark terrain spots
        // punch through and bright pixel overlays feel like organic light instead of a wash.
        const lumNorm = Math.min(lum / 255, 1.0);
        // We let the lowest values drop their opacity more, while preserving high-luminance vibrancy.
        // Reduced attenuation strength (0.50, 0.9) to keep overlays visible on pale backgrounds
        let organicAlpha = opacity * Math.pow(lumNorm + 0.50, 0.9) * (0.60 + 0.40 * trust);

        // ── Hybrid Vegetation Attention: emphasis from |NDVI_DEVIATION| ──
        // Only in veg_attention mode. Uniform areas fade; anomalies pop.
        if (safeMode === "veg_attention" && deviationSurface) {
          const devVal = deviationSurface.values[r]?.[c];
          if (devVal !== null && devVal !== undefined && !isNaN(devVal)) {
            // |deviation| typically 0–0.3 for most fields.
            // Map to emphasis of [0.35, 1.0]: uniform fades hard, anomalies pop.
            const absDev = Math.min(Math.abs(devVal), 0.3);
            const emphasisBoost = 0.35 + (absDev / 0.3) * 0.65;
            organicAlpha *= emphasisBoost;
          }
        }
        
        imgData.data[ptr++] = Math.round(rawR);
        imgData.data[ptr++] = Math.round(rawG);
        imgData.data[ptr++] = Math.round(rawB);
        imgData.data[ptr++] = Math.round(Math.min(1.0, organicAlpha) * 255);
      }
      maskPtr++;
    }
  }
  return imgData;
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
  visible = true
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
}) {
  if (!visible || !surfaceData || !plotGeoJson) return null;

  // DeckGL requires bounds as [minLng, minLat, maxLng, maxLat] for BitmapLayer
  // Extract BBox from GeoJSON
  let minLng = Infinity, maxLng = -Infinity, minLat = Infinity, maxLat = -Infinity;
  const coords = plotGeoJson.geometry.type === 'MultiPolygon' 
    ? plotGeoJson.geometry.coordinates[0][0] 
    : plotGeoJson.geometry.coordinates[0];
  
  coords.forEach((c: number[]) => {
    if (c[0] < minLng) minLng = c[0];
    if (c[0] > maxLng) maxLng = c[0];
    if (c[1] < minLat) minLat = c[1];
    if (c[1] > maxLat) maxLat = c[1];
  });

  const bounds: [number, number, number, number] = [minLng, minLat, maxLng, maxLat];
  const imageUrl = createSurfaceImage(plotId, surfaceData, surfaceColors, plotGeoJson, confidenceSurface, opacity, detailMode, quantizeBands, mode, reliabilitySurface, deviationSurface);

  if (!imageUrl) return null;

  return new BitmapLayer({
    id,
    bounds,
    image: imageUrl,
    opacity: 1, // handled inside canvas gen
    pickable: true,
    // DeckGL uses linear resampling by default when spanning a bitmap across coordinates.
    textureParameters: {
      minFilter: "linear",
      magFilter: "linear"
    }
  });
}
