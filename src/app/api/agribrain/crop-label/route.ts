/**
 * /api/agribrain/crop-label — Crop Label proxy endpoint
 *
 * Proxies confirmed crop labels from the UI to the agribrain backend.
 */
import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { authorizePlot } from "@/lib/agribrain/authorize-plot";

export async function POST(request: NextRequest) {
  try {
    const session = await getSession();
    const userId = session?.userId || null;
    const body = await request.json();

    const {
      plotId,
      cropCode,
      plantingDate,
      harvestDate,
      labelSource,
      notes,
      synthetic
    } = body;

    if (!plotId || !cropCode) {
      return NextResponse.json(
        { error: "plotId and cropCode are required" },
        { status: 400 }
      );
    }
    if (!userId) {
      return NextResponse.json(
        { error: "Authentication required" },
        { status: 401 },
      );
    }
    const access = await authorizePlot(plotId);
    if (!access.plot) {
      return NextResponse.json(
        { error: "Plot not found" },
        { status: access.status },
      );
    }

    const apiUrl = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15_000);

    const response = await fetch(`${apiUrl}/v2/crop-label`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plot_id: plotId,
        crop_code: cropCode,
        planting_date: plantingDate || null,
        harvest_date: harvestDate || null,
        label_source: labelSource,
        created_by: userId,
        notes: notes || null,
        synthetic: !!synthetic,
      }),
      signal: controller.signal,
    }).finally(() => clearTimeout(timeoutId));

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`[CropLabel Proxy API] Error: ${response.status} - ${errorText}`);
      return NextResponse.json(
        { success: false, error: `Crop label creation failed: ${response.statusText}` },
        { status: response.status }
      );
    }

    const result = await response.json();
    return NextResponse.json({ success: true, ...result });

  } catch (error: unknown) {
    if (error instanceof Error && error.name === "AbortError") {
      return NextResponse.json(
        { success: false, error: "Crop label creation timed out" },
        { status: 504 }
      );
    }
    const message = error instanceof Error ? error.message : "Unknown error";
    console.error("[CropLabel Proxy API] Error:", message);
    return NextResponse.json(
      { success: false, error: `Crop label creation failed: ${message}` },
      { status: 500 }
    );
  }
}
