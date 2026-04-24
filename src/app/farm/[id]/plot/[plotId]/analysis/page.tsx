import { getPlot, getFarm, getCropCycles } from "@/lib/farm-services";
import { notFound } from "next/navigation";
import AgriBrainCommandCenterClient from "@/components/farm/intelligence/AgriBrainCommandCenterClient";

export default async function AnalysisPage({ params }: { params: Promise<{ id: string; plotId: string }> }) {
  const { id: farmId, plotId } = await params;
  
  const plot = await getPlot(plotId);
  const farm = await getFarm(farmId);
  const cropCycles = await getCropCycles(plotId);
  const currentCrop = cropCycles.find(c => c.status !== 'HARVESTED') ?? null;

  if (!plot || !farm) return notFound();

  return (
    <div className="min-h-screen pb-32 bg-slate-50 dark:bg-[#0a0f1a] animate-in fade-in duration-500">
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      <AgriBrainCommandCenterClient plot={plot} farm={farm} currentCrop={currentCrop as any} />
    </div>
  );
}
