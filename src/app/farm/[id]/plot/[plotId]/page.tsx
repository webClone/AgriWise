import { getAuthorizedPlotRouteContext } from "@/lib/farm-services";
import PlotDashboard from "@/components/farm/PlotDashboard";
import { notFound } from "next/navigation";
import { getSession } from "@/lib/session";
import DevelopmentSessionBootstrap from "@/components/auth/DevelopmentSessionBootstrap";
import { isActiveCropCycleStatus } from "@/lib/agribrain/crop-cycle-status.mjs";

export default async function PlotDetailsPage({ params }: { params: Promise<{ id: string; plotId: string }> }) {
  const { id: farmIdRaw, plotId: plotIdRaw } = await params;
  const farmId = farmIdRaw.replace(/\/+$/, "");
  const plotId = plotIdRaw.replace(/\/+$/, "");
  const session = await getSession();

  if (!session?.userId && process.env.NODE_ENV !== "development") {
    notFound();
  }
  
  const routeContext = await getAuthorizedPlotRouteContext(plotId, farmId);
  if (!routeContext) {
    if (process.env.NODE_ENV === "development") {
      return <DevelopmentSessionBootstrap plotId={plotId} farmId={farmId} />;
    }
    notFound();
  }

  const { plot, farm, cropCycles, ownerUserId } = routeContext;
  const currentCrop = cropCycles.find(c => isActiveCropCycleStatus(c.status));

  // If the active session is not the plot owner, layout.tsx renders
  // DevelopmentSessionBootstrap (dev) or notFound (prod).
  // page.tsx must not render PlotDashboard outside the required providers.
  if (!session?.userId || session.userId !== ownerUserId) {
    if (process.env.NODE_ENV === "development") {
      return null;
    }
    notFound();
  }

  return (
    <div className="w-full h-full" style={{ minHeight: 'calc(100vh - 48px)' }} suppressHydrationWarning={true}>
      <PlotDashboard
        farm={farm}
        plot={plot}
        cropName={currentCrop?.cropNameAr || currentCrop?.cropCode}
        context={{ 
          plot, 
          farm, 
          crop: currentCrop, 
        }}
      />
    </div>
  );
}
