import * as turf from "@turf/turf";
import type L from "leaflet";

export interface DetectedPlot {
  id: string;
  geoJson: GeoJSON.Feature<GeoJSON.Polygon>;
  areaHa: number;
  confidence: number;
  name?: string;
  cropType?: string;
  source: "ai-vision-wand" | "ai-vision-scan" | "fallback-radial";
}

/**
 * Magic Wand — click-based single-field delineation via server-side Gemini Vision AI.
 * 
 * Sends the map center, zoom, and clicked coordinate to the server which:
 * 1. Fetches a 3×3 grid of satellite tiles (768×768 composite)
 * 2. Sends to Gemini Vision for field boundary segmentation
 * 3. Returns the polygon in GeoJSON
 */
export async function detectFieldAtPoint(
  map: L.Map,
  latlng: L.LatLng
): Promise<DetectedPlot | null> {
  const center = map.getCenter();
  const zoom = map.getZoom();

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 45000); // 45s timeout

  try {
    const res = await fetch("/api/map/detect-boundaries", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        centerLat: center.lat,
        centerLng: center.lng,
        zoom,
        clickLat: latlng.lat,
        clickLng: latlng.lng,
        mode: "wand",
      }),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      const errData = await res.json().catch(() => null);
      console.error(
        "[Magic Wand] API error:",
        res.status,
        errData?.error || res.statusText
      );
      return null;
    }

    const data = await res.json();

    if (data.success && data.plot?.geoJson) {
      return data.plot as DetectedPlot;
    }

    if (data.error) {
      console.warn("[Magic Wand] Detection failed:", data.error);
    }

    return null;
  } catch (err: any) {
    clearTimeout(timeoutId);

    if (err.name === "AbortError") {
      console.warn("[Magic Wand] Request timed out after 45s");
    } else {
      console.error("[Magic Wand] Network error:", err);
    }

    return null;
  }
}

/**
 * Auto-Scan — multi-plot viewport detection via server-side Gemini Vision AI.
 * 
 * Detects all visible agricultural parcels in the current map viewport.
 */
export async function scanViewportPlots(map: L.Map): Promise<DetectedPlot[]> {
  const center = map.getCenter();
  const zoom = map.getZoom();

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 60000); // 60s timeout

  try {
    const res = await fetch("/api/map/detect-boundaries", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        centerLat: center.lat,
        centerLng: center.lng,
        zoom,
        mode: "scan",
      }),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      const errData = await res.json().catch(() => null);
      console.error(
        "[Auto-Scan] API error:",
        res.status,
        errData?.error || res.statusText
      );
      return [];
    }

    const data = await res.json();

    if (data.success && Array.isArray(data.plots) && data.plots.length > 0) {
      console.log(`[Auto-Scan] Detected ${data.plots.length} plot(s)`);
      return data.plots as DetectedPlot[];
    }

    if (data.error) {
      console.warn("[Auto-Scan] Detection failed:", data.error);
    }

    return [];
  } catch (err: any) {
    clearTimeout(timeoutId);

    if (err.name === "AbortError") {
      console.warn("[Auto-Scan] Request timed out after 60s");
    } else {
      console.error("[Auto-Scan] Network error:", err);
    }

    return [];
  }
}
