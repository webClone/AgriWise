import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

/**
 * POST /api/sensors/ingest
 * 
 * Accepts telemetry data from IoT devices/gateways.
 * 
 * Body:
 * {
 *   "deviceId": "DEV-1234",        // required
 *   "apiKey": "abc123",             // optional auth
 *   "temperature": 28.5,
 *   "humidity": 65.2,
 *   "soilMoisture": 42.1,
 *   "ec": 1.2,
 *   "windSpeed": 5.3,
 *   "rainfall": 0.5,
 *   "battery": 87,
 *   "rssi": -62
 * }
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { deviceId, apiKey, temperature, humidity, soilMoisture, ec, windSpeed, rainfall, battery, rssi } = body;

    if (!deviceId) {
      return NextResponse.json({ error: "deviceId is required" }, { status: 400 });
    }

    // Find the sensor by deviceId
    const sensor = await prisma.sensor.findUnique({
      where: { deviceId },
    });

    if (!sensor) {
      return NextResponse.json(
        { error: `No sensor registered with deviceId: ${deviceId}` },
        { status: 404 }
      );
    }

    // Optional: verify API key if provided
    if (apiKey && sensor.apiKey && sensor.apiKey !== apiKey) {
      return NextResponse.json({ error: "Invalid API key" }, { status: 403 });
    }

    // Create a reading
    const reading = await prisma.sensorReading.create({
      data: {
        sensorId: sensor.id,
        temperature: temperature != null ? parseFloat(temperature) : null,
        humidity: humidity != null ? parseFloat(humidity) : null,
        soilMoisture: soilMoisture != null ? parseFloat(soilMoisture) : null,
        ec: ec != null ? parseFloat(ec) : null,
        windSpeed: windSpeed != null ? parseFloat(windSpeed) : null,
        rainfall: rainfall != null ? parseFloat(rainfall) : null,
        battery: battery != null ? parseFloat(battery) : null,
        rssi: rssi != null ? parseInt(rssi) : null,
      },
    });

    // Update sensor metadata
    await prisma.sensor.update({
      where: { id: sensor.id },
      data: {
        lastSync: new Date(),
        status: "ACTIVE",
        battery: battery != null ? parseFloat(battery) : sensor.battery,
        rssi: rssi != null ? parseInt(rssi) : sensor.rssi,
      },
    });

    return NextResponse.json({
      success: true,
      readingId: reading.id,
      deviceId,
      timestamp: reading.timestamp,
    });
  } catch (error) {
    console.error("Sensor ingest error:", error);
    return NextResponse.json({ error: "Ingestion failed" }, { status: 500 });
  }
}
