import { getPlot, getFarm, getCropCycles, getPlotCenter } from "@/lib/farm-services";
import { getFAOLandIntelligence } from "@/lib/agribrain/fao-data-service";
import PlotDashboard from "@/components/farm/PlotDashboard";

export default async function PlotDetailsPage({ params }: { params: Promise<{ id: string; plotId: string }> }) {
  const { id: farmId, plotId } = await params;
  
  // Use Shared Services
  const plot = await getPlot(plotId);
  const farm = await getFarm(farmId);
  const cropCycles = await getCropCycles(plotId);
  const currentCrop = cropCycles.find(c => c.status !== 'HARVESTED');
  
  if (!plot) {
    return (
        <div style={{ padding: "2rem" }}>
            <h1>Debug: Plot Not Found</h1>
            <p>Target ID: &apos;{plotId}&apos;</p>
        </div>
    );
  }

  // Calculate coordinates using shared helper
  const { lat, lng } = getPlotCenter(plot, farm);

  // Server-side fetch of FAO Context
  let faoContext = null;
  try {
     faoContext = await getFAOLandIntelligence(lat, lng, currentCrop?.cropCode || "generic");
  } catch (e) {
     console.error("FAO Context fetch failed", e);
  }

  return (
    <div className="w-full h-full" style={{ minHeight: 'calc(100vh - 48px)' }}>
      <PlotDashboard
        farm={farm}
        plot={plot}
        cropName={currentCrop?.cropNameAr || currentCrop?.cropCode}
        context={{ 
          plot, 
          farm, 
          crop: currentCrop, 
          faoData: faoContext
        }}
      />
    </div>
  );
}
