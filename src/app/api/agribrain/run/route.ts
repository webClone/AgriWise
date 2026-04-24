/**
 * /api/agribrain/run — Unified AgriBrain Run API
 * 
 * Single entry point that replaces:
 *   - /api/agribrain/analyze (legacy orchestrator.py)
 *   - /api/agribrain/surfaces (synthetic L10 bridge)
 *   - /api/agribrain/chat (already on Orchestrator v2)
 * 
 * All modes go through Orchestrator v2 → real data only.
 * 
 * Modes:
 *   chat     — Intent-aware, returns ChatPayload (backward compat)
 *   full     — Full pipeline, returns AgriBrainRun JSON
 *   surfaces — Pipeline + Layer 10 surfaces
 */
import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";

interface RunRequest {
  plotId: string;
  query?: string;
  mode?: "chat" | "full" | "surfaces";
  history?: Array<{ role: string; content: string }>;
  experienceLevel?: string;
}

export async function POST(request: NextRequest) {
  try {
    const body: RunRequest = await request.json();
    const { plotId, query, mode = "chat", history, experienceLevel } = body;

    if (!plotId) {
      return NextResponse.json(
        { success: false, error: "plotId is required" },
        { status: 400 }
      );
    }

    // 1. Fetch real data from DB
    const plot = await prisma.plot.findUnique({
      where: { id: plotId },
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

    // 2. Build context
    const context: Record<string, unknown> = {
      plot_id: plotId,
      lat: plot?.farm?.latitude || 36.0,
      lng: plot?.farm?.longitude || 3.0,
      area: plot?.area,
      farm_id: plot?.farmId || "UNKNOWN",
      polygon: plot?.geoJson || null, // Thread real polygon
    };

    if (plot?.cropCycles?.length) {
      context.crop = plot.cropCycles[0].cropCode;
      context.stage = plot.cropCycles[0].status;
    }

    if (plot?.soilAnalyses?.length) {
      const soil = plot.soilAnalyses[0];
      context.soil_type = plot.soilType || "LOAM";
      context.soil = {
        type: plot.soilType || "LOAM",
        ph: soil.ph,
        organic_matter: soil.organicMatter,
        texture: soil.texture,
      };
    }

    if (plot?.sensors?.length) {
      const sensorData: Record<string, number> = {};
      for (const s of plot.sensors) {
        if (s.readings.length > 0) {
          const r = s.readings[0];
          if (r.soilMoisture !== null) sensorData.soil_moisture = Number(r.soilMoisture);
          if (r.temperature !== null) sensorData.temperature = Number(r.temperature);
          if (r.humidity !== null) sensorData.humidity = Number(r.humidity);
          if (r.rainfall !== null) sensorData.rainfall = Number(r.rainfall);
        }
      }
      context.sensors = sensorData;
    }

    // 3. Encode context
    const contextB64 = Buffer.from(JSON.stringify(context)).toString("base64");

    // 4. Build API Request
    const historyB64 = history && history.length > 0
      ? Buffer.from(JSON.stringify(history)).toString("base64")
      : "";

    const payload = {
      context: contextB64,
      query: query || "",
      mode: mode || "chat",
      history: historyB64,
      exp: experienceLevel || "INTERMEDIATE"
    };

    const apiUrl = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";

    const response = await fetch(`${apiUrl}/v2/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
        const errorText = await response.text();
        console.error(`[AgriBrain Run API] Error: ${response.status} - ${errorText}`);
        return NextResponse.json(
          { success: false, error: `AgriBrain run failed: ${response.statusText}` },
          { status: response.status }
        );
    }

    // 5. Parse JSON
    const result = await response.json();

    if (result.error) {
      return NextResponse.json(
        { success: false, error: result.error, details: result.type },
        { status: 500 }
      );
    }

    return NextResponse.json(result);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    console.error("[AgriBrain Run] Error:", message);
    return NextResponse.json(
      { success: false, error: `AgriBrain run failed: ${message}` },
      { status: 500 }
    );
  }
}
