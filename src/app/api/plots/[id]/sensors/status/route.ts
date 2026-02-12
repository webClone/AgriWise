import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

/**
 * GET /api/plots/[id]/sensors/status
 * 
 * Returns computed status for ALL sensors on a plot.
 * Used by the frontend for polling.
 */
export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: plotId } = await params;

    const sensors = await prisma.sensor.findMany({
      where: { plotId },
      orderBy: { createdAt: "desc" },
    });

    const OFFLINE_THRESHOLD_MS = 5 * 60 * 1000;
    const now = Date.now();

    const statuses = await Promise.all(
      sensors.map(async (sensor) => {
        const lastSyncMs = sensor.lastSync ? sensor.lastSync.getTime() : 0;
        const isOnline = now - lastSyncMs < OFFLINE_THRESHOLD_MS;

        // Signal quality from RSSI
        let signalQuality = "None";
        if (sensor.rssi != null) {
          if (sensor.rssi > -50) signalQuality = "Excellent";
          else if (sensor.rssi > -60) signalQuality = "Good";
          else if (sensor.rssi > -70) signalQuality = "Fair";
          else signalQuality = "Weak";
        }

        // Get latest reading
        const latestReading = await prisma.sensorReading.findFirst({
          where: { sensorId: sensor.id },
          orderBy: { timestamp: "desc" },
        });

        return {
          id: sensor.id,
          deviceId: sensor.deviceId,
          type: sensor.type,
          vendor: sensor.vendor,
          status: isOnline ? "ACTIVE" : "OFFLINE",
          isOnline,
          battery: sensor.battery,
          rssi: sensor.rssi,
          signalQuality,
          lastSync: sensor.lastSync,
          createdAt: sensor.createdAt,
          latestReading: latestReading
            ? {
                temperature: latestReading.temperature,
                humidity: latestReading.humidity,
                soilMoisture: latestReading.soilMoisture,
                ec: latestReading.ec,
                windSpeed: latestReading.windSpeed,
                rainfall: latestReading.rainfall,
                timestamp: latestReading.timestamp,
              }
            : null,
        };
      })
    );

    return NextResponse.json({ sensors: statuses });
  } catch (error) {
    console.error("Plot sensors status error:", error);
    return NextResponse.json({ error: "Failed to fetch sensor statuses" }, { status: 500 });
  }
}
