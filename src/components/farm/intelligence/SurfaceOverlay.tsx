"use client";

import { useEffect, useState } from "react";
import { ImageOverlay } from "react-leaflet";
import type { SurfaceData } from "@/hooks/useLayer10";
import L from "leaflet";

interface SurfaceOverlayProps {
  surface: SurfaceData;
  confidenceSurface?: SurfaceData | null;
  gridHeight: number;
  gridWidth: number;
  bounds: { north: number; south: number; east: number; west: number };
  colors: [string, string, string]; // [low, mid, high]
  opacity?: number;
  clipPolygon?: [number, number][]; // normalized 0-1 polygon for clipping
}

// ============================================================================
// COLOR INTERPOLATION
// ============================================================================

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}

function interpolateRgb(t: number, colors: [string, string, string]): [number, number, number, number] {
  const [low, mid, high] = colors.map(hexToRgb) as [[number, number, number], [number, number, number], [number, number, number]];
  let r: number, g: number, b: number;

  const clamped = Math.max(0, Math.min(1, t));

  if (clamped <= 0.5) {
    const f = clamped * 2;
    r = low[0] + f * (mid[0] - low[0]);
    g = low[1] + f * (mid[1] - low[1]);
    b = low[2] + f * (mid[2] - low[2]);
  } else {
    const f = (clamped - 0.5) * 2;
    r = mid[0] + f * (high[0] - mid[0]);
    g = mid[1] + f * (high[1] - mid[1]);
    b = mid[2] + f * (high[2] - mid[2]);
  }
  return [Math.round(r), Math.round(g), Math.round(b), 255];
}

// ============================================================================
// BILINEAR INTERPOLATION (smooth upsampling)
// ============================================================================

function bilinearSample(
  grid: (number | null)[][],
  fy: number, // fractional row (0 to H-1)
  fx: number, // fractional col (0 to W-1)
  H: number,
  W: number,
  fallback: number
): number {
  const y0 = Math.floor(fy);
  const x0 = Math.floor(fx);
  const y1 = Math.min(y0 + 1, H - 1);
  const x1 = Math.min(x0 + 1, W - 1);

  const dy = fy - y0;
  const dx = fx - x0;

  const v00 = grid[y0]?.[x0] ?? fallback;
  const v10 = grid[y1]?.[x0] ?? fallback;
  const v01 = grid[y0]?.[x1] ?? fallback;
  const v11 = grid[y1]?.[x1] ?? fallback;

  return (
    v00 * (1 - dx) * (1 - dy) +
    v01 * dx * (1 - dy) +
    v10 * (1 - dx) * dy +
    v11 * dx * dy
  );
}

// ============================================================================
// EDGE-AWARE SMOOTHING (Guided filter approximation)
// ============================================================================

function edgeAwareSmooth(
  data: Float32Array,
  w: number,
  h: number,
  radius: number
): Float32Array {
  const out = new Float32Array(data.length);
  const r = radius;

  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const center = data[y * w + x];
      let sum = 0;
      let weight = 0;

      for (let dy = -r; dy <= r; dy++) {
        for (let dx = -r; dx <= r; dx++) {
          const ny = y + dy;
          const nx = x + dx;
          if (ny < 0 || ny >= h || nx < 0 || nx >= w) continue;

          const neighbor = data[ny * w + nx];
          const diff = Math.abs(neighbor - center);
          // Edge-aware weight: preserve edges where values differ significantly
          const spatial = Math.exp(-(dx * dx + dy * dy) / (2 * r * r));
          const range = Math.exp(-(diff * diff) / 0.02); // preserve edges
          const w2 = spatial * range;

          sum += neighbor * w2;
          weight += w2;
        }
      }
      out[y * w + x] = weight > 0 ? sum / weight : center;
    }
  }
  return out;
}

// ============================================================================
// CONFIDENCE CROSSHATCH PATTERN
// ============================================================================

function drawConfidencePattern(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  size: number,
  confidence: number
) {
  if (confidence > 0.7) return; // High confidence = no pattern
  
  ctx.save();
  const opacity = (1 - confidence) * 0.35; // Lower confidence = more visible pattern
  ctx.strokeStyle = `rgba(255, 255, 255, ${opacity})`;
  ctx.lineWidth = 0.5;
  
  if (confidence < 0.3) {
    // Very low confidence: crosshatch
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + size, y + size);
    ctx.moveTo(x + size, y);
    ctx.lineTo(x, y + size);
    ctx.stroke();
  } else {
    // Medium confidence: single diagonal
    ctx.beginPath();
    ctx.moveTo(x, y + size);
    ctx.lineTo(x + size, y);
    ctx.stroke();
  }
  ctx.restore();
}

