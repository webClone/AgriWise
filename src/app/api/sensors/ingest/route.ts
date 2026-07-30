import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import crypto from "crypto";

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

    const suppliedKey = typeof apiKey === "string"
      ? Buffer.from(apiKey, "utf8")
      : Buffer.alloc(0);
    const expectedKey = sensor.apiKey
      ? Buffer.from(sensor.apiKey, "utf8")
      : Buffer.alloc(0);
    if (
      suppliedKey.length === 0
      || suppliedKey.length !== expectedKey.length
      || !crypto.timingSafeEqual(suppliedKey, expectedKey)
    ) {
      return NextResponse.json({ error: "Invalid API key" }, { status: 403 });
    }

    const rawValues = {
      temperature,
      humidity,
      soilMoisture,
      ec,
      windSpeed,
      rainfall,
      battery,
      rssi,
    };
    for (const [name, value] of Object.entries(rawValues)) {
      if (value != null && !Number.isFinite(Number(value))) {
        return NextResponse.json(
          { error: `${name} must be a finite number` },
          { status: 400 },
        );
      }
    }
    if (
      (humidity != null && (Number(humidity) < 0 || Number(humidity) > 100))
      || (
        soilMoisture != null
        && (Number(soilMoisture) < 0 || Number(soilMoisture) > 100)
      )
      || (battery != null && (Number(battery) < 0 || Number(battery) > 100))
      || (rainfall != null && Number(rainfall) < 0)
    ) {
      return NextResponse.json(
        { error: "Telemetry value is outside its physical range" },
        { status: 400 },
      );
    }

    // Create a reading
    const reading = await prisma.sensorReading.create({
      data: {
        sensorId: sensor.id,
        temperature: temperature != null ? Number(temperature) : null,
        humidity: humidity != null ? Number(humidity) : null,
        soilMoisture: soilMoisture != null ? Number(soilMoisture) : null,
        ec: ec != null ? Number(ec) : null,
        windSpeed: windSpeed != null ? Number(windSpeed) : null,
        rainfall: rainfall != null ? Number(rainfall) : null,
        battery: battery != null ? Number(battery) : null,
        rssi: rssi != null ? Math.trunc(Number(rssi)) : null,
      },
    });

    // Update sensor metadata
    await prisma.sensor.update({
      where: { id: sensor.id },
      data: {
        lastSync: new Date(),
        status: "ACTIVE",
        battery: battery != null ? Number(battery) : sensor.battery,
        rssi: rssi != null ? Math.trunc(Number(rssi)) : sensor.rssi,
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
