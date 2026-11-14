import { getAuthorizedPlotRouteContext } from "@/lib/farm-services";
import PlotWorkspaceFeatureGate from "@/components/farm/workspace/PlotWorkspaceFeatureGate";
import { notFound } from "next/navigation";
import { getSession } from "@/lib/session";
import DevelopmentSessionBootstrap from "@/components/auth/DevelopmentSessionBootstrap";
import { isActiveCropCycleStatus } from "@/lib/agribrain/crop-cycle-status.mjs";

export default async function PlotDetailsPage({ params }: { params: Promise<{ id: string; plotId: string }> }) {
  const { id: farmIdRaw, plotId: plotIdRaw } = await params;
  const farmId = farmIdRaw.replace(/\/+$/, "");
  const plotId = plotIdRaw.replace(/\/+$/, "");
  const session = await getSession();

  if (!session?.userId) {
    if (process.env.NODE_ENV === "development") {
      return <DevelopmentSessionBootstrap plotId={plotId} farmId={farmId} />;
    }
    notFound();
  }

  const routeContext = await getAuthorizedPlotRouteContext(plotId, farmId);
  // Do not switch an already signed-in user into another owner's session.
  if (!routeContext) notFound();

  const { plot, farm, cropCycles } = routeContext;
  const currentCrop = cropCycles.find(c => isActiveCropCycleStatus(c.status));

  const verifiedScope = {
    tenantId: session.userId,
    farmId,
    plotId,
    cropCycleId: currentCrop?.id || null,
    geometryHash: (plot as any)?.geometryHash || null,
    geometryVersion: (plot as any)?.geometryVersion ?? null,
  };

  return (
    <div className="w-full h-full" style={{ minHeight: 'calc(100vh - 48px)' }} suppressHydrationWarning={true}>
      <PlotWorkspaceFeatureGate
        farm={farm}
        plot={plot}
        cropName={currentCrop?.cropNameAr || currentCrop?.cropCode}
        context={{ 
          plot, 
          farm, 
          crop: currentCrop, 
        }}
        verifiedScope={verifiedScope}
      />
    </div>
  );
}
