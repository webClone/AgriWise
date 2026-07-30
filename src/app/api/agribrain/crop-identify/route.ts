/**
 * /api/agribrain/crop-identify — Crop Auto-Identification API
 * 
 * Calls the Python biophysical engine to identify the crop on a plot
 * using satellite data (NDVI, SAR, weather, location).
 * Returns ranked crop candidates with confidence scores.
 * 
 * Now sends per-plot differentiating data (area, soilType, irrigation,
 * polygon centroid, previous crops) so plots on the same farm get
 * different results.
 */
import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { authorizePlot } from "@/lib/agribrain/authorize-plot";
import { getAuthoritativePlotSpatialContext } from "@/lib/agribrain/plot-geometry";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { plotId } = body;

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

    // Fetch plot + farm + crop cycles for full context
    const plot = await prisma.plot.findFirst({
      where: { id: plotId, farmId: access.plot.farmId },
      include: {
        farm: true,
        cropCycles: {
          orderBy: { plantDate: "desc" },
          take: 5,
          select: {
            cropCode: true,
            cropNameAr: true,
            plantDate: true,
            status: true,
            actualYield: true,
          },
        },
      },
    });

    if (!plot) {
      return NextResponse.json(
        { error: "Plot not found" },
        { status: 404 }
      );
    }

    const spatial = getAuthoritativePlotSpatialContext(
      plot.geoJson,
      plot.farm?.latitude,
      plot.farm?.longitude,
    );
    if (!spatial) {
      return NextResponse.json(
        { error: "Plot has no authoritative geometry or location" },
        { status: 422 },
      );
    }

    // Build previous crops list for the engine
    const previousCrops = plot.cropCycles
      .filter((c: { status: string }) => c.status !== "PLANNED")
      .map((c: { cropCode: string; plantDate: Date }) => ({
        code: c.cropCode,
        plantDate: c.plantDate.toISOString().split("T")[0],
      }));

    // Call the Python backend crop identification endpoint
    const apiUrl = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15_000);

    const response = await fetch(`${apiUrl}/v2/crop-identify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plot_id: plotId,
        lat: spatial.lat,
        lng: spatial.lng,
        // Per-plot differentiating data
        area_ha: plot.area || null,
        soil_type: plot.soilType || null,
        irrigation: plot.irrigation || null,
        plot_name: plot.name || null,
        previous_crops: previousCrops,
      }),
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
