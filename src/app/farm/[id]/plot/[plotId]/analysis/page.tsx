import { getAuthorizedPlotRouteContext } from "@/lib/farm-services";
import { notFound } from "next/navigation";
import { getSession } from "@/lib/session";
import AgriBrainCommandCenterClient from "@/components/farm/intelligence/AgriBrainCommandCenterClient";
import { isActiveCropCycleStatus } from "@/lib/agribrain/crop-cycle-status.mjs";

export default async function AnalysisPage({ params }: { params: Promise<{ id: string; plotId: string }> }) {
  const { id: farmId, plotId } = await params;
  
  const routeContext = await getAuthorizedPlotRouteContext(plotId, farmId);
  if (!routeContext) notFound();

  const { plot, farm, cropCycles } = routeContext;
  const currentCrop = cropCycles.find(c => isActiveCropCycleStatus(c.status)) ?? null;

  return (
    <div className="min-h-screen pb-32 bg-slate-50 dark:bg-[#0a0f1a] animate-in fade-in duration-500">
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      <AgriBrainCommandCenterClient plot={plot} farm={farm} currentCrop={currentCrop as any} />
    </div>
  );
}
