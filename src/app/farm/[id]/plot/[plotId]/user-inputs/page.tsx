import { notFound } from "next/navigation";
import { getPlot, getFarm, getPlotCenter } from "@/lib/farm-services";
import PlotIdentityForm from "@/components/farm/PlotIdentityForm";
import PlotVisualGroundTruth from "@/components/farm/PlotVisualGroundTruth";
import PlotSoilData from "@/components/farm/PlotSoilData";

interface PageProps {
  params: Promise<{
    id: string;
    plotId: string;
  }>;
}

export default async function UserInputsPage({ params }: PageProps) {
  const { id, plotId } = await params;

  // 1. Fetch Data
  const [plot, farm] = await Promise.all([
    getPlot(plotId),
    getFarm(id)
  ]);

  if (!plot || !farm) {
    notFound();
  }

  // 2. Calculate Center for Map
  const { lat, lng } = getPlotCenter(plot, farm);

  return (
    <div className="min-h-screen p-6 pb-24 space-y-8 max-w-7xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
      
      {/* Header */}
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100 flex items-center gap-3">
          📝 User Inputs
          <span className="text-sm font-normal text-slate-500 bg-slate-100 dark:bg-slate-800 px-3 py-1 rounded-full border border-slate-200 dark:border-slate-700">
            Phase 1: Identity & Geometry
          </span>
        </h1>
        <p className="text-slate-600 dark:text-slate-400 max-w-2xl">
          Manage your plot's core identity, boundaries, and physical characteristics. 
          Correct geometry ensures accurate satellite analysis.
        </p>
      </div>



      {/* Section 1: Identity & Geometry */}
      <section>
        <PlotIdentityForm plot={plot} lat={lat} lng={lng} />
      </section>

      {/* Section 2: Visual Ground Truth */}
      <section>
         <PlotVisualGroundTruth plot={plot} />
      </section>

      {/* Section 3: Soil & Sensors */}
      <section>
         <PlotSoilData 
            plotId={plot.id} 
            soilAnalyses={plot.soilAnalyses || []} 
            sensors={plot.sensors || []}
         />
      </section>

    </div>
  );
}
