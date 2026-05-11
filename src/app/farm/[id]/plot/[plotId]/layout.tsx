import PlotContextBand from "@/components/farm/PlotContextBand";
import PlotControls from "@/components/farm/PlotControls";
import { getPlot, getFarm, getCropCycles, getPlotCenter } from "@/lib/farm-services";
import { getFAOLandIntelligence } from "@/lib/agribrain/fao-data-service";
import { Layer10Provider } from "@/hooks/useLayer10";
import { PlotIntelligenceProvider } from "@/hooks/usePlotIntelligence";
import PlotLayoutClient from "./PlotLayoutClient";

export default async function PlotLayout({
  children,
  params
}: {
  children: React.ReactNode;
  params: Promise<{ id: string; plotId: string }>;
}) {
  const { id: farmId, plotId } = await params;
  
  // Fetch Shared Data
  const plot = await getPlot(plotId);
  const farm = await getFarm(farmId);
  const cropCycles = await getCropCycles(plotId);
  const currentCrop = cropCycles.find(c => c.status !== 'HARVESTED');
  
  // Tasks not needed in layout usually, but kept in page.tsx if specific there.
  
  // Coordinate Calculation for Context
  const { lat, lng } = getPlotCenter(plot, farm);

  // FAO Context
  let faoContext = null;
  try {
     faoContext = await getFAOLandIntelligence(lat, lng, currentCrop?.cropCode || "generic");
  } catch (e) {
     console.error("FAO Context fetch failed", e);
  }

  // Handle Missing Plot (Optional: redirect or error UI here?)
  if (!plot) {
      return (
          <div className="p-8 text-center">
              <h1 className="text-2xl font-bold text-red-500">Plot Not Found</h1>
              <p>Unable to load plot {plotId}</p>
          </div>
      );
  }

  // V2.2: Defer map view detection to Client Component
  // as headers() is unreliable during client-side navigation.
  return (
    <Layer10Provider>
      <PlotIntelligenceProvider>
      <PlotLayoutClient 
        farmId={farmId}
        topBarMap={
          <PlotContextBand 
            plotName={plot.name}
            plotArea={plot.area}
            cropName={currentCrop?.cropNameAr || currentCrop?.cropCode || "No Crop"}
            cropStage={currentCrop?.stage}
            telemetry={faoContext?.realTime}
            farmId={farmId}
          />
        }
        topBarFull={
          <>
            <div className="flex-1">
                <PlotContextBand 
                    plotName={plot.name}
                    plotArea={plot.area}
                    cropName={currentCrop?.cropNameAr || currentCrop?.cropCode || "No Crop"}
                    cropStage={currentCrop?.stage}
                    telemetry={faoContext?.realTime}
                />
            </div>
            <div className="min-w-fit">
                <PlotControls plot={plot} farmId={farmId} />
            </div>
          </>
        }
      >
        {children}
      </PlotLayoutClient>
      </PlotIntelligenceProvider>
    </Layer10Provider>
  );
}
