import { prisma } from "@/lib/db";
import { getSession } from "@/lib/session";

export async function authorizePlot(plotId: string, farmId?: string | null) {
  const session = await getSession();
  const userId = session?.userId || null;
  const isDev = process.env.NODE_ENV === "development";

  if (!userId && !isDev) {
    return { status: 401 as const, plot: null, userId: null };
  }

  const plot = await prisma.plot.findFirst({
    where: {
      id: plotId,
      ...(farmId ? { farmId } : {}),
      ...(userId && !isDev ? { farm: { userId } } : {}),
    },
    select: {
      id: true,
      farmId: true,
      geoJson: true,
      soilType: true,
      area: true,
      farm: {
        select: { id: true, latitude: true, longitude: true, userId: true },
      },
    },
  });

  return plot
    ? { status: 200 as const, plot, userId: userId || plot.farm.userId }
    : { status: 404 as const, plot: null, userId: null };
}