// ============================================================================
// ZONE CONTOUR RENDERING
// ============================================================================

function drawZoneContours(
  ctx: CanvasRenderingContext2D,
  values: Float32Array,
  w: number,
  h: number,
  canvasW: number,
  canvasH: number,
  thresholds: number[]
) {
  const cellW = canvasW / w;
  const cellH = canvasH / h;
  
  ctx.save();
  
  for (const threshold of thresholds) {
    ctx.strokeStyle = "rgba(255, 255, 255, 0.4)";
    ctx.lineWidth = 1.2;
    ctx.setLineDash([4, 3]);
    ctx.beginPath();
    
    // Simple marching squares for contour at threshold
    for (let y = 0; y < h - 1; y++) {
      for (let x = 0; x < w - 1; x++) {
        const v00 = values[y * w + x];
        const v10 = values[(y + 1) * w + x];
        const v01 = values[y * w + (x + 1)];
        const v11 = values[(y + 1) * w + (x + 1)];
        
        const b00 = v00 >= threshold ? 1 : 0;
        const b10 = v10 >= threshold ? 1 : 0;
        const b01 = v01 >= threshold ? 1 : 0;
        const b11 = v11 >= threshold ? 1 : 0;
        
        const idx = b00 | (b01 << 1) | (b10 << 2) | (b11 << 3);
        if (idx === 0 || idx === 15) continue; // All same side
        
        const cx = x * cellW;
        const cy = y * cellH;
        
        // Interpolate edge crossings
        const lerp = (a: number, b: number) => {
          const d = b - a;
          return d === 0 ? 0.5 : (threshold - a) / d;
        };
        
        const top = lerp(v00, v01) * cellW + cx;
        const bottom = lerp(v10, v11) * cellW + cx;
        const left = lerp(v00, v10) * cellH + cy;
        const right = lerp(v01, v11) * cellH + cy;
        
        // Draw contour segments based on marching squares case
        if ((idx & 0b0011) === 0b0001 || (idx & 0b0011) === 0b0010) {
          ctx.moveTo(top, cy);
          ctx.lineTo(cx, left);
        }
        if ((idx & 0b0110) === 0b0010 || (idx & 0b0110) === 0b0100) {
          ctx.moveTo(cx + cellW, right);
          ctx.lineTo(top, cy);
        }
        if ((idx & 0b1100) === 0b0100 || (idx & 0b1100) === 0b1000) {
          ctx.moveTo(cx, left);
          ctx.lineTo(bottom, cy + cellH);
        }
        if ((idx & 0b1001) === 0b1000 || (idx & 0b1001) === 0b0001) {
          ctx.moveTo(bottom, cy + cellH);
          ctx.lineTo(cx + cellW, right);
        }
      }
    }
    ctx.stroke();
  }
  
  ctx.restore();
}

// ============================================================================
// CANVAS RENDERER — the core of the visual upgrade
// ============================================================================

