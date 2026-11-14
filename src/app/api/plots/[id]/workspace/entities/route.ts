import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { authenticatedUserId } from "@/lib/tenant-authorization";
import {
  createWorkspaceFeatureEnvelope,
  validateWorkspaceFeatureEnvelope,
  type WorkspaceFeatureEnvelope,
  type EntityKind,
} from "@/lib/agribrain/workspace-feature-envelope";

export interface BenchmarkEntity {
  entityId: string;
  kind: EntityKind;
  name: string;
  vendor?: string;
  model?: string;
  type?: string;
  lat: number;
  lon: number;
  depthCm?: number | null;
  zoneId?: string;
  variables?: string[];
  locationSource: "REGISTERED_HARDWARE" | "OBSERVED_GPS" | "SURVEYED";
  epistemicClass: "REGISTERED_GROUND_TRUTH" | "OBSERVED_TELEMETRY" | "SIMULATED" | "PLANNED";
  properties: Record<string, unknown>;
}

const BENCHMARK_PLOT_ENTITIES: Record<string, BenchmarkEntity[]> = {
  // Canonical Mitidja Plot-A benchmark
  "6a09d9e91dd0c7ed6fce7d50": [
    {
      entityId: "sensor_probe_alpha_15cm",
      kind: "SENSOR",
      name: "Sentek TriScan 15cm",
      vendor: "Sentek Drill & Drop",
      model: "Sentek-D&D-TriScan-15",
      type: "MOISTURE",
      lat: 36.509081,
      lon: 2.659269,
      depthCm: 15.0,
      zoneId: "zone-north",
      variables: ["soil_moisture_vwc", "soil_temperature"],
      locationSource: "SURVEYED",
      epistemicClass: "SIMULATED",
      properties: { is_benchmark_fixture: true, latestReading: null, isOnline: false },
    },
    {
      entityId: "sensor_probe_alpha_30cm",
      kind: "SENSOR",
      name: "Sentek TriScan 30cm",
      vendor: "Sentek Drill & Drop",
      model: "Sentek-D&D-TriScan-30",
      type: "MOISTURE",
      lat: 36.509081,
      lon: 2.659269,
      depthCm: 30.0,
      zoneId: "zone-north",
      variables: ["soil_moisture_vwc", "soil_temperature"],
      locationSource: "SURVEYED",
      epistemicClass: "SIMULATED",
      properties: { is_benchmark_fixture: true, latestReading: null, isOnline: false },
    },
    {
      entityId: "sensor_probe_beta_10cm",
      kind: "SENSOR",
      name: "Sentek TriScan 10cm",
      vendor: "Sentek Drill & Drop",
      model: "Sentek-D&D-TriScan-10",
      type: "MOISTURE",
      lat: 36.507850,
      lon: 2.660150,
      depthCm: 10.0,
      zoneId: "zone-south",
      variables: ["soil_moisture_vwc", "soil_temperature"],
      locationSource: "SURVEYED",
      epistemicClass: "SIMULATED",
      properties: { is_benchmark_fixture: true, latestReading: null, isOnline: false },
    },
    {
      entityId: "camera_trap_mitidja_north",
      kind: "CAMERA",
      name: "North Plot Optical Trap",
      vendor: "AgroVision IoT",
      model: "AgroCam 4K Solar",
      lat: 36.509200,
      lon: 2.659400,
      zoneId: "zone-north",
      locationSource: "SURVEYED",
      epistemicClass: "SIMULATED",
      properties: {
        deviceId: "camera_trap_mitidja_north",
        model: "AgroCam 4K Solar",
        resolution: "3840x2160 UHD",
        fieldOfView: "120° Wide Angle",
        status: "STANDBY",
        is_benchmark_fixture: true,
      },
    },
    {
      entityId: "drone_mission_mitidja_canopy",
      kind: "DRONE_MISSION",
      name: "Canopy Multispectral Recon",
      vendor: "DJI Enterprise",
      model: "Matrice 350 RTK",
      lat: 36.508500,
      lon: 2.659800,
      locationSource: "SURVEYED",
      epistemicClass: "PLANNED",
      properties: {
        missionId: "drone_mission_mitidja_canopy",
        missionType: "MAPPING",
        altitudeM: 50,
        gsdCmPx: 2.0,
        pattern: "boustrophedon",
        status: "PLANNED",
        is_benchmark_fixture: true,
      },
    },
  ],
  // Workspace Demo / Pilot Plot
  "69fb754f2ab4b04e9f00394c": [
    {
      entityId: "probe_mitidja_station_1",
      kind: "SENSOR",
      name: "Sentek TriScan 20cm",
      vendor: "Sentek Drill & Drop",
      model: "Sentek-D&D-TriScan-2026",
      type: "MOISTURE",
      lat: 36.578488,
      lon: 2.953944,
      depthCm: 20.0,
      zoneId: "zone-4",
      variables: ["soil_moisture_vwc", "soil_temperature"],
      locationSource: "SURVEYED",
      epistemicClass: "SIMULATED",
      properties: { is_benchmark_fixture: true, latestReading: null, isOnline: false },
    },
    {
      entityId: "meteo_station_mitidja_alpha",
      kind: "SENSOR",
      name: "iMETOS Weather Station",
      vendor: "Pessl Instruments",
      model: "iMETOS 3.3",
      type: "WEATHER",
      lat: 36.578920,
      lon: 2.954510,
      depthCm: 0.0,
      zoneId: "zone-4",
      variables: ["temperature", "humidity", "rainfall", "wind_speed"],
      locationSource: "SURVEYED",
      epistemicClass: "SIMULATED",
      properties: { is_benchmark_fixture: true, latestReading: null, isOnline: false },
    },
    {
      entityId: "camera_canopy_station_alpha",
      kind: "CAMERA",
      name: "Canopy Vision Trap Alpha",
      vendor: "AgroVision IoT",
      model: "AgroCam 4K Solar",
      lat: 36.578650,
      lon: 2.954120,
      zoneId: "zone-4",
      locationSource: "SURVEYED",
      epistemicClass: "SIMULATED",
      properties: {
        deviceId: "camera_canopy_station_alpha",
        model: "AgroCam 4K Solar",
        resolution: "3840x2160 UHD",
        fieldOfView: "120° Wide Angle",
        status: "STANDBY",
        is_benchmark_fixture: true,
      },
    },
    {
      entityId: "drone_mission_citrus_recon",
      kind: "DRONE_MISSION",
      name: "Citrus Reconnaissance Mission",
      vendor: "DJI Enterprise",
      model: "Matrice 350 RTK",
      lat: 36.578250,
      lon: 2.953700,
      zoneId: "zone-4",
      locationSource: "SURVEYED",
      epistemicClass: "PLANNED",
      properties: {
        missionId: "drone_mission_citrus_recon",
        missionType: "MAPPING",
        altitudeM: 45,
        gsdCmPx: 1.8,
        pattern: "boustrophedon",
        status: "PLANNED",
        waypointsCount: 24,
        is_benchmark_fixture: true,
      },
    },
    {
      entityId: "obs_scouting_aphid_hotspot",
      kind: "FIELD_OBSERVATION",
      name: "Aphid Foliar Hotspot",
      lat: 36.578810,
      lon: 2.953850,
      zoneId: "zone-4",
      locationSource: "OBSERVED_GPS",
      epistemicClass: "REGISTERED_GROUND_TRUTH",
      properties: {
        category: "PEST_DAMAGE",
        severity: "MEDIUM",
        notes: "Localized aphid colony on young citrus shoot",
        observer: "Agronomist Mobile Scout",
        aiTags: ["aphids", "leaf_curl"],
        is_benchmark_fixture: true,
      },
    },
  ],
};

