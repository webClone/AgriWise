import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import crypto from "crypto";
import { physicalObservationStore } from "@/lib/agribrain/physical-observation-store";

/**
 * POST /api/sensors/ingest
 * 
 * Akaloris W2 Secure Sensor Ingestion Endpoint:
 * - Authenticated via timing-safe API key verification
 * - Bounded payload size (<1MB) and readings count (<=50)
 * - Atomic ingest transaction & deduplication registry
 * - Conflict detection (HTTP 409) for conflicting payload digests
 * - Idempotent replay response (HTTP 200) for identical payload digests
 * - Multi-depth channel ingestion with explicit registered depths
 * - Physical QA range boundaries & quarantine partitioning
 * - All-quarantined payload suppression of active sensor state & unverified reading records
 * - Immutable raw payload provenance (SHA-256)
 * - Calibration tracking & expiration checks
 */
export async function POST(request: NextRequest) {
  const ISO_UTC_REGEX = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/;
  try {
    // 0. Bounded payload check
    const contentLength = request.headers?.get ? request.headers.get("content-length") : null;
    if (contentLength && parseInt(contentLength, 10) > 1024 * 1024) {
      return NextResponse.json({ error: "Payload exceeds 1MB limit" }, { status: 413 });
    }

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

    if (Array.isArray(readings) && readings.length > 50) {
      return NextResponse.json(
        { error: "Payload exceeds maximum allowed readings count (50)" },
        { status: 400 }
      );
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
      if (typeof deviceAcquiredAt !== "string" || !ISO_UTC_REGEX.test(deviceAcquiredAt)) {
        return NextResponse.json(
          { error: "deviceAcquiredAt must be a valid ISO 8601 UTC timestamp" },
          { status: 400 }
        );
      }
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

    // 3. Prepare Ingestion (handles replay detection, QA range, depth checks, calibration, and quarantine)
    const prepared = physicalObservationStore.prepareIngest(body, {
      registeredPlotId: sensor.plotId,
      expectedApiKey: sensor.apiKey ?? undefined,
      rawPayloadForHash: body,
    });

    // 3a. Conflict Detection (W2-R03): 409 Conflict if same messageId has different payload digest
    if (prepared.conflict) {
      return NextResponse.json(
        {
          error: prepared.error || "Conflicting message payload digest",
          deviceId,
          rawPayloadHash: prepared.rawPayloadHash,
        },
        { status: 409 }
      );
    }

    // 3b. Idempotent duplicate replay response
    if (prepared.replayed) {
      return NextResponse.json(
        {
          success: true,
          replayed: true,
          message: prepared.message || "Duplicate payload detected; idempotent response",
          deviceId,
          serverReceivedAt: prepared.serverReceivedAt,
          rawPayloadHash: prepared.rawPayloadHash,
        },
        { status: 200 }
      );
    }

    // 4. All-Quarantined Payload Handling (W2-R04)
    // If every physical measurement was quarantined, do NOT create a Prisma reading and do NOT mark device ACTIVE.
    if (prepared.allQuarantined || prepared.accepted.length === 0) {
      // Commit quarantine evidence to durable store
      const ingestResult = physicalObservationStore.commitIngest(prepared);

      // Record lastSync on sensor without changing status to ACTIVE
      await prisma.sensor.update({
        where: { id: sensor.id },
        data: {
          lastSync: new Date(),
        },
      });

      return NextResponse.json(
        {
          success: true,
          replayed: false,
          allQuarantined: true,
          deviceId,
          deviceAcquiredAt: ingestResult.deviceAcquiredAt,
          serverReceivedAt: ingestResult.serverReceivedAt,
          timeBasis: ingestResult.timeBasis,
          rawPayloadHash: ingestResult.rawPayloadHash,
          acceptedCount: 0,
          quarantinedCount: ingestResult.quarantined.length,
          acceptedReadings: [],
          quarantinedReadings: ingestResult.quarantined,
        },
        { status: 200 }
      );
    }

    // 5. Persistence into Prisma database (Atomic: write DB first, then commit to store) (W2-R02)
    const primaryMoisture = prepared.accepted.find((r) => r.variable === "soil_moisture_vwc");
    const primaryTemp = prepared.accepted.find(
      (r) => r.variable === "soil_temperature_c" || r.variable === "air_temperature_c"
    );
    const primaryEc = prepared.accepted.find((r) => r.variable === "soil_ec_ds_m");

    let reading;
    try {
      reading = await prisma.sensorReading.create({
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

      // Update sensor metadata & status
      await prisma.sensor.update({
        where: { id: sensor.id },
        data: {
          lastSync: new Date(),
          status: "ACTIVE",
          battery: battery != null ? Number(battery) : sensor.battery,
          rssi: rssi != null ? Math.trunc(Number(rssi)) : sensor.rssi,
        },
      });
    } catch (dbErr: any) {
      // Database failure: DO NOT commit to observation store!
      // This ensures a subsequent retry does NOT return a false replayed: true (W2-R02).
      console.error("Database persistence failure during sensor ingestion:", dbErr);
      return NextResponse.json(
        { error: "Database transaction failed during telemetry persistence" },
        { status: 500 }
      );
    }

    // 6. Commit to durable physical observation store only after successful DB persistence
    const ingestResult = physicalObservationStore.commitIngest(prepared);

    return NextResponse.json({
      success: true,
      replayed: false,
      allQuarantined: false,
      readingId: reading.id,
      deviceId,
      deviceAcquiredAt: ingestResult.deviceAcquiredAt,
      serverReceivedAt: ingestResult.serverReceivedAt,
      timeBasis: ingestResult.timeBasis,
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
