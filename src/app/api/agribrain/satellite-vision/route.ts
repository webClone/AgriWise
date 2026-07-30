/**
 * /api/agribrain/satellite-vision — Run LLM vision on a cached tile
 */
import { NextRequest, NextResponse } from "next/server";
import { authorizePlot } from "@/lib/agribrain/authorize-plot";
import { getAuthoritativePlotSpatialContext } from "@/lib/agribrain/plot-geometry";

const AGRIBRAIN_URL = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const plotId = body?.plot_id;
    if (typeof plotId !== "string" || !plotId) {
      return NextResponse.json(
        { status: "error", error: "plot_id is required" },
        { status: 400 },
      );
    }
    const access = await authorizePlot(plotId);
    if (!access.plot) {
      return NextResponse.json(
        {
          status: "error",
          error: access.status === 401
            ? "Authentication required"
            : "Plot not found",
        },
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

    const response = await fetch(`${AGRIBRAIN_URL}/v2/satellite-vision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plot_id: plotId,
        lat: spatial.lat,
        lng: spatial.lng,
        polygon: spatial.polygon,
        force: body.force === true,
      }),
      signal: AbortSignal.timeout(30000),
    });

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
