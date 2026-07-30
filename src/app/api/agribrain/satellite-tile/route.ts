/**
 * /api/agribrain/satellite-tile — Satellite RGB Tile Proxy
 *
 * THIN PROXY to AgriBrain's /v2/satellite-tile endpoint.
 * Triggered once on plot page load (fire-and-forget from PlotDashboard).
 * The backend caches tiles for 7 days, so this is a no-op most of the time.
 */
import { NextRequest, NextResponse } from "next/server";
import { authorizePlot } from "@/lib/agribrain/authorize-plot";
import { getAuthoritativePlotSpatialContext } from "@/lib/agribrain/plot-geometry";

const AGRIBRAIN_URL = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { plot_id } = body;

    if (!plot_id) {
      return NextResponse.json(
        { status: "error", error: "plot_id is required" },
        { status: 400 }
      );
    }
    const access = await authorizePlot(plot_id);
    if (!access.plot) {
      return NextResponse.json(
        { status: "error", error: access.status === 401 ? "Authentication required" : "Plot not found" },
        { status: access.status },
      );
    }
    const spatial = getAuthoritativePlotSpatialContext(
      access.plot.geoJson,
      access.plot.farm.latitude,
      access.plot.farm.longitude,
    );
    if (!spatial) {
      return NextResponse.json(
        { status: "error", error: "Plot has no authoritative geometry or location" },
        { status: 422 },
      );
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 35000);

    const response = await fetch(`${AGRIBRAIN_URL}/v2/satellite-tile`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plot_id,
        lat: spatial.lat,
        lng: spatial.lng,
        polygon: spatial.polygon,
        force: body.force === true,
      }),
      signal: controller.signal,
    }).finally(() => clearTimeout(timer));

    if (!response.ok) {
      return NextResponse.json(
        { status: "error", error: `AgriBrain returned ${response.status}` },
        { status: 502 }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      { status: "error", error: message },
      { status: 500 }
    );
  }
}
