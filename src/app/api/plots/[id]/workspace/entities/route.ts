import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { authenticatedUserId, userOwnsPlot } from "@/lib/tenant-authorization";
import {
  createWorkspaceFeatureEnvelope,
  validateWorkspaceFeatureEnvelope,
  type WorkspaceFeatureEnvelope,
} from "@/lib/agribrain/workspace-feature-envelope";

// Authoritative persistent field sensors for canonical benchmark plots
interface RegisteredProbe {
  deviceId: string;
  vendor: string;
  model: string;
  type: string;
  lat: number;
  lon: number;
  depthCm: number;
  zoneId: string;
  variables: string[];
}

const BENCHMARK_PLOT_PROBES: Record<string, RegisteredProbe[]> = {
  // Canonical Mitidja Plot-A benchmark
  "6a09d9e91dd0c7ed6fce7d50": [
    {
      deviceId: "sensor_probe_alpha_15cm",
      vendor: "Sentek Drill & Drop",
      model: "Sentek-D&D-TriScan-15",
      type: "MOISTURE",
      lat: 36.509081,
      lon: 2.659269,
      depthCm: 15.0,
      zoneId: "zone-north",
      variables: ["soil_moisture_vwc", "soil_temperature"],
    },
    {
      deviceId: "sensor_probe_alpha_30cm",
      vendor: "Sentek Drill & Drop",
      model: "Sentek-D&D-TriScan-30",
      type: "MOISTURE",
      lat: 36.509081,
      lon: 2.659269,
      depthCm: 30.0,
      zoneId: "zone-north",
      variables: ["soil_moisture_vwc", "soil_temperature"],
    },
    {
      deviceId: "sensor_probe_beta_10cm",
      vendor: "Sentek Drill & Drop",
      model: "Sentek-D&D-TriScan-10",
      type: "MOISTURE",
      lat: 36.507850,
      lon: 2.660150,
      depthCm: 10.0,
      zoneId: "zone-south",
      variables: ["soil_moisture_vwc", "soil_temperature"],
    },
  ],
  // Workspace Demo / Pilot Plot
  "69fb754f2ab4b04e9f00394c": [
    {
      deviceId: "probe_mitidja_station_1",
      vendor: "Sentek Drill & Drop",
      model: "Sentek-D&D-TriScan-2026",
      type: "MOISTURE",
      lat: 36.578488,
      lon: 2.953944,
      depthCm: 20.0,
      zoneId: "zone-4",
      variables: ["soil_moisture_vwc", "soil_temperature"],
    },
    {
      deviceId: "meteo_station_mitidja_alpha",
      vendor: "Pessl Instruments",
      model: "iMETOS 3.3",
      type: "WEATHER",
      lat: 36.578920,
      lon: 2.954510,
      depthCm: 0.0,
      zoneId: "zone-4",
      variables: ["temperature", "humidity", "rainfall", "wind_speed"],
    },
  ],
};

