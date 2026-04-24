'use server';

import { prisma } from "@/lib/prisma";
import { revalidatePath } from "next/cache";

export async function updatePlotDetails(plotId: string, data: {
  name?: string;
  perimeter?: number;
  ownership?: string;
  irrigationDistrict?: string;
  physicalConstraints?: string[];
}) {
  try {
    // Build update data explicitly
    const updateData: Record<string, unknown> = {};
    if (data.name !== undefined) updateData.name = data.name;
    if (data.perimeter !== undefined && !isNaN(data.perimeter)) updateData.perimeter = data.perimeter;
    if (data.ownership !== undefined) updateData.ownership = data.ownership;
    if (data.irrigationDistrict !== undefined) updateData.irrigationDistrict = data.irrigationDistrict;
    if (data.physicalConstraints !== undefined) updateData.physicalConstraints = data.physicalConstraints;

    console.log("[updatePlotDetails] plotId:", plotId, "data:", JSON.stringify(updateData));

    // Replicate the exact getPlot pattern that works for page load
    const allPlots = await prisma.plot.findMany({});
    const plot = allPlots.find(p => p.id === plotId);
    
    if (!plot) {
      // Log all available IDs for debugging
      console.log("[updatePlotDetails] Plot not found. Available IDs:", allPlots.map(p => p.id));
      return { success: false, error: `Plot not found. ID: ${plotId}` };
    }

    console.log("[updatePlotDetails] Found plot via findMany, id:", plot.id, "farmId:", plot.farmId);

    // Diagnose: try raw find on different collection names to find the right one
    let collectionName = "Plot";
    let rawFind = await prisma.$runCommandRaw({
      find: collectionName,
      filter: { _id: { $oid: plot.id } },
      limit: 1
    }) as { cursor?: { firstBatch?: unknown[] } };

    console.log("[updatePlotDetails] Raw find on 'Plot' with $oid:", JSON.stringify(rawFind?.cursor?.firstBatch?.length));

    // If not found with $oid, try as string
    if (!rawFind?.cursor?.firstBatch?.length) {
      rawFind = await prisma.$runCommandRaw({
        find: collectionName,
        filter: { _id: plot.id },
        limit: 1
      }) as typeof rawFind;
      console.log("[updatePlotDetails] Raw find on 'Plot' with string ID:", JSON.stringify(rawFind?.cursor?.firstBatch?.length));
    }

    // If still not found, try collection "plot" (lowercase)
    if (!rawFind?.cursor?.firstBatch?.length) {
      collectionName = "plot";
      rawFind = await prisma.$runCommandRaw({
        find: collectionName,
        filter: { _id: { $oid: plot.id } },
        limit: 1
      }) as typeof rawFind;
      console.log("[updatePlotDetails] Raw find on 'plot' with $oid:", JSON.stringify(rawFind?.cursor?.firstBatch?.length));
    }

    // Last resort: list collections
    if (!rawFind?.cursor?.firstBatch?.length) {
      const collections = await prisma.$runCommandRaw({ listCollections: 1 }) as { cursor?: { firstBatch?: Array<{ name: string }> } };
      const names = collections?.cursor?.firstBatch?.map((c: { name: string }) => c.name) || [];
      console.log("[updatePlotDetails] Available collections:", names);
      return { success: false, error: `Cannot find document in any collection. Collections: ${names.join(', ')}. plotId: ${plot.id}` };
    }

    console.log("[updatePlotDetails] Found! Using collection:", collectionName, "First doc:", JSON.stringify(rawFind?.cursor?.firstBatch?.[0]).substring(0, 200));

    // Now do the actual update on the correct collection
    const result = await prisma.$runCommandRaw({
      findAndModify: collectionName,
      query: { _id: { $oid: plot.id } },
      update: { $set: updateData as any },
      new: true
    }) as { ok?: number; value?: unknown; lastErrorObject?: { n: number; updatedExisting: boolean } };

    console.log("[updatePlotDetails] findAndModify result ok:", result.ok, "updatedExisting:", result.lastErrorObject?.updatedExisting);

    if (result.ok === 1 && result.lastErrorObject?.updatedExisting) {
      revalidatePath(`/farm/${plot.farmId}/plot/${plotId}`);
      revalidatePath(`/farm/${plot.farmId}/plot/${plotId}/user-inputs`);
      return { success: true };
    } else {
      return { success: false, error: `findAndModify on '${collectionName}' failed. ok=${result.ok}, updatedExisting=${result.lastErrorObject?.updatedExisting}` };
    }
  } catch (error) {
    console.error("Failed to update plot details:", error);
    const message = error instanceof Error ? error.message : "Failed to update plot details";
    return { success: false, error: message };
  }
}

export async function addPlotPhoto(plotId: string, data: {
  url: string;
  type: 'CROP' | 'SOIL' | 'OVERVIEW' | 'DAMAGE' | 'OTHER';
  tags?: string[];
  notes?: string;
  date: Date;
}) {
    try {
        const photo = await prisma.plotPhoto.create({
            data: {
                plotId,
                url: data.url,
                type: data.type,
                tags: data.tags || [],
                notes: data.notes,
                date: data.date
            }
        });
        revalidatePath(`/farm/[id]/plot/${plotId}/user-inputs`);
        return { success: true, data: photo };
    } catch (error) {
        console.error("Failed to add plot photo:", error);
        return { success: false, error: "Failed to add plot photo" };
    }
}

export async function deletePlotPhoto(photoId: string) {
    try {
        const photo = await prisma.plotPhoto.delete({
            where: { id: photoId }
        });
        revalidatePath(`/farm/[id]/plot/${photo.plotId}/user-inputs`);
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
        await prisma.iPCamera.delete({
            where: { id: cameraId }
        });
        revalidatePath(`/farm/[id]/plot/${plotId}/user-inputs`);
        return { success: true };
    } catch (error) {
        console.error("Failed to delete IP camera:", error);
        return { success: false, error: "Failed to delete IP camera" };
    }
}



export async function toggleIPCameraStatus(plotId: string, cameraId: string, currentStatus: string) {
    try {
        const newStatus = currentStatus === 'ACTIVE' ? 'OFFLINE' : 'ACTIVE';
        await prisma.iPCamera.update({
            where: { id: cameraId },
            data: { status: newStatus }
        });
        revalidatePath(`/farm/[id]/plot/${plotId}/user-inputs`);
        return { success: true, newStatus };
    } catch (error) {
        console.error("Failed to toggle camera status:", error);
        return { success: false, error: "Failed to toggle status" };
    }
}

export async function addSoilAnalysis(plotId: string, data: any) {
    try {
        const analysis = await prisma.soilAnalysis.create({
            data: {
                plotId,
                date: data.date || new Date(),
                ...data
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
