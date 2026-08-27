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
import { writeSnapshot } from "@/lib/intelligence-store";
import { authorizePlot } from "@/lib/agribrain/authorize-plot";
import { loadPlotIntelligenceContext } from "@/lib/agribrain/plot-intelligence-context";

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
    const access = await authorizePlot(plotId, farmId);
    if (!access.plot) {
      return NextResponse.json(
        { success: false, error: access.status === 401 ? "Authentication required" : "Plot not found" },
        { status: access.status },
      );
    }

    const loaded = await loadPlotIntelligenceContext(plotId, farmId);
    if (!loaded.context) {
      return NextResponse.json(
        {
          success: false,
          error: loaded.error === "plot_not_found"
            ? "Plot not found"
            : "Plot has no authoritative geometry or location",
        },
        { status: loaded.error === "plot_not_found" ? 404 : 422 },
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

    // Call AgriBrain LIVE
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 60000);

    const response = await fetch(`${AGRIBRAIN_URL}/v2/plot-intelligence`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lat, lng, crop, polygon, plant_date, crop_administrative_status,
        irrigation_type, soil_type, soil_analysis, physical_constraints,
        area_ha, sensor_readings,
        expert_mode: true,
        force_refresh_weather: true,
        days_past: 7, days_future: 7,
        plot_id: plotId,
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
