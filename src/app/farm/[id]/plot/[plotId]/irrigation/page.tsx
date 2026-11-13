import IrrigationDashboard from "@/components/irrigation/IrrigationDashboard";
import { getAuthorizedPlotRouteContext } from "@/lib/farm-services";
import { notFound } from "next/navigation";

export const metadata = {
  title: "Irrigation Control Center | AgriWise",
  description: "Real-time irrigation fleet management, scheduling, and monitoring",
};

export default async function IrrigationPage({
  params,
}: {
  params: Promise<{ id: string; plotId: string }>;
}) {
  const { id: farmId, plotId } = await params;
  // Defense in depth: this child route must enforce plot ownership even
  // if Next.js changes how it reuses the parent layout across navigation.
  if (!await getAuthorizedPlotRouteContext(plotId, farmId)) notFound();
  return (
    <div style={{ padding: "24px 16px", maxWidth: 1100, margin: "0 auto" }}>
      <IrrigationDashboard />
    </div>
  );
}
