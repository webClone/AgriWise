import { NextRequest, NextResponse } from "next/server";
import { GoogleGenerativeAI } from "@google/generative-ai";
import sharp from "sharp";
import * as turf from "@turf/turf";

// Allow up to 120s for satellite fetch + Gemini Vision analysis
export const maxDuration = 120;

const GEMINI_API_KEY =
  process.env.GEMINI_API_KEY || "AIzaSyCOMBAdFlQaCz39S3ues1nnX58j5sxI5eI";

/**
 * Precision agricultural boundary-detection API route.
 * 
 * Workflow:
 * 1. Fetch a 3×3 grid of Esri satellite tiles centered on the coordinate → stitch into 768×768 composite
 * 2. Send to Gemini Vision AI (with automatic model fallback: 3.5-flash-lite → 3-flash-preview → 3.7-flash)
 * 3. Parse AI response JSON with multi-layered extraction
 * 4. Map normalized pixel coordinates back to geographic WGS84 GeoJSON
 * 5. Validate geometry and calculate area with Turf.js
 */

// ─── Tile Math ──────────────────────────────────────────────────────────

function latLngToTile(lat: number, lng: number, zoom: number) {
  const x = Math.floor(((lng + 180) / 360) * Math.pow(2, zoom));
  const y = Math.floor(
    ((1 -
      Math.log(
        Math.tan((lat * Math.PI) / 180) + 1 / Math.cos((lat * Math.PI) / 180)
      ) /
        Math.PI) /
      2) *
      Math.pow(2, zoom)
  );
  return { x, y, z: zoom };
}

function tileToBounds(x: number, y: number, z: number) {
  const n = Math.pow(2, z);
  const west = (x / n) * 360 - 180;
  const east = ((x + 1) / n) * 360 - 180;
  const northRad = Math.atan(Math.sinh(Math.PI * (1 - (2 * y) / n)));
  const southRad = Math.atan(Math.sinh(Math.PI * (1 - (2 * (y + 1)) / n)));
  const north = (northRad * 180) / Math.PI;
  const south = (southRad * 180) / Math.PI;
  return { north, south, east, west };
}

// ─── Satellite Tile Fetching & 3x3 Stitching ───────────────────────────

const TILE_SIZE = 256;
const GRID_SIZE = 3; // 3×3 grid = 768×768 px composite (point always centered)
const COMPOSITE_PX = TILE_SIZE * GRID_SIZE; // 768

async function fetchTile(z: number, y: number, x: number): Promise<Buffer | null> {
  const url = `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${z}/${y}/${x}`;
  try {
    const res = await fetch(url, {
      headers: { "User-Agent": "AgriWise/1.0" },
      signal: AbortSignal.timeout(6000),
    });
    if (!res.ok) return null;
    const ab = await res.arrayBuffer();
    return Buffer.from(ab);
  } catch {
    return null;
  }
}

