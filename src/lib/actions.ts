'use server';

import { prisma } from "@/lib/prisma";
import { revalidatePath } from "next/cache";
import { authorizePlot } from "@/lib/agribrain/authorize-plot";
import { authenticatedUserId } from "@/lib/tenant-authorization";
import { isValidWgs84Point } from "@/lib/agribrain/plot-geometry";

export async function updatePlotDetails(plotId: string, data: {
  name?: string;
  perimeter?: number;
  ownership?: string;
  irrigationDistrict?: string;
  physicalConstraints?: string[];
}) {
  try {
    const access = await authorizePlot(plotId);
    if (!access.plot) return { success: false, error: "Plot not found" };
    // Build update data with explicit field whitelist
    const updateData: Record<string, unknown> = {};
    if (data.name !== undefined) updateData.name = data.name;
    if (data.perimeter !== undefined && !isNaN(data.perimeter)) updateData.perimeter = data.perimeter;
    if (data.ownership !== undefined) updateData.ownership = data.ownership;
    if (data.irrigationDistrict !== undefined) updateData.irrigationDistrict = data.irrigationDistrict;
    if (data.physicalConstraints !== undefined) updateData.physicalConstraints = data.physicalConstraints;

    // Use Prisma ORM — not raw MongoDB commands
    const plot = await prisma.plot.findFirst({
      where: { id: plotId, farmId: access.plot.farmId },
    });
    if (!plot) {
      return { success: false, error: `Plot not found. ID: ${plotId}` };
    }

    await prisma.plot.update({
      where: { id: plotId },
      data: updateData,
    });

    revalidatePath(`/farm/${plot.farmId}/plot/${plotId}`);
    revalidatePath(`/farm/${plot.farmId}/plot/${plotId}/user-inputs`);
    return { success: true };
  } catch (error) {
    console.error("Failed to update plot details:", error);
    const message = error instanceof Error ? error.message : "Failed to update plot details";
    return { success: false, error: message };
  }
}

export async function addPlotPhoto(plotId: string, data: {
  url: string;
  type: 'CROP' | 'SOIL' | 'OVERVIEW' | 'DAMAGE' | 'SATELLITE' | 'OTHER';
  tags?: string[];
  notes?: string;
  date: Date;
  source?: string;
  aiTags?: string[];
  aiConfidence?: number;
}) {
    try {
        const access = await authorizePlot(plotId);
        if (!access.plot) return { success: false, error: "Plot not found" };
        const photo = await prisma.plotPhoto.create({
            data: {
                plotId,
                url: data.url,
                type: data.type,
                tags: data.tags || [],
                notes: data.notes,
                date: data.date,
                source: "farmer",
                aiTags: (data.aiTags || []).filter((tag) => typeof tag === "string").slice(0, 10),
                aiConfidence: 0.0,
            }
        });
        // Look up farmId for correct cache revalidation
        const plot = await prisma.plot.findUnique({ where: { id: plotId }, select: { farmId: true } });
        if (plot) {
          revalidatePath(`/farm/${plot.farmId}/plot/${plotId}/user-inputs`);
        }
        return { success: true, data: photo };
    } catch (error) {
        console.error("Failed to add plot photo:", error);
        return { success: false, error: "Failed to add plot photo" };
    }
}

export async function deletePlotPhoto(photoId: string) {
    try {
        const userId = await authenticatedUserId();
        if (!userId) return { success: false, error: "Authentication required" };
        const ownedPhoto = await prisma.plotPhoto.findFirst({
          where: { id: photoId, plot: { farm: { userId } } },
          select: { id: true, plotId: true },
        });
        if (!ownedPhoto) return { success: false, error: "Photo not found" };
        const photo = await prisma.plotPhoto.delete({
            where: { id: ownedPhoto.id }
        });
        // Look up farmId for correct cache revalidation
        const plot = await prisma.plot.findUnique({ where: { id: photo.plotId }, select: { farmId: true } });
        if (plot) {
          revalidatePath(`/farm/${plot.farmId}/plot/${photo.plotId}/user-inputs`);
        }
        return { success: true };
    } catch (error) {
        console.error("Failed to delete plot photo:", error);
        return { success: false, error: "Failed to delete photo" };
    }
}

export async function addIPCamera(plotId: string, data: {
    name: string;
    url: string;
    type: 'FIXED' | 'PTZ' | 'DRONE_FEED';
}) {
    try {
        const access = await authorizePlot(plotId);
        if (!access.plot) return { success: false, error: "Plot not found" };
        const camera = await prisma.iPCamera.create({
            data: {
                plotId,
                name: data.name,
                url: data.url,
                type: data.type,
                status: 'OFFLINE'
            }
        });
        return { success: true, data: camera };
    } catch (error) {
         console.error("Failed to add IP camera:", error);
        return { success: false, error: "Failed to add IP camera" };
    }
}

export async function deleteIPCamera(plotId: string, cameraId: string) {
    try {
        const userId = await authenticatedUserId();
        if (!userId) return { success: false, error: "Authentication required" };
        const camera = await prisma.iPCamera.findFirst({
          where: { id: cameraId, plotId, plot: { farm: { userId } } },
          select: { id: true },
        });
        if (!camera) return { success: false, error: "Camera not found" };
        await prisma.iPCamera.delete({
            where: { id: camera.id }
        });
        // Look up farmId for correct cache revalidation
        const plot = await prisma.plot.findUnique({ where: { id: plotId }, select: { farmId: true } });
        if (plot) {
          revalidatePath(`/farm/${plot.farmId}/plot/${plotId}/user-inputs`);
        }
        return { success: true };
    } catch (error) {
        console.error("Failed to delete IP camera:", error);
        return { success: false, error: "Failed to delete IP camera" };
    }
}



