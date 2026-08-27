/**
 * /api/agribrain/crop-identify — Canonical Crop Identity API
 * 
 * Reads the canonical crop posterior and returns its public identity DTO.
 * Declarations, EO crop-group support, and independent species confirmation
 * remain separate claims. Ranking shares are not calibrated probabilities.
 * 
 * No acquisition or species-scoring context is sent: the backend reads the
 * already-published, namespace-bound canonical crop posterior.
 */
import { NextRequest, NextResponse } from "next/server";
import { authorizePlot } from "@/lib/agribrain/authorize-plot";
import { getSession } from "@/lib/session";
import { buildSignedInternalHeaders } from "@/lib/agribrain/internal-service-auth";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { plotId } = body;
    const session = await getSession();

    if (!plotId) {
      return NextResponse.json(
        { error: "plotId is required" },
        { status: 400 }
      );
    }
    const access = await authorizePlot(plotId);
    if (!access.plot) {
      return NextResponse.json(
        { error: access.status === 401 ? "Authentication required" : "Plot not found" },
        { status: access.status },
      );
    }

    // Read the canonical backend crop-identification DTO. This request does
    // not launch a second live crop-scoring pipeline.
    const apiUrl = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15_000);

    const upstreamPath = "/v2/crop-identify";
    const upstreamBody = JSON.stringify({
      plot_id: plotId,
    });
    const signedHeaders = buildSignedInternalHeaders(
      "POST",
      upstreamPath,
      {
        tenantId: String(session?.userId || ""),
        farmId: String(access.plot.farmId),
        plotId: String(plotId),
      },
      upstreamBody,
    );

    const response = await fetch(`${apiUrl}${upstreamPath}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...signedHeaders },
      body: upstreamBody,
      signal: controller.signal,
    }).finally(() => clearTimeout(timeoutId));

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`[CropIdentify API] Error: ${response.status} - ${errorText}`);
      return NextResponse.json(
        { success: false, error: `Crop identification failed: ${response.statusText}` },
        { status: response.status }
      );
    }

    const result = await response.json();
    if (result?.crop_identify_dto_version !== "crop-identify-dto-v2") {
      console.error("[CropIdentify API] Unsupported public DTO version");
      return NextResponse.json(
        { success: false, error: "Canonical crop identity publication is incompatible" },
        { status: 502 },
      );
    }
    return NextResponse.json({ success: true, ...result });

  } catch (error: unknown) {
    if (error instanceof Error && error.name === "AbortError") {
      return NextResponse.json(
        { success: false, error: "Crop identification timed out" },
        { status: 504 }
      );
    }
    const message = error instanceof Error ? error.message : "Unknown error";
    console.error("[CropIdentify API] Error:", message);
    return NextResponse.json(
      { success: false, error: `Crop identification failed: ${message}` },
      { status: 500 }
    );
  }
}