async function getSatelliteComposite(
  centerLat: number,
  centerLng: number,
  zoom = 16
): Promise<{
  buffer: Buffer;
  bbox: { north: number; south: number; east: number; west: number };
  widthPx: number;
  heightPx: number;
} | null> {
  const clampedZoom = Math.min(18, Math.max(14, Math.round(zoom)));
  const centerTile = latLngToTile(centerLat, centerLng, clampedZoom);

  const compositeList: Array<{ input: Buffer; top: number; left: number }> = [];
  const fetches: Promise<void>[] = [];

  for (let dy = -1; dy <= 1; dy++) {
    for (let dx = -1; dx <= 1; dx++) {
      const y = centerTile.y + dy;
      const x = centerTile.x + dx;
      const p = fetchTile(clampedZoom, y, x).then((buf) => {
        if (buf) {
          compositeList.push({
            input: buf,
            top: (dy + 1) * TILE_SIZE,
            left: (dx + 1) * TILE_SIZE,
          });
        }
      });
      fetches.push(p);
    }
  }

  await Promise.all(fetches);

  if (compositeList.length < 5) {
    console.warn(`[Boundary Detection] Only ${compositeList.length}/9 tiles fetched`);
    if (compositeList.length === 0) return null;
  }

  try {
    const stitched = await sharp({
      create: {
        width: COMPOSITE_PX,
        height: COMPOSITE_PX,
        channels: 3,
        background: { r: 30, g: 35, b: 40 },
      },
    })
      .composite(compositeList)
      .jpeg({ quality: 85 })
      .toBuffer();

    const topLeft = tileToBounds(centerTile.x - 1, centerTile.y - 1, clampedZoom);
    const bottomRight = tileToBounds(centerTile.x + 1, centerTile.y + 1, clampedZoom);

    return {
      buffer: stitched,
      bbox: {
        north: topLeft.north,
        south: bottomRight.south,
        west: topLeft.west,
        east: bottomRight.east,
      },
      widthPx: COMPOSITE_PX,
      heightPx: COMPOSITE_PX,
    };
  } catch (err) {
    console.error("[Boundary Detection] Sharp composite error:", err);
    return null;
  }
}

// ─── Robust JSON Extraction ─────────────────────────────────────────────

function extractJSON(raw: string): any {
  let cleaned = raw.trim();

  // Strip markdown code fences if present
  const fenceMatch = cleaned.match(/```(?:json)?\s*\n?([\s\S]*?)```/);
  if (fenceMatch) {
    cleaned = fenceMatch[1].trim();
  }

  // Try direct parse first
  try {
    return JSON.parse(cleaned);
  } catch {
    // fallback
  }

  // Bracket matching for outermost object or array
  const firstBrace = cleaned.indexOf("{");
  const firstBracket = cleaned.indexOf("[");

  let start = -1;
  let openChar = "{";
  let closeChar = "}";

  if (firstBrace >= 0 && (firstBracket < 0 || firstBrace < firstBracket)) {
    start = firstBrace;
  } else if (firstBracket >= 0) {
    start = firstBracket;
    openChar = "[";
    closeChar = "]";
  }

  if (start >= 0) {
    let depth = 0;
    for (let i = start; i < cleaned.length; i++) {
      if (cleaned[i] === openChar) depth++;
      else if (cleaned[i] === closeChar) depth--;
      if (depth === 0) {
        try {
          return JSON.parse(cleaned.substring(start, i + 1));
        } catch {
          break;
        }
      }
    }
  }

  throw new Error("Could not extract valid JSON from AI response: " + cleaned.substring(0, 150));
}

// ─── Multi-Model Gemini Vision Query with Automatic Fallback ────────────

// ─── Multi-Model Gemini Vision Query with Automatic Fallback ────────────

const CANDIDATE_MODELS = [
  "gemini-3.5-flash-lite",   // Ultra-fast (~2-3s) & reliable spatial delineation
  "gemini-2.5-flash",        // High precision flash
  "gemini-3-flash-preview",  // Experimental preview
  "gemini-3.7-flash",        // Secondary fallback
];

async function queryGeminiVision(base64Image: string, prompt: string): Promise<string> {
  const genAI = new GoogleGenerativeAI(GEMINI_API_KEY);
  let lastError: any = null;

  for (const modelName of CANDIDATE_MODELS) {
    const t0 = Date.now();
    try {
      console.log(`[Boundary Detection] Querying Gemini model '${modelName}'...`);
      const model = genAI.getGenerativeModel({
        model: modelName,
        generationConfig: {
          responseMimeType: "application/json",
          temperature: 0.1,
        },
      });

      const aiResponse = await Promise.race([
        model.generateContent([
          { inlineData: { mimeType: "image/jpeg", data: base64Image } },
          prompt,
        ]),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error(`Timeout with model ${modelName} after 25s`)), 25000)
        ),
      ]);

      const text = aiResponse.response.text();
      console.log(`[Boundary Detection] '${modelName}' succeeded in ${Date.now() - t0}ms (${text.length} chars)`);
      return text;
    } catch (err: any) {
      console.warn(`[Boundary Detection] Model '${modelName}' failed in ${Date.now() - t0}ms:`, err?.message || err);
      lastError = err;
    }
  }

  throw lastError || new Error("All Gemini Vision models failed");
}

