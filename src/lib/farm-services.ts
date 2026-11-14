import { prisma } from "@/lib/prisma";
import { ObjectId } from "bson";
import { cache } from "react";
import { getPlotRepresentativePoint, isValidWgs84Point } from "@/lib/agribrain/plot-geometry";
import { getSession } from "@/lib/session";
import { activeCropCyclePrismaFilter } from "@/lib/agribrain/crop-cycle-status.mjs";
import { computeGeometryHash } from "@/lib/agribrain/parcel-assessment-contract";

function ownerScope(userId: string) {
  return { farm: { userId } };
}

async function currentOwnerId(): Promise<string | null> {
  const session = await getSession();
  if (session?.userId) return session.userId;
  return null;
}

function mapPlot(plot: any) {
  return {
    id: plot.id,
    name: plot.name,
    nameAr: plot.nameAr,
    area: plot.area,
    soilType: plot.soilType,
    irrigation: plot.irrigation,
    farmId: plot.farmId,
    geoJson: plot.geoJson,
    geometryHash: plot.geometryHash || (plot.geoJson ? computeGeometryHash(plot.geoJson) : null),
    geometryVersion: plot.geometryVersion ?? null,
    perimeter: plot.perimeter,
    ownership: plot.ownership,
    irrigationDistrict: plot.irrigationDistrict,
    physicalConstraints: plot.physicalConstraints,
    photos: plot.photos || [],
    cameras: plot.cameras || [],
    soilAnalyses: plot.soilAnalyses || [],
    sensors: plot.sensors || [],
  };
}

function mapFarm(farm: any) {
  return {
    id: farm.id,
    userId: farm.userId || null,
    ownerId: farm.userId || null,
    name: farm.name,
    nameAr: farm.nameAr,
    wilaya: farm.wilaya,
    latitude: farm.latitude,
    longitude: farm.longitude,
    totalArea: farm.totalArea,
  };
}

function mapCropCycle(cycle: any) {
  return {
    id: cycle.id,
    cropCode: cycle.cropCode,
    cropNameAr: cycle.cropNameAr,
    variety: cycle.variety,
    status: cycle.status,
    startDate: cycle.plantDate,
  };
}

/** Resolve a plot page through one ownership-scoped relational query. */
export const getAuthorizedPlotRouteContext = cache(
  async (plotId: string, farmId: string) => {
    if (!ObjectId.isValid(plotId) || !ObjectId.isValid(farmId)) return null;

    // Owner scope is required in every environment, including local development.
    // The local-only dev-session endpoint must establish a verified session first.
    const ownerId = await currentOwnerId();
    if (!ownerId) return null;

    const plot = await prisma.plot.findFirst({
      where: {
        id: plotId,
        farmId,
        ...ownerScope(ownerId),
      },
      include: {
        farm: true,
        cropCycles: {
          where: { status: activeCropCyclePrismaFilter() },
          orderBy: { updatedAt: "desc" },
        },
        photos: true,
        cameras: true,
        soilAnalyses: { orderBy: { date: "desc" } },
        sensors: true,
      },
    });

    if (!plot?.farm || plot.farm.id !== farmId) return null;
    return {
      plot: mapPlot(plot),
      farm: mapFarm(plot.farm),
      cropCycles: (plot.cropCycles || []).map(mapCropCycle),
    };
  },
);

// Wrap with React cache() for request-level deduplication.
// Layout and child pages fetch the same data — without cache(),
// they make separate Prisma calls that race and can exhaust connections.
export const getPlot = cache(async (id: string) => {
  try {
    if (!ObjectId.isValid(id) || id.match(/\.(png|jpg|jpeg|gif|ico|svg)$/)) return null;

    const ownerId = await currentOwnerId();
    if (!ownerId) return null;
    const plot = await prisma.plot.findFirst({
      where: { id, ...ownerScope(ownerId) },
      include: { photos: true, cameras: true, soilAnalyses: { orderBy: { date: 'desc' } }, sensors: true }
    });

    if (!plot) return null;
    return mapPlot(plot);
  } catch (error) {
    console.error("getPlot error:", error);
    return null;
  }
});

export const getCropCycles = cache(async (plotId: string) => {
  // Prevent Prisma crash on image requests or invalid IDs
  if (plotId.includes('.') || plotId.length < 15) return [];

  try {
    const ownerId = await currentOwnerId();
    if (!ownerId) return [];
    const authorizedPlot = await prisma.plot.findFirst({
      where: { id: plotId, ...ownerScope(ownerId) },
      select: { id: true },
    });
    if (!authorizedPlot) return [];

    const cycles = await prisma.cropCycle.findMany({
      where: { plotId },
      orderBy: { plantDate: 'desc' }
    });
    
    return cycles.map(mapCropCycle);
  } catch (error) {
    console.error("getCropCycles error:", error);
    return [];
  }
});

export const getFarm = cache(async (id: string) => {
  try {
    if (!ObjectId.isValid(id)) return null;

    const ownerId = await currentOwnerId();
    if (!ownerId) return null;
    const farm = await prisma.farm.findFirst({
      where: { id, userId: ownerId },
    });

    if (!farm) return null;
    return mapFarm(farm);
  } catch (error) {
    console.error("getFarm error:", error);
    return null;
  }
});

export function getPlotCenter(plot: any, farm: any) {
    const farmPoint = { lat: Number(farm?.latitude), lng: Number(farm?.longitude) };
    return getPlotRepresentativePoint(
      plot?.geoJson,
      isValidWgs84Point(farmPoint) ? farmPoint : undefined,
    );
  }
