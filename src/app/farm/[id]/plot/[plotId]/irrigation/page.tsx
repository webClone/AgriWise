import IrrigationDashboard from "@/components/irrigation/IrrigationDashboard";
import { getAuthorizedPlotRouteContext } from "@/lib/farm-services";
import { getSession } from "@/lib/session";
import { notFound } from "next/navigation";

export const metadata = {
  title: "Irrigation Control Center | AgriWise",
  description: "Real-time irrigation fleet management, scheduling, and monitoring",
};

export default async function IrrigationPage({ params }: { params: Promise<{ id: string; plotId: string }> }) {
  const { id: farmId, plotId } = await params;
  const routeContext = await getAuthorizedPlotRouteContext(plotId, farmId);
  if (!routeContext) notFound();

  const session = await getSession();
  if (!session?.userId || session.userId !== routeContext.ownerUserId) {
    if (process.env.NODE_ENV === "development") {
      return null;
    }
    notFound();
  }

  return (
    <div style={{ padding: "24px 16px", maxWidth: 1100, margin: "0 auto" }}>
      <IrrigationDashboard />
    </div>
  );
}