// ─── Coordinate Conversion & Geometry Validation ────────────────────────

function normalizedToGeo(
  normY: number,
  normX: number,
  bbox: { north: number; south: number; east: number; west: number }
): [number, number] {
  const lat = bbox.north - (normY / 1000) * (bbox.north - bbox.south);
  const lng = bbox.west + (normX / 1000) * (bbox.east - bbox.west);
  return [lng, lat]; // GeoJSON is [lng, lat]
}

function buildGeoJsonPolygon(
  normalizedVertices: Array<[number, number]>,
  bbox: { north: number; south: number; east: number; west: number }
): GeoJSON.Feature<GeoJSON.Polygon> | null {
  if (!normalizedVertices || normalizedVertices.length < 3) return null;

  const geoCoords: Array<[number, number]> = normalizedVertices.map(([y, x]) =>
    normalizedToGeo(y, x, bbox)
  );

  // Close ring if not closed
  const first = geoCoords[0];
  const last = geoCoords[geoCoords.length - 1];
  if (first[0] !== last[0] || first[1] !== last[1]) {
    geoCoords.push([...first]);
  }

  try {
    const poly = turf.polygon([geoCoords]);

    // Area check (0.01 ha to 2000 ha)
    const areaM2 = turf.area(poly);
    const areaHa = areaM2 / 10000;
    if (areaHa < 0.01 || areaHa > 2000) return null;

    // Fix self-intersections if any
    const kinked = turf.kinks(poly);
    if (kinked.features.length > 0) {
      const simplified = turf.simplify(poly, { tolerance: 0.00005, highQuality: true });
      const kinked2 = turf.kinks(simplified);
      if (kinked2.features.length > 0) return null;
      return simplified as GeoJSON.Feature<GeoJSON.Polygon>;
    }

    return poly as GeoJSON.Feature<GeoJSON.Polygon>;
  } catch {
    return null;
  }
}

// ─── Prompts ────────────────────────────────────────────────────────────

function buildWandPrompt(normY: number, normX: number): string {
  return `You are an expert satellite cadastral surveyor applying European LPIS and USDA parcel delineation standards with millimeter precision.

TARGET:
The user clicked inside an individual agricultural plot/block at normalized coordinate [Y: ${normY}, X: ${normX}]. A red crosshair marker is at this exact point.

TASK: Delineate the exact perimeter contour of ONLY the single individual cultivated plot or orchard block containing the red marker.
Normalized coordinate space: Top-Left = [0, 0], Bottom-Right = [1000, 1000].

MANDATORY LPIS SUB-PARCEL / BLOCK RULES (CRITICAL):
1. IMMEDIATE FIRST PHYSICAL BARRIER IN ALL DIRECTIONS (360°):
   From the red crosshair, trace outwards in all directions until you encounter the VERY FIRST physical barrier:
   - Stop at the FIRST dirt road, tractor access lane, bare-ground pathway, windbreak tree row, hedgerow, or ditch.
   - UNDER NO CIRCUMSTANCES JUMP OVER OR CROSS ANY TREE ROW, DIRT TRACK, OR ACCESS LANE TO REACH A FARTHER BOUNDARY!
2. INDIVIDUAL BLOCK DELINEATION (NO MULTI-BLOCK MERGING):
   - Farms, orchards, and plantations are subdivided into individual rectangular or angled blocks by internal tractor lanes or dirt tracks.
   - Every internal tractor track, vehicle path, or row of shelterbelt trees separates distinct blocks.
   - DO NOT merge adjacent blocks, strips, or neighboring sections across any track or lane!
   - Trace ONLY the single, immediate homogeneous block containing the red marker.
3. CONTOUR ACCURACY:
   - Provide 4 to 16 clockwise vertices [y, x] in 0-1000 normalized space tracing the true physical perimeter of this single block.
   - Follow the actual angle/slant of bordering tracks and roads.
   - Every vertex must lie directly on the boundary between the crop canopy and the bordering track or tree row.
4. The polygon MUST enclose the clicked point [Y: ${normY}, X: ${normX}].

Respond with ONLY this JSON (no markdown fences, no explanation):
{
  "detected": true,
  "name": "<descriptive parcel name, e.g. 'Cultivated Orchard Block'>",
  "cropType": "<detected crop: Orchard, Vineyard, Wheat, Vegetables, Citrus, etc.>",
  "confidence": 0.98,
  "polygon": [
    [y1, x1],
    [y2, x2]
  ]
}

If the clicked point is on a paved highway, urban building, or body of water, return:
{"detected": false};`;
}