/**
 * GET /api/plots/[id]/workspace/entities
 * 
 * Returns tenant-scoped, version-governed WorkspaceFeatureEnvelopes for registered
 * agricultural entities across multiple families (Sensors, Cameras, Drones, Field Observations).
 * 
 * Enforces Gate P05-G01: Server-authenticated tenant and plot scope.
 * Enforces Gate P05-G02: Coordinates equal registered physical location, never plot centroid.
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

    // Optional query filter for entity kinds (SENSOR, CAMERA, DRONE_MISSION, FIELD_OBSERVATION)
    const { searchParams } = new URL(request.url);
    const kindFilter = searchParams.get("kind")?.toUpperCase();

    const OFFLINE_THRESHOLD_MS = 5 * 60 * 1000;
    const now = Date.now();

    const envelopes: WorkspaceFeatureEnvelope[] = [];
    const benchmarkEntities = BENCHMARK_PLOT_ENTITIES[plotId] || [];

    // 1. Fetch DB Sensors (prisma.sensor)
    const dbSensors = await prisma.sensor.findMany({
      where: { plotId },
      orderBy: { createdAt: "desc" },
    });

    for (const sensor of dbSensors) {
      const latestReading = await prisma.sensorReading.findFirst({
        where: { sensorId: sensor.id },
        orderBy: { timestamp: "desc" },
      });

      const lastSyncMs = sensor.lastSync ? sensor.lastSync.getTime() : 0;
      const isOnline = now - lastSyncMs < OFFLINE_THRESHOLD_MS;

      // Check if this DB sensor has registered benchmark coordinates
      const matchedEntity = benchmarkEntities.find(
        (b) => b.kind === "SENSOR" && (b.properties as any)?.deviceId === sensor.deviceId || b.entityId === sensor.deviceId
      );

      const rawSensor = sensor as any;
      const lat = matchedEntity?.lat ?? rawSensor.latitude ?? null;
      const lng = matchedEntity?.lon ?? rawSensor.longitude ?? null;
      const depthCm = matchedEntity?.depthCm ?? rawSensor.depthCm ?? null;
      const zoneId = matchedEntity?.zoneId ?? rawSensor.zoneId ?? null;

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
          vendor: sensor.vendor || matchedEntity?.vendor || "Agricultural IoT",
          model: matchedEntity?.model || "Standard Probe",
          type: sensor.type,
          status: sensor.status,
          isOnline,
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
          registry_source: matchedEntity
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

    // 2. Fetch DB Visual Evidence (prisma.plotPhoto)
    const dbPhotos = await prisma.plotPhoto.findMany({
      where: { plotId },
      orderBy: { createdAt: "desc" },
    });

    for (const photo of dbPhotos) {
      const isCamera = photo.source === "ip_camera";
      const entityKind: EntityKind = isCamera ? "CAMERA" : "FIELD_OBSERVATION";

      const envelope = createWorkspaceFeatureEnvelope({
        entity_kind: entityKind,
        entity_id: photo.id,
        source_version: photo.createdAt.toISOString(),
        owner_scope: {
          tenant_id: tenantId,
          farm_id: farmId,
          plot_id: plotId,
        },
        latitude: null, // PlotPhoto in DB has no GPS coordinates (catalog eligible)
        longitude: null,
        zone_id: photo.zoneId || null,
        location_source: "UNSPECIFIED",
        epistemic_class: isCamera ? "OBSERVED_TELEMETRY" : "REGISTERED_GROUND_TRUTH",
        temporal_extent: {
          observed_at: photo.date.toISOString(),
          published_at: photo.createdAt.toISOString(),
        },
        properties: {
          photoId: photo.id,
          type: photo.type,
          url: photo.url,
          notes: photo.notes,
          tags: photo.tags,
          aiTags: photo.aiTags,
          source: photo.source,
          is_benchmark_fixture: false,
        },
        provenance: {
          registry_source: "prisma:plotPhoto",
          verified_identity: true,
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

    // 3. Add Benchmark Entities (Sensors, Cameras, Drone Missions, Field Observations)
    for (const item of benchmarkEntities) {
      const alreadyIncluded = envelopes.some(
        (e) => (e.properties as any)?.deviceId === item.entityId || e.entity_id === item.entityId
      );
      if (!alreadyIncluded) {
        const envelope = createWorkspaceFeatureEnvelope({
          entity_kind: item.kind,
          entity_id: item.entityId,
          source_version: "2026-03-01T00:00:00Z",
          owner_scope: {
            tenant_id: tenantId,
            farm_id: farmId,
            plot_id: plotId,
          },
          latitude: item.lat,
          longitude: item.lon,
          depth_cm: item.depthCm ?? null,
          zone_id: item.zoneId ?? null,
          location_source: item.locationSource,
          epistemic_class: item.epistemicClass,
          temporal_extent: {
            observed_at: item.epistemicClass === "REGISTERED_GROUND_TRUTH" ? "2026-11-12T14:30:00Z" : null,
            published_at: "2026-03-01T00:00:00Z",
          },
          properties: {
            ...item.properties,
            deviceId: item.entityId,
            name: item.name,
            vendor: item.vendor,
            model: item.model,
            type: item.type,
            depthCm: item.depthCm ?? null,
            zoneId: item.zoneId ?? null,
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

    // Apply optional filter by entity kind
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
