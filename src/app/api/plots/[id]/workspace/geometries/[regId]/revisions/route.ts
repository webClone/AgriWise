import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { authenticatedUserId } from "@/lib/tenant-authorization";

const objectIdRegex = /^[a-f\d]{24}$/i;

async function authorizedScope(rawPlotId: string, userId: string) {
  const plot = await prisma.plot.findFirst({
    where: { id: rawPlotId, farm: { userId } },
    select: { id: true, farm: { select: { id: true, userId: true } } },
  });
  return plot ? { tenantId: plot.farm.userId, farmId: plot.farm.id, plotId: plot.id } : null;
}

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string; regId: string }> }
) {
  try {
    const userId = await authenticatedUserId();
    if (!userId) return NextResponse.json({ error: "Authentication required" }, { status: 401 });
    const { id: plotId, regId } = await params;
    if (!objectIdRegex.test(plotId)) {
      return NextResponse.json({ error: "Resource not found" }, { status: 404 });
    }
    const scope = await authorizedScope(plotId, userId);
    if (!scope) return NextResponse.json({ error: "Plot not found" }, { status: 404 });

    const registration = await prisma.workspaceGeometryRegistration.findFirst({
      where: objectIdRegex.test(regId)
        ? { id: regId, plotId: scope.plotId }
        : { plotId: scope.plotId, OR: [{ entityId: regId }, { registrationKey: regId }] },
      select: { id: true, name: true, entityKind: true, status: true, revision: true },
    });
    if (!registration) return NextResponse.json({ error: "Geometry registration not found" }, { status: 404 });

    const revisions = await prisma.workspaceGeometryRevision.findMany({
      where: { registrationId: registration.id },
      orderBy: { revision: "asc" },
    });

    return NextResponse.json({
      success: true,
      registration_id: registration.id,
      current_revision: registration.revision,
      current_status: registration.status,
      revisions: revisions.map((r) => ({
        id: r.id,
        revision: r.revision,
        operation: r.operation,
        geometry: r.geometry,
        geometryDigest: r.geometryDigest,
        name: r.name,
        notes: r.notes,
        editorId: r.editorId,
        createdAt: r.createdAt.toISOString(),
      })),
    });
  } catch (error) {
    console.error("[workspace/geometries/[regId]/revisions:GET]", error);
    return NextResponse.json({ error: "Unable to fetch revision history" }, { status: 500 });
  }
}