export async function toggleIPCameraStatus(plotId: string, cameraId: string, currentStatus: string) {
    try {
        const userId = await authenticatedUserId();
        if (!userId) return { success: false, error: "Authentication required" };
        const camera = await prisma.iPCamera.findFirst({
          where: { id: cameraId, plotId, plot: { farm: { userId } } },
          select: { id: true, status: true },
        });
        if (!camera) return { success: false, error: "Camera not found" };
        const newStatus = camera.status === 'ACTIVE' ? 'OFFLINE' : 'ACTIVE';
        await prisma.iPCamera.update({
            where: { id: camera.id },
            data: { status: newStatus }
        });
        // Look up farmId for correct cache revalidation
        const plot = await prisma.plot.findUnique({ where: { id: plotId }, select: { farmId: true } });
        if (plot) {
          revalidatePath(`/farm/${plot.farmId}/plot/${plotId}/user-inputs`);
        }
        return { success: true, newStatus };
    } catch (error) {
        console.error("Failed to toggle camera status:", error);
        return { success: false, error: "Failed to toggle status" };
    }
}

export async function addSoilAnalysis(plotId: string, data: {
    date?: Date;
    fileUrl?: string;
    depthFrom?: number;
    depthTo?: number;
    samplingLocation?: string;
    notes?: string;
    ph?: number;
    ec?: number;
    organicMatter?: number;
    nitrogen?: number;
    phosphorus?: number;
    potassium?: number;
    texture?: string;
}) {
    try {
        const access = await authorizePlot(plotId);
        if (!access.plot) return { success: false, error: "Plot not found" };
        // Explicit field whitelist — never spread raw user data into Prisma
        const analysis = await prisma.soilAnalysis.create({
            data: {
                plotId,
                date: data.date || new Date(),
                fileUrl: data.fileUrl,
                depthFrom: data.depthFrom,
                depthTo: data.depthTo,
                samplingLocation: data.samplingLocation,
                notes: data.notes,
                ph: data.ph,
                ec: data.ec,
                organicMatter: data.organicMatter,
                nitrogen: data.nitrogen,
                phosphorus: data.phosphorus,
                potassium: data.potassium,
                texture: data.texture,
            }
        });
        return { success: true, data: analysis };
    } catch (error) {
         console.error("Failed to add soil analysis:", error);
        return { success: false, error: "Failed to add soil analysis" };
    }
}

export async function addSensor(plotId: string, data: {
    deviceId: string;
    type: 'MOISTURE' | 'TEMP' | 'EC' | 'WEATHER' | 'OTHER';
    vendor?: string;
}) {
    try {
        const access = await authorizePlot(plotId);
        if (!access.plot) return { success: false, error: "Plot not found" };
        const sensor = await prisma.sensor.create({
            data: {
                plotId,
                deviceId: data.deviceId,
                type: data.type,
                vendor: data.vendor,
                status: 'ACTIVE'
            }
        });
        return { success: true, data: sensor };
    } catch (error) {
        console.error("Failed to add sensor:", error);
        return { success: false, error: "Failed to add sensor" };
    }
}

// ============================================================================
// SERVER ACTIONS FOR SATELLITE & LAND INTELLIGENCE DATA
// ============================================================================

import { fetchOneSoilData } from "@/lib/onesoil-service";
import { fetchSatelliteData, getAvailableProviders } from "@/lib/satellite-providers";
import { getFAOLandIntelligence } from "@/lib/agribrain/fao-data-service";
import type { SatelliteProvider } from "@/lib/satellite-providers";

export type { OneSoilProfile, SatelliteLayer } from "@/lib/onesoil-service";
export type { SatelliteProvider, ProviderInfo } from "@/lib/satellite-providers";
export type { FAOIntelligenceProfile } from "@/lib/agribrain/fao-data-service";

export async function fetchOneSoilDataAction(lat: number, lng: number, cropCode: string) {
  if (!(await authenticatedUserId())) throw new Error("Authentication required");
  if (!isValidWgs84Point({ lat: Number(lat), lng: Number(lng) })) throw new Error("Invalid location");
  return await fetchOneSoilData(lat, lng, cropCode);
}

export async function fetchSatelliteDataAction(
  provider: SatelliteProvider,
  lat: number,
  lng: number,
  cropCode: string
) {
  if (!(await authenticatedUserId())) throw new Error("Authentication required");
  if (!isValidWgs84Point({ lat: Number(lat), lng: Number(lng) })) throw new Error("Invalid location");
  return await fetchSatelliteData(provider, lat, lng, cropCode);
}

export async function getAvailableProvidersAction() {
  if (!(await authenticatedUserId())) throw new Error("Authentication required");
  return await getAvailableProviders();
}

export async function getFAOLandIntelligenceAction(
  latitude: number,
  longitude: number,
  cropCode: string,
  plotId?: string
) {
  if (!(await authenticatedUserId())) throw new Error("Authentication required");
  if (!isValidWgs84Point({ lat: Number(latitude), lng: Number(longitude) })) throw new Error("Invalid location");
  if (plotId) {
    const access = await authorizePlot(plotId);
    if (!access.plot) throw new Error("Plot not found");
  }
  return await getFAOLandIntelligence(latitude, longitude, cropCode, plotId);
}
