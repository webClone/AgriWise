import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import crypto from "crypto";
import { physicalObservationStore } from "@/lib/agribrain/physical-observation-store";

/**
 * POST /api/sensors/ingest
 * 
 * Akaloris W2 Secure Sensor Ingestion Endpoint:
 * - Authenticated via timing-safe API key verification
 * - Idempotent & replay-resistant (messageId & provenance hash cache)
 * - Multi-depth channel ingestion with explicit depths
 * - Physical QA range boundaries & quarantine partitioning
 * - Immutable raw payload provenance (SHA-256)
 * - Calibration tracking & expiration checks
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const {
      deviceId,
      apiKey,
      messageId,
      deviceAcquiredAt,
      readings,
      temperature,
      humidity,
      soilMoisture,
      ec,
      windSpeed,
      rainfall,
      battery,
      rssi,
    } = body;

    if (!deviceId || typeof deviceId !== "string") {
      return NextResponse.json({ error: "deviceId is required and must be a string" }, { status: 400 });
    }

    // 1. Device authentication & registration check
    const sensor = await prisma.sensor.findUnique({
      where: { deviceId },
    });

    if (!sensor) {
      return NextResponse.json(
        { error: `No sensor registered with deviceId: ${deviceId}` },
        { status: 404 }
      );
    }

    // Timing-safe API key verification
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

    // 2. Acquisition timestamp validation (format and clock drift)
    if (deviceAcquiredAt != null) {
      const parsedTime = Date.parse(deviceAcquiredAt);
      if (isNaN(parsedTime)) {
        return NextResponse.json(
          { error: "deviceAcquiredAt must be a valid ISO 8601 UTC timestamp" },
          { status: 400 }
        );
      }
      const now = Date.now();
      // Clock drift guard: reject future timestamps exceeding 5 minutes
      if (parsedTime > now + 300_000) {
        return NextResponse.json(
          { error: "deviceAcquiredAt cannot be in the future (clock drift violation)" },
          { status: 400 }
        );
      }
    }

    // 3. Ingestion Engine (handles replay detection, QA range, depth checks, calibration, and quarantine)
    const ingestResult = physicalObservationStore.ingestPayload(body, {
      registeredPlotId: sensor.plotId,
      expectedApiKey: sensor.apiKey ?? undefined,
      rawPayloadForHash: body,
    });

    // Idempotent duplicate replay response
    if (ingestResult.replayed) {
      return NextResponse.json(
        {
          success: true,
          replayed: true,
          message: ingestResult.message || "Duplicate payload detected; idempotent response",
          deviceId,
          serverReceivedAt: ingestResult.serverReceivedAt,
          rawPayloadHash: ingestResult.rawPayloadHash,
        },
        { status: 200 }
      );
    }

    // 4. Persistence into Prisma database
    const primaryMoisture = ingestResult.accepted.find((r) => r.variable === "soil_moisture_vwc");
    const primaryTemp = ingestResult.accepted.find(
      (r) => r.variable === "soil_temperature_c" || r.variable === "air_temperature_c"
    );
    const primaryEc = ingestResult.accepted.find((r) => r.variable === "soil_ec_ds_m");

    const reading = await prisma.sensorReading.create({
      data: {
        sensorId: sensor.id,
        temperature: primaryTemp ? primaryTemp.rawValue : (temperature != null ? Number(temperature) : null),
        humidity: humidity != null ? Number(humidity) : null,
        soilMoisture: primaryMoisture ? primaryMoisture.rawValue : (soilMoisture != null ? Number(soilMoisture) : null),
        ec: primaryEc ? primaryEc.rawValue : (ec != null ? Number(ec) : null),
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
      replayed: false,
      readingId: reading.id,
      deviceId,
      deviceAcquiredAt: ingestResult.deviceAcquiredAt,
      serverReceivedAt: ingestResult.serverReceivedAt,
      rawPayloadHash: ingestResult.rawPayloadHash,
      acceptedCount: ingestResult.accepted.length,
      quarantinedCount: ingestResult.quarantined.length,
      acceptedReadings: ingestResult.accepted.map((r) => ({
        readingId: r.readingId,
        channelId: r.channelId,
        variable: r.variable,
        normalizedValue: r.normalizedValue,
        normalizedUnit: r.normalizedUnit,
        depthCm: r.depthInterval?.nominalCm,
        qaState: r.qaState,
        admissionStatus: r.admissionStatus,
      })),
      quarantinedReadings: ingestResult.quarantined,
    });
  } catch (error: any) {
    console.error("Sensor ingest error:", error);
    if (error?.message?.includes("clock drift violation")) {
      return NextResponse.json({ error: error.message }, { status: 400 });
    }
    if (error?.message?.includes("valid ISO 8601")) {
      return NextResponse.json({ error: error.message }, { status: 400 });
    }
    return NextResponse.json({ error: "Ingestion failed" }, { status: 500 });
  }
}
