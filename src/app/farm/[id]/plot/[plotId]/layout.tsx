import FloatingActionMenu from "@/components/farm/FloatingActionMenu";
import Link from "next/link";
import PlotContextBand from "@/components/farm/PlotContextBand";
import PlotControls from "@/components/farm/PlotControls";
import { getPlot, getFarm, getCropCycles, getPlotCenter } from "@/lib/farm-services";
import { getFAOLandIntelligence } from "@/lib/agribrain/fao-data-service";

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

  return (
    <div className="flex flex-col min-h-screen w-full">
        {/* Persistent Header & Context Band */}
        <div className="p-4 md:p-8 pb-0"> {/* Matches page padding for alignment */}
            <div className="flex flex-col md:flex-row items-stretch gap-4 mb-6">
                {/* Back Button */}
                <Link 
                    href={`/farm/${farmId}`} 
                    className="flex items-center justify-center w-12 h-auto rounded-xl bg-slate-800/50 hover:bg-slate-700/50 border border-slate-700/50 transition-colors"
                >
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5 text-slate-400">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
                    </svg>
                </Link>

                {/* Context Band (Flexible Width) */}
                <div className="flex-1">
                    <PlotContextBand 
                        plotName={plot.name}
                        plotArea={plot.area}
                        cropName={currentCrop?.cropNameAr || currentCrop?.cropCode || "No Crop"}
                        cropStage={currentCrop?.stage}
                        telemetry={faoContext?.realTime}
                    />
                </div>

                {/* Controls (Right Aligned) */}
                <div className="min-w-fit">
                    <PlotControls plot={plot} farmId={farmId} />
                </div>
            </div>
        </div>

        {/* Page Content */}
        <main className="flex-1 w-full"> {/* Removed duplicate padding if page has it, or coordinate */}
             {children}
        </main>

        <FloatingActionMenu />
    </div>
  );
}
