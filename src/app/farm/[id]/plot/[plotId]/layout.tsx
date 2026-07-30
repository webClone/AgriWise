import PlotContextBand from "@/components/farm/PlotContextBand";
import PlotControls from "@/components/farm/PlotControls";
import { getAuthorizedPlotRouteContext, getPlotCenter } from "@/lib/farm-services";
import { getFAOLandIntelligence } from "@/lib/agribrain/fao-data-service";
import { Layer10Provider } from "@/hooks/useLayer10";
import { PlotIntelligenceProvider } from "@/hooks/usePlotIntelligence";
import PlotLayoutClient from "./PlotLayoutClient";
import FarmThemeWrapper from "@/components/farm/FarmThemeWrapper";
import { notFound } from "next/navigation";
import { getSession } from "@/lib/session";

export default async function PlotLayout({
  children,
  params
}: {
  children: React.ReactNode;
  params: Promise<{ id: string; plotId: string }>;
}) {
  const { id: farmId, plotId } = await params;

  const session = await getSession();
  if (!session?.userId) {
    // The page owns the tightly-scoped localhost development bootstrap.  Do
    // not resolve plot data in the layout before that bootstrap can render.
    if (process.env.NODE_ENV === "development") return <>{children}</>;
    notFound();
  }
  
  const routeContext = await getAuthorizedPlotRouteContext(plotId, farmId);
  if (!routeContext) {
    // Let the child replace a stale local-development session for this exact
    // route. Production ownership still fails closed.
    if (process.env.NODE_ENV === "development") return <>{children}</>;
    notFound();
  }

  const { plot, farm, cropCycles } = routeContext;
  const currentCrop = cropCycles.find(c => c.status !== 'HARVESTED');
  
  // Tasks not needed in layout usually, but kept in page.tsx if specific there.
  
  // Coordinate Calculation for Context
  const center = getPlotCenter(plot, farm);
  if (!center) notFound();
  const { lat, lng } = center;

  // FAO Context
  let faoContext = null;
  try {
     faoContext = await getFAOLandIntelligence(lat, lng, currentCrop?.cropCode || "generic", plot?.id);
  } catch (e) {
     console.error("FAO Context fetch failed", e);
  }

  // V2.2: Defer map view detection to Client Component
  // as headers() is unreliable during client-side navigation.
  return (
    <FarmThemeWrapper>
    <Layer10Provider plotGeoJson={plot.geoJson}>
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
    </FarmThemeWrapper>
  );
}