function buildScanPrompt(): string {
  return `You are an expert AI satellite surveyor applying European LPIS (Land Parcel Identification System) and USDA agricultural parcel delineation standards.

TASK: Detect and delineate 4 to 8 prominent, clearly defined individual agricultural parcels / orchard blocks / cultivated plots in this satellite image.
Normalized coordinate space: Top-left = [0, 0], Bottom-right = [1000, 1000].

MANDATORY RULES:
1. ZERO TRACK CROSSING: Dirt roads, tractor access tracks, irrigation ditches, vehicle lanes, and tree shelterbelts are ABSOLUTE BOUNDARIES. Each plot must be bounded strictly by the surrounding dirt tracks or roads.
2. SEPARATE ADJACENT PARCELS: Adjacent fields separated by a tractor lane or dirt path must be delineated as separate parcels. NEVER merge adjacent fields across any visible track.
3. PRECISE PHYSICAL FIT: Delineate the real physical perimeter of each parcel (following the crop canopy boundary) with 6 to 20 clockwise vertices [y, x].
4. Parcels MUST NOT overlap each other.
5. Focus on the clearly visible cultivated fields in the central region of the image (between 120 and 880).
6. Ignore roads, buildings, and non-agricultural land.

Respond with ONLY this JSON (no markdown fences, no explanation):
{
  "plots": [
    {
      "name": "<descriptive field name, e.g. 'North Cultivated Parcel'>",
      "cropType": "<crop>",
      "confidence": 0.9,
      "polygon": [
        [y1, x1],
        [y2, x2]
      ]
    }
  ]
}`;
}

// ─── Main Route Handler ─────────────────────────────────────────────────

