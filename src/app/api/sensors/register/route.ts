import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import crypto from "crypto";

/**
 * POST /api/sensors/register
 * 
 * Registers a new sensor device and generates an API key.
 * 
 * Body:
 * {
 *   "plotId": "...",
 *   "deviceId": "ESP32-FIELD-A1",
 *   "type": "MOISTURE",
 *   "vendor": "Espressif"
 * }
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { plotId, deviceId, type, vendor } = body;

    if (!plotId || !deviceId || !type) {
      return NextResponse.json(
        { error: "plotId, deviceId, and type are required" },
        { status: 400 }
      );
    }

    // Check if deviceId already exists
    const existing = await prisma.sensor.findUnique({
      where: { deviceId },
    });

    if (existing) {
      return NextResponse.json(
        { error: `A sensor with deviceId "${deviceId}" is already registered` },
        { status: 409 }
      );
    }

    // Generate API key
    const apiKey = `agw_${crypto.randomBytes(24).toString("hex")}`;

    const sensor = await prisma.sensor.create({
      data: {
        plotId,
        deviceId,
        type,
        vendor: vendor || null,
        apiKey,
        status: "OFFLINE", // Starts offline until first data arrives
      },
    });

    return NextResponse.json({
      success: true,
      sensorId: sensor.id,
      deviceId: sensor.deviceId,
      apiKey,
    });
  } catch (error) {
    console.error("Sensor register error:", error);
    return NextResponse.json({ error: "Registration failed" }, { status: 500 });
  }
}
