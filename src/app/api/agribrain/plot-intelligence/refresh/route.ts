/**
 * /api/agribrain/plot-intelligence/refresh — Background Refresh Endpoint
 *
 * Called by the frontend AFTER receiving a STALE cache response.
 * Always calls AgriBrain live, writes a new snapshot, returns fresh data.
 *
 * This is intentionally separate from the main route so the frontend
 * can show cached data instantly while refreshing in the background.
 */
import { NextRequest, NextResponse } from "next/server";
export const runtime = "nodejs"; // Required for zlib in intelligence-store
import { prisma } from "@/lib/db";
import { writeSnapshot } from "@/lib/intelligence-store";

const AGRIBRAIN_URL = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { plotId, farmId } = body;

    if (!plotId || !farmId) {
      return NextResponse.json(
        { success: false, error: "plotId and farmId are required" },
        { status: 400 }
      );
    }

    // Resolve plot metadata
    let lat = 36.0, lng = 3.0, crop = "generic";
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
          soilAnalyses: { orderBy: { date: "desc" }, take: 1 },
          sensors: {
            include: { readings: { orderBy: { timestamp: "desc" }, take: 5 } },
          },
        },
      });

      if (plot) {
        lat = plot.farm?.latitude || 36.0;
        lng = plot.farm?.longitude || 3.0;
        crop = plot.cropCycles?.[0]?.cropCode || "generic";
        area_ha = plot.area ?? null;

        if (plot.geoJson) {
          try {
            polygon = typeof plot.geoJson === "string"
              ? JSON.parse(plot.geoJson) : plot.geoJson;
          } catch { polygon = null; }
        }

        const cycle = plot.cropCycles?.[0];
        if (cycle?.plantDate) {
          plant_date = new Date(cycle.plantDate).toISOString().split("T")[0];
        }
        if (cycle?.status) crop_stage_label = cycle.status;

        irrigation_type = (plot as any).irrigation || null;
        soil_type = (plot as any).soilType || null;
        physical_constraints = ((plot as any).physicalConstraints as string[]) || [];

        const sa = (plot as any).soilAnalyses?.[0];
        if (sa) {
          soil_analysis = {
            ph: sa.ph ?? null,
            organic_matter_pct: sa.organicMatter ?? null,
            nitrogen_ppm: sa.nitrogen ?? null,
            phosphorus_ppm: sa.phosphorus ?? null,
            potassium_ppm: sa.potassium ?? null,
            ec_ds_m: sa.ec ?? null,
            sample_date: sa.date ? new Date(sa.date).toISOString().split("T")[0] : null,
          };
        }

        for (const s of ((plot as any).sensors || [])) {
          const latest = s.readings?.[0];
          if (!latest) continue;
          sensor_readings.push({
            device_id: s.deviceId, type: s.type,
            status: s.status, battery: s.battery ?? null,
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
      console.warn("[Refresh] DB fetch failed, using defaults:", dbErr);
    }

    // Call AgriBrain LIVE
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 60000);

    const response = await fetch(`${AGRIBRAIN_URL}/v2/plot-intelligence`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lat, lng, crop, polygon, plant_date, crop_stage_label,
        irrigation_type, soil_type, soil_analysis, physical_constraints,
        area_ha, sensor_readings,
        expert_mode: true,
        force_refresh_weather: true,
        days_past: 7, days_future: 7,
      }),
      signal: controller.signal,
    });
    clearTimeout(timer);

    if (!response.ok) {
      const errText = await response.text();
      return NextResponse.json(
        { success: false, error: `AgriBrain returned ${response.status}` },
        { status: 502 }
      );
    }

    const data = await response.json();
    data.plotId = plotId;
    data.farmId = farmId;

    // Write new snapshot
    const snapshotId = await writeSnapshot({
      plotId, farmId,
      response: data,
      // Note: L10 surface data comes via /api/agribrain/run, not here
      lat, lng,
      cropCode: crop,
      areaHa: area_ha ?? undefined,
    });

    data._cache = {
      status: "REFRESHED",
      capturedAt: new Date().toISOString(),
      snapshotId,
    };

    const headers = new Headers();
    headers.set("X-Cache-Status", "REFRESHED");
    if (snapshotId) headers.set("X-Snapshot-Id", snapshotId);

    return NextResponse.json(data, { headers });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    console.error("[Refresh API] Error:", message);
    return NextResponse.json(
      { success: false, error: `Refresh failed: ${message}` },
      { status: 500 }
    );
  }
}
