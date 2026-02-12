import { prisma } from "@/lib/prisma";
import { getPlot, getFarm, getCropCycles, getPlotCenter } from "@/lib/farm-services";
import { getFAOLandIntelligence } from "@/lib/agribrain/fao-data-service";

import FarmMapClient from "@/components/farm/FarmMapClient";
import AgriBrainChat from "@/components/farm/AgriBrainChat";

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
    <div className="w-full pb-32 px-4 md:px-8">
      {/* DASHBOARD GRID */}
      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        

        
        {/* Re-implementing the Grid for Map + Chat as the ONLY content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[75vh]">
            
            {/* COL 1: Map (2/3 Width) */}
            {farm && (
                <div className="lg:col-span-2 card fade-in overflow-hidden p-0 h-full flex flex-col">
                    <div style={{ flex: 1, position: "relative" }}>
                        <FarmMapClient 
                            farms={[farm]} 
                            plots={[plot]} 
                            cropName={currentCrop?.cropNameAr || currentCrop?.cropCode}
                        />
                    </div>
                </div>
            )}

            {/* COL 2: AI Advisor (1/3 Width) */}
            <div className="h-full">
                <AgriBrainChat 
                    context={{ 
                        plot, 
                        farm, 
                        crop: currentCrop, 
                        faoData: faoContext
                    }} 
                />
            </div>
        </div>

      </div>
    </div>
  );
}
