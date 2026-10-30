import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { authenticatedUserId, userOwnsPlot } from "@/lib/tenant-authorization";
import { TELEMETRY_CONTRACT_VERSION } from "@/lib/agribrain/telemetry-contract";
import { serializeOperationalTelemetry } from "@/lib/agribrain/operational-telemetry-transport.mjs";

export const dynamic = "force-dynamic";

/**
 * GET /api/plots/[id]/telemetry — owner-scoped, read-only operational stream.
 * Persisted sensor readings and plot observations are not certified manifest
 * entries and do not mutate scientific publications. No client tenant selector.
 */
export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const userId = await authenticatedUserId();
  if (!userId) {
    return NextResponse.json({ error: "Authentication required" }, { status: 401 });
  }

  const { id: plotId } = await params;
  if (!/^[a-fA-F0-9]{24}$/.test(plotId || "") || !(await userOwnsPlot(userId, plotId))) {
    return NextResponse.json({ error: "Plot not found" }, { status: 404 });
  }

  try {
    // Recheck the authorized plot and derive the actual farm from the database.
    const plot = await prisma.plot.findFirst({
      where: { id: plotId, farm: { userId } },
      select: { farmId: true },
    });
    if (!plot) {
      return NextResponse.json({ error: "Plot not found" }, { status: 404 });
    }

    const scope = { tenantId: userId, farmId: plot.farmId, plotId };
    const [sensorReadings, plotObservations] = await Promise.all([
      prisma.sensorReading.findMany({
        where: { sensor: { is: { plotId } } },
        orderBy: { timestamp: "desc" },
        take: 50,
        select: {
          id: true, timestamp: true, temperature: true, humidity: true,
          soilMoisture: true, rainfall: true, sensor: { select: { deviceId: true } },
        },
      }),
      prisma.plotObservation.findMany({
        // Forecasts must never masquerade as measured observations.
        // Only persistently acquired weather/sensor observations enter M1.
        where: { plotId, source: { in: ["weather", "sensor"] } },
        orderBy: { obsDate: "desc" },
        take: 50,
        select: {
          id: true, source: true, obsDate: true, fetchedAt: true,
          tempC: true, humidity: true, precipMm: true,
          soilMoisture: true, et0: true,
        },
      }),
    ]);

    const observations = serializeOperationalTelemetry({
      sensorReadings, plotObservations, scope,
    });
    return NextResponse.json(
      { contractVersion: TELEMETRY_CONTRACT_VERSION, scope, observations },
      { headers: { "Cache-Control": "private, no-store, max-age=0" } },
    );
  } catch (error) {
    console.error("Authorized plot telemetry fetch failed:", error);
    return NextResponse.json({ error: "Telemetry unavailable" }, { status: 500 });
  }
}
