import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { authorizePlot } from "@/lib/agribrain/authorize-plot";
import { getAuthoritativePlotSpatialContext } from "@/lib/agribrain/plot-geometry";

interface SandboxRequest {
  plotId: string;
  tempOffset?: number;
  rainVolume?: number;
  irrigationMode?: string;
  nitrogenApplied?: number;
}

export async function POST(request: NextRequest) {
  try {
    const body: SandboxRequest = await request.json();
    const {
      plotId,
      tempOffset = 0.0,
      rainVolume = 0.0,
      irrigationMode = "default",
      nitrogenApplied = 0.0,
    } = body;

    if (!plotId) {
      return NextResponse.json(
        { success: false, error: "plotId is required" },
        { status: 400 }
      );
    }
    const access = await authorizePlot(plotId);
    if (!access.plot) {
      return NextResponse.json(
        {
          success: false,
          error: access.status === 401
            ? "Authentication required"
            : "Plot not found",
        },
        { status: access.status },
      );
    }

    // 1. Fetch rich database metrics to formulate context
    const plot = await prisma.plot.findFirst({
      where: { id: plotId, farmId: access.plot.farmId },
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
          where: { status: "ACTIVE" },
          include: {
            readings: {
              orderBy: { timestamp: "desc" },
              take: 1,
            },
          },
        },
      },
    });

    if (!plot) {
      return NextResponse.json(
        { success: false, error: "Plot not found" },
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
        { success: false, error: "Plot has no authoritative geometry or location" },
        { status: 422 },
      );
    }

    // 2. Build plot context
    const context: Record<string, any> = {
      plot_id: plotId,
      lat: spatial.lat,
      lng: spatial.lng,
      area: plot.area,
      farm_id: plot.farmId || "UNKNOWN",
      polygon: spatial.polygon,
      theta_retention: plot.soilType === "PEAT" ? 1.25 : plot.soilType === "SANDY" ? 0.70 : 1.0,
    };

    if (plot.cropCycles?.length) {
      context.crop = plot.cropCycles[0].cropCode;
      context.stage = plot.cropCycles[0].status;
    }

    if (plot.soilAnalyses?.length) {
      const soil = plot.soilAnalyses[0];
      context.soil_type = plot.soilType || "LOAM";
      context.soil = {
        type: plot.soilType || "LOAM",
        ph: soil.ph,
        organic_matter: soil.organicMatter,
        texture: soil.texture,
      };
    }

    if (plot.sensors?.length) {
      const sensorArray = plot.sensors
        .filter((s: any) => s.readings.length > 0)
        .map((s: any) => {
          const r = s.readings[0];
          return {
            id: s.id,
            deviceId: s.deviceId,
            type: s.type,
            soilMoisture: r.soilMoisture != null ? Number(r.soilMoisture) : null,
            temperature: r.temperature != null ? Number(r.temperature) : null,
            humidity: r.humidity != null ? Number(r.humidity) : null,
          };
        });

      const sensorSummary: Record<string, number> = {};
      const moistureValues: number[] = [];
      for (const s of sensorArray) {
        if (s.soilMoisture != null) moistureValues.push(s.soilMoisture);
        if (s.temperature != null) sensorSummary.temperature = s.temperature;
        if (s.humidity != null) sensorSummary.humidity = s.humidity;
      }
      if (moistureValues.length > 0) {
        sensorSummary.soil_moisture =
          moistureValues.reduce((a, b) => a + b, 0) / moistureValues.length;
      }

      context.sensors = sensorArray;
      context.sensor_summary = sensorSummary;
    }

    // 3. Base64 Encode Context
    const contextB64 = Buffer.from(JSON.stringify(context)).toString("base64");

    // 4. Send POST request to FastAPI Sandbox Endpoint
    const payload = {
      context: contextB64,
      temp_offset: tempOffset,
      rain_volume: rainVolume,
      irrigation_mode: irrigationMode,
      nitrogen_applied: nitrogenApplied,
    };

    const apiUrl = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";

    const response = await fetch(`${apiUrl}/v2/sandbox/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`[Sandbox API Gate] Error: ${response.status} - ${errorText}`);
      return NextResponse.json(
        { success: false, error: `Sandbox run failed: ${response.statusText}` },
        { status: response.status }
      );
    }

    const result = await response.json();
    return NextResponse.json(result);
  } catch (error: any) {
    console.error("[Sandbox API Gate] System Error:", error);
    return NextResponse.json(
      { success: false, error: error.message || "Unknown gateway error" },
      { status: 500 }
    );
  }
}