function renderSurfaceToCanvas(
  surface: SurfaceData,
  confidenceSurface: SurfaceData | null | undefined,
  gridH: number,
  gridW: number,
  colors: [string, string, string],
  baseOpacity: number,
  clipPolygon?: [number, number][]
): string | null {
  if (!surface?.values?.length) return null;

  // Upsampling factor: 8x8 → 64x64
  const UPSAMPLE = 8;
  const canvasW = gridW * UPSAMPLE;
  const canvasH = gridH * UPSAMPLE;

  // Find value range
  let min = Infinity, max = -Infinity;
  for (const row of surface.values) {
    for (const v of row) {
      if (v !== null && v !== undefined) {
        if (v < min) min = v;
        if (v > max) max = v;
      }
    }
  }
  if (min === Infinity) return null;
  const range = max - min || 1;
  const mean = (min + max) / 2;

  // Step 1: Bilinear upsample to smooth grid
  const upsampled = new Float32Array(canvasW * canvasH);
  for (let y = 0; y < canvasH; y++) {
    for (let x = 0; x < canvasW; x++) {
      const fy = (y / canvasH) * (gridH - 1);
      const fx = (x / canvasW) * (gridW - 1);
      upsampled[y * canvasW + x] = bilinearSample(surface.values, fy, fx, gridH, gridW, mean);
    }
  }

  // Step 2: Edge-aware smoothing (bilateral filter approximation)
  const smoothed = edgeAwareSmooth(upsampled, canvasW, canvasH, 2);

  // Step 3: Compute confidence grid (upsampled)
  let confidenceGrid: Float32Array | null = null;
  if (confidenceSurface?.values) {
    confidenceGrid = new Float32Array(canvasW * canvasH);
    for (let y = 0; y < canvasH; y++) {
      for (let x = 0; x < canvasW; x++) {
        const fy = (y / canvasH) * (gridH - 1);
        const fx = (x / canvasW) * (gridW - 1);
        confidenceGrid[y * canvasW + x] = bilinearSample(confidenceSurface.values, fy, fx, gridH, gridW, 0.5);
      }
    }
  }

  // Step 4: Render pixel data to a temp canvas first
  const tempCanvas = document.createElement("canvas");
  tempCanvas.width = canvasW;
  tempCanvas.height = canvasH;
  const tempCtx = tempCanvas.getContext("2d");
  if (!tempCtx) return null;

  const imageData = tempCtx.createImageData(canvasW, canvasH);
  const data = imageData.data;

  for (let y = 0; y < canvasH; y++) {
    for (let x = 0; x < canvasW; x++) {
      const idx = (y * canvasW + x) * 4;
      const val = smoothed[y * canvasW + x];
      const t = (val - min) / range;
      const [r, g, b] = interpolateRgb(t, colors);

      // Confidence-modulated opacity
      let alpha = baseOpacity * 255;
      if (confidenceGrid) {
        const conf = confidenceGrid[y * canvasW + x];
        alpha *= (0.4 + 0.6 * Math.max(0, Math.min(1, conf)));
      }

      data[idx]     = r;
      data[idx + 1] = g;
      data[idx + 2] = b;
      data[idx + 3] = Math.round(alpha);
    }
  }
  tempCtx.putImageData(imageData, 0, 0);

  // Step 5: Confidence crosshatch on temp canvas
  if (confidenceGrid) {
    const patchSize = UPSAMPLE;
    for (let gy = 0; gy < gridH; gy++) {
      for (let gx = 0; gx < gridW; gx++) {
        const confVal = confidenceGrid[gy * UPSAMPLE * canvasW + gx * UPSAMPLE] || 0.5;
        if (confVal < 0.7) {
          drawConfidencePattern(tempCtx, gx * patchSize, gy * patchSize, patchSize, confVal);
        }
      }
    }
  }

  // Step 6: Contour lines on temp canvas
  const p25 = min + range * 0.25;
  const p50 = min + range * 0.5;
  const p75 = min + range * 0.75;
  drawZoneContours(tempCtx, smoothed, canvasW, canvasH, canvasW, canvasH, [p25, p50, p75]);

  // Step 7: Final canvas with polygon clipping
  const canvas = document.createElement("canvas");
  canvas.width = canvasW;
  canvas.height = canvasH;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;

  // Apply polygon clip mask if available
  if (clipPolygon && clipPolygon.length > 2) {
    ctx.beginPath();
    ctx.moveTo(clipPolygon[0][0] * canvasW, clipPolygon[0][1] * canvasH);
    for (let i = 1; i < clipPolygon.length; i++) {
      ctx.lineTo(clipPolygon[i][0] * canvasW, clipPolygon[i][1] * canvasH);
    }
    ctx.closePath();
    ctx.clip();
  }

  // Draw the rendered surface (clipped to polygon)
  ctx.drawImage(tempCanvas, 0, 0);

  // Step 8: Subtle vignette within the clip
  const gradient = ctx.createRadialGradient(
    canvasW / 2, canvasH / 2, Math.min(canvasW, canvasH) * 0.25,
    canvasW / 2, canvasH / 2, Math.min(canvasW, canvasH) * 0.55
  );
  gradient.addColorStop(0, "rgba(0,0,0,0)");
  gradient.addColorStop(1, "rgba(0,0,0,0.12)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, canvasW, canvasH);

  return canvas.toDataURL("image/png");
}

// ============================================================================
// REACT COMPONENT
// ============================================================================

export default function SurfaceOverlay({
  surface,
  confidenceSurface,
  gridHeight,
  gridWidth,
  bounds,
  colors,
  opacity = 0.65,
  clipPolygon,
}: SurfaceOverlayProps) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);

  // Render surface to canvas on data change
  useEffect(() => {
    const url = renderSurfaceToCanvas(
      surface,
      confidenceSurface,
      gridHeight,
      gridWidth,
      colors,
      opacity,
      clipPolygon
    );
    // eslint-disable-next-line
    setImageUrl(url);
  }, [surface, confidenceSurface, gridHeight, gridWidth, colors, opacity, clipPolygon]);

  if (!imageUrl) return null;

  const leafletBounds: L.LatLngBoundsExpression = [
    [bounds.south, bounds.west],
    [bounds.north, bounds.east],
  ];

  return (
    <ImageOverlay
      url={imageUrl}
      bounds={leafletBounds}
      opacity={1}
      className="surface-overlay-image"
    />
  );
}