export async function POST(req: NextRequest) {
  const startTime = Date.now();

  try {
    if (!GEMINI_API_KEY) {
      return NextResponse.json(
        { success: false, error: "GEMINI_API_KEY not configured" },
        { status: 500 }
      );
    }

    const body = await req.json();
    const {
      centerLat,
      centerLng,
      zoom = 16,
      clickLat,
      clickLng,
      mode = "scan",
    } = body;

    const targetLat =
      typeof clickLat === "number" ? clickLat : parseFloat(centerLat);
    const targetLng =
      typeof clickLng === "number" ? clickLng : parseFloat(centerLng);

    if (isNaN(targetLat) || isNaN(targetLng)) {
      return NextResponse.json(
        { success: false, error: "Valid latitude and longitude required" },
        { status: 400 }
      );
    }

    const isWandMode =
      mode === "wand" ||
      (typeof clickLat === "number" && typeof clickLng === "number" && mode !== "scan");

    // For Wand mode, fetch high-resolution satellite imagery (zoom 17-18) so that field tracks, lanes, and boundaries are crystal clear!
    const effectiveZoom = isWandMode
      ? Math.min(18, Math.max(17, Math.round(zoom || 17)))
      : Math.min(18, Math.max(14, Math.round(zoom || 16)));

    console.log(
      `[Boundary Detection] Mode=${mode} target=[${targetLat.toFixed(4)}, ${targetLng.toFixed(4)}] zoom=${effectiveZoom}`
    );

    // 1. Fetch satellite composite (3×3 = 768px centered on target)
    const composite = await getSatelliteComposite(targetLat, targetLng, effectiveZoom);
    if (!composite) {
      return NextResponse.json(
        {
          success: false,
          error: "Unable to retrieve satellite imagery for boundary analysis",
        },
        { status: 502 }
      );
    }

    const { buffer, bbox } = composite;
    const base64Image = buffer.toString("base64");

    console.log(
      `[Boundary Detection] Composite ready: ${(buffer.length / 1024).toFixed(0)}KB, bbox=[${bbox.north.toFixed(4)},${bbox.south.toFixed(4)},${bbox.west.toFixed(4)},${bbox.east.toFixed(4)}]`
    );

    if (isWandMode) {
      // ─── MAGIC WAND: Single-field detection with Visual Crosshair ─────
      const cLat = clickLat as number;
      const cLng = clickLng as number;

      const normY = Math.min(
        990,
        Math.max(10, Math.round(((bbox.north - cLat) / (bbox.north - bbox.south)) * 1000))
      );
      const normX = Math.min(
        990,
        Math.max(10, Math.round(((cLng - bbox.west) / (bbox.east - bbox.west)) * 1000))
      );

      console.log(`[Boundary Detection] Wand click at norm=[${normY}, ${normX}]`);

      // Overlay high-contrast target marker directly on the satellite image
      const pixelX = Math.round((normX / 1000) * COMPOSITE_PX);
      const pixelY = Math.round((normY / 1000) * COMPOSITE_PX);

      const markerSvg = Buffer.from(`
        <svg width="${COMPOSITE_PX}" height="${COMPOSITE_PX}">
          <circle cx="${pixelX}" cy="${pixelY}" r="18" fill="none" stroke="#ff2222" stroke-width="4" />
          <circle cx="${pixelX}" cy="${pixelY}" r="5" fill="#ff2222" />
          <line x1="${pixelX - 32}" y1="${pixelY}" x2="${pixelX - 20}" y2="${pixelY}" stroke="#ff2222" stroke-width="4" />
          <line x1="${pixelX + 20}" y1="${pixelY}" x2="${pixelX + 32}" y2="${pixelY}" stroke="#ff2222" stroke-width="4" />
          <line x1="${pixelX}" y1="${pixelY - 32}" x2="${pixelX}" y2="${pixelY - 20}" stroke="#ff2222" stroke-width="4" />
          <line x1="${pixelX}" y1="${pixelY + 20}" x2="${pixelX}" y2="${pixelY + 32}" stroke="#ff2222" stroke-width="4" />
        </svg>
      `);

      const markedBuffer = await sharp(buffer)
        .composite([{ input: markerSvg, top: 0, left: 0 }])
        .jpeg({ quality: 90 })
        .toBuffer();

      const prompt = buildWandPrompt(normY, normX);
      const rawText = await queryGeminiVision(markedBuffer.toString("base64"), prompt);
      const parsed = extractJSON(rawText);

      if (parsed?.detected === false) {
        return NextResponse.json({
          success: false,
          error: "No clear agricultural field boundary detected at this point",
        });
      }

      if (parsed?.polygon && Array.isArray(parsed.polygon) && parsed.polygon.length >= 3) {
        const geoJson = buildGeoJsonPolygon(parsed.polygon, bbox);

        if (geoJson) {
          const areaHa = parseFloat((turf.area(geoJson) / 10000).toFixed(2));

          console.log(
            `[Boundary Detection] Wand SUCCESS: ${parsed.name || "Field"}, ${areaHa}ha, ${parsed.polygon.length} vertices in ${Date.now() - startTime}ms`
          );

          return NextResponse.json({
            success: true,
            detected: true,
            plot: {
              id: `wand-${Date.now()}`,
              name: parsed.name || "Detected Field",
              cropType: parsed.cropType || "Agricultural Field",
              confidence: Math.min(1, Math.max(0, parsed.confidence || 0.85)),
              areaHa: areaHa > 0 ? areaHa : 1.0,
              geoJson,
              source: "ai-vision-wand" as const,
            },
          });
        }
      }

      return NextResponse.json({
        success: false,
        error: "Field boundary could not be delineated at this point. Try clicking inside a clearly visible field.",
      });
    }

    // ─── AUTO-SCAN: Multi-plot viewport detection ────────────────────
    const prompt = buildScanPrompt();
    const rawText = await queryGeminiVision(base64Image, prompt);
    const parsed = extractJSON(rawText);

    const detectedPlots: Array<{
      id: string;
      name: string;
      cropType: string;
      confidence: number;
      areaHa: number;
      geoJson: GeoJSON.Feature<GeoJSON.Polygon>;
      source: string;
    }> = [];

    if (Array.isArray(parsed?.plots)) {
      for (let i = 0; i < parsed.plots.length; i++) {
        const p = parsed.plots[i];
        if (!Array.isArray(p?.polygon) || p.polygon.length < 3) continue;

        const geoJson = buildGeoJsonPolygon(p.polygon, bbox);
        if (!geoJson) continue;

        const areaHa = parseFloat((turf.area(geoJson) / 10000).toFixed(2));
        if (areaHa < 0.02 || areaHa > 1000) continue;

        detectedPlots.push({
          id: `ai-plot-${i + 1}-${Date.now()}`,
          name: p.name || `Plot #${i + 1}`,
          cropType: p.cropType || "Agricultural Field",
          confidence: Math.min(1, Math.max(0, p.confidence || 0.85)),
          areaHa,
          geoJson,
          source: "ai-vision-scan",
        });
      }
    }

    // Deduplicate overlapping plots: keep distinct parcels
    const nonOverlappingPlots: typeof detectedPlots = [];
    for (const plot of detectedPlots) {
      let overlaps = false;
      for (const accepted of nonOverlappingPlots) {
        try {
          const intersection = turf.intersect(
            turf.featureCollection([plot.geoJson, accepted.geoJson])
          );
          if (intersection) {
            const intersectArea = turf.area(intersection);
            const plotArea = turf.area(plot.geoJson);
            if (plotArea > 0 && intersectArea / plotArea > 0.25) {
              overlaps = true;
              break;
            }
          }
        } catch {
          // If intersection math fails, continue
        }
      }
      if (!overlaps) {
        nonOverlappingPlots.push(plot);
      }
    }

    console.log(
      `[Boundary Detection] Scan COMPLETE: ${nonOverlappingPlots.length} clean plots found in ${Date.now() - startTime}ms`
    );

    return NextResponse.json({
      success: true,
      plots: nonOverlappingPlots,
      count: nonOverlappingPlots.length,
    });
  } catch (err: any) {
    console.error("[Boundary Detection] Route error:", err);
    return NextResponse.json(
      {
        success: false,
        error: err.message || "Failed to detect boundaries",
        details: process.env.NODE_ENV === "development" ? err.stack : undefined,
      },
      { status: 500 }
    );
  }
}

// GET for quick testing
export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const lat = parseFloat(searchParams.get("lat") || "36.5667");
  const lng = parseFloat(searchParams.get("lng") || "2.9167");
  const zoom = parseInt(searchParams.get("zoom") || "16", 10);
  const mode = searchParams.get("mode") || "scan";

  const dummyReq = new NextRequest(req.url, {
    method: "POST",
    body: JSON.stringify({ centerLat: lat, centerLng: lng, zoom, mode }),
    headers: { "Content-Type": "application/json" },
  });

  return POST(dummyReq);
}
