import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { authenticatedUserId, userOwnsPlot } from "@/lib/tenant-authorization";
import { physicalObservationStore } from "@/lib/agribrain/physical-observation-store";
import {
  SoilDepthProfile,
  STANDARD_SOIL_PROFILE_DEPTHS_CM,
} from "@/lib/agribrain/physical-sensor-contract";

export const dynamic = "force-dynamic";

/**
 * GET /api/plots/[id]/sensors/depth-profile
 *
 * Akaloris W2 Multi-Depth Profile & Sensor State API:
 * - Strictly owner-scoped (401 unauthenticated, 404 unauthorized/wrong tenant)
 * - True multi-depth observation profiles with measured channels
 * - Explicit gaps for unmeasured depths (zero synthetic fabrication)
 * - Channel health, freshness (FRESH/STALE/OFFLINE), and calibration status
 * - Never fabricates 15cm or "VALID" calibration for legacy records without depth
 * - Bounded query parameters (limit <= 100)
 * - Sealed historical publication isolation
 */
export async function GET(
  request: NextRequest,
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
    const { searchParams } = new URL(request.url);
    const requestedDeviceId = searchParams.get("deviceId") || undefined;
    const since = searchParams.get("since") || undefined;
    const rawLimit = searchParams.get("limit");
    const limit = rawLimit ? Math.min(Math.max(1, parseInt(rawLimit, 10) || 50), 100) : 50;

    // Fetch authorized sensors for this plot
    const sensors = await prisma.sensor.findMany({
      where: { plotId },
      orderBy: { createdAt: "desc" },
      select: {
        id: true,
        deviceId: true,
        type: true,
        vendor: true,
        status: true,
        battery: true,
        rssi: true,
        lastSync: true,
      },
    });

    if (sensors.length === 0) {
      return NextResponse.json(
        {
          plotId,
          profile: null,
          channels: [],
          history: [],
          quarantinedCount: 0,
          message: "No sensors registered on this plot",
        },
        { headers: { "Cache-Control": "private, no-store, max-age=0" } }
      );
    }

    const targetSensor = requestedDeviceId
      ? sensors.find((s) => s.deviceId === requestedDeviceId)
      : sensors[0];

    if (!targetSensor) {
      return NextResponse.json(
        { error: `Device ${requestedDeviceId} not found on this plot` },
        { status: 404 }
      );
    }

    const deviceId = targetSensor.deviceId;

    // 1. Fetch multi-depth profile from durable observation store
    let depthProfile: SoilDepthProfile = physicalObservationStore.getSoilDepthProfile(plotId, deviceId);

    // If store has no multi-depth readings, check Prisma for fallback metadata
    // Truthfulness invariant (W2-R05):
    // If a legacy Prisma reading exists without registered depth mapping,
    // do NOT invent 15cm nominal depth or claim VALID calibration!
    if (depthProfile.measuredCount === 0) {
      const latestPrismaReading = await prisma.sensorReading.findFirst({
        where: { sensorId: targetSensor.id },
        orderBy: { timestamp: "desc" },
      });

      const standardDepths = [10, 15, 30, 45, 60, 90];
      depthProfile = {
        plotId,
        deviceId,
        timestamp: latestPrismaReading?.timestamp.toISOString() ?? new Date().toISOString(),
        standardDepthsCm: standardDepths,
        layers: standardDepths.map((nominalCm) => ({
          nominalCm,
          measured: false,
          vwcFraction: null,
          reading: null,
          label: "Not measured —",
        })),
        measuredCount: 0,
        rootZoneAggregateAllowed: false,
        supportDifferenceDisclaimer:
          "No registered multi-depth sensor observations available. Individual point measurements cannot be assumed to represent root-zone profile.",
      };
    }

    // 2. Fetch history time series (strictly bounded)
    const observations = physicalObservationStore.getObservationsForPlot(plotId, {
      deviceId,
      variable: "soil_moisture_vwc",
      since,
      limit,
    });

    // 3. Channel health and freshness
    let channels = physicalObservationStore.getChannelsForDevice(deviceId);

    // If no dynamic channels registered, supply status from database metadata
    // Truthfulness invariant (W2-R05): calibrationStatus is UNREGISTERED, depth is null
    if (channels.length === 0) {
      const now = Date.now();
      const lastSyncMs = targetSensor.lastSync ? targetSensor.lastSync.getTime() : 0;
      const isOnline = now - lastSyncMs < 45 * 60 * 1000;
      const isStale = now - lastSyncMs >= 15 * 60 * 1000 && isOnline;

      channels = [
        {
          channelId: "ch_unregistered",
          deviceId,
          variable: "soil_moisture_vwc",
          depthCm: null,
          status: isOnline ? "ACTIVE" : "OFFLINE",
          freshness: !isOnline ? "OFFLINE" : isStale ? "STALE" : "FRESH",
          calibrationStatus: "UNREGISTERED",
          lastSeen: targetSensor.lastSync ? targetSensor.lastSync.toISOString() : null,
          latestNormalizedValue: null,
          latestUnit: null,
        },
      ];
    }

    const quarantinedCount = physicalObservationStore.getQuarantined(plotId).length;

    return NextResponse.json(
      {
        plotId,
        deviceId,
        profile: depthProfile,
        channels,
        history: observations.map((o) => ({
          readingId: o.readingId,
          channelId: o.channelId,
          variable: o.variable,
          normalizedValue: o.normalizedValue,
          normalizedUnit: o.normalizedUnit,
          depthCm: o.depthInterval?.nominalCm ?? null,
          deviceAcquiredAt: o.deviceAcquiredAt,
          qaState: o.qaState,
        })),
        quarantinedCount,
        rootZoneAggregateAllowed: depthProfile.rootZoneAggregateAllowed,
        supportDifferenceDisclaimer: depthProfile.supportDifferenceDisclaimer,
      },
      { headers: { "Cache-Control": "private, no-store, max-age=0" } }
    );
  } catch (error) {
    console.error("Depth profile fetch error:", error);
    return NextResponse.json({ error: "Failed to fetch depth profile" }, { status: 500 });
  }
}
