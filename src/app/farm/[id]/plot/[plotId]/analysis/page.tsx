import { getAuthorizedPlotRouteContext } from "@/lib/farm-services";
import { notFound } from "next/navigation";
import AgriBrainCommandCenterClient from "@/components/farm/intelligence/AgriBrainCommandCenterClient";

export default async function AnalysisPage({ params }: { params: Promise<{ id: string; plotId: string }> }) {
  const { id: farmId, plotId } = await params;
  
  const routeContext = await getAuthorizedPlotRouteContext(plotId, farmId);
  if (!routeContext) return notFound();

  const { plot, farm, cropCycles } = routeContext;
  const currentCrop = cropCycles.find(c => c.status !== 'HARVESTED') ?? null;

  return (
    <div className="min-h-screen pb-32 bg-slate-50 dark:bg-[#0a0f1a] animate-in fade-in duration-500">
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      <AgriBrainCommandCenterClient plot={plot} farm={farm} currentCrop={currentCrop as any} />
    </div>
  );
}
