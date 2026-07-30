import { prisma } from "@/lib/prisma";
import { getAuthorizedPlotRouteContext, getPlotCenter } from "@/lib/farm-services";
import { getFAOLandIntelligence } from "@/lib/agribrain/fao-data-service";

import PlotPageClient from "@/components/farm/PlotPageClient";
import RawSatelliteViewer from "@/components/farm/RawSatelliteViewer";
import RawTelemetryHub from "@/components/farm/RawTelemetryHub";
import { notFound } from "next/navigation";

export default async function RawDataPage({ params }: { params: Promise<{ id: string; plotId: string }> }) {
  const { id: farmId, plotId } = await params;
  
  const routeContext = await getAuthorizedPlotRouteContext(plotId, farmId);
  if (!routeContext) notFound();

  const { plot, farm, cropCycles } = routeContext;
  const currentCrop = cropCycles.find(c => c.status !== 'HARVESTED');
  
  // Fetch tasks for the current crop if exists
  let currentTasks: any[] = [];
  if (currentCrop) {
      currentTasks = await prisma.cropTask.findMany({
          where: { cropCycleId: currentCrop.id },
          orderBy: { dueDate: 'asc' }
      });
  }

  // Calculate coordinates using shared helper
  const center = getPlotCenter(plot, farm);
  if (!center) notFound();
  const { lat, lng } = center;

  return (
    <div className="w-full pb-32 px-4 md:px-8">
      {/* DASHBOARD GRID */}
      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        
        {/* ROW 1: SATELLITE INTELLIGENCE (Modernized, Backend-Driven) */}
        <RawSatelliteViewer
          lat={lat}
          lng={lng}
          geoJson={plot?.geoJson as any}
          plotId={plotId}
          farmId={farmId}
        />

            <div className="card fade-in mb-6" style={{ padding: 0, overflow: "hidden" }}>
                <PlotPageClient 
                    plotId={plotId} 
                    activeCycle={currentCrop || null} 
                    tasks={currentTasks} 
                />
            </div>

        {/* ROW 3: DEEP TELEMETRY HUB (Replaces individual API calls) */}
        <div className="w-full">
            <RawTelemetryHub plotId={plotId} farmId={farmId} />
        </div>

      </div>
    </div>
  );
}
