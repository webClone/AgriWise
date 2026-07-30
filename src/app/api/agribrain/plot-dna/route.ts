/**
 * /api/agribrain/plot-dna — Plot DNA Sequencing Proxy
 *
 * Proxies requests to the AgriBrain /v2/plot-dna endpoint which runs
 * the decadal generative inversion pipeline (EO data + Monte Carlo).
 *
 * This replaces the previous direct localhost:8000 call from
 * PlotDNADashboard.tsx so it works in all environments.
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

    // DNA sequencing is a heavy operation — 120s timeout
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 120000);

    const response = await fetch(`${AGRIBRAIN_URL}/v2/plot-dna`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plot_id,
        lat: spatial.lat,
        lng: spatial.lng,
        polygon: spatial.polygon,
      }),
      signal: controller.signal,
    }).finally(() => clearTimeout(timer));

    if (!response.ok) {
      const errText = await response.text();
      return NextResponse.json(
        { status: "error", error: `AgriBrain returned ${response.status}: ${errText}` },
        { status: 502 }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error: unknown) {
    if (error instanceof Error && error.name === "AbortError") {
      return NextResponse.json(
        { status: "error", error: "DNA sequencing timed out (120s)" },
        { status: 504 }
      );
    }
    const message = error instanceof Error ? error.message : "Unknown error";
    console.error("[Plot DNA API] Error:", message);
    return NextResponse.json(
      { status: "error", error: `DNA sequencing failed: ${message}` },
      { status: 500 }
    );
  }
}
