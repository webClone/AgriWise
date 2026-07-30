/**
 * /api/agribrain/crop-suitability — Crop Suitability Analysis API
 *
 * Calls the Python biophysical suitability engine to rank all 212 crops
 * against plot environmental conditions. Returns rainfed + irrigated
 * candidates with FAO suitability classes and limiting factors.
 */
import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { authorizePlot } from "@/lib/agribrain/authorize-plot";
import { authenticatedUserId } from "@/lib/tenant-authorization";
import {
  getAuthoritativePlotSpatialContext,
  isValidWgs84Point,
} from "@/lib/agribrain/plot-geometry";

export async function POST(request: NextRequest) {
  try {
    const userId = await authenticatedUserId();
    if (!userId) {
      return NextResponse.json(
        { error: "Authentication required" },
        { status: 401 },
      );
    }
    const body = await request.json();
    const { plotId, lat, lng } = body;

    // If plotId provided, resolve coordinates and get user-declared data
    let plotLat = Number(lat);
    let plotLng = Number(lng);
    // v5.1: Only pass explicitly known user values. No fake defaults.
    let userKnownValues: Record<string, unknown> = {};

    if (plotId) {
      const access = await authorizePlot(plotId);
      if (!access.plot) {
        return NextResponse.json(
          { error: "Plot not found" },
          { status: access.status },
        );
      }
      const plot = await prisma.plot.findFirst({
        where: { id: plotId, farmId: access.plot.farmId },
        include: { farm: true },
      });

      if (plot) {
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
        plotLat = spatial.lat;
        plotLng = spatial.lng;

        // v5.1: Only include explicitly known user-declared values
        // Do NOT inject soil_type defaults — Python backend hydrates from L0
        if (plot.irrigation) {
          userKnownValues.irrigation_type = plot.irrigation;
        }
      }
    }

    if (!isValidWgs84Point({ lat: plotLat, lng: plotLng })) {
      return NextResponse.json(
        { error: "lat and lng are required (or provide plotId)" },
        { status: 400 }
      );
    }

    const apiUrl = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 20_000);

    // v5.1: Send only plotId, coordinates, and explicit user overrides.
    // The Python backend owns all environmental hydration from L0.
    const response = await fetch(`${apiUrl}/v2/crop-suitability`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plot_id: plotId || "",
        lat: Number(plotLat),
        lng: Number(plotLng),
        ...userKnownValues,
        ...pickSuitabilityOverrides(body),
      }),
      signal: controller.signal,
    }).finally(() => clearTimeout(timeoutId));

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`[CropSuitability API] Error: ${response.status} - ${errorText}`);
      return NextResponse.json(
        { success: false, error: `Crop suitability failed: ${response.statusText}` },
        { status: response.status }
      );
    }

    const result = await response.json();
    return NextResponse.json({ success: true, ...result });

  } catch (error: unknown) {
    if (error instanceof Error && error.name === "AbortError") {
      return NextResponse.json(
        { success: false, error: "Crop suitability timed out" },
        { status: 504 }
      );
    }
    const message = error instanceof Error ? error.message : "Unknown error";
    console.error("[CropSuitability API] Error:", message);
    return NextResponse.json(
      { success: false, error: `Crop suitability failed: ${message}` },
      { status: 500 }
    );
  }
}

const SUITABILITY_OVERRIDE_KEYS = [
  "elevation_m",
  "mean_temp_c",
  "annual_rainfall_mm",
  "et0_mm",
  "soil_ph",
  "soil_texture",
  "soil_awc",
  "soil_salinity_ds_m",
  "slope_pct",
  "irrigation_type",
  "frost_days",
  "heat_days_above_35",
  "soil_depth_cm",
] as const;

function pickSuitabilityOverrides(body: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const key of SUITABILITY_OVERRIDE_KEYS) {
    if (body[key] !== undefined && body[key] !== null) result[key] = body[key];
  }
  return result;
}
