import { prisma } from "@/lib/prisma";
import { ObjectId } from "bson";

export async function getPlot(id: string) {
  try {
    if (!ObjectId.isValid(id) || id.match(/\.(png|jpg|jpeg|gif|ico|svg)$/)) return null;
    
    // Use findFirst instead of findUnique to avoid potential ID format issues
    let plot = await prisma.plot.findFirst({
      where: { id },
      include: { photos: true, cameras: true, soilAnalyses: { orderBy: { date: 'desc' } }, sensors: true }
    });
    
    // Fallback: If findFirst by ID failed, fetch all plots and find by ID in memory
    if (!plot) {
        console.log(`[getPlot] Direct lookup failed for ${id}, trying fallback...`);
        const allPlots = await prisma.plot.findMany({ include: { photos: true, cameras: true, soilAnalyses: true, sensors: true } });
        plot = allPlots.find(p => p.id === id) || null;
    }
    
    if (!plot) return null;
    
    return {
      id: plot.id,
      name: plot.name,
      nameAr: plot.nameAr,
      area: plot.area,
      soilType: plot.soilType,
      irrigation: plot.irrigation,
      farmId: plot.farmId,
      geoJson: plot.geoJson,
      perimeter: plot.perimeter,
      ownership: plot.ownership,
      irrigationDistrict: plot.irrigationDistrict,
      physicalConstraints: plot.physicalConstraints,
      photos: plot.photos || [],
      cameras: plot.cameras || [],
      soilAnalyses: plot.soilAnalyses || [],
      sensors: plot.sensors || []
    };
  } catch (error) {
    console.error("getPlot error:", error);
    return null;
  }
}

export async function getCropCycles(plotId: string) {
  // Prevent Prisma crash on image requests or invalid IDs
  if (plotId.includes('.') || plotId.length < 15) return [];

  try {
    const cycles = await prisma.cropCycle.findMany({
      where: { plotId },
      orderBy: { plantDate: 'desc' }
    });
    
    return cycles.map(c => ({
      id: c.id,
      cropCode: c.cropCode,
      cropNameAr: c.cropNameAr,
      variety: c.variety,
      status: c.status,
      startDate: c.plantDate,
      stage: c.status 
    }));
  } catch (error) {
    console.error("getCropCycles error:", error);
    return [];
  }
}

export async function getFarm(id: string) {
  try {
    if (!ObjectId.isValid(id)) return null;
    
    let farm = await prisma.farm.findFirst({
      where: { id },
    });
    
    if (!farm) {
       const allFarms = await prisma.farm.findMany();
       farm = allFarms.find(f => f.id === id) || null;
    }
    
    if (!farm) return null;
    
    return {
      id: farm.id,
      name: farm.name,
      nameAr: farm.nameAr,
      wilaya: farm.wilaya,
      latitude: farm.latitude,
      longitude: farm.longitude,
      totalArea: farm.totalArea,
    };
  } catch (error) {
    console.error("getFarm error:", error);
    return null;
  }
}

export function getPlotCenter(plot: any, farm: any) {
    let lat = farm?.latitude || 36.75;
    let lng = farm?.longitude || 3.05;
  
    if (plot?.geoJson) {
      const geo = plot.geoJson as any;
      if (geo?.geometry?.coordinates) {
          try {
              const coords = geo.geometry.type === 'MultiPolygon' 
                  ? geo.geometry.coordinates[0][0] 
                  : geo.geometry.coordinates[0];
              
              if (coords && coords.length > 0) {
                  const lats = coords.map((c: any) => c[1]);
                  const lngs = coords.map((c: any) => c[0]);
                  lat = (Math.min(...lats) + Math.max(...lats)) / 2;
                  lng = (Math.min(...lngs) + Math.max(...lngs)) / 2;
              }
          } catch (e) { console.error("GeoJSON parse error", e); }
      }
    }
    return { lat, lng };
  }
