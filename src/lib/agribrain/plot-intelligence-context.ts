import { prisma } from "@/lib/db";
import { getAuthoritativePlotSpatialContext } from "@/lib/agribrain/plot-geometry";
import { activeCropCyclePrismaFilter } from "@/lib/agribrain/crop-cycle-status.mjs";

export interface PlotIntelligenceContext {
  lat: number;
  lng: number;
  crop: string;
  polygon: unknown | null;
  plant_date: string | null;
  crop_administrative_status: string | null;
  irrigation_type: string | null;
  soil_type: string | null;
  soil_analysis: Record<string, unknown> | null;
  physical_constraints: string[];
  area_ha: number | null;
  sensor_readings: Record<string, unknown>[];
}

export type PlotIntelligenceContextResult =
  | { context: PlotIntelligenceContext; error: null }
  | { context: null; error: "plot_not_found" | "missing_authoritative_location" };

/** Load an exact plot/farm pair and construct the upstream scientific context. */
export async function loadPlotIntelligenceContext(
  plotId: string,
  farmId: string,
): Promise<PlotIntelligenceContextResult> {
  const plot = await prisma.plot.findFirst({
    where: { id: plotId, farmId },
    include: {
      farm: true,
      cropCycles: {
        where: { status: activeCropCyclePrismaFilter() },
        orderBy: { updatedAt: "desc" },
        take: 1,
      },
      soilAnalyses: {
        orderBy: { date: "desc" },
        take: 1,
      },
      sensors: {
        include: {
          readings: {
            orderBy: { timestamp: "desc" },
            take: 5,
          },
        },
      },
    },
  });
  if (!plot) return { context: null, error: "plot_not_found" };

  const spatial = getAuthoritativePlotSpatialContext(
    plot.geoJson,
    plot.farm?.latitude,
    plot.farm?.longitude,
  );
  if (!spatial) {
    return { context: null, error: "missing_authoritative_location" };
  }

  const cycle = plot.cropCycles?.[0];
  const soil = plot.soilAnalyses?.[0];
  const sensorReadings: Record<string, unknown>[] = [];
  for (const sensor of plot.sensors || []) {
    const latest = sensor.readings?.[0];
    if (!latest) continue;
    sensorReadings.push({
      device_id: sensor.deviceId,
      type: sensor.type,
      vendor: sensor.vendor || null,
      status: sensor.status,
      battery: sensor.battery ?? null,
      rssi: sensor.rssi ?? null,
      last_sync: sensor.lastSync ? new Date(sensor.lastSync).toISOString() : null,
      latest: {
        temperature: latest.temperature ?? null,
        humidity: latest.humidity ?? null,
        soil_moisture: latest.soilMoisture ?? null,
        ec: latest.ec ?? null,
        wind_speed: latest.windSpeed ?? null,
        rainfall: latest.rainfall ?? null,
        timestamp: new Date(latest.timestamp).toISOString(),
      },
    });
  }

  return {
    error: null,
    context: {
      lat: spatial.lat,
      lng: spatial.lng,
      crop: cycle?.cropCode || "generic",
      polygon: spatial.polygon,
      plant_date: cycle?.plantDate
        ? new Date(cycle.plantDate).toISOString().split("T")[0]
        : null,
      crop_administrative_status: cycle?.status || null,
      irrigation_type: plot.irrigation || null,
      soil_type: plot.soilType || null,
      soil_analysis: soil
        ? {
            ph: soil.ph ?? null,
            organic_matter_pct: soil.organicMatter ?? null,
            nitrogen_ppm: soil.nitrogen ?? null,
            phosphorus_ppm: soil.phosphorus ?? null,
            potassium_ppm: soil.potassium ?? null,
            ec_ds_m: soil.ec ?? null,
            sample_date: soil.date
              ? new Date(soil.date).toISOString().split("T")[0]
              : null,
          }
        : null,
      physical_constraints: Array.isArray(plot.physicalConstraints)
        ? plot.physicalConstraints
        : [],
      area_ha: plot.area ?? null,
      sensor_readings: sensorReadings,
    },
  };
}
