import PlotContextBand from "@/components/farm/PlotContextBand";
import PlotControls from "@/components/farm/PlotControls";
import { getAuthorizedPlotRouteContext, getPlotCenter } from "@/lib/farm-services";
import { getFAOLandIntelligence } from "@/lib/agribrain/fao-data-service";
import { Layer10Provider } from "@/hooks/useLayer10";
import { PlotIntelligenceProvider } from "@/hooks/usePlotIntelligence";
import { PlotTelemetryProvider } from "@/hooks/usePlotTelemetry";
import { ParcelAssessmentProvider } from "@/hooks/useParcelAssessment";
import PlotLayoutClient from "./PlotLayoutClient";
import FarmThemeWrapper from "@/components/farm/FarmThemeWrapper";
import { notFound } from "next/navigation";
import { getSession } from "@/lib/session";
import { isActiveCropCycleStatus } from "@/lib/agribrain/crop-cycle-status.mjs";

export default async function PlotLayout({
  children,
  params
}: {
  children: React.ReactNode;
  params: Promise<{ id: string; plotId: string }>;
}) {
  const { id: farmIdRaw, plotId: plotIdRaw } = await params;
  const farmId = farmIdRaw.replace(/\/+$/, "");
  const plotId = plotIdRaw.replace(/\/+$/, "");

  const session = await getSession();
  if (!session?.userId && process.env.NODE_ENV !== "development") {
    notFound();
  }
  
  const routeContext = await getAuthorizedPlotRouteContext(plotId, farmId);
  if (!routeContext) {
    if (process.env.NODE_ENV === "development") return <>{children}</>;
    notFound();
  }

  const { plot, farm, cropCycles } = routeContext;
  const currentCrop = cropCycles.find(c => isActiveCropCycleStatus(c.status));
  
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
    <ParcelAssessmentProvider plotGeoJson={plot.geoJson} cropCycleId={currentCrop?.id || null}>
    <Layer10Provider plotGeoJson={plot.geoJson}>
      <PlotTelemetryProvider scope={{ tenantId: String(session?.userId || farm.userId || ""), farmId, plotId }}>
      <PlotIntelligenceProvider>
      <PlotLayoutClient 
        farmId={farmId}
        topBarMap={
          <PlotContextBand 
            plotName={plot.name}
            plotArea={plot.area}
            cropName={currentCrop?.cropNameAr || currentCrop?.cropCode || "No Crop"}
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
      </PlotTelemetryProvider>
    </Layer10Provider>
    </ParcelAssessmentProvider>
    </FarmThemeWrapper>
  );
}
