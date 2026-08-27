/**
 * /api/agribrain/plot-intelligence — Cache-First Intelligence API
 *
 * v2: Stale-While-Revalidate pattern
 *
 * Flow:
 *   1. Check MongoDB for latest cached snapshot
 *   2. If fresh (<30min) → return immediately (HIT)
 *   3. If stale (30min-2h) → return cached, set X-Cache-Status: STALE
 *   4. If miss or >2h → call AgriBrain live, write snapshot, return
 *   5. On every live fetch → write IntelligenceSnapshot + update PlotDNA
 *
 * Headers returned:
 *   - X-Cache-Status: HIT | STALE | MISS
 *   - X-Snapshot-Id: MongoDB document ID
 *   - X-Captured-At: ISO timestamp of cached data
 */
import { NextRequest, NextResponse } from "next/server";
export const runtime = "nodejs"; // Required for zlib in intelligence-store
import { authorizePlot } from "@/lib/agribrain/authorize-plot";
import { loadPlotIntelligenceContext } from "@/lib/agribrain/plot-intelligence-context";
import {
  getLatestSnapshot,
  writeSnapshot,
  type CacheStatus,
} from "@/lib/intelligence-store";

const AGRIBRAIN_URL = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";
const AUTO_REFRESH_HOURS = 2;

class PlotContextError extends Error {
  constructor(
    message: string,
    readonly status: 404 | 422,
  ) {
    super(message);
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const {
      plotId,
      farmId,
      expertMode = false,
      forceRefreshWeather = false,
      forceRefresh = false,
    } = body;

    if (!plotId || !farmId) {
      return NextResponse.json(
        { success: false, error: "plotId and farmId are required" },
        { status: 400 }
      );
    }
    const access = await authorizePlot(plotId, farmId);
    if (!access.plot) {
      return NextResponse.json(
        { success: false, error: access.status === 401 ? "Authentication required" : "Plot not found" },
        { status: access.status },
      );
    }

    // ── Step 1: Check cache (unless forced refresh) ───────────────
    if (!forceRefresh) {
      const cached = await getLatestSnapshot(plotId);
      if (cached) {
        const ageHrs =
          (Date.now() - cached.capturedAt.getTime()) / (1000 * 60 * 60);

        // HIT: Fresh data, return immediately
        if (cached.status === "HIT") {
          return buildResponse(cached.data, "HIT", cached);
        }

        // STALE but within auto-refresh window: return cached,
        // frontend will call /refresh endpoint
        if (ageHrs < AUTO_REFRESH_HOURS) {
          return buildResponse(cached.data, "STALE", cached);
        }

        // Very stale (>2h): still return cached, but mark for refresh
        // Frontend MUST call /refresh
        return buildResponse(cached.data, "STALE", cached);
      }
    }

    // ── Step 2: Cache MISS — call AgriBrain live ──────────────────
    const { data: freshData, plotMeta } = await fetchFromAgriBrain(
      plotId,
      farmId,
      expertMode,
      forceRefreshWeather
    );

    // ── Step 3: Write snapshot to DB ──────────────────────────────
    const snapshotId = await writeSnapshot({
      plotId,
      farmId,
      response: freshData,
      // Note: L10 surface data comes via /api/agribrain/run, not here
      lat: plotMeta.lat,
      lng: plotMeta.lng,
      cropCode: plotMeta.crop,
      areaHa: plotMeta.areaHa,
    });

    // Inject metadata
    freshData.plotId = plotId;
    freshData.farmId = farmId;
    freshData._cache = {
      status: "MISS",
      capturedAt: new Date().toISOString(),
      snapshotId,
    };

    return buildResponse(freshData, "MISS");
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    console.error("[Plot Intelligence API] Error:", message);
    return NextResponse.json(
      { success: false, error: `Intelligence fetch failed: ${message}` },
      { status: error instanceof PlotContextError ? error.status : 500 }
    );
  }
}

// ── Build Response with Cache Headers ─────────────────────────────

function buildResponse(
  data: any,
  cacheStatus: CacheStatus,
  cached?: {
    snapshotId: string;
    capturedAt: Date;
    surfaceDigest: string | null;
  }
) {
  const headers = new Headers();
  headers.set("X-Cache-Status", cacheStatus);
  if (cached) {
    headers.set("X-Snapshot-Id", cached.snapshotId);
    headers.set("X-Captured-At", cached.capturedAt.toISOString());
    if (cached.surfaceDigest) {
      headers.set("X-Surface-Digest", cached.surfaceDigest);
    }
  }
  return NextResponse.json(data, { headers });
}

// ── Fetch from AgriBrain (with DB context resolution) ─────────────

async function fetchFromAgriBrain(
  plotId: string,
  farmId: string,
  expertMode: boolean,
  forceRefreshWeather: boolean
): Promise<{ data: any; plotMeta: any }> {
  const loaded = await loadPlotIntelligenceContext(plotId, farmId);
  if (!loaded.context) {
    throw new PlotContextError(
      loaded.error === "plot_not_found"
        ? "Authorized plot context no longer exists"
        : "Plot has no authoritative geometry or location",
      loaded.error === "plot_not_found" ? 404 : 422,
    );
  }
  const {
    lat,
    lng,
    crop,
    polygon,
    plant_date,
    crop_administrative_status,
    irrigation_type,
    soil_type,
    soil_analysis,
    physical_constraints,
    area_ha,
    sensor_readings,
  } = loaded.context;

  // Call AgriBrain
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 60000);

  const response = await fetch(`${AGRIBRAIN_URL}/v2/plot-intelligence`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      lat,
      lng,
      crop,
      polygon,
      plant_date,
      crop_administrative_status,
      irrigation_type,
      soil_type,
      soil_analysis,
      physical_constraints,
      area_ha,
      sensor_readings,
      expert_mode: expertMode,
      force_refresh_weather: forceRefreshWeather,
      days_past: 7,
      days_future: 7,
      plot_id: plotId,
    }),
    signal: controller.signal,
  });
  clearTimeout(timer);

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`AgriBrain returned ${response.status}: ${errText}`);
  }

  const data = await response.json();
  data.plotId = plotId;
  data.farmId = farmId;

  return {
    data,
    plotMeta: { lat, lng, crop, areaHa: area_ha },
  };
}
