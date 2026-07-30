import { getAuthorizedPlotRouteContext } from "@/lib/farm-services";
import PlotDashboard from "@/components/farm/PlotDashboard";
import { notFound } from "next/navigation";
import { getSession } from "@/lib/session";
import DevelopmentSessionBootstrap from "@/components/auth/DevelopmentSessionBootstrap";

export default async function PlotDetailsPage({ params }: { params: Promise<{ id: string; plotId: string }> }) {
  const { id: farmId, plotId } = await params;
  const session = await getSession();
  if (!session?.userId) {
    if (process.env.NODE_ENV === "development") {
      return <DevelopmentSessionBootstrap plotId={plotId} farmId={farmId} />;
    }
    notFound();
  }
  
  const routeContext = await getAuthorizedPlotRouteContext(plotId, farmId);
  if (!routeContext) {
    if (process.env.NODE_ENV === "development") {
      return <DevelopmentSessionBootstrap plotId={plotId} farmId={farmId} />;
    }
    notFound();
  }

  const { plot, farm, cropCycles } = routeContext;
  const currentCrop = cropCycles.find(c => c.status !== 'HARVESTED');

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

