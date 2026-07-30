import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/session";

export async function authenticatedUserId(): Promise<string | null> {
  const session = await getSession();
  return session?.userId || null;
}

export async function userOwnsFarm(
  userId: string,
  farmId: string,
): Promise<boolean> {
  return Boolean(await prisma.farm.findFirst({
    where: { id: farmId, userId },
    select: { id: true },
  }));
}

export async function userOwnsPlot(
  userId: string,
  plotId: string,
): Promise<boolean> {
  return Boolean(await prisma.plot.findFirst({
    where: { id: plotId, farm: { userId } },
    select: { id: true },
  }));
}

export async function userOwnsCycle(
  userId: string,
  cropCycleId: string,
): Promise<boolean> {
  return Boolean(await prisma.cropCycle.findFirst({
    where: {
      id: cropCycleId,
      plot: { farm: { userId } },
    },
    select: { id: true },
  }));
}

export async function userOwnsTask(
  userId: string,
  taskId: string,
): Promise<boolean> {
  return Boolean(await prisma.cropTask.findFirst({
    where: {
      id: taskId,
      cropCycle: { plot: { farm: { userId } } },
    },
    select: { id: true },
  }));
}

export async function userOwnsInput(
  userId: string,
  inputId: string,
): Promise<boolean> {
  return Boolean(await prisma.inputLog.findFirst({
    where: {
      id: inputId,
      cropCycle: { plot: { farm: { userId } } },
    },
    select: { id: true },
  }));
}

export async function userOwnsSensor(
  userId: string,
  sensorId: string,
): Promise<boolean> {
  return Boolean(await prisma.sensor.findFirst({
    where: {
      id: sensorId,
      plot: { farm: { userId } },
    },
    select: { id: true },
  }));
}

export async function userOwnsSoilAnalysis(
  userId: string,
  analysisId: string,
): Promise<boolean> {
  return Boolean(await prisma.soilAnalysis.findFirst({
    where: {
      id: analysisId,
      plot: { farm: { userId } },
    },
    select: { id: true },
  }));
}
