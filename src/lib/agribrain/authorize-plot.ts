import { prisma } from "@/lib/db";
import { getSession } from "@/lib/session";

export async function authorizePlot(plotId: string, farmId?: string | null) {
  const session = await getSession();
  const userId = session?.userId || null;

  if (!userId) {
    return { status: 401 as const, plot: null };
  }

  const plot = await prisma.plot.findFirst({
    where: {
      id: plotId,
      ...(farmId ? { farmId } : {}),
      farm: { userId },
    },
    select: {
      id: true,
      farmId: true,
      geoJson: true,
      farm: {
        select: { latitude: true, longitude: true },
      },
    },
  });

  return plot
    ? { status: 200 as const, plot, userId }
    : { status: 404 as const, plot: null, userId: null };
}
