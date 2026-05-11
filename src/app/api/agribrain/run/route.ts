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
  userMode?: string;
}

export async function POST(request: NextRequest) {
  try {
    const body: RunRequest = await request.json();
    const { plotId, query, mode = "chat", history, experienceLevel, userMode = "farmer" } = body;

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
      // Per-sensor array preserves multi-sensor spatial diversity
      const sensorArray = plot.sensors
        .filter((s: any) => s.readings.length > 0)
        .map((s: any) => {
          const r = s.readings[0];
          return {
            id: s.id,
            deviceId: s.deviceId,
            type: s.type,
            lastSync: s.lastSync?.toISOString() || new Date().toISOString(),
            soilMoisture: r.soilMoisture != null ? Number(r.soilMoisture) : null,
            temperature: r.temperature != null ? Number(r.temperature) : null,
            humidity: r.humidity != null ? Number(r.humidity) : null,
            rainfall: r.rainfall != null ? Number(r.rainfall) : null,
            ec: r.ec != null ? Number(r.ec) : null,
            windSpeed: r.windSpeed != null ? Number(r.windSpeed) : null,
            battery: r.battery != null ? Number(r.battery) : null,
            rssi: r.rssi != null ? Number(r.rssi) : null,
          };
        });

      // Flat summary for backward compatibility (L3 features, etc.)
      const sensorSummary: Record<string, number> = {};
      const moistureValues: number[] = [];
      for (const s of sensorArray) {
        if (s.soilMoisture != null) moistureValues.push(s.soilMoisture);
        if (s.temperature != null) sensorSummary.temperature = s.temperature;
        if (s.humidity != null) sensorSummary.humidity = s.humidity;
        if (s.rainfall != null) sensorSummary.rainfall = s.rainfall;
        if (s.ec != null) sensorSummary.ec = s.ec;
        if (s.windSpeed != null) sensorSummary.wind_speed = s.windSpeed;
      }
      // Average across all moisture sensors instead of last-writer-wins
      if (moistureValues.length > 0) {
        sensorSummary.soil_moisture = moistureValues.reduce((a, b) => a + b, 0) / moistureValues.length;
      }

      context.sensors = sensorArray;
      context.sensor_summary = sensorSummary;
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
      exp: experienceLevel || "INTERMEDIATE",
      userMode: userMode
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

    // GAP 2 fix: When surfaces mode returns L10 data, update the latest
    // IntelligenceSnapshot with surface stats + compressed grids
    if (mode === "surfaces" && result.data?.surfaces) {
      try {
        const { extractSurfaceStats, computeSurfaceDigest } = await import("@/lib/ml-features");
        const { gzipSync } = await import("zlib");

        const l10Data = result.data;
        const surfaceStats = extractSurfaceStats(l10Data);
        const surfaceDigest = await computeSurfaceDigest(l10Data);

        // Find the latest snapshot for this plot
        const latestSnap = await prisma.intelligenceSnapshot.findFirst({
          where: { plotId },
          orderBy: { capturedAt: "desc" },
          select: { id: true, surfaceDigest: true },
        });

        if (latestSnap) {
          const gridsChanged = !latestSnap.surfaceDigest || latestSnap.surfaceDigest !== surfaceDigest;
          let surfaceGridsGz: string | null = null;
          if (gridsChanged && Array.isArray(l10Data.surfaces)) {
            const gridData = l10Data.surfaces.map((s: any) => ({
              type: s.semantic_type || s.type,
              grid_ref: s.grid_ref,
              values: s.values,
            }));
            const compressed = gzipSync(Buffer.from(JSON.stringify(gridData)));
            surfaceGridsGz = compressed.toString("base64");
          }

          await prisma.intelligenceSnapshot.update({
            where: { id: latestSnap.id },
            data: {
              surfaceStats: surfaceStats as any,
              surfaceDigest,
              ...(surfaceGridsGz ? { surfaceGridsGz } : {}),
            },
          });
          console.log(`[AgriBrain Run] Updated snapshot ${latestSnap.id} with L10 surface stats`);
        }
      } catch (surfaceErr) {
        console.warn("[AgriBrain Run] Failed to update surface stats:", surfaceErr);
      }
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
