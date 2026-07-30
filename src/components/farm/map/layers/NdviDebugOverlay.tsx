"use client";

import { useEffect, useRef } from "react";
import { SurfaceData } from "@/hooks/useLayer10";

interface ViewState {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch?: number;
  bearing?: number;
}

interface NdviDebugOverlayProps {
  surfaceData: SurfaceData | null | undefined;
  plotGeoJson: GeoJSON.Feature<GeoJSON.Geometry> | null | undefined;
  viewState: ViewState;
  containerRef: React.RefObject<HTMLDivElement | null>;
  enabled: boolean;
}

/**
 * Debug overlay that renders the raw NDVI value on each grid cell.
 * Uses a canvas projected onto the map using the same geo→screen transform.
 * Toggle with the `enabled` prop — zero cost when disabled.
 */
export default function NdviDebugOverlay({
  surfaceData,
  plotGeoJson,
  viewState,
  containerRef,
  enabled,
}: NdviDebugOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container || !enabled || !surfaceData?.values || !plotGeoJson) {
      if (canvas) {
        const ctx = canvas.getContext("2d");
        ctx?.clearRect(0, 0, canvas.width, canvas.height);
      }
      return;
    }

    const values = surfaceData.values;
    const gridH = values.length;
    const gridW = values[0]?.length || 0;
    if (gridH === 0 || gridW === 0) return;

    // Bounding box from plot polygon
    const coords =
      plotGeoJson.geometry?.type === "MultiPolygon"
        ? (plotGeoJson.geometry as GeoJSON.MultiPolygon).coordinates[0][0]
        : (plotGeoJson.geometry as GeoJSON.Polygon)?.coordinates?.[0];

    if (!coords || coords.length < 3) return;

    let minLng = Infinity, maxLng = -Infinity, minLat = Infinity, maxLat = -Infinity;
    for (const c of coords) {
      if (c[0] < minLng) minLng = c[0];
      if (c[0] > maxLng) maxLng = c[0];
      if (c[1] < minLat) minLat = c[1];
      if (c[1] > maxLat) maxLat = c[1];
    }

    const latStep = (maxLat - minLat) / gridH;
    const lngStep = (maxLng - minLng) / gridW;

    // Mercator geo → screen pixel projection
    const W = container.clientWidth;
    const H = container.clientHeight;
    const zoom = viewState.zoom;
    const scale = Math.pow(2, zoom);
    const TILE_SIZE = 512;

    const lngToX = (lng: number) =>
      W / 2 + (lng - viewState.longitude) * (TILE_SIZE * scale) / 360;

    const latToY = (lat: number) => {
      const sinLat = Math.sin((lat * Math.PI) / 180);
      const worldY = (0.5 - Math.log((1 + sinLat) / (1 - sinLat)) / (4 * Math.PI)) * TILE_SIZE * scale;
      const centerSinLat = Math.sin((viewState.latitude * Math.PI) / 180);
      const centerWorldY = (0.5 - Math.log((1 + centerSinLat) / (1 - centerSinLat)) / (4 * Math.PI)) * TILE_SIZE * scale;
      return H / 2 + (worldY - centerWorldY);
    };

    // Resize canvas to container
    canvas.width = W;
    canvas.height = H;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, W, H);

    // Compute field stats for color coding
    const flat: number[] = [];
    for (let r = 0; r < gridH; r++)
      for (let c = 0; c < gridW; c++)
        if (values[r][c] != null) flat.push(values[r][c] as number);
    const fieldMean = flat.length > 0 ? flat.reduce((a, b) => a + b, 0) / flat.length : 0;
    const fieldMin = flat.length > 0 ? Math.min(...flat) : 0;
    const fieldMax = flat.length > 0 ? Math.max(...flat) : 1;

    // Compute cell screen size (to decide font size)
    const cellW = Math.abs(lngToX(minLng + lngStep) - lngToX(minLng));
    const cellH = Math.abs(latToY(maxLat - latStep) - latToY(maxLat));

    if (cellW < 12 || cellH < 8) return; // Too small to display text

    const fontSize = Math.min(Math.floor(cellH * 0.35), Math.floor(cellW * 0.25), 13);
    if (fontSize < 7) return;

    ctx.font = `bold ${fontSize}px monospace`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    for (let r = 0; r < gridH; r++) {
      for (let c = 0; c < gridW; c++) {
        const val = values[r][c];
        if (val == null) continue;

        const cellCenterLng = minLng + (c + 0.5) * lngStep;
        const cellCenterLat = maxLat - (r + 0.5) * latStep;

        const screenX = lngToX(cellCenterLng);
        const screenY = latToY(cellCenterLat);

        // Skip off-screen cells
        if (screenX < -10 || screenX > W + 10 || screenY < -10 || screenY > H + 10) continue;

        // Color code: red=low, yellow=mean, green=high
        const t = fieldMax > fieldMin ? (val as number - fieldMin) / (fieldMax - fieldMin) : 0.5;
        let r_col: number, g_col: number, b_col: number;
        if (t < 0.5) {
          r_col = 255;
          g_col = Math.round(t * 2 * 255);
          b_col = 0;
        } else {
          r_col = Math.round((1 - t) * 2 * 255);
          g_col = 255;
          b_col = 0;
        }

        // Draw semi-transparent cell background
        ctx.fillStyle = `rgba(0,0,0,0.45)`;
        const pw = cellW * 0.92;
        const ph = cellH * 0.92;
        ctx.fillRect(screenX - pw / 2, screenY - ph / 2, pw, ph);

        // Draw NDVI value
        const label = (val as number).toFixed(3);
        ctx.fillStyle = `rgb(${r_col},${g_col},${b_col})`;
        ctx.fillText(label, screenX, screenY - fontSize * 0.15);

        // Draw row,col index below
        if (fontSize >= 9) {
          ctx.font = `${Math.max(fontSize - 2, 6)}px monospace`;
          ctx.fillStyle = "rgba(200,200,200,0.7)";
          ctx.fillText(`r${r}c${c}`, screenX, screenY + fontSize * 0.6);
          ctx.font = `bold ${fontSize}px monospace`;
        }

        // Mark cells at field mean with a dot
        if (Math.abs((val as number) - fieldMean) < 0.005) {
          ctx.strokeStyle = "rgba(255,255,255,0.6)";
          ctx.lineWidth = 1;
          ctx.strokeRect(screenX - pw / 2, screenY - ph / 2, pw, ph);
        }
      }
    }

    // Draw legend — top-right corner (below nav bar, above map controls)
    const legendX = W - 195, legendY = 80;
    ctx.fillStyle = "rgba(0,0,0,0.75)";
    ctx.fillRect(legendX, legendY, 185, 76);
    ctx.fillStyle = "#facc15";
    ctx.font = "bold 11px monospace";
    ctx.textAlign = "left";
    ctx.fillText(`🔬 NDVI DEBUG (${gridH}×${gridW})`, legendX + 6, legendY + 15);
    ctx.fillStyle = "#aaa";
    ctx.font = "10px monospace";
    ctx.fillText(`Min: ${fieldMin.toFixed(3)}  Max: ${fieldMax.toFixed(3)}`, legendX + 6, legendY + 31);
    ctx.fillText(`Mean: ${fieldMean.toFixed(3)}`, legendX + 6, legendY + 45);
    ctx.fillText(`Surface: ${surfaceData.type}`, legendX + 6, legendY + 59);
    ctx.fillText(`Cells: ${flat.length} valid`, legendX + 6, legendY + 68);
  }, [surfaceData, plotGeoJson, viewState, containerRef, enabled]);

  if (!enabled) return null;

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 pointer-events-none"
      style={{ zIndex: 999, mixBlendMode: "normal" }}
    />
  );
}