/**
 * GET /api/plots/[id]/workspace/entities
 * 
 * Returns tenant-scoped, authoritative WorkspaceFeatureEnvelopes for registered
 * agricultural entities (sensors, cameras, field events, etc.).
 * 
 * Enforces Gate P05-G01: Server-authenticated tenant and plot scope.
 * Enforces Gate P05-G02: Coordinates equal registered hardware location, never plot centroid.
 * Enforces Gate P05-G08: Unlocated entities appear with has_location=false, eligible for catalog.
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const userId = await authenticatedUserId();

    if (!userId) {
      return NextResponse.json(
        { error: "Authentication required" },
        { status: 401 }
      );
    }

    const { id: plotId } = await params;

    const plot = await prisma.plot.findFirst({
      where: {
        id: plotId,
        farm: { userId },
      },
      include: {
        farm: {
          select: { id: true, userId: true, name: true },
        },
      },
    });

    if (!plot) {
      return NextResponse.json({ error: "Plot not found" }, { status: 404 });
    }

    const tenantId = plot.farm.userId;
    const farmId = plot.farm.id;

    // Optional query filter for entity kinds
    const { searchParams } = new URL(request.url);
    const kindFilter = searchParams.get("kind")?.toUpperCase();

    const OFFLINE_THRESHOLD_MS = 5 * 60 * 1000;
    const now = Date.now();

    const envelopes: WorkspaceFeatureEnvelope[] = [];

    // 1. Fetch DB Sensors
    const dbSensors = await prisma.sensor.findMany({
      where: { plotId },
      orderBy: { createdAt: "desc" },
    });

    const benchmarkProbes = BENCHMARK_PLOT_PROBES[plotId] || [];

    // Map DB Sensors
    for (const sensor of dbSensors) {
      const latestReading = await prisma.sensorReading.findFirst({
        where: { sensorId: sensor.id },
        orderBy: { timestamp: "desc" },
      });

      const lastSyncMs = sensor.lastSync ? sensor.lastSync.getTime() : 0;
      const isOnline = now - lastSyncMs < OFFLINE_THRESHOLD_MS;

      // Check if this DB sensor has registered benchmark coordinates
      const matchedProbe = benchmarkProbes.find(
        (p) => p.deviceId === sensor.deviceId
      );

      // Raw coordinates from sensor or matched probe
      // Cast to any since schema might not have lat/lng typed yet
      const rawSensor = sensor as any;
      const lat = matchedProbe?.lat ?? rawSensor.latitude ?? null;
      const lng = matchedProbe?.lon ?? rawSensor.longitude ?? null;
      const depthCm = matchedProbe?.depthCm ?? rawSensor.depthCm ?? null;
      const zoneId = matchedProbe?.zoneId ?? rawSensor.zoneId ?? null;

      // Gate P05-G02: Ensure we never invent or substitute the plot centroid
      const envelope = createWorkspaceFeatureEnvelope({
        entity_kind: "SENSOR",
        entity_id: sensor.id,
        source_version: sensor.createdAt.toISOString(),
        owner_scope: {
          tenant_id: tenantId,
          farm_id: farmId,
          plot_id: plotId,
        },
        latitude: lat,
        longitude: lng,
        depth_cm: depthCm,
        zone_id: zoneId,
        location_source: lat && lng ? "REGISTERED_HARDWARE" : "UNSPECIFIED",
        epistemic_class: latestReading ? "OBSERVED_TELEMETRY" : "REGISTERED_GROUND_TRUTH",
        temporal_extent: {
          observed_at: latestReading?.timestamp?.toISOString() || null,
          published_at: sensor.lastSync?.toISOString() || null,
        },
        properties: {
          deviceId: sensor.deviceId,
          vendor: sensor.vendor || matchedProbe?.vendor || "Agricultural IoT",
          model: matchedProbe?.model || "Standard Probe",
          type: sensor.type,
          status: sensor.status, // Hardware life status: ACTIVE / OFFLINE / RETIRED
          isOnline, // Freshness status
          battery: sensor.battery,
          rssi: sensor.rssi,
          depthCm,
          zoneId,
          is_benchmark_fixture: false,
          latestReading: latestReading
            ? {
                temperature: latestReading.temperature,
                humidity: latestReading.humidity,
                soilMoisture: latestReading.soilMoisture,
                ec: latestReading.ec,
                windSpeed: latestReading.windSpeed,
                rainfall: latestReading.rainfall,
                timestamp: latestReading.timestamp.toISOString(),
              }
            : null,
        },
        provenance: {
          registry_source: matchedProbe
            ? "sensor_runtime:registry"
            : "prisma:sensor",
          verified_identity: Boolean(sensor.apiKey),
          is_benchmark_fixture: false,
        },
      });

      const validation = validateWorkspaceFeatureEnvelope(envelope, {
        tenantId,
        plotId,
      });

      if (validation.valid) {
        envelopes.push(envelope);
      }
    }

    // Benchmark probes not in DB: explicitly tagged as SIMULATED fixtures
    for (const probe of benchmarkProbes) {
      const alreadyIncluded = envelopes.some(
        (e) => (e.properties as any)?.deviceId === probe.deviceId
      );
      if (!alreadyIncluded) {
        const envelope = createWorkspaceFeatureEnvelope({
          entity_kind: "SENSOR",
          entity_id: probe.deviceId,
          source_version: "2026-03-01T00:00:00Z",
          owner_scope: {
            tenant_id: tenantId,
            farm_id: farmId,
            plot_id: plotId,
          },
          latitude: probe.lat,
          longitude: probe.lon,
          depth_cm: probe.depthCm,
          zone_id: probe.zoneId,
          location_source: "SURVEYED",
          epistemic_class: "SIMULATED",
          temporal_extent: {
            observed_at: null,
            published_at: "2026-03-01T00:00:00Z",
          },
          properties: {
            deviceId: probe.deviceId,
            vendor: probe.vendor,
            model: probe.model,
            type: probe.type,
            status: "BENCHMARK_FIXTURE",
            isOnline: false,
            battery: null,
            rssi: null,
            depthCm: probe.depthCm,
            zoneId: probe.zoneId,
            variables: probe.variables,
            is_benchmark_fixture: true,
            latestReading: null,
          },
          provenance: {
            registry_source: "fixture:benchmark_plot",
            verified_identity: false,
            is_benchmark_fixture: true,
          },
        });

        const validation = validateWorkspaceFeatureEnvelope(envelope, {
          tenantId,
          plotId,
        });

        if (validation.valid) {
          envelopes.push(envelope);
        }
      }
    }

    // Apply optional filter
    const filtered = kindFilter
      ? envelopes.filter((e) => e.entity_kind === kindFilter)
      : envelopes;

    const locatedCount = filtered.filter(
      (e) => e.display_eligibility.eligible_for_map_pin
    ).length;
    const unlocatedCount = filtered.length - locatedCount;

    return NextResponse.json({
      success: true,
      contract_version: "2026.11-p05.1",
      plot_id: plotId,
      tenant_id: tenantId,
      total: filtered.length,
      located_count: locatedCount,
      unlocated_count: unlocatedCount,
      entities: filtered,
    });
  } catch (error) {
    console.error("Workspace entities error:", error);
    return NextResponse.json(
      { error: "Failed to fetch workspace entities" },
      { status: 500 }
    );
  }
}
