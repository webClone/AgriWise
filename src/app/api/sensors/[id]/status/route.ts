import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

/**
 * GET /api/sensors/[id]/status
 * 
 * Returns computed status for a single sensor:
 * - online/offline (offline if no data in 5 minutes)
 * - battery, rssi, lastSync
 * - latest reading values
 */
export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;

    const sensor = await prisma.sensor.findFirst({
      where: { id },
    });

    if (!sensor) {
      return NextResponse.json({ error: "Sensor not found" }, { status: 404 });
    }

    // Compute online/offline
    const OFFLINE_THRESHOLD_MS = 5 * 60 * 1000; // 5 minutes
    const now = Date.now();
    const lastSyncMs = sensor.lastSync ? sensor.lastSync.getTime() : 0;
    const isOnline = now - lastSyncMs < OFFLINE_THRESHOLD_MS;

    // Get latest reading
    const latestReading = await prisma.sensorReading.findFirst({
      where: { sensorId: sensor.id },
      orderBy: { timestamp: "desc" },
    });

    // Compute signal quality from RSSI
    let signalQuality = "None";
    if (sensor.rssi != null) {
      if (sensor.rssi > -50) signalQuality = "Excellent";
      else if (sensor.rssi > -60) signalQuality = "Good";
      else if (sensor.rssi > -70) signalQuality = "Fair";
      else signalQuality = "Weak";
    }

    return NextResponse.json({
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
    });
  } catch (error) {
    console.error("Sensor status error:", error);
    return NextResponse.json({ error: "Failed to fetch status" }, { status: 500 });
  }
}
