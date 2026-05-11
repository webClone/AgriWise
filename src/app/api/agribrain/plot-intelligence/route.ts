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
import { prisma } from "@/lib/db";
import {
  getLatestSnapshot,
  writeSnapshot,
  type CacheStatus,
} from "@/lib/intelligence-store";

const AGRIBRAIN_URL = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";
const AUTO_REFRESH_HOURS = 2;

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
      { status: 500 }
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
  // Resolve plot metadata from DB
  let lat = 36.0;
  let lng = 3.0;
  let crop = "generic";
  let polygon: unknown = null;
  let plant_date: string | null = null;
  let crop_stage_label: string | null = null;
  let irrigation_type: string | null = null;
  let soil_type: string | null = null;
  let soil_analysis: Record<string, unknown> | null = null;
  let physical_constraints: string[] = [];
  let area_ha: number | null = null;
  let sensor_readings: Record<string, unknown>[] = [];

  try {
    const plot = await prisma.plot.findUnique({
      where: { id: plotId },
      include: {
        farm: true,
        cropCycles: {
          where: { status: { not: "HARVESTED" } },
          orderBy: { plantDate: "desc" },
          take: 1,
        },
        soilAnalyses: {
          orderBy: { date: "desc" },
          take: 1,
        },
        sensors: {
          include: {
            readings: {
              orderBy: { timestamp: "desc" },
              take: 5,
            },
          },
        },
      },
    });
    if (plot) {
      lat = plot.farm?.latitude || 36.0;
      lng = plot.farm?.longitude || 3.0;
      crop = plot.cropCycles?.[0]?.cropCode || "generic";

      if (plot.geoJson) {
        try {
          polygon =
            typeof plot.geoJson === "string"
              ? JSON.parse(plot.geoJson)
              : plot.geoJson;
        } catch {
          polygon = null;
        }
      }

      const cycle = plot.cropCycles?.[0];
      if (cycle?.plantDate) {
        plant_date = new Date(cycle.plantDate).toISOString().split("T")[0];
      }
      if (cycle?.status) {
        crop_stage_label = cycle.status;
      }

      irrigation_type = (plot as any).irrigation || null;
      soil_type = (plot as any).soilType || null;
      area_ha = plot.area ?? null;
      physical_constraints =
        ((plot as any).physicalConstraints as string[]) || [];

      const sa = (plot as any).soilAnalyses?.[0];
      if (sa) {
        soil_analysis = {
          ph: sa.ph ?? null,
          organic_matter_pct: sa.organicMatter ?? null,
          nitrogen_ppm: sa.nitrogen ?? null,
          phosphorus_ppm: sa.phosphorus ?? null,
          potassium_ppm: sa.potassium ?? null,
          ec_ds_m: sa.ec ?? null,
          sample_date: sa.date
            ? new Date(sa.date).toISOString().split("T")[0]
            : null,
        };
      }

      const sensors = (plot as any).sensors || [];
      for (const s of sensors) {
        const latest = s.readings?.[0];
        if (!latest) continue;
        sensor_readings.push({
          device_id: s.deviceId,
          type: s.type,
          vendor: s.vendor || null,
          status: s.status,
          battery: s.battery ?? null,
          rssi: s.rssi ?? null,
          last_sync: s.lastSync
            ? new Date(s.lastSync).toISOString()
            : null,
          latest: {
            temperature: latest.temperature ?? null,
            humidity: latest.humidity ?? null,
            soil_moisture: latest.soilMoisture ?? null,
            ec: latest.ec ?? null,
            wind_speed: latest.windSpeed ?? null,
            rainfall: latest.rainfall ?? null,
            timestamp: new Date(latest.timestamp).toISOString(),
          },
        });
      }
    }
  } catch (dbErr) {
    console.warn(
      "[Plot Intelligence] DB fetch failed, using defaults:",
      dbErr
    );
    try {
      const farm = await prisma.farm.findUnique({ where: { id: farmId } });
      if (farm) {
        lat = farm.latitude || 36.0;
        lng = farm.longitude || 3.0;
      }
    } catch {
      /* use defaults */
    }
  }

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
      crop_stage_label,
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
