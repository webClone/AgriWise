import { getAuthorizedPlotRouteContext } from "@/lib/farm-services";
import { getSession } from "@/lib/session";
import { notFound } from "next/navigation";

export default async function LiveAssistancePage({ params }: { params: Promise<{ id: string; plotId: string }> }) {
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
    <div className="min-h-screen p-8 flex flex-col items-center justify-center text-center">
      <h1 className="text-3xl font-bold mb-4 text-slate-800 dark:text-slate-200">
        🎧 Live Assistance
      </h1>
      <p className="text-slate-600 dark:text-slate-400 max-w-md">
        Connect with expert agronomists or AI support agents in real-time.
      </p>
      <div className="mt-8 p-4 bg-slate-100 dark:bg-slate-800 rounded-lg animate-pulse">
        Coming Soon...
      </div>
    </div>
  );
}
